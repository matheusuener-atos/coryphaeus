"""
Servicos por colaborador (src/servicos_acesso.py): de fora, cada pessoa so ve
os servicos de que participa - a Equipe do servico, pelas fichas de Cadastros
casadas pelo e-mail da conta.

  Servico A: Mateus e Sara.   Servico B: Mateus e Joao.

  - Sara ve A e nao B; Joao ve B e nao A; o titular e a janela do servidor
    veem os dois;
  - pedir B pelo endereco (e qualquer rota dele) da 404 para a Sara - a API
    barra, nao so a tela;
  - o que e de B some para ela: a pasta de B no Acervo (lista, busca), a
    etapa de B em Tarefas e na Agenda, o compromisso de B e a gravacao de B;
  - o servico que a Sara cria nasce com ela na Equipe; editar nao muda a
    Equipe (quem define e o titular);
  - o titular muda a Equipe e vale na proxima requisicao.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_servicos_colaboradores.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-servcolab-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def test_http() -> None:
    print("\nservicos por colaborador, de fora")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI (fora do Windows)")
        return
    from fastapi.testclient import TestClient

    import api
    from acesso.contas import codigo_totp

    servico = api.estado.acesso_de_fora
    servico.conferir_turnstile = lambda token, ip="": "ok"
    api.estado.prefs.dados["acesso_remoto"]["ligado"] = True
    api.estado.prefs.dados["acesso_remoto"]["so_google"] = False
    local = TestClient(api.app, headers=api.cabecalho_local())
    passo = int(time.time() // 30) - 1

    def entrar(nome, email, papel):
        c = servico.contas.criar(nome, email, papel, "senha-forte-" + nome.lower())
        servico.contas.confirmar_totp(c["conta"]["id"], codigo_totp(c["segredo"], passo))
        if papel != "titular":
            local.put(f"/api/acesso/contas/{c['conta']['id']}/permissoes",
                      json={"niveis": {"servicos": "faz", "tarefas": "faz", "agenda": "faz", "gravacoes": "ver", "acervo": "ver"}})
        f = TestClient(api.app, base_url="https://x.paulus.ia.br", headers={"Cf-Connecting-IP": "200.2.2.2"})
        pend = f.post("/api/acesso/entrar", json={"email": email, "senha": "senha-forte-" + nome.lower(),
                                                 "turnstile": "ok"}).json()["pendente"]
        r = f.post("/api/acesso/entrar/codigo", json={"pendente": pend, "codigo": codigo_totp(c["segredo"], passo + 1)})
        f.headers["X-PAULUS-CSRF"] = r.json()["csrf"]
        return f

    def cad(nome, email, tipo="colaborador"):
        return local.post("/api/cadastros", json={"id": None, "dados": {"tipo": tipo, "nome": nome, "email": email}}).json()["id"]

    try:
        mateus = cad("Mateus", "mateus@x.com", "socio")
        sara = cad("Sara", "Sara@X.com")          # o e-mail da ficha casa sem olhar maiusculas
        joao = cad("João", "joao@x.com")
        a = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Serviço A", "equipe": [mateus, sara]}}).json()["id"]
        b = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Serviço B", "equipe": [mateus, joao]}}).json()["id"]

        # O que e de B: um arquivo na pasta dele, uma tarefa, um compromisso e uma gravacao.
        pasta_b = api.estado.servicos.pasta_de(b, criar=True)
        (pasta_b / "parecer-do-b.txt").write_text("Parecer sigiloso sobre a fusao Zebralux do servico B.", encoding="utf-8")
        pasta_a = api.estado.servicos.pasta_de(a, criar=True)
        (pasta_a / "nota-do-a.txt").write_text("Nota do servico A sobre a fusao Zebralux.", encoding="utf-8")
        api.estado.recarregar()
        agora = "2026-09-29T10:00:00"
        hoje = time.strftime("%Y-%m-%d")
        tb = api.estado.base.escrever("INSERT INTO tarefas (titulo, prazo, servico_id, criada_em) VALUES (?, ?, ?, ?)",
                                      ("Etapa do B", hoje, b, agora))
        ta = api.estado.base.escrever("INSERT INTO tarefas (titulo, prazo, servico_id, criada_em) VALUES (?, ?, ?, ?)",
                                      ("Etapa do A", hoje, a, agora))
        cb = api.estado.base.escrever("INSERT INTO compromissos (titulo, data, servico_id, criado_em) VALUES (?, ?, ?, ?)",
                                      ("Reunião do B", hoje, b, agora))
        gb = api.estado.base.escrever("INSERT INTO gravacoes (titulo, servico_id, criado_em) VALUES (?, ?, ?)",
                                      ("Gravação do B", b, agora))

        # a primeira conta do escritorio e a do titular
        f_tita = entrar("Mateus", "mateus@x.com", "titular")
        f_sara = entrar("Sara", "sara@x.com", "colaborador")
        f_joao = entrar("Joao", "joao@x.com", "colaborador")

        print("  a lista")
        nomes = lambda cli: sorted(s["nome"] for s in cli.get("/api/servicos").json()["servicos"])  # noqa: E731
        checar(nomes(f_sara) == ["Serviço A"], "Sara ve so o A", nomes(f_sara))
        checar(nomes(f_joao) == ["Serviço B"], "Joao ve so o B", nomes(f_joao))
        checar(nomes(f_tita) == ["Serviço A", "Serviço B"], "o titular ve os dois", nomes(f_tita))
        checar(nomes(local) == ["Serviço A", "Serviço B"], "a janela do servidor ve os dois")
        checar(f_sara.get("/api/servicos").json()["contagem"]["total"] == 1, "a contagem tambem e so a dela")

        print("  pedir direto pela API")
        checar(f_sara.get(f"/api/servicos/{b}").status_code == 404, "Sara pede o B pelo endereco: 404")
        checar(f_sara.post(f"/api/servicos/{b}/anotacoes", json={"texto": "x"}).status_code == 404, "e anotar no B: 404")
        checar(f_sara.post("/api/servicos", json={"id": b, "dados": {"nome": "invadido"}}).status_code == 404,
               "e editar o B pelo corpo: 404")
        checar(f_sara.get(f"/api/servicos/{a}").status_code == 200, "o A abre para ela")
        checar(f_joao.get(f"/api/servicos/{b}").status_code == 200, "o B abre para o Joao")

        print("  o que e de B some junto")
        docs = lambda cli: {d["nome"] for d in cli.get("/api/biblioteca").json()["documentos"]}  # noqa: E731
        checar("parecer-do-b.txt" not in docs(f_sara) and "nota-do-a.txt" in docs(f_sara), "Acervo: a pasta do B nao aparece para a Sara",
               docs(f_sara))
        checar("parecer-do-b.txt" in docs(f_joao), "e aparece para o Joao")
        achados = {d["nome"] for d in f_sara.get("/api/biblioteca", params={"termo": "Zebralux"}).json()["documentos"]}
        checar("parecer-do-b.txt" not in achados and "nota-do-a.txt" in achados, "a busca pelo conteudo tambem nao acha o do B", achados)
        import search as search_mod

        tok = search_mod.FILTRO.set(lambda c: "parecer-do-b" not in c)
        try:
            hits = api.estado.searcher.search("Zebralux fusao", top_k=5)
        finally:
            search_mod.FILTRO.reset(tok)
        checar(hits and all("parecer-do-b" not in h.chunk.doc_path for h in hits), "a busca do assistente respeita o filtro",
               [h.chunk.doc_path for h in hits])
        tarefas = {t["titulo"] for t in f_sara.get("/api/tarefas", params={"filtro": "meu_dia"}).json()["tarefas"]}
        checar("Etapa do B" not in tarefas and "Etapa do A" in tarefas, "Tarefas: a etapa do B nao aparece", tarefas)
        checar(f_sara.post(f"/api/tarefas/{tb}/concluir").status_code == 404, "concluir a etapa do B: 404")
        dia = f_sara.get("/api/agenda/dia", params={"dia": hoje}).json()
        checar(all(c["titulo"] != "Reunião do B" for c in dia["compromissos"])
               and all(t["titulo"] != "Etapa do B" for t in dia["tarefas"]), "Agenda: nem o compromisso nem a etapa do B")
        checar(f_sara.delete(f"/api/agenda/{cb}").status_code == 404, "apagar o compromisso do B: 404")
        grav = {g["titulo"] for g in f_sara.get("/api/gravacoes").json().get("gravacoes", [])}
        checar("Gravação do B" not in grav, "Gravacoes: a do B nao aparece", grav)
        checar(f_sara.get(f"/api/gravacoes/{gb}").status_code == 404, "e pedir a gravacao do B: 404")
        dia_j = f_joao.get("/api/agenda/dia", params={"dia": hoje}).json()
        checar(any(c["titulo"] == "Reunião do B" for c in dia_j["compromissos"]), "para o Joao, a reuniao do B esta la")
        checar(ta, "(a etapa do A existe)")

        print("  criar e editar de fora")
        r = f_sara.post("/api/servicos", json={"id": None, "dados": {"nome": "Serviço da Sara", "equipe": []}})
        checar(r.status_code == 200 and [p["id"] for p in r.json()["equipe"]] == [sara], "o que a Sara cria nasce com ela na Equipe",
               r.text[:200])
        checar("Serviço da Sara" in nomes(f_sara) and "Serviço da Sara" not in nomes(f_joao), "e so ela (e o titular) o veem")
        r = f_sara.post("/api/servicos", json={"id": a, "dados": {"nome": "Serviço A", "equipe": [sara, joao]}})
        checar(r.status_code == 200 and sorted(p["id"] for p in r.json()["equipe"]) == sorted([mateus, sara]),
               "editar de fora nao muda a Equipe", r.text[:200])

        print("  o titular muda a Equipe")
        local.post("/api/servicos", json={"id": b, "dados": {"nome": "Serviço B", "equipe": [mateus, joao, sara]}})
        checar("Serviço B" in nomes(f_sara), "a Sara entra no B e ve na hora")
        checar(f_sara.get(f"/api/servicos/{b}").status_code == 200, "e abre o B")
        checar("parecer-do-b.txt" in docs(f_sara), "e a pasta do B aparece no Acervo dela")
    finally:
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = False
        api.estado.prefs.dados["acesso_remoto"]["so_google"] = True


def main() -> int:
    test_http()
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print("    - " + f)
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
