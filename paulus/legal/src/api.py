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
import re
import sys
import threading
import unicodedata
from datetime import datetime
from collections.abc import Iterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

import requests

import aprovacoes as fila_aprovacoes
import assinatura
import certificado
import correio
import correio_contas
import destinos
import bemestar
import conexoes
import documento
import financeiro
import acervo
import citacao
import escritorio
import intencao
import leis
import redacao
import ritmo as ritmo_mod
import planilha
import relatorios
import pastas
import recursos
import registro
from classify import Classificacao, ROTULOS
from agenda import Agenda, ONDES, TIPOS as TIPOS_AGENDA
from base import Base
from cadastros import Cadastros, TIPOS as TIPOS_CADASTRO
from config import Preferencias
import tarefas as tarefas_mod
from tarefas import Tarefas
from habilidade_base import (
    PRECISA_ASSISTENTE,
    PRECISA_DOCUMENTOS,
    Contexto,
)
from extract import SUPPORTED_SUFFIXES, index_all_contracts
from jobs import AGUARDANDO, CONCLUIDO, EXECUTANDO, Etapa, Trabalhos, titular
from jobs import agora as jobs_agora
from llama_client import (
    DEFAULT_MODEL,
    LlamaClient,
    OllamaError,
    check_ollama,
    janela_para,
)
from organize import (
    PADROES_SUGERIDOS,
    aplicar_plano,
    desfazer,
    listar_diarios,
    montar_plano,
)
from scan import escanear
from search import ContractSearcher

BASE_DIR = Path(__file__).parent.parent
CONTRACTS_DIR = BASE_DIR / "data" / "test_contracts"
CACHE_PATH = BASE_DIR / "data" / "extractions" / "index.json"
CLASSIFICACAO_PATH = BASE_DIR / "data" / "extractions" / "classificacao.json"
DIARIOS_DIR = BASE_DIR / "data" / "diarios"
TRABALHOS_DIR = BASE_DIR / "data" / "trabalhos"
APROVACOES_PATH = BASE_DIR / "data" / "aprovacoes.json"
PREFERENCIAS_PATH = BASE_DIR / "data" / "preferencias.json"
BASE_PATH = BASE_DIR / "data" / "paulus.db"
CERTIFICADO_DIR = BASE_DIR / "data" / "certificado"
COFRE_PATH = CERTIFICADO_DIR / "cofre.json"
ASSINATURAS_PATH = BASE_DIR / "data" / "assinaturas.json"
CONTAS_EMAIL_PATH = BASE_DIR / "data" / "contas_email.json"
ENVIOS_PATH = BASE_DIR / "data" / "envios.json"
CLAUSULAS_PATH = BASE_DIR / "data" / "clausulas.json"
CONEXOES_PATH = BASE_DIR / "data" / "conexoes.json"
SESSOES_DIR = BASE_DIR / "data" / "sessoes"
COMPROVANTES_DIR = BASE_DIR / "data" / "comprovantes"
RECIBOS_DIR = BASE_DIR / "data" / "recibos"
EXPORTACOES_DIR = BASE_DIR / "data" / "exportacoes"
RITMO_PATH = BASE_DIR / "data" / "ritmo.json"
HABILIDADES_DIR = BASE_DIR / "habilidades"
FRONTEND_DIR = BASE_DIR / "frontend"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_CERTIFICADO_BYTES = 8 * 1024 * 1024


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
        # Levantado quando a pessoa pede para parar a leitura em andamento.
        self.cancelar = threading.Event()
        # Habilidades carregadas da pasta do projeto, uma por arquivo.
        self.registro = registro.carregar(HABILIDADES_DIR)
        # Fila do que espera decisao humana, e as preferencias da casa.
        self.fila = fila_aprovacoes.Fila(APROVACOES_PATH)
        self.prefs = Preferencias(PREFERENCIAS_PATH)
        # Base local: cadastros, tarefas e o que vier depois.
        self.base = Base(BASE_PATH)
        self.cadastros = Cadastros(self.base)
        self.tarefas = Tarefas(self.base)
        self.agenda = Agenda(self.base)
        # Certificado digital: o arquivo, o selo e o historico de assinaturas.
        self.cofre = certificado.Cofre(COFRE_PATH, CERTIFICADO_DIR)
        self.assinaturas = assinatura.Registro(ASSINATURAS_PATH)
        # Contas de e-mail e o historico do que ja saiu daqui.
        self.contas = correio_contas.Contas(CONTAS_EMAIL_PATH)
        self.envios = correio.RegistroEnvios(ENVIOS_PATH)
        # Documentos de texto e planilhas, com historico de versoes.
        self.documentos = documento.Documentos(self.base)
        self.clausulas = documento.Clausulas(CLAUSULAS_PATH)
        # Os codigos oficiais em base local: citar vira consulta.
        self.leis = leis.Leis(self.base)
        # O que a pessoa marcou sobre cada documento da biblioteca.
        self.marcas = acervo.Marcas(self.base)
        # O que esta maquina ja mediu de si: quanto le e quanto escreve por
        # segundo. E daqui que sai o "leituras assim levaram ~70 s aqui".
        self.ritmo = ritmo_mod.Ritmo(RITMO_PATH)
        # Financeiro, bem-estar e conexoes; relatorios so le o que os outros gravaram.
        self.financeiro = financeiro.Financeiro(self.base)
        # A folha, as notas e os boletos: o escritorio por dentro.
        self.folha = escritorio.Folha(self.base)
        self.papeis = escritorio.PapeisFiscais(self.base)
        self.bem_estar = bemestar.BemEstar(self.base)
        self.conexoes = conexoes.Conexoes(CONEXOES_PATH, SESSOES_DIR)
        self.relatorios = relatorios.Relatorios(
            self.base, fila=self.fila, assinaturas=self.assinaturas,
            envios=self.envios, bem_estar=self.bem_estar,
        )

    def recarregar(self, *, force: bool = False) -> int:
        docs = index_all_contracts(self.pasta, CACHE_PATH, force=force, verbose=False)
        searcher = ContractSearcher()
        searcher.add_contracts(docs)
        searcher.build()
        self.searcher = searcher

        # A janela do modelo acompanha o acervo. Com a janela fixa e pequena, o
        # programa lia um terco dos documentos e respondia "nao encontrei essa
        # informacao" sobre os outros dois tercos - resposta errada com cara de
        # certa, que e o pior tipo.
        if self.client is not None:
            self.client.num_ctx = janela_para(searcher.caracteres())
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


@app.get("/img/{arquivo}")
def imagem(arquivo: str) -> FileResponse:
    alvo = (FRONTEND_DIR / "img" / Path(arquivo).name).resolve()
    if alvo.parent != (FRONTEND_DIR / "img").resolve() or not alvo.exists():
        raise HTTPException(status_code=404, detail="imagem nao encontrada")
    return FileResponse(alvo)


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


def _sse(tipo: str, dados: dict) -> str:
    """Um evento no formato que o navegador consome (Server-Sent Events)."""
    return f"event: {tipo}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"


def _disponibilidade() -> dict:
    ok, _ = check_ollama(estado.client.model)
    return {
        PRECISA_DOCUMENTOS: len(estado.searcher.documents) > 0,
        PRECISA_ASSISTENTE: ok,
    }


def _contexto(registrar=None) -> Contexto:
    """O que as habilidades enxergam da aplicacao."""
    return Contexto(
        searcher=estado.searcher,
        client=estado.client,
        pasta=estado.pasta,
        cache_classificacao=CLASSIFICACAO_PATH,
        diarios=DIARIOS_DIR,
        recarregar=estado.recarregar,
        registrar=registrar,
        cancelado=estado.cancelar.is_set,
        antes_de_cada=lambda: recursos.esperar_maquina_livre(estado.devagar, limite_s=10),
        ritmo=estado.ritmo,
    )


@app.get("/api/destinos")
def listar_destinos() -> dict:
    """Menu lateral na ordem oficial do manual do sistema."""
    return {"grupos": destinos.por_grupo(), "contagem": destinos.contagem()}


@app.get("/api/habilidades")
def listar_habilidades() -> dict:
    """
    Catalogo do que o programa sabe fazer, com o que falta para cada coisa.

    A disponibilidade e checada agora: nao adianta oferecer "perguntar sobre os
    documentos" quando nao ha documento aberto.
    """
    return {
        "grupos": estado.registro.por_grupo(_disponibilidade()),
        "contagem": estado.registro.contagem(),
        "pasta": estado.registro.pasta,
    }


@app.post("/api/habilidades/recarregar")
def recarregar_habilidades() -> dict:
    """Rele a pasta de modulos sem fechar o programa."""
    estado.registro = registro.carregar(HABILIDADES_DIR)
    return {"contagem": estado.registro.contagem()}


