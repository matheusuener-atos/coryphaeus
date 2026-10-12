"""
A tela Notas fiscais (js/93-notas-fiscais.js) no Edge, pelo Playwright, com a
Sefin simulada (tests/_sefin_simulada.py) e o Worker de paulus.ia.br de
mentira (como tests/test_nfse_recebidas.py):

  - abre pelo menu (o item "Notas fiscais" do trilho);
  - sem a emissão configurada, a aba Emitidas mostra o estado vazio com
    "Configurar a nota fiscal", que leva a Configurações › Nota fiscal, e diz
    que no município sem convênio a nota é registrada no Financeiro;
  - com notas emitidas: a lista (nº, cliente, competência, valor, situação,
    ambiente), o filtro por situação, o cartão da nota, o PDF (DANFSe) e o XML;
  - a aba Recebidas: competência por extenso, nº, valor, situação, ambiente,
    Download e XML respondem;
  - sem erro de página, no claro e no escuro.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_notas_fiscais_tela.py

As capturas ficam em NOTAS_CAPTURAS (ou numa pasta temporária).
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-notas-tela-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
os.environ["PAULUS_NFSE_SEM_FILA"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))
CAPTURAS = Path(os.environ.get("NOTAS_CAPTURAS") or (TMP / "capturas"))

from _nfse_comum import checar, falhas  # noqa: E402

SEGREDO = "pia_" + "a1" * 12 + "_" + "b2" * 32


def emitir_notas(api, local) -> list[dict]:
    import test_n8_producao as n8

    n8.TMP = TMP
    _s, cid = n8.preparar(api)
    emitidas = [n8.emitir(api, local, cid)[0] for _ in range(2)]
    # Um rascunho, para o filtro por situação.
    local.post("/api/nfse/notas", json={"origem": "teste", "dados": {"cadastro_id": cid, "valor": "50,00"}})
    return emitidas


def main() -> int:
    print("=" * 55)
    print("  Notas fiscais — a tela")
    print("=" * 55)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return 0
    from fastapi.testclient import TestClient
    from test_gravacoes import _porta_livre, _subir_servidor

    import api
    from test_nfse_recebidas import Worker  # depois do api: o módulo mexe em PAULUS_DADOS
    import nfse_recebidas
    import nuvem
    import segredos

    try:
        local = TestClient(api.app, headers=api.cabecalho_local())
        worker = Worker()
        nuvem.PEDIR["fn"] = worker
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
            ctx = nav.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
            ctx.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
            ctx.set_default_timeout(60000)
            pag = ctx.new_page()
            erros: list[str] = []
            pag.on("pageerror", lambda e: erros.append(str(e)))
            pag.goto(base + "/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
            pag.wait_for_function("() => typeof mostrarNotasFiscais === 'function' && typeof acessoDeFora !== 'undefined'")
            pag.evaluate("() => acessoDeFora.pronto")

            print("\nsem a emissão configurada")
            pag.evaluate("() => aplicarTema('claro')")
            pag.evaluate("() => document.querySelector('.trilho [data-destino=\"notas\"]').click()")  # a barra do alto clica o mesmo botao
            # 12/10 (js/99-nfse-emissor.js): Emitidas e a lista com filtros (.nfv-emitidas), mesmo vazia.
            pag.wait_for_selector("#nf-tela .nfv-emitidas, #nf-tela .nf-vazio", timeout=20000)
            pag.wait_for_timeout(400)
            checar(pag.locator('.trilho [data-destino="notas"].ativo').count() == 1, "o item do menu acende")
            vazio = pag.inner_text("#nf-tela")
            checar("Configurar a nota fiscal" in vazio and "registrada no Financeiro" in vazio and "sem convênio" in vazio,
                   "estado vazio: configurar e o caminho do município sem convênio", vazio[:300])
            pag.screenshot(path=str(CAPTURAS / "notas-vazio-claro.png"))
            if pag.locator("#nf-tela [data-nf-configurar]").count():
                pag.click("#nf-tela [data-nf-configurar] >> nth=0")
                pag.wait_for_function("() => typeof cfg !== 'undefined' && cfg.secao === 'nfse'", timeout=20000)
                checar(True, "Configurar a nota fiscal abre Configurações › Nota fiscal")
            else:
                checar(False, "Configurar a nota fiscal abre Configurações › Nota fiscal", "a tela Notas fiscais não tem mais o botão")

            print("\nRecebidas sem a conta da nuvem")
            pag.evaluate("() => mostrarNotasFiscais('recebidas')")
            pag.wait_for_selector(".nf-vazio", timeout=20000)
            checar("quando o escritório tem a assinatura" in pag.inner_text(".nf-vazio"), "frase curta sem a assinatura")

            print("\ncom notas emitidas (Sefin simulada) e a conta da nuvem")
            emitidas = emitir_notas(api, local)
            checar(all(n["estado"] == "emitida" for n in emitidas), "duas notas emitidas", [n["estado"] for n in emitidas])
            tem_dpapi = segredos.disponivel()
            if tem_dpapi:
                nuvem.guardar_chave(api.estado, "paulus", SEGREDO)
                nfse_recebidas.esquecer()

            for tema in ("claro", "escuro"):
                print(f"\nno tema {tema}")
                pag.evaluate("() => { aplicarTema('" + tema + "'); abrirDestino('notas'); mostrarNotasFiscais('emitidas'); }")
                pag.wait_for_selector(".nf-tabela tbody tr", timeout=20000)
                pag.wait_for_timeout(500)
                linhas = pag.locator(".nf-tabela tbody tr").count()
                checar(linhas == 3, "as três notas na lista (duas emitidas e um rascunho)", linhas)
                # 12/10: as colunas na ordem da de Recebidas, e "Cliente" passou a "Tomador"
                cab = pag.evaluate("() => [...document.querySelectorAll('.nf-tabela th')].map(x => x.textContent)")
                checar(cab[:6] == ["Competência", "Nº", "Tomador", "Valor", "Situação", "Ambiente"], "as colunas", cab)
                texto = pag.inner_text(".nf-tabela")
                checar("ACME Ltda" in texto and "testes" in texto and "Emitida" in texto, "cliente, ambiente e situação", texto[:300])
                checar(pag.locator("#acoes-tela [data-nf-ir-emitir]").count() == 1, "o botão Emitir nota")
                # Cancelar e Substituir moram no "..." de cada nota emitida
                cancelar = substituir = 0
                for i in range(pag.locator('.nf-tabela tr.nfv-nota[data-estado="emitida"]').count()):
                    pag.locator('.nf-tabela tr.nfv-nota[data-estado="emitida"] [data-nfv-menu]').nth(i).click()
                    pag.wait_for_selector(".nfv-menu", timeout=5000)
                    cancelar += pag.locator(".nfv-menu [data-nota-cancelar]").count()
                    substituir += pag.locator(".nfv-menu [data-nota-substituir]").count()
                    pag.evaluate("() => document.querySelectorAll('.nfv-menu').forEach(m => m.remove())")
                checar(cancelar == 2 and substituir == 2, "Cancelar e Substituir nas emitidas (no menu “...” da nota)", (cancelar, substituir))
                pag.screenshot(path=str(CAPTURAS / f"notas-emitidas-{tema}.png"), full_page=True)

                trocar = ("v => { const s = document.querySelector('#nf-tela select[data-nfv-filtro-sel=\"situacao\"]');"
                          " s.value = v; s.dispatchEvent(new Event('change', { bubbles: true })); }")
                pag.evaluate(trocar, "rascunho")
                pag.wait_for_timeout(300)
                checar(pag.locator(".nf-tabela tbody tr.nfv-nota").count() == 1, "o filtro por situação")
                pag.evaluate(trocar, "todas")
                pag.wait_for_timeout(300)

                nid = emitidas[0]["id"]
                r = pag.request.get(f"{base}/api/nfse/notas/{nid}/danfse")
                checar(r.status == 200 and r.body()[:4] == b"%PDF", "o PDF (DANFSe) responde", r.status)
                r = pag.request.get(f"{base}/api/nfse/notas/{nid}/xml")
                checar(r.status == 200 and b"<" in r.body() and "attachment" in r.headers.get("content-disposition", ""),
                       "o XML responde como anexo", r.status)
                # "Baixar XML" no menu da nota abre o endereço do XML (window.open); o endereço baixa como anexo
                pag.evaluate("() => { window._abertos = []; window._openAntes = window._openAntes || window.open;"
                             " window.open = (u) => { window._abertos.push(u); return null; }; }")
                pag.click(f'.nf-tabela tr.nfv-nota[data-nfv-nota="{nid}"] [data-nfv-menu]')
                pag.wait_for_selector('.nfv-menu [data-nfv-a="xml"]', timeout=5000)
                pag.click('.nfv-menu [data-nfv-a="xml"]')
                pag.wait_for_timeout(300)
                url_xml = pag.evaluate("() => window._abertos[0] || ''")
                pag.evaluate("() => { document.querySelectorAll('.nfv-menu').forEach(m => m.remove()); window.open = window._openAntes; }")
                r = pag.request.get(base + url_xml) if url_xml.startswith("/") else None
                checar(url_xml.startswith(f"/api/nfse/notas/{nid}/xml") and r is not None and r.status == 200
                       and "attachment" in r.headers.get("content-disposition", "") and ".xml" in r.headers.get("content-disposition", ""),
                       "o botão XML baixa o arquivo", url_xml)

                # a nota abre na própria lista (sem pop-up), com os dados e as ações
                pag.click(f'.nf-tabela tr.nfv-nota[data-nfv-nota="{nid}"] .nfv-tomador')
                pag.wait_for_selector(f'.nfv-detalhe[data-nfv-nota-det="{nid}"]', timeout=10000)
                det = pag.inner_text(f'.nfv-detalhe[data-nfv-nota-det="{nid}"]')
                linha = pag.inner_text(f'.nf-tabela tr.nfv-nota[data-nfv-nota="{nid}"]')
                checar("ACME Ltda" in det and "Emitida" in linha and "Baixar PDF" in det, "o cliente abre a nota (na lista)", det[:200])
                pag.wait_for_timeout(500)
                pag.screenshot(path=str(CAPTURAS / f"notas-cartao-{tema}.png"))
                pag.click(f'.nf-tabela tr.nfv-nota[data-nfv-nota="{nid}"] .nfv-tomador')
                pag.wait_for_timeout(400)

                if tem_dpapi:
                    pag.click('[data-nf-aba="recebidas"]')
                    pag.wait_for_selector(".nf-tabela tbody tr", timeout=20000)
                    pag.wait_for_timeout(400)
                    texto = pag.inner_text(".nf-tabela")
                    checar(pag.locator(".nf-tabela tbody tr").count() == 3, "as três notas recebidas")
                    checar("outubro de 2026" in texto and "Cancelada" in texto and "testes" in texto and "R$ 1.234,50" in texto,
                           "competência por extenso, valor, situação e ambiente", texto[:300])
                    r = pag.request.get(f"{base}/api/nfse-recebidas/n-1/pdf")
                    checar(r.status == 200 and r.body()[:4] == b"%PDF", "Download (PDF) responde", r.status)
                    with pag.expect_download() as baixa:
                        pag.click('.nf-tabela [data-nf-baixar$="n-1/xml"]')
                    checar(baixa.value.suggested_filename.endswith(".xml"), "o botão XML baixa", baixa.value.suggested_filename)
                    pag.screenshot(path=str(CAPTURAS / f"notas-recebidas-{tema}.png"), full_page=True)
                else:
                    print("  pulado: recebidas com a conta (sem DPAPI)")
                checar(not erros, "sem erro na página", erros)

            print("\nno celular")
            cel = ctx.new_page()
            cel.set_viewport_size({"width": 390, "height": 844})
            cel.goto(base + "/", wait_until="load")
            cel.wait_for_function("() => typeof mostrarNotasFiscais === 'function' && typeof acessoDeFora !== 'undefined'")
            cel.evaluate("() => acessoDeFora.pronto")
            cel.evaluate("() => mostrarNotasFiscais('emitidas')")
            cel.wait_for_selector(".nf-tabela", timeout=20000)
            cel.wait_for_timeout(400)
            largura = cel.evaluate("() => document.documentElement.scrollWidth")
            checar(largura <= 390, "a página não rola para o lado em 390 px (só a tabela)", largura)
            cel.screenshot(path=str(CAPTURAS / "notas-celular.png"), full_page=True)
            nav.close()
        print(f"\ncapturas em {CAPTURAS}")
    finally:
        shutil.rmtree(TMP / "dados", ignore_errors=True)
    if falhas:
        print(f"\n  {len(falhas)} falha(s)")
        return 1
    print("\n  Notas fiscais: todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
