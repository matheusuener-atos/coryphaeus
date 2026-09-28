"""
As rotas de "quem acessou" (R8). So na janela local: e o registro de quem
entrou de fora, e quem esta de fora nao le nem exporta o registro de si mesmo.
"""

from __future__ import annotations

from datetime import date

from fastapi import Request
from fastapi.responses import Response

from acesso.auditoria import ACOES
from acesso.rotas import so_local


def montar(servico, r) -> None:
    @r.get("/api/acesso/auditoria")
    def auditoria_listar(request: Request, pessoa: str = "", acao: str = "", de: str = "", ate: str = "",
                         texto: str = "", limite: int = 500) -> dict:
        so_local(request)
        linhas = servico.auditoria.filtrar(pessoa=pessoa, acao=acao, de=de, ate=ate, texto=texto)
        conferencia = servico.auditoria.verificar()
        return {"linhas": list(reversed(linhas))[:max(1, min(limite, 5000))], "total": len(linhas),
                "integro": conferencia["integro"], "quebra_na_linha": conferencia["linha"],
                "linhas_no_arquivo": conferencia["total"], "acoes": ACOES}

    @r.get("/api/acesso/auditoria/pdf")
    def auditoria_pdf(request: Request, pessoa: str = "", acao: str = "", de: str = "", ate: str = "",
                      texto: str = "") -> Response:
        so_local(request)
        linhas = servico.auditoria.filtrar(pessoa=pessoa, acao=acao, de=de, ate=ate, texto=texto)
        nome = f"acessos-de-fora-{date.today().isoformat()}.pdf"
        return Response(servico.auditoria.pdf(linhas), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{nome}"'})
