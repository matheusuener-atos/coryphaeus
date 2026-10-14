"""
PAULUS - O agente de edição (docs/PLANO-EDITOR.md, E5).

Cada pedido feito ao documento aberto ao lado da conversa é uma rodada:

  1. entender   por regra: concluir, desfazer, aceitar ou recusar tudo,
                renumerar, pergunta ou edição - e o lugar que a frase aponta
                (o esboço: "a cláusula do prazo", "o inciso II da cláusula 3ª")
  2. editar     o modelo recebe o documento com o nome de cada bloco, o
                esboço, o foco, a seleção e as regras do escritório, e devolve
                OPERAÇÕES (src/edicao.py) - nunca o documento reescrito
  3. aplicar    cada operação é conferida e aplicada como sugestão marcada
                ENQUANTO o modelo ainda escreve: a tela vê a mudança entrando
  4. corrigir   a operação que não passou na conferência (trecho que não está
                no bloco) volta ao modelo uma vez, com o texto exato do bloco
  5. conferir   a numeração das cláusulas (renumerada como sugestão própria),
                a referência para cláusula que não existe, a lacuna [●]; nos
                níveis Max e Ultra, uma segunda leitura do modelo
  6. responder  o que mudou, com o lugar de cada mudança, o que não deu e por
                quê - montado do que foi aplicado de fato, não do que o modelo
                disse que fez

`rodar` é um gerador de eventos (tipo, dados) - o que a rota manda à tela.
O modelo entra por `chamar(mensagens, json_mode=, max_tokens=, on_token=)`:
a nuvem, o modelo deste computador ou o modelo de mentira dos testes.
"""

from __future__ import annotations

import copy
import json
import re
import time
from dataclasses import dataclass, field

import blocos as B
import edicao as ED
import esboco as E

# ------------------------------------------------------------- entender

_VERBO_DE_MUDANCA = (r"(?:deix[ae]|torn[ae]|reescrev[ae]|escrev[ae]|redij[ao]|troqu?e|troca|substitu[ai]|acrescent[ae]|"
                     r"adicion[ae]|inclu[ai]|insir[ao]|insere|alter[ae]|mud[ae]|corrij[ao]|corrige|remov[ae]|retir[ae]|"
                     r"tir[ae]|apagu?e|apaga|exclu[ai]|resum[ae]|encurt[ae]|melhor[ae]|formaliz[ae]|ajust[ae]|complet[ae]|"
                     r"mov[ae]|pass[ae]|coloqu?e|ponha|traduz[ae]?|padroniz[ae]|uniformiz[ae]|reorganiz[ae]|simplifiqu?e|"
                     r"detalh[ae]|explicit[ae]|faça|fa[cç]a|prev[eê]ja|preveja|estabele[cç]a|fix[ae]|defin[ae]|"
                     r"reduz[ae]?|aument[ae]|diminu[ai]|amplie|restrinj[ao]|elimin[ae]|cancel[ae]|comente|aponte|"
                     r"numer[ae]|renumer[ae]|cit[ae]|fundament[ae]|qualifiqu?e)")
RE_CONCLUIR = re.compile(r"(?i)^\s*(?:(?:pode|podemos|vamos)\s+)?(?:conclu[ia]r?|conclua|finaliz[ae]r?|finalize|encerr[ae])"
                         r"(?:\s+(?:o|este|esse)\s+(?:documento|contrato|texto|arquivo))?\s*[.!]?\s*$|"
                         r"\best[aá]\s+pronto\b[^.?!]{0,40}\b(?:salv|conclu|guard|grav)")
RE_DESFAZER = re.compile(r"(?i)^\s*(?:desfa[cç]a|desfazer|volt[ae]\s+(?:como|ao\s+que)\s+(?:estava|era)|"
                         r"descart[ae]\s+(?:a\s+|as\s+|essa\s+|esta\s+|essas\s+|estas\s+)?(?:[uú]ltima\s+)?"
                         r"(?:altera|mudan|sugest|resposta|rodada))")
RE_ACEITAR_TUDO = re.compile(r"(?i)^\s*(?:aceit[ae]|mantenha|pode\s+manter|aprov[ae])\s+(?:todas|tudo|as\s+(?:altera|mudan|sugest))")
RE_RECUSAR_TUDO = re.compile(r"(?i)^\s*(?:recus[ae]|rejeit[ae]|descart[ae])\s+(?:todas|tudo)\b")
RE_RENUMERAR = re.compile(r"(?i)^\s*(?:por\s+favor\s*,?\s*)?(?:re)?numer[ae]\s+(?:as\s+|todas\s+as\s+)?cl[aá]usulas\s*[.!]?\s*$")
RE_PERGUNTA = re.compile(r"(?i)^\s*(?:qual|quais|quanto|quantos|quantas|quando|onde|quem|o\s+que|que\s+|como\s+(?:est[aá]|fica|ficou|é)|"
                         r"existe|h[aá]\s|tem\s|por\s+que|porque|em\s+que|este|esse|esta|essa|isso|isto|a\s+cl[aá]usula|"
                         r"o\s+contrato|o\s+documento)")
RE_EM_TUDO = re.compile(r"(?i)em\s+todo\s+o\s+(?:documento|contrato|texto|instrumento|acordo|termo)|em\s+toda\s+a\s+"
                        r"(?:pe[cç]a|peti[cç][aã]o|minuta|procura[cç][aã]o|notifica[cç][aã]o)|em\s+todas?\s+as\s+"
                        r"(?:ocorr[eê]ncias|partes|vezes|cl[aá]usulas)|sempre\s+que\s+aparecer|onde\s+(?:quer\s+que|houver)|"
                        r"\bem\s+tudo\b")
RE_TROCA_ENTRE_ASPAS = re.compile(r"(?i)(?:troqu?e|troca|substitua|mude|altere|corrija|trocar|substituir)\s+"
                                  r"[\"“'‘]([^\"”'’]{1,160})[\"”'’]\s+(?:por|para|pelo|pela)\s+[\"“'‘]([^\"”'’]{0,240})[\"”'’]")
RE_SO_NA = re.compile(r"(?i)\bs[oó]\s+(?:na|no|nas|nos|dentro\s+d[aeo])\s+")
# "Dê uma revisada", "como está ficando?", "confira o contrato", "arrume a
# formatação": a revisão - a conferência por regra, as correções seguras como
# sugestão e a leitura do modelo. Antes (13/10/2026) virava "Não fiz: revisão".
RE_REVISAR = re.compile(
    r"(?i)\b(?:revis(?:e|ar|ão|ao|ada|ando)\b|d[eê]\s+uma\s+(?:olhada|revisada|conferida|lida|geral|repassada|checada)|"
    r"confir(?:a|e|ir)\s+(?:o\s+|a\s+|todo\s+o\s+)?(?:documento|contrato|texto|minuta|tudo)|"
    r"como\s+(?:o\s+(?:documento|contrato|texto)\s+)?(?:est[aá]\s+ficando|ficou)|o\s+que\s+(?:voc[eê]\s+)?acha|"
    r"analis(?:e|ar)\s+(?:o\s+|a\s+)?(?:documento|contrato|texto|minuta|tudo)|"
    r"(?:arrum|organiz|limp|ajust)(?:e|ar)\s+(?:a\s+|o\s+)?(?:formata[cç][aã]o|visual|apar[eê]ncia|texto|documento|layout)|"
    r"junt(?:e|ar)\s+as\s+linhas|forma\s+visual|visualmente)")
# Revisão com instrução ("revise a cláusula 5ª para incluir multa") é edição.
RE_INSTRUCAO = re.compile(r"(?i)\b(?:para\s+(?:que|ficar|incluir|tirar|prever|constar|deixar)|deixando|incluindo|"
                          r"acrescentando|mais\s+(?:formal|curt|clar|objetiv|simples|t[eé]cnic)|por\s+[\"“'])")
# "Isso mesmo", "pode fazer", "sim": o que a última resposta deixou para fazer.
RE_CONFIRMA = re.compile(
    r"(?i)^\s*(?:sim|isso|isso\s+mesmo|exato|exatamente|pode|pode\s+(?:sim|fazer|seguir|ir|mandar)|"
    r"fa[cç]a(?:\s+isso)?|faz(?:\s+isso)?|ok|okay|beleza|perfeito|manda(?:\s+ver)?|vai|vamos|aplique|aplica|"
    r"concordo|de\s+acordo|certo|claro|positivo|prossiga|segue)"
    r"(?:[\s,.!]+(?:sim|isso|pode|por\s+favor|pf|pfv|obrigad[oa]|mesmo|fa[cç]a|claro))*[\s.!]*$")
RE_CITACAO = re.compile(r"\[(b[0-9a-f]{4,8})(?:\s*[·|-][^\]\n]{0,60})?\]")


@dataclass
class Entendimento:
    # editar | pergunta | concluir | desfazer | aceitar | recusar | renumerar | revisar | confirmar | texto_colado
    tipo: str = "editar"
    foco: list = field(default_factory=list)       # os blocos que o pedido aponta
    rotulos: list = field(default_factory=list)
    restrito: bool = False        # o foco é limite (seleção, "só na cláusula X")
    em_tudo: bool = False
    regra: list = field(default_factory=list)      # operações que a regra já faz, sem modelo
    nao_existe: str = ""          # "Cláusula 10ª" citada e inexistente
    porque: str = ""


