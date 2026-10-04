"""
A Area do cliente (src/area_cliente.py, docs/PLANO-AREA-CLIENTE.md), de ponta
a ponta: o escritorio compartilha a pasta, o cliente entra pelo link com o
codigo do e-mail e acompanha, conversa, manda arquivo e confirma horario.

  - o que NUNCA sai para o cliente: anotacao, etapa e compromisso escondidos,
    documento nao compartilhado, trilha, horas, equipe - procurado no JSON
    inteiro, nao so na tela;
  - o "Ver como o cliente" e a MESMA resposta que o cliente recebe;
  - entrar: link sem e-mail certo nao manda codigo, codigo errado conta
    tentativa, sessao propria (a do cliente nao abre o escritorio, e sem ela
    as rotas do cliente respondem 401), anti-CSRF no que altera;
  - documento com marca d'agua (pagina e PDF baixado), registro de cada coisa
    em "Atividade do cliente" e em "quem acessou";
  - arquivo do cliente: tipo pelo conteudo, antivirus, "Recebidos do cliente";
  - confirmar e remarcar horario, .ics, conversa, resumo publicado, parar
    de compartilhar, e o plano sem o recurso fecha tudo.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_area_cliente.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-areacliente-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def _pdf(texto: str) -> bytes:
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, texto)
    c.showPage()
    c.drawString(72, 720, texto + " (segunda pagina)")
    c.save()
    return buf.getvalue()


def test_unidades() -> None:
    print("\npecas soltas")
    import area_cliente as ac

    checar(ac.mascarar("joao.silva@gmail.com") == "j•••••••••@gmail.com", "o e-mail mascarado diz o dominio, nao o nome")
    nome = ac.nome_de_arquivo("a:b<c>|d?.pdf")
    checar(not any(ch in nome for ch in ':<>|?') and nome.endswith(".pdf"), "o nome do arquivo do cliente perde o que o Windows nao aceita", nome)
    checar(ac.nome_de_arquivo("..\\..\\Windows\\boot.ini") == "boot.ini" and ac.nome_de_arquivo("../../etc/x.pdf") == "x.pdf",
           "e nao sobe pasta nenhuma")
    checar(ac.conferir_envio("rg.exe", b"MZ....") != "", "programa nao entra")
    checar("JPG" in ac.conferir_envio("rg.jpg", b"%PDF-1.4"), "foto que nao e foto: recusada")
    checar(ac.conferir_envio("rg.jpg", b"\xff\xd8\xff\xe0" + b"0" * 50) == "", "foto de verdade entra")
    checar("PDF" in ac.conferir_envio("contrato.pdf", b"MZ isto nao e pdf"), "PDF que nao e PDF: recusado")
    checar("vazio" in ac.conferir_envio("a.pdf", b""), "arquivo vazio: recusado")
    ics = ac.ics("Audiência", "2026-10-22", "14:00", 60, "Fórum, sala 3", "Pasta X", "u1@paulus.ia.br")
    checar("DTSTART:20261022T140000" in ics and "DTEND:20261022T150000" in ics and "Fórum\\, sala 3" in ics, "o .ics tem inicio, fim e lugar", ics)


def test_http() -> None:
    print("\na area do cliente, de ponta a ponta")
    from fastapi.testclient import TestClient
    from pypdf import PdfReader

    import api
    import area_cliente as ac
    import recursos_do_plano

    estado = api.estado
    estado.prefs.dados.setdefault("escritorio", {})["nome"] = "Moura Advogados"
    estado.prefs.dados.setdefault("pessoa", {})["nome"] = "Ana Moura"
    local = TestClient(api.app, headers=api.cabecalho_local())
    area = estado.area_cliente
    emails: list[dict] = []
    area.enviar_email = lambda dados: emails.append(dict(dados)) or ""
    avisos: list[tuple] = []
    area.avisar = lambda titulo, texto: avisos.append((titulo, texto))
    veredito = {"v": "limpo"}
    area.antivirus = lambda caminho: veredito["v"]

    # --- a pasta, com o que e do escritorio e o que pode ser do cliente
    cliente_id = local.post("/api/cadastros", json={"id": None, "dados": {"tipo": "cliente", "nome": "João Cliente",
                                                                           "email": "Joao@Cliente.com"}}).json()["id"]
    sid = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Revisional do contrato", "cadastro_id": cliente_id}}).json()["id"]
    outro = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Inventário da família", "cadastro_id": cliente_id}}).json()["id"]
    alheio = local.post("/api/servicos", json={"id": None, "dados": {"nome": "Pasta de outro cliente"}}).json()["id"]
    local.post(f"/api/servicos/{sid}/anotacoes", json={"texto": "ANOTACAO-SECRETA-123: cliente atrasou honorário"})
    amanha = (date.today() + timedelta(days=1)).isoformat()
    depois = (date.today() + timedelta(days=9)).isoformat()
    local.post(f"/api/servicos/{sid}/etapas", json={"titulo": "Petição protocolada"})
    local.post(f"/api/servicos/{sid}/etapas/0")
    local.post(f"/api/servicos/{sid}/etapas", json={"titulo": "Reunião interna SEGREDO-ETAPA", "quando": depois})
    local.post(f"/api/servicos/{sid}/etapas", json={"titulo": "Enviar RG e comprovante", "quando": depois})
    agora = "2026-10-04T10:00:00"
    audiencia = estado.base.escrever(
        "INSERT INTO compromissos (titulo, data, hora, onde, servico_id, criado_em) VALUES (?, ?, ?, ?, ?, ?)",
        ("Audiência de conciliação", amanha, "14:00", "online", sid, agora))
    estado.base.escrever("UPDATE compromissos SET meet = ? WHERE id = ?", ("https://meet.google.com/abc-defg-hij", audiencia))
    almoco = estado.base.escrever("INSERT INTO compromissos (titulo, data, hora, servico_id, criado_em) VALUES (?, ?, ?, ?, ?)",
                                  ("Almoço interno SEGREDO-COMP", depois, "12:00", sid, agora))
    pasta = estado.servicos.pasta_de(sid, criar=True)
    (pasta / "Petição inicial.pdf").write_bytes(_pdf("Peticao inicial do Joao"))
    (pasta / "Parecer interno.pdf").write_bytes(_pdf("SEGREDO-DOC parecer interno"))
    estado.recarregar()
    s = local.get(f"/api/servicos/{sid}").json()
    arquivos = {a["nome"]: a["sha1"] for a in s["arquivos"]}
    checar({"Petição inicial.pdf", "Parecer interno.pdf"} <= set(arquivos), "os PDFs entraram na pasta", list(arquivos))
    checar(s["cliente"] == {**s["cliente"], "compartilhado": False, "pessoas": 0}, "a pasta sabe que nao esta compartilhada", s["cliente"])

    print("  compartilhar")
    r = local.post(f"/api/servicos/{sid}/cliente/compartilhar", json={"nome": "João Cliente", "email": "joao@cliente.com"})
    checar(r.status_code == 409 and "acesso de fora" in r.json()["detail"], "sem o acesso de fora ligado, nao compartilha (e diz por que)", r.text[:200])
    estado.prefs.dados["acesso_remoto"].update({"ligado": True, "hostname": "moura.paulus.ia.br"})
    r = local.post(f"/api/servicos/{sid}/cliente/compartilhar", json={"nome": "João Cliente", "email": "Joao@Cliente.com", "cadastro_id": cliente_id})
    d = r.json()
    link = d["pessoa"]["link"]
    token = link.rsplit("/", 1)[-1]
    checar(r.status_code == 200 and d["email_enviado"] and link.startswith("https://moura.paulus.ia.br/cliente/"), "compartilhou e mandou o convite", d)
    convite = emails[-1]
    checar(convite["tipo"] == "convite" and convite["para"] == "joao@cliente.com" and convite["advogado"] == "Ana Moura"
           and convite["pasta"] == "Revisional do contrato" and convite["link"] == link and convite["escritorio"] == "Moura Advogados",
           "o convite leva o tipo, o link, quem compartilhou e a pasta (o texto e do Worker)", convite)
    r2 = local.post(f"/api/servicos/{outro}/cliente/compartilhar", json={"nome": "João", "email": "joao@cliente.com"}).json()
    checar(r2["pessoa"]["link"] == link, "a mesma pessoa em outra pasta: o mesmo link (um link por cliente)")
    r = local.post(f"/api/servicos/{sid}/cliente/compartilhar", json={"nome": "X", "email": "nao-e-email"})
    checar(r.status_code == 400, "e-mail torto: 400")
    checar(any((e.get("tipo") == "cliente_compartilhou") for e in local.get(f"/api/servicos/{sid}").json()["trilha"]),
           "a trilha da pasta guarda o compartilhar")

    print("  o olhinho, a pendencia, a confirmacao e o documento")
    checar(local.post(f"/api/servicos/{sid}/cliente/etapas/1", json={"oculta": True}).status_code == 200, "esconder uma etapa")
    r = local.post(f"/api/servicos/{sid}/cliente/etapas/2", json={"do_cliente": True})
    checar(r.status_code == 200 and r.json()["etapas"][2].get("cliente") is True, "a etapa vira do cliente")
    tarefa = estado.base.um("SELECT responsavel_id FROM tarefas WHERE servico_id = ? AND titulo = ?", (sid, "Enviar RG e comprovante"))
    checar(tarefa is not None and tarefa["responsavel_id"] is None, "a etapa do cliente nao cai na Agenda de ninguem da equipe", tarefa)
    checar(local.post(f"/api/servicos/{sid}/cliente/compromissos/{almoco}", json={"oculto": True}).status_code == 200, "esconder um compromisso")
    checar(local.post(f"/api/servicos/{sid}/cliente/compromissos/{audiencia}", json={"confirmar": True}).status_code == 200,
           "pedir que o cliente confirme a audiencia")
    r = local.post(f"/api/servicos/{sid}/cliente/documentos/{arquivos['Petição inicial.pdf']}", json={"compartilhado": True})
    checar(r.status_code == 200 and r.json()["documentos"] == [arquivos["Petição inicial.pdf"]], "compartilhar um documento")
    checar(local.post(f"/api/servicos/{sid}/cliente/documentos/{'0' * 40}", json={"compartilhado": True}).status_code == 404,
           "documento que nao e da pasta: 404")
    checar(local.post(f"/api/servicos/{alheio}/cliente/compromissos/{audiencia}", json={"oculto": True}).status_code == 404,
           "compromisso de outra pasta: 404")

    print("  a lista fechada: o que o cliente NAO ve")
    previa = local.get(f"/api/servicos/{sid}/como-cliente").json()
    bruto = json.dumps(previa, ensure_ascii=False)
    for proibido in ("ANOTACAO-SECRETA", "SEGREDO-ETAPA", "SEGREDO-COMP", "Parecer interno", "SEGREDO-DOC", "honorário"):
        checar(proibido not in bruto, f"'{proibido}' nao aparece em lugar nenhum da resposta")
    checar(set(previa) == {"pasta", "escritorio", "responsavel", "resumo", "pendencias", "datas", "andamento", "documentos",
                           "mensagens", "previa"}, "as chaves sao as da lista fechada", sorted(previa))
    checar(set(previa["pasta"]) == {"id", "nome", "status", "status_rotulo", "progresso"}, "a pasta: so nome, status e progresso")
    checar([e["titulo"] for e in previa["andamento"]] == ["Petição protocolada", "Enviar RG e comprovante"]
           and previa["pasta"]["progresso"] == 50, "o andamento: as etapas visiveis, e o progresso conta so elas", previa["andamento"])
    pend = {p["pendencia"]: p for p in previa["pendencias"]}
    checar(set(pend) == {"fazer", "confirmar"} and pend["fazer"]["titulo"] == "Enviar RG e comprovante"
           and pend["confirmar"]["id"] == audiencia, "Para voce: a etapa do cliente e a audiencia a confirmar", previa["pendencias"])
    aud = next(x for x in previa["datas"] if x.get("id") == audiencia)
    checar(aud["sala"] == "https://meet.google.com/abc-defg-hij" and aud["onde"] == "Online", "a audiencia online leva a sala", aud)
    checar([x["nome"] for x in previa["documentos"]] == ["Petição inicial.pdf"], "so o documento compartilhado", previa["documentos"])

    print("  entrar")
    fora = lambda ip="200.9.9.9": TestClient(api.app, base_url="https://moura.paulus.ia.br", headers={"Cf-Connecting-IP": ip})  # noqa: E731
    f = fora()
    r = f.get(f"/cliente/{token}")
    checar(r.status_code == 200 and "cliente.js" in r.text and r.headers.get("content-security-policy"),
           "a pagina do cliente abre de fora, com os cabecalhos de seguranca")
    checar(f.get("/js/cliente.js").status_code == 200 and f.get("/css/cliente.css").status_code == 200, "e o que ela carrega, sem sessao")
    checar(f.get("/js/10-servicos.js").status_code != 200, "o resto do programa, nao")
    checar(f.get("/api/cliente/eu").status_code == 401, "sem entrar: 401")
    checar(f.get(f"/api/cliente/pastas/{sid}").status_code == 401, "a pasta sem entrar: 401")
    checar(f.post("/api/cliente/entrar", json={"token": "link-inventado", "email": "joao@cliente.com"}).status_code == 404, "link inventado: 404")
    n = len(emails)
    r = f.post("/api/cliente/entrar", json={"token": token, "email": "outra@pessoa.com"})
    checar(r.status_code == 200 and r.json()["ok"] and len(emails) == n, "outro e-mail: a mesma resposta, e nenhum codigo sai", r.text)
    r = f.post("/api/cliente/entrar", json={"token": token, "email": " JOAO@cliente.com "})
    checar(r.status_code == 200 and r.json()["para"] == "j•••@cliente.com" and emails[-1]["tipo"] == "codigo", "o e-mail certo: o codigo vai", r.text)
    codigo = emails[-1]["codigo"]
    errado = "000000" if codigo != "000000" else "111111"
    r = f.post("/api/cliente/codigo", json={"token": token, "codigo": errado})
    checar(r.status_code == 400 and "restam 4" in r.json()["detail"], "codigo errado conta tentativa", r.text)
    r = f.post("/api/cliente/codigo", json={"token": token, "codigo": codigo, "lembrar": True})
    checar(r.status_code == 200 and ac.COOKIE in r.cookies, "o codigo certo abre a sessao", r.text)
    cookie = r.headers.get("set-cookie", "")
    checar("HttpOnly" in cookie and "Secure" in cookie and "samesite=strict" in cookie.lower() and "Max-Age=2592000" in cookie,
           "o cookie: HttpOnly, Secure, SameSite e 30 dias com 'lembrar'", cookie)
    csrf = r.json()["csrf"]
    checar(f.post("/api/cliente/codigo", json={"token": token, "codigo": codigo}).status_code == 400, "o codigo vale uma vez so")
    eu = f.get("/api/cliente/eu").json()
    checar(sorted(p["nome"] for p in eu["pastas"]) == ["Inventário da família", "Revisional do contrato"], "o cliente ve as duas pastas dele", eu)

    print("  a pasta, para o cliente")
    v = f.get(f"/api/cliente/pastas/{sid}").json()
    checar({k: x for k, x in v.items()} == {k: x for k, x in previa.items() if k != "previa"},
           "o cliente recebe exatamente o que o 'Ver como o cliente' mostrou")
    checar(f.get(f"/api/cliente/pastas/{alheio}").status_code == 404, "pasta de outro cliente: 404")
    checar(f.get("/api/servicos").status_code == 401 and f.get(f"/api/servicos/{sid}").status_code == 401,
           "o cookie do cliente nao abre nada do escritorio")
    checar(f.get(f"/api/servicos/{sid}/como-cliente").status_code == 401, "nem a previa do escritorio")

    print("  documentos, com marca d'agua")
    sha = arquivos["Petição inicial.pdf"]
    r = f.get(f"/api/cliente/pastas/{sid}/documentos/{sha}/pagina?n=1")
    checar(r.status_code == 200 and r.headers["content-type"] == "image/png" and r.headers.get("x-paginas") == "2",
           "a pagina vem desenhada, e diz quantas sao", r.headers.get("x-paginas"))
    from PIL import Image

    import documento

    cru = Image.open(io.BytesIO(documento.pagina_png((pasta / "Petição inicial.pdf").read_bytes(), 1, 1100))).convert("RGB")
    marcada = Image.open(io.BytesIO(r.content)).convert("RGB")
    bc, bm = cru.tobytes(), marcada.tobytes()
    diferentes = sum(1 for i in range(0, len(bc), 3) if bc[i:i + 3] != bm[i:i + 3])
    checar(cru.size == marcada.size and diferentes > cru.size[0] * cru.size[1] * 0.02, "a pagina tem a marca d'agua por cima", diferentes)
    checar(f.get(f"/api/cliente/pastas/{sid}/documentos/{arquivos['Parecer interno.pdf']}/pagina").status_code == 404,
           "documento nao compartilhado: 404, mesmo sabendo o sha1")
    r = f.get(f"/api/cliente/pastas/{sid}/documentos/{sha}/baixar")
    texto = "".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(r.content)).pages)
    checar(r.status_code == 200 and r.content.startswith(b"%PDF") and "João Cliente" in texto and "Peticao inicial" in texto,
           "o PDF baixado leva o nome do cliente em cada pagina", texto[:200])

    print("  o que o cliente faz")
    checar(f.post(f"/api/cliente/pastas/{sid}/mensagens", json={"texto": "Oi"}).status_code == 403, "sem o token anti-CSRF: 403")
    f.headers["x-paulus-csrf"] = csrf
    r = f.post(f"/api/cliente/pastas/{sid}/mensagens", json={"texto": "Bom dia, quando sai a sentença?"})
    checar(r.status_code == 200 and r.json()["mensagens"][-1]["de"] == "cliente", "o cliente escreve")
    checar(avisos and "João Cliente" in avisos[-1][0], "o escritorio recebe o aviso", avisos[-1:])
    checar(local.get("/api/servicos").json()["cliente_nao_lidas"].get(str(sid)) == 1, "a grade de Servicos ve a mensagem nova")
    r = f.post(f"/api/cliente/pastas/{sid}/enviar?nome=programa.exe&etapa=2", content=b"MZ\x90\x00")
    checar(r.status_code == 400 and "tipo de arquivo" in r.json()["detail"], "programa nao entra", r.text)
    veredito["v"] = "ameaca"
    r = f.post(f"/api/cliente/pastas/{sid}/enviar?nome=rg.jpg&etapa=2", content=b"\xff\xd8\xff\xe0" + b"1" * 500)
    checar(r.status_code == 422 and not (pasta / ac.PASTA_RECEBIDOS / "rg.jpg").exists(), "o antivirus barrou: nada fica na pasta", r.text)
    veredito["v"] = "limpo"
    r = f.post(f"/api/cliente/pastas/{sid}/enviar?nome=rg.jpg&etapa=2", content=b"\xff\xd8\xff\xe0" + b"1" * 500)
    checar(r.status_code == 200 and (pasta / ac.PASTA_RECEBIDOS / "rg.jpg").exists(), "a foto do RG chega em 'Recebidos do cliente'", r.text[:300])
    v = r.json()["visao"]
    checar(not any(p["pendencia"] == "fazer" for p in v["pendencias"]) and v["andamento"][1]["feita"], "e a pendencia dela se fecha sozinha")
    checar(v["mensagens"][-1]["anexo"] == "rg.jpg", "a conversa diz o que chegou")
    r = f.post(f"/api/cliente/pastas/{sid}/enviar?nome=rg.jpg", content=b"\xff\xd8\xff\xe0" + b"2" * 500)
    checar(r.json()["nome"] == "rg (2).jpg", "o mesmo nome de novo nao passa por cima", r.json().get("nome"))
    (pasta / "contrato-cliente.txt").unlink(missing_ok=True)
    r = f.post(f"/api/cliente/pastas/{sid}/enviar?nome=contrato-cliente.txt", content="Contrato que o cliente mandou.".encode("utf-8"))
    ligados = [a["nome"] for a in local.get(f"/api/servicos/{sid}").json()["arquivos"]]
    checar(r.status_code == 200 and "contrato-cliente.txt" in ligados, "o que o Acervo le entra na pasta do servico", ligados)
    r = f.post(f"/api/cliente/pastas/{sid}/compromissos/{audiencia}/responder", json={"resposta": "remarcar"})
    checar(r.status_code == 400, "remarcar sem dizer quando: 400")
    r = f.post(f"/api/cliente/pastas/{sid}/compromissos/{audiencia}/responder", json={"resposta": "remarcar", "sugestao": "quinta à tarde"})
    checar(r.status_code == 200 and any(p["pendencia"] == "confirmar" for p in r.json()["pendencias"]), "pediu para remarcar: continua pendente")
    conf = local.get(f"/api/servicos/{sid}").json()["cliente"]["confirmacoes"][str(audiencia)]
    checar(conf["resposta"] == "remarcar" and conf["sugestao"] == "quinta à tarde", "o escritorio ve a sugestao na pasta", conf)
    r = f.post(f"/api/cliente/pastas/{sid}/compromissos/{audiencia}/responder", json={"resposta": "confirmado"})
    checar(r.status_code == 200 and not r.json()["pendencias"], "confirmou: nada pendente")
    checar(f.post(f"/api/cliente/pastas/{sid}/compromissos/{almoco}/responder", json={"resposta": "confirmado"}).status_code == 404,
           "compromisso escondido nao se responde")
    r = f.get(f"/api/cliente/pastas/{sid}/compromissos/{audiencia}/agenda")
    checar(r.status_code == 200 and "SUMMARY:Audiência de conciliação" in r.text and "meet.google.com" in r.text, "o horario vai para a agenda (.ics)")
    checar(f.post("/api/cliente/evento", json={"tipo": "imprimiu", "servico_id": sid, "alvo": "Petição inicial.pdf"}).status_code == 200,
           "imprimir fica registrado")

    print("  o escritorio")
    r = local.post(f"/api/servicos/{sid}/cliente/mensagens", json={"texto": "A sentença sai em novembro."})
    checar(r.status_code == 200 and r.json()["avisados"] == 1 and emails[-1]["tipo"] == "mensagem" and "texto" not in emails[-1],
           "a resposta avisa o cliente por e-mail - sem o texto", emails[-1])
    checar(local.get("/api/servicos").json()["cliente_nao_lidas"].get(str(sid)) is None, "responder marca como lidas")
    r = local.post(f"/api/servicos/{sid}/cliente/resumo", json={"texto": "Seu processo está na fase de conciliação."})
    checar(r.status_code == 200 and f.get(f"/api/cliente/pastas/{sid}").json()["resumo"]["texto"].startswith("Seu processo"),
           "o resumo publicado aparece para o cliente")
    ia = area.texto_para_ia(sid)
    checar("ANOTACAO" not in ia and "SEGREDO" not in ia and "Petição inicial.pdf" in ia, "a IA do resumo le so o que o cliente ve", ia)
    ativ = local.get(f"/api/servicos/{sid}/cliente/atividade").json()["atividade"]
    acoes = {a["acao"] for a in ativ}
    checar({"entrou", "abriu_pasta", "abriu", "baixou", "escreveu", "enviou", "envio_barrado", "remarcar", "confirmou", "agenda",
            "imprimiu", "email_errado", "codigo_errado"} <= acoes, "a atividade do cliente tem cada coisa", sorted(acoes))
    linhas = estado.acesso_de_fora.auditoria.filtrar(pessoa="cliente")
    checar(any(l["acao"] == "cliente_baixou" and "Petição inicial.pdf" in l["alvo"] for l in linhas)
           and estado.acesso_de_fora.auditoria.verificar()["integro"], "e o registro encadeado de 'quem acessou' tambem")

    print("  limites")
    g = fora("200.7.7.7")
    for _ in range(4):
        g.post("/api/cliente/entrar", json={"token": token, "email": "joao@cliente.com"})
    r = g.post("/api/cliente/entrar", json={"token": token, "email": "joao@cliente.com"})
    checar(r.status_code == 429, "mais de 5 codigos na hora: 429", r.status_code)
    for _ in range(5):
        g.post("/api/cliente/codigo", json={"token": token, "codigo": "999999" if emails[-1]["codigo"] != "999999" else "888888"})
    r = g.post("/api/cliente/codigo", json={"token": token, "codigo": emails[-1]["codigo"]})
    checar(r.status_code == 400 and "peça outro" in r.json()["detail"], "5 erros: nem o codigo certo vale mais", r.text)

    print("  parar de compartilhar e o plano")
    pessoa_id = local.get(f"/api/servicos/{sid}/cliente").json()["pessoas"][0]["id"]
    checar(local.post(f"/api/servicos/{sid}/cliente/parar", json={"pessoa_id": pessoa_id}).status_code == 200, "parar de compartilhar")
    checar(f.get(f"/api/cliente/pastas/{sid}").status_code == 404, "na hora: a pasta some para o cliente")
    checar([p["nome"] for p in f.get("/api/cliente/eu").json()["pastas"]] == ["Inventário da família"], "e a outra continua")
    original = recursos_do_plano.pode
    recursos_do_plano.pode = lambda e, chave: chave != "pagina_cliente"
    try:
        checar(f.get("/api/cliente/eu").status_code == 403, "plano sem a area do cliente: o cliente nao entra")
        r = local.post(f"/api/servicos/{outro}/cliente/compartilhar", json={"nome": "Maria", "email": "maria@x.com"})
        checar(r.status_code == 403, "e o escritorio nao compartilha", r.status_code)
    finally:
        recursos_do_plano.pode = original
    estado.prefs.dados["acesso_remoto"]["ligado"] = False
    checar(f.get("/api/cliente/eu").status_code == 403, "acesso de fora desligado: ninguem de fora entra, nem o cliente")
    r = f.post("/api/cliente/sair")
    checar(r.status_code == 403, "nem para sair (o portao fecha antes)")


def main() -> int:
    print("=" * 55)
    print("  PAULUS - Area do cliente")
    print("=" * 55)
    test_unidades()
    test_http()
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
