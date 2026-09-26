"""
Testes do login do e-mail com Google e Microsoft (OAuth 2.0).

Nenhum teste fala com o Google nem com a Microsoft. O servidor de token e um
http.server local, numa thread, que responde como os de verdade; o
"navegador" e uma chamada HTTP ao servidor de volta; IMAP e SMTP sao dubles.
Tudo em pasta temporaria: data/ e as contas de verdade nao sao tocados.

Cobre:

  - PKCE: o vetor da RFC 7636 e o verificador gerado
  - a URL de autorizacao de cada provedor
  - o servidor de volta: aceita code com o state certo, recusa state errado,
    trata "acesso negado", prazo vencido e cancelamento
  - troca de codigo e renovacao contra o servidor de token falso
  - a linha XOAUTH2, e IMAP/SMTP entrando com ela
  - refresh token guardado na DPAPI e lido de volta
  - renovacao recusada deixa a conta "precisa entrar de novo"; queda de rede nao
  - conta antiga, por senha, continua entrando por senha
  - as rotas da API: config, entrar, andamento, cancelar

    python tests/test_email_oauth.py
"""

from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import correio  # noqa: E402
import correio_contas  # noqa: E402
import correio_oauth  # noqa: E402
import segredos  # noqa: E402

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {detalhe}")
        _falhas.append(descricao)


# ------------------------------------------------ servidor de token falso


def _id_token(email: str, nome: str = "") -> str:
    def parte(dados: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(dados).encode()).decode().rstrip("=")
    return parte({"alg": "none"}) + "." + parte({"email": email, "name": nome}) + ".assinatura"


class TokenFalso:
    """Responde como o endpoint de token: authorization_code e refresh_token."""

    def __init__(self) -> None:
        self.pedidos: list[dict] = []
        self.email = "pessoa@gmail.com"
        self.girar_refresh = False
        self.contador = 0
        dono = self

        class Manipulador(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                return

            def do_POST(self) -> None:  # noqa: N802
                tamanho = int(self.headers.get("Content-Length") or 0)
                campos = dict(urllib.parse.parse_qsl(self.rfile.read(tamanho).decode()))
                dono.pedidos.append(campos)
                codigo, corpo = dono.responder(campos)
                bruto = json.dumps(corpo).encode()
                self.send_response(codigo)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(bruto)))
                self.end_headers()
                self.wfile.write(bruto)

        self.srv = HTTPServer(("127.0.0.1", 0), Manipulador)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}/token"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def responder(self, campos: dict) -> tuple[int, dict]:
        self.contador += 1
        if campos.get("client_id") == "cliente-ruim":
            return 401, {"error": "invalid_client", "error_description": "client desconhecido"}
        if campos.get("grant_type") == "authorization_code":
            if campos.get("code") != "codigo-bom" or not campos.get("code_verifier"):
                return 400, {"error": "invalid_grant"}
            return 200, {
                "access_token": f"acesso-{self.contador}", "expires_in": 3599,
                "refresh_token": "refresh-inicial", "token_type": "Bearer",
                "id_token": _id_token(self.email, "Pessoa de Teste"),
            }
        if campos.get("grant_type") == "refresh_token":
            if campos.get("refresh_token") == "revogado":
                return 400, {"error": "invalid_grant", "error_description": "Token has been expired or revoked."}
            corpo = {"access_token": f"renovado-{self.contador}", "expires_in": 3599, "token_type": "Bearer"}
            if self.girar_refresh:
                corpo["refresh_token"] = f"refresh-girado-{self.contador}"
            return 200, corpo
        return 400, {"error": "unsupported_grant_type"}

    def fechar(self) -> None:
        self.srv.shutdown()
        self.srv.server_close()


