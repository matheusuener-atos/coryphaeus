"""
Testes do teste da máquina e da recomendação de modelo (src/maquina.py).

  - a leitura da etiqueta do modelo: parâmetros ("3.2B", "494M") e a família
    da quantização;
  - a calibração acha de volta as constantes de amostras feitas com
    constantes conhecidas, em máquinas diferentes;
  - a estimativa: memória que não cabe, medida real valendo no lugar da
    estimativa, a correção pelo que foi medido nesta máquina;
  - a recomendação: melhor nota dentro do limite, empate vai ao mais rápido,
    nenhum dentro do limite vai ao mais rápido avisando, modelo sem nota
    nunca é recomendado, nada cabendo diz por quê;
  - o teste de verdade roda sem IA e em poucos segundos;
  - pela API, com a máquina e o Ollama trocados por dados prontos.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_maquina.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import maquina  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def perto(a, b, tolerancia=0.03) -> bool:
    return abs(a - b) <= tolerancia * abs(b)


MAQ_A = {"id": "a", "banda_gbs": 50.0, "gflops": 280.0, "ram_total_gb": 16.0, "ram_livre_gb": 8.0}
MAQ_B = {"id": "b", "banda_gbs": 20.0, "gflops": 90.0, "ram_total_gb": 8.0, "ram_livre_gb": 3.0}
A, B, K4, K8 = 0.6, 2.6, 0.68, 0.39


def sintetica(maq, nome, gb, params, quant) -> dict:
    """Uma amostra feita com as constantes conhecidas: a calibração tem de achá-las de volta."""
    t = A * gb / maq["banda_gbs"] + B * 2 * params / maq["gflops"]
    k = K4 if maquina.familia(quant) == "q4" else K8
    return {"maquina": maq, "gpu": False, "modelo": nome, "tamanho_gb": gb, "parametros_b": params,
            "quantizacao": quant, "escrita_tps": 1 / t, "leitura_tps": k * maq["gflops"] / params}


AMOSTRAS = [
    sintetica(MAQ_A, "m3", 2.0, 3.2, "Q4_K_M"), sintetica(MAQ_A, "m3q8", 3.4, 3.2, "Q8_0"),
    sintetica(MAQ_A, "m1", 1.3, 1.2, "Q8_0"), sintetica(MAQ_B, "m3", 2.0, 3.2, "Q4_K_M"),
    sintetica(MAQ_B, "m7", 4.7, 7.6, "Q4_K_M"),
]


def test_etiquetas() -> None:
    print("\na etiqueta do modelo")
    checar(maquina.parametros_b("3.2B") == 3.2 and maquina.parametros_b("494M") == 0.494
           and maquina.parametros_b(7) == 7.0 and maquina.parametros_b("") == 0.0, "parâmetros: 3.2B, 494M, número, vazio")
    checar([maquina.familia(q) for q in ("Q4_K_M", "Q4_0", "Q5_K_S", "IQ3_M", "Q8_0", "Q6_K", "F16", "")] ==
           ["q4", "q4", "q4", "q4", "q8", "q8", "f16", "q4"], "famílias de quantização")


def test_calibrar() -> None:
    print("\na calibração")
    c = maquina.calibrar(AMOSTRAS)
    checar(perto(c["escrita"]["a"], A) and perto(c["escrita"]["b"], B), "acha de volta a memória e a conta da escrita", c["escrita"])
    checar(perto(c["leitura"]["q4"], K4) and perto(c["leitura"]["q8"], K8) and "f16" not in c["leitura"],
           "acha o fator de leitura de cada família, e não inventa o que não tem amostra", c["leitura"])
    checar(c["amostras"] == 5 and c["maquinas"] == 2, "conta amostras e máquinas", c)
    com_gpu = AMOSTRAS + [{**AMOSTRAS[0], "gpu": True, "escrita_tps": 900.0}]
    checar(maquina.calibrar(com_gpu)["escrita"] == c["escrita"], "amostra com placa de vídeo não entra")
    checar(maquina.calibrar([])["escrita"]["a"] > 0, "sem amostra nenhuma, ainda estima")


def test_estimar() -> None:
    print("\na estimativa")
    c = maquina.calibrar(AMOSTRAS)
    sem = {"escrita": 1.0, "leitura": 1.0}
    m3 = {"nome": "m3", "gb": 2.0, "parametros": "3.2B", "quantizacao": "Q4_K_M"}
    e = maquina.estimar(m3, MAQ_B, c, sem)
    esperado = 1 / (A * 2.0 / 20 + B * 6.4 / 90)
    checar(perto(e["escrita_tps"], esperado) and e["fonte"] == "estimado", "escrita pela física calibrada", e)
    primeira = maquina.LER_PRIMEIRA / e["leitura_tps"] + maquina.ESCREVER / e["escrita_tps"]
    checar(abs(e["primeira_s"] - primeira) <= 1 and e["seguinte_s"] < e["primeira_s"],
           "primeira pergunta lê o documento; as seguintes, só a pergunta", e)
    grande = {"nome": "g", "gb": 4.9, "parametros": "8.0B", "quantizacao": "Q4_K_M"}
    checar(not maquina.estimar(grande, MAQ_B, c, sem)["cabe"] and maquina.estimar(grande, MAQ_A, c, sem)["cabe"],
           "8B não cabe em 8 GB e cabe em 16 GB")
    checar(maquina.estimar(m3, MAQ_A, c, sem)["apertado"] is False and maquina.estimar(m3, MAQ_B, c, sem)["apertado"] and maquina.estimar(grande, {**MAQ_A, "ram_livre_gb": 2.0}, c, sem)["apertado"],
           "apertado: cabe no total, mas não no que está livre agora")
    medida = {"tokens_por_segundo": 7.0, "leitura_tokens_por_segundo": 30.0}
    e = maquina.estimar(m3, MAQ_B, c, sem, medida)
    checar(e["fonte"] == "medido" and e["escrita_tps"] == 7.0, "medida real vale no lugar da estimativa", e)
    antiga = {"tokens_por_segundo": 7.0}  # de antes de medir a leitura
    checar(maquina.estimar(m3, MAQ_B, c, sem, antiga)["fonte"] == "estimado", "medida sem leitura não substitui a estimativa")
    f16 = {"nome": "f", "gb": 6.0, "parametros": "3.2B", "quantizacao": "F16"}
    checar(maquina.estimar(f16, MAQ_A, c, sem)["fonte"] == "aproximado", "família sem amostra fica aproximada")
    # Esta máquina é 20% mais lenta que a calibração diz, medido em um modelo:
    # a estimativa dos outros se corrige.
    lenta = {**MAQ_B, "id": "lenta"}
    daqui = [{**AMOSTRAS[3], "maquina": lenta, "escrita_tps": AMOSTRAS[3]["escrita_tps"] * 0.8,
              "leitura_tps": AMOSTRAS[3]["leitura_tps"] * 0.8}]
    corr = maquina.correcao_local(lenta, c, daqui)
    m7 = {"nome": "m7", "gb": 4.7, "parametros": "7.6B", "quantizacao": "Q4_K_M"}
    checar(perto(corr["escrita"], 0.8) and corr["medidos"] == 1, "a correção sai do que foi medido aqui", corr)
    checar(perto(maquina.estimar(m7, lenta, c, corr)["escrita_tps"], maquina.estimar(m7, lenta, c, sem)["escrita_tps"] * 0.8, 0.06),
           "e vale para os modelos que não foram medidos")


def test_recomendar() -> None:
    print("\na recomendação")
    c = maquina.calibrar(AMOSTRAS)
    sem = {"escrita": 1.0, "leitura": 1.0}
    modelos = [
        {"nome": "bom", "gb": 2.0, "parametros": "3.2B", "quantizacao": "Q4_K_M"},
        {"nome": "igual-lento", "gb": 3.4, "parametros": "3.2B", "quantizacao": "Q8_0"},
        {"nome": "rapido-sem-nota", "gb": 1.3, "parametros": "1.2B", "quantizacao": "Q8_0"},
        {"nome": "enorme", "gb": 18.0, "parametros": "9.2B", "quantizacao": "F16"},
    ]
    q = {"bom": {"certas": 41, "total": 41}, "igual-lento": {"certas": 36, "total": 36}, "enorme": {"certas": 41, "total": 41}}
    r = maquina.recomendar(modelos, MAQ_A, c, sem, q, {})
    checar(r["recomendado"] == "bom" and not r["lento"], "empate na nota: o mais rápido", r["recomendado"])
    checar("41 de 41" in r["porque"] and "~" in r["porque"], "o porquê diz a nota e o tempo", r["porque"])
    checar(not any(x["recomendado"] for x in r["modelos"] if x["nome"] == "rapido-sem-nota"), "sem nota, nunca recomendado")
    q2 = {**q, "igual-lento": {"certas": 36, "total": 36}, "bom": {"certas": 30, "total": 41}}
    checar(maquina.recomendar(modelos, MAQ_A, c, sem, q2, {})["recomendado"] == "igual-lento", "nota melhor ganha dentro do limite")
    fraca = {"id": "x", "banda_gbs": 4.0, "gflops": 10.0, "ram_total_gb": 16.0, "ram_livre_gb": 8.0}
    r = maquina.recomendar(modelos, fraca, c, sem, q, {})
    checar(r["recomendado"] == "bom" and r["lento"] and "lento" in r["porque"], "nenhum no limite: o mais rápido, avisando", r)
    q3 = {**q, "rapido-sem-nota": {"certas": 22, "total": 41}}
    r = maquina.recomendar(modelos, fraca, c, sem, q3, {})
    checar(r["recomendado"] == "bom" and r["lento"], "rápido com nota baixa (22 de 41) não passa na frente do lento que acerta", r["recomendado"])
    minuscula = {"id": "y", "banda_gbs": 40.0, "gflops": 200.0, "ram_total_gb": 4.0, "ram_livre_gb": 1.0}
    r = maquina.recomendar(modelos, minuscula, c, sem, q, {})
    checar(r["recomendado"] == "" and "cabe na memória" in r["porque"] and "4,0 GB" in r["porque"], "nada cabe: diz por quê", r["porque"])


def test_de_verdade() -> None:
    print("\no teste de verdade, sem IA")
    comeco = time.time()
    t = maquina.testar()
    segundos = time.time() - comeco
    checar(segundos < 20, f"roda em poucos segundos ({segundos:.1f} s)")
    checar(t["banda_gbs"] > 0 and t["gflops"] > 0 and t["ram_total_gb"] > 0 and t["id"], "mede memória, contas e o total", t)
    checar(t["versao"] == maquina.VERSAO_DO_TESTE and "na_bateria" in t, "guarda a versão do teste e a energia")
    base = maquina.ler_amostras(maquina.BASE_PATH)
    checar(len(base) >= 2 and all(a["maquina"].get("versao") == maquina.VERSAO_DO_TESTE for a in base),
           "a base que vai com o programa foi medida com esta versão do teste", len(base))


def test_api() -> None:
    print("\npela API")
    from fastapi.testclient import TestClient

    import api

    originais = (api._maquina, api.modelos_mod.instalados, api.modelos_mod.tamanhos_do_catalogo)
    api._maquina = lambda fresco=False, testar=True: {**MAQ_A, "processador": "teste", "placas_nvidia": [], "na_bateria": False}
    api.modelos_mod.instalados = lambda host: [{"nome": "llama3.2:3b", "gb": 2.02, "parametros": "3.2B", "quantizacao": "Q4_K_M"}]
    api.modelos_mod.tamanhos_do_catalogo = lambda: {}
    try:
        c = TestClient(api.app)
        d = c.get("/api/maquina").json()
        checar(d["recomendado"] == "llama3.2:3b" and d["maquina"]["processador"] == "teste", "recomenda pela máquina", d.get("recomendado"))
        nomes = [x["nome"] for x in d["modelos"]]
        checar(nomes.count("llama3.2:3b") == 1 and "llama3.1:8b" in nomes, "instalados e catálogo, sem repetir", nomes)
        checar(next(x for x in d["modelos"] if x["nome"] == "llama3.2:3b")["instalado"], "o instalado vale no lugar do catálogo")
        m = c.get("/api/modelos").json()
        checar(m["recomendado"] == "llama3.2:3b" and m["instalados"][0].get("estimativa"),
               "a tela de modelos traz a estimativa de cada um", m.get("recomendado"))
    finally:
        api._maquina, api.modelos_mod.instalados, api.modelos_mod.tamanhos_do_catalogo = originais


def main() -> int:
    print("=" * 55)
    print("  esta máquina e o modelo recomendado")
    print("=" * 55)
    test_etiquetas()
    test_calibrar()
    test_estimar()
    test_recomendar()
    test_de_verdade()
    test_api()
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
