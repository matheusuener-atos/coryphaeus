"""
Imprimir sem sair do programa.

O botao Imprimir abria o PDF numa janela do navegador e dali a pessoa ia ao
dialogo do Chromium - outro visual, outra letra, e um passo a mais. Aqui a
tela do PAULUS escolhe impressora, copias, paginas, cor e frente e verso, e o
PDF vai direto para o spooler do Windows.

Sem dependencia nova: as paginas saem desenhadas pelo PDFium (o mesmo que a
pre-visualizacao usa), e a conversa com a impressora e a API do Windows por
ctypes - EnumPrinters para listar, CreateDC/StartDoc para imprimir. A folha
sai em tamanho real (A4 a 100%), e nao "ajustada a pagina": a margem de
2,5 cm tem de continuar 2,5 cm no papel.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

# Resolucao em que a pagina e desenhada antes de ir para a impressora. A
# impressora estica para a dela; 300 dpi e texto nitido sem 100 MB por folha.
DPI_DO_DESENHO = 300

PRINTER_ENUM_LOCAL = 0x2
PRINTER_ENUM_CONNECTIONS = 0x4
PRINTER_ATTRIBUTE_NETWORK = 0x10

LOGPIXELSX, LOGPIXELSY = 88, 90
PHYSICALOFFSETX, PHYSICALOFFSETY = 112, 113

DM_OUT_BUFFER, DM_IN_BUFFER = 2, 8
DM_COPIES, DM_COLOR, DM_DUPLEX = 0x100, 0x800, 0x1000
DMCOLOR_MONOCHROME, DMCOLOR_COLOR = 1, 2
DMDUP_SIMPLEX, DMDUP_VERTICAL = 1, 2


class ErroDeImpressao(Exception):
    """Mensagem ja em portugues, para a tela mostrar como veio."""


def disponivel() -> bool:
    return sys.platform == "win32"


class _PrinterInfo4(ctypes.Structure):
    _fields_ = [("pPrinterName", wintypes.LPWSTR), ("pServerName", wintypes.LPWSTR),
                ("Attributes", wintypes.DWORD)]


class _DocInfo(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_int), ("lpszDocName", wintypes.LPCWSTR),
                ("lpszOutput", wintypes.LPCWSTR), ("lpszDatatype", wintypes.LPCWSTR),
                ("fwType", wintypes.DWORD)]


class _DevMode(ctypes.Structure):
    """So o comeco do DEVMODEW - o que se muda aqui. O resto do buffer (e o
    pedaco do driver) fica como o driver entregou."""
    _fields_ = [("dmDeviceName", ctypes.c_wchar * 32), ("dmSpecVersion", wintypes.WORD),
                ("dmDriverVersion", wintypes.WORD), ("dmSize", wintypes.WORD),
                ("dmDriverExtra", wintypes.WORD), ("dmFields", wintypes.DWORD),
                ("dmOrientation", ctypes.c_short), ("dmPaperSize", ctypes.c_short),
                ("dmPaperLength", ctypes.c_short), ("dmPaperWidth", ctypes.c_short),
                ("dmScale", ctypes.c_short), ("dmCopies", ctypes.c_short),
                ("dmDefaultSource", ctypes.c_short), ("dmPrintQuality", ctypes.c_short),
                ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short)]


def _winspool():
    w = ctypes.WinDLL("winspool.drv", use_last_error=True)
    w.EnumPrintersW.argtypes = [wintypes.DWORD, wintypes.LPWSTR, wintypes.DWORD, ctypes.c_void_p,
                                wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)]
    w.GetDefaultPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    w.OpenPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.HANDLE), ctypes.c_void_p]
    w.ClosePrinter.argtypes = [wintypes.HANDLE]
    w.DocumentPropertiesW.argtypes = [wintypes.HWND, wintypes.HANDLE, wintypes.LPWSTR,
                                      ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
    w.DocumentPropertiesW.restype = ctypes.c_long
    return w


def _gdi():
    g = ctypes.WinDLL("gdi32", use_last_error=True)
    g.CreateDCW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p]
    g.CreateDCW.restype = wintypes.HDC
    g.DeleteDC.argtypes = [wintypes.HDC]
    g.GetDeviceCaps.argtypes = [wintypes.HDC, ctypes.c_int]
    g.StartDocW.argtypes = [wintypes.HDC, ctypes.POINTER(_DocInfo)]
    for nome in ("StartPage", "EndPage", "EndDoc", "AbortDoc"):
        getattr(g, nome).argtypes = [wintypes.HDC]
    return g


def padrao() -> str:
    if not disponivel():
        return ""
    w = _winspool()
    tamanho = wintypes.DWORD(0)
    w.GetDefaultPrinterW(None, ctypes.byref(tamanho))
    if not tamanho.value:
        return ""
    buffer = ctypes.create_unicode_buffer(tamanho.value)
    return buffer.value if w.GetDefaultPrinterW(buffer, ctypes.byref(tamanho)) else ""


def listar() -> list[dict]:
    """As impressoras desta conta do Windows, a padrao primeiro."""
    if not disponivel():
        return []
    w = _winspool()
    flags = PRINTER_ENUM_LOCAL | PRINTER_ENUM_CONNECTIONS
    precisa, quantas = wintypes.DWORD(0), wintypes.DWORD(0)
    w.EnumPrintersW(flags, None, 4, None, 0, ctypes.byref(precisa), ctypes.byref(quantas))
    if not precisa.value:
        return []
    buffer = ctypes.create_string_buffer(precisa.value)
    if not w.EnumPrintersW(flags, None, 4, buffer, precisa, ctypes.byref(precisa), ctypes.byref(quantas)):
        return []
    itens = ctypes.cast(buffer, ctypes.POINTER(_PrinterInfo4 * quantas.value)).contents
    escolhida = padrao()
    lista = [{
        "nome": i.pPrinterName,
        "padrao": i.pPrinterName == escolhida,
        "rede": bool(i.Attributes & PRINTER_ATTRIBUTE_NETWORK) or bool(i.pServerName),
        # Impressora que vira arquivo: a tela avisa que vai pedir onde salvar.
        "arquivo": any(x in i.pPrinterName.lower() for x in ("pdf", "xps", "onenote", "fax")),
    } for i in itens]
    return sorted(lista, key=lambda x: (not x["padrao"], x["arquivo"], x["nome"].lower()))


def paginas_pedidas(texto: str, total: int) -> list[int]:
    """
    "todas", "3" ou "1-3, 7" viram a lista de paginas (a partir de 1).

    Fora do documento e erro, e nao silencio: pedir a pagina 9 de um documento
    de 5 e engano de quem digitou, e imprimir so ate a 5 esconderia isso.
    """
    texto = (texto or "").strip().lower()
    if texto in ("", "todas", "tudo"):
        return list(range(1, total + 1))
    paginas: list[int] = []
    for parte in texto.replace(";", ",").split(","):
        parte = parte.strip()
        if not parte:
            continue
        try:
            if "-" in parte:
                a, b = (int(x) for x in parte.split("-", 1))
            else:
                a = b = int(parte)
        except ValueError:
            raise ErroDeImpressao(f"não entendi “{parte}” — escreva como 1-3, 7") from None
        if a < 1 or b > total or a > b:
            raise ErroDeImpressao(f"o documento tem {total} página{'s' if total != 1 else ''}; “{parte}” fica fora")
        paginas.extend(range(a, b + 1))
    if not paginas:
        raise ErroDeImpressao("diga quais páginas imprimir")
    return paginas


def _modo_da_impressora(w, nome: str, copias: int, cor: bool, frente_verso: bool):
    """O DEVMODE do driver com copias, cor e frente e verso ajustados - ou None
    se o driver nao entregar um (imprime do jeito padrao dele)."""
    porta = wintypes.HANDLE()
    if not w.OpenPrinterW(nome, ctypes.byref(porta), None):
        return None
    try:
        tamanho = w.DocumentPropertiesW(None, porta, nome, None, None, 0)
        if tamanho <= 0:
            return None
        buffer = ctypes.create_string_buffer(tamanho)
        if w.DocumentPropertiesW(None, porta, nome, buffer, None, DM_OUT_BUFFER) < 0:
            return None
        modo = ctypes.cast(buffer, ctypes.POINTER(_DevMode)).contents
        modo.dmCopies = max(1, min(copias, 99))
        modo.dmColor = DMCOLOR_COLOR if cor else DMCOLOR_MONOCHROME
        modo.dmDuplex = DMDUP_VERTICAL if frente_verso else DMDUP_SIMPLEX
        modo.dmFields |= DM_COPIES | DM_COLOR | DM_DUPLEX
        # O driver confere e corrige o que nao suporta (cor numa laser P&B).
        w.DocumentPropertiesW(None, porta, nome, buffer, buffer, DM_IN_BUFFER | DM_OUT_BUFFER)
        return buffer
    finally:
        w.ClosePrinter(porta)


def imprimir(pdf: bytes, impressora: str, titulo: str = "Documento", paginas: str = "todas",
             copias: int = 1, cor: bool = True, frente_verso: bool = False,
             saida: str | None = None) -> dict:
    """
    Manda o PDF para a impressora. Devolve quantas folhas foram ao spooler.

    `saida` e para impressora de arquivo (Microsoft Print to PDF): grava ali em
    vez de abrir a janela de "salvar como". E o que os testes usam.
    """
    if not disponivel():
        raise ErroDeImpressao("imprimir direto só funciona no Windows")
    import leitor_pdf
    from PIL import ImageWin

    nomes = {i["nome"] for i in listar()}
    if impressora not in nomes:
        raise ErroDeImpressao("essa impressora não está mais instalada — escolha outra")
    copias = max(1, min(int(copias or 1), 99))

    w, g = _winspool(), _gdi()
    modo = _modo_da_impressora(w, impressora, copias, cor, frente_verso)
    # Quem nao aceitou o DEVMODE ainda imprime as copias: repetidas aqui.
    repetir = 1 if modo is not None else copias

    hdc = g.CreateDCW("WINSPOOL", impressora, None, modo)
    if not hdc:
        raise ErroDeImpressao("o Windows não abriu essa impressora")
    enviadas = 0
    try:
        dpi_x, dpi_y = g.GetDeviceCaps(hdc, LOGPIXELSX), g.GetDeviceCaps(hdc, LOGPIXELSY)
        margem_x, margem_y = g.GetDeviceCaps(hdc, PHYSICALOFFSETX), g.GetDeviceCaps(hdc, PHYSICALOFFSETY)
        info = _DocInfo(ctypes.sizeof(_DocInfo), titulo[:120] or "Documento", saida, None, 0)
        if g.StartDocW(hdc, ctypes.byref(info)) <= 0:
            raise ErroDeImpressao("a impressora recusou o documento (cancelado ou sem papel?)")
        try:
            with leitor_pdf.abrir(pdf) as doc:
                lista = paginas_pedidas(paginas, len(doc))
                for _ in range(repetir):
                    for numero in lista:
                        pagina = doc[numero - 1]
                        largura_pt, altura_pt = pagina.get_width(), pagina.get_height()
                        imagem = pagina.render(scale=DPI_DO_DESENHO / 72).to_pil()
                        imagem = imagem.convert("L" if not cor else "RGB").convert("RGB")
                        # Tamanho real, a partir do canto fisico do papel: a area
                        # que a impressora nao alcanca e descontada, nao esticada.
                        x0, y0 = -margem_x, -margem_y
                        x1 = x0 + round(largura_pt / 72 * dpi_x)
                        y1 = y0 + round(altura_pt / 72 * dpi_y)
                        g.StartPage(hdc)
                        ImageWin.Dib(imagem).draw(hdc, (x0, y0, x1, y1))
                        g.EndPage(hdc)
                        enviadas += 1
        except Exception:
            g.AbortDoc(hdc)
            raise
        g.EndDoc(hdc)
    finally:
        g.DeleteDC(hdc)
    return {"impressora": impressora, "folhas": enviadas, "copias": copias}
