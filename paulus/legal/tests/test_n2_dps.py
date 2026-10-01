"""
Portão da N2 do emissor de NFS-e — montar e conferir a DPS.

  - 20 DPS de exemplo (CNPJ e CPF de tomador; com e sem retenção; ISS
    retido; Simples × não optante; sociedade com ISS fixo; município da
    prestação diferente…) validam no XSD oficial;
  - a conta de cada uma confere, centavo a centavo, com a planilha de
    referência feita à mão (tests/dados/nfse_referencia_n2.csv);
  - numeração sem repetição e sem buraco com 50 reservas concorrentes
    (50 threads, e 5 processos com conexões próprias);
  - campo obrigatório faltando bloqueia, dizendo qual;
  - o cartão pela rota: cria do recebimento, edita, confere e descarta.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_n2_dps.py
"""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-n2-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

from _nfse_comum import CNPJ_PRESTADOR, CNPJ_TOMADOR, CPF_TOMADOR, GOIANIA, checar, falhas  # noqa: E402

CPF_PRESTADOR = "11144477735"
CAMPOS_CONTA = ("base_iss", "iss", "iss_retido", "paliq", "irrf", "pis", "cofins", "csll", "cp",
                "v_ret_csll", "tp_ret", "v_total_ret", "v_liq", "cbs", "ibs")


def _quando(texto: str) -> tuple[str, int]:
    """"150pj" -> ("tomador_pj", 150); "1100s" -> ("sempre", 1100); "n" -> ("nunca", 0)."""
    if texto == "n":
        return "nunca", 0
    if texto in ("pj", "s"):
        return ("tomador_pj" if texto == "pj" else "sempre"), 0
    if texto.endswith("pj"):
        return "tomador_pj", int(texto[:-2])
    return "sempre", int(texto[:-1])


def _casos() -> list[dict]:
    linhas = [l for l in (RAIZ / "tests" / "dados" / "nfse_referencia_n2.csv").read_text(encoding="utf-8").splitlines()
              if l and not l.startswith("#")]
    return list(csv.DictReader(linhas, delimiter=";"))


def _prestador(c: dict) -> dict:
    from nfse import prestador

    ret = {}
    for k in ("iss", "irrf", "pis", "cofins", "csll", "cp"):
        quando, bp = _quando(c[f"ret_{k}"])
        ret[k] = {"quando": quando, "aliquota_bp": bp, "minimo_centavos": int(c["min_irrf"]) if k == "irrf" else 0}
    dados = {
        "documento": CPF_PRESTADOR if c["prestador"] == "cpf" else CNPJ_PRESTADOR,
        "razao_social": "Escritório de Teste", "inscricao_municipal": "123456", "municipio": GOIANIA,
        "opcao_simples": c["op_simples"], "regime_apuracao_sn": "" if c["reg_ap"] == "-" else c["reg_ap"],
        "regime_especial": c["reg_esp"],
        "servico": {"ctribnac": "171401", "nbs": "113012000", "descricao": "Honorários advocatícios",
                    "aliquota_iss_bp": int(c["aliq_iss"])},
        "retencoes": ret, "pis_cofins": {"cst": "01"},
        "ibscbs": {"enviar": c["ibscbs"] == "1", "cst": "200", "cclasstrib": "200052", "cindop": "100301"},
        "total_tributos": {"modo": "simples" if c["op_simples"] == "3" else "percentual", "federal_bp": 1345,
                           "estadual_bp": 0, "municipal_bp": 500, "simples_bp": 600},
    }
    limpo, _ = prestador.conferir(dados)
    return limpo


def _nota(c: dict) -> dict:
    return {
        "valor_centavos": int(c["valor"]), "desconto_incond_centavos": int(c["desconto"]),
        "competencia": "2026-09-15", "descricao": f"Honorários — caso {c['caso']}",
        "municipio_incidencia": "" if c["loc_prest"] == "-" else c["loc_prest"],
        "tomador": {"nome": "Tomador de Teste", "documento": CPF_TOMADOR if c["tomador"] == "cpf" else CNPJ_TOMADOR,
                    "logradouro": "Rua 1", "numero": "10", "bairro": "Centro", "cep": "74000000", "cmun": GOIANIA,
                    "email": "fiscal@tomador.com.br"},
    }


