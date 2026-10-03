"""A aba Notas fiscais do painel no navegador (Playwright), contra o servidor local.

    python worker/tela-nfse/teste_tela.py [pasta-das-fotos]

Sobe worker/tela-nfse/servidor.mjs (o painel e o emissor de verdade, o resto
simulado), abre /admin/ no Chromium e faz o caminho da tela: Parâmetros,
o município pelo nome (Parâmetros, Emitir e Clientes:
digitar, escolher, gravar e conferir o código IBGE), certificado sem e com o token da Cloudflare, Testar comunicação, Emitir a
partir do pagamento (com um erro de conferência no pop-up), PDF, Enviar ao
cliente, Clientes e Cancelar. Depois, como suporte: os botões travados. Falha
em qualquer erro de JavaScript da página.
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
PFX = RAIZ / "worker" / "nfse" / "fixtures" / "a1-cn.pfx"
FOTOS = Path(sys.argv[1]) if len(sys.argv) > 1 else None
falhas = []


def checar(ok, descricao):
    print(("  ok   " if ok else "  FALHA ") + descricao)
    if not ok:
        falhas.append(descricao)


def subir(porta, papel):
    env = dict(os.environ, PAPEL=papel)
    p = subprocess.Popen(["node", "--no-warnings", str(AQUI / "servidor.mjs"), str(porta)], cwd=RAIZ, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
    linha = p.stdout.readline()
    if "painel local" not in linha:
        p.kill()
        raise SystemExit("o servidor não subiu: " + linha)
    return p


def foto(pagina, nome):
    if FOTOS:
        FOTOS.mkdir(parents=True, exist_ok=True)
        pagina.screenshot(path=str(FOTOS / (nome + ".png")), full_page=True)


def entrar(pagina, base, erros):
    # As fontes do Google ficam de fora (o teste não depende da rede). "Failed to
    # load resource" é o navegador contando uma resposta 4xx (o erro de
    # conferência de propósito) ou a fonte barrada: não é erro de JavaScript.
    pagina.route(re.compile(r"^https://fonts\.(googleapis|gstatic)\.com/.*"), lambda rota: rota.abort())
    pagina.on("pageerror", lambda e: erros.append("pageerror: " + str(e)))
    pagina.on("console", lambda m: erros.append("console: " + m.text) if m.type == "error" and not m.text.startswith("Failed to load resource") else None)
    pagina.goto(base + "/admin/")
    pagina.click("#entrar-painel")
    pagina.goto(base + "/admin/#nfse")
    expect(pagina.get_by_role("heading", name="Notas fiscais (NFS-e)")).to_be_visible()


def campo(pagina, chave):
    return pagina.locator('.modal [data-k="' + chave + '"]')


def codigo(pagina, chave):
    """O código IBGE guardado escondido atrás do campo de município."""
    return pagina.locator('.modal [data-codigo="' + chave + '"]').get_attribute("value")


def toast(pagina, texto):
    expect(pagina.locator("#toast")).to_contain_text(texto, timeout=15000)


def como_dono(pw):
    porta = 8791
    srv = subir(porta, "dono")
    erros = []
    try:
        nav = pw.chromium.launch()
        pagina = nav.new_page(viewport={"width": 1280, "height": 900})
        base = "http://127.0.0.1:%d" % porta
        entrar(pagina, base, erros)
        tela = pagina.locator("#tela")
        expect(tela).to_contain_text("Pagamentos sem nota")
        expect(tela).to_contain_text("Ana Advocacia")
        expect(tela).to_contain_text("falta CEP")
        checar(True, "a aba abre: selo de testes, os quatro botões e os pagamentos sem nota (com o motivo)")
        expect(tela).to_contain_text("ambiente de testes")
        foto(pagina, "1-inicio")

        # Parâmetros
        pagina.click('[data-a="nfParametros"]')
        expect(pagina.locator(".modal")).to_contain_text("O PAVLVS (prestador)")
        for chave, valor in [("documento", "11222333000181"), ("razao_social", "PAVLVS Tecnologia"), ("inscricao_municipal", "7788990"),
                             ("servico.ctribnac", "010301"), ("servico.nbs", "115062100"),
                             ("servico.aliquota_iss_pct", "2,00"), ("servico.descricao", "Assinatura do PAULUS"), ("ibscbs.cst", "000"),
                             ("ibscbs.cclasstrib", "000001"), ("ibscbs.cindop", "100301"), ("total_tributos.federal_pct", "13,45"),
                             ("total_tributos.municipal_pct", "2,00")]:
            campo(pagina, chave).fill(valor)
        campo(pagina, "ibscbs.indfinal").select_option("1")
        campo(pagina, "opcao_simples").select_option("1")
        for k in ["iss", "irrf", "pis", "cofins", "csll", "cp"]:
            campo(pagina, "retencoes." + k + ".quando").select_option("nunca")
        # o município pelo nome: colar o código mostra o nome; digitar "belém" lista e escolhe
        mun = campo(pagina, "municipio")
        mun.fill("5208707")
        expect(mun).to_have_value("Goiânia/GO", timeout=10000)
        checar(codigo(pagina, "municipio") == "5208707", "Parâmetros: colar os 7 dígitos do IBGE mostra \"Goiânia/GO\" e guarda o código")
        mun.fill("")
        mun.press_sequentially("belém", delay=40)
        opcao = pagina.locator(".modal .nf-mun-opcao", has_text="Belém/PA")
        expect(opcao).to_be_visible(timeout=10000)
        checar(pagina.locator(".modal .nf-mun-opcao", has_text="Belém/PB").count() == 1, "a lista mostra os Belém de cada UF (nome/UF)")
        foto(pagina, "2-parametros-municipio")
        opcao.click()
        expect(mun).to_have_value("Belém/PA")
        checar(codigo(pagina, "municipio") == "1501402" and pagina.locator(".modal .nf-mun-lista").count() == 0,
               "Parâmetros: escolher \"Belém/PA\" fecha a lista e guarda o código 1501402 escondido")
        foto(pagina, "2-parametros")
        pagina.click('[data-a="nfParamSalvar"]')
        toast(pagina, "Parâmetros gravados (versão")
        checar(pagina.locator(".modal").count() == 0, "Parâmetros: grava o prestador e a tributação (alíquotas em %)")
        expect(tela).to_contain_text("PAVLVS Tecnologia")
        r = pagina.request.get(base + "/api/admin/nfse/emissor/situacao")
        checar(r.json()["prestador"]["dados"]["municipio"] == "1501402", "o código IBGE do município foi gravado no prestador")
        pagina.click('[data-a="nfParametros"]')
        expect(campo(pagina, "municipio")).to_have_value("Belém/PA", timeout=10000)
        checar(True, "reaberto, Parâmetros mostra \"Belém/PA\" no lugar do código")
        pagina.keyboard.press("Escape")

        # certificado sem o token
        pagina.set_input_files("#nf-pfx", str(PFX))
        expect(tela).to_contain_text("a1-cn.pfx")
        pagina.fill("#nf-senha", "segredo-de-teste")
        pagina.click('[data-a="nfCert"]')
        expect(tela).to_contain_text("falta o token da Cloudflare", timeout=20000)
        expect(tela).to_contain_text("11.222.333/0001-81")
        checar(True, "certificado aberto no navegador e guardado; o cartão e o aviso de que falta o token")
        foto(pagina, "3-certificado")

        # o token
        pagina.click('[data-a="nfParametros"]')
        pagina.fill("#nf-token", "cfat_" + "x" * 40)
        pagina.click('[data-a="nfToken"]')
        expect(pagina.locator(".modal")).to_contain_text("Certificado cadastrado na Cloudflare", timeout=15000)
        checar(True, "Token da Cloudflare: gravado e o certificado cadastrado como mTLS")
        pagina.click('.modal [data-a="fecharModal"] >> nth=0')
        expect(tela).to_contain_text("mTLS na Cloudflare")

        # testar
        pagina.click('[data-a="nfTestar"]')
        expect(tela).to_contain_text("Comunicação ok", timeout=15000)
        expect(tela).to_contain_text("Convênio do município")
        checar(True, "Testar comunicação: as três etapas com o tempo")

        # emitir a partir do pagamento, com um erro de conferência antes
        pagina.locator('[data-a="nfEmitirPag"][data-id="PAY1"]').click()
        expect(campo(pagina, "tomador.nome")).to_have_value("Ana Advocacia", timeout=10000)
        expect(campo(pagina, "valor")).to_have_value("300,00")
        checar(True, "Emitir: o pop-up vem preenchido pelo pagamento (cliente, tomador, valor)")
        expect(campo(pagina, "tomador.cmun")).to_have_value("Belém/PA", timeout=10000)
        checar(codigo(pagina, "tomador.cmun") == "1501402", "Emitir: o município do cliente aparece pelo nome (\"Belém/PA\"), com o código escondido")
        campo(pagina, "tomador.documento").fill("52998224726")
        pagina.click('[data-a="nfEmitirConfirmar"]')
        expect(pagina.locator(".modal .erro-campo")).to_be_visible(timeout=15000)
        checar("CPF" in pagina.locator(".modal .erro-campo").inner_text() or "conferência" in pagina.locator(".modal .erro-campo").inner_text(),
               "o erro de conferência aparece dentro do pop-up")
        foto(pagina, "4-erro-conferencia")
        campo(pagina, "tomador.documento").fill("52998224725")
        pagina.click('[data-a="nfEmitirConfirmar"]')
        toast(pagina, "emitida")
        expect(tela.locator(".grade-linha").first).to_contain_text("Emitida")
        checar(True, "emitida; a nota aparece na lista")
        expect(tela.locator('[data-a="nfEmitirPag"][data-id="PAY1"]')).to_have_count(0)
        checar(True, "o pagamento sai da lista dos sem nota")

        # PDF e XML
        href = tela.locator('a.mini:has-text("PDF")').first.get_attribute("href")
        r = pagina.request.get(base + "/admin/" + href if not href.startswith("/") else base + href)
        checar(r.status == 200 and r.headers.get("content-type") == "application/pdf" and r.body()[:5] == b"%PDF-", "PDF: o link baixa o DANFSe")
        href = tela.locator('a.mini:has-text("XML")').first.get_attribute("href")
        r = pagina.request.get(base + href)
        checar(r.status == 200 and b"<NFSe" in r.body(), "XML: o link baixa a nota")

        # enviar ao cliente
        tela.locator('[data-a="nfEnviar"]').first.click()
        toast(pagina, "Enviada")
        expect(tela).to_contain_text("no app do cliente desde")
        checar(True, "Enviar ao cliente: entregue no app dele")
        foto(pagina, "5-emitida")

        # clientes
        pagina.click('[data-a="nfClientes"]')
        expect(pagina.locator(".modal")).to_contain_text("Escritório bruno", timeout=10000)
        pagina.locator('.modal [data-a="nfCliEditar"][data-id="' + "b" * 24 + '"]').click()
        for chave, valor in [("tomador.documento", "11222333000181"), ("tomador.cep", "66010000"), ("tomador.logradouro", "Av. Nazaré"),
                             ("tomador.numero", "10"), ("tomador.bairro", "Nazaré")]:
            campo(pagina, chave).fill(valor)
        mun = campo(pagina, "tomador.cmun")
        mun.press_sequentially("goi", delay=40)
        opcao = pagina.locator(".modal .nf-mun-opcao", has_text="Goiânia/GO")
        expect(opcao).to_be_visible(timeout=10000)
        mun.press("ArrowDown")
        checar(pagina.locator('.modal .nf-mun-opcao[aria-selected="true"]').count() == 1, "Clientes: as setas andam na lista")
        foto(pagina, "6-clientes-municipio")
        opcao.click()
        expect(mun).to_have_value("Goiânia/GO")
        checar(codigo(pagina, "tomador.cmun") == "5208707" and campo(pagina, "tomador.uf").input_value() == "GO",
               "Clientes: digitar \"goi\" e escolher \"Goiânia/GO\" guarda 5208707 e preenche a UF")
        pagina.locator('.modal [data-a="nfCliSalvar"]').click()
        expect(pagina.locator(".modal")).to_contain_text("salvos", timeout=10000)
        checar("completo" in pagina.locator(".modal").inner_text(), "Clientes: editar e salvar o tomador; o que faltava some")
        bruno = [c for c in pagina.request.get(base + "/api/admin/nfse/emissor/clientes").json()["clientes"] if c["id"] == "b" * 24][0]
        checar(bruno["tomador"]["cmun"] == "5208707" and bruno["tomador"]["uf"] == "GO", "o código IBGE escolhido pelo nome foi gravado no cliente (5208707)")
        foto(pagina, "6-clientes")
        pagina.keyboard.press("Escape")

        # cancelar
        tela.locator('[data-a="nfCancelar"]').first.click()
        campo(pagina, "texto").fill("Erro na emissão: valor errado na nota")
        pagina.click('[data-a="nfCancelarConfirmar"]')
        toast(pagina, "cancelada")
        expect(tela.locator(".grade-linha").first).to_contain_text("Cancelada")
        checar(True, "Cancelar: a nota fica cancelada")
        foto(pagina, "7-cancelada")
        checar(not erros, "nenhum erro de JavaScript na página" + ("" if not erros else ": " + "; ".join(erros)))
        nav.close()
    finally:
        srv.terminate()


def como_suporte(pw):
    porta = 8792
    srv = subir(porta, "suporte")
    erros = []
    try:
        nav = pw.chromium.launch()
        pagina = nav.new_page(viewport={"width": 390, "height": 844})
        entrar(pagina, "http://127.0.0.1:%d" % porta, erros)
        tela = pagina.locator("#tela")
        expect(tela).to_contain_text("Pagamentos sem nota")
        checar(tela.locator('[data-a="nfEmitir"]').is_disabled() and tela.locator('[data-a="nfTestar"]').is_disabled()
               and tela.locator('[data-a="nfEmitirPag"]').first.is_disabled(), "suporte: Emitir, Testar e Emitir do pagamento travados")
        checar(tela.locator("#nf-pfx").count() == 0, "suporte: sem a linha de instalar o certificado")
        pagina.click('[data-a="nfParametros"]')
        checar(pagina.locator('.modal [data-a="nfParamSalvar"]').count() == 0 and "só lê" in pagina.locator(".modal").inner_text(), "suporte: Parâmetros só para ler")
        foto(pagina, "8-suporte-celular")
        checar(not erros, "nenhum erro de JavaScript (suporte, celular)" + ("" if not erros else ": " + "; ".join(erros)))
        nav.close()
    finally:
        srv.terminate()


with sync_playwright() as pw:
    print("dono")
    como_dono(pw)
    print("suporte")
    como_suporte(pw)

print("\n  " + (str(len(falhas)) + " falha(s)" if falhas else "a tela das notas fiscais: todos os testes passaram"))
sys.exit(1 if falhas else 0)
