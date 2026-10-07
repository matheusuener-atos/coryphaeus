"""
PAULUS - Entrar no e-mail com a conta Google ou Microsoft (OAuth 2.0).

A Microsoft desligou a senha no IMAP e no SMTP das contas Outlook, Hotmail e
Microsoft 365, e o Google so aceita senha de app com verificacao em duas
etapas. O caminho que os dois aceitam e o login deles: a pessoa entra na
pagina do proprio Google ou da propria Microsoft, no navegador, e o programa
recebe uma autorizacao para ler e enviar e-mail - nunca a senha.

O fluxo e o de aplicativo instalado (RFC 8252), com PKCE (RFC 7636):

  1. o programa sobe um servidor HTTP temporario em 127.0.0.1, numa porta
     livre, e abre o navegador padrao na pagina de login do provedor;
  2. a pessoa entra e autoriza; o provedor manda o navegador de volta para
     http://127.0.0.1:<porta>/ com um `code` e o `state` que o programa
     inventou - `state` diferente e recusado;
  3. o `code`, junto do verificador PKCE, vira um access token (vale ~1 h) e
     um refresh token (vale ate ser revogado - ou 7 dias, no modo Teste do
     Google).

O refresh token vai para a DPAPI, como a senha; o access token fica so na
memoria e e renovado antes de vencer. IMAP e SMTP entram com XOAUTH2.

Os client IDs sao do aplicativo PAULUS e vem no codigo (src/oauth_app.py),
iguais em toda instalacao. Nenhum ID de outro programa e usado: provedor sem
ID nao aparece na tela. O roteiro para registrar esta em docs/email-oauth.md.

Tudo aqui e biblioteca padrao: urllib, http.server, secrets.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PRAZO_LOGIN = 300          # segundos esperando a pessoa entrar no navegador
TEMPO_REDE = 20            # segundos por chamada ao servidor de token
MARGEM_RENOVAR = 120       # renova o access token quando faltar menos que isso

PROVEDORES: dict[str, dict] = {
    "google": {
        "rotulo": "Google",
        "autorizar": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "escopos": "https://mail.google.com/ openid email",
        # offline: devolve refresh token. consent: devolve de novo quando a
        # pessoa ja tinha autorizado antes - sem isso, o segundo login vem sem
        # refresh token e a conta cairia em uma hora.
        "extras": {"access_type": "offline", "prompt": "consent"},
        "escopo_na_troca": False,
        "precisa_secret": True,
        "host_redirect": "127.0.0.1",
        "imap": ("imap.gmail.com", 993),
        "smtp": ("smtp.gmail.com", 587),
    },
    "microsoft": {
        "rotulo": "Microsoft",
        "autorizar": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "escopos": (
            "https://outlook.office.com/IMAP.AccessAsUser.All "
            "https://outlook.office.com/SMTP.Send offline_access openid email"
        ),
        "extras": {"prompt": "select_account"},
        # A Microsoft quer o escopo tambem na troca e na renovacao.
        "escopo_na_troca": True,
        "precisa_secret": False,
        # O portal do Azure registra "http://localhost" para app de desktop e
        # aceita qualquer porta nele; 127.0.0.1 exige editar o manifesto.
        "host_redirect": "localhost",
        "imap": ("outlook.office365.com", 993),
        "smtp": ("smtp.office365.com", 587),
    },
}


class ErroOAuth(RuntimeError):
    """
    Falha do login, ja em portugues.

    `precisa_entrar` separa o que se resolve entrando de novo (refresh token
    revogado ou vencido) do que nao se resolve (sem internet, ID faltando):
    marcar a conta como "precisa entrar de novo" por causa de uma queda de
    rede faria a pessoa refazer o login a toa.
    """

    def __init__(self, mensagem: str, *, precisa_entrar: bool = False) -> None:
        super().__init__(mensagem)
        self.precisa_entrar = precisa_entrar


def rotulo(provedor: str) -> str:
    return PROVEDORES.get(provedor, {}).get("rotulo", provedor)


# ------------------------------------------------------------------ PKCE


def gerar_pkce() -> tuple[str, str]:
    """(verificador, desafio S256), como a RFC 7636 manda."""
    verificador = secrets.token_urlsafe(64)[:96]
    desafio = desafio_s256(verificador)
    return verificador, desafio


def desafio_s256(verificador: str) -> str:
    resumo = hashlib.sha256(verificador.encode("ascii")).digest()
    return base64.urlsafe_b64encode(resumo).decode("ascii").rstrip("=")


def url_autorizacao(provedor: str, client_id: str, redirect_uri: str, state: str,
                    desafio: str, *, login_hint: str = "", endpoint: str = "",
                    escopos: str = "", incremental: bool = False, so_identidade: bool = False) -> str:
    """
    O endereco que o navegador abre.

    `escopos` troca os do e-mail (a Agenda, o Drive - src/google_servicos.py).
    `incremental` e a autorizacao incremental do Google: a permissao nova se
    soma as que ja existem, e o refresh token que volta vale para todas.
    """
    dados = PROVEDORES[provedor]
    parametros = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": escopos or dados["escopos"],
        "state": state,
        "code_challenge": desafio,
        "code_challenge_method": "S256",
        **dados["extras"],
    }
    # So quem e (destravar, confirmar, vincular sem os servicos): sem
    # refresh token a guardar, o "prompt=consent" so fazia o Google pedir a
    # confirmacao em toda entrada (02/10). Sem ele, pergunta so na primeira.
    if so_identidade:
        parametros.pop("prompt", None)
        parametros.pop("access_type", None)
    if login_hint:
        parametros["login_hint"] = login_hint
    if incremental:
        parametros["include_granted_scopes"] = "true"
    base = endpoint or dados["autorizar"]
    return base + "?" + urllib.parse.urlencode(parametros, quote_via=urllib.parse.quote)


# --------------------------------------------------- o servidor de volta


# A pagina da volta (os tres estados: sucesso, negado, expirado) mora em
# src/pagina_retorno.py, no desenho de docs/ui/login-google.
import pagina_retorno  # noqa: E402

# Depois que o login termina (ou e cancelado), a porta fica aberta mais este
# tempo, respondendo "este login expirou": fechar na hora deixava o navegador
# que voltava atrasado numa pagina de "conexao recusada".
FICAR_ABERTO_DEPOIS = 120


class _Servidor(HTTPServer):
    # Sem SO_REUSEADDR: no Windows ele deixa outro processo ocupar a mesma
    # porta, e o code poderia ir parar em outro lugar.
    allow_reuse_address = False


class _ServidorV6(_Servidor):
    address_family = socket.AF_INET6


class Loopback:
    """
    O servidor HTTP que recebe o navegador de volta.

    Escuta so em 127.0.0.1 (e em ::1, na mesma porta, quando da: o navegador
    pode resolver "localhost" para o IPv6 primeiro). Aceita um unico `code`,
    e so com o `state` certo - qualquer outro pedido recebe uma pagina dizendo
    que nao veio do PAULUS e nao muda nada.
    """

    def __init__(self, state: str, provedor: str = "Google", tema: str = "escuro") -> None:
        self.state = state
        self.provedor = provedor
        self.tema = tema
        # O andamento da conexao (para a pagina mostrar o e-mail e o fim) e o
        # "Voltar ao PAULUS" (traz a janela para frente): quem cria diz.
        self.situacao = None
        self.ao_voltar = None
        self.encerrado = False
        self.resultado: dict | None = None
        self.recusados = 0
        self._chegou = threading.Event()
        self._servidores: list[HTTPServer] = []
        self._threads: list[threading.Thread] = []
        self.porta = 0

    def iniciar(self) -> int:
        manipulador = self._manipulador()
        principal = _Servidor(("127.0.0.1", 0), manipulador)
        self.porta = principal.server_address[1]
        self._servidores.append(principal)
        try:
            self._servidores.append(_ServidorV6(("::1", self.porta), manipulador))
        except OSError:
            pass                    # sem IPv6, ou porta ocupada no ::1: segue so com o IPv4
        for srv in self._servidores:
            t = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
            t.start()
            self._threads.append(t)
        return self.porta

    def _manipulador(self):
        dono = self

        class Manipulador(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:       # nada no console
                return

            def _responder(self, codigo: int, html: str) -> None:
                corpo = html.encode("utf-8")
                self.send_response(codigo)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(corpo)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(corpo)

            def _json(self, codigo: int, dados: dict) -> None:
                corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
                self.send_response(codigo)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(corpo)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(corpo)

            def _pagina(self, codigo: int, estado: str, **extra) -> None:
                self._responder(codigo, pagina_retorno.pagina(estado, provedor=dono.provedor, tema=dono.tema,
                                                              porta=dono.porta, **extra))

            def do_GET(self) -> None:  # noqa: N802 - nome do http.server
                partes = urllib.parse.urlsplit(self.path)
                consulta = urllib.parse.parse_qs(partes.query)
                pega = lambda k: (consulta.get(k) or [""])[0]  # noqa: E731
                state, code, erro = pega("state"), pega("code"), pega("error")
                certo = bool(state) and secrets.compare_digest(state, dono.state)

                # A pagina pergunta o andamento e pede para trazer o PAULUS
                # para frente - so com o state deste login.
                if partes.path == "/estado":
                    situacao = dono.situacao() if (certo and dono.situacao) else {}
                    self._json(200 if certo else 403, situacao if certo else {"fase": "desconhecido"})
                    return
                if partes.path == "/voltar":
                    if certo and dono.ao_voltar:
                        try:
                            dono.ao_voltar()
                        except Exception:
                            pass
                    self.send_response(204)
                    self.end_headers()
                    return
                if partes.path == "/favicon.ico":
                    # O "P" do programa na aba desta pagina.
                    icone = Path(__file__).resolve().parent.parent / "frontend" / "img" / "paulus.ico"
                    try:
                        corpo = icone.read_bytes()
                    except OSError:
                        corpo = b""
                    self.send_response(200 if corpo else 404)
                    self.send_header("Content-Type", "image/x-icon")
                    self.send_header("Content-Length", str(len(corpo)))
                    self.send_header("Cache-Control", "max-age=86400")
                    self.end_headers()
                    self.wfile.write(corpo)
                    return
                if not state and not code and not erro:
                    self._pagina(404, "expirado")            # afins
                    return
                if dono.encerrado or dono._chegou.is_set() or not certo:
                    dono.recusados += 1
                    self._pagina(400, "expirado")
                    return
                if erro:
                    dono.resultado = {"erro": erro, "descricao": pega("error_description")}
                    self._pagina(200, "negado", detalhe="error=" + erro)
                elif code:
                    dono.resultado = {"code": code}
                    self._pagina(200, "sucesso", escopos=pega("scope"), state=state)
                else:
                    self._pagina(400, "expirado")
                    return
                dono._chegou.set()

        return Manipulador

    def esperar(self, prazo: float, cancelado: threading.Event | None = None) -> dict:
        """Espera o navegador voltar. Devolve {"code": ...} ou levanta ErroOAuth."""
        fim = time.monotonic() + prazo
        while not self._chegou.wait(0.2):
            if cancelado is not None and cancelado.is_set():
                raise ErroOAuth("login cancelado")
            if time.monotonic() >= fim:
                minutos = max(1, round(prazo / 60))
                raise ErroOAuth(
                    f"passaram {minutos} min sem o navegador voltar com o login. "
                    "Nada foi guardado - tente de novo quando quiser."
                )
        resultado = self.resultado or {}
        if resultado.get("erro"):
            if resultado["erro"] == "access_denied":
                raise ErroOAuth("o acesso não foi autorizado na página de login")
            detalhe = resultado.get("descricao") or resultado["erro"]
            raise ErroOAuth(f"a página de login devolveu um erro: {detalhe}")
        return resultado

    def encerrar(self, depois: float = FICAR_ABERTO_DEPOIS) -> None:
        """O login acabou: a porta responde "expirou" por mais um tempo e fecha."""
        self.encerrado = True
        t = threading.Timer(depois, self.fechar)
        t.daemon = True
        t.start()

    def fechar(self) -> None:
        for srv in self._servidores:
            try:
                srv.shutdown()
                srv.server_close()
            except Exception:
                pass
        self._servidores.clear()


# ------------------------------------------------------------ os tokens


def _postar(url: str, campos: dict) -> dict:
    """POST de formulario ao servidor de token; devolve o JSON."""
    corpo = urllib.parse.urlencode(campos).encode("ascii")
    pedido = urllib.request.Request(
        url, data=corpo, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(pedido, timeout=TEMPO_REDE) as resposta:
            return json.loads(resposta.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        try:
            bruto = json.loads(exc.read().decode("utf-8") or "{}")
        except (ValueError, OSError):
            bruto = {}
        codigo = str(bruto.get("error", "")) or f"HTTP {exc.code}"
        descricao = str(bruto.get("error_description", "")).split("\r\n")[0][:240]
        if codigo == "invalid_grant":
            raise ErroOAuth(
                "a autorização desta conta venceu ou foi revogada - é preciso entrar de novo",
                precisa_entrar=True,
            ) from exc
        if codigo in ("invalid_client", "unauthorized_client"):
            raise ErroOAuth(
                "o provedor recusou o aplicativo Paulus - o registro dele (src/oauth_app.py) precisa ser conferido por quem mantém o programa"
                + (f" ({descricao})" if descricao else ""),
            ) from exc
        raise ErroOAuth(f"o servidor de login recusou o pedido: {codigo}"
                        + (f" - {descricao}" if descricao else "")) from exc
    except (urllib.error.URLError, socket.timeout, OSError) as exc:
        raise ErroOAuth("não consegui falar com o servidor de login - confira a internet") from exc
    except ValueError as exc:
        raise ErroOAuth("o servidor de login respondeu algo que não entendi") from exc


def _com_validade(tokens: dict) -> dict:
    try:
        dura = int(tokens.get("expires_in") or 3600)
    except (TypeError, ValueError):
        dura = 3600
    tokens["expira_em"] = time.time() + dura
    return tokens


# O escopo que abre a caixa, por provedor. O login pode entrar sem ele: o
# Google descarta escopo que o app nao declarou em "Acesso a dados", e a
# tela de consentimento deixa a pessoa desmarcar o Gmail. Sem ele, o
# servidor de e-mail recusaria o acesso depois, com uma frase generica.
ESCOPO_DO_EMAIL = {"google": "https://mail.google.com/"}


def _conferir_escopo_do_email(provedor: str, tokens: dict) -> None:
    exigido = ESCOPO_DO_EMAIL.get(provedor)
    concedidos = str(tokens.get("scope") or "").split()
    if exigido and concedidos and exigido not in concedidos:
        raise ErroOAuth(
            "o Google entrou, mas não concedeu o acesso ao Gmail - na tela de permissão, "
            "marque o acesso aos e-mails. Se essa opção nem aparece, o escopo "
            "https://mail.google.com/ precisa estar em Acesso a dados, no Google Cloud")


def trocar_codigo(provedor: str, credenciais: dict, code: str, verificador: str,
                  redirect_uri: str, *, endpoint: str = "", conferir_email: bool = True) -> dict:
    """O `code` do navegador vira access token e refresh token."""
    dados = PROVEDORES[provedor]
    campos = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": credenciais.get("client_id", ""),
        "code_verifier": verificador,
    }
    if credenciais.get("client_secret"):
        campos["client_secret"] = credenciais["client_secret"]
    if dados["escopo_na_troca"]:
        campos["scope"] = dados["escopos"]
    tokens = _postar(endpoint or dados["token"], campos)
    if not tokens.get("access_token"):
        raise ErroOAuth("o servidor de login não devolveu o acesso")
    if conferir_email:
        _conferir_escopo_do_email(provedor, tokens)
    return _com_validade(tokens)


def renovar(provedor: str, credenciais: dict, refresh_token: str, *, endpoint: str = "") -> dict:
    """Um access token novo a partir do refresh token."""
    dados = PROVEDORES[provedor]
    campos = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": credenciais.get("client_id", ""),
    }
    if credenciais.get("client_secret"):
        campos["client_secret"] = credenciais["client_secret"]
    if dados["escopo_na_troca"]:
        campos["scope"] = dados["escopos"]
    tokens = _postar(endpoint or dados["token"], campos)
    if not tokens.get("access_token"):
        raise ErroOAuth("o servidor de login não devolveu o acesso")
    _conferir_escopo_do_email(provedor, tokens)
    return _com_validade(tokens)


# Onde se revoga a autorizacao inteira (RFC 7009). So o Google: e o que a
# ordem de desvincular da Minha conta pede (src/google_nuvem.py).
REVOGAR = {"google": "https://oauth2.googleapis.com/revoke"}


def revogar(provedor: str, token: str, *, endpoint: str = "") -> None:
    """
    Revoga no provedor a autorizacao de onde veio o `token` - de preferencia o
    refresh token. No Google isso desfaz a concessao inteira desta conta ao
    aplicativo PAULUS: o refresh token e os access tokens dela param de valer,
    com todos os escopos juntos (o Google nao revoga um escopo sozinho).

    Token que o provedor ja nao reconhece (vencido ou revogado antes) conta
    como revogado: nao sobra concessao para desfazer. Sem falar com o
    provedor, ou com outra recusa, levanta ErroOAuth - e quem chamou tenta de
    novo depois.
    """
    url = endpoint or REVOGAR.get(provedor, "")
    if not url:
        raise ErroOAuth(f"o {rotulo(provedor)} não tem como revogar por aqui")
    if not token:
        return
    pedido = urllib.request.Request(
        url, data=urllib.parse.urlencode({"token": token}).encode("ascii"), method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(pedido, timeout=TEMPO_REDE):
            return
    except urllib.error.HTTPError as exc:
        try:
            bruto = json.loads(exc.read().decode("utf-8") or "{}")
        except (ValueError, OSError):
            bruto = {}
        codigo = str(bruto.get("error", "")) or f"HTTP {exc.code}"
        if exc.code == 400 and codigo in ("invalid_token", "invalid_grant"):
            return
        raise ErroOAuth(f"o {rotulo(provedor)} recusou revogar o acesso: {codigo}") from exc
    except (urllib.error.URLError, socket.timeout, OSError) as exc:
        raise ErroOAuth(f"não consegui falar com o {rotulo(provedor)} para revogar o acesso - confira a internet") from exc


def quem_entrou(tokens: dict) -> tuple[str, str]:
    """
    (e-mail, nome) do id_token.

    Sem conferir assinatura, e isso e o que a especificacao permite: o
    id_token veio direto do servidor de token, por TLS, em resposta a um
    pedido nosso - nao passou pelo navegador. Serve para saber o endereco, nao
    para autenticar ninguem; quem autentica e o servidor IMAP, com o token.
    """
    bruto = str(tokens.get("id_token") or "")
    partes = bruto.split(".")
    if len(partes) < 2:
        return "", ""
    carga = partes[1] + "=" * (-len(partes[1]) % 4)
    try:
        dados = json.loads(base64.urlsafe_b64decode(carga.encode("ascii")))
    except (ValueError, TypeError):
        return "", ""
    email = str(dados.get("email") or dados.get("preferred_username") or "").strip()
    if "@" not in email:
        email = ""
    return email, str(dados.get("name") or "").strip()


def xoauth2(email: str, token: str) -> str:
    """A linha do SASL XOAUTH2, antes do base64 que imaplib e smtplib aplicam."""
    return f"user={email}\x01auth=Bearer {token}\x01\x01"


# ------------------------------------------------------ o login inteiro


class Entrada:
    """
    Um login em andamento: navegador aberto, esperando a volta.

    Roda numa thread para a tela poder perguntar o andamento e oferecer
    Cancelar. `ao_concluir(provedor, tokens, email, nome)` recebe o resultado
    e devolve o que a tela deve mostrar (a conta ligada).
    """

    def __init__(self, provedor: str, credenciais: dict, ao_concluir, *,
                 login_hint: str = "", abrir=None, prazo: float = PRAZO_LOGIN,
                 endpoints: dict | None = None, escopos: str = "", exigir: tuple[str, ...] = (),
                 tema: str = "escuro", ao_voltar=None, so_identidade: bool = False) -> None:
        if provedor not in PROVEDORES:
            raise ErroOAuth("provedor desconhecido")
        if not credenciais.get("client_id"):
            raise ErroOAuth(f"este Paulus ainda não traz o login do {rotulo(provedor)}")
        if PROVEDORES[provedor]["precisa_secret"] and not credenciais.get("client_secret"):
            raise ErroOAuth(f"este Paulus ainda não traz o login do {rotulo(provedor)}")
        self.provedor = provedor
        self.credenciais = credenciais
        self.ao_concluir = ao_concluir
        self.login_hint = login_hint
        self.abrir = abrir or webbrowser.open
        self.prazo = prazo
        self.endpoints = endpoints or {}
        # Pedir mais que o e-mail (a Agenda, o Drive): os escopos a pedir,
        # somados aos que ja existem, e os que tem de voltar concedidos.
        self.escopos = escopos
        self.exigir = tuple(exigir)
        self.tema = tema
        self.ao_voltar = ao_voltar
        # So saber QUEM e (o vinculo do PAULUS a conta Google, src/vinculo.py):
        # sem o e-mail, sem a autorizacao duradoura.
        self.so_identidade = so_identidade
        self.email = ""
        self.id = secrets.token_hex(8)
        self.fase = "preparando"
        self.mensagem = ""
        self.resultado: dict | None = None
        self.url = ""
        self.abriu_navegador = False
        self._cancelado = threading.Event()
        self._loopback: Loopback | None = None
        self._thread: threading.Thread | None = None

    def iniciar(self) -> dict:
        state = secrets.token_urlsafe(24)
        self._verificador, desafio = gerar_pkce()
        self._loopback = Loopback(state, provedor=rotulo(self.provedor), tema=self.tema)
        self._loopback.situacao = lambda: {"fase": self.fase, "email": self.email, "mensagem": self.mensagem}
        self._loopback.ao_voltar = self.ao_voltar
        porta = self._loopback.iniciar()
        host = PROVEDORES[self.provedor]["host_redirect"]
        self.redirect_uri = f"http://{host}:{porta}/" if host == "127.0.0.1" else f"http://{host}:{porta}"
        self.url = url_autorizacao(
            self.provedor, self.credenciais["client_id"], self.redirect_uri, state, desafio,
            login_hint=self.login_hint, endpoint=self.endpoints.get("autorizar", ""),
            escopos=self.escopos, incremental=bool(self.escopos), so_identidade=self.so_identidade,
        )
        self.fase = "aguardando"
        self._thread = threading.Thread(target=self._rodar, daemon=True)
        self._thread.start()
        try:
            self.abriu_navegador = bool(self.abrir(self.url))
        except Exception:
            self.abriu_navegador = False
        return self.andamento()

    def _rodar(self) -> None:
        try:
            volta = self._loopback.esperar(self.prazo, self._cancelado)
            self.fase = "trocando"
            tokens = trocar_codigo(
                self.provedor, self.credenciais, volta["code"], self._verificador,
                self.redirect_uri, endpoint=self.endpoints.get("token", ""),
                conferir_email=not self.so_identidade,
            )
            concedidos = str(tokens.get("scope") or "").split()
            faltando = [e for e in self.exigir if e not in concedidos]
            if faltando:
                raise ErroOAuth(
                    "o Google entrou, mas não concedeu a permissão pedida - na tela do Google, "
                    "marque a caixa do serviço (" + ", ".join(e.rsplit("/", 1)[-1] for e in faltando) + ") e tente de novo"
                )
            if not tokens.get("refresh_token") and not self.so_identidade:
                raise ErroOAuth(
                    "o login funcionou, mas o provedor não devolveu a autorização duradoura "
                    "(refresh token) - sem ela a conta cairia em uma hora. Tente entrar de novo."
                )
            email, nome = quem_entrou(tokens)
            self.email = email or ""
            if not email:
                raise ErroOAuth("o login funcionou, mas não consegui saber qual é o endereço de e-mail")
            if self._cancelado.is_set():
                raise ErroOAuth("login cancelado")
            self.fase = "testando"
            self.resultado = self.ao_concluir(self.provedor, tokens, email, nome)
            self.fase = "pronto"
        except ErroOAuth as exc:
            self.fase = "cancelado" if self._cancelado.is_set() else "erro"
            self.mensagem = str(exc)
        except Exception as exc:  # o que escapar vira mensagem, nao thread morta calada
            self.fase = "erro"
            self.mensagem = f"o login falhou: {exc}"
        finally:
            if self._loopback:
                self._loopback.encerrar()

    def cancelar(self) -> None:
        self._cancelado.set()
        if self.fase in ("preparando", "aguardando"):
            self.fase = "cancelado"
            self.mensagem = "login cancelado"

    def reabrir(self) -> dict:
        """
        Abre de novo a mesma pagina de login, sem comecar outro login: quem
        fechou a aba (ou o navegador nao abriu) volta ao mesmo pedido, e a
        resposta continua caindo na mesma porta local.
        """
        if self.fase == "aguardando" and self.url:
            try:
                self.abriu_navegador = bool(self.abrir(self.url))
            except Exception:
                self.abriu_navegador = False
        return self.andamento()

    @property
    def terminou(self) -> bool:
        return self.fase in ("pronto", "erro", "cancelado")

    def esperar(self, prazo: float = 10.0) -> None:
        if self._thread:
            self._thread.join(prazo)

    def andamento(self) -> dict:
        return {
            "id": self.id,
            "provedor": self.provedor,
            "rotulo": rotulo(self.provedor),
            "fase": self.fase,
            "mensagem": self.mensagem,
            "url": self.url if self.fase == "aguardando" else "",
            "abriu_navegador": self.abriu_navegador,
            "resultado": self.resultado,
            "prazo_s": int(self.prazo),
        }
