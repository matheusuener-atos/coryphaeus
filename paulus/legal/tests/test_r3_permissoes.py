"""
Portao da R3 - o que cada rota permite a quem esta de fora
(src/acesso/politicas.py e remoto.py).

  - percorre `app.routes` e FALHA se alguma rota nao tiver politica declarada
    - rota nova nasce bloqueada, e este teste obriga alguem a decidir;
  - o registro nao guarda politica de rota que nao existe mais;
  - cada linha da tabela do contrato (acesso-remoto/v0, §5) e testada com
    sessao remota de colaborador e de titular:
      conversar e ver documento .............. permitido
      agenda, tarefas, cadastros ............. ver; o colaborador propoe (vira
                                                pedido na fila); o titular faz (E2)
      editor ................................. redigir e salvar rascunho
      aprovar ................................ so titular; o que sai daqui
                                                pede o codigo de novo; o que
                                                e so do escritorio, nem assim
      baixar um documento .................... um por vez, registrado
      exportar em lote ....................... bloqueado
      assinar ................................ bloqueado
      mover, organizar, apagar, lixeira ...... bloqueado
      configuracoes, contas, o proprio acesso  bloqueado
      modelos, atualizacao ................... bloqueado
      e-mail: configurar / usar .............. bloqueado / permitido, e enviar
                                                vai sempre para a fila
      /api/externo e o que abre programa ..... bloqueado

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_r3_permissoes.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-r3-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def test_todas_declaradas() -> None:
    print("\ntoda rota tem politica declarada")
    import api
    from acesso import politicas

    faltam, pares = [], set()
    for r in api.app.routes:
        if not hasattr(r, "path") or not getattr(r, "methods", None):
            continue
        for m in r.methods:
            if m == "HEAD":
                continue
            pares.add((m, r.path))
            if (m, r.path) not in politicas.REGISTRO:
                faltam.append(f"{m} {r.path}")
    checar(not faltam, f"{len(pares)} pares metodo+rota, todos com politica", faltam[:12])
    sobrando = sorted(f"{m} {p}" for (m, p) in politicas.REGISTRO if (m, p) not in pares)
    checar(not sobrando, "o registro nao tem rota que nao existe", sobrando[:12])
    checar(all(v in politicas.POLITICAS for v in politicas.REGISTRO.values()), "so politicas conhecidas")
    checar(politicas.de("GET", "/rota/nova/sem/declaracao") == politicas.BLOQUEADO, "rota sem declaracao e bloqueada")


class Fora:
    """Um navegador de fora, com sessao do PAULUS e o token anti-CSRF."""

    def __init__(self, api, email: str, senha: str, segredo: str) -> None:
        from fastapi.testclient import TestClient

        from acesso.contas import codigo_totp

        self.c = TestClient(api.app, base_url="https://escritorio.paulus.ia.br",
                            headers={"Cf-Connecting-IP": "200.1.2.3"})
        pend = self.c.post("/api/acesso/entrar", json={"email": email, "senha": senha, "turnstile": "ok"}).json()["pendente"]
        r = self.c.post("/api/acesso/entrar/codigo",
                        json={"pendente": pend, "codigo": codigo_totp(segredo, int(time.time() // 30))})
        self.csrf = r.json()["csrf"]
        self.segredo = segredo

    def get(self, url, **k):
        return self.c.get(url, **k)

    def post(self, url, **k):
        return self.c.post(url, headers={"X-PAULUS-CSRF": self.csrf}, **k)

    def delete(self, url, **k):
        return self.c.delete(url, headers={"X-PAULUS-CSRF": self.csrf}, **k)


def _contas(api):
    from acesso.contas import codigo_totp

    contas = api.estado.acesso_de_fora.contas
    passo = int(time.time() // 30) - 1
    t = contas.criar("Tereza Titular", "tereza@escritorio.com", "titular", "senha-da-tereza-1")
    contas.confirmar_totp(t["conta"]["id"], codigo_totp(t["segredo"], passo))
    c = contas.criar("Caio Colaborador", "caio@escritorio.com", "colaborador", "senha-do-caio-1")
    contas.confirmar_totp(c["conta"]["id"], codigo_totp(c["segredo"], passo))
    return t, c


def test_tabela() -> None:
    print("\na tabela do contrato, de fora, com colaborador e titular")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI (fora do Windows), o acesso de fora fica indisponivel")
        return
    from fastapi.testclient import TestClient

    import api

    servico = api.estado.acesso_de_fora
    servico.conferir_turnstile = lambda token, ip="": "ok" if token == "ok" else "recusado"
    api.estado.prefs.dados["acesso_remoto"]["ligado"] = True
    # entra por senha para testar outra coisa: a regra "so Google" fica de lado
    api.estado.prefs.dados["acesso_remoto"]["so_google"] = False
    local = TestClient(api.app, headers=api.cabecalho_local())
    try:
        t, c = _contas(api)
        titular = Fora(api, "tereza@escritorio.com", "senha-da-tereza-1", t["segredo"])
        colab = Fora(api, "caio@escritorio.com", "senha-do-caio-1", c["segredo"])
        ambos = (("colaborador", colab), ("titular", titular))

        # conversar, perguntar, ver documento
        for quem, f in ambos:
            r = f.post("/api/trabalhos", json={"pedido": "conversa de fora"})
            checar(r.status_code == 200 and r.json().get("id"), f"{quem}: conversar (criar conversa)", r.status_code)
            checar(f.get("/api/biblioteca").status_code == 200, f"{quem}: ver o acervo")
            checar(f.get("/api/status").status_code == 200, f"{quem}: o estado do programa")

        # agenda, tarefas, cadastros: o colaborador ve e propoe (o padrao);
        # o titular faz direto (E2, docs/PLANO-EQUIPE.md: o titular tem o
        # maior nivel de cada modulo - propor para ele mesmo aprovar nao
        # fazia sentido)
        antes = len(api.estado.tarefas.listar("todas"))
        pedidos_antes = len(api.estado.fila.pendentes)
        for quem, f in ambos:
            checar(f.get("/api/agenda").status_code == 200 and f.get("/api/tarefas").status_code == 200,
                   f"{quem}: ver agenda e tarefas")
        r = colab.post("/api/tarefas", json={"id": None, "dados": {"titulo": "Tarefa proposta por colaborador"}})
        checar(r.status_code == 202 and r.json().get("proposto"), "colaborador: criar tarefa vira proposta (202)", r.text[:200])
        checar(len(api.estado.fila.pendentes) == pedidos_antes + 1, "a proposta esta na fila de Aprovacoes")
        checar(len(api.estado.tarefas.listar("todas")) == antes, "e nenhuma tarefa foi gravada direto")
        r = titular.post("/api/tarefas", json={"id": None, "dados": {"titulo": "Tarefa gravada pelo titular"}})
        checar(r.status_code == 200 and not r.json().get("proposto"), "titular: criar tarefa grava direto", r.text[:200])
        checar(len(api.estado.tarefas.listar("todas")) == antes + 1, "e a tarefa do titular existe")
        proposta = [p for p in api.estado.fila.pendentes if p.acao == "acesso.proposta"][-1]
        checar("Caio" in proposta.pedido_por, "o pedido diz quem propos", proposta.pedido_por)

        # editor
        for quem, f in ambos:
            r = f.post("/api/documentos", json={"titulo": "Minuta de " + quem, "tipo": "texto"})
            checar(r.status_code == 200, f"{quem}: redigir no editor", r.text[:160])
        doc_id = r.json().get("id")

        # aprovar: so o titular
        r = colab.post("/api/aprovacoes/decidir", json={"ids": [proposta.id], "aprovar": True})
        checar(r.status_code == 403, "colaborador: aprovar e recusado", r.status_code)
        r = titular.post("/api/aprovacoes/decidir", json={"ids": [proposta.id], "aprovar": True})
        feito = (r.json().get("feitos") or [{}])[0] if r.status_code == 200 else {}
        checar(r.status_code == 200 and feito.get("estado") == "aprovado", "titular: aprovar executa a proposta", r.text[:300])
        titulos = [x.get("titulo") for x in local.get("/api/tarefas?filtro=todas").json().get("tarefas", [])]
        checar(any("proposta por" in (x or "") for x in titulos), "e a tarefa proposta existe depois do sim", titulos[:5])

        # o que sai daqui pede o codigo de novo; o que e so do escritorio nao sai de fora
        enviados = []
        api.EXECUTORES["correio.enviar"], antes_exec = (lambda p: enviados.append(p.id) or "enviado"), api.EXECUTORES["correio.enviar"]
        try:
            sai = api.estado.fila.pedir("Enviar e-mail de teste", "email", acao="correio.enviar", dados={})
            r = titular.post("/api/aprovacoes/decidir", json={"ids": [sai.id], "aprovar": True})
            falha = (r.json().get("falhas") or [{}])[0]
            checar(not enviados and "código" in falha.get("motivo", ""), "sai daqui: sem o codigo do autenticador, nao aprova", r.text[:300])
            from acesso.contas import codigo_totp

            codigo = codigo_totp(titular.segredo, int(time.time() // 30) + 1)
            r = titular.post("/api/aprovacoes/decidir", json={"ids": [sai.id], "aprovar": True, "codigo": codigo})
            checar(enviados == [sai.id], "com o codigo, aprova e executa", r.text[:300])
        finally:
            api.EXECUTORES["correio.enviar"] = antes_exec
        mover = api.estado.fila.pedir("Mover 3 arquivos", "organizar", acao="organizar.mover", dados={})
        r = titular.post("/api/aprovacoes/decidir", json={"ids": [mover.id], "aprovar": True})
        falha = (r.json().get("falhas") or [{}])[0]
        checar(api.estado.fila.obter(mover.id).estado == "pendente" and "escritório" in falha.get("motivo", ""),
               "mover arquivos nao se aprova de fora, nem pelo titular", r.text[:300])

        # baixar UM documento: permitido e registrado
        for quem, f in ambos:
            eventos = len(servico.eventos)
            r = f.get(f"/api/documentos/{doc_id}/docx")
            checar(r.status_code == 200, f"{quem}: baixar um documento", r.status_code)
            checar(any(e.get("acao") == "download" for e in servico.eventos[eventos:]), f"{quem}: o download ficou registrado")

        bloqueadas = [
            ("exportar em lote", "post", "/api/biblioteca/lote/exportar", {"caminhos": []}),
            ("assinar", "post", "/api/assinar", {}),
            ("mover arquivos", "post", "/api/biblioteca/lote/mover", {"caminhos": []}),
            ("apagar arquivos", "post", "/api/biblioteca/lote/apagar", {"caminhos": []}),
            ("esvaziar a lixeira", "post", "/api/lixeira/esvaziar", {}),
            ("configuracoes", "post", "/api/preferencias", {}),
            ("contas", "post", "/api/acesso/contas", {"nome": "x", "email": "x@x.com", "senha": "0123456789"}),
            ("baixar modelo", "post", "/api/modelos/baixar", {"nome": "llama3.2:3b"}),
            ("atualizar", "post", "/api/atualizacao/instalar", {}),
            ("configurar e-mail", "post", "/api/email/contas", {}),
            ("pedido externo", "post", "/api/externo/perguntar", {"caminho": "C:/x.pdf"}),
            ("abrir no Windows", "post", "/api/arquivos/abrir", {"caminho": "C:/x.pdf"}),
        ]
        for quem, f in ambos:
            for rotulo, metodo, url, corpo in bloqueadas:
                r = getattr(f, metodo)(url, json=corpo)
                checar(r.status_code == 403 and "escritório" in r.text, f"{quem}: {rotulo} bloqueado", (r.status_code, r.text[:100]))
            checar(f.get("/api/email/envios").status_code == 200, f"{quem}: usar o e-mail ja configurado")
    finally:
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = False
        api.estado.prefs.dados["acesso_remoto"]["so_google"] = True
        servico.__dict__.pop("conferir_turnstile", None)


def test_email_sempre_pela_fila() -> None:
    print("\nde fora, e-mail vai sempre para a fila")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI")
        return
    import api
    from types import SimpleNamespace

    servico = api.estado.acesso_de_fora
    servico.conferir_turnstile = lambda token, ip="": "ok" if token == "ok" else "recusado"
    api.estado.prefs.dados["acesso_remoto"]["ligado"] = True
    # entra por senha para testar outra coisa: a regra "so Google" fica de lado
    api.estado.prefs.dados["acesso_remoto"]["so_google"] = False
    conta = SimpleNamespace(id="c1", email="escritorio@x.com", por_login=False, pode_enviar_sem_confirmar=True,
                            autenticacao="senha")
    antes_montar, antes_cred = api._montar_do_pedido, api.estado.contas.tem_credencial
    antes_aut = dict(api.estado.prefs.dados["autonomia"])
    api._montar_do_pedido = lambda payload: (conta, None, ["cliente@x.com"])
    api.estado.contas.tem_credencial = lambda c: True
    api.estado.prefs.dados["autonomia"]["enviar_mensagem"] = True
    try:
        from acesso.contas import codigo_totp

        contas = servico.contas
        e = contas.criar("Edu", "edu@escritorio.com", "colaborador", "senha-do-edu-12")
        contas.confirmar_totp(e["conta"]["id"], codigo_totp(e["segredo"], int(time.time() // 30) - 1))
        f = Fora(api, "edu@escritorio.com", "senha-do-edu-12", e["segredo"])
        r = f.post("/api/email/enviar", json={"para": "cliente@x.com", "assunto": "a", "corpo": "b"})
        checar(r.status_code == 200 and r.json().get("aguardando_aprovacao") is True,
               "com 'enviar sem confirmar' ligado, de fora vai para a fila mesmo assim", r.text[:200])
        r = f.post("/api/email/enviar", json={"para": "cliente@x.com", "assunto": "a", "corpo": "b", "senha": "x"})
        checar(r.status_code == 403, "de fora nao se entrega senha de e-mail", r.status_code)
    finally:
        api._montar_do_pedido, api.estado.contas.tem_credencial = antes_montar, antes_cred
        api.estado.prefs.dados["autonomia"] = antes_aut
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = False
        api.estado.prefs.dados["acesso_remoto"]["so_google"] = True
        servico.__dict__.pop("conferir_turnstile", None)


def main() -> int:
    print("=" * 55)
    print("  R3 - permissoes por rota, padrao nega")
    print("=" * 55)
    try:
        test_todas_declaradas()
        test_tabela()
        test_email_sempre_pela_fila()
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
