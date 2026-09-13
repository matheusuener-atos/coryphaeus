"""
As referencias normativas: artigo, lei, sumula.

"art. 300, §1º, II, do CPC" e uma das coisas mais regulares que existem num
texto juridico, e uma das que um modelo pequeno mais erra: ele troca o
paragrafo pelo inciso, inventa o codigo quando a sigla esta longe do artigo, e
de vez em quando muda o numero. Regra acerta sempre e de graca.

Duas escolhas que fazem diferenca na consulta:

**A sigla vira identificador de lei.** "CPC" e "Lei 13.105/2015" sao a mesma
norma; guardadas como texto seriam duas. `instrument_id` normaliza para
`lei_13105_2015`, e e por ele que se acha "todos os documentos que citam o
art. 300 do CPC" - inclusive nos que escreveram o nome por extenso.

**O que fica sem instrumento fica sem instrumento.** "na forma do art. 5º"
sozinho, sem dizer de que lei, nao vira "art. 5º da Constituicao": fica com o
artigo e sem `instrument`, e quem le decide. Completar aqui seria adivinhar a
norma mais famosa, que e exatamente o erro que este modulo existe para evitar.
"""

from __future__ import annotations

import re
import unicodedata

from .base import Pedido, Resultado, item_do_span

ID = "lawref-rules/v1"
SECAO = "legal_references"
NIVEL = 0
PROMPT_VERSAO = ""

# A tabela de instrumentos. As quatro primeiras siglas sao as mesmas de
# src/leis.py, onde os codigos ficam guardados para consulta - o programa ja
# sabe abrir o artigo depois de achar a citacao.
INSTRUMENTOS = {
    "cpc": ("lei_13105_2015", "Código de Processo Civil"),
    "cc": ("lei_10406_2002", "Código Civil"),
    "cp": ("decreto_lei_2848_1940", "Código Penal"),
    "clt": ("decreto_lei_5452_1943", "Consolidação das Leis do Trabalho"),
    "cf": ("constituicao_1988", "Constituição Federal"),
    "cdc": ("lei_8078_1990", "Código de Defesa do Consumidor"),
    "ctn": ("lei_5172_1966", "Código Tributário Nacional"),
    "cpp": ("decreto_lei_3689_1941", "Código de Processo Penal"),
    "ctb": ("lei_9503_1997", "Código de Trânsito Brasileiro"),
    "ecа": ("lei_8069_1990", "Estatuto da Criança e do Adolescente"),
    "eca": ("lei_8069_1990", "Estatuto da Criança e do Adolescente"),
}

# Como a norma aparece escrita por extenso, para cair na mesma sigla.
POR_EXTENSO = {
    "codigo de processo civil": "cpc",
    "novo codigo de processo civil": "cpc",
    "codigo civil": "cc",
    "codigo penal": "cp",
    "codigo de processo penal": "cpp",
    "consolidacao das leis do trabalho": "clt",
    "constituicao federal": "cf",
    "constituicao da republica": "cf",
    "codigo de defesa do consumidor": "cdc",
    "codigo tributario nacional": "ctn",
    "estatuto da crianca e do adolescente": "eca",
}

RE_ARTIGO = re.compile(
    r"\bart(?:igo|\.|s\.|igos)?\s*(\d+[\-‐-―]?[A-Z]?)\s*[ºo°]?"
    r"(?P<resto>(?:\s*[,;]?\s*(?:§+\s*\d+[ºo°]?|par[áa]grafo\s+[úu]nico|"
    r"inciso\s+[IVXLCDM]+|al[íi]nea\s+[a-z]\b|[IVXLCDM]{1,6}\b)){0,3})"
    r"(?P<lei>(?:\s*,?\s*(?:d[aoe]s?\s+)?(?:CPC|CC|CF|CLT|CP|CPP|CDC|CTN|CTB|ECA|"
    r"Lei\s*n?[º°.]?\s*[\d.]+\s*/\s*\d{4}|C[óo]digo[^.;\n]{0,40}|Constitui[çc][ãa]o[^.;\n]{0,30}))?)",
    re.IGNORECASE)

RE_LEI = re.compile(
    r"\bLei\s*(?:Complementar\s*)?n?[º°.]?\s*([\d]{1,3}(?:\.\d{3})*)\s*/\s*(\d{4})", re.IGNORECASE)

RE_SUMULA = re.compile(
    r"\bS[úu]mula\s*(?:Vinculante\s*)?n?[º°.]?\s*(\d+)"
    r"(?:\s*(?:d[oa]\s*)?(STF|STJ|TST|TSE|STM|TJ[A-Z]{2}|TRF\s*\d))?", re.IGNORECASE)

