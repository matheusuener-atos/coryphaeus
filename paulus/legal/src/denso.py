"""
A busca por sentido: vetores do `bge-m3`, pelo proprio Ollama (I7).

A busca lexica (src/lexico.py) acha a palavra; esta acha o assunto. "Quanto
custa sair do contrato antes?" nao tem a palavra "rescisao", e o trecho da
clausula de rescisao e o que responde. As duas listas se juntam por RRF
(src/recuperacao.py).

O modelo de vetores roda no Ollama da maquina (`/api/embed`): nenhum texto
sai daqui. Ele e baixado so com o consentimento da pessoa, pelo mesmo
Baixador dos outros modelos (Configuracoes > Modelos), que diz o tamanho
antes.

**Um espaco de vetores por vez.** Cada vetor grava o espaco em que nasceu,
`bge-m3|1024|l2|v1`; a consulta so compara com vetores do mesmo espaco.
Trocar o modelo de vetores nao mistura nada: os vetores antigos deixam de
ser usados, e o acervo e vetorizado de novo.

Onde os vetores moram: SQLite, como BLOB de float32, com o cosseno em numpy
(que ja vem com o programa). A extensao `sqlite-vec` nao esta no ambiente do
programa, e para o tamanho de um acervo de escritorio - dezenas de milhares
de trechos - o produto de matriz em numpy responde em milissegundos.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

import numpy as np
import requests

MODELO = "bge-m3"
DIMENSAO = 1024
ESPACO = f"{MODELO}|{DIMENSAO}|l2|v1"
# O tamanho do download, para a tela dizer antes (registro do Ollama).
GB_APROX = 1.2
LOTE = 16


def normalizar_l2(matriz: np.ndarray) -> np.ndarray:
    normas = np.linalg.norm(matriz, axis=1, keepdims=True)
    normas[normas == 0] = 1.0
    return matriz / normas


class Vetorizador:
    """Texto -> vetor, pelo `/api/embed` do Ollama local."""

    def __init__(self, host: str, modelo: str = MODELO, *, post=None, timeout: int = 120) -> None:
        self.host = host
        self.modelo = modelo
        self._post = post or requests.post
        self.timeout = timeout

    def vetores(self, textos: list[str]) -> np.ndarray:
        if not textos:
            return np.zeros((0, DIMENSAO), dtype=np.float32)
        resp = self._post(f"{self.host}/api/embed",
                          json={"model": self.modelo, "input": textos, "keep_alive": "30m"},
                          timeout=self.timeout)
        resp.raise_for_status()
        matriz = np.asarray(resp.json().get("embeddings") or [], dtype=np.float32)
        if matriz.ndim != 2 or matriz.shape[0] != len(textos):
            raise RuntimeError("o Ollama devolveu vetores fora do formato")
        return normalizar_l2(matriz)


class IndiceDenso:
    """Os vetores do Acervo, um por trecho estrutural, com o espaco de cada um."""

    def __init__(self, caminho: Path | str, espaco: str = ESPACO) -> None:
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.espaco = espaco
        self._trava = threading.Lock()
        self._con = sqlite3.connect(str(self.caminho), check_same_thread=False)
        self._con.execute("PRAGMA journal_mode=WAL")
        self._con.execute("""CREATE TABLE IF NOT EXISTS vetores (
            chunk_id TEXT NOT NULL, espaco TEXT NOT NULL, documento TEXT NOT NULL, vetor BLOB NOT NULL,
            PRIMARY KEY (chunk_id, espaco))""")
        self._con.commit()
        self._cache: tuple[list[str], list[str], np.ndarray] | None = None

    def ids(self) -> set[str]:
        with self._trava:
            return {r[0] for r in self._con.execute("SELECT chunk_id FROM vetores WHERE espaco = ?", (self.espaco,))}

    def faltam(self, chunks) -> list:
        """Os trechos sem vetor neste espaco - o que o backfill ainda tem de fazer."""
        tem = self.ids()
        return [c for c in chunks if c.chunk_id and c.chunk_id not in tem]

    def gravar(self, chunks, matriz: np.ndarray) -> None:
        linhas = [(c.chunk_id, self.espaco, c.doc_name, np.asarray(v, dtype=np.float32).tobytes())
                  for c, v in zip(chunks, matriz)]
        with self._trava:
            self._con.executemany("INSERT OR REPLACE INTO vetores VALUES (?, ?, ?, ?)", linhas)
            self._con.commit()
            self._cache = None

    def podar(self, chunks) -> int:
        """Tira os vetores de trechos que nao existem mais (documento mudou ou saiu)."""
        vivos = {c.chunk_id for c in chunks if c.chunk_id}
        with self._trava:
            mortos = [r[0] for r in self._con.execute("SELECT chunk_id FROM vetores WHERE espaco = ?", (self.espaco,))
                      if r[0] not in vivos]
            self._con.executemany("DELETE FROM vetores WHERE chunk_id = ? AND espaco = ?",
                                  [(m, self.espaco) for m in mortos])
            self._con.commit()
            if mortos:
                self._cache = None
        return len(mortos)

    def _matriz(self) -> tuple[list[str], list[str], np.ndarray]:
        with self._trava:
            if self._cache is None:
                linhas = self._con.execute(
                    "SELECT chunk_id, documento, vetor FROM vetores WHERE espaco = ? ORDER BY chunk_id",
                    (self.espaco,)).fetchall()
                ids = [r[0] for r in linhas]
                docs = [r[1] for r in linhas]
                matriz = (np.vstack([np.frombuffer(r[2], dtype=np.float32) for r in linhas])
                          if linhas else np.zeros((0, DIMENSAO), dtype=np.float32))
                self._cache = (ids, docs, matriz)
            return self._cache

    def buscar(self, vetor: np.ndarray, limite: int = 50, documentos=None) -> list[tuple[str, float]]:
        """(chunk_id, cosseno), do mais parecido para o menos. Empate desempata pelo id."""
        ids, docs, matriz = self._matriz()
        if not ids:
            return []
        cossenos = matriz @ np.asarray(vetor, dtype=np.float32).reshape(-1)
        so = set(n for n in (documentos or []) if n)
        ordem = sorted((i for i in range(len(ids)) if not so or docs[i] in so),
                       key=lambda i: (-float(cossenos[i]), ids[i]))[:limite]
        return [(ids[i], float(cossenos[i])) for i in ordem]

    def vetor_de(self, chunk_id: str) -> np.ndarray | None:
        ids, _, matriz = self._matriz()
        try:
            return matriz[ids.index(chunk_id)]
        except ValueError:
            return None

    def quantos(self) -> int:
        return len(self._matriz()[0])

    def fechar(self) -> None:
        with self._trava:
            self._con.close()


class Backfill:
    """
    Vetoriza o que falta, em segundo plano, cedendo a vez para as perguntas.

    O modelo de vetores e o de conversa dividem a mesma CPU: com alguem
    esperando resposta, o backfill para e espera a fila do modelo (R4)
    esvaziar. Um lote de cada vez, para a pergunta nunca esperar mais que um
    lote.
    """

    def __init__(self, indice: IndiceDenso, vetorizador: Vetorizador, ceder=None) -> None:
        self.indice = indice
        self.vetorizador = vetorizador
        self._ceder = ceder or (lambda: None)
        self._fio: threading.Thread | None = None
        self.estado: dict = {"andando": False, "feitos": 0, "total": 0, "erro": ""}

    def iniciar(self, chunks) -> None:
        if self._fio and self._fio.is_alive():
            return
        faltam = self.indice.faltam(chunks)
        self.indice.podar(chunks)
        if not faltam:
            return
        self.estado = {"andando": True, "feitos": 0, "total": len(faltam), "erro": ""}
        self._fio = threading.Thread(target=self._rodar, args=(faltam,), name="vetores", daemon=True)
        self._fio.start()

    def _rodar(self, faltam) -> None:
        try:
            for i in range(0, len(faltam), LOTE):
                self._ceder()
                lote = faltam[i:i + LOTE]
                matriz = self.vetorizador.vetores([c.text_embed or c.text for c in lote])
                self.indice.gravar(lote, matriz)
                self.estado["feitos"] = min(len(faltam), i + LOTE)
        except Exception as exc:  # noqa: BLE001 - o backfill para; a busca lexica continua
            self.estado["erro"] = str(exc)[:200]
        finally:
            self.estado["andando"] = False
            self.estado["quando"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    def esperar(self, limite_s: float = 600) -> None:
        if self._fio:
            self._fio.join(limite_s)
