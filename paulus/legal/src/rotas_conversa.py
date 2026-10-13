"""
PAULUS - O que e de cada conversa, e a busca no texto delas (C3). O api.py so
chama montar().

  GET  /api/conversas/buscar?termo= os ids das conversas cujo titulo OU o
                                    texto de alguma mensagem tem o termo

Rascunho, anexos pendentes e rolagem sao conveniencia desta janela: ficam no
localStorage, por id (frontend/js/03-assistente.js). O "modo de escopo" que
morava aqui saiu em 13/10/2026: onde procurar e decidido pelo servidor, a cada
pergunta (src/caminho_da_pergunta.py).

Chave: `conversa.painel`.
"""

from __future__ import annotations

import unicodedata

# O resultado da busca: o bastante para a lista, sem varrer para sempre.
LIMITE_BUSCA = 200


def _plano(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or "").lower()) if unicodedata.category(c) != "Mn")


def buscar(trabalhos, termo: str) -> list[dict]:
    """As conversas com o termo no titulo ou nas mensagens, sem acento e sem caixa."""
    alvo = _plano(termo).strip()
    if len(alvo) < 2:
        return []
    achadas = []
    for t in sorted(list(trabalhos._itens.values()), key=lambda x: x.atualizado_em, reverse=True):
        if alvo in _plano(t.titulo):
            achadas.append({"id": t.id, "onde": "titulo"})
        else:
            m = next((m for m in t.mensagens if alvo in _plano(m.texto)), None)
            if m is not None:
                i = _plano(m.texto).find(alvo)
                achadas.append({"id": t.id, "onde": "mensagem",
                                "trecho": m.texto[max(0, i - 40): i + len(alvo) + 60].strip()})
        if len(achadas) >= LIMITE_BUSCA:
            break
    return achadas


def montar(estado, app) -> None:
    @app.get("/api/conversas/buscar")
    def conversas_buscar(termo: str = "") -> dict:
        return {"termo": termo, "conversas": buscar(estado.trabalhos, termo)}
