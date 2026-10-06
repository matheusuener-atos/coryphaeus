"""
Testes do CNPJ que preenche a ficha (src/cnpj_receita.py e o pedaço de
frontend/js/39-campos.js que consulta e preenche).

A BrasilAPI é trocada por uma falsa (`pedir`): nada sai para a rede. Confere
o resumo da resposta da Receita, os erros (inválido, com letras, não achado,
sem internet), a resposta guardada, a rota e a política do acesso de fora,
e, no Node, o que a tela consulta e o valor que vai para cada campo.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_cnpj_receita.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import cnpj_receita  # noqa: E402

JS = RAIZ / "frontend" / "js" / "39-campos.js"
_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


# Como a BrasilAPI devolve (consulta real de 06/10/2026, Banco do Brasil).
BRUTO = {
    "cnpj": "00000000000191", "razao_social": "BANCO DO BRASIL SA", "nome_fantasia": "DIRECAO GERAL",
    "descricao_situacao_cadastral": "ATIVA", "descricao_tipo_de_logradouro": "QUADRA",
    "logradouro": "SAUN QUADRA 5 BLOCO B TORRE I, II, III", "numero": "SN", "complemento": "ANDAR T I SL S101",
    "bairro": "ASA NORTE", "municipio": "BRASILIA", "uf": "DF", "codigo_municipio_ibge": 5300108,
    "cep": "70040912", "ddd_telefone_1": "6134939002", "email": None,
}


class Resposta:
    def __init__(self, status: int, corpo=None):
        self.status_code = status
        self._corpo = corpo

    def json(self):
        if isinstance(self._corpo, Exception):
            raise self._corpo
        return self._corpo


class Falsa:
    def __init__(self, resposta):
        self.resposta = resposta
        self.urls: list[str] = []

    def __call__(self, url, **_):
        self.urls.append(url)
        if isinstance(self.resposta, Exception):
            raise self.resposta
        return self.resposta


def test_resumo() -> None:
    print("\no resumo da resposta da Receita")
    d = cnpj_receita.resumir(BRUTO)
    checar(d["razao_social"] == "BANCO DO BRASIL SA", "razão social como a Receita escreve", d["razao_social"])
    checar(d["logradouro"] == "Quadra Saun Quadra 5 Bloco B Torre I, II, III", "tipo + logradouro, romanos em maiúsculas", d["logradouro"])
    checar(d["complemento"] == "Andar T I Sl S101", "código com número fica como veio", d["complemento"])
    checar(d["numero"] == "SN", "SN fica", d["numero"])
    checar(d["municipio"] == "Brasilia" and d["uf"] == "DF", "cidade e UF", (d["municipio"], d["uf"]))
    checar(d["codigo_municipio_ibge"] == "5300108", "código IBGE em texto (a NFS-e pede)", d["codigo_municipio_ibge"])
    checar(d["telefone"] == "6134939002" and d["email"] == "", "telefone em dígitos; e-mail nulo vira vazio", (d["telefone"], d["email"]))
    checar(d["endereco"].endswith("Asa Norte, Brasilia/DF, CEP 70040-912"), "endereço numa linha", d["endereco"])
    checar(d["ativa"] is True, "situação ativa")
    d2 = cnpj_receita.resumir({**BRUTO, "descricao_situacao_cadastral": "BAIXADA", "logradouro": "RUA DAS FLORES",
                               "descricao_tipo_de_logradouro": "RUA"})
    checar(d2["ativa"] is False and d2["situacao"] == "BAIXADA", "baixada não é ativa")
    checar(d2["logradouro"] == "Rua das Flores", "tipo não se repete; 'das' minúsculo", d2["logradouro"])


def test_consulta() -> None:
    print("\na consulta, com a BrasilAPI falsa")
    cnpj_receita._guardado.clear()
    falsa = Falsa(Resposta(200, BRUTO))
    d = cnpj_receita.consultar("00.000.000/0001-91", pedir=falsa)
    checar(d["razao_social"] == "BANCO DO BRASIL SA", "consulta pelo número formatado")
    checar(falsa.urls == ["https://brasilapi.com.br/api/cnpj/v1/00000000000191"], "a URL leva só os dígitos", falsa.urls)
    cnpj_receita.consultar("00000000000191", pedir=falsa)
    checar(len(falsa.urls) == 1, "o mesmo CNPJ de novo não sai outra vez", len(falsa.urls))

    def erro(cnpj, resposta, tipo):
        f = Falsa(resposta)
        try:
            cnpj_receita.consultar(cnpj, pedir=f)
        except tipo as exc:
            return str(exc), f.urls
        except Exception as exc:  # noqa: BLE001
            return "outro erro: " + repr(exc), f.urls
        return "sem erro", f.urls

    msg, urls = erro("00.000.000/0001-92", Resposta(200, BRUTO), ValueError)
    checar("inválido" in msg and not urls, "dígito errado: recusa sem ir à rede", msg)
    msg, urls = erro("12.ABC.345/01DE-35", Resposta(200, BRUTO), LookupError)
    checar("letras" in msg and not urls, "CNPJ com letras: não consulta", msg)
    msg, _ = erro("11.222.333/0001-81", Resposta(404, {"message": "não encontrado"}), LookupError)
    checar("não tem" in msg, "404: a Receita não tem", msg)
    msg, _ = erro("11.444.777/0001-61", OSError("sem rede"), ConnectionError)
    checar("internet" in msg, "sem rede: diz para conferir a internet", msg)
    msg, _ = erro("45.997.418/0001-53", Resposta(503), ConnectionError)
    checar("503" in msg, "BrasilAPI fora: o código", msg)
    msg, _ = erro("11.222.333/0001-81", Resposta(200, {"planos": []}), ConnectionError)
    checar("não devolveu" in msg, "200 sem razão social não vira CNPJ encontrado", msg)


def test_rota() -> None:
    print("\na rota e a política do acesso de fora")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from acesso import politicas

    app = FastAPI()
    cnpj_receita.montar(app)
    cnpj_receita._guardado.clear()
    cnpj_receita._guardado["00000000000191"] = (10 ** 12, cnpj_receita.resumir(BRUTO))
    c = TestClient(app)
    r = c.get("/api/cnpj/00000000000191")
    checar(r.status_code == 200 and r.json()["uf"] == "DF", "200 com os dados", r.status_code)
    r = c.get("/api/cnpj/00000000000192")
    checar(r.status_code == 400 and "inválido" in r.json()["detail"], "400 com o motivo", r.text)
    checar(politicas.REGISTRO.get(("GET", "/api/cnpj/{cnpj}")) == politicas.PERMITIDO, "permitida de fora, como ver cadastros")


def rodar_js(corpo: str):
    codigo = JS.read_text(encoding="utf-8") + "\n;process.stdout.write(JSON.stringify((() => {" + corpo + "})()));"
    r = subprocess.run(["node", "-"], input=codigo, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise RuntimeError(r.stderr[-800:])
    return json.loads(r.stdout)


def test_tela() -> None:
    print("\na tela: o que consulta e o que preenche")
    dados = cnpj_receita.resumir(BRUTO)
    r = rodar_js("""
      const el = (valor, ds) => ({ value: valor, dataset: ds, readOnly: false, disabled: false });
      const d = """ + json.dumps(dados) + """;
      return {
        cnpj: cnpjParaConsultar(el("00.000.000/0001-91", { campo: "cnpj" })),
        cpfCnpj: cnpjParaConsultar(el("00000000000191", { campo: "cpf-cnpj" })),
        semMascara: cnpjParaConsultar(el("00000000000191", { cnpjBusca: "1" })),
        incompleto: cnpjParaConsultar(el("00.000.000/0001-9", { campo: "cnpj" })),
        errado: cnpjParaConsultar(el("00.000.000/0001-92", { campo: "cnpj" })),
        cpf: cnpjParaConsultar(el("529.982.247-25", { campo: "cpf-cnpj" })),
        telefoneCampo: cnpjParaConsultar(el("00000000000191", { campo: "telefone" })),
        soLeitura: cnpjParaConsultar(Object.assign(el("00000000000191", { cnpjBusca: "1" }), { readOnly: true })),
        letras: cnpjParaConsultar(el("12.ABC.345/01DE-35", { campo: "cnpj" })),
        telefone: valorDaReceita(d, "telefone"),
        ibge: valorDaReceita(d, "codigo_municipio_ibge"),
        email: valorDaReceita(d, "email"),
        estranho: valorDaReceita(d, "fonte"),
        marca: marcaCnpj("cep") + "|" + marcaCnpj(""),
      };
    """)
    checar(r["cnpj"] == "00000000000191" and r["cpfCnpj"] == r["cnpj"] and r["semMascara"] == r["cnpj"],
           "consulta no campo de CNPJ, no CPF/CNPJ e no marcado sem máscara", r)
    checar(not r["incompleto"] and not r["errado"] and not r["cpf"], "incompleto, dígito errado e CPF não consultam", r)
    checar(not r["telefoneCampo"] and not r["soLeitura"], "outro tipo de campo e campo só de leitura não consultam", r)
    checar(not r["letras"], "CNPJ com letras não consulta", r["letras"])
    checar(r["telefone"] == "(61) 3493-9002", "telefone formatado", r["telefone"])
    checar(r["ibge"] == "5300108" and r["email"] == "", "IBGE e e-mail vazio", (r["ibge"], r["email"]))
    checar(r["estranho"] == "", "dado fora da lista não entra em campo", r["estranho"])
    checar(r["marca"] == ' data-cnpj="cep"|', "a marca do campo", r["marca"])


def test_telas_marcadas() -> None:
    print("\nas telas com CNPJ marcam o que ele preenche")
    js = RAIZ / "frontend" / "js"
    for arquivo, trechos in {
        "06-cadastros.js": ["marcaCnpj(cadPeloCnpj(chave))", 'end_cmun: "codigo_municipio_ibge"'],
        "05-configuracoes.js": ['data-cnpj-grupo="1"', 'marcaCnpj("razao_social")'],
        "86-fichas-na-conversa.js": ["cnpjBusca: true", 'data-cnpj-grupo="1"'],
        "12-telas-e-acervo.js": ['"razao_social"]', 'data-cnpj-grupo="1"'],
        "90-nfse.js": ["data-cnpj-busca", 'marcaCnpj("codigo_municipio_ibge")'],
        "91-nfse-nota.js": ["data-cnpj-busca", 'data-cnpj-grupo="1"'],
    }.items():
        texto = (js / arquivo).read_text(encoding="utf-8")
        checar(all(t in texto for t in trechos), arquivo, [t for t in trechos if t not in texto])


def main() -> int:
    test_resumo()
    test_consulta()
    test_rota()
    test_tela()
    test_telas_marcadas()
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
