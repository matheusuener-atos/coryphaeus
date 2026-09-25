"""
PAULUS Legal - Plano de organizacao de arquivos.

Regras que nao se negociam neste modulo:

1. Nada se move sem plano aprovado. `montar_plano` nao toca em disco.
2. Nada e apagado. Nada e sobrescrito - colisao ganha sufixo. (A unica
   excecao e desfazer uma COPIA: sai a copia que o proprio plano criou; o
   original nunca foi tocado.)
3. Todo movimento vai para um diario, e `desfazer` reverte o lote inteiro.
4. Nada sai da pasta de destino escolhida.

O plano move (tira da origem) ou copia (a origem fica). Arquivo que ja esta
no lugar que o padrao pede fica onde esta: reorganizar o proprio acervo nao
pode criar "contrato (2).pdf" de si mesmo.

Reorganizar o acervo de um escritorio e destrutivo e dificil de conferir no
olho. O diario e o que separa "ferramenta" de "acidente".
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from classify import Classificacao

# Campos aceitos no padrao de pastas.
CAMPOS = ("cliente", "tipo", "tipo_rotulo", "ano", "mes", "mes_nome", "confianca")

PADROES_SUGERIDOS = [
    {"padrao": "{cliente}/{tipo_rotulo}", "rotulo": "Cliente > Tipo de documento"},
    {"padrao": "{tipo_rotulo}/{cliente}", "rotulo": "Tipo de documento > Cliente"},
    {"padrao": "{ano}/{mes_nome}/{tipo_rotulo}", "rotulo": "Ano > Mes > Tipo"},
    {"padrao": "{tipo_rotulo}/{ano}", "rotulo": "Tipo de documento > Ano"},
    {"padrao": "{cliente}/{ano}/{tipo_rotulo}", "rotulo": "Cliente > Ano > Tipo"},
]

SEM_VALOR = "_A revisar"
CARACTERES_PROIBIDOS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVADOS_WINDOWS = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


@dataclass
class Movimento:
    origem: str
    destino: str
    nome: str
    cliente: str
    tipo: str
    confianca: str
    motivo: str = ""       # por que caiu em "_A revisar", quando for o caso

    @property
    def pasta_destino(self) -> str:
        return str(Path(self.destino).parent)


OPERACOES = ("mover", "copiar")


@dataclass
class Plano:
    movimentos: list[Movimento]
    destino: str
    padrao: str
    ignorados: list[dict]
    operacao: str = "mover"        # "mover" tira da origem; "copiar" deixa o original

    @property
    def total(self) -> int:
        return len(self.movimentos)

    def resumo_por_pasta(self) -> list[dict]:
        contagem: dict[str, int] = {}
        for m in self.movimentos:
            contagem[m.pasta_destino] = contagem.get(m.pasta_destino, 0) + 1
        return [
            {"pasta": pasta, "arquivos": qtd}
            for pasta, qtd in sorted(contagem.items(), key=lambda x: x[0].lower())
        ]

    def to_dict(self) -> dict:
        return {
            "destino": self.destino,
            "padrao": self.padrao,
            "operacao": self.operacao,
            "total": self.total,
            "movimentos": [asdict(m) for m in self.movimentos],
            "ignorados": self.ignorados,
            "pastas": self.resumo_por_pasta(),
        }


# --------------------------------------------------------------------------
# Nomes de pasta seguros no Windows
# --------------------------------------------------------------------------


def _palavra_de_pasta(palavra: str) -> str:
    """
    Capitaliza uma palavra de nome proprio, preservando siglas.

    "S.A." nao pode virar "S.a." e "ME" nao pode virar "me" - sao siglas de
    razao social e aparecem no nome da pasta.
    """
    if "." in palavra.strip("."):  # S.A., S/A ja normalizado, Ltda.
        return palavra
    if len(palavra) <= 2:
        return palavra.lower() if palavra.lower() in {"e", "de", "da", "do", "em"} else palavra
    return palavra.capitalize()


def limpar_segmento(valor: str, *, limite: int = 60) -> str:
    """
    Transforma um valor em nome de pasta valido no Windows.

    Nome de parte vem em CAIXA ALTA e as vezes com 90 caracteres; vira pasta
    ilegivel. Aqui vira Capitalizado E Curto.
    """
    if not valor or not valor.strip():
        return SEM_VALOR

    limpo = CARACTERES_PROIBIDOS.sub(" ", valor)
    limpo = " ".join(limpo.split()).strip(" .")

    if not limpo:
        return SEM_VALOR

    # CAIXA ALTA inteira fica agressiva como nome de pasta.
    if limpo.isupper():
        limpo = " ".join(_palavra_de_pasta(p) for p in limpo.split())

    if len(limpo) > limite:
        limpo = limpo[:limite].rsplit(" ", 1)[0].strip() or limpo[:limite]

    if limpo.lower() in RESERVADOS_WINDOWS:
        limpo = f"{limpo}_"

    return limpo or SEM_VALOR


def _campos(resultado: Classificacao) -> dict[str, str]:
    dados = resultado.to_dict()
    return {campo: str(dados.get(campo, "") or "") for campo in CAMPOS}


def render_padrao(padrao: str, resultado: Classificacao) -> tuple[str, str]:
    """
    Aplica o padrao aos dados do documento.

    Devolve (caminho_relativo, motivo). `motivo` explica quando algum campo
    ficou vazio - a interface mostra isso para o usuario decidir.
    """
    valores = _campos(resultado)
    faltando: list[str] = []
    partes: list[str] = []

    for segmento in [s for s in padrao.replace("\\", "/").split("/") if s.strip()]:
        texto = segmento
        for campo in CAMPOS:
            marcador = "{" + campo + "}"
            if marcador in texto:
                bruto = valores.get(campo, "")
                if not bruto:
                    faltando.append(campo)
                texto = texto.replace(marcador, bruto)
        partes.append(limpar_segmento(texto))

    motivo = ""
    if faltando:
        nomes = ", ".join(dict.fromkeys(faltando))
        motivo = f"sem {nomes} no documento"

    return "/".join(partes) if partes else SEM_VALOR, motivo


def caminho_livre(alvo: Path, ocupados: set[str] | None = None) -> Path:
    """
    Caminho que ainda nao existe, somando sufixo quando preciso.

    `ocupados` cobre as colisoes dentro do proprio plano, antes de qualquer
    arquivo existir em disco.
    """
    ocupados = ocupados if ocupados is not None else set()

    def livre(p: Path) -> bool:
        return not p.exists() and str(p).lower() not in ocupados

    if livre(alvo):
        return alvo

    base, sufixo = alvo.stem, alvo.suffix
    for n in range(2, 1000):
        candidato = alvo.with_name(f"{base} ({n}){sufixo}")
        if livre(candidato):
            return candidato

    marca = datetime.now().strftime("%Y%m%d%H%M%S")
    return alvo.with_name(f"{base} ({marca}){sufixo}")


# --------------------------------------------------------------------------
# Plano
# --------------------------------------------------------------------------


def montar_plano(
    resultados: list[Classificacao],
    destino: Path | str,
    padrao: str,
    *,
    incluir_baixa_confianca: bool = True,
    operacao: str = "mover",
) -> Plano:
    """Monta o plano de movimentacao. NAO toca em disco."""
    raiz = Path(destino)
    movimentos: list[Movimento] = []
    ignorados: list[dict] = []
    ocupados: set[str] = set()
    operacao = operacao if operacao in OPERACOES else "mover"

    for resultado in resultados:
        if resultado.erro:
            ignorados.append({"nome": resultado.nome, "motivo": resultado.erro})
            continue

        if not incluir_baixa_confianca and resultado.confianca == "baixa":
            ignorados.append({"nome": resultado.nome, "motivo": "confianca baixa"})
            continue

        relativo, motivo = render_padrao(padrao, resultado)
        ideal = raiz / relativo / resultado.nome
        if _mesmo_arquivo(ideal, Path(resultado.arquivo)):
            # Ja esta onde o padrao pede. Mover para o mesmo lugar geraria
            # "nome (2)" do proprio arquivo; copiar, uma copia inutil.
            ignorados.append({"nome": resultado.nome, "motivo": "já está no lugar"})
            continue
        alvo = caminho_livre(ideal, ocupados)
        ocupados.add(str(alvo).lower())

        movimentos.append(
            Movimento(
                origem=resultado.arquivo,
                destino=str(alvo),
                nome=resultado.nome,
                cliente=resultado.cliente,
                tipo=resultado.tipo_rotulo,
                confianca=resultado.confianca,
                motivo=motivo,
            )
        )

    return Plano(movimentos, str(raiz), padrao, ignorados, operacao)


def _mesmo_arquivo(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return str(a).lower() == str(b).lower()


# --------------------------------------------------------------------------
# Aplicacao e desfazer
# --------------------------------------------------------------------------


@dataclass
class Resultado:
    movidos: int
    falhas: list[dict]
    diario: str

    @property
    def ok(self) -> bool:
        return not self.falhas


def aplicar_plano(plano: Plano, diario_dir: Path | str) -> Resultado:
    """
    Executa o plano, gravando o diario ANTES de cada movimento.

    Se o processo morrer no meio, o diario ja contem o que foi feito - e o
    desfazer funciona mesmo assim.
    """
    pasta_diario = Path(diario_dir)
    pasta_diario.mkdir(parents=True, exist_ok=True)
    diario = pasta_diario / f"movimentos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    copiar = plano.operacao == "copiar"
    registro = {
        "criado_em": datetime.now().isoformat(timespec="seconds"),
        "destino": plano.destino,
        "padrao": plano.padrao,
        "operacao": plano.operacao,
        "movimentos": [],
    }
    falhas: list[dict] = []
    movidos = 0

    def gravar() -> None:
        diario.write_text(json.dumps(registro, ensure_ascii=False, indent=1), encoding="utf-8")

    gravar()

    for movimento in plano.movimentos:
        origem = Path(movimento.origem)
        if not origem.exists():
            falhas.append({"nome": movimento.nome, "motivo": "arquivo nao existe mais"})
            continue

        alvo = caminho_livre(Path(movimento.destino))
        try:
            alvo.parent.mkdir(parents=True, exist_ok=True)
            registro["movimentos"].append({"origem": str(origem), "destino": str(alvo)})
            gravar()  # diario antes do movimento: falha no meio nao perde rastro
            if copiar:
                shutil.copy2(str(origem), str(alvo))
            else:
                shutil.move(str(origem), str(alvo))
            movidos += 1
        except OSError as exc:
            registro["movimentos"].pop()
            gravar()
            falhas.append({"nome": movimento.nome, "motivo": str(exc)})

    registro["concluido_em"] = datetime.now().isoformat(timespec="seconds")
    registro["movidos"] = movidos
    gravar()

    if not copiar:
        # Reorganizar a propria pasta de destino esvazia as pastas antigas
        # ("Compra e Venda > ..."): saem as que ficaram vazias, so dentro do
        # destino. Pasta de origem de fora (a que a pessoa escolheu) fica.
        _limpar_pastas_vazias_acima(
            [Path(m["origem"]).parent for m in registro["movimentos"]], plano.destino
        )

    return Resultado(movidos=movidos, falhas=falhas, diario=str(diario))


def _limpar_pastas_vazias_acima(pastas: list[Path], raiz: str) -> None:
    """Sobe de cada pasta ate a raiz tirando as que ficaram vazias. Nunca arquivo."""
    try:
        base = Path(raiz).resolve()
    except OSError:
        return
    for pasta in sorted({p for p in pastas}, key=lambda p: len(p.parts), reverse=True):
        atual = pasta
        while True:
            try:
                real = atual.resolve()
            except OSError:
                break
            if real == base or base not in real.parents:
                break
            try:
                atual.rmdir()   # so remove pasta vazia; com qualquer coisa dentro, falha
            except OSError:
                break
            atual = atual.parent


def desfazer(diario_path: Path | str) -> Resultado:
    """
    Devolve cada arquivo ao lugar de origem, na ordem inversa.

    Num lote de copia, desfazer e tirar as copias: o original nunca saiu do
    lugar. So sai a copia que ainda e a mesma que o plano criou (mesmo
    tamanho do original) - se a pessoa editou a copia depois, ela fica.
    """
    caminho = Path(diario_path)
    registro = json.loads(caminho.read_text(encoding="utf-8"))
    copia = registro.get("operacao") == "copiar"

    falhas: list[dict] = []
    revertidos = 0
    restantes: list[dict] = []

    for item in reversed(registro.get("movimentos", [])):
        atual = Path(item["destino"])
        volta = Path(item["origem"])

        if not atual.exists():
            falhas.append({"nome": atual.name, "motivo": "arquivo nao esta mais no destino"})
            continue

        try:
            if copia:
                # Sem o original, a copia virou o unico exemplar: nao sai.
                if not volta.exists():
                    falhas.append({"nome": atual.name, "motivo": "o original não existe mais - a cópia ficou"})
                    restantes.append(item)
                    continue
                if volta.stat().st_size != atual.stat().st_size:
                    falhas.append({"nome": atual.name, "motivo": "a cópia mudou depois de copiada - ficou"})
                    restantes.append(item)
                    continue
                atual.unlink()
                revertidos += 1
                continue
            volta.parent.mkdir(parents=True, exist_ok=True)
            destino_final = caminho_livre(volta)
            shutil.move(str(atual), str(destino_final))
            revertidos += 1
        except OSError as exc:
            falhas.append({"nome": atual.name, "motivo": str(exc)})
            restantes.append(item)

    registro["movimentos"] = list(reversed(restantes))
    registro["desfeito_em"] = datetime.now().isoformat(timespec="seconds")
    registro["revertidos"] = revertidos
    caminho.write_text(json.dumps(registro, ensure_ascii=False, indent=1), encoding="utf-8")

    _limpar_pastas_vazias(registro.get("destino", ""))

    return Resultado(movidos=revertidos, falhas=falhas, diario=str(caminho))


def _limpar_pastas_vazias(raiz: str) -> None:
    """Remove so pastas vazias criadas pelo plano. Nunca remove arquivo."""
    if not raiz:
        return
    base = Path(raiz)
    if not base.is_dir():
        return

    for pasta in sorted(base.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if pasta.is_dir():
            try:
                next(pasta.iterdir())
            except StopIteration:
                try:
                    pasta.rmdir()
                except OSError:
                    pass
            except OSError:
                pass


def listar_diarios(diario_dir: Path | str) -> list[dict]:
    """Lotes aplicados, do mais recente para o mais antigo."""
    pasta = Path(diario_dir)
    if not pasta.is_dir():
        return []

    saida: list[dict] = []
    for arquivo in sorted(pasta.glob("movimentos_*.json"), reverse=True):
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        saida.append(
            {
                "diario": str(arquivo),
                "criado_em": dados.get("criado_em", ""),
                "destino": dados.get("destino", ""),
                "padrao": dados.get("padrao", ""),
                "pendentes": len(dados.get("movimentos", [])),
                "desfeito_em": dados.get("desfeito_em", ""),
            }
        )
    return saida
