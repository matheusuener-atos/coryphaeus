"""
PAULUS - Foco e bem-estar.

Ciclo de foco, lembretes e o acompanhamento do dia.

O ponto delicado deste modulo e o que ele mede. Para dizer "voce esta ha duas
horas sem levantar" o programa precisa saber se voce esta usando o computador -
e ha duas formas de saber isso. Uma e ler o teclado, que e um registrador de
teclas com outro nome. A outra e perguntar ao Windows quanto tempo faz desde o
ultimo toque, sem saber qual foi.

Este modulo usa a segunda. GetLastInputInfo devolve um numero: ha quantos
milissegundos houve o ultimo toque de teclado ou mouse. Nao devolve tecla, nao
devolve janela, nao devolve texto. Nao existe caminho daqui para o que foi
digitado, nem que alguem quisesse.

E o que fica guardado e menos ainda: totais do dia. Minutos ativos, quantas
pausas, quantos ciclos, quantos copos de agua. Nao ha linha do tempo, nao ha
"as 14h32 voce parou" - so o total, que e o que serve para a conversa sobre
habito e o que ninguem usaria para vigiar alguem.

Desligar e uma opcao de verdade: sem o acompanhamento, o ciclo de foco e os
lembretes continuam funcionando, e as telas dizem que os numeros de atividade
nao existem em vez de estimar.
"""

from __future__ import annotations

import sys
import threading
import time
from datetime import date, datetime, timedelta

# Sem toque por mais que isso, considera-se que a pessoa saiu.
OCIOSO_SEGUNDOS = 90
INTERVALO_AMOSTRA = 30          # de quanto em quanto tempo pergunta ao sistema

FOCO_PADRAO = 25
PAUSA_PADRAO = 5

LEMBRETES_SUGERIDOS = [
    ("Beber água", 45, 8),
    ("Levantar e caminhar", 120, 6),
    ("Olhar para longe por 20 segundos", 25, 0),
    ("Alongar ombros e pescoço", 180, 3),
]


def tempo_ocioso_segundos() -> float | None:
    """
    Ha quanto tempo ninguem toca no teclado ou no mouse.

    So o tempo. O Windows nao conta qual tecla foi, e este programa nao tem
    como perguntar. Fora do Windows devolve None, e quem chama trata como
    "nao da para medir" em vez de inventar.
    """
    if sys.platform != "win32":
        return None

    import ctypes
    from ctypes import wintypes

    class INFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    info = INFO()
    info.cbSize = ctypes.sizeof(INFO)
    try:
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        agora = ctypes.windll.kernel32.GetTickCount()
    except OSError:
        return None
    return max(0.0, (agora - info.dwTime) / 1000.0)


def da_para_medir() -> bool:
    return tempo_ocioso_segundos() is not None


# ------------------------------------------------------------ o dia


