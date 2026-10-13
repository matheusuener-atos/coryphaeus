"""
Mede o editor no banco de provas (docs/PLANO-EDITOR.md, E0 e E9).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/medir_editor.py --adaptador gabarito
    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/medir_editor.py --adaptador hoje --modelo nuvem
    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/medir_editor.py --adaptador agente --modelo nuvem --nivel juiz
    ... --so loc-01,cv-03      só essas tarefas
    ... --dados <pasta>        a pasta de dados de onde vem a chave da nuvem (só leitura)

O resultado vai para tools/bancada_editor/resultados/<data>-<adaptador>-<modelo>.json,
uma linha por tarefa na tela e o resumo no fim. Nada é gravado na pasta de dados.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

LEGAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LEGAL / "src"))
sys.path.insert(0, str(LEGAL / "tools" / "bancada_editor"))

import adaptadores  # noqa: E402
import bancada  # noqa: E402
from tarefas import TAREFAS  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--adaptador", default="gabarito", choices=sorted(adaptadores.ADAPTADORES))
    p.add_argument("--modelo", default="", help="nuvem | local[:nome] | (vazio: sem modelo)")
    p.add_argument("--nivel", default="advogado")
    p.add_argument("--so", default="")
    p.add_argument("--dados", default=str(LEGAL / "data"))
    p.add_argument("--saida", default="")
    a = p.parse_args()

    modelo = None
    if a.modelo == "nuvem":
        modelo = adaptadores.ModeloNuvem(a.dados, nivel=a.nivel)
    elif a.modelo.startswith("local"):
        modelo = adaptadores.ModeloLocal(a.modelo.split(":", 1)[1] if ":" in a.modelo else "llama3.2:3b")
    elif a.adaptador in ("hoje", "agente"):
        print("este adaptador precisa de --modelo nuvem ou --modelo local")
        return 2

    escolhidas = [t for t in TAREFAS if not a.so or t.id in a.so.split(",")]
    fazer = adaptadores.ADAPTADORES[a.adaptador]
    resultados = []
    inicio = time.time()
    for t in escolhidas:
        try:
            s = fazer(t, modelo)
        except Exception as exc:  # noqa: BLE001 - uma tarefa que quebra não para o banco
            s = bancada.Saida(erro=f"{type(exc).__name__}: {exc}"[:300])
        r = bancada.avaliar(t, s)
        resultados.append(r)
        marca = "ok " if r["acerto"] else "-- "
        extra = "" if r["acerto"] else "  " + json.dumps(r.get("por_que") or {}, ensure_ascii=False)[:160]
        print(f"{marca}{t.id:7} {t.categoria:18} {r['segundos']:6.1f}s{('  ERRO ' + r['erro'][:80]) if r['erro'] else ''}{extra}")
    res = bancada.resumo(resultados)
    nome_modelo = (getattr(modelo, "modelo_real", "") or getattr(modelo, "nome", "")) if modelo else "sem-modelo"
    print()
    print(f"{a.adaptador} · {nome_modelo} · {len(escolhidas)} tarefas · {time.time() - inicio:.0f} s")
    for chave in ("acerto", "acerto_edicao", "lugar_unico", "varios", "sem_dano", "marcado", "honesto", "numeracao",
                  "erros", "segundos_medio", "tokens"):
        print(f"  {chave:15} {res[chave]}")
    for cat, v in res["por_categoria"].items():
        print(f"    {cat:18} {v['acerto']}% de {v['n']}")
    pasta = LEGAL / "tools" / "bancada_editor" / "resultados"
    pasta.mkdir(parents=True, exist_ok=True)
    rotulo = nome_modelo.split("/")[-1].replace(":", "-")
    destino = Path(a.saida) if a.saida else pasta / f"{datetime.now():%Y-%m-%d-%H%M}-{a.adaptador}-{rotulo}-{a.nivel}.json"
    destino.write_text(json.dumps({"adaptador": a.adaptador, "modelo": nome_modelo, "nivel": a.nivel,
                                   "quando": datetime.now().isoformat(timespec="seconds"), "resumo": res,
                                   "tarefas": resultados}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nresultado em {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
