"""
PAULUS Legal - Varredura de documentos no disco.

Percorre as pastas escolhidas pelo usuario procurando documentos. Varrer o
disco inteiro seria inutil e lento: o que interessa esta em Documentos,
Desktop, Drive sincronizado e afins. As pastas de sistema sao puladas de
proposito - nao ha contrato de cliente dentro de Windows/ ou AppData/.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from extract import SUPPORTED_SUFFIXES

# Pastas que nunca contem documento de cliente e custam caro para percorrer.
PASTAS_IGNORADAS = {
    "$recycle.bin",
    ".git",
    ".idea",
    ".vscode",
    "__pycache__",
    "appdata",
    "application data",
    "node_modules",
    "program files",
    "program files (x86)",
    "programdata",
    "site-packages",
    "system volume information",
    "temp",
    "tmp",
    "venv",
    ".venv",
    "windows",
}

TAMANHO_MAXIMO_MB = 50


@dataclass
class Arquivo:
    """Um documento encontrado no disco, ainda sem ler o conteudo."""

    path: str
    nome: str
    pasta: str
    suffix: str
    bytes: int
    modificado: str

    @property
    def mb(self) -> float:
        return self.bytes / (1024 * 1024)


@dataclass
class Varredura:
    arquivos: list[Arquivo]
    pastas_visitadas: int
    sem_permissao: list[str]
    ignorados_por_tamanho: list[str]

    @property
    def total(self) -> int:
        return len(self.arquivos)


def raizes_sugeridas() -> list[dict]:
    """
    Pastas do Windows onde documento de escritorio costuma estar.

    So devolve o que existe de fato, para a interface nao oferecer caminho
    morto.
    """
    lar = Path.home()
    candidatas = [
        (lar / "Documents", "Documentos"),
        (lar / "Documentos", "Documentos"),
        (lar / "Desktop", "Area de Trabalho"),
        (lar / "Downloads", "Downloads"),
        (lar / "OneDrive", "OneDrive"),
        (lar / "OneDrive" / "Documentos", "OneDrive - Documentos"),
        (lar / "Google Drive", "Google Drive"),
    ]

    vistos: set[str] = set()
    saida: list[dict] = []
    for caminho, rotulo in candidatas:
        chave = str(caminho).lower()
        if chave in vistos or not caminho.is_dir():
            continue
        vistos.add(chave)
        saida.append({"caminho": str(caminho), "rotulo": rotulo})

    return saida


def _deve_ignorar(pasta: str, excluir: set[str]) -> bool:
    minuscula = pasta.lower()
    return minuscula in PASTAS_IGNORADAS or minuscula in excluir


def raizes_unicas(raizes: list[Path] | list[str]) -> list[Path]:
    """
    Descarta raizes repetidas e as que ja estao dentro de outra.

    Escolher OneDrive e OneDrive/Documentos faria a varredura visitar os mesmos
    arquivos duas vezes, e o plano proporia mover o mesmo documento duas vezes.
    """
    resolvidas: list[Path] = []
    for bruta in raizes:
        try:
            caminho = Path(bruta).resolve()
        except OSError:
            continue
        if caminho.is_dir():
            resolvidas.append(caminho)

    unicas: list[Path] = []
    for caminho in sorted(set(resolvidas), key=lambda p: len(p.parts)):
        if not any(caminho == mantida or mantida in caminho.parents for mantida in unicas):
            unicas.append(caminho)
    return unicas


def escanear(
    raizes: list[Path] | list[str],
    *,
    excluir: list[str] | None = None,
    max_mb: float = TAMANHO_MAXIMO_MB,
    limite: int | None = None,
    profundidade: int | None = None,
) -> Varredura:
    """
    Procura documentos suportados nas raizes informadas.

    - `excluir`: nomes de pasta adicionais a pular (alem das de sistema)
    - `max_mb`: arquivo maior que isso e listado a parte, nao processado
    - `limite`: para a varredura depois de N arquivos (util para previa)
    - `profundidade`: quantos niveis descer a partir da raiz; None = sem limite
    """
    excluidos = {e.strip().lower() for e in (excluir or []) if e.strip()}
    arquivos: list[Arquivo] = []
    sem_permissao: list[str] = []
    grandes: list[str] = []
    vistos: set[str] = set()
    pastas = 0

    for base in raizes_unicas(raizes):

        for pasta_atual, subpastas, nomes in os.walk(base, onerror=lambda e: sem_permissao.append(str(e.filename))):
            pastas += 1
            atual = Path(pasta_atual)

            # Poda: alterar subpastas no lugar impede o os.walk de descer nelas.
            subpastas[:] = [s for s in subpastas if not _deve_ignorar(s, excluidos)]
            if profundidade is not None:
                try:
                    if len(atual.relative_to(base).parts) >= profundidade:
                        subpastas[:] = []
                except ValueError:
                    pass

            for nome in nomes:
                if Path(nome).suffix.lower() not in SUPPORTED_SUFFIXES:
                    continue

                caminho = atual / nome
                chave = str(caminho).lower()
                if chave in vistos:
                    continue
                vistos.add(chave)

                try:
                    info = caminho.stat()
                except OSError:
                    sem_permissao.append(str(caminho))
                    continue

                if info.st_size > max_mb * 1024 * 1024:
                    grandes.append(str(caminho))
                    continue

                arquivos.append(
                    Arquivo(
                        path=str(caminho),
                        nome=nome,
                        pasta=str(atual),
                        suffix=caminho.suffix.lower(),
                        bytes=info.st_size,
                        modificado=datetime.fromtimestamp(info.st_mtime).strftime("%Y-%m-%d"),
                    )
                )

                if limite is not None and len(arquivos) >= limite:
                    return Varredura(arquivos, pastas, sem_permissao, grandes)

    arquivos.sort(key=lambda a: a.path.lower())
    return Varredura(arquivos, pastas, sem_permissao, grandes)


if __name__ == "__main__":
    import sys

    alvos = sys.argv[1:] or [d["caminho"] for d in raizes_sugeridas()]
    print("Varrendo:")
    for alvo in alvos:
        print(f"  {alvo}")

    resultado = escanear(alvos)
    print(f"\n{resultado.total} documento(s) em {resultado.pastas_visitadas} pasta(s)")
    if resultado.sem_permissao:
        print(f"{len(resultado.sem_permissao)} caminho(s) sem permissao de leitura")
    if resultado.ignorados_por_tamanho:
        print(f"{len(resultado.ignorados_por_tamanho)} arquivo(s) acima do limite de tamanho")
