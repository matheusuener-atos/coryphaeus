"""
O município do prestador: dá para emitir pelo padrão nacional daqui?

Só dá se o município emissor for conveniado ao Sistema Nacional, estiver
ativo e permitir os emissores públicos (documentação do campo `cLocEmi` no
XSD; regra E0037). O PAULUS pergunta isso ao próprio Sistema Nacional
(`/parametros_municipais/{município}/convenio`), com o certificado do
escritório, guarda a resposta com a data e pergunta de novo uma vez por mês
ou quando a pessoa pede.

O formato exato da resposta está no Swagger, que só abre com certificado. Por
isso a leitura é cautelosa: guarda o JSON inteiro e procura os sinais de
convênio inativo ou emissor não permitido; o que não reconhece vira "não
consegui confirmar", e a emissão fica indisponível até confirmar — nunca o
contrário.
"""

from __future__ import annotations

import json
import unicodedata
from datetime import datetime, timedelta

from . import tabelas
from .cliente import NaoChegou, SemResposta

RECONSULTAR_DIAS = 30

CONVENIADO = "conveniado"
SEM_CONVENIO = "sem_convenio"
INDEFINIDO = "indefinido"
NAO_CONSULTADO = "nao_consultado"


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _chave(texto: str) -> str:
    t = unicodedata.normalize("NFD", str(texto))
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower()


def _achatar(obj, prefixo: str = "") -> dict:
    """{"a": {"b": 1}} -> {"a.b": 1}, com as chaves sem acento e minúsculas."""
    saida: dict = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            saida.update(_achatar(v, f"{prefixo}{_chave(k)}."))
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:50]):
            saida.update(_achatar(v, f"{prefixo}{i}."))
    else:
        saida[prefixo.rstrip(".")] = obj
    return saida


def _verdade(valor) -> bool | None:
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int,)) and valor in (0, 1):
        return bool(valor)
    t = _chave(valor).strip()
    if t in ("s", "sim", "true", "ativo", "ativa", "1", "permitido", "habilitado"):
        return True
    if t in ("n", "nao", "false", "inativo", "inativa", "0", "suspenso", "suspensa", "bloqueado"):
        return False
    return None


def interpretar(status: int, corpo: dict | None, texto: str = "") -> dict:
    """
    A resposta da consulta do convênio em {situacao, emissor_nacional, detalhes}.

    - 404, ou corpo dizendo que não existe convênio: sem convênio;
    - 200 com convênio e nenhum sinal de inativo/suspenso/emissor não
      permitido: conveniado;
    - qualquer outra coisa: indefinido (e a emissão não abre).
    """
    if status == 404:
        return {"situacao": SEM_CONVENIO, "emissor_nacional": False, "detalhes": "convênio não encontrado"}
    if status != 200 or not isinstance(corpo, dict):
        return {"situacao": INDEFINIDO, "emissor_nacional": None,
                "detalhes": f"resposta {status} do Sistema Nacional"}
    plano = _achatar(corpo)
    # Mensagem de "não encontrado" em resposta 200 também é sem convênio.
    for k, v in plano.items():
        if isinstance(v, str) and any(p in _chave(v) for p in ("nao encontrad", "inexistente", "nao conveniad")):
            return {"situacao": SEM_CONVENIO, "emissor_nacional": False, "detalhes": v[:200]}
    negativos = []
    emissor = None
    for k, v in plano.items():
        ultimo = k.split(".")[-1]
        vv = _verdade(v)
        if any(p in ultimo for p in ("situacao", "ativo", "status", "aderente", "vigente")):
            if vv is False or (isinstance(v, str) and _chave(v).strip() in ("inativo", "suspenso", "inativa", "suspensa")):
                negativos.append(f"{k}={v}")
        if "emissor" in ultimo or "emissao" in ultimo or "sefin" in ultimo:
            if vv is not None:
                emissor = vv if emissor is None else (emissor and vv)
    if negativos:
        return {"situacao": SEM_CONVENIO, "emissor_nacional": False,
                "detalhes": "convênio inativo ou suspenso (" + ", ".join(negativos[:3]) + ")"}
    if emissor is False:
        return {"situacao": SEM_CONVENIO, "emissor_nacional": False,
                "detalhes": "o município não permite os emissores públicos nacionais"}
    return {"situacao": CONVENIADO, "emissor_nacional": True if emissor is None else emissor, "detalhes": ""}


