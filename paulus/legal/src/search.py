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
from contextvars import ContextVar
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


def radical(token: str) -> str:
    """
    Reduz o plural ao singular.

    Sem isso, "clausulas" na pergunta nao casa com "CLAUSULA" no contrato, e a
    busca perde justamente o trecho que interessa. Nao e um stemmer completo -
    e a regra de plural do portugues, que cobre a quase totalidade do
    vocabulario de contrato.
    """
    if len(token) <= 3 or not token.endswith("s"):
        return token

    for final, troca in (("oes", "ao"), ("aes", "ao"), ("ais", "al"), ("eis", "el"), ("ois", "ol")):
        if token.endswith(final):
            return token[: -len(final)] + troca

    if token.endswith("ns"):          # bens -> bem
        return token[:-2] + "m"

    return token[:-1]


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", normalize(text))
    return [radical(t) for t in tokens if len(t) >= 2 and t not in STOPWORDS_PT]


@dataclass
class Chunk:
    doc_name: str
    doc_path: str
    index: int
    text: str
    # Os trechos estruturais (I5, src/trechos.py) sabem onde estao: o id
    # estavel, a faixa no texto extraido, as paginas, o regime e o texto com
    # o caminho na frente, que e o que a busca indexa. Os de tamanho fixo
    # deixam vazio.
    chunk_id: str = ""
    char_start: int = 0
    char_end: int = 0
    pagina_inicio: int | None = None
    pagina_fim: int | None = None
    regime: str = ""
    text_embed: str = ""

    @property
    def text_raw(self) -> str:
        return self.text


@dataclass
class Hit:
    chunk: Chunk
    score: float
    snippet: str

    @property
    def doc_name(self) -> str:
        return self.chunk.doc_name


def _cauda(texto: str, overlap: int) -> str:
    """
    Ultimos caracteres de um trecho, comecando em palavra inteira.

    Cortar numa posicao fixa faz o trecho seguinte comecar no meio de uma
    palavra ("fo Unico:" no lugar de "Paragrafo Unico:"). Isso aparece na tela
    do usuario, tanto na busca quanto nos trechos citados na resposta.
    """
    if overlap <= 0 or not texto:
        return ""

    cauda = texto[-overlap:]
    if len(texto) <= overlap or texto[-overlap - 1].isspace():
        return cauda  # ja comeca em palavra inteira

    frase = cauda.find(". ")
    if frase != -1:
        return cauda[frase + 2 :]

    espaco = re.search(r"\s", cauda)
    return cauda[espaco.end() :] if espaco else ""


