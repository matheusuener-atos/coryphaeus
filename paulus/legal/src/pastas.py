"""
PAULUS - Navegacao de pastas para a interface.

O usuario escolhe onde procurar navegando pelo computador, como no seletor de
arquivo do Windows: unidades, pastas, um nivel por vez. Uma lista fixa de
sugestoes ja marcadas convida ao acidente de varrer o disco inteiro.
"""

from __future__ import annotations

import os
import string
from dataclasses import dataclass
from pathlib import Path

# Nao vale a pena oferecer: nao ha documento de cliente ai dentro.
OCULTAS = {
    "$recycle.bin", "appdata", "application data", "config.msi", "msocache",
    "perflogs", "program files", "program files (x86)", "programdata",
    "recovery", "system volume information", "windows", "winsxs",
    "node_modules", "__pycache__", "venv", ".venv", ".git",
}


@dataclass
class Entrada:
    nome: str
    caminho: str
    tipo: str = "pasta"     # "pasta" | "unidade"


def unidades() -> list[Entrada]:
    """Unidades de disco presentes, tolerando drive de rede que nao responde."""
    achadas: list[Entrada] = []
    for letra in string.ascii_uppercase:
        raiz = f"{letra}:\\"
        try:
            if os.path.exists(raiz):
                achadas.append(Entrada(nome=raiz.rstrip("\\"), caminho=raiz, tipo="unidade"))
        except OSError:
            continue
    return achadas


def atalhos() -> list[Entrada]:
    """Lugares por onde a pessoa costuma comecar. Sugestao, nunca selecao."""
    lar = Path.home()
    candidatos = [
        (lar, "Pasta pessoal"),
        (lar / "Documents", "Documentos"),
        (lar / "Documentos", "Documentos"),
        (lar / "Desktop", "Área de Trabalho"),
        (lar / "Downloads", "Downloads"),
        (lar / "OneDrive", "OneDrive"),
    ]

    vistos: set[str] = set()
    saida: list[Entrada] = []
    for caminho, rotulo in candidatos:
        chave = str(caminho).lower()
        if chave in vistos:
            continue
        try:
            if not caminho.is_dir():
                continue
        except OSError:
            continue
        vistos.add(chave)
        saida.append(Entrada(nome=rotulo, caminho=str(caminho)))
    return saida


def _interessa(nome: str) -> bool:
    # "$WINDOWS.~BT", "$WinREAgent" e afins sao sobras de atualizacao do
    # sistema. Aparecem na raiz de C: e so poluem a escolha.
    if nome.startswith((".", "$", "~")):
        return False
    return nome.lower() not in OCULTAS


def listar(caminho: str | None = None) -> dict:
    """
    Um nivel de navegacao.

    Sem caminho, devolve unidades e atalhos - a tela inicial do seletor.
    """
    if not caminho:
        return {
            "atual": "",
            "titulo": "Este computador",
            "pai": None,
            "unidades": [vars(u) for u in unidades()],
            "atalhos": [vars(a) for a in atalhos()],
            "pastas": [],
            "erro": "",
        }

    alvo = Path(caminho)
    if not alvo.is_dir():
        return {
            "atual": str(alvo), "titulo": alvo.name or str(alvo), "pai": None,
            "unidades": [], "atalhos": [], "pastas": [],
            "erro": "essa pasta não existe mais",
        }

    pastas: list[dict] = []
    erro = ""
    try:
        with os.scandir(alvo) as itens:
            for item in itens:
                try:
                    if item.is_dir(follow_symlinks=False) and _interessa(item.name):
                        pastas.append(vars(Entrada(nome=item.name, caminho=item.path)))
                except OSError:
                    continue
    except PermissionError:
        erro = "sem permissão para abrir esta pasta"
    except OSError as exc:
        erro = f"não consegui abrir: {exc.strerror or exc}"

    pastas.sort(key=lambda p: p["nome"].lower())
    pai = str(alvo.parent) if alvo.parent != alvo else ""

    return {
        "atual": str(alvo),
        "titulo": alvo.name or str(alvo),
        "pai": pai,
        "unidades": [],
        "atalhos": [],
        "pastas": pastas,
        "erro": erro,
    }


def migalhas(caminho: str) -> list[dict]:
    """Trilha clicavel do caminho atual: C: > Users > Fulano > Documentos."""
    if not caminho:
        return []
    alvo = Path(caminho)
    partes = list(alvo.parts)
    trilha: list[dict] = []
    acumulado = ""
    for i, parte in enumerate(partes):
        acumulado = parte if i == 0 else str(Path(acumulado) / parte)
        trilha.append({"nome": parte.rstrip("\\") or parte, "caminho": acumulado})
    return trilha
