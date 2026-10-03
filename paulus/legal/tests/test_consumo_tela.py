"""
A tela Plano e consumo (js/91-plano-consumo.js, desenho A24 · Assinatura v2)
no Edge, pelo Playwright, com a conta da nuvem simulada (sem rede):

  - o consumo do ciclo: o número, a barra com a marca do dia e a ficha
    (Restantes, Hoje, Da recarga, Ritmo);
  - a equipe com papel e limite; a linha abre o histórico e as ações
    (limite, permissões, titular, tirar o acesso);
  - os limites com o uso; o plano em quatro colunas e a recarga com uso alto;
  - o extrato (por área e por pessoa) e os planos em três colunas;
  - sem erro de página, no claro, no escuro e no celular (390 px).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_consumo_tela.py

As capturas ficam em CONSUMO_CAPTURAS (ou numa pasta temporária).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-consumo-tela-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))
CAPTURAS = Path(os.environ.get("CONSUMO_CAPTURAS") or (TMP / "capturas"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def _conta_simulada() -> dict:
    agora = datetime.now()
    inicio, fim = agora - timedelta(days=18), agora + timedelta(days=12)
    planos = [{"id": "advogado", "nome": "Advogado", "valor": 150, "tokens": 12_000_000},
              {"id": "escritorio", "nome": "Escritório", "valor": 300, "tokens": 30_000_000},
              {"id": "plus", "nome": "Escritório Plus", "valor": 550, "tokens": 60_000_000}]
    return {"ok": True, "email": "titular@escritorio.adv.br", "cortesia": False, "plano_vigente": True,
            "assinatura": {"id": "pre1", "situacao": "authorized", "valor": 300, "desde": (agora - timedelta(days=80)).isoformat()},
            "plano": planos[1], "plano_proximo": None, "planos": planos,
            "recargas_pacotes": [{"id": "p5", "tokens": 5_000_000, "valor": 25}, {"id": "p10", "tokens": 10_000_000, "valor": 50},
                                 {"id": "p20", "tokens": 20_000_000, "valor": 100}],
            "ciclo": {"inicio": inicio.isoformat(), "fim": fim.isoformat(), "tokens": 30_000_000, "usados": 22_200_000},
            "tokens": {"restantes": 7_800_000, "hoje": 1_350_000, "da_recarga": 0},
            "recargas": [{"pedido": "r1", "tokens": 5_000_000, "valor": 25, "quando": (agora - timedelta(days=40)).isoformat()}]}


def preparar(api) -> None:
    import consumo
    import nuvem

    e = api.estado
    contas = e.acesso_de_fora.contas
    # A primeira conta criada vira titular (src/acesso/contas.py).
    contas.criar("Ana Titular", "ana@escritorio.adv.br", "titular")
    contas.criar("João Bastos", "joao@escritorio.adv.br", "colaborador")
    contas.criar("Maria Tavares", "maria@escritorio.adv.br", "colaborador")
    ids = {c["nome"]: c["id"] for c in contas.listar()}
    agora = datetime.now()
    h = lambda **k: (agora - timedelta(**k)).isoformat(timespec="seconds")  # noqa: E731
    linhas = [
        {"quando": h(minutes=40), "tarefa": "conversa", "trabalho_id": "t1", "pessoa": {"conta_id": ids["João Bastos"], "nome": "João Bastos"},
         "pergunta": "Elabore uma contestação para a ação de cobrança do caso Mendes", "tokens_entrada": 9000, "tokens_saida": 2400},
        {"quando": h(hours=3), "tarefa": "redacao", "pessoa": {"conta_id": ids["João Bastos"], "nome": "João Bastos"},
         "pergunta": "Redação no editor", "tokens_entrada": 4000, "tokens_saida": 900},
        {"quando": h(days=1), "tarefa": "conversa", "trabalho_id": "t2", "pessoa": {"conta_id": ids["Maria Tavares"], "nome": "Maria Tavares"},
         "pergunta": "Calcule verbas rescisórias com base nesta CTPS", "tokens_entrada": 7000, "tokens_saida": 1500},
        {"quando": h(minutes=5), "tarefa": "resumos", "pessoa": {"conta_id": 0, "nome": "Janela"},
         "pergunta": "Resumos de serviços e gravações", "tokens_entrada": 2000, "tokens_saida": 400},
    ]
    pasta = nuvem._pasta(e)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "envios.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in linhas), encoding="utf-8")
    consumo.guardar_limites(e, {"diario": 0, "mensal": 25_000_000, "pessoas": {str(ids["João Bastos"]): {"diario": 0, "mensal": 20_000}}})
    conta = _conta_simulada()
    nuvem.conta_paulus = lambda estado, forcar=False: (nuvem._CONTA_CACHE.update(dados=conta) or conta)


def main() -> int:
    print("=" * 55)
    print("  Plano e consumo — a tela")
    print("=" * 55)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return 0
    from test_gravacoes import _porta_livre, _subir_servidor

    import api

    try:
        preparar(api)
        porta = _porta_livre()
        _subir_servidor(porta)
        base = f"http://127.0.0.1:{porta}"
        CAPTURAS.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            try:
                nav = p.chromium.launch(channel="msedge")
            except Exception as exc:  # noqa: BLE001
                print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
                return 0
            # Um contexto só: a chave da janela entra uma vez; as outras páginas usam o cookie.
            ctx = nav.new_context(viewport={"width": 1440, "height": 1000})
            ctx.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
            ctx.set_default_timeout(60000)
            pag = ctx.new_page()
            erros: list[str] = []
            pag.on("pageerror", lambda e: erros.append(str(e)))
            pag.goto(base + "/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
            pag.wait_for_function("() => typeof mostrarConsumo === 'function' && typeof acessoDeFora !== 'undefined'")
            pag.evaluate("() => acessoDeFora.pronto")
            for tema in ("claro", "escuro"):
                print(f"\nno tema {tema}")
                pag.evaluate("() => { aplicarTema('" + tema + "'); mostrarConsumo(); }")
                pag.wait_for_selector(".pc-pessoa-linha", timeout=20000)
                pag.wait_for_timeout(600)
                pag.screenshot(path=str(CAPTURAS / f"consumo-{tema}.png"), full_page=True)
                pag.evaluate("() => { const r = document.querySelector('#pc-tela .sv-principal'); r.scrollTop = r.scrollHeight; }")
                pag.wait_for_timeout(200)
                pag.screenshot(path=str(CAPTURAS / f"consumo-{tema}-plano.png"))
                ficha = pag.evaluate("() => [...document.querySelectorAll('.pc-ficha .sv-kicker')].map(x => x.textContent)")
                checar(ficha[:4] == ["Restantes", "Hoje", "Da recarga", "Ritmo"], "a ficha do ciclo em faixa", ficha)
                checar(pag.locator(".pc-marca").count() == 1, "a barra tem a marca do dia")
                checar("acima do esperado" in pag.inner_text(".pc-geral"), "74% usado com 60% do ciclo: o ritmo está acima")
                nomes = pag.evaluate("() => [...document.querySelectorAll('.pc-pessoa-linha .pc-quem b')].map(x => x.textContent)")
                checar(nomes[0] == "João Bastos" and "Maria Tavares" in nomes, "a equipe, de quem gasta mais", nomes)
                papel = pag.evaluate("() => [...document.querySelectorAll('.pc-pessoa-linha .pc-quem small')].map(x => x.textContent)")
                checar("titular" in papel and any(x.startswith("colaborador") for x in papel), "com o papel de cada um", papel)
                checar("perto do limite mensal (82%)" in pag.inner_text(".pc-equipe"), "o João está a 82% do limite próprio: a linha avisa")
                plano = pag.evaluate("() => [...document.querySelectorAll('.pc-ficha-plano .sv-kicker')].map(x => x.textContent)")
                checar(plano == ["Próxima cobrança", "Pagamento", "Nota fiscal", "Pessoas"], "o plano em quatro colunas", plano)
                checar(pag.locator("[data-pc-recarga]").count() == 3, "com 74% usado, a recarga rápida aparece")
                checar(pag.locator("[data-pc-cancelar]").count() == 1, "cancelar a assinatura, no rodapé do plano")

                pag.click('.pc-pessoa-linha[data-pc-pessoa]')
                pag.wait_for_selector(".pc-historico .pc-item", timeout=10000)
                checar("Elabore uma contestação" in pag.inner_text(".pc-historico"), "a linha abre o histórico com o começo da pergunta")
                acoes = pag.evaluate("() => [...document.querySelectorAll('.pc-pessoa-acoes button')].map(x => x.textContent)")
                checar(acoes == ["Ajustar limite", "Permissões", "Tornar titular", "Tirar o acesso"], "e as ações da pessoa", acoes)
                pag.screenshot(path=str(CAPTURAS / f"consumo-{tema}-historico.png"), full_page=True)

                pag.click("#acoes-tela [data-pc-extrato]")
                pag.wait_for_selector(".pc-extrato", timeout=10000)
                texto = pag.inner_text(".dialogo")
                checar(all(x in texto.lower() for x in ("por área", "por pessoa", "perguntas sobre documentos", "pela conta do plano")),
                       "o extrato por área e por pessoa, com o custo pela conta do plano", texto[-400:])
                pag.wait_for_timeout(700)
                pag.screenshot(path=str(CAPTURAS / f"consumo-{tema}-extrato.png"))
                pag.click('.dialogo [data-dialogo="cancelar"]')
                pag.wait_for_timeout(400)

                pag.click("#acoes-tela [data-pc-upgrade]")
                pag.wait_for_selector(".pc-planos", timeout=10000)
                cols = pag.evaluate("() => [...document.querySelectorAll('.pc-plano-col button')].map(x => [x.textContent, x.disabled])")
                checar(cols == [["Reduzir para o Advogado", False], ["Plano atual", True], ["Mudar para o Escritório Plus", False]],
                       "os planos em três colunas, com o atual travado", cols)
                pag.wait_for_timeout(700)
                pag.screenshot(path=str(CAPTURAS / f"consumo-{tema}-planos.png"))
                pag.click('.dialogo [data-dialogo="confirmar"]')
                pag.wait_for_timeout(400)

                pag.click(".pc-secao [data-pc-limites]")
                pag.wait_for_selector(".pc-limites", timeout=10000)
                checar(pag.locator(".pc-limite-linha").count() >= 3, "o modal dos limites, com o escritório e cada pessoa")
                pag.wait_for_timeout(700)
                pag.screenshot(path=str(CAPTURAS / f"consumo-{tema}-limites.png"))
                pag.click('.dialogo [data-dialogo="cancelar"]')
                pag.wait_for_timeout(300)
                checar(not erros, "sem erro na página", erros)

            print("\nno celular")
            pc = ctx.new_page()
            pc.set_viewport_size({"width": 390, "height": 844})
            erros_cel: list[str] = []
            pc.on("pageerror", lambda e: erros_cel.append(str(e)))
            pc.goto(base + "/", wait_until="load")
            pc.wait_for_function("() => typeof mostrarConsumo === 'function' && typeof acessoDeFora !== 'undefined'")
            pc.evaluate("() => acessoDeFora.pronto")
            pc.evaluate("() => { mostrarConsumo(); }")
            pc.wait_for_selector(".pc-pessoa-linha", timeout=20000)
            pc.wait_for_timeout(500)
            largura = pc.evaluate("() => document.documentElement.scrollWidth")
            checar(largura <= 390, "sem rolagem para o lado em 390 px", largura)
            pc.screenshot(path=str(CAPTURAS / "consumo-celular.png"), full_page=True)
            checar(not erros_cel, "sem erro na página", erros_cel)
            nav.close()
        print(f"\n  capturas em {CAPTURAS}")
    finally:
        if not os.environ.get("CONSUMO_CAPTURAS"):
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
