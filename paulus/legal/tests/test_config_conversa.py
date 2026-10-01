"""
As Configurações pela conversa (T5 do pacote de telas; src/config_pela_conversa.py,
js/89-config-na-conversa.js).

  - a frase vira a seção e as mudanças, por regra; o que é de outra tela
    (agenda, cadastro, a pergunta sobre o contrato) não vira
  - assinar, enviar e a nuvem a conversa não liga
  - na tela: a seção abre na coluna de 460 px com o selo "novo", o rodapé
    conta as mudanças, e nada é gravado antes do "Salvar alterações"
  - a Lixeira restaura pela conversa, o lembrete se guarda pela coluna

    python tests/test_config_conversa.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-cfn-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

import config_pela_conversa as cpc  # noqa: E402

CAPTURAS = Path(os.environ.get("PAULUS_CAPTURAS", str(TMP)))
_falhas: list[str] = []


def checar(condicao, descricao: str, detalhe="") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHOU  {descricao}  -> {detalhe}")
        _falhas.append(descricao)


FRASES = {
    "troquei de número, agora é (94) 99123-4567. e já liga o papel timbrado nos PDFs": "perfil",
    "para de me avisar de pausa toda hora, e coloca o tema claro durante o dia": "aparencia",
    "deixa o paulus organizar as pastas sozinho, sem ficar me pedindo sim toda hora": "assistente",
    "as respostas estão demorando muito. dá pra deixar mais rápido?": "modelos",
    "o computador tá travando desde de manhã, é o paulus?": "desempenho",
    "faz um teste com os modelos instalados pra ver qual vale mais a pena nessa máquina": "desempenho",
    "manda no whatsapp do Wagner que a audiência foi remarcada pra quinta, 14h": "conexoes",
    "quero usar o paulus dentro do word pra conferir as citações da contestação": "word",
    "consigo usar o paulus do celular quando estiver no fórum?": "acesso",
    "convida a Ana Beatriz pra equipe, o email dela é anabeatriz.moura@gmail.com": "vinculos",
    "se esse computador estragar eu perco tudo?": "backup",
    "lembra que aqui no escritório a gente sempre pede justiça gratuita pros clientes da cooperativa": "aprendizado",
    "tira gravações e assinatura do menu, a gente não usa": "menu",
    "o paulus tá atualizado?": "plano",
    "apaguei sem querer o documento B do teste C5, dá pra voltar?": "lixeira",
}

NAO_SAO = ["qual a multa do contrato?", "lembra que amanhã tenho audiência às 14h", "abra as configurações",
           "o telefone do cliente João é (62) 99999-0000", "me lembra de pagar o boleto", "me avisa da audiência amanhã às 9h",
           "marque uma reunião com a Priscila sexta às 10h"]


def test_regras() -> None:
    print("\nas regras")
    for frase, secao in FRASES.items():
        lido = cpc.ler(frase)
        checar(lido and lido["secao"] == secao, f"“{frase[:48]}…” -> {secao}", lido)
    for frase in NAO_SAO:
        checar(cpc.ler(frase) is None, f"“{frase}” não é configuração", cpc.ler(frase))
    p = cpc.ler(FRASES and "troquei de número, agora é (94) 99123-4567. e já liga o papel timbrado nos PDFs")
    checar(p["mudancas"] == [{"chave": "pessoa.telefone", "valor": "(94) 99123-4567"}, {"chave": "timbre_no_pdf", "valor": True}],
           "o telefone e o timbre", p)
    r = cpc.ler("deixa o paulus assinar sem revisar")
    checar(r["mudancas"] == [] and r["recusadas"] == ["assinar"], "assinar sem revisar a conversa não liga", r)
    checar(cpc.lembrete_da_frase("aqui no escritório a gente sempre pede justiça gratuita pros clientes da cooperativa", ["Cooperativa Rio Fresco"])
           == "Para os clientes da Cooperativa Rio Fresco, pedir justiça gratuita.", "o lembrete como regra da casa")
    checar(cpc.recado_do_whatsapp("Wagner Antônio", "a audiência foi remarcada pra quinta, 14h").startswith("Olá, Wagner. A audiência foi remarcada para quinta-feira, "),
           "o recado do WhatsApp com o dia")


def test_frases() -> None:
    print("\nas frases, com os dados conhecidos")
    prefs = {"pessoa": {"nome": "Matheus Uener", "oab": "000000", "telefone": "(94) 98806-7392", "endereco": "Av. Paraná, 1965"},
             "timbre_no_pdf": False, "autonomia": {"assinar": False, "enviar_mensagem": False}, "modulos": {}}
    frase, p = cpc.proposta(cpc.ler("troquei de número, agora é (94) 99123-4567. e já liga o papel timbrado nos PDFs"), {"prefs": prefs})
    checar(frase.startswith("Abri Meus dados ao lado com as duas mudanças marcadas.") and "`000000`" in frase, "Meus dados: as duas mudanças e a OAB", frase)
    checar([l["tom"] for l in p["linhas"]] == ["ok", "ok", "aviso"] and p["linhas"][0]["antes"] == "(94) 98806-7392", "as três linhas", p["linhas"])
    checar([a["rotulo"] for a in p["acoes"]] == ["Vou informar a OAB", "Salvar só o telefone"] and p["titulo_conversa"] == "Troque meu telefone", "os botões e o título", p["acoes"])
    frase, p = cpc.proposta(cpc.ler("deixa o paulus organizar as pastas sozinho, sem ficar me pedindo sim toda hora"), {"prefs": prefs})
    checar(frase.startswith("Liguei \"Mover arquivos sem pedir\" ao lado.") and p["linhas"][1]["depois"] == "continuam pedindo o seu sim", "Assistente: mover sem pedir, assinar fica", p["linhas"])
    frase, p = cpc.proposta(cpc.ler("tira gravações e assinatura do menu, a gente não usa"), {"prefs": prefs})
    checar(frase.startswith("Desliguei os dois ao lado.") and [l["depois"] for l in p["linhas"]] == ["fora do menu", "fora do menu"], "Módulos", frase)
    frase, p = cpc.proposta(cpc.ler("o paulus tá atualizado?"), {"prefs": prefs, "atualizacao": {"atual": "0.9.23", "ultima_consulta": "2026-10-01T05:09:00", "anuncio": {"nova": False}}})
    checar(frase.startswith("Está. Você usa a versão 0.9.23, a mais nova"), "Versão", frase)
    frase, p = cpc.proposta(cpc.ler("se esse computador estragar eu perco tudo?"), {"prefs": prefs, "backup": {}, "drives": ["G:\\Meu Drive"]})
    checar("Já deixei a pasta sugerida ao lado" in frase and p["extra"]["pasta_sugerida"] == "G:\\Meu Drive\\PAULUS Backup"
           and p["linhas"][1]["depois"] == "Google Drive › PAULUS Backup", "Backup: a pasta no Drive", p["linhas"])
    itens = [{"id": 1, "titulo": "Teste C5 — documento B", "tipo": "documento", "tipo_rotulo": "Documento", "apagado_em": "2026-10-01T05:20:10", "dias_restantes": 30},
             {"id": 2, "titulo": "Teste C5 — documento A", "tipo": "documento", "tipo_rotulo": "Documento", "apagado_em": "2026-10-01T05:20:40", "dias_restantes": 30},
             {"id": 3, "titulo": "Programa", "tipo": "conversa", "tipo_rotulo": "Conversa", "apagado_em": "2026-10-01T05:38:00", "dias_restantes": 30}]
    frase, p = cpc.proposta(cpc.ler("apaguei sem querer o documento B do teste C5, dá pra voltar?"), {"prefs": prefs, "lixeira": itens})
    checar(p["extra"]["achados"][0]["id"] == 1 and p["extra"]["vizinhos"][0]["id"] == 2 and p["extra"]["busca"] == "Teste C5", "Lixeira: o documento B e o A do mesmo minuto", p["extra"])


class _Modelo:
    model = "duble"

    def ask(self, *_a, **_k):
        return "resposta"


def test_tela() -> None:
    print("\nna tela (Edge pelo Playwright)")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  pulado: playwright não instalado")
        return
    import api
    from test_gravacoes import _porta_livre, _subir_servidor

    e = api.estado
    e.cliente_para = lambda *_a, **_k: _Modelo()
    api.check_ollama = lambda *_a, **_k: (True, "ok")
    e.prefs.atualizar({"pessoa": {"nome": "Matheus Uener", "oab": "000000", "telefone": "(94) 98806-7392", "endereco": "Avenida Paraná, 1965"},
                       "timbre_no_pdf": False})
    e.cadastros.salvar({"tipo": "cliente", "nome": "Cooperativa Rio Fresco"})
    tid = e.tarefas.salvar({"titulo": "Teste C5 — documento B"})
    e.lixeira.apagar_linha("tarefa", tid, "Teste C5 — documento B", "Agenda · Tarefas")
    porta = _porta_livre()
    _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"
    with sync_playwright() as p:
        try:
            nav = p.chromium.launch(channel="msedge")
        except Exception as exc:  # noqa: BLE001
            print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            return
        pag = nav.new_page(viewport={"width": 1984, "height": 1064})
        pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); localStorage.setItem('paulus.tema', 'escuro'); } catch (e) {}")
        erros: list[str] = []
        pag.on("pageerror", lambda x: erros.append(str(x)))
        pag.goto(base + "/entrar-local?chave=" + e.acesso.chave, wait_until="networkidle")
        pag.wait_for_timeout(800)

        def pedir(frase: str, secao: str) -> None:
            pag.click("#nova")
            pag.wait_for_timeout(400)
            pag.fill("#pedido", frase)
            pag.click("#enviar")
            pag.wait_for_selector(f"#lado-ferramenta [data-fl-tipo='config'][data-cfn-secao='{secao}']", timeout=20000)
            pag.wait_for_timeout(900)

        # Meus dados: telefone e timbre marcados, a OAB pede atenção, nada gravado ainda.
        pedir("troquei de número, agora é (94) 99123-4567. e já liga o papel timbrado nos PDFs", "perfil")
        t = pag.evaluate("""() => ({frase: [...document.querySelectorAll('#centro .resposta .texto')].map(t => t.textContent).pop(),
          linhas: document.querySelectorAll('#centro .cfc-linha').length,
          tel: document.querySelector('#lado-ferramenta [data-cfg-campo="pessoa.telefone"]').value,
          novos: [...document.querySelectorAll('#lado-ferramenta .cfn-novo')].length,
          atencao: Boolean(document.querySelector('#lado-ferramenta .cfn-atencao')),
          pe: document.querySelector('#lado-ferramenta .cfn-resumo').textContent,
          largura: document.getElementById('lado-ferramenta').getBoundingClientRect().width,
          meta: document.getElementById('conversa-meta').textContent,
          titulo: document.getElementById('conversa-titulo').textContent})""")
        checar(t["frase"].startswith("Abri Meus dados ao lado com as duas mudanças") and t["linhas"] == 3, "a frase e as três linhas", t)
        checar(t["tel"] == "(94) 99123-4567" and t["novos"] == 2 and t["atencao"], "o telefone novo, os dois selos e a OAB marcada", t)
        checar(t["pe"] == "2 mudanças · 1 campo pede atenção" and abs(t["largura"] - 460) < 30, "o rodapé e a coluna de 460", t)
        checar(t["meta"] == "Configurações › Meus dados · 2 mudanças por salvar" and t["titulo"] == "Troque meu telefone", "o título e o caminho", t)
        checar((e.prefs.dados.get("pessoa") or {}).get("telefone") == "(94) 98806-7392" and not e.prefs.dados.get("timbre_no_pdf"), "nada gravado antes do clique")
        pag.screenshot(path=str(CAPTURAS / "t5-meus-dados.png"))
        pag.click("#centro .cfc-acoes button:nth-child(2)")  # Salvar só o telefone
        pag.wait_for_selector(".nota-feito", timeout=8000)
        salvo = e.prefs.dados
        checar("".join(c for c in salvo["pessoa"]["telefone"] if c.isdigit()) == "94991234567" and not salvo.get("timbre_no_pdf"),
               "“Salvar só o telefone” grava o telefone e deixa o timbre", salvo["pessoa"])
        nota = pag.evaluate("() => (([...document.querySelectorAll('.nota-feito')].pop() || {}).textContent || '')")
        checar("Salvei em Meus dados: telefone" in nota, "a nota na conversa", nota)

        # Aparência: tema e bem-estar pendentes até salvar.
        pedir("para de me avisar de pausa toda hora, e coloca o tema claro durante o dia", "aparencia")
        a = pag.evaluate("""() => ({tema: localStorage.getItem('paulus.tema'), pe: document.querySelector('#lado-ferramenta .cfn-resumo').textContent,
          selos: document.querySelectorAll('#lado-ferramenta .cfn-novo').length})""")
        checar(a["tema"] == "escuro" and a["pe"] == "2 mudanças · tema e bem-estar" and a["selos"] == 2, "o tema e o bem-estar esperam o Salvar", a)
        pag.screenshot(path=str(CAPTURAS / "t5-aparencia.png"))
        pag.click("#lado-ferramenta [data-cfn-salvar]")
        pag.wait_for_function("() => (([...document.querySelectorAll('.nota-feito')].pop() || {}).textContent || '').includes('Aparência')", timeout=8000)
        checar(pag.evaluate("() => localStorage.getItem('paulus.tema')") == "auto" and e.prefs.dados["avisos_tipos"]["bem_estar"] is False,
               "salvo: Seguir o Windows e o bem-estar desligado")

        # Módulos.
        pedir("tira gravações e assinatura do menu, a gente não usa", "menu")
        pag.screenshot(path=str(CAPTURAS / "t5-modulos.png"))
        pag.click("#lado-ferramenta [data-cfn-salvar]")
        pag.wait_for_function("() => (([...document.querySelectorAll('.nota-feito')].pop() || {}).textContent || '').includes('Módulos')", timeout=8000)
        mods = e.prefs.dados.get("modulos") or {}
        checar(mods.get("gravacoes") is False and mods.get("assinatura") is False, "Gravações e Assinatura fora do menu", mods)

        # Assistente: assinar sem revisar a conversa não liga.
        pedir("deixa o paulus assinar sem revisar", "assistente")
        s = pag.evaluate("""() => ({frase: [...document.querySelectorAll('#centro .resposta .texto')].map(t => t.textContent).pop(),
          destaque: Boolean(document.querySelector('#lado-ferramenta .cfn-destaque')),
          ligado: document.querySelector('#lado-ferramenta [data-cfg-liga="autonomia.assinar"]').classList.contains('on')})""")
        checar("eu não ligo pela conversa" in s["frase"] and s["destaque"] and not s["ligado"], "assinar fica com você", s)
        pag.screenshot(path=str(CAPTURAS / "t5-assistente.png"))

        # Lixeira: restaurar pela conversa.
        pedir("apaguei sem querer o documento B do teste C5, dá pra voltar?", "lixeira")
        lx = pag.evaluate("""() => ({frase: [...document.querySelectorAll('#centro .resposta .texto')].map(t => t.textContent).pop(),
          busca: document.querySelector('#lado-ferramenta [data-cfn-busca]').value, achado: document.querySelectorAll('#lado-ferramenta .cfn-achado').length})""")
        checar(lx["frase"].startswith("Dá. Ele está na Lixeira") and lx["busca"] == "Teste C5" and lx["achado"] == 1, "a Lixeira achou e destacou", lx)
        pag.screenshot(path=str(CAPTURAS / "t5-lixeira.png"))
        pag.click("#centro [data-cfc-restaurar]")
        pag.wait_for_function("() => (([...document.querySelectorAll('.nota-feito')].pop() || {}).textContent || '').startsWith('Restaurei')", timeout=8000)
        checar(e.tarefas.obter(tid) is not None, "a tarefa voltou")

        # Biblioteca: o lembrete se guarda pela coluna.
        pedir("lembra que aqui no escritório a gente sempre pede justiça gratuita pros clientes da cooperativa", "aprendizado")
        texto = pag.evaluate("() => document.getElementById('cfn-lembrete').value")
        checar(texto == "Para os clientes da Cooperativa Rio Fresco, pedir justiça gratuita.", "o lembrete na coluna", texto)
        pag.screenshot(path=str(CAPTURAS / "t5-biblioteca.png"))
        pag.click("#lado-ferramenta [data-cfn-lembrete]")
        pag.wait_for_function("() => (([...document.querySelectorAll('.nota-feito')].pop() || {}).textContent || '').startsWith('Guardei o lembrete')", timeout=8000)
        checar(any("justiça gratuita" in c["texto"] for c in e.contextos.listar()) if hasattr(e, "contextos") else True, "o lembrete guardado")

        # As que só mostram: abrem sem erro, com o rodapé da seção.
        for frase, secao, captura, pe in [("o paulus tá atualizado?", "plano", "t5-versao", "Verificar agora"),
                                          ("o computador tá travando desde de manhã, é o paulus?", "desempenho", "t5-desempenho", "Gerar diagnóstico"),
                                          ("se esse computador estragar eu perco tudo?", "backup", "t5-backup", "Salvar e fazer backup agora"),
                                          ("quero usar o paulus dentro do word pra conferir as citações da contestação", "word", "t5-word", ""),
                                          ("consigo usar o paulus do celular quando estiver no fórum?", "acesso", "t5-acesso", ""),
                                          ("convida a Ana Beatriz pra equipe, o email dela é anabeatriz.moura@gmail.com", "vinculos", "t5-escritorio", "Convidar pela internet"),
                                          ("manda no whatsapp do Wagner que a audiência foi remarcada pra quinta, 14h", "conexoes", "t5-conexoes", "Abrir WhatsApp Web")]:
            pedir(frase, secao)
            texto_pe = pag.evaluate("() => document.querySelector('#lado-ferramenta [data-cfn-pe]').textContent")
            checar(not pe or pe in texto_pe, f"{secao}: a coluna abre com o rodapé dela", texto_pe)
            pag.screenshot(path=str(CAPTURAS / (captura + ".png")))

        pag.set_viewport_size({"width": 390, "height": 844})
        pag.wait_for_timeout(500)
        checar(pag.evaluate("() => document.documentElement.scrollWidth") <= 392, "sem rolagem horizontal em 390 px")
        checar(not erros, "nenhum erro de JavaScript", erros[:3])
        nav.close()


if __name__ == "__main__":
    test_regras()
    test_frases()
    test_tela()
    print("\n" + "=" * 60)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print("    - " + f)
        sys.exit(1)
    print("  todos os testes passaram")
