"""
"Qual o CPF do cliente Matheus?" - a consulta de cadastro, por molde.

Medido em 30/09/2026 (docs/PROGRESSO-CONVERSA.md, 1.5): a pergunta ia para a
busca nos documentos e lia 21 deles (~40 mil caracteres, ~165 s) para achar um
número que está na ficha de Cadastros. Nada consultava os campos das fichas:
`intencao.py` só trata "cadastrar", e a consulta de cadastros do
`programa.py` só conta registros.

Aqui a pergunta de UM dado de UMA pessoa - CPF, CNPJ, telefone, e-mail,
endereço, OAB - é respondida sem modelo, nesta ordem:

1. **Cadastros** (tabela `cadastros`, src/base.py): "O CPF de Matheus Silva é
   111.222.333-44 (Cadastros)." Nome que casa com mais de uma ficha vira lista
   para escolher, em vez de o programa escolher uma.
2. **Meus dados**, quando o nome é o do titular ou o do escritório: é o único
   lugar com OAB (a tabela não tem a coluna).
3. **Os fatos já conferidos dos documentos** (o metadata: espelho
   `meta_fatos`, pessoas com CPF/OAB de `regras_pessoas`, empresas com CNPJ de
   `regras_organizacoes`): só o que `Item.pode_virar_fato` - escrito, com o
   trecho conferido e o dígito verificador que fecha. Responde com o
   documento e a página.
4. Nada disso: "não encontrei", com a oferta de procurar lendo os documentos.
   **Nunca** lê o acervo sem a pessoa pedir.

Uma exceção, de propósito: CPF, CNPJ ou OAB de um nome que não está em
Cadastros, em Meus dados nem nos fatos, e sem nada na frase que diga
"cadastro" ("do cliente", "da colaboradora"), segue para os documentos como
antes. É o caso de "qual o CNPJ da Transportes Rio Fresco?" do banco de
provas (tools/demo/roteiro.py): a parte do contrato, que não é cliente, e
cujo número está no contrato. Telefone, e-mail e endereço não caem nessa
exceção: os documentos não guardam esses dados como fato, e ler o acervo
inteiro atrás deles era o que custava os 165 s.

O que a frase precisa ter para ser consulta (e não um pedido sobre o
documento): o campo seguido de "de/do/da" + nome, e antes do campo só
palavras de pergunta ("qual o", "me passa o"). "Responda o e-mail da
Clínica" não é consulta; "qual o CPF do locador?" é papel no documento, e
também não.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import campos_br
from cadastros import _chave

# O campo pedido: (artigo, como se escreve na resposta).
CAMPOS = {
    "cpf": ("o", "CPF"),
    "cnpj": ("o", "CNPJ"),
    "telefone": ("o", "telefone"),
    "email": ("o", "e-mail"),
    "endereco": ("o", "endereço"),
    "oab": ("a", "OAB"),
}

# Os que o metadata guarda como fato (com o tipo do documento no item).
NOS_FATOS = {"cpf": ("people", "CPF"), "cnpj": ("organizations", "CNPJ"), "oab": ("people", "OAB")}

_CAMPO = (r"(?P<campo>endereco de e-?mail|e-?mail|cpf|cnpj|numero de telefone|numero do telefone|telefone|"
          r"celular|whatsapp|numero da oab|numero de oab|inscricao na oab|registro na oab|oab|endereco)")
RE_CAMPO = re.compile(r"(?<![a-z0-9])" + _CAMPO + r"(?:\s+de\s+contato)?\s+(?:d[aeo]s?)\s+(?P<resto>.+)$")
RE_MEU = re.compile(r"(?<![a-z0-9])(?:meu|minha)\s+" + _CAMPO + r"(?![a-z0-9])")

# Antes do campo, só palavras de pergunta. Com qualquer outra ("responda o
# e-mail", "traduza o e-mail", "qual o valor do contrato e o CPF"), a frase
# pede outra coisa.
ANTES_DO_CAMPO = {
    "qual", "quais", "e", "o", "a", "os", "as", "me", "passa", "passe", "passar", "diga", "diz", "dizer",
    "da", "de", "do", "manda", "mande", "mandar", "informa", "informe", "informar", "fala", "falar",
    "preciso", "saber", "sabe", "voce", "tem", "consegue", "pode", "poderia", "numero", "oi", "ola", "ok",
    "entao", "por", "favor", "seria", "ai", "ver", "queria", "quero", "gostaria", "lembra", "confirma",
    "confirmar",
}

# O que vem antes do nome e não é nome. Os de cadastro dizem que a pessoa
# quer a ficha: sem ficha, a resposta é "não encontrei" (e a oferta), nunca
# a leitura do acervo.
TRATAMENTOS = ("o", "a", "os", "as", "dr", "dra", "doutor", "doutora", "sr", "sra", "senhor", "senhora",
               "empresa", "nosso", "nossa", "meu", "minha")
DE_CADASTRO = ("cliente", "clientes", "colaborador", "colaboradora", "socio", "socia", "estagiario",
               "estagiaria", "funcionario", "funcionaria", "advogado", "advogada")

# Papel no documento: "o CPF do locador" está no contrato, não numa ficha.
PAPEIS = {
    "locador", "locadora", "locatario", "locataria", "fiador", "fiadora", "inquilino", "inquilina",
    "proprietario", "proprietaria", "comprador", "compradora", "vendedor", "vendedora", "devedor",
    "devedora", "credor", "credora", "requerente", "requerido", "requerida", "parte", "partes",
    "contratante", "contratada", "contratado", "autor", "autora", "reu", "re", "outorgante", "outorgado",
    "outorgada", "testemunha", "testemunhas", "imovel", "cartorio", "tribunal", "juiz", "juiza", "vara",
    "banco", "reclamante", "reclamada", "reclamado", "exequente", "executado", "executada", "herdeiro",
    "herdeira", "espolio", "cujus", "empregador", "empregado", "empregada", "sede", "filial",
    "empresa", "pessoa", "mesmo", "mesma", "dele", "dela", "deles", "delas", "signatario", "signataria",
}

# Onde o nome acaba: "do Matheus no cadastro, por favor?".
RE_FIM_DO_NOME = re.compile(
    r"\s*(?:[?!,;]|\s(?:por favor|por gentileza|no cadastro|nos cadastros|na ficha|cadastrad[oa]s?|"
    r"que esta|que consta|que tem|pra mim|para mim|ai|aqui|ali)\b).*$")

# Tokens que não distinguem nome: "Clínica Bem Viver" casa com "Clínica Bem
# Viver Ltda.".
SEM_PESO = {"de", "da", "do", "das", "dos", "e", "ltda", "me", "sa", "s", "eireli", "epp", "cia"}


def _plano(texto: str) -> str:
    normal = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


def _tokens(nome: str) -> list[str]:
    return [t for t in _chave(nome).split() if t not in SEM_PESO]


def _contido(pequeno: list[str], grande: list[str]) -> bool:
    return bool(pequeno) and all(t in grande for t in pequeno)


def ligado(preferencias: dict | None) -> bool:
    """A chave `conversa.roteamento`. Desligada, a conversa segue como antes."""
    return bool(((preferencias or {}).get("conversa") or {}).get("roteamento"))


@dataclass
class Pedido:
    campo: str                 # cpf | cnpj | telefone | email | endereco | oab
    nome: str = ""             # como a pessoa escreveu (com a caixa original, se deu)
    de_cadastro: bool = False  # "do cliente X", "da colaboradora Y"
    nome_proprio: bool = False # alguma palavra do nome com maiúscula
    meu: bool = False          # "qual o meu CPF?": Meus dados
    escritorio: bool = False   # "o CNPJ do escritório": Meus dados


def _campo_de(bruto: str) -> str:
    if "mail" in bruto:
        return "email"
    if "oab" in bruto:
        return "oab"
    if bruto in ("cpf", "cnpj"):
        return bruto
    if bruto == "endereco":
        return "endereco"
    return "telefone"


def _so_pergunta(antes: str) -> bool:
    return all(p in ANTES_DO_CAMPO for p in re.findall(r"[a-z0-9]+", antes))


def pedido(frase: str) -> Pedido | None:
    """Campo e nome, se a frase é a pergunta de um dado de alguém. Senão, None."""
    original = unicodedata.normalize("NFC", (frase or "").strip())
    plano = _plano(original)
    if not plano:
        return None
    import programa

    if programa.ancora_de_documento(plano):
        return None

    meu = RE_MEU.search(plano)
    if meu and _so_pergunta(plano[:meu.start()]):
        return Pedido(campo=_campo_de(meu.group("campo")), meu=True)

    m = RE_CAMPO.search(plano)
    if not m or not _so_pergunta(plano[:m.start()]):
        return None
    campo = _campo_de(m.group("campo"))
    inicio = m.start("resto")
    resto = RE_FIM_DO_NOME.sub("", plano[inicio:]).rstrip(" .")

    de_cadastro = False
    while True:
        palavra = re.match(r"([a-z]+)\.?\s+", resto)
        if not palavra:
            break
        if palavra.group(1) in DE_CADASTRO:
            de_cadastro = True
        elif palavra.group(1) not in TRATAMENTOS:
            break
        inicio += palavra.end()
        resto = resto[palavra.end():]
    nome = resto.strip(" .")
    if not nome or nome in DE_CADASTRO:
        return None
    # "a OAB do advogado da Rio Fresco": o dado é de outra pessoa, que a frase
    # não nomeia - não é o da Rio Fresco.
    if re.match(r"d[aeo]s?\s", nome):
        return None
    if nome in ("escritorio", "nosso escritorio", "meu escritorio"):
        return Pedido(campo=campo, escritorio=True)
    palavras = nome.split()
    if len(palavras) > 7 or palavras[0] in PAPEIS or nome in PAPEIS:
        return None

    # O nome com a caixa de quem escreveu: sem acento, as posições são as
    # mesmas (texto em NFC, uma letra por letra).
    exibido = nome
    if len(plano) == len(original):
        pos = plano.find(nome, inicio)
        if pos >= 0:
            exibido = original[pos:pos + len(nome)]
    proprio = any(p[:1].isupper() for p in exibido.split())
    return Pedido(campo=campo, nome=exibido, de_cadastro=de_cadastro, nome_proprio=proprio)


# ----------------------------------------------------------- a resposta


@dataclass
class Resposta:
    modo: str                  # achado | escolher | nada
    campo: str
    texto: str
    nome: str = ""
    fonte: str = ""            # cadastros | meus_dados | documentos
    ficha_id: int | None = None
    ficha_tipo: str = ""       # cliente | colaborador | socio: a visão de Cadastros
    opcoes: list[dict] = field(default_factory=list)   # [{nome, pergunta}]
    documento: str = ""
    pagina: int | None = None
    oferta: bool = False       # "procurar lendo os documentos"
    porque: str = ""


def _rotulo(campo: str) -> tuple[str, str]:
    return CAMPOS[campo]


def _frase(campo: str, nome: str, valor: str, onde: str) -> str:
    art, rotulo = _rotulo(campo)
    return f"{art.upper()} {rotulo} de {nome} é {valor} ({onde})."


def _pergunta_de(campo: str, nome: str) -> str:
    art, rotulo = _rotulo(campo)
    return f"qual {art} {rotulo} de {nome}?"


def _tipo_do_documento(documento: str) -> str:
    bruto = campos_br.normalizado(documento)
    return "cnpj" if len(bruto) == 14 else "cpf" if len(bruto) == 11 else ""


def _da_ficha(ficha: dict, campo: str) -> tuple[str, str]:
    """(valor, aviso): o dado da ficha, e o aviso quando o que há é outro."""
    if campo in ("cpf", "cnpj"):
        doc = (ficha.get("documento") or "").strip()
        tipo = _tipo_do_documento(doc)
        if not doc:
            return "", ""
        if tipo and tipo != campo:
            return doc, tipo
        return doc, ""
    if campo == "oab":
        return "", ""
    return (ficha.get(campo) or "").strip(), ""


def _fichas_do_nome(nome: str, cadastros: list[dict]) -> list[dict]:
    """
    As fichas que o nome escreve. Todas as palavras do que a pessoa escreveu
    estão no nome da ficha ("Matheus" casa com "Matheus Silva" e com "Matheus
    Andrade"); ficha cujo nome inteiro é igual vence as outras. Sem nenhuma,
    a ficha cujo nome inteiro está na frase ("Clínica Bem Viver Ltda. de
    Goiânia"), só com duas palavras ou mais.
    """
    alvo = _tokens(nome)
    pessoas = [f for f in cadastros if f.get("tipo") != "despesa"]
    casam = [f for f in pessoas if _contido(alvo, _tokens(f.get("nome", "")))]
    iguais = [f for f in casam if sorted(_tokens(f.get("nome", ""))) == sorted(alvo)]
    if len(iguais) == 1:
        return iguais
    if not casam:
        casam = [f for f in pessoas if len(_tokens(f.get("nome", ""))) >= 2
                 and _contido(_tokens(f.get("nome", "")), alvo)]
    return casam


def _dos_meus_dados(p: Pedido, preferencias: dict) -> tuple[str, str] | None:
    """(nome, valor) de Meus dados, quando a pergunta é do titular ou do escritório."""
    pessoa = (preferencias or {}).get("pessoa") or {}
    escritorio = (preferencias or {}).get("escritorio") or {}
    campos_pessoa = {"cpf": "cpf", "oab": "oab", "telefone": "telefone", "email": "email", "endereco": "endereco"}
    campos_escr = {"cnpj": "cnpj", "oab": "oab"}
    if p.meu or (p.nome and pessoa.get("nome") and _contido(_tokens(p.nome), _tokens(pessoa["nome"]))):
        chave = campos_pessoa.get(p.campo)
        return (pessoa.get("nome") or "você", str(pessoa.get(chave) or "").strip()) if chave else None
    if p.escritorio or (p.nome and escritorio.get("nome") and _contido(_tokens(p.nome), _tokens(escritorio["nome"]))):
        chave = campos_escr.get(p.campo)
        return (escritorio.get("nome") or "o escritório", str(escritorio.get(chave) or "").strip()) if chave else None
    return None


def _pelos_fatos(p: Pedido, nome: str, fatos) -> Resposta | None:
    """A resposta tirada dos fatos conferidos dos documentos, ou None."""
    if p.campo not in NOS_FATOS or fatos is None:
        return None
    achados = fatos(nome, p.campo) or []
    if not achados:
        return None
    art, rotulo = _rotulo(p.campo)
    pessoas: dict[str, list[dict]] = {}
    for a in achados:
        pessoas.setdefault(" ".join(_tokens(a["nome"])), []).append(a)
    if len(pessoas) > 1:
        opcoes = [{"nome": grupo[0]["nome"], "pergunta": _pergunta_de(p.campo, grupo[0]["nome"])}
                  for grupo in list(pessoas.values())[:5]]
        return Resposta("escolher", p.campo, f"Nos documentos, “{nome}” aparece como "
                        f"{len(pessoas)} pessoas diferentes. De quem é {art} {rotulo}?",
                        nome=nome, fonte="documentos", opcoes=opcoes,
                        porque="o nome casa com mais de uma pessoa nos fatos já lidos dos documentos")
    grupo = next(iter(pessoas.values()))
    quem = grupo[0]["nome"]
    valores: dict[str, list[dict]] = {}
    for a in grupo:
        valores.setdefault(campos_br.normalizado(a["valor"]) or a["valor"], []).append(a)

    def onde(a: dict) -> str:
        return f"“{a['documento']}”" + (f", página {a['pagina']}" if a.get("pagina") else "")

    if len(valores) == 1:
        lista = next(iter(valores.values()))
        primeiro = lista[0]
        mais = f", e em mais {len(lista) - 1} documento{'s' if len(lista) > 2 else ''}" if len(lista) > 1 else ""
        texto = (f"{art.upper()} {rotulo} de {quem} é {primeiro['valor']} — está em {onde(primeiro)}{mais} "
                 f"(dado já lido do documento, com o trecho conferido).")
        return Resposta("achado", p.campo, texto, nome=quem, fonte="documentos",
                        documento=primeiro["documento"], pagina=primeiro.get("pagina"),
                        porque="fato já lido e conferido no documento")
    partes = [f"{lista[0]['valor']} ({onde(lista[0])})" for lista in valores.values()]
    texto = (f"Encontrei {len(valores)} números diferentes para {art} {rotulo} de {quem} nos documentos: "
             + "; ".join(partes) + ". Confira no documento qual vale.")
    primeiro = next(iter(valores.values()))[0]
    return Resposta("achado", p.campo, texto, nome=quem, fonte="documentos", documento=primeiro["documento"],
                    pagina=primeiro.get("pagina"), porque="fatos já lidos e conferidos nos documentos")


def ler(frase: str, *, cadastros: list[dict], preferencias: dict | None = None, fatos=None) -> Resposta | None:
    """
    A resposta da consulta, ou None: a frase não é consulta de cadastro (ou
    é o caso que segue para os documentos, descrito no alto do módulo).

    `cadastros`: as fichas (dicts com id, tipo, nome, documento, telefone,
    email, endereco). `fatos(nome, campo)`: os fatos conferidos dos
    documentos, em dicts {nome, valor, documento, pagina} - quem chama liga
    ao metadata (`fatos_dos_documentos`); sem ele, não há fatos.
    """
    p = pedido(frase)
    if p is None:
        return None
    art, rotulo = _rotulo(p.campo)

    if p.meu or p.escritorio:
        nome, valor = _dos_meus_dados(p, preferencias or {}) or ("", "")
        if valor:
            return Resposta("achado", p.campo, _frase(p.campo, nome, valor, "Meus dados"), nome=nome,
                            fonte="meus_dados", porque="Configurações › Meus dados")
        quem = "seu" if p.meu else "do escritório"
        return Resposta("nada", p.campo, f"Não há {rotulo} {quem} em Configurações › Meus dados.",
                        nome=nome, fonte="meus_dados", porque="Configurações › Meus dados")

    fichas = _fichas_do_nome(p.nome, cadastros)
    if len(fichas) > 1:
        fichas = sorted(fichas, key=lambda f: _chave(f.get("nome", "")))
        opcoes = [{"nome": f["nome"], "pergunta": _pergunta_de(p.campo, f["nome"]), "ficha_id": f.get("id")}
                  for f in fichas[:5]]
        nomes = [f["nome"] for f in fichas[:5]]
        lista = ", ".join(nomes[:-1]) + " e " + nomes[-1]
        mais = f" (e mais {len(fichas) - 5})" if len(fichas) > 5 else ""
        return Resposta("escolher", p.campo,
                        f"Há {len(fichas)} cadastros com “{p.nome}”: {lista}{mais}. De quem é {art} {rotulo}?",
                        nome=p.nome, fonte="cadastros", opcoes=opcoes,
                        porque="o nome casa com mais de uma ficha de Cadastros")

    if len(fichas) == 1:
        ficha = fichas[0]
        nome = ficha["nome"]
        valor, outro = _da_ficha(ficha, p.campo)
        a_ficha = {"ficha_id": ficha.get("id"), "ficha_tipo": ficha.get("tipo", "")}
        if valor and outro:
            return Resposta("achado", p.campo,
                            f"O documento cadastrado de {nome} é o {CAMPOS[outro][1]} {valor}, "
                            f"não um {rotulo} (Cadastros).",
                            nome=nome, fonte="cadastros", porque="a ficha de Cadastros tem outro documento", **a_ficha)
        if valor:
            return Resposta("achado", p.campo, _frase(p.campo, nome, valor, "Cadastros"), nome=nome,
                            fonte="cadastros", porque="a ficha de Cadastros", **a_ficha)
        # A ficha existe, mas sem o dado: o titular (OAB) e os fatos ainda podem ter.
        meus = _dos_meus_dados(Pedido(campo=p.campo, nome=nome), preferencias or {})
        if meus and meus[1]:
            return Resposta("achado", p.campo, _frase(p.campo, meus[0], meus[1], "Meus dados"),
                            nome=meus[0], fonte="meus_dados", porque="Configurações › Meus dados", **a_ficha)
        pelos = _pelos_fatos(p, nome, fatos)
        sem = ("Cadastros não guarda OAB" if p.campo == "oab"
               else f"A ficha de {nome} em Cadastros não tem {rotulo}")
        if pelos and pelos.modo == "achado":
            pelos.texto = sem + ". " + pelos.texto
            pelos.ficha_id, pelos.ficha_tipo = a_ficha["ficha_id"], a_ficha["ficha_tipo"]
            return pelos
        return Resposta("nada", p.campo,
                        f"{sem}, e não encontrei {art} {rotulo} de {nome} no que já foi lido dos documentos.",
                        nome=nome, fonte="cadastros", oferta=True,
                        porque="nem a ficha nem os fatos já lidos dos documentos têm o dado", **a_ficha)

    meus = _dos_meus_dados(p, preferencias or {})
    if meus and meus[1]:
        return Resposta("achado", p.campo, _frase(p.campo, meus[0], meus[1], "Meus dados"), nome=meus[0],
                        fonte="meus_dados", porque="Configurações › Meus dados")

    pelos = _pelos_fatos(p, p.nome, fatos)
    if pelos:
        return pelos

    # Nada em lugar nenhum. CPF/CNPJ/OAB de um nome que nem sequer diz
    # "cadastro" segue para os documentos, como antes (ver o alto do módulo).
    if not (p.de_cadastro or p.campo not in NOS_FATOS):
        return None
    if not (p.nome_proprio or p.de_cadastro):
        return None
    return Resposta("nada", p.campo,
                    f"Não encontrei {art} {rotulo} de {p.nome} nos Cadastros nem no que já foi lido dos documentos.",
                    nome=p.nome, fonte="", oferta=True,
                    porque="nem Cadastros nem os fatos já lidos dos documentos têm o nome")


def proposta(r: Resposta, pergunta: str) -> dict:
    """O cartão da conversa: abrir a ficha, escolher de quem, ou ler os documentos."""
    return {
        "tipo": "consulta_cadastro", "modo": r.modo, "titulo": r.nome, "pergunta": pergunta,
        "campos": {"campo": r.campo, "rotulo": CAMPOS[r.campo][1], "nome": r.nome, "fonte": r.fonte,
                   "ficha_id": r.ficha_id, "ficha_tipo": r.ficha_tipo, "documento": r.documento, "pagina": r.pagina},
        "opcoes": r.opcoes, "oferta": r.oferta, "porque": r.porque, "falta": "",
    }


# --------------------------------------------------- os fatos do metadata


def fatos_dos_documentos(base, biblioteca, nome: str, campo: str, limite: int = 20) -> list[dict]:
    """
    Os fatos conferidos do metadata com este nome: {nome, valor, documento,
    pagina}. O espelho `meta_fatos` acha quem tem o nome (milissegundos, sem
    abrir documento); o metadata.json da versão dá o número e a página. Só a
    versão atual de cada documento, e só `Item.pode_virar_fato`.
    """
    if campo not in NOS_FATOS or base is None or biblioteca is None:
        return []
    secao, tipo = NOS_FATOS[campo]
    alvo = _tokens(nome)
    if not alvo:
        return []
    try:
        linhas = base.buscar(
            "SELECT f.versao_id, f.documento_id, f.item_id, f.mostrar, d.titulo, d.caminho"
            " FROM meta_fatos f JOIN meta_documentos d ON d.versao_atual = f.versao_id"
            " WHERE f.secao = ? AND f.verificado = 1", (secao,))
    except Exception:  # noqa: BLE001 - base sem as tabelas do metadata: sem fatos
        return []
    casam = [l for l in linhas if _contido(alvo, _tokens(l.get("mostrar") or ""))]
    saida: list[dict] = []
    lidos: dict[str, object] = {}
    for l in casam:
        versao = l["versao_id"]
        if versao not in lidos:
            if len(lidos) >= limite:
                break
            lidos[versao] = biblioteca.ler(l["documento_id"], versao)
        meta = lidos[versao]
        if meta is None:
            continue
        item = next((i for i in meta.colecao(secao) if i.id == l["item_id"]), None)
        if item is None or not item.pode_virar_fato or item.dados.get("document_kind") != tipo:
            continue
        documento = l.get("titulo") or (Path(l["caminho"]).name if l.get("caminho") else "documento")
        saida.append({"nome": str(item.dados.get("name") or item.valor), "valor": str(item.dados.get("document", "")),
                      "documento": documento, "pagina": item.source.page})
    return saida
