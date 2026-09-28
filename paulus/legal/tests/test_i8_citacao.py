"""
Portao da I8 - o contrato de resposta [Tn] (src/citacoes.py).

Com respostas simuladas, as tres conferencias:
  1. frase sem marca fica com o rotulo "sem fonte";
  2. marca de trecho que nao existe refaz a resposta uma vez, com menos
     trechos;
  3. lei, artigo, sumula ou numero de processo que nao esta em nenhum trecho
     sai da resposta.
E pela conversa: os trechos chegam numerados, o texto conferido e o que
fica gravado, e a resposta sem fundamento vira o cartao com "ler o
documento inteiro" e "procurar em todo o Acervo".

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_i8_citacao.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-i8-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


TRECHOS = ["CLÁUSULA 3ª - DO ATRASO. A multa é de 2% sobre o valor devido, conforme o art. 406 do Código Civil.",
           "CLÁUSULA 6ª - DO FORO. Fica eleito o foro de Santarém. Processo 0801234-50.2024.8.14.0301."]


def test_conferencias() -> None:
    print("\nas três conferências")
    import citacoes

    r = citacoes.revisar("A multa é de 2% [T1]. O foro é o de Santarém [T2].", TRECHOS)
    checar(r.texto == "A multa é de 2% [T1]. O foro é o de Santarém [T2]." and not r.sem_fonte and not r.removidas,
           "resposta toda marcada passa intacta", r.texto)
    r = citacoes.revisar("A multa é de 2% [T1]. O prazo de defesa é de 15 dias.", TRECHOS)
    checar(r.sem_fonte == 1 and r.texto.endswith("15 dias. [sem fonte]"), "1: frase sem marca ganha “sem fonte”", r.texto)
    r = citacoes.revisar("A multa é de 2% [T9].", TRECHOS)
    checar(r.refazer and r.marcas_invalidas == [9], "2: marca que não existe pede refazer", r.marcas_invalidas)
    r = citacoes.revisar("A multa é de 2%, nos termos do art. 412 do Código Civil [T1].", TRECHOS)
    checar("412" not in r.texto and r.removidas == ["art. 412 do Código Civil"] and r.texto == "A multa é de 2% [T1].",
           "3: artigo que não está nos trechos sai, e a marca fica", (r.texto, r.removidas))
    r = citacoes.revisar("Conforme a Súmula 331 do TST, cabe recurso [T1].", TRECHOS)
    checar(r.removidas == ["Súmula 331 do TST"] and r.texto.startswith("Cabe recurso"), "3: súmula inventada sai",
           (r.texto, r.removidas))
    r = citacoes.revisar("O processo 0801234-05.2024.8.14.0301 corre em Santarém [T2].", TRECHOS)
    checar("0801234-05" not in r.texto and r.removidas, "3: número de processo com dígito trocado sai", r.texto)
    r = citacoes.revisar("A multa segue o art. 406 do Código Civil [T1].", TRECHOS)
    checar(not r.removidas, "3: artigo que está no trecho fica")
    r = citacoes.revisar("Não encontrei essa informação nos documentos.", TRECHOS)
    checar(r.sem_fundamento, "nenhuma frase com marca: sem fundamento")
    contexto, mapa = citacoes.numerar(["x"] and [type("H", (), {"chunk": type("C", (), {
        "doc_name": "Contrato.pdf", "text": TRECHOS[0], "pagina_inicio": 3})()})()])
    checar(contexto.startswith("[T1] (Contrato.pdf, p. 3)\nCLÁUSULA 3ª") and list(mapa) == [1],
           "o trecho numerado leva o arquivo e a página", contexto[:40])


class Simulado:
    """O modelo de mentira: devolve as respostas da fila, uma por chamada."""

    model = "falso:1b"
    num_ctx = 16384
    host = "http://127.0.0.1:9"
    aceita_tarefa = True

    def __init__(self, respostas: list[str]) -> None:
        self.respostas = list(respostas)
        self.contextos: list[str] = []
        self.ensinados: list[str] = []

    def ask(self, question, context="", *, sistema="", ensinado="", stream=False, on_token=None, on_fase=None,
            parar=None, tarefa="", historico=None):
        self.contextos.append(context)
        self.ensinados.append(ensinado)
        texto = self.respostas.pop(0) if self.respostas else ""
        if on_token:
            on_token(texto)
        return texto

    def digest(self, model=""):
        return ""


def test_na_conversa() -> None:
    print("\nna conversa")
    from fastapi.testclient import TestClient

    import api

    api.estado.saber.ligada = False
    api.estado.prefs.dados.setdefault("ia", {})["citacao"] = True
    pasta = Path(api.estado.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    # Cada clausula com corpo proprio (mais de 80 tokens), para virar um
    # trecho so dela - clausulas curtas se juntam (I5).
    corpo = " Esta cláusula vale durante toda a vigência do contrato e obriga as partes e seus sucessores." * 4
    (pasta / "contrato.txt").write_text("\n\n".join(t + corpo for t in TRECHOS), encoding="utf-8")
    api.estado.recarregar()
    c = TestClient(api.app, headers=api.cabecalho_local())

    def perguntar(simulado, texto="qual a multa?"):
        api.estado.client = simulado
        api.estado.cliente_para = lambda tarefa: simulado
        id_ = c.post("/api/trabalhos", json={"pedido": "teste"}).json()["id"]
        r = c.post(f"/api/trabalhos/{id_}/perguntar", json={"pergunta": texto, "apenas": ["contrato.txt"], "documentos": True})
        eventos = []
        for bloco in r.text.split("\n\n"):
            tipo = next((l[7:] for l in bloco.splitlines() if l.startswith("event: ")), "")
            corpo = "".join(l[6:] for l in bloco.splitlines() if l.startswith("data: "))
            if tipo:
                eventos.append((tipo, json.loads(corpo or "{}")))
        t = c.get(f"/api/trabalhos/{id_}").json()
        return eventos, [m for m in t["mensagens"] if m["autor"] == "paulus"][-1]

    s = Simulado(["A multa é de 2% [T1], conforme o art. 999 do CPC. O prazo é de 15 dias."])
    eventos, msg = perguntar(s)
    checar("[T1]" in s.contextos[0] and "[T2]" in s.contextos[0], "os trechos chegam numerados", s.contextos[0][:80])
    checar("Termine cada frase" in s.ensinados[0], "com a regra das marcas na instrução")
    rev = next((d for t, d in eventos if t == "revisao"), {})
    checar(rev and "999" not in rev["texto"] and "[sem fonte]" in rev["texto"], "a revisão chega à tela", rev)
    checar(msg["texto"] == rev.get("texto") or msg["texto"].startswith(rev.get("texto", "?")),
           "o texto conferido é o que fica gravado", msg["texto"])

    s = Simulado(["A multa é de 2% [T7].", "A multa é de 2% [T1]."])
    eventos, msg = perguntar(s)
    checar(any(t == "refazendo" for t, _ in eventos) and len(s.contextos) == 2, "marca inexistente: refez uma vez",
           [t for t, _ in eventos])
    checar("[T2]" not in s.contextos[1] and msg["texto"].startswith("A multa é de 2% [T1]."),
           "a segunda leitura tem menos trechos, e a resposta dela fica", (s.contextos[1][:60], msg["texto"]))

    s = Simulado(["Os documentos lidos não trazem esse dado."])
    eventos, msg = perguntar(s, "qual o índice de reajuste?")
    oferta = next((d for t, d in eventos if t == "oferta"), {})
    checar(oferta.get("tipo") == "escopo" and oferta.get("motivo") == "sem_fundamento"
           and oferta.get("nomes") == ["contrato.txt"], "sem fundamento: o cartão com os dois caminhos", oferta)
    checar((msg.get("proposta") or {}).get("motivo") == "sem_fundamento", "e o cartão fica guardado com a resposta")

    api.estado.prefs.dados["ia"]["citacao"] = False
    s = Simulado(["A multa é de 2%."])
    eventos, msg = perguntar(s)
    checar("[T1]" not in s.contextos[0] and not any(t == "revisao" for t, _ in eventos),
           "com a chave desligada, nada muda")


def main() -> int:
    print("=" * 55)
    print("  I8 - contrato de resposta [Tn]")
    print("=" * 55)
    try:
        test_conferencias()
        test_na_conversa()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print("   -", f)
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
