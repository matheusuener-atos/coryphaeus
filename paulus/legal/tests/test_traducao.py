"""
O tradutor desta maquina (src/traducao.py): o HTML volta com as mesmas tags,
os numeros sobrevivem e as pontas do trecho continuam as do original.

Precisa dos pacotes em data/modelos/traducao (python src/traducao.py baixar);
sem eles, so as regras que nao dependem do modelo rodam.

Rodar: venv\\Scripts\\python.exe tests\\test_traducao.py
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import traducao  # noqa: E402

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {str(detalhe)[:300]}")
        _falhas.append(descricao)


def test_regras() -> None:
    print("\nRegras sem o modelo")
    checar(traducao.adivinhar_lingua("Here is your code. Please do not share it with anyone, we will never ask for it.") == "en", "reconhece inglês")
    checar(traducao.adivinhar_lingua("Hola, gracias por su correo. Le enviamos la factura con los datos del pedido.") == "es", "reconhece espanhol")
    checar(traducao.adivinhar_lingua("Olá, segue o contrato para você conferir. Qualquer dúvida é só falar com a gente.") == "", "português não pede tradução")
    checar(traducao._acertar_pontas(": ChatGPT Web", "ChatGPT Web.") == ": ChatGPT Web", "devolve a pontuação das pontas")
    checar(traducao._acertar_pontas("review your security", "Revise a sua segurança.") == "revise a sua segurança", "trecho do meio da frase fica minúsculo e sem ponto")


HTML = ('<html><head><style>.t{color:#222}</style></head><body><table><tr><td class="t">'
        '<p>Hi,</p><p>We detected a new login to your account.</p>'
        '<p><b>Application</b>: ChatGPT Web</p>'
        '<p>If you do not recognize this activity, <a href="https://exemplo.com/seguranca">review your account security</a> immediately.</p>'
        '<p>Here is your code: 94411675</p></td></tr></table></body></html>')


def test_html() -> None:
    print("\nHTML traduzido no lugar")
    if not traducao.disponivel("en"):
        print("  (pulado: pacote en->pt não instalado)")
        return
    inicio = time.time()
    saida = traducao.traduzir_html(HTML, "en")
    gasto = time.time() - inicio
    tags = lambda h: re.findall(r"<[^>]+>", h)  # noqa: E731
    checar(tags(saida) == tags(HTML), "as tags voltam iguais, na mesma ordem")
    checar("94411675" in saida, "o código continua o mesmo")
    checar(".t{color:#222}" in saida, "o CSS não é traduzido")
    checar("Hi," not in saida and "account" not in saida, "o texto vira português", saida)
    checar("</b>: " in saida, "a pontuação entre as tags fica", saida)
    checar(gasto < 15, f"é rápido ({gasto:.1f}s)")


if __name__ == "__main__":
    test_regras()
    test_html()
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        sys.exit(1)
    print("  todos os testes passaram")
