"""
A Area do cliente na tela, no Edge, pelo Playwright (docs/PLANO-AREA-CLIENTE.md):

  - o escritorio (1440 px): a pasta compartilhada mostra o olhinho nas etapas
    e nos compromissos e o "compartilhar" nos documentos; a aba Cliente
    (quem ve, resumo, conversa, atividade, as tres regras) e o "Ver como o
    cliente" na moldura de celular;
  - o cliente (celular, 390 px, claro e escuro): entrar com o e-mail e o
    codigo, a pasta sem rolagem de lado, "Para voce", abrir o documento (a
    pagina com marca d'agua), escrever, mandar o arquivo da pendencia e
    confirmar o horario;
  - sem erro de pagina dos dois lados.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_area_cliente_tela.py

As capturas ficam em AREA_CAPTURAS (ou numa pasta temporaria).
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-area-tela-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))
CAPTURAS = Path(os.environ.get("AREA_CAPTURAS") or (TMP / "capturas"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def _pdf(texto: str) -> bytes:
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.setFont("Helvetica", 14)
    c.drawString(72, 760, "PETIÇÃO INICIAL")
    for i, linha in enumerate(texto.split("\n")):
        c.drawString(72, 720 - 18 * i, linha)
    c.save()
    return buf.getvalue()


def preparar(api, local) -> dict:
    """A pasta do exemplo: o que e do escritorio e o que o cliente pode ver."""
    estado = api.estado
    estado.prefs.dados.setdefault("escritorio", {})["nome"] = "Moura Advogados"
    estado.prefs.dados.setdefault("pessoa", {})["nome"] = "Ana Moura"
    estado.prefs.dados["acesso_remoto"].update({"ligado": True, "hostname": "moura.paulus.ia.br"})
    cliente = local.post("/api/cadastros", json={"id": None, "dados": {"tipo": "cliente", "nome": "João da Silva",
                                                                        "email": "joao@cliente.com"}}).json()["id"]
    socia = local.post("/api/cadastros", json={"id": None, "dados": {"tipo": "socio", "nome": "Ana Moura", "email": "ana@moura.adv.br"}}).json()["id"]
    sid = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Revisional do financiamento", "cadastro_id": cliente,
                                                                   "descricao": "Revisão das taxas do financiamento do carro."}}).json()["id"]
    estado.base.escrever("UPDATE servicos SET equipe = ? WHERE id = ?", (f"[{socia}]", sid))
    local.post(f"/api/servicos/{sid}/anotacoes", json={"texto": "Cliente difícil — só falar por escrito."})
    em = lambda d: (date.today() + timedelta(days=d)).isoformat()  # noqa: E731
    for titulo, quando, feita in (("Análise do contrato", "", True), ("Petição inicial protocolada", "", True),
                                  ("Citação do banco", em(12), False), ("Estratégia interna de acordo", em(5), False),
                                  ("Enviar RG e comprovante de renda", em(3), False)):
        local.post(f"/api/servicos/{sid}/etapas", json={"titulo": titulo, "quando": quando})
    local.post(f"/api/servicos/{sid}/etapas/0")
    local.post(f"/api/servicos/{sid}/etapas/1")
    aud = estado.base.escrever(
        "INSERT INTO compromissos (titulo, data, hora, duracao, onde, servico_id, criado_em, meet) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("Audiência de conciliação", em(9), "14:30", 60, "online", sid, "2026-10-04T10:00:00", "https://meet.google.com/abc-defg-hij"))
    pasta = estado.servicos.pasta_de(sid, criar=True)
    (pasta / "Petição inicial.pdf").write_bytes(_pdf("Autor: João da Silva\nRéu: Banco Exemplo S.A.\nRevisão das taxas do contrato nº 123."))
    estado.recarregar()
    s = local.get(f"/api/servicos/{sid}").json()
    sha = next(a["sha1"] for a in s["arquivos"] if a["nome"] == "Petição inicial.pdf")
    return {"sid": sid, "aud": aud, "sha": sha}


def main() -> int:
    print("=" * 55)
    print("  Area do cliente - a tela")
    print("=" * 55)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright nao instalado")
        return 0
    from fastapi.testclient import TestClient
    from test_gravacoes import _porta_livre, _subir_servidor

    import api

    local = TestClient(api.app, headers=api.cabecalho_local())
    area = api.estado.area_cliente
    emails: list[dict] = []
    area.enviar_email = lambda dados: emails.append(dict(dados)) or ""
    area.antivirus = lambda caminho: "limpo"
    area.avisar = lambda titulo, texto: None
    d = preparar(api, local)
    sid = d["sid"]
    porta = _porta_livre()
    _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"
    CAPTURAS.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        try:
            nav = p.chromium.launch(channel="msedge")
        except Exception as exc:  # noqa: BLE001
            print(f"  pulado: nao achei o Edge ({str(exc)[:60]})")
            return 0

        print("\no escritorio")
        ctx = nav.new_context(viewport={"width": 1440, "height": 1000})
        ctx.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
        ctx.set_default_timeout(60000)
        pag = ctx.new_page()
        erros: list[str] = []
        pag.on("pageerror", lambda e: erros.append(str(e)))
        pag.goto(base + "/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
        pag.wait_for_function("() => typeof abrirServico === 'function' && typeof acessoDeFora !== 'undefined' && window.AreaCliente")
        pag.evaluate("() => acessoDeFora.pronto")
        pag.evaluate("() => aplicarTema('claro')")
        pag.evaluate(f"() => abrirServico({sid})")
        pag.wait_for_selector(".sv-linha-etapa")
        checar(pag.locator("[data-acp-etapa-olho]").count() == 0, "sem compartilhar, nada de olhinho")
        pag.click('[data-sv-aba="cliente"]')
        pag.wait_for_selector("[data-acp-compartilhar]")
        checar("Ninguém de fora vê esta pasta" in pag.inner_text("#acp-aba"), "a aba Cliente explica antes de compartilhar")
        pag.click("[data-acp-compartilhar]")
        pag.wait_for_selector(".dialogo #dialogo-campo")
        checar(pag.input_value("#dialogo-campo") == "João da Silva" and pag.input_value("#dialogo-campo-1") == "joao@cliente.com",
               "o diálogo vem com o cliente do cadastro")
        pag.screenshot(path=str(CAPTURAS / "escritorio-compartilhar.png"))
        pag.click('.dialogo [data-dialogo="confirmar"]')
        pag.wait_for_selector(".acp-pessoa")
        checar(emails and emails[-1]["tipo"] == "convite", "o convite saiu", emails[-1:])
        link = emails[-1]["link"]
        token = link.rsplit("/", 1)[-1]

        pag.click('[data-sv-aba="geral"]')
        pag.wait_for_selector("[data-acp-etapa-olho]")
        checar(pag.locator("[data-acp-etapa-olho]").count() == 5, "com a pasta compartilhada, um olhinho por etapa")
        pag.click('[data-acp-etapa-olho="3"]')
        pag.wait_for_selector('[data-acp-etapa-olho="3"].oculto')
        checar(True, "o olhinho esconde a etapa interna")
        pag.click('[data-sv-etapa-quem="4"]')
        pag.wait_for_selector(".menu-conversa.menu-novo")
        pag.click('.menu-conversa.menu-novo button:has-text("O cliente")')
        pag.wait_for_function("() => (document.querySelectorAll('[data-sv-etapa-quem]')[4] || {textContent: ''}).textContent.includes('cliente')")
        checar("cliente" in pag.inner_text('[data-sv-etapa-quem="4"]'), "a etapa passa a ser do cliente")
        pag.click(f'[data-acp-prazo-olho="{d["aud"]}"]')
        pag.click('.menu-conversa.menu-novo button:has-text("Pedir ao cliente que confirme")')
        pag.wait_for_selector(".acp-conf")
        checar(True, "pedir a confirmação da audiência")
        pag.wait_for_timeout(400)
        pag.screenshot(path=str(CAPTURAS / "escritorio-pasta.png"), full_page=True)
        pag.click('[data-sv-aba="arquivos"]')
        pag.wait_for_selector("[data-acp-doc]")
        pag.click("[data-acp-doc]")
        pag.wait_for_selector("[data-acp-doc].sim")
        checar(True, "compartilhar o documento na aba Arquivos")
        pag.screenshot(path=str(CAPTURAS / "escritorio-arquivos.png"))

        pag.click('[data-sv-aba="cliente"]')
        pag.wait_for_selector(".acp-pessoa")
        texto = pag.inner_text("#acp-aba")
        checar("Quem vê esta pasta" in texto and "Resumo para o cliente" in texto and "Conversa com o cliente" in texto
               and "Atividade do cliente" in texto and "O que o cliente vê" in texto, "a aba Cliente tem as cinco partes")
        pag.fill("[data-acp-resumo]", "Seu processo foi distribuído e o banco ainda vai ser citado. A audiência de conciliação está marcada; confirme o horário em “Para você”.")
        pag.click("[data-acp-publicar]")
        pag.wait_for_selector("text=publicado")
        pag.wait_for_timeout(400)
        pag.screenshot(path=str(CAPTURAS / "escritorio-aba-cliente.png"), full_page=True)
        pag.click("#acoes-tela [data-acp-ver]")
        pag.wait_for_selector(".acp-tela .pcl-cabeca h1")
        previa = pag.inner_text(".acp-tela")
        checar("Revisional do financiamento" in previa and "para você" in previa.lower() and "Estratégia interna" not in previa
               and "Cliente difícil" not in previa, "Ver como o cliente: a pasta como ele vê, sem o que está escondido", previa[:300])
        pag.wait_for_timeout(600)
        pag.screenshot(path=str(CAPTURAS / "escritorio-ver-como-cliente.png"))
        pag.click(".acp-tela [data-pcl-doc]")
        pag.wait_for_function("() => { const i = document.querySelector('.acp-tela .pcl-visor img'); return i && i.complete && i.naturalWidth > 0; }")
        checar(True, "a prévia abre o documento")
        pag.wait_for_timeout(300)
        pag.screenshot(path=str(CAPTURAS / "escritorio-previa-documento.png"))
        pag.keyboard.press("Escape")
        pag.keyboard.press("Escape")
        checar(not erros, "o escritório sem erro de página", erros[:3])
        ctx.close()

        for tema in ("light", "dark"):
            print(f"\no cliente, no celular ({tema})")
            cli = nav.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True,
                                  color_scheme=tema)
            cli.set_default_timeout(60000)
            c = cli.new_page()
            erros_c: list[str] = []
            c.on("pageerror", lambda e: erros_c.append(str(e)))
            c.goto(base + "/cliente/" + token, wait_until="load")
            c.wait_for_selector("#pcl-email")
            c.screenshot(path=str(CAPTURAS / f"cliente-entrar-{tema}.png"))
            c.fill("#pcl-email", "joao@cliente.com")
            c.click('[data-pcl-form-email] button[type="submit"]')
            c.wait_for_selector("#pcl-codigo")
            checar(emails[-1]["tipo"] == "codigo", "o código foi para o e-mail")
            c.screenshot(path=str(CAPTURAS / f"cliente-codigo-{tema}.png"))
            checar(c.evaluate("() => document.scrollingElement.scrollWidth") <= 390, "a tela do código cabe no celular")
            c.fill("#pcl-codigo", emails[-1]["codigo"])
            c.wait_for_selector(".pcl-cabeca h1")
            texto = c.inner_text("#pcl-raiz")
            # Na segunda volta (escuro), a pendencia e a confirmacao ja foram feitas na primeira.
            if tema == "light":
                checar("Revisional do financiamento" in texto and "para você" in texto.lower() and "enviar rg" in texto.lower()
                       and "confirmar: audiência" in texto.lower(), "a pasta abre com o que é para ele", texto[:200])
            else:
                checar("Revisional do financiamento" in texto and c.locator("[data-pcl-enviar], [data-pcl-confirmar]").count() == 0
                       and "Seu processo foi distribuído" in texto,
                       "a pasta abre sem pendências (resolvidas) e com o resumo publicado", texto[:200])
            checar("Estratégia interna" not in texto and "Cliente difícil" not in texto, "e sem o que é só do escritório")
            largura = c.evaluate("() => document.scrollingElement.scrollWidth")
            checar(largura <= 390, "sem rolagem de lado no celular", largura)
            c.wait_for_timeout(500)
            c.screenshot(path=str(CAPTURAS / f"cliente-pasta-{tema}.png"), full_page=True)
            c.click("[data-pcl-doc]")
            c.wait_for_function("() => { const i = document.querySelector('.pcl-visor img'); return i && i.complete && i.naturalWidth > 0; }")
            checar("1 de 1" in c.inner_text(".pcl-visor"), "o documento abre, com a contagem de páginas")
            c.wait_for_timeout(300)
            c.screenshot(path=str(CAPTURAS / f"cliente-documento-{tema}.png"))
            c.click("[data-pcl-fechar]")
            if tema == "light":
                c.fill("[data-pcl-escrever] textarea", "Bom dia! Preciso levar algum documento na audiência?")
                c.click('[data-pcl-escrever] button[type="submit"]')
                c.wait_for_selector(".pcl-msg.minha")
                checar(True, "o cliente escreve ao escritório")
                with c.expect_file_chooser() as escolha:
                    c.click("[data-pcl-enviar]")
                escolha.value.set_files(files=[{"name": "RG.jpg", "mimeType": "image/jpeg", "buffer": b"\xff\xd8\xff\xe0" + b"0" * 2000}])
                c.wait_for_function("() => { const t = document.querySelector('.pcl-toast'); return t && t.textContent.includes('chegou'); }")
                checar("chegou ao escritório" in c.inner_text(".pcl-toast"), "o arquivo da pendência chega", c.inner_text(".pcl-toast"))
                c.wait_for_function("() => !document.querySelector('[data-pcl-enviar]')")
                c.click("[data-pcl-confirmar]")
                c.wait_for_function("() => !document.querySelector('[data-pcl-confirmar]')")
                checar("Você confirmou este horário" in c.inner_text("#pcl-raiz"), "confirmar a audiência")
                c.wait_for_timeout(600)
                c.screenshot(path=str(CAPTURAS / "cliente-depois.png"), full_page=True)
            checar(not erros_c, f"o cliente sem erro de página ({tema})", erros_c[:3])
            cli.close()

        print("\no escritorio ve o que o cliente fez")
        ativ = local.get(f"/api/servicos/{sid}/cliente/atividade").json()["atividade"]
        acoes = {a["acao"] for a in ativ}
        checar({"entrou", "abriu_pasta", "abriu", "escreveu", "enviou", "confirmou"} <= acoes, "a atividade tem cada passo", sorted(acoes))
        nav.close()

    print(f"\n  capturas em {CAPTURAS}")
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print("    - " + f)
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
