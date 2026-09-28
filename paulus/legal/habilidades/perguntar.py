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
from material import RE_PAGINA

# O material entra depois dos documentos, com o aviso do que ele e. O aviso vai
# aqui, e nao no prompt de sistema: pergunta sem material nao muda em nada.
CABECA_MATERIAL = (
    "MATERIAL DE CONSULTA DO ESCRITÓRIO — referência que o escritório entregou "
    "(manual, tabela, doutrina, norma); não é documento de cliente. Ao usar, cite "
    "o material e a página.\n\n"
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

    # "Quem é o advogado da X?" quando nenhum documento liga advogado a X: a
    # resposta sai por regra, sem modelo - o 3B juntava a X com a advogada da
    # outra parte (src/verificacao.py).
    import verificacao

    lidos = [apenas] if isinstance(apenas, str) and apenas else list(apenas or [])
    escopo_do_papel = [d for d in ctx.documentos if d.name in set(lidos)] if lidos else ctx.documentos
    pronta = verificacao.papel_sem_prova(pergunta, escopo_do_papel)
    if pronta:
        ctx.registrar("nenhum documento liga advogado a essa parte - respondi sem o modelo")
        yield evento("vazio", mensagem=pronta, caminho="regra")
        return

    # O material de consulta (src/material.py): manual, tabela, doutrina que
    # o escritorio entregou para o PAULUS aprender. Os trechos que tem a ver
    # com a pergunta entram junto com os documentos, com espaco reservado -
    # sem reserva, o acervo lido por inteiro ocupava a janela toda.
    material = getattr(ctx, "material", None)
    do_material = material.consultar(pergunta) if material is not None else []
    bloco_material = ""
    if do_material:
        bloco_material = CABECA_MATERIAL + material.bloco(do_material, orcamento=min(2400, orcamento // 3))
        orcamento -= len(bloco_material) + 2
        ctx.registrar("Achou " + _quantos(len(do_material), "trecho") + " no material de consulta")
    leitura_material = (do_material, bloco_material)

    # HOOK 2: o que ja foi lido uma vez responde de novo sem ler outra vez.
    # Nao respondendo - metadata que falta, dado nao conferido, pergunta que
    # pede leitura, ou resposta ambigua -, o caminho e o de sempre, daqui para
    # baixo, sem que nada mude. Com material na pergunta, os fatos guardados
    # nao bastam: eles sao so dos documentos.
    quais_em_foco = [apenas] if isinstance(apenas, str) and apenas else list(apenas or [])
    # O nivel 0 tentou e desistiu: a medicao (src/medicao.py) separa essas
    # perguntas, que pagaram duas vezes.
    fallback = False
    saber = getattr(ctx, "saber", None)
    if saber is not None:
        escopo = ([d for d in ctx.documentos if d.name in set(quais_em_foco)]
                  if quais_em_foco else ctx.documentos)
        pacote = saber.montar_contexto(pergunta, escopo, em_foco=bool(quais_em_foco))
        if pacote.responde_sozinho and not do_material:
            sinal = {"escalou": False}
            yield from _responder_do_que_ja_se_sabe(ctx, pergunta, pacote, sinal)
            if not sinal["escalou"]:
                return
            fallback = True
            ctx.registrar("os fatos guardados não bastaram — refiz pelo caminho de sempre")
        elif pacote.estreita:
            # Niveis 3 e 4: a camada nao tem a resposta, mas sabe em quais
            # documentos ela esta. Dali para baixo nada muda - e o buscador de
            # sempre, com os trechos de sempre, so que dentro de um pedaco do
            # acervo em vez do acervo inteiro.
            conhecidos = {d.name for d in ctx.documentos}
            recorte = [n for n in pacote.restringe if n in conhecidos]
            if recorte:
                apenas = quais_em_foco = recorte
                ctx.registrar("Procurei só em " + _quantos(len(recorte), "documento") +
                              ": " + pacote.porque)

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
            yield from _responder(ctx, pergunta, so_deles, orcamento, apenas=quais, material=leitura_material,
                                  caminho="foco", fallback=fallback)
            return
        # Nomeou documento que nao esta aberto: dizer isso e melhor do que
        # responder pelo acervo como se nada tivesse sido pedido.
        yield evento(
            "vazio",
            mensagem="“" + "”, “".join(quais) + "” não está entre os documentos "
                     "abertos, então não tenho o que ler.",
            caminho="foco",
        )
        return

    # Escolher trecho é o que se faz quando não dá para ler tudo. Com seis
    # documentos e vinte e quatro mil caracteres dava, e o programa escolhia
    # mesmo assim: lia três de seis e respondia "não encontrei essa
    # informação" sobre um documento que nunca abriu.
    caminho = "busca"
    if ctx.searcher.cabe_inteiro(orcamento):
        caminho = "tudo"
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

    if not hits and not do_material:
        yield evento("vazio", mensagem="Não achei nada sobre isso nos documentos abertos"
                     + (" nem no material de consulta." if material is not None and material.itens else "."),
                     caminho=caminho)
        return
    if not hits:
        ctx.registrar("Nada nos documentos abertos — respondeu pelo material de consulta")

    yield from _responder(ctx, pergunta, hits, orcamento, material=leitura_material,
                          caminho=caminho, fallback=fallback)


def _responder_do_que_ja_se_sabe(ctx: Contexto, pergunta: str, pacote, sinal: dict):
    """
    A resposta de nivel 0: fatos conferidos, sem abrir o documento.

    O prompt sai com poucas linhas e termina mandando o modelo dizer ESCALAR
    se os fatos nao bastarem. Dito isso, nada e emitido como resposta e a
    pergunta refaz o caminho de sempre - quem perguntou nao percebe, e o
    programa nao responde pior do que responderia antes.
    """
    fontes = [
        {
            "documento": f.documento,
            "trecho": i,
            "onde": (f"página {f.pagina}" if f.pagina else "no documento"),
            "score": 1.0,
            "texto": f.quote or f.valor,
            "pagina": f.pagina,
        }
        for i, f in enumerate(pacote.fatos, start=1)
    ]
    prompt = pacote.prompt(pergunta)
    ctx.registrar("Respondi pelo que já tinha lido: " +
                  _quantos(len(pacote.fatos), "fato") + " conferido em " +
                  _quantos(len(pacote.documentos), "documento"))

    try:
        resposta = (ctx.client.ask(prompt, "", sistema=SISTEMA_DOS_FATOS,
                                   ensinado=getattr(ctx, "ensinado", ""), **_da_conversa(ctx)) or "").strip()
    except Exception:
        # Modelo fora do ar no meio do caminho rapido: o caminho de sempre
        # tambem precisa dele, mas quem decide isso e o fluxo de fora.
        sinal["escalou"] = True
        return

    from inteligencia import roteador as _roteador

    if not resposta or _roteador.pediu_escalar(resposta):
        sinal["escalou"] = True
        return

    yield evento(
        "fontes",
        consultados=pacote.documentos,
        ignorados=[],
        total_contratos=len(ctx.documentos),
        trechos=fontes,
        apenas=pacote.documentos,
        nivel=pacote.nivel,
        inferencia=pacote.inferencia,
        porque=pacote.porque,
    )
    yield evento("lendo", caracteres=len(prompt), trechos=len(fontes),
                 documentos=len(pacote.documentos),
                 janela=getattr(ctx.client, "num_ctx", 0),
                 modelo=getattr(ctx.client, "model", ""),
                 previsao={"sabe": False}, nivel=pacote.nivel,
                 caminho="nivel0", fallback=False)
    # Sem stream, os numeros do modelo ficam no cliente. Vao so para a
    # medicao (src/medicao.py), e nao para a tela como "medida": sem stream
    # nao ha tempo de leitura e de escrita separados para mostrar.
    ultima = getattr(ctx.client, "ultima", None) or {}
    if ultima:
        yield evento("contagem", tokens_lidos=ultima.get("prompt_eval_count", 0),
                     tokens_escritos=ultima.get("eval_count", 0), num_ctx=ultima.get("num_ctx", 0),
                     truncou=bool(ultima.get("truncou")))
    yield evento("token", t=resposta)
    yield evento("fim", fontes=fontes, consultados=pacote.documentos, ignorados=[],
                 nivel=pacote.nivel)


# O nivel 0 nao esta lendo documento: esta lendo fatos ja conferidos. A
# instrucao de sempre manda citar o arquivo de onde saiu cada informacao, o
# que aqui faria o modelo inventar nome de arquivo - as fontes ja vao na
# lista, e sao as de verdade.
SISTEMA_DOS_FATOS = (
    "Voce e o PAULUS, assistente do escritorio. Responde em portugues do Brasil, "
    "direto e sem preambulo.\n\n"
    "Abaixo estao FATOS ja conferidos no documento, com a pagina de cada um. "
    "Responda usando exclusivamente esses fatos. Nao invente, nao complete, nao "
    "acrescente clausula, valor, data ou nome que nao esteja ali.\n\n"
    "Se os fatos nao bastarem para responder a pergunta, responda exatamente: ESCALAR"
)


def _responder(ctx: Contexto, pergunta: str, hits, orcamento: int, apenas=None, material=([], ""),
               caminho: str = "busca", fallback: bool = False):
    """
    Monta as fontes, entrega ao assistente e devolve a resposta.

    Os dois caminhos - acervo inteiro e documento nomeado - passam por aqui,
    para que a lista de fontes, a conta de caracteres e o aviso de cobertura
    sejam sempre os mesmos.

    `material` e o que veio do material de consulta: os trechos e o bloco ja
    montado, com nome e pagina de cada um.
    """
    do_material, bloco_material = material
    consultados = list(dict.fromkeys(h.doc_name for h in hits))
    # Com a leitura estreitada os outros nao ficaram "de fora": a pergunta
    # nomeou um arquivo. Listar oito documentos como nao consultados viraria
    # um aviso de cobertura assustando quem fez exatamente o que quis. Sem
    # trecho nenhum do acervo (respondeu pelo material), tambem nao: a busca
    # passou por eles e nao achou nada.
    ignorados = ([] if apenas or not hits else
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
    for h in do_material:
        pagina = ctx.material.pagina(h)
        fontes.append({
            "documento": h.doc_name,
            "trecho": h.chunk.index + 1,
            "score": round(h.score, 2),
            "texto": RE_PAGINA.sub("", h.chunk.text).strip(),
            "material": True,
            "pagina": pagina,
            "onde": f"página {pagina}" if pagina else f"trecho {h.chunk.index + 1}",
        })
    usados_do_material = list(dict.fromkeys(h.doc_name for h in do_material))

    ctx.registrar(_quantos(len(hits), "trecho") + " de " +
                  _quantos(len(consultados), "documento") +
                  (" e " + _quantos(len(do_material), "trecho") + " do material de consulta" if do_material else ""))
    yield evento(
        "fontes",
        consultados=consultados,
        ignorados=ignorados,
        total_contratos=len(ctx.documentos),
        trechos=fontes,
        apenas=apenas,
        material=usados_do_material,
    )

    contexto = ctx.searcher.format_context(hits, max_chars=orcamento) if hits else ""
    if bloco_material:
        contexto = (contexto + "\n\n" if contexto else "") + bloco_material

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
        caminho=caminho,
        fallback=fallback,
    )

    escrito = []
    for tipo, dados in _pedacos(ctx, pergunta, contexto):
        if tipo == "token":
            escrito.append(dados.get("t", ""))
        elif tipo == "truncou":
            ctx.registrar("o texto não coube inteiro na janela do modelo: o começo ficou de fora desta leitura")
        yield evento(tipo, **dados)

    # Pergunta de consequencia: a frase do documento que decide, literal,
    # quando ela traz o que a resposta deixou de fora (src/verificacao.py).
    import verificacao

    complemento = verificacao.trecho_decisivo(pergunta, "".join(escrito), hits)
    if complemento:
        ctx.registrar("acrescentei a frase do documento que decide a pergunta")
        yield evento("token", t=complemento)

    yield evento("fim", fontes=fontes, consultados=consultados, ignorados=ignorados)


def _da_conversa(ctx: Contexto) -> dict:
    """
    O teto de resposta da conversa (src/inferencia.py). So vai para o cliente
    que conhece o argumento: o de mentira dos testes nao precisa conhecer.
    """
    return {"tarefa": "conversa"} if getattr(ctx.client, "aceita_tarefa", False) else {}


def _quantos(n: int, palavra: str) -> str:
    return f"{n} {palavra if n == 1 else palavra + 's'}"


def _pedacos(ctx: Contexto, pergunta: str, contexto: str):
    """
    O cliente entrega por callback; aqui vira iterador de eventos.

    Alem dos tokens, passam as viradas de fase: a hora em que a leitura acabou
    e a primeira palavra saiu, e os numeros que o Ollama devolve no fim -
    tokens lidos e escritos, contados por ele, nao estimados por mim.
    """
    # O botao de parar da tela chega aqui como `ctx.parar`: o cliente do modelo
    # fecha a conexao e a ponte deixa de esperar.
    parar = getattr(ctx, "parar", None)

    def trabalho(empurrar):
        return ctx.client.ask(
            pergunta, contexto, stream=True, ensinado=getattr(ctx, "ensinado", ""),
            on_token=lambda t: empurrar(("token", {"t": t})),
            on_fase=lambda fase, dados: empurrar((fase, dados)),
            parar=parar,
            **_da_conversa(ctx),
        )

    for item in Ponte(trabalho, parar=parar):
        yield item
