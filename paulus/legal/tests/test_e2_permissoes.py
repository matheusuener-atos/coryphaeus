"""
Portao da E2 do PAULUS de equipe (docs/PLANO-EQUIPE.md) - quem mexe no que.

Cada pessoa tem um nivel por modulo (src/acesso/permissoes.py): nao ve, so
ve, propoe, faz. Com o app de verdade e sessoes de fora:

  - o colaborador novo tem o padrao (propoe na Agenda, so ve Servicos, nao
    ve o Financeiro);
  - o titular muda o nivel na janela do servidor e vale na proxima
    requisicao, sem entrar de novo;
  - nao ve: 403 com a frase do nivel, e /api/acesso/eu diz para o menu;
  - so ve: le, e gravar e 403; consulta (POST que nao grava) passa;
  - faz: grava direto, sem passar por Aprovacoes; em Aprovacoes, aprova;
  - o Financeiro, fechado de fabrica, abre para ver quando liberado;
  - o que e so do computador do escritorio continua fechado em qualquer nivel;
  - o titular nao se limita; nivel que o modulo nao oferece e ignorado;
  - mudar permissao de fora: 403.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_e2_permissoes.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-e2-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def test_regras() -> None:
    print("\nas regras, sem o app")
    from acesso import permissoes as p

    rotas_do_app = set()
    import api

    for r in api.app.routes:
        for m in getattr(r, "methods", None) or ():
            rotas_do_app.add((m, getattr(r, "path", "")))
    for m in p.MODULOS:
        for grupo in ("libera_ver", "libera_faz", "consultas"):
            sobra = [x for x in m.get(grupo, set()) if x not in rotas_do_app]
            checar(not sobra, f"{m['id']}: toda rota de {grupo} existe no app", sobra)
            fora = [x for x in m.get(grupo, set()) if p.modulo_da_rota(x[1]) is not m]
            checar(not fora, f"{m['id']}: as rotas de {grupo} sao do proprio modulo", fora)
        checar(m["padrao"] in m["niveis"], f"{m['id']}: o padrao e um nivel do modulo")
    checar(p.modulo_da_rota("/api/documentos-abertos")["id"] == "acervo", "/api/documentos-abertos e do Acervo, nao de Documentos")
    checar(p.limpar({"agenda": "faz", "acervo": "faz", "x": "faz"})["acervo"] == "ver",
           "nivel que o modulo nao oferece e ignorado")


def test_http() -> None:
    print("\nde fora, com o app de verdade")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI (fora do Windows)")
        return
    from fastapi.testclient import TestClient

    import api
    from acesso.contas import codigo_totp

    servico = api.estado.acesso_de_fora
    servico.conferir_turnstile = lambda token, ip="": "ok" if token == "ok" else "recusado"
    api.estado.prefs.dados["acesso_remoto"]["ligado"] = True
    # entra por senha para testar outra coisa: a regra "so Google" fica de lado
    api.estado.prefs.dados["acesso_remoto"]["so_google"] = False
    local = TestClient(api.app, headers=api.cabecalho_local())
    passo = int(time.time() // 30) - 1

    def entrar(nome, email, papel):
        c = servico.contas.criar(nome, email, papel, "senha-forte-" + nome.lower())
        servico.contas.confirmar_totp(c["conta"]["id"], codigo_totp(c["segredo"], passo))
        f = TestClient(api.app, base_url="https://x.paulus.ia.br", headers={"Cf-Connecting-IP": "200.2.2.2"})
        pend = f.post("/api/acesso/entrar", json={"email": email, "senha": "senha-forte-" + nome.lower(),
                                                 "turnstile": "ok"}).json()["pendente"]
        r = f.post("/api/acesso/entrar/codigo", json={"pendente": pend, "codigo": codigo_totp(c["segredo"], passo + 1)})
        f.headers["X-PAULUS-CSRF"] = r.json()["csrf"]
        return c["conta"]["id"], f

    try:
        tita_id, tita = entrar("Tita", "tita@x.com", "titular")
        caio_id, caio = entrar("Caio", "caio@x.com", "colaborador")

        print("  o padrao do colaborador")
        eu = caio.get("/api/acesso/eu").json()
        niveis = {m["id"]: m["nivel"] for m in eu.get("permissoes", [])}
        checar(niveis.get("agenda") == "propor" and niveis.get("servicos") == "ver" and niveis.get("financeiro") == "nao",
               "/api/acesso/eu diz o nivel de cada modulo para o menu", niveis)
        r = caio.post("/api/tarefas", json={"id": None, "dados": {"titulo": "proposta"}})
        checar(r.status_code == 202, "tarefas: propoe (202)", r.status_code)
        r = caio.get("/api/financeiro")
        checar(r.status_code == 403 and "Financeiro" in r.json().get("detail", ""), "financeiro: nao ve, com a frase",
               r.text[:160])

        print("  o titular muda, e vale na hora")
        r = local.put(f"/api/acesso/contas/{caio_id}/permissoes",
                      json={"niveis": {"tarefas": "faz", "agenda": "nao", "documentos": "ver", "financeiro": "ver",
                                       "aprovacoes": "faz", "acervo": "faz"}})
        checar(r.status_code == 200 and r.json()["conta"]["permissoes"]["tarefas"] == "faz", "salvar pela janela do servidor",
               r.text[:200])
        checar(r.json()["conta"]["permissoes"]["acervo"] == "ver", "acervo nao oferece 'faz': fica 'ver'")
        antes = len(api.estado.tarefas.listar("todas"))
        r = caio.post("/api/tarefas", json={"id": None, "dados": {"titulo": "direto"}})
        checar(r.status_code == 200 and len(api.estado.tarefas.listar("todas")) == antes + 1,
               "tarefas 'faz': grava direto, sem entrar de novo", r.status_code)
        r = caio.get("/api/agenda")
        checar(r.status_code == 403 and "Agenda" in r.json().get("detail", ""), "agenda 'nao ve': 403", r.status_code)
        checar(caio.get("/api/documentos").status_code == 200, "documentos 'so ve': le")
        r = caio.post("/api/documentos", json={"titulo": "x", "tipo": "texto"})
        checar(r.status_code == 403 and "só pode ver" in r.json().get("detail", ""), "documentos 'so ve': gravar e 403",
               r.text[:160])
        checar(caio.get("/api/financeiro").status_code == 200, "financeiro liberado para ver: le")
        r = caio.post("/api/financeiro/lancamentos", json={})
        checar(r.status_code == 403, "financeiro 'so ve': lancar e 403", r.status_code)
        r = caio.post("/api/biblioteca/lote/apagar", json={"caminhos": []})
        checar(r.status_code == 403 and "escritório" in r.text, "apagar arquivos: fechado em qualquer nivel", r.status_code)
        pedido = api.estado.fila.pedir("Teste de aprovar", "outro", acao="acesso.teste", dados={})
        r = caio.post("/api/aprovacoes/decidir", json={"ids": [pedido.id], "aprovar": False})
        checar(r.status_code == 200, "aprovacoes 'faz': o colaborador aprova (recusa aqui)", r.text[:200])

        print("  o que nao muda")
        r = local.put(f"/api/acesso/contas/{tita_id}/permissoes", json={"niveis": {"agenda": "nao"}})
        checar(r.status_code == 400, "o titular nao se limita", r.status_code)
        r = tita.put(f"/api/acesso/contas/{caio_id}/permissoes", json={"niveis": {"agenda": "faz"}})
        checar(r.status_code == 403, "mudar permissao de fora: 403, mesmo para o titular", r.status_code)
        checar(tita.get("/api/financeiro").status_code == 200, "o titular ve o Financeiro de fora")
    finally:
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = False
        api.estado.prefs.dados["acesso_remoto"]["so_google"] = True
        servico.__dict__.pop("conferir_turnstile", None)


def main() -> int:
    print("=" * 55)
    print("  E2 - quem mexe no que (PAULUS de equipe)")
    print("=" * 55)
    try:
        test_regras()
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
