"""
A ponte doutrina ↔ lei: o Código anotado pela biblioteca do escritório (M3).

Quando o escritório põe um livro de doutrina no PAULUS, cada artigo de lei
que o livro cita passa a ter, ao lado, o que aquele autor diz sobre ele, com
página. Na tela do artigo: "Na biblioteca do escritório: Brandão, p. 7". Na
pergunta que cita o artigo, os trechos que o comentam entram na busca.

Três regras, todas para não ligar errado - uma ligação errada põe a opinião
de um autor ao lado do artigo que ele não comentou:

- **Sem instrumento, não liga.** "Como visto no art. 18", sozinho, não vira
  anotação do art. 18 do CDC, mesmo num livro de consumidor. É a regra do
  cabeçalho de src/inteligencia/extratores/regras_leis.py: completar seria
  adivinhar a norma.
- **A frase é conferida no texto do arquivo** (src/inteligencia/alinhar.py).
  Anotação cuja frase não casa não é gravada - e a página é a da frase, não a
  do começo do trecho.
- **Tirar o material tira as anotações dele.**

A base é `<pasta do material>/biblioteca.db`, separada do Acervo e das leis.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from pathlib import Path

import leis as leis_mod

TRECHO_NA_TELA = 300
RE_NUMERO = re.compile(r"^(\d{1,3}(?:\.\d{3})+|\d+)(?:[\-‐-―]([A-Z]{1,2}))?")


def ordem_do_artigo(artigo: str) -> int:
    """'54-A' -> a mesma ordem que src/leis.py dá ao art. 54-A (é por ela que se acha o artigo guardado)."""
    m = RE_NUMERO.match((artigo or "").strip().upper())
    if not m:
        return 0
    return leis_mod._ordem(m.group(1), "-" + m.group(2) if m.group(2) else "")


def numero_legivel(artigo: str) -> str:
    """'6' -> '6º' (até o 9 o artigo é ordinal, como no texto da lei); '18' -> '18'."""
    m = RE_NUMERO.match((artigo or "").strip().upper())
    if not m:
        return artigo
    base = m.group(1)
    return (base + "º" if base.isdigit() and int(base) < 10 else base) + (f"-{m.group(2)}" if m.group(2) else "")


def frase_em_volta(texto: str, inicio: int, fim: int) -> str:
    """A frase do texto que contém [inicio, fim) - sem cortar em "art." -, até ~300 caracteres."""
    from citacoes import _frases

    pos = 0
    for frase in _frases(texto):
        if pos <= inicio < pos + len(frase):
            limpa = " ".join(frase.split())
            if len(limpa) <= TRECHO_NA_TELA:
                return limpa
            # Frase longa: a janela em volta da citação.
            rel = inicio - pos
            corpo = frase[max(0, rel - 120):rel + 180]
            return " ".join(corpo.split())
        pos += len(frase)
    return " ".join(texto[max(0, inicio - 120):fim + 180].split())


class Anotacoes:
    def __init__(self, caminho: Path | str) -> None:
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self._trava = threading.Lock()
        self._con = sqlite3.connect(str(self.caminho), check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._con.execute("PRAGMA journal_mode=WAL")
        self._con.executescript("""
            CREATE TABLE IF NOT EXISTS anotacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id TEXT NOT NULL,
                instrument_id TEXT NOT NULL,
                codigo TEXT NOT NULL DEFAULT '',
                artigo TEXT NOT NULL,
                ordem INTEGER NOT NULL,
                chunk_id TEXT NOT NULL,
                pagina INTEGER,
                quote TEXT NOT NULL,
                inicio INTEGER NOT NULL DEFAULT 0,
                fim INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_anotacao_artigo ON anotacoes(instrument_id, ordem);
            CREATE INDEX IF NOT EXISTS idx_anotacao_material ON anotacoes(material_id);
            CREATE TABLE IF NOT EXISTS versoes (material_id TEXT PRIMARY KEY, versao TEXT NOT NULL);
        """)
        self._con.commit()

    def fechar(self) -> None:
        with self._trava:
            self._con.close()

    # ------------------------------------------------------------ montar

    @staticmethod
    def anotar(item: dict, texto: str, chunks) -> list[dict]:
        """As anotações de um material: cada citação com instrumento, conferida no texto do arquivo."""
        from inteligencia import alinhar
        from inteligencia.extratores import regras_leis
        from inteligencia.texto import mapa_de_paginas, pagina_de

        paginas = mapa_de_paginas(texto)
        saida: list[dict] = []
        por_chave: dict[tuple, int] = {}
        for chunk in chunks:
            # A quebra de linha do PDF no meio da frase ("art. 421 do Código⏎
            # Civil") vira espaço - do mesmo tamanho, as posições ficam. Sem
            # isso, a sigla ficava na linha de baixo e a citação perdia o
            # código (e, sem código, a regra é não ligar).
            plano = re.sub(r"(?<!\n)\n(?!\n)", " ", chunk.text)
            # A frase é conferida no pedaço do arquivo de onde o trecho saiu, e
            # não no arquivo inteiro: o título "4.1 O art. 18 do CDC" também
            # está no sumário, e a página seria a do sumário.
            inicio_regiao = max(0, chunk.char_start - 40)
            regiao = texto[inicio_regiao:chunk.char_end + 40]
            for achado in regras_leis.achar(plano):
                d = achado["dados"]
                if d.get("kind") != "article" or not d.get("instrument_id"):
                    continue
                ordem = ordem_do_artigo(d.get("article", ""))
                if not ordem:
                    continue
                quote = frase_em_volta(plano, achado["inicio"], achado["fim"])
                conf = alinhar.conferir(regiao, quote)
                if not conf.achou:
                    continue
                linha = {
                    "material_id": item["id"], "instrument_id": d["instrument_id"],
                    "codigo": leis_mod.CODIGO_DO_INSTRUMENTO.get(d["instrument_id"], ""),
                    "artigo": numero_legivel(d.get("article", "")), "ordem": ordem, "chunk_id": chunk.chunk_id,
                    "pagina": pagina_de(paginas, inicio_regiao + conf.char_start) or chunk.pagina_inicio,
                    "quote": quote, "inicio": inicio_regiao + conf.char_start, "fim": inicio_regiao + conf.char_end,
                }
                chave = (chunk.chunk_id, d["instrument_id"], ordem)
                if chave in por_chave:
                    # O mesmo artigo duas vezes no trecho: fica a frase mais
                    # longa - o título da seção diz menos que a frase do texto.
                    if len(quote) > len(saida[por_chave[chave]]["quote"]):
                        saida[por_chave[chave]] = linha
                    continue
                por_chave[chave] = len(saida)
                saida.append(linha)
        return saida

    def sincronizar(self, materiais: list[tuple[dict, str, list]]) -> dict:
        """
        Deixa as anotações iguais aos materiais de agora: o que saiu, sai; o
        que mudou (outra versão dos trechos), é anotado de novo; o resto fica.
        """
        vivos = {item["id"]: (item, texto, chunks) for item, texto, chunks in materiais}
        with self._trava:
            guardadas = dict(self._con.execute("SELECT material_id, versao FROM versoes").fetchall())
        sairam = [m for m in guardadas if m not in vivos]
        refazer = []
        for id_, (item, texto, chunks) in vivos.items():
            versao = "|".join(sorted({(c.chunk_id or "").split("_")[1] for c in chunks if c.chunk_id})) or "0"
            if guardadas.get(id_) != versao:
                refazer.append((id_, versao, item, texto, chunks))
        novas = {id_: self.anotar(item, texto, chunks) for id_, _, item, texto, chunks in refazer}
        with self._trava:
            for id_ in sairam + [r[0] for r in refazer]:
                self._con.execute("DELETE FROM anotacoes WHERE material_id = ?", (id_,))
                self._con.execute("DELETE FROM versoes WHERE material_id = ?", (id_,))
            for id_, versao, *_ in refazer:
                self._con.executemany(
                    "INSERT INTO anotacoes (material_id, instrument_id, codigo, artigo, ordem, chunk_id, pagina, quote,"
                    " inicio, fim) VALUES (:material_id, :instrument_id, :codigo, :artigo, :ordem, :chunk_id, :pagina,"
                    " :quote, :inicio, :fim)", novas[id_])
                self._con.execute("INSERT INTO versoes (material_id, versao) VALUES (?, ?)", (id_, versao))
            self._con.commit()
        return {"sairam": len(sairam), "anotados": len(refazer),
                "anotacoes": sum(len(v) for v in novas.values())}

    # ------------------------------------------------------------ ler

    def do_artigo(self, codigo: str, numero: str) -> list[dict]:
        """As anotações de um artigo guardado em src/leis.py ("cdc", "18")."""
        instrumento = leis_mod.INSTRUMENTO.get(codigo, "")
        ordem = ordem_do_artigo(str(numero).replace("º", "").replace("°", ""))
        return self.por_instrumento(instrumento, ordem) if instrumento and ordem else []

    def por_instrumento(self, instrument_id: str, ordem: int) -> list[dict]:
        with self._trava:
            linhas = self._con.execute(
                "SELECT * FROM anotacoes WHERE instrument_id = ? AND ordem = ? ORDER BY material_id, pagina, inicio",
                (instrument_id, ordem)).fetchall()
        return [dict(l) for l in linhas]

    def chunks_do_dispositivo(self, instrument_id: str, ordem: int) -> list[str]:
        """Os trechos que comentam o artigo, na ordem em que aparecem - a terceira lista da RRF."""
        return list(dict.fromkeys(a["chunk_id"] for a in self.por_instrumento(instrument_id, ordem)))

    def do_material(self, material_id: str) -> list[dict]:
        with self._trava:
            return [dict(l) for l in self._con.execute(
                "SELECT * FROM anotacoes WHERE material_id = ? ORDER BY ordem, pagina", (material_id,)).fetchall()]

    def contagem(self) -> dict[str, dict]:
        """Por código: quantos artigos têm anotação, quantas anotações, e os mais comentados."""
        with self._trava:
            linhas = self._con.execute(
                "SELECT codigo, artigo, ordem, COUNT(*) AS n, COUNT(DISTINCT material_id) AS obras FROM anotacoes "
                "WHERE codigo != '' GROUP BY codigo, ordem ORDER BY codigo, n DESC, ordem").fetchall()
        saida: dict[str, dict] = {}
        for l in linhas:
            c = saida.setdefault(l["codigo"], {"artigos": 0, "anotacoes": 0, "mais_comentados": []})
            c["artigos"] += 1
            c["anotacoes"] += l["n"]
            if len(c["mais_comentados"]) < 8:
                c["mais_comentados"].append({"artigo": l["artigo"], "anotacoes": l["n"], "obras": l["obras"]})
        return saida

    def remover_material(self, material_id: str) -> None:
        with self._trava:
            self._con.execute("DELETE FROM anotacoes WHERE material_id = ?", (material_id,))
            self._con.execute("DELETE FROM versoes WHERE material_id = ?", (material_id,))
            self._con.commit()

    def total(self) -> int:
        with self._trava:
            return int(self._con.execute("SELECT COUNT(*) FROM anotacoes").fetchone()[0])
