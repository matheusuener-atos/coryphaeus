"""
Tarefas de vários passos, com ponto de restauração (docs/PLANO-PILOTO.md, L4).

Uma tarefa é uma receita de passos que roda em segundo plano, com cada passo
à vista, e deixa um resultado que se abre (um relatório no editor). Duas
receitas, as do plano:

- **vencimentos**: os contratos que vencem (ou terminam a vigência) nos
  próximos N dias, pelas datas **conferidas** da leitura dos documentos
  (src/ajuda.py, `prazos`) - sem modelo. Pode propor cada data na Agenda,
  por Aprovações.
- **revisar**: um contrato contra o padrão da casa, cláusula por cláusula
  (src/redacao.py acha as cláusulas; difflib alinha e compara) - igual,
  alterada (com o que saiu e o que entrou), faltando, a mais. Só se a pessoa
  pedir, o modelo explica em uma frase cada cláusula alterada (até 6), e a
  frase vem marcada como do assistente.

**Ponto de restauração** (`Restauracao`): tudo o que a tarefa cria ou muda
fica anotado antes - o documento do relatório, os pedidos em Aprovações, as
tarefas, e os arquivos (a cópia do original, antes de mexer). "Desfazer"
volta cada coisa e diz o que não conseguiu voltar (um arquivo que alguém
mudou depois não é apagado: seria apagar trabalho de outra pessoa).
"""

from __future__ import annotations

import difflib
import hashlib
import html
import json
import re
import shutil
import threading
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel

