"""
Material de consulta: o que o escritório entrega ao PAULUS para ele aprender.

Um manual interno, a tabela de honorários da OAB, um livro de doutrina, as
normas de um tribunal. Não é documento de cliente - é referência. Por isso
mora num índice próprio, separado do Acervo.

O que "aprender" quer dizer aqui, sem exagero: o PAULUS lê o arquivo uma vez,
guarda o texto nesta máquina com a página de cada trecho e, em cada pergunta
da conversa, procura nele os trechos que têm a ver - e os lê junto com os
documentos, citando o material e a página. Não é treinar o modelo: o modelo
continua o mesmo, e a resposta sempre mostra de onde saiu. É o que dá para
fazer com garantia num computador sem placa de vídeo, e é o que dá para
conferir.

Diferente dos lembretes (src/contextos.py): lembrete é regra curta que vai em
TODA pergunta; material é grande, e só os trechos que importam vão.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import threading
from datetime import datetime
from pathlib import Path

from extract import Document, extract_file
from search import ContractSearcher, Hit, chunk_document

FORMATOS = {".pdf", ".docx", ".txt", ".md"}
MAX_BYTES = 80 * 1024 * 1024
# Abaixo disto por página, mesmo depois do OCR, o PDF não tem o que ensinar:
# dizer que "aprendeu" seria mentir.
MIN_CARACTERES_POR_PAGINA = 40
# Quanto do material entra em cada pergunta, no máximo. A janela do modelo é
# disputada com os documentos do Acervo.
ORCAMENTO = 2400
# Um trecho só entra se tiver ao menos esta fração das palavras da pergunta.
# Material é referência: trecho que mal toca a pergunta é ruído - e ruído que
# um modelo de 3B lê como resposta ("entre 20% e 30%" da tabela, perguntado o
# êxito do contrato de um cliente).
MIN_COBERTURA = 0.45
# E só entra quem chega perto do melhor trecho: a página 2 com nota 2,9 e a
# página 4 com 0,4 não são igualmente sobre a pergunta.
MIN_DA_MELHOR = 0.35

RE_PAGINA = re.compile(r"\[pagina (\d+)\]")

# O jeito de perguntar, e não o assunto: fica fora da conta da cobertura.
# "Em quanto tempo devemos responder o e-mail" tem três palavras de assunto;
# contando "quanto" e "devemos", o trecho certo cobria só um terço e ficava
# de fora. Já passadas pelo tokenize (sem acento, no singular).
PALAVRAS_DE_PERGUNTA = {
    "quanto", "quanta", "qual", "quando", "onde", "como", "quem", "devo", "devemo", "deve", "posso",
    "podemo", "pode", "preciso", "precisamo", "precisa", "tenho", "temo", "fazer", "faco", "fazemo",
    "existe", "ha", "sobre", "diz", "dizer", "esta", "dentro",
}


def _agora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _slug(nome: str) -> str:
    base = re.sub(r"[^\w.-]+", "-", Path(nome).stem, flags=re.UNICODE).strip("-")[:60]
    return base or "material"


def paginas_do_texto(texto: str) -> list[tuple[int | None, str]]:
    """
    O texto separado pelas marcas [pagina N] que a leitura do PDF deixa.
    DOCX, TXT e MD nao tem pagina: volta um pedaco so, sem numero.
    """
    partes = RE_PAGINA.split(texto)
    if len(partes) == 1:
        return [(None, texto)]
    saida = [(None, partes[0])] if partes[0].strip() else []
    for i in range(1, len(partes) - 1, 2):
        saida.append((int(partes[i]), partes[i + 1]))
    return saida


class Material:
    def __init__(self, pasta: Path, *, hibrida=False, vetorizador=None, ceder=None, chaves=None) -> None:
        self.pasta = Path(pasta)
        self.arquivos = self.pasta / "arquivos"
        self.textos = self.pasta / "textos"
        self.indice_path = self.pasta / "indice.json"
        self._trava = threading.Lock()
        self.itens: list[dict] = []
        self.buscador = ContractSearcher()
        # (material, trecho) -> pagina. Cada trecho nasce dentro de uma pagina:
        # cortado por cima delas, a citacao dizia a pagina onde o trecho
        # comecava, e nao a pagina onde estava a resposta.
        self._pagina_de: dict[tuple[str, int], int | None] = {}
        # A Biblioteca, M1 (src/biblioteca/indice.py): o material no pipeline
        # hibrido do Acervo - trechos pela estrutura, FTS5 e vetores, em
        # indices proprios. Chave `biblioteca.hibrida`; `hibrida` pode ser uma
        # funcao, para a chave valer na hora em que muda.
        self._hibrida = hibrida if callable(hibrida) else (lambda: bool(hibrida))
        self._vetorizador = vetorizador
        self._ceder = ceder
        # As outras chaves do bloco `biblioteca` (anotacoes, leitura...): uma
        # funcao que devolve o dicionario delas, lido na hora.
        self._chaves = chaves if callable(chaves) else (lambda: dict(chaves or {}))
        self._anotacoes = None
        # M5: quem da o cliente do modelo da tarefa `leitura` (o api.py poe).
        self.cliente_leitura = None
        self._leitura = None
        self.indice = None
        self._indice_versao = -1
        self._versao = 0
        self._carregar()

    # ------------------------------------------------------------ guarda

    def _carregar(self) -> None:
        try:
            self.itens = json.loads(self.indice_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.itens = []
        self._montar()

    def _salvar(self) -> None:
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.indice_path.write_text(json.dumps(self.itens, ensure_ascii=False, indent=1), encoding="utf-8")

    def _montar(self) -> None:
        """O índice de busca, refeito do texto guardado de cada material."""
        buscador = ContractSearcher()
        paginas_de: dict[tuple[str, int], int | None] = {}
        for item in self.itens:
            try:
                texto = (self.textos / f"{item['id']}.txt").read_text(encoding="utf-8")
            except OSError:
                continue
            buscador.documents.append(Document(name=item["nome"], path=item["arquivo"], text=texto))
            n = 0
            for pagina, pedaco in paginas_do_texto(texto):
                for trecho in chunk_document(Document(name=item["nome"], path=item["arquivo"], text=pedaco)):
                    trecho.index = n
                    paginas_de[(item["nome"], n)] = pagina
                    buscador.chunks.append(trecho)
                    n += 1
        buscador.build()
        self.buscador = buscador
        self._pagina_de = paginas_de
        por_nome: dict[str, int] = {}
        for c in buscador.chunks:
            por_nome[c.doc_name] = por_nome.get(c.doc_name, 0) + 1
        for item in self.itens:
            item["trechos"] = por_nome.get(item["nome"], 0)
        self._versao += 1
        if self.hibrida:
            self._montar_hibrido()

    @property
    def hibrida(self) -> bool:
        try:
            return bool(self._hibrida())
        except Exception:  # noqa: BLE001 - preferencia ilegivel: o de sempre
            return False

    def _montar_hibrido(self):
        """O indice hibrido (src/biblioteca/indice.py), refeito quando o material mudou."""
        if self.indice is not None and self._indice_versao == self._versao:
            return self.indice
        from biblioteca.indice import IndiceDoMaterial

        if self.indice is None:
            self.indice = IndiceDoMaterial(self.pasta, vetorizador=self._vetorizador, ceder=self._ceder)
        pares = []
        for item in self.itens:
            try:
                pares.append((item, (self.textos / f"{item['id']}.txt").read_text(encoding="utf-8")))
            except OSError:
                continue
        por_material = self.indice.montar(pares)
        for item in self.itens:
            item["trechos"] = por_material.get(item["id"], 0)
        self._indice_versao = self._versao
        if self.chave("anotacoes"):
            # M3: cada artigo citado com instrumento vira anotacao (src/biblioteca/anotacoes.py).
            por_nome: dict[str, list] = {}
            for c in self.indice.searcher.chunks:
                por_nome.setdefault(c.doc_name, []).append(c)
            self.anotacoes.sincronizar([(item, texto, por_nome.get(item["nome"], [])) for item, texto in pares])
        return self.indice

    def chave(self, nome: str) -> bool:
        try:
            return bool((self._chaves() or {}).get(nome))
        except Exception:  # noqa: BLE001 - preferencia ilegivel: desligada
            return False

    @property
    def anotacoes(self):
        """O Codigo anotado pela biblioteca (M3), em <pasta>/biblioteca.db."""
        if self._anotacoes is None:
            from biblioteca.anotacoes import Anotacoes

            self._anotacoes = Anotacoes(self.pasta / "biblioteca.db")
        return self._anotacoes

    def item_por_nome(self, nome: str) -> dict | None:
        return next((x for x in self.itens if x["nome"] == nome), None)

    def item(self, id_: str) -> dict | None:
        return next((x for x in self.itens if x["id"] == id_), None)

    def listas_do_dispositivo(self, pergunta: str) -> list[list[str]]:
        """
        M3: a pergunta cita um artigo com o instrumento ("o art. 18 do CDC"):
        os trechos que o comentam viram uma terceira lista da RRF. A fusao
        continua por posicao, sem peso manual.
        """
        if not self.chave("anotacoes") and not self.chave("leitura"):
            return []
        from biblioteca.anotacoes import ordem_do_artigo
        from inteligencia.extratores import regras_leis

        ids: list[str] = []
        for achado in regras_leis.achar(pergunta) if self.chave("anotacoes") else []:
            d = achado["dados"]
            if d.get("kind") == "article" and d.get("instrument_id"):
                ids += self.anotacoes.chunks_do_dispositivo(d["instrument_id"], ordem_do_artigo(d.get("article", "")))
        listas = [list(dict.fromkeys(ids))] if ids else []
        # M5: o termo que a obra define esta na pergunta -> o trecho que o define.
        if self.chave("leitura"):
            termos = self.leitura.chunks_do_termo(pergunta)
            if termos:
                listas.append(termos)
        return listas

    @property
    def leitura(self):
        """A leitura das obras pelo modelo (M5, src/biblioteca/leitura.py)."""
        if self._leitura is None:
            from biblioteca.leitura import Leitura

            self._leitura = Leitura(self, cliente=lambda: self.cliente_leitura() if self.cliente_leitura else None,
                                    ceder=self._ceder)
        return self._leitura

    def fechar(self) -> None:
        if self._anotacoes is not None:
            self._anotacoes.fechar()
            self._anotacoes = None
        if self.indice is not None:
            self.indice.fechar()
            self.indice = None
            self._indice_versao = -1

    def preparar(self, esperar: bool = False) -> dict:
        """Com a chave ligada: o indice montado e os vetores que faltam andando (esperar=True espera)."""
        if not self.hibrida:
            return {"hibrida": False, "trechos": len(self.buscador.chunks)}
        indice = self._montar_hibrido()
        indice.sentido(esperar=esperar)
        leitura = self.leitura.iniciar() if self.chave("leitura") else {}
        return {"hibrida": True, **indice.estado(), "leitura": leitura}

    # ------------------------------------------------------------ público

    def listar(self) -> list[dict]:
        return sorted(self.itens, key=lambda x: x.get("criado_em", ""), reverse=True)

    def absorver(self, nome_original: str, conteudo: bytes) -> dict:
        """
        Guarda o arquivo, lê o texto com a página de cada trecho e o põe no
        índice. O mesmo arquivo (mesmo conteúdo) não entra duas vezes.
        """
        nome_original = Path(nome_original or "material").name
        ext = Path(nome_original).suffix.lower()
        if ext not in FORMATOS:
            raise ValueError("esse formato não dá para ler: use PDF, DOCX, TXT ou MD")
        if not conteudo:
            raise ValueError("o arquivo está vazio")
        if len(conteudo) > MAX_BYTES:
            raise ValueError(f"o arquivo passa de {MAX_BYTES // (1024 * 1024)} MB")
        sha1 = hashlib.sha1(conteudo).hexdigest()
        ja = next((x for x in self.itens if x.get("sha1") == sha1), None)
        if ja:
            return {**ja, "ja_existia": True}

        id_ = f"{datetime.now():%Y%m%d%H%M%S}-{sha1[:8]}"
        self.arquivos.mkdir(parents=True, exist_ok=True)
        self.textos.mkdir(parents=True, exist_ok=True)
        destino = self.arquivos / f"{id_}-{_slug(nome_original)}{ext}"
        destino.write_bytes(conteudo)
        try:
            texto, paginas = extract_file(destino)
        except Exception as exc:  # noqa: BLE001 - arquivo quebrado ou protegido
            destino.unlink(missing_ok=True)
            raise ValueError("não consegui ler o arquivo: " + str(exc)[:160]) from exc
        util = RE_PAGINA.sub("", texto).strip()
        if ext == ".pdf" and paginas and len(util) < MIN_CARACTERES_POR_PAGINA * paginas:
            # A leitura já passou as páginas de imagem pelo OCR (src/ocr_windows.py):
            # sobrar tão pouco é página em branco, foto sem letras ou OCR
            # indisponível - e o motivo diz qual.
            from extract import motivo_sem_texto

            motivo = motivo_sem_texto(destino) if not util else "quase nada de texto nas páginas, mesmo lendo a imagem"
            destino.unlink(missing_ok=True)
            raise ValueError("não deu para aprender com esse PDF: " + (motivo or "sem texto"))
        if not util:
            destino.unlink(missing_ok=True)
            raise ValueError("não achei texto nesse arquivo")
        (self.textos / f"{id_}.txt").write_text(texto, encoding="utf-8")

        nome = nome_original
        nomes = {x["nome"] for x in self.itens}
        n = 2
        while nome in nomes:  # nomes iguais confundiriam a citação
            nome = f"{Path(nome_original).stem} ({n}){ext}"
            n += 1
        item = {"id": id_, "nome": nome, "arquivo": str(destino), "sha1": sha1, "paginas": paginas or 0,
                "caracteres": len(util), "criado_em": _agora()}
        with self._trava:
            self.itens.append(item)
            self._salvar()
            self._montar()
        return next(x for x in self.itens if x["id"] == id_)

    def remover(self, id_: str) -> bool:
        with self._trava:
            item = next((x for x in self.itens if x["id"] == id_), None)
            if not item:
                return False
            self.itens.remove(item)
            if item.get("arquivo"):  # o que veio de pacote nao tem arquivo original
                Path(item["arquivo"]).unlink(missing_ok=True)
            (self.textos / f"{id_}.txt").unlink(missing_ok=True)
            # As anotacoes dele (M3) saem junto, mesmo com a chave desligada agora.
            if self._anotacoes is not None or (self.pasta / "biblioteca.db").exists():
                self.anotacoes.remover_material(id_)
            self.leitura.remover(id_)
            self._salvar()
            self._montar()
        return True

    def absorver_texto(self, nome: str, texto: str, ficha: dict, *, id_de_origem: str = "", sha1: str = "") -> dict:
        """
        Um material que chega como texto, sem o arquivo original: o pacote
        .paulus-material (src/biblioteca/pacote.py). O mesmo texto nao entra
        duas vezes; `id_de_origem` e `sha1` sao os do PAULUS de onde veio - e
        o que faz os trechos terem os mesmos ids la e aqui.
        """
        texto = texto or ""
        if not RE_PAGINA.sub("", texto).strip():
            raise ValueError("o pacote não tem texto")
        chave = hashlib.sha1(texto.encode("utf-8")).hexdigest()
        ja = next((x for x in self.itens if x.get("sha1_texto") == chave), None)
        if ja:
            return {**ja, "ja_existia": True}
        id_ = f"{datetime.now():%Y%m%d%H%M%S}-{chave[:8]}"
        self.textos.mkdir(parents=True, exist_ok=True)
        (self.textos / f"{id_}.txt").write_text(texto, encoding="utf-8")
        nomes = {x["nome"] for x in self.itens}
        base, n = nome, 2
        while nome in nomes:
            nome = f"{base} ({n})"
            n += 1
        item = {"id": id_, "nome": nome, "arquivo": "", "sha1": sha1 or chave, "sha1_texto": chave,
                "id_de_origem": id_de_origem or id_, "paginas": len(RE_PAGINA.findall(texto)),
                "caracteres": len(RE_PAGINA.sub("", texto).strip()), "criado_em": _agora(), "ficha": ficha}
        with self._trava:
            self.itens.append(item)
            self._salvar()
            self._montar()
        return next(x for x in self.itens if x["id"] == id_)

    def texto_de(self, id_: str) -> str:
        try:
            return (self.textos / f"{id_}.txt").read_text(encoding="utf-8")
        except OSError:
            return ""

    def definir_ficha(self, id_: str, ficha: dict) -> dict:
        """
        A ficha da Biblioteca (src/biblioteca/ficha.py) - tipo, autor, obra,
        ano. Mudar o tipo muda o corte (doutrina por capitulo, manual por
        pagina), e o indice se refaz.
        """
        with self._trava:
            item = next((x for x in self.itens if x["id"] == id_), None)
            if item is None:
                raise KeyError(id_)
            item["ficha"] = ficha
            self._salvar()
            self._montar()
        return next(x for x in self.itens if x["id"] == id_)

    def editar_ficha(self, id_: str, mudancas: dict) -> dict:
        from biblioteca import ficha as ficha_mod

        item = next((x for x in self.itens if x["id"] == id_), None)
        if item is None:
            raise KeyError(id_)
        return self.definir_ficha(id_, ficha_mod.editar(item.get("ficha") or ficha_mod.vazia(), mudancas))

    def caminho(self, id_: str) -> Path | None:
        item = next((x for x in self.itens if x["id"] == id_), None)
        return Path(item["arquivo"]) if item and item.get("arquivo") and Path(item["arquivo"]).exists() else None

    def consultar(self, pergunta: str, top: int = 4) -> list[Hit]:
        """
        Os trechos do material que têm a ver com a pergunta. Só entram os que
        cobrem parte boa das palavras dela: material é referência, e trecho
        que mal toca a pergunta só ocupa a janela do modelo.

        Com `biblioteca.hibrida`, a busca é a do Acervo - léxico e sentido,
        fundidos por RRF - no índice próprio do material
        (src/biblioteca/indice.py), com a mesma regra dos nomes e o mesmo
        corte relativo.
        """
        if self.hibrida:
            indice = self._montar_hibrido()
            return indice.consultar(pergunta, top=top, extras=self.listas_do_dispositivo(pergunta))
        if not self.buscador.chunks:
            return []
        from search import tokenize

        # Nome próprio não casa: o material é de regras, não de partes. Mas
        # conta no total - pergunta com nome de cliente é, quase sempre, sobre
        # o documento dele. Sem isso, "quais poderes a procuração dá à Dra.
        # Helena?" trazia a página do manual que diz que a Dra. Helena revisa
        # as contestações.
        palavras = pergunta.split()
        nomes = set(tokenize(" ".join(p for i, p in enumerate(palavras) if i and p[:1].isupper())))
        procurados = set(tokenize(pergunta)) - PALAVRAS_DE_PERGUNTA
        if not procurados - nomes:
            return []
        hits = self.buscador.search(pergunta, top_k=top, per_doc_limit=3)
        melhor = max((h.score for h in hits), default=0.0)
        bons = []
        for h in hits:
            if h.score < MIN_DA_MELHOR * melhor:
                continue
            termos = set(tokenize(h.chunk.text))
            radicais = {t[:6] for t in termos if len(t) >= 6}
            achados = [p for p in procurados - nomes if p in termos or (len(p) >= 6 and p[:6] in radicais)]
            # Uma palavra em comum é coincidência ("contrato" está em meio
            # manual): com pergunta de duas ou mais, pede pelo menos duas.
            if len(achados) / len(procurados) >= MIN_COBERTURA and len(achados) >= min(2, len(procurados - nomes)):
                bons.append(h)
        return bons

    def pagina(self, hit: Hit) -> int | None:
        if hit.chunk.chunk_id:  # trecho do indice hibrido: ele sabe a pagina
            return hit.chunk.pagina_inicio
        return self._pagina_de.get((hit.doc_name, hit.chunk.index))

    def onde(self, hit: Hit) -> str:
        """'página 3', ou 'páginas 3–4' para o trecho da obra que atravessa a página."""
        if hit.chunk.chunk_id:
            from biblioteca.indice import onde

            return onde(hit.chunk)
        pagina = self.pagina(hit)
        return f"página {pagina}" if pagina else ""

    def bloco(self, hits: list[Hit], orcamento: int = ORCAMENTO) -> str:
        """O material que vai para o modelo, com nome e página de cada trecho."""
        partes, usado = [], 0
        for h in hits:
            lugar = self.onde(h)
            cabeca = f"[Material: {h.doc_name}" + (f", {lugar}" if lugar else "") + "]"
            texto = RE_PAGINA.sub("", h.chunk.text).strip()
            pedaco = cabeca + "\n" + texto
            if usado + len(pedaco) > orcamento:
                sobra = orcamento - usado - len(cabeca) - 1
                if sobra < 200:
                    break
                pedaco = cabeca + "\n" + texto[:sobra] + "…"
            partes.append(pedaco)
            usado += len(pedaco)
        return "\n\n".join(partes)

    def para_tela(self) -> dict:
        trechos = len(self.indice.searcher.chunks) if self.hibrida and self.indice is not None \
            else len(self.buscador.chunks)
        return {"itens": self.listar(), "trechos": trechos, "formatos": sorted(FORMATOS)}

    def apagar_tudo(self) -> None:
        """Só para teste: some com a pasta."""
        shutil.rmtree(self.pasta, ignore_errors=True)
        self.itens = []
        self._montar()
