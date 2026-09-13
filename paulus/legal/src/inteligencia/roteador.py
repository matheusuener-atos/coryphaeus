"""
Quanto custa responder esta pergunta.

Este e o coracao da otimizacao, e ele e feito de uma decisao repetida: dado o
que ja se sabe do documento, qual e o MENOR caminho que responde com
seguranca? A escala vai de "consultar tres linhas de metadata" a "ler o
documento inteiro":

    nivel 0   metadata          ~0 tokens de documento   milissegundos
    nivel 1   metadata + resumo ~300 tokens
    nivel 2   o buscador de hoje                          <- comportamento atual
    nivel 3   buscador + metadata como filtro
    nivel 4   varios documentos escolhidos pelo metadata
    nivel 5   documento inteiro                           <- so a pedido

As regras que impedem a otimizacao de virar erro, em ordem de importancia:

**Ausencia no metadata nunca e resposta negativa.** Se o campo nao esta la, o
documento pode conte-lo assim mesmo - o que faltou foi a analise, nao o dado.
Entao escala. Esta e a regra que mais protege: sem ela, a camada responderia
"nao ha valor da causa" sobre uma peca que tem valor da causa na primeira
linha.

**Nivel 0 exige tres coisas ao mesmo tempo**: o campo existe, esta conferido,
e a correspondencia e unica. Duas pecas com valores diferentes nao viram uma
resposta escolhida por sorteio.

**Duvida escala.** O roteador prefere gastar tokens a errar. Quando o
classificador nao tem certeza do que foi perguntado, a pergunta vai para o
caminho de hoje.

**A escalada tambem acontece depois.** O prompt do nivel 0 manda o modelo
responder exatamente ESCALAR quando os fatos nao bastarem - e ai a pergunta
refaz o caminho normal, sem que quem perguntou perceba. E o mecanismo mais
simples e mais confiavel de nao-regressao que existe aqui.
"""

from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass, field

from .esquema import Item, Metadata

# ------------------------------------------------------------------ niveis

METADATA = 0
METADATA_E_RESUMO = 1
BUSCADOR = 2            # o que o programa ja fazia antes desta camada
BUSCADOR_FILTRADO = 3
VARIOS_DOCUMENTOS = 4
DOCUMENTO_INTEIRO = 5


def _quantos(n: int, palavra: str) -> str:
    return f"{n} {palavra if n == 1 else palavra + 's'}"


def _plano(texto: str) -> str:
    normal = unicodedata.normalize("NFD", (texto or "").lower())
    return " ".join("".join(c for c in normal if unicodedata.category(c) != "Mn").split())


# As perguntas factuais em portugues juridico, por regra. Camada zero do
# classificador: e instantanea, repetivel e cobre a maior parte do que se
# pergunta mil vezes sobre o mesmo documento.
INTENCOES: list[tuple[str, str, str]] = [
    # (secao, chave desejada, padrao)
    ("case", "case_number",
     r"\b(numero do processo|n[º°o]? do processo|processo n[º°o]|numero dos autos|autos n)"),
    ("amounts", "claim",
     r"\b(valor da causa|valor atribuido a causa|quanto vale a causa)"),
    ("amounts", "fee",
     r"\b(valor dos honorarios|quanto (sao|e|ficou) os honorarios|honorarios (contratados|combinados|s[ãa]o de))"),
    ("amounts", "",
     r"\b(qual (o|e o) valor|quanto (custa|vale|foi pago|ficou)|valor do contrato|valor total)"),
    ("dates", "signature",
     r"\b(quando (o |a )?(contrato|documento|acordo|instrumento)?\s*(foi )?(assinad|celebrad|firmad)"
     r"|data (da|de) assinatura)"),
    ("dates", "deadline",
     r"\b(qual (o|e o) prazo|quando vence|data de vencimento|ate quando)"),
    ("dates", "",
     r"\b(quando|em que data|qual a data)\b"),
    ("legal_references", "",
     r"\b((quais|que) (artigos?|leis?|s[uú]mulas?|dispositivos?|normas?)"
     r"|artigos? (citad|mencionad)|base legal|fundamento legal)"),
    ("parties", "",
     r"\b(quem (e|sao|foi) (o|a|os|as) (autor|autora|reu|re|requerente|requerid|exequente|executad|"
     r"contratante|contratad|parte)|quais (as )?partes|quem (assinou|contratou)|nome (do|da) (autor|reu|cliente))"),
    ("jurisdiction", "court",
     r"\b(qual (o|e o) (tribunal|comarca|vara|foro|juizo)|em que (vara|comarca|tribunal))"),
    ("classification", "document_type",
     r"\b(que (tipo de )?documento e (este|esse)|qual (o|e o) tipo (deste|desse) documento)"),
]

