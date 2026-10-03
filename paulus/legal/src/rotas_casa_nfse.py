"""
As rotas da tela "Notas do PAVLVS" (src/casa_nfse.py).

Só existem no PAULUS da casa (casa_nfse.ligada). Fora dele, 404. Pelo túnel,
só o titular entra (src/acesso/politicas.py, nível TITULAR): é ele quem emite
as notas do PAVLVS, de qualquer lugar.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import File, Form, HTTPException, UploadFile
from pydantic import BaseModel

import casa_nfse


class Parametros(BaseModel):
    prestador: dict | None = None
    token_ponte: str = ""
    enviar_sozinho: bool | None = None


class Emitir(BaseModel):
    conta: str = ""
    pagamento: str = ""
    tomador: dict = {}
    valor: str = ""
    descricao: str = ""
    competencia: str = ""


class Tomador(BaseModel):
    tomador: dict = {}


def montar(estado, app, dados_dir) -> None:
    estado.casa_nfse = None

    def casa() -> casa_nfse.Casa:
        if not casa_nfse.ligada(estado.prefs.dados):
            raise HTTPException(status_code=404, detail="rota não existe")
        if estado.casa_nfse is None:
            estado.casa_nfse = casa_nfse.Casa(Path(dados_dir))
        return estado.casa_nfse

    def erro(exc: Exception, status: int = 400):
        raise HTTPException(status_code=status, detail=str(exc)) from exc

    @app.get("/api/casa-nfse/disponivel")
    def casa_disponivel() -> dict:
        return {"ligada": casa_nfse.ligada(estado.prefs.dados)}

    @app.get("/api/casa-nfse/municipios")
    def casa_municipios(q: str = "") -> dict:
        from nfse import tabelas

        casa()
        return {"itens": tabelas.buscar_municipios(q, "", limite=12)}

    @app.get("/api/casa-nfse")
    def casa_estado() -> dict:
        return casa().para_tela()

    @app.post("/api/casa-nfse/certificado")
    async def casa_certificado(arquivo: UploadFile = File(...), senha: str = Form("")) -> dict:
        c = casa()
        conteudo = await arquivo.read()
        if not conteudo or len(conteudo) > 64 * 1024:
            raise HTTPException(status_code=400, detail="o arquivo não parece um certificado A1 (.pfx)")
        try:
            c.emissor.instalar_certificado(arquivo.filename or "a1.pfx", conteudo, senha, True)
        except ValueError as exc:
            erro(exc)
        return c.para_tela()

    @app.post("/api/casa-nfse/certificado/remover")
    def casa_certificado_remover() -> dict:
        c = casa()
        c.emissor.remover_certificado()
        return c.para_tela()

    @app.post("/api/casa-nfse/parametros")
    def casa_parametros(payload: Parametros) -> dict:
        c = casa()
        try:
            c.gravar_parametros(payload.model_dump(exclude_none=True), quem="titular")
        except ValueError as exc:
            erro(exc)
        return c.para_tela()

    @app.post("/api/casa-nfse/testar")
    def casa_testar() -> dict:
        return casa().testar()

    @app.get("/api/casa-nfse/clientes")
    def casa_clientes() -> dict:
        try:
            return {"clientes": casa().clientes()}
        except casa_nfse.ErroPonte as exc:
            erro(exc, 502)

    @app.post("/api/casa-nfse/clientes/{conta}")
    def casa_cliente_editar(conta: str, payload: Tomador) -> dict:
        try:
            return {"cliente": casa().editar_cliente(conta, payload.tomador)}
        except casa_nfse.ErroPonte as exc:
            erro(exc)

    @app.get("/api/casa-nfse/pagamentos")
    def casa_pagamentos() -> dict:
        try:
            return {"pagamentos": casa().pagamentos()}
        except casa_nfse.ErroPonte as exc:
            erro(exc, 502)

    @app.post("/api/casa-nfse/emitir")
    def casa_emitir(payload: Emitir) -> dict:
        try:
            return casa().emitir(payload.model_dump(), quem="titular")
        except ValueError as exc:
            erro(exc)

    def _nota(id_: int) -> dict:
        n = casa().emissor.notas.obter(id_)
        if not n or n.get("origem") != casa_nfse.ORIGEM:
            raise HTTPException(status_code=404, detail="nota não encontrada")
        return n

    @app.get("/api/casa-nfse/notas/{id_}/pdf")
    def casa_nota_pdf(id_: int, baixar: int = 0):
        from fastapi.responses import Response

        n = _nota(id_)
        pdf = casa().pdf(n)
        if not pdf:
            raise HTTPException(status_code=404, detail="a nota ainda não foi emitida")
        modo = "attachment" if baixar else "inline"
        return Response(pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'{modo}; filename="NFS-e {n.get("numero_nfse") or n["id"]}.pdf"'})

    @app.get("/api/casa-nfse/notas/{id_}/xml")
    def casa_nota_xml(id_: int):
        from fastapi.responses import Response

        n = _nota(id_)
        xml = casa().xml(n)
        if not xml:
            raise HTTPException(status_code=404, detail="a nota ainda não foi emitida")
        return Response(xml, media_type="application/xml",
                        headers={"Content-Disposition": f'attachment; filename="NFS-e {n.get("numero_nfse") or n["id"]}.xml"'})

    @app.post("/api/casa-nfse/notas/{id_}/enviar")
    def casa_nota_enviar(id_: int) -> dict:
        _nota(id_)
        try:
            return casa().enviar(id_)
        except (ValueError, casa_nfse.ErroPonte) as exc:
            erro(exc)

    @app.post("/api/casa-nfse/producao/liberar")
    def casa_liberar() -> dict:
        c = casa()
        try:
            c.liberar_producao("titular")
        except ValueError as exc:
            erro(exc)
        return c.para_tela()

    @app.post("/api/casa-nfse/producao/voltar")
    def casa_voltar() -> dict:
        c = casa()
        c.voltar_para_testes("titular")
        return c.para_tela()
