"""
PAULUS - As rotas dos agentes do escritorio (src/agentes.py, A1). O api.py so
chama montar().

  GET  /api/agentes                       a lista (com os com problema), os
                                           catalogos e se a chave esta ligada
  GET  /api/agentes/{slug}                a ficha e o markdown inteiro (e o
                                           original, se importado)
  GET  /api/agentes/{slug}/versoes/{n}    uma versao guardada
  POST /api/agentes                       criar: {markdown}
  PUT  /api/agentes/{slug}                salvar: {markdown}; guarda a anterior
  POST /api/agentes/{slug}/ativar         ligar; importado pede {vi_o_conteudo: true}
  POST /api/agentes/{slug}/desativar      desligar
  POST /api/agentes/importar              {markdown, nome_arquivo}; entra desligado
  POST /api/agentes/{slug}/testar         roda os `testes` do agente

Criar, salvar, ligar e importar so na janela do escritorio ou pelo titular
(TITULAR em src/acesso/politicas.py); listar, ler e testar, qualquer pessoa
com sessao - no celular a lista e o teste funcionam (A3).

A chave e `conversa.agentes`. Desligada, as rotas que mudam alguma coisa (e o
teste, que ocupa o modelo) respondem 409 e a lista diz `ligado: false`. Ela
nao muda nada na conversa: nesta etapa nenhum agente entra nela (A2).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import HTTPException, Request

import agentes as agentes_mod
import ferramentas as ferramentas_mod
from acesso import rotas as rotas_do_acesso
from fila_modelo import FilaCheia
from habilidade_base import COM_PROBLEMA

DESLIGADOS = "os agentes estão desligados (conversa.agentes)"
AVISO_DO_TESTE = ("o teste roda cada pergunta pela conversa, com as instruções do agente e o perfil de modelo "
                  "dele; nenhuma ferramenta é executada")


def ligada(estado) -> bool:
    return bool((estado.prefs.dados.get("conversa") or {}).get("agentes"))


def _exigir_ligada(estado) -> None:
    if not ligada(estado):
        raise HTTPException(status_code=409, detail=DESLIGADOS)


def _http(exc: agentes_mod.ErroDeAgente) -> HTTPException:
    if isinstance(exc, agentes_mod.AgenteNaoEncontrado):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, agentes_mod.ConflitoDeAgente):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


def _markdown(payload: dict | None) -> str:
    texto = (payload or {}).get("markdown")
    if not isinstance(texto, str) or not texto.strip():
        raise HTTPException(status_code=400, detail="mande o conteúdo do AGENTE.md em 'markdown'")
    return texto


def texto_da_resposta(saida) -> str:
    """
    O texto que a pessoa leria, a partir do que a habilidade de perguntar
    devolve - a mesma conta de tools/medir.py: os pedacos escritos mais as
    mensagens sem modelo; com a conferencia das marcas (evento `revisao`), o
    texto conferido e o que veio depois dele.
    """
    if isinstance(saida, dict):
        return str(saida.get("resposta") or saida.get("mensagem") or "")
    eventos = list(saida or [])
    erro = next((d.get("mensagem") for t, d in eventos if t == "erro"), None)
    if erro:
        raise RuntimeError(str(erro))
    texto = "".join(d.get("t", "") for t, d in eventos if t == "token") + \
        "".join(d.get("mensagem", "") for t, d in eventos if t == "vazio")
    revisao = [i for i, (t, _) in enumerate(eventos) if t == "revisao"]
    if revisao:
        i = revisao[0]
        texto = eventos[i][1].get("texto", "") + "".join(d.get("t", "") for t, d in eventos[i:] if t == "token")
    return texto


def montar(estado, app, pasta: Path | str, contexto: Callable[[str], object]) -> None:
    """
    `pasta` e onde moram os agentes (DADOS_DIR / "agentes"); `contexto(tarefa)`
    e o Contexto das habilidades para aquele perfil de modelo, que so o api.py
    sabe montar.
    """
    estado.agentes = agentes_mod.Agentes(
        pasta,
        # As listas vivas: a habilidade recarregada vale na proxima leitura.
        capacidades=lambda: [h.id for h in estado.registro.habilidades if h.estado != COM_PROBLEMA],
        ferramentas=lambda: ferramentas_mod.CATALOGO_FERRAMENTAS,
    )

    def quem(request: Request | None) -> str:
        p = rotas_do_acesso.pessoa(request)
        return str(p.get("nome") or p.get("email") or "titular") if p else "janela do escritório"

    def dono(request: Request | None) -> str:
        p = rotas_do_acesso.pessoa(request)
        return f"conta:{p['conta_id']}" if p else "local"

    @app.get("/api/agentes")
    def agentes_listar() -> dict:
        lista = estado.agentes.listar()
        return {
            "ligado": ligada(estado),
            "agentes": [a.ficha() for a in lista],
            "contagem": {"total": len(lista), "em_uso": sum(1 for a in lista if a.em_uso),
                         "com_problema": sum(1 for a in lista if a.problema)},
            "catalogos": estado.agentes.catalogos(),
            "pasta": str(estado.agentes.pasta),
        }

    @app.get("/api/agentes/{slug}")
    def agentes_ler(slug: str) -> dict:
        try:
            return estado.agentes.ler(slug)
        except agentes_mod.ErroDeAgente as exc:
            raise _http(exc) from exc

    @app.get("/api/agentes/{slug}/versoes/{n}")
    def agentes_versao(slug: str, n: int) -> dict:
        try:
            return {"slug": slug, "versao": n, "markdown": estado.agentes.ler_versao(slug, n)}
        except agentes_mod.ErroDeAgente as exc:
            raise _http(exc) from exc

    @app.post("/api/agentes")
    def agentes_criar(payload: dict | None = None) -> dict:
        _exigir_ligada(estado)
        try:
            return estado.agentes.criar(_markdown(payload)).ficha()
        except agentes_mod.ErroDeAgente as exc:
            raise _http(exc) from exc

    @app.put("/api/agentes/{slug}")
    def agentes_salvar(slug: str, payload: dict | None = None) -> dict:
        _exigir_ligada(estado)
        try:
            return estado.agentes.salvar(slug, _markdown(payload)).ficha()
        except agentes_mod.ErroDeAgente as exc:
            raise _http(exc) from exc

    @app.post("/api/agentes/{slug}/ativar")
    def agentes_ativar(slug: str, payload: dict | None = None, request: Request = None) -> dict:
        _exigir_ligada(estado)
        try:
            # So `true` de verdade conta: "sim", 1 ou um campo esquecido nao aprovam.
            vi = (payload or {}).get("vi_o_conteudo") is True
            return estado.agentes.ativar(slug, vi_o_conteudo=vi, por=quem(request)).ficha()
        except agentes_mod.ErroDeAgente as exc:
            raise _http(exc) from exc

    @app.post("/api/agentes/{slug}/desativar")
    def agentes_desativar(slug: str) -> dict:
        _exigir_ligada(estado)
        try:
            return estado.agentes.desativar(slug).ficha()
        except agentes_mod.ErroDeAgente as exc:
            raise _http(exc) from exc

    @app.post("/api/agentes/importar")
    def agentes_importar(payload: dict | None = None) -> dict:
        _exigir_ligada(estado)
        try:
            nome_arquivo = str((payload or {}).get("nome_arquivo") or "")[:200]
            return estado.agentes.importar(_markdown(payload), nome_arquivo=nome_arquivo).ficha()
        except agentes_mod.ErroDeAgente as exc:
            raise _http(exc) from exc

    @app.post("/api/agentes/{slug}/testar")
    def agentes_testar(slug: str, request: Request = None) -> dict:
        """
        Os `testes` do agente pela habilidade de perguntar de sempre, SEM as
        instrucoes dele: e isso que o resultado diz, porque e o que acontece
        ate a A2. Cada pergunta entra na fila do modelo como qualquer outra.
        """
        _exigir_ligada(estado)
        habilidade = estado.registro.obter("perguntar")
        if habilidade is None or not habilidade.executavel:
            motivo = (habilidade.problema if habilidade else "") or "a habilidade de perguntar não está pronta"
            raise HTTPException(status_code=409, detail=motivo)
        de_quem = dono(request)

        def rodar(pergunta: str, agente) -> str:
            try:
                vez = estado.fila_modelo.entrar(de_quem, rotulo=f"Teste do agente {agente.nome}")
            except FilaCheia as exc:
                raise RuntimeError(str(exc)) from exc
            try:
                if not estado.fila_modelo.esperar(vez, timeout=600):
                    raise RuntimeError("o modelo ficou ocupado demais; tente de novo")
                # A2: o teste roda com as instrucoes do agente (e o escopo dele
                # vale na conversa); ferramenta nenhuma e executada aqui.
                import agente_na_conversa

                ctx = contexto(agente.modelo)
                ctx.agente_instrucoes = agente_na_conversa.instrucoes(agente)
                return texto_da_resposta(habilidade.executar(ctx, pergunta=pergunta))
            finally:
                estado.fila_modelo.sair(vez)

        try:
            resultado = estado.agentes.testar(slug, rodar)
        except agentes_mod.ErroDeAgente as exc:
            raise _http(exc) from exc
        return {**resultado, "aviso": AVISO_DO_TESTE, "perfil": estado.agentes.obter(slug).modelo}
