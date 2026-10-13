"""
Os sistemas que o banco de provas mede (docs/PLANO-EDITOR.md, E0).

  gabarito      aplica o gabarito da tarefa (src/edicao.py): tem de tirar 100%
  troca_global  ruim de propósito: toda troca em todas as ocorrências do documento
  no_fim        ruim de propósito: todo texto novo vai para o fim do documento
  hoje          o editor de antes de 13/10/2026, copiado fielmente (rota
                /api/documentos/{id}/assistente e js/13-editor-na-conversa.js
                no commit ded4164): a troca dita na frase por regra; senão o
                modelo com a instrução de então ("trocas" e "acrescentar"),
                as trocas aplicadas no documento inteiro e o texto novo no fim,
                marcados com <mark class="ed-novo">; com seleção, o texto do
                modelo no lugar do trecho
  agente        o agente de edição (E5), quando existir

Os modelos: `ModeloNuvem` fala com a IA da nuvem do PAULUS pela chave desta
instalação (só leitura; nada é gravado na pasta de dados), `ModeloLocal` com
o Ollama deste computador, `ModeloFalso` responde o que o teste mandar.
"""

from __future__ import annotations

import copy
import json
import re
import time
from types import SimpleNamespace

from bancada import LEGAL, Saida, documento  # noqa: F401

import blocos as B
import edicao as ED


# ------------------------------------------------------------------ modelos

class ModeloNuvem:
    def __init__(self, dados_dir, modelo: str = "", nivel: str = "advogado") -> None:
        import nuvem

        self._nuvem = nuvem
        self.k = nuvem.chave(SimpleNamespace(dados_dir=str(dados_dir)), "paulus")
        if not self.k:
            raise RuntimeError("esta instalação não tem a chave da nuvem (entre com a Conta Atos no PAULUS)")
        self.modelo = modelo or nuvem.PROVEDORES["paulus"]["padrao"]
        self.nivel = nivel
        self.nome = f"nuvem:{self.nivel}"
        self.uso = {"tokens_entrada": 0, "tokens_saida": 0}
        self.modelo_real = ""

    def chamar(self, mensagens: list[dict], *, json_mode: bool = False, max_tokens: int = 4000, on_token=None) -> str:
        partes: list[str] = []

        def entrou(t: str) -> None:
            partes.append(t)
            if on_token:
                on_token(t)

        uso = self._nuvem.chamar("paulus", self.modelo, self.k, mensagens, entrou, json_mode=json_mode,
                                 max_tokens=max_tokens, nivel=self.nivel)
        self.modelo_real = uso.get("modelo") or self.modelo_real
        self.uso["tokens_entrada"] += int(uso.get("tokens_entrada") or 0)
        self.uso["tokens_saida"] += int(uso.get("tokens_saida") or 0)
        return "".join(partes).strip()

    # A cara do ClienteNuvem (src/nuvem.py), que era quem respondia no editor de antes.
    def ask(self, instrucao: str, contexto: str = "", sistema: str = "", ensinado: str = "") -> str:
        import llama_client

        return self.chamar(llama_client.montar_mensagens(instrucao, contexto, sistema=sistema, ensinado=ensinado))

    def ask_json(self, instrucao: str, contexto: str = "", sistema: str = ""):
        prompt = instrucao
        if contexto:
            prompt = f"Trechos de contratos:\n\n{contexto}\n\n{prompt}"
        bruto = self.chamar([{"role": "system", "content": sistema}, {"role": "user", "content": prompt}], json_mode=True)
        return _json(bruto)


class ModeloLocal:
    def __init__(self, modelo: str = "llama3.2:3b") -> None:
        from llama_client import LlamaClient

        self.c = LlamaClient(model=modelo)
        self.nome = f"local:{modelo}"
        self.uso = {"tokens_entrada": 0, "tokens_saida": 0}
        self.modelo_real = modelo

    def chamar(self, mensagens: list[dict], *, json_mode: bool = False, max_tokens: int = 4000, on_token=None) -> str:
        texto = self.c._chat(mensagens, fmt="json" if json_mode else None, stream=bool(on_token), on_token=on_token)
        ult = getattr(self.c, "ultima", {}) or {}
        self.uso["tokens_entrada"] += int(ult.get("prompt_eval_count") or 0)
        self.uso["tokens_saida"] += int(ult.get("eval_count") or 0)
        return (texto or "").strip()

    def ask(self, instrucao: str, contexto: str = "", sistema: str = "", ensinado: str = "") -> str:
        return self.c.ask(instrucao, contexto, sistema=sistema, ensinado=ensinado)

    def ask_json(self, instrucao: str, contexto: str = "", sistema: str = ""):
        return self.c.ask_json(instrucao, contexto, sistema=sistema)


