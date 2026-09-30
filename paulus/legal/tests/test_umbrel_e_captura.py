"""
Ideia E do umbrelOS (docs/DECISAO-UMBREL.md): documento fotografado pelo
celular (src/captura.py).

  - as fotos viram um PDF, uma página por foto, na ordem, com o giro da
    prévia e a orientação do EXIF; foto que não é imagem é recusada;
  - o OCR do Windows lê a foto: página de texto conhecido, girada 2°, com
    ruído e JPEG de celular -> pelo menos 90% das palavras certas (pula fora
    do Windows ou sem o OCR);
  - na janela do escritório, o PDF entra no Acervo; de fora, fica à parte e
    vira pedido em Aprovações, e o sim o põe no Acervo;
  - com a chave desligada, a rota recusa.

As fotos são geradas aqui, não são fotos de verdade: é a limitação da medida
(docs/DECISAO-UMBREL.md).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_umbrel_e_captura.py
"""

from __future__ import annotations

import io
import random
import re
import shutil
import sys
import tempfile
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import captura  # noqa: E402

_falhas: list[str] = []

TEXTO = [
    "PODER JUDICIÁRIO", "TRIBUNAL DE JUSTIÇA DO ESTADO DO PARÁ", "1ª Vara Cível e Empresarial de Santarém",
    "Processo nº 0801234-56.2026.8.14.0051", "INTIMAÇÃO",
    "Fica a parte autora intimada para, no prazo de 15 (quinze) dias,",
    "especificar as provas que pretende produzir, justificando a",
    "pertinência de cada uma, sob pena de preclusão.",
    "A audiência de conciliação fica designada para o dia 12 de novembro",
    "de 2026, às 10 horas, na sala de audiências desta Vara.",
    "Santarém, 29 de setembro de 2026.", "Diretor de Secretaria",
]


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def _fonte(tamanho: int):
    from PIL import ImageFont

    for f in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(f).exists():
            return ImageFont.truetype(f, tamanho)
    return ImageFont.load_default()


def foto_de_celular(linhas, giro: float = 2.0, semente: int = 7, exif_deitada: bool = False) -> bytes:
    """Uma página impressa fotografada: fundo não branco, giro, ruído, JPEG de celular."""
    from PIL import Image, ImageDraw, ImageFilter

    rng = random.Random(semente)
    img = Image.new("RGB", (2100, 2970), (238, 234, 226))
    d = ImageDraw.Draw(img)
    fonte = _fonte(46)
    y = 220
    for linha in linhas:
        d.text((180, y), linha, fill=(28, 28, 30), font=fonte)
        y += 96
    img = img.rotate(giro, expand=True, fillcolor=(120, 118, 110))
    px = img.load()
    for _ in range(90000):
        x, y = rng.randrange(img.width), rng.randrange(img.height)
        v = rng.randrange(-40, 40)
        r, g, b = px[x, y]
        px[x, y] = (max(0, min(255, r + v)), max(0, min(255, g + v)), max(0, min(255, b + v)))
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    saida = io.BytesIO()
    if exif_deitada:
        img = img.rotate(90, expand=True)
        exif = Image.Exif()
        exif[0x0112] = 6   # a câmera guardou "girar 90° para ver direito"
        img.save(saida, format="JPEG", quality=72, exif=exif.tobytes())
    else:
        img.save(saida, format="JPEG", quality=72)
    return saida.getvalue()


def _palavras(t: str) -> list[str]:
    plano = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    return re.findall(r"[a-z0-9]+", plano)


def test_pdf() -> None:
    print("\nas fotos viram um PDF")
    fotos = [foto_de_celular(TEXTO[:6], semente=1), foto_de_celular(TEXTO[6:], semente=2)]
    pdf, paginas = captura.pdf_das_fotos(fotos, [0, 90])
    from pypdf import PdfReader

    leitor = PdfReader(io.BytesIO(pdf))
    checar(paginas == 2 and len(leitor.pages) == 2, "duas fotos, duas páginas", paginas)
    p1, p2 = leitor.pages[0].mediabox, leitor.pages[1].mediabox
    checar(float(p1.height) > float(p1.width) and float(p2.width) > float(p2.height),
           "a página 2, girada 90° na prévia, fica deitada", (p1, p2))
    pdf, _ = captura.pdf_das_fotos([foto_de_celular(TEXTO[:3], exif_deitada=True)])
    caixa = PdfReader(io.BytesIO(pdf)).pages[0].mediabox
    checar(float(caixa.height) > float(caixa.width), "a foto deitada pelo EXIF da câmera volta de pé", caixa)
    for bruto, nome in ((b"%PDF-1.4 nao e foto", "um PDF"), (b"", "vazio"), (b"texto qualquer", "texto")):
        try:
            captura.pdf_das_fotos([bruto])
            checar(False, f"{nome} no lugar da foto é recusado")
        except ValueError as exc:
            checar("não é uma imagem" in str(exc), f"{nome} no lugar da foto é recusado", str(exc))
    checar(captura.nome_do_documento("Intimação / audiência?").startswith("Intimação audiência - "),
           "o nome do documento sem caractere que o Windows não aceita")


