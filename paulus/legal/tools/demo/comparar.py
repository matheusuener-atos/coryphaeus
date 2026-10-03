"""
Duas rodadas do roteiro lado a lado (V1, docs/PLANO-NUVEM.md): o Ollama local
contra a nuvem, ou um modelo da nuvem contra outro, nas mesmas perguntas.

    venv\\Scripts\\python.exe tools\\demo\\comparar.py data\\demo\\roteiro-resultado.json data\\demo\\roteiro-resultado-deepinfra_meta_llama_llama_3.3_70b_instruct.json

Sem argumentos, compara todas as rodadas guardadas em data/demo. Mostra, por
pergunta, quem acertou e o tempo; no fim, o placar, a mediana do tempo e os
tokens da nuvem (o custo, pelos preços de referência do DeepInfra).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DEMO = RAIZ / "data" / "demo"
# Dólares por milhão de tokens (docs/PLANO-NUVEM.md; o pacote do dono, 01/10/2026).
PRECO = {"llama": (0.23, 0.40), "qwen": (0.23, 0.40)}


def _nome(arq: Path) -> str:
    n = arq.stem.replace("roteiro-resultado", "").lstrip("-")
    return n or "local (padrão)"


def _mediana(xs: list[float]) -> float:
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else 0.0


def main() -> int:
    arquivos = [Path(a) for a in sys.argv[1:]] or sorted(DEMO.glob("roteiro-resultado*.json"))
    if len(arquivos) < 2:
        print("preciso de duas rodadas (rode tools/demo/roteiro.py com e sem --nuvem)")
        return 1
    rodadas = {_nome(a): {r["pergunta"]: r for r in json.loads(a.read_text(encoding="utf-8"))} for a in arquivos}
    nomes = list(rodadas)
    perguntas = list(dict.fromkeys(p for r in rodadas.values() for p in r))
    largura = max(14, *(len(n) for n in nomes))
    print("pergunta".ljust(60) + "".join(n[:largura].rjust(largura + 2) for n in nomes))
    for p in perguntas:
        linha = (p[:57] + "...") if len(p) > 60 else p.ljust(60)
        for n in nomes:
            r = rodadas[n].get(p)
            cel = "—" if r is None else (("ok " if r["certo"] else "ERR") + f" {r['segundos']:5.1f}s")
            linha += cel.rjust(largura + 2)
        print(linha)
    print()
    for n in nomes:
        rs = [r for r in rodadas[n].values() if r["pergunta"] in perguntas]
        docs = [r for r in rs if r["caminho"] == "documentos"]
        tokens = sum(int(r.get("tokens") or 0) for r in rs)
        custo = ""
        if tokens:
            preco = next((v for k, v in PRECO.items() if k in n.lower()), None)
            if preco:
                # Sem a divisão entrada/saída na rodada: o teto (tudo pelo preço de saída).
                custo = f" · até US$ {tokens * preco[1] / 1e6:.3f} pelos {tokens:,} tokens".replace(",", ".")
        print(f"{n}: {sum(r['certo'] for r in rs)}/{len(rs)} certas (documentos {sum(r['certo'] for r in docs)}/{len(docs)})"
              f" · mediana {_mediana([r['segundos'] for r in docs]):.1f} s nos documentos{custo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
