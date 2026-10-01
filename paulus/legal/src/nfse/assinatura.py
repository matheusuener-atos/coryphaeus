"""
A assinatura XML (XMLDSig) da DPS e do pedido de evento, com o A1.

O perfil é o que o XSD 1.00 da NFS-e fixava e o 1.01 continua aceitando
(docs/PROGRESSO-NFSE.md, N0, linha 13): assinatura envelopada, referência ao
`Id` do elemento assinado (`infDPS` ou `infPedReg`), transformações
"enveloped-signature" e C14N 1.0 (20010315), resumo e assinatura RSA. O
padrão é SHA-1, o único escrito no esquema oficial; SHA-256 fica como opção
(`algoritmo="sha256"`), para o dia em que a documentação pedir.

C14N 1.0 é o motivo do `lxml` (a biblioteca padrão do Python só tem a 2.0).
A assinatura sai sem prefixo de namespace (`<Signature xmlns="...">`): a
Sefin recusa prefixo (E1228).

A conferência independente fica no teste (tests/test_n3_envio.py): o
SignedXml do .NET, o mesmo motor que costuma validar do lado de lá.
"""

from __future__ import annotations

import base64
import hashlib

from lxml import etree

DS = "http://www.w3.org/2000/09/xmldsig#"
C14N = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
ENVELOPED = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"
ALGORITMOS = {
    "sha1": {"assinatura": "http://www.w3.org/2000/09/xmldsig#rsa-sha1",
             "resumo": "http://www.w3.org/2000/09/xmldsig#sha1", "hash": "sha1"},
    "sha256": {"assinatura": "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",
               "resumo": "http://www.w3.org/2001/04/xmlenc#sha256", "hash": "sha256"},
}


class ErroAssinatura(RuntimeError):
    pass


def _c14n(el) -> bytes:
    """
    C14N 1.0 inclusivo do elemento como subconjunto do documento.

    O libxml2 erra quando o elemento é canonizado no lugar e um ancestral
    redeclara o namespace padrão (como a Signature dentro da DPS): sai um
    xmlns="" nos filhos, e a assinatura não confere em nenhum outro
    validador (medido contra o SignedXml do .NET). Uma cópia destacada leva
    os namespaces em escopo para a raiz dela e dá o resultado da norma.
    """
    import copy

    return etree.tostring(copy.deepcopy(el), method="c14n", exclusive=False, with_comments=False)


def _chave_e_certificado(pfx: bytes, senha: str):
    from cryptography.hazmat.primitives.serialization import pkcs12

    try:
        chave, cert, _ = pkcs12.load_key_and_certificates(pfx, (senha or "").encode())
    except ValueError as exc:
        raise ErroAssinatura("senha do certificado incorreta, ou arquivo inválido") from exc
    if chave is None or cert is None:
        raise ErroAssinatura("o certificado não traz a chave privada")
    return chave, cert


