"""
PAULUS - Relatorios.

O que aconteceu no escritorio, somado do que ja esta gravado: tarefas
concluidas, lancamentos liquidados, documentos assinados, e-mails enviados,
pedidos aprovados na fila, versoes de documento gravadas.

Nada aqui gera dado novo. Este modulo le o que as outras etapas produziram e
junta - e por isso ele so podia existir depois delas. O plano dizia isso desde
o comeco: relatorio antes de haver historico mostra grafico vazio ou, pior,
numero inventado.

Quando uma medida nao existe, o relatorio diz que nao existe. "Tempo no
escritorio" so aparece se o acompanhamento de bem-estar estiver ligado; sem
ele, a linha some em vez de virar estimativa. Uma media calculada sobre um dia
de dado nao e uma media - e um numero com cara de media, que e pior.

O parecer em texto e a unica parte que passa pelo modelo, e sempre depois: ele
recebe os numeros ja apurados e escreve sobre eles. Nunca calcula.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import financeiro as fin

TIPOS_RELATORIO = {
    "dia": "Hoje",
    "semana": "Esta semana",
    "mes": "Este mês",
}


def _br(iso: str) -> str:
    if not iso or len(iso) < 10:
        return iso or ""
    a, m, d = iso[:10].split("-")
    return f"{d}/{m}/{a}"


_DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
         "sexta-feira", "sábado", "domingo"]


class Relatorios:
    """
    Junta o que as outras telas produziram.

    Recebe as fontes por parametro em vez de importar o estado do servidor:
    assim da para testar cada numero com dado controlado, e fica visivel de
    onde cada linha do relatorio veio.
    """

    def __init__(self, base, *, fila=None, assinaturas=None, envios=None, bem_estar=None) -> None:
        self.base = base
        self.fila = fila
        self.assinaturas = assinaturas
        self.envios = envios
        self.bem_estar = bem_estar
        self.financeiro = fin.Financeiro(base)

    # ------------------------------------------------------------- o dia

    def dia(self, quando: str = "") -> dict:
        alvo = quando or date.today().isoformat()
        quandodata = date.fromisoformat(alvo)

        feitas = self.base.buscar(
            "SELECT t.id, t.titulo, t.concluida_em, t.prazo, k.nome AS cadastro_nome "
            "FROM tarefas t LEFT JOIN cadastros k ON k.id = t.cadastro_id "
            "WHERE t.concluida = 1 AND substr(t.concluida_em,1,10) = ? "
            "ORDER BY t.concluida_em",
            (alvo,),
        )
        for t in feitas:
            t["hora"] = (t["concluida_em"] or "")[11:16]

        # "Planejado" e o que estava no Meu dia ou vencia hoje - nao a lista
        # inteira do escritorio, que nunca esteve planejada para um dia so.
        abertas = self.base.buscar(
            "SELECT t.id, t.titulo, t.prazo, k.nome AS cadastro_nome "
            "FROM tarefas t LEFT JOIN cadastros k ON k.id = t.cadastro_id "
            "WHERE t.concluida = 0 AND (t.meu_dia = 1 OR (t.prazo != '' AND t.prazo <= ?)) "
            "ORDER BY t.prazo",
            (alvo,),
        )
        for t in abertas:
            t["quando"] = _br(t["prazo"]) if t["prazo"] else "sem prazo"

        planejado = len(feitas) + len(abertas)

        assinados = self._assinaturas_do_dia(alvo)
        enviados = self._envios_do_dia(alvo)
        versoes = self.base.um(
            "SELECT COUNT(*) AS n FROM versoes WHERE substr(criada_em,1,10) = ?", (alvo,)
        )
        compromissos = self.base.um(
            "SELECT COUNT(*) AS n FROM compromissos WHERE data = ?", (alvo,)
        )

        medido = {}
        if self.bem_estar:
            hoje_be = self.bem_estar.dia(alvo)
            if hoje_be["minutos_ativos"]:
                medido["tempo_ativo"] = hoje_be["ativo_texto"]
                medido["ciclos"] = hoje_be["ciclos"]
                medido["pausas"] = hoje_be["pausas"]

        return {
            "dia": alvo,
            "rotulo": f"{_DIAS[quandodata.weekday()]}, {_br(alvo)}",
            "tarefas": {
                "feitas": feitas,
                "abertas": abertas,
                "planejado": planejado,
                "percentual": round(len(feitas) * 100 / planejado) if planejado else 0,
            },
            "assinaturas": assinados,
            "emails": enviados,
            "versoes": int(versoes["n"]) if versoes else 0,
            "compromissos": int(compromissos["n"]) if compromissos else 0,
            "acoes": self.acoes(alvo),
            "medido": medido,
            "sem_medicao": not medido,
        }

    def _assinaturas_do_dia(self, alvo: str) -> list[dict]:
        if not self.assinaturas:
            return []
        return [
            {"documento": a.get("documento", ""), "hora": (a.get("quando") or "")[11:16],
             "icp_brasil": a.get("icp_brasil", False)}
            for a in self.assinaturas.itens
            if (a.get("quando") or "").startswith(alvo)
        ]

    def _envios_do_dia(self, alvo: str) -> list[dict]:
        if not self.envios:
            return []
        return [
            {"assunto": e.get("assunto", ""), "para": e.get("para", []),
             "hora": (e.get("quando") or "")[11:16]}
            for e in self.envios.itens
            if (e.get("quando") or "").startswith(alvo)
        ]

    # -------------------------------------------------- acoes aprovadas

    def acoes(self, dia: str = "", limite: int = 20) -> list[dict]:
        """
        O que o assistente fez com o seu sim.

        Sai da fila de aprovacoes: cada linha aqui e um pedido que existiu, foi
        decidido e guardou o resultado. E o registro que torna a fila
        verificavel depois - sem ele, "aprovei alguma coisa ontem" nao tem onde
        ser conferido.
        """
        if not self.fila:
            return []

        saida = []
        for p in sorted(self.fila._itens.values(), key=lambda x: x.decidido_em, reverse=True):
            if p.estado == "pendente" or not p.decidido_em:
                continue
            if dia and not p.decidido_em.startswith(dia):
                continue
            saida.append({
                "id": p.id,
                "titulo": p.titulo,
                "categoria": p.categoria,
                "categoria_rotulo": p.categoria_rotulo,
                "estado": p.estado,
                "quando": p.decidido_em,
                "hora": p.decidido_em[11:16],
                "dia": p.decidido_em[:10],
                "resultado": p.resultado,
                "reversivel": p.reversivel,
            })
            if len(saida) >= limite:
                break
        return saida

    # ------------------------------------------------------------- o mes

    def mes(self, chave: str = "") -> dict:
        chave = chave or date.today().strftime("%Y-%m")
        extrato = self.financeiro.extrato(chave)

        anterior = _mes_antes(chave)
        entradas = self._soma_mes(chave, "recebimento")
        saidas = self._soma_mes(chave, "despesa")
        entradas_antes = self._soma_mes(anterior, "recebimento")
        saidas_antes = self._soma_mes(anterior, "despesa")

        sem_comprovante = self.base.um(
            "SELECT COUNT(*) AS n FROM lancamentos l WHERE l.liquidado_em != '' "
            "AND substr(l.liquidado_em,1,7) = ? "
            "AND NOT EXISTS (SELECT 1 FROM comprovantes c WHERE c.lancamento_id = l.id)",
            (chave,),
        )

        tarefas = self.base.um(
            "SELECT COUNT(*) AS n FROM tarefas WHERE concluida = 1 AND substr(concluida_em,1,7) = ?",
            (chave,),
        )

        return {
            "mes": chave,
            "rotulo": fin._mes_extenso(chave),
            "extrato": extrato,
            "entradas": entradas,
            "entradas_texto": fin.curto(entradas),
            "saidas": saidas,
            "saidas_texto": fin.curto(saidas),
            "comparacao": {
                "entradas": _variacao(entradas_antes, entradas),
                "saidas": _variacao(saidas_antes, saidas),
                "tem_base": bool(entradas_antes or saidas_antes),
                "mes_anterior": fin._mes_extenso(anterior),
            },
            "sem_comprovante": int(sem_comprovante["n"]) if sem_comprovante else 0,
            "prazo_medio": self._prazo_medio(chave),
            "tarefas_concluidas": int(tarefas["n"]) if tarefas else 0,
            "acoes": [a for a in self.acoes(limite=200) if a["dia"].startswith(chave)],
        }

    def _soma_mes(self, chave: str, tipo: str) -> int:
        linha = self.base.um(
            "SELECT COALESCE(SUM(centavos),0) AS s FROM lancamentos "
            "WHERE tipo = ? AND liquidado_em != '' AND substr(liquidado_em,1,7) = ?",
            (tipo, chave),
        )
        return int(linha["s"]) if linha else 0

    def _prazo_medio(self, chave: str) -> dict:
        """
        Quantos dias, em media, entre o vencimento e o recebimento.

        Com menos de tres recebimentos no mes nao devolve media: media de dois
        numeros nao descreve habito nenhum, e mostrar "prazo medio: 14 dias"
        apoiado em duas linhas e inventar precisao.
        """
        linhas = self.base.buscar(
            "SELECT vencimento, liquidado_em FROM lancamentos "
            "WHERE tipo = 'recebimento' AND liquidado_em != '' AND vencimento != '' "
            "AND substr(liquidado_em,1,7) = ?",
            (chave,),
        )
        dias = []
        for l in linhas:
            try:
                dias.append(
                    (date.fromisoformat(l["liquidado_em"][:10])
                     - date.fromisoformat(l["vencimento"][:10])).days
                )
            except ValueError:
                continue

        if len(dias) < 3:
            return {"tem": False, "quantos": len(dias),
                    "porque": "preciso de pelo menos três recebimentos no mês para uma média que signifique algo"}
        return {"tem": True, "quantos": len(dias), "dias": round(sum(dias) / len(dias), 1)}

    # ------------------------------------------------------------ resumo

    def para_tela(self, quando: str = "") -> dict:
        alvo = quando or date.today().isoformat()
        do_dia = self.dia(alvo)
        do_mes = self.mes(alvo[:7])

        return {
            "dia": do_dia,
            "mes": do_mes,
            "semana": self.bem_estar.semana(alvo) if self.bem_estar else None,
            "vazio": self._esta_vazio(do_dia, do_mes),
            "periodos": [{"valor": k, "rotulo": v} for k, v in TIPOS_RELATORIO.items()],
        }

    @staticmethod
    def _esta_vazio(do_dia: dict, do_mes: dict) -> bool:
        return not any([
            do_dia["tarefas"]["planejado"], do_dia["assinaturas"], do_dia["emails"],
            do_dia["acoes"], do_dia["versoes"], do_mes["extrato"]["linhas"],
        ])

    def numeros_para_o_parecer(self, quando: str = "") -> str:
        """
        Os numeros ja apurados, em texto, para o modelo escrever sobre eles.

        O modelo recebe conta feita. Se ele calculasse, um erro de aritmetica
        de um modelo de 3 bilhoes de parametros viraria numero errado num
        parecer financeiro - e parecer com numero errado e pior que nenhum.
        """
        do_dia = self.dia(quando)
        do_mes = self.mes((quando or date.today().isoformat())[:7])
        t = do_dia["tarefas"]

        linhas = [
            f"Dia: {do_dia['rotulo']}",
            f"Tarefas concluídas: {len(t['feitas'])} de {t['planejado']} planejadas.",
        ]
        if t["feitas"]:
            linhas.append("Concluídas: " + "; ".join(
                f"{x['titulo']} às {x['hora']}" for x in t["feitas"][:6]))
        if t["abertas"]:
            linhas.append("Ficaram abertas: " + "; ".join(
                f"{x['titulo']} ({x['quando']})" for x in t["abertas"][:6]))

        if do_dia["medido"]:
            linhas.append(f"Tempo ativo no computador: {do_dia['medido']['tempo_ativo']}, "
                          f"{do_dia['medido']['pausas']} pausa(s).")
        if do_dia["assinaturas"]:
            linhas.append(f"Documentos assinados hoje: {len(do_dia['assinaturas'])}.")
        if do_dia["emails"]:
            linhas.append(f"E-mails enviados hoje: {len(do_dia['emails'])}.")
        if do_dia["acoes"]:
            linhas.append("Ações aprovadas hoje: " + "; ".join(
                a["titulo"] for a in do_dia["acoes"][:5]))

        linhas.append(
            f"No mês: entradas {do_mes['entradas_texto']}, saídas {do_mes['saidas_texto']}, "
            f"resultado {do_mes['extrato']['resultado_texto']}, "
            f"saldo em caixa {do_mes['extrato']['saldo_final_texto']}."
        )
        painel = self.financeiro.painel(do_mes["mes"])
        if painel["atrasado_quantos"]:
            linhas.append(
                f"Em atraso: {painel['atrasado_quantos']} cobrança(s), {painel['atrasado_texto']}."
            )
        if do_mes["sem_comprovante"]:
            linhas.append(f"Lançamentos sem comprovante no mês: {do_mes['sem_comprovante']}.")

        return "\n".join(linhas)


INSTRUCAO_PARECER = """Voce e assistente de um advogado brasileiro. Escreva um
parecer curto sobre o dia dele, em portugues do Brasil.

Regras, e elas valem mais que o estilo:
- use SOMENTE os numeros que estao abaixo; nao calcule nada por conta propria
- nao invente numero, nome, data nem valor que nao esteja na lista
- se um dado nao esta na lista, nao mencione o assunto
- dois paragrafos curtos: o que aconteceu, e uma sugestao pratica para amanha
- sem marcacao, sem asteriscos, sem titulo, sem saudacao"""


def _mes_antes(chave: str) -> str:
    ano, mes = (int(x) for x in chave.split("-"))
    return f"{ano - 1}-12" if mes == 1 else f"{ano}-{mes - 1:02d}"


def _variacao(antes: int, agora: int) -> dict:
    if not antes:
        return {"tem": False}
    variacao = (agora - antes) * 100 / antes
    return {
        "tem": True,
        "percentual": round(variacao),
        "texto": ("+" if variacao >= 0 else "") + f"{round(variacao)}%",
        "subiu": variacao >= 0,
    }
