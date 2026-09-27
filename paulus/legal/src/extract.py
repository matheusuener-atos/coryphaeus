"""
PAULUS Legal - Extracao de texto de contratos.

Suporta PDF, DOCX, TXT e MD. Mantem um cache em JSON para nao reprocessar
arquivos que nao mudaram entre execucoes (extracao de PDF grande e lenta).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

# .xlsx desde 27/09/2026: a planilha que o editor guarda e a do Financeiro
# vao para o Acervo, e o Acervo precisa le-las (antes, ficavam na pasta sem
# aparecer).
SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt", ".md", ".xlsx"}
# Pagina de PDF com menos texto que isto vai para o OCR: o carimbo de um
# escaneado ("Digitalizado por...") nao e o documento.
MIN_TEXTO_DA_PAGINA = 20


@dataclass
class Document:
    """Um contrato ja extraido para texto puro."""

    name: str
    path: str
    text: str
    pages: int = 0
    sha1: str = ""
    # Quantas paginas vieram de imagem, pelo OCR (src/ocr_windows.py): texto que pode
    # ter erro de leitura, e a tela avisa.
    ocr: int = 0

    @property
    def chars(self) -> int:
        return len(self.text)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Document":
        return cls(
            name=data["name"],
            path=data["path"],
            text=data["text"],
            pages=data.get("pages", 0),
            sha1=data.get("sha1", ""),
            ocr=data.get("ocr", 0),
        )


# --------------------------------------------------------------------------
# Extratores por formato
# --------------------------------------------------------------------------


def _texto_da_pagina(page) -> str:
    """
    O texto de uma pagina, na ordem em que se le.

    O modo padrao do pypdf devolve na ordem em que o PDF desenha, que num
    formulario nao e a ordem de leitura: um comprovante de viagem saia como

        Nome
        JOSE MARCIO CAMPOS TEIXEIRA
        PA - SAO FELIX DO XINGU
        Destino

    com o rotulo depois do valor, e "Partida" e "Retorno" soltos longe de
    tudo. Rotulo separado do valor e um documento que nao da para responder:
    nao ha como saber o que e de quem.

    No modo layout o mesmo documento sai com "Destino  PA - SAO FELIX DO
    XINGU" na mesma linha. Nos contratos em prosa a diferenca e nenhuma -
    medido, +-2% de palavras nos cinco PDFs do acervo - e custa 340 ms a mais
    na indexacao inteira, que acontece uma vez e fica em cache.
    """
    for modo in ("layout", None):
        try:
            texto = (page.extract_text(extraction_mode=modo) if modo
                     else page.extract_text()) or ""
        except Exception:
            continue
        if texto.strip():
            return texto
    return ""


def extract_pdf(path: Path) -> tuple[str, int]:
    """Extrai texto de um PDF. Retorna (texto, numero_de_paginas)."""
    texto, paginas, _ = extract_pdf_info(path)
    return texto, paginas


def extract_pdf_info(path: Path) -> tuple[str, int, int]:
    """
    Texto, numero de paginas e quantas delas vieram de imagem.

    Pagina sem texto proprio - escaneada - vai para o OCR do Windows
    (src/ocr_windows.py). Pagina a pagina, e nao o arquivo inteiro: um contrato
    digitado com a ultima pagina assinada e escaneada tem as duas coisas.
    """
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    if reader.is_encrypted:
        # Muitos PDFs juridicos vem "protegidos" apenas contra edicao,
        # com senha vazia. Tentamos abrir antes de desistir.
        try:
            reader.decrypt("")
        except Exception as exc:  # pragma: no cover - depende do arquivo
            raise RuntimeError(f"PDF protegido por senha: {path.name}") from exc

    textos: dict[int, str] = {}
    sem_texto: list[int] = []
    for i, page in enumerate(reader.pages, start=1):
        texto = _texto_da_pagina(page).strip()
        textos[i] = texto
        if len(texto) < MIN_TEXTO_DA_PAGINA:
            sem_texto.append(i)

    lidas_por_ocr = 0
    if sem_texto:
        import ocr_windows as ocr

        if ocr.situacao()["ok"]:
            for n, texto in ocr.ler_paginas(path, sem_texto).items():
                if len(texto) > len(textos[n]):
                    textos[n] = texto
                    lidas_por_ocr += 1

    partes = [f"[pagina {i}]\n{t}" for i, t in textos.items() if t]
    return "\n\n".join(partes), len(reader.pages), lidas_por_ocr


def motivo_sem_texto(path: Path) -> str:
    """
    Por que um arquivo nao virou texto, dito do jeito certo.

    A tela dizia "PDF escaneado?" para tudo - inclusive para um arquivo de 0
    bytes, que era um download que nao terminou.
    """
    try:
        tamanho = path.stat().st_size
    except OSError:
        return "o arquivo não foi encontrado"
    if tamanho == 0:
        return "o arquivo está vazio (0 bytes) — o download ou a cópia não terminou; baixe de novo"
    try:
        texto, _ = extract_file(path)
    except Exception as exc:  # noqa: BLE001 - o motivo e o erro
        return "não consegui abrir o arquivo: " + str(exc)[:120]
    if texto.strip():
        return ""
    if path.suffix.lower() == ".pdf":
        import ocr_windows as ocr

        s = ocr.situacao()
        if not s["ok"]:
            return "o PDF é só imagem (escaneado) e " + s["motivo"]
        return "o PDF é só imagem e o leitor de imagem não achou texto nele (página em branco ou foto sem letras)"
    return "o arquivo não tem texto"


def extract_docx(path: Path) -> tuple[str, int]:
    """Extrai texto de um DOCX, incluindo o conteudo das tabelas."""
    import docx

    doc = docx.Document(str(path))
    partes = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    for tabela in doc.tables:
        for linha in tabela.rows:
            celulas = [c.text.strip() for c in linha.cells if c.text.strip()]
            if celulas:
                partes.append(" | ".join(celulas))

    return "\n".join(partes), 0


# Planilha enorme (um extrato de banco com 50 mil linhas) nao vira contexto de
# pergunta: o comeco basta para achar e classificar.
MAX_LINHAS_DA_PLANILHA = 20000


def extract_xlsx(path: Path) -> tuple[str, int]:
    """
    O texto de uma planilha: cada aba com o nome dela, e cada linha com as
    celulas separadas por " | " - o valor calculado, nao a formula.
    """
    from openpyxl import load_workbook

    livro = load_workbook(str(path), read_only=True, data_only=True)
    partes: list[str] = []
    linhas_lidas = 0
    try:
        for aba in livro.worksheets:
            linhas: list[str] = []
            for linha in aba.iter_rows(values_only=True):
                celulas = [str(v).strip() for v in linha if v is not None and str(v).strip()]
                if celulas:
                    linhas.append(" | ".join(celulas))
                    linhas_lidas += 1
                if linhas_lidas >= MAX_LINHAS_DA_PLANILHA:
                    break
            # A aba entra mesmo vazia: a planilha recem-criada existe, e o
            # Acervo mostra - sem texto nenhum, o indice a pularia.
            partes.append(f"[planilha {aba.title}]" + ("\n" + "\n".join(linhas) if linhas else ""))
            if linhas_lidas >= MAX_LINHAS_DA_PLANILHA:
                break
    finally:
        livro.close()
    return "\n\n".join(partes), 0


def extract_txt(path: Path) -> tuple[str, int]:
    return path.read_text(encoding="utf-8", errors="replace"), 0


def extract_file(path: Path) -> tuple[str, int]:
    """Dispatch por extensao. Levanta ValueError se o formato nao e suportado."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(path)
    if suffix == ".docx":
        return extract_docx(path)
    if suffix in {".txt", ".md"}:
        return extract_txt(path)
    if suffix == ".xlsx":
        return extract_xlsx(path)
    raise ValueError(f"Formato nao suportado: {suffix}")


