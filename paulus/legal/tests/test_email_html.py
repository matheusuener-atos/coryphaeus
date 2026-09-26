"""
O e-mail em HTML: o que sai limpo para o iframe isolado da caixa.

O iframe (sem script, com CSP) e a barreira principal; aqui se confere a
segunda - que codigo, formulario e evento saem, que a imagem embutida (cid:)
entra como data URI, e que as imagens de fora sao contadas para a tela
bloquear.

Rodar: venv\\Scripts\\python.exe tests\\test_email_html.py
"""

from __future__ import annotations

import sys
from email.message import EmailMessage
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import correio  # noqa: E402

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {str(detalhe)[:300]}")
        _falhas.append(descricao)


PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")

HTML = """<html><head><script>alert(1)</script><link rel="stylesheet" href="https://x.test/a.css">
<style>@import url(https://x.test/b.css); .t{color:red}</style></head>
<body onload="roubar()"><h1 class="t">Olá</h1>
<p>Veja <a href="javascript:alert(2)">aqui</a> e <a href="https://exemplo.com.br">o site</a>.</p>
<img src="cid:logo123"> <img src="https://rastreio.test/pixel.gif" width="1">
<div style="background:url(https://x.test/fundo.png)">x</div>
<form action="https://x.test"><input name="senha"></form>
<iframe src="https://x.test"></iframe></body></html>"""


def montar() -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = "Remetente <a@exemplo.com.br>"
    msg["To"] = "b@exemplo.com.br"
    msg["Subject"] = "Teste"
    msg.set_content("Olá\nVeja o site.")
    msg.add_alternative(HTML, subtype="html")
    parte_html = msg.get_payload()[1]
    parte_html.add_related(PNG, maintype="image", subtype="png", cid="<logo123>")
    msg.add_attachment(b"%PDF-1.4 teste", maintype="application", subtype="pdf", filename="contrato.pdf")
    return msg


def test_limpeza() -> None:
    print("\nHTML limpo para o iframe")
    texto, anexos, html, remotas = correio._corpo_legivel(montar())
    checar("Olá" in texto, "o texto puro continua vindo")
    checar(bool(html) and "<h1" in html, "a versão HTML vem junto")
    for proibido in ("<script", "alert(1)", "onload", "<form", "<iframe", "<link", "@import", "javascript:"):
        checar(proibido not in html.lower(), f"sai: {proibido}")
    checar("data:image/png;base64," in html and "cid:logo123" not in html, "a imagem embutida vira data URI")
    checar('href="https://exemplo.com.br"' in html, "link comum continua")
    checar(remotas == 2, "conta as imagens de fora (img e fundo)", remotas)
    nomes = [a["nome"] for a in anexos]
    checar(nomes == ["contrato.pdf"], "a imagem embutida não aparece como anexo; o PDF sim", nomes)


def test_sem_html() -> None:
    print("\nE-mail só em texto")
    msg = EmailMessage()
    msg.set_content("só texto")
    texto, anexos, html, remotas = correio._corpo_legivel(msg)
    checar(texto == "só texto" and html == "" and remotas == 0, "sem HTML, nada muda")


if __name__ == "__main__":
    test_limpeza()
    test_sem_html()
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        sys.exit(1)
    print("  todos os testes passaram")
