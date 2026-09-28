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


# ------------------------------------------- e-mail e Google por pessoa (E3b)

def pessoa_da_vez() -> dict | None:
    """A sessao de fora que fez o pedido atendido agora; None na janela do servidor."""
    from acesso.porteiro import PESSOA_DA_VEZ

    return PESSOA_DA_VEZ.get()


def conta_email_visivel(conta) -> bool:
    """
    De fora, cada pessoa ve a conta de e-mail dela (dono = a conta do acesso)
    e as do escritorio (dono 0). A janela do servidor ve todas.
    """
    p = pessoa_da_vez()
    if conta is None or p is None:
        return conta is not None
    return int(getattr(conta, "dono", 0) or 0) in (0, int(p["conta_id"]))


def conta_email_padrao(contas):
    """A conta que a tela abre: de fora, a da propria pessoa, se ela tem; senao, a em uso."""
    p = pessoa_da_vez()
    if p is not None:
        propria = next((c for c in contas.itens if int(c.dono or 0) == int(p["conta_id"])), None)
        if propria:
            return propria
    atual = contas.em_uso
    if atual is not None and conta_email_visivel(atual):
        return atual
    return next((c for c in contas.itens if conta_email_visivel(c)), None)
