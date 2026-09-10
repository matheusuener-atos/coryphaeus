"""
PAULUS Legal - Classificacao de documentos por conteudo.

Hibrido de proposito. Data, valor e CPF/CNPJ sao problemas resolvidos por
expressao regular ha decadas: usar LLM para isso e trocar 0,001s por 20s e
ainda arriscar alucinacao. O modelo entra so onde a regra nao decide - tipo do
documento e nomes das partes.

Medido em 2026-09-09, llama3.2:3b em CPU: ~20-27s por documento quando o
modelo e chamado. Por isso o resultado e cacheado por SHA-1 do conteudo:
reclassificar o mesmo acervo e instantaneo, e mover ou renomear o arquivo nao
invalida o cache.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

from extract import Document, extract_file, file_sha1
from llama_client import LlamaClient, OllamaError

# --------------------------------------------------------------------------
# Vocabulario de tipos
# --------------------------------------------------------------------------

TIPOS = {
    "compra_e_venda": [
        "compromisso de compra e venda",
        "contrato de compra e venda",
        "promessa de compra e venda",
        "escritura de compra e venda",
    ],
    "locacao": ["contrato de locacao", "locador", "locataria", "locatario", "aluguel mensal"],
    "prestacao_servicos": [
        "prestacao de servicos",
        "contratada se obriga a prestar",
        "prestador de servicos",
    ],
    "nda": [
        "acordo de confidencialidade",
        "termo de confidencialidade",
        "non disclosure",
        "informacoes confidenciais",
    ],
    "procuracao": ["procuracao", "outorgante", "outorgado", "poderes para o foro em geral"],
    "peticao": [
        "excelentissimo senhor doutor juiz",
        "meritissimo",
        "requer a vossa excelencia",
        "peticao inicial",
    ],
    "trabalhista": ["contrato de trabalho", "clt", "rescisao do contrato de trabalho", "aviso previo"],
    "distrato": ["distrato", "rescisao amigavel", "termo de encerramento"],
}

ROTULOS = {
    "compra_e_venda": "Compra e Venda",
    "locacao": "Locacao",
    "prestacao_servicos": "Prestacao de Servicos",
    "nda": "Confidencialidade",
    "procuracao": "Procuracao",
    "peticao": "Peticao",
    "trabalhista": "Trabalhista",
    "distrato": "Distrato",
    "outro": "Nao classificado",
}

MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}
MESES_NOME = {v: k.capitalize() for k, v in MESES.items()}

# Rotulos que precedem o nome de uma parte em contrato brasileiro.
PAPEIS = (
    "contratante", "contratada", "contratado", "locador", "locadora", "locatario",
    "locataria", "vendedor", "vendedora", "comprador", "compradora", "promitente vendedor",
    "promitente comprador", "outorgante", "outorgado", "cedente", "cessionario",
    "reclamante", "reclamada", "requerente", "requerido",
)

RE_CNPJ = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
RE_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
RE_VALOR = re.compile(r"R\$\s?\d{1,3}(?:\.\d{3})*,\d{2}")
RE_DATA_EXTENSO = re.compile(
    r"\b(\d{1,2})\s*(?:º|o)?\s+de\s+([a-zç]+)\s+de\s+(\d{4})\b", re.IGNORECASE
)
RE_DATA_NUMERICA = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
RE_DATA_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def _sem_acento(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in normalizado if not unicodedata.combining(c))


# --------------------------------------------------------------------------
# Resultado
# --------------------------------------------------------------------------


@dataclass
class Classificacao:
    arquivo: str
    nome: str
    sha1: str
    tipo: str = "outro"
    partes: list[str] = field(default_factory=list)
    cliente: str = ""
    data: str = ""          # ISO (AAAA-MM-DD); vazio quando nao encontrada
    valor: str = ""
    documentos: list[str] = field(default_factory=list)  # CPF/CNPJ encontrados
    origem_tipo: str = "regra"     # "regra" ou "modelo"
    origem_partes: str = "regra"
    erro: str = ""

    @property
    def ano(self) -> str:
        return self.data[:4] if self.data else ""

    @property
    def mes(self) -> str:
        return self.data[5:7] if self.data else ""

    @property
    def mes_nome(self) -> str:
        if not self.data:
            return ""
        return MESES_NOME.get(int(self.data[5:7]), "")

    @property
    def tipo_rotulo(self) -> str:
        return ROTULOS.get(self.tipo, ROTULOS["outro"])

    @property
    def confianca(self) -> str:
        """Alta so quando tipo e cliente vieram com evidencia."""
        if self.erro or self.tipo == "outro" or not self.cliente:
            return "baixa"
        if self.origem_tipo == "regra" and self.origem_partes == "regra":
            return "alta"
        return "media"

    def to_dict(self) -> dict:
        dados = asdict(self)
        dados.update(
            ano=self.ano,
            mes=self.mes,
            mes_nome=self.mes_nome,
            tipo_rotulo=self.tipo_rotulo,
            confianca=self.confianca,
        )
        return dados


# --------------------------------------------------------------------------
# Heuristicas
# --------------------------------------------------------------------------


def detectar_tipo(texto: str) -> str:
    """Tipo pelo vocabulario do proprio documento. 'outro' quando nao decide."""
    plano = _sem_acento(texto.lower())
    pontos: dict[str, int] = {}

    # O cabecalho vale mais: o titulo do contrato esta no comeco.
    cabecalho = plano[:1500]
    for tipo, termos in TIPOS.items():
        for termo in termos:
            alvo = _sem_acento(termo)
            if alvo in cabecalho:
                pontos[tipo] = pontos.get(tipo, 0) + 3
            elif alvo in plano:
                pontos[tipo] = pontos.get(tipo, 0) + 1

    if not pontos:
        return "outro"

    melhor = max(pontos.values())
    empatados = [t for t, p in pontos.items() if p == melhor]
    return empatados[0] if len(empatados) == 1 else "outro"


def detectar_data(texto: str) -> str:
    """
    Data de assinatura em ISO.

    Contrato assina no fim ("Sao Paulo, 23 de janeiro de 2025"), entao o
    trecho final tem prioridade sobre datas citadas no corpo.
    """
    for fatia in (texto[-1500:], texto):
        achado = RE_DATA_EXTENSO.search(fatia)
        if achado:
            dia, mes_texto, ano = achado.groups()
            mes = MESES.get(_sem_acento(mes_texto.lower()))
            if mes:
                return f"{ano}-{mes:02d}-{int(dia):02d}"

        achado = RE_DATA_NUMERICA.search(fatia)
        if achado:
            dia, mes, ano = (int(g) for g in achado.groups())
            if 1 <= mes <= 12 and 1 <= dia <= 31:
                return f"{ano}-{mes:02d}-{dia:02d}"

        achado = RE_DATA_ISO.search(fatia)
        if achado:
            ano, mes, dia = achado.groups()
            if 1 <= int(mes) <= 12:
                return f"{ano}-{mes}-{dia}"

    return ""


def detectar_valor(texto: str) -> str:
    """Maior valor em reais do documento - normalmente o valor principal."""
    achados = RE_VALOR.findall(texto)
    if not achados:
        return ""

    def numero(v: str) -> float:
        limpo = v.replace("R$", "").strip().replace(".", "").replace(",", ".")
        try:
            return float(limpo)
        except ValueError:
            return 0.0

    return max(achados, key=numero)


def detectar_documentos(texto: str) -> list[str]:
    return list(dict.fromkeys(RE_CNPJ.findall(texto) + RE_CPF.findall(texto)))


def detectar_partes(texto: str) -> list[str]:
    """
    Nomes que aparecem logo apos um papel contratual (CONTRATANTE:, VENDEDOR:).

    E o padrao dominante em contrato brasileiro. Quando nao casa, o modelo
    assume - e mais caro, mas le o que a regra nao alcanca.
    """
    achados: list[tuple[int, str]] = []
    plano = _sem_acento(texto)

    for papel in PAPEIS:
        for casamento in re.finditer(rf"\b{papel}\b\s*[:\-–]\s*", plano, re.IGNORECASE):
            trecho = texto[casamento.end() : casamento.end() + 120]
            nome = _primeiro_nome(trecho)
            if nome:
                achados.append((casamento.start(), nome))

    # Ordem do documento, nao a ordem da lista PAPEIS: "primeira parte citada"
    # tem que significar primeira no texto, senao o cliente eleito depende de
    # como esta escrita a constante aqui em cima.
    achados.sort(key=lambda item: item[0])
    return _unicos([nome for _, nome in achados])


def _primeiro_nome(trecho: str) -> str:
    """
    Recorta o nome no inicio do trecho, parando na primeira pontuacao forte.

    Aceita nome de pessoa e razao social (LTDA, S.A.), com ou sem caixa alta.
    """
    corte = re.split(r"[,;\n]|\bCPF\b|\bCNPJ\b|\binscrit|\bportador|\bbrasileir", trecho, maxsplit=1)[0]
    nome = " ".join(corte.split()).strip(" .-–:")

    if len(nome) < 5 or len(nome) > 90:
        return ""
    if not re.search(r"[A-Za-zÀ-ÿ]{3}", nome):
        return ""
    # Um nome tem ao menos duas palavras (nome + sobrenome, ou razao social).
    if len(nome.split()) < 2:
        return ""
    return nome


def _unicos(nomes: list[str]) -> list[str]:
    vistos: set[str] = set()
    saida: list[str] = []
    for nome in nomes:
        chave = _sem_acento(nome.lower())
        if chave not in vistos:
            vistos.add(chave)
            saida.append(nome)
    return saida


def escolher_cliente(partes: list[str]) -> str:
    """
    Qual das partes nomeia a pasta.

    Sem saber quem e o cliente do escritorio, a primeira parte citada e o
    melhor palpite - e o usuario corrige na tela antes de qualquer arquivo se
    mover.
    """
    return partes[0] if partes else ""


# --------------------------------------------------------------------------
# Modelo (so quando a regra nao decide)
# --------------------------------------------------------------------------

ESQUEMA = '{"tipo": "locacao", "partes": ["NOME COMPLETO DA PRIMEIRA PARTE", "NOME DA SEGUNDA"]}'

INSTRUCAO = (
    "Classifique este documento juridico brasileiro.\n"
    "- tipo: exatamente um de [" + ", ".join(TIPOS) + ", outro]\n"
    "- partes: nomes das pessoas ou empresas que assinam. Copie o nome como "
    "esta escrito, sem abreviar. Se nao houver nome legivel, devolva lista vazia.\n"
    "Nao explique. Nao invente nome que nao esteja no texto."
)


def classificar_com_modelo(texto: str, client: LlamaClient) -> tuple[str, list[str]]:
    """Devolve (tipo, partes) segundo o modelo. Excerto curto: o cabecalho basta."""
    resposta = client.ask_json(INSTRUCAO, texto[:3000], ESQUEMA)
    if not isinstance(resposta, dict):
        return "", []

    tipo = str(resposta.get("tipo", "")).strip().lower()
    if tipo not in TIPOS and tipo != "outro":
        tipo = ""

    brutas = resposta.get("partes", [])
    partes = [str(p).strip() for p in brutas if isinstance(p, str)] if isinstance(brutas, list) else []
    # O modelo as vezes devolve a frase de "nao encontrei" como se fosse nome.
    partes = [p for p in partes if 5 <= len(p) <= 90 and "nao encontrei" not in _sem_acento(p.lower())]

    return tipo, _unicos(partes)


# --------------------------------------------------------------------------
# Classificacao de um documento e de um acervo
# --------------------------------------------------------------------------


def classificar_documento(
    doc: Document,
    client: LlamaClient | None = None,
    *,
    usar_modelo: bool = True,
) -> Classificacao:
    texto = doc.text
    resultado = Classificacao(arquivo=doc.path, nome=doc.name, sha1=doc.sha1)

    resultado.tipo = detectar_tipo(texto)
    resultado.data = detectar_data(texto)
    resultado.valor = detectar_valor(texto)
    resultado.documentos = detectar_documentos(texto)
    resultado.partes = detectar_partes(texto)

    # O nome do arquivo costuma trazer o tipo quando o texto nao traz.
    if resultado.tipo == "outro":
        pelo_nome = detectar_tipo(doc.name.replace("_", " ").replace("-", " "))
        if pelo_nome != "outro":
            resultado.tipo = pelo_nome

    precisa_tipo = resultado.tipo == "outro"
    # Contrato tem no minimo duas partes. Uma so significa que a regra pegou
    # apenas um dos papeis - vale o custo de perguntar ao modelo.
    precisa_partes = len(resultado.partes) < 2

    if usar_modelo and client and (precisa_tipo or precisa_partes):
        try:
            tipo, partes = classificar_com_modelo(texto, client)
            if precisa_tipo and tipo:
                resultado.tipo = tipo
                resultado.origem_tipo = "modelo"
            if precisa_partes and len(partes) > len(resultado.partes):
                resultado.partes = partes
                resultado.origem_partes = "modelo"
        except OllamaError as exc:
            resultado.erro = str(exc)

    resultado.cliente = escolher_cliente(resultado.partes)
    return resultado


# Suba isto ao mudar heuristica, prompt ou vocabulario de tipos. Sem versao, o
# cache por SHA-1 devolveria a classificacao antiga para sempre - o arquivo nao
# mudou, mas o classificador mudou.
VERSAO_CLASSIFICADOR = 3


class CacheClassificacao:
    """Resultados por SHA-1: mover ou renomear o arquivo nao invalida."""

    def __init__(self, caminho: Path) -> None:
        self.caminho = Path(caminho)
        self.dados: dict[str, dict] = {}

        if not self.caminho.exists():
            return
        try:
            bruto = json.loads(self.caminho.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return

        if isinstance(bruto, dict) and bruto.get("versao") == VERSAO_CLASSIFICADOR:
            self.dados = bruto.get("itens", {})

    def obter(self, sha: str) -> Classificacao | None:
        bruto = self.dados.get(sha)
        if not bruto:
            return None
        campos = {k: v for k, v in bruto.items() if k in Classificacao.__dataclass_fields__}
        return Classificacao(**campos)

    def guardar(self, resultado: Classificacao) -> None:
        self.dados[resultado.sha1] = asdict(resultado)

    def salvar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        payload = {"versao": VERSAO_CLASSIFICADOR, "itens": self.dados}
        self.caminho.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def classificar_acervo(
    caminhos: list[str],
    *,
    cache_path: Path | None = None,
    client: LlamaClient | None = None,
    usar_modelo: bool = True,
    progresso=None,
    cancelado=None,
    antes_de_cada=None,
) -> list[Classificacao]:
    """
    Classifica uma lista de arquivos, reaproveitando o cache.

    `progresso(indice, total, nome, do_cache)` e chamado a cada documento -
    a leitura leva minutos e a interface precisa mostrar andamento.

    `cancelado()` e consultado antes de cada documento: um acervo grande leva
    quase uma hora e a pessoa precisa poder desistir. O que ja foi classificado
    ate ali e devolvido, e o cache guarda.

    `antes_de_cada()` roda antes de cada documento - e onde entra o "ir devagar
    quando eu usar o PC".
    """
    cache = CacheClassificacao(cache_path) if cache_path else None
    resultados: list[Classificacao] = []
    total = len(caminhos)

    for indice, caminho in enumerate(caminhos, start=1):
        if cancelado and cancelado():
            break
        if antes_de_cada:
            antes_de_cada()

        alvo = Path(caminho)
        try:
            sha = file_sha1(alvo)
        except OSError as exc:
            resultados.append(
                Classificacao(arquivo=str(alvo), nome=alvo.name, sha1="", erro=f"sem acesso: {exc}")
            )
            continue

        guardado = cache.obter(sha) if cache else None
        if guardado:
            guardado.arquivo = str(alvo)
            guardado.nome = alvo.name
            resultados.append(guardado)
            if progresso:
                progresso(indice, total, alvo.name, True)
            continue

        try:
            texto, paginas = extract_file(alvo)
        except Exception as exc:
            resultados.append(
                Classificacao(arquivo=str(alvo), nome=alvo.name, sha1=sha, erro=str(exc))
            )
            if progresso:
                progresso(indice, total, alvo.name, False)
            continue

        if not texto.strip():
            resultados.append(
                Classificacao(
                    arquivo=str(alvo),
                    nome=alvo.name,
                    sha1=sha,
                    erro="sem texto extraivel (PDF escaneado?)",
                )
            )
            if progresso:
                progresso(indice, total, alvo.name, False)
            continue

        doc = Document(name=alvo.name, path=str(alvo), text=texto, pages=paginas, sha1=sha)
        resultado = classificar_documento(doc, client, usar_modelo=usar_modelo)
        resultados.append(resultado)

        if cache:
            cache.guardar(resultado)
        if progresso:
            progresso(indice, total, alvo.name, False)

    if cache:
        cache.salvar()

    return resultados
