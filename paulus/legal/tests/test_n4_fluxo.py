"""
Portão da N4 do emissor de NFS-e — o fluxo no PAULUS.

  - pela conversa, pelo Financeiro e pelo Serviço, o mesmo cartão (o mesmo
    rascunho, e na tela a mesma função);
  - a nota entra em Aprovações como pedido próprio, com a conta e a DPS à vista;
  - colaborador sem permissão não aprova; com o nível "Emitir nota fiscal", aprova;
  - de fora, sem o código do autenticador recente, não aprova;
  - agente nunca aprova nem emite sozinho (autonomia recusada);
  - emitida: arquivos no Acervo, registro em notas fiscais (chave e ambiente),
    recebimento fora da lista "sem nota", e-mail proposto em Aprovações,
    aviso no carrossel e linha na auditoria;
  - com a chave desligada, a conversa continua só conferindo.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_n4_fluxo.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-n4-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
os.environ["PAULUS_NFSE_SEM_FILA"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

from _nfse_comum import (CNPJ_PRESTADOR, CNPJ_TOMADOR, GOIANIA, certificado_a1, checar, codigo_novo,  # noqa: E402
                         eventos_sse, falhas, sessoes_de_fora)

SENHA = "senha-do-a1-n4"


def preparar(api):
    from _sefin_simulada import SefinSimulada

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
    certificado_a1(TMP / "a1.pfx", senha=SENHA)
    e.instalar_certificado("a1.pfx", (TMP / "a1.pfx").read_bytes(), SENHA, True)
    api.estado.base.escrever("INSERT OR REPLACE INTO nfse_municipio (cmun, ambiente, situacao, consultado_em) "
                             "VALUES (?, 'producao_restrita', 'conveniado', datetime('now'))", (GOIANIA,))
    certificado_a1(TMP / "sefin.pfx", senha="sefin", nome="SEFIN NACIONAL TESTE")
    e.transporte = SefinSimulada(TMP / "sefin.json", "sucesso", (TMP / "sefin.pfx").read_bytes(), "sefin")
    cid = api.estado.cadastros.salvar({"nome": "ACME Ltda", "documento": CNPJ_TOMADOR, "end_logradouro": "Rua 1",
                                       "end_numero": "10", "end_bairro": "Centro", "end_cep": "74000000",
                                       "end_cmun": GOIANIA, "email_nota": "fiscal@acme.com.br"})
    api.estado.contas.salvar_conta({"email": "escritorio@teste.com.br", "nome": "Escritório"})
    return cid


def test_chave_desligada(api, local) -> None:
    print("\ncom a chave desligada, a conversa só confere")
    r = local.post("/api/trabalhos", json={"pedido": "nota desligada"})
    tid = r.json()["id"]
    r = local.post(f"/api/trabalhos/{tid}/perguntar", json={"pergunta": "emita a NFS-e da ACME Ltda de R$ 5.000,00 referente a setembro"})
    p = next((d for t, d in eventos_sse(r.text) if t == "proposta"), {})
    checar(p.get("tipo") == "nota" and p.get("disponivel") is False, "a proposta vem marcada como desligada", p.get("disponivel"))
    r = local.post(f"/api/trabalhos/{tid}/fazer", json={"tipo": "nota", "campos": p.get("campos", {})})
    feito = r.json()
    checar(r.status_code == 200 and feito.get("pendente") and "não está disponível" in feito.get("resumo", ""),
           "confirmar só confere e diz que está desligada", feito.get("resumo"))
    checar(not api.estado.nfse.notas.listar(), "nenhuma nota criada")


def test_portas(api, local, cid) -> dict:
    print("\nas três portas levam ao mesmo cartão")
    api.estado.nfse.ligar(True)
    # 1. conversa
    r = local.post("/api/trabalhos", json={"pedido": "nota pela conversa"})
    tid = r.json()["id"]
    r = local.post(f"/api/trabalhos/{tid}/perguntar", json={"pergunta": "emita a NFS-e da ACME Ltda de R$ 5.000,00 referente a setembro"})
    p = next((d for t, d in eventos_sse(r.text) if t == "proposta"), {})
    checar(p.get("tipo") == "nota" and p.get("disponivel") is True, "ligada: a proposta é de verdade", p.get("disponivel"))
    r = local.post(f"/api/trabalhos/{tid}/fazer", json={"tipo": "nota", "campos": p.get("campos", {})})
    feito = r.json()
    checar(r.status_code == 200 and feito.get("onde") == "nfse" and feito.get("id"), "confirmar cria o rascunho", feito)
    conversa = api.estado.nfse.notas.obter(feito["id"])
    checar(conversa["cadastro_id"] == cid and conversa["centavos"] == 500000 and conversa["competencia"].endswith("-09-01")
           and "setembro" in conversa["rascunho"]["descricao"],
           "tomador dos Cadastros, valor, competência de setembro e descrição", (conversa["cadastro_id"], conversa["competencia"],
                                                                              conversa["rascunho"]["descricao"]))
    checar(conversa["estado"] == "rascunho" and conversa["origem"] == "conversa", "é rascunho: nada foi enviado")
    # 2. Financeiro
    lid = api.estado.financeiro.salvar({"tipo": "recebimento", "descricao": "Honorários de setembro", "centavos": 500000,
                                        "cadastro_id": cid, "vencimento": "2026-09-30"})
    api.estado.financeiro.liquidar(lid, "2026-09-30")
    checar(any(x["id"] == lid for x in api.estado.papeis.a_emitir("2026-09")), "antes: o recebimento está sem nota")
    r = local.post("/api/nfse/notas", json={"origem": "financeiro", "dados": {"lancamento_id": lid}})
    fin = r.json()
    # 3. Serviço
    sid = api.estado.servicos.salvar({"nome": "Ação de cobrança ACME", "cadastro_id": cid})
    r = local.post("/api/nfse/notas", json={"origem": "servico", "dados": {"servico_id": sid, "valor_centavos": 500000}})
    serv = r.json()
    chaves = [set(n.keys()) - {"passos", "eventos"} for n in (conversa, fin, serv)]
    checar(chaves[0] == chaves[1] == chaves[2], "o mesmo cartão: os três rascunhos têm os mesmos campos")
    checar(all(n["rascunho"]["tomador"]["documento"] == CNPJ_TOMADOR for n in (conversa, fin, serv)),
           "o mesmo tomador nos três")
    checar(serv["rascunho"]["tomador"]["nome"] == "ACME Ltda" and serv["servico_id"] == sid, "do Serviço, o cliente do Serviço")
    js = "\n".join((RAIZ / "frontend" / "js" / f).read_text(encoding="utf-8")
                   for f in ("20-financeiro.js", "49-horas.js", "12-telas-e-acervo.js"))
    checar(js.count("novaNotaFiscal(") >= 3 and "abrirNotaFiscal(feito.id)" in js,
           "na tela, as três portas chamam o mesmo cartão (novaNotaFiscal / abrirNotaFiscal)")
    return {"conversa": conversa, "financeiro": fin, "servico": serv, "lancamento": lid}


def test_aprovacao(api, local, notas: dict) -> None:
    print("\nAprovações: pedido próprio; quem pode; de fora pede o código")
    fin = notas["financeiro"]
    r = local.post(f"/api/nfse/notas/{fin['id']}/pedir-aprovacao")
    checar(r.status_code == 200 and r.json()["estado"] == "aguardando_aprovacao", "pedir aprovação", r.text[:300])
    pedido = next(p for p in api.estado.fila.pendentes if p.acao == "nfse.emitir")
    checar(pedido.titulo == "Emitir NFS-e — ACME Ltda — R$ 5.000,00" and pedido.categoria == "fiscal" and not pedido.reversivel,
           "título “Emitir NFS-e — ACME — R$ 5.000,00”, categoria Nota fiscal, sem desfazer", (pedido.titulo, pedido.categoria))
    checar("Valor líquido: R$ 4.925,00" in pedido.resumo and "IRRF retido" in pedido.resumo and "DPS DPS" in pedido.resumo,
           "a aprovação mostra a conta e a DPS resumida", pedido.resumo[:300])
    r = local.post(f"/api/nfse/notas/{fin['id']}", json={"dados": {"valor": "1,00"}})
    checar(r.status_code == 400, "esperando aprovação, a nota não se edita", r.status_code)

    sessoes = sessoes_de_fora(api)
    if not sessoes:
        print("  pulado: sem DPAPI, sem acesso de fora")
    else:
        titular, colab = sessoes
        api.estado.acesso_de_fora.contas.mudar_permissoes(colab.conta_id, {"aprovacoes": "faz", "nfse": "nao"})
        r = colab.post("/api/aprovacoes/decidir", json={"ids": [pedido.id], "aprovar": True, "codigo": codigo_novo(colab)})
        falha = (r.json().get("falhas") or [{}])[0] if r.status_code == 200 else {"motivo": r.text}
        checar(api.estado.fila.obter(pedido.id).estado == "pendente" and "titular ou de quem ele liberou" in falha.get("motivo", ""),
               "colaborador sem o nível de nota fiscal não aprova", r.text[:300])
        r = titular.post("/api/aprovacoes/decidir", json={"ids": [pedido.id], "aprovar": True})
        falha = (r.json().get("falhas") or [{}])[0]
        checar(api.estado.fila.obter(pedido.id).estado == "pendente" and "código" in falha.get("motivo", ""),
               "titular de fora sem o código do autenticador não aprova", r.text[:300])
        checar(api.estado.nfse.notas.obter(fin["id"])["estado"] == "aguardando_aprovacao", "e a nota não saiu")
        api.estado.acesso_de_fora.contas.mudar_permissoes(colab.conta_id, {"aprovacoes": "faz", "nfse": "faz"})
        r = colab.post("/api/aprovacoes/decidir", json={"ids": [pedido.id], "aprovar": True, "codigo": codigo_novo(colab)})
        checar(r.status_code == 200 and api.estado.nfse.notas.obter(fin["id"])["estado"] == "emitida",
               "colaborador liberado, com o código: aprova e a nota é emitida", r.text[:400])
        nota = api.estado.nfse.notas.obter(fin["id"])
        checar(nota["aprovado_por"] == "Caio Colaborador", "quem aprovou fica na nota", nota["aprovado_por"])
        return
    # Sem acesso de fora: aprova na janela do escritório.
    r = local.post("/api/aprovacoes/decidir", json={"ids": [pedido.id], "aprovar": True})
    checar(api.estado.nfse.notas.obter(fin["id"])["estado"] == "emitida", "aprovada na janela: emitida", r.text[:300])


def test_depois(api, notas: dict) -> None:
    print("\ndepois de emitida: Acervo, registro, recebimento, e-mail, aviso, auditoria")
    nota = api.estado.nfse.notas.obter(notas["financeiro"]["id"])
    pasta = Path(api.estado.pasta) / "Notas fiscais" / "ACME Ltda"
    arquivos = sorted(p.name for p in pasta.glob("*")) if pasta.exists() else []
    checar(any(a.endswith(".xml") and a.startswith(f"NFS-e {nota['numero_nfse']}") for a in arquivos),
           "o XML da NFS-e no Acervo, em Notas fiscais/ACME Ltda", arquivos)
    papel = api.estado.base.um("SELECT * FROM papeis_fiscais WHERE nfse_nota_id = ?", (nota["id"],))
    checar(papel and papel["chave"] == nota["chave"] and papel["ambiente"] == "producao_restrita"
           and papel["situacao"] == "emitida" and papel["lancamento_id"] == notas["lancamento"],
           "registrada em notas fiscais com situação, chave e ambiente", papel)
    checar(not any(x["id"] == notas["lancamento"] for x in api.estado.papeis.a_emitir("2026-09")),
           "o recebimento sai da lista “sem nota”")
    try:
        api.estado.papeis.apagar(papel["id"])
        checar(False, "a nota emitida pelo PAULUS não sai do registro")
    except ValueError:
        checar(True, "a nota emitida pelo PAULUS não sai do registro")
    email = next((p for p in api.estado.fila.pendentes if p.acao == "correio.enviar" and str(nota["numero_nfse"]) in p.titulo), None)
    checar(email is not None and email.dados.get("para") == "fiscal@acme.com.br" and len(email.dados.get("anexos") or []) >= 1
           and all(Path(a).exists() for a in email.dados["anexos"]),
           "e-mail ao cliente proposto em Aprovações, com os arquivos da nota", email.dados if email else None)
    central = getattr(api.estado, "central_avisos", None)
    if central is not None:
        ids = [a["id"] for a in central.coletar(pessoa="local")]
        checar(f"nfse:emitida:{nota['id']}" in ids, "aviso no carrossel, com id estável", [i for i in ids if i.startswith("nfse")])
        ids2 = [a["id"] for a in central.coletar(pessoa="local")]
        checar(ids2.count(f"nfse:emitida:{nota['id']}") == 1, "uma vez só")
    else:
        print("  pulado: carrossel desligado nesta instalação")
    aud = api.estado.acesso_de_fora.auditoria
    linhas = [json.loads(l) for l in Path(aud.caminho).read_text(encoding="utf-8").splitlines() if l.strip()] \
        if hasattr(aud, "caminho") and Path(aud.caminho).exists() else []
    texto = " ".join(l.get("alvo", "") for l in linhas if l.get("acao") == "nfse")
    checar("pediu a emissão" in texto and f"NFS-e {nota['numero_nfse']} emitida" in texto and "sha256" in texto
           and "aprovada por" in texto, "a auditoria tem quem pediu, quem aprovou e os hashes", texto[:400])
    passos = [p["detalhe"] for p in api.estado.nfse.notas.passos(nota["id"])]
    checar(any("no Acervo" in p for p in passos) and any("e-mail ao cliente proposto" in p for p in passos),
           "os passos da nota contam o que foi feito depois", passos[-5:])


def test_agente(api) -> None:
    print("\nagente nunca aprova nem emite sozinho")
    import agentes
    import ferramentas

    checar(ferramentas.CATALOGO_FERRAMENTAS["emitir_nfse"].get("nunca_sozinha"), "o catálogo marca a NFS-e como nunca sozinha")
    texto = ("---\nnome: Faturador\ndescricao: prepara notas\nquando_usar:\n  exemplos: [emitir nota]\n"
             "ferramentas: [emitir_nfse]\nautonomia: [emitir_nfse]\n---\nPrepare a nota.\n")
    try:
        api.estado.agentes.validar(texto)
        erro = ""
    except agentes.ErroDeAgente as exc:
        erro = str(exc)
    checar("nunca é sozinha" in erro, "AGENTE.md com emitir_nfse na autonomia é recusado", erro)
    from api import EXECUTORES

    checar("nfse.emitir" in EXECUTORES, "só Aprovações executa a emissão (executor nfse.emitir)")


def main() -> int:
    try:
        import api
        from fastapi.testclient import TestClient

        local = TestClient(api.app, headers=api.cabecalho_local())
        cid = preparar(api)
        test_chave_desligada(api, local)
        notas = test_portas(api, local, cid)
        test_aprovacao(api, local, notas)
        test_depois(api, notas)
        test_agente(api)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    if falhas:
        print(f"\n{len(falhas)} falha(s): {falhas}")
        return 1
    print("\ntodos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
