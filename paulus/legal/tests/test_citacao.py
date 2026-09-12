"""
Testes de "mostrar o trecho citado dentro do documento".

A conversa sempre disse de onde tirou cada informação — mas dizia em texto, e
conferir de verdade exigia abrir o PDF por fora, achar a página e procurar o
parágrafo com o olho. Este módulo fecha essa distância, e por isso o que ele
não pode fazer é marcar o lugar errado: um destaque no parágrafo errado é pior
que destaque nenhum, porque a pessoa confere e acredita.

Os testes cobrem:

  - todo trecho que o assistente leu de um PDF é localizado nele
  - a marca cai na página certa, em coordenadas que acompanham o zoom
  - trecho que não está no arquivo devolve "não achei", não um palpite
  - DOCX e TXT dizem que não têm página, em vez de fingir uma
  - "por que este trecho" conta palavras da pergunta, não inventa explicação

    python tests/test_citacao.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import citacao  # noqa: E402
from extract import index_all_contracts  # noqa: E402
from search import ContractSearcher  # noqa: E402

CONTRATOS = RAIZ / "data" / "test_contracts"
SAMPLES = RAIZ / "data" / "samples"

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {detalhe}")
        _falhas.append(descricao)


def _acervo(pasta: Path):
    docs = index_all_contracts(pasta, verbose=False)
    s = ContractSearcher()
    s.add_contracts(docs)
    s.build()
    return docs, s


def test_acha_todo_trecho_que_leu() -> None:
    """
    O que o assistente citou tem que ser localizável no arquivo.

    Com um pedaço só de agulha, 12 de 14 trechos eram achados — as duas falhas
    eram descasamento bobo entre o texto extraído e o texto interno do PDF (um
    espaço antes da vírgula, uma linha de assinatura em underscores). Por isso
    a busca tenta vários pontos do trecho: basta um casar.
    """
    print("\ntodo trecho citado é localizado no PDF")
    pasta = CONTRATOS if CONTRATOS.exists() else SAMPLES
    docs, s = _acervo(pasta)

    pdfs = [d for d in docs if d.path.lower().endswith(".pdf")]
    if not pdfs:
        print("  pulado: nenhum PDF na pasta de exemplos")
        return

    nomes = {d.name for d in pdfs}
    trechos = [c for c in s.chunks if c.doc_name in nomes]
    achados = []
    for c in trechos:
        doc = next(d for d in docs if d.name == c.doc_name)
        achados.append(citacao.onde_esta(doc.path, c.text))

    quantos = sum(1 for r in achados if r["achou"])
    checar(quantos == len(trechos),
           f"os {len(trechos)} trechos de PDF foram localizados (achou {quantos})",
           ", ".join(c.doc_name[:24] for c, r in zip(trechos, achados) if not r["achou"]))

    # A página tem que existir de verdade no arquivo.
    fora = [r for r in achados if r["achou"] and not (1 <= r["pagina"] <= r["total"])]
    checar(not fora, "e a página está dentro do documento", str(fora[:2]))


def test_a_marca_cai_dentro_da_pagina() -> None:
    """
    Coordenada em fração da página, e não em pixel.

    A imagem muda de tamanho com o zoom e com a janela. Em pixel, a marca sairia
    do lugar em toda mudança; em fração, ela acompanha sem recalcular nada.
    """
    print("\na marca cai dentro da página")
    pasta = CONTRATOS if CONTRATOS.exists() else SAMPLES
    docs, s = _acervo(pasta)
    pdfs = {d.name: d for d in docs if d.path.lower().endswith(".pdf")}
    if not pdfs:
        print("  pulado: nenhum PDF")
        return

    marcas = []
    for c in s.chunks:
        if c.doc_name not in pdfs:
            continue
        r = citacao.onde_esta(pdfs[c.doc_name].path, c.text)
        if r["achou"]:
            marcas += r["marcas"]

    checar(bool(marcas), f"há marcas para desenhar ({len(marcas)})")
    dentro = all(0 <= m["x"] <= 1 and 0 <= m["y"] <= 1 and
                 m["x"] + m["w"] <= 1.001 and m["y"] + m["h"] <= 1.001
                 for m in marcas)
    checar(dentro, "toda marca cabe dentro da página, em fração de 0 a 1")
    checar(all(m["w"] > 0 and m["h"] > 0 for m in marcas), "e nenhuma tem tamanho zero")

    # O eixo do PDF conta do rodapé para cima; o da tela, do topo para baixo.
    # Sem virar, tudo cairia espelhado — e a metade de cima ficaria vazia.
    altos = [m for m in marcas if m["y"] < 0.5]
    checar(bool(altos), "há marcas na metade de cima da página (o eixo foi virado)")


def test_o_que_nao_esta_la_nao_e_marcado() -> None:
    """Marcar o lugar errado é pior que não marcar."""
    print("\no que não está no arquivo não é marcado")
    pasta = CONTRATOS if CONTRATOS.exists() else SAMPLES
    docs, _ = _acervo(pasta)
    pdf = next((d for d in docs if d.path.lower().endswith(".pdf")), None)
    if not pdf:
        print("  pulado: nenhum PDF")
        return

    r = citacao.onde_esta(pdf.path, "cláusula de confidencialidade zumbi quântica")
    checar(r["achou"] is False, "trecho inventado não é localizado")
    checar(r["marcas"] == [], "e não devolve marca nenhuma")
    checar(r["total"] > 0, "mas ainda diz quantas páginas o documento tem")

    vazio = citacao.onde_esta(pdf.path, "")
    checar(vazio["achou"] is False, "trecho vazio não quebra")
    checar(citacao.onde_esta(Path("nao/existe.pdf"), "qualquer")["achou"] is False,
           "arquivo inexistente não quebra")


def test_so_pdf_tem_pagina() -> None:
    print("\nsó PDF tem página para desenhar")
    pasta = CONTRATOS if CONTRATOS.exists() else SAMPLES
    docs, _ = _acervo(pasta)

    pdf = next((d for d in docs if d.path.lower().endswith(".pdf")), None)
    outro = next((d for d in docs if not d.path.lower().endswith(".pdf")), None)

    if pdf:
        checar(citacao.paginas_de(pdf.path) > 0, "PDF tem páginas contadas")
    if outro:
        checar(citacao.paginas_de(outro.path) == 0,
               f"{Path(outro.path).suffix} devolve zero em vez de fingir uma página")
        checar(citacao.onde_esta(outro.path, "qualquer trecho")["achou"] is False,
               "e não tenta localizar trecho nele")


def test_por_que_este_trecho() -> None:
    """
    A explicação é contável: as palavras da pergunta que estão ali.

    Um resumo escrito por modelo seria mais uma frase para conferir. Quem abre
    o documento quer saber o que ligou a pergunta ao trecho — e isso se conta.
    """
    print("\npor que este trecho")
    trecho = ("9ª CLÁUSULA - Para dirimir quaisquer dúvidas, controvérsias ou "
              "litígios oriundos deste contrato, as partes elegem o foro da "
              "Comarca de São Félix do Xingu, Estado do Pará.")

    r = citacao.por_que_este_trecho("Qual o foro eleito neste contrato?", trecho)
    checar("foro" in r["termos"], f"acha a palavra que importa ({r['termos']})")
    checar("contrato" in r["termos"], "e as outras que aparecem")
    checar(r["quantos"] <= r["de"], "nunca conta mais palavras do que a pergunta tem")

    # Palavra que aparece em qualquer texto não explica nada.
    comuns = citacao.por_que_este_trecho("o que que tem sobre isso", trecho)
    checar(comuns["termos"] == [], f"palavra comum não vira explicação ({comuns['termos']})")

    nada = citacao.por_que_este_trecho("quanto custa o aluguel do imóvel", trecho)
    checar(nada["termos"] == [], "sem nada em comum, não inventa ligação")

    # Plural na pergunta, singular no texto: é a mesma palavra.
    plural = citacao.por_que_este_trecho("quais os contratos?", trecho)
    checar("contratos" in plural["termos"], f"plural casa com singular ({plural['termos']})")


def test_varias_agulhas() -> None:
    print("\na busca tenta vários pedaços do trecho")
    longo = "palavra " * 60
    agulhas = citacao.frases_de_busca(longo)
    checar(len(agulhas) >= 2, f"trecho longo vira várias agulhas ({len(agulhas)})")
    checar(all(len(a) >= 20 for a in agulhas), "nenhuma curta demais para procurar")
    checar(len(set(agulhas)) == len(agulhas), "e nenhuma repetida")

    curto = citacao.frases_de_busca("um trecho curto")
    checar(curto == ["um trecho curto"], f"trecho curto vira ele mesmo ({curto})")
    checar(citacao.frases_de_busca("") == [], "texto vazio não vira agulha")
    checar(citacao.frases_de_busca("   ") == [], "só espaço também não")

    # A marca de página que a extração escreve não pode ir para a busca: ela
    # não existe dentro do PDF.
    com_marca = citacao.frases_de_busca("[pagina 4] " + longo)
    checar(all("pagina 4" not in a for a in com_marca), "a marca de página sai da agulha")

    # A agulha não atravessa quebra de linha.
    #
    # O texto extraído respeita a ordem de leitura da página, e duas linhas
    # vizinhas na folha podem estar longe uma da outra no fluxo interno do
    # PDF. Num formulário isso é a regra: "11/09/2026" e "Despesas de Viagem"
    # ficam lado a lado no cabeçalho e viravam a agulha "11/09/2026 Despesas
    # de Viagem" — uma sequência que não existe no arquivo. O trecho ficava
    # sem marca nenhuma no visor.
    formulario = ("Importância entregue R$ 200,00\n"
                  "Partida Retorno\n"
                  "Motivo REUNIÃO DE ENSINAMENTOS P/ PORTEIROS\n"
                  "Destino PA - SÃO FÉLIX DO XINGU")
    agulhas = citacao.frases_de_busca(formulario)
    checar(bool(agulhas), f"o formulário vira agulha ({len(agulhas)})")
    checar(all("\n" not in a for a in agulhas), "nenhuma agulha tem quebra de linha")
    linhas = {l.strip() for l in formulario.splitlines()}
    atravessa = [a for a in agulhas
                 if not any(a in l for l in linhas)]
    checar(not atravessa,
           "e toda agulha cabe dentro de UMA linha do trecho", str(atravessa[:2]))

    # Trecho curto de formulário: nenhuma linha chega a vinte letras, e ele
    # ficava sem agulha nenhuma — sem agulha, sem marca.
    curto = "11/09/2026\n                    Despesas de Viagem"
    checar(bool(citacao.frases_de_busca(curto)),
           f"trecho curto de duas linhas ainda vira agulha ({citacao.frases_de_busca(curto)})")


def main() -> int:
    print("=" * 55)
    print("PAULUS - o trecho citado dentro do documento")
    print("=" * 55)

    test_varias_agulhas()
    test_por_que_este_trecho()
    test_acha_todo_trecho_que_leu()
    test_a_marca_cai_dentro_da_pagina()
    test_o_que_nao_esta_la_nao_e_marcado()
    test_so_pdf_tem_pagina()

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
