"""
A busca de tudo (Ctrl+K): /api/busca e o que a tela faz com ela (js/50-busca.js).

  - acha cliente, servico, documento, tarefa e lancamento pelo termo, sem
    depender de acento nem de maiuscula;
  - termo curto: nada;
  - de fora: so os modulos que a pessoa ve, e so os servicos de que participa.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_busca.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-busca-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def test_busca() -> None:
    print("\na busca de tudo")
    from fastapi.testclient import TestClient

    import api

    local = TestClient(api.app, headers=api.cabecalho_local())
    cli = local.post("/api/cadastros", json={"id": None, "dados": {"tipo": "cliente", "nome": "Cooperativa Agrícola Vale Verde"}}).json()["id"]
    s_coop = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Renovação da Cooperativa", "cadastro_id": cli}}).json()["id"]
    local.post("/api/tarefas", json={"id": None, "dados": {"titulo": "Minuta para a Cooperativa"}})
    local.post("/api/financeiro/lancamentos", json={"id": None, "dados": {"tipo": "recebimento", "descricao": "Honorários Cooperativa", "valor": "100,00"}})
    (api.estado.pasta).mkdir(parents=True, exist_ok=True)
    (api.estado.pasta / "Contrato Cooperativa.txt").write_text("Contrato de transporte.", encoding="utf-8")
    api.estado.recarregar()

    itens = local.get("/api/busca", params={"q": "COOPERATIVA agricola"}).json()["itens"]
    checar(any(i["tipo"] == "cadastro" for i in itens), "acha o cliente sem acento e em maiuscula", itens)
    tipos = {i["tipo"] for i in local.get("/api/busca", params={"q": "cooperativa"}).json()["itens"]}
    checar({"cadastro", "servico", "documento", "tarefa", "lancamento"} <= tipos, "cliente, servico, documento, tarefa e lancamento", tipos)
    checar(local.get("/api/busca", params={"q": "c"}).json()["itens"] == [], "termo curto: nada")

    import segredos

    if not segredos.disponivel():
        return
    print("  de fora")
    from acesso.contas import codigo_totp

    servico = api.estado.acesso_de_fora
    servico.conferir_turnstile = lambda token, ip="": "ok"
    api.estado.prefs.dados["acesso_remoto"].update(ligado=True, so_google=False)
    passo = int(time.time() // 30) - 1
    try:
        def entrar(nome, email, papel, niveis=None):
            c = servico.contas.criar(nome, email, papel, "senha-forte-" + nome.lower())
            servico.contas.confirmar_totp(c["conta"]["id"], codigo_totp(c["segredo"], passo))
            if niveis:
                local.put(f"/api/acesso/contas/{c['conta']['id']}/permissoes", json={"niveis": niveis})
            f = TestClient(api.app, base_url="https://x.paulus.ia.br", headers={"Cf-Connecting-IP": "200.2.2.2"})
            pend = f.post("/api/acesso/entrar", json={"email": email, "senha": "senha-forte-" + nome.lower(), "turnstile": "ok"}).json()["pendente"]
            r = f.post("/api/acesso/entrar/codigo", json={"pendente": pend, "codigo": codigo_totp(c["segredo"], passo + 1)})
            f.headers["X-PAULUS-CSRF"] = r.json()["csrf"]
            return f

        entrar("Tita", "tita@x.com", "titular")
        caio = entrar("Caio", "caio@x.com", "colaborador", {"cadastros": "nao", "financeiro": "nao", "servicos": "ver"})
        tipos = {i["tipo"] for i in caio.get("/api/busca", params={"q": "cooperativa"}).json()["itens"]}
        checar("cadastro" not in tipos and "lancamento" not in tipos, "sem Cadastros nem Financeiro: nao aparecem", tipos)
        checar("servico" not in tipos, "servico de que nao participa: nao aparece", tipos)
        checar("publicacao" not in tipos, "publicacoes: so no servidor")
    finally:
        api.estado.prefs.dados["acesso_remoto"].update(ligado=False, so_google=True)
    checar(s_coop > 0, "(o servico existe)")


def main() -> int:
    test_busca()
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print("    - " + f)
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
