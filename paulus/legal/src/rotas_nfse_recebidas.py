"""
PAULUS - As rotas das NFS-e que o PAVLVS emitiu para este escritório
(src/nfse_recebidas.py). O api.py só chama montar().

  GET /api/nfse-recebidas              {notas: [...]} (vazia sem a conta da nuvem)
  GET /api/nfse-recebidas/{id}/pdf     o PDF, como anexo "NFS-e <numero>.pdf"
  GET /api/nfse-recebidas/{id}/xml     o XML, como anexo "NFS-e <numero>.xml"

Só da janela do escritório (src/acesso/politicas.py), como Plano e consumo.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import HTTPException
from fastapi.responses import Response

import nfse_recebidas
import nuvem


def montar(estado, app) -> None:
    central = getattr(estado, "central_avisos", None)
    if central is not None:
        central.estado_nuvem = estado

    @app.get("/api/nfse-recebidas")
    def nfse_recebidas_lista(forcar: bool = False) -> dict:
        return {"notas": nfse_recebidas.listar(estado, forcar=forcar)}

    def _arquivo(id_: str, tipo: str) -> Response:
        try:
            dados, nome, ctype = nfse_recebidas.arquivo(estado, id_, tipo)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except nuvem.ErroNuvem as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        disp = f"attachment; filename=\"{nome}\"; filename*=UTF-8''{quote(nome)}"
        return Response(content=dados, media_type=ctype, headers={"Content-Disposition": disp, "Cache-Control": "no-store"})

    @app.get("/api/nfse-recebidas/{id_}/pdf")
    def nfse_recebida_pdf(id_: str) -> Response:
        return _arquivo(id_, "pdf")

    @app.get("/api/nfse-recebidas/{id_}/xml")
    def nfse_recebida_xml(id_: str) -> Response:
        return _arquivo(id_, "xml")
