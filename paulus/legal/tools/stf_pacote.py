"""
O pacote do STF que vai no instalador (docs/PLANO-PILOTO.md, N8).

O portal do STF recusa programa (403 para quem não é navegador), então este
script roda UMA vez, na máquina de quem monta o instalador, pelo Edge, sem
pressa (uma página a cada ~1,2 s), e grava em config/acervo-inicial/:

  - sumulas-stf.txt.gz: as súmulas do STF ("Súmula N do STF", o enunciado);
    as canceladas ficam de fora; as superadas entram, marcadas "(superada)";
  - sumulas-vinculantes.txt.gz: as súmulas vinculantes, do mesmo jeito;
  - temas-rg-stf.jsonl.gz: as teses de repercussão geral (com e sem
    repercussão), pelo banco de teses do portal - a primeira linha diz a fonte
    e a data;
  - indice.json: as duas listas de súmulas e o pacote de teses.

O PAULUS instalado nunca fala com o STF: o que ele tem é o que veio aqui, e
uma versão nova do instalador traz a lista nova. São textos oficiais (Lei
9.610/1998, art. 8º, IV).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/stf_pacote.py
"""

from __future__ import annotations

import gzip
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ACERVO = RAIZ / "config" / "acervo-inicial"
PORTAL = "https://portal.stf.jus.br/jurisprudencia/"
TESES = "https://portal.stf.jus.br/repercussaogeral/teses.asp"
PAUSA = 3.0
# O portal recusa depois de umas 150 páginas seguidas: com três falhas em
# sequência, o script descansa e abre o navegador de novo. O que já veio fica
# em <tools>/.stf-progresso.json, e uma rodada nova continua de onde parou.
DESCANSO = 300
PROGRESSO = Path(__file__).with_name(".stf-progresso.json")
RE_FIM_DO_ENUNCIADO = re.compile(r"\n\s*(Jurisprudência selecionada|Precedentes? Representativos?|Legislação|Observaç|Data de Aprovação|"
                                 r"Tese[s]? de repercussão|Referência|Aplicação e interpretação|Debates|Fonte de publicação|●)", re.IGNORECASE)


def _enunciado(texto: str, titulo: str) -> str:
    """
    O enunciado: as linhas logo abaixo do título da súmula ("Súmula 3",
    "Súmula Vinculante 13", às vezes com espaços no fim), até a primeira seção
    da página. O título é procurado como linha inteira - a mesma frase no meio
    da jurisprudência citada não conta.
    """
    base = titulo.split("(")[0].strip()
    texto = texto.replace("\xa0", " ")
    # [^\S\n]: qualquer espaço menos a quebra de linha - o portal põe espaço não separável no fim do título.
    m = re.search(r"^[^\S\n]*" + re.escape(base) + r"[^\S\n]*(?:\((?:superada|cancelada|revogada)\))?[^\S\n]*$", texto, re.MULTILINE | re.IGNORECASE)
    if not m:
        return ""
    resto = texto[m.end():]
    fim = RE_FIM_DO_ENUNCIADO.search(resto)
    corpo = resto[:fim.start()] if fim else resto[:2000]
    corpo = re.sub(r"\s*\((superada|cancelada|revogada)\)\s*$", "", " ".join(corpo.split()), flags=re.IGNORECASE)
    return corpo.strip()


def suspeito(texto: str) -> bool:
    """Texto que não tem cara de enunciado: longo, ou com as marcas da jurisprudência citada."""
    return len(texto) > 700 or bool(re.search(r"\[[A-Z][^\]]{3,80}\]|rel\. min\.|\bj\. \d", texto))


