"""
Habilidade: responder perguntas sobre os documentos abertos.

Procura os trechos que interessam, entrega ao assistente e devolve a resposta
com as fontes. Declara tambem quais documentos ficaram de fora: silencio ali
faz a pessoa ler "nao ha clausula de penalidade" onde o certo e "nao procurei
nesse documento".
"""

import re

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

# A virada da I7 (`ia.leitura = "trechos"`): ler o escopo inteiro so quando
# ele cabe em ~4000 tokens, ou quando a pergunta pede.
LER_TUDO_ATE = 4000 * CHARS_POR_TOKEN
RE_LER_INTEIRO = re.compile(r"\b(leia|ler|le|lendo|analise|analisar|revise|revisar)\b.{0,30}"
                            r"\b(inteir[oa]|todo|toda|completo|completa|integral)\b"
                            r"|\b(documento|contrato|arquivo|processo) (inteiro|todo|completo)\b")


def _por_trechos(ctx: Contexto, pergunta: str, tamanho: int) -> bool:
    """A leitura vai pelos trechos da busca hibrida, e nao pelo escopo inteiro?"""
    if getattr(ctx, "ia", {}).get("leitura", "tudo") != "trechos" or not getattr(ctx, "recuperar", None):
        return False
    if tamanho <= LER_TUDO_ATE:
        return False
    import unicodedata

    plano = "".join(c for c in unicodedata.normalize("NFD", pergunta.lower()) if unicodedata.category(c) != "Mn")
    return not RE_LER_INTEIRO.search(plano)


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
    # A Biblioteca, M4 (src/biblioteca/camadas.py): com `biblioteca.camadas`,
    # o que ela traz vai em blocos rotulados - LEI, SUMULAS, DOUTRINA,
    # COMUNIDADE, REGRA DA CASA - antes dos documentos, e a camada LEI traz o
    # texto do artigo que a pergunta ou os trechos citam.
    camadas = _camadas(material, pergunta, do_material, orcamento)
    if camadas is not None:
        bloco_material = camadas.texto
        orcamento -= len(bloco_material) + 2
        ctx.registrar("A biblioteca trouxe " + _quantos(len(camadas.trechos), "trecho") + " (" +
                      ", ".join(dict.fromkeys(t.origem for t in camadas.trechos)) + ")")
    elif do_material:
        bloco_material = CABECA_MATERIAL + material.bloco(do_material, orcamento=min(2400, orcamento // 3))
        orcamento -= len(bloco_material) + 2
        ctx.registrar("Achou " + _quantos(len(do_material), "trecho") + " no material de consulta")
    leitura_material = (do_material, bloco_material, camadas)

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
        if pacote.responde_sozinho and not do_material and camadas is None:
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
            if _por_trechos(ctx, pergunta, texto):
                escolhidos = ctx.recuperar(pergunta, quais)
                if escolhidos:
                    ctx.registrar("Li " + _quantos(len(escolhidos), "trecho") + " escolhidos pela busca, "
                                  "e não os documentos inteiros")
                    yield from _responder(ctx, pergunta, escolhidos, orcamento, apenas=quais,
                                          material=leitura_material, caminho="foco", fallback=fallback)
                    return
            if texto > orcamento:
                por_documento = max(2, ctx.searcher.quantos_cabem(orcamento) // len(quais))
                escolhidos = ctx.searcher.search(
                    pergunta, top_k=max(top, len(so_deles)), per_doc_limit=por_documento, documentos=quais)
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
    if _por_trechos(ctx, pergunta, ctx.searcher.caracteres()):
        hits = ctx.recuperar(pergunta, None)
        ctx.registrar("Procurou em " + _quantos(len(ctx.documentos), "documento") +
                      " e leu os " + _quantos(len(hits), "trecho") + " que mais respondem")
    elif ctx.searcher.cabe_inteiro(orcamento):
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

    if not hits and not do_material and camadas is None:
        fora = _fora_da_cobertura(ctx, pergunta, do_material, camadas)
        yield evento("vazio", mensagem="Não achei nada sobre isso nos documentos abertos"
                     + (" nem no material de consulta." if material is not None and material.itens else ".")
                     + ("\n\n" + fora if fora else ""),
                     caminho=caminho)
        return
    if not hits:
        ctx.registrar("Nada nos documentos abertos — respondeu pelo material de consulta")

    yield from _responder(ctx, pergunta, hits, orcamento, material=leitura_material,
                          caminho=caminho, fallback=fallback)


def sem_modelo(ctx: Contexto, pergunta: str = "", apenas=None) -> bool:
    """
    Esta pergunta vai ser respondida sem o modelo?

    Quem pergunta e a conversa, ANTES de entrar na fila do modelo (R4): a
    resposta por molde sai em milissegundos, e esperar a vez de outra pessoa
    por ela seria esperar por nada. As mesmas decisoes de `executar`, na
    mesma ordem - sem anotar medida nenhuma, que a de verdade vem depois.
    """
    pergunta = (pergunta or "").strip()
    if not pergunta:
        return True
    import verificacao

    lidos = [apenas] if isinstance(apenas, str) and apenas else list(apenas or [])
    escopo = [d for d in ctx.documentos if d.name in set(lidos)] if lidos else ctx.documentos
    if verificacao.papel_sem_prova(pergunta, escopo):
        return True
    material = getattr(ctx, "material", None)
    if material is not None and material.consultar(pergunta):
        return False
    # A camada LEI (M4): a pergunta cita um artigo que esta guardado - vai ao modelo, com o texto dele.
    if material is not None and _camadas(material, pergunta, [], 20000) is not None:
        return False
    saber = getattr(ctx, "saber", None)
    if saber is None or not getattr(saber, "ligada", False) or not getattr(ctx, "ia", {}).get("molde", True):
        return False
    from inteligencia import molde, roteador as _roteador

    try:
        metas, nomes = saber.metadados_de(escopo)
        pacote = _roteador.resolver(pergunta, metas, nomes=nomes, em_foco=bool(lidos))
    except Exception:  # noqa: BLE001 - na duvida, a fila de sempre
        return False
    return pacote.responde_sozinho and bool(molde.montar(pacote, pergunta))


def _fora_da_cobertura(ctx: Contexto, pergunta: str, do_material, camadas) -> str:
    """A linha "Não tenho material de <área> na biblioteca..." (M7), ou "" - chave `biblioteca.mapa`."""
    material = getattr(ctx, "material", None)
    if material is None or not getattr(material, "chave", None) or not material.chave("mapa"):
        return ""
    if do_material or camadas is not None:
        return ""  # a biblioteca trouxe algo: a resposta usou a biblioteca
    from biblioteca import mapa

    area = mapa.fora_da_cobertura(pergunta, material, getattr(material, "leis", None))
    if area:
        ctx.registrar(f"a pergunta é de {area}, e a biblioteca não tem nada dessa área")
    return mapa.linha_de_aviso(area) if area else ""


def _camadas(material, pergunta: str, do_material: list, orcamento: int):
    """As camadas da Biblioteca (M4), ou None: chave desligada, ou nada a mostrar."""
    chave = getattr(material, "chave", None)
    if material is None or chave is None or not chave("camadas"):
        return None
    from biblioteca import camadas as camadas_mod

    feitas = camadas_mod.montar(material, getattr(material, "leis", None), pergunta, do_material,
                                total=min(camadas_mod.TOTAL, max(1200, orcamento // 3)))
    return None if feitas.vazia else feitas


def _responder_do_que_ja_se_sabe(ctx: Contexto, pergunta: str, pacote, sinal: dict):
    """
    A resposta de nivel 0: fatos conferidos, sem abrir o documento.

    Pergunta de um dado so sai por molde, sem modelo (src/inteligencia/
    molde.py). O resto vai ao modelo com poucas linhas, terminando em "diga
    ESCALAR se os fatos nao bastarem"; dito isso - ou escrito um numero que
    nao esta nos fatos -, nada e emitido e a pergunta refaz o caminho de
    sempre. Quem perguntou nao percebe, e o programa nao responde pior do
    que responderia antes.
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
    from inteligencia import molde
    from inteligencia import roteador as _roteador

    com_molde = getattr(ctx, "ia", {}).get("molde", True)
    # A lista inteira de uma secao (os pedidos, as decisoes) tambem e molde:
    # "listar exatamente os itens" e o que o modelo fazia, e aqui sai igual,
    # na hora (I9: as perguntas sugeridas respondem sem esperar).
    pronta = (molde.montar(pacote, pergunta) or molde.lista(pacote)) if com_molde else ""
    if pronta:
        ctx.registrar("Respondi pelos fatos já conferidos, sem o modelo: " +
                      _quantos(len(pacote.fatos), "fato") + " em " +
                      _quantos(len(pacote.documentos), "documento"))
        yield from _entregar_nivel0(ctx, pacote, fontes, pronta, caracteres=0, molde_usado=True)
        return

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

    if not resposta or _roteador.pediu_escalar(resposta):
        sinal["escalou"] = True
        return

    # A conferencia mecanica (I3): todo numero, data, CNJ, CPF, CNPJ e valor
    # da resposta tem de estar nos fatos. Um digito trocado derruba a
    # resposta: a lista pronta a substitui quando a pergunta era de lista;
    # sem ela, escala.
    faltam = molde.conferir(resposta, pacote.fatos, pergunta) if com_molde else []
    if faltam:
        substituta = molde.lista(pacote)
        ctx.registrar("a resposta do modelo trazia " + ", ".join(faltam[:3]) +
                      ", que não está nos fatos conferidos — " +
                      ("respondi com a lista deles" if substituta else "descartei e fui ler o documento"))
        if not substituta:
            sinal["escalou"] = True
            return
        resposta = substituta

    yield from _entregar_nivel0(ctx, pacote, fontes, resposta, caracteres=len(prompt),
                                molde_usado=bool(faltam))


def _entregar_nivel0(ctx: Contexto, pacote, fontes: list, resposta: str, *, caracteres: int,
                     molde_usado: bool):
    """Os eventos de uma resposta de nivel 0 - pelo modelo ou pelo molde."""
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
    yield evento("lendo", caracteres=caracteres, trechos=len(fontes),
                 documentos=len(pacote.documentos),
                 janela=getattr(ctx.client, "num_ctx", 0),
                 modelo="" if molde_usado and not caracteres else getattr(ctx.client, "model", ""),
                 previsao={"sabe": False}, nivel=pacote.nivel,
                 caminho="nivel0", fallback=False, molde=molde_usado)
    # Sem stream, os numeros do modelo ficam no cliente. Vao so para a
    # medicao (src/medicao.py), e nao para a tela como "medida": sem stream
    # nao ha tempo de leitura e de escrita separados para mostrar.
    ultima = (getattr(ctx.client, "ultima", None) or {}) if caracteres else {}
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


def _responder(ctx: Contexto, pergunta: str, hits, orcamento: int, apenas=None, material=([], "", None),
               caminho: str = "busca", fallback: bool = False):
    """
    Monta as fontes, entrega ao assistente e devolve a resposta.

    Os dois caminhos - acervo inteiro e documento nomeado - passam por aqui,
    para que a lista de fontes, a conta de caracteres e o aviso de cobertura
    sejam sempre os mesmos.

    `material` e o que veio do material de consulta: os trechos e o bloco ja
    montado, com nome e pagina de cada um.
    """
    do_material, bloco_material, camadas = (tuple(material) + (None,))[:3]
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
            # O trecho estrutural sabe a pagina (I5): a tela diz "pagina 3" em
            # vez de "trecho 3", e a marca [Tn] leva a ela.
            **({"pagina": h.chunk.pagina_inicio, "onde": f"página {h.chunk.pagina_inicio}"}
               if getattr(h.chunk, "pagina_inicio", None) else {}),
        }
        for h in hits
    ]
    for h in ([] if camadas is not None else do_material):
        pagina = ctx.material.pagina(h)
        lugar = ctx.material.onde(h) if hasattr(ctx.material, "onde") else ""
        fontes.append({
            "documento": h.doc_name,
            "trecho": h.chunk.index + 1,
            "score": round(h.score, 2),
            "texto": RE_PAGINA.sub("", h.chunk.text).strip(),
            "material": True,
            "pagina": pagina,
            "onde": lugar or (f"página {pagina}" if pagina else f"trecho {h.chunk.index + 1}"),
        })
    usados_do_material = list(dict.fromkeys(h.doc_name for h in do_material))
    if camadas is not None:
        # M4: as fontes na ordem das camadas, e os documentos depois - e a
        # ordem da numeracao [Tn] que a resposta vai ter.
        for f in fontes:
            f["origem"] = "documento"
        fontes = [dict(t.fonte) for t in camadas.trechos] + fontes
        usados_do_material = list(dict.fromkeys(t.fonte["documento"] for t in camadas.trechos
                                                if not t.fonte.get("lei")))

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

    # I8: as marcas [T1], [T2]... de cada frase (src/citacoes.py). Chave
    # `ia.citacao`: "codigo" poe as marcas depois, em codigo, e o modelo
    # le o de sempre; "modelo" (ou True) numera os trechos e pede as marcas
    # ao modelo - que, medido, derruba o banco de provas com o 3B.
    modo = getattr(ctx, "ia", {}).get("citacao", False)
    modo = "modelo" if modo is True else (modo or "")
    # Com as camadas, as marcas sao sempre postas em codigo, sobre a lista
    # inteira (biblioteca + documentos): pedir ao modelo seria instrucao nova.
    com_marcas = bool(modo and hits) and camadas is None
    regra = ""
    if com_marcas and modo == "modelo":
        import citacoes

        contexto, _ = citacoes.numerar(hits, max_chars=orcamento)
        regra = citacoes.REGRA
    else:
        contexto = ctx.searcher.format_context(hits, max_chars=orcamento) if hits else ""
    if camadas is not None:
        # M4: os documentos primeiro, e as camadas da biblioteca depois deles,
        # na ordem LEI, SUMULAS, DOUTRINA, COMUNIDADE, REGRA DA CASA. O
        # contrato pedia os documentos por ultimo; medido (30/09/2026): com a
        # biblioteca na frente, o comeco do contexto muda a cada pergunta, o
        # Ollama nao reaproveita os ~20 mil caracteres do Acervo ja lidos, e a
        # resposta ia de 10 s para 55 s na mesma pergunta do manual.
        # Só material sem ficha: o contexto de antes das camadas, sem o título.
        titulo = "" if camadas.so_material else "DOCUMENTOS — os documentos do Acervo\n\n"
        contexto = ((titulo + contexto + "\n\n") if contexto else "") + bloco_material
    elif bloco_material:
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
    for tipo, dados in _pedacos(ctx, pergunta, contexto, regra=regra):
        if tipo == "token":
            escrito.append(dados.get("t", ""))
        elif tipo == "truncou":
            ctx.registrar("o texto não coube inteiro na janela do modelo: o começo ficou de fora desta leitura")
        yield evento(tipo, **dados)

    sem_fundamento = False
    if com_marcas and escrito and not (getattr(ctx, "parar", None) and ctx.parar()):
        resposta = "".join(escrito)
        if modo != "modelo":
            import citacoes

            resposta = citacoes.atribuir(resposta, [h.chunk.text for h in hits])
        texto, sem_fundamento = yield from _conferir_marcas(ctx, pergunta, hits, orcamento, resposta, regra)
        escrito = [texto]
    elif camadas is not None and escrito and not (getattr(ctx, "parar", None) and ctx.parar()):
        texto = _conferir_camadas(ctx, "".join(escrito), camadas, hits, modo)
        yield evento("revisao", **texto)
        escrito = [texto["texto"]]

    # Pergunta de consequencia: a frase do documento que decide, literal,
    # quando ela traz o que a resposta deixou de fora (src/verificacao.py).
    import verificacao

    complemento = verificacao.trecho_decisivo(pergunta, "".join(escrito), hits)
    if complemento:
        ctx.registrar("acrescentei a frase do documento que decide a pergunta")
        yield evento("token", t=complemento)

    # M7: a pergunta é de uma área de que a biblioteca não tem nada - a
    # resposta segue, e diz isso no fim. Nunca bloqueia.
    fora = _fora_da_cobertura(ctx, pergunta, do_material, camadas)
    if fora:
        yield evento("token", t="\n\n" + fora)

    if sem_fundamento:
        yield evento("sem_fundamento", documentos=consultados)
    yield evento("fim", fontes=fontes, consultados=consultados, ignorados=ignorados)


def _conferir_camadas(ctx: Contexto, resposta: str, camadas, hits, modo: str) -> dict:
    """
    A resposta com as camadas (M4), conferida em codigo: a marca [Tn] de cada
    frase, na ordem das fontes (biblioteca, depois documentos); a citacao de
    lei que nao esta em trecho nenhum sai; e a frase que diz "a lei diz"
    sustentada so por doutrina ganha o autor na frente. O rotulo "sem fonte"
    so aparece com `ia.citacao` ligada, como sempre.
    """
    import citacoes
    from biblioteca import camadas as camadas_mod

    trechos = list(camadas.trechos) + [camadas_mod.trecho_de_documento(h) for h in hits]
    textos = [t.texto for t in trechos]
    marcada = citacoes.atribuir(resposta, textos)
    rev = citacoes.revisar(marcada, textos)
    texto = rev.texto if modo else rev.texto.replace(" " + citacoes.SEM_FONTE, "")
    texto, corrigidas = camadas_mod.conferir_doutrina(texto, trechos)
    # M6: a obra anterior à redação atual do artigo que ela comenta - só avisa.
    material = getattr(ctx, "material", None)
    if material is not None and material.chave("defasagem"):
        from biblioteca import defasagem

        avisos = defasagem.para_a_resposta(texto, trechos, getattr(material, "leis", None))
        if avisos:
            texto = texto.rstrip() + "\n\n" + avisos
            ctx.registrar("a obra citada é anterior à redação atual do artigo: avisei")
    if rev.removidas:
        ctx.registrar("tirei da resposta o que não está nos trechos lidos: " + "; ".join(rev.removidas[:3]))
    if corrigidas:
        ctx.registrar(_quantos(corrigidas, "frase") + " de doutrina dita como lei: atribuí ao autor")
    return {"texto": texto, "sem_fonte": rev.sem_fonte if modo else 0, "removidas": rev.removidas,
            "marcas": rev.marcas_validas, "doutrina_atribuida": corrigidas}


def _conferir_marcas(ctx: Contexto, pergunta: str, hits, orcamento: int, resposta: str, regra: str):
    """
    As tres conferencias da I8 (src/citacoes.py) sobre a resposta ja escrita.
    Devolve (texto conferido, sem fundamento) e emite `revisao` - a tela troca
    o que mostrou pelo texto conferido.
    """
    import citacoes

    rev = citacoes.revisar(resposta, [h.chunk.text for h in hits])
    if rev.refazer and len(hits) > 1:
        # Regra 2: marca de trecho que nao existe. O modelo pequeno se perde
        # em contexto longo - refaz uma vez, com a metade dos trechos. A
        # numeracao dos que ficam e a mesma: as fontes da tela continuam
        # valendo.
        ctx.registrar("a resposta citou " + ", ".join(f"[T{m}]" for m in rev.marcas_invalidas[:3]) +
                      ", que não existe — refiz com menos trechos")
        yield evento("refazendo", motivo="marca de trecho que não existe")
        menos = hits[:max(1, len(hits) // 2)]
        contexto, _ = citacoes.numerar(menos, max_chars=orcamento)
        try:
            novo = ctx.client.ask(pergunta, contexto, ensinado=_com_regra(ctx, regra),
                                  **_da_conversa(ctx, historico=True)) or ""
        except Exception:  # noqa: BLE001 - sem a segunda leitura, fica a primeira conferida
            novo = ""
        if novo.strip():
            rev = citacoes.revisar(novo, [h.chunk.text for h in menos])
    if rev.removidas:
        ctx.registrar("tirei da resposta o que não está nos trechos lidos: " + "; ".join(rev.removidas[:3]))
    if rev.sem_fonte:
        ctx.registrar(_quantos(rev.sem_fonte, "frase") + " sem trecho que a sustente — marcadas “sem fonte”")
    yield evento("revisao", texto=rev.texto, sem_fonte=rev.sem_fonte, removidas=rev.removidas,
                 marcas=rev.marcas_validas)
    return rev.texto, rev.sem_fundamento


def _com_regra(ctx: Contexto, regra: str) -> str:
    """O que o escritorio ensinou, mais a regra das marcas - as duas vao no fim da instrucao."""
    ensinado = getattr(ctx, "ensinado", "") or ""
    return (ensinado + "\n\n" + regra).strip() if regra else ensinado


def _da_conversa(ctx: Contexto, historico: bool = False) -> dict:
    """
    O teto de resposta da conversa (src/inferencia.py) e, na resposta que le
    documentos, os pares anteriores (src/memoria.py). So vai para o cliente
    que conhece os argumentos: o de mentira dos testes nao precisa conhecer.
    O nivel 0 nao leva historico: ele responde de fatos, e a conversa de
    antes so aumentaria o prompt.
    """
    if not getattr(ctx.client, "aceita_tarefa", False):
        return {}
    extra: dict = {"tarefa": "conversa"}
    if historico and getattr(ctx, "historico", None):
        extra["historico"] = ctx.historico
    return extra


def _quantos(n: int, palavra: str) -> str:
    return f"{n} {palavra if n == 1 else palavra + 's'}"


def _pedacos(ctx: Contexto, pergunta: str, contexto: str, regra: str = ""):
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
            pergunta, contexto, stream=True, ensinado=_com_regra(ctx, regra),
            on_token=lambda t: empurrar(("token", {"t": t})),
            on_fase=lambda fase, dados: empurrar((fase, dados)),
            parar=parar,
            **_da_conversa(ctx, historico=True),
        )

    for item in Ponte(trabalho, parar=parar):
        yield item
