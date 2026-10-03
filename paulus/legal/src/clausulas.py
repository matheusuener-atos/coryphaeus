"""
Cláusula por cláusula (03/10/2026): o trabalho redigido junto com o advogado.

Pedido do dono, depois de ver um contrato de arrendamento "pequeno, sem
robustez jurídica" saído de uma vez só: o Paulus diz que vão fazer cláusula
por cláusula, juntos, começando pela qualificação das partes; cada cláusula
chega com "Aprovar" e "Corrigir" (os pontos ajustáveis daquela cláusula e um
campo livre); no fim, tudo é compilado num documento só. Quem insistir em
fazer de uma vez pode - a tela diz, com honestidade, o que se perde.

Antes de começar (a fase "preparo"):
- o plano das seções, com a qualificação das partes primeiro (regra daqui);
- as leis de que o trabalho depende: as que estão na Biblioteca (os códigos de
  `leis.CODIGOS`) entram pelo texto oficial; a que falta (o Estatuto da Terra,
  um decreto) o Paulus pede para anexar - ou segue sem ela, se a pessoa pular;
- o modelo já feito, se houver: anexado agora, ou um do Acervo.

O que vai em cada cláusula: o pedido, o que foi definido na entrevista, as
cláusulas já aprovadas (para não contradizer), os artigos da lei que tratam
do assunto daquela cláusula (da Biblioteca ou da lei anexada, por regra) e o
trecho do modelo que trata dele. Tudo pela nuvem, mascarado e registrado
(`nuvem.chamada`).
"""

from __future__ import annotations

import json
import re
import unicodedata

MAX_SECOES = 24
# Medido em 03/10 com o Llama 3.3 70B: sem meta, o plano de um arrendamento
# saiu com 8 cláusulas e cada cláusula com ~80 palavras. A meta diz o tamanho
# que um trabalho completo tem em cada nível - para não parar no esqueleto.
SECOES_POR_NIVEL = {"estagiario": "6 a 10", "bacharel": "8 a 12", "advogado": "12 a 18", "juiz": "15 a 22", "ministro": "18 a 24"}
PALAVRAS_POR_SECAO = {"estagiario": "60 a 150", "bacharel": "100 a 220", "advogado": "150 a 350", "juiz": "200 a 450",
                      "ministro": "250 a 550"}
SEPARADOR_PONTOS = "###PONTOS###"
# "faça tudo de uma vez", "o resto de uma vez", "pode fazer o contrato inteiro"
RE_TUDO = re.compile(r"(?i)\b(?:tudo|o resto|o restante|todas?(?: as cl[aá]usulas)?|(?:o )?(?:contrato|documento|texto) "
                     r"(?:inteiro|completo|todo))\b.{0,20}\b(?:de uma (?:s[oó] )?vez|direto|junt[oa]s?)\b"
                     r"|\bde uma vez s[oó]\b|\bfa[cç]a (?:tudo|o resto)\b")
RE_APROVA = re.compile(r"(?i)^\s*(?:ok|okay|aprovad[oa]|aprovo|aprova|pode seguir|segue|siga|pr[oó]xima|est[aá] (?:[oó]timo|bom|"
                       r"certo|perfeito)|perfeito|[oó]timo|beleza|isso)\W*$")


def _plano_txt(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or "").lower()) if unicodedata.category(c) != "Mn")


def _curto(v, n: int) -> str:
    return " ".join(str(v or "").split())[:n].strip()


def _ler_json(bruto: str) -> dict | None:
    try:
        d = json.loads(bruto)
    except (ValueError, TypeError):
        ini, fim = str(bruto or "").find("{"), str(bruto or "").rfind("}")
        if ini == -1 or fim <= ini:
            return None
        try:
            d = json.loads(bruto[ini:fim + 1])
        except ValueError:
            return None
    return d if isinstance(d, dict) else None


# ------------------------------------------------------------ o plano das seções