@app.post("/api/habilidades/{id_}")
def executar_habilidade(id_: str, parametros: dict | None = None):
    """
    Porta unica para rodar qualquer habilidade.

    Se o modulo devolve um dict, sai como JSON. Se e um gerador, sai como
    stream de eventos - e a mesma porta serve para a busca instantanea e para
    uma leitura de uma hora.
    """
    habilidade = estado.registro.obter(id_)
    if not habilidade:
        raise HTTPException(status_code=404, detail="habilidade desconhecida")
    if not habilidade.executavel:
        raise HTTPException(
            status_code=400,
            detail=habilidade.problema or "essa habilidade ainda não faz nada",
        )

    faltando = [p for p in habilidade.precisa if not _disponibilidade().get(p, False)]
    if faltando:
        from habilidade_base import ROTULOS_PRECISA

        nomes = ", ".join(ROTULOS_PRECISA.get(p, p) for p in faltando)
        raise HTTPException(status_code=400, detail=f"precisa de: {nomes}")

    try:
        saida = habilidade.executar(_contexto(), **(parametros or {}))
    except TypeError as exc:
        raise HTTPException(status_code=400, detail=f"parâmetros inválidos: {exc}") from exc

    if not hasattr(saida, "__next__"):
        return saida

    def gerar() -> Iterator[str]:
        try:
            for tipo, dados in saida:
                yield _sse(tipo, dados)
        except Exception as exc:
            yield _sse("erro", {"mensagem": str(exc)})

    return StreamingResponse(
        gerar(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------- biblioteca


class Remocao(BaseModel):
    sha1: str


class AbrirPasta(BaseModel):
    caminho: str


def _itens_da_biblioteca() -> list[dict]:
    """
    Cada documento com tudo o que o programa sabe dele.

    Junta tres coisas que moram separadas: o indice de leitura (paginas,
    trechos), o cache de classificacao (tipo, cliente) e as marcas da pessoa
    (fixado, quando foi analisado). Sem juntar, a tela mostraria nome e
    tamanho - que e o que o Explorer ja faz.
    """
    from classify import CacheClassificacao

    cache = CacheClassificacao(CLASSIFICACAO_PATH).dados
    marcas = estado.marcas.de_todos()
    trechos_por_nome: dict[str, int] = {}
    for c in estado.searcher.chunks:
        trechos_por_nome[c.doc_name] = trechos_por_nome.get(c.doc_name, 0) + 1

    itens: list[dict] = []
    for doc in estado.searcher.documents:
        caminho = Path(doc.path)
        try:
            info = caminho.stat()
            tamanho = info.st_size
            modificado = datetime.fromtimestamp(info.st_mtime).isoformat(timespec="seconds")
            existe = True
        except OSError:
            tamanho, modificado, existe = 0, "", False

        conhecido = cache.get(doc.sha1) or {}
        marca = marcas.get(doc.sha1) or {}

        item = {
            "sha1": doc.sha1,
            "nome": doc.name,
            "caminho": str(caminho),
            "pasta": str(caminho.parent),
            "pasta_curta": caminho.parent.name or str(caminho.parent),
            "existe": existe,
            "bytes": tamanho,
            "paginas": doc.pages,
            "caracteres": doc.chars,
            "trechos": trechos_por_nome.get(doc.name, 0),
            "modificado_em": modificado,
            "modificado": acervo.quando(modificado),
            "aberto_em": modificado[:10],
            "fixado": bool(marca.get("fixado")),
            "visto_em": marca.get("visto_em", ""),
            "tipo": conhecido.get("tipo", ""),
            "tipo_rotulo": ROTULOS.get(conhecido.get("tipo", ""), ""),
            "cliente": conhecido.get("cliente", ""),
            "data": conhecido.get("data", ""),
            "valor": conhecido.get("valor", ""),
        }
        item["analise"] = acervo.estado_da_analise(item)
        itens.append(item)

    return itens


@app.get("/api/biblioteca")
def biblioteca(termo: str = "", filtro: str = "todos", ordem: str = "modificacao",
               limite: int = 0) -> dict:
    """
    O que o PAULUS tem aberto, ja procurado, filtrado e ordenado.

    O corte acontece aqui e nao na tela porque procurar inclui o conteudo dos
    documentos, e o conteudo nao esta no navegador. A conta de quantos sobraram
    vem junto: "mostrando 8 de 128" e a diferenca entre "achei pouco" e "tem
    pouco".
    """
    todos = _itens_da_biblioteca()
    trechos = acervo.indexar_trechos(estado.searcher.chunks) if termo else {}

    achados = acervo.procurar(todos, termo, trechos)
    achados = acervo.filtrar(achados, filtro)
    achados = acervo.ordenar(achados, ordem)

    mostrados = achados[:limite] if limite else achados
    return {
        "documentos": mostrados,
        "achados": len(achados),
        "total": len(todos),
        "fixados": sum(1 for i in todos if i["fixado"]),
        "sem_analise": sum(1 for i in todos if not i["tipo"]),
        "filtros": acervo.FILTROS,
        "ordens": acervo.ORDENS,
        "pasta": str(estado.pasta),
        "total_bytes": sum(i["bytes"] for i in todos),
        "total_trechos": len(estado.searcher.chunks),
    }


class MarcarDocumento(BaseModel):
    sha1: str
    fixado: bool = True


class OndeCitou(BaseModel):
    nome: str = ""
    trecho: str = ""
    pergunta: str = ""


@app.post("/api/biblioteca/citacao")
def biblioteca_citacao(payload: OndeCitou) -> dict:
    """
    Em que pagina do documento este trecho esta, e onde marcar.

    A conversa ja dizia de onde tirou cada informacao - mas dizia em texto, e
    conferir exigia abrir o PDF por fora e procurar o paragrafo com o olho.
    Aqui a pagina volta com as coordenadas da marca, e a tela mostra o
    documento de verdade com o trecho destacado.
    """
    doc = next((d for d in estado.searcher.documents if d.name == payload.nome), None)
    if not doc:
        raise HTTPException(status_code=404, detail="esse documento nao esta aberto")

    alvo = Path(doc.path)
    lugar = citacao.onde_esta(alvo, payload.trecho)
    tamanho = alvo.stat().st_size if alvo.exists() else 0

    return {
        **lugar,
        "nome": doc.name,
        "caminho": str(alvo),
        "bytes": tamanho,
        # PDF da para desenhar; docx e txt, nao - e a tela precisa saber disso
        # antes de prometer uma pagina que nao existe.
        "desenhavel": alvo.suffix.lower() == ".pdf" and alvo.exists(),
        "porque": citacao.por_que_este_trecho(payload.pergunta, payload.trecho),
    }


@app.get("/api/biblioteca/pagina")
def biblioteca_pagina(nome: str, numero: int = 1, largura: int = 1000):
    """A pagina do documento desenhada, para conferir sem sair daqui."""
    from fastapi.responses import Response

    doc = next((d for d in estado.searcher.documents if d.name == nome), None)
    if not doc:
        raise HTTPException(status_code=404, detail="esse documento nao esta aberto")
    alvo = Path(doc.path)
    if alvo.suffix.lower() != ".pdf" or not alvo.exists():
        raise HTTPException(status_code=400, detail="so da para desenhar PDF")

    try:
        png = assinatura.pagina_png(alvo, numero, largura=max(240, min(1600, largura)))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"nao consegui desenhar: {exc}") from exc
    return Response(png, media_type="image/png",
                    headers={"Cache-Control": "max-age=120"})


@app.post("/api/biblioteca/fixar")
def biblioteca_fixar(payload: MarcarDocumento) -> dict:
    if not any(d.sha1 == payload.sha1 for d in estado.searcher.documents):
        raise HTTPException(status_code=404, detail="documento nao esta na biblioteca")
    estado.marcas.fixar(payload.sha1, payload.fixado)
    return {"sha1": payload.sha1, "fixado": payload.fixado}


class LoteDocumentos(BaseModel):
    # Caminhos, e nao SHA-1. Dois arquivos iguais byte a byte - "contrato.pdf"
    # e "contrato (1).pdf" - tem o mesmo SHA-1, e escolher por hash faria o
    # lote agir sobre a copia que a pessoa nao marcou. Apagar um e levar dois
    # e exatamente o estrago que a fila existe para impedir.
    caminhos: list[str] = []
    destino: str = ""


def _selecionados(caminhos: list[str]) -> list[dict]:
    escolhidos = set(caminhos)
    itens = [i for i in _itens_da_biblioteca() if i["caminho"] in escolhidos]
    if not itens:
        raise HTTPException(status_code=400, detail="nenhum documento selecionado")
    return itens


@app.post("/api/biblioteca/analisar")
def biblioteca_analisar(payload: LoteDocumentos) -> StreamingResponse:
    """
    Tomar vista de novo: le o documento outra vez e refaz a classificacao.

    Existe porque o arquivo muda depois de analisado - a tela marca esses como
    "mudou desde entao" justamente para que este botao tenha para que servir.

    Vai por evento e nao por resposta unica porque ler com o modelo leva perto
    de um minuto por documento nesta maquina. Oito documentos sao oito minutos
    de tela parada, e o andamento que aparece e o numero de documentos prontos
    - contado, nao estimado.
    """
    from classify import CacheClassificacao

    itens = _selecionados(payload.caminhos)

    habilidade = estado.registro.obter("classificar")
    if not habilidade or not habilidade.executavel:
        raise HTTPException(status_code=503, detail="a habilidade de classificar nao carregou")

    # Sem isto a releitura devolveria o que esta no cache, que e exatamente o
    # resultado que a pessoa pediu para refazer.
    cache = CacheClassificacao(CLASSIFICACAO_PATH)
    for item in itens:
        cache.dados.pop(item["sha1"], None)
    cache.salvar()

    estado.cancelar.clear()
    caminhos = [i["caminho"] for i in itens]

    def gerar() -> Iterator[str]:
        try:
            for tipo, dados in habilidade.executar(_contexto(), caminhos=caminhos):
                if tipo == "resultados":
                    for doc in dados.get("documentos", []):
                        if doc.get("sha1"):
                            estado.marcas.marcar_visto(doc["sha1"])
                    estado.recarregar(force=True)
                yield _sse(tipo, dados)
        except Exception as exc:
            yield _sse("erro", {"mensagem": str(exc)})

    return StreamingResponse(
        gerar(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/biblioteca/lote/mover")
def biblioteca_lote_mover(payload: LoteDocumentos) -> dict:
    """
    Mover muitos de uma vez - pela fila, com o plano a vista.

    Reaproveita o plano do organizador de propósito: e o mesmo executor, o
    mesmo diario e o mesmo desfazer. Mover em lote e a operacao que mais
    estraga quando erra, e nao era hora de inventar um caminho novo para ela.
    """
    if not payload.destino:
        raise HTTPException(status_code=400, detail="escolha a pasta de destino")
    destino = Path(payload.destino)
    if not destino.is_dir():
        raise HTTPException(status_code=400, detail="essa pasta nao existe")

    itens = _selecionados(payload.caminhos)
    plano = acervo.plano_de_mover(itens, destino)
    if not plano["movimentos"]:
        return {"pedido": None, "impedidos": plano["impedidos"],
                "aviso": "nenhum dos escolhidos pode ser movido"}

    pedido = estado.fila.pedir(
        f"Mover {len(plano['movimentos'])} documento(s) para {destino.name}",
        "arquivo",
        acao="organizar.mover",
        resumo=acervo.resumo_do_lote("mover", itens, str(destino)),
        etiquetas=["dá para desfazer"],
        dados={"movimentos": plano["movimentos"], "destino": str(destino),
               "padrao": "escolha na biblioteca", "ignorados": []},
    )
    return {"pedido": pedido.to_dict(), "impedidos": plano["impedidos"],
            **estado.fila.para_tela()}


@app.post("/api/biblioteca/lote/apagar")
def biblioteca_lote_apagar(payload: LoteDocumentos) -> dict:
    """Tirar muitos da biblioteca de uma vez - pela fila, porque nao desfaz."""
    itens = _selecionados(payload.caminhos)
    pasta = Path(estado.pasta).resolve()

    dentro, fora = [], []
    for item in itens:
        if pasta in Path(item["caminho"]).resolve().parents:
            dentro.append(item)
        else:
            fora.append({"nome": item["nome"],
                         "motivo": "está fora da pasta do programa"})

    if not dentro:
        return {"pedido": None, "impedidos": fora,
                "aviso": "nenhum dos escolhidos está na pasta do programa"}

    pedido = estado.fila.pedir(
        f"Tirar {len(dentro)} documento(s) da biblioteca",
        "arquivo",
        acao="acervo.apagar",
        resumo=acervo.resumo_do_lote("apagar", dentro),
        etiquetas=["não dá para desfazer"],
        dados={"caminhos": [i["caminho"] for i in dentro],
               "nomes": [i["nome"] for i in dentro]},
    )
    return {"pedido": pedido.to_dict(), "impedidos": fora, **estado.fila.para_tela()}


@app.post("/api/biblioteca/lote/exportar")
def biblioteca_lote_exportar(payload: LoteDocumentos) -> dict:
    """Copiar muitos para uma pasta de fora - pela fila, porque sai daqui."""
    if not payload.destino:
        raise HTTPException(status_code=400, detail="escolha a pasta de destino")
    destino = Path(payload.destino)
    if not destino.is_dir():
        raise HTTPException(status_code=400, detail="essa pasta nao existe")

    itens = _selecionados(payload.caminhos)
    pedido = estado.fila.pedir(
        f"Copiar {len(itens)} documento(s) para {destino.name}",
        "arquivo",
        acao="acervo.exportar",
        resumo=acervo.resumo_do_lote("exportar", itens, str(destino)),
        etiquetas=["dá para desfazer"],
        dados={"caminhos": [i["caminho"] for i in itens], "destino": str(destino)},
    )
    return {"pedido": pedido.to_dict(), **estado.fila.para_tela()}


@app.post("/api/biblioteca/remover")
def biblioteca_remover(payload: Remocao) -> dict:
    """
    Tira um documento da biblioteca, apagando a copia que o programa guarda.

    So mexe em arquivo dentro da pasta do programa: o original de onde o
    documento veio nao e tocado.
    """
    alvo = next((d for d in estado.searcher.documents if d.sha1 == payload.sha1), None)
    if not alvo:
        raise HTTPException(status_code=404, detail="documento nao esta na biblioteca")

    caminho = Path(alvo.path).resolve()
    pasta = Path(estado.pasta).resolve()
    if pasta not in caminho.parents:
        raise HTTPException(
            status_code=400,
            detail="esse arquivo está fora da pasta do programa; remova por lá",
        )

    try:
        caminho.unlink(missing_ok=True)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"não consegui remover: {exc}") from exc

    return {"removido": alvo.name, "documentos": estado.recarregar(force=True)}


@app.post("/api/biblioteca/abrir-pasta")
def biblioteca_abrir_pasta(payload: AbrirPasta) -> dict:
    """Abre a pasta no Explorer, para a pessoa ver o arquivo onde ele esta."""
    import os

    alvo = Path(payload.caminho)
    if not alvo.is_dir():
        raise HTTPException(status_code=400, detail="pasta nao encontrada")
    try:
        os.startfile(str(alvo))  # noqa: S606 - abre o gerenciador do proprio Windows
    except (OSError, AttributeError) as exc:
        raise HTTPException(status_code=500, detail=f"não consegui abrir: {exc}") from exc
    return {"aberta": str(alvo)}


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


@app.post("/api/buscar-agora")
def buscar_agora(payload: Busca) -> dict:
    """Atalho para a habilidade `buscar`, mantido para nao quebrar chamadas antigas."""
    habilidade = estado.registro.obter("buscar")
    if not habilidade or not habilidade.executavel:
        raise HTTPException(status_code=503, detail="a habilidade de busca nao carregou")
    return habilidade.executar(_contexto(), termo=payload.termo, top=payload.top)


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


class Renomear(BaseModel):
    titulo: str


class MoverGrupo(BaseModel):
    grupo: str


@app.post("/api/trabalhos/{id_}/renomear")
def trabalhos_renomear(id_: str, payload: Renomear) -> dict:
    trabalho = estado.trabalhos.obter(id_)
    if not trabalho:
        raise HTTPException(status_code=404, detail="conversa nao encontrada")

    titulo = " ".join(payload.titulo.split())[:80]
    if not titulo:
        raise HTTPException(status_code=400, detail="o nome nao pode ficar vazio")

    trabalho.titulo = titulo
    estado.trabalhos.salvar(trabalho)
    return trabalho.resumo()


@app.post("/api/trabalhos/{id_}/grupo")
def trabalhos_grupo(id_: str, payload: MoverGrupo) -> dict:
    trabalho = estado.trabalhos.obter(id_)
    if not trabalho:
        raise HTTPException(status_code=404, detail="conversa nao encontrada")

    trabalho.grupo = " ".join(payload.grupo.split())[:40]
    trabalho.atualizado_em = jobs_agora()
    estado.trabalhos.salvar(trabalho)
    return trabalho.resumo()


@app.post("/api/trabalhos/{id_}/duplicar")
def trabalhos_duplicar(id_: str) -> dict:
    copia = estado.trabalhos.duplicar(id_)
    if not copia:
        raise HTTPException(status_code=404, detail="conversa nao encontrada")
    return copia.to_dict()


@app.get("/api/agora")
def acontecendo_agora() -> dict:
    """
    O que esta acontecendo neste instante, para os cartoes da tela inicial.

    Tudo com numero real: cartao que diz "processando" sem dizer quanto falta
    e enfeite, nao informacao.
    """
    abertos = [
        estado.trabalhos.obter(t["id"])
        for t in estado.trabalhos.listar()["em_andamento"]
    ]
    abertos = [t for t in abertos if t]

    executando = []
    esperando = []
    for trabalho in abertos:
        if trabalho.aprovacao:
            esperando.append({
                "id": trabalho.id,
                "titulo": trabalho.titulo,
                "pergunta": trabalho.aprovacao.pergunta,
            })
            continue
        if trabalho.estado == EXECUTANDO:
            atual = next((e for e in trabalho.etapas if e.estado == EXECUTANDO), None)
            executando.append({
                "id": trabalho.id,
                "titulo": trabalho.titulo,
                "etapa": atual.titulo if atual else "",
                "feitos": atual.feitos if atual else 0,
                "total": atual.total if atual else 0,
                "progresso": trabalho.progresso or 0,
            })

    return {
        "executando": executando,
        "esperando": esperando,
        "biblioteca": {
            "documentos": len(estado.searcher.documents),
            "trechos": len(estado.searcher.chunks),
        },
        "pausados": sum(1 for t in abertos if t.estado == "pausado"),
    }


@app.delete("/api/trabalhos/{id_}")
def trabalhos_remover(id_: str) -> dict:
    if not estado.trabalhos.remover(id_):
        raise HTTPException(status_code=404, detail="trabalho nao encontrado")
    return {"removido": id_}


@app.post("/api/trabalhos/{id_}/perguntar")
def trabalhos_perguntar(id_: str, payload: Pergunta) -> StreamingResponse:
    """
    Pergunta dentro de um trabalho.

    A logica de responder mora em habilidades/perguntar.py. Aqui fica so a
    contabilidade do trabalho: gravar a conversa, mexer nas etapas e salvar.
    """
    trabalho = estado.trabalhos.obter(id_)
    if not trabalho:
        raise HTTPException(status_code=404, detail="trabalho nao encontrado")
    if not payload.pergunta.strip():
        raise HTTPException(status_code=400, detail="pergunta vazia")

    habilidade = estado.registro.obter("perguntar")
    if not habilidade or not habilidade.executavel:
        raise HTTPException(status_code=503, detail="a habilidade de perguntar nao carregou")

    pergunta = payload.pergunta.strip()
    if trabalho.titulo == "Nova conversa" and not trabalho.mensagens:
        trabalho.titulo = titular(pergunta)

    trabalho.dizer("pessoa", pergunta)

    # Antes de sair procurando: o que a pessoa pediu? A conversa tinha um
    # caminho so, e "anote uma reuniao no calendario" virava busca pela
    # palavra "reuniao" dentro dos contratos - resposta certa para a pergunta
    # errada. Ler a intencao e por regra: instantaneo e repetivel.
    lido = intencao.ler(pergunta, documentos=estado.searcher.documents)
    if lido.tipo in ("agenda", "tarefa", "sobre", "abrir"):
        return _responder_sem_documentos(trabalho, lido, pergunta)

    trabalho.etapas = [
        Etapa("Procurar nos documentos", estado=EXECUTANDO),
        Etapa("Ler os trechos e responder"),
    ]
    trabalho.estado = EXECUTANDO
    estado.trabalhos.salvar(trabalho)

    def registrar(texto: str) -> None:
        trabalho.registrar(texto)

    def gerar() -> Iterator[str]:
        import time

        inicio = time.time()
        partes: list[str] = []
        cobertura: dict = {}
        fontes: list[dict] = []
        medida: dict = {}
        lido_chars = 0

        try:
            for tipo, dados in habilidade.executar(
                _contexto(registrar), pergunta=pergunta, top=payload.top
            ):
                if tipo == "fontes":
                    cobertura = {
                        "consultados": dados["consultados"],
                        "ignorados": dados["ignorados"],
                        "total_contratos": dados["total_contratos"],
                    }
                    fontes = dados["trechos"]
                    trabalho.etapas[0].estado = CONCLUIDO
                    trabalho.etapas[0].detalhe = (
                        _quantos(dados["total_contratos"], "documento") + ", "
                        + _quantos(len(fontes), "trecho"))
                    # Sem 25/25 aqui: os dois numeros chegavam juntos, e uma
                    # barra que nasce cheia nao e progresso - e enfeite.
                    yield _sse("fontes", dados)
                    yield _sse("etapas", {"etapas": [asdict_etapa(e) for e in trabalho.etapas]})
                elif tipo == "lendo":
                    lido_chars = dados["caracteres"]
                    trabalho.etapas[1].titulo = "Lendo os documentos"
                    trabalho.etapas[1].estado = EXECUTANDO
                    trabalho.etapas[1].detalhe = f"{dados['caracteres']:,}".replace(",", ".") + " caracteres"
                    yield _sse("lendo", dados)
                    yield _sse("etapas", {"etapas": [asdict_etapa(e) for e in trabalho.etapas]})
                elif tipo == "escrevendo":
                    # A leitura acabou de verdade: a primeira palavra saiu.
                    trabalho.etapas[1].estado = CONCLUIDO
                    trabalho.etapas[1].detalhe = f"{dados['lendo_segundos']} s"
                    trabalho.etapas.append(Etapa("Escrevendo a resposta", estado=EXECUTANDO))
                    yield _sse("escrevendo", dados)
                    yield _sse("etapas", {"etapas": [asdict_etapa(e) for e in trabalho.etapas]})
                elif tipo == "medida":
                    medida = dados
                    yield _sse("medida", dados)
                elif tipo == "token":
                    partes.append(dados["t"])
                    yield _sse("token", dados)
                elif tipo == "vazio":
                    trabalho.etapas[0].estado = CONCLUIDO
                    trabalho.etapas[1].estado = CONCLUIDO
                    trabalho.estado = CONCLUIDO
                    trabalho.dizer("paulus", dados["mensagem"])
                    estado.trabalhos.salvar(trabalho)
                    yield _sse("vazio", dados)
                    return
                elif tipo == "fim":
                    pass  # o fechamento e daqui: o modulo nao sabe de trabalho
        except Exception as exc:
            trabalho.etapas[1].estado = "falhou"
            trabalho.estado = "falhou"
            estado.trabalhos.salvar(trabalho)
            yield _sse("erro", {"mensagem": str(exc)})
            return

        segundos = round(time.time() - inicio, 1)

        # O que acabou de acontecer entra no historico da maquina: e dele que
        # sai o "leituras deste tamanho levaram ~70 s aqui" da proxima vez.
        if medida and lido_chars:
            estado.ritmo.anotar(
                modelo=estado.client.model,
                caracteres=lido_chars,
                # A espera, e nao o tempo de calculo do modelo: a previsao
                # existe para dizer quanto a pessoa vai esperar, e a espera
                # inclui carregar o modelo quando ele esta frio.
                segundos_lendo=medida.get("esperou_segundos") or medida.get("lendo_segundos", 0),
                palavras=len("".join(partes).split()),
                segundos_escrevendo=medida.get("escrevendo_segundos", 0),
            )

        for etapa in trabalho.etapas:
            if etapa.estado == EXECUTANDO:
                etapa.estado = CONCLUIDO
        trabalho.estado = CONCLUIDO
        trabalho.dizer(
            "paulus", "".join(partes).strip(),
            fontes=fontes, cobertura=cobertura, segundos=segundos,
        )
        estado.trabalhos.salvar(trabalho)
        yield _sse("fim", {"segundos": segundos, "titulo": trabalho.titulo})

    return StreamingResponse(
        gerar(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class PropostaConfirmada(BaseModel):
    tipo: str = ""
    campos: dict = {}


@app.post("/api/trabalhos/{id_}/fazer")
def trabalhos_fazer(id_: str, payload: PropostaConfirmada) -> dict:
    """
    Grava o que a pessoa confirmou na conversa.

    A rota existe separada de propósito: entender a frase e gravar sao dois
    passos, e o segundo so acontece depois do sim. Os campos que chegam aqui
    sao os que estavam na tela - a pessoa pode ter corrigido a data ou a hora
    antes de confirmar, e vale o que ela deixou.
    """
    trabalho = estado.trabalhos.obter(id_)
    if not trabalho:
        raise HTTPException(status_code=404, detail="trabalho nao encontrado")

    campos = dict(payload.campos or {})
    try:
        if payload.tipo == "abrir":
            nome = str(campos.get("nome", ""))
            doc = next((d for d in estado.searcher.documents if d.name == nome), None)
            if not doc:
                raise HTTPException(status_code=404, detail="esse documento nao esta mais aberto")
            alvo = Path(doc.path)
            if not alvo.exists():
                raise HTTPException(status_code=404, detail="o arquivo saiu do lugar")
            import os

            os.startfile(str(alvo))  # noqa: S606 - abre no programa do proprio Windows
            novo = 0
            feito = {"nome": nome, "caminho": str(alvo)}
            resumo = f"Abri “{nome}” no programa padrao do Windows"
            onde = "biblioteca"
        elif payload.tipo == "agenda":
            novo = estado.agenda.salvar(campos)
            feito = estado.agenda.obter(novo)
            resumo = (f"Anotei “{feito['titulo']}” em {escritorio._br(feito['data'])} "
                      f"às {feito['hora']}")
            if feito.get("avisar_min"):
                resumo += f", avisando {feito['avisar_min']} minutos antes"
            onde = "calendario"
        elif payload.tipo == "tarefa":
            novo = estado.tarefas.salvar(campos)
            feito = estado.tarefas.obter(novo)
            resumo = f"Criei a tarefa “{feito['titulo']}”"
            if feito.get("prazo"):
                resumo += f", com prazo em {escritorio._br(feito['prazo'])}"
            onde = "tarefas"
        else:
            raise HTTPException(status_code=400, detail="nao sei fazer isso")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    trabalho.dizer("paulus", resumo + ".", feito={"tipo": payload.tipo, "id": novo, "onde": onde})
    estado.trabalhos.salvar(trabalho)
    return {"id": novo, "resumo": resumo, "onde": onde, "registro": feito}


def _responder_sem_documentos(trabalho, lido, pergunta: str) -> StreamingResponse:
    """
    O que nao precisa ler documento nenhum.

    Duas coisas caem aqui. Uma acao sobre a agenda ou as tarefas vira uma
    PROPOSTA, com os campos a vista - entender nao e fazer, e nada entra no
    calendario de alguem por interpretacao de frase. E pergunta sobre o proprio
    programa e respondida do registro de habilidades, sem modelo: a lista do
    que ele faz esta declarada no codigo, e passar isso por um modelo de 3
    bilhoes de parametros so acrescentaria chance de erro.
    """
    def gerar() -> Iterator[str]:
        if lido.tipo == "sobre":
            texto = _o_que_eu_faco()
            trabalho.etapas = [Etapa("Responder", estado=CONCLUIDO)]
            trabalho.estado = CONCLUIDO
            trabalho.dizer("paulus", texto)
            estado.trabalhos.salvar(trabalho)
            yield _sse("token", {"t": texto})
            yield _sse("fim", {"segundos": 0, "titulo": trabalho.titulo})
            return

        proposta = {
            "tipo": lido.tipo,
            "titulo": lido.titulo,
            "campos": lido.campos,
            "porque": lido.porque,
            "falta": lido.falta,
            "pergunta": pergunta,
        }
        trabalho.etapas = [Etapa("Entender o pedido", estado=CONCLUIDO)]
        trabalho.estado = CONCLUIDO
        trabalho.dizer("paulus", "", proposta=proposta)
        estado.trabalhos.salvar(trabalho)
        yield _sse("proposta", proposta)
        yield _sse("fim", {"segundos": 0, "titulo": trabalho.titulo})

    return StreamingResponse(
        gerar(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _o_que_eu_faco() -> str:
    """
    O que o programa faz, montado do proprio programa.

    Sai da lista de telas e do registro de habilidades - nao de um texto
    escrito a mao. Um texto a mao envelhece na primeira tela nova: passa a
    prometer o que nao existe, ou a esconder o que existe. E o que esta em pe
    e o que ainda nao esta saem separados, porque a diferenca e a informacao.
    """
    grupos = destinos.por_grupo()

    linhas = ["Eu trabalho com o que está nesta máquina. Nada sai daqui.", ""]
    faltando: list[str] = []

    for bloco in grupos:
        prontas = [d for d in bloco["destinos"] if d["pronta"]]
        faltando += [d["nome"] for d in bloco["destinos"] if not d["pronta"]]
        if not prontas:
            continue
        # Sem asterisco: a conversa mostra texto puro, e "**Documentos**"
        # apareceria com os asteriscos na tela.
        linhas.append(bloco["grupo"].upper())
        linhas += [f"  {d['nome']} — {d['resolve'][0].lower() + d['resolve'][1:]}"
                   for d in prontas]
        linhas.append("")

    linhas += [
        "AQUI NA CONVERSA",
        "  perguntar sobre os documentos abertos, com o trecho de origem à vista",
        "  anotar na agenda — “anote uma reunião dia 20/10 às 14h com lembrete "
        "30 minutos antes”",
        "  criar tarefa — “crie uma tarefa para revisar o contrato até sexta”",
        "",
        "Antes de gravar qualquer coisa eu mostro o que entendi, e você "
        "confirma. As outras telas estão no menu à esquerda.",
    ]

    if faltando:
        linhas += ["", "Ainda não faço: " + ", ".join(faltando) + "."]

    return "\n".join(linhas)


def _quantos(n: int, palavra: str, muitos: str = "") -> str:
    """"1 documento", "6 documentos" - nunca "6 documento(s)"."""
    return f"{n} {palavra if n == 1 else (muitos or palavra + 's')}"


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


# ----------------------------------------------------------------- agenda


class FichaCompromisso(BaseModel):
    id: int | None = None
    dados: dict = {}


class NotaDia(BaseModel):
    dia: str
    texto: str = ""


def _documentos_com_data() -> list[dict]:
    from classify import CacheClassificacao

    return list(CacheClassificacao(CLASSIFICACAO_PATH).dados.values())


@app.get("/api/agenda")
def agenda_grade(de: str = "", ate: str = "") -> dict:
    """
    Tudo o que tem data no periodo: compromisso, prazo de tarefa e data de
    contrato na mesma grade.
    """
    from datetime import date, timedelta

    if not de or not ate:
        hoje = date.today()
        de = (hoje - timedelta(days=hoje.day - 1)).isoformat()
        ate = (date.fromisoformat(de) + timedelta(days=45)).isoformat()

    grade = estado.agenda.grade(de, ate, estado.tarefas.listar("todas"), _documentos_com_data())
    grade["compromissos"] = estado.agenda.listar(de, ate)
    grade["tipos"] = [{"valor": k, "rotulo": v} for k, v in TIPOS_AGENDA.items()]
    grade["ondes"] = [{"valor": k, "rotulo": v} for k, v in ONDES.items() if k]
    grade["clientes"] = [{"id": f["id"], "nome": f["nome"]} for f in estado.cadastros.listar()]
    return grade


@app.get("/api/agenda/dia")
def agenda_dia(dia: str) -> dict:
    tarefas = [t for t in estado.tarefas.listar("todas") if t.get("prazo") == dia]
    return {
        "dia": dia,
        "compromissos": estado.agenda.listar(dia, dia),
        "tarefas": tarefas,
        "nota": estado.agenda.nota(dia),
    }


@app.post("/api/agenda")
def agenda_salvar(payload: FichaCompromisso) -> dict:
    try:
        id_ = estado.agenda.salvar(payload.dados, payload.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return estado.agenda.obter(id_) or {}


@app.delete("/api/agenda/{id_}")
def agenda_apagar(id_: int) -> dict:
    if not estado.agenda.apagar(id_):
        raise HTTPException(status_code=404, detail="compromisso nao encontrado")
    return {"apagado": id_}


@app.post("/api/agenda/nota")
def agenda_nota(payload: NotaDia) -> dict:
    estado.agenda.gravar_nota(payload.dia, payload.texto)
    return {"dia": payload.dia, "texto": payload.texto}


@app.get("/api/agenda/livres")
def agenda_livres(duracao: int = 60, dia: str = "") -> dict:
    """Horarios em que cabe um compromisso desse tamanho."""
    regra = estado.prefs.dados.get("disponibilidade", {})
    if dia:
        return {"dia": dia, "horarios": estado.agenda.livres(dia, duracao, regra)}
    return {"proximos": estado.agenda.proximos_livres(duracao, regra)}


# -------------------------------------------------------------- cadastros


class FichaCadastro(BaseModel):
    id: int | None = None
    dados: dict = {}


class VinculoDoc(BaseModel):
    sha1: str
    nome: str = ""


@app.get("/api/cadastros")
def cadastros_listar(tipo: str = "", termo: str = "", ordem: str = "nome") -> dict:
    return {
        "fichas": estado.cadastros.listar(tipo, termo, ordem),
        "contagem": estado.cadastros.contagem(),
        "ordens": {"nome": "A–Z", "aberto": "em aberto", "atraso": "atraso"},
        "tipos": [{"valor": k, "rotulo": v} for k, v in TIPOS_CADASTRO.items()],
    }


@app.get("/api/cadastros/sugestoes")
def cadastros_sugestoes() -> dict:
    """Quem ja aparece nos documentos e ainda nao tem ficha."""
    return {"sugestoes": estado.cadastros.sugestoes(CLASSIFICACAO_PATH)}


@app.post("/api/cadastros")
def cadastros_salvar(payload: FichaCadastro) -> dict:
    try:
        id_ = estado.cadastros.salvar(payload.dados, payload.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return estado.cadastros.obter(id_) or {}


@app.post("/api/cadastros/{id_}/vincular")
def cadastros_vincular(id_: int, payload: VinculoDoc) -> dict:
    if not estado.cadastros.obter(id_):
        raise HTTPException(status_code=404, detail="cadastro nao encontrado")
    estado.cadastros.vincular(id_, payload.sha1, payload.nome)
    return estado.cadastros.obter(id_) or {}


@app.delete("/api/cadastros/{id_}")
def cadastros_apagar(id_: int) -> dict:
    if not estado.cadastros.apagar(id_):
        raise HTTPException(status_code=404, detail="cadastro nao encontrado")
    return {"apagado": id_}


# ---------------------------------------------------------------- tarefas


class FichaTarefa(BaseModel):
    id: int | None = None
    dados: dict = {}


class MarcaTarefa(BaseModel):
    valor: bool = True


class NovaEtapa(BaseModel):
    titulo: str


@app.get("/api/tarefas")
def tarefas_listar(filtro: str = "meu_dia", lista: str = "") -> dict:
    return {
        "tarefas": estado.tarefas.listar(filtro, lista),
        "contagens": estado.tarefas.contagens(),
        "listas": estado.tarefas.listas(),
        "clientes": [
            {"id": f["id"], "nome": f["nome"]}
            for f in estado.cadastros.listar()
        ],
        "repeticoes": [
            {"valor": k, "rotulo": v} for k, v in tarefas_mod.REPETICOES.items()
        ],
    }


@app.get("/api/tarefas/sugestoes")
def tarefas_sugestoes() -> dict:
    """Prazos que os documentos ja lidos pedem para conferir."""
    from classify import CacheClassificacao

    cache = CacheClassificacao(CLASSIFICACAO_PATH).dados
    return {"sugestoes": estado.tarefas.sugerir(list(cache.values()))}


@app.post("/api/tarefas")
def tarefas_salvar(payload: FichaTarefa) -> dict:
    try:
        id_ = estado.tarefas.salvar(payload.dados, payload.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return estado.tarefas.obter(id_) or {}


@app.post("/api/tarefas/{id_}/concluir")
def tarefas_concluir(id_: int, payload: MarcaTarefa) -> dict:
    """Concluir uma tarefa que repete ja deixa a proxima no lugar."""
    resultado = estado.tarefas.concluir(id_, payload.valor)
    saida = estado.tarefas.obter(id_) or {"apagada": True}
    if resultado.get("proxima"):
        proxima = estado.tarefas.obter(resultado["proxima"])
        saida["proxima"] = proxima
        saida["aviso_repeticao"] = (
            f"criei a próxima para {proxima['prazo']}" if proxima and proxima.get("prazo") else ""
        )
    return saida


@app.post("/api/tarefas/{id_}/importante")
def tarefas_importante(id_: int, payload: MarcaTarefa) -> dict:
    estado.tarefas.marcar_importante(id_, payload.valor)
    return estado.tarefas.obter(id_) or {}


@app.post("/api/tarefas/{id_}/meu-dia")
def tarefas_meu_dia(id_: int, payload: MarcaTarefa) -> dict:
    estado.tarefas.marcar_meu_dia(id_, payload.valor)
    return estado.tarefas.obter(id_) or {}


@app.post("/api/tarefas/{id_}/etapas")
def tarefas_nova_etapa(id_: int, payload: NovaEtapa) -> dict:
    try:
        estado.tarefas.nova_etapa(id_, payload.titulo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return estado.tarefas.obter(id_) or {}


@app.post("/api/etapas/{id_}")
def etapa_marcar(id_: int, payload: MarcaTarefa) -> dict:
    estado.tarefas.marcar_etapa(id_, payload.valor)
    return {"ok": True}


@app.get("/api/tarefas/{id_}/vinculos")
def tarefas_vinculos(id_: int) -> dict:
    """Os documentos ligados a tarefa, com o caminho de cada um se ainda existir."""
    from classify import CacheClassificacao

    cache = CacheClassificacao(CLASSIFICACAO_PATH).dados
    por_sha = {d.path: d for d in estado.searcher.documents}
    achados = []
    for v in estado.tarefas.vinculos_de(id_):
        doc = next((d for d in estado.searcher.documents if d.sha1 == v["sha1"]), None)
        conhecido = cache.get(v["sha1"]) or {}
        achados.append({
            **v,
            "existe": doc is not None,
            "caminho": doc.path if doc else "",
            "tipo_rotulo": ROTULOS.get(conhecido.get("tipo", ""), ""),
        })
    return {"vinculos": achados}


@app.post("/api/tarefas/{id_}/vincular")
def tarefas_vincular(id_: int, payload: VinculoDoc) -> dict:
    if not estado.tarefas.obter(id_):
        raise HTTPException(status_code=404, detail="tarefa não encontrada")
    estado.tarefas.vincular(id_, payload.sha1, payload.nome)
    return tarefas_vinculos(id_)


@app.delete("/api/vinculos/{id_}")
def vinculo_apagar(id_: int) -> dict:
    estado.tarefas.desvincular(id_)
    return {"removido": id_}


@app.delete("/api/tarefas/{id_}")
def tarefas_apagar(id_: int) -> dict:
    if not estado.tarefas.apagar(id_):
        raise HTTPException(status_code=404, detail="tarefa nao encontrada")
    return {"apagada": id_}


# ------------------------------------------------------------- aprovacoes


class Decisao(BaseModel):
    ids: list[str] = []
    aprovar: bool = True


@app.get("/api/aprovacoes")
def aprovacoes_listar() -> dict:
    return estado.fila.para_tela()


@app.post("/api/aprovacoes/decidir")
def aprovacoes_decidir(payload: Decisao) -> dict:
    """
    Aprova ou recusa. Aprovar executa a acao; recusar so encerra o pedido.

    A execucao nao mora na fila: cada acao e feita por quem sabe faze-la, e o
    resultado volta para o pedido. Assim a fila nao precisa entender de mover
    arquivo, assinar ou enviar.
    """
    feitos, falhas = [], []

    for id_ in payload.ids:
        pedido = estado.fila.decidir(id_, payload.aprovar)
        if not pedido:
            falhas.append({"id": id_, "motivo": "pedido nao esta mais na fila"})
            continue

        if not payload.aprovar:
            feitos.append({"id": id_, "estado": pedido.estado})
            continue

        executor = EXECUTORES.get(pedido.acao)
        if not executor:
            estado.fila.registrar_resultado(id_, "aprovado, sem nada a executar")
            feitos.append({"id": id_, "estado": pedido.estado})
            continue

        try:
            resultado = executor(pedido)
            estado.fila.registrar_resultado(id_, resultado)
            feitos.append({"id": id_, "estado": pedido.estado, "resultado": resultado})
        except Exception as exc:
            estado.fila.registrar_resultado(id_, f"nao consegui: {exc}", falhou=True)
            falhas.append({"id": id_, "motivo": str(exc)})

    return {"feitos": feitos, "falhas": falhas, **estado.fila.para_tela()}


def _executar_mover(pedido) -> str:
    """Executa um plano de organizacao que estava esperando aprovacao."""
    from organize import Movimento, Plano

    dados = pedido.dados
    plano = Plano(
        movimentos=[Movimento(**m) for m in dados.get("movimentos", [])],
        destino=dados.get("destino", ""),
        padrao=dados.get("padrao", ""),
        ignorados=dados.get("ignorados", []),
    )
    resultado = aplicar_plano(plano, DIARIOS_DIR)
    estado.recarregar(force=True)
    if resultado.falhas:
        return f"{resultado.movidos} movido(s), {len(resultado.falhas)} falha(s)"
    return f"{resultado.movidos} arquivo(s) movido(s)"


def _executar_assinar(pedido) -> str:
    """Assina o que estava esperando o sim na fila."""
    senha = estado.cofre.senha_agora()
    if not senha:
        raise RuntimeError("a senha do certificado expirou - abra o certificado e tente de novo")

    resultado = _assinar_de_fato(pedido.dados, senha)
    if resultado.erro:
        raise RuntimeError(resultado.erro)

    aviso = "" if resultado.icp_brasil else " (certificado fora da ICP-Brasil)"
    return f"assinado, codigo {resultado.codigo}{aviso}"


def _executar_enviar(pedido) -> str:
    """Manda o e-mail que estava esperando o sim na fila."""
    resultado = _enviar_de_fato(pedido.dados)
    quem = ", ".join(resultado.get("para", []))
    anexos = resultado.get("anexos") or []
    return f"enviado para {quem}" + (f" com {len(anexos)} anexo(s)" if anexos else "")


def _executar_apagar_do_acervo(pedido) -> str:
    """
    Tira da biblioteca o que a pessoa aprovou tirar.

    So apaga dentro da pasta do programa, e confere de novo na hora de apagar:
    o pedido pode ter ficado na fila tempo suficiente para o arquivo ter sido
    movido para fora, e apagar fora daqui seria apagar o original de alguem.
    """
    import shutil

    pasta = Path(estado.pasta).resolve()
    apagados, recusados = 0, []

    for bruto in pedido.dados.get("caminhos", []):
        alvo = Path(bruto)
        try:
            resolvido = alvo.resolve()
        except OSError:
            recusados.append(alvo.name)
            continue
        if pasta not in resolvido.parents:
            recusados.append(alvo.name)
            continue
        try:
            resolvido.unlink(missing_ok=True)
            apagados += 1
        except OSError:
            recusados.append(alvo.name)

    estado.recarregar(force=True)
    if recusados:
        return f"{apagados} tirado(s); nao mexi em {len(recusados)}: {', '.join(recusados[:3])}"
    return f"{apagados} documento(s) tirado(s) da biblioteca"


def _executar_exportar(pedido) -> str:
    """Copia para fora da pasta do programa, sem passar por cima de nada."""
    import shutil

    destino = Path(pedido.dados.get("destino", ""))
    if not destino.is_dir():
        raise RuntimeError("a pasta de destino nao existe mais")

    copiados, falhas = 0, []
    for bruto in pedido.dados.get("caminhos", []):
        origem = Path(bruto)
        if not origem.exists():
            falhas.append(origem.name)
            continue
        alvo = destino / origem.name
        if alvo.exists():
            alvo = acervo._nome_livre(destino, origem.name, set())
        try:
            shutil.copy2(origem, alvo)
            copiados += 1
        except OSError:
            falhas.append(origem.name)

    if falhas:
        return f"{copiados} copiado(s); nao consegui {len(falhas)}: {', '.join(falhas[:3])}"
    return f"{copiados} documento(s) copiado(s) para {destino}"


EXECUTORES = {
    "organizar.mover": _executar_mover,
    "acervo.apagar": _executar_apagar_do_acervo,
    "acervo.exportar": _executar_exportar,
    "assinatura.assinar": _executar_assinar,
    "correio.enviar": _executar_enviar,
}


# ------------------------------------------------- folha, notas e boletos


class MesPedido(BaseModel):
    mes: str = ""


class FichaPapel(BaseModel):
    id: int | None = None
    dados: dict = {}


@app.get("/api/financeiro/folha")
def folha_ler(mes: str = "") -> dict:
    mes = mes or escritorio.mes_de_hoje()
    return {
        "folha": estado.folha.do_mes(mes),
        "candidatos": estado.folha.pessoas(),
        "vinculos": [{"valor": k, "rotulo": v} for k, v in escritorio.VINCULOS.items()],
    }


@app.post("/api/financeiro/folha/montar")
def folha_montar(payload: MesPedido) -> dict:
    """Copia os valores dos cadastros para a folha do mes."""
    try:
        return {"folha": estado.folha.montar(payload.mes)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/financeiro/folha/pagar")
def folha_pagar(payload: MesPedido) -> dict:
    """
    A folha do mes vira uma conta a pagar.

    Um lancamento so, e nao um por pessoa: o que sai do caixa e a folha
    inteira, e o detalhamento por pessoa ja esta gravado na folha. Espalhar
    seis lancamentos no extrato esconderia o numero que importa.
    """
    mes = payload.mes or escritorio.mes_de_hoje()
    da_folha = estado.folha.do_mes(mes)
    if not da_folha["quantos"]:
        raise HTTPException(status_code=400, detail="monte a folha deste mes antes")
    if da_folha["lancamento_id"]:
        raise HTTPException(status_code=400, detail="a folha deste mes ja esta lancada")

    ultimo = escritorio.ultimo_dia(mes)
    id_ = estado.financeiro.salvar({
        "tipo": "despesa",
        "descricao": f"Folha de {escritorio.mes_por_extenso(mes)}",
        "centavos": da_folha["total"],
        "categoria": "folha",
        "vencimento": ultimo,
        "observacao": f"{da_folha['quantos']} pessoa(s)",
    })
    estado.folha.ligar_ao_lancamento(mes, id_)
    return {"folha": estado.folha.do_mes(mes), "lancamento": estado.financeiro.obter(id_)}


@app.post("/api/financeiro/folha/recibos")
def folha_recibos(payload: MesPedido) -> dict:
    """
    Um recibo em PDF por pessoa, na pasta do programa.

    O recibo sai com o valor que esta gravado na folha daquele mes - nao com o
    salario de hoje. E essa a razao de a folha ser copia.
    """
    mes = payload.mes or escritorio.mes_de_hoje()
    da_folha = estado.folha.do_mes(mes)
    if not da_folha["quantos"]:
        raise HTTPException(status_code=400, detail="monte a folha deste mes antes")

    # Quem paga e quem esta configurado em Preferencias. Sem isso o recibo
    # sairia dizendo "recebi de este escritorio", que nao serve de recibo.
    pessoa = estado.prefs.dados.get("pessoa", {})
    quem_paga = str(pessoa.get("nome", "")).strip()

    destino = RECIBOS_DIR / mes
    try:
        feitos = escritorio.gerar_recibos(
            da_folha, destino, escritorio.mes_por_extenso(mes), quem_paga)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"nao consegui gerar: {exc}") from exc

    return {"recibos": feitos, "pasta": str(destino)}


@app.get("/api/financeiro/papeis")
def papeis_listar(tipo: str = "", mes: str = "") -> dict:
    mes = mes or escritorio.mes_de_hoje()
    return {
        "notas": estado.papeis.listar("nota", mes),
        "boletos": estado.papeis.listar("boleto"),
        "a_emitir": estado.papeis.a_emitir(mes),
    }


@app.post("/api/financeiro/papeis")
def papeis_salvar(payload: FichaPapel) -> dict:
    try:
        id_ = estado.papeis.salvar(payload.dados, payload.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": id_, **papeis_listar(mes=str(payload.dados.get("data", ""))[:7])}


@app.delete("/api/financeiro/papeis/{id_}")
def papeis_apagar(id_: int) -> dict:
    if not estado.papeis.apagar(id_):
        raise HTTPException(status_code=404, detail="nao achei esse registro")
    return {"apagado": id_}


@app.post("/api/financeiro/papeis/{id_}/pago")
def papeis_pago(id_: int) -> dict:
    if not estado.papeis.marcar_pago(id_):
        raise HTTPException(status_code=404, detail="nao achei esse boleto")
    return {"pago": id_}


@app.get("/api/financeiro/fechamento")
def financeiro_fechamento(mes: str = "") -> dict:
    return escritorio.fechamento(estado.base, estado.folha, estado.papeis, mes)


@app.post("/api/financeiro/comprovantes")
async def financeiro_comprovante(lancamento_id: int = Form(...),
                                 arquivo: UploadFile = File(...)) -> dict:
    """
    Guarda o comprovante e o liga ao lancamento.

    O arquivo fica na pasta do programa, com o mes no caminho: procurar o
    comprovante do DAS de setembro daqui a um ano nao pode depender de lembrar
    o nome que o banco deu ao PDF.
    """
    lancamento = estado.financeiro.obter(lancamento_id)
    if not lancamento:
        raise HTTPException(status_code=404, detail="nao achei esse lancamento")

    nome = Path(arquivo.filename or "").name
    if not nome:
        raise HTTPException(status_code=400, detail="arquivo sem nome")

    conteudo = await arquivo.read()
    if len(conteudo) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="arquivo maior que 50 MB")

    quando = lancamento.get("liquidado_em") or lancamento.get("vencimento") or ""
    pasta = COMPROVANTES_DIR / (quando[:7] or escritorio.mes_de_hoje())
    pasta.mkdir(parents=True, exist_ok=True)

    alvo = pasta / nome
    n = 2
    while alvo.exists():
        alvo = pasta / f"{Path(nome).stem} ({n}){Path(nome).suffix}"
        n += 1
    alvo.write_bytes(conteudo)

    import hashlib
    sha = hashlib.sha1(conteudo).hexdigest()
    id_ = estado.financeiro.anexar(lancamento_id, nome, str(alvo), sha)
    return {"id": id_, "nome": nome, "caminho": str(alvo),
            "comprovantes": estado.financeiro.comprovantes(lancamento_id)}


@app.delete("/api/financeiro/comprovantes/{id_}")
def financeiro_tirar_comprovante(id_: int) -> dict:
    """
    Desliga o comprovante do lancamento.

    O arquivo continua na pasta: apagar o papel do disco porque a ligacao
    estava errada seria destruir o comprovante por causa de um erro de
    digitacao.
    """
    if not estado.financeiro.tirar_comprovante(id_):
        raise HTTPException(status_code=404, detail="nao achei esse comprovante")
    return {"tirado": id_}


@app.get("/api/financeiro/exportar")
def financeiro_exportar(mes: str = "") -> FileResponse:
    """O mes inteiro numa planilha, para quem faz a contabilidade."""
    mes = mes or escritorio.mes_de_hoje()
    destino = EXPORTACOES_DIR / f"financeiro-{mes}.xlsx"
    try:
        escritorio.exportar_mes(
            destino, mes,
            extrato=estado.financeiro.extrato(mes),
            folha=estado.folha.do_mes(mes),
            notas=estado.papeis.listar("nota", mes),
            boletos=estado.papeis.listar("boleto"),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"nao consegui exportar: {exc}") from exc
    return FileResponse(
        destino,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=_anexo(destino.name),
    )


# ----------------------------------------------------------- preferencias


@app.get("/api/preferencias")
def preferencias_ler() -> dict:
    dados = estado.prefs.para_tela()
    dados["modelos"] = _modelos_disponiveis()
    dados["modelo_atual"] = estado.client.model
    dados["pasta_acervo"] = str(estado.pasta)
    return dados


@app.post("/api/preferencias")
def preferencias_gravar(payload: dict) -> dict:
    estado.prefs.atualizar(payload)

    # O que a preferencia muda de verdade, agora: modelo e ritmo.
    modelo = estado.prefs.dados.get("modelo")
    if modelo and modelo != estado.client.model:
        # A janela vem junto. Sem esta linha, trocar de modelo devolvia o
        # cliente ao padrao de 8.192 e o programa voltava a ler um quarto do
        # acervo - calado, e so na proxima pergunta.
        estado.client = LlamaClient(
            model=modelo, num_ctx=janela_para(estado.searcher.caracteres())
        )
    estado.devagar = bool(estado.prefs.dados.get("devagar"))

    return preferencias_ler()


def _modelos_disponiveis() -> list[str]:
    try:
        return estado.client.list_models()
    except Exception:
        return []


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
        "padroes": PADROES_SUGERIDOS,
        "tipos": [{"valor": k, "rotulo": v} for k, v in ROTULOS.items()],
        "destino_sugerido": str(Path.home() / "Documentos" / "Acervo PAULUS"),
        "diarios": listar_diarios(DIARIOS_DIR),
    }


@app.get("/api/pastas")
def navegar_pastas(caminho: str = "") -> dict:
    """Um nivel do seletor de pastas. Sem caminho, mostra unidades e atalhos."""
    dados = pastas.listar(caminho)
    dados["migalhas"] = pastas.migalhas(caminho)
    return dados


@app.post("/api/organizar/cancelar")
def organizar_cancelar() -> dict:
    estado.cancelar.set()
    return {"cancelando": True}


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

    # Quanto ja esta em cache define o tempo real da leitura: documento
    # conhecido sai em milissegundos, novo custa ~8 a 25 s.
    conhecidos = _quantos_em_cache([a["path"] for a in estado.encontrados])
    novos = varredura.total - conhecidos

    return {
        "total": varredura.total,
        "em_cache": conhecidos,
        "novos": novos,
        "minutos_min": round(novos * 8 / 60, 1),
        "minutos_max": round(novos * 25 / 60, 1),
        "pastas_visitadas": varredura.pastas_visitadas,
        "sem_permissao": len(varredura.sem_permissao),
        "grandes": len(varredura.ignorados_por_tamanho),
        "arquivos": estado.encontrados[:500],
    }


def _quantos_em_cache(caminhos: list[str]) -> int:
    """Quantos desses documentos ja foram lidos antes (mesmo conteudo)."""
    from classify import CacheClassificacao
    from extract import file_sha1

    cache = CacheClassificacao(CLASSIFICACAO_PATH)
    if not cache.dados:
        return 0

    total = 0
    for caminho in caminhos:
        try:
            if file_sha1(Path(caminho)) in cache.dados:
                total += 1
        except OSError:
            continue
    return total


@app.post("/api/organizar/classificar")
def organizar_classificar() -> StreamingResponse:
    """
    Le o que a varredura achou.

    A leitura em si mora em habilidades/classificar.py. Aqui fica so o que e do
    servidor: guardar o resultado para os passos seguintes do organizador.
    """
    caminhos = [a["path"] for a in estado.encontrados]
    if not caminhos:
        raise HTTPException(status_code=400, detail="nada para ler - faca a varredura antes")

    habilidade = estado.registro.obter("classificar")
    if not habilidade or not habilidade.executavel:
        raise HTTPException(status_code=503, detail="a habilidade de classificar nao carregou")

    estado.cancelar.clear()

    def gerar() -> Iterator[str]:
        try:
            for tipo, dados in habilidade.executar(_contexto(), caminhos=caminhos):
                if tipo == "resultados":
                    # O organizador precisa dos objetos, nao do JSON: os passos
                    # seguintes montam o plano a partir deles.
                    from classify import Classificacao as _C

                    estado.classificacoes = {
                        d["arquivo"]: _C(**{
                            k: v for k, v in d.items()
                            if k in _C.__dataclass_fields__
                        })
                        for d in dados["documentos"]
                    }
                yield _sse(tipo, dados)
        except Exception as exc:
            yield _sse("erro", {"mensagem": str(exc)})

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
    """
    Mover arquivo em lote e acao com efeito no disco do cliente.

    Se a permissao "mover arquivos sem pedir" estiver desligada - e ela vem
    desligada -, isto nao move nada: monta o pedido e devolve para a fila de
    aprovacao. Quem move e o executor, depois do sim.
    """
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

    if not estado.prefs.pode("organizar_mover"):
        pastas_alvo = plano.resumo_por_pasta()
        pedido = estado.fila.pedir(
            f"Mover {plano.total} arquivo(s) para {Path(plano.destino).name or plano.destino}",
            "organizar",
            resumo=(
                f"{plano.total} arquivo(s) em {len(pastas_alvo)} pasta(s), "
                f"no padrao {plano.padrao}. Nada e apagado nem sobrescrito."
            ),
            etiquetas=["da para desfazer"],
            acao="organizar.mover",
            dados=plano.to_dict(),
            reversivel=True,
        )
        return {
            "aguardando_aprovacao": True,
            "pedido": pedido.to_dict(),
            "total": plano.total,
            "pastas": pastas_alvo,
        }

    resultado = aplicar_plano(plano, DIARIOS_DIR)
    estado.classificacoes = {}
    estado.encontrados = []
    estado.recarregar(force=True)
    return {
        "aguardando_aprovacao": False,
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



# -------------------------------------------------- certificado e assinatura


class SenhaCertificado(BaseModel):
    senha: str = ""
    guardar: bool = False


class AjusteCofre(BaseModel):
    minutos: int | None = None
    pedir_confirmacao: bool | None = None
    mostrar_documento: bool | None = None
    lote_sem_confirmar: bool | None = None


class DesenhoSelo(BaseModel):
    campo: str = "desenho"          # "desenho" ou "imagem"
    dados: str = ""                 # PNG em data URL, vindo do canvas


class PedidoAssinatura(BaseModel):
    arquivo: str
    paginas: str = "ultima"
    intervalo: str = ""
    posicao: str = "rodape_direita"
    x: float | None = None
    y: float | None = None
    senha_pdf: str = ""
    motivo: str = ""
    guardar_biblioteca: bool = True
    manter_original: bool = True
    senha_certificado: str = ""


@app.get("/api/certificado")
def certificado_ler() -> dict:
    dados = estado.cofre.para_tela()
    dados["registro"] = estado.assinaturas.para_tela(10)
    dados["pode_assinar_sozinho"] = estado.prefs.pode("assinar")
    return dados


@app.get("/api/certificado/windows")
def certificado_windows() -> dict:
    """
    Os certificados que ja estao no Windows.

    Listar sem oferecer assinatura direta e proposital: a chave de um e-CPF
    instalado costuma vir marcada como nao exportavel, e assinar por ela
    exigiria falar com a CryptoAPI. A tela mostra o que existe e explica que
    aqui se usa o arquivo .pfx.
    """
    return {"certificados": certificado.listar_windows()}


@app.post("/api/certificado/arquivo")
async def certificado_arquivo(arquivo: UploadFile) -> dict:
    nome = arquivo.filename or "certificado.pfx"
    if Path(nome).suffix.lower() not in (".pfx", ".p12"):
        raise HTTPException(status_code=400, detail="o certificado A1 e um arquivo .pfx ou .p12")

    conteudo = await arquivo.read()
    if len(conteudo) > MAX_CERTIFICADO_BYTES:
        raise HTTPException(status_code=400, detail="arquivo grande demais para um certificado")

    estado.cofre.guardar_arquivo(nome, conteudo)
    estado.cofre.esquecer_senha()
    return estado.cofre.para_tela()


@app.post("/api/certificado/senha")
def certificado_senha(payload: SenhaCertificado) -> dict:
    """
    Confere a senha e, se a pessoa pediu, guarda protegida pela conta Windows.

    A senha so vira memoria depois de abrir o certificado de verdade: guardar
    uma senha errada faria o programa falhar mais tarde, longe daqui.
    """
    alvo = estado.cofre.arquivo
    if not alvo or not alvo.exists():
        raise HTTPException(status_code=400, detail="nenhum certificado instalado")

    lido = certificado.ler(alvo, payload.senha)
    if lido.erro:
        raise HTTPException(status_code=400, detail=lido.erro)

    estado.cofre.lembrar(payload.senha)
    if payload.guardar and not estado.cofre.proteger(payload.senha):
        return {
            **estado.cofre.para_tela(),
            "aviso": "não consegui guardar a senha nesta máquina - vou perguntar a cada assinatura",
        }
    return estado.cofre.para_tela()


@app.post("/api/certificado/esquecer")
def certificado_esquecer() -> dict:
    """Apaga a senha guardada, mas mantem o certificado instalado."""
    estado.cofre.dados["senha_protegida"] = ""
    estado.cofre.dados["guardar_senha"] = False
    estado.cofre.esquecer_senha()
    estado.cofre.salvar()
    return estado.cofre.para_tela()


@app.delete("/api/certificado")
def certificado_remover() -> dict:
    estado.cofre.remover()
    return estado.cofre.para_tela()


@app.post("/api/certificado/opcoes")
def certificado_opcoes(payload: AjusteCofre) -> dict:
    for campo, valor in payload.model_dump(exclude_none=True).items():
        if campo == "minutos":
            valor = max(0, min(int(valor), 240))
        estado.cofre.dados[campo] = valor
    estado.cofre.salvar()
    return estado.cofre.para_tela()


@app.post("/api/certificado/selo")
def certificado_selo(payload: dict) -> dict:
    return {"selo": estado.cofre.gravar_selo(payload)}


@app.post("/api/certificado/selo/imagem")
def certificado_selo_imagem(payload: DesenhoSelo) -> dict:
    """Recebe o PNG do desenho ou do logotipo, vindo como data URL."""
    import base64

    cabeca, _, corpo = payload.dados.partition(",")
    if "image/png" not in cabeca or not corpo:
        raise HTTPException(status_code=400, detail="esperava uma imagem PNG")
    try:
        conteudo = base64.b64decode(corpo)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="não consegui ler a imagem") from exc
    if len(conteudo) > 4 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="imagem grande demais")

    try:
        nome = estado.cofre.guardar_imagem(payload.campo, conteudo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"selo": estado.cofre.dados["selo"], "arquivo": nome}


@app.delete("/api/certificado/selo/{campo}")
def certificado_selo_limpar(campo: str) -> dict:
    if campo not in ("desenho", "imagem"):
        raise HTTPException(status_code=400, detail="campo desconhecido")
    alvo = estado.cofre.caminho_do_selo(campo)
    if alvo:
        try:
            alvo.unlink()
        except OSError:
            pass
    return {"selo": estado.cofre.gravar_selo({campo: ""})}


@app.get("/api/certificado/selo/{campo}.png")
def certificado_selo_png(campo: str) -> FileResponse:
    alvo = estado.cofre.caminho_do_selo(campo) if campo in ("desenho", "imagem") else None
    if not alvo:
        raise HTTPException(status_code=404, detail="não há imagem gravada")
    return FileResponse(alvo, media_type="image/png")


@app.post("/api/certificado/teste")
def certificado_teste() -> dict:
    """
    Cria um certificado autoassinado para experimentar a assinatura.

    Existe para dar para conhecer a tela sem um e-CPF na mao. O que sai daqui
    assina de verdade do ponto de vista criptografico e NAO tem validade
    juridica - a tela repete isso em cada passo, e o registro grava assim.
    """
    if estado.cofre.arquivo and estado.cofre.arquivo.exists():
        raise HTTPException(
            status_code=400,
            detail="já existe um certificado instalado - remova antes de criar um de teste",
        )
    senha = "paulus"
    alvo = certificado.gerar_de_teste(CERTIFICADO_DIR / "certificado.pfx", senha, "CERTIFICADO DE TESTE")
    estado.cofre.dados["arquivo"] = str(alvo)
    estado.cofre.salvar()
    estado.cofre.lembrar(senha)
    return {**estado.cofre.para_tela(), "senha_do_teste": senha}


# ------------------------------------------------------------- assinar PDF


@app.get("/api/assinar/documento")
def assinar_documento(arquivo: str) -> dict:
    """Quantas paginas o PDF tem, e se ja vem assinado."""
    doc = assinatura.ler(arquivo)
    if doc.erro:
        raise HTTPException(status_code=400, detail=doc.erro)

    cofre = estado.cofre.para_tela()
    return {
        "documento": doc.to_dict(),
        "certificado": cofre["certificado"],
        "instalado": cofre["instalado"],
        "selo": cofre["selo"],
        "posicoes": cofre["posicoes"],
        "escolhas": [{"valor": k, "rotulo": v} for k, v in assinatura.ESCOLHAS_PAGINA.items()],
        "pede_confirmacao": cofre["pedir_confirmacao"],
        "precisa_senha": not bool(estado.cofre.senha_agora()),
    }


@app.get("/api/assinar/pagina")
def assinar_pagina(arquivo: str, numero: int = 1, largura: int = 1000):
    """A pagina desenhada como PNG, para a tela mostrar o documento."""
    from fastapi.responses import Response

    try:
        png = assinatura.pagina_png(arquivo, numero, largura)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"não consegui desenhar a página: {exc}") from exc
    return Response(png, media_type="image/png", headers={"Cache-Control": "no-cache"})


@app.get("/api/assinar/pdfs")
def assinar_pdfs() -> dict:
    """Os PDFs que o programa ja conhece, para escolher sem procurar no disco."""
    achados = []
    for doc in estado.searcher.documents:
        caminho = Path(doc.path)
        if caminho.suffix.lower() != ".pdf" or not caminho.exists():
            continue
        achados.append({
            "path": str(caminho),
            "nome": caminho.name,
            "mb": round(caminho.stat().st_size / (1024 * 1024), 2),
            "paginas": doc.pages,
        })
    return {"pdfs": sorted(achados, key=lambda a: a["nome"].lower())}


@app.post("/api/assinar")
def assinar_agora(payload: PedidoAssinatura) -> dict:
    """
    Assina, ou poe o pedido na fila.

    Assinatura tem efeito juridico, entao segue a mesma regra do resto: sem a
    permissao "assinar sem revisar" ligada - e ela vem desligada -, isto nao
    assina nada, monta o pedido e devolve para a fila de aprovacao.
    """
    doc = assinatura.ler(payload.arquivo)
    if doc.erro:
        raise HTTPException(status_code=400, detail=doc.erro)

    alvo_pfx = estado.cofre.arquivo
    if not alvo_pfx or not alvo_pfx.exists():
        raise HTTPException(status_code=400, detail="nenhum certificado instalado")

    senha = payload.senha_certificado or estado.cofre.senha_agora()
    if not senha:
        raise HTTPException(status_code=400, detail="preciso da senha do certificado")

    cert = certificado.ler(alvo_pfx, senha)
    if cert.erro:
        raise HTTPException(status_code=400, detail=cert.erro)
    if payload.senha_certificado:
        estado.cofre.lembrar(payload.senha_certificado)

    alvos = assinatura.paginas_alvo(payload.paginas, doc.paginas, payload.intervalo)
    if not alvos:
        raise HTTPException(status_code=400, detail="nenhuma página escolhida")

    dados = {
        **payload.model_dump(exclude={"senha_certificado"}),
        "paginas_alvo": alvos,
        "titular": cert.titular,
        "icp_brasil": cert.icp_brasil,
    }

    if not estado.prefs.pode("assinar"):
        etiquetas = ["não dá para desfazer"]
        if not cert.icp_brasil:
            etiquetas.append("certificado fora da ICP-Brasil")
        pedido = estado.fila.pedir(
            f"Assinar {Path(payload.arquivo).name}",
            "assinatura",
            resumo=assinatura.resumo_em_portugues(cert, doc, alvos, payload.senha_pdf),
            etiquetas=etiquetas,
            acao="assinatura.assinar",
            dados=dados,
            reversivel=False,
        )
        return {"aguardando_aprovacao": True, "pedido": pedido.to_dict()}

    resultado = _assinar_de_fato(dados, senha)
    if resultado.erro:
        raise HTTPException(status_code=400, detail=resultado.erro)
    return {"aguardando_aprovacao": False, **resultado.to_dict()}


def _assinar_de_fato(dados: dict, senha: str) -> "assinatura.Resultado":
    """O trabalho em si, chamado direto ou depois do sim na fila."""
    origem = Path(dados["arquivo"])
    destino = _nome_do_assinado(origem, dados.get("guardar_biblioteca", True))

    ponto = None
    if dados.get("x") is not None and dados.get("y") is not None:
        ponto = (float(dados["x"]), float(dados["y"]))

    resultado = assinatura.assinar(
        origem,
        destino,
        arquivo_pfx=str(estado.cofre.arquivo),
        senha=senha,
        selo=estado.cofre.dados.get("selo") or {},
        escolha_paginas=dados.get("paginas", "ultima"),
        intervalo=dados.get("intervalo", ""),
        posicao=dados.get("posicao", "rodape_direita"),
        ponto=ponto,
        senha_pdf=dados.get("senha_pdf", ""),
        motivo=dados.get("motivo", ""),
        imagem=estado.cofre.caminho_do_selo("desenho") or estado.cofre.caminho_do_selo("imagem"),
    )
    if resultado.erro:
        return resultado

    estado.assinaturas.anotar(resultado, origem)

    if not dados.get("manter_original", True):
        try:
            origem.unlink()
        except OSError:
            pass

    if dados.get("guardar_biblioteca", True):
        estado.recarregar(force=True)

    return resultado


def _nome_do_assinado(origem: Path, na_biblioteca: bool) -> Path:
    """
    Onde o assinado e gravado, sem nunca passar por cima do original.

    Sobrescrever o documento de origem com a versao assinada seria perder o
    original de um jeito que nao se desfaz.
    """
    pasta = estado.pasta if na_biblioteca else origem.parent
    base = f"{origem.stem} - assinado"
    destino = pasta / f"{base}.pdf"
    conta = 2
    while destino.exists():
        destino = pasta / f"{base} ({conta}).pdf"
        conta += 1
    return destino


@app.get("/api/assinar/baixar")
def assinar_baixar(arquivo: str) -> FileResponse:
    """Entrega o PDF assinado para o navegador salvar."""
    alvo = Path(arquivo)
    if not alvo.exists() or alvo.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="arquivo não encontrado")
    return FileResponse(alvo, media_type="application/pdf", filename=alvo.name)


@app.get("/api/assinaturas")
def assinaturas_registro(codigo: str = "") -> dict:
    if codigo:
        achado = estado.assinaturas.procurar(codigo)
        if not achado:
            raise HTTPException(status_code=404, detail="não achei esse código no registro")
        return {"assinatura": achado}
    return estado.assinaturas.para_tela()


@app.get("/api/assinaturas/conferir")
def assinaturas_conferir(arquivo: str, senha: str = "") -> dict:
    """
    O que as assinaturas de um PDF dizem, lidas do proprio arquivo.

    Offline nao da para checar revogacao nem a cadeia ate a raiz da ICP-Brasil.
    O que da para afirmar - o documento foi mexido depois de assinado, ou nao -
    e o que vale a pena responder, e e o que vai aqui.
    """
    return {
        "assinaturas": assinatura.verificar(arquivo, senha),
        "conferencia_limitada": True,
    }

# ----------------------------------------------------------------- e-mail


class EnderecoEmail(BaseModel):
    email: str = ""


class FichaConta(BaseModel):
    dados: dict = {}
    senha: str = ""


class SenhaConta(BaseModel):
    id: str = ""
    senha: str = ""


class PedidoEnvio(BaseModel):
    conta_id: str = ""
    para: str = ""
    cc: str = ""
    cco: str = ""
    assunto: str = ""
    corpo: str = ""
    anexos: list[str] = []          # caminhos de arquivos da biblioteca
    responder_a: str = ""           # Message-ID, quando e resposta
    senha: str = ""


def _conta_e_senha(id_: str = "") -> tuple:
    """A conta pedida (ou a em uso) com a senha disponivel."""
    conta = estado.contas.obter(id_) if id_ else estado.contas.em_uso
    if not conta:
        raise HTTPException(status_code=400, detail="nenhuma conta de e-mail conectada")
    senha = estado.contas.senha(conta)
    if not senha:
        raise HTTPException(status_code=401, detail=f"preciso da senha de {conta.email}")
    return conta, senha


def _emails_dos_cadastros() -> dict:
    """{e-mail: nome} das fichas, para marcar quem e cliente na caixa."""
    achados = {}
    for ficha in estado.cadastros.listar():
        alvo = (ficha.get("email") or "").strip().lower()
        if alvo:
            achados[alvo] = ficha.get("nome", "")
    return achados


@app.get("/api/email/contas")
def email_contas() -> dict:
    dados = estado.contas.para_tela()
    dados["registro"] = estado.envios.para_tela(10)
    dados["pode_enviar_sozinho"] = estado.prefs.pode("enviar_mensagem")
    return dados


@app.post("/api/email/detectar")
def email_detectar(payload: EnderecoEmail) -> dict:
    """Acha os servidores do endereco, pela tabela ou sondando o dominio."""
    return correio_contas.detectar(payload.email)


@app.post("/api/email/testar")
def email_testar(payload: FichaConta) -> dict:
    """
    Prova a conta antes de guardar.

    Testa entrada e saida separadamente: da para ler e da para enviar sao
    coisas diferentes, e guardar uma conta que so le - sem dizer - seria
    descobrir o problema na hora de mandar o e-mail que importava.
    """
    campos = {k: v for k, v in payload.dados.items()
              if k in correio_contas.Conta.__dataclass_fields__}
    campos.pop("senha_protegida", None)
    conta = correio_contas.Conta(**{"id": "teste", **campos})

    senha = payload.senha
    if not senha and payload.dados.get("id"):
        guardada = estado.contas.obter(str(payload.dados["id"]))
        senha = estado.contas.senha(guardada) if guardada else ""
    if not senha:
        raise HTTPException(status_code=400, detail="informe a senha para testar")

    return correio.testar(conta, senha)


@app.post("/api/email/contas")
def email_salvar_conta(payload: FichaConta) -> dict:
    try:
        conta = estado.contas.salvar_conta(payload.dados, payload.senha)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if payload.senha:
        estado.contas.lembrar(conta.id, payload.senha)
    return estado.contas.para_tela()


@app.post("/api/email/contas/senha")
def email_senha_conta(payload: SenhaConta) -> dict:
    """Confere a senha contra o servidor antes de aceitar como boa."""
    conta = estado.contas.obter(payload.id)
    if not conta:
        raise HTTPException(status_code=404, detail="conta não encontrada")

    prova = correio.testar(conta, payload.senha)
    if not prova["entrada"]:
        estado.contas.marcar_erro(conta, prova["erro_entrada"])
        raise HTTPException(status_code=400, detail=prova["erro_entrada"] or "o servidor recusou a senha")

    estado.contas.lembrar(conta.id, payload.senha)
    if conta.guardar_senha:
        estado.contas.salvar_conta({"id": conta.id, "email": conta.email}, payload.senha)
    estado.contas.marcar_ok(conta)
    return estado.contas.para_tela()


@app.post("/api/email/contas/{id_}/usar")
def email_usar_conta(id_: str) -> dict:
    if not estado.contas.usar(id_):
        raise HTTPException(status_code=404, detail="conta não encontrada")
    return estado.contas.para_tela()


@app.delete("/api/email/contas/{id_}")
def email_apagar_conta(id_: str) -> dict:
    if not estado.contas.apagar(id_):
        raise HTTPException(status_code=404, detail="conta não encontrada")
    return estado.contas.para_tela()


@app.post("/api/email/esquecer-senhas")
def email_esquecer_senhas() -> dict:
    quantas = estado.contas.esquecer_senhas()
    return {**estado.contas.para_tela(), "apagadas": quantas}


# --------------------------------------------------------- caixa de entrada


@app.get("/api/email/caixa")
def email_caixa(conta_id: str = "", filtro: str = "tudo", busca: str = "",
                limite: int = 25, antes_de: str = "") -> dict:
    """
    Os cabecalhos das mensagens - nao as mensagens.

    O corpo fica no servidor ate alguem abrir. E a promessa do rodape da tela,
    e tambem o que faz uma caixa com milhares de mensagens abrir em segundos.
    """
    conta, senha = _conta_e_senha(conta_id)
    try:
        dados = correio.listar(
            conta, senha, filtro=filtro, busca=busca,
            limite=min(max(int(limite), 1), 60), antes_de=antes_de,
            clientes=_emails_dos_cadastros(),
        )
    except correio.ErroCorreio as exc:
        estado.contas.marcar_erro(conta, str(exc))
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    estado.contas.marcar_ok(conta)
    dados["conta"] = conta.to_dict(em_uso=True)
    dados["filtros"] = [{"valor": k, "rotulo": v} for k, v in correio.FILTROS.items()]
    return dados


@app.get("/api/email/mensagem")
def email_mensagem(uid: str, conta_id: str = "") -> dict:
    conta, senha = _conta_e_senha(conta_id)
    try:
        msg = correio.abrir(conta, senha, uid)
    except correio.ErroCorreio as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    dados = msg.to_dict()
    dados["pode_rascunhar"] = conta.pode_rascunhar
    return dados


@app.get("/api/email/anexo")
def email_anexo(uid: str, nome: str, conta_id: str = ""):
    """Entrega o anexo ao navegador, sem gravar nada no disco."""
    from fastapi.responses import Response

    conta, senha = _conta_e_senha(conta_id)
    try:
        achado, dados = correio.baixar_anexo(conta, senha, uid, nome)
    except correio.ErroCorreio as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    import mimetypes

    tipo, _ = mimetypes.guess_type(achado)
    return Response(dados, media_type=tipo or "application/octet-stream")


@app.post("/api/email/anexo/guardar")
def email_guardar_anexo(payload: dict) -> dict:
    """Traz o anexo para a biblioteca, sem passar por cima de nada."""
    conta, senha = _conta_e_senha(str(payload.get("conta_id", "")))
    uid = str(payload.get("uid", ""))
    nome = str(payload.get("nome", ""))

    try:
        achado, dados = correio.baixar_anexo(conta, senha, uid, nome)
    except correio.ErroCorreio as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    limpo = Path(achado).name
    if Path(limpo).suffix.lower() not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"não sei ler {Path(limpo).suffix or 'esse tipo'} - guardo PDF, DOCX, TXT e MD",
        )

    estado.pasta.mkdir(parents=True, exist_ok=True)
    destino = estado.pasta / limpo
    conta_repetida = 2
    while destino.exists():
        destino = estado.pasta / f"{Path(limpo).stem} ({conta_repetida}){Path(limpo).suffix}"
        conta_repetida += 1

    destino.write_bytes(dados)
    return {"guardado": destino.name, "documentos": estado.recarregar(force=True)}


@app.post("/api/email/arquivar")
def email_arquivar(payload: dict) -> dict:
    conta, senha = _conta_e_senha(str(payload.get("conta_id", "")))
    uid = str(payload.get("uid", ""))
    try:
        movida = correio.arquivar(conta, senha, uid)
    except correio.ErroCorreio as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "arquivada": movida,
        "aviso": "" if movida else "seu servidor não tem pasta de arquivo - marquei só como lida",
    }


@app.post("/api/email/rascunho")
def email_rascunho(payload: dict) -> dict:
    """
    Escreve um rascunho de resposta, quando alguem pede.

    Sob demanda de proposito: rodar o modelo em cada mensagem que chega custaria
    perto de um minuto por e-mail nesta maquina, e a caixa de entrada demoraria
    uma hora para abrir.
    """
    conta, senha = _conta_e_senha(str(payload.get("conta_id", "")))
    if not conta.pode_rascunhar:
        raise HTTPException(status_code=403, detail="esta conta não permite que eu escreva rascunhos")

    disponivel, motivo = check_ollama(estado.client.model)
    if not disponivel:
        raise HTTPException(status_code=503, detail=motivo)

    try:
        msg = correio.abrir(conta, senha, str(payload.get("uid", "")), marcar_lido=False)
    except correio.ErroCorreio as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    quem = estado.prefs.dados.get("pessoa", {}).get("nome", "") or conta.nome
    try:
        texto = correio.sugerir_resposta(estado.client, msg, quem)
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "rascunho": texto,
        "para": [msg.de_email],
        "assunto": msg.assunto if msg.assunto.lower().startswith("re:") else f"Re: {msg.assunto}",
        "responder_a": "",
        "sobre": msg.assunto,
    }


# ---------------------------------------------------------------- enviar


def _montar_do_pedido(payload: PedidoEnvio):
    conta = estado.contas.obter(payload.conta_id) if payload.conta_id else estado.contas.em_uso
    if not conta:
        raise HTTPException(status_code=400, detail="nenhuma conta de e-mail conectada")

    para = correio.enderecos(payload.para)
    if not para:
        raise HTTPException(status_code=400, detail="informe pelo menos um destinatário")

    anexos = [Path(a) for a in payload.anexos]
    if anexos and not conta.pode_anexar:
        raise HTTPException(status_code=403, detail="esta conta não permite que eu anexe arquivos")
    for alvo in anexos:
        if not alvo.exists():
            raise HTTPException(status_code=400, detail=f"não achei o anexo {alvo.name}")

    try:
        msg = correio.montar_email(
            conta,
            para=para,
            assunto=payload.assunto,
            corpo=payload.corpo,
            cc=correio.enderecos(payload.cc),
            anexos=anexos,
            responder_a=payload.responder_a,
        )
    except correio.ErroCorreio as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return conta, msg, para


@app.post("/api/email/previa")
def email_previa(payload: PedidoEnvio) -> dict:
    """
    Como a mensagem vai chegar - sem nada ter saido.

    Montar e enviar sao passos separados justamente para isto existir.
    """
    conta, msg, para = _montar_do_pedido(payload)
    corpo = msg.get_body(preferencelist=("plain",))
    return {
        "de": str(msg.get("From", "")),
        "para": para,
        "cc": correio.enderecos(payload.cc),
        "cco": correio.enderecos(payload.cco),
        "assunto": str(msg.get("Subject", "")) or "(sem assunto)",
        "corpo": corpo.get_content().rstrip() if corpo else "",
        "anexos": [
            {"nome": p.get_filename(), "kb": round(len(p.get_payload(decode=True) or b"") / 1024, 1)}
            for p in msg.iter_attachments()
        ],
        "resumo": correio.resumo_do_envio(
            conta, para, [p.get_filename() for p in msg.iter_attachments()],
            not conta.pode_enviar_sem_confirmar,
        ),
    }


@app.post("/api/email/enviar")
def email_enviar(payload: PedidoEnvio) -> dict:
    """
    Envia, ou poe o pedido na fila.

    E-mail que sai nao volta. Sem a permissao "enviar sem confirmar" - que vem
    desligada, no programa e na conta -, isto nao manda nada: monta o pedido e
    devolve para a fila de aprovacao.
    """
    conta, msg, para = _montar_do_pedido(payload)

    if payload.senha:
        estado.contas.lembrar(conta.id, payload.senha)
    if not estado.contas.senha(conta):
        raise HTTPException(status_code=401, detail=f"preciso da senha de {conta.email}")

    anexos = [Path(a).name for a in payload.anexos]
    livre = estado.prefs.pode("enviar_mensagem") and conta.pode_enviar_sem_confirmar

    if not livre:
        pedido = estado.fila.pedir(
            f"Enviar e-mail para {', '.join(para[:2])}" + ("…" if len(para) > 2 else ""),
            "email",
            resumo=correio.resumo_do_envio(conta, para, anexos, False),
            etiquetas=["não dá para desfazer"] + (["com anexo"] if anexos else []),
            acao="correio.enviar",
            dados=payload.model_dump(exclude={"senha"}),
            reversivel=False,
        )
        return {"aguardando_aprovacao": True, "pedido": pedido.to_dict()}

    resultado = _enviar_de_fato(payload.model_dump(exclude={"senha"}))
    return {"aguardando_aprovacao": False, **resultado}


def _enviar_de_fato(dados: dict) -> dict:
    """O envio em si, chamado direto ou depois do sim na fila."""
    payload = PedidoEnvio(**{k: v for k, v in dados.items() if k in PedidoEnvio.model_fields})
    conta, msg, _ = _montar_do_pedido(payload)

    senha = estado.contas.senha(conta)
    if not senha:
        raise RuntimeError(f"a senha de {conta.email} não está mais disponível - entre na conta de novo")

    try:
        resultado = correio.enviar(conta, senha, msg, correio.enderecos(payload.cco))
    except correio.ErroCorreio as exc:
        raise RuntimeError(str(exc)) from exc

    estado.contas.marcar_ok(conta)
    return estado.envios.anotar(conta.email, resultado)


@app.get("/api/email/envios")
def email_envios() -> dict:
    return estado.envios.para_tela()


@app.get("/api/email/anexaveis")
def email_anexaveis() -> dict:
    """Arquivos da biblioteca que dao para anexar."""
    achados = []
    for doc in estado.searcher.documents:
        caminho = Path(doc.path)
        if not caminho.exists():
            continue
        achados.append({
            "path": str(caminho),
            "nome": caminho.name,
            "mb": round(caminho.stat().st_size / (1024 * 1024), 2),
        })
    return {"arquivos": sorted(achados, key=lambda a: a["nome"].lower())}

# ------------------------------------------------- documentos e planilha


class NovoDocumento(BaseModel):
    titulo: str = ""
    tipo: str = "texto"
    corpo: str = ""
    cadastro_id: int | None = None


class GravarDocumento(BaseModel):
    corpo: str = ""
    titulo: str = ""
    nota: str = ""


class PedidoAoAssistente(BaseModel):
    pedido: str = ""
    trecho: str = ""            # o que estava selecionado, quando havia
    selecao: str = ""           # celulas, na planilha


class CelulaPlanilha(BaseModel):
    aba: int = 0
    ref: str = ""
    dados: dict = {}


def _documento_ou_404(id_: int) -> dict:
    item = estado.documentos.obter(id_)
    if not item:
        raise HTTPException(status_code=404, detail="documento não encontrado")
    return item


@app.get("/api/documentos")
def documentos_listar(tipo: str = "") -> dict:
    return {
        "documentos": estado.documentos.listar(tipo),
        "contagem": estado.documentos.contagem(),
        "clientes": [{"id": f["id"], "nome": f["nome"]} for f in estado.cadastros.listar()],
    }


@app.post("/api/documentos")
def documentos_criar(payload: NovoDocumento) -> dict:
    corpo = payload.corpo
    if not corpo and payload.tipo == "planilha":
        corpo = planilha.para_json([planilha.Aba()])
    id_ = estado.documentos.criar(payload.titulo, payload.tipo, corpo, payload.cadastro_id)
    return estado.documentos.obter(id_) or {}


class ImportarParaEditar(BaseModel):
    caminho: str = ""
    nome: str = ""


@app.post("/api/documentos/importar")
def documentos_importar(payload: ImportarParaEditar) -> dict:
    """
    Traz um documento da biblioteca para o editor, como rascunho.

    O arquivo original NAO e tocado. O que nasce aqui e uma copia editavel: a
    pessoa pediu para abrir para editar, e editar o .docx de origem no lugar
    seria mexer no documento que ja foi assinado, enviado ou protocolado.
    """
    alvo = Path(payload.caminho) if payload.caminho else None
    if not alvo or not alvo.exists():
        doc = next((d for d in estado.searcher.documents if d.name == payload.nome), None)
        if not doc:
            raise HTTPException(status_code=404, detail="nao achei esse documento")
        alvo = Path(doc.path)
    if not alvo.exists():
        raise HTTPException(status_code=404, detail="o arquivo saiu do lugar")

    lido = next((d for d in estado.searcher.documents if d.path == str(alvo)), None)
    if lido is None:
        raise HTTPException(status_code=400, detail="esse arquivo ainda nao foi lido")

    # Paragrafo por paragrafo: o texto extraido vem com quebras de linha, e
    # jogar tudo num <p> so daria um bloco unico impossivel de editar.
    paragrafos = [p.strip() for p in lido.text.splitlines() if p.strip()]
    corpo = "".join(f"<p>{_escapar(p)}</p>" for p in paragrafos) or "<p><br></p>"

    id_ = estado.documentos.criar(Path(lido.name).stem, "texto", corpo, None)
    return {"id": id_, "titulo": Path(lido.name).stem, "de": lido.name,
            "paragrafos": len(paragrafos)}


def _escapar(texto: str) -> str:
    return (texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# A rota fixa vem ANTES da rota com parametro: o FastAPI casa na ordem de
# declaracao, e /api/documentos/{id_} engoliria /api/documentos/modelos.
@app.get("/api/documentos/modelos")
def documentos_modelos() -> dict:
    """
    As clausulas do escritorio e os codigos de lei disponiveis.

    Os codigos ficaram de fora ate a Etapa 11 porque o programa nao tinha o
    texto das leis, e pedir o artigo ao modelo produziria numero plausivel e
    errado dentro de um contrato. Com o texto oficial no disco, citar passa a
    ser consulta - e quando um codigo nao esta instalado, a tela diz isso em
    vez de chutar.
    """
    instalados = estado.leis.instalados()
    return {
        "clausulas": estado.clausulas.listar(),
        "codigos": instalados,
        "tem_codigo": any(c["instalado"] for c in instalados),
        "sem_codigo": {
            "titulo": "Nenhum código instalado",
            "porque": (
                "Sem o texto oficial no disco eu não cito artigo: o número sairia de um "
                "modelo pequeno, plausível e possivelmente errado dentro de um contrato."
            ),
            "onde": "Configurações · Códigos de lei",
        },
    }


@app.post("/api/documentos/modelos")
def documentos_gravar_modelo(payload: dict) -> dict:
    try:
        estado.clausulas.gravar(
            str(payload.get("titulo", "")), str(payload.get("texto", "")),
            str(payload.get("id", "")),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"clausulas": estado.clausulas.listar()}


@app.delete("/api/documentos/modelos/{id_}")
def documentos_apagar_modelo(id_: str) -> dict:
    estado.clausulas.apagar(id_)
    return {"clausulas": estado.clausulas.listar()}


@app.get("/api/documentos/{id_}")
def documentos_obter(id_: int) -> dict:
    item = _documento_ou_404(id_)
    if item["tipo"] == "texto":
        blocos = documento.ler_html(item["corpo"])
        item["contagem"] = documento.contar(blocos)
        # Pagina medida, nao estimada: a conta antiga era palavras/450, e
        # errava em todo documento com titulo, lista ou paragrafo curto.
        item["paginacao"] = documento.mapa_de_paginas(
            blocos, timbre=_timbre_do_escritorio() or None, formato=item.get("formato"))
        item["formato"] = documento.normalizar_formato(item.get("formato"))
    return item


@app.post("/api/documentos/{id_}")
def documentos_gravar(id_: int, payload: GravarDocumento) -> dict:
    try:
        resultado = estado.documentos.salvar(id_, payload.corpo, payload.titulo, payload.nota)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if payload.corpo and not payload.corpo.lstrip().startswith("{"):
        resultado["contagem"] = documento.contar(documento.ler_html(payload.corpo))
    return resultado


@app.delete("/api/documentos/{id_}")
def documentos_apagar(id_: int) -> dict:
    if not estado.documentos.apagar(id_):
        raise HTTPException(status_code=404, detail="documento não encontrado")
    return {"apagado": id_}


@app.get("/api/documentos/{id_}/versoes")
def documentos_versoes(id_: int) -> dict:
    _documento_ou_404(id_)
    return {"versoes": estado.documentos.versoes(id_)}


@app.get("/api/documentos/{id_}/comparar")
def documentos_comparar(id_: int, de: int = 0, ate: int = 0) -> dict:
    """
    O que mudou entre duas versoes.

    Compara o texto, nao o HTML: o editor troca <b> por <strong> sozinho, e
    listar isso como alteracao de contrato faria a comparacao perder utilidade
    justamente no dia em que ela importa.
    """
    _documento_ou_404(id_)
    ultima = estado.documentos.ultima_versao(id_)
    ate = ate or ultima
    de = de or max(1, ate - 1)

    antes = estado.documentos.corpo_da_versao(id_, de)
    depois = estado.documentos.corpo_da_versao(id_, ate)
    if antes is None or depois is None:
        raise HTTPException(status_code=404, detail="essa versão não existe")

    return {"de": de, "ate": ate, "mudancas": documento.comparar(antes, depois)}


@app.post("/api/documentos/{id_}/restaurar")
def documentos_restaurar(id_: int, payload: dict) -> dict:
    _documento_ou_404(id_)
    try:
        resultado = estado.documentos.restaurar(id_, int(payload.get("numero", 0)))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {**resultado, "documento": estado.documentos.obter(id_)}


# ------------------------------------------------ sair: PDF, DOCX, avisos


def _timbre_do_escritorio() -> dict:
    """
    O timbre sai dos dados profissionais, e so quando o escritorio quer.

    Fica desligado por padrao: por um lado, o dado pode nao estar preenchido;
    por outro, nem todo documento sai em papel timbrado - uma minuta interna
    com timbre parece peca protocolada.
    """
    prefs = estado.prefs.dados
    if not prefs.get("timbre_no_pdf"):
        return {}
    pessoa = prefs.get("pessoa", {})
    # Sem nome nao ha timbre: o resto sozinho sairia como um endereco solto no
    # alto da folha. Quem ligou a chave precisa saber disso na tela de
    # Configuracoes, e nao ao abrir o PDF e nao ver nada.
    if not str(pessoa.get("nome", "")).strip():
        return {}
    return {
        "nome": pessoa.get("nome", ""),
        "oab": pessoa.get("oab", ""),
        "cpf": pessoa.get("cpf", ""),
        "endereco": pessoa.get("endereco", ""),
        "telefone": pessoa.get("telefone", ""),
        "email": pessoa.get("email", ""),
    }


def _pdf_do_documento(item: dict, timbre: dict | None = None) -> bytes:
    blocos = documento.ler_html(item["corpo"])
    rodape = item["titulo"]
    if timbre is None:
        timbre = _timbre_do_escritorio()
    return documento.para_pdf(blocos, item["titulo"], rodape, timbre=timbre or None,
                              formato=item.get("formato"))


@app.get("/api/documentos/{id_}/pdf")
def documentos_pdf(id_: int):
    from fastapi.responses import Response

    item = _documento_ou_404(id_)
    if item["tipo"] != "texto":
        raise HTTPException(status_code=400, detail="isso é uma planilha - baixe em XLSX ou CSV")
    return Response(
        _pdf_do_documento(item), media_type="application/pdf",
        headers=_anexo(_arquivo(item["titulo"]) + ".pdf"),
    )


@app.get("/api/documentos/{id_}/docx")
def documentos_docx(id_: int):
    from fastapi.responses import Response

    item = _documento_ou_404(id_)
    if item["tipo"] != "texto":
        raise HTTPException(status_code=400, detail="isso é uma planilha - baixe em XLSX ou CSV")

    dados = documento.para_docx(documento.ler_html(item["corpo"]), item["titulo"],
                                formato=item.get("formato"))
    return Response(
        dados,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=_anexo(_arquivo(item["titulo"]) + ".docx"),
    )


@app.get("/api/documentos/{id_}/pagina")
def documentos_pagina(id_: int, numero: int = 1, largura: int = 900, versao: int = 0):
    """
    A pagina desenhada, para a pre-visualizacao.

    E o PDF de verdade rasterizado, nao uma aproximacao em CSS: o que a tela
    mostra e o arquivo que vai sair.

    Com `versao`, desenha uma versao antiga - e o que permite ver as duas lado
    a lado na comparacao. Listar o que mudou em texto nao mostra como ficou.
    """
    from fastapi.responses import Response

    item = _documento_ou_404(id_)
    if item["tipo"] != "texto":
        raise HTTPException(status_code=400, detail="planilha não tem página de PDF")

    if versao:
        corpo = estado.documentos.corpo_da_versao(id_, versao)
        if corpo is None:
            raise HTTPException(status_code=404, detail="essa versão não existe")
        item = {**item, "corpo": corpo}

    pdf = _pdf_do_documento(item)
    return Response(
        documento.pagina_png(pdf, numero, largura),
        media_type="image/png", headers={"Cache-Control": "no-cache"},
    )


@app.post("/api/documentos/{id_}/paginacao")
def documentos_paginacao(id_: int, payload: dict) -> dict:
    """
    Em que pagina cai cada paragrafo do que esta no editor agora.

    O editor mostrava "paginas ~4": caracteres divididos por uma media, que
    erra com titulo, lista ou paragrafo curto. Aqui o numero e medido - o PDF
    e montado de verdade, o mesmo que a pre-visualizacao desenha.

    Recebe o corpo em vez de ler do banco porque a pergunta e sobre o texto
    que esta na tela, ainda nao gravado.
    """
    item = _documento_ou_404(id_)
    if item["tipo"] != "texto":
        raise HTTPException(status_code=400, detail="planilha não tem página de PDF")

    corpo = payload.get("corpo")
    blocos = documento.ler_html(item["corpo"] if corpo is None else corpo)
    mapa = documento.mapa_de_paginas(
        blocos, timbre=_timbre_do_escritorio() or None, formato=item.get("formato"))

    return {**mapa, "blocos": len(blocos), "formato": documento.normalizar_formato(item.get("formato"))}


@app.post("/api/documentos/{id_}/formato")
def documentos_formato(id_: int, payload: dict) -> dict:
    """A fonte, o corpo, o recuo e as entrelinhas da folha deste documento."""
    item = _documento_ou_404(id_)
    if item["tipo"] != "texto":
        raise HTTPException(status_code=400, detail="planilha não tem formato de folha")

    try:
        formato = estado.documentos.formatar(id_, payload.get("formato", payload))
    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro))

    corpo = payload.get("corpo")
    blocos = documento.ler_html(item["corpo"] if corpo is None else corpo)
    mapa = documento.mapa_de_paginas(
        blocos, timbre=_timbre_do_escritorio() or None, formato=formato)
    return {**mapa, "blocos": len(blocos), "formato": formato}


@app.get("/api/documentos/{id_}/conferir")
def documentos_conferir(id_: int) -> dict:
    """
    O que conferir antes de o documento sair.

    Tudo regra, nada de modelo: lacuna de modelo que ficou, documento com
    digito verificador errado, valor com cifrao e sem numero, nome que aparece
    no texto sem bater com a ficha do cadastro. Roda em milissegundos e a
    resposta e sempre a mesma.
    """
    item = _documento_ou_404(id_)
    if item["tipo"] != "texto":
        return {"avisos": [], "paginas": 0}

    blocos = documento.ler_html(item["corpo"])
    avisos = documento.conferir(blocos, estado.cadastros.listar())
    pdf = _pdf_do_documento(item)

    return {
        "avisos": avisos,
        "impedem": sum(1 for a in avisos if a["grau"] == "impede"),
        "paginas": documento.paginas_de(pdf),
        "bytes": len(pdf),
        "contagem": documento.contar(blocos),
        "versao": item["versao"],
    }


@app.post("/api/documentos/{id_}/biblioteca")
def documentos_para_biblioteca(id_: int, payload: dict | None = None) -> dict:
    """
    Grava o PDF na biblioteca, para poder assinar e anexar em e-mail.

    Nunca passa por cima de arquivo existente: sai com numero no fim.
    """
    item = _documento_ou_404(id_)
    formato = str((payload or {}).get("formato", "pdf")).lower()

    if item["tipo"] == "planilha":
        abas = planilha.de_dict(json.loads(item["corpo"] or "{}"))
        dados = planilha.para_xlsx(abas, [planilha.calcular_aba(a) for a in abas])
        sufixo = ".xlsx"
    elif formato == "docx":
        dados = documento.para_docx(documento.ler_html(item["corpo"]), item["titulo"])
        sufixo = ".docx"
    else:
        dados = _pdf_do_documento(item)
        sufixo = ".pdf"

    estado.pasta.mkdir(parents=True, exist_ok=True)
    base = _arquivo(item["titulo"])
    destino = estado.pasta / f"{base}{sufixo}"
    conta = 2
    while destino.exists():
        destino = estado.pasta / f"{base} ({conta}){sufixo}"
        conta += 1

    destino.write_bytes(dados)
    return {
        "guardado": destino.name,
        "caminho": str(destino),
        "documentos": estado.recarregar(force=True) if sufixo != ".xlsx" else estado.recarregar(),
    }


def _arquivo(titulo: str) -> str:
    """Titulo virando nome de arquivo que o Windows aceita."""
    limpo = re.sub(r'[<>:"/\\|?*]', "-", titulo or "documento").strip(" .")
    return (limpo or "documento")[:90]


def _anexo(nome: str) -> dict:
    """
    O cabecalho que manda o navegador salvar o arquivo com esse nome.

    Cabecalho HTTP e latin-1, e titulo de documento brasileiro tem acento e
    travessao - "Contrato de honorarios - Cooperativa" derrubava a rota com
    UnicodeEncodeError. A regra do proprio HTTP resolve: um nome sem acento
    para quem so entende o basico, e o nome de verdade em UTF-8 ao lado.
    """
    from urllib.parse import quote

    simples = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    simples = (simples or "documento").replace(_ASPAS, "")
    return {
        "Content-Disposition":
            "attachment; filename=" + _ASPAS + simples + _ASPAS
            + "; filename*=UTF-8''" + quote(nome)
    }


_ASPAS = chr(34)



# --------------------------------------------------------- o assistente


INSTRUCAO_EDITOR = """Voce ajuda um advogado brasileiro a redigir. Responda em
portugues do Brasil, direto, sem preambulo.

Regras:
- devolva APENAS o texto pedido, pronto para entrar no documento
- nao invente numero de artigo, de lei, de sumula nem de processo
- nao invente nome, data, valor nem prazo que nao estejam no que foi dado
- se faltar informacao para escrever, escreva o texto com a lacuna marcada
  entre colchetes, por exemplo [VALOR]
- sem marcacao, sem asteriscos, sem titulo"""


class PedidoDeRedacao(BaseModel):
    corpo: str = ""
    cadastro_id: int | None = None


@app.post("/api/documentos/{id_}/clausulas")
def documentos_renumerar(id_: int, payload: PedidoDeRedacao) -> dict:
    """
    Poe as clausulas em sequencia e leva as referencias cruzadas junto.

    Nao grava: devolve o texto novo e a lista do que mudaria. Renumerar um
    contrato sem mostrar o que mudou e pedir para a pessoa aceitar no escuro.
    """
    _documento_ou_404(id_)
    corpo = payload.corpo or ""
    resultado = redacao.renumerar(corpo)
    return {
        **resultado,
        "quebradas": redacao.referencias_quebradas(resultado["texto"]),
        "estilo": redacao.estilo_do_documento(corpo),
    }


@app.get("/api/documentos/{id_}/conferir-clausulas")
def documentos_conferir_clausulas(id_: int) -> dict:
    """O que esta fora de ordem ou apontando para o nada, sem mexer em nada."""
    item = _documento_ou_404(id_)
    corpo = item["corpo"] or ""
    achadas = redacao.achar_clausulas(corpo)
    numeros = [a["numero"] for a in achadas]
    return {
        "clausulas": len(achadas),
        "numeros": numeros,
        "fora_de_ordem": numeros != sorted(numeros) or numeros != list(range(1, len(numeros) + 1)),
        "quebradas": redacao.referencias_quebradas(corpo),
        "estilo": redacao.estilo_do_documento(corpo),
    }


@app.get("/api/redacao/qualificacao")
def redacao_qualificacao(cadastro_id: int) -> dict:
    """
    O paragrafo de qualificacao de uma parte, com o que o cadastro tem.

    O que falta vira lacuna entre colchetes - e sai declarado, porque e mais
    barato completar o cadastro do que cacar colchete dentro do contrato
    depois de assinado.
    """
    ficha = estado.cadastros.obter(cadastro_id)
    if not ficha:
        raise HTTPException(status_code=404, detail="nao achei esse cadastro")
    return {
        "texto": redacao.qualificar(ficha),
        "falta": redacao.o_que_falta(ficha),
        "nome": ficha["nome"],
        "cadastro_id": cadastro_id,
    }


@app.post("/api/documentos/{id_}/assistente")
def documentos_assistente(id_: int, payload: PedidoAoAssistente) -> dict:
    """
    O assistente escrevendo dentro do documento.

    O ganho desta tela e este - o editor em si o Word ja faz. O que volta e
    sugestao: entra no texto so quando a pessoa aceitar.
    """
    item = _documento_ou_404(id_)
    pedido = payload.pedido.strip()
    if not pedido:
        raise HTTPException(status_code=400, detail="diga o que você quer que eu escreva")

    disponivel, motivo = check_ollama(estado.client.model)
    if not disponivel:
        raise HTTPException(status_code=503, detail=motivo)

    if payload.trecho.strip():
        contexto = f"Trecho selecionado do documento:\n{payload.trecho[:2500]}"
    else:
        texto = documento.para_texto(documento.ler_html(item["corpo"]))
        contexto = f"Documento (início):\n{texto[:2500]}"

    try:
        resposta = estado.client.ask(INSTRUCAO_EDITOR + f"\n\nPedido: {pedido}", contexto)
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    sugestao = _limpar_sugestao(resposta)
    inteiro = documento.para_texto(documento.ler_html(item["corpo"]))
    if _e_o_documento_de_volta(sugestao, inteiro):
        raise HTTPException(
            status_code=422,
            detail=("o modelo devolveu o documento de volta em vez da alteração. "
                    "Selecione no texto o trecho que você quer mudar e peça de "
                    "novo — com o trecho à mão ele acerta."),
        )

    return {
        "sugestao": sugestao,
        "sobre": payload.trecho[:160],
        "aviso": (
            "Escrito por um modelo pequeno rodando nesta máquina. Confira nomes, "
            "datas, valores e qualquer artigo de lei antes de aceitar."
        ),
    }


def _limpar_sugestao(texto: str) -> str:
    limpo = (texto or "").strip()
    limpo = re.sub(r"\*\*(.+?)\*\*", r"\1", limpo)
    limpo = re.sub(r"^\s*[*-]\s+", "", limpo, flags=re.M)
    limpo = re.sub(r"^\s*(sugest[aã]o|resposta|texto)\s*:\s*", "", limpo, flags=re.I)
    # "[Texto do documento]", "[Documento]": rotulo que o modelo copia do
    # cabecalho do contexto e entrega como se fosse parte do texto.
    limpo = re.sub(r"^\s*\[[^\]]{0,40}\]\s*", "", limpo)
    return limpo.strip()


def _e_o_documento_de_volta(sugestao: str, texto_do_documento: str) -> bool:
    """
    O modelo devolveu o documento em vez da alteracao?

    Acontece com pedido amplo - "deixe mais formal" sem trecho selecionado - e
    o estrago e silencioso: o texto entra no fim e o documento dobra de
    tamanho. Aconteceu de verdade: 355 palavras viraram 712.
    """
    a = re.sub(r"\s+", " ", sugestao or "").strip().lower()
    b = re.sub(r"\s+", " ", texto_do_documento or "").strip().lower()
    if len(a) < 400 or len(b) < 400:
        return False
    # Comeca igual, ou e quase do tamanho do documento e aparece dentro dele:
    # nos dois casos e copia, nao reescrita.
    return a[:300] == b[:300] or (len(a) > len(b) * 0.7 and a[:150] in b)


# ------------------------------------------------------------ planilha


def _abas_do(item: dict) -> list:
    try:
        return planilha.de_dict(json.loads(item["corpo"] or "{}"))
    except json.JSONDecodeError:
        return [planilha.Aba()]


def _resposta_planilha(id_: int, item: dict, abas: list) -> dict:
    calculados = [planilha.calcular_aba(a) for a in abas]
    return {
        "id": id_,
        "titulo": item["titulo"],
        "versao": item.get("versao", 1),
        "abas": [a.to_dict() for a in abas],
        "calculado": calculados,
        "resumos": [planilha.resumo(a, c) for a, c in zip(abas, calculados)],
        "formatos": [{"valor": k, "rotulo": v} for k, v in planilha.FORMATOS.items()],
        "funcoes": [
            {"nome": n, "exemplo": e, "explica": x} for n, e, x in planilha.AJUDA_FUNCOES
        ],
    }


@app.get("/api/planilha/{id_}")
def planilha_abrir(id_: int) -> dict:
    item = _documento_ou_404(id_)
    if item["tipo"] != "planilha":
        raise HTTPException(status_code=400, detail="isso não é uma planilha")
    return _resposta_planilha(id_, item, _abas_do(item))


@app.post("/api/planilha/{id_}/celula")
def planilha_celula(id_: int, payload: CelulaPlanilha) -> dict:
    item = _documento_ou_404(id_)
    abas = _abas_do(item)
    if not 0 <= payload.aba < len(abas):
        raise HTTPException(status_code=400, detail="aba não encontrada")
    if not planilha.RE_CELULA.match(payload.ref.upper()):
        raise HTTPException(status_code=400, detail="referência de célula inválida")

    abas[payload.aba].gravar(payload.ref, payload.dados)
    estado.documentos.salvar(id_, planilha.para_json(abas), nota=f"{payload.ref.upper()} alterada")
    return _resposta_planilha(id_, estado.documentos.obter(id_), abas)


@app.post("/api/planilha/{id_}/faixa")
def planilha_faixa(id_: int, payload: dict) -> dict:
    """
    Aplica formato, negrito, italico ou borda a uma selecao inteira.

    Uma celula de cada vez obrigava a repetir o clique por linha - e numa
    tabela de parcelas ninguem faz isso, simplesmente deixa sem.
    """
    item = _documento_ou_404(id_)
    abas = _abas_do(item)
    indice = int(payload.get("aba", 0))
    if not 0 <= indice < len(abas):
        raise HTTPException(status_code=400, detail="aba não encontrada")

    refs = planilha.refs_da_faixa(payload.get("faixa", ""))
    if not refs:
        raise HTTPException(status_code=400, detail="seleção vazia")
    if len(refs) > planilha.MAX_LINHAS * 4:
        raise HTTPException(status_code=400, detail="seleção grande demais")

    dados = {c: payload[c] for c in ("formato", "negrito", "italico", "borda", "valor")
             if c in payload}
    if not dados:
        raise HTTPException(status_code=400, detail="nada para aplicar")

    for ref in refs:
        abas[indice].gravar(ref, dados)

    estado.documentos.salvar(
        id_, planilha.para_json(abas),
        nota=f"{str(payload.get('faixa', '')).upper()}: {', '.join(dados)}")
    return _resposta_planilha(id_, estado.documentos.obter(id_), abas)


@app.post("/api/planilha/{id_}/congelar")
def planilha_congelar(id_: int, payload: dict) -> dict:
    """Prende a primeira linha no lugar - e vai junto para o XLSX."""
    item = _documento_ou_404(id_)
    abas = _abas_do(item)
    indice = int(payload.get("aba", 0))
    if not 0 <= indice < len(abas):
        raise HTTPException(status_code=400, detail="aba não encontrada")

    abas[indice].congelar_cabecalho = bool(payload.get("congelar"))
    estado.documentos.salvar(
        id_, planilha.para_json(abas),
        nota="congelou o cabeçalho" if abas[indice].congelar_cabecalho
        else "soltou o cabeçalho")
    return _resposta_planilha(id_, estado.documentos.obter(id_), abas)


@app.post("/api/planilha/{id_}/selecao")
def planilha_selecao(id_: int, payload: dict) -> dict:
    """
    O que a seleção tem dentro: soma, média, mínimo, máximo, vazias.

    Quem conta é a planilha, e não a tela: os mesmos números que as fórmulas
    usam. Uma soma calculada em JavaScript e outra em Python é a promessa de
    duas respostas diferentes para a mesma coluna.
    """
    item = _documento_ou_404(id_)
    abas = _abas_do(item)
    indice = int(payload.get("aba", 0))
    if not 0 <= indice < len(abas):
        raise HTTPException(status_code=400, detail="aba não encontrada")

    refs = planilha.refs_da_faixa(payload.get("faixa", ""))
    if not refs:
        raise HTTPException(status_code=400, detail="seleção vazia")

    calculado = planilha.calcular_aba(abas[indice])
    return {**planilha.resumo_selecao(abas[indice], calculado, refs),
            "faixa": str(payload.get("faixa", "")).upper()}


@app.post("/api/planilha/{id_}/ordenar")
def planilha_ordenar(id_: int, payload: dict) -> dict:
    """
    Ordena as linhas de uma faixa por uma coluna, com a linha inteira junto.

    Cria versao: ordenar muda o documento, e e a operacao desta tela com maior
    potencial de estrago que ninguem percebe olhando - cada celula continua com
    um numero plausivel, so que na linha errada. O "voltar para a v(n-1)" tem
    que existir.
    """
    item = _documento_ou_404(id_)
    abas = _abas_do(item)
    indice = int(payload.get("aba", 0))
    if not 0 <= indice < len(abas):
        raise HTTPException(status_code=400, detail="aba não encontrada")

    aba = abas[indice]
    calculado = planilha.calcular_aba(aba)
    try:
        feito = planilha.ordenar(
            aba, calculado, payload.get("faixa", ""), payload.get("coluna", ""),
            crescente=bool(payload.get("crescente", True)),
            com_cabecalho=bool(payload.get("com_cabecalho", False)),
        )
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro))

    estado.documentos.salvar(
        id_, planilha.para_json(abas),
        nota=f"ordenou {str(payload.get('faixa', '')).upper()} por {payload.get('coluna', '')}")
    return {**_resposta_planilha(id_, estado.documentos.obter(id_), abas), "ordenou": feito}


