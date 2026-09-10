"""
PAULUS Legal - janela desktop.

Sobe o servidor local numa thread e abre uma janela nativa do Windows com a
interface. Sem barra de endereco, sem cara de site: para o usuario e um
programa.

    python src/desktop.py

A janela tambem da acesso ao seletor de pasta do proprio Windows, que o
navegador nao permite - a pasta de destino do organizador deixa de ser um
caminho digitado a mao.
"""

from __future__ import annotations

import socket
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

TITULO = "PAULUS Legal"


class Ponte:
    """Metodos chamados pelo JavaScript da pagina (window.pywebview.api)."""

    def __init__(self) -> None:
        self.janela = None

    def escolher_pasta(self) -> str:
        import webview

        if not self.janela:
            return ""

        # pywebview 6 trocou FOLDER_DIALOG por FileDialog.FOLDER; a constante
        # antiga ainda funciona, mas emite aviso de descontinuada.
        try:
            tipo = webview.FileDialog.FOLDER
        except AttributeError:
            tipo = webview.FOLDER_DIALOG

        escolha = self.janela.create_file_dialog(tipo)
        if not escolha:
            return ""
        return escolha[0] if isinstance(escolha, (list, tuple)) else str(escolha)


def _porta_livre(preferida: int = 8000) -> int:
    """Usa a porta preferida; se estiver ocupada, pede uma qualquer ao sistema."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferida))
            return preferida
        except OSError:
            pass

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _esperar_servidor(porta: int, timeout: float = 30.0) -> bool:
    limite = time.time() + timeout
    while time.time() < limite:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", porta)) == 0:
                return True
        time.sleep(0.2)
    return False


def main() -> int:
    try:
        import webview
    except ImportError:
        print(
            "pywebview nao instalado. Rode:\n"
            "  pip install -r requirements.txt\n\n"
            "Ou use a interface no navegador:\n"
            "  python src/api.py"
        )
        return 1

    import uvicorn

    import api

    porta = _porta_livre()
    api.estado.porta = porta

    servidor = uvicorn.Server(
        uvicorn.Config(api.app, host="127.0.0.1", port=porta, log_level="warning")
    )
    threading.Thread(target=servidor.run, daemon=True).start()

    if not _esperar_servidor(porta):
        print(f"O servidor local nao subiu na porta {porta}.")
        return 1

    ponte = Ponte()
    ponte.janela = webview.create_window(
        TITULO,
        f"http://127.0.0.1:{porta}",
        js_api=ponte,
        width=1280,
        height=860,
        min_size=(900, 620),
    )
    # private_mode=False com storage_path guarda a sessao do navegador embutido
    # numa pasta do proprio programa. E o que faz a tela de Conexoes valer a
    # pena: sem isso, o WhatsApp Web pediria o codigo a cada abertura.
    sessoes = Path(__file__).parent.parent / "data" / "sessoes"
    sessoes.mkdir(parents=True, exist_ok=True)
    webview.start(private_mode=False, storage_path=str(sessoes))

    servidor.should_exit = True
    return 0


if __name__ == "__main__":
    sys.exit(main())
