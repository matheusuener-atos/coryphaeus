"""
PAULUS - Carregador de habilidades.

Le a pasta `habilidades/` e transforma cada arquivo numa habilidade. Um
arquivo com erro nao derruba o programa: ele entra na lista marcado com o
problema, e o resto continua funcionando. Sem esse isolamento, um erro de
digitacao num modulo mataria a aplicacao inteira - e ai nao ha nada de
modular.
"""

from __future__ import annotations

import importlib.util
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from habilidade_base import (
    COM_PROBLEMA,
    EM_BREVE,
    GRUPOS,
    PRONTA,
    ROTULOS_PRECISA,
    Habilidade,
)


@dataclass
class Registro:
    habilidades: list[Habilidade] = field(default_factory=list)
    pasta: str = ""

    def obter(self, id_: str) -> Habilidade | None:
        return next((h for h in self.habilidades if h.id == id_), None)

    @property
    def problemas(self) -> list[Habilidade]:
        return [h for h in self.habilidades if h.estado == COM_PROBLEMA]

    def contagem(self) -> dict:
        return {
            "prontas": sum(1 for h in self.habilidades if h.estado == PRONTA),
            "em_breve": sum(1 for h in self.habilidades if h.estado == EM_BREVE),
            "com_problema": len(self.problemas),
            "total": len(self.habilidades),
        }

    def por_grupo(self, disponibilidade: dict[str, bool] | None = None) -> list[dict]:
        """Habilidades agrupadas para a tela, com o que falta para cada uma."""
        disponivel = disponibilidade or {}
        ordem_grupos = GRUPOS + ["Com problema"]
        saida: list[dict] = []

        for grupo in ordem_grupos:
            itens = []
            for habilidade in self.habilidades:
                alvo = "Com problema" if habilidade.estado == COM_PROBLEMA else habilidade.grupo
                if alvo != grupo:
                    continue

                dados = habilidade.to_dict()
                faltando = [
                    ROTULOS_PRECISA.get(p, p)
                    for p in habilidade.precisa
                    if not disponivel.get(p, False)
                ]
                dados["faltando"] = faltando
                dados["utilizavel"] = habilidade.executavel and not faltando
                itens.append(dados)

            if itens:
                itens.sort(key=lambda d: (d["ordem"], d["nome"]))
                saida.append({"grupo": grupo, "habilidades": itens})

        return saida


def _quebrada(caminho: Path, motivo: str) -> Habilidade:
    """Habilidade de fachada para um arquivo que nao carregou."""
    return Habilidade(
        id=f"quebrada:{caminho.stem}",
        nome=caminho.name,
        resumo="Este módulo não carregou",
        grupo="Com problema",
        estado=COM_PROBLEMA,
        arquivo=str(caminho),
        problema=motivo,
        detalhe="O programa continua funcionando sem ele. Corrija o arquivo e reabra.",
    )


def _carregar_arquivo(caminho: Path) -> Habilidade:
    nome_modulo = f"paulus_habilidade_{caminho.stem}"

    try:
        spec = importlib.util.spec_from_file_location(nome_modulo, caminho)
        if spec is None or spec.loader is None:
            return _quebrada(caminho, "não consegui ler o arquivo")

        modulo = importlib.util.module_from_spec(spec)
        sys.modules[nome_modulo] = modulo
        spec.loader.exec_module(modulo)
    except Exception:
        sys.modules.pop(nome_modulo, None)
        linhas = traceback.format_exc(limit=2).strip().splitlines()
        return _quebrada(caminho, linhas[-1] if linhas else "erro ao carregar")

    declarada = getattr(modulo, "HABILIDADE", None)
    if not isinstance(declarada, Habilidade):
        return _quebrada(caminho, "o arquivo não declara HABILIDADE = Habilidade(...)")

    if declarada.grupo not in GRUPOS:
        return _quebrada(caminho, f"grupo desconhecido: {declarada.grupo!r}")

    declarada.arquivo = str(caminho)
    executar = getattr(modulo, "executar", None)
    declarada.executar = executar if callable(executar) else None

    if declarada.estado == PRONTA and declarada.executar is None:
        return _quebrada(caminho, "está marcada como pronta mas não tem executar()")

    return declarada


def carregar(pasta: Path | str) -> Registro:
    """
    Le todos os modulos da pasta.

    Arquivos comecando com "_" sao ignorados: servem para codigo compartilhado
    entre habilidades, nao sao habilidades.
    """
    raiz = Path(pasta)
    registro = Registro(pasta=str(raiz))
    if not raiz.is_dir():
        return registro

    vistos: dict[str, Path] = {}
    for caminho in sorted(raiz.glob("*.py")):
        if caminho.name.startswith("_"):
            continue

        habilidade = _carregar_arquivo(caminho)

        # Dois arquivos com o mesmo id fariam a interface abrir um e listar o
        # outro. Melhor apontar o conflito do que escolher em silencio.
        anterior = vistos.get(habilidade.id)
        if anterior and habilidade.estado != COM_PROBLEMA:
            habilidade = _quebrada(
                caminho, f"o id {habilidade.id!r} já é usado por {anterior.name}"
            )
        vistos[habilidade.id] = caminho

        registro.habilidades.append(habilidade)

    return registro
