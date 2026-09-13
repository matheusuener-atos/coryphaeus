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

from . import alinhar, esquema, roteador
from .catalogo import Catalogo, Extrator
from .esquema import Metadata, Secao
from .extratores.base import Pedido
from .roteador import Pacote


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
                else biblioteca.desatualizadas(
                    meta, catalogo, _digest_do(client) if client else "",
                    getattr(client, "model", "") if client else ""))

    for nome in alvo:
        extrator = catalogo.para_secao(nome)
        if not extrator:
            analise.puladas.append(nome)
            continue
        if extrator.modelo and extrator.exige_modelo and client is None:
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
            meta.guardar(nome, itens)
        elif objeto is not None:
            setattr(meta, nome, objeto)
        meta.marcar_secao(nome, ficha)

    biblioteca.gravar(meta, nota="analise: " + (", ".join(analise.rodadas) or "nada a fazer"))
    analise.ms = int((time.time() - comeco) * 1000)
    return analise


def _digest_do(client) -> str:
    """A impressao digital do modelo, quando da para perguntar."""
    try:
        return client.digest() if hasattr(client, "digest") else ""
    except Exception:
        return ""


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
        # O digest diz que modelo produziu isto. Trocar o modelo com o mesmo
        # nome - um `ollama pull` novo - muda o digest e envelhece a secao;
        # sem ele, o extraido pelo modelo antigo passaria por atual sempre.
        model_digest=(_digest_do(client) if extrator.modelo and client is not None else ""),
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

    # O que o extrator afirmou sem ancorar no texto passa pela conferencia
    # antes de virar qualquer coisa. Extrator de regra ja entrega o item preso
    # a uma posicao do documento - a citacao E o texto daquela posicao -, entao
    # ele nao paga por isso; o que vem de modelo, sim, sempre.
    soltos = [i for i in resultado.itens if not i.source.resolvivel]
    if soltos:
        alinhar.verificar_todos(soltos, texto, meta.version_id, pedido.paginas)
        # E o que passou pela aritmetica ainda passa pela leitura: o trecho
        # existe, mas sustenta o que foi afirmado? Extrator e conferidor nunca
        # sao a mesma chamada - auto-verificacao nao verifica nada.
        conferidor = catalogo.verificador()
        if conferidor and client is not None and extrator.modelo:
            from .extratores import verificador as _conferidor

            rebaixados = _conferidor.conferir_todos(client, soltos, extrator.secao)
            if rebaixados:
                ficha.error = f"{rebaixados} item(ns) reprovados pelo conferidor"[:200]

    ficha.status = resultado.status
    ficha.item_count = len(resultado.itens) if resultado.itens else (1 if resultado.objeto else 0)
    ficha.unverified_count = len([i for i in resultado.itens if not i.verified])
    ficha.duration_ms = int((time.time() - comeco) * 1000)
    if resultado.modelo:
        ficha.model = resultado.modelo
    elif extrator.modelo:
        # O extrator podia chamar o modelo e nao chamou - a regra decidiu
        # sozinha. Anotar modelo e digest aqui faria a secao envelhecer no dia
        # em que o modelo mudasse, sem que o modelo tivesse feito nada nela.
        ficha.model = None
        ficha.model_digest = ""
    if resultado.digest:
        ficha.model_digest = resultado.digest
    if resultado.erro:
        ficha.error = resultado.erro[:200]
    return ficha, resultado.itens, resultado.objeto


# ------------------------------------------------------- HOOK 2 e HOOK 3


