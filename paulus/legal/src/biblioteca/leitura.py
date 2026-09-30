"""
A leitura da obra em segundo plano: conceitos e posições (M5).

Depois de indexar, o modelo da tarefa `leitura` (src/modelos.py) lê cada
trecho de cada obra de consulta - um trecho do regime C nunca atravessa
capítulo - e devolve, por JSON Schema (o `format` do Ollama):

- `conceitos`: os termos que a obra DEFINE, com a frase que define;
- `posicoes`: o que o autor SUSTENTA, com a frase e os artigos citados.

**Toda `quote` passa por src/inteligencia/alinhar.py.** A que não casa com o
texto do trecho é descartada: não fica guardada como "inferida" e não aparece
em lugar nenhum. O modelo propõe; a frase do livro prova.

Onde isto aparece:

- na tela do material: o **glossário** (conceitos com página) e as **teses do
  autor** (posições com página);
- na busca: cada termo vira uma entrada a mais que aponta para o trecho da
  frase - expansão determinística, o sinônimo está escrito na obra;
- na tela da lei (M3): a tese cujo artigo é o da tela aparece em destaque.

Não é o modo de "treinar": o modelo lê, o programa guarda o que o texto
confirma, e o que o PAULUS diz depois continua citando a obra e a página.

Guardado por material, em `<material>/leituras/<id>.json`, com o extrator, o
modelo, o digest e a versão do prompt, como `analysis.sections` do
legal-document/v0. Trocar o modelo marca a leitura como `stale`, e ela é
refeita. Interromper e reabrir continua do trecho em que parou: cada trecho
lido é gravado na hora.
"""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path

EXTRATOR = "leitura-biblioteca/v1"
PROMPT_VERSAO = "1"
TIPOS_LIDOS = ("doutrina", "artigo")

SCHEMA = {
    "type": "object",
    "properties": {
        "conceitos": {"type": "array", "items": {
            "type": "object", "properties": {"termo": {"type": "string"}, "quote": {"type": "string"}},
            "required": ["termo", "quote"]}},
        "posicoes": {"type": "array", "items": {
            "type": "object", "properties": {"afirmacao": {"type": "string"}, "quote": {"type": "string"},
                                             "dispositivos": {"type": "array", "items": {"type": "string"}}},
            "required": ["afirmacao", "quote"]}},
    },
    "required": ["conceitos", "posicoes"],
}

SISTEMA = ("Você lê trechos de livros jurídicos brasileiros e devolve só o que está escrito neles, em JSON. "
           "Nunca invente conceito, posição, frase ou artigo.")
INSTRUCAO = (
    "Trecho de uma obra jurídica:\n\n{trecho}\n\n"
    "Liste em JSON:\n"
    "- conceitos: cada termo que o trecho DEFINE (o que é), com a frase do trecho que define, copiada exatamente;\n"
    "- posicoes: cada coisa que o autor SUSTENTA, com um resumo curto (afirmacao), a frase do trecho copiada "
    "exatamente (quote) e os artigos de lei citados nela (dispositivos, como \"art. 18 do CDC\").\n"
    "Se não houver, devolva a lista vazia. Não resuma o capítulo; não acrescente o que não está no trecho."
)


def _plano(texto: str) -> str:
    import unicodedata

    normal = unicodedata.normalize("NFD", (texto or "").lower())
    return " ".join("".join(c for c in normal if unicodedata.category(c) != "Mn").split())


