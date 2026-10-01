"""
Criar um agente pela conversa (pacote de telas de 01/10/2026, `Conversa -
Criar agente`, docs/PLANO-TELAS-ASSISTENTE.md, T3).

"Crie um agente que preencha a procuracao ad judicia a partir dos documentos
do cliente" vira, em tres passos:

1. a regra le o pedido e acha no Acervo os documentos que podem ser o MODELO
   (o nome do arquivo tem as palavras do pedido; "modelo" no nome conta mais);
   a conversa faz tres perguntas - qual modelo, o que fazer quando faltar um
   dado, em que formato entregar;
2. com as respostas, a regra le o modelo escolhido e conta os campos em branco
   (`____`, `[ ]`, `{{ }}`, `xxx`, "(nome)" ...);
3. o modelo local escreve o nome, a descricao, as instrucoes e os exemplos,
   em JSON. As respostas da pessoa entram nas instrucoes POR REGRA - o que ela
   decidiu nao depende do modelo lembrar.

Nada e gravado aqui: o rascunho vai para a coluna da direita, e quem grava e
o "Salvar agente" (POST /api/agentes, a validacao de sempre).
"""

from __future__ import annotations

import re
import unicodedata

RE_PEDIDO = re.compile(
    r"^(?:(?:por|favor|pode|poderia|voce|vc|me|quero|preciso|agora|ai|entao|ja|que|e)\s+)*"
    r"(?:crie|criar|cria|monte|montar|monta|faca|fazer|faz|configure|configurar)\s+"
    r"(?:(?:um|uma|o|meu)\s+)?(?:novo\s+)?agente\b\s*(?:que|para|pra|de|capaz de)?\s*(.*)$")

GENERICAS = {"agente", "documento", "documentos", "cliente", "clientes", "partir", "dados", "arquivo", "arquivos",
             "preencha", "preencher", "faca", "fazer", "crie", "criar", "acompanhe", "acompanhar", "revise",
             "revisar", "leia", "ler", "monte", "montar", "entrada", "acervo", "todos", "todas", "sempre"}

# Os jeitos de deixar campo em branco num modelo de documento.
RE_BRANCO = re.compile(r"_{3,}|\[\s*[^\]]{0,30}\]|\{\{[^}]{0,40}\}\}|\bx{3,}\b|\((?:nome|cpf|cnpj|rg|endere[cç]o|"
                       r"nacionalidade|estado civil|profiss[aã]o|data|valor|cidade)[^)]{0,20}\)", re.I)

FALTANDO = {
    "perguntar": "Se algum campo continuar sem dado, liste os que faltam e peça a informação. Não entregue com "
                 "lacunas, a menos que a pessoa diga para seguir.",
    "marcar": "Se algum campo continuar sem dado, entregue assim mesmo e marque cada lacuna com [FALTA: o que é], "
              "para a pessoa completar.",
}
ROTULO_FALTANDO = {"perguntar": "Perguntar antes de entregar", "marcar": "Entregar marcando o que falta"}
ROTULO_FORMATO = {"modelo_de_documento": "Documento Word", "texto": "Texto na conversa", "lista": "Lista",
                  "tabela": "Tabela"}

SISTEMA = (
    "Você escreve a ficha de um agente de um escritório de advocacia brasileiro: um assistente que faz sempre o "
    "mesmo trabalho. Recebe o pedido de quem quer o agente e, se houver, o começo do modelo de documento que ele "
    "usa. Responda só com JSON. Escreva em português do Brasil, frases curtas e imperativas. Não invente lei, "
    "número de artigo nem dado de cliente."
)
ESQUEMA = ('{"nome": "nome curto do agente, 2 a 4 palavras", "descricao": "uma frase do que ele faz", '
           '"instrucoes": ["passo 1", "passo 2", "..."], "exemplos": ["pedido de exemplo 1", "pedido de exemplo 2"], '
           '"palavras": ["palavra", "palavra"]}')


def _passo_limpo(x) -> str:
    """O passo sem o numero que o modelo as vezes escreve dentro ("1. Leia...")."""
    return re.sub(r"^\s*(?:\d+\s*[.)\-:]\s*|[-*\u2022]\s+)+", "", " ".join(str(x).split())).strip()


def _chave(texto: str) -> str:
    """Para comparar passos: sem acento, sem pontuacao, o comeco da frase."""
    return re.sub(r"[^a-z0-9 ]", "", _plano(_passo_limpo(texto)))[:48].strip()


