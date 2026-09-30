"""
Pensar no aparelho (docs/PROGRESSO-APARELHO.md, D1): o pacote de escrita e a
porta por onde ele sai e o texto volta.

A regra que manda em tudo: o aparelho nunca recebe mais do que a pessoa já
veria na tela pelo acesso de fora, e nada fica guardado nele.

Como a pergunta anda:

1. A pergunta de fora pede "escrever neste aparelho" (`Pergunta.aparelho`).
   `pode_escrever` confere, no servidor: o recurso ligado (`aparelho.ligado`),
   a sessão de fora, o nível "aparelho" da conta (dado pelo titular) e que a
   conta vê o Acervo. Não pode: a resposta é escrita no escritório, com o
   motivo.
2. Tudo o que envolve o acervo continua no escritório, pelo caminho de
   sempre - escopo, filtro de Serviços, busca, trechos. O pacote é montado
   DEPOIS disso, no ponto exato em que o escritório chamaria o modelo
   (habilidades/perguntar.py, `_responder`): as mesmas mensagens, sem os
   lembretes do escritório (de fora, ninguém os vê).
3. `Escrita.preparar` recusa, e a resposta segue no escritório: caminho que
   não é o de trechos (o Acervo inteiro, o documento em foco lido inteiro, os
   fatos já lidos); trecho de caso marcado "só no escritório"; trecho de
   documento fora do filtro da pessoa (defesa em profundidade: a busca já
   filtrou); trechos acima do orçamento da busca (3.000 tokens).
4. Passou: a vez do modelo é devolvida à fila (quem escreve é o aparelho), e
   a execução espera o texto por até `VALIDADE_S`. O evento da execução - que
   fica no disco - leva só o id e a assinatura do pacote; o conteúdo sai pela
   rota, para a mesma sessão que pediu, uma vez.
5. O texto que volta é tratado como não confiável: `conferir` decide. Até a
   D3 existir, ela reprova tudo - e a resposta é refeita no escritório. Nada
   do aparelho é gravado sem passar pela conferência.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
import time
import uuid
from pathlib import Path

from fastapi import HTTPException, Request
from pydantic import BaseModel

VALIDADE_S = 600
# O orçamento da busca por trechos (src/recuperacao.py): 3.000 tokens, a 3
# caracteres por token. O pacote nunca passa disso.
ORCAMENTO_CARACTERES = 3000 * 3
CAMINHOS_DE_TRECHOS = ("busca", "foco")

_SEGREDO = secrets.token_bytes(32)
_PACOTES: dict[str, dict] = {}
# A pasta de dados desta maquina, dada em `montar`.
_DADOS: dict = {"dir": None}
_trava = threading.Lock()


def ligado(estado) -> bool:
    return bool((estado.prefs.dados.get("aparelho") or {}).get("ligado"))


def _pessoa(request):
    from acesso import rotas as rotas_do_acesso

    return rotas_do_acesso.pessoa(request)


def pode_escrever(estado, request) -> tuple[bool, str]:
    """Se esta pessoa, nesta sessão, pode ter a resposta escrita no aparelho. (pode, motivo)."""
    if not ligado(estado):
        return False, "o escritório não ligou a escrita no aparelho"
    pessoa = _pessoa(request)
    if not pessoa:
        return False, "na janela do escritório a resposta é escrita aqui"
    niveis = pessoa.get("permissoes") or {}
    if niveis.get("aparelho") != "faz":
        return False, "o titular não liberou a escrita no aparelho para a sua conta"
    if niveis.get("acervo") == "nao":
        return False, "a sua conta não vê o Acervo"
    return True, ""


# ------------------------------------------------------- só no escritório

class SoNoEscritorio:
    """
    Os casos cujo conteúdo nunca vai para aparelho: pastas do Acervo e
    Serviços (a pasta de trabalho de cada um). Um arquivo por máquina,
    <dados>/aparelho/so-no-escritorio.json; quem marca é o titular (D5).
    """

    def __init__(self, pasta: Path) -> None:
        self.arquivo = Path(pasta) / "so-no-escritorio.json"

    def marcas(self) -> list[dict]:
        try:
            return list(json.loads(self.arquivo.read_text(encoding="utf-8")).get("marcas") or [])
        except (OSError, ValueError):
            return []

    def guardar(self, marcas: list[dict]) -> None:
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        self.arquivo.write_text(json.dumps({"marcas": marcas}, ensure_ascii=False, indent=1), encoding="utf-8")

    def pastas(self, estado) -> list[Path]:
        saida = []
        for m in self.marcas():
            try:
                if m.get("tipo") == "pasta":
                    p = Path(m["valor"])
                    saida.append((p if p.is_absolute() else Path(estado.pasta) / p).resolve())
                elif m.get("tipo") == "servico":
                    pasta = estado.servicos.pasta_de(int(m["valor"]))
                    if pasta:
                        saida.append(Path(pasta).resolve())
            except (KeyError, ValueError, TypeError, OSError):
                continue
        return saida

    def toca(self, estado, caminhos: list[str]) -> bool:
        pastas = self.pastas(estado)
        if not pastas:
            return False
        for c in caminhos:
            try:
                alvo = Path(c).resolve()
            except OSError:
                continue
            if any(alvo == p or alvo.is_relative_to(p) for p in pastas):
                return True
        return False


def so_no_escritorio() -> SoNoEscritorio:
    return SoNoEscritorio(Path(_DADOS["dir"] or ".") / "aparelho")


# ------------------------------------------------------------ o pacote

def _assinar(pid: str, sessao: str, expira: float) -> str:
    return hmac.new(_SEGREDO, f"{pid}|{sessao}|{int(expira)}".encode(), hashlib.sha256).hexdigest()


def _aparelho_curto(request) -> str:
    """Sem identificador invasivo: 6 caracteres do hash do navegador, para a auditoria distinguir dois aparelhos."""
    try:
        agente = dict(request.headers).get("user-agent", "") if request is not None else ""
    except Exception:  # noqa: BLE001
        agente = ""
    return "navegador " + hashlib.sha256(agente.encode()).hexdigest()[:6] if agente else "navegador"


def auditar(estado, pessoa: dict | None, alvo: str) -> None:
    try:
        estado.acesso_de_fora.anotar(acao="aparelho", alvo=alvo, pessoa=(pessoa or {}).get("nome") or "?",
                                     email=(pessoa or {}).get("email", ""))
    except Exception:  # noqa: BLE001 - o registro não derruba a pergunta
        pass


class Escrita:
    """Uma pergunta que pediu o aparelho: montada no escritório, escrita lá, conferida aqui."""

    def __init__(self, estado, request, trabalho_id: str) -> None:
        self.estado = estado
        self.pessoa = _pessoa(request) or {}
        self.sessao = str(self.pessoa.get("hash") or "")
        self.aparelho = _aparelho_curto(request)
        self.trabalho_id = trabalho_id
        self.pid = ""
        self.onde = "escritorio"
        self.motivo = ""
        self.conferida = False

    # ------------------------------------------------------------ montar
    def preparar(self, *, pergunta: str, mensagens: list[dict], fontes: list[dict], hits, caminho: str,
                 por_trechos: bool, parametros: dict) -> dict | None:
        """
        O pacote desta resposta, ou None (com `motivo`) - e a resposta segue
        no escritório. Chamado DEPOIS do filtro e da busca.
        """
        if not por_trechos or caminho not in CAMINHOS_DE_TRECHOS:
            self.motivo = ("a pergunta pede o documento inteiro" if caminho == "foco" else
                           "a pergunta pede o Acervo inteiro" if caminho == "tudo" else
                           "esta resposta não é por trechos")
            return None
        import search as search_mod

        caminhos = [getattr(h.chunk, "doc_path", "") for h in hits]
        filtro = search_mod.FILTRO.get()
        if filtro is not None and not all(filtro(c) for c in caminhos if c):
            self.motivo = "um trecho não é de documento que a sua conta vê"
            return None
        if so_no_escritorio().toca(self.estado, caminhos):
            self.motivo = "a resposta usa um caso marcado só no escritório"
            return None
        trechos = [{"n": i + 1, "documento": f.get("documento", ""), "texto": f.get("texto", ""),
                    **({"pagina": f["pagina"]} if f.get("pagina") else {})} for i, f in enumerate(fontes)]
        if sum(len(t["texto"]) for t in trechos) > ORCAMENTO_CARACTERES:
            self.motivo = "trechos demais para mandar ao aparelho"
            return None
        agora = time.time()
        self.pid = uuid.uuid4().hex
        expira = agora + VALIDADE_S
        with _trava:
            _PACOTES[self.pid] = {
                "sessao": self.sessao, "conta_id": self.pessoa.get("conta_id"), "expira": expira, "estado": "pronto",
                "trabalho_id": self.trabalho_id, "pessoa": dict(self.pessoa), "aparelho": self.aparelho,
                "conteudo": {"pergunta": pergunta, "mensagens": mensagens, "trechos": trechos,
                             "parametros": parametros, "expira_s": VALIDADE_S},
                "documentos": list(dict.fromkeys(t["documento"] for t in trechos)),
                "chegou": threading.Event(), "texto": "", "parcial": "",
            }
        # A vez do modelo volta para a fila: quem escreve agora é o aparelho.
        import fila_modelo

        vez = fila_modelo.VEZ.get()
        if vez is not None:
            self.estado.fila_modelo.sair(vez)
        self.onde = "aparelho"
        return {"pacote": self.pid, "assinatura": _assinar(self.pid, self.sessao, expira), "expira_s": VALIDADE_S}

    def esperar(self, parar=None) -> dict:
        """Bloqueia até o aparelho devolver, abandonar, o pacote vencer ou a pessoa parar."""
        reg = _PACOTES.get(self.pid)
        if reg is None:
            return {"estado": "sumiu"}
        while not reg["chegou"].wait(0.5):
            if parar is not None and parar():
                self._encerrar("parado")
                return {"estado": "parado"}
            if time.time() > reg["expira"] or not ligado(self.estado):
                self._encerrar("vencido" if ligado(self.estado) else "desligado")
                return {"estado": reg["estado"], "parcial": reg.get("parcial", "")}
        return {"estado": reg["estado"], "texto": reg.get("texto", ""), "parcial": reg.get("parcial", "")}

    def _encerrar(self, como: str) -> None:
        with _trava:
            reg = _PACOTES.get(self.pid)
            if reg and reg["estado"] in ("pronto", "entregue"):
                reg["estado"] = como

    # ---------------------------------------------------------- conferir
    def conferir(self, texto: str, fontes: list[dict]) -> tuple[bool, str]:
        """
        O texto do aparelho é não confiável. D1: a conferência do escritório
        para ele ainda não existe (é a D3) - reprova tudo, e a resposta é
        refeita no escritório.
        """
        return False, "a conferência do texto do aparelho ainda não existe"

    def voltou_ao_escritorio(self, motivo: str) -> None:
        self.onde = "escritorio"
        self.motivo = motivo

    def resumo(self) -> dict:
        """O que fica na resposta: onde foi escrita e por quê (D4 mostra)."""
        return {"onde": self.onde, "motivo": self.motivo, "conferida": self.conferida, "pacote": bool(self.pid)}


# ------------------------------------------------------------- a porta

class Devolver(BaseModel):
    assinatura: str
    texto: str = ""


class Abandonar(BaseModel):
    assinatura: str
    parcial: str = ""


def _pacote_da_sessao(pid: str, assinatura: str, request) -> dict:
    """O pacote, se a assinatura e a sessão batem e ele vale. Senão, 403 ou 410 - sem dizer qual parte falhou."""
    pessoa = _pessoa(request) or {}
    reg = _PACOTES.get(pid)
    if reg is None:
        raise HTTPException(status_code=410, detail="esse pacote não existe mais")
    sessao = str(pessoa.get("hash") or "")
    if not sessao or not hmac.compare_digest(sessao, reg["sessao"]) or \
            not hmac.compare_digest(_assinar(pid, reg["sessao"], reg["expira"]), str(assinatura or "")):
        raise HTTPException(status_code=403, detail="esse pacote é de outra sessão")
    if time.time() > reg["expira"]:
        with _trava:
            if reg["estado"] in ("pronto", "entregue"):
                reg["estado"] = "vencido"
                reg["chegou"].set()
        raise HTTPException(status_code=410, detail="esse pacote venceu")
    return reg


def montar(estado, app, dados_dir) -> None:
    _DADOS["dir"] = Path(dados_dir)

    @app.get("/api/aparelho/estado")
    def aparelho_estado(request: Request = None) -> dict:
        pode, motivo = pode_escrever(estado, request)
        return {"ligado": ligado(estado), "pode": pode, "motivo": motivo, "validade_s": VALIDADE_S}

    @app.get("/api/aparelho/pacote/{pid}")
    def aparelho_pacote(pid: str, assinatura: str = "", request: Request = None) -> dict:
        reg = _pacote_da_sessao(pid, assinatura, request)
        with _trava:
            if reg["estado"] != "pronto":
                raise HTTPException(status_code=409, detail="esse pacote já foi entregue")
            reg["estado"] = "entregue"
        auditar(estado, reg["pessoa"], f"recebeu {len(reg['conteudo']['trechos'])} trecho(s) de "
                                       f"{', '.join(reg['documentos']) or 'nenhum documento'} para escrever "
                                       f"({reg['aparelho']})")
        return reg["conteudo"]

    @app.post("/api/aparelho/pacote/{pid}/devolver")
    def aparelho_devolver(pid: str, payload: Devolver, request: Request = None) -> dict:
        reg = _pacote_da_sessao(pid, payload.assinatura, request)
        with _trava:
            if reg["estado"] != "entregue":
                raise HTTPException(status_code=409, detail="esse pacote já foi usado")
            reg["estado"] = "devolvido"
            reg["texto"] = str(payload.texto or "")[:20000]
            reg["chegou"].set()
        auditar(estado, reg["pessoa"], f"devolveu o texto ({len(reg['texto'])} caracteres, {reg['aparelho']})")
        return {"recebido": True}

    @app.post("/api/aparelho/pacote/{pid}/abandonar")
    def aparelho_abandonar(pid: str, payload: Abandonar, request: Request = None) -> dict:
        reg = _pacote_da_sessao(pid, payload.assinatura, request)
        with _trava:
            if reg["estado"] not in ("pronto", "entregue"):
                raise HTTPException(status_code=409, detail="esse pacote já foi usado")
            reg["estado"] = "abandonado"
            reg["parcial"] = str(payload.parcial or "")[:20000]
            reg["chegou"].set()
        auditar(estado, reg["pessoa"], f"abandonou a escrita ({reg['aparelho']}); o escritório termina")
        return {"recebido": True}
