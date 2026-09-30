"""
Quem mexe no que (docs/PLANO-EQUIPE.md, E2): o nivel de cada pessoa em cada
modulo, por cima da tabela de rotas da R3 (politicas.py).

Os niveis, do menor para o maior:

    nao      nao ve: o modulo some do menu e toda rota dele responde 403
    ver      so ve: le tudo; o que grava responde 403 (menos as consultas,
             que usam o metodo POST mas nao gravam nada - o resumo, a
             traducao, o trecho citado)
    propor   ve, e o que grava vira pedido em Aprovacoes (o de hoje para
             Agenda, Tarefas e Cadastros)
    faz      grava direto. Em Aprovacoes, "faz" e aprovar

Cada modulo oferece so os niveis que fazem sentido nele: documento nao se
propoe (ou se escreve ou nao), e o Acervo de fora so se le.

O titular tem sempre o maior nivel de cada modulo - e quem cuida das contas.
O que a R3 bloqueou por ser "so do computador do escritorio" (configuracoes,
contas, certificado, assinar, mover e apagar arquivos, modelos) continua
bloqueado para todo mundo: nenhum nivel abre isso. O que ficou bloqueado so
por falta de decisao (Financeiro, Relatorios, gravar em Servicos e em
Gravacoes) passa a abrir pelo nivel - as rotas que abrem estao listadas uma
a uma, e nao por prefixo, para que um "apagar" nao entre junto por engano.
"""

from __future__ import annotations

import json

from acesso import politicas

NAO, VER, PROPOR, FAZ = "nao", "ver", "propor", "faz"
ORDEM = (NAO, VER, PROPOR, FAZ)
ROTULOS = {NAO: "não vê", VER: "só vê", PROPOR: "propõe", FAZ: "faz"}
SEGUROS = {"GET", "HEAD", "OPTIONS"}


def _r(*rotas: str) -> set[tuple[str, str]]:
    return {tuple(r.split(" ", 1)) for r in rotas}


# id, rotulo, niveis, padrao do colaborador, prefixos, destinos do menu,
# consultas (POST que nao grava), libera_ver e libera_faz (rotas BLOQUEADO
# que o nivel abre)
MODULOS: list[dict] = [
    {"id": "agenda", "rotulo": "Agenda", "niveis": (NAO, VER, PROPOR, FAZ), "padrao": PROPOR,
     "prefixos": ("/api/agenda", "/api/google/sincronizar"), "exatos": ("/api/google",),
     "destinos": ("calendario", "agendamento")},
    {"id": "tarefas", "rotulo": "Tarefas", "niveis": (NAO, VER, PROPOR, FAZ), "padrao": PROPOR,
     "prefixos": ("/api/tarefas", "/api/etapas", "/api/vinculos"), "destinos": ("tarefas",)},
    {"id": "cadastros", "rotulo": "Cadastros", "niveis": (NAO, VER, PROPOR, FAZ), "padrao": PROPOR,
     "prefixos": ("/api/cadastros",), "destinos": ("cadastros",),
     "consultas": _r("POST /api/cadastros/levantamento")},
    {"id": "documentos", "rotulo": "Documentos", "niveis": (NAO, VER, FAZ), "padrao": FAZ,
     "prefixos": ("/api/documentos", "/api/planilha", "/api/redacao"), "destinos": ("editor",),
     "consultas": _r("POST /api/documentos/{id_}/pdf")},
    {"id": "email", "rotulo": "E-mail", "niveis": (NAO, VER, FAZ), "padrao": FAZ,
     "prefixos": ("/api/email",), "destinos": ("caixa",),
     "consultas": _r("POST /api/email/caixa/resumo", "POST /api/email/traduzir")},
    {"id": "servicos", "rotulo": "Serviços", "niveis": (NAO, VER, FAZ), "padrao": VER,
     "prefixos": ("/api/servicos",), "destinos": ("servicos",),
     "consultas": _r("POST /api/servicos/{id_}/resumo", "POST /api/servicos/{id_}/conversar"),
     "libera_faz": _r("POST /api/servicos", "POST /api/servicos/{id_}/status", "POST /api/servicos/{id_}/etapas",
                      "POST /api/servicos/{id_}/etapas/{indice}/editar", "POST /api/servicos/{id_}/etapas/{indice}",
                      "POST /api/servicos/{id_}/anotacoes", "POST /api/servicos/{id_}/anotacoes/{indice}",
                      "POST /api/servicos/{id_}/prazos/{origem}/{item_id}",
                      "POST /api/servicos/{id_}/horas", "DELETE /api/servicos/{id_}/horas/{hid}",
                      "POST /api/servicos/{id_}/horas/cronometro")},
    {"id": "gravacoes", "rotulo": "Gravações", "niveis": (NAO, VER, FAZ), "padrao": VER,
     "prefixos": ("/api/gravacoes", "/api/voz/ao-vivo"), "destinos": ("gravacoes",),
     "libera_faz": _r("POST /api/voz/ao-vivo", "POST /api/voz/ao-vivo/{sid}/audio", "POST /api/voz/ao-vivo/{sid}/fim",
                      "DELETE /api/voz/ao-vivo/{sid}", "POST /api/gravacoes", "POST /api/gravacoes/{id_}/transcrever",
                      "POST /api/gravacoes/{id_}/resumo", "POST /api/gravacoes/{id_}",
                      "POST /api/gravacoes/{id_}/anotacoes", "POST /api/gravacoes/{id_}/anotacoes/{indice}",
                      "POST /api/gravacoes/{id_}/corrigir", "POST /api/gravacoes/{id_}/marcadores")},
    {"id": "acervo", "rotulo": "Acervo", "niveis": (NAO, VER), "padrao": VER,
     "prefixos": ("/api/biblioteca", "/api/acervo", "/api/arquivos", "/api/documents", "/api/documentos-abertos"),
     "destinos": ("biblioteca",),
     "consultas": _r("POST /api/biblioteca/citacao", "POST /api/biblioteca/analisar", "POST /api/biblioteca/fixar")},
    {"id": "financeiro", "rotulo": "Financeiro e relatórios", "niveis": (NAO, VER, FAZ), "padrao": NAO,
     "prefixos": ("/api/financeiro", "/api/relatorios"), "destinos": ("financeiro", "relatorios"),
     "libera_ver": _r("GET /api/financeiro", "GET /api/financeiro/lancamentos", "GET /api/financeiro/extrato",
                      "GET /api/financeiro/folha", "GET /api/financeiro/papeis", "GET /api/financeiro/fechamento",
                      "GET /api/relatorios", "GET /api/relatorios/acoes", "GET /api/relatorios/pdf"),
     "consultas": _r("POST /api/relatorios/pdf"),
     "libera_faz": _r("POST /api/financeiro/lancamentos", "POST /api/financeiro/lancamentos/{id_}/liquidar",
                      "POST /api/financeiro/lancamentos/{id_}/reabrir", "POST /api/financeiro/papeis",
                      "POST /api/financeiro/papeis/{id_}/pago", "POST /api/relatorios/pdf")},
    {"id": "aprovacoes", "rotulo": "Aprovações", "niveis": (NAO, VER, FAZ), "padrao": VER,
     "prefixos": ("/api/aprovacoes",), "destinos": ("aprovacoes",), "rotulo_faz": "aprova"},
]
POR_ID = {m["id"]: m for m in MODULOS}


