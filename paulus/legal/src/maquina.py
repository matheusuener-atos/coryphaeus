"""
Esta máquina, e qual modelo roda bem nela - sem rodar modelo nenhum.

Na instalação, baixar um modelo de 4,7 GB que escreve duas palavras por
segundo é o pior começo possível: a pessoa acha que o PAULUS é lento. Este
módulo estima, antes de baixar, quanto cada modelo vai demorar AQUI.

Como, sem IA:

- **O teste da máquina** (uns 5 s): memória total e livre, núcleos, AVX2,
  placa NVIDIA, e duas contas com numpy - a velocidade da memória (copiar
  meio giga) e a de conta (multiplicar matrizes).
- **Por que essas duas.** Num computador sem placa de vídeo, escrever cada
  palavra obriga o modelo inteiro a passar pela memória: é a velocidade da
  memória que manda. Ler os documentos antes de responder é conta pesada: é
  a velocidade de conta que manda - e o tipo de compressão do modelo
  (quantização) pesa muito: o mesmo 3B lê quase o dobro em Q4 do que em Q8,
  medido.
- **A calibração.** A ligação entre o teste e a velocidade real vem de
  AMOSTRAS: uma máquina testada mais um modelo medido nela ("Medir", em
  Configurações › Modelos). As amostras de base vão com o programa
  (calibracao_base.json); cada "Medir" feito aqui vira amostra local, e a
  estimativa desta máquina se corrige por ela.
- **A qualidade não depende da máquina.** O mesmo modelo responde igual em
  qualquer computador; quanto ele acertou no nosso banco de provas
  (tools/demo/roteiro.py) vai numa tabela fixa (modelos.QUALIDADE).

É estimativa, e a tela diz isso. Depois de baixar, o "Medir" dá o número de
verdade - e ele passa a valer no lugar da estimativa.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from statistics import median

VERSAO_DO_TESTE = 2
BASE_PATH = Path(__file__).with_name("calibracao_base.json")

# A pergunta típica, em tokens (a unidade que o modelo lê e escreve; em
# português, perto de três caracteres cada). A primeira pergunta sobre um
# documento de umas três páginas lê o documento inteiro mais as instruções; as
# seguintes sobre o mesmo documento aproveitam o que o Ollama já leu e leem só
# a pergunta nova.
LER_PRIMEIRA = 2300
LER_SEGUINTE = 150
ESCREVER = 200
# Acima disto a primeira resposta cansa: a recomendação procura um modelo que
# caiba aqui antes de ir para o de melhor nota.
LIMITE_PRIMEIRA_S = 120
# Abaixo desta nota o modelo não é recomendado nem sendo o único rápido: o
# llama3.2:1b é duas vezes mais rápido que o 3b e acertou 22 de 41 - errar
# rápido não serve.
NOTA_MINIMA = 0.85
# O que o Windows, o PAULUS e o navegador ocupam: não fica para o modelo.
RESERVA_SISTEMA_GB = 3.5


# ------------------------------------------------------------ o teste

def _banda_gbs(nucleos: int) -> float:
    """
    Gigabytes por segundo copiando meio giga. Escolhe quantas linhas em
    paralelo enchem a memória e fica com a MEDIANA de várias cópias: o modelo
    escreve por minutos, no ritmo sustentado, e não no pico do turbo.
    """
    import numpy as np

    n = 64 * 1024 * 1024  # 256 MB de float32
    a = np.ones(n, dtype=np.float32)
    b = np.empty_like(a)

    def copiar(linhas: int) -> float:
        fatias = [(i * n // linhas, (i + 1) * n // linhas) for i in range(linhas)]
        comeco = time.perf_counter()
        ts = [threading.Thread(target=np.copyto, args=(b[i:j], a[i:j])) for i, j in fatias]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        return 2 * a.nbytes / (time.perf_counter() - comeco) / 1e9

    opcoes = sorted({1, 2, min(4, nucleos), min(8, nucleos)})
    melhor = max(opcoes, key=lambda linhas: max(copiar(linhas) for _ in range(2)))
    # Por tempo, e não por contagem: uma cópia atrapalhada pelo Windows no
    # meio de nove mudava a mediana; no meio de trinta, não.
    medidas = []
    fim = time.perf_counter() + 1.2
    while time.perf_counter() < fim or len(medidas) < 9:
        medidas.append(copiar(melhor))
    return round(median(medidas), 1)


def _gflops(segundos: float = 1.5) -> float:
    """
    Bilhões de contas por segundo multiplicando matrizes 1024 x 1024 durante
    um segundo e meio; a mediana. Com o melhor de seis, o pico de turbo de um
    notebook fazia o teste dizer 356 com a leitura real parada em 60 tokens/s.
    """
    import numpy as np

    m = np.random.default_rng(7).random((1024, 1024), dtype=np.float32)
    m @ m  # aquece
    medidas = []
    fim = time.perf_counter() + segundos
    while time.perf_counter() < fim or len(medidas) < 5:
        comeco = time.perf_counter()
        m @ m
        medidas.append(2 * 1024 ** 3 / (time.perf_counter() - comeco) / 1e9)
    return round(median(medidas), 1)


def _processador() -> str:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
            return " ".join(str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).split())
    except OSError:
        import platform

        return platform.processor() or "processador desconhecido"


def _instrucoes() -> dict:
    """AVX2 é o que o Ollama usa para ser rápido em processador; sem ele, tudo fica bem mais lento."""
    try:
        import ctypes

        k = ctypes.windll.kernel32
        return {"avx2": bool(k.IsProcessorFeaturePresent(40)), "avx512": bool(k.IsProcessorFeaturePresent(41))}
    except (AttributeError, OSError):
        return {"avx2": None, "avx512": None}


def _placas_nvidia() -> list[dict]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return []
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        saida = subprocess.run([exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                               capture_output=True, text=True, timeout=5, creationflags=flags).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    placas = []
    for linha in saida.strip().splitlines():
        nome, _, mb = linha.rpartition(",")
        try:
            placas.append({"nome": nome.strip(), "memoria_gb": round(float(mb) / 1024, 1)})
        except ValueError:
            continue
    return placas


FABRICANTES = (("nvidia", "NVIDIA"), ("amd", "AMD"), ("advanced micro", "AMD"), ("radeon", "AMD"), ("ati ", "AMD"),
               ("intel", "Intel"), ("qualcomm", "Qualcomm"), ("adreno", "Qualcomm"))
# Adaptador que não é placa: a tela da área de trabalho remota, o driver
# genérico do Windows, o de captura.
NAO_E_PLACA = ("microsoft basic", "remote display", "remote desktop", "hyper-v", "virtual", "parsec", "citrix",
               "displaylink", "spacedesk", "idd")


def _fabricante(nome: str, compat: str) -> str:
    texto = f"{nome} {compat}".lower() + " "
    return next((f for chave, f in FABRICANTES if chave in texto), "outra")


def _integrada(nome: str, fabricante: str) -> bool:
    """A placa que divide a memória com o processador (Intel UHD/Iris/Arc integrada, AMD Radeon Graphics)."""
    n = nome.lower()
    if fabricante == "Intel":
        return not re.search(r"\barc\b.*\b[ab]\d{3}\b", n)   # Arc A380/A770/B580 são placas próprias
    if fabricante == "AMD":
        return not re.search(r"\b(rx|pro w|firepro|instinct)\b", n)
    return fabricante == "Qualcomm"


def ler_placas_do_windows(bruto: str) -> list[dict]:
    """As placas de vídeo, a partir do JSON do Win32_VideoController (separado para dar para testar)."""
    try:
        dados = json.loads(bruto or "[]")
    except ValueError:
        return []
    if isinstance(dados, dict):
        dados = [dados]
    placas = []
    for d in dados or []:
        nome = str(d.get("Name") or "").strip()
        if not nome or any(x in nome.lower() for x in NAO_E_PLACA):
            continue
        fabricante = _fabricante(nome, str(d.get("AdapterCompatibility") or ""))
        ram = d.get("AdapterRAM")
        placas.append({
            "nome": nome, "fabricante": fabricante, "integrada": _integrada(nome, fabricante),
            # O AdapterRAM é um inteiro de 32 bits: acima de 4 GB o Windows
            # informa 4 GB (ou nada). Serve de ordem de grandeza, não de conta.
            "memoria_gb": round(float(ram) / 1024 ** 3, 1) if isinstance(ram, (int, float)) and ram > 0 else None,
        })
    return placas


def _placas_windows() -> list[dict]:
    """Todas as placas de vídeo pelo Windows (NVIDIA, AMD, Intel), sem depender do driver de cada fabricante."""
    import os

    if os.name != "nt":
        return []
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        saida = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "Get-CimInstance Win32_VideoController | Select-Object Name, AdapterCompatibility, AdapterRAM | "
             "ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=10, creationflags=flags).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return ler_placas_do_windows(saida)


def na_placa(host: str, nome: str, pegar=None) -> float | None:
    """
    A fração do modelo que o Ollama pôs na memória da placa (`size_vram` /
    `size` do /api/ps), com o modelo carregado: é a medida que decide se a placa
    é usada - placa detectada que o Ollama não usa não conta. None: não deu
    para saber.
    """
    import requests

    try:
        resp = (pegar or requests.get)(f"{host}/api/ps", timeout=5)
        resp.raise_for_status()
        modelos = resp.json().get("models") or []
    except Exception:  # noqa: BLE001 - sem o Ollama agora, fica sem saber
        return None
    for m in modelos:
        if m.get("name") == nome or m.get("model") == nome or m.get("name", "").split(":")[0] == nome.split(":")[0]:
            total = m.get("size") or 0
            return round(float(m.get("size_vram") or 0) / total, 2) if total else None
    return None


def _na_bateria() -> bool | None:
    import psutil

    try:
        bateria = psutil.sensors_battery()
    except Exception:  # noqa: BLE001
        return None
    return None if bateria is None else not bateria.power_plugged


def testar() -> dict:
    """O teste da máquina: nenhum modelo, uns cinco segundos."""
    import psutil

    comeco = time.time()
    memoria = psutil.virtual_memory()
    nucleos = psutil.cpu_count(logical=False) or psutil.cpu_count() or 1
    processador = _processador()
    resultado = {
        "versao": VERSAO_DO_TESTE,
        "processador": processador,
        "nucleos": nucleos,
        "linhas": psutil.cpu_count() or nucleos,
        "ram_total_gb": round(memoria.total / 1e9, 1),
        "ram_livre_gb": round(memoria.available / 1e9, 1),
        **_instrucoes(),
        "placas_nvidia": _placas_nvidia(),
        # Todas as placas, de qualquer fabricante (ideia F do umbrelOS,
        # docs/DECISAO-UMBREL.md). Se o Ollama usa alguma, diz a medida.
        "placas": _placas_windows(),
        # Notebook na bateria: o Windows segura o processador, e o modelo fica
        # mais lento do que na tomada. O teste mede o estado da hora.
        "na_bateria": _na_bateria(),
        "banda_gbs": _banda_gbs(nucleos),
        "gflops": _gflops(),
    }
    resultado["id"] = hashlib.sha1(f"{processador}|{nucleos}|{round(memoria.total / 1e9)}".encode()).hexdigest()[:12]
    resultado["segundos"] = round(time.time() - comeco, 1)
    resultado["quando"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return resultado


# ------------------------------------------------------ as amostras

def familia(quantizacao: str) -> str:
    """Q4_K_M, Q4_0, Q5_K_M... leem parecido; Q8_0 e F16, bem mais devagar (medido)."""
    q = (quantizacao or "").upper()
    if re.match(r"(IQ|Q)[2-5]", q):
        return "q4"
    if q.startswith(("Q6", "Q8")):
        return "q8"
    if q.startswith(("F16", "BF16", "F32")):
        return "f16"
    return "q4"


def parametros_b(texto) -> float:
    """'3.2B' -> 3.2; '494M' -> 0.494; número passa direto."""
    if isinstance(texto, (int, float)):
        return float(texto)
    achado = re.match(r"\s*([\d.]+)\s*([BM])", str(texto or ""), re.I)
    if not achado:
        return 0.0
    valor = float(achado.group(1))
    return valor / 1000 if achado.group(2).upper() == "M" else valor


def amostra(maquina: dict, modelo: dict, medida: dict) -> dict:
    """
    Uma amostra de calibração: o teste da máquina, o modelo e a medida real.
    Nada de quem usa - só números da máquina e do modelo. É o formato que
    poderá ir ao servidor, com a permissão de quem usa, para a estimativa
    melhorar com as máquinas de todos.
    """
    return {
        "maquina": {k: maquina.get(k) for k in ("id", "versao", "processador", "nucleos", "ram_total_gb",
                                                 "avx2", "banda_gbs", "gflops", "na_bateria")},
        # Com a medida dizendo onde o Ollama pôs o modelo (`na_placa`, a fração
        # que foi para a memória da placa), é ela que vale - uma Intel ou AMD
        # integrada conta como placa só quando o Ollama a usa de verdade.
        "gpu": (medida.get("na_placa", 0) >= 0.5) if "na_placa" in medida else bool(maquina.get("placas_nvidia")),
        "modelo": modelo["nome"],
        "tamanho_gb": modelo["gb"],
        "parametros_b": parametros_b(modelo.get("parametros")),
        "quantizacao": modelo.get("quantizacao", ""),
        "escrita_tps": medida.get("tokens_por_segundo", 0.0),
        "leitura_tps": medida.get("leitura_tokens_por_segundo", 0.0),
        "quando": medida.get("quando", ""),
    }


def ler_amostras(caminho: Path) -> list[dict]:
    try:
        return list(json.loads(caminho.read_text(encoding="utf-8")).get("amostras", []))
    except (OSError, ValueError):
        return []


def guardar_amostra(caminho: Path, nova: dict) -> None:
    """Uma por máquina e modelo: medir de novo troca a antiga."""
    amostras = [a for a in ler_amostras(caminho)
                if not (a["maquina"].get("id") == nova["maquina"].get("id") and a["modelo"] == nova["modelo"])]
    amostras.append(nova)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps({"amostras": amostras}, ensure_ascii=False, indent=1), encoding="utf-8")


# -------------------------------------------------------- calibração

def calibrar(amostras: list[dict]) -> dict:
    """
    Tira das amostras a ligação entre o teste e a velocidade real.

    Escrever: o tempo de cada token é o modelo passando pela memória mais
    um tanto de conta - t = a * tamanho / banda + b * (2 * parâmetros) /
    contas. Ler: tokens por segundo = k * contas / parâmetros, com um k por
    família de quantização.

    Só entram amostras de processador (com placa de vídeo, a conta é outra).
    """
    import numpy as np

    usaveis = [a for a in amostras if not a.get("gpu") and a.get("escrita_tps") and a["maquina"].get("banda_gbs")
               and a["maquina"].get("gflops") and a.get("parametros_b")]
    escrita = {"a": 1.0, "b": 2.5}
    if len(usaveis) >= 2:
        x = np.array([[a["tamanho_gb"] / a["maquina"]["banda_gbs"],
                       2 * a["parametros_b"] / a["maquina"]["gflops"]] for a in usaveis])
        y = np.array([1 / a["escrita_tps"] for a in usaveis])
        coef, *_ = np.linalg.lstsq(x, y, rcond=None)
        if (coef > 0).all():
            escrita = {"a": float(coef[0]), "b": float(coef[1])}
        else:
            # Poucas amostras parecidas demais: fica só a memória, que é o
            # que mais pesa, com o fator que melhor explica as medidas.
            escrita = {"a": float(median(y[i] / x[i, 0] for i in range(len(y)))), "b": 0.0}
    leitura: dict[str, float] = {}
    for fam in ("q4", "q8", "f16"):
        ks = [a["leitura_tps"] * a["parametros_b"] / a["maquina"]["gflops"] for a in usaveis
              if a.get("leitura_tps") and familia(a.get("quantizacao", "")) == fam]
        if ks:
            leitura[fam] = float(median(ks))
    return {"escrita": escrita, "leitura": leitura, "amostras": len(usaveis),
            "maquinas": len({a["maquina"].get("id") for a in usaveis})}


def _bruto(modelo: dict, maquina: dict, calib: dict) -> tuple[float, float, str]:
    """Escrita e leitura em tokens por segundo, pela física calibrada. E quão certo é."""
    p = parametros_b(modelo.get("parametros")) or 1.0
    t_token = (calib["escrita"]["a"] * modelo["gb"] / maquina["banda_gbs"]
               + calib["escrita"]["b"] * 2 * p / maquina["gflops"])
    escrita = 1 / t_token if t_token > 0 else 0.0
    fam = familia(modelo.get("quantizacao", ""))
    k = calib["leitura"].get(fam)
    confianca = "calibrado"
    if k is None:
        # Família sem amostra: usa a mais lenta que houver, e diz que é aproximado.
        k = min(calib["leitura"].values()) if calib["leitura"] else 0.3
        confianca = "aproximado"
    leitura = k * maquina["gflops"] / p
    return escrita, leitura, confianca


def correcao_local(maquina: dict, calib: dict, amostras_locais: list[dict]) -> dict:
    """
    O quanto esta máquina foge da calibração, pelo que já foi medido nela.
    Sem amostra daqui, 1: vale a calibração pura.
    """
    daqui = [a for a in amostras_locais if a["maquina"].get("id") == maquina.get("id")]
    escrita, leitura = [], []
    for a in daqui:
        modelo = {"gb": a["tamanho_gb"], "parametros": a["parametros_b"], "quantizacao": a["quantizacao"]}
        e, l, _ = _bruto(modelo, maquina, calib)
        if a.get("escrita_tps") and e:
            escrita.append(a["escrita_tps"] / e)
        if a.get("leitura_tps") and l:
            leitura.append(a["leitura_tps"] / l)
    return {"escrita": median(escrita) if escrita else 1.0, "leitura": median(leitura) if leitura else 1.0,
            "medidos": len(daqui)}


def estimar(modelo: dict, maquina: dict, calib: dict, correcao: dict, medida: dict | None = None) -> dict:
    """
    Quanto o modelo demora nesta máquina numa pergunta típica, e se cabe na
    memória. Com medida real daqui, vale a medida.
    """
    p = parametros_b(modelo.get("parametros")) or 1.0
    if medida and medida.get("tokens_por_segundo") and medida.get("leitura_tokens_por_segundo"):
        escrita, leitura, fonte = medida["tokens_por_segundo"], medida["leitura_tokens_por_segundo"], "medido"
    else:
        escrita, leitura, confianca = _bruto(modelo, maquina, calib)
        escrita *= correcao["escrita"]
        leitura *= correcao["leitura"]
        fonte = "estimado" if confianca == "calibrado" else "aproximado"
    # O modelo, o espaço da conversa (umas oito mil unidades de texto) e uma folga.
    precisa = modelo["gb"] + 0.3 * p + 0.5
    disponivel = max(0.0, maquina["ram_total_gb"] - RESERVA_SISTEMA_GB)
    primeira = LER_PRIMEIRA / leitura + ESCREVER / escrita if leitura and escrita else None
    seguinte = LER_SEGUINTE / leitura + ESCREVER / escrita if leitura and escrita else None
    return {
        "escrita_tps": round(escrita, 1),
        "leitura_tps": round(leitura, 1),
        "primeira_s": round(primeira) if primeira else None,
        "seguinte_s": round(seguinte) if seguinte else None,
        "precisa_gb": round(precisa, 1),
        "cabe": precisa <= disponivel,
        # Cabe no total, mas não no que está livre agora: vai disputar memória.
        "apertado": precisa <= disponivel and precisa > maquina.get("ram_livre_gb", disponivel),
        "fonte": fonte,
    }


def recomendar(modelos: list[dict], maquina: dict, calib: dict, correcao: dict, qualidade: dict,
               medidas: dict) -> dict:
    """
    Cada modelo com a estimativa e a nota, e o recomendado.

    A regra: entre os que têm nota no nosso banco de provas e cabem na
    memória, o de melhor nota que responde a primeira pergunta dentro do
    limite; empate, o mais rápido. Nenhum dentro do limite: o mais rápido que
    cabe, avisando que vai ser lento. Modelo sem nota nunca é recomendado -
    rápido que erra não serve; nem modelo com nota abaixo da mínima.
    """
    linhas = []
    for m in modelos:
        e = estimar(m, maquina, calib, correcao, medidas.get(m["nome"]))
        q = qualidade.get(m["nome"])
        linhas.append({**m, "estimativa": e, "qualidade": q})
    def nota(x):
        return x["qualidade"]["certas"] / x["qualidade"]["total"]

    com_nota = [x for x in linhas if x["qualidade"] and nota(x) >= NOTA_MINIMA
                and x["estimativa"]["cabe"] and x["estimativa"]["primeira_s"]]

    rapidos = [x for x in com_nota if x["estimativa"]["primeira_s"] <= LIMITE_PRIMEIRA_S]
    escolhido, lento = None, False
    if rapidos:
        escolhido = sorted(rapidos, key=lambda x: (-nota(x), x["estimativa"]["primeira_s"]))[0]
    elif com_nota:
        escolhido = sorted(com_nota, key=lambda x: x["estimativa"]["primeira_s"])[0]
        lento = True
    for x in linhas:
        x["recomendado"] = x is escolhido
    porque = ""
    if escolhido:
        q, e = escolhido["qualidade"], escolhido["estimativa"]
        porque = (f"acertou {q['certas']} de {q['total']} perguntas no nosso teste; nesta máquina, "
                  f"a primeira pergunta sobre um documento deve levar ~{e['primeira_s']} s e as seguintes ~{e['seguinte_s']} s")
        if lento:
            porque += ". É o mais rápido dos que testamos, e ainda assim vai ser lento aqui"
    elif linhas:
        porque = ("nenhum dos modelos que acertam o suficiente no nosso teste cabe na memória desta máquina "
                  f"({maquina['ram_total_gb']:.1f} GB)").replace(".", ",", 1)
    return {"modelos": linhas, "recomendado": escolhido["nome"] if escolhido else "", "porque": porque,
            "lento": lento, "limite_s": LIMITE_PRIMEIRA_S}


# ----------------------------------------------------- base do programa

def montar_base(host: str, modelos_para_medir: list[str]) -> dict:
    """
    As amostras que vão com o programa: testa esta máquina, mede cada modelo
    e grava calibracao_base.json. Rodar numa máquina de cliente do piloto
    acrescenta outra máquina à base (as amostras antigas ficam).

        venv\\Scripts\\python.exe src\\maquina.py --base llama3.2:3b llama3.2:3b-instruct-q8_0
    """
    import modelos as modelos_mod

    maq = testar()
    instalados = {m["nome"]: m for m in modelos_mod.instalados(host)}
    for nome in modelos_para_medir:
        if nome not in instalados:
            print(f"  {nome}: não está instalado, pulei")
            continue
        modelos_mod.medir(host, nome)  # a primeira carrega o modelo; a segunda vale
        medida = modelos_mod.medir(host, nome)
        guardar_amostra(BASE_PATH, amostra(maq, instalados[nome], medida))
        print(f"  {nome}: escreve {medida['tokens_por_segundo']} e lê {medida['leitura_tokens_por_segundo']} tokens/s")
    return calibrar(ler_amostras(BASE_PATH))


if __name__ == "__main__":
    import sys

    if "--base" in sys.argv:
        nomes = [a for a in sys.argv[sys.argv.index("--base") + 1:] if not a.startswith("--")]
        print(json.dumps(montar_base("http://localhost:11434", nomes), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(testar(), ensure_ascii=False, indent=1))
