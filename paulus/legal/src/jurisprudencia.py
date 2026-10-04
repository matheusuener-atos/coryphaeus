"""
Jurisprudência em massa: os acórdãos do STJ no computador (docs/PLANO-PILOTO.md, N13).

A primeira volta deixou de fora de propósito; o dono decidiu fazer. Do jeito
da casa:

- **De onde**: os "espelhos de acórdãos" do Portal de Dados Abertos do STJ
  (licença CC-BY), um conjunto por órgão julgador - a Corte Especial, as três
  Seções e as seis Turmas -, com a ementa, a decisão, a tese, o tema e as
  referências legislativas de cada acórdão desde 2022 (e o histórico de
  antes, no arquivo base de cada órgão).
- **Desligado de fábrica**: nada é baixado até a pessoa escolher os órgãos e
  pedir, na Biblioteca. O que sai deste computador é só o pedido dos arquivos
  públicos ao portal do STJ (nenhum dado do escritório). "Atualizar" baixa só
  os meses novos.
- **No computador**: um SQLite à parte (`<dados>/jurisprudencia/stj.db`), com
  a busca de texto do SQLite (FTS5, sem acento) e, para cada acórdão, os
  artigos que ele cita ("LEI:010406 ANO:2002 ... ART:00206" vira `cc:206`) -
  é o que liga o acórdão ao artigo na conversa e no editor.
- **Sem modelo**: a busca é por palavras; o que a tela mostra é a ementa
  oficial, com o processo, o relator e as datas.
"""

from __future__ import annotations

import io
import json
import re
import sqlite3
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel

CKAN = "https://dadosabertos.web.stj.jus.br/api/3/action/package_show?id=espelhos-de-acordaos-{slug}"
LICENCA = "Portal de Dados Abertos do STJ, espelhos de acórdãos (Creative Commons Atribuição)"
# O órgão, o nome, o ramo que ele julga e o tamanho do download (medido em 30/09/2026).
ORGAOS = {
    "corte-especial": ("Corte Especial", "uniformização entre as Seções", 24),
    "primeira-secao": ("Primeira Seção", "direito público", 35),
    "primeira-turma": ("Primeira Turma", "direito público", 107),
    "segunda-turma": ("Segunda Turma", "direito público", 163),
    "segunda-secao": ("Segunda Seção", "direito privado", 13),
    "terceira-turma": ("Terceira Turma", "direito privado", 113),
    "quarta-turma": ("Quarta Turma", "direito privado", 138),
    "terceira-secao": ("Terceira Seção", "direito penal", 17),
    "quinta-turma": ("Quinta Turma", "direito penal", 247),
    "sexta-turma": ("Sexta Turma", "direito penal", 164),
}
# A referência legislativa do STJ ("LEG:FED LEI:010406 ANO:2002") -> o código guardado no PAULUS.
CODIGOS = {("LEI", "10406", "2002"): "cc", ("LEI", "13105", "2015"): "cpc", ("LEI", "8078", "1990"): "cdc",
           ("CFB", "", "1988"): "cf", ("LEI", "5172", "1966"): "ctn", ("DEL", "5452", "1943"): "clt",
           ("DEL", "2848", "1940"): "cp", ("DEL", "3689", "1941"): "cpp", ("LEI", "8069", "1990"): "eca",
           ("LEI", "8245", "1991"): "inquilinato", ("LEI", "9503", "1997"): "ctb"}
RE_LEG = re.compile(r"LEG:\w+\s+(?P<tipo>[A-Z]{2,4}):(?P<num>[\d*]+)\s+ANO:(?P<ano>\d{4})")
RE_ART = re.compile(r"ART:0*(\d{1,4})([A-Z]{0,2})\b")
SCHEMA = """
CREATE TABLE IF NOT EXISTS acordaos (
    id TEXT PRIMARY KEY, orgao_slug TEXT, processo TEXT, registro TEXT, classe TEXT, classe_nome TEXT, orgao TEXT,
    relator TEXT, data_decisao TEXT, data_publicacao TEXT, ementa TEXT, decisao TEXT, tese TEXT, tema TEXT, info TEXT,
    referencias TEXT, artigos TEXT
);
CREATE INDEX IF NOT EXISTS idx_acordaos_data ON acordaos(data_decisao);
CREATE VIRTUAL TABLE IF NOT EXISTS busca USING fts5(ementa, info, tese, content='acordaos', content_rowid='rowid',
                                                    tokenize='unicode61 remove_diacritics 2');
CREATE TABLE IF NOT EXISTS recursos (id TEXT PRIMARY KEY, orgao_slug TEXT, nome TEXT, quantos INTEGER, quando TEXT);
"""