class Saber:
    """
    A camada vista de fora - uma coisa so, que se liga e se desliga.

    O programa de hoje conhece este objeto e mais nada da camada. Com ele
    desligado, `montar_contexto` devolve na hora um pacote de fallback e tudo
    volta a ser como era: e a chave que torna o retrofit reversivel a qualquer
    momento, e que permite medir o ganho ligando e desligando na mesma
    maquina, com as mesmas perguntas.
    """

    def __init__(self, biblioteca, catalogo: Catalogo, ligada: bool = True) -> None:
        self.biblioteca = biblioteca
        self.catalogo = catalogo
        self.ligada = bool(ligada)
        self.medidas: list[dict] = []

    # ----------------------------------------------------------- consulta

    def metadados_de(self, documentos) -> tuple[list[Metadata], dict]:
        """
        O que ja se sabe dos documentos que a conversa esta olhando.

        A ponte entre os dois mundos e o sha1: e assim que o acervo deste
        programa identifica arquivo, e e o que a biblioteca guardou junto da
        versao. Documento sem metadata simplesmente nao entra na lista - e o
        roteador trata isso como cobertura incompleta, nao como ausencia.
        """
        metas, nomes = [], {}
        for doc in documentos or []:
            meta = None
            sha1 = getattr(doc, "sha1", "")
            if sha1:
                meta = self.biblioteca.ler_por_sha1(sha1)
            if meta is None:
                caminho = getattr(doc, "path", "")
                if caminho:
                    meta = self.biblioteca.ler_por_caminho(caminho)
            if meta is not None:
                metas.append(meta)
                nomes[meta.version_id] = getattr(doc, "name", "") or meta.titulo
        return metas, nomes

    def montar_contexto(self, pergunta: str, documentos, *, em_foco: bool = False) -> Pacote:
        """
        HOOK 2. O que ler para responder isto - e quanto isso custa.

        Nunca levanta excecao: qualquer problema aqui vira fallback, porque um
        erro na camada nao pode virar um erro na conversa de alguem.
        """
        if not self.ligada:
            return Pacote(porque="camada desligada", fallback=True,
                          trace={"decisao": "desligada"})
        try:
            metas, nomes = self.metadados_de(documentos)
            pacote = roteador.resolver(pergunta, metas, nomes=nomes, em_foco=em_foco)
        except Exception as exc:   # a camada falhando nao pode derrubar a resposta
            return Pacote(porque=f"a camada falhou ({type(exc).__name__}) - segui pelo caminho de sempre",
                          fallback=True, trace={"decisao": "erro", "erro": str(exc)[:200]})
        self.anotar(pacote, len(documentos or []))
        return pacote

    def anotar(self, pacote: Pacote, documentos: int) -> None:
        """Cada decisao vira uma linha de medida - sem isso nao ha como saber o ganho."""
        self.medidas.append({
            "quando": esquema.agora(), "nivel": pacote.nivel, "fallback": pacote.fallback,
            "fatos": len(pacote.fatos), "documentos": documentos, "ms": pacote.ms,
            "intencao": pacote.intencao.secao or "-",
        })
        del self.medidas[:-500]

    def medicao(self) -> dict:
        """Quanto a camada esta economizando, medido - nao estimado."""
        total = len(self.medidas)
        if not total:
            return {"perguntas": 0}
        rapidas = len([m for m in self.medidas if m["nivel"] <= roteador.METADATA_E_RESUMO])
        return {
            "perguntas": total,
            "no_metadata": rapidas,
            "porcento": round(rapidas * 100 / total),
            "fallback": len([m for m in self.medidas if m["fallback"]]),
            "ms_medio": round(sum(m["ms"] for m in self.medidas) / total, 1),
        }


def fontes_da_resposta(pacote: Pacote, resposta: str) -> dict:
    """
    HOOK 3. A resposta com as fontes do lado - e o aviso quando nao ha.

    O que sai daqui tem a mesma forma das fontes que a tela ja desenha, para
    nao exigir tela nova: documento, um rotulo de onde, e o texto citado. A
    diferenca e que no nivel 0 o texto citado e a frase exata do documento,
    conferida, e o rotulo e a pagina - nao "trecho 3".
    """
    fontes = []
    for i, fato in enumerate(pacote.fatos, start=1):
        fontes.append({
            "documento": fato.documento,
            "trecho": i,
            "onde": f"página {fato.pagina}" if fato.pagina else "no documento",
            "score": 1.0,
            "texto": fato.quote or fato.valor,
            "pagina": fato.pagina,
            "char_start": fato.char_start,
            "char_end": fato.char_end,
            "nivel": pacote.nivel,
        })
    return {
        "fontes": fontes,
        "nivel": pacote.nivel,
        "porque": pacote.porque,
        "inferencia": False,     # nivel 0 so usa fato conferido
        "resposta": resposta,
    }
