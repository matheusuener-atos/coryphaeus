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
"""

from __future__ import annotations

import itertools
import threading
import time
from dataclasses import dataclass, field

MAX_POR_PESSOA = 2


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

    def entrar(self, dono: str, rotulo: str = "") -> Vez:
        """
        Pega um lugar na fila, ou levanta FilaCheia. Nao espera: quem chamou
        decide como esperar (`esperar`) - a conversa espera emitindo a
        posicao para a tela.
        """
        with self._cond:
            do_dono = [v for v in self._fila if v.dono == dono]
            if len(do_dono) >= self.max_por_pessoa:
                raise FilaCheia(
                    f"você já tem {len(do_dono)} perguntas na fila do modelo; "
                    "espere uma terminar para mandar outra")
            vez = Vez(dono=dono, ordem=next(self._contador), rotulo=rotulo)
            self._fila.append(vez)
            return vez

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
