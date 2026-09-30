"""
PAULUS - O que a tela "Agentes" precisa do servidor (A3).

A tela (frontend/js/56-agentes.js) lista, mostra, testa e edita os agentes
pelas rotas da A1 (src/rotas_agentes.py). Aqui fica o que a A1 nao tinha:

- **os dois agentes de exemplo** que vem com o produto ("Revisor de
  contratos" e "Triagem de consumidor"), em `config/agentes/<slug>/`. Na
  abertura do programa, cada um e copiado para `data/agentes/` UMA vez,
  desligado e com origem "produto". A lista do que ja foi copiado fica em
  `data/agentes/.exemplos.json`: um exemplo que o escritorio editou nao e
  sobrescrito, e um que ele apagou da pasta nao volta sozinho;
- **o formulario vira AGENTE.md** (`markdown_do_formulario`), com o YAML
  escrito pelo PyYAML - aspas, dois-pontos e acentos certos sem a pessoa
  saber o que e YAML - e conferido pela validacao da A1 antes de gravar;
- **"Criar agente a partir desta conversa"** (`rascunho_da_conversa`), por
  regra e sem modelo: as perguntas da pessoa viram os exemplos, as palavras
  que mais se repetem nelas viram as palavras, o titulo da conversa vira o
  nome. Nada e gravado: a rota so devolve o rascunho, e a tela abre o
  formulario preenchido; quem grava e o "Criar agente" da pessoa (a rota de
  criar da A1).

Rotas (as tres so conferem e devolvem; nenhuma grava):

  POST /api/agentes/formulario                {campos} -> {markdown, valido, erro, avisos}
  POST /api/agentes/validar                   {markdown} -> {valido, erro, avisos, ficha}
  GET  /api/agentes/da-conversa/{trabalho_id} o rascunho, com o markdown e a validacao
"""

from __future__ import annotations

import json
import re
import shutil
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

import yaml
from fastapi import HTTPException

import agentes as agentes_mod

RAIZ = Path(__file__).resolve().parent.parent
EXEMPLOS = RAIZ / "config" / "agentes"
MARCA_EXEMPLOS = ".exemplos.json"

# Do rascunho da conversa: quantos exemplos e palavras, no maximo. Seis
# exemplos cobrem uma conversa comprida sem virar a conversa inteira; cinco
# palavras bastam para a regra (uma ja faz o agente candidato, A2).
MAX_EXEMPLOS = 6
MAX_PALAVRAS = 5
MAX_EXEMPLO = 160

# Palavras que toda pergunta tem e nao dizem nada do assunto. Somam-se as da
# A2 (artigos, preposicoes); estas sao as de pergunta e pedido.
PALAVRAS_DE_PERGUNTA = {
    "qual", "quais", "quanto", "quantos", "quanta", "quantas", "como", "onde", "quando", "quem", "porque", "porquê",
    "sobre", "tem", "tenho", "temos", "ha", "há", "ser", "são", "sao", "foi", "era", "está", "esta", "estão", "pode",
    "posso", "podemos", "fazer", "faça", "faz", "me", "mim", "diga", "diz", "dizer", "mostre", "mostra", "quero",
    "preciso", "gostaria", "favor", "obrigado", "obrigada", "ele", "ela", "eles", "elas", "isso", "aqui", "ali",
    "mais", "menos", "muito", "pouco", "também", "tambem", "já", "ainda", "sim", "não", "nao", "seu", "sua", "seus",
    "suas", "dele", "dela", "nos", "nas", "aos", "às", "pelo", "pela", "pelos", "pelas", "num", "numa", "entre",
    "até", "ate", "depois", "antes", "agora", "hoje", "então", "entao", "algum", "alguma", "algo", "tudo", "todo",
    "toda", "todos", "todas", "cada", "outro", "outra", "mesmo", "mesma", "deve", "devo", "devemos", "vai", "vou",
}


def _plano(texto: str) -> str:
    normal = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in normal if unicodedata.category(c) != "Mn")


# ------------------------------------------------------------ os exemplos

def semear_exemplos(agentes: agentes_mod.Agentes, origem: Path | str = EXEMPLOS) -> list[str]:
    """
    Copia para a pasta dos agentes os exemplos do produto que ainda nao foram
    copiados. Devolve os slugs copiados agora. Uma pasta que ja existe com o
    mesmo nome e do escritorio: fica como esta, e o exemplo conta como
    entregue.
    """
    origem = Path(origem)
    if not origem.is_dir():
        return []
    destino = agentes.pasta
    marca = destino / MARCA_EXEMPLOS
    try:
        entregues = set(json.loads(marca.read_text(encoding="utf-8")).get("entregues") or [])
    except (OSError, ValueError, AttributeError):
        entregues = set()
    copiados = []
    for pasta in sorted(origem.iterdir()):
        arquivo = pasta / agentes_mod.ARQUIVO
        if not pasta.is_dir() or not arquivo.is_file() or pasta.name in entregues:
            continue
        alvo = destino / pasta.name
        if not alvo.exists():
            alvo.mkdir(parents=True)
            shutil.copyfile(arquivo, alvo / agentes_mod.ARQUIVO)
            agora = datetime.now().isoformat(timespec="seconds")
            (alvo / agentes_mod.ESTADO).write_text(json.dumps(
                {"ativo": False, "origem": "produto", "criado_em": agora, "atualizado_em": agora},
                ensure_ascii=False, indent=2), encoding="utf-8")
            copiados.append(pasta.name)
        entregues.add(pasta.name)
    if copiados or not marca.exists():
        destino.mkdir(parents=True, exist_ok=True)
        marca.write_text(json.dumps({"entregues": sorted(entregues)}, ensure_ascii=False, indent=2), encoding="utf-8")
    return copiados


