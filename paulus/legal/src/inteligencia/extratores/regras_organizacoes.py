"""
As empresas do documento, pelo CNPJ.

Mesma regra das pessoas, outro documento e outra conta de verificacao. E e
aqui que o acervo real deste escritorio da o melhor exemplo do que um digito
verificador vale: uma das procuracoes traz o CNPJ da outorgante duas vezes,
no cabecalho e na assinatura, com um digito diferente entre as duas. Uma
delas esta errada desde 2021. A camada le as duas, confere as duas e diz qual
e qual - sem consultar nada, sem rede, so com aritmetica.
"""

from __future__ import annotations

from . import entidades, frases
from .base import Pedido, Resultado, item_do_span
from .entidades import papel_perto

ID = "organization-rules/v1"
SECAO = "organizations"
NIVEL = 0
PROMPT_VERSAO = ""

MAXIMO = 30


def achar(texto: str) -> list[dict]:
    achados: list[dict] = []
    for encontro in entidades.RE_CNPJ.finditer(texto or ""):
        nome, inicio = entidades.nome_antes(texto, encontro.start())
        if not nome:
            continue
        achados.append({
            "inicio": inicio, "fim": encontro.end(), "name": nome,
            "document": encontro.group(0),
            "valid": entidades.cnpj_valido(encontro.group(0)),
        })
    return sorted(frases.sem_sobrepor(achados), key=lambda a: a["inicio"])


def extrair(pedido: Pedido) -> Resultado:
    itens, vistos = [], set()
    for achado in achar(pedido.texto):
        marca = frases.chave(achado["name"]) + "|" + achado["document"]
        if marca in vistos:
            continue
        vistos.add(marca)
        dados = {"name": achado["name"], "document": achado["document"],
                 "document_kind": "CNPJ", "document_valid": achado["valid"],
                 "kind": "organization"}
        papel = papel_perto(pedido.texto, achado["inicio"])
        if papel:
            dados["role"] = papel
        if not achado["valid"]:
            dados["note"] = "o dígito verificador do CNPJ não fecha — confira no documento"
        item = item_do_span(
            pedido, achado["inicio"], achado["fim"],
            id_=f"organization_{len(itens) + 1:03d}", dados=dados, produzido_por=ID)
        if not achado["valid"]:
            item.certainty = "uncertain"
        itens.append(item)
        if len(itens) >= MAXIMO:
            break
    return Resultado(itens=itens)
