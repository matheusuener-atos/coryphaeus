"""
Mede a conversa sobre documentos num conjunto de perguntas com resposta
conhecida (I2): acerto, latência p50/p95, tokens de entrada e, para a busca,
Recall@20, Recall@6 e MRR@6.

Dois conjuntos:

- o da demonstração (`tools/demo/conjunto-demo.jsonl`), sobre os documentos
  fictícios de tools/demo/criar_demo.py - está no git, é o exemplo do formato;
- o real (`data/medicao/conjunto-real.jsonl`), sobre documentos do
  escritório - FORA do git: são documentos de cliente. Como anotar está em
  docs/medicao.md.

Cada linha do conjunto é uma pergunta no formato do `P(...)` do roteiro
(`alguma`, `todas`, `nunca`, `minimo`, `tipo`), mais:

- `trechos_esperados`: frases literais curtas do documento que TÊM de estar
  no contexto para a pergunta ter resposta. Frases, e não id de trecho: os ids
  mudam até a I5;
- `documentos` (opcional): a pergunta é só sobre estes arquivos;
- `continua` (opcional): a pergunta depende da anterior e vai na mesma
  conversa ("e a multa?").

Recall@k: das frases esperadas, quantas estão nos k primeiros trechos da
busca (média por pergunta). MRR@6: 1/posição do primeiro trecho, entre os 6
primeiros, que traz alguma frase esperada. "No contexto": das frases
esperadas, quantas estavam no que foi de fato mandado ao modelo.

    venv\\Scripts\\python.exe tools\\medir.py                   (demonstração)
    venv\\Scripts\\python.exe tools\\medir.py --real            (conjunto real)
    venv\\Scripts\\python.exe tools\\medir.py --so-busca        (sem o modelo)

Grava o resultado em <dados>/medicao/medir-<conjunto>-<data e hora>.json. Nada
sai da máquina.
"""

from __future__ import annotations

import json
import os
import sys
import time
import unicodedata
import urllib.request
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DEMO = RAIZ / "data" / "demo"
CONJUNTO_DEMO = RAIZ / "tools" / "demo" / "conjunto-demo.jsonl"

TIPOS = ("fato", "lista", "ausencia", "consequencia", "comparacao", "continuacao")


def _plano(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn").lower()


def _compacto(t: str) -> str:
    """Sem acento, minúsculo e com os espaços juntos: a quebra de linha do
    extrator não pode fazer uma frase esperada "sumir" do trecho."""
    return " ".join(_plano(t).split())


def conferir(p: dict, alvo: str) -> tuple[bool, str]:
    """A mesma conferência do roteiro (tools/demo/roteiro.py)."""
    a = _plano(alvo)
    tem = lambda x: _plano(x) in a  # noqa: E731
    if p.get("alguma") and not any(tem(x) for x in p["alguma"]):
        return False, "faltou: " + " | ".join(p["alguma"][:4])
    for alts in p.get("todas") or []:
        if not any(tem(x) for x in alts):
            return False, "faltou: " + " | ".join(alts)
    if p.get("minimo"):
        n, itens = p["minimo"]
        achados = sum(1 for alts in itens if any(tem(x) for x in alts))
        if achados < n:
            return False, f"só {achados} de {n} valores"
    ruins = [x for x in p.get("nunca") or [] if tem(x)]
    if ruins:
        return False, "inventou: " + ", ".join(ruins)
    return True, ""


def ler_conjunto(caminho: Path) -> list[dict]:
    perguntas = []
    for n, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), start=1):
        linha = linha.strip()
        if not linha or linha.startswith("//"):
            continue
        try:
            p = json.loads(linha)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{caminho.name}, linha {n}: não é JSON ({exc})") from exc
        if not p.get("pergunta"):
            raise SystemExit(f"{caminho.name}, linha {n}: falta a pergunta")
        p.setdefault("caminho", "documentos")
        p.setdefault("trechos_esperados", [])
        perguntas.append(p)
    return perguntas


# ------------------------------------------------------------ as métricas

def percentil(valores: list[float], p: float) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    posicao = min(len(ordenados) - 1, max(0, round(p / 100 * (len(ordenados) - 1))))
    return ordenados[posicao]


