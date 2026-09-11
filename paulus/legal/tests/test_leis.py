"""
Testes dos códigos de lei.

Este módulo existe para tirar o modelo do caminho: com o texto oficial no
disco, citar um artigo vira consulta a um índice. Então o que os testes cobrem
não é "achou alguma coisa" — é **não citar errado**, que é o dano real:

  - artigo revogado marcado como revogado, e o que teve só os incisos revogados
    NÃO marcado. Dizer que o art. 3º do Código Civil não existe seria pior que
    não ter a busca
  - artigo de outra lei, citado nas disposições finais, não vira artigo deste
    código nem sobrescreve o que já existe. O CPC tem art. 48 (foro do
    inventário) e também cita um "Art. 48" da Lei dos Juizados no seu art.
    1.064 — quem lê os dois como o mesmo artigo devolve a lei errada
  - os artigos do decreto que aprova a consolidação não são artigos da CLT
  - "Art. 58 - A duração normal" é o artigo 58, não um "58-A"
  - o sufixo inteiro conta: 359-M-A não é 359-A

Os testes rodam contra o texto oficial de verdade quando ele está na máquina, e
contra um HTML montado aqui quando não está — assim a suíte não depende de um
download para passar.

    python tests/test_leis.py
"""

from __future__ import annotations

import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import leis  # noqa: E402
from base import Base  # noqa: E402

# Onde os textos oficiais podem estar. Sem eles, os testes de leitura rodam
# contra o HTML montado abaixo.
PASTAS = [
    Path.home() / "Downloads" / "DOC-JURIDICOS",
    RAIZ / "data" / "leis",
]

_falhas: list[str] = []


@contextmanager
def base_em(caminho: Path):
    """
    Banco que fecha mesmo quando o teste quebra.

    No Windows um arquivo aberto não se apaga, e a pasta temporária some no fim
    da suíte: sem isto, uma falha de teste vira um erro de permissão que
    esconde a falha de verdade.
    """
    base = Base(caminho)
    try:
        yield base
    finally:
        base.fechar()


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {detalhe}")
        _falhas.append(descricao)


def _oficiais() -> dict[str, Path]:
    achados: dict[str, Path] = {}
    for pasta in PASTAS:
        if not pasta.is_dir():
            continue
        for arquivo in sorted(list(pasta.glob("*.html")) + list(pasta.glob("*.htm"))):
            codigo = leis.reconhecer(arquivo)
            if codigo and codigo not in achados:
                achados[codigo] = arquivo
    return achados


# Um código de mentira, com todas as armadilhas do texto real numa página só.
FALSO = """<html><head><meta charset="windows-1252"></head><body>
<p>DECRETO-LEI Nº 9.999, DE 1943</p>
<p>Art. 1º Fica aprovada a Consolidação de Teste que a este decreto acompanha.</p>
<p>Art. 2º Este decreto entra em vigor na data de sua publicação.</p>
<p>TÍTULO I</p>
<p>DAS DISPOSIÇÕES GERAIS</p>
<p>Art. 1º Esta Consolidação estatui as normas de teste.</p>
<p>Art. 2º Considera-se empregador a empresa que assume os riscos.</p>
<p>Art. 3º São absolutamente incapazes os menores de 16 anos.
I - (Revogado); II - (Revogado); III - (Revogado)</p>
<p>Art. 4º (Revogado pela Lei nº 1.111, de 2010)</p>
<p>Art. 5</p><p><sup>o</sup> O ordinal deste artigo veio num bloco separado.</p>
<p>Art. 58 - A duração normal do trabalho não excederá de 8 horas.</p>
<p>Art. 58-A. Considera-se trabalho em regime de tempo parcial o de trinta horas.</p>
<p>Art. 91 - São efeitos da condenação tornar certa a obrigação.</p>
""" + "".join(
    f"<p>Art. {n}. Artigo de enchimento número {n}, para o arquivo ter tamanho de código.</p>"
    for n in range(100, 130)
) + """
<p>SEÇÃO IV</p>
<p>DOS CRIMES CONTRA O ESTADO</p>
<p>Art. 359-M Tentar depor o governo legitimamente constituído.</p>
<p>Art. 359-M-A. Quando os delitos deste Capítulo forem praticados em multidão.</p>
<p>Art. 359-N Constranger, por meio de violência, o exercício de poder.</p>
<p>CAPÍTULO ÚNICO</p>
<p>DISPOSIÇÕES FINAIS</p>
<p>Art. 900. O art. 48 da Lei nº 9.099 passa a vigorar com a seguinte redação:</p>
<p>Art. 48. Caberão embargos de declaração contra sentença ou acórdão.</p>
<p>Art. 901. Este código entra em vigor após um ano.</p>
</body></html>"""


