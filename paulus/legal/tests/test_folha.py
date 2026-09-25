"""
A folha do documento: cabecalho (papel timbrado), rodape e numeracao.

O que se testa e o que sai no PDF - a tela desenha a mesma folha, mas quem
vai para o cliente e o arquivo -, e a sugestao do modo Folha: a regra resolve
as escolhas, o modelo so escreve texto, e numero inventado nao entra no
timbre.

Rodar: venv\\Scripts\\python.exe tests\\test_folha.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import documento as D  # noqa: E402

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {str(detalhe)[:300]}")
        _falhas.append(descricao)


def texto_das_paginas(pdf: bytes) -> list[str]:
    from pypdf import PdfReader

    return [p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf)).pages]


def blocos_longos(n: int = 90) -> list:
    return D.ler_html("".join(f"<p>Cláusula {i}. Texto de teste para ocupar a folha inteira.</p>" for i in range(n)))


def test_normalizar() -> None:
    print("\nnormalizar a folha")
    checar(D.normalizar_folha(None) == D.FOLHA_PADRAO, "sem nada, o padrão")
    torta = D.normalizar_folha({"cabecalho": "xadrez", "numeracao": "romana", "alinhar": "diagonal",
                                "linhas": ["Um", "", "Três", "Quatro", "Cinco", ""]})
    checar(torta["cabecalho"] == "padrao" and torta["numeracao"] == "pagina" and torta["alinhar"] == "centro",
           "o que o PDF não desenha volta ao padrão")
    checar(torta["linhas"] == ["Um", "", "Três", "Quatro"], "no máximo quatro linhas", torta["linhas"])
    checar(D.normalizar_formato({"corpo": 11})["folha"] == D.FOLHA_PADRAO, "formato antigo ganha a folha padrão")


def test_numeracao() -> None:
    print("\na numeração")
    checar(D.numero_da_pagina("pagina", 2) == "página 2", "página N")
    checar(D.numero_da_pagina("pagina_de", 2, 5) == "página 2 de 5", "página N de M")
    checar(D.numero_da_pagina("numero", 3) == "3", "só o número")
    checar(D.numero_da_pagina("nenhuma", 3) == "", "nenhuma")

    folha = {**D.FOLHA_PADRAO, "numeracao": "pagina_de"}
    paginas = texto_das_paginas(D.para_pdf(blocos_longos(), "Contrato", "Contrato",
                                           formato={"folha": folha}))
    total = len(paginas)
    checar(total > 1, "o documento de teste tem mais de uma página", total)
    checar(f"página 1 de {total}" in paginas[0] and f"página {total} de {total}" in paginas[-1],
           "o PDF escreve 'página N de M' com o total certo", paginas[0][-80:])

    sem = texto_das_paginas(D.para_pdf(blocos_longos(10), "Contrato", "",
                                       formato={"folha": {**D.FOLHA_PADRAO, "numeracao": "nenhuma"}}))
    checar("página" not in sem[0], "sem numeração, nenhum número no rodapé")


def test_cabecalho_e_rodape() -> None:
    print("\ncabeçalho e rodapé")
    timbre = {"linhas": ["Escritório de Teste", "Rua das Flores, 10"], "logo": ""}
    pdf = D.para_pdf(blocos_longos(5), "Contrato", "Rodapé próprio", timbre=timbre,
                     formato={"folha": {**D.FOLHA_PADRAO, "alinhar": "esquerda"}})
    texto = texto_das_paginas(pdf)[0]
    checar("Escritório de Teste" in texto and "Rua das Flores, 10" in texto, "as linhas escritas saem no alto")
    checar("Rodapé próprio" in texto, "o rodapé sai")

    folha = D.normalizar_folha({"rodape": "proprio", "rodape_texto": "www.exemplo.com.br"})
    checar(D.texto_do_rodape(folha, "Contrato") == "www.exemplo.com.br", "rodapé próprio")
    checar(D.texto_do_rodape({"rodape": "nenhum"}, "Contrato") == "", "sem rodapé")
    checar(D.texto_do_rodape({}, "Contrato") == "Contrato", "o padrão é o título")

    com = D.medidas_da_folha(timbre)
    checar(com["topo_cm"] > D.MARGEM_CM, "timbre abre espaço no alto", com)
    checar(D.medidas_da_folha(None)["topo_cm"] == D.MARGEM_CM, "sem timbre, a margem de sempre")

    mapa_com = D.mapa_de_paginas(blocos_longos(), timbre=timbre)
    mapa_sem = D.mapa_de_paginas(blocos_longos())
    checar(mapa_com["paginas"] >= mapa_sem["paginas"], "o timbre empurra o texto, não o sobrepõe")


def test_sugerir() -> None:
    print("\na sugestão do modo Folha")
    escritorio = ["Fulano de Tal Advocacia", "OAB SP 123.456", "Rua A, 1 · (11) 5555-0000"]

    r = D.sugerir_folha("numeração página x de y no centro, sem logo", D.FOLHA_PADRAO, escritorio, "Contrato")
    f = r["folha"]
    checar(f["numeracao"] == "pagina_de" and f["numeracao_onde"] == "centro" and f["logo"] is False,
           "as escolhas saem da regra, sem modelo", f)

    f = D.sugerir_folha("timbre à esquerda, numeração página x de y no centro", D.FOLHA_PADRAO, escritorio, "Contrato")["folha"]
    checar(f["alinhar"] == "esquerda" and f["numeracao_onde"] == "centro",
           "'no centro' da numeração não centraliza o timbre", f)

    def modelo(instrucao, sistema, esquema):
        return {"linhas": ["Fulano de Tal Advocacia", "OAB SP 123.456", "OAB RJ 999.999", "Telefone (21) 4444-1234"],
                "rodape_texto": "Documento confidencial"}

    r = D.sugerir_folha("cabeçalho com meu nome e OAB, rodapé dizendo documento confidencial",
                        D.FOLHA_PADRAO, escritorio, "Contrato", modelo)
    f = r["folha"]
    checar(f["cabecalho"] == "proprio" and f["linhas"][:2] == escritorio[:2], "o modelo escreve o cabeçalho", f["linhas"])
    checar(not any("999.999" in l or "4444" in l for l in f["linhas"]), "número inventado não entra no timbre", f["linhas"])
    checar(f["rodape"] == "proprio" and f["rodape_texto"] == "Documento confidencial", "e o rodapé")

    def quebrado(*_):
        raise RuntimeError("sem ollama")

    r = D.sugerir_folha("cabeçalho com meu nome, sem numeração", D.FOLHA_PADRAO, escritorio, "Contrato", quebrado)
    checar(r["folha"]["numeracao"] == "nenhuma" and r["nota"], "sem modelo, a regra ainda vale e a nota avisa", r)


if __name__ == "__main__":
    test_normalizar()
    test_numeracao()
    test_cabecalho_e_rodape()
    test_sugerir()
    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        sys.exit(1)
    print("  todos os testes passaram")
