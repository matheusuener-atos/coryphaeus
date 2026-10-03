"""
Teste das Notas Admin (src/casa_nfse.py): o emissor do PAVLVS no PAULUS da casa.

  - sem PAULUS_CASA_PAVLVS a tela não existe (404);
  - o emissor é separado do do escritório (banco, certificado, configuração);
  - certificado numa linha, parâmetros, chave da ponte cifrada;
  - testar a comunicação: certificado, Sefin e a ponte com o painel;
  - clientes e edição pela ponte; emitir pelo pop-up (com erro de conferência
    dito), PDF, XML, enviar ao app do cliente, envio sozinho;
  - produção só depois de uma nota no ambiente de testes;
  - pelo túnel: o titular entra, o colaborador não.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_casa_nfse.py
"""

from __future__ import annotations

import base64
import os
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-casa-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
os.environ["PAULUS_NFSE_SEM_FILA"] = "1"
os.environ.pop("PAULUS_CASA_PAVLVS", None)
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

from _nfse_comum import CNPJ_PRESTADOR, CNPJ_TOMADOR, GOIANIA, certificado_a1, checar, falhas, sessoes_de_fora  # noqa: E402

SENHA = "senha-do-a1-pavlvs"


class WorkerFalso:
    def __init__(self) -> None:
        self.notas: list[dict] = []
        self.canceladas: list[tuple] = []
        self.config = {"auto": False, "email": False}
        self.pagamentos = [{"id": "p1", "conta": "c1", "cliente": "ACME Advogados", "tipo": "mensalidade",
                            "valor": 300, "nota": "pendente", "quando": "2026-09-05T10:00:00Z"}]
        self.tomadores = {"c1": {"nome": "ACME Advogados", "documento": CNPJ_TOMADOR, "email": "acme@exemplo.com.br",
                                 "logradouro": "Rua 1", "numero": "10", "bairro": "Centro", "cep": "74000000", "cmun": GOIANIA}}

    def __call__(self, metodo, caminho, corpo):
        if caminho == "/api/nfse-casa/ping":
            return 200, {"ok": True, "contas": len(self.tomadores)}
        if caminho == "/api/nfse-casa/clientes":
            return 200, {"clientes": [{"id": k, "nome": v["nome"], "tomador": v} for k, v in self.tomadores.items()]}
        if caminho.startswith("/api/nfse-casa/clientes/"):
            k = caminho.rsplit("/", 1)[1]
            if k not in self.tomadores:
                return 404, {"erro": "conta não encontrada"}
            self.tomadores[k].update(corpo["tomador"])
            return 200, {"cliente": {"id": k, "tomador": self.tomadores[k]}}
        if caminho == "/api/nfse-casa/pagamentos":
            return 200, {"pagamentos": self.pagamentos, "config": self.config}
        if caminho == "/api/nfse-casa/notas":
            self.notas.append(corpo)
            return 200, {"ok": True, "email": "enviado" if corpo.get("email") else ""}
        if caminho.startswith("/api/nfse-casa/notas/") and caminho.endswith("/cancelada"):
            self.canceladas.append((caminho.split("/")[4], corpo))
            return 200, {"ok": True}
        return 404, {"erro": "rota não existe"}


