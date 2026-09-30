"""
Julgamento tipado: o modelo decide, não escreve.

Até aqui o modelo local era usado de um jeito só - escrever. Pedia-se uma
resposta, ou um JSON, e o que voltava era texto a conferir: podia vir fora do
formato, com um campo inventado, e custava um minuto em CPU. Para decidir
"esta frase é sobre o Financeiro ou sobre um contrato?" isso é o instrumento
errado.

Este módulo é o outro instrumento, no estilo dos modelos "System One" (o Jev,
da TypeSafe): a pergunta tem respostas fechadas, cada uma com uma letra, e o
modelo gera UM token. O Ollama devolve a probabilidade de cada letra
(`logprobs`), e a resposta é a distribuição inteira - não um palpite solto.
Três formas, as mesmas do Jev:

- **escolha** - uma opção de um conjunto dado ("qual tela resolve isto?");
- **sim ou não** - a probabilidade de uma condição valer;
- **nota** - a posição numa escala de níveis descritos.

Quatro decisões:

**O código é dono do fluxo.** O modelo não chama ferramenta, não monta texto
e não decide o que acontece depois: ele responde a pergunta fechada que o
código fez, e o código decide com o número na mão.

**Uma letra, não uma frase.** Gerar um token custa a leitura do prompt e mais
nada. Medido nesta máquina (llama3.2:3b, CPU): ~6 s com o modelo frio, contra
~60 s de uma resposta escrita.

**A parte fixa vem primeiro.** O Ollama reaproveita o que já leu quando o
começo do prompt se repete. O catálogo e as opções vão antes; a frase da
pessoa, que muda, vai no fim.

**Sem resposta é sem resposta.** Ollama fora do ar, versão sem `logprobs`,
modelo que respondeu fora das letras: o julgamento devolve None, e quem
chamou segue o caminho de antes. Nunca vira "a primeira opção".
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Callable

import requests

LETRAS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Abaixo disto, a massa de probabilidade que caiu em letras válidas é pouca:
# o modelo quis escrever outra coisa ("Eu", "A resposta"...). A distribuição
# renormalizada sobre as letras seria um número sem lastro.
MASSA_MINIMA = 0.5

SISTEMA = (
    "Você é um classificador. Leia o estado e a pergunta e responda com UMA "
    "letra maiúscula, a da opção correta. Não escreva mais nada."
)


def _host() -> str:
    bruto = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").strip()
    if not bruto.startswith("http"):
        bruto = "http://" + bruto
    return bruto.replace("0.0.0.0", "127.0.0.1").rstrip("/")


# --------------------------------------------------------------- respostas


@dataclass
class Escolha:
    """Uma opção de um conjunto, com a distribuição inteira."""
    valor: str                                   # id da opção mais provável
    probabilidades: dict[str, float] = field(default_factory=dict)
    confianca: float = 0.0                       # 1 - entropia normalizada

    @property
    def p(self) -> float:
        return self.probabilidades.get(self.valor, 0.0)

    def to_dict(self) -> dict:
        return {"valor": self.valor, "p": round(self.p, 3), "confianca": round(self.confianca, 3),
                "probabilidades": {k: round(v, 3) for k, v in self.probabilidades.items()}}


@dataclass
class Nota:
    """Posição numa escala: 0 é o primeiro nível, 1 o último."""
    valor: float
    probabilidades: list[float] = field(default_factory=list)
    confianca: float = 0.0


def _confianca(ps: list[float]) -> float:
    """Concentração da distribuição: 1 é certeza, 0 é tudo igual."""
    ps = [p for p in ps if p > 0]
    if len(ps) < 2:
        return 1.0
    entropia = -sum(p * math.log(p) for p in ps)
    return max(0.0, 1.0 - entropia / math.log(len(ps)))


def distribuicao(top_logprobs: list[dict], letras: str) -> dict[str, float] | None:
    """
    Probabilidade de cada letra, a partir dos candidatos do primeiro token.

    " B", "B" e "B)" são a mesma resposta: o token é limpo antes de contar.
    Letra que não apareceu entre os candidatos fica com zero - o Ollama só
    devolve os 20 mais prováveis, e fora deles a probabilidade é desprezível.
    """
    massa: dict[str, float] = {}
    for cand in top_logprobs or []:
        token = str(cand.get("token", "")).strip().strip(").:").upper()
        if len(token) == 1 and token in letras:
            massa[token] = massa.get(token, 0.0) + math.exp(float(cand.get("logprob", -99)))
    total = sum(massa.values())
    if total < MASSA_MINIMA:
        return None
    return {letra: massa.get(letra, 0.0) / total for letra in letras}


# ------------------------------------------------------------------ o juiz


class Juiz:
    """
    Faz perguntas fechadas ao modelo local e devolve respostas tipadas.

    `post` existe para o teste trocar o HTTP; em uso é `requests.post`.
    """

    def __init__(self, model: str = "", host: str = "", *, timeout: int = 90,
                 num_ctx: int = 4096, keep_alive: str = "", sem_pensar: bool = False,
                 post: Callable | None = None) -> None:
        self.model = model or os.getenv("PAULUS_MODEL", "llama3.2:3b")
        self.host = host or _host()
        self.timeout = timeout
        # A mesma janela e o mesmo keep_alive da conversa (src/inferencia.py):
        # o juiz roda no modelo que responde, e janela diferente recarrega.
        self.num_ctx = num_ctx
        self.keep_alive = keep_alive
        # `think: false` so para modelo que declara a capacidade de pensar -
        # num juiz de um token, pensar antes gastaria o token inteiro.
        self.sem_pensar = sem_pensar
        self._post = post or requests.post
        self._memoria: OrderedDict[str, dict[str, float] | None] = OrderedDict()
        # O que o último julgamento custou, para a tela e para a medição.
        self.ultima_medida: dict = {}

    # -------------------------------------------------------------- baixo

    def _letras(self, usuario: str, letras: str) -> dict[str, float] | None:
        chave = hashlib.sha1((self.model + "\0" + usuario).encode("utf-8")).hexdigest()
        if chave in self._memoria:
            self._memoria.move_to_end(chave)
            self.ultima_medida = {"do_cache": True, "segundos": 0.0}
            return self._memoria[chave]
        # F1: com alguem na fila do modelo, o juiz nao espera a vez - esperar
        # atras de uma resposta de 34 s por uma letra so atrasaria a pergunta,
        # e sem juiz a regra decide, como quando ele passa dos 20 s.
        import fila_modelo

        fila = fila_modelo.instalada()
        if fila is not None and fila.ocupada_por_outro():
            self.ultima_medida = {"fila_ocupada": True, "segundos": 0.0}
            return None

        payload = {
            "model": self.model,
            "stream": False,
            "logprobs": True,
            "top_logprobs": 20,
            # Temperatura zero e semente fixa: a mesma pergunta, a mesma
            # distribuição. Um token só - a letra.
            "options": {"temperature": 0, "seed": 7, "num_predict": 1, "num_ctx": self.num_ctx},
            "messages": [
                {"role": "system", "content": SISTEMA},
                {"role": "user", "content": usuario},
            ],
        }
        if self.keep_alive:
            payload["keep_alive"] = self.keep_alive
        if self.sem_pensar:
            import inferencia

            if inferencia.pensa(self.host, self.model):
                payload["think"] = False
        import time

        comeco = time.time()
        try:
            resp = self._post(f"{self.host}/api/chat", json=payload, timeout=self.timeout)
            resp.raise_for_status()
            dado = resp.json()
        except Exception:
            self.ultima_medida = {"erro": True, "segundos": round(time.time() - comeco, 2)}
            return None

        tokens = dado.get("logprobs") or []
        dist = distribuicao(tokens[0].get("top_logprobs", []), letras) if tokens else None
        self.ultima_medida = {
            "segundos": round(time.time() - comeco, 2),
            "tokens_lidos": dado.get("prompt_eval_count", 0),
            "sem_logprobs": not tokens,
        }
        self._memoria[chave] = dist
        if len(self._memoria) > 256:
            self._memoria.popitem(last=False)
        return dist

    @staticmethod
    def _montar(estado, instrucao: str, opcoes: list[str], entrada: str) -> str:
        """
        Estado, instrução e opções primeiro (a parte que se repete), a frase
        da pessoa por último. Estado estruturado vai como JSON com nomes.
        """
        partes = []
        if estado:
            texto = estado if isinstance(estado, str) else json.dumps(estado, ensure_ascii=False, indent=1)
            partes.append("ESTADO:\n" + texto)
        partes.append("PERGUNTA: " + instrucao.strip())
        partes.append("OPÇÕES:\n" + "\n".join(f"{LETRAS[i]}) {o}" for i, o in enumerate(opcoes)))
        if entrada:
            partes.append("ENTRADA: " + entrada.strip())
        partes.append("Responda só com a letra.")
        return "\n\n".join(partes)

    # ------------------------------------------------------------ público

    def escolher(self, instrucao: str, opcoes: list[tuple[str, str]], *,
                 estado=None, entrada: str = "", trocar_ordem: bool = False) -> Escolha | None:
        """
        Uma opção de `opcoes` - pares (id, descrição). A descrição é o que o
        modelo lê; o id é o que o código recebe. Inclua a opção de "nenhuma"
        quando nada pode servir: o modelo não escolhe o que não está na lista.

        `trocar_ordem` faz a mesma pergunta com as opções em cada rotação e
        tira a média. Um modelo pequeno tem viés de posição - medido aqui: o
        llama3.2:3b dava ~0,55 para a letra A em 22 de 23 frases, fosse qual
        fosse a opção. Custa uma chamada por opção; use com poucas opções.
        """
        if not 2 <= len(opcoes) <= len(LETRAS):
            raise ValueError("escolha precisa de 2 a 26 opções")
        letras = LETRAS[: len(opcoes)]
        rotacoes = range(len(opcoes)) if trocar_ordem else range(1)
        soma = {id_: 0.0 for id_, _ in opcoes}
        segundos = 0.0
        for r in rotacoes:
            ordem = opcoes[r:] + opcoes[:r]
            dist = self._letras(self._montar(estado, instrucao, [d for _, d in ordem], entrada), letras)
            if dist is None:
                return None
            segundos += self.ultima_medida.get("segundos", 0.0)
            for i, (id_, _) in enumerate(ordem):
                soma[id_] += dist[letras[i]]
        self.ultima_medida["segundos"] = round(segundos, 2)
        probs = {id_: v / len(rotacoes) for id_, v in soma.items()}
        melhor = max(probs, key=probs.get)
        return Escolha(valor=melhor, probabilidades=probs, confianca=_confianca(list(probs.values())))

    def sim_ou_nao(self, pergunta: str, *, estado=None, entrada: str = "") -> float | None:
        """Probabilidade de a resposta ser sim. Perto de 0,5 é empate, não "meio"."""
        dist = self._letras(self._montar(estado, pergunta, ["Sim", "Não"], entrada), "AB")
        return None if dist is None else dist["A"]

    def nota(self, instrucao: str, niveis: list[str], *, estado=None, entrada: str = "") -> Nota | None:
        """
        Posição esperada numa escala de níveis descritos, do menor ao maior.
        Cada nível descreve uma situação concreta e se sustenta sozinho.
        """
        if not 2 <= len(niveis) <= 10:
            raise ValueError("nota precisa de 2 a 10 níveis")
        letras = LETRAS[: len(niveis)]
        dist = self._letras(self._montar(estado, instrucao, niveis, entrada), letras)
        if dist is None:
            return None
        ps = [dist[l] for l in letras]
        esperado = sum(i * p for i, p in enumerate(ps)) / (len(ps) - 1)
        return Nota(valor=esperado, probabilidades=ps, confianca=_confianca(ps))
