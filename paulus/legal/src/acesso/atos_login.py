"""
Entrar com Atos, de fora (09/10/2026): a equipe que entra pelo endereco do
escritorio (<escritorio>.paulus.ia.br) entra com a Conta Atos - e so com ela.
A Atos prova o e-mail (com a senha dela ou com o Google, la em atos.dev.br);
o codigo do celular (TOTP) continua pedido depois, conforme o nivel de
seguranca da conta, como era com o Google e com a senha local.

O caminho:

  1. o PAULUS monta o endereco de https://atos.dev.br/entrar com PKCE (o
     verificador fica aqui, em memoria, 10 minutos), um `state` e um `nonce`
     (OpenID Connect), e poe um cookie que amarra a volta a este navegador;
  2. a Atos volta direto ao escritorio, em
     https://<escritorio>.paulus.ia.br/api/acesso/atos/retorno - o cliente
     "pavlvs-escritorio" da Atos aceita esse endereco em todo escritorio, entao
     nada passa pelo Worker de paulus.ia.br;
  3. o PAULUS troca o codigo pelo id_token direto em atos.dev.br (o cliente e
     publico: sem segredo, o PKCE prova que foi ele que pediu) e le o e-mail.

Escopos: `openid email profile`. O Google de trabalho de cada pessoa (o
e-mail, a Agenda e o Drive dela) continua com o Google, em acesso/google_login.py.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

EMISSOR = "https://atos.dev.br"
AUTORIZAR = EMISSOR + "/entrar"
TOKEN = EMISSOR + "/oauth/token"
CLIENTE = "pavlvs-escritorio"
CAMINHO_VOLTA = "/api/acesso/atos/retorno"
ESCOPOS = "openid email profile"
VALIDADE_S = 600
COOKIE = "paulus_atos"


class ErroAtos(RuntimeError):
    """O login pela Atos nao fechou; a frase vai para a tela."""


def _b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode("ascii")


def _payload_do_jwt(jwt: str) -> dict:
    try:
        meio = jwt.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(meio + "=" * (-len(meio) % 4)))
    except (IndexError, ValueError):
        raise ErroAtos("a Atos respondeu algo que não entendi") from None


def trocar_na_atos(code: str, verificador: str, volta: str) -> dict:
    """POST no endpoint de token da Atos; devolve o JSON (com id_token)."""
    corpo = urllib.parse.urlencode({
        "grant_type": "authorization_code", "code": code, "client_id": CLIENTE,
        "redirect_uri": volta, "code_verifier": verificador,
    }).encode("ascii")
    pedido = urllib.request.Request(TOKEN, data=corpo, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(pedido, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode("utf-8"))
        except (ValueError, OSError):
            return {"error": f"HTTP {exc.code}"}
    except OSError as exc:
        raise ErroAtos("não consegui falar com a Atos agora; tente de novo") from exc


class LoginAtos:
    def __init__(self, servico, *, trocar=trocar_na_atos, relogio=time.time) -> None:
        self.servico = servico
        self.trocar = trocar
        self.relogio = relogio
        self._trava = threading.Lock()
        self._pedidos: dict[str, dict] = {}

    def _volta(self) -> str:
        host = str(self.servico.preferencias().get("hostname", "") or "")
        if not host.endswith(".paulus.ia.br"):
            raise ErroAtos("o acesso externo deste escritório não está conectado")
        return "https://" + host + CAMINHO_VOLTA

    def disponivel(self) -> bool:
        return str(self.servico.preferencias().get("hostname", "") or "").endswith(".paulus.ia.br")

    def iniciar(self, finalidade: str, convite: str = "", dica: str = "") -> tuple[str, str]:
        """(endereco da Atos, valor do cookie que amarra o retorno a este navegador)."""
        if finalidade not in ("entrar", "convite"):
            raise ErroAtos("finalidade desconhecida")
        volta = self._volta()
        state = secrets.token_urlsafe(24)
        verificador = secrets.token_urlsafe(48)
        nonce = secrets.token_urlsafe(24)
        amarra = secrets.token_urlsafe(24)
        with self._trava:
            agora = self.relogio()
            for k in [k for k, v in self._pedidos.items() if v["expira"] < agora]:
                self._pedidos.pop(k, None)
            self._pedidos[state] = {"verificador": verificador, "finalidade": finalidade, "convite": convite, "volta": volta,
                                    "nonce": nonce, "amarra": hashlib.sha256(amarra.encode()).hexdigest(),
                                    "expira": agora + VALIDADE_S}
        parametros = {
            "client_id": CLIENTE, "redirect_uri": volta, "response_type": "code", "scope": ESCOPOS,
            "state": state, "nonce": nonce, "code_challenge": _b64(hashlib.sha256(verificador.encode()).digest()),
            "code_challenge_method": "S256",
        }
        dica = str(dica or "").strip()
        if dica and "@" in dica and len(dica) <= 254:
            parametros["login_hint"] = dica
        return AUTORIZAR + "?" + urllib.parse.urlencode(parametros), amarra

    def retorno(self, code: str, state: str, amarra: str, iss: str = "") -> dict:
        """Confere, troca o codigo e devolve {email, nome, finalidade, convite}."""
        with self._trava:
            pedido = self._pedidos.pop(str(state or ""), None)
        if not pedido or pedido["expira"] < self.relogio():
            raise ErroAtos("o login pela Atos demorou demais ou já foi usado; comece de novo")
        if not amarra or hashlib.sha256(amarra.encode()).hexdigest() != pedido["amarra"]:
            raise ErroAtos("este retorno da Atos não é deste navegador; comece de novo")
        if iss and iss != EMISSOR:
            raise ErroAtos("a resposta não veio da Atos")
        dados = self.trocar(code, pedido["verificador"], pedido["volta"])
        if "id_token" not in dados:
            raise ErroAtos("a Atos recusou o login: " + str(dados.get("error_description") or dados.get("error") or "sem motivo"))
        info = _payload_do_jwt(dados["id_token"])
        # O id_token veio direto da Atos, por TLS, em resposta a um pedido
        # nosso: a assinatura nao precisa ser conferida de novo (OpenID
        # Connect, 3.1.3.7, item 6). O resto sim.
        if info.get("aud") != CLIENTE or info.get("iss") != EMISSOR:
            raise ErroAtos("a resposta da Atos não é para este escritório")
        if info.get("exp", 0) < self.relogio():
            raise ErroAtos("a resposta da Atos venceu; comece de novo")
        if info.get("nonce") != pedido["nonce"]:
            raise ErroAtos("a resposta da Atos não é deste pedido; comece de novo")
        if not info.get("email") or info.get("email_verified") is not True:
            raise ErroAtos("a Conta Atos não tem e-mail confirmado")
        return {"email": str(info["email"]).lower(), "nome": str(info.get("name") or ""),
                "finalidade": pedido["finalidade"], "convite": pedido["convite"]}
