"""
Teste da N8 do emissor de NFS-e — a liberação da produção.

(A N8 não tem portão próprio no prompt: o portão é o teste real do dono. Este
teste mede o que o código garante antes dele.)

  - o checklist trava a liberação até todos os itens: revisão do contador, 5
    notas em produção restrita conferidas, certificado válido, município com
    convênio e backup configurado;
  - liberar grava quem e quando, muda o ambiente e vai para a auditoria; o
    cliente passa a falar com os endereços de produção;
  - a primeira nota de produção pede a confirmação "Esta nota vale de verdade";
  - voltar para produção restrita tranca de novo;
  - de fora, nada disso se alcança.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_n8_producao.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-n8-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
os.environ["PAULUS_NFSE_SEM_FILA"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

from _nfse_comum import CNPJ_PRESTADOR, CNPJ_TOMADOR, GOIANIA, certificado_a1, checar, falhas, sessoes_de_fora  # noqa: E402

SENHA = "senha-do-a1-n8"


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
    for amb in ("producao_restrita", "producao"):
        api.estado.base.escrever("INSERT OR REPLACE INTO nfse_municipio (cmun, ambiente, situacao, consultado_em) "
                                 "VALUES (?, ?, 'conveniado', datetime('now'))", (GOIANIA, amb))
    certificado_a1(TMP / "sefin.pfx", senha="sefin", nome="SEFIN NACIONAL TESTE")
    s = SefinSimulada(TMP / "sefin.json", "sucesso", (TMP / "sefin.pfx").read_bytes(), "sefin")
    e.transporte = s
    return s, api.estado.cadastros.salvar({"nome": "ACME Ltda", "documento": CNPJ_TOMADOR, "end_logradouro": "Rua 1",
                                           "end_numero": "10", "end_bairro": "Centro", "end_cep": "74000000", "end_cmun": GOIANIA})


def emitir(api, local, cid, confirmar=False):
    n = local.post("/api/nfse/notas", json={"origem": "teste", "dados": {"cadastro_id": cid, "valor": "100,00"}}).json()
    r = local.post(f"/api/nfse/notas/{n['id']}/pedir-aprovacao", json={"confirmou_producao": confirmar})
    if r.status_code != 200:
        return n, r
    pedido = next(p for p in api.estado.fila.pendentes if p.acao == "nfse.emitir" and p.dados.get("nota_id") == n["id"])
    local.post("/api/aprovacoes/decidir", json={"ids": [pedido.id], "aprovar": True})
    return api.estado.nfse.notas.obter(n["id"]), r


def main() -> int:
    try:
        import api
        from fastapi.testclient import TestClient

        local = TestClient(api.app, headers=api.cabecalho_local())
        s, cid = preparar(api)
        e = api.estado.nfse

        print("\no checklist trava a liberação")
        ch = local.get("/api/nfse/producao").json()
        checar(not ch["pode_liberar"] and not ch["liberada"], "de início, não dá para liberar")
        r = local.post("/api/nfse/producao/liberar", json={"confirmo": True})
        checar(r.status_code == 400 and "falta no checklist" in r.json()["detail"], "liberar sem o checklist é recusado", r.text[:200])
        for _ in range(5):
            emitir(api, local, cid)
        ch = local.get("/api/nfse/producao").json()
        testes = next(i for i in ch["itens"] if i["id"] == "testes")
        checar(not testes["ok"] and "5 emitida(s)" in testes["detalhe"], "5 emitidas, mas falta marcar que foram conferidas", testes)
        local.post("/api/nfse/producao/testes-conferidos", json={"por": "Dra. Ana"})
        local.post("/api/nfse/producao/revisado", json={"por": "Carla Contadora"})
        ch = local.get("/api/nfse/producao").json()
        falta = [i["id"] for i in ch["itens"] if not i["ok"]]
        checar(falta == ["backup"], "só falta o backup", falta)
        api.estado.prefs.dados["backup"]["pasta"] = str(TMP / "bk")
        api.estado.prefs.dados["backup"]["senha"] = "x"
        ch = local.get("/api/nfse/producao").json()
        checar(ch["pode_liberar"], "checklist completo")
        r = local.post("/api/nfse/producao/liberar", json={"confirmo": False})
        checar(r.status_code == 400, "sem a confirmação, não libera")
        checar(not e.producao_liberada() and e.ambiente == "producao_restrita", "ainda em produção restrita")
        checar(not any("sefin.nfse.gov.br" in u and "producaorestrita" not in u for _, u in s.pedidos),
               "até aqui, nenhum pedido a endereço de produção", [u for _, u in s.pedidos][:3])

        print("\nliberar")
        r = local.post("/api/nfse/producao/liberar", json={"confirmo": True})
        checar(r.status_code == 200 and r.json()["liberada"], "liberada", r.text[:200])
        lib = e.liberacao()
        checar(lib and lib["liberado_por"].startswith("titular") and "revisado" in lib["checklist"], "quem, quando e o checklist gravados")
        checar(e.ambiente == "producao", "o ambiente da configuração é produção")
        hist = e.prestador.historico()
        checar(hist[0]["motivo"] == "produção liberada pelo titular", "o histórico da configuração registra", hist[0])

        print("\na primeira nota de produção pede a confirmação a mais")
        n, r = emitir(api, local, cid)
        checar(r.status_code == 409 and r.json()["detail"] == "Esta nota vale de verdade. Conferiu os dados?",
               "sem confirmar: 409 com a frase", r.text[:200])
        r = local.post(f"/api/nfse/notas/{n['id']}/pedir-aprovacao", json={"confirmou_producao": True})
        checar(r.status_code == 200, "confirmada, vai para Aprovações", r.text[:200])
        pedido = next(p for p in api.estado.fila.pendentes if p.acao == "nfse.emitir" and p.dados.get("nota_id") == n["id"])
        checar("PRODUÇÃO (vale de verdade)" in pedido.resumo and "produção" in pedido.etiquetas, "a aprovação diz que é produção")
        local.post("/api/aprovacoes/decidir", json={"ids": [pedido.id], "aprovar": True})
        n = e.notas.obter(n["id"])
        checar(n["estado"] == "emitida" and n["ambiente"] == "producao", "emitida em produção", (n["estado"], n["ultimo_erro"]))
        checar(any("sefin.nfse.gov.br/SefinNacional" in u for _, u in s.pedidos), "o envio foi ao endereço de produção")
        dps = Path(n["xml_dps"]).read_text(encoding="utf-8")
        checar("<tpAmb>1</tpAmb>" in dps, "a DPS diz tpAmb 1 (produção)")
        n2, r = emitir(api, local, cid)
        checar(r.status_code == 200 and n2["estado"] == "emitida", "a segunda já não pede a confirmação a mais", r.status_code)

        print("\nvoltar para produção restrita")
        r = local.post("/api/nfse/producao/voltar")
        checar(r.status_code == 200 and not r.json()["liberada"] and e.ambiente == "producao_restrita", "voltou", r.text[:200])
        checar(not e.producao_liberada(), "a produção está trancada de novo")
        from nfse.cliente import ProducaoBloqueada

        rasc = local.post("/api/nfse/notas", json={"origem": "teste", "dados": {"cadastro_id": cid, "valor": "100,00"}}).json()
        api.estado.base.escrever("UPDATE nfse_notas SET ambiente = 'producao', estado = 'aprovada' WHERE id = ?", (rasc["id"],))
        try:
            e.envio.emitir(rasc["id"], "teste")
            checar(False, "nota de produção não sai depois de voltar")
        except ProducaoBloqueada:
            checar(True, "nota de produção não sai depois de voltar")
        aud = Path(api.estado.acesso_de_fora.auditoria.caminho).read_text(encoding="utf-8")
        checar("liberou a PRODUÇÃO" in aud and "voltou a NFS-e para a produção restrita" in aud, "liberar e voltar na auditoria")

        print("\nde fora não se alcança")
        sessoes = sessoes_de_fora(api)
        if sessoes:
            titular, _ = sessoes
            r = titular.post("/api/nfse/producao/liberar", json={"confirmo": True})
            checar(r.status_code == 403, "titular de fora não libera produção", r.status_code)
        else:
            print("  pulado: sem DPAPI")
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    if falhas:
        print(f"\n{len(falhas)} falha(s): {falhas}")
        return 1
    print("\ntodos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