def _pergunta(pedido: str) -> bool:
    texto = pedido.strip()
    if re.search(r"\b" + _VERBO_DE_MUDANCA + r"\b", texto, re.I) and not texto.endswith("?"):
        return False
    if texto.endswith("?"):
        return not re.match(r"(?i)^\s*(?:pode|poderia|consegue|você\s+pode|da\s+para|dá\s+para)\s+"
                            + _VERBO_DE_MUDANCA, texto)
    return bool(RE_PERGUNTA.match(texto)) and not re.search(r"\b" + _VERBO_DE_MUDANCA + r"\b", texto, re.I)


def texto_colado(blocos: list, pedido: str) -> bool:
    """
    O texto do próprio documento colado na conversa, sem instrução (13/10/2026:
    o contrato inteiro colado virou seis mudanças a esmo). É comparar e marcar
    as diferenças, não editar. Longo, sem verbo de mudança no começo e com as
    palavras do documento.
    """
    texto = " ".join((pedido or "").split())
    if len(texto) < 350 or re.search(r"\b" + _VERBO_DE_MUDANCA + r"\b", texto[:90], re.I):
        return False
    if re.match(r"(?i)\s*(?:compare|comparar|use|usar|considere|veja|segue|aqui\s+est[aá])\b", texto):
        return True
    palavras = {p for p in re.findall(r"[a-z0-9]{4,}", E.plano(texto))}
    do_documento = {p for p in re.findall(r"[a-z0-9]{4,}", E.plano(B.texto_puro(blocos)))}
    return bool(palavras) and len(palavras & do_documento) / len(palavras) >= 0.6


def entender(blocos: list, pedido: str, selecao: dict | None = None) -> Entendimento:
    """O que o pedido é e onde ele mexe - por regra, sem modelo."""
    texto = " ".join((pedido or "").split())
    ent = Entendimento()
    if RE_CONCLUIR.search(texto):
        ent.tipo, ent.porque = "concluir", "pedido de conclusão"
        return ent
    if RE_DESFAZER.match(texto):
        ent.tipo, ent.porque = "desfazer", "pedido para desfazer a última resposta"
        return ent
    if RE_ACEITAR_TUDO.match(texto):
        ent.tipo, ent.porque = "aceitar", "pedido para manter as mudanças"
        return ent
    if RE_RECUSAR_TUDO.match(texto):
        ent.tipo, ent.porque = "recusar", "pedido para descartar as mudanças"
        return ent
    if RE_RENUMERAR.match(texto):
        ent.tipo, ent.porque = "renumerar", "renumerar é regra, não precisa de modelo"
        return ent
    if RE_CONFIRMA.match(texto):
        ent.tipo, ent.porque = "confirmar", "confirmação do que a última resposta deixou para fazer"
        return ent
    if texto_colado(blocos, pedido):
        ent.tipo, ent.porque = "texto_colado", "texto do documento colado na conversa: comparar e marcar"
        return ent
    ent.em_tudo = bool(RE_EM_TUDO.search(texto))
    if selecao and (selecao.get("blocos") or selecao.get("bloco")):
        ids = list(selecao.get("blocos") or [selecao["bloco"]])
        ent.foco, ent.restrito = ids, True
        ent.rotulos = ["o trecho selecionado"]
    else:
        lugares = E.localizar_todos(blocos, texto)
        inexistente = next((l for l in lugares if l.get("como") == "nao_existe"), None)
        if not lugares:
            unico = E.localizar(blocos, texto)
            if unico.get("como") == "nao_existe":
                inexistente = unico
        if inexistente:
            ent.nao_existe = inexistente.get("rotulo", "")
        for l in lugares:
            ent.foco += [i for i in l["ids"] if i not in ent.foco]
            ent.rotulos.append(l["rotulo"])
        ent.restrito = bool(ent.foco) and bool(RE_SO_NA.search(texto))
    if RE_REVISAR.search(texto) and not RE_INSTRUCAO.search(texto) and not RE_TROCA_ENTRE_ASPAS.search(texto):
        ent.tipo, ent.porque = "revisar", "pedido de revisão"
        return ent
    if _pergunta(texto):
        ent.tipo, ent.porque = "pergunta", "pergunta sobre o documento"
        return ent
    # A troca entre aspas é regra: "troque “X” por “Y”".
    for m in RE_TROCA_ENTRE_ASPAS.finditer(texto):
        de, para = m.group(1).strip(), m.group(2).strip()
        if not de or de == para:
            continue
        alvo = [b for b in blocos if b.sug != "del" and b.tipo != "table" and (not ent.restrito or b.id in ent.foco)
                and B.ocorrencias(b.texto, de)]
        if not alvo:
            continue
        if len(alvo) == 1:
            ent.regra.append({"op": "substituir", "bloco": alvo[0].id, "de": de, "para": para})
        else:
            ent.regra.append({"op": "substituir_em_tudo", "de": de, "para": para})
            ent.em_tudo = True
    if ent.regra:
        ent.porque = "troca dita entre aspas: regra, letra por letra"
    return ent


# ---------------------------------------------------------- localizar

_VAZIAS = set("""a o as os de da do das dos e em no na nos nas um uma uns umas que para por com sem ao aos à às
se sua seu suas seus este esta isso isto esse essa aquele aquela mais menos muito pouco ser ter fazer favor
deixe torne mude troque altere corrija inclua acrescente coloque passe remova tire apague texto documento
contrato clausula paragrafo""".split())


def relevantes(blocos: list, pedido: str, quantos: int = 8) -> list[str]:
    """Os blocos que mais têm as palavras do pedido (para o documento longo, que não cabe inteiro)."""
    import math

    def palavras(t: str) -> list[str]:
        return [p for p in re.findall(r"[a-z0-9]{3,}", E.plano(t)) if p not in _VAZIAS]

    alvo = set(palavras(pedido))
    if not alvo:
        return []
    docs = [(b.id, palavras(b.texto)) for b in blocos if b.sug != "del"]
    n = len(docs) or 1
    df = {w: sum(1 for _, ps in docs if w in ps) for w in alvo}
    notas = []
    for bid, ps in docs:
        if not ps:
            continue
        nota = sum(ps.count(w) * math.log(1 + n / (1 + df[w])) for w in alvo) / (1 + len(ps) / 60)
        if nota > 0:
            notas.append((nota, bid))
    return [bid for _, bid in sorted(notas, reverse=True)[:quantos]]


# ------------------------------------------------------------- o modelo

SISTEMA = """Você é o Paulus, assistente de um escritório de advocacia no Brasil. Você está DENTRO do editor de texto, \
editando o documento jurídico aberto ao lado da conversa, a pedido de um advogado. Trabalhe como um advogado sênior \
revisando a minuta de um colega: faça exatamente o que foi pedido, no lugar certo, com a redação técnica e o estilo que \
o documento já usa.

COMO O DOCUMENTO CHEGA
Cada bloco (parágrafo, título, item, quadro) vem numa linha, com o nome entre colchetes:
[b0b0008 · Cláusula 2ª] O prazo da locação é de 30 (trinta) meses...
O nome (b0b0008) é como você aponta o lugar. O rótulo depois do ponto é só para você se orientar.

O QUE VOCÊ DEVOLVE
Só um objeto JSON, nesta ordem de campos:
{"entendi": "o que você vai fazer, numa frase",
 "operacoes": [ ... ],
 "nao_fiz": ["parte DO PEDIDO que ficou sem fazer, e por quê - [] quando fez tudo"],
 "sugestoes": ["outro ponto do documento que talvez devesse mudar junto, e por quê - sem mudar; [] quando não há"],
 "lacunas": ["dado que falta e ficou como [●] no texto - [] quando não há"]}
Nesses três campos você fala com o advogado: frase curta, com o rótulo do lugar (Cláusula 3ª, § 1º), nunca o nome do \
bloco (b12). Nada de "nenhuma lacuna" ou "não alterei o que não foi pedido": campo sem nada a dizer fica [].

AS OPERAÇÕES
- {"op": "substituir", "bloco": "b12", "de": "trecho EXATO do bloco", "para": "texto novo"}
  Troca um trecho dentro de UM bloco. "de" é copiado do bloco letra por letra: o menor trecho que identifica o lugar, \
mas completo (o número junto com o extenso: "30 (trinta) meses"). "de" é um pedaço CONTÍNUO do texto: dois pontos \
separados do mesmo bloco pedem uma operação para cada um. Para tirar um trecho, "para" fica "" (cuide da vírgula).
- {"op": "reescrever", "bloco": "b12", "texto": "o bloco inteiro, já reescrito"}
  Para mudar o parágrafo como um todo (mais formal, mais claro, mais curto, outra redação). Mantenha o que não precisa mudar.
- {"op": "inserir", "depois_de": "b12", "blocos": [{"texto": "..."}, {"texto": "..."}]}   (ou "antes_de")
  Texto novo NO LUGAR CERTO. Cláusula nova entra depois da cláusula a que se liga: um bloco com a cabeça, no mesmo \
estilo das outras ("CLÁUSULA 3ª – DA MULTA"), e um ou mais blocos com o corpo. Parágrafo novo de uma cláusula entra \
depois do último bloco dela. Cada parágrafo é um item de "blocos".
- {"op": "apagar", "bloco": "b12"}   ou   {"op": "apagar", "blocos": ["b12", "b13"]}
- {"op": "mover", "blocos": ["b12", "b13"], "depois_de": "b30"}   (ou "antes_de")
- {"op": "substituir_em_tudo", "de": "...", "para": "..."}  SÓ quando o pedido é trocar em todo o documento (um nome, \
um termo, um índice).
- {"op": "comentar", "bloco": "b12", "texto": "observação para o advogado"}  quando o pedido é comentar ou apontar \
problema, sem mudar o texto.

REGRAS
1. Mude SÓ o que o pedido manda, nos blocos de que ele fala. Se outro ponto do documento parecer depender da mudança \
(a caução calculada sobre o aluguel, uma multa em aluguéis, uma data em outra cláusula), NÃO mude: escreva em \
"sugestoes" o que talvez devesse mudar e por quê. Quem decide é o advogado.
2. Número igual não é o mesmo dado: "30 (trinta) dias" de um parágrafo não é o "30 (trinta) meses" do prazo. Troque só \
o trecho que é o dado pedido.
3. Nunca escreva no fim do documento o que tem lugar certo dentro dele.
4. Valores, prazos e quantidades: número e extenso juntos, como o documento já faz ("R$ 2.600,00 (dois mil e \
seiscentos reais)", "24 (vinte e quatro) meses"). Dentro do MESMO trecho, ajuste o que depende diretamente da mudança \
(a data de término do prazo que mudou), na mesma operação.
5. Mantenha os termos definidos como o documento os escreve (LOCATÁRIA, VENDEDORES, CONTRATANTE) e a forma de numerar \
cláusulas, parágrafos (§ 1º, Parágrafo único), incisos (I –, II –) e alíneas (a), b)).
6. Cláusula nova: numere com o número que ela vai ocupar na sequência (nunca "2ª-A"). O programa renumera as seguintes e \
as referências cruzadas depois - você NÃO renumera as outras.
7. Não invente fato, nome, número de documento, valor, data, artigo de lei, súmula ou processo. O que faltar fica [●] no \
texto e vai em "lacunas". Cite artigo de lei só com certeza absoluta de que ele existe e diz aquilo.
8. Com trecho selecionado, mude só dentro dele.
9. Pergunta sobre o documento não é pedido de mudança: "operacoes": [].
10. Português do Brasil, registro jurídico formal, sem markdown, sem asteriscos."""

