"""
O material de consulta no pipeline híbrido (M1): as mesmas peças do Acervo,
em índices próprios.

Antes, o material era cortado em blocos de 1.200 caracteres e procurado por
BM25 em memória, com um filtro de cobertura de palavras. Doutrina é o texto
em que esse filtro mais falha: o autor escreve "adimplemento substancial"
onde o advogado pergunta "inadimplemento mínimo". A busca por sentido (bge-m3,
src/denso.py) foi feita para esse caso, e aqui ela passa a atender o
material.

**O material nunca entra no índice do Acervo, nem o Acervo no dele.** O
léxico e os vetores moram em `<pasta do material>/indice/`, e a busca só
enxerga os trechos do material. Pergunta de cliente continua respondida pelos
documentos do cliente.

Como um trecho entra na pergunta (a regra foi escrita antes de medir, em
docs/PROGRESSO-BIBLIOTECA.md, M1):

1. estar entre os 20 primeiros da fusão RRF (léxico 50 + denso 50);
2. ter evidência de uma das buscas - a cobertura de palavras de sempre, ou o
   cosseno com a pergunta de pelo menos `TAU`;
3. ter pelo menos 0,35 da nota RRF do melhor trecho;
4. e a pergunta não ser só nome próprio.

O corte de cada material segue o que ele é:

- **obra de consulta** (doutrina, curso, comentário): regime C, por capítulo
  e seção, sem sumário e sem cabeçalho repetido (src/trechos.py);
- **lei**: regime A, um artigo por trecho, o inciso junto do caput;
- **manual e tabela**: regime B, dentro de cada página - uma página do
  manual é uma regra, e o trecho que nasce numa página cita a página certa.
"""

from __future__ import annotations

import hashlib
import re
import threading
from pathlib import Path

import trechos
from extract import Document
from inteligencia.texto import mapa_de_paginas, pagina_de
from lexico import IndiceLexico
from search import Chunk, ContractSearcher, Hit, _extract_snippet, tokenize

# O cosseno mínimo para a evidência densa. Escolhido no conjunto da
# Biblioteca pela regra escrita antes de medir (docs/PROGRESSO-BIBLIOTECA.md,
# M1): o maior Recall@6 - ruído, com o ruído não maior que o da linha de
# base; no empate, o maior.
TAU = 0.625
# O mesmo corte relativo do material de antes: só entra quem chega perto do
# melhor trecho.
MIN_DA_MELHOR = 0.35
# Quantos trechos de uma mesma obra, no máximo, numa pergunta.
POR_MATERIAL = 3

RE_PAGINA = re.compile(r"\[pagina (\d+)\]")

# O regime de cada tipo da ficha (M2). Sem ficha, `regime_do_material`
# decide pelo texto.
REGIME_DO_TIPO = {
    "doutrina": trechos.REGIME_OBRA, "artigo": trechos.REGIME_OBRA,
    "manual": trechos.REGIME_PECA, "tabela": trechos.REGIME_PECA, "modelo_de_peca": trechos.REGIME_PECA,
    "lei": trechos.REGIME_LEI, "sumulas": "S",
}


def regime_do_material(texto: str, tipo: str = "") -> str:
    """O regime do corte: o da ficha, quando há; senão, pela cara do texto."""
    if tipo in REGIME_DO_TIPO:
        regime = REGIME_DO_TIPO[tipo]
        # Doutrina sem capítulo que o regime C saiba ler vai por página.
        if regime == trechos.REGIME_OBRA and not trechos.parece_obra(texto):
            return trechos.REGIME_PECA
        return regime
    if trechos.regime_de(texto) == trechos.REGIME_LEI:
        return trechos.REGIME_LEI
    if trechos.parece_obra(texto):
        return trechos.REGIME_OBRA
    return trechos.REGIME_PECA


def _paginas(texto: str) -> list[tuple[int, int]]:
    """(início, fim) de cada página no texto; sem marcas, uma faixa só."""
    marcas = list(re.finditer(r"^\[pagina \d+\][ \t]*$", texto, re.M))
    if not marcas:
        return [(0, len(texto))]
    faixas = [(0, marcas[0].start())] if texto[:marcas[0].start()].strip() else []
    for i, m in enumerate(marcas):
        faixas.append((m.start(), marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)))
    return faixas


