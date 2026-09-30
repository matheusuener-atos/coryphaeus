"""
Servicos por colaborador: de fora, cada pessoa so ve os servicos de que
participa (pedido do dono, 29/09/2026).

Os colaboradores de um servico sao a Equipe dele (servicos.equipe, pessoas de
Cadastros › Equipe) - e so ela: quem a define e o titular (ou a janela do
servidor), e o responsavel de uma etapa sai sempre dela. A pessoa que entra pelo
tunel e reconhecida pelo e-mail: a conta de acesso (o e-mail Google e o
secundario) casa com o e-mail da ficha em Cadastros.

Quem ve tudo: a janela do servidor (sem pessoa) e o titular. O resto - socio
e colaborador, de fora - so ve o que participa, e o que e de um servico
fechado para ele some junto: a pasta do servico no Acervo (e na busca e no
assistente), as etapas e os compromissos dele na Agenda e em Tarefas, e as
gravacoes ligadas a ele.

A regra vale na API (o porteiro dos servicos, em api.py, e os filtros por
rota) e a tela so mostra o que a API devolve. Nada aqui muda o codigo quando o
titular muda a Equipe de um servico: tudo e lido a cada requisicao.
"""

from __future__ import annotations

import json
import os
from contextvars import ContextVar
from pathlib import Path

# Os servicos que a pessoa da vez NAO ve, posto por requisicao (vazio: ve tudo).
OCULTOS: ContextVar = ContextVar("paulus_servicos_ocultos", default=frozenset())


def restrita(sessao: dict | None) -> bool:
    """A regra vale para quem entra de fora e nao e titular."""
    return bool(sessao) and sessao.get("papel") != "titular"


def _json(texto, padrao):
    try:
        return json.loads(texto) if texto else padrao
    except (TypeError, ValueError):
        return padrao


def emails_da_pessoa(sessao: dict, contas) -> set[str]:
    emails = {str(sessao.get("email") or "").strip().lower()}
    try:
        conta = contas.obter(int(sessao.get("conta_id") or 0)) or {}
        emails.add(str(conta.get("email_secundario") or "").strip().lower())
    except Exception:  # noqa: BLE001 - sem o banco das contas, fica o e-mail da sessao
        pass
    return {e for e in emails if e}


def cadastros_da_pessoa(base, emails: set[str]) -> set[int]:
    """As fichas de Cadastros (equipe) que sao esta pessoa, pelo e-mail."""
    if not emails:
        return set()
    linhas = base.buscar("SELECT id, email FROM cadastros WHERE tipo IN ('colaborador', 'socio')")
    return {int(l["id"]) for l in linhas if str(l.get("email") or "").strip().lower() in emails}


def acesso_da_equipe(base, contas, convites) -> dict[int, str]:
    """
    A equipe do escritorio e quem entra no PAULUS (pedido do dono, 29/09): para
    cada ficha de Cadastros › Equipe, o estado do acesso - "titular", "ativo",
    "pendente" (falta o autenticador) ou "convidado" (convite em aberto). Quem
    nao aparece aqui nao tem acesso e nao entra na Equipe de um servico.
    """
    por_email: dict[str, str] = {}
    try:
        for c in contas.listar():
            estado = "titular" if c.get("papel") == "titular" else ("ativo" if c.get("pronta", c.get("totp_confirmado")) else "pendente")
            for e in (c.get("email"), c.get("email_secundario")):
                if e:
                    por_email[str(e).strip().lower()] = estado
    except Exception:  # noqa: BLE001 - sem o banco das contas, ninguem tem acesso
        pass
    try:
        for x in convites.listar():
            e = str(x.get("email") or "").strip().lower()
            if e and x.get("estado") == "aberto" and e not in por_email:
                por_email[e] = "convidado"
    except Exception:  # noqa: BLE001
        pass
    linhas = base.buscar("SELECT id, email FROM cadastros WHERE tipo IN ('colaborador', 'socio')")
    return {int(l["id"]): por_email[e] for l in linhas
            if (e := str(l.get("email") or "").strip().lower()) in por_email}


def participantes(equipe_json) -> set[int]:
    return {int(x) for x in _json(equipe_json, []) if str(x).lstrip("-").isdigit()}


def ocultos(base, contas, sessao: dict | None) -> set[int]:
    """Os servicos que esta pessoa nao ve (vazio para quem ve tudo)."""
    if not restrita(sessao):
        return set()
    minhas = cadastros_da_pessoa(base, emails_da_pessoa(sessao, contas))
    linhas = base.buscar("SELECT id, equipe FROM servicos")
    return {int(l["id"]) for l in linhas if not (minhas & participantes(l.get("equipe")))}


def predicado_de_pastas(pastas: list[Path]):
    """caminho -> visivel: fora das pastas dos servicos fechados."""
    raizes = []
    for p in pastas:
        try:
            raizes.append(os.path.normcase(str(Path(p).resolve())))
        except OSError:
            continue
    if not raizes:
        return None

    def visivel(caminho: str) -> bool:
        try:
            c = os.path.normcase(str(Path(caminho).resolve()))
        except OSError:
            c = os.path.normcase(str(caminho))
        return not any(c == r or c.startswith(r + os.sep) for r in raizes)

    return visivel


def visivel(servico_id) -> bool:
    """O servico (ou nenhum) e visivel para a pessoa da vez?"""
    try:
        return not servico_id or int(servico_id) not in OCULTOS.get()
    except (TypeError, ValueError):
        return True
