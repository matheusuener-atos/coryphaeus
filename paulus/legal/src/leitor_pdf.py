"""
Uma porta so para o PDFium.

O PDFium e uma biblioteca em C, e nao e segura para duas threads ao mesmo
tempo. O FastAPI atende rota `def` num pool de threads, entao duas paginas
pedidas juntas caem dentro do PDFium juntas - e foi exatamente o que aconteceu
quando a comparacao de versoes passou a mostrar as duas folhas lado a lado:
dois `<img>` disparados no mesmo instante, e o processo devolveu

    OSError: exception: access violation reading 0x000000000000002C

Nao e um erro que da para tratar: o processo inteiro morre, sem traceback da
aplicacao. E nao aparece em teste de uma requisicao de cada vez, so quando a
tela pede duas.

Entao todo acesso ao PDFium passa por aqui, um de cada vez:

    with leitor_pdf.abrir(caminho_ou_bytes) as doc:
        ...

A trava cobre a vida inteira do documento - abrir, desenhar, procurar, fechar -
porque o perigo nao esta so em abrir: desenhar uma pagina enquanto outra thread
fecha um documento mexe na mesma memoria.

O custo e sequenciar o desenho. Uma folha A4 desenha em dezenas de
milissegundos, e a tela pede no maximo duas por vez; a pessoa nao percebe a
fila. Ja o processo caindo, percebe.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path

# Uma so para o programa inteiro: o PDFium e global ao processo, nao ao
# documento. Uma trava por arquivo nao resolveria nada.
_PORTA = threading.RLock()


@contextmanager
def abrir(origem: Path | str | bytes):
    """
    O documento aberto, com a porta fechada atras.

    Aceita caminho ou os bytes do PDF - a pre-visualizacao gera o PDF na hora e
    nunca chega a ter arquivo.
    """
    import pypdfium2 as pdfium

    with _PORTA:
        doc = pdfium.PdfDocument(origem if isinstance(origem, bytes) else str(origem))
        try:
            yield doc
        finally:
            doc.close()


@contextmanager
def emprestado():
    """
    A porta, sem documento.

    Para o trecho raro que precisa segurar a trava um pouco alem do documento -
    salvar uma imagem que ainda aponta para a memoria do PDFium, por exemplo.
    """
    with _PORTA:
        yield
