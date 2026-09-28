"""
O caminho de quem chega de fora, na ordem em que as barreiras aparecem:

  1. o acesso de fora esta ligado? Desligado, 403 - para todo mundo;
  2. sem sessao do PAULUS, so a tela de entrar e o que ela carrega passam:
     a pagina, as fontes, a folha de cores e as duas rotas do login (senha e
     codigo), mais a que diz a sitekey do Turnstile. Toda outra rota /api/*
     responde 401, e toda outra pagina, a tela de entrar;
  3. o pedido altera algo? Precisa do token anti-CSRF da sessao;
  4. a politica da rota (politicas.py) deixa esta pessoa?

Sem Cloudflare Access (decisao de produto de 28/09/2026): quem garante que so
o escritorio entra e o proprio PAULUS - Turnstile, senha e o codigo do
autenticador, bloqueio por conta e por endereco, sessoes curtas. E, em TODA
resposta de fora, os cabecalhos de seguranca: a pagina nao entra em moldura
de outro site, nao vaza endereco, nao carrega script de lugar nenhum alem
dela mesma e do Turnstile.

O que passou leva, no `scope["state"]`, quem e a pessoa - e dali que as rotas
e a auditoria tiram o nome.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path

from acesso import politicas
from acesso.porteiro import cookies, recusar, responder

COOKIE_SESSAO = "paulus_sessao"
CABECALHO_CSRF = "x-paulus-csrf"
SEGUROS = {"GET", "HEAD", "OPTIONS"}
# Uma proposta de agenda, tarefa ou ficha e um formulario: 1 MB sobra.
LIMITE_DA_PROPOSTA = 1024 * 1024
FRONTEND = Path(__file__).parent.parent.parent / "frontend"
PAGINA_DE_ENTRADA = FRONTEND / "entrar.html"
TURNSTILE = "https://challenges.cloudflare.com"


def _hashes_dos_scripts() -> list[str]:
    """
    O sha256 de cada script escrito dentro das paginas (o do tema, que roda
    antes da primeira pintura; o da tela de entrar). Com eles na lista, a CSP
    nao precisa de 'unsafe-inline' para script - e script injetado nao roda.
    """
    saida = []
    for pagina in (FRONTEND / "index.html", PAGINA_DE_ENTRADA):
        try:
            html = pagina.read_text(encoding="utf-8")
        except OSError:
            continue
        for corpo in re.findall(r"<script>(.*?)</script>", html, flags=re.S):
            saida.append("'sha256-" + base64.b64encode(hashlib.sha256(corpo.encode("utf-8")).digest()).decode() + "'")
    return saida


def politica_de_conteudo() -> str:
    """
    A Content-Security-Policy de quem esta de fora: so o que o frontend ja
    usa. Estilo inline fica (a tela escreve `style=` em muitos lugares); script
    inline, so os conferidos por hash. Imagem de fora nao carrega - inclusive a
    de e-mail, que de fora vira privacidade: pixel de rastreio nao abre.
    """
    scripts = " ".join(["'self'", *_hashes_dos_scripts(), TURNSTILE])
    return ("default-src 'self'; "
            f"script-src {scripts}; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; "
            f"frame-src 'self' {TURNSTILE}; child-src 'self' blob: {TURNSTILE}; "
            "media-src 'self' blob:; worker-src 'self' blob:; object-src 'none'; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


PERMISSOES = ("accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), "
              "payment=(), usb=(), interest-cohort=(), browsing-topics=()")


def cabecalhos_de_seguranca(csp: str) -> list[tuple[bytes, bytes]]:
    return [
        (b"content-security-policy", csp.encode("latin-1")),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"no-referrer"),
        (b"x-content-type-options", b"nosniff"),
        (b"permissions-policy", PERMISSOES.encode("latin-1")),
        (b"cross-origin-opener-policy", b"same-origin"),
        (b"strict-transport-security", b"max-age=31536000"),
    ]


def com_cabecalhos(send, extras: list[tuple[bytes, bytes]]):
    """O `send` do ASGI que acrescenta os cabecalhos de seguranca a toda resposta."""
    nomes = {k for k, _ in extras}

    async def enviar(mensagem):
        if mensagem.get("type") == "http.response.start":
            atuais = [(k, v) for k, v in (mensagem.get("headers") or []) if k.lower() not in nomes]
            mensagem = {**mensagem, "headers": atuais + extras}
        await send(mensagem)

    return enviar


class PortaoRemoto:
    """
    `ligado()` diz se o modulo esta ligado. `registrar(evento)` e a auditoria
    (R8).
    """

    def __init__(self, contas, ligado, registrar=None) -> None:
        self.contas = contas
        self.ligado = ligado
        self.registrar = registrar
        # O roteador do app, para saber qual rota atende o pedido. O porteiro
        # recebe a pilha de dentro (o tratamento de excecoes), que nao conhece
        # as rotas; o api.py entrega o roteador aqui depois de criar o app.
        self.rotas = None
        # (sessao, metodo, caminho, corpo, tipo) -> dict do pedido na fila.
        # Quem monta e o AcessoDeFora, que conhece a fila.
        self.propor = None
        self._seguranca = cabecalhos_de_seguranca(politica_de_conteudo())

    def _anotar(self, **evento) -> None:
        if self.registrar:
            try:
                self.registrar(**evento)
            except Exception:  # noqa: BLE001 - a auditoria nao derruba o pedido
                pass

    async def __call__(self, app, scope, receive, send, cab: dict) -> None:
        send = com_cabecalhos(send, self._seguranca)
        if not self.ligado():
            await recusar(scope, send, 403, "o acesso de fora está desligado")
            return
        ip = cab.get("cf-connecting-ip", "")
        estado = scope.setdefault("state", {})
        estado["paulus_remoto"] = {"ip": ip}

        metodo = scope.get("method", "GET")
        caminho_puro = scope.get("path", "")
        rota = politicas.rota_de(self.rotas or app, scope)
        politica = politicas.de(metodo, getattr(rota, "path", None))
        sessao = self.contas.sessao(cookies(cab).get(COOKIE_SESSAO))
        estado["paulus_pessoa"] = sessao

        if not sessao:
            if (metodo, caminho_puro) in politicas.SEM_SESSAO or politicas.estatico_da_entrada(metodo, caminho_puro):
                if caminho_puro == "/":
                    await self._pagina_de_entrada(send)
                    return
                await app(scope, receive, send)
                return
            if caminho_puro.startswith("/api/"):
                # O cabecalho diz a tela que foi a SESSAO que acabou - e nao
                # uma rota respondendo 401 por outro motivo -, e so entao ela
                # volta para a tela de entrar.
                await recusar(scope, send, 401, "entre de novo: a sessão acabou",
                              [(b"x-paulus-sessao", b"acabou")])
                return
            await self._pagina_de_entrada(send, 401)
            return

        if politica == politicas.PUBLICO:
            await app(scope, receive, send)
            return
        if metodo not in SEGUROS and not self.contas.csrf_confere(sessao, cab.get(CABECALHO_CSRF)):
            await recusar(scope, send, 403, "pedido sem o token da sessão")
            return
        if politica == politicas.BLOQUEADO:
            self._anotar(acao="recusado", alvo=f"{metodo} {caminho_puro}", pessoa=sessao["nome"],
                         email=sessao["email"], ip=ip)
            await recusar(scope, send, 403, politicas.MENSAGEM_BLOQUEADA)
            return
        if politica == politicas.TITULAR and sessao["papel"] != "titular":
            await recusar(scope, send, 403, "só o titular pode fazer isso")
            return
        caminho = caminho_puro + (("?" + scope["query_string"].decode("latin-1")) if scope.get("query_string") else "")
        if politica == politicas.PROPOR and metodo not in SEGUROS:
            await self._propor(scope, receive, send, cab, sessao, metodo, caminho, ip)
            return
        if politica == politicas.DOWNLOAD:
            # Um arquivo por pedido - a rota so entrega um -, e cada um fica
            # registrado: e o documento saindo do escritorio.
            self._anotar(acao="download", alvo=caminho, pessoa=sessao["nome"], email=sessao["email"], ip=ip)
        elif (metodo, getattr(rota, "path", "")) in politicas.ROTAS_DE_VER_DOCUMENTO:
            # Documento aberto de fora tambem fica em "quem acessou" (R8); a
            # auditoria junta as paginas do mesmo documento numa linha so.
            self._anotar(acao="documento", alvo=caminho, pessoa=sessao["nome"], email=sessao["email"], ip=ip)
        await app(scope, receive, send)

    async def _propor(self, scope, receive, send, cab, sessao, metodo, caminho, ip) -> None:
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
        self._anotar(acao="proposta", alvo=f"{metodo} {caminho}", pessoa=sessao["nome"], email=sessao["email"], ip=ip)
        resposta = {"proposto": True, "pedido": pedido,
                    "detail": "Foi para Aprovações: acontece quando o escritório confirmar."}
        await responder(send, 202, json.dumps(resposta, ensure_ascii=False).encode("utf-8"),
                        "application/json; charset=utf-8")

    @staticmethod
    async def _pagina_de_entrada(send, status: int = 200) -> None:
        try:
            corpo = PAGINA_DE_ENTRADA.read_bytes()
        except OSError:
            corpo = json.dumps({"detail": "entre com sua conta"}).encode("utf-8")
        await responder(send, status, corpo, "text/html; charset=utf-8")
