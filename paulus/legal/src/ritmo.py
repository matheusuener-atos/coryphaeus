"""
O ritmo desta máquina, medido.

A tela ficava parada uns oitenta segundos com uma barra em 25/25 — que não era
progresso, era enfeite: os dois números chegavam juntos. E o tempo todo o
programa não dizia o que estava fazendo.

O que está acontecendo naquele silêncio tem nome: o modelo está **lendo** o
prompt inteiro antes de escrever a primeira palavra. O Ollama não emite nada
nessa fase, então não há progresso a relatar — mas há duas coisas honestas a
dizer: o tamanho do que está sendo lido, e quanto tempo leituras desse tamanho
levaram *neste computador*.

Daí este módulo. Ele guarda o que já aconteceu e responde duas perguntas:

  - quantos caracteres por segundo esta máquina lê
  - quantas palavras por segundo ela escreve

Nenhum número sai daqui sem ter sido medido antes. Sem histórico, o módulo diz
que não sabe, e a tela mostra só o que está acontecendo — que já é melhor do
que uma barra cheia parada.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from statistics import median

# Quantas leituras guardar. O suficiente para a mediana não pular com um
# outlier, e pouco o bastante para acompanhar a máquina quando ela muda —
# trocar de modelo muda o ritmo, e o número velho vira mentira em uma semana.
LEMBRAR = 25

# Abaixo disto a medida é ruído: modelo carregando, cache quente, o sistema
# fazendo outra coisa.
MINIMO_CHARS = 800
MINIMO_SEGUNDOS = 0.4


class Ritmo:
    def __init__(self, caminho: Path) -> None:
        self.caminho = Path(caminho)
        self._trava = threading.Lock()
        self.leituras: list[dict] = []
        self._carregar()

    def _carregar(self) -> None:
        if not self.caminho.exists():
            return
        try:
            bruto = json.loads(self.caminho.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if isinstance(bruto, dict):
            self.leituras = [x for x in bruto.get("leituras", []) if isinstance(x, dict)]

    def _salvar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        payload = {"versao": 1, "leituras": self.leituras[-LEMBRAR:]}
        try:
            self.caminho.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    # ---------------------------------------------------------- registrar

    def anotar(self, *, modelo: str, caracteres: int, segundos_lendo: float,
               palavras: int = 0, segundos_escrevendo: float = 0.0) -> None:
        """
        Guarda uma leitura que aconteceu de verdade.

        O modelo entra junto porque o ritmo é dele: a mesma máquina lê em
        velocidades diferentes com Q4 e com Q8, e misturar os dois daria uma
        média que não descreve nenhum.
        """
        if caracteres < MINIMO_CHARS or segundos_lendo < MINIMO_SEGUNDOS:
            return
        with self._trava:
            self.leituras.append({
                "modelo": modelo,
                "caracteres": int(caracteres),
                "lendo": round(float(segundos_lendo), 2),
                "palavras": int(palavras),
                "escrevendo": round(float(segundos_escrevendo), 2),
            })
            self.leituras = self.leituras[-LEMBRAR:]
        self._salvar()

    # ------------------------------------------------------------- prever

    def _de(self, modelo: str) -> list[dict]:
        return [x for x in self.leituras if x.get("modelo") == modelo]

    def chars_por_segundo(self, modelo: str) -> float:
        """Quanto esta máquina lê, pela mediana do que já leu. Zero se não sabe."""
        taxas = [x["caracteres"] / x["lendo"] for x in self._de(modelo) if x.get("lendo")]
        return median(taxas) if taxas else 0.0

    def palavras_por_segundo(self, modelo: str) -> float:
        taxas = [x["palavras"] / x["escrevendo"]
                 for x in self._de(modelo)
                 if x.get("escrevendo") and x.get("palavras")]
        return median(taxas) if taxas else 0.0

    def previsao_de_leitura(self, modelo: str, caracteres: int) -> dict:
        """
        Quanto deve levar para ler este tanto — e de onde saiu esse palpite.

        Devolve `sabe=False` quando não há histórico. A tela precisa saber a
        diferença: um número sem medição atrás é pior que nenhum, porque
        parece igual.
        """
        taxa = self.chars_por_segundo(modelo)
        quantas = len(self._de(modelo))
        if not taxa:
            return {"sabe": False, "segundos": 0, "medicoes": quantas}
        return {
            "sabe": True,
            "segundos": max(1, round(caracteres / taxa)),
            "medicoes": quantas,
            "chars_por_segundo": round(taxa),
        }

    def para_tela(self, modelo: str) -> dict:
        return {
            "modelo": modelo,
            "medicoes": len(self._de(modelo)),
            "chars_por_segundo": round(self.chars_por_segundo(modelo)),
            "palavras_por_segundo": round(self.palavras_por_segundo(modelo), 1),
        }
