"""
Arquivo de mesmo nome: perguntar, e nao decidir sozinho.

Pedido de 28/09/2026: ao salvar um documento com o nome de um que ja existe,
o programa pergunta se a pessoa quer renomear ou substituir. Antes, uns
lugares passavam por cima sem avisar (o certificado de conformidade, os
recibos, a transcricao) e outros trocavam o nome para " (2)" por conta
propria.

Toda rota que grava um arquivo com nome que a pessoa ve faz o mesmo:

    decisoes = nomes.do_pedido(payload)          # o que a pessoa ja decidiu
    pendentes = []
    alvo = nomes.destino(pasta, nome, decisoes, pendentes)
    ...                                           # (um por arquivo)
    nomes.conferir(pendentes)                     # levanta NomeRepetido

`destino` devolve onde gravar, ou None quando o nome ja existe e ainda nao
ha decisao - nada e gravado antes de `conferir`, que levanta NomeRepetido
com todos os conflitos de uma vez. A API responde 409 com a lista; a tela
pergunta um por um (Renomear / Substituir) e manda o pedido de novo com as
decisoes, por nome original:

    {"decisoes": {"contrato.pdf": {"acao": "substituir"},
                  "parecer.pdf": {"acao": "renomear", "nome": "parecer v2.pdf"}}}

Arquivo identico ao que ja esta la nao e conflito: quem chama confere o
conteudo antes, quando faz sentido (anexar, incluir no Acervo).
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

RE_PROIBIDO = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class NomeRepetido(Exception):
    """Um ou mais arquivos com nome que ja existe, sem decisao da pessoa."""

    def __init__(self, conflitos: list[dict]):
        super().__init__("arquivo de mesmo nome")
        self.conflitos = conflitos


def limpar(nome: str, extensao: str) -> str:
    """O nome que a pessoa digitou, sem caractere que o Windows recusa, e com
    a extensao do arquivo quando ela a apagou."""
    nome = RE_PROIBIDO.sub(" ", str(nome or "")).strip().strip(".")
    nome = re.sub(r"\s+", " ", nome)
    if not nome:
        return ""
    if extensao and not nome.lower().endswith(extensao.lower()):
        nome += extensao
    return nome[:200]


def do_pedido(payload) -> dict:
    """As decisoes que vieram no pedido (dict, ou texto JSON de um formulario)."""
    bruto = payload.get("decisoes") if isinstance(payload, dict) else payload
    if isinstance(bruto, str):
        try:
            bruto = json.loads(bruto or "{}")
        except ValueError:
            bruto = {}
    if not isinstance(bruto, dict):
        return {}
    saida = {}
    for nome, d in bruto.items():
        if isinstance(d, dict) and d.get("acao") in ("renomear", "substituir"):
            saida[str(nome)] = {"acao": d["acao"], "nome": str(d.get("nome") or "")}
    return saida


def destino(pasta: Path, nome: str, decisoes: dict, pendentes: list, *, ocupados: set | None = None) -> Path | None:
    """
    Onde gravar `nome` em `pasta`, segundo a decisao da pessoa.

    Sem conflito, o proprio nome. Com decisao "substituir", o proprio nome (o
    de la sera trocado). Com "renomear", o nome escolhido - que, se tambem ja
    existir, volta a ser conflito. Sem decisao, None e o conflito vai para
    `pendentes`. `ocupados` sao nomes (minusculos) ja reservados neste mesmo
    pedido, para dois arquivos do lote nao caírem no mesmo nome.
    """
    ocupados = ocupados if ocupados is not None else set()
    extensao = Path(nome).suffix
    d = decisoes.get(nome) or {}
    final = nome
    if d.get("acao") == "renomear":
        final = limpar(d.get("nome"), extensao) or nome
    # A decisao ja foi usada por outro arquivo deste mesmo pedido (dois com o
    # mesmo nome, de pastas diferentes): o seguinte ganha o proximo nome
    # livre, em vez de perguntar de novo pela mesma chave.
    if d and final.lower() in ocupados:
        final = livre(pasta, final, ocupados)
    existe = (pasta / final).exists() or final.lower() in ocupados
    if existe and not (d.get("acao") == "substituir" and final == nome):
        pendentes.append({
            "nome": nome,
            "existente": final,
            "sugestao": livre(pasta, final, ocupados),
            "pasta": str(pasta),
            "pasta_curta": pasta.name or str(pasta),
        })
        return None
    ocupados.add(final.lower())
    return pasta / final


def livre(pasta: Path, nome: str, ocupados: set | None = None) -> str:
    """O primeiro "nome (n).ext" que nao existe em `pasta` - a sugestao."""
    ocupados = ocupados or set()
    base, sufixo = Path(nome).stem, Path(nome).suffix
    candidato = nome
    n = 2
    while (pasta / candidato).exists() or candidato.lower() in ocupados:
        candidato = f"{base} ({n}){sufixo}"
        n += 1
        if n > 999:
            return f"{base} ({datetime.now():%Y%m%d%H%M%S}){sufixo}"
    return candidato


def conferir(pendentes: list) -> None:
    """Havendo conflito sem decisao, nada foi gravado: a tela pergunta."""
    if pendentes:
        raise NomeRepetido(pendentes)
