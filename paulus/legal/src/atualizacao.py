"""
A atualizacao do PAULUS: saber se ha versao nova, baixar o instalador e
passar a vez para ele.

- **Onde a versao nova e anunciada:** `https://paulus.ia.br/atualizacao.json`,
  publicado junto com o site a cada release (site/atualizacao.json):

      {"versao": "0.9.2", "url": "https://github.com/.../PAULUS-0.9.2-instalador.exe",
       "sha256": "...", "tamanho": 94103737, "publicada": "2026-10-01",
       "notas": "https://github.com/.../releases/tag/v0.9.2", "novidades": ["...", "..."]}

  So a leitura desse arquivo sai daqui (uma vez por dia, se a pessoa deixou
  ligado) - nenhum dado do escritorio, da pessoa ou da maquina vai junto.
- **Baixar:** o instalador vai para dados/atualizacao/ e so e usado se o
  SHA-256 bater com o anunciado. Baixado pela metade ou diferente, e apagado.
- **Instalar:** so o PAULUS instalado (PAULUS_INSTALADO) se atualiza; rodando
  do codigo-fonte, atualizar e `git pull`. O instalador abre no modo
  `/atualizar` (sem perguntas, com o andamento, reabre o PAULUS no fim) ou,
  para instalar ao fechar, `/silencioso`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests

URL = os.environ.get("PAULUS_ATUALIZACAO_URL") or "https://paulus.ia.br/atualizacao.json"
UM_DIA = 24 * 3600
_RE_VERSAO = re.compile(r"^\d+(\.\d+){1,3}$")
_RE_SHA = re.compile(r"^[0-9a-f]{64}$")


def numeros(versao: str) -> tuple[int, ...]:
    """'0.9.10' -> (0, 9, 10): compara versao como numero, nao como texto."""
    try:
        return tuple(int(x) for x in str(versao).split("."))
    except ValueError:
        return ()


def mais_nova(anunciada: str, atual: str) -> bool:
    a, b = numeros(anunciada), numeros(atual)
    return bool(a) and bool(b) and a > b


def validar(dados: dict) -> dict:
    """O anuncio, conferido campo a campo. Levanta ValueError se nao presta."""
    versao = str(dados.get("versao", "")).strip()
    url = str(dados.get("url", "")).strip()
    sha = str(dados.get("sha256", "")).strip().lower()
    if not _RE_VERSAO.match(versao):
        raise ValueError("anúncio sem versão válida")
    # O instalador so vem de lugar conhecido, e por HTTPS. O teste de ponta a
    # ponta (PAULUS_ATUALIZACAO_TESTE) serve o anuncio e o instalador daqui.
    local = bool(os.environ.get("PAULUS_ATUALIZACAO_TESTE")) and url.startswith("http://127.0.0.1:")
    if not local and not re.match(r"^https://(github\.com/matheusuener-atos/coryphaeus/releases/download/|paulus\.ia\.br/)", url):
        raise ValueError("endereço do instalador fora dos lugares conhecidos")
    if not _RE_SHA.match(sha):
        raise ValueError("anúncio sem SHA-256")
    novidades = [str(x)[:300] for x in (dados.get("novidades") or [])][:12]
    return {"versao": versao, "url": url, "sha256": sha, "tamanho": int(dados.get("tamanho") or 0),
            "publicada": str(dados.get("publicada", ""))[:10], "notas": str(dados.get("notas", ""))[:300],
            "novidades": novidades}


def consultar(atual: str, url: str = URL, pegar=None) -> dict:
    """Le o anuncio e diz se ha versao nova. `pegar` troca o HTTP (testes)."""
    pegar = pegar or (lambda u: requests.get(u, timeout=15, headers={"User-Agent": "PAULUS/" + atual}))
    resp = pegar(url)
    resp.raise_for_status()
    anuncio = validar(resp.json())
    return {**anuncio, "nova": mais_nova(anuncio["versao"], atual), "atual": atual,
            "consultado_em": time.strftime("%Y-%m-%d %H:%M")}


def sha256_de(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


class Baixador:
    """Baixa o instalador anunciado, com andamento, e confere o SHA-256."""

    def __init__(self, pasta: Path, pegar=None) -> None:
        self.pasta = Path(pasta)
        self._pegar = pegar or (lambda u: requests.get(u, timeout=30, stream=True,
                                                        headers={"User-Agent": "PAULUS-atualizacao"}))
        self._trava = threading.Lock()
        self._cancelar = threading.Event()
        self.estado = {"andando": False, "baixado": 0, "total": 0, "progresso": 0, "pronto": False,
                       "erro": "", "versao": "", "arquivo": ""}

    def andamento(self) -> dict:
        with self._trava:
            return dict(self.estado)

    def _por(self, **kw) -> None:
        with self._trava:
            self.estado.update(kw)

    def pronto_para(self, anuncio: dict) -> Path | None:
        """O instalador ja baixado e conferido desta versao, se houver."""
        arq = self.pasta / f"PAULUS-{anuncio['versao']}-instalador.exe"
        if arq.exists() and arq.stat().st_size > 0 and sha256_de(arq) == anuncio["sha256"]:
            return arq
        return None

    def iniciar(self, anuncio: dict, ao_terminar=None) -> dict:
        if self.andamento()["andando"]:
            raise RuntimeError("já estou baixando a atualização")
        feito = self.pronto_para(anuncio)
        if feito:
            self._por(andando=False, pronto=True, progresso=100, erro="", versao=anuncio["versao"], arquivo=str(feito))
            if ao_terminar:
                ao_terminar(feito)
            return self.andamento()
        self._cancelar.clear()
        self._por(andando=True, baixado=0, total=anuncio.get("tamanho") or 0, progresso=0, pronto=False,
                  erro="", versao=anuncio["versao"], arquivo="")
        threading.Thread(target=self._rodar, args=(anuncio, ao_terminar), name="baixar-atualizacao", daemon=True).start()
        return self.andamento()

    def cancelar(self) -> dict:
        self._cancelar.set()
        return self.andamento()

    def _rodar(self, anuncio: dict, ao_terminar) -> None:
        self.pasta.mkdir(parents=True, exist_ok=True)
        destino = self.pasta / f"PAULUS-{anuncio['versao']}-instalador.exe"
        parcial = destino.with_suffix(".parcial")
        try:
            # So a versao nova fica: instaladores de antes saem.
            for velho in self.pasta.glob("PAULUS-*-instalador.exe"):
                if velho != destino:
                    velho.unlink(missing_ok=True)
            resp = self._pegar(anuncio["url"])
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length") or anuncio.get("tamanho") or 0)
            feito = 0
            h = hashlib.sha256()
            with open(parcial, "wb") as f:
                for bloco in resp.iter_content(1 << 16):
                    if self._cancelar.is_set():
                        raise InterruptedError("cancelado")
                    f.write(bloco)
                    h.update(bloco)
                    feito += len(bloco)
                    self._por(baixado=feito, total=total, progresso=int(feito * 100 / total) if total else 0)
            if h.hexdigest() != anuncio["sha256"]:
                raise ValueError("o arquivo baixado não confere com o SHA-256 anunciado; foi apagado")
            parcial.replace(destino)
            self._por(andando=False, pronto=True, progresso=100, arquivo=str(destino))
            if ao_terminar:
                ao_terminar(destino)
        except InterruptedError:
            self._por(andando=False, erro="cancelado")
        except Exception as exc:  # noqa: BLE001 - vira frase na tela
            self._por(andando=False, erro=str(exc)[:300])
        finally:
            parcial.unlink(missing_ok=True)


def instalado() -> bool:
    return bool(os.environ.get("PAULUS_INSTALADO"))


def pasta_do_programa(base_dir: Path) -> Path:
    """Instalado, o programa fica em <pasta>/app: a pasta e a de cima."""
    return Path(base_dir).parent


def abrir_instalador(instalador: Path, pasta: Path, calado: bool) -> None:
    """
    Passa a vez para o instalador, solto deste processo (ele fecha o PAULUS
    para trocar os arquivos). `calado`: instala sem janela, ao fechar.
    """
    args = [str(instalador), f"/pasta={pasta}"]
    args += ["/silencioso"] if calado else ["/atualizar"]
    flags = 0
    if sys.platform == "win32":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(args, cwd=str(instalador.parent), close_fds=True, creationflags=flags,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    print(json.dumps(consultar(sys.argv[1] if len(sys.argv) > 1 else "0.0.0"), ensure_ascii=False, indent=1))
