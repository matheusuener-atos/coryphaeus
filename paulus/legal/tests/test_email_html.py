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


def test_envio_formatado() -> None:
    print("\nE-mail escrito com formatação e assinatura com imagem")
    import base64
    import correio_contas

    png = "data:image/png;base64," + base64.b64encode(PNG).decode()
    conta = correio_contas.Conta(id="c1", email="escritorio@exemplo.com.br", nome="Escritório Exemplo")
    conta.assinatura_html = correio.limpar_assinatura(
        f'<p><b>Nome Exemplo</b><br>OAB/UF 00000</p><img src="{png}" width="80"><img src="https://rastreio.test/x.gif">')
    conta.assinatura = correio.html_para_texto(conta.assinatura_html)
    checar("rastreio.test" not in conta.assinatura_html, "imagem de fora não entra na assinatura")
    checar(conta.assinatura.startswith("Nome Exemplo\nOAB/UF 00000"), "a assinatura tem versão em texto", conta.assinatura)

    msg = correio.montar_email(conta, para=["cliente@exemplo.com.br"], assunto="Contrato",
                               corpo="Segue o contrato.", corpo_html='<p>Segue o <b>contrato</b>.</p><script>x()</script>')
    tipos = [p.get_content_type() for p in msg.walk()]
    checar("text/plain" in tipos and "text/html" in tipos, "sai em texto e em HTML", tipos)
    checar("image/png" in tipos, "a imagem da assinatura vai embutida", tipos)
    html = msg.get_body(preferencelist=("html",)).get_content()
    checar("<b>contrato</b>" in html and "<script" not in html, "a formatação vai, o código não")
    checar("cid:" in html and "data:image" not in html, "a imagem vira cid: (o Gmail não mostra data:)")
    texto = msg.get_body(preferencelist=("plain",)).get_content()
    checar("Segue o contrato." in texto and "--\nNome Exemplo" in texto, "o texto puro leva a assinatura", texto)
    previa = correio.html_da_mensagem(msg)
    checar("data:image/png;base64," in previa, "a prévia mostra a imagem de volta")

    grande = "data:image/png;base64," + "A" * 400_000
    try:
        correio.limpar_assinatura(f'<img src="{grande}">')
        checar(False, "recusa imagem grande na assinatura")
    except ValueError:
        checar(True, "recusa imagem grande na assinatura")


if __name__ == "__main__":
    test_limpeza()
    test_sem_html()
    test_envio_formatado()
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        sys.exit(1)
    print("  todos os testes passaram")
