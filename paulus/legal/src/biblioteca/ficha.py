"""
A ficha de cada material da Biblioteca (M2): o que ele é, de quem, de quando.

Sem ficha, o material era um balde: o PAULUS não sabia se um trecho era do
manual da casa ou de um livro, nem de que ano. Com ela, a resposta diz "Segundo
Fulano (2ª ed., 2015), p. 45", e o aviso de obra anterior à redação atual do
artigo (M6) tem com o que comparar.

**Campo não achado fica vazio, nunca chutado.** Tudo aqui é regra, sobre as
primeiras páginas do arquivo:

- a **ficha catalográfica (CIP)**, quando existe, é a fonte de verdade: o
  autor ("/ Heitor Valadares Brandão."), o título (antes da barra), a edição
  ("2. ed."), a cidade, a editora e o ano ("São Paulo : Editora, 2015");
- o **ISBN** só entra com o dígito verificador certo - ISBN com um número
  trocado (leitura de imagem, erro de digitação) é pior que nenhum;
- a **edição** fora da ficha só vale se houver uma só ("2ª edição" na folha
  de rosto); o histórico "1ª edição: 2010, 2ª edição: 2013" sem ficha fica
  vazio, porque qual é a deste arquivo é justamente o que não se sabe;
- o **ano** é o da ficha; sem ela, o do © quando só há um.

As **áreas sugeridas** vêm das leis mais citadas na obra (a mesma regra que
acha "art. 18 do CDC" em documento, src/inteligencia/extratores/regras_leis):
uma obra que cita o CDC 200 vezes é de consumidor.

A tela mostra a ficha para conferir ao entrar, e **o que a pessoa edita vale
sobre o que a regra achou** - reler o arquivo não desfaz a correção.

Dois campos pensam no compartilhamento futuro (docs/PROGRESSO-BIBLIOTECA.md):
`origem` (escritorio, oficial, comunidade) e `licenca` - vazia de fábrica,
preenchida só por quem é autor do material, nunca deduzida.
"""

from __future__ import annotations

import re
import unicodedata

TIPOS = ("doutrina", "manual", "tabela", "sumulas", "lei", "artigo", "modelo_de_peca", "outro")
ROTULO_DO_TIPO = {"doutrina": "Doutrina", "manual": "Manual interno", "tabela": "Tabela", "sumulas": "Súmulas",
                  "lei": "Lei", "artigo": "Artigo", "modelo_de_peca": "Modelo de peça", "outro": "Outro"}
AREAS = ("civil", "consumidor", "processo civil", "trabalho", "processo do trabalho", "penal", "processo penal",
         "tributário", "família e sucessões", "empresarial", "administrativo", "previdenciário", "constitucional",
         "imobiliário", "outra")
ORIGENS = ("escritorio", "oficial", "comunidade")
CAMPOS = ("tipo", "titulo", "autor", "edicao", "ano", "editora", "isbn", "areas", "origem", "licenca")

# De qual área é cada lei, pelo identificador de regras_leis.
AREA_DO_INSTRUMENTO = {
    "lei_8078_1990": "consumidor", "lei_10406_2002": "civil", "lei_13105_2015": "processo civil",
    "decreto_lei_5452_1943": "trabalho", "decreto_lei_2848_1940": "penal", "decreto_lei_3689_1941": "processo penal",
    "lei_5172_1966": "tributário", "constituicao_1988": "constitucional", "lei_8069_1990": "família e sucessões",
    "lei_8245_1991": "imobiliário", "lei_8213_1991": "previdenciário", "lei_8212_1991": "previdenciário",
    "lei_11101_2005": "empresarial", "lei_6404_1976": "empresarial", "lei_8112_1990": "administrativo",
    "lei_14133_2021": "administrativo", "lei_8666_1993": "administrativo", "lei_9784_1999": "administrativo",
}

ORDINAIS = {"primeira": 1, "segunda": 2, "terceira": 3, "quarta": 4, "quinta": 5, "sexta": 6, "setima": 7,
            "oitava": 8, "nona": 9, "decima": 10}

RE_ISBN = re.compile(r"ISBN(?:-1[03])?[:\s]*((?:97[89][\s-]?)?\d{1,5}[\s-]?\d{1,7}[\s-]?\d{1,7}[\s-]?[\dXx])\b")
RE_EDICAO_ROSTO = re.compile(r"\b(\d{1,2})\s*[ªa]\.?\s*edi[çc][ãa]o\b", re.I)
RE_EDICAO_EXTENSO = re.compile(r"\b(primeira|segunda|terceira|quarta|quinta|sexta|s[ée]tima|oitava|nona|d[ée]cima)"
                               r"\s+edi[çc][ãa]o\b", re.I)
