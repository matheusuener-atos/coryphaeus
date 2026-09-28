"""
As fontes dos PDFs que o PAULUS emite (hoje, o extrato de contribuições).

O reportlab so le TrueType estatico: aqui cada peso das fontes do app
(frontend/fontes, woff2 e variaveis) vira um .ttf com nome de familia
proprio, com o recorte latino e o latino estendido juntos - o nome de um
apoiador pode ter letra que o portugues nao usa.

    venv/Scripts/python.exe tools/fontes_pdf.py

Os .ttf ficam em src/fontes_pdf (licenca SIL OFL 1.1, em OFL-*.txt) e vao
dentro do instalador com o resto de src. O IBM Plex Mono tem "Plex" como
nome reservado: convertido, ele passa a se chamar PAULUS Mono.
"""

from __future__ import annotations

import io
from pathlib import Path

from fontTools.merge import Merger
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

RAIZ = Path(__file__).resolve().parent.parent
FONTES = RAIZ / "frontend" / "fontes"
DESTINO = RAIZ / "src" / "fontes_pdf"

# (arquivo do app sem o recorte, peso, nome da familia no PDF)
PECAS = [
    ("EBGaramond-normal-400", 400, "PAULUS Garamond"),
    ("EBGaramond-normal-400", 500, "PAULUS Garamond Medio"),
    ("EBGaramond-italic-400", 400, "PAULUS Garamond Italico"),
    ("Manrope-normal-400", 400, "PAULUS Manrope"),
    ("Manrope-normal-400", 600, "PAULUS Manrope Seminegrito"),
    ("Manrope-normal-400", 700, "PAULUS Manrope Negrito"),
    ("IBMPlexMono-normal-400", 400, "PAULUS Mono"),
    ("IBMPlexMono-normal-500", 500, "PAULUS Mono Medio"),
]


def _estatica(arquivo: Path, peso: int) -> bytes:
    fonte = TTFont(str(arquivo))
    fonte.flavor = None
    if "fvar" in fonte:
        fonte = instantiateVariableFont(fonte, {"wght": peso})
    buf = io.BytesIO()
    fonte.save(buf)
    return buf.getvalue()


def _renomear(fonte: TTFont, familia: str) -> None:
    nomes = fonte["name"]
    postscript = familia.replace(" ", "") + "-Regular"
    for registro in list(nomes.names):
        if registro.nameID in (16, 17, 21, 22, 25):
            nomes.removeNames(nameID=registro.nameID)
    for nid, texto in ((1, familia), (2, "Regular"), (4, familia), (6, postscript), (3, postscript)):
        nomes.setName(texto, nid, 3, 1, 0x409)
        nomes.setName(texto, nid, 1, 0, 0)


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    for base, peso, familia in PECAS:
        pedacos = []
        for recorte in ("latin", "latin-ext"):
            arquivo = FONTES / f"{base}-{recorte}.woff2"
            if arquivo.exists():
                caminho = DESTINO / f"_{recorte}.ttf"
                caminho.write_bytes(_estatica(arquivo, peso))
                pedacos.append(caminho)
        try:
            fonte = Merger().merge([str(p) for p in pedacos]) if len(pedacos) > 1 else TTFont(str(pedacos[0]))
            juntou = len(pedacos) > 1
        except Exception as exc:  # recortes que nao se juntam: fica o latino, que cobre o portugues
            print(f"   {familia}: so o latino ({exc})")
            fonte, juntou = TTFont(str(pedacos[0])), False
        _renomear(fonte, familia)
        destino = DESTINO / (familia.replace(" ", "") + ".ttf")
        fonte.save(str(destino))
        for p in pedacos:
            p.unlink(missing_ok=True)
        print(f"   {destino.name} ({'latino e estendido' if juntou else 'latino'}, {destino.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
