"""
Os valores em dinheiro, guardados como numero - nunca so como texto.

"R$ 15.000,00" guardado em texto obriga quem consulta a interpretar de novo:
tirar o R$, tirar o ponto de milhar, trocar a virgula decimal por ponto. Feito
uma vez no lugar errado, o valor da causa de quinze mil vira quinze reais. Aqui
o valor entra como `{"value": 15000.0, "currency": "BRL"}` e o texto original
fica na citacao, para a pessoa conferir com os proprios olhos.

Como nas datas, o `kind` vem do contexto e e heuristica declarada: o fato e o
valor e o trecho; o rotulo e como aquele trecho o apresenta. Num contrato de
honorarios a diferenca entre "valor da causa" e "honorarios" muda a resposta
inteira, e por isso vale procurar - mas nunca vale inventar.
"""

from __future__ import annotations

import re

from .base import Pedido, Resultado, escolher_kind, item_do_span, limpar, volta_de

ID = "amount-parser/v1"
SECAO = "amounts"
NIVEL = 0
PROMPT_VERSAO = ""

# R$ com milhar e centavos, a forma que aparece em peca e contrato. O valor
# sem "R$" fica de fora de proposito: numero solto no meio de um contrato e
# quase sempre artigo, clausula ou prazo, nao dinheiro.
RE_REAIS = re.compile(r"R\$\s*((?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{2})?)")

TIPOS = {
    "claim": ("valor da causa", "valor atribuido a causa", "da-se a causa", "valor da acao"),
    "fee": ("honorario", "honorarios contratuais", "honorarios advocaticios"),
    "contract": ("valor do contrato", "valor total", "preco", "remuneracao"),
    "penalty": ("multa", "penalidade", "clausula penal", "juros"),
    "rent": ("aluguel", "locacao mensal"),
    "damages": ("indenizacao", "danos morais", "danos materiais", "reparacao"),
    "debt": ("divida", "debito", "saldo devedor", "em atraso", "vencid"),
    "installment": ("parcela", "prestacao", "mensalidade"),
}


def para_numero(bruto: str) -> float | None:
    """"15.000,00" vira 15000.0. Sem centavos, "15.000" vira 15000.0."""
    limpo = (bruto or "").strip().replace(".", "").replace(",", ".")
    try:
        return round(float(limpo), 2)
    except ValueError:
        return None


def achar(texto: str) -> list[dict]:
    achados: list[dict] = []
    for encontro in RE_REAIS.finditer(texto or ""):
        valor = para_numero(encontro.group(1))
        if valor is None:
            continue
        volta = volta_de(texto, encontro.start())
        achados.append({
            "value": valor,
            "currency": "BRL",
            "kind": escolher_kind(volta, TIPOS),
            "inicio": encontro.start(),
            "fim": encontro.end(),
        })
    return achados


def extrair(pedido: Pedido) -> Resultado:
    itens = []
    vistos: set[tuple[float, str]] = set()
    for i, achado in enumerate(achar(pedido.texto), start=1):
        marca = (achado["value"], achado["kind"])
        if marca in vistos:
            continue
        vistos.add(marca)
        itens.append(item_do_span(
            pedido, achado["inicio"], achado["fim"],
            id_=f"amount_{i:03d}",
            dados={"value": achado["value"], "currency": "BRL", "kind": achado["kind"],
                   "value_text": limpar(pedido.texto[achado["inicio"]:achado["fim"]])},
            produzido_por=ID,
        ))
    return Resultado(itens=itens)
