"""
Ligar e desligar as chaves da Biblioteca e das ideias do umbrelOS pela tela
(Configurações). Cada mudança de comportamento nasceu atrás de uma chave em
config.PADRAO; aqui a pessoa liga e desliga, uma por vez, só na janela do
escritório (de fora, bloqueado em src/acesso/politicas.py).

Moram aqui, e não no api.py: o api.py só chama `montar`.
"""

from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel

import config

# Os blocos que esta rota mexe, e só as chaves que o PADRAO conhece. `tau` e
# afins não entram: número se ajusta medindo, não pela tela.
BLOCOS = ("biblioteca", "umbrel")


class Chave(BaseModel):
    bloco: str
    chave: str
    ligada: bool


def montar(estado, app) -> None:
    @app.get("/api/chaves")
    def chaves_listar() -> dict:
        return {b: {k: bool((estado.prefs.dados.get(b) or {}).get(k)) for k in config.PADRAO[b]} for b in BLOCOS}

    @app.post("/api/chaves")
    def chaves_mudar(payload: Chave) -> dict:
        if payload.bloco not in BLOCOS or payload.chave not in config.PADRAO[payload.bloco]:
            raise HTTPException(status_code=400, detail="essa chave não existe")
        estado.prefs.atualizar({payload.bloco: {payload.chave: bool(payload.ligada)}})
        return chaves_listar()
