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

# A pagina de quem abre o endereco do PAULUS num navegador comum (sem a chave
# da janela), no desenho "Acesso - Porteiro - endereco recusado" (07/10/2026):
# a topbar do site com o tema, o motivo e o "Abrir o Paulus" (paulus://, que o
# instalador e o desktop.py registram; o navegador pergunta antes de abrir).
PAGINA_RECUSADA = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><title>Paulus</title>
<link rel="stylesheet" href="/fontes.css">
<style>:root,[data-tema="escuro"]{--bg:#131312;--ink:#f2f1ec;--ink2:#a8a69e;--ink3:#95938a;--fio:rgba(242,241,236,.1);color-scheme:dark}
[data-tema="claro"]{--bg:#faf9f6;--ink:#1c1c1a;--ink2:#5c5b56;--ink3:#77766f;--fio:rgba(28,28,26,.1);color-scheme:light}
@media (prefers-color-scheme:light){:root:not([data-tema]){--bg:#faf9f6;--ink:#1c1c1a;--ink2:#5c5b56;--ink3:#77766f;--fio:rgba(28,28,26,.1);color-scheme:light}}
.barra{position:fixed;top:0;left:0;right:0;display:flex;align-items:center;justify-content:space-between;height:56px;padding:0 28px;background:var(--bg);border-bottom:1px solid var(--fio);box-sizing:border-box}
.barra a{font:400 20px/1 'EB Garamond',Georgia,serif;letter-spacing:.12em;color:var(--ink);text-decoration:none}
.barra-tema{width:32px;height:32px;margin-right:-8px;padding:0;border:0;border-radius:8px;background:none;color:var(--ink3);display:flex;align-items:center;justify-content:center;cursor:pointer}
.barra-tema:hover{color:var(--ink)}.barra-tema svg{width:18px;height:18px}
:root{--surf:#1a1a18;--fill2:#2a2a27;--sobre:#303030}[data-tema="claro"]{--surf:#efeee9;--fill2:#e2e1db;--sobre:#dad9d2}
@media (prefers-color-scheme:light){:root:not([data-tema]){--surf:#efeee9;--fill2:#e2e1db;--sobre:#dad9d2}}
.trilho{display:flex;width:100%;max-width:360px;margin:26px auto 0;padding:1px;border-radius:12px;background:var(--surf);border:1px solid var(--fio);text-decoration:none;cursor:pointer;box-sizing:border-box}
.pastilha{flex:1;height:28px;display:flex;align-items:center;justify-content:center;gap:8px;border-radius:8px;background:var(--fill2);color:var(--ink);font:500 13px 'Manrope',system-ui,sans-serif;letter-spacing:.01em}
.trilho:hover .pastilha{background:var(--sobre)}
.dica{margin-top:10px;font:400 12px/1.5 'Manrope',sans-serif;color:var(--ink2);opacity:.8}
@media (max-width:600px){.barra{padding:0 16px}}
body{margin:0;min-height:100vh;background:var(--bg);color:var(--ink);font:400 16px/1.6 'Manrope',system-ui,sans-serif;
display:flex;justify-content:center;padding:22vh 24px 48px;box-sizing:border-box}
main{max-width:360px;display:grid;gap:14px;text-align:center;align-content:start}
h1{margin:0;font:400 40px/1.08 'EB Garamond',Georgia,serif;letter-spacing:-.015em;text-wrap:balance}
p{margin:0;color:var(--ink2);text-wrap:pretty}
main>*{animation:aparece .7s ease both}@keyframes aparece{from{opacity:0}to{opacity:1}}
@media (prefers-reduced-motion:reduce){main>*{animation:none}}</style></head>
<body><header class="barra"><a href="https://paulus.ia.br">PAVLVS</a><button type="button" class="barra-tema" id="barra-tema" aria-label="Alternar tema"><svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10Zm0-5 1.5 3h-3L12 2Zm0 20-1.5-3h3L12 22Zm10-10-3 1.5v-3L22 12ZM2 12l3-1.5v3L2 12Zm17.07-7.07-1.06 3.18-2.12-2.12 3.18-1.06ZM4.93 19.07l1.06-3.18 2.12 2.12-3.18 1.06Zm14.14 0-3.18-1.06 2.12-2.12 1.06 3.18ZM4.93 4.93l3.18 1.06-2.12 2.12-1.06-3.18Z"/></svg></button></header>
<main><h1>Paulus está te esperando.</h1>
<p>Este endereço é o do Paulus instalado neste computador e só abre dentro dele. Para entrar de outro lugar, use o endereço do escritório em paulus.ia.br.</p>
<a class="trilho" href="paulus://abrir"><span class="pastilha">Abrir o Paulus</span></a>
<span class="dica">O navegador pergunta antes de abrir o programa.</span>
</main>
<script>(function(){var h=document.documentElement,b=document.getElementById("barra-tema");if(!b)return;b.onclick=function(){var atual=h.dataset.tema||(matchMedia("(prefers-color-scheme:light)").matches?"claro":"escuro");h.dataset.tema=atual==="claro"?"escuro":"claro";};})();</script>
</body></html>"""


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

    def __init__(self, app, chave: ChaveLocal, remoto=None, travado=None, mcp=None, word=None) -> None:
        self.app = app
        self.chave = chave
        # () -> o servidor MCP das leis (src/mcp_leis.py), que tem o token
        # proprio e as travas proprias: o agente de fora nao tem a chave da
        # janela, e o /mcp nao passa pelo login do acesso de fora.
        self.mcp = mcp
        # () -> a porta do suplemento do Word (src/word_suplemento.py): o painel
        # tem token proprio e entra antes da chave da janela, como o /mcp.
        self.word = word
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
        word = self.word() if self.word and scope.get("type") == "http" else None
        if word is not None and word.atende(scope):
            await word(self.app, scope, receive, send, cab)
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
