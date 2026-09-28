"""
O computador do escritorio acordado e o PAULUS aberto (R9).

O acesso de fora so funciona com a maquina ligada e o PAULUS rodando. Tres
coisas ajudam, e nenhuma pede administrador:

  - **nao deixar o Windows suspender por inatividade** enquanto o acesso de
    fora estiver ligado: `SetThreadExecutionState(ES_CONTINUOUS |
    ES_SYSTEM_REQUIRED)`. O pedido vale enquanto a thread que o fez existir -
    por isso ele mora numa thread propria, que fica viva ate o acesso
    desligar. A tela ainda pode apagar; o que nao pode e a maquina dormir.
    Fechar a tampa ou mandar suspender continua suspendendo: isso e decisao
    de quem esta na frente do computador;
  - **dizer se o plano de energia suspenderia** (`powercfg`), para a pessoa
    saber o que o PAULUS esta segurando;
  - **abrir com o Windows**, minimizado, pela chave HKCU\\...\\Run - so do
    usuario, desligado de fabrica, sugerido pelo assistente.
"""

from __future__ import annotations

import re
import subprocess
import sys
import threading
from pathlib import Path

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
CHAVE_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
NOME_NA_RUN = "PAULUS"
CREATE_NO_WINDOW = 0x08000000


def _set_thread_execution_state(flags: int) -> int:
    import ctypes

    return int(ctypes.windll.kernel32.SetThreadExecutionState(ctypes.c_uint(flags)))


class Acordado:
    """
    Enquanto ligado, o Windows nao suspende por inatividade. `chamar` e o
    SetThreadExecutionState (trocavel no teste).
    """

    def __init__(self, chamar=None) -> None:
        self._chamar = chamar or (_set_thread_execution_state if sys.platform == "win32" else None)
        self._parar = threading.Event()
        self._fio: threading.Thread | None = None
        self.ligado = False

    def _segurar(self) -> None:
        self._chamar(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        self.ligado = True
        self._parar.wait()
        # Na mesma thread que pediu: e ela que o Windows conta.
        self._chamar(ES_CONTINUOUS)
        self.ligado = False

    def ligar(self) -> bool:
        if self._chamar is None:
            return False
        if self._fio and self._fio.is_alive():
            return True
        self._parar.clear()
        self._fio = threading.Thread(target=self._segurar, name="acordado", daemon=True)
        self._fio.start()
        return True

    def desligar(self) -> None:
        self._parar.set()
        if self._fio:
            self._fio.join(timeout=3)
        self._fio = None


def minutos_ate_suspender() -> dict:
    """
    Quanto tempo parado o plano de energia deixa ate suspender, na tomada e
    na bateria (0 = nunca). Vazio quando nao da para ler (fora do Windows).
    `powercfg` fala a lingua do Windows; os dois numeros sao os ultimos
    "0x..." da resposta, na ordem tomada, bateria.
    """
    if sys.platform != "win32":
        return {}
    try:
        r = subprocess.run(["powercfg", "/query", "SCHEME_CURRENT", "SUB_SLEEP", "STANDBYIDLE"],
                           capture_output=True, text=True, timeout=10, creationflags=CREATE_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return {}
    numeros = re.findall(r":\s*0x([0-9a-fA-F]{8})\s*$", r.stdout or "", re.M)
    if len(numeros) < 2:
        return {}
    tomada, bateria = (int(n, 16) for n in numeros[-2:])
    return {"tomada_min": round(tomada / 60), "bateria_min": round(bateria / 60)}


# ------------------------------------------------------- abrir com o Windows

def exe_do_programa() -> Path | None:
    """O PAULUS.exe desta instalacao; no codigo-fonte (desenvolvimento) nao ha."""
    exe = Path(__file__).resolve().parent.parent.parent.parent / "PAULUS.exe"
    return exe if exe.is_file() else None


def abre_com_windows(chave: str = CHAVE_RUN) -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, chave) as k:
            valor, _ = winreg.QueryValueEx(k, NOME_NA_RUN)
            return bool(valor)
    except OSError:
        return False


def abrir_com_windows(ligar: bool, exe: Path | None = None, chave: str = CHAVE_RUN) -> bool:
    """Grava (ou tira) o PAULUS da lista do que abre com o Windows, minimizado."""
    if sys.platform != "win32":
        return False
    import winreg

    if ligar:
        exe = exe or exe_do_programa()
        if not exe:
            return False
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, chave) as k:
            winreg.SetValueEx(k, NOME_NA_RUN, 0, winreg.REG_SZ, f'"{exe}" --minimizado')
        return True
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, chave, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, NOME_NA_RUN)
    except OSError:
        pass
    return True
