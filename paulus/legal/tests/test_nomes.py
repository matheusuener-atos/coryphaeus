"""
Arquivo de mesmo nome: a pessoa decide, o programa nao (src/nomes.py).

  - o modulo: sem conflito o proprio nome; conflito sem decisao nao grava e
    sugere "nome (2).ext"; renomear usa o nome escolhido (e volta a perguntar
    se ele tambem existe); substituir usa o proprio nome; dois arquivos do
    mesmo lote nao caem no mesmo nome;
  - as rotas: incluir no Acervo, anexar pelo caminho, exportar a planilha do
    mes - 409 com os conflitos e nada gravado; com a decisao, grava; o mesmo
    conteudo nao e conflito.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_nomes.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))
DADOS = tempfile.mkdtemp(prefix="paulus_nomes_")
os.environ["PAULUS_DADOS"] = DADOS
os.environ.setdefault("PAULUS_MODELOS", str(RAIZ / "data" / "modelos"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def test_modulo() -> None:
    print("\no modulo")
    import nomes

    pasta = Path(tempfile.mkdtemp(prefix="paulus_nomes_mod_"))
    (pasta / "contrato.pdf").write_text("antigo")
    pend: list = []
    checar(nomes.destino(pasta, "novo.pdf", {}, pend) == pasta / "novo.pdf" and not pend, "sem conflito, o proprio nome")
    checar(nomes.destino(pasta, "contrato.pdf", {}, pend) is None and pend[0]["sugestao"] == "contrato (2).pdf",
           "conflito sem decisao nao da destino e sugere (2)", pend)
    try:
        nomes.conferir(pend)
        checar(False, "conferir levanta NomeRepetido")
    except nomes.NomeRepetido as exc:
        checar(exc.conflitos[0]["existente"] == "contrato.pdf", "conferir levanta NomeRepetido com os conflitos")
    dec = nomes.do_pedido({"decisoes": {"contrato.pdf": {"acao": "renomear", "nome": "contrato v2"}}})
    pend = []
    checar(nomes.destino(pasta, "contrato.pdf", dec, pend) == pasta / "contrato v2.pdf" and not pend,
           "renomear usa o nome escolhido e devolve a extensao")
    (pasta / "contrato v2.pdf").write_text("x")
    pend = []
    checar(nomes.destino(pasta, "contrato.pdf", dec, pend) is None and pend[0]["existente"] == "contrato v2.pdf",
           "renomear para um nome que tambem existe volta a perguntar")
    dec = nomes.do_pedido({"decisoes": json.dumps({"contrato.pdf": {"acao": "substituir"}})})
    pend = []
    checar(nomes.destino(pasta, "contrato.pdf", dec, pend) == pasta / "contrato.pdf" and not pend,
           "substituir (decisao vinda como texto de formulario) usa o proprio nome")
    pend, ocupados = [], set()
    a = nomes.destino(pasta, "igual.pdf", {}, pend, ocupados=ocupados)
    b = nomes.destino(pasta, "igual.pdf", {}, pend, ocupados=ocupados)
    checar(a == pasta / "igual.pdf" and b is None and pend[-1]["sugestao"] == "igual (2).pdf",
           "dois do mesmo lote com o mesmo nome: o segundo pergunta")
    checar(nomes.limpar('a<b>:c?.pdf', ".pdf") == "a b c .pdf".replace("  ", " ") or "?" not in nomes.limpar("a?b", ".pdf"),
           "o nome digitado perde o que o Windows recusa")
    checar(nomes.do_pedido({"decisoes": {"x.pdf": {"acao": "apagar"}}}) == {}, "decisao desconhecida e ignorada")
    shutil.rmtree(pasta, ignore_errors=True)


def test_rotas() -> None:
    print("\nas rotas")
    from fastapi.testclient import TestClient

    import api

    c = TestClient(api.app)
    pasta = Path(api.estado.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "parecer.txt").write_text("versao antiga", encoding="utf-8")

    def subir(conteudo: str, decisoes: dict | None = None, nome: str = "parecer.txt"):
        return c.post("/api/upload", files=[("arquivos", (nome, conteudo.encode("utf-8"), "text/plain"))],
                      data={"autorizados": "[]", "decisoes": json.dumps(decisoes or {})})

    r = subir("versao nova")
    corpo = r.json()
    checar(r.status_code == 409 and corpo["conflitos"][0]["sugestao"] == "parecer (2).txt",
           "incluir no Acervo com nome repetido: 409 com a sugestao", corpo)
    checar((pasta / "parecer.txt").read_text(encoding="utf-8") == "versao antiga", "e nada foi gravado")
    r = subir("versao antiga")
    checar(r.status_code == 200 and "parecer.txt" in r.json()["salvos"], "o mesmo conteudo nao e conflito", r.text[:200])
    r = subir("versao nova", {"parecer.txt": {"acao": "renomear", "nome": "parecer revisado"}})
    checar(r.status_code == 200 and (pasta / "parecer revisado.txt").read_text(encoding="utf-8") == "versao nova",
           "renomear grava com o nome escolhido", r.text[:200])
    r = subir("versao nova", {"parecer.txt": {"acao": "substituir"}})
    checar(r.status_code == 200 and (pasta / "parecer.txt").read_text(encoding="utf-8") == "versao nova",
           "substituir troca o que estava la", r.text[:200])

    # Anexar pelo caminho (Meu computador / Google Drive).
    fora = Path(tempfile.mkdtemp(prefix="paulus_nomes_fora_")) / "parecer.txt"
    fora.write_text("terceira versao", encoding="utf-8")
    r = c.post("/api/anexar/caminhos", json={"caminhos": [str(fora)]})
    checar(r.status_code == 409 and r.json()["conflitos"][0]["nome"] == "parecer.txt",
           "anexar pelo caminho com nome repetido: 409", r.text[:200])
    r = c.post("/api/anexar/caminhos", json={"caminhos": [str(fora)], "decisoes": {"parecer.txt": {"acao": "renomear", "nome": "parecer 3.txt"}}})
    checar(r.status_code == 200 and (pasta / "parecer 3.txt").exists() and
           (pasta / "parecer.txt").read_text(encoding="utf-8") == "versao nova",
           "com a decisao, copia com o outro nome e o de la fica", r.text[:200])

    # A planilha do mes: a segunda exportacao pergunta.
    r1 = c.post("/api/financeiro/exportar", json={"mes": "2026-09"})
    r2 = c.post("/api/financeiro/exportar", json={"mes": "2026-09"})
    checar(r1.status_code == 200 and r2.status_code == 409, "exportar o mesmo mes de novo pergunta", (r1.status_code, r2.status_code))
    r3 = c.post("/api/financeiro/exportar", json={"mes": "2026-09", "decisoes": {"financeiro-2026-09.xlsx": {"acao": "substituir"}}})
    baixar = c.get("/api/financeiro/exportar", params={"mes": "2026-09", "arquivo": r3.json().get("nome", "")})
    checar(r3.status_code == 200 and baixar.status_code == 200 and baixar.content[:2] == b"PK",
           "substituindo, gera e o GET entrega a planilha gerada")
    fuga = c.get("/api/financeiro/exportar", params={"mes": "2026-09", "arquivo": "..\\..\\preferencias.json"})
    checar(fuga.status_code == 404, "o GET so entrega planilha da pasta Planilhas")


def main() -> int:
    try:
        test_modulo()
        test_rotas()
    finally:
        shutil.rmtree(DADOS, ignore_errors=True)
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S)")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
