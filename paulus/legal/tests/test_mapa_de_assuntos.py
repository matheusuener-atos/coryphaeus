"""
O mapa de assuntos (src/mapa_de_assuntos.py), conferido contra a lei guardada.

  - cada artigo do mapa existe no pacote do instalador, não está revogado e
    diz o trecho que o mapa promete ("15 (quinze) dias") - o que o Planalto
    mudar aparece aqui, e não numa resposta errada;
  - o contexto escolhe a lei: embargos de declaração no CPC, na CLT e nos
    Juizados; contestação no CPC e defesa na audiência trabalhista;
  - pela busca (leis.procurar_assunto), o artigo do mapa vem primeiro e a
    busca por palavra completa.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_mapa_de_assuntos.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tools"))

import mapa_de_assuntos as mapa  # noqa: E402
import medir_leis  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def _plano(texto: str) -> str:
    normal = unicodedata.normalize("NFD", (texto or "").lower())
    return " ".join("".join(c for c in normal if unicodedata.category(c) != "Mn").split())


def test_contra_a_lei(L) -> None:
    print("\ncada artigo do mapa, contra o texto do Planalto")
    erros = []
    for e in mapa.MAPA:
        for codigo, numero, trecho in e.artigos:
            a = L.artigo(codigo, numero)
            if not a:
                erros.append(f"{e.rotulo}: {codigo} art. {numero} não existe")
            elif a["revogado"]:
                erros.append(f"{e.rotulo}: {a['citacao']} está revogado")
            elif _plano(trecho) not in _plano(a["texto"]):
                erros.append(f"{e.rotulo}: {a['citacao']} não diz '{trecho}'")
    total = sum(len(e.artigos) for e in mapa.MAPA)
    checar(not erros, f"os {total} artigos de {len(mapa.MAPA)} assuntos existem, vigentes, e dizem o trecho", erros)


def test_contexto() -> None:
    print("\no contexto escolhe a lei")
    casos = [
        ("qual o prazo dos embargos de declaração?", ("cpc", "1.023")),
        ("qual o prazo dos embargos de declaração na reclamação trabalhista?", ("clt", "897-A")),
        ("qual o prazo dos embargos de declaração no juizado especial?", ("juizados", "49")),
        ("qual o prazo para contestar?", ("cpc", "335")),
        ("qual o prazo da defesa do empregador na reclamação trabalhista?", ("clt", "847")),
        ("qual o prazo para recorrer da sentença do juizado?", ("juizados", "42")),
        ("qual o prazo de prescrição dos créditos trabalhistas?", ("clt", "11")),
        ("qual o prazo de prescrição da indenização por dano moral?", ("cc", "206")),
    ]
    for pergunta, esperado in casos:
        achados = mapa.artigos_do_assunto(pergunta)
        checar(achados and achados[0][:2] == esperado, f"{pergunta!r} -> {esperado[0]} art. {esperado[1]}", achados[:2])
    checar(mapa.artigos_do_assunto("qual o valor do aluguel da sala 402?") == [],
           "pergunta sobre documento não aciona o mapa")
    checar(mapa.artigos_do_assunto("quem é o inventariante?") == [],
           "'inventário' sem prazo não aciona a abertura do inventário")


def test_na_busca(L) -> None:
    print("\npela busca de lei")
    achados = L.procurar_assunto("tenho quantos dias para apelar da sentença?", limite=3)
    checar([a["citacao"] for a in achados[:2]] == ["CPC, art. 1.003", "CPC, art. 1.009"],
           "o mapa vem primeiro", [a["citacao"] for a in achados])
    achados = L.procurar_assunto("o que é o lançamento do crédito tributário?", limite=3)
    checar(achados and all(a["codigo"] == "ctn" for a in achados[:1]),
           "assunto fora do mapa: a busca por palavra, como antes", [a["citacao"] for a in achados])


def main() -> int:
    print("=" * 55)
    print("  o mapa de assuntos")
    print("=" * 55)
    pasta = Path(tempfile.mkdtemp(prefix="paulus-mapa-"))
    try:
        L = medir_leis.montar(pasta)
        test_contra_a_lei(L)
        test_contexto()
        test_na_busca(L)
        L.base.fechar()
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print("   -", f)
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
