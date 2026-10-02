"""
As rotas da nuvem (N15 com a chave do escritório; V1-V7 com o PAULUS (nuvem),
docs/PLANO-NUVEM.md; src/nuvem.py).

Quase todas só na janela do escritório (src/acesso/politicas.py): de fora não
se guarda chave, não se dá nem se retira o sim, não se ativa nem se paga.
De fora só passa `GET /api/nuvem/situacao`, o pouco que a caixa da pergunta
precisa para mostrar a pílula "Nuvem" (V5).
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
    pedir_cada_envio: bool | None = None
    tarefas: dict | None = None


class Liberar(BaseModel):
    liberada: bool = True


class Consentimento(BaseModel):
    aceito: bool = True
    versao: str = ""


class Email(BaseModel):
    email: str = ""


def _estado_da_tela(estado) -> dict:
    import segredos

    c = nuvem.config(estado)
    provedor = c.get("provedor") or "paulus"
    sim = c.get("consentimento") or {}
    tarefas = {t: bool((c.get("tarefas") or {}).get(t, True)) for t in nuvem.TAREFAS}
    return {
        "ligado": bool(c.get("ligado")),
        "ligada": nuvem.ligada(estado),
        "provedor": provedor,
        "modelo": c.get("modelo") or "",
        "mascarar": bool(c.get("mascarar", True)),
        "pedir_cada_envio": bool(c.get("pedir_cada_envio")),
        "tarefas": tarefas,
        "nomes_tarefas": nuvem.TAREFAS,
        "consentido": nuvem.consentido(estado),
        "consentimento": sim if sim.get("versao") else None,
        "termo_versao": nuvem.TERMO_VERSAO,
        "provedores": [{"id": k, "nome": v["nome"], "padrao": v["padrao"], "tem_chave": bool(nuvem.chave(estado, k)),
                        "assinatura": bool(v.get("assinatura"))}
                       for k, v in nuvem.PROVEDORES.items()],
        "sem_pedir": estado.prefs.pode("modelo_nuvem"),
        "dpapi": segredos.disponivel(),
        "envios": len(nuvem.envios(estado, limite=500)),
    }


def _nome_de_quem(estado) -> str:
    v = estado.prefs.dados.get("vinculo") or {}
    p = estado.prefs.dados.get("pessoa") or {}
    return str(v.get("nome") or p.get("nome") or v.get("email") or "titular")


def _conta(estado, forcar: bool = False) -> dict:
    try:
        return {"conta": nuvem.conta_paulus(estado, forcar=forcar), "erro": ""}
    except nuvem.ErroNuvem as exc:
        return {"conta": None, "erro": str(exc)}


def montar(estado, app, dados_dir) -> None:
    estado.dados_dir = Path(dados_dir)

    def _paulus_ou_400(fazer):
        try:
            return fazer()
        except nuvem.ErroNuvem as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/nuvem")
    def nuvem_estado() -> dict:
        return _estado_da_tela(estado)

    @app.get("/api/nuvem/situacao")
    def nuvem_situacao() -> dict:
        """O que a caixa da pergunta precisa, de dentro e de fora: nada de chave nem de conta."""
        c = nuvem.config(estado)
        prov = c.get("provedor") or "paulus"
        return {"ligada": nuvem.usa(estado, "conversa"), "provedor": prov,
                "nome": nuvem.PROVEDORES.get(prov, {}).get("nome", prov), "modelo": c.get("modelo") or "",
                "pedir_cada_envio": bool(c.get("pedir_cada_envio"))}

    @app.get("/api/nuvem/termo")
    def nuvem_termo(provedor: str = "") -> dict:
        provedor = provedor or nuvem.config(estado).get("provedor") or "paulus"
        if provedor not in nuvem.PROVEDORES:
            raise HTTPException(status_code=400, detail="provedor desconhecido")
        return {"versao": nuvem.TERMO_VERSAO, "provedor": provedor, "nome": nuvem.PROVEDORES[provedor]["nome"],
                "texto": nuvem.termo(provedor)}

    @app.post("/api/nuvem/consentimento")
    def nuvem_consentimento(payload: Consentimento) -> dict:
        """O sim (ou o não) do titular, na janela do escritório. O sim vale para a versão do termo que ele leu."""
        quem = _nome_de_quem(estado)
        if not payload.aceito:
            nuvem.retirar(estado, quem)
            return _estado_da_tela(estado)
        if payload.versao != nuvem.TERMO_VERSAO:
            raise HTTPException(status_code=409, detail="o termo mudou desde que a tela abriu: leia de novo")
        _paulus_ou_400(lambda: nuvem.consentir(estado, quem))
        return _estado_da_tela(estado)

    @app.post("/api/nuvem/chave")
    def nuvem_guardar_chave(payload: Chave) -> dict:
        """Guarda cifrada e testa (a única chamada: a lista de modelos que a chave enxerga)."""
        if payload.provedor == "paulus":
            raise HTTPException(status_code=400, detail="o PAULUS (nuvem) não usa chave colada: ative com o Google")
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
        provedor = provedor or nuvem.config(estado).get("provedor") or "paulus"
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
        if provedor == "paulus":
            nuvem.sair_paulus(estado)
            return _estado_da_tela(estado)
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
        if payload.pedir_cada_envio is not None:
            novo["pedir_cada_envio"] = bool(payload.pedir_cada_envio)
        if payload.tarefas is not None:
            novo["tarefas"] = {t: bool(v) for t, v in payload.tarefas.items() if t in nuvem.TAREFAS}
        if payload.ligado is not None:
            novo["ligado"] = bool(payload.ligado)
        estado.prefs.atualizar({"nuvem": novo})
        if payload.ligado and not nuvem.ligada(estado):
            estado.prefs.atualizar({"nuvem": {"ligado": False}})
            if not nuvem.consentido(estado):
                raise HTTPException(status_code=400, detail="para ligar, o titular lê o termo e dá o sim")
            raise HTTPException(status_code=400, detail="para ligar, ative o provedor (ou guarde e teste a chave) e escolha o modelo")
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

    # ------------------------------------------------ o PAULUS (nuvem): conta, plano, recarga

    @app.post("/api/nuvem/paulus/ativar")
    def nuvem_paulus_ativar() -> dict:
        """A conta da nuvem é a conta Google vinculada: precisa do login recente (o id_token, 1 h)."""
        token = estado.vinculo.id_token_valido() if getattr(estado, "vinculo", None) else ""
        if not token:
            raise HTTPException(status_code=401, detail="confirme com o Google para ativar a nuvem")
        _paulus_ou_400(lambda: nuvem.ativar_paulus(estado, token, _nome_de_quem(estado)))
        return dict(_estado_da_tela(estado), **_conta(estado))

    @app.get("/api/nuvem/paulus/conta")
    def nuvem_paulus_conta(forcar: bool = False) -> dict:
        return _conta(estado, forcar=forcar)

    @app.post("/api/nuvem/paulus/assinar")
    def nuvem_paulus_assinar(payload: Email) -> dict:
        email = payload.email.strip() or str((estado.prefs.dados.get("vinculo") or {}).get("email") or "")
        return _paulus_ou_400(lambda: nuvem._paulus(estado, "POST", "/api/ia/assinar", {"email": email}))

    @app.get("/api/nuvem/paulus/assinatura")
    def nuvem_paulus_assinatura() -> dict:
        d = _paulus_ou_400(lambda: nuvem._paulus(estado, "GET", "/api/ia/assinatura"))
        nuvem._CONTA_CACHE.update(quando=0.0, dados=None)
        return {"conta": d, "erro": ""}

    @app.post("/api/nuvem/paulus/cancelar")
    def nuvem_paulus_cancelar() -> dict:
        d = _paulus_ou_400(lambda: nuvem._paulus(estado, "POST", "/api/ia/assinatura/cancelar", {}))
        nuvem._CONTA_CACHE.update(quando=0.0, dados=None)
        return {"conta": d, "erro": ""}

    @app.post("/api/nuvem/paulus/recarga")
    def nuvem_paulus_recarga(payload: Email) -> dict:
        email = payload.email.strip() or str((estado.prefs.dados.get("vinculo") or {}).get("email") or "")
        return _paulus_ou_400(lambda: nuvem._paulus(estado, "POST", "/api/ia/recarga", {"email": email}))

    @app.get("/api/nuvem/paulus/recarga/{pedido}")
    def nuvem_paulus_recarga_situacao(pedido: str) -> dict:
        if not pedido.replace("-", "").replace("_", "").isalnum():
            raise HTTPException(status_code=400, detail="pedido inválido")
        d = _paulus_ou_400(lambda: nuvem._paulus(estado, "GET", f"/api/ia/recarga/{pedido}"))
        if d.get("pago"):
            nuvem._CONTA_CACHE.update(quando=0.0, dados=None)
        return d
