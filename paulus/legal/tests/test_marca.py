"""
A foto de quem usa e a logo do escritorio.

Sao duas imagens que a pessoa escolhe no computador e que passam a aparecer
em toda parte: a foto no avatar, a logo no alto do papel timbrado. Por isso
o que se testa aqui e o caminho todo - o arquivo que chega vira PNG pequeno,
o lixo e recusado com uma frase em portugues, e o timbre com logo abre mais
espaco no alto da folha do que o timbre so de texto.

Rodar: venv\\Scripts\\python.exe tests\\test_marca.py
"""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import documento  # noqa: E402
import marca as marca_mod  # noqa: E402

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {str(detalhe)[:300]}")
        _falhas.append(descricao)


def imagem_de_teste(largura: int, altura: int, formato: str = "PNG", cor=(200, 30, 30, 255)) -> bytes:
    from PIL import Image

    modo = "RGBA" if formato == "PNG" else "RGB"
    img = Image.new(modo, (largura, altura), cor[: 4 if modo == "RGBA" else 3])
    saco = io.BytesIO()
    img.save(saco, format=formato)
    return saco.getvalue()


def test_guardar() -> None:
    """O arquivo escolhido vira um PNG pequeno; o resto e recusado com motivo."""
    print("\nguardar a imagem")
    from PIL import Image

    with tempfile.TemporaryDirectory() as tmp:
        m = marca_mod.Marca(Path(tmp))
        checar(m.caminho("foto") is None and m.info()["foto"]["tem"] is False,
               "sem foto, a tela sabe que nao tem")

        # Uma foto 3x4 de celular: sai quadrada, porque o avatar e redondo.
        item = m.guardar("foto", imagem_de_teste(1200, 1600, "JPEG"))
        alvo = m.caminho("foto")
        checar(alvo is not None and alvo.name == "foto.png", "a foto virou PNG em data/marca")
        with Image.open(alvo) as img:
            checar(img.size == (512, 512), f"cortada no centro e reduzida a 512 ({img.size})")
            checar(img.format == "PNG", "gravada como PNG")
        checar(item["tem"] and item["versao"] > 0 and item["kb"] >= 0, "a tela recebe tamanho e versao", item)

        # A logo mantem a proporcao: ela vai para o alto da folha.
        m.guardar("logo", imagem_de_teste(2000, 500))
        with Image.open(m.caminho("logo")) as img:
            checar(img.size == (1024, 256), f"a logo cabe em 1024 sem deformar ({img.size})")
            checar(img.mode == "RGBA", "e mantem a transparencia")

        for dados, pedaco in (
            (b"isto nao e uma imagem, e um texto", "nao e uma imagem"),
            (b"", "vazio"),
            # PNG que comeca certo e acaba no meio: pode dar "nao e imagem" ou
            # "nao consegui ler", conforme onde o Pillow desiste.
            (b"\x89PNG\r\n\x1a\n" + b"\x00" * 40, "imagem"),
        ):
            try:
                m.guardar("foto", dados)
                checar(False, f"recusa o arquivo que nao serve ({pedaco})")
            except ValueError as exc:
                checar(pedaco in str(exc).lower(), f"recusa dizendo o motivo: {exc}", str(exc))

        try:
            m.guardar("foto", b"x" * (marca_mod.MAX_BYTES + 1))
            checar(False, "recusa acima de 4 MB")
        except ValueError as exc:
            checar("4 MB" in str(exc), f"acima de 4 MB, diz o tamanho e o limite: {exc}")

        try:
            m.guardar("bandeira", imagem_de_teste(10, 10))
            checar(False, "so existem foto e logo")
        except ValueError:
            checar(True, "so existem foto e logo")

        # Trocar a foto troca a versao: e ela que faz a tela buscar de novo.
        antes = m.info()["foto"]["versao"]
        import os
        import time

        time.sleep(1.1)
        m.guardar("foto", imagem_de_teste(64, 64))
        checar(m.info()["foto"]["versao"] != antes, "trocar a foto muda a versao")
        checar(not list(Path(tmp).glob("*.novo")), "nao sobra arquivo provisorio",
               os.listdir(tmp))

        checar(m.tirar("foto") and m.caminho("foto") is None, "remover volta para as iniciais")
        checar(m.tirar("foto") is False, "remover de novo nao quebra")


def test_timbre_com_logo() -> None:
    """A logo entra no alto do papel e empurra o texto para baixo."""
    print("\no timbre do PDF")
    blocos = documento.ler_html("<p>Primeiro paragrafo do documento.</p>")
    timbre = {"nome": "Maria Vasconcelos", "oab": "GO 12345",
              "endereco": "Rua 7, 100", "telefone": "(62) 90000-0000"}

    so_texto = documento._altura_do_timbre(timbre)
    with tempfile.TemporaryDirectory() as tmp:
        m = marca_mod.Marca(Path(tmp))
        m.guardar("logo", imagem_de_teste(600, 200))
        com_logo = dict(timbre, logo=str(m.caminho("logo")))

        alto = documento._altura_do_timbre(com_logo)
        checar(alto > so_texto, f"com logo, o alto da folha abre mais espaco ({so_texto:.0f} -> {alto:.0f} pt)")

        pdf = documento.para_pdf(blocos, "Teste", timbre=com_logo)
        checar(pdf.startswith(b"%PDF") and len(pdf) > len(documento.para_pdf(blocos, "Teste", timbre=timbre)),
               "o PDF sai com a imagem dentro")

        # Sem nome nao ha timbre - e uma logo sozinha nao inventa um.
        checar(documento._altura_do_timbre({"logo": str(m.caminho("logo"))}) == 0,
               "logo sem nome nao vira timbre")

        # A logo pode ter sido apagada por fora depois de gravada. O PDF tem de
        # sair assim mesmo: um documento sem logo vale mais que um erro.
        sumida = dict(timbre, logo=str(Path(tmp) / "nao-existe.png"))
        checar(documento._altura_do_timbre(sumida) == so_texto, "logo que sumiu volta ao timbre de texto")
        checar(documento.para_pdf(blocos, "Teste", timbre=sumida).startswith(b"%PDF"),
               "e o PDF sai mesmo assim")


def main() -> int:
    print("=" * 55)
    print("  PAULUS - a foto e a logo")
    print("=" * 55)
    test_guardar()
    test_timbre_com_logo()

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
