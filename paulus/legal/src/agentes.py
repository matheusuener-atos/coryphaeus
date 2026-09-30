"""
PAULUS - Agentes do escritorio (A1: carregar, validar e versionar).

Um agente e um especialista escrito pelo escritorio, em linguagem simples:
um arquivo `AGENTE.md` numa pasta por agente (`data/agentes/<slug>/`), com
um cabecalho YAML entre linhas `---` e, embaixo, as instrucoes. Ele NAO e
codigo: usa as capacidades (as habilidades Python de `habilidades/`) e as
ferramentas (`CATALOGO_FERRAMENTAS`) que ja existem, dentro dos limites que
declara. O formato esta no §2.6 de docs/prompt-conversa-agentes-v0.md.

Quatro decisoes:

**Nome desconhecido e erro, nunca silencio.** Uma ferramenta que nao esta no
catalogo, uma capacidade que nao carregou, um campo com erro de digitacao
("ferramenta:" em vez de "ferramentas:"): o agente fica "com problema", com o
motivo e a lista do que existe. Ignorar calado faria o escritorio achar que o
agente pode algo que ele nao pode - ou pior, que ele NAO pode algo que pode.

**Um agente com problema nao derruba os outros**, como em `registro.py`: ele
aparece na lista com o motivo, e o resto continua funcionando.

**`modelo` e perfil de tarefa, nunca nome de modelo.** O modelo de cada perfil
muda com a maquina (src/modelos.py); um agente preso a "llama3.2:3b" quebraria
no primeiro escritorio que usa outro.

**Importado e dado ate o titular aprovar.** Um SKILL.md ou AGENTE.md de fora
entra desativado, com origem "importado", o original guardado inteiro e o que
nele parece ordem ao assistente (src/blindagem.py) anotado na ficha. So liga
com a confirmacao explicita de que o conteudo foi visto.

O estado de cada agente (ligado, origem, aprovacao) mora ao lado do arquivo,
em `estado.json`, e nao no cabecalho: o AGENTE.md e o que o escritorio
escreve, e ligar ou desligar nao e edicao - nao deve criar versao nem mexer
no texto dele. A versao, ao contrario, fica no cabecalho: e parte do que foi
escrito, e cada edicao guarda a anterior em `versoes/<n>.md`.

Nesta etapa nenhum agente entra na conversa (isso e a A2).
"""

from __future__ import annotations

import difflib
import json
import re
import threading
import time
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

ARQUIVO = "AGENTE.md"
ESTADO = "estado.json"
ORIGINAL = "original.md"
VERSOES = "versoes"

ORIGENS = ("escritorio", "importado", "produto")
FORMATOS_SAIDA = ("texto", "lista", "tabela", "modelo_de_documento")
ACERVO_MODOS = ("acervo", "documento_em_foco")

# A ordem e a do §2.6: e a ordem em que a tela e o relatorio listam.
CAMPOS = ("nome", "descricao", "quando_usar", "capacidades", "ferramentas", "fontes", "saida", "modelo",
          "testes", "versao")
CAMPOS_QUANDO_USAR = ("exemplos", "palavras")
CAMPOS_FONTES = ("acervo", "biblioteca", "leis")
CAMPOS_SAIDA = ("formato", "modelo")
CAMPOS_TESTE = ("pergunta", "deve_conter")

# Do SKILL.md/AGENTE.md de fora para este formato.
MAPA_IMPORTACAO = {"name": "nome", "description": "descricao"}

# O que parece nome de modelo, e nao perfil: "llama3.2:3b", "qwen2.5", "gpt-4o".
RE_NOME_DE_MODELO = re.compile(r"[:/]|^(llama|qwen|gemma|phi|mistral|deepseek|gpt|claude|granite|smollm)", re.I)
RE_SLUG = re.compile(r"[\w-]{1,80}")
RE_VERSAO = re.compile(r"^(versao\s*:)[^#\n]*?(\s*#.*)?$")

MAX_NOME = 80
MAX_DESCRICAO = 1000
# Um agente e uma pagina de instrucoes; 200 mil caracteres e mais que um
# livro curto. Acima disso e arquivo errado, e iria inteiro para o modelo.
MAX_MARKDOWN = 200_000


class ErroDeAgente(ValueError):
    """Um motivo em portugues, pronto para a tela: o que esta errado e como corrigir."""


class AgenteNaoEncontrado(ErroDeAgente):
    pass


class ConflitoDeAgente(ErroDeAgente):
    """O pedido esta certo, mas o estado do agente nao deixa: nome repetido, importado sem aprovacao."""


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _plano(texto: str) -> str:
    """Sem acento e em minusculas: "Cláusula" e "clausula" sao a mesma palavra."""
    normal = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


