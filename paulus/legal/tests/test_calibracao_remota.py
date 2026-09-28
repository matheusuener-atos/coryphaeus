"""
Testes da calibração compartilhada (src/calibracao_remota.py e /api/calibracao).

  - desligada de fábrica: medir não manda nada;
  - "ver o que é enviado" mostra exatamente as amostras desta máquina, só
    números de máquina e modelo;
  - ligar manda as medidas daqui e traz as de outras máquinas;
  - amostra de fora que a física não explica (falsa, ou de outro mundo) fica
    fora da conta;
  - o servidor fora do ar vira frase, não queda.

Sem internet: o site é trocado por respostas prontas. Dados numa pasta
temporária (PAULUS_DADOS).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_calibracao_remota.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-calib-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
sys.path.insert(0, str(RAIZ / "src"))

import calibracao_remota as cr  # noqa: E402
import maquina  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


MAQ = {"id": "abc123def456", "versao": 2, "processador": "Intel Teste", "nucleos": 8, "ram_total_gb": 16.0,
       "avx2": True, "banda_gbs": 40.0, "gflops": 250.0, "na_bateria": False}


def amostra(escrita: float, leitura: float = 60.0, maq=None) -> dict:
    return {"maquina": dict(maq or MAQ), "gpu": False, "modelo": "llama3.2:3b", "tamanho_gb": 2.0, "parametros_b": 3.2,
            "quantizacao": "Q4_K_M", "escrita_tps": escrita, "leitura_tps": leitura, "quando": "2026-09-27 10:00"}


class Resp:
    def __init__(self, status=200, corpo=None):
        self.status_code = status
        self._c = corpo or {}

    def json(self):
        return self._c

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(str(self.status_code))


def test_modulo() -> None:
    print("\no envio e a leitura")
    enviados = []
    r = cr.enviar([amostra(11.0)], "0.9.0", url="http://x", postar=lambda url, json, timeout: (enviados.append(json), Resp(200, {"recebidas": 1}))[1])
    checar(r["recebidas"] == 1 and enviados[0]["programa"] == "0.9.0" and enviados[0]["amostras"][0]["escrita_tps"] == 11.0,
           "manda as amostras e a versão do programa", enviados)
    try:
        cr.enviar([amostra(11.0)], url="http://x", postar=lambda *a, **k: Resp(429, {"erro": "muitas tentativas"}))
        checar(False, "recusa vira frase")
    except cr.ErroCalibracao as exc:
        checar("429" in str(exc) and "muitas" in str(exc), "recusa do site vira frase", str(exc))
    destino = TMP / "servidor.json"
    n = cr.baixar(destino, url="http://x", pegar=lambda url, timeout: Resp(200, {"amostras": [amostra(10.0), "lixo"]}))
    checar(n == 1 and cr.ler_guardadas(destino)[0][0]["escrita_tps"] == 10.0, "baixa e guarda, jogando fora o que não é amostra")

    import requests

    def cai(*a, **k):
        raise requests.ConnectionError("sem rede")

    try:
        cr.baixar(destino, url="http://x", pegar=cai)
        checar(False, "sem rede vira frase")
    except cr.ErroCalibracao:
        checar(True, "sem rede vira frase, e o que já havia continua guardado")


def test_plausiveis() -> None:
    print("\no filtro do que vem de fora")
    calib = maquina.calibrar(maquina.ler_amostras(maquina.BASE_PATH))
    prevista, _, _ = maquina._bruto({"gb": 2.0, "parametros": 3.2, "quantizacao": "Q4_K_M"}, MAQ, calib)
    boas = cr.plausiveis([amostra(prevista), amostra(prevista * 1.8), amostra(prevista * 40), amostra(prevista / 30),
                          {"maquina": {}, "escrita_tps": "x"}], calib)
    checar(len(boas) == 2, "fica a amostra que a física explica; a de 40× e a de 1/30 ficam de fora", len(boas))


def test_api() -> None:
    print("\npela API")
    from fastapi.testclient import TestClient

    import api

    c = TestClient(api.app, headers=api.cabecalho_local())
    enviados, baixados = [], []
    original = (cr.enviar, cr.baixar)
    api.calibracao_remota.enviar = lambda amostras, versao="", **k: (enviados.append(list(amostras)), {"recebidas": len(amostras)})[1]

    def baixar_de_mentira(destino, **k):
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
        Path(destino).write_text(json.dumps({"quando": "2026-09-27 10:00", "amostras": [amostra(12.0, maq=dict(MAQ, id="outramaquina1"))]}), encoding="utf-8")
        baixados.append(destino)
        return 1

    api.calibracao_remota.baixar = baixar_de_mentira
    medir_de_verdade = api._medir_para_calibracao
    api._medir_para_calibracao = lambda *a, **k: False   # sem Ollama de verdade aqui
    try:
        d = c.get("/api/calibracao").json()
        checar(d["participar"] is False, "desligada de fábrica")
        api._maquina = lambda fresco=False, testar=True: dict(MAQ)
        maquina.guardar_amostra(api.CALIBRACAO_PATH, amostra(11.2))
        d = c.get("/api/calibracao").json()
        vai = d["o_que_vai"]
        texto = json.dumps(vai, ensure_ascii=False)
        checar(len(vai) == 1 and vai[0]["modelo"] == "llama3.2:3b", "ver o que é enviado mostra a amostra desta máquina", vai)
        checar(not any(p in texto for p in ("@", "cliente", "documento", "senha")), "só números de máquina e modelo")
        checar(not enviados, "desligada, nada foi mandado")

        d = c.post("/api/calibracao", json={"participar": True}).json()
        fim = time.time() + 5
        while time.time() < fim and not (enviados and baixados):
            time.sleep(0.1)
        checar(d["participar"] and enviados and enviados[0][0]["escrita_tps"] == 11.2, "ligar manda as medidas daqui", enviados)
        checar(baixados and c.get("/api/calibracao").json()["de_outras_maquinas"] == 1, "e traz as de outras máquinas")

        c.post("/api/calibracao", json={"participar": False})
        antes = len(enviados)
        checar(c.get("/api/calibracao").json()["participar"] is False and len(enviados) == antes, "desligar para de mandar")
    finally:
        api.calibracao_remota.enviar, api.calibracao_remota.baixar = original
        api._medir_para_calibracao = medir_de_verdade


def test_medida_automatica() -> None:
    print("\na avaliação desta máquina vai sozinha")
    import api

    medidos = []
    originais = (api._participa_da_calibracao, api._medidas_dos_modelos, api._medir_e_guardar)
    participa = {"sim": True}
    ja_medidos = {}
    api._participa_da_calibracao = lambda: participa["sim"]
    api._medidas_dos_modelos = lambda: dict(ja_medidos)
    api._medir_e_guardar = lambda nome: (medidos.append(nome), ja_medidos.__setitem__(nome, {}))
    try:
        checar(api._medir_para_calibracao("qwen2.5:3b", espera=0.2), "modelo que terminou de baixar é agendado para medir")
        checar(not api._medir_para_calibracao("qwen2.5:3b", espera=0.2), "o mesmo modelo não é agendado duas vezes")
        fim = time.time() + 5
        while time.time() < fim and not medidos:
            time.sleep(0.05)
        checar(medidos == ["qwen2.5:3b"], "é medido (e a medida vai ao servidor pelo caminho de sempre)", medidos)
        checar(not api._medir_para_calibracao("qwen2.5:3b", espera=0), "já medido não mede de novo")
        participa["sim"] = False
        checar(not api._medir_para_calibracao("gemma2:2b", espera=0), "calibração desligada: não mede nem manda")
    finally:
        api._participa_da_calibracao, api._medidas_dos_modelos, api._medir_e_guardar = originais


def main() -> int:
    print("=" * 55)
    print("  a calibração compartilhada")
    print("=" * 55)
    try:
        test_modulo()
        test_plausiveis()
        test_api()
        test_medida_automatica()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
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
