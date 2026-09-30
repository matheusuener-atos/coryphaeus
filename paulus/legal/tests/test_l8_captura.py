"""
L8 - captura pelo celular (src/captura.py, js/51-captura.js).

  - a nitidez e a luz: página nítida passa (com ou sem ruído de celular);
    desfocada e escura são avisadas; a conferência não grava nada;
  - destino num Serviço: o PDF vai para a pasta do Serviço; Serviço que não
    existe (ou que a pessoa de fora não vê) é recusado;
  - de fora, o pedido em Aprovações leva o Serviço, e o sim põe lá;
  - a entrada diz o que a leitura achou (páginas pelo OCR e caracteres), ou
    por que não leu;
  - no Edge: a prévia avisa a foto tremida, o destino no Serviço e a frase
    da leitura.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_l8_captura.py
"""

from __future__ import annotations

import io
import os
import random
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-l8-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def pagina():
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (2480, 3508), "white")
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("arial.ttf", 56)
    except OSError:
        f = None
    for i in range(40):
        d.text((150, 150 + i * 80), f"Cláusula {i + 1}. O locatário pagará o aluguel até o quinto dia útil.", fill="black", font=f)
    return img


def jpeg(img) -> bytes:
    s = io.BytesIO()
    img.save(s, "JPEG", quality=85)
    return s.getvalue()