def slug_de(nome: str) -> str:
    """O nome da pasta: "Revisor de contratos" -> "revisor-de-contratos"."""
    return re.sub(r"[^a-z0-9]+", "-", _plano(nome)).strip("-")[:60].strip("-") or "agente"


def _sugestao(valor: str, opcoes: Iterable[str]) -> str:
    perto = difflib.get_close_matches(str(valor), list(opcoes), n=1, cutoff=0.6)
    return f" (você quis dizer '{perto[0]}'?)" if perto else ""


def _lista_de(opcoes: Iterable[str]) -> str:
    return ", ".join(opcoes) or "nenhuma"


# ------------------------------------------------------------- o arquivo

def separar(texto: str) -> tuple[dict, str]:
    """
    O cabecalho YAML (entre as linhas ---) e o corpo markdown. Levanta
    ErroDeAgente com a linha, quando da para saber.
    """
    texto = (texto or "").lstrip("\ufeff").replace("\r\n", "\n")
    if len(texto) > MAX_MARKDOWN:
        raise ErroDeAgente(f"o arquivo passa de {MAX_MARKDOWN:,} caracteres: um agente é uma página de "
                           "instruções, não um documento".replace(",", "."))
    linhas = texto.split("\n")
    if not linhas or linhas[0].strip() != "---":
        raise ErroDeAgente("o arquivo precisa começar com o cabeçalho entre duas linhas --- "
                           "(a primeira linha do arquivo é ---)")
    fim = next((i for i in range(1, len(linhas)) if linhas[i].strip() in ("---", "...")), None)
    if fim is None:
        raise ErroDeAgente("o cabeçalho não fecha: falta a segunda linha --- depois dos campos")
    cabecalho = "\n".join(linhas[1:fim])
    corpo = "\n".join(linhas[fim + 1:]).strip("\n")
    try:
        dados = yaml.safe_load(cabecalho)
    except yaml.YAMLError as exc:
        marca = getattr(exc, "problem_mark", None)
        problema = getattr(exc, "problem", None) or str(exc).splitlines()[0]
        onde = f" na linha {marca.line + 2} do arquivo" if marca is not None else ""
        raise ErroDeAgente(f"o cabeçalho tem um erro de YAML{onde}: {problema} "
                           "(confira os dois-pontos, os colchetes e as aspas)") from exc
    if dados is None:
        dados = {}
    if not isinstance(dados, dict):
        raise ErroDeAgente("o cabeçalho precisa ser uma lista de campos no formato 'campo: valor'")
    return dados, corpo


def _texto(valor, onde: str, erros: list[str]) -> str:
    if isinstance(valor, bool) or valor is None or isinstance(valor, (list, dict)):
        erros.append(f"'{onde}' precisa ser um texto" + (" (ponha entre aspas)" if isinstance(valor, bool) else ""))
        return ""
    return str(valor).strip()


def _textos(valor, onde: str, erros: list[str]) -> list[str]:
    """Lista de textos. Numero vira texto; sim/nao sem aspas (YAML le como booleano) e erro."""
    if valor is None:
        return []
    if isinstance(valor, str):
        valor = [valor]
    if not isinstance(valor, list):
        erros.append(f"'{onde}' precisa ser uma lista, como [a, b]")
        return []
    saida = []
    for item in valor:
        if isinstance(item, bool) or isinstance(item, (list, dict)) or item is None:
            erros.append(f"um item de '{onde}' não é texto: {item!r} (ponha entre aspas)")
            continue
        if str(item).strip():
            saida.append(str(item).strip())
    return saida


def _sub(valor, onde: str, campos: tuple[str, ...], erros: list[str]) -> dict:
    if valor is None:
        return {}
    if not isinstance(valor, dict):
        erros.append(f"'{onde}' precisa ter os campos {_lista_de(campos)}, um por linha")
        return {}
    for k in valor:
        if k not in campos:
            erros.append(f"o campo '{onde}.{k}' não faz parte do formato{_sugestao(k, campos)}; "
                         f"os de '{onde}' são: {_lista_de(campos)}")
    return valor


# ------------------------------------------------------------- o agente

