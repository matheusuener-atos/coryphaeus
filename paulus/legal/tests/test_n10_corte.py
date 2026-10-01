"""
N10 - a folha na foto: cortar a mesa e endireitar a perspectiva (src/corte_da_foto.py, src/captura.py, js/51-captura.js).

Com fotos montadas (a folha com texto, torta ou em perspectiva, sobre uma
mesa escura, com ruído e desfoque leve):

  - os quatro cantos achados ficam a menos de 1,5% de onde a folha está;
  - folha que ocupa a foto inteira, fundo claro como a folha e folha pequena
    demais: não corta, e diz por quê;
  - endireitada, a folha sai retangular (a proporção do trapézio desfeita) e
    o OCR do Windows lê pelo menos tantas palavras certas quanto na foto
    crua (com a foto em perspectiva, mais);
  - a captura: a conferência traz os cantos; com "cortar", o PDF sai com a
    folha endireitada e a resposta diz quantas; sem, como veio;
  - no Edge: o contorno da folha na prévia, e o botão que desliga o corte.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_n10_corte.py
"""

from __future__ import annotations

import io
import json
import os
import random
import re
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-n10-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []
PALAVRAS = ["contrato", "locação", "cláusula", "multa", "prazo", "aluguel", "imóvel", "partes", "fiador", "garantia"]


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def folha(w=1240, h=1754):
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (w, h), (245, 243, 238))
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("arial.ttf", 34)
    except OSError:
        f = ImageFont.load_default()
    random.seed(3)
    y = 120
    while y < h - 120:
        d.text((110, y), " ".join(random.choice(PALAVRAS) for _ in range(7)), fill=(30, 30, 30), font=f)
        y += 52
    return img


def foto(cantos, W=3000, H=4000, fundo=(70, 52, 40)):
    from PIL import Image, ImageFilter

    import corte_da_foto as c

    pag = folha()
    base = Image.new("RGB", (W, H), fundo)
    q = [(x * W, y * H) for x, y in cantos]
    coef = c._coeficientes(q, [(0, 0), (pag.width, 0), (pag.width, pag.height), (0, pag.height)])
    mascara = Image.new("L", pag.size, 255).transform((W, H), Image.PERSPECTIVE, coef, Image.BILINEAR)
    base.paste(pag.transform((W, H), Image.PERSPECTIVE, coef, Image.BICUBIC), (0, 0), mascara)
    ruido = Image.effect_noise((W, H), 18).convert("RGB")
    return Image.blend(base, ruido, 0.08).filter(ImageFilter.GaussianBlur(1))


def jpeg(img) -> bytes:
    b = io.BytesIO()
    img.save(b, format="JPEG", quality=88)
    return b.getvalue()


def certas(texto: str) -> int:
    return sum(1 for p in re.findall(r"\w+", texto.lower()) if p in PALAVRAS)


CASOS = {"torta": [(0.18, 0.12), (0.80, 0.18), (0.86, 0.86), (0.12, 0.80)],
         "perspectiva": [(0.25, 0.10), (0.75, 0.10), (0.92, 0.90), (0.08, 0.90)],
         "reta": [(0.15, 0.10), (0.85, 0.10), (0.85, 0.90), (0.15, 0.90)]}


