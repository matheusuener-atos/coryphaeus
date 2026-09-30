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
5. O texto que volta é tratado como não confiável: `conferir`
   (src/aparelho_conferencia.py, D3) decide. Reprovou: o escritório reescreve.
6. Retomada (D3): o aparelho manda o texto parcial enquanto escreve
   (`/pedaco`). Abandonou, venceu ou ficou `SILENCIO_S` sem sinal: o
   escritório continua a partir do parcial - se ele passar na mesma
   conferência -, ou escreve do zero. A resposta diz onde cada parte foi
   escrita.
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
from pydantic import BaseModel, ConfigDict

VALIDADE_S = 600
# Sem sinal do aparelho (nem pedir o pacote, nem mandar pedaço) por este tempo:
# a aba fechou ou o aparelho ficou sem rede - o escritório termina.
SILENCIO_S = 45
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


def ainda_pode(estado, pessoa: dict | None) -> tuple[bool, str]:
    """
    Com a escrita em andamento: o recurso continua ligado, e o titular não
    tirou a liberação desta conta? O nível é lido de novo da conta (D5), e
    não da sessão de quando a pergunta saiu.
    """
    if not ligado(estado):
        return False, "o escritório desligou a escrita no aparelho"
    conta_id = (pessoa or {}).get("conta_id")
    if conta_id is None:
        return True, ""
    try:
        conta = estado.acesso_de_fora.contas.obter(int(conta_id))
    except Exception:  # noqa: BLE001 - sem ler a conta, não arrisca
        conta = None
    if not conta or (conta.get("permissoes") or {}).get("aparelho") != "faz":
        return False, "o titular desligou a escrita no aparelho para a sua conta"
    return True, ""


# ------------------------------------------------------- só no escritório

