"""
Testes do "Perguntar ao PAULUS" (botao direito no Explorer) e da janela unica.

  - /api/externo/perguntar entrega o arquivo a janela aberta; arquivo que
    nao existe ou que o programa nao le e recusado;
  - /api/externo/mostrar so traz a janela para frente;
  - o desktop.py le o `--perguntar <arquivo>` e so conversa com um PAULUS
    aberto se a porta responder como PAULUS (o instancia.json pode ter
    sobrado de uma queda).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_externo.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def test_rotas() -> None:
    print("\nas rotas do pedido externo")
    from fastapi.testclient import TestClient

    import api

    c = TestClient(api.app)
    recebidos = []
    antes = api.estado.ao_pedido_externo
    api.estado.ao_pedido_externo = lambda tipo, caminho: recebidos.append((tipo, caminho))
    pasta = Path(tempfile.mkdtemp(prefix="paulus_externo_"))
    try:
        txt = pasta / "contrato.txt"
        txt.write_text("CLÁUSULA 1. Teste.", encoding="utf-8")
        exe = pasta / "programa.exe"
        exe.write_bytes(b"MZ")
        r = c.post("/api/externo/perguntar", json={"caminho": str(txt)})
        checar(r.status_code == 200 and recebidos == [("perguntar", str(txt.resolve()))],
               "o arquivo chega a janela aberta", (r.status_code, recebidos))
        checar(c.post("/api/externo/perguntar", json={"caminho": str(pasta / "sumiu.pdf")}).status_code == 404,
               "arquivo que nao existe e recusado")
        checar(c.post("/api/externo/perguntar", json={"caminho": str(exe)}).status_code == 400,
               "arquivo que o programa nao le e recusado")
        recebidos.clear()
        checar(c.post("/api/externo/mostrar").status_code == 200 and recebidos == [("mostrar", "")],
               "abrir de novo so traz a janela para frente", recebidos)
        api.estado.ao_pedido_externo = None
        checar(c.post("/api/externo/perguntar", json={"caminho": str(txt)}).json() == {"entregue": False},
               "sem janela (no navegador), diz que nao entregou")
    finally:
        api.estado.ao_pedido_externo = antes
        for f in pasta.iterdir():
            f.unlink()
        pasta.rmdir()


def test_desktop() -> None:
    print("\no desktop.py")
    import desktop

    arquivo = str(Path(tempfile.gettempdir()) / "x.pdf")
    checar(desktop._arquivo_pedido(["--perguntar", arquivo]) == str(Path(arquivo).resolve()), "le o --perguntar")
    checar(desktop._arquivo_pedido([]) == "" and desktop._arquivo_pedido(["--perguntar"]) == "", "sem arquivo, nada")
    pasta = tempfile.mkdtemp(prefix="paulus_instancia_")
    antes = os.environ.get("PAULUS_DADOS")
    os.environ["PAULUS_DADOS"] = pasta
    try:
        checar(desktop._porta_da_instancia_aberta() == 0, "sem instancia.json, nenhum PAULUS aberto")
        Path(pasta, "instancia.json").write_text(json.dumps({"porta": 1, "pid": 1}), encoding="utf-8")
        checar(desktop._porta_da_instancia_aberta() == 0, "instancia.json que sobrou de uma queda nao engana")
    finally:
        if antes is None:
            os.environ.pop("PAULUS_DADOS", None)
        else:
            os.environ["PAULUS_DADOS"] = antes
        Path(pasta, "instancia.json").unlink(missing_ok=True)
        os.rmdir(pasta)


def main() -> int:
    print("=" * 55)
    print("  perguntar ao PAULUS pelo Explorer")
    print("=" * 55)
    test_rotas()
    test_desktop()
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