def recall_em(textos: list[str], esperados: list[str], k: int) -> float:
    """Das frases esperadas, a fração que aparece nos k primeiros textos."""
    if not esperados:
        return 1.0
    juntos = [_compacto(t) for t in textos[:k]]
    achadas = sum(1 for frase in esperados if any(_compacto(frase) in t for t in juntos))
    return achadas / len(esperados)


def rr_em(textos: list[str], esperados: list[str], k: int) -> float:
    """1/posição do primeiro texto, entre os k primeiros, com alguma frase esperada."""
    if not esperados:
        return 1.0
    frases = [_compacto(f) for f in esperados]
    for posicao, texto in enumerate(textos[:k], start=1):
        t = _compacto(texto)
        if any(f in t for f in frases):
            return 1.0 / posicao
    return 0.0


def medir_busca(searcher, p: dict, consulta: str = "", denso=None, vetorizador=None) -> dict:
    """
    A busca sozinha: o ranking que ela daria para a pergunta, sem o modelo.

    `consulta` e a pergunta como a conversa a manda para a busca (a
    continuacao ja reescrita, I4). Com o indice denso (I7), mede cada lista
    sozinha - lexica e densa - e a hibrida: Recall@20 na fusao RRF, e
    Recall@6/MRR@6/tokens no que o orcamento deixa ir para o modelo.
    """
    if not p.get("trechos_esperados"):
        return {}
    consulta = consulta or p["pergunta"]
    esperados = p["trechos_esperados"]
    docs = p.get("documentos") or None
    hits = searcher.search(consulta, top_k=20, per_doc_limit=20, documentos=docs)
    textos = [h.chunk.text for h in hits]
    saida = {"recall20": recall_em(textos, esperados, 20), "recall6": recall_em(textos, esperados, 6),
             "rr6": rr_em(textos, esperados, 6)}
    if denso is None or vetorizador is None or not any(c.chunk_id for c in searcher.chunks):
        return saida
    import recuperacao

    por_id = {c.chunk_id: c.text for c in searcher.chunks}
    lexico, densa = recuperacao.listas(searcher, consulta, denso=denso, vetorizador=vetorizador, documentos=docs)
    fundidos = [cid for cid, _ in recuperacao.rrf([lexico, densa])][:recuperacao.FUNDIDOS_TOP]
    finais = recuperacao.recuperar(searcher, consulta, denso=denso, vetorizador=vetorizador, documentos=docs)
    texto_de = lambda ids: [por_id[c] for c in ids if c in por_id]  # noqa: E731
    saida.update(
        lexico20=recall_em(texto_de(lexico), esperados, 20),
        denso20=recall_em(texto_de(densa), esperados, 20),
        recall20=recall_em(texto_de(fundidos), esperados, 20),
        recall6=recall_em([h.chunk.text for h in finais], esperados, 6),
        rr6=rr_em([h.chunk.text for h in finais], esperados, 6),
        tokens_contexto=sum(len(h.chunk.text) for h in finais) // 3,
    )
    return saida


# -------------------------------------------------------------- a conversa

def _local() -> dict:
    import api

    return api.cabecalho_local()


def _eventos(texto: str) -> list[tuple[str, dict]]:
    eventos = []
    for bloco in texto.split("\n\n"):
        tipo, corpo = "", ""
        for linha in bloco.splitlines():
            if linha.startswith("event: "):
                tipo = linha[7:]
            elif linha.startswith("data: "):
                corpo += linha[6:]
        if tipo:
            eventos.append((tipo, json.loads(corpo or "{}")))
    return eventos