# As perguntas cuja resposta e uma LISTA do que o documento diz - a porta das
# colecoes de extensao (spec, passo 7). Elas sao diferentes das de cima: nao
# pedem um dado, pedem tudo o que consta de um tipo.
#
# O que as torna respondiveis sem ler o documento e que a lista ja e a
# resposta: os pedidos de uma peca sao as frases em que ela pede, e elas estao
# guardadas com a citacao e a pagina. O que as torna perigosas e o mesmo: uma
# lista de tres quando havia cinco tem cara de completa. As travas de
# `_pela_lista` existem por isso.
ENUMERACOES: list[tuple[str, str, str]] = [
    ("requests", "",
     r"\b((quais|que) (sao )?(os |as )?(pedidos|requerimentos)"
     r"|qual (o|e o) pedido|o que (o autor|a autora|o reu|a re|a parte|a peca|a inicial|ele|ela)"
     r"\s*(requer|pede|pleiteia|postula|pediu|requereu)"
     r"|o que (foi|esta sendo|se) (requerid|pedid|pleitead))"),
    ("events", "",
     r"\b(linha do tempo|cronologia|hist[oó]rico (do|desse|deste|da)"
     r"|o que (ja )?aconteceu|andamento (do|desse|deste)"
     r"|(quais|que) (as |os )?(datas|prazos) (importantes|relevantes|do processo))"),
    ("decisions", "",
     r"\b(qual (foi )?(a|o) (decisao|sentenca|dispositivo|resultado|desfecho)"
     r"|o que (o juiz|a juiza|o tribunal|a corte|o relator|a decisao|a sentenca)"
     r"\s*(decidiu|julgou|determinou|deferiu|indeferiu|diz)"
     r"|o que foi (decidido|julgado|determinado|deferido)"
     r"|foi (deferid|indeferid|julgad|acolhid|negad|homologad|procedente|improcedente)"
     r"|(deu|nao deu) (certo|ganho)|ganhou ou perdeu|qual (o|e o) resultado)"),
]

# Pergunta com recorte nao e pergunta de lista: "o que a contestacao alega
# SOBRE A PRESCRICAO" pede leitura daquele ponto, e a lista inteira nao
# responde. Havendo recorte, a pergunta segue o caminho de hoje.
RE_QUALIFICA = re.compile(
    r"\b(sobre|a respeito|quanto (a|ao)|em rela[cç][aã]o|referente|acerca|"
    r"por que|porque|como |onde |em que ponto)\b")

# Perguntas que NAO sao factuais mesmo contendo as palavras acima: elas pedem
# leitura, e leitura e o caminho de hoje. "O que a contestacao alega sobre a
# prescricao?" tem "o que" e nao tem resposta em tres linhas de metadata.
PEDE_LEITURA = re.compile(
    r"\b(alega|argumenta|sustenta|fundamenta|explica|resume|resumo|analis|compar|"
    r"por que|porque|como|discorre|entende|conclui|clausula que|onde diz|"
    r"contradiz|diverg|interpreta)\b")

RE_INTENCOES = [(secao, chave, re.compile(padrao)) for secao, chave, padrao in INTENCOES]
RE_ENUMERACOES = [(secao, chave, re.compile(padrao)) for secao, chave, padrao in ENUMERACOES]

# "Do que se trata este documento?" tem resposta guardada: o resumo escrito na
# ingestao. Ela e a unica coisa nesta camada que NAO e fato - e conclusao do
# modelo sobre o texto -, e por isso sai rotulada como leitura do assistente.
RE_RESUMO = re.compile(
    r"\b(do que (se )?trata|sobre o que (e|é)|resum[ae]|resumo (deste|desse|do)|"
    r"me (diga|fale) sobre (este|esse) documento|qual (o|e o) (assunto|objeto) (deste|desse|do))")


@dataclass
class Intencao:
    """O que a pergunta parece pedir - e com quanta certeza."""

    secao: str = ""
    chave: str = ""
    nivel: int = BUSCADOR
    porque: str = ""
    # A resposta e a lista inteira de uma secao, e nao um campo dela.
    enumera: bool = False

    @property
    def factual(self) -> bool:
        return self.nivel == METADATA and bool(self.secao)

    @property
    def resolvivel(self) -> bool:
        """Da para tentar responder sem abrir o documento?"""
        return self.nivel <= METADATA_E_RESUMO and bool(self.secao)


