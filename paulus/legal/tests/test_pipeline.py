"""
Testes do pipeline de extracao e busca.

Nao dependem do Ollama nem de rede - rodam em segundos.

    python tests/test_pipeline.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from extract import Document, index_all_contracts  # noqa: E402
from search import (  # noqa: E402
    Chunk,
    ContractSearcher,
    chunk_document,
    merge_chunks,
    normalize,
    radical,
    tokenize,
)

SAMPLES = RAIZ / "data" / "samples"
_falhas: list[str] = []


def checar(condicao: bool, descricao: str) -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        _falhas.append(descricao)


# ---------------------------------------------------------------- tokenizacao


def test_normalizacao() -> None:
    print("\ntokenizacao")
    checar(normalize("CLÁUSULA Rescisão") == "clausula rescisao", "remove acento e caixa")
    checar("clausula" in tokenize("CLÁUSULA QUARTA"), "clausula acentuada vira token")
    checar("de" not in tokenize("contrato de locacao"), "stopword 'de' removida")
    checar("90" in tokenize("prazo de 90 dias"), "numero de 2 digitos preservado")
    checar(tokenize("") == [], "texto vazio nao quebra")


# -------------------------------------------------------------------- chunking


def test_plural() -> None:
    """
    Regressao: sem reduzir plural, "clausulas" na pergunta nao casava com
    "CLAUSULA" no contrato e a busca devolvia 1 trecho onde havia 5.
    """
    print("\nplural e singular")
    pares = [
        ("contratos", "contrato"), ("clausulas", "clausula"), ("partes", "parte"),
        ("obrigacoes", "obrigacao"), ("contratuais", "contratual"),
        ("imoveis", "imovel"), ("bens", "bem"), ("penalidades", "penalidade"),
    ]
    for plural, singular in pares:
        checar(radical(plural) == radical(singular), f"{plural} casa com {singular}")

    checar(radical("mes") == "mes", "palavra curta terminada em s fica intacta")
    checar(radical("contrato") == "contrato", "singular nao e alterado")
    checar(tokenize("CLÁUSULAS") == tokenize("cláusula"), "tokenize aplica o radical")


def test_chunking() -> None:
    print("\nchunking")
    texto = "\n\n".join(f"Paragrafo {i}. " + "palavra " * 60 for i in range(10))
    doc = Document(name="x.txt", path="x.txt", text=texto)
    chunks = chunk_document(doc, size=1200, overlap=200)

    checar(len(chunks) > 1, "texto longo gera mais de um trecho")
    checar(all(c.text.strip() for c in chunks), "nenhum trecho vazio")
    checar([c.index for c in chunks] == list(range(len(chunks))), "indices sequenciais")
    checar(max(len(c.text) for c in chunks) <= 1600, "trechos respeitam o tamanho alvo")
    checar("Paragrafo 9" in chunks[-1].text, "fim do documento chega no ultimo trecho")

    # paragrafo unico gigante, sem quebras de linha
    doc_denso = Document(name="y.txt", path="y.txt", text="frase. " * 800)
    checar(len(chunk_document(doc_denso)) > 1, "paragrafo unico gigante e fatiado")

    doc_curto = Document(name="z.txt", path="z.txt", text="Contrato curto.")
    checar(len(chunk_document(doc_curto)) == 1, "documento curto vira um trecho so")


def test_chunk_nao_corta_palavra() -> None:
    """
    Regressao: a sobreposicao cortava numa posicao fixa e o trecho seguinte
    comecava no meio de uma palavra ("fo Unico:" no lugar de "Paragrafo
    Unico:"). Isso aparecia na tela, nos snippets da busca.
    """
    print("\nlimites de palavra nos trechos")

    # Palavras unicas: qualquer corte no meio produz um token inexistente.
    palavras = [f"palavra{i:04d}" for i in range(600)]
    texto = "\n\n".join(" ".join(palavras[i : i + 25]) for i in range(0, 600, 25))
    doc = Document(name="p.txt", path="p.txt", text=texto)
    vocabulario = set(palavras)

    def primeiro_e_ultimo_ok(chunks: list) -> bool:
        for c in chunks:
            tokens = c.text.split()
            if tokens[0] not in vocabulario or tokens[-1] not in vocabulario:
                return False
        return True

    checar(primeiro_e_ultimo_ok(chunk_document(doc)), "paragrafos: nenhum trecho corta palavra")

    # Paragrafo unico gigante, sem quebra de linha: outro caminho no codigo.
    denso = Document(name="d.txt", path="d.txt", text=" ".join(palavras))
    chunks_densos = chunk_document(denso)
    checar(len(chunks_densos) > 1, "paragrafo gigante gera varios trechos")
    checar(primeiro_e_ultimo_ok(chunks_densos), "paragrafo gigante: nenhum trecho corta palavra")


def test_merge() -> None:
    print("\nremontagem de trechos")
    a = Chunk("c.txt", "c.txt", 0, "CLAUSULA 1. Objeto do contrato. TRECHO COMPARTILHADO ENTRE OS DOIS BLOCOS")
    b = Chunk("c.txt", "c.txt", 1, "TRECHO COMPARTILHADO ENTRE OS DOIS BLOCOS CLAUSULA 2. Prazo de vigencia.")
    juntos = merge_chunks([a, b])
    checar(juntos.count("TRECHO COMPARTILHADO") == 1, "sobreposicao de vizinhos removida")
    checar("CLAUSULA 1" in juntos and "CLAUSULA 2" in juntos, "conteudo dos dois trechos preservado")

    distante = Chunk("c.txt", "c.txt", 5, "CLAUSULA 9. Foro.")
    checar("[...]" in merge_chunks([a, distante]), "lacuna entre trechos e sinalizada")
    checar(merge_chunks([]) == "", "lista vazia nao quebra")


# ---------------------------------------------------------------------- busca


def test_busca() -> None:
    print("\nbusca BM25")
    docs = index_all_contracts(SAMPLES, verbose=False)
    checar(len(docs) == 3, f"3 contratos de exemplo extraidos (achou {len(docs)})")
    checar(any(d.name.endswith(".docx") for d in docs), "extrator de DOCX funcionou")
    checar(all(d.chars > 500 for d in docs), "todos os contratos tem texto")

    searcher = ContractSearcher()
    searcher.add_contracts(docs)
    searcher.build()

    hits = searcher.search("aluguel IPTU condominio", top_k=3)
    checar(bool(hits) and "locacao" in hits[0].doc_name, "pergunta sobre aluguel acha o contrato de locacao")

    hits_nda = searcher.search("acordo de confidencialidade due diligence", top_k=3)
    checar(bool(hits_nda) and "nda" in hits_nda[0].doc_name, "pergunta sobre NDA acha o NDA")

    checar(searcher.search("xyzabc123inexistente") == [], "termo inexistente retorna vazio")
    checar(searcher.search("") == [], "busca vazia retorna vazio")

    penalidades = searcher.search("multa penalidade rescisao", top_k=6)
    por_doc: dict[str, int] = {}
    for h in penalidades:
        por_doc[h.doc_name] = por_doc.get(h.doc_name, 0) + 1
    checar(max(por_doc.values()) <= 2, "nenhum contrato ocupa mais que o limite por documento")
    checar(all(h.snippet for h in penalidades), "todo resultado traz um snippet")


def test_busca_poucos_contratos() -> None:
    """
    Regressao: o IDF do BM25 zera (ou fica negativo) para termos presentes em
    metade ou mais dos trechos. Com um ou dois contratos indexados a busca
    devolvia vazio mesmo com o termo presente no texto.
    """
    print("\nbusca com poucos contratos indexados")

    um = Document(
        name="unico.txt",
        path="unico.txt",
        text="CLAUSULA 2. Multa de 15% por descumprimento contratual.",
    )
    searcher = ContractSearcher()
    searcher.add_contracts([um])
    searcher.build()

    hits = searcher.search("descumprimento", top_k=3)
    checar(bool(hits), "termo presente e encontrado com um unico contrato indexado")
    checar(bool(searcher.format_context(hits)), "contexto montado com um unico contrato")
    checar(searcher.search("hipoteca maritima", top_k=3) == [], "termo ausente continua vazio")

    dois = Document(name="outro.txt", path="outro.txt", text="CLAUSULA 1. Prazo de 12 meses.")
    searcher2 = ContractSearcher()
    searcher2.add_contracts([um, dois])
    searcher2.build()
    achados = searcher2.search("descumprimento", top_k=3)
    checar(bool(achados), "termo presente e encontrado com dois contratos indexados")
    checar(achados[0].doc_name == "unico.txt", "acha o contrato certo, nao o outro")


def test_contexto() -> None:
    print("\nmontagem do contexto para o LLM")
    docs = index_all_contracts(SAMPLES, verbose=False)
    searcher = ContractSearcher()
    searcher.add_contracts(docs)
    searcher.build()

    hits = searcher.search("multa penalidade rescisao", top_k=6)
    ctx = searcher.format_context(hits)
    cabecalhos = [l for l in ctx.splitlines() if l.startswith("--- ")]

    checar(len(cabecalhos) == len(set(cabecalhos)), "cada contrato aparece uma unica vez no contexto")
    checar(bool(cabecalhos), "contexto tem cabecalho de origem")
    checar(len(searcher.format_context(hits, max_chars=500)) <= 700, "max_chars limita o contexto")
    checar(searcher.format_context([]) == "", "sem hits, contexto vazio")


# ---------------------------------------------------------------------- cache


def test_cache() -> None:
    print("\ncache de extracao")
    with tempfile.TemporaryDirectory() as tmp:
        pasta = Path(tmp) / "contratos"
        pasta.mkdir()
        (pasta / "a.txt").write_text("CLAUSULA 1. Prazo de 12 meses.", encoding="utf-8")
        cache = Path(tmp) / "index.json"

        primeira = index_all_contracts(pasta, cache, verbose=False)
        checar(len(primeira) == 1 and cache.exists(), "primeira passada extrai e grava cache")

        segunda = index_all_contracts(pasta, cache, verbose=False)
        checar(segunda[0].text == primeira[0].text, "segunda passada reaproveita o cache")

        (pasta / "a.txt").write_text("CLAUSULA 1. Prazo de 24 meses.", encoding="utf-8")
        terceira = index_all_contracts(pasta, cache, verbose=False)
        checar("24 meses" in terceira[0].text, "arquivo alterado e reextraido")

        (pasta / "ignorado.xyz").write_text("nao suportado", encoding="utf-8")
        checar(len(index_all_contracts(pasta, cache, verbose=False)) == 1, "formato nao suportado e ignorado")

    checar(index_all_contracts(Path("pasta/que/nao/existe"), verbose=False) == [], "pasta inexistente retorna vazio")


def test_le_o_acervo_inteiro_quando_cabe() -> None:
    """
    Escolher trecho e o que se faz quando nao da para ler tudo.

    Com seis documentos e vinte e quatro mil caracteres dava, e o programa
    escolhia mesmo assim: lia seis trechos de tres documentos e respondia "nao
    encontrei essa informacao" sobre os outros tres, que nunca abriu. Medido:
    com 6.000 caracteres achou 0 dos 4 outorgados; com o acervo inteiro, os 4.
    """
    print("\nler tudo quando tudo cabe")
    from llama_client import janela_para

    docs = index_all_contracts(SAMPLES, verbose=False)
    searcher = ContractSearcher()
    searcher.add_contracts(docs)
    searcher.build()

    total = searcher.caracteres()
    checar(total > 0, f"o acervo de exemplo tem texto ({total} chars)")

    # A janela acompanha o acervo: fixa e pequena, ela cortava o que o modelo
    # via sem ninguem saber.
    checar(janela_para(total) >= 8192, "a janela nunca fica abaixo do minimo")
    checar(janela_para(500_000) == 32768, "e nao passa do teto, por causa da memoria")
    checar(janela_para(120_000) > janela_para(5_000), "acervo maior pede janela maior")

    folgado = (janela_para(total) - 1200) * 3
    checar(searcher.cabe_inteiro(folgado), "este acervo cabe inteiro na janela dele")

    todos = searcher.tudo()
    checar(len(todos) == len(searcher.chunks), "ler tudo devolve todos os trechos")
    vistos = {h.doc_name for h in todos}
    checar(len(vistos) == len(docs),
           f"e todos os documentos ({len(vistos)} de {len(docs)})")


def test_nenhum_documento_some_do_contexto() -> None:
    """
    Sem espaco para todos, cada um cede - nenhum desaparece calado.

    Enchendo com os primeiros ate estourar, os ultimos nunca chegavam ao
    modelo, que respondia sobre o acervo inteiro tendo visto dois tercos dele.
    """
    print("\nnenhum documento some do contexto")
    docs = index_all_contracts(SAMPLES, verbose=False)
    searcher = ContractSearcher()
    searcher.add_contracts(docs)
    searcher.build()
    todos = searcher.tudo()

    for orcamento in (40000, 8000, 4000, 2000):
        ctx = searcher.format_context(todos, max_chars=orcamento)
        cabecalhos = ctx.count("--- ")
        checar(len(ctx) <= orcamento,
               f"orcamento de {orcamento} e respeitado ({len(ctx)} chars)")
        checar(cabecalhos == len(docs) or "nao coube" in ctx,
               f"com {orcamento}, ou entram os {len(docs)} ou diz quem ficou de fora "
               f"({cabecalhos} entraram)")

    # Orcamento minusculo: quase nada cabe, e e obrigatorio DIZER isso.
    apertado = searcher.format_context(todos, max_chars=300)
    checar(len(apertado) <= 300, f"mesmo apertado, cabe no orcamento ({len(apertado)})")
    if apertado.count("--- ") < len(docs):
        checar("coube" in apertado, "e nomeia os documentos que ficaram de fora")


def test_formulario_sai_na_ordem_de_leitura() -> None:
    """
    Num formulário, o rótulo tem que sair junto do valor.

    O modo padrão do pypdf devolve o texto na ordem em que o PDF desenha, que
    num formulário não é a ordem de leitura. Um comprovante de viagem saía
    assim:

        Nome
        JOSÉ MARCIO CAMPOS TEIXEIRA
        PA - SÃO FÉLIX DO XINGU
        Destino

    O destino aparecendo ANTES do seu rótulo, e "Partida" e "Retorno" soltos
    longe de tudo. Não há como responder "qual o destino?" a partir disso: não
    dá para saber o que é de quem, e o modelo responde pelo que sobra.

    Aqui a checagem é a que importa para a resposta: rótulo e valor na mesma
    linha.
    """
    print("\nformulário sai na ordem de leitura")
    from extract import index_all_contracts

    contratos = RAIZ / "data" / "test_contracts"
    if not contratos.exists():
        print("  pulado: pasta de contratos não existe")
        return

    docs = index_all_contracts(contratos, verbose=False)
    forma = next((d for d in docs if "VIAGEM" in d.name.upper()), None)
    if not forma:
        print("  pulado: o formulário de viagem não está nesta máquina")
        return

    linhas = [" ".join(l.split()) for l in forma.text.splitlines() if l.strip()]
    juntos = [
        ("Destino", "PA - SÃO FÉLIX DO XINGU"),
        ("Nome", "JOSÉ MARCIO CAMPOS TEIXEIRA"),
        ("Motivo", "REUNIÃO DE ENSINAMENTOS"),
        ("Importância entregue", "R$ 200,00"),
    ]
    for rotulo, valor in juntos:
        checar(any(l.startswith(rotulo) and valor in l for l in linhas),
               f"“{rotulo}” sai na mesma linha do valor")

    # Campo em branco continua em branco: o documento não tem essas datas, e
    # inventá-las seria muito pior do que não achá-las.
    partida = [l for l in linhas if l.startswith("Partida")]
    checar(bool(partida) and partida[0].replace("Partida", "").replace("Retorno", "").strip() == "",
           f"campo não preenchido continua vazio ({partida[:1]})")

    # E o documento inteiro continua lá.
    for pedaco in ("000434", "11/09/2026", "03.187.785/0001-41", "CONGREGAÇÃO CRISTÃ"):
        checar(pedaco in forma.text, f"o texto guarda “{pedaco}”")


def test_copias_do_mesmo_arquivo() -> None:
    """
    Dois arquivos iguais byte a byte tem o mesmo sha1 - e o cache e por sha1.

    Este teste existe porque a biblioteca escondia documento. O cache devolvia
    o MESMO objeto para os dois, e o laco mudava o caminho e o nome dele: o
    segundo arquivo sobrescrevia os dados do primeiro, e a lista mostrava a
    copia duas vezes com o original sumido. Num escritorio, "contrato.pdf" e
    "contrato (1).pdf" com o mesmo conteudo sao o caso comum.
    """
    print("\ncopias com o mesmo conteudo")
    with tempfile.TemporaryDirectory() as tmp:
        pasta = Path(tmp) / "contratos"
        pasta.mkdir()
        igual = "CLAUSULA 1. Prazo de 12 meses."
        (pasta / "contrato.txt").write_text(igual, encoding="utf-8")
        cache = Path(tmp) / "index.json"

        index_all_contracts(pasta, cache, verbose=False)     # enche o cache
        (pasta / "contrato (1).txt").write_text(igual, encoding="utf-8")
        docs = index_all_contracts(pasta, cache, verbose=False)

        nomes = sorted(d.name for d in docs)
        checar(len(docs) == 2, f"as duas copias entram no indice (achou {len(docs)})")
        checar(nomes == ["contrato (1).txt", "contrato.txt"],
               f"cada uma com o proprio nome (achou {nomes})")
        caminhos = {d.path for d in docs}
        checar(len(caminhos) == 2, "e com o proprio caminho")
        checar(all(d.text == igual for d in docs), "o texto e o mesmo nos dois")
        checar(len({id(d) for d in docs}) == 2,
               "e nao sao o mesmo objeto - mexer num nao pode mexer no outro")


def main() -> int:
    print("=" * 55)
    print("  PAULUS Legal - testes do pipeline (sem LLM)")
    print("=" * 55)

    if not SAMPLES.exists():
        print(f"\nERRO: pasta de exemplos nao encontrada: {SAMPLES}")
        return 1

    test_normalizacao()
    test_plural()
    test_chunking()
    test_chunk_nao_corta_palavra()
    test_merge()
    test_busca()
    test_busca_poucos_contratos()
    test_contexto()
    test_cache()
    test_le_o_acervo_inteiro_quando_cabe()
    test_nenhum_documento_some_do_contexto()
    test_formulario_sai_na_ordem_de_leitura()
    test_copias_do_mesmo_arquivo()

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
