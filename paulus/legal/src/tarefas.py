"""
PAULUS - Tarefas.

Lista do escritorio com prazo, lista, etapas e a origem de cada tarefa.

O filtro que importa e "Meu dia": o que vence hoje, o que ja passou e o que
foi marcado como importante. Uma lista que mostra tudo de uma vez nao ajuda a
decidir o que fazer agora, que e a unica pergunta que essa tela responde.
"""

from __future__ import annotations

from datetime import date, timedelta

CAMPOS = ("titulo", "lista", "importante", "prazo", "hora", "cadastro_id", "anotacao",
          "lembrar_em", "repetir")

# Repetir e comportamento, nao rotulo: concluir uma tarefa que repete cria a
# proxima com o prazo andado. Sem isso, "semanal" seria so uma palavra na ficha.
REPETICOES = {
    "": "Não repete",
    "diaria": "Todo dia",
    "semanal": "Toda semana",
    "quinzenal": "A cada 15 dias",
    "mensal": "Todo mês",
}
PASSO_DIAS = {"diaria": 1, "semanal": 7, "quinzenal": 15}


def _andar(prazo: str, repetir: str) -> str:
    """A proxima data, a partir do prazo que a tarefa tinha."""
    from datetime import date, timedelta

    try:
        base = date.fromisoformat(prazo[:10])
    except (ValueError, TypeError):
        base = date.today()

    if repetir == "mensal":
        mes = base.month + 1
        ano = base.year + (1 if mes > 12 else 0)
        mes = 1 if mes > 12 else mes
        dia = min(base.day, [31, 29 if ano % 4 == 0 and (ano % 100 or ano % 400 == 0) else 28,
                             31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mes - 1])
        return date(ano, mes, dia).isoformat()
    return (base + timedelta(days=PASSO_DIAS.get(repetir, 7))).isoformat()


def _hora_ou_nada(valor) -> str:
    """HH:MM valida, ou vazio - hora que nao existe nao vira hora."""
    import re

    achado = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", str(valor or ""))
    if not achado or int(achado.group(1)) > 23 or int(achado.group(2)) > 59:
        return ""
    return f"{int(achado.group(1)):02d}:{achado.group(2)}"


def hoje() -> str:
    return date.today().isoformat()


