"""
PAULUS - Agenda.

Compromissos, e a grade que junta tres coisas que ate agora viviam separadas:
compromisso marcado, prazo de tarefa e data que os contratos trazem.

E esse o ponto da tela. Ver so os compromissos e ter meia agenda: o que faz
perder prazo nao e a reuniao esquecida, e o vencimento que estava escrito num
contrato que ninguem reabriu.

A disponibilidade mora nas preferencias, nao aqui: e escolha da pessoa sobre o
proprio dia, e a mesma resposta serve para agendar, sugerir e recusar horario.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

# Compromisso e o que se agenda - reuniao, videoconferencia, audiencia -, com
# hora, duracao e lugar. O resto (prazo interno, pagamento, o do dia a dia) e
# tarefa, em src/tarefas.py: com prazo e, se quiser, hora.
TIPOS = {
    "compromisso": "Compromisso",
}

ONDES = {
    "online": "Reunião online",
    "escritorio": "No escritório",
    "telefone": "Telefone",
    "": "Sem local",
}

CAMPOS = (
    "titulo", "tipo", "data", "hora", "duracao", "onde",
    "cadastro_id", "anotacao", "avisar_min",
)

# Usado quando a pessoa ainda nao mexeu na disponibilidade.
DISPONIBILIDADE_PADRAO = {
    "dias": [0, 1, 2, 3, 4],          # segunda a sexta
    "inicio": "09:00",
    "fim": "18:00",
    "almoco_inicio": "12:00",
    "almoco_fim": "13:30",
    "intervalo_min": 15,
    "mesmo_dia": True,
}


def _hm(texto: str) -> time:
    try:
        h, m = texto.split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError):
        return time(0, 0)


def _minutos(t: time) -> int:
    return t.hour * 60 + t.minute


def _texto(minutos: int) -> str:
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


class Agenda:
    def __init__(self, base) -> None:
        self.base = base

    # --------------------------------------------------------- compromissos

    def listar(self, de: str, ate: str) -> list[dict]:
        itens = self.base.buscar(
            "SELECT c.*, k.nome AS cadastro_nome FROM compromissos c "
            "LEFT JOIN cadastros k ON k.id = c.cadastro_id "
            "WHERE c.data >= ? AND c.data <= ? ORDER BY c.data, c.hora",
            (de, ate),
        )
        for i in itens:
            i["tipo_rotulo"] = TIPOS.get(i["tipo"], i["tipo"])
            i["onde_rotulo"] = ONDES.get(i["onde"], i["onde"])
            i["fim"] = self._fim(i["hora"], i["duracao"])
        return itens

    @staticmethod
    def _fim(hora: str, duracao: int) -> str:
        return _texto(min(_minutos(_hm(hora)) + int(duracao or 0), 24 * 60 - 1))

    def obter(self, id_: int) -> dict | None:
        item = self.base.um(
            "SELECT c.*, k.nome AS cadastro_nome FROM compromissos c "
            "LEFT JOIN cadastros k ON k.id = c.cadastro_id WHERE c.id = ?",
            (id_,),
        )
        if item:
            item["tipo_rotulo"] = TIPOS.get(item["tipo"], item["tipo"])
            item["fim"] = self._fim(item["hora"], item["duracao"])
        return item

    def salvar(self, dados: dict, id_: int | None = None) -> int:
        titulo = " ".join(str(dados.get("titulo", "")).split())
        if not titulo:
            raise ValueError("o compromisso precisa de um titulo")
        if not str(dados.get("data", "")).strip():
            raise ValueError("o compromisso precisa de uma data")

        limpo = {
            "titulo": titulo,
            "tipo": "compromisso",
            "data": str(dados["data"])[:10],
            "hora": str(dados.get("hora", "09:00"))[:5],
            "duracao": int(dados.get("duracao") or 60),
            "onde": str(dados.get("onde", "")),
            "cadastro_id": dados.get("cadastro_id") or None,
            "anotacao": str(dados.get("anotacao", "")),
            "avisar_min": int(dados.get("avisar_min") or 0),
        }

        if id_:
            atribui = ", ".join(f"{c} = ?" for c in CAMPOS)
            self.base.escrever(
                f"UPDATE compromissos SET {atribui} WHERE id = ?",
                tuple(limpo[c] for c in CAMPOS) + (id_,),
            )
        else:
            colunas = ", ".join(CAMPOS)
            marcas = ", ".join("?" for _ in CAMPOS)
            id_ = self.base.escrever(
                f"INSERT INTO compromissos ({colunas}, criado_em) "
                f"VALUES ({marcas}, datetime('now','localtime'))",
                tuple(limpo[c] for c in CAMPOS),
            )

        # De onde veio e quem cuida: so mudam quando a ficha diz. A tela da
        # Agenda nao manda esses campos, e editar la nao desliga o compromisso
        # do servico que o marcou.
        for coluna in ("servico_id", "responsavel_id"):
            if coluna in dados:
                self.base.escrever(f"UPDATE compromissos SET {coluna} = ? WHERE id = ?",
                                   (int(dados[coluna]) if dados[coluna] else None, id_))
        return id_

    def apagar(self, id_: int) -> bool:
        return self.base.escrever("DELETE FROM compromissos WHERE id = ?", (id_,)) > 0

    # ---------------------------------------------------------- notas do dia

    def nota(self, dia: str) -> str:
        linha = self.base.um("SELECT texto FROM notas_dia WHERE dia = ?", (dia,))
        return linha["texto"] if linha else ""

    def gravar_nota(self, dia: str, texto: str) -> None:
        self.base.escrever(
            "INSERT INTO notas_dia (dia, texto, atualizado_em) "
            "VALUES (?, ?, datetime('now','localtime')) "
            "ON CONFLICT(dia) DO UPDATE SET texto = excluded.texto, "
            "atualizado_em = excluded.atualizado_em",
            (dia, texto),
        )

    # ------------------------------------------------------------- a grade

    def grade(self, de: str, ate: str, tarefas=None, documentos=None, pessoa: int | None = None) -> dict:
        """
        Tudo o que tem data no periodo, junto.

        Compromisso, prazo de tarefa e data de contrato entram na mesma grade
        porque e assim que o dia acontece - separados em telas diferentes, o
        prazo que estava so no contrato e o que se perde.

        `pessoa` e a agenda de alguem da equipe: so o que tem essa pessoa como
        responsavel (a etapa de servico atribuida a ela, o compromisso marcado
        para ela). Os documentos nao tem dono e ficam de fora.
        """
        por_dia: dict[str, list[dict]] = {}

        def por(dia: str) -> list[dict]:
            return por_dia.setdefault(dia, [])

        def dela(item: dict) -> bool:
            return not pessoa or item.get("responsavel_id") == pessoa

        for c in self.listar(de, ate):
            if not dela(c):
                continue
            por(c["data"]).append({
                "genero": "compromisso",
                "id": c["id"],
                "titulo": c["titulo"],
                "hora": c["hora"],
                "detalhe": c["cadastro_nome"] or c["tipo_rotulo"],
                "tipo": c["tipo"],
                "servico_id": c.get("servico_id"),
                "responsavel_id": c.get("responsavel_id"),
            })

        for t in (tarefas or []):
            if t.get("prazo") and de <= t["prazo"] <= ate and dela(t):
                por(t["prazo"]).append({
                    "genero": "prazo" if not t.get("concluida") else "tarefa",
                    "id": t["id"],
                    "titulo": t["titulo"],
                    "hora": t.get("hora") or "",
                    "detalhe": t.get("cadastro_nome") or t.get("lista") or "",
                    "tipo": "tarefa",
                    "servico_id": t.get("servico_id"),
                    "responsavel_id": t.get("responsavel_id"),
                })

        for d in ([] if pessoa else (documentos or [])):
            data = (d.get("data") or "")[:10]
            if data and de <= data <= ate:
                por(data).append({
                    "genero": "documento",
                    "id": d.get("sha1", ""),
                    "titulo": d.get("nome", "documento"),
                    "hora": "",
                    "detalhe": d.get("cliente") or d.get("tipo_rotulo") or "",
                    "tipo": "documento",
                })

        for dia in por_dia.values():
            dia.sort(key=lambda x: (x["hora"] == "", x["hora"]))

        return {
            "de": de,
            "ate": ate,
            "dias": por_dia,
            "contagem": {
                "compromissos": sum(1 for d in por_dia.values() for x in d if x["genero"] == "compromisso"),
                "prazos": sum(1 for d in por_dia.values() for x in d if x["genero"] == "prazo"),
                "documentos": sum(1 for d in por_dia.values() for x in d if x["genero"] == "documento"),
            },
        }

    # ------------------------------------------------------ horarios livres

    def livres(self, dia: str, duracao: int, disponibilidade: dict | None = None) -> list[str]:
        """
        Horarios em que cabe um compromisso desse tamanho.

        Respeita a janela de trabalho, o almoco, o intervalo entre
        compromissos e o que ja esta marcado. Sugerir horario que colide com o
        almoco da pessoa e o tipo de ajuda que ninguem pede duas vezes.
        """
        regra = {**DISPONIBILIDADE_PADRAO, **(disponibilidade or {})}

        try:
            quando = date.fromisoformat(dia)
        except ValueError:
            return []
        if quando.weekday() not in regra["dias"]:
            return []

        inicio = _minutos(_hm(regra["inicio"]))
        fim = _minutos(_hm(regra["fim"]))
        folga = int(regra["intervalo_min"])
        duracao = max(int(duracao or 30), 5)

        ocupado = [
            (_minutos(_hm(regra["almoco_inicio"])), _minutos(_hm(regra["almoco_fim"])))
        ]
        for c in self.listar(dia, dia):
            comeca = _minutos(_hm(c["hora"]))
            ocupado.append((comeca - folga, comeca + int(c["duracao"] or 0) + folga))

        # Hoje, nao adianta oferecer horario que ja passou.
        if quando == date.today():
            agora = datetime.now()
            inicio = max(inicio, _minutos(time(agora.hour, agora.minute)))

        livres: list[str] = []
        passo = 30
        atual = ((inicio + passo - 1) // passo) * passo
        while atual + duracao <= fim:
            conflito = any(atual < f and comeca < atual + duracao for comeca, f in ocupado)
            if not conflito:
                livres.append(_texto(atual))
            atual += passo

        return livres

    def proximos_livres(self, duracao: int, disponibilidade: dict | None = None,
                        dias: int = 10, quantos: int = 6) -> list[dict]:
        """Primeiros horarios livres a partir de hoje, para a tela sugerir."""
        regra = {**DISPONIBILIDADE_PADRAO, **(disponibilidade or {})}
        saida: list[dict] = []
        inicio = date.today() if regra.get("mesmo_dia", True) else date.today() + timedelta(days=1)

        for salto in range(dias):
            dia = (inicio + timedelta(days=salto)).isoformat()
            for hora in self.livres(dia, duracao, regra)[:3]:
                saida.append({"data": dia, "hora": hora})
                if len(saida) >= quantos:
                    return saida
        return saida