def chunk_document(doc: Document, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[Chunk]:
    """Quebra o texto em blocos, respeitando quebras de paragrafo quando da."""
    paragrafos = [p.strip() for p in re.split(r"\n\s*\n", doc.text) if p.strip()]
    chunks: list[Chunk] = []
    buffer = ""

    def flush() -> None:
        nonlocal buffer
        if buffer.strip():
            chunks.append(Chunk(doc.name, doc.path, len(chunks), buffer.strip()))
            buffer = _cauda(buffer, overlap)

    for par in paragrafos:
        # Paragrafo gigante (contrato sem quebras): corta no fim de frase; nao
        # havendo, no ultimo espaco - nunca no meio de uma palavra.
        while len(par) > size:
            corte = par[:size]
            ponto = corte.rfind(". ")
            ponto = ponto + 1 if ponto >= size // 2 else -1
            if ponto == -1:
                espaco = corte.rfind(" ")
                ponto = espaco if espaco >= size // 2 else size
            buffer += ("\n" if buffer else "") + par[:ponto]
            flush()
            par = par[ponto:].lstrip()

        if len(buffer) + len(par) > size:
            flush()
        buffer += ("\n" if buffer else "") + par

    flush()
    return chunks


def chunk_estrutural(doc: Document) -> list[Chunk]:
    """
    Os trechos pela estrutura do documento (src/trechos.py): clausula, secao
    ou artigo, com id estavel e pagina.
    """
    import trechos
    from inteligencia.texto import mapa_de_paginas, pagina_de

    versao = trechos.versao_de(doc.sha1, doc.text, doc.name)
    paginas = mapa_de_paginas(doc.text)
    titulo = re.sub(r"\.[A-Za-z0-9]{2,4}$", "", doc.name)
    saida: list[Chunk] = []
    for i, fatia in enumerate(trechos.fatiar(doc.text, titulo)):
        bruto = doc.text[fatia.char_start:fatia.char_end]
        saida.append(Chunk(
            doc.name, doc.path, i, bruto,
            chunk_id=trechos.chunk_id(versao, fatia.char_start),
            char_start=fatia.char_start, char_end=fatia.char_end,
            pagina_inicio=pagina_de(paginas, fatia.char_start),
            pagina_fim=pagina_de(paginas, max(fatia.char_start, fatia.char_end - 1)),
            regime=fatia.regime,
            text_embed=(fatia.caminho + "\n" if fatia.caminho else "") + bruto,
        ))
    return saida


# O que a pessoa da vez pode ver do Acervo (Servicos por colaborador,
# src/servicos_acesso.py): um predicado sobre o caminho do arquivo, posto por
# requisicao. Sem ele (a janela do servidor, o titular, as tarefas de fundo),
# o Acervo inteiro.
FILTRO: ContextVar = ContextVar("paulus_filtro_do_acervo", default=None)


class ContractSearcher:
    """Indice BM25 sobre os trechos de todos os contratos carregados."""

    def __init__(self, *, estrutural: bool = False, lexico=None, filtravel: bool = False) -> None:
        self._trechos: list[Chunk] = []
        self._documentos: list[Document] = []
        # So o Acervo e filtrado por pessoa; o material de consulta nao.
        self.filtravel = filtravel
        self._bm25 = None
        self._termos: list[set[str]] = []
        # I5: trechos pela estrutura (clausula, secao, artigo) em vez de
        # blocos de 1.200 caracteres. Chave `ia.trechos_estruturais`.
        self.estrutural = estrutural
        # I6: o indice lexico em SQLite FTS5 (src/lexico.py), no lugar do
        # rank_bm25 - so com trechos estruturais, que tem id estavel. Chave
        # `ia.lexico_fts`.
        self.lexico = lexico
        self._pronto = False

    # O que se le de fora passa pelo filtro da pessoa da vez; o indice por
    # dentro (build, pontuacao) usa sempre a lista inteira.
    def _filtro(self):
        return FILTRO.get() if self.filtravel else None

    @property
    def documents(self) -> list[Document]:
        f = self._filtro()
        return self._documentos if f is None else [d for d in self._documentos if f(d.path)]

    @documents.setter
    def documents(self, valor: list[Document]) -> None:
        self._documentos = valor

    @property
    def chunks(self) -> list[Chunk]:
        f = self._filtro()
        return self._trechos if f is None else [c for c in self._trechos if f(c.doc_path)]

    @chunks.setter
    def chunks(self, valor: list[Chunk]) -> None:
        self._trechos = valor

    def add_contracts(self, docs: list[Document]) -> None:
        self._documentos.extend(docs)
        fatiar = chunk_estrutural if self.estrutural else chunk_document
        for doc in docs:
            self._trechos.extend(fatiar(doc))
        self._bm25 = None  # invalida o indice
        self._pronto = False

    def build(self) -> None:
        try:
            from rank_bm25 import BM25Okapi
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "rank-bm25 nao instalado. Rode: pip install -r requirements.txt"
            ) from exc

        if not self._trechos:
            self._bm25 = None
            self._pronto = False
            return

        # O texto com o caminho na frente, quando o trecho tem: "Contrato ACME >
        # CLAUSULA 9a" faz a busca achar a clausula pelo nome do documento.
        corpus = [tokenize(c.text_embed or c.text) for c in self._trechos]
        self._termos = [set(t) for t in corpus]
        self._por_id = {c.chunk_id: i for i, c in enumerate(self._trechos) if c.chunk_id}
        if self._usa_lexico():
            self.lexico.sincronizar(self._trechos)
            self._pronto = True
            return
        self._bm25 = BM25Okapi(corpus)
        self._pronto = True

    def _usa_lexico(self) -> bool:
        return self.lexico is not None and bool(self._trechos) and all(c.chunk_id for c in self._trechos)

    def caracteres(self) -> int:
        """Quanto texto o acervo inteiro tem."""
        return sum(len(c.text) for c in self.chunks)

    def cabe_inteiro(self, orcamento: int) -> bool:
        """Se dá para ler tudo sem escolher."""
        total = self.caracteres()
        return 0 < total <= orcamento

    def tudo(self) -> list[Hit]:
        """
        O acervo inteiro, na ordem em que está escrito.

        Escolher trecho é o que se faz quando não dá para ler tudo. Com seis
        documentos e vinte e quatro mil caracteres, dava — e o programa
        escolhia mesmo assim, lendo três de seis e respondendo "não encontrei
        essa informação" sobre um documento que nunca abriu.

        Sem pontuação de relevância aqui: não há relevância a medir quando
        tudo entra.
        """
        return [Hit(chunk, 0.0, chunk.text[:200]) for chunk in self.chunks]

    def do_documento(self, nome: str) -> list[Hit]:
        """Os trechos de um documento só, na ordem em que estão escritos."""
        return self.dos_documentos([nome])

    def dos_documentos(self, nomes) -> list[Hit]:
        """
        Os trechos de alguns documentos, na ordem em que estão escritos.

        Para quando a pergunta é sobre arquivos determinados — anexados,
        nomeados ou em foco. Ler o acervo inteiro nesse caso fazia o documento
        citado virar uma fração do contexto — 937 de 27.213 caracteres, medido
        — e a resposta saía sobre os outros.

        A ordem é a dos nomes pedidos, e não a do acervo: quem anexou dois
        arquivos espera o primeiro primeiro.
        """
        quais = [n for n in (nomes or []) if n]
        if not quais:
            return []
        por_nome: dict[str, list[Hit]] = {n: [] for n in quais}
        for c in self.chunks:
            if c.doc_name in por_nome:
                por_nome[c.doc_name].append(Hit(c, 0.0, c.text[:200]))
        return [h for n in quais for h in por_nome[n]]

    def quantos_cabem(self, orcamento: int) -> int:
        """Quantos trechos cabem no orçamento, pelo tamanho médio deles."""
        if not self.chunks:
            return 0
        medio = max(1, self.caracteres() // len(self.chunks))
        return max(4, min(len(self.chunks), orcamento // medio))

    def search(self, query: str, top_k: int = 5, per_doc_limit: int = 2, documentos=None) -> list[Hit]:
        """
        Retorna os melhores trechos para a pergunta.

        `per_doc_limit` evita que um unico contrato ocupe todos os slots de
        contexto - com 10 contratos, o usuario quase sempre quer comparar.
        `documentos` restringe a busca a estes arquivos ANTES de ordenar.
        """
        if not self._pronto:
            self.build()
        if not self._pronto:
            return []

        tokens = tokenize(query)
        if not tokens:
            return []

        so = set(n for n in (documentos or []) if n)
        if self._usa_lexico():
            scores = [0.0] * len(self._trechos)
            for cid, escore in self.lexico.buscar(query, max(50, top_k * 4), list(so)):
                i = self._por_id.get(cid)
                if i is not None:
                    scores[i] = escore
        else:
            scores = list(self._bm25.get_scores(tokens))
            if so:
                scores = [s if self._trechos[i].doc_name in so else 0.0 for i, s in enumerate(scores)]
        filtro = self._filtro()
        if filtro is not None:
            scores = [s if filtro(self._trechos[i].doc_path) else 0.0 for i, s in enumerate(scores)]
        hits: list[Hit] = []
        por_doc: dict[str, int] = {}
        usados: set[int] = set()

        def colher(pontuacoes) -> None:
            ordem = sorted(range(len(pontuacoes)), key=lambda i: pontuacoes[i], reverse=True)
            for i in ordem:
                if len(hits) >= top_k:
                    return
                if pontuacoes[i] <= 0 or i in usados:
                    continue
                chunk = self._trechos[i]
                if por_doc.get(chunk.doc_name, 0) >= per_doc_limit:
                    continue
                por_doc[chunk.doc_name] = por_doc.get(chunk.doc_name, 0) + 1
                usados.add(i)
                hits.append(Hit(chunk, float(pontuacoes[i]), _extract_snippet(chunk.text, tokens)))

        colher(scores)

        # O IDF do BM25 so e positivo para termos presentes em menos da metade
        # dos trechos. Com poucos contratos indexados, quase tudo zera e a
        # busca devolve um ou nenhum resultado - mesmo com o termo no texto.
        # Quando falta trecho, completamos por contagem de termos presentes.
        if len(hits) < top_k:
            presenca = self._scores_por_presenca(tokens)
            if so:
                presenca = [s if self._trechos[i].doc_name in so else 0.0 for i, s in enumerate(presenca)]
            if filtro is not None:
                presenca = [s if filtro(self._trechos[i].doc_path) else 0.0 for i, s in enumerate(presenca)]
            colher(presenca)

        return hits

    def _scores_por_presenca(self, tokens: list[str]) -> list[float]:
        """Quantos termos distintos da busca aparecem em cada trecho."""
        procurados = set(tokens)
        return [float(len(procurados & termos)) for termos in self._termos]

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

        blocos: list[tuple[str, str]] = []
        for doc_name, chunks in por_doc.items():
            unicos = {c.index: c for c in chunks}
            ordenados = [unicos[i] for i in sorted(unicos)]
            blocos.append((doc_name, merge_chunks(ordenados)))

        cabecalho = sum(len(f"--- {n} ---\n\n\n") for n, _ in blocos)
        sobra = max_chars - cabecalho
        if sum(len(t) for _, t in blocos) <= sobra:
            return "\n\n".join(f"--- {n} ---\n{t}" for n, t in blocos)

        # Não cabendo tudo, cada documento cede o mesmo tanto — e nenhum fica
        # de fora. Encher com os primeiros até estourar fazia os últimos
        # sumirem sem aviso: quatro contratos entravam inteiros e dois nunca
        # chegavam ao modelo, que respondia sobre o acervo inteiro tendo visto
        # dois terços dele.
        #
        # O orçamento continua valendo ao pé da letra: passar dele é a janela
        # do modelo cortar por conta própria, e aí o corte é em lugar
        # arbitrário e sem ninguém saber.
        AVISO = "\n[…cortado para caber na leitura…]"
        MINIMO = 120                      # abaixo disso o pedaço não diz nada

        # Com documentos demais para o orçamento, nem todos cabem nem no
        # mínimo. Aí a resposta é dizer quais ficaram de fora — o modelo
        # precisa saber que não viu tudo, senão responde como se tivesse
        # visto, que foi o problema o tempo inteiro.
        cabem = max(1, sobra // MINIMO)
        de_fora = [n for n, _ in blocos[cabem:]]
        blocos = blocos[:cabem]

        # A linha do aviso também ocupa espaço, e o orçamento é para tudo.
        linha_de_fora = ("[não coube nesta leitura: " + ", ".join(de_fora) + "]\n\n"
                         if de_fora else "")
        sobra -= len(linha_de_fora)

        fatia = max(0, sobra // max(1, len(blocos)))
        partes = []
        for nome, texto in blocos:
            if len(texto) <= fatia:
                partes.append(f"--- {nome} ---\n{texto}")
            else:
                partes.append(f"--- {nome} ---\n{texto[:max(0, fatia - len(AVISO))]}{AVISO}")

        montado = linha_de_fora + "\n\n".join(partes)
        return montado[:max_chars]


def merge_chunks(chunks: list[Chunk]) -> str:
    """Remonta trechos de um mesmo contrato, removendo a sobreposicao."""
    if not chunks:
        return ""

    texto = chunks[0].text
    for anterior, atual in zip(chunks, chunks[1:]):
        if atual.index != anterior.index + 1:
            texto += "\n\n[...]\n\n" + atual.text
            continue
        if atual.char_end and anterior.char_end:
            # Trecho estrutural: a sobreposicao se sabe pela posicao no texto,
            # sem adivinhar pelo conteudo.
            corte = max(0, anterior.char_end - atual.char_start)
            texto += "\n" + atual.text[corte:].lstrip()
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