# --------------------------------------------------------------------------
# Indexacao da pasta + cache
# --------------------------------------------------------------------------


def file_sha1(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _load_cache(cache_path: Path) -> dict[str, Document]:
    if not cache_path.exists():
        return {}
    try:
        dados = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {d["sha1"]: Document.from_dict(d) for d in dados.get("documents", []) if d.get("sha1")}


def _save_cache(cache_path: Path, docs: list[Document]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "documents": [d.to_dict() for d in docs]}
    cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def chave_do_caminho(p: str | Path) -> str:
    """O mesmo arquivo, escrito de jeitos diferentes (maiuscula, barra, atalho), vira a mesma chave."""
    import os

    try:
        return os.path.normcase(str(Path(p).resolve()))
    except OSError:
        return os.path.normcase(os.path.abspath(str(p)))


def listar_arquivos(pastas: list[Path], ignorar: set[str] | frozenset = frozenset()) -> list[Path]:
    """
    Os documentos que o Acervo le nas pastas vigiadas.

    Fica de fora: pasta de sistema e de programa (scan.PASTAS_IGNORADAS) e
    pasta oculta, o arquivo temporario que o Word deixa enquanto o documento
    esta aberto ("~$contrato.docx", que nao abre) e o que a pessoa tirou do
    Acervo (`ignorar`, chaves de chave_do_caminho). Pasta dentro de outra da
    lista nao conta duas vezes.
    """
    import os

    from scan import PASTAS_IGNORADAS

    vistos: set[str] = set()
    saida: list[Path] = []
    for pasta in pastas:
        for raiz, subpastas, nomes in os.walk(pasta):
            subpastas[:] = [d for d in subpastas if d.lower() not in PASTAS_IGNORADAS and not d.startswith(".")]
            for nome in nomes:
                if nome.startswith("~$") or Path(nome).suffix.lower() not in SUPPORTED_SUFFIXES:
                    continue
                caminho = Path(raiz) / nome
                chave = chave_do_caminho(caminho)
                if chave in vistos or chave in ignorar:
                    continue
                vistos.add(chave)
                saida.append(caminho)
    saida.sort()
    return saida


# O sha1 de cada arquivo, lembrado por caminho, tamanho e data. Reler o acervo
# lia TODOS os arquivos de ponta a ponta so para saber se mudaram; com a vigia
# das pastas relendo quando algo muda, isso seria ler gigabytes a cada novo
# documento. Arquivo que nao mudou de tamanho nem de data nao e lido de novo.
_SHA1_LEMBRADO: dict[tuple[str, int, int], str] = {}


def sha1_lembrado(path: Path) -> str:
    st = path.stat()
    chave = (str(path), st.st_size, st.st_mtime_ns)
    sha = _SHA1_LEMBRADO.get(chave)
    if sha is None:
        sha = file_sha1(path)
        _SHA1_LEMBRADO[chave] = sha
    return sha


def index_all_contracts(
    folder: Path | list[Path],
    cache_path: Path | None = None,
    *,
    force: bool = False,
    verbose: bool = True,
    ignorar: set[str] | frozenset = frozenset(),
    progresso=None,
) -> list[Document]:
    """
    Extrai todos os contratos de `folder` (recursivamente) - ou de varias
    pastas, numa passada so.

    Varias pastas vao juntas, e nao numa chamada por pasta, porque o cache e
    gravado inteiro no fim: a segunda chamada apagaria do cache o que a
    primeira leu. Pasta dentro de outra da lista nao conta duas vezes.

    Arquivos ja extraidos com o mesmo conteudo (mesmo sha1) sao lidos do cache.
    Passe force=True para reprocessar tudo.
    """
    pastas = [Path(f) for f in (folder if isinstance(folder, (list, tuple)) else [folder])]
    pastas = [p for p in pastas if p.exists()]
    if not pastas:
        return []

    cache = {} if (force or cache_path is None) else _load_cache(Path(cache_path))
    docs: list[Document] = []

    arquivos = listar_arquivos(pastas, ignorar)

    for indice, path in enumerate(arquivos, start=1):
        if progresso:
            progresso(indice, len(arquivos), path.name)
        try:
            sha = sha1_lembrado(path)
        except OSError:
            continue  # sumiu entre listar e ler
        if sha in cache:
            # Copia, e nao o objeto do cache. Dois arquivos iguais byte a byte
            # - "contrato.pdf" e "contrato (1).pdf" - tem o mesmo sha1 e caem
            # nesta linha os dois. Mexer no objeto guardado fazia o segundo
            # sobrescrever o caminho e o nome do primeiro, e a biblioteca
            # passava a mostrar a copia duas vezes, com o original sumido da
            # lista. O texto e o mesmo; o caminho e o nome nao sao.
            doc = replace(cache[sha], path=str(path), name=path.name)
            docs.append(doc)
            if verbose:
                print(f"  = {path.name} (cache)")
            continue

        try:
            if path.suffix.lower() == ".pdf":
                texto, paginas, lidas_por_ocr = extract_pdf_info(path)
            else:
                (texto, paginas), lidas_por_ocr = extract_file(path), 0
        except Exception as exc:
            if verbose:
                print(f"  ! {path.name}: {exc}")
            continue

        if not texto.strip():
            if verbose:
                print(f"  ! {path.name}: sem texto ({motivo_sem_texto(path)})")
            continue

        doc = Document(name=path.name, path=str(path), text=texto, pages=paginas, sha1=sha, ocr=lidas_por_ocr)
        if verbose and lidas_por_ocr:
            print(f"  ~ {path.name}: {lidas_por_ocr} pagina(s) lida(s) da imagem (OCR)")
        docs.append(doc)
        if verbose:
            print(f"  + {path.name} ({doc.chars:,} chars)".replace(",", "."))

    if cache_path is not None:
        _save_cache(Path(cache_path), docs)

    return docs


if __name__ == "__main__":
    import sys

    pasta = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent / "data" / "test_contracts"
    documentos = index_all_contracts(pasta)
    print(f"\n{len(documentos)} documento(s) extraido(s) de {pasta}")
