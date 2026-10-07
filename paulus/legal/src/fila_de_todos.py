"""
A fila do modelo à vista, e a pergunta que espera dentro da conversa (F1,
docs/PROGRESSO-APARELHO.md). Tudo atrás da chave `aparelho.fila`.

- **Quem pede** (`QuemPedeAoModelo`): a cada requisição, dono ("local" ou
  "conta:<id>"), primeiro nome e a origem pela rota ("conversa", "editor",
  "e-mail"...). O cliente do modelo lê isso ao entrar na fila
  (src/fila_modelo.py); thread sem requisição é o segundo plano.
- **A pergunta que espera na conversa**: mandada com outra resposta andando
  na mesma conversa, ela não some mais. Fica guardada no servidor, na
  conversa (`contexto["pendentes"]`), com um lugar de verdade na fila; quando
  a vez chega e a resposta anterior termina, vai sozinha - no contexto de
  quem a mandou (o filtro de Serviços e a pessoa vão junto). O programa
  reiniciou no meio: ela fica "não enviada", com enviar e descartar - mandar
  sozinha sem o contexto de quem pediu seria mandar sem o filtro dele.
- **Prioridade** (Ctrl+Enter): sempre passa na frente das próprias perguntas
  e do segundo plano; na frente de outras pessoas só com o nível "passa na
  frente" dado pelo titular (Acesso de fora › Contas), até
  `aparelho.prioridade_por_hora` vezes por hora. A janela do escritório é o
  titular. Toda prioridade vai para o registro de acessos.
- **A fila inteira** (GET /api/fila): só na janela do escritório. Nome e
  origem, nunca o texto.
"""

from __future__ import annotations

import contextvars
import threading
import time
import uuid
from collections import deque
from types import SimpleNamespace

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import fila_modelo

# A origem pela rota: o que quem espera lê ("Helena · editor").
ORIGENS = (
    ("/api/trabalhos", "conversa"), ("/api/servicos", "serviços"), ("/api/documentos", "editor"),
    ("/api/redacao", "editor"), ("/api/planilha", "planilha"), ("/api/email", "e-mail"),
    ("/api/gravacoes", "gravação"), ("/api/relatorios", "parecer"), ("/api/financeiro", "financeiro"),
    ("/api/agentes", "agentes"), ("/api/biblioteca", "acervo"), ("/api/organizar", "organizar"),
    ("/api/cadastros", "cadastros"), ("/api/contextos", "biblioteca"), ("/api/modelos", "modelos"),
    ("/api/habilidades", "habilidades"),
)
ORIGEM_DO_TIPO = {"parecer": "parecer", "resumo_gravacao": "resumo de gravação", "reescrever_email": "e-mail"}
PRIORIDADE_POR_HORA = 3


def ligada(estado) -> bool:
    return bool((estado.prefs.dados.get("aparelho") or {}).get("fila"))


def origem_da_rota(caminho: str) -> str:
    if caminho.startswith("/api/ia/"):
        return ORIGEM_DO_TIPO.get(caminho.split("/")[3] if len(caminho.split("/")) > 3 else "", "outra tela")
    for prefixo, origem in ORIGENS:
        if caminho == prefixo or caminho.startswith(prefixo + "/"):
            return origem
    return "outra tela"


def primeiro_nome(nome: str) -> str:
    return (str(nome or "").strip().split() or [""])[0]


class QuemPedeAoModelo:
    """
    Middleware ASGI, por dentro do porteiro: põe em `fila_modelo.PEDIDO` quem
    fez esta requisição. Por dentro, porque é o porteiro que diz se é de fora.
    """

    def __init__(self, app, nome_local=None) -> None:
        self.app = app
        self.nome_local = nome_local or (lambda: "")

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") == "http" and str(scope.get("path", "")).startswith("/api/"):
            p = (scope.get("state") or {}).get("paulus_pessoa")
            if p:
                pedido = {"dono": f"conta:{p['conta_id']}", "nome": primeiro_nome(p.get("nome", "")) or "alguém"}
            else:
                try:
                    nome = primeiro_nome(self.nome_local())
                except Exception:  # noqa: BLE001
                    nome = ""
                pedido = {"dono": "local", "nome": nome or "Escritório"}
            pedido["origem"] = origem_da_rota(scope["path"])
            fila_modelo.PEDIDO.set(pedido)
        await self.app(scope, receive, send)


# ------------------------------------------------------------ prioridade

_USOS: dict[str, deque] = {}
_trava_usos = threading.Lock()


