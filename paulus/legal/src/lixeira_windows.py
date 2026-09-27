"""
Excluir um documento do computador mandando para a Lixeira do Windows.

Quando alguém tira um documento do Acervo e marca "também excluir do
computador", o arquivo vai para a Lixeira do Windows - não é apagado de vez.
Dá para restaurar pelo próprio Windows, e por isso não precisa passar por
Aprovações.

Pasta de rede é a exceção: nela o Windows apaga sem lixeira, mesmo pedindo a
lixeira. Aí o PAULUS recusa e diz por quê, em vez de apagar de vez sem avisar.

A chamada é a SHFileOperationW do Windows, com FOF_ALLOWUNDO (a lixeira), sem
janela de confirmação do Windows (quem confirmou foi a tela do PAULUS).
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path

FO_DELETE = 3
FOF_SILENT = 0x0004
FOF_NOCONFIRMATION = 0x0010
FOF_ALLOWUNDO = 0x0040
FOF_NOERRORUI = 0x0400
DRIVE_REMOTE = 4


class _SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR),
        ("fFlags", ctypes.c_uint16),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


def em_pasta_de_rede(caminho: Path) -> bool:
    """Unidade de rede ou caminho \\\\servidor\\pasta: o Windows não tem lixeira ali."""
    texto = str(caminho.resolve())
    if texto.startswith("\\\\"):
        return True
    raiz = os.path.splitdrive(texto)[0] + "\\"
    try:
        return ctypes.windll.kernel32.GetDriveTypeW(raiz) == DRIVE_REMOTE
    except (AttributeError, OSError):
        return False


def mandar_para_lixeira(caminho: Path) -> str:
    """
    Manda um arquivo para a Lixeira do Windows. Devolve "" quando foi, ou o
    motivo de não ter ido - nesse caso o arquivo continua onde estava.
    """
    caminho = Path(caminho)
    if not caminho.is_file():
        return "o arquivo não está mais lá"
    if em_pasta_de_rede(caminho):
        return "está numa pasta de rede, onde o Windows apagaria sem lixeira; exclua pelo Windows se tiver certeza"
    op = _SHFILEOPSTRUCTW()
    op.wFunc = FO_DELETE
    op.pFrom = str(caminho.resolve()) + "\0"  # a lista termina com dois zeros
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
    try:
        codigo = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    except (AttributeError, OSError) as exc:
        return "a Lixeira do Windows não respondeu: " + str(exc)[:100]
    if codigo != 0 or op.fAnyOperationsAborted:
        return f"o Windows não deixou (código {codigo}); o arquivo pode estar aberto em outro programa"
    if caminho.exists():
        return "o Windows não tirou o arquivo do lugar"
    return ""