SISTEMA_PERGUNTA = """Você é o Paulus, assistente de um escritório de advocacia no Brasil, conversando com o advogado sobre \
o documento aberto no editor ao lado. Responda à pergunta como um colega advogado: direto, curto, com a informação \
exata do documento. Cite o bloco de onde tirou cada informação, com o nome dele entre colchetes, assim: [b0b0008]. O \
documento nem sempre usa o nome técnico do que se pergunta: procure pelo instituto jurídico, não só pela palavra. Se o \
documento não traz a resposta, diga isso. Não invente. Português do Brasil, sem markdown."""

SISTEMA_LEITURA = """Você é o revisor sênior de um escritório de advocacia no Brasil. Leia o documento inteiro, como o \
advogado que vai assinar, e aponte o que um colega experiente apontaria antes de mandar ao cliente: contradição entre \
cláusulas, valor ou prazo incoerente, obrigação sem prazo ou sem consequência, cláusula essencial que falta para este \
tipo de documento, redação ambígua que pode virar litígio, parte qualificada de um jeito numa cláusula e de outro em \
outra. Não aponte numeração, repetição, lacuna [●], CPF ou CNPJ - o programa já conferiu. Seja específico e curto, \
como numa nota de revisão: o problema e o que fazer. Responda só com JSON:
{"pontos": [{"bloco": "b12", "texto": "o problema e o que fazer, em uma ou duas frases"}]}
No máximo 6, os mais importantes primeiro. Documento bom: "pontos": []. Português do Brasil, sem markdown."""

SISTEMA_REVISAO = """Você é o revisor do escritório. Um assistente acabou de mudar um documento jurídico a pedido do \
advogado. Confira como um revisor rigoroso: (1) o pedido foi cumprido por inteiro? (2) mudou algo além do pedido? (3) \
alguma mudança contradiz outra parte do documento (datas, valores em número e por extenso, prazos, referências a \
cláusulas, termos definidos, nomes das partes)? Responda só com JSON:
{"ok": true, "problemas": ["..."], "operacoes": [correções, no mesmo formato das operações do editor]}
Correção só para problema real e concreto; sem problema, "operacoes": []."""

FORMATO_OPERACOES = ('{"entendi": "...", "operacoes": [{"op": "substituir", "bloco": "b12", "de": "...", "para": "..."}], '
                     '"nao_fiz": [], "lacunas": []}')


def mensagens_de_edicao(blocos: list, ent: Entendimento, pedido: str, *, titulo: str = "", selecao: dict | None = None,
                        regras: str = "", memoria: str = "", artigos: str = "", casa: str = "",
                        conversa: str = "", limite: int = 90000) -> list[dict]:
    """O que o modelo lê: o esboço, o documento com os nomes, o foco, a seleção e o pedido."""
    rotulos = E.rotulos(blocos)
    inteiro = B.para_modelo([b for b in blocos if b.sug != "del"], rotulos=rotulos)
    partes = [f"DOCUMENTO: {titulo}" if titulo else "DOCUMENTO", "", "ESBOÇO:", E.resumo(blocos, 4000), ""]
    if len(inteiro) <= limite:
        partes += ["TEXTO (um bloco por linha):", inteiro]
    else:
        # O documento longo: o foco, os vizinhos e o que mais tem as palavras do pedido.
        alvo = list(ent.foco) + [i for i in relevantes(blocos, pedido) if i not in ent.foco]
        indices = {B.indice(blocos, i) for i in alvo}
        perto = sorted({j for i in indices for j in range(max(0, i - 2), min(len(blocos), i + 3))})
        partes += ["TEXTO (só os trechos que importam ao pedido; o resto está no esboço):",
                   B.para_modelo([blocos[j] for j in perto if blocos[j].sug != "del"], rotulos=rotulos)]
    if ent.foco and not ent.restrito:
        partes += ["", f"O PEDIDO APONTA PARA: {', '.join(ent.rotulos)} ({ent.foco[0]}…{ent.foco[-1]})"]
    if selecao and selecao.get("texto"):
        partes += ["", f"TRECHO SELECIONADO pela pessoa (mude só dentro dele), no bloco {selecao.get('bloco')}:",
                   f"\"{selecao['texto'][:3000]}\""]
    elif ent.restrito and ent.foco:
        partes += ["", f"SÓ MEXA EM: {', '.join(ent.rotulos)} ({', '.join(ent.foco[:30])})"]
    if ent.nao_existe:
        partes += ["", f"ATENÇÃO: o pedido cita {ent.nao_existe}, que não existe neste documento."]
    if regras.strip():
        partes += ["", "REGRAS DE REDAÇÃO DO ESCRITÓRIO:", regras.strip()[:4000]]
    if memoria.strip():
        partes += ["", "O QUE JÁ FOI PEDIDO E DECIDIDO NESTE DOCUMENTO:", memoria.strip()[:3000]]
    if casa.strip():
        partes += ["", "CLÁUSULAS DO ESCRITÓRIO (quando o pedido mandar usar a da casa, use esta, adaptada às partes "
                       "e aos termos deste documento):", casa.strip()[:6000]]
    if artigos.strip():
        partes += ["", "LEI (texto oficial da base instalada; cite só daqui, com o número exato):", artigos.strip()[:6000]]
    if conversa.strip():
        partes += ["", "A CONVERSA ATÉ AQUI (para entender “isso”, “aquela cláusula”, “o que você sugeriu”):",
                   conversa.strip()[:3000]]
    partes += ["", f"PEDIDO: {pedido}", "",
               "ANTES DE RESPONDER, CONFIRA:",
               "- Mudo só os blocos de que o pedido fala? Outro ponto que talvez devesse mudar vai em \"sugestoes\".",
               "- O trecho que eu troco é o dado pedido, e não outro número igual em outro lugar?",
               "- Texto novo está no lugar certo (depois da cláusula a que se liga), e não no fim do documento?",
               "Responda só com o JSON."]
    return [{"role": "system", "content": SISTEMA}, {"role": "user", "content": "\n".join(partes)}]


def mensagens_de_pergunta(blocos: list, pergunta: str, titulo: str = "", limite: int = 90000) -> list[dict]:
    rotulos = E.rotulos(blocos)
    inteiro = B.para_modelo([b for b in blocos if b.sug != "del"], rotulos=rotulos, limite=limite)
    return [{"role": "system", "content": SISTEMA_PERGUNTA},
            {"role": "user", "content": f"DOCUMENTO: {titulo}\n\n{inteiro}\n\nPERGUNTA: {pergunta}"}]


# ------------------------------------------- o JSON enquanto ele chega

def _fim_do_objeto(texto: str, inicio: int) -> int:
    """Onde fecha o objeto que abre em `inicio` (-1: ainda não fechou)."""
    nivel = 0
    em_texto = False
    escape = False
    for i in range(inicio, len(texto)):
        c = texto[i]
        if em_texto:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                em_texto = False
            continue
        if c == '"':
            em_texto = True
        elif c == "{":
            nivel += 1
        elif c == "}":
            nivel -= 1
            if nivel == 0:
                return i
    return -1


