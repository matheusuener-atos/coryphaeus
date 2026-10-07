"""
PAULUS - a IA faz parte da assinatura (02/10/2026).

O dono "virou a chave": o PAULUS deixa de ser gratuito. Sem a assinatura
vigente, o programa funciona inteiro - Agenda, Acervo, Financeiro, cadastros,
as respostas por regra (navegação, consultas) -, mas sem IA nenhuma: nem a da
nuvem nem o modelo local. Com a assinatura, a IA é a da nuvem (src/nuvem.py,
o portão do Worker até o DeepInfra) e o modelo local responde de reserva, com
aviso, sem internet ou com a cota no fim.

Quem diz se a assinatura vale é o Worker de paulus.ia.br (`plano_vigente` em
GET /api/ia/conta). Sem internet, vale o último plano conhecido até o fim do
ciclo pago - guardado em preferencias.json, bloco "plano".

A cobrança só vale no PAULUS instalado (PAULUS_INSTALADO, posto pelo
lançador) ou com PAULUS_COBRANCA=1. Rodando pelo terminal e nos testes,
nada muda; PAULUS_COBRANCA=0 desliga até no instalado.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone

# Uma consulta ao Worker vale por 60 s: a trava é perguntada a cada chamada
# do modelo e não pode custar uma ida à internet cada vez.
VALIDADE_S = 60
_CACHE = {"quando": 0.0, "situacao": None}

FRASE_SEM_PLANO = ("A IA do Paulus faz parte da assinatura. O resto do programa continua aqui; para as respostas "
                   "que leem os seus documentos, resumos e redação, assine em Configurações › Modelos.")


def cobranca_ligada() -> bool:
    valor = os.environ.get("PAULUS_COBRANCA", "")
    if valor in ("0", "1"):
        return valor == "1"
    return os.environ.get("PAULUS_INSTALADO") == "1"


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ainda_vale(ate: str) -> bool:
    try:
        fim = datetime.fromisoformat(str(ate).replace("Z", "+00:00"))
    except ValueError:
        return False
    if fim.tzinfo is None:
        fim = fim.replace(tzinfo=timezone.utc)
    return fim > datetime.now(timezone.utc)


def situacao(estado, forcar: bool = False) -> dict:
    """
    {"ia": bool, "motivo": "", "ate": "", "fonte": "worker"|"guardado"|"livre"}.
    `motivo`: "" (liberada), "sem_conta", "sem_plano".
    """
    if not cobranca_ligada():
        return {"ia": True, "motivo": "", "ate": "", "fonte": "livre"}
    if not forcar and _CACHE["situacao"] is not None and time.time() - _CACHE["quando"] < VALIDADE_S:
        return _CACHE["situacao"]
    import nuvem

    guardado = dict(estado.prefs.dados.get("plano") or {})
    try:
        conta = nuvem.conta_paulus(estado, forcar=forcar)
    except Exception:  # noqa: BLE001 - sem internet: vale o que se sabia
        conta = False
    if conta is None:
        s = {"ia": False, "motivo": "sem_conta", "ate": "", "fonte": "worker"}
    elif conta is False:
        vale = bool(guardado.get("ativo")) and _ainda_vale(guardado.get("ate", ""))
        s = {"ia": vale, "motivo": "" if vale else "sem_plano", "ate": guardado.get("ate", ""), "fonte": "guardado"}
    else:
        vigente = bool(conta.get("plano_vigente"))
        ate = str((conta.get("ciclo") or {}).get("fim") or "")
        s = {"ia": vigente, "motivo": "" if vigente else "sem_plano", "ate": ate, "fonte": "worker"}
        # O plano e o que ele libera (src/recursos_do_plano.py), guardados para valer sem internet.
        p = conta.get("plano") or {}
        novo = {"ativo": vigente, "ate": ate, "id": str(p.get("id") or ""), "nome": str(p.get("nome") or ""),
                "recursos": dict(p.get("recursos") or {}), "pessoas": int(p.get("pessoas") or 0),
                "planos": [{"id": x.get("id"), "nome": x.get("nome"), "pessoas": x.get("pessoas"), "recursos": x.get("recursos") or {}}
                           for x in conta.get("planos") or []]}
        if any(guardado.get(k) != v for k, v in novo.items()):
            estado.prefs.atualizar({"plano": {**novo, "conferido_em": _agora_iso()}})
    _CACHE.update(quando=time.time(), situacao=s)
    return s


def liberada(estado) -> bool:
    try:
        return bool(situacao(estado)["ia"])
    except Exception:  # noqa: BLE001 - na dúvida com a cobrança ligada, sem IA
        return not cobranca_ligada()


def esquecer() -> None:
    """Depois de assinar, ativar ou sair: a próxima pergunta confere de novo."""
    _CACHE.update(quando=0.0, situacao=None)


class SemPlano(RuntimeError):
    """O modelo foi chamado sem a assinatura vigente."""

    def __init__(self) -> None:
        super().__init__(FRASE_SEM_PLANO)
