"""
Onde o que se sabe fica guardado - e como o documento continua sendo dele.

Duas regras mandam neste modulo.

**O original nunca e tocado.** Nao e movido, nao e renomeado, nao e copiado,
nao e reescrito. O que a camada guarda e uma referencia: o caminho, o tamanho,
o hash e a data. Se o arquivo mudar, a camada percebe pelo hash e cria uma
versao nova, preservando a anterior; se sumir, a camada diz que sumiu. Um
programa que mexe na pasta de um escritorio uma vez perde a confianca para
sempre.

**O metadata nao mora ao lado do documento.** Ele fica numa biblioteca propria
do programa, em `data/conhecimento`. A razao e contraintuitiva e importante: o
metadata costuma ser MAIS sensivel que o documento, porque nele as partes, os
valores e as teses estao em texto plano, prontos para serem lidos por
qualquer coisa - e as pastas de trabalho de um escritorio costumam estar
sincronizadas em nuvem. O sidecar ao lado do PDF existe so como exportacao
explicita de quem pediu.

Identidade, que e o que permite tudo isso funcionar com o tempo:

    documento   a obra       `document.id`   nunca muda
    versao      o conteudo   `version.id`    muda quando o sha256 muda

Nome de arquivo nunca e identidade. Renomear "contrato.pdf" para "contrato
assinado.pdf" nao cria documento novo: o conteudo e o mesmo, e o programa
reconhece pelo hash. Trocar o conteudo no mesmo nome cria versao nova, e a
anterior fica - e ela que sustenta as citacoes ja feitas.
"""

from __future__ import annotations

import json
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import esquema
from .esquema import Metadata, Secao
from .texto import Pagina, mapa_de_paginas

# Base32 de Crockford: id que da para ler em voz alta sem confundir 0 com O.
_ALFABETO = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _ulid() -> str:
    """
    Id ordenavel por tempo, sem depender de biblioteca.

    Ordenavel importa: `ls` na biblioteca sai na ordem em que os documentos
    entraram, e o id mais novo de uma versao e sempre o maior - o que evita
    uma coluna de data so para ordenar.
    """
    agora = int(time.time() * 1000)
    tempo = ""
    for _ in range(10):
        agora, resto = divmod(agora, 32)
        tempo = _ALFABETO[resto] + tempo
    acaso = "".join(secrets.choice(_ALFABETO) for _ in range(16))
    return tempo + acaso


