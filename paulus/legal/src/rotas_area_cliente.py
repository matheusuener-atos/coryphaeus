"""
As rotas da Area do cliente (src/area_cliente.py, docs/PLANO-AREA-CLIENTE.md).

Dois grupos:

- as do escritorio, dentro da pasta (/api/servicos/{id_}/cliente/*): quem ve,
  o olhinho, o "compartilhar" do documento, a conversa, o resumo, a
  atividade e o "Ver como o cliente". De fora, valem as regras da pasta: so
  quem esta na Equipe do servico (o titular, sempre) - e gravar abre pelo
  nivel "faz" em Servicos;
- as do cliente (/cliente/{token} e /api/cliente/*): a pagina, entrar com o
  codigo e o que ele faz na pasta. Chegam pelo portao de fora, que as entrega
  a PortaDoCliente; a sessao e conferida de novo aqui, e a pasta pedida tem
  de ser uma das que a pessoa ve - senao, 404.
"""

import urllib.parse
from datetime import date

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

import area_cliente as area_mod
import recursos_do_plano
import servicos_acesso

RECURSO = "pagina_cliente"


class Compartilhar(BaseModel):
    nome: str = ""
    email: str = ""
    cadastro_id: int | None = None


class PessoaDaPasta(BaseModel):
    pessoa_id: int


class MarcaDaEtapa(BaseModel):
    oculta: bool | None = None
    do_cliente: bool | None = None


class MarcaDoCompromisso(BaseModel):
    oculto: bool | None = None
    confirmar: bool | None = None


class MarcaDoDocumento(BaseModel):
    compartilhado: bool


class Texto(BaseModel):
    texto: str = ""


class PedirCodigo(BaseModel):
    token: str = ""
    email: str = ""


class Entrar(BaseModel):
    token: str = ""
    codigo: str = ""
    lembrar: bool = False


class Evento(BaseModel):
    tipo: str = ""
    servico_id: int | None = None
    alvo: str = ""


class MensagemDoCliente(BaseModel):
    texto: str = ""
    etapa: str = ""


class Resposta(BaseModel):
    resposta: str = ""
    sugestao: str = ""


def _ip(request) -> str:
    if request is None:
        return ""
    return (request.headers.get("cf-connecting-ip") or "")[:64]


def _erro(exc: area_mod.ErroDoCliente):
    return HTTPException(status_code=exc.status, detail=str(exc))