def modulo_da_rota(caminho: str | None) -> dict | None:
    """O modulo a que a rota (o caminho declarado no app) pertence, se algum."""
    if not caminho:
        return None
    for m in MODULOS:
        if caminho in m.get("exatos", ()):
            return m
        for p in m["prefixos"]:
            if caminho == p or caminho.startswith(p + "/"):
                return m
    return None


def padrao() -> dict[str, str]:
    return {m["id"]: m["padrao"] for m in MODULOS}


def do_titular() -> dict[str, str]:
    return {m["id"]: m["niveis"][-1] for m in MODULOS}


def limpar(bruto) -> dict[str, str]:
    """O que foi guardado, por cima do padrao, so com niveis que o modulo oferece."""
    try:
        dados = json.loads(bruto) if isinstance(bruto, str) else dict(bruto or {})
    except (TypeError, ValueError):
        dados = {}
    saida = padrao()
    for mid, nivel in (dados or {}).items():
        m = POR_ID.get(mid)
        if m and nivel in m["niveis"]:
            saida[mid] = nivel
    return saida


def efetivas(papel: str, guardadas) -> dict[str, str]:
    return do_titular() if papel == "titular" else limpar(guardadas)


def politica_efetiva(sessao: dict, metodo: str, caminho_da_rota: str | None, politica: str) -> tuple[str, str]:
    """
    A politica que vale para ESTA pessoa nesta rota: (politica, motivo). O
    motivo so vem quando a resposta e 403 por causa do nivel.
    """
    m = modulo_da_rota(caminho_da_rota)
    if m is None:
        return politica, ""
    niveis = sessao.get("permissoes") or efetivas(sessao.get("papel", ""), {})
    nivel = niveis.get(m["id"], m["padrao"])
    chave = ("GET" if metodo == "HEAD" else metodo, caminho_da_rota)
    if nivel == NAO:
        return politicas.BLOQUEADO, f"você não tem acesso a {m['rotulo']}; o titular libera em Configurações › Acesso de fora"
    if politica == politicas.BLOQUEADO:
        if nivel == FAZ and chave in m.get("libera_faz", set()):
            return politicas.PERMITIDO, ""
        if ORDEM.index(nivel) >= ORDEM.index(VER) and chave in m.get("libera_ver", set()):
            return politicas.PERMITIDO, ""
        return politica, ""
    le = metodo in SEGUROS or chave in m.get("consultas", set()) or politica == politicas.DOWNLOAD
    if nivel == VER and not le:
        return politicas.BLOQUEADO, f"você só pode ver {m['rotulo']}; o titular libera em Configurações › Acesso de fora"
    if nivel == FAZ and politica in (politicas.PROPOR, politicas.TITULAR):
        return politicas.PERMITIDO, ""
    return politica, ""


def para_a_tela(niveis: dict[str, str]) -> list[dict]:
    """Os modulos com os niveis que oferecem e o escolhido - a grade de Configuracoes."""
    return [{"id": m["id"], "rotulo": m["rotulo"], "nivel": niveis.get(m["id"], m["padrao"]),
             "niveis": [{"id": n, "rotulo": m.get("rotulo_faz", ROTULOS[n]) if n == FAZ else ROTULOS[n]}
                        for n in m["niveis"]],
             "destinos": list(m["destinos"])} for m in MODULOS]
