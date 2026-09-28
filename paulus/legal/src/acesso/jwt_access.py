"""
A conferencia do JWT do Cloudflare Access, aqui dentro (R6).

O Access ja barra, na Cloudflare, quem nao confirmou um e-mail autorizado.
Conferir de novo aqui e defesa em profundidade: se um dia a aplicacao do
Access for apagada ou mal configurada, o tunel continua levando o pedido ate
este computador - e e este computador que diz nao.

Cada pedido de fora traz `Cf-Access-Jwt-Assertion`. Vale se:

  - a assinatura e RS256, de uma das chaves publicas do time
    (https://<time>.cloudflareaccess.com/cdn-cgi/access/certs), escolhida
    pelo `kid` - as chaves giram a cada seis semanas;
  - `aud` inclui a aplicacao deste escritorio (recebida na conexao);
  - `iss` e o time; `exp` nao passou.

As chaves ficam guardadas por uma hora. Sem chave alcancavel - internet fora,
time errado -, nega: o acesso de fora para, e a janela local nao e afetada.
A criptografia e da `cryptography`, que o programa ja usa para o certificado.
"""

from __future__ import annotations

import base64
import json
import threading
import time

CACHE_S = 3600
FOLGA_S = 60


def _b64url(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _inteiro(texto: str) -> int:
    return int.from_bytes(_b64url(texto), "big")


def buscar_certs(time_dominio: str) -> dict:
    import requests

    r = requests.get(f"https://{time_dominio}/cdn-cgi/access/certs", timeout=8)
    r.raise_for_status()
    return r.json()


class ConferidorAccess:
    """Chamavel: `conferidor(token)` devolve as claims, ou None."""

    def __init__(self, time_dominio: str, aud: str, *, buscar=None, relogio=time.time) -> None:
        self.time_dominio = str(time_dominio or "").strip().lower()
        self.aud = str(aud or "").strip()
        self._buscar = buscar or buscar_certs
        self.relogio = relogio
        self._trava = threading.Lock()
        self._chaves: dict[str, object] = {}
        self._quando = 0.0

    def _chave(self, kid: str):
        with self._trava:
            velho = self.relogio() - self._quando > CACHE_S
            if velho or kid not in self._chaves:
                # Chave nova (girou) ou cache vencido: busca de novo. Falhou,
                # fica sem chave nenhuma - na duvida, nega.
                try:
                    self._chaves = self._carregar(self._buscar(self.time_dominio))
                    self._quando = self.relogio()
                except Exception:  # noqa: BLE001 - sem chave, ninguem passa
                    self._chaves, self._quando = {}, 0.0
            return self._chaves.get(kid)

    @staticmethod
    def _carregar(certs: dict) -> dict:
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers

        chaves = {}
        for k in (certs or {}).get("keys", []):
            if k.get("kty") != "RSA" or not k.get("kid"):
                continue
            chaves[k["kid"]] = RSAPublicNumbers(_inteiro(k["e"]), _inteiro(k["n"])).public_key()
        return chaves

    def __call__(self, token: str) -> dict | None:
        if not token or not self.time_dominio or not self.aud:
            return None
        try:
            cab64, corpo64, assinatura64 = str(token).split(".")
            cab = json.loads(_b64url(cab64))
            claims = json.loads(_b64url(corpo64))
            if cab.get("alg") != "RS256" or not cab.get("kid"):
                return None
            chave = self._chave(cab["kid"])
            if chave is None:
                return None
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding

            chave.verify(_b64url(assinatura64), f"{cab64}.{corpo64}".encode("ascii"),
                         padding.PKCS1v15(), hashes.SHA256())
        except Exception:  # noqa: BLE001 - token torto, assinatura errada: nao passa
            return None
        agora = self.relogio()
        auds = claims.get("aud")
        auds = auds if isinstance(auds, list) else [auds]
        if self.aud not in auds:
            return None
        if claims.get("iss") != f"https://{self.time_dominio}":
            return None
        if not claims.get("exp") or float(claims["exp"]) < agora:
            return None
        if claims.get("nbf") and float(claims["nbf"]) > agora + FOLGA_S:
            return None
        return claims
