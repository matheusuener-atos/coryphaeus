"""
O que o site do PAULUS publica e o programa mostra: o historico de versoes,
mes a mes (tela Desenvolvimento aberto, js/41-desenvolvimento.js).

So leitura - nada do usuario vai junto. A resposta boa fica guardada; sem
internet, volta a ultima copia, com `offline: True`.

O endereco do site pode ser trocado por PAULUS_SITE (para testar num Worker
local, por exemplo).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import requests

SITE = os.environ.get("PAULUS_SITE", "https://paulus.ia.br").rstrip("/")
TEMPO = 20
PUBLICADOS = ("desenvolvimento",)


class ErroDoSite(Exception):
    """Mensagem ja em portugues, para a tela mostrar como veio."""


def _ler(caminho: str) -> dict:
    try:
        r = requests.get(SITE + caminho, timeout=TEMPO)
    except requests.RequestException as exc:
        raise ErroDoSite("não consegui falar com o site do PAULUS - confira a internet") from exc
    try:
        dados = r.json()
    except ValueError:
        dados = {}
    if not r.ok:
        raise ErroDoSite(str(dados.get("erro") or f"o site respondeu {r.status_code}"))
    return dados


def publico(qual: str, pasta) -> dict:
    """O que o site publica em /api/public/<qual>, com a ultima copia em `pasta` para ficar sem internet."""
    if qual not in PUBLICADOS:
        raise ErroDoSite("isso o site não publica")
    copia = Path(pasta) / f"{qual}.json"
    try:
        dados = _ler(f"/api/public/{qual}")
        copia.parent.mkdir(parents=True, exist_ok=True)
        copia.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        return {**dados, "offline": False}
    except ErroDoSite:
        if copia.exists():
            try:
                return {**json.loads(copia.read_text(encoding="utf-8")), "offline": True}
            except ValueError:
                pass
        raise
