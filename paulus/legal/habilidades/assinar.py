"""
Habilidade: Assinar digitalmente, pela conversa.

Assinar EXISTE - na tela "Assinar documento", com certificado A1, desde a
Etapa 4. O que ainda nao existe e pedir isso aqui na conversa, que e o que
esta habilidade declara. Deixar escrito "ainda nao existe" sem essa distincao
fazia o proprio programa negar uma coisa que ele faz.
"""

from habilidade_base import EM_BREVE, Habilidade

HABILIDADE = Habilidade(
    id="assinar",
    nome="Assinar digitalmente",
    resumo="Assinatura com certificado ICP-Brasil",
    grupo="Escrita",
    estado=EM_BREVE,
    detalhe=("A tela Assinar documento já faz isso, com certificado A1 e sem que o "
         "arquivo saia da máquina. O que falta é pedir a assinatura por aqui, "
         "na conversa."),
    ordem=20,
)
