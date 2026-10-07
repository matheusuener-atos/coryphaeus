"""
A calibração compartilhada: as medidas de modelo de muitas máquinas.

A estimativa de quanto cada modelo demora numa máquina (src/maquina.py) vem
de amostras - uma máquina testada mais um modelo medido nela. As que vão com
o programa são de uma máquina só. Quem escolhe **Participar da calibração**
(desligado de fábrica) manda as amostras da própria máquina ao site do PAULUS
e recebe as de todos, e a estimativa melhora para todo mundo.

O que vai é exatamente o que `maquina.amostra()` monta, e a tela mostra antes:
o processador, a memória, as duas velocidades medidas, o modelo e as palavras
por segundo dele. Nada do escritório, nada de pessoa. O servidor (Worker do
paulus.ia.br, /api/calibracao) confere campo a campo e joga fora o resto.

As amostras que chegam de fora passam por uma conferência antes de entrar na
conta: a que foge demais do que a física prevê (de 0,2 a 5 vezes) fica de
fora. Uma amostra falsa não estraga a estimativa de ninguém.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import requests

URL = os.environ.get("PAULUS_CALIBRACAO_URL") or "https://paulus.ia.br/api/calibracao"
TEMPO = 15
FAIXA_PLAUSIVEL = (0.2, 5.0)


class ErroCalibracao(RuntimeError):
    pass


def enviar(amostras: list[dict], versao: str = "", url: str = URL, postar=None) -> dict:
    """Manda as amostras desta máquina. Devolve o que o servidor respondeu."""
    if not amostras:
        return {"recebidas": 0}
    postar = postar or requests.post
    try:
        r = postar(url, json={"amostras": amostras[:50], "programa": versao}, timeout=TEMPO)
    except requests.RequestException as exc:
        raise ErroCalibracao("não consegui falar com o site do Paulus: " + str(exc)[:120]) from exc
    if r.status_code >= 400:
        try:
            motivo = r.json().get("erro", "")
        except ValueError:
            motivo = ""
        raise ErroCalibracao(f"o site do Paulus recusou ({r.status_code}) {motivo}".strip())
    try:
        return r.json()
    except ValueError:
        return {}


def baixar(destino: Path, url: str = URL, pegar=None) -> int:
    """As amostras de todos, guardadas em `destino`. Devolve quantas vieram."""
    pegar = pegar or requests.get
    try:
        r = pegar(url, timeout=TEMPO)
        r.raise_for_status()
        amostras = [a for a in (r.json().get("amostras") or []) if isinstance(a, dict)]
    except (requests.RequestException, ValueError) as exc:
        raise ErroCalibracao("não consegui ler a calibração do site do Paulus: " + str(exc)[:120]) from exc
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps({"quando": datetime.now().strftime("%Y-%m-%d %H:%M"), "amostras": amostras},
                                  ensure_ascii=False), encoding="utf-8")
    return len(amostras)


def plausiveis(remotas: list[dict], calib: dict) -> list[dict]:
    """
    As amostras de fora que a física explica: a escrita medida fica entre 0,2
    e 5 vezes o que a calibração de base prevê para aquela máquina e modelo.
    """
    import maquina

    boas = []
    for a in remotas:
        try:
            m = a["maquina"]
            modelo = {"gb": float(a["tamanho_gb"]), "parametros": float(a["parametros_b"]), "quantizacao": a.get("quantizacao", "")}
            prevista, _, _ = maquina._bruto(modelo, {"banda_gbs": float(m["banda_gbs"]), "gflops": float(m["gflops"])}, calib)
            razao = float(a["escrita_tps"]) / prevista if prevista else 0
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue
        if FAIXA_PLAUSIVEL[0] <= razao <= FAIXA_PLAUSIVEL[1]:
            boas.append(a)
    return boas


def ler_guardadas(caminho: Path) -> tuple[list[dict], str]:
    try:
        d = json.loads(caminho.read_text(encoding="utf-8"))
        return list(d.get("amostras") or []), str(d.get("quando", ""))
    except (OSError, ValueError):
        return [], ""