@app.post("/api/planilha/{id_}/filtrar")
def planilha_filtrar(id_: int, payload: dict) -> dict:
    """
    Quais linhas esconder para ver so o que casa com o criterio.

    Nao grava nada: filtro e jeito de olhar. Um filtro gravado esconderia
    linhas de quem abrisse o arquivo depois sem saber que ha filtro, e uma
    tabela de parcelas com linhas faltando e um erro que ninguem percebe.
    """
    item = _documento_ou_404(id_)
    abas = _abas_do(item)
    indice = int(payload.get("aba", 0))
    if not 0 <= indice < len(abas):
        raise HTTPException(status_code=400, detail="aba não encontrada")

    aba = abas[indice]
    try:
        return planilha.filtrar(
            aba, planilha.calcular_aba(aba), payload.get("faixa", ""),
            payload.get("coluna", ""), payload.get("criterio", ""),
            com_cabecalho=bool(payload.get("com_cabecalho", True)),
        )
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro))


@app.post("/api/planilha/{id_}/aba")
def planilha_nova_aba(id_: int, payload: dict) -> dict:
    item = _documento_ou_404(id_)
    abas = _abas_do(item)
    if len(abas) >= 6:
        raise HTTPException(status_code=400, detail="seis abas é o limite por planilha")

    nome = " ".join(str(payload.get("nome", "")).split())[:24] or f"Página {len(abas) + 1}"
    abas.append(planilha.Aba(nome=nome))
    estado.documentos.salvar(id_, planilha.para_json(abas), nota=f"aba {nome} criada")
    return _resposta_planilha(id_, estado.documentos.obter(id_), abas)