class ModeloFalso:
    """Responde o que o teste mandou, na ordem; guarda o que recebeu."""

    def __init__(self, respostas: list[str]) -> None:
        self.respostas = list(respostas)
        self.recebido: list[list[dict]] = []
        self.nome = "falso"
        self.uso = {"tokens_entrada": 0, "tokens_saida": 0}
        self.modelo_real = "falso"

    def chamar(self, mensagens: list[dict], *, json_mode: bool = False, max_tokens: int = 4000, on_token=None) -> str:
        self.recebido.append(mensagens)
        texto = self.respostas.pop(0) if self.respostas else ""
        if on_token:
            for i in range(0, len(texto), 40):
                on_token(texto[i:i + 40])
        return texto

    def ask(self, instrucao: str, contexto: str = "", sistema: str = "", ensinado: str = "") -> str:
        return self.chamar([{"role": "user", "content": instrucao + "\n" + contexto}])

    def ask_json(self, instrucao: str, contexto: str = "", sistema: str = ""):
        return _json(self.chamar([{"role": "user", "content": instrucao + "\n" + contexto}], json_mode=True))


def _json(bruto: str):
    try:
        return json.loads(bruto)
    except ValueError:
        ini = min((i for i in (bruto.find("{"), bruto.find("[")) if i != -1), default=-1)
        fim = max(bruto.rfind("}"), bruto.rfind("]"))
        if ini != -1 and fim > ini:
            try:
                return json.loads(bruto[ini:fim + 1])
            except ValueError:
                return None
        return None


# ------------------------------------------------------------- adaptadores

def gabarito(t, modelo=None) -> Saida:
    blocos = documento(t.doc)
    if t.pergunta:
        return Saida(html=B.html(blocos), resposta="(gabarito)", mudou=False, cita=list(t.cita))
    escopo = [t.selecao["bloco"]] if t.selecao else None
    r = ED.aplicar(blocos, t.gabarito, rodada=1, escopo=escopo, selecao=t.selecao, em_tudo=t.em_tudo)
    if ED.precisa_renumerar(r.blocos):
        ED.renumerar(r.blocos, 1)
    falhas = "; ".join(f["motivo"] for f in r.falhas)
    return Saida(html=B.html(r.blocos), resposta="; ".join(a["resumo"] for a in r.aplicadas),
                 mudou=bool(r.aplicadas), erro=("gabarito falhou: " + falhas) if falhas else "")


def troca_global(t, modelo=None) -> Saida:
    """Ruim de propósito: cada troca do gabarito em todas as ocorrências; inserção no fim."""
    blocos = documento(t.doc)
    if t.pergunta:
        return Saida(html=B.html(blocos), resposta="", mudou=False)
    novos = []
    for op in t.gabarito:
        if op["op"] in ("substituir", "apagar_trecho"):
            novos.append({"op": "substituir_em_tudo", "de": op["de"], "para": op.get("para", "")})
        else:
            novos.append(op)
    r = ED.aplicar(blocos, novos, rodada=1, em_tudo=True)
    return Saida(html=B.html(r.blocos), resposta="feito", mudou=bool(r.aplicadas))


def no_fim(t, modelo=None) -> Saida:
    """Ruim de propósito: o texto novo de toda operação vai para o fim do documento."""
    blocos = documento(t.doc)
    if t.pergunta:
        return Saida(html=B.html(blocos), resposta="", mudou=False)
    existentes = {b.id for b in blocos}
    for op in t.gabarito:
        textos = []
        if op["op"] == "inserir":
            textos = [d["texto"] if isinstance(d, dict) else d for d in op.get("blocos") or []]
        elif op["op"] in ("substituir", "reescrever"):
            textos = [op.get("para") or op.get("texto") or ""]
        for tx in textos:
            if tx:
                blocos.append(B.bloco_novo("p", tx, existentes, "s-fim", 1))
    return Saida(html=B.html(blocos), resposta="Escrevi no fim do documento.", mudou=True)


# ------------------------------------------------------- o editor de antes

