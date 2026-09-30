"""
L2 - acompanhamento de processos pelo DataJud (src/processos.py, js/64-processos.js).

Com o DataJud trocado por um de mentira (nada sai daqui):

  - o prazo sugerido: intimação, citação e publicação sim, juntada não; a
    conta vem inteira, com a origem certa;
  - número inválido recusado; "achar nos documentos" traz os números
    validados da leitura, ligados ao Serviço da pasta, sem acompanhar;
  - a primeira consulta só guarda o que já havia (nenhum aviso); a segunda
    traz o novo: aviso na Central, pedido de prazo em Aprovações; o sim
    cria a tarefa em "Prazos" com a conta; marcar como vistas tira o aviso;
  - desligado, a volta não roda; erro do DataJud fica no processo;
  - de fora: a pessoa vê só os processos dos Serviços dela e não acompanha,
    consulta nem muda nada;
  - no Edge: a tela Processos, o detalhe com as movimentações novas.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_l2_processos.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-l2-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def numero_cnj(seq: int, ano: int = 2024, j: str = "8", tr: str = "26", origem: str = "0100") -> str:
    n = f"{seq:07d}"
    dd = 98 - (int(n + str(ano) + j + tr + origem) * 100 % 97)
    return f"{n}-{dd:02d}.{ano}.{j}.{tr}.{origem}"


class DataJud:
    """Os movimentos de cada número; `mais` acrescenta movimentos novos na próxima consulta."""

    def __init__(self) -> None:
        self.movs: dict[str, list[dict]] = {}
        self.chamadas: list[str] = []
        self.falhar: set[str] = set()

    def __call__(self, numero: str) -> dict:
        self.chamadas.append(numero)
        if numero in self.falhar:
            raise ConnectionError("o DataJud respondeu com erro (503)")
        return {"numero": numero, "graus": [{"grau": "G1", "classe": "Procedimento Comum Cível", "orgao": "1ª Vara Cível",
                                            "movimentos": list(self.movs.get(numero, []))}]}


def main() -> int:
    print("=" * 55)
    print("  L2 — processos pelo DataJud")
    print("=" * 55)
    import processos

    print("\no prazo sugerido")
    s = processos.sugerir_prazo({"quando": "2026-09-14 10:00", "nome": "Expedição de documento", "complemento": "Intimação"})
    checar(s and s["dias"] == 15 and s["origem"] == "intimacao" and s["passos"] and s["vencimento"] > "2026-09-14",
           "intimação: 15 dias úteis, com a conta", s)
    s = processos.sugerir_prazo({"quando": "2026-09-14 10:00", "nome": "Publicação", "complemento": ""})
    checar(s and s["origem"] == "disponibilizacao", "publicação: conta pela disponibilização", s)
    checar(processos.sugerir_prazo({"quando": "2026-09-14", "nome": "Juntada de Petição", "complemento": ""}) is None,
           "juntada: sem prazo sugerido")

    import api
    from fastapi.testclient import TestClient

    local = TestClient(api.app, headers=api.cabecalho_local())
    falso = DataJud()
    processos._CONSULTAR["fn"] = falso
    n1, n2, n3 = numero_cnj(1234), numero_cnj(5678), numero_cnj(9012)

    print("\ncadastro e achar nos documentos")
    checar(local.post("/api/processos", json={"numero": "0001234-00.2024.8.26.0100"}).status_code == 400, "número com dígito errado: recusa")
    r = local.post("/api/processos", json={"numero": n1})
    checar(r.status_code == 200 and r.json()["acompanhar"] and r.json()["tribunal"] == "TJSP", "número à mão entra acompanhado", r.json())
    s1 = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Ação de cobrança"}}).json()["id"]
    pasta = api.estado.servicos.pasta_de(s1, criar=True)
    base = api.estado.base
    for i, (num, caminho) in enumerate(((n2, str(pasta / "inicial.pdf")), (n1, "C:/x/outro.pdf"))):
        base.escrever("INSERT INTO meta_documentos (id, titulo, caminho, versao_atual, criado_em, atualizado_em) VALUES (?,?,?,?,?,?)",
                      (f"d{i}", Path(caminho).name, caminho, f"v{i}", "2026-09-30", "2026-09-30"))
        base.escrever("INSERT INTO meta_versoes (id, documento_id, sha256, criado_em) VALUES (?,?,?,?)", (f"v{i}", f"d{i}", f"s{i}", "2026-09-30"))
        base.escrever("INSERT INTO meta_fatos (versao_id, documento_id, secao, item_id, chave, valor, mostrar, verificado)"
                      " VALUES (?,?,?,?,?,?,?,1)", (f"v{i}", f"d{i}", "case", "case", "case_number", num.lower(), num))
    d = local.post("/api/processos/descobrir").json()
    lista = local.get("/api/processos").json()["processos"]
    achado = next((p for p in lista if p["numero_fmt"] == n2), {})
    checar(d == {"encontrados": 2, "novos": 1} and achado.get("origem") == "documento" and not achado.get("acompanhar")
           and achado.get("servico_id") == s1 and achado.get("documento") == "inicial.pdf",
           "achar nos documentos: o número novo entra ligado ao Serviço da pasta, sem acompanhar", (d, achado))

    print("\na volta")
    api.estado.prefs.dados.setdefault("processos", {})["acompanhar"] = False
    checar(local.post("/api/processos/acompanhar-agora").status_code == 409, "desligado: a volta não roda")
    api.estado.prefs.dados["processos"]["acompanhar"] = True
    falso.movs[n1.replace("-", "").replace(".", "")] = [{"quando": "2026-08-01 09:00", "nome": "Distribuição", "complemento": ""}]
    r = local.post("/api/processos/acompanhar-agora").json()
    avisos = [a for a in local.get("/api/central-avisos?periodo=semana").json().get("avisos", []) if a["tipo"] == "processo"]
    checar(r["consultados"] == 1 and r["novos"] == 0 and not avisos and len(falso.chamadas) == 1,
           "primeira consulta: guarda o que já havia, sem aviso; o não acompanhado não é consultado", (r, falso.chamadas))
    checar(falso.chamadas == [n1.replace("-", "").replace(".", "")], "ao DataJud vai só o número")
    falso.movs[n1.replace("-", "").replace(".", "")] += [
        {"quando": "2026-09-14 10:00", "nome": "Expedição de documento", "complemento": "Intimação"},
        {"quando": "2026-09-15 11:00", "nome": "Juntada de Petição", "complemento": ""}]
    r = local.post("/api/processos/acompanhar-agora").json()
    checar(r["novos"] == 2 and r["prazos_propostos"] == 1, "segunda consulta: 2 novas, 1 com prazo proposto", r)
    avisos = [a for a in local.get("/api/central-avisos?periodo=semana").json().get("avisos", []) if a["tipo"] == "processo"]
    checar(len(avisos) == 1 and "2 movimentações novas" in avisos[0]["quando"] and avisos[0]["destino"]["tela"] == "processo",
           "um aviso na Central para o processo, com a contagem", avisos)
    pedidos = [p for p in api.estado.fila.pendentes if p.acao == "processos.prazo"]
    checar(len(pedidos) == 1 and pedidos[0].prazo and "Vence" in pedidos[0].resumo, "o prazo espera em Aprovações, com a conta", [p.resumo for p in pedidos])
    antes = len(base.buscar("SELECT id FROM tarefas WHERE lista = 'Prazos'"))
    r = local.post("/api/aprovacoes/decidir", json={"ids": [pedidos[0].id], "aprovar": True})
    tarefa = base.um("SELECT * FROM tarefas WHERE lista = 'Prazos' ORDER BY id DESC LIMIT 1") or {}
    checar(r.status_code == 200 and len(base.buscar("SELECT id FROM tarefas WHERE lista = 'Prazos'")) == antes + 1
           and tarefa.get("prazo") == pedidos[0].prazo and "confira a data da ciência" in (tarefa.get("anotacao") or ""),
           "o sim cria a tarefa em Prazos, com a conta e o aviso de conferir", dict(tarefa))
    pid = next(p["id"] for p in local.get("/api/processos").json()["processos"] if p["numero_fmt"] == n1)
    det = local.get(f"/api/processos/{pid}").json()
    checar(len(det["movimentos"]) == 3 and sum(1 for m in det["movimentos"] if not m["visto"]) == 2 and det["processo"]["classe"],
           "o detalhe traz as movimentações, com as novas marcadas", len(det["movimentos"]))
    local.post(f"/api/processos/{pid}/vistos")
    avisos = [a for a in local.get("/api/central-avisos?periodo=semana").json().get("avisos", []) if a["tipo"] == "processo"]
    checar(not avisos, "marcar como vistas tira o aviso")
    r = local.post("/api/processos/acompanhar-agora").json()
    checar(r["novos"] == 0, "consultar de novo não duplica")
    falso.falhar.add(n1.replace("-", "").replace(".", ""))
    local.post(f"/api/processos/{pid}/consultar")
    checar("503" in (local.get(f"/api/processos/{pid}").json()["processo"]["ultimo_erro"] or ""), "erro do DataJud fica no processo")
    falso.falhar.clear()

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
        local.put(f"/api/acesso/contas/{conta['conta']['id']}/permissoes", json={"niveis": {"servicos": "faz", "acervo": "ver"}})
        rui_cad = local.post("/api/cadastros", json={"id": None, "dados": {"tipo": "colaborador", "nome": "Rui", "email": "rui@x.com"}}).json()["id"]
        s2 = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Do Rui", "equipe": [rui_cad]}}).json()["id"]
        local.post("/api/processos", json={"numero": n3, "servico_id": s2})
        f = TestClient(api.app, base_url="https://x.paulus.ia.br", headers={"Cf-Connecting-IP": "200.2.2.2"})
        pend = f.post("/api/acesso/entrar", json={"email": "rui@x.com", "senha": "senha-forte-rui", "turnstile": "ok"}).json()["pendente"]
        rr = f.post("/api/acesso/entrar/codigo", json={"pendente": pend, "codigo": codigo_totp(conta["segredo"], int(time.time() // 30) + 1)})
        f.headers["X-PAULUS-CSRF"] = rr.json()["csrf"]
        vistos = [p["numero_fmt"] for p in f.get("/api/processos").json()["processos"]]
        checar(vistos == [n3], "de fora, a pessoa vê só os processos dos Serviços dela", vistos)
        checar(f.get(f"/api/processos/{pid}").status_code == 404, "o processo de outro Serviço não abre")
        checar(f.post("/api/processos", json={"numero": numero_cnj(77)}).status_code == 403
               and f.post("/api/processos/acompanhar-agora").status_code == 403
               and f.put(f"/api/processos/{pid}", json={"acompanhar": False}).status_code == 403,
               "de fora, ninguém acompanha, consulta nem muda")
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = False

    print("\nno Edge")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None
        print("  pulado: playwright não instalado")
    if sync_playwright is not None:
        from test_gravacoes import _porta_livre, _subir_servidor

        falso.movs[n1.replace("-", "").replace(".", "")].append({"quando": "2026-09-20 15:00", "nome": "Publicação", "complemento": "DJEN"})
        local.post("/api/processos/acompanhar-agora")
        porta = _porta_livre()
        _subir_servidor(porta)
        with sync_playwright() as p:
            try:
                nav = p.chromium.launch(channel="msedge")
            except Exception as exc:  # noqa: BLE001
                nav = None
                print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            if nav is not None:
                pag = nav.new_context(viewport={"width": 1280, "height": 860}).new_page()
                erros = []
                pag.on("pageerror", lambda e: erros.append(str(e)))
                pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
                pag.goto(f"http://127.0.0.1:{porta}/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
                pag.wait_for_function("() => typeof mostrarProcessos === 'function'")
                pag.wait_for_timeout(800)
                pag.evaluate("() => mostrarServicos('pastas')")
                pag.wait_for_selector("[data-pr-tela]", timeout=15000)
                pag.click("[data-pr-tela]")
                pag.wait_for_selector(".pr-linha", timeout=15000)
                texto = pag.inner_text("#pr-tela")
                checar(n1 in texto and n2 in texto and "1 nova" in texto and "Acompanhar pelo DataJud" in texto,
                       "a tela Processos: a lista, a nova e a chave", texto[:200])
                pag.screenshot(path=str(TMP / "l2-lista.png"))
                pag.click(f".pr-linha:has-text('{n1}')")
                pag.wait_for_selector(".pr-mov", timeout=10000)
                checar(pag.locator(".pr-mov.nova").count() == 1 and "Publicação" in pag.inner_text(".pr-movs"),
                       "o detalhe mostra as movimentações, com a nova marcada")
                pag.screenshot(path=str(TMP / "l2-detalhe.png"))
                pag.click("[data-pr-vistos]")
                pag.wait_for_timeout(600)
                checar(base.um("SELECT COUNT(*) AS n FROM movimentos WHERE visto = 0")["n"] == 0, "marcar como vistas pela tela")
                pag.evaluate(f"() => abrirServico({s1})")
                pag.wait_for_selector("[data-sv-aba='processos']", timeout=15000)
                pag.click("[data-sv-aba='processos']")
                pag.wait_for_selector("#pr-servico .pr-linha", timeout=15000)
                checar(n2 in pag.inner_text("#pr-servico") and n1 not in pag.inner_text("#pr-servico"),
                       "a aba Processos do Serviço mostra só os dele")
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