@app.delete("/api/planilha/{id_}/aba/{indice}")
def planilha_apagar_aba(id_: int, indice: int) -> dict:
    item = _documento_ou_404(id_)
    abas = _abas_do(item)
    if len(abas) <= 1:
        raise HTTPException(status_code=400, detail="a planilha precisa de pelo menos uma aba")
    if not 0 <= indice < len(abas):
        raise HTTPException(status_code=400, detail="aba não encontrada")

    fora = abas.pop(indice)
    estado.documentos.salvar(id_, planilha.para_json(abas), nota=f"aba {fora.nome} apagada")
    return _resposta_planilha(id_, estado.documentos.obter(id_), abas)


@app.post("/api/planilha/{id_}/importar")
async def planilha_importar(id_: int, arquivo: UploadFile) -> dict:
    """Traz um CSV ou XLSX para dentro da planilha, como abas novas."""
    item = _documento_ou_404(id_)
    nome = Path(arquivo.filename or "").name
    sufixo = Path(nome).suffix.lower()
    if sufixo not in (".csv", ".xlsx", ".txt"):
        raise HTTPException(status_code=400, detail="importo CSV e XLSX")

    dados = await arquivo.read()
    if len(dados) > 12 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="arquivo grande demais")

    abas = _abas_do(item)
    try:
        if sufixo == ".xlsx":
            novas = planilha.de_xlsx(dados)
        else:
            texto = dados.decode("utf-8", errors="replace")
            if texto.count("�") > len(texto) * 0.01:
                texto = dados.decode("cp1252", errors="replace")
            novas = [planilha.de_csv(texto, Path(nome).stem[:24])]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"não consegui ler o arquivo: {exc}") from exc

    abas = (abas + novas)[:6]
    estado.documentos.salvar(id_, planilha.para_json(abas), nota=f"importado {nome}")
    return _resposta_planilha(id_, estado.documentos.obter(id_), abas)


