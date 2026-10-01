"""Capturas da maquete da W0: cada estado em cada tema e largura, a faixa e o
menu do botão direito, mais uma folha com todos os estados por tema.

Uso: python capturar_maquete.py <pasta-saida>
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

AQUI = Path(__file__).resolve().parent
URL = (AQUI / "maquete.html").as_uri()
TEMAS = ("claro", "colorido", "escuro")
LARGURAS = (320, 480)


def main(saida: Path) -> None:
    saida.mkdir(parents=True, exist_ok=True)
    erros: list[str] = []
    with sync_playwright() as p:
        nav = p.chromium.launch(channel="msedge")
        pag = nav.new_page(viewport={"width": 1400, "height": 900}, device_scale_factor=1)
        pag.on("pageerror", lambda e: erros.append(str(e)))
        pag.goto(URL)
        estados = pag.evaluate("ORDEM")
        n = 0
        for tema in TEMAS:
            for larg in LARGURAS:
                for estado in estados:
                    pag.goto(f"{URL}?estado={estado}&larg={larg}&tema={tema}")
                    pag.wait_for_timeout(60)
                    pag.locator("#pt").screenshot(path=str(saida / f"{tema}-{larg}-{estado}.png"))
                    n += 1
            pag.goto(f"{URL}?estado=inicio&larg=320&tema={tema}")
            pag.locator("#faixa").screenshot(path=str(saida / f"faixa-{tema}.png"))
            pag.locator("#ctx").screenshot(path=str(saida / f"menu-{tema}.png"))
            pag.goto(f"{URL}?estado=lei&larg=480&tema={tema}")
            pag.locator("#sec-word").screenshot(path=str(saida / f"word-{tema}.png"))
            for larg in LARGURAS:
                pag.set_viewport_size({"width": 2600 if larg == 320 else 3000, "height": 900})
                pag.goto(f"{URL}?tudo=1&larg={larg}&tema={tema}")
                pag.locator("#grade").screenshot(path=str(saida / f"todos-{tema}-{larg}.png"))
                pag.set_viewport_size({"width": 1400, "height": 900})
        nav.close()
    print(f"{n} capturas de estado; erros de página: {erros or 'nenhum'}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
