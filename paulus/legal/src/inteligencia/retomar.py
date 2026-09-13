"""
O acervo que ja existe: analisar o que esta la, sem atrapalhar quem trabalha.

Quando a camada entra em funcionamento, o escritorio ja tem documentos - e os
documentos ja indexados sao justamente os que mais recebem pergunta. Este
modulo passa por eles uma vez.

Tres regras, e todas vem da mesma preocupacao: a maquina e de alguem que esta
usando o computador.

**Um documento por vez.** A ingestao disputa processador com o assistente.
Analisar dez em paralelo deixaria a conversa lenta justamente enquanto a
pessoa espera resposta.

**Retomavel.** Um acervo grande nao termina numa sentada. Rodar de novo
continua de onde parou, porque `analisar_documento` e idempotente: o que ja
esta bom nao e refeito.

**Regra primeiro.** Rodar so os extratores de nivel 0 sobre o acervo inteiro
leva segundos por documento, nao usa modelo nenhum e ja liga boa parte do
caminho rapido. Os extratores de modelo entram depois, em janela ociosa.

Enquanto um documento nao tiver metadata, ele continua respondendo pelo
caminho de hoje - sem erro, sem aviso, sem regressao.

    venv\\Scripts\\python.exe -m inteligencia.retomar --secoes case,dates,amounts,legal_references
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from base import Base                              # noqa: E402
from config import Preferencias                    # noqa: E402
from extract import index_all_contracts            # noqa: E402
from inteligencia import portas                    # noqa: E402
from inteligencia.catalogo import Catalogo         # noqa: E402
from inteligencia.guarda import Biblioteca, raiz_padrao   # noqa: E402

CACHE = RAIZ / "data" / "extractions" / "index.json"
BANCO = RAIZ / "data" / "paulus.db"
PREFERENCIAS = RAIZ / "data" / "preferencias.json"


def pasta_do_acervo() -> Path:
    """A pasta que a pessoa escolheu na tela - nao uma pasta inventada aqui."""
    prefs = Preferencias(PREFERENCIAS)
    pastas = prefs.dados.get("pastas") or []
    if pastas:
        return Path(pastas[0])
    return RAIZ / "data" / "test_contracts"


def exportar_sidecars(biblioteca, documentos) -> int:
    """
    Escreve o metadata ao lado de cada documento, por pedido explicito.

    Isto NAO e o padrao, e a flag existe justamente para que seja uma escolha
    consciente. O metadata tem as partes, os valores e as teses em texto
    plano, prontos para qualquer coisa ler - ele costuma ser mais sensivel que
    o PDF que descreve, e a pasta de trabalho de um escritorio quase sempre
    esta sincronizada em alguma nuvem. Quem exporta assume isso.

    O arquivo original continua intocado: o que se escreve e um vizinho.
    """
    import json

    escritos = 0
    for doc in documentos:
        meta = biblioteca.ler_por_sha1(doc.sha1) or biblioteca.ler_por_caminho(doc.path)
        if not meta:
            continue
        alvo = Path(doc.path).with_suffix(Path(doc.path).suffix + ".meta.json")
        try:
            alvo.write_text(json.dumps(meta.to_dict(), ensure_ascii=False, indent=1),
                            encoding="utf-8")
            escritos += 1
        except OSError as exc:
            print(f"  ! {alvo.name}: {exc}")
    return escritos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analisa o acervo existente para a camada de inteligencia.")
    parser.add_argument("--pasta", default="", help="onde estao os documentos (padrao: a do programa)")
    parser.add_argument("--secoes", default="", help="quais secoes rodar, separadas por virgula")
    parser.add_argument("--limite", type=int, default=0, help="para depois de N documentos")
    parser.add_argument("--forcar", action="store_true", help="refaz secao que ja estava boa")
    parser.add_argument("--assistente", action="store_true",
                        help="liga o modelo para as secoes que precisam dele")
    parser.add_argument("--sidecar", action="store_true",
                        help="ALEM de analisar, escreve <documento>.meta.json ao lado de cada arquivo")
    argumentos = parser.parse_args(argv)

    pasta = Path(argumentos.pasta) if argumentos.pasta else pasta_do_acervo()
    if not pasta.is_dir():
        print(f"a pasta {pasta} nao existe")
        return 1

    catalogo = Catalogo.carregar()
    problemas = catalogo.problemas()
    if problemas:
        print("o catalogo tem problema:")
        for linha in problemas:
            print("  -", linha)
        return 1

    base = Base(BANCO)
    base.migrar()
    biblioteca = Biblioteca(raiz_padrao(RAIZ), base)

    client = None
    if argumentos.assistente:
        from llama_client import LlamaClient, check_ollama

        ligado, motivo = check_ollama()
        if not ligado:
            print(f"o assistente nao esta ligado ({motivo}) - rodando so as regras")
        else:
            client = LlamaClient()

    secoes = [s.strip() for s in argumentos.secoes.split(",") if s.strip()] or None
    documentos = index_all_contracts(pasta, CACHE, verbose=False)
    if argumentos.limite:
        documentos = documentos[: argumentos.limite]

    print(f"acervo: {len(documentos)} documento(s) em {pasta}")
    comeco = time.time()
    mexidos = 0
    for i, doc in enumerate(documentos, start=1):
        try:
            analise = portas.analisar_documento(
                biblioteca, catalogo, doc.path, texto=doc.text, paginas=doc.pages,
                sha1=doc.sha1, titulo=doc.name, secoes=secoes, forcar=argumentos.forcar,
                client=client)
        except Exception as exc:   # um documento torto nao para o acervo
            print(f"  {i:3d}. {doc.name}: FALHOU ({type(exc).__name__}: {exc})")
            continue
        if analise.mudou:
            mexidos += 1
            print(f"  {i:3d}. {doc.name}: " + ", ".join(analise.rodadas) + f" ({analise.ms} ms)")
        else:
            print(f"  {i:3d}. {doc.name}: ja estava em dia")
        for secao, erro in (analise.falhas or {}).items():
            print(f"       ! {secao}: {erro}")

    if argumentos.sidecar:
        escritos = exportar_sidecars(biblioteca, documentos)
        print(f"\n{escritos} arquivo(s) .meta.json escritos AO LADO dos documentos.")
        print("  Atencao: o metadata tem partes, valores e teses em texto plano - "
              "costuma ser mais sensivel que o proprio documento.")

    situacao = biblioteca.situacao()
    print(f"\n{mexidos} documento(s) analisado(s) em {round(time.time() - comeco, 1)} s")
    print(f"biblioteca: {situacao['documentos']} documento(s)")
    for secao, estados in sorted(situacao["secoes"].items()):
        print("  " + secao + ": " + ", ".join(f"{k} {v}" for k, v in sorted(estados.items())))
    base.fechar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
