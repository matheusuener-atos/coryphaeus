"""
PAULUS - As rotas das execucoes (src/execucoes.py). O api.py so chama montar().

  GET /api/execucoes/{id}/eventos?desde=n   inscricao (SSE): o que houve depois
                                             de n, e depois ao vivo, ate o fim
  GET /api/trabalhos/{id}/execucao          a execucao desta conversa (a que
                                             roda, ou a ultima), para a tela
                                             se reinscrever ao voltar
"""

from __future__ import annotations

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

CABECALHOS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def ligada(estado, nome: str) -> bool:
    return bool((estado.prefs.dados.get("conversa") or {}).get(nome))


def resposta_sse(gerador) -> StreamingResponse:
    return StreamingResponse(gerador, media_type="text/event-stream", headers=CABECALHOS)


def rodar_conversa(estado, conversa_id: str, dono: str, eventos) -> StreamingResponse:
    """
    A resposta da conversa como execucao: `eventos` (o gerador de sempre) roda
    numa thread de trabalho, e quem pediu recebe uma inscricao desde o
    comeco. Fechar a janela encerra a inscricao; a resposta continua.
    """
    execucao = estado.execucoes.criar(conversa_id=conversa_id, dono=dono, tipo="conversa")
    # O primeiro evento diz o id: e por ele que a tela se reinscreve.
    execucao.acrescentar("execucao", {"conversa_id": conversa_id})
    estado.execucoes.rodar(execucao, eventos)
    return resposta_sse(estado.execucoes.inscrever(execucao, 0))


def montar(estado, app) -> None:
    @app.get("/api/execucoes/{id_}/eventos")
    def execucao_eventos(id_: str, desde: int = 0) -> StreamingResponse:
        execucao = estado.execucoes.obter(id_)
        if execucao is None:
            raise HTTPException(status_code=404, detail="execução não encontrada (o programa foi reaberto depois dela?)")
        return resposta_sse(estado.execucoes.inscrever(execucao, desde))

    @app.get("/api/trabalhos/{id_}/execucao")
    def trabalho_execucao(id_: str) -> dict:
        if not estado.trabalhos.obter(id_):
            raise HTTPException(status_code=404, detail="conversa não encontrada")
        execucao = estado.execucoes.da_conversa(id_)
        return {"execucao": execucao.resumo() if execucao else None}