def test_referencia() -> None:
    print("\n20 DPS: a conta confere com a planilha feita à mão e o XML valida no XSD oficial")
    from nfse import conferencia, dps, tributos

    casos = _casos()
    checar(len(casos) == 20, "20 casos na planilha de referência", len(casos))
    validas = 0
    for c in casos:
        prest = _prestador(c)
        nota = _nota(c)
        conta = tributos.calcular(prest, nota, municipio_ativo=c["ativo"] == "1")
        obtido = {
            "base_iss": conta.base_iss, "iss": conta.iss, "iss_retido": int(conta.iss_retido),
            "paliq": int(conta.informar_paliq), **{k: conta.retencoes.get(k, 0) for k in ("irrf", "pis", "cofins", "csll", "cp")},
            "v_ret_csll": conta.v_ret_csll, "tp_ret": int(conta.tp_ret_pis_cofins), "v_total_ret": conta.v_total_ret,
            "v_liq": conta.v_liq, "cbs": conta.ibscbs.get("cbs", "-"), "ibs": conta.ibscbs.get("ibs_uf", "-"),
        }
        esperado = {k: (c[k] if c[k] == "-" else int(c[k])) for k in CAMPOS_CONTA}
        diferentes = {k: (obtido[k], esperado[k]) for k in CAMPOS_CONTA if obtido[k] != esperado[k]}
        checar(not diferentes and not conta.erros, f"caso {c['caso']} ({c['descricao']}): conta centavo a centavo",
               diferentes or conta.erros)
        xml, ident = dps.montar(prest=prest, nota=nota, conta=conta, ambiente="producao_restrita", serie="1",
                                numero=int(c["caso"]), ver_aplic="PAULUS-teste")
        erros_xsd = conferencia.validar_xsd(xml, "producao_restrita")
        erros_prod = conferencia.validar_xsd(xml, "producao")
        if not erros_xsd and not erros_prod:
            validas += 1
        checar(not erros_xsd and not erros_prod, f"caso {c['caso']}: valida no XSD (produção restrita e produção)",
               (erros_xsd or erros_prod)[:3])
        checar(ident.startswith("DPS" + GOIANIA + ("1000" if c["prestador"] == "cpf" else "2"))
               and len(ident) == 45 and ident.endswith(f"{int(c['caso']):015d}"),
               f"caso {c['caso']}: Id da DPS com 45 posições (TSIdDPS)", ident)
        texto = xml.decode("utf-8")
        checar(("<pAliq>" in texto) == (esperado["paliq"] == 1), f"caso {c['caso']}: pAliq só quando a regra manda", esperado["paliq"])
        checar("<xNome>" not in texto.split("<toma>")[0], f"caso {c['caso']}: sem nome do prestador (E0121)")
        checar(("<IBSCBS>" in texto) == (c["ibscbs"] == "1"), f"caso {c['caso']}: grupo IBSCBS conforme a configuração")
        checar("ds:" not in texto and texto.startswith("<?xml version='1.0' encoding='UTF-8'?>"),
               f"caso {c['caso']}: sem prefixo de namespace e em UTF-8 (E1228, E1229)")
    checar(validas == 20, "as 20 DPS validam no XSD oficial", validas)


