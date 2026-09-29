"""
Publicacoes do Diario de Justica Eletronico Nacional (DJEN), pela OAB
(docs/PLANO-PRODUTO.md, P3).

O CNJ publica as comunicacoes processuais (intimacoes, editais, citacoes) na
API publica do DJEN (comunicaapi.pje.jus.br). O PAULUS pergunta, uma vez por
dia, o que saiu para as OABs que o escritorio acompanha, e cada comunicacao
nova vira um item para revisar, com o prazo sugerido pela data de
disponibilizacao (src/prazos.py) - o advogado confere e cria a tarefa.

O que sai deste computador: so o numero e a UF de cada OAB acompanhada e o
periodo, na consulta ao CNJ. O que volta e publico (o proprio Diario).
"""

from __future__ import annotations

import html
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta

API = "https://comunicaapi.pje.jus.br/api/v1/comunicacao"
POR_PAGINA = 100
MAX_PAGINAS = 10


class ErroPublicacoes(RuntimeError):
    """A consulta nao deu certo; a frase vai para a tela."""


def ler_oab(texto: str) -> dict | None:
    """'GO 12345', '12.345/GO', 'OAB/SP 123456' -> {numero, uf}; None se nao da."""
    t = str(texto or "").upper()
    uf = re.search(r"\b([A-Z]{2})\b", t.replace("OAB", " "))
    numero = re.sub(r"\D", "", t)
    if not uf or not numero:
        return None
    return {"numero": numero.lstrip("0") or "0", "uf": uf.group(1)}


def _texto(html_bruto: str) -> str:
    t = re.sub(r"(?is)<(script|style|head).*?</\1>", " ", html_bruto or "")
    t = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t ]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n\n", t).strip()


def consultar(oab: dict, de: date, ate: date, *, abrir=urllib.request.urlopen) -> list[dict]:
    """As comunicacoes publicadas para esta OAB no periodo (todas as paginas, ate um teto)."""
    saida: list[dict] = []
    for pagina in range(1, MAX_PAGINAS + 1):
        q = urllib.parse.urlencode({
            "numeroOab": oab["numero"], "ufOab": oab["uf"],
            "dataDisponibilizacaoInicio": de.isoformat(), "dataDisponibilizacaoFim": ate.isoformat(),
            "itensPorPagina": POR_PAGINA, "pagina": pagina})
        pedido = urllib.request.Request(f"{API}?{q}", headers={"Accept": "application/json", "User-Agent": "PAULUS"})
        try:
            with abrir(pedido, timeout=40) as r:
                dados = json.loads(r.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - sem internet, fora do ar
            raise ErroPublicacoes("não consegui consultar o Diário de Justiça Eletrônico agora; tento de novo mais tarde") from exc
        itens = dados.get("items") or []
        saida.extend(itens)
        if len(itens) < POR_PAGINA:
            break
    return saida


def normalizar(item: dict, oab: dict) -> dict:
    return {
        "id_externo": str(item["id"]) if item.get("id") is not None else str(item.get("hash") or ""),
        "data": str(item.get("data_disponibilizacao") or ""),
        "tribunal": str(item.get("siglaTribunal") or ""),
        "tipo": str(item.get("tipoComunicacao") or item.get("tipoDocumento") or ""),
        "orgao": str(item.get("nomeOrgao") or ""),
        "classe": str(item.get("nomeClasse") or ""),
        "processo": str(item.get("numeroprocessocommascara") or item.get("numero_processo") or ""),
        "texto": _texto(str(item.get("texto") or ""))[:20000],
        "link": str(item.get("link") or ""),
        "oab": f"{oab['uf']} {oab['numero']}",
    }


class Publicacoes:
    def __init__(self, base) -> None:
        self.base = base

    def guardar(self, itens: list[dict]) -> int:
        """Guarda as novas (pelo id do DJEN); devolve quantas eram novas."""
        novas = 0
        agora = time.strftime("%Y-%m-%dT%H:%M:%S")
        for i in itens:
            if not i["id_externo"] or self.base.um("SELECT id FROM publicacoes WHERE id_externo = ?", (i["id_externo"],)):
                continue
            self.base.escrever(
                "INSERT INTO publicacoes (id_externo, data, tribunal, tipo, orgao, classe, processo, texto, link, oab, criada_em) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (i["id_externo"], i["data"], i["tribunal"], i["tipo"], i["orgao"], i["classe"], i["processo"],
                 i["texto"], i["link"], i["oab"], agora))
            novas += 1
        return novas

    def listar(self, filtro: str = "novas", limite: int = 200) -> list[dict]:
        onde = {"novas": "lida = 0", "lidas": "lida = 1"}.get(filtro, "1=1")
        return self.base.buscar(f"SELECT * FROM publicacoes WHERE {onde} ORDER BY data DESC, id DESC LIMIT ?", (limite,))

    def obter(self, id_: int) -> dict | None:
        return self.base.um("SELECT * FROM publicacoes WHERE id = ?", (id_,))

    def marcar(self, id_: int, lida: bool = True, tarefa_id: int | None = None) -> None:
        if tarefa_id is None:
            self.base.escrever("UPDATE publicacoes SET lida = ? WHERE id = ?", (1 if lida else 0, id_))
        else:
            self.base.escrever("UPDATE publicacoes SET lida = 1, tarefa_id = ? WHERE id = ?", (tarefa_id, id_))

    def contar_novas(self) -> int:
        return self.base.contar("publicacoes", "lida = 0")


def periodo_para_consultar(ultima: str, hoje: date | None = None) -> tuple[date, date]:
    """Desde dois dias antes da ultima consulta (o DJEN pode publicar atrasado), ate hoje; no maximo 30 dias."""
    hoje = hoje or date.today()
    try:
        de = date.fromisoformat(ultima[:10]) - timedelta(days=2)
    except ValueError:
        de = hoje - timedelta(days=7)
    return max(de, hoje - timedelta(days=30)), hoje