def classificar(pergunta: str) -> Intencao:
    """
    Que tipo de pergunta e esta - por regra, e sem modelo.

    Reconhecer "quem e o autor" nao exige inteligencia nenhuma: exige uma
    lista. Perguntar a um modelo de tres bilhoes de parametros o que a pessoa
    quis dizer custaria um minuto e erraria de formas imprevisiveis, e o
    modelo continua sendo para o que e de verdade ambiguo.
    """
    plano = _plano(pergunta)
    if not plano:
        return Intencao(porque="pergunta vazia")
    if RE_RESUMO.search(plano):
        return Intencao(secao="summary", nivel=METADATA_E_RESUMO,
                        porque="pergunta pelo assunto do documento")

    # As perguntas de lista vem antes de `PEDE_LEITURA` porque as duas usam as
    # mesmas palavras: "o que o autor alega" e lista, "o que o autor alega
    # sobre a prescricao" e leitura. O recorte e o que separa - e na duvida
    # manda o recorte, que e o caminho de hoje.
    if not RE_QUALIFICA.search(plano):
        for secao, chave, padrao in RE_ENUMERACOES:
            if padrao.search(plano):
                return Intencao(secao=secao, chave=chave, nivel=METADATA, enumera=True,
                                porque=f"pergunta pela lista de {secao}")

    if PEDE_LEITURA.search(plano):
        return Intencao(porque="a pergunta pede leitura, nao um dado")

    for secao, chave, padrao in RE_INTENCOES:
        if padrao.search(plano):
            return Intencao(secao=secao, chave=chave, nivel=METADATA,
                            porque=f"pergunta factual sobre {secao}")
    return Intencao(porque="não reconheci um pedido de dado")


# ------------------------------------------------------------------ pacote


@dataclass
class Fato:
    """Um fato pronto para entrar na resposta, com de onde ele veio."""

    documento: str = ""
    document_id: str = ""
    version_id: str = ""
    secao: str = ""
    rotulo: str = ""
    valor: str = ""
    quote: str = ""
    pagina: int | None = None
    char_start: int | None = None
    char_end: int | None = None

    def to_dict(self) -> dict:
        return {"documento": self.documento, "secao": self.secao, "rotulo": self.rotulo,
                "valor": self.valor, "quote": self.quote, "pagina": self.pagina,
                "char_start": self.char_start, "char_end": self.char_end,
                "document_id": self.document_id, "version_id": self.version_id}

    def linha(self) -> str:
        onde = f"  [p.{self.pagina}]" if self.pagina else ""
        rotulo = f" ({self.rotulo})" if self.rotulo else ""
        return f"- {SECOES_BR.get(self.secao, self.secao)}{rotulo}: {self.valor}{onde}"


