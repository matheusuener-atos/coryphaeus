"""
Habilidade: identificar o que e cada documento.

Hibrido de proposito. Data, valor e CPF/CNPJ sao problemas resolvidos por
expressao regular ha decadas: usar o assistente para isso e trocar
milissegundos por 20 segundos e ainda arriscar invencao. O assistente entra so
onde a regra nao decide - tipo do documento e nomes das partes.
"""

from pathlib import Path

from habilidade_base import PRECISA_ASSISTENTE, Contexto, Habilidade, Ponte, evento

HABILIDADE = Habilidade(
    id="classificar",
    nome="Identificar o que é cada documento",
    resumo="Tipo, partes, data e valor de cada arquivo",
    grupo="Organizar",
    acao="organizacao",
    precisa=[PRECISA_ASSISTENTE],
    detalhe=(
        "O resultado fica guardado por conteúdo: reler o mesmo acervo é "
        "instantâneo, e mover ou renomear o arquivo não invalida nada."
    ),
    demora="8 a 25 s por documento novo",
    ordem=10,
)


def executar(ctx: Contexto, caminhos: list[str] | None = None):
    """Gerador: andamento documento a documento, depois o resultado."""
    from classify import classificar_acervo

    alvos = caminhos or []
    if not alvos:
        yield evento("vazio", mensagem="Nenhum documento para ler.")
        return

    def trabalho(empurrar):
        return classificar_acervo(
            alvos,
            cache_path=Path(ctx.cache_classificacao) if ctx.cache_classificacao else None,
            client=ctx.client,
            progresso=lambda i, t, nome, cache: empurrar(
                {"indice": i, "total": t, "nome": nome, "cache": cache}
            ),
            cancelado=ctx.cancelado,
            antes_de_cada=ctx.antes_de_cada,
        )

    ponte = Ponte(trabalho)
    for passo in ponte:
        yield evento("progresso", **passo)

    resultados = ponte.resultado or []
    ctx.registrar(f"Leu {len(resultados)} documento(s)")
    yield evento(
        "resultados",
        documentos=[r.to_dict() for r in resultados],
        parado=ctx.cancelado(),
    )
