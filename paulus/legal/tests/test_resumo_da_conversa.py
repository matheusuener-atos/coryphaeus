"""
O resumo da conversa longa (src/memoria.py, "o resumo da conversa longa").

  - so ha o que resumir quando um par sai da janela dos dois ultimos;
  - o pedido e incremental: o resumo de antes mais os pares que sairam;
  - resumo com numero que nao esta no texto de onde veio e descartado, e a
    falha pula as 3 perguntas seguintes;
  - conversa mudada (resposta retomada) invalida o resumo guardado;
  - pela conversa: o resumo e feito em segundo plano depois da resposta, e a
    pergunta seguinte o leva na frente do historico, como um par.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_resumo_da_conversa.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-resumo-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


class Msg:
    def __init__(self, autor, texto, interrompida=False):
        self.autor, self.texto, self.interrompida = autor, texto, interrompida


def _conversa(n: int) -> list[Msg]:
    saida = []
    for i in range(1, n + 1):
        saida += [Msg("pessoa", f"pergunta {i} sobre o contrato?"), Msg("paulus", f"Resposta {i}: o prazo é de {i * 10} dias.")]
    return saida


class Resumidor:
    def __init__(self, texto: str) -> None:
        self.texto = texto
        self.pedidos: list[dict] = []

    def ask(self, question, context="", **k):
        self.pedidos.append({"pergunta": question, **k})
        return self.texto


def test_regras() -> None:
    print("\nas regras do resumo")
    import memoria

    pares = memoria.pares_respondidos(_conversa(2))
    checar(not memoria.precisa_resumir({}, pares), "dois pares cabem na janela: nada a resumir")
    pares = memoria.pares_respondidos(_conversa(3))
    checar(memoria.precisa_resumir({}, pares), "o terceiro par empurra o primeiro para fora")

    ctx: dict = {}
    r = Resumidor("A pessoa perguntou do contrato e o prazo era de 10 dias.")
    checar(memoria.resumir(ctx, pares, r), "resumo aceito e gravado", ctx)
    checar(ctx["resumo_conversa"]["pares"] == 1 and not memoria.precisa_resumir(ctx, pares),
           "cobre o par que saiu", ctx)
    checar(r.pedidos[0].get("sistema") == memoria.SISTEMA_DO_RESUMO and "pergunta 1" in r.pedidos[0]["pergunta"]
           and "pergunta 3" not in r.pedidos[0]["pergunta"], "o pedido leva só o que saiu da janela",
           r.pedidos[0]["pergunta"])

    pares5 = memoria.pares_respondidos(_conversa(5))
    pedido = memoria.pedido_de_resumo(ctx, pares5)
    checar(pedido and "RESUMO ATÉ AQUI" in pedido["texto"] and "pergunta 1 " not in pedido["texto"]
           and "pergunta 2" in pedido["texto"] and "pergunta 3" in pedido["texto"] and "pergunta 4" not in pedido["texto"],
           "incremental: o resumo de antes mais os pares novos que saíram", pedido and pedido["texto"])

    h = memoria.historico(_conversa(5), resumo=memoria.resumo_vigente(ctx, pares5))
    checar([m["role"] for m in h] == ["user", "assistant"] * 3 and h[0]["content"] == memoria.PEDIDO_DO_RESUMO
           and h[1]["content"].startswith("A pessoa perguntou"), "o resumo vai na frente, como um par",
           [m["content"][:30] for m in h])

    print("\nnão inventa")
    ctx2: dict = {}
    inventou = Resumidor("O prazo da notificação vence em 2026-12-10, conforme o contrato.")
    checar(not memoria.resumir(ctx2, pares, inventou), "número que não está na conversa: descartado", ctx2)
    checar(ctx2["resumo_conversa"].get("pular") == memoria.PULAR_DEPOIS_DE_FALHA and not memoria.precisa_resumir(ctx2, pares),
           "a falha pula as próximas", ctx2)
    for _ in range(memoria.PULAR_DEPOIS_DE_FALHA):
        memoria.contar_pergunta(ctx2)
    checar(memoria.precisa_resumir(ctx2, pares), "depois de 3 perguntas tenta de novo", ctx2)
    checar(memoria.aceitar_resumo("O valor mensal é de R$ 19.980,00 desde o aditivo.", "o valor passou a 19.980")
           is not None, "R$ 19.980,00 e 19.980 são o mesmo número")
    checar(memoria.aceitar_resumo("ok", "x") is None, "resumo vazio não vale")

    class Quebrado:
        def ask(self, *a, **k):
            raise RuntimeError("o Ollama caiu")

    ctx3: dict = {}
    checar(not memoria.resumir(ctx3, pares, Quebrado()) and ctx3["resumo_conversa"].get("pular"),
           "modelo fora do ar conta como falha, sem exceção")

    print("\nconversa mudada")
    mudada = _conversa(3)
    mudada[1].texto = "Outra resposta, retomada."
    checar(memoria.resumo_vigente(ctx, memoria.pares_respondidos(mudada)) == "",
           "o par resumido mudou: o resumo guardado não vale mais")


class Falso:
    """O modelo de mentira: responde as perguntas e escreve o resumo quando pedido."""

    model = "falso:1b"
    num_ctx = 16384
    host = "http://127.0.0.1:9"
    aceita_tarefa = True

    def __init__(self) -> None:
        self.pedidos: list[dict] = []
        self.resumos = 0

    def ask(self, question, context="", *, sistema="", ensinado="", stream=False, on_token=None, on_fase=None,
            parar=None, tarefa="", historico=None, **k):
        import memoria

        if sistema == memoria.SISTEMA_DO_RESUMO:
            self.resumos += 1
            return "A conversa tratou do contrato de transporte: o valor mensal é de R$ 18.500,00."
        self.pedidos.append({"pergunta": question, "historico": list(historico or [])})
        texto = "O valor é R$ 18.500,00." if "valor" in question else "O foro é o da Comarca de Santarém."
        if on_token:
            on_token(texto)
        return texto

    def digest(self, model=""):
        return ""


def test_na_conversa() -> None:
    print("\nna conversa")
    from fastapi.testclient import TestClient

    import api

    falso = Falso()
    api.estado.client = falso
    api.estado.cliente_para = lambda tarefa, **k: falso
    api.estado.saber.ligada = False

    print("  só pela nuvem")
    from jobs import Trabalho

    t0 = Trabalho(id="x", titulo="x")
    checar(api._cliente_do_resumo(t0) is None, "sem a nuvem ligada para os resumos: não há resumo (não ocupa o modelo daqui)")
    import nuvem as nuvem_mod

    usa = nuvem_mod.usa
    nuvem_mod.usa = lambda estado, tarefa: True
    try:
        t0.contexto["resumo_so_aqui"] = True
        checar(api._cliente_do_resumo(t0) is None, "conversa com pergunta que ficou neste computador: não há resumo")
    finally:
        nuvem_mod.usa = usa
    # Daqui em diante, a nuvem dos resumos é o modelo falso.
    real = api._cliente_do_resumo
    api._cliente_do_resumo = lambda trabalho: falso
    pasta = Path(api.estado.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "transporte.txt").write_text(
        "CONTRATO DE TRANSPORTE. Cláusula 2. O valor mensal é de R$ 18.500,00. "
        "Cláusula 6. Fica eleito o foro da Comarca de Santarém.", encoding="utf-8")
    api.estado.recarregar()
    c = TestClient(api.app, headers=api.cabecalho_local())

    def perguntar(id_: str, texto: str) -> None:
        c.post(f"/api/trabalhos/{id_}/perguntar", json={"pergunta": texto, "apenas": ["transporte.txt"], "documentos": True})

    id_ = c.post("/api/trabalhos", json={"pedido": "teste"}).json()["id"]
    perguntas = ["qual o valor mensal do contrato de transporte?", "qual o foro do contrato de transporte?",
                 "qual o valor mensal do contrato de transporte, de novo?", "qual o foro, mais uma vez?"]
    for p in perguntas:
        perguntar(id_, p)
    fim = time.time() + 30
    t = api.estado.trabalhos.obter(id_)
    while ((t.contexto.get("resumo_conversa") or {}).get("pares") != 2 or api._resumindo) and time.time() < fim:
        time.sleep(0.3)
    checar(falso.resumos >= 1, "o resumo é feito em segundo plano", falso.resumos)
    checar((t.contexto.get("resumo_conversa") or {}).get("pares") == 2,
           "quatro perguntas: os dois pares que saíram estão no resumo, gravado na conversa", t.contexto)

    checar(t.contexto.get("resumo_so_aqui"), "a pergunta sem nuvem marca a conversa (o resumo real não sairia dela)")

    perguntar(id_, "qual o foro do contrato de transporte, de novo?")
    h = falso.pedidos[-1]["historico"]
    checar(len(h) == 6 and h[0]["content"] == __import__("memoria").PEDIDO_DO_RESUMO and "18.500" in h[1]["content"],
           "a pergunta seguinte leva o resumo e os dois últimos pares", [m["content"][:40] for m in h])
    api._cliente_do_resumo = real


def main() -> int:
    print("=" * 55)
    print("  o resumo da conversa longa")
    print("=" * 55)
    try:
        test_regras()
        test_na_conversa()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print("   -", f)
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
