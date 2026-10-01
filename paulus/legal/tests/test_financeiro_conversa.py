"""
O Financeiro e o Relatório pela conversa (pacote de telas: `Conversa -
Financeiro` e `Conversa - Relatorio`; src/financeiro_pela_conversa.py,
js/88-financeiro-na-conversa.js).

  - a frase vira "financeiro" ou "relatório", com o mês e o mês de
    comparação; "abra o financeiro" não vira
  - os números são somados aqui; a comparação é no mesmo período
  - na tela: os cinco números, o fluxo de seis meses, o que está a receber
    e a pagar; na coluna, o parecer do modelo (sobre a conta feita), os
    papéis e as sugestões; o relatório nasce com o PDF e a planilha no
    Acervo, e o envio por e-mail pede o sim e vai para Aprovações

    python tests/test_financeiro_conversa.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-fnc-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

import financeiro_pela_conversa as fpc  # noqa: E402

CAPTURAS = Path(os.environ.get("PAULUS_CAPTURAS", str(TMP)))
_falhas: list[str] = []
HOJE = date.today()
MES = HOJE.strftime("%Y-%m")
ANTES = fpc.mes_antes(MES)


def checar(condicao, descricao: str, detalhe="") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHOU  {descricao}  -> {detalhe}")
        _falhas.append(descricao)


def test_regras() -> None:
    print("\nas regras")
    h = date(2026, 10, 1)
    checar(fpc.ler("como está o financeiro do mês?", h) == {"tipo": "financeiro", "mes": "2026-10", "comparar": "2026-09"}, "o financeiro do mês")
    checar(fpc.ler("gera o relatório financeiro de outubro e compara com agosto", h) == {"tipo": "relatorio", "mes": "2026-10", "comparar": "2026-08"},
           "o relatório, com o mês de comparação")
    checar(fpc.ler("abra o financeiro", h) is None and fpc.ler("qual a multa do contrato?", h) is None, "abrir a tela e outra pergunta não viram")
    checar(fpc.ler("me mostra o resumo do caixa de dezembro", h)["mes"] == "2025-12", "mês que ainda não chegou é do ano passado")


class _Modelo:
    model = "duble"

    def ask(self, pergunta, contexto="", **_):
        self.ultimo = contexto
        return "Outubro vai bem: as entradas cobrem as saídas. O ponto de atenção são as custas que vencem hoje."


def _semear(e) -> None:
    rio = e.cadastros.salvar({"tipo": "cliente", "nome": "Cooperativa Rio Fresco", "email": "contabil@riofresco.coop.br"})
    dia = f"{HOJE.day:02d}"
    e.financeiro.salvar({"tipo": "recebimento", "descricao": "Honorários · parcela 3/10", "centavos": 1200000, "categoria": "honorarios",
                         "cadastro_id": rio, "vencimento": f"{MES}-{dia}", "liquidado_em": f"{MES}-{dia}"})
    e.financeiro.salvar({"tipo": "despesa", "descricao": "Aluguel · sala 204", "centavos": 450000, "categoria": "aluguel",
                         "vencimento": f"{MES}-{dia}", "liquidado_em": f"{MES}-{dia}"})
    e.financeiro.salvar({"tipo": "despesa", "descricao": "Custas iniciais", "centavos": 124000, "categoria": "custas", "vencimento": HOJE.isoformat()})
    e.financeiro.salvar({"tipo": "recebimento", "descricao": "Honorários · parcela 4/6", "centavos": 380000, "categoria": "honorarios",
                         "cadastro_id": rio, "vencimento": f"{MES}-28"})
    e.financeiro.salvar({"tipo": "recebimento", "descricao": "Honorários · setembro", "centavos": 1000000, "categoria": "honorarios",
                         "vencimento": f"{ANTES}-01", "liquidado_em": f"{ANTES}-01"})


def test_soma() -> None:
    print("\nos números")
    import api

    e = api.estado
    _semear(e)
    r = fpc.relatorio(e.financeiro, e.base, MES, ANTES)
    checar((r["entradas"], r["saidas"], r["resultado"]) == (1200000, 450000, 750000), "entradas, saídas e resultado do mês", r)
    checar(r["comparacao"]["entradas"] == (1000000 if HOJE.day >= 1 else 0) and r["comparacao"]["ate_o_dia"] == HOJE.day,
           "a comparação no mesmo período", r["comparacao"])
    frase = fpc.frase_do_relatorio(r)
    checar(frase.startswith(f"Somei os lançamentos de {fpc.rotulo_do_mes(MES)} até hoje. O resultado está positivo em R$ 7.500"), "a frase do relatório", frase)


def test_tela() -> None:
    print("\nna tela (Edge pelo Playwright)")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return
    import api
    import correio_contas
    from test_gravacoes import _porta_livre, _subir_servidor

    e = api.estado
    modelo = _Modelo()
    e.cliente_para = lambda *_a, **_k: modelo
    api.check_ollama = lambda *_a, **_k: (True, "ok")
    e.contas = correio_contas.Contas(TMP / "contas.json")
    conta = e.contas.salvar_conta({"email": "advogado@escritorio.adv.br", "imap_host": "imap.x", "smtp_host": "smtp.x"}, "senha")
    e.contas.lembrar(conta.id, "senha")
    porta = _porta_livre()
    _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"
    with sync_playwright() as p:
        try:
            nav = p.chromium.launch(channel="msedge")
        except Exception as exc:  # noqa: BLE001
            print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            return
        pag = nav.new_page(viewport={"width": 1984, "height": 1064})
        pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
        erros: list[str] = []
        pag.on("pageerror", lambda x: erros.append(str(x)))
        pag.goto(base + "/entrar-local?chave=" + e.acesso.chave, wait_until="networkidle")
        pag.wait_for_timeout(800)

        pag.fill("#pedido", "como está o financeiro do mês?")
        pag.click("#enviar")
        pag.wait_for_selector("#lado-ferramenta [data-fl-tipo='financeiro']", timeout=20000)
        pag.wait_for_function("() => document.querySelector('#lado-ferramenta .fnc-secao p') && !document.querySelector('#lado-ferramenta .em-andamento')", timeout=10000)
        t = pag.evaluate("""() => ({frase: [...document.querySelectorAll('#centro .resposta .texto')].map(t => t.textContent).pop(),
          kpis: document.querySelectorAll('.fnc-kpis .lcn-kpi').length, barras: document.querySelectorAll('.fnc-mes').length,
          receber: [...document.querySelectorAll('.fnc-lista')][0].querySelectorAll('.fnc-item').length,
          parecer: document.querySelector('#lado-ferramenta .fnc-secao p').textContent,
          tiles: document.querySelectorAll('#lado-ferramenta .fnc-tile').length,
          sugestoes: document.querySelectorAll('#lado-ferramenta .fnc-sugestoes li').length,
          precisa: (document.querySelector('#lado-ferramenta .fnc-precisa') || {}).textContent || '',
          ph: document.getElementById('pedido').placeholder})""")
        checar("Entraram R$ 12.000 e saíram R$ 4.500" in t["frase"] and "uma conta precisa de você hoje" in t["frase"], "a frase dos números do mês", t["frase"])
        checar(t["kpis"] == 5 and t["barras"] == 6 and t["receber"] >= 1, "os cinco números, o fluxo de seis meses e as listas", t)
        checar(t["parecer"].startswith("Outubro vai bem") and "Entradas: R$ 12.000,00" in getattr(modelo, "ultimo", ""),
               "o parecer do modelo, escrito sobre a conta feita", getattr(modelo, "ultimo", "")[:120])
        checar(t["tiles"] == 4 and t["sugestoes"] >= 1 and "Custas iniciais" in t["precisa"], "os papéis, as sugestões e o que precisa de você", t)
        checar(t["ph"] == "Pergunte sobre os números, ou peça um relatório…", "a caixa de pedido", t["ph"])
        pag.wait_for_timeout(900)
        pag.screenshot(path=str(CAPTURAS / "t4-financeiro.png"))

        pag.click("#nova")
        pag.wait_for_timeout(500)
        nome_mes = fpc.rotulo_do_mes(MES)
        pag.fill("#pedido", f"gera o relatório financeiro de {nome_mes} e compara com {fpc.rotulo_do_mes(ANTES)}")
        pag.click("#enviar")
        pag.wait_for_selector("#lado-ferramenta [data-fl-tipo='relatorio']", timeout=20000)
        pag.wait_for_selector(".fnc-relatorio", timeout=10000)
        pag.wait_for_timeout(800)
        r = pag.evaluate("""() => ({frase: [...document.querySelectorAll('#centro .resposta .texto')].map(t => t.textContent).pop(),
          links: [...document.querySelectorAll('.fnc-relatorio a.emc-botao')].map(a => a.getAttribute('href')),
          cats: [...document.querySelectorAll('.fnc-cat span:first-child')].map(s => s.textContent),
          contra: (document.querySelector('.fnc-contra') || {}).textContent || '',
          envio: (document.querySelector('#lado-ferramenta .fnc-secao-cabeca small') || {}).textContent})""")
        checar(r["frase"].endswith("O PDF e a planilha estão prontos para baixar."), "a frase do relatório", r["frase"])
        prontos = pag.evaluate("""async (hrefs) => Promise.all(hrefs.map(async h => { const x = await fetch(h); return [x.status, x.headers.get('content-type')]; }))""", r["links"])
        checar(len(r["links"]) == 2 and all(s == 200 for s, _ in prontos) and "pdf" in prontos[0][1], "o PDF e a planilha baixam", prontos)
        checar("Honorários" in r["cats"] and "Aluguel" in r["cats"] and "Contra" in r["contra"], "as categorias e a comparação", r)
        pag.screenshot(path=str(CAPTURAS / "t4-relatorio.png"))
        pag.fill("#lado-ferramenta [data-fnc-add]", "contabil@riofresco.coop.br")
        pag.keyboard.press("Enter")
        pag.wait_for_selector("#lado-ferramenta .fnc-para .emc-chip", timeout=5000)
        pag.click("#lado-ferramenta [data-fnc-enviar]")
        pag.wait_for_selector("#veu-dialogo .dialogo", timeout=5000)
        checar("Vai para Aprovações" in pag.evaluate("() => document.getElementById('veu-dialogo').textContent"), "enviar pede o sim e diz que vai para Aprovações")
        pag.click("#veu-dialogo [data-dialogo='confirmar']")
        pag.wait_for_selector(".nota-feito", timeout=8000)
        pedidos = [x for x in e.fila.pendentes if x.categoria == "email"]
        anexos = (pedidos[-1].dados or {}).get("anexos", []) if pedidos else []
        checar(pedidos and len(anexos) == 2 and anexos[0].endswith(".pdf") and anexos[1].endswith(".xlsx"), "o pedido em Aprovações leva o PDF e a planilha", anexos)

        pag.set_viewport_size({"width": 390, "height": 844})
        pag.wait_for_timeout(500)
        checar(pag.evaluate("() => document.documentElement.scrollWidth") <= 392, "sem rolagem horizontal em 390 px")
        checar(not erros, "nenhum erro de JavaScript", erros[:3])
        nav.close()


if __name__ == "__main__":
    test_regras()
    test_soma()
    test_tela()
    print("\n" + "=" * 60)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print("    - " + f)
        sys.exit(1)
    print("  todos os testes passaram")