@dataclass
class Pacote:
    """
    O que o roteador decidiu, e o que ele entrega para responder.

    `fallback` ligado quer dizer: a camada nao teve o que oferecer, siga o
    caminho de hoje. Todo campo existe para poder ser medido depois - sem
    medicao, o retrofit e fe.
    """

    nivel: int = BUSCADOR
    fatos: list[Fato] = field(default_factory=list)
    documentos: list[str] = field(default_factory=list)
    fallback: bool = True
    porque: str = ""
    intencao: Intencao = field(default_factory=Intencao)
    # Ligado quando o que vai na resposta e conclusao do modelo (o resumo), e
    # nao trecho conferido. A tela tem de dizer isso a quem le.
    inferencia: bool = False
    # Ligado quando a resposta e a lista inteira de uma secao - pedidos,
    # decisoes, provas. Muda o prompt: listar nao e responder.
    enumera: bool = False
    # Nivel 3 e 4: a camada nao respondeu, mas sabe em QUAIS documentos esta a
    # resposta. O buscador de hoje roda igual - so que dentro destes.
    restringe: list[str] = field(default_factory=list)
    ms: int = 0
    trace: dict = field(default_factory=dict)

    @property
    def responde_sozinho(self) -> bool:
        return self.nivel <= METADATA_E_RESUMO and bool(self.fatos)

    @property
    def estreita(self) -> bool:
        """A camada nao respondeu, mas diz onde procurar."""
        return bool(self.restringe) and not self.responde_sozinho

    def prompt(self, pergunta: str) -> str:
        """
        O prompt do nivel 0: fatos, nao prosa.

        A ultima linha e o mecanismo de nao-regressao: o modelo que nao
        conseguir responder com estes fatos diz ESCALAR, e a pergunta refaz o
        caminho de sempre.
        """
        if self.inferencia:
            return "\n".join([
                f"RESUMO JÁ ESCRITO DE {', '.join(self.documentos)} (leitura do assistente, "
                "não é trecho do documento):",
                self.fatos[0].valor if self.fatos else "",
                "",
                "Responda em uma frase, usando exclusivamente o resumo acima.",
                "Se ele não bastar para responder, responda exatamente: ESCALAR",
                "",
                f"Pergunta: {pergunta}",
            ])
        if self.enumera:
            cabecalho = CABECALHOS.get(self.intencao.secao, "O QUE CONSTA DO DOCUMENTO")
            linhas = [f"{cabecalho} ({', '.join(self.documentos)}):"]
            linhas += [fato.linha() for fato in self.fatos]
            linhas += [
                "",
                "Responda listando exatamente os itens acima, com as palavras deles.",
                "Não acrescente, não junte e não resuma itens.",
                "Se a pergunta pedir algo que não esteja nesta lista, responda "
                "exatamente: ESCALAR",
                "",
                f"Pergunta: {pergunta}",
            ]
            return "\n".join(linhas)
        linhas = [f"FATOS VERIFICADOS ({', '.join(self.documentos)}):"]
        linhas += [fato.linha() for fato in self.fatos]
        linhas += [
            "",
            "Responda em uma frase, usando exclusivamente os fatos acima.",
            "Não acrescente nada que não esteja neles.",
            "Se os fatos não bastarem para responder, responda exatamente: ESCALAR",
            "",
            f"Pergunta: {pergunta}",
        ]
        return "\n".join(linhas)

    def resumo_para_tela(self) -> dict:
        return {"nivel": self.nivel, "porque": self.porque, "fallback": self.fallback,
                "fatos": [f.to_dict() for f in self.fatos], "documentos": self.documentos,
                "restringe": self.restringe, "inferencia": self.inferencia,
                "enumera": self.enumera, "ms": self.ms, "trace": self.trace}


ROTULOS = {
    "signature": "assinatura", "filing": "protocolo", "publication": "publicação",
    "hearing": "audiência", "deadline": "prazo", "decision": "decisão", "term": "vigência",
    "claim": "valor da causa", "fee": "honorários", "contract": "valor do contrato",
    "penalty": "multa", "rent": "aluguel", "damages": "indenização", "debt": "dívida",
    "installment": "parcela", "article": "artigo", "law": "lei", "precedent": "súmula",
    # ------------------------------------------- colecoes de extensao
    "injunction": "tutela", "citation": "citação", "condemnation": "condenação",
    "merits": "mérito", "evidence_production": "prova", "free_justice": "gratuidade",
    "fees": "honorários", "procedural": "processual", "other": "",
    "granted": "deferido", "denied": "indeferido", "partial": "parcial",
    "merits_granted": "procedente", "merits_denied": "improcedente",
    "homologated": "homologado", "extinguished": "extinto",
    "conviction": "condenação", "acquittal": "absolvição", "order": "determinação",
}

# Como cada secao se chama na frase que vai para o modelo. O JSON fala ingles
# porque e formato; o prompt fala portugues porque e leitura.
SECOES_BR = {
    "case": "processo", "amounts": "valor", "dates": "data",
    "legal_references": "lei citada", "parties": "parte", "jurisdiction": "juízo",
    "classification": "tipo", "requests": "pedido", "decisions": "decisão",
    "events": "aconteceu",
}

# O cabecalho da lista, quando a resposta e a colecao inteira. Ele diz a
# palavra que mais importa nessas respostas: EXPRESSAMENTE. O que esta ali e o
# que o documento escreveu com todas as letras - nao o que ele quis dizer.
CABECALHOS = {
    "requests": "PEDIDOS QUE CONSTAM EXPRESSAMENTE DA PEÇA",
    "decisions": "O QUE FOI DECIDIDO, COMO ESTÁ ESCRITO NO DOCUMENTO",
    "events": "O QUE O DOCUMENTO REGISTRA, EM ORDEM DE DATA",
}

# Quantos fatos entram numa resposta de nivel 0. Mais que isso deixa de ser
# resposta e vira listagem - e listagem e a tela de Prazos, nao a conversa.
FATOS_MAX = 12


