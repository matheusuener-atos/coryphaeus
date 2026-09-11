"""
Testes do ritmo medido da máquina.

Este módulo alimenta a janelinha que diz "leituras deste tamanho levaram ~72 s
aqui". É um número que aparece na tela enquanto a pessoa espera, e a regra da
casa vale inteira: número na tela é número medido.

Então o que os testes cobrem é principalmente o que ele NÃO pode fazer:

  - sem histórico, dizer que não sabe — e não chutar
  - não misturar modelos: a mesma máquina lê em velocidades diferentes com Q4
    e com Q8, e a média dos dois não descreve nenhum
  - não deixar uma medida absurda envenenar a mediana
  - não crescer para sempre no disco

    python tests/test_ritmo.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import ritmo  # noqa: E402

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {detalhe}")
        _falhas.append(descricao)


def test_sem_historico_nao_chuta(tmp: Path) -> None:
    print("\nsem histórico, não chuta")
    r = ritmo.Ritmo(tmp / "vazio.json")

    previsao = r.previsao_de_leitura("llama3.2:3b", 21000)
    checar(previsao["sabe"] is False, "diz que não sabe")
    checar(previsao["segundos"] == 0, "e não devolve um número inventado")
    checar(r.chars_por_segundo("llama3.2:3b") == 0, "nem uma taxa")
    checar(r.para_tela("llama3.2:3b")["medicoes"] == 0, "e conta zero medições")


def test_prevê_pelo_que_mediu(tmp: Path) -> None:
    print("\nprevê pelo que mediu")
    r = ritmo.Ritmo(tmp / "medido.json")
    for segundos in (68.0, 74.0, 71.0, 90.0):
        r.anotar(modelo="llama3.2:3b", caracteres=21000, segundos_lendo=segundos,
                 palavras=96, segundos_escrevendo=34.0)

    previsao = r.previsao_de_leitura("llama3.2:3b", 21000)
    checar(previsao["sabe"] is True, "depois de medir, sabe")
    checar(68 <= previsao["segundos"] <= 80,
           f"e o número fica entre o que aconteceu ({previsao['segundos']} s)")
    checar(previsao["medicoes"] == 4, "dizendo de quantas medições saiu")

    # A previsão acompanha o tamanho: o dobro de texto, perto do dobro de tempo.
    dobro = r.previsao_de_leitura("llama3.2:3b", 42000)["segundos"]
    checar(1.8 <= dobro / previsao["segundos"] <= 2.2,
           f"o dobro de texto pede perto do dobro do tempo ({dobro} s)")


def test_cada_modelo_tem_seu_ritmo(tmp: Path) -> None:
    """
    Misturar modelos daria uma média que não descreve nenhum.

    A mesma máquina lê em velocidades bem diferentes com Q4 e Q8 — medido: 4,6 s
    contra 15,4 s numa mesma pergunta. Uma média dos dois seria falsa para os
    dois, e é justamente quando a pessoa troca de modelo que ela olha o número.
    """
    print("\ncada modelo tem seu ritmo")
    r = ritmo.Ritmo(tmp / "dois.json")
    for _ in range(3):
        r.anotar(modelo="rapido:3b", caracteres=21000, segundos_lendo=70.0)
        r.anotar(modelo="lento:3b", caracteres=21000, segundos_lendo=210.0)

    rapido = r.previsao_de_leitura("rapido:3b", 21000)["segundos"]
    lento = r.previsao_de_leitura("lento:3b", 21000)["segundos"]
    checar(rapido < lento / 2, f"o lento prevê muito mais que o rápido ({rapido} s vs {lento} s)")
    checar(r.previsao_de_leitura("nunca-rodou:3b", 21000)["sabe"] is False,
           "e um modelo que nunca rodou continua sem previsão")


def test_ruido_nao_entra(tmp: Path) -> None:
    """Medida curta demais é o modelo carregando, não a máquina lendo."""
    print("\nruído não vira medida")
    r = ritmo.Ritmo(tmp / "ruido.json")
    r.anotar(modelo="m:3b", caracteres=100, segundos_lendo=0.1)
    r.anotar(modelo="m:3b", caracteres=50, segundos_lendo=8.0)
    checar(r.leituras == [], "leitura pequena demais é descartada")

    r.anotar(modelo="m:3b", caracteres=21000, segundos_lendo=0.05)
    checar(r.leituras == [], "e tempo curto demais também")

    r.anotar(modelo="m:3b", caracteres=21000, segundos_lendo=70.0)
    checar(len(r.leituras) == 1, "mas a medida de verdade entra")


def test_nao_cresce_sem_fim(tmp: Path) -> None:
    print("\no arquivo não cresce sem fim")
    caminho = tmp / "muitas.json"
    r = ritmo.Ritmo(caminho)
    for i in range(80):
        r.anotar(modelo="m:3b", caracteres=21000, segundos_lendo=60.0 + i)

    checar(len(r.leituras) == ritmo.LEMBRAR,
           f"guarda só as últimas {ritmo.LEMBRAR} ({len(r.leituras)})")
    gravado = json.loads(caminho.read_text(encoding="utf-8"))
    checar(len(gravado["leituras"]) == ritmo.LEMBRAR, "e o disco também")

    # As últimas, e não as primeiras: a máquina de hoje é que importa.
    checar(r.leituras[-1]["lendo"] == 139.0,
           f"a mais recente é a última anotada ({r.leituras[-1]['lendo']})")


def test_sobrevive_ao_arquivo_estragado(tmp: Path) -> None:
    print("\narquivo estragado não derruba o programa")
    ruim = tmp / "ruim.json"
    ruim.write_text("isto não é json", encoding="utf-8")
    r = ritmo.Ritmo(ruim)
    checar(r.leituras == [], "começa vazio em vez de quebrar")

    r.anotar(modelo="m:3b", caracteres=21000, segundos_lendo=70.0)
    checar(len(r.leituras) == 1, "e volta a gravar por cima")

    de_novo = ritmo.Ritmo(ruim)
    checar(len(de_novo.leituras) == 1, "o que gravou é lido de volta")


def main() -> int:
    print("=" * 55)
    print("PAULUS - o ritmo medido da máquina")
    print("=" * 55)

    with tempfile.TemporaryDirectory() as bruto:
        tmp = Path(bruto)
        test_sem_historico_nao_chuta(tmp)
        test_prevê_pelo_que_mediu(tmp)
        test_cada_modelo_tem_seu_ritmo(tmp)
        test_ruido_nao_entra(tmp)
        test_nao_cresce_sem_fim(tmp)
        test_sobrevive_ao_arquivo_estragado(tmp)

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
