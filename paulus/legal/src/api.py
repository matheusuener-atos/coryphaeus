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
import threading
from datetime import datetime
from collections.abc import Iterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

import requests

import aprovacoes as fila_aprovacoes
import assinatura
import certificado
import destinos
import pastas
import recursos
import registro
from classify import Classificacao, ROTULOS
from agenda import Agenda, ONDES, TIPOS as TIPOS_AGENDA
from base import Base
from cadastros import Cadastros, TIPOS as TIPOS_CADASTRO
from config import Preferencias
from tarefas import Tarefas
from habilidade_base import (
    PRECISA_ASSISTENTE,
    PRECISA_DOCUMENTOS,
    Contexto,
)
from extract import SUPPORTED_SUFFIXES, index_all_contracts
from jobs import AGUARDANDO, CONCLUIDO, EXECUTANDO, Etapa, Trabalhos, titular
from jobs import agora as jobs_agora
from llama_client import DEFAULT_MODEL, LlamaClient, OllamaError, check_ollama
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


@app.get("/api/biblioteca")
def biblioteca() -> dict:
    """
    O que o PAULUS tem aberto, com o que ele ja sabe sobre cada arquivo.

    Junta o indice de leitura com o cache de classificacao: sem isso a tela
    mostraria nome e tamanho, que e o que o Explorer ja faz.
    """
    from classify import CacheClassificacao

    cache = CacheClassificacao(CLASSIFICACAO_PATH).dados
    itens: list[dict] = []

    for doc in estado.searcher.documents:
        caminho = Path(doc.path)
        try:
            info = caminho.stat()
            tamanho = info.st_size
            aberto_em = datetime.fromtimestamp(info.st_mtime).strftime("%Y-%m-%d")
            existe = True
        except OSError:
            tamanho, aberto_em, existe = 0, "", False

        conhecido = cache.get(doc.sha1) or {}
        trechos = sum(1 for c in estado.searcher.chunks if c.doc_name == doc.name)

        itens.append({
            "sha1": doc.sha1,
            "nome": doc.name,
            "caminho": str(caminho),
            "pasta": str(caminho.parent),
            "existe": existe,
            "bytes": tamanho,
            "paginas": doc.pages,
            "caracteres": doc.chars,
            "trechos": trechos,
            "aberto_em": aberto_em,
            "tipo": conhecido.get("tipo", ""),
            "tipo_rotulo": ROTULOS.get(conhecido.get("tipo", ""), ""),
            "cliente": conhecido.get("cliente", ""),
            "data": conhecido.get("data", ""),
            "valor": conhecido.get("valor", ""),
        })

    itens.sort(key=lambda i: i["nome"].lower())
    return {
        "documentos": itens,
        "pasta": str(estado.pasta),
        "total_bytes": sum(i["bytes"] for i in itens),
        "total_trechos": len(estado.searcher.chunks),
    }


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
                    trabalho.etapas[0].detalhe = f"{dados['total_contratos']} documento(s)"
                    trabalho.etapas[1].estado = EXECUTANDO
                    trabalho.etapas[1].feitos = len(fontes)
                    trabalho.etapas[1].total = len(fontes)
                    yield _sse("fontes", dados)
                    yield _sse("etapas", {"etapas": [asdict_etapa(e) for e in trabalho.etapas]})
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
        trabalho.etapas[1].estado = CONCLUIDO
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
def cadastros_listar(tipo: str = "", termo: str = "") -> dict:
    return {
        "fichas": estado.cadastros.listar(tipo, termo),
        "contagem": estado.cadastros.contagem(),
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
    estado.tarefas.concluir(id_, payload.valor)
    return estado.tarefas.obter(id_) or {"apagada": True}


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


EXECUTORES = {
    "organizar.mover": _executar_mover,
    "assinatura.assinar": _executar_assinar,
}


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
        estado.client = LlamaClient(model=modelo)
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