# A instrução de então, copiada de src/api.py no commit ded4164: o sistema que
# este banco mede como linha de base. Não importa de api.py de propósito -
# quando o editor novo substituir a rota, a linha de base continua a mesma.
HOJE_INSTRUCAO_INTEIRO = """Voce ajuda um advogado brasileiro a mudar um documento. O documento inteiro
vem abaixo. Responda so com um objeto JSON, assim:
{"trocas": [{"de": "trecho copiado do documento", "para": "o texto novo"}], "acrescentar": ""}

- Para mudar o que ja esta escrito, use "trocas". "de" e copiado do documento
  letra por letra - o menor trecho que deixa claro o lugar (uma palavra, uma
  frase). Todas as trocas que o pedido pede, uma por lugar diferente.
- "acrescentar" e so para texto novo que o pedido manda escrever (uma
  clausula, um paragrafo), e vai para o fim do documento. Sem isso, "".
- nao invente numero de artigo, de lei, de sumula nem de processo
- nao invente nome, data, valor nem prazo que nao estejam no documento ou no pedido
- sem marcacao, sem asteriscos"""

HOJE_INSTRUCAO_TRECHO = """Voce ajuda um advogado brasileiro a redigir. Responda em
portugues do Brasil, direto, sem preambulo.

Regras:
- devolva APENAS o texto pedido, pronto para entrar no documento
- nao invente numero de artigo, de lei, de sumula nem de processo
- nao invente nome, data, valor nem prazo que nao estejam no que foi dado
- se faltar informacao para escrever, escreva o texto com a lacuna marcada
  entre colchetes, por exemplo [VALOR]
- sem marcacao, sem asteriscos, sem titulo"""

HOJE_SISTEMA = """Voce e o PAULUS, ajudando a redigir um documento juridico
brasileiro. Voce nao esta consultando arquivos: o que vem abaixo e o texto em
que se esta trabalhando agora.

Nunca cite nome de arquivo, nunca escreva cabecalho como "Arquivo:" ou
"Documento:", nunca repita o pedido antes de responder.

Nunca invente artigo de lei, sumula, processo, nome, data, valor ou prazo.

Voce NAO conhece a tela deste programa. Nunca diga onde clicar, nunca cite
botao, menu ou atalho."""


def _ocorrencias(texto: str, trecho: str) -> int:
    alvo = " ".join((trecho or "").split())
    if not alvo:
        return 0
    padrao = (r"(?<![\w])" if alvo[0].isalnum() else "") + r"\s+".join(map(re.escape, alvo.split())) + \
        (r"(?![\w])" if alvo[-1].isalnum() else "")
    return len(re.findall(padrao, texto or ""))


def _limpar_sugestao(texto: str) -> str:
    limpo = (texto or "").strip()
    limpo = re.sub(r"\*\*(.+?)\*\*", r"\1", limpo)
    limpo = re.sub(r"^\s*[*-]\s+", "", limpo, flags=re.M)
    limpo = re.sub(r"^\s*(sugest[aã]o|resposta|texto)\s*:\s*", "", limpo, flags=re.I)
    limpo = re.sub(r"^\s*\[[^\]]{0,40}\]\s*", "", limpo)
    limpo = re.sub(r"^\s*(arquivo|documento|origem|fonte)\s*:[^\n]{0,80}\n+", "", limpo, flags=re.I)
    return limpo.strip()


def _trocar_como_antes(blocos: list, trocas: list) -> int:
    """
    O aplicarTrocas da tela de antes: em todo nó de texto, toda ocorrência
    (palavra inteira) vira <mark class="ed-novo"> com o texto novo - e o texto
    de antes some (não fica riscado).
    """
    feitas = 0
    for de, para in trocas:
        partes = de.split()
        if not partes:
            continue
        padrao = re.compile((r"(?<![\w])" if de[0].isalnum() else "") + r"\s+".join(map(re.escape, partes))
                            + (r"(?![\w])" if de[-1].isalnum() else ""))
        for b in blocos:
            novas = []
            for c in b.corridas:
                if c.sug or not padrao.search(c.texto):
                    novas.append(c)
                    continue
                desde = 0
                for m in padrao.finditer(c.texto):
                    if m.start() > desde:
                        novas.append(B.Corrida(c.texto[desde:m.start()], c.marcas))
                    novas.append(B.Corrida(para, c.marcas, "ins", "s-legado", 0))
                    desde = m.end()
                    feitas += 1
                if desde < len(c.texto):
                    novas.append(B.Corrida(c.texto[desde:], c.marcas))
            b.corridas = novas
    return feitas


