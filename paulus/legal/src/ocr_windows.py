"""
Ler PDF escaneado: o texto que está na imagem da página.

O motor é o OCR do próprio Windows (Windows.Media.Ocr), que vem com o
sistema e com o idioma instalado - num Windows em português, o português. Não
baixa modelo, não usa a internet, não passa pelo modelo de linguagem.

Medido em 27/09/2026 com páginas de texto conhecido transformadas em
"escaneado" (imagem, giro, ruído, JPEG):

- escaneado limpo (200 dpi, giro de 0,7°): 99,9% dos caracteres e 99,2% das
  palavras, 0,12 s por página;
- escaneado ruim (150 dpi, giro de 2°, borrado, ruído forte, JPEG 35):
  98,1% dos caracteres, 92,9% das palavras - 95% sem contar acento, que a
  busca do PAULUS ignora -, 0,7 s por página.

Tirar o ruído antes (filtro de mediana, contraste) PIORAVA: 51% das palavras
no escaneado ruim. A imagem vai crua, a 300 dpi.

OCR erra - troca "l" por "t", perde acento, junta número. O documento lido
assim fica marcado, e a tela diz que o texto veio de imagem.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

# Todo o trabalho com o Windows numa linha de execucao so, com laco de eventos
# proprio. Chamado de dentro do servidor (a abertura do programa e assincrona),
# o asyncio.run falhava - "coroutine was never awaited" - e o motor criado numa
# linha e usado em outra derrubava o processo inteiro (medido: o teste das
# gravacoes caia com falha de segmentacao).
_linha = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ocr-windows")

DPI = 300
# Uma página com menos que isto de texto próprio é tratada como imagem: o
# carimbo de um escaneado ("Digitalizado por...") não é o documento.
MIN_TEXTO_DA_PAGINA = 20

_motor = None
_idioma = ""
_trava = threading.Lock()
_situacao: dict | None = None


def _criar_motor():
    """O motor do Windows, em português se houver; senão no idioma de quem usa."""
    from winrt.windows.globalization import Language
    from winrt.windows.media.ocr import OcrEngine

    idiomas = [l.language_tag for l in OcrEngine.available_recognizer_languages]
    for preferido in ("pt-BR", "pt-PT"):
        if preferido in idiomas:
            return OcrEngine.try_create_from_language(Language(preferido)), preferido, idiomas
    portugues = next((i for i in idiomas if i.lower().startswith("pt")), "")
    if portugues:
        return OcrEngine.try_create_from_language(Language(portugues)), portugues, idiomas
    motor = OcrEngine.try_create_from_user_profile_languages()
    return motor, (motor.recognizer_language.language_tag if motor else ""), idiomas


def situacao() -> dict:
    """Se dá para ler imagem nesta máquina, em que idioma, e por quê não, quando não."""
    if _situacao is not None:
        return _situacao
    return _linha.submit(_situacao_na_linha).result()


def _situacao_na_linha() -> dict:
    global _motor, _idioma, _situacao
    with _trava:
        if _situacao is not None:
            return _situacao
        try:
            motor, idioma, idiomas = _criar_motor()
        except ImportError:
            _situacao = {"ok": False, "idioma": "", "motivo": "o leitor de imagem do Windows não está instalado no PAULUS"}
            return _situacao
        except Exception as exc:  # noqa: BLE001 - Windows antigo, serviço desligado
            _situacao = {"ok": False, "idioma": "", "motivo": "o leitor de imagem do Windows não respondeu: " + str(exc)[:120]}
            return _situacao
        if motor is None:
            _situacao = {"ok": False, "idioma": "", "motivo": "o Windows não tem nenhum idioma de leitura de imagem instalado"}
            return _situacao
        _motor, _idioma = motor, idioma
        aviso = "" if idioma.lower().startswith("pt") else (
            f"lendo em {idioma}: sem o pacote de idioma Português do Windows, os acentos se perdem")
        _situacao = {"ok": True, "idioma": idioma, "motivo": aviso, "idiomas": idiomas}
        return _situacao


def ler_imagem(img) -> str:
    """O texto de uma imagem (PIL), linha por linha - sempre na linha do OCR."""
    return _linha.submit(_ler_na_linha, img).result()


def _ler_na_linha(img) -> str:
    import asyncio

    from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap
    from winrt.windows.storage.streams import DataWriter

    if not _situacao_na_linha()["ok"]:
        raise RuntimeError(_situacao_na_linha()["motivo"])
    from winrt.windows.media.ocr import OcrEngine

    cinza = img.convert("L")
    limite = OcrEngine.max_image_dimension
    if max(cinza.size) > limite:
        escala = limite / max(cinza.size)
        cinza = cinza.resize((int(cinza.width * escala), int(cinza.height * escala)))
    escritor = DataWriter()
    escritor.write_bytes(cinza.tobytes())
    bitmap = SoftwareBitmap.create_copy_from_buffer(escritor.detach_buffer(), BitmapPixelFormat.GRAY8,
                                                    cinza.width, cinza.height)

    async def reconhecer():
        return await _motor.recognize_async(bitmap)

    resultado = asyncio.run(reconhecer())
    return "\n".join(linha.text for linha in resultado.lines)


def ler_paginas(caminho, paginas: list[int], dpi: int = DPI) -> dict[int, str]:
    """
    O texto das páginas pedidas (contando de 1) de um PDF, pela imagem de cada uma.

    A página é desenhada DENTRO da porta do PDFium (leitor_pdf.abrir): ele não
    aguenta duas linhas de execução ao mesmo tempo, e desenhar por fora dela
    derrubava o programa inteiro quando coincidia com a tela abrindo um PDF
    (medido: falha de segmentação intermitente no teste de tela). A imagem sai
    copiada, e a leitura - o trecho lento - acontece com a porta aberta.
    """
    import leitor_pdf

    saida = {}
    for n in paginas:
        with leitor_pdf.abrir(caminho) as doc:
            imagem = doc[n - 1].render(scale=dpi / 72).to_pil().convert("L").copy()
        saida[n] = ler_imagem(imagem).strip()
    return saida
