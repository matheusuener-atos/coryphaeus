"""
Testes do PDF escaneado (src/ocr_windows.py e extract): o texto que está na imagem.

  - o leitor de imagem do Windows responde, em português;
  - um PDF só de imagem vira texto, com as páginas marcadas como lidas da
    imagem; num PDF misto, só a página escaneada vai para o OCR;
  - o motivo certo quando não dá: arquivo vazio (era "PDF escaneado?" para
    um download que não terminou), arquivo quebrado, página em branco;
  - pela API: anexar no serviço recusa o vazio sem copiar e liga o
    escaneado; o Acervo mostra que o texto veio da imagem.

Os dados vão para uma pasta temporária (PAULUS_DADOS): nada toca no acervo
de verdade.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_ocr.py
"""

from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-ocr-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
sys.path.insert(0, str(RAIZ / "src"))

import extract  # noqa: E402
import ocr_windows as ocr  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


PAGINAS = [
    ["CONTRATO DE LOCAÇÃO COMERCIAL", "O aluguel mensal é de R$ 3.200,00, pago até o dia cinco de cada mês.",
     "A multa por atraso é de dois por cento sobre o valor devido."],
    ["CLÁUSULA DA RESCISÃO", "Qualquer parte pode rescindir com aviso prévio de trinta dias, por escrito.",
     "Fica eleito o foro da comarca de Marabá para as questões deste contrato."],
]


def pdf_de_texto(paginas) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    saida = io.BytesIO()
    c = canvas.Canvas(saida, pagesize=A4)
    for linhas in paginas:
        y = 790
        for linha in linhas:
            c.setFont("Helvetica", 12)
            c.drawString(60, y, linha)
            y -= 22
        c.showPage()
    c.save()
    return saida.getvalue()


def escaneado(pdf: bytes, so_paginas=None) -> bytes:
    """Cada página vira imagem (como um scanner); com `so_paginas`, as outras ficam com texto."""
    import pypdfium2 as pdfium
    from PIL import Image
    from pypdf import PdfReader, PdfWriter

    doc = pdfium.PdfDocument(pdf)
    imagens = []
    for i, p in enumerate(doc):
        img = p.render(scale=200 / 72).to_pil().convert("L").rotate(0.6, fillcolor=255, resample=Image.BICUBIC)
        imagens.append(img)
    feito = io.BytesIO()
    imagens[0].save(feito, "PDF", save_all=True, append_images=imagens[1:], resolution=200)
    if so_paginas is None:
        return feito.getvalue()
    original, imagem, saida = PdfReader(io.BytesIO(pdf)), PdfReader(feito), PdfWriter()
    for i in range(len(original.pages)):
        saida.add_page(imagem.pages[i] if i + 1 in so_paginas else original.pages[i])
    buf = io.BytesIO()
    saida.write(buf)
    return buf.getvalue()


def em_branco() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("L", (1654, 2339), 255).save(buf, "PDF", resolution=200)
    return buf.getvalue()


def test_leitor() -> None:
    print("\no leitor de imagem do Windows")
    s = ocr.situacao()
    checar(s["ok"] and s["idioma"].startswith("pt"), "responde, em português", s)


def test_extrair() -> None:
    print("\nPDF escaneado vira texto")
    alvo = TMP / "escaneado.pdf"
    alvo.write_bytes(escaneado(pdf_de_texto(PAGINAS)))
    checar(extract.extract_pdf_info.__name__ and not "".join(extract.extract_file(alvo)[0].split()) == "", "sai texto")
    texto, paginas, lidas = extract.extract_pdf_info(alvo)
    plano = " ".join(texto.split())
    checar(paginas == 2 and lidas == 2, "as duas páginas lidas da imagem", (paginas, lidas))
    for trecho in ("3.200,00", "trinta dias", "Marabá", "[pagina 2]"):
        checar(trecho in plano, f"acha “{trecho}”", plano[:200])
    misto = TMP / "misto.pdf"
    misto.write_bytes(escaneado(pdf_de_texto(PAGINAS), so_paginas={2}))
    texto, paginas, lidas = extract.extract_pdf_info(misto)
    checar(lidas == 1 and "3.200,00" in texto and "Marabá" in texto, "PDF misto: só a página escaneada vai ao OCR", lidas)
    digitado = TMP / "digitado.pdf"
    digitado.write_bytes(pdf_de_texto(PAGINAS))
    checar(extract.extract_pdf_info(digitado)[2] == 0, "PDF digitado não passa pelo OCR")


def test_motivos() -> None:
    print("\no motivo certo quando não dá")
    vazio = TMP / "vazio.pdf"
    vazio.write_bytes(b"")
    checar("vazio (0 bytes)" in extract.motivo_sem_texto(vazio), "arquivo vazio: diz que está vazio, não que é escaneado")
    quebrado = TMP / "quebrado.pdf"
    quebrado.write_bytes(b"%PDF-1.4 isto nao e um pdf")
    checar("não consegui abrir" in extract.motivo_sem_texto(quebrado), "arquivo quebrado: diz que não abriu",
           extract.motivo_sem_texto(quebrado))
    branco = TMP / "branco.pdf"
    branco.write_bytes(em_branco())
    checar("não achou texto" in extract.motivo_sem_texto(branco), "página em branco: diz que não achou letra",
           extract.motivo_sem_texto(branco))
    bom = TMP / "escaneado.pdf"
    checar(extract.motivo_sem_texto(bom) == "", "escaneado legível: sem motivo")


def test_api() -> None:
    print("\npela API")
    from fastapi.testclient import TestClient

    import api

    c = TestClient(api.app, headers=api.cabecalho_local())
    sid = api.estado.servicos.salvar({"nome": "Teste de OCR"})
    vazio, bom = TMP / "download-que-falhou.pdf", TMP / "procuracao escaneada.pdf"
    vazio.write_bytes(b"")
    bom.write_bytes(escaneado(pdf_de_texto(PAGINAS)))
    r = c.post(f"/api/servicos/{sid}/anexar", json={"caminhos": [str(vazio), str(bom)]})
    d = r.json()
    checar(r.status_code == 200, "anexar responde", r.text[:200])
    motivo = next((x["motivo"] for x in d.get("recusados", []) if x["nome"] == vazio.name), "")
    checar("vazio (0 bytes)" in motivo, "o vazio volta com o motivo certo", d.get("recusados"))
    pasta = Path(d.get("pasta", ""))
    checar(not (pasta / vazio.name).exists(), "e não é copiado para a pasta do serviço")
    checar(bom.name in d.get("ligados", []), "o escaneado é lido e ligado ao serviço", d.get("ligados"))
    itens = c.get("/api/biblioteca").json()
    lista = itens.get("itens") or itens.get("documentos") or []
    achado = next((x for x in lista if x.get("nome") == bom.name), {})
    checar(achado.get("ocr") == 2, "o Acervo marca as páginas lidas da imagem", {k: achado.get(k) for k in ("nome", "ocr", "paginas")})


def main() -> int:
    print("=" * 55)
    print("  PDF escaneado")
    print("=" * 55)
    try:
        test_leitor()
        if not ocr.situacao()["ok"]:
            print("  (sem leitor de imagem nesta máquina: o resto não se aplica)")
        else:
            test_extrair()
            test_motivos()
            test_api()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
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
