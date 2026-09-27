"""
As imagens do instalador, desenhadas em HTML com as cores e as letras do app
e fotografadas pelo Edge sem janela, em 100, 150 e 200% (o Inno Setup escolhe
a que casa com a escala da tela):

    venv/Scripts/python.exe tools/instalador/arte/desenhar.py

Gera lateral-*.png (o painel da esquerda) e icone-*.png / icone-escuro-*.png (o
logo no canto das páginas, no tema claro e no escuro). Os PNG ficam no
repositório; rode de novo só se mudar o desenho.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
EDGE = [
    Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
    Path(os.environ.get("ProgramFiles", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
]
PECAS = [("lateral", 164, 314), ("icone", 58, 58), ("icone-escuro", 58, 58)]
ESCALAS = [(100, 1.0), (150, 1.5), (200, 2.0)]


def main() -> int:
    edge = next((e for e in EDGE if e.exists()), None)
    if not edge:
        print("não achei o Edge")
        return 1
    from PIL import Image

    for nome, largura, altura in PECAS:
        for rotulo, escala in ESCALAS:
            destino = AQUI / f"{nome}-{rotulo}.png"
            for _tentativa in range(3):  # às vezes o Edge sai sem gravar a foto
                with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as perfil:
                    subprocess.run([
                        str(edge), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        f"--user-data-dir={perfil}", f"--window-size={largura},{altura}",
                        f"--force-device-scale-factor={escala}", "--default-background-color=00000000",
                        "--virtual-time-budget=2000", f"--screenshot={destino}", (AQUI / f"{nome}.html").as_uri(),
                    ], check=True, capture_output=True, timeout=60)
                for _ in range(30):
                    if destino.exists():
                        break
                    time.sleep(0.1)
                if destino.exists():
                    break
            im = Image.open(destino)
            esperado = (round(largura * escala), round(altura * escala))
            if im.size != esperado:
                im.crop((0, 0) + esperado).save(destino)
            print(f"  {destino.name} {Image.open(destino).size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
