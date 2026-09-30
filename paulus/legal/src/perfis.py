"""
Modelo por máquina (docs/PLANO-PILOTO.md, L6): o perfil desta máquina, pela
faixa de hardware do teste que já existe (src/maquina.py) - memória, placa de
vídeo e fabricante.

- **NVIDIA** com memória própria: o Ollama usa a placa sozinho (CUDA). Pela
  memória da placa (nvidia-smi, exata): até 4 GB, o 3B de fábrica cabe
  inteiro; de 6 GB, o 3B em 8 bits (o de melhor nota) cabe inteiro; de 10 GB,
  cabe um 7-8B - que ainda não tem nota no roteiro desta casa: meça antes.
- **AMD** com memória própria: nas Radeon que o Ollama roda por ROCm no
  Windows (RX 7600 a 7900, RX 6800 a 6950, Vega, PRO W6800/W7x00), sozinho;
  nas outras, pelo Vulkan (`OLLAMA_VULKAN=1`, experimental no Ollama).
- **Intel Arc** com memória própria: pelo Vulkan.
- **Placa integrada** (Intel UHD/Iris, AMD Radeon Graphics): divide a memória
  com o processador; o perfil é o do processador.
- **Só processador**: pela memória - abaixo de 8 GB, o 1B (acerta 22 de 41
  no roteiro: a tela diz isso); de 8 GB, o 3B de fábrica.

A memória das placas AMD e Intel vem do Windows, que não informa mais que
4 GB: é ordem de grandeza, e o perfil diz. Nada é trocado sozinho: o perfil
sugere, a pessoa mede em Modelos e troca. Ligar o Vulkan grava a variável na
conta do Windows (HKCU\\Environment) e pede para reabrir o Ollama.
"""

from __future__ import annotations

import os
import re

from fastapi import HTTPException, Request
from pydantic import BaseModel

ROCM_WINDOWS = re.compile(r"\brx\s*7(6|7|8|9)\d\d|\brx\s*6(8|9)\d\d|\bvega\b|\bpro\s*w(68|7\d)\d\d", re.IGNORECASE)
PADRAO = "llama3.2:3b"
OITO_BITS = "llama3.2:3b-instruct-q8_0"
LEVE = "llama3.2:1b"
GRANDE = "qwen2.5:7b"


def _gb(x) -> str:
    return f"{float(x):g}".replace(".", ",")


def _placa_propria(maquina: dict) -> dict | None:
    """A melhor placa com memória própria: {nome, fabricante, memoria_gb, exata}."""
    nvidia = [dict(p, fabricante="NVIDIA", exata=True) for p in maquina.get("placas_nvidia") or []]
    outras = [dict(p, exata=False) for p in maquina.get("placas") or []
              if not p.get("integrada") and p.get("fabricante") in ("AMD", "Intel", "NVIDIA")]
    nomes_nvidia = {p["nome"].lower() for p in nvidia}
    outras = [p for p in outras if not (p["fabricante"] == "NVIDIA" and p["nome"].lower() in nomes_nvidia)]
    todas = nvidia + [p for p in outras if p["fabricante"] != "NVIDIA" or not nvidia]
    if not todas:
        return None
    return max(todas, key=lambda p: (p["fabricante"] == "NVIDIA", p.get("memoria_gb") or 0))