@app.get("/api/planilha/{id_}/exportar")
def planilha_exportar(id_: int, formato: str = "xlsx", aba: int = 0):
    from fastapi.responses import Response

    item = _documento_ou_404(id_)
    abas = _abas_do(item)
    nome = _arquivo(item["titulo"])

    if formato == "csv":
        if not 0 <= aba < len(abas):
            aba = 0
        texto = planilha.para_csv(abas[aba], planilha.calcular_aba(abas[aba]))
        return Response(
            texto.encode("utf-8-sig"), media_type="text/csv",
            headers=_anexo(nome + ".csv"),
        )

    dados = planilha.para_xlsx(abas, [planilha.calcular_aba(a) for a in abas])
    return Response(
        dados,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=_anexo(nome + ".xlsx"),
    )


@app.post("/api/planilha/{id_}/assistente")
def planilha_assistente(id_: int, payload: PedidoAoAssistente) -> dict:
    """
    Pede uma formula em portugues e recebe a formula pronta.

    O modelo escreve a formula; quem calcula e o motor da planilha. Assim um
    erro do modelo vira #NOME? numa celula, nao numero errado num honorario.
    """
    item = _documento_ou_404(id_)
    if item["tipo"] != "planilha":
        raise HTTPException(status_code=400, detail="isso não é uma planilha")
    if not payload.pedido.strip():
        raise HTTPException(status_code=400, detail="diga o que você quer calcular")

    disponivel, motivo = check_ollama(estado.client.model)
    if not disponivel:
        raise HTTPException(status_code=503, detail=motivo)

    abas = _abas_do(item)
    aba = abas[0]
    calculado = planilha.calcular_aba(aba)

    linhas = []
    for ref in sorted(aba.celulas, key=lambda r: (planilha._posicao(r)[0], planilha._posicao(r)[1]))[:60]:
        linhas.append(f"{ref}: {(calculado.get(ref) or {}).get('texto', '')}")

    instrucao = (
        "Voce escreve formulas de planilha no padrao brasileiro: ponto e virgula separa "
        "argumento e virgula e o decimal. Funcoes em portugues: SOMA, MEDIA, SE, SOMASE, "
        "CONT.SE, MAXIMO, MINIMO, ARRED. Responda APENAS com a formula, comecando por =. "
        "Nao explique. Nao invente celula que nao esta na lista."
    )
    try:
        resposta = estado.client.ask(instrucao + f"\n\nPedido: {payload.pedido}",
                                     "Células com valor:\n" + "\n".join(linhas))
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    formula = _so_a_formula(resposta)
    prova = _provar_formula(formula, aba)
    return {
        "formula": formula,
        "resultado": prova["texto"],
        "erro": prova["erro"],
        "aviso": "Confira a fórmula antes de inserir: o modelo pode citar a célula errada.",
    }


