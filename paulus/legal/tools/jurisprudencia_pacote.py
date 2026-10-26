"""
A jurisprudência consolidada que vem com o PAULUS, além das súmulas do STJ e do
STF (tools/acervo_inicial.py, tools/stf_pacote.py): por ora, a do TST.

O TST publica o "Livro de Súmulas, OJs e PNs" (www.tst.jus.br/livro-de-sumulas-
ojs-e-pns), em PDF e em RTF. O PDF quebra as palavras na extração ("poss í-
vel"); o RTF sai limpo, e cada verbete começa com o código dele numa linha:

    SUM-8    JUNTADA DE DOCUMENTO (mantida - Res. 121/2003 ...). - Entendimento reafirmado no IRR nº 286.
    <o enunciado vigente>
    IRR-286  JUNTADA DE DOCUMENTO NA FASE RECURSAL. (RR-..., Tribunal Pleno, publicado em 03.09.2025 ...)
    <a tese do recurso repetitivo>
    Histórico:
    <as redações de antes>

Entra o que vale hoje: o cancelado ("cancelada", "cancelamento mantido",
"cancelado pela SDC") fica fora, o histórico também. A tese do IRR vai junto
do verbete que ela reafirmou. Saem três textos, no formato que a Biblioteca
já divide um verbete por trecho (src/biblioteca/sumulas.py):

    Súmula 8 do TST / OJ 394 da SBDI-1 do TST / Precedente Normativo 119 do TST

Decisão judicial não tem direito autoral (Lei 9.610/98, art. 8º, IV).

    venv\\Scripts\\python.exe tools\\jurisprudencia_pacote.py
"""

from __future__ import annotations

import gzip
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))

import rtf_em_texto  # noqa: E402

DESTINO = RAIZ / "config" / "acervo-inicial"
CABECA = {"User-Agent": "Mozilla/5.0 PAULUS"}
TST_RTF = "https://www.tst.jus.br/documents/d/guest/livrointernet-12-rtf"
TST_PAGINA = "https://www.tst.jus.br/livro-de-sumulas-ojs-e-pns"

# O codigo e o titulo vem separados por tabulacao, menos da Sumula 431 a 447,
# que o livro separa por espaco - sem isso, a 443 (dispensa discriminatoria)
# ficava fora.
RE_CABECA = re.compile(r"^(SUM|OJ-SDI1T|OJ-SDI1|OJ-SDI2|OJ-SDC|PN|IRR)-(\d+[A-Z]?)[\t ]+(.*)$")
RE_CANCELADO = re.compile(r"\(\s*cancelad[oa]|cancelamento mantido|\bcancelad[oa] pel[ao]", re.IGNORECASE)
# A situacao e a resolucao saem do titulo: "(mantida) - Res. 121/2003, DJ ..." nao e o assunto.
RE_SITUACAO = re.compile(
    r"\s*[-–]?\s*\((?:mantid|cancelad|nova reda|reda[çc][ãa]o|alterad|atualizad|convers|incorporad|inserid|inclu[íi]d"
    r"|aglutinad|republicad|t[íi]tulo|item|itens|negativo|positivo).*$", re.IGNORECASE)
NOMES = {
    "SUM": "Súmula {n} do TST",
    "OJ-SDI1": "OJ {n} da SBDI-1 do TST",
    "OJ-SDI1T": "OJ {n} da SBDI-1 Transitória do TST",
    "OJ-SDI2": "OJ {n} da SBDI-2 do TST",
    "OJ-SDC": "OJ {n} da SDC do TST",
    "PN": "Precedente Normativo {n} do TST",
}
ARQUIVOS = {
    "tst": ("sumulas-tst.txt.gz", "Súmulas do TST", ("SUM",)),
    "tst_ojs": ("ojs-tst.txt.gz", "Orientações Jurisprudenciais do TST", ("OJ-SDI1", "OJ-SDI1T", "OJ-SDI2", "OJ-SDC")),
    "tst_pns": ("pns-tst.txt.gz", "Precedentes Normativos do TST", ("PN",)),
}


def _titulo(resto: str) -> str:
    return RE_SITUACAO.sub("", resto).strip(" .-–\t")


