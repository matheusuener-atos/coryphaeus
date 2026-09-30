"""
A fila do modelo local (acesso-remoto/v0, R4).

O modelo desta maquina responde uma pergunta por vez. Enquanto era uma pessoa
so, na janela do programa, isso nao aparecia: ninguem pergunta duas coisas ao
mesmo tempo. Com o acesso de fora, o escritorio pergunta daqui, o advogado
pergunta do celular, e as duas respostas disputariam o mesmo processador - as
duas mais lentas, e sem ninguem saber por que.

Daqui em diante as perguntas entram numa fila unica:

  - ordem de chegada, e no maximo DUAS por pessoa (a que esta sendo
    respondida conta): ninguem enfileira dez perguntas seguidas na frente dos
    outros;
  - quem espera ve a posicao e a previsao ("voce e o 2o, ~40 s"), tirada do
    que esta maquina ja mediu de si (src/ritmo.py). Com uma pessoa so, a fila
    e invisivel: ninguem espera, nada aparece;
  - parar tira da fila, ou interrompe so a propria resposta - nunca a de
    outra pessoa;
  - o trabalho de segundo plano (ler documento novo, calcular vetor) chama
    `ceder()` entre um item e outro, e espera enquanto houver pergunta na
    fila: segundo plano e segundo plano.

A fila nao chama o modelo: ela so diz de quem e a vez. Quem chama o modelo
continua sendo quem sempre chamou.

F1 (docs/PROGRESSO-APARELHO.md), com a chave `aparelho.fila`:

  - TODA chamada ao modelo entra aqui, de qualquer tela, pelo proprio cliente
    do modelo (`vez_para_o_modelo`, usado em src/llama_client.py), com a
    origem ("conversa", "editor", "e-mail"...) e o primeiro nome de quem
    pediu. Quem ja tem a vez (a conversa, que a pega antes de ler) nao entra
    de novo: a marca e a ContextVar `VEZ`, que desde a correcao do filtro de
    Servicos chega as threads da resposta;
  - prioridade (Ctrl+Enter): "propria" passa na frente das perguntas da
    mesma pessoa e do segundo plano; "geral" (liberada pelo titular) passa na
    frente de todos que esperam. Nenhuma passa na frente de quem ja comecou;
  - quem espera ve quem esta na frente pelo primeiro nome e a origem - nunca
    o texto de ninguem.
"""

from __future__ import annotations

import contextvars
import itertools
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

MAX_POR_PESSOA = 2
FUNDO = "segundo plano"

# A vez que a thread atual ja tem: o cliente do modelo nao entra de novo na
# fila por uma chamada feita de dentro dela.
VEZ: contextvars.ContextVar = contextvars.ContextVar("paulus_vez_no_modelo", default=None)
# Quem pediu, posto a cada requisicao (src/fila_de_todos.py): {"dono", "nome",
# "origem"}. Sem ele - thread de segundo plano -, e o segundo plano.
PEDIDO: contextvars.ContextVar = contextvars.ContextVar("paulus_pedido_ao_modelo", default=None)


class FilaCheia(RuntimeError):
    """A pessoa ja tem o maximo de perguntas na fila."""


@dataclass
class Vez:
    """Uma pergunta na fila. `ordem` e a ordem de chegada."""

    dono: str
    ordem: int
    rotulo: str = ""
    chegou: float = field(default_factory=time.time)
    comecou: float = 0.0
    saiu: bool = False
    # F1: o que a tela de quem espera ve desta vez - nunca o texto.
    origem: str = ""
    nome: str = ""
    fundo: bool = False
    prioridade: str = ""          # "" | "propria" | "geral"
    passado_por: str = ""         # o primeiro nome de quem passou na frente

    @property
    def respondendo(self) -> bool:
        return bool(self.comecou) and not self.saiu


