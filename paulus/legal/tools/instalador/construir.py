"""
Constrói o instalador do PAULUS para Windows.

    venv\\Scripts\\python.exe tools\\instalador\\construir.py

O que sai, em tools\\instalador\\_construcao\\:

- PAULUS\\ - o programa pronto para rodar, sem depender de nada instalado:
  - python\\  o Python "embutível" oficial (python.org), da mesma versão deste
    venv, com as dependências do requirements.txt dentro e as bibliotecas do
    C++ que elas usam (copiadas do Windows desta máquina: a Microsoft permite
    levá-las junto do programa);
  - app\\     o código: src, frontend, habilidades, config, word, oauth_app.json;
  - PAULUS.exe o lançador (Lancador.cs, compilado com o csc.exe que já vem no
    Windows).
- PAULUS-<versão>-instalador.exe - o instalador (Instalador.cs, compilado com o
  mesmo csc.exe), com o programa em .7z e o 7zr.exe (7-Zip, LGPL) emendados no
  fim. O mesmo programa, sem o que foi emendado, vira o Desinstalar.exe.

Custo: zero. Nada é assinado digitalmente - o Windows mostra "editor
desconhecido" na primeira vez (SmartScreen). Assinar pede certificado de
código, que é pago.
"""

from __future__ import annotations

import shutil
import struct
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent                      # paulus/legal
CONSTRUCAO = AQUI / "_construcao"
CACHE = CONSTRUCAO / "cache"
PRONTO = CONSTRUCAO / "PAULUS"

sys.path.insert(0, str(RAIZ / "src"))
from versao import VERSAO  # noqa: E402

# O que vai do código. Testes, ferramentas, dados e o venv ficam de fora.
# W1: `word` é o painel, o manifesto e os ícones do PAVLVS no Word
# (src/word_suplemento.py serve de app/word). A prova da W0 (word/prova) fica.
PASTAS_DO_APP = ["src", "frontend", "habilidades", "config", "word"]
ARQUIVOS_DO_APP = ["oauth_app.json", "LICENSE", "requirements.txt"]
DOCS_DO_APP = ["NOVIDADES.md"]
# As bibliotecas do C++ que numpy, ctranslate2 e onnxruntime usam. O Python
# embutível traz só vcruntime140; o resto vem daqui, "app-local".
DLLS_DO_CPP = ["msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll", "vcruntime140.dll", "vcruntime140_1.dll", "concrt140.dll"]
IGNORAR = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", "prova")
CSC = Path("C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe")
# O 7-Zip de linha de comando, oficial (LGPL): comprime aqui e extrai na
# maquina de quem instala. O .7z sai uns 40% menor que um .zip.
URL_7ZR = "https://www.7-zip.org/a/7zr.exe"
# O rodape do instalador (Instalador.cs, classe Pacote): cinco inteiros de 8
# bytes - stub, 7zr.exe, .7z, tamanho instalado - e a marca.
MARCA = b"PAULUS02"


def passo(texto: str) -> None:
    print(f"\n== {texto}", flush=True)


def baixar(url: str, destino: Path) -> Path:
    if destino.exists() and destino.stat().st_size > 0:
        print(f"   já baixado: {destino.name}")
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    print(f"   baixando {url}")
    with urllib.request.urlopen(url, timeout=120) as r, open(destino.with_suffix(".parcial"), "wb") as f:
        shutil.copyfileobj(r, f)
    destino.with_suffix(".parcial").replace(destino)
    return destino


def python_embutivel() -> None:
    passo("Python embutível")
    v = sys.version_info
    versao = f"{v.major}.{v.minor}.{v.micro}"
    zipado = baixar(f"https://www.python.org/ftp/python/{versao}/python-{versao}-embed-amd64.zip",
                    CACHE / f"python-{versao}-embed-amd64.zip")
    destino = PRONTO / "python"
    with zipfile.ZipFile(zipado) as z:
        z.extractall(destino)
    # O ._pth decide o sys.path do embutível: sem "import site" e sem a pasta
    # site-packages, as dependências não seriam achadas.
    pth = next(destino.glob("python*._pth"))
    linhas = [l for l in pth.read_text(encoding="utf-8").splitlines() if l.strip() and not l.lstrip().startswith("#")]
    linhas += ["Lib\\site-packages", "import site"]
    pth.write_text("\n".join(dict.fromkeys(linhas)) + "\n", encoding="utf-8")
    print(f"   Python {versao} em {destino}")


def dependencias() -> None:
    passo("Dependências (requirements.txt)")
    alvo = PRONTO / "python" / "Lib" / "site-packages"
    alvo.mkdir(parents=True, exist_ok=True)
    # O pip deste venv instala para a mesma versão do Python (mesmas rodas
    # cp3xx-win_amd64), só que dentro do embutível.
    subprocess.run([sys.executable, "-m", "pip", "install", "--target", str(alvo), "-r", str(RAIZ / "requirements.txt"),
                    "--no-warn-script-location", "--disable-pip-version-check", "--quiet"], check=True)
    # Os .exe de linha de comando das dependências não servem ao programa.
    lixo = alvo / "bin"
    if lixo.exists():
        shutil.rmtree(lixo, ignore_errors=True)
    tamanho = sum(f.stat().st_size for f in alvo.rglob("*") if f.is_file()) / 1e6
    print(f"   {tamanho:.0f} MB de dependências")


