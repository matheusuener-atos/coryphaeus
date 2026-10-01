"""Prova da W0: certificado HTTPS para localhost, confiável só nesta máquina.

Gera uma autoridade restrita por "name constraints" a localhost e 127.0.0.1,
emite com ela o certificado do servidor e descarta a chave da autoridade sem
gravá-la. Mesmo que alguém copie o que fica no disco, não consegue emitir
certificado para outro nome. O preço: renovar é gerar outra autoridade (e o
Windows pergunta de novo).

Uso: python certificado_local.py <pasta>
Grava <pasta>/autoridade.cer (para o CurrentUser\\Root), servidor.pem e
servidor.key.
"""

from __future__ import annotations

import ipaddress
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

NOMES_DNS = ["localhost"]
IPS = [ipaddress.ip_address("127.0.0.1")]


def gerar(pasta: Path, dias: int = 825) -> dict:
    pasta.mkdir(parents=True, exist_ok=True)
    agora = datetime.now(timezone.utc)
    fim = agora + timedelta(days=dias)

    chave_ac = ec.generate_private_key(ec.SECP256R1())
    nome_ac = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "PAULUS - esta instalacao (so localhost)"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PAULUS"),
    ])
    restricao = x509.NameConstraints(
        permitted_subtrees=[x509.DNSName(n) for n in NOMES_DNS]
        + [x509.IPAddress(ipaddress.ip_network(f"{ip}/32")) for ip in IPS],
        excluded_subtrees=None,
    )
    ac = (
        x509.CertificateBuilder()
        .subject_name(nome_ac).issuer_name(nome_ac)
        .public_key(chave_ac.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora - timedelta(minutes=5)).not_valid_after(fim)
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(restricao, critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=False, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=True,
            crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(chave_ac.public_key()), critical=False)
        .sign(chave_ac, hashes.SHA256())
    )

    chave_srv = ec.generate_private_key(ec.SECP256R1())
    srv = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
        .issuer_name(nome_ac)
        .public_key(chave_srv.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora - timedelta(minutes=5)).not_valid_after(fim)
        .add_extension(x509.SubjectAlternativeName(
            [x509.DNSName(n) for n in NOMES_DNS] + [x509.IPAddress(ip) for ip in IPS]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(chave_ac.public_key()), critical=False)
        .sign(chave_ac, hashes.SHA256())
    )
    del chave_ac  # nunca gravada

    (pasta / "autoridade.cer").write_bytes(ac.public_bytes(serialization.Encoding.DER))
    (pasta / "servidor.pem").write_bytes(
        srv.public_bytes(serialization.Encoding.PEM) + ac.public_bytes(serialization.Encoding.PEM))
    (pasta / "servidor.key").write_bytes(chave_srv.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return {"impressao": ac.fingerprint(hashes.SHA1()).hex().upper(), "vence": fim.isoformat()}


if __name__ == "__main__":
    print(gerar(Path(sys.argv[1])))
