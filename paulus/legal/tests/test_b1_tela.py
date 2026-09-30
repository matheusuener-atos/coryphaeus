"""
B1 - a tela Biblioteca (frontend/js/57-biblioteca.js), no Edge pelo Playwright.

Com dados de mentira (uma pasta temporária) e o acervo que vem com o PAULUS
posto nela:

  - o trilho e o menu têm a Biblioteca; Configurações › Biblioteca abre a
    mesma tela, na aba Obras e lembretes, com o material e os lembretes;
  - Leis e súmulas: os códigos do acervo, o art. 5º da Constituição pelo
    número, a busca por palavra e a Súmula 297 do STJ; o que foi apagado
    aparece como "fora", e "Pôr de volta" devolve;
  - Tribunais e fontes: número errado é recusado sem sair da máquina, o
    DataJud (simulado: o teste não vai à internet) mostra classe e
    movimentos, e as buscas de fora abrem no navegador;
  - em 390 px, sem rolagem horizontal.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_b1_tela.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-b1t-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

CAPTURAS = Path(os.environ.get("PAULUS_CAPTURAS") or (TMP / "capturas"))
_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def datajud_simulado(numero: str, *, pedir=None) -> dict:
    from biblioteca import tribunais

    lido = tribunais.ler_numero(numero)
    if not lido["ok"]:
        raise ValueError(lido["erro"])
    return {"numero": lido["numero"], "tribunal": "TJSP", "fonte": "DataJud, API pública do CNJ", "consultado_em": "",
            "graus": [tribunais.resumir({
                "tribunal": "TJSP", "grau": "G1", "dataAjuizamento": "20260730012658",
                "classe": {"nome": "Procedimento Comum Cível"}, "orgaoJulgador": {"nome": "2ª Vara Cível de Campinas"},
                "sistema": {"nome": "SAJ"}, "assuntos": [{"nome": "Indenização por Dano Moral"}],
                "movimentos": [{"dataHora": "2026-09-15T10:38:57.000Z", "nome": "Conclusos para despacho"},
                               {"dataHora": "2026-09-03T08:12:03.000Z", "nome": "Juntada de Petição"}]})]}


def test_tela(base: str, api) -> None:
    print("\nna tela (Edge pelo Playwright)")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        try:
            nav = p.chromium.launch(channel="msedge")
        except Exception as exc:  # noqa: BLE001
            print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            return
        ctx = nav.new_context(viewport={"width": 1440, "height": 900})
        ctx.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
        ctx.set_default_timeout(60000)
        pag = ctx.new_page()
        erros: list[str] = []
        pag.on("pageerror", lambda e: erros.append(str(e)))
        pag.goto(base + "/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
        pag.wait_for_function("() => typeof mostrarBibliotecaContexto === 'function' && typeof acessoDeFora !== 'undefined'")
        pag.evaluate("() => acessoDeFora.pronto")
        pag.wait_for_selector('.trilho [data-destino="contexto"]')
        pag.wait_for_timeout(1000)
        checar(pag.evaluate("() => !!document.querySelector('#menu [data-destino=\"contexto\"]')"), "o menu tem a Biblioteca")

        # pelo trilho: Obras e lembretes
        pag.click('.trilho [data-destino="contexto"]')
        pag.wait_for_selector("#bib-tela .cfg-cartao", timeout=15000)
        pag.wait_for_timeout(600)
        titulo = pag.evaluate("() => document.getElementById('conversa-titulo').textContent")
        abas = pag.evaluate("() => [...document.querySelectorAll('[data-bib-aba]')].map(b => b.textContent)")
        checar(titulo == "Biblioteca" and abas == ["Obras e lembretes", "Leis e súmulas", "Tribunais e fontes"],
               "a tela Biblioteca abre com as três abas", (titulo, abas))
        cartoes = pag.evaluate("() => [...document.querySelectorAll('#bib-tela .cfg-cartao-cabeca > span:first-child')].map(s => s.textContent)")
        checar("Material de consulta" in cartoes and "Lembretes" in cartoes and "O que eu sei fazer" in cartoes,
               "Obras e lembretes tem o material, os lembretes e as habilidades", cartoes)
        materiais = pag.inner_text("#bib-tela")
        checar("Súmulas do STJ" in materiais, "e as súmulas do STJ já estão no material")
        pag.screenshot(path=str(CAPTURAS / "b1-obras.png"))

        # Configurações › Biblioteca abre a mesma tela
        pag.evaluate("() => mostrarConfig('perfil')")
        pag.wait_for_selector("[data-cfg-secao='aprendizado']", timeout=10000)
        pag.click("[data-cfg-secao='aprendizado']")
        pag.wait_for_selector("#bib-tela .cfg-cartao", timeout=15000)
        checar(pag.evaluate("() => document.getElementById('conversa-titulo').textContent === 'Biblioteca' && cfg.secao === 'aprendizado'"),
               "Configurações › Biblioteca abre a tela Biblioteca")
        checar(pag.evaluate("() => document.querySelector('.trilho [data-destino=\"contexto\"]').classList.contains('ativo')"),
               "e o trilho acende a Biblioteca")

        # Leis e súmulas
        pag.click("[data-bib-aba='leis']")
        pag.wait_for_selector("#bib-codigo", state="attached", timeout=15000)
        pag.wait_for_timeout(300)
        linhas = pag.evaluate("() => [...document.querySelectorAll('#bib-tela .cfg-lei b')].map(b => b.textContent)")
        checar("Constituição Federal" in " ".join(linhas) and "Código de Processo Penal" in linhas and "Súmulas do STJ" in linhas,
               "os códigos e as súmulas do acervo aparecem", linhas)
        checar(not pag.query_selector(".bib-falta"), "nada fora: sem o aviso de faltando")
        pag.evaluate("() => { const s = document.getElementById('bib-codigo'); s.value = 'cf'; s.dispatchEvent(new Event('change')); }")
        pag.fill("#bib-artigo", "5")
        pag.click("[data-bib-artigo]")
        pag.wait_for_function("() => (document.getElementById('bib-achados') || {}).textContent.includes('inviolabilidade')", timeout=10000)
        checar(True, "o art. 5º da Constituição abre pelo número")
        pag.fill("#bib-termo-lei", "usucapião")
        pag.press("#bib-termo-lei", "Enter")
        pag.wait_for_function("() => document.querySelectorAll('#bib-achados .artigo').length >= 3", timeout=10000)
        checar(True, "a busca por palavra acha artigos (Enter também procura)")
        pag.fill("#bib-termo-sumula", "297")
        pag.click("[data-bib-procurar-sumula]")
        pag.wait_for_function("() => (document.getElementById('bib-achados') || {}).textContent.includes('Súmula 297 do STJ')", timeout=10000)
        checar("instituições financeiras" in pag.inner_text("#bib-achados"), "a Súmula 297 do STJ se acha pelo número")
        pag.screenshot(path=str(CAPTURAS / "b1-leis.png"))

        # apagar e pôr de volta
        pag.evaluate("async () => { await fetch('/api/leis/ctb', {method: 'DELETE'}); await mostrarBibliotecaContexto('leis'); }")
        pag.wait_for_selector(".bib-falta [data-bib-por]", timeout=10000)
        checar("1 item do acervo está fora" in pag.inner_text(".bib-falta"), "o código apagado aparece como fora", pag.inner_text(".bib-falta"))
        pag.click("[data-bib-por]")
        pag.wait_for_function("() => !document.querySelector('.bib-falta') && !!document.getElementById('bib-codigo')", timeout=60000)
        checar(api.estado.leis.artigo("ctb", "165") is not None, "“Pôr de volta” devolve o CTB")
        aviso = pag.evaluate("() => (document.getElementById('faixa-janela') || {}).textContent || ''")
        checar("1 código voltou" in aviso, "e o aviso diz que só ele voltou", aviso)

        # Tribunais e fontes
        pag.click("[data-bib-aba='tribunais']")
        pag.wait_for_selector("#bib-processo", timeout=10000)
        pag.fill("#bib-processo", "0000001-00.2026.8.26.0100")
        pag.click("[data-bib-datajud]")
        pag.wait_for_selector("#bib-processo-resultado .bib-erro", timeout=10000)
        checar("dígito verificador" in pag.inner_text("#bib-processo-resultado"), "número com dígito errado é recusado, com o motivo")
        pag.fill("#bib-processo", "4014273-81.2026.8.26.0008")
        pag.press("#bib-processo", "Enter")
        pag.wait_for_selector("#bib-processo-resultado .bib-processo", timeout=15000)
        texto = pag.inner_text("#bib-processo-resultado")
        checar("Procedimento Comum Cível" in texto and "Conclusos para despacho" in texto and "30/07/2026" in texto,
               "o processo mostra classe, ajuizamento e movimentos", texto[:200])
        pag.evaluate("() => { window._abertos = []; window.open = (u) => { window._abertos.push(u); return null; }; }")
        pag.fill("#bib-termo-fora", "dano moral negativação")
        pag.click("[data-bib-montar]")
        pag.wait_for_selector("[data-bib-abrir-fora]", timeout=10000)
        botoes = pag.evaluate("() => document.querySelectorAll('[data-bib-abrir-fora]').length")
        pag.click("[data-bib-abrir-fora]")
        aberto = pag.evaluate("() => window._abertos[0] || ''")
        checar(botoes == 5 and aberto.startswith("https://www.jusbrasil.com.br/busca?q=dano+moral"),
               "as buscas de fora abrem no navegador, com o termo", (botoes, aberto))
        pag.screenshot(path=str(CAPTURAS / "b1-tribunais.png"))

        # no celular
        pag.set_viewport_size({"width": 390, "height": 844})
        pag.wait_for_timeout(400)
        for aba in ("tribunais", "leis", "obras"):
            pag.evaluate(f"() => mostrarBibliotecaContexto('{aba}')")
            pag.wait_for_selector("#bib-tela .cfg-cartao", timeout=15000)
            pag.wait_for_timeout(400)
            largura = pag.evaluate("() => document.documentElement.scrollWidth")
            checar(largura <= 392, f"em 390 px, {aba} sem rolagem horizontal", largura)
        pag.evaluate("() => mostrarBibliotecaContexto('leis')")
        pag.wait_for_selector("#bib-codigo", state="attached")
        pag.screenshot(path=str(CAPTURAS / "b1-celular.png"), full_page=False)
        checar(not erros, "nenhum erro de JavaScript na página", erros[:3])
        nav.close()


def main() -> int:
    print("=" * 55)
    print("  B1 — a tela Biblioteca")
    print("=" * 55)
    from test_gravacoes import _porta_livre, _subir_servidor

    import api
    from biblioteca import nativo, tribunais

    feito = nativo.instalar(api.estado.leis, api.estado.material, Path(os.environ["PAULUS_DADOS"]) / "leis", forcar=True)
    checar(len(feito["codigos"]) >= 11 and feito["sumulas"] == ["stj"], "o acervo entra na pasta do teste", feito)
    original = tribunais.consultar_datajud
    tribunais.consultar_datajud = datajud_simulado
    porta = _porta_livre()
    _subir_servidor(porta)
    try:
        test_tela(f"http://127.0.0.1:{porta}", api)
    finally:
        tribunais.consultar_datajud = original
    print(f"\n  capturas em {CAPTURAS}")
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
