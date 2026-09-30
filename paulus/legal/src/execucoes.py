"""
PAULUS - Execucoes: a chamada de IA que roda sem depender da janela.

Antes (30/09/2026), a resposta da conversa era um gerador preso a conexao
HTTP: fechar ou recarregar a janela fechava o gerador, a conversa ficava
"parada" e o texto que ja tinha saido se perdia. Aqui a resposta roda numa
thread de trabalho e cada evento (etapa, fontes, pedaco de texto, fim) entra,
na hora, num registro so acrescentado - na memoria e em
`data/execucoes/<id>.jsonl`. A tela se INSCREVE nesse registro a partir de um
numero de sequencia: ao voltar para a conversa ou recarregar, recebe o que
perdeu e continua ao vivo. Fechar a janela encerra so a inscricao.

Parar continua sendo so pelo botao (o sinal de sempre, em estado.respondendo)
ou pelo encerramento do programa; nesse caso, ao abrir de novo,
`recuperar_interrompidas` poe na conversa o texto parcial, marcado como
interrompido.

Chave: `conversa.execucao`.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# O evento que encerra uma execucao, e o estado que ele deixa.
TERMINAIS = {"fim": "concluida", "vazio": "concluida", "parado": "parada", "erro": "falhou",
             "interrompida": "interrompida"}
# Registro com mais de 30 dias vira resumo: o texto final ja esta na conversa.
DIAS_DE_REGISTRO = 30


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def do_sse(texto: str) -> tuple[str, dict]:
    """O contrario de api._sse: 'event: x\\ndata: {...}' -> ('x', {...})."""
    tipo, dados = "", {}
    for linha in texto.splitlines():
        if linha.startswith("event:"):
            tipo = linha[6:].strip()
        elif linha.startswith("data:"):
            try:
                dados = json.loads(linha[5:].strip() or "{}")
            except json.JSONDecodeError:
                dados = {}
    return tipo, dados


def sse(evento: dict) -> str:
    """Um evento do registro no formato do navegador, com a sequencia e os ids junto."""
    dados = dict(evento["dados"])
    dados.update(seq=evento["seq"], execucao_id=evento["execucao_id"], conversa_id=evento["conversa_id"])
    return f"event: {evento['tipo']}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"


class Execucao:
    def __init__(self, pasta: Path, id_: str, conversa_id: str = "", dono: str = "", tipo: str = "conversa") -> None:
        self.pasta = pasta
        self.id = id_
        self.conversa_id = conversa_id
        self.dono = dono
        self.tipo = tipo
        self.estado = "rodando"
        self.criada = _agora()
        self.eventos: list[dict] = []
        self._cond = threading.Condition()

    @property
    def arquivo(self) -> Path:
        return self.pasta / f"{self.id}.jsonl"

    @property
    def terminou(self) -> bool:
        return self.estado != "rodando"

    def acrescentar(self, tipo: str, dados: dict | None = None) -> dict:
        with self._cond:
            evento = {"seq": len(self.eventos) + 1, "em": _agora(), "tipo": tipo, "dados": dados or {},
                      "execucao_id": self.id, "conversa_id": self.conversa_id}
            self.eventos.append(evento)
            # Uma linha por evento, gravada na hora: e o que sobra se o
            # programa fechar no meio.
            with self.arquivo.open("a", encoding="utf-8") as f:
                f.write(json.dumps(evento, ensure_ascii=False) + "\n")
            if tipo in TERMINAIS and self.estado == "rodando":
                self.estado = TERMINAIS[tipo]
            self._cond.notify_all()
            return evento

    def encerrar(self, estado: str) -> None:
        with self._cond:
            if self.estado == "rodando":
                self.estado = estado
            self._cond.notify_all()

    def desde(self, n: int) -> list[dict]:
        with self._cond:
            return self.eventos[max(0, int(n)):]

    def esperar(self, n: int, timeout: float) -> bool:
        """Espera haver evento depois de `n` (ou o fim). Verdadeiro se ha o que entregar."""
        with self._cond:
            if len(self.eventos) > n or self.terminou:
                return True
            self._cond.wait(timeout)
            return len(self.eventos) > n

    def texto_parcial(self) -> str:
        """O que o modelo ja escreveu: o texto conferido, quando houve, e o que chegou depois dele."""
        return texto_dos_eventos(self.desde(0))

    def resumo(self) -> dict:
        return {"id": self.id, "conversa_id": self.conversa_id, "tipo": self.tipo, "estado": self.estado,
                "criada": self.criada, "eventos": len(self.eventos)}


def texto_dos_eventos(eventos: list[dict]) -> str:
    texto, depois = "", []
    for e in eventos:
        if e["tipo"] == "revisao":
            texto, depois = e["dados"].get("texto", ""), []
        elif e["tipo"] == "token":
            depois.append(e["dados"].get("t", ""))
    return (texto + "".join(depois)).strip()


class Execucoes:
    def __init__(self, pasta: Path) -> None:
        self.pasta = Path(pasta)
        self.pasta.mkdir(parents=True, exist_ok=True)
        self._itens: dict[str, Execucao] = {}
        self._trava = threading.Lock()

    def criar(self, conversa_id: str = "", dono: str = "", tipo: str = "conversa") -> Execucao:
        e = Execucao(self.pasta, uuid.uuid4().hex[:16], conversa_id, dono, tipo)
        with self._trava:
            self._itens[e.id] = e
        return e

    def obter(self, id_: str) -> Execucao | None:
        return self._itens.get(id_)

    def da_conversa(self, conversa_id: str) -> Execucao | None:
        """A execucao desta conversa que ainda roda (ou a ultima, se nenhuma roda)."""
        delas = [e for e in list(self._itens.values()) if e.conversa_id == conversa_id]
        rodando = [e for e in delas if not e.terminou]
        return (rodando or delas or [None])[-1]

    def rodar(self, execucao: Execucao, eventos, ao_terminar=None) -> threading.Thread:
        """
        Consome `eventos` (um iterador de strings SSE ou de pares (tipo, dados))
        numa thread de trabalho, gravando cada um no registro. A thread nao
        depende de ninguem estar inscrito.
        """
        def trabalhar() -> None:
            try:
                for item in eventos:
                    tipo, dados = do_sse(item) if isinstance(item, str) else item
                    if tipo:
                        execucao.acrescentar(tipo, dados)
            except Exception as exc:  # noqa: BLE001 - o erro vai para o registro, e dali para a tela
                execucao.acrescentar("erro", {"mensagem": str(exc)[:300]})
            finally:
                # O gerador acabou sem evento de fim (a resposta rapida que so
                # manda "proposta", por exemplo): a execucao termina assim mesmo.
                if not execucao.terminou:
                    execucao.acrescentar("fim", {"sem_evento": True})
                if ao_terminar:
                    try:
                        ao_terminar(execucao)
                    except Exception:  # noqa: BLE001
                        pass

        t = threading.Thread(target=trabalhar, name=f"execucao-{execucao.id}", daemon=True)
        t.start()
        return t

    def inscrever(self, execucao: Execucao, desde: int = 0, parar=None):
        """
        Os eventos depois de `desde`, em SSE, e depois os que chegarem, ate o
        fim da execucao. `parar()` verdadeiro encerra so a inscricao.
        """
        n = max(0, int(desde))
        while True:
            for evento in execucao.desde(n):
                n = evento["seq"]
                yield sse(evento)
            if execucao.terminou and not execucao.desde(n):
                return
            if parar is not None and parar():
                return
            execucao.esperar(n, timeout=0.5)

    # ------------------------------------------------ o que ficou no disco

    def ler_registro(self, arquivo: Path) -> list[dict]:
        eventos = []
        try:
            for linha in arquivo.read_text(encoding="utf-8").splitlines():
                if linha.strip():
                    try:
                        eventos.append(json.loads(linha))
                    except json.JSONDecodeError:
                        break   # a ultima linha, cortada no meio pelo desligamento
        except OSError:
            pass
        return eventos

    def interrompidas(self) -> list[tuple[Path, list[dict]]]:
        """Os registros em disco sem evento de fim: o programa fechou no meio."""
        achadas = []
        for arquivo in sorted(self.pasta.glob("*.jsonl")):
            if arquivo.stem in self._itens:
                continue
            eventos = self.ler_registro(arquivo)
            if eventos and not any(e.get("tipo") in TERMINAIS for e in eventos):
                achadas.append((arquivo, eventos))
        return achadas

    def recuperar_interrompidas(self, trabalhos, pausar) -> int:
        """
        Ao abrir o programa: cada resposta que ficou pela metade entra na
        conversa como texto parcial, marcado como interrompido, e o registro
        ganha o evento "interrompida" (para nao ser recuperado de novo).
        `pausar(trabalho)` devolve as etapas e a conversa a "parado".
        """
        feitas = 0
        for arquivo, eventos in self.interrompidas():
            conversa_id = eventos[0].get("conversa_id", "")
            trabalho = trabalhos.obter(conversa_id) if conversa_id else None
            texto = texto_dos_eventos(eventos)
            if trabalho is not None:
                ultima = trabalho.mensagens[-1] if trabalho.mensagens else None
                # A resposta ja tinha sido gravada inteira e o programa fechou
                # antes do evento de fim: nada a acrescentar.
                ja_gravada = ultima is not None and ultima.autor == "paulus" and ultima.em >= eventos[0].get("em", "")
                if texto and not ja_gravada:
                    fontes = next((e["dados"].get("trechos") or [] for e in reversed(eventos) if e["tipo"] == "fontes"), [])
                    trabalho.dizer("paulus", texto, fontes=fontes, interrompida=True)
                pausar(trabalho)
                trabalhos.salvar(trabalho)
            with arquivo.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"seq": len(eventos) + 1, "em": _agora(), "tipo": "interrompida",
                                    "dados": {"texto": bool(texto)}, "execucao_id": arquivo.stem,
                                    "conversa_id": conversa_id}, ensure_ascii=False) + "\n")
            feitas += 1
        return feitas

    def compactar(self, dias: int = DIAS_DE_REGISTRO) -> int:
        """Registro com mais de `dias`: fica o resumo (etapas, tempos, contagens), sem o texto."""
        limite = time.time() - timedelta(days=dias).total_seconds()
        feitos = 0
        for arquivo in self.pasta.glob("*.jsonl"):
            try:
                if arquivo.stat().st_mtime > limite:
                    continue
            except OSError:
                continue
            eventos = self.ler_registro(arquivo)
            if not eventos:
                arquivo.unlink(missing_ok=True)
                continue
            por_tipo: dict[str, int] = {}
            for e in eventos:
                por_tipo[e["tipo"]] = por_tipo.get(e["tipo"], 0) + 1
            resumo = {
                "id": arquivo.stem, "conversa_id": eventos[0].get("conversa_id", ""),
                "de": eventos[0].get("em"), "ate": eventos[-1].get("em"), "eventos": por_tipo,
                "etapas": next((e["dados"].get("etapas") for e in reversed(eventos) if e["tipo"] == "etapas"), []),
                "medida": next((e["dados"] for e in reversed(eventos) if e["tipo"] == "medida"), {}),
                "fim": next((e["dados"] for e in reversed(eventos) if e["tipo"] in TERMINAIS), {}),
            }
            arquivo.with_suffix(".resumo.json").write_text(json.dumps(resumo, ensure_ascii=False), encoding="utf-8")
            arquivo.unlink(missing_ok=True)
            feitos += 1
        return feitos
