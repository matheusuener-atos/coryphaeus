"""
PAULUS - o que cada plano libera (03/10/2026).

Os planos diferem em recursos, e não só em créditos: a profundidade máxima,
quantas pessoas, quantos agentes, as contas de e-mail, a NFS-e por mês, o
DataJud, as gravações, as sugestões ao vivo, as horas, a muralha, o agente que
faz sozinho, a jurisprudência do STJ, o Word e o MCP. A lista é do Worker
(`plano.recursos` em GET /api/ia/conta, PLANOS_DE_FABRICA em worker/ia.js):
este módulo só lê e diz "pode" ou "não pode", com a frase do plano que tem.

Onde vale:
- Sem a cobrança ligada (terminal, testes, PAULUS_COBRANCA=0), tudo liberado,
  como a IA em src/plano.py.
- Com a cobrança: os recursos do plano da conta, guardados em prefs "plano"
  para valer sem internet. Sem plano nenhum (nunca assinou, ou venceu), os do
  plano mais simples - o programa continua inteiro no que é de todos.

É uma trava do programa, no computador do escritório. As que não dá para
contornar são as do Worker: o modelo, os créditos e o nível de profundidade
que chega à nuvem.
"""

from __future__ import annotations

# A ordem da profundidade (src/profundidade.py).
NIVEIS = ("estagiario", "bacharel", "advogado", "juiz", "ministro")

# O plano mais simples, para quem não tem plano conhecido (o Advogado de fábrica).
BASICO = {"profundidade": "advogado", "agentes": 3, "equipe": False, "emails": 1, "consumo_por_pessoa": False,
          "nfse_mes": 0, "nfse_recorrente": False, "datajud": False, "gravacao": False, "ao_vivo": False,
          "horas": False, "muralha": False, "autonomia": False, "jurisprudencia_stj": False, "word": False,
          "mcp": False, "pagina_cliente": False}
BASICO_PESSOAS = 1

# Como cada recurso aparece na frase "X faz parte do plano Y".
NOMES = {
    "equipe": "a equipe (contas de colaboradores)",
    "consumo_por_pessoa": "o consumo de IA por pessoa, com limites",
    "nfse_mes": "a emissão de NFS-e",
    "nfse_recorrente": "a NFS-e recorrente",
    "datajud": "o acompanhamento de processos pelo DataJud",
    "gravacao": "a gravação e a transcrição de reuniões",
    "ao_vivo": "as sugestões jurídicas ao vivo durante a reunião",
    "horas": "as horas por serviço",
    "muralha": "a muralha de conflito de interesses",
    "autonomia": "o agente que faz sozinho e as tarefas de vários passos",
    "jurisprudencia_stj": "a jurisprudência do STJ em massa",
    "word": "o assistente no Word",
    "mcp": "a conexão MCP com outras IAs",
    "agentes": "mais agentes personalizados",
    "emails": "mais contas de e-mail",
    "pessoas": "mais pessoas na equipe",
}


class SemRecurso(RuntimeError):
    """O plano não tem o recurso (ou chegou ao limite dele). A frase vai para a tela (403)."""

    def __init__(self, frase: str, recurso: str = "") -> None:
        super().__init__(frase)
        self.recurso = recurso


def _cobranca() -> bool:
    import plano

    return plano.cobranca_ligada()


def _guardado(estado) -> dict:
    return dict(estado.prefs.dados.get("plano") or {})


def do_plano(estado) -> dict | None:
    """Os recursos valendo agora; None quando tudo está liberado (sem cobrança)."""
    if not _cobranca():
        return None
    import plano

    try:
        s = plano.situacao(estado)
    except Exception:  # noqa: BLE001 - na dúvida, o que se sabia
        s = {"ia": False}
    g = _guardado(estado)
    if not s.get("ia") or not g.get("recursos"):
        return dict(BASICO, pessoas=BASICO_PESSOAS)
    return {**BASICO, **g["recursos"], "pessoas": int(g.get("pessoas") or BASICO_PESSOAS)}


def pode(estado, chave: str) -> bool:
    r = do_plano(estado)
    if r is None:
        return True
    v = r.get(chave)
    # Número: 0 é "não tem"; None é "sem limite".
    return v is None or bool(v)


