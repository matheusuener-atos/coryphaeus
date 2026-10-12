"""
Os tribunais e as fontes de fora, para a tela Biblioteca.

- **DataJud (CNJ)**: a API pública do CNJ devolve os dados de um processo pelo
  número único (classe, órgão julgador, assuntos, movimentos). É a única
  consulta que sai desta máquina aqui, só quando a pessoa pede, e só o
  número do processo vai junto. A chave é a pública que o CNJ divulga na
  wiki do DataJud (não é segredo de ninguém). Se o CNJ trocar, a recusa
  (401/403) faz o PAULUS ler a chave vigente na própria wiki, guardar em
  <dados>/datajud.json e tentar de novo - sem esperar versão. A variável
  PAULUS_DATAJUD_CHAVE ainda manda em tudo, para quem precisar.
- **Indisponível**: o DataJud vive cheio (429) ou fora (5xx, tempo esgotado).
  Isso vira DataJudIndisponivel, e a volta diária tenta de novo no fim.
- **Perfil da vara**: contagens do órgão julgador (classes, assuntos,
  distribuições por ano) e o tempo até a sentença numa amostra da mesma
  classe. Só o código da vara e da classe saem daqui.
- **Jusbrasil, LexML, jurisprudência do STF, do STJ e do TST**: não têm API
  aberta para programa (o Jusbrasil proíbe raspar, o LexML e o STF barram
  robô). Aqui só se monta o endereço da busca, que abre no navegador.
"""

from __future__ import annotations

import base64
import binascii
import html
import json
import os
import re
import statistics
import unicodedata
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote_plus

DATAJUD = "https://api-publica.datajud.cnj.jus.br/api_publica_{alias}/_search"
CHAVE_PUBLICA = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="
# Onde o CNJ mostra a chave vigente ("APIKey atual: Authorization: APIKey ...").
WIKI_CHAVE = "https://datajud-wiki.cnj.jus.br/api-publica/acesso/"
RE_CHAVE = re.compile(r"APIKey\s*([A-Za-z0-9+/_-]{20,}={0,2})")
# Cheio (429) ou fora (5xx): vale tentar de novo depois.
INDISPONIVEL = (429, 500, 502, 503, 504)


class DataJudIndisponivel(ConnectionError):
    """O DataJud não atendeu agora (cheio, fora ou lento demais): tentar de novo mais tarde resolve."""

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
        "classe_codigo": _inteiro((fonte.get("classe") or {}).get("codigo")),
        "orgao": (fonte.get("orgaoJulgador") or {}).get("nome", ""),
        "orgao_codigo": _inteiro((fonte.get("orgaoJulgador") or {}).get("codigo")),
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