def fatias_do_material(texto: str, regime: str, titulo: str) -> tuple[str, list[trechos.Fatia]]:
    """(o texto de onde sai cada trecho, as fatias) - as posições valem no texto guardado."""
    if regime == trechos.REGIME_OBRA:
        return trechos.limpar_obra(texto), trechos.fatiar_obra(texto, titulo)
    if regime == trechos.REGIME_LEI:
        return texto, trechos.fatiar(texto, titulo, regime=trechos.REGIME_LEI)
    if regime == "S":
        from biblioteca import sumulas

        return texto, sumulas.fatiar(texto, titulo)
    # B: dentro de cada página.
    saida: list[trechos.Fatia] = []
    for inicio, fim in _paginas(texto):
        for f in trechos.fatiar(texto[inicio:fim], titulo, regime=trechos.REGIME_PECA):
            saida.append(trechos.Fatia(f.char_start + inicio, f.char_end + inicio, f.caminho, f.regime))
    return texto, saida


def trechos_do_material(item: dict, texto: str, regime: str = "") -> list[Chunk]:
    """
    Os trechos de um material, com `chunk_id` estável: a versão sai do
    arquivo (sha1), do id do material, do regime e de onde cada fatia começa e
    termina. O mesmo arquivo dá sempre os mesmos ids; mudar o corte (outro
    regime, outra regra) muda a versão, e o índice léxico - que é por versão -
    se refaz sozinho.
    """
    regime = regime or regime_do_material(texto, (item.get("ficha") or {}).get("tipo", ""))
    titulo = (item.get("ficha") or {}).get("titulo") or re.sub(r"\.[A-Za-z0-9]{2,4}$", "", item["nome"])
    fonte, fatias = fatias_do_material(texto, regime, titulo)
    marca = "|".join(f"{f.char_start}-{f.char_end}" for f in fatias)
    versao = hashlib.sha1(f"{item.get('sha1', '')}\0{item['id']}\0{regime}\0{marca}".encode("utf-8")).hexdigest()[:12]
    paginas = mapa_de_paginas(texto)
    saida: list[Chunk] = []
    for i, f in enumerate(fatias):
        bruto = fonte[f.char_start:f.char_end]
        limpo = _limpo(bruto)
        if not limpo:
            continue
        # A pagina do fim e a do ultimo texto de verdade: o trecho que acaba
        # na virada ("[pagina 6]" e o cabecalho apagado) nao esta na 6.
        util = len(re.sub(r"(?:\s|\[pagina \d+\])+$", "", bruto))
        saida.append(Chunk(
            item["nome"], item.get("arquivo", ""), i, limpo,
            chunk_id=trechos.chunk_id(versao, f.char_start),
            char_start=f.char_start, char_end=f.char_end,
            pagina_inicio=pagina_de(paginas, f.char_start),
            pagina_fim=pagina_de(paginas, max(f.char_start, f.char_start + util - 1)),
            regime=regime,
            text_embed=(f.caminho + "\n" if f.caminho else "") + limpo,
        ))
    return saida


def _limpo(bruto: str) -> str:
    """O texto do trecho como vai para o modelo e para a busca: sem marca de página e sem o vazio do que foi tirado."""
    texto = RE_PAGINA.sub(" ", bruto)
    linhas = [" ".join(l.split()) for l in texto.splitlines()]
    saida, vazio = [], False
    for l in linhas:
        if not l:
            if not vazio and saida:
                saida.append("")
            vazio = True
            continue
        saida.append(l)
        vazio = False
    return "\n".join(saida).strip()


def onde(chunk: Chunk) -> str:
    """'página 3' ou 'páginas 3–4': o trecho que atravessa a página diz as duas."""
    a, b = chunk.pagina_inicio, chunk.pagina_fim
    if not a:
        return ""
    return f"página {a}" if not b or b == a else f"páginas {a}–{b}"


