"""
A chave da janela local (R1).

A cada inicio do servidor sai uma chave nova, aleatoria. Ela vai para o
arquivo de instancia (dados/instancia.json), que so a conta do Windows que
roda o PAULUS le, e e dela que sai a diferenca entre local e remoto:

  - a janela pywebview abre `/entrar-local?chave=...` uma vez. A rota troca a
    chave por um cookie de sessao local, de valor DIFERENTE da chave, e esse
    endereco nao vale uma segunda vez: endereco fica em historico e em log;
  - quem nao tem janela (a segunda instancia do desktop.py, o roteiro da
    demonstracao, os testes) le a chave do arquivo e manda no cabecalho
    X-PAULUS-Chave.

Tudo o que nao traz nem um nem outro e remoto. A comparacao e sempre por
`hmac.compare_digest`: comparar com `==` vaza, pelo tempo de resposta,
quantos caracteres do comeco estavam certos.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading

CABECALHO = "x-paulus-chave"
COOKIE = "paulus_local"


def _resumo(valor: str) -> str:
    return hashlib.sha256(valor.encode("utf-8")).hexdigest()


class ChaveLocal:
    """A chave desta execucao e as sessoes locais que ela abriu."""

    def __init__(self, chave: str | None = None) -> None:
        self.chave = chave or secrets.token_urlsafe(32)
        self._trava = threading.Lock()
        self._entrada_usada = False
        # So o resumo de cada cookie: quem ler a memoria do processo nao acha
        # um cookie pronto para usar (e quem le a memoria ja esta dentro).
        self._sessoes: set[str] = set()

    # ------------------------------------------------------------ conferir

    def confere(self, valor: str | None) -> bool:
        """Se `valor` e a chave desta execucao."""
        if not valor:
            return False
        return hmac.compare_digest(str(valor).encode("utf-8"), self.chave.encode("utf-8"))

    def sessao_valida(self, cookie: str | None) -> bool:
        if not cookie:
            return False
        procurado = _resumo(cookie)
        with self._trava:
            # compare_digest um a um: o conjunto e pequeno (uma janela, as
            # vezes duas), e assim nenhuma comparacao depende do valor.
            return any(hmac.compare_digest(procurado, s) for s in self._sessoes)

    def e_local(self, cabecalho: str | None, cookie: str | None) -> bool:
        return self.confere(cabecalho) or self.sessao_valida(cookie)

    # -------------------------------------------------------------- entrar

    def trocar_por_sessao(self, chave: str | None) -> str | None:
        """
        A chave vira um cookie de sessao local, uma unica vez por execucao.

        Devolve o valor do cookie, ou None: chave errada, ou endereco de
        entrada ja usado. A segunda vez e recusada mesmo com a chave certa -
        o endereco com a chave passou por uma barra de endereco, e quem o
        copiou de la nao pode entrar com ele.
        """
        if not self.confere(chave):
            return None
        with self._trava:
            if self._entrada_usada:
                return None
            self._entrada_usada = True
            sessao = secrets.token_urlsafe(32)
            self._sessoes.add(_resumo(sessao))
        return sessao

    def cabecalho(self) -> dict:
        """O cabecalho que um cliente local sem janela manda."""
        return {"X-PAULUS-Chave": self.chave}