class BemEstar:
    """
    O acompanhamento do dia, os ciclos de foco e os lembretes.

    A amostragem roda numa thread propria e escreve so o total do dia. Se a
    pessoa desligar o acompanhamento, a thread para e nada e gravado.
    """

    def __init__(self, base) -> None:
        self.base = base
        self.ligado = False
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None
        self._trava = threading.Lock()

        # Estado do ciclo de foco - vive na memoria do processo, porque um
        # cronometro que sobrevive ao programa fechado nao faz sentido.
        self.ciclo = {
            "estado": "parado",          # parado | foco | pausa
            "comeca_em": 0.0,
            "duracao": FOCO_PADRAO * 60,
            "foco_min": FOCO_PADRAO,
            "pausa_min": PAUSA_PADRAO,
            "numero": 0,
            "tarefa": "",
            "silenciar": False,
        }
        self._seguida = 0               # minutos ativos sem pausa

    # ------------------------------------------------------- a medicao

    def ligar(self) -> bool:
        if not da_para_medir():
            return False
        with self._trava:
            if self.ligado:
                return True
            self._parar.clear()
            self._thread = threading.Thread(target=self._rodar, daemon=True)
            self._thread.start()
            self.ligado = True
        return True

    def desligar(self) -> None:
        with self._trava:
            self._parar.set()
            self.ligado = False

    def _rodar(self) -> None:
        """Pergunta ao sistema de tempos em tempos e soma o total do dia."""
        while not self._parar.wait(INTERVALO_AMOSTRA):
            ocioso = tempo_ocioso_segundos()
            if ocioso is None:
                continue
            if ocioso < OCIOSO_SEGUNDOS:
                minutos = INTERVALO_AMOSTRA / 60
                self._somar(minutos_ativos=minutos)
                self._seguida += minutos
                self._guardar_seguida()
            else:
                # Ficou longe do computador: a sequencia recomeca.
                self._seguida = 0

    def _somar(self, **campos) -> None:
        hoje = date.today().isoformat()
        self._garantir_dia(hoje)
        for campo, quanto in campos.items():
            self.base.escrever(
                f"UPDATE bem_estar SET {campo} = {campo} + ?, "
                "atualizado_em = datetime('now','localtime') WHERE dia = ?",
                (int(round(quanto)) if campo != "minutos_ativos" else quanto, hoje),
            )

    def _guardar_seguida(self) -> None:
        hoje = date.today().isoformat()
        self.base.escrever(
            "UPDATE bem_estar SET maior_seguida = MAX(maior_seguida, ?) WHERE dia = ?",
            (int(self._seguida), hoje),
        )

    def _garantir_dia(self, dia: str) -> None:
        self.base.escrever(
            "INSERT INTO bem_estar (dia, atualizado_em) "
            "VALUES (?, datetime('now','localtime')) ON CONFLICT(dia) DO NOTHING",
            (dia,),
        )

    # --------------------------------------------------- o ciclo de foco

    def comecar_ciclo(self, tarefa: str = "", foco: int = 0, pausa: int = 0) -> dict:
        self.ciclo["foco_min"] = max(1, min(int(foco or self.ciclo["foco_min"]), 180))
        self.ciclo["pausa_min"] = max(1, min(int(pausa or self.ciclo["pausa_min"]), 60))
        self.ciclo.update(
            estado="foco",
            comeca_em=time.time(),
            duracao=self.ciclo["foco_min"] * 60,
            numero=self.ciclo["numero"] + 1,
            tarefa=tarefa or self.ciclo["tarefa"],
        )
        return self.estado_do_ciclo()

    def ir_para_pausa(self) -> dict:
        """
        Fecha o ciclo e comeca a pausa.

        A pausa conta como pausa mesmo que o ciclo nao tenha terminado: quem
        para antes descansou do mesmo jeito, e um programa que so conta a
        pausa "merecida" vira cobranca.
        """
        if self.ciclo["estado"] == "foco":
            self._somar(ciclos=1)
        self._somar(pausas=1)
        self._seguida = 0
        self.ciclo.update(
            estado="pausa", comeca_em=time.time(), duracao=self.ciclo["pausa_min"] * 60
        )
        return self.estado_do_ciclo()

    def parar_ciclo(self) -> dict:
        self.ciclo.update(estado="parado", comeca_em=0.0)
        return self.estado_do_ciclo()

    def estado_do_ciclo(self) -> dict:
        restante = 0
        if self.ciclo["estado"] != "parado" and self.ciclo["comeca_em"]:
            passou = time.time() - self.ciclo["comeca_em"]
            restante = max(0, int(self.ciclo["duracao"] - passou))
        return {
            **self.ciclo,
            "restante": restante,
            "restante_texto": f"{restante // 60:02d}:{restante % 60:02d}",
            "acabou": self.ciclo["estado"] != "parado" and restante == 0,
        }

    # ------------------------------------------------------- lembretes

    def lembretes(self) -> list[dict]:
        hoje = date.today().isoformat()
        itens = self.base.buscar("SELECT * FROM lembretes ORDER BY id")
        agora = datetime.now()

        for l in itens:
            if l["dia"] != hoje:
                # Vira o dia: a contagem recomeca.
                self.base.escrever(
                    "UPDATE lembretes SET feitos_dia = 0, dia = ? WHERE id = ?", (hoje, l["id"])
                )
                l["feitos_dia"], l["dia"] = 0, hoje

            atrasado_min = 0
            proximo = ""
            if l["ligado"] and l["ultima_vez"]:
                try:
                    passou = (agora - datetime.fromisoformat(l["ultima_vez"])).total_seconds() / 60
                    atrasado_min = int(passou - l["cada_min"])
                    quando = datetime.fromisoformat(l["ultima_vez"]) + timedelta(minutes=l["cada_min"])
                    proximo = quando.strftime("%H:%M")
                except ValueError:
                    pass

            l["atrasado_min"] = max(0, atrasado_min)
            l["proximo"] = proximo
            l["meta_texto"] = (
                f"{l['feitos_dia']} de {l['meta_dia']}" if l["meta_dia"] else f"{l['feitos_dia']} hoje"
            )
            l["cumprido"] = bool(l["meta_dia"]) and l["feitos_dia"] >= l["meta_dia"]
        return itens

    def salvar_lembrete(self, dados: dict, id_: int | None = None) -> int:
        titulo = " ".join(str(dados.get("titulo", "")).split())
        if not titulo:
            raise ValueError("o lembrete precisa de um nome")
        cada = max(1, min(int(dados.get("cada_min") or 60), 720))
        meta = max(0, min(int(dados.get("meta_dia") or 0), 50))
        ligado = 1 if dados.get("ligado", True) else 0

        if id_:
            self.base.escrever(
                "UPDATE lembretes SET titulo = ?, cada_min = ?, meta_dia = ?, ligado = ? WHERE id = ?",
                (titulo, cada, meta, ligado, id_),
            )
            return id_
        return self.base.escrever(
            "INSERT INTO lembretes (titulo, cada_min, meta_dia, ligado, dia, criado_em) "
            "VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))",
            (titulo, cada, meta, ligado, date.today().isoformat()),
        )

    def marcar_lembrete(self, id_: int) -> bool:
        hoje = date.today().isoformat()
        linha = self.base.um("SELECT titulo, meta_dia FROM lembretes WHERE id = ?", (id_,))
        if not linha:
            return False

        self.base.escrever(
            "UPDATE lembretes SET feitos_dia = feitos_dia + 1, dia = ?, "
            "ultima_vez = datetime('now','localtime') WHERE id = ?",
            (hoje, id_),
        )
        if "água" in linha["titulo"].lower() or "agua" in linha["titulo"].lower():
            self._somar(copos_agua=1)
        return True

    def apagar_lembrete(self, id_: int) -> bool:
        return self.base.escrever("DELETE FROM lembretes WHERE id = ?", (id_,)) > 0

    def sugerir_lembretes(self) -> int:
        """Cria a lista inicial, para a tela nao comecar em branco."""
        if self.base.contar("lembretes"):
            return 0
        for titulo, cada, meta in LEMBRETES_SUGERIDOS:
            self.salvar_lembrete({"titulo": titulo, "cada_min": cada, "meta_dia": meta})
        return len(LEMBRETES_SUGERIDOS)

    # ------------------------------------------------------- os numeros

    def dia(self, quando: str = "") -> dict:
        alvo = quando or date.today().isoformat()
        linha = self.base.um("SELECT * FROM bem_estar WHERE dia = ?", (alvo,))
        base = {
            "dia": alvo, "minutos_ativos": 0, "ciclos": 0,
            "pausas": 0, "copos_agua": 0, "maior_seguida": 0,
        }
        if linha:
            base.update({k: linha[k] for k in base if k in linha.keys()})

        minutos = int(base["minutos_ativos"])
        base["ativo_texto"] = f"{minutos // 60} h {minutos % 60:02d} min" if minutos else "ainda nada hoje"
        base["seguida_texto"] = (
            f"{int(base['maior_seguida']) // 60} h {int(base['maior_seguida']) % 60:02d} min"
            if base["maior_seguida"] else "—"
        )
        base["sem_pausa_min"] = int(self._seguida)
        base["medindo"] = self.ligado
        base["da_para_medir"] = da_para_medir()
        return base

    def semana(self, ate: str = "") -> dict:
        """Os sete dias que terminam no dia informado."""
        fim = date.fromisoformat(ate) if ate else date.today()
        inicio = fim - timedelta(days=6)
        linhas = self.base.buscar(
            "SELECT * FROM bem_estar WHERE dia >= ? AND dia <= ? ORDER BY dia",
            (inicio.isoformat(), fim.isoformat()),
        )
        por_dia = {l["dia"]: l for l in linhas}

        dias = []
        nomes = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
        for passo in range(7):
            alvo = inicio + timedelta(days=passo)
            chave = alvo.isoformat()
            l = por_dia.get(chave)
            dias.append({
                "dia": chave,
                "rotulo": nomes[alvo.weekday()],
                "minutos_ativos": int(l["minutos_ativos"]) if l else 0,
                "pausas": int(l["pausas"]) if l else 0,
                "ciclos": int(l["ciclos"]) if l else 0,
                "copos_agua": int(l["copos_agua"]) if l else 0,
            })

        com_dado = [d for d in dias if d["minutos_ativos"] or d["ciclos"] or d["pausas"]]
        total_ciclos = sum(d["ciclos"] for d in dias)
        total_pausas = sum(d["pausas"] for d in dias)
        maior = max((int(l["maior_seguida"]) for l in linhas), default=0)

        return {
            "de": inicio.isoformat(),
            "ate": fim.isoformat(),
            "dias": dias,
            "tem_dado": bool(com_dado),
            "dias_com_dado": len(com_dado),
            "ciclos": total_ciclos,
            "pausas": total_pausas,
            "agua_media": round(
                sum(d["copos_agua"] for d in com_dado) / len(com_dado), 1
            ) if com_dado else 0,
            "maior_seguida": maior,
            "maior_seguida_texto": f"{maior // 60} h {maior % 60:02d} min" if maior else "—",
        }

    def alerta(self) -> dict | None:
        """
        A sugestao do momento - so quando ha motivo medido.

        Sem medicao ligada, nao ha sugestao: um conselho baseado em nada e o
        tipo de coisa que faz a pessoa desligar o programa.
        """
        if not self.ligado:
            return None
        seguida = int(self._seguida)
        if seguida < 90:
            return None
        return {
            "titulo": f"Você está há {seguida // 60} h {seguida % 60:02d} min sem parar",
            "detalhe": (
                "Medido pelo tempo desde o último toque no teclado ou no mouse — "
                "sem saber o que foi digitado. Sugiro fechar este ciclo, beber água "
                "e caminhar cinco minutos."
            ),
        }

    def para_tela(self) -> dict:
        return {
            "hoje": self.dia(),
            "ciclo": self.estado_do_ciclo(),
            "lembretes": self.lembretes(),
            "semana": self.semana(),
            "alerta": self.alerta(),
            "como_mede": (
                "Eu pergunto ao Windows há quanto tempo ninguém toca no teclado ou no "
                "mouse. Não sei qual tecla foi, nem qual janela estava aberta, e guardo "
                "só os totais do dia."
            ),
        }
