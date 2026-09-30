"""
N1 - o prazo pelo tipo de ato (src/tipo_de_ato.py, src/processos.py, js/04-aprovacoes.js, js/48-publicacoes.js).

  - o ramo: trabalho pelo número e pelo tribunal, juizado pela classe e pelo
    grau, penal pela classe, cível no resto;
  - o ato de cada movimentação do DataJud: sentença, acórdão (só no grau
    recursal), decisão, despacho, juntadas;
  - a sugestão pelo ato anterior, em cada ramo: apelação, recurso inominado,
    recurso ordinário, apelação penal (corridos, sem recesso); citação no
    cível e no juizado (sem prazo daqui); cumprimento de sentença; sem ato:
    os 15 dias genéricos, dito;
  - o prazo que o juiz fixou vale no despacho e fica como lembrete na sentença;
  - o texto do DJEN: sentença, acórdão, decisão, despacho, citação;
  - de ponta a ponta com o DataJud de mentira: o pedido diz o ato, o porquê e
    as opções; aprovar com a segunda opção cria a tarefa dela;
  - a publicação do DJEN traz a sugestão, e o prazo criado leva o ato;
  - no Edge: as opções na caixa do pedido e a sugestão no "Criar prazo".

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_n1_tipo_de_ato.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-n1-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def numero_cnj(seq: int, ano: int = 2024, j: str = "8", tr: str = "26", origem: str = "0100") -> str:
    n = f"{seq:07d}"
    dd = 98 - (int(n + str(ano) + j + tr + origem) * 100 % 97)
    return f"{n}-{dd:02d}.{ano}.{j}.{tr}.{origem}"


class DataJud:
    """O DataJud de mentira: os movimentos de cada número."""

    def __init__(self) -> None:
        self.movs: dict[str, list[dict]] = {}

    def __call__(self, numero: str) -> dict:
        return {"numero": numero, "graus": [{"grau": "G1", "classe": "Procedimento Comum Cível", "orgao": "1ª Vara Cível",
                                            "movimentos": list(self.movs.get(numero, []))}]}


def main() -> int:
    print("=" * 55)
    print("  N1 — o prazo pelo tipo de ato")
    print("=" * 55)
    import prazos
    import processos
    import tipo_de_ato as t

    print("\no ramo")
    checar(t.ramo(numero=numero_cnj(1, j="5", tr="18")) == "trabalho" and t.ramo(tribunal="TRT18") == "trabalho", "trabalho: pelo número e pelo tribunal")
    checar(t.ramo(classe="Procedimento do Juizado Especial Cível") == "juizado" and t.ramo(grau="JE") == "juizado", "juizado: pela classe e pelo grau")
    checar(t.ramo(classe="Ação Penal - Procedimento Ordinário") == "penal", "penal: pela classe")
    checar(t.ramo(classe="Procedimento Comum Cível", orgao="1ª Vara Cível") == "civel", "cível no resto")

    print("\no ato de cada movimentação")
    casos = [({"nome": "Procedência"}, "G1", "sentenca"), ({"nome": "Improcedência"}, "G1", "sentenca"),
             ({"nome": "Não-Provimento"}, "G2", "acordao"), ({"nome": "Procedência"}, "G2", "acordao"),
             ({"nome": "Antecipação de Tutela"}, "G1", "decisao"), ({"nome": "Concessão"}, "G1", "decisao"),
             ({"nome": "Mero expediente"}, "G1", "despacho"), ({"nome": "Juntada de Petição", "complemento": "Contestação"}, "G1", "contestacao_juntada"),
             ({"nome": "Juntada de Petição", "complemento": "Apelação"}, "G1", "recurso_juntado"),
             ({"nome": "Juntada de Petição", "complemento": "Embargos de Declaração"}, "G1", "embargos_juntados"),
             ({"nome": "Distribuição"}, "G1", ""), ({"nome": "Conclusão"}, "G1", "")]
    errados = [(m, g, e, t.ato_do_movimento(m, grau=g)) for m, g, e in casos if t.ato_do_movimento(m, grau=g) != e]
    checar(not errados, "sentença, acórdão (no grau recursal), decisão, despacho e juntadas", errados)

    print("\na sugestão pelo ato anterior")
    intim = {"quando": "2026-09-14 10:00", "nome": "Expedição de documento", "complemento": "Intimação"}
    sent = [{"quando": "2026-09-10 16:00", "nome": "Procedência em Parte"}, {"quando": "2026-08-01", "nome": "Conclusão"}]
    s = t.do_movimento(intim, sent, classe="Procedimento Comum Cível")
    checar(s["ato"] == "Apelação" and s["dias"] == 15 and s["uteis"] and s["certeza"] == "reconhecido"
           and "1.003" in s["base"] and s["alternativas"][0]["ato"] == "Embargos de declaração" and "Procedência em Parte" in s["porque"],
           "sentença no cível: apelação, 15 dias úteis; embargos como alternativa; o porquê", s)
    s = t.do_movimento(intim, sent, classe="Procedimento do Juizado Especial Cível")
    checar(s["ato"] == "Recurso inominado" and s["dias"] == 10 and s["uteis"], "no juizado: recurso inominado, 10 dias úteis", s["ato"])
    s = t.do_movimento(intim, sent, classe="Ação Trabalhista - Rito Ordinário", tribunal="TRT2")
    checar(s["ato"] == "Recurso ordinário" and s["dias"] == 8, "no trabalho: recurso ordinário, 8 dias", s["ato"])
    s = t.do_movimento(intim, sent, classe="Ação Penal - Procedimento Ordinário")
    checar(s["ato"] == "Apelação" and s["dias"] == 5 and not s["uteis"] and s["ramo"] == "penal", "no penal: apelação, 5 dias corridos", s)
    s = t.do_movimento(intim, [{"quando": "2026-09-10", "nome": "Não-Provimento"}], classe="Apelação Cível", grau="G2")
    checar(s["ato"] == "Recurso especial ou extraordinário" and s["dias"] == 15, "acórdão: recurso especial ou extraordinário", s["ato"])
    s = t.do_movimento(intim, [{"quando": "2026-09-10", "nome": "Decisão", "complemento": "Antecipação de tutela"}], classe="Procedimento Comum Cível")
    checar(s["ato"] == "Agravo de instrumento" and "1.015" in s["base"], "decisão: agravo de instrumento, com o aviso do rol", s["base"])
    s = t.do_movimento({"quando": "2026-09-14", "nome": "Expedição de documento", "complemento": "Citação"}, [], classe="Procedimento Comum Cível")
    checar(s["ato"] == "Contestação" and s["dias"] == 15 and "335" in s["base"], "citação no cível: contestação", s["ato"])
    s = t.do_movimento({"quando": "2026-09-14", "nome": "Expedição de documento", "complemento": "Citação"}, [], classe="Procedimento do Juizado Especial Cível")
    checar(s["sem_prazo"] and "audiência" in s["sem_prazo"], "citação no juizado: sem prazo contado daqui, e diz por quê", s)
    s = t.do_movimento(intim, [{"quando": "2026-09-10", "nome": "Mero expediente"}], classe="Cumprimento de sentença")
    checar(s["ato"] == "Pagamento voluntário" and "523" in s["base"], "cumprimento de sentença: pagamento voluntário", s["ato"])
    s = t.do_movimento(intim, [{"quando": "2026-09-10", "nome": "Juntada de Petição", "complemento": "Contestação"}], classe="Procedimento Comum Cível")
    checar(s["ato"] == "Réplica", "contestação juntada: réplica", s["ato"])
    s = t.do_movimento(intim, [{"quando": "2026-09-10", "nome": "Conclusão"}], classe="Procedimento Comum Cível")
    checar(s["certeza"] == "generico" and s["dias"] == 15 and "não reconheci" in s["ato"], "sem ato reconhecido: 15 dias, e diz", s)

    print("\no prazo fixado pelo juiz")
    checar((t.prazo_fixado("Manifeste-se a parte autora, no prazo de 5 (cinco) dias.") or {}).get("dias") == 5, "“no prazo de 5 (cinco) dias”")
    checar((t.prazo_fixado("no prazo de quinze dias úteis") or {}).get("dias") == 15, "“no prazo de quinze dias”")
    checar((t.prazo_fixado("em 48 (quarenta e oito) horas") or {}).get("dias") == 2, "48 horas: 2 dias")
    checar(t.prazo_fixado("valor de R$ 1.000,00 em 12/10/2024, 3 parcelas") is None, "data e valor não são prazo")
    s = t.do_texto("DESPACHO. Intime-se a parte autora para, no prazo de 10 (dez) dias, emendar a inicial.", tipo="Intimação")
    checar(s["certeza"] == "fixado" and s["dias"] == 10 and "emendar" in s["base"], "despacho com prazo: vale o do juiz, com o trecho", s)
    s = t.do_texto("SENTENÇA. Ante o exposto, JULGO PROCEDENTE o pedido e condeno o réu a pagar, no prazo de 15 (quinze) dias, "
                   "a quantia de R$ 5.000,00.", tipo="Intimação", classe="Procedimento Comum Cível")
    checar(s["ato"] == "Apelação" and not any(a["ato"] == "Prazo fixado no ato" for a in s["alternativas"]), "sentença com prazo de pagar: continua apelação", s)
    s = t.do_texto("SENTENÇA. Ante o exposto, JULGO PROCEDENTE o pedido e condeno o réu a pagar, no prazo de 30 (trinta) dias.",
                   tipo="Intimação", classe="Procedimento Comum Cível")
    checar(any("cumprir" in a["base"] for a in s["alternativas"]), "o prazo do texto fica como lembrete na sentença", s["alternativas"])

    print("\no texto do DJEN")
    checar(t.do_texto("ACÓRDÃO. Vistos, relatados e discutidos... ACORDAM os Desembargadores em negar provimento.")["ato"] ==
           "Recurso especial ou extraordinário", "acórdão")
    checar(t.do_texto("DECISÃO. Presentes os requisitos, DEFIRO a tutela de urgência.")["ato"] == "Agravo de instrumento", "decisão")
    checar(t.do_texto("Fica o réu CITADO para, querendo, contestar...", tipo="Citação")["ato"] == "Contestação", "citação")
    checar(t.do_texto("Vistos. Diga a parte autora sobre a contestação.")["ato"] == "Manifestação", "despacho sem prazo: 5 dias (art. 218)")

    print("\no recesso no penal")
    a = prazos.calcular(date(2026, 12, 15), 5, uteis=False, recesso=False)
    b = prazos.calcular(date(2026, 12, 15), 5, uteis=False)
    checar(a["vencimento"] < "2026-12-31" and b["vencimento"] >= "2027-01-21", "corrido sem recesso vence em dezembro; com recesso passa para 21/01", (a["vencimento"], b["vencimento"]))

    print("\nde ponta a ponta")
    import api
    from fastapi.testclient import TestClient

    local = TestClient(api.app, headers=api.cabecalho_local())
    base = api.estado.base
    falso = DataJud()
    processos._CONSULTAR["fn"] = falso
    n1 = numero_cnj(4321)
    dig = n1.replace("-", "").replace(".", "")
    local.post("/api/processos", json={"numero": n1})
    api.estado.prefs.dados.setdefault("processos", {})["acompanhar"] = True
    falso.movs[dig] = [{"quando": "2026-08-01 09:00", "nome": "Distribuição", "complemento": ""}]
    local.post("/api/processos/acompanhar-agora")
    falso.movs[dig] += [{"quando": "2026-09-10 16:00", "nome": "Procedência", "complemento": ""},
                        {"quando": "2026-09-14 10:00", "nome": "Expedição de documento", "complemento": "Intimação"}]
    r = local.post("/api/processos/acompanhar-agora").json()
    pedidos = [p for p in api.estado.fila.pendentes if p.acao == "processos.prazo"]
    ped = pedidos[0] if pedidos else None
    checar(r["prazos_propostos"] == 1 and ped and "Apelação (15 dias úteis)" in ped.titulo and "Por quê" in ped.resumo
           and "Também pode ser: Embargos de declaração" in ped.resumo and len(ped.dados["opcoes"]) == 2,
           "o pedido diz o ato, o porquê e as opções", ped and (ped.titulo, ped.resumo))
    ed = ped.dados["opcoes"][1]
    r = local.post("/api/aprovacoes/decidir", json={"ids": [ped.id], "aprovar": True, "escolhas": {ped.id: 1}})
    tarefa = base.um("SELECT * FROM tarefas WHERE lista = 'Prazos' ORDER BY id DESC LIMIT 1") or {}
    checar(r.status_code == 200 and tarefa.get("titulo", "").startswith("Prazo: Embargos de declaração") and tarefa.get("prazo") == ed["vencimento"]
           and "1.023" in (tarefa.get("anotacao") or ""), "aprovar com a segunda opção cria a tarefa dela", dict(tarefa))

    print("\na publicação do DJEN")
    base.escrever("INSERT INTO publicacoes (id_externo, data, tribunal, tipo, orgao, classe, processo, texto, link, oab, criada_em)"
                  " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  ("x1", "2026-09-21", "TJSP", "Intimação", "1ª Vara Cível", "Procedimento Comum Cível", n1,
                   "SENTENÇA. Ante o exposto, JULGO IMPROCEDENTE o pedido.", "", "SP 1", "2026-09-21T10:00:00"))
    pubs = local.get("/api/publicacoes").json()["publicacoes"]
    sg = (pubs[0] if pubs else {}).get("sugestao") or {}
    checar(sg.get("ato") == "Apelação" and sg.get("vencimento") and sg.get("origem") == "disponibilizacao", "a publicação traz a sugestão, pela disponibilização", sg)
    r = local.post(f"/api/publicacoes/{pubs[0]['id']}/prazo", json={"dias": 15, "uteis": True, "ato": "Apelação", "base": sg.get("base", "")})
    tarefa = base.um("SELECT * FROM tarefas WHERE lista = 'Prazos' ORDER BY id DESC LIMIT 1") or {}
    checar(r.status_code == 200 and tarefa.get("titulo", "").startswith("Prazo: Apelação") and "1.009" in (tarefa.get("anotacao") or ""),
           "o prazo criado leva o ato e a base", dict(tarefa))

    print("\nno Edge")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None
        print("  pulado: playwright não instalado")
    if sync_playwright is not None:
        from test_gravacoes import _porta_livre, _subir_servidor

        base.escrever("INSERT INTO publicacoes (id_externo, data, tribunal, tipo, orgao, classe, processo, texto, link, oab, criada_em)"
                      " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      ("x2", "2026-09-22", "TJSP", "Intimação", "1ª Vara Cível", "Procedimento Comum Cível", numero_cnj(9876),
                       "DECISÃO. DEFIRO a tutela de urgência requerida.", "", "SP 1", "2026-09-22T10:00:00"))
        falso.movs[dig] += [{"quando": "2026-09-25 10:00", "nome": "Decisão", "complemento": "Concessão"},
                            {"quando": "2026-09-28 10:00", "nome": "Publicação", "complemento": "DJEN"}]
        local.post("/api/processos/acompanhar-agora")
        pendente = next(p for p in api.estado.fila.pendentes if p.acao == "processos.prazo")
        porta = _porta_livre()
        _subir_servidor(porta)
        with sync_playwright() as p:
            try:
                nav = p.chromium.launch(channel="msedge")
            except Exception as exc:  # noqa: BLE001
                nav = None
                print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            if nav is not None:
                pag = nav.new_context(viewport={"width": 1280, "height": 900}).new_page()
                erros = []
                pag.on("pageerror", lambda e: erros.append(str(e)))
                pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
                pag.goto(f"http://127.0.0.1:{porta}/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
                pag.wait_for_function("() => typeof mostrarAprovacoes === 'function'")
                pag.wait_for_timeout(800)
                pag.evaluate("() => mostrarAprovacoes()")
                pag.wait_for_selector(f"[data-pedido='{pendente.id}']", timeout=15000)
                pag.click(f"[data-pedido='{pendente.id}'] .nome-doc")
                pag.wait_for_selector(".ap-opcoes", timeout=10000)
                texto = pag.inner_text(".ap-opcoes")
                checar("Agravo de instrumento" in texto and "Embargos de declaração" in texto and "Manifestação" in texto,
                       "a caixa do pedido mostra as opções", texto)
                pag.wait_for_timeout(500)
                pag.screenshot(path=str(TMP / "n1-pedido.png"))
                pag.check("[data-ap-opcao='2']")
                pag.click("#veu-dialogo [data-dialogo='confirmar']")
                pag.wait_for_timeout(500)
                pag.click("#veu-dialogo [data-dialogo='confirmar']")
                pag.wait_for_timeout(1200)
                tarefa = base.um("SELECT * FROM tarefas WHERE lista = 'Prazos' ORDER BY id DESC LIMIT 1") or {}
                checar(tarefa.get("titulo", "").startswith("Prazo: Manifestação"), "aprovar pela tela, com a terceira opção", tarefa.get("titulo"))
                pag.evaluate("async () => { ag.tar.filtro = 'publicacoes'; ag.tar.lista = null; await mostrarAgenda('tarefas'); }")
                pag.wait_for_selector("[data-pub-abrir]", timeout=15000)
                pag.click("[data-pub-abrir]:has-text('Intimação') >> nth=0")
                pag.wait_for_selector("[data-pub-prazo]", timeout=10000)
                pag.click("[data-pub-prazo]")
                pag.wait_for_selector(".pub-sugestao", timeout=10000)
                sug = pag.inner_text(".pub-sugestao")
                checar(("Agravo de instrumento" in sug or "Apelação" in sug) and "Por quê" in sug, "o “Criar prazo” mostra a sugestão e o porquê", sug)
                pag.wait_for_timeout(500)
                pag.screenshot(path=str(TMP / "n1-publicacao.png"))
                checar(not erros, "nenhum erro de JavaScript", erros[:3])
                print(f"  (fotos em {TMP})")
                nav.close()

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for x in _falhas:
            print(f"    - {x}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
