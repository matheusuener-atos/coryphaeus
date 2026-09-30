"""
N4 - o conflito de interesse guardado como pendência (src/clientes.py, js/72-conflitos.js).

  - anotar a parte contrária que é cliente guarda o conflito (e a muralha),
    uma vez só; a mesma situação vista da ficha do cliente é a mesma pendência;
  - a Central de avisos mostra cada conflito aberto;
  - resolver pede a forma (e a frase, em "outro"), guarda quem e quando; o
    aviso sai; a visão do cliente mostra os resolvidos; reabrir volta;
  - muralha dada por aplicada, com a pessoa ainda nas duas equipes, reabre;
    a pessoa saindo, a conferência geral fecha sozinha ("deixou de existir");
    a parte saindo, também; voltando, reabre;
  - de fora, as rotas são da janela do escritório;
  - no Edge: Cadastros › Conflitos, resolver pela caixa, e o aviso da Central.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_n4_conflitos.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-n4-"))
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
    print("  N4 — o conflito como pendência")
    print("=" * 55)
    import api
    from acesso import politicas
    from fastapi.testclient import TestClient

    local = TestClient(api.app, headers=api.cabecalho_local())
    base = api.estado.base
    api.estado.prefs.atualizar({"pessoa": {"nome": "Dra. Ana Titular"}})
    alfa = local.post("/api/cadastros", json={"id": None, "dados": {"tipo": "cliente", "nome": "Construtora Alfa Ltda",
                                                                    "documento": "11.444.777/0001-61"}}).json()["id"]
    maria = local.post("/api/cadastros", json={"id": None, "dados": {"tipo": "cliente", "nome": "Maria Souza"}}).json()["id"]
    rui = local.post("/api/cadastros", json={"id": None, "dados": {"tipo": "colaborador", "nome": "Rui Costa"}}).json()["id"]
    s_alfa = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Obra da Alfa", "cadastro_id": alfa}}).json()["id"]
    s_maria = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Ação da Maria", "cadastro_id": maria}}).json()["id"]
    for s in (s_alfa, s_maria):
        base.escrever("UPDATE servicos SET equipe = ? WHERE id = ?", (json.dumps([rui]), s))

    def abertos():
        return base.buscar("SELECT * FROM conflitos WHERE estado = 'aberto' ORDER BY id")

    def central():
        return [a for a in local.get("/api/central-avisos?periodo=semana").json().get("avisos", []) if a["tipo"] == "conflito"]

    print("\nguardar")
    partes = [{"nome": "CONSTRUTORA ALFA", "documento": "", "papel": "contraria"}]
    r = local.put(f"/api/servicos/{s_maria}/partes", json={"partes": partes}).json()
    tipos = sorted(c["tipo"] for c in r["conflitos"])
    checar(tipos == ["cliente", "muralha"] and all(c.get("id") and c["estado"] == "aberto" for c in r["conflitos"]),
           "a parte contrária que é cliente guarda o conflito e a muralha, abertos", r["conflitos"])
    local.put(f"/api/servicos/{s_maria}/partes", json={"partes": partes})
    local.get(f"/api/servicos/{s_maria}/conflitos")
    checar(len(abertos()) == 2, "conferir de novo não duplica", len(abertos()))
    r = local.post("/api/clientes/conflitos", json={"nome": "Construtora Alfa Ltda", "documento": "11.444.777/0001-61",
                                                     "papel": "cliente", "cadastro_id": alfa}).json()
    lados = next((c for c in abertos() if c["tipo"] == "cliente"), {})
    checar(len(abertos()) == 2 and r["conflitos"] and r["conflitos"][0]["id"] == lados.get("id"),
           "a mesma situação vista da ficha do cliente é a mesma pendência", (r["conflitos"], lados.get("id")))
    av = central()
    checar(len(av) == 2 and all(a["destino"]["tela"] == "conflito" for a in av), "a Central mostra os dois conflitos abertos", av)

    print("\nresolver")
    checar(local.post(f"/api/conflitos/{lados['id']}/resolver", json={"resolucao": "outro", "nota": ""}).status_code == 400,
           "“outro motivo” sem a frase: recusa")
    checar(local.post(f"/api/conflitos/{lados['id']}/resolver", json={"resolucao": "qualquer"}).status_code == 400, "resolução que não existe: recusa")
    r = local.post(f"/api/conflitos/{lados['id']}/resolver", json={"resolucao": "autorizado", "nota": "Termo assinado pelos dois em 01/10."}).json()
    c = r["conflito"]
    checar(c["estado"] == "resolvido" and c["resolvido_por"] == "Dra. Ana Titular" and c["resolvido_em"] and "Termo" in c["nota"]
           and c["resolucao_rotulo"].startswith("Os clientes autorizaram"), "resolvido: a forma, a anotação, quem e quando", c)
    checar(len(central()) == 1, "o aviso do resolvido sai da Central")
    r = local.get(f"/api/servicos/{s_maria}/conflitos").json()
    checar(any(x["id"] == lados["id"] and x["estado"] == "resolvido" for x in r["conflitos"]), "conferir de novo não reabre o resolvido")
    v = local.get(f"/api/clientes/{alfa}/visao").json()
    checar(any(x["id"] == lados["id"] for x in v["conflitos_resolvidos"]), "a visão do cliente mostra os resolvidos", v["conflitos_resolvidos"])
    r = local.post(f"/api/conflitos/{lados['id']}/reabrir").json()
    checar(r["conflito"]["estado"] == "aberto" and "Reaberto por Dra. Ana Titular" in r["conflito"]["nota"], "reabrir volta, com a anotação")
    local.post(f"/api/conflitos/{lados['id']}/resolver", json={"resolucao": "autorizado", "nota": "Termo assinado."})

    print("\na muralha e o que deixa de existir")
    mur = next(c for c in abertos() if c["tipo"] == "muralha")
    local.post(f"/api/conflitos/{mur['id']}/resolver", json={"resolucao": "muralha"})
    local.get(f"/api/servicos/{s_maria}/conflitos")
    m = base.um("SELECT * FROM conflitos WHERE id = ?", (mur["id"],))
    checar(m["estado"] == "aberto" and "continua nas duas equipes" in m["nota"], "muralha dada por aplicada, com a pessoa ainda lá: reabre", dict(m))
    base.escrever("UPDATE servicos SET equipe = '[]' WHERE id = ?", (s_alfa,))
    d = local.get("/api/conflitos?conferir=true").json()
    m = base.um("SELECT * FROM conflitos WHERE id = ?", (mur["id"],))
    checar(m["estado"] == "resolvido" and m["resolucao"] == "sumiu" and m["resolvido_por"] == "PAULUS" and d["conferido"]["fechados_sozinhos"] == 1,
           "a pessoa saiu: a conferência geral fecha sozinha, dito", dict(m))
    local.post(f"/api/conflitos/{lados['id']}/reabrir")
    local.put(f"/api/servicos/{s_maria}/partes", json={"partes": []})
    local.get("/api/conflitos?conferir=true")
    l = base.um("SELECT * FROM conflitos WHERE id = ?", (lados["id"],))
    checar(l["estado"] == "resolvido" and l["resolucao"] == "sumiu", "a parte saiu do Serviço: fecha sozinho", dict(l))
    local.put(f"/api/servicos/{s_maria}/partes", json={"partes": partes})
    l = base.um("SELECT * FROM conflitos WHERE id = ?", (lados["id"],))
    checar(l["estado"] == "aberto" and "voltou a aparecer" in l["nota"], "a parte voltou: reabre, dito", dict(l))

    print("\nde fora")
    checar(all(politicas.de(m_, r_) == politicas.BLOQUEADO for m_, r_ in (("GET", "/api/conflitos"), ("GET", "/api/conflitos/{id_}"),
                                                                           ("POST", "/api/conflitos/{id_}/resolver"),
                                                                           ("POST", "/api/conflitos/{id_}/reabrir"))),
           "as rotas são da janela do escritório")

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
                pag.wait_for_function("() => typeof mostrarConflitos === 'function' && typeof mostrarCadastros === 'function'")
                pag.wait_for_timeout(800)
                pag.evaluate("() => { mostrarCadastros(); }")
                pag.wait_for_selector("[data-cfl-lista]", timeout=15000)
                pag.click("[data-cfl-lista]")
                pag.wait_for_selector(".cfl-dialogo .cfl-linha", timeout=15000)
                texto = pag.inner_text(".cfl-dialogo")
                checar("Abertos · 1" in texto and "Resolvidos" in texto and "Deixou de existir" in texto, "Cadastros › Conflitos: abertos e resolvidos", texto[:400])
                pag.wait_for_timeout(400)
                pag.screenshot(path=str(TMP / "n4-lista.png"))
                pag.click(".cfl-dialogo .cfl-linha:not(.resolvido) [data-cfl-abrir]")
                pag.wait_for_selector("[data-cfl-como]", timeout=10000)
                pag.check("[data-cfl-como][value='recusado']")
                pag.fill("#cfl-nota", "Deixamos a ação da Maria.")
                pag.wait_for_timeout(300)
                pag.screenshot(path=str(TMP / "n4-resolver.png"))
                pag.click("#veu-dialogo [data-dialogo='confirmar']")
                pag.wait_for_timeout(1000)
                l = base.um("SELECT * FROM conflitos WHERE id = ?", (lados["id"],))
                checar(l["estado"] == "resolvido" and l["resolucao"] == "recusado" and "Deixamos" in l["nota"], "resolver pela caixa", dict(l))
                local.post(f"/api/conflitos/{lados['id']}/reabrir")
                pag.evaluate(f"() => {{ abrirAviso({{ destino: {{ tela: 'conflito', id: {lados['id']} }} }}); }}")
                pag.wait_for_selector("[data-cfl-como]", timeout=10000)
                checar(True, "o aviso da Central abre a caixa de resolver")
                pag.keyboard.press("Escape")
                pag.wait_for_timeout(400)
                pag.set_viewport_size({"width": 390, "height": 844})
                pag.evaluate("() => { mostrarCadastros(); }")
                pag.wait_for_timeout(1200)
                largura = pag.evaluate("() => document.documentElement.scrollWidth")
                checar(largura <= 392, "Cadastros no celular (390 px), com o botão novo, não vaza", largura)
                checar(not erros, "nenhum erro de JavaScript", erros[:3])
                print(f"  (fotos em {TMP})")
                nav.close()

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for x in _falhas:
            print(f"    - {x}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
