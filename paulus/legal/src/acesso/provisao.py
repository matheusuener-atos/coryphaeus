"""
A conversa do PAULUS com o Worker de paulus.ia.br (R7): pedir o endereco,
saber quando o titular confirmou, e depois manter a lista de e-mails, a
porta, e remover.

Nada de documento passa por aqui: sai o e-mail do titular, o nome do
escritorio, a porta e um identificador aleatorio da instalacao; volta o
endereco, o token do tunel (uma vez so) e o segredo da instalacao - que so
existe para este PAULUS falar de novo com o Worker.
"""

from __future__ import annotations

import os

BASE = os.environ.get("PAULUS_TUNEL_URL", "https://paulus.ia.br").rstrip("/")


class ErroProvisao(RuntimeError):
    pass


class Provisao:
    def __init__(self, base: str = BASE, sessao=None, timeout: float = 20.0) -> None:
        import requests

        self.base = base.rstrip("/")
        self.http = sessao or requests.Session()
        self.timeout = timeout

    def _pedir(self, metodo: str, caminho: str, corpo=None, segredo: str = "") -> dict:
        cab = {"Content-Type": "application/json", "User-Agent": "PAULUS-acesso-de-fora"}
        if segredo:
            cab["Authorization"] = "Bearer " + segredo
        try:
            r = self.http.request(metodo, self.base + caminho, json=corpo, headers=cab, timeout=self.timeout)
        except Exception as exc:  # noqa: BLE001 - sem internet, a frase diz isso
            raise ErroProvisao("não consegui falar com paulus.ia.br: confira a internet") from exc
        try:
            dados = r.json()
        except ValueError:
            dados = {}
        if r.status_code == 404:
            raise ErroProvisao("o acesso de fora ainda não está disponível em paulus.ia.br")
        if r.status_code >= 400:
            raise ErroProvisao(dados.get("erro") or f"paulus.ia.br respondeu {r.status_code}")
        return dados

    def iniciar(self, instalacao_id: str, email_titular: str, nome_escritorio: str, porta: int) -> dict:
        return self._pedir("POST", "/api/tunel/iniciar", {
            "instalacao_id": instalacao_id, "email_titular": email_titular,
            "nome_escritorio": nome_escritorio, "porta": porta})

    def estado(self, codigo_dispositivo: str) -> dict:
        return self._pedir("POST", "/api/tunel/estado", {"codigo_dispositivo": codigo_dispositivo})

    def emails(self, segredo: str, emails: list[str]) -> dict:
        return self._pedir("POST", "/api/tunel/emails", {"emails": emails}, segredo)

    def porta(self, segredo: str, porta: int) -> dict:
        return self._pedir("POST", "/api/tunel/porta", {"porta": porta}, segredo)

    def situacao(self, segredo: str) -> dict:
        return self._pedir("GET", "/api/tunel/situacao", None, segredo)

    def remover(self, segredo: str) -> dict:
        return self._pedir("POST", "/api/tunel/remover", {}, segredo)
