"""Servidor da prova da W0 (rascunho; não é o PAULUS).

Serve a página do suplemento e um /api/status de mentira, e guarda o que a
página relatar em relatos.jsonl. Sobe em HTTPS (montagem A) e, se pedido,
também em HTTP (o lado 127.0.0.1 da montagem B).

Uso:
  python servidor.py https <porta> <pasta-do-certificado> <pasta-dos-relatos>
  python servidor.py http  <porta> - <pasta-dos-relatos>
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response

AQUI = Path(__file__).resolve().parent
modo, porta, pasta_cert, pasta_relatos = sys.argv[1], int(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
pasta_relatos.mkdir(parents=True, exist_ok=True)

app = FastAPI()


def _cors(resp: Response, request: Request) -> Response:
    origem = request.headers.get("origin")
    if origem:
        resp.headers["Access-Control-Allow-Origin"] = origem
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Headers"] = "content-type, authorization"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        # Private Network Access / Local Network Access: a resposta ao
        # preflight precisa dizer que aceita ser chamada de origem pública.
        resp.headers["Access-Control-Allow-Private-Network"] = "true"
    return resp


def _registra(tipo: str, request: Request, dados=None) -> None:
    linha = {
        "quando": datetime.now().isoformat(timespec="seconds"), "tipo": tipo, "servidor": f"{modo}:{porta}",
        "caminho": request.url.path, "origem": request.headers.get("origin"),
        "pna": request.headers.get("access-control-request-private-network"),
        "ua": request.headers.get("user-agent", "")[:160], "dados": dados,
    }
    with open(pasta_relatos / "relatos.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")


@app.options("/{caminho:path}")
async def preflight(caminho: str, request: Request):
    _registra("preflight", request)
    return _cors(Response(status_code=204), request)


@app.get("/api/status")
async def status(request: Request):
    _registra("status", request)
    return _cors(JSONResponse({"ok": True, "prova": True, "servidor": f"{modo}:{porta}"}), request)


@app.get("/word/prova/{nome}")
async def arquivo(nome: str, request: Request):
    if nome not in ("pagina.html", "pagina.js"):
        return Response(status_code=404)
    _registra("pagina", request, {"nome": nome, "query": str(request.url.query)})
    resp = FileResponse(AQUI / nome)
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.post("/word/prova/relato")
async def relato(request: Request):
    _registra("relato", request, await request.json())
    return _cors(JSONResponse({"ok": True}), request)


if __name__ == "__main__":
    kw = {}
    if modo == "https":
        kw = {"ssl_certfile": str(Path(pasta_cert) / "servidor.pem"), "ssl_keyfile": str(Path(pasta_cert) / "servidor.key")}
    uvicorn.run(app, host="127.0.0.1", port=porta, log_level="warning", **kw)
