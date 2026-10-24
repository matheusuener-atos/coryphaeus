"""
A medida do modelo (src/modelos.py, medir): várias rodadas, mediana e faixa.

  - três rodadas, cada uma com um texto diferente (o cache do Ollama não lê de graça);
  - leitura e escrita pela mediana, com a faixa do meio (25% a 75%);
  - a primeira palavra das rodadas mornas, e a da fria (que carrega) à parte;
  - as chaves de antes continuam: a tela, a calibração e o servidor leem as mesmas;
  - erro do Ollama no meio do texto vira erro de requisição, não medida falsa.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_medida_do_modelo.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
os.environ["PAULUS_DADOS"] = str(Path(tempfile.mkdtemp(prefix="paulus-medida-")) / "dados")
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


class Resposta:
    def __init__(self, linhas):
        self._linhas = linhas

    def raise_for_status(self):
        pass

    def iter_lines(self):
        for linha in self._linhas:
            yield json.dumps(linha).encode()


def ollama_falso(rodadas):
    """Cada rodada: (escrita tok/s, leitura tok/s, carregar s)."""
    pedidos = []

    def postar(url, json=None, stream=False, timeout=None):
        escrita, leitura, carregar = rodadas[len(pedidos)]
        pedidos.append(json)
        return Resposta([
            {"response": "Procuração", "done": False},
            {"response": " é...", "done": False},
            {"response": "", "done": True, "eval_count": 60, "eval_duration": int(60 / escrita * 1e9),
             "prompt_eval_count": 1500, "prompt_eval_duration": int(1500 / leitura * 1e9),
             "load_duration": int(carregar * 1e9)},
        ])
    return postar, pedidos


def main() -> int:
    print("=" * 55)
    print("  a medida do modelo")
    print("=" * 55)
    import maquina
    import modelos

    maquina.na_placa = lambda host, nome: 0.0
    postar, pedidos = ollama_falso([(8.0, 50.0, 6.0), (10.0, 60.0, 0.0), (9.0, 55.0, 0.0)])
    m = modelos.medir("http://falso", "llama3.2:3b", postar=postar)

    checar(len(pedidos) == 3 and m["rodadas"] == 3, "três rodadas", m.get("rodadas"))
    checar(len({p["prompt"] for p in pedidos}) == 3 and all(p["stream"] for p in pedidos),
           "cada rodada com um texto diferente, em streaming")
    checar(m["tokens_por_segundo"] == 9.0 and m["leitura_tokens_por_segundo"] == 55.0,
           "escrita e leitura pela mediana", (m["tokens_por_segundo"], m["leitura_tokens_por_segundo"]))
    checar(m["faixas"]["escrita"] == [8.5, 9.5] and m["faixas"]["leitura"] == [52.5, 57.5],
           "com a faixa do meio", m["faixas"])
    checar(m["carregar_s"] == 6.0 and m["carregar_morno_s"] == 0.0, "carregar: a fria e a morna à parte",
           (m["carregar_s"], m["carregar_morno_s"]))
    checar(m["primeira_palavra_s"] >= 0 and "primeira_palavra_fria_s" in m and len(m["faixas"]["primeira_palavra"]) == 2,
           "a primeira palavra, mornas e fria", m)
    checar(m["na_placa"] == 0.0 and m["tokens_lidos"] == 1500 and m["quando"],
           "as chaves de antes continuam")

    amostra = maquina.amostra({"id": "x"}, {"nome": "llama3.2:3b", "gb": 2.0, "parametros": "3.2B"}, m)
    checar(amostra["escrita_tps"] == 9.0 and amostra["leitura_tps"] == 55.0, "a calibração lê a mediana", amostra)

    postar, pedidos = ollama_falso([(8.0, 50.0, 1.0)])
    m = modelos.medir("http://falso", "llama3.2:3b", rodadas=1, postar=postar)
    checar(m["rodadas"] == 1 and m["tokens_por_segundo"] == 8.0 and m["carregar_morno_s"] is None,
           "uma rodada só: sem morna para separar", m)

    def quebrado(url, json=None, stream=False, timeout=None):
        return Resposta([{"error": "model not found"}])

    try:
        modelos.medir("http://falso", "nao-existe", postar=quebrado)
        checar(False, "erro do Ollama vira erro de requisição")
    except Exception as exc:  # noqa: BLE001
        import requests

        checar(isinstance(exc, requests.RequestException) and "model not found" in str(exc),
               "erro do Ollama vira erro de requisição (a rota responde 503)", exc)

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
