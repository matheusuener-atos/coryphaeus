"""
Portão da N5 do emissor de NFS-e — consultar, cancelar, substituir, DANFSe.

  - cancelar fora do prazo do município é recusado aqui, com a explicação e
    o caminho da substituição;
  - dentro do prazo: Aprovações → evento e101101 (validado no XSD, assinado)
    → nota cancelada, registro "cancelada", recebimento volta a "sem nota";
  - o evento sem resposta segue a regra: consulta antes de pedir de novo
    (tempo esgotado depois de registrar e antes de registrar);
  - a substituição liga as duas notas (a Sefin cancela a antiga, e105102);
    no Simples, tomador, competência e valor não mudam (E0061);
  - "atualizar situação" acha o cancelamento por ofício;
  - o DANFSe abre (PDF de uma página) e confere com o XML.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_n5_eventos.py
"""

from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-n5-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
os.environ["PAULUS_NFSE_SEM_FILA"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

from _nfse_comum import CNPJ_PRESTADOR, CNPJ_TOMADOR, GOIANIA, certificado_a1, checar, falhas  # noqa: E402

SENHA = "senha-do-a1-n5"


def preparar(api):
    from _sefin_simulada import SefinSimulada

    e = api.estado.nfse
    e.ligar(True)
    e.prestador.gravar({
        "documento": CNPJ_PRESTADOR, "razao_social": "Escritório de Teste", "inscricao_municipal": "123456",
        "municipio": GOIANIA, "opcao_simples": "1",
        "servico": {"ctribnac": "171401", "nbs": "113012000", "descricao": "Honorários advocatícios", "aliquota_iss_pct": "5"},
        "retencoes": {"irrf": {"quando": "tomador_pj", "aliquota_pct": "1,5"}, "pis": {"quando": "nunca"},
                      "cofins": {"quando": "nunca"}, "csll": {"quando": "nunca"}, "cp": {"quando": "nunca"},
                      "iss": {"quando": "nunca"}},
        "ibscbs": {"enviar": True, "cst": "200", "cclasstrib": "200052", "cindop": "100301"},
        "total_tributos": {"modo": "percentual", "federal_pct": "13,45", "municipal_pct": "5"},
    }, quem="teste")
    certificado_a1(TMP / "a1.pfx", senha=SENHA)
    e.instalar_certificado("a1.pfx", (TMP / "a1.pfx").read_bytes(), SENHA, True)
    api.estado.base.escrever("INSERT OR REPLACE INTO nfse_municipio (cmun, ambiente, situacao, prazo_cancelamento_dias, "
                             "consultado_em) VALUES (?, 'producao_restrita', 'conveniado', 30, datetime('now'))", (GOIANIA,))
    certificado_a1(TMP / "sefin.pfx", senha="sefin", nome="SEFIN NACIONAL TESTE")
    e.transporte = SefinSimulada(TMP / "sefin.json", "sucesso", (TMP / "sefin.pfx").read_bytes(), "sefin")
    return api.estado.cadastros.salvar({"nome": "ACME Ltda", "documento": CNPJ_TOMADOR, "end_logradouro": "Rua 1",
                                        "end_numero": "10", "end_bairro": "Centro", "end_cep": "74000000",
                                        "end_cmun": GOIANIA, "email_nota": "fiscal@acme.com.br"})


def emitir(api, local, cid, valor: str = "5.000,00") -> dict:
    lid = api.estado.financeiro.salvar({"tipo": "recebimento", "descricao": "Honorários", "centavos": 500000,
                                        "cadastro_id": cid, "vencimento": "2026-09-30"})
    api.estado.financeiro.liquidar(lid, "2026-09-30")
    n = local.post("/api/nfse/notas", json={"origem": "financeiro", "dados": {"lancamento_id": lid, "valor": valor}}).json()
    local.post(f"/api/nfse/notas/{n['id']}/pedir-aprovacao")
    pedido = next(p for p in api.estado.fila.pendentes if p.acao == "nfse.emitir" and p.dados.get("nota_id") == n["id"])
    local.post("/api/aprovacoes/decidir", json={"ids": [pedido.id], "aprovar": True})
    nota = api.estado.nfse.notas.obter(n["id"])
    assert nota["estado"] == "emitida", (nota["estado"], nota["ultimo_erro"])
    return nota


def aprovar_pendente(api, local, acao: str) -> None:
    pedido = next(p for p in api.estado.fila.pendentes if p.acao == acao)
    local.post("/api/aprovacoes/decidir", json={"ids": [pedido.id], "aprovar": True})


def test_prazo(api, local, cid) -> None:
    print("\ncancelar fora do prazo do município é recusado aqui, com o caminho")
    nota = emitir(api, local, cid)
    velha = (date.today() - timedelta(days=60)).isoformat() + "T10:00:00-03:00"
    api.estado.base.escrever("UPDATE nfse_notas SET dh_proc = ? WHERE id = ?", (velha, nota["id"]))
    r = local.post(f"/api/nfse/notas/{nota['id']}/cancelar", json={"motivo": "1", "texto": "Valor digitado errado na nota"})
    checar(r.status_code == 400 and "acabou em" in r.json()["detail"] and "substituta" in r.json()["detail"],
           "fora do prazo: recusa e explica, oferecendo a substituição", r.text[:300])
    checar(not any(p.acao == "nfse.cancelar" for p in api.estado.fila.pendentes), "nada foi para Aprovações")
    r = local.post(f"/api/nfse/notas/{nota['id']}/cancelar", json={"motivo": "7", "texto": "Valor digitado errado na nota"})
    checar(r.status_code == 400 and "tabela oficial" in r.json()["detail"], "motivo fora da tabela oficial é recusado")
    r = local.post(f"/api/nfse/notas/{nota['id']}/cancelar", json={"motivo": "1", "texto": "curto"})
    checar(r.status_code == 400 and "15 a 255" in r.json()["detail"], "descrição curta é recusada (15 a 255)")


def test_cancelar(api, local, cid) -> None:
    print("\ncancelar dentro do prazo: Aprovações, evento, nota cancelada")
    e = api.estado.nfse
    s = e.transporte
    nota = emitir(api, local, cid)
    r = local.post(f"/api/nfse/notas/{nota['id']}/cancelar", json={"motivo": "1", "texto": "Valor digitado errado na nota"})
    checar(r.status_code == 200, "pedido de cancelamento aceito", r.text[:200])
    checar(e.notas.obter(nota["id"])["estado"] == "emitida", "até o sim, a nota continua emitida")
    pedido = next(p for p in api.estado.fila.pendentes if p.acao == "nfse.cancelar")
    checar(pedido.categoria == "fiscal" and not pedido.reversivel and "Motivo: 1" in pedido.resumo, "o pedido mostra o motivo", pedido.resumo[:200])
    aprovar_pendente(api, local, "nfse.cancelar")
    n = e.notas.obter(nota["id"])
    checar(n["estado"] == "cancelada", "depois do sim: nota cancelada", n["estado"])
    ev = e.eventos.da_nota(nota["id"])[-1]
    checar(ev["estado"] == "registrado" and Path(ev["xml_evento"]).exists() and Path(ev["xml_pedido"]).exists(),
           "o pedido e o evento ficam guardados", ev)
    from nfse import assinatura, conferencia

    pedido_xml = Path(ev["xml_pedido"]).read_bytes()
    checar(not conferencia.validar_xsd(pedido_xml, "producao_restrita", "pedRegEvento_v1.01.xsd"),
           "o pedido de evento valida no XSD oficial (com a assinatura)")
    checar(assinatura.verificar(pedido_xml)[0], "e a assinatura do pedido confere")
    papel = api.estado.base.um("SELECT situacao FROM papeis_fiscais WHERE nfse_nota_id = ?", (nota["id"],))
    checar(papel["situacao"] == "cancelada", "registro em notas fiscais: cancelada", papel)
    checar(any(x["id"] == nota["lancamento_id"] for x in api.estado.papeis.a_emitir("2026-09")),
           "o recebimento volta para “sem nota”")
    checar(s.pedidos_de_evento(nota["chave"], "101101") == 1, "um pedido de evento só")


def test_evento_sem_resposta(api, local, cid) -> None:
    print("\nevento sem resposta: consulta antes de pedir de novo")
    e = api.estado.nfse
    s = e.transporte
    nota = emitir(api, local, cid)
    s.modos = ["timeout_depois", "sucesso"]
    local.post(f"/api/nfse/notas/{nota['id']}/cancelar", json={"motivo": "2", "texto": "Serviço não foi prestado ao cliente"})
    aprovar_pendente(api, local, "nfse.cancelar")
    n = e.notas.obter(nota["id"])
    checar(n["estado"] == "cancelada" and s.pedidos_de_evento(nota["chave"], "101101") == 1,
           "depois de registrar sem resposta: a consulta acha, sem pedir de novo", (n["estado"], s.pedidos_de_evento(nota["chave"], "101101")))

    nota = emitir(api, local, cid)
    s.modos = ["timeout_antes", "sucesso"]
    local.post(f"/api/nfse/notas/{nota['id']}/cancelar", json={"motivo": "2", "texto": "Serviço não foi prestado ao cliente"})
    aprovar_pendente(api, local, "nfse.cancelar")
    ev = e.eventos.da_nota(nota["id"])[-1]
    checar(ev["estado"] == "aguardando_confirmacao" and e.notas.obter(nota["id"])["estado"] == "emitida",
           "antes de registrar sem resposta: fica aguardando, a nota continua emitida", ev["estado"])
    ev = e.eventos.enviar(ev["id"], "teste")
    checar(ev["estado"] == "registrado" and e.notas.obter(nota["id"])["estado"] == "cancelada",
           "nova tentativa: consultou (não havia) e pediu de novo; cancelada", ev["estado"])
    checar(len([x for x in s.eventos_de(nota["chave"]) if x["tipo"] == "101101"]) == 1, "um evento só registrado")


def test_substituir(api, local, cid) -> None:
    print("\nsubstituição: nota nova ligada à antiga; a Sefin cancela a antiga")
    e = api.estado.nfse
    s = e.transporte
    s.modos = ["sucesso"]
    original = emitir(api, local, cid)
    r = local.post(f"/api/nfse/notas/{original['id']}/substituir", json={"motivo": "99", "texto": "Descrição do serviço estava errada"})
    checar(r.status_code == 200 and r.json()["estado"] == "rascunho" and r.json()["substitui_id"] == original["id"],
           "cria a substituta como rascunho, ligada à original", r.text[:300])
    nova = r.json()
    checar(nova["rascunho"]["substitui"]["chave"] == original["chave"], "com o grupo subst apontando a chave da original")
    local.post(f"/api/nfse/notas/{nova['id']}", json={"dados": {"descricao": "Honorários advocatícios — consultoria societária"}})
    local.post(f"/api/nfse/notas/{nova['id']}/pedir-aprovacao")
    aprovar_pendente(api, local, "nfse.emitir")
    nova = e.notas.obter(nova["id"])
    orig = e.notas.obter(original["id"])
    checar(nova["estado"] == "emitida" and orig["estado"] == "substituida" and orig["substituida_por_id"] == nova["id"],
           "emitida a nova; a original fica substituída e ligada", (nova["estado"], orig["estado"]))
    dps = Path(nova["xml_dps"]).read_text(encoding="utf-8")
    checar(f"<chSubstda>{original['chave']}</chSubstda>" in dps and "<cMotivo>99</cMotivo>" in dps, "a DPS leva o grupo subst")
    checar(any(x["tipo"] == "105102" for x in s.eventos_de(original["chave"])), "no Sistema Nacional, a antiga tem o e105102")
    papel = api.estado.base.um("SELECT situacao FROM papeis_fiscais WHERE nfse_nota_id = ?", (original["id"],))
    checar(papel["situacao"] == "substituída", "registro da original: substituída", papel)
    r = local.post(f"/api/nfse/notas/{original['id']}/substituir", json={"motivo": "99", "texto": "Outra tentativa de substituir"})
    checar(r.status_code == 400, "a substituída não se substitui de novo", r.status_code)

    # Simples Nacional: tomador, competência e valor não mudam (E0061).
    outra = emitir(api, local, cid)
    e.prestador.gravar({"opcao_simples": "3", "regime_apuracao_sn": "1",
                        "total_tributos": {"modo": "simples", "simples_pct": "6"}}, quem="teste")
    r = local.post(f"/api/nfse/notas/{outra['id']}/substituir", json={"motivo": "99", "texto": "Correção de descrição do serviço"})
    sub = r.json()
    sub = local.post(f"/api/nfse/notas/{sub['id']}", json={"dados": {"valor": "4.000,00"}}).json()
    checar(any("valor do serviço não muda" in x for x in sub["erros"]), "Simples: mudar o valor na substituição bloqueia (E0061)", sub["erros"])
    e.prestador.gravar({"opcao_simples": "1", "total_tributos": {"modo": "percentual"}}, quem="teste")


def test_situacao(api, local, cid) -> None:
    print("\natualizar situação: o cancelamento por ofício aparece")
    from nfse.cliente import gzip_b64

    e = api.estado.nfse
    s = e.transporte
    nota = emitir(api, local, cid)
    r = local.post(f"/api/nfse/notas/{nota['id']}/situacao")
    checar(r.status_code == 200 and r.json()["estado"] == "emitida", "sem eventos: continua emitida", r.text[:200])
    xml = ("<evento xmlns=\"http://www.sped.fazenda.gov.br/nfse\"><infEvento><pedRegEvento><infPedReg>"
           "<e305101><xDesc>Cancelamento de NFS-e por Ofício</xDesc></e305101></infPedReg></pedRegEvento></infEvento></evento>").encode()
    s._registrar_evento(nota["chave"], xml, "305101")
    r = local.post(f"/api/nfse/notas/{nota['id']}/situacao")
    checar(r.json()["estado"] == "cancelada" and any("por ofício" in p["detalhe"] for p in r.json()["passos"]),
           "o município cancelou por ofício: a nota fica cancelada, e o passo diz por quê", r.json()["estado"])
    del gzip_b64


def test_danfse(api, local, cid) -> None:
    print("\no DANFSe abre e confere com o XML")
    from pypdf import PdfReader

    from nfse import danfse

    nota = emitir(api, local, cid)
    r = local.get(f"/api/nfse/notas/{nota['id']}/danfse")
    checar(r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content[:4] == b"%PDF",
           "a rota devolve o PDF", r.status_code)
    leitor = PdfReader(io.BytesIO(r.content))
    checar(len(leitor.pages) == 1, "uma página (NT 008, §2.2)", len(leitor.pages))
    texto = leitor.pages[0].extract_text().replace("\n", " ")
    d = danfse.dados_do_xml(Path(nota["xml_nfse"]).read_bytes())
    for rotulo, valor in (("chave de acesso", nota["chave"]), ("número da NFS-e", nota["numero_nfse"]),
                          ("tomador", "ACME Ltda"), ("valor do serviço", "R$ 5.000,00"),
                          ("valor líquido", d["total"]["liquido"]), ("IRRF", "R$ 75,00"),
                          ("cabeçalho", "DANFSe v2.0"), ("produção restrita", "NFS-e SEM VALIDADE JURÍDICA"),
                          ("código do serviço", "17.14.01"), ("totais aproximados", "Federal 13,45%")):
        checar(valor in texto, f"o DANFSe traz {rotulo} ({valor})", texto[:200] if valor not in texto else None)
    checar(d["total"]["liquido"] == "R$ 4.925,00", "o valor líquido do XML (calculado pela Sefin)", d["total"]["liquido"])
    checar(danfse.url_qr(nota["chave"]) == "https://www.nfse.gov.br/ConsultaPublica/?tpc=1&chave=" + nota["chave"],
           "o QR Code aponta a consulta pública oficial com a chave")
    pasta = Path(api.estado.pasta) / "Notas fiscais" / "ACME Ltda"
    pdfs = list(pasta.glob(f"NFS-e {nota['numero_nfse']} *.pdf"))
    checar(len(pdfs) == 1, "o DANFSe também vai para o Acervo, ao lado do XML", [p.name for p in pasta.glob("*")][:6])
    email = next((p for p in api.estado.fila.pendentes if p.acao == "correio.enviar" and str(nota["numero_nfse"]) in p.titulo), None)
    checar(email and any(a.endswith(".pdf") for a in email.dados["anexos"]) and any(a.endswith(".xml") for a in email.dados["anexos"]),
           "o e-mail proposto leva o PDF e o XML", email.dados["anexos"] if email else None)


def main() -> int:
    try:
        import api
        from fastapi.testclient import TestClient

        local = TestClient(api.app, headers=api.cabecalho_local())
        api.estado.contas.salvar_conta({"email": "escritorio@teste.com.br", "nome": "Escritório"})
        cid = preparar(api)
        test_prazo(api, local, cid)
        test_cancelar(api, local, cid)
        test_evento_sem_resposta(api, local, cid)
        test_substituir(api, local, cid)
        test_situacao(api, local, cid)
        test_danfse(api, local, cid)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    if falhas:
        print(f"\n{len(falhas)} falha(s): {falhas}")
        return 1
    print("\ntodos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