def _progresso() -> dict:
    try:
        return json.loads(PROGRESSO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _guardar_progresso(dados: dict) -> None:
    PROGRESSO.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")


# As súmulas cuja página no portal não traz o enunciado (só a jurisprudência): ficam de fora, contadas.
sem_enunciado: list[str] = []


def _sumulas(abrir, base: int, vinculante: bool) -> tuple[list[dict], int]:
    pag = abrir()
    pag.goto(f"{PORTAL}sumariosumulas.asp?base={base}", wait_until="load", timeout=90000)
    pag.wait_for_timeout(1500)
    links = pag.eval_on_selector_all(".sumula-item a", "els => els.map(e => [e.textContent.trim(), e.getAttribute('href')])")
    prog = _progresso()
    feitas = prog.setdefault(str(base), {})
    saida, fora, seguidas = [], 0, 0
    for n, (titulo, href) in enumerate(links, 1):
        if href in feitas and not (feitas[href] and suspeito(feitas[href]["texto"])):
            if feitas[href]:
                saida.append(feitas[href])
            else:
                fora += 1
            continue
        titulo = " ".join(titulo.replace("\u200b", "").split())
        m = re.search(r"(\d{1,4})", titulo)
        if not m:
            continue
        situacao = "cancelada" if re.search(r"cancela", titulo, re.I) else ("superada" if re.search(r"superad", titulo, re.I) else "")
        if situacao == "cancelada" or re.search(r"revogad", titulo, re.I):
            fora += 1
            feitas[href] = None
            continue
        texto = ""
        for tentativa in range(4):
            try:
                r = pag.goto(PORTAL + href, wait_until="load", timeout=60000)
                pag.wait_for_timeout(700)
                texto = pag.inner_text("body").replace("\u200b", "")
                if r is not None and r.status >= 400 or titulo.split("(")[0].strip() not in texto:
                    raise RuntimeError(f"recusado ({r.status if r else '?'})")
                seguidas = 0
                break
            except Exception as exc:  # noqa: BLE001 - o portal oscila ou recusa: descansa
                texto = ""
                seguidas += 1
                espera = DESCANSO if seguidas >= 3 else 20 * (tentativa + 1)
                print(f"  {titulo}: {str(exc)[:60]} - espero {espera} s")
                time.sleep(espera)
                if seguidas >= 3:
                    pag = abrir()
                    seguidas = 0
        if not texto:
            print(f"  não consegui: {titulo}")
            continue
        enunciado = _enunciado(texto, titulo)
        if len(enunciado) < 15:
            print(f"  sem enunciado: {titulo}")
            sem_enunciado.append(titulo)
            # O que estava guardado (errado) sai: na próxima rodada, tenta de novo.
            feitas.pop(href, None)
            continue
        item = {"numero": m.group(1), "situacao": situacao, "texto": enunciado, "fonte": PORTAL + href}
        saida.append(item)
        feitas[href] = item
        _guardar_progresso(prog)
        if n % 50 == 0:
            print(f"  {n}/{len(links)}")
        time.sleep(PAUSA)
    _guardar_progresso(prog)
    return saida, fora


def _teses(pag) -> list[dict]:
    capturadas = {}

    def ouvir(r):
        if "retornartesesrepercussaogeral" in r.url:
            try:
                capturadas[r.request.post_data or ""] = r.json()
            except Exception:  # noqa: BLE001
                pass

    pag.on("response", ouvir)
    pag.goto(TESES, wait_until="load", timeout=90000)
    pag.wait_for_timeout(2000)
    for tipo in ("com", "sem"):
        pag.click(f"button[data-tipo='{tipo}']")
        pag.wait_for_timeout(8000)
        time.sleep(PAUSA)
    saida = {}
    for pedido, lista in capturadas.items():
        com = "com" in pedido
        for t in lista or []:
            numero = str(int(re.sub(r"\D", "", str(t.get("numeroTema") or "0")) or 0))
            tese = " ".join(str(t.get("descricaoTese") or "").split())
            if numero == "0" or len(tese) < 15:
                continue
            saida[numero] = {"numero": numero, "tese": tese, "com_repercussao": com,
                             "paradigma": f"{t.get('siglaClasse') or ''} {t.get('numeroProcesso') or ''}".strip(),
                             "data": str(t.get("dataAndamento") or ""), "incidente": str(t.get("incidente") or "")}
    return sorted(saida.values(), key=lambda x: int(x["numero"]))


def _gravar_sumulas(lista: list[dict], arquivo: str, vinculante: bool) -> None:
    rotulo = "Súmula Vinculante" if vinculante else "Súmula"
    linhas = []
    for s in sorted(lista, key=lambda x: int(x["numero"])):
        linhas.append(f"{rotulo} {s['numero']} do STF" + (" (superada)" if s["situacao"] == "superada" else ""))
        linhas.append(s["texto"])
        linhas.append("")
    (ACERVO / arquivo).write_bytes(gzip.compress("\n".join(linhas).encode("utf-8")))


def main() -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        atual = {"nav": None}

        def abrir():
            """Um navegador novo (o portal pode ter fechado a porta para o anterior)."""
            if atual["nav"] is not None:
                try:
                    atual["nav"].close()
                except Exception:  # noqa: BLE001
                    pass
            atual["nav"] = p.chromium.launch(channel="msedge", headless=True)
            return atual["nav"].new_page()

        prog = _progresso()
        if prog.get("teses"):
            teses = prog["teses"]
        else:
            print("teses de repercussão geral")
            teses = _teses(abrir())
            prog["teses"] = teses
            _guardar_progresso(prog)
        print(f"  {len(teses)} teses")
        print("súmulas vinculantes")
        vinc, vinc_fora = _sumulas(abrir, 26, True)
        print(f"  {len(vinc)} (fora: {vinc_fora})")
        print("súmulas do STF")
        sums, sums_fora = _sumulas(abrir, 30, False)
        print(f"  {len(sums)} (fora: {sums_fora})")
        atual["nav"].close()
    if len(sums) < 600 or len(vinc) < 50 or len(teses) < 900:
        print("pouco demais: nada gravado (o portal pode ter mudado)")
        return 1
    agora = datetime.now().isoformat(timespec="seconds")
    _gravar_sumulas(sums, "sumulas-stf.txt.gz", False)
    _gravar_sumulas(vinc, "sumulas-vinculantes.txt.gz", True)
    meta = {"fonte": TESES, "baixado_em": agora, "teses": len(teses),
            "licenca": "texto oficial (Lei 9.610/1998, art. 8º, IV)"}
    corpo = "\n".join(json.dumps(x, ensure_ascii=False) for x in [meta] + teses)
    (ACERVO / "temas-rg-stf.jsonl.gz").write_bytes(gzip.compress(corpo.encode("utf-8")))
    idx_arq = ACERVO / "indice.json"
    idx = json.loads(idx_arq.read_text(encoding="utf-8"))
    idx.setdefault("sumulas", {})["stf"] = {"arquivo": "sumulas-stf.txt.gz", "nome": "Súmulas do STF", "enunciados": len(sums),
                                           "canceladas_fora": sums_fora, "superadas": sum(1 for s in sums if s["situacao"] == "superada"),
                                           "fonte": PORTAL + "sumariosumulas.asp?base=30", "baixado_em": agora}
    idx["sumulas"]["stf"]["sem_enunciado_no_portal"] = list(sem_enunciado)
    idx["sumulas"]["stf_vinculantes"] = {"arquivo": "sumulas-vinculantes.txt.gz", "nome": "Súmulas vinculantes do STF",
                                         "enunciados": len(vinc), "canceladas_fora": vinc_fora,
                                         "fonte": PORTAL + "sumariosumulas.asp?base=26", "baixado_em": agora}
    idx["temas_stf"] = {"arquivo": "temas-rg-stf.jsonl.gz", "teses": len(teses), "fonte": TESES, "baixado_em": agora}
    idx_arq.write_text(json.dumps(idx, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("gravado em", ACERVO)
    return 0


if __name__ == "__main__":
    sys.exit(main())