PLANO = """Planeje o trabalho em SEÇÕES, para redigi-lo uma de cada vez com o advogado. Responda só com JSON:
{{"titulo_documento": "CONTRATO DE ARRENDAMENTO RURAL", "unidade": "cláusula", \
"secoes": [{{"titulo": "Qualificação das partes", "objetivo": "quem são o arrendador e o arrendatário, com os \
campos de qualificação"}}, {{"titulo": "Do objeto", "objetivo": "..."}}], \
"leis": [{{"nome": "Estatuto da Terra (Lei 4.504/1964)", "codigo": ""}}]}}

- "unidade": "cláusula" para contrato, aditivo, acordo, termo, procuração; "seção" para petição, parecer, \
notificação e o resto.
- A PRIMEIRA seção é sempre a qualificação das partes (ou o endereçamento e a qualificação, numa peça).
- As seções que este trabalho exige por lei e as que protegem o cliente do escritório, na ordem em que \
aparecem no documento - completo, não um esqueleto: no nível {nivel}, um trabalho deste tipo tem de \
{quantas} seções (a qualificação, as obrigações de cada parte, as garantias, o que a lei exige, o \
descumprimento e suas consequências, o fim do contrato, o foro). Cada "objetivo" diz em uma frase o que a \
seção resolve, com o que já foi definido.
- "leis": as leis e os regulamentos de que o texto depende (até 5). "codigo": um destes, se for um deles, \
senão "": {codigos}."""


def planejar(estado, *, trabalho, pedido: str, briefing: str, nivel, pessoa=None, parar=None) -> dict | None:
    """O plano das seções, conferido (`conferir_plano`), ou None se a nuvem não respondeu."""
    import elaboracao
    import leis as leis_mod
    import nuvem
    import profundidade as profundidade_mod

    codigos = ", ".join(f'"{c}" ({d["nome"]})' for c, d in leis_mod.CODIGOS.items())
    usuario = elaboracao._base_do_pedido(pedido, briefing, ()) + "\n\n" + PLANO.format(nivel=nivel.nome, codigos=codigos,
                                                                                 quantas=SECOES_POR_NIVEL.get(nivel.id, "10 a 16"))
    mensagens = [{"role": "system", "content": elaboracao._sistema(nivel)}, {"role": "user", "content": usuario}]
    modelo = profundidade_mod.modelo_do_nivel(estado.prefs.dados, nivel, nuvem.config(estado).get("modelo") or "")
    try:
        bruto, _uso = nuvem.chamada(estado, mensagens, pessoa=pessoa, trabalho=trabalho, etapa="plano", pergunta=pedido,
                                    mascara=nuvem.Mascara() if nuvem.config(estado).get("mascarar", True) else None,
                                    json_mode=True, max_tokens=2500, parar=parar, modelo=modelo, profundidade=nivel.id)
    except nuvem.ErroNuvem:
        return None
    instalados = {i["codigo"] for i in (getattr(estado, "leis", None).instalados() if getattr(estado, "leis", None) else [])
                  if i.get("instalado")}
    return conferir_plano(_ler_json(bruto), instalados, pedido)


RE_QUALIF = re.compile(r"(?i)qualifica|partes|endere[cç]amento|pre[aâ]mbulo")


def conferir_plano(dados: dict | None, instalados=(), pedido: str = "") -> dict:
    """Seções com título e objetivo, a qualificação primeiro, no máximo 24; as leis com o que há na Biblioteca."""
    import leis as leis_mod

    dados = dados or {}
    secoes = []
    for s in dados.get("secoes") or []:
        if not isinstance(s, dict):
            continue
        titulo = _curto(s.get("titulo"), 80)
        if not titulo or any(_plano_txt(titulo) == _plano_txt(x["titulo"]) for x in secoes):
            continue
        secoes.append({"titulo": titulo, "objetivo": _curto(s.get("objetivo"), 300)})
    if not secoes or not RE_QUALIF.search(secoes[0]["titulo"]):
        secoes = [x for x in secoes if not RE_QUALIF.search(x["titulo"])]
        secoes.insert(0, {"titulo": "Qualificação das partes", "objetivo": "quem são as partes, com os campos de qualificação"})
    secoes = secoes[:MAX_SECOES]
    for i, s in enumerate(secoes):
        s["id"] = f"s{i + 1}"
    # Cláusula é de contrato; petição e parecer têm seções. Regra, e não o
    # modelo: "o parecer, cláusula 3" seria estranho para qualquer advogado.
    de_contrato = r"(?i)contrato|aditivo|distrato|acordo|termo de|procura[cç][aã]o"
    de_peca = r"(?i)peti[cç]|parecer|contesta|recurso|apela|agravo|notifica|r[eé]plica|memoria|requerimento|manifesta"
    if re.search(de_contrato, pedido):
        unidade = "cláusula"
    elif re.search(de_peca, pedido):
        unidade = "seção"
    else:
        unidade = "cláusula" if re.search(de_contrato, str(dados.get("titulo_documento") or "")) else "seção"
    leis = []
    for l in dados.get("leis") or []:
        if not isinstance(l, dict):
            continue
        nome = _curto(l.get("nome"), 120)
        codigo = str(l.get("codigo") or "").strip().lower()
        if codigo not in leis_mod.CODIGOS:
            codigo = ""
        if nome and not any(_plano_txt(nome) == _plano_txt(x["nome"]) for x in leis):
            leis.append({"nome": nome, "codigo": codigo, "na_biblioteca": bool(codigo and codigo in instalados)})
    return {"titulo_documento": _curto(dados.get("titulo_documento"), 120).upper(), "unidade": unidade,
            "secoes": secoes, "leis": leis[:5]}