def test_leitura_do_falso(tmp: Path) -> None:
    """Todas as armadilhas do texto real, numa página montada aqui."""
    print("\nleitura de um código montado com as armadilhas")
    alvo = tmp / "falso.html"
    alvo.write_bytes(FALSO.encode("cp1252"))

    artigos, fora = leis.ler_codigo(alvo, "cc")
    por_numero = {a.numero: a for a in artigos}

    checar(fora["preambulo"] == 2,
           f"os 2 artigos do decreto ficam fora do código (achou {fora['preambulo']})")
    checar("1º" in por_numero and "estatui as normas" in por_numero["1º"].texto,
           "e o art. 1º do corpo é o da consolidação, não o do decreto")

    checar(fora["citados"] == 1,
           f"o artigo de outra lei citado nas disposições finais fica fora (achou {fora['citados']})")
    checar("48" not in por_numero, "e NÃO vira artigo deste código")
    checar("Caberão embargos" in por_numero["900"].texto,
           "o texto citado fica no artigo que está citando")

    checar("58" in por_numero and "duração normal" in por_numero["58"].texto,
           "“Art. 58 - A duração normal” é o artigo 58")
    checar("58-A" in por_numero and "tempo parcial" in por_numero["58-A"].texto,
           "e o 58-A continua sendo outro artigo")
    checar("91" in por_numero and por_numero["91"].texto.startswith("São efeitos"),
           f"“Art. 91 - São efeitos” não perde o S ({por_numero.get('91', leis.Artigo()).texto[:24]!r})")

    checar("359-M-A" in por_numero, "sufixo de dois degraus é lido inteiro")
    checar(por_numero["359-M"].ordem < por_numero["359-M-A"].ordem < por_numero["359-N"].ordem,
           "e o 359-M-A fica entre o 359-M e o 359-N")

    checar("5º" in por_numero and por_numero["5º"].texto.startswith("O ordinal"),
           f"o ordinal em bloco separado volta para o número ({list(por_numero)[:9]})")

    checar(por_numero["4º"].revogado, "artigo revogado no todo é marcado")
    checar(not por_numero["3º"].revogado,
           "mas o que teve só os incisos revogados NÃO é — o art. 3º está em vigor")

    # O lugar do artigo dentro do código: um cabeçalho maior fecha os menores.
    # Se a SEÇÃO IV vazar para o art. 900, a citação aponta para outro trecho
    # do código — e quem confere o contexto é levado ao lugar errado.
    checar("SEÇÃO IV" in por_numero["359-M"].contexto,
           "o artigo sabe em que seção está")
    checar("SEÇÃO" not in por_numero["900"].contexto,
           f"e a seção anterior não vaza para depois do capítulo seguinte "
           f"({por_numero['900'].contexto})")
    checar(por_numero["900"].contexto.startswith("TÍTULO I"),
           "o contexto vai do maior para o menor")

    numeros = [a.ordem for a in artigos]
    checar(numeros == sorted(numeros), "os artigos saem em ordem")
    checar(len(numeros) == len(set(numeros)), "e nenhum número se repete")


def test_cabecalho() -> None:
    """Frase que começa com a palavra do cabeçalho não é cabeçalho."""
    print("\nonde o artigo fica no código")
    e = leis.RE_ESTRUTURA
    for linha in ("LIVRO I", "PARTE GERAL", "PARTE ESPECIAL", "TÍTULO I", "Seção I",
                  "Subseção II", "CAPÍTULO ÚNICO", "Capítulo Único", "CAPÍTULO I-A",
                  "TÍTULO PRELIMINAR",
                  # o nome vem na mesma linha, e isso continua sendo cabeçalho
                  "LIVRO I DAS PESSOAS", "Seção I Disposições Gerais",
                  "TÍTULO III Do Domicílio"):
        checar(bool(e.match(linha)), f"“{linha}” é cabeçalho")

    # Todas estas estão no texto oficial — a primeira na CLT, o resto no CC e
    # no CPC. São continuações de frase que caíram no começo da linha.
    for linha in ('TÍTULO "DO PROCESSO DE MULTAS ADMINISTRATIVAS", NO QUE LHE FOR APLICÁVEL, COM',
                  "parte em relação a cada uma das que falecerem, salvo se, por estipulação",
                  "Livro II da Parte Especial deste Código.",
                  "Título II do Livro",
                  "Capítulo I do Título II da Lei nº 4.591, de 16 de dezembro de 1964,",
                  "Parte civil do processo"):
        checar(not e.match(linha), f"“{linha[:34]}…” é texto, não cabeçalho")