def test_ocr() -> None:
    print("\no OCR do Windows lê a foto")
    import ocr_windows

    if not ocr_windows.situacao().get("ok"):
        print("  pulado: sem o OCR do Windows nesta máquina")
        return
    from extract import extract_file

    pasta = Path(tempfile.mkdtemp(prefix="paulus-captura-ocr-"))
    try:
        pdf, _ = captura.pdf_das_fotos([foto_de_celular(TEXTO, giro=2.0, semente=11)])
        alvo = pasta / "foto.pdf"
        alvo.write_bytes(pdf)
        texto, _ = extract_file(alvo)
        esperadas, lidas = _palavras(" ".join(TEXTO)), set(_palavras(texto))
        taxa = sum(1 for w in esperadas if w in lidas) / len(esperadas)
        print(f"       {taxa:.1%} das palavras certas ({len(esperadas)} esperadas)")
        checar(taxa >= 0.90, "foto girada, com ruído e JPEG de celular: pelo menos 90% das palavras", round(taxa, 3))
        checar("0801234-56.2026.8.14.0051" in texto.replace(" ", ""), "o número do processo sai inteiro")
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_destino() -> None:
    print("\nna janela do escritório e de fora")
    pasta = Path(tempfile.mkdtemp(prefix="paulus-captura-"))

    class Fila:
        def __init__(self):
            self.pedidos = []

        def pedir(self, titulo, categoria, **extras):
            from aprovacoes import Pedido

            p = Pedido(id=f"p{len(self.pedidos)}", titulo=titulo, categoria=categoria, **extras)
            self.pedidos.append(p)
            return p

    class Estado:
        def __init__(self):
            self.pasta = pasta / "acervo"
            self.fila = Fila()
            self.recarregados = 0
            self.prefs = type("P", (), {"dados": {"umbrel": {"captura": True}}})()

        def recarregar(self):
            self.recarregados += 1
            return 0

    try:
        e = Estado()
        fotos = [foto_de_celular(TEXTO[:4])]
        r = captura.receber(e, pasta / "dados", None, fotos, [0], "Intimação")
        checar(r["destino"] == "acervo" and (e.pasta / r["nome"]).exists() and e.recarregados == 1,
               "na janela do escritório: o PDF entra no Acervo e é lido", r)
        r = captura.receber(e, pasta / "dados", {"nome": "Dra. Helena", "email": "h@x"}, fotos, [0], "Intimação")
        checar(r["destino"] == "aprovacoes" and len(list(e.pasta.glob("*.pdf"))) == 1,
               "de fora: não entra no Acervo, vira pedido em Aprovações", r)
        pedido = e.fila.pedidos[0]
        checar(pedido.acao == "captura.entrar" and pedido.categoria == "acervo" and "Dra. Helena" in pedido.resumo,
               "o pedido diz quem fotografou e o que o sim faz", pedido.resumo)
        texto = captura.executar(e, pedido)
        checar(len(list(e.pasta.glob("*.pdf"))) == 2 and not Path(pedido.dados["arquivo"]).exists(),
               "o sim põe o PDF no Acervo (e ele sai da pasta de captura)", texto)
        try:
            captura.executar(e, pedido)
            checar(False, "aprovar de novo o que já entrou dá erro, sem duplicar")
        except RuntimeError:
            checar(True, "aprovar de novo o que já entrou dá erro, sem duplicar")
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_rota() -> None:
    print("\npela API")
    from fastapi.testclient import TestClient

    import api

    prefs = dict(api.estado.prefs.dados.get("umbrel") or {})
    try:
        c = TestClient(api.app, headers=api.cabecalho_local())
        api.estado.prefs.dados["umbrel"] = {**prefs, "captura": False}
        r = c.post("/api/captura", files=[("fotos", ("a.jpg", foto_de_celular(TEXTO[:2]), "image/jpeg"))])
        checar(r.status_code == 409, "com a chave desligada, a rota recusa", r.status_code)
        api.estado.prefs.dados["umbrel"] = {**prefs, "captura": True}
        r = c.post("/api/captura", files=[("fotos", ("a.txt", b"nada", "text/plain"))])
        checar(r.status_code == 400 and "imagem" in r.json()["detail"], "foto que não é imagem volta com o motivo")
        import acesso.politicas as pol

        checar(pol.de("POST", "/api/captura") == pol.PERMITIDO and pol.de("POST", "/api/upload") == pol.BLOQUEADO,
               "a captura passa de fora (e ela mesma manda para Aprovações); o envio comum continua bloqueado")
    finally:
        api.estado.prefs.dados["umbrel"] = prefs


def main() -> int:
    print("=" * 55)
    print("  Umbrel E — documento fotografado pelo celular")
    print("=" * 55)
    test_pdf()
    test_ocr()
    test_destino()
    test_rota()
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
