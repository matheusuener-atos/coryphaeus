"""
Uma linha por pergunta, para medir o que muda de uma etapa para outra (I1).

`data/medicao/perguntas.jsonl`: modelo, digest, janela, tokens lidos e
escritos, tempos de leitura e de escrita, o caminho que a pergunta tomou
(`tudo` | `busca` | `foco` | `nivel0` | `programa` | `regra`), o nivel, os
trechos, os caracteres de contexto, se o texto foi cortado e se o nivel 0
desistiu e a pergunta refez o caminho de sempre.

O ARQUIVO E LOCAL E NUNCA E ENVIADO. Nao guarda o texto da pergunta nem da
resposta: so numeros e o caminho - o que basta para comparar antes e depois
sem copiar documento de cliente para um segundo lugar.

`ia.medir` desligado nao escreve nada.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path

CAMINHOS = ("tudo", "busca", "foco", "nivel0", "programa", "regra")

# Os campos, na ordem em que saem no arquivo. Faltando algum na chamada, vai
# nulo: uma linha com buraco ainda compara; uma linha que nao foi escrita,
# nao.
CAMPOS = ("modelo", "digest", "num_ctx", "prompt_eval_count", "eval_count", "lendo_s", "escrevendo_s",
          "total_s", "caminho", "nivel", "trechos", "caracteres", "truncou", "fallback")


class Medicao:
    def __init__(self, pasta: Path | str, *, ligada=lambda: True, digest=None) -> None:
        self.arquivo = Path(pasta) / "perguntas.jsonl"
        self._ligada = ligada
        # O digest vem do Ollama (/api/tags): perguntado uma vez por modelo a
        # cada cinco minutos, e nao a cada pergunta.
        self._digest = digest
        self._digests: dict[str, tuple[float, str]] = {}
        self._trava = threading.Lock()

    def digest_de(self, modelo: str) -> str:
        if not self._digest or not modelo:
            return ""
        quando, valor = self._digests.get(modelo, (0.0, ""))
        if time.time() - quando > 300:
            try:
                valor = self._digest(modelo) or ""
            except Exception:  # noqa: BLE001 - sem digest a linha sai mesmo assim
                valor = ""
            self._digests[modelo] = (time.time(), valor)
        return valor

    def pergunta(self, **campos) -> dict | None:
        """Grava uma linha. Devolve o que gravou (ou None, desligada)."""
        if not self._ligada():
            return None
        linha = {"quando": datetime.now().isoformat(timespec="seconds")}
        for nome in CAMPOS:
            linha[nome] = campos.get(nome)
        if not linha["digest"] and linha["modelo"]:
            linha["digest"] = self.digest_de(linha["modelo"])
        linha["truncou"] = bool(linha["truncou"])
        linha["fallback"] = bool(linha["fallback"])
        try:
            with self._trava:
                self.arquivo.parent.mkdir(parents=True, exist_ok=True)
                with self.arquivo.open("a", encoding="utf-8") as saida:
                    saida.write(json.dumps(linha, ensure_ascii=False) + "\n")
        except OSError:
            # Medir nunca pode derrubar a resposta.
            return None
        return linha

    def linhas(self) -> list[dict]:
        try:
            texto = self.arquivo.read_text(encoding="utf-8")
        except OSError:
            return []
        saida = []
        for bruto in texto.splitlines():
            try:
                saida.append(json.loads(bruto))
            except json.JSONDecodeError:
                continue
        return saida
