"""
PAULUS - Gravacoes.

O audio de reunioes, atendimentos, audiencias e notas de voz, guardado nesta
maquina (docs/ui/03-telas-desktop.md, A16). O que existe hoje: gravar pelo
microfone ou importar um arquivo, marcar momentos, anotar e ligar a um
cliente e a um servico. Transcrever por falante e resumir precisam de um
modelo de voz local que ainda nao esta aqui - e a tela diz isso em vez de
fingir uma transcricao.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from html import escape as _esc
from pathlib import Path

TIPOS = {
    "reuniao": "Reunião",
    "atendimento": "Atendimento",
    "audiencia": "Audiência",
    "nota": "Nota de voz",
}

# O que o navegador grava (webm/opus) e o que costuma vir de fora.
SUFIXOS = {".webm", ".ogg", ".opus", ".mp3", ".m4a", ".wav", ".aac", ".mp4", ".flac"}
MEDIA_TYPES = {
    ".webm": "audio/webm", ".ogg": "audio/ogg", ".opus": "audio/ogg", ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4", ".mp4": "audio/mp4", ".wav": "audio/wav", ".aac": "audio/aac", ".flac": "audio/flac",
}

CAMPOS = ("titulo", "tipo", "cadastro_id", "servico_id", "participantes", "notas", "duracao_s")

ESTADOS_TRANSCRICAO = {
    "": "sem transcrição",
    "fila": "na fila",
    "transcrevendo": "transcrevendo",
    "pronta": "transcrita",
    "erro": "erro na transcrição",
}

INSTRUCAO_RESUMO = """Você é assistente de um escritório de advocacia brasileiro. Abaixo está a
transcrição literal de uma gravação (reunião, atendimento, audiência ou nota
de voz), com o minuto de cada trecho. Escreva em português do Brasil, nesta
ordem e com estes títulos:

Resumo: um parágrafo curto dizendo do que se tratou e onde ficou.
Decisões: uma linha por decisão tomada. Se não houve, escreva "nenhuma".
Pendências: uma linha por coisa que ficou para fazer, dizendo quem e até
quando, se isso foi dito.

