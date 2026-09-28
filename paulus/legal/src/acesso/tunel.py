"""
O tunel dentro do PAULUS (R6): o `cloudflared` como processo filho.

O `cloudflared` abre uma conexao de SAIDA da maquina ate a Cloudflare, e e
por ela que chega quem esta de fora. Nenhuma porta aberta no roteador, nada
escutando alem de 127.0.0.1.

  - **Onde ele esta**, nesta ordem: a pasta onde o instalador o poe
    (%LOCALAPPDATA%\\Programs\\PAULUS-cloudflared), o PATH, e
    Program Files\\cloudflared. Versao abaixo da minima nao roda.
  - **O token vai no ambiente** (TUNNEL_TOKEN), nunca na linha de comando:
    linha de comando de processo qualquer programa da maquina le. E o log
    (data/logs/tunel.log) passa por um filtro que tira o token de toda linha.
  - **Caiu, levanta de novo**, com espera crescente (2 s, 4 s, 8 s... ate 1
    min) - internet que oscila nao pode virar um processo reiniciando sem
    parar.
  - **Morre com o PAULUS**: desligar o modulo ou fechar o programa encerra o
    processo. Processo de tunel orfao seria a porta de fora aberta sem o
    PAULUS saber.

Os segredos (token do tunel, segredo da instalacao) moram protegidos pela
DPAPI em data/acesso/tunel.json. Fora do Windows, o modulo e indisponivel.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

VERSAO_MINIMA = "2025.4.0"
RE_VERSAO = re.compile(r"version\s+(\d+)\.(\d+)\.(\d+)")
# O que o cloudflared escreve quando a conexao com a borda da Cloudflare fica
# de pe - e o que separa "ligando" de "conectado".
RE_CONECTOU = re.compile(r"Registered tunnel connection|Connection [0-9a-f-]+ registered", re.I)
CREATE_NO_WINDOW = 0x08000000


def pasta_do_instalador() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "Programs" / "PAULUS-cloudflared"


def achar_cloudflared() -> Path | None:
    candidatos = [pasta_do_instalador() / "cloudflared.exe"]
    no_path = shutil.which("cloudflared")
    if no_path:
        candidatos.append(Path(no_path))
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        if base:
            candidatos.append(Path(base) / "cloudflared" / "cloudflared.exe")
    return next((c for c in candidatos if c.is_file()), None)


def versao_de(exe: Path | list) -> str:
    """'2026.9.3', ou vazio se o programa nao respondeu como cloudflared."""
    comando = list(exe) if isinstance(exe, list) else [str(exe)]
    try:
        r = subprocess.run(comando + ["--version"], capture_output=True, text=True, timeout=15,
                           creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    except (OSError, subprocess.SubprocessError):
        return ""
    achado = RE_VERSAO.search((r.stdout or "") + (r.stderr or ""))
    return ".".join(achado.groups()) if achado else ""


def versao_basta(versao: str, minima: str = VERSAO_MINIMA) -> bool:
    try:
        return tuple(int(x) for x in versao.split(".")) >= tuple(int(x) for x in minima.split("."))
    except ValueError:
        return False


# ------------------------------------------------------------- segredos

class Cofre:
    """O token do tunel e o segredo da instalacao, protegidos pela DPAPI."""

    def __init__(self, caminho: Path, proteger=None, revelar=None) -> None:
        import segredos

        self.caminho = Path(caminho)
        self._proteger = proteger or segredos.proteger
        self._revelar = revelar or segredos.revelar

    def guardar(self, token: str, segredo: str) -> None:
        t, s = self._proteger(token), self._proteger(segredo)
        if not t or not s:
            raise RuntimeError("não consegui proteger o token do túnel neste computador")
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.write_text(json.dumps({"token": t, "segredo": s}), encoding="utf-8")

    def _ler(self) -> dict:
        try:
            return json.loads(self.caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def token(self) -> str:
        return self._revelar(self._ler().get("token", ""))

    def segredo(self) -> str:
        return self._revelar(self._ler().get("segredo", ""))

    def tem(self) -> bool:
        return bool(self._ler().get("token"))

    def apagar(self) -> None:
        try:
            self.caminho.unlink()
        except OSError:
            pass


# ------------------------------------------------------------ o processo

class Tunel:
    """
    O `cloudflared tunnel run` sob supervisao. `comando()` devolve a linha de
    comando SEM o token; `token()` devolve o token, que vai so no ambiente.
    """

    def __init__(self, comando, token, log: Path, *, espera_inicial: float = 2.0,
                 espera_maxima: float = 60.0, popen=subprocess.Popen) -> None:
        self.comando = comando
        self.token = token
        self.log = Path(log)
        self.espera_inicial = espera_inicial
        self.espera_maxima = espera_maxima
        self._popen = popen
        self._trava = threading.Lock()
        self._parar = threading.Event()
        self._processo = None
        self._fio = None
        self.estado = "desligado"
        self.partidas = 0
        self.ultimo_erro = ""

    # ------------------------------------------------------------- vida

    def ligar(self) -> None:
        with self._trava:
            if self._fio and self._fio.is_alive():
                return
            self._parar.clear()
            self.estado = "ligando"
            self._fio = threading.Thread(target=self._supervisionar, name="tunel", daemon=True)
            self._fio.start()

    def desligar(self, esperar: float = 5.0) -> None:
        self._parar.set()
        with self._trava:
            p = self._processo
        if p and p.poll() is None:
            try:
                p.terminate()
                p.wait(timeout=esperar)
            except Exception:  # noqa: BLE001 - quem nao sai por bem sai por mal
                try:
                    p.kill()
                except Exception:  # noqa: BLE001
                    pass
        if self._fio:
            self._fio.join(timeout=esperar)
        self.estado = "desligado"

    @property
    def ligado(self) -> bool:
        return bool(self._fio and self._fio.is_alive())

    # --------------------------------------------------------- supervisor

    def _supervisionar(self) -> None:
        espera = self.espera_inicial
        while not self._parar.is_set():
            token = self.token() or ""
            comando = self.comando()
            if not token or not comando:
                self.estado = "sem_token" if not token else "sem_cloudflared"
                return
            ambiente = {**os.environ, "TUNNEL_TOKEN": token}
            comeco = time.time()
            try:
                p = self._popen(
                    list(comando), env=ambiente, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
                    creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            except OSError as exc:
                self.ultimo_erro = str(exc)
                self.estado = "caiu"
                if self._parar.wait(espera):
                    return
                espera = min(espera * 2, self.espera_maxima)
                continue
            with self._trava:
                self._processo = p
            self.partidas += 1
            self.estado = "ligando"
            for linha in p.stdout:
                self._anotar(linha, token)
                if RE_CONECTOU.search(linha):
                    self.estado = "conectado"
                    espera = self.espera_inicial
            p.wait()
            if self._parar.is_set():
                return
            self.estado = "caiu"
            self.ultimo_erro = f"o cloudflared saiu (código {p.returncode})"
            # Ficou de pe um bom tempo antes de cair: nao e o mesmo defeito
            # repetindo, e a espera volta ao comeco.
            if time.time() - comeco > 120:
                espera = self.espera_inicial
            if self._parar.wait(espera):
                return
            espera = min(espera * 2, self.espera_maxima)

    def _anotar(self, linha: str, token: str) -> None:
        """O log do tunel, sem o token - nunca, em linha nenhuma."""
        limpa = linha.rstrip("\n")
        if token:
            limpa = limpa.replace(token, "***")
        limpa = re.sub(r"(?i)(token[\"'=: ]+)[A-Za-z0-9_\-\.=]{20,}", r"\1***", limpa)
        try:
            self.log.parent.mkdir(parents=True, exist_ok=True)
            if self.log.exists() and self.log.stat().st_size > 2 * 1024 * 1024:
                self.log.replace(self.log.with_suffix(".anterior.log"))
            with open(self.log, "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + limpa + "\n")
        except OSError:
            pass
