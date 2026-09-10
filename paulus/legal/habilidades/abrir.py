"""
Habilidade: abrir documentos e deixar o conteudo disponivel.

Extrai o texto e guarda por conteudo (SHA-1): renomear ou mover o arquivo nao
obriga a ler de novo.
"""

from habilidade_base import Contexto, Habilidade

HABILIDADE = Habilidade(
    id="abrir",
    nome="Abrir documentos",
    resumo="Lê PDF, DOCX, TXT e MD e deixa o conteúdo disponível",
    grupo="Documentos",
    acao="anexar",
    detalhe=(
        "PDF escaneado, que é imagem e não texto, ainda não dá: o arquivo é "
        "ignorado com aviso em vez de entrar vazio no acervo."
    ),
    demora="alguns segundos por arquivo",
    ordem=30,
)


def executar(ctx: Contexto) -> dict:
    """Reabre a pasta de documentos e reconstroi o indice."""
    total = ctx.recarregar()
    ctx.registrar(f"{total} documento(s) aberto(s)")
    return {"documentos": total}