def resolver(pergunta: str, metas: list[Metadata], *, nomes: dict | None = None,
             em_foco: bool = False) -> Pacote:
    """
    HOOK 2, o miolo. Decide o nivel e junta os fatos quando eles bastam.

    `metas` sao os documentos que a conversa esta olhando - todos, ou so os
    que a pessoa colocou em foco. `em_foco` afrouxa a exigencia de unicidade:
    perguntar "qual o valor?" com um documento aberto e perguntar sobre ele.
    """
    comeco = time.time()
    intencao = classificar(pergunta)
    pacote = Pacote(intencao=intencao, porque=intencao.porque)
    pacote.trace = {"pergunta": pergunta, "intencao": intencao.secao or "-",
                    "chave": intencao.chave, "documentos": len(metas), "em_foco": em_foco}

    if not intencao.resolvivel:
        pacote.trace["decisao"] = "escalou: não é pergunta de dado"
        # Nao responder nao e o fim: o metadata ainda pode dizer ONDE procurar.
        if metas and not em_foco:
            return _pelo_filtro(pacote, pergunta, metas, nomes or {}, comeco)
        pacote.ms = int((time.time() - comeco) * 1000)
        return pacote

    if not metas:
        pacote.porque = "nenhum documento analisado - o caminho de hoje responde"
        pacote.trace["decisao"] = "escalou: sem metadata"
        pacote.ms = int((time.time() - comeco) * 1000)
        return pacote

    if intencao.secao == "summary":
        return _pelo_resumo(pacote, metas, nomes or {}, em_foco, comeco)

    if intencao.enumera:
        return _pela_lista(pacote, metas, nomes or {}, em_foco, comeco)

    achados: list[Fato] = []
    sem_secao = 0
    for meta in metas:
        nome = (nomes or {}).get(meta.version_id) or meta.titulo
        if not meta.secao(intencao.secao).utilizavel:
            # Secao que falta, falhou ou envelheceu conta como "nao sei", e
            # nao como "nao tem": e a diferenca entre escalar e mentir.
            sem_secao += 1
            continue
        achados += _fatos_de(meta, intencao, nome)

    pacote.trace["sem_secao"] = sem_secao
    pacote.trace["achados"] = len(achados)

    if sem_secao and not em_foco:
        # Parte do acervo nao foi analisada: responder so com o que foi
        # analisado daria uma resposta parcial com cara de completa.
        pacote.porque = f"{sem_secao} documento(s) sem essa seção analisada"
        pacote.trace["decisao"] = "escalou: cobertura incompleta"
        pacote.ms = int((time.time() - comeco) * 1000)
        return pacote

    if not achados:
        pacote.porque = "o metadata não tem esse dado - pode estar no documento assim mesmo"
        pacote.trace["decisao"] = "escalou: metadata sem o campo"
        pacote.ms = int((time.time() - comeco) * 1000)
        return pacote

    documentos = list(dict.fromkeys(f.documento for f in achados))
    if len(documentos) > 1 and not em_foco:
        # Ambiguidade nao se resolve por sorteio: tres contratos com valores
        # diferentes e uma pergunta que ainda nao disse qual deles.
        pacote.porque = f"{len(documentos)} documentos respondem a isso - escolher seria sortear"
        pacote.trace["decisao"] = "escalou: resposta ambígua"
        pacote.ms = int((time.time() - comeco) * 1000)
        return pacote

    pacote.nivel = METADATA
    pacote.fatos = achados[:FATOS_MAX]
    pacote.documentos = documentos
    pacote.fallback = False
    pacote.porque = f"respondido pelo que já foi lido em {', '.join(documentos)}"
    pacote.trace["decisao"] = "nível 0"
    pacote.ms = int((time.time() - comeco) * 1000)
    return pacote


# O que numa pergunta diz "procure so num pedaco do acervo". Nao e uma lista de
# palavras bonitas: e o que um escritorio efetivamente escreve quando quer
# recortar o acervo - o ano, o tipo do documento, o tribunal.
RE_ANO = re.compile(r"\b(19\d{2}|20\d{2})\b")
RE_DEPOIS = re.compile(r"\b(posteriores?|depois|a partir|desde|apos)\b")
RE_ANTES = re.compile(r"\b(anteriores?|antes de|ate)\b")

TIPOS_NA_PERGUNTA = {
    "compra_e_venda": ("compra e venda", "compras e vendas"),
    "locacao": ("locacao", "locacoes", "aluguel"),
    "prestacao_servicos": ("prestacao de servicos", "servicos advocaticios"),
    "procuracao": ("procuracao", "procuracoes"),
    "peticao": ("peticao", "peticoes", "contestacao", "inicial"),
    "nda": ("confidencialidade", "nda"),
    "distrato": ("distrato", "rescisao amigavel"),
    "trabalhista": ("contrato de trabalho", "trabalhista"),
}