_trava = threading.Lock()


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _sha(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


# ------------------------------------------------------------ restauração

class Restauracao:
    """O que uma tarefa fez, anotado antes, para poder desfazer."""

    def __init__(self, pasta: Path) -> None:
        self.pasta = Path(pasta)
        self.arquivo = self.pasta / "restauracao.json"
        self.itens: list[dict] = []
        if self.arquivo.exists():
            try:
                self.itens = json.loads(self.arquivo.read_text(encoding="utf-8"))
            except ValueError:
                self.itens = []

    def _gravar(self) -> None:
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.arquivo.write_text(json.dumps(self.itens, ensure_ascii=False, indent=1), encoding="utf-8")

    def documento(self, id_: int, titulo: str = "") -> None:
        self.itens.append({"tipo": "documento", "id": int(id_), "titulo": titulo})
        self._gravar()

    def pedido(self, id_: str, titulo: str = "") -> None:
        self.itens.append({"tipo": "pedido", "id": id_, "titulo": titulo})
        self._gravar()

    def tarefa(self, id_: int, titulo: str = "") -> None:
        self.itens.append({"tipo": "tarefa", "id": int(id_), "titulo": titulo})
        self._gravar()

    def arquivo_criado(self, caminho: Path) -> None:
        caminho = Path(caminho)
        self.itens.append({"tipo": "arquivo_criado", "caminho": str(caminho), "sha": _sha(caminho) if caminho.exists() else ""})
        self._gravar()

    def antes_de_alterar(self, caminho: Path) -> None:
        """Chame ANTES de mexer: guarda a cópia do original."""
        caminho = Path(caminho)
        copia = self.pasta / "originais" / f"{len(self.itens):03d}-{caminho.name}"
        copia.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(caminho, copia)
        self.itens.append({"tipo": "arquivo_alterado", "caminho": str(caminho), "copia": str(copia)})
        self._gravar()

    def depois_de_alterar(self, caminho: Path) -> None:
        for item in reversed(self.itens):
            if item["tipo"] == "arquivo_alterado" and item["caminho"] == str(caminho):
                item["sha_depois"] = _sha(Path(caminho))
                break
        self._gravar()

    def desfazer(self, estado) -> list[dict]:
        """Volta tudo, do último para o primeiro. Cada item diz o que aconteceu."""
        saida = []
        for item in reversed(self.itens):
            if item.get("desfeito"):
                continue
            t = item["tipo"]
            ok, como = True, ""
            try:
                if t == "documento":
                    ok = bool(estado.documentos.apagar(int(item["id"])))
                    como = "relatório apagado do editor" if ok else "o relatório já não estava lá"
                elif t == "pedido":
                    p = estado.fila.obter(item["id"])
                    if p is not None and p.estado == "pendente":
                        estado.fila.esquecer(item["id"])
                        como = "pedido tirado de Aprovações"
                    else:
                        ok, como = False, "o pedido já tinha sido decidido em Aprovações: o que ele fez fica"
                elif t == "tarefa":
                    ok = estado.base.escrever("DELETE FROM tarefas WHERE id = ?", (int(item["id"]),)) > 0
                    como = "tarefa apagada" if ok else "a tarefa já não estava lá"
                elif t == "arquivo_criado":
                    c = Path(item["caminho"])
                    if not c.exists():
                        ok, como = False, "o arquivo já não estava lá"
                    elif item.get("sha") and _sha(c) != item["sha"]:
                        ok, como = False, "alguém mudou o arquivo depois: ficou onde está"
                    else:
                        c.unlink()
                        como = "arquivo apagado"
                elif t == "arquivo_alterado":
                    c = Path(item["caminho"])
                    if item.get("sha_depois") and c.exists() and _sha(c) != item["sha_depois"]:
                        ok, como = False, "alguém mudou o arquivo depois: não voltei, para não perder esse trabalho"
                    else:
                        shutil.copy2(item["copia"], c)
                        como = "arquivo voltou ao original"
            except Exception as exc:  # noqa: BLE001 - o que falhou fica dito, o resto segue
                ok, como = False, f"não consegui: {exc}"
            item["desfeito"] = ok
            saida.append({"tipo": t, "titulo": item.get("titulo") or Path(item.get("caminho", "")).name, "ok": ok, "como": como})
        self._gravar()
        return saida


# ------------------------------------------------------------ as receitas

TIPOS = {
    "vencimentos": {
        "nome": "Contratos vencendo",
        "descricao": "Os contratos que vencem ou terminam a vigência nos próximos dias, pelas datas conferidas na leitura. Sem modelo.",
        "parametros": [{"id": "dias", "rotulo": "Nos próximos (dias)", "tipo": "numero", "padrao": 90},
                       {"id": "so_contratos", "rotulo": "Só contratos", "tipo": "sim_nao", "padrao": True},
                       {"id": "propor", "rotulo": "Propor cada data na Agenda (por Aprovações)", "tipo": "sim_nao", "padrao": False}],
    },
    "revisar": {
        "nome": "Revisar contra o padrão da casa",
        "descricao": "Um contrato comparado cláusula por cláusula com o modelo do escritório: igual, alterada, faltando e a mais.",
        "parametros": [{"id": "documento", "rotulo": "Contrato", "tipo": "documento", "padrao": ""},
                       {"id": "padrao", "rotulo": "Padrão da casa", "tipo": "documento", "padrao": ""},
                       {"id": "explicar", "rotulo": "O assistente explica cada cláusula alterada (mais lento)", "tipo": "sim_nao", "padrao": False}],
    },
}


class Parou(RuntimeError):
    pass


def _e(s) -> str:
    return html.escape(str(s or ""))


def _vencimentos(estado, t, passo) -> dict:
    import ajuda

    dias = max(1, min(int(t["params"].get("dias") or 90), 3650))
    so_contratos = bool(t["params"].get("so_contratos", True))
    hoje = date.today()
    ate = hoje + timedelta(days=dias)
    passo(0, "andando")
    achados = []
    for doc in list(estado.searcher.documents):
        metas, _ = estado.saber.metadados_de([doc])
        for meta in metas:
            tipo = str((meta.por_secao("classification") or {}).get("document_type") or "")
            if so_contratos and "contr" not in tipo.lower():
                continue
            for p in ajuda.prazos(meta, doc.name, hoje):
                achados.append(dict(p, tipo_documento=tipo))
    passo(0, "feito", f"{len(achados)} data(s) conferida(s) no Acervo")
    passo(1, "andando")
    no_prazo = sorted((a for a in achados if a["data"] <= ate.isoformat()), key=lambda a: a["data"])
    passo(1, "feito", f"{len(no_prazo)} até {ate:%d/%m/%Y}")
    passo(2, "andando")
    linhas = "".join(
        f"<tr><td>{_e(a['documento'])}</td><td>{_e(a['titulo'].split(' de ')[0])}</td><td>{date.fromisoformat(a['data']):%d/%m/%Y}</td>"
        f"<td>{(date.fromisoformat(a['data']) - hoje).days} dias</td><td>{_e(a.get('pagina') or '')}</td><td>“{_e(a.get('quote'))}”</td></tr>"
        for a in no_prazo)
    corpo = (f"<h1>Contratos vencendo nos próximos {dias} dias</h1>"
             f"<p>Feito em {datetime.now():%d/%m/%Y %H:%M} pela tarefa “Contratos vencendo”, a partir das datas que a leitura dos "
             f"documentos conferiu (com a página e o trecho). Documento sem data conferida não entra.</p>" +
             (f"<table><thead><tr><th>Documento</th><th>O quê</th><th>Data</th><th>Faltam</th><th>Página</th><th>Trecho</th></tr></thead>"
              f"<tbody>{linhas}</tbody></table>" if no_prazo else "<p>Nenhum vencimento nesse período.</p>"))
    doc_id = estado.documentos.criar(f"Contratos vencendo em {dias} dias — {hoje:%d/%m/%Y}", "texto", corpo)
    t["_restauracao"].documento(doc_id, "relatório")
    passo(2, "feito", "relatório no editor")
    propostos = 0
    if t["params"].get("propor") and len(t["passos"]) > 3:
        passo(3, "andando")
        for a in no_prazo:
            p = estado.fila.pedir(a["titulo"] + " — anotar?", "agenda", acao="ajuda.prazo", pedido_por="Tarefa: contratos vencendo",
                                  resumo=f"Do documento {a['documento']}: “{a.get('quote', '')}”", etiquetas=["tarefa de vários passos"],
                                  prazo=a["data"], dados={k: a.get(k) for k in ("titulo", "data", "documento", "pagina", "quote")})
            t["_restauracao"].pedido(p.id, a["titulo"])
            propostos += 1
        passo(3, "feito", f"{propostos} pedido(s) em Aprovações")
    return {"documento_id": doc_id, "quantos": len(no_prazo), "propostos": propostos,
            "itens": [{k: a.get(k) for k in ("documento", "titulo", "data", "pagina")} for a in no_prazo[:50]]}


# ---- revisar contra o padrão

RE_TAG = re.compile(r"<[^>]+>")


def _texto_de(estado, ref: str) -> tuple[str, str]:
    """(nome, texto) de um documento do Acervo pelo nome, ou do editor por "doc:<id>"."""
    ref = str(ref or "").strip()
    if ref.startswith("doc:"):
        item = estado.documentos.obter(int(ref[4:]))
        if not item:
            raise ValueError("o documento do editor não existe mais")
        texto = RE_TAG.sub("\n", str(item.get("corpo") or "").replace("</p>", "</p>\n"))
        return item.get("titulo") or "documento", html.unescape(texto)
    doc = next((d for d in estado.searcher.documents if d.name == ref), None)
    if doc is None:
        raise ValueError(f"“{ref}” não está no Acervo")
    return doc.name, doc.text


def clausulas_de(texto: str) -> list[dict]:
    import redacao

    achadas = redacao.achar_clausulas(texto)
    saida = []
    for i, a in enumerate(achadas):
        fim = achadas[i + 1]["inicio"] if i + 1 < len(achadas) else len(texto)
        bloco = texto[a["inicio"]:fim].strip()
        titulo = bloco.split("\n", 1)[0][:140]
        saida.append({"numero": a["numero"], "titulo": titulo, "texto": " ".join(bloco.split())})
    return saida


def _norm(s: str) -> str:
    import unicodedata

    s = "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))
    s = re.sub(r"\b(clausula|\d+[ªaº°o]?|primeira|segunda|terceira|quarta|quinta|sexta|setima|oitava|nona|decima)\b", " ", s)
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s).split())