RE_PARAGRAFO = re.compile(r"§+\s*(\d+)", re.IGNORECASE)
RE_UNICO = re.compile(r"par[áa]grafo\s+[úu]nico", re.IGNORECASE)
RE_INCISO = re.compile(r"(?:inciso\s+)?\b([IVXLCDM]{1,6})\b")
RE_ALINEA = re.compile(r"al[íi]nea\s+([a-z])\b", re.IGNORECASE)


def _plano(texto: str) -> str:
    normal = unicodedata.normalize("NFD", (texto or "").lower())
    return " ".join("".join(c for c in normal if unicodedata.category(c) != "Mn").split())


def _instrumento(bruto: str) -> tuple[str, str, str]:
    """De "do CPC" ou "da Lei 13.105/2015" para (sigla, id, nome)."""
    plano = _plano(bruto)
    lei = RE_LEI.search(bruto or "")
    if lei:
        numero = lei.group(1).replace(".", "")
        return ("", f"lei_{numero}_{lei.group(2)}", f"Lei {lei.group(1)}/{lei.group(2)}")

    for nome, sigla in POR_EXTENSO.items():
        if nome in plano:
            identificador, rotulo = INSTRUMENTOS[sigla]
            return (sigla.upper(), identificador, rotulo)

    for sigla in ("cpc", "cpp", "cdc", "ctn", "ctb", "clt", "eca", "cf", "cc", "cp"):
        if re.search(rf"\b{sigla}\b", plano):
            identificador, rotulo = INSTRUMENTOS[sigla]
            return (sigla.upper(), identificador, rotulo)
    return ("", "", "")


def achar(texto: str) -> list[dict]:
    """Cada citacao normativa do texto, com o que der para saber dela."""
    achados: list[dict] = []

    for encontro in RE_ARTIGO.finditer(texto or ""):
        resto = encontro.group("resto") or ""
        cauda = encontro.group("lei") or ""
        sigla, identificador, nome = _instrumento(cauda)
        dados = {
            "kind": "article",
            "article": encontro.group(1).upper().replace("º", "").replace("°", ""),
        }
        if RE_UNICO.search(resto):
            dados["paragraph"] = "único"
        else:
            paragrafo = RE_PARAGRAFO.search(resto)
            if paragrafo:
                dados["paragraph"] = paragrafo.group(1)
        inciso = RE_INCISO.search(re.sub(r"§+\s*\d+", "", resto))
        if inciso:
            dados["item"] = inciso.group(1).upper()
        alinea = RE_ALINEA.search(resto)
        if alinea:
            dados["subitem"] = alinea.group(1).lower()
        if identificador:
            dados["instrument"] = sigla or nome
            dados["instrument_id"] = identificador
            dados["instrument_name"] = nome
        achados.append({"dados": dados, "inicio": encontro.start(), "fim": encontro.end()})

    for encontro in RE_LEI.finditer(texto or ""):
        # A lei que ja foi citada colada a um artigo nao vira item separado.
        if any(a["inicio"] <= encontro.start() < a["fim"] for a in achados):
            continue
        numero = encontro.group(1).replace(".", "")
        achados.append({
            "dados": {"kind": "law", "instrument_id": f"lei_{numero}_{encontro.group(2)}",
                      "instrument": f"Lei {encontro.group(1)}/{encontro.group(2)}",
                      "instrument_name": f"Lei {encontro.group(1)}/{encontro.group(2)}"},
            "inicio": encontro.start(), "fim": encontro.end(),
        })

    for encontro in RE_SUMULA.finditer(texto or ""):
        tribunal = (encontro.group(2) or "").upper().replace(" ", "")
        achados.append({
            "dados": {"kind": "precedent", "number": encontro.group(1),
                      "court": tribunal,
                      "instrument": f"Súmula {encontro.group(1)}" + (f" do {tribunal}" if tribunal else ""),
                      "instrument_id": f"sumula_{tribunal.lower()}_{encontro.group(1)}" if tribunal
                      else f"sumula_{encontro.group(1)}"},
            "inicio": encontro.start(), "fim": encontro.end(),
        })

    return sorted(achados, key=lambda a: a["inicio"])


def _assinatura(dados: dict) -> tuple:
    return (dados.get("kind"), dados.get("instrument_id", ""), dados.get("article", ""),
            dados.get("paragraph", ""), dados.get("item", ""), dados.get("number", ""))


def extrair(pedido: Pedido) -> Resultado:
    itens = []
    vistos: set[tuple] = set()
    for i, achado in enumerate(achar(pedido.texto), start=1):
        marca = _assinatura(achado["dados"])
        if marca in vistos:
            continue
        vistos.add(marca)
        itens.append(item_do_span(
            pedido, achado["inicio"], achado["fim"],
            id_=f"ref_{i:03d}",
            dados=achado["dados"],
            produzido_por=ID,
        ))
    return Resultado(itens=itens)
