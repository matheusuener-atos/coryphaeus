"""
O que os testes do emissor de NFS-e (test_n1 … test_n9) usam em comum.

Importe DEPOIS de pôr PAULUS_DADOS no ambiente e ANTES de `import api`: o
módulo não mexe no ambiente; só traz o `checar`, a sessão de fora (titular e
colaborador, como no test_r3) e um certificado A1 de teste com CNPJ.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        falhas.append(nome)


class Fora:
    """Um navegador de fora, com sessão do PAULUS e o token anti-CSRF."""

    def __init__(self, api, email: str, senha: str, segredo: str) -> None:
        from fastapi.testclient import TestClient

        from acesso.contas import codigo_totp

        self.c = TestClient(api.app, base_url="https://escritorio.paulus.ia.br",
                            headers={"Cf-Connecting-IP": "200.1.2.3"})
        r = self.c.post("/api/acesso/entrar", json={"email": email, "senha": senha, "turnstile": "ok"})
        if "pendente" not in r.json():
            raise RuntimeError(f"entrar de fora falhou: {r.status_code} {r.text[:300]}")
        pend = r.json()["pendente"]
        r = self.c.post("/api/acesso/entrar/codigo",
                        json={"pendente": pend, "codigo": codigo_totp(segredo, int(time.time() // 30))})
        self.csrf = r.json()["csrf"]
        self.segredo = segredo

    def get(self, url, **k):
        return self.c.get(url, **k)

    def post(self, url, **k):
        return self.c.post(url, headers={"X-PAULUS-CSRF": self.csrf}, **k)


def sessoes_de_fora(api):
    """(titular, colaborador) de fora, ou None sem DPAPI (fora do Windows)."""
    import segredos
    from acesso.contas import codigo_totp

    if not segredos.disponivel():
        return None
    servico = api.estado.acesso_de_fora
    servico.conferir_turnstile = lambda token, ip="": "ok" if token == "ok" else "recusado"
    api.estado.prefs.dados["acesso_remoto"]["ligado"] = True
    api.estado.prefs.dados["acesso_remoto"]["so_google"] = False
    contas = servico.contas
    # O passo do código sai na hora de confirmar: calculado antes do criar
    # (scrypt, lento com a máquina cheia), a virada dos 30 s o deixava velho.
    t = contas.criar("Tereza Titular", "tereza@escritorio.com", "titular", "senha-da-tereza-1")
    contas.confirmar_totp(t["conta"]["id"], codigo_totp(t["segredo"], int(time.time() // 30) - 1))
    c = contas.criar("Caio Colaborador", "caio@escritorio.com", "colaborador", "senha-do-caio-1")
    contas.confirmar_totp(c["conta"]["id"], codigo_totp(c["segredo"], int(time.time() // 30) - 1))
    titular = Fora(api, "tereza@escritorio.com", "senha-da-tereza-1", t["segredo"])
    colab = Fora(api, "caio@escritorio.com", "senha-do-caio-1", c["segredo"])
    titular.conta_id, colab.conta_id = t["conta"]["id"], c["conta"]["id"]
    return titular, colab


def codigo_novo(fora) -> str:
    """O código do autenticador do passo seguinte (o do login já foi usado)."""
    from acesso.contas import codigo_totp

    return codigo_totp(fora.segredo, int(time.time() // 30) + 1)


def eventos_sse(texto: str) -> list[tuple[str, dict]]:
    import json

    eventos = []
    for bloco in texto.split("\n\n"):
        tipo, corpo = "", ""
        for linha in bloco.splitlines():
            if linha.startswith("event: "):
                tipo = linha[7:]
            elif linha.startswith("data: "):
                corpo += linha[6:]
        if tipo:
            eventos.append((tipo, json.loads(corpo or "{}")))
    return eventos


# CNPJ válido de teste (dígitos conferidos) e o CPF de um tomador pessoa física.
CNPJ_PRESTADOR = "11222333000181"
CNPJ_TOMADOR = "45997418000153"
CPF_TOMADOR = "52998224725"
GOIANIA = "5208707"


def certificado_a1(destino: Path, senha: str = "segredo-de-teste", cnpj: str = CNPJ_PRESTADOR,
                   dias: int = 365, nome: str = "ESCRITORIO DE TESTE LTDA") -> Path:
    """
    Um .pfx de teste com o CNPJ no nome ("RAZÃO SOCIAL:CNPJ", como o e-CNPJ
    da ICP-Brasil), que é onde o leitor do PAULUS procura.
    Não é ICP-Brasil: serve para assinar e conferir aqui, não para a Sefin.
    """
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome_x = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ICP-Brasil"),
        x509.NameAttribute(NameOID.COMMON_NAME, f"{nome}:{cnpj}"),
    ])
    agora = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(nome_x).issuer_name(nome_x).public_key(chave.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(agora - timedelta(days=1)).not_valid_after(agora + timedelta(days=dias))
            .add_extension(x509.KeyUsage(True, True, False, False, False, False, False, False, False), critical=True)
            .sign(chave, hashes.SHA256()))
    pfx = pkcs12.serialize_key_and_certificates(b"teste", chave, cert, None,
                                                serialization.BestAvailableEncryption(senha.encode()))
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(pfx)
    return destino
