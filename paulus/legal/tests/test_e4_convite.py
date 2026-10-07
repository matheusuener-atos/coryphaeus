"""
Portao da E4 do PAULUS de equipe (docs/PLANO-EQUIPE.md) - so no servidor, a
equipe entra por convite (src/acesso/convites.py).

  - sem titular pronto, nao ha convite (o convidado viraria titular);
  - sem o acesso de fora conectado, nao ha link;
  - o link e https://<endereco>/convite/<codigo>; de fora, sem sessao, a
    pagina abre e as tres rotas do convite respondem; o resto continua 401;
  - aceitar pede a verificacao contra robos e senha forte; a conta nasce
    colaborador, com as permissoes do convite, e so entra depois do codigo;
  - confirmar com o codigo certo devolve 10 codigos de recuperacao e gasta o
    convite; a pessoa entra com senha + codigo;
  - quem abandona no meio abre de novo: senha e QR refeitos;
  - cancelado, vencido, usado, inexistente: a frase de cada um;
  - convidar de fora: 403.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_e4_convite.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-e4-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def test_http() -> None:
    print("\no convite, de ponta a ponta")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI (fora do Windows)")
        return
    from fastapi.testclient import TestClient

    import api
    from acesso.contas import codigo_totp

    servico = api.estado.acesso_de_fora
    # o PAULUS do servidor vinculado (E5), aberto: convidar e ligar o acesso pedem o vinculo
    api.estado.prefs.dados["vinculo"] = {"email": "dono@x.com", "nome": "Dono", "em": "", "manter_aberto": True}
    prefs = api.estado.prefs.dados["acesso_remoto"]
    servico.conferir_turnstile = lambda token, ip="": "ok" if token == "ok" else "recusado"
    # O convite por senha (o caminho sem o Google): o "so Google" do
    # escritorio e testado em test_e3_google.py.
    prefs["ligado"] = True
    prefs["so_google"] = False
    local = TestClient(api.app, headers=api.cabecalho_local())

    def de_fora() -> TestClient:
        return TestClient(api.app, base_url="https://moura.paulus.ia.br", headers={"Cf-Connecting-IP": "200.3.3.3"})

    try:
        r = local.post("/api/acesso/convites", json={"nome": "Bia Souza", "email": "bia@x.com"})
        checar(r.status_code == 400, "sem titular e sem endereco: nao ha convite", r.text[:160])
        t = servico.contas.criar("Tita", "tita@x.com", "titular", "senha-da-tita-1")
        servico.contas.confirmar_totp(t["conta"]["id"], codigo_totp(t["segredo"], int(time.time() // 30) - 1))
        r = local.post("/api/acesso/convites", json={"nome": "Bia Souza", "email": "bia@x.com"})
        checar(r.status_code == 400 and "acesso externo" in r.json().get("detail", ""), "sem o acesso conectado: nao ha link",
               r.text[:160])
        prefs["hostname"] = "moura.paulus.ia.br"
        r = local.post("/api/acesso/convites", json={"nome": "Bia Souza", "email": "bia@x.com",
                                                     "permissoes": {"agenda": "faz"}})
        checar(r.status_code == 200 and r.json()["link"].startswith("https://moura.paulus.ia.br/convite/"), "o link",
               r.text[:200])
        codigo = r.json()["link"].rsplit("/", 1)[1]
        checar(len(codigo) >= 30, "o codigo do convite e longo (nao se adivinha)", len(codigo))
        r = local.post("/api/acesso/convites", json={"nome": "Tita 2", "email": "tita@x.com"})
        checar(r.status_code == 400, "e-mail que ja tem conta: nao convida")

        print("  o convidado, de fora e sem conta")
        f = de_fora()
        pagina = f.get("/convite/" + codigo)
        checar(pagina.status_code == 200 and "passo-senha" in pagina.text and pagina.headers.get("x-frame-options") == "DENY",
               "a pagina do convite abre sem sessao, com os cabecalhos de seguranca")
        checar(f.get("/api/status").status_code == 401, "o resto continua 401")
        r = f.get("/api/acesso/convite/" + codigo)
        checar(r.status_code == 200 and r.json()["nome"] == "Bia Souza" and r.json()["email"] == "bia@x.com",
               "ver o convite", r.text[:200])
        r = f.post(f"/api/acesso/convite/{codigo}/aceitar", json={"senha": "senha-da-bia-1"})
        checar(r.status_code == 403, "aceitar sem a verificacao contra robos: 403", r.status_code)
        r = f.post(f"/api/acesso/convite/{codigo}/aceitar", json={"senha": "curta", "turnstile": "ok"})
        checar(r.status_code == 400, "senha fraca: 400", r.status_code)
        r = f.post(f"/api/acesso/convite/{codigo}/aceitar", json={"senha": "senha-provisoria-1", "turnstile": "ok"})
        checar(r.status_code == 200 and r.json()["otpauth"].startswith("otpauth://") and r.json()["qr_svg"].startswith("<svg"),
               "aceitar: o QR e o otpauth:// para o botao do celular", r.text[:120])
        conta = next(c for c in servico.contas.listar() if c["email"] == "bia@x.com")
        checar(conta["papel"] == "colaborador" and not conta["totp_confirmado"] and conta["permissoes"]["agenda"] == "faz",
               "a conta nasce colaborador, sem autenticador, com as permissoes do convite", conta)

        # Abandonou e abriu de novo: senha e QR refeitos, a mesma conta.
        r = f.post(f"/api/acesso/convite/{codigo}/aceitar", json={"senha": "senha-da-bia-1", "turnstile": "ok"})
        segredo = r.json()["segredo"]
        checar(r.status_code == 200 and len([c for c in servico.contas.listar() if c["email"] == "bia@x.com"]) == 1,
               "abrir de novo refaz senha e QR, na mesma conta")
        r = f.post("/api/acesso/entrar", json={"email": "bia@x.com", "senha": "senha-da-bia-1", "turnstile": "ok"})
        checar(r.status_code == 401, "antes do codigo, a conta nao entra", r.status_code)
        r = f.post(f"/api/acesso/convite/{codigo}/confirmar", json={"codigo": "000000"})
        checar(r.status_code == 400, "codigo errado: 400")
        passo = int(time.time() // 30)
        r = f.post(f"/api/acesso/convite/{codigo}/confirmar", json={"codigo": codigo_totp(segredo, passo)})
        checar(r.status_code == 200 and len(r.json()["codigos_recuperacao"]) == 10, "confirmar: 10 codigos de recuperacao",
               r.text[:160])
        checar(f.get("/api/acesso/convite/" + codigo).status_code == 410, "o convite usado nao vale mais")
        pend = f.post("/api/acesso/entrar", json={"email": "bia@x.com", "senha": "senha-da-bia-1", "turnstile": "ok"})
        r = f.post("/api/acesso/entrar/codigo", json={"pendente": pend.json().get("pendente", ""),
                                                      "codigo": codigo_totp(segredo, passo + 1)})
        checar(r.status_code == 200, "a Bia entra com senha + codigo", r.text[:160])
        checar(any(e.get("acao") == "convite_aceito" for e in servico.eventos), "o aceite ficou no registro de acessos")

        print("  cancelado, vencido, inexistente, e de fora")
        r = local.post("/api/acesso/convites", json={"nome": "Caio", "email": "caio@x.com"})
        c2 = r.json()["link"].rsplit("/", 1)[1]
        local.delete("/api/acesso/convites/" + r.json()["convite"]["id"])
        r = f.get("/api/acesso/convite/" + c2)
        checar(r.status_code == 410 and "cancelado" in r.json()["detail"], "cancelado: a frase", r.text[:160])
        r = local.post("/api/acesso/convites", json={"nome": "Duda", "email": "duda@x.com"})
        c3 = r.json()["link"].rsplit("/", 1)[1]
        antes = servico.convites.relogio
        servico.convites.relogio = lambda: time.time() + 8 * 24 * 3600
        try:
            r = f.get("/api/acesso/convite/" + c3)
            checar(r.status_code == 410 and "venceu" in r.json()["detail"], "depois de 7 dias: venceu", r.text[:160])
        finally:
            servico.convites.relogio = antes
        checar(f.get("/api/acesso/convite/nao-existe-" + "x" * 30).status_code == 410, "codigo inventado: 410")
        lista = local.get("/api/acesso/convites").json()["convites"]
        checar({x["estado"] for x in lista} >= {"aceito", "revogado", "aberto"}, "a lista diz o estado de cada convite",
               [x["estado"] for x in lista])
        tita = de_fora()
        pend = tita.post("/api/acesso/entrar", json={"email": "tita@x.com", "senha": "senha-da-tita-1", "turnstile": "ok"})
        r = tita.post("/api/acesso/entrar/codigo", json={"pendente": pend.json()["pendente"],
                                                         "codigo": codigo_totp(t["segredo"], int(time.time() // 30))})
        tita.headers["X-PAULUS-CSRF"] = r.json()["csrf"]
        r = tita.post("/api/acesso/convites", json={"nome": "X", "email": "x@x.com"})
        checar(r.status_code == 403, "convidar de fora: 403, mesmo para o titular", r.status_code)
    finally:
        prefs["ligado"] = False
        prefs["hostname"] = ""
        prefs["so_google"] = True
        servico.__dict__.pop("conferir_turnstile", None)


def main() -> int:
    print("=" * 55)
    print("  E4 - so no servidor: a equipe entra por convite")
    print("=" * 55)
    try:
        test_http()
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