def limite(estado, chave: str) -> int | None:
    """O teto (pessoas, agentes, emails, nfse_mes); None sem limite."""
    r = do_plano(estado)
    if r is None or r.get(chave) is None:
        return None
    return int(r[chave])


def nivel_max(estado) -> str:
    r = do_plano(estado)
    return "ministro" if r is None else str(r.get("profundidade") or "advogado")


def nivel_permitido(estado, nivel_id: str) -> bool:
    m = nivel_max(estado)
    return nivel_id not in NIVEIS or NIVEIS.index(nivel_id) <= NIVEIS.index(m)


def _planos_que_tem(estado, chave: str, minimo: int = 1) -> list[str]:
    """Os nomes dos planos que têm o recurso (pelo que o Worker mandou)."""
    nomes = []
    for p in _guardado(estado).get("planos") or []:
        v = (p.get("recursos") or {}).get(chave) if chave != "pessoas" else p.get("pessoas")
        ok = v is None or (isinstance(v, bool) and v) or (not isinstance(v, bool) and int(v or 0) >= minimo)
        if ok:
            nomes.append(str(p.get("nome") or p.get("id")))
    return nomes


def _juntar(nomes: list[str]) -> str:
    if len(nomes) <= 1:
        return "".join(nomes)
    return ", ".join(nomes[:-1]) + " e " + nomes[-1]


def frase(estado, chave: str, minimo: int = 1) -> str:
    """'a gravação ... faz parte dos planos Escritório e Escritório Plus' (o assunto é o recurso)."""
    nome = NOMES.get(chave, chave)
    tem = _planos_que_tem(estado, chave, minimo)
    if not tem:
        return f"{nome[0].upper()}{nome[1:]} não faz parte do seu plano. Veja os planos em Configurações › Plano e consumo."
    onde = ("do plano " if len(tem) == 1 else "dos planos ") + _juntar(tem)
    return f"{nome[0].upper()}{nome[1:]} faz parte {onde}. Veja em Configurações › Plano e consumo."


def frase_nivel(estado, nivel_id: str) -> str:
    tem = [str(p.get("nome")) for p in _guardado(estado).get("planos") or []
           if NIVEIS.index(str((p.get("recursos") or {}).get("profundidade") or "advogado")) >= NIVEIS.index(nivel_id)]
    nome = nivel_id.capitalize().replace("Estagiario", "Estagiário")
    if not tem:
        return f"A profundidade {nome} não faz parte do seu plano."
    return f"A profundidade {nome} faz parte " + ("do plano " if len(tem) == 1 else "dos planos ") + _juntar(tem) + "."


def exigir(estado, chave: str) -> None:
    """Levanta SemRecurso se o plano não tem o recurso."""
    if not pode(estado, chave):
        raise SemRecurso(frase(estado, chave), chave)


def exigir_vaga(estado, chave: str, usados: int, coisa: str) -> None:
    """Para os recursos contados (pessoas, agentes, emails, nfse_mes): levanta SemRecurso no teto."""
    teto = limite(estado, chave)
    if teto is None or usados < teto:
        return
    if teto == 0:
        raise SemRecurso(frase(estado, chave), chave)
    tem = _planos_que_tem(estado, chave, usados + 1)
    mais = (" Para mais, " + ("o plano " if len(tem) == 1 else "os planos ") + _juntar(tem) + ".") if tem else ""
    raise SemRecurso(f"O seu plano vai até {teto} {coisa}.{mais} Veja em Configurações › Plano e consumo.", chave)


def exigir_pessoa(estado, existentes: int) -> None:
    """Mais uma pessoa na equipe (o titular conta como uma)."""
    if not pode(estado, "equipe"):
        raise SemRecurso(frase(estado, "equipe"), "equipe")
    exigir_vaga(estado, "pessoas", existentes, "pessoas")


def colaborador_barrado(estado) -> str:
    """De fora, quem não é o titular só entra se o plano tem equipe."""
    return "" if pode(estado, "equipe") else frase(estado, "equipe")


def para_tela(estado) -> dict:
    """O que a tela precisa: os recursos de agora, o nível máximo e se tudo está liberado."""
    r = do_plano(estado)
    return {"livre": r is None, "recursos": r or {}, "profundidade_max": nivel_max(estado)}