class Leitura:
    """
    A leitura de todas as obras do material. `cliente` devolve o cliente do
    modelo da tarefa `leitura` (ou None, sem Ollama); `ceder` espera a fila
    do modelo esvaziar antes de cada trecho.
    """

    def __init__(self, material, *, cliente=None, ceder=None) -> None:
        self.material = material
        self.pasta = Path(material.pasta) / "leituras"
        self._cliente = cliente
        self._ceder = ceder or (lambda: None)
        self._fio: threading.Thread | None = None
        self._parar = threading.Event()
        self._trava = threading.Lock()
        self.estado: dict = {"andando": False, "feitos": 0, "total": 0, "erro": ""}

    # ------------------------------------------------------------ guarda

    def _caminho(self, material_id: str) -> Path:
        return self.pasta / f"{material_id}.json"

    def carregar(self, material_id: str) -> dict:
        try:
            return json.loads(self._caminho(material_id).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _gravar(self, material_id: str, dados: dict) -> None:
        self.pasta.mkdir(parents=True, exist_ok=True)
        alvo = self._caminho(material_id)
        temporario = alvo.with_suffix(".tmp")
        temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
        temporario.replace(alvo)

    def remover(self, material_id: str) -> None:
        self._caminho(material_id).unlink(missing_ok=True)

    # ------------------------------------------------------------ ler

    def _trechos_a_ler(self) -> list[tuple[dict, list]]:
        indice = self.material._montar_hibrido()
        por_nome: dict[str, list] = {}
        for c in indice.searcher.chunks:
            por_nome.setdefault(c.doc_name, []).append(c)
        saida = []
        for item in self.material.itens:
            if (item.get("ficha") or {}).get("tipo") in TIPOS_LIDOS and por_nome.get(item["nome"]):
                saida.append((item, por_nome[item["nome"]]))
        return saida

    @staticmethod
    def _assinatura(cliente) -> dict:
        modelo = getattr(cliente, "model", "")
        try:
            digest = cliente.digest(modelo) if hasattr(cliente, "digest") else ""
        except Exception:  # noqa: BLE001 - sem o digest, o nome do modelo basta
            digest = ""
        return {"extrator": EXTRATOR, "modelo": modelo, "digest": digest, "prompt": PROMPT_VERSAO}

    def pendentes(self, cliente) -> list[tuple[dict, object]]:
        """(material, trecho) que falta ler - ou que foi lido por outro modelo (stale)."""
        assinatura = self._assinatura(cliente)
        saida = []
        for item, chunks in self._trechos_a_ler():
            dados = self.carregar(item["id"])
            antiga = {k: dados.get(k) for k in assinatura}
            if dados and antiga != assinatura:
                dados = {**dados, "estado": "stale"}
                self._gravar(item["id"], dados)
            lidos = dados.get("unidades", {}) if antiga == assinatura else {}
            saida += [(item, c) for c in chunks if c.chunk_id not in lidos]
        return saida

    def ler_trecho(self, cliente, chunk) -> dict:
        """Uma unidade: o modelo lê, e só fica o que a frase do trecho confirma."""
        from inteligencia import alinhar

        bruto = cliente._chat([{"role": "system", "content": SISTEMA},
                               {"role": "user", "content": INSTRUCAO.format(trecho=chunk.text)}],
                              fmt=SCHEMA, tarefa="json")
        try:
            dados = json.loads(bruto) if isinstance(bruto, str) else (bruto or {})
        except ValueError:
            dados = {}
        conceitos, posicoes, descartados = [], [], 0
        for c in dados.get("conceitos") or []:
            termo = " ".join(str(c.get("termo", "")).split())[:80]
            conf = alinhar.conferir(chunk.text, str(c.get("quote", "")))
            if termo and conf.achou:
                conceitos.append({"termo": termo, "quote": conf.trecho or c["quote"], "pagina": chunk.pagina_inicio})
            else:
                descartados += 1
        for p in dados.get("posicoes") or []:
            afirmacao = " ".join(str(p.get("afirmacao", "")).split())[:300]
            conf = alinhar.conferir(chunk.text, str(p.get("quote", "")))
            if afirmacao and conf.achou:
                from biblioteca.camadas import dispositivos_citados

                # Os artigos saem da frase conferida, por regra - não do que o modelo listou.
                posicoes.append({"afirmacao": afirmacao, "quote": conf.trecho or p["quote"],
                                 "dispositivos": [list(d) for d in dispositivos_citados(conf.trecho or p["quote"])],
                                 "pagina": chunk.pagina_inicio})
            else:
                descartados += 1
        return {"conceitos": conceitos, "posicoes": posicoes, "descartados": descartados,
                "lido_em": time.strftime("%Y-%m-%dT%H:%M:%S")}

    def iniciar(self, esperar: bool = False) -> dict:
        cliente = self._cliente() if self._cliente else None
        if cliente is None:
            return {**self.estado, "erro": "sem o modelo de leitura"}
        if self._fio and self._fio.is_alive():
            return self.estado
        faltam = self.pendentes(cliente)
        if not faltam:
            return self.estado
        self._parar.clear()
        self.estado = {"andando": True, "feitos": 0, "total": len(faltam), "erro": ""}
        self._fio = threading.Thread(target=self._rodar, args=(cliente, faltam), name="leitura-biblioteca",
                                     daemon=True)
        self._fio.start()
        if esperar:
            self._fio.join()
        return self.estado

    def parar(self) -> None:
        self._parar.set()
        if self._fio:
            self._fio.join(120)

    def _rodar(self, cliente, faltam) -> None:
        assinatura = self._assinatura(cliente)
        try:
            for item, chunk in faltam:
                if self._parar.is_set():
                    break
                self._ceder()
                unidade = self.ler_trecho(cliente, chunk)
                with self._trava:
                    dados = self.carregar(item["id"])
                    if {k: dados.get(k) for k in assinatura} != assinatura:
                        dados = {**assinatura, "unidades": {}}
                    dados.setdefault("unidades", {})[chunk.chunk_id] = unidade
                    total = len([c for c in self.material._montar_hibrido().searcher.chunks
                                 if c.doc_name == item["nome"]])
                    dados["estado"] = "completa" if len(dados["unidades"]) >= total else "parcial"
                    self._gravar(item["id"], dados)
                self.estado["feitos"] += 1
        except Exception as exc:  # noqa: BLE001 - a leitura para; a busca continua
            self.estado["erro"] = str(exc)[:200]
        finally:
            self.estado["andando"] = False

    # ------------------------------------------------------------ usar

    def de(self, material_id: str) -> dict:
        """Glossário e teses de uma obra, na ordem do livro, sem repetir."""
        dados = self.carregar(material_id)
        conceitos, posicoes, vistos = [], [], set()
        for cid, u in (dados.get("unidades") or {}).items():
            for c in u.get("conceitos") or []:
                if _plano(c["termo"]) not in vistos:
                    vistos.add(_plano(c["termo"]))
                    conceitos.append({**c, "chunk_id": cid})
            for p in u.get("posicoes") or []:
                posicoes.append({**p, "chunk_id": cid})
        conceitos.sort(key=lambda x: (x.get("pagina") or 0, x["termo"]))
        posicoes.sort(key=lambda x: x.get("pagina") or 0)
        return {"estado": dados.get("estado", ""), "modelo": dados.get("modelo", ""), "conceitos": conceitos,
                "posicoes": posicoes}

    def chunks_do_termo(self, pergunta: str) -> list[str]:
        """
        A expansão determinística da busca: o termo que a obra define está na
        pergunta -> o trecho onde a obra o define. O sinônimo está escrito na
        obra, e não inventado por modelo.
        """
        plano = " " + re.sub(r"[^\w\s-]", " ", _plano(pergunta)) + " "
        ids = []
        for item in self.material.itens:
            for c in self.de(item["id"])["conceitos"]:
                termo = _plano(c["termo"])
                if len(termo) >= 4 and f" {termo} " in plano:
                    ids.append(c["chunk_id"])
        return list(dict.fromkeys(ids))

    def teses_do_artigo(self, material_id: str, codigo: str, numero: str) -> list[dict]:
        from biblioteca.anotacoes import ordem_do_artigo

        alvo = ordem_do_artigo(str(numero).replace("º", ""))
        return [p for p in self.de(material_id)["posicoes"]
                if any(d[0] == codigo and ordem_do_artigo(str(d[1]).replace("º", "")) == alvo
                       for d in p.get("dispositivos") or [])]
