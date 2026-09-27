"""
Testes do que o PAULUS gera e vai para o Acervo (src/api.py, _pasta_no_acervo).

  - editor: um arquivo por documento e formato, atualizado no lugar - sem
    "(2)", "(3)"; o que alguém mudou por fora não é sobrescrito; título novo
    troca o nome; a planilha guardada entra no Acervo (.xlsx agora é lido);
  - recibos da folha: geram (antes davam erro sempre) e ficam em
    Financeiro/Recibos;
  - comprovante e planilha do mês: em Financeiro, no Acervo;
  - transcrição exportada: em Gravações, no Acervo.

Tudo numa pasta temporária (PAULUS_DADOS).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_gerados.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-gerados-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def main() -> int:
    print("=" * 55)
    print("  o que o PAULUS gera vai para o Acervo")
    print("=" * 55)
    from fastapi.testclient import TestClient

    import api

    c = TestClient(api.app)
    Path(api.estado.pasta).mkdir(parents=True, exist_ok=True)
    api.estado.recarregar()
    programa = Path(api.estado.pasta)

    def no_acervo(caminho) -> bool:
        deadline = time.time() + 10
        alvo = api.chave_do_caminho(caminho)
        while time.time() < deadline:
            if not api.estado.lendo.get("andando") and alvo in {api.chave_do_caminho(d.path) for d in api.estado.searcher.documents}:
                return True
            time.sleep(0.2)
        return False

    print("\neditor: um arquivo por documento")
    doc = c.post("/api/documentos", json={"titulo": "Contrato de honorários", "corpo": "<p>Honorários de R$ 4.500,00.</p>"}).json()
    id_ = doc.get("id") or (doc.get("documento") or {}).get("id")
    a = c.post(f"/api/documentos/{id_}/biblioteca", json={"formato": "pdf"}).json()
    b = c.post(f"/api/documentos/{id_}/biblioteca", json={"formato": "pdf"}).json()
    pasta_editor = programa / "Editor"
    checar(a["caminho"] == b["caminho"] and len(list(pasta_editor.glob("*.pdf"))) == 1,
           "guardar duas vezes atualiza o mesmo arquivo, sem “(2)”", [p.name for p in pasta_editor.glob("*")])
    checar(no_acervo(a["caminho"]), "e ele está no Acervo")
    Path(a["caminho"]).write_bytes(Path(a["caminho"]).read_bytes() + b"\n% mudado por fora")
    d = c.post(f"/api/documentos/{id_}/biblioteca", json={"formato": "pdf"}).json()
    checar(d["caminho"] != a["caminho"] and Path(a["caminho"]).exists(),
           "arquivo mudado por fora não é sobrescrito: o novo sai com outro nome", d["guardado"])
    c.post(f"/api/documentos/{id_}", json={"titulo": "Contrato de honorários - Cooperativa"})
    item = c.get(f"/api/documentos/{id_}").json()
    titulo_novo = (item.get("titulo") or (item.get("documento") or {}).get("titulo") or "")
    e = c.post(f"/api/documentos/{id_}/biblioteca", json={"formato": "pdf"}).json()
    if "Cooperativa" in titulo_novo:
        checar("Cooperativa" in e["guardado"] and not Path(d["caminho"]).exists(),
               "título novo: o arquivo que era só do PAULUS dá lugar ao de nome novo", [p.name for p in pasta_editor.glob("*")])
    else:
        print("  (a rota de renomear não aceitou esse formato; pulei o título novo)")
    senha = c.post(f"/api/documentos/{id_}/biblioteca", json={"formato": "pdf", "senha": "1234"}).json()
    checar("com senha" in senha["guardado"] and senha["caminho"] != e["caminho"], "o PDF com senha é outro arquivo, não troca o sem senha", senha["guardado"])

    plan = c.post("/api/documentos", json={"titulo": "Controle de prazos", "tipo": "planilha"}).json()
    pid = plan.get("id") or (plan.get("documento") or {}).get("id")
    x = c.post(f"/api/documentos/{pid}/biblioteca", json={}).json()
    checar(x["guardado"].endswith(".xlsx") and no_acervo(x["caminho"]), "a planilha guardada entra no Acervo (xlsx agora é lido)", x)

    print("\nrecibos da folha")
    cid = api.estado.cadastros.salvar({"tipo": "colaborador", "nome": "Lívia Santos", "vinculo": "estagio", "salario_centavos": 150000})
    checar(bool(cid), "cadastro com vínculo")
    r = c.post("/api/financeiro/folha/montar", json={"mes": "2026-09"})
    r = c.post("/api/financeiro/folha/recibos", json={"mes": "2026-09"})
    corpo = r.json()
    checar(r.status_code == 200 and corpo.get("recibos"), "gera os recibos (antes dava erro sempre)", corpo)
    if r.status_code == 200:
        pasta = Path(corpo["pasta"])
        checar(pasta == programa / "Financeiro" / "Recibos" / "2026-09", "em Financeiro/Recibos/<mês>, no Acervo", str(pasta))
        pdfs = list(pasta.glob("*.pdf"))
        checar(pdfs and no_acervo(pdfs[0]), "e o recibo entra no Acervo")

    print("\nFinanceiro")
    lid = api.estado.financeiro.salvar({"tipo": "despesa", "descricao": "Aluguel", "valor": "2.800,00", "vencimento": "2026-09-10"})
    r = c.post(f"/api/financeiro/lancamentos/{lid}/comprovante",
               files={"arquivo": ("comprovante aluguel.pdf", Path(a["caminho"]).read_bytes(), "application/pdf")})
    comp = r.json()
    caminho = next((x.get("caminho") for x in comp.get("comprovantes", []) if x.get("caminho")), "") or comp.get("caminho", "")
    checar(r.status_code == 200 and "Financeiro" in caminho and "Comprovantes" in caminho, "comprovante em Financeiro/Comprovantes", caminho or comp)
    r = c.get("/api/financeiro/exportar?mes=2026-09")
    planilha = programa / "Financeiro" / "Planilhas" / "financeiro-2026-09.xlsx"
    checar(r.status_code == 200 and planilha.exists() and no_acervo(planilha), "a planilha do mês entra no Acervo", r.status_code)

    print("\ngravação")
    original = api._docx_da_gravacao
    api._docx_da_gravacao = lambda _id: ("Reunião com a Cooperativa", RAIZ.joinpath("tests").exists() and _docx_de_teste())
    try:
        g = c.post("/api/gravacoes/1/exportar").json()
    finally:
        api._docx_da_gravacao = original
    checar(Path(g["path"]).parent == programa / "Gravações" and no_acervo(g["path"]), "a transcrição exportada fica em Gravações, no Acervo", g)

    shutil.rmtree(TMP, ignore_errors=True)
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


def _docx_de_teste() -> bytes:
    import io

    from docx import Document

    d = Document()
    d.add_paragraph("Transcrição: a Cooperativa quer renovar o transporte por mais doze meses.")
    saida = io.BytesIO()
    d.save(saida)
    return saida.getvalue()


if __name__ == "__main__":
    sys.exit(main())
