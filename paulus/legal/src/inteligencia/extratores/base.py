"""
O que todo extrator recebe e o que ele devolve.

Um extrator e um especialista: ele olha um documento e escreve o que sabe
sobre UMA secao. Quem manda nele e o catalogo; quem confere o que ele
produziu e a camada de verificacao. Ele nao sabe da biblioteca, nao sabe do
roteador e nao grava nada - por isso da para trocar um extrator sem tocar em
mais nada, que e a promessa do registro.

A forma de trabalho tem uma hierarquia que vale lembrar:

    nivel 0   regra deterministica   numero do processo, datas, valores, leis
    nivel 1   modelo pequeno         tipo de documento, tribunal
    nivel 2   modelo grande          partes, resumo
    nivel 3   verificador            confere o que os niveis 1 e 2 disseram

**Nivel 0 nao e atalho: e o nivel mais confiavel do sistema.** Numero de
processo tem digito verificador; data e valor em portugues tem forma fixa;
citacao de lei e altamente regular. Nada disso deve passar por um modelo de
tres bilhoes de parametros, que erraria de formas imprevisiveis o que uma
expressao regular acerta sempre - e de graca.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from ..esquema import Fonte, Item
from ..texto import Pagina, pagina_de

# Quanto de um documento um extrator de modelo le por vez. Um processo de 400
# paginas nao cabe na janela; o que interessa a estas secoes esta quase sempre
# no comeco (qualificacao, objeto, valor da causa).
LEITURA_PADRAO = 6000


@dataclass
class Pedido:
    """O documento e o que o extrator precisa para trabalhar nele."""

    texto: str
    version_id: str = ""
    paginas: list[Pagina] = field(default_factory=list)
    nome: str = ""
    client: object | None = None          # so para extrator de modelo
    limite: int = LEITURA_PADRAO
    registrar: Callable[[str], None] | None = None

    def contar(self, mensagem: str) -> None:
        if self.registrar:
            self.registrar(mensagem)

    @property
    def comeco(self) -> str:
        return self.texto[: self.limite]


@dataclass
class Resultado:
    """O que o extrator achou, e como foi."""

    itens: list[Item] = field(default_factory=list)
    objeto: dict | None = None            # secoes que sao objeto, nao lista
    status: str = "ok"                    # ok | failed | skipped
    erro: str = ""
    modelo: str = ""
    digest: str = ""

    @property
    def nao_verificados(self) -> int:
        return len([i for i in self.itens if not i.verified])


def limpar(trecho: str) -> str:
    """O trecho numa linha so - e como ele aparece na resposta."""
    return " ".join((trecho or "").split())


def fonte_do_span(pedido: Pedido, inicio: int, fim: int) -> Fonte:
    return Fonte(
        version_id=pedido.version_id, kind="text",
        page=pagina_de(pedido.paginas, inicio) if pedido.paginas else None,
        char_start=inicio, char_end=fim,
    )


def item_do_span(pedido: Pedido, inicio: int, fim: int, *, id_: str, dados: dict,
                 produzido_por: str, folga: int = 0) -> Item:
    """
    Um item ancorado no texto - conferido por construcao.

    Extrator de regra nao precisa de verificacao posterior: o item nasceu de
    uma posicao do proprio texto, e a citacao E o texto daquela posicao. O
    `verified` aqui nao e confianca no extrator, e o fato de a evidencia e o
    span serem a mesma coisa.
    """
    aberto = max(0, inicio - folga)
    fechado = min(len(pedido.texto), fim + folga)
    return Item(
        id=id_,
        dados=dados,
        quote=pedido.texto[aberto:fechado].strip(),
        certainty="explicit",
        verified=True,
        source=fonte_do_span(pedido, aberto, fechado),
        produced_by=produzido_por,
    )


def volta_de(texto: str, inicio: int, antes: int = 120, depois: int = 60) -> tuple[str, int]:
    """
    A janela em volta do achado, e onde ele comeca dentro dela.

    Sai sem acento e em minuscula, mas com o MESMO tamanho do original: cada
    caractere acentuado vira a letra base no lugar dele. Manter o tamanho e o
    que permite medir distancia - e distancia e o que decide o rotulo.
    """
    import unicodedata

    aberto = max(0, inicio - antes)
    bruto = texto[aberto: inicio + depois]
    plano = "".join(
        (unicodedata.normalize("NFD", c)[0] if unicodedata.category(c) != "Mn" else c)
        for c in bruto
    ).lower()
    onde = inicio - aberto

    # A janela para na frase: o que qualifica um valor esta na frase dele.
    # Sem este corte, "Protocolado em 02/01/2026. 30/09/2025, data da
    # assinatura" faria a segunda data virar protocolo, por vizinhanca.
    corte = max(plano.rfind(". ", 0, onde), plano.rfind("\n", 0, onde),
                plano.rfind("; ", 0, onde))
    if corte > 0:
        plano, onde = plano[corte + 1:], onde - corte - 1
    fim_da_frase = min((p for p in (plano.find(". ", onde), plano.find("\n", onde))
                        if p >= 0), default=-1)
    if fim_da_frase > 0:
        plano = plano[: fim_da_frase + 1]
    return plano, onde


# Pista longe demais nao qualifica coisa nenhuma: num paragrafo corrido, uma
# palavra a mais de cem caracteres fala de outra frase.
ALCANCE = 70


def escolher_kind(volta: tuple[str, int] | str, mapa: dict[str, tuple[str, ...]],
                  padrao: str = "") -> str:
    """
    O rotulo cuja pista esta MAIS PERTO do achado - nao o primeiro da lista.

    Esta e a diferenca entre "o valor da causa e de R$ 15.000,00; a multa e de
    R$ 1.500,00" sair com dois valores da causa ou com um valor da causa e uma
    multa. A pista mais proxima e quase sempre a que qualifica; a mais longe e
    quase sempre a frase anterior.

    Pista ANTES vence sempre que existir. Em portugues juridico o que
    qualifica vem antes ("assinado em 12/03/2025", "o valor da causa e de R$
    15.000,00"); o que vem depois costuma ser a proxima frase, falando de
    outra coisa. So quando nao ha nenhuma pista antes e que se olha para
    tras - e ai perto, para pegar "12/03/2025, data da assinatura".
    """
    plano, onde = (volta if isinstance(volta, tuple) else (volta, len(volta)))

    def procurar(antes: bool, alcance: int) -> str:
        melhor, menor = "", alcance + 1
        for rotulo, pistas in mapa.items():
            for pista in pistas:
                comeco = 0
                while True:
                    posicao = plano.find(pista, comeco)
                    if posicao < 0:
                        break
                    comeco = posicao + 1
                    fim = posicao + len(pista)
                    if antes and fim <= onde:
                        distancia = onde - fim
                    elif not antes and posicao >= onde:
                        distancia = posicao - onde
                    else:
                        continue
                    if distancia < menor:
                        melhor, menor = rotulo, distancia
        return melhor

    return procurar(True, ALCANCE) or procurar(False, 25) or padrao


RE_ESPACO = re.compile(r"\s+")
