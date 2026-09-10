"""
Habilidade: Assinar digitalmente.

Ainda nao existe. Entra no catalogo marcada como tal - listar promessa junto
com o que funciona e a forma mais rapida de perder a confianca de quem usa.
"""

from habilidade_base import EM_BREVE, Habilidade

HABILIDADE = Habilidade(
    id="assinar",
    nome="Assinar digitalmente",
    resumo="Assinatura com certificado ICP-Brasil",
    grupo="Escrita",
    estado=EM_BREVE,
    detalhe="Assina o documento com o certificado do escritório, sem que o arquivo saia da máquina.",
    ordem=20,
)
