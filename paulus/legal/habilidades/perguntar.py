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
        ctx.registrar("Leu " + _quantos(len(ctx.documentos), "documento") + " por inteiro")
    else:
        # Não cabendo tudo, cabe mais do que seis trechos: o quanto couber.
        # E dois trechos por documento com um orçamento grande deixava
        # documento de fora à toa.
        cabem = ctx.searcher.quantos_cabem(orcamento)
        por_documento = max(2, cabem // max(1, len(ctx.documentos)))
        hits = ctx.searcher.search(pergunta, top_k=max(top, cabem),
                                   per_doc_limit=por_documento)
        ctx.registrar("Procurou em " + _quantos(len(ctx.documentos), "documento"))

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

    ctx.registrar(_quantos(len(hits), "trecho") + " de " +
                  _quantos(len(consultados), "documento"))
    yield evento(
        "fontes",
        consultados=consultados,
        ignorados=ignorados,
        total_contratos=len(ctx.documentos),
        trechos=fontes,
    )

    contexto = ctx.searcher.format_context(hits, max_chars=orcamento)

    # O que vai acontecer, dito antes de acontecer. Ler o prompt inteiro e o
    # silencio longo: o Ollama nao emite nada ate a primeira palavra, entao a
    # tela mostra O QUE esta sendo lido e quanto leituras deste tamanho
    # levaram NESTA maquina - quando ja houve alguma para medir.
    previsao = {"sabe": False}
    if getattr(ctx, "ritmo", None):
        previsao = ctx.ritmo.previsao_de_leitura(ctx.client.model, len(contexto))

    yield evento(
        "lendo",
        caracteres=len(contexto),
        trechos=len(hits),
        documentos=len(consultados),
        janela=getattr(ctx.client, "num_ctx", 0),
        modelo=getattr(ctx.client, "model", ""),
        previsao=previsao,
    )

    for tipo, dados in _pedacos(ctx, pergunta, contexto):
        yield evento(tipo, **dados)

    yield evento("fim", fontes=fontes, consultados=consultados, ignorados=ignorados)


def _quantos(n: int, palavra: str) -> str:
    return f"{n} {palavra if n == 1 else palavra + 's'}"


def _pedacos(ctx: Contexto, pergunta: str, contexto: str):
    """
    O cliente entrega por callback; aqui vira iterador de eventos.

    Alem dos tokens, passam as viradas de fase: a hora em que a leitura acabou
    e a primeira palavra saiu, e os numeros que o Ollama devolve no fim -
    tokens lidos e escritos, contados por ele, nao estimados por mim.
    """
    def trabalho(empurrar):
        return ctx.client.ask(
            pergunta, contexto, stream=True,
            on_token=lambda t: empurrar(("token", {"t": t})),
            on_fase=lambda fase, dados: empurrar((fase, dados)),
        )

    for item in Ponte(trabalho):
        yield item
