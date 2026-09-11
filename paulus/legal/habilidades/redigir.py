"""
Habilidade: Redigir a partir de um modelo, pela conversa.

Redigir com apoio do assistente EXISTE - no Editor de texto, no painel "Pedir
aqui", desde a Etapa 6. O que falta e partir de um modelo do escritorio e
preenche-lo com o que ja foi lido dos documentos, e pedir isso por aqui.
"""

from habilidade_base import EM_BREVE, Habilidade

HABILIDADE = Habilidade(
    id="redigir",
    nome="Redigir a partir de um modelo",
    resumo="Preenche um modelo com os dados dos documentos abertos",
    grupo="Escrita",
    estado=EM_BREVE,
    detalhe=("O Editor de texto já redige com o assistente, no painel “Pedir aqui”. "
         "O que falta é partir de um modelo do escritório e preenchê-lo com as "
         "partes, valores e datas já extraídos dos documentos."),
    ordem=10,
)
