"""
A recuperacao hibrida: lexico + denso, fundidos por RRF, e o orcamento do
que vai para o modelo (I7).

Cada busca erra de um jeito. A lexica (FTS5) acha "clausula 9" e erra
"quanto custa sair antes?"; a densa acha o assunto e erra o numero exato. A
fusao por posicao (Reciprocal Rank Fusion, k=60) junta as duas sem precisar
que os escores delas sejam comparaveis: um trecho que aparece bem nas duas
listas sobe; um que so aparece mal numa delas fica para tras.

Depois da fusao, o orcamento - o que de fato vai para o modelo de 3B:

- no maximo 6 trechos e 3000 tokens de contexto: com o acervo inteiro na
  janela o modelo le devagar e divaga (medido: ~32 mil tokens antes da
  primeira palavra);
- no maximo 3 trechos por documento: a pergunta que compara dois contratos
  precisa dos dois;
- trecho quase igual a outro ja escolhido (cosseno >= 0,92) nao entra: e o
  mesmo texto duas vezes, ocupando o lugar de outro;
- trecho fraco nao entra para "completar": o que nao ficou entre os 20
  primeiros de nenhuma das duas listas fica de fora, mesmo sobrando espaco.
"""

from __future__ import annotations

K_RRF = 60
LEXICO_TOP = 50
DENSO_TOP = 50
FUNDIDOS_TOP = 20
TOP = 6
TOKENS = 3000
POR_DOCUMENTO = 3
DUPLICADO = 0.92
CHARS_POR_TOKEN = 3


def rrf(listas: list[list[str]], k: int = K_RRF) -> list[tuple[str, float]]:
    """A fusao: soma de 1/(k + posicao) em cada lista. Empate desempata pelo id."""
    pontos: dict[str, float] = {}
    for lista in listas:
        for posicao, cid in enumerate(lista, start=1):
            pontos[cid] = pontos.get(cid, 0.0) + 1.0 / (k + posicao)
    return sorted(pontos.items(), key=lambda par: (-par[1], par[0]))


def minimo_rrf(k: int = K_RRF, fundo: int = FUNDIDOS_TOP) -> float:
    """O escore de quem ficou na posicao `fundo` de uma lista so: abaixo disso e fraco."""
    return 1.0 / (k + fundo)


def listas(searcher, pergunta: str, *, denso=None, vetorizador=None, documentos=None) -> tuple[list[str], list[str]]:
    """As duas listas de ids, cada uma com os 50 melhores - para medir cada uma sozinha."""
    lexico = []
    if getattr(searcher, "lexico", None) is not None and searcher._usa_lexico():
        if not searcher._pronto:
            searcher.build()
        lexico = [cid for cid, _ in searcher.lexico.buscar(pergunta, LEXICO_TOP, documentos)]
    else:
        lexico = [h.chunk.chunk_id for h in searcher.search(pergunta, top_k=LEXICO_TOP, per_doc_limit=LEXICO_TOP,
                                                              documentos=documentos) if h.chunk.chunk_id]
    densa: list[str] = []
    if denso is not None and vetorizador is not None:
        try:
            vetor = vetorizador.vetores([pergunta])[0]
            densa = [cid for cid, _ in denso.buscar(vetor, DENSO_TOP, documentos)]
        except Exception:  # noqa: BLE001 - sem o modelo de vetores, fica a lexica
            densa = []
    return lexico, densa


def recuperar(searcher, pergunta: str, *, denso=None, vetorizador=None, documentos=None,
              top: int = TOP, tokens: int = TOKENS, por_documento: int = POR_DOCUMENTO,
              reranquear=None) -> list:
    """
    Os trechos que vao para o modelo, em ordem de relevancia, ja dentro do
    orcamento. Devolve `Hit`s do buscador.
    """
    from search import Hit, _extract_snippet, tokenize

    lexico, densa = listas(searcher, pergunta, denso=denso, vetorizador=vetorizador, documentos=documentos)
    fundidos = [(cid, p) for cid, p in rrf([lexico, densa]) if p >= minimo_rrf()][:FUNDIDOS_TOP]
    por_id = {c.chunk_id: c for c in searcher.chunks if c.chunk_id}
    candidatos = [(por_id[cid], p) for cid, p in fundidos if cid in por_id]
    if reranquear is not None and candidatos:
        candidatos = reranquear(pergunta, candidatos)

    termos = tokenize(pergunta)
    escolhidos: list = []
    vetores: list = []
    usados = 0
    contagem: dict[str, int] = {}
    for chunk, ponto in candidatos:
        if len(escolhidos) >= top:
            break
        if contagem.get(chunk.doc_name, 0) >= por_documento:
            continue
        custo = len(chunk.text) // CHARS_POR_TOKEN
        if escolhidos and usados + custo > tokens:
            continue
        vetor = denso.vetor_de(chunk.chunk_id) if denso is not None else None
        if vetor is not None and any(float(vetor @ outro) >= DUPLICADO for outro in vetores):
            continue
        escolhidos.append(Hit(chunk, float(ponto), _extract_snippet(chunk.text, termos)))
        if vetor is not None:
            vetores.append(vetor)
        usados += custo
        contagem[chunk.doc_name] = contagem.get(chunk.doc_name, 0) + 1
    return escolhidos