@dataclass
class Agente:
    slug: str
    arquivo: str = ""
    nome: str = ""
    descricao: str = ""
    quando_usar: dict = field(default_factory=lambda: {"exemplos": [], "palavras": []})
    capacidades: list[str] = field(default_factory=list)
    ferramentas: list[str] = field(default_factory=list)
    fontes: dict = field(default_factory=lambda: {"acervo": "acervo", "biblioteca": [], "leis": []})
    saida: dict = field(default_factory=lambda: {"formato": "texto", "modelo": ""})
    modelo: str = "conversa"
    testes: list[dict] = field(default_factory=list)
    versao: int = 1
    instrucoes: str = ""
    markdown: str = ""
    # O que nao esta no arquivo: estado.json.
    ativo: bool = False
    origem: str = "escritorio"
    aprovado_em: str = ""
    aprovado_por: str = ""
    importado_em: str = ""
    suspeitas: list[str] = field(default_factory=list)
    ignorados_na_importacao: list[str] = field(default_factory=list)
    atualizado_em: str = ""
    versoes: list[int] = field(default_factory=list)
    # Preenchidos pela validacao.
    problema: str = ""
    avisos: list[str] = field(default_factory=list)
    # A4 (src/agentes_medida.py): o ultimo teste, as contas de uso e se os
    # testes desta versao falharam - quem precisa de revisao nao e escolhido
    # sozinho na conversa.
    medida: dict = field(default_factory=dict)
    precisa_revisao: bool = False
    revisao_motivo: str = ""

    @property
    def precisa_aprovar(self) -> bool:
        """Importado que o titular ainda nao viu: e dado, nao instrucao."""
        return self.origem == "importado" and not self.aprovado_em

    @property
    def em_uso(self) -> bool:
        return self.ativo and not self.problema and not self.precisa_aprovar

    def ficha(self) -> dict:
        """O que a tela (A3) e a conversa (A2) usam. O markdown inteiro vem em `ler`."""
        return {
            "slug": self.slug, "nome": self.nome or self.slug, "descricao": self.descricao,
            "quando_usar": self.quando_usar, "capacidades": self.capacidades, "ferramentas": self.ferramentas,
            "fontes": self.fontes, "saida": self.saida, "modelo": self.modelo, "testes": self.testes,
            "versao": self.versao, "instrucoes": self.instrucoes,
            "estado": "com_problema" if self.problema else ("ativo" if self.ativo else "desativado"),
            "ativo": self.ativo, "em_uso": self.em_uso, "origem": self.origem,
            "problema": self.problema, "avisos": self.avisos, "suspeitas": self.suspeitas,
            "precisa_aprovar": self.precisa_aprovar, "aprovado_em": self.aprovado_em,
            "aprovado_por": self.aprovado_por, "importado_em": self.importado_em,
            "ignorados_na_importacao": self.ignorados_na_importacao,
            "versoes": self.versoes, "arquivo": self.arquivo, "atualizado_em": self.atualizado_em,
            "precisa_revisao": self.precisa_revisao, "revisao_motivo": self.revisao_motivo, "medida": self.medida,
        }


def _chamar(fonte):
    return fonte() if callable(fonte) else fonte


