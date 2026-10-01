"""
A conversa com o Sistema Nacional da NFS-e: HTTPS com o certificado A1 no TLS.

Três cuidados moram aqui e em nenhum outro lugar:

- **Produção trancada.** O cliente recusa o ambiente de produção enquanto a
  liberação da N8 não tiver sido dada (a chave vem de fora, e o teste confere
  que sem ela nada sai). Produção restrita é o padrão.
- **A chave privada não fica em disco.** O `ssl` do Python só carrega
  certificado de arquivo; o .pfx é aberto na memória e a chave vai para um
  arquivo temporário CIFRADO com uma senha aleatória que nunca toca o disco,
  carregada no contexto TLS e apagada na hora.
- **Nada do conteúdo vai para o log.** Nem a DPS, nem a NFS-e, nem a senha.
  O que se registra é o método, o caminho e o código da resposta.

Os nomes dos campos JSON (`CAMPOS`) não estão em documento público: o Swagger
oficial só abre com certificado. `conferir_contrato()` baixa o Swagger com o
certificado do escritório e confere cada nome; se algum não estiver lá, o
envio fica travado até alguém olhar (docs/PROGRESSO-NFSE.md, N0, linha 14).
"""

from __future__ import annotations

import base64
import gzip
import json
import logging
import os
import re
import secrets
import ssl
import tempfile
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("paulus.nfse")

# docs/PROGRESSO-NFSE.md, N0 › Endereços (página "APIs - Prod. Restrita e
# Produção", atualizada em 20/08/2026).
URLS = {
    "producao_restrita": {
        "sefin": "https://sefin.producaorestrita.nfse.gov.br/API/SefinNacional",
        "parametros": "https://adn.producaorestrita.nfse.gov.br/parametrizacao",
        "contribuintes": "https://adn.producaorestrita.nfse.gov.br/contribuintes",
    },
    "producao": {
        "sefin": "https://sefin.nfse.gov.br/SefinNacional",
        "parametros": "https://adn.nfse.gov.br/parametrizacao",
        "contribuintes": "https://adn.nfse.gov.br/contribuintes",
    },
}

# Os nomes que o cliente usa no JSON. Uma tabela só, para a conferência no
# Swagger achar todos (e para trocar num lugar só, se o Swagger disser outro).
CAMPOS = {
    "dps": "dpsXmlGZipB64",
    "nfse": "nfseXmlGZipB64",
    "chave": "chaveAcesso",
    "id_dps": "idDps",
    "evento_pedido": "pedidoRegistroEventoXmlGZipB64",
    "evento": "eventoXmlGZipB64",
    "erros": "erros",
    "alertas": "alertas",
}

TEMPO_CONEXAO = 10
TEMPO_RESPOSTA = 60


class ProducaoBloqueada(RuntimeError):
    """Tentativa de falar com produção sem a liberação do titular (N8)."""


class SemResposta(RuntimeError):
    """
    O pedido pode ter chegado e não houve resposta (tempo esgotado, queda).

    Quem recebe isto NUNCA reenvia: consulta pela identidade da DPS (ou da
    nota, no evento) e só então decide.
    """


class NaoChegou(RuntimeError):
    """A conexão nem abriu: o pedido certamente não chegou ao servidor."""


class CertificadoInvalido(RuntimeError):
    """O .pfx não abre, não tem chave, ou não serve para o TLS."""


@dataclass
class Resposta:
    status: int
    corpo: dict | None
    texto: str = ""

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


def gzip_b64(xml: bytes) -> str:
    return base64.b64encode(gzip.compress(xml)).decode("ascii")


def de_gzip_b64(texto: str) -> bytes:
    return gzip.decompress(base64.b64decode(texto))


