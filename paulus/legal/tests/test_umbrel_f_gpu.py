"""
Ideia F do umbrelOS (docs/DECISAO-UMBREL.md): placas de vídeo de qualquer
fabricante, e a medida decidindo se o Ollama usa a placa.

  - a leitura do Win32_VideoController: Intel, AMD e NVIDIA, integrada ou
    não; o adaptador que não é placa (área de trabalho remota, driver básico)
    fica de fora; a saída vazia ou quebrada não derruba nada;
  - `na_placa`: a fração do modelo que o Ollama pôs na memória da placa
    (/api/ps), e None quando não dá para saber;
  - a amostra de calibração só conta a placa quando a medida confirma;
  - nesta máquina, o teste real diz o que há (pula fora do Windows).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_umbrel_f_gpu.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import maquina  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def test_leitura() -> None:
    print("\nas placas do Windows")
    bruto = json.dumps([
        {"Name": "Intel(R) Iris(R) Xe Graphics", "AdapterCompatibility": "Intel Corporation", "AdapterRAM": 1073741824},
        {"Name": "AMD Radeon(TM) Graphics", "AdapterCompatibility": "Advanced Micro Devices, Inc.", "AdapterRAM": 536870912},
        {"Name": "AMD Radeon RX 7600", "AdapterCompatibility": "Advanced Micro Devices, Inc.", "AdapterRAM": 4293918720},
        {"Name": "NVIDIA GeForce RTX 3060", "AdapterCompatibility": "NVIDIA", "AdapterRAM": 4293918720},
        {"Name": "Intel(R) Arc(TM) A770 Graphics", "AdapterCompatibility": "Intel Corporation", "AdapterRAM": None},
        {"Name": "Microsoft Basic Display Adapter", "AdapterCompatibility": "(Standard display types)"},
        {"Name": "Microsoft Remote Display Adapter", "AdapterCompatibility": "Microsoft"},
    ])
    placas = maquina.ler_placas_do_windows(bruto)
    por_nome = {p["nome"]: p for p in placas}
    checar(len(placas) == 5, "cinco placas; o driver básico e a área remota ficam de fora", list(por_nome))
    checar(por_nome["Intel(R) Iris(R) Xe Graphics"]["fabricante"] == "Intel"
           and por_nome["Intel(R) Iris(R) Xe Graphics"]["integrada"], "Intel Iris Xe: Intel, integrada")
    checar(por_nome["AMD Radeon(TM) Graphics"]["integrada"] and not por_nome["AMD Radeon RX 7600"]["integrada"],
           "AMD Radeon Graphics é integrada; a RX 7600, não")
    checar(not por_nome["Intel(R) Arc(TM) A770 Graphics"]["integrada"], "Intel Arc A770 é placa própria")
    checar(por_nome["NVIDIA GeForce RTX 3060"]["fabricante"] == "NVIDIA", "NVIDIA reconhecida pelo Windows também")
    checar(por_nome["Intel(R) Arc(TM) A770 Graphics"]["memoria_gb"] is None, "sem AdapterRAM, sem número inventado")
    uma = maquina.ler_placas_do_windows(json.dumps({"Name": "Intel(R) UHD Graphics 620", "AdapterCompatibility": "Intel"}))
    checar(len(uma) == 1, "uma placa só (o PowerShell devolve objeto, não lista)")
    checar(maquina.ler_placas_do_windows("") == [] and maquina.ler_placas_do_windows("{quebrado") == [],
           "saída vazia ou quebrada: lista vazia, sem erro")


def test_na_placa() -> None:
    print("\nonde o Ollama pôs o modelo")

    class Resp:
        def __init__(self, dados):
            self.dados = dados

        def raise_for_status(self):
            pass

        def json(self):
            return self.dados

    ps = {"models": [{"name": "llama3.2:3b", "size": 4000, "size_vram": 4000},
                     {"name": "bge-m3:latest", "size": 1200, "size_vram": 0}]}
    checar(maquina.na_placa("h", "llama3.2:3b", pegar=lambda *a, **k: Resp(ps)) == 1.0, "inteiro na placa: 1,0")
    checar(maquina.na_placa("h", "bge-m3", pegar=lambda *a, **k: Resp(ps)) == 0.0, "no processador: 0,0")
    checar(maquina.na_placa("h", "outro:1b", pegar=lambda *a, **k: Resp(ps)) is None, "modelo não carregado: não sei")

    def cai(*a, **k):
        raise ConnectionError("Ollama fora")

    checar(maquina.na_placa("h", "llama3.2:3b", pegar=cai) is None, "Ollama fora do ar: não sei, sem erro")


def test_amostra() -> None:
    print("\na calibração só conta a placa medida")
    maq = {"id": "x", "placas_nvidia": [], "placas": [{"nome": "Intel Iris Xe", "fabricante": "Intel", "integrada": True}]}
    modelo = {"nome": "llama3.2:3b", "gb": 2.0}
    checar(maquina.amostra(maq, modelo, {"na_placa": 0.0})["gpu"] is False, "Intel integrada que o Ollama não usa: processador")
    checar(maquina.amostra(maq, modelo, {"na_placa": 1.0})["gpu"] is True, "a mesma placa, usada pelo Ollama: placa")
    checar(maquina.amostra({"placas_nvidia": [{"nome": "RTX"}]}, modelo, {})["gpu"] is True,
           "medida antiga, sem na_placa: vale a NVIDIA de antes")


def test_real() -> None:
    print("\nnesta máquina")
    if os.name != "nt":
        print("  pulado: fora do Windows")
        return
    placas = maquina._placas_windows()
    print("       placas: " + (", ".join(p["nome"] + (" (integrada)" if p["integrada"] else "") for p in placas) or "nenhuma"))
    checar(isinstance(placas, list), "o teste da máquina lê as placas pelo Windows sem erro")


def main() -> int:
    print("=" * 55)
    print("  Umbrel F — placas de vídeo de qualquer fabricante")
    print("=" * 55)
    test_leitura()
    test_na_placa()
    test_amostra()
    test_real()
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
