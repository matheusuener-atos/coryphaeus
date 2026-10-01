"""
Os caminhos do Windows até o Word com o PAVLVS (W1, depois da 0.9.23):

  - o atalho "Word com PAVLVS" na área de trabalho (e, se a pessoa quiser,
    no menu Iniciar): abre um documento novo já com o PAVLVS. Chama o
    PAULUS.exe com `--word`; o PAULUS fechado abre minimizado, porque o
    painel do Word precisa dele no ar;
  - "Abrir no Word com o PAVLVS" no botão direito de todo arquivo .docx:
    `--word-abrir "<arquivo>"` põe a referência ao PAVLVS no arquivo (o texto
    não muda) e o abre; dali em diante, o duplo clique já abre com ele.

Por que: no Word 2021 a aba PAVLVS só aparece no documento que traz o
suplemento (medido em 01/10/2026; ver src/word_instalar.py).

Fixar na barra de tarefas ou no Iniciar o Windows 11 não deixa programa
nenhum fazer: só a própria pessoa. O PAULUS cria os atalhos e diz isso.

Tudo em HKEY_CURRENT_USER e nas pastas da pessoa: nada de administrador.
No Windows 11 o item do botão direito aparece em "Mostrar mais opções", como
o "Perguntar ao PAULUS" (src/menu_explorer.py).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

NOME_DO_ATALHO = "Word com PAVLVS"
BASE = r"Software\Classes\SystemFileAssociations"
VERBO = "PAULUS.AbrirComPavlvs"
ROTULO = "Abrir no Word com o PAVLVS"
TIPOS = (".docx",)   # .doc é binário: não leva a referência


def _sem_janela() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def pasta_do_windows(qual: str) -> Path | None:
    """'Desktop' ou 'Programs' (o menu Iniciar), já com a pasta do OneDrive se for o caso."""
    if sys.platform != "win32":
        return None
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", f"[Environment]::GetFolderPath('{qual}')"],
                           capture_output=True, text=True, timeout=30, creationflags=_sem_janela())
    except (OSError, subprocess.SubprocessError):
        return None
    caminho = (r.stdout or "").strip()
    return Path(caminho) if caminho else None


def icone_do_word() -> str:
    """O ícone do próprio Word (o atalho tem cara de Word); sem achar, o do PAULUS."""
    if sys.platform != "win32":
        return ""
    import winreg

    caminho = r"Software\Microsoft\Windows\CurrentVersion\App Paths\Winword.exe"
    for raiz in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for vista in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(raiz, caminho, 0, winreg.KEY_READ | vista) as k:
                    exe, _ = winreg.QueryValueEx(k, "")
                    if exe:
                        return f"{exe.strip(chr(34))},0"
            except OSError:
                continue
    return ""


def criar_atalho(lnk: Path, alvo: Path, argumentos: str, icone: str, descricao: str) -> None:
    """Um .lnk pelo WScript.Shell do Windows (o do Explorer, não o Word)."""
    def aspas(t: str) -> str:
        return "'" + str(t).replace("'", "''") + "'"

    lnk.parent.mkdir(parents=True, exist_ok=True)
    script = ("$s = New-Object -ComObject WScript.Shell; "
              f"$a = $s.CreateShortcut({aspas(lnk)}); $a.TargetPath = {aspas(alvo)}; "
              f"$a.Arguments = {aspas(argumentos)}; $a.WorkingDirectory = {aspas(alvo.parent)}; "
              f"$a.Description = {aspas(descricao)}; "
              + (f"$a.IconLocation = {aspas(icone)}; " if icone else "") + "$a.Save()")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True,
                       timeout=60, creationflags=_sem_janela())
    if r.returncode != 0 or not lnk.exists():
        raise OSError(f"o Windows não criou o atalho: {(r.stderr or '').strip()[:200]}")


def lnk_em(pasta: Path | None) -> Path | None:
    return pasta / f"{NOME_DO_ATALHO}.lnk" if pasta else None


def ligar_botao_direito(exe: Path, base: str = BASE) -> None:
    import winreg

    icone = icone_do_word() or f'"{exe}",0'
    for tipo in TIPOS:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + "\\" + tipo + r"\shell" + "\\" + VERBO) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, ROTULO)
            winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, icone)
            with winreg.CreateKey(k, "command") as c:
                winreg.SetValueEx(c, "", 0, winreg.REG_SZ, f'"{exe}" --word-abrir "%1"')
    _avisar_o_explorer()


def desligar_botao_direito(base: str = BASE) -> None:
    import winreg

    for tipo in TIPOS:
        chave = base + "\\" + tipo + r"\shell" + "\\" + VERBO
        for sub in (chave + r"\command", chave):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
            except OSError:
                pass
    _avisar_o_explorer()


def botao_direito_ligado(exe: Path | None, base: str = BASE) -> bool:
    if sys.platform != "win32" or not exe:
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base + r"\.docx\shell" + "\\" + VERBO + r"\command") as k:
            comando, _ = winreg.QueryValueEx(k, "")
    except OSError:
        return False
    return str(exe) in comando and "--word-abrir" in comando


def _avisar_o_explorer() -> None:
    try:
        import ctypes

        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    except Exception:  # noqa: BLE001 - o menu vale na próxima vez que o Explorer olhar
        pass


def pedido_do_word(argv: list[str]) -> tuple[str, str] | None:
    """O que o atalho ou o botão direito pediram: ("novo", "") ou ("abrir", <arquivo>)."""
    if "--word-abrir" in argv:
        i = argv.index("--word-abrir")
        if i + 1 < len(argv):
            return ("abrir", str(Path(argv[i + 1]).resolve()))
        return None
    if "--word" in argv:
        return ("novo", "")
    return None