def test_ordem() -> None:
    print("\nordem dos números")
    o = leis._ordem
    checar(o("1") < o("2") < o("10") < o("100"), "número simples ordena por valor")
    checar(o("1.228") > o("999"), "o ponto de milhar não confunde a ordem")
    checar(o("5") < o("5", "-A") < o("5", "-B") < o("6"), "o sufixo cabe entre dois artigos")
    checar(o("359", "-M") < o("359", "-M-A") < o("359", "-N"),
           "e o sufixo de dois degraus cabe entre eles")


def test_base(tmp: Path) -> None:
    print("\nguardar e procurar")
    alvo = tmp / "falso.html"
    alvo.write_bytes(FALSO.encode("cp1252"))

    with base_em(tmp / "leis.db") as base:
        L = leis.Leis(base)
        r = L.importar(alvo, "cc")
        checar(r["artigos"] > 10, f"importa e conta os artigos ({r['artigos']})")

        checar(L.artigo("cc", "58")["texto"].startswith("A duração") or
               "duração normal" in L.artigo("cc", "58")["texto"],
               "acha pelo número")
        checar(L.artigo("cc", "1")["numero"] == "1º",
               "acha o 1º digitando só “1” — é como a pessoa escreve")
        checar(L.artigo("cc", "58-A")["numero"] == "58-A", "acha com sufixo")
        checar(L.artigo("cc", "359-M-A")["numero"] == "359-M-A",
               "e o sufixo de dois degraus não cai no de um")
        checar(L.artigo("cc", "48") is None, "não acha o artigo de outra lei")
        checar(L.artigo("cc", "9999") is None, "número que não existe devolve nada, sem quebrar")

        achados = L.procurar("tempo parcial")
        checar(any(a["numero"] == "58-A" for a in achados), "busca por palavra acha o artigo")
        checar(all(a["citacao"].startswith("CC, art.") for a in achados),
               "e a citação vem pronta, no formato que se escreve")

        # Acento e hífen são digitação, não sintaxe de busca.
        checar(L.procurar("duracao") or L.procurar("duração"), "busca ignora acento")
        checar(isinstance(L.procurar("tempo-parcial"), list), "hífen no termo não quebra a busca")
        checar(L.procurar("") == [], "termo vazio não devolve o código inteiro")

        revogado = L.artigo("cc", "4")
        checar(revogado["revogado"] is True, "o revogado chega marcado na tela")
        checar(L.artigo("cc", "3")["revogado"] is False, "e o que está em vigor, não")

        L.apagar("cc")
        checar(L.contagem()["artigos"] == 0, "remover um código apaga os artigos junto")
        checar(L.procurar("tempo parcial") == [], "e a busca deixa de achar")


def test_recusa(tmp: Path) -> None:
    """Arquivo que não é código não pode entrar como se fosse."""
    print("\no que não entra")
    with base_em(tmp / "recusa.db") as base:
        L = leis.Leis(base)

        curto = tmp / "curto.html"
        curto.write_text("<html><body><p>Art. 1º Um artigo só.</p></body></html>", encoding="utf-8")
        try:
            L.importar(curto, "cc")
            checar(False, "recusa arquivo com artigos de menos")
        except ValueError as exc:
            checar("artigo" in str(exc).lower(), f"recusa arquivo com artigos de menos ({exc})")

        try:
            L.importar(tmp / "nao-existe.html", "cc")
            checar(False, "arquivo inexistente vira erro tratado")
        except ValueError:
            checar(True, "arquivo inexistente vira erro tratado")

        sem_pista = tmp / "qualquer.html"
        sem_pista.write_text("<html><body><p>texto solto</p></body></html>", encoding="utf-8")
        checar(leis.reconhecer(sem_pista) == "", "não adivinha de qual código é um arquivo qualquer")