def main() -> int:
    print("=" * 55)
    print("  L8 — captura pelo celular")
    print("=" * 55)
    from PIL import Image, ImageFilter

    import captura

    random.seed(1)
    base = pagina()
    ruido = Image.effect_noise(base.size, 40).convert("RGB")
    nitida = jpeg(base)
    com_ruido = jpeg(Image.blend(base, ruido, 0.25))
    tremida = jpeg(base.filter(ImageFilter.GaussianBlur(5)))
    escura = jpeg(base.point(lambda p: int(p * 0.18)))

    print("\na nitidez e a luz")
    q = [captura.qualidade(x) for x in (nitida, com_ruido, tremida, escura)]
    checar(not q[0]["borrada"] and not q[0]["escura"] and not q[1]["borrada"], "nítida passa, com ou sem ruído de celular", q[:2])
    checar(q[2]["borrada"], "desfocada: avisada", q[2])
    checar(q[3]["escura"], "escura: avisada", q[3])

    import api
    from fastapi.testclient import TestClient

    api.estado.prefs.dados.setdefault("umbrel", {})["captura"] = True
    local = TestClient(api.app, headers=api.cabecalho_local())
    r = local.post("/api/captura/conferir", files=[("fotos", ("a.jpg", nitida, "image/jpeg")), ("fotos", ("b.jpg", tremida, "image/jpeg"))])
    fotos = r.json()["fotos"]
    checar([f["borrada"] for f in fotos] == [False, True] and not list((TMP / "dados").rglob("*.pdf")),
           "a conferência pela rota: a tremida marcada, e nada gravado", fotos)

    print("\ndestino no Serviço e a leitura")
    s1 = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Audiência Alfa"}}).json()["id"]
    r = local.post("/api/captura", data={"titulo": "Intimação", "servico_id": str(s1), "giros": "[0,0]"},
                   files=[("fotos", ("a.jpg", nitida, "image/jpeg")), ("fotos", ("b.jpg", nitida, "image/jpeg"))])
    d = r.json()
    pasta = api.estado.servicos.pasta_de(s1)
    checar(r.status_code == 200 and d["servico_id"] == s1 and (Path(pasta) / d["nome"]).exists(), "o PDF vai para a pasta do Serviço", d)
    import ocr_windows

    if ocr_windows.situacao().get("ok"):
        checar(d["leitura"]["lido"] and d["leitura"]["ocr_paginas"] == 2 and d["leitura"]["caracteres"] > 500,
               "a entrada diz o que a leitura achou: 2 páginas pelo OCR", d["leitura"])
    else:
        checar(not d["leitura"]["lido"] and d["leitura"]["motivo"], "sem OCR nesta máquina: a entrada diz por quê", d["leitura"])
    checar(local.post("/api/captura", data={"servico_id": "9999"}, files=[("fotos", ("a.jpg", nitida, "image/jpeg"))]).status_code == 404,
           "Serviço que não existe: recusa")

    print("\nde fora")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI")
    else:
        from acesso.contas import codigo_totp

        servico = api.estado.acesso_de_fora
        servico.conferir_turnstile = lambda token, ip="": "ok"
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = True
        api.estado.prefs.dados["acesso_remoto"]["so_google"] = False
        servico.contas.criar("Mateus", "mateus@x.com", "titular", "senha-forte-mateus")
        conta = servico.contas.criar("Rui", "rui@x.com", "colaborador", "senha-forte-rui")
        servico.contas.confirmar_totp(conta["conta"]["id"], codigo_totp(conta["segredo"], int(time.time() // 30)))
        local.put(f"/api/acesso/contas/{conta['conta']['id']}/permissoes", json={"niveis": {"servicos": "faz", "acervo": "ver"}})
        rui = local.post("/api/cadastros", json={"id": None, "dados": {"tipo": "colaborador", "nome": "Rui", "email": "rui@x.com"}}).json()["id"]
        s_rui = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Do Rui"}}).json()["id"]
        api.estado.base.escrever("UPDATE servicos SET equipe = ? WHERE id = ?", (f"[{rui}]", s_rui))
        f = TestClient(api.app, base_url="https://x.paulus.ia.br", headers={"Cf-Connecting-IP": "200.2.2.2"})
        pend = f.post("/api/acesso/entrar", json={"email": "rui@x.com", "senha": "senha-forte-rui", "turnstile": "ok"}).json()["pendente"]
        rr = f.post("/api/acesso/entrar/codigo", json={"pendente": pend, "codigo": codigo_totp(conta["segredo"], int(time.time() // 30) + 1)})
        f.headers["X-PAULUS-CSRF"] = rr.json()["csrf"]
        checar(f.post("/api/captura", data={"servico_id": str(s1)}, files=[("fotos", ("a.jpg", nitida, "image/jpeg"))]).status_code == 404,
               "de fora, Serviço que a pessoa não vê: recusa")
        r = f.post("/api/captura", data={"titulo": "Do fórum", "servico_id": str(s_rui)}, files=[("fotos", ("a.jpg", nitida, "image/jpeg"))])
        d = r.json()
        checar(r.status_code == 200 and d["destino"] == "aprovacoes" and d["servico_id"] == s_rui, "de fora: vai para Aprovações, com o Serviço", d)
        r = local.post("/api/aprovacoes/decidir", json={"ids": [d["pedido"]], "aprovar": True})
        pasta_rui = Path(api.estado.servicos.pasta_de(s_rui))
        resultado = (api.estado.fila.obter(d["pedido"]) or type("x", (), {"resultado": ""})).resultado
        checar(any(x.name.startswith("Do fórum") for x in pasta_rui.glob("*.pdf")), "o sim põe o PDF na pasta do Serviço", list(pasta_rui.glob("*")))
        if resultado:
            checar("entrou no Serviço" in resultado and ("li " in resultado or "sem texto" in resultado), "e diz o que a leitura achou", resultado)
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = False

    print("\nno Edge")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None
        print("  pulado: playwright não instalado")
    if sync_playwright is not None:
        from test_gravacoes import _porta_livre, _subir_servidor

        (TMP / "n.jpg").write_bytes(nitida)
        (TMP / "t.jpg").write_bytes(tremida)
        porta = _porta_livre()
        _subir_servidor(porta)
        with sync_playwright() as p:
            try:
                nav = p.chromium.launch(channel="msedge")
            except Exception as exc:  # noqa: BLE001
                nav = None
                print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            if nav is not None:
                pag = nav.new_context(viewport={"width": 1280, "height": 900}).new_page()
                erros = []
                pag.on("pageerror", lambda e: erros.append(str(e)))
                pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
                pag.goto(f"http://127.0.0.1:{porta}/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
                pag.wait_for_function("() => typeof fotografarDocumento === 'function'")
                pag.wait_for_timeout(800)
                with pag.expect_file_chooser() as escolha:
                    pag.evaluate("() => { fotografarDocumento(); }")
                escolha.value.set_files([str(TMP / "n.jpg"), str(TMP / "t.jpg")])
                pag.wait_for_selector(".cap-alerta", timeout=20000)
                alertas = pag.locator(".cap-alerta").all_inner_texts()
                checar(len(alertas) == 1 and "tremida" in alertas[0], "a prévia avisa só a foto tremida", alertas)
                # O select fica atrás do botão de escolha do programa (js/16-dialogos.js).
                pag.evaluate(f"() => {{ const s = document.getElementById('cap-servico'); s.value = '{s1}'; s.dispatchEvent(new Event('change')); }}")
                pag.screenshot(path=str(TMP / "l8-previa.png"))
                pag.click("[data-cap-tirar='1']")
                pag.wait_for_function("() => document.querySelectorAll('.cap-foto').length === 1", timeout=5000)
                pag.get_by_role("button", name="Guardar no Acervo").click()
                pag.wait_for_selector("text=entrou no Serviço", timeout=60000)
                aviso = pag.inner_text("body")
                checar("entrou no Serviço" in aviso and ("li " in aviso or "não li texto" in aviso), "o aviso diz onde entrou e o que leu")
                checar(not erros, "nenhum erro de JavaScript", erros[:3])
                print(f"  (foto em {TMP})")
                nav.close()

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
