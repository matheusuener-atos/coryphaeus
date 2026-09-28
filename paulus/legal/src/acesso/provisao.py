"""
A conversa do PAULUS com o Worker de paulus.ia.br (R5/R7): o nome esta livre?,
pedir o endereco, saber quando o titular confirmou, e depois conferir o
Turnstile de cada login, trocar a porta, perguntar a situacao e remover.

Nada de documento passa por aqui: sai o nome do escritorio, o nome escolhido
para o endereco, a porta, um identificador aleatorio da instalacao e - no
login - o token do Turnstile e o endereco de internet de quem tenta entrar;
volta o endereco, o token do tunel (uma vez so), a sitekey do Turnstile e o
segredo da instalacao, que so existe para este PAULUS falar de novo com o
Worker.
"""

from __future__ import annotations

import os

BASE = os.environ.get("PAULUS_TUNEL_URL", "https://paulus.ia.br").rstrip("/")


class ErroProvisao(RuntimeError):
    """O Worker nao respondeu ou recusou; a mensagem vai para a tela."""


class ErroRemovido(ErroProvisao):
    """O endereco deste PAULUS nao existe mais (removido, ou liberado por falta de uso)."""

    def __init__(self, motivo: str) -> None:
        super().__init__("o endereço foi liberado" + (f" ({motivo})" if motivo else ""))
        self.motivo = motivo


class Provisao:
    def __init__(self, base: str = BASE, sessao=None, timeout: float = 20.0) -> None:
        import requests

        self.base = base.rstrip("/")
        self.http = sessao or requests.Session()
        self.timeout = timeout

    def _pedir(self, metodo: str, caminho: str, corpo=None, segredo: str = "", params=None) -> dict:
        cab = {"Content-Type": "application/json", "User-Agent": "PAULUS-acesso-de-fora"}
        if segredo:
            cab["Authorization"] = "Bearer " + segredo
        try:
            r = self.http.request(metodo, self.base + caminho, json=corpo, params=params, headers=cab,
                                  timeout=self.timeout)
        except Exception as exc:  # noqa: BLE001 - sem internet, a frase diz isso
            raise ErroProvisao("não consegui falar com paulus.ia.br: confira a internet") from exc
        try:
            dados = r.json()
        except ValueError:
            dados = {}
        if r.status_code == 410 and dados.get("removido"):
            raise ErroRemovido(str(dados.get("motivo") or ""))
        if r.status_code == 404:
            raise ErroProvisao("o acesso de fora ainda não está disponível em paulus.ia.br")
        if r.status_code >= 400:
            erro = ErroProvisao(dados.get("erro") or f"paulus.ia.br respondeu {r.status_code}")
            erro.sugestao = dados.get("sugestao", "")
            raise erro
        return dados

    def disponivel(self, nome: str, instalacao_id: str = "") -> dict:
        return self._pedir("GET", "/api/tunel/disponivel", params={"nome": nome, "instalacao": instalacao_id})

    def iniciar(self, instalacao_id: str, nome_escritorio: str, slug: str, porta: int) -> dict:
        return self._pedir("POST", "/api/tunel/iniciar", {
            "instalacao_id": instalacao_id, "nome_escritorio": nome_escritorio, "slug": slug, "porta": porta})

    def estado(self, codigo_dispositivo: str) -> dict:
        return self._pedir("POST", "/api/tunel/estado", {"codigo_dispositivo": codigo_dispositivo})

    def turnstile(self, segredo: str, token: str, ip: str = "") -> bool:
        """So o token do Turnstile e o endereco de quem tenta entrar vao. Volta ok ou nao."""
        return bool(self._pedir("POST", "/api/tunel/turnstile", {"token": token, "ip": ip}, segredo).get("ok"))

    def porta(self, segredo: str, porta: int) -> dict:
        return self._pedir("POST", "/api/tunel/porta", {"porta": porta}, segredo)

    def situacao(self, segredo: str) -> dict:
        return self._pedir("GET", "/api/tunel/situacao", None, segredo)

    def remover(self, segredo: str) -> dict:
        return self._pedir("POST", "/api/tunel/remover", {}, segredo)