def test_oficiais(tmp: Path) -> None:
    """
    Contra o texto oficial, quando ele está na máquina.

    Os artigos conferidos aqui são os que dá para conferir de cabeça: se o
    art. 121 do Código Penal não disser "Matar alguem", a leitura está errada.
    """
    print("\ncontra o texto oficial do Planalto")
    arquivos = _oficiais()
    if not arquivos:
        print("  pulado: nenhum código oficial achado em " +
              " nem ".join(str(p) for p in PASTAS))
        return

    with base_em(tmp / "oficial.db") as base:
        L = leis.Leis(base)
        for codigo, arquivo in arquivos.items():
            r = L.importar(arquivo, codigo)
            checar(r["artigos"] > 300, f"{r['nome']}: {r['artigos']} artigos")

        esperado = {
            ("cc", "1º"): "Toda pessoa é capaz",
            ("cc", "186"): "ato ilícito",
            ("cc", "421"): "função social do contrato",
            ("cc", "421-A"): "paritários",
            ("cc", "1.228"): "proprietário tem a faculdade",
            ("cpc", "300"): "tutela de urgência",
            ("cpc", "1.022"): "embargos de declaração",
            ("cp", "121"): "Matar alguem",
            ("cp", "155"): "Subtrair",
            ("clt", "7º"): "preceitos constantes",
            ("clt", "58"): "duração normal do trabalho",
            ("clt", "58-A"): "tempo parcial",
            ("clt", "482"): "justa causa",
        }
        for (codigo, numero), trecho in esperado.items():
            if codigo not in arquivos:
                continue
            a = L.artigo(codigo, numero)
            if not a:
                checar(False, f"{codigo} art. {numero} existe")
                continue
            checar(trecho.lower() in a["texto"].lower(),
                   f"{a['citacao']} diz o que deve dizer", a["resumo"][:70])

        # O rótulo de alteração fica ao lado da citação: dizer que o art. 121
        # é de 2015 seria afirmar sobre a lei uma coisa que não é.
        if "cp" in arquivos:
            cento_e_vinte_um = L.artigo("cp", "121")
            checar("13.104" not in (cento_e_vinte_um["alterado_por"] or ""),
                   "CP art. 121 não é “incluído pela Lei de 2015” — isso foi o § 2º-A",
                   cento_e_vinte_um["alterado_por"] or "sem rótulo")
        if "cc" in arquivos:
            checar("13.874" in (L.artigo("cc", "421")["alterado_por"] or ""),
                   "mas o caput alterado continua dizendo qual lei o alterou",
                   L.artigo("cc", "421")["alterado_por"] or "sem rótulo")
            # Um cabeçalho maior fecha os menores também no texto oficial.
            duzentos = L.artigo("cpc", "294") if "cpc" in arquivos else None
            if duzentos:
                checar("SEÇÃO" not in duzentos["contexto"],
                       "CPC art. 294 não herda a seção do livro anterior",
                       duzentos["contexto"])

        if "cpc" in arquivos:
            # O CPC tem art. 48 de verdade (foro do inventário) E cita um
            # "Art. 48" da Lei dos Juizados nas disposições finais. O erro a
            # evitar é o citado sobrescrever o real — os dois têm o número 48.
            quarenta_e_oito = L.artigo("cpc", "48")
            checar(quarenta_e_oito and "autor da herança" in quarenta_e_oito["texto"],
                   "CPC art. 48 é o do foro do inventário",
                   (quarenta_e_oito or {}).get("texto", "não achei")[:70])
            checar(quarenta_e_oito and "embargos de declaração" not in quarenta_e_oito["texto"],
                   "e não foi trocado pelo art. 48 da Lei dos Juizados citado no art. 1.064")
            mil64 = L.artigo("cpc", "1.064")
            checar(mil64 and "embargos de declaração" in mil64["texto"],
                   "o texto citado ficou no artigo que cita")
        if "clt" in arquivos:
            um = L.artigo("clt", "1º")
            checar(um and "Consolidação" in um["texto"] and "Fica aprovada" not in um["texto"],
                   "CLT art. 1º é o da consolidação, não o do decreto que a aprova")
        if "cc" in arquivos:
            checar(L.artigo("cc", "3º")["revogado"] is False,
                   "CC art. 3º está em vigor — só os incisos foram revogados")

        # O contexto sai ao lado da citação; frase inteira ali é sinal de que
        # uma linha de texto foi lida como cabeçalho.
        for codigo in arquivos:
            longos = base.buscar(
                "SELECT numero, contexto FROM artigos WHERE codigo = ? "
                "AND length(contexto) > 110 ORDER BY length(contexto) DESC LIMIT 3",
                (codigo,))
            checar(not longos,
                   f"{codigo}: nenhum contexto é frase de texto",
                   "; ".join(f"art. {l['numero']}: {l['contexto'][:60]}" for l in longos))

        # Nenhum código pode ter buraco nem repetição.
        for codigo in arquivos:
            linhas = base.buscar(
                "SELECT ordem FROM artigos WHERE codigo = ? ORDER BY ordem", (codigo,))
            ordens = [l["ordem"] for l in linhas]
            checar(len(ordens) == len(set(ordens)), f"{codigo}: nenhum artigo repetido")
            checar(ordens == sorted(ordens), f"{codigo}: os artigos estão em ordem")



def main() -> int:
    print("=" * 55)
    print("PAULUS - códigos de lei")
    print("=" * 55)

    test_cabecalho()
    test_ordem()
    with tempfile.TemporaryDirectory() as bruto:
        tmp = Path(bruto)
        test_leitura_do_falso(tmp)
        test_base(tmp)
        test_recusa(tmp)
        test_oficiais(tmp)

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
