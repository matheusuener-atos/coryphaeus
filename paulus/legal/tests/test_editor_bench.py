"""
O banco de provas do editor confere o que diz conferir (docs/PLANO-EDITOR.md, E0).

  - o corpus: seis documentos, todo bloco com nome fixo, e as 62 tarefas
    apontando para blocos que existem;
  - o gabarito de cada tarefa se aplica sem falha e tira 100%;
  - os sistemas ruins de propósito são pegos: a troca em todas as ocorrências
    (dano colateral: "só na cláusula do foro" trocou o contrato inteiro), o
    texto novo no fim (lugar e ordem), a numeração que não segue a cláusula
    nova;
  - o editor de antes (adaptador "hoje"), com um modelo falso: a troca curta
    em todo o documento dá dano colateral, o "acrescentar" vai para o fim, e
    a marca dele não é reversível (o texto trocado sumia);
  - a renumeração não conta como dano quando a tarefa mexe na numeração, e
    conta quando não mexe;
  - pergunta: o documento não pode mudar e a resposta tem de apontar o bloco.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_editor_bench.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tools" / "bancada_editor"))

import adaptadores as A  # noqa: E402
import bancada  # noqa: E402
import blocos as B  # noqa: E402
from tarefas import CATEGORIAS, TAREFAS, por_id  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def rodar(adaptador, tarefas=TAREFAS, modelo=None) -> list[dict]:
    return [bancada.avaliar(t, adaptador(t, modelo)) for t in tarefas]


def teste_corpus() -> None:
    print("o corpus e as tarefas")
    docs = {t.doc for t in TAREFAS}
    checar(len(docs) == 6 and len(TAREFAS) >= 60, "seis documentos e pelo menos 60 tarefas", (len(docs), len(TAREFAS)))
    checar(len({t.id for t in TAREFAS}) == len(TAREFAS), "id de tarefa único")
    checar({t.categoria for t in TAREFAS} == set(CATEGORIAS), "toda categoria tem tarefa")
    ruins = []
    for t in TAREFAS:
        ids = {b.id for b in bancada.documento(t.doc)}
        citados = set(t.mudam) | set(t.podem) | set(t.cita) | ({t.selecao["bloco"]} if t.selecao else set())
        if t.ordem:
            citados |= {t.ordem[1], t.ordem[2]}
        for op in t.gabarito:
            for chave in ("bloco", "depois_de", "antes_de"):
                if op.get(chave):
                    citados.add(op[chave])
            citados |= set(op.get("blocos") or []) if all(isinstance(x, str) for x in op.get("blocos") or []) else set()
        if citados - ids:
            ruins.append((t.id, sorted(citados - ids)))
    checar(not ruins, "toda tarefa aponta para blocos que existem", ruins)


def teste_gabarito() -> None:
    print("o gabarito tira 100%")
    res = rodar(A.gabarito)
    erros = [(r["id"], r["erro"]) for r in res if r["erro"]]
    checar(not erros, "todo gabarito se aplica sem falha", erros)
    falhou = [(r["id"], r.get("por_que")) for r in res if not r["acerto"]]
    checar(not falhou, "todas as tarefas certas", falhou[:4])
    s = bancada.resumo(res)
    checar(s["acerto"] == 100.0 and s["sem_dano"] == 100.0 and s["marcado"] == 100.0, "resumo 100%", s)


def teste_sistemas_ruins() -> None:
    print("os sistemas ruins são pegos")
    res = {r["id"]: r for r in rodar(A.troca_global)}
    checar(not res["cv-11"]["sem_dano"] and "b0a0002" in res["cv-11"]["por_que"]["danos"],
           "“só na cláusula do foro” trocado em tudo: dano colateral", res["cv-11"].get("por_que"))
    checar(not res["loc-05"]["numeracao"], "cláusula nova sem renumerar: numeração errada")
    res = {r["id"]: r for r in rodar(A.no_fim)}
    checar(not any(r["acerto"] for r in res.values()), "tudo no fim: nenhuma tarefa certa")
    checar(not res["loc-05"]["ordem"] and not res["loc-01"]["lugar"], "no fim: ordem e lugar errados")


def teste_hoje_com_modelo_falso() -> None:
    print("o editor de antes, com um modelo falso")
    # Troca curta que o modelo devolvia: "30 (trinta)" está no prazo e no parágrafo único.
    t = por_id("loc-12")
    modelo = A.ModeloFalso([json.dumps({"trocas": [{"de": "30 (trinta)", "para": "36 (trinta e seis)"}],
                                        "acrescentar": ""})])
    r = bancada.avaliar(t, A.hoje(t, modelo))
    checar(not r["sem_dano"] and "b0b0009" in r["por_que"].get("danos", []),
           "a troca em todas as ocorrências pega o parágrafo único (30 dias)", r.get("por_que"))
    checar(not r["marcado"], "a marca de antes não é reversível: o texto trocado sumia")
    checar(modelo.recebido and "Documento:" in modelo.recebido[0][-1]["content"], "a instrução de antes, com o documento")
    # A regra de antes ("mude X para Y") lia o pedido ao pé da letra.
    t = por_id("loc-01")
    r = bancada.avaliar(t, A.hoje(t, A.ModeloFalso([])))
    aceito = B.texto_puro(B.aceito(B.ler(A.hoje(t, A.ModeloFalso([])).html)))
    checar(not r["acerto"] and "O 24 meses é de" in aceito, "a regra de antes trocava “prazo da locação” por “24 meses”",
           aceito[:200])
    t = por_id("loc-05")
    modelo = A.ModeloFalso([json.dumps({"trocas": [], "acrescentar": "CLÁUSULA 3ª – DA MULTA\nO atraso implica multa."})])
    r = bancada.avaliar(t, A.hoje(t, modelo))
    checar(not r["ordem"] and not r["acerto"], "o acrescentar vai para o fim do documento", r.get("por_que"))
    t = por_id("cv-11")
    r = bancada.avaliar(t, A.hoje(t, A.ModeloFalso([])))
    checar(not r["sem_dano"], "a troca dita na frase era feita em todo o documento, mesmo “só na cláusula do foro”")
    t = por_id("loc-10")
    r = bancada.avaliar(t, A.hoje(t, A.ModeloFalso([])))
    checar(r["intacto"] and not r["aponta"], "pergunta: o documento fica, mas a resposta de antes não apontava o lugar")


def teste_regras_das_checagens() -> None:
    print("as regras das checagens")
    checar(bancada._so_numeracao("CLÁUSULA 3ª – DO ALUGUEL", "CLÁUSULA 4ª – DO ALUGUEL"), "cabeça renumerada é só numeração")
    checar(bancada._so_numeracao("CLÁUSULA TERCEIRA – DA POSSE", "CLÁUSULA QUARTA – DA POSSE"), "por extenso também")
    checar(bancada._so_numeracao("conforme a cláusula 2ª.", "conforme a cláusula 3ª."), "referência renumerada")
    checar(not bancada._so_numeracao("multa de 10%", "multa de 20%"), "outro número não é numeração")
    # Renumerar sem a tarefa mexer na numeração conta como dano.
    t = por_id("loc-01")
    blocos = bancada.documento("locacao")
    import edicao as ED
    r = ED.aplicar(blocos, t.gabarito + [{"op": "substituir", "bloco": "b0b0010", "de": "CLÁUSULA 3ª", "para": "CLÁUSULA 4ª"}],
                   rodada=1)
    res = bancada.avaliar(t, bancada.Saida(html=B.html(r.blocos), mudou=True))
    checar(not res["sem_dano"], "mexer na numeração sem a tarefa pedir é dano", res.get("por_que"))
    t = por_id("cv-09")
    res = bancada.avaliar(t, bancada.Saida(html=B.html(bancada.documento("compra_venda")), mudou=False, cita=["b0a0007"]))
    checar(res["acerto"], "pergunta respondida apontando o bloco certo")
    res = bancada.avaliar(t, bancada.Saida(html=B.html(bancada.documento("compra_venda")), mudou=True, cita=["b0a0007"]))
    checar(res["honesto"] is False, "dizer que mudou sem ter mudado não é honesto")


if __name__ == "__main__":
    teste_corpus()
    teste_gabarito()
    teste_sistemas_ruins()
    teste_hoje_com_modelo_falso()
    teste_regras_das_checagens()
    print()
    if _falhas:
        print(f"{len(_falhas)} falha(s): " + "; ".join(_falhas))
        sys.exit(1)
    print("todos os testes passaram")