def verbetes_do_tst(texto: str) -> tuple[dict[str, list[tuple[str, str, str]]], dict]:
    """
    {tipo: [(numero, titulo, enunciado)]} do que vale hoje, e as contas.
    Só a parte de verbetes: o que vem do primeiro "Índice Remissivo" em diante
    repete os códigos como índice.
    """
    linhas = texto.split("\n")
    fim = next((i for i, l in enumerate(linhas) if i > 1000 and re.match(r"^\s*[ÍI]ndice Remissivo", l, re.I)),
               len(linhas))
    saida: dict[str, list[tuple[str, str, str]]] = {t: [] for t in NOMES}
    contas = {"canceladas_fora": 0, "irr_juntos": 0}
    vistos: set[tuple[str, str]] = set()
    atual = None   # [tipo, numero, titulo, partes, cancelado]

    def fechar() -> None:
        if atual and not atual[4] and atual[0] in saida:
            enunciado = " ".join(" ".join(atual[3]).split())
            if enunciado:
                saida[atual[0]].append((atual[1], atual[2], enunciado))

    lendo_historico = False
    for linha in linhas[:fim]:
        m = RE_CABECA.match(linha.strip())   # a Sumula 72 vem com espacos na frente
        if m:
            tipo, numero, resto = m.groups()
            if tipo == "IRR":
                # A tese do recurso repetitivo vai junto do verbete que ela reafirmou.
                if atual is not None and not lendo_historico:
                    atual[3].append(f"[Reafirmado no IRR nº {numero}, tese vinculante: ")
                    atual[5] = True
                    contas["irr_juntos"] += 1
                lendo_historico = False
                continue
            fechar()
            lendo_historico = False
            if (tipo, numero) in vistos:
                atual = None
                continue
            vistos.add((tipo, numero))
            cancelado = bool(RE_CANCELADO.search(resto))
            contas["canceladas_fora"] += cancelado
            atual = [tipo, numero, _titulo(resto), [], cancelado, False]
            continue
        if atual is None:
            continue
        if re.match(r"^\s*Hist[óo]rico\s*:", linha):
            if atual[5]:
                atual[3].append("]")
                atual[5] = False
            lendo_historico = True
            continue
        if lendo_historico or not linha.strip():
            continue
        atual[3].append(linha.strip())
    fechar()
    return saida, contas


def texto_do_pacote(saida: dict, tipos: tuple[str, ...]) -> tuple[str, int]:
    partes, n = [], 0
    for tipo in tipos:
        for numero, titulo, enunciado in sorted(saida[tipo], key=lambda x: (int(re.sub(r"\D", "", x[0])), x[0])):
            enunciado = enunciado.replace(" ]", "]")
            partes.append(f"{NOMES[tipo].format(n=numero)}\n{titulo}. {enunciado}\n\n" if titulo else
                          f"{NOMES[tipo].format(n=numero)}\n{enunciado}\n\n")
            n += 1
    return "".join(partes), n


def montar_tst(indice: dict, rtf: bytes | None = None) -> None:
    if rtf is None:
        r = requests.get(TST_RTF, timeout=600, headers=CABECA)
        r.raise_for_status()
        rtf = r.content
    saida, contas = verbetes_do_tst(rtf_em_texto.converter(rtf))
    # Abaixo disto o livro mudou de formato (medido em 25/10/2026: 300 sumulas,
    # 379 OJs e 74 PNs vigentes).
    minimos = {"tst": 250, "tst_ojs": 300, "tst_pns": 60}
    for chave, (arquivo, nome, tipos) in ARQUIVOS.items():
        texto, n = texto_do_pacote(saida, tipos)
        if n < minimos[chave]:
            raise SystemExit(f"{nome}: só {n} verbetes vigentes - o livro do TST mudou de formato?")
        (DESTINO / arquivo).write_bytes(gzip.compress(texto.encode("utf-8"), 9, mtime=0))
        indice["sumulas"][chave] = {"arquivo": arquivo, "nome": nome, "enunciados": n, "fonte": TST_PAGINA,
                                    "autor": "Tribunal Superior do Trabalho",
                                    "areas": ["trabalho", "processo do trabalho"],
                                    "baixado_em": datetime.now().isoformat(timespec="seconds")}
        print(f"{nome}: {n} vigentes")
    indice["sumulas"]["tst"]["canceladas_fora"] = contas["canceladas_fora"]
    indice["sumulas"]["tst"]["irr_juntos"] = contas["irr_juntos"]
    print(f"TST: {contas['canceladas_fora']} canceladas ficaram fora; {contas['irr_juntos']} teses de IRR junto do verbete")


# ------------------------------------------------------------------ CJF
#
# Os enunciados das Jornadas do Conselho da Justiça Federal (Direito Civil,
# Processual Civil, Comercial...): a base oficial (www.cjf.jus.br/enunciados)
# tem uma página por enunciado, com a jornada, o número e o texto. O endereço
# é um identificador interno, não o número, e tem buracos: percorre-se tudo,
# com uma pausa entre as páginas e cada uma guardada (a coleta para e volta).

CJF_PAGINA = "https://www.cjf.jus.br/enunciados/enunciado/{id}"
CJF_FONTE = "https://www.cjf.jus.br/enunciados/"
RE_CJF = re.compile(r"Enunciado (\d+) Jornada (.+?) Coordenador.*?N[úu]mero \d+ Enunciado (.+?)"
                    r"(?: Justificativa | Refer[êe]ncia Legislativa | Palavras de Resgate | Conselho da Justi)", re.S)