class LeitorDeOperacoes:
    """
    Tira cada operação completa da lista "operacoes" enquanto o modelo ainda
    escreve o resto: a primeira mudança aparece no documento segundos depois
    do pedido, e não depois do último caractere da resposta.
    """

    def __init__(self) -> None:
        self.texto = ""
        self.cursor = -1
        self.acabou = False
        self.lidas = 0

    def entrar(self, pedaco: str) -> list[dict]:
        self.texto += pedaco
        if self.acabou:
            return []
        if self.cursor < 0:
            m = re.search(r'"operacoes"\s*:\s*\[', self.texto)
            if not m:
                return []
            self.cursor = m.end()
        saida = []
        while True:
            i = self.cursor
            while i < len(self.texto) and self.texto[i] in " \n\r\t,":
                i += 1
            if i >= len(self.texto):
                self.cursor = i
                return saida
            if self.texto[i] == "]":
                self.acabou = True
                return saida
            if self.texto[i] != "{":
                self.cursor = i + 1
                continue
            fim = _fim_do_objeto(self.texto, i)
            if fim < 0:
                self.cursor = i
                return saida
            try:
                op = json.loads(self.texto[i:fim + 1])
                if isinstance(op, dict):
                    saida.append(op)
                    self.lidas += 1
            except ValueError:
                pass
            self.cursor = fim + 1


