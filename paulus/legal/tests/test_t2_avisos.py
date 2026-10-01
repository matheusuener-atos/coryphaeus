"""
Portao da T2 - carrossel de avisos, Central de avisos e historico
(src/central_avisos.py, src/rotas_avisos.py, frontend/js/53-avisos.js).

Numa pasta de dados temporaria (PAULUS_DADOS), com um exemplo de cada fonte
- prazo processual (lista Prazos), tarefa, compromisso, conta a pagar e a
receber, publicacao nova do DJEN, data de documento do Acervo, aprovacao
esperando, conversa pela metade e lembrete do Vigia vencido:

  - o carrossel mostra os avisos na ordem (atrasado -> hoje -> amanha ->
    esta semana; no mesmo dia, prazo processual primeiro);
  - o mesmo prazo na Agenda e em Tarefas e um aviso so;
  - marcar como visto tira o aviso, cria a linha do historico com pessoa e
    hora, e desmarcar devolve;
  - prazo visto ontem ("vence amanha") volta no dia ("vence hoje");
  - com duas contas, o visto de uma nao esconde o da outra, e o titular ve
    os dois no historico;
  - marcar pelo acesso de fora registra "remoto" (e quem nao ve o
    Financeiro nao recebe aviso de conta);
  - o Vigia usa o mesmo id e nao avisa de novo o que foi visto;
  - com a chave desligada, as rotas dizem {ligado: false};
  - na tela (Edge, pacote de telas de 01/10/2026): o resumo em tres
    cartoes com as contas do servidor, o vinho so nos atrasados, "ver N"
    abre o painel no lugar da lista, marcar tira o aviso e cria o
    historico, a Central com os tipos e os periodos, desmarcar devolve, em
    390 px os cartoes empilham com o circulo de 44 px, sem avisos nao
    aparece.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_t2_avisos.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-t2-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

CAPTURAS = Path(r"C:\Users\MATHEU~1\AppData\Local\Temp\claude\c--coryphaeus\7b88221c-3b6c-4588-bbbd-a113e4c3118c\scratchpad")

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


H = date.today()


def d(n: int) -> str:
    return (H + timedelta(days=n)).isoformat()


def _exemplo(api) -> dict:
    """Um exemplo de cada fonte, direto nos objetos que as telas usam."""
    e = api.estado
    ids: dict = {}
    # O lembrete so vale no horario de trabalho: aqui, o dia inteiro, todo dia.
    e.prefs.dados["disponibilidade"] = {**(e.prefs.dados.get("disponibilidade") or {}),
                                        "dias": [0, 1, 2, 3, 4, 5, 6], "inicio": "00:00", "fim": "23:59"}
    e.prefs.dados["pessoa"] = {**(e.prefs.dados.get("pessoa") or {}), "nome": "Helena Duarte"}
    ids["replica"] = e.tarefas.salvar({"titulo": "Réplica — processo 7654321-00", "prazo": d(-2), "lista": "Prazos"})
    ids["contestacao"] = e.tarefas.salvar({"titulo": "Contestação — processo 1234567-89", "prazo": d(0), "lista": "Prazos"})
    ids["ligar"] = e.tarefas.salvar({"titulo": "Ligar para a Rio Fresco", "prazo": d(0)})
    ids["futura"] = e.tarefas.salvar({"titulo": "Revisar minuta do aditivo", "prazo": d(3)})
    ids["recurso"] = e.tarefas.salvar({"titulo": "Recurso — processo 5550001-11", "prazo": d(3), "lista": "Prazos"})
    # O mesmo prazo tambem posto na Agenda, com o mesmo nome e o mesmo dia.
    ids["recurso_agenda"] = e.agenda.salvar({"titulo": "Recurso — processo 5550001-11", "data": d(3), "hora": "09:00"})
    ids["reuniao"] = e.agenda.salvar({"titulo": "Reunião com a Rio Fresco", "data": d(1), "hora": "10:00", "onde": "escritorio"})
    ids["aluguel"] = e.financeiro.salvar({"tipo": "despesa", "descricao": "Aluguel do escritório", "valor": "3200",
                                          "vencimento": d(2), "categoria": "aluguel"})
    ids["honorarios"] = e.financeiro.salvar({"tipo": "recebimento", "descricao": "Honorários João Batista",
                                             "valor": "1500", "vencimento": d(-1)})
    e.publicacoes.guardar([{"id_externo": "t2-pub-1", "data": d(-1), "tribunal": "TJGO", "tipo": "Intimação",
                            "orgao": "3ª Vara Cível", "classe": "", "processo": "0001234-56.2026.8.09.0051",
                            "texto": "Fica intimada a parte...", "link": "", "oab": "GO 12345"}])
    ids["publicacao"] = e.publicacoes.listar("novas")[0]["id"]
    e.central_avisos.classificados = lambda: [{"nome": "Contrato ACME.pdf", "data": d(5), "sha1": "t2sha1acme",
                                               "tipo_rotulo": "Contrato", "cliente": "ACME Ltda"}]
    ids["aprovacao"] = e.fila.pedir("Enviar a notificação à ACME", "email", acao="t2.teste", dados={}).id
    t = e.trabalhos.criar("Notificação da Rio Fresco", estado="pausado")
    ids["conversa"] = t.id
    ids["lembrete"] = e.bem_estar.salvar_lembrete({"titulo": "Beber água", "cada_min": 60})
    # Duas horas antes do mais cedo entre agora e as 11h de hoje (a hora do
    # test_modulo): depois do meio-dia, "agora - 2 h" ainda nao venceu as 11h.
    feito = (min(datetime.now(), datetime.combine(H, datetime.min.time()).replace(hour=11))
             - timedelta(hours=2)).isoformat(timespec="seconds")
    e.base.escrever("UPDATE lembretes SET ultima_vez = ? WHERE id = ?", (feito, ids["lembrete"]))
    return ids


def test_modulo(api, ids) -> None:
    print("\no modulo (src/central_avisos.py), com o relogio passado de fora")
    c = api.estado.central_avisos
    agora = datetime.combine(H, datetime.min.time()).replace(hour=11)
    lista = c.do_dia("local", hoje=H, agora=agora)
    checar(not c.falhas, "nenhuma fonte falhou", c.falhas)
    tipos = {a["tipo"] for a in lista}
    checar(tipos == set(("prazo compromisso vencimento a_pagar a_receber tarefa publicacao pendencia rotina").split()),
           "um aviso de cada fonte: os nove tipos", sorted(tipos))
    titulos = [a["titulo"] for a in lista]
    esperado_inicio = ["Réplica — processo 7654321-00", "Honorários João Batista — R$ 1.500,00",
                       "Contestação — processo 1234567-89", "Ligar para a Rio Fresco"]
    checar(titulos[:4] == esperado_inicio, "atrasado primeiro (o mais antigo antes), depois hoje com o prazo processual na frente",
           titulos[:5])
    grupos = [a["grupo"] for a in lista]
    ordem = ["atrasado", "hoje", "amanha", "semana"]
    checar(grupos == sorted(grupos, key=ordem.index), "a ordem: atrasado -> hoje -> amanhã -> esta semana", grupos)
    checar(titulos[-4:] == ["Reunião com a Rio Fresco", "Aluguel do escritório — R$ 3.200,00",
                            "Recurso — processo 5550001-11", "Conferir prazo — Contrato ACME.pdf"],
           "amanhã e a semana, pela data", titulos[-4:])
    checar("Revisar minuta do aditivo" not in titulos, "tarefa comum de daqui a 3 dias não entra no carrossel (só do dia ou atrasada)")
    por = {a["titulo"]: a for a in lista}
    checar(por["Reunião com a Rio Fresco"]["quando"] == "amanhã às 10:00", "compromisso: 'amanhã às 10:00'",
           por["Reunião com a Rio Fresco"]["quando"])
    checar(por["Réplica — processo 7654321-00"]["quando"] == "atrasado há 2 dias", "prazo: 'atrasado há 2 dias'")
    checar(por["Contestação — processo 1234567-89"]["quando"] == "vence hoje", "prazo: 'vence hoje'")
    checar(por["Recurso — processo 5550001-11"]["quando"] == "em 3 dias", "prazo: 'em 3 dias'")
    checar(por["Contestação — processo 1234567-89"]["id"] == f"prazo:{ids['contestacao']}:{d(0)}",
           "id estável pela origem: prazo:<id>:<data>", por["Contestação — processo 1234567-89"]["id"])
    checar(por["Aluguel do escritório — R$ 3.200,00"]["id"] == f"pagar:{ids['aluguel']}:{d(2)}:antes",
           "antes do dia, o id ganha ':antes'", por["Aluguel do escritório — R$ 3.200,00"]["id"])
    checar(all(a["destaque"] == (a["dias"] < 0 or (a["dias"] == 0 and a["tipo"] not in ("publicacao", "pendencia", "rotina")))
               for a in lista), "destaque só no atrasado e no que vence hoje")
    acoes = {x["id"] for a in lista for x in a["acoes"]}
    checar(acoes == {"concluir", "liquidar"}, "ações diretas: concluir tarefa e marcar como pago/recebido", acoes)
    checar(all(x["rota"].startswith(("/api/tarefas/", "/api/financeiro/lancamentos/")) for a in lista for x in a["acoes"]),
           "as ações chamam as rotas da tela de origem")
    checar(all(a["destino"].get("tela") for a in lista), "todo aviso diz a tela e o item a abrir")

    print("\nsem duplicado")
    recurso = [a for a in c.todos("local", hoje=H, agora=agora) if a["titulo"].startswith("Recurso")]
    checar(len(recurso) == 1 and recurso[0]["id"].startswith(f"prazo:{ids['recurso']}:"),
           "o mesmo prazo na Agenda e em Tarefas aparece uma vez só", [a["id"] for a in recurso])
    checar("Agenda" in recurso[0]["origem"], "e o aviso diz que está nos dois lugares", recurso[0]["origem"])

    print("\nmarcar como visto e desmarcar")
    alvo = por["Contestação — processo 1234567-89"]["id"]
    visto = c.marcar(alvo, "local", nome="Helena Duarte", de_onde="local", hoje=H, agora=agora)
    depois = [a["id"] for a in c.do_dia("local", hoje=H, agora=agora)]
    checar(alvo not in depois and len(depois) == len(lista) - 1, "marcado, sai do carrossel")
    h = [l for l in c.historico("local") if l["aviso_id"] == alvo]
    checar(len(h) == 1 and h[0]["pessoa"] == "local" and h[0]["pessoa_nome"] == "Helena Duarte"
           and h[0]["visto_em"] == agora.isoformat(timespec="seconds"),
           "a linha do histórico tem pessoa e hora", h[:1])
    checar(h and h[0]["titulo"] == visto["titulo"] and h[0]["quando"] == "vence hoje" and h[0]["de_onde"] == "local",
           "e a cópia do que o aviso dizia", h[:1])
    tarefa = api.estado.tarefas.obter(ids["contestacao"])
    checar(not tarefa["concluida"], "visto não conclui a tarefa")
    checar(c.desmarcar(alvo, "local") and alvo in [a["id"] for a in c.do_dia("local", hoje=H, agora=agora)],
           "desmarcar apaga a linha e o aviso volta")
    checar(not [l for l in c.historico("local") if l["aviso_id"] == alvo], "e sai do histórico")
    try:
        c.marcar("prazo:999999:2020-01-01", "local", hoje=H, agora=agora)
        checar(False, "id inventado não se marca")
    except LookupError:
        checar(True, "id inventado não se marca")

    print("\nprazo visto ontem volta no dia do vencimento")
    ontem = H - timedelta(days=1)
    ontem_lista = c.do_dia("local", hoje=ontem)
    aviso_ontem = next(a for a in ontem_lista if a["titulo"].startswith("Contestação"))
    checar(aviso_ontem["quando"] == "vence amanhã" and aviso_ontem["id"].endswith(":antes"),
           "ontem: 'vence amanhã', com id de antes", aviso_ontem["id"])
    c.marcar(aviso_ontem["id"], "local", nome="Helena Duarte", hoje=ontem)
    checar(not any(a["titulo"].startswith("Contestação") for a in c.do_dia("local", hoje=ontem)), "visto ontem, some ontem")
    hoje_lista = c.do_dia("local", hoje=H, agora=agora)
    volta = [a for a in hoje_lista if a["titulo"].startswith("Contestação")]
    checar(len(volta) == 1 and volta[0]["quando"] == "vence hoje" and volta[0]["id"] == alvo,
           "hoje volta ao carrossel como aviso novo ('vence hoje')", [a["id"] for a in volta])
    c.desmarcar(aviso_ontem["id"], "local")

    print("\nduas contas: cada pessoa com os próprios vistos")
    c.marcar(alvo, "conta:1", nome="Caio Colaborador", de_onde="remoto", hoje=H, agora=agora)
    checar(alvo not in [a["id"] for a in c.do_dia("conta:1", hoje=H, agora=agora)], "a conta 1 não vê mais o que marcou")
    checar(alvo in [a["id"] for a in c.do_dia("conta:2", hoje=H, agora=agora)], "a conta 2 continua vendo")
    checar(alvo in [a["id"] for a in c.do_dia("local", hoje=H, agora=agora)], "e a janela do escritório também")
    c.marcar(alvo, "local", nome="Helena Duarte", hoje=H, agora=agora)
    do_titular = {(l["aviso_id"], l["pessoa"]) for l in c.historico("local", titular=True)}
    checar({(alvo, "conta:1"), (alvo, "local")} <= do_titular, "o titular vê os dois no histórico", do_titular)
    so_dele = {l["pessoa"] for l in c.historico("conta:2")}
    checar(not so_dele, "a conta 2 não vê o visto dos outros", so_dele)
    checar(not c.desmarcar(alvo, "conta:2"), "e não desmarca o visto de outra pessoa")
    c.desmarcar(alvo, "conta:1")
    c.desmarcar(alvo, "local")


def test_vigia(api, ids) -> None:
    print("\no Vigia: o mesmo id, e o visto não volta como notificação")
    import avisos

    e = api.estado
    mandados = []
    antes = avisos.notificar
    avisos.notificar = lambda titulo, texto, **k: mandados.append(titulo) or True
    comeca = (datetime.now() + timedelta(minutes=10)).replace(second=0, microsecond=0)
    if comeca.date() != H:
        print("  pulado: perto da meia-noite, o compromisso de daqui a 10 min cai amanhã")
        avisos.notificar = antes
        return
    cid = e.agenda.salvar({"titulo": "Audiência de conciliação", "data": H.isoformat(), "hora": comeca.strftime("%H:%M")})
    antes_prefs = dict(e.prefs.dados.get("conversa") or {})
    e.prefs.dados["conversa"] = {**antes_prefs, "avisos": True}
    try:
        agora = datetime.now()
        vigia = avisos.Vigia(e.bem_estar, e.prefs, agenda=e.agenda)
        vigia.visto = e.vigia.visto
        vigia._olhar_agenda(agora)
        esperado = f"compromisso:{cid}:{H.isoformat()}"
        checar(vigia.ids_avisados == [esperado], "a notificação usa o id da central", vigia.ids_avisados)
        central = [a["id"] for a in e.central_avisos.do_dia("local")]
        checar(esperado in central, "e o cartão tem o mesmo id")
        e.central_avisos.marcar(esperado, "local", nome="Helena Duarte")
        outro = avisos.Vigia(e.bem_estar, e.prefs, agenda=e.agenda)
        outro.visto = e.vigia.visto
        mandados.clear()
        outro._olhar_agenda(agora)
        checar(not mandados and not outro.ids_avisados, "visto no cartão, o Vigia não notifica", mandados)
        # o lembrete vencido: mesmo id no cartao e no Vigia
        rotina = next(a for a in e.central_avisos.do_dia("local") if a["tipo"] == "rotina")
        mandados.clear()
        vigia.desde = datetime.now() - timedelta(hours=3)
        vigia.ids_avisados = []
        e.prefs.dados.setdefault("avisos_tipos", {})
        vigia.olhar()
        checar(rotina["id"] in vigia.ids_avisados, "o lembrete vencido: o Vigia e o cartão com o mesmo id",
               (rotina["id"], vigia.ids_avisados))
        e.central_avisos.marcar(rotina["id"], "local", nome="Helena Duarte")
        terceiro = avisos.Vigia(e.bem_estar, e.prefs, agenda=e.agenda)
        terceiro.visto = e.vigia.visto
        terceiro.desde = datetime.now() - timedelta(hours=3)
        mandados.clear()
        terceiro.olhar()
        checar("Beber água" not in mandados, "lembrete visto não volta como notificação", mandados)
        e.central_avisos.desmarcar(rotina["id"], "local")
        e.prefs.dados["conversa"] = {**antes_prefs, "avisos": False}
        mandados.clear()
        terceiro.compromissos_avisados.clear()
        terceiro._olhar_agenda(agora)
        checar(mandados == ["Audiência de conciliação"], "com a chave desligada, o Vigia avisa como antes", mandados)
    finally:
        avisos.notificar = antes
        e.prefs.dados["conversa"] = antes_prefs
        e.central_avisos.desmarcar(f"compromisso:{cid}:{H.isoformat()}", "local")
        e.agenda.apagar(cid)


class Fora:
    """Um navegador de fora, com sessao do PAULUS e o token anti-CSRF (como em test_r3_permissoes)."""

    def __init__(self, api, email: str, senha: str, segredo: str) -> None:
        from fastapi.testclient import TestClient

        from acesso.contas import codigo_totp

        self.c = TestClient(api.app, base_url="https://escritorio.paulus.ia.br",
                            headers={"Cf-Connecting-IP": "200.1.2.3"})
        pend = self.c.post("/api/acesso/entrar", json={"email": email, "senha": senha, "turnstile": "ok"}).json()["pendente"]
        r = self.c.post("/api/acesso/entrar/codigo",
                        json={"pendente": pend, "codigo": codigo_totp(segredo, int(time.time() // 30))})
        self.csrf = r.json()["csrf"]

    def get(self, url, **k):
        return self.c.get(url, **k)

    def post(self, url, **k):
        return self.c.post(url, headers={"X-PAULUS-CSRF": self.csrf}, **k)


def test_api(api, ids) -> None:
    print("\npela API: a chave, a janela local e o acesso de fora")
    from fastapi.testclient import TestClient

    import segredos
    from acesso.contas import codigo_totp

    e = api.estado
    local = TestClient(api.app, headers=api.cabecalho_local())
    antes = dict(e.prefs.dados.get("conversa") or {})
    e.prefs.dados["conversa"] = {**antes, "avisos": False}
    r = local.get("/api/central-avisos/hoje").json()
    checar(r == {"ligado": False, "avisos": []}, "chave desligada: {ligado: false} e nenhum aviso", r)
    checar(local.post("/api/central-avisos/visto", json={"id": "x"}).status_code == 404, "e marcar não grava nada")
    e.prefs.dados["conversa"] = {**antes, "avisos": True}
    hoje = local.get("/api/central-avisos/hoje").json()
    checar(hoje["ligado"] and len(hoje["avisos"]) >= 11, "chave ligada: o carrossel pela rota", len(hoje["avisos"]))
    todos = local.get("/api/central-avisos?periodo=semana&tipo=tarefa").json()
    checar({a["tipo"] for a in todos["avisos"]} == {"tarefa"} and
           any(a["titulo"] == "Revisar minuta do aditivo" for a in todos["avisos"]),
           "Todos com filtro de tipo e período (a tarefa de daqui a 3 dias aparece)", [a["titulo"] for a in todos["avisos"]])
    so_hoje = local.get("/api/central-avisos?periodo=hoje").json()["avisos"]
    checar(all(a["dias"] <= 0 for a in so_hoje), "período 'hoje' só traz atrasado e hoje")
    alvo = next(a["id"] for a in hoje["avisos"] if a["titulo"].startswith("Ligar"))
    r = local.post("/api/central-avisos/visto", json={"id": alvo})
    checar(r.status_code == 200 and alvo not in [a["id"] for a in r.json()["avisos"]], "marcar pela rota devolve o carrossel sem ele")
    h = local.get("/api/central-avisos/historico").json()
    linha = next((l for l in h["itens"] if l["aviso_id"] == alvo), {})
    checar(linha.get("de_onde") == "local" and linha.get("pessoa") == "local" and linha.get("pessoa_nome") == "Helena Duarte",
           "da janela do escritório: 'local', com o nome de Meus dados", linha)
    local.post("/api/central-avisos/desmarcar", json={"id": alvo})

    if not segredos.disponivel():
        print("  pulado: sem DPAPI (fora do Windows), o acesso de fora fica indisponivel")
        return
    servico = e.acesso_de_fora
    servico.conferir_turnstile = lambda token, ip="": "ok" if token == "ok" else "recusado"
    e.prefs.dados["acesso_remoto"]["ligado"] = True
    e.prefs.dados["acesso_remoto"]["so_google"] = False
    contas = servico.contas
    passo = int(time.time() // 30) - 1
    t = contas.criar("Tereza Titular", "tereza@escritorio.com", "titular", "senha-da-tereza-1")
    contas.confirmar_totp(t["conta"]["id"], codigo_totp(t["segredo"], passo))
    c = contas.criar("Caio Colaborador", "caio@escritorio.com", "colaborador", "senha-do-caio-1")
    contas.confirmar_totp(c["conta"]["id"], codigo_totp(c["segredo"], passo))
    titular = Fora(api, "tereza@escritorio.com", "senha-da-tereza-1", t["segredo"])
    colab = Fora(api, "caio@escritorio.com", "senha-do-caio-1", c["segredo"])

    r = colab.get("/api/central-avisos/hoje")
    avisos_colab = r.json().get("avisos", []) if r.status_code == 200 else []
    checar(r.status_code == 200 and avisos_colab, "de fora, o colaborador lê o carrossel (PERMITIDO)", r.status_code)
    tipos_colab = {a["tipo"] for a in avisos_colab}
    checar(not tipos_colab & {"a_pagar", "a_receber", "publicacao", "rotina"},
           "quem não vê Financeiro, DJEN e Foco não recebe esses avisos", sorted(tipos_colab))
    checar(not any(a["tipo"] == "pendencia" and a["destino"].get("tela") == "aprovacoes" for a in avisos_colab),
           "nem aprovação, que ele só vê e não decide")
    concluir = [x for a in avisos_colab for x in a["acoes"] if x["id"] == "concluir"]
    checar(concluir and all(x["propoe"] for x in concluir), "a ação direta dele é propor (a política da rota de origem)")
    alvo = next(a["id"] for a in avisos_colab if a["tipo"] == "prazo")
    r = colab.post("/api/central-avisos/visto", json={"id": alvo})
    checar(r.status_code == 200, "de fora, marcar como visto é permitido", r.text[:200])
    linha = next((l for l in local.get("/api/central-avisos/historico").json()["itens"]
                  if l["aviso_id"] == alvo and l["pessoa"] == f"conta:{c['conta']['id']}"), {})
    checar(linha.get("de_onde") == "remoto" and linha.get("pessoa_nome") == "Caio Colaborador",
           "marcar pelo acesso de fora registra 'remoto'", linha)
    checar(alvo in [a["id"] for a in local.get("/api/central-avisos/hoje").json()["avisos"]],
           "e não some da janela do escritório")
    checar(alvo in [a["id"] for a in titular.get("/api/central-avisos/hoje").json()["avisos"]],
           "nem do carrossel da titular")
    h_tit = titular.get("/api/central-avisos/historico").json()
    checar(h_tit.get("titular") and any(l["pessoa_nome"] == "Caio Colaborador" for l in h_tit["itens"]),
           "a titular de fora vê o visto da equipe no histórico")
    h_col = colab.get("/api/central-avisos/historico").json()
    checar(not h_col.get("titular") and all(l["meu"] for l in h_col["itens"]), "o colaborador vê só os dele")
    tipos_tit = {a["tipo"] for a in titular.get("/api/central-avisos/hoje").json()["avisos"]}
    checar({"a_pagar", "a_receber", "pendencia"} <= tipos_tit, "a titular recebe as contas e as aprovações", sorted(tipos_tit))
    r = colab.post("/api/central-avisos/desmarcar", json={"id": alvo})
    checar(r.status_code == 200 and alvo in [a["id"] for a in r.json()["avisos"]], "de fora, desmarcar devolve o aviso")
    e.prefs.dados["acesso_remoto"]["ligado"] = False


def _pedir(base: str, metodo: str, caminho: str, dados=None):
    import api

    req = urllib.request.Request(base + caminho, method=metodo,
                                 data=json.dumps(dados).encode() if dados is not None else None,
                                 headers={"Content-Type": "application/json", **api.cabecalho_local()})
    return json.loads(urllib.request.urlopen(req, timeout=60).read() or b"{}")


# O que a cor de erro pode ser na tela (os tokens --acc*), em rgb, e onde procurar.
SONDA_DE_ERRO = """() => {
  const cores = new Set();
  for (const v of ['--acc', '--accln', '--accln2', '--accbg', '--accbg2']) {
    const s = document.createElement('span');
    s.style.color = 'var(' + v + ')';
    document.body.appendChild(s);
    const c = getComputedStyle(s).color;
    if (c && c !== 'rgba(0, 0, 0, 0)') cores.add(c);
    s.remove();
  }
  const achados = [];
  // O vinho so vale para o que esta atrasado (pacote de telas de 01/10/2026:
  // "verde, ambar e vermelho so como sinal de estado"): o icone e o selo do
  // aviso atrasado. Em qualquer outro lugar da faixa, e erro.
  document.querySelectorAll('#av-dia, #av-dia *').forEach((el) => {
    if (el.closest('.av-faixa-ic.atrasado, .av-faixa-selo.atrasado')) return;
    const st = getComputedStyle(el);
    for (const p of ['color', 'background-color', 'border-top-color', 'border-left-color', 'border-right-color', 'border-bottom-color']) {
      if (cores.has(st[p])) achados.push((el.className || el.tagName) + ' ' + p);
    }
  });
  return {cores: [...cores], achados: achados};
}"""


def test_tela(api, ids) -> None:
    print("\nna tela (Edge pelo Playwright)")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return
    from test_gravacoes import _porta_livre, _subir_servidor

    e = api.estado
    antes = dict(e.prefs.dados.get("conversa") or {})
    e.prefs.dados["conversa"] = {**antes, "avisos": True}
    porta = _porta_livre()
    _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"
    try:
        with sync_playwright() as p:
            try:
                nav = p.chromium.launch(channel="msedge")
            except Exception as exc:  # noqa: BLE001
                print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
                return
            pag = nav.new_page(viewport={"width": 1440, "height": 900})
            pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
            erros: list[str] = []
            pag.on("pageerror", lambda x: erros.append(str(x)))
            pag.goto(base + "/entrar-local?chave=" + api.estado.acesso.chave, wait_until="networkidle")
            pag.wait_for_selector("#av-dia:not([hidden]) .av-faixa-texto", timeout=15000)
            pag.wait_for_timeout(600)
            do_servidor = _pedir(base, "GET", "/api/central-avisos/hoje")["avisos"]
            atrasados = [a for a in do_servidor if a["grupo"] == "atrasado"]
            faixa = pag.evaluate("""() => ({id: document.querySelector('#av-dia .av-faixa-texto').dataset.avAbrir,
              conta: (document.querySelector('#av-dia .av-faixa-conta') || {}).textContent || '',
              linha: document.querySelector('#av-dia .av-faixa-texto small').textContent,
              altura: document.getElementById('av-dia').getBoundingClientRect().height})""")
            checar(faixa["conta"] == f"1 / {len(do_servidor)}", "a faixa mostra um aviso por vez, com a conta do servidor", (faixa["conta"], len(do_servidor)))
            checar(faixa["id"] == atrasados[0]["id"], "o primeiro é o atrasado mais antigo", faixa["id"])
            checar(f"e mais {len(atrasados) - 1} atrasado" in faixa["linha"], "a linha de baixo diz quantos mais estão atrasados", faixa["linha"])
            checar(55 <= faixa["altura"] <= 60, "a faixa tem 56 px, como no desenho", faixa["altura"])
            pag.click("#av-dia [data-av-passa='1']")
            pag.wait_for_timeout(300)
            depois = pag.evaluate("() => [document.querySelector('#av-dia .av-faixa-conta').textContent, document.querySelector('#av-dia .av-faixa-texto').dataset.avAbrir]")
            checar(depois[0] == f"2 / {len(do_servidor)}" and depois[1] != faixa["id"], "a seta passa para o próximo aviso", depois)
            pag.click("#av-dia [data-av-passa='-1']")
            pag.wait_for_timeout(300)
            debaixo = pag.evaluate("() => { const a = document.getElementById('agora'), v = document.getElementById('av-dia');"
                                   " return a.compareDocumentPosition(v) & Node.DOCUMENT_POSITION_FOLLOWING; }")
            checar(bool(debaixo), "logo abaixo de 'Acontecendo agora'")
            sonda = pag.evaluate(SONDA_DE_ERRO)
            checar(sonda["cores"] and not sonda["achados"], "o vinho só no ícone e no selo do atrasado", sonda["achados"][:4])
            pag.screenshot(path=str(CAPTURAS / "t2-inicio.png"))

            # a seta de abrir: o painel no lugar da lista de conversas
            pag.click("#av-dia [data-av-lista]")
            pag.wait_for_selector("#av-painel:not([hidden]) .avp-linha", timeout=8000)
            pag.wait_for_timeout(300)
            painel = pag.evaluate("""() => ({lista: document.getElementById('lista-conversas').hidden,
              recentes: document.getElementById('recentes').hidden,
              grupos: [...document.querySelectorAll('#av-painel .avp-grupo-cabeca')].map(g => g.childNodes[1].textContent.trim()),
              tipos: document.querySelectorAll('#av-painel [data-avp-tipo]').length})""")
            checar(painel["lista"] and painel["recentes"], "o painel entra no lugar da lista de conversas", painel)
            checar(painel["grupos"][:1] == ["Atrasados"] and painel["tipos"] >= 12, "os atrasados primeiro, com os tipos à esquerda", painel)
            checar(pag.evaluate("() => document.getElementById('av-dia').hidden"), "com o painel aberto, a faixa sai")
            pag.screenshot(path=str(CAPTURAS / "t2-painel.png"))
            primeiro = pag.evaluate("() => document.querySelector('#av-painel .avp-linha').dataset.av")
            pag.click(f"#av-painel .avp-linha[data-av='{primeiro}'] .av-marca")
            pag.wait_for_function(f"() => !(avs.avisos || []).some(a => a.id === {primeiro!r})", timeout=5000)
            h = _pedir(base, "GET", "/api/central-avisos/historico")["itens"]
            linha = next((l for l in h if l["aviso_id"] == primeiro), {})
            checar(linha.get("pessoa") == "local" and linha.get("visto_em"), "marcar como visto cria a linha no histórico com pessoa e hora", linha)
            pag.click("#av-painel [data-avp-fechar]")
            pag.wait_for_timeout(400)
            checar(not pag.evaluate("() => document.getElementById('lista-conversas').hidden"), "fechar o painel devolve a lista de conversas")

            pag.evaluate("() => abrirAvisosNaInicio('')")
            pag.wait_for_selector("#av-painel [data-avp-central]", timeout=8000)
            pag.click("#av-painel [data-avp-central]")
            pag.wait_for_selector("#veu-dialogo .av-central .avp-linha", timeout=8000)
            pag.wait_for_timeout(400)
            central = pag.evaluate("""() => ({tipos: document.querySelectorAll('#veu-dialogo [data-avp-tipo]').length,
              periodos: [...document.querySelectorAll('#veu-dialogo [data-avp-periodo]')].map(b => b.textContent.trim()),
              linhas: document.querySelectorAll('#veu-dialogo .avp-linha').length,
              pe: (document.querySelector('#veu-dialogo [data-avp-pe]') || {}).textContent || ''})""")
            checar(central["tipos"] >= 12 and central["periodos"] == ["Hoje", "7 dias", "30 dias"],
                   "a Central tem os tipos à esquerda e os períodos Hoje, 7 dias e 30 dias", central)
            checar(central["linhas"] >= 8 and "selecione vários" in central["pe"], "a lista agrupada e o pé com a conta", central)
            pag.click("#veu-dialogo [data-avp-tipo='prazo']")
            pag.wait_for_timeout(500)
            so_prazo = pag.evaluate("() => [...document.querySelectorAll('#veu-dialogo .avp-linha small')].map(s => s.textContent.split(' · ')[0])")
            checar(so_prazo and set(so_prazo) == {"Prazo"}, "o filtro de tipo funciona", set(so_prazo))
            pag.click("#veu-dialogo [data-avp-tipo='todos']")
            pag.wait_for_timeout(400)
            pag.screenshot(path=str(CAPTURAS / "t2-central.png"))
            pag.click("#veu-dialogo [data-avp-tipo='historico']")
            pag.wait_for_selector(f"#veu-dialogo [data-av-hist='{primeiro}']", timeout=5000)
            quem = pag.evaluate(f"() => document.querySelector(\"#veu-dialogo [data-av-hist='{primeiro}'] small\").textContent")
            checar("Helena Duarte" in quem and "computador do escritório" in quem, "o histórico diz quem viu, quando e de onde", quem)
            pag.screenshot(path=str(CAPTURAS / "t2-historico.png"))
            pag.click(f"#veu-dialogo [data-av-desmarcar='{primeiro}']")
            pag.wait_for_function(f"() => (avs.avisos || []).some(a => a.id === {primeiro!r})", timeout=5000)
            checar(True, "desmarcar no histórico devolve o aviso à faixa")
            pag.keyboard.press("Escape")
            pag.wait_for_timeout(300)
            pag.evaluate("() => fecharAvisosNaInicio()")

            # a ação direta pergunta antes, e cancelar não conclui
            alvo = f"prazo:{ids['contestacao']}:{d(0)}"
            pag.evaluate("() => abrirAvisosNaInicio('')")
            pag.wait_for_selector(f"#av-painel .avp-linha[data-av='{alvo}']", timeout=8000)
            pag.click(f"#av-painel .avp-linha[data-av='{alvo}'] [data-av-acao]")
            pag.wait_for_selector("#veu-dialogo .dialogo", timeout=5000)
            pergunta = pag.evaluate("() => document.getElementById('dialogo-titulo').textContent")
            pag.keyboard.press("Escape")
            pag.wait_for_timeout(600)
            checar("Concluir" in pergunta and not e.tarefas.obter(ids["contestacao"])["concluida"],
                   "'Concluir tarefa' pergunta antes, e cancelar não conclui", pergunta)
            pag.evaluate("() => fecharAvisosNaInicio()")

            pag.set_viewport_size({"width": 390, "height": 844})
            pag.wait_for_timeout(500)
            pag.evaluate("() => document.getElementById('av-dia').scrollIntoView()")
            pag.screenshot(path=str(CAPTURAS / "t2-celular.png"))
            cabe = pag.evaluate("() => { const r = document.getElementById('av-dia').getBoundingClientRect(); return [r.left, r.right]; }")
            checar(cabe[0] >= 0 and cabe[1] <= 390, "em 390 px a faixa cabe na tela, com a ação e as setas embaixo", cabe)
            pag.evaluate("() => abrirAvisosNaInicio('')")
            pag.wait_for_selector("#av-painel .avp-linha .av-marca", timeout=8000)
            dedo = pag.evaluate("() => { const r = document.querySelector('#av-painel .avp-linha .av-marca').getBoundingClientRect(); return [r.width, r.height]; }")
            checar(dedo[0] >= 44 and dedo[1] >= 44, "com o círculo do tamanho do dedo (44 px)", dedo)
            largura = pag.evaluate("() => document.documentElement.scrollWidth")
            checar(largura <= 392, "sem rolagem horizontal na página", largura)
            pag.evaluate("() => fecharAvisosNaInicio()")
            pag.set_viewport_size({"width": 1440, "height": 900})

            # sem avisos: marca tudo como visto e o resumo some
            for a in _pedir(base, "GET", "/api/central-avisos/hoje")["avisos"]:
                _pedir(base, "POST", "/api/central-avisos/visto", {"id": a["id"]})
            pag.evaluate("() => carregarAvisosDoDia(true)")
            pag.wait_for_timeout(800)
            checar(pag.evaluate("() => document.getElementById('av-dia').hidden"), "sem avisos, a faixa não aparece")
            for l in _pedir(base, "GET", "/api/central-avisos/historico")["itens"]:
                if l["meu"]:
                    _pedir(base, "POST", "/api/central-avisos/desmarcar", {"id": l["aviso_id"]})
            e.prefs.dados["conversa"] = {**antes, "avisos": False}
            pag.evaluate("() => carregarAvisosDoDia(true)")
            pag.wait_for_timeout(800)
            checar(pag.evaluate("() => document.getElementById('av-dia').hidden"), "com a chave desligada, também não aparece")
            checar(not erros, "nenhum erro de JavaScript", erros[:3])
            nav.close()
    finally:
        e.prefs.dados["conversa"] = antes


def main() -> int:
    print("=" * 60)
    print("  T2 — carrossel de avisos, Central de avisos e histórico")
    print("=" * 60)
    try:
        import api

        antes = dict(api.estado.prefs.dados.get("conversa") or {})
        api.estado.prefs.dados["conversa"] = {**antes, "avisos": True}
        try:
            ids = _exemplo(api)
            test_modulo(api, ids)
            test_vigia(api, ids)
            test_api(api, ids)
            test_tela(api, ids)
        finally:
            api.estado.prefs.dados["conversa"] = antes
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    print("\n" + "=" * 60)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