def test_numeracao(api) -> None:
    print("\nnumeração: sem repetir e sem buraco, com reservas concorrentes")
    from nfse import numeracao

    base = api.estado.base
    obtidos: list[int] = []
    trava = threading.Lock()

    def reserva():
        n = numeracao.reservar(base, "producao_restrita", "7")
        with trava:
            obtidos.append(n)

    fios = [threading.Thread(target=reserva) for _ in range(50)]
    for f in fios:
        f.start()
    for f in fios:
        f.join()
    checar(sorted(obtidos) == list(range(1, 51)), "50 threads: 1 a 50, sem repetir nem pular",
           (len(set(obtidos)), min(obtidos), max(obtidos)))

    # Cinco processos, cada um com a sua conexão ao mesmo arquivo.
    codigo = (
        "import sys; sys.path.insert(0, sys.argv[1]);\n"
        "from base import Base; from nfse import numeracao\n"
        "b = Base(sys.argv[2])\n"
        "print(','.join(str(numeracao.reservar(b, 'producao_restrita', '8')) for _ in range(10)))\n"
    )
    procs = [subprocess.Popen([sys.executable, "-c", codigo, str(RAIZ / "src"), str(base.caminho)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(5)]
    numeros: list[int] = []
    for p in procs:
        saida, erro = p.communicate(timeout=120)
        numeros += [int(x) for x in saida.strip().split(",") if x]
        if p.returncode:
            print(erro[-500:])
    checar(sorted(numeros) == list(range(1, 51)), "5 processos × 10: 1 a 50, sem repetir nem pular",
           (len(numeros), len(set(numeros))))

    numeracao.devolver(base, "producao_restrita", "7", 13)
    checar(numeracao.proximo(base, "producao_restrita", "7") == 13, "número devolvido (nota descartada) volta primeiro")
    checar(numeracao.reservar(base, "producao_restrita", "7") == 13, "e é o próximo reservado")
    checar(numeracao.reservar(base, "producao_restrita", "7") == 51, "depois a sequência continua do 51")
    checar(numeracao.reservar(base, "producao", "7") == 1, "produção tem a própria sequência")


def _configurar(api) -> None:
    e = api.estado.nfse
    e.prestador.gravar({
        "documento": CNPJ_PRESTADOR, "razao_social": "Escritório de Teste", "inscricao_municipal": "123456",
        "municipio": GOIANIA, "opcao_simples": "1",
        "servico": {"ctribnac": "171401", "nbs": "113012000", "descricao": "Honorários advocatícios", "aliquota_iss_pct": "5"},
        "retencoes": {"irrf": {"quando": "tomador_pj", "aliquota_pct": "1,5"}, "pis": {"quando": "nunca"},
                      "cofins": {"quando": "nunca"}, "csll": {"quando": "nunca"}, "cp": {"quando": "nunca"},
                      "iss": {"quando": "nunca"}},
        "ibscbs": {"enviar": True, "cst": "200", "cclasstrib": "200052", "cindop": "100301"},
    }, quem="teste")
    api.estado.base.escrever("INSERT OR REPLACE INTO nfse_municipio (cmun, ambiente, situacao, consultado_em) "
                             "VALUES (?, 'producao_restrita', 'conveniado', datetime('now'))", (GOIANIA,))


def test_obrigatorios(api) -> None:
    print("\ncampo obrigatório faltando bloqueia, dizendo qual")
    _configurar(api)
    n = api.estado.nfse.notas.criar({"valor": "1.000,00", "descricao": "Honorários", "competencia": "2026-09-30"})
    checar("falta o CPF ou CNPJ do tomador" in n["erros"] and "falta o nome do tomador" in n["erros"],
           "sem tomador: diz que falta o documento e o nome", n["erros"])
    n = api.estado.nfse.notas.atualizar(n["id"], {"tomador": {"nome": "ACME", "documento": CNPJ_TOMADOR}})
    checar(any("falta o endereço completo do tomador" in e for e in n["erros"]),
           "tomador sem endereço com cIndOp 100301: bloqueia e diz a regra", n["erros"])
    n = api.estado.nfse.notas.atualizar(n["id"], {"tomador": {"logradouro": "Rua 1", "numero": "1", "bairro": "Centro",
                                                              "cep": "74000-000", "cmun": GOIANIA}, "valor": "0"})
    checar(any("valor do serviço precisa ser maior que zero" in e for e in n["erros"]), "valor zero bloqueia", n["erros"])
    n = api.estado.nfse.notas.atualizar(n["id"], {"valor": "1.000,00", "competencia": "2099-01-01"})
    checar(any("competência não pode ser depois de hoje" in e for e in n["erros"]), "competência no futuro bloqueia (E0015)", n["erros"])
    n = api.estado.nfse.notas.atualizar(n["id"], {"competencia": "2025-12-20"})
    checar(any("E0850" in e for e in n["erros"]), "IBS/CBS antes de 2026 bloqueia (E0850)", n["erros"])
    n = api.estado.nfse.notas.atualizar(n["id"], {"competencia": "2026-09-30", "tomador": {"documento": "45997418000154"}})
    checar(any("CNPJ do tomador não confere" in e for e in n["erros"]), "CNPJ do tomador com DV errado bloqueia", n["erros"])
    n = api.estado.nfse.notas.atualizar(n["id"], {"tomador": {"documento": CNPJ_TOMADOR}})
    checar(not n["erros"], "corrigido: sem erros", n["erros"])
    checar(any("mês anterior" in a for a in n["avisos"]) or n["competencia"][:7] == __import__("datetime").date.today().isoformat()[:7],
           "competência de mês anterior vira aviso, não erro", n["avisos"])


def test_cartao_pela_rota(api) -> None:
    print("\no cartão pela rota: do recebimento, editar, conferir, descartar")
    from fastapi.testclient import TestClient

    local = TestClient(api.app, headers=api.cabecalho_local())
    cid = api.estado.cadastros.salvar({"nome": "Cliente do Recebimento", "documento": "45.997.418/0001-53",
                                       "end_logradouro": "Av. 2", "end_numero": "200", "end_bairro": "Setor Sul",
                                       "end_cep": "74000000", "end_cmun": GOIANIA})
    lid = api.estado.financeiro.salvar({"tipo": "recebimento", "descricao": "Honorários de setembro", "centavos": 500000,
                                        "cadastro_id": cid, "vencimento": "2026-09-30"})
    api.estado.financeiro.liquidar(lid, "2026-09-30")
    r = local.post("/api/nfse/notas", json={"origem": "financeiro", "dados": {"lancamento_id": lid}})
    checar(r.status_code == 200, "cria a nota do recebimento", r.text[:300])
    n = r.json()
    checar(n["centavos"] == 500000 and n["rascunho"]["tomador"]["nome"] == "Cliente do Recebimento"
           and n["competencia"] == "2026-09-30", "valor, tomador e competência vêm do recebimento",
           (n["centavos"], n["rascunho"]["tomador"].get("nome"), n["competencia"]))
    checar(not n["erros"], "sem erros", n["erros"])
    checar(any(l["chave"] == "irrf" and l["centavos"] == -7500 for l in n["conta"]["linhas"]),
           "a conta mostra o IRRF com a regra", [l for l in n["conta"]["linhas"] if l["chave"] == "irrf"])
    r = local.post(f"/api/nfse/notas/{n['id']}", json={"dados": {"valor": "4.000,00"}})
    n = r.json()
    checar(any("diferente do recebimento" in a for a in n["avisos"]), "valor diferente do recebimento vira aviso", n["avisos"])
    r = local.get(f"/api/nfse/notas/{n['id']}/dps")
    checar(r.status_code == 200 and "<vServ>4000.00</vServ>" in r.json()["xml"] and r.json()["previa"],
           "a prévia da DPS sai com o valor editado", r.text[:200])
    r = local.get(f"/api/nfse/notas/{n['id']}")
    checar(len(r.json()["passos"]) >= 2, "os passos ficam registrados", len(r.json()["passos"]))
    r = local.post(f"/api/nfse/notas/{n['id']}/descartar")
    checar(r.status_code == 200 and r.json()["estado"] == "descartada", "rascunho se descarta", r.text[:200])
    r = local.post(f"/api/nfse/notas/{n['id']}", json={"dados": {"valor": "1,00"}})
    checar(r.status_code == 400, "nota descartada não se edita", r.status_code)
    from fastapi.testclient import TestClient as TC

    r = TC(api.app).get("/api/nfse/notas")
    checar(r.status_code in (401, 403), "de fora, sem a chave da janela, não lê as notas", r.status_code)


def test_sem_float() -> None:
    print("\nnenhum float no caminho do dinheiro da nota")
    import inspect

    from nfse import conferencia, dinheiro, dps, notas, numeracao, prestador, tributos

    for mod in (dinheiro, tributos, dps, notas, numeracao, prestador, conferencia):
        fonte = inspect.getsource(mod)
        checar("float(" not in fonte and "round(" not in fonte, f"{mod.__name__}: sem float( nem round(")


def main() -> int:
    try:
        test_referencia()
        test_sem_float()
        import api

        test_numeracao(api)
        test_obrigatorios(api)
        test_cartao_pela_rota(api)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    if falhas:
        print(f"\n{len(falhas)} falha(s): {falhas}")
        return 1
    print("\ntodos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