def hoje(t, modelo) -> Saida:
    import documento as documento_mod
    import intencao

    blocos = documento(t.doc)
    html = B.html(blocos)
    inteiro = documento_mod.para_texto(documento_mod.ler_html(html))
    inicio = time.time()
    antes = dict(modelo.uso)

    def saida(**k) -> Saida:
        s = Saida(segundos=time.time() - inicio, tokens_entrada=modelo.uso["tokens_entrada"] - antes["tokens_entrada"],
                  tokens_saida=modelo.uso["tokens_saida"] - antes["tokens_saida"], **k)
        return s

    # Pergunta: com o editor aberto, a frase sem verbo de mudança ia para a
    # conversa (destinoDoPedido). Aqui só se confere que o documento não muda;
    # a conversa de antes não apontava bloco nenhum.
    if t.pergunta:
        return saida(html=html, resposta="(ia para a conversa, que não apontava o lugar no documento)", mudou=False)

    if t.selecao:
        trecho = t.selecao["texto"]
        resposta = modelo.ask(HOJE_INSTRUCAO_TRECHO + f"\n\nPedido: {t.pedido}", f"Trecho selecionado do documento:\n{trecho[:2500]}",
                              sistema=HOJE_SISTEMA)
        sugestao = _limpar_sugestao(resposta)
        b = B.por_id(blocos)[t.selecao["bloco"]]
        lugar = B.achar(b.texto, trecho)
        if lugar and sugestao:
            texto = b.texto
            b.corridas = [B.Corrida(texto[:lugar[0]]), B.Corrida(sugestao, (), "ins", "s-legado", 0),
                          B.Corrida(texto[lugar[1]:])]
            B._limpar_corridas(b)
        return saida(html=B.html(blocos), resposta="Troquei o trecho que você selecionou.", mudou=True)

    trocas = [(de, para) for de, para in intencao.trocas_do_pedido(t.pedido) if _ocorrencias(inteiro, de)]
    if trocas:
        _trocar_como_antes(blocos, trocas)
        return saida(html=B.html(blocos), resposta="Troquei por regra, em todas as ocorrências.", mudou=True)

    try:
        dados = modelo.ask_json(HOJE_INSTRUCAO_INTEIRO + f"\n\nPedido: {t.pedido}", f"Documento:\n{inteiro[:60000]}",
                                sistema=HOJE_SISTEMA)
    except Exception as exc:  # noqa: BLE001
        return saida(html=html, resposta="", mudou=False, erro=str(exc)[:200])
    dados = dados if isinstance(dados, dict) else {}
    validas = []
    for x in dados.get("trocas") or []:
        if not isinstance(x, dict):
            continue
        de, para = str(x.get("de") or "").strip(), str(x.get("para") or "")
        if de and de != para and _ocorrencias(inteiro, de) and (de, para) not in validas:
            validas.append((de, para))
    acrescentar = _limpar_sugestao(str(dados.get("acrescentar") or ""))
    if validas:
        feitas = _trocar_como_antes(blocos, validas)
        return saida(html=B.html(blocos), resposta=f"Mudei {len(validas)} trecho(s) ({feitas} ocorrências).",
                     mudou=bool(feitas))
    if acrescentar:
        existentes = {b.id for b in blocos}
        blocos.append(B.bloco_novo("p", acrescentar.replace("\n\n", "\n"), existentes, "s-legado", 0))
        return saida(html=B.html(blocos), resposta="Escrevi no fim do documento.", mudou=True)
    return saida(html=html, resposta="Não achei no documento o trecho a mudar.", mudou=False)


# ------------------------------------------------------- o agente novo (E5)

def agente(t, modelo) -> Saida:
    """O agente de edição (src/agente_de_edicao.py), com o modelo dado e o nível dele."""
    import agente_de_edicao as AG

    blocos = documento(t.doc)
    inicio = time.time()
    antes = dict(modelo.uso)
    final = None
    remendos = 0
    for tipo, dados in AG.rodar(modelo.chamar, blocos, t.pedido, rodada=1, titulo=t.doc, selecao=t.selecao,
                                nivel=getattr(modelo, "nivel", "advogado")):
        if tipo == "remendo":
            remendos += 1
        elif tipo == "fim":
            final = dados["rodada"]
    r = final
    feitas = [a for a in r.aplicadas if a.get("tipo") != "comentar"]
    return Saida(html=B.html(r.blocos), resposta=AG.resposta(r, t.doc),
                 mudou=False if r.tipo == "pergunta" else bool(feitas), cita=r.citados, segundos=time.time() - inicio,
                 tokens_entrada=modelo.uso["tokens_entrada"] - antes["tokens_entrada"],
                 tokens_saida=modelo.uso["tokens_saida"] - antes["tokens_saida"],
                 detalhe={"chamadas": r.chamadas, "remendos": remendos, "entendi": r.entendi,
                          "falhas": [f["motivo"] for f in r.falhas], "nao_fiz": r.nao_fiz})


ADAPTADORES = {"gabarito": gabarito, "troca_global": troca_global, "no_fim": no_fim, "hoje": hoje, "agente": agente}
