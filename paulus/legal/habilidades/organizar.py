"""
Habilidade: organizar uma pasta.

Varre, classifica e propoe a estrutura de pastas. Move so depois de aprovado,
gravando um diario que permite desfazer o lote inteiro.

O fluxo tem varios passos com decisao humana no meio, entao a interface conduz
a sequencia chamando os endpoints do organizador. Este modulo e onde o
comportamento e a descricao dessa habilidade vivem.
"""

from habilidade_base import PRECISA_ASSISTENTE, Contexto, Habilidade

HABILIDADE = Habilidade(
    id="organizar",
    nome="Organizar uma pasta",
    resumo="Propõe a estrutura de pastas e move, com desfazer",
    grupo="Organizar",
    acao="organizacao",
    precisa=[PRECISA_ASSISTENTE],
    detalhe=(
        "Você escolhe as pastas navegando pelo computador. Depois de ler, confere "
        "a tabela e corrige o que estiver errado — nada sai do lugar até você "
        "aprovar. Nada é apagado, nada é sobrescrito, e todo lote pode ser desfeito."
    ),
    demora="depende do tamanho do acervo",
    ordem=20,
)

# Ordem dos passos, usada pelo cartao de plano na tela.
PASSOS = [
    "Escolher onde procurar",
    "Ler e classificar os documentos",
    "Conferir a classificação",
    "Mover para a estrutura nova",
]


def executar(ctx: Contexto) -> dict:
    """Devolve o roteiro; a condução é da interface, por ter decisão humana no meio."""
    return {"passos": PASSOS, "conduzido_pela_tela": True}