class SoNoEscritorio:
    """
    Os casos cujo conteúdo nunca vai para aparelho: pastas do Acervo,
    Serviços (a pasta de trabalho de cada um) e clientes (as pastas de todos
    os Serviços do cliente, inclusive os abertos depois de marcar). Um
    arquivo por máquina, <dados>/aparelho/so-no-escritorio.json; quem marca
    é o titular, na janela do escritório (D5).
    """

    TIPOS = ("cliente", "servico", "pasta")

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
                    pasta = estado.servicos.pasta_de(int(m["valor"]), criar=False)
                    if pasta:
                        saida.append(Path(pasta).resolve())
                elif m.get("tipo") == "cliente":
                    for s in estado.servicos.base.buscar("SELECT id FROM servicos WHERE cadastro_id = ?", (int(m["valor"]),)):
                        pasta = estado.servicos.pasta_de(int(s["id"]), criar=False)
                        if pasta:
                            saida.append(Path(pasta).resolve())
            except (KeyError, ValueError, TypeError, OSError):
                continue
        return saida

    def para_a_tela(self, estado) -> list[dict]:
        """As marcas com o nome de cada uma, para a janela do escritório."""
        saida = []
        for m in self.marcas():
            rotulo = str(m.get("valor", ""))
            try:
                if m.get("tipo") == "servico":
                    l = estado.servicos.base.um("SELECT nome FROM servicos WHERE id = ?", (int(m["valor"]),))
                    rotulo = l["nome"] if l else "Serviço apagado"
                elif m.get("tipo") == "cliente":
                    l = estado.servicos.base.um("SELECT nome FROM cadastros WHERE id = ?", (int(m["valor"]),))
                    rotulo = l["nome"] if l else "Cliente apagado"
            except (ValueError, TypeError):
                pass
            saida.append({"tipo": m.get("tipo"), "valor": m.get("valor"), "rotulo": rotulo})
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
        self.pergunta = ""
        # Onde cada parte da resposta foi escrita (D3): [{"onde", "caracteres"}].
        self.partes: list[dict] = []

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
        self.pergunta = pergunta
        self.pid = uuid.uuid4().hex
        expira = agora + VALIDADE_S
        with _trava:
            _PACOTES[self.pid] = {
                "sessao": self.sessao, "conta_id": self.pessoa.get("conta_id"), "expira": expira, "estado": "pronto",
                "trabalho_id": self.trabalho_id, "pessoa": dict(self.pessoa), "aparelho": self.aparelho,
                "conteudo": {"pergunta": pergunta, "mensagens": mensagens, "trechos": trechos,
                             "parametros": parametros, "expira_s": VALIDADE_S},
                "documentos": list(dict.fromkeys(t["documento"] for t in trechos)),
                "chegou": threading.Event(), "texto": "", "parcial": "", "sinal": agora,
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
            pode, motivo = ainda_pode(self.estado, self.pessoa)
            if not pode:
                self._encerrar("desligado")
                return {"estado": "desligado", "parcial": reg.get("parcial", ""), "motivo": motivo}
            if time.time() > reg["expira"]:
                self._encerrar("vencido")
                return {"estado": reg["estado"], "parcial": reg.get("parcial", "")}
            if time.time() - reg.get("sinal", 0) > SILENCIO_S:
                self._encerrar("sem_sinal")
                return {"estado": "sem_sinal", "parcial": reg.get("parcial", "")}
        return {"estado": reg["estado"], "texto": reg.get("texto", ""), "parcial": reg.get("parcial", ""),
                "motivo": reg.get("motivo", "")}

    def _encerrar(self, como: str) -> None:
        with _trava:
            reg = _PACOTES.get(self.pid)
            if reg and reg["estado"] in ("pronto", "entregue"):
                reg["estado"] = como

    # ---------------------------------------------------------- conferir
    def conferir(self, texto: str, fontes: list[dict]) -> tuple[bool, str, str]:
        """
        O texto do aparelho é não confiável (D3, src/aparelho_conferencia.py):
        (passou, o texto conferido, o motivo quando reprovou).
        """
        import aparelho_conferencia

        r = aparelho_conferencia.conferir(texto, [f.get("texto", "") for f in fontes], self.pergunta)
        if r["removidas"]:
            auditar(self.estado, self.pessoa, "a conferência tirou do texto do aparelho: " + "; ".join(r["removidas"][:5]))
        if not r["ok"]:
            auditar(self.estado, self.pessoa, "texto do aparelho reprovado na conferência: " + "; ".join(r["motivos"]))
        return r["ok"], r["texto"], "; ".join(r["motivos"])

    def voltou_ao_escritorio(self, motivo: str) -> None:
        self.onde = "escritorio"
        self.motivo = motivo

    def resumo(self) -> dict:
        """O que fica na resposta: onde foi escrita e por quê (D4 mostra)."""
        return {"onde": self.onde, "motivo": self.motivo, "conferida": self.conferida, "pacote": bool(self.pid),
                "partes": self.partes, "modelo": nome_do_modelo(self.estado) if self.pid else ""}


    def fechar(self) -> None:
        """
        A linha do fim na auditoria (D5): onde a resposta ficou. É dela que
        sai o relatório do titular - quantas no aparelho, quantas refeitas.
        """
        if not self.pid:
            return
        if self.onde == "aparelho":
            alvo = FIM_NO_APARELHO
        elif self.motivo == "conferência reprovou":
            alvo = FIM_REFEITA + ": " + self.motivo
        else:
            alvo = FIM_NO_ESCRITORIO + ": " + (self.motivo or "?")
        auditar(self.estado, self.pessoa, alvo + f" ({self.aparelho})")


FIM_NO_APARELHO = "resposta escrita no aparelho"
FIM_REFEITA = "resposta refeita no escritório"
FIM_NO_ESCRITORIO = "o escritório terminou a resposta"


def relatorio(estado) -> dict:
    """Por pessoa: respostas escritas no aparelho, refeitas pela conferência e terminadas no escritório."""
    pessoas: dict[str, dict] = {}
    for l in estado.acesso_de_fora.auditoria.linhas():
        if l.get("acao") != "aparelho":
            continue
        alvo = str(l.get("alvo") or "")
        chave = "no_aparelho" if alvo.startswith(FIM_NO_APARELHO) else (
            "refeitas" if alvo.startswith(FIM_REFEITA) else ("no_escritorio" if alvo.startswith(FIM_NO_ESCRITORIO) else ""))
        if not chave:
            continue
        p = pessoas.setdefault(l.get("email") or l.get("pessoa") or "?",
                               {"pessoa": l.get("pessoa") or "?", "email": l.get("email") or "",
                                "no_aparelho": 0, "refeitas": 0, "no_escritorio": 0, "ultima": ""})
        p[chave] += 1
        p["ultima"] = max(p["ultima"], str(l.get("quando") or ""))
    lista = sorted(pessoas.values(), key=lambda p: (-p["no_aparelho"], p["pessoa"]))
    return {"pessoas": lista, "total": {k: sum(p[k] for p in lista) for k in ("no_aparelho", "refeitas", "no_escritorio")}}


# ------------------------------------------------ a sugestão e o Automático (D4)

# Como a pessoa decidiu no seletor, quando a resposta é do escritório: o que a
# resposta diz (Pergunta.escolha).
ESCOLHAS = {
    "escritorio": "você escolheu o escritório",
    "fila": "você escolheu esperar na fila",
    "automatico": "no automático, o escritório estava mais rápido",
    "caso": "a conversa está num caso marcado só no escritório",
    "inteiro": "a pergunta pede o documento inteiro",
}
# A janela de sugestão aparece com a espera estimada acima disto, ou com
# tantas perguntas na frente (§3).
LIMITE_ESPERA_S = 30
LIMITE_NA_FRENTE = 2
# Uma resposta típica por trechos, para comparar o aparelho com o escritório:
# ~1.500 tokens de pergunta (instruções + 6 trechos) e ~250 de resposta.
TOKENS_DA_PERGUNTA = 1500
TOKENS_DA_RESPOSTA = 250
# Sem medida do escritório ainda (nenhuma leitura no ritmo), uma resposta aqui
# leva ~60 s (medido no 3B em CPU).
RESPOSTA_DO_ESCRITORIO_S = 60
# Só para o "~" do download da primeira vez: um palpite de rede, dito como tal.
BAIXAR_BYTES_POR_S = 8 * 1024 * 1024


def nome_do_modelo(estado) -> str:
    import aparelho_motor

    return str(aparelho_motor.modelo_escolhido(estado).get("nome") or "")


def espera_no_escritorio(estado) -> dict:
    """A fila do escritório agora, para quem chegasse: quantos na frente, a espera e uma resposta."""
    fila = estado.fila_modelo
    na_frente, espera = fila.espera_de_quem_chega()
    por_resposta = round(float(fila.segundos_por_resposta() or 0))
    return {"na_frente": na_frente, "espera_s": espera, "resposta_s": por_resposta or RESPOSTA_DO_ESCRITORIO_S,
            "sabe": bool(por_resposta)}


def acima_do_limite(escritorio: dict) -> bool:
    return escritorio["espera_s"] > LIMITE_ESPERA_S or escritorio["na_frente"] >= LIMITE_NA_FRENTE


def tempo_no_aparelho(capacidade: dict, *, carregado: bool, baixado: bool, bytes_do_modelo: int) -> int | None:
    """
    Segundos estimados para o aparelho escrever uma resposta típica, pela
    medida DELE (o teste de capacidade). None sem medida.
    """
    tps = float(capacidade.get("tokens_por_segundo") or 0)
    if tps <= 0:
        return None
    # Ler a pergunta costuma ser bem mais rápido que escrever; sem a medida
    # da leitura, 5 vezes a da escrita.
    leitura = float(capacidade.get("leitura_tps") or 0) or tps * 5
    t = TOKENS_DA_RESPOSTA / tps + TOKENS_DA_PERGUNTA / leitura
    if not carregado:
        t += float(capacidade.get("carregou_s") or 30)
    if not baixado:
        t += bytes_do_modelo / BAIXAR_BYTES_POR_S
    return max(1, round(t))


def decidir(escritorio: dict, aparelho_s: int | None) -> str:
    """O Automático: o aparelho só quando ele é mais rápido que a fila e o escritório, agora."""
    if aparelho_s is None:
        return "escritorio"
    return "aparelho" if aparelho_s < escritorio["espera_s"] + escritorio["resposta_s"] else "escritorio"


def escopo_so_no_escritorio(estado, apenas: list[str]) -> bool:
    """Os documentos em foco da pergunta tocam um caso "só no escritório"? (a busca livre só se sabe depois)."""
    if not apenas:
        return False
    nomes = set(apenas)
    caminhos = [str(d.path) for d in estado.searcher.documents if d.name in nomes]
    return so_no_escritorio().toca(estado, caminhos)


class Sugestao(BaseModel):
    """O que a tela sabe antes de mandar: o escopo e a medida deste aparelho (só números)."""

    model_config = ConfigDict(extra="forbid")
    apenas: list[str] = []
    inteiro: bool = False
    tokens_por_segundo: float | None = None
    leitura_tps: float | None = None
    carregou_s: float | None = None
    carregado: bool = False
    baixado: bool = False


# ------------------------------------------------------------- a porta

class Marca(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo: str
    valor: str | int


class Marcas(BaseModel):
    marcas: list[Marca] = []


class Devolver(BaseModel):
    assinatura: str
    texto: str = ""


class Abandonar(BaseModel):
    assinatura: str
    parcial: str = ""


class Pedaco(BaseModel):
    assinatura: str
    texto: str = ""


def _pacote_da_sessao(estado, pid: str, assinatura: str, request) -> dict:
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
    # D5: desligado (no escritório ou para a conta), nenhum pacote vale mais.
    pode, motivo = ainda_pode(estado, pessoa)
    if not pode:
        with _trava:
            if reg["estado"] in ("pronto", "entregue"):
                reg["estado"] = "desligado"
                reg["motivo"] = motivo
                reg["chegou"].set()
        raise HTTPException(status_code=410, detail=motivo)
    return reg


def montar(estado, app, dados_dir) -> None:
    _DADOS["dir"] = Path(dados_dir)

    @app.get("/api/aparelho/estado")
    def aparelho_estado(request: Request = None) -> dict:
        pode, motivo = pode_escrever(estado, request)
        import aparelho_motor

        m = aparelho_motor.modelo_escolhido(estado) if pode else {}
        return {"ligado": ligado(estado), "pode": pode, "motivo": motivo, "validade_s": VALIDADE_S,
                "modelo": m.get("nome", ""), "bytes": int(m.get("bytes") or 0)}

    # ---------------------------------------------- o titular (D5), só aqui
    def _so_local(request) -> None:
        from acesso import rotas as rotas_do_acesso

        rotas_do_acesso.so_local(request)

    @app.get("/api/aparelho/so-no-escritorio")
    def aparelho_so_no_escritorio(request: Request = None) -> dict:
        _so_local(request)
        servicos = [{"id": s["id"], "nome": s["nome"], "cliente": s.get("cliente_nome") or ""}
                    for s in estado.servicos.listar()]
        clientes = [{"id": c["id"], "nome": c["nome"]} for c in estado.cadastros.listar(tipo="cliente")]
        return {"marcas": so_no_escritorio().para_a_tela(estado), "servicos": servicos, "clientes": clientes}

    @app.put("/api/aparelho/so-no-escritorio")
    def aparelho_marcar(payload: Marcas, request: Request = None) -> dict:
        _so_local(request)
        limpas: list[dict] = []
        for m in payload.marcas:
            if m.tipo not in SoNoEscritorio.TIPOS:
                raise HTTPException(status_code=400, detail="tipo de marca desconhecido")
            if m.tipo == "pasta":
                p = Path(str(m.valor))
                p = p if p.is_absolute() else Path(estado.pasta) / p
                if not p.is_dir():
                    raise HTTPException(status_code=400, detail=f"a pasta {m.valor} não existe")
                valor = str(m.valor)
            else:
                try:
                    valor = int(m.valor)
                except (TypeError, ValueError):
                    raise HTTPException(status_code=400, detail="marca sem o número do Serviço ou do cliente") from None
                tabela = "servicos" if m.tipo == "servico" else "cadastros"
                if not estado.servicos.base.um(f"SELECT id FROM {tabela} WHERE id = ?", (valor,)):
                    raise HTTPException(status_code=400, detail=("esse Serviço" if m.tipo == "servico" else "esse cliente") + " não existe")
            if not any(x["tipo"] == m.tipo and str(x["valor"]) == str(valor) for x in limpas):
                limpas.append({"tipo": m.tipo, "valor": valor})
        antes = {(x.get("tipo"), str(x.get("valor"))) for x in so_no_escritorio().marcas()}
        so_no_escritorio().guardar(limpas)
        depois = so_no_escritorio().para_a_tela(estado)
        for m in depois:
            if (m["tipo"], str(m["valor"])) not in antes:
                auditar(estado, {"nome": "janela local"}, f"marcou só no escritório: {m['rotulo']}")
        for tipo, valor in sorted(antes - {(x["tipo"], str(x["valor"])) for x in limpas}):
            auditar(estado, {"nome": "janela local"}, f"tirou a marca só no escritório: {tipo} {valor}")
        return {"marcas": depois}

    @app.get("/api/aparelho/relatorio")
    def aparelho_relatorio(request: Request = None) -> dict:
        _so_local(request)
        return relatorio(estado)

    @app.post("/api/aparelho/sugestao")
    def aparelho_sugestao(payload: Sugestao, request: Request = None) -> dict:
        """
        Antes de a pergunta entrar na fila (D4): a fila do escritório agora, se
        a pergunta pode ir ao aparelho, a janela de sugestão e a escolha do
        Automático. Não guarda nada.
        """
        import aparelho_motor

        pode, motivo = pode_escrever(estado, request)
        escritorio = espera_no_escritorio(estado)
        so_aqui = escopo_so_no_escritorio(estado, payload.apenas)
        vai = pode and not so_aqui and not payload.inteiro
        m = aparelho_motor.modelo_escolhido(estado) if pode else {}
        aparelho_s = tempo_no_aparelho(payload.model_dump(), carregado=payload.carregado, baixado=payload.baixado,
                                       bytes_do_modelo=int(m.get("bytes") or 0)) if vai else None
        return {
            "pode": pode, "motivo": motivo,
            "vai_ao_aparelho": vai,
            "motivo_do_escritorio": ("a conversa está num caso marcado só no escritório" if so_aqui else
                                     "a pergunta pede o documento inteiro" if payload.inteiro and pode else motivo),
            "escritorio": escritorio,
            "acima_do_limite": acima_do_limite(escritorio),
            "sugerir": vai and acima_do_limite(escritorio),
            "aparelho_s": aparelho_s, "baixado": payload.baixado,
            "automatico": decidir(escritorio, aparelho_s) if vai else "escritorio",
            "modelo": {"nome": m.get("nome", ""), "bytes": int(m.get("bytes") or 0)} if pode else {},
        }

    @app.get("/api/aparelho/pacote/{pid}")
    def aparelho_pacote(pid: str, assinatura: str = "", request: Request = None) -> dict:
        reg = _pacote_da_sessao(estado, pid, assinatura, request)
        with _trava:
            if reg["estado"] != "pronto":
                raise HTTPException(status_code=409, detail="esse pacote já foi entregue")
            reg["estado"] = "entregue"
            reg["sinal"] = time.time()
        auditar(estado, reg["pessoa"], f"recebeu {len(reg['conteudo']['trechos'])} trecho(s) de "
                                       f"{', '.join(reg['documentos']) or 'nenhum documento'} para escrever "
                                       f"({reg['aparelho']})")
        return reg["conteudo"]

    @app.post("/api/aparelho/pacote/{pid}/devolver")
    def aparelho_devolver(pid: str, payload: Devolver, request: Request = None) -> dict:
        reg = _pacote_da_sessao(estado, pid, payload.assinatura, request)
        with _trava:
            if reg["estado"] != "entregue":
                raise HTTPException(status_code=409, detail="esse pacote já foi usado")
            reg["estado"] = "devolvido"
            reg["texto"] = str(payload.texto or "")[:20000]
            reg["chegou"].set()
        auditar(estado, reg["pessoa"], f"devolveu o texto ({len(reg['texto'])} caracteres, {reg['aparelho']})")
        return {"recebido": True}

    @app.post("/api/aparelho/pacote/{pid}/pedaco")
    def aparelho_pedaco(pid: str, payload: Pedaco, request: Request = None) -> dict:
        """O texto que o aparelho já escreveu (o inteiro até aqui): é dele que o escritório continua, se precisar."""
        reg = _pacote_da_sessao(estado, pid, payload.assinatura, request)
        with _trava:
            if reg["estado"] != "entregue":
                raise HTTPException(status_code=409, detail="esse pacote já foi usado")
            reg["parcial"] = str(payload.texto or "")[:20000]
            reg["sinal"] = time.time()
        return {"recebido": True}

    @app.post("/api/aparelho/pacote/{pid}/abandonar")
    def aparelho_abandonar(pid: str, payload: Abandonar, request: Request = None) -> dict:
        reg = _pacote_da_sessao(estado, pid, payload.assinatura, request)
        with _trava:
            if reg["estado"] not in ("pronto", "entregue"):
                raise HTTPException(status_code=409, detail="esse pacote já foi usado")
            reg["estado"] = "abandonado"
            reg["parcial"] = str(payload.parcial or "")[:20000]
            reg["chegou"].set()
        auditar(estado, reg["pessoa"], f"abandonou a escrita ({reg['aparelho']}); o escritório termina")
        return {"recebido": True}
