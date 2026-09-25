"""
Testes dos avisos do Windows: QUANDO o vigia avisa.

A notificacao em si e do Windows, e aqui ela e trocada por uma lista - o
teste nao pode encher o canto da tela de quem roda. O que importa e a regra:

  - lembrete vencido avisa uma vez, e so avisa de novo depois de outro
    intervalo;
  - lembrete desligado, cumprido ou fora do horario de trabalho nao avisa;
  - o fim do ciclo de foco avisa uma vez por ciclo, a qualquer hora;
  - o texto com aspas e acento chega inteiro ao roteiro do PowerShell.

    python tests/test_avisos.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import avisos  # noqa: E402

_falhas: list[str] = []
_enviados: list[tuple[str, str]] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {detalhe}")
        _falhas.append(descricao)


def _notificar_de_mentira(titulo: str, texto: str, **_) -> bool:
    _enviados.append((titulo, texto))
    return True


class Prefs:
    def __init__(self, **dados) -> None:
        self.dados = {"avisos_windows": True,
                      "disponibilidade": {"dias": [0, 1, 2, 3, 4, 5, 6], "inicio": "08:00", "fim": "18:00"}}
        self.dados.update(dados)


class BemEstarFalso:
    def __init__(self) -> None:
        self.ciclo = {"estado": "parado", "comeca_em": 0, "acabou": False, "pausa_min": 5}
        self.itens = [
            {"id": 1, "titulo": "Beber água", "cada_min": 45, "meta_dia": 8, "meta_texto": "0 de 8",
             "ligado": 1, "cumprido": False, "ultima_vez": None},
            {"id": 2, "titulo": "Alongar", "cada_min": 45, "meta_dia": 3, "meta_texto": "0 de 3",
             "ligado": 0, "cumprido": False, "ultima_vez": None},
            {"id": 3, "titulo": "Olhar para longe", "cada_min": 45, "meta_dia": 2, "meta_texto": "2 de 2",
             "ligado": 1, "cumprido": True, "ultima_vez": None},
        ]
        self.alertar = None

    def estado_do_ciclo(self) -> dict:
        return dict(self.ciclo)

    def lembretes(self) -> list[dict]:
        return [dict(l) for l in self.itens]

    def alerta(self):
        return self.alertar


def test_lembretes() -> None:
    bem = BemEstarFalso()
    vigia = avisos.Vigia(bem, Prefs())
    inicio = datetime(2026, 9, 21, 9, 0)   # segunda, 9h
    vigia.desde = inicio

    _enviados.clear()
    vigia.olhar(inicio + timedelta(minutes=30))
    checar(not _enviados, "antes do intervalo, nada avisa")

    vigia.olhar(inicio + timedelta(minutes=46))
    checar([t for t, _ in _enviados] == ["Beber água"], "venceu o intervalo: avisa só o ligado e não cumprido",
           str(_enviados))

    _enviados.clear()
    vigia.olhar(inicio + timedelta(minutes=50))
    checar(not _enviados, "não repete o aviso na volta seguinte")

    vigia.olhar(inicio + timedelta(minutes=46 + 45))
    checar([t for t, _ in _enviados] == ["Beber água"], "avisa de novo depois de outro intervalo")

    _enviados.clear()
    bem.itens[0]["ultima_vez"] = (inicio + timedelta(minutes=100)).isoformat()
    vigia.olhar(inicio + timedelta(minutes=120))
    checar(not _enviados, "marcar Feito recomeça a contagem")

    _enviados.clear()
    vigia.olhar(datetime(2026, 9, 21, 22, 0))
    checar(not _enviados, "fora do horário de trabalho, lembrete não avisa")


def test_ciclo() -> None:
    bem = BemEstarFalso()
    vigia = avisos.Vigia(bem, Prefs())
    _enviados.clear()
    bem.ciclo = {"estado": "foco", "comeca_em": 1000.0, "acabou": True, "pausa_min": 10}
    vigia.olhar(datetime(2026, 9, 21, 23, 0))
    checar(_enviados and _enviados[0][0] == "Ciclo de foco terminado", "fim do foco avisa, mesmo fora do horário")
    checar("10 min" in _enviados[0][1] if _enviados else False, "o aviso diz a duração da pausa")

    _enviados.clear()
    vigia.olhar(datetime(2026, 9, 21, 23, 1))
    checar(not _enviados, "o mesmo ciclo não avisa duas vezes")

    bem.ciclo = {"estado": "pausa", "comeca_em": 2500.0, "acabou": True, "pausa_min": 10}
    vigia.olhar(datetime(2026, 9, 21, 23, 11))
    checar([t for t, _ in _enviados] == ["Pausa terminada"], "fim da pausa avisa")


def test_alerta() -> None:
    bem = BemEstarFalso()
    bem.itens = []
    bem.alertar = {"titulo": "Você está há 1 h 35 min sem parar", "detalhe": ""}
    vigia = avisos.Vigia(bem, Prefs())
    agora = datetime(2026, 9, 21, 15, 0)
    _enviados.clear()
    vigia.olhar(agora)
    vigia.olhar(agora + timedelta(minutes=20))
    checar(len(_enviados) == 1, "o alerta de pausa avisa no máximo uma vez por hora", str(_enviados))
    vigia.olhar(agora + timedelta(minutes=61))
    checar(len(_enviados) == 2, "depois de uma hora, avisa de novo")


class AgendaFalsa:
    def __init__(self, itens) -> None:
        self.itens = itens

    def listar(self, de: str, ate: str) -> list[dict]:
        return [dict(c) for c in self.itens if de <= c["data"] <= ate]


def test_tipos() -> None:
    bem = BemEstarFalso()
    bem.ciclo = {"estado": "foco", "comeca_em": 1.0, "acabou": True, "pausa_min": 5}
    vigia = avisos.Vigia(bem, Prefs(avisos_tipos={"bem_estar": False}))
    _enviados.clear()
    vigia.olhar(datetime(2026, 9, 21, 10, 0))
    checar(not _enviados, "bem-estar desligado: nem o fim do ciclo avisa")


def test_agenda() -> None:
    bem = BemEstarFalso()
    bem.itens = []
    agenda = AgendaFalsa([
        {"id": 1, "titulo": "Audiência", "data": "2026-09-21", "hora": "14:00", "avisar_min": 0, "onde_rotulo": "Fórum"},
        {"id": 2, "titulo": "Reunião", "data": "2026-09-21", "hora": "15:00", "avisar_min": 60, "onde_rotulo": ""},
    ])
    vigia = avisos.Vigia(bem, Prefs(), agenda=agenda)
    _enviados.clear()
    vigia.olhar(datetime(2026, 9, 21, 13, 40))
    checar(not _enviados, "20 min antes, sem aviso escolhido: ainda não avisa")
    vigia.olhar(datetime(2026, 9, 21, 13, 46))
    checar([t for t, _ in _enviados] == ["Audiência"], "15 min antes avisa", str(_enviados))
    checar("em 14 min" in _enviados[0][1] and "Fórum" in _enviados[0][1], "diz a hora que falta e onde", _enviados[0][1] if _enviados else "")
    _enviados.clear()
    vigia.olhar(datetime(2026, 9, 21, 13, 50))
    checar(not _enviados, "o mesmo compromisso não avisa duas vezes")
    vigia.olhar(datetime(2026, 9, 21, 14, 0))
    checar([t for t, _ in _enviados] == ["Reunião"], "com aviso de 60 min escolhido, avisa uma hora antes", str(_enviados))
    _enviados.clear()
    agenda.itens[0]["hora"] = "14:05"
    vigia.olhar(datetime(2026, 9, 21, 13, 52))
    checar([t for t, _ in _enviados] == ["Audiência"], "remarcou: avisa de novo")

    vigia = avisos.Vigia(bem, Prefs(avisos_tipos={"agenda": False}), agenda=agenda)
    _enviados.clear()
    vigia.olhar(datetime(2026, 9, 21, 13, 52))
    checar(not _enviados, "agenda desligada não avisa")


def test_avisar() -> None:
    import os

    antes = os.environ.pop("PAULUS_SEM_AVISOS", None)
    frente = avisos.janela_na_frente
    try:
        avisos.configurar(Prefs())
        avisos.janela_na_frente = lambda: True
        _enviados.clear()
        avisos.avisar("resposta", "Resposta pronta", "x")
        checar(not _enviados, "janela na frente: resposta não vira aviso do Windows")
        avisos.avisar("agenda", "Audiência", "x")
        checar(len(_enviados) == 1, "compromisso avisa mesmo com a janela na frente")
        avisos.janela_na_frente = lambda: False
        _enviados.clear()
        avisos.avisar("resposta", "Resposta pronta", "x")
        checar(len(_enviados) == 1, "janela atrás: resposta avisa")
        avisos.configurar(Prefs(avisos_tipos={"resposta": False}))
        _enviados.clear()
        avisos.avisar("resposta", "Resposta pronta", "x")
        checar(not _enviados, "tipo desligado não avisa")
        avisos.configurar(Prefs(avisos_windows=False))
        avisos.avisar("aprovacao", "Aprovação pendente", "x")
        checar(not _enviados, "geral desligado cala todos os tipos")
        os.environ["PAULUS_SEM_AVISOS"] = "1"
        avisos.configurar(Prefs())
        avisos.avisar("resposta", "Resposta pronta", "x")
        checar(not _enviados, "servidor de teste (PAULUS_SEM_AVISOS) não avisa")
    finally:
        avisos.janela_na_frente = frente
        avisos.configurar(None)
        os.environ.pop("PAULUS_SEM_AVISOS", None)
        if antes is not None:
            os.environ["PAULUS_SEM_AVISOS"] = antes


def test_fila_avisa() -> None:
    import tempfile

    import aprovacoes

    with tempfile.TemporaryDirectory() as pasta:
        fila = aprovacoes.Fila(Path(pasta) / "fila.json")
        chegou = []
        fila.ao_pedir = lambda p: chegou.append(p.titulo)
        fila.pedir("Assinar contrato", "assinatura")
        checar(chegou == ["Assinar contrato"], "pedido novo na fila chama o aviso")
        fila.ao_pedir = lambda p: 1 / 0
        p = fila.pedir("Outro", "assinatura")
        checar(fila.obter(p.id) is not None, "aviso que quebra não desfaz o pedido")


def test_roteiro() -> None:
    r = avisos._roteiro("Revisar o “contrato” d'Ávila", "a < b & c")
    checar("d''Ávila" in r, "aspa simples dobrada dentro do roteiro do PowerShell")
    checar("a &lt; b &amp; c" in r, "o texto vai escapado para o XML do aviso")
    checar(f"CreateToastNotifier('{avisos.APP_ID}')" in r, "o aviso sai com o identificador do PAULUS")


def main() -> int:
    original = avisos.notificar
    avisos.notificar = _notificar_de_mentira
    try:
        test_lembretes()
        test_ciclo()
        test_alerta()
        test_tipos()
        test_agenda()
        test_avisar()
        test_fila_avisa()
        test_roteiro()
    finally:
        avisos.notificar = original

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
