"""
PAULUS - A saudacao da tela inicial (T1), sem modelo.

Antes (30/09/2026) eram cinco titulos fixos escolhidos pelo relogio, e quem
abria o programa de terca a quinta, de dia, via sempre "Ola. Por onde
comecamos?". Agora ha um banco de frases (config/saudacoes.json, mais de 120
titulos e 80 subtitulos), cada uma com as condicoes em que vale - o momento
do dia, o dia da semana, o calendario (inicio e fim de mes, vespera e dia
seguinte de feriado nacional, recesso forense, inicio do ano, aniversario do
escritorio), como a pessoa chegou (primeira abertura do dia, volta rapida,
volta depois de dias) e a situacao (prazo hoje, muita pendencia, acervo
vazio, conversa pela metade, tudo em dia).

A escolha e por regra, instantanea: filtra as frases que servem; a situacao
vence o calendario, o calendario vence o dia e o momento; as 20 ultimas
mostradas nesta maquina (a tela manda a lista) nao voltam enquanto houver
outra que sirva; entre as que sobram, sorteia. Uma situacao forte (prazo
hoje, acervo vazio) nunca cede a vez a uma frase de sexta-feira.

Feriados e recesso: src/prazos.py (a mesma tabela dos prazos, com os moveis
calculados pela Pascoa).

Chave: `conversa.saudacao`.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import prazos
from fastapi import Request

BANCO = Path(__file__).resolve().parent.parent / "config" / "saudacoes.json"
RECENTES = 20
LIMITE_TITULO = 90
# A partir de quantas pendencias o dia e "cheio".
MUITA_PENDENCIA = 8
# "De volta" depois de pouco tempo: a ultima conversa aberta ha menos de 3 h.
VOLTA_RAPIDA_H = 3
VOLTA_DIAS = 3

# A ordem de forca das condicoes. A situacao forte fica sozinha; as outras
# cedem a vez quando todas as frases delas ja foram mostradas ha pouco.
FORTES = {"prazo_hoje", "prazos_hoje", "acervo_vazio", "muita_pendencia"}
CAMADAS = ("situacao", "chegada", "calendario", "dia", "momento")
RE_MARCA = re.compile(r"\{(\w+)\}")


def momento_de(h: int) -> str:
    if h < 5:
        return "madrugada"
    if h < 8:
        return "manha_cedo"
    if h < 12:
        return "manha"
    if h < 14:
        return "almoco"
    if h < 17:
        return "tarde"
    if h < 19:
        return "fim_de_tarde"
    if h < 22:
        return "noite"
    return "noite_alta"


def dia_de(d: date) -> str:
    return {0: "segunda", 4: "sexta", 5: "sabado", 6: "domingo"}.get(d.weekday(), "meio_semana")


def _nome_do_feriado(nome: str) -> str:
    # "Carnaval (segunda)" vira "Carnaval" na frase.
    return re.sub(r"\s*\(.*\)$", "", nome)


def calendario_de(d: date, fundacao: str = "") -> tuple[set[str], str]:
    """As condicoes de calendario do dia e o nome do feriado que vale (hoje, amanha ou ontem)."""
    conds: set[str] = set()
    feriado = ""

    def f(x: date) -> str:
        return prazos.feriados(x.year).get(x, "")

    hoje, amanha, ontem = f(d), f(d + timedelta(days=1)), f(d - timedelta(days=1))
    if hoje:
        conds.add("feriado")
        feriado = _nome_do_feriado(hoje)
    elif amanha:
        conds.add("vespera_feriado")
        feriado = _nome_do_feriado(amanha)
    elif ontem:
        conds.add("pos_feriado")
        feriado = _nome_do_feriado(ontem)
    if d.day <= 3:
        conds.add("inicio_mes")
    if (d + timedelta(days=3)).month != d.month:
        conds.add("fim_mes")
    if prazos.em_recesso(d):
        conds.add("recesso")
    if d.month == 1 and 2 <= d.day <= 15:
        conds.add("inicio_ano")
    if fundacao and fundacao[5:10] == d.isoformat()[5:10]:
        conds.add("aniversario_escritorio")
    return conds, feriado


@dataclass
class Contexto:
    """O que a escolha precisa saber. `agora` e injetavel (relogio simulado nos testes)."""

    agora: datetime
    nome: str = ""
    documentos: int = 0
    prazos_hoje: list[str] = field(default_factory=list)
    pendencias: int = 0
    pela_metade: list[dict] = field(default_factory=list)   # [{id, titulo}]
    ultima_abertura: datetime | None = None
    ultima_conversa: dict | None = None                    # {id, titulo, aberta_em: datetime}
    fundacao: str = ""                                      # AAAA-MM-DD, das preferencias

    def condicoes(self) -> dict[str, set[str]]:
        d = self.agora.date()
        cal, self._feriado = calendario_de(d, self.fundacao)
        chegada: set[str] = set()
        if self.ultima_abertura is None or self.ultima_abertura.date() != d:
            chegada.add("primeira_do_dia")
        if self.ultima_abertura is not None and (d - self.ultima_abertura.date()).days >= VOLTA_DIAS:
            chegada.add("volta_dias")
        c = self.ultima_conversa or {}
        if c.get("titulo") and c.get("aberta_em") and self.agora - c["aberta_em"] < timedelta(hours=VOLTA_RAPIDA_H):
            chegada.add("volta_rapida")
        situacao: set[str] = set()
        if self.documentos == 0:
            situacao.add("acervo_vazio")
        if len(self.prazos_hoje) == 1:
            situacao.add("prazo_hoje")
        elif len(self.prazos_hoje) > 1:
            situacao.add("prazos_hoje")
        if self.pendencias >= MUITA_PENDENCIA:
            situacao.add("muita_pendencia")
        if self.pela_metade:
            situacao.add("conversa_pela_metade")
        if not situacao and self.pendencias == 0:
            situacao.add("tudo_em_dia")
        return {"momento": {momento_de(self.agora.hour)}, "dia": {dia_de(d)}, "calendario": cal,
                "chegada": chegada, "situacao": situacao}

    def marcas(self) -> dict[str, str]:
        def curto(s: str, n: int = 40) -> str:
            s = str(s or "").strip()
            return s if len(s) <= n else s[: n - 1].rstrip() + "…"

        conversa = (self.pela_metade[0]["titulo"] if self.pela_metade else "") or (self.ultima_conversa or {}).get("titulo", "")
        return {
            "nome": (self.nome or "").split()[0] if self.nome else "",
            "conversa": "“" + curto(conversa) + "”" if conversa else "",
            "feriado": getattr(self, "_feriado", ""),
            "prazo": curto(self.prazos_hoje[0]) if self.prazos_hoje else "",
            "n_prazos": str(len(self.prazos_hoje)),
            "pendencias": str(self.pendencias),
        }


def carregar(caminho: Path = BANCO) -> dict:
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def serve(frase: dict, conds: dict[str, set[str]], marcas: dict[str, str]) -> bool:
    for camada in CAMADAS:
        pede = frase.get(camada)
        if pede and not (set(pede) & conds[camada]):
            return False
    return all(marcas.get(m) for m in RE_MARCA.findall(frase["texto"]))


def preencher(texto: str, marcas: dict[str, str]) -> str:
    return RE_MARCA.sub(lambda m: marcas.get(m.group(1), ""), texto)


def _camada(frase: dict) -> float:
    """
    Quanto mais especifica, mais forte: situacao 5, chegada 4, calendario 3,
    dia 2, momento 1, geral 0. "Tudo em dia" e situacao fraca (1,5): se
    vencesse o calendario, o Natal diria "Tudo em dia por aqui".
    """
    if set(frase.get("situacao") or []) == {"tudo_em_dia"}:
        return 1.5
    # Madrugada e noite alta dizem mais que o dia da semana: as 3 h de uma
    # terca, "Ainda de pe a esta hora?" e nao "a semana esta na metade".
    if not any(frase.get(c) for c in ("situacao", "chegada", "calendario")) and frase.get("momento")             and set(frase["momento"]) <= {"madrugada", "noite_alta"}:
        return 2.5
    for i, camada in enumerate(CAMADAS):
        if frase.get(camada):
            return len(CAMADAS) - i
    return 0


def escolher(frases: list[dict], ctx: Contexto, recentes: list[str], *, sorteio: random.Random | None = None,
             limite: int = 0) -> dict | None:
    """
    A frase: das que servem, a camada mais forte que ainda tenha frase fora das
    `recentes`; uma situacao forte nunca cede. Devolve {id, texto} ou None.
    """
    r = sorteio or random.Random()
    conds, marcas = ctx.condicoes(), ctx.marcas()
    servem = [f for f in frases if serve(f, conds, marcas)]
    if limite:
        servem = [f for f in servem if len(preencher(f["texto"], marcas)) <= limite]
    if not servem:
        return None
    vistos = list(recentes or [])[-RECENTES:]
    forte = [f for f in servem if set(f.get("situacao") or []) & FORTES & conds["situacao"]]
    if forte:
        livres = [f for f in forte if f["id"] not in vistos] or sorted(forte, key=lambda f: vistos.index(f["id"]) if f["id"] in vistos else -1)[:1]
        f = r.choice(livres)
        return {"id": f["id"], "texto": preencher(f["texto"], marcas)}
    for nivel in sorted({_camada(f) for f in servem}, reverse=True):
        livres = [f for f in servem if _camada(f) == nivel and f["id"] not in vistos]
        if livres:
            f = r.choice(livres)
            return {"id": f["id"], "texto": preencher(f["texto"], marcas)}
    # Todas ja mostradas ha pouco: a mostrada ha mais tempo.
    f = min(servem, key=lambda f: vistos.index(f["id"]) if f["id"] in vistos else -1)
    return {"id": f["id"], "texto": preencher(f["texto"], marcas)}


def saudar(ctx: Contexto, recentes: list[str], banco: dict | None = None, sorteio: random.Random | None = None) -> dict:
    banco = banco or carregar()
    titulo = escolher(banco["titulos"], ctx, recentes, sorteio=sorteio, limite=LIMITE_TITULO) \
        or {"id": "t-antigo-ola", "texto": "Olá. Por onde começamos?"}
    sub = escolher(banco["subtitulos"], ctx, recentes, sorteio=sorteio) \
        or {"id": "s-antigo-padrao", "texto": "É só me dizer o que você precisa — eu leio e respondo aqui mesmo."}
    conds = ctx.condicoes()
    conversa = None
    if "{conversa}" in next((f["texto"] for f in banco["titulos"] if f["id"] == titulo["id"]), ""):
        c = ctx.pela_metade[0] if ctx.pela_metade else ctx.ultima_conversa
        conversa = {"id": c.get("id"), "titulo": c.get("titulo")} if c else None
    return {"titulo": titulo["texto"], "subtitulo": sub["texto"], "ids": [titulo["id"], sub["id"]],
            "conversa": conversa, "condicoes": {k: sorted(v) for k, v in conds.items()}}


# ------------------------------------------------------------------ servidor

def _data(texto: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(texto)) if texto else None
    except ValueError:
        return None


def contexto_do_escritorio(estado, agora: datetime, pessoa: dict | None, ultima_abertura: str = "",
                           ultima_conversa: str = "", conversa_aberta_em: str = "") -> Contexto:
    prefs = estado.prefs.dados
    nome = (pessoa or {}).get("nome") or ((prefs.get("pessoa") or {}).get("nome") or "")
    hoje = agora.date().isoformat()
    prazos_hoje, pendencias = [], 0
    try:
        for t in estado.tarefas.listar("todas"):
            if t.get("concluida"):
                continue
            p = str(t.get("prazo") or "")[:10]
            if p == hoje and str(t.get("lista") or "").lower() == "prazos":
                prazos_hoje.append(t.get("titulo") or "prazo")
            if p and p < hoje:
                pendencias += 1
    except Exception:  # noqa: BLE001 - sem tarefas, sem prazos: a frase so fica mais geral
        pass
    try:
        pendencias += len(estado.fila.pendentes())
    except Exception:  # noqa: BLE001
        pass
    pela_metade = []
    try:
        for r in estado.trabalhos.listar().get("trabalhos", []):
            if r.get("estado") == "pausado":
                pela_metade.append({"id": r["id"], "titulo": r.get("titulo", "")})
    except Exception:  # noqa: BLE001
        pass
    ultima = None
    if ultima_conversa:
        t = estado.trabalhos.obter(ultima_conversa)
        aberta = _data(conversa_aberta_em)
        if t and aberta:
            ultima = {"id": t.id, "titulo": t.titulo, "aberta_em": aberta}
    return Contexto(agora=agora, nome=nome, documentos=len(estado.searcher.documents), prazos_hoje=prazos_hoje,
                    pendencias=pendencias, pela_metade=pela_metade[:1], ultima_abertura=_data(ultima_abertura),
                    ultima_conversa=ultima, fundacao=str((prefs.get("escritorio") or {}).get("fundacao") or ""))


def montar(estado, app, pessoa_de) -> None:
    @app.get("/api/saudacao")
    def rota_saudacao(request: Request, recentes: str = "", ultima_abertura: str = "", ultima_conversa: str = "",
                      conversa_aberta_em: str = "", agora: str = "") -> dict:
        if not bool((estado.prefs.dados.get("conversa") or {}).get("saudacao")):
            return {"ligado": False}
        quando = _data(agora) or datetime.now()
        ctx = contexto_do_escritorio(estado, quando, pessoa_de(request), ultima_abertura, ultima_conversa,
                                     conversa_aberta_em)
        return {"ligado": True, **saudar(ctx, [x for x in recentes.split(",") if x])}
