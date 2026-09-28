"""
Entrar com o Google (docs/PLANO-EQUIPE.md, E3a): no convite e na tela de
entrar, o Google prova o e-mail no lugar da senha. O codigo do celular
(TOTP) continua pedido depois - Google + codigo, sempre.

O caminho, por que e assim:

  1. o PAULUS monta o endereco do Google com PKCE (o verificador fica aqui,
     em memoria, 10 minutos) e um `state` "<slug>~<aleatorio>";
  2. o Google so aceita enderecos de retorno cadastrados um a um - e cada
     escritorio tem o seu <slug>.paulus.ia.br. O retorno e entao o de
     paulus.ia.br/oauth/google, e o Worker so repassa ao escritorio do
     `state` (worker/tunel.js). O que passa por ele e um codigo de uso
     unico, que nao vale nada sem o verificador e o segredo, que ficam aqui;
  3. o PAULUS troca o codigo pelo id_token direto no Google e le o e-mail.
     Um cookie posto no passo 1 amarra o retorno ao mesmo navegador: um link
     de retorno mandado a outra pessoa nao entra por ela.

Escopos: so `openid email profile`. Nada de e-mail, agenda ou arquivos aqui -
isso e a E3b, com a autorizacao de cada pessoa.

O cliente OAuth e um "Aplicativo da Web" do Google Cloud do Atos, com o
endereco de retorno https://paulus.ia.br/oauth/google (oauth_app.json:
google_web_client_id, google_web_client_secret).
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
import urllib.parse
import urllib.request

import oauth_app

AUTORIZAR = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
RETORNO = "https://paulus.ia.br/oauth/google"
ESCOPOS = "openid email profile"
VALIDADE_S = 600
COOKIE = "paulus_google"


class ErroGoogle(RuntimeError):
    """O login pelo Google nao fechou; a frase vai para a tela."""


def _b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode("ascii")


def _payload_do_jwt(jwt: str) -> dict:
    try:
        meio = jwt.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(meio + "=" * (-len(meio) % 4)))
    except (IndexError, ValueError):
        raise ErroGoogle("o Google respondeu algo que não entendi") from None


def trocar_no_google(code: str, verificador: str, credenciais: dict) -> dict:
    """POST no endpoint de token do Google; devolve o JSON (com id_token)."""
    corpo = urllib.parse.urlencode({
        "code": code, "client_id": credenciais["client_id"], "client_secret": credenciais["client_secret"],
        "redirect_uri": RETORNO, "grant_type": "authorization_code", "code_verifier": verificador,
    }).encode("ascii")
    pedido = urllib.request.Request(TOKEN, data=corpo, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(pedido, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except OSError as exc:
        raise ErroGoogle("não consegui falar com o Google agora; tente de novo") from exc


class LoginGoogle:
    def __init__(self, servico, *, trocar=trocar_no_google, relogio=time.time) -> None:
        self.servico = servico
        self.trocar = trocar
        self.relogio = relogio
        self._trava = threading.Lock()
        self._pedidos: dict[str, dict] = {}

    @staticmethod
    def credenciais() -> dict:
        return oauth_app.credenciais("google_web")

    def disponivel(self) -> bool:
        c = self.credenciais()
        return bool(c.get("client_id") and c.get("client_secret") and self.servico.preferencias().get("hostname"))

    def iniciar(self, finalidade: str, convite: str = "") -> tuple[str, str]:
        """(endereco do Google, valor do cookie que amarra o retorno a este navegador)."""
        if finalidade not in ("entrar", "convite"):
            raise ErroGoogle("finalidade desconhecida")
        c = self.credenciais()
        host = self.servico.preferencias().get("hostname", "")
        if not (c.get("client_id") and c.get("client_secret")):
            raise ErroGoogle("o login com o Google ainda não foi configurado neste PAULUS")
        if not host.endswith(".paulus.ia.br"):
            raise ErroGoogle("o acesso de fora deste escritório não está conectado")
        slug = host[: -len(".paulus.ia.br")]
        aleatorio = secrets.token_urlsafe(24)
        verificador = secrets.token_urlsafe(48)
        nonce = secrets.token_urlsafe(24)
        with self._trava:
            agora = self.relogio()
            for k in [k for k, v in self._pedidos.items() if v["expira"] < agora]:
                self._pedidos.pop(k, None)
            self._pedidos[aleatorio] = {"verificador": verificador, "finalidade": finalidade, "convite": convite,
                                        "nonce": hashlib.sha256(nonce.encode()).hexdigest(), "expira": agora + VALIDADE_S}
        parametros = {
            "client_id": c["client_id"], "redirect_uri": RETORNO, "response_type": "code", "scope": ESCOPOS,
            "state": f"{slug}~{aleatorio}", "code_challenge": _b64(hashlib.sha256(verificador.encode()).digest()),
            "code_challenge_method": "S256", "prompt": "select_account",
        }
        return AUTORIZAR + "?" + urllib.parse.urlencode(parametros), nonce

    def retorno(self, code: str, state: str, nonce: str) -> dict:
        """Confere, troca o codigo e devolve {email, nome, finalidade, convite}."""
        aleatorio = str(state or "").split("~", 1)[-1]
        with self._trava:
            pedido = self._pedidos.pop(aleatorio, None)
        if not pedido or pedido["expira"] < self.relogio():
            raise ErroGoogle("o login pelo Google demorou demais ou já foi usado; comece de novo")
        if not nonce or hashlib.sha256(nonce.encode()).hexdigest() != pedido["nonce"]:
            raise ErroGoogle("este retorno do Google não é deste navegador; comece de novo")
        c = self.credenciais()
        dados = self.trocar(code, pedido["verificador"], c)
        if "id_token" not in dados:
            raise ErroGoogle("o Google recusou o login: " + str(dados.get("error_description") or dados.get("error") or "sem motivo"))
        info = _payload_do_jwt(dados["id_token"])
        # O id_token veio direto do Google, por TLS: a assinatura nao precisa
        # ser conferida de novo (OpenID Connect, 3.1.3.7, item 6). O resto sim.
        if info.get("aud") != c["client_id"] or info.get("iss") not in ("https://accounts.google.com", "accounts.google.com"):
            raise ErroGoogle("a resposta do Google não é para este aplicativo")
        if info.get("exp", 0) < self.relogio():
            raise ErroGoogle("a resposta do Google venceu; comece de novo")
        if not info.get("email") or not info.get("email_verified"):
            raise ErroGoogle("a conta do Google não tem e-mail confirmado")
        return {"email": str(info["email"]).lower(), "nome": str(info.get("name") or ""),
                "finalidade": pedido["finalidade"], "convite": pedido["convite"]}
