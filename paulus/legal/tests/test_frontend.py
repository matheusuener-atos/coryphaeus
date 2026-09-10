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
    test_ids()
    test_tokens()
    test_javascript_compila()
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