RE_EDICAO_CIP = re.compile(r"(?:^|[\s–—-])(\d{1,2})\s*[.ªa]\s*ed\.", re.I)
RE_COPYRIGHT = re.compile(r"(?:©|\(c\)|copyright)\s*(?:©\s*)?(?:by\s+)?(\d{4})\b", re.I)
# O começo da ficha catalográfica. "Ficha catalográfica" só vale no começo da
# linha: no meio da frase é alguém falando dela (a folha de rosto da obra
# fictícia da demonstração diz que "a ficha catalográfica não existe").
RE_CIP = re.compile(r"dados\s+internacionais\s+de\s+cataloga[çc][ãa]o|^\s*ficha\s+catalogr[áa]fica|\(CIP\)",
                    re.I | re.M)
# A área de publicação da ficha: "São Paulo : Editora Exemplo Jurídico, 2015".
RE_IMPRENTA = re.compile(r"([A-ZÀ-Ý][A-Za-zÀ-ÿ .'-]{1,40}?)\s*:\s*([^,:\n]{2,70}?),\s*((?:19|20)\d{2})\b")
# A indicação de responsabilidade: "... do Consumidor / Heitor Valadares Brandão. – 2. ed."
RE_BARRA_AUTOR = re.compile(r"\s/\s*(?P<autor>[A-ZÀ-Ý][^.;/]{3,90}?)\s*[.;]")


def _plano(texto: str) -> str:
    normal = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


def vazia(tipo: str = "") -> dict:
    return {"tipo": tipo if tipo in TIPOS else "", "titulo": "", "autor": "", "edicao": "", "ano": "", "editora": "",
            "isbn": "", "areas": [], "origem": "escritorio", "licenca": "", "editado": [], "confirmada": False}


def isbn_valido(bruto: str) -> bool:
    digitos = re.sub(r"[^\dXx]", "", bruto or "").upper()
    if len(digitos) == 13 and digitos.isdigit():
        soma = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digitos[:12]))
        return (10 - soma % 10) % 10 == int(digitos[12])
    if len(digitos) == 10 and digitos[:9].isdigit():
        soma = sum(int(d) * (10 - i) for i, d in enumerate(digitos[:9]))
        final = 10 if digitos[9] == "X" else (int(digitos[9]) if digitos[9].isdigit() else -1)
        return (soma + final) % 11 == 0
    return False


def frente(texto: str, paginas: int = 4) -> str:
    """As primeiras páginas: folha de rosto, ficha catalográfica, verso. É onde a ficha está."""
    marcas = list(re.finditer(r"^\[pagina (\d+)\][ \t]*$", texto or "", re.M))
    if len(marcas) > paginas:
        return texto[:marcas[paginas].start()]
    return (texto or "")[:8000]


def _bloco_cip(inicio: str) -> str:
    """O texto da ficha catalográfica, numa linha só (a quebra do PDF parte o título no meio)."""
    m = RE_CIP.search(inicio)
    if not m:
        return ""
    pagina = inicio[m.start():]
    fim = re.search(r"^\[pagina \d+\]", pagina, re.M)
    return " ".join(pagina[:fim.start() if fim else 2500].split())


def ler_ficha(texto: str, tipo: str = "") -> dict:
    """A ficha pela regra: o que a regra não acha fica vazio."""
    ficha = vazia(tipo)
    inicio = frente(texto)
    cip = _bloco_cip(inicio)

    isbns = [x for x in RE_ISBN.findall(inicio) if isbn_valido(x)]
    distintos = list(dict.fromkeys(re.sub(r"[^\dXx]", "", x) for x in isbns))
    if len(distintos) == 1:
        ficha["isbn"] = " ".join(isbns[0].split())

    # Edição: a da ficha catalográfica manda; sem ela, só se houver uma.
    na_cip = {int(n) for n in RE_EDICAO_CIP.findall(cip)} if cip else set()
    no_resto = {int(n) for n in RE_EDICAO_ROSTO.findall(inicio)}
    no_resto |= {ORDINAIS[_plano(n)] for n in RE_EDICAO_EXTENSO.findall(inicio) if _plano(n) in ORDINAIS}
    if len(na_cip) == 1:
        ficha["edicao"] = f"{na_cip.pop()}ª"
    elif not na_cip and len(no_resto) == 1:
        ficha["edicao"] = f"{no_resto.pop()}ª"

    # Ano, editora, cidade: a área de publicação da ficha.
    imprenta = RE_IMPRENTA.search(cip) if cip else None
    anos_cip = {imprenta.group(3)} if imprenta else set()
    anos_c = set(RE_COPYRIGHT.findall(inicio))
    if len(anos_cip) == 1:
        ficha["ano"] = anos_cip.pop()
    elif not anos_cip and len(anos_c) == 1:
        ficha["ano"] = anos_c.pop()
    if imprenta:
        editora = " ".join(imprenta.group(2).split()).strip(" .")
        if editora and not re.search(r"\d", editora):
            ficha["editora"] = editora

    # Autor e título: a indicação de responsabilidade da ficha ("Título :
    # subtítulo / Nome do Autor."). O título é o que vem depois da entrada
    # principal, que é o mesmo autor invertido ("Brandão, Heitor Valadares").
    if cip:
        # A barra certa é a do autor que também abre a entrada ("Duarte,
        # Paulo Henrique ... / Paulo Henrique Duarte."): o registro da
        # bibliotecária ("CRB-9/1234") também tem barra.
        resp = None
        for m in RE_BARRA_AUTOR.finditer(cip):
            nomes = m.group("autor").split()
            if nomes and re.search(re.escape(nomes[-1]) + r",\s*", cip[:m.start()]):
                resp = m
                break
        if resp:
            autor = " ".join(resp.group("autor").split())
            ficha["autor"] = autor
            antes = cip[:resp.start()]
            nomes = autor.split()
            entrada = re.search(re.escape(nomes[-1]) + r",\s*", antes) if nomes else None
            titulo = ""
            if entrada:
                resto = antes[entrada.end():].split()
                i = 0
                while i < len(resto) and (resto[i].strip(".,") in nomes or resto[i] in ("de", "da", "do", "dos", "das")):
                    i += 1
                titulo = " ".join(resto[i:]).split(" : ")[0].strip(" .:")
            if 3 <= len(titulo) <= 160 and not re.search(r"CIP|C[âa]mara Brasileira|Cataloga", titulo):
                ficha["titulo"] = titulo
    ficha["areas"] = areas_sugeridas(texto)
    return ficha