def rotulo(plano: dict, i: int) -> str:
    """"QUALIFICAÇÃO DAS PARTES", "CLÁUSULA 3ª – DO PRAZO" ou o título da seção, em maiúsculas."""
    s = plano["secoes"][i]
    titulo = s["titulo"].upper()
    if i == 0 or plano.get("unidade") != "cláusula":
        return titulo
    titulo = re.sub(r"(?i)^cl[aá]usula\s+\S+\s*[-–:]\s*", "", titulo)
    return f"CLÁUSULA {i}ª – {titulo}"


# ------------------------------------------------------------ o material de cada seção

RE_ARTIGO = re.compile(r"(?m)^\s*Art\.?\s*\d+[º°o]?[-–A-Z]*\.?\s")


def e_lei(texto: str) -> bool:
    """Um texto de lei ou decreto (anexado), e não um modelo: muitos "Art. N" e o título de lei no começo."""
    t = str(texto or "")
    return len(RE_ARTIGO.findall(t)) >= 8 and bool(re.search(r"(?i)\b(lei|decreto|c[oó]digo)\b", t[:3000]))


def _palavras(texto: str) -> set[str]:
    return {p[:6] for p in re.findall(r"[a-z]{4,}", _plano_txt(texto))}


def artigos_relevantes(texto: str, consulta: str, k: int = 4, limite: int = 3500) -> str:
    """Os artigos da lei anexada que mais tratam do assunto da seção, por palavras em comum."""
    pos = [m.start() for m in RE_ARTIGO.finditer(texto or "")]
    if not pos:
        return ""
    alvo = _palavras(consulta)
    artigos = [texto[a:b].strip() for a, b in zip(pos, pos[1:] + [len(texto)])]
    pontuados = sorted(((len(alvo & _palavras(a)), i) for i, a in enumerate(artigos)), reverse=True)
    escolhidos = sorted(i for n, i in pontuados[:k] if n >= 2)
    saida = "\n\n".join(artigos[i][:1200] for i in escolhidos)
    return saida[:limite]


def trecho_do_modelo(texto: str, consulta: str, limite: int = 2500) -> str:
    """O pedaço do modelo que trata da seção: os parágrafos com mais palavras em comum, na ordem do modelo."""
    paragrafos = [p.strip() for p in re.split(r"\n\s*\n|\n(?=\s*(?:CL[AÁ]USULA|\d+[ªº.]))", texto or "") if len(p.strip()) > 40]
    if not paragrafos:
        return ""
    alvo = _palavras(consulta)
    pontuados = sorted(((len(alvo & _palavras(p)), i) for i, p in enumerate(paragrafos)), reverse=True)
    escolhidos = sorted(i for n, i in pontuados[:3] if n >= 2)
    return "\n\n".join(paragrafos[i] for i in escolhidos)[:limite]


