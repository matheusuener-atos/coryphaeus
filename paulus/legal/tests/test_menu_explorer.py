"""
"Perguntar ao PAULUS" no botao direito do Explorer (src/menu_explorer.py).

Num ramo proprio do registro (HKCU\\Software\\PAULUS-teste-menu), para nao
mexer no menu de verdade:

  - ligar grava os cinco tipos com o comando `"<exe>" --perguntar "%1"`, o
    rotulo e o icone - as mesmas chaves do instalador;
  - o estado diz ligado so quando o menu aponta para ESTE PAULUS.exe; o de
    outra instalacao aparece como `de_outro`;
  - desligar tira tudo;
  - pela API: sem o PAULUS.exe (codigo-fonte), ligar recusa com a frase;
  - de fora, as rotas nao existem para ninguem (so na janela do servidor).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_menu_explorer.py
"""

from __future__ import annotations

import functools
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-menu-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []
BASE_TESTE = r"Software\PAULUS-teste-menu\Classes\SystemFileAssociations"


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def _ler(tipo: str, sub: str = "") -> str:
    import winreg

    import menu_explorer

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, menu_explorer._chave(tipo, BASE_TESTE) + sub) as k:
            return winreg.QueryValueEx(k, "")[0]
    except OSError:
        return ""


def _limpar() -> None:
    import winreg

    def apagar(caminho: str) -> None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, caminho) as k:
                filhos = []
                i = 0
                while True:
                    try:
                        filhos.append(winreg.EnumKey(k, i))
                        i += 1
                    except OSError:
                        break
            for f in filhos:
                apagar(caminho + "\\" + f)
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, caminho)
        except OSError:
            pass

    apagar(r"Software\PAULUS-teste-menu")


def test_registro() -> None:
    print("\no menu no registro")
    import menu_explorer

    exe = TMP / "PAULUS.exe"
    exe.write_bytes(b"MZ")
    outro = TMP / "outro" / "PAULUS.exe"
    outro.parent.mkdir()
    outro.write_bytes(b"MZ")
    e = menu_explorer.estado(exe, BASE_TESTE)
    checar(e["disponivel"] and not e["ligado"] and not e["de_outro"], "de fabrica: desligado", e)
    menu_explorer.ligar(exe, BASE_TESTE)
    comandos = {t: _ler(t, r"\command") for t in menu_explorer.TIPOS}
    checar(all(c == f'"{exe}" --perguntar "%1"' for c in comandos.values()), "ligar: os cinco tipos com o comando do desktop.py", comandos)
    checar(_ler(".pdf") == "Perguntar ao PAULUS", "o rotulo do menu", _ler(".pdf"))
    checar(menu_explorer.estado(exe, BASE_TESTE)["ligado"], "o estado diz ligado")
    o = menu_explorer.estado(outro, BASE_TESTE)
    checar(not o["ligado"] and o["de_outro"], "outra instalacao ve que o menu e de outro PAULUS", o)
    menu_explorer.desligar(BASE_TESTE)
    checar(not any(_ler(t) for t in menu_explorer.TIPOS), "desligar tira todos")
    checar(not menu_explorer.estado(exe, BASE_TESTE)["ligado"], "e o estado volta a desligado")
    checar(not menu_explorer.estado(None, BASE_TESTE)["disponivel"], "sem PAULUS.exe (codigo-fonte): indisponivel")


def test_api() -> None:
    print("\npela API")
    from fastapi.testclient import TestClient

    import api
    import menu_explorer
    from acesso import energia

    antes = (menu_explorer.estado, menu_explorer.ligar, menu_explorer.desligar, energia.exe_do_programa)
    menu_explorer.estado = functools.partial(antes[0], base=BASE_TESTE)
    menu_explorer.ligar = functools.partial(antes[1], base=BASE_TESTE)
    menu_explorer.desligar = functools.partial(antes[2], base=BASE_TESTE)
    local = TestClient(api.app, headers=api.cabecalho_local())
    try:
        energia.exe_do_programa = lambda: None
        r = local.post("/api/explorer", json={"ligado": True})
        checar(r.status_code == 400 and "instalado" in r.json().get("detail", ""), "sem o PAULUS.exe: recusa com a frase", r.text[:160])
        exe = TMP / "PAULUS.exe"
        energia.exe_do_programa = lambda: exe
        r = local.post("/api/explorer", json={"ligado": True})
        checar(r.status_code == 200 and r.json()["ligado"] and _ler(".docx", r"\command").startswith(f'"{exe}"'),
               "ligar pela tela grava o menu", r.text[:160])
        checar(local.get("/api/explorer").json()["ligado"], "e a tela le ligado")
        r = local.post("/api/explorer", json={"ligado": False})
        checar(r.status_code == 200 and not r.json()["ligado"] and not _ler(".pdf"), "desligar pela tela tira", r.text[:160])
        import segredos

        if segredos.disponivel():
            api.estado.prefs.dados["acesso_remoto"]["ligado"] = True
            try:
                fora = TestClient(api.app, base_url="https://x.paulus.ia.br")
                checar(fora.post("/api/explorer", json={"ligado": True}).status_code in (401, 403),
                       "de fora: nao mexe no registro do servidor")
            finally:
                api.estado.prefs.dados["acesso_remoto"]["ligado"] = False
    finally:
        menu_explorer.estado, menu_explorer.ligar, menu_explorer.desligar, energia.exe_do_programa = antes


def main() -> int:
    if sys.platform != "win32":
        print("pulado: o menu do Explorer so existe no Windows")
        return 0
    try:
        test_registro()
        test_api()
    finally:
        _limpar()
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print("    - " + f)
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
