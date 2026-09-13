"""
O formato `legal-document/v0`: o que se sabe de um documento, por escrito.

Este e o contrato da camada. Tudo o que os extratores produzem e tudo o que o
roteador consulta passa por aqui, e por isso ele e o unico modulo que nao pode
mudar de forma sem plano de migracao.

Tres decisoes que o resto do pacote depende:

**As chaves do JSON ficam em ingles.** O repositorio inteiro fala portugues, e
esta e a excecao: `legal-document/v0` e um formato, nao uma tela. Um metadata
gravado hoje pode ser lido amanha por outro programa, exportado, comparado com
o de outra instalacao. Traduzir as chaves criaria uma tabela de equivalencia
para manter viva e um dia errar. Os comentarios e as mensagens continuam em
portugues, que e quem le codigo aqui.

**Todo item carrega de onde veio.** Nao existe fato solto: ou ele tem `source`
apontando para o trecho que o sustenta, ou ele nao e fato. `verified: false`
significa "ninguem conferiu", e item nao conferido nunca vira resposta.

**A secao sabe quem a produziu.** `analysis.sections` guarda o extrator, o
modelo, o digest do modelo e a versao do prompt. Sem isso, trocar de modelo
seria trocar de resultado sem saber, e reprocessar exigiria refazer tudo em
vez de refazer uma secao.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

ESQUEMA = "legal-document/v0"

# As secoes do nucleo minimo (spec, secao 5).
SECOES_OBJETO = ("classification", "jurisdiction", "case", "summary")
SECOES_NUCLEO = ("parties", "dates", "amounts", "legal_references")

# As colecoes de extensao (spec, passo 7). Elas nao ganharam campo proprio no
# `Metadata` de proposito: ficam num dicionario e sobem para o primeiro nivel
# do JSON na hora de gravar. Assim acrescentar uma colecao e acrescentar um
# nome nesta tupla e um extrator - nao mexer na classe, nao migrar o acervo, e
# nao tocar em nada do que ja estava gravado. E o que a spec pede quando diz
# que nenhuma extensao exige migracao desde que `analysis.sections` exista.
SECOES_EXTENSAO = ("events", "claims", "requests", "decisions", "evidence",
                   "relationships", "people", "organizations")

SECOES_COLECAO = SECOES_NUCLEO + SECOES_EXTENSAO
SECOES = SECOES_OBJETO + SECOES_COLECAO

# `explicit` esta escrito no documento, com trecho citado. `inferred` foi
# deduzido. `uncertain` e palpite assumido. `disputed` e o que as partes
# discordam entre si. So o primeiro pode ser apresentado como fato.
CERTEZAS = ("explicit", "inferred", "uncertain", "disputed")

# Confianca nunca e float auto-reportado pelo modelo (spec, nao-objetivos).
CONFIANCAS = ("high", "medium", "low", "unknown")

ESTADOS_SECAO = ("ok", "stale", "failed", "missing", "skipped")

METODOS = ("pdf-text", "pdf-ocr", "docx-parser", "html-parser", "asr",
           "manual", "external-source", "model-inference")


def agora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _limpo(dados: dict) -> dict:
    """Sem as chaves vazias: metadata e para ler, e nulo em fila polui."""
    return {k: v for k, v in dados.items() if v not in (None, "", [], {})}


@dataclass
class Fonte:
    """
    Onde, no acervo, esta o que sustenta o item.

    Tem forma para texto, audio e imagem desde o comeco de proposito. `source`
    aparece em toda colecao; mudar o formato depois seria migrar o acervo
    inteiro, e a transcricao de audio ja existe neste programa.
    """

    version_id: str = ""
    kind: str = "text"                  # text | audio | image
    page: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    chunk_id: str = ""
    time_start: float | None = None     # audio
    time_end: float | None = None
    speaker: str = ""
    bbox: list[float] = field(default_factory=list)   # imagem

    def to_dict(self) -> dict:
        return _limpo({
            "version_id": self.version_id, "kind": self.kind, "page": self.page,
            "char_start": self.char_start, "char_end": self.char_end,
            "chunk_id": self.chunk_id, "time_start": self.time_start,
            "time_end": self.time_end, "speaker": self.speaker,
            "bbox": self.bbox,
        })

    @classmethod
    def from_dict(cls, dados: dict | None) -> "Fonte":
        dados = dados or {}
        return cls(
            version_id=dados.get("version_id", ""), kind=dados.get("kind", "text"),
            page=dados.get("page"), char_start=dados.get("char_start"),
            char_end=dados.get("char_end"), chunk_id=dados.get("chunk_id", ""),
            time_start=dados.get("time_start"), time_end=dados.get("time_end"),
            speaker=dados.get("speaker", ""), bbox=list(dados.get("bbox") or []),
        )

    @property
    def resolvivel(self) -> bool:
        """Da para levar alguem ate la? E o minimo para citar."""
        if self.kind == "text":
            return self.char_start is not None and self.char_end is not None
        if self.kind == "audio":
            return self.time_start is not None
        return bool(self.bbox)


# Os campos que sao do item em si; o resto e da secao e fica em `dados`.
_CAMPOS_ITEM = {"id", "quote", "certainty", "verified", "source", "produced_by"}


@dataclass
class Item:
    """
    Um fato extraido, na forma canonica da spec (secao 5.1).

    `dados` guarda o que e proprio da secao - `name`/`role` numa parte,
    `value`/`currency` num valor - e sobe para o primeiro nivel do JSON. Assim
    uma secao nova nao exige classe nova, e o formato continua o da spec.
    """

    id: str = ""
    dados: dict = field(default_factory=dict)
    quote: str = ""
    certainty: str = "inferred"
    verified: bool = False
    source: Fonte = field(default_factory=Fonte)
    produced_by: str = ""

    def to_dict(self) -> dict:
        saida = {"id": self.id}
        saida.update(self.dados)
        saida.update({
            "quote": self.quote,
            "certainty": self.certainty,
            "verified": self.verified,
            "source": self.source.to_dict(),
            "produced_by": self.produced_by,
        })
        return _limpo(saida)

    @classmethod
    def from_dict(cls, dados: dict) -> "Item":
        proprios = {k: v for k, v in dados.items() if k not in _CAMPOS_ITEM}
        return cls(
            id=dados.get("id", ""), dados=proprios, quote=dados.get("quote", ""),
            certainty=dados.get("certainty", "inferred"),
            verified=bool(dados.get("verified")),
            source=Fonte.from_dict(dados.get("source")),
            produced_by=dados.get("produced_by", ""),
        )

    @property
    def valor(self) -> str:
        """O que se mostra na resposta: o nome, o texto, o numero."""
        for chave in ("name", "text", "value_text", "number", "value", "title"):
            if self.dados.get(chave):
                return str(self.dados[chave])
        return self.quote

    @property
    def pode_virar_fato(self) -> bool:
        """
        A regra que impede a camada de inventar.

        Fato e o que esta escrito e foi conferido no texto. Deduzido, duvidoso
        ou nao conferido pode aparecer rotulado, nunca como fato - e nunca no
        nivel 0 do roteador.
        """
        return self.verified and self.certainty == "explicit" and self.source.resolvivel


@dataclass
class Secao:
    """A ficha de producao de uma secao: quem fez, com o que, e como acabou."""

    extractor: str = ""
    model: str | None = None
    model_digest: str = ""
    prompt_version: str = ""
    schema_version: str = "v0"
    generated_at: str = ""
    status: str = "missing"
    item_count: int = 0
    unverified_count: int = 0
    duration_ms: int = 0
    stale_reason: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return _limpo({
            "extractor": self.extractor, "model": self.model,
            "model_digest": self.model_digest, "prompt_version": self.prompt_version,
            "schema_version": self.schema_version, "generated_at": self.generated_at,
            "status": self.status, "item_count": self.item_count,
            "unverified_count": self.unverified_count, "duration_ms": self.duration_ms,
            "stale_reason": self.stale_reason, "error": self.error,
        })

    @classmethod
    def from_dict(cls, dados: dict) -> "Secao":
        return cls(
            extractor=dados.get("extractor", ""), model=dados.get("model"),
            model_digest=dados.get("model_digest", ""),
            prompt_version=dados.get("prompt_version", ""),
            schema_version=dados.get("schema_version", "v0"),
            generated_at=dados.get("generated_at", ""),
            status=dados.get("status", "missing"),
            item_count=int(dados.get("item_count", 0) or 0),
            unverified_count=int(dados.get("unverified_count", 0) or 0),
            duration_ms=int(dados.get("duration_ms", 0) or 0),
            stale_reason=dados.get("stale_reason", ""), error=dados.get("error", ""),
        )

    @property
    def utilizavel(self) -> bool:
        """Secao velha ou quebrada e tratada como inexistente, nao como errada."""
        return self.status == "ok"


@dataclass
class Metadata:
    """
    O que se sabe de UMA versao de um documento.

    Documento e a obra e nao muda de identidade; versao e o conteudo e muda a
    cada byte diferente no original. Relacoes apontam para o documento;
    proveniencia aponta para a versao (spec, secao 5.2).
    """

    document: dict = field(default_factory=dict)
    version: dict = field(default_factory=dict)
    classification: dict = field(default_factory=dict)
    jurisdiction: dict = field(default_factory=dict)
    case: dict = field(default_factory=dict)
    parties: list[Item] = field(default_factory=list)
    dates: list[Item] = field(default_factory=list)
    amounts: list[Item] = field(default_factory=list)
    legal_references: list[Item] = field(default_factory=list)
    summary: dict = field(default_factory=lambda: {"one_line": "", "short": None, "detailed": None})
    provenance: dict = field(default_factory=dict)
    analysis: dict = field(default_factory=lambda: {"sections": {}})
    # As colecoes de extensao moram aqui. A chave so existe depois que o
    # extrator rodou - e a diferenca entre "analisei e nao ha pedido nenhum"
    # (lista vazia) e "ninguem procurou pedido aqui" (chave ausente).
    extensoes: dict[str, list[Item]] = field(default_factory=dict)

    # ------------------------------------------------------------ acesso

    def colecao(self, secao: str) -> list[Item]:
        if secao in SECOES_EXTENSAO:
            return list(self.extensoes.get(secao) or [])
        return list(getattr(self, secao, []) or []) if secao in SECOES_NUCLEO else []

    def guardar(self, secao: str, itens: list[Item]) -> None:
        """Onde a colecao fica depende de ela ser do nucleo ou de extensao."""
        if secao in SECOES_EXTENSAO:
            self.extensoes[secao] = list(itens)
        elif secao in SECOES_NUCLEO:
            setattr(self, secao, list(itens))

    def por_secao(self, secao: str) -> Any:
        if secao in SECOES_EXTENSAO:
            return self.extensoes.get(secao)
        return getattr(self, secao, None)

    def secao(self, nome: str) -> Secao:
        bruto = (self.analysis.get("sections") or {}).get(nome)
        return Secao.from_dict(bruto) if bruto else Secao(status="missing")

    def marcar_secao(self, nome: str, ficha: Secao) -> None:
        self.analysis.setdefault("sections", {})[nome] = ficha.to_dict()

    def fatos(self, secao: str) -> list[Item]:
        """So o que pode ser apresentado como fato - a regra do nivel 0."""
        if not self.secao(secao).utilizavel:
            return []
        return [i for i in self.colecao(secao) if i.pode_virar_fato]

    @property
    def version_id(self) -> str:
        return self.version.get("id", "")

    @property
    def document_id(self) -> str:
        return self.document.get("id", "")

    @property
    def titulo(self) -> str:
        return self.document.get("title") or self.version.get("source_path", "")

    # ------------------------------------------------------------- forma

    def to_dict(self) -> dict:
        saida = {
            "schema": ESQUEMA,
            "document": self.document,
            "version": self.version,
            "classification": self.classification,
            "jurisdiction": self.jurisdiction,
            "case": self.case,
            "parties": [i.to_dict() for i in self.parties],
            "dates": [i.to_dict() for i in self.dates],
            "amounts": [i.to_dict() for i in self.amounts],
            "legal_references": [i.to_dict() for i in self.legal_references],
            "summary": self.summary,
            "provenance": self.provenance,
            "analysis": self.analysis,
        }
        # Extensao sobe para o primeiro nivel, junto das colecoes do nucleo:
        # quem le o JSON nao precisa saber que ela chegou depois.
        for nome in SECOES_EXTENSAO:
            if nome in self.extensoes:
                saida[nome] = [i.to_dict() for i in self.extensoes[nome]]
        return saida

    @classmethod
    def from_dict(cls, dados: dict) -> "Metadata":
        def itens(nome: str) -> list[Item]:
            return [Item.from_dict(x) for x in (dados.get(nome) or [])]

        return cls(
            document=dados.get("document") or {},
            version=dados.get("version") or {},
            classification=dados.get("classification") or {},
            jurisdiction=dados.get("jurisdiction") or {},
            case=dados.get("case") or {},
            parties=itens("parties"), dates=itens("dates"),
            amounts=itens("amounts"), legal_references=itens("legal_references"),
            summary=dados.get("summary") or {"one_line": "", "short": None, "detailed": None},
            provenance=dados.get("provenance") or {},
            analysis=dados.get("analysis") or {"sections": {}},
            extensoes={nome: itens(nome) for nome in SECOES_EXTENSAO if nome in dados},
        )


def problemas(dados: dict) -> list[str]:
    """
    O que esta errado neste metadata, em portugues.

    Existe para o teste e para o backfill: um metadata gravado torto so
    aparece na hora de responder, e ali ja e tarde.
    """
    achados: list[str] = []
    if dados.get("schema") != ESQUEMA:
        achados.append(f"schema deveria ser {ESQUEMA}")
    for chave in ("document", "version"):
        if not (dados.get(chave) or {}).get("id"):
            achados.append(f"{chave}.id vazio")
    if not (dados.get("version") or {}).get("sha256"):
        achados.append("version.sha256 vazio")

    for secao in SECOES_COLECAO:
        for bruto in dados.get(secao) or []:
            item = Item.from_dict(bruto)
            if not item.id:
                achados.append(f"{secao}: item sem id")
            if item.certainty not in CERTEZAS:
                achados.append(f"{secao}/{item.id}: certainty '{item.certainty}' nao existe")
            if item.certainty == "explicit" and not item.quote:
                achados.append(f"{secao}/{item.id}: explicit sem quote")
            if item.verified and not item.source.resolvivel:
                achados.append(f"{secao}/{item.id}: verificado sem fonte resolvivel")
            if not item.produced_by:
                achados.append(f"{secao}/{item.id}: sem produced_by")

    for nome, bruto in (dados.get("analysis", {}).get("sections") or {}).items():
        ficha = Secao.from_dict(bruto)
        if ficha.status not in ESTADOS_SECAO:
            achados.append(f"analysis/{nome}: status '{ficha.status}' nao existe")
        if ficha.status == "ok" and not ficha.extractor:
            achados.append(f"analysis/{nome}: ok sem extrator")
    return achados
