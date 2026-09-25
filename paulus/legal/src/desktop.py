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
# O "P" do programa (frontend/img/paulus-logo.svg), desenhado de 16 a 256 px.
ICONE = Path(__file__).parent.parent / "frontend" / "img" / "paulus.ico"


# A janela mora aqui fora, e nao dentro da Ponte. O motivo esta na classe.
_JANELA = None

# O identificador da janela no Windows, lido UMA vez, na thread da interface,
# quando ela aparece. Ler `janela.native` de outra thread e o que derrubava o
# programa antes (ver a Ponte), e aqui basta o numero.
_HWND = 0
_MAXIMIZADA = False

# Redimensionar sem moldura: diz-se ao Windows "comece a redimensionar por
# esta borda" e o proprio sistema toma conta do gesto, com o encaixe nas
# laterais e a fluidez de sempre.
#
# A mensagem e WM_SYSCOMMAND e nao WM_NCLBUTTONDOWN, que seria o caminho
# obvio: aquele exige um `ReleaseCapture()` antes, e `ReleaseCapture` so
# solta a captura da THREAD que chama. A chamada vem do JavaScript, que o
# pywebview atende numa thread de trabalho - nao na thread da janela -, e ali
# ele nao solta nada. `WM_SYSCOMMAND` e postado na fila da janela e roda na
# thread certa.
_WM_SYSCOMMAND = 0x0112
_SC_SIZE = 0xF000
_BORDAS = {
    "left": 1, "right": 2, "top": 3, "topleft": 4, "topright": 5,
    "bottom": 6, "bottomleft": 7, "bottomright": 8,
}


def _mandar_para_o_windows(codigo: int) -> bool:
    if not _HWND:
        return False
    from ctypes import windll

    windll.user32.PostMessageW(_HWND, _WM_SYSCOMMAND, _SC_SIZE + codigo, 0)
    return True


class Ponte:
    """
    Metodos chamados pelo JavaScript da pagina (window.pywebview.api).

    **Esta classe so pode ter metodos. Nenhum atributo, nunca.**

    O pywebview monta o objeto `window.pywebview.api` percorrendo `dir()` deste
    objeto e recursando em todo atributo que nao seja funcao. Guardar a janela
    aqui - `self.janela` - fazia o passeio entrar no controle nativo do
    WebView2 e seguir por

        janela.native.AccessibilityObject.Bounds.Empty.Empty.Empty.Empty...

    ate estourar a pilha. A protecao de ciclo do pywebview e por id do objeto,
    e nao pega este caso: `Rectangle.Empty` devolve um objeto NOVO a cada
    acesso, entao o id nunca se repete.

    E o estrago nao parava no erro. Cada passo do passeio lia uma propriedade
    COM do WebView2 de fora da thread da interface - dai a enxurrada de
    "CoreWebView2 can only be accessed from the UI thread" - e a janela
    terminava em "Nao Respondendo". Era o que acontecia em quase toda abertura.
    """

    def escolher_pasta(self) -> str:
        import webview

        if _JANELA is None:
            return ""

        # pywebview 6 trocou FOLDER_DIALOG por FileDialog.FOLDER; a constante
        # antiga ainda funciona, mas emite aviso de descontinuada.
        try:
            tipo = webview.FileDialog.FOLDER
        except AttributeError:
            tipo = webview.FOLDER_DIALOG

        escolha = _JANELA.create_file_dialog(tipo)
        if not escolha:
            return ""
        return escolha[0] if isinstance(escolha, (list, tuple)) else str(escolha)

    def salvar_como(self, nome: str, tipos: list | None = None) -> str:
        """
        O "Salvar como" do Windows. Sem `tipos`, e o de exportar a conversa:
        Markdown vem primeiro na lista, e por isso e o padrao. O audio de uma
        gravacao manda os tipos dele.
        """
        import webview

        if _JANELA is None:
            return ""
        try:
            tipo = webview.FileDialog.SAVE
        except AttributeError:
            tipo = webview.SAVE_DIALOG
        escolha = _JANELA.create_file_dialog(
            tipo, save_filename=nome,
            file_types=tuple(tipos) if tipos else ("Markdown (*.md)", "Texto (*.txt)", "Documento do Word (*.docx)"),
        )
        if not escolha:
            return ""
        return escolha[0] if isinstance(escolha, (list, tuple)) else str(escolha)

    # ------------------------------------------------------------- a janela
    # A moldura do Windows saiu, e com ela os tres botoes do canto e a barra
    # que se arrasta. Estes metodos sao o que a pagina chama no lugar deles.

    def janela_minimizar(self) -> bool:
        if _JANELA is None:
            return False
        _JANELA.minimize()
        return True

    def janela_alternar_tamanho(self) -> bool:
        """Maximiza ou volta ao tamanho de antes. Devolve se ficou maximizada."""
        global _MAXIMIZADA
        if _JANELA is None:
            return False
        if _MAXIMIZADA:
            _JANELA.restore()
        else:
            _JANELA.maximize()
        _MAXIMIZADA = not _MAXIMIZADA
        return _MAXIMIZADA

    def janela_fechar(self) -> bool:
        if _JANELA is None:
            return False
        _JANELA.destroy()
        return True

    def janela_borda(self, qual: str) -> bool:
        """O clique foi numa borda: daqui em diante quem redimensiona e o Windows."""
        codigo = _BORDAS.get(str(qual or "").lower())
        return _mandar_para_o_windows(codigo) if codigo else False

    def janela_maximizada(self) -> bool:
        return _MAXIMIZADA