class IndiceDoMaterial:
    """
    O índice híbrido do material: FTS5 e vetores em `<pasta>/indice/`.

    `vetorizador` é uma função que devolve o `Vetorizador` do bge-m3, ou None
    quando o modelo de vetores não está instalado (ou a busca por sentido foi
    desligada): aí o material funciona só com o léxico, sem erro. `ceder` é a
    vez da fila do modelo - o backfill para enquanto alguém espera resposta.
    """

    def __init__(self, pasta: Path, *, vetorizador=None, ceder=None) -> None:
        self.pasta = Path(pasta) / "indice"
        self.lexico = IndiceLexico(self.pasta / "lexico.db")
        self.searcher = ContractSearcher(estrutural=True, lexico=self.lexico)
        self._fabrica = vetorizador
        self._ceder = ceder
        self._denso = None
        self._backfill = None
        self._vetores: dict[str, object] = {}
        self._trava = threading.Lock()

    # ------------------------------------------------------------ montar

    def montar(self, itens_e_textos: list[tuple[dict, str]]) -> dict[str, int]:
        """Refaz os trechos de todos os materiais; o FTS5 só mexe no que mudou. Devolve trechos por material."""
        chunks: list[Chunk] = []
        documentos: list[Document] = []
        por_material: dict[str, int] = {}
        for item, texto in itens_e_textos:
            deste = trechos_do_material(item, texto)
            por_material[item["id"]] = len(deste)
            chunks.extend(deste)
            documentos.append(Document(name=item["nome"], path=item.get("arquivo", ""), text=""))
        with self._trava:
            searcher = ContractSearcher(estrutural=True, lexico=self.lexico)
            searcher.documents = documentos
            searcher.chunks = chunks
            if chunks:
                searcher.build()
            else:
                self.lexico.sincronizar([])
            self.searcher = searcher
        if self._denso is not None:
            self._denso.podar(chunks)
        return por_material

    def sentido(self, esperar: bool = False):
        """(índice denso, vetorizador), com o backfill do que falta andando - ou (None, None)."""
        vetorizador = self._fabrica() if self._fabrica else None
        if vetorizador is None:
            return None, None
        from denso import Backfill, IndiceDenso

        if self._denso is None:
            self._denso = IndiceDenso(self.pasta / "densos.db")
            self._backfill = Backfill(self._denso, vetorizador, ceder=self._ceder)
        self._backfill.vetorizador = vetorizador
        self._backfill.iniciar(self.searcher.chunks)
        if esperar:
            self._backfill.esperar()
        return self._denso, vetorizador

    def fechar(self) -> None:
        """Solta os arquivos do índice (no Windows, pasta com SQLite aberto não se apaga)."""
        if self._backfill is not None:
            self._backfill.esperar(30)
        self.lexico.fechar()
        if self._denso is not None:
            self._denso.fechar()

    def estado(self) -> dict:
        denso = self._denso
        return {"trechos": len(self.searcher.chunks), "vetores": denso.quantos() if denso is not None else 0,
                "vetorizando": bool(self._backfill and self._backfill.estado.get("andando"))}

    # ------------------------------------------------------------ consultar

    def _vetor(self, pergunta: str, vetorizador):
        """O vetor da pergunta, lembrado: a conversa consulta duas vezes (a fila e a resposta)."""
        if pergunta not in self._vetores:
            if len(self._vetores) > 32:
                self._vetores.clear()
            self._vetores[pergunta] = vetorizador.vetores([pergunta])[0]
        return self._vetores[pergunta]

    def consultar(self, pergunta: str, top: int = 4, tau: float | None = None, extras=None) -> list[Hit]:
        """
        Os trechos do material para a pergunta, pela regra do cabeçalho.

        `extras` são listas a mais para a RRF - a da M3: os trechos que
        comentam o artigo que a pergunta cita. Quem está nelas já tem a
        evidência: cita o dispositivo perguntado, com o instrumento.
        """
        import recuperacao

        extras = [l for l in (extras or []) if l]
        anotados = {cid for lista in extras for cid in lista}

        tau = TAU if tau is None else tau
        searcher = self.searcher
        if not searcher.chunks:
            return []
        procurados, nomes = termos_da_pergunta(pergunta)
        if not procurados - nomes:
            return []
        lexica = [cid for cid, _ in self.lexico.buscar(pergunta, recuperacao.LEXICO_TOP)]
        densa: list[str] = []
        cossenos: dict[str, float] = {}
        denso, vetorizador = self.sentido()
        if denso is not None:
            try:
                pares = denso.buscar(self._vetor(pergunta, vetorizador), recuperacao.DENSO_TOP)
                densa = [cid for cid, _ in pares]
                cossenos = dict(pares)
            except Exception:  # noqa: BLE001 - sem o modelo de vetores agora, fica o léxico
                densa, cossenos = [], {}
        fundidos = [(cid, p) for cid, p in recuperacao.rrf([lexica, densa] + extras) if p >= recuperacao.minimo_rrf()]
        fundidos = fundidos[:recuperacao.FUNDIDOS_TOP]
        if not fundidos:
            return []
        melhor = fundidos[0][1]
        por_id = {c.chunk_id: c for c in searcher.chunks}
        termos = tokenize(pergunta)
        bons: list[Hit] = []
        contagem: dict[str, int] = {}
        for cid, ponto in fundidos:
            chunk = por_id.get(cid)
            if chunk is None or ponto < MIN_DA_MELHOR * melhor:
                continue
            if not (cid in anotados or cobre(procurados, nomes, chunk.text_embed or chunk.text)
                    or cossenos.get(cid, -1.0) >= tau):
                continue
            if contagem.get(chunk.doc_name, 0) >= POR_MATERIAL:
                continue
            contagem[chunk.doc_name] = contagem.get(chunk.doc_name, 0) + 1
            bons.append(Hit(chunk, float(ponto), _extract_snippet(chunk.text, termos)))
            if len(bons) >= top:
                break
        return bons