def perfil(maquina: dict | None) -> dict:
    if not maquina:
        return {"faixa": "sem-teste", "rotulo": "Sem o teste da máquina", "modelo": PADRAO, "explica": ["Faça o teste da máquina primeiro."],
                "ollama": {}, "avisos": []}
    ram = float(maquina.get("ram_total_gb") or 0)
    placa = _placa_propria(maquina)
    integradas = [p["nome"] for p in maquina.get("placas") or [] if p.get("integrada")]
    avisos: list[str] = []
    ollama: dict = {"motor": "processador", "variavel": "", "explica": ""}
    if placa and placa["fabricante"] == "NVIDIA":
        vram = float(placa.get("memoria_gb") or 0)
        ollama = {"motor": "CUDA", "variavel": "", "explica": "O Ollama usa a placa NVIDIA sozinho, com o driver da NVIDIA."}
        if vram >= 10:
            faixa, modelo, alt = "gpu-grande", OITO_BITS, GRANDE
            explica = [f"{placa['nome']} com {_gb(vram)} GB: o 3B em 8 bits cabe inteiro na placa, e sobra lugar.",
                       f"Cabe um modelo de 7-8B ({GRANDE}): ele ainda não tem nota no roteiro desta casa. Meça em Modelos antes de trocar."]
        elif vram >= 6:
            faixa, modelo, alt = "gpu-media", OITO_BITS, PADRAO
            explica = [f"{placa['nome']} com {_gb(vram)} GB: o 3B em 8 bits (a melhor nota do banco de provas) cabe inteiro na placa."]
        elif vram >= 3.5:
            faixa, modelo, alt = "gpu-pequena", PADRAO, LEVE
            explica = [f"{placa['nome']} com {_gb(vram)} GB: o 3B de fábrica cabe inteiro na placa."]
        else:
            faixa, modelo, alt = "cpu", PADRAO, LEVE
            explica = [f"{placa['nome']} tem só {_gb(vram)} GB: o modelo não cabe inteiro nela; o Ollama divide com o processador."]
        rotulo = "Placa NVIDIA"
    elif placa and placa["fabricante"] in ("AMD", "Intel"):
        vram = placa.get("memoria_gb")
        rocm = placa["fabricante"] == "AMD" and bool(ROCM_WINDOWS.search(placa["nome"]))
        if rocm:
            ollama = {"motor": "ROCm", "variavel": "", "explica": "Esta Radeon está na lista das que o Ollama roda por ROCm no Windows: ele usa a placa sozinho."}
        else:
            ollama = {"motor": "Vulkan", "variavel": "OLLAMA_VULKAN",
                      "explica": "Esta placa não está na lista do ROCm; o Ollama pode usá-la pelo Vulkan, que ainda é experimental nele. "
                                 "Ligar grava OLLAMA_VULKAN=1 na sua conta do Windows; depois, reabra o Ollama e meça em Modelos."}
        faixa = "gpu-amd" if placa["fabricante"] == "AMD" else "gpu-intel"
        rotulo = "Placa AMD" if placa["fabricante"] == "AMD" else "Placa Intel Arc"
        modelo, alt = PADRAO, OITO_BITS
        explica = [f"{placa['nome']}" + (f", cerca de {_gb(vram)} GB pelo Windows" if vram else "") + ": o 3B de fábrica é o ponto de partida."]
        avisos.append("O Windows não informa mais que 4 GB de memória das placas AMD e Intel: o número é ordem de grandeza.")
    else:
        faixa, rotulo = ("cpu-leve", "Só o processador, pouca memória") if ram < 8 else ("cpu", "Só o processador")
        if ram < 8:
            modelo, alt = LEVE, PADRAO
            explica = [f"{_gb(ram)} GB de memória: o 3B mal cabe com o Windows aberto; o 1B cabe, mas acerta 22 de 41 perguntas do roteiro."]
            avisos.append("Com 8 GB de memória, o 3B de fábrica passa a caber.")
        else:
            modelo, alt = PADRAO, LEVE
            explica = [f"{_gb(ram)} GB de memória: o 3B de fábrica cabe (acertou 41 de 41 no roteiro)."]
        if integradas:
            explica.append(f"A placa {integradas[0]} é integrada: divide a memória com o processador, e o Ollama usa o processador.")
    return {"faixa": faixa, "rotulo": rotulo, "modelo": modelo, "alternativa": alt, "placa": placa, "ram_gb": ram,
            "explica": explica, "ollama": ollama, "avisos": avisos}


# ------------------------------------------------------------ a variável do Vulkan

def vulkan_ligado() -> bool:
    """OLLAMA_VULKAN na conta do Windows (HKCU\\Environment) - é dela que o Ollama lê ao abrir."""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            valor, _ = winreg.QueryValueEx(k, "OLLAMA_VULKAN")
            return str(valor).strip() == "1"
    except (ImportError, OSError):
        return os.environ.get("OLLAMA_VULKAN") == "1"


def ligar_vulkan(ligar: bool) -> None:
    import ctypes
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as k:
        if ligar:
            winreg.SetValueEx(k, "OLLAMA_VULKAN", 0, winreg.REG_SZ, "1")
        else:
            try:
                winreg.DeleteValue(k, "OLLAMA_VULKAN")
            except FileNotFoundError:
                pass
    # Avisa os programas abertos de que o ambiente mudou (o Ollama lê ao reabrir).
    try:
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 0x0002, 3000, None)
    except (AttributeError, OSError):
        pass


# ------------------------------------------------------------------ rotas

class Vulkan(BaseModel):
    ligar: bool


# Os testes trocam quem grava a variável.
_ESCRITOR = {"ligar": ligar_vulkan, "ler": vulkan_ligado}


def montar(app, maquina) -> None:
    """`maquina`: () -> o teste desta máquina (api._maquina)."""
    from acesso import rotas as rotas_do_acesso

    @app.get("/api/maquina/perfil")
    def maquina_perfil() -> dict:
        p = perfil(maquina())
        p["vulkan_ligado"] = bool(_ESCRITOR["ler"]())
        return p

    @app.post("/api/maquina/perfil/vulkan")
    def maquina_vulkan(payload: Vulkan, request: Request = None) -> dict:
        rotas_do_acesso.so_local(request)
        try:
            _ESCRITOR["ligar"](payload.ligar)
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"não consegui gravar a variável do Windows: {exc}") from None
        return {"vulkan_ligado": bool(_ESCRITOR["ler"]()),
                "proximo": "Feche e abra o Ollama (ícone perto do relógio › Quit, e abra de novo); depois meça em Modelos."}
