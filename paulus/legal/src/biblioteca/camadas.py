"""
A resposta em camadas (M4): lei, súmulas, doutrina, regra da casa e os
documentos, cada um com o seu rótulo e a sua fonte.

Antes, tudo o que a biblioteca trazia chegava ao modelo num bloco só,
"MATERIAL DE CONSULTA", com o mesmo peso: o texto do art. 18 do CDC e a
opinião de um autor sobre ele. Um modelo de 3B não distingue um do outro, e a
resposta dizia "o CDC determina" onde era o autor quem sustentava.

Aqui o contexto é montado **em blocos rotulados, nesta ordem**, cada um só se
tiver conteúdo:

1. LEI - o texto do artigo guardado em src/leis.py, quando a pergunta ou os
   trechos da biblioteca citam um dispositivo instalado; o revogado vem
   marcado como revogado;
2. SÚMULAS;
3. DOUTRINA - com autor, obra, edição, ano e página em cada trecho;
4. COMUNIDADE - material importado de pacote, de outro advogado (ver
   docs/PROGRESSO-BIBLIOTECA.md, "Compartilhamento futuro"), nunca como lei
   nem como regra da casa;
5. REGRA DA CASA - o manual interno e a tabela do escritório;
6. DOCUMENTOS - o Acervo, como sempre.

Os lembretes (src/contextos.py) continuam indo na instrução, como sempre:
movê-los para cá mudaria toda resposta, com ou sem biblioteca.

**O que vai em código, e não em instrução ao modelo.** Medido quando o
contrato [Tn] foi feito (src/citacoes.py): instrução nova ao 3B derrubou o
banco de provas duas vezes. Então o modelo lê os blocos rotulados e responde
como sempre; depois, em código:

- cada frase ganha a marca [Tn] do trecho que a sustenta, e a marca sabe a
  origem (lei, súmula, doutrina, comunidade, casa, documento);
- **frase sustentada só por doutrina que atribui o conteúdo à lei** ("o art.
  18 determina", "o CDC estabelece", "a lei prevê") ganha "Segundo <Autor>,"
  na frente. Opinião de autor nunca sai como texto de lei.

Duas obras sobre o mesmo artigo entram cada uma com o seu cabeçalho, e cada
frase leva o autor do trecho que a sustenta: as duas atribuições ficam
separadas. Detectar "divergência" fica para depois; aqui só não se funde.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# A ordem e o rótulo de cada camada. "material" é o material sem ficha (de
# antes da triagem): vai com o rótulo de sempre, sem dizer o que não se sabe.
ORDEM = ("lei", "sumula", "doutrina", "comunidade", "casa", "material")
ROTULO = {"lei": "LEI", "sumula": "SÚMULAS", "doutrina": "DOUTRINA", "comunidade": "COMUNIDADE",
          "casa": "REGRA DA CASA", "material": "MATERIAL DE CONSULTA", "documento": "DOCUMENTOS"}
EXPLICA = {
    "lei": "o texto oficial do artigo, guardado nesta máquina",
    "sumula": "enunciados de súmula",
    "doutrina": "o que autores sustentam; não é texto de lei",
    "comunidade": "material compartilhado por outros advogados, não revisado por este escritório",
    "casa": "as regras internas deste escritório",
    "material": "referência que o escritório entregou; não é documento de cliente",
    "documento": "os documentos do Acervo",
}
# O rótulo curto da marca [Tn] na tela.
CURTO = {"lei": "lei", "sumula": "súm.", "doutrina": "dout.", "comunidade": "com.", "casa": "casa",
         "material": "mat.", "documento": "doc."}

# Quanto cada camada pode ocupar (caracteres). A que não usa o seu teto cede
# o espaço para as seguintes; o total não passa de TOTAL - o mesmo teto que o
# material tinha antes das camadas (min(2400, orçamento/3) em perguntar.py).
# Medido na primeira rodada da M4 com o dobro disto: a resposta levava de 50 a
# 110 s em vez de 15 a 45, e o 3B se perdia mais ("não está nos documentos").
TETOS = {"lei": 900, "sumula": 400, "doutrina": 1000, "comunidade": 400, "casa": 800, "material": 900}
TOTAL = 2400
MAX_ARTIGOS = 2
# Do artigo longo, o começo do caput vai sempre; o resto, a partir do parágrafo
# ou inciso que a pergunta cita ("art. 26, § 3º": o § 3º fica no fim).
CAPUT_MINIMO = 260

RE_PAGINA = re.compile(r"\[pagina (\d+)\]")

# A frase que diz que a LEI diz: "o art. 18 determina", "o CDC estabelece",
# "a lei prevê", "segundo o art. 49".
VERBOS = r"(?:determina|prev[êe]|estabelece|disp[õo]e|diz|garante|assegura|imp[õo]e|obriga|define|exige|permite|proíbe|veda)"
RE_ATRIBUI_A_LEI = re.compile(
    r"\b(?:o|do|no|pelo)\s+art(?:igo)?\.?\s*\d[^.;]{0,60}?\b" + VERBOS + r"\b"
    r"|\b(?:a|pela)\s+lei\s+" + VERBOS + r"\b"
    r"|\b(?:o|a)\s+(?:CDC|CC|CPC|CLT|CTN|Constitui[çc][ãa]o|C[óo]digo[^.,;]{0,40}?)\s+" + VERBOS + r"\b"
    r"|\b(?:segundo|conforme|nos termos d)[oa]?\s+(?:o\s+)?art(?:igo)?\.?\s*\d",
    re.IGNORECASE)


@dataclass
class Trecho:
    origem: str
    cabeca: str
    texto: str
    fonte: dict
    autor: str = ""
    obra: str = ""
    ano: str = ""
    dispositivos: list = field(default_factory=list)   # (codigo, numero) que o trecho comenta


@dataclass
class Camadas:
    trechos: list[Trecho]
    texto: str

    @property
    def vazia(self) -> bool:
        return not self.trechos

    def textos(self) -> list[str]:
        return [t.texto for t in self.trechos]


def origem_do_item(item: dict) -> str:
    ficha = item.get("ficha") or {}
    if ficha.get("origem") == "comunidade":
        return "comunidade"
    tipo = ficha.get("tipo") or ""
    if not tipo:
        return "material"
    return {"manual": "casa", "tabela": "casa", "modelo_de_peca": "casa", "sumulas": "sumula",
            "lei": "lei"}.get(tipo, "doutrina")


def _sobrenome(autor: str) -> str:
    partes = (autor or "").split()
    return partes[-1] if partes else ""


def cabeca_da_obra(ficha: dict, nome: str, lugar: str) -> str:
    """"Brandão, Vícios do produto e do serviço, 2ª ed., 2015, p. 7" - com o que a ficha tiver."""
    titulo = ficha.get("titulo") or re.sub(r"\.[A-Za-z0-9]{2,4}$", "", nome)
    partes = [_sobrenome(ficha.get("autor", "")), titulo, f"{ficha['edicao']} ed." if ficha.get("edicao") else "",
              ficha.get("ano") or "", lugar.replace("página ", "p. ").replace("páginas ", "pp. ")]
    return ", ".join(p for p in partes if p)


def dispositivos_citados(texto: str) -> list[tuple[str, str]]:
    """(codigo, numero) dos artigos citados COM instrumento, de uma lei que src/leis.py conhece."""
    import leis as leis_mod
    from biblioteca.anotacoes import numero_legivel
    from inteligencia.extratores import regras_leis

    plano = re.sub(r"(?<!\n)\n(?!\n)", " ", texto or "")
    saida = []
    for achado in regras_leis.achar(plano):
        d = achado["dados"]
        codigo = leis_mod.CODIGO_DO_INSTRUMENTO.get(d.get("instrument_id", ""))
        if d.get("kind") == "article" and codigo:
            par = (codigo, numero_legivel(d.get("article", "")))
            if par not in saida:
                saida.append(par)
    return saida


def partes_citadas(texto: str) -> dict[tuple[str, str], tuple[str, str]]:
    """(codigo, numero) -> (parágrafo, inciso) que o texto cita: "art. 26, § 3º, do CDC" -> ("3", "")."""
    import leis as leis_mod
    from biblioteca.anotacoes import numero_legivel
    from inteligencia.extratores import regras_leis

    saida = {}
    for achado in regras_leis.achar(re.sub(r"(?<!\n)\n(?!\n)", " ", texto or "")):
        d = achado["dados"]
        codigo = leis_mod.CODIGO_DO_INSTRUMENTO.get(d.get("instrument_id", ""))
        if codigo and (d.get("paragraph") or d.get("item")):
            saida[(codigo, numero_legivel(d.get("article", "")))] = (d.get("paragraph", ""), d.get("item", ""))
    return saida


def recorte_do_artigo(texto: str, parte, limite: int) -> str:
    """
    O artigo inteiro, se couber; senão o começo do caput e, depois de "[…]", o
    parágrafo ou o inciso citado - nunca um artigo cortado antes da parte que a
    pergunta pediu.
    """
    if len(texto) <= limite or not parte:
        return texto
    paragrafo, inciso = parte
    padrao = None
    if paragrafo == "único":
        padrao = r"Par[áa]grafo [úu]nico"
    elif paragrafo:
        padrao = r"§\s*" + re.escape(paragrafo) + r"\s*[º°o]?(?!\d)"
    elif inciso:
        padrao = r"(?<![A-Za-z])" + re.escape(inciso) + r"\s*[-–—]\s"
    m = re.search(padrao, texto) if padrao else None
    if not m or m.start() < limite:
        return texto
    caput = texto[:CAPUT_MINIMO].rsplit(" ", 1)[0]
    return caput + " […] " + texto[m.start():m.start() + max(200, limite - len(caput) - 5)]


def montar(material, leis, pergunta: str, hits: list, total: int = TOTAL) -> Camadas:
    """
    As camadas da pergunta: os trechos do material (já escolhidos pela busca)
    repartidos pela origem, e os artigos de lei que a pergunta ou esses
    trechos citam. `leis` pode ser None (sem as leis em casa, sem camada LEI).
    """
    por_origem: dict[str, list[Trecho]] = {o: [] for o in ORDEM}
    for h in hits:
        item = material.item_por_nome(h.doc_name) or {"nome": h.doc_name}
        ficha = item.get("ficha") or {}
        origem = origem_do_item(item)
        lugar = material.onde(h) if hasattr(material, "onde") else ""
        texto = RE_PAGINA.sub("", h.chunk.text).strip()
        if origem == "lei":
            cabeca = (ficha.get("titulo") or item["nome"]) + " (lei guardada sem conferência de vigência)"
        elif origem == "comunidade":
            cabeca = cabeca_da_obra(ficha, item["nome"], lugar) + (
                f" — compartilhado por {ficha['autor']}" if ficha.get("autor") else "")
        else:
            cabeca = cabeca_da_obra(ficha, item["nome"], lugar)
        fonte = {"documento": item["nome"], "trecho": h.chunk.index + 1, "score": round(h.score, 2), "texto": texto,
                 "material": True, "origem": origem, "pagina": getattr(h.chunk, "pagina_inicio", None),
                 "onde": lugar, "material_id": item.get("id", ""), "autor": ficha.get("autor", ""),
                 "ano": ficha.get("ano", "")}
        por_origem[origem].append(Trecho(origem, cabeca, texto, fonte, autor=ficha.get("autor", ""),
                                         obra=ficha.get("titulo") or item["nome"], ano=ficha.get("ano", ""),
                                         dispositivos=dispositivos_citados(texto)))

    # LEI: primeiro o que a pergunta cita; depois o que os trechos citam.
    if leis is not None:
        pedidos = dispositivos_citados(pergunta)
        partes = partes_citadas(pergunta)
        for trechos in (por_origem["doutrina"], por_origem["comunidade"], por_origem["casa"], por_origem["sumula"]):
            for t in trechos:
                pedidos += [p for p in t.dispositivos if p not in pedidos]
        for codigo, numero in pedidos:
            if len([t for t in por_origem["lei"] if t.fonte.get("lei")]) >= MAX_ARTIGOS:
                break
            artigo = leis.artigo(codigo, numero)
            if not artigo:
                continue
            cabeca = artigo["citacao"] + (" — REVOGADO: não está em vigor" if artigo["revogado"] else "")
            texto = ("(Revogado) " if artigo["revogado"] and not artigo["texto"].lower().startswith("(revogad") else "") \
                + recorte_do_artigo(artigo["texto"], partes.get((codigo, numero)), TETOS["lei"] - len(cabeca) - 8)
            fonte = {"documento": artigo["citacao"], "trecho": 1, "score": 1.0, "texto": texto, "material": True,
                     "lei": True, "origem": "lei", "codigo": codigo, "numero": artigo["numero"],
                     "revogado": artigo["revogado"], "onde": artigo.get("contexto") or "texto do Planalto"}
            por_origem["lei"].insert(len([t for t in por_origem["lei"] if t.fonte.get("lei")]),
                                     Trecho("lei", cabeca, texto, fonte, dispositivos=[(codigo, artigo["numero"])]))

    # O orçamento: cada camada até o seu teto, e o que sobra passa adiante.
    escolhidos: list[Trecho] = []
    blocos: list[str] = []
    usado, sobra = 0, 0
    for origem in ORDEM:
        deste = por_origem[origem]
        if not deste:
            sobra += TETOS[origem]
            continue
        verba = min(TETOS[origem] + sobra, total - usado)
        partes, gasto = [], 0
        for t in deste:
            # O que veio de outro advogado vai cercado, como todo texto de
            # terceiro (src/blindagem.py): e dado, nunca instrucao.
            pedaco = f"[{t.cabeca}]\n{_cercado(t)}"
            if gasto + len(pedaco) > verba:
                resto = verba - gasto - len(t.cabeca) - 4
                if resto < 200:
                    break
                t.texto = t.texto[:resto] + "…"
                pedaco = f"[{t.cabeca}]\n{_cercado(t)}"
            partes.append(pedaco)
            escolhidos.append(t)
            gasto += len(pedaco) + 2
        if partes:
            blocos.append(f"{ROTULO[origem]} — {EXPLICA[origem]}\n\n" + "\n\n".join(partes))
        usado += gasto
        sobra = max(0, verba - gasto)
    return Camadas(escolhidos, "\n\n".join(blocos))


def _cercado(t: Trecho) -> str:
    if t.origem != "comunidade":
        return t.texto
    import blindagem

    return blindagem.cercar(t.texto)


def trecho_de_documento(hit) -> Trecho:
    fonte = {"documento": hit.doc_name, "trecho": hit.chunk.index + 1, "texto": hit.chunk.text, "origem": "documento"}
    return Trecho("documento", hit.doc_name, hit.chunk.text, fonte)


# ------------------------------------------------------------ depois da resposta

def conferir_doutrina(resposta: str, trechos: list[Trecho]) -> tuple[str, int]:
    """
    A frase que diz "a lei diz" sustentada só por doutrina ganha o autor na
    frente. Devolve (texto, quantas frases foram corrigidas).

    Quem sustenta cada frase: a marca [Tn] que ela tem (posta em código por
    citacoes.atribuir). Se algum trecho de lei sustenta a mesma frase (as
    palavras e os números dela estão no artigo), a frase fica como está.
    """
    from citacoes import RE_MARCA, _frases
    from inteligencia import molde
    from lexico import normalizar

    base = [(set(normalizar(t.texto).split()), molde.numeros_de(t.texto)) for t in trechos]
    saida, corrigidas = [], 0
    for frase in _frases(resposta):
        if not RE_ATRIBUI_A_LEI.search(frase):
            saida.append(frase)
            continue
        corpo = RE_MARCA.sub("", frase)
        palavras = {p for p in normalizar(corpo).split() if not p.isdigit() and len(p) > 2}
        numeros = molde.numeros_de(corpo)
        marcas = [int(m) for m in RE_MARCA.findall(frase)]
        if not marcas:
            # Sem marca (a atribuição por palavras não chegou a 3 em comum):
            # quem sustenta é o trecho mais parecido, se houver algum.
            pontos = [len(palavras & termos) + (2 * len(numeros) if numeros and numeros <= nums else 0)
                      for termos, nums in base]
            melhor = max(range(len(trechos)), key=lambda i: pontos[i], default=None)
            marcas = [melhor + 1] if melhor is not None and pontos[melhor] >= 2 else []
        origens = {trechos[m - 1].origem for m in marcas if 1 <= m <= len(trechos)}
        if not origens & {"doutrina", "comunidade"}:
            saida.append(frase)
            continue
        da_lei = any(t.origem == "lei" and (not numeros or numeros <= base[i][1]) and len(palavras & base[i][0]) >= 3
                     for i, t in enumerate(trechos))
        if da_lei or origens & {"lei"}:
            saida.append(frase)
            continue
        autor_trecho = next(trechos[m - 1] for m in marcas if 1 <= m <= len(trechos)
                            and trechos[m - 1].origem in ("doutrina", "comunidade"))
        saida.append(_atribuir_ao_autor(frase, autor_trecho))
        corrigidas += 1
    return "".join(saida), corrigidas


def _atribuir_ao_autor(frase: str, trecho: Trecho) -> str:
    """'O art. 18 determina...' -> 'Segundo Brandão, o art. 18 determina...'; sem autor, '(posição doutrinária)'."""
    inicio = len(frase) - len(frase.lstrip())
    corpo = frase[inicio:]
    if re.match(r"(?i)segundo\s", corpo):
        return frase
    if trecho.autor:
        # "O art. 18" -> "o art. 18"; sigla fica ("CDC", "STJ").
        palavra = (re.match(r"\S+", corpo) or [""])[0]
        primeiro = corpo[:1] if len(palavra) >= 2 and palavra.isupper() else corpo[:1].lower()
        return frase[:inicio] + f"Segundo {_sobrenome(trecho.autor)}, " + primeiro + corpo[1:]
    fim = len(frase.rstrip())
    marca = re.search(r"\s*\[T\d{1,3}\][.!?]?$", frase[:fim])
    corte = marca.start() if marca else (fim - 1 if frase[fim - 1:fim] in ".!?" else fim)
    return frase[:corte] + " (posição doutrinária)" + frase[corte:]
