"""
N9 - o MCP com escopo por cliente e com ferramentas que escrevem (src/mcp_leis.py, js/69-mcp.js).

  - escopo por cliente: os Serviços dele e os documentos ligados à ficha;
    o documento de outro cliente não sai;
  - as que escrevem pedem o segundo "entendi"; criar_rascunho, propor_tarefa
    e propor_compromisso não pedem escopo; anotar_no_servico, sim;
  - criar_rascunho: documento novo no editor, marcado como do assistente;
  - anotar_no_servico: na trilha do Serviço liberado, marcada com a conexão;
    Serviço de fora do escopo: recusa;
  - propor_tarefa e propor_compromisso: pedido em Aprovações, nada criado
    antes do sim; o sim cria; data errada: recusa;
  - ferramenta que escreve sem estar liberada na conexão: recusa; tudo na
    auditoria;
  - no Edge: o diálogo da conexão nova com os clientes e o segundo "entendi".

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_n9_mcp_escreve.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-n9-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def main() -> int:
    print("=" * 55)
    print("  N9 — MCP: escopo por cliente e ferramentas que escrevem")
    print("=" * 55)
    import api
    from fastapi.testclient import TestClient

    auditoria = []
    api.estado.mcp.registrar = lambda **e: auditoria.append(e)
    api.estado.prefs.dados.setdefault("umbrel", {})["mcp"] = True
    janela = TestClient(api.app, headers=api.cabecalho_local(), client=("127.0.0.1", 50124))
    local = TestClient(api.app, client=("127.0.0.1", 50123))
    base = api.estado.base

    alfa = janela.post("/api/cadastros", json={"id": None, "dados": {"tipo": "cliente", "nome": "Construtora Alfa"}}).json()["id"]
    beta = janela.post("/api/cadastros", json={"id": None, "dados": {"tipo": "cliente", "nome": "Beta Comércio"}}).json()["id"]
    s_alfa = janela.post("/api/servicos", json={"id": None, "dados": {"nome": "Obra da Alfa", "cadastro_id": alfa}}).json()["id"]
    s_beta = janela.post("/api/servicos", json={"id": None, "dados": {"nome": "Cobrança da Beta", "cadastro_id": beta}}).json()["id"]
    (api.estado.servicos.pasta_de(s_alfa, criar=True) / "contrato-alfa.txt").write_text("Contrato da Alfa. Multa zebrina de dez por cento.", encoding="utf-8")
    (api.estado.servicos.pasta_de(s_beta, criar=True) / "contrato-beta.txt").write_text("Contrato da Beta. Multa zebrina de vinte por cento.", encoding="utf-8")
    solta = Path(api.estado.pasta) / "Avulsos"
    solta.mkdir(parents=True, exist_ok=True)
    (solta / "procuracao-alfa.txt").write_text("Procuração da Alfa. Poderes zebrinos para o foro em geral.", encoding="utf-8")
    api.estado.recarregar()
    doc_solto = next(d for d in api.estado.searcher.documents if d.name == "procuracao-alfa.txt")
    base.escrever("INSERT INTO vinculos (tipo, alvo_id, sha1, nome, criado_em) VALUES ('cadastro', ?, ?, ?, '2026-09-30')",
                  (alfa, doc_solto.sha1, doc_solto.name))

    def rpc(metodo, params=None, token="", id_=1):
        return local.post("/mcp", headers={"Authorization": f"Bearer {token}"},
                          content=json.dumps({"jsonrpc": "2.0", "id": id_, "method": metodo, "params": params or {}})).json()

    def chamar(token, nome, args=None):
        r = rpc("tools/call", {"name": nome, "arguments": args or {}}, token=token)
        return r.get("result", {}).get("content", [{}])[0].get("text", "") if "result" in r else json.dumps(r)

    print("\nescopo por cliente")
    r = janela.post("/api/mcp/conexoes", json={"nome": "Só a Alfa", "ferramentas": ["acervo_documentos", "acervo_procurar"],
                                              "escopo": {"clientes": [alfa]}, "entendi": True})
    checar(r.status_code == 200 and r.json()["conexao"]["escopo"]["clientes"] == [alfa], "cria com o cliente como escopo", r.text[:200])
    t = r.json()["token"]
    lista = chamar(t, "acervo_documentos")
    checar("contrato-alfa.txt" in lista and "procuracao-alfa.txt" in lista and "contrato-beta.txt" not in lista,
           "os documentos dos Serviços dele e os ligados à ficha; o do outro cliente não", lista)
    achado = chamar(t, "acervo_procurar", {"termo": "multa zebrina"})
    checar("contrato-alfa" in achado and "beta" not in achado.lower(), "a busca também", achado[:200])

    print("\nas que escrevem")
    r = janela.post("/api/mcp/conexoes", json={"nome": "Escritor", "ferramentas": ["criar_rascunho"], "entendi": True})
    checar(r.status_code == 400 and "criar coisas" in r.json()["detail"], "sem o segundo “entendi”: recusa")
    r = janela.post("/api/mcp/conexoes", json={"nome": "Escritor", "ferramentas": ["criar_rascunho", "propor_tarefa", "propor_compromisso"],
                                              "entendi": True, "entendi_escrever": True})
    checar(r.status_code == 200 and r.json()["conexao"]["escreve"] == ["criar_rascunho", "propor_tarefa", "propor_compromisso"],
           "rascunho e pedidos não pedem escopo; a conexão diz o que escreve", r.text[:200])
    t_w = r.json()["token"]
    r = janela.post("/api/mcp/conexoes", json={"nome": "Anotador", "ferramentas": ["anotar_no_servico"], "entendi": True, "entendi_escrever": True})
    checar(r.status_code == 400 and "escopo" in r.json()["detail"], "anotar no Serviço sem escopo: recusa")
    t_a = janela.post("/api/mcp/conexoes", json={"nome": "Anotador", "ferramentas": ["anotar_no_servico"], "escopo": {"clientes": [alfa]},
                                                 "entendi": True, "entendi_escrever": True}).json()["token"]
    listadas = [x["name"] for x in rpc("tools/list", token=t_w)["result"]["tools"]]
    checar(listadas == ["criar_rascunho", "propor_tarefa", "propor_compromisso"], "tools/list só com as liberadas", listadas)

    texto = chamar(t_w, "criar_rascunho", {"titulo": "Notificação à Beta", "texto": "Prezados,\n\nNotificamos o atraso.\n\nAtenciosamente."})
    doc = base.um("SELECT * FROM documentos ORDER BY id DESC LIMIT 1") or {}
    checar("Rascunho criado" in texto and doc.get("titulo") == "Notificação à Beta (rascunho do assistente)"
           and "Rascunho criado pelo" in (doc.get("corpo") or "") and "<p>Notificamos o atraso.</p>" in (doc.get("corpo") or ""),
           "criar_rascunho: documento novo no editor, marcado", texto)
    antes_t = base.contar("tarefas")
    texto = chamar(t_w, "propor_tarefa", {"titulo": "Ligar para a Beta", "prazo": "2026-10-10"})
    pedido = next((p for p in api.estado.fila.pendentes if p.acao == "mcp.tarefa"), None)
    checar("Aprovações" in texto and pedido and base.contar("tarefas") == antes_t, "propor_tarefa: pedido em Aprovações, nada criado antes", texto)
    janela.post("/api/aprovacoes/decidir", json={"ids": [pedido.id], "aprovar": True})
    tarefa = base.um("SELECT * FROM tarefas ORDER BY id DESC LIMIT 1") or {}
    checar(tarefa.get("titulo") == "Ligar para a Beta" and tarefa.get("prazo") == "2026-10-10" and "MCP" in (tarefa.get("anotacao") or ""),
           "o sim cria a tarefa, dita como pedida pelo MCP", dict(tarefa))
    checar(chamar(t_w, "propor_compromisso", {"titulo": "Reunião", "data": "10/10/2026"}).startswith("A data vai como"), "data errada: recusa")
    texto = chamar(t_w, "propor_compromisso", {"titulo": "Reunião com a Beta", "data": "2026-10-12", "hora": "14:30"})
    pedido = next((p for p in api.estado.fila.pendentes if p.acao == "mcp.compromisso"), None)
    janela.post("/api/aprovacoes/decidir", json={"ids": [pedido.id], "aprovar": True})
    comp = base.um("SELECT * FROM compromissos ORDER BY id DESC LIMIT 1") or {}
    checar("Aprovações" in texto and comp.get("titulo") == "Reunião com a Beta" and comp.get("hora") == "14:30",
           "propor_compromisso: pelo sim, na agenda", dict(comp))

    texto = chamar(t_a, "anotar_no_servico", {"servico": "Obra da Alfa", "texto": "O cliente mandou o aditivo por e-mail."})
    trilha = (base.um("SELECT trilha FROM servicos WHERE id = ?", (s_alfa,)) or {}).get("trilha") or ""
    checar("Anotado" in texto and "aditivo" in trilha and "Anotador" in trilha, "anotar_no_servico: na trilha, marcada com a conexão", texto)
    checar("não está entre os liberados" in chamar(t_a, "anotar_no_servico", {"servico": "Cobrança da Beta", "texto": "x"}),
           "Serviço de outro cliente: recusa")
    r = rpc("tools/call", {"name": "criar_rascunho", "arguments": {"titulo": "x", "texto": "y"}}, token=t)
    checar("error" in r and "não está liberada" in r["error"]["message"], "ferramenta que escreve sem estar liberada: recusa")
    checar(any(e.get("acao") == "mcp" and "criar_rascunho" in e.get("alvo", "") for e in auditoria)
           and any(e.get("acao") == "mcp-conexao" and "escreve:" in e.get("alvo", "") for e in auditoria), "tudo na auditoria")

    print("\nno Edge")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None
        print("  pulado: playwright não instalado")
    if sync_playwright is not None:
        from test_gravacoes import _porta_livre, _subir_servidor

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
                pag.wait_for_function("() => typeof novaConexaoMcp === 'function'")
                pag.wait_for_timeout(800)
                pag.evaluate("async () => { cfg.mcp = await (await fetch('/api/mcp')).json(); novaConexaoMcp(); }")
                pag.wait_for_selector("[data-mcp-f='criar_rascunho']", timeout=15000)
                checar(pag.locator("#mcp-escrever-caixa").is_hidden(), "o segundo “entendi” só aparece com uma que escreve")
                pag.check("[data-mcp-f='anotar_no_servico']")
                pag.wait_for_timeout(200)
                checar(pag.locator("#mcp-escrever-caixa").is_visible() and pag.locator(f"[data-mcp-c='{alfa}']").count() == 1,
                       "marcada uma que escreve: o “entendi” e os clientes no escopo")
                pag.check(f"[data-mcp-c='{alfa}']")
                pag.check("#mcp-entendi")
                pag.check("#mcp-escrever")
                pag.fill("#mcp-nome", "Pela tela")
                pag.wait_for_timeout(300)
                pag.screenshot(path=str(TMP / "n9-dialogo.png"))
                pag.click("#veu-dialogo [data-dialogo='confirmar']")
                pag.wait_for_selector(".mcp-token", timeout=10000)
                criada = next((c for c in api.estado.mcp.conexoes.listar() if c["nome"] == "Pela tela"), {})
                checar(criada.get("escopo", {}).get("clientes") == [alfa] and "anotar_no_servico" in criada.get("escreve", []),
                       "criada pela tela, com o cliente e a que escreve", criada)
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
