"""
Horas por servico e a cobranca delas (docs/PLANO-PRODUTO.md, P4).

Cada pessoa registra o tempo que trabalhou num servico: a mao (data, duracao,
o que fez) ou pelo cronometro (um por pessoa; comecar num servico para o que
estiver correndo em outro). As horas ainda nao cobradas, vezes o valor da
hora, viram um recebimento de honorarios no Financeiro, do cliente do
servico - e passam a "cobradas", ligadas a esse lancamento.

Quem: a conta de quem registrou (0 = a janela do servidor) e o nome, como no
resto do PAULUS de equipe (src/equipe.py).
"""

from __future__ import annotations

import re
import time
from datetime import date


class ErroHoras(ValueError):
    """O que impede; a frase vai para a tela."""


def ler_duracao(texto: str) -> int:
    """'1:30', '1h30', '90min', '1,5' (horas) -> minutos."""
    t = str(texto or "").strip().lower().replace(" ", "")
    m = re.fullmatch(r"(\d{1,3}):(\d{2})", t) or re.fullmatch(r"(\d{1,3})h(\d{1,2})?(?:min)?", t)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2) or 0)
    m = re.fullmatch(r"(\d{1,4})min", t)
    if m:
        return int(m.group(1))
    m = re.fullmatch(r"(\d{1,3})(?:[.,](\d{1,2}))?h?", t)
    if m:
        return round(float(m.group(1) + "." + (m.group(2) or "0")) * 60)
    raise ErroHoras("escreva a duração como 1:30, 1h30, 90min ou 1,5")


def texto_da_duracao(minutos: int) -> str:
    h, m = divmod(int(minutos or 0), 60)
    return f"{h}h{m:02d}" if h else f"{m}min"


class Horas:
    def __init__(self, base, relogio=time.time) -> None:
        self.base = base
        self.relogio = relogio

    def _agora(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(self.relogio()))

    def registrar(self, servico_id: int, *, minutos: int, dia: str = "", descricao: str = "", quem: str = "",
                  conta: int = 0) -> int:
        if minutos <= 0 or minutos > 24 * 60:
            raise ErroHoras("a duração precisa ficar entre 1 minuto e 24 horas")
        dia = dia or date.today().isoformat()
        try:
            date.fromisoformat(dia)
        except ValueError as exc:
            raise ErroHoras("data inválida") from exc
        return self.base.escrever(
            "INSERT INTO horas (servico_id, dia, minutos, descricao, quem, conta, criado_em) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (servico_id, dia, int(minutos), str(descricao or "").strip()[:500], quem, int(conta or 0), self._agora()))

    # ---------------------------------------------------------- cronometro

    def cronometro(self, conta: int) -> dict | None:
        return self.base.um("SELECT * FROM cronometros WHERE conta = ?", (int(conta or 0),))

    def comecar(self, servico_id: int, *, quem: str, conta: int, descricao: str = "") -> dict:
        """Comeca o cronometro desta pessoa; se corria em outro servico, fecha aquele antes."""
        atual = self.cronometro(conta)
        if atual:
            self.parar(conta)
        self.base.escrever("INSERT INTO cronometros (conta, servico_id, inicio, quem, descricao) VALUES (?, ?, ?, ?, ?)",
                           (int(conta or 0), servico_id, self.relogio(), quem, str(descricao or "")[:500]))
        return self.cronometro(conta)

    def parar(self, conta: int, descricao: str = "") -> int | None:
        """Para o cronometro e registra o tempo (arredondado para cima, minimo 1 min). Devolve o id."""
        c = self.cronometro(conta)
        if not c:
            return None
        self.base.escrever("DELETE FROM cronometros WHERE conta = ?", (int(conta or 0),))
        minutos = max(1, int((self.relogio() - float(c["inicio"]) + 59) // 60))
        minutos = min(minutos, 24 * 60)
        dia = time.strftime("%Y-%m-%d", time.localtime(float(c["inicio"])))
        return self.registrar(int(c["servico_id"]), minutos=minutos, dia=dia, descricao=descricao or c.get("descricao") or "",
                              quem=c.get("quem") or "", conta=int(c["conta"]))

    # ---------------------------------------------------------- leitura

    def do_servico(self, servico_id: int) -> dict:
        linhas = self.base.buscar("SELECT * FROM horas WHERE servico_id = ? ORDER BY dia DESC, id DESC", (servico_id,))
        abertas = sum(l["minutos"] for l in linhas if not l.get("lancamento_id"))
        return {"registros": linhas, "total_min": sum(l["minutos"] for l in linhas), "a_cobrar_min": abertas,
                "por_pessoa": self._por_pessoa(linhas)}

    @staticmethod
    def _por_pessoa(linhas) -> list[dict]:
        por: dict[str, int] = {}
        for l in linhas:
            por[l.get("quem") or "—"] = por.get(l.get("quem") or "—", 0) + int(l["minutos"])
        return [{"quem": k, "minutos": v} for k, v in sorted(por.items(), key=lambda x: -x[1])]

    def apagar(self, id_: int, conta: int | None = None) -> bool:
        """Apaga um registro ainda nao cobrado (de fora, so o da propria pessoa)."""
        l = self.base.um("SELECT * FROM horas WHERE id = ?", (id_,))
        if not l or l.get("lancamento_id"):
            return False
        if conta is not None and int(l.get("conta") or 0) != int(conta):
            return False
        self.base.escrever("DELETE FROM horas WHERE id = ?", (id_,))
        return True

    def marcar_cobradas(self, servico_id: int, lancamento_id: int) -> int:
        return self.base.escrever("UPDATE horas SET lancamento_id = ? WHERE servico_id = ? AND lancamento_id IS NULL",
                                  (lancamento_id, servico_id))