def _so_a_formula(bruto: str) -> str:
    texto = (bruto or "").strip().replace("`", "")
    achado = re.search(r"=[^\n]+", texto)
    return achado.group().strip() if achado else texto.split("\n")[0].strip()


def _provar_formula(formula: str, aba) -> dict:
    """Roda a formula antes de oferecer, para a tela ja mostrar o resultado."""
    prova = planilha.Aba(nome=aba.nome, celulas=dict(aba.celulas))
    prova.gravar("ZZ999", {"valor": formula})
    calculado = planilha.calcular_aba(prova)
    celula = calculado.get("ZZ999", {})
    return {"texto": celula.get("texto", ""), "erro": bool(celula.get("erro"))}

# --------------------------------------- financeiro, relatorios, bem-estar


class FichaLancamento(BaseModel):
    id: int | None = None
    dados: dict = {}


class Liquidacao(BaseModel):
    quando: str = ""


class FichaLembrete(BaseModel):
    id: int | None = None
    dados: dict = {}


class PedidoCiclo(BaseModel):
    tarefa: str = ""
    foco: int = 0
    pausa: int = 0


class MensagemWhats(BaseModel):
    telefone: str = ""
    nome: str = ""
    texto: str = ""
    anexo: str = ""


@app.get("/api/financeiro")
def financeiro_painel(mes: str = "") -> dict:
    """
    O painel do mes.

    Todo numero aqui e soma de lancamento que existe. Sem lancamento, o numero
    e zero e a tela diz que esta vazio - grafico bonito de dado que ninguem
    digitou e a forma mais rapida de o financeiro perder a confianca de quem usa.
    """
    dados = estado.financeiro.para_tela(mes)
    dados["clientes"] = [
        {"id": f["id"], "nome": f["nome"]} for f in estado.cadastros.listar()
    ]
    dados["onde_moram"] = (
        "Os lançamentos ficam no mesmo arquivo do resto do programa, nesta máquina. "
        "Não há senha separada para o financeiro: quem abre o Windows com a sua conta "
        "vê esta tela. Uma permissão por pessoa só faria sentido num PAULUS de equipe, "
        "que ainda não existe."
    )

    # O escritorio por dentro vem na mesma resposta: sao seis blocos da mesma
    # tela, e seis chamadas fariam a tela pintar em pedacos.
    mes_alvo = dados["painel"]["mes"]
    dados["folha"] = estado.folha.do_mes(mes_alvo)
    dados["candidatos_folha"] = estado.folha.pessoas()
    dados["notas"] = estado.papeis.listar("nota", mes_alvo)
    dados["notas_a_emitir"] = estado.papeis.a_emitir(mes_alvo)
    dados["boletos"] = estado.papeis.listar("boleto")
    dados["comprovantes"] = escritorio.comprovantes_do_mes(estado.base, mes_alvo)
    dados["sem_comprovante"] = escritorio.sem_comprovante(estado.base, mes_alvo)
    dados["concluidos"] = escritorio.contratos_concluidos(estado.base, mes_alvo)
    dados["fechamento"] = escritorio.fechamento(
        estado.base, estado.folha, estado.papeis, mes_alvo)
    dados["meses"] = _meses_com_movimento()
    return dados


