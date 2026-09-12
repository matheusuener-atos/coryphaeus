"""
PAULUS - Transcricao de audio.

Um modelo de voz que roda nesta maquina: Whisper, pelo faster-whisper
(CTranslate2 em CPU, int8). O audio nao sai do computador. Os modelos ficam
em data/modelos/whisper; baixar e uma acao explicita, feita uma vez com
internet. Transcrever e um trabalho de fundo, um por vez, porque ocupa os
nucleos todos - a tela mostra o andamento e continua usavel.

Dois tamanhos, escolhidos pela maquina de quem usa:
  turbo  large-v3-turbo, ~1,6 GB - o que acerta mais em portugues;
  small  ~0,5 GB - para maquina fraca ou nota de voz curta.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

MODELOS = {
    "turbo": {"alias": "large-v3-turbo", "rotulo": "Whisper large-v3-turbo", "mb": 1600,
              "nota": "acerta mais em português; precisa de ~2 GB de memória"},
    "small": {"alias": "small", "rotulo": "Whisper small", "mb": 480,
              "nota": "rápido e leve; erra mais em nomes e números"},
}
PADRAO = "turbo"
ARQUIVOS_DO_MODELO = ("model.bin", "config.json")


class Transcritor:
    def __init__(self, pasta: Path, modelo: str = PADRAO, nucleos: int = 0) -> None:
        self.pasta = Path(pasta)
        self.modelo = modelo if modelo in MODELOS else PADRAO
        # Metade dos nucleos logicos: o resto fica para a tela e o Ollama.
        self.nucleos = nucleos or max(1, (os.cpu_count() or 2) // 2)
        self._carregado = None
        self._nome_carregado = ""
        self._trava = threading.Lock()
        self.baixando = ""

    # ---------------------------------------------------------------- estado

    def pasta_de(self, nome: str) -> Path:
        return self.pasta / nome

    def instalado(self, nome: str | None = None) -> bool:
        p = self.pasta_de(nome or self.modelo)
        return all((p / a).exists() for a in ARQUIVOS_DO_MODELO)

    def tamanho_mb(self, nome: str) -> int:
        p = self.pasta_de(nome)
        if not p.exists():
            return 0
        return int(sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1_000_000)

    def situacao(self) -> dict:
        """O que a tela precisa saber: se da para transcrever e com o que."""
        return {
            "disponivel": self.instalado(),
            "modelo": self.modelo,
            "rotulo": MODELOS[self.modelo]["rotulo"],
            "pasta": str(self.pasta),
            "nucleos": self.nucleos,
            "baixando": self.baixando,
            # O andamento do download e o que ja esta no disco: o Hugging Face
            # grava aos pedacos na propria pasta.
            "baixado_mb": self.tamanho_mb(self.baixando) if self.baixando else 0,
            "modelos": [
                {"nome": n, "rotulo": m["rotulo"], "mb": m["mb"], "nota": m["nota"], "instalado": self.instalado(n)}
                for n, m in MODELOS.items()
            ],
        }

    def escolher(self, nome: str) -> None:
        if nome not in MODELOS:
            raise ValueError("modelo desconhecido: " + nome)
        with self._trava:
            self.modelo = nome
            if self._nome_carregado != nome:
                self._carregado = None
                self._nome_carregado = ""

    # ---------------------------------------------------------------- baixar

    def baixar(self, nome: str | None = None) -> Path:
        """Baixa o modelo do Hugging Face para a pasta de dados. Precisa de internet uma vez."""
        nome = nome or self.modelo
        if nome not in MODELOS:
            raise ValueError("modelo desconhecido: " + nome)
        from faster_whisper import download_model

        self.baixando = nome
        try:
            destino = self.pasta_de(nome)
            destino.mkdir(parents=True, exist_ok=True)
            download_model(MODELOS[nome]["alias"], output_dir=str(destino))
        finally:
            self.baixando = ""
        return self.pasta_de(nome)

    # ------------------------------------------------------------ transcrever

    def carregar(self):
        with self._trava:
            if self._carregado is not None and self._nome_carregado == self.modelo:
                return self._carregado
            if not self.instalado():
                raise RuntimeError("o modelo de voz " + MODELOS[self.modelo]["rotulo"] + " não está baixado nesta máquina")
            from faster_whisper import WhisperModel

            self._carregado = WhisperModel(
                str(self.pasta_de(self.modelo)), device="cpu", compute_type="int8",
                cpu_threads=self.nucleos, local_files_only=True,
            )
            self._nome_carregado = self.modelo
            return self._carregado

    def descarregar(self) -> None:
        with self._trava:
            self._carregado = None
            self._nome_carregado = ""

    def transcrever(self, caminho: Path, idioma: str = "pt", progresso=None) -> dict:
        """
        Devolve os trechos com inicio, fim e texto, mais a duracao e o tempo gasto.

        `progresso(fracao)` e chamado a cada trecho, para a tela mostrar o
        andamento; a fracao e o fim do trecho sobre a duracao do audio.
        """
        modelo = self.carregar()
        comeco = time.time()
        segmentos, info = modelo.transcribe(
            str(caminho), language=idioma or None, beam_size=5, vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500}, condition_on_previous_text=False,
        )
        trechos = []
        duracao = float(info.duration or 0)
        for s in segmentos:
            texto = s.text.strip()
            if not texto:
                continue
            # O Whisper inventa uma frase no silencio do fim ("O que e isso?"
            # depois do audio acabar) e em trechos que ele mesmo acha que nao
            # tem fala. Esses trechos nao entram.
            if duracao and (float(s.start) >= duracao - 1.0 or float(s.end) > duracao + 1.0):
                continue
            if float(getattr(s, "no_speech_prob", 0) or 0) > 0.8 and float(getattr(s, "avg_logprob", 0) or 0) < -1.0:
                continue
            trechos.append({"inicio": round(float(s.start), 2), "fim": round(float(s.end), 2), "texto": texto})
            if progresso and duracao:
                progresso(min(1.0, float(s.end) / duracao))
        return {
            "trechos": trechos,
            "idioma": info.language,
            "duracao": round(duracao, 2),
            "modelo": self.modelo,
            "tempo": round(time.time() - comeco, 1),
            "palavras": sum(len(t["texto"].split()) for t in trechos),
        }


def texto_da_transcricao(trechos: list[dict]) -> str:
    return "\n".join(t["texto"] for t in trechos)


if __name__ == "__main__":
    # python src/transcricao.py baixar [turbo|small]
    # python src/transcricao.py transcrever caminho.wav [turbo|small]
    import json
    import sys

    raiz = Path(__file__).resolve().parent.parent
    t = Transcritor(raiz / "data" / "modelos" / "whisper")
    if len(sys.argv) >= 2 and sys.argv[1] == "baixar":
        nome = sys.argv[2] if len(sys.argv) > 2 else PADRAO
        print("baixando", MODELOS[nome]["rotulo"], "para", t.pasta_de(nome))
        t.baixar(nome)
        print("pronto")
    elif len(sys.argv) >= 3 and sys.argv[1] == "transcrever":
        if len(sys.argv) > 3:
            t.escolher(sys.argv[3])
        r = t.transcrever(Path(sys.argv[2]), progresso=lambda f: print(f"\r{f * 100:5.1f}%", end=""))
        print()
        print(json.dumps({k: v for k, v in r.items() if k != "trechos"}, ensure_ascii=False))
        for x in r["trechos"]:
            print(f"[{x['inicio']:7.2f} - {x['fim']:7.2f}] {x['texto']}")
    else:
        print(json.dumps(t.situacao(), ensure_ascii=False, indent=2))
