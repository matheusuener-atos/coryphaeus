"""
PAULUS Legal - Chat CLI sobre contratos.

Fluxo: pergunta -> busca BM25 nos contratos -> trechos relevantes -> Llama -> resposta.

Uso:
    python src/main.py                          # chat interativo
    python src/main.py --ask "Qual o prazo?"    # pergunta unica
    python src/main.py --reindex                # forca reextracao dos PDFs
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from extract import SUPPORTED_SUFFIXES, index_all_contracts  # noqa: E402
from llama_client import DEFAULT_MODEL, LlamaClient, OllamaError, check_ollama  # noqa: E402
from search import ContractSearcher  # noqa: E402

BASE_DIR = Path(__file__).parent.parent
CONTRACTS_DIR = BASE_DIR / "data" / "test_contracts"
CACHE_PATH = BASE_DIR / "data" / "extractions" / "index.json"

AJUDA = """
Comandos:
  /docs         lista os contratos carregados
  /buscar TEXTO busca sem chamar o LLM (rapido, mostra os trechos)
  /trechos      mostra os trechos usados na ultima resposta
  /top N        muda quantos trechos vao para o LLM (atual: {top})
  /reindex      reextrai os contratos da pasta
  /ajuda        esta mensagem
  /sair         encerra
"""


def _configurar_saida() -> None:
    """Evita UnicodeEncodeError no console do Windows (cp1252)."""
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def carregar(pasta: Path, *, reindex: bool = False) -> ContractSearcher:
    print(f"\nCarregando contratos de {pasta}")
    docs = index_all_contracts(pasta, CACHE_PATH, force=reindex)

    if not docs:
        formatos = ", ".join(sorted(SUPPORTED_SUFFIXES))
        print(
            f"\nNenhum contrato encontrado.\n"
            f"  Coloque arquivos ({formatos}) em: {pasta}\n"
        )
        return ContractSearcher()

    searcher = ContractSearcher()
    searcher.add_contracts(docs)
    searcher.build()
    total_chars = sum(d.chars for d in docs)
    print(
        f"\n{len(docs)} contrato(s), {len(searcher.chunks)} trecho(s) indexados "
        f"({total_chars:,} caracteres)".replace(",", ".")
    )
    return searcher


def mostrar_hits(hits: list, com_score: bool = True) -> None:
    if not hits:
        print("  (nenhum trecho relevante encontrado)")
        return
    for i, hit in enumerate(hits, start=1):
        score = f"  [score {hit.score:.1f}]" if com_score else ""
        print(f"  {i}. {hit.doc_name} (trecho {hit.chunk.index + 1}){score}")
        print(f"     {hit.snippet}")


def responder(
    searcher: ContractSearcher,
    client: LlamaClient,
    pergunta: str,
    *,
    top: int,
    stream: bool,
) -> list:
    hits = searcher.search(pergunta, top_k=top)

    if not hits:
        print(
            "\nNao encontrei trechos relevantes nos contratos para essa pergunta.\n"
            "Tente outras palavras (ex.: 'rescisao', 'multa', 'vigencia')."
        )
        return []

    contexto = searcher.format_context(hits)
    origens = ", ".join(dict.fromkeys(h.doc_name for h in hits))
    print(f"\n[buscou em: {origens}]")
    print("\nPAULUS: ", end="", flush=True)

    inicio = time.time()
    try:
        if stream:
            client.ask(pergunta, contexto, stream=True, on_token=lambda t: print(t, end="", flush=True))
            print()
        else:
            print(client.ask(pergunta, contexto))
    except OllamaError as exc:
        print(f"\n\nErro: {exc}")
        return hits

    print(f"\n[{time.time() - inicio:.1f}s]")
    return hits


def repl(searcher: ContractSearcher, client: LlamaClient, args: argparse.Namespace) -> None:
    top = args.top
    ultimos_hits: list = []

    print(AJUDA.format(top=top))

    while True:
        try:
            entrada = input("\nVoce: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAte logo.")
            return

        if not entrada:
            continue

        if entrada.startswith("/"):
            comando, _, resto = entrada.partition(" ")
            comando = comando.lower()
            resto = resto.strip()

            if comando in {"/sair", "/quit", "/exit"}:
                print("Ate logo.")
                return

            if comando in {"/ajuda", "/help"}:
                print(AJUDA.format(top=top))

            elif comando == "/docs":
                if not searcher.documents:
                    print("  (nenhum contrato carregado)")
                for doc in searcher.documents:
                    paginas = f", {doc.pages} pag." if doc.pages else ""
                    print(f"  - {doc.name} ({doc.chars:,} chars{paginas})".replace(",", "."))

            elif comando == "/buscar":
                if not resto:
                    print("  uso: /buscar palavra-chave")
                else:
                    ultimos_hits = searcher.search(resto, top_k=top)
                    mostrar_hits(ultimos_hits)

            elif comando == "/trechos":
                mostrar_hits(ultimos_hits)

            elif comando == "/top":
                if resto.isdigit() and 1 <= int(resto) <= 20:
                    top = int(resto)
                    print(f"  agora usando {top} trecho(s) por pergunta")
                else:
                    print("  uso: /top N  (1 a 20)")

            elif comando == "/reindex":
                searcher = carregar(CONTRACTS_DIR, reindex=True)

            else:
                print(f"  comando desconhecido: {comando}")
            continue

        if not searcher.documents:
            print("Nenhum contrato carregado - use /reindex depois de adicionar arquivos.")
            continue

        ultimos_hits = responder(searcher, client, entrada, top=top, stream=not args.no_stream)


def main() -> int:
    _configurar_saida()

    parser = argparse.ArgumentParser(description="PAULUS Legal - chat sobre contratos (100% local)")
    parser.add_argument("--contracts", type=Path, default=CONTRACTS_DIR, help="pasta com os contratos")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"modelo Ollama (padrao: {DEFAULT_MODEL})")
    parser.add_argument("--top", type=int, default=5, help="trechos enviados ao LLM (padrao: 5)")
    parser.add_argument("--ask", help="faz uma pergunta e sai")
    parser.add_argument("--reindex", action="store_true", help="reextrai tudo, ignorando o cache")
    parser.add_argument("--no-stream", action="store_true", help="nao imprime a resposta token a token")
    args = parser.parse_args()

    print("=" * 62)
    print("  PAULUS Legal - MVP  |  Coryphaeus / ATOS")
    print("  Analise de contratos 100% local. Nenhum dado sai desta maquina.")
    print("=" * 62)

    ok, mensagem = check_ollama(args.model)
    print(f"\n{mensagem}")
    if not ok:
        return 1

    searcher = carregar(args.contracts, reindex=args.reindex)
    client = LlamaClient(model=args.model)

    if args.ask:
        if not searcher.documents:
            return 1
        responder(searcher, client, args.ask, top=args.top, stream=not args.no_stream)
        return 0

    repl(searcher, client, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
