"""
Habilidade: Redigir a partir de um modelo.

Ainda nao existe. Entra no catalogo marcada como tal - listar promessa junto
com o que funciona e a forma mais rapida de perder a confianca de quem usa.
"""

from habilidade_base import EM_BREVE, Habilidade

HABILIDADE = Habilidade(
    id="redigir",
    nome="Redigir a partir de um modelo",
    resumo="Preenche um modelo com os dados dos documentos abertos",
    grupo="Escrita",
    estado=EM_BREVE,
    detalhe="Pega um modelo do escritório e preenche partes, valores e datas com o que já foi extraído dos documentos.",
    ordem=10,
)