class Agentes:
    """
    Os agentes de uma pasta. Le do disco a cada consulta: sao poucos arquivos
    pequenos, e assim uma edicao feita a mao no AGENTE.md vale na hora, sem
    botao de recarregar.

    Os catalogos entram como funcoes (ou listas) para a validacao usar a lista
    VIVA: uma habilidade recarregada, ou uma ferramenta nova, vale na proxima
    leitura sem reabrir o programa.
    """

    def __init__(
        self,
        pasta: Path | str,
        *,
        capacidades: Callable[[], Iterable[str]] | Iterable[str] | None = None,
        ferramentas: Callable[[], dict] | dict | None = None,
        perfis: Callable[[], Iterable[str]] | Iterable[str] | None = None,
        areas: Iterable[str] | None = None,
        leis: Iterable[str] | dict | None = None,
        medidas=None,
    ) -> None:
        self.pasta = Path(pasta)
        # A4: agentes_medida.Medidas, ou None (sem medida: ninguem precisa de revisao).
        self.medidas = medidas
        self._capacidades = capacidades
        self._ferramentas = ferramentas
        self._perfis = perfis
        self._areas = areas
        self._leis = leis
        self._trava = threading.Lock()

    # ---------------------------------------------------------- catalogos

    def catalogo_capacidades(self) -> list[str]:
        if self._capacidades is None:
            import registro
            from habilidade_base import COM_PROBLEMA

            reg = registro.carregar(Path(__file__).resolve().parent.parent / "habilidades")
            self._capacidades = [h.id for h in reg.habilidades if h.estado != COM_PROBLEMA]
        return sorted(str(c) for c in _chamar(self._capacidades))

    def catalogo_ferramentas(self) -> dict:
        if self._ferramentas is None:
            import ferramentas

            self._ferramentas = lambda: ferramentas.CATALOGO_FERRAMENTAS
        valor = _chamar(self._ferramentas)
        return dict(valor) if isinstance(valor, dict) else {str(n): {} for n in valor}

    def catalogo_perfis(self) -> list[str]:
        if self._perfis is None:
            import modelos

            self._perfis = list(modelos.IDS_TAREFAS)
        return list(_chamar(self._perfis))

    def catalogo_areas(self) -> list[str]:
        if self._areas is None:
            from biblioteca import ficha

            self._areas = list(ficha.AREAS)
        return list(self._areas)

    def catalogo_leis(self) -> dict[str, str]:
        if self._leis is None:
            import leis

            self._leis = {k: v.get("nome", k) for k, v in leis.CODIGOS.items()}
        valor = self._leis
        return dict(valor) if isinstance(valor, dict) else {str(k): str(k) for k in valor}

    def catalogos(self) -> dict:
        """O que um agente pode declarar, para a tela montar o formulario."""
        return {
            "capacidades": self.catalogo_capacidades(),
            "ferramentas": [{"id": n, "descricao": f.get("descricao", ""), "disponivel": f.get("disponivel", True)}
                            for n, f in self.catalogo_ferramentas().items()],
            "perfis": self.catalogo_perfis(), "areas": self.catalogo_areas(),
            "leis": [{"id": k, "nome": v} for k, v in self.catalogo_leis().items()],
            "formatos": list(FORMATOS_SAIDA), "acervo": list(ACERVO_MODOS) + ["pastas"],
        }

    # ---------------------------------------------------------- validar

    def _validar_campos(self, dados: dict, corpo: str) -> tuple[dict, list[str]]:
        """Os campos conferidos contra o formato e os catalogos: (campos, avisos)."""
        erros: list[str] = []
        avisos: list[str] = []
        for k in dados:
            if k not in CAMPOS:
                erros.append(f"o campo '{k}' não faz parte do formato{_sugestao(k, CAMPOS)}; "
                             f"os campos são: {_lista_de(CAMPOS)}")

        nome = _texto(dados.get("nome"), "nome", erros) if dados.get("nome") is not None else ""
        if not nome:
            erros.append("falta o nome (nome: Revisor de contratos)")
        elif len(nome) > MAX_NOME:
            erros.append(f"o nome passa de {MAX_NOME} caracteres")
        descricao = _texto(dados.get("descricao"), "descricao", erros) if dados.get("descricao") is not None else ""
        if not descricao:
            erros.append("falta a descrição (descricao: para que o agente serve, numa frase)")
        elif len(descricao) > MAX_DESCRICAO:
            erros.append(f"a descrição passa de {MAX_DESCRICAO} caracteres")

        qu = _sub(dados.get("quando_usar"), "quando_usar", CAMPOS_QUANDO_USAR, erros)
        quando_usar = {"exemplos": _textos(qu.get("exemplos"), "quando_usar.exemplos", erros),
                       "palavras": _textos(qu.get("palavras"), "quando_usar.palavras", erros)}

        existentes = self.catalogo_capacidades()
        capacidades = _textos(dados.get("capacidades"), "capacidades", erros)
        for c in capacidades:
            if c not in existentes:
                erros.append(f"a capacidade '{c}' não existe{_sugestao(c, existentes)}; "
                             f"as que existem: {_lista_de(existentes)}")

        catalogo = self.catalogo_ferramentas()
        ferramentas = _textos(dados.get("ferramentas"), "ferramentas", erros)
        for f in ferramentas:
            if f not in catalogo:
                erros.append(f"a ferramenta '{f}' não existe no catálogo{_sugestao(f, catalogo)}; "
                             f"as que existem: {_lista_de(sorted(catalogo))}")
            elif catalogo[f].get("disponivel") is False:
                avisos.append(f"a ferramenta '{f}' ainda não faz o trabalho de verdade: confirmar confere os dados "
                              "e diz isso, sem executar")

        fo = _sub(dados.get("fontes"), "fontes", CAMPOS_FONTES, erros)
        acervo = fo.get("acervo", "acervo")
        if isinstance(acervo, dict) and set(acervo) == {"pastas"}:
            pastas = _textos(acervo.get("pastas"), "fontes.acervo.pastas", erros)
            if not pastas:
                erros.append("fontes.acervo.pastas está vazio: ponha as pastas, ou use 'acervo' para o Acervo inteiro")
            acervo = {"pastas": pastas}
        elif acervo not in ACERVO_MODOS:
            erros.append(f"fontes.acervo precisa ser 'acervo', 'documento_em_foco' ou 'pastas: [...]'; veio {acervo!r}")
        areas = self.catalogo_areas()
        por_plano = {_plano(a): a for a in areas}
        biblioteca = []
        for a in _textos(fo.get("biblioteca"), "fontes.biblioteca", erros):
            if _plano(a) in por_plano:
                biblioteca.append(por_plano[_plano(a)])
            else:
                erros.append(f"a área '{a}' não existe na Biblioteca{_sugestao(a, areas)}; as que existem: {_lista_de(areas)}")
        leis = self.catalogo_leis()
        codigos = []
        for lei in _textos(fo.get("leis"), "fontes.leis", erros):
            if lei.lower() in leis:
                codigos.append(lei.lower())
            else:
                erros.append(f"a lei '{lei}' não é conhecida; as que o programa conhece: "
                             + _lista_de(f"{k} ({v})" for k, v in leis.items()))
        fontes = {"acervo": acervo, "biblioteca": biblioteca, "leis": codigos}

        sa = _sub(dados.get("saida"), "saida", CAMPOS_SAIDA, erros)
        formato = str(sa.get("formato") or "texto")
        if formato not in FORMATOS_SAIDA:
            erros.append(f"saida.formato '{formato}' não existe{_sugestao(formato, FORMATOS_SAIDA)}; "
                         f"os formatos são: {_lista_de(FORMATOS_SAIDA)}")
        modelo_doc = _texto(sa["modelo"], "saida.modelo", erros) if sa.get("modelo") is not None else ""
        saida = {"formato": formato, "modelo": modelo_doc}

        perfis = self.catalogo_perfis()
        perfil = str(dados.get("modelo") if dados.get("modelo") is not None else "conversa").strip()
        if perfil not in perfis:
            if RE_NOME_DE_MODELO.search(perfil):
                erros.append(f"'modelo' é o perfil de tarefa, não o nome de um modelo: '{perfil}' parece nome de "
                             f"modelo. Use um destes perfis: {_lista_de(perfis)} (o modelo de cada perfil é "
                             "escolhido nas configurações do programa, e muda com a máquina)")
            else:
                erros.append(f"o perfil de modelo '{perfil}' não existe{_sugestao(perfil, perfis)}; "
                             f"os perfis são: {_lista_de(perfis)}")

        testes = []
        brutos = dados.get("testes") or []
        if not isinstance(brutos, list):
            erros.append("'testes' precisa ser uma lista de '- pergunta: ... / deve_conter: [...]'")
            brutos = []
        for i, t in enumerate(brutos, 1):
            if not isinstance(t, dict):
                erros.append(f"o teste {i} precisa ter 'pergunta' e 'deve_conter'")
                continue
            _sub(t, f"testes[{i}]", CAMPOS_TESTE, erros)
            pergunta = _texto(t.get("pergunta"), f"testes[{i}].pergunta", erros) if t.get("pergunta") is not None else ""
            if not pergunta:
                erros.append(f"o teste {i} não tem pergunta")
            deve = _textos(t.get("deve_conter"), f"testes[{i}].deve_conter", erros)
            if not deve:
                erros.append(f"o teste {i} não diz o que a resposta deve conter (deve_conter: [...])")
            testes.append({"pergunta": pergunta, "deve_conter": deve})

        versao = dados.get("versao", 1)
        if isinstance(versao, bool) or not isinstance(versao, int) or versao < 1:
            erros.append("'versao' precisa ser um número inteiro a partir de 1")
            versao = 1

        if not corpo.strip():
            erros.append("o agente não tem instruções: escreva, embaixo da segunda linha ---, como ele deve trabalhar")

        if erros:
            raise ErroDeAgente("; ".join(erros))
        if not testes:
            avisos.append("sem testes: o Testar não tem o que rodar")
        if not quando_usar["exemplos"] and not quando_usar["palavras"]:
            avisos.append("sem exemplos nem palavras: só será usado quando a pessoa o escolher pelo nome")
        return ({"nome": nome, "descricao": descricao, "quando_usar": quando_usar, "capacidades": capacidades,
                 "ferramentas": ferramentas, "fontes": fontes, "saida": saida, "modelo": perfil,
                 "testes": testes, "versao": versao, "instrucoes": corpo}, avisos)

    def validar(self, markdown: str, slug: str = "") -> Agente:
        """O AGENTE.md conferido, sem gravar nada. Levanta ErroDeAgente."""
        dados, corpo = separar(markdown)
        campos, avisos = self._validar_campos(dados, corpo)
        return Agente(slug=slug or slug_de(campos["nome"]), markdown=markdown.replace("\r\n", "\n"),
                      avisos=avisos, **campos)

    # ---------------------------------------------------------- ler

    def _pasta_de(self, slug: str) -> Path:
        if not isinstance(slug, str) or not RE_SLUG.fullmatch(slug):
            raise ErroDeAgente(f"nome de agente inválido: {slug!r}")
        return self.pasta / slug

    def _estado(self, pasta: Path) -> tuple[dict, str]:
        caminho = pasta / ESTADO
        if not caminho.is_file():
            # Pasta criada a mao, sem passar pelo programa: nasce desligada.
            # Com o original de uma importacao ao lado, continua importada.
            return {"origem": "importado" if (pasta / ORIGINAL).is_file() else "escritorio"}, ""
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
            if not isinstance(dados, dict):
                raise ValueError("não é um objeto")
            return dados, ""
        except (OSError, ValueError) as exc:
            origem = "importado" if (pasta / ORIGINAL).is_file() else "escritorio"
            return {"origem": origem}, f"o estado.json não pôde ser lido ({exc}); o agente ficou desligado"

    def _gravar_estado(self, pasta: Path, dados: dict) -> None:
        temp = pasta / (ESTADO + ".tmp")
        temp.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(pasta / ESTADO)

    def _versoes_de(self, pasta: Path) -> list[int]:
        dir_ = pasta / VERSOES
        if not dir_.is_dir():
            return []
        return sorted(int(p.stem) for p in dir_.glob("*.md") if p.stem.isdigit())

    def _medir(self, agente: Agente, todas: dict | None) -> Agente:
        """A4: a medida guardada deste agente e, se os testes da versao atual falharam, o aviso."""
        if self.medidas is None:
            return agente
        import agentes_medida

        m = (todas if todas is not None else self.medidas.todas()).get(agente.slug) or {}
        agente.medida = agentes_medida.resumo(agente.versao, m)
        if not agente.problema and agentes_medida.precisa_revisao(agente.versao, m):
            agente.precisa_revisao = True
            agente.revisao_motivo = agentes_medida.motivo_da_revisao(m)
        return agente

    def _carregar(self, pasta: Path, todas: dict | None = None) -> Agente:
        return self._medir(self._carregar_arquivo(pasta), todas)

    def _carregar_arquivo(self, pasta: Path) -> Agente:
        estado, aviso_estado = self._estado(pasta)
        agente = Agente(slug=pasta.name, arquivo=str(pasta / ARQUIVO), versoes=self._versoes_de(pasta))
        agente.ativo = bool(estado.get("ativo")) and not aviso_estado
        origem = estado.get("origem")
        agente.origem = origem if origem in ORIGENS else "escritorio"
        for chave in ("aprovado_em", "aprovado_por", "importado_em", "atualizado_em"):
            setattr(agente, chave, str(estado.get(chave) or ""))
        agente.suspeitas = [str(s) for s in estado.get("suspeitas") or []]
        agente.ignorados_na_importacao = [str(s) for s in estado.get("ignorados_na_importacao") or []]
        if aviso_estado:
            agente.avisos.append(aviso_estado)

        caminho = pasta / ARQUIVO
        if not caminho.is_file():
            agente.problema = f"a pasta não tem o arquivo {ARQUIVO}"
            return agente
        try:
            agente.markdown = caminho.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            agente.problema = f"não consegui ler o {ARQUIVO} ({exc.__class__.__name__}); salve o arquivo em UTF-8"
            return agente
        try:
            dados, corpo = separar(agente.markdown)
            campos, avisos = self._validar_campos(dados, corpo)
        except ErroDeAgente as exc:
            agente.problema = str(exc)
            # O que der para ler do cabecalho ajuda a tela a mostrar quem e.
            try:
                d, _ = separar(agente.markdown)
                agente.nome = str(d.get("nome") or d.get("name") or "")
            except ErroDeAgente:
                pass
            return agente
        for k, v in campos.items():
            setattr(agente, k, v)
        agente.avisos = avisos + agente.avisos
        return agente

    def listar(self) -> list[Agente]:
        """Todos, os com problema tambem, no fim: um arquivo quebrado aparece com o motivo."""
        if not self.pasta.is_dir():
            return []
        agentes = []
        # As medidas uma vez so, para a lista inteira.
        todas = self.medidas.todas() if self.medidas is not None else None
        for p in sorted(self.pasta.iterdir()):
            if not p.is_dir() or p.name.startswith((".", "_")):
                continue
            if RE_SLUG.fullmatch(p.name):
                agentes.append(self._carregar(p, todas))
            else:
                # Pasta criada a mao com espaco ou ponto no nome: aparece, com
                # o motivo, em vez de sumir da lista.
                agentes.append(Agente(slug=p.name, arquivo=str(p / ARQUIVO),
                                      problema="o nome da pasta só pode ter letras, números e hífen "
                                               f"(ex.: {slug_de(p.name)})"))
        return sorted(agentes, key=lambda a: (bool(a.problema), _plano(a.nome or a.slug)))

    def ativos(self) -> list[Agente]:
        """Os que a conversa pode usar (A2): ligados, sem problema e, se importados, aprovados."""
        return [a for a in self.listar() if a.em_uso]

    def obter(self, slug: str) -> Agente | None:
        pasta = self._pasta_de(slug)
        return self._carregar(pasta) if pasta.is_dir() else None

    def _exigir(self, slug: str) -> Agente:
        agente = self.obter(slug)
        if agente is None:
            raise AgenteNaoEncontrado(f"não existe agente '{slug}'")
        return agente

    def ler(self, slug: str) -> dict:
        """A ficha, o markdown inteiro e, se importado, o original como veio."""
        agente = self._exigir(slug)
        saida = {"ficha": agente.ficha(), "markdown": agente.markdown}
        original = self.pasta / slug / ORIGINAL
        if original.is_file():
            saida["original"] = original.read_text(encoding="utf-8")
        return saida

    def versoes(self, slug: str) -> list[dict]:
        self._exigir(slug)
        pasta = self._pasta_de(slug)
        saida = []
        for n in self._versoes_de(pasta):
            arq = pasta / VERSOES / f"{n}.md"
            saida.append({"versao": n, "guardada_em": datetime.fromtimestamp(arq.stat().st_mtime).isoformat(timespec="seconds")})
        return saida

    def ler_versao(self, slug: str, n: int) -> str:
        arq = self._pasta_de(slug) / VERSOES / f"{int(n)}.md"
        if not arq.is_file():
            raise AgenteNaoEncontrado(f"o agente '{slug}' não tem a versão {n} guardada")
        return arq.read_text(encoding="utf-8")

    # ---------------------------------------------------------- gravar

    @staticmethod
    def _escrever(caminho: Path, texto: str) -> None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        temp = caminho.with_name(caminho.name + ".tmp")
        with open(temp, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
        temp.replace(caminho)

    def criar(self, markdown: str, *, origem: str = "escritorio") -> Agente:
        """Um agente novo, desligado. O nome da pasta sai do nome do agente."""
        novo = self.validar(markdown)
        with self._trava:
            pasta = self._pasta_de(novo.slug)
            if pasta.exists():
                raise ConflitoDeAgente(f"já existe um agente com esse nome (pasta '{novo.slug}'); "
                                   "edite o que existe ou escolha outro nome")
            self._escrever(pasta / ARQUIVO, novo.markdown)
            agora = _agora()
            self._gravar_estado(pasta, {"ativo": False, "origem": origem if origem in ORIGENS else "escritorio",
                                        "criado_em": agora, "atualizado_em": agora})
        return self._exigir(novo.slug)

    def salvar(self, slug: str, markdown: str) -> Agente:
        """
        Grava a edicao e guarda a anterior em versoes/<n>.md. A versao do texto
        novo e a seguinte, qualquer que seja a que veio escrita: e o programa
        que conta, para duas edicoes nunca dizerem o mesmo numero.
        """
        with self._trava:
            atual = self._exigir(slug)
            texto = markdown.replace("\r\n", "\n")
            self.validar(texto, slug)  # recusa antes de mexer em qualquer coisa
            pasta = self._pasta_de(slug)
            guardadas = self._versoes_de(pasta)
            base = atual.versao if not atual.problema else (max(guardadas) + 1 if guardadas else 1)
            # Editada a mao sem subir a versao, a atual ja pode estar guardada
            # com esse numero: guarda com o proximo livre, sem sobrescrever.
            n_guardada = base if base not in guardadas else max(guardadas) + 1
            nova = max(base, n_guardada) + 1
            if (pasta / ARQUIVO).is_file():
                self._escrever(pasta / VERSOES / f"{n_guardada}.md", (pasta / ARQUIVO).read_text(encoding="utf-8"))
            self._escrever(pasta / ARQUIVO, _com_versao(texto, nova))
            estado, _ = self._estado(pasta)
            estado["atualizado_em"] = _agora()
            self._gravar_estado(pasta, estado)
        return self._exigir(slug)

    def ativar(self, slug: str, *, vi_o_conteudo: bool = False, por: str = "") -> Agente:
        """
        Liga o agente. Importado e ainda nao aprovado so liga com a
        confirmacao de que o titular viu o conteudo inteiro e as ferramentas
        pedidas; a aprovacao fica guardada, com quem e quando.
        """
        with self._trava:
            agente = self._exigir(slug)
            if agente.problema:
                raise ConflitoDeAgente(f"o agente está com problema e não pode ser ligado: {agente.problema}")
            pasta = self._pasta_de(slug)
            estado, _ = self._estado(pasta)
            if agente.precisa_aprovar:
                if vi_o_conteudo is not True:
                    pedidas = _lista_de(agente.ferramentas) if agente.ferramentas else "nenhuma"
                    raise ConflitoDeAgente("este agente foi importado: antes de ligar, leia o conteúdo inteiro e as "
                                       f"ferramentas que ele pede ({pedidas}) e confirme com vi_o_conteudo")
                estado["aprovado_em"] = _agora()
                estado["aprovado_por"] = por or "janela do escritório"
            estado["ativo"] = True
            estado["atualizado_em"] = _agora()
            self._gravar_estado(pasta, estado)
        return self._exigir(slug)

    def desativar(self, slug: str) -> Agente:
        with self._trava:
            self._exigir(slug)
            pasta = self._pasta_de(slug)
            estado, _ = self._estado(pasta)
            estado["ativo"] = False
            estado["atualizado_em"] = _agora()
            self._gravar_estado(pasta, estado)
        return self._exigir(slug)

    def importar(self, texto: str, *, nome_arquivo: str = "") -> Agente:
        """
        Um SKILL.md ou AGENTE.md de fora. `name`/`description` viram
        `nome`/`descricao`; campos de outro programa (license, allowed-tools...)
        saem do cabecalho e ficam listados na ficha, nunca somem calados. O
        original fica em original.md, para o titular ler como veio.
        """
        import blindagem

        texto = (texto or "").lstrip("\ufeff").replace("\r\n", "\n")
        dados, corpo = separar(texto)
        mapeados: dict[str, Any] = {}
        ignorados: list[str] = []
        for k, v in dados.items():
            destino = k if k in CAMPOS else MAPA_IMPORTACAO.get(k)
            if destino is None:
                resumo = json.dumps(v, ensure_ascii=False, default=str)
                ignorados.append(f"{k}: {resumo[:120]}")
            elif destino not in mapeados or k in CAMPOS:
                # Com `nome` e `name` juntos, vale o do formato.
                mapeados[destino] = v
        mapeados.setdefault("versao", 1)
        if not ignorados and all(k in CAMPOS for k in dados) and "versao" in dados:
            convertido = texto  # ja esta no formato: fica como veio, com os comentarios
        else:
            ordem = {k: mapeados[k] for k in CAMPOS if k in mapeados}
            convertido = ("---\n" + yaml.safe_dump(ordem, allow_unicode=True, sort_keys=False, width=1000)
                          + "---\n\n" + corpo + "\n")
        novo = self.validar(convertido)
        with self._trava:
            slug, n = novo.slug, 2
            while self._pasta_de(slug).exists():
                slug, n = f"{novo.slug[:56]}-{n}", n + 1
            pasta = self._pasta_de(slug)
            self._escrever(pasta / ORIGINAL, texto)
            self._escrever(pasta / ARQUIVO, convertido)
            agora = _agora()
            self._gravar_estado(pasta, {
                "ativo": False, "origem": "importado", "importado_em": agora, "nome_arquivo": nome_arquivo,
                "criado_em": agora, "atualizado_em": agora,
                # Texto de fora e dado ate a aprovacao: o que nele parece
                # ordem ao assistente fica aqui, para a tela mostrar.
                "suspeitas": blindagem.suspeitas(texto), "ignorados_na_importacao": ignorados,
            })
        return self._exigir(slug)

    # ---------------------------------------------------------- testar

    def testar(self, slug: str, rodar: Callable[[str, Agente], str]) -> dict:
        """
        Roda os `testes` do agente com `rodar(pergunta, agente) -> texto`. Nenhuma
        ferramenta e executada aqui: quem chama decide o caminho da resposta, e
        o teste so confere o texto.
        """
        agente = self._exigir(slug)
        if agente.problema:
            raise ConflitoDeAgente(f"corrija o agente antes de testar: {agente.problema}")
        return rodar_testes(agente, rodar)


def _com_versao(texto: str, n: int) -> str:
    """O texto com `versao: n` no cabecalho; o resto, comentarios inclusive, como veio."""
    linhas = texto.split("\n")
    fim = next(i for i in range(1, len(linhas)) if linhas[i].strip() in ("---", "..."))
    for i in range(1, fim):
        casou = RE_VERSAO.match(linhas[i])
        if casou:
            linhas[i] = f"{casou.group(1)} {n}{casou.group(2) or ''}"
            return "\n".join(linhas)
    linhas.insert(fim, f"versao: {n}")
    return "\n".join(linhas)


def rodar_testes(agente: Agente, rodar: Callable[[str, Agente], str]) -> dict:
    """Cada teste: passou se a resposta contem tudo de `deve_conter` (sem diferenca de acento e maiuscula)."""
    resultados = []
    for t in agente.testes:
        comeco = time.monotonic()
        erro = ""
        try:
            resposta = str(rodar(t["pergunta"], agente) or "")
        except Exception as exc:  # noqa: BLE001 - um teste que quebra e um teste que falhou
            resposta, erro = "", str(exc) or exc.__class__.__name__
        plano = _plano(resposta)
        faltou = [x for x in t["deve_conter"] if _plano(x) not in plano]
        resultados.append({"pergunta": t["pergunta"], "deve_conter": t["deve_conter"], "passou": not erro and not faltou,
                           "faltou": faltou if not erro else list(t["deve_conter"]), "erro": erro,
                           "resposta": resposta, "segundos": round(time.monotonic() - comeco, 1)})
    return {"slug": agente.slug, "versao": agente.versao, "total": len(resultados),
            "passaram": sum(1 for r in resultados if r["passou"]), "resultados": resultados}


__all__ = ["Agente", "AgenteNaoEncontrado", "Agentes", "ConflitoDeAgente", "ErroDeAgente", "rodar_testes", "separar", "slug_de"]
