"""
O padrão das listas: selecionar, marcar todas pela caixa da barra e o
menu do botão direito - em todas as listas do programa (27/09/2026).

Para cada lista confere:
  - nenhuma caixinha nas linhas; a linha escolhida tem a barra lateral;
  - Ctrl+clique marca, e a caixa da barra mostra o traço ("parte");
  - clicar na caixa marca todas; clicar de novo limpa, e a barra some;
  - o botão direito numa linha abre o menu do "…" no ponto do clique.

Roda na base de demonstração (data/demo), criada se não existir, e apaga o
que cria. O E-mail fica de fora: precisa de uma conta conectada.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_listas.py
"""
import subprocess
import os, sys, json
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
if not (RAIZ / "data" / "demo" / "paulus.db").exists():
    subprocess.run([sys.executable, str(RAIZ / "tools" / "demo" / "criar_demo.py")], check=True)
os.environ["PAULUS_DADOS"] = str(RAIZ / "data" / "demo")
sys.path.insert(0, str(RAIZ / "src")); sys.path.insert(0, str(RAIZ / "tests"))
from test_gravacoes import _porta_livre, _subir_servidor, Cliente
import api
from playwright.sync_api import sync_playwright

porta = _porta_livre(); _subir_servidor(porta); base = f"http://127.0.0.1:{porta}"
c = Cliente(porta)
criados = [c.pedir("POST", "/api/trabalhos", {"pedido": f"conversa de teste {i}"})[1]["id"] for i in range(3)]
pedidos = [api.estado.fila.pedir(f"Teste de lista {i}", "email", resumo="teste", reversivel=True).id for i in range(2)]
docs = [c.pedir("POST", "/api/documentos", {"titulo": f"Teste de lista {i}", "tipo": "texto", "corpo": "<p>x</p>"})[1]["id"] for i in range(2)]
pdfs = [c.pedir("POST", f"/api/documentos/{i}/biblioteca", {})[1].get("caminho", "") for i in docs]
gravs = [api.estado.gravacoes.guardar({"titulo": f"Teste de lista {i}", "tipo": "reuniao"}, b"RIFF0000WAVE", "teste.wav") for i in range(2)]
saida = os.environ["TEMP"]
falhas = []

def checar(ok, nome, det=None):
    print(("ok   " if ok else "FALHA ") + nome + ("" if ok or det is None else f"  -> {det}"))
    if not ok: falhas.append(nome)

ESTADO_BARRA = """() => { const b = document.querySelector('[data-selecao-alternar]');
  return b ? {parte: b.classList.contains('parte'), icone: b.textContent.trim(), limpar: !!document.querySelector('.selecao .limpar'),
              n: (document.querySelector('.selecao-conta')||{}).textContent} : null; }"""

def exercitar(pag, nome, abrir, linhas):
    pag.evaluate(abrir); pag.wait_for_timeout(1800)
    rows = pag.locator(linhas)
    total = rows.count()
    if total < 2:
        checar(False, f"{nome}: tem ao menos 2 linhas", total); return
    checar(pag.locator(linhas + " .marcar").count() == 0, f"{nome}: sem caixinha nas linhas")
    rows.nth(0).click(modifiers=["Control"]); pag.wait_for_timeout(400)
    e = pag.evaluate(ESTADO_BARRA)
    checar(e and e["parte"] and not e["limpar"], f"{nome}: Ctrl+clique marca, a caixa mostra 'parte' e não há Limpar/Selecionar em texto", e)
    checar(pag.locator(linhas + ".escolhida").count() == 1, f"{nome}: a linha marcada tem a barra lateral (.escolhida)")
    pag.click("[data-selecao-alternar]"); pag.wait_for_timeout(400)
    e = pag.evaluate(ESTADO_BARRA)
    checar(e and not e["parte"] and pag.locator(linhas + ".escolhida").count() == pag.locator(linhas).count(),
           f"{nome}: a caixa marca todas", e)
    pag.click("[data-selecao-alternar]"); pag.wait_for_timeout(400)
    checar(pag.locator(linhas + ".escolhida").count() == 0 and pag.evaluate(ESTADO_BARRA) is None, f"{nome}: clicar de novo limpa")
    caixa = rows.nth(1).bounding_box()
    x, y = caixa["x"] + caixa["width"] * 0.4, caixa["y"] + caixa["height"] / 2
    pag.mouse.click(x, y, button="right"); pag.wait_for_timeout(400)
    menu = pag.evaluate("() => { const m = [...document.querySelectorAll('.menu-conversa:not(.menu-sub)')].pop(); if (!m) return null; const r = m.getBoundingClientRect(); return {x: r.left, y: r.top, itens: [...m.querySelectorAll('button')].map(b => b.textContent.trim()).slice(0, 8)}; }")
    checar(menu is not None and abs(menu["x"] - x) < 6 and abs(menu["y"] - y) < 6, f"{nome}: botão direito abre o menu no ponto clicado", menu)
    pag.keyboard.press("Escape"); pag.mouse.click(5, 5); pag.wait_for_timeout(300)