def main() -> int:
    try:
        import api
        from fastapi.testclient import TestClient
        from _sefin_simulada import SefinSimulada

        local = TestClient(api.app, headers=api.cabecalho_local())

        print("\nsó no PAULUS da casa, sozinho (a nuvem diz se a conta é da equipe)")
        import casa_nfse

        checar(local.get("/api/casa-nfse").status_code == 404, "sem conta da assinatura, a tela não existe")
        checar(local.get("/api/casa-nfse/disponivel").json() == {"ligada": False}, "disponível diz que não")
        perguntas = []
        resposta = {"status": 403, "dados": {"erro": "esta conta do PAULUS não é da equipe do painel (dono ou financeiro)"}}

        def perguntar(segredo):
            perguntas.append(segredo)
            return resposta["status"], resposta["dados"]

        casa_nfse.PERGUNTAR["fn"] = perguntar
        casa_nfse._segredo = lambda estado: "pia_cliente_qualquer"
        checar(local.get("/api/casa-nfse/disponivel").json() == {"ligada": False} and perguntas == ["pia_cliente_qualquer"],
               "conta de cliente: a nuvem diz que não, e a tela não aparece")
        local.get("/api/casa-nfse/disponivel")
        checar(len(perguntas) == 1, "a resposta fica guardada (não pergunta a cada clique)")
        casa_nfse._segredo = lambda estado: "pia_do_dono"
        resposta.update(status=200, dados={"ok": True, "email": "dono@pavlvs.com.br", "papel": "dono"})
        checar(local.get("/api/casa-nfse/disponivel").json() == {"ligada": True}, "conta da equipe: aparece sozinha, sem chave")
        r = local.get("/api/casa-nfse")
        checar(r.status_code == 200, "e a tela abre", r.text[:200])
        casa = api.estado.casa_nfse
        checar(casa._segredo() == "pia_do_dono", "a ponte usa o segredo da instalação, o mesmo da nuvem")
        w = WorkerFalso()
        casa.ponte_local = w

        print("\nseparado do emissor do escritório")
        checar(casa.base.caminho != api.estado.base.caminho and casa.emissor is not api.estado.nfse, "banco e emissor próprios")

        print("\ncertificado numa linha e parâmetros")
        certificado_a1(TMP / "a1.pfx", senha=SENHA, nome="PAVLVS TECNOLOGIA LTDA")
        r = local.post("/api/casa-nfse/certificado", files={"arquivo": ("a1.pfx", (TMP / "a1.pfx").read_bytes())}, data={"senha": "errada"})
        checar(r.status_code == 400, "senha errada é recusada", r.status_code)
        r = local.post("/api/casa-nfse/certificado", files={"arquivo": ("a1.pfx", (TMP / "a1.pfx").read_bytes())}, data={"senha": SENHA})
        t = r.json()
        checar(r.status_code == 200 and t["certificado"]["instalado"], "certificado instalado", r.text[:200])
        checar(t["prestador"]["dados"]["documento"] == CNPJ_PRESTADOR and "PAVLVS" in t["prestador"]["dados"]["razao_social"],
               "CNPJ e nome vieram do certificado", t["prestador"]["dados"].get("razao_social"))
        checar(not api.estado.nfse.cofre.instalado and not api.estado.nfse.prestador.atual()["dados"]["documento"],
               "o emissor do escritório não foi tocado")
        r = local.post("/api/casa-nfse/parametros", json={"enviar_sozinho": False, "prestador": {
            "inscricao_municipal": "998877", "municipio": GOIANIA, "opcao_simples": "1",
            "endereco": {"logradouro": "Rua 2", "numero": "5", "bairro": "Centro", "cep": "74000000"},
            "servico": {"ctribnac": "171401", "nbs": "113012000", "descricao": "Assinatura do PAULUS", "aliquota_iss_pct": "5"},
            "retencoes": {k: {"quando": "nunca"} for k in ("irrf", "pis", "cofins", "csll", "cp", "iss")},
            "ibscbs": {"enviar": True, "cst": "200", "cclasstrib": "200052", "cindop": "100301"}}})
        checar(r.status_code == 200 and not r.json()["prestador"]["faltas"], "parâmetros gravados, sem faltas", r.text[:300])
        casa.base.escrever("INSERT OR REPLACE INTO nfse_municipio (cmun, ambiente, situacao, consultado_em) "
                           "VALUES (?, 'producao_restrita', 'conveniado', datetime('now'))", (GOIANIA,))
        certificado_a1(TMP / "sefin.pfx", senha="sefin", nome="SEFIN NACIONAL TESTE")
        s = SefinSimulada(TMP / "sefin.json", "sucesso", (TMP / "sefin.pfx").read_bytes(), "sefin")
        casa.emissor.transporte = s

        print("\ntestar a comunicação")
        r = local.post("/api/casa-nfse/testar").json()
        nomes = {e["titulo"]: e["ok"] for e in r["etapas"]}
        checar(nomes.get("Certificado instalado e válido") and nomes.get("Ponte com o painel (paulus.ia.br)"),
               "certificado e ponte ok", r["etapas"])
        checar("Servidor da Sefin (Sistema Nacional)" in nomes, "a Sefin foi chamada com o certificado", r["etapas"])

        print("\nclientes pela ponte")
        cl = local.get("/api/casa-nfse/clientes").json()["clientes"]
        checar(cl and cl[0]["tomador"]["documento"] == CNPJ_TOMADOR, "lista vem do Worker")
        r = local.post("/api/casa-nfse/clientes/c1", json={"tomador": {"email": "financeiro@acme.com.br"}})
        checar(r.status_code == 200 and w.tomadores["c1"]["email"] == "financeiro@acme.com.br", "edição chega ao Worker")
        checar(local.post("/api/casa-nfse/clientes/xx", json={"tomador": {}}).status_code == 400, "conta que não existe: a frase do Worker")
        checar(len(local.get("/api/casa-nfse/pagamentos").json()["pagamentos"]) == 1, "pagamentos pela ponte")

        print("\nemitir")
        tom = dict(w.tomadores["c1"])
        r = local.post("/api/casa-nfse/emitir", json={"conta": "c1", "tomador": {**tom, "documento": "123"}, "valor": "300,00",
                                                     "descricao": "Assinatura do PAULUS — setembro/2026"})
        checar(r.status_code == 400 and "tomador" in r.json()["detail"], "documento ruim: a conferência diz", r.text[:200])
        r = local.post("/api/casa-nfse/producao/liberar")
        checar(r.status_code == 400 and "ambiente de testes" in r.json()["detail"], "produção só depois de uma nota de teste", r.text[:200])
        r = local.post("/api/casa-nfse/emitir", json={"conta": "c1", "pagamento": "p1", "tomador": tom, "valor": "300,00",
                                                     "descricao": "Assinatura do PAULUS — setembro/2026", "competencia": "2026-09-01"})
        n = r.json()
        checar(r.status_code == 200 and n["estado"] == "emitida" and n["numero"], "emitida", r.text[:300])
        checar(not api.estado.fila.pendentes or not any(p.acao == "nfse.emitir" for p in api.estado.fila.pendentes),
               "sem fila de Aprovações")
        t = local.get("/api/casa-nfse").json()
        checar([x["id"] for x in t["notas"]] == [n["id"]], "a nota aparece na lista (sem o rascunho descartado)", t["notas"])
        pdf = local.get(f"/api/casa-nfse/notas/{n['id']}/pdf")
        checar(pdf.status_code == 200 and pdf.content[:4] == b"%PDF" and "inline" in pdf.headers["content-disposition"], "PDF para imprimir")
        checar("attachment" in local.get(f"/api/casa-nfse/notas/{n['id']}/pdf?baixar=1").headers["content-disposition"], "PDF para baixar")
        xml = local.get(f"/api/casa-nfse/notas/{n['id']}/xml")
        checar(xml.status_code == 200 and b"<NFSe" in xml.content, "XML")

        print("\nenviar ao app do cliente")
        r = local.post(f"/api/casa-nfse/notas/{n['id']}/enviar")
        checar(r.status_code == 200 and r.json()["enviada_em"], "enviada", r.text[:200])
        env = w.notas[-1]
        checar(env["conta"] == "c1" and env["pagamento"] == "p1" and env["competencia"] == "2026-09"
               and base64.b64decode(env["pdf_b64"])[:4] == b"%PDF" and env["valor"] == 300.0, "o Worker recebe conta, pagamento, PDF e XML")
        local.post("/api/casa-nfse/parametros", json={"enviar_sozinho": True})
        antes = len(w.notas)
        n2 = local.post("/api/casa-nfse/emitir", json={"conta": "c1", "tomador": tom, "valor": "25,00", "descricao": "Recarga"}).json()
        checar(n2["estado"] == "emitida" and len(w.notas) == antes + 1, "ligado, vai sozinho depois de emitir")
        n3 = local.post("/api/casa-nfse/emitir", json={"tomador": tom, "valor": "10,00", "descricao": "Avulsa"}).json()
        r = local.post(f"/api/casa-nfse/notas/{n3['id']}/enviar")
        checar(r.status_code == 400 and "conta" in r.json()["detail"], "sem conta de assinante, não envia (e diz)")

        print("\nemitir ao confirmar o pagamento (interruptores do painel)")
        local.post("/api/casa-nfse/parametros", json={"enviar_sozinho": False})
        w.pagamentos += [{"id": "p2", "conta": "c1", "cliente": "ACME", "tipo": "recarga pix", "valor": 50, "nota": "pendente",
                          "quando": "2026-10-02T10:00:00Z"},
                         {"id": "p3", "conta": "c9", "cliente": "Sem dados", "tipo": "mensalidade", "valor": 150, "nota": "pendente",
                          "quando": "2026-10-02T10:00:00Z"}]
        checar(casa.rodada_automatica() == [], "com o painel desligado, nada sai sozinho")
        w.config = {"auto": True, "email": True}
        antes = len(w.notas)
        feitos = casa.rodada_automatica()
        checar([f["estado"] for f in feitos] == ["emitida"], "só o p2 sai (p1 já tem nota; p3 sem dados fiscais)", feitos)
        checar(len(w.notas) == antes + 1 and w.notas[-1]["pagamento"] == "p2" and w.notas[-1]["competencia"] == "2026-10",
               "com 'enviar ao cliente' ligado no painel, vai ao app", w.notas[-1:])
        auto = casa.prefs.dados["automaticas"]
        checar("dados fiscais" in auto["p3"]["erro"], "o p3 fica anotado com o motivo", auto.get("p3"))
        checar(casa.rodada_automatica() == [], "a segunda rodada não emite de novo")

        print("\ncancelar e substituir")
        alvo = feitos[0]["id"]
        w.config["mail"] = True
        casa.pagamentos()
        r = local.post(f"/api/casa-nfse/notas/{alvo}/cancelar", json={"motivo": "1", "texto": "curto"})
        checar(r.status_code == 400 and "15 a 255" in r.json()["detail"], "motivo curto é recusado", r.text[:200])
        r = local.post(f"/api/casa-nfse/notas/{alvo}/cancelar", json={"motivo": "1", "texto": "Valor da recarga lançado em duplicidade"})
        checar(r.status_code == 200 and r.json()["estado"] == "cancelada", "cancelada no Sistema Nacional", r.text[:300])
        checar(w.canceladas and w.canceladas[-1][0] == str(alvo) and w.canceladas[-1][1]["email"] is True,
               "o Worker é avisado (com o e-mail ligado no painel)", w.canceladas[-1:])
        checar(local.post(f"/api/casa-nfse/notas/{alvo}/cancelar", json={"motivo": "1", "texto": "Valor da recarga lançado em duplicidade"}).status_code == 400,
               "cancelar de novo é recusado")
        antes = len(w.notas)
        r = local.post(f"/api/casa-nfse/notas/{n['id']}/substituir", json={
            "motivo": "01", "texto": "", "ajustes": {"valor": "320,00", "descricao": "Assinatura do PAULUS — setembro/2026 (corrigida)"}})
        sub = r.json()
        checar(r.status_code == 200 and sub["estado"] == "emitida" and sub["valor"] == "R$ 320,00", "a substituta sai com o valor corrigido", r.text[:300])
        orig = casa.emissor.notas.obter(n["id"])
        checar(orig["estado"] == "substituida", "a original fica substituída", orig["estado"])
        checar(w.canceladas[-1][0] == str(n["id"]) and w.canceladas[-1][1].get("substituta", {}).get("numero") == sub["numero"],
               "o Worker sabe que foi substituída, e por qual", w.canceladas[-1:])
        checar(len(w.notas) == antes + 1 and w.notas[-1]["pagamento"] == "p1" and w.notas[-1]["conta"] == "c1",
               "a substituta vai ao app do cliente, ligada ao mesmo pagamento")
        t = local.get("/api/casa-nfse").json()
        checar(any(x["id"] == sub["id"] and x["email"] == "enviado" for x in t["notas"]), "a lista mostra que o e-mail foi")
        checar(local.post(f"/api/casa-nfse/notas/{n['id']}/substituir", json={"motivo": "01"}).status_code == 400,
               "nota já substituída não se substitui de novo")

        print("\nprodução")
        r = local.post("/api/casa-nfse/producao/liberar")
        checar(r.status_code == 200 and r.json()["producao_liberada"] and r.json()["ambiente"] == "producao", "liberada", r.text[:200])
        checar(api.estado.nfse.ambiente == "producao_restrita", "a do escritório continua em testes")
        r = local.post("/api/casa-nfse/producao/voltar")
        checar(not r.json()["producao_liberada"], "voltou para testes")

        print("\npelo túnel")
        sessoes = sessoes_de_fora(api)
        if sessoes:
            titular, colaborador = sessoes
            checar(titular.get("/api/casa-nfse").status_code == 200, "titular de fora entra")
            checar(colaborador.get("/api/casa-nfse").status_code == 403, "colaborador de fora não", colaborador.get("/api/casa-nfse").status_code)
        else:
            print("  pulado: sem DPAPI")
    finally:
        os.environ.pop("PAULUS_CASA_PAVLVS", None)
        shutil.rmtree(TMP, ignore_errors=True)
    if falhas:
        print(f"\n{len(falhas)} falha(s): {falhas}")
        return 1
    print("\ntodos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
