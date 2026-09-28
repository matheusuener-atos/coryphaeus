"""
O PAULUS de equipe (docs/PLANO-EQUIPE.md): o programa roda no servidor do
escritorio e cada colaborador entra pela internet com a propria conta.

Os dados continuam do escritorio - todos veem tudo, por decisao do dono -,
mas cada coisa diz quem a criou: a conversa (e, dentro dela, quem perguntou),
o documento, a gravacao. Quem esta de fora e a conta da sessao; quem esta na
janela do servidor e a pessoa de "Meus dados".
"""

from __future__ import annotations

NO_SERVIDOR = "no computador do escritório"
TABELAS_COM_AUTOR = {"documentos", "gravacoes"}


def quem(request, prefs: dict | None) -> dict:
    """{"conta_id", "nome"} de quem fez o pedido. conta_id 0 = a janela do servidor."""
    from acesso import rotas as rotas_do_acesso

    p = rotas_do_acesso.pessoa(request) if request is not None else None
    if p:
        return {"conta_id": int(p["conta_id"]), "nome": str(p["nome"])}
    nome = str(((prefs or {}).get("pessoa") or {}).get("nome") or "").strip()
    return {"conta_id": 0, "nome": nome or NO_SERVIDOR}


def marcar_autor(base, tabela: str, id_: int, autor: dict) -> None:
    """Grava quem criou o registro (documento, gravacao) logo depois de criado."""
    if tabela not in TABELAS_COM_AUTOR:
        raise ValueError("tabela sem autor: " + tabela)
    base.escrever(f"UPDATE {tabela} SET criado_por = ?, criado_por_conta = ? WHERE id = ?",
                  (str(autor.get("nome") or ""), int(autor.get("conta_id") or 0), int(id_)))
