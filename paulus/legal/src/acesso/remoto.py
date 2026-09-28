"""
O caminho de quem chega de fora, na ordem em que as barreiras aparecem:

  1. o acesso de fora esta ligado? Desligado, 403 - para todo mundo;
  2. o Cloudflare Access deixou passar? O JWT dele e conferido aqui de novo
     (defesa em profundidade): assinatura, `aud`, `iss`, validade. Sem JWT
     valido, 403 antes mesmo do login do PAULUS;
  3. a rota e publica (a tela de login e o que ela carrega)? Passa;
  4. ha sessao do PAULUS, e o e-mail dela e o mesmo do Access? Sem sessao,
     401 na API e a tela de login na pagina;
  5. o pedido altera algo? Precisa do token anti-CSRF da sessao;
  6. a politica da rota (politicas.py) deixa esta pessoa?

O que passou leva, no `scope["state"]`, quem e a pessoa - e dali que as rotas
e a auditoria tiram o nome.
"""

from __future__ import annotations

import json
from pathlib import Path

from acesso import politicas
from acesso.porteiro import cookies, recusar, responder

COOKIE_SESSAO = "paulus_sessao"
CABECALHO_CSRF = "x-paulus-csrf"
CABECALHO_JWT = "cf-access-jwt-assertion"
SEGUROS = {"GET", "HEAD", "OPTIONS"}
PAGINA_DE_ENTRADA = Path(__file__).parent.parent.parent / "frontend" / "entrar.html"


class PortaoRemoto:
    """
    `ligado()` diz se o modulo esta ligado; `verificar_jwt(token)` devolve as
    claims do Access ou None. Sem verificador configurado (tunel nunca
    conectado), ninguem de fora entra. `registrar(evento)` e a auditoria (R8).
    """

    def __init__(self, contas, ligado, verificar_jwt=None, registrar=None) -> None:
        self.contas = contas
        self.ligado = ligado
        self.verificar_jwt = verificar_jwt
        self.registrar = registrar
        # O roteador do app, para saber qual rota atende o pedido. O porteiro
        # recebe a pilha de dentro (o tratamento de excecoes), que nao conhece
        # as rotas; o api.py entrega o roteador aqui depois de criar o app.
        self.rotas = None

    def _anotar(self, **evento) -> None:
        if self.registrar:
            try:
                self.registrar(**evento)
            except Exception:  # noqa: BLE001 - a auditoria nao derruba o pedido
                pass

    async def __call__(self, app, scope, receive, send, cab: dict) -> None:
        if not self.ligado():
            await recusar(scope, send, 403, "o acesso de fora está desligado")
            return
        claims = None
        if self.verificar_jwt is not None:
            try:
                claims = self.verificar_jwt(cab.get(CABECALHO_JWT, ""))
            except Exception:  # noqa: BLE001 - na duvida, nega
                claims = None
        if not claims or not claims.get("email"):
            await recusar(scope, send, 403, "acesso não autorizado pelo Cloudflare Access")
            return
        email_access = str(claims["email"]).lower()
        ip = cab.get("cf-connecting-ip", "")
        estado = scope.setdefault("state", {})
        estado["paulus_remoto"] = {"email_access": email_access, "ip": ip}

        metodo = scope.get("method", "GET")
        rota = politicas.rota_de(self.rotas or app, scope)
        politica = politicas.de(metodo, getattr(rota, "path", None))
        sessao = self.contas.sessao(cookies(cab).get(COOKIE_SESSAO))
        if sessao and sessao["email"].lower() != email_access:
            # O Access diz que e uma pessoa e o cookie diz que e outra: nao
            # vale nenhum dos dois.
            sessao = None
        estado["paulus_pessoa"] = sessao

        if politica == politicas.PUBLICO:
            if scope.get("path") == "/" and not sessao:
                await self._pagina_de_entrada(send)
                return
            await app(scope, receive, send)
            return

        if not sessao:
            await recusar(scope, send, 401, "entre de novo: a sessão acabou")
            return
        if metodo not in SEGUROS and not self.contas.csrf_confere(sessao, cab.get(CABECALHO_CSRF)):
            await recusar(scope, send, 403, "pedido sem o token da sessão")
            return
        if politica == politicas.BLOQUEADO:
            self._anotar(acao="recusado", alvo=f"{metodo} {scope.get('path', '')}", pessoa=sessao["nome"],
                         email=email_access, ip=ip)
            await recusar(scope, send, 403, politicas.MENSAGEM_BLOQUEADA)
            return
        if politica == politicas.TITULAR and sessao["papel"] != "titular":
            await recusar(scope, send, 403, "só o titular pode fazer isso")
            return
        await app(scope, receive, send)

    @staticmethod
    async def _pagina_de_entrada(send) -> None:
        try:
            corpo = PAGINA_DE_ENTRADA.read_bytes()
        except OSError:
            corpo = json.dumps({"detail": "entre com sua conta"}).encode("utf-8")
        await responder(send, 200, corpo, "text/html; charset=utf-8")
