"""
A biblioteca quando ela cresce.

Com 128 documentos a lista basta. Com 1.200, a lista é o problema: rolar não é
achar. O que falta não é mais informação na tela — é um jeito de estreitar o
que está à vista e de agir em muitos de uma vez.

Três decisões moram aqui:

**Procurar inclui o conteúdo.** Quem lembra "aquele contrato que falava em
cessão de direitos hereditários" não lembra o nome do arquivo. O índice de
leitura já tem os trechos; procurar neles custa nada e é o que a pessoa quer.
Quando o achado vem do conteúdo, a tela mostra o trecho — senão o documento
aparece na lista sem explicação de por que apareceu.

**A marca é do documento, não do caminho.** Fixar fica guardado por SHA-1:
mover ou renomear o arquivo não pode desfazer a marca, porque é o mesmo
documento.

**O que o lote faz, o lote desfaz.** Mover e apagar em lote são efeitos
externos: passam pela fila de aprovação como qualquer outro, com o plano à
vista antes do sim. Um erro em lote é um erro multiplicado por 128.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import Path

# Os cortes que a tela oferece. "Recentes" é o padrão porque o documento que
# interessa quase sempre é o de agora; "todos" fica a um clique.
FILTROS = {
    "recentes": "Recentes",
    "fixados": "Fixados",
    "todos": "Todos",
    "sem-analise": "Sem análise",
}

ORDENS = {
    "modificacao": "modificação",
    "nome": "nome",
    "tamanho": "tamanho",
}

DIAS_DE_RECENTE = 14

MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro")

RE_ESPACO = re.compile(r"\s+")


def _sem_acento(texto: str) -> str:
    normal = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


# ------------------------------------------------------------------ marcas


class Marcas:
    """
    O que a pessoa marcou sobre cada documento.

    Guardado por SHA-1 de propósito: o caminho muda quando o arquivo é movido
    ou renomeado, e perder a marca nessa hora seria perder trabalho da pessoa.
    """

    def __init__(self, base) -> None:
        self.base = base

    def de_todos(self) -> dict[str, dict]:
        linhas = self.base.buscar("SELECT * FROM marcas_acervo")
        return {l["sha1"]: dict(l) for l in linhas}

    def fixar(self, sha1: str, fixado: bool = True) -> bool:
        agora = datetime.now().isoformat(timespec="seconds")
        self.base.escrever(
            "INSERT INTO marcas_acervo (sha1, fixado, fixado_em) VALUES (?, ?, ?) "
            "ON CONFLICT(sha1) DO UPDATE SET fixado = excluded.fixado, "
            "fixado_em = excluded.fixado_em",
            (sha1, 1 if fixado else 0, agora if fixado else ""),
        )
        return fixado

    def marcar_visto(self, sha1: str) -> str:
        """Anota quando o documento foi analisado pela última vez."""
        agora = datetime.now().isoformat(timespec="seconds")
        self.base.escrever(
            "INSERT INTO marcas_acervo (sha1, visto_em) VALUES (?, ?) "
            "ON CONFLICT(sha1) DO UPDATE SET visto_em = excluded.visto_em",
            (sha1, agora),
        )
        return agora

    def esquecer(self, sha1: str) -> None:
        self.base.escrever("DELETE FROM marcas_acervo WHERE sha1 = ?", (sha1,))


# ------------------------------------------------------------------- tempo


def quando(iso: str, agora: datetime | None = None) -> str:
    """
    Um instante do jeito que se fala.

    "há 2 h" para o que é de hoje, a data por extenso para o resto. Dizer "há
    18 dias" de um documento de agosto obriga a pessoa a fazer a conta de
    cabeça para saber de quando é.

    `agora` existe para o teste. A resposta muda com a hora do dia — à meia
    noite e dez, uma leitura de uma hora atrás vira "ontem", que é verdade — e
    um teste que passa de tarde e falha de madrugada não mede nada.
    """
    if not iso:
        return ""
    try:
        quanto = datetime.fromisoformat(iso)
    except ValueError:
        return iso[:10]

    agora = agora or datetime.now()
    segundos = (agora - quanto).total_seconds()

    if segundos < 0:
        return "agora"
    if segundos < 90:
        return "agora"
    if segundos < 3600:
        return f"há {int(segundos // 60)} min"
    if segundos < 86400 and quanto.date() == agora.date():
        return f"há {int(segundos // 3600)} h"
    if (agora.date() - quanto.date()).days == 1:
        return "ontem"
    if quanto.year == agora.year:
        return f"{quanto.day} de {MESES[quanto.month - 1]}"
    return f"{quanto.day} de {MESES[quanto.month - 1]} de {quanto.year}"


def _idade_em_dias(iso: str) -> float:
    if not iso:
        return 1e9
    try:
        return (datetime.now() - datetime.fromisoformat(iso)).total_seconds() / 86400
    except ValueError:
        return 1e9


# ----------------------------------------------------------------- análise


def estado_da_analise(item: dict) -> dict:
    """
    Em que pé está a leitura deste documento.

    São três estados, e a diferença entre eles importa: "sem análise" é
    trabalho que não foi feito, "mudou desde então" é trabalho que foi feito e
    não vale mais. Confundir os dois faz a pessoa citar um documento pela
    versão errada.

    O "quando" só aparece se estiver medido. Documento analisado antes de
    existir esse registro mostra "analisado" e mais nada — melhor sem hora do
    que com hora inventada.
    """
    analisado = bool(item.get("tipo"))
    visto = item.get("visto_em", "")
    modificado = item.get("modificado_em", "")

    if not analisado:
        return {"estado": "sem-analise", "rotulo": "sem análise", "quando": ""}

    if visto and modificado and modificado > visto:
        return {"estado": "mudou", "rotulo": "mudou desde então", "quando": quando(visto)}

    rotulo = "analisado"
    if visto:
        rotulo += " · " + quando(visto)
    return {"estado": "analisado", "rotulo": rotulo, "quando": quando(visto)}


# ---------------------------------------------------------------- procurar


def _trecho_com_termo(texto: str, termo: str, volta: int = 46, total: int = 150) -> str:
    limpo = RE_ESPACO.sub(" ", texto).strip()
    onde = _sem_acento(limpo).find(termo)
    if onde < 0:
        return limpo[:total] + ("…" if len(limpo) > total else "")
    comeco = max(0, onde - volta)
    pedaco = limpo[comeco:comeco + total]
    return ("…" if comeco else "") + pedaco + ("…" if comeco + total < len(limpo) else "")


def indexar_trechos(chunks) -> dict[str, list[str]]:
    """Os trechos de cada documento, agrupados uma vez só."""
    por_documento: dict[str, list[str]] = {}
    for c in chunks or []:
        por_documento.setdefault(c.doc_name, []).append(c.text)
    return por_documento


def procurar(itens: list[dict], termo: str, trechos: dict[str, list[str]] | None = None) -> list[dict]:
    """
    Nome, pasta ou trecho.

    Procurar só no nome do arquivo devolve pouco: nome de arquivo é o que a
    pessoa menos lembra. Quando o achado veio do conteúdo, o item leva o
    trecho junto — sem isso o documento aparece na lista e quem procurou não
    sabe por quê.
    """
    alvo = _sem_acento(termo).strip()
    if not alvo:
        return [dict(i, achado_em="", trecho="") for i in itens]

    trechos = trechos or {}
    achados: list[dict] = []

    for item in itens:
        campos = {
            "nome": item.get("nome", ""),
            "pasta": item.get("pasta", ""),
            "cliente": item.get("cliente", ""),
            "tipo": item.get("tipo_rotulo", ""),
        }
        onde = next((k for k, v in campos.items() if alvo in _sem_acento(v)), "")
        if onde:
            achados.append(dict(item, achado_em=onde, trecho=""))
            continue

        for texto in trechos.get(item.get("nome", ""), []):
            if alvo in _sem_acento(texto):
                achados.append(dict(item, achado_em="trecho",
                                    trecho=_trecho_com_termo(texto, alvo)))
                break

    return achados


def filtrar(itens: list[dict], filtro: str) -> list[dict]:
    if filtro == "fixados":
        return [i for i in itens if i.get("fixado")]
    if filtro == "sem-analise":
        return [i for i in itens if not i.get("tipo")]
    if filtro == "recentes":
        return [i for i in itens if _idade_em_dias(i.get("modificado_em", "")) <= DIAS_DE_RECENTE]
    return list(itens)


def ordenar(itens: list[dict], ordem: str) -> list[dict]:
    """
    O fixado sobe sempre.

    Fixar é a pessoa dizendo "este importa". Deixá-lo cair na ordenação
    esvaziaria o gesto.
    """
    if ordem == "nome":
        chave = lambda i: _sem_acento(i.get("nome", ""))            # noqa: E731
        ao_contrario = False
    elif ordem == "tamanho":
        chave = lambda i: i.get("bytes", 0)                          # noqa: E731
        ao_contrario = True
    else:
        chave = lambda i: i.get("modificado_em", "")                 # noqa: E731
        ao_contrario = True

    ordenados = sorted(itens, key=chave, reverse=ao_contrario)
    return sorted(ordenados, key=lambda i: 0 if i.get("fixado") else 1)


# ------------------------------------------------------------------- lote


def plano_de_mover(itens: list[dict], destino: str | Path) -> dict:
    """
    O plano de mover, antes de mover.

    Devolve os movimentos e, separado, o que não dá para mover e por quê. O
    que não dá tem que aparecer na tela antes do sim: um lote que "moveu 6 de
    8" sem dizer quais dois ficaram é pior que um erro.
    """
    pasta = Path(destino)
    movimentos, impedidos = [], []
    nomes_usados: set[str] = set()

    for item in itens:
        origem = Path(item.get("caminho", ""))
        if not item.get("existe", True):
            impedidos.append({"nome": item.get("nome", ""), "motivo": "o arquivo não está mais no disco"})
            continue
        if origem.parent == pasta:
            impedidos.append({"nome": item.get("nome", ""), "motivo": "já está nessa pasta"})
            continue

        alvo = pasta / origem.name
        if str(alvo).lower() in nomes_usados or alvo.exists():
            alvo = _nome_livre(pasta, origem.name, nomes_usados)
        nomes_usados.add(str(alvo).lower())

        movimentos.append({
            "origem": str(origem),
            "destino": str(alvo),
            "nome": origem.name,
            "cliente": item.get("cliente", ""),
            "tipo": item.get("tipo", ""),
            "confianca": "manual",
            "motivo": "escolhido na biblioteca",
        })

    return {"movimentos": movimentos, "impedidos": impedidos, "destino": str(pasta)}


def _nome_livre(pasta: Path, nome: str, usados: set[str]) -> Path:
    """
    Nunca passar por cima de um arquivo que já existe.

    Mover em lote para uma pasta que já tem um arquivo de mesmo nome apagaria
    o de lá sem avisar. Um sufixo numérico custa nada e não perde nada.
    """
    base, sufixo = Path(nome).stem, Path(nome).suffix
    for n in range(2, 1000):
        alvo = pasta / f"{base} ({n}){sufixo}"
        if not alvo.exists() and str(alvo).lower() not in usados:
            return alvo
    return pasta / f"{base} ({datetime.now():%Y%m%d%H%M%S}){sufixo}"


def resumo_do_lote(acao: str, itens: list[dict], destino: str = "") -> str:
    """A frase que a fila mostra antes do sim, em português e com o número."""
    quantos = len(itens)
    plural = "documento" if quantos == 1 else "documentos"
    primeiros = ", ".join(i.get("nome", "") for i in itens[:3])
    se_mais = f" e mais {quantos - 3}" if quantos > 3 else ""

    if acao == "mover":
        return (f"Mover {quantos} {plural} para {destino}: {primeiros}{se_mais}. "
                f"Os arquivos saem de onde estão; dá para desfazer pelo diário.")
    if acao == "apagar":
        return (f"Tirar {quantos} {plural} da biblioteca: {primeiros}{se_mais}. "
                f"Apaga a cópia que o PAULUS guarda; o arquivo original de onde "
                f"veio não é tocado.")
    if acao == "exportar":
        return (f"Copiar {quantos} {plural} para {destino}: {primeiros}{se_mais}. "
                f"Nada é enviado para a internet — a cópia fica nessa pasta.")
    return f"{quantos} {plural}: {primeiros}{se_mais}"