# ------------------------------------------------------ formulario -> markdown

def _linhas(valor) -> list[str]:
    """Uma lista de textos, venha como lista ou como texto com uma linha por item."""
    if valor is None:
        return []
    itens = valor if isinstance(valor, list) else str(valor).splitlines()
    return [str(x).strip() for x in itens if str(x).strip()]


def _virgulas(valor) -> list[str]:
    """Palavras: lista, ou texto separado por virgula, ponto e virgula ou linha."""
    if valor is None:
        return []
    itens = valor if isinstance(valor, list) else re.split(r"[,;\n]", str(valor))
    vistos, saida = set(), []
    for x in itens:
        x = str(x).strip()
        if x and _plano(x) not in vistos:
            vistos.add(_plano(x))
            saida.append(x)
    return saida


def cabecalho_do_formulario(campos: dict) -> dict:
    """Os campos da tela no formato do AGENTE.md (§2.6), na ordem do formato."""
    c = campos or {}
    acervo = str(c.get("acervo") or "acervo")
    fontes: dict = {"acervo": {"pastas": _linhas(c.get("pastas"))} if acervo == "pastas" else acervo}
    # O formulario nao mostra biblioteca nem leis; editar pelo formulario um
    # agente que as tem nao pode apagá-las: vem de volta como veio.
    for chave in ("biblioteca", "leis"):
        if _virgulas(c.get(chave)):
            fontes[chave] = _virgulas(c.get(chave))
    saida: dict = {"formato": str(c.get("formato") or "texto")}
    if str(c.get("saida_modelo") or "").strip():
        saida["modelo"] = str(c["saida_modelo"]).strip()
    testes = []
    for t in c.get("testes") or []:
        if not isinstance(t, dict):
            continue
        pergunta, deve = str(t.get("pergunta") or "").strip(), _virgulas(t.get("deve_conter"))
        if pergunta or deve:
            testes.append({"pergunta": pergunta, "deve_conter": deve})
    try:
        versao = max(1, int(c.get("versao") or 1))
    except (TypeError, ValueError):
        versao = 1
    cab = {
        "nome": str(c.get("nome") or "").strip(),
        "descricao": str(c.get("descricao") or "").strip(),
        "quando_usar": {"exemplos": _linhas(c.get("exemplos")), "palavras": _virgulas(c.get("palavras"))},
        "capacidades": _virgulas(c.get("capacidades")) or ["perguntar"],
        "ferramentas": _virgulas(c.get("ferramentas")),
        "fontes": fontes,
        "saida": saida,
        "modelo": str(c.get("modelo") or "conversa").strip(),
    }
    if testes:
        cab["testes"] = testes
    cab["versao"] = versao
    return cab


def markdown_do_formulario(campos: dict) -> str:
    """O AGENTE.md que o formulario grava: o cabecalho YAML e as instrucoes embaixo."""
    cab = cabecalho_do_formulario(campos)
    texto = yaml.safe_dump(cab, allow_unicode=True, sort_keys=False, width=1000, default_flow_style=False)
    instrucoes = str((campos or {}).get("instrucoes") or "").replace("\r\n", "\n").strip()
    return "---\n" + texto + "---\n\n" + instrucoes + "\n"


def conferir(agentes: agentes_mod.Agentes, markdown: str) -> dict:
    """A validacao da A1, sem gravar: o erro em portugues, ou a ficha e os avisos."""
    try:
        a = agentes.validar(markdown)
    except agentes_mod.ErroDeAgente as exc:
        return {"valido": False, "erro": str(exc), "avisos": [], "ficha": None}
    return {"valido": True, "erro": "", "avisos": a.avisos, "ficha": a.ficha(), "slug": a.slug}


# -------------------------------------------------- a partir de uma conversa

def _perguntas(trabalho) -> list[str]:
    return [str(m.texto or "").strip() for m in getattr(trabalho, "mensagens", []) or []
            if getattr(m, "autor", "") == "pessoa" and str(m.texto or "").strip()]


def _sem_arroba(texto: str) -> str:
    """"@Revisor revise..." -> "revise...": o exemplo e o pedido, nao a escolha do agente."""
    return re.sub(r"(?:^|\s)@\S+", " ", texto).strip()


