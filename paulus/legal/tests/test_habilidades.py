"""
Testes do registro de habilidades.

Cobrem duas coisas: se os modulos reais da pasta `habilidades/` estao
consistentes, e se o carregador aguenta arquivo quebrado sem derrubar o
programa - que e a promessa toda da modularizacao.

    python tests/test_habilidades.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import registro  # noqa: E402
from habilidade_base import (  # noqa: E402
    COM_PROBLEMA,
    EM_BREVE,
    GRUPOS,
    PRECISA_ASSISTENTE,
    PRECISA_DOCUMENTOS,
    PRONTA,
    ROTULOS_PRECISA,
    Contexto,
    Ponte,
)

PASTA = RAIZ / "habilidades"

# Acoes que a interface sabe abrir. Habilidade pronta apontando para outra
# coisa vira botao "Usar" que nao faz nada.
ACOES_CONHECIDAS = {"conversa", "busca", "anexar", "organizacao"}

_falhas: list[str] = []


def checar(condicao: bool, descricao: str) -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        _falhas.append(descricao)


def _escrever(pasta: Path, nome: str, conteudo: str) -> None:
    (pasta / nome).write_text(conteudo, encoding="utf-8")


# ------------------------------------------------------------ modulos reais


def test_modulos_do_projeto() -> None:
    print("\nmodulos em habilidades/")
    r = registro.carregar(PASTA)

    checar(bool(r.habilidades), "a pasta tem habilidades")
    checar(not r.problemas, f"nenhum modulo com problema (achou {len(r.problemas)})")

    ids = [h.id for h in r.habilidades]
    checar(len(ids) == len(set(ids)), "nenhum id repetido")
    checar(all(h.grupo in GRUPOS for h in r.habilidades), "todo grupo existe em GRUPOS")
    checar(all(h.nome and h.resumo for h in r.habilidades), "toda habilidade tem nome e resumo")
    checar(all(h.arquivo for h in r.habilidades), "toda habilidade sabe de que arquivo veio")

    prontas = [h for h in r.habilidades if h.estado == PRONTA]
    checar(bool(prontas), "existe habilidade pronta")
    checar(all(h.executavel for h in prontas), "toda habilidade pronta tem executar()")
    checar(all(h.acao in ACOES_CONHECIDAS for h in prontas), "acao conhecida pela interface")
    checar(all(h.demora for h in prontas), "habilidade pronta declara quanto demora")

    futuras = [h for h in r.habilidades if h.estado == EM_BREVE]
    checar(bool(futuras), "o catalogo admite o que ainda nao existe")
    checar(all(not h.executavel for h in futuras), "habilidade futura nunca e executavel")
    checar(all(not h.acao for h in futuras), "habilidade futura nao oferece acao")

    checar(
        all(p in ROTULOS_PRECISA for h in r.habilidades for p in h.precisa),
        "todo requisito tem rotulo em portugues",
    )


def test_disponibilidade() -> None:
    print("\ndisponibilidade conforme o estado da maquina")
    r = registro.carregar(PASTA)

    tudo = [h for g in r.por_grupo({PRECISA_DOCUMENTOS: True, PRECISA_ASSISTENTE: True})
            for h in g["habilidades"]]
    perguntar = next(h for h in tudo if h["id"] == "perguntar")
    checar(perguntar["utilizavel"], "com documento e assistente, perguntar e utilizavel")
    checar(not perguntar["faltando"], "nada faltando quando tudo esta disponivel")

    sem_docs = [h for g in r.por_grupo({PRECISA_DOCUMENTOS: False, PRECISA_ASSISTENTE: True})
                for h in g["habilidades"]]
    p2 = next(h for h in sem_docs if h["id"] == "perguntar")
    checar(not p2["utilizavel"], "sem documento aberto, perguntar nao e utilizavel")
    checar("documentos abertos" in p2["faltando"], "diz em portugues o que falta")

    organizar = next(h for h in sem_docs if h["id"] == "organizar")
    checar(organizar["utilizavel"], "organizar nao depende de documento ja aberto")

    sem_nada = [h for g in r.por_grupo({}) for h in g["habilidades"]]
    checar(
        all(not h["utilizavel"] for h in sem_nada if h["precisa"]),
        "sem informacao de disponibilidade, nada que exige requisito e oferecido",
    )

    c = r.contagem()
    checar(c["total"] == len(r.habilidades), "contagem total confere")
    checar(c["prontas"] < c["total"], "ha habilidade nao entregue - o catalogo nao mente")


# ------------------------------------------------------- carregador robusto


def test_arquivo_quebrado_nao_derruba() -> None:
    """
    A promessa da modularizacao: mexer num modulo nao pode quebrar o programa.
    Cada forma de erro vira uma entrada marcada, e o resto continua de pe.
    """
    print("\ncarregador aguenta arquivo quebrado")
    with tempfile.TemporaryDirectory() as tmp:
        pasta = Path(tmp)

        _escrever(pasta, "boa.py", (
            "from habilidade_base import Contexto, Habilidade\n"
            "HABILIDADE = Habilidade(id='boa', nome='Boa', resumo='r', grupo='Documentos',\n"
            "                        acao='busca', demora='rapido')\n"
            "def executar(ctx: Contexto):\n"
            "    return {'ok': True}\n"
        ))
        _escrever(pasta, "sintaxe.py", "isto nao e python (((\n")
        _escrever(pasta, "sem_declaracao.py", "X = 1\n")
        _escrever(pasta, "estoura.py", "raise RuntimeError('estouro no import')\n")
        _escrever(pasta, "grupo_ruim.py", (
            "from habilidade_base import Habilidade\n"
            "HABILIDADE = Habilidade(id='g', nome='G', resumo='r', grupo='Inventado')\n"
        ))
        _escrever(pasta, "sem_executar.py", (
            "from habilidade_base import Habilidade\n"
            "HABILIDADE = Habilidade(id='s', nome='S', resumo='r', grupo='Documentos')\n"
        ))
        _escrever(pasta, "_ajudante.py", "NAO_E_HABILIDADE = True\n")

        r = registro.carregar(pasta)

        boa = r.obter("boa")
        checar(boa is not None and boa.executavel, "a habilidade boa carregou apesar das quebradas")
        checar(boa.executar(Contexto()) == {"ok": True}, "e roda normalmente")

        problemas = {Path(h.arquivo).name: h.problema for h in r.problemas}
        checar("sintaxe.py" in problemas, "erro de sintaxe vira problema, nao exception")
        checar("sem_declaracao.py" in problemas, "arquivo sem HABILIDADE vira problema")
        checar("estoura.py" in problemas, "erro no import vira problema")
        checar("grupo_ruim.py" in problemas, "grupo inexistente vira problema")
        checar("sem_executar.py" in problemas, "pronta sem executar() vira problema")
        checar(all(problemas.values()), "todo problema tem mensagem explicando")
        checar(
            not any("ajudante" in h.arquivo for h in r.habilidades),
            "arquivo com _ no inicio e ignorado, nao vira habilidade",
        )
        checar(r.contagem()["com_problema"] == 5, "conta os cinco quebrados")

        grupos = [g["grupo"] for g in r.por_grupo({})]
        checar("Com problema" in grupos, "quebradas aparecem num grupo proprio na tela")


def test_id_repetido() -> None:
    print("\ndois modulos com o mesmo id")
    with tempfile.TemporaryDirectory() as tmp:
        pasta = Path(tmp)
        corpo = (
            "from habilidade_base import Contexto, Habilidade\n"
            "HABILIDADE = Habilidade(id='mesmo', nome='{nome}', resumo='r',\n"
            "                        grupo='Documentos', acao='busca', demora='rapido')\n"
            "def executar(ctx: Contexto):\n"
            "    return {{'de': '{nome}'}}\n"
        )
        _escrever(pasta, "a_primeira.py", corpo.format(nome="Primeira"))
        _escrever(pasta, "b_segunda.py", corpo.format(nome="Segunda"))

        r = registro.carregar(pasta)
        checar(len(r.habilidades) == 2, "as duas entram na lista")
        checar(len(r.problemas) == 1, "a segunda e marcada como problema")
        checar(
            "já é usado" in r.problemas[0].problema,
            "o conflito e explicado em vez de resolvido em silencio",
        )
        checar(r.obter("mesmo").nome == "Primeira", "a primeira continua utilizavel")


def test_pasta_ausente() -> None:
    print("\npasta de habilidades ausente")
    r = registro.carregar(Path("pasta/que/nao/existe"))
    checar(r.habilidades == [], "nao quebra, so devolve lista vazia")
    checar(r.contagem()["total"] == 0, "contagem zerada")


# -------------------------------------------------------------------- ponte


def test_ponte() -> None:
    print("\nponte de callback para iterador")

    def trabalho(empurrar):
        for i in range(5):
            empurrar(i)
        return "terminou"

    ponte = Ponte(trabalho)
    recebidos = list(ponte)
    checar(recebidos == [0, 1, 2, 3, 4], "entrega os avisos na ordem")
    checar(ponte.resultado == "terminou", "guarda o valor de retorno")

    def estoura(empurrar):
        empurrar("antes")
        raise ValueError("falhou no meio")

    ponte2 = Ponte(estoura)
    itens, erro = [], None
    try:
        for item in ponte2:
            itens.append(item)
    except ValueError as exc:
        erro = exc
    checar(itens == ["antes"], "entrega o que veio antes do erro")
    checar(erro is not None, "o erro chega em quem consome, nao some na thread")

    ponte3 = Ponte(lambda empurrar: "sem avisos")
    naoconsumida = True
    try:
        _ = ponte3.resultado
        naoconsumida = False
    except RuntimeError:
        pass
    checar(naoconsumida, "pedir resultado antes de consumir e erro explicito")


# ------------------------------------------------------------- destinos


def test_destinos() -> None:
    """
    O menu do manual do sistema. Destino pronto tem que apontar para algo que a
    interface sabe abrir; destino ainda nao construido tem que dizer o que
    falta, senao vira botao morto sem explicacao.
    """
    print("\ndestinos do menu")
    import destinos

    ABRE_CONHECIDO = {"conversa", "biblioteca", "habilidades", "maquina", "organizar"}

    ids = [d.id for d in destinos.DESTINOS]
    checar(len(ids) == len(set(ids)), "nenhum id de destino repetido")
    checar(len(destinos.DESTINOS) == 20, f"20 destinos, como o manual (achou {len(ids)})")
    checar(
        all(d.grupo in destinos.GRUPOS for d in destinos.DESTINOS),
        "todo destino esta num dos quatro grupos",
    )
    checar(all(d.nome and d.resolve for d in destinos.DESTINOS), "todo destino diz o que resolve")

    prontos = [d for d in destinos.DESTINOS if d.pronta]
    checar(bool(prontos), "existe destino com motor")
    checar(
        all(d.abre in ABRE_CONHECIDO for d in prontos),
        "destino pronto abre algo que a interface conhece",
    )

    adiante = [d for d in destinos.DESTINOS if not d.pronta]
    checar(bool(adiante), "o menu admite o que ainda nao existe")
    checar(all(not d.abre for d in adiante), "destino nao construido nao finge ter tela")
    checar(all(d.precisa for d in adiante), "destino nao construido diz o que falta")

    c = destinos.contagem()
    checar(c["prontas"] < c["total"], "a contagem nao mente sobre o que existe")
    checar(destinos.obter("conversa") is not None, "acha destino por id")
    checar(destinos.obter("nao-existe") is None, "id desconhecido devolve None")


def main() -> int:
    print("=" * 55)
    print("  PAULUS - testes do registro de habilidades")
    print("=" * 55)

    test_modulos_do_projeto()
    test_disponibilidade()
    test_arquivo_quebrado_nao_derruba()
    test_id_repetido()
    test_pasta_ausente()
    test_ponte()
    test_destinos()

    total = len(registro.carregar(PASTA).habilidades)
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print(f"  todos os testes passaram ({total} habilidades na pasta)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
