"""
Portao da E5 do PAULUS de equipe (docs/PLANO-EQUIPE.md) - o PAULUS do
servidor vinculado a conta Google (src/vinculo.py).

Com o login do Google simulado (a Entrada de mentira chama a volta na hora):

  - sem vinculo, nada muda: nada trava;
  - vincular grava a conta, preenche Meus dados vazios e ja deixa aberto;
  - travado, a janela do servidor so alcanca a tela de destravar: as outras
    rotas respondem 423 (a trava e do servidor, e nao so da tela);
  - destravar com outra conta Google: recusado; com a vinculada: abre;
  - se a conta de titular desse e-mail tem o autenticador, pede o codigo;
  - "manter aberto" vale na proxima abertura (outra instancia);
  - sem vinculo, nao se liga o acesso de fora nem se convida a equipe;
  - de fora, as rotas do vinculo sao bloqueadas; desvincular travado, nao.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_e5_vinculo.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-e5-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


class EntradaFalsa:
    """O login do Google de mentira: quem 'entra' e o e-mail de `EntradaFalsa.email`."""

    email = ""
    nome = "Dona do Escritório"
    kwargs: dict = {}

    def __init__(self, provedor, credenciais, ao_concluir, **kw) -> None:
        EntradaFalsa.kwargs = kw
        self.ao_concluir = ao_concluir
        self.fase = "preparando"
        self.mensagem = ""

    def iniciar(self) -> dict:
        import correio_oauth

        try:
            self.ao_concluir("google", {}, EntradaFalsa.email, EntradaFalsa.nome)
            self.fase = "pronto"
        except correio_oauth.ErroOAuth as exc:
            self.fase = "erro"
            self.mensagem = str(exc)
        return self.andamento()

    @property
    def terminou(self) -> bool:
        return self.fase in ("pronto", "erro", "cancelado")

    def cancelar(self) -> None:
        self.fase = "cancelado"

    def andamento(self) -> dict:
        return {"fase": self.fase, "mensagem": self.mensagem, "url": ""}


def test_http() -> None:
    print("\no vinculo, a trava e o destravar")
    from fastapi.testclient import TestClient

    import api
    import vinculo as vinculo_mod
    from acesso.contas import codigo_totp

    vinculo_mod.correio_oauth.Entrada = EntradaFalsa
    v = api.estado.vinculo
    prefs = api.estado.prefs.dados
    local = TestClient(api.app, headers=api.cabecalho_local())

    checar(local.get("/api/vinculo").json()["travado"] is False, "sem vinculo, nada trava")
    checar(local.get("/api/documentos").status_code == 200, "e o programa responde")
    r = local.post("/api/acesso/tunel/conectar", json={"nome": "Escritório", "slug": "escritorio-teste"})
    checar(r.status_code == 400 and "vincule" in r.json().get("detail", ""), "sem vinculo, nao liga o acesso de fora",
           r.text[:160])
    r = local.post("/api/acesso/convites", json={"nome": "X", "email": "x@gmail.com"})
    checar(r.status_code == 400 and "vincule" in r.json().get("detail", ""), "sem vinculo, nao convida a equipe", r.text[:160])

    print("  vincular")
    prefs.setdefault("pessoa", {}).update(nome="", email="")
    EntradaFalsa.email = "dona@gmail.com"
    r = local.post("/api/vinculo/entrar", json={"finalidade": "vincular"})
    e = r.json()
    checar(r.status_code == 200 and e["vinculado"] and e["email"] == "dona@gmail.com" and not e["travado"],
           "vincula e ja fica aberto", e)
    checar(EntradaFalsa.kwargs.get("escopos") == "openid email profile" and EntradaFalsa.kwargs.get("so_identidade"),
           "o login pede so a identidade (nada de e-mail)", EntradaFalsa.kwargs)
    checar(prefs["pessoa"].get("nome") == "Dona do Escritório" and prefs["pessoa"].get("email") == "dona@gmail.com",
           "Meus dados vazios ganham o nome e o e-mail", prefs["pessoa"])
    # o e-mail que havia vira o secundario ao vincular de novo com outra conta
    local.post("/api/vinculo/desvincular")
    prefs["pessoa"].update(email="contato@escritorio.com", email_secundario="")
    local.post("/api/vinculo/entrar", json={"finalidade": "vincular"})
    checar(prefs["pessoa"].get("email") == "dona@gmail.com" and prefs["pessoa"].get("email_secundario") == "contato@escritorio.com",
           "o e-mail de Meus dados vira o do Google, e o antigo vai para o secundario", prefs["pessoa"])

    print("  vincular e ja conectar o Gmail, a Agenda e o Drive, num login so")
    ligados = []
    antes_ligar = v.ligar_servicos
    v.ligar_servicos = lambda tokens, email, nome: ligados.append(email)
    try:
        local.post("/api/vinculo/desvincular")
        r = local.post("/api/vinculo/entrar", json={"finalidade": "vincular", "servicos": True})
        esc = EntradaFalsa.kwargs.get("escopos", "")
        checar(r.status_code == 200 and "https://mail.google.com/" in esc and "calendar.events" in esc and "drive.file" in esc
               and not EntradaFalsa.kwargs.get("so_identidade"), "o mesmo login pede o Gmail, a Agenda e o Drive", esc)
        checar(ligados == ["dona@gmail.com"] and r.json()["vinculado"], "e a conta de e-mail do escritorio nasce junto", ligados)
    finally:
        v.ligar_servicos = antes_ligar

    print("  travado")
    local.post("/api/vinculo/travar")
    r = local.get("/api/documentos")
    checar(r.status_code == 423 and r.headers.get("x-paulus-travado") == "1", "travado: a API responde 423", r.status_code)
    checar(local.post("/api/documentos", json={"titulo": "x"}).status_code == 423, "e gravar tambem")
    checar(local.get("/").status_code == 200 and local.get("/js/45-vinculo.js").status_code == 200,
           "a pagina e os scripts passam (a tela de destravar e desenhada por eles)")
    checar(local.get("/api/vinculo").status_code == 200, "e a rota do vinculo passa")
    EntradaFalsa.email = "outra@gmail.com"
    e = local.post("/api/vinculo/entrar", json={"finalidade": "destravar"}).json()
    checar(e["travado"] and e["fase"] == "erro" and "dona@gmail.com" in e["mensagem"], "outra conta Google: recusada",
           e["mensagem"])
    r = local.post("/api/vinculo/desvincular")
    checar(r.status_code == 400 or r.status_code == 423, "desvincular travado: nao", r.status_code)
    EntradaFalsa.email = "Dona@Gmail.com"
    e = local.post("/api/vinculo/entrar", json={"finalidade": "destravar"}).json()
    checar(not e["travado"] and local.get("/api/documentos").status_code == 200, "a conta vinculada abre", e)

    print("  com o autenticador da titular")
    t = api.estado.acesso_de_fora.contas.criar("Dona", "dona@gmail.com", "titular", "senha-da-dona-12")
    api.estado.acesso_de_fora.contas.confirmar_totp(t["conta"]["id"], codigo_totp(t["segredo"], int(time.time() // 30) - 1))
    local.post("/api/vinculo/travar")
    e = local.post("/api/vinculo/entrar", json={"finalidade": "destravar"}).json()
    checar(e["travado"] and e["precisa_codigo"], "depois do Google, pede o codigo do celular", e)
    checar(local.post("/api/vinculo/codigo", json={"codigo": "000000"}).status_code == 400, "codigo errado: 400")
    r = local.post("/api/vinculo/codigo", json={"codigo": codigo_totp(t["segredo"], int(time.time() // 30))})
    checar(r.status_code == 200 and not r.json()["travado"], "codigo certo: abre", r.text[:160])

    print("  manter aberto, na proxima abertura")
    novo = vinculo_mod.Vinculo(api.estado.prefs, api.estado.acesso_de_fora.contas, lambda: {"client_id": "x"})
    checar(novo.travado(), "abrir de novo (outra instancia): travado")
    local.post("/api/vinculo/manter-aberto", json={"ligado": True})
    novo = vinculo_mod.Vinculo(api.estado.prefs, api.estado.acesso_de_fora.contas, lambda: {"client_id": "x"})
    checar(not novo.travado(), "com 'manter aberto': abre sem pedir o Google")

    print("  sair, no servidor")
    r = local.post("/api/vinculo/travar")
    checar(r.status_code == 200 and r.json()["travado"] and r.json()["saiu"], "sair trava mesmo com 'manter aberto'", r.text[:200])
    checar(local.get("/api/documentos").status_code == 423, "e a janela do servidor para")
    arq = Path(os.environ["PAULUS_DADOS"]) / "pergunta.txt"
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text("contrato de teste", encoding="utf-8")
    rx = local.post("/api/externo/perguntar", json={"caminho": str(arq)})
    checar(rx.status_code == 200, "travado, o 'Perguntar ao PAULUS' do Explorer chega a janela (e nao abre um segundo PAULUS)",
           rx.status_code)
    novo = vinculo_mod.Vinculo(api.estado.prefs, api.estado.acesso_de_fora.contas, lambda: {"client_id": "x"})
    checar(novo.travado(), "fechou e abriu o programa: continua travado (saiu fica gravado)")
    checar("acesso_de_fora" in r.json(), "a tela da trava sabe do acesso de fora")
    import segredos

    if segredos.disponivel():
        # Com a janela do servidor fora da conta, quem entra de fora continua.
        servico = api.estado.acesso_de_fora
        servico.conferir_turnstile = lambda token, ip="": "ok"
        prefs["acesso_remoto"].update(ligado=True, so_google=False)
        try:
            fora = TestClient(api.app, base_url="https://x.paulus.ia.br", headers={"Cf-Connecting-IP": "200.2.2.2"})
            pend = fora.post("/api/acesso/entrar", json={"email": "dona@gmail.com", "senha": "senha-da-dona-12",
                                                         "turnstile": "ok"}).json().get("pendente")
            rc = fora.post("/api/acesso/entrar/codigo", json={"pendente": pend, "codigo": codigo_totp(t["segredo"], int(time.time() // 30) + 1)})
            fora.headers["X-PAULUS-CSRF"] = rc.json().get("csrf", "")
            checar(rc.status_code == 200 and fora.get("/api/documentos").status_code == 200,
                   "de fora, com a janela do servidor travada: entra e usa normalmente", rc.text[:160])
        finally:
            prefs["acesso_remoto"].update(ligado=False, so_google=True)
    EntradaFalsa.email = "dona@gmail.com"
    local.post("/api/vinculo/entrar", json={"finalidade": "destravar"})
    # os codigos do celular desta janela de tempo ja foram usados: vai um de recuperacao
    r = local.post("/api/vinculo/codigo", json={"codigo": t["codigos_recuperacao"][0]})
    checar(r.status_code == 200 and not r.json()["travado"] and not r.json()["saiu"], "entrar de novo abre e limpa o 'saiu'",
           r.text[:160])
    novo = vinculo_mod.Vinculo(api.estado.prefs, api.estado.acesso_de_fora.contas, lambda: {"client_id": "x"})
    checar(not novo.travado(), "e o 'manter aberto' volta a valer")

    print("  de fora")
    import segredos

    if segredos.disponivel():
        prefs["acesso_remoto"]["ligado"] = True
        try:
            fora = TestClient(api.app, base_url="https://x.paulus.ia.br")
            checar(fora.get("/api/vinculo").status_code == 401, "de fora, sem sessao: 401")
        finally:
            prefs["acesso_remoto"]["ligado"] = False
    r = local.post("/api/vinculo/desvincular")
    checar(r.status_code == 200 and not r.json()["vinculado"], "desvincular (aberto): sim")


def main() -> int:
    print("=" * 55)
    print("  E5 - o PAULUS do servidor vinculado a conta Google")
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