def _parecido(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _norm(a), _norm(b), autojunk=False).ratio()


def alinhar(padrao: list[dict], contrato: list[dict]) -> list[dict]:
    """Cada cláusula do padrão com a do contrato que mais se parece (título pesa, texto decide); o resto fica sozinho."""
    pares = []
    for i, p in enumerate(padrao):
        for j, c in enumerate(contrato):
            nota = 0.4 * _parecido(p["titulo"], c["titulo"]) + 0.6 * _parecido(p["texto"][:1500], c["texto"][:1500])
            pares.append((nota, i, j))
    usados_p, usados_c, saida = set(), set(), []
    for nota, i, j in sorted(pares, reverse=True):
        if nota < 0.35 or i in usados_p or j in usados_c:
            continue
        usados_p.add(i)
        usados_c.add(j)
        saida.append({"padrao": padrao[i], "contrato": contrato[j], "nota": round(nota, 2)})
    for i, p in enumerate(padrao):
        if i not in usados_p:
            saida.append({"padrao": p, "contrato": None, "nota": 0})
    for j, c in enumerate(contrato):
        if j not in usados_c:
            saida.append({"padrao": None, "contrato": c, "nota": 0})
    saida.sort(key=lambda x: (x["padrao"] or x["contrato"])["numero"] + (0 if x["padrao"] else 1000))
    return saida


