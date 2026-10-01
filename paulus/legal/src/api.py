"""
PAULUS Legal - Backend web (FastAPI).

Serve a interface e expoe a mesma logica do CLI por HTTP. Roda so em
localhost: o navegador precisa estar na mesma maquina que o Ollama, e nenhum
documento sai daqui.

    python src/api.py
    http://localhost:8000
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import shutil
import tempfile
import subprocess
import sys
import queue
import threading
import time
import uuid
import unicodedata
from datetime import date, datetime, timedelta
from collections.abc import Iterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel

import requests

import aprovacoes as fila_aprovacoes
import apoio
import assinatura
import traducao
import certificado
import correio
import correio_contas
import correio_oauth
import segredos
import destinos
import avisos
import bemestar
import conexoes
import documento
import financeiro
import extrato
import acervo
import nomes as nomes_mod
import citacao
import escritorio
import ferramentas
import intencao
import juizo
import modelos as modelos_mod
import programa
import consulta_cadastro
import leis
import redacao
import ritmo as ritmo_mod
import planilha
import relatorios
import servicos as servicos_mod
import gravacoes as gravacoes_mod
import transcricao as transcricao_mod
import lixeira as lixeira_mod
import contextos as contextos_mod
import material as material_mod
import maquina as maquina_mod
import entrada
import google_servicos
import atualizacao as atualizacao_mod
import calibracao_remota
from versao import VERSAO
from acesso.chave import ChaveLocal
from acesso.porteiro import Porteiro
from acesso.servico import AcessoDeFora
import equipe
from acesso import politicas as politicas_do_acesso
from acesso import rotas as rotas_do_acesso
from acesso import rotas_tunel as rotas_do_tunel
from acesso import rotas_auditoria as rotas_da_auditoria
from acesso.conexao import ConexaoDoTunel
from inteligencia import portas as inteligencia
import inferencia
from inteligencia.catalogo import Catalogo
import denso as denso_mod
import rotas_ajuda
from biblioteca import rotas as rotas_biblioteca
import captura as captura_mod
import mcp_leis
import word_suplemento
import rotas_chaves
import execucoes as execucoes_mod
import rotas_execucoes
import rotas_conversa
import saudacao as saudacao_mod
import agente_na_conversa as agente_mod
import ia_em_fundo
import detalhes as detalhes_mod
import rotas_agentes
import agentes_medida
import agentes_tela
import rotas_avisos
import recuperacao as recuperacao_mod
from lexico import IndiceLexico
from medicao import Medicao
import memoria as memoria_mod
from inteligencia.guarda import Biblioteca
import marca as marca_mod
import pastas
import recursos
import registro
from classify import Classificacao, ROTULOS
from agenda import Agenda, CAMPOS as CAMPOS_AGENDA, ONDES, TIPOS as TIPOS_AGENDA
from base import Base
from cadastros import Cadastros, TIPOS as TIPOS_CADASTRO
from config import Preferencias
import tarefas as tarefas_mod
import aparelho as aparelho_mod
import aparelho_motor
import aprendizado as aprendizado_mod
import processos as processos_mod
import clientes as clientes_mod
import passos as passos_mod
import fundamentacao as fundamentacao_mod
import comunidade as comunidade_mod
import jurisprudencia as jurisprudencia_mod
import nuvem as nuvem_mod
import vigencia as vigencia_mod
import perfis as perfis_mod
import fila_de_todos
import fila_modelo
from fila_modelo import FilaCheia, FilaDoModelo
from tarefas import Tarefas
from habilidade_base import (
    PRECISA_ASSISTENTE,
    PRECISA_DOCUMENTOS,
    Contexto,
)
from extract import (SUPPORTED_SUFFIXES, chave_do_caminho, extract_file, file_sha1, index_all_contracts,
                     listar_arquivos, motivo_sem_texto)
from jobs import AGUARDANDO, CONCLUIDO, EXECUTANDO, LIMITE_DE_NOME, PAUSADO, Etapa, Trabalhos, titular
from jobs import agora as jobs_agora
from llama_client import (
    DEFAULT_MODEL,
    LlamaClient,
    OllamaError,
    check_ollama,
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
import search as search_mod
import servicos_acesso

BASE_DIR = Path(__file__).parent.parent
# Onde ficam os dados desta instalacao. PAULUS_DADOS troca a pasta inteira -
# e assim que a base de demonstracao (tools/demo) roda sem encostar nos dados
# de verdade. Os modelos de voz ficam fora disso: sao do programa, nao do
# escritorio, e baixar 1,6 GB de novo para uma demonstracao nao faz sentido.
DADOS_DIR = Path(os.environ.get("PAULUS_DADOS") or (BASE_DIR / "data")).resolve()
CONTRACTS_DIR = DADOS_DIR / "test_contracts"
NOME_DA_PASTA_PADRAO = "Documentos do escritório"
CACHE_PATH = DADOS_DIR / "extractions" / "index.json"
CLASSIFICACAO_PATH = DADOS_DIR / "extractions" / "classificacao.json"
# Os nomes que a pessoa recusou na sugestao de cadastro (Cadastros).
SUGESTOES_IGNORADAS_PATH = DADOS_DIR / "cadastros_ignorados.json"
DIARIOS_DIR = DADOS_DIR / "diarios"
TRABALHOS_DIR = DADOS_DIR / "trabalhos"
APROVACOES_PATH = DADOS_DIR / "aprovacoes.json"
PREFERENCIAS_PATH = DADOS_DIR / "preferencias.json"
BASE_PATH = DADOS_DIR / "paulus.db"
CERTIFICADO_DIR = DADOS_DIR / "certificado"
COFRE_PATH = CERTIFICADO_DIR / "cofre.json"
ASSINATURAS_PATH = DADOS_DIR / "assinaturas.json"
CONTAS_EMAIL_PATH = DADOS_DIR / "contas_email.json"
ENVIOS_PATH = DADOS_DIR / "envios.json"
CLAUSULAS_PATH = DADOS_DIR / "clausulas.json"
CONEXOES_PATH = DADOS_DIR / "conexoes.json"
SESSOES_DIR = DADOS_DIR / "sessoes"
COMPROVANTES_DIR = DADOS_DIR / "comprovantes"
RECIBOS_DIR = DADOS_DIR / "recibos"
EXPORTACOES_DIR = DADOS_DIR / "exportacoes"
GRAVACOES_DIR = DADOS_DIR / "gravacoes"
# Os modelos baixados (voz, traducao): PAULUS_MODELOS no programa instalado
# (%LOCALAPPDATA%\PAULUS\modelos, que o lancador passa); sem ela, a pasta do
# codigo, compartilhada entre a base real e a de demonstracao.
MODELOS_DIR = Path(os.environ.get("PAULUS_MODELOS") or (BASE_DIR / "data" / "modelos")).resolve()
MODELOS_VOZ_DIR = MODELOS_DIR / "whisper"
# Os modelos do Ollama que o PAULUS baixou: o desinstalador le esta lista para
# perguntar se tira tambem os modelos de IA local (e so estes - o que a pessoa
# baixou por fora do PAULUS fica).
BAIXADOS_PELO_PAULUS_PATH = MODELOS_DIR / "ollama_baixados.txt"
LIXEIRA_DIR = DADOS_DIR / "lixeira"
MARCA_DIR = DADOS_DIR / "marca"
CONHECIMENTO_DIR = DADOS_DIR / "conhecimento"
MATERIAL_DIR = DADOS_DIR / "aprendizado"
MAX_AUDIO_BYTES = 500 * 1024 * 1024
RITMO_PATH = DADOS_DIR / "ritmo.json"
MEDIDAS_MODELOS_PATH = DADOS_DIR / "modelos_medidas.json"
# O teste desta maquina e as amostras de calibracao feitas aqui (src/maquina.py).
MAQUINA_PATH = DADOS_DIR / "maquina.json"
# De quanto em quanto tempo a vigia olha as pastas do Acervo.
VIGIA_SEGUNDOS = 30
CALIBRACAO_PATH = DADOS_DIR / "calibracao.json"
# As amostras de outras maquinas, quando se participa da calibracao.
CALIBRACAO_SERVIDOR_PATH = DADOS_DIR / "calibracao_servidor.json"
HABILIDADES_DIR = BASE_DIR / "habilidades"
FRONTEND_DIR = BASE_DIR / "frontend"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_CERTIFICADO_BYTES = 8 * 1024 * 1024


def _quem_sou() -> str:
    """O primeiro nome de quem usa esta maquina, para assinar a trilha."""
    nome = str((estado.prefs.dados.get("pessoa") or {}).get("nome", "")).strip()
    return nome.split(" ")[0] if nome else "você"


def _credenciais_oauth(provedor: str) -> dict:
    """
    Client ID (e, no Google, o secret) do aplicativo PAULUS - vem do codigo
    (src/oauth_app.py), igual em toda instalacao. Quem usa so faz login.
    """
    import oauth_app

    return oauth_app.credenciais(provedor)


def _como_pensou(conversa_id: str, cobertura: dict) -> dict:
    """
    C2 (`conversa.pensando`): a resposta guardada leva a contagem dos
    documentos sem trecho, e nao a lista (que chegava a 56 nomes), e as linhas
    do "ver detalhes", tiradas do registro da execucao (src/detalhes.py).
    """
    if not rotas_execucoes.ligada(estado, "pensando"):
        return cobertura
    cobertura = dict(cobertura)
    sem = cobertura.get("ignorados") or []
    if sem:
        cobertura["ignorados_n"] = len(sem)
        cobertura["ignorados"] = []
    execucao = estado.execucoes.da_conversa(conversa_id)
    if execucao is not None and not execucao.terminou:
        cobertura["detalhes"] = detalhes_mod.linhas(execucao.desde(0))
        cobertura["execucao_id"] = execucao.id
    return cobertura


def _registrar_suspeita(trabalho, pergunta: str, dados: dict) -> None:
    """A frase de injecao achada num trecho lido: na conversa e em data/cerca/suspeitas.jsonl."""
    try:
        pasta = DADOS_DIR / "cerca"
        pasta.mkdir(parents=True, exist_ok=True)
        with (pasta / "suspeitas.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"em": datetime.now().isoformat(timespec="seconds"), "conversa": trabalho.id,
                                "pergunta": pergunta[:300], **dados}, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _pausar_trabalho(trabalho) -> None:
    """A conversa que ficou no meio volta a "parada", com a etapa em curso parada."""
    for etapa in trabalho.etapas:
        if etapa.estado == EXECUTANDO:
            etapa.estado = PAUSADO
    if trabalho.estado == EXECUTANDO:
        trabalho.estado = PAUSADO


class Estado:
    """Indice em memoria, compartilhado entre as requisicoes."""

    def __init__(self) -> None:
        self.searcher = ContractSearcher(filtravel=True)
        self.pasta = CONTRACTS_DIR
        # O indice e relido por muita gente (a vigia das pastas, anexar,
        # organizar): um de cada vez. `lendo` e o andamento para a tela, e a
        # versao muda a cada releitura - a tela do Acervo sabe por ela que
        # precisa buscar de novo.
        self._trava_indice = threading.RLock()
        self.lendo: dict = {"andando": False}
        self.retrato = ""
        self.versao_do_acervo = 0
        self.porta = 8000
        # A chave da janela desta execucao (src/acesso/chave.py): sem ela,
        # a requisicao e de fora e o porteiro barra.
        self.acesso = ChaveLocal()
        # Quem abre a janela (src/desktop.py) diz como trazer ela para frente
        # e entregar um arquivo vindo do Explorer ("Perguntar ao PAULUS").
        # Sem janela (o programa no navegador), fica None.
        self.ao_pedido_externo = None
        # E como fechar a janela: a atualizacao passa a vez ao instalador e
        # fecha o PAULUS, para ele trocar os arquivos (src/desktop.py).
        self.ao_fechar = None
        self.client = LlamaClient()
        # Organizador: resultado da ultima varredura/classificacao, por caminho.
        self.encontrados: list[dict] = []
        self.classificacoes: dict[str, Classificacao] = {}
        # O fim da ultima organizacao (movidos, falhas, diario para desfazer):
        # quando o mover passa pela fila, e daqui que a tela tira o desfecho.
        self.ultima_organizacao: dict | None = None
        # Conversas persistidas e o interruptor "ir devagar".
        self.trabalhos = Trabalhos(TRABALHOS_DIR)
        # As respostas que rodam sem depender da janela (C1, src/execucoes.py):
        # o registro de cada uma fica em data/execucoes. Ao abrir, a resposta
        # que o programa fechado deixou pela metade entra na conversa como
        # texto parcial, marcado como interrompido.
        self.execucoes = execucoes_mod.Execucoes(DADOS_DIR / "execucoes")
        try:
            self.execucoes.recuperar_interrompidas(self.trabalhos, _pausar_trabalho)
            self.execucoes.compactar()
        except Exception:  # noqa: BLE001 - o registro velho nao impede o programa de abrir
            pass
        self.devagar = False
        # Levantado quando a pessoa pede para parar a leitura em andamento.
        self.cancelar = threading.Event()
        # O botao de parar da conversa: um sinal por resposta sendo escrita,
        # pelo id da conversa. Sai daqui quando a resposta termina.
        self.respondendo: dict[str, threading.Event] = {}
        # O andamento de verdade de cada resposta sendo escrita, para o cartao
        # de "Acontecendo agora": a fase, desde quando, a previsao de leitura
        # medida nesta maquina (quando ha) e as palavras ja escritas. So em
        # memoria - acabou a resposta, sai daqui.
        self.andamento: dict[str, dict] = {}
        # Habilidades carregadas da pasta do projeto, uma por arquivo.
        self.registro = registro.carregar(HABILIDADES_DIR)
        # Fila do que espera decisao humana, e as preferencias da casa.
        self.fila = fila_aprovacoes.Fila(APROVACOES_PATH)
        self.prefs = Preferencias(PREFERENCIAS_PATH)
        # O acesso de fora (src/acesso/): contas, sessoes e o portao de quem
        # chega pelo tunel. Desligado de fabrica.
        self.acesso_de_fora = AcessoDeFora(DADOS_DIR, self.prefs, self.acesso, fila=self.fila)
        # Base local: cadastros, tarefas e o que vier depois.
        self.base = Base(BASE_PATH)
        self.cadastros = Cadastros(self.base, SUGESTOES_IGNORADAS_PATH)
        self.tarefas = Tarefas(self.base)
        self.agenda = Agenda(self.base)
        # Certificado digital: o arquivo, o selo e o historico de assinaturas.
        self.cofre = certificado.Cofre(COFRE_PATH, CERTIFICADO_DIR)
        self.assinaturas = assinatura.Registro(ASSINATURAS_PATH)
        # Contas de e-mail e o historico do que ja saiu daqui.
        self.contas = correio_contas.Contas(CONTAS_EMAIL_PATH)
        self.contas.credenciais_oauth = _credenciais_oauth
        self.envios = correio.RegistroEnvios(ENVIOS_PATH)
        # O login com Google/Microsoft em andamento (um por vez).
        self.entrada_oauth: correio_oauth.Entrada | None = None
        # A conta Google alem do Gmail: Agenda, Meet e Drive (src/google_servicos.py).
        self.google = google_servicos.Google(self._token_google)
        # O Drive pela internet: as pastas escolhidas viram copia no Acervo.
        import drive_online

        self.drive_online = drive_online.EspelhoDoDrive(self.google, lambda: self.pasta, self.prefs,
                                                        ao_mudar=lambda: self.recarregar_em_segundo_plano())
        # A agenda lida e a de quem pede (E3b): o cache e por conta.
        self.google.quem = lambda: (lambda c: c.email if c else "")(self.conta_google())
        # Documentos de texto e planilhas, com historico de versoes.
        self.documentos = documento.Documentos(self.base)
        self.comentarios = documento.Comentarios(self.base)
        self.clausulas = documento.Clausulas(CLAUSULAS_PATH)
        # Os codigos oficiais em base local: citar vira consulta.
        self.leis = leis.Leis(self.base)
        # O que a pessoa marcou sobre cada documento da biblioteca.
        self.marcas = acervo.Marcas(self.base)
        # O que esta maquina ja mediu de si: quanto le e quanto escreve por
        # segundo. E daqui que sai o "leituras assim levaram ~70 s aqui".
        self.ritmo = ritmo_mod.Ritmo(RITMO_PATH)
        # A fila do modelo (src/fila_modelo.py): uma pergunta por vez, na
        # ordem de chegada, com a previsao tirada do ritmo medido aqui.
        self.fila_modelo = FilaDoModelo(
            segundos_por_resposta=lambda: self.ritmo.segundos_por_resposta(self.client.model))
        # Financeiro, bem-estar e conexoes; relatorios so le o que os outros gravaram.
        self.financeiro = financeiro.Financeiro(self.base)
        # A folha, as notas e os boletos: o escritorio por dentro.
        self.folha = escritorio.Folha(self.base)
        self.papeis = escritorio.PapeisFiscais(self.base)
        self.bem_estar = bemestar.BemEstar(self.base)
        # Avisos do Windows: olha os lembretes e o ciclo de foco no servidor,
        # para o aviso chegar com a janela minimizada ou noutra tela.
        self.vigia = avisos.Vigia(self.bem_estar, self.prefs, agenda=self.agenda)
        # Os avisos de evento (resposta, aprovacao, transcricao) leem daqui o
        # que esta ligado em Configuracoes.
        avisos.configurar(self.prefs)
        self.fila.ao_pedir = lambda p: avisos.avisar(
            "aprovacao", "Aprovação pendente", f"{p.titulo} — espera a sua confirmação em Aprovações.")
        # Servicos: as pastas de trabalho (docs/ui, A15).
        self.servicos = servicos_mod.Servicos(self.base, _quem_sou, lambda: self.pasta)
        # As horas por servico e o cronometro de cada pessoa (src/horas.py).
        import horas as _horas

        self.horas = _horas.Horas(self.base)
        # As publicacoes do DJEN pelas OABs acompanhadas (src/publicacoes.py).
        import publicacoes as _pub

        self.publicacoes = _pub.Publicacoes(self.base)
        # Gravacoes de audio, guardadas nesta maquina (docs/ui, A16).
        self.gravacoes = gravacoes_mod.Gravacoes(self.base, GRAVACOES_DIR)
        # Transcricao: o modelo de voz desta maquina e uma fila de fundo, um
        # audio por vez, porque o Whisper ocupa metade dos nucleos.
        voz = self.prefs.dados.get("voz") or {}
        self.transcritor = transcricao_mod.Transcritor(MODELOS_VOZ_DIR, modelo=voz.get("modelo") or transcricao_mod.PADRAO)
        self.fila_voz: "queue.Queue[int]" = queue.Queue()
        self.progresso_voz: dict[int, float] = {}
        self.transcrevendo: int | None = None
        self.erro_voz = ""
        # O download do modelo do assistente pelo cartao "falta baixar".
        self.puxando: dict | None = None
        # Os modelos do PAULUS (src/modelos.py): o download pela tela e a lista
        # do que esta instalado, lembrada por alguns segundos para a delegacao
        # nao perguntar ao Ollama a cada chamada.
        self.baixador = modelos_mod.Baixador(lambda: self.client.host)
        self._presentes: tuple[float, set[str] | None] = (0.0, None)
        # Sessoes de transcricao ao vivo (uma por gravacao em andamento).
        self.ao_vivo: dict[str, transcricao_mod.SessaoAoVivo] = {}
        # A camada de inteligencia de documentos: o que ja foi entendido de
        # cada documento, para nao entender de novo a cada pergunta. Com a
        # chave desligada ela devolve fallback na hora e nada muda.
        self.catalogo = Catalogo.carregar()
        # As opcoes do modelo vem do catalogo (perfil `conversa`), e por isso
        # o cliente e refeito aqui, depois de le-lo (src/inferencia.py).
        self.client = self.novo_cliente(self.client.model)
        # Uma linha por pergunta, local (src/medicao.py).
        self.medicao = Medicao(DADOS_DIR / "medicao",
                               ligada=lambda: bool((self.prefs.dados.get("ia") or {}).get("medir", True)),
                               digest=lambda modelo: self.client.digest(modelo))
        self.analisando = False
        self.saber = inteligencia.Saber(
            Biblioteca(CONHECIMENTO_DIR, self.base), self.catalogo,
            ligada=bool(self.prefs.dados.get("inteligencia", True)))
        # O que o escritorio ensinou com as proprias palavras (docs/ui, A13).
        self.contextos = contextos_mod.Contextos(self.base)
        # O material de consulta: PDFs e textos de referencia, com indice
        # proprio, separado do Acervo (src/material.py). Com a chave
        # `biblioteca.hibrida`, a busca dele e a hibrida (src/biblioteca).
        self._vetorizador_material = None
        self.material = material_mod.Material(
            MATERIAL_DIR, hibrida=lambda: bool(self.prefs.dados.get("biblioteca", {}).get("hibrida")),
            vetorizador=self.vetorizador_do_material, ceder=lambda: self.fila_modelo.ceder(limite_s=600),
            chaves=lambda: self.prefs.dados.get("biblioteca") or {})
        # As leis em casa, para a camada LEI da resposta (src/biblioteca/camadas.py).
        self.material.leis = self.leis
        # O modelo que le as obras (M5): o da tarefa `leitura` (src/modelos.py).
        self.material.cliente_leitura = lambda: self.cliente_para("leitura")
        # A foto de quem usa e a logo do escritorio (docs/ui, A13).
        self.marca = marca_mod.Marca(MARCA_DIR)
        # A lixeira: apagar guarda por 30 dias; o que venceu some ao abrir.
        self.lixeira = lixeira_mod.Lixeira(self.base, LIXEIRA_DIR)
        self.lixeira.esvaziar_vencidos()
        for id_ in self.gravacoes.pendentes():
            self.fila_voz.put(id_)
        threading.Thread(target=self._trabalhar_voz, name="voz", daemon=True).start()
        self.conexoes = conexoes.Conexoes(CONEXOES_PATH, SESSOES_DIR)
        self.relatorios = relatorios.Relatorios(
            self.base, fila=self.fila, assinaturas=self.assinaturas,
            envios=self.envios, bem_estar=self.bem_estar,
        )

    def _trabalhar_voz(self) -> None:
        """A fila de transcricao: pega uma gravacao, transcreve, guarda, avisa a trilha."""
        while True:
            id_ = self.fila_voz.get()
            # Enquanto alguem grava com transcricao ao vivo, a fila espera: o
            # texto que chega enquanto a pessoa fala vale mais que o de fundo.
            while any(not s.fechada for s in self.ao_vivo.values()):
                time.sleep(1)
            self.transcrevendo = id_
            self.progresso_voz[id_] = 0.0
            try:
                caminho = self.gravacoes.caminho(id_)
                if not caminho:
                    self.gravacoes.marcar_transcricao(id_, "erro", erro="o áudio não está mais no disco")
                    continue
                self.gravacoes.marcar_transcricao(id_, "transcrevendo")
                r = self.transcritor.transcrever(
                    caminho, progresso=lambda f, i=id_: self.progresso_voz.__setitem__(i, f))
                self.gravacoes.marcar_transcricao(id_, "pronta", trechos=r["trechos"], modelo=r["modelo"], tempo=r["tempo"])
                g = self.gravacoes.obter(id_)
                if g and g.get("servico_id"):
                    self.servicos.trilha(int(g["servico_id"]), "Gravação transcrita: " + g["titulo"], "Assistente")
                if g:
                    avisos.avisar("gravacao", "Transcrição pronta", g.get("titulo") or "Gravação")
            except Exception as exc:  # noqa: BLE001 - a fila nao pode morrer por um audio
                self.gravacoes.marcar_transcricao(id_, "erro", erro=str(exc)[:300])
            finally:
                self.progresso_voz.pop(id_, None)
                self.transcrevendo = None
                self.fila_voz.task_done()

    def conta_google(self):
        """
        A conta Google em uso. De fora, a da propria pessoa, quando ela
        conectou a dela (E3b); senao - e na janela do servidor - a escolhida
        em Conexoes ou a primeira do escritorio que entrou pelo Google.
        """
        pessoa = equipe.pessoa_da_vez()
        if pessoa is not None:
            propria = next((c for c in self.contas.itens if c.autenticacao == "google"
                            and int(c.dono or 0) == int(pessoa["conta_id"])), None)
            if propria:
                return propria
        preferida = str((self.prefs.dados.get("google") or {}).get("conta", "")).lower()
        contas = [c for c in self.contas.itens if c.autenticacao == "google" and not int(c.dono or 0)]
        return next((c for c in contas if c.email.lower() == preferida), contas[0] if contas else None)

    def _token_google(self) -> str:
        conta = self.conta_google()
        if not conta:
            raise google_servicos.ErroGoogle("nenhuma conta Google conectada: entre com o Google em E-mail › Contas")
        try:
            return self.contas.credencial(conta)
        except correio_oauth.ErroOAuth as exc:
            raise google_servicos.ErroGoogle(str(exc), status=401) from exc

    def google_tem(self, servico: str) -> bool:
        """Se a conta Google ja concedeu a permissao do servico (agenda, drive)."""
        conta = self.conta_google()
        return bool(conta and google_servicos.ESCOPOS.get(servico, "-") in conta.escopos.split())

    def prefs_google(self) -> dict:
        return dict(self.prefs.dados.get("google") or {})

    def pastas_do_acervo(self) -> list[Path]:
        """
        As pastas que o Acervo vigia: a do programa e as que a pessoa incluiu.
        Cada uma e lida onde esta - nada e movido nem copiado para dentro do
        PAULUS.
        """
        extras = [Path(p) for p in self.prefs.dados.get("pastas_acervo") or []]
        return [Path(self.pasta)] + [p for p in extras if p.is_dir()]

    def incluir_no_acervo(self, pasta: str | Path) -> bool:
        """
        Passa a vigiar `pasta`. Pasta ja vigiada (ou dentro de uma) nao entra
        de novo; pasta que CONTEM vigiadas passa a valer no lugar delas.
        """
        alvo = Path(pasta).resolve()
        for ja in self.pastas_do_acervo():
            ja = ja.resolve()
            if alvo == ja or ja in alvo.parents:
                return False
        extras = [e for e in (self.prefs.dados.get("pastas_acervo") or []) if alvo not in Path(e).resolve().parents]
        self.prefs.dados["pastas_acervo"] = extras + [str(alvo)]
        self.prefs.atualizar({})
        return True

    def tirar_pasta_do_acervo(self, pasta: str | Path) -> bool:
        """Deixa de vigiar a pasta. Nenhum arquivo e tocado."""
        alvo = chave_do_caminho(pasta)
        extras = list(self.prefs.dados.get("pastas_acervo") or [])
        ficam = [e for e in extras if chave_do_caminho(e) != alvo]
        if len(ficam) == len(extras):
            return False
        self.prefs.dados["pastas_acervo"] = ficam
        self.prefs.atualizar({})
        return True

    def fora_do_acervo(self) -> set[str]:
        """Os documentos que a pessoa tirou do Acervo: continuam no disco, so nao sao lidos."""
        return {chave_do_caminho(c) for c in self.prefs.dados.get("acervo_fora") or []}

    def tirar_documentos(self, caminhos: list[str]) -> int:
        atuais = list(self.prefs.dados.get("acervo_fora") or [])
        chaves = {chave_do_caminho(c) for c in atuais}
        novos = [str(Path(c)) for c in caminhos if chave_do_caminho(c) not in chaves]
        if novos:
            self.prefs.dados["acervo_fora"] = atuais + novos
            self.prefs.atualizar({})
        return len(novos)

    def devolver_documentos(self, caminhos: list[str]) -> int:
        voltam = {chave_do_caminho(c) for c in caminhos}
        atuais = list(self.prefs.dados.get("acervo_fora") or [])
        ficam = [c for c in atuais if chave_do_caminho(c) not in voltam]
        if len(ficam) != len(atuais):
            self.prefs.dados["acervo_fora"] = ficam
            self.prefs.atualizar({})
        return len(atuais) - len(ficam)

    def assinatura_das_pastas(self) -> str:
        """
        O retrato das pastas vigiadas: nome, tamanho e data de cada documento.
        So metadados do Windows - nada e aberto. Mudou o retrato, algo entrou,
        saiu ou foi alterado.
        """
        partes = []
        for arquivo in listar_arquivos(self.pastas_do_acervo(), self.fora_do_acervo()):
            try:
                st = arquivo.stat()
            except OSError:
                continue
            partes.append(f"{arquivo}|{st.st_size}|{st.st_mtime_ns}")
        return hashlib.sha1("\n".join(partes).encode("utf-8", "replace")).hexdigest()

    def recarregar_em_segundo_plano(self) -> bool:
        """Relê sem prender quem pediu. Já relendo, não começa outra."""
        if self.lendo.get("andando"):
            return False
        threading.Thread(target=self.recarregar, name="acervo-reler", daemon=True).start()
        return True

    def _vigiar(self) -> None:
        """
        A vigia das pastas: a cada meio minuto, o retrato delas. Mudou, relê.
        Arquivo que ja foi lido nao e lido de novo (o sha1 e lembrado por
        tamanho e data, e o texto fica no cache), entao reler custa o que
        entrou de novo.
        """
        while True:
            time.sleep(VIGIA_SEGUNDOS)
            try:
                if self.lendo.get("andando"):
                    continue
                retrato = self.assinatura_das_pastas()
                if retrato != self.retrato:
                    self.recarregar()
            except Exception:  # noqa: BLE001 - a vigia nao pode morrer
                pass

    def modelos_presentes(self, fresco: bool = False) -> set[str] | None:
        quando, nomes = self._presentes
        if fresco or time.time() - quando > 30:
            try:
                nomes = {m["nome"] for m in modelos_mod.instalados(self.client.host)}
            except Exception:  # noqa: BLE001 - Ollama fora: "nao sei"
                nomes = None
            self._presentes = (time.time(), nomes)
        return nomes

    def modelo_para(self, tarefa: str) -> str:
        return modelos_mod.modelo_da_tarefa(tarefa, self.prefs.dados.get("tarefas_modelo") or {},
                                            self.client.model, self.modelos_presentes())

    def busca_por_sentido(self, esperar: bool = False):
        """
        (indice, vetorizador) da busca por sentido (I7, src/denso.py), com o
        backfill do que falta ja andando - ou (None, None) sem o modelo de
        vetores instalado ou com `ia.denso` desligada. O modelo so chega pelo
        download que a pessoa pede em Configuracoes > Modelos.
        """
        if not (self.prefs.dados.get("ia") or {}).get("denso", True):
            return None, None
        presentes = self.modelos_presentes() or set()
        if not any(n.split(":")[0] == denso_mod.MODELO for n in presentes):
            return None, None
        if getattr(self, "_denso", None) is None:
            self._denso = denso_mod.IndiceDenso(DADOS_DIR / "indice" / "densos.db")
            self._vetorizador = denso_mod.Vetorizador(self.client.host)
            self.backfill = denso_mod.Backfill(self._denso, self._vetorizador,
                                               ceder=lambda: self.fila_modelo.ceder(limite_s=600))
        self.backfill.iniciar(self.searcher.chunks)
        if esperar:
            self.backfill.esperar()
        return self._denso, self._vetorizador

    def vetorizador_do_material(self):
        """
        O bge-m3 para o material de consulta (src/biblioteca/indice.py), com as
        mesmas condicoes do Acervo: `ia.denso` ligada e o modelo baixado. Sem
        ele, o material fica so com a busca lexica.
        """
        if not (self.prefs.dados.get("ia") or {}).get("denso", True):
            return None
        presentes = self.modelos_presentes() or set()
        if not any(n.split(":")[0] == denso_mod.MODELO for n in presentes):
            return None
        if self._vetorizador_material is None:
            self._vetorizador_material = denso_mod.Vetorizador(self.client.host)
        return self._vetorizador_material

    def preparar_biblioteca(self, esperar: bool = False) -> dict:
        """O indice do material montado e os vetores andando (tools/medir.py espera)."""
        return self.material.preparar(esperar=esperar)

    def recuperar(self, pergunta: str, documentos=None) -> list:
        """Os trechos para o modelo pela busca hibrida (src/recuperacao.py)."""
        denso, vetorizador = self.busca_por_sentido()
        return recuperacao_mod.recuperar(self.searcher, pergunta, denso=denso, vetorizador=vetorizador,
                                         documentos=documentos)

    def indice_lexico(self):
        """O FTS5 do Acervo (src/lexico.py), aberto uma vez; sem ele, o BM25 de antes."""
        if getattr(self, "_lexico", None) is None:
            try:
                self._lexico = IndiceLexico(DADOS_DIR / "indice" / "lexico.db")
            except Exception:  # noqa: BLE001 - sem o indice em disco, a busca de antes serve
                return None
        return self._lexico

    def novo_cliente(self, modelo: str) -> LlamaClient:
        """Um cliente para `modelo`, com as opcoes do catalogo e das preferencias."""
        host = getattr(getattr(self, "client", None), "host", None) or DEFAULT_HOST
        return LlamaClient(model=modelo, host=host,
                           opcoes=inferencia.opcoes(self.catalogo, self.prefs.dados, modelo))

    def cliente_para(self, tarefa: str) -> LlamaClient:
        """
        O cliente do modelo que faz a tarefa. O padrao e o proprio
        `self.client`; outro modelo ganha um cliente com as opcoes dele - a
        janela e por modelo (src/inferencia.py).
        """
        nome = self.modelo_para(tarefa)
        if nome == self.client.model:
            return self.client
        return self.novo_cliente(nome)

    def recarregar(self, *, force: bool = False) -> int:
        with self._trava_indice:
            self.lendo = {"andando": True, "feitos": 0, "total": 0, "nome": ""}

            def andou(feitos: int, total: int, nome: str) -> None:
                self.lendo.update(feitos=feitos, total=total, nome=nome)

            try:
                retrato = self.assinatura_das_pastas()
                docs = index_all_contracts(self.pastas_do_acervo(), CACHE_PATH, force=force, verbose=False,
                                           ignorar=self.fora_do_acervo(), progresso=andou)
            finally:
                self.lendo = {"andando": False}
            # I5: trechos pela estrutura (clausula, secao, artigo), com id
            # estavel e pagina - chave `ia.trechos_estruturais`. I6: o indice
            # lexico em disco (FTS5), incremental - chave `ia.lexico_fts`.
            ia = self.prefs.dados.get("ia") or {}
            searcher = ContractSearcher(
                filtravel=True,
                estrutural=bool(ia.get("trechos_estruturais", True)),
                lexico=self.indice_lexico() if ia.get("lexico_fts", True) else None)
            searcher.add_contracts(docs)
            searcher.build()
            self.searcher = searcher
            self.retrato = retrato
            self.versao_do_acervo += 1

        # I7: os vetores do que entrou ou mudou, em segundo plano, cedendo a
        # vez para as perguntas - so com o modelo de vetores instalado.
        try:
            self.busca_por_sentido()
        except Exception:  # noqa: BLE001 - sem vetores, a busca lexica serve
            pass

        # A janela NAO acompanha mais o acervo (I1): cada mudanca dela fazia o
        # Ollama recarregar o modelo na pergunta seguinte. Ela e fixa por
        # modelo (src/inferencia.py); o que nao cabe nela passa pela busca.

        # HOOK 1: o que entrou vai ser entendido uma vez, em segundo plano.
        # Nao bloqueia a indexacao e nao altera arquivo nenhum; se falhar, o
        # programa continua exatamente como era - documento sem metadata
        # responde pelo caminho de sempre.
        self.analisar_em_segundo_plano(docs)
        return len(docs)

    def analisar_em_segundo_plano(self, docs) -> None:
        if not self.saber.ligada or self.analisando:
            return

        def trabalhar() -> None:
            self.analisando = True
            try:
                for doc in docs:
                    try:
                        analise = inteligencia.analisar_documento(
                            self.saber.biblioteca, self.catalogo, doc.path,
                            texto=doc.text, paginas=doc.pages, sha1=doc.sha1, titulo=doc.name)
                    except Exception:
                        continue   # um documento torto nao para o acervo
                    # I9: os prazos conferidos viram proposta em Aprovacoes
                    # (uma vez por prazo; nada vai para a Agenda sem o sim).
                    try:
                        rotas_ajuda.propor_prazos(self, analise.metadata, doc.name)
                    except Exception:  # noqa: BLE001 - propor e ajuda, nao pode travar a leitura
                        pass
            finally:
                self.analisando = False

        threading.Thread(target=trabalhar, daemon=True).start()


estado = Estado()


@asynccontextmanager
async def lifespan(app: FastAPI):
    estado.pasta.mkdir(parents=True, exist_ok=True)
    total = estado.recarregar()
    estado.vigia.comecar()
    threading.Thread(target=estado._vigiar, name="acervo-vigia", daemon=True).start()
    threading.Thread(target=_verificar_atualizacao_se_velha, name="atualizacao", daemon=True).start()
    threading.Thread(target=_backup_automatico, name="backup", daemon=True).start()
    threading.Thread(target=_publicacoes_automatico, name="publicacoes", daemon=True).start()
    threading.Thread(target=_drive_online_automatico, name="drive-online", daemon=True).start()
    threading.Thread(target=processos_mod.vigiar, args=(estado,), name="processos", daemon=True).start()
    # A Constituição, os códigos e as súmulas que vêm no instalador (src/biblioteca/nativo.py).
    threading.Thread(target=rotas_biblioteca.instalar_na_abertura, args=(estado, DADOS_DIR),
                     name="acervo-inicial", daemon=True).start()
    print(f"\n  PAULUS Legal - servidor em 127.0.0.1:{estado.porta}")
    print(f"  {total} contrato(s) carregado(s) de {estado.pasta}\n")
    # O acesso de fora ligado e conectado: o tunel sobe junto com o programa
    # (src/acesso/servico.py). Em segundo plano - ler a versao do cloudflared
    # e abrir a porta do tunel nao pode atrasar a janela.
    threading.Thread(target=estado.acesso_de_fora.iniciar, name="acesso-de-fora", daemon=True).start()
    # W1: a porta HTTPS do painel do Word, se ligado e instalado.
    threading.Thread(target=estado.word_instalacao.aplicar, name="porta-do-word", daemon=True).start()
    yield
    estado.vigia.parar()
    estado.acesso_de_fora.parar()
    estado.word_instalacao.fechar()


app = FastAPI(title="PAULUS Legal", docs_url="/api/docs", lifespan=lifespan)


@app.exception_handler(FilaCheia)
async def _fila_cheia(request, exc):
    """F1: qualquer tela que chamou o modelo com duas perguntas da pessoa esperando."""
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=429, content={"detail": str(exc)})
# O porteiro vem antes de tudo: separa a janela local (chave ou cookie da
# sessao local) de quem chega de fora. Quem chega de fora passa pelo portao
# do acesso remoto - desligado, ninguem passa.
# O PAULUS vinculado a conta Google (E5, src/vinculo.py): travado, a janela
# do servidor so alcanca a tela de destravar.
import vinculo as vinculo_mod  # noqa: E402

estado.vinculo = vinculo_mod.Vinculo(estado.prefs, estado.acesso_de_fora.contas, lambda: _credenciais_oauth("google"))
estado.acesso_de_fora.vinculo = estado.vinculo
estado.vinculo.ligar_servicos = lambda tokens, email, nome: estado.contas.ligar_oauth("google", email, nome, tokens)
# Cada login da conta vinculada diz ao Worker de que conta e o endereco do
# acesso de fora (quando conectado): e o que deixa retomar depois de reinstalar.
# A tela da trava diz se o acesso de fora continua (ele nao passa pela trava).
estado.vinculo.situacao_de_fora = lambda: {k: estado.acesso_de_fora.situacao().get(k) for k in ("ligado", "estado", "hostname")}
estado.vinculo.ao_confirmar = lambda token: estado.acesso_de_fora.conexao.informar_dono(token) \
    if getattr(estado.acesso_de_fora, "conexao", None) else None
vinculo_mod.montar(app, estado.vinculo)


class PortaDosServicos:
    """
    Servicos por colaborador (src/servicos_acesso.py). Por dentro do porteiro,
    que ja sabe quem e a pessoa da vez: para quem entra de fora e nao e
    titular, calcula os servicos que ela nao ve e (1) responde 404 a quem pede
    um deles pelo endereco - servico, gravacao, tarefa ou compromisso dele -, e
    (2) poe o filtro da requisicao: as listagens (servicos, tarefas, agenda,
    gravacoes) e o Acervo (a pasta de cada servico fechado, tambem na busca e
    no assistente) so devolvem o resto.
    """

    ITENS = (
        (re.compile(r"^/api/servicos/(\d+)(?:/|$)"), None),
        (re.compile(r"^/api/gravacoes/(\d+)(?:/|$)"), "SELECT servico_id FROM gravacoes WHERE id = ?"),
        (re.compile(r"^/api/tarefas/(\d+)(?:/|$)"), "SELECT servico_id FROM tarefas WHERE id = ?"),
        (re.compile(r"^/api/agenda/(\d+)(?:/|$)"), "SELECT servico_id FROM compromissos WHERE id = ?"),
    )

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        sessao = equipe.pessoa_da_vez() if scope.get("type") == "http" else None
        if not servicos_acesso.restrita(sessao):
            await self.app(scope, receive, send)
            return
        fechados = servicos_acesso.ocultos(estado.base, estado.acesso_de_fora.contas, sessao)
        caminho = scope.get("path", "")
        for padrao, sql in self.ITENS:
            m = padrao.match(caminho)
            if not m:
                continue
            alvo = int(m.group(1))
            if sql:
                linha = estado.base.um(sql, (alvo,))
                alvo = int((linha or {}).get("servico_id") or 0)
            if alvo and alvo in fechados:
                corpo = json.dumps({"detail": "não encontrado"}).encode("utf-8")
                await send({"type": "http.response.start", "status": 404,
                            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(corpo)).encode())]})
                await send({"type": "http.response.body", "body": corpo})
                return
        pastas = [p for p in (estado.servicos.pasta_de(i, criar=False) for i in fechados) if p]
        f = search_mod.FILTRO.set(servicos_acesso.predicado_de_pastas(pastas))
        o = servicos_acesso.OCULTOS.set(frozenset(fechados))
        try:
            await self.app(scope, receive, send)
        finally:
            search_mod.FILTRO.reset(f)
            servicos_acesso.OCULTOS.reset(o)


# F1: quem pede ao modelo (dono, primeiro nome, a tela). Por dentro do
# porteiro, que e quem diz se o pedido e de fora.
app.add_middleware(fila_de_todos.QuemPedeAoModelo,
                   nome_local=lambda: ((estado.prefs.dados.get("pessoa") or {}).get("nome") or ""))
app.add_middleware(PortaDosServicos)
# O servidor MCP das leis (ideia A do umbrelOS, src/mcp_leis.py): o /mcp tem
# token e travas proprios, e o porteiro o entrega antes da chave da janela.
estado.mcp = mcp_leis.ServidorMCP(
    leis=estado.leis, conexoes=mcp_leis.Conexoes(DADOS_DIR),
    ligado=lambda: bool((estado.prefs.dados.get("umbrel") or {}).get("mcp")),
    registrar=estado.acesso_de_fora.auditoria.registrar, versao=VERSAO, estado=estado)
# W1: o suplemento do Word (src/word_suplemento.py) - o painel, o pareamento e
# as rotas com token entram pelo porteiro antes da chave da janela.
word_suplemento.montar(estado, app, DADOS_DIR)
estado.app_para_word = app
app.add_middleware(Porteiro, chave=estado.acesso, remoto=estado.acesso_de_fora.portao,
                   travado=lambda: estado.vinculo.travado(), mcp=lambda: estado.mcp,
                   word=lambda: getattr(estado, "word", None))
rotas_do_acesso.montar(estado.acesso_de_fora, app)
estado.acesso_de_fora.portao.rotas = app.router
estado.acesso_de_fora.app = app
# O assistente de conexao (R7): pedir o endereco ao Worker de paulus.ia.br,
# esperar o titular confirmar, e depois manter a lista de e-mails.
estado.acesso_de_fora.conexao = ConexaoDoTunel(estado.acesso_de_fora)


def _ligar_google_da_pessoa(conta_id: int, email: str, nome: str, dados: dict):
    """
    O Google de uma pessoa da equipe, autorizado de fora (E3b): vira uma conta
    de e-mail dela (dono = a conta do acesso), entrando pelo cliente web - e a
    Agenda e o Drive dela vem na mesma autorizacao.
    """
    tokens = {"access_token": dados.get("access_token", ""), "refresh_token": dados.get("refresh_token", ""),
              "expira_em": time.time() + float(dados.get("expires_in") or 3600), "scope": dados.get("scope", "")}
    return estado.contas.ligar_oauth("google", email, nome, tokens, dono=int(conta_id), cliente="google_web")


def _google_da_pessoa(conta_id: int) -> str:
    """
    O Google de trabalho da pessoa: o que ela conectou de fora (dono = a conta)
    ou, se nao, a conta de e-mail do escritorio com o mesmo endereco com que
    ela entra - o titular que vinculou o PAULUS ja conectou o proprio Gmail.
    """
    c = next((c for c in estado.contas.itens if c.autenticacao == "google" and int(c.dono or 0) == int(conta_id)), None)
    if c is None:
        conta = estado.acesso_de_fora.contas.obter(int(conta_id)) or {}
        email = str(conta.get("email") or "").lower()
        c = next((x for x in estado.contas.itens if x.autenticacao == "google" and x.email.lower() == email), None) if email else None
    return c.email if c else ""


estado.acesso_de_fora.ligar_google = _ligar_google_da_pessoa
estado.acesso_de_fora.google_da_pessoa = _google_da_pessoa
rotas_do_tunel.montar(estado.acesso_de_fora, estado.acesso_de_fora.conexao, app)
# "Quem acessou" (R8): a tela e o PDF, so na janela local.
rotas_da_auditoria.montar(estado.acesso_de_fora, app)
# A ajuda sem pergunta (I9): cartao do documento, correcao, prazos.
rotas_ajuda.montar(estado, app, DADOS_DIR)
rotas_biblioteca.montar(estado, app, DADOS_DIR)
# F1: a fila do modelo a vista e a pergunta que espera na conversa (src/fila_de_todos.py).
fila_modelo.instalar(estado.fila_modelo, lambda: fila_de_todos.ligada(estado))
fila_de_todos.montar(estado, app, lambda request: _dono_da_vez(request), lambda **campos: Pergunta(**campos))
# D1: o pacote de escrita e a porta do aparelho (src/aparelho.py).
aparelho_mod.montar(estado, app, DADOS_DIR)
# D2: o motor que escreve no aparelho - a biblioteca, os pesos e a capacidade (src/aparelho_motor.py).
aparelho_motor.montar(estado, app, DADOS_DIR)
# L1: aprender com o uso - 👍/👎, o caderno de falhas e o caso de teste (src/aprendizado.py).
aprendizado_mod.montar(estado, app, DADOS_DIR)
captura_mod.montar(estado, app, DADOS_DIR)
mcp_leis.montar(estado, app)
rotas_chaves.montar(estado, app)
rotas_execucoes.montar(estado, app)
rotas_conversa.montar(estado, app)
saudacao_mod.montar(estado, app, rotas_do_acesso.pessoa)
agente_mod.montar(estado, app)
# C5: o parecer, o resumo da gravacao e o reescrever do e-mail como execucao,
# com a vez na fila do modelo (src/ia_em_fundo.py). As funcoes sao as rotas de
# antes: o resultado e o mesmo JSON.
ia_em_fundo.montar(estado, app, {
    "parecer": ("Parecer do Financeiro", lambda d: "parecer:" + str(d.get("quando", "")),
                lambda d: relatorios_parecer(d)),
    "resumo_gravacao": ("Resumo da gravação", lambda d: "gravacao:" + str(d.get("id", "")),
                        lambda d: gravacoes_resumo(int(d.get("id") or 0))),
    "reescrever_email": ("Reescrever o e-mail", lambda d: "email:rascunho", lambda d: email_reescrever(d)),
}, lambda request: _dono_da_vez(request))
# Os agentes do escritorio (A1): os arquivos e as rotas (a A2 os poe na conversa).
rotas_agentes.montar(estado, app, DADOS_DIR / "agentes", contexto=lambda tarefa: _contexto(tarefa=tarefa))
# A tela de agentes (A3): os exemplos do produto, o formulario e o rascunho da conversa.
agentes_tela.montar(estado, app)
# A Central de avisos (T2): o carrossel da tela inicial e o historico do visto.
rotas_avisos.montar(estado, app, lambda: _documentos_com_data())
# L2: o acompanhamento de processos pelo DataJud (src/processos.py) - depois da Central,
# que ganha a fonte das movimentacoes novas.
processos_mod.montar(estado, app)
# L3: visao por cliente, parte contraria e conflito de interesse (src/clientes.py).
clientes_mod.montar(estado, app)
# L4: tarefas de varios passos, com ponto de restauracao (src/passos.py).
passos_mod.montar(estado, app, DADOS_DIR)
# L5: fundamentacao sugerida, temas do STJ e posicao da casa (src/fundamentacao.py).
fundamentacao_mod.montar(estado, app)
# L9: materiais entre advogados, pelo site (src/comunidade.py).
comunidade_mod.montar(estado, app)
# L10: a vigencia de cada artigo, dispositivo por dispositivo (src/vigencia.py).
vigencia_mod.montar(estado, app)
# N13: os acordaos do STJ no computador, baixados so quando a pessoa pede (src/jurisprudencia.py).
jurisprudencia_mod.montar(estado, app, DADOS_DIR)
# N15: a nuvem com a chave do escritorio (src/nuvem.py, rotas em src/rotas_nuvem.py).
import rotas_nuvem  # noqa: E402

rotas_nuvem.montar(estado, app, DADOS_DIR)


def _descrever_para_auditoria(caminho: str) -> str:
    """
    O que o endereco da API significa, para quem le "quem acessou": o nome do
    documento, da planilha, da gravacao, da conversa ou do arquivo, e o
    formato. Sem traducao, fica o endereco - melhor que nada.
    """
    from urllib.parse import parse_qs, urlsplit

    partes = urlsplit(caminho)
    rota, consulta = partes.path, parse_qs(partes.query)
    try:
        m = re.match(r"^/api/(documentos|planilha|gravacoes|trabalhos)/(\w+)(?:/(\w+)(?:\.(\w+))?)?", rota)
        if m:
            tipo, id_, parte, extensao = m.groups()
            if tipo in ("documentos", "planilha"):
                item = estado.documentos.obter(int(id_)) or {}
                nome = item.get("titulo") or f"documento {id_}"
            elif tipo == "gravacoes":
                nome = (estado.gravacoes.obter(int(id_)) or {}).get("titulo") or f"gravação {id_}"
            else:
                t = estado.trabalhos.obter(id_)
                nome = ("conversa " + t.titulo) if t else f"conversa {id_}"
            formato = (consulta.get("formato") or [""])[0] or extensao or (parte if parte in ("pdf", "docx", "audio") else "")
            return f"“{nome}”" + (f" ({formato.upper()})" if formato else "")
        for chave in ("caminho", "nome", "arquivo"):
            if consulta.get(chave):
                return f"“{Path(consulta[chave][0]).name}”"
    except Exception:  # noqa: BLE001 - a auditoria nunca deixa de anotar por causa do nome
        pass
    return caminho


estado.acesso_de_fora.descrever = _descrever_para_auditoria
# Garantia a mais: o processo do tunel nunca sobrevive ao programa, nem
# quando o fechamento nao passa pelo fim do servidor.
import atexit  # noqa: E402

atexit.register(estado.acesso_de_fora.parar)


def cabecalho_local() -> dict:
    """O cabecalho de quem fala com este servidor de dentro do mesmo processo (roteiro, testes)."""
    return estado.acesso.cabecalho()


@app.exception_handler(Exception)
async def _erro_inesperado(request: Request, exc: Exception):
    """
    O erro que escapou de uma rota: fica anotado para a Saude e o diagnostico
    (src/saude.py - sem a mensagem, que pode trazer nome de cliente) e a tela
    recebe uma frase, em vez de uma resposta vazia.
    """
    import saude

    rota = getattr(request.scope.get("route"), "path", "") or request.url.path.split("?")[0]
    saude.anotar_erro(f"{request.method} {rota}", exc)
    return JSONResponse(status_code=500, content={
        "detail": "algo deu errado no PAULUS ao fazer isso. Se continuar, gere o diagnóstico em Configurações › Desempenho"})


@app.exception_handler(nomes_mod.NomeRepetido)
def _nome_repetido(_request: Request, exc: nomes_mod.NomeRepetido) -> Response:
    """Arquivo de mesmo nome sem decisao: nada foi gravado, a tela pergunta
    (Renomear / Substituir) e manda de novo com as decisoes (src/nomes.py)."""
    corpo = {"detail": "já existe um arquivo com esse nome", "conflitos": exc.conflitos}
    return Response(json.dumps(corpo, ensure_ascii=False), status_code=409, media_type="application/json")


# ------------------------------------------------------------------ modelos


class Pergunta(BaseModel):
    pergunta: str
    top: int = 6
    # A2: o agente que a pessoa escolheu na barra (slug), ou "nao usar".
    agente: str = ""
    sem_agente: bool = False
    # Os documentos que a tela diz estarem em foco - as pilulas do compositor,
    # postas pelo "/", por anexar, ou por ter perguntado sobre eles. Vem da
    # tela porque e o que a pessoa esta VENDO; adivinhar pelo texto quando a
    # tela ja mostra a resposta seria trocar uma certeza por um palpite.
    #
    # Lista porque anexar dois arquivos e perguntar sobre "eles" e o caso
    # comum - quem arrasta um contrato e o aditivo quer os dois lidos juntos.
    apenas: list[str] = []
    # "olha o acervo inteiro", dito pelo botao em vez de pela frase.
    tudo: bool = False
    # A pilula da caixa em "pergunto onde procurar": sem documento nomeado, a
    # conversa pergunta onde antes de sair lendo o acervo inteiro.
    sem_anexo: bool = False
    # O botao Retomar do cartao "Parado": a mesma pergunta de novo, sem
    # repeti-la no historico e trocando a resposta que parou no meio.
    retomar: bool = False
    # O botao "Procurar nos documentos" do cartao da camada do programa: a
    # pessoa disse que a pergunta era sobre os documentos, e a camada nao
    # decide de novo.
    documentos: bool = False
    # O botao "ler o documento inteiro" do cartao de resposta sem fundamento
    # (I8): esta pergunta le o escopo inteiro, mesmo com a leitura por trechos.
    inteiro: bool = False
    # F1: Ctrl+Enter - com prioridade na fila do modelo (src/fila_de_todos.py).
    prioridade: bool = False
    # D1: escrever a resposta no aparelho de quem pergunta (src/aparelho.py).
    aparelho: bool = False
    # N15: a pessoa marcou "Nuvem" (src/nuvem.py) - cada envio espera o sim.
    nuvem: bool = False
    # D4: como a pessoa decidiu no seletor, quando a resposta e do escritorio
    # ("escritorio", "fila", "automatico") - so para a resposta dizer por que.
    escolha: str = ""


class Busca(BaseModel):
    termo: str
    top: int = 8


# ------------------------------------------------------------------- rotas


SEM_CACHE = {"Cache-Control": "no-cache"}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html", headers=SEM_CACHE)


def _arquivo_do_frontend(pasta: str, arquivo: str, tipo: str) -> FileResponse:
    """
    Um arquivo de frontend/css ou frontend/js. O nome vem da propria pagina;
    ainda assim, nada de subir pastas. "no-cache" faz o navegador embutido
    conferir a data a cada abertura: sem isso, um CSS trocado so aparecia
    depois de limpar o WebView2.
    """
    alvo = (FRONTEND_DIR / pasta / Path(arquivo).name).resolve()
    if alvo.parent != (FRONTEND_DIR / pasta).resolve() or not alvo.exists():
        raise HTTPException(status_code=404, detail="arquivo nao encontrado")
    return FileResponse(alvo, media_type=tipo, headers=SEM_CACHE)


@app.get("/css/{arquivo}")
def css_da_pagina(arquivo: str) -> FileResponse:
    return _arquivo_do_frontend("css", arquivo, "text/css")


@app.get("/js/{arquivo}")
def js_da_pagina(arquivo: str) -> FileResponse:
    return _arquivo_do_frontend("js", arquivo, "text/javascript")


@app.get("/favicon.ico")
def favicon() -> FileResponse:
    # O navegador pede /favicon.ico por conta propria (a aba, o historico, a
    # tela de entrar de fora): o mesmo "P" do programa, e nao a tela de entrar.
    return FileResponse(FRONTEND_DIR / "img" / "paulus.ico", media_type="image/x-icon")


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


@app.get("/img/marcas/{arquivo}")
def imagem_de_marca(arquivo: str) -> FileResponse:
    """Os logos dos fabricantes de modelo (assistente de configuracao), so .svg."""
    pasta = (FRONTEND_DIR / "img" / "marcas").resolve()
    alvo = (pasta / Path(arquivo).name).resolve()
    if alvo.parent != pasta or alvo.suffix != ".svg" or not alvo.exists():
        raise HTTPException(status_code=404, detail="imagem nao encontrada")
    return FileResponse(alvo, media_type="image/svg+xml")


# ------------------------------------------------------------------- cache


class LimparCache(BaseModel):
    classificacao: bool = False


@app.post("/api/cache/limpar")
def cache_limpar(payload: LimparCache) -> dict:
    """
    Apaga o que foi guardado para nao refazer trabalho.

    Sao dois caches, e eles custam coisas diferentes para refazer. O da
    extracao e o texto tirado de cada PDF: volta sozinho na proxima leitura,
    so demora. O da classificacao e o que o MODELO decidiu sobre cada
    documento - tipo, partes, datas -, e refazer aquilo e rodar o modelo de
    novo em tudo, o que nesta maquina leva minutos por documento. Por isso o
    segundo so vai embora quando a pessoa marca, e a tela diz o preco.
    """
    sumiu, apagados = 0, []
    alvos = [("extração", CACHE_PATH)]
    if payload.classificacao:
        alvos.append(("classificação", CLASSIFICACAO_PATH))
    for rotulo, caminho in alvos:
        if caminho.exists():
            sumiu += caminho.stat().st_size
            try:
                caminho.unlink()
            except OSError as exc:
                raise HTTPException(status_code=500, detail=f"nao consegui apagar o cache de {rotulo}: {exc}") from exc
            apagados.append(rotulo)

    if not apagados:
        return {"apagados": [], "mb": 0, "aviso": "o cache já estava vazio"}

    mb = round(sumiu / 1024 / 1024, 1)
    aviso = "cache de " + " e de ".join(apagados) + " apagado"
    aviso += f" · {mb} MB liberados" if mb >= 0.1 else " · era menos de 0,1 MB"
    return {"apagados": apagados, "mb": mb, "aviso": aviso,
            "refaz": "os documentos são lidos de novo no próximo Reindexar"}


# --------------------------------------------------------------- novidades

NOVIDADES_PATH = BASE_DIR / "docs" / "NOVIDADES.md"


@app.get("/api/novidades")
def novidades() -> dict:
    """
    O que mudou no programa, escrito para quem usa.

    Sai de um arquivo do proprio repositorio, e nao de um servidor: o
    programa nao busca nada na internet, e a lista de novidades de uma versao
    e da versao - ela chega junto com o programa, nao depois dele.
    """
    if not NOVIDADES_PATH.exists():
        return {"blocos": [], "aviso": "ainda não há lista de novidades nesta instalação"}

    blocos: list[dict] = []
    intro: list[str] = []
    for linha in NOVIDADES_PATH.read_text(encoding="utf-8").splitlines():
        crua = linha.rstrip()
        if crua.startswith("## "):
            blocos.append({"titulo": crua[3:].strip(), "itens": []})
        elif crua.startswith("- ") and blocos:
            blocos[-1]["itens"].append(crua[2:].strip())
        elif crua.startswith("  ") and crua.strip() and blocos and blocos[-1]["itens"]:
            # Continuacao da linha anterior: o arquivo quebra em 80 colunas.
            blocos[-1]["itens"][-1] += " " + crua.strip()
        elif crua and not crua.startswith("#") and not blocos:
            intro.append(crua.strip())
    return {"blocos": blocos, "intro": " ".join(intro)}


# --------------------------------------------------------------- contextos


class NovoContexto(BaseModel):
    id: int | None = None
    titulo: str = ""
    texto: str = ""
    gaveta: str = ""


@app.get("/api/contextos")
def contextos_listar() -> dict:
    return estado.contextos.para_tela()


@app.post("/api/contextos")
def contextos_salvar(payload: NovoContexto) -> dict:
    try:
        id_ = estado.contextos.salvar(payload.model_dump(), payload.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": id_, **estado.contextos.para_tela()}


# Arquivo de onde se aprende: ate aqui de tamanho, e so o que da para ler.
MAX_ENSINAR_BYTES = 20 * 1024 * 1024
FORMATOS_ENSINAR = (".pdf", ".docx", ".txt", ".md")


@app.post("/api/contextos/ler")
async def contextos_ler_arquivo(arquivo: UploadFile = File(...)) -> dict:
    """
    Le um arquivo e propoe o lembrete - sem guardar nada.

    A tela promete "eu leio, resumo em contextos curtos e MOSTRO antes de
    guardar", e e o que acontece: o que volta daqui vai para os campos do
    formulario, onde a pessoa corrige e confirma. O arquivo nao entra no
    Acervo nem fica no disco; o que sobra dele, se a pessoa guardar, sao as
    quatro linhas que ela leu antes.
    """
    nome = Path(arquivo.filename or "").name
    if not nome:
        raise HTTPException(status_code=400, detail="arquivo sem nome")
    if Path(nome).suffix.lower() not in FORMATOS_ENSINAR:
        raise HTTPException(status_code=400,
                            detail="dá para ler PDF, DOCX, TXT e MD; imagem ainda não")
    dados = await arquivo.read(MAX_ENSINAR_BYTES + 1)
    if len(dados) > MAX_ENSINAR_BYTES:
        raise HTTPException(status_code=413, detail="esse arquivo passa de 20 MB")

    def ler() -> tuple[str, int]:
        # Em pasta temporaria: os leitores trabalham sobre caminho, e o
        # arquivo nao tem por que ficar no computador depois disto.
        with tempfile.TemporaryDirectory() as tmp:
            alvo = Path(tmp) / nome
            alvo.write_bytes(dados)
            return extract_file(alvo)

    try:
        texto, paginas = await run_in_threadpool(ler)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"não consegui ler esse arquivo: {exc}") from exc

    texto = " ".join((texto or "").split())
    if len(texto) < 40:
        raise HTTPException(
            status_code=422,
            detail="esse arquivo não tem texto para ler — se for um PDF digitalizado, passe o OCR antes")

    disponivel, motivo = check_ollama(estado.client.model)
    if not disponivel:
        # Sem modelo, ainda da para ensinar: o comeco do documento vai para o
        # campo e a pessoa escreve a regra com as palavras dela. Dizer isso e
        # melhor que devolver erro e deixar o arquivo sem serventia.
        return {"titulo": contextos_mod.titulo_do_arquivo(nome), "texto": texto[:contextos_mod.MAX_TEXTO],
                "de": nome, "paginas": paginas, "pelo_modelo": False,
                "aviso": f"{motivo} — trouxe o começo do arquivo para você resumir com as suas palavras"}

    try:
        resposta = await run_in_threadpool(
            lambda: estado.cliente_para("redacao").ask(contextos_mod.INSTRUCAO_DO_ARQUIVO,
                                      f"Documento “{nome}”:\n{texto[:contextos_mod.LEITURA_MAX]}",
                                      sistema=contextos_mod.INSTRUCAO_DO_ARQUIVO))
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    sugestao = " ".join(_limpar_sugestao(resposta).split())[:contextos_mod.MAX_TEXTO]
    if not sugestao:
        sugestao = texto[:contextos_mod.MAX_TEXTO]
    return {"titulo": contextos_mod.titulo_do_arquivo(nome), "texto": sugestao,
            "de": nome, "paginas": paginas, "pelo_modelo": True,
            "aviso": "li o arquivo e escrevi isto — confira antes de guardar"}


@app.delete("/api/contextos/{id_}")
def contextos_apagar(id_: int) -> dict:
    item = estado.contextos.obter(id_)
    if not item:
        raise HTTPException(status_code=404, detail="esse lembrete nao existe")
    entrada = estado.lixeira.apagar_linha("contexto", id_, item["titulo"], item["gaveta"])
    return {**_foi_para_lixeira(entrada, "contexto", id_), **estado.contextos.para_tela()}


# ------------------------------------------------- material de consulta


@app.get("/api/material")
def material_listar() -> dict:
    return estado.material.para_tela()


@app.post("/api/material")
async def material_enviar(arquivos: list[UploadFile] = File(...)) -> dict:
    """
    O escritorio entrega um PDF (ou DOCX, TXT, MD) para o PAULUS aprender.

    Aprender, aqui, e o que src/material.py diz: o texto e lido uma vez,
    guardado nesta maquina com a pagina de cada trecho, e consultado em cada
    pergunta da conversa. Um arquivo que nao deu para ler volta com o motivo,
    sem derrubar os outros do mesmo envio.
    """
    # Com `biblioteca.triagem`, cada arquivo passa pela triagem da Biblioteca
    # (src/biblioteca/triagem.py): o CDC em PDF vai para as leis em casa, e o
    # resto ganha a ficha para conferir.
    entraram, recusados, leis_guardadas, avisos = [], [], [], []
    for arquivo in arquivos:
        nome = Path(arquivo.filename or "").name or "material"
        dados = await arquivo.read(material_mod.MAX_BYTES + 1)
        try:
            feito = await run_in_threadpool(rotas_biblioteca.receber, estado, DADOS_DIR, nome, dados)
        except ValueError as exc:
            recusados.append({"nome": nome, "motivo": str(exc)})
            continue
        if feito.get("mensagem"):
            avisos.append({"nome": nome, "mensagem": feito["mensagem"]})
        if feito["destino"] == "lei":
            leis_guardadas.append({"nome": nome, **feito.get("lei", {})})
        else:
            entraram.append({**feito["item"], "triagem": feito.get("triagem") or {}})
    if not entraram and not leis_guardadas and recusados:
        raise HTTPException(status_code=400, detail=f"{recusados[0]['nome']}: {recusados[0]['motivo']}")
    return {"entraram": entraram, "recusados": recusados, "leis": leis_guardadas, "avisos": avisos,
            **estado.material.para_tela()}


@app.delete("/api/material/{id_}")
def material_remover(id_: str) -> dict:
    if not estado.material.remover(id_):
        raise HTTPException(status_code=404, detail="esse material não existe mais")
    return estado.material.para_tela()


@app.post("/api/material/{id_}/abrir")
def material_abrir(id_: str) -> dict:
    """Abre o arquivo original no programa padrao do Windows."""
    alvo = estado.material.caminho(id_)
    if not alvo:
        raise HTTPException(status_code=404, detail="o arquivo desse material saiu do lugar")
    import os

    os.startfile(str(alvo))  # noqa: S606 - abre no programa do proprio Windows
    return {"aberto": str(alvo)}


# ------------------------------------------------- o que ja foi lido


@app.get("/api/inteligencia")
def inteligencia_situacao() -> dict:
    """
    Quanto do acervo ja foi entendido, e quanto isso esta economizando.

    Sem medicao o retrofit e fe: a tela mostra quantos documentos tem
    metadata, o que cada secao rendeu e a proporcao de perguntas respondidas
    sem abrir documento. Tudo medido nesta maquina, nada estimado.
    """
    situacao = estado.saber.biblioteca.situacao()
    total = len(estado.searcher.documents)
    return {
        "ligada": estado.saber.ligada,
        "analisando": estado.analisando,
        "documentos": situacao["documentos"],
        "no_acervo": total,
        "secoes": situacao["secoes"],
        "medicao": estado.saber.medicao(),
        "catalogo": {
            "arquivo": str(estado.catalogo.caminho.name),
            "problemas": estado.catalogo.problemas(),
            "extratores": [
                {"secao": e.secao, "id": e.id, "nivel": e.nivel, "modelo": e.modelo}
                for e in (estado.catalogo.para_secao(s)
                          for s in estado.catalogo.secoes_declaradas())
                if e is not None
            ],
        },
        "pasta": str(CONHECIMENTO_DIR),
    }


# ------------------------------------------------------------------- marca


@app.get("/marca/{tipo}.png")
def marca_imagem(tipo: str) -> FileResponse:
    """
    A foto ou a logo, para a tela desenhar.

    Sem cache: a imagem troca no lugar, com o mesmo endereco. O `?v=` que a
    tela manda ja resolveria, mas quem abre o endereco direto tambem tem de
    ver a atual.
    """
    alvo = estado.marca.caminho(tipo)
    if not alvo:
        raise HTTPException(status_code=404, detail="essa imagem nao foi enviada")
    return FileResponse(alvo, media_type="image/png", headers=SEM_CACHE)


@app.post("/api/marca/{tipo}")
async def marca_enviar(tipo: str, arquivo: UploadFile = File(...)) -> dict:
    """A imagem escolhida vira um PNG pequeno em data/marca."""
    dados = await arquivo.read(marca_mod.MAX_BYTES + 1)
    try:
        item = await run_in_threadpool(estado.marca.guardar, tipo, dados)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"tipo": tipo, **item, "marca": estado.marca.info()}


@app.delete("/api/marca/{tipo}")
def marca_tirar(tipo: str) -> dict:
    if tipo not in marca_mod.TIPOS:
        raise HTTPException(status_code=404, detail="imagem desconhecida")
    tirou = estado.marca.tirar(tipo)
    return {"tirou": tirou, "marca": estado.marca.info()}


@app.get("/api/status")
def status() -> dict:
    ok, mensagem = check_ollama(estado.client.model)
    return {
        "ollama": ok,
        "mensagem": mensagem,
        "motor": _motor(mensagem),
        "modelo": estado.client.model,
        # A interface nunca mostra o nome do modelo (regra de linguagem do
        # manual): mostra "Assistente local - X GB na sua maquina".
        "tamanho_gb": _tamanho_do_modelo(),
        "pasta": str(estado.pasta),
        "contratos": len(estado.searcher.documents),
        "trechos": len(estado.searcher.chunks),
        "versao": VERSAO,
        # A pasta do programa: instalado, a de Programs (o app fica em
        # <pasta>/app); rodando do codigo, a do repositorio.
        "programa": str(BASE_DIR.parent if os.environ.get("PAULUS_INSTALADO") else BASE_DIR),
    }


# Tamanho aproximado dos modelos que o programa sugere, para o cartao de
# "falta baixar" dizer quanto vem antes de a pessoa clicar.
TAMANHOS_MODELO = {"llama3.2:3b": "2,0 GB", "llama3.2:1b": "1,3 GB", "llama3.1:8b": "4,9 GB", "qwen2.5:3b": "1,9 GB", "gemma2:2b": "1,6 GB"}


def _ollama_exe() -> str | None:
    """O executavel do Ollama: no PATH ou onde o instalador do Windows o poe."""
    achado = shutil.which("ollama")
    if achado:
        return achado
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    return str(local) if local.exists() else None


def _motor(mensagem: str = "") -> dict:
    """
    Em que pe esta o motor, para o cartao de erro (docs/ui/05) dizer a coisa
    certa: nao instalado, desligado, ou ligado sem o modelo.
    """
    try:
        modelos = estado.client.list_models()
        rodando = True
    except Exception:  # noqa: BLE001 - sem servidor e um estado, nao um erro
        modelos, rodando = [], False
    nome = estado.client.model
    presente = nome in modelos or any(m.split(":")[0] == nome.split(":")[0] and ":" not in nome for m in modelos)
    return {
        "instalado": bool(_ollama_exe()) or rodando,
        "rodando": rodando,
        "modelo_presente": presente,
        "modelo": nome,
        "tamanho": TAMANHOS_MODELO.get(nome, ""),
        "mensagem": mensagem,
        "puxando": estado.puxando or _puxando_pelo_baixador(),
        # C3: o endereco de verdade, para o modo de diagnostico do painel (o
        # HTML dizia "127.0.0.1" fixo, errado com outro OLLAMA_HOST).
        "host": str(getattr(estado.client, "host", "")).replace("http://", "").replace("https://", ""),
    }


@app.post("/api/ollama/ligar")
def ollama_ligar() -> dict:
    """
    "Ligar agora" do cartao de erro: abre o servidor do Ollama daqui, sem
    terminal, e espera ate 20 s por ele. Se ja estiver de pe, so confere.
    """
    exe = _ollama_exe()
    if not exe:
        raise HTTPException(status_code=503, detail="O Ollama não está instalado nesta máquina")
    ok, _ = check_ollama(estado.client.model)
    if not ok:
        try:
            estado.client.list_models()
        except Exception:  # noqa: BLE001 - e isso que estamos tratando
            try:
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
                # Na pasta do proprio Ollama: ele segue rodando depois que o
                # PAULUS fecha, e com a pasta de trabalho herdada prendia a
                # pasta do programa - o instalador nao conseguia atualizar.
                subprocess.Popen([exe, "serve"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, creationflags=flags, cwd=str(Path(exe).parent))
            except OSError as exc:
                raise HTTPException(status_code=503, detail="não consegui abrir o Ollama: " + str(exc)) from exc
            limite = time.time() + 20
            while time.time() < limite:
                try:
                    estado.client.list_models()
                    break
                except Exception:  # noqa: BLE001 - ainda subindo
                    time.sleep(0.5)
    ok, mensagem = check_ollama(estado.client.model)
    return {"ligado": ok, "mensagem": mensagem, "motor": _motor(mensagem)}


@app.post("/api/ollama/puxar")
def ollama_puxar() -> dict:
    """Baixa o modelo do assistente em segundo plano (`ollama pull`), com o andamento em /api/ollama/puxar."""
    exe = _ollama_exe()
    if not exe:
        raise HTTPException(status_code=503, detail="O Ollama não está instalado nesta máquina")
    if estado.puxando and estado.puxando.get("andando"):
        return estado.puxando
    estado.puxando = {"modelo": estado.client.model, "progresso": 0, "andando": True, "erro": "", "pronto": False, "linha": ""}
    andamento = estado.puxando

    def puxar() -> None:
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            p = subprocess.Popen([exe, "pull", andamento["modelo"]], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, creationflags=flags, text=True, encoding="utf-8", errors="replace")
            pedaco = ""
            while True:
                ch = p.stdout.read(1)
                if not ch:
                    break
                if ch in "\r\n":
                    linha = pedaco.strip()
                    pedaco = ""
                    if linha:
                        andamento["linha"] = linha[:120]
                        achado = re.search(r"(\d{1,3})%", linha)
                        if achado:
                            andamento["progresso"] = int(achado.group(1))
                else:
                    pedaco += ch
            if p.wait() == 0:
                andamento["progresso"] = 100
                andamento["pronto"] = True
                _anotar_baixado(andamento["modelo"])
                _medir_para_calibracao(andamento["modelo"])
            else:
                andamento["erro"] = "o download parou: " + (andamento["linha"] or "sem detalhe")
        except Exception as exc:  # noqa: BLE001 - o erro vai para a tela
            andamento["erro"] = str(exc)[:200]
        finally:
            andamento["andando"] = False

    threading.Thread(target=puxar, name="ollama-pull", daemon=True).start()
    return andamento


@app.get("/api/ollama/puxar")
def ollama_puxando() -> dict:
    return estado.puxando or _puxando_pelo_baixador() or {"andando": False, "progresso": 0, "pronto": False, "erro": ""}


def _puxando_pelo_baixador() -> dict | None:
    """
    O download do modelo padrao feito pelo Baixador (Configuracoes › Modelos,
    ou a escolha do instalador), no formato do cartao do Assistente - sem
    isso, o cartao dizia "Falta baixar" com o download ja andando.
    """
    b = estado.baixador.andamento()
    if not b.get("andando") or b.get("modelo") != estado.client.model:
        return None
    linha = str(b.get("fase", "")) + (f" · {b.get('baixado_gb', 0)} de {b.get('total_gb', 0)} GB" if b.get("total_gb") else "")
    return {"modelo": b["modelo"], "andando": True, "progresso": b.get("progresso", 0), "pronto": False, "erro": "",
            "linha": linha.replace(".", ",")}


def _anotar_baixado(nome: str) -> None:
    """Guarda que o PAULUS baixou este modelo no Ollama (para o desinstalador)."""
    try:
        ja = set(BAIXADOS_PELO_PAULUS_PATH.read_text(encoding="utf-8").split()) if BAIXADOS_PELO_PAULUS_PATH.exists() else set()
        if nome and nome not in ja:
            BAIXADOS_PELO_PAULUS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(BAIXADOS_PELO_PAULUS_PATH, "a", encoding="utf-8") as f:
                f.write(nome + "\n")
    except OSError:
        pass


def _usar_e_baixar(modelo: str, baixar: bool) -> None:
    """
    O modelo escolhido no assistente de configuracao (passo Modelo de IA):
    vira o padrao e, se a pessoa pediu e ele ainda nao esta aqui, o download
    comeca - com o Ollama ligado daqui, se estiver desligado. O andamento
    aparece no cartao do Assistente e em Configuracoes › Modelos.
    """
    try:
        preferencias_gravar({"modelo": modelo})
    except Exception:  # noqa: BLE001 - sem o padrao gravado, a pessoa escolhe em Configuracoes
        return
    if not baixar:
        return
    try:
        ollama_ligar()
        instalados = {m["nome"] for m in modelos_mod.instalados(estado.client.host)}
    except Exception:  # noqa: BLE001 - Ollama ausente: o cartao do Assistente diz como seguir
        return
    if modelo in instalados:
        return
    try:
        estado.baixador.iniciar(modelo, ao_terminar=_terminou_de_baixar)
    except (ValueError, RuntimeError):
        pass


# ------------------------------------------------------------- atualizacao

ATUALIZACAO_DIR = DADOS_DIR / "atualizacao"
ANUNCIO_PATH = ATUALIZACAO_DIR / "anuncio.json"
_baixador_atualizacao = atualizacao_mod.Baixador(ATUALIZACAO_DIR)


def _prefs_atualizacao() -> dict:
    return estado.prefs.dados.get("atualizacoes") or {}


def _anuncio() -> dict | None:
    try:
        a = json.loads(ANUNCIO_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    # A versao pode ter mudado desde a consulta (atualizou): "nova" e de agora.
    a["nova"] = atualizacao_mod.mais_nova(a.get("versao", ""), VERSAO)
    return a


def _consultar_atualizacao() -> dict:
    """Le o anuncio do site, guarda, e - sem aviso antes - ja baixa."""
    try:
        anuncio = atualizacao_mod.consultar(VERSAO)
    except Exception as exc:  # noqa: BLE001 - sem internet, fica o anuncio de antes
        estado.prefs.atualizar({"atualizacoes": {"erro": "não consegui ver se há versão nova: " + str(exc)[:160],
                                                 "ultima_consulta": time.strftime("%Y-%m-%d %H:%M")}})
        return atualizacao_situacao()
    ATUALIZACAO_DIR.mkdir(parents=True, exist_ok=True)
    ANUNCIO_PATH.write_text(json.dumps(anuncio, ensure_ascii=False, indent=1), encoding="utf-8")
    estado.prefs.atualizar({"atualizacoes": {"erro": "", "ultima_consulta": anuncio["consultado_em"]}})
    if anuncio["nova"] and atualizacao_mod.instalado() and not _prefs_atualizacao().get("avisar_antes", True):
        try:
            _baixador_atualizacao.iniciar(anuncio)
        except RuntimeError:
            pass
    return atualizacao_situacao()


def _verificar_atualizacao_se_velha(espera: float = 30.0) -> None:
    """Uma vez por dia, se a pessoa deixou ligado. Espera o programa abrir antes."""
    time.sleep(espera)
    p = _prefs_atualizacao()
    if not p.get("verificar", True):
        return
    ultima = p.get("ultima_consulta", "")
    try:
        velha = not ultima or time.time() - time.mktime(time.strptime(ultima, "%Y-%m-%d %H:%M")) > atualizacao_mod.UM_DIA
    except ValueError:
        velha = True
    if velha:
        _consultar_atualizacao()


@app.get("/api/atualizacao")
def atualizacao_situacao() -> dict:
    p = _prefs_atualizacao()
    anuncio = _anuncio()
    pronto = bool(anuncio and anuncio.get("nova") and _baixador_atualizacao.pronto_para(anuncio))
    return {"atual": VERSAO, "instalado": atualizacao_mod.instalado(), "verificar": bool(p.get("verificar", True)),
            "avisar_antes": bool(p.get("avisar_antes", True)), "ultima_consulta": p.get("ultima_consulta", ""),
            "erro": p.get("erro", ""), "anuncio": anuncio, "baixando": _baixador_atualizacao.andamento(),
            "pronto": pronto, "endereco": atualizacao_mod.URL}


@app.post("/api/atualizacao/verificar")
def atualizacao_verificar() -> dict:
    return _consultar_atualizacao()


@app.post("/api/atualizacao/baixar")
def atualizacao_baixar() -> dict:
    anuncio = _anuncio()
    if not anuncio or not anuncio.get("nova"):
        raise HTTPException(status_code=409, detail="não há versão nova para baixar")
    try:
        _baixador_atualizacao.iniciar(anuncio)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return atualizacao_situacao()


@app.post("/api/atualizacao/cancelar")
def atualizacao_cancelar() -> dict:
    _baixador_atualizacao.cancelar()
    return atualizacao_situacao()


@app.post("/api/atualizacao/instalar")
def atualizacao_instalar() -> dict:
    """
    Abre o instalador conferido no modo atualizar e fecha o PAULUS: o
    instalador troca os arquivos e abre a versao nova no fim.
    """
    if not atualizacao_mod.instalado():
        raise HTTPException(status_code=409, detail="rodando do código-fonte: para atualizar, use git pull")
    anuncio = _anuncio()
    arquivo = _baixador_atualizacao.pronto_para(anuncio) if anuncio and anuncio.get("nova") else None
    if not arquivo:
        raise HTTPException(status_code=409, detail="a atualização ainda não foi baixada e conferida")
    atualizacao_mod.abrir_instalador(arquivo, atualizacao_mod.pasta_do_programa(BASE_DIR), calado=False)
    if estado.ao_fechar:
        threading.Timer(1.5, estado.ao_fechar).start()
    return {"instalando": anuncio["versao"]}


def instalar_atualizacao_ao_fechar() -> bool:
    """
    Chamado pelo desktop.py quando a janela fecha: sem "avisar antes", a
    versao nova ja baixada e conferida se instala agora, sem janela.
    """
    if not atualizacao_mod.instalado() or _prefs_atualizacao().get("avisar_antes", True):
        return False
    anuncio = _anuncio()
    arquivo = _baixador_atualizacao.pronto_para(anuncio) if anuncio and anuncio.get("nova") else None
    if not arquivo:
        return False
    atualizacao_mod.abrir_instalador(arquivo, atualizacao_mod.pasta_do_programa(BASE_DIR), calado=True)
    return True


@app.post("/api/modelos/usar")
def modelos_usar(payload: dict) -> dict:
    """
    Usa este modelo como padrao e, com `baixar`, baixa se faltar. Responde na
    hora: ligar o Ollama e comecar o download acontecem por tras.
    """
    nome = str(payload.get("nome", "")).strip().lower()
    if not modelos_mod.nome_valido(nome):
        raise HTTPException(status_code=400, detail="nome de modelo inválido")
    threading.Thread(target=_usar_e_baixar, args=(nome, bool(payload.get("baixar"))),
                     name="usar-modelo", daemon=True).start()
    return {"modelo": nome, "baixar": bool(payload.get("baixar"))}


# ------------------------------------------------------------ os modelos

def _medidas_dos_modelos() -> dict:
    try:
        return json.loads(MEDIDAS_MODELOS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@app.get("/api/modelos")
def modelos_listar() -> dict:
    """
    O que a tela de modelos mostra: os instalados (com o que cada um faz e a
    medida nesta maquina), o catalogo com o tamanho lido do registro, as
    tarefas com o modelo de cada uma e o download em andamento.
    """
    try:
        lista = modelos_mod.instalados(estado.client.host)
        rodando = True
    except Exception:  # noqa: BLE001 - Ollama fora e um estado da tela
        lista, rodando = [], False
    presentes = {m["nome"] for m in lista}
    estado._presentes = (time.time(), presentes if rodando else None)
    delegados = estado.prefs.dados.get("tarefas_modelo") or {}
    medidas = _medidas_dos_modelos()
    padrao = estado.client.model
    for m in lista:
        m["padrao"] = m["nome"] == padrao
        m["tarefas"] = [t for t in modelos_mod.IDS_TAREFAS if delegados.get(t) == m["nome"]]
        m["medida"] = medidas.get(m["nome"])
    tamanhos = modelos_mod.tamanhos_do_catalogo()
    catalogo = [{**c, "gb": tamanhos.get(c["nome"]), "instalado": c["nome"] in presentes} for c in modelos_mod.CATALOGO]
    tarefas = [{"id": t, "rotulo": r, "explica": e, "modelo": delegados.get(t) or "",
                "em_uso": modelos_mod.modelo_da_tarefa(t, delegados, padrao, presentes if rodando else None)}
               for t, r, e in modelos_mod.TAREFAS]
    # A estimativa de cada um nesta maquina e a nota no banco de provas: so
    # quando a maquina ja foi testada (o teste leva segundos e roda na
    # primeira abertura, ou pelo botao da tela).
    recomendacao = _recomendacao(lista if rodando else None, testar=False)
    if recomendacao:
        por_nome = {x["nome"]: x for x in recomendacao["modelos"]}
        for m in lista + catalogo:
            x = por_nome.get(m["nome"])
            if x:
                m["estimativa"] = x["estimativa"]
                m["qualidade"] = x["qualidade"]
                m["recomendado"] = x["recomendado"]
    # A busca por sentido (I7): o modelo de vetores e o andamento dos vetores
    # do Acervo. Fica fora da lista de modelos de conversa - ele nao responde
    # pergunta, e nao pode ser escolhido para uma tarefa.
    busca = {"modelo": denso_mod.MODELO, "gb": denso_mod.GB_APROX,
             "instalado": any(m["nome"].split(":")[0] == denso_mod.MODELO for m in lista),
             "ligada": bool((estado.prefs.dados.get("ia") or {}).get("denso", True)),
             "trechos": sum(1 for c in estado.searcher.chunks if c.chunk_id)}
    if busca["instalado"] and getattr(estado, "_denso", None) is not None:
        busca["vetores"] = estado._denso.quantos()
        busca["andamento"] = dict(estado.backfill.estado)
    lista = [m for m in lista if m["nome"].split(":")[0] != denso_mod.MODELO]
    return {"rodando": rodando, "padrao": padrao, "instalados": lista, "catalogo": catalogo, "busca": busca,
            "tarefas": tarefas, "baixando": estado.baixador.andamento(),
            "maquina": (recomendacao or {}).get("maquina"), "recomendado": (recomendacao or {}).get("recomendado", ""),
            "porque": (recomendacao or {}).get("porque", "")}


@app.post("/api/modelos/baixar")
def modelos_baixar(payload: dict) -> dict:
    nome = str(payload.get("nome", "")).strip().lower()
    try:
        return estado.baixador.iniciar(nome, ao_terminar=_terminou_de_baixar)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/modelos/baixar")
def modelos_baixando() -> dict:
    return estado.baixador.andamento()


@app.post("/api/modelos/cancelar")
def modelos_cancelar() -> dict:
    return estado.baixador.cancelar()


@app.post("/api/modelos/remover")
def modelos_remover(payload: dict) -> dict:
    """Tira o modelo do Ollama. O padrao nao sai; tarefa delegada a ele volta ao padrao."""
    nome = str(payload.get("nome", "")).strip()
    if nome == estado.client.model:
        raise HTTPException(status_code=409, detail="esse é o modelo padrão - escolha outro padrão antes de remover")
    try:
        modelos_mod.remover(estado.client.host, nome)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail="não consegui falar com o Ollama") from exc
    delegados = dict(estado.prefs.dados.get("tarefas_modelo") or {})
    soltos = [t for t, m in delegados.items() if m == nome]
    if soltos:
        estado.prefs.atualizar({"tarefas_modelo": {t: "" for t in soltos}})
    estado.modelos_presentes(fresco=True)
    return {"removido": nome, "tarefas_de_volta_ao_padrao": soltos}


@app.post("/api/modelos/padrao")
def modelos_padrao(payload: dict) -> dict:
    """O modelo padrao: o que faz toda tarefa sem modelo proprio."""
    nome = str(payload.get("nome", "")).strip()
    presentes = estado.modelos_presentes(fresco=True)
    if presentes is not None and nome not in presentes:
        raise HTTPException(status_code=404, detail="esse modelo não está instalado")
    return preferencias_gravar({"modelo": nome})


@app.post("/api/modelos/tarefa")
def modelos_tarefa(payload: dict) -> dict:
    """Delega uma tarefa a um modelo. Vazio devolve a tarefa ao padrao."""
    tarefa = str(payload.get("tarefa", ""))
    nome = str(payload.get("modelo", "")).strip()
    if tarefa not in modelos_mod.IDS_TAREFAS:
        raise HTTPException(status_code=400, detail="tarefa desconhecida")
    presentes = estado.modelos_presentes(fresco=True)
    if nome and presentes is not None and nome not in presentes:
        raise HTTPException(status_code=404, detail="esse modelo não está instalado")
    estado.prefs.atualizar({"tarefas_modelo": {tarefa: nome}})
    return {"tarefa": tarefa, "modelo": nome, "em_uso": estado.modelo_para(tarefa)}


@app.post("/api/modelos/medir")
def modelos_medir(payload: dict) -> dict:
    """Mede o modelo nesta maquina e guarda (data/modelos_medidas.json)."""
    nome = str(payload.get("nome", "")).strip()
    try:
        return _medir_e_guardar(nome)
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail="o Ollama não respondeu: " + str(exc)[:120]) from exc


def _terminou_de_baixar(nome: str) -> None:
    """Um modelo terminou de baixar: fica anotado (desinstalador) e, com a calibracao ligada, e medido."""
    _anotar_baixado(nome)
    estado.modelos_presentes(fresco=True)
    _medir_para_calibracao(nome)


_medindo_para_calibracao: set[str] = set()


def _medir_para_calibracao(nome: str, espera: float = 20.0) -> bool:
    """
    A avaliacao desta maquina para o servidor do PAULUS (a calibracao, com
    a chave ligada): o modelo que acabou de baixar - ou o padrao, ao ligar
    a chave - e medido uma vez, sozinho, e a amostra vai para o servidor.
    Sem isto, a amostra so saia de quem clicava em Medir, e quem so ligava
    a chave no assistente nao mandava nada. Espera uns segundos antes, para
    nao disputar com o que a pessoa estiver fazendo logo depois do download.
    Devolve se a medida foi agendada.
    """
    if not nome or not _participa_da_calibracao() or nome in _medidas_dos_modelos() or nome in _medindo_para_calibracao:
        return False
    _medindo_para_calibracao.add(nome)

    def trabalho() -> None:
        try:
            time.sleep(espera)
            if _participa_da_calibracao() and nome not in _medidas_dos_modelos():
                _medir_e_guardar(nome)
                print(f"  calibracao: {nome} medido e enviado")
        except Exception as exc:  # noqa: BLE001 - sem a medida, a calibracao so fica sem esta amostra
            print(f"  calibracao: nao consegui medir {nome}: {exc}")
        finally:
            _medindo_para_calibracao.discard(nome)

    threading.Thread(target=trabalho, name="medir-para-calibracao", daemon=True).start()
    return True


def _medir_e_guardar(nome: str) -> dict:
    medida = modelos_mod.medir(estado.client.host, nome)
    medidas = _medidas_dos_modelos()
    medidas[nome] = medida
    MEDIDAS_MODELOS_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEDIDAS_MODELOS_PATH.write_text(json.dumps(medidas, ensure_ascii=False, indent=1), encoding="utf-8")
    # A medida vira amostra de calibracao desta maquina: a estimativa dos
    # outros modelos passa a se corrigir por ela (src/maquina.py).
    try:
        info = next((m for m in modelos_mod.instalados(estado.client.host) if m["nome"] == nome), None)
        if info:
            nova = maquina_mod.amostra(_maquina(), info, medida)
            maquina_mod.guardar_amostra(CALIBRACAO_PATH, nova)
            if _participa_da_calibracao():
                _calibracao_em_segundo_plano(_enviar_calibracao, [nova])
    except Exception:  # noqa: BLE001 - a medida ja foi guardada; a amostra e um extra
        pass
    return {"nome": nome, "medida": medida}


# ----------------------------------------------------- esta maquina

_trava_maquina = threading.Lock()


def _maquina(fresco: bool = False, testar: bool = True) -> dict | None:
    """
    O teste desta maquina (src/maquina.py), guardado em data/maquina.json.
    Roda uma vez; de novo so pelo botao, ou quando o teste mudou de versao.
    A memoria livre e lida na hora: e a unica coisa que muda de minuto a minuto.
    """
    with _trava_maquina:
        dados = None
        if not fresco:
            try:
                dados = json.loads(MAQUINA_PATH.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                dados = None
            if dados and dados.get("versao") != maquina_mod.VERSAO_DO_TESTE:
                dados = None
        if dados is None:
            if not testar:
                return None
            dados = maquina_mod.testar()
            MAQUINA_PATH.parent.mkdir(parents=True, exist_ok=True)
            MAQUINA_PATH.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        import psutil

        dados["ram_livre_gb"] = round(psutil.virtual_memory().available / 1e9, 1)
    except Exception:  # noqa: BLE001
        pass
    return dados


def _recomendacao(instalados: list[dict] | None = None, testar: bool = True) -> dict | None:
    """
    Cada modelo (os do catalogo e os instalados) com a estimativa nesta
    maquina e a nota no banco de provas, e o recomendado.
    """
    maq = _maquina(testar=testar)
    if maq is None:
        return None
    if instalados is None:
        try:
            instalados = modelos_mod.instalados(estado.client.host)
        except Exception:  # noqa: BLE001 - sem Ollama, estima so o catalogo
            instalados = []
    tamanhos = modelos_mod.tamanhos_do_catalogo()
    modelos, vistos = [], set()
    for m in instalados:
        if m.get("gb"):
            modelos.append({"nome": m["nome"], "gb": m["gb"], "parametros": m.get("parametros", ""),
                            "quantizacao": m.get("quantizacao", ""), "instalado": True})
            vistos.add(m["nome"])
    for c in modelos_mod.CATALOGO:
        if c["nome"] not in vistos:
            modelos.append({"nome": c["nome"], "gb": tamanhos.get(c["nome"]) or c["gb_aprox"], "parametros": c["parametros"],
                            "quantizacao": c["quantizacao"], "instalado": False})
    amostras = maquina_mod.ler_amostras(maquina_mod.BASE_PATH) + maquina_mod.ler_amostras(CALIBRACAO_PATH)
    if _participa_da_calibracao():
        _ler_calibracao_se_velha()
        de_fora, _ = calibracao_remota.ler_guardadas(CALIBRACAO_SERVIDOR_PATH)
        amostras += calibracao_remota.plausiveis(de_fora, maquina_mod.calibrar(amostras))
    calib = maquina_mod.calibrar(amostras)
    correcao = maquina_mod.correcao_local(maq, calib, amostras)
    r = maquina_mod.recomendar(modelos, maq, calib, correcao, modelos_mod.QUALIDADE, _medidas_dos_modelos())
    r["maquina"] = maq
    r["calibracao"] = {"amostras": calib["amostras"], "maquinas": calib["maquinas"], "medidos_aqui": correcao["medidos"]}
    return r


def _participa_da_calibracao() -> bool:
    return bool((estado.prefs.dados.get("calibracao") or {}).get("participar"))


def _calibracao_em_segundo_plano(funcao, *args) -> None:
    def trabalhar() -> None:
        try:
            funcao(*args)
            estado.prefs.atualizar({"calibracao": {"erro": ""}})
        except calibracao_remota.ErroCalibracao as exc:
            estado.prefs.atualizar({"calibracao": {"erro": str(exc)}})

    threading.Thread(target=trabalhar, name="calibracao", daemon=True).start()


def _enviar_calibracao(amostras: list[dict]) -> None:
    calibracao_remota.enviar(amostras, VERSAO)
    estado.prefs.atualizar({"calibracao": {"ultimo_envio": time.strftime("%Y-%m-%d %H:%M")}})


def _baixar_calibracao() -> None:
    calibracao_remota.baixar(CALIBRACAO_SERVIDOR_PATH)
    estado.prefs.atualizar({"calibracao": {"ultima_leitura": time.strftime("%Y-%m-%d %H:%M")}})


def _ler_calibracao_se_velha() -> None:
    """Uma leitura por dia basta: as medidas de outras maquinas mudam devagar."""
    ultima = str((estado.prefs.dados.get("calibracao") or {}).get("ultima_leitura", ""))
    if ultima[:10] != time.strftime("%Y-%m-%d"):
        _calibracao_em_segundo_plano(_baixar_calibracao)


def _o_que_vai_para_a_calibracao() -> list[dict]:
    """Exatamente o que sai desta maquina: as amostras medidas aqui."""
    maq = _maquina(testar=False)
    todas = maquina_mod.ler_amostras(CALIBRACAO_PATH)
    return [a for a in todas if not maq or a["maquina"].get("id") == maq.get("id")]


@app.get("/api/calibracao")
def calibracao_situacao() -> dict:
    """Se participa, o que vai (o conteudo exato) e quando foi e veio pela ultima vez."""
    c = estado.prefs.dados.get("calibracao") or {}
    de_fora, quando = calibracao_remota.ler_guardadas(CALIBRACAO_SERVIDOR_PATH)
    return {"participar": bool(c.get("participar")), "endereco": calibracao_remota.URL,
            "o_que_vai": _o_que_vai_para_a_calibracao(), "de_outras_maquinas": len(de_fora),
            "ultimo_envio": c.get("ultimo_envio", ""), "ultima_leitura": c.get("ultima_leitura", "") or quando,
            "erro": c.get("erro", "")}


@app.post("/api/calibracao")
def calibracao_escolher(payload: dict) -> dict:
    """Participar ou nao. Ligar manda as medidas daqui e traz as de outras maquinas."""
    participar = bool(payload.get("participar"))
    estado.prefs.atualizar({"calibracao": {"participar": participar}})
    if participar:
        def ida_e_volta() -> None:
            _enviar_calibracao(_o_que_vai_para_a_calibracao())
            _baixar_calibracao()
        _calibracao_em_segundo_plano(ida_e_volta)
        # O modelo padrao, se ja esta aqui e nunca foi medido: sem medida,
        # nao ha o que mandar. (Se ainda vai baixar, mede quando terminar.)
        try:
            if estado.client.model in {m["nome"] for m in modelos_mod.instalados(estado.client.host)}:
                _medir_para_calibracao(estado.client.model)
        except Exception:  # noqa: BLE001 - Ollama fora: mede quando o modelo baixar
            pass
    return calibracao_situacao()


@app.get("/api/maquina")
def maquina_ver() -> dict:
    """O teste desta maquina e o modelo recomendado. Na primeira vez, testa (uns 5 s)."""
    return _recomendacao()


@app.post("/api/maquina/testar")
def maquina_testar() -> dict:
    _maquina(fresco=True)
    return _recomendacao()


# L6: o perfil desta maquina pela faixa de hardware (src/perfis.py).
perfis_mod.montar(app, lambda: _maquina(testar=False))


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


def _contexto(registrar=None, parar=None, tarefa: str = "") -> Contexto:
    """O que as habilidades enxergam da aplicacao. `tarefa` escolhe o modelo (src/modelos.py)."""
    return Contexto(
        parar=parar,
        searcher=estado.searcher,
        client=estado.cliente_para(tarefa) if tarefa else estado.client,
        pasta=estado.pasta,
        cache_classificacao=CLASSIFICACAO_PATH,
        diarios=DIARIOS_DIR,
        recarregar=estado.recarregar,
        registrar=registrar,
        cancelado=estado.cancelar.is_set,
        antes_de_cada=lambda: recursos.esperar_maquina_livre(estado.devagar, limite_s=10),
        ritmo=estado.ritmo,
        # Os lembretes de Configuracoes > Aprendizado entram em toda resposta.
        ensinado=estado.contextos.bloco(),
        # O que ja foi lido uma vez, para nao ler de novo (HOOK 2).
        saber=estado.saber,
        # O que o escritorio entregou para o PAULUS aprender (src/material.py).
        material=estado.material,
        # As chaves do plano de melhoria da IA (config `ia`).
        ia=estado.prefs.dados.get("ia") or {},
        # A busca hibrida, para a leitura por trechos (I7).
        recuperar=estado.recuperar,
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

    # A pasta padrao tem nome de programador no disco (test_contracts); na tela
    # ela e o acervo do escritorio. So o nome mostrado muda: o caminho segue o
    # mesmo, porque e por ele que o indice acha cada documento. Subpasta sai
    # contada da raiz que o Acervo le - "Acervo PAULUS › Cliente › Tipo" -,
    # que e o que a tela agrupa; so o ultimo nome repetia "Locacao" para
    # cada cliente.
    padrao = Path(estado.pasta).resolve()
    raizes = [(padrao, NOME_DA_PASTA_PADRAO)] + [
        (p.resolve(), p.name or str(p)) for p in estado.pastas_do_acervo()[1:]
    ]
    nomes: dict[Path, str] = {}

    def nome_da_pasta(pasta: Path) -> str:
        if pasta not in nomes:
            real = pasta.resolve()
            nome = pasta.name or str(pasta)
            for raiz, rotulo in raizes:
                if real == raiz or raiz in real.parents:
                    nome = " › ".join([rotulo, *real.relative_to(raiz).parts])
                    break
            nomes[pasta] = nome
        return nomes[pasta]

    raiz_da_pasta: dict[Path, str] = {}

    def raiz_de(pasta: Path) -> str:
        """A pasta vigiada de onde o documento vem: a tela agrupa por ela."""
        if pasta not in raiz_da_pasta:
            real = pasta.resolve()
            raiz_da_pasta[pasta] = next((str(r) for r, _ in raizes if real == r or r in real.parents), "")
        return raiz_da_pasta[pasta]

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
            "raiz": raiz_de(caminho.parent),
            "pasta_curta": nome_da_pasta(caminho.parent),
            "existe": existe,
            "bytes": tamanho,
            "paginas": doc.pages,
            # Da pasta do proprio PAULUS: so estes podem ser apagados do disco
            # por aqui. Os das pastas vigiadas sao da pessoa - saem do Acervo,
            # nao do computador.
            "do_programa": Path(estado.pasta).resolve() in caminho.resolve().parents,
            # Paginas lidas da imagem pelo OCR (src/ocr_windows.py): texto que pode ter erro.
            "ocr": getattr(doc, "ocr", 0),
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
        item["assinado"] = _tem_assinatura_digital(caminho, tamanho, modificado) if existe else False
        item["analise"] = acervo.estado_da_analise(item)
        itens.append(item)

    return itens


_ASSINATURA_NO_ARQUIVO: dict[tuple, bool] = {}
LIMITE_PARA_PROCURAR_ASSINATURA = 40 * 1024 * 1024


def _tem_assinatura_digital(caminho: Path, tamanho: int, modificado: str) -> bool:
    """
    Se o PDF traz uma assinatura digital - so a presenca, nao a validade.

    Toda assinatura de PDF grava um /ByteRange (o trecho do arquivo que ela
    cobre); sem ele nao ha assinatura. Procurar a palavra no arquivo e barato,
    e o resultado fica guardado ate o arquivo mudar. Se ela vale, quem diz e
    /api/assinaturas/conferir, que le a assinatura de verdade.
    """
    if caminho.suffix.lower() != ".pdf" or not tamanho or tamanho > LIMITE_PARA_PROCURAR_ASSINATURA:
        return False
    chave = (str(caminho), tamanho, modificado)
    if chave not in _ASSINATURA_NO_ARQUIVO:
        try:
            _ASSINATURA_NO_ARQUIVO[chave] = b"/ByteRange" in caminho.read_bytes()
        except OSError:
            return False
    return _ASSINATURA_NO_ARQUIVO[chave]


@app.get("/api/documentos-abertos")
def documentos_abertos() -> dict:
    """
    So os nomes dos documentos abertos, para o "/" do compositor.

    Existe separada de /api/biblioteca porque aquela junta classificacao,
    marcas e estatistica de arquivo - trabalho demais para uma lista que a
    tela filtra a cada tecla digitada.
    """
    return {
        "documentos": [
            {"nome": d.name, "paginas": getattr(d, "pages", 0) or 0}
            for d in estado.searcher.documents
        ]
    }


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
    e_pdf = alvo.suffix.lower() == ".pdf"

    # Word e texto tambem tem pagina: o mesmo gerador do editor monta o PDF a
    # partir do texto lido - e o que o leitor da conversa ja mostra. Sem
    # trecho para achar, o total ainda precisa vir, senao o visor nao anda.
    if alvo.exists() and not lugar.get("total"):
        try:
            pdf = alvo.read_bytes() if e_pdf else ferramentas.pdf_do_documento(doc)
            lugar = {**lugar, "total": documento.paginas_de(pdf)}
        except Exception:  # noqa: BLE001 - sem contar, o visor mostra a primeira
            pass

    return {
        **lugar,
        "nome": doc.name,
        "caminho": str(alvo),
        "bytes": tamanho,
        "desenhavel": alvo.exists(),
        # Nao e a diagramacao do Word: e o texto do arquivo na folha do
        # PAULUS. A tela diz isso, em vez de apresentar como o original.
        "convertido": not e_pdf,
        "porque": citacao.por_que_este_trecho(payload.pergunta, payload.trecho),
    }


class LeituraDoDocumento(BaseModel):
    nome: str = ""
    trechos: list[str] = []


@app.post("/api/biblioteca/leitura")
def biblioteca_leitura(payload: LeituraDoDocumento) -> dict:
    """
    O que o visor ao lado da conversa desenha (paginas, as citadas e as
    marcas), sem registrar nada na conversa: e o clique num cartao de
    "Trechos lidos". O "Mostrar aqui" passa por /fazer, que anota.
    """
    doc = next((d for d in estado.searcher.documents if d.name == payload.nome), None)
    if not doc:
        raise HTTPException(status_code=404, detail="esse documento nao esta aberto")
    if not Path(doc.path).exists():
        raise HTTPException(status_code=404, detail="o arquivo saiu do lugar")
    trechos = [str(t)[:400] for t in payload.trechos[:12] if isinstance(t, str)]
    return ferramentas.leitura(doc, trechos)


class PlanilhaDoAcervo(BaseModel):
    nome: str = ""
    trechos: list[str] = []


@app.post("/api/biblioteca/planilha")
def biblioteca_planilha(payload: PlanilhaDoAcervo) -> dict:
    """
    A planilha do Acervo para o visor ao lado da conversa (pacote de telas,
    `Conversa - Planilha`): as abas com o valor calculado de cada celula, como
    no editor, e as linhas que a resposta citou. So leitura - nada e gravado.
    """
    doc = next((d for d in estado.searcher.documents if d.name == payload.nome), None)
    if not doc:
        raise HTTPException(status_code=404, detail="esse documento nao esta aberto")
    alvo = Path(doc.path)
    if not alvo.exists():
        raise HTTPException(status_code=404, detail="o arquivo saiu do lugar")
    if alvo.suffix.lower() != ".xlsx":
        raise HTTPException(status_code=400, detail="isso não é uma planilha do Excel")
    try:
        abas = planilha.de_xlsx(alvo.read_bytes())
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"não consegui ler a planilha: {exc}") from exc
    try:
        citadas = ferramentas.linhas_citadas_da_planilha(alvo, payload.trechos[:12])
    except Exception:  # noqa: BLE001 - sem citacao, a planilha abre do mesmo jeito
        citadas = []
    return {"nome": doc.name, "caminho": str(alvo), "bytes": alvo.stat().st_size,
            "abas": [a.to_dict() for a in abas], "calculado": [planilha.calcular_aba(a) for a in abas],
            "citadas": citadas}


class ProcurarNoDocumento(BaseModel):
    nome: str = ""
    termo: str = ""


@app.post("/api/biblioteca/procurar-no-documento")
def biblioteca_procurar_no_documento(payload: ProcurarNoDocumento) -> dict:
    """
    A lupa do visor ao lado da conversa (pacote de telas, T3): onde o termo
    aparece, pagina a pagina, com as marcas. Procura no PDF que a tela
    desenha - o arquivo, ou o que o gerador do editor monta para o Word.
    """
    import citacao

    doc = next((d for d in estado.searcher.documents if d.name == payload.nome), None)
    if not doc:
        raise HTTPException(status_code=404, detail="esse documento nao esta aberto")
    if not Path(doc.path).exists():
        raise HTTPException(status_code=404, detail="o arquivo saiu do lugar")
    try:
        origem = doc.path if Path(doc.path).suffix.lower() == ".pdf" else ferramentas.pdf_do_documento(doc)
        achados = citacao.ocorrencias(origem, payload.termo)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"nao consegui procurar: {exc}") from exc
    return {"termo": payload.termo, "achados": achados}


@app.get("/api/biblioteca/pagina")
def biblioteca_pagina(nome: str, numero: int = 1, largura: int = 1000):
    """A pagina do documento desenhada, para conferir sem sair daqui."""
    from fastapi.responses import Response

    doc = next((d for d in estado.searcher.documents if d.name == nome), None)
    if not doc:
        raise HTTPException(status_code=404, detail="esse documento nao esta aberto")
    if not Path(doc.path).exists():
        raise HTTPException(status_code=404, detail="o arquivo saiu do lugar")

    # PDF e desenhado do arquivo; Word e o resto, do PDF que o gerador do
    # editor monta a partir do texto lido - o visor da conversa mostra paginas
    # para qualquer formato.
    try:
        png = ferramentas.pagina_png(doc, numero, largura)
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
            for tipo, dados in habilidade.executar(_contexto(tarefa="leitura"), caminhos=caminhos):
                if tipo == "resultados":
                    for doc in dados.get("documentos", []):
                        if doc.get("sha1"):
                            estado.marcas.marcar_visto(doc["sha1"])
                    estado.recarregar()
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
        reversivel=False,
        dados={"caminhos": [i["caminho"] for i in dentro],
               "nomes": [i["nome"] for i in dentro]},
    )
    return {"pedido": pedido.to_dict(), "impedidos": fora, **estado.fila.para_tela()}


# ------------------------------------------------ pastas vigiadas


class CaminhoDePasta(BaseModel):
    caminho: str


def _nome_da_pasta_vigiada(p: Path) -> str:
    return NOME_DA_PASTA_PADRAO if chave_do_caminho(p) == chave_do_caminho(estado.pasta) else (p.name or str(p))


def _motivo_para_nao_vigiar(pasta: Path) -> str:
    """Por que essa pasta não entra no Acervo - vazio quando entra."""
    from scan import PASTAS_IGNORADAS

    if not pasta.is_dir():
        return "essa pasta não existe"
    alvo = pasta.resolve()
    if alvo.parent == alvo:
        return "um disco inteiro é demais para vigiar: escolha a pasta onde ficam os documentos"
    if alvo == Path.home().resolve():
        return "a pasta do usuário inteira tem de tudo (programas, fotos, downloads): escolha a pasta dos documentos"
    if any(parte.lower() in PASTAS_IGNORADAS for parte in alvo.parts[1:]):
        return "essa é uma pasta de sistema ou de programa, não de documentos"
    for ja in estado.pastas_do_acervo():
        ja = ja.resolve()
        if alvo == ja:
            return "essa pasta já está no Acervo"
        if ja in alvo.parents:
            return f"essa pasta já está no Acervo, dentro de “{_nome_da_pasta_vigiada(ja)}”"
    return ""


def _pastas_vigiadas_para_tela() -> dict:
    por_pasta: dict[str, int] = {}
    for d in estado.searcher.documents:
        caminho = chave_do_caminho(d.path)
        for pasta in estado.pastas_do_acervo():
            if caminho.startswith(chave_do_caminho(pasta) + os.sep):
                por_pasta[chave_do_caminho(pasta)] = por_pasta.get(chave_do_caminho(pasta), 0) + 1
                break
    programa = chave_do_caminho(estado.pasta)
    pastas = [{"caminho": str(p.resolve()), "nome": _nome_da_pasta_vigiada(p), "programa": chave_do_caminho(p) == programa,
               "documentos": por_pasta.get(chave_do_caminho(p), 0)} for p in estado.pastas_do_acervo()]
    # Incluida que sumiu do disco (pen drive tirado, pasta renomeada): a tela
    # mostra, em vez de fazer de conta que nunca existiu.
    sumidas = [{"caminho": e, "nome": Path(e).name or e, "programa": False, "documentos": 0, "sumiu": True}
               for e in (estado.prefs.dados.get("pastas_acervo") or []) if not Path(e).is_dir()]
    return {"pastas": pastas + sumidas, "fora": len(estado.prefs.dados.get("acervo_fora") or []),
            "lendo": estado.lendo, "versao": estado.versao_do_acervo}


@app.get("/api/acervo/pastas")
def acervo_pastas() -> dict:
    """As pastas que o Acervo vigia, com quantos documentos cada uma tem."""
    return _pastas_vigiadas_para_tela()


@app.post("/api/acervo/pastas")
def acervo_incluir_pasta(payload: CaminhoDePasta) -> dict:
    """
    Passa a vigiar uma pasta do computador, onde ela está: nada é movido nem
    copiado. A leitura é em segundo plano; a vigia pega o que entrar depois.
    """
    pasta = Path(payload.caminho.strip().strip('"'))
    motivo = _motivo_para_nao_vigiar(pasta)
    if motivo:
        raise HTTPException(status_code=400, detail=motivo)
    estado.incluir_no_acervo(pasta)
    arquivos = len(listar_arquivos([pasta.resolve()], estado.fora_do_acervo()))
    estado.recarregar_em_segundo_plano()
    return {"incluida": str(pasta.resolve()), "nome": pasta.resolve().name, "arquivos": arquivos,
            **_pastas_vigiadas_para_tela()}


@app.post("/api/acervo/pastas/tirar")
def acervo_tirar_pasta(payload: CaminhoDePasta) -> dict:
    """Deixa de vigiar a pasta. Os arquivos ficam onde estão."""
    if chave_do_caminho(payload.caminho) == chave_do_caminho(estado.pasta):
        raise HTTPException(status_code=400, detail="a pasta do próprio PAULUS não sai do Acervo")
    if not estado.tirar_pasta_do_acervo(payload.caminho):
        raise HTTPException(status_code=404, detail="essa pasta não está no Acervo")
    estado.recarregar()
    return _pastas_vigiadas_para_tela()


class CaminhosDeDocumentos(BaseModel):
    caminhos: list[str]
    # "Também excluir do computador", marcado na confirmação: o arquivo vai
    # para a Lixeira do Windows (src/lixeira_windows.py), de onde se restaura.
    excluir: bool = False


@app.post("/api/acervo/tirar")
def acervo_tirar_documentos(payload: CaminhosDeDocumentos) -> dict:
    """
    Tira documentos do Acervo sem apagar: o arquivo fica no disco, só deixa de
    ser lido. Volta pelo "devolver" - ou pelo Desfazer do aviso.

    Com `excluir`, o arquivo também vai para a Lixeira do Windows. O que o
    Windows não deixar excluir (pasta de rede, arquivo aberto) sai do Acervo
    do mesmo jeito, e volta com o motivo.
    """
    import lixeira_windows

    lidos = {chave_do_caminho(d.path) for d in estado.searcher.documents}
    caminhos = [c for c in payload.caminhos if chave_do_caminho(c) in lidos]
    if not caminhos:
        raise HTTPException(status_code=404, detail="nenhum desses documentos está no Acervo")
    excluidos: list[str] = []
    nao_excluidos: list[dict] = []
    if payload.excluir:
        for c in caminhos:
            motivo = lixeira_windows.mandar_para_lixeira(Path(c))
            if motivo:
                nao_excluidos.append({"nome": Path(c).name, "motivo": motivo})
            else:
                excluidos.append(c)
    # O que foi para a lixeira nao precisa da lista "fora do Acervo": nao esta
    # mais na pasta. O resto fica fora, para poder voltar.
    ficam = [c for c in caminhos if c not in excluidos]
    tirados = estado.tirar_documentos(ficam) if ficam else 0
    estado.recarregar()
    return {"tirados": tirados, "caminhos": ficam, "excluidos": excluidos, "nao_excluidos": nao_excluidos,
            **_pastas_vigiadas_para_tela()}


@app.post("/api/acervo/devolver")
def acervo_devolver_documentos(payload: CaminhosDeDocumentos) -> dict:
    devolvidos = estado.devolver_documentos(payload.caminhos)
    if devolvidos:
        estado.recarregar()
    return {"devolvidos": devolvidos, **_pastas_vigiadas_para_tela()}


@app.get("/api/acervo/fora")
def acervo_fora() -> dict:
    """O que foi tirado do Acervo, para devolver."""
    itens = []
    for c in estado.prefs.dados.get("acervo_fora") or []:
        p = Path(c)
        itens.append({"caminho": c, "nome": p.name, "pasta": str(p.parent), "existe": p.exists()})
    return {"itens": itens}


@app.get("/api/acervo/versao")
def acervo_versao() -> dict:
    """Barato, para a tela perguntar de tempos em tempos se o Acervo mudou."""
    return {"versao": estado.versao_do_acervo, "lendo": estado.lendo}


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

    return {"removido": alvo.name, "documentos": estado.recarregar()}


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
    try:
        return {"contratos": estado.recarregar(force=True)}
    except OSError as exc:
        # Disco cheio no meio da leitura (docs/ui/05): para, o cache do que
        # ja foi lido fica, e a tela diz o que fazer.
        if exc.errno == errno.ENOSPC:
            raise HTTPException(status_code=507, detail="O disco encheu no meio da leitura. O que já foi lido ficou guardado; libere espaço e reindexe de novo.") from exc
        raise


@app.post("/api/buscar-agora")
def buscar_agora(payload: Busca) -> dict:
    """Atalho para a habilidade `buscar`, mantido para nao quebrar chamadas antigas."""
    habilidade = estado.registro.obter("buscar")
    if not habilidade or not habilidade.executavel:
        raise HTTPException(status_code=503, detail="a habilidade de busca nao carregou")
    return habilidade.executar(_contexto(), termo=payload.termo, top=payload.top)


@app.post("/api/upload")
async def upload(arquivos: list[UploadFile], autorizados: str = Form(""), decisoes: str = Form("")) -> dict:
    """
    Arquivos que chegam pelo seletor do Windows ou arrastados.

    Acima de 50 MB volta em `pedem_confirmacao`, sem ser gravado; a tela
    pergunta e manda de novo com o nome em `autorizados` (JSON). Conteúdo que
    não é do tipo do nome é recusado (src/entrada.py). Nome repetido com
    conteúdo diferente: a tela pergunta (Renomear / Substituir, src/nomes.py)
    e nada é gravado antes; conteúdo igual não é conflito.
    """
    Path(estado.pasta).mkdir(parents=True, exist_ok=True)
    salvos: list[str] = []
    recusados: list[dict] = []
    pedem: list[dict] = []
    a_gravar: list[tuple[str, bytes]] = []
    try:
        liberados = set(json.loads(autorizados)) if autorizados else set()
    except ValueError:
        liberados = set()

    for arquivo in arquivos:
        nome = Path(arquivo.filename or "").name  # descarta qualquer caminho
        if not nome:
            continue
        if Path(nome).suffix.lower() not in SUPPORTED_SUFFIXES:
            recusados.append({"nome": nome, "motivo": "formato nao suportado"})
            continue
        # O tamanho antes de ler: 600 MB nao precisam ir para a memoria para
        # serem recusados.
        tamanho = arquivo.size if arquivo.size is not None else None
        if tamanho is not None:
            decisao, motivo = entrada.faixa(tamanho, nome in liberados)
            if decisao == "recusar":
                recusados.append({"nome": nome, "motivo": motivo})
                continue
            if decisao == "perguntar":
                pedem.append({"nome": nome, "caminho": nome, "mb": entrada.mb(tamanho), "motivo": motivo})
                continue

        conteudo = await arquivo.read()
        decisao, motivo = entrada.faixa(len(conteudo), nome in liberados)
        if decisao == "recusar":
            recusados.append({"nome": nome, "motivo": motivo})
            continue
        if decisao == "perguntar":
            pedem.append({"nome": nome, "caminho": nome, "mb": entrada.mb(len(conteudo)), "motivo": motivo})
            continue
        if not conteudo:
            recusados.append({"nome": nome, "motivo": "arquivo vazio (0 bytes) — o download ou a cópia não terminou; baixe de novo"})
            continue
        errado = entrada.conferir_bytes(nome, conteudo)
        if errado:
            recusados.append({"nome": nome, "motivo": errado})
            continue

        a_gravar.append((nome, conteudo))

    # Os nomes, todos antes de gravar o primeiro: com um conflito sem
    # decisao, nada entra e a tela pergunta.
    escolhas = nomes_mod.do_pedido(decisoes)
    pendentes: list[dict] = []
    ocupados: set[str] = set()
    destinos = []
    for nome, conteudo in a_gravar:
        igual = estado.pasta / nome
        if igual.exists() and nome not in escolhas and igual.read_bytes() == conteudo:
            destinos.append((None, nome, conteudo))      # o mesmo arquivo: nada a fazer
            continue
        destinos.append((nomes_mod.destino(estado.pasta, nome, escolhas, pendentes, ocupados=ocupados), nome, conteudo))
    nomes_mod.conferir(pendentes)
    for destino, nome, conteudo in destinos:
        if destino is None:
            salvos.append(nome)
            continue
        destino.write_bytes(conteudo)
        salvos.append(destino.name)

    total = estado.recarregar() if salvos else len(estado.searcher.documents)
    return {"salvos": salvos, "recusados": recusados + _nao_lidos(estado.pasta, salvos),
            "pedem_confirmacao": pedem, "contratos": total}


def _triagem_do_caminho(origem: Path, liberados: set[str]) -> tuple[str, str, dict | None]:
    """
    ("entra" | "perguntar" | "recusar", motivo, pedido) para um arquivo que
    vem pelo caminho: tamanho (src/entrada.py), vazio e tipo pelo conteúdo.
    """
    tamanho = origem.stat().st_size
    decisao, motivo = entrada.faixa(tamanho, chave_do_caminho(origem) in liberados)
    if decisao == "perguntar":
        return decisao, motivo, {"nome": origem.name, "caminho": str(origem), "mb": entrada.mb(tamanho), "motivo": motivo}
    if decisao == "recusar":
        return decisao, motivo, None
    if tamanho == 0:
        return "recusar", "arquivo vazio (0 bytes) — o download ou a cópia não terminou; baixe de novo", None
    errado = entrada.conferir_caminho(origem)
    if errado:
        return "recusar", errado, None
    return "entra", "", None


def _nao_lidos(pasta: Path, nomes: list[str]) -> list[dict]:
    """
    O que entrou na pasta e nao virou texto, com o motivo certo (extract.motivo_sem_texto).
    Fica na pasta; so nao entra no indice.
    """
    lidos = {os.path.normcase(str(Path(d.path).resolve())) for d in estado.searcher.documents}
    saida = []
    for nome in nomes:
        alvo = Path(pasta) / nome
        if os.path.normcase(str(alvo.resolve())) not in lidos:
            saida.append({"nome": nome, "motivo": motivo_sem_texto(alvo) or "não entrou no índice"})
    return saida


class AnexarCaminhos(BaseModel):
    caminhos: list[str]
    # Os acima de 50 MB que a pessoa confirmou na tela (src/entrada.py).
    autorizados: list[str] = []
    # Nome repetido: renomear ou substituir, por nome (src/nomes.py).
    decisoes: dict = {}


def _destinos_das_copias(origens: list[Path], pasta: Path, escolhas: dict) -> list[tuple[Path, Path, bool]]:
    """
    Para cada arquivo que vai ser copiado para `pasta`: (origem, destino,
    copiar?). O que ja esta la dentro, ou o mesmo conteudo com o mesmo nome,
    nao e copiado. Nome repetido com outro conteudo e sem decisao: nada e
    copiado e NomeRepetido sobe para a tela perguntar (src/nomes.py).
    """
    pendentes: list[dict] = []
    ocupados: set[str] = set()
    plano: list[tuple[Path, Path | None, bool]] = []
    for origem in origens:
        nome = origem.name
        igual = pasta / nome
        if origem.resolve().is_relative_to(pasta.resolve()):
            plano.append((origem, origem, False))
            continue
        if igual.exists() and nome not in escolhas and file_sha1(igual) == file_sha1(origem):
            plano.append((origem, igual, False))
            continue
        plano.append((origem, nomes_mod.destino(pasta, nome, escolhas, pendentes, ocupados=ocupados), True))
    nomes_mod.conferir(pendentes)
    return plano  # type: ignore[return-value]


class PedidoExterno(BaseModel):
    caminho: str = ""


@app.post("/api/externo/perguntar")
def externo_perguntar(payload: PedidoExterno) -> dict:
    """
    "Perguntar ao PAULUS", do botao direito no Explorer, com o programa ja
    aberto: o PAULUS.exe novo entrega o arquivo aqui e sai. A janela vem para
    frente com o arquivo anexado numa conversa nova.
    """
    caminho = Path(payload.caminho)
    if not caminho.is_file():
        raise HTTPException(status_code=404, detail="arquivo nao encontrado")
    if caminho.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise HTTPException(status_code=400, detail="formato nao suportado")
    if estado.ao_pedido_externo:
        # Em segundo plano: quem entregou (o PAULUS.exe do clique) recebe a
        # resposta na hora, sem esperar a janela.
        threading.Thread(target=estado.ao_pedido_externo, args=("perguntar", str(caminho.resolve())),
                         name="pedido-externo", daemon=True).start()
    return {"entregue": bool(estado.ao_pedido_externo)}


@app.post("/api/externo/mostrar")
def externo_mostrar() -> dict:
    """Abrir o PAULUS com ele ja aberto traz a janela que existe para frente."""
    if estado.ao_pedido_externo:
        threading.Thread(target=estado.ao_pedido_externo, args=("mostrar", ""), name="pedido-externo", daemon=True).start()
    return {"entregue": bool(estado.ao_pedido_externo)}


@app.post("/api/anexar/caminhos")
def anexar_caminhos(payload: AnexarCaminhos) -> dict:
    """
    Anexar a partir do computador, pelo caminho do arquivo.

    E o "Meu computador" do pop-up de anexar: a tela navega pelas pastas desta
    maquina e manda os caminhos escolhidos, e aqui o arquivo e copiado para o
    acervo e lido - o mesmo que /api/upload faz com o que chega pelo seletor
    do Windows, sem o arquivo precisar atravessar o navegador. Arquivo que ja
    esta na pasta do acervo nao e copiado sobre ele mesmo.
    """
    Path(estado.pasta).mkdir(parents=True, exist_ok=True)
    salvos: list[str] = []
    recusados: list[dict] = []
    pedem: list[dict] = []
    liberados = {chave_do_caminho(c) for c in payload.autorizados}
    aceitos: list[Path] = []
    for bruto in payload.caminhos:
        origem = Path(bruto)
        nome = origem.name
        if not origem.is_file():
            recusados.append({"nome": nome or bruto, "motivo": "arquivo nao encontrado"})
            continue
        if origem.suffix.lower() not in SUPPORTED_SUFFIXES:
            recusados.append({"nome": nome, "motivo": "formato nao suportado"})
            continue
        try:
            decisao, motivo, pedido = _triagem_do_caminho(origem, liberados)
        except OSError as exc:
            recusados.append({"nome": nome, "motivo": f"nao consegui ler: {exc.strerror or exc}"})
            continue
        if decisao == "perguntar":
            pedem.append(pedido)
        elif decisao == "recusar":
            recusados.append({"nome": nome, "motivo": motivo})
        else:
            aceitos.append(origem)
    # Nome repetido com outro conteudo: a tela pergunta antes de copiar.
    for origem, destino, copiar in _destinos_das_copias(aceitos, Path(estado.pasta), nomes_mod.do_pedido({"decisoes": payload.decisoes})):
        try:
            if copiar:
                shutil.copy2(origem, destino)
        except OSError as exc:
            recusados.append({"nome": origem.name, "motivo": f"nao consegui copiar: {exc.strerror or exc}"})
            continue
        salvos.append(destino.name)
    total = estado.recarregar() if salvos else len(estado.searcher.documents)
    return {"salvos": salvos, "recusados": recusados + _nao_lidos(estado.pasta, salvos),
            "pedem_confirmacao": pedem, "contratos": total}


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
def trabalhos_criar(payload: NovoTrabalho, request: Request = None) -> dict:
    titulo = titular(payload.pedido) if payload.pedido.strip() else "Nova conversa"
    trabalho = estado.trabalhos.criar(titulo, tipo=payload.tipo,
                                      criado_por=equipe.quem(request, estado.prefs.dados))
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


class RenomearGrupo(BaseModel):
    de: str
    para: str = ""


class ExportarConversa(BaseModel):
    caminho: str


FORMATOS_DE_CONVERSA = {"md": "text/markdown", "txt": "text/plain", "docx":
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


def _conversa_exportada(trabalho, formato: str) -> bytes:
    """
    A conversa num arquivo, para levar para fora do programa.

    Markdown e o padrao: abre legivel em qualquer editor e vira documento
    formatado onde houver quem o leia. Texto e o mesmo sem marcacao. Word sai
    com o titulo, quem falou em negrito e o texto em paragrafos. Em todos, a
    resposta que a pessoa parou no meio diz isso, e a que citou trechos diz
    de quais documentos.
    """
    from datetime import datetime

    def quando(iso: str) -> str:
        try:
            return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")
        except (TypeError, ValueError):
            return ""

    falas = []
    for m in trabalho.mensagens:
        quem = "Você" if m.autor == "pessoa" else "PAULUS"
        notas = []
        if getattr(m, "interrompida", False):
            notas.append("resposta parada no meio")
        documentos = sorted({f.get("documento", "") for f in (m.fontes or []) if f.get("documento")})
        if documentos:
            notas.append("trechos de " + ", ".join(documentos))
        falas.append((quem, quando(m.em), (m.texto or "").strip(), notas))
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    if formato == "docx":
        import io

        from docx import Document
        from docx.shared import Pt

        doc = Document()
        doc.add_heading(trabalho.titulo, level=1)
        rodape = doc.add_paragraph()
        rodape.add_run(f"Exportado do PAULUS Legal em {agora}").italic = True
        for quem, em, texto, notas in falas:
            cabeca = doc.add_paragraph()
            cabeca.add_run(quem).bold = True
            if em:
                cabeca.add_run(f"  ·  {em}").font.size = Pt(9)
            for paragrafo in (texto.split("\n") if texto else [""]):
                doc.add_paragraph(paragrafo)
            for nota in notas:
                doc.add_paragraph().add_run(nota).italic = True
        saida = io.BytesIO()
        doc.save(saida)
        return saida.getvalue()

    linhas: list[str] = []
    if formato == "md":
        linhas += [f"# {trabalho.titulo}", "", f"*Exportado do PAULUS Legal em {agora}*", ""]
        for quem, em, texto, notas in falas:
            linhas += [f"**{quem}**" + (f" · {em}" if em else ""), "", texto, ""]
            linhas += [f"> _{nota}_" for nota in notas]
            if notas:
                linhas.append("")
    else:
        linhas += [trabalho.titulo, f"Exportado do PAULUS Legal em {agora}", ""]
        for quem, em, texto, notas in falas:
            linhas += [quem + (f" - {em}" if em else ""), texto]
            linhas += [f"({nota})" for nota in notas]
            linhas.append("")
    return "\n".join(linhas).rstrip("\n").encode("utf-8") + b"\n"


@app.post("/api/trabalhos/{id_}/renomear")
def trabalhos_renomear(id_: str, payload: Renomear) -> dict:
    trabalho = estado.trabalhos.obter(id_)
    if not trabalho:
        raise HTTPException(status_code=404, detail="conversa nao encontrada")

    titulo = " ".join(payload.titulo.split())[:LIMITE_DE_NOME]
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

    trabalho.grupo = " ".join(payload.grupo.split())[:LIMITE_DE_NOME]
    trabalho.atualizado_em = jobs_agora()
    estado.trabalhos.salvar(trabalho)
    return trabalho.resumo()


@app.get("/api/trabalhos/{id_}/exportar")
def trabalhos_exportar_baixar(id_: str, formato: str = "md") -> Response:
    """A conversa como download - o caminho de quem abre pelo navegador."""
    trabalho = estado.trabalhos.obter(id_)
    if not trabalho:
        raise HTTPException(status_code=404, detail="conversa nao encontrada")
    formato = formato if formato in FORMATOS_DE_CONVERSA else "md"
    nome = re.sub(r'[\\/:*?"<>|]+', "-", trabalho.titulo or "conversa").strip() or "conversa"
    from urllib.parse import quote

    return Response(
        content=_conversa_exportada(trabalho, formato),
        media_type=FORMATOS_DE_CONVERSA[formato],
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(nome + '.' + formato)}"},
    )


@app.post("/api/trabalhos/{id_}/exportar")
def trabalhos_exportar_gravar(id_: str, payload: ExportarConversa) -> dict:
    """
    A conversa gravada no caminho que a pessoa escolheu no "Salvar como".

    Na janela do programa, download de navegador nao chega a lugar nenhum: a
    tela pede o caminho ao Windows e o servidor grava. O formato sai da
    extensao escolhida; sem extensao, e Markdown.
    """
    trabalho = estado.trabalhos.obter(id_)
    if not trabalho:
        raise HTTPException(status_code=404, detail="conversa nao encontrada")
    caminho = Path(payload.caminho)
    formato = caminho.suffix.lower().lstrip(".")
    if formato not in FORMATOS_DE_CONVERSA:
        formato = "md"
        caminho = caminho.with_name(caminho.name + ".md")
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(_conversa_exportada(trabalho, formato))
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"nao consegui gravar o arquivo: {exc}") from exc
    return {"caminho": str(caminho), "nome": caminho.name, "formato": formato}


@app.post("/api/grupos/renomear")
def grupos_renomear(payload: RenomearGrupo) -> dict:
    """
    Renomeia um grupo de conversas - ou o desfaz, com `para` vazio.

    Desfazer o grupo nao apaga conversa nenhuma: elas vao para "Sem grupo".
    A resposta traz os ids, para a tela oferecer Desfazer (que e renomear de
    volta so aquelas conversas).
    """
    de = " ".join(payload.de.split())
    para = " ".join(payload.para.split())[:LIMITE_DE_NOME]
    if not de:
        raise HTTPException(status_code=400, detail="diga qual grupo")
    ids = estado.trabalhos.renomear_grupo(de, para)
    if not ids:
        raise HTTPException(status_code=404, detail="grupo nao encontrado")
    return {"ids": ids, "de": de, "para": para}


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
            item = {
                "id": trabalho.id,
                "titulo": trabalho.titulo,
                "etapa": atual.titulo if atual else "",
                "feitos": atual.feitos if atual else 0,
                "total": atual.total if atual else 0,
                "progresso": trabalho.progresso or 0,
                # O cartao do pacote de telas (Assistente - Acontecendo agora)
                # desenha uma faixa por etapa, com o que cada uma achou.
                "etapas": [{"titulo": e.titulo, "estado": e.estado, "detalhe": e.detalhe,
                            "feitos": e.feitos, "total": e.total} for e in trabalho.etapas],
            }
            # A resposta andando diz em que fase esta e ha quanto tempo - e a
            # barra so existe onde ha medida: leitura com previsao desta
            # maquina. A conta de etapas (1 de 2) deixava a barra parada em
            # 50% a leitura inteira.
            a = estado.andamento.get(trabalho.id)
            if a:
                agora = time.time()
                item["andamento"] = {
                    "fase": a["fase"],
                    "decorrido_s": round(agora - a["inicio"], 1),
                    "fase_s": round(agora - a["desde"], 1),
                    "previsao_s": a["previsao_s"],
                    "palavras": a["palavras"],
                    "documentos": a["documentos"],
                    # Na fila do modelo: quantas perguntas estao na frente.
                    "posicao": a.get("posicao", 0),
                }
            executando.append(item)

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
    trabalho = estado.trabalhos.obter(id_)
    if not trabalho:
        raise HTTPException(status_code=404, detail="trabalho nao encontrado")
    caminho = estado.trabalhos.caminho_de(id_)
    movidos = [estado.lixeira.mover_arquivo(caminho)] if caminho.exists() else []
    entrada = estado.lixeira.guardar("conversa", id_, trabalho.titulo, "Assistente", {"id": id_}, movidos)
    estado.trabalhos.remover(id_)
    return _foi_para_lixeira(entrada, "removido", id_)


def _em_foco(trabalho) -> list[str]:
    """
    Os documentos que esta conversa vinha lendo.

    Aceita o formato antigo - um nome so, em texto - porque conversa gravada
    antes do escopo virar lista continua no disco.
    """
    guardado = trabalho.contexto.get("documento_em_foco") or []
    if isinstance(guardado, str):
        return [guardado] if guardado else []
    return [n for n in guardado if n]


def _escopo_da_pergunta(trabalho, pergunta: str, payload: Pergunta) -> tuple[list, list]:
    """
    Quais documentos ler, e quais a frase referiu de proposito.

    A regra mora em `intencao.escopo` - e da mesma familia das outras regras
    de conversa, e la da para testar sem subir o programa inteiro. Aqui fica
    so a contabilidade: ler o foco do trabalho e grava-lo de volta.
    """
    escolhidos, explicito = intencao.escopo(
        pergunta,
        abertos=estado.searcher.documents,
        em_foco=_em_foco(trabalho),
        pedidos=payload.apenas,
        tudo=payload.tudo,
        herdar_foco=not payload.sem_anexo,
    )
    trabalho.contexto["documento_em_foco"] = escolhidos
    return escolhidos, explicito


@app.post("/api/trabalhos/{id_}/parar")
def trabalhos_parar(id_: str) -> dict:
    """
    O botao de parar da caixa de pedido.

    Com resposta sendo escrita, levanta o sinal dela: a leitura larga o modelo
    em ate um quarto de segundo, guarda o que ja saiu e fecha a conversa como
    parada. Sem resposta nenhuma andando - a conversa ficou "trabalhando" de
    uma sessao que ja nao existe -, a propria rota a devolve como parada.
    """
    trabalho = estado.trabalhos.obter(id_)
    if not trabalho:
        raise HTTPException(status_code=404, detail="conversa nao encontrada")
    sinal = estado.respondendo.get(id_)
    if sinal:
        sinal.set()
        return {"parando": True, "estado": trabalho.estado}
    if trabalho.estado == EXECUTANDO:
        for etapa in trabalho.etapas:
            if etapa.estado == EXECUTANDO:
                etapa.estado = PAUSADO
        trabalho.estado = PAUSADO
        estado.trabalhos.salvar(trabalho)
    return {"parando": False, "estado": trabalho.estado}


def _dono_da_vez(request: Request | None) -> str:
    """De quem e a pergunta, para a fila do modelo: a janela local, ou a conta de fora."""
    p = rotas_do_acesso.pessoa(request)
    return f"conta:{p['conta_id']}" if p else "local"


@app.post("/api/trabalhos/{id_}/perguntar")
def trabalhos_perguntar(id_: str, payload: Pergunta, request: Request = None) -> StreamingResponse:
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
    # A 3a pergunta da mesma pessoa, com duas na fila do modelo, e recusada
    # ANTES de entrar no historico: nada fica pela metade na conversa.
    dono = _dono_da_vez(request)
    # F1 (src/fila_de_todos.py): a pergunta que vem da fila da conversa ja tem
    # a vez (fila_modelo.VEZ) e nao entra de novo. As outras podem pedir
    # prioridade (Ctrl+Enter); com esta conversa ja respondendo, a pergunta
    # fica guardada nela, com lugar na fila, e vai sozinha na vez.
    herdada = fila_modelo.VEZ.get()
    herdada = herdada if herdada is not None and not herdada.saiu else None
    prioridade = ({"tipo": "", "aviso": ""} if herdada is not None
                  else fila_de_todos.decidir_prioridade(estado, request, dono, payload.prioridade))
    # A que espera vai sozinha pela execucao desacoplada (C1): sem ela, ninguem a rodaria.
    if (herdada is None and fila_de_todos.ligada(estado) and rotas_execucoes.ligada(estado, "execucao")
            and estado.respondendo.get(id_) and not payload.retomar):
        resposta = fila_de_todos.guardar(estado, trabalho, payload, request, dono, prioridade, trabalhos_perguntar)
        fila_de_todos.anotar_prioridade(estado, request, prioridade["tipo"])
        return resposta
    if herdada is None and not estado.fila_modelo.cabe(dono):
        raise HTTPException(status_code=429, detail="você já tem duas perguntas esperando a vez do modelo; "
                                                    "espere uma terminar para mandar outra")
    fila_de_todos.anotar_prioridade(estado, request, prioridade["tipo"])
    # D1: escrever no aparelho - so se o servidor deixa (src/aparelho.py).
    escrita_no_aparelho, motivo_do_escritorio = None, ""
    if payload.aparelho:
        pode, motivo_do_escritorio = aparelho_mod.pode_escrever(estado, request)
        if pode:
            escrita_no_aparelho = aparelho_mod.Escrita(estado, request, id_)
    # N15: a nuvem - so na janela do escritorio, ligada e com a chave (src/nuvem.py).
    # O Envio confere tudo de novo depois da busca, com os trechos na mao.
    envio_nuvem = None
    if payload.nuvem and escrita_no_aparelho is None:
        envio_nuvem = nuvem_mod.Envio(estado, trabalho, pessoa=rotas_do_acesso.pessoa(request))

    habilidade = estado.registro.obter("perguntar")
    if not habilidade or not habilidade.executavel:
        raise HTTPException(status_code=503, detail="a habilidade de perguntar nao carregou")

    pergunta = payload.pergunta.strip()
    # A2: o agente desta pergunta (src/agente_na_conversa.py), por regra - o
    # que a pessoa escolheu, "@Nome", exemplos e palavras; o juiz so desempata.
    agente = None
    agente_como = ""
    if rotas_execucoes.ligada(estado, "agentes") and getattr(estado, "agentes", None) is not None:
        try:
            ativos = estado.agentes.ativos()
        except Exception:  # noqa: BLE001 - agente com problema nao para a conversa
            ativos = []
        if ativos:
            # A4: "sem agente" quando a regra sugeria um conta no "nao usar" dele.
            if payload.sem_agente:
                agentes_medida.anotar_nao_usar(estado, pergunta, ativos)
            escolha = agente_mod.escolher(pergunta, ativos, pedido=payload.agente, sem_agente=payload.sem_agente,
                                          juiz=None if (payload.agente or payload.sem_agente) else _juiz())
            pergunta = escolha.pergunta or pergunta
            agente, agente_como = escolha.agente, escolha.como
            # A4: a pergunta sai com o agente - conta como uso dele.
            agentes_medida.usou(estado, agente)
    if trabalho.titulo == "Nova conversa" and not trabalho.mensagens:
        trabalho.titulo = titular(pergunta)

    ultima = trabalho.mensagens[-1] if trabalho.mensagens else None
    # Retomar troca a resposta parada - e tambem o cartao "onde eu procuro?",
    # que a pessoa respondeu escolhendo onde.
    if (payload.retomar and ultima and ultima.autor == "paulus"
            and (ultima.interrompida
                 or (ultima.proposta or {}).get("tipo") in ("escopo", "programa", "consulta_cadastro"))):
        trabalho.mensagens.pop()
        ultima = trabalho.mensagens[-1] if trabalho.mensagens else None
    if not (payload.retomar and ultima and ultima.autor == "pessoa" and ultima.texto.strip() == pergunta):
        trabalho.dizer("pessoa", pergunta, quem=equipe.quem(request, estado.prefs.dados)["nome"])

    # A memoria da conversa (I4, src/memoria.py): "e a multa?" herda o sujeito
    # da pergunta anterior, por regra, e os dois ultimos pares vao junto para
    # o modelo. A conversa guarda o que a pessoa escreveu; daqui para baixo,
    # busca e modelo leem a pergunta inteira.
    historico: list[dict] = []
    continuou = False
    if (estado.prefs.dados.get("ia") or {}).get("memoria", True):
        pergunta, historico, continuou = memoria_mod.preparar(trabalho.mensagens, trabalho.contexto, pergunta)
        if continuou:
            trabalho.registrar("Entendi como continuação da anterior: “" + pergunta + "”",
                               mexer_na_ordem=not rotas_execucoes.ligada(estado, "painel"))

    # Antes de sair procurando: o que a pessoa pediu? A conversa tinha um
    # caminho so, e "anote uma reuniao no calendario" virava busca pela
    # palavra "reuniao" dentro dos contratos - resposta certa para a pergunta
    # errada. Ler a intencao e por regra: instantaneo e repetivel.
    # Sobre qual documento e esta conversa. Duas fontes, nesta ordem: o nome
    # que a frase escreve, e - quando ela diz "o referido documento" - o que
    # ficou em foco na conversa. Sem isso, "Exiba o referido documento aqui"
    # nao nomeia arquivo nenhum, cai na busca e e respondido pelo acervo
    # inteiro: foi assim que a pergunta sobre um comprovante de viagem voltou
    # falando de contrato de compra e venda.
    foco_antes = _em_foco(trabalho)
    citado, explicito = _escopo_da_pergunta(trabalho, pergunta, payload)
    # A2: `fontes` do agente so restringe o que a busca le - nunca abre o que
    # a pessoa nao teria.
    if agente is not None:
        # O documento em foco e o anexo desta pergunta, ou o que a conversa ja
        # vinha lendo; so sem nenhum dos dois, o que a frase nomeia.
        em_foco = list(payload.apenas or []) or list(foco_antes or []) or list(citado or [])
        restrito = agente_mod.restringir(agente, em_foco, estado.searcher.documents)
        if restrito is not None:
            if not restrito:
                return _so_dizer(trabalho, agente_mod.sem_documento(agente))
            citado = [n for n in (citado or []) if n in restrito] or restrito
            explicito = [n for n in explicito if n in restrito]
    # A continuacao herda tambem os documentos a que a resposta anterior se
    # restringiu: "e o foro?" e sobre o mesmo contrato.
    if continuou and not citado:
        abertos = {d.name for d in estado.searcher.documents}
        herdado = [n for n in memoria_mod.escopo_anterior(trabalho.mensagens) if n in abertos]
        if herdado:
            citado = herdado
            trabalho.contexto["documento_em_foco"] = herdado

    lido = intencao.ler(pergunta, documentos=estado.searcher.documents,
                        cadastros=[f["nome"] for f in estado.cadastros.listar()])
    # "Exiba o referido documento" so vira acao de abrir quando se sabe qual e.
    # `explicito`, e nao `citado`: com o foco herdado, "mostre o valor do
    # adiantamento" abriria o arquivo em vez de responder a pergunta.
    # "Quero que voce abra o documento", com o anexo na caixa: o pedido e o
    # arquivo. Antes ia para o modelo, que respondia copiando o texto inteiro
    # na conversa. Agora vem o cartao - mostrar aqui, editar ou abrir no
    # Windows -, a nao ser que a frase peca o conteudo.
    if lido.tipo == "documentos" and intencao.quer_abrir(pergunta):
        alvo = explicito if len(explicito) == 1 else (
            citado if citado and intencao.pede_so_o_documento(pergunta) else [])
        if len(alvo) == 1:
            lido = intencao.Intencao(
                tipo="abrir", titulo=alvo[0], campos={"nome": alvo[0]},
                porque="“" + pergunta.strip().rstrip(".!?") + "”",
            )
        elif alvo:
            lido = intencao.Intencao(
                tipo="exibir", titulo=alvo[0], campos={"nome": alvo[0], "nomes": alvo[:4]},
                porque="você pediu para abrir os documentos anexados",
            )
    # C4 (chave conversa.roteamento): "como funciona o acesso de fora?" e
    # "o que você faz" caem os dois em intencao.SOBRE; com uma tela citada, a
    # resposta e a explicacao dela, e nao a lista de tudo o que o programa faz.
    roteamento = consulta_cadastro.ligado(estado.prefs.dados)
    if roteamento and lido.tipo == "sobre":
        leitura = programa.ler(pergunta, dados=estado, juiz=None, ampliado=True)
        if leitura and leitura.tipo == "como":
            return _responder_programa(trabalho, leitura, pergunta)

    # N6: as tarefas de vários passos rodam na janela do escritório (como a tela Agentes).
    if lido.tipo == "passos" and not rotas_do_acesso.e_local(request):
        return _so_dizer(trabalho, "As tarefas de vários passos (os contratos vencendo, revisar contra o padrão) rodam "
                                   "só na janela do escritório, por ora. Peça de lá, ou em Agentes › Tarefas de vários passos.")
    # Pacote de telas (`Conversa - Gravando`): gravar a reuniao aqui, com a
    # transcricao ao vivo e, se pedido, as sugestoes tiradas do caso.
    if lido.tipo == "gravar":
        return _responder_gravacao(trabalho, lido, pergunta)
    # `Conversa - Assinar`: o PDF abre ao lado com o selo posto, e o cartao
    # da conversa traz as escolhas. Assinar continua pedindo o sim.
    if lido.tipo == "assinar":
        return _responder_assinatura(trabalho, lido, pergunta)
    # `Conversa - E-mail` e `Conversa - Escrever e-mail`: a mensagem aberta na
    # conversa, e a resposta escrita no lugar da caixa de pedido.
    if lido.tipo == "email":
        return _responder_email(trabalho, lido, pergunta, request)
    # `Conversa - Cadastro`, `- Equipe`, `- Despesa fixa`: a ficha na coluna,
    # preenchida com o que o Acervo (ou o anexo) diz. Com um agente, o cartao
    # de sempre (a ferramenta dele).
    if (lido.tipo == "ficha" or (lido.tipo == "cadastro" and lido.campos.get("nome"))) and agente is None:
        return _responder_ficha(trabalho, lido, pergunta, citado or explicito)
    # `Conversa - Financeiro` e `- Relatorio`: os numeros do mes somados
    # aqui; a coluna traz o parecer, os papeis e as sugestoes.
    if lido.tipo in ("financeiro", "relatorio") and agente is None:
        return _responder_financeiro(trabalho, lido, pergunta)
    # T5: uma secao de Configuracoes na coluna, com as mudancas marcadas -
    # nada gravado antes do "Salvar alteracoes". So na janela do escritorio.
    if lido.tipo == "config" and agente is None:
        if not rotas_do_acesso.e_local(request):
            return _so_dizer(trabalho, "As Configurações mudam só na janela do escritório. Peça de lá, ou abra Configurações no computador do escritório.")
        return _responder_config(trabalho, lido, pergunta)
    # `Conversa - Lancamento` e `- Recebimento`: o lancamento na coluna.
    if lido.tipo == "lancamento" and agente is None:
        return _responder_lancamento(trabalho, lido, pergunta, citado or explicito)
    # `Conversa - Criar agente`: tres perguntas e o rascunho na coluna.
    if lido.tipo == "criar_agente":
        return _responder_criar_agente(trabalho, lido, pergunta)
    if lido.tipo in ("agenda", "tarefa", "sobre", "abrir", "servico", "cadastro", "nota", "exibir", "passos"):
        # A2: com um agente, a acao so vale se ele declarou a ferramenta dela;
        # o que ele pediu sem ter e recusado e fica registrado.
        if agente is not None and lido.tipo != "sobre":
            ferramenta = agente_mod.ferramenta_da_acao(lido.tipo)
            if not agente_mod.pode_usar(agente, ferramenta):
                agente_mod.registrar_recusa(estado, trabalho, agente, ferramenta, pergunta)
                return _so_dizer(trabalho, agente_mod.frase_da_recusa(agente, ferramenta))
        return _responder_sem_documentos(trabalho, lido, pergunta, agente=agente)

    # C4: "qual o CPF do cliente Matheus?" responde da ficha, por molde, sem
    # modelo e sem entrar na fila dele (src/consulta_cadastro.py). Antes lia
    # 21 documentos (~165 s). Com documento anexado, a pergunta e sobre ele -
    # a consulta nem olha. Com um documento cujo NOME a frase escreve
    # ("Matheus Uener 1.docx" e "qual o CPF do Matheus Uener?"), vale a ficha
    # quando ela existe; sem ficha, segue para aquele documento, e nao para a
    # oferta - ler um documento nomeado nao e ler o acervo.
    if roteamento and lido.tipo == "documentos" and not payload.documentos and not payload.apenas:
        consulta = _consultar_cadastro(pergunta)
        if consulta and (not explicito or (consulta.fonte in ("cadastros", "meus_dados") and consulta.modo != "nada")):
            return _responder_consulta_cadastro(trabalho, consulta, pergunta)

    # O que o programa sabe de si: a agenda, as tarefas, o Financeiro, a
    # fila, e como se faz cada coisa em cada tela. Antes, "quanto recebi este
    # mes?" ia procurar dentro dos contratos. A regra decide o que pode; so a
    # duvida vai ao modelo, como ESCOLHA de uma letra entre o que a regra
    # montou (programa.py, juizo.py). Com documento anexado, a pergunta e
    # sobre ele - a camada nem olha.
    if lido.tipo == "documentos" and not payload.documentos and not payload.apenas and not explicito:
        leitura = programa.ler(pergunta, dados=estado, juiz=_juiz(), em_foco=citado, ampliado=roteamento)
        if leitura:
            return _responder_programa(trabalho, leitura, pergunta)

    # "Qual o valor do contrato?" sem dizer qual, e o Acervo tem varios: a
    # conversa pergunta qual, em vez de o modelo escolher um e responder como
    # se fosse o unico. So quando nada na conversa diz qual (anexo, foco,
    # nome na frase). Nao olha `tudo`: a pilula "Acervo" do compositor manda
    # `tudo` em toda pergunta, e o cartao nunca aparecia pela tela. Quem vem
    # do cartao (um documento ou "Em todos") vem com `retomar`.
    if not payload.apenas and not payload.retomar and not explicito and not citado:
        substantivo = intencao.referencia_generica(pergunta)
        if substantivo:
            nomes = intencao.documentos_do_tipo(substantivo, pergunta, estado.searcher.documents)
            if len(nomes) >= 2:
                return _perguntar_qual_documento(trabalho, pergunta, substantivo, nomes)

    # Tirou o anexo e perguntou sem nomear documento: antes de ler os
    # dezessete, pergunta onde - so no que a conversa vinha lendo, ou no
    # acervo inteiro. Ler tudo leva minutos, e nao foi o que a pessoa disse.
    if (payload.sem_anexo and not citado and not payload.tudo
            and not intencao.quer_todo_o_acervo(pergunta)):
        trabalho.contexto["documento_em_foco"] = foco_antes
        return _perguntar_onde_procurar(trabalho, pergunta, foco_antes)

    trabalho.etapas = [
        Etapa("Procurar nos documentos", estado=EXECUTANDO),
        Etapa("Ler os trechos e responder"),
    ]
    trabalho.estado = EXECUTANDO
    estado.trabalhos.salvar(trabalho)

    def registrar(texto: str) -> None:
        trabalho.registrar(texto, mexer_na_ordem=not rotas_execucoes.ligada(estado, "painel"))

    parar = threading.Event()
    estado.respondendo[id_] = parar

    def pausar_o_que_executava() -> None:
        for etapa in trabalho.etapas:
            if etapa.estado == EXECUTANDO:
                etapa.estado = PAUSADO
        trabalho.estado = PAUSADO

    def gerar() -> Iterator[str]:
        """
        A resposta e o que sempre garante que a conversa nao fica presa.

        Se quem esta do outro lado some no meio - a janela fechou, a pagina
        recarregou -, o gerador e fechado sem chegar ao fim, e a conversa
        ficava "trabalhando" para sempre: foi o que apareceu com 345 s no
        relogio. O `finally` a devolve como parada.
        """
        try:
            yield from _gerar()
        finally:
            # A vez no modelo volta para a fila em qualquer saida: fim,
            # parar, erro ou a pagina que fechou no meio.
            if na_fila["vez"] is not None:
                estado.fila_modelo.sair(na_fila["vez"])
            estado.andamento.pop(id_, None)
            if estado.respondendo.get(id_) is parar:
                del estado.respondendo[id_]
            if trabalho.estado == EXECUTANDO:
                pausar_o_que_executava()
                estado.trabalhos.salvar(trabalho)

    na_fila: dict = {"vez": None}

    def _gerar() -> Iterator[str]:
        import time

        inicio = time.time()
        partes: list[str] = []
        cobertura: dict = {}
        fontes: list[dict] = []
        andamento = {"fase": "procurando", "inicio": inicio, "desde": inicio,
                     "previsao_s": 0, "palavras": 0, "documentos": 0, "caracteres": 0}
        estado.andamento[id_] = andamento

        def fase(nome: str) -> None:
            andamento["fase"] = nome
            andamento["desde"] = time.time()

        # C2: as etapas, com os nomes do servidor, desde o primeiro instante -
        # a tela nao inventa as dela.
        yield _sse("etapas", {"etapas": [asdict_etapa(e) for e in trabalho.etapas]})

        # A vez no modelo (src/fila_modelo.py). A vez e pega aqui, dentro da
        # resposta, e nao na rota: se a pagina fechar antes de a resposta
        # comecar, nenhum lugar fica preso na fila. Sem ninguem na frente,
        # passa direto e nada aparece; com alguem, a tela ve a posicao.
        # A resposta por molde (I3) nao usa o modelo e sai em milissegundos:
        # esperar a vez de outra pessoa por ela seria esperar por nada.
        sem_fila = _sem_modelo(habilidade, pergunta, citado)
        if herdada is not None:
            # A pergunta que esperava na conversa: a vez ja e dela (F1).
            na_fila["vez"] = herdada
        elif not sem_fila and escrita_no_aparelho is None and envio_nuvem is None:
            # D4: a pergunta que vai ao aparelho nao entra na fila do
            # escritorio - a busca nao usa a vez, e quem escreve e o aparelho.
            # Se a resposta voltar para o escritorio, a chamada ao modelo
            # entra na fila sozinha (fila_modelo.vez_para_o_modelo).
            try:
                na_fila["vez"] = estado.fila_modelo.entrar(dono, rotulo=trabalho.titulo, origem="conversa",
                                                           prioridade=prioridade["tipo"])
            except FilaCheia as exc:
                trabalho.estado = PAUSADO
                estado.trabalhos.salvar(trabalho)
                yield _sse("erro", {"mensagem": str(exc)})
                return
        ultima_posicao = -1
        ultimo_evento: tuple = ()
        while na_fila["vez"] is not None and not estado.fila_modelo.esperar(na_fila["vez"], timeout=0.5):
            if parar.is_set():
                break
            # F1: a posicao, a previsao e quem esta na frente (primeiro nome e
            # origem, nunca o texto); muda quando alguem passa na frente.
            dados_fila = estado.fila_modelo.para_evento(na_fila["vez"])
            chave_evento = (dados_fila["posicao"], len(dados_fila["na_frente"]), dados_fila.get("motivo", ""))
            if chave_evento != ultimo_evento:
                ultimo_evento = chave_evento
                ultima_posicao = dados_fila["posicao"]
                fase("fila")
                andamento.update(posicao=ultima_posicao, previsao_s=dados_fila["previsao_s"])
                if not fila_de_todos.ligada(estado):
                    dados_fila = {"posicao": dados_fila["posicao"], "previsao_s": dados_fila["previsao_s"]}
                elif prioridade.get("aviso"):
                    # Ctrl+Enter sem a liberacao do titular (ou alem do limite): a razao, numa linha.
                    dados_fila["aviso"] = prioridade["aviso"]
                yield _sse("fila", dados_fila)
        if parar.is_set():
            pausar_o_que_executava()
            estado.trabalhos.salvar(trabalho)
            yield _sse("parado", {"segundos": round(time.time() - inicio, 1), "titulo": trabalho.titulo,
                                  "escreveu": False})
            return
        if ultima_posicao >= 0:
            fase("procurando")
            andamento["previsao_s"] = 0
        medida: dict = {}
        lido_chars = 0
        # O nivel com que a camada respondeu, quando ela respondeu. Nulo quer
        # dizer o caminho de sempre.
        nivel: int | None = None
        inferencia = False
        # O que vai para a linha da medicao (src/medicao.py): o caminho que a
        # pergunta tomou e os numeros que o modelo devolveu.
        medir: dict = {"caminho": None, "fallback": False, "truncou": False, "trechos": 0}

        def medir_agora() -> None:
            numeros = medida or medir.get("contagem") or {}
            estado.medicao.pergunta(
                modelo=medir.get("modelo", estado.client.model), num_ctx=numeros.get("num_ctx") or getattr(estado.client, "num_ctx", 0),
                prompt_eval_count=numeros.get("tokens_lidos"), eval_count=numeros.get("tokens_escritos"),
                lendo_s=medida.get("esperou_segundos") if medida else None,
                escrevendo_s=medida.get("escrevendo_segundos") if medida else None,
                total_s=round(time.time() - inicio, 1), caminho=medir["caminho"], nivel=nivel,
                trechos=medir["trechos"], caracteres=lido_chars,
                truncou=medir["truncou"] or bool(numeros.get("truncou")), fallback=medir["fallback"])

        ctx = _contexto(registrar, parar=parar.is_set, tarefa=(agente.modelo if agente is not None and agente.modelo else "conversa"))
        ctx.historico = historico
        # A2: o corpo do agente, cercado e rotulado, no fim da instrucao de
        # sistema - abaixo das regras do produto (habilidades/perguntar.py).
        if agente is not None:
            ctx.agente_instrucoes = agente_mod.instrucoes(agente)
        # C6: a cerca em todo texto de terceiros (habilidades/perguntar.py).
        ctx.cerca = rotas_execucoes.ligada(estado, "cerca")
        if escrita_no_aparelho is not None:
            ctx.escrita_no_aparelho = escrita_no_aparelho
        if envio_nuvem is not None:
            ctx.nuvem = envio_nuvem
        if payload.inteiro:
            ctx.ia["leitura"] = "tudo"
        sem_fundamento: dict = {}
        passos = habilidade.executar(ctx, pergunta=pergunta, top=payload.top, apenas=citado)
        try:
            for tipo, dados in passos:
                if parar.is_set():
                    break
                if tipo == "fontes":
                    andamento["documentos"] = len(dados.get("consultados") or [])
                    nivel = dados.get("nivel", nivel)
                    inferencia = bool(dados.get("inferencia", inferencia))
                    cobertura = {
                        "consultados": dados["consultados"],
                        "ignorados": dados["ignorados"],
                        "total_contratos": dados["total_contratos"],
                        "apenas": dados.get("apenas") or [],
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
                    fase("lendo")
                    previsao = dados.get("previsao") or {}
                    andamento["previsao_s"] = previsao.get("segundos", 0) if previsao.get("sabe") else 0
                    andamento["caracteres"] = dados.get("caracteres", 0)
                    lido_chars = dados["caracteres"]
                    medir.update(caminho=dados.get("caminho"), fallback=bool(dados.get("fallback")),
                                 trechos=dados.get("trechos", 0), modelo=dados.get("modelo", estado.client.model),
                                 molde=bool(dados.get("molde")))
                    trabalho.etapas[1].titulo = "Lendo os documentos"
                    trabalho.etapas[1].estado = EXECUTANDO
                    trabalho.etapas[1].detalhe = f"{dados['caracteres']:,}".replace(",", ".") + " caracteres"
                    yield _sse("lendo", dados)
                    yield _sse("etapas", {"etapas": [asdict_etapa(e) for e in trabalho.etapas]})
                elif tipo == "escrevendo":
                    fase("escrevendo")
                    # A leitura acabou de verdade: a primeira palavra saiu.
                    trabalho.etapas[1].estado = CONCLUIDO
                    trabalho.etapas[1].detalhe = f"{dados['lendo_segundos']} s"
                    trabalho.etapas.append(Etapa("Escrevendo a resposta", estado=EXECUTANDO))
                    yield _sse("escrevendo", dados)
                    yield _sse("etapas", {"etapas": [asdict_etapa(e) for e in trabalho.etapas]})
                elif tipo == "fila":
                    # N11: a resposta que voltou do aparelho esperando a vez no escritório.
                    fase("fila")
                    andamento.update(posicao=dados.get("posicao"), previsao_s=dados.get("previsao_s", 0))
                    if not fila_de_todos.ligada(estado):
                        dados = {"posicao": dados.get("posicao"), "previsao_s": dados.get("previsao_s", 0),
                                 "depois_do_aparelho": True}
                    yield _sse("fila", dados)
                elif tipo in ("nuvem_pedido", "nuvem_mandando", "nuvem_fim"):
                    # N15: a pergunta esperando o sim para ir à nuvem, indo, e onde terminou.
                    fase({"nuvem_pedido": "nuvem_esperando", "nuvem_mandando": "nuvem"}.get(tipo, "escrevendo"))
                    yield _sse(tipo, dados)
                elif tipo == "medida":
                    medida = dados
                    yield _sse("medida", dados)
                elif tipo == "contagem":
                    medir["contagem"] = dados
                elif tipo == "revisao":
                    # O texto conferido (I8) toma o lugar do que foi escrito:
                    # e ele que fica na conversa.
                    partes[:] = [dados.get("texto", "")]
                    yield _sse("revisao", dados)
                elif tipo == "refazendo":
                    yield _sse("refazendo", dados)
                elif tipo == "suspeita":
                    # C6: frase de "ordem ao assistente" num trecho lido - o
                    # modelo a leu cercada; aqui fica o registro.
                    _registrar_suspeita(trabalho, pergunta, dados)
                    yield _sse("suspeita", dados)
                elif tipo == "sem_fundamento":
                    sem_fundamento = {
                        "tipo": "escopo", "motivo": "sem_fundamento", "pergunta": pergunta,
                        "nomes": list(dados.get("documentos") or [])[:4],
                        "total": len(estado.searcher.documents),
                    }
                elif tipo == "truncou":
                    # O prompt nao coube na janela: o Ollama cortou o comeco
                    # calado (src/inferencia.py). A tela diz, e a resposta
                    # guarda o aviso.
                    medir["truncou"] = True
                    cobertura["truncou"] = True
                    yield _sse("truncou", dados)
                elif tipo == "token":
                    partes.append(dados["t"])
                    # Contar a cada dez pedacos basta para o cartao, e nao
                    # refaz a conta do texto inteiro a cada palavra.
                    if len(partes) % 10 == 0:
                        andamento["palavras"] = len("".join(partes).split())
                    yield _sse("token", dados)
                elif tipo == "vazio":
                    trabalho.etapas[0].estado = CONCLUIDO
                    trabalho.etapas[1].estado = CONCLUIDO
                    trabalho.estado = CONCLUIDO
                    trabalho.dizer("paulus", dados["mensagem"])
                    estado.trabalhos.salvar(trabalho)
                    medir["caminho"] = dados.get("caminho") or medir["caminho"]
                    medir_agora()
                    yield _sse("vazio", dados)
                    return
                elif tipo in ("aparelho", "aparelho_fim"):
                    # D1: o id e a assinatura do pacote (o conteudo sai pela
                    # rota, para a mesma sessao), e onde a resposta foi escrita.
                    yield _sse(tipo, dados)
                elif tipo == "fim":
                    pass  # o fechamento e daqui: o modulo nao sabe de trabalho
        except Exception as exc:
            trabalho.etapas[1].estado = "falhou"
            trabalho.estado = "falhou"
            estado.trabalhos.salvar(trabalho)
            yield _sse("erro", {"mensagem": str(exc)})
            return

        segundos = round(time.time() - inicio, 1)

        # Parou no meio: guarda o que o modelo ja tinha escrito, marcado como
        # interrompido, e a conversa fica "parada" - da para perguntar de novo.
        # Nada disso entra no historico de ritmo: uma leitura cortada nao e
        # medida de quanto esta maquina leva.
        if parar.is_set():
            passos.close()
            pausar_o_que_executava()
            escrito = "".join(partes).strip()
            if escrito:
                trabalho.dizer(
                    "paulus", escrito,
                    fontes=fontes, cobertura=_como_pensou(id_, cobertura), segundos=segundos,
                    nivel=nivel, inferencia=inferencia, interrompida=True,
                )
            estado.trabalhos.salvar(trabalho)
            yield _sse("parado", {"segundos": segundos, "titulo": trabalho.titulo, "escreveu": bool(escrito)})
            return

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

        medir_agora()

        for etapa in trabalho.etapas:
            if etapa.estado == EXECUTANDO:
                etapa.estado = CONCLUIDO
        trabalho.estado = CONCLUIDO
        # Quer ver o documento? A oferta sai por regra dos trechos usados, e
        # fica guardada na propria resposta - e assim que a conversa sabe que
        # ja ofereceu e nao oferece o mesmo arquivo de novo.
        # Como a resposta foi feita, para a tela dizer em linguagem simples
        # (I9): "respondi pelos fatos ja conferidos, em 0,1 s", "li 6 trechos
        # de 2 documentos, em 34 s". Fica com a resposta.
        cobertura["como"] = {"caminho": medir.get("caminho"), "trechos": medir.get("trechos", 0),
                             "documentos": len(cobertura.get("consultados") or []),
                             "molde": bool(medir.get("molde")),
                             # C3: o que o painel "Sobre esta resposta" mostra
                             # desta resposta, e nao do estado de agora.
                             "modelo": medir.get("modelo") or "", "continuacao": bool(continuou),
                             "escopo": {"apenas": list(citado or []), "tudo": bool(payload.tudo),
                                        "sem_anexo": bool(payload.sem_anexo)},
                             "truncou": bool(medir.get("truncou")),
                             # A2: o agente que respondeu, e a versao dele.
                             "agente": (agente.nome or agente.slug) if agente is not None else "",
                             "agente_slug": agente.slug if agente is not None else "",
                             "agente_versao": agente.versao if agente is not None else 0,
                             "agente_como": agente_como}
        # N15: a nuvem - onde foi escrita, o provedor e o modelo, o que foi mascarado.
        if envio_nuvem is not None:
            cobertura["como"]["nuvem"] = envio_nuvem.resumo()
            if envio_nuvem.foi:
                cobertura["como"]["modelo"] = f"{envio_nuvem.nome_do_provedor} · {envio_nuvem.modelo}"
        # D1: onde a resposta foi escrita e por que, quando a pessoa pediu o aparelho.
        # D4: com o seletor na tela, a escolha da pessoa tambem fica dita.
        if payload.aparelho or payload.escolha in aparelho_mod.ESCOLHAS:
            cobertura["como"]["escrita"] = (escrita_no_aparelho.resumo() if escrita_no_aparelho is not None
                                            else {"onde": "escritorio",
                                                  "motivo": (motivo_do_escritorio if payload.aparelho
                                                             else aparelho_mod.ESCOLHAS[payload.escolha]),
                                                  "conferida": False, "pacote": False})
            # Escrita inteira no aparelho: o modelo da resposta e o do aparelho.
            if cobertura["como"]["escrita"].get("onde") == "aparelho" and cobertura["como"]["escrita"].get("modelo"):
                cobertura["como"]["modelo"] = cobertura["como"]["escrita"]["modelo"]
            if payload.escolha == "automatico" and escrita_no_aparelho is not None:
                cobertura["como"]["escrita"]["automatico"] = True
            # D5: a linha do fim na auditoria (o relatorio do titular sai dela).
            if escrita_no_aparelho is not None:
                escrita_no_aparelho.fechar()
            # D3: na resposta retomada, a parte do escritorio e o que veio depois do parcial.
            pedacos = cobertura["como"]["escrita"].get("partes") or []
            if len(pedacos) == 2 and pedacos[1]["onde"] == "escritorio":
                pedacos[1]["caracteres"] = max(0, len("".join(partes).strip()) - pedacos[0]["caracteres"])
        oferta = sem_fundamento or ferramentas.oferta_de_exibir(
            fontes, estado.searcher.documents, _documentos_ja_oferecidos(trabalho))
        # N7: os temas e as súmulas ligados aos artigos que a conversa citou, e a
        # posição da casa - por regra, embaixo da resposta, sem mudar o texto.
        relacionados = None
        if (estado.prefs.dados.get("conversa") or {}).get("relacionados", True):
            try:
                import fundamentacao as _fund

                relacionados = _fund.relacionados(estado, pergunta, "".join(partes), fontes)
            except Exception:  # noqa: BLE001 - sem o bloco, a resposta vale igual
                relacionados = None
        if relacionados:
            cobertura["relacionados"] = relacionados
        trabalho.dizer(
            "paulus", "".join(partes).strip(),
            fontes=fontes, cobertura=_como_pensou(id_, cobertura), segundos=segundos,
            nivel=nivel, inferencia=inferencia, proposta=oferta or {},
        )
        estado.trabalhos.salvar(trabalho)
        # Uma resposta leva cerca de um minuto nesta maquina: quem foi para
        # outra janela esperar fica sabendo que acabou.
        resumo = " ".join("".join(partes).split())
        avisos.avisar("resposta", "Resposta pronta · " + (trabalho.titulo or "Conversa")[:60],
                      resumo[:140] + ("…" if len(resumo) > 140 else ""))
        yield _sse("fim", {"segundos": segundos, "titulo": trabalho.titulo, "como": cobertura.get("como")})
        if relacionados:
            yield _sse("relacionados", relacionados)
        if oferta:
            yield _sse("oferta", oferta)

    # C1: com `conversa.execucao`, a resposta roda numa thread de trabalho e
    # esta conexao e so uma inscricao nela (src/execucoes.py) - fechar a
    # janela nao para nada, e a tela se reinscreve ao voltar.
    if rotas_execucoes.ligada(estado, "execucao"):
        return rotas_execucoes.rodar_conversa(estado, id_, dono, gerar())
    return StreamingResponse(
        gerar(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sem_modelo(habilidade, pergunta: str, citado) -> bool:
    """
    A pergunta sai sem o modelo (molde ou regra)? Quem sabe e a habilidade
    (habilidades/perguntar.py, `sem_modelo`); na duvida, a fila de sempre.
    """
    import inspect

    decidir = getattr(inspect.getmodule(habilidade.executar), "sem_modelo", None)
    if decidir is None:
        return False
    try:
        return bool(decidir(_contexto(), pergunta, apenas=citado))
    except Exception:  # noqa: BLE001 - errar aqui so custa esperar a vez
        return False


def _documentos_ja_oferecidos(trabalho) -> set[str]:
    """
    Os arquivos que esta conversa ja ofereceu mostrar, ja mostrou, ou que a
    pessoa pediu para abrir - o cartao deles continua na conversa, e oferecer
    de novo embaixo da resposta seguinte seria o mesmo convite duas vezes.
    """
    vistos: set[str] = set()
    for m in trabalho.mensagens:
        proposta = m.proposta or {}
        if proposta.get("tipo") == "exibir":
            vistos.update(proposta.get("nomes") or (proposta.get("campos") or {}).get("nomes") or [])
        if proposta.get("tipo") == "abrir" and (proposta.get("campos") or {}).get("nome"):
            vistos.add(proposta["campos"]["nome"])
        if (m.feito or {}).get("tipo") in ("exibir", "abrir", "editar") and (m.feito or {}).get("nome"):
            vistos.add(m.feito["nome"])
    return vistos


class PropostaConfirmada(BaseModel):
    tipo: str = ""
    campos: dict = {}
    # A2: o pedido na fila de Aprovacoes que acompanha a proposta de um agente.
    pedido_id: str = ""


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
    pendente = False
    # A2: a proposta de um agente que ja foi decidida em Aprovacoes nao grava
    # de novo pelo cartao.
    if payload.pedido_id:
        pedido = next((p for p in estado.fila.pendentes if p.id == payload.pedido_id), None)
        if pedido is None:
            raise HTTPException(status_code=409, detail="este pedido já foi decidido em Aprovações")
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
        elif payload.tipo in ferramentas.POR_PROPOSTA:
            # Agenda, cadastro e nota fiscal: as ferramentas do catalogo. O
            # catalogo confere os campos do jeito que o modelo e a tela os
            # mandam, e so entao grava - ou, na NFS-e, so confere.
            feito_ferramenta = ferramentas.executar(ferramentas.POR_PROPOSTA[payload.tipo], campos, estado)
            novo = feito_ferramenta["id"]
            feito = feito_ferramenta["registro"]
            resumo = feito_ferramenta["resumo"]
            onde = feito_ferramenta["onde"]
            pendente = bool(feito_ferramenta.get("pendente"))
        elif payload.tipo == "tarefa":
            novo = estado.tarefas.salvar(campos)
            feito = estado.tarefas.obter(novo)
            resumo = f"Criei a tarefa “{feito['titulo']}”"
            if feito.get("prazo"):
                resumo += f", com prazo em {escritorio._br(feito['prazo'])}"
            onde = "tarefas"
        elif payload.tipo == "servico":
            # A pasta de trabalho nasce da conversa (docs/ui, A15). O cliente
            # e ligado pelo nome como esta em Cadastros; sem ficha, a pasta
            # abre sem cliente e o resumo diz isso.
            nome_cliente = " ".join(str(campos.get("cliente", "")).split())
            ficha = None
            if nome_cliente:
                ficha = next((f for f in estado.cadastros.listar()
                              if " ".join(f["nome"].split()).lower() == nome_cliente.lower()), None)
            novo = estado.servicos.salvar({
                "nome": str(campos.get("nome", "")), "cadastro_id": ficha["id"] if ficha else None,
                "descricao": str(campos.get("descricao", "")),
            })
            estado.servicos.trilha(novo, "Serviço aberto a partir da conversa “" + trabalho.titulo + "”")
            feito = estado.servicos.obter(novo)
            resumo = f"Abri o serviço “{feito['nome']}”"
            if feito.get("cliente_nome"):
                resumo += f" para {feito['cliente_nome']}"
            elif nome_cliente:
                resumo += f" sem cliente ligado — “{nome_cliente}” não está em Cadastros"
            onde = "servicos"
        elif payload.tipo == "gravacao":
            # A gravacao feita na conversa (`Conversa - Gravando`) ja foi
            # arquivada pela tela (POST /api/gravacoes); aqui ela entra na
            # conversa, com o caminho para a gravacao.
            g = estado.gravacoes.obter(int(campos.get("id") or 0))
            if not g:
                raise HTTPException(status_code=404, detail="essa gravação não está mais aqui")
            novo = g["id"]
            feito = g
            minutos, segundos = divmod(int(g.get("duracao_s") or 0), 60)
            duracao = (f"{minutos} min {segundos:02d} s" if minutos else f"{segundos} s")
            sugeridas = int(campos.get("sugestoes") or 0)
            resumo = (f"Gravei “{g.get('titulo') or 'a reunião'}” ({duracao}) e arquivei em Gravações, com a transcrição"
                      + (f" e {sugeridas} sugest{'ão' if sugeridas == 1 else 'ões'} de resposta" if sugeridas else ""))
            onde = "gravacoes"
            campos["nome"] = g.get("titulo") or ""
        elif payload.tipo == "config":
            # T5: o que a coluna de Configuracoes salvou pela rota de sempre
            # (POST /api/preferencias, /api/contextos, /api/backup...). Aqui so
            # entra na conversa, com o resumo escrito daqui pelas chaves.
            import config_pela_conversa as cpc

            secao = str(campos.get("secao") or "")
            if secao not in cpc.SECOES:
                raise HTTPException(status_code=400, detail="seção desconhecida")
            acao = str(campos.get("acao") or "salvar")
            nomes = [cpc.rotulo(str(c)) for c in (campos.get("chaves") or [])][:8]
            juntar = lambda xs: ", ".join(xs[:-1]) + " e " + xs[-1] if len(xs) > 1 else (xs[0] if xs else "")  # noqa: E731
            rotulo_secao = cpc.SECOES[secao][0]
            titulos = [str(t)[:120] for t in (campos.get("titulos") or [])][:5]
            if acao == "restaurar":
                resumo = "Restaurei " + juntar(["“" + t + "”" for t in titulos]) + " da Lixeira"
            elif acao == "lembrete":
                resumo = "Guardei o lembrete do escritório: ele entra em toda pergunta da conversa"
            elif acao == "backup":
                resumo = "Guardei a pasta e a senha do backup e comecei o primeiro"
            elif acao == "teste":
                resumo = "Medi " + juntar(titulos) + " nesta máquina" if titulos else "Parei o teste dos modelos"
            elif acao == "word":
                resumo = "Instalei o PAVLVS no Word deste computador"
            else:
                resumo = f"Salvei em {rotulo_secao}" + (": " + juntar([n[:1].lower() + n[1:] if not n.isupper() else n for n in nomes]) if nomes else "")
            novo = 0
            feito = {"secao": secao, "acao": acao}
            onde = "config"
            campos["nome"] = rotulo_secao
        elif payload.tipo == "lancamento":
            # O lancamento feito pela coluna: quem gravou foi POST
            # /api/financeiro/lancar-pela-conversa; aqui ele entra na conversa.
            l = estado.financeiro.obter(int(campos.get("id") or 0))
            if not l:
                raise HTTPException(status_code=404, detail="não achei esse lançamento")
            novo = l["id"]
            feito = l
            if l["tipo"] == "recebimento":
                resumo = f"Lancei o recebimento de {l.get('valor')} (“{l['descricao']}”)" + (" como recebido em " + escritorio._br(l["liquidado_em"]) if l.get("liquidado_em") else "")
            else:
                resumo = f"Lancei a despesa de {l.get('valor')} (“{l['descricao']}”)" + (", vence " + escritorio._br(l["vencimento"]) if l.get("vencimento") else "")
            if campos.get("papel"):
                resumo += ", com o " + str(campos["papel"]) + " guardado"
            if campos.get("tarefa"):
                resumo += " e o lembrete na Agenda"
            onde = "financeiro"
            campos["nome"] = l["descricao"]
        elif payload.tipo == "ficha":
            # A ficha salva pela coluna (`Conversa - Cadastro`, `- Equipe`,
            # `- Despesa fixa`): quem gravou foi POST /api/cadastros; aqui ela
            # entra na conversa. A ficha tem de existir.
            ficha = estado.cadastros.obter(int(campos.get("id") or 0))
            if not ficha:
                raise HTTPException(status_code=404, detail="não achei essa ficha")
            novo = ficha["id"]
            feito = ficha
            ligados = int(campos.get("ligados") or 0)
            if ficha["tipo"] == "despesa":
                resumo = f"Cadastrei a despesa fixa “{ficha['nome']}”" + (f", {ficha['honorario']}" if ficha.get("honorario") else "") + \
                         (f" todo dia {ficha['dia_vencimento']}" if ficha.get("dia_vencimento") else "")
                onde = "cadastros"
            elif ficha["tipo"] in ("socio", "colaborador"):
                resumo = f"Pus {ficha['nome']} na equipe como {'sócio' if ficha['tipo'] == 'socio' else 'colaborador'}"
                if campos.get("convite"):
                    resumo += " e gerei o convite para o PAULUS"
                onde = "equipe"
            else:
                resumo = f"Cadastrei “{ficha['nome']}” como cliente" + (f", ligado a {ligados} documento{'s' if ligados != 1 else ''}" if ligados else "")
                onde = "cadastros"
            campos["nome"] = ficha["nome"]
        elif payload.tipo == "email":
            # A resposta enviada pela conversa (`Conversa - Escrever e-mail`):
            # quem enviou foi POST /api/email/enviar, com o sim; aqui o
            # resultado entra na conversa. Enviado direto, tem de estar no
            # registro de envios.
            assunto = str(campos.get("assunto") or "")
            para = ", ".join(str(x) for x in (campos.get("para") or [])[:3])
            novo = 0
            feito = {}
            if campos.get("aguardando"):
                resumo = f"Deixei a resposta “{assunto}” para {para} esperando o seu sim em Aprovações"
                onde = "aprovacoes"
            else:
                if not any(e.get("assunto") == assunto for e in estado.envios.para_tela(10)["envios"]):
                    raise HTTPException(status_code=404, detail="não achei esse envio no registro")
                resumo = f"Enviei “{assunto}” para {para}"
                onde = "caixa"
            campos["nome"] = assunto
        elif payload.tipo == "assinatura":
            # A assinatura feita pela conversa (`Conversa - Assinar`): quem
            # assinou foi POST /api/assinar, com o sim e a senha; aqui o
            # resultado entra na conversa. O arquivo assinado tem de existir.
            nome = str(campos.get("nome") or "")
            novo = 0
            feito = {}
            if campos.get("aguardando"):
                resumo = f"Deixei a assinatura de “{nome}” esperando o seu sim em Aprovações"
                onde = "aprovacoes"
            else:
                destino = Path(str(campos.get("destino") or ""))
                if not destino.exists():
                    raise HTTPException(status_code=404, detail="não achei o arquivo assinado")
                titular = str(campos.get("titular") or "").strip()
                codigo = str(campos.get("codigo") or "").strip()
                resumo = (f"Assinei “{nome}”" + (f" com o certificado de {titular}" if titular else "")
                          + f" e guardei como “{destino.name}”" + (f" (código {codigo})" if codigo else ""))
                onde = "assinar"
                campos["nome"] = destino.name
        else:
            raise HTTPException(status_code=400, detail="nao sei fazer isso")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    trabalho.dizer("paulus", resumo + ".", feito={"tipo": payload.tipo, "id": novo, "onde": onde,
                                                  "pendente": pendente, "nome": str(campos.get("nome", ""))})
    estado.trabalhos.salvar(trabalho)
    if payload.pedido_id:
        estado.fila.decidir(payload.pedido_id, True)
        estado.fila.registrar_resultado(payload.pedido_id, resumo + " (confirmado no cartão da conversa)")
    return {"id": novo, "resumo": resumo, "onde": onde, "registro": feito, "pendente": pendente}


def _responder_gravacao(trabalho, lido, pergunta: str) -> StreamingResponse:
    """
    "Grave a reuniao com a Rio Fresco e me ajude a responder": a conversa
    devolve o que a tela precisa para gravar ali mesmo - o titulo, o tipo, a
    ficha do cliente, os documentos do caso - e diz o que vai acontecer. Quem
    abre o microfone e a tela (o audio fica nesta maquina, src/gravacoes.py).
    """
    import sugestoes_ao_vivo as sav

    campos = dict(lido.campos)
    nome = campos.get("cliente") or ""
    ficha = None
    if nome:
        alvo = " ".join(nome.split()).lower()
        fichas = estado.cadastros.listar()
        ficha = next((f for f in fichas if " ".join(f["nome"].split()).lower() == alvo), None) or \
            next((f for f in fichas if alvo and alvo in " ".join(f["nome"].split()).lower()), None)
    if ficha:
        campos["cadastro_id"] = ficha["id"]
        campos["cliente"] = ficha["nome"]
        campos["titulo"] = (campos.get("titulo") or "Reunião").split(" · ")[0] + " · " + ficha["nome"]
    documentos = sav.documentos_do_caso(estado, campos.get("cliente", ""), campos.get("cadastro_id"))
    campos["documentos"] = documentos
    if campos.get("ajudar") and documentos:
        citados = " e ".join(", ".join(f"“{n}”" for n in documentos[:2]).rsplit(", ", 1)) if len(documentos) > 1 else f"“{documentos[0]}”"
        texto = (f"Gravando. Vou transcrever aqui e, quando algo dito cruzar com {citados}"
                 f"{' e os outros documentos do caso' if len(documentos) > 2 else ''}, sugiro uma resposta logo abaixo da fala.")
    elif campos.get("ajudar"):
        texto = ("Gravando. Vou transcrever aqui. Não achei documentos do caso para cruzar com o que for dito: "
                 "anexe ou aponte a pasta, e eu passo a sugerir respostas.")
    else:
        texto = "Gravando. Vou transcrever aqui; o áudio e a transcrição ficam nesta máquina."
    proposta = {"tipo": "gravar", "titulo": campos.get("titulo", ""), "campos": campos, "porque": lido.porque,
                "pergunta": pergunta, "texto": texto}

    def gerar() -> Iterator[str]:
        # A conversa que comeca pelo pedido de gravar ganha o nome da gravacao
        # ("Reuniao · Cooperativa Rio Fresco"), como no desenho.
        if len(trabalho.mensagens) <= 1 and campos.get("titulo"):
            trabalho.titulo = titular(campos["titulo"])
        trabalho.etapas = [Etapa("Entender o pedido", estado=CONCLUIDO)]
        trabalho.estado = CONCLUIDO
        trabalho.dizer("paulus", texto, proposta=proposta)
        estado.trabalhos.salvar(trabalho)
        yield _sse("token", {"t": texto})
        yield _sse("proposta", proposta)
        yield _sse("fim", {"segundos": 0, "titulo": trabalho.titulo})

    return StreamingResponse(gerar(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _responder_assinatura(trabalho, lido, pergunta: str) -> StreamingResponse:
    """
    "Assine o contrato de honorarios": a conversa diz onde o selo entra (o
    canto que o certificado guarda, na ultima pagina) e manda a tela abrir o
    PDF ao lado. Nada e assinado aqui - o sim (e a senha) vem do clique.
    """
    campos = dict(lido.campos)
    nome = campos.get("nome", "")
    doc = next((d for d in estado.searcher.documents if d.name == nome), None)
    proposta = None
    if not doc:
        texto = f"Não achei “{nome}” aberto no Acervo agora."
    elif campos.get("nao_pdf") or Path(doc.path).suffix.lower() != ".pdf":
        texto = (f"Só assino PDF, e “{nome}” não é. Abra no editor e use Assinar: eu gero o PDF, "
                 "guardo no Acervo e abro a assinatura nele.")
        proposta = {"tipo": "exibir", "titulo": nome, "campos": {"nome": nome}, "nomes": [nome],
                    "porque": "é o documento que você pediu para assinar"}
    else:
        cofre = estado.cofre.para_tela()
        posicao = (cofre.get("selo") or {}).get("posicao") or "rodape_direita"
        rotulo = next((p["rotulo"] for p in cofre.get("posicoes") or [] if p.get("valor") == posicao), "")
        onde = {"rodape_direita": "no rodapé da última página, à direita", "rodape_esquerda": "no rodapé da última página, à esquerda",
                "rodape_centro": "no rodapé da última página, no meio", "topo_direita": "no alto da última página, à direita"}.get(
            posicao, ("na última página (" + rotulo.lower() + ")") if rotulo else "na última página")
        texto = f"Coloquei a assinatura {onde}. Confira ao lado, ajuste o que quiser aqui e assine."
        if not cofre.get("instalado"):
            texto += " Falta o certificado: instale o seu e-CPF antes de assinar."
        proposta = {"tipo": "assinar", "titulo": nome, "campos": {"nome": nome, "caminho": str(doc.path)},
                    "porque": lido.porque, "pergunta": pergunta}

    def gerar() -> Iterator[str]:
        trabalho.etapas = [Etapa("Entender o pedido", estado=CONCLUIDO)]
        trabalho.estado = CONCLUIDO
        trabalho.dizer("paulus", texto, proposta=proposta)
        estado.trabalhos.salvar(trabalho)
        yield _sse("token", {"t": texto})
        if proposta:
            yield _sse("proposta", proposta)
        yield _sse("fim", {"segundos": 0, "titulo": trabalho.titulo})

    return StreamingResponse(gerar(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _documentos_citados(nomes) -> list:
    abertos = {d.name: d for d in estado.searcher.documents}
    return [abertos[n] for n in (nomes or []) if n in abertos]


def _responder_ficha(trabalho, lido, pergunta: str, citados=None) -> StreamingResponse:
    """
    A ficha pela conversa: o cliente (o nome procurado no Acervo, com o
    CPF/CNPJ e o endereco que estao perto dele), a pessoa da equipe (o que a
    frase disse) e a despesa fixa (o contrato anexo, lido por regra). A frase
    diz o que foi achado; a ficha abre na coluna e so grava no clique.
    """
    import fichas_pela_conversa as fpc

    campos = dict(lido.campos)
    tipo = campos.get("tipo") or "cliente"
    hoje = date.today()
    ficha: dict = {"tipo": tipo, "nome": campos.get("nome", "")}
    origem: dict = {}
    achados = None
    if lido.tipo == "cadastro":
        tipo = ficha["tipo"] = "cliente"
        ficha.update({k: campos.get(k, "") for k in ("documento", "telefone", "email", "endereco", "observacao")})
        achados = fpc.achar_no_acervo(ficha["nome"], estado.searcher.documents, limite=40)
        for chave in ("documento", "endereco"):
            if not ficha.get(chave) and achados["campos"].get(chave):
                ficha[chave] = achados["campos"][chave]
                origem[chave] = achados["origem"].get(chave, 0)
        if achados["total"]:
            origem["nome"] = achados["total"]
            lido_no_doc = achados.get("nome_mais_lido", "")
            if lido_no_doc and fpc._plano(lido_no_doc).startswith(fpc._plano(ficha["nome"])):
                ficha["nome"] = lido_no_doc
        import campos_br

        ficha["pessoa"] = "juridica" if (fpc.parece_pj(ficha["nome"]) or campos_br.e_cnpj(ficha.get("documento", ""))) else "fisica"
        sugestoes = estado.cadastros.sugestoes(CLASSIFICACAO_PATH, limite=None)
        alvo = fpc._plano(ficha["nome"])
        sugestao = next((s for s in sugestoes if fpc._plano(s.get("nome", "")) == alvo), None)
        ficha["sugestoes_pendentes"] = max(0, len(sugestoes) - (1 if sugestao else 0))
        n = achados["total"]
        ligados = min(6, sum(1 for x in achados["documentos"] if len(x["campos"]) > 1))
        if n:
            mostrado = fpc._nome_proprio(ficha["nome"].lower()) if ficha["nome"].isupper() else ficha["nome"]
            texto = (f"Achei {mostrado} em "
                     f"{n} documento{'s' if n != 1 else ''} do Acervo e preenchi a ficha ao lado com o que estava neles. "
                     "Confira o nome e o documento; o resto, se souber. "
                     f"Ao salvar, a ficha nasce ligada a {ligados} documento{'s' if ligados != 1 else ''}.")
        else:
            texto = (f"Não achei “{ficha['nome']}” nos documentos do Acervo. Preenchi a ficha ao lado com o que você disse; "
                     "complete o que souber e salve.")
    elif tipo in ("colaborador", "socio"):
        ficha.update({"funcao": campos.get("funcao", ""), "email": campos.get("email", ""), "salario": campos.get("salario", ""),
                      "inicio": campos.get("inicio", ""), "vinculo": campos.get("vinculo", ""),
                      "convidar": bool(campos.get("convidar"))})
        papel = "sócia" if tipo == "socio" else ("colaboradora" if (campos.get("funcao", "").endswith("a")) else "colaborador")
        partes = [f"Preenchi a ficha ao lado como {papel}"]
        if ficha["salario"]:
            partes[0] += ", entrando na folha" + (f" a partir de {escritorio._br(ficha['inicio'])[:5]}" if ficha["inicio"] else "")
        texto = partes[0] + "."
        if ficha["convidar"]:
            texto += (" O convite gera o link de entrada para " + (ficha["email"] or "o e-mail Google dela") +
                      " quando você clicar em Salvar e convidar.")
        if not ficha["nome"]:
            texto = "Não achei o nome da pessoa nessa frase. Preenchi o que deu na ficha ao lado."
    else:
        ficha.update({"valor": campos.get("valor", ""), "dia": campos.get("dia", 0)})
        contrato = {}
        lido_de = ""
        for d in _documentos_citados(citados):
            contrato = fpc.ler_contrato(d.text or "")
            if contrato:
                lido_de = d.name
                break
        for chave in ("valor", "dia"):
            if not ficha.get(chave) and contrato.get(chave):
                ficha[chave] = contrato[chave]
                origem[chave] = 1
        if contrato.get("fornecedor"):
            ficha["fornecedor"] = contrato["fornecedor"]
            origem["fornecedor"] = 1
        for chave in ("documento", "email"):
            if contrato.get(chave):
                ficha[chave] = contrato[chave]
        nota = [contrato.get("reajuste", ""), ("contrato até " + contrato["ate"]) if contrato.get("ate") else ""]
        ficha["observacao"] = " · ".join(x for x in nota if x)
        if ficha["nome"]:
            origem["nome"] = 1 if lido_de else 0
        ficha["lido_de"] = lido_de
        ficha["avisar_dias"] = 3
        ficha["lancar_mensal"] = True
        if lido_de:
            dito = [ficha.get("valor") or "", f"todo dia {ficha['dia']}" if ficha.get("dia") else ""]
            texto = (f"Li “{lido_de}” e preenchi a despesa ao lado: " + ", ".join(x for x in dito if x) +
                     (f", com {contrato['reajuste'][0].lower() + contrato['reajuste'][1:]}" if contrato.get("reajuste") else "") +
                     ". Vou lembrar 3 dias antes e lançar no Financeiro todo mês.")
        else:
            texto = ("Preenchi a despesa ao lado com o que você disse" +
                     ("" if ficha.get("valor") else "; falta o valor") + ". Ela entra no Financeiro todo mês, se você deixar ligado.")
    ficha["origem"] = origem
    proposta = {"tipo": "ficha", "titulo": ficha["nome"], "campos": ficha, "porque": lido.porque, "pergunta": pergunta,
                "achados": achados}

    def gerar() -> Iterator[str]:
        trabalho.etapas = [Etapa("Preencher a ficha", estado=CONCLUIDO)]
        trabalho.estado = CONCLUIDO
        trabalho.dizer("paulus", texto, proposta=proposta)
        estado.trabalhos.salvar(trabalho)
        yield _sse("token", {"t": texto})
        yield _sse("proposta", proposta)
        yield _sse("fim", {"segundos": 0, "titulo": trabalho.titulo})

    return StreamingResponse(gerar(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _gerar_relatorio_financeiro(mes: str, comparar: str) -> dict:
    """O PDF (Relatorios/Financeiro do Acervo) e a planilha do mes (Financeiro/Planilhas)."""
    import financeiro_pela_conversa as fpc

    r = fpc.relatorio(estado.financeiro, estado.base, mes, comparar)
    pasta = _pasta_no_acervo("Relatórios", "Financeiro")
    pdf = pasta / f"relatorio-financeiro-{mes}.pdf"
    pdf.write_bytes(documento.para_pdf(documento.ler_html(fpc.html_do_relatorio(r, _escapar)),
                                       f"Relatório financeiro · {r['rotulo']} {r['ano']}", "PAULUS · relatório gerado nesta máquina"))
    xlsx = _pasta_no_acervo("Financeiro", "Planilhas") / f"financeiro-{mes}.xlsx"
    _exportar_mes_em(xlsx, mes)
    estado.recarregar_em_segundo_plano()
    return {"relatorio": r, "pdf": {"nome": pdf.name, "caminho": str(pdf)}, "xlsx": {"nome": xlsx.name, "caminho": str(xlsx)}}


def _responder_financeiro(trabalho, lido, pergunta: str) -> StreamingResponse:
    """
    "Como está o financeiro do mês?" / "gera o relatório financeiro de
    outubro": a frase sai dos numeros somados aqui (src/financeiro_pela_conversa.py);
    o relatorio ja nasce com o PDF e a planilha no Acervo.
    """
    import financeiro_pela_conversa as fpc

    c = dict(lido.campos)
    mes, comparar = c.get("mes") or escritorio.mes_de_hoje(), c.get("comparar") or ""
    estado.financeiro.lancar_fixas(estado.cadastros.listar(tipo="despesa"))
    precisa = estado.financeiro.precisa_de_voce()
    if lido.tipo == "relatorio":
        try:
            gerado = _gerar_relatorio_financeiro(mes, comparar)
            texto = fpc.frase_do_relatorio(gerado["relatorio"])
        except Exception as exc:  # noqa: BLE001 - o relatorio diz o que houve, a conversa segue
            gerado = None
            texto = f"Não consegui gerar o relatório agora: {exc}."
        proposta = {"tipo": "relatorio", "titulo": "Relatório financeiro", "porque": lido.porque, "pergunta": pergunta,
                    "campos": {"mes": mes, "comparar": comparar,
                               "pdf": (gerado or {}).get("pdf"), "xlsx": (gerado or {}).get("xlsx")}}
    else:
        texto = fpc.frase_do_financeiro(estado.financeiro, mes, precisa)
        proposta = {"tipo": "financeiro", "titulo": "Financeiro", "porque": lido.porque, "pergunta": pergunta,
                    "campos": {"mes": mes, "comparar": comparar}}

    def gerar() -> Iterator[str]:
        trabalho.etapas = [Etapa("Somar o mês", estado=CONCLUIDO)]
        trabalho.estado = CONCLUIDO
        trabalho.dizer("paulus", texto, proposta=proposta)
        estado.trabalhos.salvar(trabalho)
        yield _sse("token", {"t": texto})
        yield _sse("proposta", proposta)
        yield _sse("fim", {"segundos": 0, "titulo": trabalho.titulo})

    return StreamingResponse(gerar(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _dados_da_config(secao: str, pedido: dict) -> dict:
    """O que a frase de cada secao de Configuracoes precisa ler agora (src/config_pela_conversa.py)."""
    dados: dict = {"prefs": estado.prefs.dados, "padrao": estado.client.model}
    try:
        if secao == "assistente":
            try:
                dados["modelos"] = [m["nome"] for m in modelos_mod.instalados(estado.client.host)]
            except Exception:  # noqa: BLE001 - Ollama fora: o modelo pedido nao e conferido
                dados["modelos"] = []
        elif secao == "modelos" or (secao == "desempenho" and pedido.get("teste")):
            listado = modelos_listar()
            dados.update({"instalados": listado.get("instalados") or [], "tarefas": listado.get("tarefas") or [],
                          "padrao": listado.get("padrao") or estado.client.model})
            dados["memoria_total_gb"] = (recursos.ler(acordar_video=False).get("memoria") or {}).get("total_gb")
        elif secao == "desempenho":
            dados["recursos"] = {**recursos.ler(acordar_video=False), "devagar": estado.devagar}
            # A primeira leitura do psutil sem intervalo e 0%: aqui mede meio segundo.
            try:
                import psutil

                dados["recursos"]["processador"] = {"percentual": round(psutil.cpu_percent(interval=0.5), 1)}
            except Exception:  # noqa: BLE001
                pass
            dados["saude"] = _itens_de_saude()
            dados["modelo_gb"] = _tamanho_do_modelo()
        elif secao == "plano":
            dados["atualizacao"] = atualizacao_situacao()
        elif secao == "lixeira":
            estado.lixeira.esvaziar_vencidos()
            dados["lixeira"] = estado.lixeira.listar()
        elif secao == "backup":
            import google_servicos

            dados["backup"] = _backup_para_tela()
            dados["drives"] = google_servicos.pastas_do_drive_no_computador()
        elif secao == "word":
            inst = getattr(estado, "word_instalacao", None)
            dados["word"] = {"ligado": bool((estado.prefs.dados.get("word") or {}).get("ligado")),
                             "instalacao": inst.situacao() if inst is not None else {}}
        elif secao == "acesso":
            sit = estado.acesso_de_fora.situacao()
            dados["acesso"] = {**sit, "contas": len(estado.acesso_de_fora.contas.listar() or [])}
        elif secao == "vinculos":
            dados["vinculado"] = bool(getattr(estado, "vinculo", None) and estado.vinculo.vinculado())
        elif secao == "conexoes":
            w = pedido.get("whatsapp") or {}
            quem = intencao._plano(w.get("quem") or "")
            fichas = [f for f in estado.cadastros.listar() if (f.get("telefone") or "").strip()]
            achadas = [f for f in fichas if quem and all(p in intencao._plano(f["nome"]).split() for p in quem.split())]
            if achadas:
                f = achadas[0]
                dados["contato"] = {"id": f["id"], "nome": f["nome"], "telefone": f["telefone"],
                                    "numero": conexoes.numero_whatsapp(f["telefone"]), "email": f.get("email") or ""}
            dados["sessao"] = estado.conexoes.sessao().to_dict()
    except Exception as exc:  # noqa: BLE001 - a frase diz menos, a coluna abre do mesmo jeito
        dados["erro"] = str(exc)
    return dados


def _responder_config(trabalho, lido, pergunta: str) -> StreamingResponse:
    """
    `Conversa - Meus dados`, `- Aparencia`, `- Modulos`... (T5): a frase diz
    o que muda, de quanto para quanto e o que precisa de atencao; a coluna
    abre a secao de Configuracoes com as mudancas marcadas "novo". Nada e
    gravado aqui - so o "Salvar alteracoes" da coluna grava, pela rota de
    sempre de Configuracoes.
    """
    import config_pela_conversa as cpc

    pedido = dict(lido.campos)
    secao = pedido["secao"]
    if secao == "aprendizado" and pedido.get("resto"):
        pedido["lembrete"] = cpc.lembrete_da_frase(pedido["resto"], [f["nome"] for f in estado.cadastros.listar()])
    texto, proposta = cpc.proposta(pedido, _dados_da_config(secao, pedido))
    proposta.update({"porque": lido.porque, "pergunta": pergunta})
    # O titulo que a frase sugere ("Troque meu telefone") so na conversa nova:
    # a que ja tinha assunto continua com o nome dela.
    if len([m for m in trabalho.mensagens if m.autor == "pessoa"]) <= 1 and proposta.get("titulo_conversa"):
        trabalho.titulo = proposta["titulo_conversa"]

    def gerar() -> Iterator[str]:
        trabalho.etapas = [Etapa("Ler Configurações", estado=CONCLUIDO)]
        trabalho.estado = CONCLUIDO
        trabalho.dizer("paulus", texto, proposta=proposta)
        estado.trabalhos.salvar(trabalho)
        yield _sse("token", {"t": texto})
        yield _sse("proposta", proposta)
        yield _sse("fim", {"segundos": 0, "titulo": trabalho.titulo})

    return StreamingResponse(gerar(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _responder_lancamento(trabalho, lido, pergunta: str, citados=None) -> StreamingResponse:
    """
    O lancamento pela conversa: a despesa ou o recebimento por regra, o
    anexo lido (boleto, comprovante) e, no recebimento, a cobranca em aberto
    que ele paga. A frase diz o que conferiu; o lancamento abre na coluna e
    so entra no Financeiro no clique em Lancar.
    """
    import lancamentos_pela_conversa as lpc

    c = dict(lido.campos)
    hoje = date.today().isoformat()
    if c.get("cadastro_nome") and not c.get("cadastro_id"):
        ficha = next((f for f in estado.cadastros.listar() if f["nome"] == c["cadastro_nome"]), None)
        c["cadastro_id"] = ficha["id"] if ficha else None
    papel_doc = next((d for d in _documentos_citados(citados) if d.text), None)
    papel = lpc.ler_papel(papel_doc.text) if papel_doc else {}
    c["papel"] = {"nome": papel_doc.name, "tipo": c.get("anexo") or ("comprovante" if c["tipo"] == "recebimento" else "boleto"),
                  **papel} if papel_doc else None
    casado = None
    if c["tipo"] == "recebimento":
        abertos = estado.financeiro.listar(tipo="recebimento", situacao="aberto")
        casado = lpc.casar_aberto(c, abertos)
    partes = []
    if casado:
        c["id"] = casado["id"]
        c["original_centavos"] = casado["centavos"]
        c["juros_centavos"] = max(0, c["centavos"] - casado["centavos"])
        c["descricao"] = casado["descricao"]
        c["categoria"] = casado.get("categoria") or c["categoria"]
        c["vencimento"] = casado.get("vencimento") or ""
        c["atrasado"] = bool(casado.get("atrasado"))
    if c.get("pago"):
        c["liquidado_em"] = hoje
    if c["tipo"] == "despesa" and c.get("cadastro_nome") and c.get("descricao") and c["cadastro_nome"] not in c["descricao"]:
        c["descricao"] = c["descricao"] + " · " + c["cadastro_nome"]
    forma = {"transferencia": "por transferência", "pix": "por Pix", "boleto": "por boleto", "cartao": "no cartão",
             "dinheiro": "em dinheiro", "debito": "no débito"}.get(c.get("forma") or "", "")
    if c["tipo"] == "recebimento":
        if casado:
            texto = (("Li o comprovante e preenchi" if papel_doc else "Preenchi") + " o recebimento ao lado: " +
                     lpc.em_reais(casado["centavos"]) + " de “" + casado["descricao"] + "”" +
                     (f" mais {lpc.em_reais(c['juros_centavos'])} de juros" if c["juros_centavos"] else "") +
                     ", pagos hoje" + (f" {forma}" if forma else "") + "." +
                     (" A cobrança em atraso sai da lista." if c.get("atrasado") else ""))
        else:
            texto = ("Preenchi o recebimento ao lado: " + lpc.em_reais(c["centavos"]) +
                     (f" de {c['cadastro_nome']}" if c.get("cadastro_nome") else "") + ", pago hoje. " +
                     ("Não achei cobrança em aberto desse cliente que case com o valor: entra como recebimento novo."
                      if c.get("cadastro_id") else "Não achei o cliente em Cadastros: escolha ao lado."))
        if papel.get("centavos") and papel["centavos"] != c["centavos"]:
            texto += f" O comprovante diz {lpc.em_reais(papel['centavos'])} — confira."
    else:
        texto = ("Li o boleto e preenchi" if papel_doc else "Preenchi") + " a despesa ao lado."
        if papel_doc:
            confere = []
            if papel.get("centavos"):
                confere.append("o valor" if papel["centavos"] == c["centavos"] else None)
            if papel.get("vencimento") and c.get("vencimento"):
                confere.append("o vencimento" if papel["vencimento"] == c["vencimento"] else None)
            if confere and all(confere):
                partes.append(" e ".join(confere).capitalize() + (" batem" if len(confere) > 1 else " bate") + " com o que você disse")
            elif papel.get("centavos") and papel["centavos"] != c["centavos"]:
                partes.append(f"o boleto diz {lpc.em_reais(papel['centavos'])}, e você disse {lpc.em_reais(c['centavos'])} — confira")
            elif papel.get("vencimento") and c.get("vencimento") and papel["vencimento"] != c["vencimento"]:
                partes.append(f"o boleto vence em {escritorio._br(papel['vencimento'])}, e você disse {escritorio._br(c['vencimento'])} — confira")
            if papel.get("beneficiario"):
                partes.append("o beneficiário é " + papel["beneficiario"])
            if partes:
                texto += " " + "; ".join(partes) + "."
        if not c.get("vencimento"):
            texto += " Falta o vencimento."
    c["frase"] = texto
    proposta = {"tipo": "lancamento", "titulo": c.get("descricao") or "", "campos": c, "porque": lido.porque, "pergunta": pergunta}

    def gerar() -> Iterator[str]:
        trabalho.etapas = [Etapa("Preencher o lançamento", estado=CONCLUIDO)]
        trabalho.estado = CONCLUIDO
        trabalho.dizer("paulus", texto, proposta=proposta)
        estado.trabalhos.salvar(trabalho)
        yield _sse("token", {"t": texto})
        yield _sse("proposta", proposta)
        yield _sse("fim", {"segundos": 0, "titulo": trabalho.titulo})

    return StreamingResponse(gerar(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _achar_email(quem: str, sobre: str = "", *, marcar_lido: bool = True):
    """
    A mensagem mais recente de `quem` (o nome na ficha, com o e-mail dela,
    ou o que a frase disse: procura no remetente e no assunto). Devolve
    (conta, Mensagem | None). HTTPException quando a conta nao abre.
    """
    conta, senha = _conta_e_senha("")
    alvo = intencao._plano(quem)
    ficha = next((f for f in estado.cadastros.listar()
                  if f.get("email") and alvo and alvo in intencao._plano(f.get("nome", ""))), None)
    buscas = ([ficha["email"]] if ficha else []) + [quem]
    clientes = _emails_dos_cadastros()
    for busca in buscas:
        try:
            dados = correio.listar(conta, senha, busca=busca, limite=12 if sobre else 1, clientes=clientes)
        except correio.ErroCorreio as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        msgs = dados.get("mensagens") or []
        if sobre:
            chave = intencao._plano(re.sub(r"^(?:a|o|as|os)\s+", "", sobre.strip(), flags=re.I))
            msgs = [m for m in msgs if chave and chave in intencao._plano(m.get("assunto", ""))] or msgs
        if msgs:
            try:
                return conta, correio.abrir(conta, senha, msgs[0]["uid"], marcar_lido=marcar_lido)
            except correio.ErroCorreio as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
    return conta, None


def _passa_por_aprovacao(conta, request) -> bool:
    """O mesmo teste de POST /api/email/enviar: sem a permissao e a conta liberada, o envio vira pedido."""
    de_fora = request is not None and not rotas_do_acesso.e_local(request)
    return not (estado.prefs.pode("enviar_mensagem") and conta.pode_enviar_sem_confirmar and not de_fora)


def _responder_email(trabalho, lido, pergunta: str, request=None) -> StreamingResponse:
    """
    "Abra o último e-mail do Mercado Pago": a mensagem abre na conversa e a
    frase diz o que ela e, por regra (src/email_pela_conversa.py). "Responda
    a Priscila confirmando...": a conversa acha a mensagem e manda a tela
    abrir o rascunho; o texto vem de POST /api/email/conversa/rascunho, que
    roda o modelo. Nada sai daqui: enviar e o clique, e passa por Aprovacoes
    quando Limites da IA mandam.
    """
    import email_pela_conversa

    campos = dict(lido.campos)
    acao = campos.get("acao", "abrir")

    if acao == "escrever":
        return _escrever_email_novo(trabalho, lido, pergunta, request)

    def gerar() -> Iterator[str]:
        proposta = None
        try:
            conta, msg = _achar_email(campos.get("quem", ""), campos.get("sobre", ""), marcar_lido=(acao == "abrir"))
        except HTTPException as exc:
            detalhe = str(exc.detail)
            if exc.status_code == 400:
                texto = "Nenhuma conta de e-mail está ligada a este PAULUS. Ligue a sua em E-mail › Contas e peça de novo."
            elif exc.status_code == 401:
                texto = f"Não consegui entrar na caixa: {detalhe}. Abra E-mail uma vez, entre, e peça de novo."
            else:
                texto = f"Não consegui abrir a caixa agora: {detalhe}."
            conta, msg = None, None
        else:
            if msg is None:
                texto = (f"Não achei e-mail de “{campos.get('quem')}” na caixa de entrada"
                         + (f" sobre “{campos.get('sobre')}”" if campos.get("sobre") else "")
                         + " (procurei no remetente e no assunto).")
        if msg is not None:
            m = msg.to_dict()
            cabeca = {k: m.get(k) for k in ("uid", "de_nome", "de_email", "para", "assunto", "quando", "quando_curto")}
            cabeca["conta_id"] = conta.id
            cabeca["conta_email"] = conta.email
            if acao == "responder":
                aprovacao = _passa_por_aprovacao(conta, request)
                quem = m.get("de_nome") or m.get("de_email")
                texto = (f"Vou escrever a resposta a {quem} sobre “{m.get('assunto') or 'sem assunto'}”. O texto aparece na caixa "
                         "abaixo para você revisar — " + ("enviar passa por Aprovações." if aprovacao else "nada sai sem o seu clique em Enviar."))
                proposta = {"tipo": "email", "titulo": m.get("assunto") or "", "porque": lido.porque, "pergunta": pergunta,
                            "campos": {"acao": "responder", "pedido": campos.get("pedido", ""), **cabeca}}
            else:
                codigo = email_pela_conversa.codigo_de_verificacao(m.get("assunto", ""), m.get("corpo", ""))
                texto = email_pela_conversa.frase_da_mensagem(m, codigo)
                proposta = {"tipo": "email", "titulo": m.get("assunto") or "", "porque": lido.porque, "pergunta": pergunta,
                            "campos": {"acao": "abrir", "codigo": codigo, "prazo": m.get("prazo") or "",
                                       "prazo_trecho": m.get("prazo_trecho") or "",
                                       "sem_resposta": email_pela_conversa.sem_resposta(m.get("de_email", "")), **cabeca}}
        trabalho.etapas = [Etapa("Achar o e-mail", estado=CONCLUIDO)]
        trabalho.estado = CONCLUIDO
        trabalho.dizer("paulus", texto, proposta=proposta or {})
        estado.trabalhos.salvar(trabalho)
        yield _sse("token", {"t": texto})
        if proposta:
            yield _sse("proposta", proposta)
        yield _sse("fim", {"segundos": 0, "titulo": trabalho.titulo})

    return StreamingResponse(gerar(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _escrever_email_novo(trabalho, lido, pergunta: str, request=None) -> StreamingResponse:
    """
    "Escreva um e-mail para a Priscila dizendo que...": o envelope do e-mail
    novo na conversa, com quem recebe achado na ficha (ou o endereco dito), e
    o texto escrito pelo modelo em POST /api/email/conversa/rascunho. Nada
    sai daqui: enviar e o clique, com o sim, e passa por Aprovacoes quando
    Limites da IA mandam.
    """
    campos = dict(lido.campos)
    quem = campos.get("quem", "")
    email = campos.get("email", "")
    nome = "" if email and quem == email else quem
    if not email and quem:
        alvo = intencao._plano(quem)
        ficha = next((f for f in estado.cadastros.listar()
                      if f.get("email") and alvo and all(p in intencao._plano(f.get("nome", "")).split() for p in alvo.split())), None)
        if ficha:
            nome, email = ficha["nome"], ficha["email"]
    try:
        conta, _senha = _conta_e_senha("")
    except HTTPException as exc:
        texto = ("Nenhuma conta de e-mail está ligada a este PAULUS. Ligue a sua em E-mail › Contas e peça de novo."
                 if exc.status_code == 400 else f"Não consegui usar a conta de e-mail agora: {exc.detail}.")
        return _so_dizer(trabalho, texto)
    aprovacao = _passa_por_aprovacao(conta, request)
    para = [{"nome": nome, "email": email}] if email else []
    texto = (f"Vou escrever o e-mail para {nome or email}. " if para else
             f"Não achei e-mail de “{quem}” em Cadastros: ponha o endereço no Para. ") + \
        "O texto aparece na caixa abaixo para você revisar — " + \
        ("enviar passa por Aprovações." if aprovacao else "nada sai sem o seu clique em Enviar.")
    uid = "novo-" + uuid.uuid4().hex[:10]
    proposta = {"tipo": "email", "titulo": "Novo e-mail", "porque": lido.porque, "pergunta": pergunta,
                "campos": {"acao": "escrever", "uid": uid, "pedido": campos.get("pedido", ""), "para": para,
                           "quem": quem, "conta_id": conta.id, "conta_email": conta.email, "assunto": ""}}

    def gerar() -> Iterator[str]:
        trabalho.etapas = [Etapa("Preparar o e-mail", estado=CONCLUIDO)]
        trabalho.estado = CONCLUIDO
        trabalho.dizer("paulus", texto, proposta=proposta)
        estado.trabalhos.salvar(trabalho)
        yield _sse("token", {"t": texto})
        yield _sse("proposta", proposta)
        yield _sse("fim", {"segundos": 0, "titulo": trabalho.titulo})

    return StreamingResponse(gerar(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _responder_criar_agente(trabalho, lido, pergunta: str) -> StreamingResponse:
    """
    "Crie um agente que preencha a procuracao...": a regra acha os modelos
    possiveis no Acervo e a conversa pergunta tres coisas antes de escrever
    (src/agente_pela_conversa.py). Nada e gravado aqui.
    """
    import agente_pela_conversa as apc

    pedido = lido.campos.get("pedido", "")
    modelos = apc.candidatos_de_modelo(pedido, estado.searcher.documents)
    texto = "Já tenho a base. Antes de escrever as instruções, preciso de três respostas."
    proposta = {"tipo": "criar_agente", "titulo": apc.nome_por_regra(pedido), "porque": lido.porque, "pergunta": pergunta,
                "campos": {"pedido": pedido, "modelos": modelos, "nome": apc.nome_por_regra(pedido)}}

    def gerar() -> Iterator[str]:
        if len(trabalho.mensagens) <= 1:
            trabalho.titulo = "Criar agente"
        trabalho.etapas = [Etapa("Montar o roteiro de leitura e preenchimento", estado=CONCLUIDO)]
        trabalho.estado = CONCLUIDO
        trabalho.dizer("paulus", texto, proposta=proposta)
        estado.trabalhos.salvar(trabalho)
        yield _sse("token", {"t": texto})
        yield _sse("proposta", proposta)
        yield _sse("fim", {"segundos": 0, "titulo": trabalho.titulo})

    return StreamingResponse(gerar(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class RascunhoDeAgente(BaseModel):
    pedido: str = ""
    modelo: str = ""
    faltando: str = "perguntar"
    formato: str = ""


def _base_do_agente(payload: RascunhoDeAgente) -> tuple[dict, str]:
    import agente_pela_conversa as apc

    doc = next((d for d in estado.searcher.documents if d.name == payload.modelo), None) if payload.modelo else None
    texto = (doc.text or "") if doc else ""
    base = apc.rascunho(payload.pedido[:600], doc.name if doc else "", payload.faltando, payload.formato,
                        apc.campos_em_branco(texto))
    base["brancos"] = apc.campos_em_branco(texto)
    return base, texto


@app.post("/api/agentes/rascunho")
def agentes_rascunho(payload: RascunhoDeAgente) -> dict:
    """O rascunho do agente so por regra: o modelo lido e os campos em branco contados. Nao grava."""
    base, _ = _base_do_agente(payload)
    return {"campos": base}


@app.post("/api/agentes/rascunho/escrever")
def agentes_rascunho_escrever(payload: RascunhoDeAgente) -> dict:
    """
    O modelo local escreve nome, descricao, instrucoes e exemplos; as
    respostas da pessoa entram por regra. Devolve os campos, o AGENTE.md e a
    validacao de sempre. Nao grava - quem grava e o "Salvar agente".
    """
    import agente_pela_conversa as apc
    import agentes_tela

    base, texto = _base_do_agente(payload)
    cliente = estado.cliente_para("redacao")
    campos = apc.escrever(payload.pedido[:600], base, texto,
                          lambda i, c, e, sis: cliente.ask_json(i, context=c, schema_hint=e, sistema=sis))
    md = agentes_tela.markdown_do_formulario(campos)
    return {"campos": campos, "markdown": md, "modelo_de_ia": estado.client.model,
            **agentes_tela.conferir(estado.agentes, md)}


class MudancaDeAgente(BaseModel):
    passos: list[str] = []
    fixos: list[str] = []
    pedido: str = ""


@app.post("/api/agentes/rascunho/mudar")
def agentes_rascunho_mudar(payload: MudancaDeAgente) -> dict:
    """O pedido de mudanca escrito na conversa, com o agente aberto ao lado. Nao grava."""
    import agente_pela_conversa as apc

    if not payload.pedido.strip():
        raise HTTPException(status_code=400, detail="diga o que mudar")
    cliente = estado.cliente_para("redacao")
    novos = apc.mudar([str(p)[:400] for p in payload.passos[:20]], payload.pedido[:600], [str(f)[:400] for f in payload.fixos[:8]],
                      lambda i, c, e, sis: cliente.ask_json(i, context=c, schema_hint=e, sistema=sis))
    if novos is None:
        raise HTTPException(status_code=503, detail="o modelo não respondeu agora; mude direto na folha")
    return {"passos": novos}


class SugestaoAoVivo(BaseModel):
    texto: str = ""
    documentos: list[str] = []
    anteriores: str = ""


@app.post("/api/gravacoes/sugerir")
def gravacoes_sugerir(payload: SugestaoAoVivo) -> dict:
    """
    A sugestao de resposta para uma fala da gravacao (src/sugestoes_ao_vivo.py):
    regra antes, modelo so quando a fala toca o que os documentos do caso dizem,
    e a resposta so passa ancorada no trecho. Sem sugestao, `sugestao` e None.
    """
    import sugestoes_ao_vivo as sav

    abertos = {d.name for d in estado.searcher.documents}
    documentos = [n for n in payload.documentos if n in abertos][:8]
    cliente = estado.cliente_para("conversa")
    sugestao = sav.sugerir(payload.texto[:1200], documentos, estado.searcher,
                           lambda i, c, e, sis: cliente.ask_json(i, context=c, schema_hint=e, sistema=sis),
                           payload.anteriores[:800])
    return {"sugestao": sugestao}


class PontosDoCaso(BaseModel):
    documentos: list[str] = []


@app.post("/api/gravacoes/pontos")
def gravacoes_pontos(payload: PontosDoCaso) -> dict:
    """Os pontos do caso numa frase, tirada dos trechos dos documentos (ou vazio)."""
    import sugestoes_ao_vivo as sav

    abertos = {d.name for d in estado.searcher.documents}
    documentos = [n for n in payload.documentos if n in abertos][:8]
    cliente = estado.cliente_para("conversa")
    pontos = sav.pontos_do_caso(documentos, estado.searcher,
                                lambda i, c, e, sis: cliente.ask_json(i, context=c, schema_hint=e, sistema=sis))
    return {"pontos": pontos}


def _so_dizer(trabalho, texto: str) -> StreamingResponse:
    """Uma resposta de uma frase, sem modelo, gravada na conversa."""
    def gerar() -> Iterator[str]:
        trabalho.etapas = [Etapa("Responder", estado=CONCLUIDO)]
        trabalho.estado = CONCLUIDO
        trabalho.dizer("paulus", texto)
        estado.trabalhos.salvar(trabalho)
        yield _sse("token", {"t": texto})
        yield _sse("fim", {"segundos": 0, "titulo": trabalho.titulo})

    return StreamingResponse(gerar(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _responder_sem_documentos(trabalho, lido, pergunta: str, agente=None) -> StreamingResponse:
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

        # A regra achou a acao mas nao um campo obrigatorio, e a frase tem com
        # o que preencher: so aqui o modelo e chamado. E um minuto no
        # computador sem placa de video, entao a etapa aparece andando.
        ajuda: list[str] = []
        ferramenta = ferramentas.POR_PROPOSTA.get(lido.tipo, "")
        if lido.precisa_modelo and ferramenta:
            import time

            agora = time.time()
            trabalho.etapas = [Etapa("Entender o pedido", estado=EXECUTANDO)]
            trabalho.estado = EXECUTANDO
            estado.trabalhos.salvar(trabalho)
            estado.andamento[trabalho.id] = {"fase": "entendendo", "inicio": agora, "desde": agora,
                                             "previsao_s": 0, "palavras": 0, "documentos": 0,
                                             "caracteres": 0}
            yield _sse("etapas", {"etapas": [asdict_etapa(e) for e in trabalho.etapas]})
            try:
                ajuda = ferramentas.completar_com_modelo(
                    lido, pergunta,
                    lambda instrucao, sistema: estado.cliente_para("conversa").ask_json(instrucao, sistema=sistema))
            finally:
                estado.andamento.pop(trabalho.id, None)

        proposta = {
            "tipo": lido.tipo,
            "titulo": lido.titulo,
            "campos": lido.campos,
            "porque": lido.porque,
            "falta": lido.falta,
            "pergunta": pergunta,
            "ferramenta": ferramenta,
            "disponivel": ferramentas.CATALOGO_FERRAMENTAS[ferramenta]["disponivel"] if ferramenta else True,
            "ajuda_do_modelo": ajuda,
        }
        # N14: com a chave "Agentes fazem sozinhos" e a ferramenta na `autonomia`
        # do AGENTE.md, o agente faz agora, sem o cartao - e fica no Historico,
        # com desfazer. Faltando dado, ou passado o limite do dia, volta ao cartao.
        motivo_sozinho = ""
        if agente is not None and ferramenta and not lido.falta:
            sozinho, motivo_sozinho = agente_mod.pode_sozinho(estado, agente, ferramenta)
            if sozinho:
                try:
                    feito = agente_mod.fazer_sozinho(estado, trabalho, agente, ferramenta, lido.tipo, lido.campos, lido.porque or pergunta)
                except ValueError as exc:
                    motivo_sozinho = f"não deu para fazer sozinho ({exc}): confira e confirme"
                else:
                    texto = f"{feito['resumo']} — feito sozinho pelo agente “{agente.nome or agente.slug}”."
                    cartao = {"tipo": "sozinho", "titulo": feito["resumo"], "campos": {"onde": feito["onde"], "id": feito["id"]},
                              "pedido_id": feito["pedido_id"], "agente": {"slug": agente.slug, "nome": agente.nome or agente.slug},
                              "ferramenta": ferramenta, "porque": lido.porque, "pergunta": pergunta}
                    trabalho.etapas = [Etapa("Fazer", estado=CONCLUIDO)]
                    trabalho.estado = CONCLUIDO
                    trabalho.dizer("paulus", texto, proposta=cartao, feito={"tipo": lido.tipo, "id": feito["id"], "onde": feito["onde"],
                                                                         "sozinho": True, "pedido_id": feito["pedido_id"]})
                    estado.trabalhos.salvar(trabalho)
                    yield _sse("token", {"t": texto})
                    yield _sse("proposta", cartao)
                    yield _sse("fim", {"segundos": 0, "titulo": trabalho.titulo})
                    return
        if motivo_sozinho:
            proposta["falta"] = proposta.get("falta") or ""
            proposta["porque"] = (proposta.get("porque") or "") + f" · {motivo_sozinho}"
        # A2: a ferramenta pedida por um agente passa tambem pela fila de
        # Aprovacoes. O cartao e o item da fila sao o mesmo pedido: confirmar
        # num fecha o outro, e o historico da fila e o registro.
        if agente is not None and ferramenta:
            pedido = estado.fila.pedir(
                (agente.nome or agente.slug) + ": " + (lido.titulo or lido.tipo), "conversa",
                resumo=lido.porque or pergunta, acao="conversa.proposta", pedido_por=(agente.nome or agente.slug),
                dados={"trabalho_id": trabalho.id, "tipo": lido.tipo, "campos": lido.campos,
                       "agente": agente.slug, "versao": agente.versao})
            proposta["pedido_id"] = pedido.id
            proposta["agente"] = {"slug": agente.slug, "nome": agente.nome or agente.slug, "versao": agente.versao}
        trabalho.etapas = [Etapa("Entender o pedido", estado=CONCLUIDO)]
        trabalho.estado = CONCLUIDO
        # Pacote de telas (`Conversa - Agendar`): o compromisso com data abre o
        # formulario ao lado e a semana na conversa, e a conversa diz o dia e
        # os horarios livres de verdade (os mesmos de /api/agenda/livres).
        texto = _frase_do_agendar(proposta) if lido.tipo == "agenda" and not lido.falta else ""
        trabalho.dizer("paulus", texto, proposta=proposta)
        estado.trabalhos.salvar(trabalho)
        if texto:
            yield _sse("token", {"t": texto})
        yield _sse("proposta", proposta)
        yield _sse("fim", {"segundos": 0, "titulo": trabalho.titulo})

    return StreamingResponse(
        gerar(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


DIAS_DA_SEMANA = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")


def _frase_do_agendar(proposta: dict) -> str:
    """
    "Separei quinta, 1º de outubro. Às 10:00 você está livre — confira ao
    lado." Liga a ficha de quem vai (campos.cadastro_id) quando o nome da
    frase esta em Cadastros. So diz o que a agenda mostra.
    """
    from datetime import date

    campos = proposta.setdefault("campos", {})
    nome = " ".join(str(campos.get("cliente") or "").split())
    if nome:
        alvo = nome.lower()
        fichas = estado.cadastros.listar()
        ficha = next((f for f in fichas if " ".join(f["nome"].split()).lower() == alvo), None) or \
            next((f for f in fichas if alvo in " ".join(f["nome"].split()).lower()), None)
        if ficha:
            campos["cadastro_id"] = ficha["id"]
            campos["cliente"] = ficha["nome"]
    campos.setdefault("onde", "online")
    try:
        dia = date.fromisoformat(str(campos.get("data") or ""))
    except ValueError:
        return ""
    quando = f"{DIAS_DA_SEMANA[dia.weekday()]}, {'1º' if dia.day == 1 else dia.day} de {acervo.MESES[dia.month - 1]}"
    regra = estado.prefs.dados.get("disponibilidade", {})
    try:
        livres = estado.agenda.livres(dia.isoformat(), int(campos.get("duracao") or 60), regra)
    except Exception:  # noqa: BLE001 - sem a conta dos livres, so o dia
        livres = None
    frase = f"Separei {quando}."
    hora = str(campos.get("hora") or "")
    if livres is not None:
        if campos.get("hora_dita") and hora:
            frase += (f" Às {hora} você está livre." if hora in livres
                      else f" Às {hora} já tem coisa na agenda" + (f"; cabe às {', '.join(livres[:3])}." if livres else "."))
        elif livres:
            campos["hora"] = livres[0]
            frase += " Cabe às " + (", ".join(livres[:3]) if len(livres) > 1 else livres[0]) + "."
        else:
            frase += " Não há horário livre nesse dia com essa duração."
    return frase + " Escolha o horário no calendário ou ao lado e confira o resto."


_JUIZES: dict[tuple, juizo.Juiz] = {}


def _juiz() -> juizo.Juiz | None:
    """
    O juiz da conversa, no mesmo modelo que responde - trocar de modelo no
    Ollama custa carregar outro. A janela e a minima da conversa pelo mesmo
    motivo: outro `num_ctx` faz o Ollama recarregar o modelo. Vinte segundos
    de paciencia: passou disso, a pergunta segue para os documentos.
    """
    modelo = estado.modelo_para("juiz")
    opcoes = estado.client.opcoes if modelo == estado.client.model else estado.novo_cliente(modelo).opcoes
    chave = (modelo, opcoes.num_ctx, opcoes.keep_alive)
    if chave not in _JUIZES:
        _JUIZES[chave] = juizo.Juiz(model=modelo, host=estado.client.host, timeout=20,
                                    num_ctx=opcoes.num_ctx, keep_alive=opcoes.keep_alive,
                                    sem_pensar=opcoes.desligar_pensar)
    return _JUIZES[chave]


def _responder_programa(trabalho, leitura, pergunta: str) -> StreamingResponse:
    """
    A resposta da camada do programa: o texto que o codigo montou (a consulta
    ao banco, os passos do mapa) e um cartao com dois botoes - abrir a tela e,
    se nao era isso, procurar nos documentos. Nenhum dos dois grava nada.
    """
    texto = leitura.texto or f"Abrindo {leitura.nome_tela}."
    proposta = {
        "tipo": "programa", "titulo": leitura.nome_tela,
        "campos": {"destino": leitura.destino, "nome": leitura.nome_tela, "modo": leitura.tipo},
        "porque": leitura.porque, "falta": "", "pergunta": pergunta,
        "por_modelo": leitura.por_modelo, "julgamento": leitura.julgamento,
    }

    def gerar() -> Iterator[str]:
        trabalho.etapas = [Etapa("Responder", estado=CONCLUIDO)]
        trabalho.estado = CONCLUIDO
        trabalho.dizer("paulus", texto, proposta=proposta)
        estado.trabalhos.salvar(trabalho)
        # Pelo juiz, o modelo gastou um token; pela regra, nenhum.
        julgado = (_juiz().ultima_medida if leitura.por_modelo else {}) or {}
        estado.medicao.pergunta(modelo=estado.client.model if leitura.por_modelo else "",
                                prompt_eval_count=julgado.get("tokens_lidos"),
                                eval_count=1 if leitura.por_modelo else 0,
                                total_s=julgado.get("segundos", 0.0), caminho="programa")
        yield _sse("token", {"t": texto})
        yield _sse("proposta", proposta)
        yield _sse("fim", {"segundos": 0, "titulo": trabalho.titulo})

    return StreamingResponse(
        gerar(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _consultar_cadastro(pergunta: str):
    """
    A consulta de cadastro (C4) com o que a pessoa pode ver: de fora, sem o
    modulo Cadastros nao ha fichas, e sem o Acervo nao ha fatos dos documentos.
    """
    ve = _modulos_visiveis()
    fichas, prefs, fatos = [], {}, None
    if ve is None or "cadastros" in ve:
        fichas = estado.cadastros.base.buscar(
            "SELECT id, tipo, nome, documento, telefone, email, endereco FROM cadastros")
        prefs = estado.prefs.dados
    if ve is None or "acervo" in ve:
        def fatos(nome: str, campo: str) -> list[dict]:
            return consulta_cadastro.fatos_dos_documentos(estado.base, estado.saber.biblioteca, nome, campo)
    return consulta_cadastro.ler(pergunta, cadastros=fichas, preferencias=prefs, fatos=fatos)


def _responder_consulta_cadastro(trabalho, resposta, pergunta: str) -> StreamingResponse:
    """A resposta por molde da consulta de cadastro, com o cartao (abrir a ficha, escolher, ler os documentos)."""
    import time

    comeco = time.time()
    proposta = consulta_cadastro.proposta(resposta, pergunta)

    def gerar() -> Iterator[str]:
        trabalho.etapas = [Etapa("Responder", estado=CONCLUIDO)]
        trabalho.estado = CONCLUIDO
        trabalho.dizer("paulus", resposta.texto, proposta=proposta)
        estado.trabalhos.salvar(trabalho)
        estado.medicao.pergunta(modelo="", eval_count=0, total_s=round(time.time() - comeco, 3), caminho="cadastro")
        yield _sse("token", {"t": resposta.texto})
        yield _sse("proposta", proposta)
        yield _sse("fim", {"segundos": 0, "titulo": trabalho.titulo})

    return StreamingResponse(
        gerar(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _perguntar_qual_documento(trabalho, pergunta: str, substantivo: str, nomes: list[str]) -> StreamingResponse:
    """
    O cartao "qual contrato?": a frase disse "o contrato" e ha varios. Os
    mais ligados a pergunta primeiro (a ordem da busca). E o mesmo cartao do
    "onde eu procuro?" - escolher refaz a pergunta so naquele documento, ou
    em todos -, com o texto de quem nao disse qual.
    """
    ordem = list(dict.fromkeys(h.doc_name for h in estado.searcher.search(pergunta, top_k=40)))
    nomes = sorted(nomes, key=lambda n: ordem.index(n) if n in ordem else len(ordem))
    rotulos = {"procuracao": "procuração", "notificacao": "notificação"}
    proposta = {
        "tipo": "escopo", "motivo": "ambigua", "titulo": "", "campos": {}, "porque": "", "falta": "",
        "pergunta": pergunta, "substantivo": rotulos.get(substantivo, substantivo),
        "nomes": nomes[:4], "total": len(nomes),
    }

    def gerar() -> Iterator[str]:
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


def _perguntar_onde_procurar(trabalho, pergunta: str, foco: list[str]) -> StreamingResponse:
    """
    O cartao "onde eu procuro?": so no que a conversa vinha lendo, ou no
    acervo inteiro. Fica guardado como proposta; escolher refaz a pergunta
    com o Retomar, que troca o cartao pela resposta.
    """
    abertos = {d.name for d in estado.searcher.documents}
    proposta = {
        "tipo": "escopo", "titulo": "", "campos": {}, "porque": "", "falta": "",
        "pergunta": pergunta,
        "nomes": [n for n in foco if n in abertos][:3],
        "total": len(estado.searcher.documents),
    }

    def gerar() -> Iterator[str]:
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
        "  abrir um serviço — “abra um serviço para a Cooperativa: renovação "
        "do contrato de logística”",
        "  perguntar o que está gravado — “quais compromissos tenho amanhã?”, "
        "“tenho tarefa atrasada?”, “quanto recebi este mês?”",
        "  perguntar como se faz — “como assino um PDF?”, “como conecto meu Gmail?”",
        "  abrir uma tela — “abra o financeiro”",
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
    # "Criar sala no Google Meet" ligado no formulario: o evento vai a Agenda
    # do Google na hora, com a sala, e o link volta no compromisso.
    meet: bool = False


class NotaDia(BaseModel):
    dia: str
    texto: str = ""


def _documentos_com_data() -> list[dict]:
    from classify import CacheClassificacao

    return list(CacheClassificacao(CLASSIFICACAO_PATH).dados.values())


@app.get("/api/agenda")
def agenda_grade(de: str = "", ate: str = "", pessoa: int = 0) -> dict:
    """
    Tudo o que tem data no periodo: compromisso, prazo de tarefa e data de
    contrato na mesma grade. `pessoa` (id de Cadastros) e a agenda de alguem
    da equipe: so o que esta com essa pessoa.
    """
    from datetime import date, timedelta

    if not de or not ate:
        hoje = date.today()
        de = (hoje - timedelta(days=hoje.day - 1)).isoformat()
        ate = (date.fromisoformat(de) + timedelta(days=45)).isoformat()

    # "todas" sao as abertas; as concluidas que sao etapa de servico entram
    # para a etapa feita continuar no dia dela.
    tarefas = estado.tarefas.listar("todas") + [t for t in estado.tarefas.listar("concluidas") if t.get("servico_id")]
    grade = estado.agenda.grade(de, ate, tarefas, _documentos_com_data(), pessoa or None)
    grade["compromissos"] = estado.agenda.listar(de, ate)
    _eventos_do_google_na_grade(grade, de, ate, pessoa)
    grade["tipos"] = [{"valor": k, "rotulo": v} for k, v in TIPOS_AGENDA.items()]
    grade["ondes"] = [{"valor": k, "rotulo": v} for k, v in ONDES.items() if k]
    grade["clientes"] = [{"id": f["id"], "nome": f["nome"]} for f in estado.cadastros.listar()]
    return grade


@app.get("/api/agenda/dia")
def agenda_dia(dia: str) -> dict:
    # As abertas e as concluidas do dia: a grade conta as duas, e o painel
    # mostra a feita riscada em vez de sumir com ela.
    tarefas = [t for t in estado.tarefas.listar("todas") + estado.tarefas.listar("concluidas") if t.get("prazo") == dia]
    return {
        "dia": dia,
        "compromissos": estado.agenda.listar(dia, dia),
        "tarefas": tarefas,
        "nota": estado.agenda.nota(dia),
    }


@app.post("/api/agenda")
def agenda_salvar(payload: FichaCompromisso) -> dict:
    if payload.id and servicos_acesso.OCULTOS.get():
        c = estado.base.um("SELECT servico_id FROM compromissos WHERE id = ?", (payload.id,)) or {}
        if not servicos_acesso.visivel(c.get("servico_id")):
            raise HTTPException(status_code=404, detail="compromisso não encontrado")
    try:
        id_ = estado.agenda.salvar(payload.dados, payload.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    c = estado.agenda.obter(id_) or {}
    # A sala do Meet pedida ao salvar: so para reuniao online que ainda nao
    # tem sala. Espera o Google (o link entra no convite que a tela monta em
    # seguida); se nao der, o compromisso fica salvo e o motivo volta em
    # "meet_erro" - a tela avisa, nao finge que criou.
    if payload.meet and c.get("onde") == "online" and not c.get("meet"):
        if not estado.google_tem("agenda"):
            return {**c, "meet_erro": "conecte a Agenda do Google em Configurações › Conexões para criar a sala"}
        try:
            _enviar_compromisso_ao_google(id_, meet=True)
        except google_servicos.ErroGoogle as exc:
            return {**c, "meet_erro": str(exc)}
        c = estado.agenda.obter(id_) or {}
        if not c.get("meet"):
            c["meet_erro"] = "o Google criou o evento, mas não devolveu a sala do Meet"
        return c
    # Com a sincronizacao ligada, o compromisso vai para a Agenda do Google
    # em segundo plano: salvar aqui nao espera a internet.
    if _sincronizar_agenda_ligada():
        _no_google_em_segundo_plano(_enviar_compromisso_ao_google, id_)
    return c


# ------------------------------------------------------ a Agenda do Google


def _sincronizar_agenda_ligada() -> bool:
    return bool(estado.prefs_google().get("agenda_sincronizar")) and estado.google_tem("agenda")


def _no_google_em_segundo_plano(funcao, *args) -> None:
    """Chama o Google sem prender a tela; o erro fica guardado para Conexoes mostrar."""
    def trabalhar() -> None:
        try:
            funcao(*args)
            estado.prefs.atualizar({"google": {"erro": ""}})
        except google_servicos.ErroGoogle as exc:
            estado.prefs.atualizar({"google": {"erro": str(exc)}})
        except Exception as exc:  # noqa: BLE001 - o erro vai para a tela, a thread nao morre calada
            estado.prefs.atualizar({"google": {"erro": "a sincronização com o Google falhou: " + str(exc)[:160]}})

    threading.Thread(target=trabalhar, name="google", daemon=True).start()


def _enviar_compromisso_ao_google(id_: int, meet: bool = False) -> dict:
    c = estado.agenda.obter(id_)
    if not c:
        return {}
    r = estado.google.enviar_compromisso(c, meet=meet)
    estado.base.escrever(
        "UPDATE compromissos SET google_id = ?, meet = ?, google_em = datetime('now','localtime') WHERE id = ?",
        (r["google_id"], r["meet"], id_),
    )
    return r


def _sincronizar_agenda_toda() -> dict:
    """Manda ao Google os compromissos de uma semana atras a um ano a frente."""
    de, ate = google_servicos.hoje_e_depois()
    enviados, falhas = 0, []
    for c in estado.agenda.listar(de, ate):
        try:
            _enviar_compromisso_ao_google(c["id"])
            enviados += 1
        except google_servicos.ErroGoogle as exc:
            falhas.append({"titulo": c["titulo"], "motivo": str(exc)})
            if exc.status in (401, 403):
                break  # sem permissao, os outros falhariam do mesmo jeito
    from datetime import datetime as _dt

    estado.prefs.atualizar({"google": {"ultimo_sinc": _dt.now().strftime("%Y-%m-%d %H:%M"),
                                       "erro": falhas[0]["motivo"] if falhas else ""}})
    return {"enviados": enviados, "falhas": falhas}


def _eventos_do_google_na_grade(grade: dict, de: str, ate: str, pessoa: int) -> None:
    """
    Os eventos da Agenda do Google entram na grade so para ler (genero
    "google"): a tela mostra e abre no Google, nao edita.
    """
    if pessoa or not estado.prefs_google().get("agenda_mostrar") or not estado.google_tem("agenda"):
        return
    try:
        eventos = estado.google.eventos(de, ate)
    except google_servicos.ErroGoogle as exc:
        grade["google_erro"] = str(exc)
        return
    for e in eventos:
        if not e["data"]:
            continue
        grade["dias"].setdefault(e["data"], []).append({
            "genero": "google", "id": e["id"], "titulo": e["titulo"], "hora": e["hora"],
            "detalhe": "Agenda do Google", "tipo": "google", "duracao": e["duracao"],
            "link": e["link"], "meet": e["meet"],
        })
    for dia in grade["dias"].values():
        dia.sort(key=lambda x: (x["hora"] == "", x["hora"]))
    grade["contagem"]["google"] = len(eventos)


def _google_para_tela() -> dict:
    conta = estado.conta_google()
    g = estado.prefs_google()
    vigiadas = [chave_do_caminho(p) for p in estado.pastas_do_acervo()]

    def ja_vigiada(caminho: str) -> bool:
        chave = chave_do_caminho(caminho)
        return any(chave == v or chave.startswith(v + os.sep) for v in vigiadas)

    return {
        "configurado": bool(_credenciais_oauth("google").get("client_id")),
        "conta": conta.email if conta else "",
        "contas": [c.email for c in estado.contas.itens if c.autenticacao == "google"],
        "precisa_entrar": bool(conta and conta.precisa_entrar),
        "servicos": {s: {"rotulo": google_servicos.ROTULOS[s], "conectado": estado.google_tem(s)}
                     for s in google_servicos.ESCOPOS},
        "agenda_sincronizar": bool(g.get("agenda_sincronizar")),
        "agenda_mostrar": bool(g.get("agenda_mostrar")),
        "ultimo_sinc": g.get("ultimo_sinc", ""),
        "erro": g.get("erro", ""),
        "drive_no_computador": [{"caminho": p, "vigiada": ja_vigiada(p)}
                                for p in google_servicos.pastas_do_drive_no_computador()],
        "drive_online": estado.drive_online.para_tela(),
    }


@app.get("/api/google")
def google_situacao() -> dict:
    """A conta Google em Conexoes: o que esta conectado, o que sincroniza, o Drive no computador."""
    return _google_para_tela()


@app.post("/api/google/conectar")
def google_conectar(payload: dict) -> dict:
    """
    Pede ao Google mais uma permissao para a mesma conta do e-mail (a Agenda,
    o Drive). E a autorizacao incremental: o navegador abre, a pessoa marca, e
    a permissao nova se soma as que ja existem. O andamento e o mesmo do login
    do e-mail (/api/email/oauth/andamento).
    """
    servico = str(payload.get("servico", ""))
    if servico not in google_servicos.ESCOPOS:
        raise HTTPException(status_code=400, detail="serviço do Google desconhecido")
    conta = estado.conta_google()
    if not conta:
        raise HTTPException(status_code=400, detail="entre primeiro com a conta Google em E-mail › Contas: "
                                                    "é a mesma conta que ganha a Agenda e o Drive")
    escopo = google_servicos.ESCOPOS[servico]
    email_da_conta = conta.email

    def concluir(provedor: str, tokens: dict, email: str, nome: str) -> dict:
        if email.lower() != email_da_conta.lower():
            raise correio_oauth.ErroOAuth(f"o Google entrou com {email}, mas a conta conectada é {email_da_conta}: "
                                          "entre com a mesma conta")
        estado.contas.ligar_oauth(provedor, email, nome, tokens)
        if servico == "agenda":
            estado.prefs.atualizar({"google": {"conta": email_da_conta, "agenda_sincronizar": True, "agenda_mostrar": True}})
            _no_google_em_segundo_plano(_sincronizar_agenda_toda)
        else:
            estado.prefs.atualizar({"google": {"conta": email_da_conta}})
        return {"servico": servico, "google": _google_para_tela()}

    anterior = estado.entrada_oauth
    if anterior and not anterior.terminou:
        anterior.cancelar()
    try:
        entrada_ = correio_oauth.Entrada("google", _credenciais_oauth("google"), concluir, login_hint=email_da_conta,
                                         escopos="openid email " + escopo, exigir=(escopo,),
                                         tema="claro" if payload.get("tema") == "claro" else "escuro",
                                         ao_voltar=_trazer_o_paulus)
        estado.entrada_oauth = entrada_
        return entrada_.iniciar()
    except correio_oauth.ErroOAuth as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"não consegui abrir a porta local para o login: {exc}") from exc


# ------------------------------------------- o Drive pela internet (leitura)


class PastaDoDrive(BaseModel):
    id: str
    nome: str = ""


class TirarPastaDoDrive(BaseModel):
    id: str
    apagar_copia: bool = False


def _drive_leitura_ou_erro() -> None:
    if not estado.conta_google():
        raise HTTPException(status_code=400, detail="entre primeiro com a conta Google em E-mail › Contas")


@app.get("/api/google/drive/navegar")
def google_drive_navegar(pasta: str = "") -> dict:
    """
    As pastas do Drive, para escolher no "Incluir pasta" do Acervo. Sem a
    leitura autorizada, diz que falta (`autorizar`), com a conta que vai
    autorizar.
    """
    conta = estado.conta_google()
    if not conta or not estado.google_tem("drive_leitura"):
        return {"autorizar": True, "conta": conta.email if conta else "", "itens": []}
    try:
        if not pasta:
            itens = [{"id": "root", "nome": "Meu Drive", "pasta": True, "tipo": "raiz"},
                     {"id": "compartilhados", "nome": "Compartilhados comigo", "pasta": True, "tipo": "compartilhados",
                      "so_navegar": True}]
            itens += [{"id": d["id"], "nome": d.get("name", ""), "pasta": True, "tipo": "drive"}
                      for d in estado.google.drive_compartilhados()]
        else:
            import drive_online

            itens = [{"id": x["id"], "nome": x.get("name", ""), "pasta": x.get("mimeType") == google_servicos.PASTA,
                      "le": bool(drive_online.sufixo_do(x))}
                     for x in estado.google.drive_listar(pasta)]
    except google_servicos.ErroGoogle as exc:
        if exc.autorizar:
            return {"autorizar": True, "conta": conta.email, "itens": []}
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"autorizar": False, "conta": conta.email, "itens": itens}


@app.get("/api/google/drive/copias")
def google_drive_copias() -> dict:
    return estado.drive_online.para_tela()


@app.post("/api/google/drive/copias")
def google_drive_copiar(payload: PastaDoDrive) -> dict:
    """Uma pasta do Drive passa a ter copia no Acervo; a primeira descida comeca ja."""
    _drive_leitura_ou_erro()
    if not estado.google_tem("drive_leitura"):
        raise HTTPException(status_code=403, detail="autorize primeiro a leitura do Google Drive")
    if payload.id == "compartilhados":
        raise HTTPException(status_code=400, detail="escolha uma das pastas de “Compartilhados comigo”")
    try:
        nova = estado.drive_online.incluir(payload.id, payload.nome)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    threading.Thread(target=estado.drive_online.sincronizar, args=(nova["id"],), name="drive-online-agora", daemon=True).start()
    return {"pasta": nova, **estado.drive_online.para_tela()}


@app.post("/api/google/drive/copias/sincronizar")
def google_drive_sincronizar() -> dict:
    _drive_leitura_ou_erro()
    threading.Thread(target=estado.drive_online.sincronizar, name="drive-online-agora", daemon=True).start()
    return estado.drive_online.para_tela()


@app.post("/api/google/drive/copias/tirar")
def google_drive_tirar(payload: TirarPastaDoDrive) -> dict:
    """Para de acompanhar a pasta. A copia fica no Acervo, a nao ser que se peca para apagar."""
    try:
        saiu = estado.drive_online.tirar(payload.id, payload.apagar_copia)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"saiu": saiu, **estado.drive_online.para_tela()}


def _drive_online_automatico() -> None:
    """A cada SINC_MINUTOS, com a leitura autorizada e alguma pasta escolhida."""
    import drive_online

    time.sleep(90)
    while True:
        try:
            if estado.drive_online.pastas() and estado.google_tem("drive_leitura"):
                estado.drive_online.sincronizar()
        except Exception:  # noqa: BLE001 - o erro fica na pasta; a vigia nao morre
            pass
        time.sleep(drive_online.SINC_MINUTOS * 60)


@app.post("/api/google/preferencias")
def google_preferencias(payload: dict) -> dict:
    """Ligar e desligar a sincronizacao e os eventos do Google na Agenda."""
    novo = {k: bool(payload[k]) for k in ("agenda_sincronizar", "agenda_mostrar") if k in payload}
    if payload.get("conta"):
        novo["conta"] = str(payload["conta"])
    estado.prefs.atualizar({"google": novo})
    if novo.get("agenda_sincronizar") and estado.google_tem("agenda"):
        _no_google_em_segundo_plano(_sincronizar_agenda_toda)
    return _google_para_tela()


@app.post("/api/google/sincronizar")
def google_sincronizar() -> dict:
    """Manda a Agenda ao Google agora, e relê os eventos de la."""
    if not estado.google_tem("agenda"):
        raise HTTPException(status_code=400, detail="conecte a Agenda do Google em Configurações › Conexões")
    estado.google._cache_eventos.clear()
    resultado = _sincronizar_agenda_toda()
    return {**resultado, "google": _google_para_tela()}


@app.delete("/api/agenda/{id_}")
def agenda_apagar(id_: int) -> dict:
    c = estado.base.um("SELECT titulo, data, hora, google_id FROM compromissos WHERE id = ?", (id_,))
    if not c:
        raise HTTPException(status_code=404, detail="compromisso nao encontrado")
    # Apagado aqui, apagado no Google - se foi para la. Restaurar da lixeira
    # manda de novo na proxima sincronizacao (o evento antigo nao existe mais).
    if c.get("google_id") and estado.google_tem("agenda"):
        _no_google_em_segundo_plano(estado.google.apagar_compromisso, c["google_id"])
    entrada = estado.lixeira.apagar_linha("compromisso", id_, c["titulo"], "Agenda · " + c["data"] + " " + (c["hora"] or ""))
    return _foi_para_lixeira(entrada, "apagado", id_)


@app.post("/api/agenda/nota")
def agenda_nota(payload: NotaDia) -> dict:
    estado.agenda.gravar_nota(payload.dia, payload.texto)
    return {"dia": payload.dia, "texto": payload.texto}


@app.post("/api/agenda/{id_}/meet")
def agenda_sala_no_meet(id_: int) -> dict:
    """
    A sala do Meet do compromisso, de verdade: o evento na Agenda do Google
    ganha a sala, e o link fica no compromisso (e no convite).
    """
    if not estado.google_tem("agenda"):
        raise HTTPException(status_code=400, detail="conecte a Agenda do Google em Configurações › Conexões para criar a sala")
    if not estado.agenda.obter(id_):
        raise HTTPException(status_code=404, detail="compromisso não encontrado")
    try:
        r = _enviar_compromisso_ao_google(id_, meet=True)
    except google_servicos.ErroGoogle as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if not r.get("meet"):
        raise HTTPException(status_code=502, detail="o Google criou o evento, mas não devolveu a sala do Meet")
    return estado.agenda.obter(id_) or {}


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


# Quantas sugestoes a tela recebe de uma vez. A conta de verdade vai junto.
LIMITE_DE_SUGESTOES = 300


class NomeSugerido(BaseModel):
    nome: str


def _documentos_por_ler() -> tuple[int, list[str]]:
    """Quantos documentos o Acervo tem e quais ainda nao foram lidos."""
    from classify import CacheClassificacao

    lidos = CacheClassificacao(CLASSIFICACAO_PATH).dados
    documentos = list(estado.searcher.documents)
    faltam = [
        d.path for d in documentos
        if d.sha1 and d.sha1 not in lidos and Path(d.path).exists()
    ]
    return len(documentos), faltam


@app.get("/api/cadastros/sugestoes")
def cadastros_sugestoes() -> dict:
    """Quem ja aparece nos documentos e ainda nao tem ficha (nem foi recusado)."""
    todas = estado.cadastros.sugestoes(CLASSIFICACAO_PATH, limite=None)
    total, faltam = _documentos_por_ler()
    return {
        "sugestoes": todas[:LIMITE_DE_SUGESTOES],
        "total": len(todas),
        "ignorados": len(estado.cadastros.ignorados()),
        "levantamento": {"documentos": total, "faltam": len(faltam)},
    }


@app.post("/api/cadastros/sugestoes/ignorar")
def cadastros_sugestao_ignorar(payload: NomeSugerido) -> dict:
    """O nome recusado sai das sugestoes e nao volta."""
    try:
        quantos = estado.cadastros.ignorar(payload.nome)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"nome": payload.nome, "ignorados": quantos}


@app.post("/api/cadastros/sugestoes/desfazer")
def cadastros_sugestao_desfazer(payload: NomeSugerido) -> dict:
    """Desfaz o ignorar: o nome volta a ser sugerido."""
    return {"nome": payload.nome, "voltou": estado.cadastros.voltar_a_sugerir(payload.nome)}


@app.post("/api/cadastros/levantamento")
def cadastros_levantamento() -> StreamingResponse:
    """
    Fazer levantamento: le os documentos do Acervo que ainda nao foram lidos,
    para achar quem assina e ainda nao tem ficha.

    E a mesma leitura do Acervo (habilidades/classificar.py), que guarda o
    resultado por conteudo - o que ja foi lido nao e lido de novo, e o que
    este levantamento ler serve ao Acervo tambem. Sem documento novo, nao
    ha o que ler: responde na hora com a conta de sugestoes de agora.
    """
    total, faltam = _documentos_por_ler()
    antes = len(estado.cadastros.sugestoes(CLASSIFICACAO_PATH, limite=None))

    habilidade = None
    if faltam:
        habilidade = estado.registro.obter("classificar")
        if not habilidade or not habilidade.executavel:
            raise HTTPException(status_code=503, detail="a leitura dos documentos não carregou")
        falta = [p for p in habilidade.precisa if not _disponibilidade().get(p, False)]
        if falta:
            from habilidade_base import ROTULOS_PRECISA

            nomes = ", ".join(ROTULOS_PRECISA.get(p, p) for p in falta)
            raise HTTPException(status_code=400, detail=f"para ler os documentos, precisa de: {nomes}")
        estado.cancelar.clear()

    def gerar() -> Iterator[str]:
        yield _sse("inicio", {"novos": len(faltam), "total": total})
        lidos, parado = 0, False
        try:
            if habilidade:
                for tipo, dados in habilidade.executar(_contexto(tarefa="leitura"), caminhos=faltam):
                    if tipo == "progresso":
                        yield _sse("progresso", dados)
                    elif tipo == "resultados":
                        lidos = sum(1 for d in dados.get("documentos", []) if not d.get("erro"))
                        parado = bool(dados.get("parado"))
        except Exception as exc:
            yield _sse("erro", {"mensagem": str(exc)})
            return
        depois = len(estado.cadastros.sugestoes(CLASSIFICACAO_PATH, limite=None))
        yield _sse("fim", {
            "lidos": lidos, "total": total, "parado": parado, "novos": len(faltam),
            "sugestoes": depois, "novas": max(0, depois - antes),
        })

    return StreamingResponse(
        gerar(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/cadastros")
def cadastros_salvar(payload: FichaCadastro) -> dict:
    try:
        id_ = estado.cadastros.salvar(payload.dados, payload.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return estado.cadastros.obter(id_) or {}


@app.post("/api/fichas/corrigir")
def fichas_corrigir(payload: dict) -> dict:
    """Com a ficha aberta na coluna: o que a frase corrige, por regra (nada e gravado)."""
    import fichas_pela_conversa

    return {"campos": fichas_pela_conversa.corrigir(str(payload.get("texto", ""))[:600])}


@app.post("/api/cadastros/{id_}/vincular")
def cadastros_vincular(id_: int, payload: VinculoDoc) -> dict:
    if not estado.cadastros.obter(id_):
        raise HTTPException(status_code=404, detail="cadastro nao encontrado")
    estado.cadastros.vincular(id_, payload.sha1, payload.nome)
    return estado.cadastros.obter(id_) or {}


@app.delete("/api/cadastros/{id_}")
def cadastros_apagar(id_: int) -> dict:
    f = estado.base.um("SELECT nome, tipo FROM cadastros WHERE id = ?", (id_,))
    if not f:
        raise HTTPException(status_code=404, detail="cadastro nao encontrado")
    entrada = estado.lixeira.apagar_linha("cadastro", id_, f["nome"], "Cadastros · " + f["tipo"])
    return _foi_para_lixeira(entrada, "apagado", id_)


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
    """
    A visao Tarefas e compromissos da Agenda. O compromisso entra em Meu dia
    (os de hoje) e em Planejadas (os que vem); nas listas, em Importante e em
    Concluidas, nao - compromisso nao tem lista, estrela nem conclusao.
    """
    from datetime import date, timedelta

    hoje = date.today().isoformat()
    amanha = (date.today() + timedelta(days=1)).isoformat()
    compromissos: list[dict] = []
    if not lista and filtro == "meu_dia":
        compromissos = estado.agenda.listar(hoje, hoje)
    elif not lista and filtro == "planejadas":
        compromissos = estado.agenda.listar(amanha, "9999-12-31")
    contagens = estado.tarefas.contagens()
    contagens["compromissos_hoje"] = estado.agenda.base.contar("compromissos", "data = ?", (hoje,))
    contagens["compromissos_planejados"] = estado.agenda.base.contar("compromissos", "data > ?", (hoje,))
    return {
        "tarefas": estado.tarefas.listar(filtro, lista),
        "compromissos": compromissos,
        "contagens": contagens,
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
    if payload.id and servicos_acesso.OCULTOS.get():
        t = estado.base.um("SELECT servico_id FROM tarefas WHERE id = ?", (payload.id,)) or {}
        if not servicos_acesso.visivel(t.get("servico_id")):
            raise HTTPException(status_code=404, detail="tarefa não encontrada")
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
    t = estado.base.um("SELECT titulo, prazo FROM tarefas WHERE id = ?", (id_,))
    if not t:
        raise HTTPException(status_code=404, detail="tarefa nao encontrada")
    entrada = estado.lixeira.apagar_linha("tarefa", id_, t["titulo"], "Agenda · Tarefas" + (" · prazo " + t["prazo"] if t["prazo"] else ""))
    return _foi_para_lixeira(entrada, "apagada", id_)


# ------------------------------------------------------------- aprovacoes


class Decisao(BaseModel):
    ids: list[str] = []
    aprovar: bool = True
    # De fora, aprovar o que sai desta maquina pede o codigo do autenticador
    # de novo (src/acesso/politicas.py, ACOES_QUE_SAEM).
    codigo: str = ""
    # Pedido com opções (N1: qual prazo - a apelação ou os embargos): o
    # índice da escolhida, por pedido. Sem escolha, vale a primeira.
    escolhas: dict[str, int] = {}


def _fila_para_tela() -> dict:
    """
    A fila, com o que a tela de fora precisa saber de cada pedido: se sai
    desta maquina (pede o codigo do autenticador) e se so se aprova no
    computador do escritorio.
    """
    tela = estado.fila.para_tela()
    for grupo in ("pendentes", "hoje"):
        for p in tela.get(grupo, []):
            p["sai_daqui"] = p.get("acao") in politicas_do_acesso.ACOES_QUE_SAEM or bool((p.get("dados") or {}).get("sai_daqui"))
            p["so_no_escritorio"] = p.get("acao") in politicas_do_acesso.ACOES_SO_NO_ESCRITORIO
    return tela


@app.get("/api/aprovacoes")
def aprovacoes_listar() -> dict:
    return _fila_para_tela()


def _pode_aprovar_de_fora(pedido, pessoa: dict, codigo: str, conferido: dict) -> str:
    """
    Vazio se quem esta de fora pode aprovar este pedido; senao, o motivo.

    O que e so do escritorio (mover, apagar, exportar em lote, assinar) nao
    se aprova de fora nem pelo titular. O que sai desta maquina pede o codigo
    do autenticador - conferido uma vez por decisao, porque o codigo vale uma
    vez so.
    """
    if pedido.acao in politicas_do_acesso.ACOES_SO_NO_ESCRITORIO:
        return politicas_do_acesso.MENSAGEM_BLOQUEADA
    sai = pedido.acao in politicas_do_acesso.ACOES_QUE_SAEM or bool((pedido.dados or {}).get("sai_daqui"))
    if not sai:
        return ""
    if "ok" not in conferido:
        conferido["ok"] = bool(codigo) and estado.acesso_de_fora.contas.confirmar_de_novo(pessoa, codigo)
    return "" if conferido["ok"] else "aprovar de fora o que sai do escritório pede o código do autenticador"


@app.post("/api/aprovacoes/decidir")
def aprovacoes_decidir(payload: Decisao, request: Request = None) -> dict:
    """
    Aprova ou recusa. Aprovar executa a acao; recusar so encerra o pedido.

    A execucao nao mora na fila: cada acao e feita por quem sabe faze-la, e o
    resultado volta para o pedido. Assim a fila nao precisa entender de mover
    arquivo, assinar ou enviar.

    De fora (so o titular chega aqui, pela politica da rota), cada pedido e
    conferido antes de ser decidido: ver `_pode_aprovar_de_fora`.
    """
    feitos, falhas = [], []
    pessoa = rotas_do_acesso.pessoa(request)
    conferido: dict = {}

    for id_ in payload.ids:
        if pessoa is not None and payload.aprovar:
            antes = estado.fila.obter(id_)
            motivo = _pode_aprovar_de_fora(antes, pessoa, payload.codigo, conferido) if antes else ""
            if motivo:
                falhas.append({"id": id_, "motivo": motivo})
                continue
        pedido = estado.fila.decidir(id_, payload.aprovar)
        if pedido and pessoa is not None:
            remoto = request.scope.get("state", {}).get("paulus_remoto") or {}
            estado.acesso_de_fora.anotar(acao="aprovacao" if payload.aprovar else "recusa", alvo=pedido.titulo,
                                         pessoa=pessoa["nome"], email=pessoa["email"],
                                         ip=remoto.get("ip", ""))
        if not pedido:
            falhas.append({"id": id_, "motivo": "pedido nao esta mais na fila"})
            continue

        if not payload.aprovar:
            feitos.append({"id": id_, "estado": pedido.estado})
            continue

        if id_ in payload.escolhas and (pedido.dados or {}).get("opcoes"):
            n = len(pedido.dados["opcoes"])
            pedido.dados["escolha"] = min(max(int(payload.escolhas[id_]), 0), n - 1)
            estado.fila.salvar()
        executor = EXECUTORES.get(pedido.acao)
        if not executor:
            estado.fila.registrar_resultado(id_, "aprovado, sem nada a executar")
            feitos.append({"id": id_, "estado": pedido.estado})
            continue

        try:
            resultado = executor(pedido)
            # O executor devolve a frase do historico ou, quando ha para onde
            # levar a pessoa depois do sim, {"texto", "desfecho"}: a tela usa
            # o desfecho para abrir o que acabou de ser feito.
            desfecho = None
            if isinstance(resultado, dict):
                desfecho = resultado.get("desfecho")
                resultado = resultado.get("texto", "")
            estado.fila.registrar_resultado(id_, resultado)
            feito = {"id": id_, "estado": pedido.estado, "categoria": pedido.categoria, "resultado": resultado}
            if desfecho:
                feito["desfecho"] = desfecho
            feitos.append(feito)
        except Exception as exc:
            estado.fila.registrar_resultado(id_, f"nao consegui: {exc}", falhou=True)
            falhas.append({"id": id_, "motivo": str(exc)})

    return {"feitos": feitos, "falhas": falhas, **_fila_para_tela()}


def _executar_mover(pedido) -> str:
    """Executa um plano de organizacao que estava esperando aprovacao."""
    from organize import Movimento, Plano

    dados = pedido.dados
    plano = Plano(
        movimentos=[Movimento(**m) for m in dados.get("movimentos", [])],
        destino=dados.get("destino", ""),
        padrao=dados.get("padrao", ""),
        ignorados=dados.get("ignorados", []),
        operacao=dados.get("operacao", "mover"),
    )
    resultado = aplicar_plano(plano, DIARIOS_DIR)
    _guardar_organizacao(plano, resultado, pedido.id)
    estado.recarregar()
    verbo = "copiado(s)" if plano.operacao == "copiar" else "movido(s)"
    if resultado.falhas:
        return f"{resultado.movidos} {verbo}, {len(resultado.falhas)} falha(s)"
    return f"{resultado.movidos} arquivo(s) {verbo}"


def _executar_assinar(pedido) -> dict:
    """Assina o que estava esperando o sim na fila."""
    senha = estado.cofre.senha_agora()
    if not senha:
        raise RuntimeError("a senha do certificado expirou - abra o certificado e tente de novo")

    resultado = _assinar_de_fato(pedido.dados, senha)
    if resultado.erro:
        raise RuntimeError(resultado.erro)

    aviso = "" if resultado.icp_brasil else " (certificado fora da ICP-Brasil)"
    return {
        "texto": f"assinado, codigo {resultado.codigo}{aviso}",
        # Depois do sim, a tela abre o documento ja assinado.
        "desfecho": {"tipo": "assinatura", "origem": pedido.dados.get("arquivo", ""), **resultado.to_dict()},
    }


def _executar_assinar_lote(pedido) -> dict:
    """
    Assina os documentos de um lote que esperava o sim na fila.

    Um documento que falha nao derruba os outros: cada um tem a sua
    assinatura, e o desfecho diz quais sairam e quais nao. So quando nenhum
    sai o pedido conta como falho.
    """
    senha = estado.cofre.senha_agora()
    if not senha:
        raise RuntimeError("a senha do certificado expirou - abra o certificado e tente de novo")

    feitos, falhas = _assinar_varios(pedido.dados.get("itens") or [], senha)
    if not feitos:
        motivo = falhas[0]["motivo"] if falhas else "o lote estava vazio"
        raise RuntimeError(f"nenhum documento assinado: {motivo}")

    texto = f"{len(feitos)} de {len(feitos) + len(falhas)} documento(s) assinado(s)"
    if falhas:
        texto += f"; {len(falhas)} com problema"
    if not all(f.get("icp_brasil") for f in feitos):
        texto += " (certificado fora da ICP-Brasil)"
    return {"texto": texto, "desfecho": {"tipo": "assinatura_lote", "feitos": feitos, "falhas": falhas}}


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

    estado.recarregar()
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


def _google_da_conta(email: str):
    """Os servicos do Google de UMA conta, pelo e-mail (o Drive de quem pediu, E3b)."""
    conta = estado.contas.por_email(email) if email else None
    if conta is None or conta.autenticacao != "google":
        return estado.google

    def token() -> str:
        try:
            return estado.contas.credencial(conta)
        except correio_oauth.ErroOAuth as exc:
            raise google_servicos.ErroGoogle(str(exc), status=401) from exc

    return google_servicos.Google(token)


def _executar_enviar_ao_drive(pedido) -> str:
    """Envia ao Google Drive, na pasta PAULUS, o que a pessoa aprovou."""
    g = estado.prefs_google()
    # O Drive de quem pediu: a conta Google guardada no pedido (E3b). A pasta
    # lembrada nas preferencias e a do Drive do escritorio.
    email = str(pedido.dados.get("conta_google") or "")
    conta = estado.contas.por_email(email) if email else None
    do_escritorio = conta is None or not int(conta.dono or 0)
    servico = estado.google if do_escritorio else _google_da_conta(email)
    try:
        pasta = servico.pasta_no_drive(g.get("drive_pasta", "") if do_escritorio else "")
    except google_servicos.ErroGoogle as exc:
        raise RuntimeError(str(exc)) from exc
    if do_escritorio and pasta != g.get("drive_pasta"):
        estado.prefs.atualizar({"google": {"drive_pasta": pasta}})
    enviados, falhas, links = 0, [], []
    for bruto in pedido.dados.get("caminhos", []):
        origem = Path(bruto)
        if not origem.is_file():
            falhas.append(origem.name)
            continue
        try:
            d = servico.enviar_ao_drive(origem, pasta)
            enviados += 1
            links.append({"nome": d.get("name", origem.name), "link": d.get("webViewLink", "")})
        except google_servicos.ErroGoogle as exc:
            falhas.append(f"{origem.name} ({exc})")
    pedido.dados["enviados"] = links
    texto = f"{enviados} documento(s) no Google Drive, na pasta {google_servicos.PASTA_NO_DRIVE}"
    if falhas:
        texto += "; não foram: " + ", ".join(falhas)
    return texto


EXECUTORES = {
    "organizar.mover": _executar_mover,
    "acervo.apagar": _executar_apagar_do_acervo,
    "acervo.exportar": _executar_exportar,
    "assinatura.assinar": _executar_assinar,
    "assinatura.lote": _executar_assinar_lote,
    "correio.enviar": _executar_enviar,
    "google.drive.enviar": _executar_enviar_ao_drive,
    # O que alguem propos pelo acesso de fora (agenda, tarefa, ficha): o sim
    # refaz exatamente o pedido guardado (src/acesso/servico.py).
    "acesso.proposta": lambda pedido: estado.acesso_de_fora.executar_proposta(pedido),
    # O prazo achado num documento (I9): o sim anota a tarefa na Agenda.
    "ajuda.prazo": lambda pedido: rotas_ajuda.executar_prazo(estado, pedido),
    # O documento fotografado de fora (ideia E do umbrelOS): o sim o poe no Acervo.
    "captura.entrar": lambda pedido: captura_mod.executar(estado, pedido),
    # N15: a pergunta que espera para ir à nuvem - o sim a libera.
    "nuvem.enviar": lambda pedido: nuvem_mod.liberar_da_fila(pedido),
    # L2: o prazo sugerido por uma movimentação do DataJud - o sim anota a tarefa.
    "processos.prazo": lambda pedido: processos_mod.executar_prazo(estado, pedido),
    # A2: a ferramenta de um agente, aprovada na fila em vez de no cartão.
    "conversa.proposta": lambda pedido: agente_mod.executar_da_fila(estado, pedido),
    # N9: a tarefa e o compromisso que um assistente conectado pelo MCP pediu.
    "mcp.tarefa": lambda pedido: mcp_leis.executar_tarefa(estado, pedido),
    "mcp.compromisso": lambda pedido: mcp_leis.executar_compromisso(estado, pedido),
}


@app.post("/api/aprovacoes/{id_}/desfazer")
def aprovacoes_desfazer(id_: str) -> dict:
    """N14: volta o que um agente fez sozinho (o pedido ja decidido, no Historico)."""
    pedido = estado.fila.obter(id_)
    if pedido is None or pedido.acao != "agente.sozinho":
        raise HTTPException(status_code=404, detail="não há o que desfazer aqui")
    try:
        texto = agente_mod.desfazer_sozinho(estado, pedido)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return {"desfeito": texto, **_fila_para_tela()}


@app.post("/api/google/drive/enviar")
def google_drive_enviar(payload: CaminhosDeDocumentos) -> dict:
    """
    Enviar documentos do Acervo ao Google Drive: sai desta maquina, entao vai
    para a fila de Aprovacoes e so acontece depois do sim.
    """
    if not estado.google_tem("drive"):
        raise HTTPException(status_code=400, detail="conecte o Google Drive em Configurações › Conexões")
    lidos = {chave_do_caminho(d.path): d for d in estado.searcher.documents}
    docs = [lidos[chave_do_caminho(c)] for c in payload.caminhos if chave_do_caminho(c) in lidos]
    if not docs:
        raise HTTPException(status_code=404, detail="nenhum desses documentos está no Acervo")
    conta = estado.conta_google()
    pedido = estado.fila.pedir(
        f"Enviar {len(docs)} documento(s) ao Google Drive",
        "google",
        acao="google.drive.enviar",
        resumo=f"Vai para o Google Drive de {conta.email if conta else 'sua conta'}, na pasta "
               f"{google_servicos.PASTA_NO_DRIVE}: " + ", ".join(d.name for d in docs[:6]) + ("…" if len(docs) > 6 else ""),
        etiquetas=["sai desta máquina"],
        dados={"caminhos": [d.path for d in docs], "nomes": [d.name for d in docs],
               "conta_google": conta.email if conta else ""},
        reversivel=False,
    )
    return {"pedido": pedido.to_dict(), **estado.fila.para_tela()}


# ------------------------------------------------- folha, notas e boletos


class MesPedido(BaseModel):
    mes: str = ""
    # Recibo do mes que ja existe: renomear ou substituir (src/nomes.py).
    decisoes: dict = {}


class FichaPapel(BaseModel):
    id: int | None = None
    dados: dict = {}


@app.get("/api/financeiro/folha")
def folha_ler(mes: str = "") -> dict:
    mes = mes or escritorio.mes_de_hoje()
    return {
        "folha": estado.folha.do_mes(mes),
        # Quem começa depois deste mês ("desde" da ficha) não é candidato a ele.
        "candidatos": estado.folha.pessoas(mes),
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
    # `dados_do_escritorio`, e nao `escritorio`: com o nome do modulo, a
    # variavel escondia o modulo na funcao inteira, e gerar recibo dava erro
    # sempre ("dict has no attribute gerar_recibos").
    pessoa = estado.prefs.dados.get("pessoa", {})
    dados_do_escritorio = estado.prefs.dados.get("escritorio", {})
    quem_paga = str(dados_do_escritorio.get("nome", "")).strip() or str(pessoa.get("nome", "")).strip()

    destino = _pasta_no_acervo("Financeiro", "Recibos", mes)
    # Recibo do mes que ja existe (gerar de novo): antes passava por cima
    # sem avisar; agora a tela pergunta, um por um (src/nomes.py).
    escolhas = nomes_mod.do_pedido({"decisoes": payload.decisoes})
    pendentes: list[dict] = []
    ocupados: set[str] = set()
    arquivos = {p["nome"]: nomes_mod.destino(destino, escritorio.nome_do_recibo(p["nome"], mes), escolhas, pendentes, ocupados=ocupados)
                for p in da_folha["pessoas"]}
    nomes_mod.conferir(pendentes)
    try:
        feitos = escritorio.gerar_recibos(
            da_folha, destino, escritorio.mes_por_extenso(mes), quem_paga, arquivos)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"nao consegui gerar: {exc}") from exc

    estado.recarregar_em_segundo_plano()
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
    pasta = _pasta_no_acervo("Financeiro", "Comprovantes", quando[:7] or escritorio.mes_de_hoje())

    alvo = pasta / nome
    n = 2
    while alvo.exists():
        alvo = pasta / f"{Path(nome).stem} ({n}){Path(nome).suffix}"
        n += 1
    alvo.write_bytes(conteudo)

    import hashlib
    sha = hashlib.sha1(conteudo).hexdigest()
    id_ = estado.financeiro.anexar(lancamento_id, nome, str(alvo), sha)
    estado.recarregar_em_segundo_plano()
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


@app.post("/api/financeiro/exportar")
def financeiro_exportar_gerar(payload: MesPedido) -> dict:
    """
    Gera a planilha do mes no Acervo (Financeiro/Planilhas) e devolve o nome;
    a tela baixa em seguida pelo GET com `arquivo`. A planilha do mes que ja
    existe nao e trocada sem a pessoa decidir (src/nomes.py).
    """
    mes = payload.mes or escritorio.mes_de_hoje()
    pasta = _pasta_no_acervo("Financeiro", "Planilhas")
    pendentes: list[dict] = []
    destino = nomes_mod.destino(pasta, f"financeiro-{mes}.xlsx", nomes_mod.do_pedido({"decisoes": payload.decisoes}), pendentes)
    nomes_mod.conferir(pendentes)
    _exportar_mes_em(destino, mes)
    return {"nome": destino.name, "mes": mes}


def _exportar_mes_em(destino: Path, mes: str) -> None:
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
    estado.recarregar_em_segundo_plano()


@app.get("/api/financeiro/exportar")
def financeiro_exportar(mes: str = "", arquivo: str = "") -> FileResponse:
    """O mes inteiro numa planilha, para quem faz a contabilidade. Com
    `arquivo`, entrega a que o POST acabou de gerar (so da pasta Planilhas)."""
    mes = mes or escritorio.mes_de_hoje()
    pasta = _pasta_no_acervo("Financeiro", "Planilhas")
    if arquivo:
        pronto = pasta / Path(arquivo).name
        if pronto.suffix.lower() != ".xlsx" or not pronto.is_file():
            raise HTTPException(status_code=404, detail="planilha não encontrada")
        return FileResponse(
            pronto,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=_anexo(pronto.name),
        )
    destino = pasta / f"financeiro-{mes}.xlsx"
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
    estado.recarregar_em_segundo_plano()
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
    dados["marca"] = estado.marca.info()
    return dados


@app.post("/api/preferencias")
def preferencias_gravar(payload: dict) -> dict:
    try:
        estado.prefs.atualizar(payload)
    except ValueError as exc:
        # CPF, telefone ou CNPJ que nao fecha (src/campos_br.py): nada e gravado.
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # O que a preferencia muda de verdade, agora: modelo e ritmo.
    modelo = estado.prefs.dados.get("modelo")
    # As opcoes vem junto: a janela e por modelo, e `ia` pode ter mudado
    # agora (src/inferencia.py).
    if (modelo and modelo != estado.client.model) or "ia" in payload:
        estado.client = estado.novo_cliente(modelo or estado.client.model)
    estado.devagar = bool(estado.prefs.dados.get("devagar"))
    estado.saber.ligada = bool(estado.prefs.dados.get("inteligencia", True))
    voz = (estado.prefs.dados.get("voz") or {}).get("modelo")
    if voz in transcricao_mod.MODELOS and voz != estado.transcritor.modelo:
        estado.transcritor.escolher(voz)

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
    operacao: str = "mover"         # "mover" ou "copiar" (o original fica)


class SoClassificar(BaseModel):
    pastas: list[str] = []          # onde o Organizar procurou
    ajustes: list[Ajuste] = []
    apenas: list[str] = []          # caminhos marcados; vazio = todos


class PedidoDesfazer(BaseModel):
    diario: str


class PedidoLeitura(BaseModel):
    apenas: list[str] = []          # caminhos escolhidos na varredura; vazio = todos


def _guardar_organizacao(plano, resultado, pedido: str = "") -> dict:
    """
    O desfecho de um mover, na forma que a tela mostra e desfaz.

    O destino passa a ser lido pelo Acervo: organizar e trazer os documentos
    para ca. Antes, o que foi movido sumia da tela Documentos - estava no
    disco, fora da unica pasta que o indice lia.
    """
    if resultado.movidos and plano.destino:
        estado.incluir_no_acervo(plano.destino)
    estado.ultima_organizacao = {
        "pedido": pedido,
        "movidos": resultado.movidos,
        "falhas": resultado.falhas,
        "diario": resultado.diario,
        "destino": plano.destino,
        "operacao": plano.operacao,
        "pastas": plano.resumo_por_pasta(),
    }
    return estado.ultima_organizacao


@app.get("/api/organizar/opcoes")
def organizar_opcoes() -> dict:
    return {
        "padroes": PADROES_SUGERIDOS,
        "tipos": [{"valor": k, "rotulo": v} for k, v in ROTULOS.items()],
        "destino_sugerido": str(Path.home() / "Documentos" / "Acervo PAULUS"),
        "diarios": listar_diarios(DIARIOS_DIR),
        # O botao diz "Mover agora" ou "Enviar para aprovacao" por isto. Vem
        # aqui, e nao de /api/preferencias, que pergunta ao Ollama a lista
        # de modelos e fazia a tela esperar.
        "mover_sem_pedir": estado.prefs.pode("organizar_mover"),
    }


@app.get("/api/pastas")
def navegar_pastas(caminho: str = "", arquivos: bool = False) -> dict:
    """Um nivel do seletor de pastas. Sem caminho, mostra unidades e atalhos.
    Com `arquivos`, lista tambem os documentos que o programa sabe ler."""
    dados = pastas.listar(caminho, sufixos=SUPPORTED_SUFFIXES if arquivos else None)
    dados["migalhas"] = pastas.migalhas(caminho)
    if not caminho:
        # As pastas que o proprio PAULUS le, no topo: e por elas que se
        # reorganiza o acervo que ja esta no sistema.
        padrao = Path(estado.pasta).resolve()
        dados["acervo"] = [
            {"nome": NOME_DA_PASTA_PADRAO if p.resolve() == padrao else (p.name or str(p)),
             "caminho": str(p), "tipo": "acervo"}
            for p in estado.pastas_do_acervo() if p.is_dir()
        ]
        # Onde o Google Drive para computador deixa o Drive, para a visao
        # "Google Drive" dos seletores; vazio = nao instalado.
        dados["drive"] = pastas.pastas_do_drive()
        # As copias do Drive pela internet (src/drive_online.py) entram como
        # mais um atalho "Google Drive" - em todo seletor de pastas.
        copias = _atalho_das_copias_do_drive(bool(dados["drive"]))
        if copias:
            dados["atalhos"] = list(dados.get("atalhos") or []) + [copias]
            dados["drive"] = list(dados["drive"]) + [copias["caminho"]]
    # Dentro da copia: o que se salva ali fica so neste computador (a copia
    # desce do Drive; nada sobe). A tela diz isso no rodape.
    dados["copia_do_drive"] = bool(caminho) and _dentro_da_copia_do_drive(caminho)
    return dados


def _atalho_das_copias_do_drive(tem_o_drive_no_computador: bool) -> dict | None:
    raiz = estado.drive_online.raiz()
    if not estado.drive_online.pastas() or not raiz.is_dir():
        return None
    return {"nome": "Google Drive (cópia)" if tem_o_drive_no_computador else "Google Drive", "caminho": str(raiz),
            "tipo": "drive", "copia": True, "tem_subpastas": True}


def _dentro_da_copia_do_drive(caminho: str) -> bool:
    try:
        raiz = estado.drive_online.raiz().resolve()
        alvo = Path(caminho).resolve()
    except (OSError, ValueError):
        return False
    return alvo == raiz or raiz in alvo.parents


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
    # conhecido sai em milissegundos, novo custa ~8 a 25 s. Cada arquivo leva
    # a marca, para a tela refazer a conta quando a pessoa escolhe quais ler.
    lidos = _em_cache([a["path"] for a in estado.encontrados])
    for a in estado.encontrados:
        a["lido"] = a["path"] in lidos
    conhecidos = len(lidos)
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


def _em_cache(caminhos: list[str]) -> set[str]:
    """Quais desses documentos ja foram lidos antes (mesmo conteudo)."""
    from classify import CacheClassificacao
    from extract import file_sha1

    cache = CacheClassificacao(CLASSIFICACAO_PATH)
    if not cache.dados:
        return set()

    lidos: set[str] = set()
    for caminho in caminhos:
        try:
            if file_sha1(Path(caminho)) in cache.dados:
                lidos.add(caminho)
        except OSError:
            continue
    return lidos


@app.post("/api/organizar/classificar")
def organizar_classificar(payload: PedidoLeitura | None = None) -> StreamingResponse:
    """
    Le o que a varredura achou - ou so o que a pessoa escolheu dela.

    A leitura em si mora em habilidades/classificar.py. Aqui fica so o que e do
    servidor: guardar o resultado para os passos seguintes do organizador.
    """
    caminhos = [a["path"] for a in estado.encontrados]
    if payload and payload.apenas:
        # So caminhos que a varredura achou: a lista vem da tela, e ler um
        # caminho qualquer que chegasse aqui seria abrir o disco inteiro.
        escolhidos = set(payload.apenas)
        caminhos = [c for c in caminhos if c in escolhidos]
    if not caminhos:
        raise HTTPException(status_code=400, detail="nada para ler - faca a varredura antes")

    habilidade = estado.registro.obter("classificar")
    if not habilidade or not habilidade.executavel:
        raise HTTPException(status_code=503, detail="a habilidade de classificar nao carregou")

    estado.cancelar.clear()

    def gerar() -> Iterator[str]:
        try:
            for tipo, dados in habilidade.executar(_contexto(tarefa="leitura"), caminhos=caminhos):
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


@app.post("/api/organizar/so-classificar")
def organizar_so_classificar(payload: SoClassificar) -> dict:
    """
    A terceira escolha do Organizar, ao lado de mover e copiar: nao mexe em
    arquivo nenhum.

    Guarda a classificacao que a pessoa conferiu - com as correcoes dela, que
    aqui sao o proprio resultado (no mover, a correcao vale so para o plano) -
    e passa a vigiar as pastas onde o Organizar procurou, como elas estao. Os
    documentos ficam sob a guarda do PAULUS sem sair do lugar. Nada vai para
    Aprovacoes: nenhum arquivo e tocado.
    """
    from classify import CacheClassificacao

    if not estado.classificacoes:
        raise HTTPException(status_code=400, detail="classifique os documentos antes")
    resultados = _com_ajustes(PedidoPlano(destino="", padrao="", ajustes=payload.ajustes, apenas=payload.apenas))
    cache = CacheClassificacao(CLASSIFICACAO_PATH)
    guardados = 0
    for resultado in resultados:
        if resultado.erro or not resultado.sha1:
            continue
        cache.guardar(resultado)
        guardados += 1
    cache.salvar()

    vigiadas, ja_vigiadas, nao_vigiadas = [], [], []
    for bruto in payload.pastas:
        pasta = Path(bruto)
        motivo = _motivo_para_nao_vigiar(pasta)
        if motivo.startswith("essa pasta já está no Acervo"):
            ja_vigiadas.append(str(pasta))
        elif motivo:
            nao_vigiadas.append({"pasta": str(pasta), "nome": pasta.name or str(pasta), "motivo": motivo})
        else:
            estado.incluir_no_acervo(pasta)
            vigiadas.append(str(pasta.resolve()))
    estado.classificacoes = {}
    estado.recarregar_em_segundo_plano()
    return {"operacao": "classificar", "classificados": guardados, "vigiadas": vigiadas,
            "ja_vigiadas": ja_vigiadas, "nao_vigiadas": nao_vigiadas}


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
        operacao=payload.operacao,
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
        operacao=payload.operacao,
    )
    if not plano.movimentos:
        raise HTTPException(status_code=400, detail="nada a fazer: os marcados já estão no lugar")

    if not estado.prefs.pode("organizar_mover"):
        pastas_alvo = plano.resumo_por_pasta()
        pedido = estado.fila.pedir(
            ("Copiar" if plano.operacao == "copiar" else "Mover") + f" {plano.total} arquivo(s) para "
            + (NOME_DA_PASTA_PADRAO if Path(plano.destino).resolve() == Path(estado.pasta).resolve()
               else Path(plano.destino).name or plano.destino),
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
    _guardar_organizacao(plano, resultado)
    estado.classificacoes = {}
    estado.encontrados = []
    estado.recarregar()
    return {
        "aguardando_aprovacao": False,
        "destino": plano.destino,
        "operacao": plano.operacao,
        "pastas": plano.resumo_por_pasta(),
        "movidos": resultado.movidos,
        "falhas": resultado.falhas,
        "diario": resultado.diario,
        "diarios": listar_diarios(DIARIOS_DIR),
    }


@app.get("/api/organizar/ultima")
def organizar_ultima() -> dict:
    """O desfecho da ultima organizacao - a tela volta a ele depois da fila."""
    return estado.ultima_organizacao or {}


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
    # Largura do selo em pontos do PDF, quando a pessoa redimensionou na tela.
    # Vazio, o tamanho de sempre; a altura acompanha na mesma proporcao.
    tamanho: float | None = None
    senha_pdf: str = ""
    motivo: str = ""
    guardar_biblioteca: bool = True
    # Nome repetido do "- assinado": renomear ou substituir (src/nomes.py).
    decisoes: dict = {}
    manter_original: bool = True
    senha_certificado: str = ""


class ItemDoLote(BaseModel):
    """Um documento do lote: onde o selo entra nele, posto pela pessoa na tela."""
    arquivo: str
    paginas: str = "ultima"
    intervalo: str = ""
    posicao: str = "rodape_direita"
    x: float | None = None
    y: float | None = None
    tamanho: float | None = None


class PedidoLote(BaseModel):
    """Varios documentos, uma senha: o que vale para todos fica fora dos itens."""
    itens: list[ItemDoLote] = []
    senha_pdf: str = ""
    motivo: str = ""
    guardar_biblioteca: bool = True
    # Nomes repetidos dos "- assinado" (src/nomes.py).
    decisoes: dict = {}
    manter_original: bool = True
    senha_certificado: str = ""


class AssinadosParaSalvar(BaseModel):
    # Nome repetido na pasta escolhida (src/nomes.py).
    decisoes: dict = {}
    arquivos: list[str] = []
    caminho: str = ""               # o .zip, escolhido no "Salvar como"
    pasta: str = ""                 # a pasta, para salvar um a um


MAX_LOTE = 200


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


class CertificadoDoWindows(BaseModel):
    impressao: str
    senha: str


@app.post("/api/certificado/windows/usar")
def certificado_windows_usar(payload: CertificadoDoWindows) -> dict:
    """
    Pre-seleciona um certificado instalado no Windows. Nada e exportado: o
    cofre guarda so a parte publica e a marca da senha do PAULUS que a
    pessoa criou agora. Ao assinar, o PAULUS confere essa senha e pede a
    conta ao Windows, com a chave que nunca sai de la - e, se o
    certificado tiver protecao forte, o Windows pede a senha dele tambem.
    """
    if len(payload.senha) < 4:
        raise HTTPException(status_code=400, detail="crie uma senha de pelo menos 4 caracteres")
    escolhido = next((c for c in certificado.listar_windows() if c["impressao"] == payload.impressao.strip().upper()), None)
    if not escolhido:
        raise HTTPException(status_code=400, detail="esse certificado não está mais no Windows")
    if escolhido["vencido"]:
        raise HTTPException(status_code=400, detail="esse certificado está vencido")

    publico = certificado.publico_do_windows(escolhido["impressao"])
    if publico.get("erro"):
        raise HTTPException(status_code=400, detail=publico["erro"])
    estado.cofre.usar_windows(publico, payload.senha)
    return {**estado.cofre.para_tela(), "aviso": "certificado de " + escolhido["titular"] + " pronto para assinar"}


@app.post("/api/certificado/windows/abrir")
def certificado_windows_abrir() -> dict:
    """Abre a janela "Certificados" do Windows."""
    if not certificado.abrir_janela_do_windows():
        raise HTTPException(status_code=400, detail="não consegui abrir a janela do Windows")
    return {"aberta": True}


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
    if not estado.cofre.instalado:
        raise HTTPException(status_code=400, detail="nenhum certificado instalado")

    lido = estado.cofre.abrir(payload.senha)
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


@app.post("/api/certificado/selo/restaurar")
def certificado_selo_restaurar() -> dict:
    return {"selo": estado.cofre.restaurar_selo()}


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
    if estado.cofre.instalado:
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
        "origem": cofre["origem"],
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

    if not estado.cofre.instalado:
        raise HTTPException(status_code=400, detail="nenhum certificado instalado")

    senha = payload.senha_certificado or estado.cofre.senha_agora()
    if not senha:
        raise HTTPException(status_code=400, detail="preciso da senha do certificado")

    cert = estado.cofre.abrir(senha)
    if cert.erro:
        raise HTTPException(status_code=400, detail=cert.erro)
    if payload.senha_certificado:
        estado.cofre.lembrar(payload.senha_certificado)

    alvos = assinatura.paginas_alvo(payload.paginas, doc.paginas, payload.intervalo)
    if not alvos:
        raise HTTPException(status_code=400, detail="nenhuma página escolhida")

    # O nome do assinado e decidido agora, antes da fila: se ja existe,
    # a tela pergunta (Renomear / Substituir) - na hora de assinar, ninguem
    # mais esta olhando.
    escolhas = nomes_mod.do_pedido({"decisoes": payload.decisoes})
    pendentes: list[dict] = []
    destino = _destino_do_assinado(Path(payload.arquivo), payload.guardar_biblioteca, escolhas, pendentes, set())
    nomes_mod.conferir(pendentes)

    dados = {
        **payload.model_dump(exclude={"senha_certificado", "decisoes"}),
        "paginas_alvo": alvos,
        "titular": cert.titular,
        "icp_brasil": cert.icp_brasil,
        **_destino_decidido(destino, escolhas),
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


@app.post("/api/assinar/lote")
def assinar_lote(payload: PedidoLote) -> dict:
    """
    Assina varios documentos com uma senha so - ou poe o lote na fila.

    Cada documento leva o selo onde a pessoa pos na tela e recebe a SUA
    assinatura: o lote e so a forma de pedir, nao junta os PDFs. A regra de
    alcada e a mesma do documento avulso; quando ela pede aprovacao, o lote
    vira UM pedido, aprovado (ou recusado) de uma vez, com os arquivos
    listados nele. Documento que nao da para assinar (nao abre, sem pagina
    escolhida) volta em `falhas` com o motivo, sem parar os outros.
    """
    if not payload.itens:
        raise HTTPException(status_code=400, detail="nenhum documento no lote")
    if len(payload.itens) > MAX_LOTE:
        raise HTTPException(status_code=400, detail=f"o lote aceita até {MAX_LOTE} documentos de uma vez")
    vistos = set()
    for item in payload.itens:
        chave = str(Path(item.arquivo)).lower()
        if chave in vistos:
            raise HTTPException(status_code=400, detail=f"{Path(item.arquivo).name} aparece duas vezes no lote")
        vistos.add(chave)

    if not estado.cofre.instalado:
        raise HTTPException(status_code=400, detail="nenhum certificado instalado")
    senha = payload.senha_certificado or estado.cofre.senha_agora()
    if not senha:
        raise HTTPException(status_code=400, detail="preciso da senha do certificado")
    cert = estado.cofre.abrir(senha)
    if cert.erro:
        raise HTTPException(status_code=400, detail=cert.erro)
    if payload.senha_certificado:
        estado.cofre.lembrar(payload.senha_certificado)

    comum = payload.model_dump(exclude={"itens", "senha_certificado"})
    prontos, recusados = [], []
    for item in payload.itens:
        doc = assinatura.ler(item.arquivo)
        nome = Path(item.arquivo).name
        if doc.erro:
            recusados.append({"arquivo": item.arquivo, "nome": nome, "motivo": doc.erro})
            continue
        alvos = assinatura.paginas_alvo(item.paginas, doc.paginas, item.intervalo)
        if not alvos:
            recusados.append({"arquivo": item.arquivo, "nome": nome, "motivo": "nenhuma página escolhida"})
            continue
        prontos.append({**comum, **item.model_dump(), "paginas_alvo": alvos,
                        "titular": cert.titular, "icp_brasil": cert.icp_brasil})
    # Os nomes dos assinados, todos antes de assinar ou de ir para a fila.
    escolhas = nomes_mod.do_pedido({"decisoes": payload.decisoes})
    pendentes: list[dict] = []
    ocupados: set[str] = set()
    for dados_item in prontos:
        destino = _destino_do_assinado(Path(dados_item["arquivo"]), dados_item.get("guardar_biblioteca", True),
                                       escolhas, pendentes, ocupados)
        dados_item.pop("decisoes", None)
        dados_item.update(_destino_decidido(destino, escolhas))
    nomes_mod.conferir(pendentes)
    if not prontos:
        raise HTTPException(status_code=400, detail="nenhum documento do lote pode ser assinado: " +
                            "; ".join(f"{r['nome']} ({r['motivo']})" for r in recusados[:3]))

    if not estado.prefs.pode("assinar"):
        etiquetas = ["não dá para desfazer", "lote"]
        if not cert.icp_brasil:
            etiquetas.append("certificado fora da ICP-Brasil")
        nomes = [Path(d["arquivo"]).name for d in prontos]
        lista = ", ".join(nomes[:5]) + (f" e mais {len(nomes) - 5}" if len(nomes) > 5 else "")
        quem = cert.titular or "seu certificado"
        quantos = f"{len(prontos)} documentos" if len(prontos) > 1 else "1 documento"
        resumo = (f"Vou assinar {quantos} com o {getattr(cert, 'tipo', '') or 'certificado'} de {quem}: {lista}. "
                  "Cada um recebe a sua assinatura, com o selo onde você o pôs na tela.")
        if payload.senha_pdf:
            resumo += " Os arquivos saem protegidos por senha."
        resumo += " Nada é enviado para a internet."
        pedido = estado.fila.pedir(
            f"Assinar {len(prontos)} documentos" if len(prontos) > 1 else f"Assinar {nomes[0]}",
            "assinatura",
            resumo=resumo,
            etiquetas=etiquetas,
            acao="assinatura.lote",
            # `arquivos` e o que Aprovacoes lista em "O que vai sair".
            dados={"itens": prontos, "arquivos": [d["arquivo"] for d in prontos]},
            reversivel=False,
        )
        return {"aguardando_aprovacao": True, "pedido": pedido.to_dict(), "falhas": recusados}

    feitos, falhas = _assinar_varios(prontos, senha)
    return {"aguardando_aprovacao": False, "feitos": feitos, "falhas": recusados + falhas}


def _assinar_varios(itens: list[dict], senha: str) -> tuple[list[dict], list[dict]]:
    """
    Assina um por um, sem parar no primeiro erro, e rele o Acervo UMA vez no
    fim - reler a cada documento deixaria um lote de vinte muito lento.
    """
    feitos, falhas = [], []
    for dados in itens:
        origem = dados.get("arquivo", "")
        try:
            resultado = _assinar_de_fato(dados, senha, recarregar=False)
        except Exception as exc:  # noqa: BLE001 - um PDF ruim nao derruba o lote
            resultado = assinatura.Resultado(erro=str(exc) or "erro ao assinar")
        if resultado.erro:
            falhas.append({"arquivo": origem, "nome": Path(origem).name, "motivo": resultado.erro})
        else:
            feitos.append({"origem": origem, **resultado.to_dict()})
    if feitos and any(d.get("guardar_biblioteca", True) for d in itens):
        estado.recarregar()
    return feitos, falhas


def _assinar_de_fato(dados: dict, senha: str, recarregar: bool = True) -> "assinatura.Resultado":
    """O trabalho em si, chamado direto ou depois do sim na fila."""
    origem = Path(dados["arquivo"])
    destino = _nome_do_assinado(origem, dados.get("guardar_biblioteca", True))
    if dados.get("destino"):
        # O nome decidido no pedido. Se, ate a aprovacao, apareceu um arquivo
        # com esse nome e ninguem mandou substituir, volta o " (n)" de sempre.
        decidido = Path(dados["destino"])
        if not decidido.exists() or dados.get("substituir"):
            destino = decidido

    ponto = None
    if dados.get("x") is not None and dados.get("y") is not None:
        ponto = (float(dados["x"]), float(dados["y"]))

    do_windows = estado.cofre.origem == "windows"
    if do_windows:
        # A senha do PAULUS e a porta: sem ela certa, o Windows nem e chamado.
        conferido = estado.cofre.abrir(senha)
        if conferido.erro:
            return assinatura.Resultado(erro=conferido.erro)
    resultado = assinatura.assinar(
        origem,
        destino,
        arquivo_pfx="" if do_windows else str(estado.cofre.arquivo),
        windows=estado.cofre.windows if do_windows else None,
        senha=senha,
        selo=estado.cofre.dados.get("selo") or {},
        escolha_paginas=dados.get("paginas", "ultima"),
        intervalo=dados.get("intervalo", ""),
        posicao=dados.get("posicao", "rodape_direita"),
        ponto=ponto,
        tamanho=float(dados["tamanho"]) if dados.get("tamanho") else None,
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

    if recarregar and dados.get("guardar_biblioteca", True):
        estado.recarregar()

    return resultado


def _destino_do_assinado(origem: Path, na_biblioteca: bool, escolhas: dict, pendentes: list, ocupados: set) -> Path | None:
    """Onde vai o assinado de `origem`, segundo a pessoa (src/nomes.py). O
    original nunca e o destino: substituir vale so para o "- assinado"."""
    pasta = estado.pasta if na_biblioteca else origem.parent
    return nomes_mod.destino(pasta, f"{origem.stem} - assinado.pdf", escolhas, pendentes, ocupados=ocupados)


def _destino_decidido(destino: Path | None, escolhas: dict) -> dict:
    if destino is None:
        return {}
    substituir = any(d.get("acao") == "substituir" and n == destino.name for n, d in escolhas.items())
    return {"destino": str(destino), "substituir": substituir}


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


# Onde ficavam, ate 27/09/2026, o certificado de conformidade e o extrato de
# apoio. O que ja esta la continua abrindo; o novo vai para o Acervo
# (_pasta_no_acervo).
CONFORMIDADE_DIR = DADOS_DIR / "conformidade"
APOIO_DIR = DADOS_DIR / "apoio"


def _pasta_no_acervo(*partes: str) -> Path:
    """
    Onde o PAULUS guarda o documento que ele mesmo gera - recibo, comprovante,
    planilha do mes, certificado de conformidade, transcricao: numa subpasta
    da pasta do programa, que o Acervo le. Tudo o que nasce aqui entra no
    Acervo; antes, ia para pastas internas que o Acervo nao via.
    """
    pasta = Path(estado.pasta).joinpath(*partes)
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _pdf_conhecido(caminho: str) -> Path:
    """
    O PDF pedido, se for um que o programa conhece: do Acervo, de uma pasta
    que o Acervo le, ou um relatorio de conformidade gerado aqui. Um caminho
    qualquer vindo da tela nao abre nem baixa arquivo arbitrario do disco.
    """
    try:
        alvo = Path(caminho).resolve()
    except (OSError, ValueError):
        raise HTTPException(status_code=404, detail="arquivo não encontrado") from None
    if alvo.suffix.lower() != ".pdf" or not alvo.is_file():
        raise HTTPException(status_code=404, detail="arquivo não encontrado")
    raizes = [Path(p).resolve() for p in estado.pastas_do_acervo()] + [CONFORMIDADE_DIR.resolve(), APOIO_DIR.resolve()]
    conhecidos = {Path(d.path).resolve() for d in estado.searcher.documents}
    if alvo in conhecidos or any(r == alvo.parent or r in alvo.parents for r in raizes):
        return alvo
    raise HTTPException(status_code=403, detail="esse arquivo não é do Acervo")


@app.post("/api/arquivos/abrir")
def arquivos_abrir(payload: dict) -> dict:
    """O PDF no programa padrao do Windows."""
    import os

    alvo = _pdf_conhecido(str(payload.get("caminho", "")))
    try:
        os.startfile(str(alvo))  # noqa: S606 - abre no programa do proprio Windows
    except (OSError, AttributeError) as exc:
        raise HTTPException(status_code=500, detail=f"não consegui abrir: {exc}") from exc
    return {"aberto": str(alvo)}


@app.get("/api/arquivos/baixar")
def arquivos_baixar(caminho: str) -> FileResponse:
    alvo = _pdf_conhecido(caminho)
    return FileResponse(alvo, media_type="application/pdf", filename=alvo.name)


@app.post("/api/arquivos/salvar")
def arquivos_salvar(payload: dict) -> dict:
    """
    Uma copia do PDF onde a pessoa escolheu no "Salvar como" do Windows.

    Na janela do programa, download de navegador nao chega a lugar nenhum:
    quem salva e o servidor. Vale para PDF do Acervo, relatorio gerado aqui ou
    PDF assinado por este programa - nunca um caminho qualquer.
    """
    import shutil

    origem = str(payload.get("caminho", ""))
    try:
        alvo = _pdf_conhecido(origem)
    except HTTPException:
        alvo = _assinados_daqui([origem])[0]
    destino = Path(str(payload.get("destino", "")))
    if not str(destino) or not destino.parent.is_dir():
        raise HTTPException(status_code=400, detail="escolha uma pasta que exista")
    if destino.suffix.lower() != ".pdf":
        destino = destino.with_name(destino.name + ".pdf")
    if destino.resolve() == alvo.resolve():
        return {"nome": destino.name, "pasta": str(destino.parent)}
    # Nome repetido na pasta: a mesma copia nao repete; outro arquivo, a tela
    # pergunta (Renomear / Substituir, src/nomes.py).
    escolhas = nomes_mod.do_pedido(payload)
    if destino.exists() and destino.name not in escolhas and file_sha1(destino) == file_sha1(alvo):
        return {"nome": destino.name, "pasta": str(destino.parent)}
    pendentes: list[dict] = []
    destino = nomes_mod.destino(destino.parent, destino.name, escolhas, pendentes)
    nomes_mod.conferir(pendentes)
    try:
        shutil.copy2(alvo, destino)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"não consegui salvar: {exc}") from exc
    return {"nome": destino.name, "pasta": str(destino.parent)}


@app.get("/api/arquivos/pagina")
def arquivos_pagina(caminho: str, numero: int = 1, largura: int = 700):
    """Uma pagina desenhada - a previa do relatorio antes de baixar."""
    from fastapi.responses import Response

    alvo = _pdf_conhecido(caminho)
    return Response(documento.pagina_png(alvo.read_bytes(), numero, largura),
                    media_type="image/png", headers={"Cache-Control": "no-cache"})


@app.post("/api/assinaturas/conformidade")
def assinaturas_conformidade(payload: dict) -> dict:
    """
    O "PAVLVS - Certificado de conformidade" do PDF: conferencia feita agora,
    gravada em data/conformidade para ver, baixar ou mandar.
    """
    import conformidade

    alvo = _pdf_conhecido(str(payload.get("arquivo", "")))
    # O certificado do mesmo PDF tem o mesmo nome: antes, o novo passava por
    # cima do antigo sem avisar. Agora a tela pergunta (src/nomes.py).
    pasta = _pasta_no_acervo("Assinaturas", "Certificados de conformidade")
    pendentes: list[dict] = []
    destino = nomes_mod.destino(pasta, conformidade.nome_do_relatorio(alvo), nomes_mod.do_pedido(payload), pendentes)
    nomes_mod.conferir(pendentes)
    assinaturas = assinatura.verificar(alvo, str(payload.get("senha", "")))
    relatorio = conformidade.gerar(alvo, assinaturas, pasta, destino)
    estado.recarregar_em_segundo_plano()
    tom, frase = conformidade.veredito(assinaturas)
    return {"caminho": str(relatorio), "nome": relatorio.name, "tom": tom, "veredito": frase,
            "paginas": documento.paginas_de(relatorio.read_bytes())}


@app.get("/api/assinar/baixar")
def assinar_baixar(arquivo: str) -> FileResponse:
    """Entrega o PDF assinado para o navegador salvar."""
    alvo = Path(arquivo)
    if not alvo.exists() or alvo.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="arquivo não encontrado")
    return FileResponse(alvo, media_type="application/pdf", filename=alvo.name)


def _assinados_daqui(arquivos: list[str]) -> list[Path]:
    """
    Os PDFs pedidos, se todos foram assinados por este programa.

    O .zip e a copia para uma pasta so aceitam o que esta no registro de
    assinaturas: um caminho qualquer vindo da tela nao vira um jeito de
    empacotar arquivo arbitrario do disco.
    """
    if not arquivos:
        raise HTTPException(status_code=400, detail="nenhum documento para salvar")
    conhecidos = set()
    for item in estado.assinaturas.itens:
        try:
            conhecidos.add(Path(item.get("destino") or "").resolve())
        except (OSError, ValueError):
            continue
    achados, vistos = [], set()
    for bruto in arquivos:
        try:
            alvo = Path(bruto).resolve()
        except (OSError, ValueError):
            raise HTTPException(status_code=404, detail="arquivo não encontrado") from None
        if alvo in vistos:
            continue
        if alvo not in conhecidos:
            raise HTTPException(status_code=403, detail=f"{alvo.name} não foi assinado por aqui")
        if not alvo.is_file():
            raise HTTPException(status_code=404, detail=f"{alvo.name} não está mais no disco")
        vistos.add(alvo)
        achados.append(alvo)
    return achados


def _nomes_no_zip(arquivos: list[Path]) -> list[str]:
    """Um nome por arquivo, sem colisao: o segundo "x.pdf" vira "x (2).pdf"."""
    usados, nomes = set(), []
    for alvo in arquivos:
        nome = alvo.name
        conta = 2
        while nome.lower() in usados:
            nome = f"{alvo.stem} ({conta}){alvo.suffix}"
            conta += 1
        usados.add(nome.lower())
        nomes.append(nome)
    return nomes


def _zip_dos_assinados(arquivos: list[Path]) -> bytes:
    import io
    import zipfile

    memoria = io.BytesIO()
    # PDF ja vem comprimido por dentro: guardar sem recomprimir e mais rapido
    # e o arquivo sai do mesmo tamanho.
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_STORED) as z:
        for alvo, nome in zip(arquivos, _nomes_no_zip(arquivos)):
            z.write(alvo, nome)
    return memoria.getvalue()


def _nome_do_zip() -> str:
    return f"PDFs assinados {datetime.now():%Y-%m-%d %H%M}.zip"


@app.get("/api/assinar/zip")
def assinar_zip_baixar(arquivo: list[str] = Query(default=[])) -> Response:
    """Os assinados num .zip, para o navegador baixar (um `arquivo=` por PDF)."""
    from urllib.parse import quote

    conteudo = _zip_dos_assinados(_assinados_daqui(arquivo))
    return Response(conteudo, media_type="application/zip",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(_nome_do_zip())}"})


@app.post("/api/assinar/zip")
def assinar_zip_gravar(payload: AssinadosParaSalvar) -> dict:
    """
    Os assinados num .zip gravado onde a pessoa escolheu no "Salvar como".
    Na janela do programa, download de navegador nao chega a lugar nenhum.
    """
    arquivos = _assinados_daqui(payload.arquivos)
    if not payload.caminho:
        raise HTTPException(status_code=400, detail="diga onde gravar o .zip")
    caminho = Path(payload.caminho)
    if caminho.suffix.lower() != ".zip":
        caminho = caminho.with_name(caminho.name + ".zip")
    # Um .zip com esse nome ja esta la: a tela pergunta (src/nomes.py).
    pendentes: list[dict] = []
    caminho = nomes_mod.destino(caminho.parent, caminho.name, nomes_mod.do_pedido({"decisoes": payload.decisoes}), pendentes)
    nomes_mod.conferir(pendentes)
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(_zip_dos_assinados(arquivos))
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"não consegui gravar o .zip: {exc}") from exc
    return {"caminho": str(caminho), "nome": caminho.name, "quantos": len(arquivos)}


@app.post("/api/assinar/copiar")
def assinar_copiar(payload: AssinadosParaSalvar) -> dict:
    """
    Os assinados, um a um, copiados para a pasta escolhida. Nome repetido
    com outro conteudo: a tela pergunta, e nada e copiado antes (src/nomes.py).
    """
    arquivos = _assinados_daqui(payload.arquivos)
    pasta = Path(payload.pasta) if payload.pasta else None
    if not pasta or not pasta.is_dir():
        raise HTTPException(status_code=400, detail="escolha uma pasta que exista")
    copiados = []
    for alvo, destino, copiar in _destinos_das_copias(arquivos, pasta, nomes_mod.do_pedido({"decisoes": payload.decisoes})):
        try:
            if copiar:
                shutil.copy2(alvo, destino)
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"não consegui copiar {alvo.name}: {exc}") from exc
        copiados.append(destino.name)
    return {"pasta": str(pasta), "copiados": copiados}


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
    import conformidade

    assinaturas = assinatura.verificar(arquivo, senha)
    tom, frase = conformidade.veredito(assinaturas)
    alvo = Path(arquivo)
    return {
        "assinaturas": assinaturas,
        "conferencia_limitada": True,
        "tom": tom,
        "veredito": frase,
        "arquivo": {"nome": alvo.name, **(conformidade.resumo_do_arquivo(alvo) if alvo.is_file() else {})},
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
    corpo_html: str = ""            # o mesmo texto com a formatacao da faixa de edicao
    anexos: list[str] = []          # caminhos de arquivos da biblioteca
    responder_a: str = ""           # Message-ID, quando e resposta
    referencias: str = ""           # as References da mensagem respondida
    senha: str = ""


def _credencial_ou_http(conta) -> str:
    """
    A senha, ou o access token renovado, da conta.

    401 quando falta algo que so a pessoa resolve (senha, ou entrar de novo
    pelo login); 502 quando o problema e de rede, que passa sozinho.
    """
    try:
        senha = estado.contas.credencial(conta)
    except correio_oauth.ErroOAuth as exc:
        codigo = 401 if exc.precisa_entrar else 502
        raise HTTPException(status_code=codigo, detail=str(exc)) from exc
    if not senha:
        raise HTTPException(status_code=401, detail=f"preciso da senha de {conta.email}")
    return senha


def _conta_da_vez(id_: str = ""):
    """
    A conta pedida (ou a padrao de quem pediu). De fora, so a da propria
    pessoa ou as do escritorio (E3b): a caixa de outra pessoa nao abre.
    """
    conta = estado.contas.obter(id_) if id_ else equipe.conta_email_padrao(estado.contas)
    if not conta:
        raise HTTPException(status_code=400, detail="nenhuma conta de e-mail conectada")
    if not equipe.conta_email_visivel(conta):
        raise HTTPException(status_code=403, detail="esta conta de e-mail é de outra pessoa")
    return conta


def _conta_e_senha(id_: str = "") -> tuple:
    """A conta pedida (ou a em uso) com a senha (ou o token) disponivel."""
    conta = _conta_da_vez(id_)
    return conta, _credencial_ou_http(conta)


def _info_oauth() -> dict:
    """Quais logins este PAULUS oferece: os provedores que vem registrados."""
    import oauth_app

    return {
        "google": {"configurado": oauth_app.configurado("google")},
        "microsoft": {"configurado": oauth_app.configurado("microsoft")},
        "prazo_s": correio_oauth.PRAZO_LOGIN,
    }


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
    dados = _contas_para_tela()
    dados["registro"] = estado.envios.para_tela(10)
    dados["pode_enviar_sozinho"] = estado.prefs.pode("enviar_mensagem")
    return dados


def _contas_para_tela() -> dict:
    dados = estado.contas.para_tela()
    # De fora, so as contas que a pessoa ve (a dela e as do escritorio), e a
    # dela abre primeiro (E3b).
    if equipe.pessoa_da_vez() is not None:
        visiveis = {c.id for c in estado.contas.itens if equipe.conta_email_visivel(c)}
        dados["contas"] = [c for c in dados["contas"] if c["id"] in visiveis]
        padrao = equipe.conta_email_padrao(estado.contas)
        dados["em_uso"] = padrao.id if padrao else ""
        for c in dados["contas"]:
            c["em_uso"] = c["id"] == dados["em_uso"]
    oauth = _info_oauth()
    dados["oauth"] = oauth
    if oauth["microsoft"]["configurado"]:
        dados["aviso_microsoft"] = correio_contas.AVISO_MICROSOFT_OAUTH
    return dados


@app.post("/api/email/detectar")
def email_detectar(payload: EnderecoEmail) -> dict:
    """Acha os servidores do endereco, pela tabela ou sondando o dominio."""
    oauth = _info_oauth()
    return correio_contas.detectar(
        payload.email, oauth={p: oauth[p]["configurado"] for p in ("google", "microsoft")},
    )


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
        if guardada and guardada.por_login:
            # A conta de login se testa com ela mesma: servidores e token dela.
            return correio.testar(guardada, _credencial_ou_http(guardada))
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
    return _contas_para_tela()


@app.post("/api/email/contas/senha")
def email_senha_conta(payload: SenhaConta) -> dict:
    """Confere a senha contra o servidor antes de aceitar como boa."""
    conta = estado.contas.obter(payload.id)
    if not conta:
        raise HTTPException(status_code=404, detail="conta não encontrada")
    if conta.por_login and not payload.senha:
        raise HTTPException(
            status_code=400,
            detail=f"esta conta entra pelo login {correio_oauth.rotulo(conta.autenticacao)} - use o botão de entrar",
        )
    if conta.por_login:
        # Senha de app numa conta que entrava pelo login: prova com a senha,
        # nos servidores dela, antes de trocar o jeito de entrar.
        import dataclasses

        conta = dataclasses.replace(conta, autenticacao="senha")

    prova = correio.testar(conta, payload.senha)
    if not prova["entrada"]:
        estado.contas.marcar_erro(conta, prova["erro_entrada"])
        raise HTTPException(status_code=400, detail=prova["erro_entrada"] or "o servidor recusou a senha")

    estado.contas.lembrar(conta.id, payload.senha)
    guardada = estado.contas.salvar_conta({"id": conta.id, "email": conta.email}, payload.senha)
    estado.contas.marcar_ok(guardada)
    return _contas_para_tela()


@app.post("/api/email/contas/{id_}/usar")
def email_usar_conta(id_: str) -> dict:
    if not estado.contas.usar(id_):
        raise HTTPException(status_code=404, detail="conta não encontrada")
    return _contas_para_tela()


@app.delete("/api/email/contas/{id_}")
def email_apagar_conta(id_: str) -> dict:
    if not estado.contas.apagar(id_):
        raise HTTPException(status_code=404, detail="conta não encontrada")
    return _contas_para_tela()


@app.post("/api/email/esquecer-senhas")
def email_esquecer_senhas() -> dict:
    quantas = estado.contas.esquecer_senhas()
    return {**_contas_para_tela(), "apagadas": quantas}


# ------------------------------------------- login com Google e Microsoft


class PedidoEntrada(BaseModel):
    provedor: str = ""
    email: str = ""          # login_hint, opcional
    tema: str = ""           # o tema do app, para a pagina de volta (claro/escuro)


def _trazer_o_paulus() -> None:
    """O "Voltar ao PAULUS" da pagina de volta do login: a janela vem para frente."""
    if estado.ao_pedido_externo:
        estado.ao_pedido_externo("mostrar", "")


@app.get("/api/email/oauth")
def email_oauth_info() -> dict:
    return _info_oauth()


def _concluir_entrada(provedor: str, tokens: dict, email: str, nome: str) -> dict:
    """Guarda a conta que entrou e prova a conexao, dizendo o que funcionou."""
    conta = estado.contas.ligar_oauth(provedor, email, nome, tokens)
    prova = correio.testar(conta, tokens["access_token"])
    if prova["entrada"]:
        estado.contas.marcar_ok(conta)
    else:
        estado.contas.marcar_erro(conta, prova["erro_entrada"])
    return {"conta": conta.to_dict(em_uso=estado.contas.em_uso is conta), "prova": prova}


@app.post("/api/email/oauth/entrar")
def email_oauth_entrar(payload: PedidoEntrada) -> dict:
    """
    Comeca o login: sobe o servidor de volta e abre o navegador.

    Um login por vez: comecar outro cancela o que estava esperando.
    """
    provedor = payload.provedor.strip().lower()
    if provedor not in correio_oauth.PROVEDORES:
        raise HTTPException(status_code=400, detail="provedor desconhecido")
    anterior = estado.entrada_oauth
    if anterior and not anterior.terminou:
        anterior.cancelar()
    try:
        entrada = correio_oauth.Entrada(
            provedor, _credenciais_oauth(provedor), _concluir_entrada,
            login_hint=payload.email.strip() if "@" in payload.email else "",
            tema="claro" if payload.tema == "claro" else "escuro", ao_voltar=_trazer_o_paulus,
        )
        estado.entrada_oauth = entrada
        return entrada.iniciar()
    except correio_oauth.ErroOAuth as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"não consegui abrir a porta local para o login: {exc}") from exc


@app.get("/api/email/oauth/andamento")
def email_oauth_andamento() -> dict:
    entrada = estado.entrada_oauth
    if not entrada:
        return {"fase": "nenhum"}
    dados = entrada.andamento()
    if entrada.fase == "pronto":
        dados["contas"] = _contas_para_tela()
    return dados


@app.post("/api/email/oauth/cancelar")
def email_oauth_cancelar() -> dict:
    entrada = estado.entrada_oauth
    if entrada and not entrada.terminou:
        entrada.cancelar()
    return entrada.andamento() if entrada else {"fase": "nenhum"}


@app.post("/api/email/oauth/reabrir")
def email_oauth_reabrir() -> dict:
    """Abre de novo a pagina do login que esta esperando - o mesmo pedido, nao outro."""
    entrada = estado.entrada_oauth
    return entrada.reabrir() if entrada else {"fase": "nenhum"}


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


@app.post("/api/email/anexos/encaminhar")
def email_anexos_encaminhar(payload: dict) -> dict:
    """
    Os anexos da mensagem para o Encaminhar: vao para data/encaminhar/<uid>
    (nao para o Acervo - sao do e-mail, nao documentos do escritorio) e a
    tela os poe na lista de anexos do envio, como qualquer outro.
    """
    conta, senha = _conta_e_senha(str(payload.get("conta_id", "")))
    if not conta.pode_anexar:
        raise HTTPException(status_code=403, detail="esta conta não permite que eu anexe arquivos")
    uid = re.sub(r"[^\w.-]", "", str(payload.get("uid", "")))[:40]
    if not uid:
        raise HTTPException(status_code=400, detail="qual mensagem?")
    try:
        anexos = correio.baixar_anexos(conta, senha, uid)
    except correio.ErroCorreio as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    pasta = DADOS_DIR / "encaminhar" / f"{conta.id}-{uid}"
    pasta.mkdir(parents=True, exist_ok=True)
    saida = []
    for nome, dados in anexos:
        alvo = pasta / (Path(nome).name or "anexo")
        alvo.write_bytes(dados)
        saida.append({"path": str(alvo), "nome": alvo.name, "mb": round(len(dados) / (1024 * 1024), 2)})
    return {"anexos": saida}


@app.post("/api/email/anexo/guardar")
def email_guardar_anexo(payload: dict) -> dict:
    """Traz o anexo para a biblioteca. Nome repetido: a tela decide."""
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
    # O mesmo anexo ja guardado nao vira copia; outro com o mesmo nome, a
    # tela pergunta (Renomear / Substituir, src/nomes.py).
    igual = estado.pasta / limpo
    escolhas = nomes_mod.do_pedido(payload)
    if igual.exists() and limpo not in escolhas and igual.read_bytes() == dados:
        return {"guardado": limpo, "documentos": len(estado.searcher.documents), "ja_estava": True}
    pendentes: list[dict] = []
    destino = nomes_mod.destino(estado.pasta, limpo, escolhas, pendentes)
    nomes_mod.conferir(pendentes)

    destino.write_bytes(dados)
    # N15: o que vem do e-mail nunca vai à nuvem - fica marcado ao entrar.
    nuvem_mod.marcar_do_email(estado, destino)
    return {"guardado": destino.name, "documentos": estado.recarregar()}


@app.post("/api/email/arquivar")
def email_arquivar(payload: dict) -> dict:
    """Uma (`uid`) ou varias (`uids`, a selecao da lista) numa conexao so."""
    conta, senha = _conta_e_senha(str(payload.get("conta_id", "")))
    if isinstance(payload.get("uids"), list):
        uids = correio._uids_validos(payload["uids"])
        if not uids:
            raise HTTPException(status_code=400, detail="nenhuma mensagem escolhida")
        try:
            feito = correio.arquivar_varias(conta, senha, uids)
        except correio.ErroCorreio as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        so_lidas = feito["so_lidas"]
        return {
            **feito,
            "aviso": ("" if not so_lidas else
                      "seu servidor não tem pasta de arquivo - marquei como lidas" if not feito["arquivadas"] else
                      f"{so_lidas} não foram copiadas para o arquivo - ficaram na caixa, marcadas como lidas"),
        }
    uid = str(payload.get("uid", ""))
    try:
        movida = correio.arquivar(conta, senha, uid)
    except correio.ErroCorreio as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "arquivada": movida,
        "aviso": "" if movida else "seu servidor não tem pasta de arquivo - marquei só como lida",
    }


@app.post("/api/email/estrela")
def email_estrela(payload: dict) -> dict:
    """Poe ou tira a estrela (\\Flagged) nas mensagens escolhidas."""
    conta, senha = _conta_e_senha(str(payload.get("conta_id", "")))
    uids = correio._uids_validos(payload.get("uids") or [])
    if not uids:
        raise HTTPException(status_code=400, detail="nenhuma mensagem escolhida")
    try:
        feitas = correio.sinalizar(conta, senha, uids, bool(payload.get("sim", True)))
    except correio.ErroCorreio as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"feitas": feitas}


@app.post("/api/email/excluir")
def email_excluir(payload: dict) -> dict:
    """Manda as mensagens escolhidas para a lixeira do servidor (nao apaga de vez)."""
    conta, senha = _conta_e_senha(str(payload.get("conta_id", "")))
    uids = correio._uids_validos(payload.get("uids") or [])
    if not uids:
        raise HTTPException(status_code=400, detail="nenhuma mensagem escolhida")
    try:
        feito = correio.excluir_varias(conta, senha, uids)
    except correio.ErroCorreio as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if feito["sem_lixeira"]:
        raise HTTPException(status_code=409, detail="seu servidor não tem lixeira - não excluí nada, para não apagar de vez")
    falta = len(uids) - feito["excluidas"]
    return {**feito, "aviso": f"{falta} não foram para a lixeira - ficaram na caixa" if falta else ""}


@app.post("/api/email/marcar")
def email_marcar(payload: dict) -> dict:
    """Marca como lidas (ou nao lidas) as mensagens escolhidas na lista."""
    conta, senha = _conta_e_senha(str(payload.get("conta_id", "")))
    uids = correio._uids_validos(payload.get("uids") or [])
    if not uids:
        raise HTTPException(status_code=400, detail="nenhuma mensagem escolhida")
    lido = bool(payload.get("lido", True))
    try:
        n = correio.marcar_lidas(conta, senha, uids, lido)
    except correio.ErroCorreio as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"marcadas": n, "lido": lido, "uids": uids}


# O resumo da caixa pelo modelo: em segundo plano, um por vez, guardado pela
# chave das mensagens. A regra responde na hora, no mesmo pedido.
_resumos_da_caixa = correio.ResumosDaCaixa()


def _cabecalhos_do_pedido(payload: dict) -> list[dict]:
    campos = ("uid", "de_nome", "de_email", "de_cadastro", "assunto", "prazo", "lido", "respondido", "tem_anexo")
    return [{k: m.get(k) for k in campos} for m in (payload.get("mensagens") or [])[:200] if isinstance(m, dict)]


@app.post("/api/email/caixa/resumo")
def email_caixa_resumo(payload: dict) -> dict:
    """
    O resumo da lista que a tela mostra: a regra agora, o modelo depois.

    Recebe os cabecalhos que a lista ja tem - nenhum corpo sai do servidor
    de e-mail para isto. O modelo roda numa thread; a resposta volta na hora
    com "resumindo" e a tela pergunta de novo em GET.
    """
    mensagens = _cabecalhos_do_pedido(payload)
    chave = correio.chave_do_resumo(str(payload.get("conta_id", "")), mensagens)
    regra = correio.resumo_por_regra(mensagens)
    if payload.get("de_novo"):
        _resumos_da_caixa.esquecer(chave)
    modelo = _resumos_da_caixa.estado(chave)
    if modelo.get("estado") in ("pronto", "resumindo", "na_fila") or not mensagens:
        return {"chave": chave, "regra": regra, "modelo": modelo if mensagens else {"estado": "nenhum"}}
    disponivel, motivo = check_ollama(estado.client.model)
    if not disponivel:
        return {"chave": chave, "regra": regra, "modelo": {"estado": "indisponivel", "motivo": motivo}}
    return {"chave": chave, "regra": regra, "modelo": _resumos_da_caixa.pedir(chave, mensagens, estado.cliente_para("email"))}


_contextos_de_email = correio.ResumosDaCaixa(fazer=correio.contexto_da_mensagem, limite=60)


@app.post("/api/email/contexto")
def email_contexto(payload: dict) -> dict:
    """
    O "Contexto IA" da mensagem aberta, pelo modelo desta maquina.

    Recebe o texto que a tela ja tem (a pessoa abriu a mensagem). Roda numa
    thread, como o resumo da caixa: volta "resumindo" e a tela pergunta de
    novo em GET. Guardado por conta e UID - abrir de novo nao roda outra vez.
    """
    uid = str(payload.get("uid", "")).strip()
    if not uid:
        raise HTTPException(status_code=400, detail="qual mensagem?")
    chave = f"{payload.get('conta_id', '')}:{uid}"
    if payload.get("de_novo"):
        _contextos_de_email.esquecer(chave)
    feito = _contextos_de_email.estado(chave)
    if feito.get("estado") in ("pronto", "resumindo", "na_fila"):
        return {"chave": chave, "modelo": feito}
    disponivel, motivo = check_ollama(estado.client.model)
    if not disponivel:
        return {"chave": chave, "modelo": {"estado": "indisponivel", "motivo": motivo}}
    item = {"de": str(payload.get("de", ""))[:200], "assunto": str(payload.get("assunto", ""))[:300],
            "corpo": str(payload.get("corpo", ""))}
    return {"chave": chave, "modelo": _contextos_de_email.pedir(chave, [item], estado.cliente_para("email"))}


@app.get("/api/email/contexto")
def email_contexto_estado(chave: str) -> dict:
    return {"chave": chave, "modelo": _contextos_de_email.estado(chave)}


@app.get("/api/email/caixa/resumo")
def email_caixa_resumo_estado(chave: str) -> dict:
    return {"chave": chave, "modelo": _resumos_da_caixa.estado(chave)}


@app.post("/api/email/reescrever")
def email_reescrever(payload: dict) -> dict:
    """
    O "Pedir aqui" do Escrever: o modelo reescreve o corpo do e-mail.

    Volta como sugestao - a tela troca o texto e oferece manter ou
    descartar. Leva cerca de um minuto nesta maquina.
    """
    pedido = str(payload.get("pedido", "")).strip()
    if not pedido:
        raise HTTPException(status_code=400, detail="diga o que mudar no e-mail")
    disponivel, motivo = check_ollama(estado.client.model)
    if not disponivel:
        raise HTTPException(status_code=503, detail=motivo)
    try:
        texto = correio.reescrever_email(estado.cliente_para("redacao"), pedido,
                                         str(payload.get("assunto", "")), str(payload.get("corpo", "")))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"sugestao": texto, "pedido": pedido}


# ------------------------------------------------------ apoiar o projeto


@app.post("/api/apoio/pix")
def apoio_pix(payload: dict) -> dict:
    """O Pix de apoio: o site (Worker) cria no Mercado Pago e devolve o QR."""
    try:
        return apoio.criar_pix(float(payload.get("valor") or 0), str(payload.get("email", "")), str(payload.get("mural") or ""))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="valor inválido") from exc
    except apoio.ErroDeApoio as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/apoio/pix/recuperar")
def apoio_pix_recuperar(payload: dict) -> dict:
    """Os Pix pagos que o historico desta maquina perdeu (versao antiga)."""
    try:
        return apoio.recuperar_pix([str(e) for e in payload.get("emails") or []], [str(d) for d in payload.get("datas") or []])
    except apoio.ErroDeApoio as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/apoio/pix/{id_}")
def apoio_pix_situacao(id_: str) -> dict:
    try:
        return apoio.situacao_do_pix(id_)
    except apoio.ErroDeApoio as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/apoio/assinatura/{id_}")
def apoio_assinatura_situacao(id_: str) -> dict:
    try:
        return apoio.situacao_da_assinatura(id_)
    except apoio.ErroDeApoio as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/apoio/neste-mes")
def apoio_neste_mes() -> dict:
    """
    O que o convite para apoiar diz (pacote de telas, `Assistente - Apoiar`):
    quantos documentos o PAULUS leu para responder neste mes (os citados nas
    respostas e os mostrados na conversa) e quantos lancamentos foram
    montados no Financeiro. Conta feita aqui, com o que esta gravado; nada
    sai da maquina.
    """
    hoje = date.today()
    inicio = hoje.replace(day=1).isoformat()
    lidos: set[str] = set()
    resumos = [r for g in estado.trabalhos.listar().get("grupos", []) for r in g.get("trabalhos", [])]
    for resumo in resumos:
        t = estado.trabalhos.obter(resumo.get("id", ""))
        if not t:
            continue
        for m in t.mensagens:
            if m.autor != "paulus" or str(m.em or "")[:10] < inicio:
                continue
            for f in m.fontes or []:
                nome = (f or {}).get("documento") if isinstance(f, dict) else None
                if nome and not (f or {}).get("material"):
                    lidos.add(nome)
            feito = m.feito or {}
            if feito.get("tipo") == "exibir" and feito.get("nome"):
                lidos.add(feito["nome"])
    lancamentos = estado.base.um(
        "SELECT COUNT(*) AS n FROM lancamentos WHERE criado_em >= ?", (inicio,)) or {"n": 0}
    import calendar
    ultimo = calendar.monthrange(hoje.year, hoje.month)[1]
    return {"mes": hoje.strftime("%Y-%m"), "documentos": len(lidos), "lancamentos": int(lancamentos["n"] or 0),
            "faltam_dias": ultimo - hoje.day}


@app.get("/api/publico/{qual}")
def publico_do_site(qual: str) -> dict:
    """
    O historico (desenvolvimento) e o mural (apoiadores) que o site publica,
    para a tela Desenvolvimento aberto e o "Quem ja apoia". So leitura; a
    ultima copia fica em dados/publico para quando nao houver internet. A
    versao instalada vai junto, para a tela marcar "e a sua versao".
    """
    try:
        dados = apoio.publico(qual, DADOS_DIR / "publico")
    except apoio.ErroDeApoio as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {**dados, "versao_instalada": VERSAO}


@app.post("/api/apoio/extrato")
def apoio_extrato(payload: dict) -> dict:
    """
    O "PAVLVS - Extrato de contribuicoes" em PDF: os Pix confirmados nesta
    maquina (a tela manda) e as cobrancas do cartao, consultadas no Mercado
    Pago agora. Gravado no Acervo, para baixar pela janela de sempre.
    """
    import extrato_apoio

    pix = [p for p in (payload.get("pix") or []) if isinstance(p, dict)][:500]
    cobrancas: list = []
    # A assinatura de agora e as ja interrompidas: as cobrancas de todas.
    for ass in [a for a in (payload.get("assinaturas") or []) if isinstance(a, dict)][:20]:
        if not (ass.get("id") and ass.get("chave")):
            continue
        try:
            cobrancas += apoio.pagamentos_da_assinatura(str(ass["id"]), str(ass["chave"])).get("pagamentos", [])
        except apoio.ErroDeApoio as exc:
            raise HTTPException(status_code=502, detail=f"não consegui as cobranças do cartão: {exc}") from exc
    # Sem nome ou e-mail na tela Apoiar, valem os de Configuracoes > Meus dados.
    pessoa = estado.prefs.dados.get("pessoa") or {}
    nome = str(payload.get("nome") or "").strip() or str(pessoa.get("nome") or "").strip()
    email = str(payload.get("email") or "").strip() or str(pessoa.get("email") or "").strip()
    try:
        caminho = extrato_apoio.gerar(_pasta_no_acervo("PAULUS", "Extratos de apoio"), nome=nome[:80], email=email[:120],
                                      pix=pix, cobrancas=cobrancas)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"não consegui montar o extrato: {exc}") from exc
    estado.recarregar_em_segundo_plano()
    return {"caminho": str(caminho), "nome": caminho.name}


@app.post("/api/apoio/assinatura/{id_}/valor")
def apoio_assinatura_valor(id_: str, payload: dict) -> dict:
    try:
        return apoio.mudar_valor(id_, str(payload.get("chave", "")), float(payload.get("valor") or 0))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="valor inválido") from exc
    except apoio.ErroDeApoio as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/apoio/assinatura/{id_}/interromper")
def apoio_assinatura_interromper(id_: str, payload: dict) -> dict:
    try:
        return apoio.interromper(id_, str(payload.get("chave", "")))
    except apoio.ErroDeApoio as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/apoio/assinatura")
def apoio_assinatura(payload: dict) -> dict:
    """A assinatura no cartao: devolve o link da pagina do Mercado Pago."""
    try:
        return apoio.criar_assinatura(float(payload.get("valor") or 0), str(payload.get("email", "")), str(payload.get("mural") or ""))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="valor inválido") from exc
    except apoio.ErroDeApoio as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/email/traduzir")
def email_traduzir(payload: dict) -> dict:
    """
    A mensagem aberta em portugues, pelo tradutor desta maquina (src/traducao.py):
    o texto e, quando ha, o HTML com as tags intactas. Menos de um segundo.
    """
    texto = str(payload.get("texto", ""))
    html_email = str(payload.get("html", ""))
    lingua = traducao.adivinhar_lingua(texto) or str(payload.get("lingua", ""))
    if lingua not in traducao.PACOTES:
        raise HTTPException(status_code=400, detail="não reconheci a língua da mensagem")
    if not traducao.disponivel(lingua):
        raise HTTPException(status_code=503, detail="o tradutor desta máquina não está instalado (python src/traducao.py baixar)")
    try:
        return {
            "lingua": lingua,
            "texto": traducao.traduzir_texto(texto, lingua) if texto.strip() else "",
            "html": traducao.traduzir_html(html_email, lingua) if html_email.strip() else "",
        }
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/email/anexos/conferir")
def email_anexos_conferir(payload: dict) -> dict:
    """Nome e tamanho dos arquivos escolhidos para anexar - e se passam do limite."""
    achados = []
    for bruto in (payload.get("caminhos") or [])[:40]:
        alvo = Path(str(bruto))
        existe = alvo.is_file()
        tamanho = alvo.stat().st_size if existe else 0
        achados.append({
            "path": str(alvo), "nome": alvo.name, "existe": existe,
            "mb": round(tamanho / (1024 * 1024), 2),
            "grande": tamanho > correio.MAX_ANEXO_BYTES,
        })
    return {"anexos": achados, "limite_mb": correio.MAX_ANEXO_BYTES // (1024 * 1024)}


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
        texto, aviso = correio.sugerir_resposta_com_aviso(estado.cliente_para("email"), msg, quem)
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "rascunho": texto,
        # Injecao de prompt suspeita, ou link/endereco que o modelo pos e que
        # nao estava no e-mail (src/blindagem.py). A tela avisa.
        "aviso": aviso,
        "para": [msg.de_email],
        "assunto": msg.assunto if msg.assunto.lower().startswith("re:") else f"Re: {msg.assunto}",
        "responder_a": msg.message_id,
        "referencias": msg.referencias,
        "sobre": msg.assunto,
    }


# ---------------------------------------------------------------- enviar


def _montar_do_pedido(payload: PedidoEnvio):
    conta = _conta_da_vez(payload.conta_id)

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
            corpo_html=payload.corpo_html,
            cc=correio.enderecos(payload.cc),
            anexos=anexos,
            responder_a=payload.responder_a,
            referencias=payload.referencias,
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
        "html": correio.html_da_mensagem(msg),
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
def email_enviar(payload: PedidoEnvio, request: Request = None) -> dict:
    """
    Envia, ou poe o pedido na fila.

    E-mail que sai nao volta. Sem a permissao "enviar sem confirmar" - que vem
    desligada, no programa e na conta -, isto nao manda nada: monta o pedido e
    devolve para a fila de aprovacao.

    De fora, vai SEMPRE para a fila, com a permissao ligada ou nao, e senha de
    e-mail nao se entrega: credencial so se configura no computador do
    escritorio (acesso-remoto/v0, §5).
    """
    de_fora = not rotas_do_acesso.e_local(request)
    if de_fora and payload.senha:
        raise HTTPException(status_code=403, detail=politicas_do_acesso.MENSAGEM_BLOQUEADA)
    conta, msg, para = _montar_do_pedido(payload)

    if payload.senha and not conta.por_login:
        estado.contas.lembrar(conta.id, payload.senha)
    if not estado.contas.tem_credencial(conta):
        if conta.por_login:
            raise HTTPException(
                status_code=401,
                detail=f"é preciso entrar de novo com {correio_oauth.rotulo(conta.autenticacao)} em {conta.email}",
            )
        raise HTTPException(status_code=401, detail=f"preciso da senha de {conta.email}")

    anexos = [Path(a).name for a in payload.anexos]
    # O pedido guarda a conta escolhida agora: aprovado depois, na janela do
    # servidor, sai pela mesma conta - e nao pela "em uso" de la (E3b).
    payload.conta_id = conta.id
    livre = estado.prefs.pode("enviar_mensagem") and conta.pode_enviar_sem_confirmar and not de_fora

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

    try:
        senha = estado.contas.credencial(conta)
    except correio_oauth.ErroOAuth as exc:
        raise RuntimeError(str(exc)) from exc
    if not senha:
        raise RuntimeError(f"a senha de {conta.email} não está mais disponível - entre na conta de novo")

    try:
        resultado = correio.enviar(conta, senha, msg, correio.enderecos(payload.cco))
    except correio.ErroCorreio as exc:
        raise RuntimeError(str(exc)) from exc

    estado.contas.marcar_ok(conta)
    return estado.envios.anotar(conta.email, resultado)


# ------------------------------------- o e-mail pela conversa (rascunho)


def _rascunhos_da_conversa(trabalho) -> dict:
    return trabalho.contexto.setdefault("email_rascunhos", {})


def _conferencias_do_rascunho(conta, msg, corpo: str, request, aviso: str = "") -> list[dict]:
    import email_pela_conversa

    documentos = [(d.name, d.text or "") for d in estado.searcher.documents]
    return email_pela_conversa.conferir(corpo, msg.corpo if msg else "", documentos, date.today(),
                                        _passa_por_aprovacao(conta, request), aviso)


@app.get("/api/email/conversa/rascunho")
def email_conversa_rascunho_ler(trabalho_id: str, uid: str) -> dict:
    """O rascunho guardado nesta conversa, para reabrir como estava."""
    trabalho = estado.trabalhos.obter(trabalho_id)
    if not trabalho:
        raise HTTPException(status_code=404, detail="conversa não encontrada")
    guardado = _rascunhos_da_conversa(trabalho).get(str(uid))
    if not guardado:
        raise HTTPException(status_code=404, detail="ainda não há rascunho")
    return guardado


@app.post("/api/email/conversa/rascunho")
def email_conversa_rascunho(payload: dict, request: Request) -> dict:
    """
    Escreve a resposta com o pedido da conversa ("confirmando o acordo da
    parcela de setembro") e guarda o rascunho nela. As conferencias saem por
    regra (src/email_pela_conversa.py). Nada e enviado.
    """
    import email_pela_conversa

    trabalho = estado.trabalhos.obter(str(payload.get("trabalho_id", "")))
    if not trabalho:
        raise HTTPException(status_code=404, detail="conversa não encontrada")
    conta, senha = _conta_e_senha(str(payload.get("conta_id", "")))
    if not conta.pode_rascunhar:
        raise HTTPException(status_code=403, detail="esta conta não permite que eu escreva rascunhos")
    disponivel, motivo = check_ollama(estado.client.model)
    if not disponivel:
        raise HTTPException(status_code=503, detail=motivo)
    uid = str(payload.get("uid", ""))
    quem = estado.prefs.dados.get("pessoa", {}).get("nome", "") or conta.nome
    # O e-mail novo ("escreva um e-mail para..."): sem mensagem de origem.
    if uid.startswith("novo-"):
        para = [x for x in payload.get("para") or [] if isinstance(x, dict) and x.get("email")]
        try:
            assunto, texto, aviso = email_pela_conversa.escrever_novo(estado.cliente_para("email"), (para[0].get("nome") if para else "") or "",
                                                                     str(payload.get("pedido", "")), quem)
        except OllamaError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        rascunho = {
            "uid": uid, "conta_id": conta.id, "de": conta.email, "novo_email": True,
            "para": [{"nome": str(x.get("nome", "")), "email": str(x["email"])} for x in para], "cc": [], "cco": [],
            "assunto": assunto, "sobre": "", "corpo": texto, "corpo_html": "", "anexos": [],
            "aviso": aviso, "pelo_assistente": True, "palavras": email_pela_conversa.palavras(texto),
            "conferencias": _conferencias_do_rascunho(conta, None, texto, request, aviso),
            "salvo_em": datetime.now().isoformat(timespec="seconds"),
        }
        _rascunhos_da_conversa(trabalho)[uid] = rascunho
        for m in reversed(trabalho.mensagens):
            p = m.proposta or {}
            if p.get("tipo") == "email" and str((p.get("campos") or {}).get("uid")) == uid:
                m.texto = ("Preparei o e-mail. O texto está na caixa abaixo para você revisar — "
                           + ("enviar passa por Aprovações." if _passa_por_aprovacao(conta, request) else "nada sai sem o seu clique em Enviar."))
                break
        estado.trabalhos.salvar(trabalho)
        return rascunho
    try:
        msg = correio.abrir(conta, senha, uid, marcar_lido=False)
    except correio.ErroCorreio as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    try:
        texto, aviso = email_pela_conversa.escrever_resposta(estado.cliente_para("email"), msg,
                                                             str(payload.get("pedido", "")), quem)
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    rascunho = {
        "uid": uid, "conta_id": conta.id, "de": conta.email,
        "para": [{"nome": msg.de_nome, "email": msg.de_email}], "cc": [], "cco": [],
        "assunto": msg.assunto if msg.assunto.lower().startswith("re:") else f"Re: {msg.assunto}",
        "responder_a": msg.message_id, "referencias": msg.referencias,
        "sobre": msg.assunto, "corpo": texto, "corpo_html": "", "anexos": [],
        "aviso": aviso, "pelo_assistente": True, "palavras": email_pela_conversa.palavras(texto),
        "conferencias": _conferencias_do_rascunho(conta, msg, texto, request, aviso),
        "salvo_em": datetime.now().isoformat(timespec="seconds"),
    }
    _rascunhos_da_conversa(trabalho)[uid] = rascunho
    # A frase da conversa passa a dizer o que aconteceu (pacote de telas:
    # "Preparei a resposta...").
    for m in reversed(trabalho.mensagens):
        p = m.proposta or {}
        if p.get("tipo") == "email" and str((p.get("campos") or {}).get("uid")) == uid:
            aprovacao = _passa_por_aprovacao(conta, request)
            m.texto = ("Preparei a resposta. O texto está na caixa abaixo para você revisar — "
                       + ("enviar passa por Aprovações." if aprovacao else "nada sai sem o seu clique em Enviar."))
            break
    estado.trabalhos.salvar(trabalho)
    return rascunho


@app.put("/api/email/conversa/rascunho")
def email_conversa_rascunho_guardar(payload: dict, request: Request) -> dict:
    """Guarda o que a pessoa mudou no rascunho e refaz as conferencias."""
    import email_pela_conversa

    trabalho = estado.trabalhos.obter(str(payload.get("trabalho_id", "")))
    if not trabalho:
        raise HTTPException(status_code=404, detail="conversa não encontrada")
    uid = str(payload.get("uid", ""))
    antes = _rascunhos_da_conversa(trabalho).get(uid) or {}
    conta = _conta_da_vez(str(payload.get("conta_id", "") or antes.get("conta_id", "")))
    corpo = str(payload.get("corpo", ""))
    msg = None
    if not uid.startswith("novo-"):
        try:
            conta_msg, senha = _conta_e_senha(antes.get("conta_id", "") or conta.id)
            msg = correio.abrir(conta_msg, senha, uid, marcar_lido=False)
        except (HTTPException, correio.ErroCorreio):
            msg = None
    def enderecos(chave):
        saida = []
        for x in payload.get(chave) or []:
            if isinstance(x, dict) and str(x.get("email", "")).strip():
                saida.append({"nome": str(x.get("nome", "")).strip(), "email": str(x["email"]).strip()})
            elif isinstance(x, str) and x.strip():
                saida.append({"nome": "", "email": x.strip()})
        return saida
    rascunho = {
        **antes, "uid": uid, "conta_id": conta.id, "de": conta.email,
        "para": enderecos("para"), "cc": enderecos("cc"), "cco": enderecos("cco"),
        "assunto": str(payload.get("assunto", antes.get("assunto", ""))), "corpo": corpo,
        "corpo_html": str(payload.get("corpo_html", "")),
        "anexos": [str(a) for a in payload.get("anexos") or []],
        "pelo_assistente": bool(payload.get("pelo_assistente", antes.get("pelo_assistente", False))),
        "responder_a": str(payload.get("responder_a", antes.get("responder_a", "")))[:300],
        "referencias": str(payload.get("referencias", antes.get("referencias", "")))[-1500:],
        "novo_email": bool(payload.get("novo_email", antes.get("novo_email", False))),
        "palavras": email_pela_conversa.palavras(corpo),
        "conferencias": _conferencias_do_rascunho(conta, msg, corpo, request, antes.get("aviso", "")),
        "salvo_em": datetime.now().isoformat(timespec="seconds"),
    }
    _rascunhos_da_conversa(trabalho)[uid] = rascunho
    estado.trabalhos.salvar(trabalho)
    return rascunho


@app.post("/api/email/conversa/proxima")
def email_conversa_proxima(payload: dict) -> dict:
    """
    "Próxima que pede resposta": a mensagem abre na conversa e FICA nela - a
    fala e o cartao entram na conversa guardada, como o "abra o e-mail...",
    e voltam ao reabrir. Devolve {texto, proposta}.
    """
    import email_pela_conversa

    trabalho = estado.trabalhos.obter(str(payload.get("trabalho_id", "")))
    if not trabalho:
        raise HTTPException(status_code=404, detail="conversa não encontrada")
    conta, senha = _conta_e_senha(str(payload.get("conta_id", "")))
    try:
        msg = correio.abrir(conta, senha, str(payload.get("uid", "")), marcar_lido=True)
    except correio.ErroCorreio as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    m = msg.to_dict()
    cabeca = {k: m.get(k) for k in ("uid", "de_nome", "de_email", "para", "assunto", "quando", "quando_curto")}
    cabeca.update({"conta_id": conta.id, "conta_email": conta.email})
    codigo = email_pela_conversa.codigo_de_verificacao(m.get("assunto", ""), m.get("corpo", ""))
    texto = ("A próxima que pede resposta: " + (m.get("de_nome") or m.get("de_email") or "") + ", “" + (m.get("assunto") or "sem assunto") + "”. "
             + email_pela_conversa.frase_da_mensagem(m, codigo).replace("Abri aqui. ", ""))
    proposta = {"tipo": "email", "titulo": m.get("assunto") or "", "porque": "a próxima que pede resposta", "pergunta": "",
                "campos": {"acao": "abrir", "codigo": codigo, "prazo": m.get("prazo") or "", "prazo_trecho": m.get("prazo_trecho") or "",
                           "sem_resposta": email_pela_conversa.sem_resposta(m.get("de_email", "")), **cabeca}}
    trabalho.dizer("paulus", texto, proposta=proposta)
    estado.trabalhos.salvar(trabalho)
    return {"texto": texto, "proposta": proposta}


INSTRUCAO_PERGUNTA_EMAIL = """Voce e assistente de um advogado brasileiro. Responda a
pergunta dele sobre o e-mail abaixo, em portugues do Brasil, em poucas linhas.
Use so o que esta no e-mail; se o e-mail nao diz, diga que nao diz. Nao
invente nome, data, valor nem prazo. Nao use marcacao nem asteriscos."""


@app.post("/api/email/conversa/perguntar")
def email_conversa_perguntar(payload: dict) -> dict:
    """
    "No e-mail": a pergunta e sobre a mensagem aberta na conversa. O texto do
    remetente vai cercado (src/blindagem.py) e a pergunta e a resposta
    entram na conversa.
    """
    import blindagem

    trabalho = estado.trabalhos.obter(str(payload.get("trabalho_id", "")))
    if not trabalho:
        raise HTTPException(status_code=404, detail="conversa não encontrada")
    pergunta = " ".join(str(payload.get("pergunta", "")).split())[:600]
    if not pergunta:
        raise HTTPException(status_code=400, detail="falta a pergunta")
    conta, senha = _conta_e_senha(str(payload.get("conta_id", "")))
    disponivel, motivo = check_ollama(estado.client.model)
    if not disponivel:
        raise HTTPException(status_code=503, detail=motivo)
    try:
        msg = correio.abrir(conta, senha, str(payload.get("uid", "")), marcar_lido=False)
    except correio.ErroCorreio as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    original = f"De: {msg.de_nome} <{msg.de_email}>\nAssunto: {msg.assunto}\n\n{msg.corpo[:4000]}"
    try:
        resposta = estado.cliente_para("email").ask(INSTRUCAO_PERGUNTA_EMAIL + "\n\n" + blindagem.REGRA,
                                                    "E-mail:\n" + blindagem.cercar(original) + "\n\nPergunta do advogado: " + pergunta)
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    texto, fora = blindagem.conferir_saida(" ".join((resposta or "").split("\n\n")).strip() or "Não consegui responder.",
                                           original, [msg.de_email])
    aviso = blindagem.aviso(blindagem.suspeitas(original))
    trabalho.dizer("pessoa", pergunta)
    trabalho.dizer("paulus", texto + (f"\n\n{aviso}" if aviso else ""))
    estado.trabalhos.salvar(trabalho)
    return {"texto": texto, "aviso": aviso, "tirado": fora}


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
    # O editor aberto ao lado de uma conversa: o pedido e o que foi feito
    # ficam nela, como qualquer outra coisa dita ali.
    trabalho_id: str = ""


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
def documentos_criar(payload: NovoDocumento, request: Request = None) -> dict:
    corpo = payload.corpo
    if not corpo and payload.tipo == "planilha":
        corpo = planilha.para_json([planilha.Aba()])
    id_ = estado.documentos.criar(payload.titulo, payload.tipo, corpo, payload.cadastro_id)
    equipe.marcar_autor(estado.base, "documentos", id_, equipe.quem(request, estado.prefs.dados))
    return estado.documentos.obter(id_) or {}


class ImportarParaEditar(BaseModel):
    caminho: str = ""
    nome: str = ""
    # Vindo de uma conversa: o rascunho fica ligado a ela, e abrir para
    # editar de novo volta ao mesmo rascunho em vez de criar outra copia.
    trabalho_id: str = ""


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

    trabalho = estado.trabalhos.obter(payload.trabalho_id) if payload.trabalho_id else None
    if trabalho:
        for m in reversed(trabalho.mensagens):
            feito = m.feito or {}
            if feito.get("tipo") == "editar" and feito.get("nome") == lido.name:
                rascunho = estado.documentos.obter(int(feito.get("id") or 0))
                if rascunho:
                    return {"id": rascunho["id"], "titulo": rascunho["titulo"], "de": lido.name,
                            "paragrafos": 0, "reaberto": True, "tipo": rascunho.get("tipo", "texto")}

    # A planilha do Excel vira planilha do editor (pacote de telas, `Conversa
    # - Editor de planilha`): as abas, as formulas (traduzidas para o padrao
    # brasileiro), o formato e o negrito. O .xlsx de origem nao e tocado.
    if alvo.suffix.lower() == ".xlsx":
        try:
            abas = planilha.de_xlsx(alvo.read_bytes())
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"não consegui ler a planilha: {exc}") from exc
        id_ = estado.documentos.criar(Path(lido.name).stem, "planilha", planilha.para_json(abas), None)
        if trabalho:
            trabalho.dizer("paulus", f"Abri “{lido.name}” para editar.",
                           feito={"tipo": "editar", "id": id_, "nome": lido.name, "onde": "planilha"})
            estado.trabalhos.salvar(trabalho)
        return {"id": id_, "titulo": Path(lido.name).stem, "de": lido.name, "paragrafos": 0,
                "reaberto": False, "tipo": "planilha"}

    # Paragrafo por paragrafo: o texto extraido vem com quebras de linha, e
    # jogar tudo num <p> so daria um bloco unico impossivel de editar.
    paragrafos = [p.strip() for p in lido.text.splitlines() if p.strip()]
    corpo = "".join(f"<p>{_escapar(p)}</p>" for p in paragrafos) or "<p><br></p>"

    id_ = estado.documentos.criar(Path(lido.name).stem, "texto", corpo, None)
    if trabalho:
        trabalho.dizer("paulus", f"Abri “{lido.name}” para editar.",
                       feito={"tipo": "editar", "id": id_, "nome": lido.name, "onde": "editor"})
        estado.trabalhos.salvar(trabalho)
    return {"id": id_, "titulo": Path(lido.name).stem, "de": lido.name,
            "paragrafos": len(paragrafos), "reaberto": False, "tipo": "texto"}


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
            blocos, timbre=_timbre_do_documento(item.get("formato")), formato=item.get("formato"))
        item["formato"] = documento.normalizar_formato(item.get("formato"))
        item["folha"] = _folha_para_tela(item)
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
    d = estado.base.um("SELECT titulo, tipo FROM documentos WHERE id = ?", (id_,))
    if not d:
        raise HTTPException(status_code=404, detail="documento não encontrado")
    entrada = estado.lixeira.apagar_linha("documento", id_, d["titulo"], "Documentos · " + ("planilha" if d["tipo"] == "planilha" else "texto"))
    return _foi_para_lixeira(entrada, "apagado", id_)


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


@app.post("/api/documentos/{id_}/notas")
def documentos_notas(id_: int, payload: dict) -> dict:
    """
    As notas de margem deste documento, presas ao paragrafo de cada uma.

    Duas origens, e a tela diz qual e qual:

      - regra: o que `conferir` acha, instantaneo e sempre igual
      - assistente: o que o modelo comentou quando pediram

    A da regra nao precisa de modelo nem de rede, e por isso aparece sempre. A
    do modelo so existe onde alguem pediu.
    """
    item = _documento_ou_404(id_)
    if item["tipo"] != "texto":
        raise HTTPException(status_code=400, detail="isso é uma planilha")

    corpo = payload.get("corpo")
    blocos = documento.ler_html(item["corpo"] if corpo is None else corpo)

    notas = []
    for aviso in documento.conferir(blocos, estado.cadastros.listar()):
        notas.append({
            "id": 0,
            "origem": "regra",
            "grau": aviso["grau"],
            "bloco": aviso["bloco"] - 1,     # a tela conta de zero
            "titulo": aviso["titulo"],
            "texto": aviso["detalhe"],
        })
    for c in estado.comentarios.ancorar(id_, blocos):
        notas.append({
            "id": c["id"],
            "origem": c["origem"],
            "grau": "comentario",
            "bloco": c["bloco"],
            "titulo": "Comentário",
            "texto": c["texto"],
            "trecho": c["trecho"],
            "criado_em": c["criado_em"],
        })

    return {"notas": notas, "blocos": len(blocos)}


@app.post("/api/documentos/{id_}/comentar")
def documentos_comentar(id_: int, payload: dict) -> dict:
    """
    O assistente comentando um trecho - sem reescrever nada.

    E diferente de pedir uma alteracao: aqui a resposta e uma observacao para
    quem le decidir, e nao um texto para entrar no contrato. O trecho vai junto
    porque comentario sobre "o documento" nao gruda em lugar nenhum.
    """
    item = _documento_ou_404(id_)
    trecho = str(payload.get("trecho", "")).strip()
    if not trecho:
        raise HTTPException(
            status_code=400,
            detail="selecione no texto o trecho que você quer que eu comente")

    disponivel, motivo = check_ollama(estado.client.model)
    if not disponivel:
        raise HTTPException(status_code=503, detail=motivo)

    pedido = (
        "Escreva UMA observacao curta sobre o trecho abaixo, para quem vai "
        "revisar o contrato. Diga o que falta, o que esta ambiguo ou o que "
        "merece conferencia. Nao reescreva o trecho e nao proponha texto novo. "
        "No maximo tres frases."
    )
    try:
        resposta = estado.cliente_para("redacao").ask(pedido, f"Trecho do contrato:\n{trecho[:2000]}",
                                     sistema=SISTEMA_COMENTARIO)
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    texto = _limpar_sugestao(resposta)
    if not texto:
        raise HTTPException(status_code=422, detail="o modelo não devolveu observação nenhuma")

    novo = estado.comentarios.criar(id_, trecho, texto, origem="assistente")
    return {"id": novo, "texto": texto, "trecho": trecho[:600],
            "aviso": ("Escrito por um modelo pequeno rodando nesta máquina. "
                      "É observação para conferir, não parecer.")}


@app.post("/api/documentos/{id_}/comentarios")
def comentarios_criar(id_: int, payload: dict) -> dict:
    """Um comentario escrito pela propria pessoa, preso a um trecho."""
    _documento_ou_404(id_)
    try:
        novo = estado.comentarios.criar(
            id_, payload.get("trecho", ""), payload.get("texto", ""), origem="pessoa")
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro))
    return {"id": novo}


@app.post("/api/documentos/{id_}/comentarios/{comentario_id}/resolver")
def comentarios_resolver(id_: int, comentario_id: int, payload: dict) -> dict:
    _documento_ou_404(id_)
    achou = estado.comentarios.resolver(comentario_id, bool(payload.get("resolvido", True)))
    if not achou:
        raise HTTPException(status_code=404, detail="comentário não encontrado")
    return {"ok": True}


@app.delete("/api/documentos/{id_}/comentarios/{comentario_id}")
def comentarios_apagar(id_: int, comentario_id: int) -> dict:
    _documento_ou_404(id_)
    if not estado.comentarios.apagar(comentario_id):
        raise HTTPException(status_code=404, detail="comentário não encontrado")
    return {"ok": True}


@app.post("/api/documentos/{id_}/alteracoes")
def documentos_alteracoes(id_: int, payload: dict) -> dict:
    """
    O que mudou no texto que esta no editor agora, em relacao a uma versao.

    Controlar alteracoes no Word marca cada tecla enquanto se digita. Aqui a
    marca vem da comparacao com uma versao gravada, e nao de interceptar a
    digitacao - porque interceptar tecla dentro de um campo editavel e o
    caminho curto para perder texto de contrato, e texto de contrato perdido
    nao tem conserto do lado de ca.

    O resultado e o mesmo que interessa: o que entrou, o que saiu, o que mudou,
    e o caminho de volta para cada um.
    """
    item = _documento_ou_404(id_)
    if item["tipo"] != "texto":
        raise HTTPException(status_code=400, detail="isso é uma planilha")

    ultima = estado.documentos.ultima_versao(id_)
    desde = int(payload.get("desde") or ultima)
    antes = estado.documentos.corpo_da_versao(id_, desde)
    if antes is None:
        raise HTTPException(status_code=404, detail="essa versão não existe")

    corpo = payload.get("corpo")
    depois = item["corpo"] if corpo is None else corpo
    return {
        "desde": desde,
        "ultima": ultima,
        "mudancas": documento.comparar(antes, depois),
    }


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
    if not estado.prefs.dados.get("timbre_no_pdf"):
        return {}
    return _dados_do_escritorio()


def _dados_do_escritorio() -> dict:
    """O timbre montado dos dados profissionais, com a chave ligada ou nao."""
    pessoa = estado.prefs.dados.get("pessoa", {})
    # Sem nome nao ha timbre: o resto sozinho sairia como um endereco solto no
    # alto da folha. Quem ligou a chave precisa saber disso na tela de
    # Configuracoes, e nao ao abrir o PDF e nao ver nada.
    if not str(pessoa.get("nome", "")).strip():
        return {}
    logo = estado.marca.caminho("logo")
    return {
        "nome": pessoa.get("nome", ""),
        "oab": pessoa.get("oab", ""),
        "cpf": pessoa.get("cpf", ""),
        "endereco": pessoa.get("endereco", ""),
        "telefone": pessoa.get("telefone", ""),
        "email": pessoa.get("email", ""),
        # A logo do escritorio vai no alto do papel, acima do nome. Quando nao
        # ha logo, o timbre continua sendo so o texto, como antes.
        "logo": str(logo) if logo else "",
    }


def _timbre_do_documento(formato) -> dict | None:
    """
    O cabecalho que ESTE documento leva, pela folha dele: o timbre de
    Configuracoes (quando a chave esta ligada, ou sempre), o que a pessoa
    escreveu, ou nenhum.
    """
    folha = documento.normalizar_formato(formato)["folha"]
    modo = folha["cabecalho"]
    if modo == "nenhum":
        return None
    if modo == "padrao":
        base = _timbre_do_escritorio()
    elif modo == "escritorio":
        base = _dados_do_escritorio()
    else:
        logo = estado.marca.caminho("logo")
        base = {"linhas": folha["linhas"], "logo": str(logo) if logo else ""}
    if not base:
        return None
    if not folha["logo"]:
        base = {**base, "logo": ""}
    return base


def _folha_para_tela(item: dict) -> dict:
    """A folha do documento e o desenho dela, para o editor e o modo Folha."""
    formato = documento.normalizar_formato(item.get("formato"))
    escritorio = _dados_do_escritorio()
    return {
        **formato["folha"],
        "desenho": documento.desenho_da_folha(
            _timbre_do_documento(formato), formato, item.get("titulo", "")),
        "escritorio": {
            "linhas": documento._linhas_do_timbre(escritorio) if escritorio else [],
            "logo": bool(estado.marca.caminho("logo")),
            "timbre_ligado": bool(estado.prefs.dados.get("timbre_no_pdf")),
        },
    }


def _pdf_do_documento(item: dict, timbre: dict | None = None) -> bytes:
    blocos = documento.ler_html(item["corpo"])
    formato = documento.normalizar_formato(item.get("formato"))
    rodape = documento.texto_do_rodape(formato["folha"], item["titulo"])
    if timbre is None:
        timbre = _timbre_do_documento(formato)
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


@app.get("/api/impressoras")
def impressoras_listar() -> dict:
    """As impressoras desta conta do Windows, para o dialogo de imprimir."""
    import impressao

    try:
        lista = impressao.listar()
    except Exception as exc:  # driver quebrado nao pode derrubar a tela
        return {"disponivel": impressao.disponivel(), "impressoras": [], "erro": str(exc)}
    return {"disponivel": impressao.disponivel(), "impressoras": lista}


@app.post("/api/documentos/{id_}/imprimir")
def documentos_imprimir(id_: int, payload: dict) -> dict:
    """O documento direto na impressora escolhida, sem o dialogo do navegador."""
    import impressao

    item = _documento_ou_404(id_)
    if item["tipo"] != "texto":
        raise HTTPException(status_code=400, detail="isso é uma planilha - baixe em XLSX para imprimir")
    try:
        return impressao.imprimir(
            _pdf_do_documento(item), str(payload.get("impressora", "")), item["titulo"],
            paginas=str(payload.get("paginas", "todas")), copias=int(payload.get("copias", 1) or 1),
            cor=bool(payload.get("cor", True)), frente_verso=bool(payload.get("frente_verso", False)))
    except impressao.ErroDeImpressao as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="não entendi o pedido de impressão") from exc


class PdfProtegido(BaseModel):
    senha: str = ""


@app.post("/api/documentos/{id_}/pdf")
def documentos_pdf_com_senha(id_: int, payload: PdfProtegido):
    """
    O mesmo PDF, pedindo senha para abrir.

    E POST, e nao um `?senha=` no endereco, de proposito: endereco fica no
    historico do navegador e no registro do servidor, e uma senha nao tem por
    que morar em nenhum dos dois.
    """
    from fastapi.responses import Response

    item = _documento_ou_404(id_)
    if item["tipo"] != "texto":
        raise HTTPException(status_code=400, detail="isso é uma planilha - baixe em XLSX ou CSV")
    try:
        dados = documento.proteger_com_senha(_pdf_do_documento(item), payload.senha)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(dados, media_type="application/pdf",
                    headers=_anexo(_arquivo(item["titulo"]) + ".pdf"))


def _docx_com_pavlvs(dados: bytes) -> bytes:
    """
    W1: o .docx que o PAULUS gera leva o PAVLVS (src/word_instalar.py) quando
    ele está ligado e instalado - no Word 2021 a aba só aparece no documento
    que traz o suplemento, e o Word o mantém quando a pessoa salva.
    """
    instalacao = getattr(estado, "word_instalacao", None)
    return instalacao.no_documento(dados) if instalacao is not None else dados


@app.post("/api/word/abrir-documento/{id_}")
def word_abrir_documento(id_: int, request: Request) -> dict:
    """
    "Abrir no Word", no Editor: o .docx com o PAVLVS vai para o Acervo (o
    mesmo arquivo do "guardar", que nunca passa por cima do que alguém mudou
    por fora) e abre no Word.
    """
    rotas_do_acesso.so_local(request)
    instalacao = estado.word_instalacao
    if not instalacao.instalado():
        raise HTTPException(status_code=409, detail="ative o PAVLVS no Word primeiro (Configurações › Word)")
    item = _documento_ou_404(id_)
    if item["tipo"] != "texto":
        raise HTTPException(status_code=400, detail="só documento de texto abre no Word")
    if instalacao.precisa_fechar_o_word():
        return {"aberto": False, "precisa_fechar": True}
    dados = _docx_com_pavlvs(documento.para_docx(documento.ler_html(item["corpo"]), item["titulo"],
                                                 formato=item.get("formato")))
    try:
        destino = _arquivo_do_editor_no_acervo(id_, item["titulo"], ".docx", dados)
    except OSError:
        # Aberto no Word (arquivo preso): abre o que já está lá.
        mapa = json.loads(EDITOR_NO_ACERVO_PATH.read_text(encoding="utf-8")) if EDITOR_NO_ACERVO_PATH.exists() else {}
        caminho = (mapa.get(f"{id_}:.docx") or {}).get("caminho")
        if not caminho:
            raise HTTPException(status_code=409, detail="o arquivo está preso por outro programa") from None
        destino = Path(caminho)
    estado.recarregar()
    try:
        estado.word_abrir_no_windows(destino)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"não consegui abrir o Word: {exc}") from exc
    return {"aberto": True, "precisa_fechar": False, "caminho": str(destino)}


@app.get("/api/documentos/{id_}/docx")
def documentos_docx(id_: int):
    from fastapi.responses import Response

    item = _documento_ou_404(id_)
    if item["tipo"] != "texto":
        raise HTTPException(status_code=400, detail="isso é uma planilha - baixe em XLSX ou CSV")

    dados = _docx_com_pavlvs(documento.para_docx(documento.ler_html(item["corpo"]), item["titulo"],
                                                 formato=item.get("formato")))
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
    # Com `formato`, mede uma folha proposta sem gravar nada.
    formato = item.get("formato")
    if isinstance(payload.get("formato"), dict):
        pedido = payload["formato"]
        if "folha" not in pedido:
            pedido = {**pedido, "folha": documento.normalizar_formato(formato)["folha"]}
        formato = documento.normalizar_formato(pedido)
    mapa = documento.mapa_de_paginas(
        blocos, timbre=_timbre_do_documento(formato), formato=formato)

    return {**mapa, "blocos": len(blocos), "formato": documento.normalizar_formato(formato),
            "folha": _folha_para_tela({**item, "formato": formato})}


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
        blocos, timbre=_timbre_do_documento(formato), formato=formato)
    return {**mapa, "blocos": len(blocos), "formato": formato,
            "folha": _folha_para_tela({**item, "formato": formato})}


@app.post("/api/documentos/{id_}/folha/sugerir")
def documentos_folha_sugerir(id_: int, payload: dict) -> dict:
    """
    O papel timbrado que o pedido descreve ("cabecalho com meu nome e OAB,
    pagina 1 de 3 no rodape"). Devolve a proposta sem gravar.
    """
    item = _documento_ou_404(id_)
    pedido = str(payload.get("pedido", "")).strip()[:600]
    if not pedido:
        raise HTTPException(status_code=400, detail="diga como quer a folha")
    atual = payload.get("folha") or documento.normalizar_formato(item.get("formato"))["folha"]
    escritorio = _dados_do_escritorio()
    linhas = documento._linhas_do_timbre(escritorio) if escritorio else []
    return documento.sugerir_folha(
        pedido, atual, linhas, item.get("titulo", ""),
        lambda instrucao, sistema, esquema: estado.cliente_para("leitura").ask_json(
            instrucao, schema_hint=esquema, sistema=sistema))


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
    Grava o documento no Acervo (pasta Editor), para poder assinar e anexar em
    e-mail. Um arquivo por documento, atualizado no lugar - nunca por cima de
    arquivo que alguem mudou por fora (_arquivo_do_editor_no_acervo).
    """
    item = _documento_ou_404(id_)
    formato = str((payload or {}).get("formato", "pdf")).lower()
    senha = str((payload or {}).get("senha", ""))

    if item["tipo"] == "planilha":
        abas = planilha.de_dict(json.loads(item["corpo"] or "{}"))
        dados = planilha.para_xlsx(abas, [planilha.calcular_aba(a) for a in abas])
        sufixo = ".xlsx"
    elif formato == "docx":
        dados = _docx_com_pavlvs(documento.para_docx(documento.ler_html(item["corpo"]), item["titulo"]))
        sufixo = ".docx"
    else:
        dados = _pdf_do_documento(item)
        # Com senha, o arquivo que vai para a biblioteca (e dali para o anexo
        # do e-mail) ja sai protegido: proteger so o download deixaria passar
        # justamente o caminho que sai desta maquina.
        if senha:
            try:
                dados = documento.proteger_com_senha(dados, senha)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        sufixo = ".pdf"

    # Guardar pedido pela pessoa pergunta quando ha outro arquivo com o nome;
    # o guardar automatico (ao fechar a pre-visualizacao) nao abre pergunta.
    escolhas = None if (payload or {}).get("automatico") else nomes_mod.do_pedido(payload or {})
    destino = _arquivo_do_editor_no_acervo(id_, item["titulo"], sufixo, dados, protegido=bool(senha), escolhas=escolhas)
    return {
        "guardado": destino.name,
        "caminho": str(destino),
        "documentos": estado.recarregar(),
    }


EDITOR_NO_ACERVO_PATH = DADOS_DIR / "editor_no_acervo.json"


def _arquivo_do_editor_no_acervo(id_: int, titulo: str, sufixo: str, dados: bytes, protegido: bool = False,
                                 escolhas: dict | None = None) -> Path:
    """
    Um arquivo por documento do editor (e por formato) no Acervo, atualizado
    no lugar.

    Antes, cada "guardar" - e o guardar automatico ao fechar a pre-visualizacao
    - criava mais uma copia: "Contrato.pdf", "Contrato (2).pdf", "(3)"... O
    PAULUS lembra qual arquivo e de qual documento, e o sha1 do que escreveu
    la. So passa por cima quando o arquivo ainda e exatamente o que ele
    escreveu: mudado por fora (alguem editou, assinou por outro programa),
    fica, e o novo sai com outro nome. O titulo mudou: o arquivo antigo, se
    ainda e o que o PAULUS escreveu, da lugar ao de nome novo.

    Com `escolhas` (o guardar que a pessoa pediu), o arquivo de outro com o
    mesmo nome nao vira " (2)" sozinho: a tela pergunta (src/nomes.py). Sem
    `escolhas` (o guardar automatico), o " (n)" de sempre.
    """
    from extract import file_sha1

    try:
        mapa = json.loads(EDITOR_NO_ACERVO_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        mapa = {}
    chave = f"{id_}:{sufixo}{':senha' if protegido else ''}"
    pasta = _pasta_no_acervo("Editor")
    base = _arquivo(titulo) + (" - com senha" if protegido else "")
    desejado = pasta / f"{base}{sufixo}"
    antigo = mapa.get(chave) or {}
    antigo_caminho = Path(antigo["caminho"]) if antigo.get("caminho") else None
    nosso = bool(antigo_caminho and antigo_caminho.exists() and file_sha1(antigo_caminho) == antigo.get("sha1"))

    if nosso and antigo_caminho == desejado:
        destino = desejado
    elif escolhas is not None:
        # Decidir o nome antes de apagar qualquer coisa: com conflito sem
        # decisao, nada muda no disco.
        pendentes: list[dict] = []
        destino = nomes_mod.destino(pasta, desejado.name, escolhas, pendentes)
        nomes_mod.conferir(pendentes)
        if nosso and antigo_caminho != destino:
            antigo_caminho.unlink()  # o titulo mudou; o arquivo antigo era so nosso
    else:
        if nosso and antigo_caminho != desejado:
            antigo_caminho.unlink()  # o titulo mudou; o arquivo antigo era so nosso
        destino = desejado
        conta = 2
        while destino.exists():
            destino = pasta / f"{base} ({conta}){sufixo}"
            conta += 1
    destino.write_bytes(dados)
    mapa[chave] = {"caminho": str(destino), "sha1": file_sha1(destino)}
    EDITOR_NO_ACERVO_PATH.parent.mkdir(parents=True, exist_ok=True)
    EDITOR_NO_ACERVO_PATH.write_text(json.dumps(mapa, ensure_ascii=False, indent=1), encoding="utf-8")
    return destino


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

# A instrucao de SISTEMA do editor. Sem ela valia a do acervo, que manda citar
# o nome do arquivo de onde a informacao saiu - e o modelo obedecia as duas
# ordens ao mesmo tempo: devolvia o texto pedido com "Arquivo: contrato.txt" na
# frente, com o nome do arquivo inventado.
SISTEMA_EDITOR = """Voce e o PAULUS, ajudando a redigir um documento juridico
brasileiro. Voce nao esta consultando arquivos: o que vem abaixo e o texto em
que se esta trabalhando agora.

Nunca cite nome de arquivo, nunca escreva cabecalho como "Arquivo:" ou
"Documento:", nunca repita o pedido antes de responder.

Nunca invente artigo de lei, sumula, processo, nome, data, valor ou prazo.

Voce NAO conhece a tela deste programa. Nunca diga onde clicar, nunca cite
botao, menu ou atalho."""

SISTEMA_COMENTARIO = SISTEMA_EDITOR + """

Aqui voce NAO reescreve nada: voce comenta. A resposta e uma observacao curta
para quem vai revisar decidir - o que falta, o que esta ambiguo, o que merece
conferencia. Nao proponha texto novo e nao repita o trecho."""


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
    instrucao = INSTRUCAO_EDITOR + f"\n\nPedido: {pedido}"

    # Vindo de uma conversa, o pedido e trabalho dela como qualquer pergunta:
    # a conversa fica "trabalhando" com as etapas a vista, o cartao
    # "Acontecendo agora" da tela inicial mostra o andamento - com barra, quando
    # esta maquina ja mediu quanto le e escreve -, e o botao de parar alcanca.
    trabalho = estado.trabalhos.obter(payload.trabalho_id) if payload.trabalho_id else None
    parar = threading.Event()
    if trabalho:
        agora = time.time()
        trabalho.dizer("pessoa", pedido)
        trabalho.etapas = [Etapa("Entender o pedido", estado=CONCLUIDO),
                           Etapa(f"Escrever em “{item['titulo']}”", estado=EXECUTANDO)]
        trabalho.estado = EXECUTANDO
        estado.trabalhos.salvar(trabalho)
        estado.respondendo[trabalho.id] = parar
        estado.andamento[trabalho.id] = {
            "fase": "documento", "inicio": agora, "desde": agora,
            "previsao_s": _previsao_de_escrita(len(instrucao) + len(contexto)),
            "palavras": 0, "documentos": 1, "caracteres": len(contexto),
        }

    def terminar(etapa: str, texto: str, **extras) -> None:
        if not trabalho:
            return
        estado.andamento.pop(trabalho.id, None)
        estado.respondendo.pop(trabalho.id, None)
        trabalho.etapas[-1].estado = etapa
        trabalho.estado = CONCLUIDO if etapa == CONCLUIDO else (PAUSADO if etapa == PAUSADO else "falhou")
        trabalho.dizer("paulus", texto, **extras)
        estado.trabalhos.salvar(trabalho)

    try:
        # No editor entram so as regras de redacao: como o escritorio escreve
        # muda o texto sugerido; o nome de um cliente nao tem o que fazer aqui.
        resposta = estado.cliente_para("redacao").ask(instrucao, contexto,
                                     sistema=SISTEMA_EDITOR,
                                     ensinado=estado.contextos.bloco(["Regras de redação"]),
                                     parar=parar.is_set)
    except OllamaError as exc:
        terminar("falhou", f"Não consegui escrever em “{item['titulo']}”: {exc}")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception:
        terminar("falhou", f"Não consegui escrever em “{item['titulo']}”.")
        raise

    if parar.is_set():
        terminar(PAUSADO, f"Parei antes de escrever em “{item['titulo']}”. O documento ficou como estava.")
        raise HTTPException(status_code=409, detail="parei antes de terminar a alteração")

    sugestao = _limpar_sugestao(resposta)
    inteiro = documento.para_texto(documento.ler_html(item["corpo"]))
    if _e_o_documento_de_volta(sugestao, inteiro):
        detalhe = ("o modelo devolveu o documento de volta em vez da alteração. "
                   "Selecione no texto o trecho que você quer mudar e peça de "
                   "novo — com o trecho à mão ele acerta.")
        terminar("falhou", "Não consegui: " + detalhe)
        raise HTTPException(status_code=422, detail=detalhe)

    onde = "o trecho selecionado" if payload.trecho.strip() else "o fim do documento"
    terminar(CONCLUIDO, f"Escrevi em “{item['titulo']}” ({onde}). A alteração ficou marcada "
                        "no documento, esperando você manter ou descartar.",
             feito={"tipo": "alteracao", "id": id_, "nome": item["titulo"], "onde": "editor"})
    avisos.avisar("resposta", "Alteração pronta · " + item["titulo"][:60],
                  f"Escrevi em {onde}. Está marcada no documento, esperando você manter ou descartar.")

    return {
        "sugestao": sugestao,
        "sobre": payload.trecho[:160],
        "aviso": (
            "Escrito por um modelo pequeno rodando nesta máquina. Confira nomes, "
            "datas, valores e qualquer artigo de lei antes de aceitar."
        ),
    }


def _previsao_de_escrita(caracteres: int) -> float:
    """
    Quanto uma alteracao no documento deve levar nesta maquina: ler o pedido
    e o trecho, e escrever uns 120 palavras. Zero quando nao ha medida - a
    tela mostra a barra so com numero de verdade atras.
    """
    leitura = estado.ritmo.previsao_de_leitura(estado.client.model, caracteres)
    if not leitura.get("sabe"):
        return 0
    por_segundo = estado.ritmo.palavras_por_segundo(estado.client.model)
    return round(leitura["segundos"] + (120 / por_segundo if por_segundo else 0), 1)


def _limpar_sugestao(texto: str) -> str:
    limpo = (texto or "").strip()
    limpo = re.sub(r"\*\*(.+?)\*\*", r"\1", limpo)
    limpo = re.sub(r"^\s*[*-]\s+", "", limpo, flags=re.M)
    limpo = re.sub(r"^\s*(sugest[aã]o|resposta|texto)\s*:\s*", "", limpo, flags=re.I)
    # "[Texto do documento]", "[Documento]": rotulo que o modelo copia do
    # cabecalho do contexto e entrega como se fosse parte do texto.
    limpo = re.sub(r"^\s*\[[^\]]{0,40}\]\s*", "", limpo)
    # "Arquivo: contrato.txt" na primeira linha: o modelo obedecendo a ordem de
    # citar a origem, com um nome de arquivo que ele mesmo inventou. A ordem ja
    # saiu do prompt do editor, mas o rotulo ainda escapa de vez em quando.
    limpo = re.sub(r"^\s*(arquivo|documento|origem|fonte)\s*:[^\n]{0,80}\n+", "",
                   limpo, flags=re.I)
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
        # Ate onde a grade cresce quando a pessoa rola.
        "limites": {"linhas": planilha.MAX_LINHAS, "colunas": planilha.MAX_COLUNAS},
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

    dados = {c: payload[c] for c in ("formato", "negrito", "italico", "borda", "valor", "fundo")
             if c in payload}
    if not dados:
        raise HTTPException(status_code=400, detail="nada para aplicar")

    for ref in refs:
        abas[indice].gravar(ref, dados)

    estado.documentos.salvar(
        id_, planilha.para_json(abas),
        nota=f"{str(payload.get('faixa', '')).upper()}: {', '.join(dados)}")
    return _resposta_planilha(id_, estado.documentos.obter(id_), abas)


@app.post("/api/planilha/{id_}/grafico")
def planilha_grafico(id_: int, payload: dict) -> dict:
    """
    A selecao virando serie para desenhar.

    Quem escolhe qual coluna e valor e qual e rotulo e a propria selecao: a
    ultima coluna com numero e o valor, a coluna de texto a esquerda sao os
    rotulos. Pedir isso num formulario antes de ver o desenho seria trocar um
    grafico por um questionario.
    """
    item = _documento_ou_404(id_)
    abas = _abas_do(item)
    indice = int(payload.get("aba", 0))
    if not 0 <= indice < len(abas):
        raise HTTPException(status_code=400, detail="aba não encontrada")

    aba = abas[indice]
    return planilha.serie_da_faixa(aba, planilha.calcular_aba(aba), payload.get("faixa", ""))


def _aba_do_pedido(item: dict, payload: dict) -> tuple[list, int]:
    abas = _abas_do(item)
    try:
        indice = int(payload.get("aba", 0))
    except (TypeError, ValueError):
        indice = -1
    if not 0 <= indice < len(abas):
        raise HTTPException(status_code=400, detail="aba não encontrada")
    return abas, indice


@app.post("/api/planilha/{id_}/lote")
def planilha_lote(id_: int, payload: dict) -> dict:
    """
    Varias celulas numa chamada so: colar, preencher com a alca, limpar,
    recortar. Uma versao no Historico para a operacao inteira - que e o que a
    pessoa fez: "colei a tabela", e nao "mudei 200 celulas".
    """
    item = _documento_ou_404(id_)
    if item["tipo"] != "planilha":
        raise HTTPException(status_code=400, detail="isso não é uma planilha")
    abas, indice = _aba_do_pedido(item, payload)
    itens = payload.get("itens")
    if not isinstance(itens, list) or not itens:
        raise HTTPException(status_code=400, detail="nada para gravar")
    if len(itens) > planilha.MAX_LINHAS * 10:
        raise HTTPException(status_code=400, detail="seleção grande demais")

    feitas = planilha.gravar_lote(abas[indice], itens)
    nota = " ".join(str(payload.get("nota") or "").split())[:80] or "células alteradas"
    estado.documentos.salvar(id_, planilha.para_json(abas), nota=nota)
    return {**_resposta_planilha(id_, estado.documentos.obter(id_), abas), "feitas": feitas}


@app.post("/api/planilha/{id_}/estrutura")
def planilha_estrutura(id_: int, payload: dict) -> dict:
    """
    Inserir ou excluir linhas e colunas, com as formulas seguindo as celulas.

    `em` e o numero da linha (1, 2, ...) ou a letra/indice da coluna.
    """
    item = _documento_ou_404(id_)
    abas, indice = _aba_do_pedido(item, payload)
    eixo = str(payload.get("eixo", ""))
    em = payload.get("em", 1)
    if eixo == "colunas" and isinstance(em, str) and not em.strip().isdigit():
        em = planilha.indice_da_coluna(em.strip())
    try:
        feito = planilha.reestruturar(abas[indice], eixo, str(payload.get("acao", "")),
                                      int(em), int(payload.get("quantas", 1) or 1))
    except (TypeError, ValueError) as erro:
        raise HTTPException(status_code=400, detail=str(erro))

    if eixo == "linhas":
        onde = f"linha {feito['em']}" if feito["quantas"] == 1 else f"linhas {feito['em']}-{feito['em'] + feito['quantas'] - 1}"
    else:
        letra = planilha.letra_da_coluna(feito["em"])
        onde = f"coluna {letra}" if feito["quantas"] == 1 else (
            f"colunas {letra}-{planilha.letra_da_coluna(feito['em'] + feito['quantas'] - 1)}")
    estado.documentos.salvar(
        id_, planilha.para_json(abas),
        nota=("inseriu " if feito["acao"] == "inserir" else "excluiu ") + onde)
    return {**_resposta_planilha(id_, estado.documentos.obter(id_), abas), "feito": feito}


@app.post("/api/planilha/{id_}/layout")
def planilha_layout(id_: int, payload: dict) -> dict:
    """
    Largura de coluna, altura de linha e o que esta oculto.

    {"larguras": {"B": 180, "C": null}, "alturas": {"3": 40},
     "ocultar": {"colunas": ["D"], "linhas": [7]}, "reexibir": {...}}
    null volta a medida ao padrao.
    """
    item = _documento_ou_404(id_)
    abas, indice = _aba_do_pedido(item, payload)
    aba = abas[indice]
    larguras = payload.get("larguras") or {}
    alturas = payload.get("alturas") or {}
    ocultar = payload.get("ocultar") or {}
    reexibir = payload.get("reexibir") or {}
    if not all(isinstance(x, dict) for x in (larguras, alturas, ocultar, reexibir)):
        raise HTTPException(status_code=400, detail="formato inválido")
    try:
        aba.medir(larguras, alturas)
        aba.ocultar(ocultar.get("colunas") or [], ocultar.get("linhas") or [], True)
        aba.ocultar(reexibir.get("colunas") or [], reexibir.get("linhas") or [], False)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="medida inválida")

    partes = []
    if larguras:
        partes.append("largura de " + ", ".join(sorted(str(k).upper() for k in larguras)))
    if alturas:
        partes.append("altura da linha " + ", ".join(sorted((str(k) for k in alturas), key=lambda x: int(x) if x.isdigit() else 0)))
    if ocultar:
        partes.append("ocultou")
    if reexibir:
        partes.append("reexibiu")
    estado.documentos.salvar(id_, planilha.para_json(abas), nota=("; ".join(partes) or "layout")[:80])
    return _resposta_planilha(id_, estado.documentos.obter(id_), abas)


@app.post("/api/planilha/{id_}/mesclar")
def planilha_mesclar(id_: int, payload: dict) -> dict:
    """
    Junta as celulas de uma faixa numa so, ou desfaz a juncao.

    Nao cobre celula com conteudo. O Excel junta e joga fora o que estava
    debaixo, avisando numa caixa que todo mundo clica em OK sem ler - e ali
    some um valor que ninguem mais procura.
    """
    item = _documento_ou_404(id_)
    abas = _abas_do(item)
    indice = int(payload.get("aba", 0))
    if not 0 <= indice < len(abas):
        raise HTTPException(status_code=400, detail="aba não encontrada")

    faixa = payload.get("faixa", "")
    try:
        feito = (planilha.separar(abas[indice], faixa) if payload.get("separar")
                 else planilha.mesclar(abas[indice], faixa))
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro))

    estado.documentos.salvar(
        id_, planilha.para_json(abas),
        nota=("separou " if payload.get("separar") else "juntou ") + str(faixa).upper())
    return {**_resposta_planilha(id_, estado.documentos.obter(id_), abas), "feito": feito}


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


class TrazerParaPlanilha(BaseModel):
    de: str = ""          # "financeiro" ou "prazos"
    mes: str = ""         # AAAA-MM; vazio traz tudo o que existe
    categoria: str = "honorarios"


@app.post("/api/planilha/{id_}/trazer")
def planilha_trazer(id_: int, payload: TrazerParaPlanilha) -> dict:
    """
    Uma aba nova com o que ja esta no programa: honorarios ou prazos.

    O painel da planilha oferecia as duas coisas e as duas diziam "em breve".
    Sao dados que o programa ja tem - o que faltava era escreve-los em linhas
    e colunas. Vem sempre numa ABA NOVA, nunca por cima do que a pessoa
    escreveu: uma importacao que apaga trabalho alheio nao se desfaz.

    O que entra e valor, nao formula: a planilha e uma fotografia do dia em
    que foi feita, e o total e que e formula, para continuar certo se alguem
    corrigir uma linha.
    """
    item = _documento_ou_404(id_)
    if item["tipo"] != "planilha":
        raise HTTPException(status_code=400, detail="isso é um documento de texto")
    abas = _abas_do(item)
    if len(abas) >= 6:
        raise HTTPException(status_code=400, detail="seis abas é o limite por planilha")

    if payload.de == "financeiro":
        aba, quantos = _aba_do_financeiro(payload.mes, payload.categoria)
    elif payload.de == "prazos":
        aba, quantos = _aba_dos_prazos()
    else:
        raise HTTPException(status_code=400, detail="não sei trazer isso")

    if not quantos:
        raise HTTPException(
            status_code=404,
            detail=("não achei honorários lançados nesse período" if payload.de == "financeiro"
                    else "não há prazos lidos nos documentos do Acervo"))

    abas.append(aba)
    estado.documentos.salvar(id_, planilha.para_json(abas), nota=f"aba {aba.nome} criada")
    return {**_resposta_planilha(id_, estado.documentos.obter(id_), abas),
            "aba_nova": len(abas) - 1, "quantos": quantos,
            "aviso": f"{_quantos(quantos, 'linha')} na aba “{aba.nome}”"}


def _cabecalho_da_aba(aba, titulos: list[str]) -> None:
    for coluna, titulo in enumerate(titulos):
        aba.gravar(f"{planilha.letra_da_coluna(coluna)}1", {"valor": titulo, "negrito": True})
    aba.congelar_cabecalho = True


def _aba_do_financeiro(mes: str, categoria: str):
    """Os honorarios do Financeiro em linhas: quem, quando, quanto, pago ou nao."""
    lancamentos = [
        x for x in estado.financeiro.listar(tipo="recebimento", mes=mes)
        if not categoria or x.get("categoria") == categoria
    ]
    rotulo = financeiro.CATEGORIAS.get(categoria, "Recebimentos")
    aba = planilha.Aba(nome=(rotulo + (" " + escritorio.mes_por_extenso(mes) if mes else ""))[:24])
    _cabecalho_da_aba(aba, ["Cliente", "Descrição", "Vencimento", "Valor", "Situação"])

    for i, l in enumerate(lancamentos, start=2):
        aba.gravar(f"A{i}", {"valor": l.get("cadastro_nome") or "—"})
        aba.gravar(f"B{i}", {"valor": l.get("descricao") or ""})
        aba.gravar(f"C{i}", {"valor": _data_br(l.get("vencimento")), "formato": "data"})
        # O valor vai em reais com virgula, como se digita aqui; a planilha
        # entende isso como numero e soma.
        aba.gravar(f"D{i}", {"valor": financeiro.em_reais(l.get("centavos", 0)).replace("R$ ", ""),
                             "formato": "moeda"})
        aba.gravar(f"E{i}", {"valor": "recebido" if l.get("liquidado_em") else "a receber"})

    if lancamentos:
        fim = len(lancamentos) + 1
        aba.gravar(f"C{fim + 1}", {"valor": "Total", "negrito": True})
        aba.gravar(f"D{fim + 1}", {"valor": f"=SOMA(D2:D{fim})", "formato": "moeda", "negrito": True})
    return aba, len(lancamentos)


def _aba_dos_prazos():
    """Os prazos que os documentos do Acervo pedem para conferir."""
    from classify import CacheClassificacao

    cache = CacheClassificacao(CLASSIFICACAO_PATH).dados
    prazos = estado.tarefas.sugerir(list(cache.values()))
    aba = planilha.Aba(nome="Prazos do Acervo")
    _cabecalho_da_aba(aba, ["Documento", "Cliente", "Tipo", "Prazo", "Faltam (dias)"])

    hoje = date.today()
    for i, p in enumerate(prazos, start=2):
        aba.gravar(f"A{i}", {"valor": p.get("arquivo") or ""})
        aba.gravar(f"B{i}", {"valor": p.get("cliente") or "—"})
        aba.gravar(f"C{i}", {"valor": p.get("lista") or ""})
        aba.gravar(f"D{i}", {"valor": _data_br(p.get("prazo")), "formato": "data"})
        try:
            faltam = (date.fromisoformat(p["prazo"]) - hoje).days
        except (ValueError, KeyError, TypeError):
            faltam = ""
        aba.gravar(f"E{i}", {"valor": str(faltam), "formato": "numero"})
    return aba, len(prazos)


def _data_br(iso: str | None) -> str:
    """2026-09-20 vira 20/09/2026 - a planilha guarda como se digita."""
    if not iso:
        return ""
    try:
        return date.fromisoformat(str(iso)[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return str(iso)

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
        resposta = estado.cliente_para("redacao").ask(instrucao + f"\n\nPedido: {payload.pedido}",
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
    # As despesas fixas com "lançar todo mês" entram no mes de hoje (uma vez).
    estado.financeiro.lancar_fixas(estado.cadastros.listar(tipo="despesa"))
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
    dados["candidatos_folha"] = estado.folha.pessoas(mes_alvo)
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


# --------------------------------------------------- o extrato do banco

MAX_EXTRATO_BYTES = 8 * 1024 * 1024


@app.post("/api/financeiro/banco")
async def financeiro_banco(arquivo: UploadFile = File(...)) -> dict:
    """
    Le o extrato do banco e diz o que parece ser o que - sem gravar nada.

    Conciliar propoe; quem da baixa e a pessoa, na tela, marcando. Dar baixa
    sozinho por causa de um valor igual seria escrever no livro-caixa de
    alguem por palpite, e valor igual acontece toda semana num escritorio que
    cobra honorario fixo.
    """
    nome = Path(arquivo.filename or "").name
    dados = await arquivo.read(MAX_EXTRATO_BYTES + 1)
    if len(dados) > MAX_EXTRATO_BYTES:
        raise HTTPException(status_code=413, detail="esse arquivo passa de 8 MB")

    try:
        movimentos = extrato.ler(dados, nome)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    lancamentos: list[dict] = []
    for mes in extrato.meses_do_extrato(movimentos):
        lancamentos += estado.financeiro.listar(mes=mes)
    vistos, unicos = set(), []
    for l in lancamentos:
        if l["id"] not in vistos:
            vistos.add(l["id"])
            unicos.append(l)

    pares = extrato.conciliar(movimentos, unicos)
    return {"arquivo": nome, "pares": [p.to_dict() for p in pares],
            "resumo": extrato.resumo(pares),
            "categorias": [{"valor": k, "rotulo": v} for k, v in financeiro.CATEGORIAS.items()]}


class ConciliarEscolha(BaseModel):
    # Os pares que a pessoa marcou: lancamento que recebe a baixa e a data do
    # banco. Movimento sem lancamento pode virar lancamento novo.
    baixas: list[dict] = []
    novos: list[dict] = []


@app.post("/api/financeiro/banco/aplicar")
def financeiro_banco_aplicar(payload: ConciliarEscolha) -> dict:
    """Da baixa no que foi marcado e lanca o que a pessoa mandou lancar."""
    baixados, criados, erros = 0, 0, []

    for item in payload.baixas:
        id_ = int(item.get("lancamento_id") or 0)
        quando = str(item.get("data") or "")[:10]
        if not id_:
            continue
        if estado.financeiro.liquidar(id_, quando):
            baixados += 1
        else:
            erros.append(f"lançamento {id_} não estava aberto")

    for item in payload.novos:
        dados = {
            "tipo": "recebimento" if int(item.get("centavos", 0)) >= 0 else "despesa",
            "descricao": str(item.get("descricao", ""))[:160] or "Do extrato do banco",
            "centavos": abs(int(item.get("centavos", 0))),
            "categoria": str(item.get("categoria") or "outros"),
            "cadastro_id": item.get("cadastro_id"),
            "vencimento": str(item.get("data") or "")[:10],
            "liquidado_em": str(item.get("data") or "")[:10],
            "observacao": "Lançado a partir do extrato do banco.",
        }
        try:
            estado.financeiro.salvar(dados)
            criados += 1
        except ValueError as exc:
            erros.append(str(exc))

    partes = []
    if baixados:
        partes.append(_quantos(baixados, "baixa"))
    if criados:
        partes.append(_quantos(criados, "lançamento") + " novo" + ("s" if criados > 1 else ""))
    aviso = " e ".join(partes) + " a partir do extrato" if partes else "nada foi marcado"
    return {"baixados": baixados, "criados": criados, "erros": erros, "aviso": aviso,
            **estado.financeiro.para_tela()}


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
    l = estado.base.um("SELECT descricao, centavos, vencimento FROM lancamentos WHERE id = ?", (id_,))
    if not l:
        raise HTTPException(status_code=404, detail="lançamento não encontrado")
    reais = f"R$ {l['centavos'] / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    entrada = estado.lixeira.apagar_linha("lancamento", id_, l["descricao"], "Financeiro · " + reais + (" · " + l["vencimento"] if l["vencimento"] else ""))
    return _foi_para_lixeira(entrada, "apagado", id_)


@app.post("/api/financeiro/lancamentos/{id_}/comprovante")
async def financeiro_comprovante(id_: int, arquivo: UploadFile, decisoes: str = Form("")) -> dict:
    """Guarda o comprovante na biblioteca e o liga ao lancamento. Nome
    repetido com outro conteudo: a tela pergunta (src/nomes.py)."""
    if not estado.financeiro.obter(id_):
        raise HTTPException(status_code=404, detail="lançamento não encontrado")

    nome = Path(arquivo.filename or "").name
    if not nome:
        raise HTTPException(status_code=400, detail="arquivo sem nome")

    dados = await arquivo.read()
    if len(dados) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="arquivo grande demais")

    lancamento = estado.financeiro.obter(id_) or {}
    quando = lancamento.get("liquidado_em") or lancamento.get("vencimento") or ""
    pasta = _pasta_no_acervo("Financeiro", "Comprovantes", quando[:7] or escritorio.mes_de_hoje())
    escolhas = nomes_mod.do_pedido(decisoes)
    igual = pasta / nome
    if igual.exists() and nome not in escolhas and igual.read_bytes() == dados:
        destino = igual                    # o mesmo comprovante: so liga
    else:
        pendentes: list[dict] = []
        destino = nomes_mod.destino(pasta, nome, escolhas, pendentes)
        nomes_mod.conferir(pendentes)
        destino.write_bytes(dados)

    import hashlib

    sha1 = hashlib.sha1(dados).hexdigest()
    estado.financeiro.anexar(id_, destino.name, str(destino), sha1)
    estado.recarregar_em_segundo_plano()
    return estado.financeiro.obter(id_) or {}


@app.post("/api/financeiro/lancar-pela-conversa")
def financeiro_lancar_pela_conversa(payload: dict) -> dict:
    """
    O "Lançar" da coluna (`Conversa - Lancamento`, `- Recebimento`): grava
    (ou atualiza a cobranca em aberto), da baixa quando ja foi pago, guarda o
    papel (o comprovante vai para Financeiro/Comprovantes do Acervo e fica
    ligado; o boleto entra em Papeis do mes) e cria o lembrete na Agenda.
    """
    dados = dict(payload.get("dados") or {})
    id_ = payload.get("id") or None
    try:
        id_ = estado.financeiro.salvar(dados, int(id_) if id_ else None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    liquidado = str(payload.get("liquidado_em") or "")[:10]
    if liquidado:
        estado.financeiro.liquidar(id_, liquidado)
    lancamento = estado.financeiro.obter(id_) or {}
    papel = payload.get("papel") or {}
    papel_feito = ""
    if papel.get("nome"):
        doc = next((d for d in estado.searcher.documents if d.name == papel["nome"]), None)
        if doc and Path(doc.path).exists():
            if papel.get("tipo") == "boleto":
                estado.papeis.salvar({"tipo": "boleto", "lancamento_id": id_, "cadastro_id": lancamento.get("cadastro_id"),
                                      "centavos": lancamento.get("centavos", 0), "data": lancamento.get("vencimento", ""),
                                      "observacao": doc.name})
                papel_feito = "boleto"
            else:
                import hashlib
                import shutil

                quando = lancamento.get("liquidado_em") or lancamento.get("vencimento") or ""
                pasta = _pasta_no_acervo("Financeiro", "Comprovantes", quando[:7] or escritorio.mes_de_hoje())
                destino = pasta / Path(doc.path).name
                if not destino.exists():
                    shutil.copy2(doc.path, destino)
                sha1 = hashlib.sha1(destino.read_bytes()).hexdigest()
                estado.financeiro.anexar(id_, destino.name, str(destino), sha1)
                estado.recarregar_em_segundo_plano()
                papel_feito = "comprovante"
    tarefa = 0
    if payload.get("lembrar") and lancamento.get("vencimento") and not liquidado:
        try:
            antes = (date.fromisoformat(lancamento["vencimento"]) - timedelta(days=1)).isoformat()
        except ValueError:
            antes = ""
        if antes:
            verbo = "Receber" if lancamento.get("tipo") == "recebimento" else "Pagar"
            tarefa = estado.tarefas.salvar({"titulo": f"{verbo}: {lancamento.get('descricao', '')} — {lancamento.get('valor', '')}",
                                            "prazo": antes, "cadastro_id": lancamento.get("cadastro_id"),
                                            "anotacao": "Lembrete do lançamento feito pela conversa (vence " + escritorio._br(lancamento["vencimento"]) + ")."})
    return {"lancamento": estado.financeiro.obter(id_) or {}, "papel": papel_feito, "tarefa": tarefa}


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


@app.get("/api/relatorios/financeiro")
def relatorios_financeiro(mes: str = "", comparar: str = "") -> dict:
    """Os numeros do relatorio financeiro do mes, somados aqui (src/financeiro_pela_conversa.py)."""
    import financeiro_pela_conversa as fpc

    mes = mes or escritorio.mes_de_hoje()
    pasta = _pasta_no_acervo("Relatórios", "Financeiro")
    pdf = pasta / f"relatorio-financeiro-{mes}.pdf"
    xlsx = _pasta_no_acervo("Financeiro", "Planilhas") / f"financeiro-{mes}.xlsx"
    return {"relatorio": fpc.relatorio(estado.financeiro, estado.base, mes, comparar),
            "pdf": {"nome": pdf.name, "caminho": str(pdf)} if pdf.exists() else None,
            "xlsx": {"nome": xlsx.name, "caminho": str(xlsx)} if xlsx.exists() else None,
            "precisa": estado.financeiro.precisa_de_voce()}


@app.post("/api/relatorios/financeiro/gerar")
def relatorios_financeiro_gerar(payload: dict) -> dict:
    """Gera (ou refaz) o PDF e a planilha do mes no Acervo."""
    mes = str(payload.get("mes") or escritorio.mes_de_hoje())[:7]
    try:
        return _gerar_relatorio_financeiro(mes, str(payload.get("comparar") or "")[:7])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"não consegui gerar: {exc}") from exc


@app.get("/api/relatorios/financeiro/arquivo")
def relatorios_financeiro_arquivo(nome: str) -> FileResponse:
    """Baixar o PDF ou a planilha gerados (so das duas pastas do relatorio)."""
    nome = Path(nome).name
    for pasta, sufixo, tipo in ((_pasta_no_acervo("Relatórios", "Financeiro"), ".pdf", "application/pdf"),
                                (_pasta_no_acervo("Financeiro", "Planilhas"), ".xlsx",
                                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")):
        alvo = pasta / nome
        if alvo.suffix.lower() == sufixo and alvo.is_file():
            return FileResponse(alvo, media_type=tipo, headers=_anexo(alvo.name))
    raise HTTPException(status_code=404, detail="arquivo não encontrado")


@app.post("/api/relatorios/parecer-do-mes")
def relatorios_parecer_do_mes(payload: dict | None = None) -> dict:
    """
    O "Parecer do mês": o modelo escreve sobre os numeros ja somados
    (src/financeiro_pela_conversa.py) - nao calcula nada.
    """
    import financeiro_pela_conversa as fpc

    mes = str((payload or {}).get("mes") or escritorio.mes_de_hoje())[:7]
    comparar = str((payload or {}).get("comparar") or fpc.mes_antes(mes))[:7]
    r = fpc.relatorio(estado.financeiro, estado.base, mes, comparar)
    disponivel, motivo = check_ollama(estado.client.model)
    if not disponivel:
        raise HTTPException(status_code=503, detail=motivo)
    try:
        texto = estado.cliente_para("redacao").ask(fpc.INSTRUCAO_PARECER_DO_MES,
                                                   fpc.numeros_para_o_parecer(r, estado.financeiro.precisa_de_voce()))
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"texto": " ".join((texto or "").split()), "mes": mes}


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
        texto = estado.cliente_para("resumos").ask(relatorios.INSTRUCAO_PARECER, numeros)
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "parecer": _limpar_sugestao(texto),
        "numeros": numeros,
        "aviso": "Escrito sobre os números acima, que foram calculados aqui. Confira antes de usar.",
    }


@app.get("/api/relatorios/pdf")
def relatorios_pdf_link(quando: str = ""):
    """
    O mesmo PDF por link. A tela baixava com um <form> POST, que manda
    "quando=..." como formulario - e a rota JSON respondia com o erro de
    validacao na tela inteira (achado em 27/09/2026). Link GET e o que o
    Exportar ja fazia, e o download do Windows abre sozinho.
    """
    return relatorios_pdf({"quando": quando})


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


# ------------------------------------------------------------------ backup
# Backup e restauracao (src/backup.py, docs/PLANO-PRODUTO.md P1). So na janela
# do servidor: de fora, as rotas nao existem (acesso/politicas.py).

import backup as backup_mod  # noqa: E402

_BACKUP = {"fazendo": False, "feitos": 0, "total": 0, "erro": ""}
_TRAVA_BACKUP = threading.Lock()
BACKUP_A_CADA_S = 24 * 3600


def _prefs_backup() -> dict:
    return dict(estado.prefs.dados.get("backup") or {})


def _senha_do_backup() -> str:
    import segredos

    guardada = _prefs_backup().get("senha") or ""
    if not guardada:
        return ""
    try:
        return segredos.revelar(guardada)
    except Exception:  # noqa: BLE001 - guardada por outro usuario do Windows
        return ""


def _fazer_backup() -> dict:
    """Um backup agora (o automatico e o botao). Devolve o resultado ou levanta ErroBackup."""
    p = _prefs_backup()
    if not p.get("pasta"):
        raise backup_mod.ErroBackup("escolha a pasta do backup")
    senha = _senha_do_backup()
    if not senha:
        raise backup_mod.ErroBackup("defina a senha do backup")
    if not _TRAVA_BACKUP.acquire(blocking=False):
        raise backup_mod.ErroBackup("já há um backup em andamento")
    try:
        _BACKUP.update(fazendo=True, feitos=0, total=0, erro="")

        def andamento(feitos, total):
            _BACKUP.update(feitos=feitos, total=total)

        try:
            feito = backup_mod.fazer(DADOS_DIR, Path(p["pasta"]), senha, versao=VERSAO,
                                     manter=int(p.get("manter") or 10), andamento=andamento)
        except backup_mod.ErroBackup as exc:
            _BACKUP["erro"] = str(exc)
            estado.prefs.atualizar({"backup": {"ultimo_erro": str(exc)}})
            raise
        estado.prefs.atualizar({"backup": {"ultimo": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                           "ultimo_arquivo": feito["arquivo"], "ultimo_erro": ""}})
        return feito
    finally:
        _BACKUP["fazendo"] = False
        _TRAVA_BACKUP.release()


def _backup_automatico() -> None:
    """Uma vez por dia, com a pasta e a senha definidas: confere a cada meia hora."""
    time.sleep(120)  # deixa o programa abrir primeiro
    while True:
        try:
            p = _prefs_backup()
            if p.get("automatico", True) and p.get("pasta") and p.get("senha"):
                ultimo = p.get("ultimo") or ""
                try:
                    passou = time.time() - time.mktime(time.strptime(ultimo, "%Y-%m-%dT%H:%M:%S")) if ultimo else None
                except ValueError:
                    passou = None
                if passou is None or passou >= BACKUP_A_CADA_S:
                    _fazer_backup()
        except Exception:  # noqa: BLE001 - o erro fica em ultimo_erro, e tenta na proxima volta
            pass
        time.sleep(1800)


def _backup_para_tela() -> dict:
    p = _prefs_backup()
    return {"pasta": p.get("pasta", ""), "automatico": bool(p.get("automatico", True)), "manter": int(p.get("manter") or 10),
            "tem_senha": bool(p.get("senha")), "ultimo": p.get("ultimo", ""), "ultimo_arquivo": p.get("ultimo_arquivo", ""),
            "ultimo_erro": p.get("ultimo_erro", ""), "andamento": dict(_BACKUP),
            "backups": backup_mod.listar(Path(p["pasta"]))[:20] if p.get("pasta") else [],
            "restauracao_pronta": (backup_mod.pasta_de_restaurar(DADOS_DIR) / ".restaurar-pronto").is_file(),
            "senha_minima": backup_mod.SENHA_MINIMA}


class ConfigBackup(BaseModel):
    pasta: str | None = None
    senha: str | None = None
    automatico: bool | None = None
    manter: int | None = None


class PastaDeBackups(BaseModel):
    pasta: str


class RestaurarBackup(BaseModel):
    arquivo: str
    senha: str


@app.get("/api/backup")
def backup_ver() -> dict:
    return _backup_para_tela()


@app.post("/api/backup/configurar")
def backup_configurar(dados: ConfigBackup) -> dict:
    import segredos

    novo: dict = {}
    if dados.pasta is not None:
        pasta = Path(dados.pasta.strip().strip('"'))
        if not pasta.is_absolute():
            raise HTTPException(status_code=400, detail="escolha uma pasta deste computador (caminho completo)")
        if pasta.resolve() == DADOS_DIR or DADOS_DIR in pasta.resolve().parents:
            raise HTTPException(status_code=400, detail="a pasta do backup não pode ficar dentro da pasta de dados do PAULUS")
        novo["pasta"] = str(pasta)
    if dados.senha is not None:
        if len(dados.senha) < backup_mod.SENHA_MINIMA:
            raise HTTPException(status_code=400, detail=f"a senha do backup precisa de pelo menos {backup_mod.SENHA_MINIMA} caracteres")
        if not segredos.disponivel():
            raise HTTPException(status_code=400, detail="este computador não tem como guardar a senha com proteção")
        novo["senha"] = segredos.proteger(dados.senha)
    if dados.automatico is not None:
        novo["automatico"] = bool(dados.automatico)
    if dados.manter is not None:
        novo["manter"] = max(1, min(60, int(dados.manter)))
    if novo:
        estado.prefs.atualizar({"backup": novo})
    return _backup_para_tela()


@app.post("/api/backup/agora")
def backup_agora() -> dict:
    """Comeca um backup em segundo plano; a tela acompanha pelo GET."""
    p = _prefs_backup()
    if not p.get("pasta") or not p.get("senha"):
        raise HTTPException(status_code=400, detail="escolha a pasta e defina a senha do backup antes")
    if _BACKUP["fazendo"]:
        raise HTTPException(status_code=409, detail="já há um backup em andamento")
    _BACKUP.update(fazendo=True, feitos=0, total=0, erro="")

    def rodar() -> None:
        try:
            _fazer_backup()
        except Exception as exc:  # noqa: BLE001 - a tela mostra
            _BACKUP.update(fazendo=False, erro=str(exc))

    threading.Thread(target=rodar, name="backup-agora", daemon=True).start()
    return _backup_para_tela()


@app.post("/api/backup/listar")
def backup_listar(dados: PastaDeBackups) -> dict:
    """Os backups de uma pasta qualquer (restaurar num computador novo)."""
    return {"backups": backup_mod.listar(Path(dados.pasta.strip().strip('"')))[:50]}


@app.post("/api/backup/restaurar")
def backup_restaurar(dados: RestaurarBackup) -> dict:
    """Prepara a restauracao: a troca acontece quando o PAULUS abre de novo."""
    arquivo = Path(dados.arquivo)
    if arquivo.suffix != backup_mod.EXTENSAO:
        raise HTTPException(status_code=400, detail="escolha um arquivo de backup do PAULUS (.paulusbak)")
    try:
        manifesto = backup_mod.preparar_restauracao(arquivo, dados.senha, DADOS_DIR)
    except backup_mod.ErroBackup as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"manifesto": manifesto, **_backup_para_tela()}


@app.post("/api/backup/restaurar/cancelar")
def backup_restaurar_cancelar() -> dict:
    shutil.rmtree(backup_mod.pasta_de_restaurar(DADOS_DIR), ignore_errors=True)
    return _backup_para_tela()


@app.post("/api/backup/reabrir")
def backup_reabrir() -> dict:
    """Fecha e abre o PAULUS de novo, para a restauracao entrar (so no instalado)."""
    from acesso import energia

    exe = energia.exe_do_programa()
    if not exe:
        raise HTTPException(status_code=400, detail="feche e abra o PAULUS para terminar de restaurar")
    import subprocess

    def reabrir() -> None:
        time.sleep(1.5)
        subprocess.Popen([str(exe)], close_fds=True, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
        if estado.ao_fechar:
            estado.ao_fechar()

    threading.Thread(target=reabrir, name="reabrir", daemon=True).start()
    return {"ok": True}


# ------------------------------------------------- prazos e publicacoes
# Prazos em dias uteis (src/prazos.py) e as publicacoes do DJEN pelas OABs
# acompanhadas (src/publicacoes.py) - docs/PLANO-PRODUTO.md, P3.

import prazos as prazos_mod  # noqa: E402
import publicacoes as publicacoes_mod  # noqa: E402

_TRAVA_PUBLICACOES = threading.Lock()


def _feriados_do_escritorio() -> dict:
    return prazos_mod.extras_das_preferencias((estado.prefs.dados.get("prazos") or {}).get("feriados"))


def _oabs_acompanhadas() -> list[dict]:
    """A OAB de Meus dados e as que o escritorio acrescentou, sem repetir."""
    p = estado.prefs.dados
    lista = []
    for texto in [(p.get("pessoa") or {}).get("oab", "")] + [str(x) for x in (p.get("publicacoes") or {}).get("oabs") or []]:
        o = publicacoes_mod.ler_oab(texto)
        if o and o not in lista:
            lista.append(o)
    return lista


def _consultar_publicacoes() -> dict:
    from datetime import date as _date

    if not _TRAVA_PUBLICACOES.acquire(blocking=False):
        raise publicacoes_mod.ErroPublicacoes("já há uma consulta em andamento")
    try:
        oabs = _oabs_acompanhadas()
        if not oabs:
            raise publicacoes_mod.ErroPublicacoes("diga a sua OAB em Meus dados (ou acrescente as da equipe) antes")
        pp = estado.prefs.dados.get("publicacoes") or {}
        de, ate = publicacoes_mod.periodo_para_consultar(pp.get("ultima", ""))
        novas = 0
        try:
            for o in oabs:
                itens = [publicacoes_mod.normalizar(i, o) for i in publicacoes_mod.consultar(o, de, ate)]
                novas += estado.publicacoes.guardar(itens)
        except publicacoes_mod.ErroPublicacoes as exc:
            estado.prefs.atualizar({"publicacoes": {"ultimo_erro": str(exc)}})
            raise
        estado.prefs.atualizar({"publicacoes": {"ultima": _date.today().isoformat(), "ultimo_erro": ""}})
        # N2: a publicação de um processo cadastrado liga a ele (e pede o prazo, se acompanhado).
        try:
            ligadas = processos_mod.ligar_publicacoes(estado, _feriados_do_escritorio())
        except Exception:  # noqa: BLE001 - a consulta vale mesmo sem ligar
            ligadas = {}
        return {"novas": novas, "de": de.isoformat(), "ate": ate.isoformat(), "oabs": len(oabs), "ligadas": ligadas}
    finally:
        _TRAVA_PUBLICACOES.release()


def _publicacoes_automatico() -> None:
    """Uma vez por dia, com a consulta ligada: confere a cada hora."""
    from datetime import date as _date

    time.sleep(180)
    while True:
        try:
            pp = estado.prefs.dados.get("publicacoes") or {}
            if pp.get("ligado") and pp.get("ultima", "") != _date.today().isoformat():
                _consultar_publicacoes()
        except Exception:  # noqa: BLE001 - o erro fica em ultimo_erro
            pass
        time.sleep(3600)


class CalculoDePrazo(BaseModel):
    data: str
    dias: int
    origem: str = "intimacao"
    uteis: bool = True


class FeriadosDoEscritorio(BaseModel):
    feriados: list[dict]


class ConfigPublicacoes(BaseModel):
    ligado: bool | None = None
    oabs: list[str] | None = None


class PrazoDaPublicacao(BaseModel):
    dias: int = 15
    uteis: bool = True
    titulo: str = ""
    # No penal, o recesso do art. 220 do CPC não suspende (N1).
    recesso: bool = True
    # O ato e a base da sugestão escolhida, para a anotação da tarefa.
    ato: str = ""
    base: str = ""


@app.post("/api/prazos/calcular")
def prazos_calcular(dados: CalculoDePrazo) -> dict:
    from datetime import date as _date

    try:
        return prazos_mod.calcular(_date.fromisoformat(dados.data), int(dados.dias), origem=dados.origem,
                                   uteis=dados.uteis, extras=_feriados_do_escritorio())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc) if "prazo" in str(exc) else "data inválida") from exc


@app.get("/api/prazos/feriados")
def prazos_feriados() -> dict:
    return {"feriados": (estado.prefs.dados.get("prazos") or {}).get("feriados") or []}


@app.post("/api/prazos/feriados")
def prazos_feriados_salvar(dados: FeriadosDoEscritorio) -> dict:
    from datetime import date as _date

    limpos = []
    for f in dados.feriados[:300]:
        try:
            limpos.append({"data": _date.fromisoformat(str(f.get("data"))).isoformat(), "nome": str(f.get("nome") or "")[:80]})
        except ValueError:
            continue
    estado.prefs.atualizar({"prazos": {"feriados": sorted(limpos, key=lambda x: x["data"])}})
    return prazos_feriados()


def _sugestao_da_publicacao(pub: dict) -> dict | None:
    """O prazo pelo tipo de ato, lido no texto da publicação (N1)."""
    import tipo_de_ato
    from datetime import date as _date

    try:
        dia = _date.fromisoformat(str(pub.get("data") or "")[:10])
    except ValueError:
        return None
    s = tipo_de_ato.do_texto(pub.get("texto") or "", tipo=pub.get("tipo") or "", classe=pub.get("classe") or "",
                             orgao=pub.get("orgao") or "", tribunal=pub.get("tribunal") or "", numero=pub.get("processo") or "")
    return processos_mod.com_conta(s, dia, "disponibilizacao", _feriados_do_escritorio())


def _publicacoes_para_tela(filtro: str = "novas") -> dict:
    pp = estado.prefs.dados.get("publicacoes") or {}
    lista = estado.publicacoes.listar(filtro)
    for pub in lista:
        try:
            pub["sugestao"] = _sugestao_da_publicacao(pub)
        except Exception:  # noqa: BLE001 - sem sugestão, a caixa abre com 15 dias
            pub["sugestao"] = None
    return {"publicacoes": lista, "novas": estado.publicacoes.contar_novas(),
            "ligado": bool(pp.get("ligado")), "oabs": [f"{o['uf']} {o['numero']}" for o in _oabs_acompanhadas()],
            "oabs_extras": pp.get("oabs") or [], "ultima": pp.get("ultima", ""), "ultimo_erro": pp.get("ultimo_erro", "")}


@app.get("/api/publicacoes")
def publicacoes_ver(filtro: str = "novas") -> dict:
    return _publicacoes_para_tela(filtro)


@app.post("/api/publicacoes/configurar")
def publicacoes_configurar(dados: ConfigPublicacoes) -> dict:
    novo: dict = {}
    if dados.ligado is not None:
        novo["ligado"] = bool(dados.ligado)
    if dados.oabs is not None:
        ruins = [o for o in dados.oabs if o.strip() and not publicacoes_mod.ler_oab(o)]
        if ruins:
            raise HTTPException(status_code=400, detail="OAB que não entendi: " + ", ".join(ruins) + " (escreva como GO 12345)")
        novo["oabs"] = [o.strip().upper() for o in dados.oabs if o.strip()][:30]
    if novo:
        estado.prefs.atualizar({"publicacoes": novo})
    return _publicacoes_para_tela()


@app.post("/api/publicacoes/consultar")
def publicacoes_consultar() -> dict:
    try:
        feito = _consultar_publicacoes()
    except publicacoes_mod.ErroPublicacoes as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {**_publicacoes_para_tela(), "encontradas": feito["novas"], "periodo": {"de": feito["de"], "ate": feito["ate"]}}


@app.post("/api/publicacoes/{id_}/lida")
def publicacoes_lida(id_: int, lida: bool = True) -> dict:
    if not estado.publicacoes.obter(id_):
        raise HTTPException(status_code=404, detail="publicação não encontrada")
    estado.publicacoes.marcar(id_, lida)
    return _publicacoes_para_tela()


@app.post("/api/publicacoes/{id_}/prazo")
def publicacoes_prazo(id_: int, dados: PrazoDaPublicacao) -> dict:
    """O prazo sugerido pela data de disponibilizacao vira tarefa; a publicacao fica lida."""
    from datetime import date as _date

    pub = estado.publicacoes.obter(id_)
    if not pub:
        raise HTTPException(status_code=404, detail="publicação não encontrada")
    try:
        conta = prazos_mod.calcular(_date.fromisoformat(pub["data"]), int(dados.dias), origem="disponibilizacao",
                                    uteis=dados.uteis, extras=_feriados_do_escritorio(), recesso=dados.recesso)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    titulo = dados.titulo.strip() or f"Prazo: {dados.ato or pub['tipo'] or 'intimação'} · {pub['processo']}"
    anotacao = (f"{pub['tribunal']} · {pub['orgao']}\nProcesso {pub['processo']}\n"
                f"Disponibilizado no DJEN em {pub['data']}\n\n" +
                (f"{dados.ato} — {dados.base}\n\n" if dados.ato and dados.base else "") + "\n".join(conta["passos"]))
    tid = estado.tarefas.salvar({"titulo": titulo[:200], "prazo": conta["vencimento"], "importante": True,
                                 "lista": "Prazos", "anotacao": anotacao})
    estado.publicacoes.marcar(id_, tarefa_id=tid)
    return {"tarefa_id": tid, "conta": conta, **_publicacoes_para_tela()}


# ------------------------------------------------------------------ horas
# Horas por servico e a cobranca delas (src/horas.py, P4). As rotas moram em
# /api/servicos/{id}: valem as permissoes do modulo Servicos e a regra dos
# colaboradores (servico fechado para a pessoa: 404). Cobrar mexe no
# Financeiro: so na janela do servidor.

import horas as horas_mod  # noqa: E402


class RegistroDeHoras(BaseModel):
    duracao: str = ""
    dia: str = ""
    descricao: str = ""


class Cronometro(BaseModel):
    acao: str
    descricao: str = ""


class ValorDaHora(BaseModel):
    valor: str


class CobrarHoras(BaseModel):
    vencimento: str = ""


def _servico_ou_404(id_: int) -> dict:
    s = estado.base.um("SELECT id, nome, cadastro_id, valor_hora FROM servicos WHERE id = ?", (id_,))
    if not s:
        raise HTTPException(status_code=404, detail="serviço não encontrado")
    return s


def _horas_para_tela(id_: int, request: Request | None) -> dict:
    s = _servico_ou_404(id_)
    q = equipe.quem(request, estado.prefs.dados)
    h = estado.horas.do_servico(id_)
    c = estado.horas.cronometro(q["conta_id"])
    return {**h, "valor_hora": int(s.get("valor_hora") or 0),
            "a_cobrar_centavos": round(h["a_cobrar_min"] * int(s.get("valor_hora") or 0) / 60),
            "cronometro": ({**c, "neste": int(c["servico_id"]) == id_} if c else None),
            "minha_conta": q["conta_id"]}


@app.get("/api/servicos/{id_}/horas")
def horas_ver(id_: int, request: Request) -> dict:
    return _horas_para_tela(id_, request)


@app.post("/api/servicos/{id_}/horas")
def horas_registrar(id_: int, dados: RegistroDeHoras, request: Request) -> dict:
    _servico_ou_404(id_)
    q = equipe.quem(request, estado.prefs.dados)
    try:
        estado.horas.registrar(id_, minutos=horas_mod.ler_duracao(dados.duracao), dia=dados.dia[:10],
                               descricao=dados.descricao, quem=q["nome"], conta=q["conta_id"])
    except horas_mod.ErroHoras as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _horas_para_tela(id_, request)


@app.delete("/api/servicos/{id_}/horas/{hid}")
def horas_apagar(id_: int, hid: int, request: Request) -> dict:
    q = equipe.quem(request, estado.prefs.dados)
    # De fora, cada pessoa so apaga o proprio registro; na janela do servidor, qualquer um.
    so_meu = q["conta_id"] if equipe.pessoa_da_vez() is not None else None
    if not estado.horas.apagar(hid, so_meu):
        raise HTTPException(status_code=400, detail="esse registro não pode ser apagado (já cobrado, ou de outra pessoa)")
    return _horas_para_tela(id_, request)


@app.post("/api/servicos/{id_}/horas/cronometro")
def horas_cronometro(id_: int, dados: Cronometro, request: Request) -> dict:
    _servico_ou_404(id_)
    q = equipe.quem(request, estado.prefs.dados)
    if dados.acao == "comecar":
        estado.horas.comecar(id_, quem=q["nome"], conta=q["conta_id"], descricao=dados.descricao)
    elif dados.acao == "parar":
        estado.horas.parar(q["conta_id"], dados.descricao)
    else:
        raise HTTPException(status_code=400, detail="ação desconhecida")
    return _horas_para_tela(id_, request)


@app.post("/api/servicos/{id_}/horas/valor")
def horas_valor(id_: int, dados: ValorDaHora, request: Request) -> dict:
    import financeiro as financeiro_mod

    _servico_ou_404(id_)
    try:
        centavos = abs(financeiro_mod.para_centavos(dados.valor))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="valor inválido") from exc
    estado.base.escrever("UPDATE servicos SET valor_hora = ? WHERE id = ?", (centavos, id_))
    return _horas_para_tela(id_, request)


@app.post("/api/servicos/{id_}/horas/cobrar")
def horas_cobrar(id_: int, dados: CobrarHoras, request: Request) -> dict:
    """As horas ainda nao cobradas viram um recebimento de honorarios no Financeiro."""
    s = _servico_ou_404(id_)
    h = estado.horas.do_servico(id_)
    valor = int(s.get("valor_hora") or 0)
    if not h["a_cobrar_min"]:
        raise HTTPException(status_code=400, detail="não há horas a cobrar neste serviço")
    if not valor:
        raise HTTPException(status_code=400, detail="defina o valor da hora deste serviço antes")
    centavos = round(h["a_cobrar_min"] * valor / 60)
    detalhe = "\n".join(f"{p['quem']}: {horas_mod.texto_da_duracao(p['minutos'])}" for p in
                        horas_mod.Horas._por_pessoa([r for r in h["registros"] if not r.get("lancamento_id")]))
    try:
        lid = estado.financeiro.salvar({
            "tipo": "recebimento", "categoria": "honorarios", "centavos": centavos, "cadastro_id": s.get("cadastro_id"),
            "descricao": f"Honorários por hora · {s['nome']} ({horas_mod.texto_da_duracao(h['a_cobrar_min'])})",
            "vencimento": dados.vencimento[:10], "observacao": "Horas do serviço:\n" + detalhe})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    estado.horas.marcar_cobradas(id_, lid)
    return {"lancamento_id": lid, **_horas_para_tela(id_, request)}


# ------------------------------------------------------------ busca geral
# A busca de tudo (Ctrl+K, js/50-busca.js): as telas e acoes a tela ja sabe;
# aqui, os dados do escritorio que casam com o termo. De fora, cada fonte so
# entra se a pessoa ve o modulo (acesso/permissoes.py), e servicos, tarefas,
# agenda, gravacoes e Acervo ja vem filtrados pela regra dos colaboradores.

def _sem_acento(texto: str) -> str:
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFD", str(texto or "").lower()) if unicodedata.category(c) != "Mn")


def _modulos_visiveis() -> set[str] | None:
    """Os modulos que a pessoa de fora ve; None = a janela do servidor (todos)."""
    from acesso import permissoes

    sessao = equipe.pessoa_da_vez()
    if sessao is None:
        return None
    niveis = sessao.get("permissoes") or permissoes.efetivas(sessao.get("papel", ""), {})
    return {m["id"] for m in permissoes.MODULOS if niveis.get(m["id"], m["padrao"]) != permissoes.NAO}


@app.get("/api/busca")
def busca_geral(q: str = "") -> dict:
    termo = " ".join(str(q or "").split())[:80]
    if len(termo) < 2:
        return {"itens": []}
    palavras = _sem_acento(termo).split()
    casa = lambda *textos: all(p in _sem_acento(" ".join(str(t or "") for t in textos)) for p in palavras)  # noqa: E731
    ve = _modulos_visiveis()
    pode = lambda m: ve is None or m in ve  # noqa: E731
    like = f"%{termo}%"
    itens: list[dict] = []
    ROTULO_CAD = {"cliente": "Cliente", "colaborador": "Equipe", "socio": "Equipe · sócio", "despesa": "Despesa fixa"}

    if pode("cadastros"):
        for f in estado.cadastros.listar():
            if casa(f.get("nome"), f.get("documento"), f.get("email"), f.get("telefone"), f.get("observacao")):
                itens.append({"tipo": "cadastro", "id": f["id"], "titulo": f["nome"], "cadastro_tipo": f.get("tipo", ""),
                              "caminho": "Cadastros › " + ROTULO_CAD.get(f.get("tipo", ""), "Cadastro"),
                              "detalhe": " · ".join(x for x in (f.get("documento"), f.get("email")) if x)})
                if sum(1 for i in itens if i["tipo"] == "cadastro") >= 6:
                    break
    if pode("servicos"):
        for s in estado.servicos.listar():
            if casa(s.get("nome"), s.get("cliente_nome"), s.get("descricao")):
                itens.append({"tipo": "servico", "id": s["id"], "titulo": s["nome"], "caminho": "Serviços",
                              "detalhe": " · ".join(x for x in (s.get("cliente_nome"), s.get("status_rotulo")) if x)})
                if sum(1 for i in itens if i["tipo"] == "servico") >= 6:
                    break
    if pode("acervo"):
        n = 0
        for d in estado.searcher.documents:
            if casa(d.name):
                pasta = Path(d.path).parent.name
                itens.append({"tipo": "documento", "id": d.name, "titulo": d.name, "caminho": "Acervo", "detalhe": pasta})
                n += 1
                if n >= 6:
                    break
    if pode("tarefas"):
        linhas = estado.base.buscar("SELECT id, titulo, prazo, concluida, servico_id, lista FROM tarefas WHERE titulo LIKE ? "
                                    "ORDER BY concluida, prazo LIMIT 20", (like,))
        n = 0
        for t in linhas:
            if servicos_acesso.visivel(t.get("servico_id")) and casa(t["titulo"]):
                itens.append({"tipo": "tarefa", "id": t["id"], "titulo": t["titulo"], "caminho": "Agenda › To-do",
                              "prazo": t.get("prazo") or "", "concluida": bool(t.get("concluida")),
                              "detalhe": " · ".join(x for x in (t.get("lista"), ("prazo " + t["prazo"]) if t.get("prazo") else "",
                                                                 "concluída" if t.get("concluida") else "") if x)})
                n += 1
                if n >= 6:
                    break
    if pode("gravacoes"):
        for g in estado.gravacoes.listar(termo=termo)[:6]:
            itens.append({"tipo": "gravacao", "id": g["id"], "titulo": g.get("titulo") or "Gravação", "caminho": "Gravações",
                          "detalhe": " · ".join(x for x in (g.get("cliente_nome"), g.get("servico_nome")) if x)})
    if pode("financeiro"):
        for l in estado.base.buscar("SELECT id, descricao, vencimento, tipo FROM lancamentos WHERE descricao LIKE ? "
                                    "ORDER BY vencimento DESC LIMIT 6", (like,)):
            itens.append({"tipo": "lancamento", "id": l["id"], "titulo": l["descricao"], "caminho": "Financeiro",
                          "detalhe": ("recebimento" if l.get("tipo") == "recebimento" else "despesa") +
                          (" · vence " + l["vencimento"] if l.get("vencimento") else "")})
    if ve is None:
        for p in estado.base.buscar("SELECT id, processo, tipo, tribunal, orgao, data FROM publicacoes WHERE processo LIKE ? "
                                    "OR orgao LIKE ? OR texto LIKE ? ORDER BY data DESC LIMIT 6", (like, like, like)):
            itens.append({"tipo": "publicacao", "id": p["id"], "titulo": (p.get("tipo") or "Publicação") + " · " + (p.get("processo") or ""),
                          "caminho": "Agenda › To-do › Publicações", "detalhe": " · ".join(x for x in (p.get("tribunal"), p.get("orgao")) if x)})
    return {"itens": itens}


# ------------------------------------------------------------------ saude
# A saude do PAULUS e o diagnostico para o suporte (src/saude.py, P2). So na
# janela do servidor.

def _itens_de_saude() -> list[dict]:
    import saude

    try:
        acesso = estado.acesso_de_fora.situacao()
    except Exception:  # noqa: BLE001
        acesso = {}
    vinculo = getattr(estado, "vinculo", None)
    return saude.verificar(
        dados=DADOS_DIR, modelo_ok=check_ollama(estado.client.model), backup=_prefs_backup(), acesso=acesso,
        sem_internet=vinculo.sem_internet() if vinculo is not None and vinculo.vinculado() else None,
        anuncio=_anuncio(), versao=VERSAO)


@app.get("/api/saude")
def saude_ver() -> dict:
    itens = _itens_de_saude()
    pior = "erro" if any(i["estado"] == "erro" for i in itens) else ("aviso" if any(i["estado"] == "aviso" for i in itens) else "ok")
    return {"itens": itens, "geral": pior}


@app.get("/api/saude/diagnostico")
def saude_diagnostico() -> Response:
    """O arquivo que o escritorio manda ao suporte: estado e erros, sem dado de cliente."""
    import saude

    p = estado.prefs.dados
    extras = {
        "Acesso de fora": "ligado" if (p.get("acesso_remoto") or {}).get("ligado") else "desligado",
        "Backup automático": "ligado" if (p.get("backup") or {}).get("automatico", True) else "desligado",
        "Documentos no Acervo": len(estado.searcher.documents),
        "Instalado": "sim" if os.environ.get("PAULUS_INSTALADO") else "não (código-fonte)",
    }
    texto = saude.diagnostico(_itens_de_saude(), versao=VERSAO, extras=extras)
    nome = "PAULUS-diagnostico-" + time.strftime("%Y%m%d-%H%M") + ".txt"
    return Response(texto.encode("utf-8"), media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})


class LigarMenu(BaseModel):
    ligado: bool


@app.get("/api/explorer")
def explorer_ver() -> dict:
    """"Perguntar ao PAULUS" no botao direito do Explorer (src/menu_explorer.py)."""
    import menu_explorer
    from acesso import energia

    return menu_explorer.estado(energia.exe_do_programa())


@app.post("/api/explorer")
def explorer_ligar(dados: LigarMenu) -> dict:
    import menu_explorer
    from acesso import energia

    exe = energia.exe_do_programa()
    if dados.ligado:
        if sys.platform != "win32" or not exe:
            raise HTTPException(status_code=400, detail="disponível no PAULUS instalado (o PAULUS.exe não foi encontrado)")
        menu_explorer.ligar(exe)
    elif sys.platform == "win32":
        menu_explorer.desligar()
    return menu_explorer.estado(exe)


@app.get("/api/avisos")
def avisos_ver() -> dict:
    """Se da para avisar no Windows, se a pessoa quer e em que horario."""
    d = estado.prefs.dados.get("disponibilidade") or {}
    nomes = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
    dias = sorted(d.get("dias") or [0, 1, 2, 3, 4])
    faixa = (f"{nomes[dias[0]]} a {nomes[dias[-1]]}" if dias == list(range(dias[0], dias[-1] + 1))
             else ", ".join(nomes[i] for i in dias))
    return {
        "disponivel": avisos.disponivel(),
        "ligado": estado.vigia.ligado(),
        "tipos": [{"chave": k, "rotulo": t["rotulo"], "explica": t["explica"], "so_fora": t["so_fora"]}
                  for k, t in avisos.TIPOS.items()],
        "horario": f"{faixa}, das {d.get('inicio') or '00:00'} às {d.get('fim') or '23:59'}",
    }


@app.post("/api/avisos/teste")
def avisos_teste() -> dict:
    """Um aviso de verdade, para a pessoa ver como chega - espera o Windows responder."""
    if not avisos.disponivel():
        raise HTTPException(status_code=400, detail="avisos do Windows só existem no Windows")
    ok = avisos.notificar("Avisos ligados", "É assim que os lembretes e o fim do ciclo de foco vão chegar.", esperar=True)
    return {"ok": ok}


@app.get("/api/bemestar/semana")
def bemestar_semana(ate: str = "") -> dict:
    """Uma semana qualquer, para comparar a atual com a anterior."""
    return estado.bem_estar.semana(ate)


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


@app.post("/api/bemestar/lembretes/restaurar")
def bemestar_restaurar_lembretes() -> dict:
    """Devolve a lista de fabrica para quem se perdeu editando."""
    quantos = estado.bem_estar.restaurar_lembretes()
    return {"lembretes": estado.bem_estar.lembretes(), "restaurados": quantos}


@app.post("/api/bemestar/lembretes/{id_}/feito")
def bemestar_marcar(id_: int) -> dict:
    if not estado.bem_estar.marcar_lembrete(id_):
        raise HTTPException(status_code=404, detail="lembrete não encontrado")
    return {"lembretes": estado.bem_estar.lembretes(), "hoje": estado.bem_estar.dia()}


@app.delete("/api/bemestar/lembretes/{id_}")
def bemestar_apagar_lembrete(id_: int) -> dict:
    estado.bem_estar.apagar_lembrete(id_)
    return {"lembretes": estado.bem_estar.lembretes()}


# ------------------------------------------------------------- servicos


class FichaServico(BaseModel):
    id: int | None = None
    dados: dict = {}


def _acesso_da_equipe() -> dict[int, str]:
    fora = estado.acesso_de_fora
    return servicos_acesso.acesso_da_equipe(estado.base, fora.contas, fora.convites)


@app.get("/api/servicos")
def servicos_listar(filtro: str = "", termo: str = "") -> dict:
    return {
        # Quem da equipe pode estar num servico: so quem entra no PAULUS
        # (conta ou convite em aberto), com o estado de cada um.
        "acesso_da_equipe": {str(k): v for k, v in _acesso_da_equipe().items()},
        "servicos": estado.servicos.listar(filtro, termo),
        "contagem": estado.servicos.contagem(),
        "status": [{"valor": k, "rotulo": v} for k, v in servicos_mod.STATUS.items()],
        "clientes": [{"id": f["id"], "nome": f["nome"], "tipo": f["tipo"], "observacao": f.get("observacao", "")}
                     for f in estado.cadastros.listar()],
    }


# Arquivos da pasta de um servico que o indice ja tentou ler e nao conseguiu
# (PDF escaneado, arquivo corrompido): caminho e data de modificacao. Sem
# isso, cada abertura da pasta mandaria reler o Acervo atras deles.
_TENTADOS_NA_PASTA: set[tuple[str, float]] = set()


def _chave_do_arquivo(p: Path) -> tuple[str, float]:
    try:
        return (os.path.normcase(str(p.resolve())), p.stat().st_mtime)
    except OSError:
        return (os.path.normcase(str(p)), 0.0)


def _documentos_por_caminho() -> dict:
    return {os.path.normcase(str(Path(d.path).resolve())): d for d in estado.searcher.documents}


def _sincronizar_pasta_do_servico(id_: int) -> Path | None:
    """
    O que esta na pasta do servico no disco entra no servico.

    Arquivo posto na pasta pelo Windows ainda nao foi lido: o Acervo e relido
    uma vez e o arquivo, ja com sha1, e ligado. Arquivo que alguem desligou
    de proposito nao volta sozinho.
    """
    pasta = estado.servicos.pasta_de(id_, criar=True)
    if not pasta or not pasta.is_dir():
        return pasta
    arquivos = [p for p in pasta.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES]
    if not arquivos:
        return pasta
    por_caminho = _documentos_por_caminho()
    novos = [p for p in arquivos
             if _chave_do_arquivo(p)[0] not in por_caminho and _chave_do_arquivo(p) not in _TENTADOS_NA_PASTA]
    if novos:
        estado.recarregar()
        por_caminho = _documentos_por_caminho()
        _TENTADOS_NA_PASTA.update(_chave_do_arquivo(p) for p in novos if _chave_do_arquivo(p)[0] not in por_caminho)
    ligados = {a["sha1"] for a in estado.servicos.arquivos_de(id_)}
    desligados = estado.servicos.desligados(id_)
    for p in arquivos:
        doc = por_caminho.get(_chave_do_arquivo(p)[0])
        if doc and doc.sha1 not in ligados and doc.sha1 not in desligados:
            estado.servicos.vincular(id_, doc.sha1, doc.name, "Pasta do serviço")
            ligados.add(doc.sha1)
    return pasta


@app.post("/api/servicos")
def servicos_salvar(payload: FichaServico) -> dict:
    sessao = equipe.pessoa_da_vez()
    if servicos_acesso.restrita(sessao):
        if payload.id and not servicos_acesso.visivel(payload.id):
            raise HTTPException(status_code=404, detail="serviço não encontrado")
        # Quem define a Equipe (os colaboradores) e o titular. De fora, o
        # colaborador mantem a que ja existe; o servico que ele cria nasce
        # com ele na Equipe - senao sumiria da tela dele ao salvar.
        dados = dict(payload.dados)
        if payload.id:
            atual = estado.base.um("SELECT equipe FROM servicos WHERE id = ?", (payload.id,)) or {}
            dados["equipe"] = json.loads(atual.get("equipe") or "[]")
        else:
            dados["equipe"] = sorted(servicos_acesso.cadastros_da_pessoa(
                estado.base, servicos_acesso.emails_da_pessoa(sessao, estado.acesso_de_fora.contas)))
        payload = FichaServico(id=payload.id, dados=dados)
    # A Equipe de um servico e de quem entra no PAULUS: a pessoa que so esta
    # em Cadastros (sem conta nem convite) nao entra - convide antes. Quem ja
    # estava fica, para salvar o resto do servico nao falhar por causa dela.
    if "equipe" in payload.dados:
        atual = set()
        if payload.id:
            linha = estado.base.um("SELECT equipe FROM servicos WHERE id = ?", (payload.id,)) or {}
            atual = servicos_acesso.participantes(linha.get("equipe"))
        pedidos = [int(x) for x in (payload.dados.get("equipe") or []) if str(x).isdigit()]
        com_acesso = _acesso_da_equipe()
        sem = [i for i in pedidos if i not in atual and i not in com_acesso]
        if sem:
            nomes = [l["nome"] for l in estado.base.buscar(
                f"SELECT nome FROM cadastros WHERE id IN ({','.join('?' for _ in sem)})", tuple(sem))]
            raise HTTPException(status_code=400, detail=(", ".join(nomes) or "essa pessoa") +
                                " não tem acesso ao PAULUS: convide em Cadastros › Equipe antes de pôr na equipe do serviço")
    antes = estado.servicos.pasta_de(payload.id, criar=False) if payload.id else None
    try:
        id_ = estado.servicos.salvar(payload.dados, payload.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Renomear o servico renomeou a pasta: os caminhos no indice e os dos
    # audios que moram nela mudaram.
    depois = estado.servicos.pasta_de(id_, criar=False)
    if antes and depois and antes != depois and depois.is_dir():
        estado.gravacoes.trocar_pasta(antes, depois)
        if any(depois.iterdir()):
            estado.recarregar()
    return servicos_obter(id_)


@app.get("/api/servicos/{id_}")
def servicos_obter(id_: int) -> dict:
    if not estado.base.um("SELECT id FROM servicos WHERE id = ?", (id_,)):
        raise HTTPException(status_code=404, detail="serviço não encontrado")
    pasta = _sincronizar_pasta_do_servico(id_)
    s = estado.servicos.obter(id_)
    if not s:
        raise HTTPException(status_code=404, detail="serviço não encontrado")
    s["gravacoes"] = [g for g in estado.gravacoes.listar() if g.get("servico_id") == id_]
    s["pasta_caminho"] = str(pasta) if pasta else ""
    return s


@app.delete("/api/servicos/{id_}")
def servicos_apagar(id_: int) -> dict:
    s = estado.servicos.obter(id_)
    if not s:
        raise HTTPException(status_code=404, detail="serviço não encontrado")
    pasta = estado.servicos.pasta_de(id_, criar=False)
    entrada = estado.lixeira.apagar_linha("servico", id_, s["nome"], "Serviços" + (" · " + s["cliente_nome"] if s.get("cliente_nome") else ""))
    # A pasta vazia sai; com arquivos, fica no Acervo - os arquivos sao do
    # escritorio, nao do servico.
    servicos_mod.remover_pasta_vazia(pasta)
    return _foi_para_lixeira(entrada, "apagado", id_)


class AnexarAoServico(BaseModel):
    caminhos: list[str]
    # Os acima de 50 MB que a pessoa confirmou na tela (src/entrada.py).
    autorizados: list[str] = []
    # Nome repetido: renomear ou substituir, por nome (src/nomes.py).
    decisoes: dict = {}


@app.post("/api/servicos/{id_}/anexar")
def servicos_anexar(id_: int, payload: AnexarAoServico) -> dict:
    """
    Adicionar arquivos ao servico: copia cada um para a pasta do servico no
    Acervo e liga a copia.

    Vale para o que vem do Acervo e do computador. O original fica onde
    estava; o que ja esta na pasta nao e copiado sobre si mesmo, e o mesmo
    conteudo com o mesmo nome nao vira "(2)".
    """
    pasta = estado.servicos.pasta_de(id_, criar=True)
    if not pasta:
        raise HTTPException(status_code=404, detail="serviço não encontrado")
    destinos: list[Path] = []
    recusados: list[dict] = []
    pedem: list[dict] = []
    liberados = {chave_do_caminho(c) for c in payload.autorizados}
    aceitos: list[Path] = []
    for bruto in payload.caminhos:
        origem = Path(bruto)
        nome = origem.name
        if not origem.is_file():
            recusados.append({"nome": nome or bruto, "motivo": "arquivo não encontrado"})
            continue
        if origem.suffix.lower() not in SUPPORTED_SUFFIXES:
            recusados.append({"nome": nome, "motivo": "formato não suportado"})
            continue
        try:
            decisao, motivo, pedido = _triagem_do_caminho(origem, liberados)
        except OSError as exc:
            recusados.append({"nome": nome, "motivo": f"não consegui ler: {exc.strerror or exc}"})
            continue
        if decisao == "perguntar":
            pedem.append(pedido)
        elif decisao == "recusar":
            recusados.append({"nome": nome, "motivo": motivo})
        else:
            aceitos.append(origem)
    # Nome repetido com outro conteudo: a tela pergunta antes de copiar.
    for origem, destino, copiar in _destinos_das_copias(aceitos, pasta, nomes_mod.do_pedido({"decisoes": payload.decisoes})):
        try:
            if copiar:
                shutil.copy2(origem, destino)
        except OSError as exc:
            recusados.append({"nome": origem.name, "motivo": f"não consegui copiar: {exc.strerror or exc}"})
            continue
        destinos.append(destino)
    if destinos:
        estado.recarregar()
    por_caminho = _documentos_por_caminho()
    ligados: list[str] = []
    for destino in destinos:
        doc = por_caminho.get(_chave_do_arquivo(destino)[0])
        if not doc:
            recusados.append({"nome": destino.name, "motivo": motivo_sem_texto(destino) or "não entrou no índice"})
            continue
        estado.servicos.vincular(id_, doc.sha1, doc.name)
        ligados.append(doc.name)
    return {"ligados": ligados, "recusados": recusados, "pedem_confirmacao": pedem, "pasta": str(pasta),
            "arquivos": estado.servicos.arquivos_de(id_)}


@app.post("/api/servicos/{id_}/status")
def servicos_status(id_: int, payload: dict) -> dict:
    try:
        estado.servicos.mudar_status(id_, str(payload.get("status", "")))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return estado.servicos.obter(id_) or {}


@app.post("/api/servicos/{id_}/etapas")
def servicos_etapa_nova(id_: int, payload: dict) -> dict:
    try:
        return {"etapas": estado.servicos.etapa_adicionar(id_, str(payload.get("titulo", "")), str(payload.get("quando", "")),
                                                          payload.get("responsavel_id"))}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/servicos/{id_}/etapas/{indice}/editar")
def servicos_etapa_editar(id_: int, indice: int, payload: dict) -> dict:
    """O prazo, o nome ou quem cuida de uma etapa - so o que vier no corpo."""
    try:
        return {"etapas": estado.servicos.etapa_editar(id_, indice, payload)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/servicos/{id_}/etapas/{indice}")
def servicos_etapa_alternar(id_: int, indice: int) -> dict:
    try:
        return {"etapas": estado.servicos.etapa_alternar(id_, indice, _quem_sou())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/servicos/{id_}/etapas/{indice}")
def servicos_etapa_remover(id_: int, indice: int) -> dict:
    try:
        return {"etapas": estado.servicos.etapa_remover(id_, indice)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/servicos/{id_}/anotacoes")
def servicos_anotar(id_: int, payload: dict) -> dict:
    try:
        return {"anotacoes": estado.servicos.anotar(id_, str(payload.get("texto", "")), _quem_sou())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/servicos/{id_}/anotacoes/{indice}")
def servicos_anotacao_editar(id_: int, indice: int, payload: dict) -> dict:
    try:
        return {"anotacoes": estado.servicos.anotacao_editar(id_, indice, str(payload.get("texto", "")), _quem_sou())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/servicos/{id_}/anotacoes/{indice}")
def servicos_anotacao_remover(id_: int, indice: int) -> dict:
    try:
        return {"anotacoes": estado.servicos.anotacao_remover(id_, indice)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/servicos/{id_}/prazos/{origem}/{item_id}")
def servicos_prazo_editar(id_: int, origem: str, item_id: int, payload: dict) -> dict:
    """
    Trocar o titulo, a data ou a hora de um prazo da pasta, sem mexer no
    resto da ficha. O compromisso e a tarefa sao gravados inteiros (a Agenda
    e Tarefas regravam todos os campos): aqui a ficha atual e lida e so o que
    veio no corpo muda.
    """
    if not estado.servicos.obter(id_):
        raise HTTPException(status_code=404, detail="serviço não encontrado")
    titulo = " ".join(str(payload.get("titulo", "")).split()) if "titulo" in payload else None
    if titulo == "":
        raise HTTPException(status_code=400, detail="o prazo precisa de um título")
    try:
        if origem == "compromisso":
            atual = estado.agenda.obter(item_id)
            if not atual:
                raise HTTPException(status_code=404, detail="compromisso não encontrado")
            dados = {c: atual.get(c) for c in CAMPOS_AGENDA}
            if titulo is not None:
                dados["titulo"] = titulo
            if payload.get("data"):
                dados["data"] = servicos_mod.data_de_prazo(str(payload["data"])) or dados["data"]
            if payload.get("hora"):
                dados["hora"] = str(payload["hora"])[:5]
            estado.agenda.salvar(dados, item_id)
        elif origem == "tarefa":
            atual = estado.tarefas.obter(item_id)
            if not atual:
                raise HTTPException(status_code=404, detail="tarefa não encontrada")
            dados = {c: atual.get(c) for c in tarefas_mod.CAMPOS}
            if titulo is not None:
                dados["titulo"] = titulo
            if payload.get("data"):
                dados["prazo"] = servicos_mod.data_de_prazo(str(payload["data"])) or dados["prazo"]
            estado.tarefas.salvar(dados, item_id)
        else:
            raise HTTPException(status_code=400, detail="prazo desconhecido")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"prazos": (estado.servicos.obter(id_) or {}).get("prazos", [])}


@app.post("/api/servicos/{id_}/vincular")
def servicos_vincular(id_: int, payload: VinculoDoc) -> dict:
    if not estado.servicos.obter(id_):
        raise HTTPException(status_code=404, detail="serviço não encontrado")
    estado.servicos.vincular(id_, payload.sha1, payload.nome)
    return {"arquivos": estado.servicos.arquivos_de(id_)}


@app.delete("/api/servicos/{id_}/vinculos/{sha1}")
def servicos_desvincular(id_: int, sha1: str) -> dict:
    estado.servicos.desvincular(id_, sha1)
    return {"arquivos": estado.servicos.arquivos_de(id_)}


@app.post("/api/servicos/{id_}/resumo")
def servicos_resumo(id_: int) -> dict:
    """
    O resumo do servico, escrito pelo modelo sobre o que esta gravado.

    O modelo recebe o servico inteiro em texto - etapas, prazos, anotacoes,
    nomes dos arquivos - e escreve sobre isso. Nao le os arquivos aqui: isso
    e a conversa do Assistente, que tem o Acervo.
    """
    s = estado.servicos.obter(id_)
    if not s:
        raise HTTPException(status_code=404, detail="serviço não encontrado")
    disponivel, motivo = check_ollama(estado.client.model)
    if not disponivel:
        raise HTTPException(status_code=503, detail=motivo)
    try:
        texto = estado.cliente_para("resumos").ask(servicos_mod.INSTRUCAO_RESUMO, estado.servicos.texto_para_resumo(s))
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    estado.servicos.guardar_resumo(id_, _limpar_sugestao(texto))
    return estado.servicos.obter(id_) or {}


@app.post("/api/servicos/{id_}/conversar")
def servicos_conversar(id_: int, payload: dict, request: Request = None) -> dict:
    """
    Conversar sobre a pasta, da caixa de pedido dela.

    O modelo recebe o que esta gravado no servico - e as ultimas perguntas,
    para a conversa continuar -, responde, e a pergunta com a resposta entram
    no historico da pasta. Como o resumo, nao le os arquivos: isso e a
    conversa do Assistente, que tem o Acervo.

    Entra na mesma fila do modelo que a conversa do Assistente: e o mesmo
    modelo, e a vez e uma so.
    """
    pergunta = " ".join(str(payload.get("pergunta", "")).split())
    if not pergunta:
        raise HTTPException(status_code=400, detail="escreva a pergunta")
    s = estado.servicos.obter(id_)
    if not s:
        raise HTTPException(status_code=404, detail="serviço não encontrado")
    disponivel, motivo = check_ollama(estado.client.model)
    if not disponivel:
        raise HTTPException(status_code=503, detail=motivo)
    try:
        vez = estado.fila_modelo.entrar(_dono_da_vez(request), rotulo=s.get("titulo", "") if isinstance(s, dict) else "")
    except FilaCheia as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    try:
        if not estado.fila_modelo.esperar(vez, timeout=600):
            raise HTTPException(status_code=503, detail="o modelo ficou ocupado demais; tente de novo")
        resposta = estado.cliente_para("resumos").ask(servicos_mod.INSTRUCAO_CONVERSA + f"\n\nPergunta: {pergunta}",
                                     estado.servicos.texto_para_conversa(s))
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        estado.fila_modelo.sair(vez)
    estado.servicos.conversar(id_, pergunta, _limpar_sugestao(resposta), _quem_sou())
    return estado.servicos.obter(id_) or {}


# ------------------------------------------------------------------ voz


def _situacao_da_voz() -> dict:
    s = estado.transcritor.situacao()
    s["fila"] = list(estado.fila_voz.queue)
    s["transcrevendo"] = estado.transcrevendo
    s["erro"] = estado.erro_voz
    return s


@app.get("/api/voz")
def voz_situacao() -> dict:
    return _situacao_da_voz()


@app.post("/api/voz/baixar")
def voz_baixar(payload: dict) -> dict:
    """Baixa o modelo de voz em segundo plano. Uma vez, com internet; depois nunca mais."""
    nome = str(payload.get("modelo") or estado.transcritor.modelo)
    if nome not in transcricao_mod.MODELOS:
        raise HTTPException(status_code=400, detail="modelo de voz desconhecido")
    if estado.transcritor.baixando:
        return _situacao_da_voz()
    if estado.transcritor.instalado(nome):
        return _situacao_da_voz()

    def baixar() -> None:
        estado.erro_voz = ""
        try:
            estado.transcritor.baixar(nome)
        except Exception as exc:  # noqa: BLE001 - o erro vai para a tela
            estado.erro_voz = "não consegui baixar: " + str(exc)[:200]

    estado.transcritor.baixando = nome
    threading.Thread(target=baixar, name="baixar-voz", daemon=True).start()
    return _situacao_da_voz()


@app.post("/api/voz/modelo")
def voz_modelo(payload: dict) -> dict:
    nome = str(payload.get("modelo") or "")
    try:
        estado.transcritor.escolher(nome)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    estado.prefs.atualizar({"voz": {"modelo": nome}})
    return _situacao_da_voz()


def _purgar_sessoes() -> None:
    """Sessao sem audio ha 15 minutos e uma gravacao que nao voltou: some."""
    agora = time.time()
    for sid in [s for s, v in estado.ao_vivo.items() if agora - v.ultima > 900]:
        estado.ao_vivo.pop(sid, None)


def _sessao_viva(sid: str) -> transcricao_mod.SessaoAoVivo:
    s = estado.ao_vivo.get(sid)
    if not s:
        raise HTTPException(status_code=404, detail="sessão de transcrição não encontrada")
    return s


@app.post("/api/voz/ao-vivo")
def voz_ao_vivo_abrir(payload: dict | None = None) -> dict:
    """Abre uma sessao para transcrever enquanto grava. O audio vem em pedacos por /audio."""
    _purgar_sessoes()
    if not estado.transcritor.instalado():
        raise HTTPException(status_code=503, detail="o modelo de voz não está baixado nesta máquina")
    sessao = transcricao_mod.SessaoAoVivo(uuid.uuid4().hex, estado.transcritor.modelo)
    estado.ao_vivo[sessao.id] = sessao
    s = sessao.situacao()
    s["rotulo"] = transcricao_mod.MODELOS[sessao.modelo]["rotulo"]
    return s


@app.post("/api/voz/ao-vivo/{sid}/audio")
async def voz_ao_vivo_audio(sid: str, request: Request) -> dict:
    """Um pedaco de audio (PCM 16 kHz, 16 bits, mono). Devolve os trechos novos, se houve pausa para transcrever."""
    sessao = _sessao_viva(sid)
    if sessao.fechada:
        raise HTTPException(status_code=409, detail="a sessão já foi encerrada")
    pcm = await request.body()
    if len(pcm) < 2:
        return {"trechos": [], **sessao.situacao()}
    try:
        novos = await run_in_threadpool(estado.transcritor.ao_vivo_receber, sessao, pcm[: len(pcm) - len(pcm) % 2])
    except transcricao_mod.SemMemoria as exc:
        # A frase inteira: a tela a reconhece e oferece o modelo mais leve.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - o erro vai para a tela, a sessao continua
        raise HTTPException(status_code=500, detail="a transcrição falhou neste pedaço: " + str(exc)[:200]) from exc
    return {"trechos": novos, **sessao.situacao()}


@app.post("/api/voz/ao-vivo/{sid}/fim")
async def voz_ao_vivo_fim(sid: str) -> dict:
    """A gravacao parou: transcreve o que sobrou e devolve tudo. A sessao fica ate a gravacao ser arquivada."""
    sessao = _sessao_viva(sid)
    # Como no pedaco: o erro vira frase (sem memoria, "mkl_malloc: failed to
    # allocate memory"), e nao um 500 sem corpo que a tela nao sabe ler.
    try:
        await run_in_threadpool(estado.transcritor.ao_vivo_fim, sessao)
    except transcricao_mod.SemMemoria as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - o motivo vai para a tela
        raise HTTPException(status_code=500, detail=f"a transcrição falhou no fim da gravação: {exc}") from exc
    return {"trechos": sessao.trechos, **sessao.situacao()}


@app.delete("/api/voz/ao-vivo/{sid}")
def voz_ao_vivo_descartar(sid: str) -> dict:
    sessao = estado.ao_vivo.pop(sid, None)
    if sessao:
        sessao.fechada = True
    return {"descartada": sid}


# ------------------------------------------------------------ gravacoes


def _com_progresso(g: dict) -> dict:
    if g.get("transcricao_estado") == "transcrevendo":
        g["progresso"] = round(estado.progresso_voz.get(int(g["id"]), 0.0), 3)
    elif g.get("transcricao_estado") == "fila":
        fila = list(estado.fila_voz.queue)
        g["posicao_na_fila"] = (fila.index(int(g["id"])) + 1) if int(g["id"]) in fila else 0
    return g


@app.get("/api/gravacoes")
def gravacoes_listar(tipo: str = "", termo: str = "") -> dict:
    return {
        "gravacoes": [_com_progresso(g) for g in estado.gravacoes.listar(tipo, termo)],
        "total_segundos": estado.gravacoes.total_segundos(),
        "tipos": [{"valor": k, "rotulo": v} for k, v in gravacoes_mod.TIPOS.items()],
        "clientes": [{"id": f["id"], "nome": f["nome"]} for f in estado.cadastros.listar("cliente")],
        "servicos": [{"id": s["id"], "nome": s["nome"]} for s in estado.servicos.listar("andamento")],
        "pessoas": _pessoas_para_gravacao(),
        "pasta": str(GRAVACOES_DIR),
    }


def _pessoas_para_gravacao() -> list[dict]:
    """
    Os nomes que o campo Participantes sugere: as fichas de Cadastros (equipe,
    clientes, fornecedores) e quem ja participou de outra gravacao. Nome
    repetido aparece uma vez, com o que se sabe dele.
    """
    rotulos = {"colaborador": "equipe", "socio": "sócio", "cliente": "cliente"}
    vistos: dict[str, dict] = {}
    for f in estado.cadastros.listar():
        nome = " ".join(str(f.get("nome", "")).split())
        if nome and nome.casefold() not in vistos:
            vistos[nome.casefold()] = {"nome": nome, "detalhe": f.get("observacao") or rotulos.get(f.get("tipo", ""), f.get("tipo", ""))}
    for g in estado.gravacoes.listar():
        for nome in g.get("participantes_lista", []):
            if nome.casefold() not in vistos:
                vistos[nome.casefold()] = {"nome": nome, "detalhe": "participou de uma gravação"}
    return sorted(vistos.values(), key=lambda p: p["nome"].casefold())


@app.post("/api/gravacoes")
async def gravacoes_guardar(
    arquivo: UploadFile,
    titulo: str = Form(""), tipo: str = Form("reuniao"), cadastro_id: str = Form(""),
    servico_id: str = Form(""), participantes: str = Form(""), duracao_s: str = Form("0"),
    origem: str = Form("gravada"), marcadores: str = Form("[]"), transcrever: str = Form("1"),
    sessao: str = Form(""), request: Request = None,
) -> dict:
    """O audio entra por aqui, gravado no navegador ou importado de um arquivo."""
    conteudo = await arquivo.read()
    if not conteudo:
        raise HTTPException(status_code=400, detail="o áudio veio vazio")
    if len(conteudo) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=400, detail="áudio maior que 500 MB")
    try:
        lista = json.loads(marcadores or "[]")
    except json.JSONDecodeError:
        lista = []
    try:
        id_ = estado.gravacoes.guardar({
            "titulo": titulo, "tipo": tipo, "cadastro_id": int(cadastro_id) if cadastro_id.isdigit() else None,
            "servico_id": int(servico_id) if servico_id.isdigit() else None, "participantes": participantes,
            "duracao_s": int(duracao_s) if duracao_s.isdigit() else 0, "origem": origem, "marcadores": lista,
        }, conteudo, arquivo.filename or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    equipe.marcar_autor(estado.base, "gravacoes", id_, equipe.quem(request, estado.prefs.dados))
    g = estado.gravacoes.obter(id_) or {}
    if g.get("servico_id"):
        # Gravada ja ligada a um servico: o audio vai para a pasta dele.
        _mover_audio_da_gravacao(id_, int(g["servico_id"]))
        estado.servicos.trilha(int(g["servico_id"]), "Gravação arquivada: " + g["titulo"])
        g = estado.gravacoes.obter(id_) or g
    viva = estado.ao_vivo.pop(sessao, None) if sessao else None
    if viva is not None:
        # O que foi transcrito enquanto gravava ja serve; fecha o que sobrou.
        await run_in_threadpool(estado.transcritor.ao_vivo_fim, viva)
    if viva is not None and viva.trechos:
        estado.gravacoes.marcar_transcricao(id_, "pronta", trechos=viva.trechos, modelo=viva.modelo + " ao vivo", tempo=0.0)
        g = estado.gravacoes.obter(id_) or g
    elif estado.transcritor.instalado() and transcrever == "1":
        estado.gravacoes.marcar_transcricao(id_, "fila")
        estado.fila_voz.put(id_)
        g = estado.gravacoes.obter(id_) or g
    return _com_progresso(g)


@app.get("/api/gravacoes/{id_}")
def gravacoes_obter(id_: int) -> dict:
    g = estado.gravacoes.obter(id_)
    if not g:
        raise HTTPException(status_code=404, detail="gravação não encontrada")
    return _com_progresso(g)


@app.post("/api/gravacoes/{id_}/transcrever")
def gravacoes_transcrever(id_: int) -> dict:
    """Poe a gravacao na fila do Whisper. Volta na hora; a tela acompanha pelo estado."""
    g = estado.gravacoes.obter(id_)
    if not g:
        raise HTTPException(status_code=404, detail="gravação não encontrada")
    if not g["existe"]:
        raise HTTPException(status_code=404, detail="o áudio não está mais no disco")
    if not estado.transcritor.instalado():
        raise HTTPException(status_code=503, detail="o modelo de voz não está baixado nesta máquina")
    if g["transcricao_estado"] in ("fila", "transcrevendo"):
        return _com_progresso(g)
    estado.gravacoes.marcar_transcricao(id_, "fila")
    estado.fila_voz.put(id_)
    return _com_progresso(estado.gravacoes.obter(id_) or {})


@app.post("/api/gravacoes/{id_}/resumo")
def gravacoes_resumo(id_: int) -> dict:
    """
    O resumo da gravacao, escrito pelo modelo local sobre a transcricao.

    Uma reuniao de uma hora nao cabe na janela do modelo: o texto e cortado
    em blocos, cada bloco ganha um resumo parcial e os parciais viram um so.
    Demora alguns minutos em CPU; a tela avisa.
    """
    g = estado.gravacoes.obter(id_)
    if not g:
        raise HTTPException(status_code=404, detail="gravação não encontrada")
    if not g.get("trechos"):
        raise HTTPException(status_code=400, detail="a gravação ainda não foi transcrita")
    disponivel, motivo = check_ollama(estado.client.model)
    if not disponivel:
        raise HTTPException(status_code=503, detail=motivo)
    texto = estado.gravacoes.texto_da_transcricao(id_)
    try:
        resumo = _resumir_em_blocos(texto)
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    estado.gravacoes.guardar_resumo(id_, resumo)
    if g.get("servico_id"):
        estado.servicos.trilha(int(g["servico_id"]), "Resumo da gravação: " + g["titulo"], "Assistente")
    return _com_progresso(estado.gravacoes.obter(id_) or {})


def _resumir_em_blocos(texto: str, tamanho: int = 9000) -> str:
    if len(texto) <= tamanho:
        return _limpar_sugestao(estado.cliente_para("resumos").ask(gravacoes_mod.INSTRUCAO_RESUMO, texto))
    linhas = texto.split("\n")
    blocos, atual = [], ""
    for linha in linhas:
        if len(atual) + len(linha) + 1 > tamanho and atual:
            blocos.append(atual)
            atual = ""
        atual += linha + "\n"
    if atual:
        blocos.append(atual)
    parciais = [
        f"Parte {i + 1} de {len(blocos)}:\n" + _limpar_sugestao(estado.cliente_para("resumos").ask(gravacoes_mod.INSTRUCAO_RESUMO, bloco))
        for i, bloco in enumerate(blocos)
    ]
    return _limpar_sugestao(estado.cliente_para("resumos").ask(gravacoes_mod.INSTRUCAO_JUNTAR, "\n\n".join(parciais)))


def _mover_audio_da_gravacao(id_: int, servico_id: int | None) -> None:
    """
    Ligar a gravacao a um servico leva o audio para a pasta do servico no
    Acervo; desligar traz de volta para a pasta das gravacoes.
    """
    pasta = estado.servicos.pasta_de(servico_id, criar=True) if servico_id else None
    try:
        estado.gravacoes.mover_para(id_, pasta)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"não consegui mover o áudio: {exc}") from exc


@app.post("/api/gravacoes/{id_}")
def gravacoes_atualizar(id_: int, payload: dict) -> dict:
    antes = estado.gravacoes.obter(id_)
    if not antes or not estado.gravacoes.atualizar(id_, payload):
        raise HTTPException(status_code=404, detail="gravação não encontrada")
    depois = estado.gravacoes.obter(id_) or {}
    if (antes.get("servico_id") or None) != (depois.get("servico_id") or None):
        _mover_audio_da_gravacao(id_, depois.get("servico_id"))
        if depois.get("servico_id"):
            estado.servicos.trilha(int(depois["servico_id"]), "Gravação ligada: " + depois["titulo"])
        depois = estado.gravacoes.obter(id_) or depois
    return depois


@app.post("/api/gravacoes/{id_}/anotacoes")
def gravacoes_anotar(id_: int, payload: dict) -> dict:
    try:
        return {"anotacoes": estado.gravacoes.anotar(id_, str(payload.get("texto", "")), _quem_sou())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/gravacoes/{id_}/anotacoes/{indice}")
def gravacoes_anotacao_editar(id_: int, indice: int, payload: dict) -> dict:
    try:
        return {"anotacoes": estado.gravacoes.anotacao_editar(id_, indice, str(payload.get("texto", "")), _quem_sou())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/gravacoes/{id_}/anotacoes/{indice}")
def gravacoes_anotacao_remover(id_: int, indice: int) -> dict:
    try:
        return {"anotacoes": estado.gravacoes.anotacao_remover(id_, indice)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/gravacoes/{id_}")
def gravacoes_apagar(id_: int) -> dict:
    g = estado.gravacoes.obter(id_)
    if not g:
        raise HTTPException(status_code=404, detail="gravação não encontrada")
    caminho = estado.gravacoes.caminho(id_)
    entrada = estado.lixeira.apagar_linha("gravacao", id_, g["titulo"], "Gravações · " + g["tipo_rotulo"] + " · " + g["duracao_texto"],
                                          arquivos=[str(caminho)] if caminho else [])
    return _foi_para_lixeira(entrada, "apagada", id_)


def _nome_para_baixar(id_: int, caminho: Path) -> str:
    g = estado.gravacoes.obter(id_) or {}
    titulo = re.sub(r'[\\/:*?"<>|]+', "-", str(g.get("titulo") or caminho.stem)).strip() or caminho.stem
    return titulo + caminho.suffix.lower()


@app.get("/api/gravacoes/{id_}/audio")
def gravacoes_audio(id_: int, baixar: int = 0) -> FileResponse:
    caminho = estado.gravacoes.caminho(id_)
    if not caminho:
        raise HTTPException(status_code=404, detail="o áudio não está mais no disco")
    tipo = gravacoes_mod.MEDIA_TYPES.get(caminho.suffix.lower(), "application/octet-stream")
    if baixar:
        return FileResponse(caminho, media_type=tipo, filename=_nome_para_baixar(id_, caminho))
    return FileResponse(caminho, media_type=tipo)


@app.post("/api/gravacoes/{id_}/audio/salvar")
def gravacoes_audio_salvar(id_: int, payload: dict) -> dict:
    """Baixar o audio na janela do programa: o "Salvar como" do Windows escolhe onde, e aqui o arquivo e copiado."""
    caminho = estado.gravacoes.caminho(id_)
    if not caminho:
        raise HTTPException(status_code=404, detail="o áudio não está mais no disco")
    destino = Path(str(payload.get("caminho", "")))
    if not destino.name:
        raise HTTPException(status_code=400, detail="escolha onde salvar")
    if not destino.suffix:
        destino = destino.with_suffix(caminho.suffix)
    try:
        shutil.copy2(caminho, destino)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"não consegui salvar: {exc.strerror or exc}") from exc
    return {"nome": destino.name, "caminho": str(destino)}


@app.get("/api/gravacoes/{id_}/audio/nome")
def gravacoes_audio_nome(id_: int) -> dict:
    caminho = estado.gravacoes.caminho(id_)
    if not caminho:
        raise HTTPException(status_code=404, detail="o áudio não está mais no disco")
    return {"nome": _nome_para_baixar(id_, caminho)}


@app.post("/api/gravacoes/{id_}/corrigir")
def gravacoes_corrigir(id_: int, payload: dict) -> dict:
    try:
        trocados = estado.gravacoes.corrigir(id_, str(payload.get("de", "")), str(payload.get("para", "")))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    g = estado.gravacoes.obter(id_) or {}
    g["trocados"] = trocados
    return _com_progresso(g)


def _docx_da_gravacao(id_: int) -> tuple[str, bytes]:
    try:
        titulo, html = estado.gravacoes.html_para_exportar(id_)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return titulo, _docx_com_pavlvs(documento.para_docx(documento.ler_html(html), titulo))


@app.get("/api/gravacoes/{id_}/transcricao.docx")
def gravacoes_docx(id_: int):
    """A transcricao (com o resumo e as notas) em Word, para continuar fora do PAULUS."""
    from fastapi.responses import Response

    titulo, dados = _docx_da_gravacao(id_)
    return Response(dados, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers=_anexo(_arquivo(titulo) + " - transcricao.docx"))


@app.post("/api/gravacoes/{id_}/exportar")
def gravacoes_exportar(id_: int, payload: dict | None = None) -> dict:
    """
    Grava o .docx da transcricao no Acervo (Gravacoes) e devolve o caminho: e
    o que vai anexo no e-mail - e fica para ser lido e perguntado depois. A
    transcricao que ja esta la nao e trocada sem a pessoa decidir (src/nomes.py).
    """
    titulo, dados = _docx_da_gravacao(id_)
    pendentes: list[dict] = []
    caminho = nomes_mod.destino(_pasta_no_acervo("Gravações"), _arquivo(titulo) + " - transcricao.docx",
                                nomes_mod.do_pedido(payload or {}), pendentes)
    nomes_mod.conferir(pendentes)
    caminho.write_bytes(dados)
    estado.recarregar_em_segundo_plano()
    return {"path": str(caminho), "nome": caminho.name, "mb": round(len(dados) / (1024 * 1024), 2)}


@app.post("/api/gravacoes/{id_}/marcadores")
def gravacoes_marcar(id_: int, payload: dict) -> dict:
    try:
        return {"marcadores": estado.gravacoes.marcar(id_, int(payload.get("t") or 0), str(payload.get("texto", "")))}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/gravacoes/{id_}/marcadores/{indice}")
def gravacoes_tirar_marcador(id_: int, indice: int) -> dict:
    try:
        return {"marcadores": estado.gravacoes.tirar_marcador(id_, indice)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# -------------------------------------------------------------- lixeira


def _foi_para_lixeira(entrada: dict | None, chave: str, id_) -> dict:
    """A resposta de um DELETE: o que saiu e o numero na lixeira, para o Desfazer do aviso."""
    if not entrada:
        raise HTTPException(status_code=404, detail="não encontrado")
    return {chave: id_, "lixeira": entrada["id"], "titulo": entrada["titulo"],
            "aviso": entrada["tipo_rotulo"] + " “" + entrada["titulo"] + "” foi para a lixeira · fica " + str(lixeira_mod.DIAS) + " dias"}


@app.get("/api/lixeira")
def lixeira_listar() -> dict:
    estado.lixeira.esvaziar_vencidos()
    itens = estado.lixeira.listar()
    return {"itens": itens, "total": len(itens), "dias": lixeira_mod.DIAS, "pasta": str(LIXEIRA_DIR)}


@app.post("/api/lixeira/esvaziar")
def lixeira_esvaziar() -> dict:
    return {"apagados": estado.lixeira.esvaziar()}


@app.post("/api/lixeira/{id_}/restaurar")
def lixeira_restaurar(id_: int) -> dict:
    try:
        e = estado.lixeira.restaurar(id_)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if e["tipo"] == "conversa":
        estado.trabalhos.recarregar_um(e["alvo_id"])
    return {"restaurado": e["alvo_id"], "tipo": e["tipo"], "titulo": e["titulo"],
            "aviso": e["tipo_rotulo"] + " “" + e["titulo"] + "” voltou"}


@app.delete("/api/lixeira/{id_}")
def lixeira_tirar(id_: int) -> dict:
    if not estado.lixeira.tirar(id_):
        raise HTTPException(status_code=404, detail="essa entrada não está na lixeira")
    return {"apagado_de_vez": id_}


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
            "“Baixar do Planalto” traz o texto compilado oficial, com as alterações já "
            "incorporadas: só a página da lei é pedida, nada desta máquina vai junto. Sem "
            "internet, abra a página do código no Planalto em outro computador, salve como "
            "“Página da Web, completa” e escolha o arquivo aqui."
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
    estado.client = estado.novo_cliente(args.model)

    # Sem a janela, quem abre e o navegador: o endereco leva a chave desta
    # execucao, como o Jupyter faz, e so vale uma vez (src/acesso/chave.py).
    print(f"\n  Abra no navegador: http://127.0.0.1:{args.port}/entrar-local?chave={estado.acesso.chave}")
    # host fixo em 127.0.0.1: o servidor nao deve ficar exposto na rede local,
    # os documentos sao de cliente.
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
