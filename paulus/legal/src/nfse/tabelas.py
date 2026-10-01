"""
As tabelas oficiais da NFS-e: municípios, serviços, NBS, indicador da
operação e os domínios que moram no XSD.

Cada tabela é um JSON com versão, data e o link de onde veio. As que vêm no
PAULUS ficam em src/nfse/tabelas/; uma planilha nova, importada pela tela,
vai para a pasta de dados e passa a valer se a versão dela for mais nova. Nada
é editado à mão no código: o que muda na documentação muda por arquivo, como
as leis.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path

PASTA_EMBUTIDA = Path(__file__).resolve().parent / "tabelas"
PASTA_XSD = Path(__file__).resolve().parent / "xsd"

BASE_DOC = "https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica"

# Qual planilha vira qual tabela. O padrão casa com o nome que o portal dá ao
# arquivo; a versão e a data saem do próprio nome.
PLANILHAS = {
    "municipios": re.compile(r"anexo_a-municipio_ibge.*\.xlsx$", re.I),
    "servicos": re.compile(r"anexo_b-nbs2-lista_servico_nacional.*\.xlsx$", re.I),
    "indop": re.compile(r"anexo[-_]c-indop.*\.xlsx$", re.I),
    "correlacao": re.compile(r"anexoviii-correlacao.*\.xlsx$", re.I),
}

# Os domínios do XSD que a tela e a conta usam. Nome da tabela -> tipo simples.
DOMINIOS_XSD = {
    "motivo_cancelamento": "TSCodJustCanc",
    "motivo_substituicao": "TSCodJustSubst",
    "regime_especial": "TSRegEspTrib",
    "opcao_simples": "TSOpSimpNac",
    "regime_apuracao_sn": "TSRegimeApuracaoSimpNac",
    "retencao_pis_cofins": "TSTipoRetPISCofins",
    "retencao_iss": "TSTipoRetISSQN",
    "tributacao_iss": "TSTribISSQN",
    "cst_pis_cofins": "TSTipoCST",
}

# Código IBGE do estado (os dois primeiros dígitos do código do município).
UF_DO_CODIGO = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}

_trava = threading.Lock()
_cache: dict[str, dict] = {}
_pasta_dados: Path | None = None


# ------------------------------------------------------------ leitura

def usar_pasta_de_dados(pasta: Path | str | None) -> None:
    """Onde ficam as tabelas importadas pela tela (a pasta de dados)."""
    global _pasta_dados
    with _trava:
        _pasta_dados = Path(pasta) if pasta else None
        _cache.clear()


def _ler(caminho: Path) -> dict | None:
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _chave_versao(t: dict) -> tuple:
    """Compara versões como números ("1.01.00" > "1.00"), depois pela data."""
    partes = tuple(int(p) for p in re.findall(r"\d+", str(t.get("versao") or "0")))
    return partes, str(t.get("data") or "")


def carregar(nome: str) -> dict:
    """A tabela `nome` mais nova entre a embutida e a importada."""
    with _trava:
        if nome in _cache:
            return _cache[nome]
        candidatas = [_ler(PASTA_EMBUTIDA / f"{nome}.json")]
        if _pasta_dados:
            candidatas.append(_ler(_pasta_dados / f"{nome}.json"))
        validas = [c for c in candidatas if c and isinstance(c.get("itens"), list)]
        tabela = max(validas, key=_chave_versao) if validas else {"nome": nome, "versao": "", "itens": []}
        _cache[nome] = tabela
        return tabela


def versoes() -> list[dict]:
    """O que a tela mostra: cada tabela com versão, data, fonte e tamanho."""
    saida = []
    for nome in ("municipios", "servicos", "nbs", "indop", "correlacao", "dominios"):
        t = carregar(nome)
        saida.append({"nome": nome, "titulo": t.get("titulo", nome), "versao": t.get("versao", ""),
                      "data": t.get("data", ""), "fonte": t.get("fonte", ""), "itens": len(t.get("itens") or [])})
    return saida


def _indice(nome: str, campo: str = "codigo") -> dict:
    chave = f"{nome}#{campo}"
    with _trava:
        if chave in _cache:
            return _cache[chave]
    tabela = carregar(nome)
    indice = {str(i.get(campo)): i for i in tabela.get("itens") or []}
    with _trava:
        _cache[chave] = indice
    return indice


def municipio(codigo: str) -> dict | None:
    return _indice("municipios").get(re.sub(r"\D", "", str(codigo or "")))


def _sem_acento(texto: str) -> str:
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn").lower().strip()


def buscar_municipios(nome: str, uf: str = "", limite: int = 10) -> list[dict]:
    """Municípios pelo nome (sem acento, começo de palavra primeiro)."""
    alvo = _sem_acento(nome)
    if not alvo:
        return []
    uf = (uf or "").upper().strip()
    exatos, comecam, contem = [], [], []
    for m in carregar("municipios").get("itens") or []:
        if uf and m.get("uf") != uf:
            continue
        n = _sem_acento(m.get("nome", ""))
        if n == alvo:
            exatos.append(m)
        elif n.startswith(alvo):
            comecam.append(m)
        elif alvo in n:
            contem.append(m)
    return (exatos + comecam + contem)[:limite]


def servico(codigo: str) -> dict | None:
    return _indice("servicos").get(re.sub(r"\D", "", str(codigo or "")).zfill(6))


def nbs(codigo: str) -> dict | None:
    """A NBS pelo código com ou sem pontos."""
    return _indice("nbs").get(re.sub(r"\D", "", str(codigo or "")))


def indop(codigo: str) -> dict | None:
    return _indice("indop").get(re.sub(r"\D", "", str(codigo or "")))


def dominio(nome: str) -> dict[str, str]:
    """Um domínio do XSD como {código: rótulo}."""
    for d in carregar("dominios").get("itens") or []:
        if d.get("nome") == nome:
            return dict(d.get("valores") or {})
    return {}


def correlacao_do_item(item: str) -> list[dict]:
    """As sugestões do Anexo VIII para um item da LC 116 ("17.14")."""
    alvo = str(item or "").strip()
    return [c for c in carregar("correlacao").get("itens") or [] if c.get("item") == alvo]


# ------------------------------------------------------------ geração

def _versao_do_nome(nome: str) -> tuple[str, str]:
    """"...-v1-01-20260122.xlsx" -> ("1.01", "2026-01-22"); "..._v1-01-00.xlsx" -> ("1.01.00", "")."""
    base = Path(nome).stem.lower()
    m = re.search(r"v(\d+(?:-\d+)*)", base)
    versao, data = "", ""
    if m:
        partes = m.group(1).split("-")
        if partes and len(partes[-1]) == 8:
            data_bruta = partes.pop()
            data = f"{data_bruta[:4]}-{data_bruta[4:6]}-{data_bruta[6:]}"
        versao = ".".join(partes)
    if not data:
        d = re.search(r"(20\d{6})", base)
        if d:
            data = f"{d.group(1)[:4]}-{d.group(1)[4:6]}-{d.group(1)[6:]}"
    return versao, data


def _linhas(caminho: Path, folha_contem: str):
    import openpyxl

    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    try:
        for ws in wb.worksheets:
            if folha_contem.lower() in ws.title.lower():
                for linha in ws.iter_rows(values_only=True):
                    yield [("" if c is None else str(c).strip()) for c in linha]
                return
    finally:
        wb.close()


def _municipios(caminho: Path) -> list[dict]:
    # A planilha mescla a célula da UF (só algumas linhas trazem a sigla). A
    # UF sai dos dois primeiros dígitos do código IBGE, que são o código do
    # estado: é a regra de formação do próprio código.
    itens = []
    for l in _linhas(caminho, "MUN_IBGE"):
        if len(l) >= 4 and re.fullmatch(r"\d{7}", l[3]):
            itens.append({"codigo": l[3], "nome": l[2], "uf": UF_DO_CODIGO.get(l[3][:2], "")})
    return itens


def _servicos_e_nbs(caminho: Path) -> tuple[list[dict], list[dict]]:
    servicos = []
    for l in _linhas(caminho, "SERV.NAC"):
        if len(l) < 5 or not re.fullmatch(r"\d+", l[1] or ""):
            continue
        codigo = l[0]
        item, subitem, desdobro = l[1], l[2], l[3]
        if codigo and re.fullmatch(r"\d{5,6}", codigo):
            servicos.append({"codigo": codigo.zfill(6), "item": f"{int(item):02d}.{int(subitem):02d}",
                             "desdobro": desdobro, "descricao": l[4]})
    nbs_itens = []
    for l in _linhas(caminho, "NBS"):
        if len(l) < 2:
            continue
        bruto = l[0].strip()
        if re.fullmatch(r"\d\.\d{4}\.\d{2}\.\d{2}", bruto):
            nbs_itens.append({"codigo": bruto.replace(".", ""), "nbs": bruto, "descricao": l[1]})
    return servicos, nbs_itens


def _indop(caminho: Path) -> list[dict]:
    itens = []
    tipo = local = ""
    for l in _linhas(caminho, "IndOp"):
        if len(l) < 8:
            continue
        if l[1]:
            tipo = l[1]
        if l[2]:
            local = l[2]
        codigo = l[6]
        if re.fullmatch(r"\d{6}", codigo):
            itens.append({"codigo": codigo, "tipo": re.sub(r"\s*\|\s*", " ", tipo),
                          "local_operacao": re.sub(r"\s*\|\s*", " ", local), "local_fornecimento": l[7]})
    return itens


def _correlacao(caminho: Path) -> list[dict]:
    itens = []
    item = descricao = ""
    for l in _linhas(caminho, "tabela geral"):
        if len(l) < 10:
            continue
        if re.fullmatch(r"\d{2}\.\d{2}", l[0]):
            item, descricao = l[0], l[1]
        if not item or not re.fullmatch(r"\d\.\d{4}\.\d{2}\.\d{2}", l[2] or ""):
            continue
        itens.append({"item": item, "descricao_item": descricao, "nbs": l[2].replace(".", ""),
                      "nbs_pontos": l[2], "descricao_nbs": l[3], "indop": l[6], "local": l[7],
                      "cclasstrib": l[8], "descricao_cclasstrib": l[9]})
    # Linhas de continuação herdam o cIndOp e o cClassTrib da primeira do item
    # quando a planilha deixa a célula em branco (é como o anexo é desenhado).
    ultimo: dict = {}
    for c in itens:
        if c["item"] != ultimo.get("item"):
            ultimo = dict(c)
        for campo in ("indop", "local", "cclasstrib", "descricao_cclasstrib"):
            if not c[campo]:
                c[campo] = ultimo.get(campo, "")
            else:
                ultimo[campo] = c[campo]
    return itens


def _dominios(pasta_xsd: Path) -> list[dict]:
    from lxml import etree

    ns = {"xs": "http://www.w3.org/2001/XMLSchema"}
    arvore = etree.parse(str(pasta_xsd / "tiposSimples_v1.01.xsd"))
    saida = []
    for nome, tipo in DOMINIOS_XSD.items():
        st = arvore.find(f".//xs:simpleType[@name='{tipo}']", ns)
        if st is None:
            continue
        valores = [e.get("value") for e in st.findall(".//xs:enumeration", ns)]
        doc = " ".join(st.xpath(".//xs:documentation//text()", namespaces=ns))
        rotulos: dict[str, str] = {}
        for linha in re.split(r"[\n;]", doc):
            m = re.match(r"\s*(\d{1,2})\s*[-–]\s*(.+?)\s*$", linha)
            if m:
                rotulos[m.group(1)] = m.group(2).rstrip(";").strip()
        saida.append({"nome": nome, "tipo": tipo,
                      "valores": {v: rotulos.get(v, rotulos.get(v.lstrip("0") or "0", v)) for v in valores}})
    return saida


def _gravar(destino: Path, nome: str, titulo: str, versao: str, data: str, fonte: str, itens: list) -> dict:
    destino.mkdir(parents=True, exist_ok=True)
    corpo = {"nome": nome, "titulo": titulo, "versao": versao, "data": data, "fonte": fonte,
             "gerado_em": datetime.now().isoformat(timespec="seconds"), "itens": itens}
    (destino / f"{nome}.json").write_text(json.dumps(corpo, ensure_ascii=False, indent=0), encoding="utf-8")
    return {"versao": versao, "data": data, "itens": len(itens)}


def importar(caminho: Path, destino: Path) -> dict:
    """Uma planilha oficial vira a(s) tabela(s) dela em `destino`."""
    nome_arq = caminho.name
    versao, data = _versao_do_nome(nome_arq)
    gravadas: dict[str, dict] = {}
    if PLANILHAS["municipios"].search(nome_arq):
        gravadas["municipios"] = _gravar(destino, "municipios", "Municípios (IBGE)", versao, data,
                                         f"{BASE_DOC}/documentacao-atual/{nome_arq}", _municipios(caminho))
    elif PLANILHAS["servicos"].search(nome_arq):
        serv, nbs_itens = _servicos_e_nbs(caminho)
        gravadas["servicos"] = _gravar(destino, "servicos", "Lista de serviços nacional (cTribNac)", versao, data,
                                       f"{BASE_DOC}/documentacao-atual/{nome_arq}", serv)
        gravadas["nbs"] = _gravar(destino, "nbs", "NBS 2.0", versao, data,
                                  f"{BASE_DOC}/documentacao-atual/{nome_arq}", nbs_itens)
    elif PLANILHAS["indop"].search(nome_arq):
        gravadas["indop"] = _gravar(destino, "indop", "Indicador da operação (cIndOp)", versao, data,
                                    f"{BASE_DOC}/documentacao-atual/{nome_arq}", _indop(caminho))
    elif PLANILHAS["correlacao"].search(nome_arq):
        gravadas["correlacao"] = _gravar(destino, "correlacao",
                                         "Correlação item × NBS × cIndOp × cClassTrib (sugestão, sem regra de negócio)",
                                         versao, data, f"{BASE_DOC}/rtc/{nome_arq}", _correlacao(caminho))
    else:
        raise ValueError("não reconheço esta planilha: use o arquivo com o nome que o portal da NFS-e dá")
    for nome, info in gravadas.items():
        if not info["itens"]:
            raise ValueError(f"a planilha não trouxe nenhum item de {nome}: confira se é a planilha oficial")
    with _trava:
        _cache.clear()
    return gravadas


def gerar_de_pasta(pasta: Path, destino: Path) -> dict:
    """Todas as planilhas oficiais de uma pasta, mais os domínios do XSD."""
    gravadas: dict[str, dict] = {}
    for arq in sorted(Path(pasta).glob("*.xlsx")):
        if "prodrest" in arq.name.lower():
            continue  # a mesma tabela, versão de homologação: vale a de produção
        if any(p.search(arq.name) for p in PLANILHAS.values()):
            gravadas.update(importar(arq, destino))
    pasta_xsd = PASTA_XSD / "1.01-20260727"
    gravadas["dominios"] = _gravar(destino, "dominios", "Domínios do XSD", "1.01", "2026-07-27",
                                   f"{BASE_DOC}/producao-restrita/esquemas-nfse-rtc-v1-01-20260727.zip",
                                   _dominios(pasta_xsd))
    with _trava:
        _cache.clear()
    return gravadas
