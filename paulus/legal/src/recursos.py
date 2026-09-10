"""
PAULUS - Leitura de recursos da maquina.

O manual exige tres medidores reais: Video, Memoria e Processador. Numero
inventado num medidor e mentira na cara do usuario, entao aqui cada valor ou e
medido de verdade ou vem marcado como indisponivel.

Processador e memoria: psutil, leitura instantanea.
Video: contador de desempenho do Windows. A leitura custa ~9s (medido nesta
maquina), entao roda numa thread separada, em ritmo lento, e a interface mostra
ha quanto tempo o valor foi medido. Chamar isso a cada segundo derrubaria a
maquina que estamos tentando medir.
"""

from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass

import psutil

INTERVALO_VIDEO = 30.0        # segundos entre leituras de GPU
LIMITE_CPU_OCUPADO = 70.0     # acima disso, "ir devagar" segura o trabalho

# ToString(InvariantCulture) por causa do Windows em portugues: sem isso o
# PowerShell devolve "1,2" e o float() do Python estoura.
_COMANDO_GPU = (
    "$ErrorActionPreference='SilentlyContinue';"
    "$c = (Get-Counter '\\GPU Engine(*)\\Utilization Percentage').CounterSamples |"
    " Where-Object CookedValue -gt 0;"
    "if ($c) { [math]::Round((($c | Measure-Object CookedValue -Sum).Sum), 1)"
    ".ToString([System.Globalization.CultureInfo]::InvariantCulture) } else { 'x' }"
)


@dataclass
class Video:
    percentual: float | None = None
    medido_em: float = 0.0
    disponivel: bool = True

    @property
    def segundos_atras(self) -> int:
        return int(time.time() - self.medido_em) if self.medido_em else 0


class LeitorDeVideo:
    """Amostra a GPU em segundo plano, sem travar a interface."""

    def __init__(self) -> None:
        self.estado = Video()
        self._thread: threading.Thread | None = None
        self._parar = threading.Event()

    def _ler_uma_vez(self) -> None:
        try:
            saida = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", _COMANDO_GPU],
                capture_output=True,
                text=True,
                timeout=25,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            self.estado = Video(disponivel=False)
            return

        try:
            # virgula decimal ainda pode escapar por outro caminho de locale
            self.estado = Video(percentual=min(float(saida.replace(",", ".")), 100.0), medido_em=time.time())
        except ValueError:
            # 'x' quando nenhum motor de GPU esta ativo: 0% e leitura valida.
            self.estado = Video(percentual=0.0, medido_em=time.time()) if saida == "x" else Video(disponivel=False)

    def _laco(self) -> None:
        while not self._parar.is_set():
            self._ler_uma_vez()
            if not self.estado.disponivel:
                return  # nao insiste num contador que nao existe
            self._parar.wait(INTERVALO_VIDEO)

    def acordar(self) -> None:
        """
        Comeca a amostrar. Chamado quando alguem esta olhando os medidores -
        nao ha por que gastar CPU medindo CPU que ninguem le.
        """
        if self._thread and self._thread.is_alive():
            return
        self._parar.clear()
        self._thread = threading.Thread(target=self._laco, daemon=True)
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()


_video = LeitorDeVideo()


def frase_de_estado(cpu: float, memoria_pct: float) -> str:
    """
    O que o usuario leigo realmente le, acima dos numeros.

    Regra do manual: linguagem de pessoa. "Uso de GPU em 62%" nao diz nada;
    "da para trabalhar normal" diz.
    """
    if memoria_pct >= 92:
        return "Memoria no limite - o computador pode ficar lento"
    if cpu >= 88:
        return "Trabalhando pesado - pode travar um pouco"
    if cpu >= 60 or memoria_pct >= 80:
        return "Ocupado, tranquilo - da para trabalhar normal"
    return "Tranquilo - quase nao esta usando o computador"


def ler(*, acordar_video: bool = True) -> dict:
    """Estado atual da maquina, pronto para a interface."""
    if acordar_video:
        _video.acordar()

    memoria = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=None)
    video = _video.estado

    return {
        "processador": {"percentual": round(cpu, 1)},
        "memoria": {
            "percentual": round(memoria.percent, 1),
            "usado_gb": round(memoria.used / 1024**3, 1),
            "total_gb": round(memoria.total / 1024**3, 1),
        },
        "video": {
            "percentual": round(video.percentual, 1) if video.percentual is not None else None,
            "disponivel": video.disponivel,
            "segundos_atras": video.segundos_atras,
        },
        "frase": frase_de_estado(cpu, memoria.percent),
        "ocupado": cpu >= LIMITE_CPU_OCUPADO,
    }


def esperar_maquina_livre(ativo: bool, *, limite_s: float = 20.0) -> float:
    """
    Segura o trabalho enquanto a pessoa esta usando o computador.

    E o que faz o interruptor "Ir devagar quando eu usar o PC" ser real e nao
    decorativo. Devolve quantos segundos esperou.
    """
    if not ativo:
        return 0.0

    inicio = time.time()
    while time.time() - inicio < limite_s:
        if psutil.cpu_percent(interval=0.5) < LIMITE_CPU_OCUPADO:
            break
    return round(time.time() - inicio, 1)


if __name__ == "__main__":
    psutil.cpu_percent(interval=None)  # primeira chamada e sempre 0
    time.sleep(1)
    estado = ler()
    print(estado["frase"])
    print(f"  processador {estado['processador']['percentual']}%")
    print(f"  memoria     {estado['memoria']['usado_gb']} GB de {estado['memoria']['total_gb']} GB")
    print("  video       medindo em segundo plano...")
    time.sleep(12)
    print(f"  video       {ler()['video']}")