def bibliotecas_do_cpp() -> None:
    passo("Bibliotecas do C++")
    sistema = Path("C:/Windows/System32")
    for nome in DLLS_DO_CPP:
        origem = sistema / nome
        destino = PRONTO / "python" / nome
        if origem.exists() and not destino.exists():
            shutil.copy2(origem, destino)
            print(f"   {nome}")


def codigo() -> None:
    passo("Código do PAULUS")
    app = PRONTO / "app"
    for pasta in PASTAS_DO_APP:
        shutil.copytree(RAIZ / pasta, app / pasta, ignore=IGNORAR, dirs_exist_ok=True)
    for nome in ARQUIVOS_DO_APP:
        if (RAIZ / nome).exists():
            shutil.copy2(RAIZ / nome, app / nome)
    (app / "docs").mkdir(exist_ok=True)
    for nome in DOCS_DO_APP:
        shutil.copy2(RAIZ / "docs" / nome, app / "docs" / nome)


def csc() -> Path:
    if not CSC.exists():
        raise SystemExit("não achei o csc.exe do .NET Framework 4 - ele vem com o Windows 10 e 11")
    return CSC


def lancador() -> None:
    passo("Lançador (PAULUS.exe)")
    icone = RAIZ / "frontend" / "img" / "paulus.ico"
    subprocess.run([str(csc()), "/nologo", "/target:winexe", "/optimize+", f"/win32icon:{icone}",
                    "/reference:System.Windows.Forms.dll", f"/out:{PRONTO / 'PAULUS.exe'}", str(AQUI / "Lancador.cs")],
                   check=True)


def conferir() -> None:
    """Abre o Python embutível e importa o que o programa usa - antes de empacotar, e não na máquina do cliente."""
    passo("Conferindo o Python embutível")
    python = PRONTO / "python" / "python.exe"
    teste = ("import sys; sys.path.insert(0, r'" + str(PRONTO / "app" / "src") + "'); "
             "import numpy, ctranslate2, faster_whisper, onnxruntime, webview, fastapi, uvicorn, pypdfium2, pypdf, docx, "
             "openpyxl, reportlab, pyhanko, cryptography, psutil, PIL, winrt.windows.media.ocr; "
             "import extract, search, ocr_windows; print('ok', sys.version.split()[0], ocr_windows.situacao().get('idioma'))")
    r = subprocess.run([str(python), "-c", teste], capture_output=True, text=True)
    print("   " + (r.stdout.strip() or r.stderr.strip()[-600:]))
    if r.returncode != 0:
        raise SystemExit("o Python embutível não abriu as dependências - veja o erro acima")


def instalador() -> None:
    passo("Instalador")
    z7 = baixar(URL_7ZR, CACHE / "7zr.exe")
    pacote = CACHE / "paulus.7z"
    pacote.unlink(missing_ok=True)
    print("   comprimindo o programa (7-Zip, uns minutos)…", flush=True)
    subprocess.run([str(z7), "a", "-t7z", "-mx=9", "-mmt=on", "-bso0", "-bsp0", str(pacote), "*"], cwd=PRONTO, check=True)
    instalado = sum(f.stat().st_size for f in PRONTO.rglob("*") if f.is_file())

    versao_cs = CACHE / "Versao.cs"
    versao_cs.write_text(f'static class Versao {{ public const string Numero = "{VERSAO}"; }}\n', encoding="utf-8")
    base = CACHE / "instalador-base.exe"
    fontes = sorted((AQUI / "fontes").glob("*.ttf"))
    if not fontes:
        raise SystemExit("faltam as fontes do instalador: rode tools/instalador/fontes/gerar.py")
    icone = RAIZ / "frontend" / "img" / "paulus.ico"
    subprocess.run([str(csc()), "/nologo", "/target:winexe", "/platform:x64", "/optimize+", f"/win32icon:{icone}",
                    f"/win32manifest:{AQUI / 'Instalador.manifest'}",
                    "/reference:System.Windows.Forms.dll", "/reference:System.Drawing.dll",
                    *[f"/resource:{f},{f.name}" for f in fontes],
                    f"/out:{base}", str(AQUI / "Instalador.cs"), str(versao_cs)], check=True)

    saida = CONSTRUCAO / f"PAULUS-{VERSAO}-instalador.exe"
    partes = [base.read_bytes(), z7.read_bytes()]
    with open(saida, "wb") as f:
        for parte in partes:
            f.write(parte)
        with open(pacote, "rb") as p7:
            shutil.copyfileobj(p7, f)
        f.write(struct.pack("<qqqq", len(partes[0]), len(partes[1]), pacote.stat().st_size, instalado) + MARCA)
    print(f"   {saida} ({saida.stat().st_size / 1e6:.0f} MB; instalado, {instalado / 1e6:.0f} MB)")


def main() -> int:
    print(f"PAULUS {VERSAO} - construindo em {CONSTRUCAO}")
    if "--so-instalador" in sys.argv:
        # A pasta PAULUS\ ja montada; so o codigo e o instalador de novo.
        if not (PRONTO / "python").exists():
            raise SystemExit("não há pasta montada: rode sem --so-instalador primeiro")
        shutil.rmtree(PRONTO / "app", ignore_errors=True)
        codigo()
        lancador()
        conferir()
        instalador()
        print("\npronto")
        return 0
    if PRONTO.exists():
        shutil.rmtree(PRONTO)
    PRONTO.mkdir(parents=True)
    python_embutivel()
    dependencias()
    bibliotecas_do_cpp()
    codigo()
    lancador()
    conferir()
    if "--sem-instalador" not in sys.argv:
        instalador()
    print("\npronto")
    return 0


if __name__ == "__main__":
    sys.exit(main())
