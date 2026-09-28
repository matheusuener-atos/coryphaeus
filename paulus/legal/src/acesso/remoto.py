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
# Uma proposta de agenda, tarefa ou ficha e um formulario: 1 MB sobra.
LIMITE_DA_PROPOSTA = 1024 * 1024
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
        # (sessao, metodo, caminho, corpo, tipo) -> dict do pedido na fila.
        # Quem monta e o AcessoDeFora, que conhece a fila.
        self.propor = None

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
            # O cabecalho diz a tela que foi a SESSAO que acabou - e nao uma
            # rota respondendo 401 por outro motivo (senha de e-mail que
            # falta, por exemplo) -, e so entao ela volta para a tela de entrar.
            await recusar(scope, send, 401, "entre de novo: a sessão acabou",
                          [(b"x-paulus-sessao", b"acabou")])
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
        caminho = scope.get("path", "") + (("?" + scope["query_string"].decode("latin-1"))
                                           if scope.get("query_string") else "")
        if politica == politicas.PROPOR and metodo not in SEGUROS:
            await self._propor(scope, receive, send, cab, sessao, metodo, caminho, email_access, ip)
            return
        if politica == politicas.DOWNLOAD:
            # Um arquivo por pedido - a rota so entrega um -, e cada um fica
            # registrado: e o documento saindo do escritorio.
            self._anotar(acao="download", alvo=caminho, pessoa=sessao["nome"], email=email_access, ip=ip)
        elif (metodo, getattr(rota, "path", "")) in politicas.ROTAS_DE_VER_DOCUMENTO:
            # Documento aberto de fora tambem fica em "quem acessou" (R8); a
            # auditoria junta as paginas do mesmo documento numa linha so.
            self._anotar(acao="documento", alvo=caminho, pessoa=sessao["nome"], email=email_access, ip=ip)
        await app(scope, receive, send)

    async def _propor(self, scope, receive, send, cab, sessao, metodo, caminho, email_access, ip) -> None:
        """
        Agenda, tarefas e cadastros, de fora: o pedido nao grava nada. Vira um
        item na fila de Aprovacoes com o pedido inteiro guardado, e o sim de
        quem pode (a janela local, ou o titular de fora) executa exatamente
        aquilo. A tela recebe 202 e diz que foi para a fila.
        """
        corpo = b""
        while True:
            msg = await receive()
            corpo += msg.get("body", b"")
            if len(corpo) > LIMITE_DA_PROPOSTA:
                await recusar(scope, send, 413, "proposta grande demais")
                return
            if not msg.get("more_body"):
                break
        if self.propor is None:
            await recusar(scope, send, 403, politicas.MENSAGEM_BLOQUEADA)
            return
        try:
            pedido = self.propor(sessao, metodo, caminho, corpo.decode("utf-8", "replace"),
                                 cab.get("content-type", "application/json"))
        except Exception as exc:  # noqa: BLE001 - a proposta que nao monta nao pode virar 500 mudo
            await recusar(scope, send, 400, f"não consegui montar a proposta: {exc}")
            return
        self._anotar(acao="proposta", alvo=f"{metodo} {caminho}", pessoa=sessao["nome"], email=email_access, ip=ip)
        resposta = {"proposto": True, "pedido": pedido,
                    "detail": "Foi para Aprovações: acontece quando o escritório confirmar."}
        await responder(send, 202, json.dumps(resposta, ensure_ascii=False).encode("utf-8"),
                        "application/json; charset=utf-8")

    @staticmethod
    async def _pagina_de_entrada(send) -> None:
        try:
            corpo = PAGINA_DE_ENTRADA.read_bytes()
        except OSError:
            corpo = json.dumps({"detail": "entre com sua conta"}).encode("utf-8")
        await responder(send, 200, corpo, "text/html; charset=utf-8")