def _parecido(chave: str, chaves) -> bool:
    """O mesmo passo com outras palavras no fim: um comeca como o outro."""
    return any(chave == c or (min(len(chave), len(c)) >= 20 and (chave.startswith(c) or c.startswith(chave))) for c in chaves)


def _plano(texto: str) -> str:
    sem = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sem.lower()).strip()


def ler_pedido(texto: str) -> str | None:
    """O que o agente deve fazer, quando a frase pede um agente; senao None."""
    m = RE_PEDIDO.search(_plano(texto))
    if not m:
        return None
    resto = m.group(1).strip(" .!?")
    if len(resto.split()) < 2:
        return None
    # Devolve o pedido com os acentos de quem escreveu.
    original = " ".join(str(texto or "").split()).strip(" .!?")
    corte = len(original) - len(resto)
    return original[max(0, corte):].strip(" .!?") or resto


def candidatos_de_modelo(pedido: str, documentos, limite: int = 3) -> list[str]:
    """Os documentos do Acervo que podem ser o modelo: as palavras do pedido no nome."""
    palavras = [p for p in re.findall(r"[a-z0-9]{4,}", _plano(pedido)) if p not in GENERICAS]
    if not palavras:
        return []
    notas = []
    for doc in documentos or []:
        nome = getattr(doc, "name", "") or (doc if isinstance(doc, str) else "")
        plano = _plano(nome)
        acertos = sum(1 for p in palavras if p in plano)
        if not acertos:
            continue
        nota = acertos * 10 + (6 if "modelo" in plano else 0) + (3 if plano.endswith(".docx") else 0)
        notas.append((nota, nome))
    notas.sort(key=lambda x: (-x[0], x[1]))
    return [n for _, n in notas[:limite]]


def campos_em_branco(texto: str) -> int:
    return len(RE_BRANCO.findall(texto or ""))


def nome_por_regra(pedido: str) -> str:
    """'preencha a procuracao ad judicia...' -> 'Preenchedor de procuração'. Sem verbo conhecido, o pedido curto."""
    p = _plano(pedido)
    verbos = {"preench": "Preenchedor", "revis": "Revisor", "acompanh": "Acompanhamento", "resum": "Resumidor",
              "redij": "Redator", "redig": "Redator", "escrev": "Redator", "confer": "Conferente", "calcul": "Calculadora"}
    for raiz, nome in verbos.items():
        m = re.search(r"\b" + raiz + r"\w*\s+(?:(?:a|o|as|os|um|uma|da|do|de)\s+)?([a-z]+)", p)
        if m:
            coisa = m.group(1)
            # A palavra com o acento de quem escreveu ("procuração", nao "procuracao").
            palavra = next((w.strip(".,;:!?") for w in pedido.split() if _plano(w.strip(".,;:!?")) == coisa), coisa)
            return f"{nome} de {palavra.lower()}"[:60]
    palavras = pedido.split()
    return (" ".join(palavras[:4]).capitalize() or "Novo agente")[:60]


def rascunho(pedido: str, modelo: str = "", faltando: str = "perguntar", formato: str = "",
             brancos: int = 0) -> dict:
    """Os campos do formulario, so por regra (o que vale mesmo sem o modelo de IA)."""
    formato = formato if formato in ROTULO_FORMATO else ("modelo_de_documento" if modelo else "texto")
    if formato == "modelo_de_documento" and not modelo:
        formato = "texto"
    passos = []
    if modelo:
        passos.append(f"Use o modelo “{modelo}”."
                      + (f" Ele tem {brancos} campo{'s' if brancos != 1 else ''} em branco para preencher." if brancos else ""))
    passos.append("Leia os documentos do cliente no Acervo e tire de lá cada dado, com o documento e a página de onde veio.")
    passos.append("Quando dois documentos trouxerem o mesmo dado de forma diferente, não escolha: mostre as duas "
                  "versões e pergunte qual vale.")
    passos.append(FALTANDO.get(faltando, FALTANDO["perguntar"]))
    if formato == "modelo_de_documento":
        passos.append("Entregue o documento Word com os campos preenchidos e o restante do modelo intocado.")
    nome = nome_por_regra(pedido)
    descricao = pedido[:1].upper() + pedido[1:240]
    return {
        "nome": nome, "descricao": descricao, "exemplos": [pedido[:160]], "palavras": [],
        "acervo": "acervo", "pastas": [], "formato": formato, "saida_modelo": modelo if formato == "modelo_de_documento" else "",
        "ferramentas": [], "capacidades": ["perguntar"], "modelo": "conversa",
        "instrucoes": instrucoes_em_markdown(nome, descricao, passos), "testes": [], "versao": 1,
        "passos": passos,
    }