def comparar(par: dict) -> dict:
    p, c = par["padrao"], par["contrato"]
    if p and not c:
        return {"situacao": "faltando", "padrao": p, "contrato": None}
    if c and not p:
        return {"situacao": "a mais", "padrao": None, "contrato": c}
    igual = difflib.SequenceMatcher(None, _norm(p["texto"]), _norm(c["texto"]), autojunk=False).ratio()
    if igual >= 0.97:
        return {"situacao": "igual", "padrao": p, "contrato": c, "semelhanca": round(igual, 2)}
    pa, ca = p["texto"].split(), c["texto"].split()
    saiu, entrou = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, pa, ca, autojunk=False).get_opcodes():
        if op in ("delete", "replace") and i2 > i1:
            saiu.append(" ".join(pa[i1:i2]))
        if op in ("insert", "replace") and j2 > j1:
            entrou.append(" ".join(ca[j1:j2]))
    return {"situacao": "alterada", "padrao": p, "contrato": c, "semelhanca": round(igual, 2),
            "saiu": [s[:240] for s in saiu[:6]], "entrou": [s[:240] for s in entrou[:6]]}


def _revisar(estado, t, passo) -> dict:
    passo(0, "andando")
    nome_c, texto_c = _texto_de(estado, t["params"].get("documento"))
    nome_p, texto_p = _texto_de(estado, t["params"].get("padrao"))
    passo(0, "feito", f"“{nome_c}” e “{nome_p}”")
    passo(1, "andando")
    cc, cp = clausulas_de(texto_c), clausulas_de(texto_p)
    if not cp or not cc:
        raise ValueError(("o padrão" if not cp else "o contrato") + " não tem cláusulas numeradas que eu reconheça (ex.: “CLÁUSULA 1ª”, “CLÁUSULA PRIMEIRA”)")
    passo(1, "feito", f"{len(cc)} no contrato, {len(cp)} no padrão")
    passo(2, "andando")
    comparacoes = [comparar(par) for par in alinhar(cp, cc)]
    conta = {k: sum(1 for x in comparacoes if x["situacao"] == k) for k in ("igual", "alterada", "faltando", "a mais")}
    passo(2, "feito", ", ".join(f"{v} {k}" for k, v in conta.items() if v))
    indice = 3
    if t["params"].get("explicar"):
        passo(3, "andando")
        nomes = (t["params"].get("documento"), t["params"].get("padrao"))
        cliente = estado.cliente_para("redacao", caminhos=[str(getattr(d, "path", "") or "") for d in estado.searcher.documents
                                                           if d.name in nomes])
        feitas = 0
        for x in comparacoes:
            if x["situacao"] != "alterada" or feitas >= 6:
                continue
            if t.get("_parar"):
                raise Parou()
            pergunta = ("Em uma frase, em português, diga o que mudou do texto PADRÃO para o texto CONTRATO e se isso é mais ou menos "
                        "favorável a quem contratou. Não invente nada que não esteja nos dois textos.")
            contexto = f"PADRÃO:\n{x['padrao']['texto'][:1800]}\n\nCONTRATO:\n{x['contrato']['texto'][:1800]}"
            try:
                x["explicacao"] = str(cliente.ask(pergunta, contexto) or "").strip()[:600]
            except Exception as exc:  # noqa: BLE001 - sem o modelo, fica a comparação por regra
                x["explicacao"] = ""
                x["erro_explicacao"] = str(exc)[:200]
            feitas += 1
        passo(3, "feito", f"{feitas} explicada(s)")
        indice = 4
    passo(indice, "andando")
    rot = {"igual": "igual ao padrão", "alterada": "alterada", "faltando": "falta no contrato", "a mais": "a mais no contrato"}
    blocos = []
    for x in comparacoes:
        ref = x["padrao"] or x["contrato"]
        cab = f"<h2>{_e(ref['titulo'])} — {rot[x['situacao']]}</h2>"
        if x["situacao"] == "alterada":
            corpo = ("".join(f"<p><b>Saiu do padrão:</b> {_e(s)}</p>" for s in x["saiu"]) +
                     "".join(f"<p><b>Entrou no contrato:</b> {_e(s)}</p>" for s in x["entrou"]) +
                     (f"<p><i>O assistente (confira): {_e(x['explicacao'])}</i></p>" if x.get("explicacao") else ""))
        elif x["situacao"] == "faltando":
            corpo = f"<p>No padrão: {_e(x['padrao']['texto'][:600])}</p>"
        elif x["situacao"] == "a mais":
            corpo = f"<p>No contrato: {_e(x['contrato']['texto'][:600])}</p>"
        else:
            corpo = ""
        blocos.append(cab + corpo)
    resumo = ", ".join(f"{v} {rot[k]}" for k, v in conta.items() if v)
    corpo = (f"<h1>Revisão de “{_e(nome_c)}” contra o padrão “{_e(nome_p)}”</h1>"
             f"<p>Feita em {datetime.now():%d/%m/%Y %H:%M} pela tarefa “Revisar contra o padrão da casa”. As cláusulas foram "
             f"alinhadas pelo título e pelo texto, e comparadas palavra por palavra. {resumo}.</p>" + "".join(blocos))
    doc_id = estado.documentos.criar(f"Revisão de {Path(nome_c).stem} contra o padrão", "texto", corpo)
    t["_restauracao"].documento(doc_id, "relatório")
    passo(indice, "feito", "relatório no editor")
    return {"documento_id": doc_id, "conta": conta,
            "clausulas": [{"situacao": x["situacao"], "titulo": (x["padrao"] or x["contrato"])["titulo"]} for x in comparacoes]}


