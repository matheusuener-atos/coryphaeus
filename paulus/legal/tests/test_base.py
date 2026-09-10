"""
Testes da base local, dos cadastros e das tarefas.

A base guarda o que a pessoa digitou - cadastro de cliente, tarefa com prazo.
Perder isso e diferente de perder um indice, que se reconstroi lendo os
arquivos de novo. Por isso as checagens aqui insistem em migracao, vinculo e
apagamento.

    python tests/test_base.py
"""

from __future__ import annotations

import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import base as modulo_base  # noqa: E402
from base import Base  # noqa: E402
from cadastros import Cadastros  # noqa: E402
from tarefas import Tarefas  # noqa: E402

_falhas: list[str] = []


def checar(condicao: bool, descricao: str) -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        _falhas.append(descricao)


def _dia(delta: int) -> str:
    return (date.today() + timedelta(days=delta)).isoformat()


# ------------------------------------------------------------------ migracoes


def test_migracoes() -> None:
    print("\nmigracoes")
    nomes = [n for n, _ in modulo_base.MIGRACOES]
    checar(len(nomes) == len(set(nomes)), "nenhuma migracao com nome repetido")

    with tempfile.TemporaryDirectory() as tmp:
        caminho = Path(tmp) / "p.db"
        b = Base(caminho)
        checar(b.contar("migracoes") == len(nomes), "todas as migracoes aplicadas na criacao")
        checar(b.migrar() == [], "rodar de novo nao reaplica nada")

        tabelas = {
            l["name"]
            for l in b.buscar("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        for esperada in ("cadastros", "tarefas", "etapas", "vinculos"):
            checar(esperada in tabelas, f"tabela {esperada} existe")

        colunas = {c["name"] for c in b.buscar("PRAGMA table_info(tarefas)")}
        checar("meu_dia" in colunas, "migracao posterior acrescentou a coluna meu_dia")
        b.fechar()

    # Base de uma versao antiga: so o que falta deve rodar.
    with tempfile.TemporaryDirectory() as tmp:
        caminho = Path(tmp) / "antiga.db"
        guardadas = modulo_base.MIGRACOES
        try:
            modulo_base.MIGRACOES = guardadas[:2]
            antiga = Base(caminho)
            antiga.fechar()

            modulo_base.MIGRACOES = guardadas
            nova = Base(caminho)
            colunas = {c["name"] for c in nova.buscar("PRAGMA table_info(tarefas)")}
            checar("meu_dia" in colunas, "base antiga recebe so as migracoes que faltavam")
            checar(nova.contar("migracoes") == len(guardadas), "o registro fica completo")
            nova.fechar()
        finally:
            modulo_base.MIGRACOES = guardadas


# ------------------------------------------------------------------ cadastros


def test_cadastros() -> None:
    print("\ncadastros")
    with tempfile.TemporaryDirectory() as tmp:
        b = Base(Path(tmp) / "p.db")
        c = Cadastros(b)

        i = c.salvar({
            "nome": "  Cooperativa Brasileira de Mineradores  ",
            "tipo": "cliente",
            "documento": "00.000.000/0001-00",
            "dia_vencimento": "12",
        })
        checar(c.obter(i)["nome"] == "Cooperativa Brasileira de Mineradores", "nome vem limpo de espaco")
        checar(c.obter(i)["dia_vencimento"] == 12, "numero vem como numero")

        c.salvar({"nome": "Fornecedor A", "tipo": "despesa"})
        checar(c.contagem()["cliente"] == 1 and c.contagem()["despesa"] == 1, "contagem por tipo")

        checar(len(c.listar(termo="00.000.000")) == 1, "acha por documento")
        checar(len(c.listar(termo="cooperativa")) == 1, "acha por nome")
        checar(len(c.listar(tipo="despesa")) == 1, "filtra por tipo")

        c.salvar({"nome": "Cooperativa Brasileira de Mineradores", "documento": "00.000.000/0001-00",
                  "telefone": "(62) 90000-0000"}, id_=i)
        checar(c.obter(i)["telefone"] == "(62) 90000-0000", "editar nao cria ficha nova")
        checar(c.contagem()["cliente"] == 1, "continua sendo um cliente so")

        erro = False
        try:
            c.salvar({"nome": "   "})
        except ValueError:
            erro = True
        checar(erro, "cadastro sem nome e recusado")

        c.vincular(i, "sha1", "contrato.pdf")
        c.vincular(i, "sha1", "contrato.pdf")
        checar(len(c.documentos_de(i)) == 1, "vincular o mesmo documento duas vezes nao duplica")

        c.apagar(i)
        checar(c.obter(i) is None, "ficha apagada")
        checar(b.contar("vinculos") == 0, "vinculos da ficha vao junto")
        b.fechar()


def test_sugestoes_de_cadastro() -> None:
    """
    O que faz a tela nascer meio pronta: quem aparece nos documentos e ainda
    nao tem ficha.
    """
    print("\nsugestoes vindas dos documentos")
    import json

    with tempfile.TemporaryDirectory() as tmp:
        b = Base(Path(tmp) / "p.db")
        c = Cadastros(b)

        cache = Path(tmp) / "classificacao.json"
        cache.write_text(json.dumps({
            "versao": 3,
            "itens": {
                "a": {"nome": "contrato1.pdf", "sha1": "a",
                      "partes": ["ACME LTDA", "Norte Solucoes"],
                      "documentos": ["12.345.678/0001-90", "98.765.432/0001-10"]},
                "b": {"nome": "contrato2.pdf", "sha1": "b",
                      "partes": ["ACME LTDA", "Bela Vista"], "documentos": []},
            },
        }, ensure_ascii=False), encoding="utf-8")

        s = c.sugestoes(cache)
        nomes = [x["nome"] for x in s]
        checar(len(s) == 3, f"tres partes distintas sugeridas (achou {len(s)})")
        checar(nomes[0] == "ACME LTDA", "quem aparece mais vem primeiro")
        checar(s[0]["aparicoes"] == 2, "conta em quantos documentos apareceu")
        checar(s[0]["documento"] == "12.345.678/0001-90", "traz o CPF/CNPJ que veio junto")
        checar(len(s[0]["arquivos"]) == 2, "diz de quais arquivos veio")

        c.salvar({"nome": "acme ltda"})
        depois = [x["nome"] for x in c.sugestoes(cache)]
        checar("ACME LTDA" not in depois, "quem ja tem ficha some da sugestao, mesmo com outra caixa")

        checar(c.sugestoes(Path(tmp) / "nao-existe.json") == [], "sem cache, sem sugestao")
        b.fechar()


# -------------------------------------------------------------------- tarefas


def test_tarefas() -> None:
    print("\ntarefas")
    with tempfile.TemporaryDirectory() as tmp:
        b = Base(Path(tmp) / "p.db")
        c, t = Cadastros(b), Tarefas(b)
        cliente = c.salvar({"nome": "Fornecedor A"})

        vencida = t.salvar({"titulo": "Enviar aviso", "prazo": _dia(-3), "cadastro_id": cliente})
        de_hoje = t.salvar({"titulo": "Conferir apolice", "prazo": _dia(0)})
        adiante = t.salvar({"titulo": "Aprovar folha", "prazo": _dia(5)})
        sem_prazo = t.salvar({"titulo": "Ligar para o cartorio", "importante": True})

        contagens = t.contagens()
        checar(contagens["meu_dia"] == 2, "meu dia traz vencida e de hoje, nao a de daqui a 5 dias")
        checar(contagens["planejadas"] == 1, "a de daqui a 5 dias e planejada")
        checar(contagens["importante"] == 1, "importante e filtro proprio")

        # "Meu dia" e escolha da pessoa, nao consequencia do prazo.
        t.marcar_meu_dia(sem_prazo, True)
        checar(t.contagens()["meu_dia"] == 3, "tarefa sem prazo entra no dia quando a pessoa marca")
        t.marcar_meu_dia(sem_prazo, False)
        checar(t.contagens()["meu_dia"] == 2, "e sai quando ela desmarca")

        situacoes = {x["titulo"]: x["situacao"] for x in t.listar("todas")}
        checar(situacoes["Enviar aviso"] == "atrasada 3 dia(s)", "atraso dito em dias")
        checar(situacoes["Conferir apolice"] == "hoje", "prazo de hoje dito como hoje")
        checar(situacoes["Aprovar folha"] == "em 5 dias", "prazo futuro em dias")
        checar(situacoes["Ligar para o cartorio"] == "sem prazo", "sem prazo e dito, nao escondido")

        primeira = t.listar("meu_dia")[0]
        checar(primeira["titulo"] == "Enviar aviso", "a mais atrasada aparece em cima")
        checar(primeira["cadastro_nome"] == "Fornecedor A", "a tarefa mostra o cliente ligado")

        t.nova_etapa(vencida, "Conferir a clausula 7")
        etapa = t.nova_etapa(vencida, "Assinar e enviar")
        checar(len(t.obter(vencida)["etapas"]) == 2, "etapas guardadas na ordem")
        t.marcar_etapa(etapa, True)
        checar(t.obter(vencida)["etapas"][1]["feita"] == 1, "etapa marcada como feita")

        t.concluir(de_hoje)
        checar(t.contagens()["concluidas"] == 1, "concluir tira do aberto")
        checar(t.obter(de_hoje)["situacao"] == "concluída", "situacao vira concluida")
        t.concluir(de_hoje, False)
        checar(t.contagens()["concluidas"] == 0, "desmarcar devolve para o aberto")

        t.apagar(vencida)
        checar(t.obter(vencida) is None, "tarefa apagada")
        checar(b.contar("etapas") == 0, "as etapas dela vao junto")

        c.apagar(cliente)
        checar(t.obter(adiante) is not None, "apagar cliente nao apaga tarefa")
        b.fechar()


def test_sugestoes_de_tarefa() -> None:
    print("\nsugestoes de prazo")
    with tempfile.TemporaryDirectory() as tmp:
        b = Base(Path(tmp) / "p.db")
        t = Tarefas(b)

        docs = [
            {"nome": "contrato_a.pdf", "data": _dia(10), "cliente": "ACME", "sha1": "a", "tipo_rotulo": "Locacao"},
            {"nome": "contrato_b.pdf", "data": _dia(400), "cliente": "Norte", "sha1": "b", "tipo_rotulo": "NDA"},
            {"nome": "sem_data.pdf", "data": "", "cliente": "X", "sha1": "c", "tipo_rotulo": ""},
        ]
        s = t.sugerir(docs)
        checar(len(s) == 1, "so o documento com data dentro do prazo vira sugestao")
        checar(s[0]["arquivo"] == "contrato_a.pdf", "a sugestao aponta o arquivo de origem")
        checar(b.contar("tarefas") == 0, "sugerir nao cria tarefa nenhuma")

        t.salvar({"titulo": s[0]["titulo"], "prazo": s[0]["prazo"]})
        checar(t.sugerir(docs) == [], "o que ja virou tarefa nao e sugerido de novo")
        b.fechar()


def main() -> int:
    print("=" * 55)
    print("  PAULUS - base local, cadastros e tarefas")
    print("=" * 55)

    test_migracoes()
    test_cadastros()
    test_sugestoes_de_cadastro()
    test_tarefas()
    test_sugestoes_de_tarefa()

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
