"""
PAULUS - As rotas da Central de avisos (src/central_avisos.py, T2). O api.py
so chama montar().

  GET  /api/central-avisos/hoje        o carrossel: o que a pessoa da vez ainda nao viu
  GET  /api/central-avisos             a aba Todos: ?tipo=&periodo=hoje|semana|mes
  POST /api/central-avisos/visto       {id} marca como visto (nao conclui nada)
  POST /api/central-avisos/desmarcar   {id} apaga o visto: o aviso volta ao carrossel
  GET  /api/central-avisos/historico   quem viu, quando, de onde e o que dizia

Com a chave `conversa.avisos` desligada, as rotas de leitura respondem
{ligado: false} e a tela nao desenha nada; as de gravar, 404.

De fora (acesso-remoto), as rotas sao PERMITIDO - marcar como visto e so da
propria pessoa -, e o que cada pessoa recebe segue as permissoes das rotas
de origem: quem nao ve o Financeiro nao recebe aviso de conta.
"""

from __future__ import annotations

from fastapi import HTTPException, Request
from pydantic import BaseModel

import central_avisos
import equipe
from acesso import permissoes, politicas
from acesso import rotas as rotas_do_acesso


class Visto(BaseModel):
    id: str


def ligada(estado) -> bool:
    # A chave mora no bloco `conversa` das preferencias (src/config.py);
    # sem ela declarada, desligada.
    return bool((estado.prefs.dados.get("conversa") or {}).get("avisos"))


def quem(estado, request: Request | None) -> dict:
    """A pessoa da vez: a janela do escritorio (o titular) ou a conta de fora."""
    p = rotas_do_acesso.pessoa(request)
    if p:
        return {"pessoa": f"conta:{int(p['conta_id'])}", "nome": str(p.get("nome") or ""), "de_onde": "remoto",
                "titular": p.get("papel") == "titular", "politica": politica_de(p)}
    nome = equipe.quem(None, estado.prefs.dados)["nome"]
    return {"pessoa": "local", "nome": nome, "de_onde": "local", "titular": True, "politica": None}


def politica_de(sessao: dict):
    """
    O que a pessoa de fora pode numa rota, pela mesma conta do porteiro
    (a tabela da R3 e o nivel de cada modulo): "permitido", "propor" ou
    None. Titular so vale para o titular.
    """
    def pode(metodo: str, rota: str) -> str | None:
        pol = politicas.de(metodo, rota)
        pol, _ = permissoes.politica_efetiva(sessao, metodo, rota, pol)
        if pol == politicas.BLOQUEADO:
            return None
        if pol == politicas.TITULAR:
            return "permitido" if sessao.get("papel") == "titular" else None
        return pol
    return pode


def montar(estado, app, classificados=None) -> None:
    central = central_avisos.Central(
        estado.base, agenda=estado.agenda, tarefas=estado.tarefas, financeiro=estado.financeiro,
        publicacoes=estado.publicacoes, fila=estado.fila, trabalhos=estado.trabalhos, bem_estar=estado.bem_estar,
        classificados=classificados, disponibilidade=lambda: estado.prefs.dados.get("disponibilidade") or {})
    estado.central_avisos = central
    # A notificacao do Windows e o cartao sao o mesmo aviso: o Vigia, que
    # roda na maquina do escritorio, nao avisa de novo o que a janela local
    # ja marcou como visto.
    estado.vigia.visto = lambda aviso_id: ligada(estado) and central.visto(aviso_id, "local")

    def _conferir() -> None:
        if not ligada(estado):
            raise HTTPException(status_code=404, detail="a Central de avisos está desligada")

    @app.get("/api/central-avisos/hoje")
    def avisos_hoje(request: Request = None) -> dict:
        if not ligada(estado):
            return {"ligado": False, "avisos": []}
        q = quem(estado, request)
        avisos = central.do_dia(q["pessoa"], politica=q["politica"])
        return {"ligado": True, "avisos": avisos, "faltou": list(central.falhas)}

    @app.get("/api/central-avisos")
    def avisos_todos(tipo: str = "", periodo: str = "semana", request: Request = None) -> dict:
        if not ligada(estado):
            return {"ligado": False, "avisos": []}
        q = quem(estado, request)
        avisos = central.todos(q["pessoa"], tipo=tipo, periodo=periodo, politica=q["politica"])
        return {"ligado": True, "avisos": avisos, "tipos": central_avisos.tipos_para_tela(),
                "periodos": [{"id": "hoje", "rotulo": "Hoje"}, {"id": "semana", "rotulo": "7 dias"},
                             {"id": "mes", "rotulo": "30 dias"}],
                "faltou": list(central.falhas)}

    @app.post("/api/central-avisos/visto")
    def avisos_visto(payload: Visto, request: Request = None) -> dict:
        _conferir()
        q = quem(estado, request)
        try:
            aviso = central.marcar(payload.id, q["pessoa"], nome=q["nome"], de_onde=q["de_onde"],
                                   politica=q["politica"])
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"aviso": aviso, "avisos": central.do_dia(q["pessoa"], politica=q["politica"])}

    @app.post("/api/central-avisos/desmarcar")
    def avisos_desmarcar(payload: Visto, request: Request = None) -> dict:
        _conferir()
        q = quem(estado, request)
        if not central.desmarcar(payload.id, q["pessoa"]):
            raise HTTPException(status_code=404, detail="esse aviso não estava marcado como visto por você")
        return {"avisos": central.do_dia(q["pessoa"], politica=q["politica"])}

    @app.get("/api/central-avisos/historico")
    def avisos_historico(request: Request = None) -> dict:
        if not ligada(estado):
            return {"ligado": False, "itens": []}
        q = quem(estado, request)
        return {"ligado": True, "titular": q["titular"], "tipos": central_avisos.tipos_para_tela(),
                "itens": central.historico(q["pessoa"], titular=q["titular"])}
