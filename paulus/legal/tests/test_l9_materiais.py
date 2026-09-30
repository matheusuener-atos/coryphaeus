"""
L9 - materiais entre advogados (src/comunidade.py, js/70-comunidade.js,
site/materiais/, site/dados/materiais.json).

Com o site trocado por um de mentira (nada sai daqui):

  - a conferência dos dados pessoais: processo, CNPJ, CPF válido, e-mail,
    telefone, nome de cliente do escritório; CPF inválido, data e valor não;
  - o e-mail montado para o projeto, com a autorização da licença; título
    obrigatório; texto curto recusado;
  - trazer um material: entra na Biblioteca com a origem "comunidade", o
    autor e a licença; hash errado não entra; endereço fora de /materiais/
    também não;
  - o site: a lista é JSON válido, a página lê e mostra (vazia e com um
    material);
  - no Edge: a aba "Da comunidade", ver, trazer, conferir e montar o e-mail.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_l9_materiais.py
"""

from __future__ import annotations

import functools
import hashlib
import http.server
import json
import os
import sys
import tempfile
import threading
from pathlib import Path

RAIZ = Path(__file__).parent.parent
SITE = RAIZ.parents[1] / "site"
TMP = Path(tempfile.mkdtemp(prefix="paulus-l9-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []
TEXTO = ("# A multa moratória no contrato de locação\n\nA multa moratória de dez por cento, prevista em contratos de locação "
         "residencial, tem sido discutida à luz do Código de Defesa do Consumidor. Este texto reúne os argumentos principais "
         "e os precedentes que o escritório usa.\n")


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def main() -> int:
    print("=" * 55)
    print("  L9 — materiais entre advogados")
    print("=" * 55)
    import comunidade as c

    print("\nos dados pessoais")
    t = ("O cliente, CPF 529.982.247-25 (e o 111.111.111-11, que não vale), da Construtora Alfa Ltda (CNPJ 11.222.333/0001-81), "
         "processo 0001234-71.2024.8.26.0100, e-mail joao@x.com, tel (11) 98765-4321. Prazo de 15 dias. Valor R$ 1.234,56 em 12/10/2024.")
    achados = c.conferir_dados(t, ["Construtora Alfa Ltda", "Maria Souza"])
    tipos = sorted(a["tipo"] for a in achados)
    checar(tipos == sorted(["número de processo", "CNPJ", "CPF", "e-mail", "telefone", "nome de cliente do escritório"]),
           "processo, CNPJ, CPF, e-mail, telefone e o cliente do escritório", achados)
    checar(not any("111.111" in a["trecho"] or "1.234" in a["trecho"] or "12/10" in a["trecho"] for a in achados),
           "CPF inválido, valor e data não são dado pessoal")
    e = c.preparar(TEXTO, {"titulo": "A multa", "autor": "Maria", "area": "civil"})
    checar(e["para"] == "contato@paulus.ia.br" and "CC BY 4.0" in e["corpo"] and TEXTO.strip() in e["corpo"], "o e-mail montado, com a licença")

    print("\ntrazer do site")
    arquivo = TEXTO.encode("utf-8")
    lista = {"atualizado_em": "2026-10-01", "materiais": [
        {"slug": "multa-moratoria", "titulo": "A multa moratória", "autor": "Maria Souza", "oab": "SP 1", "areas": ["civil"],
         "tipo": "artigo", "resumo": "Quando é abusiva.", "publicado_em": "2026-10-01", "licenca": "CC BY 4.0",
         "arquivo": "/materiais/multa-moratoria.md", "sha256": hashlib.sha256(arquivo).hexdigest()},
        {"slug": "errado", "titulo": "Hash errado", "arquivo": "/materiais/errado.md", "sha256": "0" * 64},
        {"slug": "fora", "titulo": "De outro lugar", "arquivo": "https://outro.site/x.md"}]}
    pedidos = []

    def baixar(url):
        pedidos.append(url)
        if url.endswith("/dados/materiais.json"):
            return json.dumps(lista).encode()
        return arquivo
    c.BAIXAR["fn"] = baixar

    import api
    from fastapi.testclient import TestClient

    local = TestClient(api.app, headers=api.cabecalho_local())
    checar(not pedidos, "nada é pedido ao site antes de a pessoa pedir")
    d = local.get("/api/comunidade/materiais").json()
    checar([m["slug"] for m in d["materiais"]] == ["multa-moratoria", "errado", "fora"] and pedidos == [c.SITE + c.LISTA],
           "ver: só a lista pública é pedida", pedidos)
    r = local.post("/api/comunidade/materiais/multa-moratoria/trazer")
    item = r.json().get("item", {})
    ficha = item.get("ficha", {})
    checar(r.status_code == 200 and ficha.get("origem") == "comunidade" and ficha.get("autor") == "Maria Souza" and "CC BY" in ficha.get("licenca", ""),
           "trazer: entra na Biblioteca com a origem, o autor e a licença", ficha)
    checar(local.post("/api/comunidade/materiais/errado/trazer").status_code == 400, "hash errado: não entra")
    checar(local.post("/api/comunidade/materiais/fora/trazer").status_code == 400, "endereço fora do site: não entra")
    checar(local.post("/api/comunidade/materiais/nao-existe/trazer").status_code == 404, "material que não está na lista: 404")

    print("\npreparar o envio")
    local.post("/api/cadastros", json={"id": None, "dados": {"tipo": "cliente", "nome": "Construtora Alfa Ltda"}})
    checar(local.post("/api/comunidade/preparar", json={"titulo": "x", "texto": "curto"}).status_code == 400, "texto curto: recusa")
    checar(local.post("/api/comunidade/preparar", json={"titulo": "", "texto": TEXTO * 2}).status_code == 400, "sem título: recusa")
    r = local.post("/api/comunidade/preparar", json={"titulo": "A multa", "texto": TEXTO + " Caso da CONSTRUTORA ALFA, CNPJ 11.222.333/0001-81."})
    d = r.json()
    checar(r.status_code == 200 and {a["tipo"] for a in d["achados"]} == {"CNPJ", "nome de cliente do escritório"} and d["email"]["assunto"].endswith("A multa"),
           "acha o cliente (com outro jeito de escrever) e o CNPJ, e monta o e-mail", d["achados"])

    print("\no site")
    dados = json.loads((SITE / "dados" / "materiais.json").read_text(encoding="utf-8"))
    pagina = (SITE / "materiais" / "index.html").read_text(encoding="utf-8")
    checar(isinstance(dados.get("materiais"), list), "a lista curada é JSON válido")
    checar("materiais.js" in pagina and 'aria-current="page">Materiais' in pagina and "<title>Materiais — PAVLVS</title>" in pagina,
           "a página tem o título, o menu e o script")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None
        print("  pulado: playwright não instalado")
    if sync_playwright is not None:
        from test_gravacoes import _porta_livre, _subir_servidor

        porta_site = _porta_livre()
        servidor_site = http.server.ThreadingHTTPServer(("127.0.0.1", porta_site),
                                                        functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE)))
        threading.Thread(target=servidor_site.serve_forever, daemon=True).start()
        porta = _porta_livre()
        _subir_servidor(porta)
        with sync_playwright() as p:
            try:
                nav = p.chromium.launch(channel="msedge")
            except Exception as exc:  # noqa: BLE001
                nav = None
                print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            if nav is not None:
                ctx = nav.new_context(viewport={"width": 1280, "height": 900})
                pag = ctx.new_page()
                pag.goto(f"http://127.0.0.1:{porta_site}/materiais/", wait_until="load")
                pag.wait_for_function("() => !/Carregando/.test(document.getElementById('mt-lista').textContent)", timeout=10000)
                checar("Ainda não há materiais" in pag.inner_text("#mt-lista"), "a página do site, vazia, diz isso")
                pag.route("**/dados/materiais.json", lambda rota: rota.fulfill(status=200, content_type="application/json",
                                                                              body=json.dumps({"materiais": lista["materiais"][:1]})))
                pag.reload(wait_until="load")
                pag.wait_for_selector(".mt-item", timeout=10000)
                checar("A multa moratória" in pag.inner_text("#mt-lista") and "Maria Souza · OAB SP 1" in pag.inner_text("#mt-lista"),
                       "com um material, a página mostra título, autor e licença")
                pag.screenshot(path=str(TMP / "l9-site.png"))

                print("\nno Edge: a Biblioteca")
                pag = ctx.new_page()
                erros = []
                pag.on("pageerror", lambda e_: erros.append(str(e_)))
                pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
                pag.goto(f"http://127.0.0.1:{porta}/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
                pag.wait_for_function("() => typeof mostrarBibliotecaContexto === 'function' && typeof abaComunidadeBib === 'function'")
                pag.wait_for_timeout(800)
                pag.evaluate("() => mostrarBibliotecaContexto('comunidade')")
                pag.wait_for_selector("[data-com-ver]", timeout=15000)
                pag.click("[data-com-ver]")
                pag.wait_for_selector("[data-com-trazer]", timeout=10000)
                pag.click("[data-com-trazer='multa-moratoria']")
                pag.wait_for_selector("text=Na Biblioteca", timeout=10000)
                checar(True, "ver e trazer pela aba")
                pag.fill("#com-titulo", "Meu material")
                pag.fill("#com-texto", TEXTO + " Cliente: Construtora Alfa Ltda.")
                pag.click("[data-com-preparar]")
                pag.wait_for_selector(".com-achados", timeout=10000)
                checar("nome de cliente do escritório" in pag.inner_text(".com-achados") and pag.input_value("#com-titulo") == "Meu material",
                       "conferir: mostra o cliente achado e guarda o que foi escrito")
                pag.click("[data-com-email]")
                pag.wait_for_timeout(300)
                checar("marque que tirou" in pag.inner_text("body"), "sem o “tirei os dados”, não monta o e-mail")
                pag.check("#com-conferi")
                pag.click("[data-com-email]")
                pag.wait_for_timeout(600)
                checar("copiei o material" in pag.inner_text("body") or pag.locator("text=Escrever").count() > 0,
                       "sem conta de e-mail, copia o material para mandar")
                pag.screenshot(path=str(TMP / "l9-biblioteca.png"))
                checar(not erros, "nenhum erro de JavaScript", erros[:3])
                print(f"  (fotos em {TMP})")
                nav.close()
        servidor_site.shutdown()

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