def rascunho_da_conversa(trabalho) -> dict:
    """
    Os campos do formulario sugeridos pela conversa, por regra:

    - exemplos: as perguntas da pessoa, na ordem, sem repetir e sem as de uma
      palavra so ("sim", "obrigado"), no maximo seis;
    - palavras: as que mais se repetem nas perguntas (sem acento na conta,
      com o acento da primeira vez que apareceram), sem as de toda pergunta;
      empate, vale a que apareceu primeiro;
    - nome: o titulo da conversa; descricao e instrucoes, uma frase que diz
      de onde o agente veio e os pedidos que ele atende - para a pessoa
      escrever por cima.
    """
    from agente_na_conversa import PALAVRAS_VAZIAS

    perguntas = [_sem_arroba(p) for p in _perguntas(trabalho)]
    exemplos, vistos = [], set()
    for p in perguntas:
        curta = " ".join(p.split())[:MAX_EXEMPLO].strip()
        chave = _plano(curta).strip(" ?.!")
        if len(curta.split()) < 2 or chave in vistos:
            continue
        vistos.add(chave)
        exemplos.append(curta)
        if len(exemplos) >= MAX_EXEMPLOS:
            break

    contagem: Counter = Counter()
    primeira: dict[str, tuple[int, str]] = {}
    ordem = 0
    for p in perguntas:
        for palavra in re.findall(r"[^\W\d_]+(?:-[^\W\d_]+)*", p.lower()):
            plano = _plano(palavra)
            if len(plano) < 4 or plano in PALAVRAS_VAZIAS or palavra in PALAVRAS_DE_PERGUNTA or plano in PALAVRAS_DE_PERGUNTA:
                continue
            contagem[plano] += 1
            if plano not in primeira:
                primeira[plano] = (ordem, palavra)
                ordem += 1
    melhores = sorted(contagem, key=lambda w: (-contagem[w], primeira[w][0]))[:MAX_PALAVRAS]
    palavras = [primeira[w][1] for w in melhores]

    titulo = str(getattr(trabalho, "titulo", "") or "").strip()
    if not titulo or titulo == "Nova conversa":
        titulo = "Agente da conversa"
    nome = titulo[:agentes_mod.MAX_NOME].strip()
    lista = "\n".join(f"- {e}" for e in exemplos) or "- (escreva aqui um pedido de exemplo)"
    instrucoes = (
        "## Como trabalhar\n"
        f"Este agente nasceu da conversa “{titulo}”. Ele atende pedidos como estes:\n\n"
        f"{lista}\n\n"
        "Responda com o que os documentos dizem, citando o documento e a página. Quando eles não disserem, "
        "diga que não encontrou.\n\n"
        "(Escreva aqui, com as palavras do escritório, o jeito da casa de fazer este trabalho.)"
    )
    return {
        "nome": nome,
        "descricao": f"Atende pedidos como os da conversa “{titulo}”.",
        "exemplos": exemplos, "palavras": palavras,
        "acervo": "acervo", "pastas": [], "formato": "texto", "ferramentas": [], "capacidades": ["perguntar"],
        "modelo": "conversa", "instrucoes": instrucoes, "testes": [], "versao": 1,
    }


# ------------------------------------------------------------------ rotas

def montar(estado, app) -> None:
    """Depois de rotas_agentes.montar: usa o `estado.agentes` que ela cria."""
    try:
        semear_exemplos(estado.agentes)
    except OSError:
        # Pasta de dados sem escrita: o programa abre sem os exemplos.
        pass

    @app.post("/api/agentes/formulario")
    def agentes_formulario(payload: dict | None = None) -> dict:
        """O AGENTE.md que os campos gravariam, e a validacao dele. Nao grava."""
        campos = (payload or {}).get("campos")
        if not isinstance(campos, dict):
            raise HTTPException(status_code=400, detail="mande os campos do formulário em 'campos'")
        md = markdown_do_formulario(campos)
        return {"markdown": md, **conferir(estado.agentes, md)}

    @app.post("/api/agentes/validar")
    def agentes_validar(payload: dict | None = None) -> dict:
        """A validacao da A1 sobre o markdown escrito a mao, antes de salvar."""
        md = (payload or {}).get("markdown")
        if not isinstance(md, str):
            raise HTTPException(status_code=400, detail="mande o conteúdo do AGENTE.md em 'markdown'")
        return conferir(estado.agentes, md)

    @app.get("/api/agentes/da-conversa/{trabalho_id}")
    def agentes_da_conversa(trabalho_id: str) -> dict:
        """O rascunho de um agente a partir da conversa. So sugere: nada e gravado."""
        trabalho = estado.trabalhos.obter(trabalho_id)
        if trabalho is None:
            raise HTTPException(status_code=404, detail="conversa não encontrada")
        campos = rascunho_da_conversa(trabalho)
        md = markdown_do_formulario(campos)
        return {"campos": campos, "markdown": md, "conversa": {"id": trabalho.id, "titulo": trabalho.titulo},
                "perguntas": len(_perguntas(trabalho)), **conferir(estado.agentes, md)}


__all__ = ["cabecalho_do_formulario", "conferir", "markdown_do_formulario", "rascunho_da_conversa", "semear_exemplos"]