def instrucoes_em_markdown(nome: str, descricao: str, passos: list[str]) -> str:
    linhas = "\n".join(f"{i}. {p}" for i, p in enumerate(passos, 1))
    return f"# {nome}\n\n{descricao}\n\n## Instruções\n\n{linhas}\n"


MUDAR_SISTEMA = (
    "Você ajusta as instruções de um agente de um escritório de advocacia brasileiro. Recebe as instruções numeradas "
    "e o pedido de mudança. Devolva TODAS as instruções, já com a mudança, em JSON. Mude só o que o pedido pede; "
    "não invente lei nem dado de cliente."
)


def mudar(passos: list[str], pedido: str, fixos: list[str], perguntar_json) -> list[str] | None:
    """
    As instrucoes com a mudanca pedida na conversa ("acrescente o CPF do
    conjuge"). As que a pessoa decidiu nas tres perguntas (`fixos`) ficam,
    mesmo que o modelo as tire. Sem JSON util, None.
    """
    contexto = "Instruções:\n" + "\n".join(f"{i}. {p}" for i, p in enumerate(passos, 1)) + f"\n\nPedido de mudança: {pedido}"
    try:
        r = perguntar_json("Aplique o pedido de mudança.", contexto, '{"instrucoes": ["passo 1", "passo 2"]}', MUDAR_SISTEMA)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(r, dict):
        return None
    # Os passos que a pessoa decidiu ficam como ela decidiu: o que o modelo
    # devolveu parecido com eles sai, e eles voltam inteiros no fim.
    chaves_fixas = {_chave(f) for f in fixos}
    novos, vistos = [], set()
    for x in r.get("instrucoes") or []:
        passo = _passo_limpo(x) if isinstance(x, str) else ""
        chave = _chave(passo)
        if len(passo.split()) < 2 or _parecido(chave, vistos) or _parecido(chave, chaves_fixas):
            continue
        vistos.add(chave)
        novos.append(passo)
    novos = novos[:14]
    if not novos:
        return None
    return novos + list(fixos)


def escrever(pedido: str, base: dict, trecho_do_modelo: str, perguntar_json) -> dict:
    """
    O modelo de IA escreve nome, descricao, instrucoes e exemplos; as respostas
    da pessoa (os `passos` da regra) entram depois, por regra. Sem JSON util, o
    rascunho da regra fica como esta.
    """
    contexto = f"Pedido: {pedido}"
    if trecho_do_modelo:
        contexto += "\n\nComeço do modelo de documento:\n" + trecho_do_modelo[:1800]
    try:
        r = perguntar_json("Escreva a ficha deste agente.", contexto, ESQUEMA, SISTEMA)
    except Exception:  # noqa: BLE001 - sem modelo, fica o rascunho da regra
        r = None
    if not isinstance(r, dict):
        return {**base, "escrito_por": "regra"}
    nome = " ".join(str(r.get("nome") or "").split())[:60] or base["nome"]
    descricao = " ".join(str(r.get("descricao") or "").split())[:240] or base["descricao"]
    dos_passos = {_chave(p) for p in base.get("passos", [])}
    instrucoes, vistos = [], set()
    for x in r.get("instrucoes") or []:
        passo = _passo_limpo(x) if isinstance(x, str) else ""
        chave = _chave(passo)
        if len(passo.split()) < 3 or _parecido(chave, vistos) or _parecido(chave, dos_passos):
            continue
        vistos.add(chave)
        instrucoes.append(passo)
    instrucoes = instrucoes[:8]
    # O que a pessoa decidiu (modelo, o que fazer quando faltar, o formato) vem da regra, no fim.
    passos = instrucoes + base.get("passos", [])
    exemplos = [" ".join(str(x).split())[:160] for x in (r.get("exemplos") or []) if isinstance(x, str) and len(str(x).split()) >= 3][:4]
    palavras = [str(x).strip()[:30] for x in (r.get("palavras") or []) if isinstance(x, str) and str(x).strip()][:5]
    return {**base, "nome": nome, "descricao": descricao, "exemplos": exemplos or base["exemplos"], "palavras": palavras,
            "instrucoes": instrucoes_em_markdown(nome, descricao, passos), "passos": passos, "escrito_por": "modelo"}
