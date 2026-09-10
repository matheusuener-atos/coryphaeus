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


def executar(ctx: Contexto, pergunta: str = "", top: int = 6):
    """Gerador de eventos: fontes, depois a resposta pedaco a pedaco."""
    pergunta = (pergunta or "").strip()
    if not pergunta:
        yield evento("vazio", mensagem="Não entendi a pergunta.")
        return

    ctx.antes_de_cada()
    hits = ctx.searcher.search(pergunta, top_k=top)
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

    contexto = ctx.searcher.format_context(hits)
    for pedaco in _pedacos(ctx, pergunta, contexto):
        yield evento("token", t=pedaco)

    yield evento("fim", fontes=fontes, consultados=consultados, ignorados=ignorados)


def _pedacos(ctx: Contexto, pergunta: str, contexto: str):
    """O cliente do assistente entrega por callback; aqui vira iterador."""
    return Ponte(
        lambda empurrar: ctx.client.ask(pergunta, contexto, stream=True, on_token=empurrar)
    )
