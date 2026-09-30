"""
Monta o acervo que já vem com o PAULUS (config/acervo-inicial/).

- os códigos de leis.CODIGOS, no texto compilado do Planalto (.htm.gz);
- os enunciados das súmulas do STJ, do PDF oficial do STJ (sumulas-stj.txt.gz),
  sem as canceladas e revogadas (a alterada vem na redação nova).

Lei e decisão judicial não têm direito autoral (Lei 9.610/98, art. 8º, IV):
por isso vêm no instalador. Doutrina não vem - é obra de alguém.

Rodar de novo quando o Planalto ou o STJ mudarem o texto:
    venv\\Scripts\\python.exe tools\\acervo_inicial.py
"""

from __future__ import annotations

import gzip
import io
import json
import re
import sys
from datetime import date
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import leis  # noqa: E402

DESTINO = RAIZ / "config" / "acervo-inicial"
STJ = "https://scon.stj.jus.br/docs_internet/VerbetesSTJ.pdf"
CABECA = {"User-Agent": "Mozilla/5.0 PAULUS"}

RE_CABECA_STJ = re.compile(r"^S[ÚU]MULA\s+(\d{1,4})\s*(?:\(S[ÚU]MULA (CANCELADA|REVOGADA|ALTERADA)\))?\s*(?:VEJA MAIS)?\s*$", re.M)
RE_RODAPE_STJ = re.compile(r"^\s*scon\.stj\.jus\.br/SCON/\s*[\d/]*\s*$", re.M)


def sumulas_do_stj(pdf: bytes) -> tuple[str, int, int]:
    """O texto 'Súmula N do STJ' + enunciado, da mais antiga para a mais nova; (texto, vigentes, canceladas)."""
    import pypdf

    bruto = "\n".join(p.extract_text() or "" for p in pypdf.PdfReader(io.BytesIO(pdf)).pages)
    bruto = RE_RODAPE_STJ.sub("", bruto)
    marcas = list(RE_CABECA_STJ.finditer(bruto))
    vigentes, canceladas = {}, 0
    for i, m in enumerate(marcas):
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(bruto)
        if m.group(2) in ("CANCELADA", "REVOGADA"):
            canceladas += 1
            continue
        enunciado = " ".join(bruto[m.end():fim].split())
        if enunciado:
            vigentes[int(m.group(1))] = enunciado
    texto = "".join(f"Súmula {n} do STJ\n{vigentes[n]}\n\n" for n in sorted(vigentes))
    return texto, len(vigentes), canceladas


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    indice = {"montado_em": date.today().isoformat(), "codigos": {}, "sumulas": {}}
    for codigo, dados in leis.CODIGOS.items():
        r = requests.get(dados["fonte"], timeout=120, headers=CABECA)
        r.raise_for_status()
        nome = Path(dados["fonte"]).name + ".gz"
        provisorio = DESTINO / Path(dados["fonte"]).name
        provisorio.write_bytes(r.content)
        try:
            artigos, _ = leis.ler_codigo(provisorio, codigo)
        finally:
            provisorio.unlink(missing_ok=True)
        if len(artigos) < 20:
            raise SystemExit(f"{codigo}: só {len(artigos)} artigos - o Planalto mudou a página?")
        (DESTINO / nome).write_bytes(gzip.compress(r.content, 9, mtime=0))
        indice["codigos"][codigo] = {"arquivo": nome, "artigos": len(artigos), "fonte": dados["fonte"]}
        print(f"{codigo}: {len(artigos)} artigos")
    r = requests.get(STJ, timeout=120, headers=CABECA)
    r.raise_for_status()
    texto, n, canceladas = sumulas_do_stj(r.content)
    if n < 500:
        raise SystemExit(f"STJ: só {n} súmulas - o PDF mudou?")
    (DESTINO / "sumulas-stj.txt.gz").write_bytes(gzip.compress(texto.encode("utf-8"), 9, mtime=0))
    indice["sumulas"]["stj"] = {"arquivo": "sumulas-stj.txt.gz", "nome": "Súmulas do STJ", "enunciados": n,
                                "canceladas_fora": canceladas, "fonte": STJ}
    print(f"STJ: {n} súmulas vigentes ({canceladas} canceladas ou revogadas ficaram fora)")
    (DESTINO / "indice.json").write_text(json.dumps(indice, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
