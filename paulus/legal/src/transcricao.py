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

Ao vivo: o navegador manda o audio em pedacos (PCM 16 kHz, 16 bits, mono)
e o servidor junta num buffer por sessao. A cada chegada, o detector de fala
(Silero, que vem com o faster-whisper) procura uma pausa; o que esta antes
da pausa vai para o modelo e vira trechos com o minuto. Cortar na pausa, e
nao no relogio, e o que evita palavra partida ao meio.
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
TAXA = 16000


class SessaoAoVivo:
    """O audio de uma gravacao em andamento, chegando aos pedacos."""

    def __init__(self, id_: str, modelo: str) -> None:
        import numpy as np

        self.id = id_
        self.modelo = modelo
        self.buffer = np.zeros(0, dtype=np.float32)
        self.offset = 0.0     # segundos ja consumidos antes do inicio do buffer
        self.total = 0.0      # segundos recebidos
        self.trechos: list[dict] = []
        self.criada = time.time()
        self.ultima = time.time()
        self.trava = threading.Lock()
        self.fechada = False

    def situacao(self) -> dict:
        return {"sessao": self.id, "modelo": self.modelo, "total_s": round(self.total, 1),
                "pendente_s": round(len(self.buffer) / TAXA, 1), "trechos_quantos": len(self.trechos), "fechada": self.fechada}


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

    # ---------------------------------------------------------------- ao vivo

    def transcrever_pedaco(self, audio, prompt: str = "") -> list[dict]:
        """Um pedaco curto (segundos) que ja esta em float32 a 16 kHz."""
        modelo = self.carregar()
        duracao = len(audio) / TAXA
        segmentos, _info = modelo.transcribe(
            audio, language="pt", beam_size=3, vad_filter=False,
            condition_on_previous_text=False, initial_prompt=prompt or None,
        )
        out = []
        for s in segmentos:
            texto = s.text.strip()
            if not texto or float(s.start) >= duracao:
                continue
            if float(getattr(s, "no_speech_prob", 0) or 0) > 0.8 and float(getattr(s, "avg_logprob", 0) or 0) < -1.0:
                continue
            out.append({"inicio": round(float(s.start), 2), "fim": round(min(float(s.end), duracao), 2), "texto": texto})
        return out

    def ao_vivo_receber(self, sessao: SessaoAoVivo, pcm: bytes) -> list[dict]:
        """Mais um pedaco de audio chegou; devolve os trechos novos, se uma pausa permitiu transcrever."""
        import numpy as np

        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        with sessao.trava:
            sessao.ultima = time.time()
            sessao.buffer = np.concatenate([sessao.buffer, audio])
            sessao.total += len(audio) / TAXA
            return self._consumir(sessao, forcar=False)

    def ao_vivo_fim(self, sessao: SessaoAoVivo) -> list[dict]:
        """A gravacao parou: transcreve o que sobrou no buffer e fecha a sessao."""
        with sessao.trava:
            novos = self._consumir(sessao, forcar=True) if not sessao.fechada else []
            sessao.fechada = True
            return novos

    def _consumir(self, sessao: SessaoAoVivo, forcar: bool) -> list[dict]:
        from faster_whisper.vad import VadOptions, get_speech_timestamps

        n = len(sessao.buffer)
        if n == 0 or (not forcar and n < TAXA * 2):
            return []
        fala = get_speech_timestamps(
            sessao.buffer, VadOptions(min_silence_duration_ms=400, speech_pad_ms=150, min_speech_duration_ms=200))
        if not fala:
            # So silencio: joga fora, guardando meio segundo caso a fala comece no fim.
            guardar = 0 if forcar else TAXA // 2
            if n > guardar:
                sessao.offset += (n - guardar) / TAXA
                sessao.buffer = sessao.buffer[n - guardar:]
            return []
        ultimo = fala[-1]
        if forcar:
            corte = n
        elif n - ultimo["end"] >= TAXA // 2:
            corte = n                      # houve pausa depois da ultima fala: tudo esta completo
        elif len(fala) >= 2:
            corte = ultimo["start"]        # a ultima fala ainda esta em andamento: corta antes dela
        elif n >= TAXA * 15:
            corte = n                      # fala longa sem pausa: corta assim mesmo
        else:
            return []
        if corte <= 0:
            return []
        pedaco = sessao.buffer[:corte]
        prompt = " ".join(t["texto"] for t in sessao.trechos[-2:])[-200:]
        base = sessao.offset
        novos = [{"inicio": round(base + t["inicio"], 2), "fim": round(base + t["fim"], 2), "texto": t["texto"]}
                 for t in self.transcrever_pedaco(pedaco, prompt)]
        # O prompt as vezes volta repetido como se fosse fala nova: fora.
        if novos and sessao.trechos and novos[0]["texto"] == sessao.trechos[-1]["texto"]:
            novos.pop(0)
        sessao.trechos.extend(novos)
        sessao.offset += corte / TAXA
        sessao.buffer = sessao.buffer[corte:]
        return novos


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
