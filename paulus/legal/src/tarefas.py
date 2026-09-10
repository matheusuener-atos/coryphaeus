"""
PAULUS - Tarefas.

Lista do escritorio com prazo, lista, etapas e a origem de cada tarefa.

O filtro que importa e "Meu dia": o que vence hoje, o que ja passou e o que
foi marcado como importante. Uma lista que mostra tudo de uma vez nao ajuda a
decidir o que fazer agora, que e a unica pergunta que essa tela responde.
"""

from __future__ import annotations

from datetime import date, timedelta

CAMPOS = ("titulo", "lista", "importante", "prazo", "cadastro_id", "anotacao")


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
        sql += " ORDER BY (prazo = '') ASC, prazo ASC, importante DESC, id DESC"

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
        return tarefa

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
            "cadastro_id": dados.get("cadastro_id") or None,
            "anotacao": str(dados.get("anotacao", "")),
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

    def concluir(self, id_: int, feita: bool = True) -> None:
        self.base.escrever(
            "UPDATE tarefas SET concluida = ?, concluida_em = ? WHERE id = ?",
            (1 if feita else 0, hoje() if feita else "", id_),
        )

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
