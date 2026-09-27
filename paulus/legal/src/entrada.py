"""
A porta de entrada de arquivo: o tamanho e o tipo, antes de copiar ou ler.

Tamanho, em três faixas:

- até LIMITE (50 MB): entra;
- entre LIMITE e TETO (500 MB): não é recusado - pede confirmação. A tela
  mostra nome e tamanho, e só com "Conheço este arquivo e quero incluí-lo"
  marcado o pedido volta com o arquivo em `autorizados`. A autorização vale
  para aquele arquivo, naquela vez;
- acima do TETO: recusado. Não é regra de segurança: é para a leitura (e o
  OCR de um escaneado de centenas de páginas) não prender a máquina.

Tipo: o conteúdo tem de ser do que o nome diz. Um .exe renomeado para
contrato.pdf não passa: PDF começa com %PDF, DOCX é um pacote ZIP com o
documento do Word dentro, TXT e MD são texto. Isso NÃO é antivírus - a tela não
diz que é. É a garantia de que o que entra é o documento que diz ser, e de que
o que foge do normal só entra com o sim de quem usa.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

MB = 1024 * 1024
LIMITE = 50 * MB
TETO = 500 * MB


def mb(tamanho: int) -> float:
    return round(tamanho / MB, 1)


def faixa(tamanho: int, autorizado: bool) -> tuple[str, str]:
    """("entra" | "perguntar" | "recusar", motivo)."""
    if tamanho > TETO:
        return "recusar", f"tem {mb(tamanho):.0f} MB; o teto do PAULUS é {TETO // MB} MB".replace(".", ",")
    if tamanho > LIMITE and not autorizado:
        return "perguntar", f"tem {mb(tamanho)} MB, acima de {LIMITE // MB} MB".replace(".", ",")
    return "entra", ""


def conferir_tipo(sufixo: str, cabeca: bytes, abrir_zip=None) -> str:
    """
    O motivo de o conteúdo não bater com a extensão, ou "" quando bate.
    `cabeca` são os primeiros bytes (1 KB basta para PDF; 8 KB para texto).
    `abrir_zip` devolve o arquivo como algo que o zipfile lê - para o DOCX.
    """
    sufixo = sufixo.lower()
    if sufixo == ".pdf":
        # A especificação aceita o cabeçalho em qualquer ponto do primeiro KB.
        return "" if b"%PDF-" in cabeca[:1024] else "o nome termina em .pdf, mas o conteúdo não é de um PDF"
    if sufixo == ".docx":
        if not cabeca.startswith(b"PK\x03\x04"):
            return "o nome termina em .docx, mas o conteúdo não é de um documento do Word"
        if abrir_zip is not None:
            try:
                with zipfile.ZipFile(abrir_zip()) as z:
                    if "word/document.xml" not in z.namelist():
                        return "o nome termina em .docx, mas o pacote não tem um documento do Word dentro"
            except zipfile.BadZipFile:
                return "o nome termina em .docx, mas o pacote está quebrado"
        return ""
    if sufixo == ".xlsx":
        if not cabeca.startswith(b"PK\x03\x04"):
            return "o nome termina em .xlsx, mas o conteúdo não é de uma planilha do Excel"
        if abrir_zip is not None:
            try:
                with zipfile.ZipFile(abrir_zip()) as z:
                    if "xl/workbook.xml" not in z.namelist():
                        return "o nome termina em .xlsx, mas o pacote não tem uma planilha dentro"
            except zipfile.BadZipFile:
                return "o nome termina em .xlsx, mas o pacote está quebrado"
        return ""
    if sufixo in (".txt", ".md"):
        return "" if b"\x00" not in cabeca[:8192] else f"o nome termina em {sufixo}, mas o conteúdo não é texto"
    return ""


def conferir_caminho(caminho: Path) -> str:
    with open(caminho, "rb") as f:
        cabeca = f.read(8192)
    return conferir_tipo(caminho.suffix, cabeca, abrir_zip=lambda: open(caminho, "rb"))


def conferir_bytes(nome: str, conteudo: bytes) -> str:
    return conferir_tipo(Path(nome).suffix, conteudo[:8192], abrir_zip=lambda: io.BytesIO(conteudo))
