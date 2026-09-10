"""
Habilidade: achar uma palavra nos documentos abertos.

Sem passar pelo assistente. Existe porque nem toda pergunta merece 20 segundos
de espera: as vezes a pessoa so quer achar onde esta escrito.
"""

from habilidade_base import PRECISA_DOCUMENTOS, Contexto, Habilidade

HABILIDADE = Habilidade(
    id="buscar",
    nome="Achar uma palavra",
    resumo="Mostra onde o termo aparece, sem passar pelo assistente",
    grupo="Documentos",
    acao="busca",
    precisa=[PRECISA_DOCUMENTOS],
    detalhe=(
        "Busca direta no texto, com plural e acento tratados: procurar por "
        "'cláusulas' acha 'CLAUSULA'. Serve para quando você só quer achar onde "
        "está escrito, sem esperar."
    ),
    demora="instantâneo",
    ordem=20,
)


def executar(ctx: Contexto, termo: str = "", top: int = 8) -> dict:
    termo = (termo or "").strip()
    if not termo:
        return {"termo": "", "documentos": len(ctx.documentos), "resultados": []}

    hits = ctx.searcher.search(termo, top_k=top)
    ctx.registrar(f"Procurou por {termo!r} em {len(ctx.documentos)} documento(s)")

    return {
        "termo": termo,
        "documentos": len(ctx.documentos),
        "resultados": [
            {
                "documento": h.doc_name,
                "trecho": h.chunk.index + 1,
                "texto": h.chunk.text,
            }
            for h in hits
        ],
    }