def decidir_prioridade(estado, request, dono: str, pediu: bool) -> dict:
    """
    {"tipo": "" | "propria" | "geral", "aviso": ""}. "geral" só com o nível do
    titular e dentro do limite por hora; senão "propria", com a razão.
    """
    if not pediu or not ligada(estado):
        return {"tipo": "", "aviso": ""}
    from acesso import rotas as rotas_do_acesso

    pessoa = rotas_do_acesso.pessoa(request)
    liberada = pessoa is None or (pessoa.get("permissoes") or {}).get("prioridade") == "faz"
    if not liberada:
        return {"tipo": "propria",
                "aviso": "com prioridade só entre as suas perguntas: passar na frente de outras pessoas "
                         "depende do titular"}
    limite = int((estado.prefs.dados.get("aparelho") or {}).get("prioridade_por_hora") or PRIORIDADE_POR_HORA)
    agora = time.time()
    with _trava_usos:
        usos = _USOS.setdefault(dono, deque())
        while usos and agora - usos[0] > 3600:
            usos.popleft()
        if len(usos) >= limite:
            return {"tipo": "propria",
                    "aviso": f"você já passou na frente {limite} vezes nesta hora: esta vai com prioridade "
                             "só entre as suas perguntas"}
        usos.append(agora)
    return {"tipo": "geral", "aviso": ""}


def anotar_prioridade(estado, request, tipo: str, origem: str = "conversa") -> None:
    """Toda prioridade vai para o registro de acessos (src/acesso/auditoria.py)."""
    if not tipo:
        return
    from acesso import rotas as rotas_do_acesso

    pessoa = rotas_do_acesso.pessoa(request) or {}
    alvo = ("passou na frente da fila" if tipo == "geral" else "passou na frente das próprias perguntas") + \
        f" ({origem})"
    try:
        estado.acesso_de_fora.anotar(acao="prioridade", alvo=alvo, pessoa=pessoa.get("nome") or "janela local",
                                     email=pessoa.get("email", ""))
    except Exception:  # noqa: BLE001 - o registro não derruba a pergunta
        pass


# ------------------------------------------- a pergunta que espera na conversa

# pid -> {"vez", "contexto", "request"}: só na memória, enquanto o programa roda.
_VIVAS: dict[str, dict] = {}
_trava = threading.Lock()
# A classe da pergunta da rota (api.Pergunta), dada em `montar`.
_PERGUNTA: dict = {"classe": None}


def _pendentes(trabalho) -> list[dict]:
    return trabalho.contexto.setdefault("pendentes", [])


def _pessoa_da_requisicao(request) -> SimpleNamespace | None:
    """O que a rota de perguntar lê do `request` (quem é, se é local), sem a requisição, que já acabou."""
    if request is None:
        return None
    estado_req = dict(request.scope.get("state") or {})
    return SimpleNamespace(scope={"state": {"paulus_pessoa": estado_req.get("paulus_pessoa"),
                                            "paulus_local": estado_req.get("paulus_local")}})


def guardar(estado, trabalho, payload, request, dono: str, prioridade: dict, perguntar) -> JSONResponse:
    """
    A conversa já está respondendo: a pergunta fica na conversa, com um lugar
    na fila, e vai sozinha na vez. A 3ª da mesma pessoa é recusada antes de
    qualquer coisa ser guardada.
    """
    pedido = fila_modelo.PEDIDO.get() or {}
    try:
        vez = estado.fila_modelo.entrar(dono, rotulo="conversa", origem="conversa",
                                        nome=pedido.get("nome", ""), prioridade=prioridade.get("tipo", ""))
    except fila_modelo.FilaCheia as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    pid = uuid.uuid4().hex[:12]
    dados = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
    registro = {"id": pid, "texto": dados.pop("pergunta", "").strip(), "dono": dono, "nome": pedido.get("nome", ""),
                "criada": time.strftime("%Y-%m-%dT%H:%M:%S"), "prioridade": prioridade.get("tipo", ""),
                "estado": "na_fila",
                "payload": {k: v for k, v in dados.items() if k not in ("retomar", "prioridade")}}
    with _trava:
        _pendentes(trabalho).append(registro)
        estado.trabalhos.salvar(trabalho)
        _VIVAS[pid] = {"vez": vez, "request": _pessoa_da_requisicao(request),
                       # O contexto de quem mandou (filtro de Serviços, pessoa,
                       # origem): a pergunta vai com ele, e não com o de ninguém.
                       "contexto": contextvars.copy_context()}
    viva = _VIVAS[pid]
    threading.Thread(target=viva["contexto"].run, args=(_esperar_e_mandar, estado, trabalho.id, pid, perguntar),
                     name=f"pendente-{pid}", daemon=True).start()
    return JSONResponse(status_code=202, content={"pendente": para_tela(estado, registro, dono),
                                                  "aviso": prioridade.get("aviso", "")})