class Tarefas:
    def __init__(self, base) -> None:
        self.base = base

    # ---------------------------------------------------------------- leitura

    def listar(self, filtro: str = "meu_dia", lista: str = "") -> list[dict]:
        onde, parametros = [], []

        if filtro == "meu_dia":
            # O que a pessoa escolheu para hoje, mais o que venceu ou vence hoje:
            # prazo que passou nao deixa de ser de hoje so porque ninguem marcou.
            onde.append("concluida = 0 AND (meu_dia = 1 OR (prazo != '' AND prazo <= ?))")
            parametros.append(hoje())
        elif filtro == "importante":
            onde.append("concluida = 0 AND importante = 1")
        elif filtro == "planejadas":
            onde.append("concluida = 0 AND prazo != '' AND prazo > ?")
            parametros.append(hoje())
        elif filtro == "concluidas":
            onde.append("concluida = 1")
        else:
            onde.append("concluida = 0")

        if lista:
            onde.append("lista = ?")
            parametros.append(lista)

        sql = (
            "SELECT t.*, c.nome AS cadastro_nome FROM tarefas t "
            "LEFT JOIN cadastros c ON c.id = t.cadastro_id"
        )
        if onde:
            sql += " WHERE " + " AND ".join(onde)
        sql += " ORDER BY (prazo = '') ASC, prazo ASC, (hora = '') ASC, hora ASC, importante DESC, id DESC"

        tarefas = self.base.buscar(sql, tuple(parametros))
        for t in tarefas:
            t["etapas"] = self.etapas_de(t["id"])
            t["situacao"] = self._situacao(t)
        return tarefas

    @staticmethod
    def _situacao(tarefa: dict) -> str:
        """Como o prazo aparece na tela, em portugues."""
        if tarefa["concluida"]:
            return "concluída"
        prazo = tarefa["prazo"]
        if not prazo:
            return "sem prazo"

        try:
            dias = (date.fromisoformat(prazo) - date.today()).days
        except ValueError:
            return "sem prazo"

        if dias < 0:
            return f"atrasada {abs(dias)} dia(s)"
        if dias == 0:
            return "hoje"
        if dias == 1:
            return "amanhã"
        return f"em {dias} dias"

    def contagens(self) -> dict:
        h = hoje()
        return {
            "meu_dia": self.base.contar(
                "tarefas", "concluida = 0 AND (meu_dia = 1 OR (prazo != '' AND prazo <= ?))", (h,)
            ),
            "importante": self.base.contar("tarefas", "concluida = 0 AND importante = 1"),
            "planejadas": self.base.contar("tarefas", "concluida = 0 AND prazo != '' AND prazo > ?", (h,)),
            "concluidas": self.base.contar("tarefas", "concluida = 1"),
            "abertas": self.base.contar("tarefas", "concluida = 0"),
        }

    def listas(self) -> list[dict]:
        return self.base.buscar(
            "SELECT lista AS nome, COUNT(*) AS abertas FROM tarefas "
            "WHERE concluida = 0 AND lista != '' GROUP BY lista ORDER BY lista COLLATE NOCASE"
        )

    def obter(self, id_: int) -> dict | None:
        tarefa = self.base.um(
            "SELECT t.*, c.nome AS cadastro_nome FROM tarefas t "
            "LEFT JOIN cadastros c ON c.id = t.cadastro_id WHERE t.id = ?",
            (id_,),
        )
        if tarefa:
            tarefa["etapas"] = self.etapas_de(id_)
            tarefa["situacao"] = self._situacao(tarefa)
            tarefa["vinculos"] = self.vinculos_de(id_)
        return tarefa

    def vinculos_de(self, id_: int) -> list[dict]:
        """Os documentos ligados a esta tarefa, pelo SHA-1 do conteudo."""
        return self.base.buscar(
            "SELECT id, sha1, nome, criado_em FROM vinculos "
            "WHERE tipo = 'tarefa' AND alvo_id = ? ORDER BY id",
            (id_,),
        )

    def vincular(self, id_: int, sha1: str, nome: str = "") -> None:
        """
        Liga um documento a tarefa.

        Pelo SHA-1, como os outros vinculos: renomear ou mover o arquivo nao
        quebra a ligacao, porque o que identifica e o conteudo.
        """
        self.base.escrever(
            "INSERT OR IGNORE INTO vinculos (tipo, alvo_id, sha1, nome, criado_em) "
            "VALUES ('tarefa', ?, ?, ?, datetime('now','localtime'))",
            (id_, sha1, nome),
        )

    def desvincular(self, vinculo_id: int) -> bool:
        return self.base.escrever("DELETE FROM vinculos WHERE id = ?", (vinculo_id,)) > 0

    # ---------------------------------------------------------------- escrita

    def salvar(self, dados: dict, id_: int | None = None) -> int:
        titulo = " ".join(str(dados.get("titulo", "")).split())
        if not titulo:
            raise ValueError("a tarefa precisa de um titulo")

        limpo = {
            "titulo": titulo,
            "lista": str(dados.get("lista", "")).strip(),
            "importante": 1 if dados.get("importante") else 0,
            "prazo": str(dados.get("prazo", "")).strip()[:10],
            # A hora e opcional: tarefa e do dia a dia; com hora, entra na
            # lista do dia na ordem dela, junto dos compromissos.
            "hora": _hora_ou_nada(dados.get("hora", "")),
            "cadastro_id": dados.get("cadastro_id") or None,
            "anotacao": str(dados.get("anotacao", "")),
            "lembrar_em": str(dados.get("lembrar_em", "")).strip()[:5],
            "repetir": dados.get("repetir") if dados.get("repetir") in REPETICOES else "",
        }

        if id_:
            atribui = ", ".join(f"{c} = ?" for c in CAMPOS)
            self.base.escrever(
                f"UPDATE tarefas SET {atribui} WHERE id = ?",
                tuple(limpo[c] for c in CAMPOS) + (id_,),
            )
            return id_

        colunas = ", ".join(CAMPOS)
        marcas = ", ".join("?" for _ in CAMPOS)
        return self.base.escrever(
            f"INSERT INTO tarefas ({colunas}, criada_em) "
            f"VALUES ({marcas}, datetime('now','localtime'))",
            tuple(limpo[c] for c in CAMPOS),
        )

    def concluir(self, id_: int, feita: bool = True) -> dict:
        """
        Marca como feita e, se a tarefa repete, ja deixa a proxima no lugar.

        Criar a proxima na hora de concluir e o unico momento em que da para
        saber que ela deve existir. Deixar para um relogio depois exigiria um
        processo rodando, e o programa fecha junto com a janela.
        """
        self.base.escrever(
            "UPDATE tarefas SET concluida = ?, concluida_em = ? WHERE id = ?",
            (1 if feita else 0, hoje() if feita else "", id_),
        )
        if not feita:
            return {"proxima": None}
        return {"proxima": self._repetir(id_)}

    def _repetir(self, id_: int) -> int | None:
        atual = self.base.um("SELECT * FROM tarefas WHERE id = ?", (id_,))
        if not atual or not atual["repetir"]:
            return None

        dados = {c: atual[c] for c in CAMPOS}
        dados["prazo"] = _andar(atual["prazo"] or hoje(), atual["repetir"])
        novo = self.salvar(dados)
        self.base.escrever("UPDATE tarefas SET meu_dia = 0 WHERE id = ?", (novo,))
        return novo

    def marcar_importante(self, id_: int, importante: bool) -> None:
        self.base.escrever("UPDATE tarefas SET importante = ? WHERE id = ?", (1 if importante else 0, id_))

    def marcar_meu_dia(self, id_: int, no_dia: bool) -> None:
        self.base.escrever("UPDATE tarefas SET meu_dia = ? WHERE id = ?", (1 if no_dia else 0, id_))

    def apagar(self, id_: int) -> bool:
        self.base.escrever("DELETE FROM vinculos WHERE tipo = 'tarefa' AND alvo_id = ?", (id_,))
        return self.base.escrever("DELETE FROM tarefas WHERE id = ?", (id_,)) > 0

    # ----------------------------------------------------------------- etapas

    def etapas_de(self, tarefa_id: int) -> list[dict]:
        return self.base.buscar(
            "SELECT * FROM etapas WHERE tarefa_id = ? ORDER BY ordem, id", (tarefa_id,)
        )

    def nova_etapa(self, tarefa_id: int, titulo: str) -> int:
        titulo = " ".join(titulo.split())
        if not titulo:
            raise ValueError("a etapa precisa de um titulo")
        ordem = self.base.contar("etapas", "tarefa_id = ?", (tarefa_id,))
        return self.base.escrever(
            "INSERT INTO etapas (tarefa_id, titulo, ordem) VALUES (?, ?, ?)",
            (tarefa_id, titulo, ordem),
        )

    def marcar_etapa(self, etapa_id: int, feita: bool) -> None:
        self.base.escrever("UPDATE etapas SET feita = ? WHERE id = ?", (1 if feita else 0, etapa_id))

    def apagar_etapa(self, etapa_id: int) -> bool:
        return self.base.escrever("DELETE FROM etapas WHERE id = ?", (etapa_id,)) > 0

    # -------------------------------------------------------------- sugestoes

    def sugerir(self, classificados: list[dict], dias: int = 90) -> list[dict]:
        """
        Tarefas que os proprios documentos pedem.

        So data futura vira sugestao. A classificacao extrai a data de
        assinatura, e assinatura de 2021 nao e prazo a conferir - sugerir isso
        enche a lista de ruido e ensina a pessoa a ignorar a sugestao.

        Nao cria nada: devolve para a pessoa aceitar ou ignorar. Inventar tarefa
        na lista de alguem e pior do que nao sugerir.
        """
        hoje_ = date.today()
        limite = hoje_ + timedelta(days=dias)
        ja = {
            _normalizar(t["titulo"])
            for t in self.base.buscar("SELECT titulo FROM tarefas")
        }

        saida: list[dict] = []
        for doc in classificados:
            data = (doc.get("data") or "")[:10]
            if not data:
                continue
            try:
                quando = date.fromisoformat(data)
            except ValueError:
                continue
            if quando < hoje_ or quando > limite:
                continue

            cliente = doc.get("cliente") or ""
            titulo = f"Conferir prazo — {doc.get('nome', 'documento')}"
            if _normalizar(titulo) in ja:
                continue

            saida.append({
                "titulo": titulo,
                "prazo": data,
                "lista": doc.get("tipo_rotulo", ""),
                "cliente": cliente,
                "sha1": doc.get("sha1", ""),
                "arquivo": doc.get("nome", ""),
            })

        return sorted(saida, key=lambda x: x["prazo"])[:20]


def _normalizar(texto: str) -> str:
    return " ".join((texto or "").lower().split())