def prazo_cancelamento_dias(corpo: dict | None) -> int | None:
    """O prazo de cancelamento parametrizado, se a resposta trouxer um campo
    com "cancel" e "prazo"/"dias" no nome. Sem ele, o PAULUS não inventa: deixa
    a Sefin decidir (regra E0822) e explica a rejeição."""
    for k, v in _achatar(corpo or {}).items():
        if "cancel" in k and any(p in k for p in ("prazo", "dias", "dia")):
            try:
                n = int(str(v).strip())
            except ValueError:
                continue
            if 0 <= n <= 3650:
                return n
    return None


def frase(cmun: str, situacao: str, detalhes: str = "") -> str:
    m = tabelas.municipio(cmun) or {}
    nome = f"{m.get('nome', cmun)}/{m.get('uf', '')}".rstrip("/") if m else (cmun or "o município")
    if situacao == CONVENIADO:
        return (f"Dá para emitir pelo padrão nacional daqui: {nome} tem convênio ativo com o "
                "Sistema Nacional da NFS-e.")
    if situacao == SEM_CONVENIO:
        return (f"{nome} não emite pelo Sistema Nacional da NFS-e"
                + (f" ({detalhes})" if detalhes else "") +
                ". As notas continuam sendo emitidas no sistema da prefeitura, e o PAULUS continua "
                "só registrando o que for emitido lá.")
    if situacao == INDEFINIDO:
        return (f"Não consegui confirmar se {nome} emite pelo Sistema Nacional"
                + (f" ({detalhes})" if detalhes else "") +
                ". Enquanto não confirmar, a emissão fica desligada; tente consultar de novo.")
    return ("Ainda não consultei o município. A consulta usa o certificado do escritório e "
            "pergunta ao próprio Sistema Nacional se dá para emitir daqui.")


class Municipios:
    """As consultas guardadas, por município e ambiente."""

    def __init__(self, base) -> None:
        self.base = base

    def ultima(self, cmun: str, ambiente: str) -> dict | None:
        linha = self.base.um("SELECT * FROM nfse_municipio WHERE cmun = ? AND ambiente = ?", (cmun, ambiente))
        if not linha:
            return None
        linha["resposta"] = json.loads(linha.get("resposta") or "null")
        return linha

    def situacao(self, cmun: str, ambiente: str) -> dict:
        """O que a tela mostra: situação, frase e se dá para emitir agora."""
        u = self.ultima(cmun, ambiente) if cmun else None
        if not u:
            return {"situacao": NAO_CONSULTADO, "frase": frase(cmun, NAO_CONSULTADO), "pode_emitir": False,
                    "consultado_em": "", "reconsultar": True, "prazo_cancelamento_dias": None}
        vencida = (datetime.now() - datetime.fromisoformat(u["consultado_em"])) > timedelta(days=RECONSULTAR_DIAS)
        return {"situacao": u["situacao"], "frase": frase(cmun, u["situacao"], u.get("detalhes") or ""),
                "pode_emitir": u["situacao"] == CONVENIADO, "consultado_em": u["consultado_em"],
                "reconsultar": vencida, "prazo_cancelamento_dias": u.get("prazo_cancelamento_dias"),
                "detalhes": u.get("detalhes") or ""}

    def consultar(self, cliente, cmun: str, ambiente: str) -> dict:
        """Pergunta ao Sistema Nacional e guarda. Falha de rede vira indefinido."""
        try:
            r = cliente.parametros_convenio(cmun)
            info = interpretar(r.status, r.corpo, r.texto)
            corpo = r.corpo
        except (SemResposta, NaoChegou) as exc:
            info = {"situacao": INDEFINIDO, "emissor_nacional": None, "detalhes": str(exc)}
            corpo = None
        prazo = prazo_cancelamento_dias(corpo)
        self.base.escrever(
            "INSERT INTO nfse_municipio (cmun, ambiente, situacao, detalhes, resposta, prazo_cancelamento_dias, "
            "consultado_em) VALUES (?,?,?,?,?,?,?) ON CONFLICT(cmun, ambiente) DO UPDATE SET "
            "situacao=excluded.situacao, detalhes=excluded.detalhes, resposta=excluded.resposta, "
            "prazo_cancelamento_dias=excluded.prazo_cancelamento_dias, consultado_em=excluded.consultado_em",
            (cmun, ambiente, info["situacao"], info.get("detalhes") or "",
             json.dumps(corpo, ensure_ascii=False) if corpo is not None else "null", prazo, _agora()),
        )
        return self.situacao(cmun, ambiente)
