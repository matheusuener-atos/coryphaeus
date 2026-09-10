"""
PAULUS Legal - Backend web (FastAPI).

Serve a interface e expoe a mesma logica do CLI por HTTP. Roda so em
localhost: o navegador precisa estar na mesma maquina que o Ollama, e nenhum
documento sai daqui.

    python src/api.py
    http://localhost:8000
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

import requests

import recursos
from classify import Classificacao, ROTULOS, classificar_acervo
from extract import SUPPORTED_SUFFIXES, index_all_contracts
from jobs import AGUARDANDO, CONCLUIDO, EXECUTANDO, Etapa, Trabalhos, titular
from llama_client import DEFAULT_MODEL, LlamaClient, OllamaError, check_ollama
from organize import (
    PADROES_SUGERIDOS,
    aplicar_plano,
    desfazer,
    listar_diarios,
    montar_plano,
)
from scan import escanear, raizes_sugeridas
from search import ContractSearcher

BASE_DIR = Path(__file__).parent.parent
CONTRACTS_DIR = BASE_DIR / "data" / "test_contracts"
CACHE_PATH = BASE_DIR / "data" / "extractions" / "index.json"
CLASSIFICACAO_PATH = BASE_DIR / "data" / "extractions" / "classificacao.json"
DIARIOS_DIR = BASE_DIR / "data" / "diarios"
TRABALHOS_DIR = BASE_DIR / "data" / "trabalhos"
FRONTEND_DIR = BASE_DIR / "frontend"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class Estado:
    """Indice em memoria, compartilhado entre as requisicoes."""

    def __init__(self) -> None:
        self.searcher = ContractSearcher()
        self.pasta = CONTRACTS_DIR
        self.porta = 8000
        self.client = LlamaClient()
        # Organizador: resultado da ultima varredura/classificacao, por caminho.
        self.encontrados: list[dict] = []
        self.classificacoes: dict[str, Classificacao] = {}
        # Conversas persistidas e o interruptor "ir devagar".
        self.trabalhos = Trabalhos(TRABALHOS_DIR)
        self.devagar = False

    def recarregar(self, *, force: bool = False) -> int:
        docs = index_all_contracts(self.pasta, CACHE_PATH, force=force, verbose=False)
        searcher = ContractSearcher()
        searcher.add_contracts(docs)
        searcher.build()
        self.searcher = searcher
        return len(docs)


estado = Estado()


@asynccontextmanager
async def lifespan(app: FastAPI):
    estado.pasta.mkdir(parents=True, exist_ok=True)
    total = estado.recarregar()
    print(f"\n  PAULUS Legal - abra http://localhost:{estado.porta}")
    print(f"  {total} contrato(s) carregado(s) de {estado.pasta}\n")
    yield


app = FastAPI(title="PAULUS Legal", docs_url="/api/docs", lifespan=lifespan)


# ------------------------------------------------------------------ modelos


class Pergunta(BaseModel):
    pergunta: str
    top: int = 6


class Busca(BaseModel):
    termo: str
    top: int = 8


# ------------------------------------------------------------------- rotas


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/classico")
def classico() -> FileResponse:
    """Interface anterior, ainda com o organizador. Sai quando ele for portado."""
    return FileResponse(FRONTEND_DIR / "classico.html")


@app.get("/fontes.css")
def fontes_css() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "fontes.css", media_type="text/css")


@app.get("/fontes/{arquivo}")
def fonte(arquivo: str) -> FileResponse:
    # Nome vem do proprio CSS que servimos; ainda assim, nada de subir pastas.
    alvo = (FRONTEND_DIR / "fontes" / Path(arquivo).name).resolve()
    if alvo.parent != (FRONTEND_DIR / "fontes").resolve() or not alvo.exists():
        raise HTTPException(status_code=404, detail="fonte nao encontrada")
    return FileResponse(alvo, media_type="font/woff2")


@app.get("/api/status")
def status() -> dict:
    ok, mensagem = check_ollama(estado.client.model)
    return {
        "ollama": ok,
        "mensagem": mensagem,
        "modelo": estado.client.model,
        # A interface nunca mostra o nome do modelo (regra de linguagem do
        # manual): mostra "Assistente local - X GB na sua maquina".
        "tamanho_gb": _tamanho_do_modelo(),
        "pasta": str(estado.pasta),
        "contratos": len(estado.searcher.documents),
        "trechos": len(estado.searcher.chunks),
    }


def _tamanho_do_modelo() -> float | None:
    try:
        resp = requests.get(f"{estado.client.host}/api/tags", timeout=5)
        resp.raise_for_status()
        for modelo in resp.json().get("models", []):
            if modelo.get("name") == estado.client.model:
                return round(modelo.get("size", 0) / 1024**3, 1)
    except (requests.RequestException, ValueError):
        return None
    return None


@app.get("/api/documents")
def documentos() -> dict:
    return {
        "documentos": [
            {"nome": d.name, "chars": d.chars, "paginas": d.pages}
            for d in estado.searcher.documents
        ]
    }


@app.post("/api/reindex")
def reindexar() -> dict:
    return {"contratos": estado.recarregar(force=True)}


@app.post("/api/search")
def buscar(payload: Busca) -> dict:
    hits = estado.searcher.search(payload.termo, top_k=payload.top)
    return {
        "resultados": [
            {
                "documento": h.doc_name,
                "trecho": h.chunk.index + 1,
                "score": round(h.score, 2),
                "snippet": h.snippet,
                "texto": h.chunk.text,
            }
            for h in hits
        ]
    }


@app.post("/api/upload")
async def upload(arquivos: list[UploadFile]) -> dict:
    salvos: list[str] = []
    recusados: list[dict] = []

    for arquivo in arquivos:
        nome = Path(arquivo.filename or "").name  # descarta qualquer caminho
        if not nome:
            continue
        if Path(nome).suffix.lower() not in SUPPORTED_SUFFIXES:
            recusados.append({"nome": nome, "motivo": "formato nao suportado"})
            continue

        conteudo = await arquivo.read()
        if len(conteudo) > MAX_UPLOAD_BYTES:
            recusados.append({"nome": nome, "motivo": "arquivo maior que 50 MB"})
            continue

        (estado.pasta / nome).write_bytes(conteudo)
        salvos.append(nome)

    total = estado.recarregar()
    return {"salvos": salvos, "recusados": recusados, "contratos": total}


@app.post("/api/ask")
def perguntar(payload: Pergunta) -> StreamingResponse:
    """Responde em streaming (SSE): primeiro as fontes, depois os tokens."""
    if not payload.pergunta.strip():
        raise HTTPException(status_code=400, detail="pergunta vazia")

    hits = estado.searcher.search(payload.pergunta, top_k=payload.top)

    def evento(tipo: str, dados: dict) -> str:
        return f"event: {tipo}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"

    def gerar() -> Iterator[str]:
        if not hits:
            yield evento("vazio", {"mensagem": "Nenhum trecho relevante encontrado nos contratos."})
            return

        # Cobertura explicita: o advogado precisa saber quais contratos NAO
        # entraram na analise. Silencio aqui vira prazo perdido.
        consultados = list(dict.fromkeys(h.doc_name for h in hits))
        ignorados = [d.name for d in estado.searcher.documents if d.name not in consultados]

        yield evento(
            "fontes",
            {
                "consultados": consultados,
                "ignorados": ignorados,
                "total_contratos": len(estado.searcher.documents),
                "trechos": [
                    {
                        "documento": h.doc_name,
                        "trecho": h.chunk.index + 1,
                        "score": round(h.score, 2),
                        "texto": h.chunk.text,
                    }
                    for h in hits
                ],
            },
        )

        contexto = estado.searcher.format_context(hits)
        try:
            for token in _tokens(payload.pergunta, contexto):
                yield evento("token", {"t": token})
        except OllamaError as exc:
            yield evento("erro", {"mensagem": str(exc)})
            return

        yield evento("fim", {})

    return StreamingResponse(
        gerar(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ------------------------------------------------------ trabalhos (conversas)


class NovoTrabalho(BaseModel):
    pedido: str = ""
    tipo: str = "conversa"


class Ajuste2(BaseModel):
    devagar: bool


@app.get("/api/trabalhos")
def trabalhos_listar() -> dict:
    dados = estado.trabalhos.listar()
    dados["pendencias"] = estado.trabalhos.pendencias
    return dados


@app.post("/api/trabalhos")
def trabalhos_criar(payload: NovoTrabalho) -> dict:
    titulo = titular(payload.pedido) if payload.pedido.strip() else "Nova conversa"
    trabalho = estado.trabalhos.criar(titulo, tipo=payload.tipo)
    return trabalho.to_dict()


@app.get("/api/trabalhos/{id_}")
def trabalhos_obter(id_: str) -> dict:
    trabalho = estado.trabalhos.obter(id_)
    if not trabalho:
        raise HTTPException(status_code=404, detail="trabalho nao encontrado")
    return trabalho.to_dict()


@app.delete("/api/trabalhos/{id_}")
def trabalhos_remover(id_: str) -> dict:
    if not estado.trabalhos.remover(id_):
        raise HTTPException(status_code=404, detail="trabalho nao encontrado")
    return {"removido": id_}


@app.post("/api/trabalhos/{id_}/perguntar")
def trabalhos_perguntar(id_: str, payload: Pergunta) -> StreamingResponse:
    """
    Pergunta dentro de um trabalho: a conversa fica gravada e as etapas
    aparecem na tela enquanto acontecem.
    """
    trabalho = estado.trabalhos.obter(id_)
    if not trabalho:
        raise HTTPException(status_code=404, detail="trabalho nao encontrado")
    if not payload.pergunta.strip():
        raise HTTPException(status_code=400, detail="pergunta vazia")

    pergunta = payload.pergunta.strip()
    if trabalho.titulo == "Nova conversa" and not trabalho.mensagens:
        trabalho.titulo = titular(pergunta)

    trabalho.dizer("pessoa", pergunta)
    trabalho.etapas = [
        Etapa("Procurar nos contratos", estado=EXECUTANDO),
        Etapa("Ler os trechos e responder"),
    ]
    trabalho.estado = EXECUTANDO
    estado.trabalhos.salvar(trabalho)

    def evento(tipo: str, dados: dict) -> str:
        return f"event: {tipo}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"

    def gerar() -> Iterator[str]:
        import time

        inicio = time.time()
        espera = recursos.esperar_maquina_livre(estado.devagar)
        if espera:
            trabalho.registrar(f"Esperou {espera}s: voce estava usando o computador")
            yield evento("etapas", {"etapas": [asdict_etapa(e) for e in trabalho.etapas]})

        hits = estado.searcher.search(pergunta, top_k=payload.top)
        trabalho.etapas[0].estado = CONCLUIDO
        trabalho.etapas[0].detalhe = f"{len(estado.searcher.documents)} contrato(s) abertos"
        trabalho.registrar(f"Procurou em {len(estado.searcher.documents)} contrato(s)")

        if not hits:
            trabalho.etapas[1].estado = CONCLUIDO
            trabalho.estado = CONCLUIDO
            texto = "Nao achei nada sobre isso nos contratos abertos."
            trabalho.dizer("paulus", texto)
            estado.trabalhos.salvar(trabalho)
            yield evento("vazio", {"mensagem": texto})
            return

        consultados = list(dict.fromkeys(h.doc_name for h in hits))
        ignorados = [d.name for d in estado.searcher.documents if d.name not in consultados]
        cobertura = {
            "consultados": consultados,
            "ignorados": ignorados,
            "total_contratos": len(estado.searcher.documents),
        }
        fontes = [
            {
                "documento": h.doc_name,
                "trecho": h.chunk.index + 1,
                "score": round(h.score, 2),
                "texto": h.chunk.text,
            }
            for h in hits
        ]

        trabalho.etapas[1].estado = EXECUTANDO
        trabalho.etapas[1].total = len(hits)
        trabalho.etapas[1].feitos = len(hits)
        trabalho.registrar(f"Leu {len(hits)} trecho(s) de {len(consultados)} contrato(s)")

        yield evento("fontes", {**cobertura, "trechos": fontes})
        yield evento("etapas", {"etapas": [asdict_etapa(e) for e in trabalho.etapas]})

        partes: list[str] = []
        contexto = estado.searcher.format_context(hits)
        try:
            for token in _tokens(pergunta, contexto):
                partes.append(token)
                yield evento("token", {"t": token})
        except OllamaError as exc:
            trabalho.etapas[1].estado = "falhou"
            trabalho.estado = "falhou"
            estado.trabalhos.salvar(trabalho)
            yield evento("erro", {"mensagem": str(exc)})
            return

        segundos = round(time.time() - inicio, 1)
        trabalho.etapas[1].estado = CONCLUIDO
        trabalho.estado = CONCLUIDO
        trabalho.dizer(
            "paulus", "".join(partes).strip(),
            fontes=fontes, cobertura=cobertura, segundos=segundos,
        )
        estado.trabalhos.salvar(trabalho)
        yield evento("fim", {"segundos": segundos, "titulo": trabalho.titulo})

    return StreamingResponse(
        gerar(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def asdict_etapa(etapa: Etapa) -> dict:
    return {
        "titulo": etapa.titulo,
        "estado": etapa.estado,
        "feitos": etapa.feitos,
        "total": etapa.total,
        "detalhe": etapa.detalhe,
    }


# ------------------------------------------------------------------ maquina


@app.get("/api/recursos")
def maquina() -> dict:
    dados = recursos.ler()
    dados["devagar"] = estado.devagar
    return dados


@app.post("/api/config")
def configurar(payload: Ajuste2) -> dict:
    estado.devagar = payload.devagar
    return {"devagar": estado.devagar}


# --------------------------------------------------------------- organizador


class Escaneamento(BaseModel):
    raizes: list[str]
    excluir: list[str] = []
    profundidade: int | None = None


class Ajuste(BaseModel):
    """Correcao feita pelo usuario na tabela, antes de montar o plano."""

    arquivo: str
    cliente: str | None = None
    tipo: str | None = None


class PedidoPlano(BaseModel):
    destino: str
    padrao: str
    ajustes: list[Ajuste] = []
    incluir_baixa_confianca: bool = True
    apenas: list[str] = []          # caminhos marcados; vazio = todos


class PedidoDesfazer(BaseModel):
    diario: str


@app.get("/api/organizar/opcoes")
def organizar_opcoes() -> dict:
    return {
        "raizes": raizes_sugeridas(),
        "padroes": PADROES_SUGERIDOS,
        "tipos": [{"valor": k, "rotulo": v} for k, v in ROTULOS.items()],
        "destino_sugerido": str(Path.home() / "Documentos" / "Acervo PAULUS"),
        "diarios": listar_diarios(DIARIOS_DIR),
    }


@app.post("/api/organizar/escanear")
def organizar_escanear(payload: Escaneamento) -> dict:
    if not payload.raizes:
        raise HTTPException(status_code=400, detail="nenhuma pasta escolhida")

    varredura = escanear(
        [Path(r) for r in payload.raizes],
        excluir=payload.excluir,
        profundidade=payload.profundidade,
    )
    estado.encontrados = [
        {"path": a.path, "nome": a.nome, "pasta": a.pasta, "suffix": a.suffix, "mb": round(a.mb, 2)}
        for a in varredura.arquivos
    ]
    return {
        "total": varredura.total,
        "pastas_visitadas": varredura.pastas_visitadas,
        "sem_permissao": len(varredura.sem_permissao),
        "grandes": len(varredura.ignorados_por_tamanho),
        "arquivos": estado.encontrados[:500],
    }


@app.post("/api/organizar/classificar")
def organizar_classificar() -> StreamingResponse:
    """Classifica o que foi encontrado, publicando o andamento por SSE."""
    caminhos = [a["path"] for a in estado.encontrados]
    if not caminhos:
        raise HTTPException(status_code=400, detail="nada para classificar - faca a varredura antes")

    def evento(tipo: str, dados: dict) -> str:
        return f"event: {tipo}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"

    def gerar() -> Iterator[str]:
        import queue
        import threading

        fila: queue.Queue = queue.Queue()
        FIM = object()

        def progresso(indice: int, total: int, nome: str, do_cache: bool) -> None:
            fila.put({"indice": indice, "total": total, "nome": nome, "cache": do_cache})

        def rodar() -> None:
            try:
                resultados = classificar_acervo(
                    caminhos,
                    cache_path=CLASSIFICACAO_PATH,
                    client=estado.client,
                    progresso=progresso,
                )
                estado.classificacoes = {r.arquivo: r for r in resultados}
                fila.put({"__resultados__": [r.to_dict() for r in resultados]})
            except Exception as exc:
                fila.put({"__erro__": str(exc)})
            finally:
                fila.put(FIM)

        threading.Thread(target=rodar, daemon=True).start()

        while True:
            item = fila.get()
            if item is FIM:
                return
            if "__erro__" in item:
                yield evento("erro", {"mensagem": item["__erro__"]})
            elif "__resultados__" in item:
                yield evento("resultados", {"documentos": item["__resultados__"]})
            else:
                yield evento("progresso", item)

    return StreamingResponse(
        gerar(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _com_ajustes(payload: PedidoPlano) -> list[Classificacao]:
    """Aplica as correcoes do usuario sobre a ultima classificacao."""
    ajustes = {a.arquivo: a for a in payload.ajustes}
    selecao = set(payload.apenas)
    saida: list[Classificacao] = []

    for caminho, resultado in estado.classificacoes.items():
        if selecao and caminho not in selecao:
            continue

        ajuste = ajustes.get(caminho)
        if ajuste:
            # Copia rasa para nao gravar a correcao no cache de classificacao:
            # ela vale para este plano, nao para o documento.
            resultado = Classificacao(**{**resultado.__dict__})
            if ajuste.cliente is not None:
                resultado.cliente = ajuste.cliente
            if ajuste.tipo is not None:
                resultado.tipo = ajuste.tipo

        saida.append(resultado)

    return saida


@app.post("/api/organizar/plano")
def organizar_plano(payload: PedidoPlano) -> dict:
    if not estado.classificacoes:
        raise HTTPException(status_code=400, detail="classifique os documentos antes")
    if not payload.destino.strip():
        raise HTTPException(status_code=400, detail="informe a pasta de destino")

    plano = montar_plano(
        _com_ajustes(payload),
        Path(payload.destino),
        payload.padrao,
        incluir_baixa_confianca=payload.incluir_baixa_confianca,
    )
    return plano.to_dict()


@app.post("/api/organizar/aplicar")
def organizar_aplicar(payload: PedidoPlano) -> dict:
    """Move os arquivos. So daqui para baixo o disco e alterado."""
    if not estado.classificacoes:
        raise HTTPException(status_code=400, detail="classifique os documentos antes")

    plano = montar_plano(
        _com_ajustes(payload),
        Path(payload.destino),
        payload.padrao,
        incluir_baixa_confianca=payload.incluir_baixa_confianca,
    )
    if not plano.movimentos:
        raise HTTPException(status_code=400, detail="o plano nao tem nenhum movimento")

    resultado = aplicar_plano(plano, DIARIOS_DIR)
    estado.classificacoes = {}
    estado.encontrados = []
    return {
        "movidos": resultado.movidos,
        "falhas": resultado.falhas,
        "diario": resultado.diario,
        "diarios": listar_diarios(DIARIOS_DIR),
    }


@app.post("/api/organizar/desfazer")
def organizar_desfazer(payload: PedidoDesfazer) -> dict:
    caminho = Path(payload.diario)
    # So diarios criados por este programa - nao aceita caminho arbitrario.
    if caminho.parent.resolve() != DIARIOS_DIR.resolve() or not caminho.exists():
        raise HTTPException(status_code=400, detail="diario desconhecido")

    resultado = desfazer(caminho)
    return {
        "revertidos": resultado.movidos,
        "falhas": resultado.falhas,
        "diarios": listar_diarios(DIARIOS_DIR),
    }


def _tokens(pergunta: str, contexto: str) -> Iterator[str]:
    """
    Converte o callback de streaming do LlamaClient em iterador.

    O cliente entrega token por callback; a resposta SSE precisa puxar. Uma
    fila com uma thread faz a ponte sem carregar a resposta inteira na memoria.
    """
    import queue
    import threading

    fila: queue.Queue = queue.Queue()
    FIM = object()

    def rodar() -> None:
        try:
            estado.client.ask(pergunta, contexto, stream=True, on_token=fila.put)
        except Exception as exc:  # repassa para a thread principal
            fila.put(exc)
        finally:
            fila.put(FIM)

    thread = threading.Thread(target=rodar, daemon=True)
    thread.start()

    while True:
        item = fila.get()
        if item is FIM:
            return
        if isinstance(item, Exception):
            raise item
        yield item


def main() -> None:
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="PAULUS Legal - interface web (local)")
    parser.add_argument("--contracts", type=Path, default=CONTRACTS_DIR, help="pasta com os contratos")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"modelo Ollama (padrao: {DEFAULT_MODEL})")
    parser.add_argument("--port", type=int, default=8000, help="porta (padrao: 8000)")
    args = parser.parse_args()

    estado.pasta = args.contracts
    estado.porta = args.port
    estado.client = LlamaClient(model=args.model)

    # host fixo em 127.0.0.1: o servidor nao deve ficar exposto na rede local,
    # os documentos sao de cliente.
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