def sha256_do_arquivo(caminho: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def sha256_do_texto(texto: str) -> str:
    import hashlib

    return hashlib.sha256((texto or "").encode("utf-8")).hexdigest()


MIMES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


@dataclass
class Registro:
    """O resultado de registrar um arquivo: quem ele e, e se mudou."""

    metadata: Metadata
    documento_novo: bool = False
    versao_nova: bool = False

    @property
    def document_id(self) -> str:
        return self.metadata.document_id

    @property
    def version_id(self) -> str:
        return self.metadata.version_id


class Biblioteca:
    """A biblioteca de metadata: disco para a verdade, sqlite para achar rapido."""

    def __init__(self, raiz: Path, base) -> None:
        self.raiz = Path(raiz)
        self.base = base
        (self.raiz / "documents").mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------ caminhos

    def pasta_do_documento(self, document_id: str) -> Path:
        return self.raiz / "documents" / document_id

    def pasta_da_versao(self, document_id: str, version_id: str) -> Path:
        return self.pasta_do_documento(document_id) / "versions" / version_id

    # ------------------------------------------------------------ registrar

    def registrar(self, caminho, texto: str, *, paginas: int = 0, sha1: str = "",
                  titulo: str = "", metodo: str = "") -> Registro:
        """
        Poe um arquivo na biblioteca - ou reconhece que ele ja estava la.

        Idempotente de proposito (spec, HOOK 1): rodar de novo no mesmo
        arquivo nao cria nada e nao perde nada. E o que permite chamar isto na
        ingestao sem medo, inclusive em cima de um acervo ja indexado.
        """
        caminho = Path(caminho)
        sha256 = sha256_do_arquivo(caminho) if caminho.exists() else sha256_do_texto(texto)

        # Mesmo conteudo ja registrado: e a mesma versao, mesmo que o arquivo
        # tenha sido renomeado ou movido. O caminho novo e anotado; a
        # identidade nao muda por causa de um nome.
        ja = self.base.um("SELECT * FROM meta_versoes WHERE sha256 = ? ORDER BY criado_em DESC LIMIT 1", (sha256,))
        if ja:
            meta = self.ler(ja["documento_id"], ja["id"])
            if meta:
                if str(caminho) != (ja["caminho"] or ""):
                    meta.version["source_path"] = str(caminho)
                    self.base.escrever("UPDATE meta_versoes SET caminho = ? WHERE id = ?", (str(caminho), ja["id"]))
                    self.base.escrever("UPDATE meta_documentos SET caminho = ? WHERE id = ?",
                                       (str(caminho), ja["documento_id"]))
                    self.gravar(meta, nota="arquivo mudou de lugar")
                return Registro(metadata=meta, documento_novo=False, versao_nova=False)

        # Mesmo caminho, conteudo diferente: versao nova do MESMO documento.
        # A anterior fica - e ela que sustenta as citacoes ja escritas.
        dono = self.base.um("SELECT * FROM meta_documentos WHERE caminho = ?", (str(caminho),))
        document_id = dono["id"] if dono else "doc_" + _ulid()
        version_id = "ver_" + _ulid()
        quando = esquema.agora()

        if not dono:
            self.base.escrever(
                "INSERT INTO meta_documentos (id, titulo, caminho, versao_atual, criado_em, atualizado_em)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (document_id, titulo or caminho.name, str(caminho), version_id, quando, quando))
        else:
            self.base.escrever(
                "UPDATE meta_documentos SET versao_atual = ?, atualizado_em = ? WHERE id = ?",
                (version_id, quando, document_id))

        try:
            mtime = datetime.fromtimestamp(caminho.stat().st_mtime).astimezone().isoformat(timespec="seconds")
        except OSError:
            mtime = ""

        self.base.escrever(
            "INSERT INTO meta_versoes (id, documento_id, sha256, sha1, caminho, mtime, mime, paginas, caracteres, criado_em)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (version_id, document_id, sha256, sha1, str(caminho), mtime,
             MIMES.get(caminho.suffix.lower(), "application/octet-stream"),
             int(paginas or 0), len(texto or ""), quando))

        meta = Metadata(
            document={"id": document_id, "title": titulo or caminho.stem},
            version={
                "id": version_id, "sha256": sha256, "sha1": sha1,
                "source_path": str(caminho), "source_mtime": mtime,
                "mime_type": MIMES.get(caminho.suffix.lower(), "application/octet-stream"),
                "page_count": int(paginas or 0), "char_count": len(texto or ""),
            },
            provenance={
                "extraction_method": metodo or _metodo_de(caminho, texto),
                "ocr_used": False,
                "text_sha256": sha256_do_texto(texto),
            },
        )

        self._gravar_extraido(document_id, version_id, caminho, texto, sha256)
        self.gravar(meta, nota="versao registrada")
        return Registro(metadata=meta, documento_novo=not dono, versao_nova=True)

    def _gravar_extraido(self, document_id: str, version_id: str, caminho: Path,
                         texto: str, sha256: str) -> None:
        pasta = self.pasta_da_versao(document_id, version_id) / "extracted"
        pasta.mkdir(parents=True, exist_ok=True)
        # O texto e guardado como esta - sem normalizar. Ele e a regua: todo
        # span gravado no metadata aponta para posicoes DESTE arquivo, e o
        # buscador ja trabalha sobre o mesmo texto.
        (pasta / "text.txt").write_text(texto or "", encoding="utf-8")
        paginas = mapa_de_paginas(texto or "")
        (pasta / "layout.json").write_text(
            json.dumps({"paginas": [p.to_dict() for p in paginas]}, ensure_ascii=False),
            encoding="utf-8")
        (self.pasta_da_versao(document_id, version_id) / "source.link").write_text(
            json.dumps({"path": str(caminho), "sha256": sha256,
                        "mtime": _mtime(caminho), "size": _tamanho(caminho)},
                       ensure_ascii=False, indent=1),
            encoding="utf-8")
        alvo = self.pasta_do_documento(document_id) / "document.json"
        cadeia = []
        if alvo.exists():
            try:
                cadeia = json.loads(alvo.read_text(encoding="utf-8")).get("versions", [])
            except (json.JSONDecodeError, OSError):
                cadeia = []
        if version_id not in cadeia:
            cadeia.append(version_id)
        alvo.write_text(json.dumps({"id": document_id, "versions": cadeia,
                                    "current": version_id}, ensure_ascii=False, indent=1),
                        encoding="utf-8")

    # ---------------------------------------------------------------- ler

    def ler(self, document_id: str, version_id: str = "") -> Metadata | None:
        if not version_id:
            linha = self.base.um("SELECT versao_atual FROM meta_documentos WHERE id = ?", (document_id,))
            version_id = (linha or {}).get("versao_atual") or ""
        alvo = self.pasta_da_versao(document_id, version_id) / "metadata.json"
        if not alvo.exists():
            return None
        try:
            return Metadata.from_dict(json.loads(alvo.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            return None

    def ler_por_versao(self, version_id: str) -> Metadata | None:
        linha = self.base.um("SELECT documento_id FROM meta_versoes WHERE id = ?", (version_id,))
        return self.ler(linha["documento_id"], version_id) if linha else None

    def ler_por_caminho(self, caminho) -> Metadata | None:
        linha = self.base.um("SELECT id, versao_atual FROM meta_documentos WHERE caminho = ?", (str(caminho),))
        return self.ler(linha["id"], linha["versao_atual"]) if linha else None

    def ler_por_sha1(self, sha1: str) -> Metadata | None:
        """O acervo deste programa identifica arquivo por sha1 - a ponte e aqui."""
        linha = self.base.um(
            "SELECT documento_id, id FROM meta_versoes WHERE sha1 = ? ORDER BY criado_em DESC LIMIT 1", (sha1,))
        return self.ler(linha["documento_id"], linha["id"]) if linha else None

    def texto_da_versao(self, document_id: str, version_id: str) -> str:
        alvo = self.pasta_da_versao(document_id, version_id) / "extracted" / "text.txt"
        return alvo.read_text(encoding="utf-8") if alvo.exists() else ""

    def paginas_da_versao(self, document_id: str, version_id: str) -> list[Pagina]:
        alvo = self.pasta_da_versao(document_id, version_id) / "extracted" / "layout.json"
        if not alvo.exists():
            return []
        try:
            dados = json.loads(alvo.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return [Pagina.from_dict(p) for p in dados.get("paginas", [])]

    # -------------------------------------------------------------- gravar

    def gravar(self, meta: Metadata, nota: str = "") -> None:
        """
        Grava o metadata e deixa rastro do que mudou.

        Nunca sobrescreve em silencio: cada gravacao vira uma linha no
        historico da versao, com o que cada secao tinha naquele momento. E o
        que permite responder "por que este documento passou a dizer isto?"
        seis meses depois.
        """
        pasta = self.pasta_da_versao(meta.document_id, meta.version_id)
        pasta.mkdir(parents=True, exist_ok=True)
        provisorio = pasta / "metadata.json.novo"
        provisorio.write_text(json.dumps(meta.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
        provisorio.replace(pasta / "metadata.json")

        with (pasta / "analysis-history.jsonl").open("a", encoding="utf-8") as historico:
            historico.write(json.dumps({
                "quando": esquema.agora(),
                "nota": nota,
                "secoes": {nome: meta.secao(nome).to_dict()
                           for nome in (meta.analysis.get("sections") or {})},
            }, ensure_ascii=False) + "\n")

        self._indexar(meta)

    def _indexar(self, meta: Metadata) -> None:
        """O espelho no sqlite: e ele que o roteador consulta em milissegundos."""
        versao = meta.version_id
        self.base.escrever("DELETE FROM meta_secoes WHERE versao_id = ?", (versao,))
        self.base.escrever("DELETE FROM meta_fatos WHERE versao_id = ?", (versao,))

        for nome, bruto in (meta.analysis.get("sections") or {}).items():
            ficha = Secao.from_dict(bruto)
            self.base.escrever(
                "INSERT INTO meta_secoes (versao_id, secao, extrator, modelo, digest, prompt_versao,"
                " esquema_versao, estado, itens, nao_verificados, ms, quando)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (versao, nome, ficha.extractor, ficha.model or "", ficha.model_digest,
                 ficha.prompt_version, ficha.schema_version, ficha.status, ficha.item_count,
                 ficha.unverified_count, ficha.duration_ms, ficha.generated_at))

        for secao in esquema.SECOES_COLECAO:
            if not meta.secao(secao).utilizavel:
                continue
            for item in meta.colecao(secao):
                self.base.escrever(
                    "INSERT INTO meta_fatos (versao_id, documento_id, secao, item_id, chave, valor,"
                    " mostrar, numero, pagina, verificado, certeza)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (versao, meta.document_id, secao, item.id, _chave_do(item), _valor_do(item),
                     item.valor, _numero_do(item), item.source.page,
                     1 if item.pode_virar_fato else 0, item.certainty))

        for nome, campo in (("case", "case_number"), ("jurisdiction", "court"),
                            ("classification", "document_type")):
            objeto = meta.por_secao(nome) or {}
            if meta.secao(nome).utilizavel and objeto.get(campo):
                self.base.escrever(
                    "INSERT INTO meta_fatos (versao_id, documento_id, secao, item_id, chave, valor,"
                    " mostrar, numero, pagina, verificado, certeza)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (versao, meta.document_id, nome, nome, campo,
                     str(objeto[campo]).lower(), str(objeto[campo]), None,
                     (objeto.get("source") or {}).get("page"),
                     1 if objeto.get("verified", True) else 0,
                     objeto.get("certainty", "explicit")))

    # ------------------------------------------------------------- listar

    def listar(self) -> list[dict]:
        return self.base.buscar(
            "SELECT d.id AS documento_id, d.titulo, d.caminho, v.id AS versao_id, v.sha256,"
            " v.sha1, v.paginas, v.caracteres, v.criado_em"
            " FROM meta_documentos d JOIN meta_versoes v ON v.id = d.versao_atual"
            " ORDER BY d.atualizado_em DESC")

    def situacao(self) -> dict:
        """Quanto do acervo ja tem metadata, por secao - o painel do backfill."""
        documentos = self.base.um("SELECT COUNT(*) AS n FROM meta_documentos") or {"n": 0}
        por_secao = self.base.buscar(
            "SELECT secao, estado, COUNT(*) AS n FROM meta_secoes"
            " JOIN meta_documentos d ON d.versao_atual = meta_secoes.versao_id"
            " GROUP BY secao, estado")
        resumo: dict = {}
        for linha in por_secao:
            resumo.setdefault(linha["secao"], {})[linha["estado"]] = linha["n"]
        return {"documentos": documentos["n"], "secoes": resumo}

    # -------------------------------------------------------- invalidacao

    def envelhecer(self, secao: str, motivo: str, quais: list[str] | None = None) -> int:
        """
        Marca uma secao como `stale` - no acervo inteiro, ou nos que se disser.

        Trocar de extrator nao apaga nada e nao reprocessa nada: marca. Secao
        `stale` o roteador trata como inexistente, entao a resposta volta a
        ser a de hoje enquanto o reprocessamento nao chega. Nao ha janela em
        que o programa responda com o que ele mesmo ja sabe estar velho.
        """
        alvos = quais or [linha["documento_id"] for linha in self.listar()]
        mexidos = 0
        for document_id in alvos:
            meta = self.ler(document_id)
            if not meta:
                continue
            ficha = meta.secao(secao)
            if ficha.status not in ("ok", "failed"):
                continue
            ficha.status = "stale"
            ficha.stale_reason = motivo
            meta.marcar_secao(secao, ficha)
            self.gravar(meta, nota=f"secao {secao} marcada stale: {motivo}")
            mexidos += 1
        return mexidos

    def desatualizadas(self, meta: Metadata, catalogo) -> list[str]:
        """Quais secoes deste documento ficaram para tras do catalogo atual."""
        velhas = []
        for nome in esquema.SECOES:
            ficha = meta.secao(nome)
            if ficha.status in ("missing", "stale"):
                velhas.append(nome)
                continue
            extrator = catalogo.para_secao(nome)
            if not extrator:
                continue
            if (ficha.extractor != extrator.id
                    or ficha.prompt_version != extrator.prompt_version
                    or ficha.schema_version != "v0"):
                velhas.append(nome)
        return velhas


def _metodo_de(caminho: Path, texto: str) -> str:
    sufixo = caminho.suffix.lower()
    if sufixo == ".pdf":
        return "pdf-text" if (texto or "").strip() else "pdf-ocr"
    if sufixo == ".docx":
        return "docx-parser"
    return "manual" if not sufixo else "html-parser" if sufixo in (".html", ".htm") else "manual"


def _mtime(caminho: Path) -> str:
    try:
        return datetime.fromtimestamp(caminho.stat().st_mtime).astimezone().isoformat(timespec="seconds")
    except OSError:
        return ""


def _tamanho(caminho: Path) -> int:
    try:
        return caminho.stat().st_size
    except OSError:
        return 0


def _chave_do(item) -> str:
    """O que o item e dentro da secao: o papel da parte, o tipo da data."""
    for chave in ("role", "kind", "type", "instrument"):
        if item.dados.get(chave):
            return str(item.dados[chave]).lower()
    return ""


def _valor_do(item) -> str:
    """A forma de comparar: minuscula, sem espaco sobrando."""
    return " ".join(str(item.valor).lower().split())


def _numero_do(item) -> float | None:
    for chave in ("value", "amount", "number"):
        bruto = item.dados.get(chave)
        if isinstance(bruto, (int, float)):
            return float(bruto)
    return None


# O caminho da pasta do usuario nunca entra aqui: `data/` e do programa.
def raiz_padrao(base_dir: Path) -> Path:
    return Path(base_dir) / "data" / "conhecimento"