def _meses_com_movimento() -> list[dict]:
    """
    Os meses que o seletor oferece: os que tem lancamento, mais o de hoje.

    Oferecer doze meses fixos daria meses vazios para escolher; oferecer so os
    que tem dado esconderia o mes corrente enquanto nada foi lancado nele.
    """
    linhas = estado.base.buscar(
        "SELECT DISTINCT substr(COALESCE(NULLIF(liquidado_em,''), vencimento, ''),1,7) m "
        "FROM lancamentos WHERE m != '' ORDER BY m DESC"
    )
    meses = [l["m"] for l in linhas]
    hoje = escritorio.mes_de_hoje()
    if hoje not in meses:
        meses.insert(0, hoje)
    return [{"valor": m, "rotulo": escritorio.mes_por_extenso(m)} for m in meses[:24]]


@app.get("/api/financeiro/lancamentos")
def financeiro_listar(tipo: str = "", mes: str = "", situacao: str = "") -> dict:
    return {"lancamentos": estado.financeiro.listar(tipo=tipo, mes=mes, situacao=situacao)}


@app.get("/api/financeiro/extrato")
def financeiro_extrato(mes: str = "") -> dict:
    return estado.financeiro.extrato(mes)


@app.post("/api/financeiro/lancamentos")
def financeiro_salvar(payload: FichaLancamento) -> dict:
    try:
        id_ = estado.financeiro.salvar(payload.dados, payload.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return estado.financeiro.obter(id_) or {}


@app.post("/api/financeiro/lancamentos/{id_}/liquidar")
def financeiro_liquidar(id_: int, payload: Liquidacao) -> dict:
    if not estado.financeiro.liquidar(id_, payload.quando):
        raise HTTPException(status_code=404, detail="lançamento não encontrado")
    return estado.financeiro.obter(id_) or {}


@app.post("/api/financeiro/lancamentos/{id_}/reabrir")
def financeiro_reabrir(id_: int) -> dict:
    if not estado.financeiro.reabrir(id_):
        raise HTTPException(status_code=404, detail="lançamento não encontrado")
    return estado.financeiro.obter(id_) or {}


@app.delete("/api/financeiro/lancamentos/{id_}")
def financeiro_apagar(id_: int) -> dict:
    if not estado.financeiro.apagar(id_):
        raise HTTPException(status_code=404, detail="lançamento não encontrado")
    return {"apagado": id_}


@app.post("/api/financeiro/lancamentos/{id_}/comprovante")
async def financeiro_comprovante(id_: int, arquivo: UploadFile) -> dict:
    """Guarda o comprovante na biblioteca e o liga ao lancamento."""
    if not estado.financeiro.obter(id_):
        raise HTTPException(status_code=404, detail="lançamento não encontrado")

    nome = Path(arquivo.filename or "").name
    if not nome:
        raise HTTPException(status_code=400, detail="arquivo sem nome")

    dados = await arquivo.read()
    if len(dados) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="arquivo grande demais")

    pasta = BASE_DIR / "data" / "comprovantes"
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / nome
    conta = 2
    while destino.exists():
        destino = pasta / f"{Path(nome).stem} ({conta}){Path(nome).suffix}"
        conta += 1
    destino.write_bytes(dados)

    import hashlib

    sha1 = hashlib.sha1(dados).hexdigest()
    estado.financeiro.anexar(id_, destino.name, str(destino), sha1)
    return estado.financeiro.obter(id_) or {}