def montar(estado, app, dados_dir, *, modelo_pronto, limpar_texto, ao_receber) -> area_mod.AreaDoCliente:
    import equipe

    fora = estado.acesso_de_fora

    def hostname() -> str:
        p = fora.preferencias()
        return str(p.get("hostname") or "") if p.get("ligado") else ""

    def escritorio() -> str:
        return str((estado.prefs.dados.get("escritorio") or {}).get("nome") or "").strip()

    def avisar(titulo: str, texto: str) -> None:
        import avisos

        avisos.avisar("cliente", titulo, texto)

    area = area_mod.AreaDoCliente(
        estado.base, estado.servicos, dados_dir,
        documentos=lambda: list(estado.searcher.documents), hostname=hostname, escritorio=escritorio,
        enviar_email=fora.email_do_cliente, registrar=fora.auditoria.registrar, avisar=avisar, ao_receber=ao_receber)
    estado.area_cliente = area

    def ligado() -> bool:
        return recursos_do_plano.pode(estado, RECURSO)

    fora.portao.cliente = area_mod.PortaDoCliente(
        area, ligado=ligado, motivo_desligado=lambda: "a área do cliente não está ativa neste escritório")

    def quem() -> str:
        """O nome inteiro de quem faz, para a trilha e para o e-mail ("Dra. Ana Moura compartilhou...")."""
        p = equipe.pessoa_da_vez()
        if p:
            return str(p.get("nome") or "")
        return str((estado.prefs.dados.get("pessoa") or {}).get("nome") or "").strip()

    def pasta(id_: int) -> dict:
        s = estado.base.um("SELECT id, nome, cadastro_id FROM servicos WHERE id = ?", (id_,))
        if not s or not servicos_acesso.visivel(id_):
            raise HTTPException(status_code=404, detail="serviço não encontrado")
        return s

    # ------------------------------------------------------- o escritorio

    @app.get("/api/servicos/{id_}/cliente")
    def area_da_pasta(id_: int, ler: bool = False) -> dict:
        """O que o escritorio controla nesta pasta, na aba Cliente."""
        s = pasta(id_)
        if ler:
            area.marcar_lidas(id_)
        sugestao = {"nome": "", "email": "", "cadastro_id": None}
        if s["cadastro_id"]:
            c = estado.base.um("SELECT id, nome, email FROM cadastros WHERE id = ?", (s["cadastro_id"],))
            if c:
                sugestao = {"nome": c["nome"], "email": c["email"] or "", "cadastro_id": c["id"]}
        hoje = date.today().isoformat()
        comps = estado.base.buscar("SELECT id, titulo, data, hora FROM compromissos WHERE servico_id = ? AND data >= ? ORDER BY data, hora",
                                   (id_, hoje))
        return {
            "disponivel": ligado(),
            "motivo_plano": "" if ligado() else recursos_do_plano.frase(estado, RECURSO),
            "endereco": hostname(),
            "pessoas": area.pessoas_da_pasta(id_),
            "sugestao": sugestao,
            "resumo": area.resumo(id_),
            "mensagens": area.mensagens(id_),
            "nao_lidas": area.nao_lidas().get(id_, 0),
            "documentos": area.documentos_compartilhados_sha1(id_),
            "compromissos": comps,
            **area.estado_dos_compromissos(id_),
        }

    @app.get("/api/servicos/cliente/nao-lidas")
    def area_nao_lidas() -> dict:
        """As mensagens de cliente ainda nao lidas, por pasta - o selo da grade de Servicos."""
        return {"por_servico": {str(k): v for k, v in area.nao_lidas().items() if servicos_acesso.visivel(k)}}

    @app.post("/api/servicos/{id_}/cliente/compartilhar")
    def area_compartilhar(id_: int, payload: Compartilhar) -> dict:
        pasta(id_)
        recursos_do_plano.exigir(estado, RECURSO)
        try:
            return area.compartilhar(id_, payload.nome, payload.email, payload.cadastro_id, quem())
        except area_mod.ErroDoCliente as exc:
            raise _erro(exc) from None

    @app.post("/api/servicos/{id_}/cliente/reenviar")
    def area_reenviar(id_: int, payload: PessoaDaPasta) -> dict:
        pasta(id_)
        recursos_do_plano.exigir(estado, RECURSO)
        try:
            return area.reenviar(id_, payload.pessoa_id, quem())
        except area_mod.ErroDoCliente as exc:
            raise _erro(exc) from None

    @app.post("/api/servicos/{id_}/cliente/parar")
    def area_parar(id_: int, payload: PessoaDaPasta) -> dict:
        pasta(id_)
        try:
            area.parar(id_, payload.pessoa_id, quem())
        except area_mod.ErroDoCliente as exc:
            raise _erro(exc) from None
        return {"pessoas": area.pessoas_da_pasta(id_)}

    @app.post("/api/servicos/{id_}/cliente/etapas/{indice}")
    def area_etapa(id_: int, indice: int, payload: MarcaDaEtapa) -> dict:
        pasta(id_)
        try:
            return {"etapas": area.marcar_etapa(id_, indice, oculta=payload.oculta, do_cliente=payload.do_cliente)}
        except area_mod.ErroDoCliente as exc:
            raise _erro(exc) from None

    @app.post("/api/servicos/{id_}/cliente/compromissos/{cid}")
    def area_compromisso(id_: int, cid: int, payload: MarcaDoCompromisso) -> dict:
        pasta(id_)
        try:
            return area.marcar_compromisso(id_, cid, oculto=payload.oculto, confirmar=payload.confirmar)
        except area_mod.ErroDoCliente as exc:
            raise _erro(exc) from None

    @app.post("/api/servicos/{id_}/cliente/documentos/{sha1}")
    def area_documento(id_: int, sha1: str, payload: MarcaDoDocumento) -> dict:
        pasta(id_)
        try:
            return {"documentos": area.compartilhar_documento(id_, sha1, payload.compartilhado, quem())}
        except area_mod.ErroDoCliente as exc:
            raise _erro(exc) from None

    @app.get("/api/servicos/{id_}/cliente/atividade")
    def area_atividade(id_: int) -> dict:
        """
        O que o cliente fez nesta pasta. De fora, so quem esta na Equipe do
        servico chega aqui (o filtro da pasta) - "so os responsaveis".
        """
        pasta(id_)
        return {"atividade": area.atividade(id_)}

    @app.post("/api/servicos/{id_}/cliente/mensagens")
    def area_responder(id_: int, payload: Texto) -> dict:
        pasta(id_)
        try:
            r = area.escritorio_escreve(id_, payload.texto, quem())
        except area_mod.ErroDoCliente as exc:
            raise _erro(exc) from None
        area.marcar_lidas(id_)
        return dict(r, mensagens=area.mensagens(id_))

    @app.post("/api/servicos/{id_}/cliente/resumo")
    def area_publicar_resumo(id_: int, payload: Texto) -> dict:
        pasta(id_)
        try:
            return area.publicar_resumo(id_, payload.texto, quem())
        except area_mod.ErroDoCliente as exc:
            raise _erro(exc) from None

    @app.post("/api/servicos/{id_}/cliente/resumo/sugerir")
    def area_sugerir_resumo(id_: int) -> dict:
        """
        O rascunho do resumo do cliente, escrito pelo modelo lendo SO o que o
        cliente ve. Fica como rascunho: aparece para o cliente depois que o
        escritorio le e publica.
        """
        from llama_client import OllamaError

        pasta(id_)
        disponivel, motivo = modelo_pronto("resumos")
        if not disponivel:
            raise HTTPException(status_code=503, detail=motivo)
        try:
            texto = estado.cliente_para("resumos", servico=id_).ask(area_mod.INSTRUCAO_RESUMO_CLIENTE, area.texto_para_ia(id_))
        except OllamaError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return area.guardar_rascunho(id_, limpar_texto(texto))

    @app.get("/api/servicos/{id_}/como-cliente")
    def area_como_cliente(id_: int) -> dict:
        """O "Ver como o cliente": a MESMA visao que a rota do cliente entrega."""
        pasta(id_)
        try:
            return dict(area.visao(id_), previa=True)
        except area_mod.ErroDoCliente as exc:
            raise _erro(exc) from None

    @app.get("/api/servicos/{id_}/como-cliente/documentos/{sha1}/pagina")
    def area_como_cliente_pagina(id_: int, sha1: str, n: int = 1, largura: int = 1100) -> Response:
        pasta(id_)
        try:
            png, total, _nome = area.pagina(id_, sha1, n, area.marca("", previa=True), largura)
        except area_mod.ErroDoCliente as exc:
            raise _erro(exc) from None
        return Response(png, media_type="image/png", headers={"Cache-Control": "no-store", "X-Paginas": str(total)})

    # ---------------------------------------------------------- o cliente

    def sessao(request: Request) -> dict:
        valor = request.cookies.get(area_mod.COOKIE) if request is not None else None
        p = area.sessao(valor)
        if not p:
            raise HTTPException(status_code=401, detail="entre de novo: a sessão acabou", headers={"x-paulus-sessao": "acabou"})
        return p

    def da_pessoa(request: Request, sid: int) -> dict:
        p = sessao(request)
        if not area.pode_ver(p["id"], sid):
            raise HTTPException(status_code=404, detail="pasta não encontrada")
        return p

    frontend = dados_dir_frontend()

    @app.get("/cliente/{token}")
    def area_pagina(token: str) -> FileResponse:
        """A pagina do cliente (tambem a previa do escritorio, em /cliente/previa)."""
        return FileResponse(frontend / "cliente.html", headers={"Cache-Control": "no-cache", "Referrer-Policy": "no-referrer"})

    @app.post("/api/cliente/entrar")
    def cliente_pedir_codigo(payload: PedirCodigo, request: Request) -> dict:
        try:
            return area.pedir_codigo(payload.token, payload.email, _ip(request))
        except area_mod.ErroDoCliente as exc:
            raise _erro(exc) from None

    @app.post("/api/cliente/codigo")
    def cliente_entrar(payload: Entrar, request: Request) -> JSONResponse:
        try:
            s = area.entrar(payload.token, payload.codigo, payload.lembrar, _ip(request))
        except area_mod.ErroDoCliente as exc:
            raise _erro(exc) from None
        r = JSONResponse({"ok": True, "csrf": s["csrf"]})
        seguro = request.url.scheme == "https" or bool(request.headers.get("cf-connecting-ip"))
        r.set_cookie(area_mod.COOKIE, s["cookie"], max_age=s["max_age"], httponly=True, samesite="strict",
                     secure=seguro, path="/")
        return r

    @app.get("/api/cliente/eu")
    def cliente_eu(request: Request) -> dict:
        return area.eu(sessao(request))

    @app.post("/api/cliente/sair")
    def cliente_sair(request: Request) -> JSONResponse:
        area.sair(request.cookies.get(area_mod.COOKIE) or "", _ip(request))
        r = JSONResponse({"ok": True})
        r.delete_cookie(area_mod.COOKIE, path="/")
        return r

    @app.get("/api/cliente/pastas/{sid}")
    def cliente_pasta(sid: int, request: Request) -> dict:
        p = da_pessoa(request, sid)
        try:
            v = area.visao(sid)
        except area_mod.ErroDoCliente as exc:
            raise _erro(exc) from None
        area.anotar(p, "abriu_pasta", sid, ip=_ip(request), juntar_s=600)
        return v

    @app.get("/api/cliente/pastas/{sid}/documentos/{sha1}/pagina")
    def cliente_pagina(sid: int, sha1: str, request: Request, n: int = 1, largura: int = 1100) -> Response:
        p = da_pessoa(request, sid)
        try:
            png, total, nome = area.pagina(sid, sha1, n, area.marca(p["nome"]), largura)
        except area_mod.ErroDoCliente as exc:
            raise _erro(exc) from None
        area.anotar(p, "abriu", sid, nome, _ip(request), juntar_s=600)
        return Response(png, media_type="image/png", headers={"Cache-Control": "no-store", "X-Paginas": str(total)})

    @app.get("/api/cliente/pastas/{sid}/documentos/{sha1}/baixar")
    def cliente_baixar(sid: int, sha1: str, request: Request) -> Response:
        p = da_pessoa(request, sid)
        try:
            conteudo, nome, tipo = area.baixar(sid, sha1, area.marca(p["nome"]))
        except area_mod.ErroDoCliente as exc:
            raise _erro(exc) from None
        area.anotar(p, "baixou", sid, nome, _ip(request))
        cabeca = "attachment; filename*=UTF-8''" + urllib.parse.quote(nome)
        return Response(conteudo, media_type=tipo, headers={"Content-Disposition": cabeca, "Cache-Control": "no-store"})

    @app.post("/api/cliente/evento")
    def cliente_evento(payload: Evento, request: Request) -> dict:
        """O que so o navegador sabe: o cliente mandou imprimir."""
        p = sessao(request)
        if payload.tipo != "imprimiu":
            raise HTTPException(status_code=400, detail="evento desconhecido")
        sid = payload.servico_id
        if sid is not None and not area.pode_ver(p["id"], sid):
            raise HTTPException(status_code=404, detail="pasta não encontrada")
        area.anotar(p, "imprimiu", sid, payload.alvo[:200], _ip(request), juntar_s=30)
        return {"ok": True}

    @app.post("/api/cliente/pastas/{sid}/mensagens")
    def cliente_mensagem(sid: int, payload: MensagemDoCliente, request: Request) -> dict:
        p = da_pessoa(request, sid)
        try:
            area.cliente_escreve(p, sid, payload.texto, payload.etapa, _ip(request))
        except area_mod.ErroDoCliente as exc:
            raise _erro(exc) from None
        return {"mensagens": area.mensagens(sid)}

    @app.post("/api/cliente/pastas/{sid}/enviar")
    async def cliente_enviar(sid: int, request: Request, nome: str = "", etapa: str = "") -> dict:
        """
        Um arquivo por pedido, no corpo (sem formulario): o nome vem na
        consulta. O tamanho e conferido enquanto chega - o que passa do teto
        para de ser lido.
        """
        p = da_pessoa(request, sid)
        corpo = bytearray()
        async for pedaco in request.stream():
            corpo += pedaco
            if len(corpo) > area_mod.LIMITE_DO_ENVIO:
                raise HTTPException(status_code=413, detail=f"o arquivo passa de {area_mod.LIMITE_DO_ENVIO // (1024 * 1024)} MB")
        import asyncio

        try:
            return await asyncio.to_thread(area.cliente_envia, p, sid, nome, bytes(corpo), etapa if etapa != "" else None,
                                           _ip(request))
        except area_mod.ErroDoCliente as exc:
            raise _erro(exc) from None

    @app.post("/api/cliente/pastas/{sid}/etapas/{indice}/feita")
    def cliente_feita(sid: int, indice: int, request: Request) -> dict:
        p = da_pessoa(request, sid)
        try:
            return area.cliente_conclui(p, sid, indice, _ip(request))
        except area_mod.ErroDoCliente as exc:
            raise _erro(exc) from None

    @app.post("/api/cliente/pastas/{sid}/compromissos/{cid}/responder")
    def cliente_responder(sid: int, cid: int, payload: Resposta, request: Request) -> dict:
        p = da_pessoa(request, sid)
        try:
            return area.cliente_responde(p, sid, cid, payload.resposta, payload.sugestao, _ip(request))
        except area_mod.ErroDoCliente as exc:
            raise _erro(exc) from None

    @app.get("/api/cliente/pastas/{sid}/compromissos/{cid}/agenda")
    def cliente_ics(sid: int, cid: int, request: Request) -> Response:
        p = da_pessoa(request, sid)
        try:
            texto, nome = area.ics_do_compromisso(sid, cid)
        except area_mod.ErroDoCliente as exc:
            raise _erro(exc) from None
        area.anotar(p, "agenda", sid, nome, _ip(request))
        cabeca = "attachment; filename*=UTF-8''" + urllib.parse.quote(nome + ".ics")
        return Response(texto.encode("utf-8"), media_type="text/calendar; charset=utf-8",
                        headers={"Content-Disposition": cabeca, "Cache-Control": "no-store"})

    return area


def dados_dir_frontend():
    from pathlib import Path

    return Path(__file__).parent.parent / "frontend"