def pedir(base: str, metodo: str, caminho: str, dados: dict | None = None, limite: int = 60) -> str:
    req = urllib.request.Request(base + caminho, method=metodo,
                                 data=json.dumps(dados).encode() if dados is not None else None,
                                 headers={**_local(), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=limite) as r:
        return r.read().decode("utf-8")


def perguntar(base: str, trabalho: str, p: dict) -> dict:
    corpo: dict = {"pergunta": p["pergunta"]}
    if p.get("documentos"):
        corpo.update(apenas=p["documentos"], documentos=True)
    comeco = time.time()
    try:
        eventos = _eventos(pedir(base, "POST", f"/api/trabalhos/{trabalho}/perguntar", corpo, limite=600))
    except Exception as exc:  # noqa: BLE001 - a medição segue
        eventos = [("erro", {"mensagem": str(exc)})]
    segundos = time.time() - comeco
    texto = "".join(d.get("t", "") for t, d in eventos if t == "token") + \
        "".join(d.get("mensagem", "") for t, d in eventos if t == "vazio")
    proposta = next((d for t, d in eventos if t == "proposta"), {})
    veio = ("programa" if proposta.get("tipo") == "programa"
            else "pergunta" if proposta.get("tipo") == "escopo" else "documentos")
    certo, motivo = conferir(p, texto + " " + json.dumps(proposta, ensure_ascii=False))
    erro = next((d.get("mensagem") for t, d in eventos if t == "erro"), "")
    medida = next((d for t, d in eventos if t == "medida"), {})
    fontes = next((d.get("trechos") or [] for t, d in eventos if t == "fontes"), [])
    no_contexto = recall_em([" ".join(f.get("texto", "") for f in fontes)], p.get("trechos_esperados") or [], 1)
    if veio != p["caminho"]:
        motivo = f"foi para {veio}" + (f"; {motivo}" if motivo else "")
    return {"certo": bool(certo and veio == p["caminho"] and not erro), "motivo": motivo or erro,
            "segundos": round(segundos, 1), "tokens_lidos": medida.get("tokens_lidos"),
            "truncou": any(t == "truncou" for t, _ in eventos), "no_contexto": no_contexto,
            "veio": veio, "resposta": texto[:600]}


# ----------------------------------------------------------------- o todo

def main() -> int:
    real = "--real" in sys.argv
    so_busca = "--so-busca" in sys.argv
    if real:
        dados = Path(os.environ.get("PAULUS_DADOS") or (RAIZ / "data"))
        conjunto = dados / "medicao" / "conjunto-real.jsonl"
        if not conjunto.exists():
            print(f"Não achei {conjunto}. Como montar: docs/medicao.md.")
            return 2
    else:
        dados = DEMO
        conjunto = CONJUNTO_DEMO
        os.environ["PAULUS_DADOS"] = str(DEMO)
        if not (DEMO / "criada-em.txt").exists():
            import subprocess

            subprocess.run([sys.executable, str(RAIZ / "tools" / "demo" / "criar_demo.py"), "--refazer"], check=True)
    os.environ["PAULUS_DADOS"] = str(dados)
    sys.path.insert(0, str(RAIZ / "src"))
    sys.path.insert(0, str(RAIZ / "tests"))

    perguntas = ler_conjunto(conjunto)
    print(f"Conjunto: {conjunto.name} · {len(perguntas)} perguntas")

    import api

    if so_busca:
        api.estado.recarregar()
    else:
        from test_gravacoes import _porta_livre, _subir_servidor

        porta = _porta_livre()
        _subir_servidor(porta)
        base = f"http://127.0.0.1:{porta}"
    for _ in range(90):
        if api.estado.searcher.documents:
            break
        time.sleep(1)
    print(f"Acervo: {len(api.estado.searcher.documents)} documentos · "
          f"{len(api.estado.searcher.chunks)} trechos · modelo {api.estado.client.model}")

    # A busca por sentido (I7), quando o modelo de vetores esta instalado: os
    # vetores que faltam sao feitos agora, antes de medir.
    denso, vetorizador = api.estado.busca_por_sentido(esperar=True)
    if denso is not None:
        print(f"Vetores: {denso.quantos()} de {len(api.estado.searcher.chunks)} trechos ({denso.espaco})")
    print()

    import memoria

    resultados: list[dict] = []
    criados: list[str] = []
    trabalho = ""
    assunto = None
    anterior = ""
    try:
        for p in perguntas:
            # A busca recebe o que a conversa mandaria: a continuacao ja
            # reescrita com o sujeito da anterior (I4).
            consulta = memoria.reescrever(p["pergunta"], anterior, assunto) if p.get("continua") else p["pergunta"]
            if consulta == p["pergunta"]:
                assunto = memoria.assunto_de(p["pergunta"]) or assunto
            anterior = consulta
            r: dict = {"pergunta": p["pergunta"], "tipo": p.get("tipo", ""), "caminho": p["caminho"],
                       **medir_busca(api.estado.searcher, p, consulta, denso, vetorizador)}
            if not so_busca:
                if not (p.get("continua") and trabalho):
                    trabalho = json.loads(pedir(base, "POST", "/api/trabalhos", {"pedido": p["pergunta"]}))["id"]
                    criados.append(trabalho)
                r.update(perguntar(base, trabalho, p))
                marca = "ok " if r["certo"] else "ERR"
                print(f"{marca} {r['segundos']:6.1f}s  {'↳ ' if p.get('continua') else ''}{p['pergunta']}")
                if not r["certo"]:
                    print(f"         {r['motivo']} · {r['resposta'][:200]!r}")
            else:
                print(f"R@6 {r.get('recall6', 1):.2f}  {p['pergunta']}")
            resultados.append(r)
    finally:
        for id_ in criados:
            try:
                pedir(base, "DELETE", f"/api/trabalhos/{id_}")
            except Exception:  # noqa: BLE001
                pass

    print()
    resumo: dict = {"conjunto": conjunto.name, "quando": datetime.now().isoformat(timespec="seconds"),
                    "modelo": api.estado.client.model, "perguntas": len(resultados)}
    com_busca = [r for r in resultados if "recall6" in r]
    if com_busca:
        resumo.update(
            recall20=round(sum(r["recall20"] for r in com_busca) / len(com_busca), 3),
            recall6=round(sum(r["recall6"] for r in com_busca) / len(com_busca), 3),
            mrr6=round(sum(r["rr6"] for r in com_busca) / len(com_busca), 3))
        print(f"busca     : Recall@20 {resumo['recall20']:.2f} · Recall@6 {resumo['recall6']:.2f} · "
              f"MRR@6 {resumo['mrr6']:.2f}  ({len(com_busca)} perguntas com trechos esperados)")
        if all("denso20" in r for r in com_busca):
            resumo.update(
                lexico20=round(sum(r["lexico20"] for r in com_busca) / len(com_busca), 3),
                denso20=round(sum(r["denso20"] for r in com_busca) / len(com_busca), 3),
                tokens_contexto_p50=percentil([r["tokens_contexto"] for r in com_busca], 50))
            print(f"            só léxico R@20 {resumo['lexico20']:.2f} · só denso R@20 {resumo['denso20']:.2f} · "
                  f"híbrido R@20 {resumo['recall20']:.2f} · contexto p50 {resumo['tokens_contexto_p50']:.0f} tokens")
    if not so_busca:
        certos = sum(1 for r in resultados if r["certo"])
        tempos = [r["segundos"] for r in resultados]
        tokens = [r["tokens_lidos"] for r in resultados if r.get("tokens_lidos")]
        contexto = [r["no_contexto"] for r in resultados if r["caminho"] == "documentos"]
        resumo.update(certas=certos, p50_s=percentil(tempos, 50), p95_s=percentil(tempos, 95),
                      tokens_p50=percentil(tokens, 50), tokens_p95=percentil(tokens, 95),
                      no_contexto=round(sum(contexto) / len(contexto), 3) if contexto else None,
                      truncou=sum(1 for r in resultados if r.get("truncou")))
        print(f"acerto    : {certos}/{len(resultados)}")
        print(f"latência  : p50 {resumo['p50_s']:.1f} s · p95 {resumo['p95_s']:.1f} s")
        if tokens:
            print(f"entrada   : p50 {resumo['tokens_p50']:.0f} tokens · p95 {resumo['tokens_p95']:.0f} tokens")
        if contexto:
            print(f"contexto  : {resumo['no_contexto']:.2f} das frases esperadas estavam no que o modelo leu")
        if resumo["truncou"]:
            print(f"cortes    : {resumo['truncou']} perguntas não couberam na janela")
        por_tipo = {}
        for r in resultados:
            t = "continuacao" if any(p.get("continua") and p["pergunta"] == r["pergunta"] for p in perguntas) \
                else r["tipo"]
            por_tipo.setdefault(t or "-", []).append(r["certo"])
        resumo["por_tipo"] = {t: f"{sum(v)}/{len(v)}" for t, v in sorted(por_tipo.items())}
        print("por tipo  : " + " · ".join(f"{t} {v}" for t, v in resumo["por_tipo"].items()))

    saida = dados / "medicao" / f"medir-{'real' if real else 'demo'}-{datetime.now():%Y%m%d-%H%M}.json"
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps({"resumo": resumo, "perguntas": resultados}, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print(f"\nresultado em {saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
