"""
PAULUS Legal - Busca BM25 sobre contratos.

Os documentos sao quebrados em trechos (chunks) antes de indexar. Isso importa
por dois motivos:
  1. O BM25 penaliza documentos longos; um contrato de 40 paginas quase nunca
     "vence" no ranking mesmo contendo a resposta exata.
  2. O contexto enviado ao LLM precisa caber na janela do modelo. Trechos de
     ~1200 caracteres cabem; contratos inteiros nao.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from extract import Document

# Stopwords de portugues + ruido tipico de peticao/contrato.
STOPWORDS_PT = {
    "a", "ao", "aos", "as", "com", "como", "da", "das", "de", "do", "dos", "e",
    "ela", "elas", "ele", "eles", "em", "entre", "era", "essa", "esse", "esta",
    "este", "eu", "foi", "ha", "isso", "isto", "ja", "la", "lhe", "mais", "mas",
    "me", "mesmo", "meu", "muito", "na", "nao", "nas", "nem", "no", "nos", "num",
    "numa", "o", "os", "ou", "para", "pela", "pelas", "pelo", "pelos", "por",
    "qual", "quando", "que", "quem", "sao", "se", "sem", "ser", "seu", "seus",
    "so", "sobre", "sua", "suas", "tem", "ter", "um", "uma", "voce", "ate",
}

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


def normalize(text: str) -> str:
    """Minusculas sem acento - 'CLÁUSULA' e 'clausula' viram o mesmo token."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", normalize(text))
    return [t for t in tokens if len(t) >= 2 and t not in STOPWORDS_PT]


@dataclass
class Chunk:
    doc_name: str
    doc_path: str
    index: int
    text: str


@dataclass
class Hit:
    chunk: Chunk
    score: float
    snippet: str

    @property
    def doc_name(self) -> str:
        return self.chunk.doc_name


def chunk_document(doc: Document, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[Chunk]:
    """Quebra o texto em blocos, respeitando quebras de paragrafo quando da."""
    paragrafos = [p.strip() for p in re.split(r"\n\s*\n", doc.text) if p.strip()]
    chunks: list[Chunk] = []
    buffer = ""

    def flush() -> None:
        nonlocal buffer
        if buffer.strip():
            chunks.append(Chunk(doc.name, doc.path, len(chunks), buffer.strip()))
            buffer = buffer[-overlap:] if overlap else ""

    for par in paragrafos:
        # Paragrafo gigante (contrato sem quebras): corta na marra.
        while len(par) > size:
            corte = par[:size]
            ponto = corte.rfind(". ")
            if ponto < size // 2:
                ponto = size
            buffer += ("\n" if buffer else "") + par[:ponto]
            flush()
            par = par[ponto:].lstrip()

        if len(buffer) + len(par) > size:
            flush()
        buffer += ("\n" if buffer else "") + par

    flush()
    return chunks


class ContractSearcher:
    """Indice BM25 sobre os trechos de todos os contratos carregados."""

    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self.documents: list[Document] = []
        self._bm25 = None

    def add_contracts(self, docs: list[Document]) -> None:
        self.documents.extend(docs)
        for doc in docs:
            self.chunks.extend(chunk_document(doc))
        self._bm25 = None  # invalida o indice

    def build(self) -> None:
        try:
            from rank_bm25 import BM25Okapi
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "rank-bm25 nao instalado. Rode: pip install -r requirements.txt"
            ) from exc

        if not self.chunks:
            self._bm25 = None
            return

        corpus = [tokenize(c.text) for c in self.chunks]
        self._bm25 = BM25Okapi(corpus)

    def search(self, query: str, top_k: int = 5, per_doc_limit: int = 2) -> list[Hit]:
        """
        Retorna os melhores trechos para a pergunta.

        `per_doc_limit` evita que um unico contrato ocupe todos os slots de
        contexto - com 10 contratos, o usuario quase sempre quer comparar.
        """
        if self._bm25 is None:
            self.build()
        if self._bm25 is None:
            return []

        tokens = tokenize(query)
        if not tokens:
            return []

        scores = self._bm25.get_scores(tokens)
        ordem = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

        hits: list[Hit] = []
        por_doc: dict[str, int] = {}
        for i in ordem:
            if scores[i] <= 0:
                break
            chunk = self.chunks[i]
            if por_doc.get(chunk.doc_name, 0) >= per_doc_limit:
                continue
            por_doc[chunk.doc_name] = por_doc.get(chunk.doc_name, 0) + 1
            hits.append(Hit(chunk, float(scores[i]), _extract_snippet(chunk.text, tokens)))
            if len(hits) >= top_k:
                break

        return hits

    def format_context(self, hits: list[Hit], max_chars: int = 6000) -> str:
        """
        Monta o bloco de contexto que vai para o LLM.

        Os trechos sao agrupados por contrato e remontados na ordem original.
        Sem isso o modelo recebe o mesmo contrato duas vezes (em pedacos com
        sobreposicao) e responde como se fossem documentos diferentes.
        """
        por_doc: dict[str, list[Chunk]] = {}
        for hit in hits:  # hits ja vem ordenado por relevancia
            por_doc.setdefault(hit.chunk.doc_name, []).append(hit.chunk)

        partes: list[str] = []
        total = 0
        for doc_name, chunks in por_doc.items():
            unicos = {c.index: c for c in chunks}
            ordenados = [unicos[i] for i in sorted(unicos)]
            bloco = f"--- {doc_name} ---\n{merge_chunks(ordenados)}"
            if total + len(bloco) > max_chars:
                break
            partes.append(bloco)
            total += len(bloco)

        return "\n\n".join(partes)


def merge_chunks(chunks: list[Chunk]) -> str:
    """Remonta trechos de um mesmo contrato, removendo a sobreposicao."""
    if not chunks:
        return ""

    texto = chunks[0].text
    for anterior, atual in zip(chunks, chunks[1:]):
        if atual.index != anterior.index + 1:
            texto += "\n\n[...]\n\n" + atual.text
            continue
        # trechos vizinhos compartilham ate CHUNK_OVERLAP caracteres
        corte = 0
        for tam in range(min(CHUNK_OVERLAP + 50, len(texto), len(atual.text)), 20, -1):
            if texto.endswith(atual.text[:tam]):
                corte = tam
                break
        texto += "\n" + atual.text[corte:]
    return texto


def _extract_snippet(text: str, tokens: list[str], width: int = 280) -> str:
    """Janela de texto em volta da primeira ocorrencia de um termo da busca."""
    norm = normalize(text)
    pos = -1
    for token in tokens:
        p = norm.find(token)
        if p != -1 and (pos == -1 or p < pos):
            pos = p

    if pos == -1:
        return text[:width].strip() + ("..." if len(text) > width else "")

    inicio = max(0, pos - width // 3)
    fim = min(len(text), inicio + width)
    trecho = text[inicio:fim].replace("\n", " ").strip()
    prefixo = "..." if inicio > 0 else ""
    sufixo = "..." if fim < len(text) else ""
    return f"{prefixo}{trecho}{sufixo}"