class FilaDoModelo:
    def __init__(self, segundos_por_resposta=None, max_por_pessoa: int = MAX_POR_PESSOA) -> None:
        # () -> segundos que uma resposta costuma levar aqui (0 se nao se sabe).
        self.segundos_por_resposta = segundos_por_resposta or (lambda: 0.0)
        self.max_por_pessoa = max_por_pessoa
        self._cond = threading.Condition()
        self._fila: list[Vez] = []
        self._contador = itertools.count(1)

    # ------------------------------------------------------------- entrar

    def entrar(self, dono: str, rotulo: str = "", *, origem: str = "", nome: str = "", fundo: bool = False,
               prioridade: str = "") -> Vez:
        """
        Pega um lugar na fila, ou levanta FilaCheia. Nao espera: quem chamou
        decide como esperar (`esperar`) - a conversa espera emitindo a
        posicao para a tela.
        """
        pedido = PEDIDO.get() or {}
        with self._cond:
            do_dono = [v for v in self._fila if v.dono == dono]
            if not fundo and len(do_dono) >= self.max_por_pessoa:
                raise FilaCheia("você já tem duas perguntas esperando a vez do modelo; "
                                "espere uma terminar para mandar outra")
            vez = Vez(dono=dono, ordem=next(self._contador), rotulo=rotulo,
                      origem=origem or pedido.get("origem", ""), nome=nome or pedido.get("nome", ""),
                      fundo=fundo, prioridade=prioridade if prioridade in ("propria", "geral") else "")
            lugar = self._lugar(vez)
            self._fila.insert(lugar, vez)
            if vez.prioridade == "propria":
                self._trocar_entre_as_proprias(vez)
            if vez.prioridade == "geral":
                for outra in self._fila[lugar + 1:]:
                    if outra.dono != vez.dono and not outra.fundo:
                        outra.passado_por = vez.nome or "alguém"
            self._cond.notify_all()
            return vez

    def _lugar(self, vez: Vez) -> int:
        """
        Onde a vez entra. Nunca antes de quem ja comecou (a resposta sendo
        escrita nao e interrompida). Segundo plano vai para o fim; pergunta
        (normal ou "propria") passa na frente do segundo plano que ainda
        espera; "geral" passa na frente de todos que esperam, depois das
        outras "geral".
        """
        inicio = 1 if self._fila and self._fila[0].comecou else 0
        if vez.fundo:
            return len(self._fila)
        if vez.prioridade == "geral":
            i = inicio
            while i < len(self._fila) and self._fila[i].prioridade == "geral":
                i += 1
            return i
        for i in range(inicio, len(self._fila)):
            if self._fila[i].fundo:
                return i
        return len(self._fila)

    def _trocar_entre_as_proprias(self, vez: Vez) -> None:
        """
        "propria": a nova vai para o lugar da pergunta mais antiga da mesma
        pessoa que ainda espera, e as dela andam uma casa para tras - nos
        lugares que ja eram dela. Os lugares dos outros nao mudam.
        """
        lugares = [i for i, v in enumerate(self._fila)
                   if v.dono == vez.dono and not v.comecou and v.prioridade != "geral"]
        if len(lugares) < 2:
            return
        proprias = [self._fila[i] for i in lugares]
        for i, v in zip(lugares, [proprias[-1]] + proprias[:-1]):
            self._fila[i] = v

    def cabe(self, dono: str) -> bool:
        """Se `dono` ainda pode pedir mais uma - para recusar antes de gravar a pergunta."""
        with self._cond:
            return sum(1 for v in self._fila if v.dono == dono) < self.max_por_pessoa

    def posicao(self, vez: Vez) -> int:
        """0 se ja e a vez dela (ou esta respondendo); 1 se e a proxima; e assim por diante."""
        with self._cond:
            if vez not in self._fila:
                return 0
            return self._fila.index(vez)

    def previsao(self, vez: Vez) -> int:
        """Segundos ate a vez chegar, pelo ritmo medido. 0 se nao se sabe."""
        por_resposta = float(self.segundos_por_resposta() or 0)
        n = self.posicao(vez)
        if not por_resposta or not n:
            return 0
        # Quem esta respondendo agora ja andou um pedaco; o resto e inteiro.
        with self._cond:
            primeiro = self._fila[0] if self._fila else None
        andado = (time.time() - primeiro.comecou) if primeiro and primeiro.comecou else 0.0
        return max(1, round(n * por_resposta - min(andado, por_resposta)))

    def esperar(self, vez: Vez, timeout: float | None = None) -> bool:
        """
        Bloqueia ate ser a vez de `vez`, ou ate `timeout`. Devolve se e a vez.
        Pode ser chamada de novo quantas vezes for preciso (a conversa chama a
        cada meio segundo, para mandar a posicao e ouvir o parar).
        """
        limite = None if timeout is None else time.time() + timeout
        with self._cond:
            while True:
                if vez.saiu:
                    return False
                if self._fila and self._fila[0] is vez:
                    if not vez.comecou:
                        vez.comecou = time.time()
                    # A thread que esperou e a que vai chamar o modelo: as
                    # chamadas dela daqui em diante ja tem a vez.
                    VEZ.set(vez)
                    return True
                resta = None if limite is None else limite - time.time()
                if resta is not None and resta <= 0:
                    return False
                self._cond.wait(resta)

    def sair(self, vez: Vez) -> None:
        """Terminou, parou ou desistiu: a vez passa para a proxima."""
        with self._cond:
            vez.saiu = True
            if vez in self._fila:
                self._fila.remove(vez)
            self._cond.notify_all()
        if VEZ.get() is vez:
            VEZ.set(None)

    def na_frente(self, vez: Vez) -> list[dict]:
        """Quem esta antes desta vez: primeiro nome e origem. Nunca o texto."""
        with self._cond:
            if vez not in self._fila:
                return []
            return [{"nome": FUNDO if v.fundo else (v.nome or "alguém"), "origem": v.origem or "outra tela",
                     "respondendo": v.respondendo} for v in self._fila[:self._fila.index(vez)]]

    def para_evento(self, vez: Vez) -> dict:
        """O evento `fila` da tela: posicao, previsao, quem esta na frente e por que mudou."""
        dados = {"posicao": self.posicao(vez), "previsao_s": self.previsao(vez), "na_frente": self.na_frente(vez)}
        if vez.passado_por:
            dados["motivo"] = "pergunta prioritária de " + vez.passado_por
        return dados

    def foto(self) -> list[dict]:
        """A fila inteira, para a janela do escritorio: quem, de onde, desde quando. Sem texto."""
        agora = time.time()
        with self._cond:
            return [{"nome": FUNDO if v.fundo else (v.nome or "alguém"), "origem": v.origem or "outra tela",
                     "respondendo": v.respondendo, "prioridade": v.prioridade,
                     "esperando_s": round(agora - v.chegou),
                     "respondendo_s": round(agora - v.comecou) if v.comecou else 0}
                    for v in self._fila]

    def ocupada_por_outro(self) -> bool:
        """Ha alguem na fila e a thread atual nao tem a vez: o juiz de uma letra nao espera."""
        vez = VEZ.get()
        with self._cond:
            return bool(self._fila) and not (vez is not None and not vez.saiu and vez in self._fila)

    # ------------------------------------------------- segundo plano

    def ocupada(self) -> bool:
        with self._cond:
            return bool(self._fila)

    def ceder(self, limite_s: float = 600.0) -> None:
        """
        Para o trabalho de segundo plano: espera enquanto houver pergunta na
        fila (ou sendo respondida). Com teto - segundo plano que nunca anda
        tambem e defeito.
        """
        fim = time.time() + limite_s
        with self._cond:
            while self._fila and time.time() < fim:
                self._cond.wait(min(1.0, max(0.0, fim - time.time())))

    # ------------------------------------------------------------ tela

    def para_tela(self) -> dict:
        with self._cond:
            return {"na_fila": len(self._fila),
                    "respondendo": next((v.rotulo for v in self._fila if v.respondendo), "")}