def material_da_secao(estado, estado_e: dict, secao: dict) -> str:
    """O que vai junto da seção: a lei (da Biblioteca e anexada) e o modelo, só o que trata dela."""
    plano = estado_e.get("plano") or {}
    consulta = secao["titulo"] + " " + secao.get("objetivo", "") + " " + (estado_e.get("trabalho") or "")
    partes = []
    codigos = [l["codigo"] for l in plano.get("leis") or [] if l.get("codigo") and l.get("na_biblioteca")]
    leis = getattr(estado, "leis", None)
    if codigos and leis is not None:
        try:
            achados = [a for a in leis.procurar_assunto(consulta, limite=12) if a.get("codigo") in codigos][:4]
        except Exception:  # noqa: BLE001 - sem a busca, segue sem o bloco
            achados = []
        for a in achados:
            partes.append(f"LEI (texto oficial) - art. {a.get('numero')} ({a.get('codigo')}): {str(a.get('texto') or '')[:1200]}")
    docs = {d.name: d for d in getattr(estado.searcher, "documents", [])}
    for nome in estado_e.get("materiais") or []:
        d = docs.get(nome)
        if d is None:
            continue
        if e_lei(d.text):
            trecho = artigos_relevantes(d.text, consulta)
            if trecho:
                partes.append(f"LEI ANEXADA «{nome}» - os artigos sobre esta seção:\n{trecho}")
        else:
            trecho = trecho_do_modelo(d.text, consulta)
            if trecho:
                partes.append(f"MODELO «{nome}» - o trecho sobre esta seção (referência de estrutura e redação; "
                              f"não copie nomes, números nem valores dele):\n{trecho}")
    return "\n\n".join(partes)


# ------------------------------------------------------------ redigir uma seção

SISTEMA_SECAO = """

CLÁUSULA POR CLÁUSULA
Você está redigindo UMA seção de um trabalho jurídico, junto com o advogado: ele aprova ou corrige cada \
seção, e no fim tudo vira um documento só.
- Redija só a seção pedida, completa e robusta para o nível: caput e os parágrafos, incisos e alíneas que \
ela pede, com os mecanismos concretos (prazos, procedimento, consequência do descumprimento). Extensão: de \
{palavras} palavras (a qualificação das partes pode ser mais curta).
- Comece exatamente pelo título dado, em maiúsculas, na primeira linha.
- Não repita nem contradiga as seções já aprovadas; use os mesmos nomes de partes e termos definidos.
- Com o bloco LEI ou LEI ANEXADA, fundamente nele e respeite as vedações; o que a lei proíbe não entra (adapte \
e diga nos pontos). Com o bloco MODELO, siga a estrutura e o nível de detalhe dele, sem copiar dados.
- Dado não informado fica [●]. Texto simples, sem markdown, sem "Notas para o advogado".
- Depois do texto da seção, numa linha só, escreva {separador} e, abaixo, um JSON: {{"pontos": [{{"ponto": \
"Prazo de pagamento", "atual": "30 dias após a colheita", "alternativas": ["15 dias", "na entrega da \
safra"]}}], "aviso": ""}} - de 2 a 5 escolhas DESTA seção que o advogado pode querer ajustar (com o que \
você escolheu e alternativas reais); "aviso": em uma frase, se algo pedido esbarrou na lei e você adaptou, ou \
se faltou a lei para conferir; senão ""."""


def _pontos(bruto: str) -> tuple[list[dict], str]:
    d = _ler_json(bruto) or {}
    pontos = []
    for p in d.get("pontos") or []:
        if not isinstance(p, dict):
            continue
        ponto = _curto(p.get("ponto"), 60)
        if not ponto:
            continue
        alternativas = [_curto(a, 70) for a in (p.get("alternativas") or []) if _curto(a, 70)][:4]
        pontos.append({"ponto": ponto, "atual": _curto(p.get("atual"), 120), "alternativas": alternativas})
    return pontos[:5], _curto(d.get("aviso"), 300)


