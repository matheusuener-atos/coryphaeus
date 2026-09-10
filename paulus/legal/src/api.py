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

from extract import SUPPORTED_SUFFIXES, index_all_contracts
from llama_client import DEFAULT_MODEL, LlamaClient, OllamaError, check_ollama
from search import ContractSearcher

BASE_DIR = Path(__file__).parent.parent
CONTRACTS_DIR = BASE_DIR / "data" / "test_contracts"
CACHE_PATH = BASE_DIR / "data" / "extractions" / "index.json"
FRONTEND_DIR = BASE_DIR / "frontend"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class Estado:
    """Indice em memoria, compartilhado entre as requisicoes."""

    def __init__(self) -> None:
        self.searcher = ContractSearcher()
        self.pasta = CONTRACTS_DIR
        self.porta = 8000
        self.client = LlamaClient()

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


@app.get("/api/status")
def status() -> dict:
    ok, mensagem = check_ollama(estado.client.model)
    return {
        "ollama": ok,
        "mensagem": mensagem,
        "modelo": estado.client.model,
        "pasta": str(estado.pasta),
        "contratos": len(estado.searcher.documents),
        "trechos": len(estado.searcher.chunks),
    }


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