# ------------------------------------------------ a fila de todas as telas (F1)

_INSTALADA: dict = {"fila": None, "ligada": lambda: False}


def instalar(fila: FilaDoModelo | None, ligada) -> None:
    """O programa diz qual e a fila e se a chave `aparelho.fila` esta ligada (src/api.py)."""
    _INSTALADA["fila"] = fila
    _INSTALADA["ligada"] = ligada


def instalada() -> FilaDoModelo | None:
    fila = _INSTALADA["fila"]
    try:
        return fila if fila is not None and _INSTALADA["ligada"]() else None
    except Exception:  # noqa: BLE001 - preferencia ilegivel: sem fila, como antes
        return None


class Parado(RuntimeError):
    """A pessoa parou enquanto esperava a vez."""


@contextmanager
def vez_para_o_modelo(parar=None):
    """
    Envolve UMA chamada ao modelo (src/llama_client.py). Sem a chave, ou com a
    vez ja na mao, nao faz nada. Senao, entra na fila como quem pediu (ou como
    segundo plano), espera a vez e sai no fim - em qualquer saida.
    """
    fila = instalada()
    atual = VEZ.get()
    if fila is None or (atual is not None and not atual.saiu):
        yield None
        return
    pedido = PEDIDO.get()
    if pedido:
        vez = fila.entrar(pedido["dono"], rotulo=pedido.get("origem", ""))
    else:
        vez = fila.entrar(FUNDO, rotulo=FUNDO, origem=FUNDO, nome=FUNDO, fundo=True)
    try:
        while not fila.esperar(vez, timeout=0.5):
            if parar is not None and parar():
                raise Parado("parado enquanto esperava a vez do modelo")
        yield vez
    finally:
        fila.sair(vez)
