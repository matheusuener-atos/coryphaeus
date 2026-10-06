"""
Os dados públicos de um CNPJ, pela BrasilAPI (brasilapi.com.br/api/cnpj/v1),
para preencher a ficha assim que o número é digitado (frontend/js/39-campos.js).

A BrasilAPI é gratuita, sem chave, e devolve o cadastro da Receita Federal:
razão social, nome fantasia, situação, endereço em partes (com o código IBGE
do município, o que a NFS-e pede), telefone e e-mail. Só o número do CNPJ sai
do computador; é dado público.

A tela não fala com a BrasilAPI direto: pergunta a /api/cnpj/{cnpj}, daqui.
Assim a consulta funciona igual na janela, no acesso de fora e no celular, e a
resposta fica guardada um dia (o mesmo CNPJ digitado de novo não sai outra
vez).

O CNPJ com letras (IN RFB 2.229/2024) é conferido pelo dígito, mas a
BrasilAPI ainda não o consulta: volta "não consulta", sem ir à rede.
"""

from __future__ import annotations

import re
import threading
import time

from fastapi import HTTPException

BRASILAPI = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
VALIDADE_S = 24 * 3600
_guardado: dict[str, tuple[float, dict]] = {}
_trava = threading.Lock()

# Palavras que ficam minúsculas no meio do endereço ("Rua das Flores").
_MINUSCULAS = {"a", "as", "o", "os", "da", "das", "de", "do", "dos", "e", "em", "na", "nas", "no", "nos"}


def limpar(cnpj: str) -> str:
    return re.sub(r"[^0-9A-Z]", "", str(cnpj or "").upper())


def valido(cnpj: str) -> bool:
    c = limpar(cnpj)
    if not re.fullmatch(r"[0-9A-Z]{12}\d{2}", c) or len(set(c)) == 1:
        return False
    v = [ord(ch) - 48 for ch in c]
    for n, pesos in ((12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]), (13, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])):
        resto = sum(a * b for a, b in zip(v[:n], pesos)) % 11
        if (0 if resto < 2 else 11 - resto) != v[n]:
            return False
    return True


def _titulo(texto: str) -> str:
    """
    'RUA DAS FLORES' -> 'Rua das Flores'. Fica como veio o que não é palavra:
    romano ('TORRE II'), código com número ('SALA S101') e o 'SN' do número.
    """
    saida = []
    for i, p in enumerate(str(texto or "").strip().split()):
        nucleo = re.sub(r"[^\w]", "", p).upper()
        if re.fullmatch(r"[IVXL]+|\w*\d\w*|SN", nucleo or "-"):
            saida.append(p.upper())
        elif i and p.lower() in _MINUSCULAS:
            saida.append(p.lower())
        else:
            saida.append(p[:1].upper() + p[1:].lower())
    return " ".join(saida)


def _texto(x) -> str:
    return str(x or "").strip()


def resumir(bruto: dict) -> dict:
    """A resposta da BrasilAPI no formato das fichas do PAULUS."""
    tipo = _texto(bruto.get("descricao_tipo_de_logradouro"))
    rua = _texto(bruto.get("logradouro"))
    if tipo and not rua.upper().startswith(tipo.upper()):
        rua = tipo + " " + rua
    logradouro = _titulo(rua)
    numero = _texto(bruto.get("numero"))
    complemento = _titulo(_texto(bruto.get("complemento")))
    bairro = _titulo(_texto(bruto.get("bairro")))
    municipio = _titulo(_texto(bruto.get("municipio")))
    uf = _texto(bruto.get("uf")).upper()
    cep = re.sub(r"\D", "", _texto(bruto.get("cep")))
    cep_legivel = cep[:5] + "-" + cep[5:] if len(cep) == 8 else cep
    # "Rua das Flores, 100, Sala 2 - Centro, Goiânia/GO, CEP 74000-000"
    endereco = ", ".join(x for x in (logradouro, numero, complemento) if x)
    if bairro:
        endereco += (" - " if endereco else "") + bairro
    cidade = municipio + ("/" + uf if uf else "")
    endereco = ", ".join(x for x in (endereco, cidade, "CEP " + cep_legivel if cep else "") if x)
    situacao = _texto(bruto.get("descricao_situacao_cadastral")).upper()
    return {
        "cnpj": limpar(bruto.get("cnpj")),
        "razao_social": _texto(bruto.get("razao_social")),
        "nome_fantasia": _texto(bruto.get("nome_fantasia")),
        "situacao": situacao,
        "ativa": situacao == "ATIVA",
        "logradouro": logradouro,
        "numero": numero,
        "complemento": complemento,
        "bairro": bairro,
        "municipio": municipio,
        "uf": uf,
        "codigo_municipio_ibge": _texto(bruto.get("codigo_municipio_ibge")),
        "cep": cep,
        "endereco": endereco,
        "telefone": re.sub(r"\D", "", _texto(bruto.get("ddd_telefone_1"))),
        "email": _texto(bruto.get("email")).lower(),
        "fonte": "Receita Federal, pela BrasilAPI",
    }


def consultar(cnpj: str, *, pedir=None) -> dict:
    """
    O CNPJ na BrasilAPI. ValueError: o número não fecha; LookupError: a
    Receita não tem o CNPJ (ou a BrasilAPI não o consulta); ConnectionError:
    sem internet ou a BrasilAPI fora. `pedir` troca o requests.get (testes).
    """
    c = limpar(cnpj)
    if not valido(c):
        raise ValueError("CNPJ inválido: confira os caracteres")
    if not c.isdigit():
        raise LookupError("a BrasilAPI ainda não consulta o CNPJ com letras")
    with _trava:
        guardado = _guardado.get(c)
        if guardado and time.time() - guardado[0] < VALIDADE_S:
            return guardado[1]
    if pedir is None:
        import requests

        pedir = requests.get
    try:
        resp = pedir(BRASILAPI.format(cnpj=c), headers={"Accept": "application/json", "User-Agent": "PAULUS"}, timeout=10)
    except Exception as exc:  # noqa: BLE001 - sem rede, DNS, tempo: tudo é "não deu agora"
        raise ConnectionError("sem resposta da BrasilAPI: confira a internet ou preencha à mão") from exc
    if resp.status_code == 404:
        raise LookupError("a Receita não tem este CNPJ")
    if resp.status_code == 400:
        raise LookupError("a BrasilAPI recusou este CNPJ")
    if resp.status_code >= 400:
        raise ConnectionError(f"a BrasilAPI respondeu com erro ({resp.status_code}); tente de novo em alguns minutos")
    try:
        dados = resumir(resp.json() or {})
    except ValueError as exc:
        raise ConnectionError("a BrasilAPI não devolveu os dados agora; tente de novo") from exc
    with _trava:
        _guardado[c] = (time.time(), dados)
    return dados


def montar(app) -> None:
    @app.get("/api/cnpj/{cnpj}")
    def cnpj_consultar(cnpj: str) -> dict:
        try:
            return consultar(cnpj)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ConnectionError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
