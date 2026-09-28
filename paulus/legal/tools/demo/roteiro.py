"""
O roteiro da demonstração, medido: as perguntas que um advogado faria sobre
o escritório fictício de criar_demo.py, cada uma com a resposta certa.

Como os documentos da demonstração foram escritos aqui, a resposta certa é
conhecida - e dá para medir, com o modelo de verdade, quantas a conversa
acerta e quanto tempo leva. Dois conjuntos:

- BASICO: o roteiro da demonstração comercial - o que tem de dar certo.
- DIFICIL: o banco de provas - ausência (o documento não diz e o modelo não
  pode inventar), vários documentos, conta, lista, consequência, pergunta
  ambígua e consultas do programa que ainda não existem. Serve para achar
  onde a IA erra, não para mostrar.
- MATERIAL: o que só o manual de rotinas em PDF (material de consulta) diz -
  confere que o PAULUS aprendeu com o arquivo.

    venv\\Scripts\\python.exe tools\\demo\\roteiro.py                 (básico)
    venv\\Scripts\\python.exe tools\\demo\\roteiro.py --dificil       (banco de provas)
    venv\\Scripts\\python.exe tools\\demo\\roteiro.py --material      (o manual em PDF)
    venv\\Scripts\\python.exe tools\\demo\\roteiro.py --tudo
    venv\\Scripts\\python.exe tools\\demo\\roteiro.py --programa      (só as sem modelo)
    venv\\Scripts\\python.exe tools\\demo\\roteiro.py --dificil --modelo llama3.2:3b-instruct-q8_0

Precisa do Ollama ligado para as perguntas sobre documentos. Grava o
resultado em data/demo/roteiro-resultado[-<modelo>].json.
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
if "--modelo" in sys.argv:
    os.environ["PAULUS_MODEL"] = sys.argv[sys.argv.index("--modelo") + 1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from criar_demo import CNPJ_TRANSPORTES  # noqa: E402


def P(pergunta, caminho, alguma=(), todas=(), nunca=(), minimo=None, tipo=""):
    """
    Uma pergunta e como conferir a resposta.

    alguma: basta um destes aparecer. todas: cada item é uma lista de
    alternativas, e cada item tem de aparecer. nunca: nenhum destes pode
    aparecer (o número de outro contrato, o nome errado). minimo: (n, itens)
    - pelo menos n dos itens (cada um com alternativas) aparecem.
    """
    return {"pergunta": pergunta, "caminho": caminho, "alguma": list(alguma), "todas": [list(x) for x in todas],
            "nunca": list(nunca), "minimo": minimo, "tipo": tipo}


BASICO = [
    P("quais compromissos tenho amanhã?", "programa", ["Reunião com a Cooperativa"]),
    P("tenho alguma tarefa atrasada?", "programa", ["Enviar a minuta do aditivo"]),
    P("quanto recebi este mês?", "programa", ["7.500"]),
    P("quanto recebi da Cooperativa este mês?", "programa", ["7.500"]),
    P("como assino um PDF?", "programa", ["Assinatura"]),
    P("abra o financeiro", "programa", ["Financeiro"]),
    P("qual o valor mensal do contrato de transporte da Cooperativa?", "documentos", ["18.500", "19.980"]),
    P("qual o novo valor mensal definido no aditivo?", "documentos", ["19.980"]),
    P("qual o prazo de aviso para não renovar o contrato de transporte?", "documentos", ["60", "sessenta"]),
    P("qual a multa por atraso no pagamento do contrato de transporte?", "documentos", ["2%", "dois por cento"]),
    P("qual o foro do contrato de transporte?", "documentos", ["Santarém"]),
    P("em que dia vence o aluguel da Clínica Bem Viver?", "documentos", ["dia 5", "dia 05", "5 (cinco)", "dia cinco"]),
    P("qual índice reajusta o aluguel da Clínica?", "documentos", ["IGP-M", "IGPM"]),
    P("a procuração da Cooperativa dá poderes para renunciar a créditos?", "documentos", ["não"]),
    P("qual o prazo dado à Rio Fresco na notificação?", "documentos", ["10 dias", "dez dias", "10 (dez)"]),
    P("quanto são os honorários fixos do João Batista?", "documentos", ["4.500"]),
]

DIFICIL = [
    # --- o que está escrito, mas pede ler com atenção
    P("quem é o locador da sala 402?", "documentos", ["Marcos Antônio Lemos", "Marcos Antonio Lemos"], tipo="fato"),
    P("até quando vai a locação da Clínica Bem Viver?", "documentos", ["30 de junho de 2027", "30/06/2027"], tipo="data"),
    P("qual o CNPJ da Transportes Rio Fresco?", "documentos", [CNPJ_TRANSPORTES], tipo="fato"),
    P("qual o percentual de êxito no contrato do João Batista?", "documentos", ["20%", "vinte por cento"], tipo="fato"),
    P("qual a garantia da locação da Clínica?", "documentos", todas=[["caução", "caucao"], ["3", "três", "tres"]], tipo="fato"),
    # --- lista: todos os itens, não só o primeiro
    P("quais são as datas das parcelas dos honorários do João Batista?", "documentos",
      todas=[["10 de outubro", "10/10"], ["10 de novembro", "10/11"], ["10 de dezembro", "10/12"]], tipo="lista"),
    P("quais poderes especiais a procuração dá à Dra. Helena?", "documentos",
      todas=[["transigir"], ["quitação", "quitacao"], ["acordo"]], tipo="lista"),
    # --- dois documentos e comparação
    P("o que mudou no contrato de transporte com o aditivo?", "documentos", todas=[["19.980"], ["Altamira"]], tipo="comparacao"),
    P("quantas viagens por mês o transporte prevê, somando o aditivo?", "documentos", ["10 viagens", "dez viagens", "até 10", "total de 10"], tipo="conta"),
    # --- consequência
    P("o que acontece se a Rio Fresco não regularizar as entregas no prazo?", "documentos",
      todas=[["multa"], ["rescis"]], tipo="consequencia"),
    P("quanto custa rescindir o contrato de transporte sem motivo?", "documentos",
      todas=[["10%", "dez por cento"], ["30 dias", "trinta dias", "30 (trinta)"]], tipo="consequencia"),
    # --- ausência: o documento não diz, e o modelo não pode inventar
    P("qual a multa por atraso no aluguel da Clínica?", "documentos", ["não há", "não prevê", "não menciona", "não encontrei",
      "não consta", "não está", "não estabelece", "não define", "não traz", "não fala", "não existe", "nenhum documento"],
      nunca=["2%", "1% ao mês", "10%"], tipo="ausencia"),
    P("qual o valor da causa da reclamação trabalhista do João Batista?", "documentos", ["não há", "não menciona", "não encontrei",
      "não consta", "não está", "não informa", "não traz", "não define", "não diz", "não existe", "nenhum documento"], nunca=["4.500", "1.500"], tipo="ausencia"),
    P("quem é o advogado da Transportes Rio Fresco?", "documentos", ["não há", "não menciona", "não encontrei", "não consta",
      "não está", "não informa", "não identifica", "não traz", "não diz", "não existe", "nenhum documento"], nunca=["Helena"], tipo="ausencia"),
    # --- ambígua: "o contrato" com três contratos no acervo
    # ambígua: com três contratos, o programa pergunta qual (cartão), em vez
    # de o modelo escolher um e responder como se fosse o único
    P("qual o valor do contrato?", "pergunta", ["ambigua"], tipo="ambigua"),
    # --- consultas do programa (algumas ainda não existem: é o que se quer ver)
    P("o que tenho para hoje?", "programa", ["Ligação com a Clínica", "Conferir o reajuste"], tipo="consulta"),
    P("quanto tenho a receber?", "programa", ["3.900"], tipo="consulta"),
    P("tem algum cliente com pagamento atrasado?", "programa", ["2.400", "Clínica"], tipo="consulta"),
    P("quais serviços estão em andamento?", "programa", ["Renovação do contrato de transporte"], tipo="consulta"),
    P("quando vence o meu certificado digital?", "programa", ["certificado"], tipo="consulta"),
]


# O material de consulta: o manual de rotinas em PDF (criar_demo.MANUAL). A
# resposta só pode sair dele - nenhum documento do Acervo diz isso.
MATERIAL = [
    P("com quantos dias de antecedência devo protocolar uma contestação?", "documentos",
      ["três dias úteis", "3 dias úteis", "tres dias uteis"], tipo="material"),
    P("quanto o escritório cobra por uma consulta avulsa?", "documentos", ["450"], tipo="material"),
    P("por quanto tempo guardamos as pastas de clientes encerradas?", "documentos", ["cinco anos", "5 anos"], tipo="material"),
    P("em quanto tempo devemos responder o e-mail de um cliente?", "documentos",
      ["um dia útil", "1 dia útil", "um dia util"], tipo="material"),
    # documento e material juntos: 20% do contrato, entre 20% e 30% na tabela
    P("o percentual de êxito do contrato do João Batista está dentro da tabela do escritório?", "documentos",
      todas=[["20%", "vinte por cento"], ["30%", "trinta por cento"]], tipo="material"),
]


def _plano(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn").lower()


def conferir(p: dict, alvo: str) -> tuple[bool, str]:
    a = _plano(alvo)
    tem = lambda x: _plano(x) in a  # noqa: E731
    if p["alguma"] and not any(tem(x) for x in p["alguma"]):
        return False, "faltou: " + " | ".join(p["alguma"][:4])
    for alts in p["todas"]:
        if not any(tem(x) for x in alts):
            return False, "faltou: " + " | ".join(alts)
    if p["minimo"]:
        n, itens = p["minimo"]
        achados = sum(1 for alts in itens if any(tem(x) for x in alts))
        if achados < n:
            return False, f"só {achados} de {n} valores"
    ruins = [x for x in p["nunca"] if tem(x)]
    if ruins:
        return False, "inventou: " + ", ".join(ruins)
    return True, ""


def _local() -> dict:
    """O servidor sobe neste mesmo processo: o roteiro e cliente local, com a chave da janela."""
    import api

    return api.cabecalho_local()


def conversar(base: str, caminho: str, dados: dict, limite: int = 420) -> list[tuple[str, dict]]:
    req = urllib.request.Request(base + caminho, data=json.dumps(dados).encode(), method="POST",
                                 headers={**_local(), "Content-Type": "application/json"})
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
                                 headers={**_local(), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


def main() -> int:
    # A base tem datas relativas ao dia em que foi criada ("amanhã" é o dia
    # seguinte ao da criação). De outro dia, ela é refeita antes de medir.
    marca = DEMO / "criada-em.txt"
    from datetime import date as _date

    if not marca.exists() or marca.read_text(encoding="utf-8").strip() != _date.today().isoformat():
        import subprocess

        subprocess.run([sys.executable, str(Path(__file__).with_name("criar_demo.py")), "--refazer"], check=True)
    if "--tudo" in sys.argv:
        roteiro = BASICO + DIFICIL + MATERIAL
    elif "--dificil" in sys.argv:
        roteiro = DIFICIL
    elif "--material" in sys.argv:
        roteiro = MATERIAL
    else:
        roteiro = BASICO
    if "--programa" in sys.argv:
        roteiro = [p for p in roteiro if p["caminho"] == "programa"]

    from test_gravacoes import _porta_livre, _subir_servidor

    import api

    porta = _porta_livre()
    _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"
    for _ in range(60):
        if len(api.estado.searcher.documents) >= 6:
            break
        time.sleep(1)
    modelo = api.estado.client.model
    print(f"Acervo da demonstração: {len(api.estado.searcher.documents)} documentos · modelo {modelo}\n")

    resultados = []
    criados = []
    try:
        for p in roteiro:
            t = pedir(base, "POST", "/api/trabalhos", {"pedido": p["pergunta"]})
            criados.append(t["id"])
            comeco = time.time()
            try:
                eventos = conversar(base, f"/api/trabalhos/{t['id']}/perguntar", {"pergunta": p["pergunta"]})
            except Exception as exc:  # noqa: BLE001 - o roteiro segue
                eventos = [("erro", {"mensagem": str(exc)})]
            segundos = time.time() - comeco
            texto = "".join(d.get("t", "") for tipo, d in eventos if tipo == "token") + \
                "".join(d.get("mensagem", "") for tipo, d in eventos if tipo == "vazio")
            proposta = next((d for tipo, d in eventos if tipo == "proposta"), {})
            veio = ("programa" if proposta.get("tipo") == "programa"
                    else "pergunta" if proposta.get("tipo") == "escopo" else "documentos")
            alvo = texto + " " + json.dumps(proposta, ensure_ascii=False)
            acertou, motivo = conferir(p, alvo)
            erro = next((d.get("mensagem") for tipo, d in eventos if tipo == "erro"), "")
            certo = acertou and veio == p["caminho"] and not erro
            if veio != p["caminho"]:
                motivo = f"foi para {veio}" + (f"; {motivo}" if motivo else "")
            resultados.append({**{k: p[k] for k in ("pergunta", "caminho", "tipo")}, "veio": veio, "certo": certo,
                               "motivo": motivo or erro, "segundos": round(segundos, 1), "resposta": texto[:900]})
            print(f"{'ok ' if certo else 'ERR'} {segundos:6.1f}s  [{veio:10}] {p['pergunta']}")
            if not certo:
                print(f"         {motivo or erro} · resposta: {(erro or texto)[:220]!r}")
    finally:
        for id_ in criados:
            try:
                pedir(base, "DELETE", f"/api/trabalhos/{id_}")
            except Exception:  # noqa: BLE001
                pass

    print()
    for grupo in ("programa", "pergunta", "documentos"):
        rs = [r for r in resultados if r["caminho"] == grupo]
        if not rs:
            continue
        certos = sum(1 for r in rs if r["certo"])
        tempos = sorted(r["segundos"] for r in rs)
        print(f"{grupo:10}: {certos}/{len(rs)} certas · tempo mediano {tempos[len(tempos) // 2]:.1f} s · máximo {tempos[-1]:.1f} s")
    tipos = sorted({r["tipo"] for r in resultados if r["tipo"]})
    if tipos:
        print("por tipo: " + " · ".join(
            f"{t} {sum(1 for r in resultados if r['tipo'] == t and r['certo'])}/{sum(1 for r in resultados if r['tipo'] == t)}"
            for t in tipos))
    sufixo = "" if "--modelo" not in sys.argv else "-" + re.sub(r"[^a-z0-9.]+", "_", modelo.lower())
    (DEMO / f"roteiro-resultado{sufixo}.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=1),
                                                          encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