def artigos_das_referencias(refs) -> list[str]:
    """["cc:206", "cpc:85"]: os artigos dos códigos guardados que o acórdão cita."""
    saida = []
    for bloco in refs or []:
        for m in RE_LEG.finditer(str(bloco)):
            num = m.group("num").lstrip("0") if "*" not in m.group("num") else ""
            codigo = CODIGOS.get((m.group("tipo"), num, m.group("ano")))
            if not codigo:
                continue
            fim = str(bloco).find("LEG:", m.end())
            trecho = str(bloco)[m.end(): fim if fim > 0 else None]
            for a in RE_ART.finditer(trecho):
                chave = f"{codigo}:{int(a.group(1))}{('-' + a.group(2)) if a.group(2) else ''}"
                if chave not in saida:
                    saida.append(chave)
    return saida[:60]


def _data(bruto: str) -> str:
    s = re.sub(r"\D", "", str(bruto or ""))[:8]
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 else ""


def _publicacao(bruto: str) -> str:
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", str(bruto or ""))
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""


def _juntar(v) -> str:
    if isinstance(v, list):
        return "\n".join(str(x) for x in v if x)
    return str(v or "")


def _baixar_padrao(url: str) -> bytes:
    import requests

    r = requests.get(url, timeout=300, headers={"User-Agent": "PAULUS"})
    r.raise_for_status()
    return r.content


