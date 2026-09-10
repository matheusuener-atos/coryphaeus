"""
Habilidade: Planilha de prazos e vencimentos.

Ainda nao existe. Entra no catalogo marcada como tal - listar promessa junto
com o que funciona e a forma mais rapida de perder a confianca de quem usa.
"""

from habilidade_base import EM_BREVE, Habilidade

HABILIDADE = Habilidade(
    id="vencimentos",
    nome="Planilha de prazos e vencimentos",
    resumo="Lista o que vence, com quantos dias faltam, em Excel",
    grupo="Organizar",
    estado=EM_BREVE,
    detalhe="Extrai as datas de vigência e vencimento de cada contrato e gera uma planilha ordenada por urgência. As datas já saem por regra hoje, dentro da classificação — falta juntar e escrever o arquivo.",
    ordem=30,
)
