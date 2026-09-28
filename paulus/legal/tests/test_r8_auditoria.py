"""
Portao da R8 - "quem acessou" (src/acesso/auditoria.py).

  - cada acao da tabela da R3, feita de fora, gera uma linha: entrada, login
    que falhou, bloqueio, documento aberto, download, proposta, aprovacao,
    pedido recusado por ser so do escritorio, saida;
  - a linha traz pessoa, e-mail do Access, data e hora, IP informado, acao e
    alvo;
  - editar uma linha a mao e detectado, com o numero da linha;
  - a poda de um ano mantem a corrente conferivel;
  - exportar em PDF funciona, e a tela so abre na janela local.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_r8_auditoria.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-r8-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def test_corrente() -> None:
    print("\na corrente de hashes")
    from acesso.auditoria import Auditoria

    relogio = [1_800_000_000.0]
    a = Auditoria(TMP / "sozinha" / "acessos.jsonl", relogio=lambda: relogio[0])
    for i in range(5):
        relogio[0] += 60
        a.registrar(acao="entrada", pessoa=f"P{i}", email=f"p{i}@x.com", ip="200.1.2.3", alvo="")
    checar(a.verificar() == {"integro": True, "linha": 0, "total": 5}, "5 linhas, corrente intacta", a.verificar())
    linhas = a.caminho.read_text(encoding="utf-8").splitlines()
    adulterada = json.loads(linhas[2])
    adulterada["pessoa"] = "Outra pessoa"
    linhas[2] = json.dumps(adulterada, ensure_ascii=False)
    a.caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    v = a.verificar()
    checar(not v["integro"] and v["linha"] == 3, "editar a 3a linha a mao e detectado, na linha 3", v)

    b = Auditoria(TMP / "poda" / "acessos.jsonl", relogio=lambda: relogio[0])
    relogio[0] = 1_800_000_000.0
    for i in range(3):
        b.registrar(acao="entrada", pessoa="Velho")
    relogio[0] += 400 * 86400
    b.registrar(acao="entrada", pessoa="Novo")
    checar(b.podar() == 3 and len(b.linhas()) == 1, "a poda tira o que passou de um ano")
    checar(b.verificar()["integro"], "e a corrente continua conferivel pela ancora", b.verificar())
    b.registrar(acao="saida", pessoa="Novo")
    checar(b.verificar() == {"integro": True, "linha": 0, "total": 2}, "e segue crescendo depois da poda", b.verificar())


def test_de_fora() -> None:
    print("\ncada acao de fora vira uma linha")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI")
        return
    from fastapi.testclient import TestClient

    import api
    from acesso.contas import codigo_totp

    servico = api.estado.acesso_de_fora
    servico.verificar_jwt = lambda t: {"email": t[3:]} if t and t.startswith("ok:") else None
    api.estado.prefs.dados["acesso_remoto"]["ligado"] = True
    local = TestClient(api.app, headers=api.cabecalho_local())
    try:
        c = servico.contas.criar("Tita", "tita@escritorio.com", "titular", "senha-da-tita-12")
        servico.contas.confirmar_totp(c["conta"]["id"], codigo_totp(c["segredo"], int(time.time() // 30) - 1))
        fora = TestClient(api.app, base_url="https://x.paulus.ia.br",
                          headers={"Cf-Access-Jwt-Assertion": "ok:tita@escritorio.com", "Cf-Connecting-IP": "200.9.8.7"})

        # login que falhou
        fora.post("/api/acesso/entrar", json={"email": "tita@escritorio.com", "senha": "errada-errada"})
        # entrada
        pend = fora.post("/api/acesso/entrar", json={"email": "tita@escritorio.com", "senha": "senha-da-tita-12"}).json()["pendente"]
        r = fora.post("/api/acesso/entrar/codigo", json={"pendente": pend, "codigo": codigo_totp(c["segredo"], int(time.time() // 30))})
        csrf = r.json()["csrf"]
        h = {"X-PAULUS-CSRF": csrf}
        # documento aberto e baixado
        doc = local.post("/api/documentos", json={"titulo": "Minuta", "tipo": "texto"}).json()
        fora.get(f"/api/documentos/{doc['id']}")
        fora.get(f"/api/documentos/{doc['id']}")
        fora.get(f"/api/documentos/{doc['id']}/docx")
        # proposta, aprovacao, recusa por ser so do escritorio
        prop = fora.post("/api/tarefas", json={"id": None, "dados": {"titulo": "Tarefa de fora"}}, headers=h).json()
        fora.post("/api/aprovacoes/decidir", json={"ids": [prop["pedido"]["id"]], "aprovar": True}, headers=h)
        fora.post("/api/biblioteca/lote/apagar", json={"caminhos": []}, headers=h)
        # saida
        fora.post("/api/acesso/sair", headers=h)
        # bloqueio: cinco erros seguidos
        for _ in range(5):
            fora.post("/api/acesso/entrar", json={"email": "tita@escritorio.com", "senha": "errada-errada"})

        linhas = servico.auditoria.linhas()
        acoes = [l["acao"] for l in linhas]
        for acao in ("login_falho", "entrada", "documento", "download", "proposta", "aprovacao", "recusado", "saida", "bloqueio"):
            checar(acao in acoes, f"'{acao}' registrado", acoes)
        checar(acoes.count("documento") == 1, "abrir o mesmo documento de novo em seguida nao repete a linha", acoes.count("documento"))
        entrada = next(l for l in linhas if l["acao"] == "entrada")
        checar(entrada["pessoa"] == "Tita" and entrada["email"] == "tita@escritorio.com" and entrada["ip"] == "200.9.8.7"
               and entrada["quando"][:4].isdigit(), "a linha tem pessoa, e-mail do Access, IP e hora", entrada)
        baixou = next(l for l in linhas if l["acao"] == "download")
        checar(baixou["alvo"] == "“Minuta” (DOCX)", "o download diz o que saiu, pelo nome", baixou["alvo"])
        checar(servico.auditoria.verificar()["integro"], "a corrente esta intacta")

        print("\na tela e o PDF")
        r = local.get("/api/acesso/auditoria?acao=download")
        checar(r.status_code == 200 and all(l["acao"] == "download" for l in r.json()["linhas"]) and r.json()["integro"],
               "filtrar por acao", r.text[:200])
        r = local.get("/api/acesso/auditoria/pdf")
        checar(r.status_code == 200 and r.content[:4] == b"%PDF" and "application/pdf" in r.headers.get("content-type", ""),
               "exportar em PDF", r.headers.get("content-type"))
        checar(fora.get("/api/acesso/auditoria").status_code in (401, 403), "de fora, a tela de acessos nao abre")
    finally:
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = False
        servico.verificar_jwt = None


def main() -> int:
    print("=" * 55)
    print("  R8 - quem acessou")
    print("=" * 55)
    try:
        test_corrente()
        test_de_fora()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
