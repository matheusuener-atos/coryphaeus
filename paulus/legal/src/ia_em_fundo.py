"""
PAULUS - As outras chamadas de IA como execucao (C5).

A conversa ja rodava sem depender da janela (C1). As outras telas esperavam
um minuto com um "escrevendo…" parado, sem fila, sem parar, e o resultado
morria com a tela: o parecer do Financeiro, o resumo de uma gravacao, o
"reescrever" do e-mail. Aqui elas viram execucoes do mesmo registro
(src/execucoes.py):

- a chamada pega a vez na fila do modelo (src/fila_modelo.py) - com uma
  conversa respondendo, ela espera e a tela mostra a posicao;
- roda numa thread de trabalho: sair da tela, recarregar ou fechar o programa
  nao perde o resultado, que fica no registro da execucao
  (data/execucoes/<id>.jsonl) e volta quando a tela se reinscreve;
- "parar" e pelo botao (POST /api/execucoes/{id}/parar): se o modelo ja
  estiver escrevendo, a resposta que chegar depois e descartada.

`POST /api/ia/{tipo}` com `{dados}` devolve `{execucao_id}`; a tela se inscreve
em `GET /api/execucoes/{id}/eventos` e recebe `fila`, `trabalhando` e, no fim,
`resultado` (o mesmo JSON que a rota de antes devolvia) ou `erro`.

Chave: `conversa.superficies`.
"""

from __future__ import annotations

import threading

from fastapi import HTTPException, Request

from fila_modelo import FilaCheia


def rodar(estado, tipo: str, dono: str, rotulo: str, objeto: str, funcao):
    """A chamada `funcao()` como execucao, com a vez na fila do modelo. Devolve a execucao."""
    e = estado.execucoes.criar(conversa_id=objeto, dono=dono, tipo=tipo)
    parar = threading.Event()
    estado.respondendo["exec:" + e.id] = parar

    def eventos():
        yield "execucao", {"tipo": tipo, "objeto": objeto, "rotulo": rotulo}
        try:
            vez = estado.fila_modelo.entrar(dono, rotulo=rotulo)
        except FilaCheia as exc:
            yield "erro", {"mensagem": str(exc)}
            return
        try:
            ultima = -1
            while not estado.fila_modelo.esperar(vez, timeout=0.5):
                if parar.is_set():
                    yield "parado", {}
                    return
                posicao = estado.fila_modelo.posicao(vez)
                if posicao != ultima:
                    ultima = posicao
                    yield "fila", {"posicao": posicao, "previsao_s": estado.fila_modelo.previsao(vez)}
            if parar.is_set():
                yield "parado", {}
                return
            yield "trabalhando", {"rotulo": rotulo}
            try:
                resultado = funcao()
            except HTTPException as exc:
                yield "erro", {"mensagem": str(exc.detail)}
                return
            if parar.is_set():
                # O modelo nao para no meio desta chamada: o que chegou depois
                # do "parar" nao vale.
                yield "parado", {"descartado": True}
                return
            yield "resultado", resultado if isinstance(resultado, dict) else {"valor": resultado}
            yield "fim", {}
        finally:
            estado.fila_modelo.sair(vez)
            estado.respondendo.pop("exec:" + e.id, None)

    estado.execucoes.rodar(e, eventos())
    return e


def montar(estado, app, tipos: dict, dono_de) -> None:
    """
    `tipos`: {"parecer": (rotulo, objeto(dados), funcao(dados)), ...} - a
    funcao e a rota de antes, chamada com os dados da tela.
    """
    @app.post("/api/ia/{tipo}")
    def ia_em_fundo(tipo: str, payload: dict, request: Request) -> dict:
        if not bool((estado.prefs.dados.get("conversa") or {}).get("superficies")):
            raise HTTPException(status_code=409, detail="as chamadas em segundo plano estão desligadas (conversa.superficies)")
        if tipo not in tipos:
            raise HTTPException(status_code=404, detail="não conheço esta chamada: " + tipo)
        rotulo, objeto, funcao = tipos[tipo]
        dados = dict((payload or {}).get("dados") or {})
        e = rodar(estado, tipo, dono_de(request), rotulo, objeto(dados), lambda: funcao(dados))
        return {"execucao_id": e.id, "tipo": tipo}

    @app.post("/api/execucoes/{id_}/parar")
    def execucao_parar(id_: str) -> dict:
        sinal = estado.respondendo.get("exec:" + id_)
        if sinal is None:
            e = estado.execucoes.obter(id_)
            return {"parando": False, "estado": e.estado if e else "desconhecida"}
        sinal.set()
        return {"parando": True}