Use só o que está na transcrição; não invente nomes, valores nem datas. Se
algo não ficou claro, diga que não ficou claro."""

INSTRUCAO_JUNTAR = """Você é assistente de um escritório de advocacia brasileiro. Abaixo estão
resumos parciais, em ordem, de partes de uma mesma gravação. Junte-os num
único texto com os títulos Resumo, Decisões e Pendências, sem repetir e sem
inventar nada que não esteja neles."""


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def duracao_texto(segundos: int) -> str:
    s = max(0, int(segundos or 0))
    h, resto = divmod(s, 3600)
    m, s = divmod(resto, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class Gravacoes:
    def __init__(self, base, pasta: Path) -> None:
        self.base = base
        self.pasta = Path(pasta)

    # ---------------------------------------------------------------- leitura

    def listar(self, tipo: str = "", termo: str = "", completo: bool = False) -> list[dict]:
        sql = ("SELECT g.*, c.nome AS cliente_nome, s.nome AS servico_nome FROM gravacoes g "
               "LEFT JOIN cadastros c ON c.id = g.cadastro_id "
               "LEFT JOIN servicos s ON s.id = g.servico_id WHERE 1=1")
        parametros: list = []
        if tipo in TIPOS:
            sql += " AND g.tipo = ?"
            parametros.append(tipo)
        if termo:
            # Procurar "no que foi dito" e procurar na transcricao tambem.
            sql += (" AND (g.titulo LIKE ? OR g.participantes LIKE ? OR g.notas LIKE ? OR c.nome LIKE ? OR s.nome LIKE ?"
                    " OR g.transcricao LIKE ? OR g.resumo LIKE ?)")
            like = f"%{termo}%"
            parametros += [like] * 7
        sql += " ORDER BY g.criado_em DESC"
        itens = self.base.buscar(sql, tuple(parametros))
        for g in itens:
            self._enfeitar(g, completo)
        return itens

    def obter(self, id_: int) -> dict | None:
        g = self.base.um(
            "SELECT g.*, c.nome AS cliente_nome, s.nome AS servico_nome FROM gravacoes g "
            "LEFT JOIN cadastros c ON c.id = g.cadastro_id "
            "LEFT JOIN servicos s ON s.id = g.servico_id WHERE g.id = ?", (id_,))
        if g:
            self._enfeitar(g, True)
        return g

    def _enfeitar(self, g: dict, completo: bool = False) -> None:
        g["tipo_rotulo"] = TIPOS.get(g.get("tipo", ""), g.get("tipo", ""))
        g["duracao_texto"] = duracao_texto(g.get("duracao_s", 0))
        g["mb"] = round((g.get("bytes") or 0) / (1024 * 1024), 1)
        try:
            g["marcadores"] = json.loads(g.get("marcadores") or "[]")
        except json.JSONDecodeError:
            g["marcadores"] = []
        g["participantes_lista"] = [p.strip() for p in str(g.get("participantes") or "").split(",") if p.strip()]
        g["anotacoes"] = anotacoes_de(g.get("notas"), g.get("criado_em", ""))
        g["existe"] = bool(g.get("arquivo")) and (self.pasta / g["arquivo"]).exists()
        # A transcricao inteira so vai quando a gravacao esta aberta: uma
        # audiencia de hora e meia sao mil trechos, e a lista nao precisa.
        try:
            trechos = json.loads(g.pop("transcricao", "") or "[]")
        except json.JSONDecodeError:
            trechos = []
        g["trechos_quantos"] = len(trechos)
        g["palavras"] = sum(len(t.get("texto", "").split()) for t in trechos)
        g["transcricao_rotulo"] = ESTADOS_TRANSCRICAO.get(g.get("transcricao_estado", ""), "")
        if completo:
            g["trechos"] = trechos

    def total_segundos(self) -> int:
        linha = self.base.um("SELECT COALESCE(SUM(duracao_s), 0) AS s FROM gravacoes")
        return int(linha["s"]) if linha else 0

    def caminho(self, id_: int) -> Path | None:
        g = self.base.um("SELECT arquivo FROM gravacoes WHERE id = ?", (id_,))
        if not g or not g["arquivo"]:
            return None
        alvo = self.pasta / g["arquivo"]
        return alvo if alvo.exists() else None

    # ---------------------------------------------------------------- escrita

    def guardar(self, dados: dict, conteudo: bytes, nome_original: str) -> int:
        sufixo = Path(nome_original or "").suffix.lower() or ".webm"
        if sufixo not in SUFIXOS:
            raise ValueError("formato de áudio não reconhecido: " + sufixo)
        titulo = " ".join(str(dados.get("titulo", "")).split()) or ("Gravação de " + datetime.now().strftime("%d/%m %H:%M"))
        tipo = dados.get("tipo") if dados.get("tipo") in TIPOS else "reuniao"
        id_ = self.base.escrever(
            "INSERT INTO gravacoes (titulo, tipo, cadastro_id, servico_id, participantes, arquivo, duracao_s, bytes, "
            "origem, marcadores, notas, criado_em) VALUES (?, ?, ?, ?, ?, '', ?, ?, ?, ?, '', ?)",
            (titulo, tipo, dados.get("cadastro_id") or None, dados.get("servico_id") or None,
             str(dados.get("participantes", "")).strip(), int(dados.get("duracao_s") or 0), len(conteudo),
             dados.get("origem") if dados.get("origem") in ("gravada", "importada") else "gravada",
             json.dumps(dados.get("marcadores") or [], ensure_ascii=False), _agora()),
        )
        self.pasta.mkdir(parents=True, exist_ok=True)
        nome = f"gravacao-{id_:05d}{sufixo}"
        (self.pasta / nome).write_bytes(conteudo)
        self.base.escrever("UPDATE gravacoes SET arquivo = ? WHERE id = ?", (nome, id_))
        return id_

    def atualizar(self, id_: int, dados: dict) -> bool:
        atual = self.base.um("SELECT * FROM gravacoes WHERE id = ?", (id_,))
        if not atual:
            return False
        novo = {c: dados.get(c, atual[c]) for c in CAMPOS}
        novo["titulo"] = " ".join(str(novo["titulo"] or "").split()) or atual["titulo"]
        novo["tipo"] = novo["tipo"] if novo["tipo"] in TIPOS else atual["tipo"]
        novo["cadastro_id"] = novo["cadastro_id"] or None
        novo["servico_id"] = novo["servico_id"] or None
        novo["duracao_s"] = int(novo["duracao_s"] or 0)
        self.base.escrever(
            "UPDATE gravacoes SET titulo = ?, tipo = ?, cadastro_id = ?, servico_id = ?, participantes = ?, "
            "notas = ?, duracao_s = ? WHERE id = ?",
            (novo["titulo"], novo["tipo"], novo["cadastro_id"], novo["servico_id"], str(novo["participantes"] or ""),
             str(novo["notas"] or ""), novo["duracao_s"], id_),
        )
        return True

    def marcar(self, id_: int, segundo: int, texto: str) -> list[dict]:
        g = self.obter(id_)
        if not g:
            raise ValueError("gravação não encontrada")
        marcadores = g["marcadores"]
        marcadores.append({"t": max(0, int(segundo or 0)), "texto": " ".join(str(texto or "").split())})
        marcadores.sort(key=lambda m: m["t"])
        self.base.escrever("UPDATE gravacoes SET marcadores = ? WHERE id = ?",
                           (json.dumps(marcadores, ensure_ascii=False), id_))
        return marcadores

    def tirar_marcador(self, id_: int, indice: int) -> list[dict]:
        g = self.obter(id_)
        if not g:
            raise ValueError("gravação não encontrada")
        marcadores = g["marcadores"]
        if 0 <= indice < len(marcadores):
            marcadores.pop(indice)
        self.base.escrever("UPDATE gravacoes SET marcadores = ? WHERE id = ?",
                           (json.dumps(marcadores, ensure_ascii=False), id_))
        return marcadores

    # ------------------------------------------------------ transcricao

    def marcar_transcricao(self, id_: int, estado: str, *, trechos: list | None = None,
                           modelo: str = "", erro: str = "", tempo: float = 0.0) -> None:
        campos = {"transcricao_estado": estado, "transcricao_erro": erro}
        if trechos is not None:
            campos.update({
                "transcricao": json.dumps(trechos, ensure_ascii=False), "transcricao_em": _agora(),
                "transcricao_modelo": modelo, "transcricao_tempo": float(tempo),
            })
        sets = ", ".join(f"{k} = ?" for k in campos)
        self.base.escrever(f"UPDATE gravacoes SET {sets} WHERE id = ?", (*campos.values(), id_))

    def pendentes(self) -> list[int]:
        """O que ficou na fila (ou no meio) quando o programa fechou: volta para a fila."""
        linhas = self.base.buscar(
            "SELECT id FROM gravacoes WHERE transcricao_estado IN ('fila', 'transcrevendo') ORDER BY criado_em")
        ids = [int(l["id"]) for l in linhas]
        for id_ in ids:
            self.marcar_transcricao(id_, "fila")
        return ids

    def texto_da_transcricao(self, id_: int, com_minutos: bool = True) -> str:
        g = self.obter(id_)
        if not g:
            return ""
        linhas = []
        for t in g.get("trechos", []):
            linhas.append((f"[{duracao_texto(int(t.get('inicio', 0)))}] " if com_minutos else "") + t.get("texto", ""))
        return "\n".join(linhas)

    def corrigir(self, id_: int, de: str, para: str) -> int:
        """
        Troca um nome (ou qualquer palavra) na transcricao e no resumo.

        O Whisper erra nome proprio - "Priscilla" por "Priscila" - e o
        desenho pede "corrigir nomes". Palavra inteira, sem diferenciar
        maiuscula; devolve quantos trechos mudaram.
        """
        de = " ".join(str(de or "").split())
        para = " ".join(str(para or "").split())
        if not de or de == para:
            return 0
        g = self.obter(id_)
        if not g:
            raise ValueError("gravação não encontrada")
        limites = r"\b" if re.match(r"^\w", de) and re.search(r"\w$", de) else ""
        padrao = re.compile(limites + re.escape(de) + limites, re.IGNORECASE)
        trocados = 0
        trechos = g.get("trechos", [])
        for t in trechos:
            novo, n = padrao.subn(para, t.get("texto", ""))
            if n:
                t["texto"] = novo
                trocados += 1
        resumo = padrao.sub(para, g.get("resumo") or "")
        self.base.escrever("UPDATE gravacoes SET transcricao = ?, resumo = ? WHERE id = ?",
                           (json.dumps(trechos, ensure_ascii=False), resumo, id_))
        return trocados

    def html_para_exportar(self, id_: int) -> tuple[str, str]:
        """O titulo e o HTML (titulo, resumo, transcricao com minutos) que vira .docx."""
        g = self.obter(id_)
        if not g:
            raise ValueError("gravação não encontrada")
        quando = (g.get("criado_em") or "")[:16].replace("T", " ")
        meta = " · ".join(x for x in [g.get("tipo_rotulo", ""), quando, g.get("duracao_texto", ""),
                                      ", ".join(g.get("participantes_lista") or [])] if x)
        partes = ["<h1>" + _esc(g["titulo"]) + "</h1>", "<p>" + _esc(meta) + "</p>"]
        if g.get("resumo"):
            partes.append("<h2>Resumo</h2>")
            partes += ["<p>" + _esc(linha) + "</p>" for linha in g["resumo"].split("\n") if linha.strip()]
        partes.append("<h2>Transcrição</h2>")
        if g.get("trechos"):
            partes += ["<p>[" + duracao_texto(int(t.get("inicio", 0))) + "] " + _esc(t.get("texto", "")) + "</p>" for t in g["trechos"]]
        else:
            partes.append("<p>Esta gravação ainda não foi transcrita.</p>")
        if g.get("notas"):
            partes.append("<h2>Notas</h2>")
            partes += ["<p>" + _esc(linha) + "</p>" for linha in g["notas"].split("\n") if linha.strip()]
        return g["titulo"], "".join(partes)

    # anotacoes: as de Servicos - texto, quem e quando, editaveis e removiveis

    def _anotacoes(self, id_: int) -> list[dict]:
        g = self.base.um("SELECT notas, criado_em FROM gravacoes WHERE id = ?", (id_,))
        if not g:
            raise ValueError("gravação não encontrada")
        return anotacoes_de(g["notas"], g["criado_em"])

    def _gravar_anotacoes(self, id_: int, anotacoes: list[dict]) -> list[dict]:
        self.base.escrever("UPDATE gravacoes SET notas = ? WHERE id = ?",
                           (json.dumps(anotacoes, ensure_ascii=False) if anotacoes else "", id_))
        return anotacoes

    def anotar(self, id_: int, texto: str, quem: str = "") -> list[dict]:
        texto = str(texto or "").strip()
        if not texto:
            raise ValueError("a anotação está vazia")
        anotacoes = self._anotacoes(id_)
        anotacoes.insert(0, {"quem": quem, "quando": _agora(), "texto": texto})
        return self._gravar_anotacoes(id_, anotacoes)

    def anotacao_editar(self, id_: int, indice: int, texto: str, quem: str = "") -> list[dict]:
        """A anotacao reescrita ganha a data e a hora da edicao, como em Servicos."""
        texto = str(texto or "").strip()
        if not texto:
            raise ValueError("a anotação está vazia")
        anotacoes = self._anotacoes(id_)
        if indice < 0 or indice >= len(anotacoes):
            raise ValueError("anotação não encontrada")
        a = anotacoes[indice]
        if a.get("texto") != texto:
            a.update({"texto": texto, "quando": _agora(), "editada": True, "editada_por": quem})
        return self._gravar_anotacoes(id_, anotacoes)

    def anotacao_remover(self, id_: int, indice: int) -> list[dict]:
        anotacoes = self._anotacoes(id_)
        if indice < 0 or indice >= len(anotacoes):
            raise ValueError("anotação não encontrada")
        anotacoes.pop(indice)
        return self._gravar_anotacoes(id_, anotacoes)

    # a pasta do audio

    def mover_para(self, id_: int, pasta: Path | None) -> Path | None:
        """
        Leva o audio para outra pasta - a do servico a que a gravacao foi
        ligada, ou de volta para a pasta das gravacoes (pasta=None). Na pasta
        das gravacoes o nome fica relativo, como sempre foi; fora dela, o
        caminho inteiro. Nome repetido no destino vira "(2)".
        """
        atual = self.caminho(id_)
        if not atual:
            return None
        destino = Path(pasta) if pasta else self.pasta
        destino.mkdir(parents=True, exist_ok=True)
        if atual.parent.resolve() == destino.resolve():
            return atual
        alvo = destino / atual.name
        n = 2
        while alvo.exists():
            alvo = destino / f"{atual.stem} ({n}){atual.suffix}"
            n += 1
        shutil.move(str(atual), str(alvo))
        arquivo = alvo.name if destino.resolve() == self.pasta.resolve() else str(alvo)
        self.base.escrever("UPDATE gravacoes SET arquivo = ? WHERE id = ?", (arquivo, id_))
        return alvo

    def trocar_pasta(self, antes: Path, depois: Path) -> int:
        """A pasta de um servico mudou de nome: os audios que estavam nela vao junto."""
        prefixo = str(antes)
        trocados = 0
        for g in self.base.buscar("SELECT id, arquivo FROM gravacoes WHERE arquivo LIKE ?", (prefixo + "%",)):
            resto = g["arquivo"][len(prefixo):]
            if resto and resto[0] not in "\\/":
                continue
            self.base.escrever("UPDATE gravacoes SET arquivo = ? WHERE id = ?", (str(depois) + resto, g["id"]))
            trocados += 1
        return trocados

    def guardar_resumo(self, id_: int, texto: str) -> None:
        self.base.escrever("UPDATE gravacoes SET resumo = ?, resumo_em = ? WHERE id = ?", (texto, _agora(), id_))

    def apagar(self, id_: int) -> bool:
        caminho = self.caminho(id_)
        apagou = self.base.escrever("DELETE FROM gravacoes WHERE id = ?", (id_,)) > 0
        if apagou and caminho:
            try:
                caminho.unlink()
            except OSError:
                pass
        return apagou


def anotacoes_de(notas: str | None, criado_em: str = "") -> list[dict]:
    """
    As anotacoes guardadas na coluna `notas`. Antes das anotacoes, a coluna
    guardava um texto solto: ele vira a primeira anotacao, com a data da
    gravacao, e nada se perde.
    """
    texto = str(notas or "").strip()
    if not texto:
        return []
    if texto.startswith("["):
        try:
            valor = json.loads(texto)
            if isinstance(valor, list):
                return [a for a in valor if isinstance(a, dict) and a.get("texto")]
        except json.JSONDecodeError:
            pass
    return [{"quem": "", "quando": criado_em or "", "texto": texto}]
