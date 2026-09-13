"""
Os tres pontos onde a camada encosta no programa que ja existe.

Toda a camada se encaixa em tres lugares. Nada mais precisa mudar:

    HOOK 1  ingestao          `analisar_documento` roda em segundo plano
    HOOK 2  montar contexto   `montar_contexto` decide o nivel e devolve o que ler
    HOOK 3  render da resposta `fontes_da_resposta` anexa fonte e rotula inferencia

A regra de ouro atravessa os tres: **nunca regredir**. Sem metadata, com
metadata velho, com campo nao verificado ou com duvida do roteador, o que
acontece e o comportamento de hoje - inclusive ler o documento inteiro. A
camada so acrescenta caminho rapido; ela nao tem autorizacao para tirar
nenhum caminho existente.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import esquema
from .catalogo import Catalogo, Extrator
from .esquema import Metadata, Secao
from .extratores.base import Pedido


@dataclass
class Analise:
    """O que uma passada de analise fez - para o log e para a tela."""

    metadata: Metadata | None = None
    rodadas: list[str] = field(default_factory=list)
    puladas: list[str] = field(default_factory=list)
    falhas: dict = field(default_factory=dict)
    ms: int = 0

    @property
    def mudou(self) -> bool:
        return bool(self.rodadas)


def analisar_documento(biblioteca, catalogo: Catalogo, caminho, *, texto: str,
                       paginas: int = 0, sha1: str = "", titulo: str = "",
                       secoes: list[str] | None = None, forcar: bool = False,
                       client=None, registrar=None) -> Analise:
    """
    HOOK 1. Le o documento uma vez e guarda o que entendeu.

    Idempotente e seguro para rodar em segundo plano: nao bloqueia a ingestao,
    nao altera o arquivo original e, chamado duas vezes no mesmo documento sem
    `forcar`, nao refaz nada. E o que permite chama-lo na indexacao sem medo,
    inclusive em cima de um acervo inteiro ja existente.

    `secoes=None` roda o que falta e o que ficou velho - nunca o que ja esta
    bom. Reprocessar o que nao mudou custa o tempo do modelo e nao muda o
    resultado.
    """
    comeco = time.time()
    registro = biblioteca.registrar(caminho, texto, paginas=paginas, sha1=sha1, titulo=titulo)
    meta = registro.metadata
    analise = Analise(metadata=meta)

    alvo = list(secoes or [])
    if not alvo:
        alvo = (catalogo.secoes_declaradas() if forcar
                else biblioteca.desatualizadas(meta, catalogo))

    for nome in alvo:
        extrator = catalogo.para_secao(nome)
        if not extrator:
            analise.puladas.append(nome)
            continue
        if extrator.modelo and client is None:
            # Sem assistente ligado a secao fica `missing`, e o roteador
            # escala. Nao e erro: e o programa dizendo o que nao sabe.
            meta.marcar_secao(nome, Secao(extractor=extrator.id, status="missing",
                                          stale_reason="assistente desligado"))
            analise.puladas.append(nome)
            continue

        ficha, itens, objeto = _rodar(extrator, catalogo, meta, biblioteca, texto,
                                      client=client, registrar=registrar)
        if ficha.status == "failed":
            analise.falhas[nome] = ficha.error
        else:
            analise.rodadas.append(nome)

        if nome in esquema.SECOES_COLECAO:
            setattr(meta, nome, itens)
        elif objeto is not None:
            setattr(meta, nome, objeto)
        meta.marcar_secao(nome, ficha)

    biblioteca.gravar(meta, nota="analise: " + (", ".join(analise.rodadas) or "nada a fazer"))
    analise.ms = int((time.time() - comeco) * 1000)
    return analise


def _rodar(extrator: Extrator, catalogo: Catalogo, meta: Metadata, biblioteca,
           texto: str, *, client=None, registrar=None):
    """Roda um extrator e monta a ficha de producao da secao."""
    modelo = catalogo.modelo_de(extrator)
    comeco = time.time()
    pedido = Pedido(
        texto=texto,
        version_id=meta.version_id,
        paginas=biblioteca.paginas_da_versao(meta.document_id, meta.version_id),
        nome=meta.titulo,
        client=client if extrator.modelo else None,
        registrar=registrar,
    )
    ficha = Secao(
        extractor=extrator.id,
        model=(modelo.id if modelo else None),
        prompt_version=extrator.prompt_version,
        schema_version="v0",
        generated_at=esquema.agora(),
    )
    try:
        modulo = extrator.carregar()
        resultado = modulo.extrair(pedido)
    except Exception as exc:   # extrator quebrado nao pode derrubar a ingestao
        ficha.status = "failed"
        ficha.error = f"{type(exc).__name__}: {exc}"[:200]
        ficha.duration_ms = int((time.time() - comeco) * 1000)
        return ficha, [], None

    ficha.status = resultado.status
    ficha.item_count = len(resultado.itens) if resultado.itens else (1 if resultado.objeto else 0)
    ficha.unverified_count = resultado.nao_verificados
    ficha.duration_ms = int((time.time() - comeco) * 1000)
    if resultado.modelo:
        ficha.model = resultado.modelo
    if resultado.digest:
        ficha.model_digest = resultado.digest
    if resultado.erro:
        ficha.error = resultado.erro[:200]
    return ficha, resultado.itens, resultado.objeto