def _passos_de(tipo: str, params: dict) -> list[str]:
    if tipo == "vencimentos":
        d = int(params.get("dias") or 90)
        return ["Ler as datas conferidas dos documentos", f"Separar o que vence em {d} dias", "Escrever o relatório"] + \
            (["Propor na Agenda, por Aprovações"] if params.get("propor") else [])
    return ["Ler o contrato e o padrão", "Separar as cláusulas", "Alinhar e comparar"] + \
        (["O assistente explica as alteradas"] if params.get("explicar") else []) + ["Escrever o relatório"]


RECEITAS = {"vencimentos": _vencimentos, "revisar": _revisar}


# ------------------------------------------------------------ o executor

class Tarefas:
    def __init__(self, estado, pasta: Path) -> None:
        self.estado = estado
        self.pasta = Path(pasta)
        self.vivas: dict[str, dict] = {}

    def _arquivo(self, id_: str) -> Path:
        return self.pasta / id_ / "tarefa.json"

    def _gravar(self, t: dict) -> None:
        a = self._arquivo(t["id"])
        a.parent.mkdir(parents=True, exist_ok=True)
        a.write_text(json.dumps({k: v for k, v in t.items() if not k.startswith("_")}, ensure_ascii=False, indent=1), encoding="utf-8")

    def obter(self, id_: str) -> dict | None:
        if not re.fullmatch(r"[0-9a-f]{12}", id_ or ""):
            return None
        if id_ in self.vivas:
            return {k: v for k, v in self.vivas[id_].items() if not k.startswith("_")}
        try:
            return json.loads(self._arquivo(id_).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def listar(self, limite: int = 30) -> list[dict]:
        saida = []
        for a in sorted(self.pasta.glob("*/tarefa.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limite]:
            t = self.obter(a.parent.name)
            if t:
                saida.append(t)
        return saida

    def comecar(self, tipo: str, params: dict, *, esperar: bool = False) -> dict:
        if tipo not in RECEITAS:
            raise ValueError("tarefa desconhecida")
        limpos = {}
        for p in TIPOS[tipo]["parametros"]:
            v = params.get(p["id"], p["padrao"])
            limpos[p["id"]] = (bool(v) if p["tipo"] == "sim_nao" else int(v or 0) if p["tipo"] == "numero" else str(v or ""))
        if tipo == "revisar" and (not limpos["documento"] or not limpos["padrao"]):
            raise ValueError("escolha o contrato e o padrão da casa")
        id_ = uuid.uuid4().hex[:12]
        t = {"id": id_, "tipo": tipo, "nome": TIPOS[tipo]["nome"], "params": limpos, "estado": "andando",
             "passos": [{"titulo": x, "estado": "esperando", "detalhe": ""} for x in _passos_de(tipo, limpos)],
             "resultado": None, "erro": "", "criada_em": _agora(), "terminada_em": "", "desfeita": []}
        t["_restauracao"] = Restauracao(self.pasta / id_)
        self.vivas[id_] = t
        self._gravar(t)

        def passo(i, estado_, detalhe=""):
            if t.get("_parar"):
                raise Parou()
            if i < len(t["passos"]):
                t["passos"][i]["estado"] = estado_
                if detalhe:
                    t["passos"][i]["detalhe"] = detalhe
            self._gravar(t)

        def rodar():
            try:
                t["resultado"] = RECEITAS[tipo](self.estado, t, passo)
                t["estado"] = "feita"
            except Parou:
                t["estado"] = "parada"
            except Exception as exc:  # noqa: BLE001 - a tarefa falha com o motivo; o programa segue
                t["estado"] = "falhou"
                t["erro"] = str(exc)[:400]
                for p in t["passos"]:
                    if p["estado"] == "andando":
                        p["estado"] = "falhou"
            t["terminada_em"] = _agora()
            self._gravar(t)
            self.vivas.pop(id_, None)

        if esperar:
            rodar()
        else:
            import contextvars

            threading.Thread(target=contextvars.copy_context().run, args=(rodar,), name="tarefa-" + id_, daemon=True).start()
        return self.obter(id_)

    def parar(self, id_: str) -> dict:
        t = self.vivas.get(id_)
        if t:
            t["_parar"] = True
        return self.obter(id_) or {}

    def desfazer(self, id_: str) -> dict:
        t = self.obter(id_)
        if not t:
            raise LookupError("tarefa não encontrada")
        if id_ in self.vivas:
            raise ValueError("espere a tarefa terminar (ou pare) antes de desfazer")
        r = Restauracao(self.pasta / id_)
        feito = r.desfazer(self.estado)
        t["desfeita"] = (t.get("desfeita") or []) + feito
        t["estado"] = "desfeita" if all(x["ok"] for x in feito) else "desfeita em parte"
        self._gravar(t)
        return t


# ------------------------------------------------------------------ rotas

class NovaTarefa(BaseModel):
    tipo: str
    params: dict = {}


def montar(estado, app, dados_dir: Path) -> None:
    estado.tarefas_de_passos = Tarefas(estado, Path(dados_dir) / "passos")

    @app.get("/api/passos/tipos")
    def passos_tipos() -> dict:
        return {"tipos": [dict(v, id=k) for k, v in TIPOS.items()],
                "documentos": sorted(d.name for d in estado.searcher.documents)[:2000]}

    @app.get("/api/passos")
    def passos_listar() -> dict:
        return {"tarefas": estado.tarefas_de_passos.listar()}

    @app.post("/api/passos")
    def passos_comecar(payload: NovaTarefa) -> dict:
        try:
            return estado.tarefas_de_passos.comecar(payload.tipo, payload.params)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    @app.get("/api/passos/{id_}")
    def passos_um(id_: str) -> dict:
        t = estado.tarefas_de_passos.obter(id_)
        if not t:
            raise HTTPException(status_code=404, detail="tarefa não encontrada")
        return t

    @app.post("/api/passos/{id_}/parar")
    def passos_parar(id_: str) -> dict:
        return estado.tarefas_de_passos.parar(id_)

    @app.post("/api/passos/{id_}/desfazer")
    def passos_desfazer(id_: str) -> dict:
        try:
            return estado.tarefas_de_passos.desfazer(id_)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