def ler_json(bruto: str) -> dict:
    """O objeto da resposta, tolerando texto antes e depois e cerca de código."""
    t = (bruto or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        d = json.loads(t)
        return d if isinstance(d, dict) else {}
    except ValueError:
        pass
    ini = t.find("{")
    if ini < 0:
        return {}
    fim = _fim_do_objeto(t, ini)
    if fim > ini:
        try:
            d = json.loads(t[ini:fim + 1])
            return d if isinstance(d, dict) else {}
        except ValueError:
            return {}
    return {}


# --------------------------------------------------------------- a rodada

@dataclass
class Rodada:
    """O que a rodada fez, para a resposta e para o registro."""
    numero: int
    pedido: str
    tipo: str = "editar"
    entendi: str = ""
    aplicadas: list = field(default_factory=list)
    falhas: list = field(default_factory=list)
    nao_fiz: list = field(default_factory=list)
    lacunas: list = field(default_factory=list)
    sugestoes: list = field(default_factory=list)   # o que talvez devesse mudar junto (o modelo não mudou)
    conferencia: list = field(default_factory=list)  # os avisos que a rodada criou (src/conferencia_juridica.py)
    avisos: list = field(default_factory=list)
    comentarios: list = field(default_factory=list)
    resposta: str = ""
    citados: list = field(default_factory=list)
    blocos: list = field(default_factory=list)
    chamadas: int = 0
    segundos: float = 0.0
    # a revisão: o que a regra achou e ficou para o advogado ({bloco, rotulo, titulo, detalhe, grau}),
    # e o que a leitura do modelo apontou ({bloco, rotulo, texto})
    pontos: list = field(default_factory=list)
    leitura: list = field(default_factory=list)
    colado: dict = field(default_factory=dict)      # a comparação com o texto colado (edicao.comparar_com_texto)

    @property
    def sids(self) -> list[str]:
        return [s for a in self.aplicadas for s in a.get("sids", [])]


_FALHA_PARA_GENTE = (
    (r"^não achei “(.+)” em b\w+", r"não achei “\1” no texto"),
    (r"^o bloco “(.+)” não existe no documento", r"o lugar “\1” não existe no documento"),
    (r"^(b\w+) está fora do trecho em que o pedido manda mexer", "a mudança cairia fora do trecho pedido"),
    (r"^(b\w+) já está marcado para sair", "o parágrafo já está marcado para sair"),
)


def falha_para_gente(motivo: str) -> str:
    for padrao, troca in _FALHA_PARA_GENTE:
        if re.match(padrao, motivo):
            return re.sub(padrao, troca, motivo)
    return motivo


# ------------------------------------------ o que o modelo escreve, limpo

# "Nenhuma lacuna identificada", "Não há", "N/A": item que não diz nada.
RE_ITEM_VAZIO = re.compile(r"(?i)^\s*(?:n[aã]o\s+h[aá]\b|nenhum[a]?\b|sem\s+(?:lacunas?|pend[eê]ncias?|sugest)|"
                           r"nada\s+(?:a\s+|mais\s+)?(?:declarar|apontar|sugerir|alterar|mais)|n/?a\b|-+$|\.+$)")
# "Não fiz ajustes em outras cláusulas que não foram mencionadas", "apenas a ordem foi
# modificada": o modelo se justificando pelo que ninguém pediu.
RE_ITEM_GENERICO = re.compile(r"(?i)n[aã]o\s+(?:foram|foi)\s+(?:especificamente\s+|expressamente\s+)?"
                              r"(?:mencionad|solicitad|pedid)|al[eé]m\s+do\s+(?:que\s+foi\s+)?(?:pedido|solicitado)|"
                              r"apenas\s+(?:a|o|as|os)\s+[^.]{0,60}\s+(?:foi|foram)\s+(?:modificad|alterad)|"
                              r"nada\s+mais\s+(?:foi|ser[aá])|conforme\s+(?:o\s+)?solicitado|"
                              r"sem\s+(?:solicitar|pedir)\s+(?:altera|mudan)|o\s+pedido\s+(?:apenas|s[oó])\s+(?:forneceu|trouxe)")
RE_NOME_DE_BLOCO = re.compile(r"\b(?:(do|da|dos|das|de|no|na|nos|nas|o|a|os|as)\s+)?(?:blocos?\s+)?"
                              r"(b(?=[0-9a-f]*\d)[0-9a-f]{6,7})\b", re.I)


def _rotulo_no_lugar(m: re.Match, rotulos: dict) -> str:
    """"do bloco b0b0008" → "da Cláusula 2ª"; "no bloco" → "na"; "o bloco" → "a": a preposição com o artigo do rótulo."""
    rotulo = rotulos.get(m.group(2), "")
    if not rotulo:
        return "outro trecho" if not m.group(1) else m.group(1) + " outro trecho"
    prep = (m.group(1) or "").lower()
    if prep in ("do", "da", "dos", "das", "de"):
        return ED.de_rotulo(rotulo)
    if prep in ("no", "na", "nos", "nas"):
        return "n" + ED.de_rotulo(rotulo)[1:]
    if prep in ("o", "a", "os", "as"):
        return ED.a_rotulo(rotulo)
    return rotulo


def _limpar_texto_do_modelo(texto: str, rotulos: dict) -> str:
    """O nome interno do bloco (b0b0008) vira o rótulo (Cláusula 2ª); espaços e pontas arrumados."""
    t = " ".join(str(texto or "").split()).strip(" ;")
    t = RE_NOME_DE_BLOCO.sub(lambda m: _rotulo_no_lugar(m, rotulos), t)
    t = re.sub(r"(Cláusula \d+ª|Preâmbulo|Fecho|Assinaturas)(?:\s+e\s+\1)+", r"\1", t)
    return t[:1].upper() + t[1:] if t else ""


def _limpar_itens(itens: list, rotulos: dict, rotulo: str = "") -> list[str]:
    """
    Os "não fiz", "lacunas" e "talvez" do modelo, só com o que diz alguma
    coisa: sem o item vazio ("Nenhuma lacuna identificada"), sem a justificativa
    pelo que não foi pedido, sem o rótulo repetido ("Não fiz: Não fiz..." e
    "Talvez você queira...: Talvez seja necessário...") e sem nome de bloco.
    """
    saida: list[str] = []
    for x in itens or []:
        t = _limpar_texto_do_modelo(str(x), rotulos)
        t = re.sub(r"(?i)^n[aã]o\s+fiz\s*[:,\-–]?\s*", "", t)
        t = re.sub(r"(?i)^talvez\s+(?:seja\s+(?:necess[aá]rio|bom|preciso|interessante)|voc[eê]\s+queira|devesse(?:\s+ser)?|"
                   r"fosse\s+(?:bom|o\s+caso\s+de))\s*", "", t)
        t = re.sub(r"(?i)^(?:verificar|conferir)\s+se\s+", "conferir se ", t)
        t = t.strip(" .;")
        if not t or RE_ITEM_VAZIO.match(t) or RE_ITEM_GENERICO.search(t):
            continue
        t = t[:1].upper() + t[1:]
        if t not in saida:
            saida.append(t)
    return saida


# ------------------------------------------------------------- a revisão

def _consertos(a: dict, mapa: dict, rotulos: dict) -> list[tuple[dict, str]]:
    """
    As correções seguras do que a conferência achou, como sugestão: tirar a
    cópia repetida, pôr a cláusula antes do fecho, acertar o número dos itens,
    separar o corpo da cabeça. O resto (valor, referência, lei) fica para o
    advogado decidir.
    """
    def curto(bid: str, n: int = 40) -> str:
        t = " ".join((mapa[bid].texto if bid in mapa else "").split())
        return t if len(t) <= n else t[: n - 1].rsplit(" ", 1)[0] + "…"

    regra, titulo, blocos_ = a.get("regra"), a.get("titulo"), [b for b in a.get("blocos") or [] if b in mapa]
    if regra == "repetido" and blocos_:
        if len(blocos_) > 1:
            return [({"op": "apagar", "blocos": blocos_},
                     f"Tirei a cópia repetida, de “{curto(blocos_[0])}” a “{curto(blocos_[-1])}” ({len(blocos_)} parágrafos)")]
        if len(mapa[blocos_[0]].texto) >= 120:
            return [({"op": "apagar", "bloco": blocos_[0]}, f"Tirei o parágrafo repetido “{curto(blocos_[0], 60)}”")]
        return []
    if titulo == "Cláusula depois do fecho" and blocos_ and a.get("antes_de") in mapa:
        return [({"op": "mover", "blocos": blocos_, "antes_de": a["antes_de"]},
                 f"Pus a {a.get('rotulo') or 'cláusula'} antes do fecho e das assinaturas")]
    if titulo == "Itens com o número de outra cláusula":
        return [({"op": "reescrever", "bloco": i["bloco"], "texto": i["texto"]}, "")
                for i in a.get("itens") or [] if i.get("bloco") in mapa]
    if titulo == "Cabeça com o corpo junto" and a.get("bloco") in mapa and a.get("cabeca") and a.get("corpo"):
        # Os itens do corpo seguem o número da cláusula ("2.1" na Cláusula 3ª vira "3.1").
        n = E._numero_da_clausula(a["cabeca"])[0]
        corpo = [re.sub(r"^(\s*)\d{1,3}\.(?=\d)", rf"\g<1>{n}.", t) if n else t for t in a["corpo"]]
        return [({"op": "reescrever", "bloco": a["bloco"], "texto": a["cabeca"]}, ""),
                ({"op": "inserir", "depois_de": a["bloco"], "blocos": [{"texto": t} for t in corpo]}, "")]
    return []


def _mensagens_de_leitura(blocos: list, pedido: str, titulo: str, foco: list | None = None) -> list[dict]:
    rotulos = E.rotulos(blocos)
    vivos = [b for b in blocos if b.sug != "del"]
    inteiro = B.para_modelo(vivos, rotulos=rotulos, limite=90000)
    onde = f"\nO PEDIDO É SOBRE: {', '.join(rotulos.get(i, '') for i in foco or [] if rotulos.get(i))}" if foco else ""
    return [{"role": "system", "content": SISTEMA_LEITURA},
            {"role": "user", "content": f"DOCUMENTO: {titulo}\n\nESBOÇO:\n{E.resumo(vivos)}\n\n{inteiro}\n\n"
                                        f"PEDIDO DO ADVOGADO: {pedido}{onde}"}]


def _aplicar_uma(atual: list, op: dict, rodada: int, original: list, ent: Entendimento,
                 selecao: dict | None) -> tuple[list, dict | None, dict | None, list]:
    escopo = ent.foco if ent.restrito else None
    r = ED.aplicar(atual, [op], rodada=rodada, escopo=escopo, selecao=selecao, em_tudo=ent.em_tudo, original=original)
    feito = r.aplicadas[0] if r.aplicadas else None
    falha = r.falhas[0] if r.falhas else None
    return r.blocos, feito, falha, r.comentarios


# "30 (trinta) dias", "24 meses", "3 (três) aluguéis": o número, o extenso e a unidade.
RE_QUANTIDADE = re.compile(
    r"(?i)(?<![\d.,])(\d{1,4})\s*(?:\([^)]{1,60}\)\s*)?"
    r"(dias?|m[eê]s(?:es)?|anos?|semanas?|horas?|parcelas?|presta[cç](?:[aã]o|[oõ]es)|alugu(?:el|[eé]is)|sal[aá]rios?)\b")
_UNIDADES = (("dia", "dia", "dias"), ("m", "mes", "meses"), ("ano", "ano", "anos"), ("semana", "semana", "semanas"),
             ("hora", "hora", "horas"), ("parcela", "parcela", "parcelas"), ("presta", "prestacao", "prestações"),
             ("alugu", "aluguel", "aluguéis"), ("sal", "salario", "salários"))


def _quantidades(texto: str) -> set[tuple[int, str]]:
    saida = set()
    for numero, unidade in RE_QUANTIDADE.findall(texto or ""):
        u = unidade.lower()
        saida.add((int(numero), next(nome for inicio, nome, _ in _UNIDADES if u.startswith(inicio))))
    return saida


def _numero_em_outra_unidade(op: dict, atual: list, pedidas: set, rotulos: dict) -> str:
    """
    A regra 2 do SISTEMA, conferida pelo programa: número igual não é o mesmo
    dado. O pedido fala de "24 meses" e a operação põe o 24 em outra unidade
    ("24 dias", no parágrafo seguinte): ela não entra e vira sugestão, para o
    advogado decidir. Devolve a sugestão ("" quando a operação passa).
    """
    if not pedidas or op.get("op") not in ("substituir", "substituir_em_tudo", "reescrever"):
        return ""
    if op.get("op") == "reescrever":
        bloco = B.por_id(atual).get(str(op.get("bloco") or ""))
        de, para = (bloco.texto if bloco else ""), str(op.get("texto") or "")
    else:
        de, para = str(op.get("de") or ""), str(op.get("para") or "")
    unidades: dict[int, set] = {}
    for n, u in pedidas:
        unidades.setdefault(n, set()).add(u)
    for n, u in sorted(_quantidades(para) - _quantidades(de)):
        if n in unidades and u not in unidades[n]:
            pedida = next(plural for _, nome, plural in _UNIDADES if nome in unidades[n])
            onde = rotulos.get(str(op.get("bloco") or ""), "")
            de_curto, _ = ED._o_que_mudou(de, para)
            return (f"{onde + ': ' if onde else ''}“{de_curto}” ficou como estava - o pedido fala de {n} {pedida}, "
                    "e este é outro dado")
    return ""


# ------------------------------------------- o dado novo que o pedido traz

# Nome próprio: duas palavras com maiúscula ou mais ("Juliana Torres Pereira", "Rua da Bahia").
RE_NOME_PROPRIO = re.compile(r"[A-ZÁÉÍÓÚÂÊÔÃÕÀÇ][\wÀ-ÿ'’-]*(?:\s+(?:(?:de|da|do|dos|das|e)\s+)?"
                             r"[A-ZÁÉÍÓÚÂÊÔÃÕÀÇ][\wÀ-ÿ'’-]*)+")
RE_REAIS = re.compile(r"R\$\s*(\d{1,3}(?:\.\d{3})+(?:,\d{2})?|\d+(?:,\d{2})?)")
RE_DATA_POR_EXTENSO = re.compile(r"(?i)\b(\d{1,2})º?\s+de\s+(janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|"
                                 r"setembro|outubro|novembro|dezembro)\s+de\s+(\d{4})\b")
_LIGA_NOME = ("de", "da", "do", "dos", "das", "e")
# "Cláusula Segunda", "Parágrafo Único", "Lei do Inquilinato": com maiúscula,
# mas apontam o lugar ou a lei - não são dado para escrever (a lei vai pelo número).
_REFERENCIA = {"clausula", "paragrafo", "inciso", "alinea", "item", "capitulo", "secao", "titulo", "anexo", "lei",
               "codigo", "constituicao", "sumula", "decreto", "resolucao", "estatuto", "portaria", "instrucao",
               "emenda", "medida", "tema"}


def _plano(texto: str) -> str:
    return " ".join(E.plano(texto).split())


def _reais(numero: str) -> float:
    return float(numero.replace(".", "").replace(",", "."))


def dados_do_pedido(pedido: str) -> list[tuple[str, str, object]]:
    """
    Os dados que o pedido traz - nomes próprios, valores em reais, datas por
    extenso e quantidades com unidade -, como (o jeito de dizer, o tipo, a chave
    para comparar com o texto).
    """
    pedido = pedido or ""
    dados: list[tuple[str, str, object]] = []
    for m in RE_NOME_PROPRIO.finditer(pedido):
        palavras = m.group(0).split()
        # No começo da frase, a primeira maiúscula pode ser só a do começo
        # ("Troque", "Em"): fica o resto, se o resto ainda é nome.
        antes = pedido[:m.start()].rstrip()
        if not antes or antes[-1] in ".!?:;“\"(":
            palavras = palavras[1:]
            while palavras and palavras[0].lower() in _LIGA_NOME:
                palavras = palavras[1:]
        if sum(1 for p in palavras if p[:1].isupper()) >= 2 and _plano(palavras[0]) not in _REFERENCIA:
            nome = " ".join(palavras)
            dados.append((nome, "nome", _plano(nome)))
    for m in RE_REAIS.finditer(pedido):
        dados.append((m.group(0), "reais", _reais(m.group(1))))
    for m in RE_DATA_POR_EXTENSO.finditer(pedido):
        dados.append((m.group(0), "data", (int(m.group(1)), _plano(m.group(2)), int(m.group(3)))))
    for n, u in sorted(_quantidades(pedido)):
        dados.append((f"{n} {next(pl for _, nome, pl in _UNIDADES if nome == u)}", "quantidade", (n, u)))
    return dados


def _tem(texto: str, tipo: str, chave) -> bool:
    if tipo == "nome":
        return chave in _plano(texto)
    if tipo == "reais":
        return chave in {_reais(v) for v in RE_REAIS.findall(texto)}
    if tipo == "data":
        return chave in {(int(d), _plano(m), int(a)) for d, m, a in RE_DATA_POR_EXTENSO.findall(texto)}
    return chave in _quantidades(texto)


def faltou_do_pedido(pedido: str, antes: str, depois: str) -> list[str]:
    """
    O dado novo do pedido (que o documento não tinha) e que ainda não está no
    texto depois da edição: "casado com Juliana Torres Pereira" e o nome dela
    não entrou. O que o documento já tinha não conta - pode ser o que saiu.
    """
    return list(dict.fromkeys(dizer for dizer, tipo, chave in dados_do_pedido(pedido)
                              if not _tem(antes, tipo, chave) and not _tem(depois, tipo, chave)))


def rodar(chamar, blocos: list, pedido: str, *, rodada: int, titulo: str = "", selecao: dict | None = None,
          nivel: str = "advogado", regras: str = "", memoria: str = "", artigos: str = "", parar=None,
          fichas=None, leis=None, casa: str = "", conversa: str = ""):
    """
    A rodada inteira, como eventos:
      ("etapa", {"id", "titulo", "estado"})
      ("nota", {"texto"})                      o bastidor
      ("remendo", {"remendos": [...], "resumo": "..."})   uma mudança entrando
      ("token", {"t"})                         a resposta da pergunta, ao vivo
      ("fim", {"rodada": Rodada})
    """
    from habilidade_base import Ponte

    inicio = time.time()
    r = Rodada(numero=rodada, pedido=pedido)
    original = copy.deepcopy(blocos)
    atual = copy.deepcopy(blocos)
    ent = entender(blocos, pedido, selecao)
    r.tipo = ent.tipo
    pedidas = _quantidades(pedido)
    rotulos_de_antes = E.rotulos(original) if pedidas else {}

    def barrar(op: dict) -> str:
        barrado = _numero_em_outra_unidade(op, atual, pedidas, rotulos_de_antes)
        if barrado:
            r.sugestoes.insert(0, barrado)
        return barrado

    def aplicar(op: dict, resumo: str = ""):
        """Aplica uma operação e manda o remendo; devolve o que foi feito (ou None)."""
        nonlocal atual
        antes = atual
        atual, feito, falha, comentarios = _aplicar_uma(atual, op, rodada, original, ent, selecao)
        r.comentarios += comentarios
        if feito:
            if resumo:
                feito["resumo"] = resumo
            r.aplicadas.append(feito)
            yield ("remendo", {"remendos": B.remendos(antes, atual), "resumo": feito["resumo"], "sids": feito["sids"]})
        elif falha:
            r.falhas.append({**falha, "operacao": op})
        return feito

    def renumerar_se_precisar():
        nonlocal atual
        if ED.precisa_renumerar(atual):
            antes = copy.deepcopy(atual)
            feito = ED.renumerar(atual, rodada)
            if feito:
                r.aplicadas.append(feito)
                yield ("remendo", {"remendos": B.remendos(antes, atual), "resumo": feito["resumo"], "sids": feito["sids"]})

    yield ("etapa", {"id": "entender", "titulo": "Entender o pedido", "estado": "concluido"})
    if ent.rotulos:
        yield ("nota", {"texto": "o pedido aponta para " + ", ".join(ent.rotulos)})
    if ent.tipo in ("concluir", "desfazer", "aceitar", "recusar", "confirmar"):
        r.blocos = atual
        r.segundos = time.time() - inicio
        yield ("fim", {"rodada": r})
        return

    if ent.tipo == "revisar":
        import conferencia_juridica as CJ

        yield ("etapa", {"id": "revisar", "titulo": "Revisar o documento", "estado": "executando"})
        avisos = CJ.conferir(atual, fichas=fichas, leis=leis)
        if ent.foco:
            avisos = [a for a in avisos if a.get("bloco") in set(ent.foco)]
        mapa, rotulos = B.por_id(atual), E.rotulos(atual)
        consertados: set[int] = set()
        # A ordem importa: tirar o repetido, depois mover (pelos blocos de antes),
        # depois acertar o número dos itens e separar o corpo da cabeça.
        ordem = {"repetido": 0, "Cláusula depois do fecho": 1, "Itens com o número de outra cláusula": 2,
                 "Cabeça com o corpo junto": 3}
        # Mover cria a cópia no lugar novo (e marca a original para sair): o
        # conserto seguinte da mesma cláusula vai na cópia.
        novos_nomes: dict[str, str] = {}

        def traduzir(op: dict) -> dict:
            t = dict(op)
            for k in ("bloco", "depois_de", "antes_de"):
                if t.get(k) in novos_nomes:
                    t[k] = novos_nomes[t[k]]
            if isinstance(t.get("blocos"), list) and all(isinstance(x, str) for x in t["blocos"]):
                t["blocos"] = [novos_nomes.get(x, x) for x in t["blocos"]]
            return t

        for i, a in sorted(enumerate(avisos), key=lambda x: ordem.get(x[1].get("regra"), ordem.get(x[1].get("titulo"), 9))):
            feitos = []
            for op, resumo in _consertos(a, mapa, rotulos):
                feito = yield from aplicar(traduzir(op), resumo)
                if feito:
                    feitos.append(feito)
                    if feito.get("tipo") == "mover":
                        ids = feito.get("ids", [])
                        novos_nomes.update(zip(ids[:len(ids) // 2], ids[len(ids) // 2:]))
                    mapa = B.por_id(atual)
            if len(feitos) > 1:
                # Os itens renumerados, o corpo separado: uma mudança só, para aceitar ou recusar junto.
                juntos = {**feitos[0], "sids": [s for f in feitos for s in f["sids"]],
                          "ids": list(dict.fromkeys(i for f in feitos for i in f.get("ids", []))),
                          "resumo": (f"Acertei o número dos itens da {a.get('rotulo')}: agora são "
                                     + re.split(r": seriam? ", a.get("detalhe", ""))[-1].rstrip(".")
                                     if a.get("titulo", "").startswith("Itens") else
                                     f"Separei da cabeça da {a.get('rotulo')} o corpo dela ({len(a.get('corpo') or [])} "
                                     f"parágrafo{'s' if len(a.get('corpo') or []) != 1 else ''})")}
                r.aplicadas = [x for x in r.aplicadas if x not in feitos] + [juntos]
            if feitos:
                consertados.add(i)
        yield from renumerar_se_precisar()
        r.pontos = [{k: a.get(k, "") for k in ("bloco", "rotulo", "titulo", "detalhe", "grau")}
                    for i, a in enumerate(avisos) if i not in consertados]
        if not (parar and parar()):
            yield ("nota", {"texto": "lendo o documento inteiro, como revisor"})
            try:
                bruto = chamar(_mensagens_de_leitura(atual, pedido, titulo, ent.foco), json_mode=True, max_tokens=1800,
                               on_token=None)
                r.chamadas += 1
                vivos_ids, rot = {b.id for b in atual}, E.rotulos(atual)
                for p in (ler_json(bruto).get("pontos") or [])[:6]:
                    if not isinstance(p, dict):
                        continue
                    texto_p = _limpar_texto_do_modelo(p.get("texto") or "", rot)
                    bid = str(p.get("bloco") or "")
                    if texto_p and not RE_ITEM_VAZIO.match(texto_p):
                        r.leitura.append({"bloco": bid if bid in vivos_ids else "", "rotulo": rot.get(bid, ""),
                                          "texto": texto_p})
            except Exception as exc:  # noqa: BLE001 - a leitura é ajuda; sem ela, a revisão por regra vale
                yield ("nota", {"texto": f"a leitura do modelo não veio ({str(exc)[:80]})"})
        yield ("etapa", {"id": "revisar", "titulo": "Revisar o documento", "estado": "concluido"})
        r.blocos = atual
        r.segundos = time.time() - inicio
        yield ("fim", {"rodada": r})
        return

    if ent.tipo == "texto_colado":
        yield ("etapa", {"id": "comparar", "titulo": "Comparar com o texto colado", "estado": "executando"})
        ops, info = ED.comparar_com_texto(atual, pedido)
        r.colado = info
        rot = E.rotulos(atual)
        for op in ops:
            nome = rot.get(op.get("bloco") or op.get("depois_de") or "", "")
            resumo = {"reescrever": f"{nome}: como no texto colado",
                      "apagar": f"{nome}: não está no texto colado",
                      "inserir": f"Trecho do texto colado que não estava no documento, depois da {nome}"}.get(op["op"], "")
            yield from aplicar(op, resumo)
        yield from renumerar_se_precisar()
        yield ("etapa", {"id": "comparar", "titulo": "Comparar com o texto colado", "estado": "concluido"})
        r.blocos = atual
        r.segundos = time.time() - inicio
        yield ("fim", {"rodada": r})
        return

    if ent.tipo == "renumerar":
        feito = ED.renumerar(atual, rodada)
        if feito:
            r.aplicadas.append(feito)
            yield ("remendo", {"remendos": B.remendos(original, atual), "resumo": feito["resumo"], "sids": feito["sids"]})
        else:
            r.nao_fiz.append("as cláusulas já estão em sequência")
        r.blocos = atual
        r.segundos = time.time() - inicio
        yield ("fim", {"rodada": r})
        return

    if ent.tipo == "pergunta":
        yield ("etapa", {"id": "responder", "titulo": "Responder pelo documento", "estado": "executando"})
        msgs = mensagens_de_pergunta(blocos, pedido, titulo)
        ponte = Ponte(lambda empurrar: chamar(msgs, json_mode=False, max_tokens=1500, on_token=empurrar), parar=parar)
        partes = []
        for pedaco in ponte:
            partes.append(pedaco)
            yield ("token", {"t": pedaco})
        r.chamadas += 1
        r.resposta = "".join(partes).strip()
        vivos = {b.id for b in blocos}
        # "[b0b0008]" ou "[b0b0008 · Cláusula 2ª]" (o modelo copia o formato
        # das linhas do documento): fica só o nome, que a tela vira atalho.
        r.resposta = RE_CITACAO.sub(lambda m: f"[{m.group(1)}]", r.resposta)
        r.citados = [c for c in dict.fromkeys(RE_CITACAO.findall(r.resposta)) if c in vivos]
        r.blocos = atual
        r.segundos = time.time() - inicio
        yield ("etapa", {"id": "responder", "titulo": "Responder pelo documento", "estado": "concluido"})
        yield ("fim", {"rodada": r})
        return

    # ------------------------------------------------ a regra (sem modelo)
    if ent.regra:
        for op in ent.regra:
            antes = atual
            atual, feito, falha, _ = _aplicar_uma(atual, op, rodada, original, ent, selecao)
            if feito:
                r.aplicadas.append(feito)
                yield ("remendo", {"remendos": B.remendos(antes, atual), "resumo": feito["resumo"], "sids": feito["sids"]})
            elif falha:
                r.falhas.append(falha)
        r.entendi = ent.porque
    else:
        # ---------------------------------------------- o modelo, ao vivo
        yield ("etapa", {"id": "editar", "titulo": "Editar o documento", "estado": "executando"})
        msgs = mensagens_de_edicao(blocos, ent, pedido, titulo=titulo, selecao=selecao, regras=regras, memoria=memoria,
                                   artigos=artigos, casa=casa, conversa=conversa)
        teto = {"estagiario": 2500, "bacharel": 3500, "advogado": 5000, "juiz": 6000, "ministro": 7000}.get(nivel, 5000)
        leitor = LeitorDeOperacoes()
        ponte = Ponte(lambda empurrar: chamar(msgs, json_mode=True, max_tokens=teto, on_token=empurrar), parar=parar)
        primeira = True
        for pedaco in ponte:
            for op in leitor.entrar(pedaco):
                if primeira:
                    yield ("nota", {"texto": f"a primeira mudança chegou em {time.time() - inicio:.1f} s"})
                    primeira = False
                if barrar(op):
                    yield ("nota", {"texto": "uma troca ficou de fora: punha o número do pedido em outro dado"})
                    continue
                antes = atual
                atual, feito, falha, comentarios = _aplicar_uma(atual, op, rodada, original, ent, selecao)
                r.comentarios += comentarios
                if feito:
                    r.aplicadas.append(feito)
                    yield ("remendo", {"remendos": B.remendos(antes, atual), "resumo": feito["resumo"],
                                       "sids": feito["sids"]})
                elif falha:
                    r.falhas.append({**falha, "operacao": op})
        r.chamadas += 1
        dados = ler_json(ponte.resultado if isinstance(ponte.resultado, str) else leitor.texto)
        r.entendi = " ".join(str(dados.get("entendi") or "").split())[:300]
        # O que o modelo escreve para o advogado, limpo: sem o item vazio ("Nenhuma lacuna"),
        # sem a justificativa pelo que não foi pedido e sem nome de bloco (13/10/2026).
        rotulos_ = E.rotulos(atual)
        r.nao_fiz += _limpar_itens(dados.get("nao_fiz"), rotulos_)[:6]
        r.lacunas += _limpar_itens(dados.get("lacunas"), rotulos_)[:12]
        r.sugestoes += _limpar_itens(dados.get("sugestoes"), rotulos_)[:6]
        # O que o leitor ao vivo não pegou (JSON torto no meio) entra agora.
        for op in (dados.get("operacoes") or [])[leitor.lidas:]:
            if isinstance(op, dict) and not barrar(op):
                antes = atual
                atual, feito, falha, comentarios = _aplicar_uma(atual, op, rodada, original, ent, selecao)
                r.comentarios += comentarios
                if feito:
                    r.aplicadas.append(feito)
                    yield ("remendo", {"remendos": B.remendos(antes, atual), "resumo": feito["resumo"],
                                       "sids": feito["sids"]})
                elif falha:
                    r.falhas.append({**falha, "operacao": op})
        if r.entendi:
            yield ("nota", {"texto": "entendi: " + r.entendi})

        # ---------------------------------- corrigir o que não passou
        tentativas = 2 if nivel in ("juiz", "ministro") else 1
        while r.falhas and tentativas and not (parar and parar()):
            tentativas -= 1
            pendentes = [f for f in r.falhas if f.get("operacao")]
            if not pendentes:
                break
            yield ("nota", {"texto": f"{len(pendentes)} operação(ões) não bateram com o texto; pedindo a correção"})
            msgs_c = _mensagens_de_correcao(msgs, atual, pendentes)
            bruto = chamar(msgs_c, json_mode=True, max_tokens=3000, on_token=None)
            r.chamadas += 1
            r.falhas = [f for f in r.falhas if not f.get("operacao")]
            for op in (ler_json(bruto).get("operacoes") or []):
                if not isinstance(op, dict) or barrar(op):
                    continue
                antes = atual
                atual, feito, falha, comentarios = _aplicar_uma(atual, op, rodada, original, ent, selecao)
                r.comentarios += comentarios
                if feito:
                    r.aplicadas.append(feito)
                    yield ("remendo", {"remendos": B.remendos(antes, atual), "resumo": feito["resumo"],
                                       "sids": feito["sids"]})
                elif falha:
                    r.falhas.append({**falha, "operacao": op})

        # ----------------------- o dado novo do pedido que não entrou
        texto_de_antes = B.texto_puro(original)
        faltam = faltou_do_pedido(pedido, texto_de_antes, B.texto_puro(B.aceito(atual))) if r.aplicadas else []
        if faltam and not (parar and parar()):
            yield ("nota", {"texto": "faltou do pedido: " + "; ".join(faltam) + " - pedindo o que falta"})
            bruto = chamar(_mensagens_do_que_faltou(msgs, atual, faltam, r.aplicadas), json_mode=True, max_tokens=3000,
                           on_token=None)
            r.chamadas += 1
            complemento = ler_json(bruto)
            r.nao_fiz += [" ".join(str(x).split()) for x in (complemento.get("nao_fiz") or []) if str(x).strip()][:3]
            for op in (complemento.get("operacoes") or []):
                if not isinstance(op, dict) or barrar(op):
                    continue
                antes = atual
                atual, feito, falha, comentarios = _aplicar_uma(atual, op, rodada, original, ent, selecao)
                r.comentarios += comentarios
                if feito:
                    r.aplicadas.append(feito)
                    yield ("remendo", {"remendos": B.remendos(antes, atual), "resumo": feito["resumo"],
                                       "sids": feito["sids"]})
            r.nao_fiz += [f"o pedido traz “{x}”, que não entrou no texto"
                          for x in faltou_do_pedido(pedido, texto_de_antes, B.texto_puro(B.aceito(atual)))]
        yield ("etapa", {"id": "editar", "titulo": "Editar o documento", "estado": "concluido"})

    # --------------------------------------------------------- conferir
    yield ("etapa", {"id": "conferir", "titulo": "Conferir", "estado": "executando"})
    if r.aplicadas and ED.precisa_renumerar(atual):
        # renumerar muda os blocos no lugar: o "antes" do remendo é uma cópia.
        antes = copy.deepcopy(atual)
        feito = ED.renumerar(atual, rodada)
        if feito:
            r.aplicadas.append(feito)
            yield ("remendo", {"remendos": B.remendos(antes, atual), "resumo": feito["resumo"], "sids": feito["sids"]})
    r.avisos += conferir_rodada(original, atual, r, fichas=fichas, leis=leis)
    if r.aplicadas and nivel in ("juiz", "ministro") and not (parar and parar()):
        yield ("nota", {"texto": "segunda leitura: conferindo o que mudou contra o pedido e o resto do documento"})
        try:
            bruto = chamar(_mensagens_de_revisao(pedido, original, atual), json_mode=True, max_tokens=2500, on_token=None)
            r.chamadas += 1
            revisao = ler_json(bruto)
        except Exception:  # noqa: BLE001 - a segunda leitura é ajuda; sem ela, a rodada vale
            revisao = {}
        for problema in (revisao.get("problemas") or [])[:6]:
            if str(problema).strip():
                r.avisos.append("revisão: " + " ".join(str(problema).split())[:240])
        for op in (revisao.get("operacoes") or [])[:6]:
            if not isinstance(op, dict) or barrar(op):
                continue
            antes = atual
            atual, feito, falha, _ = _aplicar_uma(atual, op, rodada, original, ent, selecao)
            if feito:
                feito["resumo"] = "Revisão: " + feito["resumo"]
                r.aplicadas.append(feito)
                yield ("remendo", {"remendos": B.remendos(antes, atual), "resumo": feito["resumo"], "sids": feito["sids"]})
    yield ("etapa", {"id": "conferir", "titulo": "Conferir", "estado": "concluido"})
    r.blocos = atual
    r.segundos = time.time() - inicio
    yield ("fim", {"rodada": r})


def _mensagens_de_correcao(msgs: list[dict], atual: list, pendentes: list[dict]) -> list[dict]:
    """A segunda chance: o que não bateu, com o texto exato de cada bloco envolvido."""
    mapa = B.por_id(atual)
    linhas = []
    for f in pendentes[:8]:
        op = f["operacao"]
        bid = str(op.get("bloco") or op.get("depois_de") or op.get("antes_de") or "")
        linhas.append(f"- {json.dumps(op, ensure_ascii=False)[:600]}\n  problema: {f['motivo']}")
        if bid in mapa:
            linhas.append(f"  texto EXATO de {bid} agora: \"{mapa[bid].texto[:1500]}\"")
            # "confessar, renunciar ao direito": cada pedaço está no bloco, mas
            # não um ao lado do outro - o programa diz isso com todas as letras.
            pedacos = [p.strip(" .") for p in re.split(r"[,;]|\s+e\s+", str(op.get("de") or "")) if len(p.strip(" .")) >= 4]
            if len(pedacos) > 1 and all(B.achar(mapa[bid].texto, p) for p in pedacos):
                linhas.append("  os pedaços estão no bloco, mas separados: faça uma operação para cada um (" +
                              "; ".join(f"“{p}”" for p in pedacos[:6]) + ")")
    pedido = ("Estas operações não puderam ser aplicadas:\n" + "\n".join(linhas) +
              "\n\nDevolva só as operações corrigidas (copie o trecho \"de\" letra por letra do texto do bloco), no "
              "mesmo formato: {\"operacoes\": [...]}. O \"de\" é um pedaço contínuo do bloco: se o que você quer "
              "mudar ou tirar está em pontos separados, faça uma operação para cada ponto. Se a correção não for "
              "possível, \"operacoes\": [].")
    return msgs + [{"role": "assistant", "content": "{\"operacoes\": [...]}"}, {"role": "user", "content": pedido}]


def _mensagens_do_que_faltou(msgs: list[dict], atual: list, faltam: list[str], aplicadas: list[dict]) -> list[dict]:
    """O dado novo do pedido que não entrou: o modelo devolve só as operações que faltam."""
    mapa = B.por_id(atual)
    ids = list(dict.fromkeys(i for a in aplicadas for i in a.get("ids", []) if i in mapa))[:6]
    linhas = [f"[{i}] \"{mapa[i].texto[:1500]}\"" for i in ids]
    pedido = ("Depois das suas operações, o documento ainda não traz estes dados do pedido: " +
              "; ".join(f"“{x}”" for x in faltam) + "." +
              ("\nTexto EXATO, agora, dos blocos que você mudou:\n" + "\n".join(linhas) if linhas else "") +
              "\n\nO advogado deu esses dados no pedido para que entrem no documento. Devolva as operações que faltam "
              "para eles entrarem no lugar certo (copie o \"de\" letra por letra do texto do bloco), no formato "
              "{\"operacoes\": [...], \"nao_fiz\": [...]}. Só deixe de fora o dado que o pedido cita como referência, "
              "sem mandar escrever, e diga por quê em \"nao_fiz\".")
    return msgs + [{"role": "assistant", "content": "{\"operacoes\": [...]}"}, {"role": "user", "content": pedido}]


def _mensagens_de_revisao(pedido: str, antes: list, depois: list) -> list[dict]:
    a = {b.id: b for b in antes}
    d = {b.id: b for b in B.aceito(depois)}
    linhas = []
    for bid, b in d.items():
        if bid not in a:
            linhas.append(f"[{bid} · NOVO] {b.texto}")
        elif a[bid].texto != b.texto:
            linhas.append(f"[{bid} · ANTES] {a[bid].texto}\n[{bid} · DEPOIS] {b.texto}")
    for bid, b in a.items():
        if bid not in d:
            linhas.append(f"[{bid} · APAGADO] {b.texto}")
    rotulos = E.rotulos(B.aceito(depois))
    contexto = B.para_modelo(B.aceito(depois), rotulos=rotulos, limite=60000)
    return [{"role": "system", "content": SISTEMA_REVISAO},
            {"role": "user", "content": f"PEDIDO: {pedido}\n\nO QUE MUDOU:\n" + "\n".join(linhas)[:20000] +
                                        f"\n\nO DOCUMENTO COMO FICOU:\n{contexto}"}]


def conferir_rodada(antes: list, depois: list, r: Rodada, fichas=None, leis=None) -> list[str]:
    """
    A conferência jurídica (src/conferencia_juridica.py) do documento como
    ficaria, contra o de antes da rodada: só o que ESTA rodada criou - valor
    que não bate com o extenso, referência que mudou de cláusula, termo sem
    definição, artigo que não existe, lacuna nova.
    """
    import conferencia_juridica as CJ

    try:
        novos = CJ.novos(CJ.conferir(antes, fichas=fichas, leis=leis),
                         CJ.conferir(depois, fichas=fichas, leis=leis, antes=antes))
    except Exception:  # noqa: BLE001 - a conferência é ajuda; sem ela, a rodada vale
        return []
    r.conferencia = novos
    return [(f"{a['rotulo']}: " if a.get("rotulo") else "") + a["detalhe"].rstrip(".") for a in novos[:6]]


# ------------------------------------------------------------ a resposta

def titulo_legivel(titulo: str) -> str:
    """“CONTRATO DE COMPRA E VENDA” → “Contrato de compra e venda”: o título em maiúsculas lido como frase."""
    t = " ".join(str(titulo or "").split())
    letras = [c for c in t if c.isalpha()]
    if letras and sum(1 for c in letras if c.isupper()) / len(letras) > 0.8:
        t = t.lower()
        t = t[:1].upper() + t[1:]
    return t


def resposta(r: Rodada, titulo: str = "") -> str:
    """
    A frase da conversa, montada do que a rodada fez de fato - o lugar de cada
    mudança, o que não deu e por quê, o que ficou para o advogado. É o texto
    guardado na conversa e lido pelo leitor de tela; a tela desenha o cartão da
    rodada (js/95-editor-inteligente.js) com os mesmos dados.
    """
    if r.tipo == "pergunta":
        return r.resposta or "Não achei a resposta no documento."
    doc = f"“{titulo_legivel(titulo)}”" if titulo else "o documento"
    linhas: list[str] = []
    feitas = [a for a in r.aplicadas if a.get("tipo") != "comentar"]
    comentadas = [a for a in r.aplicadas if a.get("tipo") == "comentar"]
    n = len(feitas)
    mudancas = f"{n} mudança{'s' if n != 1 else ''}"

    def lista(itens) -> str:
        # "; " entre os itens e um ponto só no fim, mesmo que o item já termine em ponto.
        return "; ".join(str(x).strip().rstrip(".") for x in itens) + "."

    if r.tipo == "revisar":
        pontos = len(r.pontos) + len(r.leitura)
        if feitas:
            linhas.append(f"Revisei {doc} e corrigi {n} ponto{'s' if n != 1 else ''}, como sugestão:")
        elif pontos:
            linhas.append(f"Revisei {doc}. Não mudei nada; ficaram {pontos} ponto{'s' if pontos != 1 else ''} "
                          "para você decidir.")
        else:
            linhas.append(f"Revisei {doc} e não achei problema: numeração, referências, valores e extensos, datas, "
                          "CPF e CNPJ, lacunas e estrutura em ordem.")
    elif r.tipo == "texto_colado":
        c = r.colado or {}
        if not feitas:
            return ("Esse texto não parece uma versão deste documento, então não mudei nada. Diga o que fazer com "
                    "ele - por exemplo, “insira isto depois da Cláusula 5ª”." if c.get("parecido", 0) < 0.5 else
                    "Comparei com o texto que você colou: é igual ao documento, não há diferença para marcar.")
        cobre = "" if c.get("cobre_tudo") or not c.get("de") else (
            f" O texto colado vai de {c.get('de')} a {c.get('ate')}; o resto do documento ficou como estava.")
        linhas.append(f"Comparei com o texto que você colou e marquei as diferenças: {mudancas}.{cobre}")
    elif feitas:
        linhas.append(f"Fiz {mudancas} em {doc}:")
    linhas += [f"- {a['resumo']}" for a in feitas]
    if comentadas:
        linhas.append(("Deixei " if not feitas else "E deixei ") + f"{len(comentadas)} comentário"
                      + ("s" if len(comentadas) > 1 else "") + " na margem.")
    if r.pontos:
        linhas.append("Para você conferir:")
        linhas += [f"- {p['rotulo'] + ': ' if p.get('rotulo') else ''}{p['titulo']}. {p['detalhe']}" for p in r.pontos]
    if r.leitura:
        linhas.append("Na leitura, como revisor:")
        linhas += [f"- {p['rotulo'] + ': ' if p.get('rotulo') else ''}{p['texto']}" for p in r.leitura]
    nao = [falha_para_gente(f["motivo"]) for f in r.falhas] + r.nao_fiz
    if nao:
        linhas.append("Não fiz: " + lista(dict.fromkeys(nao)))
    if r.lacunas:
        linhas.append("Ficou para preencher: " + lista(r.lacunas[:6]))
    if r.sugestoes:
        linhas.append("Vale olhar também (não mudei): " + lista(r.sugestoes[:4]))
    if r.avisos:
        linhas.append("Conferi: " + lista(r.avisos[:6]))
    if feitas:
        linhas.append("Cada mudança está marcada no texto: aceite ou recuse uma a uma, ou todas de uma vez.")
    if not feitas and not comentadas and not nao and r.tipo not in ("revisar", "texto_colado"):
        linhas.append("Não mudei nada: não achei no documento o que o pedido manda mudar.")
    return "\n".join(linhas)
