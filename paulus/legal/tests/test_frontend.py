"""
Testes de integridade da interface.

Existem por causa de um erro real: ao remover o CSS de uma coluna por
marcador de secao, o corte levou junto o CSS da Biblioteca e das Habilidades,
que estavam no meio do intervalo. A pagina continuou "funcionando" - servia,
respondia, nao dava erro nenhum - e chegou ao usuario com os icones do tamanho
da tela e a lista sem layout.

Nada disso aparece em teste de backend. Estas checagens sao estaticas e
rodam em milissegundos:

  - toda classe usada tem regra no CSS
  - todo id usado no JS existe no HTML
  - todo token var(--x) foi declarado
  - o JavaScript da pagina compila

    python tests/test_frontend.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
PAGINA = RAIZ / "frontend" / "index.html"

# Classes que existem so para o JS marcar estado ou achar elemento, e que por
# isso nao precisam de aparencia propria.
SEM_ESTILO = {
    "vazia", "aberto", "on", "ativo", "recolhida", "fora", "sumido",
    "arrastando", "parado", "chama", "corta", "num", "rotulo", "nota",
    "explica", "erro", "titulo", "texto", "nome", "valor", "trilho",
    "desc", "numero", "cresce", "quem", "balao", "marca", "estado",
    "detalhe", "cabeca", "corpo", "rodape", "seta", "icone", "cam",
    "arq", "origem", "caminho", "mais", "chave", "assistente", "txt",
    "concluido", "executando", "na_fila", "falhou", "aguardando",
    "pausado", "alta", "media", "baixa", "pronta", "futura", "em_breve",
    "com_problema", "primario", "perigo", "largo", "pastilha", "coroa",
    "exemplo", "hab-usar", "voltar-bancada",
    # nome de variavel do JS dentro de class="msg " + classe
    "classe",
}

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {detalhe}")
        _falhas.append(descricao)


def _partes(html: str) -> tuple[str, str]:
    css = "\n".join(re.findall(r"<style>(.*?)</style>", html, re.S))
    js = "\n".join(re.findall(r"<script>(.*?)</script>", html, re.S))
    return css, js


def classes_definidas(css: str) -> set[str]:
    """Classes que aparecem em algum seletor."""
    sem_comentario = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return set(re.findall(r"\.([a-z][a-z0-9_-]*)", sem_comentario))


def classes_usadas(html: str) -> set[str]:
    """
    Classes que a pagina realmente aplica.

    Pega tanto o class="..." da marcacao quanto os que o JS monta em string,
    que e onde vive a maior parte da interface.
    """
    usadas: set[str] = set()
    for atributo in re.findall(r'class="([^"]*)"', html):
        for nome in atributo.split():
            if not nome.startswith("${") and "+" not in nome:
                usadas.add(nome)
    for atributo in re.findall(r"class='([^']*)'", html):
        usadas.update(atributo.split())
    return {c for c in usadas if re.fullmatch(r"[a-z][a-z0-9_-]*", c)}


def test_css_completo() -> None:
    print("\nclasses usadas tem regra no CSS")
    html = PAGINA.read_text(encoding="utf-8")
    css, _ = _partes(html)

    definidas = classes_definidas(css)
    usadas = classes_usadas(html)
    orfas = sorted(usadas - definidas - SEM_ESTILO)

    checar(
        not orfas,
        f"nenhuma classe sem regra (achou {len(orfas)})",
        ", ".join(orfas[:12]) if orfas else "",
    )

    # As pecas que ja quebraram uma vez ficam checadas por nome.
    essenciais = [
        ".doc-linha", ".doc-marca", ".doc-acoes", ".etiqueta",
        ".hab-marca", ".hab-acao", ".catalogo", ".bib-topo",
        ".medidor", ".maquina", ".cartao-campo", ".pilula", ".enviar",
        ".menu-conversa", ".cartao-agora", ".chamada",
    ]
    faltando = [e for e in essenciais if e not in css]
    checar(not faltando, "as pecas centrais da tela tem estilo", ", ".join(faltando))


def test_css_bem_formado() -> None:
    """
    Regressao: ao recuperar um bloco de CSS de um commit antigo, veio junto um
    trecho sem seletor - so as declaracoes e a chave de fechar. O navegador
    engole isso em silencio e descarta o que vem depois.
    """
    print("\nCSS bem formado")
    css, _ = _partes(PAGINA.read_text(encoding="utf-8"))
    sem_comentario = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    abre, fecha = sem_comentario.count("{"), sem_comentario.count("}")
    checar(abre == fecha, f"chaves equilibradas ({abre} abrem, {fecha} fecham)")

    # Um seletor nunca contem ";" - declaracoes sim. E a assinatura exata de
    # um bloco que perdeu o seletor.
    orfaos = []
    for antes, seletor in re.findall(r"(^|\})([^{}]*)\{", sem_comentario, re.M):
        if ";" in seletor:
            orfaos.append(seletor.strip().splitlines()[0][:45])
    checar(not orfaos, f"nenhum bloco sem seletor (achou {len(orfaos)})", " | ".join(orfaos[:3]))


def test_sem_regra_repetida() -> None:
    """
    Regressao: um bloco recuperado duplicou 106 linhas de regras. Como em CSS a
    ultima ganha, a copia antiga sobrescrevia os ajustes novos - a coluna
    voltava a 660 px depois de eu a ter alargado.
    """
    print("\nnenhuma regra repetida")
    css, _ = _partes(PAGINA.read_text(encoding="utf-8"))
    sem_comentario = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    # Seletores que podem repetir de proposito: tema, media query, estado.
    contagem: dict[str, int] = {}
    for linha in sem_comentario.splitlines():
        m = re.match(r"^  ([.#][a-z][\w -]*)\s*\{", linha)
        if m:
            contagem[m.group(1)] = contagem.get(m.group(1), 0) + 1

    repetidos = sorted(s for s, n in contagem.items() if n > 1)
    checar(
        not repetidos,
        f"nenhum seletor de primeiro nivel repetido (achou {len(repetidos)})",
        ", ".join(repetidos[:8]),
    )


def test_ids() -> None:
    print("\nids usados no JS existem no HTML")
    html = PAGINA.read_text(encoding="utf-8")

    estaticos = set(re.findall(r'\bid="([a-z0-9-]+)"', html))
    criados = set(re.findall(r'\.id = "([a-z0-9-]+)"', html))
    usados = set(re.findall(r'\$\("([a-z0-9-]+)"\)', html))

    orfaos = sorted(usados - estaticos - criados)
    checar(not orfaos, f"nenhum id orfao (achou {len(orfaos)})", ", ".join(orfaos))


def test_tokens() -> None:
    print("\ntokens de cor declarados")
    css, _ = _partes(PAGINA.read_text(encoding="utf-8"))

    usados = set(re.findall(r"var\((--[a-z0-9-]+)\)", css))
    declarados = set(re.findall(r"^\s*(--[a-z0-9-]+):", css, re.M))
    orfaos = sorted(usados - declarados)
    checar(not orfaos, f"nenhum token sem declaracao (achou {len(orfaos)})", ", ".join(orfaos))

    # Cor fixa fora dos blocos de tema significa que o tema nao alcanca ela.
    sem_comentario = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    fora, dentro = [], False
    for linha in sem_comentario.splitlines():
        if re.search(r"^\s*(:root|\[data-tema)", linha):
            dentro = True
            continue
        if dentro and linha.strip() == "}":
            dentro = False
            continue
        if dentro:
            continue
        if re.search(r"#[0-9a-fA-F]{3,6}\b", linha):
            fora.append(linha.strip()[:50])
    checar(not fora, f"nenhuma cor fixa fora dos temas (achou {len(fora)})", " | ".join(fora[:3]))


def test_javascript_compila() -> None:
    print("\njavascript da pagina compila")
    node = shutil.which("node")
    if not node:
        print("  --   node nao encontrado, checagem pulada")
        return

    _, js = _partes(PAGINA.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        alvo = Path(tmp) / "pagina.js"
        alvo.write_text(js, encoding="utf-8")
        r = subprocess.run([node, "--check", str(alvo)], capture_output=True, text=True)
    checar(r.returncode == 0, "sem erro de sintaxe", (r.stderr or "").strip()[:200])


def test_nome_de_funcao_nao_se_repete() -> None:
    """
    Duas funcoes com o mesmo nome: a segunda apaga a primeira, calada.

    Este teste existe porque aconteceu. A pagina tem oito mil linhas num
    arquivo so, e "blocoComprovantes" ja existia dentro da ficha de lancamento
    quando nasceu outra com o mesmo nome no bloco do escritorio. O JavaScript
    nao reclama: fica com a ultima, e o bloco novo simplesmente nao aparece na
    tela - sem erro no console, sem nada para procurar.
    """
    print("\nnenhum nome de funcao repetido")
    _, js = _partes(PAGINA.read_text(encoding="utf-8"))

    nomes: dict[str, int] = {}
    for m in re.finditer(r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)", js, re.M):
        nomes[m.group(1)] = nomes.get(m.group(1), 0) + 1

    repetidos = sorted(n for n, quantas in nomes.items() if quantas > 1)
    checar(not repetidos,
           f"as {len(nomes)} funcoes tem nomes unicos",
           ", ".join(repetidos))


def test_tela_usa_a_largura() -> None:
    """
    Os recipientes de tela nao tem teto de largura.

    `.centro`, `.catalogo` e `.bancada` sao as tres caixas em que toda tela cai.
    Enquanto tinham `max-width: 1240px`, sobravam 370 px de tela vazia numa
    janela de 1.920 e 1.010 px numa de 2.560 - medido, e em TODAS as telas,
    inclusive as que sao tabela e so ganhavam com a largura.

    Quem precisa de medida e a prosa, e ela tem a propria (--leitura). O teto
    no recipiente atinge tabela, grade e painel junto, que e o que nao se quer -
    e por isso ele nao pode voltar por descuido.
    """
    print("\nas telas usam a largura da coluna")
    css, _ = _partes(PAGINA.read_text(encoding="utf-8"))
    sem_comentario = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    presos = []
    for caixa in (".centro", ".catalogo", ".bancada"):
        m = re.search(re.escape(caixa) + r"\s*\{([^}]*)\}", sem_comentario)
        if not m:
            presos.append(caixa + " (regra sumiu)")
        elif "max-width" in m.group(1):
            presos.append(caixa + ": " + m.group(1).strip()[:40])

    checar(not presos, "nenhum recipiente de tela com teto de largura",
           " | ".join(presos))
    checar("--leitura:" in css, "e a prosa tem a medida dela declarada")


def test_campo_nao_estica_sem_teto() -> None:
    """
    Campo com `flex: 1` e sem `max-width` ocupa a coluna inteira.

    Depois que as telas passaram a usar a largura toda, isso deixou de ser
    detalhe: numa janela de 1.920 o campo de e-mail ficou com 1.490 px e o
    botao ao lado dele a meia tela de distancia, como se nao fosse do mesmo
    campo.

    O erro se repete sozinho porque cada tipo de input tem a sua regra - text,
    password, date, time - e a regra nova nasce copiada da anterior. O de
    password foi achado assim: o de text ja tinha teto, o dele nao.
    """
    print("\ncampo de uma linha nao estica sem teto")
    css, _ = _partes(PAGINA.read_text(encoding="utf-8"))
    sem_comentario = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    soltos = []
    for seletor, bloco in re.findall(r"([^{}]+)\{([^{}]*)\}", sem_comentario):
        alvo = seletor.strip()
        if not re.search(r"\b(input|select|textarea)\b", alvo):
            continue
        if not re.search(r"flex\s*:\s*1\b", bloco):
            continue
        if "max-width" not in bloco:
            soltos.append(alvo.splitlines()[-1].strip()[:50])

    checar(not soltos,
           "todo campo que estica tem teto de largura",
           ", ".join(soltos) + " — falta max-width")


def test_plural_em_portugues() -> None:
    """
    plural() poe um "s" no fim. Em portugues isso nem sempre da certo.

    "3 alteraçãos", "6 valors". Sao erros que nao quebram nada e por isso
    ficam: aparecem num canto da tela, ninguem abre chamado, e o programa passa
    a parecer feito as pressas - num produto que se vende para advogado, isso
    conta.

    A funcao aceita o plural certo como terceiro argumento. Este teste cobra
    esse argumento das palavras cujo plural nao e so "+s".
    """
    print("\nplural das palavras que nao terminam em s")
    _, js = _partes(PAGINA.read_text(encoding="utf-8"))

    # Terminacoes em que o portugues nao forma plural so com "s".
    #   -ao -> -oes/-aes/-aos    -r/-z/-s -> -es
    #   -l  -> -is/-eis          -m -> -ns
    teimosas = ("ão", "ãe", "r", "z", "s", "l", "m")

    erradas = []
    for chamada in re.finditer(r"plural\(([^()]*(?:\([^()]*\)[^()]*)*)\)", js):
        partes = _argumentos(chamada.group(1))
        if len(partes) < 2 or len(partes) > 2:
            continue                      # ja passou o plural certo, ou e a propria definicao
        palavra = partes[1].strip()
        if not (palavra.startswith('"') and palavra.endswith('"')):
            continue                      # palavra vinda de variavel: nao da para conferir aqui
        nua = palavra.strip('"').split(" ")[-1].lower()
        if nua.endswith(teimosas):
            erradas.append(nua)

    checar(not erradas,
           "toda palavra teimosa passa o plural certo como 3o argumento",
           ", ".join(sorted(set(erradas))) + " — use plural(n, \"x\", \"xs certo\")")


def _argumentos(bruto: str) -> list[str]:
    """Separa os argumentos de uma chamada, sem cortar dentro de aspas."""
    partes, atual, aspas = [], "", ""
    for c in bruto:
        if aspas:
            atual += c
            if c == aspas:
                aspas = ""
            continue
        if c in "\"'":
            aspas = c
            atual += c
        elif c == ",":
            partes.append(atual)
            atual = ""
        else:
            atual += c
    partes.append(atual)
    return partes


def test_rota_fixa_antes_da_com_parametro() -> None:
    """
    "/api/documentos/importar" tem que ser declarada antes de
    "/api/documentos/{id_}".

    O FastAPI casa na ordem de declaracao: com a parametrizada na frente,
    "importar" vira um id e a rota devolve "unable to parse string as an
    integer". Ja aconteceu duas vezes neste arquivo - com /modelos e com
    /importar - e da sempre o mesmo erro confuso.
    """
    print("\nordem das rotas")
    fonte = (RAIZ / "src" / "api.py").read_text(encoding="utf-8")

    rotas = re.findall(r'@app\.(get|post|put|delete)\("([^"]+)"', fonte)
    posicao = {}
    for i, (metodo, caminho) in enumerate(rotas):
        posicao.setdefault((metodo, caminho), i)

    problemas = []
    for (metodo, caminho), onde in posicao.items():
        if "{" not in caminho:
            continue
        prefixo = caminho[:caminho.index("{")]
        for (m2, fixa), onde2 in posicao.items():
            if m2 != metodo or "{" in fixa or not fixa.startswith(prefixo):
                continue
            resto = fixa[len(prefixo):]
            # So conta quando a fixa ocuparia o lugar do parametro: um
            # segmento so, sem barra depois.
            if resto and "/" not in resto and onde2 > onde:
                problemas.append(f"{metodo.upper()} {fixa} depois de {caminho}")

    checar(not problemas,
           f"as {len(posicao)} rotas estao em ordem",
           "; ".join(problemas))


def test_sem_internet() -> None:
    print("\na pagina nao busca nada na internet")
    html = PAGINA.read_text(encoding="utf-8")
    css_fontes = (RAIZ / "frontend" / "fontes.css").read_text(encoding="utf-8")

    externos = re.findall(r'(?:src|href)="(https?://[^"]+)"', html)
    checar(not externos, "nenhum recurso externo na pagina", ", ".join(externos[:3]))

    remotas = re.findall(r"url\((https?://[^)]+)\)", css_fontes)
    checar(not remotas, "nenhuma fonte remota", ", ".join(remotas[:3]))

    arquivos = re.findall(r"url\(([^)]+\.woff2)\)", css_fontes)
    sumidos = [a for a in arquivos if not (RAIZ / "frontend" / a).exists()]
    checar(not sumidos, f"as {len(arquivos)} fontes citadas existem", ", ".join(sumidos[:3]))


def main() -> int:
    print("=" * 55)
    print("  PAULUS - integridade da interface")
    print("=" * 55)

    if not PAGINA.exists():
        print(f"\nERRO: nao achei {PAGINA}")
        return 1

    test_css_completo()
    test_css_bem_formado()
    test_sem_regra_repetida()
    test_ids()
    test_tokens()
    test_javascript_compila()
    test_nome_de_funcao_nao_se_repete()
    test_tela_usa_a_largura()
    test_campo_nao_estica_sem_teto()
    test_plural_em_portugues()
    test_rota_fixa_antes_da_com_parametro()
    test_sem_internet()

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
