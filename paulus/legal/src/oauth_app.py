"""
O aplicativo PAULUS registrado no Google e na Microsoft.

Os IDs sao do PAULUS, e nao de cada escritorio: quem publica o programa
registra o aplicativo uma vez em cada provedor (roteiro em
docs/email-oauth.md). Toda instalacao vai com eles, e quem usa so clica em
"Entrar com Google/Microsoft" e faz login na pagina do provedor.

Onde ficam: no arquivo oauth_app.json, na pasta do programa (ao lado de
src/), versionado no repositorio - que e PRIVADO. Se o repositorio voltar a
ser publico, este arquivo sai dele antes: um client secret publicado deixa
qualquer um usar o registro em nome do PAULUS (gastar a cota, montar uma tela
falsa de "Entrar com PAULUS"), e aí o certo e gerar uma chave nova no Google
Cloud. O modelo com os campos vazios e o oauth_app.exemplo.json.

Em aplicativo de computador, o proprio Google diz que o client secret nao e
tratado como confidencial - ele vai dentro de todo programa instalado, e a
protecao do login e o PKCE. Mante-lo fora de repositorio publico e para nao
publica-lo, nao porque esconde-lo do usuario seja possivel.

Sem o arquivo (ou com o campo vazio), o provedor nao aparece na tela. Para
desenvolver com outro registro, as variaveis de ambiente
PAULUS_GOOGLE_CLIENT_ID, PAULUS_GOOGLE_CLIENT_SECRET e
PAULUS_MICROSOFT_CLIENT_ID passam na frente do arquivo.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent.parent / "oauth_app.json"

_CAMPOS = {
    "google_client_id": "PAULUS_GOOGLE_CLIENT_ID",
    "google_client_secret": "PAULUS_GOOGLE_CLIENT_SECRET",
    "microsoft_client_id": "PAULUS_MICROSOFT_CLIENT_ID",
}


def _do_arquivo() -> dict:
    try:
        dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _valor(chave: str) -> str:
    return (os.environ.get(_CAMPOS[chave]) or str(_do_arquivo().get(chave) or "")).strip()


def credenciais(provedor: str) -> dict:
    """O client ID (e, no Google, o secret) que o login deste provedor usa."""
    if provedor == "google":
        return {"client_id": _valor("google_client_id"), "client_secret": _valor("google_client_secret")}
    if provedor == "microsoft":
        return {"client_id": _valor("microsoft_client_id")}
    return {}


def configurado(provedor: str) -> bool:
    c = credenciais(provedor)
    if not c.get("client_id"):
        return False
    return bool(c.get("client_secret")) if provedor == "google" else True