# Agrupadas por assunto; a jornada vai em cada enunciado.
CJF_GRUPOS = {
    "cjf_civil": ("enunciados-cjf-civil.txt.gz", "Enunciados das Jornadas de Direito Civil (CJF)",
                  r"Direito Civil$", ["civil", "família e sucessões", "imobiliário", "consumidor"]),
    "cjf_processo": ("enunciados-cjf-processo-civil.txt.gz", "Enunciados das Jornadas de Direito Processual Civil (CJF)",
                     r"Processual Civil$|Processo Civil$", ["processo civil"]),
    "cjf_comercial": ("enunciados-cjf-comercial.txt.gz", "Enunciados das Jornadas de Direito Comercial (CJF)",
                      r"Direito Comercial$|Empresarial$", ["empresarial"]),
    # As jornadas de um tema só (Notarial e Registral, Seguridade Social,
    # Tributário...): juntas, cada enunciado com a jornada dele.
    "cjf_outras": ("enunciados-cjf-outras.txt.gz", "Enunciados de outras Jornadas do CJF",
                   r"Notarial|Seguridade|Tribut[áa]rio|Administrativo|Penal|Extrajudicial|Sa[úu]de|Desportivo"
                   r"|Ambientais|Patrim[ôo]nio|Equidade",
                   ["imobiliário", "previdenciário", "tributário", "administrativo", "penal", "processo penal", "outra"]),
}


def _texto_da_pagina(bruto: str) -> str:
    import html as _html

    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", bruto, flags=re.S | re.I)
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def coletar_cjf(cache: Path, ate: int = 4000, buraco: int = 400, pausa: float = 0.3) -> list[dict]:
    """[{id, numero, jornada, texto}] - lendo do cache o que já veio."""
    import time

    cache.mkdir(parents=True, exist_ok=True)
    saida, vazios, sessao = [], 0, requests.Session()
    sessao.headers.update(CABECA)
    for id_ in range(1, ate + 1):
        arquivo = cache / f"{id_}.html"
        if arquivo.exists():
            bruto = arquivo.read_text(encoding="utf-8")
        else:
            for tentativa in range(4):
                try:
                    r = sessao.get(CJF_PAGINA.format(id=id_), timeout=60)
                    break
                except requests.RequestException:
                    time.sleep(5 * (tentativa + 1))
            else:
                raise SystemExit(f"CJF: a página {id_} não respondeu - rode de novo, o que veio está guardado")
            bruto = r.text if r.status_code == 200 else ""
            arquivo.write_text(bruto, encoding="utf-8")
            time.sleep(pausa)
        m = RE_CJF.search(_texto_da_pagina(bruto)) if bruto else None
        if not m:
            vazios += 1
            if vazios >= buraco and id_ > 1500:
                break
            continue
        vazios = 0
        saida.append({"id": id_, "numero": int(m.group(1)), "jornada": m.group(2).strip(), "texto": m.group(3).strip()})
        if len(saida) % 200 == 0:
            print(f"  CJF: {len(saida)} enunciados (página {id_})", flush=True)
    return saida


def montar_cjf(indice: dict, cache: Path) -> None:
    enunciados = coletar_cjf(cache)
    for chave, (arquivo, nome, padrao, areas) in CJF_GRUPOS.items():
        deste = sorted((e for e in enunciados if re.search(padrao, e["jornada"])), key=lambda e: (e["numero"], e["id"]))
        vistos, partes = set(), []
        for e in deste:
            # Cada jornada de tema proprio recomeca do 1: a chave e a jornada e o numero.
            if (e["jornada"], e["numero"]) in vistos:
                continue
            vistos.add((e["jornada"], e["numero"]))
            partes.append(f"Enunciado {e['numero']} da {e['jornada']} (CJF)\n{e['texto']}\n\n")
        if len(partes) < 50:
            raise SystemExit(f"{nome}: só {len(partes)} enunciados - a base do CJF mudou?")
        (DESTINO / arquivo).write_bytes(gzip.compress("".join(partes).encode("utf-8"), 9, mtime=0))
        indice["sumulas"][chave] = {"arquivo": arquivo, "nome": nome, "enunciados": len(partes), "fonte": CJF_FONTE,
                                    "autor": "Conselho da Justiça Federal", "areas": areas,
                                    "baixado_em": datetime.now().isoformat(timespec="seconds")}
        print(f"{nome}: {len(partes)} enunciados")
    outras = sorted({e["jornada"] for e in enunciados} - {e["jornada"] for e in enunciados
                                                          for _, _, p, _ in CJF_GRUPOS.values() if re.search(p, e["jornada"])})
    if outras:
        print("  jornadas que não entraram (outros assuntos):", "; ".join(outras))


def main() -> None:
    caminho = DESTINO / "indice.json"
    indice = json.loads(caminho.read_text(encoding="utf-8"))
    indice.setdefault("sumulas", {})
    if "--cjf" in sys.argv:
        montar_cjf(indice, Path(sys.argv[sys.argv.index("--cjf") + 1]))
    else:
        rtf = Path(sys.argv[sys.argv.index("--rtf") + 1]).read_bytes() if "--rtf" in sys.argv else None
        montar_tst(indice, rtf)
    caminho.write_text(json.dumps(indice, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
