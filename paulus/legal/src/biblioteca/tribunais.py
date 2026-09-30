"""
Os tribunais e as fontes de fora, para a tela Biblioteca.

- **DataJud (CNJ)**: a API pública do CNJ devolve os dados de um processo pelo
  número único (classe, órgão julgador, assuntos, movimentos). É a única
  consulta que sai desta máquina aqui, só quando a pessoa pede, e só o
  número do processo vai junto. A chave é a pública que o CNJ divulga na
  wiki do DataJud (não é segredo de ninguém); se o CNJ trocar, a variável
  PAULUS_DATAJUD_CHAVE põe a nova sem esperar versão.
- **Jusbrasil, LexML, jurisprudência do STF, do STJ e do TST**: não têm API
  aberta para programa (o Jusbrasil proíbe raspar, o LexML e o STF barram
  robô). Aqui só se monta o endereço da busca, que abre no navegador.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from urllib.parse import quote_plus

DATAJUD = "https://api-publica.datajud.cnj.jus.br/api_publica_{alias}/_search"
CHAVE_PUBLICA = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="

# A ordem das UFs no número único (Resolução CNJ 65/2008), de 01 a 27.
UFS = ("ac", "al", "ap", "am", "ba", "ce", "df", "es", "go", "ma", "mt", "ms", "mg", "pa", "pb", "pr", "pe", "pi",
       "rj", "rn", "rs", "ro", "rr", "sc", "se", "sp", "to")
MILITAR_ESTADUAL = {"13": "tjmmg", "21": "tjmrs", "26": "tjmsp"}

RE_NUMERO = re.compile(r"\b(\d{7})-?(\d{2})\.?(\d{4})\.?(\d)\.?(\d{2})\.?(\d{4})\b")


def digitos(numero: str) -> str:
    return re.sub(r"\D", "", numero or "")


def formatar(n20: str) -> str:
    return f"{n20[:7]}-{n20[7:9]}.{n20[9:13]}.{n20[13]}.{n20[14:16]}.{n20[16:]}"


def digito_confere(n20: str) -> bool:
    """O dígito verificador do número único (módulo 97, ISO 7064)."""
    if len(n20) != 20:
        return False
    base = n20[:7] + n20[9:] + "00"
    return 98 - int(base) % 97 == int(n20[7:9])


def alias_do_tribunal(n20: str) -> str:
    """O índice do DataJud pelo segmento (J) e o tribunal (TR); vazio se não há índice público."""
    j, tr = n20[13], n20[14:16]
    if j == "8":
        return "tjdft" if tr == "07" else ("tj" + UFS[int(tr) - 1] if 1 <= int(tr) <= 27 else "")
    if j == "4":
        return f"trf{int(tr)}" if 1 <= int(tr) <= 6 else ""
    if j == "5":
        return "tst" if tr == "00" else (f"trt{int(tr)}" if 1 <= int(tr) <= 24 else "")
    if j == "6":
        return "tse" if tr == "00" else ("tre-" + UFS[int(tr) - 1] if 1 <= int(tr) <= 27 else "")
    if j == "9":
        return MILITAR_ESTADUAL.get(tr, "")
    if j == "7":
        return "stm"
    if j == "3":
        return "stj"
    return ""


def ler_numero(texto: str) -> dict:
    """{'ok', 'numero' (formatado), 'digitos', 'alias', 'erro'}."""
    d = digitos(texto)
    if len(d) != 20:
        m = RE_NUMERO.search(texto or "")
        d = "".join(m.groups()) if m else d
    if len(d) != 20:
        return {"ok": False, "erro": "o número único do processo tem 20 dígitos (NNNNNNN-DD.AAAA.J.TR.OOOO)"}
    if not digito_confere(d):
        return {"ok": False, "erro": f"o dígito verificador de {formatar(d)} não confere: confira o número"}
    alias = alias_do_tribunal(d)
    if not alias:
        return {"ok": False, "erro": "esse tribunal não tem consulta pública no DataJud (o STF, por exemplo, não está lá)"}
    return {"ok": True, "numero": formatar(d), "digitos": d, "alias": alias}


def _data(bruto: str) -> str:
    """'20260730012658' ou '2026-09-15T10:38:57.000Z' -> '2026-09-15 10:38'."""
    s = str(bruto or "")
    if re.fullmatch(r"\d{14}", s):
        return f"{s[:4]}-{s[4:6]}-{s[6:8]} {s[8:10]}:{s[10:12]}"
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return s[:16]


def resumir(fonte: dict, movimentos: int = 12) -> dict:
    movs = sorted(fonte.get("movimentos") or [], key=lambda m: str(m.get("dataHora") or ""), reverse=True)
    return {
        "tribunal": fonte.get("tribunal", ""), "grau": fonte.get("grau", ""),
        "classe": (fonte.get("classe") or {}).get("nome", ""),
        "orgao": (fonte.get("orgaoJulgador") or {}).get("nome", ""),
        "ajuizamento": _data(fonte.get("dataAjuizamento", "")),
        "sistema": (fonte.get("sistema") or {}).get("nome", ""),
        "sigilo": int(fonte.get("nivelSigilo") or 0),
        "assuntos": [a.get("nome", "") for a in (fonte.get("assuntos") or []) if isinstance(a, dict) and a.get("nome")],
        "atualizado": _data(fonte.get("dataHoraUltimaAtualizacao", "")),
        "movimentos": [{"quando": _data(m.get("dataHora", "")), "nome": m.get("nome", ""),
                        "complemento": "; ".join(str(c.get("nome") or c.get("descricao") or "")
                                                 for c in (m.get("complementosTabelados") or []) if isinstance(c, dict))}
                       for m in movs[:movimentos]],
        "total_movimentos": len(movs),
    }


def consultar_datajud(numero: str, *, pedir=None, movimentos: int = 12) -> dict:
    """
    Os dados públicos do processo no DataJud. Um processo pode vir em mais de
    um grau (G1, G2, JE): cada um é uma linha. `pedir` troca o requests.post
    (os testes).
    """
    lido = ler_numero(numero)
    if not lido["ok"]:
        raise ValueError(lido["erro"])
    if pedir is None:
        import requests

        pedir = requests.post
    chave = os.environ.get("PAULUS_DATAJUD_CHAVE") or CHAVE_PUBLICA
    # O DataJud é lento: 20 a 60 s numa consulta ao TJSP é comum.
    resp = pedir(DATAJUD.format(alias=lido["alias"]),
                 json={"size": 10, "query": {"match": {"numeroProcesso": lido["digitos"]}}},
                 headers={"Authorization": "APIKey " + chave, "Content-Type": "application/json"}, timeout=90)
    if resp.status_code in (401, 403):
        raise PermissionError("o DataJud recusou a chave pública: o CNJ pode tê-la trocado")
    if resp.status_code >= 400:
        raise ConnectionError(f"o DataJud respondeu com erro ({resp.status_code}); tente de novo em alguns minutos")
    try:
        hits = ((resp.json() or {}).get("hits") or {}).get("hits") or []
    except ValueError as exc:
        raise ConnectionError("o DataJud não devolveu os dados agora; tente de novo em alguns minutos") from exc
    return {"numero": lido["numero"], "tribunal": lido["alias"].upper(),
            "graus": [resumir(h.get("_source") or {}, movimentos) for h in hits],
            "fonte": "DataJud, API pública do CNJ", "consultado_em": datetime.now().isoformat(timespec="seconds")}


FONTES = (
    {"id": "jusbrasil", "nome": "Jusbrasil", "o_que": "jurisprudência, notícias e diários",
     "url": "https://www.jusbrasil.com.br/busca?q={q}"},
    {"id": "stf", "nome": "STF — jurisprudência", "o_que": "acórdãos, súmulas e repercussão geral",
     "url": "https://jurisprudencia.stf.jus.br/pages/search?base=acordaos&queryString={q}"},
    {"id": "stj", "nome": "STJ — jurisprudência", "o_que": "acórdãos, súmulas e repetitivos",
     "url": "https://scon.stj.jus.br/SCON/pesquisar.jsp?livre={q}"},
    {"id": "tst", "nome": "TST — jurisprudência", "o_que": "acórdãos e súmulas do trabalho",
     "url": "https://jurisprudencia.tst.jus.br/?q={q}"},
    {"id": "lexml", "nome": "LexML", "o_que": "leis, decretos e projetos de todo o país",
     "url": "https://www.lexml.gov.br/busca/search?keyword={q}"},
)


def links(termo: str) -> list[dict]:
    q = quote_plus((termo or "").strip())
    return [{**{k: v for k, v in f.items() if k != "url"}, "url": f["url"].format(q=q)} for f in FONTES] if q else []
