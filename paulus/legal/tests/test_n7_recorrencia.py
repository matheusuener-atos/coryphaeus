"""
Portão da N7 do emissor de NFS-e — honorários recorrentes e avisos.

  - no dia X, o rascunho aparece em Aprovações; antes do dia, nada; nada é
    emitido sem aprovação; um por mês (rodar de novo não duplica);
  - cliente sem endereço: o rascunho espera, com aviso, e não vai a Aprovações;
  - os avisos aparecem uma vez cada, com o id estável do carrossel: rascunho do
    mês, certificado a 30, 7 e 1 dia, fila parada, parâmetros do município que
    mudaram e esquema novo no portal; marcado como visto, não volta.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_n7_recorrencia.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-n7-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
os.environ["PAULUS_NFSE_SEM_FILA"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

from _nfse_comum import CNPJ_PRESTADOR, CNPJ_TOMADOR, GOIANIA, certificado_a1, checar, falhas  # noqa: E402

SENHA = "senha-do-a1-n7"
HOJE = date(2026, 10, 5)


def preparar(api):
    from _sefin_simulada import SefinSimulada

    e = api.estado.nfse
    e.ligar(True)
    e.prestador.gravar({
        "documento": CNPJ_PRESTADOR, "razao_social": "Escritório de Teste", "inscricao_municipal": "123456",
        "municipio": GOIANIA, "opcao_simples": "1",
        "servico": {"ctribnac": "171401", "nbs": "113012000", "descricao": "Honorários advocatícios", "aliquota_iss_pct": "5"},
        "retencoes": {k: {"quando": "nunca"} for k in ("irrf", "pis", "cofins", "csll", "cp", "iss")},
        "ibscbs": {"enviar": True, "cst": "200", "cclasstrib": "200052", "cindop": "100301"},
    }, quem="teste")
    certificado_a1(TMP / "a1.pfx", senha=SENHA)
    e.instalar_certificado("a1.pfx", (TMP / "a1.pfx").read_bytes(), SENHA, True)
    api.estado.base.escrever("INSERT OR REPLACE INTO nfse_municipio (cmun, ambiente, situacao, consultado_em) "
                             "VALUES (?, 'producao_restrita', 'conveniado', datetime('now'))", (GOIANIA,))
    certificado_a1(TMP / "sefin.pfx", senha="sefin", nome="SEFIN NACIONAL TESTE")
    s = SefinSimulada(TMP / "sefin.json", "sucesso", (TMP / "sefin.pfx").read_bytes(), "sefin")
    e.transporte = s
    return s


def ids_nfse(api, hoje) -> list[str]:
    return [a["id"] for a in api.estado.central_avisos.do_dia("local", hoje=hoje) if a["id"].startswith("nfse:")]


def main() -> int:
    try:
        import api
        from fastapi.testclient import TestClient

        local = TestClient(api.app, headers=api.cabecalho_local())
        s = preparar(api)
        e = api.estado.nfse
        cid = api.estado.cadastros.salvar({"nome": "ACME Ltda", "documento": CNPJ_TOMADOR, "end_logradouro": "Rua 1",
                                           "end_numero": "10", "end_bairro": "Centro", "end_cep": "74000000", "end_cmun": GOIANIA})
        sid = api.estado.servicos.salvar({"nome": "Assessoria mensal ACME", "cadastro_id": cid})
        sem_end = api.estado.cadastros.salvar({"nome": "Beta Sem Endereço Ltda", "documento": "11444777000161"})

        print("\nhonorários recorrentes: no dia, o rascunho em Aprovações; nada emitido")
        r = local.post("/api/nfse/recorrencias", json={"servico_id": sid, "dia": 5, "valor": "5.000,00"})
        checar(r.status_code == 200 and r.json()["recorrencia"]["centavos"] == 500000, "recorrência do Serviço: dia 5, R$ 5.000,00", r.text[:200])
        local.post("/api/nfse/recorrencias", json={"cadastro_id": sem_end, "dia": 5, "valor": "1.000,00"})
        r = local.post("/api/nfse/recorrencias", json={"cadastro_id": cid, "dia": 0, "valor": "10,00"})
        checar(r.status_code == 400, "dia fora de 1 a 31 é recusado")
        checar(e.recorrencias.rodar(api.estado, date(2026, 10, 4)) == [], "dia 4: nada ainda")
        feitas = e.recorrencias.rodar(api.estado, HOJE)
        checar(len(feitas) == 2, "dia 5: um rascunho por recorrência", feitas)
        boa = next(f for f in feitas if not f["erros"])
        nota = e.notas.obter(boa["nota_id"])
        checar(nota["estado"] == "aguardando_aprovacao" and nota["origem"] == "recorrencia" and nota["recorrencia_id"],
               "o rascunho completo vai para Aprovações", nota["estado"])
        checar(nota["competencia"] == "2026-10-01" and "outubro/2026" in nota["rascunho"]["descricao"]
               and nota["rascunho"]["tomador"]["nome"] == "ACME Ltda", "do mês, com o cliente do Serviço", nota["rascunho"]["descricao"])
        checar(any(p.acao == "nfse.emitir" and p.dados["nota_id"] == nota["id"] for p in api.estado.fila.pendentes),
               "o pedido está na fila de Aprovações")
        checar(not s.pedidos and not s.geradas(), "nada foi ao Sistema Nacional", s.pedidos)
        ruim = next(f for f in feitas if f["erros"])
        checar(e.notas.obter(ruim["nota_id"])["estado"] == "rascunho" and any("endereço" in x for x in ruim["erros"]),
               "cliente sem endereço: o rascunho espera por você", ruim["erros"])
        checar(e.recorrencias.rodar(api.estado, HOJE) == [] and e.recorrencias.rodar(api.estado, date(2026, 10, 20)) == [],
               "rodar de novo no mês não duplica")
        checar(e.recorrencias.dia_efetivo(31, date(2027, 2, 10)) == 28, "dia 31 em fevereiro vale o último dia")
        checar(len(e.recorrencias.rodar(api.estado, date(2026, 11, 5))) == 2, "no mês seguinte, de novo")

        print("\navisos: uma vez cada, com id estável")
        ids = ids_nfse(api, HOJE)
        rec_ids = [i for i in ids if i.startswith("nfse:recorrencia:")]
        checar(len(rec_ids) == 2 and len(set(ids)) == len(ids), "os dois rascunhos do mês no carrossel, sem duplicar", ids)
        checar(ids == ids_nfse(api, HOJE), "o mesmo id nas duas coletas (estável)")
        api.estado.central_avisos.marcar(rec_ids[0], "local", hoje=HOJE)
        checar(rec_ids[0] not in ids_nfse(api, HOJE), "marcado como visto, não volta")

        for dias, faixa in ((20, 30), (5, 7), (1, 1)):
            certificado_a1(TMP / f"c{dias}.pfx", senha=SENHA, dias=dias)
            e.instalar_certificado(f"c{dias}.pfx", (TMP / f"c{dias}.pfx").read_bytes(), SENHA, True)
            cert_ids = [i for i in ids_nfse(api, HOJE) if i.startswith("nfse:certificado:")]
            checar(len(cert_ids) == 1 and cert_ids[0].startswith(f"nfse:certificado:{faixa}:"),
                   f"certificado a {dias} dia(s): o aviso da faixa de {faixa}", cert_ids)
            api.estado.central_avisos.marcar(cert_ids[0], "local", hoje=HOJE)
            checar(not [i for i in ids_nfse(api, HOJE) if i.startswith(f"nfse:certificado:{faixa}:")],
                   f"visto, o de {faixa} dia(s) não volta")

        n = e.notas.obter(boa["nota_id"])
        api.estado.base.escrever("UPDATE nfse_notas SET estado = 'na_fila', esperas = 3, ultimo_erro = 'sem rede' WHERE id = ?", (n["id"],))
        checar(f"nfse:fila_parada:{n['id']}" in ids_nfse(api, HOJE), "fila de envio parada (3 esperas)")

        from _nfse_comum import GOIANIA as G
        from nfse.cliente import Resposta

        e.transporte = lambda m, u, c: Resposta(200, {"situacaoConvenio": "Ativo", "prazoCancelamentoDias": 30, "aliquotaIss": "5.00"})
        e.consultar_municipio()
        checar(not [i for i in ids_nfse(api, HOJE) if i.startswith("nfse:municipio:")], "primeira consulta: nada mudou")
        e.transporte = lambda m, u, c: Resposta(200, {"situacaoConvenio": "Ativo", "prazoCancelamentoDias": 10, "aliquotaIss": "4.00"})
        e.consultar_municipio()
        mun = [a for a in api.estado.central_avisos.do_dia("local", hoje=HOJE) if a["id"].startswith(f"nfse:municipio:{G}:")]
        checar(len(mun) == 1 and "prazo de cancelamento: 30 para 10" in mun[0]["detalhe"] and "aliquotaiss" in mun[0]["detalhe"],
               "parâmetros do município mudaram: o aviso diz o quê", mun[0]["detalhe"] if mun else None)
        e.transporte = s

        pagina_igual = '<a href="x/nfse-esquemas_xsd-v1-01-20260209.zip">XSD</a>'
        pagina_nova = '<a href="x/nfse-esquemas_xsd-v1-02-20261001.zip">XSD</a>'
        e._rotina_em = ""
        r = e.rotina_diaria(HOJE, baixar=lambda url: pagina_igual)
        checar(r.get("documentacao", {}).get("ok") and not r["documentacao"]["novos"], "documentação conferida: nada novo")
        checar(not [i for i in ids_nfse(api, HOJE) if i.startswith("nfse:layout:")], "sem aviso de esquema novo")
        (e.pasta / "documentacao.json").unlink()
        e._rotina_em = ""
        e.rotina_diaria(date(2026, 10, 6), baixar=lambda url: pagina_nova)
        lay = [i for i in ids_nfse(api, HOJE) if i.startswith("nfse:layout:")]
        checar(lay == ["nfse:layout:nfse-esquemas_xsd-v1-02-20261001.zip"], "esquema novo publicado: um aviso, id pelo arquivo", lay)
        checar(e.rotina_diaria(date(2026, 10, 6), baixar=lambda url: 1 / 0) == {}, "a rotina roda uma vez por dia")
        checar(not s.geradas(), "e em nenhum momento uma nota foi emitida sem aprovação")
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    if falhas:
        print(f"\n{len(falhas)} falha(s): {falhas}")
        return 1
    print("\ntodos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
