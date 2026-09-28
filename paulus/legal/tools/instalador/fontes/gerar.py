"""
As fontes do instalador, tiradas das do app (frontend/fontes).

O instalador desenha com o GDI+ do Windows, que nao le woff2 nem fonte
variavel: aqui cada peso vira um .ttf estatico, com o nome de familia
proprio (senao dois pesos da mesma familia se atropelam no GDI+). So o
recorte latino - cobre o portugues inteiro.

    venv/Scripts/python.exe tools/instalador/fontes/gerar.py

Os .ttf ficam no repositorio (licenca SIL OFL 1.1, em OFL-*.txt) e vao
dentro do instalador.
"""

from __future__ import annotations

import io
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

AQUI = Path(__file__).resolve().parent
FONTES = AQUI.parent.parent.parent / "frontend" / "fontes"

# (arquivo do app, peso, nome da familia no instalador)
PECAS = [
    ("EBGaramond-normal-400-latin.woff2", 400, "PAULUS Garamond"),
    ("EBGaramond-normal-400-latin.woff2", 500, "PAULUS Garamond Medio"),
    ("Manrope-normal-400-latin.woff2", 400, "PAULUS Manrope"),
    ("Manrope-normal-400-latin.woff2", 500, "PAULUS Manrope Medio"),
    ("Manrope-normal-400-latin.woff2", 600, "PAULUS Manrope Seminegrito"),
]


def renomear(fonte: TTFont, familia: str) -> None:
    nomes = fonte["name"]
    postscript = familia.replace(" ", "") + "-Regular"
    for registro in list(nomes.names):
        if registro.nameID in (16, 17, 21, 22, 25):
            nomes.removeNames(nameID=registro.nameID)
    for nid, texto in ((1, familia), (2, "Regular"), (4, familia), (6, postscript), (3, postscript)):
        nomes.setName(texto, nid, 3, 1, 0x409)
        nomes.setName(texto, nid, 1, 0, 0)
    fonte["OS/2"].usWeightClass = 400
    fonte["OS/2"].fsSelection = (fonte["OS/2"].fsSelection & ~0b1100001) | 0b1000000  # REGULAR
    fonte["head"].macStyle = 0


def main() -> None:
    for arquivo, peso, familia in PECAS:
        fonte = TTFont(str(FONTES / arquivo))
        fonte.flavor = None
        if "fvar" in fonte:
            fonte = instantiateVariableFont(fonte, {"wght": peso})
        renomear(fonte, familia)
        destino = AQUI / (familia.replace(" ", "") + ".ttf")
        buf = io.BytesIO()
        fonte.save(buf)
        destino.write_bytes(buf.getvalue())
        print(f"  {destino.name}  {len(buf.getvalue()) // 1024} KB")


if __name__ == "__main__":
    main()
