"""
O indice lexico persistente do Acervo, em SQLite FTS5 (I6).

O BM25 de antes (rank_bm25) vivia na memoria e era refeito do zero a cada
abertura do programa - com o acervo inteiro tokenizado de novo. Aqui o
indice fica em disco, na pasta de dados, e e incremental por versao do
documento: arquivo que nao mudou nao e reindexado; arquivo que saiu, sai do
indice.

**Uma unica normalizacao para indexar e para consultar.** E a regra que mais
importa: se o texto vira "art 300" e a pergunta vira "art. 300", nada casa, e
ninguem ve o erro - a busca so devolve menos. `normalizar` reaproveita
`normalize` e `radical` de src/search.py e acrescenta o que a escrita
juridica tem de proprio:

    art. 300          -> art 300
    §1º               -> par 1
    13.105/2015       -> 13105 2015
    S. 331 TST        -> sumula 331 tst

O tokenizador do FTS5 e `unicode61 remove_diacritics 2` sobre o texto ja
normalizado (sem acento, minusculo, no singular): ele so separa as palavras.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from pathlib import Path

from search import STOPWORDS_PT, normalize, radical

# ------------------------------------------------------------ normalizacao

_TRIBUNAIS = r"(tst|stj|stf|tse|stm|tnu|trf\s?\d|trt\s?\d{1,2}|tj[a-z]{2})"

_TROCAS = [
    # Sumula: "S. 331 TST", "Sum. 331 do TST", "sumula 331 do TST" -> "sumula 331 tst".
    (re.compile(r"\b(?:s|sum|sumula)\.?\s*(?:n[º°o]\.?\s*)?(\d+)\s*(?:do|da|de)?\s*" + _TRIBUNAIS + r"\b"),
     lambda m: f" sumula {m.group(1)} {m.group(2).replace(' ', '')} "),
    # Artigo: "art. 300", "arts. 5", "artigo 300" -> "art 300".
    (re.compile(r"\bart(?:igo)?s?\.?\s*(\d+)"), lambda m: f" art {m.group(1)} "),
    # Paragrafo: "§1º", "§ 2o", "§§ 1º" -> "par 1"; "paragrafo unico" -> "par unico".
    (re.compile(r"§+\s*(\d+)"), lambda m: f" par {m.group(1)} "),
    (re.compile(r"\bparagrafo\s+unico\b"), lambda m: " par unico "),
    (re.compile(r"\bparagrafo\s+(\d+)"), lambda m: f" par {m.group(1)} "),
    # Numero com ponto de milhar e barra de ano: "13.105/2015" -> "13105 2015".
    (re.compile(r"(?<=\d)\.(?=\d{3}\b)"), lambda m: ""),
    (re.compile(r"(?<=\d)/(?=\d)"), lambda m: " "),
    # Ordinal colado: "1º", "2ª" -> "1", "2" (o NFKD ja fez deles "1o", "2a").
    (re.compile(r"(?<=\d)[°oa]\b"), lambda m: ""),
]


def normalizar(texto: str) -> str:
    """
    O texto como o indice o guarda - e como a consulta tem de chegar.

    Palavras sem acento, minusculas e no singular; numeros inteiros mantidos,
    mesmo de um digito (o "5" de "art. 5" e o que a pergunta procura);
    stopwords fora.
    """
    # `normalize` (NFKD) ja troca "º" por "o" e "ª" por "a".
    t = normalize(texto or "")
    for padrao, troca in _TROCAS:
        t = padrao.sub(troca, t)
    termos = []
    for token in re.findall(r"[a-z0-9]+", t):
        if token in STOPWORDS_PT:
            continue
        if not token.isdigit() and len(token) < 2:
            continue
        termos.append(token if token.isdigit() else radical(token))
    return " ".join(termos)


def _consulta_fts(texto: str) -> str:
    """Os termos da pergunta em OU, cada um entre aspas (nada vira operador do FTS5)."""
    termos = list(dict.fromkeys(normalizar(texto).split()))
    return " OR ".join(f'"{t}"' for t in termos)


# -------------------------------------------------------------- o indice

class IndiceLexico:
    """
    O FTS5 do Acervo. Um arquivo SQLite; uma linha por trecho estrutural
    (src/trechos.py), identificada pelo `chunk_id` - que ja carrega a versao.
    """

    def __init__(self, caminho: Path | str) -> None:
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self._trava = threading.Lock()
        self._con = sqlite3.connect(str(self.caminho), check_same_thread=False)
        self._con.execute("PRAGMA journal_mode=WAL")
        self._con.executescript("""
            CREATE TABLE IF NOT EXISTS versoes (versao TEXT PRIMARY KEY, documento TEXT NOT NULL);
            CREATE VIRTUAL TABLE IF NOT EXISTS trechos USING fts5(
                chunk_id UNINDEXED, versao UNINDEXED, documento UNINDEXED, texto,
                tokenize = 'unicode61 remove_diacritics 2');
        """)
        self._con.commit()

    @staticmethod
    def versao_do(chunk_id: str) -> str:
        partes = (chunk_id or "").split("_")
        return partes[1] if len(partes) >= 3 else ""

    def sincronizar(self, chunks) -> dict:
        """
        Deixa o indice igual aos trechos de agora, mexendo so no que mudou.

        Devolve quantas versoes entraram, sairam e ficaram - para medir que
        abrir o programa de novo nao reindexa nada.
        """
        por_versao: dict[str, list] = {}
        for c in chunks:
            if c.chunk_id:
                por_versao.setdefault(self.versao_do(c.chunk_id), []).append(c)
        with self._trava:
            guardadas = dict(self._con.execute("SELECT versao, documento FROM versoes").fetchall())
            sairam = [v for v in guardadas if v not in por_versao]
            entraram = [v for v in por_versao if v not in guardadas]
            renomeadas = [v for v in por_versao if v in guardadas and guardadas[v] != por_versao[v][0].doc_name]
            for v in sairam + renomeadas:
                self._con.execute("DELETE FROM trechos WHERE versao = ?", (v,))
                self._con.execute("DELETE FROM versoes WHERE versao = ?", (v,))
            for v in entraram + renomeadas:
                itens = por_versao[v]
                self._con.executemany(
                    "INSERT INTO trechos (chunk_id, versao, documento, texto) VALUES (?, ?, ?, ?)",
                    [(c.chunk_id, v, c.doc_name, normalizar(c.text_embed or c.text)) for c in itens])
                self._con.execute("INSERT INTO versoes (versao, documento) VALUES (?, ?)", (v, itens[0].doc_name))
            self._con.commit()
        return {"entraram": len(entraram) + len(renomeadas), "sairam": len(sairam),
                "ficaram": len(por_versao) - len(entraram) - len(renomeadas)}

    def buscar(self, consulta: str, limite: int = 50, documentos=None) -> list[tuple[str, float]]:
        """
        (chunk_id, escore) dos melhores trechos, do melhor para o pior.

        `documentos` restringe a busca ANTES de ordenar: os 50 melhores de
        dois contratos, e nao os dois contratos que sobraram entre os 50
        melhores do acervo. Empate no escore desempata pelo id: a mesma
        consulta, a mesma ordem, sempre.
        """
        expressao = _consulta_fts(consulta)
        if not expressao:
            return []
        sql = "SELECT chunk_id, bm25(trechos) FROM trechos WHERE trechos MATCH ?"
        args: list = [expressao]
        nomes = [n for n in (documentos or []) if n]
        if nomes:
            sql += " AND documento IN (" + ",".join("?" * len(nomes)) + ")"
            args += nomes
        sql += " ORDER BY bm25(trechos), chunk_id LIMIT ?"
        args.append(int(limite))
        with self._trava:
            try:
                linhas = self._con.execute(sql, args).fetchall()
            except sqlite3.OperationalError:
                return []
        # O bm25 do FTS5 e negativo (menor = melhor); a busca do programa
        # trabalha com escore positivo.
        return [(cid, -float(escore)) for cid, escore in linhas]

    def quantos(self) -> int:
        with self._trava:
            return int(self._con.execute("SELECT count(*) FROM trechos").fetchone()[0])

    def fechar(self) -> None:
        with self._trava:
            self._con.close()
