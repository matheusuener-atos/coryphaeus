"""
A saudacao das telas de entrar (src/saudacao.py, saudar_entrada;
config/saudacoes_entrada.json; js/entrada-saudacao.js), sem rede:

  - o titulo e sempre "Paulus está te esperando." (PAVLVS e a marca);
  - toda tela tem frase, os ids sao unicos e nenhuma frase fica com buraco;
  - a frase de boas-vindas segue a hora, o dia e o calendario (manha, Natal);
  - as telas serias (codigo, chave, erro) so tem frases serias e fixas;
  - o convite usa o nome e o escritorio quando vem os dois;
  - a mesma tela, aberta seguidas vezes, nao repete a frase;
  - nada do escritorio entra: a rota abre sem sessao, de fora e com o
    programa travado, e a resposta so tem o titulo, a frase e os ids;
  - a pagina de volta do Google e a de fora da janela tem o titulo novo.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_entrada_saudacao.py
"""

from __future__ import annotations

import os
import random
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-entrada-saudacao-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

import saudacao  # noqa: E402

_falhas: list[str] = []
TITULO = "Paulus está te esperando."
SERIAS = ("codigo", "trava_codigo", "chave", "convite_erro", "google_negado", "google_expirado", "fora_da_janela", "trava_sem_internet")


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def main() -> int:
    print("=" * 55)
    print("  A saudação das telas de entrar")
    print("=" * 55)
    try:
        banco = saudacao.carregar_entrada()
        frases = banco["subtitulos"]

        print("\no banco")
        checar(banco["titulo"] == TITULO, "o título é “Paulus está te esperando.”", banco["titulo"])
        ids = [f["id"] for f in frases]
        checar(len(ids) == len(set(ids)), "os ids são únicos")
        sem = [t for t in saudacao.TELAS_ENTRADA if not any(t in f["telas"] for f in frases)]
        checar(not sem, "toda tela tem frase", sem)
        fora = sorted({t for f in frases for t in f["telas"]} - set(saudacao.TELAS_ENTRADA))
        checar(not fora, "nenhuma frase aponta para tela que não existe", fora)
        checar(all(len(f["texto"]) <= 160 for f in frases), "nenhuma frase passa de 160 caracteres")
        checar(not any("PAVLVS está" in f["texto"] or "Paulus" in f["texto"] for f in frases),
               "a frase de baixo não repete o agente (ele está no título)")

        print("\na hora, o dia e o calendário")
        manha = saudacao.saudar_entrada("entrar", datetime(2026, 10, 7, 9, 30), sorteio=random.Random(3))
        checar(manha["titulo"] == TITULO and manha["subtitulo"], "a resposta tem o título e a frase", manha)
        bom_dia = {saudacao.saudar_entrada("entrar", datetime(2026, 10, 7, 9, 30), sorteio=random.Random(s))["subtitulo"] for s in range(20)}
        checar(all(x.startswith("Bom dia") for x in bom_dia), "de manhã, as frases do momento vencem as gerais", bom_dia)
        natal = saudacao.saudar_entrada("trava", datetime(2026, 12, 25, 10), sorteio=random.Random(1))
        checar(natal["subtitulo"].startswith("Natal."), "no Natal, a frase do feriado", natal["subtitulo"])
        noite = saudacao.saudar_entrada("trava", datetime(2026, 10, 7, 23, 30), sorteio=random.Random(2))
        checar("noite" in noite["subtitulo"].lower(), "de noite, boa noite", noite["subtitulo"])

        print("\nas telas sérias")
        for tela in SERIAS:
            vistas = {saudacao.saudar_entrada(tela, datetime(2026, 12, 25, h), sorteio=random.Random(h))["subtitulo"] for h in range(24)}
            proprias = {f["texto"] for f in frases if tela in f["telas"]}
            checar(vistas <= proprias and not any(re.search(r"Natal|Bom dia|Boa (tarde|noite)", v) for v in vistas),
                   f"{tela}: só as frases dela, sem hora nem feriado", vistas)

        print("\no convite")
        c = saudacao.saudar_entrada("convite", datetime(2026, 10, 7, 9), nome="Beatriz Souza", escritorio="Silva Advogados")
        checar(c["subtitulo"] == "Beatriz, este é o seu convite para o PAVLVS de Silva Advogados.", "com o nome e o escritório", c["subtitulo"])
        c = saudacao.saudar_entrada("convite", datetime(2026, 10, 7, 9))
        checar(c["subtitulo"] == "Este é o seu convite para o PAVLVS do escritório.", "sem nada, a frase geral", c["subtitulo"])
        c = saudacao.saudar_entrada("convite", datetime(2026, 10, 7, 9), nome="<script>x</script>")
        checar("<" not in c["subtitulo"], "o nome entra limpo", c["subtitulo"])
        g = saudacao.saudar_entrada("google_ok", datetime(2026, 10, 7, 9), provedor="Google")
        checar(g["subtitulo"] == "Conta Google conectada. Já pode fechar esta aba.", "a volta do Google diz o provedor", g["subtitulo"])

        print("\nsem repetir")
        recentes, vistas = [], []
        for i in range(4):
            d = saudacao.saudar_entrada("trava", datetime(2026, 10, 7, 15), recentes, sorteio=random.Random(i))
            vistas.append(d["subtitulo"])
            recentes += d["ids"]
        checar(len(set(vistas)) == 4, "quatro aberturas seguidas, quatro frases", vistas)
        checar(saudacao.saudar_entrada("qualquer", datetime(2026, 10, 7, 15))["tela"] == "entrar", "tela desconhecida vale como entrar")

        print("\nnada do escritório, e aberta antes de entrar")
        import api
        import vinculo
        from acesso import politicas
        from fastapi.testclient import TestClient

        checar(("GET", "/api/saudacao/entrada") in politicas.SEM_SESSAO and ("GET", "/js/entrada-saudacao.js") in politicas.SEM_SESSAO,
               "de fora, sem sessão: a rota e o script abrem")
        checar(politicas.de("GET", "/api/saudacao/entrada") == politicas.PUBLICO, "a rota é pública")
        checar(vinculo.passa_travado("GET", "/api/saudacao/entrada"), "com o programa travado, a rota passa")
        api.estado.prefs.dados["pessoa"] = {"nome": "Doutora Secreta"}
        cli = TestClient(api.app, headers=api.cabecalho_local())
        r = cli.get("/api/saudacao/entrada", params={"tela": "trava", "recentes": "e-geral-2"})
        d = r.json()
        checar(r.status_code == 200 and set(d) == {"titulo", "subtitulo", "ids", "tela"} and d["titulo"] == TITULO,
               "a resposta só tem o título, a frase, os ids e a tela", d)
        checar("Secreta" not in r.text and "Doutora" not in r.text, "o nome do escritório não entra")
        js = (RAIZ / "frontend" / "js" / "entrada-saudacao.js").read_text(encoding="utf-8")
        checar("/api/saudacao/entrada" in js and "abrindo" in js, "o script pede a frase e revela o bloco")
        for pagina in ("entrar.html", "convite.html"):
            html = (RAIZ / "frontend" / pagina).read_text(encoding="utf-8")
            checar(TITULO in html and "<b>PAVLVS</b>" not in html and "/js/entrada-saudacao.js" in html,
                   f"{pagina}: o título novo e o script, sem a marca no alto")
        trava = (RAIZ / "frontend" / "js" / "45-vinculo.js").read_text(encoding="utf-8")
        checar(TITULO in trava and "<b>PAVLVS</b>" not in trava, "a trava do servidor: o título novo")

        print("\nas páginas que o servidor monta")
        import pagina_retorno
        from acesso import porteiro

        for estado, esperado in (("sucesso", "Login recebido."), ("negado", "não foi autorizada"), ("expirado", "expirou")):
            html = pagina_retorno.pagina(estado, provedor="Google")
            checar(TITULO in html and esperado in html and "<b>PAVLVS</b>" not in html and 'class="topo abrindo"' in html,
                   f"volta do Google ({estado}): o título, a frase do estado e o aparecer devagar")
        html = pagina_retorno.pagina("sucesso", provedor="Google", escopos="https://mail.google.com/")
        checar("Conta Google conectada." in html, "com a conta conectada, a frase diz a conta")
        pronto = re.search(r'd\.fase === "pronto"\) \{[^}]*\}', html)
        checar(pronto and "voltar()" in pronto.group(0) and "paulus://" not in pronto.group(0),
               "login pronto: a página pede ao PAULUS que venha para a frente, sem o diálogo do paulus://")
        checar(html.count("paulus://voltar") == 1 and ".catch(function () { try { window.location.href = \"paulus://voltar\"" in html,
               "o paulus:// só se o PAULUS não responder")
        checar(TITULO in porteiro.PAGINA_RECUSADA and "janela do PAULUS" in porteiro.PAGINA_RECUSADA, "fora da janela: o título e o motivo")
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
