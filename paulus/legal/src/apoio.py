"""
Apoiar o projeto: o pagamento pelo Mercado Pago, sempre atraves do site.

O programa nunca fala com o Mercado Pago direto e nunca tem a chave dele: o
Access Token mora no Worker do paulus.ia.br (worker/index.js, na raiz do
repositorio). Aqui so se repassa o pedido ao Worker e a resposta a tela:

    criar_pix(valor, email)            o QR do Pix
    situacao_do_pix(id)                se ja foi pago
    situacao_da_assinatura(id)         se o cartao foi posto e esta ativa
    criar_assinatura(valor, email, f)  o link da pagina do Mercado Pago onde
                                       a pessoa poe o cartao

O endereco do site pode ser trocado por PAULUS_SITE (para testar num Worker
local, por exemplo).
"""

from __future__ import annotations

import os
import re

import requests

SITE = os.environ.get("PAULUS_SITE", "https://paulus.ia.br").rstrip("/")
TEMPO = 20
RE_ID = re.compile(r"^[A-Za-z0-9_-]{6,64}$")


class ErroDeApoio(Exception):
    """Mensagem ja em portugues, para a tela mostrar como veio."""


def _chamar(metodo: str, caminho: str, corpo: dict | None = None) -> dict:
    try:
        r = requests.request(metodo, SITE + caminho, json=corpo, timeout=TEMPO)
    except requests.RequestException as exc:
        raise ErroDeApoio("não consegui falar com o site do PAULUS - confira a internet") from exc
    try:
        dados = r.json()
    except ValueError:
        dados = {}
    if not r.ok:
        raise ErroDeApoio(str(dados.get("erro") or f"o site respondeu {r.status_code}"))
    return dados


def criar_pix(valor: float, email: str) -> dict:
    return _chamar("POST", "/api/mp/pix", {"valor": valor, "email": email})


def situacao_do_pix(id_: str) -> dict:
    if not RE_ID.match(id_ or ""):
        raise ErroDeApoio("identificador de Pix inválido")
    return _chamar("GET", f"/api/mp/pix/{id_}")


def situacao_da_assinatura(id_: str) -> dict:
    if not RE_ID.match(id_ or ""):
        raise ErroDeApoio("identificador de assinatura inválido")
    return _chamar("GET", f"/api/mp/assinatura/{id_}")


def criar_assinatura(valor: float, email: str, frequencia: str) -> dict:
    frequencia = "anual" if frequencia == "anual" else "mensal"
    return _chamar("POST", "/api/mp/assinatura", {"valor": valor, "email": email, "frequencia": frequencia})
