"""
O que chega ao modelo junto com o texto: temperatura, semente, janela, teto
de resposta e quanto tempo ele fica carregado (I1).

Antes desta etapa os parametros nao chegavam ao modelo. `config/extratores.yaml`
dizia temperatura 0 e semente 42, mas a conversa mandava 0,1 e semente
nenhuma: a mesma pergunta, duas vezes, podia dar duas respostas - e nao
havia como saber se uma troca de prompt tinha melhorado ou so sorteado outra
resposta. A janela (`num_ctx`) crescia com o acervo, e cada mudanca dela
faz o Ollama recarregar o modelo: um documento novo custava uma recarga na
pergunta seguinte.

Daqui para frente:

- as opcoes vem do perfil `conversa` do catalogo (config/extratores.yaml);
  o NOME do modelo continua vindo da delegacao por tarefa (src/modelos.py) -
  trocar de modelo e configuracao, nao codigo;
- a janela e fixa por modelo: `ia.janela_por_modelo` nas preferencias, senao
  a do perfil (16384 nesta etapa, que ainda le o acervo inteiro quando cabe);
- `ia.opcoes_fixas` desligado volta ao comportamento de antes (temperatura
  0,1 e nada mais) - a chave existe para dar para voltar atras.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field, replace

import requests

# O teto de resposta por tarefa. Conversa: 700 tokens sao ~500 palavras,
# mais que qualquer resposta do banco de provas. JSON: as ferramentas e a
# folha do documento devolvem objetos pequenos. Juiz: uma letra.
NUM_PREDICT = {"conversa": 700, "json": 800, "juiz": 1}

# Trinta minutos carregado: o padrao do Ollama sao cinco, e a pergunta
# seguinte de quem esta lendo um contrato quase sempre vem depois disso -
# pagando a carga do modelo de novo (~9 s nesta maquina).
KEEP_ALIVE = "30m"

JANELA_PADRAO = 16384

# O Ollama nao avisa quando corta: com o prompt maior que a janela, ele
# descarta o comeco e responde com o resto. Chegar a menos de 64 tokens do
# fim da janela e o sinal de que isso aconteceu.
FOLGA_DO_CORTE = 64


@dataclass
class Opcoes:
    """As opcoes de uma chamada ao modelo, ja resolvidas."""

    temperature: float = 0.0
    seed: int | None = 42
    keep_alive: str = KEEP_ALIVE
    num_ctx: int = JANELA_PADRAO
    num_predict: dict = field(default_factory=lambda: dict(NUM_PREDICT))
    # `think: false` para o modelo que pensa antes de responder (ver `pensa`).
    desligar_pensar: bool = True

    def options(self, tarefa: str = "") -> dict:
        """O bloco `options` do /api/chat para esta tarefa."""
        saida: dict = {"temperature": self.temperature, "num_ctx": self.num_ctx}
        if self.seed is not None:
            saida["seed"] = self.seed
        teto = self.num_predict.get(tarefa) if tarefa else None
        if teto:
            saida["num_predict"] = teto
        return saida


# As opcoes de antes da I1, para quem desligar `ia.opcoes_fixas`.
LEGADO = Opcoes(temperature=0.1, seed=None, keep_alive="", num_predict={}, desligar_pensar=False)


def opcoes(catalogo=None, prefs: dict | None = None, modelo: str = "") -> Opcoes:
    """
    As opcoes da conversa para `modelo`, do catalogo e das preferencias.

    Sem catalogo legivel, os valores deste modulo: o programa nao pode parar
    de responder porque um YAML ficou torto.
    """
    ia = (prefs or {}).get("ia") or {}
    perfil = getattr(catalogo, "modelos", {}).get("conversa") if catalogo is not None else None
    janela = int((ia.get("janela_por_modelo") or {}).get(modelo) or 0) or \
        int(getattr(perfil, "num_ctx", 0) or 0) or JANELA_PADRAO
    if not ia.get("opcoes_fixas", True):
        return replace(LEGADO, num_ctx=janela, num_predict={})
    teto = dict(NUM_PREDICT)
    teto.update({k: int(v) for k, v in (getattr(perfil, "num_predict", None) or {}).items() if v})
    return Opcoes(
        temperature=float(getattr(perfil, "temperature", 0.0) or 0.0),
        seed=int(getattr(perfil, "seed", 42) or 42),
        keep_alive=str(getattr(perfil, "keep_alive", "") or KEEP_ALIVE),
        num_ctx=janela,
        num_predict=teto,
    )


def truncou(prompt_eval_count: int, num_ctx: int) -> bool:
    """O prompt encostou no fim da janela: o comeco ficou de fora."""
    return bool(prompt_eval_count and num_ctx and prompt_eval_count >= num_ctx - FOLGA_DO_CORTE)


# ------------------------------------------------------------ capacidades

_CAPACIDADES: dict[tuple[str, str], frozenset] = {}
_TRAVA = threading.Lock()


def capacidades(host: str, modelo: str, *, get=None) -> frozenset:
    """
    O que o modelo declara saber fazer, pelo `/api/show` do Ollama.

    Guardado por (host, modelo) enquanto o programa roda. Sem resposta, o
    conjunto vazio - e nada e pedido que o modelo possa nao entender.
    """
    chave = (host, modelo)
    with _TRAVA:
        if chave in _CAPACIDADES:
            return _CAPACIDADES[chave]
    enviar = get or requests.post
    try:
        resp = enviar(f"{host}/api/show", json={"model": modelo}, timeout=5)
        resp.raise_for_status()
        achadas = frozenset(str(c) for c in (resp.json().get("capabilities") or []))
    except Exception:  # noqa: BLE001 - Ollama fora: nao sei, e nao guardo
        return frozenset()
    with _TRAVA:
        _CAPACIDADES[chave] = achadas
    return achadas


def pensa(host: str, modelo: str, *, get=None) -> bool:
    """
    O modelo tem o modo de pensar antes de responder.

    So para esses vai `think: false`. Ha versoes do Ollama que recusam o
    pedido inteiro quando a flag vai para um modelo que nao a conhece ("does
    not support thinking") - por isso a pergunta vem antes, e nao depois.
    """
    return "thinking" in capacidades(host, modelo, get=get)


def esquecer_capacidades() -> None:
    """Depois de baixar ou trocar modelo, a proxima chamada pergunta de novo."""
    with _TRAVA:
        _CAPACIDADES.clear()