RE_TRIBUNAL_PERGUNTA = re.compile(r"\b(tj[a-z]{2}|trf\s?\d|trt\s?\d{1,2}|stf|stj|tst)\b")

# Perguntas que comparam pedem mais de um documento aberto ao mesmo tempo.
RE_COMPARA = re.compile(
    r"\b(compar\w*|contradiz\w*|diverg\w*|diferenca entre|bate com|confere com|versus)\b")

# Quantos documentos ainda fazem uma leitura possivel. Acima disso, estreitar
# nao ajudou: continua sendo o acervo, e o caminho e o de hoje.
ESTREITO_MAX = 6


def _filtro_da_pergunta(plano: str) -> dict:
    """O recorte que a pergunta pede - ano, tipo de documento, tribunal."""
    filtro: dict = {}
    anos = [int(a) for a in RE_ANO.findall(plano)]
    if anos:
        filtro["ano"] = anos[0]
        if RE_DEPOIS.search(plano):
            filtro["ano_modo"] = "desde"
        elif RE_ANTES.search(plano):
            filtro["ano_modo"] = "ate"
        else:
            filtro["ano_modo"] = "igual"
    for tipo, pistas in TIPOS_NA_PERGUNTA.items():
        if any(pista in plano for pista in pistas):
            filtro["tipo"] = tipo
            break
    tribunal = RE_TRIBUNAL_PERGUNTA.search(plano)
    if tribunal:
        filtro["tribunal"] = tribunal.group(1).upper().replace(" ", "")
    return filtro


SIM, NAO, NAO_SEI = "sim", "nao", "nao_sei"


def _passa(meta: Metadata, filtro: dict) -> str:
    """
    Este documento entra no recorte? Tres respostas, e a terceira e a que
    protege.

    "Nao sei" nao pode virar "nao". Se a camada ainda nao classificou um
    documento, ele PODE ser o contrato de compra e venda que a pergunta
    procura - e exclui-lo faria o programa responder "nao achei" sobre um
    documento que tem a resposta. O custo de incluir um documento a mais e
    tempo; o de excluir e uma resposta errada com cara de certa.
    """
    duvida = False

    if filtro.get("tipo"):
        classificacao = meta.classification or {}
        conhecido = (meta.secao("classification").utilizavel
                     and classificacao.get("document_type_br")
                     and classificacao.get("document_type_br") != "outro")
        if not conhecido:
            duvida = True
        elif classificacao.get("document_type_br") != filtro["tipo"]:
            return NAO

    if filtro.get("tribunal"):
        juizo = meta.jurisdiction or {}
        if not (meta.secao("jurisdiction").utilizavel and juizo.get("court")):
            duvida = True
        elif str(juizo.get("court", "")).upper() != filtro["tribunal"]:
            return NAO

    if filtro.get("ano"):
        anos = {int(str(i.dados.get("date", ""))[:4]) for i in meta.fatos("dates")
                if str(i.dados.get("date", ""))[:4].isdigit()}
        do_caso = (meta.case or {}).get("year")
        if do_caso:
            anos.add(int(do_caso))
        if not anos:
            # Documento sem data lida nao e documento sem data: pode ser data
            # que o extrator nao reconheceu.
            duvida = True
        else:
            alvo, modo = filtro["ano"], filtro.get("ano_modo", "igual")
            bate = (any(a >= alvo for a in anos) if modo == "desde"
                    else any(a <= alvo for a in anos) if modo == "ate"
                    else alvo in anos)
            if not bate:
                return NAO

    return NAO_SEI if duvida else SIM