def _navegador(url: str, *, code: str = "codigo-bom", state: str | None = None,
               erro: str = "") -> int:
    """Faz o papel do navegador voltando do login: GET no redirect_uri."""
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
    volta = {"state": q["state"] if state is None else state}
    if erro:
        volta["error"] = erro
    else:
        volta["code"] = code
    redirect = q["redirect_uri"].replace("localhost", "127.0.0.1")
    alvo = redirect.rstrip("/") + "/?" + urllib.parse.urlencode(volta)
    try:
        with urllib.request.urlopen(alvo, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except urllib.error.URLError:
        return 0                     # o servidor de volta ja fechou


# ------------------------------------------------------------------ PKCE


def test_pkce() -> None:
    print("\nPKCE (S256)")
    # Vetor do apendice B da RFC 7636.
    checar(
        correio_oauth.desafio_s256("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk")
        == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
        "o desafio bate com o vetor da RFC 7636",
    )
    verificador, desafio = correio_oauth.gerar_pkce()
    permitidos = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
    checar(43 <= len(verificador) <= 128, f"verificador entre 43 e 128 caracteres ({len(verificador)})")
    checar(set(verificador) <= permitidos, "verificador so com caracteres nao reservados")
    checar(desafio == correio_oauth.desafio_s256(verificador) and "=" not in desafio,
           "desafio e o SHA-256 em base64url sem preenchimento")
    checar(correio_oauth.gerar_pkce()[0] != verificador, "cada login tem verificador novo")


def test_url_autorizacao() -> None:
    print("\nURL de autorizacao")
    url = correio_oauth.url_autorizacao(
        "google", "id-google.apps.googleusercontent.com", "http://127.0.0.1:5555/",
        "estado-x", "desafio-y", login_hint="pessoa@gmail.com",
    )
    base, _, consulta = url.partition("?")
    q = dict(urllib.parse.parse_qsl(consulta))
    checar(base == "https://accounts.google.com/o/oauth2/v2/auth", "Google: endpoint oficial")
    checar(q["scope"] == "https://mail.google.com/ openid email", "Google: escopo do Gmail + openid email")
    checar(q["access_type"] == "offline" and q["prompt"] == "consent", "Google: offline e consent")
    checar(q["code_challenge"] == "desafio-y" and q["code_challenge_method"] == "S256", "PKCE S256 na URL")
    checar(q["state"] == "estado-x" and q["response_type"] == "code", "state e response_type=code")
    checar(q["redirect_uri"] == "http://127.0.0.1:5555/" and q["login_hint"] == "pessoa@gmail.com",
           "redirect de loopback e login_hint")
    checar("client_secret" not in q, "o secret nunca vai na URL")

    url = correio_oauth.url_autorizacao("microsoft", "id-ms", "http://localhost:6000", "s", "d")
    base, _, consulta = url.partition("?")
    q = dict(urllib.parse.parse_qsl(consulta))
    checar(base == "https://login.microsoftonline.com/common/oauth2/v2.0/authorize", "Microsoft: endpoint common")
    checar(set(q["scope"].split()) == {
        "https://outlook.office.com/IMAP.AccessAsUser.All", "https://outlook.office.com/SMTP.Send",
        "offline_access", "openid", "email"}, "Microsoft: IMAP, SMTP, offline_access, openid, email")
    checar("login_hint" not in q, "sem e-mail, sem login_hint")


# ---------------------------------------------------- servidor de volta


def test_loopback() -> None:
    print("\nservidor de volta (loopback)")
    volta = correio_oauth.Loopback("estado-certo")
    porta = volta.iniciar()
    try:
        base = f"http://127.0.0.1:{porta}/"
        checar(porta > 0, f"escuta numa porta livre ({porta})")
        r = _navegador(base + "?redirect_uri=" + base + "&state=x", state="estado-errado")
        checar(r == 400, f"state errado recebe 400 ({r})")
        checar(volta.recusados == 1 and volta.resultado is None, "e nao conta como login")
        r = _navegador(base + "?redirect_uri=" + base + "&state=estado-certo")
        checar(r == 200, "state certo com code recebe a pagina de sucesso")
        checar(volta.esperar(2) == {"code": "codigo-bom"}, "esperar devolve o code")
        r = _navegador(base + "?redirect_uri=" + base + "&state=estado-certo")
        checar(r == 400, "um segundo code, mesmo com o state certo, e recusado")
    finally:
        volta.fechar()

    volta = correio_oauth.Loopback("s")
    porta = volta.iniciar()
    try:
        base = f"http://127.0.0.1:{porta}/"
        _navegador(base + "?redirect_uri=" + base + "&state=s", erro="access_denied")
        try:
            volta.esperar(2)
            checar(False, "acesso negado vira erro")
        except correio_oauth.ErroOAuth as exc:
            checar("não foi autorizado" in str(exc), f"acesso negado vira erro claro ({exc})")
    finally:
        volta.fechar()

    volta = correio_oauth.Loopback("s")
    volta.iniciar()
    inicio = time.monotonic()
    try:
        volta.esperar(0.6)
        checar(False, "prazo vencido vira erro")
    except correio_oauth.ErroOAuth as exc:
        checar("sem o navegador voltar" in str(exc) and time.monotonic() - inicio < 3,
               f"prazo vencido vira erro com explicacao ({exc})")
    finally:
        volta.fechar()

    volta = correio_oauth.Loopback("s")
    volta.iniciar()
    cancelado = threading.Event()
    threading.Timer(0.3, cancelado.set).start()
    try:
        volta.esperar(10, cancelado)
        checar(False, "cancelar interrompe a espera")
    except correio_oauth.ErroOAuth as exc:
        checar("cancelado" in str(exc), "cancelar interrompe a espera")
    finally:
        volta.fechar()


# ------------------------------------------------------------ os tokens


def test_troca_e_renovacao(token: TokenFalso) -> None:
    print("\ntroca de codigo e renovacao (servidor de token falso)")
    cred = {"client_id": "id-google", "client_secret": "segredo-google"}
    t = correio_oauth.trocar_codigo("google", cred, "codigo-bom", "verificador-1",
                                    "http://127.0.0.1:1/", endpoint=token.url)
    pedido = token.pedidos[-1]
    checar(t["access_token"].startswith("acesso-") and t["refresh_token"] == "refresh-inicial",
           "o code vira access e refresh token")
    checar(pedido["code_verifier"] == "verificador-1" and pedido["client_secret"] == "segredo-google",
           "a troca leva o verificador PKCE e o secret do Google")
    checar("scope" not in pedido, "Google: sem escopo na troca")
    checar(t["expira_em"] > time.time() + 3000, "guarda quando o access token vence")
    checar(correio_oauth.quem_entrou(t) == ("pessoa@gmail.com", "Pessoa de Teste"),
           "o id_token diz qual e o endereco")

    t = correio_oauth.trocar_codigo("microsoft", {"client_id": "id-ms"}, "codigo-bom", "v",
                                    "http://localhost:1", endpoint=token.url)
    pedido = token.pedidos[-1]
    checar("client_secret" not in pedido and "IMAP.AccessAsUser.All" in pedido.get("scope", ""),
           "Microsoft: cliente publico (sem secret) e escopo na troca")

    r = correio_oauth.renovar("google", cred, "refresh-inicial", endpoint=token.url)
    checar(r["access_token"].startswith("renovado-") and token.pedidos[-1]["grant_type"] == "refresh_token",
           "renovar devolve access token novo")
    try:
        correio_oauth.renovar("google", cred, "revogado", endpoint=token.url)
        checar(False, "refresh revogado vira erro")
    except correio_oauth.ErroOAuth as exc:
        checar(exc.precisa_entrar, "refresh revogado (invalid_grant) pede para entrar de novo")
    try:
        correio_oauth.renovar("google", {"client_id": "cliente-ruim"}, "x", endpoint=token.url)
        checar(False, "client errado vira erro")
    except correio_oauth.ErroOAuth as exc:
        checar(not exc.precisa_entrar and "aplicativo PAULUS" in str(exc), "client ID recusado diz que o registro do aplicativo precisa ser conferido")
    try:
        correio_oauth.renovar("google", cred, "x", endpoint="http://127.0.0.1:9/token")
        checar(False, "sem rede vira erro")
    except correio_oauth.ErroOAuth as exc:
        checar(not exc.precisa_entrar, f"queda de rede NAO pede para entrar de novo ({exc})")


def test_xoauth2() -> None:
    print("\nlinha XOAUTH2")
    checar(correio_oauth.xoauth2("a@b.com", "tok") == "user=a@b.com\x01auth=Bearer tok\x01\x01",
           "formato user=...^Aauth=Bearer ...^A^A")
    checar(correio.xoauth2("a@b.com", "tok") == correio_oauth.xoauth2("a@b.com", "tok"),
           "o mesmo formato no modulo do correio")


class _IMAPFalso:
    visto: dict = {}

    def __init__(self, host, porta, timeout=None):
        _IMAPFalso.visto = {"host": host, "porta": porta}

    def authenticate(self, mecanismo, resposta):
        _IMAPFalso.visto.update(mecanismo=mecanismo, linha=resposta(b""))
        return ("OK", [b""])

    def login(self, usuario, senha):
        _IMAPFalso.visto.update(mecanismo="LOGIN", usuario=usuario, senha=senha)
        return ("OK", [b""])

    def list(self):
        return ("OK", [b"INBOX"])

    def logout(self):
        pass


class _SMTPFalso:
    visto: dict = {}

    def __init__(self, host, porta, timeout=None):
        _SMTPFalso.visto = {"host": host, "porta": porta}

    def starttls(self):
        _SMTPFalso.visto["tls"] = True

    def ehlo_or_helo_if_needed(self):
        pass

    def auth(self, mecanismo, objeto, initial_response_ok=True):
        _SMTPFalso.visto.update(mecanismo=mecanismo, linha=objeto(), resposta_ao_erro=objeto(b"{}"))

    def login(self, usuario, senha):
        _SMTPFalso.visto.update(mecanismo="LOGIN", usuario=usuario, senha=senha)

    def quit(self):
        pass


def _com_dubles(funcao):
    antes = (correio.imaplib.IMAP4_SSL, correio.smtplib.SMTP)
    correio.imaplib.IMAP4_SSL, correio.smtplib.SMTP = _IMAPFalso, _SMTPFalso
    try:
        return funcao()
    finally:
        correio.imaplib.IMAP4_SSL, correio.smtplib.SMTP = antes


def test_imap_smtp_com_xoauth2() -> None:
    print("\nIMAP e SMTP com XOAUTH2")
    conta = correio_contas.Conta(id="g", email="pessoa@gmail.com", autenticacao="google",
                                 **correio_contas.SERVIDORES_OAUTH["google"])
    r = _com_dubles(lambda: correio.testar(conta, "tok-123"))
    checar(r["ok"], "entrada e saida funcionam com o token")
    checar(_IMAPFalso.visto["mecanismo"] == "XOAUTH2"
           and _IMAPFalso.visto["linha"] == b"user=pessoa@gmail.com\x01auth=Bearer tok-123\x01\x01",
           "IMAP: AUTHENTICATE XOAUTH2 com a linha certa")
    checar(_IMAPFalso.visto["host"] == "imap.gmail.com" and _IMAPFalso.visto["porta"] == 993, "IMAP do Gmail na 993")
    checar(_SMTPFalso.visto["mecanismo"] == "XOAUTH2" and _SMTPFalso.visto.get("tls")
           and _SMTPFalso.visto["linha"] == "user=pessoa@gmail.com\x01auth=Bearer tok-123\x01\x01",
           "SMTP: STARTTLS e AUTH XOAUTH2")
    checar(_SMTPFalso.visto["resposta_ao_erro"] == "", "SMTP: responde vazio ao desafio de erro (sem laco)")

    ms = correio_contas.Conta(id="m", email="pessoa@outlook.com", autenticacao="microsoft",
                              **correio_contas.SERVIDORES_OAUTH["microsoft"])
    _com_dubles(lambda: correio.testar(ms, "tok"))
    checar(_IMAPFalso.visto["host"] == "outlook.office365.com" and _SMTPFalso.visto["host"] == "smtp.office365.com"
           and _SMTPFalso.visto["porta"] == 587, "Microsoft: outlook.office365.com e smtp.office365.com:587")

    antiga = correio_contas.Conta(id="s", email="eu@escritorio.adv.br", imap_host="imap.x", smtp_host="smtp.x")
    _com_dubles(lambda: correio.testar(antiga, "senha-de-app"))
    checar(_IMAPFalso.visto["mecanismo"] == "LOGIN" and _IMAPFalso.visto["senha"] == "senha-de-app"
           and _SMTPFalso.visto["mecanismo"] == "LOGIN", "conta por senha continua com LOGIN")

    erro = correio._erro_amigavel(Exception("AUTHENTICATE failed."), "entrada", conta)
    checar("login Google" in str(erro) and "Senha de app" not in str(erro),
           "recusa na conta de login nao fala em senha de app")


# ------------------------------------------------------------- as contas


def test_contas(tmp: Path, token: TokenFalso) -> None:
    print("\nrefresh token guardado e renovacao automatica")
    caminho = tmp / "contas.json"
    contas = correio_contas.Contas(caminho)
    contas.credenciais_oauth = lambda p: {"client_id": "id-google", "client_secret": "segredo"}
    contas.endpoints_oauth = {"google": {"token": token.url}}

    antiga = contas.salvar_conta({"email": "eu@escritorio.adv.br", "imap_host": "imap.x", "smtp_host": "smtp.x"},
                                 "senha-antiga")
    tokens = {"access_token": "acesso-1", "refresh_token": "refresh-inicial", "expira_em": time.time() + 3600}
    conta = contas.ligar_oauth("google", "pessoa@gmail.com", "Pessoa", tokens)
    checar(conta.autenticacao == "google" and conta.imap_host == "imap.gmail.com", "a conta de login nasce com os servidores do Gmail")
    bruto = caminho.read_text(encoding="utf-8")
    if segredos.disponivel():
        checar("refresh-inicial" not in bruto and conta.refresh_protegido, "o refresh token nao fica em texto no disco")
    checar("acesso-1" not in bruto, "o access token nunca vai para o disco")
    checar(contas.credencial(conta) == "acesso-1", "token ainda valido: usa o da memoria, sem rede")

    de_novo = correio_contas.Contas(caminho)
    de_novo.credenciais_oauth = contas.credenciais_oauth
    de_novo.endpoints_oauth = contas.endpoints_oauth
    reaberta = de_novo.por_email("pessoa@gmail.com")
    if segredos.disponivel():
        checar(de_novo._refresh(reaberta) == "refresh-inicial", "depois de reabrir, a DPAPI devolve o refresh token")
        antes = len(token.pedidos)
        acesso = de_novo.credencial(reaberta)
        checar(acesso.startswith("renovado-") and len(token.pedidos) == antes + 1,
               "sem access token na memoria, renova sozinho antes de usar")
        checar(token.pedidos[-1]["refresh_token"] == "refresh-inicial", "renova com o refresh guardado")
        checar(de_novo.credencial(reaberta) == acesso and len(token.pedidos) == antes + 1,
               "e reaproveita o renovado enquanto vale")
        de_novo._tokens[reaberta.id] = ("quase", time.time() + 30)
        checar(de_novo.credencial(reaberta).startswith("renovado-"), "renova antes de vencer (margem)")

        token.girar_refresh = True
        de_novo._tokens.pop(reaberta.id)
        de_novo.credencial(reaberta)
        token.girar_refresh = False
        checar(de_novo._refresh(reaberta).startswith("refresh-girado-"),
               "refresh token trocado pelo provedor e guardado no lugar do antigo")

    velha = de_novo.por_email("eu@escritorio.adv.br")
    checar(velha.autenticacao == "senha" and de_novo.credencial(velha) == ("senha-antiga" if segredos.disponivel() else ""),
           "conta antiga continua por senha e devolve a senha")

    print("\nrenovacao recusada e queda de rede")
    de_novo._refresh_vivos[reaberta.id] = "revogado"
    de_novo._tokens.pop(reaberta.id, None)
    try:
        de_novo.credencial(reaberta)
        checar(False, "revogado levanta erro")
    except correio_oauth.ErroOAuth as exc:
        checar(exc.precisa_entrar, "refresh revogado levanta erro de entrar de novo")
    checar(reaberta.precisa_entrar and reaberta.situacao == "precisa entrar de novo",
           "a conta fica \"precisa entrar de novo\"")
    tela = reaberta.to_dict()
    checar(not tela["tem_senha"] and tela["por_login"] and "refresh_protegido" not in tela,
           "a tela ve que falta entrar, e nunca ve o refresh token")
    checar(correio_contas.Contas(caminho).por_email("pessoa@gmail.com").precisa_entrar,
           "e isso sobrevive a fechar o programa")

    de_novo.ligar_oauth("google", "pessoa@gmail.com", "", {"access_token": "a2", "refresh_token": "r2", "expira_em": time.time() + 3600})
    checar(not reaberta.precisa_entrar and not reaberta.ultimo_erro and de_novo.credencial(reaberta) == "a2",
           "entrar de novo religa a mesma conta")

    de_novo.endpoints_oauth = {"google": {"token": "http://127.0.0.1:9/token"}}
    de_novo._tokens.pop(reaberta.id)
    try:
        de_novo.credencial(reaberta)
        checar(False, "sem rede levanta erro")
    except correio_oauth.ErroOAuth as exc:
        checar(not exc.precisa_entrar and not reaberta.precisa_entrar,
               "sem internet: erro, mas a conta NAO fica marcada para entrar de novo")

    de_novo.credenciais_oauth = lambda p: {}
    try:
        de_novo.credencial(reaberta)
        checar(False, "sem client ID levanta erro")
    except correio_oauth.ErroOAuth as exc:
        checar("não traz o login" in str(exc), "sem client ID, o erro diz que esta versão não traz o login")

    quantas = de_novo.esquecer_senhas()
    checar(quantas >= 1 and reaberta.refresh_protegido == "" and reaberta.precisa_entrar,
           "apagar as senhas apaga tambem a autorizacao do login")

    # Conta gravada antes do login existir: sem o campo autenticacao.
    antigo = tmp / "contas-antigas.json"
    antigo.write_text(json.dumps({"versao": 1, "contas": [{
        "id": "x1", "email": "eu@escritorio.adv.br", "imap_host": "imap.x", "smtp_host": "smtp.x",
        "senha_protegida": segredos.proteger("s3nha"),
    }]}), encoding="utf-8")
    lida = correio_contas.Contas(antigo).obter("x1")
    checar(lida.autenticacao == "senha" and not lida.por_login, "JSON antigo, sem o campo, carrega como senha")


def test_detectar() -> None:
    print("\nMicrosoft bloqueada so sem client ID")
    sem = correio_contas.detectar("alguem@outlook.com", sondar=False)
    checar(sem["bloqueado"] and "use outra conta" in sem["aviso"] and "Configura" not in sem["aviso"], "sem ID: bloqueada, sem mandar a pessoa configurar nada")
    com = correio_contas.detectar("alguem@hotmail.com", sondar=False, oauth={"microsoft": True})
    checar(not com["bloqueado"] and com["oauth"] == "microsoft" and "Entrar com Microsoft" in com["aviso"],
           "com ID: deixa de ser bloqueada e oferece Entrar com Microsoft")
    g = correio_contas.detectar("alguem@gmail.com", sondar=False, oauth={"google": True})
    checar(g["oauth"] == "google" and g["oauth_disponivel"] and not g["bloqueado"], "Gmail oferece o login do Google")


# ------------------------------------------------------- o login inteiro


def test_entrada_completa(token: TokenFalso) -> None:
    print("\no login inteiro: navegador, volta, troca")
    recebidos = []
    urls = []

    def abrir(url):
        urls.append(url)
        threading.Timer(0.2, lambda: _navegador(url)).start()
        return True

    e = correio_oauth.Entrada(
        "google", {"client_id": "id-google", "client_secret": "s"},
        lambda prov, tok, email, nome: recebidos.append((prov, email, nome)) or {"ok": True},
        abrir=abrir, endpoints={"token": token.url}, prazo=10,
    )
    inicio = e.iniciar()
    checar(inicio["fase"] == "aguardando" and inicio["abriu_navegador"], "abre o navegador e fica esperando")
    checar(inicio["url"].startswith("https://accounts.google.com/"), "a URL devolvida e a do Google")
    e.esperar(8)
    checar(e.fase == "pronto" and recebidos == [("google", "pessoa@gmail.com", "Pessoa de Teste")],
           f"volta, troca e entrega a conta ({e.fase} {e.mensagem})")
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(urls[0]).query))
    troca = [p for p in token.pedidos if p.get("grant_type") == "authorization_code"][-1]
    checar(correio_oauth.desafio_s256(troca["code_verifier"]) == q["code_challenge"],
           "o verificador enviado na troca e o do desafio da URL")
    checar(troca["redirect_uri"] == q["redirect_uri"], "o redirect da troca e o mesmo da URL")

    e = correio_oauth.Entrada("microsoft", {"client_id": "id-ms"}, lambda *a: {},
                              abrir=lambda url: True, endpoints={"token": token.url}, prazo=10)
    andamento = e.iniciar()
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(andamento["url"]).query))
    checar(q["redirect_uri"].startswith("http://localhost:"), "Microsoft volta para http://localhost:<porta>")
    e.cancelar()
    e.esperar(3)
    checar(e.fase == "cancelado", "Cancelar encerra o login")

    try:
        correio_oauth.Entrada("google", {"client_id": "x"}, lambda *a: {})
        checar(False, "Google sem secret nao comeca")
    except correio_oauth.ErroOAuth as exc:
        checar("não traz o login do Google" in str(exc), "Google sem client secret nem comeca, e diz o que falta")
    try:
        correio_oauth.Entrada("microsoft", {}, lambda *a: {})
        checar(False, "sem client ID nao comeca")
    except correio_oauth.ErroOAuth as exc:
        checar("não traz o login" in str(exc), "sem client ID nem comeca")


