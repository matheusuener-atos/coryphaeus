"""
"Perguntar ao PAULUS" no botao direito do Windows Explorer.

O instalador oferece ligar isso (a caixa "Perguntar ao PAULUS no botao
direito do Explorer", tools/instalador/Instalador.cs); aqui o programa liga e
desliga depois, em Configuracoes › Aparencia e avisos - com as MESMAS chaves,
para o instalador e o programa concordarem sobre o que esta ligado.

O clique no arquivo abre o PAULUS.exe com `--perguntar "<arquivo>"`: o
desktop.py entrega o caminho para a janela aberta (/api/externo/perguntar) ou
abre a janela com `#perguntar=...`, e a conversa comeca com o arquivo anexado
(perguntarSobreArquivo, js/03-assistente.js). O arquivo nao sai do computador.

So HKEY_CURRENT_USER: nada de administrador, e so para quem instalou. No
Windows 11 o item aparece em "Mostrar mais opcoes".
"""

from __future__ import annotations

import sys
from pathlib import Path

# Os tipos que o PAULUS le (os mesmos do instalador, Instalador.cs TIPOS).
TIPOS = (".pdf", ".docx", ".txt", ".md", ".xlsx")
BASE = r"Software\Classes\SystemFileAssociations"
VERBO = "PAULUS.Perguntar"
ROTULO = "Perguntar ao Paulus"


def _chave(tipo: str, base: str) -> str:
    return base + "\\" + tipo + r"\shell" + "\\" + VERBO


def _avisar_o_explorer() -> None:
    """O Explorer rele as associacoes (SHCNE_ASSOCCHANGED), sem reiniciar."""
    try:
        import ctypes

        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    except Exception:  # noqa: BLE001 - o menu vale na proxima vez que o Explorer olhar
        pass


def _exe_do_comando(comando: str) -> str:
    comando = (comando or "").strip()
    if comando.startswith('"'):
        fim = comando.find('"', 1)
        return comando[1:fim] if fim > 1 else ""
    return comando.split(" ", 1)[0]


def estado(exe: Path | None, base: str = BASE) -> dict:
    """
    {"disponivel", "ligado", "de_outro"}: disponivel so no Windows e no PAULUS
    instalado (com o PAULUS.exe); `de_outro` quando o menu aponta para outra
    instalacao.
    """
    if sys.platform != "win32":
        return {"disponivel": False, "ligado": False, "de_outro": False, "motivo": "só no Windows"}
    import winreg

    comando = ""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _chave(".pdf", base) + r"\command") as k:
            comando, _ = winreg.QueryValueEx(k, "")
    except OSError:
        pass
    alvo = _exe_do_comando(comando)
    meu = bool(exe) and bool(alvo) and Path(alvo).resolve() == Path(exe).resolve()
    return {"disponivel": bool(exe), "ligado": meu, "de_outro": bool(alvo) and not meu,
            "motivo": "" if exe else "disponível no Paulus instalado (o PAULUS.exe não foi encontrado)"}


def ligar(exe: Path, base: str = BASE) -> None:
    import winreg

    for tipo in TIPOS:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _chave(tipo, base)) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, ROTULO)
            winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, f'"{exe}",0')
            with winreg.CreateKey(k, "command") as c:
                winreg.SetValueEx(c, "", 0, winreg.REG_SZ, f'"{exe}" --perguntar "%1"')
    _avisar_o_explorer()


def desligar(base: str = BASE) -> None:
    import winreg

    for tipo in TIPOS:
        for sub in (_chave(tipo, base) + r"\command", _chave(tipo, base)):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
            except OSError:
                pass
    _avisar_o_explorer()