def _pelo_filtro(pacote: "Pacote", pergunta: str, metas: list[Metadata], nomes: dict,
                 comeco: float) -> "Pacote":
    """
    Nivel 3 e 4: a camada nao responde, mas diz onde procurar.

    "O que os contratos de 2025 dizem sobre multa" e pergunta de leitura - o
    metadata nao tem a resposta. Mas ele sabe quais documentos sao contratos e
    quais sao de 2025, e essa e a diferenca entre o buscador varrer catorze
    documentos e varrer tres. O que acontece depois e exatamente o que
    acontecia antes: o buscador de hoje, com os trechos de sempre.

    Recorte que nao recorta nada nao ajuda ninguem; e recorte que deixa zero
    documento seria responder "nao ha" sobre o que pode estar num documento
    que a camada ainda nao analisou. Nos dois casos, escala.
    """
    plano = _plano(pergunta)
    filtro = _filtro_da_pergunta(plano)
    if not filtro:
        pacote.ms = int((time.time() - comeco) * 1000)
        return pacote

    vereditos = [(m, _passa(m, filtro)) for m in metas]
    certos = [m for m, v in vereditos if v == SIM]
    # Os que a camada nao conhece entram junto: nao saber nao e dizer que nao.
    escolhidos = [m for m, v in vereditos if v in (SIM, NAO_SEI)]
    pacote.trace["filtro"] = filtro
    pacote.trace["certos"] = len(certos)
    pacote.trace["escolhidos"] = len(escolhidos)

    if not certos or len(escolhidos) >= len(metas) or len(escolhidos) > ESTREITO_MAX:
        # Recorte que nao recorta nada nao ajuda; recorte sem nenhum documento
        # certo seria procurar so entre os que a camada nao conhece.
        pacote.trace["decisao"] = "escalou: o recorte nao estreitou"
        pacote.ms = int((time.time() - comeco) * 1000)
        return pacote

    comparando = bool(RE_COMPARA.search(plano))
    pacote.nivel = VARIOS_DOCUMENTOS if (comparando and len(escolhidos) > 1) else BUSCADOR_FILTRADO
    pacote.restringe = [nomes.get(m.version_id) or m.titulo for m in escolhidos]
    pacote.documentos = list(pacote.restringe)
    pacote.fallback = False
    duvidosos = len(escolhidos) - len(certos)
    pacote.porque = (
        "o que já foi lido aponta " + _quantos(len(certos), "documento") +
        (f" (mais {duvidosos} que ainda não foram analisados)" if duvidosos else "") +
        " em vez de " + _quantos(len(metas), "documento"))
    pacote.trace["decisao"] = f"nível {pacote.nivel}"
    pacote.ms = int((time.time() - comeco) * 1000)
    return pacote


def _pelo_resumo(pacote: Pacote, metas: list[Metadata], nomes: dict, em_foco: bool,
                 comeco: float) -> Pacote:
    """
    Nivel 1: o resumo que foi escrito quando o documento entrou.

    So com documento em foco. "Resuma o acervo" nao e uma pergunta que um
    resumo por documento responde - e juntar catorze resumos numa resposta
    seria dar a impressao de que o programa leu todos agora.
    """
    if not em_foco or len(metas) != 1:
        pacote.porque = "resumir pede um documento de cada vez"
        pacote.trace["decisao"] = "escalou: resumo sem documento em foco"
        pacote.ms = int((time.time() - comeco) * 1000)
        return pacote

    meta = metas[0]
    resumo = (meta.summary or {}) if meta.secao("summary").utilizavel else {}
    texto = str(resumo.get("short") or resumo.get("one_line") or "").strip()
    if not texto:
        pacote.porque = "este documento ainda não foi resumido"
        pacote.trace["decisao"] = "escalou: sem resumo guardado"
        pacote.ms = int((time.time() - comeco) * 1000)
        return pacote

    nome = nomes.get(meta.version_id) or meta.titulo
    pacote.nivel = METADATA_E_RESUMO
    pacote.inferencia = True
    pacote.fatos = [Fato(documento=nome, document_id=meta.document_id,
                         version_id=meta.version_id, secao="summary",
                         rotulo="leitura do assistente", valor=texto)]
    pacote.documentos = [nome]
    pacote.fallback = False
    pacote.porque = "respondido pelo resumo guardado de " + nome
    pacote.trace["decisao"] = "nível 1"
    pacote.ms = int((time.time() - comeco) * 1000)
    return pacote


