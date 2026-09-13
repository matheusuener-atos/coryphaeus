"""
De que juizo veio o documento: tribunal, vara, comarca.

Isto quase nunca precisa de modelo. A informacao esta no alto da primeira
pagina, escrita do mesmo jeito ha decadas - "EXCELENTISSIMO SENHOR DOUTOR JUIZ
DE DIREITO DA 3a VARA CIVEL DA COMARCA DE SAO PAULO", "TRIBUNAL DE JUSTICA DO
ESTADO DE GOIAS" - e o numero do processo, quando existe, ja diz o segmento e
o tribunal por construcao (os dois digitos do meio, validados pelo modulo 97).

Quando o documento nao e judicial - um contrato, uma procuracao -, a secao sai
vazia. Vazia e a resposta certa: inventar uma comarca para um contrato
particular seria criar do nada o dado mais facil de conferir e mais caro de
errar.
"""

from __future__ import annotations

import re
import unicodedata

from .base import Pedido, Resultado, fonte_do_span, limpar

ID = "jurisdiction-rules/v1"
SECAO = "jurisdiction"
NIVEL = 0
PROMPT_VERSAO = ""

# Os tribunais escritos como aparecem: sigla ou nome por extenso.
RE_SIGLA = re.compile(r"\b(TJ[A-Z]{2}|TRF\s*-?\s*[1-6]|TRT\s*-?\s*\d{1,2}|STF|STJ|TST|TSE|STM)\b")
RE_TRIBUNAL = re.compile(
    r"TRIBUNAL\s+(?:DE\s+JUSTI[ÇC]A|REGIONAL\s+(?:FEDERAL|DO\s+TRABALHO|ELEITORAL))"
    r"(?:\s+D[OAE]\s+ESTADO\s+D[OAE]\s+[A-ZÁÉÍÓÚÃÕÂÊÔÇ ]{3,30}|\s+D[AO]\s+\d+[ªa]\s+REGI[ÃA]O)?",
    re.IGNORECASE)
RE_VARA = re.compile(
    r"\b(\d{1,3})\s*[ªa]\s*VARA\s+([A-ZÁÉÍÓÚÃÕÂÊÔÇ][A-ZÁÉÍÓÚÃÕÂÊÔÇa-záéíóúãõâêôç ]{2,30})",
    re.IGNORECASE)
RE_COMARCA = re.compile(
    r"\bCOMARCA\s+D[EAO]S?\s+([A-ZÁÉÍÓÚÃÕÂÊÔÇ][A-Za-zÁÉÍÓÚÃÕÂÊÔÇáéíóúãõâêôç ]{2,34})",
    re.IGNORECASE)

# Sigla do tribunal estadual -> unidade da federacao, para a tela poder dizer
# "TJSP" e "São Paulo" sem que ninguem precise decorar a tabela.
UFS = {
    "AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MG": "Minas Gerais", "MS": "Mato Grosso do Sul",
    "MT": "Mato Grosso", "PA": "Pará", "PB": "Paraíba", "PE": "Pernambuco",
    "PI": "Piauí", "PR": "Paraná", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RO": "Rondônia", "RR": "Roraima", "RS": "Rio Grande do Sul", "SC": "Santa Catarina",
    "SE": "Sergipe", "SP": "São Paulo", "TO": "Tocantins",
}

INSTANCIAS = (
    (re.compile(r"\b(TRIBUNAL|C[ÂA]MARA|DESEMBARGADOR|RELATOR|AC[ÓO]RD[ÃA]O|AGRAVO|APELA[ÇC][ÃA]O)\b",
                re.IGNORECASE), "second_instance"),
    (re.compile(r"\b(VARA|JU[ÍI]ZO|JUIZ DE DIREITO|FORO|JUIZADO)\b", re.IGNORECASE), "first_instance"),
)


def _plano(texto: str) -> str:
    normal = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in normal if unicodedata.category(c) != "Mn")


def extrair(pedido: Pedido) -> Resultado:
    # O juizo esta no alto da primeira pagina; procurar no processo inteiro so
    # traria o tribunal citado numa jurisprudencia no meio da fundamentacao.
    cabeca = pedido.texto[:4000]
    objeto: dict = {"country": "BR"}
    ancora: tuple[int, int] | None = None

    sigla = RE_SIGLA.search(cabeca)
    if sigla:
        corte = sigla.group(1).upper().replace(" ", "").replace("-", "")
        objeto["court"] = corte
        ancora = sigla.span()
        if corte.startswith("TJ") and corte[2:] in UFS:
            objeto["state"] = corte[2:]
            objeto["state_name"] = UFS[corte[2:]]
            objeto["court_level"] = "state"
        elif corte.startswith("TRF"):
            objeto["court_level"] = "federal"
        elif corte.startswith("TRT") or corte == "TST":
            objeto["court_level"] = "labor"
        else:
            objeto["court_level"] = "superior"
    else:
        tribunal = RE_TRIBUNAL.search(cabeca)
        if tribunal:
            objeto["court"] = limpar(tribunal.group(0)).title()
            ancora = tribunal.span()

    vara = RE_VARA.search(cabeca)
    if vara:
        objeto["court_division"] = limpar(f"{vara.group(1)}ª Vara {vara.group(2).title()}")
        ancora = ancora or vara.span()

    comarca = RE_COMARCA.search(cabeca)
    if comarca:
        objeto["county"] = limpar(comarca.group(1)).title()
        ancora = ancora or comarca.span()

    if not ancora:
        # Documento que nao e de juizo nenhum: a secao fica vazia, e o
        # roteador escala quando alguem perguntar pelo tribunal.
        return Resultado(objeto={})

    plano = _plano(cabeca)
    for padrao, instancia in INSTANCIAS:
        if padrao.search(cabeca) or padrao.search(plano):
            objeto["instance"] = instancia
            break

    fonte = fonte_do_span(pedido, ancora[0], ancora[1])
    objeto.update({
        "quote": limpar(pedido.texto[ancora[0]:ancora[1]]),
        "certainty": "explicit",
        "verified": True,
        "source": fonte.to_dict(),
        "produced_by": ID,
    })
    return Resultado(objeto=objeto)
