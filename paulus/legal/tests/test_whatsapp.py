"""
WhatsApp Web ao lado do PAULUS (src/conexoes.py, src/api.py, js/05-configuracoes.js).

  - a ficha do cliente com telefone tem o botao WhatsApp; sem telefone, nao;
  - o botao abre "Preparar uma mensagem" ja com o telefone e o contato
    escolhido; preparar monta o endereco oficial e anota para quem, sem o texto;
  - fora do programa (no navegador), nada de janela: o pop-up mostra o
    endereco, em vez de fingir que abriu;
  - /api/conexoes/abrir recusa endereco de fora e anexo que nao existe;
  - apagar sem sessao diz que nao havia; as rotas sao da janela do escritorio.

A janela de verdade (uma so, encaixada a direita, o programa encolhendo e
voltando, o anexo selecionado no Explorer, apagar pelo DevTools do WebView2)
foi conferida abrindo o programa numa pasta de dados temporaria em
12/10/2026; ela precisa do pywebview com tela, e nao roda aqui.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_whatsapp.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-whats-"))
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
    print("  WhatsApp Web ao lado do Paulus")
    print("=" * 55)
    import api
    from acesso import politicas
    from fastapi.testclient import TestClient

    local = TestClient(api.app, headers=api.cabecalho_local())
    maria = local.post("/api/cadastros", json={"id": None, "dados": {"tipo": "cliente", "nome": "Maria Souza",
                                                                     "telefone": "(62) 99999-8888"}}).json()["id"]
    sem = local.post("/api/cadastros", json={"id": None, "dados": {"tipo": "cliente", "nome": "Rui Sem Telefone"}}).json()["id"]

    print("\na rota")
    r = local.post("/api/conexoes/abrir", json={"endereco": "https://exemplo.com"})
    checar(r.status_code == 400, "não abre endereço que não é do WhatsApp", r.text[:120])
    r = local.post("/api/conexoes/abrir", json={"anexo": str(TMP / "nao-existe.pdf")})
    checar(r.status_code == 400 and "arquivo" in r.text, "anexo que não existe é recusado", r.text[:120])
    pdf = TMP / "Procuração.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
    r = local.post("/api/conexoes/abrir", json={"anexo": str(pdf)}).json()
    checar(r["abriu"] is False and "programa" in r["motivo"], "sem a janela do programa, diz que não abriu (sem fingir)", r)
    r = local.post("/api/conexoes/sessao/apagar").json()
    checar(r["apagou"] is False and "Não havia" in r["aviso"], "apagar sem sessão diz que não havia", r)
    rotas = ("GET /api/conexoes", "POST /api/conexoes/abrir", "POST /api/conexoes/mensagem",
             "POST /api/conexoes/sessao/apagar", "GET /api/conexoes/contatos")
    checar(all(politicas.de(*x.split(" ", 1)) == politicas.BLOQUEADO for x in rotas), "de fora, as rotas são da janela do escritório")

    print("\nno Edge")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return _fim()
    from test_gravacoes import _porta_livre, _subir_servidor

    porta = _porta_livre()
    _subir_servidor(porta)
    with sync_playwright() as p:
        try:
            nav = p.chromium.launch(channel="msedge")
        except Exception as exc:  # noqa: BLE001
            print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            return _fim()
        pag = nav.new_context(viewport={"width": 1280, "height": 900}).new_page()
        erros = []
        pag.on("pageerror", lambda e: erros.append(str(e)))
        pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
        pag.goto(f"http://127.0.0.1:{porta}/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
        pag.wait_for_function("() => typeof mostrarCadastros === 'function' && typeof verFicha === 'function'")
        pag.wait_for_timeout(800)
        pag.evaluate("() => { mostrarCadastros(); }")
        pag.wait_for_selector(f"[data-cad-abrir='{sem}']", timeout=15000)

        pag.click(f"[data-cad-abrir='{sem}']")
        pag.wait_for_selector(".dialogo.cad-dialogo", timeout=10000)
        checar(pag.locator(".cad-dialogo [data-cad-whatsapp]").count() == 0, "ficha sem telefone: sem botão WhatsApp")
        pag.keyboard.press("Escape")
        pag.wait_for_timeout(400)

        pag.click(f"[data-cad-abrir='{maria}']")
        pag.wait_for_selector(".cad-dialogo [data-cad-whatsapp]", timeout=10000)
        checar(True, "ficha com telefone: botão WhatsApp")
        pag.click(".cad-dialogo [data-cad-whatsapp]")
        pag.wait_for_selector("#cx-telefone", timeout=10000)
        pag.wait_for_function("() => document.querySelector('#cx-contato').options.length > 1")
        checar(pag.input_value("#cx-telefone") == "(62) 99999-8888", "o telefone já vem preenchido", pag.input_value("#cx-telefone"))
        escolhido = pag.evaluate("() => { const o = document.querySelector('#cx-contato').selectedOptions[0]; return o ? o.textContent : ''; }")
        checar(escolhido.startswith("Maria Souza"), "e o contato já vem escolhido", escolhido)
        visivel = pag.inner_text("#cx-contato-botao")
        checar(visivel.startswith("Maria Souza"), "e o botão de escolha mostra o contato (não só o select escondido)", visivel)
        checar("Maria Souza" in pag.inner_text("#veu-dialogo"), "o pop-up diz para quem é")
        pag.fill("#cx-texto", "Sua audiência foi remarcada.")
        pag.screenshot(path=str(TMP / "whats-preparar.png"))
        pag.click("#veu-dialogo [data-dialogo='confirmar']")
        pag.wait_for_selector("#veu-dialogo .cfg-endereco", timeout=10000)
        endereco = pag.inner_text("#veu-dialogo .cfg-endereco")
        checar(endereco.startswith("https://web.whatsapp.com/send?phone=5562999998888"),
               "sem a janela do programa, mostra o endereço oficial da conversa", endereco)
        item = api.estado.conexoes.itens[0]
        checar(item["nome"] == "Maria Souza" and item["para"] == "5562999998888" and "texto" not in item,
               "anota para quem, sem guardar o texto", item)
        pag.keyboard.press("Escape")
        checar(not erros, "nenhum erro de JavaScript", erros[:3])
        print(f"  (fotos em {TMP})")
        nav.close()
    return _fim()


def _fim() -> int:
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
