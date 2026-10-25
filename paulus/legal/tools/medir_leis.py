"""
A régua da busca de lei por assunto (src/leis.py, procurar_assunto), sem modelo.

É a busca de reserva: quando a pergunta não cita "art. X do Y", são os
artigos dela que a resposta leva. Mais lei no acervo pode virar ruído - um
artigo do Estatuto da OAB passando na frente do CPC -, e esta régua mede isso
antes e depois de cada pacote novo:

- GERAIS: perguntas que não nomeiam a lei, sobre os códigos de sempre. Não
  podem piorar quando o acervo cresce;
- NOVAS: perguntas das leis acrescentadas em 25/10/2026, com o nome (ou o
  assunto inconfundível) na frase.

Conta, por pergunta, se o código certo e o artigo certo estão entre os 3
primeiros. Monta a base numa pasta temporária, com o pacote do instalador
(config/acervo-inicial): sem rede e sem tocar nos dados.

    venv\\Scripts\\python.exe tools\\medir_leis.py
"""

from __future__ import annotations

import gzip
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import leis as leis_mod  # noqa: E402
from base import Base  # noqa: E402
from biblioteca import nativo  # noqa: E402

# (pergunta, código, artigos aceitos)
GERAIS = [
    ("qual o prazo para contestar a ação?", "cpc", {"335"}),
    ("qual o prazo de prescrição quando a lei não fixa outro menor?", "cc", {"205"}),
    ("os honorários de sucumbência ficam entre dez e vinte por cento de quê?", "cpc", {"85"}),
    ("quantos anos de posse para a usucapião extraordinária?", "cc", {"1238", "1.238"}),
    ("como funciona a guarda compartilhada dos filhos?", "cc", {"1583", "1584", "1.583", "1.584"}),
    ("quantos dias de férias o empregado tem depois de doze meses?", "clt", {"130"}),
    ("o aviso prévio do empregado é de quantos dias?", "clt", {"487"}),
    ("o consumidor pode desistir da compra feita fora do estabelecimento em quantos dias?", "cdc", {"49"}),
    ("qual o prazo para reclamar de vício aparente em produto durável?", "cdc", {"26"}),
    ("qual a pena do homicídio simples?", "cp", {"121"}),
    ("quais os requisitos da prisão preventiva?", "cpp", {"312", "313"}),
    ("a casa é asilo inviolável do indivíduo?", "cf", {"5"}),
    ("o locatário pode devolver o imóvel antes do prazo pagando multa?", "inquilinato", {"4"}),
    ("quais as garantias que o locador pode exigir do locatário?", "inquilinato", {"37"}),
    ("o que é o lançamento do crédito tributário?", "ctn", {"142"}),
    ("qual o prazo dos embargos de declaração?", "cpc", {"1023", "1.023"}),
    ("qual a idade mínima para adotar?", "eca", {"42"}),
]

NOVAS = [
    ("qual o prazo do recurso no juizado especial cível?", "juizados", {"42"}),
    ("o estatuto da advocacia garante honorários de que tipo ao advogado?", "oab", {"22", "23"}),
    ("em que hipóteses a LGPD permite tratar dados pessoais?", "lgpd", {"7"}),
    ("qual o prazo para impetrar mandado de segurança?", "ms", {"23"}),
    ("quais medidas protetivas de urgência a Lei Maria da Penha prevê contra o agressor?", "maria_da_penha", {"22"}),
    ("pela lei do bem de família, o imóvel residencial do casal é impenhorável?", "bem_de_familia", {"1"}),
    ("quem tem legitimidade para propor ação civil pública?", "acp", {"5"}),
    ("qual o prazo mínimo do arrendamento rural pelo estatuto da terra?", "terra", {"95"}),
    ("qual o percentual de reserva legal do código florestal na Amazônia Legal?", "florestal", {"12"}),
    ("quais os requisitos da aposentadoria por idade?", "beneficios", {"48"}),
    ("quem pode requerer recuperação judicial?", "falencia", {"48"}),
    ("qual a pena por destruir floresta de preservação permanente, crime ambiental?", "ambientais", {"38"}),
    ("qual ato de improbidade importa enriquecimento ilícito?", "improbidade", {"9"}),
    ("quais as modalidades de licitação?", "licitacoes", {"28"}),
    ("na lei de alimentos, o juiz fixa alimentos provisórios ao despachar o pedido?", "alimentos", {"4"}),
    ("pela LINDB, quando a lei começa a vigorar depois de publicada?", "lindb", {"1"}),
    ("a sentença arbitral produz os mesmos efeitos da sentença judicial?", "arbitragem", {"31"}),
    ("na lei de registros públicos, todo imóvel tem matrícula própria?", "registros", {"176"}),
]


def montar(pasta: Path) -> "leis_mod.Leis":
    base = Base(pasta / "leis.db")
    L = leis_mod.Leis(base)
    idx = nativo.indice()
    for codigo, dados in idx.get("codigos", {}).items():
        if codigo not in leis_mod.CODIGOS:
            continue
        alvo = pasta / dados["arquivo"].removesuffix(".gz")
        alvo.write_bytes(gzip.decompress((nativo.ACERVO / dados["arquivo"]).read_bytes()))
        L.importar(alvo, codigo)
    return L


def medir(L, perguntas) -> tuple[int, int, list[str]]:
    instalados = {l["codigo"] for l in L.instalados() if l["instalado"]}
    codigo_certo = artigo_certo = 0
    linhas = []
    for pergunta, codigo, aceitos in perguntas:
        achados = L.procurar_assunto(pergunta, limite=3) if codigo in instalados or codigo in leis_mod.CODIGOS else []
        codigos = [a["codigo"] for a in achados]
        numeros = {str(a["numero"]).rstrip("º°o") for a in achados if a["codigo"] == codigo}
        ok_codigo = codigo in codigos
        ok_artigo = bool(numeros & {n.rstrip("º°o") for n in aceitos})
        codigo_certo += ok_codigo
        artigo_certo += ok_artigo
        marca = "art" if ok_artigo else "cod" if ok_codigo else "---"
        trouxe = ", ".join(a["citacao"] for a in achados) or "(nada)"
        linhas.append(f"  {marca}  {pergunta}  ->  {trouxe}")
    return codigo_certo, artigo_certo, linhas


def main() -> int:
    pasta = Path(tempfile.mkdtemp(prefix="paulus-medir-leis-"))
    try:
        L = montar(pasta)
        instalados = sorted(l["codigo"] for l in L.instalados() if l["instalado"])
        print(f"{len(instalados)} leis no pacote: {', '.join(instalados)}\n")
        for rotulo, perguntas in (("GERAIS (não nomeiam a lei)", GERAIS), ("NOVAS (leis de 25/10)", NOVAS)):
            c, a, linhas = medir(L, perguntas)
            print(rotulo)
            print("\n".join(linhas))
            print(f"  -> código certo nos 3 primeiros: {c}/{len(perguntas)} · artigo certo: {a}/{len(perguntas)}\n")
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
