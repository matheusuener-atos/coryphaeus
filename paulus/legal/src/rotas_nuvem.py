"""
As rotas da nuvem com a chave do escritório (N15, src/nuvem.py).

Todas só na janela do escritório (src/acesso/politicas.py): de fora não se
guarda chave, não se liga a nuvem e não se libera conversa.
"""

from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel

import nuvem


class Chave(BaseModel):
    provedor: str = "anthropic"
    chave: str = ""


class Configurar(BaseModel):
    ligado: bool | None = None
    provedor: str | None = None
    modelo: str | None = None
    mascarar: bool | None = None


class Liberar(BaseModel):
    liberada: bool = True


def _estado_da_tela(estado) -> dict:
    import segredos

    c = nuvem.config(estado)
    provedor = c.get("provedor") or "anthropic"
    return {
        "ligado": bool(c.get("ligado")),
        "ligada": nuvem.ligada(estado),
        "provedor": provedor,
        "modelo": c.get("modelo") or "",
        "mascarar": bool(c.get("mascarar", True)),
        "provedores": [{"id": k, "nome": v["nome"], "padrao": v["padrao"], "tem_chave": bool(nuvem.chave(estado, k))}
                       for k, v in nuvem.PROVEDORES.items()],
        "sem_pedir": estado.prefs.pode("modelo_nuvem"),
        "dpapi": segredos.disponivel(),
        "envios": len(nuvem.envios(estado, limite=500)),
    }


def montar(estado, app, dados_dir) -> None:
    estado.dados_dir = Path(dados_dir)

    @app.get("/api/nuvem")
    def nuvem_estado() -> dict:
        return _estado_da_tela(estado)

    @app.post("/api/nuvem/chave")
    def nuvem_guardar_chave(payload: Chave) -> dict:
        """Guarda cifrada e testa (a única chamada: a lista de modelos que a chave enxerga)."""
        try:
            nuvem.guardar_chave(estado, payload.provedor, payload.chave)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            modelos = nuvem.testar(estado, payload.provedor)
        except nuvem.ErroNuvem as exc:
            nuvem.apagar_chave(estado, payload.provedor)
            raise HTTPException(status_code=400, detail=f"não guardei a chave: {exc}") from exc
        atual = nuvem.config(estado)
        novo = {"provedor": payload.provedor}
        if atual.get("provedor") != payload.provedor or not atual.get("modelo") or atual.get("modelo") not in modelos:
            padrao = nuvem.PROVEDORES[payload.provedor]["padrao"]
            novo["modelo"] = padrao if padrao in modelos else (modelos[0] if modelos else "")
        estado.prefs.atualizar({"nuvem": novo})
        return dict(_estado_da_tela(estado), modelos=modelos)

    @app.get("/api/nuvem/modelos")
    def nuvem_modelos(provedor: str = "") -> dict:
        provedor = provedor or nuvem.config(estado).get("provedor") or "anthropic"
        if provedor not in nuvem.PROVEDORES:
            raise HTTPException(status_code=400, detail="provedor desconhecido")
        try:
            return {"modelos": nuvem.testar(estado, provedor)}
        except nuvem.ErroNuvem as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/nuvem/chave/{provedor}")
    def nuvem_apagar_chave(provedor: str) -> dict:
        if provedor not in nuvem.PROVEDORES:
            raise HTTPException(status_code=400, detail="provedor desconhecido")
        nuvem.apagar_chave(estado, provedor)
        if nuvem.config(estado).get("provedor") == provedor:
            estado.prefs.atualizar({"nuvem": {"ligado": False}})
        return _estado_da_tela(estado)

    @app.post("/api/nuvem/configurar")
    def nuvem_configurar(payload: Configurar) -> dict:
        novo: dict = {}
        if payload.provedor is not None:
            if payload.provedor not in nuvem.PROVEDORES:
                raise HTTPException(status_code=400, detail="provedor desconhecido")
            novo["provedor"] = payload.provedor
        if payload.modelo is not None:
            novo["modelo"] = payload.modelo.strip()[:120]
        if payload.mascarar is not None:
            novo["mascarar"] = bool(payload.mascarar)
        if payload.ligado is not None:
            novo["ligado"] = bool(payload.ligado)
        estado.prefs.atualizar({"nuvem": novo})
        if payload.ligado and not nuvem.ligada(estado):
            estado.prefs.atualizar({"nuvem": {"ligado": False}})
            raise HTTPException(status_code=400, detail="para ligar, guarde e teste a chave do provedor e escolha o modelo")
        return _estado_da_tela(estado)

    @app.post("/api/trabalhos/{id_}/nuvem")
    def nuvem_liberar_conversa(id_: str, payload: Liberar) -> dict:
        """Libera (ou volta a pedir) a nuvem nesta conversa: as próximas perguntas marcadas "Nuvem" vão sem pedir."""
        trabalho = estado.trabalhos.obter(id_)
        if trabalho is None:
            raise HTTPException(status_code=404, detail="conversa não encontrada")
        trabalho.contexto["nuvem_liberada"] = bool(payload.liberada)
        estado.trabalhos.salvar(trabalho)
        return {"liberada": bool(payload.liberada)}

    @app.get("/api/nuvem/envios")
    def nuvem_envios(limite: int = 30) -> dict:
        return {"envios": nuvem.envios(estado, limite=max(1, min(limite, 200)))}

    @app.get("/api/nuvem/envios/{envio}")
    def nuvem_envio(envio: str) -> dict:
        """O texto exato que saiu nesse envio."""
        if not envio.isalnum():
            raise HTTPException(status_code=400, detail="envio inválido")
        arq = Path(estado.dados_dir) / "nuvem" / "envios" / f"{envio}.txt"
        if not arq.exists():
            raise HTTPException(status_code=404, detail="envio não encontrado")
        return {"envio": envio, "texto": arq.read_text(encoding="utf-8")}