def assinar(xml: bytes, pfx: bytes, senha: str, ref_id: str, algoritmo: str = "sha1") -> bytes:
    """
    Assina o elemento com `Id=ref_id` e põe a Signature como último filho da
    raiz (é onde o XSD espera: DPS/Signature, pedRegEvento/Signature).
    """
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    if algoritmo not in ALGORITMOS:
        raise ErroAssinatura("algoritmo de assinatura desconhecido")
    alg = ALGORITMOS[algoritmo]
    chave, cert = _chave_e_certificado(pfx, senha)

    parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False, no_network=True)
    raiz = etree.fromstring(xml, parser)
    alvo = raiz.xpath("//*[@Id=$i]", i=ref_id)
    if len(alvo) != 1:
        raise ErroAssinatura(f"não achei um único elemento com Id {ref_id}")
    alvo = alvo[0]
    for velha in raiz.findall(f"{{{DS}}}Signature"):
        raiz.remove(velha)

    resumo = base64.b64encode(hashlib.new(alg["hash"], _c14n(alvo)).digest()).decode("ascii")

    sig = etree.SubElement(raiz, f"{{{DS}}}Signature", nsmap={None: DS})
    si = etree.SubElement(sig, f"{{{DS}}}SignedInfo")
    etree.SubElement(si, f"{{{DS}}}CanonicalizationMethod", Algorithm=C14N)
    etree.SubElement(si, f"{{{DS}}}SignatureMethod", Algorithm=alg["assinatura"])
    ref = etree.SubElement(si, f"{{{DS}}}Reference", URI=f"#{ref_id}")
    trs = etree.SubElement(ref, f"{{{DS}}}Transforms")
    etree.SubElement(trs, f"{{{DS}}}Transform", Algorithm=ENVELOPED)
    etree.SubElement(trs, f"{{{DS}}}Transform", Algorithm=C14N)
    etree.SubElement(ref, f"{{{DS}}}DigestMethod", Algorithm=alg["resumo"])
    etree.SubElement(ref, f"{{{DS}}}DigestValue").text = resumo

    h = hashes.SHA1() if alg["hash"] == "sha1" else hashes.SHA256()
    valor = chave.sign(_c14n(si), padding.PKCS1v15(), h)
    etree.SubElement(sig, f"{{{DS}}}SignatureValue").text = base64.b64encode(valor).decode("ascii")
    ki = etree.SubElement(sig, f"{{{DS}}}KeyInfo")
    xd = etree.SubElement(ki, f"{{{DS}}}X509Data")
    der = cert.public_bytes(serialization.Encoding.DER)
    etree.SubElement(xd, f"{{{DS}}}X509Certificate").text = base64.b64encode(der).decode("ascii")
    return etree.tostring(raiz, xml_declaration=True, encoding="UTF-8")


def verificar(xml: bytes) -> tuple[bool, str]:
    """
    Confere a assinatura (resumo do elemento referenciado e o valor RSA com o
    certificado do KeyInfo). Serve para conferir o que a Sefin devolve e o
    que foi assinado aqui; a conferência independente é a do .NET, no teste.
    """
    from cryptography import x509
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    raiz = etree.fromstring(xml, etree.XMLParser(resolve_entities=False, no_network=True))
    sig = raiz.find(f".//{{{DS}}}Signature")
    if sig is None:
        return False, "sem assinatura"
    ns = {"ds": DS}
    ref_uri = sig.xpath("string(ds:SignedInfo/ds:Reference/@URI)", namespaces=ns)
    alvo = raiz.xpath("//*[@Id=$i]", i=ref_uri.lstrip("#"))
    if len(alvo) != 1:
        return False, "a referência não aponta para um elemento"
    met_resumo = sig.xpath("string(ds:SignedInfo/ds:Reference/ds:DigestMethod/@Algorithm)", namespaces=ns)
    nome_hash = "sha256" if met_resumo.endswith("sha256") else "sha1"
    # O elemento assinado pode conter a própria Signature (enveloped): tira
    # numa cópia antes de canonicalizar.
    copia = etree.fromstring(etree.tostring(alvo[0]))
    for s in copia.iter(f"{{{DS}}}Signature"):
        s.getparent().remove(s)
    alvo_c14n = _c14n(alvo[0]) if alvo[0].find(f".//{{{DS}}}Signature") is None else _c14n(copia)
    resumo = base64.b64encode(hashlib.new(nome_hash, alvo_c14n).digest()).decode("ascii")
    if resumo != sig.xpath("string(ds:SignedInfo/ds:Reference/ds:DigestValue)", namespaces=ns).strip():
        return False, "o conteúdo assinado foi alterado (resumo não confere)"
    der = base64.b64decode(sig.xpath("string(ds:KeyInfo/ds:X509Data/ds:X509Certificate)", namespaces=ns))
    cert = x509.load_der_x509_certificate(der)
    met_ass = sig.xpath("string(ds:SignedInfo/ds:SignatureMethod/@Algorithm)", namespaces=ns)
    h = hashes.SHA256() if met_ass.endswith("sha256") else hashes.SHA1()
    valor = base64.b64decode(sig.xpath("string(ds:SignatureValue)", namespaces=ns))
    try:
        cert.public_key().verify(valor, _c14n(sig.find(f"{{{DS}}}SignedInfo")), padding.PKCS1v15(), h)
    except InvalidSignature:
        return False, "a assinatura não confere com o certificado"
    return True, "assinatura válida"
