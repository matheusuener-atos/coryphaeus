"""
N2 - a publicação do DJEN ligada ao processo acompanhado (src/processos.py, src/central_avisos.py).

Com o DJEN e o DataJud de mentira (nada sai daqui):

  - a consulta do DJEN liga a publicação ao processo cadastrado e pede o
    prazo a partir dela (pela disponibilização e pelo texto);
  - um aviso só na Central: o do processo, com as movimentações e as
    publicações; a publicação ligada não vira aviso à parte;
  - a movimentação do DataJud da mesma intimação, dias depois, não pede de
    novo; ao contrário, a publicação que chega depois se junta ao pedido do
    DataJud;
  - o sim anota a tarefa e a publicação fica com ela, lida;
  - publicação de processo não cadastrado continua sozinha; "acompanhar este
    processo" liga e pede; publicação antiga não vira pedido;
  - marcar como vistas deixa as publicações lidas;
  - no Edge: o detalhe do processo mostra as publicações, e a publicação diz
    que está ligada ou oferece acompanhar.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_n2_djen_processo.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-n2-"))
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


def dig(n: str) -> str:
    return n.replace("-", "").replace(".", "")


class DataJud:
    def __init__(self) -> None:
        self.movs: dict[str, list[dict]] = {}

    def __call__(self, numero: str) -> dict:
        return {"numero": numero, "graus": [{"grau": "G1", "classe": "Procedimento Comum Cível", "orgao": "1ª Vara Cível",
                                            "movimentos": list(self.movs.get(numero, []))}]}


def dia(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


def main() -> int:
    print("=" * 55)
    print("  N2 — o DJEN junto do processo")
    print("=" * 55)
    import api
    import processos
    from fastapi.testclient import TestClient

    local = TestClient(api.app, headers=api.cabecalho_local())
    base = api.estado.base
    falso = DataJud()
    processos._CONSULTAR["fn"] = falso
    api.estado.prefs.atualizar({"pessoa": {"oab": "SP 123"}})
    djen: list[dict] = []
    api.publicacoes_mod.consultar = lambda oab, de, ate, **k: list(djen)

    def item(id_, numero, data, texto, tipo="Intimação"):
        return {"id": id_, "data_disponibilizacao": data, "siglaTribunal": "TJSP", "tipoComunicacao": tipo, "nomeOrgao": "1ª Vara Cível",
                "nomeClasse": "Procedimento Comum Cível", "numeroprocessocommascara": numero, "texto": texto, "link": ""}

    def avisos():
        return [a for a in local.get("/api/central-avisos?periodo=semana").json().get("avisos", []) if a["tipo"] in ("processo", "publicacao")]

    def pedidos_de(pid):
        return [p for p in api.estado.fila.pendentes if p.acao == "processos.prazo" and p.dados.get("processo_id") == pid]

    api.estado.prefs.dados.setdefault("processos", {})["acompanhar"] = True
    n1, n2, n3, n4 = numero_cnj(1111), numero_cnj(2222), numero_cnj(3333), numero_cnj(4444)
    p1 = local.post("/api/processos", json={"numero": n1}).json()["id"]
    p2 = local.post("/api/processos", json={"numero": n2}).json()["id"]
    falso.movs[dig(n1)] = [{"quando": dia(40) + " 09:00", "nome": "Distribuição", "complemento": ""}]
    falso.movs[dig(n2)] = [{"quando": dia(40) + " 09:00", "nome": "Distribuição", "complemento": ""}]
    local.post("/api/processos/acompanhar-agora")

    print("\no DJEN primeiro")
    djen[:] = [item(9001, n1, dia(3), "SENTENÇA. Ante o exposto, JULGO PROCEDENTE o pedido.")]
    r = local.post("/api/publicacoes/consultar")
    pub1 = base.um("SELECT * FROM publicacoes WHERE id_externo = '9001'") or {}
    ped = pedidos_de(p1)
    checar(r.status_code == 200 and pub1.get("processo_id") == p1, "a publicação fica ligada ao processo cadastrado", (r.status_code, dict(pub1)))
    checar(len(ped) == 1 and "Apelação" in ped[0].titulo and ped[0].pedido_por == "Publicações do DJEN" and pub1.get("pedido_id") == ped[0].id
           and ped[0].dados["quando"] == dia(3) and "Disponibilizado" in ped[0].resumo,
           "o prazo é pedido a partir da publicação (pela disponibilização e pelo texto)", [p.titulo for p in ped])
    av = avisos()
    checar(len(av) == 1 and av[0]["tipo"] == "processo" and "1 publicação no DJEN" in av[0]["quando"] and "DJEN" in av[0]["origem"],
           "um aviso só: o do processo, com a publicação", av)
    falso.movs[dig(n1)] += [{"quando": dia(5) + " 16:00", "nome": "Procedência", "complemento": ""},
                            {"quando": dia(2) + " 10:00", "nome": "Publicação", "complemento": "DJEN"}]
    r = local.post("/api/processos/acompanhar-agora").json()
    checar(r["prazos_propostos"] == 0 and r["pelo_djen"] == 1 and len(pedidos_de(p1)) == 1,
           "a movimentação do DataJud da mesma intimação não pede de novo", r)
    av = avisos()
    checar(len(av) == 1 and "2 movimentações novas e 1 publicação no DJEN" in av[0]["quando"] and "DataJud + DJEN" in av[0]["origem"],
           "o aviso do processo junta as duas fontes", av and av[0]["quando"])
    local.post("/api/aprovacoes/decidir", json={"ids": [ped[0].id], "aprovar": True})
    pub1 = base.um("SELECT * FROM publicacoes WHERE id_externo = '9001'") or {}
    tarefa = base.um("SELECT * FROM tarefas WHERE lista = 'Prazos' ORDER BY id DESC LIMIT 1") or {}
    checar(pub1.get("tarefa_id") == tarefa.get("id") and pub1.get("lida") == 1 and "Publicado no DJEN" in (tarefa.get("anotacao") or ""),
           "o sim anota a tarefa, e a publicação fica com ela, lida", (dict(pub1), tarefa.get("anotacao")))

    print("\no DataJud primeiro")
    falso.movs[dig(n2)] += [{"quando": dia(4) + " 16:00", "nome": "Decisão", "complemento": "Concessão"},
                            {"quando": dia(2) + " 10:00", "nome": "Expedição de documento", "complemento": "Intimação"}]
    r = local.post("/api/processos/acompanhar-agora").json()
    ped2 = pedidos_de(p2)
    checar(r["prazos_propostos"] == 1 and len(ped2) == 1 and ped2[0].pedido_por == "Acompanhamento de processos", "o DataJud pede o prazo", r)
    djen[:] = [item(9002, n2, dia(1), "DECISÃO. DEFIRO a tutela de urgência.")]
    local.post("/api/publicacoes/consultar")
    pub2 = base.um("SELECT * FROM publicacoes WHERE id_externo = '9002'") or {}
    checar(len(pedidos_de(p2)) == 1 and pub2.get("pedido_id") == ped2[0].id, "a publicação que chega depois se junta ao pedido do DataJud", dict(pub2))

    print("\nsem processo cadastrado")
    djen[:] = [item(9003, n3, dia(1), "DESPACHO. Manifeste-se a parte autora no prazo de 5 (cinco) dias."),
               item(9004, n4, dia(60), "DESPACHO. Diga a parte autora.")]
    local.post("/api/publicacoes/consultar")
    pub3 = base.um("SELECT * FROM publicacoes WHERE id_externo = '9003'") or {}
    checar(pub3.get("processo_id") is None and any(a["tipo"] == "publicacao" and n3 in a["titulo"] for a in avisos()),
           "publicação de processo não cadastrado continua sozinha, com o aviso dela")
    local.post("/api/processos", json={"numero": n3})
    pub3 = base.um("SELECT * FROM publicacoes WHERE id_externo = '9003'") or {}
    p3 = pub3.get("processo_id")
    checar(p3 and len(pedidos_de(p3)) == 1 and "Prazo fixado no ato (5 dias úteis)" in pedidos_de(p3)[0].titulo,
           "acompanhar o processo liga e pede o prazo (o fixado pelo juiz)", [p.titulo for p in pedidos_de(p3 or 0)])
    local.post("/api/processos", json={"numero": n4})
    pub4 = base.um("SELECT * FROM publicacoes WHERE id_externo = '9004'") or {}
    checar(pub4.get("processo_id") and not pedidos_de(pub4["processo_id"]) and not pub4.get("pedido_id"),
           "publicação antiga (60 dias) liga, mas não vira pedido", dict(pub4))
    det = local.get(f"/api/processos/{p3}").json()
    checar(len(det["publicacoes"]) == 1 and det["publicacoes"][0]["pedido_id"], "o detalhe do processo traz as publicações")
    local.post(f"/api/processos/{p3}/vistos")
    checar(base.um("SELECT lida FROM publicacoes WHERE id_externo = '9003'")["lida"] == 1, "marcar como vistas deixa as publicações lidas")

    print("\nno Edge")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None
        print("  pulado: playwright não instalado")
    if sync_playwright is not None:
        from test_gravacoes import _porta_livre, _subir_servidor

        n5 = numero_cnj(5555)
        djen[:] = [item(9005, n5, dia(1), "DESPACHO. Especifiquem as partes as provas que pretendem produzir.")]
        local.post("/api/publicacoes/consultar")
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
                pag.wait_for_function("() => typeof abrirProcesso === 'function'")
                pag.wait_for_timeout(800)
                pag.evaluate(f"() => {{ abrirProcesso({p1}); }}")
                pag.wait_for_selector(".pr-pubs", timeout=10000)
                texto = pag.inner_text(".pr-detalhe")
                checar("Publicações no DJEN" in texto and "prazo anotado em Tarefas" in texto and "Movimentações no DataJud" in texto,
                       "o detalhe do processo mostra as publicações e o que houve com o prazo", texto[:300])
                pag.wait_for_timeout(400)
                pag.screenshot(path=str(TMP / "n2-processo.png"))
                pag.keyboard.press("Escape")
                pag.wait_for_timeout(400)
                pag.evaluate("async () => { pub.filtro = 'todas'; ag.tar.filtro = 'publicacoes'; ag.tar.lista = null; await carregarPublicacoes(); await mostrarAgenda('tarefas'); }")
                pag.wait_for_selector("[data-pub-abrir]", timeout=15000)
                pag.click(f"[data-pub-abrir]:has-text('{n5}')")
                pag.wait_for_selector("[data-pub-acompanhar]", timeout=10000)
                checar(pag.locator("[data-pub-acompanhar]").count() == 1, "a publicação sem processo oferece acompanhar")
                pag.click("[data-pub-acompanhar]")
                pag.wait_for_selector("[data-pub-processo]", timeout=10000)
                checar("prazo já espera em Aprovações" in pag.inner_text(".pub-corpo"), "acompanhado pela tela: ligada, e o prazo já em Aprovações",
                       pag.inner_text(".pub-corpo")[:300])
                pag.wait_for_timeout(400)
                pag.screenshot(path=str(TMP / "n2-publicacao.png"))
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
