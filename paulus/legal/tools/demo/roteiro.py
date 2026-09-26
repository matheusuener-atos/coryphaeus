"""
O roteiro da demonstração, medido: as perguntas que um advogado faria sobre
o escritório fictício de criar_demo.py, cada uma com a resposta certa.

Como os documentos da demonstração foram escritos aqui, a resposta certa é
conhecida - e dá para medir, com o modelo de verdade, quantas a conversa
acerta e quanto tempo leva. Serve para duas coisas: ensaiar a demonstração
e saber, antes de mostrar, o que o PAULUS erra.

    venv\\Scripts\\python.exe tools\\demo\\roteiro.py            (tudo)
    venv\\Scripts\\python.exe tools\\demo\\roteiro.py --programa (só as sem modelo)

Precisa do Ollama ligado para as perguntas sobre documentos. Grava o
resultado em data/demo/roteiro-resultado.json.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DEMO = RAIZ / "data" / "demo"
os.environ["PAULUS_DADOS"] = str(DEMO)
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

# (pergunta, caminho esperado, respostas aceitas - basta uma)
# caminho: "programa" = responde do banco ou do mapa, sem modelo;
#          "documentos" = lê os documentos com o modelo local.
ROTEIRO = [
    ("quais compromissos tenho amanhã?", "programa", ["Reunião com a Cooperativa"]),
    ("tenho alguma tarefa atrasada?", "programa", ["Enviar a minuta do aditivo"]),
    ("quanto recebi este mês?", "programa", ["7.500"]),
    ("quanto recebi da Cooperativa este mês?", "programa", ["7.500"]),
    ("como assino um PDF?", "programa", ["Assinatura"]),
    ("abra o financeiro", "programa", ["Financeiro"]),
    ("qual o valor mensal do contrato de transporte da Cooperativa?", "documentos", ["18.500", "19.980"]),
    ("qual o novo valor mensal definido no aditivo?", "documentos", ["19.980"]),
    ("qual o prazo de aviso para não renovar o contrato de transporte?", "documentos", ["60", "sessenta"]),
    ("qual a multa por atraso no pagamento do contrato de transporte?", "documentos", ["2%", "dois por cento"]),
    ("qual o foro do contrato de transporte?", "documentos", ["Santarém"]),
    ("em que dia vence o aluguel da Clínica Bem Viver?", "documentos", ["dia 5", "dia 05", "5 (cinco)", "dia cinco"]),
    ("qual índice reajusta o aluguel da Clínica?", "documentos", ["IGP-M", "IGPM"]),
    ("a procuração da Cooperativa dá poderes para renunciar a créditos?", "documentos", ["não"]),
    ("qual o prazo dado à Rio Fresco na notificação?", "documentos", ["10 dias", "dez dias", "10 (dez)"]),
    ("quanto são os honorários fixos do João Batista?", "documentos", ["4.500"]),
]


def _plano(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn").lower()


def conversar(base: str, caminho: str, dados: dict, limite: int = 360) -> list[tuple[str, dict]]:
    req = urllib.request.Request(base + caminho, data=json.dumps(dados).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=limite) as r:
        texto = r.read().decode("utf-8")
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


def pedir(base: str, metodo: str, caminho: str, dados: dict | None = None) -> dict:
    req = urllib.request.Request(base + caminho, method=metodo,
                                 data=json.dumps(dados).encode() if dados is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


def main() -> int:
    if not (DEMO / "paulus.db").exists():
        print("sem base de demonstração: rode tools/demo/criar_demo.py")
        return 1
    so_programa = "--programa" in sys.argv

    from test_gravacoes import _porta_livre, _subir_servidor

    import api

    porta = _porta_livre()
    _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"
    # O índice do Acervo sobe junto com o servidor; espera ele ter os seis.
    for _ in range(60):
        if len(api.estado.searcher.documents) >= 6:
            break
        time.sleep(1)
    print(f"Acervo da demonstração: {len(api.estado.searcher.documents)} documentos · modelo {api.estado.client.model}\n")

    resultados = []
    criados = []
    try:
        for pergunta, caminho, aceitas in ROTEIRO:
            if so_programa and caminho != "programa":
                continue
            t = pedir(base, "POST", "/api/trabalhos", {"pedido": pergunta})
            criados.append(t["id"])
            comeco = time.time()
            try:
                eventos = conversar(base, f"/api/trabalhos/{t['id']}/perguntar", {"pergunta": pergunta})
            except Exception as exc:  # noqa: BLE001 - o roteiro segue
                eventos = [("erro", {"mensagem": str(exc)})]
            segundos = time.time() - comeco
            texto = "".join(d.get("t", "") for tipo, d in eventos if tipo == "token")
            proposta = next((d for tipo, d in eventos if tipo == "proposta"), {})
            veio = "programa" if proposta.get("tipo") == "programa" else "documentos"
            alvo = texto + " " + json.dumps(proposta, ensure_ascii=False)
            acertou = any(_plano(a) in _plano(alvo) for a in aceitas)
            erro = next((d.get("mensagem") for tipo, d in eventos if tipo == "erro"), "")
            resultados.append({"pergunta": pergunta, "esperado": caminho, "veio": veio, "acertou": acertou,
                               "segundos": round(segundos, 1), "resposta": texto[:600], "erro": erro})
            marca = "ok " if acertou and veio == caminho else "ERR"
            print(f"{marca} {segundos:6.1f}s  [{veio:10}] {pergunta}")
            if not acertou or erro:
                print(f"         esperado: {aceitas} · veio: {(erro or texto)[:160]!r}")
    finally:
        for id_ in criados:
            try:
                pedir(base, "DELETE", f"/api/trabalhos/{id_}")
            except Exception:  # noqa: BLE001
                pass

    print()
    for grupo in ("programa", "documentos"):
        rs = [r for r in resultados if r["esperado"] == grupo]
        if not rs:
            continue
        certos = sum(1 for r in rs if r["acertou"] and r["veio"] == grupo)
        tempos = sorted(r["segundos"] for r in rs)
        print(f"{grupo:10}: {certos}/{len(rs)} certas · tempo mediano {tempos[len(tempos) // 2]:.1f} s · máximo {tempos[-1]:.1f} s")
    (DEMO / "roteiro-resultado.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
