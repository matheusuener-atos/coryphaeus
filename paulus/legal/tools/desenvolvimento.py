"""
O historico de versoes da pagina Desenvolvimento aberto (site e app).

    venv/Scripts/python.exe tools/desenvolvimento.py

Le as releases do GitHub e escreve site/dados/versoes.json:

    {"releases": [{"version": "0.9.3", "date": "2026-09-28",
                   "changes": ["Extrato de contribuições no desenho novo",
                               {"text": "...", "preview": "/versoes/0.9.3/extrato.webp"}]}]}

Cada mudanca sai da lista "O que mudou" das notas da release: o titulo em
negrito, quando houver, ou a primeira frase. A data e a da publicacao, no
horario de Brasilia.

Uma versao marcada com "curado": true no arquivo (textos revistos, miniatura
escolhida) nunca e sobrescrita: so as outras sao refeitas das notas. O
Worker junta este arquivo ao apoio consolidado de cada mes em
/api/public/desenvolvimento. O publicar.py roda isto a cada versao nova.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
REPO = APP.parent.parent
DESTINO = REPO / "site" / "dados" / "versoes.json"
REPOSITORIO = "matheusuener-atos/coryphaeus"


def _gh(*args: str) -> str:
    r = subprocess.run(["gh", *args, "-R", REPOSITORIO], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise RuntimeError(r.stderr.strip() or "gh falhou")
    return r.stdout


def data_brasilia(iso: str) -> str:
    quando = datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S") - timedelta(hours=3)
    return quando.strftime("%Y-%m-%d")


def mudancas(notas: str) -> list[str]:
    """Os itens da lista "O que ..." das notas, curtos."""
    linhas = notas.replace("\r", "").split("\n")
    itens: list[str] = []
    dentro = False
    for linha in linhas:
        if re.match(r"^\*\*O que ", linha.strip()):
            dentro = True
            continue
        if not dentro:
            continue
        if not linha.strip().startswith("- "):
            if itens and not linha.strip():
                break
            continue
        item = linha.strip()[2:].strip()
        titulo = re.match(r"^\*\*(.+?)\*\*", item)
        if titulo and not titulo.group(1).strip().endswith(":"):
            texto = titulo.group(1).strip().rstrip(".")
        elif titulo:  # "**Calibração:** com ... ligado, ..." - o rotulo e a frase
            resto = item[titulo.end():].strip()
            texto = titulo.group(1).strip() + " " + re.split(r"(?<=[a-zà-ú0-9)])\. |; ", resto, maxsplit=1)[0].strip().rstrip(".")
        else:
            texto = re.split(r"(?<=[a-zà-ú0-9)])\. |; | — ", item, maxsplit=1)[0].strip().rstrip(".")
        texto = re.sub(r"[*`]", "", texto)
        if len(texto) > 110:
            texto = texto[:107].rsplit(" ", 1)[0] + "…"
        if texto:
            itens.append(texto)
    return itens[:12]


def gerar() -> dict:
    antes = {}
    if DESTINO.exists():
        antes = {r["version"]: r for r in json.loads(DESTINO.read_text(encoding="utf-8")).get("releases", [])}
    lista = json.loads(_gh("release", "list", "--limit", "200", "--json", "tagName,publishedAt,isDraft"))
    releases = []
    for rel in lista:
        if rel.get("isDraft"):
            continue
        versao = rel["tagName"].lstrip("v")
        if antes.get(versao, {}).get("curado"):
            releases.append(antes[versao])
            continue
        corpo = json.loads(_gh("release", "view", rel["tagName"], "--json", "body")).get("body", "")
        releases.append({"version": versao, "date": data_brasilia(rel["publishedAt"]),
                         "changes": mudancas(corpo) or ["Correções e melhorias"]})
    releases.sort(key=lambda r: tuple(int(x) for x in r["version"].split(".")), reverse=True)
    dados = {"releases": releases}
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dados


if __name__ == "__main__":
    d = gerar()
    for r in d["releases"]:
        print(r["version"], r["date"], "·", len(r["changes"]), "mudança(s)")