def _contexto_tls(pfx: bytes, senha: str) -> ssl.SSLContext:
    """Contexto TLS com o certificado do cliente, sem a chave em claro no disco."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import pkcs12

    try:
        chave, cert, extras = pkcs12.load_key_and_certificates(pfx, (senha or "").encode())
    except ValueError as exc:
        raise CertificadoInvalido("senha do certificado incorreta, ou arquivo inválido") from exc
    if chave is None or cert is None:
        raise CertificadoInvalido("o arquivo do certificado não traz a chave privada")

    contexto = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    try:
        import certifi

        contexto.load_verify_locations(certifi.where())
    except ImportError:  # pragma: no cover - certifi vem com requests
        pass
    contexto.minimum_version = ssl.TLSVersion.TLSv1_2

    senha_efemera = secrets.token_bytes(32)
    pem_chave = chave.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(senha_efemera),
    )
    pem_cert = cert.public_bytes(serialization.Encoding.PEM) + b"".join(
        c.public_bytes(serialization.Encoding.PEM) for c in (extras or []))
    pasta = tempfile.mkdtemp(prefix="paulus-tls-")
    arq_chave, arq_cert = Path(pasta) / "k.pem", Path(pasta) / "c.pem"
    try:
        arq_chave.write_bytes(pem_chave)
        arq_cert.write_bytes(pem_cert)
        contexto.load_cert_chain(str(arq_cert), str(arq_chave), password=senha_efemera)
    finally:
        for arq in (arq_chave, arq_cert):
            try:
                arq.unlink()
            except OSError:
                pass
        try:
            os.rmdir(pasta)
        except OSError:
            pass
    return contexto


class Cliente:
    """
    Um cliente por ambiente e certificado. `transporte` existe para o teste:
    o servidor simulado da N3 entra no lugar da rede, com as mesmas regras de
    produção trancada e de "sem resposta, consulta".
    """

    def __init__(self, ambiente: str, pfx: bytes | None = None, senha: str = "", *,
                 producao_liberada: bool = False, transporte=None, urls: dict | None = None) -> None:
        if ambiente not in URLS:
            raise ValueError("ambiente desconhecido")
        if ambiente == "producao" and not producao_liberada:
            raise ProducaoBloqueada(
                "a produção ainda não foi liberada pelo titular (Configurações › Nota fiscal › Produção)")
        self.ambiente = ambiente
        self.urls = dict(urls or URLS[ambiente])
        self._transporte = transporte
        self._sessao = None
        if transporte is None:
            if not pfx:
                raise CertificadoInvalido("nenhum certificado A1 configurado para a nota fiscal")
            self._sessao = self._abrir_sessao(_contexto_tls(pfx, senha))

    @staticmethod
    def _abrir_sessao(contexto: ssl.SSLContext):
        import requests
        from requests.adapters import HTTPAdapter

        class _Adaptador(HTTPAdapter):
            def init_poolmanager(self, *args, **kwargs):
                kwargs["ssl_context"] = contexto
                return super().init_poolmanager(*args, **kwargs)

            def proxy_manager_for(self, *args, **kwargs):
                kwargs["ssl_context"] = contexto
                return super().proxy_manager_for(*args, **kwargs)

        sessao = requests.Session()
        sessao.mount("https://", _Adaptador(max_retries=0))
        sessao.headers.update({"Accept": "application/json", "User-Agent": "PAULUS-Legal"})
        return sessao

    # ------------------------------------------------------------ transporte

    def _pedir(self, metodo: str, servico: str, caminho: str, corpo: dict | None = None) -> Resposta:
        url = self.urls[servico].rstrip("/") + caminho
        log.info("nfse %s %s %s", self.ambiente, metodo, re.sub(r"\d{20,}", "<id>", caminho))
        if self._transporte is not None:
            return self._transporte(metodo, url, corpo)

        import requests

        try:
            r = self._sessao.request(metodo, url, json=corpo, timeout=(TEMPO_CONEXAO, TEMPO_RESPOSTA))
        except requests.exceptions.ConnectTimeout as exc:
            raise NaoChegou("o Sistema Nacional não atendeu (tempo de conexão esgotado)") from exc
        except requests.exceptions.SSLError as exc:
            raise NaoChegou("o servidor recusou o certificado ou a conexão segura falhou") from exc
        except requests.exceptions.ConnectionError as exc:
            # Pode ter caído antes ou depois de chegar: na dúvida, é "sem resposta".
            raise SemResposta("a conexão caiu sem resposta do Sistema Nacional") from exc
        except requests.exceptions.Timeout as exc:
            raise SemResposta("o Sistema Nacional não respondeu a tempo") from exc
        log.info("nfse %s %s -> %s", self.ambiente, metodo, r.status_code)
        try:
            dados = r.json() if r.content else None
        except ValueError:
            dados = None
        return Resposta(r.status_code, dados if isinstance(dados, dict) else None,
                        "" if isinstance(dados, dict) else (r.text or "")[:2000])

    # --------------------------------------------------------------- serviços

    def emitir(self, dps_assinada: bytes) -> Resposta:
        return self._pedir("POST", "sefin", "/nfse", {CAMPOS["dps"]: gzip_b64(dps_assinada)})

    def consultar_nfse(self, chave: str) -> Resposta:
        return self._pedir("GET", "sefin", f"/nfse/{chave}")

    def consultar_dps(self, id_dps: str) -> Resposta:
        return self._pedir("GET", "sefin", f"/dps/{id_dps}")

    def dps_existe(self, id_dps: str) -> Resposta:
        return self._pedir("HEAD", "sefin", f"/dps/{id_dps}")

    def registrar_evento(self, chave: str, pedido_assinado: bytes) -> Resposta:
        return self._pedir("POST", "sefin", f"/nfse/{chave}/eventos",
                           {CAMPOS["evento_pedido"]: gzip_b64(pedido_assinado)})

    def consultar_eventos(self, chave: str, tipo: str = "") -> Resposta:
        return self._pedir("GET", "sefin", f"/nfse/{chave}/eventos" + (f"/{tipo}" if tipo else ""))

    def parametros_convenio(self, cmun: str) -> Resposta:
        return self._pedir("GET", "parametros", f"/parametros_municipais/{cmun}/convenio")

    def parametros_servico(self, cmun: str, ctribnac: str) -> Resposta:
        return self._pedir("GET", "parametros", f"/parametros_municipais/{cmun}/{ctribnac}")

    def parametros_contribuinte(self, cmun: str, documento: str) -> Resposta:
        return self._pedir("GET", "parametros", f"/parametros_municipais/{cmun}/{documento}")

    # ----------------------------------------------------- conferir o contrato

    def conferir_contrato(self) -> dict:
        """
        Baixa o Swagger oficial (só abre com certificado) e confere se cada
        nome de `CAMPOS` aparece nele. Devolve {ok, faltam, fonte}.
        """
        achados: list[str] = []
        fontes: list[str] = []
        for servico in ("sefin",):
            for caminho in ("/docs/index", "/swagger/v1/swagger.json", "/docs/v1/swagger.json"):
                try:
                    r = self._pedir("GET", servico, caminho)
                except (SemResposta, NaoChegou):
                    continue
                texto = r.texto or (json.dumps(r.corpo) if r.corpo else "")
                if not r.ok or not texto:
                    continue
                fontes.append(self.urls[servico] + caminho)
                achados.append(texto)
                for extra in re.findall(r"""["']([^"']+\.json)["']""", texto)[:3]:
                    alvo = extra if extra.startswith("/") else "/docs/" + extra
                    try:
                        r2 = self._pedir("GET", servico, alvo)
                    except (SemResposta, NaoChegou):
                        continue
                    if r2.ok:
                        achados.append(r2.texto or json.dumps(r2.corpo or {}))
                        fontes.append(self.urls[servico] + alvo)
        todo = "\n".join(achados)
        if not todo:
            return {"ok": False, "faltam": list(CAMPOS.values()), "fonte": [],
                    "erro": "não consegui baixar o Swagger oficial com este certificado"}
        faltam = [c for c in CAMPOS.values() if c not in todo]
        return {"ok": not faltam, "faltam": faltam, "fonte": fontes}
