"""
PAULUS - Segredos guardados nesta maquina.

Senha de certificado e senha de e-mail tem o mesmo problema: precisam ficar
disponiveis para o programa e precisam nao ficar legiveis para quem abrir a
pasta. Guardar em texto num JSON resolveria o primeiro e entregaria o segundo.

A DPAPI do Windows amarra o segredo a conta que o gravou: copiar o arquivo
para outra maquina, ou abri-lo por outra conta do mesmo computador, devolve
bytes inuteis. Nao e cofre inviolavel - quem ja esta rodando como voce
consegue - mas e a diferenca entre um arquivo que qualquer um le e um que so
esta conta le.

Fora do Windows nao ha equivalente sem trazer dependencia nova, entao
`disponivel()` responde False e quem chama nao guarda senha nenhuma - pergunta
toda vez, e diz isso na tela. Melhor perguntar de novo do que guardar mal.
"""

from __future__ import annotations

import base64
import sys

ROTULO = "PAULUS"


def _dpapi(dados: bytes, proteger: bool) -> bytes | None:
    if sys.platform != "win32":
        return None

    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buffer_ = ctypes.create_string_buffer(dados, len(dados))
    entrada = BLOB(len(dados), ctypes.cast(buffer_, ctypes.POINTER(ctypes.c_char)))
    saida = BLOB()
    crypt32 = ctypes.windll.crypt32

    try:
        if proteger:
            ok = crypt32.CryptProtectData(
                ctypes.byref(entrada), ROTULO, None, None, None, 0, ctypes.byref(saida)
            )
        else:
            ok = crypt32.CryptUnprotectData(
                ctypes.byref(entrada), None, None, None, None, 0, ctypes.byref(saida)
            )
    except OSError:
        return None
    if not ok:
        return None

    try:
        return ctypes.string_at(saida.pbData, saida.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(saida.pbData)


def disponivel() -> bool:
    """Se da para guardar segredo com protecao de verdade nesta maquina."""
    return _dpapi(b"teste", True) is not None


def proteger(segredo: str) -> str:
    """Devolve o segredo protegido em base64, ou vazio se nao der para proteger."""
    if not segredo:
        return ""
    blob = _dpapi(segredo.encode("utf-8"), True)
    return base64.b64encode(blob).decode("ascii") if blob else ""


def revelar(guardado: str) -> str:
    """
    Abre o que `proteger` guardou.

    Devolve vazio quando nao da - conta trocada, maquina trocada, arquivo
    corrompido. Quem chama trata isso como "nao tenho a senha" e pergunta, em
    vez de estourar.
    """
    if not guardado:
        return ""
    try:
        bruto = base64.b64decode(guardado)
    except (ValueError, TypeError):
        return ""
    aberto = _dpapi(bruto, False)
    return aberto.decode("utf-8", errors="replace") if aberto else ""