def _preparar_janela_nativa() -> None:
    """
    O que so da para ajustar com a janela ja criada: o numero dela e o limite
    de quando maximiza.

    **O limite existe porque janela sem moldura maximiza errado.** O Windows
    encaixa a janela normal na area de trabalho - a tela menos a barra de
    tarefas -, mas uma janela sem borda ele estica pela tela inteira, e a
    barra de tarefas some atras dela. Dizer o `MaximizedBounds` devolve o
    comportamento de qualquer outro programa.

    Este e o unico ponto que toca em `janela.native`, e ele roda no evento
    `shown`, de dentro da thread da interface. Ler isso de outra thread e o
    que travava a janela.
    """
    global _HWND
    try:
        nativa = _JANELA.native
        _HWND = int(nativa.Handle.ToInt64())
    except Exception:
        _HWND = 0
        return
    # Os avisos do Windows piscam o botao desta janela na barra de tarefas.
    try:
        import avisos

        avisos.definir_janela(_HWND)
    except Exception:  # noqa: BLE001 - sem isso so a notificacao sai, sem piscar
        pass
    try:
        from System.Windows.Forms import Screen

        nativa.MaximizedBounds = Screen.FromControl(nativa).WorkingArea
    except Exception:
        # Sem isso a janela maximiza por cima da barra de tarefas; nao e
        # motivo para nao abrir.
        pass


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


def _identidade_no_windows() -> None:
    """
    O programa aparece como ele mesmo na barra de tarefas, e nao como Python.

    Quem roda e o python.exe, e o Windows agrupa a janela pelo executavel:
    sem uma identidade propria, a barra mostra o icone do Python mesmo com o
    icone da janela trocado. Tem de ser dito antes de a janela existir.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Coryphaeus.PaulusLegal")
    except Exception:  # noqa: BLE001 - sem isso o programa abre igual, so com o icone do Python
        pass


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

    global _JANELA
    _identidade_no_windows()
    # Sem moldura: os tres botoes e a barra de titulo passam a ser da propria
    # pagina. `easy_drag=False` porque quem decide onde se arrasta e ela - com
    # ele ligado, a janela inteira vira area de arraste e selecionar texto
    # move a janela.
    _JANELA = webview.create_window(
        TITULO,
        f"http://127.0.0.1:{porta}",
        js_api=Ponte(),
        width=1280,
        height=860,
        min_size=(900, 620),
        frameless=True,
        easy_drag=False,
    )
    _JANELA.events.shown += _preparar_janela_nativa

    # Arrastar a janela e do proprio pywebview: a pagina marca com a classe
    # `pywebview-drag-region` o que pode ser agarrado. `DIRECT_TARGET_ONLY`
    # exige que o clique seja NAQUELE elemento e nao num filho dele - sem
    # isso, apertar qualquer botao do cabecalho e mexer o mouse dois pixels
    # arrastaria a janela junto.
    webview.settings['DRAG_REGION_DIRECT_TARGET_ONLY'] = True
    # Sem isto, todo download por link (Exportar PDF, DOCX, XLSX, o relatorio
    # do Financeiro) era cancelado em silencio na janela do programa. Ligado,
    # o proprio pywebview abre o "Salvar como" do Windows.
    webview.settings['ALLOW_DOWNLOADS'] = True
    # private_mode=False com storage_path guarda a sessao do navegador embutido
    # numa pasta do proprio programa. E o que faz a tela de Conexoes valer a
    # pena: sem isso, o WhatsApp Web pediria o codigo a cada abertura.
    sessoes = Path(__file__).parent.parent / "data" / "sessoes"
    sessoes.mkdir(parents=True, exist_ok=True)
    webview.start(private_mode=False, storage_path=str(sessoes),
                  icon=str(ICONE) if ICONE.exists() else None)

    servidor.should_exit = True
    return 0


if __name__ == "__main__":
    sys.exit(main())