# --------------------------------------------------------------- a API


def test_api(tmp: Path, token: TokenFalso) -> None:
    print("\nrotas da API (preferencias e contas em pasta temporaria)")
    import webbrowser

    import api
    from config import Preferencias

    import oauth_app

    # O teste nao usa o oauth_app.json de verdade: parte de "sem IDs" e
    # liga os provedores so pelas variaveis de ambiente.
    arquivo_real = oauth_app.ARQUIVO
    oauth_app.ARQUIVO = tmp / "oauth_app-que-nao-existe.json"
    guardados = (api.estado.contas, api.estado.prefs, api.estado.entrada_oauth)
    endpoint_real = correio_oauth.PROVEDORES["microsoft"]["token"]
    abrir_real = webbrowser.open
    try:
        api.estado.prefs = Preferencias(tmp / "prefs.json")
        api.estado.contas = correio_contas.Contas(tmp / "contas-api.json")
        api.estado.contas.credenciais_oauth = api._credenciais_oauth

        info = api.email_contas()["oauth"]
        checar(not info["google"]["configurado"] and not info["microsoft"]["configurado"],
               "sem IDs: nenhum login disponivel")
        try:
            api.email_oauth_entrar(api.PedidoEntrada(provedor="microsoft"))
            checar(False, "sem ID a rota recusa")
        except api.HTTPException as exc:
            checar(exc.status_code == 400 and "não traz o login" in exc.detail, "sem ID, entrar e recusado com explicacao")

        # Os IDs sao do aplicativo PAULUS e vem do codigo (src/oauth_app.py);
        # as variaveis de ambiente sao o jeito de trocar sem mexer nele.
        os.environ["PAULUS_GOOGLE_CLIENT_ID"] = "123-abc.apps.googleusercontent.com"
        os.environ["PAULUS_GOOGLE_CLIENT_SECRET"] = "GOCSPX-segredo"
        os.environ["PAULUS_MICROSOFT_CLIENT_ID"] = "0000-1111"
        info = api.email_oauth_info()
        checar(info["google"]["configurado"] and info["microsoft"]["configurado"], "com IDs no programa: os dois logins ficam disponiveis")
        checar("GOCSPX" not in json.dumps(info) and "0000-1111" not in json.dumps(info), "a tela nao recebe os IDs, so se cada login existe")
        checar(api._credenciais_oauth("google")["client_secret"] == "GOCSPX-segredo", "o login usa o secret do programa")
        checar(not hasattr(api, "email_oauth_config"), "nao ha rota para gravar IDs: nada a configurar em cada maquina")
        checar(not api.email_detectar(api.EnderecoEmail(email="x@outlook.com"))["bloqueado"],
               "com ID, a conta Outlook deixa de ser bloqueada")

        # Login inteiro pela rota, com navegador, token e IMAP/SMTP falsos.
        correio_oauth.PROVEDORES["microsoft"]["token"] = token.url
        webbrowser.open = lambda url: threading.Timer(0.2, lambda: _navegador(url)).start() or True
        token.email = "escritorio@outlook.com"
        antes = (correio.imaplib.IMAP4_SSL, correio.smtplib.SMTP)
        correio.imaplib.IMAP4_SSL, correio.smtplib.SMTP = _IMAPFalso, _SMTPFalso
        try:
            d = api.email_oauth_entrar(api.PedidoEntrada(provedor="microsoft"))
            checar(d["fase"] == "aguardando", "entrar devolve 'aguardando'")
            api.estado.entrada_oauth.esperar(8)
            a = api.email_oauth_andamento()
        finally:
            correio.imaplib.IMAP4_SSL, correio.smtplib.SMTP = antes
        checar(a["fase"] == "pronto", f"andamento chega em 'pronto' ({a['fase']} {a.get('mensagem')})")
        contas = (a.get("contas") or {}).get("contas") or []
        ligada = next((c for c in contas if c["email"] == "escritorio@outlook.com"), None)
        checar(ligada is not None and ligada["autenticacao"] == "microsoft" and ligada["tem_senha"]
               and ligada["situacao"] == "conectada", "a conta aparece ligada, pelo login Microsoft")
        checar(a["resultado"]["prova"]["ok"], "e a conexao foi provada (IMAP e SMTP com XOAUTH2)")
        try:
            api.email_senha_conta(api.SenhaConta(id=ligada["id"], senha=""))
            checar(False, "reconectar por senha vazia recusa")
        except api.HTTPException as exc:
            checar(exc.status_code == 400 and "login" in exc.detail, "conta de login nao pede senha")

        webbrowser.open = lambda url: True
        api.email_oauth_entrar(api.PedidoEntrada(provedor="google"))
        api.email_oauth_cancelar()
        api.estado.entrada_oauth.esperar(3)
        checar(api.email_oauth_andamento()["fase"] == "cancelado", "cancelar pela rota")
    finally:
        correio_oauth.PROVEDORES["microsoft"]["token"] = endpoint_real
        webbrowser.open = abrir_real
        api.estado.contas, api.estado.prefs, api.estado.entrada_oauth = guardados
        oauth_app.ARQUIVO = arquivo_real
        for nome in ("PAULUS_GOOGLE_CLIENT_ID", "PAULUS_GOOGLE_CLIENT_SECRET", "PAULUS_MICROSOFT_CLIENT_ID"):
            os.environ.pop(nome, None)


def main() -> int:
    print("PAULUS - login do e-mail (OAuth)")
    print("=" * 55)
    token = TokenFalso()
    try:
        test_pkce()
        test_url_autorizacao()
        test_loopback()
        test_troca_e_renovacao(token)
        test_xoauth2()
        test_imap_smtp_com_xoauth2()
        test_detectar()
        test_entrada_completa(token)
        with tempfile.TemporaryDirectory() as bruto:
            test_contas(Path(bruto), token)
        with tempfile.TemporaryDirectory() as bruto:
            test_api(Path(bruto), token)
    finally:
        token.fechar()

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
