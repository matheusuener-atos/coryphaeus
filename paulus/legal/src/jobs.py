"""
PAULUS - Trabalhos (conversas).

Ate aqui o programa tinha um estado global unico: uma pasta, um indice, uma
conversa. Isso nao sustenta a tela da orquestradora, onde a pessoa toca varias
coisas ao mesmo tempo e volta no que ficou pela metade.

Um Trabalho e uma conversa com historico proprio, etapas visiveis, registro de
atividade e, quando for o caso, um pedido de aprovacao pendente. Cada um vive
num arquivo JSON: o programa fecha e o trabalho continua ali.
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

# Estados do manual (secao 6). "falhou" tambem usa cartao ambar, nunca vermelho.
EXECUTANDO = "executando"
AGUARDANDO = "aguardando"      # precisa de voce
NA_FILA = "na_fila"
CONCLUIDO = "concluido"
PAUSADO = "pausado"
FALHOU = "falhou"

ABERTOS = {EXECUTANDO, AGUARDANDO, NA_FILA, PAUSADO}


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class Mensagem:
    autor: str            # "pessoa" | "paulus"
    texto: str
    em: str = field(default_factory=agora)
    fontes: list[dict] = field(default_factory=list)
    cobertura: dict = field(default_factory=dict)
    segundos: float = 0.0


@dataclass
class Etapa:
    titulo: str
    estado: str = NA_FILA          # na_fila | executando | concluido | falhou
    feitos: int = 0
    total: int = 0
    detalhe: str = ""


@dataclass
class Atividade:
    texto: str
    em: str = field(default_factory=agora)


@dataclass
class Aprovacao:
    """Pedido que espera decisao humana. Nada externo acontece sem passar aqui."""

    pergunta: str
    acao: str                       # identificador que o backend sabe executar
    dados: dict = field(default_factory=dict)
    detalhe: str = ""


@dataclass
class Trabalho:
    id: str
    titulo: str
    tipo: str = "conversa"          # conversa | organizacao
    estado: str = CONCLUIDO
    criado_em: str = field(default_factory=agora)
    atualizado_em: str = field(default_factory=agora)
    mensagens: list[Mensagem] = field(default_factory=list)
    etapas: list[Etapa] = field(default_factory=list)
    atividade: list[Atividade] = field(default_factory=list)
    aprovacao: Aprovacao | None = None
    contexto: dict = field(default_factory=dict)   # estado interno do tipo de trabalho

    # ---------------------------------------------------------------- ajudas

    @property
    def aberto(self) -> bool:
        return self.estado in ABERTOS

    @property
    def progresso(self) -> int | None:
        """Percentual do trabalho inteiro, para a coluna da esquerda."""
        if not self.etapas:
            return None
        total = len(self.etapas)
        feitas = sum(1 for e in self.etapas if e.estado == CONCLUIDO)
        atual = next((e for e in self.etapas if e.estado == EXECUTANDO), None)
        parcial = (atual.feitos / atual.total) if atual and atual.total else 0.0
        return int(((feitas + parcial) / total) * 100)

    @property
    def etapa_atual(self) -> int:
        for i, etapa in enumerate(self.etapas, start=1):
            if etapa.estado in (EXECUTANDO, NA_FILA):
                return i
        return len(self.etapas)

    def registrar(self, texto: str, *, limite: int = 40) -> None:
        self.atividade.insert(0, Atividade(texto))
        del self.atividade[limite:]
        self.atualizado_em = agora()

    def dizer(self, autor: str, texto: str, **extras) -> Mensagem:
        msg = Mensagem(autor=autor, texto=texto, **extras)
        self.mensagens.append(msg)
        self.atualizado_em = agora()
        return msg

    def to_dict(self) -> dict:
        dados = asdict(self)
        dados["progresso"] = self.progresso
        dados["etapa_atual"] = self.etapa_atual
        dados["aberto"] = self.aberto
        return dados

    def resumo(self) -> dict:
        """Versao curta para a lista da coluna esquerda."""
        return {
            "id": self.id,
            "titulo": self.titulo,
            "tipo": self.tipo,
            "estado": self.estado,
            "progresso": self.progresso,
            "aberto": self.aberto,
            "atualizado_em": self.atualizado_em,
            "pendencias": 1 if self.aprovacao else 0,
        }


# --------------------------------------------------------------------------
# Titulo a partir do que a pessoa pediu
# --------------------------------------------------------------------------


def titular(pedido: str, limite: int = 46) -> str:
    """
    Nome curto do trabalho, tirado da propria frase da pessoa.

    A coluna da esquerda tem 230 px: "Quais contratos da pasta Juridico vencem
    este trimestre?" nao cabe e nao ajuda. "Contratos que vencem" cabe.
    """
    texto = " ".join(pedido.split())
    texto = re.sub(
        r"^(me\s+)?(diga|fale|mostre|liste|quais|qual|quem|quando|onde|como|por que|porque|o que)\s+",
        "",
        texto,
        flags=re.IGNORECASE,
    )
    # Tirar so a palavra interrogativa deixa o verbo orfao: "Quais sao as
    # clausulas" viraria "Sao as clausulas". O verbo de ligacao vai junto.
    texto = re.sub(
        r"^(sao|são|é|e|eh|foi|foram|esta|está|estao|estão|ha|há|tem)\s+(os\s+|as\s+|o\s+|a\s+)?",
        "",
        texto,
        flags=re.IGNORECASE,
    )
    texto = texto.rstrip("?!. ")
    if not texto:
        return "Nova conversa"

    if len(texto) > limite:
        texto = texto[:limite].rsplit(" ", 1)[0].rstrip(",;:") or texto[:limite]
    return texto[0].upper() + texto[1:]


# --------------------------------------------------------------------------
# Deposito em disco
# --------------------------------------------------------------------------


class Trabalhos:
    """Colecao de trabalhos, persistida em JSON (um arquivo por trabalho)."""

    def __init__(self, pasta: Path) -> None:
        self.pasta = Path(pasta)
        self.pasta.mkdir(parents=True, exist_ok=True)
        self._itens: dict[str, Trabalho] = {}
        self._trava = threading.Lock()
        self._carregar()

    # ---------------------------------------------------------------- disco

    def _caminho(self, id_: str) -> Path:
        return self.pasta / f"{id_}.json"

    def _carregar(self) -> None:
        for arquivo in self.pasta.glob("*.json"):
            try:
                bruto = json.loads(arquivo.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            trabalho = _de_dict(bruto)
            if trabalho:
                # Trabalho que ficou "executando" quando o programa fechou nao
                # esta executando coisa nenhuma agora.
                if trabalho.estado == EXECUTANDO:
                    trabalho.estado = PAUSADO
                self._itens[trabalho.id] = trabalho

    def salvar(self, trabalho: Trabalho) -> None:
        dados = asdict(trabalho)
        self._caminho(trabalho.id).write_text(
            json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    # --------------------------------------------------------------- acesso

    def criar(self, titulo: str, tipo: str = "conversa", estado: str = CONCLUIDO) -> Trabalho:
        with self._trava:
            trabalho = Trabalho(id=uuid.uuid4().hex[:12], titulo=titulo, tipo=tipo, estado=estado)
            self._itens[trabalho.id] = trabalho
        self.salvar(trabalho)
        return trabalho

    def obter(self, id_: str) -> Trabalho | None:
        return self._itens.get(id_)

    def remover(self, id_: str) -> bool:
        with self._trava:
            if id_ not in self._itens:
                return False
            del self._itens[id_]
        self._caminho(id_).unlink(missing_ok=True)
        return True

    def listar(self) -> dict[str, list[dict]]:
        """Agrupado como a coluna da esquerda pede: em andamento e recentes."""
        ordenados = sorted(self._itens.values(), key=lambda t: t.atualizado_em, reverse=True)
        return {
            "em_andamento": [t.resumo() for t in ordenados if t.aberto],
            "recentes": [t.resumo() for t in ordenados if not t.aberto][:12],
        }

    @property
    def pendencias(self) -> int:
        return sum(1 for t in self._itens.values() if t.aprovacao)


def _de_dict(bruto: dict) -> Trabalho | None:
    try:
        return Trabalho(
            id=bruto["id"],
            titulo=bruto.get("titulo", "Sem titulo"),
            tipo=bruto.get("tipo", "conversa"),
            estado=bruto.get("estado", CONCLUIDO),
            criado_em=bruto.get("criado_em", agora()),
            atualizado_em=bruto.get("atualizado_em", agora()),
            mensagens=[Mensagem(**m) for m in bruto.get("mensagens", [])],
            etapas=[Etapa(**e) for e in bruto.get("etapas", [])],
            atividade=[Atividade(**a) for a in bruto.get("atividade", [])],
            aprovacao=Aprovacao(**bruto["aprovacao"]) if bruto.get("aprovacao") else None,
            contexto=bruto.get("contexto", {}),
        )
    except (KeyError, TypeError):
        return None