def termos_da_pergunta(pergunta: str) -> tuple[set[str], set[str]]:
    """
    (palavras de assunto da pergunta, as que são nome próprio).

    As palavras de pergunta ("quanto", "devemos") ficam de fora: são o jeito
    de perguntar, e não o assunto. O nome próprio conta no total e não casa -
    ver `cobre`.
    """
    from material import PALAVRAS_DE_PERGUNTA

    palavras = pergunta.split()
    nomes = set(tokenize(" ".join(p for i, p in enumerate(palavras) if i and p[:1].isupper())))
    # Nome de norma e sigla de tribunal também vêm com maiúscula, e não são
    # parte: "o que os autores dizem do art. 475 do Código Civil?" perdia
    # "código" e "civil" como se fossem nome de cliente, e a cobertura caía
    # abaixo do mínimo - a obra que comenta o art. 475 não entrava.
    return set(tokenize(pergunta)) - PALAVRAS_DE_PERGUNTA, nomes - NAO_SAO_NOMES


# As palavras com maiúscula que são do direito, e não de uma parte (já no
# formato do tokenize: sem acento, minúsculas, no singular).
NAO_SAO_NOMES = set(tokenize(
    "Código Civil Penal Processo Processual Defesa Consumidor Tributário Nacional Trânsito Constituição Federal "
    "República Consolidação Leis Trabalho Estatuto Criança Adolescente Lei Decreto Complementar Súmula Vinculante "
    "Enunciado Tribunal Justiça Superior Supremo CDC CC CPC CP CPP CLT CTN CTB ECA CF ADCT STF STJ TST TSE STM TNU "
    "TRF TRT TJ INSS Procon"))


def cobre(procurados: set[str], nomes: set[str], texto: str) -> bool:
    """
    A cobertura de palavras do material de antes (src/material.py): ao menos
    0,45 das palavras de assunto, e duas em comum quando a pergunta tem duas.
    Nome próprio não casa, mas conta no total - pergunta com nome de cliente
    é, quase sempre, sobre o documento dele.
    """
    from material import MIN_COBERTURA

    if not procurados:
        return False
    termos = set(tokenize(texto))
    radicais = {t[:6] for t in termos if len(t) >= 6}
    achados = [p for p in procurados - nomes if p in termos or (len(p) >= 6 and p[:6] in radicais)]
    return len(achados) / len(procurados) >= MIN_COBERTURA and len(achados) >= min(2, len(procurados - nomes))
