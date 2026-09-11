"""
PAULUS - Contrato de uma habilidade.

Uma habilidade e um arquivo em `habilidades/`. Para existir, o arquivo precisa
declarar `HABILIDADE = Habilidade(...)`. Para fazer alguma coisa, precisa
tambem de `executar(ctx, **parametros)`.

`executar` pode:
  - devolver um dict, e a interface recebe a resposta pronta; ou
  - ser um gerador de `(tipo, dados)`, e a interface recebe evento por evento
    enquanto o trabalho acontece.

O `ctx` entrega o que a habilidade precisa da aplicacao - indice, assistente,
pastas - sem que o modulo importe a aplicacao. E o que permite mexer numa
habilidade sem mexer no programa, e o programa sem mexer nas habilidades.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from typing import Any

PRONTA = "pronta"
EM_BREVE = "em_breve"
COM_PROBLEMA = "com_problema"

PRECISA_DOCUMENTOS = "documentos"
PRECISA_ASSISTENTE = "assistente"

ROTULOS_PRECISA = {
    PRECISA_DOCUMENTOS: "documentos abertos",
    PRECISA_ASSISTENTE: "assistente local ligado",
}

GRUPOS = ["Documentos", "Organizar", "Escrita"]


@dataclass
class Habilidade:
    """O que um modulo declara sobre si mesmo."""

    id: str
    nome: str
    resumo: str
    grupo: str
    estado: str = PRONTA
    acao: str = ""                                  # o que a interface abre
    precisa: list[str] = field(default_factory=list)
    detalhe: str = ""
    demora: str = ""
    ordem: int = 100                                # posicao dentro do grupo

    # Preenchidos pelo carregador, nao pelo autor do modulo.
    arquivo: str = ""
    problema: str = ""
    executar: Callable[..., Any] | None = None

    @property
    def executavel(self) -> bool:
        return self.estado == PRONTA and self.executar is not None

    def to_dict(self) -> dict:
        dados = {
            k: v for k, v in asdict(self).items()
            if k not in ("executar",)
        }
        dados["precisa_rotulos"] = [ROTULOS_PRECISA.get(p, p) for p in self.precisa]
        dados["executavel"] = self.executavel
        return dados


class Contexto:
    """
    A porta da aplicacao para dentro da habilidade.

    Existe para o modulo nao precisar importar `api`: sem isso, mexer numa
    habilidade obrigaria a entender o servidor inteiro, e uma importacao
    circular impediria carregar o modulo sozinho num teste.
    """

    def __init__(
        self,
        *,
        searcher=None,
        client=None,
        pasta=None,
        cache_classificacao=None,
        diarios=None,
        recarregar=None,
        registrar=None,
        cancelado=None,
        antes_de_cada=None,
        ritmo=None,
    ) -> None:
        self.searcher = searcher
        self.client = client
        # O que esta maquina ja mediu de si mesma: quanto ela le por segundo,
        # quanto escreve. Sem isso, a tela nao promete tempo nenhum.
        self.ritmo = ritmo
        self.pasta = pasta
        self.cache_classificacao = cache_classificacao
        self.diarios = diarios
        self._recarregar = recarregar
        self._registrar = registrar
        self.cancelado = cancelado or (lambda: False)
        self.antes_de_cada = antes_de_cada or (lambda: None)

    # -------------------------------------------------------------- estado

    @property
    def documentos(self) -> list:
        return self.searcher.documents if self.searcher else []

    @property
    def tem_documentos(self) -> bool:
        return bool(self.documentos)

    def recarregar(self) -> int:
        """Reabre a pasta de documentos e reconstroi o indice."""
        return self._recarregar() if self._recarregar else 0

    def registrar(self, texto: str) -> None:
        """Anota uma linha na coluna de atividade do trabalho em andamento."""
        if self._registrar:
            self._registrar(texto)


def evento(tipo: str, **dados) -> tuple[str, dict]:
    """Acucar para os geradores: `yield evento("token", t=pedaco)`."""
    return (tipo, dados)


class Ponte:
    """
    Transforma uma funcao que empurra por callback num iterador que puxa.

    Varias coisas demoradas aqui avisam do andamento por callback - o cliente
    do assistente entrega pedaco a pedaco, o classificador avisa a cada
    documento. Mas quem publica na tela precisa puxar evento por evento. Uma
    fila com uma thread faz a ponte sem acumular tudo na memoria, que era o
    jeito errado: juntar o andamento numa lista e so emitir no fim mostra a
    barra de progresso pulando de 0 para 100.

        ponte = Ponte(lambda empurrar: trabalho_demorado(aviso=empurrar))
        for passo in ponte:
            yield evento("progresso", **passo)
        usar(ponte.resultado)
    """

    def __init__(self, trabalho: Callable[[Callable[[Any], None]], Any]) -> None:
        import queue
        import threading

        self._fila: queue.Queue = queue.Queue()
        self._fim = object()
        self._resultado: Any = None
        self._erro: BaseException | None = None
        self._terminou = False

        def rodar() -> None:
            try:
                self._resultado = trabalho(self._fila.put)
            except BaseException as exc:  # repassado ao consumidor
                self._erro = exc
            finally:
                self._fila.put(self._fim)

        threading.Thread(target=rodar, daemon=True).start()

    def __iter__(self) -> Iterator[Any]:
        while True:
            item = self._fila.get()
            if item is self._fim:
                self._terminou = True
                if self._erro:
                    raise self._erro
                return
            yield item

    @property
    def resultado(self) -> Any:
        if not self._terminou:
            raise RuntimeError("consuma a ponte inteira antes de pedir o resultado")
        return self._resultado


__all__ = [
    "COM_PROBLEMA",
    "Contexto",
    "EM_BREVE",
    "GRUPOS",
    "Habilidade",
    "Ponte",
    "PRECISA_ASSISTENTE",
    "PRECISA_DOCUMENTOS",
    "PRONTA",
    "ROTULOS_PRECISA",
    "evento",
]