class Jurisprudencia:
    def __init__(self, pasta: Path) -> None:
        self.caminho = Path(pasta) / "jurisprudencia" / "stj.db"
        self._con: sqlite3.Connection | None = None
        self._trava = threading.Lock()
        self.andamento: dict = {"baixando": False}
        self._parar = threading.Event()
        self.baixar_fn = None  # os testes trocam o download aqui

    # ---------------------------------------------------------- a base
    def _c(self) -> sqlite3.Connection:
        if self._con is None:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            self._con = sqlite3.connect(str(self.caminho), check_same_thread=False)
            self._con.row_factory = sqlite3.Row
            self._con.executescript(SCHEMA)
        return self._con

    def instalado(self) -> bool:
        return self.caminho.exists() and self.total() > 0

    def total(self) -> int:
        if not self.caminho.exists():
            return 0
        with self._trava:
            return int(self._c().execute("SELECT COUNT(*) FROM acordaos").fetchone()[0])

    def estado(self) -> dict:
        por = {}
        recursos = 0
        if self.caminho.exists():
            with self._trava:
                c = self._c()
                por = {l["orgao_slug"]: l["n"] for l in c.execute("SELECT orgao_slug, COUNT(*) AS n FROM acordaos GROUP BY orgao_slug")}
                recursos = int(c.execute("SELECT COUNT(*) FROM recursos").fetchone()[0])
                ultimo = c.execute("SELECT MAX(quando) FROM recursos").fetchone()[0] or ""
        else:
            ultimo = ""
        return {"total": sum(por.values()), "por_orgao": por, "arquivos": recursos, "atualizado_em": ultimo,
                "andamento": dict(self.andamento), "licenca": LICENCA,
                "tamanho_mb": round(self.caminho.stat().st_size / 1e6, 1) if self.caminho.exists() else 0,
                "orgaos": [{"slug": k, "nome": v[0], "ramo": v[1], "download_mb": v[2], "acordaos": por.get(k, 0)} for k, v in ORGAOS.items()]}

    # ---------------------------------------------------------- baixar
    def guardar(self, slug: str, itens: list[dict]) -> int:
        novos = 0
        with self._trava:
            c = self._c()
            for x in itens:
                if not isinstance(x, dict) or not x.get("id"):
                    continue
                refs = x.get("referenciasLegislativas") or []
                cur = c.execute(
                    "INSERT OR IGNORE INTO acordaos (id, orgao_slug, processo, registro, classe, classe_nome, orgao, relator,"
                    " data_decisao, data_publicacao, ementa, decisao, tese, tema, info, referencias, artigos)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (str(x["id"]), slug, str(x.get("numeroProcesso") or ""), str(x.get("numeroRegistro") or ""),
                     str(x.get("siglaClasse") or ""), str(x.get("descricaoClasse") or ""), str(x.get("nomeOrgaoJulgador") or ""),
                     str(x.get("ministroRelator") or ""), _data(x.get("dataDecisao")), _publicacao(x.get("dataPublicacao")),
                     _juntar(x.get("ementa"))[:20000], _juntar(x.get("decisao"))[:3000], _juntar(x.get("teseJuridica"))[:3000],
                     _juntar(x.get("tema"))[:200], _juntar(x.get("informacoesComplementares"))[:4000], _juntar(refs)[:4000],
                     json.dumps(artigos_das_referencias(refs))))
                if cur.rowcount:
                    rowid = cur.lastrowid
                    l = c.execute("SELECT ementa, info, tese FROM acordaos WHERE rowid = ?", (rowid,)).fetchone()
                    c.execute("INSERT INTO busca (rowid, ementa, info, tese) VALUES (?,?,?,?)", (rowid, l["ementa"], l["info"], l["tese"]))
                    novos += 1
            c.commit()
        return novos

    def _itens_do_arquivo(self, nome: str, bruto: bytes):
        if nome.lower().endswith(".zip") or bruto[:2] == b"PK":
            with zipfile.ZipFile(io.BytesIO(bruto)) as z:
                for membro in z.namelist():
                    if membro.lower().endswith(".json"):
                        yield json.loads(z.read(membro).decode("utf-8"))
        else:
            yield json.loads(bruto.decode("utf-8"))

    def baixar(self, slugs: list[str]) -> dict:
        """Baixa os arquivos que ainda não vieram, órgão por órgão (roda em segundo plano)."""
        baixar = self.baixar_fn or _baixar_padrao
        self._parar.clear()
        self.andamento = {"baixando": True, "orgao": "", "arquivo": "", "feitos": 0, "total": 0, "novos": 0, "erro": "", "com_defeito": []}
        try:
            for slug in slugs:
                if slug not in ORGAOS or self._parar.is_set():
                    continue
                self.andamento["orgao"] = ORGAOS[slug][0]
                pacote = json.loads(baixar(CKAN.format(slug=slug)).decode("utf-8"))["result"]
                recursos = [r for r in pacote.get("resources") or [] if re.search(r"\.(json|zip)$", str(r.get("url") or ""), re.I)]
                with self._trava:
                    ja = {l[0] for l in self._c().execute("SELECT id FROM recursos")}
                faltam = [r for r in recursos if r["id"] not in ja]
                self.andamento["total"] += len(faltam)
                for r in sorted(faltam, key=lambda x: str(x.get("name") or "")):
                    if self._parar.is_set():
                        break
                    self.andamento["arquivo"] = str(r.get("name") or "")
                    n = 0
                    try:
                        for lista in self._itens_do_arquivo(str(r.get("url") or ""), baixar(r["url"])):
                            n += self.guardar(slug, lista if isinstance(lista, list) else [lista])
                    except (ValueError, zipfile.BadZipFile) as exc:
                        # O STJ às vezes publica um mês com o JSON quebrado: esse fica de fora (e é
                        # tentado de novo no próximo "Atualizar"), e o resto segue.
                        self.andamento["com_defeito"].append(f"{ORGAOS[slug][0]} · {r.get('name') or ''}: {str(exc)[:80]}")
                        self.andamento["feitos"] += 1
                        continue
                    with self._trava:
                        self._c().execute("INSERT OR REPLACE INTO recursos (id, orgao_slug, nome, quantos, quando) VALUES (?,?,?,?,?)",
                                          (r["id"], slug, str(r.get("name") or ""), n, datetime.now().isoformat(timespec="seconds")))
                        self._c().commit()
                    self.andamento["feitos"] += 1
                    self.andamento["novos"] += n
        except Exception as exc:  # noqa: BLE001 - o erro fica no andamento, para a tela
            self.andamento["erro"] = f"não consegui baixar agora: {str(exc)[:160]}"
        finally:
            self.andamento["baixando"] = False
            self.andamento["parado"] = self._parar.is_set()
        return dict(self.andamento)

    def parar(self) -> None:
        self._parar.set()

    def apagar(self) -> None:
        with self._trava:
            if self._con is not None:
                self._con.close()
                self._con = None
            if self.caminho.exists():
                self.caminho.unlink()

    # ---------------------------------------------------------- procurar
    @staticmethod
    def _consulta(termo: str, juncao: str = " AND ") -> str:
        palavras = [p for p in re.findall(r"\w+", termo or "") if len(p) > 1][:12]
        return juncao.join(f'"{p}"' for p in palavras)

    def _linha(self, l, trecho: str = "") -> dict:
        d = dict(l)
        d["artigos"] = json.loads(d.get("artigos") or "[]")
        d["citacao"] = (f"STJ, {d['classe']} {d['processo']}, rel. Min. {d['relator'].title()}, {d['orgao'].title()}, "
                        f"j. {d['data_decisao'][8:10]}/{d['data_decisao'][5:7]}/{d['data_decisao'][:4]}"
                        + (f", DJe {d['data_publicacao'][8:10]}/{d['data_publicacao'][5:7]}/{d['data_publicacao'][:4]}" if d.get("data_publicacao") else ""))
        d["link"] = f"https://processo.stj.jus.br/processo/pesquisa/?num_registro={d.get('registro') or ''}"
        if trecho:
            d["trecho"] = trecho
        return d

    def procurar(self, termo: str, *, orgao: str = "", de: str = "", ate: str = "", limite: int = 20) -> list[dict]:
        """Com todas as palavras; sem nenhum, com qualquer uma - e cada achado diz qual foi (`todas`)."""
        achados = self._procurar(self._consulta(termo), orgao, de, ate, limite)
        if achados or len(re.findall(r"\w{2,}", termo or "")) < 2:
            return [dict(a, todas=True) for a in achados]
        return [dict(a, todas=False) for a in self._procurar(self._consulta(termo, " OR "), orgao, de, ate, limite)]

    def _procurar(self, consulta: str, orgao: str, de: str, ate: str, limite: int) -> list[dict]:
        if not consulta or not self.caminho.exists():
            return []
        onde, args = ["busca MATCH ?"], [consulta]
        if orgao:
            onde.append("a.orgao_slug = ?")
            args.append(orgao)
        if de:
            onde.append("a.data_decisao >= ?")
            args.append(de)
        if ate:
            onde.append("a.data_decisao <= ?")
            args.append(ate)
        sql = ("SELECT a.*, snippet(busca, 0, '[', ']', '…', 28) AS trecho FROM busca JOIN acordaos a ON a.rowid = busca.rowid"
               f" WHERE {' AND '.join(onde)} ORDER BY bm25(busca, 1.0, 0.6, 1.2) LIMIT ?")
        with self._trava:
            try:
                linhas = self._c().execute(sql, (*args, int(limite))).fetchall()
            except sqlite3.OperationalError:
                return []
        return [self._linha(l, l["trecho"]) for l in linhas]

    def do_artigo(self, codigo: str, numero: str, limite: int = 5) -> list[dict]:
        if not self.caminho.exists():
            return []
        chave = f'"{codigo}:{str(numero).replace(".", "")}"'
        with self._trava:
            linhas = self._c().execute("SELECT * FROM acordaos WHERE artigos LIKE ? ORDER BY data_decisao DESC LIMIT ?",
                                       (f"%{chave}%", int(limite))).fetchall()
        return [self._linha(l) for l in linhas]

    def obter(self, id_: str) -> dict | None:
        if not self.caminho.exists():
            return None
        with self._trava:
            l = self._c().execute("SELECT * FROM acordaos WHERE id = ?", (str(id_),)).fetchone()
        return self._linha(l) if l else None


