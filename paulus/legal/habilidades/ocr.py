"""
Habilidade: Ler documento escaneado.

Ainda nao existe. Entra no catalogo marcada como tal - listar promessa junto
com o que funciona e a forma mais rapida de perder a confianca de quem usa.
"""

from habilidade_base import EM_BREVE, Habilidade

HABILIDADE = Habilidade(
    id="ocr",
    nome="Ler documento escaneado",
    resumo="Reconhece o texto de PDF que é imagem",
    grupo="Documentos",
    estado=EM_BREVE,
    detalhe="Hoje um PDF escaneado é ignorado com aviso, porque não tem texto para extrair. Reconhecimento de caracteres resolveria, ao custo de mais uma dependência pesada.",
    ordem=40,
)
