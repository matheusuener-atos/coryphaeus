"""
As rotas da Biblioteca (docs/PROGRESSO-BIBLIOTECA.md). Moram aqui, e não no
api.py: o api.py só chama `montar` e, no envio de material, `receber`.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import File, HTTPException, UploadFile
from pydantic import BaseModel

import leis as leis_mod
from biblioteca import ficha as ficha_mod


def ligada(estado, chave: str) -> bool:
    return bool((estado.prefs.dados.get("biblioteca") or {}).get(chave))


def receber(estado, dados_dir: Path, nome: str, conteudo: bytes) -> dict:
    """
    Um arquivo entregue como material. Com `biblioteca.triagem`, passa pela
    triagem (lei vai para as leis em casa; o resto ganha a ficha); sem ela, o
    material de sempre.
    """
    if not ligada(estado, "triagem"):
        return {"destino": "material", "item": estado.material.absorver(nome, conteudo), "mensagem": ""}
    from biblioteca import triagem

    return triagem.entregar(estado.material, estado.leis, nome, conteudo, Path(dados_dir) / "leis")


def anotacoes_para_tela(estado, anotacoes: list[dict], codigo: str = "") -> list[dict]:
    """Cada anotação com a ficha da obra: obra, autor, edição, ano, página e o trecho (até ~300 caracteres)."""
    from biblioteca import defasagem
    from biblioteca.anotacoes import TRECHO_NA_TELA

    artigo = None
    if codigo and anotacoes and ligada(estado, "defasagem"):
        artigo = estado.leis.artigo(codigo, anotacoes[0]["artigo"])
    saida = []
    for a in anotacoes:
        item = estado.material.item(a["material_id"]) or {}
        f = item.get("ficha") or {}
        trecho = a["quote"] if len(a["quote"]) <= TRECHO_NA_TELA else a["quote"][:TRECHO_NA_TELA - 1] + "…"
        saida.append({"material_id": a["material_id"], "obra": f.get("titulo") or item.get("nome", ""),
                      "autor": f.get("autor", ""), "edicao": f.get("edicao", ""), "ano": f.get("ano", ""),
                      "tipo": f.get("tipo", ""), "pagina": a["pagina"], "trecho": trecho,
                      "pdf": str(item.get("arquivo", "")).lower().endswith(".pdf"),
                      # M6: obra anterior à redação atual do artigo.
                      "aviso": defasagem.aviso(f.get("ano", ""), artigo["alterado_em"]) if artigo else "",
                      # M5: a tese do autor sobre este artigo, em destaque.
                      "teses": ([x["afirmacao"] for x in estado.material.leitura.teses_do_artigo(
                          a["material_id"], codigo, a["artigo"])][:2] if codigo and ligada(estado, "leitura") else [])})
    return saida


class Ficha(BaseModel):
    tipo: str | None = None
    titulo: str | None = None
    autor: str | None = None
    edicao: str | None = None
    ano: str | None = None
    editora: str | None = None
    isbn: str | None = None
    areas: list[str] | None = None
    licenca: str | None = None


class Baixar(BaseModel):
    codigo: str


class Autoria(BaseModel):
    sou_autor: bool = False
    licenca: str = ""


def montar(estado, app, dados_dir: Path) -> None:
    pasta_leis = Path(dados_dir) / "leis"

    @app.get("/api/biblioteca-juridica")
    def biblioteca_geral() -> dict:
        """O que a tela precisa saber: as chaves, os tipos e as áreas da ficha."""
        return {"chaves": dict(estado.prefs.dados.get("biblioteca") or {}),
                "tipos": [{"id": t, "rotulo": ficha_mod.ROTULO_DO_TIPO[t]} for t in ficha_mod.TIPOS],
                "areas": list(ficha_mod.AREAS)}

    @app.get("/api/biblioteca-juridica/mapa")
    def biblioteca_mapa() -> dict:
        """O que o PAULUS sabe: por área, as obras e as leis; por código, os artigos anotados."""
        from biblioteca import mapa

        if not ligada(estado, "mapa"):
            return {"ligada": False}
        estado.material.preparar()
        return {"ligada": True, **mapa.painel(estado.material, estado.leis, getattr(estado, "contextos", None))}

    @app.get("/api/material/{id_}/leitura")
    def material_leitura(id_: str) -> dict:
        """O glossário (conceitos com página) e as teses do autor (posições com página) da obra (M5)."""
        if not estado.material.item(id_):
            raise HTTPException(status_code=404, detail="esse material não existe mais")
        return {"ligada": ligada(estado, "leitura"), **estado.material.leitura.de(id_),
                "andamento": estado.material.leitura.estado}

    @app.post("/api/biblioteca-juridica/ler")
    def biblioteca_ler() -> dict:
        """Começa (ou continua) a leitura das obras em segundo plano, cedendo a vez à conversa."""
        if not ligada(estado, "leitura"):
            raise HTTPException(status_code=409, detail="a leitura das obras está desligada em Configurações")
        return estado.material.leitura.iniciar()

    # ------------------------------------------------ o pacote .paulus-material

    def _pacote_ligado() -> None:
        if not ligada(estado, "pacote"):
            raise HTTPException(status_code=409, detail="o pacote .paulus-material está desligado em Configurações")

    @app.post("/api/material/{id_}/autoria")
    def material_autoria(id_: str, payload: Autoria) -> dict:
        """'Sou o autor deste material e posso compartilhá-lo', e a licença - só assim ele se exporta."""
        from biblioteca import pacote

        _pacote_ligado()
        try:
            item = pacote.declarar(estado.material, id_, payload.sou_autor, payload.licenca)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="esse material não existe mais") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"item": item, **estado.material.para_tela()}

    @app.get("/api/material/{id_}/pacote")
    def material_pacote(id_: str):
        """O pacote para levar a outro PAULUS: ficha, texto com as páginas e anotações. Nada vai pela rede."""
        from fastapi.responses import Response

        import versao
        from biblioteca import pacote

        _pacote_ligado()
        try:
            conteudo = pacote.exportar(estado.material, id_, versao.VERSAO)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="esse material não existe mais") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        nome = re.sub(r"[^\w.-]+", "-", Path(estado.material.item(id_)["nome"]).stem, flags=re.UNICODE)[:60]
        return Response(conteudo, media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{nome}{pacote.EXTENSAO}"'})

    @app.post("/api/material/pacote")
    async def material_importar_pacote(arquivo: UploadFile = File(...)) -> dict:
        """Um .paulus-material de outro advogado: entra como material da comunidade, não revisado."""
        from biblioteca import pacote

        _pacote_ligado()
        conteudo = await arquivo.read(pacote.MAX_BYTES + 1)
        try:
            item = pacote.importar(estado.material, conteudo, Path(arquivo.filename or "").name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"item": item, **estado.material.para_tela()}

    @app.put("/api/material/{id_}/ficha")
    def material_ficha(id_: str, payload: Ficha) -> dict:
        """A ficha conferida na tela: o que a pessoa escreve vale sobre o que a regra achou."""
        mudancas = {k: v for k, v in payload.model_dump().items() if v is not None}
        try:
            item = estado.material.editar_ficha(id_, mudancas)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="esse material não existe mais") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"item": item, **estado.material.para_tela()}

    @app.get("/api/leis/anotacoes")
    def leis_anotacoes(codigo: str, numero: str) -> dict:
        """
        "Na biblioteca do escritório": as obras que citam este artigo, com
        obra, autor, edição e página, e um trecho curto. Sem obra que cite,
        diz isso - e não mostra trecho "parecido".
        """
        if not ligada(estado, "anotacoes"):
            return {"anotacoes": [], "ligada": False, "mensagem": ""}
        estado.material.preparar()
        return {"anotacoes": anotacoes_para_tela(estado, estado.material.anotacoes.do_artigo(codigo, numero), codigo),
                "ligada": True, "mensagem": "nenhuma obra da biblioteca cita este artigo"}

    @app.get("/api/material/{id_}/arquivo")
    def material_arquivo(id_: str):
        """O arquivo do próprio escritório, para abrir na página (o visor de PDF do programa)."""
        from fastapi.responses import FileResponse

        alvo = estado.material.caminho(id_)
        if not alvo:
            raise HTTPException(status_code=404, detail="o arquivo desse material saiu do lugar")
        return FileResponse(str(alvo), media_type="application/pdf" if alvo.suffix.lower() == ".pdf" else None,
                            headers={"Content-Disposition": "inline"})

    @app.post("/api/leis/baixar")
    def leis_baixar(payload: Baixar) -> dict:
        """
        Baixa o texto compilado do Planalto e guarda artigo por artigo. Só um
        GET no endereço oficial da lei: nada desta máquina vai junto.
        """
        import requests

        dados = leis_mod.CODIGOS.get(payload.codigo)
        if not dados:
            raise HTTPException(status_code=404, detail="não conheço esse código")
        try:
            resp = requests.get(dados["fonte"], timeout=90, headers={"User-Agent": "Mozilla/5.0 PAULUS"})
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail="não consegui baixar do Planalto agora: " +
                                str(exc)[:120]) from exc
        pasta_leis.mkdir(parents=True, exist_ok=True)
        alvo = pasta_leis / Path(dados["fonte"]).name
        alvo.write_bytes(resp.content)
        try:
            r = estado.leis.importar(alvo, payload.codigo)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {**r, "codigos": estado.leis.instalados(), "contagem": estado.leis.contagem()}
