"""
Portao da E1 do PAULUS de equipe (docs/PLANO-EQUIPE.md) - quem criou.

Os dados continuam do escritorio (todos veem tudo, decisao do dono), mas:

  - a conversa aberta por uma conta de fora guarda {conta_id, nome}; a aberta
    na janela do servidor guarda o nome de "Meus dados" e conta 0;
  - a mensagem da pessoa guarda quem perguntou, e isso volta do disco;
  - o documento e a gravacao guardam quem criou (a migracao 023 existe);
  - o colaborador de fora ve a conversa do outro (dados do escritorio).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_e1_quem_criou.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-e1-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def test_disco() -> None:
    print("\na conversa guarda quem abriu e quem perguntou")
    from jobs import Trabalhos

    pasta = TMP / "trabalhos"
    t = Trabalhos(pasta)
    tr = t.criar("Teste", criado_por={"conta_id": 7, "nome": "Bia"})
    tr.dizer("pessoa", "qual a multa?", quem="Bia")
    tr.dizer("paulus", "10%")
    t.salvar(tr)
    de_novo = Trabalhos(pasta).obter(tr.id)
    checar(de_novo and de_novo.criado_por == {"conta_id": 7, "nome": "Bia"}, "quem abriu volta do disco",
           de_novo and de_novo.criado_por)
    checar(de_novo and de_novo.mensagens[0].quem == "Bia" and de_novo.mensagens[1].quem == "",
           "quem perguntou volta do disco (a resposta nao tem)")


def test_http() -> None:
    print("\nde fora e na janela do servidor")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI (fora do Windows), o acesso de fora fica indisponivel")
        return
    from fastapi.testclient import TestClient

    import api
    from acesso.contas import codigo_totp

    servico = api.estado.acesso_de_fora
    servico.conferir_turnstile = lambda token, ip="": "ok" if token == "ok" else "recusado"
    api.estado.prefs.dados["acesso_remoto"]["ligado"] = True
    api.estado.prefs.dados.setdefault("pessoa", {})["nome"] = "Dra. Ana Servidor"
    local = TestClient(api.app, headers=api.cabecalho_local())
    passo = int(time.time() // 30) - 1

    def conta(nome, email):
        c = servico.contas.criar(nome, email, "colaborador", "senha-forte-" + nome.lower())
        servico.contas.confirmar_totp(c["conta"]["id"], codigo_totp(c["segredo"], passo))
        fora = TestClient(api.app, base_url="https://x.paulus.ia.br", headers={"Cf-Connecting-IP": "200.1.1.1"})
        pend = fora.post("/api/acesso/entrar", json={"email": email, "senha": "senha-forte-" + nome.lower(),
                                                    "turnstile": "ok"}).json()["pendente"]
        r = fora.post("/api/acesso/entrar/codigo", json={"pendente": pend, "codigo": codigo_totp(c["segredo"], passo + 1)})
        fora.headers["X-PAULUS-CSRF"] = r.json()["csrf"]
        return c["conta"]["id"], fora

    try:
        servico.contas.criar("Tita", "tita@x.com", "titular", "senha-da-tita-1")
        bia_id, bia = conta("Bia", "bia@x.com")
        caio_id, caio = conta("Caio", "caio@x.com")

        r = bia.post("/api/trabalhos", json={"pedido": "contrato da ACME"})
        checar(r.status_code == 200 and r.json()["criado_por"] == {"conta_id": bia_id, "nome": "Bia"},
               "conversa aberta de fora: a conta e o nome", r.text[:200])
        tid = r.json()["id"]
        r = local.post("/api/trabalhos", json={"pedido": "outra"})
        checar(r.json()["criado_por"] == {"conta_id": 0, "nome": "Dra. Ana Servidor"},
               "na janela do servidor: o nome de Meus dados, conta 0", r.json()["criado_por"])
        grupos = caio.get("/api/trabalhos").json()["grupos"]
        itens = [t for g in grupos for t in g["trabalhos"]]
        da_bia = next((t for t in itens if t["id"] == tid), None)
        checar(da_bia is not None, "o Caio ve a conversa da Bia (dados do escritorio)")
        checar(da_bia and da_bia["criado_por"]["nome"] == "Bia", "e a lista diz que foi a Bia", da_bia)

        r = bia.post("/api/documentos", json={"titulo": "Minuta da Bia", "tipo": "texto"})
        checar(r.status_code == 200 and r.json().get("criado_por") == "Bia" and r.json().get("criado_por_conta") == bia_id,
               "documento criado de fora: quem criou", r.text[:200])
        docs = local.get("/api/documentos").json()
        docs = docs["documentos"]
        d = next((x for x in docs if x["titulo"] == "Minuta da Bia"), {})
        checar(d.get("criado_por") == "Bia" and d.get("criado_por_conta") == bia_id, "e a lista mostra", d)
        r = local.post("/api/documentos", json={"titulo": "Do servidor", "tipo": "texto"})
        checar(r.json().get("criado_por") == "Dra. Ana Servidor" and r.json().get("criado_por_conta") == 0,
               "documento criado no servidor: o nome de Meus dados")

        colunas = {c["name"] for c in api.estado.base.buscar("PRAGMA table_info(gravacoes)")}
        checar({"criado_por", "criado_por_conta"} <= colunas, "gravacoes tem as colunas de quem criou")
    finally:
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = False
        servico.__dict__.pop("conferir_turnstile", None)


def main() -> int:
    print("=" * 55)
    print("  E1 - quem criou (PAULUS de equipe)")
    print("=" * 55)
    try:
        test_disco()
        test_http()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
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
