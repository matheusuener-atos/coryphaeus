"""
Aprender com o uso (docs/PLANO-PILOTO.md, L1).

- **Avaliação** 👍/👎 em cada resposta da conversa, por quem perguntou - de
  dentro ou de fora. Guarda uma cópia do que foi avaliado (a pergunta, a
  resposta, os documentos citados e como a resposta foi feita): a conversa
  pode mudar ou ir para a lixeira, e o caderno continua contando o que
  aconteceu. Fica só neste computador, na base local.
- **Caderno de falhas**: as 👎, com o motivo, o comentário e a resposta
  certa, na janela do escritório (de fora ninguém lê o caderno).
- **A correção vira caso de teste**: quem marca 👎 pode dizer o que a
  resposta certa precisa ter (palavras). Com isso, a pergunta entra no
  conjunto real (data/medicao/conjunto-real.jsonl, docs/medicao.md), o mesmo
  em que a correção do cartão do documento (I9) já entrava - e é dele que
  `tools/medir.py` mede cada troca de modelo, de regra ou de prompt.

Ligado de fábrica (`aprendizado.avaliar`): o piloto precisa medir desde o
primeiro dia, e nada disto sai da máquina.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import HTTPException, Request
from pydantic import BaseModel

MOTIVOS = {
    "fato": "errou um fato",
    "faltou": "faltou informação",
    "fonte": "citou errado ou sem fonte",
    "entendeu": "não entendeu a pergunta",
    "demorou": "demorou demais",
    "outro": "outro",
}
NOTAS = ("bom", "ruim")
MAX_TEXTO = 4000
MAX_TERMOS = 8

_trava = threading.Lock()


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def termos_de(bruto) -> list[str]:
    """As palavras que a resposta certa precisa ter: separadas por vírgula ou ponto e vírgula."""
    if isinstance(bruto, (list, tuple)):
        itens = bruto
    else:
        itens = str(bruto or "").replace(";", ",").split(",")
    saida = []
    for t in itens:
        t = " ".join(str(t).split())[:80]
        if t and t.casefold() not in {x.casefold() for x in saida}:
            saida.append(t)
    return saida[:MAX_TERMOS]


def caso_de_teste(av: dict, termos: list[str]) -> dict:
    """A linha do conjunto real (docs/medicao.md) que a correção vira: cada termo precisa aparecer."""
    return {"pergunta": av["pergunta"], "caminho": "documentos", "tipo": "fato", "alguma": [],
            "todas": [[t] for t in termos], "nunca": [], "documentos": list(av.get("documentos") or []),
            "trechos_esperados": [], "origem": "caderno de falhas", "motivo": av.get("motivo") or "",
            "avaliacao": av["id"], "quando": _agora()}


class Aprendizado:
    def __init__(self, base, trabalhos, conjunto: Path) -> None:
        self.base = base
        self.trabalhos = trabalhos
        self.conjunto = Path(conjunto)

    # ----------------------------------------------------------- avaliar
    def _resposta(self, trabalho_id: str, indice: int) -> tuple[str, dict]:
        t = self.trabalhos.obter(trabalho_id)
        if not t:
            raise LookupError("conversa não encontrada")
        mensagens = list(t.mensagens)
        if not 0 <= indice < len(mensagens) or getattr(mensagens[indice], "autor", "") != "paulus":
            raise LookupError("essa mensagem não é uma resposta do assistente")
        m = mensagens[indice]
        pergunta = next((x.texto for x in reversed(mensagens[:indice]) if x.autor == "pessoa"), "")
        como = dict((getattr(m, "cobertura", {}) or {}).get("como") or {})
        documentos = list(dict.fromkeys(f.get("documento", "") for f in (getattr(m, "fontes", []) or []) if f.get("documento")))
        return pergunta, {
            "resposta": str(m.texto or "")[:MAX_TEXTO], "documentos": documentos[:12],
            "caminho": como.get("caminho") or "", "modelo": como.get("modelo") or "",
            "onde": ((como.get("escrita") or {}).get("onde") or "escritorio"),
            "titulo": getattr(t, "titulo", "") or "",
        }

    def avaliar(self, trabalho_id: str, indice: int, nota: str, pessoa: str, pessoa_nome: str = "", *,
                motivo: str = "", comentario: str = "", correcao: str = "", deve_conter=None) -> dict:
        if nota not in NOTAS:
            raise ValueError("a nota é bom ou ruim")
        if motivo and motivo not in MOTIVOS:
            raise ValueError("motivo desconhecido")
        pergunta, copia = self._resposta(trabalho_id, int(indice))
        termos = termos_de(deve_conter) if nota == "ruim" else []
        with _trava:
            velha = self.base.um("SELECT id, caso FROM avaliacoes WHERE trabalho_id = ? AND indice = ? AND pessoa = ?",
                                 (trabalho_id, int(indice), pessoa))
            campos = (nota, motivo if nota == "ruim" else "", str(comentario or "")[:MAX_TEXTO] if nota == "ruim" else "",
                      str(correcao or "")[:MAX_TEXTO] if nota == "ruim" else "", json.dumps(termos, ensure_ascii=False),
                      pergunta[:MAX_TEXTO], copia["resposta"], json.dumps(copia["documentos"], ensure_ascii=False),
                      copia["caminho"], copia["modelo"], copia["onde"], copia["titulo"], pessoa_nome, _agora())
            if velha:
                self.base.escrever(
                    "UPDATE avaliacoes SET nota=?, motivo=?, comentario=?, correcao=?, termos=?, pergunta=?, resposta=?,"
                    " documentos=?, caminho=?, modelo=?, onde=?, titulo=?, pessoa_nome=?, quando=?, resolvida=0 WHERE id = ?",
                    campos + (velha["id"],))
                id_ = velha["id"]
            else:
                id_ = self.base.escrever(
                    "INSERT INTO avaliacoes (nota, motivo, comentario, correcao, termos, pergunta, resposta, documentos,"
                    " caminho, modelo, onde, titulo, pessoa_nome, quando, trabalho_id, indice, pessoa)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", campos + (trabalho_id, int(indice), pessoa))
        av = self.obter(id_)
        if nota == "ruim" and termos and not av["caso"]:
            av = self.virar_caso(id_, termos)
        return av

    def obter(self, id_: int) -> dict | None:
        l = self.base.um("SELECT * FROM avaliacoes WHERE id = ?", (int(id_),))
        return self._enfeitar(l) if l else None

    @staticmethod
    def _enfeitar(l: dict) -> dict:
        d = dict(l)
        d["termos"] = json.loads(d.get("termos") or "[]")
        d["documentos"] = json.loads(d.get("documentos") or "[]")
        d["motivo_rotulo"] = MOTIVOS.get(d.get("motivo") or "", "")
        d["caso"] = bool(d.get("caso"))
        d["resolvida"] = bool(d.get("resolvida"))
        return d

    def da_conversa(self, trabalho_id: str, pessoa: str) -> dict:
        """{indice: {nota, motivo}} desta pessoa nesta conversa - para a tela marcar os botões."""
        return {str(l["indice"]): {"nota": l["nota"], "motivo": l["motivo"], "caso": bool(l["caso"])}
                for l in self.base.buscar("SELECT indice, nota, motivo, caso FROM avaliacoes WHERE trabalho_id = ? AND pessoa = ?",
                                          (trabalho_id, pessoa))}

    # ----------------------------------------------------------- caderno
    def caderno(self, *, abertas: bool = False, dias: int = 30) -> dict:
        falhas = [self._enfeitar(l) for l in self.base.buscar(
            "SELECT * FROM avaliacoes WHERE nota = 'ruim'" + (" AND resolvida = 0" if abertas else "") + " ORDER BY quando DESC LIMIT 500")]
        desde = (datetime.now() - timedelta(days=dias)).isoformat(timespec="seconds")
        conta: dict = {"bom": 0, "ruim": 0}
        por_caminho: dict = {}
        por_modelo: dict = {}
        por_motivo: dict = {}
        for l in self.base.buscar("SELECT nota, caminho, modelo, onde, motivo FROM avaliacoes WHERE quando >= ?", (desde,)):
            conta[l["nota"]] = conta.get(l["nota"], 0) + 1
            for grupo, chave in ((por_caminho, l["caminho"] or "?"),
                                 (por_modelo, (l["modelo"] or "?") + (" · aparelho" if l["onde"] == "aparelho" else ""))):
                g = grupo.setdefault(chave, {"bom": 0, "ruim": 0})
                g[l["nota"]] += 1
            if l["nota"] == "ruim":
                por_motivo[l["motivo"] or "sem motivo"] = por_motivo.get(l["motivo"] or "sem motivo", 0) + 1
        return {"falhas": falhas, "dias": dias, "conta": conta, "por_caminho": por_caminho, "por_modelo": por_modelo,
                "por_motivo": {MOTIVOS.get(k, k): v for k, v in por_motivo.items()},
                "casos": sum(1 for f in falhas if f["caso"])}

    def virar_caso(self, id_: int, termos) -> dict:
        av = self.obter(id_)
        if not av:
            raise LookupError("avaliação não encontrada")
        if av["nota"] != "ruim":
            raise ValueError("só uma 👎 vira caso de teste")
        termos = termos_de(termos)
        if not termos:
            raise ValueError("diga o que a resposta certa precisa ter")
        if not av["pergunta"].strip():
            raise ValueError("a resposta não tem pergunta antes dela")
        linha = caso_de_teste(av, termos)
        with _trava:
            self.conjunto.parent.mkdir(parents=True, exist_ok=True)
            with open(self.conjunto, "a", encoding="utf-8") as f:
                f.write(json.dumps(linha, ensure_ascii=False) + "\n")
            self.base.escrever("UPDATE avaliacoes SET caso = 1, termos = ? WHERE id = ?",
                               (json.dumps(termos, ensure_ascii=False), int(id_)))
        return self.obter(id_)

    def resolver(self, id_: int, resolvida: bool = True) -> dict:
        self.base.escrever("UPDATE avaliacoes SET resolvida = ? WHERE id = ?", (1 if resolvida else 0, int(id_)))
        av = self.obter(id_)
        if not av:
            raise LookupError("avaliação não encontrada")
        return av


# ------------------------------------------------------------------ rotas

class Avaliar(BaseModel):
    trabalho_id: str
    indice: int
    nota: str
    motivo: str = ""
    comentario: str = ""
    correcao: str = ""
    deve_conter: str | list[str] = ""


class Termos(BaseModel):
    deve_conter: str | list[str] = ""


class Resolver(BaseModel):
    resolvida: bool = True


def montar(estado, app, dados_dir: Path) -> None:
    from acesso import rotas as rotas_do_acesso

    estado.aprendizado = Aprendizado(estado.base, estado.trabalhos, Path(dados_dir) / "medicao" / "conjunto-real.jsonl")

    def _quem(request) -> tuple[str, str]:
        p = rotas_do_acesso.pessoa(request)
        return (f"conta:{p['conta_id']}", p.get("nome") or "") if p else ("local", "janela local")

    def ligado() -> bool:
        return bool((estado.prefs.dados.get("aprendizado") or {}).get("avaliar", True))

    @app.post("/api/aprendizado/avaliar")
    def aprendizado_avaliar(payload: Avaliar, request: Request = None) -> dict:
        if not ligado():
            raise HTTPException(status_code=409, detail="a avaliação das respostas está desligada")
        pessoa, nome = _quem(request)
        try:
            return estado.aprendizado.avaliar(payload.trabalho_id, payload.indice, payload.nota, pessoa, nome,
                                              motivo=payload.motivo, comentario=payload.comentario,
                                              correcao=payload.correcao, deve_conter=payload.deve_conter)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    @app.get("/api/aprendizado/da-conversa/{trabalho_id}")
    def aprendizado_da_conversa(trabalho_id: str, request: Request = None) -> dict:
        pessoa, _ = _quem(request)
        return {"ligado": ligado(), "avaliacoes": estado.aprendizado.da_conversa(trabalho_id, pessoa), "motivos": MOTIVOS}

    @app.get("/api/aprendizado/caderno")
    def aprendizado_caderno(abertas: bool = False, dias: int = 30, request: Request = None) -> dict:
        rotas_do_acesso.so_local(request)
        return estado.aprendizado.caderno(abertas=abertas, dias=max(1, min(dias, 365)))

    @app.post("/api/aprendizado/caderno/{id_}/caso")
    def aprendizado_caso(id_: int, payload: Termos, request: Request = None) -> dict:
        rotas_do_acesso.so_local(request)
        try:
            return estado.aprendizado.virar_caso(id_, payload.deve_conter)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    @app.post("/api/aprendizado/caderno/{id_}/resolver")
    def aprendizado_resolver(id_: int, payload: Resolver, request: Request = None) -> dict:
        rotas_do_acesso.so_local(request)
        try:
            return estado.aprendizado.resolver(id_, payload.resolvida)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