def areas_sugeridas(texto: str, maximo: int = 3) -> list[str]:
    """
    As áreas das leis mais citadas: pelo menos 3 citações e 20% do total.
    Contadas sem o sumário e o cabeçalho repetido (src/trechos.py): o título
    "4.1 O art. 18 do CDC" no sumário não é mais uma citação.
    """
    import trechos
    from inteligencia.extratores import regras_leis

    contagem: dict[str, int] = {}
    for achado in regras_leis.achar(trechos.limpar_obra(texto or "")):
        area = AREA_DO_INSTRUMENTO.get(achado["dados"].get("instrument_id", ""))
        if area:
            contagem[area] = contagem.get(area, 0) + 1
    total = sum(contagem.values())
    boas = [(n, a) for a, n in contagem.items() if n >= 3 and n >= 0.2 * total]
    return [a for _, a in sorted(boas, key=lambda x: (-x[0], x[1]))[:maximo]]


def fundir(da_regra: dict, atual: dict | None) -> dict:
    """A ficha da regra, com o que a pessoa editou por cima (o editado não volta)."""
    atual = atual or {}
    saida = {**vazia(), **da_regra}
    for campo in atual.get("editado") or []:
        if campo in atual:
            saida[campo] = atual[campo]
    saida["editado"] = list(atual.get("editado") or [])
    saida["confirmada"] = bool(atual.get("confirmada"))
    return saida


def editar(atual: dict, mudancas: dict) -> dict:
    """O que a pessoa corrigiu na tela. Campo fora da lista, tipo ou área que não existe: fora."""
    ficha = {**vazia(), **(atual or {})}
    editado = set(ficha.get("editado") or [])
    for campo, valor in (mudancas or {}).items():
        if campo not in CAMPOS or campo == "origem":
            continue
        if campo == "tipo" and valor not in TIPOS:
            continue
        if campo == "areas":
            valor = [a for a in (valor or []) if a in AREAS]
        elif campo == "isbn" and valor and not isbn_valido(str(valor)):
            raise ValueError("esse ISBN não confere: o dígito verificador não bate")
        elif campo == "ano" and valor and not re.fullmatch(r"(1[5-9]|20)\d{2}", str(valor)):
            raise ValueError("o ano é com quatro algarismos, como 2015")
        else:
            valor = " ".join(str(valor or "").split())[:200]
        ficha[campo] = valor
        editado.add(campo)
    ficha["editado"] = sorted(editado)
    ficha["confirmada"] = True
    return ficha


def precisa_conferir(ficha: dict) -> bool:
    """Ficha que a pessoa ainda não viu, ou sem o essencial para citar."""
    return not ficha.get("confirmada") or (ficha.get("tipo") == "doutrina" and not ficha.get("autor"))


def citacao_curta(ficha: dict, nome: str = "") -> str:
    """'Brandão, Vícios do produto e do serviço, 2ª ed., 2015' - com o que houver."""
    autor = ficha.get("autor") or ""
    sobrenome = autor.split()[-1] if autor else ""
    partes = [p for p in (sobrenome, ficha.get("titulo") or re.sub(r"\.[A-Za-z0-9]{2,4}$", "", nome),
                          f"{ficha['edicao']} ed." if ficha.get("edicao") else "", ficha.get("ano") or "") if p]
    return ", ".join(partes)