def _pela_lista(pacote: Pacote, metas: list[Metadata], nomes: dict, em_foco: bool,
                comeco: float) -> Pacote:
    """
    Nivel 0 para as colecoes de extensao: a resposta e a lista inteira.

    "Quais os pedidos?" nao pede um dado, pede todos os de um tipo - e a lista
    ja esta guardada, com a citacao e a pagina de cada um. E onde mora o risco
    desta camada inteira: **uma lista de tres quando havia cinco tem a mesma
    cara de uma lista completa.** Quem le nao tem como saber que faltou.

    Tres travas, e todas escalam em vez de responder pela metade:

    - **so com um documento em foco.** Listar os pedidos de catorze documentos
      numa resposta so seria juntar pecas diferentes na mesma lista;
    - **secao nao utilizavel escala.** Documento nao analisado para esta
      colecao pode ter dez pedidos escritos - a lista vazia seria mentira;
    - **lista que nao cabe escala.** Se o que foi achado ja encosta no limite
      da resposta, cortar seria entregar uma lista truncada sem dizer - entao
      a pergunta vai para o caminho de hoje, que le o documento.
    """
    secao = pacote.intencao.secao
    def desistir(porque: str, decisao: str) -> Pacote:
        pacote.porque = porque
        pacote.trace["decisao"] = f"escalou: {decisao}"
        pacote.ms = int((time.time() - comeco) * 1000)
        return pacote

    if not em_foco or len(metas) != 1:
        return desistir("listar pede um documento de cada vez", "lista sem documento em foco")

    meta = metas[0]
    nome = nomes.get(meta.version_id) or meta.titulo
    if not meta.secao(secao).utilizavel:
        return desistir("este documento ainda não foi lido para isso",
                        "seção não utilizável")

    itens = [i for i in meta.fatos(secao)
             if not pacote.intencao.chave or i.dados.get("kind") == pacote.intencao.chave]
    pacote.trace["achados"] = len(itens)
    if not itens:
        return desistir("o metadata não tem essa lista - pode estar no documento assim mesmo",
                        "coleção vazia")
    if len(itens) >= FATOS_MAX:
        return desistir(f"são {len(itens)} itens - listar sem ler o documento cortaria a lista",
                        "lista longa demais")

    pacote.nivel = METADATA
    pacote.enumera = True
    pacote.fatos = [_fato_do_item(meta, item, nome, secao) for item in itens]
    pacote.documentos = [nome]
    pacote.fallback = False
    pacote.porque = f"{_quantos(len(itens), 'item')} que já foram lidos em {nome}"
    pacote.trace["decisao"] = "nível 0 (lista)"
    pacote.ms = int((time.time() - comeco) * 1000)
    return pacote


def _fatos_de(meta: Metadata, intencao: Intencao, nome: str) -> list[Fato]:
    """Os fatos conferidos desta secao que respondem ao que foi perguntado."""
    saida: list[Fato] = []

    if intencao.secao in ("case", "jurisdiction", "classification"):
        objeto = meta.por_secao(intencao.secao) or {}
        valor = objeto.get(intencao.chave or "")
        if not valor or not objeto.get("verified", False):
            return []
        fonte = objeto.get("source") or {}
        return [Fato(documento=nome, document_id=meta.document_id, version_id=meta.version_id,
                     secao=intencao.secao, rotulo=ROTULOS.get(intencao.chave, ""),
                     valor=str(valor), quote=objeto.get("quote", ""),
                     pagina=fonte.get("page"), char_start=fonte.get("char_start"),
                     char_end=fonte.get("char_end"))]

    for item in meta.fatos(intencao.secao):
        if intencao.chave and item.dados.get("kind") != intencao.chave:
            continue
        saida.append(_fato_do_item(meta, item, nome, intencao.secao))
    return saida


def _fato_do_item(meta: Metadata, item: Item, nome: str, secao: str) -> Fato:
    tipo = str(item.dados.get("kind") or "")
    valor = item.valor
    if secao == "amounts":
        valor = str(item.dados.get("value_text") or valor)
    elif secao == "dates":
        valor = str(item.dados.get("date") or valor)
    elif secao == "events":
        # Numa linha do tempo a data nao e um rotulo da frase: e a metade
        # esquerda dela. Sem a data na frente, a lista deixa de ser cronologia.
        valor = f"{item.dados.get('date', '')} - {valor}".strip(" -")
    elif secao == "legal_references":
        partes = [str(item.dados.get("instrument") or "")]
        if item.dados.get("article"):
            partes.append("art. " + str(item.dados["article"]))
        if item.dados.get("paragraph"):
            partes.append("§ " + str(item.dados["paragraph"]))
        if item.dados.get("item"):
            partes.append(str(item.dados["item"]))
        valor = ", ".join(p for p in partes if p) or valor
    return Fato(
        documento=nome, document_id=meta.document_id, version_id=meta.version_id,
        secao=secao, rotulo=ROTULOS.get(tipo, tipo), valor=valor, quote=item.quote,
        pagina=item.source.page, char_start=item.source.char_start,
        char_end=item.source.char_end,
    )


def pediu_escalar(resposta: str) -> bool:
    """O modelo avisou que os fatos nao bastavam."""
    limpo = _plano(resposta)[:40]
    return limpo.startswith("escalar") or limpo == "escalar"
