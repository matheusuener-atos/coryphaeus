"""
Testes do Organizar: copiar em vez de mover, e reorganizar a propria pasta.

  - copiar deixa o original; desfazer tira so a copia;
  - copia sem original (o original sumiu) nao sai no desfazer;
  - arquivo que ja esta onde o padrao pede fica onde esta (sem "nome (2)");
  - mover dentro do destino tira as pastas que ficaram vazias, e so elas.

    python tests/test_organizar_copiar.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from classify import Classificacao  # noqa: E402
from organize import aplicar_plano, desfazer, montar_plano  # noqa: E402

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {detalhe}")
        _falhas.append(descricao)


def _doc(caminho: Path, cliente: str, tipo: str = "contrato") -> Classificacao:
    return Classificacao(arquivo=str(caminho), nome=caminho.name, sha1=caminho.name, tipo=tipo, cliente=cliente)


def test_copiar(tmp: Path) -> None:
    origem = tmp / "entrada"
    origem.mkdir()
    a = origem / "a.pdf"
    a.write_bytes(b"conteudo de a")
    destino = tmp / "acervo"

    plano = montar_plano([_doc(a, "Fulano")], destino, "{cliente}", operacao="copiar")
    checar(plano.operacao == "copiar", "o plano guarda a operação")
    r = aplicar_plano(plano, tmp / "diarios")
    copia = destino / "Fulano" / "a.pdf"
    checar(a.exists() and copia.exists(), "copiar deixa o original e cria a cópia")

    d = desfazer(r.diario)
    checar(d.movidos == 1 and a.exists() and not copia.exists(), "desfazer a cópia tira só a cópia", str(d))

    # A copia sem o original vira o unico exemplar: nao pode sair.
    r = aplicar_plano(montar_plano([_doc(a, "Fulano")], destino, "{cliente}", operacao="copiar"), tmp / "diarios")
    a.unlink()
    d = desfazer(r.diario)
    checar(copia.exists() and d.falhas, "sem o original, a cópia fica no desfazer")


def test_ja_no_lugar(tmp: Path) -> None:
    acervo = tmp / "acervo2"
    (acervo / "Beltrano").mkdir(parents=True)
    certo = acervo / "Beltrano" / "b.pdf"
    certo.write_bytes(b"b")
    plano = montar_plano([_doc(certo, "Beltrano")], acervo, "{cliente}")
    checar(not plano.movimentos, "arquivo já no lugar não entra no plano")
    checar(any(i["motivo"] == "já está no lugar" for i in plano.ignorados), "e o plano diz por quê")


def test_pastas_vazias(tmp: Path) -> None:
    acervo = tmp / "acervo3"
    velho = acervo / "Compra e Venda" / "Ciclano"
    velho.mkdir(parents=True)
    c = velho / "c.pdf"
    c.write_bytes(b"c")
    vizinha = acervo / "Outra"
    vizinha.mkdir()
    (vizinha / "fica.pdf").write_bytes(b"x")
    fora = tmp / "fora"
    fora.mkdir()
    f = fora / "f.pdf"
    f.write_bytes(b"f")

    plano = montar_plano([_doc(c, "Ciclano"), _doc(f, "Ciclano")], acervo, "{cliente}/{tipo_rotulo}")
    aplicar_plano(plano, tmp / "diarios")
    checar(not (acervo / "Compra e Venda").exists(), "as pastas antigas que ficaram vazias saem")
    checar((vizinha / "fica.pdf").exists(), "pasta com arquivo não é tocada")
    checar(fora.exists(), "a pasta de origem de fora do destino fica, mesmo vazia")


def main() -> int:
    with tempfile.TemporaryDirectory() as bruto:
        tmp = Path(bruto)
        test_copiar(tmp)
        test_ja_no_lugar(tmp)
        test_pastas_vazias(tmp)

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