def redigir(estado, *, trabalho, estado_e: dict, nivel, indice: int, ajustes: dict | None = None, pessoa=None,
            parar=None):
    """
    Gerador: ("token", {"t"}) enquanto a seção é escrita (só o texto: o JSON
    dos pontos, depois do separador, não vai à tela). Devolve, no fim
    (StopIteration), {"texto", "pontos", "aviso"}. Erro da nuvem sobe.
    """
    import elaboracao
    import instrucao_nuvem
    import nuvem
    import profundidade as profundidade_mod
    from habilidade_base import Ponte

    plano = estado_e["plano"]
    secao = plano["secoes"][indice]
    titulo = rotulo(plano, indice)
    sistema = (instrucao_nuvem.instrucao()
               + SISTEMA_SECAO.format(separador=SEPARADOR_PONTOS, palavras=PALAVRAS_POR_SECAO.get(nivel.id, "150 a 350")) + "\n"
               + elaboracao.PROFUNDIDADE_REDACAO[nivel.id].split(" Extensão:")[0])
    partes = [elaboracao._base_do_pedido(estado_e.get("pedido", ""), _briefing(estado_e), ())]
    material = material_da_secao(estado, estado_e, secao)
    if material:
        partes.append(material)
    sumario = "\n".join(("-> " if i == indice else "   ") + rotulo(plano, i) + (": " + s["objetivo"] if s.get("objetivo") else "")
                        for i, s in enumerate(plano["secoes"]))
    partes.append("O PLANO (a seta marca a seção de agora):\n" + sumario)
    aprovadas = [estado_e["clausulas"][s["id"]]["texto"] for s in plano["secoes"][:indice]
                 if (estado_e.get("clausulas") or {}).get(s["id"], {}).get("status") == "aprovada"]
    if aprovadas:
        texto_aprovado = "\n\n".join(aprovadas)
        partes.append("SEÇÕES JÁ APROVADAS:\n" + texto_aprovado[-14000:])
    if ajustes:
        linhas = [f"- {a['ponto']}: {a['escolha']}" for a in ajustes.get("pontos") or [] if a.get("escolha")]
        if ajustes.get("pedido"):
            linhas.append("- " + ajustes["pedido"])
        partes.append("VERSÃO ANTERIOR DESTA SEÇÃO:\n" + (ajustes.get("anterior") or "")
                      + "\n\nAJUSTES PEDIDOS PELO ADVOGADO:\n" + "\n".join(linhas)
                      + "\n\nReescreva a seção com esses ajustes, mantendo o resto.")
    partes.append(f"Redija agora SOMENTE a seção: {titulo}" + (f" - {secao['objetivo']}" if secao.get("objetivo") else "")
                  + f"\nPrimeira linha: {titulo}")
    mensagens = [{"role": "system", "content": sistema}, {"role": "user", "content": "\n\n".join(partes)}]
    modelo = profundidade_mod.modelo_do_nivel(estado.prefs.dados, nivel, nuvem.config(estado).get("modelo") or "")
    mascara = nuvem.Mascara() if nuvem.config(estado).get("mascarar", True) else None
    ponte = Ponte(lambda empurrar: nuvem.chamada(
        estado, mensagens, pessoa=pessoa, trabalho=trabalho, etapa="clausula", pergunta=estado_e.get("pedido", ""),
        mascara=mascara, on_token=empurrar, max_tokens=min(3000, nivel.saida_tokens), parar=parar, modelo=modelo,
        profundidade=nivel.id), parar=parar)
    visto = ""
    mostrado = 0
    for pedaco in ponte:
        visto += pedaco
        corte = visto.find(SEPARADOR_PONTOS)
        # Segura o fim do texto até ter certeza de que não é o começo do separador.
        ate = corte if corte >= 0 else max(mostrado, len(visto) - len(SEPARADOR_PONTOS))
        if ate > mostrado:
            yield ("token", {"t": visto[mostrado:ate]})
            mostrado = ate
    texto_todo, _uso = ponte.resultado or (visto, {})
    corte = texto_todo.find(SEPARADOR_PONTOS)
    corpo, resto = (texto_todo[:corte], texto_todo[corte + len(SEPARADOR_PONTOS):]) if corte >= 0 else (texto_todo, "")
    if len(corpo) > mostrado and corte < 0:
        yield ("token", {"t": corpo[mostrado:]})
    pontos, aviso = _pontos(resto)
    return {"texto": elaboracao.limpar_texto(corpo), "pontos": pontos, "aviso": aviso}


def _briefing(estado_e: dict) -> str:
    import entrevista

    return entrevista.briefing(estado_e)


def compilar(estado_e: dict) -> str:
    """O documento inteiro: o título e as seções aprovadas, na ordem do plano."""
    plano = estado_e.get("plano") or {}
    corpo = [estado_e["clausulas"][s["id"]]["texto"].strip() for s in plano.get("secoes") or []
             if (estado_e.get("clausulas") or {}).get(s["id"], {}).get("texto")]
    titulo = plano.get("titulo_documento") or (estado_e.get("trabalho") or "").upper()
    return ((titulo + "\n\n") if titulo else "") + "\n\n".join(corpo)


def proxima(estado_e: dict) -> int | None:
    """O índice da primeira seção ainda não aprovada, ou None (todas aprovadas)."""
    for i, s in enumerate((estado_e.get("plano") or {}).get("secoes") or []):
        if (estado_e.get("clausulas") or {}).get(s["id"], {}).get("status") != "aprovada":
            return i
    return None
