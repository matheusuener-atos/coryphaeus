"""
PAULUS - As NFS-e que o PAVLVS emitiu para este escritório (a assinatura).

Quem emite é o PAULUS da casa (tela "Notas Admin", no servidor do dono);
a nota fica no Worker (worker/nfse-casa.js) e este PAULUS a busca com o
segredo da instalação da nuvem (src/nuvem.py):

    GET /api/ia/nfse               a lista (sem os arquivos)
    GET /api/ia/nfse/<id>/pdf|xml  o arquivo

Sem a conta da nuvem ativada, ou sem internet, a lista é vazia e nada
reclama: a nota é um aviso a mais, não um erro. A lista fica 30 minutos em
memória (a Central de avisos pergunta a cada volta); a falha fica 5 minutos,
com a última lista boa no lugar.

Não confundir com src/nfse/: aquele é o emissor do escritório (as notas que
ELE emite para os clientes dele). Aqui são as que ele RECEBE do PAVLVS.
"""

from __future__ import annotations

import re
import threading
import time
from datetime import date, datetime, timedelta

import nuvem

CACHE_S = 30 * 60
CACHE_FALHA_S = 5 * 60
DIAS_DO_AVISO = 45
MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro")
_RE_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_cache: dict = {"quando": 0.0, "validade": 0.0, "chave": "", "notas": []}
_trava = threading.Lock()


def esquecer() -> None:
    with _trava:
        _cache.update(quando=0.0, validade=0.0, chave="", notas=[])


def listar(estado, forcar: bool = False) -> list[dict]:
    """As notas da conta, mais novas primeiro. Sem conta ou sem rede: []."""
    try:
        k = nuvem.chave(estado, "paulus")
    except Exception:  # noqa: BLE001
        k = ""
    if not k:
        return []
    with _trava:
        if not forcar and _cache["chave"] == k and time.time() - _cache["quando"] < _cache["validade"]:
            return list(_cache["notas"])
        antes = list(_cache["notas"]) if _cache["chave"] == k else []
    try:
        d = nuvem._paulus(estado, "GET", "/api/ia/nfse")
        notas = [_limpa(n) for n in (d.get("notas") or []) if isinstance(n, dict) and _RE_ID.match(str(n.get("id") or ""))]
        validade = CACHE_S
    except Exception:  # noqa: BLE001 - sem rede, sem conta, Worker fora: a ultima lista boa
        notas, validade = antes, CACHE_FALHA_S
    with _trava:
        _cache.update(quando=time.time(), validade=validade, chave=k, notas=notas)
    return list(notas)


def _limpa(n: dict) -> dict:
    try:
        valor = float(n.get("valor") or 0)
    except (TypeError, ValueError):
        valor = 0.0
    return {"id": str(n["id"]), "numero": str(n.get("numero") or ""), "competencia": str(n.get("competencia") or ""),
            "valor": valor, "descricao": str(n.get("descricao") or ""), "emitida_em": str(n.get("emitida_em") or ""),
            "ambiente": str(n.get("ambiente") or ""), "cancelada": bool(n.get("cancelada"))}


def arquivo(estado, id_: str, tipo: str) -> tuple[bytes, str, str]:
    """(bytes, nome do arquivo, content-type) do PDF ou do XML. LookupError se não houver."""
    if tipo not in ("pdf", "xml") or not _RE_ID.match(str(id_ or "")):
        raise LookupError("essa nota não existe")
    dados, ctype = nuvem.paulus_bytes(estado, f"/api/ia/nfse/{id_}/{tipo}")
    nota = next((n for n in listar(estado) if n["id"] == id_), None)
    numero = (nota or {}).get("numero") or id_
    nome = f"NFS-e {re.sub(r'[^A-Za-z0-9._-]', '_', numero)}.{tipo}"
    padrao = "application/pdf" if tipo == "pdf" else "application/xml"
    return dados, nome, (ctype.split(";")[0].strip() or padrao)


# ------------------------------------------------------------ o aviso

def mes_por_extenso(competencia: str) -> str:
    """"2026-10" -> "outubro/2026"."""
    m = re.match(r"^(\d{4})-(\d{2})$", str(competencia or ""))
    if not m or not 1 <= int(m.group(2)) <= 12:
        return str(competencia or "")
    return f"{MESES[int(m.group(2)) - 1]}/{m.group(1)}"


def reais(valor: float) -> str:
    """300 -> "R$ 300,00"; 1234.5 -> "R$ 1.234,50"."""
    texto = f"{float(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return "R$ " + texto


def _data(iso: str) -> date | None:
    try:
        return datetime.fromisoformat(str(iso or "").replace("Z", "+00:00")[:25]).date()
    except ValueError:
        try:
            return date.fromisoformat(str(iso or "")[:10])
        except ValueError:
            return None


def para_avisos(estado, hoje: date) -> list[dict]:
    """
    As notas recebidas, não canceladas, dos últimos 45 dias, já no formato que
    a Central de avisos monta (src/central_avisos.py, _das_nfse_recebidas).
    """
    saida = []
    for n in listar(estado):
        if n["cancelada"]:
            continue
        quando = _data(n["emitida_em"])
        if quando is None or quando < hoje - timedelta(days=DIAS_DO_AVISO):
            continue
        detalhe = f"nº {n['numero']} · {reais(n['valor'])}" + (" · ambiente de testes" if n["ambiente"] == "producao_restrita" else "")
        base = f"/api/nfse-recebidas/{n['id']}"
        saida.append({
            "id": f"nfse-recebida:{n['id']}",
            "titulo": f"Sua NFS-e de {mes_por_extenso(n['competencia'])} chegou",
            "detalhe": detalhe,
            "quando": "emitida em " + quando.strftime("%d/%m/%Y"),
            "nota_id": n["id"],
            # "baixar": o clique baixa o arquivo (frontend/js/53-avisos.js), sem perguntar.
            "acoes": [{"id": "pdf", "tipo": "baixar", "rotulo": "Download", "url": base + "/pdf", "metodo": "GET"},
                      {"id": "xml", "tipo": "baixar", "rotulo": "XML", "url": base + "/xml", "metodo": "GET"}],
        })
    return saida
