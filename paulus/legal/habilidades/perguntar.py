"""
Habilidade: responder perguntas sobre os documentos abertos.

Procura os trechos que interessam, entrega ao assistente e devolve a resposta
com as fontes. Declara tambem quais documentos ficaram de fora: silencio ali
faz a pessoa ler "nao ha clausula de penalidade" onde o certo e "nao procurei
nesse documento".
"""

from habilidade_base import (
    PRECISA_ASSISTENTE,
    PRECISA_DOCUMENTOS,
    Contexto,
    Habilidade,
    Ponte,
    evento,
)

HABILIDADE = Habilidade(
    id="perguntar",
    nome="Perguntar sobre os documentos",
    resumo="Responde com base no que está escrito, citando o trecho de origem",
    grupo="Documentos",
    acao="conversa",
    precisa=[PRECISA_DOCUMENTOS, PRECISA_ASSISTENTE],
    detalhe=(
        "Toda resposta vem com os trechos que o assistente leu, para você conferir, "
        "e diz quais documentos não entraram na busca."
    ),
    demora="cerca de 20 s por pergunta",
    ordem=10,
)


# Português com acento dá perto de três caracteres por token neste modelo:
# 21.382 caracteres do acervo viraram 6.983 tokens de entrada, medido.
CHARS_POR_TOKEN = 3

# O que não é documento e ocupa a janela do mesmo jeito: a instrução, a
# pergunta e a resposta que ainda vai ser escrita.
TOKENS_RESERVADOS = 1200


def orcamento_de_leitura(ctx: Contexto) -> int:
    """
    Quantos caracteres de documento cabem numa leitura, nesta máquina.

    Sai da janela do modelo, e não de um número fixo: `num_ctx` é quem manda.
    """
    janela = getattr(ctx.client, "num_ctx", 0) or 8192
    return max(4000, (janela - TOKENS_RESERVADOS) * CHARS_POR_TOKEN)


def executar(ctx: Contexto, pergunta: str = "", top: int = 6):
    """Gerador de eventos: fontes, depois a resposta pedaco a pedaco."""
    pergunta = (pergunta or "").strip()
    if not pergunta:
        yield evento("vazio", mensagem="Não entendi a pergunta.")
        return

    ctx.antes_de_cada()
    orcamento = orcamento_de_leitura(ctx)

    # Escolher trecho é o que se faz quando não dá para ler tudo. Com seis
    # documentos e vinte e quatro mil caracteres dava, e o programa escolhia
    # mesmo assim: lia três de seis e respondia "não encontrei essa
    # informação" sobre um documento que nunca abriu.
    if ctx.searcher.cabe_inteiro(orcamento):
        hits = ctx.searcher.tudo()
        ctx.registrar(f"Leu os {len(ctx.documentos)} documento(s) inteiros")
    else:
        # Não cabendo tudo, cabe mais do que seis trechos: o quanto couber.
        # E dois trechos por documento com um orçamento grande deixava
        # documento de fora à toa.
        cabem = ctx.searcher.quantos_cabem(orcamento)
        por_documento = max(2, cabem // max(1, len(ctx.documentos)))
        hits = ctx.searcher.search(pergunta, top_k=max(top, cabem),
                                   per_doc_limit=por_documento)
        ctx.registrar(f"Procurou em {len(ctx.documentos)} documento(s)")

    if not hits:
        yield evento("vazio", mensagem="Não achei nada sobre isso nos documentos abertos.")
        return

    consultados = list(dict.fromkeys(h.doc_name for h in hits))
    ignorados = [d.name for d in ctx.documentos if d.name not in consultados]
    fontes = [
        {
            "documento": h.doc_name,
            "trecho": h.chunk.index + 1,
            "score": round(h.score, 2),
            "texto": h.chunk.text,
        }
        for h in hits
    ]

    ctx.registrar(f"Leu {len(hits)} trecho(s) de {len(consultados)} documento(s)")
    yield evento(
        "fontes",
        consultados=consultados,
        ignorados=ignorados,
        total_contratos=len(ctx.documentos),
        trechos=fontes,
    )

    contexto = ctx.searcher.format_context(hits, max_chars=orcamento)
    for pedaco in _pedacos(ctx, pergunta, contexto):
        yield evento("token", t=pedaco)

    yield evento("fim", fontes=fontes, consultados=consultados, ignorados=ignorados)


def _pedacos(ctx: Contexto, pergunta: str, contexto: str):
    """O cliente do assistente entrega por callback; aqui vira iterador."""
    return Ponte(
        lambda empurrar: ctx.client.ask(pergunta, contexto, stream=True, on_token=empurrar)
    )
