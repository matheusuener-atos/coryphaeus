"""
Testes da porta de entrada de arquivo (src/entrada.py e as três rotas de anexar).

  - acima do limite, o arquivo não é recusado: volta pedindo confirmação, e
    entra quando vem autorizado; acima do teto, é recusado;
  - o conteúdo tem de ser do tipo do nome: um executável chamado .pdf, um ZIP
    qualquer chamado .docx e um binário chamado .txt não entram;
  - nome repetido com outro conteúdo ganha "(2)" em vez de sobrescrever.

O limite e o teto do teste são 1 MB e 3 MB (os de verdade são 50 e 500), para
não criar arquivo de centenas de MB. Tudo numa pasta temporária.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_entrada.py
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-entrada-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
sys.path.insert(0, str(RAIZ / "src"))

import entrada  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def pdf(tamanho: int = 0, texto: str = "Contrato de teste") -> bytes:
    from reportlab.pdfgen import canvas

    saida = io.BytesIO()
    c = canvas.Canvas(saida)
    c.drawString(60, 700, texto)
    c.showPage()
    c.save()
    dados = saida.getvalue()
    # Enche depois do fim: o PDF continua abrindo, e o tamanho e o pedido.
    return dados + b"\n%" + b"0" * max(0, tamanho - len(dados) - 2)


def docx(com_documento: bool = True) -> bytes:
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w") as z:
        z.writestr("word/document.xml" if com_documento else "qualquer.txt", "<w:document/>")
    return saida.getvalue()


def test_regras() -> None:
    print("\nas regras")
    MB = entrada.MB
    checar(entrada.faixa(10 * MB, False)[0] == "entra", "10 MB entra")
    decisao, motivo = entrada.faixa(60 * MB, False)
    checar(decisao == "perguntar" and "60" in motivo, "60 MB pergunta, dizendo o tamanho", motivo)
    checar(entrada.faixa(60 * MB, True)[0] == "entra", "60 MB autorizado entra")
    checar(entrada.faixa(600 * MB, True)[0] == "recusar", "600 MB é recusado mesmo autorizado")
    checar(entrada.conferir_bytes("a.pdf", pdf()) == "", "PDF de verdade passa")
    checar("não é de um PDF" in entrada.conferir_bytes("contrato.pdf", b"MZ\x90\x00" + b"\x00" * 100),
           "executável chamado .pdf é recusado")
    checar(entrada.conferir_bytes("a.docx", docx()) == "", "DOCX de verdade passa")
    checar("não tem um documento do Word" in entrada.conferir_bytes("a.docx", docx(False)), "ZIP qualquer chamado .docx é recusado")
    checar("não é texto" in entrada.conferir_bytes("a.txt", b"abc\x00def"), "binário chamado .txt é recusado")
    checar(entrada.conferir_bytes("a.md", "Título\ncom acentuação".encode("utf-8")) == "", "texto com acento passa")


def test_rotas() -> None:
    print("\npelas rotas")
    from fastapi.testclient import TestClient

    import api

    entrada.LIMITE, entrada.TETO = 1 * entrada.MB, 3 * entrada.MB
    c = TestClient(api.app)
    origem = TMP / "origem"
    origem.mkdir()
    grande = origem / "escaneado grande.pdf"
    grande.write_bytes(pdf(2 * entrada.MB))
    enorme = origem / "enorme.pdf"
    enorme.write_bytes(pdf(4 * entrada.MB))
    falso = origem / "fatura.pdf"
    falso.write_bytes(b"MZ\x90\x00 isto e um programa")

    d = c.post("/api/anexar/caminhos", json={"caminhos": [str(grande), str(enorme), str(falso)]}).json()
    pedem = [x["nome"] for x in d.get("pedem_confirmacao", [])]
    motivos = {x["nome"]: x["motivo"] for x in d.get("recusados", [])}
    checar(pedem == ["escaneado grande.pdf"] and not (Path(api.estado.pasta) / grande.name).exists(),
           "acima do limite: pede confirmação e não copia", d)
    checar("teto" in motivos.get("enorme.pdf", ""), "acima do teto: recusado", motivos)
    checar("não é de um PDF" in motivos.get("fatura.pdf", ""), "executável com nome de PDF: recusado", motivos)
    d = c.post("/api/anexar/caminhos", json={"caminhos": [str(grande)], "autorizados": [str(grande)]}).json()
    checar(d["salvos"] == ["escaneado grande.pdf"], "autorizado, entra", d)

    r = c.post("/api/upload", files=[("arquivos", ("grande pelo navegador.pdf", pdf(2 * entrada.MB), "application/pdf"))])
    checar(r.json()["pedem_confirmacao"] and not r.json()["salvos"], "pelo navegador: pede confirmação", r.json())
    r = c.post("/api/upload", files=[("arquivos", ("grande pelo navegador.pdf", pdf(2 * entrada.MB), "application/pdf"))],
               data={"autorizados": json.dumps(["grande pelo navegador.pdf"])})
    checar(r.json()["salvos"] == ["grande pelo navegador.pdf"], "pelo navegador, autorizado: entra", r.json())

    primeiro = c.post("/api/upload", files=[("arquivos", ("mesmo nome.pdf", pdf(0, "Primeiro"), "application/pdf"))]).json()
    segundo = c.post("/api/upload", files=[("arquivos", ("mesmo nome.pdf", pdf(0, "Segundo"), "application/pdf"))]).json()
    checar(primeiro["salvos"] == ["mesmo nome.pdf"] and segundo["salvos"] and segundo["salvos"][0] != "mesmo nome.pdf",
           "mesmo nome com outro conteúdo não sobrescreve", segundo["salvos"])

    sid = api.estado.servicos.salvar({"nome": "Teste de entrada"})
    d = c.post(f"/api/servicos/{sid}/anexar", json={"caminhos": [str(grande)]}).json()
    checar([x["nome"] for x in d.get("pedem_confirmacao", [])] == [grande.name] and not d["ligados"],
           "no serviço: pede confirmação", d)
    d = c.post(f"/api/servicos/{sid}/anexar", json={"caminhos": [str(grande)], "autorizados": [str(grande)]}).json()
    checar(d["ligados"] == [grande.name], "no serviço, autorizado: entra e liga", d)


def main() -> int:
    print("=" * 55)
    print("  a porta de entrada de arquivo")
    print("=" * 55)
    try:
        test_regras()
        test_rotas()
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
