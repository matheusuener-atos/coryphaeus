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
import plano
import profundidade
import recursos_do_plano


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
    # O pacote da recarga rapida (worker/ia.js: "0.5", "1", "2"); vazio, o de sempre.
    pacote: str = ""
    # O plano escolhido na tela (worker/ia.js: advogado, escritorio, plus); vazio, o da conta.
    plano: str = ""
    # "mensal" (a assinatura no cartao) ou "anual" (o ano de uma vez, parcelavel); vazio, mensal.
    periodo: str = ""


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

    @app.get("/api/plano")
    def plano_situacao(forcar: bool = False) -> dict:
        """A IA faz parte da assinatura (src/plano.py): liberada ou nao, e ate quando."""
        return {**plano.situacao(estado, forcar=forcar), "cobranca": plano.cobranca_ligada(), "frase": plano.FRASE_SEM_PLANO}

    @app.get("/api/nuvem/situacao")
    def nuvem_situacao() -> dict:
        """O que a caixa da pergunta precisa, de dentro e de fora: nada de chave nem de conta."""
        c = nuvem.config(estado)
        prov = c.get("provedor") or "paulus"
        return {"ligada": nuvem.usa(estado, "conversa"), "provedor": prov,
                "nome": nuvem.PROVEDORES.get(prov, {}).get("nome", prov), "modelo": c.get("modelo") or "",
                "pedir_cada_envio": bool(c.get("pedir_cada_envio")),
                # O seletor de profundidade (src/profundidade.py): os cinco niveis e o padrao.
                # Os niveis acima do plano vem travados (src/recursos_do_plano.py).
                "profundidade": profundidade.para_tela(estado.prefs.dados, recursos_do_plano.nivel_max(estado),
                                                       lambda n: recursos_do_plano.frase_nivel(estado, n))}

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
        corpo = {"email": email, **({"plano": payload.plano.strip()} if payload.plano.strip() else {}),
                 **({"periodo": payload.periodo.strip()} if payload.periodo.strip() else {})}
        return _paulus_ou_400(lambda: nuvem._paulus(estado, "POST", "/api/ia/assinar", corpo))

    @app.post("/api/nuvem/paulus/adiantar")
    def nuvem_paulus_adiantar() -> dict:
        """Adianta a cota da semana que vem (uma vez por mes, depois dos 7 primeiros dias; worker/ia.js)."""
        d = _paulus_ou_400(lambda: nuvem._paulus(estado, "POST", "/api/ia/adiantar", {}))
        nuvem._CONTA_CACHE.update(quando=0.0, dados=None)
        plano.esquecer()
        return {"conta": d}

    @app.post("/api/nuvem/paulus/plano")
    def nuvem_paulus_plano(payload: Email) -> dict:
        """Trocar de plano com a assinatura ativa: o valor novo e os tokens novos valem na renovacao (worker/ia.js)."""
        if not payload.plano.strip():
            raise HTTPException(status_code=400, detail="escolha o plano")
        d = _paulus_ou_400(lambda: nuvem._paulus(estado, "POST", "/api/ia/plano", {"plano": payload.plano.strip()}))
        plano.esquecer()
        return {"conta": d}

    @app.get("/api/nuvem/paulus/assinatura")
    def nuvem_paulus_assinatura() -> dict:
        d = _paulus_ou_400(lambda: nuvem._paulus(estado, "GET", "/api/ia/assinatura"))
        nuvem._CONTA_CACHE.update(quando=0.0, dados=None)
        plano.esquecer()
        return {"conta": d, "erro": ""}

    @app.post("/api/nuvem/paulus/cancelar")
    def nuvem_paulus_cancelar() -> dict:
        d = _paulus_ou_400(lambda: nuvem._paulus(estado, "POST", "/api/ia/assinatura/cancelar", {}))
        nuvem._CONTA_CACHE.update(quando=0.0, dados=None)
        plano.esquecer()
        return {"conta": d, "erro": ""}

    @app.post("/api/nuvem/paulus/recarga")
    def nuvem_paulus_recarga(payload: Email) -> dict:
        email = payload.email.strip() or str((estado.prefs.dados.get("vinculo") or {}).get("email") or "")
        corpo = {"email": email, **({"pacote": payload.pacote.strip()} if payload.pacote.strip() else {})}
        return _paulus_ou_400(lambda: nuvem._paulus(estado, "POST", "/api/ia/recarga", corpo))

    # ------------------------------------------------ Plano e consumo (src/consumo.py)

    @app.get("/api/consumo")
    def consumo_painel(forcar: bool = False) -> dict:
        """Quanto o escritorio gasta (a conta do Worker), quem gasta (o registro daqui) e os limites."""
        import consumo

        conta = _conta(estado, forcar=forcar)
        return {**conta, "painel": consumo.painel(estado), "cobranca": plano.cobranca_ligada(),
                "ligada": nuvem.ligada(estado), "ativa": bool(nuvem.chave(estado, "paulus"))}

    @app.get("/api/consumo/pessoa/{conta_id}")
    def consumo_pessoa(conta_id: int, dias: int = 31) -> dict:
        import consumo

        recursos_do_plano.exigir(estado, "consumo_por_pessoa")
        return {"conta_id": conta_id, "dias": consumo.historico(estado, conta_id, dias=max(1, min(dias, 120)))}

    @app.post("/api/consumo/limites")
    def consumo_limites(payload: dict) -> dict:
        """Os limites de uso: diario e mensal do escritorio e de cada pessoa. 0 = sem limite."""
        import consumo

        # O do escritorio e de todos; o de cada pessoa, do plano com equipe.
        if any(str((v or {}).get(k) or "").strip(" 0.,") for v in ((payload or {}).get("pessoas") or {}).values() for k in ("diario", "mensal")):
            recursos_do_plano.exigir(estado, "consumo_por_pessoa")
        return {"limites": consumo.guardar_limites(estado, payload or {}), "painel": consumo.painel(estado)}

    @app.get("/api/consumo/extrato")
    def consumo_extrato() -> dict:
        """O extrato do ciclo: por area e por pessoa, o total e o custo pela conta do plano."""
        import consumo

        return consumo.extrato(estado)

    @app.post("/api/consumo/extrato/pdf")
    def consumo_extrato_pdf() -> dict:
        """Grava o PDF do extrato no Acervo e devolve o caminho - o anexo do e-mail e o nome para baixar."""
        import html as _html

        import consumo

        try:
            arq = consumo.gravar_pdf_do_extrato(estado, _html.escape)
        except Exception as exc:  # noqa: BLE001 - a tela diz o que houve
            raise HTTPException(status_code=500, detail=f"não consegui gerar o PDF: {exc}") from exc
        if hasattr(estado, "recarregar_em_segundo_plano"):
            estado.recarregar_em_segundo_plano()
        return {"path": str(arq), "nome": arq.name, "mb": round(arq.stat().st_size / (1024 * 1024), 2)}

    @app.get("/api/consumo/extrato/arquivo")
    def consumo_extrato_arquivo(nome: str):
        """Baixar um PDF do extrato (so da pasta do extrato)."""
        from fastapi.responses import FileResponse

        alvo = Path(estado.pasta) / "Relatórios" / "Consumo da IA" / Path(nome).name
        if alvo.suffix.lower() != ".pdf" or not alvo.is_file():
            raise HTTPException(status_code=404, detail="arquivo não encontrado")
        return FileResponse(alvo, media_type="application/pdf", filename=alvo.name)

    @app.get("/api/nuvem/paulus/recarga/{pedido}")
    def nuvem_paulus_recarga_situacao(pedido: str) -> dict:
        if not pedido.replace("-", "").replace("_", "").isalnum():
            raise HTTPException(status_code=400, detail="pedido inválido")
        d = _paulus_ou_400(lambda: nuvem._paulus(estado, "GET", f"/api/ia/recarga/{pedido}"))
        if d.get("pago"):
            nuvem._CONTA_CACHE.update(quando=0.0, dados=None)
            plano.esquecer()
        return d
