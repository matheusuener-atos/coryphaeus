"""
Portao da R9 - celular, energia e abrir com o Windows (src/acesso/energia.py).

  - toda resposta em streaming do api.py sai como text/event-stream com
    Cache-Control: no-cache e X-Accel-Buffering: no - sem isso, um proxy no
    caminho (o tunel inclusive) pode segurar a resposta e ela chega de uma
    vez no fim, e nao palavra a palavra;
  - com o acesso de fora ligado, o PAULUS pede ao Windows para nao suspender
    (SetThreadExecutionState, simulado aqui) - da mesma thread que depois
    devolve o pedido; desligado, devolve;
  - "abrir com o Windows" grava e tira a linha da chave Run (numa chave de
    teste, e nao na de verdade), minimizado;
  - o desktop.py abre minimizado com --minimizado.

As quatro telas em 390 px (login, conversa, documento com trecho citado,
Aprovacoes) estao em tests/test_tela.py, que precisa do Playwright.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_r9_celular.py
"""

from __future__ import annotations

import ast
import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-r9-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def test_streaming() -> None:
    print("\ntoda resposta em streaming sai sem buffer")
    arvore = ast.parse((RAIZ / "src" / "api.py").read_text(encoding="utf-8"))
    chamadas = [n for n in ast.walk(arvore) if isinstance(n, ast.Call)
                and getattr(n.func, "id", getattr(n.func, "attr", "")) == "StreamingResponse"]
    ruins = []
    for c in chamadas:
        args = {k.arg: k.value for k in c.keywords}
        tipo = args.get("media_type")
        cab = args.get("headers")
        texto = ast.unparse(cab) if cab is not None else ""
        if not (isinstance(tipo, ast.Constant) and tipo.value == "text/event-stream"
                and "'Cache-Control': 'no-cache'" in texto and "'X-Accel-Buffering': 'no'" in texto):
            ruins.append(c.lineno)
    checar(len(chamadas) >= 9, f"achou as respostas em streaming ({len(chamadas)})")
    checar(not ruins, "todas com text/event-stream, Cache-Control: no-cache e X-Accel-Buffering: no", ruins)

    from fastapi.testclient import TestClient

    import api

    c = TestClient(api.app, headers=api.cabecalho_local())
    id_ = c.post("/api/trabalhos", json={"pedido": "teste"}).json()["id"]
    with c.stream("POST", f"/api/trabalhos/{id_}/perguntar", json={"pergunta": "oi"}) as r:
        cab = r.headers
    checar(cab.get("content-type", "").startswith("text/event-stream") and cab.get("cache-control") == "no-cache"
           and cab.get("x-accel-buffering") == "no", "e de verdade, na resposta da conversa", dict(cab))


def test_energia() -> None:
    print("\no Windows nao suspende com o acesso de fora ligado")
    from acesso.energia import ES_CONTINUOUS, ES_SYSTEM_REQUIRED, Acordado

    chamadas: list[tuple[int, int]] = []
    a = Acordado(chamar=lambda flags: chamadas.append((flags, threading.get_ident())) or 1)
    checar(a.ligar(), "ligar")
    for _ in range(50):
        if a.ligado:
            break
        threading.Event().wait(0.02)
    checar(chamadas and chamadas[0][0] == ES_CONTINUOUS | ES_SYSTEM_REQUIRED, "pede ES_CONTINUOUS | ES_SYSTEM_REQUIRED", chamadas)
    a.desligar()
    checar(len(chamadas) == 2 and chamadas[1][0] == ES_CONTINUOUS, "desligar devolve (so ES_CONTINUOUS)", chamadas)
    checar(chamadas[0][1] == chamadas[1][1] != threading.get_ident(), "da mesma thread, que fica viva enquanto segura")

    import api

    servico = api.estado.acesso_de_fora
    chamadas.clear()
    servico.acordado = Acordado(chamar=lambda flags: chamadas.append((flags, threading.get_ident())) or 1)
    servico.segurar_acordado(True)
    for _ in range(50):
        if servico.acordado.ligado:
            break
        threading.Event().wait(0.02)
    checar(servico.acordado.ligado, "o acesso de fora ligado segura o Windows acordado")
    servico.segurar_acordado(False)
    checar(not servico.acordado.ligado and chamadas[-1][0] == ES_CONTINUOUS, "desligado, solta")
    e = servico.energia()
    checar({"acordado", "situacao", "abrir_com_windows", "pode_abrir_com_windows"} <= set(e), "a tela sabe da energia", e)


def test_abrir_com_windows() -> None:
    print("\nabrir com o Windows")
    if sys.platform != "win32":
        print("  pulado: so no Windows")
        return
    import winreg

    from acesso import energia

    chave = r"Software\PAULUS-teste-r9\Run"
    exe = TMP / "PAULUS.exe"
    exe.write_bytes(b"MZ")
    try:
        checar(not energia.abre_com_windows(chave), "desligado de fabrica")
        checar(energia.abrir_com_windows(True, exe, chave) and energia.abre_com_windows(chave), "ligar grava a linha")
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, chave) as k:
            valor, _ = winreg.QueryValueEx(k, energia.NOME_NA_RUN)
        checar(valor == f'"{exe}" --minimizado', "o PAULUS.exe, minimizado", valor)
        energia.abrir_com_windows(False, chave=chave)
        checar(not energia.abre_com_windows(chave), "desligar tira a linha")
    finally:
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, chave)
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\PAULUS-teste-r9")
        except OSError:
            pass


def test_minimizado() -> None:
    print("\no desktop.py abre minimizado com --minimizado")
    import desktop

    checar(desktop._opcoes_da_janela(["--minimizado"]).get("minimized") is True, "--minimizado")
    checar(not desktop._opcoes_da_janela([]).get("minimized"), "sem ele, abre normal")


def main() -> int:
    print("=" * 55)
    print("  R9 - celular, energia, abrir com o Windows")
    print("=" * 55)
    try:
        test_streaming()
        test_energia()
        test_abrir_com_windows()
        test_minimizado()
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
