"""
Testes do registro de habilidades.

O registro virou a fonte unica do que o programa sabe fazer: a pagina, as
portas de entrada e os tipos de trabalho saem dele. Entrada inconsistente aqui
vira botao quebrado na tela.

    python tests/test_habilidades.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import habilidades  # noqa: E402
from habilidades import (  # noqa: E402
    EM_BREVE,
    GRUPOS,
    HABILIDADES,
    PRECISA_ASSISTENTE,
    PRECISA_DOCUMENTOS,
    PRONTA,
    ROTULOS_PRECISA,
    contagem,
    obter,
    por_grupo,
)

# Acoes que a interface sabe abrir. Habilidade pronta com acao fora desta
# lista vira botao "Usar" que nao faz nada.
ACOES_CONHECIDAS = {"conversa", "busca", "anexar", "organizacao"}

_falhas: list[str] = []


def checar(condicao: bool, descricao: str) -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        _falhas.append(descricao)


def test_consistencia() -> None:
    print("\nconsistencia do registro")
    ids = [h.id for h in HABILIDADES]
    checar(len(ids) == len(set(ids)), "nenhum id repetido")
    checar(all(h.grupo in GRUPOS for h in HABILIDADES), "todo grupo declarado existe em GRUPOS")
    checar(all(h.estado in (PRONTA, EM_BREVE) for h in HABILIDADES), "estado sempre pronta ou em_breve")
    checar(all(h.nome and h.resumo for h in HABILIDADES), "toda habilidade tem nome e resumo")

    prontas = [h for h in HABILIDADES if h.estado == PRONTA]
    checar(
        all(h.acao in ACOES_CONHECIDAS for h in prontas),
        "habilidade pronta abre uma acao que a interface conhece",
    )
    checar(
        all(not h.acao for h in HABILIDADES if h.estado == EM_BREVE),
        "habilidade que nao existe nao oferece acao",
    )
    checar(
        all(p in ROTULOS_PRECISA for h in HABILIDADES for p in h.precisa),
        "todo requisito tem rotulo em portugues",
    )
    checar(all(h.demora for h in prontas), "habilidade pronta declara quanto demora")


def test_disponibilidade() -> None:
    print("\ndisponibilidade conforme o estado da maquina")
    tudo = por_grupo({PRECISA_DOCUMENTOS: True, PRECISA_ASSISTENTE: True})
    achatado = [h for g in tudo for h in g["habilidades"]]

    perguntar = next(h for h in achatado if h["id"] == "perguntar")
    checar(perguntar["utilizavel"], "com documento e assistente, perguntar e utilizavel")
    checar(not perguntar["faltando"], "nada faltando quando tudo esta disponivel")

    sem_docs = por_grupo({PRECISA_DOCUMENTOS: False, PRECISA_ASSISTENTE: True})
    achatado2 = [h for g in sem_docs for h in g["habilidades"]]
    p2 = next(h for h in achatado2 if h["id"] == "perguntar")
    checar(not p2["utilizavel"], "sem documento aberto, perguntar nao e utilizavel")
    checar("documentos abertos" in p2["faltando"], "diz em portugues o que falta")

    organizar = next(h for h in achatado2 if h["id"] == "organizar")
    checar(organizar["utilizavel"], "organizar nao depende de documento ja aberto")

    sem_nada = por_grupo({})
    achatado3 = [h for g in sem_nada for h in g["habilidades"]]
    checar(
        all(not h["utilizavel"] for h in achatado3 if h["precisa"]),
        "sem informacao de disponibilidade, nada que exige requisito e oferecido",
    )

    futuras = [h for h in achatado if h["estado"] == EM_BREVE]
    checar(bool(futuras), "existe habilidade marcada como futura")
    checar(all(not h["utilizavel"] for h in futuras), "habilidade futura nunca aparece utilizavel")


def test_agrupamento() -> None:
    print("\nagrupamento e contagem")
    grupos = por_grupo({PRECISA_DOCUMENTOS: True, PRECISA_ASSISTENTE: True})
    nomes = [g["grupo"] for g in grupos]

    checar(nomes == [g for g in GRUPOS if g in nomes], "grupos saem na ordem declarada")
    checar(all(g["habilidades"] for g in grupos), "nenhum grupo vazio e devolvido")

    total_listado = sum(len(g["habilidades"]) for g in grupos)
    checar(total_listado == len(HABILIDADES), "toda habilidade aparece em algum grupo")

    c = contagem()
    checar(c["total"] == len(HABILIDADES), "contagem total confere")
    checar(c["prontas"] == sum(1 for h in HABILIDADES if h.estado == PRONTA), "contagem de prontas confere")
    checar(c["prontas"] < c["total"], "ha habilidade ainda nao entregue - o catalogo nao mente")


def test_obter() -> None:
    print("\nbusca por id")
    checar(obter("organizar") is not None, "acha habilidade existente")
    checar(obter("nao-existe") is None, "id desconhecido devolve None")
    checar(obter("") is None, "id vazio devolve None")


def main() -> int:
    print("=" * 55)
    print("  PAULUS - testes do registro de habilidades")
    print("=" * 55)

    test_consistencia()
    test_disponibilidade()
    test_agrupamento()
    test_obter()

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print(f"  todos os testes passaram ({len(HABILIDADES)} habilidades no registro)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
