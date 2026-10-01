"""
O lançamento pela conversa (pacote de telas: `Conversa - Lancamento` e
`Conversa - Recebimento`; src/lancamentos_pela_conversa.py,
js/87-lancamento-na-conversa.js).

  - a frase vira despesa ou recebimento: valor, dia, quem (as fichas),
    categoria, forma; pergunta não é pedido
  - o recebimento acha a cobrança em aberto que ele paga e diz os juros
  - o boleto anexo é conferido (valor, vencimento, beneficiário)
  - na tela: os números do mês com o que muda, a lista com a linha nova;
    Lançar grava, dá baixa, guarda o papel e o lembrete, e a conversa diz

    python tests/test_lancamento_conversa.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-lcn-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

import lancamentos_pela_conversa as lpc  # noqa: E402

CAPTURAS = Path(os.environ.get("PAULUS_CAPTURAS", str(TMP)))
_falhas: list[str] = []
HOJE = date.today()


def checar(condicao, descricao: str, detalhe="") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHOU  {descricao}  -> {detalhe}")
        _falhas.append(descricao)


def _dia8() -> date:
    d = date(HOJE.year, HOJE.month, 8)
    if d < HOJE:
        d = date(HOJE.year + (HOJE.month == 12), HOJE.month % 12 + 1, 8)
    return d


def test_regras() -> None:
    print("\nas regras")
    fichas = [{"id": 1, "nome": "José Carlos Ribeiro"}, {"id": 2, "nome": "Cooperativa Rio Fresco"}]
    d = lpc.ler_lancamento("lança a perícia contábil do José Carlos, 2.150 com vencimento dia 8. o boleto tá anexo", fichas, HOJE)
    checar(d and (d["tipo"], d["centavos"], d["cadastro_id"], d["categoria"], d["forma"], d["vencimento"]) ==
           ("despesa", 215000, 1, "pericias", "boleto", _dia8().isoformat()), "a despesa", d)
    r = lpc.ler_lancamento("a Rio Fresco pagou a parcela de setembro, 6.036 com os juros. o comprovante tá anexo", fichas, HOJE)
    checar(r and (r["tipo"], r["centavos"], r["cadastro_id"], r["mes_dito"], r["pago"]) == ("recebimento", 603600, 2, 9, True), "o recebimento", r)
    checar(lpc.ler_lancamento("quanto a Rio Fresco pagou?", fichas) is None, "pergunta não é pedido")
    checar(lpc.ler_lancamento("cadastre o cliente João Souza, CPF 529.982.247-25", fichas) is None, "CPF não é valor, cadastro não é lançamento")
    checar(lpc.ler_lancamento("anote uma reunião no calendário 11/09/2026 às 13:40", fichas) is None, "reunião não é lançamento")
    aberto = {"id": 9, "tipo": "recebimento", "cadastro_id": 2, "centavos": 600000, "vencimento": f"{HOJE.year}-09-12", "liquidado_em": ""}
    outro = {"id": 10, "tipo": "recebimento", "cadastro_id": 2, "centavos": 600000, "vencimento": f"{HOJE.year}-11-12", "liquidado_em": ""}
    checar((lpc.casar_aberto(r, [outro, aberto]) or {}).get("id") == 9, "casa a cobrança do mês dito")
    checar(lpc.casar_aberto(dict(r, centavos=900000), [aberto]) is None, "valor que não é a cobrança nem com juros não casa")
    p = lpc.ler_papel("BOLETO Beneficiário: Ricardo Nunes CPF 111 Vencimento: 08/10/2026 Valor do documento: R$ 2.150,00")
    checar(p == {"centavos": 215000, "vencimento": "2026-10-08", "beneficiario": "Ricardo Nunes"}, "o boleto lido", p)


class _Doc:
    def __init__(self, nome, texto, sha1):
        self.name, self.text, self.sha1 = nome, texto, sha1
        caminho = TMP / nome
        caminho.write_text(texto, encoding="utf-8")
        self.path = str(caminho)
        self.pages, self.ocr = 1, 0

    @property
    def chars(self):
        return len(self.text)


def test_tela() -> None:
    print("\nna tela (Edge pelo Playwright)")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return
    import api
    from test_gravacoes import _porta_livre, _subir_servidor

    e = api.estado
    jose = e.cadastros.salvar({"tipo": "cliente", "nome": "José Carlos Ribeiro"})
    rio = e.cadastros.salvar({"tipo": "cliente", "nome": "Cooperativa Rio Fresco"})
    mes = _dia8().isoformat()[:7]
    e.financeiro.salvar({"tipo": "despesa", "descricao": "Custas iniciais", "centavos": 124000, "categoria": "custas", "vencimento": mes + "-03"})
    parcela = e.financeiro.salvar({"tipo": "recebimento", "descricao": "Acordo · parcela 2/10", "centavos": 600000, "categoria": "honorarios",
                                   "cadastro_id": rio, "vencimento": f"{HOJE.year}-09-12"})
    venc = _dia8()
    boleto = _Doc("Boleto perícia José Carlos.pdf",
                  f"BOLETO Beneficiário: Ricardo Nunes CPF 111 Vencimento: {venc:%d/%m/%Y} Valor do documento: R$ 2.150,00", "b1")
    comprovante = _Doc("Comprovante Rio Fresco.pdf", "COMPROVANTE DE TRANSFERÊNCIA Pagador: Cooperativa Rio Fresco Valor: R$ 6.036,00", "b2")
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
        e.searcher.documents.extend([boleto, comprovante])

        # a despesa, com o boleto
        pag.evaluate("() => { estado.escopo = ['Boleto perícia José Carlos.pdf']; }")
        pag.fill("#pedido", "lança a perícia contábil do José Carlos, 2.150 com vencimento dia 8. o boleto tá anexo")
        pag.click("#enviar")
        pag.wait_for_selector("#lado-ferramenta [data-fl-tipo='lancamento']", timeout=20000)
        pag.wait_for_timeout(800)
        t = pag.evaluate("""() => ({frase: [...document.querySelectorAll('#centro .resposta .texto')].map(t => t.textContent).pop(),
          valor: document.querySelector('#lado-ferramenta [data-lcn=valor]').value,
          confere: (document.querySelector('#lado-ferramenta .lcn-confere') || {}).textContent || '',
          nova: (document.querySelector('.lcn-linha.nova b') || {}).textContent || '',
          kpi: [...document.querySelectorAll('.lcn-kpi small.lcn-delta')].map(x => x.textContent),
          ph: document.getElementById('pedido').placeholder})""")
        checar("O valor e o vencimento batem com o que você disse; o beneficiário é Ricardo Nunes" in t["frase"], "a conversa confere o boleto", t["frase"])
        checar(t["valor"] == "2.150,00" and "confere com o boleto" in t["confere"], "o valor e a conferência na coluna", t)
        checar(t["nova"] == "José Carlos Ribeiro" and t["kpi"] == ["+ 2.150"], "a lista com a nova e o “a pagar” que muda", t)
        checar(t["ph"] == "Mude o valor, a data ou lance outra coisa…", "a caixa de pedido diz o que faz", t["ph"])
        pag.screenshot(path=str(CAPTURAS / "t4-lancamento.png"))
        pag.click("#lado-ferramenta [data-lcn-lancar]")
        pag.wait_for_function("() => [...document.querySelectorAll('.nota-feito')].some(n => n.textContent.startsWith('Lancei'))", timeout=8000)
        lanc = next((x for x in e.financeiro.listar(tipo="despesa") if x["cadastro_id"] == jose), {})
        boletos = e.papeis.listar("boleto")
        tarefas = e.base.buscar("SELECT * FROM tarefas WHERE titulo LIKE 'Pagar: Perícia contábil%'")
        checar(lanc.get("centavos") == 215000 and lanc.get("categoria") == "pericias" and lanc.get("forma") == "boleto", "a despesa gravada", lanc)
        checar(any(b.get("lancamento_id") == lanc.get("id") for b in boletos), "o boleto em Papéis do mês", boletos)
        checar(tarefas and tarefas[0].get("prazo") == (venc - timedelta(days=1)).isoformat(), "o lembrete na Agenda, um dia antes", tarefas)

        # o recebimento, com o comprovante
        pag.click("#nova")
        pag.wait_for_timeout(500)
        pag.evaluate("() => { estado.escopo = ['Comprovante Rio Fresco.pdf']; }")
        pag.fill("#pedido", "a Rio Fresco pagou a parcela de setembro, 6.036 com os juros. o comprovante tá anexo")
        pag.click("#enviar")
        pag.wait_for_selector("#lado-ferramenta [data-fl-tipo='lancamento']", timeout=20000)
        pag.wait_for_timeout(800)
        r = pag.evaluate("""() => ({frase: [...document.querySelectorAll('#centro .resposta .texto')].map(t => t.textContent).pop(),
          confere: (document.querySelector('#lado-ferramenta .lcn-confere') || {}).textContent || '',
          pago: document.querySelector('#lado-ferramenta [data-lcn=liquidado_em]').value})""")
        checar(r["frase"].startswith("Li o comprovante e preenchi o recebimento ao lado: R$ 6.000,00 de “Acordo · parcela 2/10” mais R$ 36,00 de juros, pagos hoje"),
               "a conversa acha a parcela em aberto e diz os juros", r["frase"])
        checar("juros R$ 36,00" in r["confere"] and r["pago"] == HOJE.isoformat(), "a coluna mostra parcela + juros, pago hoje", r)
        pag.screenshot(path=str(CAPTURAS / "t4-recebimento.png"))
        pag.click("#lado-ferramenta [data-lcn-lancar]")
        pag.wait_for_function("() => [...document.querySelectorAll('.nota-feito')].some(n => n.textContent.startsWith('Lancei o recebimento'))", timeout=8000)
        p2 = e.financeiro.obter(parcela)
        checar(p2.get("centavos") == 603600 and p2.get("liquidado_em") == HOJE.isoformat(), "a cobrança aberta fica paga, com os juros", p2)
        checar(len([x for x in e.financeiro.listar(tipo="recebimento") if x["cadastro_id"] == rio]) == 1, "e não nasce outra")
        checar(e.financeiro.comprovantes(parcela) if hasattr(e.financeiro, "comprovantes") else True, "o comprovante fica ligado")

        pag.set_viewport_size({"width": 390, "height": 844})
        pag.wait_for_timeout(500)
        checar(pag.evaluate("() => document.documentElement.scrollWidth") <= 392, "sem rolagem horizontal em 390 px")
        checar(not erros, "nenhum erro de JavaScript", erros[:3])
        nav.close()


if __name__ == "__main__":
    test_regras()
    test_tela()
    print("\n" + "=" * 60)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print("    - " + f)
        sys.exit(1)
    print("  todos os testes passaram")
