"""
PAULUS - Financeiro.

Contas a receber, contas a pagar e o que elas dizem sobre o caixa do mes.

Duas decisoes atravessam o modulo:

Dinheiro em centavos inteiros. Somar 0,1 + 0,2 em ponto flutuante da
0,30000000000000004; num extrato de honorarios o erro aparece depois de algumas
dezenas de lancamentos, e extrato ninguem confere somando de cabeca. Aqui o
valor entra em centavos, soma em centavos e so vira "R$ 12.000,00" na hora de
mostrar.

Numero na tela e numero medido. Saldo, a receber, a pagar e atraso saem dos
lancamentos que existem - nao ha estimativa, nao ha projecao inventada. Quando
nao ha lancamento, o numero e zero e a tela diz que esta vazio, em vez de
mostrar um grafico bonito de dado que ninguem digitou.

O que o programa NAO faz, e a tela repete: nao emite nota fiscal (isso continua
no sistema da prefeitura) e nao gera boleto (isso sai do banco). Aqui se
registra o que foi emitido e se acompanha o vencimento.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

TIPOS = {"recebimento": "Recebimento", "despesa": "Despesa"}

CATEGORIAS = {
    "honorarios": "Honorários",
    "reembolso": "Reembolso",
    "folha": "Folha de pagamento",
    "imposto": "Impostos",
    "aluguel": "Aluguel",
    "sistemas": "Assinaturas e sistemas",
    "custas": "Custas e cartório",
    "outros": "Outros",
}

CAMPOS = ("tipo", "descricao", "centavos", "categoria", "cadastro_id",
          "vencimento", "liquidado_em", "observacao")


# ----------------------------------------------------------- dinheiro


def para_centavos(bruto) -> int:
    """
    "12.000,00" vira 1200000 centavos.

    Le do jeito que se escreve no Brasil: ponto separa milhar, virgula e o
    decimal. Ler ao contrario troca doze mil por doze.
    """
    if isinstance(bruto, int) and not isinstance(bruto, bool):
        return bruto
    if isinstance(bruto, float):
        return int(round(bruto * 100))

    texto = str(bruto or "").strip().replace("R$", "").strip()
    if not texto:
        return 0

    negativo = texto.startswith("-") or (texto.startswith("(") and texto.endswith(")"))
    texto = texto.strip("()-").strip()

    if "," in texto:
        limpo = texto.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", texto):
        limpo = texto.replace(".", "")
    else:
        limpo = texto

    try:
        valor = int(round(float(limpo) * 100))
    except ValueError:
        return 0
    return -valor if negativo else valor


def em_reais(centavos: int) -> str:
    """Centavos viram "R$ 12.000,00"."""
    sinal = "-" if centavos < 0 else ""
    inteiro, resto = divmod(abs(int(centavos)), 100)
    texto = f"{inteiro:,}".replace(",", ".")
    return f"{sinal}R$ {texto},{resto:02d}"


def curto(centavos: int) -> str:
    """"R$ 84.320" - sem centavos, para os cartoes de resumo."""
    inteiro = abs(int(centavos)) // 100
    return ("-" if centavos < 0 else "") + "R$ " + f"{inteiro:,}".replace(",", ".")


# --------------------------------------------------------- os lancamentos


class Financeiro:
    def __init__(self, base) -> None:
        self.base = base

    # ------------------------------------------------------------ escrever

    def salvar(self, dados: dict, id_: int | None = None) -> int:
        descricao = " ".join(str(dados.get("descricao", "")).split())
        if not descricao:
            raise ValueError("o lançamento precisa de uma descrição")

        tipo = dados.get("tipo")
        if tipo not in TIPOS:
            raise ValueError("o lançamento é recebimento ou despesa")

        centavos = abs(para_centavos(dados.get("valor", dados.get("centavos", 0))))
        if not centavos:
            raise ValueError("o lançamento precisa de um valor")

        limpo = {
            "tipo": tipo,
            "descricao": descricao,
            "centavos": centavos,
            "categoria": dados.get("categoria") if dados.get("categoria") in CATEGORIAS else "outros",
            "cadastro_id": dados.get("cadastro_id") or None,
            "vencimento": str(dados.get("vencimento", ""))[:10],
            "liquidado_em": str(dados.get("liquidado_em", ""))[:10],
            "observacao": str(dados.get("observacao", "")),
        }

        if id_:
            atribui = ", ".join(f"{c} = ?" for c in CAMPOS)
            self.base.escrever(
                f"UPDATE lancamentos SET {atribui} WHERE id = ?",
                tuple(limpo[c] for c in CAMPOS) + (id_,),
            )
            return id_

        colunas = ", ".join(CAMPOS)
        marcas = ", ".join("?" for _ in CAMPOS)
        return self.base.escrever(
            f"INSERT INTO lancamentos ({colunas}, criado_em) "
            f"VALUES ({marcas}, datetime('now','localtime'))",
            tuple(limpo[c] for c in CAMPOS),
        )

    def liquidar(self, id_: int, quando: str = "") -> bool:
        """Marca como recebido ou pago. Sem data, vale hoje."""
        dia = (quando or date.today().isoformat())[:10]
        return self.base.escrever(
            "UPDATE lancamentos SET liquidado_em = ? WHERE id = ?", (dia, id_)
        ) > 0

    def reabrir(self, id_: int) -> bool:
        return self.base.escrever(
            "UPDATE lancamentos SET liquidado_em = '' WHERE id = ?", (id_,)
        ) > 0

    def apagar(self, id_: int) -> bool:
        return self.base.escrever("DELETE FROM lancamentos WHERE id = ?", (id_,)) > 0

    # -------------------------------------------------------------- ler

    def listar(self, *, tipo: str = "", mes: str = "", situacao: str = "") -> list[dict]:
        sql = (
            "SELECT l.*, k.nome AS cadastro_nome,"
            " (SELECT COUNT(*) FROM comprovantes c WHERE c.lancamento_id = l.id) AS comprovantes"
            " FROM lancamentos l LEFT JOIN cadastros k ON k.id = l.cadastro_id WHERE 1=1"
        )
        parametros: list = []
        if tipo in TIPOS:
            sql += " AND l.tipo = ?"
            parametros.append(tipo)
        if mes:
            # Um lancamento pertence ao mes em que venceu; sem vencimento,
            # ao mes em que foi liquidado.
            sql += " AND (substr(l.vencimento,1,7) = ? OR (l.vencimento = '' AND substr(l.liquidado_em,1,7) = ?))"
            parametros += [mes, mes]
        if situacao == "aberto":
            sql += " AND l.liquidado_em = ''"
        elif situacao == "liquidado":
            sql += " AND l.liquidado_em != ''"

        sql += " ORDER BY (l.liquidado_em = '') DESC, l.vencimento, l.id"
        itens = self.base.buscar(sql, tuple(parametros))
        for i in itens:
            self._enfeitar(i)
        return itens

    @staticmethod
    def _enfeitar(item: dict) -> None:
        hoje = date.today().isoformat()
        item["valor"] = em_reais(item["centavos"])
        item["tipo_rotulo"] = TIPOS.get(item["tipo"], item["tipo"])
        item["categoria_rotulo"] = CATEGORIAS.get(item["categoria"], "Outros")
        item["aberto"] = not item["liquidado_em"]
        item["atrasado"] = bool(item["aberto"] and item["vencimento"] and item["vencimento"] < hoje)
        item["dias_atraso"] = _dias_entre(item["vencimento"], hoje) if item["atrasado"] else 0
        item["dias_para_vencer"] = (
            _dias_entre(hoje, item["vencimento"])
            if item["aberto"] and item["vencimento"] and item["vencimento"] >= hoje else None
        )
        if item["liquidado_em"]:
            item["situacao"] = ("recebido" if item["tipo"] == "recebimento" else "pago") + \
                f" {_br(item['liquidado_em'])}"
        elif item["atrasado"]:
            item["situacao"] = "atrasado " + _dias(item["dias_atraso"])
        elif item["vencimento"]:
            item["situacao"] = f"vence {_br(item['vencimento'])}"
        else:
            item["situacao"] = "sem data"

    def obter(self, id_: int) -> dict | None:
        item = self.base.um(
            "SELECT l.*, k.nome AS cadastro_nome FROM lancamentos l "
            "LEFT JOIN cadastros k ON k.id = l.cadastro_id WHERE l.id = ?",
            (id_,),
        )
        if item:
            self._enfeitar(item)
            item["comprovantes"] = self.comprovantes(id_)
        return item

    # ------------------------------------------------------- comprovantes

    def anexar(self, lancamento_id: int, nome: str, caminho: str = "", sha1: str = "") -> int:
        return self.base.escrever(
            "INSERT INTO comprovantes (lancamento_id, nome, sha1, caminho, criado_em) "
            "VALUES (?, ?, ?, ?, datetime('now','localtime'))",
            (lancamento_id, nome, sha1, caminho),
        )

    def comprovantes(self, lancamento_id: int) -> list[dict]:
        return self.base.buscar(
            "SELECT * FROM comprovantes WHERE lancamento_id = ? ORDER BY id", (lancamento_id,)
        )

    def tirar_comprovante(self, id_: int) -> bool:
        return self.base.escrever("DELETE FROM comprovantes WHERE id = ?", (id_,)) > 0

    # ---------------------------------------------------------- os numeros

    def painel(self, mes: str = "") -> dict:
        """
        Os cartoes do topo, todos somados dos lancamentos que existem.

        Saldo em caixa aqui e o que ja entrou menos o que ja saiu - dinheiro
        liquidado, nao previsto. Chamar de "saldo" uma soma que inclui o que
        ainda nao foi pago seria mostrar um caixa que nao existe.
        """
        mes = mes or date.today().strftime("%Y-%m")
        hoje = date.today().isoformat()

        entrou = self._soma("tipo = 'recebimento' AND liquidado_em != ''")
        saiu = self._soma("tipo = 'despesa' AND liquidado_em != ''")
        a_receber = self._soma("tipo = 'recebimento' AND liquidado_em = ''")
        a_pagar = self._soma("tipo = 'despesa' AND liquidado_em = ''")
        atrasado = self._soma(
            "tipo = 'recebimento' AND liquidado_em = '' AND vencimento != '' AND vencimento < ?",
            (hoje,),
        )

        entrou_mes = self._soma(
            "tipo = 'recebimento' AND liquidado_em != '' AND substr(liquidado_em,1,7) = ?", (mes,)
        )
        saiu_mes = self._soma(
            "tipo = 'despesa' AND liquidado_em != '' AND substr(liquidado_em,1,7) = ?", (mes,)
        )

        return {
            "mes": mes,
            "mes_rotulo": _mes_extenso(mes),
            "saldo": entrou - saiu,
            "saldo_texto": curto(entrou - saiu),
            "resultado_mes": entrou_mes - saiu_mes,
            "resultado_mes_texto": ("+" if entrou_mes >= saiu_mes else "") + curto(entrou_mes - saiu_mes),
            "a_receber": a_receber,
            "a_receber_texto": curto(a_receber),
            "a_receber_quantos": self._contar("tipo = 'recebimento' AND liquidado_em = ''"),
            "a_pagar": a_pagar,
            "a_pagar_texto": curto(a_pagar),
            "a_pagar_quantos": self._contar("tipo = 'despesa' AND liquidado_em = ''"),
            "atrasado": atrasado,
            "atrasado_texto": curto(atrasado),
            "atrasado_quantos": self._contar(
                "tipo = 'recebimento' AND liquidado_em = '' AND vencimento != '' AND vencimento < ?",
                (hoje,),
            ),
            "entradas_mes": entrou_mes,
            "entradas_mes_texto": curto(entrou_mes),
            "saidas_mes": saiu_mes,
            "saidas_mes_texto": curto(saiu_mes),
            "tem_dado": bool(self.base.contar("lancamentos")),
        }

    def _soma(self, onde: str, parametros: tuple = ()) -> int:
        linha = self.base.um(
            f"SELECT COALESCE(SUM(centavos), 0) AS s FROM lancamentos WHERE {onde}", parametros
        )
        return int(linha["s"]) if linha else 0

    def _contar(self, onde: str, parametros: tuple = ()) -> int:
        linha = self.base.um(
            f"SELECT COUNT(*) AS n FROM lancamentos WHERE {onde}", parametros
        )
        return int(linha["n"]) if linha else 0

    def fluxo(self, meses: int = 6) -> list[dict]:
        """Entradas e saidas mes a mes, para o grafico."""
        hoje = date.today().replace(day=1)
        saida = []
        for passo in range(meses - 1, -1, -1):
            alvo = hoje
            for _ in range(passo):
                alvo = (alvo - timedelta(days=1)).replace(day=1)
            chave = alvo.strftime("%Y-%m")
            entrou = self._soma(
                "tipo = 'recebimento' AND liquidado_em != '' AND substr(liquidado_em,1,7) = ?", (chave,)
            )
            saiu = self._soma(
                "tipo = 'despesa' AND liquidado_em != '' AND substr(liquidado_em,1,7) = ?", (chave,)
            )
            saida.append({
                "mes": chave,
                "rotulo": _MESES_CURTO[alvo.month - 1],
                "entradas": entrou,
                "saidas": saiu,
                "entradas_texto": curto(entrou),
                "saidas_texto": curto(saiu),
            })
        return saida

    def extrato(self, mes: str = "") -> dict:
        """
        O extrato do mes, com saldo correndo linha a linha.

        Ordena por data de liquidacao: extrato e o que aconteceu, na ordem em
        que aconteceu. Previsao entra na lista de aberto, nao no extrato.
        """
        mes = mes or date.today().strftime("%Y-%m")
        linhas = self.base.buscar(
            "SELECT l.*, k.nome AS cadastro_nome,"
            " (SELECT COUNT(*) FROM comprovantes c WHERE c.lancamento_id = l.id) AS comprovantes"
            " FROM lancamentos l LEFT JOIN cadastros k ON k.id = l.cadastro_id"
            " WHERE l.liquidado_em != '' AND substr(l.liquidado_em,1,7) = ?"
            " ORDER BY l.liquidado_em, l.id",
            (mes,),
        )

        anterior = self._soma(
            "liquidado_em != '' AND substr(liquidado_em,1,7) < ? AND tipo = 'recebimento'", (mes,)
        ) - self._soma(
            "liquidado_em != '' AND substr(liquidado_em,1,7) < ? AND tipo = 'despesa'", (mes,)
        )

        saldo = anterior
        itens = []
        for l in linhas:
            movimento = l["centavos"] if l["tipo"] == "recebimento" else -l["centavos"]
            saldo += movimento
            self._enfeitar(l)
            itens.append({
                **l,
                "movimento": movimento,
                "movimento_texto": ("+" if movimento >= 0 else "−") + em_reais(abs(movimento)).replace("R$ ", ""),
                "saldo": saldo,
                "saldo_texto": em_reais(saldo).replace("R$ ", ""),
                "dia": _br(l["liquidado_em"]),
            })

        return {
            "mes": mes,
            "mes_rotulo": _mes_extenso(mes),
            "saldo_anterior": anterior,
            "linhas": itens,
            "saldo_final": saldo,
            "saldo_final_texto": em_reais(saldo),
            "resultado": saldo - anterior,
            "resultado_texto": ("+" if saldo >= anterior else "") + em_reais(saldo - anterior),
        }

    def precisa_de_voce(self) -> list[dict]:
        """
        O que esta esperando uma decisao sua.

        Sai de regra, nao de opiniao: venceu e nao foi pago, vence nos
        proximos dias, ou foi liquidado sem comprovante. Cada linha aponta um
        lancamento de verdade.
        """
        hoje = date.today()
        limite = (hoje + timedelta(days=7)).isoformat()
        avisos = []

        atrasados = self.listar(tipo="recebimento", situacao="aberto")
        atrasados = [l for l in atrasados if l["atrasado"]]
        if atrasados:
            total = sum(l["centavos"] for l in atrasados)
            avisos.append({
                "grau": "urgente",
                "titulo": (_quantos(len(atrasados), "cobrança atrasada", "cobranças atrasadas")
                           + f" — {curto(total)}"),
                "detalhe": ", ".join(l["descricao"] for l in atrasados[:3]),
                "acao": "cobrar",
                "ids": [l["id"] for l in atrasados],
            })

        vencendo = self.base.buscar(
            "SELECT * FROM lancamentos WHERE tipo = 'despesa' AND liquidado_em = '' "
            "AND vencimento != '' AND vencimento <= ? ORDER BY vencimento",
            (limite,),
        )
        for l in vencendo:
            dias = _dias_entre(hoje.isoformat(), l["vencimento"])
            avisos.append({
                "grau": "urgente" if dias <= 2 else "atencao",
                "titulo": f"{l['descricao']} — {em_reais(l['centavos'])}",
                "detalhe": "vence hoje" if dias == 0 else (
                    "venceu há " + _dias(abs(dias)) if dias < 0 else "vence em " + _dias(dias)),
                "acao": "pagar",
                "ids": [l["id"]],
            })

        sem_comprovante = self.base.buscar(
            "SELECT l.id, l.descricao, l.centavos, l.liquidado_em FROM lancamentos l "
            "WHERE l.liquidado_em != '' AND substr(l.liquidado_em,1,7) = ? "
            "AND NOT EXISTS (SELECT 1 FROM comprovantes c WHERE c.lancamento_id = l.id)",
            (hoje.strftime("%Y-%m"),),
        )
        if sem_comprovante:
            avisos.append({
                "grau": "atencao",
                "titulo": (_quantos(len(sem_comprovante), "lançamento")
                           + " sem comprovante neste mês"),
                "detalhe": ", ".join(l["descricao"] for l in sem_comprovante[:3]),
                "acao": "anexar",
                "ids": [l["id"] for l in sem_comprovante],
            })

        return avisos

    def por_categoria(self, mes: str = "") -> list[dict]:
        mes = mes or date.today().strftime("%Y-%m")
        linhas = self.base.buscar(
            "SELECT categoria, tipo, SUM(centavos) AS total, COUNT(*) AS quantos "
            "FROM lancamentos WHERE liquidado_em != '' AND substr(liquidado_em,1,7) = ? "
            "GROUP BY categoria, tipo ORDER BY total DESC",
            (mes,),
        )
        for l in linhas:
            l["rotulo"] = CATEGORIAS.get(l["categoria"], "Outros")
            l["total_texto"] = em_reais(l["total"])
        return linhas

    def para_tela(self, mes: str = "") -> dict:
        mes = mes or date.today().strftime("%Y-%m")
        return {
            "painel": self.painel(mes),
            "fluxo": self.fluxo(),
            "precisa": self.precisa_de_voce(),
            "receber": self.listar(tipo="recebimento", situacao="aberto")[:12],
            "pagar": self.listar(tipo="despesa", situacao="aberto")[:12],
            "categorias": self.por_categoria(mes),
            "tipos": [{"valor": k, "rotulo": v} for k, v in TIPOS.items()],
            "opcoes_categoria": [{"valor": k, "rotulo": v} for k, v in CATEGORIAS.items()],
        }


# --------------------------------------------------------------- ajudas


_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
          "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
_MESES_CURTO = ["jan", "fev", "mar", "abr", "mai", "jun",
                "jul", "ago", "set", "out", "nov", "dez"]


def _mes_extenso(mes: str) -> str:
    try:
        ano, numero = mes.split("-")
        return f"{_MESES[int(numero) - 1]} de {ano}"
    except (ValueError, IndexError):
        return mes


def _quantos(n: int, palavra: str, muitos: str = "") -> str:
    """"1 cobrança", "3 cobranças" — nunca "3 cobrança(s)"."""
    return f"{n} {palavra if n == 1 else (muitos or palavra + 's')}"


def _dias(n: int) -> str:
    """"1 dia", "12 dias" — e nunca "12 dia(s)", que ninguém escreve."""
    return f"{n} dia" if n == 1 else f"{n} dias"


def _br(iso: str) -> str:
    if not iso or len(iso) < 10:
        return iso or ""
    a, m, d = iso[:10].split("-")
    return f"{d}/{m}/{a}"


def _dias_entre(de: str, ate: str) -> int:
    try:
        return (date.fromisoformat(ate[:10]) - date.fromisoformat(de[:10])).days
    except (ValueError, TypeError):
        return 0
