"""
A lista de modelos para a tela "Modelo de IA" do instalador.

O instalador (tools/instalador/paulus.iss.modelo) roda isto com o Python que
acabou de instalar, antes de o PAULUS abrir pela primeira vez:

    python\\python.exe app\\src\\recomendar_modelo.py <arquivo de saida>

Faz o teste da máquina (sem IA, uns cinco segundos, src/maquina.py) e escreve,
em texto simples - o instalador não lê JSON -, uma linha por modelo do
catálogo com o tamanho, a nota no nosso banco de provas e o tempo estimado
aqui, marcando o recomendado:

    MAQUINA|<resumo da máquina>
    MODELO|<nome>|<texto para a tela>|<1 se recomendado>
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import maquina  # noqa: E402
import modelos  # noqa: E402


def _br(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def linhas() -> list[str]:
    maq = maquina.testar()
    calib = maquina.calibrar(maquina.ler_amostras(maquina.BASE_PATH))
    sem_correcao = {"escrita": 1.0, "leitura": 1.0}
    catalogo = [{"nome": c["nome"], "gb": c["gb_aprox"], "parametros": c["parametros"], "quantizacao": c["quantizacao"]}
                for c in modelos.CATALOGO]
    r = maquina.recomendar(catalogo, maq, calib, sem_correcao, modelos.QUALIDADE, {})
    placa = ", ".join(p["nome"] for p in maq.get("placas_nvidia") or []) or "sem placa NVIDIA"
    saida = [f"MAQUINA|{maq['processador']} · {_br(maq['ram_total_gb'])} GB de memória · {placa}"]
    for m in r["modelos"]:
        e, q = m["estimativa"], m["qualidade"]
        partes = [f"{_br(m['gb'])} GB"]
        if q:
            partes.append(f"acertou {q['certas']} de {q['total']} no nosso teste")
        else:
            partes.append("ainda sem nota no nosso teste")
        if not e["cabe"]:
            partes.append("não cabe na memória desta máquina")
        elif e["primeira_s"]:
            partes.append(f"1ª pergunta ~{e['primeira_s']} s")
        texto = f"{m['nome']} — " + " · ".join(partes) + (" (recomendado)" if m["recomendado"] else "")
        saida.append(f"MODELO|{m['nome']}|{texto}|{1 if m['recomendado'] else 0}")
    return saida


def main() -> int:
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    try:
        texto = "\n".join(linhas()) + "\n"
    except Exception as exc:  # noqa: BLE001 - o instalador mostra a lista sem recomendação
        texto = f"MAQUINA|não consegui conferir esta máquina ({exc})\n" + "\n".join(
            f"MODELO|{c['nome']}|{c['nome']} — {_br(c['gb_aprox'])} GB|{1 if c['nome'] == 'llama3.2:3b' else 0}"
            for c in modelos.CATALOGO) + "\n"
    if destino:
        # Com BOM: o instalador lê o arquivo como UTF-8 por ele.
        destino.write_text(texto, encoding="utf-8-sig")
    else:
        print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