def _esperar_e_mandar(estado, trabalho_id: str, pid: str, perguntar) -> None:
    viva = _VIVAS.get(pid)
    if not viva:
        return
    vez = viva["vez"]
    fila = estado.fila_modelo
    while not fila.esperar(vez, timeout=0.5):
        if vez.saiu:          # cancelada
            return
    # A vez chegou; a resposta anterior desta conversa larga o lugar e a
    # marca de "respondendo" quase ao mesmo tempo.
    limite = time.time() + 30
    while estado.respondendo.get(trabalho_id) and time.time() < limite:
        time.sleep(0.2)
    with _trava:
        trabalho = estado.trabalhos.obter(trabalho_id)
        registro = None
        if trabalho is not None:
            lista = _pendentes(trabalho)
            registro = next((r for r in lista if r["id"] == pid), None)
            if registro is not None:
                lista.remove(registro)
                estado.trabalhos.salvar(trabalho)
        _VIVAS.pop(pid, None)
    if registro is None or not registro["texto"]:
        fila.sair(vez)
        return
    try:
        # A vez desta thread (fila_modelo.VEZ) vai para a execução: a resposta
        # não entra de novo no fim da fila.
        perguntar(trabalho_id, _PERGUNTA["classe"](pergunta=registro["texto"], **registro["payload"]), viva["request"])
    except Exception:  # noqa: BLE001 - a conversa mostra que não foi
        fila.sair(vez)
        with _trava:
            trabalho = estado.trabalhos.obter(trabalho_id)
            if trabalho is not None:
                _pendentes(trabalho).append({**registro, "estado": "interrompida", "motivo": "não consegui mandar"})
                estado.trabalhos.salvar(trabalho)


def para_tela(estado, registro: dict, dono: str) -> dict:
    """O que a bolha mostra. O texto só para quem escreveu."""
    viva = _VIVAS.get(registro["id"])
    sua = registro.get("dono") == dono
    saida = {"id": registro["id"], "nome": registro.get("nome", ""), "sua": sua,
             "criada": registro.get("criada", ""), "prioridade": registro.get("prioridade", ""),
             "estado": registro.get("estado", "na_fila") if viva or registro.get("estado") != "na_fila" else "interrompida",
             "texto": registro["texto"] if sua else ""}
    if viva and not viva["vez"].saiu:
        saida.update(estado.fila_modelo.para_evento(viva["vez"]))
    elif saida["estado"] == "interrompida":
        saida["motivo"] = registro.get("motivo") or "o Paulus reiniciou antes de mandar"
    return saida


def recuperar(estado) -> int:
    """Na abertura: o que estava na fila não tem mais lugar nela - fica "não enviada"."""
    n = 0
    for trabalho in list(getattr(estado.trabalhos, "_itens", {}).values()):
        mudou = False
        for r in trabalho.contexto.get("pendentes") or []:
            if r.get("estado") == "na_fila" and r["id"] not in _VIVAS:
                r["estado"], r["motivo"] = "interrompida", "o Paulus reiniciou antes de mandar"
                mudou = True
                n += 1
        if mudou:
            estado.trabalhos.salvar(trabalho)
    return n


class Editar(BaseModel):
    texto: str


def montar(estado, app, dono_da_vez, pergunta_cls) -> None:
    _PERGUNTA["classe"] = pergunta_cls

    @app.get("/api/trabalhos/{id_}/pendentes")
    def pendentes_listar(id_: str, request: Request = None) -> dict:
        trabalho = estado.trabalhos.obter(id_)
        if not trabalho:
            raise HTTPException(status_code=404, detail="conversa não encontrada")
        dono = dono_da_vez(request)
        return {"pendentes": [para_tela(estado, r, dono) for r in trabalho.contexto.get("pendentes") or []],
                "fila_ligada": ligada(estado)}

    def _do_dono(id_: str, pid: str, request):
        trabalho = estado.trabalhos.obter(id_)
        registro = next((r for r in (trabalho.contexto.get("pendentes") or []) if r["id"] == pid), None) if trabalho else None
        if registro is None or registro.get("dono") != dono_da_vez(request):
            raise HTTPException(status_code=404, detail="essa pergunta não está mais na fila")
        return trabalho, registro

    @app.put("/api/trabalhos/{id_}/pendentes/{pid}")
    def pendentes_editar(id_: str, pid: str, payload: Editar, request: Request = None) -> dict:
        texto = payload.texto.strip()
        if not texto:
            raise HTTPException(status_code=400, detail="pergunta vazia")
        with _trava:
            trabalho, registro = _do_dono(id_, pid, request)
            registro["texto"] = texto
            estado.trabalhos.salvar(trabalho)
        return {"pendente": para_tela(estado, registro, dono_da_vez(request))}

    @app.delete("/api/trabalhos/{id_}/pendentes/{pid}")
    def pendentes_cancelar(id_: str, pid: str, request: Request = None) -> dict:
        with _trava:
            trabalho, registro = _do_dono(id_, pid, request)
            trabalho.contexto["pendentes"].remove(registro)
            estado.trabalhos.salvar(trabalho)
            viva = _VIVAS.pop(pid, None)
        if viva:
            estado.fila_modelo.sair(viva["vez"])
        return {"cancelada": pid}

    @app.get("/api/fila")
    def fila_inteira(request: Request = None) -> dict:
        """A fila inteira, só na janela do escritório: quem, de onde, há quanto tempo. Nunca o texto."""
        from acesso import rotas as rotas_do_acesso

        rotas_do_acesso.so_local(request)
        return {"fila": estado.fila_modelo.foto(), "ligada": ligada(estado)}

    recuperar(estado)