@app.delete("/api/financeiro/comprovante/{id_}")
def financeiro_tirar_comprovante(id_: int) -> dict:
    estado.financeiro.tirar_comprovante(id_)
    return {"removido": id_}


@app.post("/api/financeiro/cobrar")
def financeiro_cobrar(payload: dict) -> dict:
    """
    Prepara a cobranca de um recebimento atrasado como rascunho de e-mail.

    Nao envia: monta o texto e devolve. O envio segue o caminho de sempre, com
    a fila de aprovacao no meio.
    """
    item = estado.financeiro.obter(int(payload.get("id", 0)))
    if not item:
        raise HTTPException(status_code=404, detail="lançamento não encontrado")

    ficha = estado.cadastros.obter(item["cadastro_id"]) if item["cadastro_id"] else None
    vencimento = item["vencimento"]
    atraso = item["dias_atraso"]

    corpo = (
        f"Prezados,\n\n"
        f"Consta em nosso controle o valor de {item['valor']} referente a "
        f"{item['descricao']}"
    )
    if vencimento:
        corpo += f", com vencimento em {financeiro._br(vencimento)}"
        if atraso:
            corpo += f" — portanto há {atraso} dia(s)"
    corpo += (
        ".\n\nCaso o pagamento já tenha sido efetuado, favor desconsiderar e nos "
        "encaminhar o comprovante.\n\nFico à disposição."
    )

    return {
        "para": (ficha or {}).get("email", ""),
        "assunto": f"Cobrança — {item['descricao']}",
        "corpo": corpo,
        "cliente": (ficha or {}).get("nome", ""),
        "sem_email": not (ficha or {}).get("email"),
    }


# ------------------------------------------------------------ relatorios


@app.get("/api/relatorios")
def relatorios_ver(quando: str = "") -> dict:
    return estado.relatorios.para_tela(quando)


@app.get("/api/relatorios/acoes")
def relatorios_acoes(limite: int = 40) -> dict:
    """O que o assistente fez com o seu sim, lido da fila de aprovacoes."""
    return {"acoes": estado.relatorios.acoes(limite=limite)}


@app.post("/api/relatorios/parecer")
def relatorios_parecer(payload: dict | None = None) -> dict:
    """
    O parecer em texto sobre o dia.

    O modelo recebe os numeros ja apurados e escreve sobre eles. Nao calcula:
    um erro de aritmetica de um modelo de 3 bilhoes de parametros viraria
    numero errado num parecer financeiro, e parecer com numero errado e pior
    que nenhum parecer.
    """
    quando = str((payload or {}).get("quando", ""))
    numeros = estado.relatorios.numeros_para_o_parecer(quando)

    disponivel, motivo = check_ollama(estado.client.model)
    if not disponivel:
        raise HTTPException(status_code=503, detail=motivo)

    try:
        texto = estado.client.ask(relatorios.INSTRUCAO_PARECER, numeros)
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "parecer": _limpar_sugestao(texto),
        "numeros": numeros,
        "aviso": "Escrito sobre os números acima, que foram calculados aqui. Confira antes de usar.",
    }


@app.post("/api/relatorios/pdf")
def relatorios_pdf(payload: dict | None = None):
    """O relatorio do dia como PDF, pelo mesmo gerador dos documentos."""
    from fastapi.responses import Response

    quando = str((payload or {}).get("quando", "")) or datetime.now().strftime("%Y-%m-%d")
    d = estado.relatorios.dia(quando)
    m = estado.relatorios.mes(quando[:7])

    html = [f"<h1>Relatório de {d['rotulo']}</h1>"]
    t = d["tarefas"]
    html.append(f"<h2>Tarefas</h2><p>{len(t['feitas'])} de {t['planejado']} concluída(s).</p>")
    if t["feitas"]:
        html.append("<ul>" + "".join(
            f"<li>{_escapar(x['titulo'])} — {x['hora']}</li>" for x in t["feitas"]) + "</ul>")
    if t["abertas"]:
        html.append("<p>Ficaram abertas:</p><ul>" + "".join(
            f"<li>{_escapar(x['titulo'])} ({_escapar(x['quando'])})</li>" for x in t["abertas"]) + "</ul>")

    if d["medido"]:
        html.append(f"<h2>Tempo</h2><p>Ativo por {d['medido']['tempo_ativo']}, "
                    f"{d['medido']['pausas']} pausa(s), {d['medido']['ciclos']} ciclo(s) de foco.</p>")

    if d["acoes"]:
        html.append("<h2>Ações aprovadas por você</h2><ul>" + "".join(
            f"<li>{_escapar(a['titulo'])} — {_escapar(a['resultado'] or a['estado'])} ({a['hora']})</li>"
            for a in d["acoes"]) + "</ul>")

    e = m["extrato"]
    html.append(f"<h2>Financeiro — {_escapar(m['rotulo'])}</h2>"
                f"<p>Entradas {m['entradas_texto']}, saídas {m['saidas_texto']}, "
                f"resultado {e['resultado_texto']}. Saldo em caixa: {e['saldo_final_texto']}.</p>")
    if e["linhas"]:
        html.append("<ul>" + "".join(
            f"<li>{l['dia']} — {_escapar(l['descricao'])}: {l['movimento_texto']}</li>"
            for l in e["linhas"]) + "</ul>")

    html.append("<p><i>Relatório montado nesta máquina. Nenhum dado saiu daqui.</i></p>")

    pdf = documento.para_pdf(
        documento.ler_html("".join(html)),
        f"Relatório de {quando}",
        "PAULUS · relatório gerado nesta máquina",
    )
    return Response(pdf, media_type="application/pdf",
                    headers=_anexo(f"Relatorio {quando}.pdf"))


def _escapar(texto: str) -> str:
    from xml.sax.saxutils import escape

    return escape(str(texto or ""))


# ------------------------------------------------------------ bem-estar


@app.get("/api/bemestar")
def bemestar_ver() -> dict:
    dados = estado.bem_estar.para_tela()
    dados["sugeridos_criados"] = estado.bem_estar.sugerir_lembretes()
    if dados["sugeridos_criados"]:
        dados["lembretes"] = estado.bem_estar.lembretes()
    return dados


@app.post("/api/bemestar/medir")
def bemestar_medir(payload: dict) -> dict:
    """
    Liga ou desliga o acompanhamento.

    Desligar e opcao de verdade: a thread para e nada mais e gravado. O ciclo
    de foco e os lembretes continuam funcionando sem ele.
    """
    if payload.get("ligar"):
        if not estado.bem_estar.ligar():
            raise HTTPException(
                status_code=400,
                detail="não consigo medir a atividade neste sistema - o ciclo de foco e os lembretes continuam funcionando",
            )
    else:
        estado.bem_estar.desligar()
    return estado.bem_estar.para_tela()


@app.post("/api/bemestar/ciclo")
def bemestar_ciclo(payload: PedidoCiclo) -> dict:
    return estado.bem_estar.comecar_ciclo(payload.tarefa, payload.foco, payload.pausa)


@app.post("/api/bemestar/pausa")
def bemestar_pausa() -> dict:
    return estado.bem_estar.ir_para_pausa()


@app.post("/api/bemestar/parar")
def bemestar_parar() -> dict:
    return estado.bem_estar.parar_ciclo()


@app.get("/api/bemestar/ciclo")
def bemestar_ciclo_estado() -> dict:
    return {**estado.bem_estar.estado_do_ciclo(), "alerta": estado.bem_estar.alerta()}


@app.post("/api/bemestar/lembretes")
def bemestar_salvar_lembrete(payload: FichaLembrete) -> dict:
    try:
        estado.bem_estar.salvar_lembrete(payload.dados, payload.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"lembretes": estado.bem_estar.lembretes()}


@app.post("/api/bemestar/lembretes/{id_}/feito")
def bemestar_marcar(id_: int) -> dict:
    if not estado.bem_estar.marcar_lembrete(id_):
        raise HTTPException(status_code=404, detail="lembrete não encontrado")
    return {"lembretes": estado.bem_estar.lembretes(), "hoje": estado.bem_estar.dia()}


@app.delete("/api/bemestar/lembretes/{id_}")
def bemestar_apagar_lembrete(id_: int) -> dict:
    estado.bem_estar.apagar_lembrete(id_)
    return {"lembretes": estado.bem_estar.lembretes()}


# ------------------------------------------------------------- conexoes


@app.get("/api/conexoes")
def conexoes_ver() -> dict:
    dados = estado.conexoes.para_tela()
    dados["janela_embutida"] = _tem_janela()
    return dados


def _tem_janela() -> bool:
    """A janela embutida so existe quando o programa roda como desktop."""
    try:
        import webview

        return bool(webview.windows)
    except Exception:
        return False


@app.post("/api/conexoes/abrir")
def conexoes_abrir(payload: dict | None = None) -> dict:
    """
    Abre a janela do serviço, presa a um endereço só.

    Fora do modo desktop nao ha janela embutida - e a tela diz isso em vez de
    abrir o navegador comum fingindo que e a mesma coisa, porque a sessao nao
    seria a mesma.
    """
    endereco = str((payload or {}).get("endereco", "")) or conexoes.WHATSAPP
    if not endereco.startswith(conexoes.WHATSAPP):
        raise HTTPException(status_code=400, detail="esta janela só abre o WhatsApp Web")

    if not _tem_janela():
        return {
            "abriu": False,
            "endereco": endereco,
            "motivo": (
                "A janela embutida existe quando o PAULUS roda como programa "
                "(python src/desktop.py). No navegador, a sessão seria a do próprio "
                "navegador, não a minha — então prefiro dizer isso a fingir que é igual."
            ),
        }

    import webview

    webview.create_window(
        "WhatsApp Web · PAULUS", endereco,
        width=1100, height=800, min_size=(720, 560),
    )
    return {"abriu": True, "endereco": endereco}


@app.post("/api/conexoes/mensagem")
def conexoes_mensagem(payload: MensagemWhats) -> dict:
    """
    Prepara a conversa com o texto pronto - e para aí.

    Apertar enviar continua sendo seu. O programa não clica na tela de um site
    de terceiro: quebraria a cada mudança de layout, e o preço de errar é a
    conta do escritório ser derrubada.
    """
    endereco = conexoes.link_de_conversa(payload.telefone, payload.texto)
    if not endereco:
        raise HTTPException(status_code=400, detail="informe um telefone com DDD")

    anexo = ""
    if payload.anexo:
        alvo = Path(payload.anexo)
        if not alvo.exists():
            raise HTTPException(status_code=400, detail="não achei esse arquivo")
        anexo = str(alvo)

    estado.conexoes.anotar(payload.telefone, payload.nome, anexo)
    return {
        "endereco": endereco,
        "anexo": Path(anexo).name if anexo else "",
        "pasta_do_anexo": str(Path(anexo).parent) if anexo else "",
        "aviso": (
            "Abro a conversa com o texto escrito. Você confere e aperta enviar."
            + (" O anexo você arrasta da pasta que eu abri." if anexo else "")
        ),
    }


@app.post("/api/conexoes/sessao/apagar")
def conexoes_apagar_sessao() -> dict:
    apagou = estado.conexoes.apagar_sessao()
    return {
        "apagou": apagou,
        "aviso": "A sessão foi apagada desta máquina. O WhatsApp vai pedir o código de novo."
        if apagou else "Não havia sessão guardada.",
    }


@app.get("/api/conexoes/contatos")
def conexoes_contatos() -> dict:
    """Quem tem telefone no cadastro - para não digitar número na mão."""
    achados = []
    for f in estado.cadastros.listar():
        if (f.get("telefone") or "").strip():
            achados.append({
                "id": f["id"], "nome": f["nome"], "telefone": f["telefone"],
                "numero": conexoes.numero_whatsapp(f["telefone"]),
            })
    return {"contatos": achados}

# ------------------------------------------------------------------ leis


class ImportarLei(BaseModel):
    caminho: str = ""
    codigo: str = ""


@app.get("/api/leis")
def leis_listar() -> dict:
    """O que está no disco, e o que falta."""
    return {
        "codigos": estado.leis.instalados(),
        "contagem": estado.leis.contagem(),
        "porque": (
            "Com o texto no disco, citar um artigo é consulta a um índice. Sem ele, eu "
            "não cito: pedir o número a um modelo de 3 bilhões de parâmetros devolve "
            "artigo plausível e errado dentro de um contrato."
        ),
        "como_baixar": (
            "Abra a página do código no Planalto, salve como “Página da Web, completa” "
            "e escolha o arquivo aqui. É o texto compilado oficial, com as alterações "
            "já incorporadas."
        ),
    }


@app.post("/api/leis/importar")
def leis_importar(payload: ImportarLei) -> dict:
    """
    Lê o texto oficial e guarda artigo por artigo.

    O que não é artigo do código fica de fora e é contado: o decreto que aprova
    a consolidação tem artigos próprios, e as disposições finais citam artigos
    de outras leis. Guardar essas citações como artigos deste código seria
    inventar artigo que não existe.
    """
    alvo = Path(payload.caminho)
    if not alvo.exists():
        raise HTTPException(status_code=400, detail="não achei esse arquivo")
    if alvo.suffix.lower() not in (".html", ".htm"):
        raise HTTPException(status_code=400, detail="salve a página do Planalto como HTML")

    try:
        resultado = estado.leis.importar(alvo, payload.codigo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {**resultado, "codigos": estado.leis.instalados(),
            "contagem": estado.leis.contagem()}


@app.post("/api/leis/importar-pasta")
def leis_importar_pasta(payload: dict) -> dict:
    """Importa de uma vez tudo o que a pasta tiver e o programa reconhecer."""
    pasta = Path(str(payload.get("pasta", "")))
    if not pasta.is_dir():
        raise HTTPException(status_code=400, detail="essa pasta não existe")

    feitos, ignorados = [], []
    for arquivo in sorted(list(pasta.glob("*.html")) + list(pasta.glob("*.htm"))):
        codigo = leis.reconhecer(arquivo)
        if not codigo:
            ignorados.append({"arquivo": arquivo.name, "motivo": "não reconheci de qual código é"})
            continue
        try:
            feitos.append(estado.leis.importar(arquivo, codigo))
        except ValueError as exc:
            ignorados.append({"arquivo": arquivo.name, "motivo": str(exc)})

    return {"importados": feitos, "ignorados": ignorados,
            "codigos": estado.leis.instalados(), "contagem": estado.leis.contagem()}


@app.delete("/api/leis/{codigo}")
def leis_apagar(codigo: str) -> dict:
    estado.leis.apagar(codigo)
    return {"codigos": estado.leis.instalados(), "contagem": estado.leis.contagem()}


@app.get("/api/leis/procurar")
def leis_procurar(termo: str = "", codigo: str = "", limite: int = 20) -> dict:
    """
    Busca por número de artigo ou por palavra.

    Quando não há código instalado, a resposta diz isso em vez de devolver
    vazio: lista vazia parece "não existe artigo sobre isso", e o certo é
    "ainda não tenho o texto da lei aqui".
    """
    if not estado.leis.contagem()["codigos"]:
        return {"achados": [], "sem_codigo": True,
                "aviso": "Nenhum código instalado ainda. Importe o texto oficial primeiro."}
    return {"achados": estado.leis.procurar(termo, codigo, limite), "sem_codigo": False}


@app.get("/api/leis/artigo")
def leis_artigo(codigo: str, numero: str) -> dict:
    a = estado.leis.artigo(codigo, numero)
    if not a:
        raise HTTPException(
            status_code=404,
            detail=f"não achei o art. {numero} no {leis.CODIGOS.get(codigo, {}).get('nome', codigo)}",
        )
    return {"artigo": a, "vizinhos": estado.leis.vizinhos(codigo, a["ordem"])}

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