# ------------------------------------------------------------------ rotas

class Baixar(BaseModel):
    orgaos: list[str] = []


def montar(estado, app, dados_dir: Path) -> None:
    estado.jurisprudencia = Jurisprudencia(dados_dir)

    @app.get("/api/jurisprudencia")
    def jur_estado() -> dict:
        return dict(estado.jurisprudencia.estado(), escolhidos=(estado.prefs.dados.get("jurisprudencia") or {}).get("orgaos") or [])

    @app.post("/api/jurisprudencia/baixar")
    def jur_baixar(payload: Baixar) -> dict:
        """Começa (ou continua) o download dos órgãos escolhidos. Só os arquivos públicos do STJ saem pedidos daqui."""
        import recursos_do_plano

        recursos_do_plano.exigir(estado, "jurisprudencia_stj")
        j = estado.jurisprudencia
        slugs = [s for s in payload.orgaos if s in ORGAOS]
        if not slugs:
            raise HTTPException(status_code=400, detail="escolha pelo menos um órgão julgador")
        if j.andamento.get("baixando"):
            raise HTTPException(status_code=409, detail="já estou baixando: espere terminar ou pare")
        estado.prefs.atualizar({"jurisprudencia": {"orgaos": slugs}})
        threading.Thread(target=j.baixar, args=(slugs,), name="jurisprudencia", daemon=True).start()
        time.sleep(0.05)
        return j.estado()

    @app.post("/api/jurisprudencia/parar")
    def jur_parar() -> dict:
        estado.jurisprudencia.parar()
        return estado.jurisprudencia.estado()

    @app.delete("/api/jurisprudencia")
    def jur_apagar() -> dict:
        if estado.jurisprudencia.andamento.get("baixando"):
            raise HTTPException(status_code=409, detail="pare o download antes de apagar")
        estado.jurisprudencia.apagar()
        return estado.jurisprudencia.estado()

    @app.get("/api/jurisprudencia/procurar")
    def jur_procurar(termo: str = "", orgao: str = "", de: str = "", ate: str = "", codigo: str = "", artigo: str = "") -> dict:
        j = estado.jurisprudencia
        if codigo and artigo:
            achados = j.do_artigo(codigo, artigo, limite=20)
        else:
            achados = j.procurar(termo, orgao=orgao, de=de, ate=ate, limite=25)
        return {"acordaos": achados, "total": j.total(), "licenca": LICENCA}

    @app.get("/api/jurisprudencia/acordao/{id_}")
    def jur_acordao(id_: str) -> dict:
        a = estado.jurisprudencia.obter(id_)
        if not a:
            raise HTTPException(status_code=404, detail="acórdão não encontrado")
        return a