def main() -> int:
    print("=" * 55)
    print("  N10 — cortar a mesa e endireitar a folha")
    print("=" * 55)
    import corte_da_foto as c
    import ocr_windows

    print("\nachar a folha")
    fotos = {n: foto(q) for n, q in CASOS.items()}
    for nome, q in CASOS.items():
        r = c.achar_folha(fotos[nome])
        erro = max(abs(a - b) for p, s_ in zip(r.get("cantos") or [[9, 9]] * 4, q) for a, b in zip(p, s_))
        checar(r["achou"] and erro < 0.015, f"{nome}: os quatro cantos a menos de 1,5%", (r.get("motivo"), round(erro, 4)))
    r = c.achar_folha(folha())
    checar(not r["achou"] and "não vi borda" in r["motivo"], "folha que ocupa a foto: não corta, e diz", r)
    r = c.achar_folha(foto(CASOS["torta"], fundo=(236, 235, 230)))
    checar(not r["achou"] and r["motivo"], "fundo claro como a folha: não corta, e diz", r.get("motivo"))
    r = c.achar_folha(foto([(0.42, 0.42), (0.58, 0.42), (0.58, 0.58), (0.42, 0.58)]))
    checar(not r["achou"] and "pouco da foto" in r["motivo"], "folha pequena demais: pede para aproximar", r.get("motivo"))

    print("\nendireitar")
    r = c.achar_folha(fotos["perspectiva"])
    reta = c.endireitar(fotos["perspectiva"], r["cantos"])
    q = CASOS["perspectiva"]
    largura_meio = ((q[1][0] - q[0][0]) * 3000 + (q[2][0] - q[3][0]) * 3000) / 2
    checar(reta.width >= int((q[2][0] - q[3][0]) * 3000) - 30, "o trapézio vira retângulo pelo lado maior", (reta.size, largura_meio))
    reta.save(TMP / "n10-endireitada.jpg")
    if ocr_windows.situacao().get("ok"):
        crua = certas(ocr_windows.ler_imagem(fotos["perspectiva"]))
        endireitada = certas(ocr_windows.ler_imagem(reta))
        checar(endireitada >= crua and endireitada > 150, "o OCR lê mais palavras certas na folha endireitada", (crua, endireitada))
        torta_crua = certas(ocr_windows.ler_imagem(fotos["torta"]))
        torta_reta = certas(ocr_windows.ler_imagem(c.endireitar(fotos["torta"], c.achar_folha(fotos["torta"])["cantos"])))
        checar(torta_reta >= torta_crua, "e na torta também, pelo menos tantas", (torta_crua, torta_reta))
    else:
        print("  pulado: sem o OCR do Windows")

    print("\na captura")
    import api
    from fastapi.testclient import TestClient

    api.estado.prefs.dados.setdefault("umbrel", {})["captura"] = True
    local = TestClient(api.app, headers=api.cabecalho_local())
    b_persp, b_cheia = jpeg(fotos["perspectiva"]), jpeg(folha())
    d = local.post("/api/captura/conferir", files=[("fotos", ("a.jpg", b_persp, "image/jpeg")), ("fotos", ("b.jpg", b_cheia, "image/jpeg"))]).json()
    f0, f1 = d["fotos"][0].get("folha") or {}, d["fotos"][1].get("folha") or {}
    checar(f0.get("achou") and len(f0["cantos"]) == 4 and f0["largura"] == 3000 and not f1.get("achou") and f1.get("motivo"),
           "a conferência traz os cantos (e o motivo, quando não corta)", (f0, f1))
    r = local.post("/api/captura", files=[("fotos", ("a.jpg", b_persp, "image/jpeg")), ("fotos", ("b.jpg", b_cheia, "image/jpeg"))],
                   data={"giros": "[0, 0]", "cortes": json.dumps([True, True]), "titulo": "Endireitada"}).json()
    checar(r.get("destino") == "acervo" and r.get("cortadas") == 1 and r.get("paginas") == 2, "com “cortar”: uma endireitada (a outra não tinha o que cortar)", r)
    r = local.post("/api/captura", files=[("fotos", ("a.jpg", b_persp, "image/jpeg"))], data={"giros": "[0]", "cortes": "[false]", "titulo": "Crua"}).json()
    checar(r.get("cortadas") == 0, "sem “cortar”: vai como veio", r)

    print("\nno Edge")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None
        print("  pulado: playwright não instalado")
    if sync_playwright is not None:
        from test_gravacoes import _porta_livre, _subir_servidor

        caminho_foto = TMP / "foto-perspectiva.jpg"
        caminho_foto.write_bytes(b_persp)
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
                with pag.expect_file_chooser() as fc:
                    pag.evaluate("() => { fotografarDocumento(); }")
                fc.value.set_files(str(caminho_foto))
                pag.wait_for_selector(".cap-quadro polygon", timeout=20000)
                checar(pag.locator("[data-cap-cortar].on").count() == 1, "a prévia mostra o contorno e o corte ligado")
                pag.wait_for_timeout(300)
                pag.screenshot(path=str(TMP / "n10-previa.png"))
                pag.click("[data-cap-cortar]")
                pag.wait_for_timeout(300)
                checar(pag.locator(".cap-quadro polygon").count() == 0 and "vai como veio" in pag.inner_text(".cap-previa"),
                       "o botão desliga o corte")
                pag.click("[data-cap-cortar]")
                pag.click("#veu-dialogo [data-dialogo='confirmar']")
                try:
                    pag.wait_for_function("() => document.body.innerText.includes('endireitada')", timeout=30000)
                except Exception:  # noqa: BLE001 - a checagem abaixo diz o que veio
                    pass
                checar("endireitada" in pag.inner_text("body"), "guardar: o aviso diz que endireitou", pag.inner_text("body")[-300:])
                checar(not erros, "nenhum erro de JavaScript", erros[:3])
                print(f"  (fotos em {TMP})")
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
