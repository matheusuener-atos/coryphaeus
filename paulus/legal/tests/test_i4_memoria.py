"""
Portao da I4 - a memoria da conversa (src/memoria.py).

  - as perguntas de continuacao do conjunto (tools/demo/conjunto-demo.jsonl)
    herdam o sujeito da anterior, em cadeia;
  - as perguntas que nao sao continuacao nao mudam;
  - o historico leva os 2 ultimos pares e respeita ~600 tokens;
  - pela conversa: o modelo recebe os pares anteriores e a pergunta
    reescrita, e a conversa guarda o que a pessoa escreveu;
  - `ia.memoria` desligada volta ao de antes.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_i4_memoria.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-i4-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tools"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


class Msg:
    def __init__(self, autor, texto, interrompida=False):
        self.autor, self.texto, self.interrompida = autor, texto, interrompida


def test_reescrita() -> None:
    print("\na reescrita, no conjunto da demonstração")
    import medir
    import memoria

    conjunto = medir.ler_conjunto(medir.CONJUNTO_DEMO)
    assunto = None
    anterior = ""
    for p in conjunto:
        novo = memoria.reescrever(p["pergunta"], anterior, assunto)
        if p.get("continua"):
            sujeito = (assunto or ("", ""))[0]
            checar(novo != p["pergunta"] and sujeito and sujeito in novo,
                   f"“{p['pergunta']}” herda o sujeito", novo)
        else:
            checar(novo == p["pergunta"], f"“{p['pergunta']}” não muda", novo)
            assunto = memoria.assunto_de(p["pergunta"]) or assunto
        anterior = novo

    print("\no exemplo do contrato")
    checar(memoria.reescrever("e a multa?", "qual o prazo do contrato ACME?") == "qual a multa do contrato ACME?",
           "“e a multa?” vira “qual a multa do contrato ACME?”",
           memoria.reescrever("e a multa?", "qual o prazo do contrato ACME?"))
    checar(memoria.reescrever("e o contrato da Clínica?", "qual o valor do contrato de transporte?")
           == "e o contrato da Clínica?", "com sujeito próprio, não herda")
    checar(memoria.reescrever("e a multa?", "") == "e a multa?", "sem pergunta anterior, não muda")


def test_historico() -> None:
    print("\no histórico")
    import memoria

    longa = "A cláusula diz muita coisa. " * 200
    msgs = [Msg("pessoa", "primeira?"), Msg("paulus", longa),
            Msg("pessoa", "segunda?"), Msg("paulus", longa),
            Msg("pessoa", "terceira?"), Msg("paulus", "curta."),
            Msg("pessoa", "parada?"), Msg("paulus", "escrevia…", interrompida=True)]
    h = memoria.historico(msgs)
    checar([m["role"] for m in h] == ["user", "assistant", "user", "assistant"], "dois pares, na ordem",
           [m["role"] for m in h])
    checar(h[0]["content"] == "segunda?" and h[2]["content"] == "terceira?",
           "os dois últimos respondidos (a parada no meio não entra)", [m["content"][:20] for m in h])
    checar(memoria.tokens(h) <= memoria.LIMITE_TOKENS, f"cabe em 600 tokens ({memoria.tokens(h)})")
    checar(h[1]["content"].endswith("…"), "a resposta longa é cortada, e diz que foi")
    checar(memoria.historico([]) == [], "conversa nova: sem histórico")


class Anota:
    """O modelo de mentira que guarda o que recebeu."""

    model = "falso:1b"
    num_ctx = 16384
    host = "http://127.0.0.1:9"
    aceita_tarefa = True

    def __init__(self) -> None:
        self.pedidos: list[dict] = []

    def ask(self, question, context="", *, sistema="", ensinado="", stream=False, on_token=None, on_fase=None,
            parar=None, tarefa="", historico=None):
        self.pedidos.append({"pergunta": question, "historico": list(historico or [])})
        texto = "O foro é o da Comarca de Santarém." if "foro" in question else "O valor é R$ 18.500,00."
        if on_token:
            on_token(texto)
        return texto

    def digest(self, model=""):
        return ""


def test_na_conversa() -> None:
    print("\nna conversa")
    from fastapi.testclient import TestClient

    import api

    anota = Anota()
    api.estado.client = anota
    api.estado.cliente_para = lambda tarefa: anota
    api.estado.saber.ligada = False
    pasta = Path(api.estado.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "transporte.txt").write_text(
        "CONTRATO DE TRANSPORTE. Cláusula 2. O valor mensal é de R$ 18.500,00. "
        "Cláusula 6. Fica eleito o foro da Comarca de Santarém.", encoding="utf-8")
    (pasta / "locacao.txt").write_text(
        "CONTRATO DE LOCAÇÃO. O aluguel é de R$ 6.200,00. Foro da Comarca de Belém.", encoding="utf-8")
    api.estado.recarregar()
    c = TestClient(api.app, headers=api.cabecalho_local())

    def perguntar(id_: str, texto: str) -> list:
        r = c.post(f"/api/trabalhos/{id_}/perguntar", json={"pergunta": texto, "apenas": ["transporte.txt"], "documentos": True})
        return [l[7:] for l in r.text.splitlines() if l.startswith("event: ")]

    id_ = c.post("/api/trabalhos", json={"pedido": "teste"}).json()["id"]
    perguntar(id_, "qual o valor mensal do contrato de transporte?")
    perguntar(id_, "e o foro?")
    ultimo = anota.pedidos[-1]
    checar(ultimo["pergunta"] == "qual o foro do contrato de transporte?", "o modelo recebe a pergunta reescrita",
           ultimo["pergunta"])
    checar([m["role"] for m in ultimo["historico"]] == ["user", "assistant"]
           and "valor mensal" in ultimo["historico"][0]["content"], "e o par anterior como mensagens",
           ultimo["historico"])
    t = c.get(f"/api/trabalhos/{id_}").json()
    pessoa = [m["texto"] for m in (t.get("mensagens") or []) if m.get("autor") == "pessoa"]
    checar(pessoa[-1:] == ["e o foro?"], "a conversa guarda o que a pessoa escreveu", pessoa)

    print("\ncom a memória desligada")
    api.estado.prefs.dados.setdefault("ia", {})["memoria"] = False
    id2 = c.post("/api/trabalhos", json={"pedido": "teste"}).json()["id"]
    perguntar(id2, "qual o valor mensal do contrato de transporte?")
    perguntar(id2, "e o foro?")
    ultimo = anota.pedidos[-1]
    checar(ultimo["pergunta"] == "e o foro?" and not ultimo["historico"], "volta ao de antes", ultimo)
    api.estado.prefs.dados["ia"]["memoria"] = True


def main() -> int:
    print("=" * 55)
    print("  I4 - memoria da conversa")
    print("=" * 55)
    try:
        test_reescrita()
        test_historico()
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
