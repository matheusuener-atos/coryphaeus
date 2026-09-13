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


def executar(ctx: Contexto, pergunta: str = "", top: int = 6, apenas=None):
    """
    Gerador de eventos: fontes, depois a resposta pedaco a pedaco.

    `apenas` é a lista de documentos a ler — anexados, nomeados ou em foco.
    Quem resolve os nomes é quem chama; aqui só se obedece, e se declara no
    bastidor que a leitura foi estreitada.

    Lista, e não um nome só, porque anexar dois arquivos e perguntar sobre
    "eles" é o caso comum: quem arrasta um contrato e o aditivo dele quer os
    dois lidos juntos.
    """
    pergunta = (pergunta or "").strip()
    if not pergunta:
        yield evento("vazio", mensagem="Não entendi a pergunta.")
        return

    ctx.antes_de_cada()
    orcamento = orcamento_de_leitura(ctx)

    # A pergunta nomeou um documento: a resposta é sobre ele, e mais ninguém.
    # Lendo os nove, o documento citado virava 937 de 27.213 caracteres -
    # medido - e a resposta saía sobre os outros 96,6%: perguntar sobre um
    # comprovante de viagem devolvia contrato de compra e venda.
    quais = [apenas] if isinstance(apenas, str) and apenas else list(apenas or [])
    if quais:
        so_deles = ctx.searcher.dos_documentos(quais)
        if so_deles:
            ctx.registrar("A pergunta é sobre " + _quantos(len(quais), "documento") +
                          " — leu só " + ("ele" if len(quais) == 1 else "eles"))
            # Cabendo, vai inteiro. Nao cabendo - alguem poe oito arquivos em
            # foco - vale escolher trecho DENTRO deles, e nunca sair deles.
            texto = sum(len(h.chunk.text) for h in so_deles)
            if texto > orcamento:
                por_documento = max(2, ctx.searcher.quantos_cabem(orcamento) // len(quais))
                escolhidos = ctx.searcher.search(
                    pergunta, top_k=max(top, len(so_deles)), per_doc_limit=por_documento)
                dentro = [h for h in escolhidos if h.doc_name in set(quais)]
                so_deles = dentro or so_deles[:1]
            yield from _responder(ctx, pergunta, so_deles, orcamento, apenas=quais)
            return
        # Nomeou documento que nao esta aberto: dizer isso e melhor do que
        # responder pelo acervo como se nada tivesse sido pedido.
        yield evento(
            "vazio",
            mensagem="“" + "”, “".join(quais) + "” não está entre os documentos "
                     "abertos, então não tenho o que ler.",
        )
        return

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

    yield from _responder(ctx, pergunta, hits, orcamento)


def _responder(ctx: Contexto, pergunta: str, hits, orcamento: int, apenas=None):
    """
    Monta as fontes, entrega ao assistente e devolve a resposta.

    Os dois caminhos - acervo inteiro e documento nomeado - passam por aqui,
    para que a lista de fontes, a conta de caracteres e o aviso de cobertura
    sejam sempre os mesmos.
    """
    consultados = list(dict.fromkeys(h.doc_name for h in hits))
    # Com a leitura estreitada os outros nao ficaram "de fora": a pergunta
    # nomeou um arquivo. Listar oito documentos como nao consultados viraria
    # um aviso de cobertura assustando quem fez exatamente o que quis.
    ignorados = ([] if apenas else
                 [d.name for d in ctx.documentos if d.name not in consultados])
    apenas = list(apenas or [])
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
        apenas=apenas,
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
            pergunta, contexto, stream=True, ensinado=getattr(ctx, "ensinado", ""),
            on_token=lambda t: empurrar(("token", {"t": t})),
            on_fase=lambda fase, dados: empurrar((fase, dados)),
        )

    for item in Ponte(trabalho):
        yield item
