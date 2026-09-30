"""
Monta config/acervo-inicial/temas-stj.jsonl.gz (L5, src/fundamentacao.py) a
partir do Temas.csv do Portal de Dados Abertos do STJ (CC-BY):

    venv/Scripts/python.exe tools/temas_stj.py            # baixa do portal
    venv/Scripts/python.exe tools/temas_stj.py Temas.csv  # de um arquivo baixado

Ficam os Temas Repetitivos e os IAC com questão ou tese; saem os cancelados,
os vinculados a outro tema e os sem processo. Depois, acertar "temas" em
config/acervo-inicial/indice.json.
"""

import gzip
import json
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import fundamentacao  # noqa: E402


def main() -> int:
    if len(sys.argv) > 1:
        texto = Path(sys.argv[1]).read_text(encoding="utf-8")
    else:
        import requests

        r = requests.get(fundamentacao.URL_STJ, timeout=120)
        r.raise_for_status()
        r.encoding = "utf-8"
        texto = r.text
    linhas = fundamentacao._linhas_do_csv(texto)
    with gzip.open(fundamentacao.ARQUIVO, "wt", encoding="utf-8") as f:
        f.write(json.dumps({"fonte": "Portal de Dados Abertos do STJ — Precedentes qualificados (Temas.csv)",
                            "url": "https://dadosabertos.web.stj.jus.br/dataset/precedentes-qualificados",
                            "licenca": "CC-BY (Creative Commons Atribuição)", "baixado_em": date.today().isoformat(),
                            "temas": len(linhas)}, ensure_ascii=False) + "\n")
        for l in linhas:
            f.write(json.dumps(l, ensure_ascii=False) + "\n")
    print(f"{len(linhas)} temas, {sum(1 for l in linhas if l['tese'])} com tese -> {fundamentacao.ARQUIVO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