with sync_playwright() as pw:
    nav = pw.chromium.launch(); pag = nav.new_page(viewport={"width": 1440, "height": 900})
    pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
    erros = []; pag.on("pageerror", lambda e: erros.append(str(e)))
    pag.goto(base, wait_until="networkidle"); pag.wait_for_timeout(2000)
    exercitar(pag, "Assistente", "() => { voltarAoAssistente(); setTimeout(() => alternarListaDeConversas(true), 300); }", "#lista-conversas .lc-linha[data-sel]")
    exercitar(pag, "Cadastros", "() => abrirDestino('cadastros')", "#cad-tela .tabela-linha[data-sel]")
    exercitar(pag, "Lançamentos", "() => mostrarFinanceiro('lancamentos')", "#financeiro .tabela-linha[data-sel]")
    exercitar(pag, "Tarefas", "() => abrirDestino('tarefas')", ".ag-tarefas .ag-linha[data-sel]")
    exercitar(pag, "Serviços", "() => abrirDestino('servicos')", "#sv-tela .sv-pasta[data-sel]")
    exercitar(pag, "Aprovações", "() => abrirDestino('aprovacoes')", "#ap-fila .tabela-linha[data-pedido]")
    exercitar(pag, "Documentos", "() => mostrarDocumentos('lista')", ".tabela-linha[data-sel][data-doc-id], #centro .tabela-linha[data-sel]")
    exercitar(pag, "Assinatura", "() => mostrarAssinar()", "[data-pdf]")
    exercitar(pag, "Gravações", "() => mostrarGravacoes('lista')", "#gv-tela .tabela-linha[data-sel]")
    exercitar(pag, "Acervo", "() => abrirDestino('biblioteca')", ".ae-tela .tabela-linha[data-doc]")
    checar(not erros, "nenhum erro de JavaScript", erros[:3])
    nav.close()

for i in criados:
    c.pedir("DELETE", f"/api/trabalhos/{i}")
for i in gravs:
    st, r = c.pedir("DELETE", f"/api/gravacoes/{i}")
    if isinstance(r, dict) and r.get("lixeira"):
        c.pedir("DELETE", f"/api/lixeira/{r['lixeira']}")
for caminho in pdfs:
    if caminho and Path(caminho).exists():
        Path(caminho).unlink()
for i in pedidos:
    api.estado.fila.esquecer(i)
for i in docs:
    st, r = c.pedir("DELETE", f"/api/documentos/{i}")
    if isinstance(r, dict) and r.get("lixeira"):
        c.pedir("DELETE", f"/api/lixeira/{r['lixeira']}")
print("\n  " + (f"{len(falhas)} FALHA(S): {falhas}" if falhas else "todos os testes passaram"))
sys.exit(1 if falhas else 0)
