"""
L3 - visão por cliente e muralha ética (src/clientes.py, js/65-clientes.js).

  - a mesma entidade: "Empresa X Ltda." = "EMPRESA X" = "Empresa X - ME";
    CPF igual e a raiz do CNPJ mandam; documento diferente não é a mesma,
    mesmo com o nome igual; nome quase igual é "parecida";
  - a parte contrária que é cliente do escritório: conflito, com o grau; a
    que é o próprio cliente do Serviço: dito; quem está na equipe dos dois
    lados: muralha;
  - o cliente que é parte contrária em outro Serviço: conflito, na ficha e
    no Serviço;
  - tudo sobre o cliente: Serviços, processos, prazos, documentos (os em
    que ele aparece como parte, com outro nome), parte contrária, conflitos;
  - de fora, as rotas que cruzam todos os clientes não respondem;
  - no Edge: a visão do cliente e a seção Partes com o aviso.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_l3_clientes.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-l3-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def main() -> int:
    print("=" * 55)
    print("  L3 — visão por cliente e muralha ética")
    print("=" * 55)
    import clientes as cl

    print("\na mesma entidade")
    checar(cl.chave("Empresa X Ltda.") == cl.chave("EMPRESA X") == cl.chave("Empresa X - ME") == cl.chave("Empresa X S/A") == "empresa x",
           "Ltda., caixa alta, ME e S/A: a mesma chave")
    checar(cl.chave("Pão & Café Comércio de Alimentos EIRELI") == "pao cafe comercio alimentos", "acento, & e EIRELI")
    checar(cl.mesma("Empresa X Ltda.", "", "EMPRESA X", "") == "igual", "sem documento, pelo nome: igual")
    checar(cl.mesma("A", "11.222.333/0001-81", "B", "11.222.333/0002-62") == "igual", "a raiz do CNPJ (matriz e filial): a mesma")
    checar(cl.mesma("Empresa X", "11.222.333/0001-81", "Empresa X", "22.333.444/0001-05") == "",
           "documentos diferentes: não é a mesma, mesmo com o nome igual")
    checar(cl.mesma("João da Silva", "529.982.247-25", "J. Silva", "529.982.247-25") == "igual", "o CPF manda")
    checar(cl.mesma("Construtora Boa Vista Ltda", "", "Boa Vista Construtora", "") == "parecida", "a ordem trocada: parecida")
    checar(cl.mesma("Maria Souza", "", "João Souza", "") == "", "uma palavra em comum não basta")

    import api
    from fastapi.testclient import TestClient

    local = TestClient(api.app, headers=api.cabecalho_local())

    def cad(nome, tipo="cliente", documento="", email=""):
        r = local.post("/api/cadastros", json={"id": None, "dados": {"tipo": tipo, "nome": nome, "documento": documento, "email": email}})
        assert r.status_code == 200, r.text
        return r.json()["id"]

    alfa = cad("Construtora Alfa Ltda", documento="11.222.333/0001-81")
    maria = cad("Maria Souza")
    rui = cad("Rui", tipo="colaborador", email="rui@x.com")
    s_alfa = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Obra da Alfa", "cadastro_id": alfa}}).json()["id"]
    s_maria = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Ação da Maria", "cadastro_id": maria}}).json()["id"]
    # A equipe direto na base: a regra "só quem tem acesso entra na equipe" é da rota de Serviços.
    for s in (s_alfa, s_maria):
        api.estado.base.escrever("UPDATE servicos SET equipe = ? WHERE id = ?", (f"[{rui}]", s))

    print("\na parte contrária")
    r = local.put(f"/api/servicos/{s_maria}/partes", json={"partes": [{"nome": "CONSTRUTORA ALFA", "papel": "contraria"}]}).json()
    tipos = sorted(c["tipo"] for c in r["conflitos"])
    checar(r["partes"] == [{"nome": "CONSTRUTORA ALFA", "documento": "", "papel": "contraria"}] and tipos == ["cliente", "muralha"],
           "a parte contrária é cliente do escritório: conflito, e o Rui está nos dois lados: muralha", r["conflitos"])
    muralha = next(c for c in r["conflitos"] if c["tipo"] == "muralha")
    checar("Rui" in muralha["texto"] and "Obra da Alfa" in muralha["texto"], "a muralha diz quem e onde", muralha["texto"])
    r = local.put(f"/api/servicos/{s_alfa}/partes", json={"partes": [{"nome": "Construtora Alfa", "papel": "contraria"}]}).json()
    checar([c["tipo"] for c in r["conflitos"]] == ["proprio"], "a parte contrária é o próprio cliente do Serviço: dito", r["conflitos"])
    local.put(f"/api/servicos/{s_alfa}/partes", json={"partes": [{"nome": "Prefeitura de Itu", "papel": "contraria"}]})
    r = local.put(f"/api/servicos/{s_maria}/partes", json={"partes": [{"nome": "Alfa Engenharia", "documento": "11.222.333/0002-62"}]}).json()
    checar(any(c["tipo"] == "cliente" and c["grau"] == "igual" for c in r["conflitos"]), "outro nome, a mesma raiz do CNPJ: conflito", r["conflitos"])
    local.put(f"/api/servicos/{s_maria}/partes", json={"partes": [{"nome": "CONSTRUTORA ALFA", "papel": "contraria"}]})

    print("\no cliente do outro lado")
    r = local.post("/api/clientes/conflitos", json={"nome": "Construtora Alfa Ltda", "documento": "11.222.333/0001-81",
                                                     "papel": "cliente", "cadastro_id": alfa}).json()
    checar(len(r["conflitos"]) == 1 and r["conflitos"][0]["tipo"] == "contraria" and "Ação da Maria" in r["conflitos"][0]["texto"],
           "a ficha do cliente: ele é parte contrária em outro Serviço", r)
    r = local.get(f"/api/servicos/{s_alfa}/conflitos").json()
    checar(any(c["tipo"] == "contraria" for c in r["conflitos"]), "no Serviço dele, o mesmo aviso", r)
    checar(local.get(f"/api/servicos/{s_maria}/conflitos").json()["conflitos"], "no outro Serviço, a parte contrária cliente")

    print("\ntudo sobre o cliente")
    import processos as pr

    n = "0001234-71.2024.8.26.0100"
    local.post("/api/processos", json={"numero": n, "servico_id": s_alfa})
    tid = api.estado.tarefas.salvar({"titulo": "Responder notificação", "prazo": "2026-12-01", "lista": "Prazos"})
    api.estado.base.escrever("UPDATE tarefas SET servico_id = ? WHERE id = ?", (s_alfa, tid))
    base = api.estado.base
    base.escrever("INSERT INTO meta_documentos (id, titulo, caminho, versao_atual, criado_em, atualizado_em) VALUES (?,?,?,?,?,?)",
                  ("d1", "contrato-obra.pdf", "C:/x/contrato-obra.pdf", "v1", "2026-09-30", "2026-09-30"))
    base.escrever("INSERT INTO meta_versoes (id, documento_id, sha256, criado_em) VALUES (?,?,?,?)", ("v1", "d1", "s1", "2026-09-30"))
    base.escrever("INSERT INTO meta_fatos (versao_id, documento_id, secao, item_id, chave, valor, mostrar, verificado)"
                  " VALUES (?,?,?,?,?,?,?,1)", ("v1", "d1", "parties", "p1", "defendant", "construtora alfa ltda.", "CONSTRUTORA ALFA LTDA."))
    v = local.get(f"/api/clientes/{alfa}/visao").json()
    checar([s["nome"] for s in v["servicos"]] == ["Obra da Alfa"], "os Serviços do cliente")
    checar([p["numero_fmt"] for p in v["processos"]] == [n], "os processos dos Serviços dele (L2)")
    checar(any(t["titulo"] == "Responder notificação" for t in v["prazos"]), "os prazos em aberto")
    checar(any(d["nome"] == "contrato-obra.pdf" and "parte" in d["como"] for d in v["documentos"]),
           "o documento em que ele aparece como parte, com outro nome", v["documentos"])
    checar(any(o["nome"] == "CONSTRUTORA ALFA LTDA." for o in v["outros_nomes"]), "também aparece como", v["outros_nomes"])
    checar([p["nome"] for p in v["partes_contrarias"]] == ["Prefeitura de Itu"] and v["conflitos"], "a parte contrária dele e os conflitos")
    checar(local.get("/api/clientes/99999/visao").status_code == 404, "cliente que não existe: 404")

    print("\nde fora")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI")
    else:
        from acesso.contas import codigo_totp

        servico = api.estado.acesso_de_fora
        servico.conferir_turnstile = lambda token, ip="": "ok"
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = True
        api.estado.prefs.dados["acesso_remoto"]["so_google"] = False
        servico.contas.criar("Mateus", "mateus@x.com", "titular", "senha-forte-mateus")
        conta = servico.contas.criar("Rui", "rui@x.com", "colaborador", "senha-forte-rui")
        servico.contas.confirmar_totp(conta["conta"]["id"], codigo_totp(conta["segredo"], int(time.time() // 30)))
        local.put(f"/api/acesso/contas/{conta['conta']['id']}/permissoes", json={"niveis": {"servicos": "faz", "cadastros": "ver"}})
        f = TestClient(api.app, base_url="https://x.paulus.ia.br", headers={"Cf-Connecting-IP": "200.2.2.2"})
        pend = f.post("/api/acesso/entrar", json={"email": "rui@x.com", "senha": "senha-forte-rui", "turnstile": "ok"}).json()["pendente"]
        rr = f.post("/api/acesso/entrar/codigo", json={"pendente": pend, "codigo": codigo_totp(conta["segredo"], int(time.time() // 30) + 1)})
        f.headers["X-PAULUS-CSRF"] = rr.json()["csrf"]
        checar(f.get(f"/api/clientes/{alfa}/visao").status_code == 403 and
               f.post("/api/clientes/conflitos", json={"nome": "x"}).status_code == 403 and
               f.get(f"/api/servicos/{s_alfa}/conflitos").status_code == 403,
               "de fora, a visão e a conferência (que cruzam todos os clientes) não respondem")
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = False

    print("\nno Edge")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None
        print("  pulado: playwright não instalado")
    if sync_playwright is not None:
        from test_gravacoes import _porta_livre, _subir_servidor

        porta = _porta_livre()
        _subir_servidor(porta)
        with sync_playwright() as p:
            try:
                nav = p.chromium.launch(channel="msedge")
            except Exception as exc:  # noqa: BLE001
                nav = None
                print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            if nav is not None:
                pag = nav.new_context(viewport={"width": 1280, "height": 900}).new_page()
                erros = []
                pag.on("pageerror", lambda e: erros.append(str(e)))
                pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
                pag.goto(f"http://127.0.0.1:{porta}/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
                pag.wait_for_function("() => typeof mostrarVisaoDoCliente === 'function'")
                pag.wait_for_timeout(800)
                pag.evaluate(f"() => mostrarVisaoDoCliente({alfa})")
                pag.wait_for_selector(".cli-bloco", timeout=15000)
                texto = pag.inner_text("#cli-visao")
                checar("Possível conflito de interesse" in texto and "Obra da Alfa" in texto and n in texto and "contrato-obra.pdf" in texto
                       and "CONSTRUTORA ALFA LTDA." in texto, "a visão do cliente, com o conflito no alto", texto[:240])
                pag.screenshot(path=str(TMP / "l3-visao.png"))
                pag.evaluate(f"() => abrirServico({s_maria})")
                pag.wait_for_selector(".cli-conflito", timeout=15000)
                texto = pag.inner_text("#sv-tela")
                checar("CONSTRUTORA ALFA" in texto and "é cliente do escritório" in texto and "equipe dos dois lados" in texto,
                       "o Serviço: a parte contrária e o aviso, com a muralha", texto[:300])
                pag.screenshot(path=str(TMP / "l3-servico.png"))
                checar(not erros, "nenhum erro de JavaScript", erros[:3])
                print(f"  (fotos em {TMP})")
                nav.close()

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
