"""
L6 - modelo por máquina (src/perfis.py, js/68-perfis.js).

Com máquinas de mentira, uma por faixa:

  - NVIDIA de 12, 8 e 4 GB: CUDA; o 7-8B só como "meça antes", o 3B em 8
    bits de 6 GB para cima, o 3B de fábrica abaixo;
  - AMD RX 7800 XT: ROCm (a lista do Ollama no Windows); RX 6600: Vulkan,
    com a variável; a memória do Windows avisada como ordem de grandeza;
  - Intel Arc A770: Vulkan; Intel UHD integrada: o processador;
  - só processador com 6 GB: o 1B, com a nota dita; com 16 GB: o 3B;
  - a placa NVIDIA que aparece pelo nvidia-smi e pelo Windows conta uma vez;
  - a rota: o perfil e ligar/desligar o Vulkan (escritor de mentira);
  - no Edge: o cartão em Configurações › Modelos.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_l6_perfis.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-l6-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def maquina(ram=16.0, nvidia=None, placas=None):
    # Os campos que a tela Modelos usa para estimar (src/maquina.py), com números de uma máquina comum.
    return {"ram_total_gb": ram, "ram_livre_gb": ram / 2, "placas_nvidia": nvidia or [], "placas": placas or [],
            "processador": "Processador de teste", "nucleos": 8, "linhas": 16, "banda_gbs": 20.0, "gflops": 120.0,
            "avx2": True, "avx512": False, "na_bateria": False, "id": "teste"}


def main() -> int:
    print("=" * 55)
    print("  L6 — modelo por máquina")
    print("=" * 55)
    import perfis

    print("\nNVIDIA")
    p = perfis.perfil(maquina(nvidia=[{"nome": "NVIDIA GeForce RTX 4070", "memoria_gb": 12.0}],
                              placas=[{"nome": "NVIDIA GeForce RTX 4070", "fabricante": "NVIDIA", "integrada": False, "memoria_gb": 4.0}]))
    checar(p["faixa"] == "gpu-grande" and p["ollama"]["motor"] == "CUDA" and p["modelo"] == perfis.OITO_BITS
           and p["alternativa"] == perfis.GRANDE and any("Meça em Modelos antes" in x for x in p["explica"]),
           "12 GB: o 3B em 8 bits, e o 7-8B só como “meça antes”", p)
    checar(p["placa"]["memoria_gb"] == 12.0 and p["placa"]["exata"], "a placa pelo nvidia-smi (exata), contada uma vez")
    p = perfis.perfil(maquina(nvidia=[{"nome": "RTX 3060 Ti", "memoria_gb": 8.0}]))
    checar(p["faixa"] == "gpu-media" and p["modelo"] == perfis.OITO_BITS, "8 GB: o 3B em 8 bits inteiro na placa", p["faixa"])
    p = perfis.perfil(maquina(nvidia=[{"nome": "GTX 1650", "memoria_gb": 4.0}]))
    checar(p["faixa"] == "gpu-pequena" and p["modelo"] == perfis.PADRAO, "4 GB: o 3B de fábrica", p["faixa"])
    p = perfis.perfil(maquina(nvidia=[{"nome": "MX150", "memoria_gb": 2.0}]))
    checar(p["faixa"] == "cpu" and "divide com o processador" in p["explica"][0], "2 GB: não cabe, divide com o processador")

    print("\nAMD e Intel")
    p = perfis.perfil(maquina(placas=[{"nome": "AMD Radeon RX 7800 XT", "fabricante": "AMD", "integrada": False, "memoria_gb": 4.0}]))
    checar(p["faixa"] == "gpu-amd" and p["ollama"]["motor"] == "ROCm" and not p["ollama"]["variavel"]
           and any("ordem de grandeza" in a for a in p["avisos"]), "RX 7800 XT: ROCm, e a memória do Windows avisada", p["ollama"])
    p = perfis.perfil(maquina(placas=[{"nome": "AMD Radeon RX 6600", "fabricante": "AMD", "integrada": False, "memoria_gb": 4.0}]))
    checar(p["ollama"]["motor"] == "Vulkan" and p["ollama"]["variavel"] == "OLLAMA_VULKAN", "RX 6600: fora do ROCm, pelo Vulkan", p["ollama"])
    p = perfis.perfil(maquina(placas=[{"nome": "Intel(R) Arc(TM) A770 Graphics", "fabricante": "Intel", "integrada": False, "memoria_gb": 4.0}]))
    checar(p["faixa"] == "gpu-intel" and p["ollama"]["motor"] == "Vulkan", "Intel Arc A770: Vulkan", p["faixa"])
    p = perfis.perfil(maquina(ram=16, placas=[{"nome": "Intel(R) UHD Graphics 620", "fabricante": "Intel", "integrada": True, "memoria_gb": 1.0}]))
    checar(p["faixa"] == "cpu" and any("integrada" in x for x in p["explica"]), "Intel UHD integrada: o processador, e dito", p["explica"])

    print("\nsó o processador")
    p = perfis.perfil(maquina(ram=6.0))
    checar(p["faixa"] == "cpu-leve" and p["modelo"] == perfis.LEVE and "22 de 41" in p["explica"][0] and "6 GB" in p["explica"][0],
           "6 GB: o 1B, com a nota dita", p["explica"])
    p = perfis.perfil(maquina(ram=16.9))
    checar(p["faixa"] == "cpu" and p["modelo"] == perfis.PADRAO and "16,9 GB" in p["explica"][0], "16,9 GB: o 3B de fábrica, em número brasileiro")
    checar(perfis.perfil(None)["faixa"] == "sem-teste", "sem o teste: diz para testar")

    print("\na rota")
    import api
    from fastapi.testclient import TestClient

    guardado = {"v": False}
    perfis._ESCRITOR["ligar"] = lambda ligar: guardado.update(v=ligar)
    perfis._ESCRITOR["ler"] = lambda: guardado["v"]
    api._maquina = lambda fresco=False, testar=True: maquina(placas=[{"nome": "AMD Radeon RX 6600", "fabricante": "AMD", "integrada": False, "memoria_gb": 4.0}])
    local = TestClient(api.app, headers=api.cabecalho_local())
    d = local.get("/api/maquina/perfil").json()
    checar(d["ollama"]["motor"] == "Vulkan" and d["vulkan_ligado"] is False, "o perfil pela rota", d.get("faixa"))
    r = local.post("/api/maquina/perfil/vulkan", json={"ligar": True}).json()
    checar(r["vulkan_ligado"] and guardado["v"] and "reabra" in r["proximo"].lower() or "abra o ollama" in r["proximo"].lower(),
           "ligar o Vulkan grava e diz para reabrir o Ollama", r)
    local.post("/api/maquina/perfil/vulkan", json={"ligar": False})
    checar(not guardado["v"], "e desligar tira")

    print("\nno Edge")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None
        print("  pulado: playwright não instalado")
    if sync_playwright is not None:
        from test_gravacoes import _porta_livre, _subir_servidor

        porta = _porta_livre()
        _subir_servidor(porta)
        with sync_playwright() as pw:
            try:
                nav = pw.chromium.launch(channel="msedge")
            except Exception as exc:  # noqa: BLE001
                nav = None
                print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            if nav is not None:
                pag = nav.new_context(viewport={"width": 1280, "height": 900}).new_page()
                erros = []
                pag.on("pageerror", lambda e: erros.append(str(e)))
                pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
                pag.goto(f"http://127.0.0.1:{porta}/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
                pag.wait_for_function("() => typeof mostrarConfig === 'function' && typeof cartaoPerfilDaMaquina === 'function'")
                pag.wait_for_timeout(800)
                pag.evaluate("() => mostrarConfig('modelos')")
                pag.wait_for_selector("[data-perfil-vulkan]", timeout=20000)
                texto = pag.inner_text("#cfg-tela")
                checar("Perfil desta máquina" in texto and "Vulkan" in texto and "RX 6600" in texto, "o cartão em Configurações › Modelos")
                pag.click("[data-perfil-vulkan]")
                pag.wait_for_function("() => document.querySelector('[data-perfil-vulkan]').classList.contains('on')", timeout=10000)
                checar(guardado["v"], "ligar pela tela")
                pag.locator("[data-perfil-vulkan]").scroll_into_view_if_needed()
                pag.screenshot(path=str(TMP / "l6-perfil.png"))
                checar(not erros, "nenhum erro de JavaScript", erros[:3])
                print(f"  (foto em {TMP})")
                nav.close()

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for x in _falhas:
            print(f"    - {x}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
