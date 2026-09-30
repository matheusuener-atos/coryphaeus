"""
O porteiro: o middleware que decide, a cada requisicao, se ela e local ou
remota, e o que a remota pode.

E ASGI puro, e nao `BaseHTTPMiddleware`, de proposito: as respostas da
conversa saem em streaming (text/event-stream) por minutos, e o middleware de
alto nivel do Starlette embrulha o corpo da resposta - no parar da conversa,
o cancelamento se perdia no meio do embrulho. Aqui a resposta passa direto.
"""

from __future__ import annotations

import contextvars

import json
from http.cookies import SimpleCookie

from acesso.chave import CABECALHO, COOKIE, ChaveLocal

PAGINA_RECUSADA = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>PAULUS</title>
<style>body{font-family:system-ui,sans-serif;background:#f4f1ea;color:#171716;display:grid;place-items:center;min-height:100vh;margin:0}
main{max-width:30rem;padding:2rem}h1{font-family:Georgia,serif;font-weight:500;font-size:1.6rem;margin:0 0 .6rem}
p{line-height:1.5;color:#4a4843}</style></head><body><main><h1>Este endereço não abre fora da janela do PAULUS</h1>
<p>O PAULUS só atende a janela do próprio programa, neste computador. Abra o PAULUS pelo atalho do Windows.</p>
</main></body></html>"""


def cabecalhos(scope) -> dict[str, str]:
    """Os cabecalhos da requisicao, com nome em minusculas (como o ASGI entrega)."""
    saida: dict[str, str] = {}
    for nome, valor in scope.get("headers") or []:
        saida[nome.decode("latin-1").lower()] = valor.decode("latin-1")
    return saida


def cookies(cab: dict[str, str]) -> dict[str, str]:
    bruto = cab.get("cookie", "")
    if not bruto:
        return {}
    pote = SimpleCookie()
    try:
        pote.load(bruto)
    except Exception:  # noqa: BLE001 - cookie torto e cookie nenhum
        return {}
    return {k: m.value for k, m in pote.items()}


async def responder(send, status: int, corpo: bytes, tipo: str, extra: list | None = None) -> None:
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", tipo.encode()), (b"cache-control", b"no-store"),
                    (b"content-length", str(len(corpo)).encode())] + list(extra or []),
    })
    await send({"type": "http.response.body", "body": corpo})


async def recusar(scope, send, status: int = 403, mensagem: str = "", extra: list | None = None) -> None:
    """403 em HTML para quem abre uma pagina, em JSON para quem chama a API."""
    caminho = scope.get("path", "")
    if scope.get("type") == "websocket":
        await send({"type": "websocket.close", "code": 4403})
        return
    if caminho.startswith("/api/"):
        corpo = json.dumps({"detail": mensagem or "acesso recusado"}, ensure_ascii=False).encode("utf-8")
        await responder(send, status, corpo, "application/json; charset=utf-8", extra)
    else:
        await responder(send, status, PAGINA_RECUSADA.encode("utf-8"), "text/html; charset=utf-8")


# Quem fez o pedido que esta sendo atendido agora: a sessao de fora, ou None
# na janela local. As rotas que nao recebem o `request` (as do e-mail, que
# escolhem a conta) leem daqui - src/equipe.py, E3b. O porteiro poe o valor a
# cada pedido, antes de tudo, para nada vazar de um pedido para o outro.
PESSOA_DA_VEZ: contextvars.ContextVar = contextvars.ContextVar("paulus_pessoa_da_vez", default=None)


class Porteiro:
    """
    Local passa como sempre passou. Remoto passa por `remoto`, que decide -
    na R1, ninguem de fora entra: `remoto` e None e a resposta e 403.
    """

    def __init__(self, app, chave: ChaveLocal, remoto=None, travado=None, mcp=None) -> None:
        self.app = app
        self.chave = chave
        # () -> o servidor MCP das leis (src/mcp_leis.py), que tem o token
        # proprio e as travas proprias: o agente de fora nao tem a chave da
        # janela, e o /mcp nao passa pelo login do acesso de fora.
        self.mcp = mcp
        # () -> bool: o PAULUS vinculado a conta Google e travado (src/vinculo.py).
        # Travado, a janela local so alcanca a tela de destravar.
        self.travado = travado
        # async (scope, receive, send, cab) -> bool: True se ja respondeu ou
        # deixou passar. Fica de fora da R1; as etapas seguintes ligam.
        self.remoto = remoto

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        if scope.get("type") == "http" and scope.get("path") == "/entrar-local":
            await self._entrar_local(scope, send)
            return
        PESSOA_DA_VEZ.set(None)
        cab = cabecalhos(scope)
        if scope.get("type") == "http" and scope.get("path") == "/mcp":
            servidor = self.mcp() if self.mcp else None
            if servidor is None:
                await recusar(scope, send, 404, "não há servidor MCP aqui")
                return
            await servidor(scope, receive, send, cab)
            return
        local = self.chave.e_local(cab.get(CABECALHO), cookies(cab).get(COOKIE))
        scope.setdefault("state", {})["paulus_local"] = local
        if local:
            if self.travado is not None and self.travado():
                from vinculo import passa_travado

                if not passa_travado(scope.get("method", "GET"), scope.get("path", "")):
                    await recusar(scope, send, 423, "o PAULUS está travado: entre com a conta Google",
                                  [(b"x-paulus-travado", b"1")])
                    return
            await self.app(scope, receive, send)
            return
        if self.remoto is not None:
            await self.remoto(self.app, scope, receive, send, cab)
            return
        await recusar(scope, send)

    async def _entrar_local(self, scope, send) -> None:
        """
        `/entrar-local?chave=...`: a chave vira o cookie da sessao local e a
        pagina segue para `/`, levando o `#fragmento` (o "#perguntar=..." do
        Explorer). O fragmento nao chega ao servidor - por isso quem segue e o
        navegador, com `location.replace`, e nao um redirecionamento daqui.

        Esta rota nao esta em `app.routes`: ela e do porteiro, e e a unica
        coisa que uma requisicao sem chave alcanca com o acesso de fora
        desligado.
        """
        from urllib.parse import parse_qs

        if scope.get("method") != "GET":
            await recusar(scope, send, 405)
            return
        qs = parse_qs((scope.get("query_string") or b"").decode("latin-1"))
        sessao = self.chave.trocar_por_sessao((qs.get("chave") or [""])[0])
        if not sessao:
            await recusar(scope, send)
            return
        cookie = f"{COOKIE}={sessao}; Path=/; HttpOnly; SameSite=Strict"
        corpo = ("<!doctype html><meta charset=utf-8><title>PAULUS</title>"
                 "<script>location.replace('/' + location.hash)</script>"
                 "<noscript><meta http-equiv=refresh content='0;url=/'></noscript>").encode("utf-8")
        await responder(send, 200, corpo, "text/html; charset=utf-8",
                        [(b"set-cookie", cookie.encode("latin-1")), (b"referrer-policy", b"no-referrer")])
