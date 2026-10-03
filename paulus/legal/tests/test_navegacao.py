"""
Toda tela tem chamada pela conversa (pedido de 02/10/2026).

"Pedimos algo na conversa, do tipo 'agende na reunião', e ele retorna 'não
encontrei nada no documento'": o PAULUS não conhecia o próprio caminho. Aqui:

  - toda tela que o servidor conhece (src/programa.py, telas_conhecidas) é
    alcançada por "abra <nome>" e por um apelido falado;
  - o frontend tem quem abra cada uma (destinos do servidor, NOVOS_DESTINOS,
    TELAS_DA_CONVERSA ou uma seção de Configurações em CFG_SECOES);
  - pela API, com e sem documento anexado, o pedido vira navegação ou ação
    (agenda, tarefa, assinatura) - nunca leitura do documento;
  - perguntas sobre o documento continuam indo para o documento.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_navegacao.py
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-nav-"))
os.environ.setdefault("PAULUS_DADOS", str(TMP / "dados"))
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def _frontend() -> str:
    pasta = RAIZ / "frontend" / "js"
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(pasta.glob("*.js")))


def test_regra() -> None:
    print("\ntoda tela por \"abra <nome>\" e por um apelido")
    import programa

    telas = programa.mapa_para(True)
    for id_ in programa.telas_conhecidas(True):
        nome = programa.nome_da_tela(id_, True)
        leitura = programa.navegar(f"abra {nome}")
        # Dois destinos com o mesmo nome ("Agenda"): vale o primeiro, e o nome bate.
        checar(leitura is not None and programa.nome_da_tela(leitura.destino, True) == nome,
               f"abra {nome}", leitura and leitura.destino)
    apelidos = {
        "vá para agentes": "agentes", "pode abrir a lixeira?": "config_lixeira", "quero ver os avisos": "avisos",
        "abra o menu mais": "mais", "abra o editor de documentos": "editor",
        "abra a seção de backup do PAULUS": "config_backup", "me leve aos meus dados": "config_perfil",
        "volte para o início": "conversa", "vamos para o financeiro": "financeiro", "abra o e-mail": "caixa",
        "abra a agenda": "calendario", "abra o acervo": "biblioteca", "abra as gravações": "gravacoes",
        "abra modelos": "config_modelos", "abra o escritório": "config_vinculos", "abra a aparência": "config_aparencia",
    }
    for frase, esperado in apelidos.items():
        leitura = programa.navegar(frase)
        checar(leitura is not None and leitura.destino == esperado, frase, leitura and leitura.destino)
    for frase in ("abra o contrato de honorários", "mostre a cláusula de multa", "abra o sistema",
                  "qual o prazo do contrato?", "do que se trata este arquivo?"):
        checar(programa.navegar(frase) is None, f"não é tela: {frase}")
    del telas


def test_frontend_abre() -> None:
    print("\no frontend tem quem abra cada tela")
    import destinos
    import programa

    js = _frontend()
    novos = set(re.findall(r"^\s{2}([a-z_]+): \{", js.split("const NOVOS_DESTINOS = {", 1)[1].split("\n};", 1)[0], re.M))
    da_conversa = set(re.findall(r"^\s{2}([a-z_]+): \{", js.split("const TELAS_DA_CONVERSA = {", 1)[1].split("\n};", 1)[0], re.M))
    secoes = set(re.findall(r'^\s{2}\["([a-z]+)", "', js.split("const CFG_SECOES = [", 1)[1].split("\n];", 1)[0], re.M))
    do_servidor = {d.id for d in destinos.DESTINOS}
    for id_ in programa.telas_conhecidas(True):
        if id_.startswith("config_"):
            ok = id_[7:] in secoes
        else:
            ok = id_ in do_servidor or id_ in novos or id_ in da_conversa
        checar(ok, f"abre {id_}")


def test_api() -> None:
    print("\npela API: com e sem anexo, o pedido não vai para o documento")
    import api
    import test_c3_painel as c3
    from test_gravacoes import _porta_livre, _subir_servidor

    habilidade = api.estado.registro.obter("perguntar")
    antes = habilidade.executar
    habilidade.executar = c3.executar_simulado
    porta = _porta_livre()
    _subir_servidor(porta)
    base = f"http://127.0.0.1:{porta}"
    frases = {
        "agende na reunião": "agenda", "agende uma reunião amanhã às 10h": "agenda",
        "nova tarefa: ligar para o João": "tarefa", "abra a agenda": "programa", "vá para agentes": "programa",
        "quero ver os avisos": "programa", "abra o menu mais": "programa", "pode abrir a lixeira?": "programa",
        "abra o editor de documentos": "programa",
    }
    try:
        for apenas in ([], ["Contrato A.docx"]):
            rotulo = "com anexo" if apenas else "sem anexo"
            for frase, tipo in frases.items():
                t = c3._pedir(base, "POST", "/api/trabalhos", {"pedido": "navegação"})
                corpo = {"pergunta": frase, **({"apenas": apenas} if apenas else {})}
                r = c3._pedir(base, "POST", f"/api/trabalhos/{t['id']}/perguntar", corpo, stream=True)
                c3._ler_eventos(r)
                r.close()
                m = c3._pedir(base, "GET", f"/api/trabalhos/{t['id']}")["mensagens"][-1]
                achado = (m.get("proposta") or {}).get("tipo")
                checar(achado == tipo, f"{rotulo}: {frase} -> {tipo}", (achado, (m.get("texto") or "")[:60]))
                c3._pedir(base, "DELETE", f"/api/trabalhos/{t['id']}")
            # A pergunta sobre o documento continua indo para o documento.
            t = c3._pedir(base, "POST", "/api/trabalhos", {"pedido": "documento"})
            corpo = {"pergunta": "qual a multa e o prazo?", **({"apenas": apenas} if apenas else {})}
            r = c3._pedir(base, "POST", f"/api/trabalhos/{t['id']}/perguntar", corpo, stream=True)
            c3._ler_eventos(r)
            r.close()
            m = c3._pedir(base, "GET", f"/api/trabalhos/{t['id']}")["mensagens"][-1]
            checar("multa" in (m.get("texto") or "").lower(), f"{rotulo}: a pergunta do documento vai ao documento", m.get("texto"))
            c3._pedir(base, "DELETE", f"/api/trabalhos/{t['id']}")
        t = c3._pedir(base, "POST", "/api/trabalhos", {"pedido": "assinar"})
        r = c3._pedir(base, "POST", f"/api/trabalhos/{t['id']}/perguntar",
                      {"pergunta": "assine este documento", "apenas": ["Contrato A.docx"]}, stream=True)
        c3._ler_eventos(r)
        r.close()
        m = c3._pedir(base, "GET", f"/api/trabalhos/{t['id']}")["mensagens"][-1]
        checar("multa" not in (m.get("texto") or "").lower(), "\"assine este documento\" com o anexo não lê o documento", m.get("texto"))
        c3._pedir(base, "DELETE", f"/api/trabalhos/{t['id']}")
    finally:
        habilidade.executar = antes


def main() -> int:
    print("=" * 60)
    print("  Navegação: toda tela tem chamada pela conversa")
    print("=" * 60)
    try:
        test_regra()
        test_frontend_abre()
        test_api()
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
