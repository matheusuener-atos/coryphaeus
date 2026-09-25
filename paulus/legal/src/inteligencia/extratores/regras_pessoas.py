"""
As pessoas do documento, pelo CPF - e pela OAB, quando ha advogado.

Uma pessoa so entra aqui com documento que fecha a conta. Nome sem CPF nao
vira pessoa nesta secao: para isso ja existe `parties`, que e feita a modelo e
sai marcada como tal. Aqui o criterio e outro e mais duro - se o digito
verificador nao bater, o item continua sendo guardado, mas nasce `uncertain` e
com um recado em portugues, porque um CPF errado num documento e justamente o
tipo de coisa que alguem precisa ver.

O papel (advogado, parte, testemunha) so aparece quando esta escrito perto do
nome. E a mesma regra que o extrator de partes aprendeu a duras penas: um
modelo pequeno gerou um papel falso numa procuracao onde a palavra nao existe,
e desde entao papel nao conferido nao vira papel.
"""

from __future__ import annotations

from . import entidades, frases
from .base import Pedido, Resultado, item_do_span
from .entidades import papel_perto

ID = "person-rules/v1"
SECAO = "people"
NIVEL = 0
PROMPT_VERSAO = ""

MAXIMO = 30


def achar(texto: str) -> list[dict]:
    achados: list[dict] = []
    for encontro in entidades.RE_CPF.finditer(texto or ""):
        nome, inicio = entidades.nome_antes(texto, encontro.start())
        if not nome:
            continue
        achados.append({
            "inicio": inicio, "fim": encontro.end(), "name": nome,
            "document": encontro.group(0), "document_kind": "CPF",
            "valid": entidades.cpf_valido(encontro.group(0)),
            "prioridade": 0,
        })
    for encontro in entidades.RE_OAB.finditer(texto or ""):
        nome, inicio = entidades.nome_antes(texto, encontro.start())
        if not nome:
            continue
        achados.append({
            "inicio": inicio, "fim": encontro.end(), "name": nome,
            "document": frases.limpo(encontro.group(0)).upper(),
            "document_kind": "OAB", "valid": True, "role": "lawyer",
            "prioridade": 1,
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
                 "document_kind": achado["document_kind"],
                 "document_valid": achado["valid"],
                 "kind": "person"}
        papel = achado.get("role") or papel_perto(pedido.texto, achado["inicio"])
        if papel:
            dados["role"] = papel
        if not achado["valid"]:
            dados["note"] = "o dígito verificador do CPF não fecha — confira no documento"
        item = item_do_span(
            pedido, achado["inicio"], achado["fim"],
            id_=f"person_{len(itens) + 1:03d}", dados=dados, produzido_por=ID)
        if not achado["valid"]:
            # O trecho existe e foi lido certo; o que nao fecha e o numero.
            # Entao a citacao continua verificada e a certeza cai.
            item.certainty = "uncertain"
        itens.append(item)
        if len(itens) >= MAXIMO:
            break
    return Resultado(itens=itens)