def _inteiro(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


# ------------------------------------------------------------ a chave

def _arquivo_chave() -> Path:
    return Path(os.environ.get("PAULUS_DADOS") or Path(__file__).resolve().parents[2] / "data") / "datajud.json"


def chave_atual() -> str:
    """A variável, senão a que a wiki do CNJ deu da última vez, senão a de fábrica."""
    if os.environ.get("PAULUS_DATAJUD_CHAVE"):
        return os.environ["PAULUS_DATAJUD_CHAVE"]
    try:
        guardada = json.loads(_arquivo_chave().read_text(encoding="utf-8")).get("chave")
    except (OSError, ValueError, AttributeError):
        guardada = ""
    return guardada or CHAVE_PUBLICA


def _parece_chave(c: str) -> bool:
    """A chave do DataJud é "id:segredo" em base64; o resto do texto da página não passa."""
    try:
        return b":" in base64.b64decode(c, validate=True)
    except (binascii.Error, ValueError):
        return False


def chave_do_cnj(*, ler=None) -> str:
    """A chave que a wiki do DataJud mostra agora ("" se a página não abriu ou mudou de jeito). `ler` troca o requests.get."""
    if ler is None:
        import requests

        def ler(url):
            return requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (PAULUS)"})
    try:
        resp = ler(WIKI_CHAVE)
        if resp.status_code != 200:
            return ""
        texto = html.unescape(re.sub(r"<[^>]+>", "", resp.text or ""))
    except Exception:  # noqa: BLE001 - sem a página, fica a chave de antes
        return ""
    return next((c for c in RE_CHAVE.findall(texto) if _parece_chave(c)), "")


def _guardar_chave(chave: str) -> None:
    try:
        arq = _arquivo_chave()
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(json.dumps({"chave": chave, "lida_em": datetime.now().isoformat(timespec="seconds"),
                                   "fonte": WIKI_CHAVE}), encoding="utf-8")
    except OSError:
        pass  # vale para esta consulta; na próxima, a recusa lê de novo


# ------------------------------------------------------------ o pedido

def _pedir_datajud(alias: str, corpo: dict, *, pedir=None, ler=None, timeout: float = 90) -> dict:
    """Um _search no índice do tribunal; a chave trocada pelo CNJ é lida na wiki e o pedido vai de novo, uma vez."""
    if pedir is None:
        import requests

        pedir = requests.post
    url = DATAJUD.format(alias=alias)

    def _uma(chave: str):
        try:
            return pedir(url, json=corpo, headers={"Authorization": "APIKey " + chave, "Content-Type": "application/json"},
                         timeout=timeout)
        except OSError as exc:  # sem rede, tempo esgotado (as do requests são OSError)
            raise DataJudIndisponivel(f"não consegui falar com o DataJud do CNJ ({exc.__class__.__name__}); "
                                      "tente de novo em alguns minutos") from exc

    chave = chave_atual()
    resp = _uma(chave)
    if resp.status_code in (401, 403) and not os.environ.get("PAULUS_DATAJUD_CHAVE"):
        nova = chave_do_cnj(ler=ler)
        if nova and nova != chave:
            _guardar_chave(nova)
            resp = _uma(nova)
    if resp.status_code in (401, 403):
        raise PermissionError("o DataJud recusou a chave pública, e a página do CNJ não mostrou outra; "
                              "avise o suporte do PAULUS")
    if resp.status_code in INDISPONIVEL:
        raise DataJudIndisponivel(f"o DataJud do CNJ está sobrecarregado agora (respondeu {resp.status_code}); "
                                  "tente de novo em alguns minutos")
    if resp.status_code >= 400:
        raise ConnectionError(f"o DataJud respondeu com erro ({resp.status_code}); tente de novo em alguns minutos")
    try:
        return resp.json() or {}
    except ValueError as exc:
        raise DataJudIndisponivel("o DataJud não devolveu os dados agora; tente de novo em alguns minutos") from exc


def consultar_datajud(numero: str, *, pedir=None, ler=None, movimentos: int = 12) -> dict:
    """
    Os dados públicos do processo no DataJud. Um processo pode vir em mais de
    um grau (G1, G2, JE): cada um é uma linha. `pedir` troca o requests.post
    e `ler` o requests.get da wiki (os testes).
    """
    lido = ler_numero(numero)
    if not lido["ok"]:
        raise ValueError(lido["erro"])
    # O DataJud é lento: 20 a 60 s numa consulta ao TJSP é comum.
    dados = _pedir_datajud(lido["alias"], {"size": 10, "query": {"match": {"numeroProcesso": lido["digitos"]}}},
                           pedir=pedir, ler=ler)
    hits = (dados.get("hits") or {}).get("hits") or []
    return {"numero": lido["numero"], "tribunal": lido["alias"].upper(),
            "graus": [resumir(h.get("_source") or {}, movimentos) for h in hits],
            "fonte": "DataJud, API pública do CNJ", "consultado_em": datetime.now().isoformat(timespec="seconds")}


# ------------------------------------------------------------ o perfil da vara

# A sentença pelos códigos da TPU (Procedência, Improcedência, Procedência em
# Parte, Homologação de Transação) ou pelo começo do nome. Só o começo: "de
# Instrução e Julgamento" é audiência, não sentença.
SENTENCA_CODIGOS = {219, 220, 221, 466}
RE_NOME_SENTENCA = re.compile(r"^(procedencia|improcedencia|homologacao de (transacao|acordo)|extincao|desistencia|"
                              r"abandono da causa|indeferimento da peticao inicial|prescricao|decadencia|"
                              r"julgad[oa] |com resolucao do merito|sem resolucao do merito)")
AMOSTRA = 100
# A amostra do tempo: distribuídos entre 6 e 2 anos atrás, que já tiveram tempo de chegar à sentença.
ANOS_AMOSTRA = (6, 2)


def _sem_acento(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode("ascii").lower().strip()


def e_sentenca(mov: dict) -> bool:
    return _inteiro(mov.get("codigo")) in SENTENCA_CODIGOS or bool(RE_NOME_SENTENCA.search(_sem_acento(mov.get("nome"))))


def _dia(bruto) -> date | None:
    s = str(bruto or "")
    try:
        if re.fullmatch(r"\d{8,14}", s):
            return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _baldes(dados: dict, nome: str) -> list[dict]:
    return [{"nome": b.get("key_as_string") or str(b.get("key", "")), "qtd": int(b.get("doc_count") or 0)}
            for b in (((dados.get("aggregations") or {}).get(nome) or {}).get("buckets") or [])]


def tempo_ate_sentenca(hits: list[dict]) -> dict:
    """Dos processos da amostra: quantos tiveram sentença e em quantos dias (mediana e o meio, do 1º ao 3º quartil)."""
    dias = []
    for h in hits:
        f = h.get("_source") or {}
        inicio = _dia(f.get("dataAjuizamento"))
        quando = [d for d in (_dia(m.get("dataHora")) for m in (f.get("movimentos") or []) if e_sentenca(m)) if d]
        if inicio and quando and min(quando) >= inicio:
            dias.append((min(quando) - inicio).days)
    saida = {"amostra": len(hits), "com_sentenca": len(dias)}
    if len(dias) >= 2:
        q1, mediana, q3 = statistics.quantiles(dias, n=4, method="inclusive")
        saida.update(mediana=round(mediana), q1=round(q1), q3=round(q3))
    elif dias:
        saida.update(mediana=dias[0], q1=dias[0], q3=dias[0])
    return saida


def perfil_do_orgao(alias: str, orgao_codigo: int, classe_codigo: int = 0, *, classe: str = "", pedir=None, ler=None,
                    hoje: date | None = None) -> dict:
    """
    O retrato da vara no DataJud: o total, por grau, as classes e os assuntos
    mais comuns, as distribuições dos últimos 5 anos e, com a classe, o tempo
    até a sentença numa amostra. Dois pedidos; no TJSP passa de um minuto.
    """
    if not orgao_codigo:
        raise ValueError("sem o código da vara: consulte o processo no DataJud primeiro")
    hoje = hoje or date.today()
    da_vara = {"term": {"orgaoJulgador.codigo": int(orgao_codigo)}}
    # Um filtro por ano: o histograma de datas do DataJud lê mal o "AAAAMMDDhhmmss".
    anos_ = [str(a) for a in range(hoje.year - 4, hoje.year + 1)]
    dados = _pedir_datajud(alias, {
        "size": 1, "track_total_hits": True, "_source": ["orgaoJulgador"], "query": da_vara,
        "aggs": {"graus": {"terms": {"field": "grau.keyword", "size": 6}},
                 "classes": {"terms": {"field": "classe.nome.keyword", "size": 6}},
                 "assuntos": {"terms": {"field": "assuntos.nome.keyword", "size": 6}},
                 "anos": {"filters": {"filters": {a: {"range": {"dataAjuizamento": {
                     "gte": f"{a}0101000000", "lt": f"{int(a) + 1}0101000000"}}} for a in anos_}}}}},
        pedir=pedir, ler=ler, timeout=120)
    hits = (dados.get("hits") or {}).get("hits") or []
    baldes_ano = (((dados.get("aggregations") or {}).get("anos") or {}).get("buckets") or {})
    anos = [{"nome": a, "qtd": int((baldes_ano.get(a) or {}).get("doc_count") or 0)} for a in anos_]
    perfil = {
        "tribunal": alias.upper(), "orgao_codigo": int(orgao_codigo),
        "orgao": ((hits[0].get("_source") or {}).get("orgaoJulgador") or {}).get("nome", "") if hits else "",
        "total": int(((dados.get("hits") or {}).get("total") or {}).get("value") or 0),
        "graus": _baldes(dados, "graus"), "classes": _baldes(dados, "classes"), "assuntos": _baldes(dados, "assuntos"),
        "por_ano": anos, "tempo": None,
        "fonte": "DataJud, API pública do CNJ", "consultado_em": datetime.now().isoformat(timespec="seconds"),
    }
    if classe_codigo:
        de, ate = hoje.year - ANOS_AMOSTRA[0], hoje.year - ANOS_AMOSTRA[1]
        amostra = _pedir_datajud(alias, {
            "size": AMOSTRA, "track_total_hits": True,
            "_source": ["dataAjuizamento", "movimentos.codigo", "movimentos.nome", "movimentos.dataHora"],
            "query": {"bool": {"filter": [da_vara, {"term": {"classe.codigo": int(classe_codigo)}},
                                          {"range": {"dataAjuizamento": {"gte": f"{de}0101000000", "lt": f"{ate}0101000000"}}}]}}},
            pedir=pedir, ler=ler, timeout=120)
        perfil["tempo"] = dict(tempo_ate_sentenca((amostra.get("hits") or {}).get("hits") or []),
                               classe=classe, de=de, ate=ate - 1,
                               populacao=int(((amostra.get("hits") or {}).get("total") or {}).get("value") or 0))
    return perfil


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
