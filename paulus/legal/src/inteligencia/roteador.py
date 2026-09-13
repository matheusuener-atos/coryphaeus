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

# Perguntas que NAO sao factuais mesmo contendo as palavras acima: elas pedem
# leitura, e leitura e o caminho de hoje. "O que a contestacao alega sobre a
# prescricao?" tem "o que" e nao tem resposta em tres linhas de metadata.
PEDE_LEITURA = re.compile(
    r"\b(alega|argumenta|sustenta|fundamenta|explica|resume|resumo|analis|compar|"
    r"por que|porque|como|discorre|entende|conclui|clausula que|onde diz|"
    r"contradiz|diverg|interpreta)\b")

RE_INTENCOES = [(secao, chave, re.compile(padrao)) for secao, chave, padrao in INTENCOES]


@dataclass
class Intencao:
    """O que a pergunta parece pedir - e com quanta certeza."""

    secao: str = ""
    chave: str = ""
    nivel: int = BUSCADOR
    porque: str = ""

    @property
    def factual(self) -> bool:
        return self.nivel == METADATA and bool(self.secao)


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
        return f"- {self.secao}{rotulo}: {self.valor}{onde}"


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
    ms: int = 0
    trace: dict = field(default_factory=dict)

    @property
    def responde_sozinho(self) -> bool:
        return self.nivel <= METADATA_E_RESUMO and bool(self.fatos)

    def prompt(self, pergunta: str) -> str:
        """
        O prompt do nivel 0: fatos, nao prosa.

        A ultima linha e o mecanismo de nao-regressao: o modelo que nao
        conseguir responder com estes fatos diz ESCALAR, e a pergunta refaz o
        caminho de sempre.
        """
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
                "ms": self.ms, "trace": self.trace}


ROTULOS = {
    "signature": "assinatura", "filing": "protocolo", "publication": "publicação",
    "hearing": "audiência", "deadline": "prazo", "decision": "decisão", "term": "vigência",
    "claim": "valor da causa", "fee": "honorários", "contract": "valor do contrato",
    "penalty": "multa", "rent": "aluguel", "damages": "indenização", "debt": "dívida",
    "installment": "parcela", "article": "artigo", "law": "lei", "precedent": "súmula",
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

    if not intencao.factual:
        pacote.ms = int((time.time() - comeco) * 1000)
        pacote.trace["decisao"] = "escalou: não é pergunta de dado"
        return pacote

    if not metas:
        pacote.porque = "nenhum documento analisado - o caminho de hoje responde"
        pacote.trace["decisao"] = "escalou: sem metadata"
        pacote.ms = int((time.time() - comeco) * 1000)
        return pacote

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
