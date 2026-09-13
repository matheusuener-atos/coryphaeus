"""
As datas do documento, e o que cada uma e.

Data em documento juridico raramente esta sozinha: ela vem colada a um verbo
que diz o que aconteceu naquele dia - assinado, protocolado, publicado,
vencido. Guardar so a data seria guardar metade do fato: "12/03/2025" nao
responde "quando o contrato foi assinado?", mas "assinatura em 2025-03-12"
responde.

A data e sempre normalizada para ISO. Guardar "12 de marco de 2025" como
texto obrigaria quem consulta a interpretar de novo - e a interpretar
diferente a cada vez. O texto original continua na citacao, que e o que a
pessoa le; o ISO e o que o programa compara.

O `kind` sai do contexto em volta, e por isso e heuristica declarada: o FATO
e a data e o trecho onde ela aparece; o rotulo e como aquele trecho a
apresenta. Se o contexto nao disser nada, o rotulo fica vazio em vez de
chutar "assinatura".
"""

from __future__ import annotations

import re
from datetime import date

from .base import Pedido, Resultado, escolher_kind, item_do_span, limpar, volta_de

ID = "date-parser/v1"
SECAO = "dates"
NIVEL = 0
PROMPT_VERSAO = ""

MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4, "maio": 5,
    "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}

RE_BARRA = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
RE_EXTENSO = re.compile(
    r"\b(\d{1,2})\s*(?:de|do)?\s+(" + "|".join(MESES) + r")\s*(?:de|do)?\s+(\d{4})\b",
    re.IGNORECASE)
RE_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")

# As pistas vem antes da data quase sempre ("assinado em 12/03/2025"), mas
# "12/03/2025, data da assinatura" tambem acontece - por isso a janela pega
# um pedaco depois tambem.
TIPOS = {
    "signature": ("assinad", "celebrad", "firmad", "pactuad", "aos", "data da assinatura"),
    "filing": ("protocolad", "distribuid", "ajuizad", "peticionad"),
    "publication": ("publicad", "diario oficial", "dje", "intimacao"),
    "hearing": ("audiencia", "sessao de julgamento", "pericia designada"),
    "deadline": ("prazo", "vencimento", "vence em", "ate o dia", "carencia", "improrrogavel"),
    "decision": ("julgad", "sentenca", "acordao", "decisao de"),
    "term": ("vigencia", "vigorar", "inicio da vigencia", "termino"),
}

# Data longe demais nao e data de documento: e numero com cara de data, ou
# erro de leitura. Um contrato de 1930 existe; um de 1230 e OCR.
ANO_MINIMO = 1900
ANO_MAXIMO = 2100


def _valida(dia: int, mes: int, ano: int) -> str:
    if not (ANO_MINIMO <= ano <= ANO_MAXIMO):
        return ""
    try:
        return date(ano, mes, dia).isoformat()
    except ValueError:
        return ""


def achar(texto: str) -> list[dict]:
    """Cada data do texto, em ISO, com onde ela estava e o que parecia ser."""
    achados: list[dict] = []
    vistos: set[tuple[str, int]] = set()

    for encontro in RE_BARRA.finditer(texto or ""):
        dia, mes, ano = (int(x) for x in encontro.groups())
        iso = _valida(dia, mes, ano)
        if iso:
            achados.append({"iso": iso, "inicio": encontro.start(), "fim": encontro.end()})

    for encontro in RE_EXTENSO.finditer(texto or ""):
        dia, mes_nome, ano = encontro.group(1), encontro.group(2).lower(), encontro.group(3)
        iso = _valida(int(dia), MESES[mes_nome], int(ano))
        if iso:
            achados.append({"iso": iso, "inicio": encontro.start(), "fim": encontro.end()})

    for encontro in RE_ISO.finditer(texto or ""):
        ano, mes, dia = (int(x) for x in encontro.groups())
        iso = _valida(dia, mes, ano)
        if iso:
            achados.append({"iso": iso, "inicio": encontro.start(), "fim": encontro.end()})

    saida = []
    for achado in sorted(achados, key=lambda a: a["inicio"]):
        volta = volta_de(texto, achado["inicio"])
        achado["kind"] = escolher_kind(volta, TIPOS)
        chave = (achado["iso"], 0 if not achado["kind"] else 1)
        # A mesma data repetida dez vezes no mesmo documento e uma data so;
        # mas a mesma data como assinatura e como prazo sao duas coisas.
        marca = (achado["iso"] + "|" + achado["kind"], 0)
        if marca in vistos:
            continue
        vistos.add(marca)
        saida.append(achado)
    return saida


def extrair(pedido: Pedido) -> Resultado:
    itens = []
    for i, achado in enumerate(achar(pedido.texto), start=1):
        itens.append(item_do_span(
            pedido, achado["inicio"], achado["fim"],
            id_=f"date_{i:03d}",
            dados={"date": achado["iso"], "kind": achado["kind"],
                   "text": limpar(pedido.texto[achado["inicio"]:achado["fim"]])},
            produzido_por=ID,
            folga=0,
        ))
    return Resultado(itens=itens)
