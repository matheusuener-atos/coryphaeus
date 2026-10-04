"""
O PAULUS dentro do Word (W1, docs/PROGRESSO-WORD.md): o pareamento, o token
do suplemento e a porta por onde o painel entra.

O painel é uma página que o Word carrega de um endereço HTTPS (montagem A:
https://localhost:<porta fixa>, servida por src/word_instalar.py; montagem C:
o endereço do acesso de fora). Ele não tem a chave da janela nem cookie - no
Word na web roda em moldura, e cookie de terceiros falha. Tem um **token só
dele**, que nasce assim:

  1. o painel pede um pareamento e recebe um código XXXX-XXXX;
  2. a pessoa confere o mesmo código e clica em Permitir: na janela do
     PAULUS, se o pedido veio deste computador; ou, se veio pelo túnel
     (montagem C), no PAULUS aberto de fora, com a sessão dela e o código do
     autenticador pedido de novo;
  3. o painel troca o pedido pelo token, uma vez. Aqui fica só o resumo.

O token tem o papel de quem permitiu: na janela local, o titular; de fora, a
conta da sessão, com as permissões dela relidas a cada pedido (a conta que
perde um módulo perde no Word na hora).

O que o token alcança é uma tabela própria, ROTAS, com padrão "nega": rota
de suplemento que não está ali responde 403, como no acesso de fora
(src/acesso/politicas.py). Cada chamada vai para a auditoria com a pessoa, a
ação, o nome do documento e quantos caracteres chegaram.

O texto do documento só vem para cá. A página do painel tem CSP: script só
dela e do office.js da Microsoft; conexão só com ela mesma.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

PREFIXO_TOKEN = "paulus_word_"
# Os arquivos do painel (paulus/legal/word). Só estes saem: a prova da W0 e
# os modelos ficam de fora.
PASTA_PAINEL = Path(__file__).resolve().parent.parent / "word"
ARQUIVOS = {"painel.html": "text/html; charset=utf-8", "painel.css": "text/css; charset=utf-8",
            "painel.js": "text/javascript; charset=utf-8"}
TIPOS_ICONE = {".png": "image/png"}

# O código que a pessoa confere: sem letra que se confunda (0/O, 1/I/L).
ALFABETO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
PEDIDO_VALE_S = 10 * 60
PEDIDOS_ABERTOS = 20
PEDIDOS_POR_ORIGEM = 10        # por endereço, a cada 10 min
LIMITE_DO_PEDIDO = 8 * 1024 * 1024   # documento grande vem em partes (W2)

# As rotas do pareamento, que passam sem token (o painel ainda não tem um).
PAREAR = {("POST", "/api/word/parear"), ("POST", "/api/word/parear/trocar"), ("POST", "/api/word/carregou")}
PREFIXO_SUPLEMENTO = "/api/word/s/"

# Office na web: o painel abre em moldura dentro destes endereços.
MOLDURAS_DO_OFFICE = ("https://*.officeapps.live.com", "https://*.office.com", "https://*.office365.com",
                      "https://*.microsoft365.com", "https://*.cloud.microsoft", "https://*.sharepoint.com",
                      "https://*.officeonline.com")
OFFICE_JS = "https://appsforoffice.microsoft.com"


def politica_do_painel() -> str:
    """A CSP do painel: script daqui e do office.js; conexão só com daqui."""
    return ("default-src 'self'; "
            f"script-src 'self' {OFFICE_JS}; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; "
            "connect-src 'self'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; "
            f"frame-ancestors 'self' {' '.join(MOLDURAS_DO_OFFICE)}")


# ------------------------------------------------------------ a política

# (método, caminho da rota no app) -> o que precisa: papel ("titular" ou
# None), e o módulo e o nível (src/acesso/permissoes.py) para as contas de
# fora. Rota de suplemento fora daqui: 403.
ROTAS: dict[tuple[str, str], dict] = {}


def declarar(rota: str, *, papel: str | None = None, modulo: str | None = None, nivel: str = "ver") -> None:
    metodo, caminho = rota.split(" ", 1)
    if not caminho.startswith(PREFIXO_SUPLEMENTO):
        raise ValueError(f"rota do suplemento fora de {PREFIXO_SUPLEMENTO}: {rota}")
    ROTAS[(metodo, caminho)] = {"papel": papel, "modulo": modulo, "nivel": nivel}


# W1: quem sou, minhas preferências e desconectar este Word.
declarar("GET /api/word/s/eu")
declarar("PUT /api/word/s/preferencias")
declarar("DELETE /api/word/s/eu")


def permitido(conexao: dict, pessoa: dict | None, metodo: str, caminho_da_rota: str | None) -> tuple[bool, str]:
    """(passa, motivo) para esta conexão nesta rota."""
    from acesso import permissoes

    regra = ROTAS.get(("GET" if metodo == "HEAD" else metodo, caminho_da_rota or ""))
    if regra is None:
        return False, "o suplemento do Word não alcança isso"
    papel = (pessoa or {}).get("papel") or conexao.get("papel") or ""
    if regra["papel"] == "titular" and papel != "titular":
        return False, "só o titular pode fazer isso"
    if regra["modulo"] and pessoa:
        niveis = pessoa.get("permissoes") or {}
        modulo = permissoes.POR_ID.get(regra["modulo"])
        tem = niveis.get(regra["modulo"], modulo["padrao"] if modulo else permissoes.NAO)
        if permissoes.ORDEM.index(tem) < permissoes.ORDEM.index(regra["nivel"]):
            rotulo = modulo["rotulo"] if modulo else regra["modulo"]
            return False, f"você não tem acesso a {rotulo} pelo Word; o titular libera em Configurações › Acesso de fora"
    return True, ""


# ------------------------------------------------------------ guardados

def _resumo(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Conexoes:
    """Os Words pareados: quem, de onde, e o resumo do token (nunca o token)."""

    def __init__(self, pasta: Path) -> None:
        self.caminho = Path(pasta) / "word" / "conexoes.json"
        self._trava = threading.Lock()

    def _ler(self) -> list[dict]:
        try:
            return json.loads(self.caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def _gravar(self, itens: list[dict]) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.write_text(json.dumps(itens, ensure_ascii=False, indent=1), encoding="utf-8")

    def listar(self) -> list[dict]:
        return [{k: v for k, v in c.items() if k != "resumo"} for c in self._ler()]

    def criar(self, *, pessoa: str, email: str, papel: str, conta_id: int, origem: str, word: str) -> tuple[dict, str]:
        token = PREFIXO_TOKEN + secrets.token_urlsafe(32)
        conexao = {"id": uuid.uuid4().hex[:10], "pessoa": pessoa, "email": email, "papel": papel,
                   "conta_id": int(conta_id), "origem": origem, "word": word[:80], "resumo": _resumo(token),
                   "criada_em": datetime.now().strftime("%Y-%m-%d %H:%M"), "ultimo_uso": "", "chamadas": 0,
                   "preferencias": {"controlada": True}}
        with self._trava:
            itens = self._ler()
            itens.append(conexao)
            self._gravar(itens)
        return {k: v for k, v in conexao.items() if k != "resumo"}, token

    def revogar(self, id_: str) -> dict | None:
        with self._trava:
            itens = self._ler()
            fora = next((c for c in itens if c["id"] == id_), None)
            if fora:
                self._gravar([c for c in itens if c["id"] != id_])
        return fora

    def do_token(self, token: str | None) -> dict | None:
        if not token or not token.startswith(PREFIXO_TOKEN):
            return None
        procurado = _resumo(token)
        achada = None
        # compare_digest com todas: o tempo não diz qual chegou perto.
        for c in self._ler():
            if hmac.compare_digest(procurado, c.get("resumo", "")):
                achada = c
        return achada

    def anotar_uso(self, id_: str) -> None:
        with self._trava:
            itens = self._ler()
            for c in itens:
                if c["id"] == id_:
                    c["ultimo_uso"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    c["chamadas"] = int(c.get("chamadas") or 0) + 1
            self._gravar(itens)

    def preferir(self, id_: str, mudancas: dict) -> dict:
        with self._trava:
            itens = self._ler()
            for c in itens:
                if c["id"] == id_:
                    c["preferencias"] = {**(c.get("preferencias") or {}), **mudancas}
                    self._gravar(itens)
                    return dict(c["preferencias"])
        return {}


class Pedidos:
    """Os pareamentos esperando o Permitir. Só na memória: fechar o PAULUS os cancela."""

    def __init__(self, relogio=time.time) -> None:
        self.relogio = relogio
        self._itens: dict[str, dict] = {}
        self._por_origem: dict[str, list[float]] = {}
        self._trava = threading.Lock()

    def _limpar(self) -> None:
        agora = self.relogio()
        for k in [k for k, p in self._itens.items() if agora - p["criado"] > PEDIDO_VALE_S]:
            del self._itens[k]

    def abrir(self, *, origem: str, endereco: str, word: str) -> dict:
        with self._trava:
            self._limpar()
            agora = self.relogio()
            recentes = [t for t in self._por_origem.get(endereco, []) if agora - t < PEDIDO_VALE_S]
            if len(recentes) >= PEDIDOS_POR_ORIGEM or len(self._itens) >= PEDIDOS_ABERTOS:
                raise PermissionError("pedidos demais; espere alguns minutos")
            self._por_origem[endereco] = recentes + [agora]
            codigo = "".join(secrets.choice(ALFABETO) for _ in range(8))
            codigo = codigo[:4] + "-" + codigo[4:]
            segredo = secrets.token_urlsafe(24)
            pedido = {"id": uuid.uuid4().hex[:12], "codigo": codigo, "segredo": _resumo(segredo), "origem": origem,
                      "word": word[:80], "criado": agora, "estado": "esperando", "conexao": None, "token": None}
            self._itens[pedido["id"]] = pedido
        return {**pedido, "segredo": segredo}

    def abertos(self, origem: str | None = None) -> list[dict]:
        with self._trava:
            self._limpar()
            return [{"id": p["id"], "codigo": p["codigo"], "origem": p["origem"], "word": p["word"],
                     "ha_s": int(self.relogio() - p["criado"])}
                    for p in self._itens.values() if p["estado"] == "esperando" and (origem is None or p["origem"] == origem)]

    def obter(self, id_: str) -> dict | None:
        with self._trava:
            self._limpar()
            return self._itens.get(id_)

    def do_codigo(self, codigo: str, origem: str) -> dict | None:
        limpo = "".join(ch for ch in str(codigo or "").upper() if ch in ALFABETO)
        if len(limpo) != 8:
            return None
        procurado = limpo[:4] + "-" + limpo[4:]
        with self._trava:
            self._limpar()
            for p in self._itens.values():
                if p["estado"] == "esperando" and p["origem"] == origem and hmac.compare_digest(p["codigo"], procurado):
                    return p
        return None

    def decidir(self, id_: str, *, conexao: dict | None, token: str | None) -> bool:
        with self._trava:
            p = self._itens.get(id_)
            if not p or p["estado"] != "esperando":
                return False
            p["estado"] = "permitido" if conexao else "recusado"
            p["conexao"], p["token"] = conexao, token
            return True

    def trocar(self, id_: str, segredo: str) -> dict:
        """{"estado": esperando|permitido|recusado|vencido} e, uma vez só, o token."""
        with self._trava:
            self._limpar()
            p = self._itens.get(id_)
            if not p or not hmac.compare_digest(p["segredo"], _resumo(str(segredo or ""))):
                return {"estado": "vencido"}
            if p["estado"] == "esperando":
                return {"estado": "esperando"}
            del self._itens[id_]
            if p["estado"] == "recusado":
                return {"estado": "recusado"}
            return {"estado": "permitido", "token": p["token"], "conexao": p["conexao"]}


# ------------------------------------------------------------ a porta

def _veio_pelo_tunel(scope, cab: dict) -> bool:
    cliente = (scope.get("client") or ("", 0))[0]
    return cliente not in ("127.0.0.1", "::1") or any(k.startswith("cf-") for k in cab) or "x-forwarded-for" in cab


class PortaDoWord:
    """
    Por onde o painel entra: os arquivos do painel, o pareamento e as rotas
    /api/word/s/* com o token. O porteiro (src/acesso/porteiro.py) entrega
    aqui antes da chave da janela, como faz com o /mcp.

    Na porta HTTPS do Word (montagem A) só passa o que é do Word e as fontes;
    o resto do PAULUS não abre por ela.
    """

    def __init__(self, *, conexoes: Conexoes, pedidos: Pedidos, ligado, porta_https, contas=None,
                 acesso_ligado=None, registrar=None) -> None:
        self.conexoes = conexoes
        self.pedidos = pedidos
        self.ligado = ligado
        self.porta_https = porta_https       # () -> int (0 = sem porta)
        self.contas = contas                 # as contas do acesso de fora
        self.acesso_ligado = acesso_ligado or (lambda: False)
        self.registrar = registrar
        self.rotas = None                    # o roteador do app (para casar a rota)
        self.app = None                      # o app de dentro do porteiro

    def _anotar(self, **evento) -> None:
        if self.registrar:
            try:
                self.registrar(**evento)
            except Exception:  # noqa: BLE001 - a auditoria não derruba o pedido
                pass

    def atende(self, scope) -> bool:
        caminho = scope.get("path", "")
        if caminho.startswith("/word/") or caminho.startswith(PREFIXO_SUPLEMENTO):
            return True
        if (scope.get("method", "GET"), caminho) in PAREAR:
            return True
        porta = (scope.get("server") or ("", 0))[1]
        return bool(porta) and porta == self.porta_https()

    async def __call__(self, app, scope, receive, send, cab: dict) -> None:
        from acesso.porteiro import PESSOA_DA_VEZ, recusar

        caminho = scope.get("path", "")
        metodo = scope.get("method", "GET")
        if scope.get("type") != "http" or not self.ligado():
            await recusar(scope, send, 404, "o suplemento do Word está desligado")
            return
        tunel = _veio_pelo_tunel(scope, cab)
        if tunel and not self.acesso_ligado():
            await recusar(scope, send, 403, "o acesso de fora está desligado")
            return
        if caminho.startswith("/word/"):
            await self._arquivo(scope, send, caminho[len("/word/"):])
            return
        if (metodo, caminho) in PAREAR:
            scope.setdefault("state", {})["paulus_word_origem"] = "fora" if tunel else "local"
            scope["state"]["paulus_word_endereco"] = cab.get("cf-connecting-ip") or (scope.get("client") or ("", 0))[0]
            await app(scope, receive, send)
            return
        if caminho.startswith(PREFIXO_SUPLEMENTO):
            await self._suplemento(app, scope, receive, send, cab, tunel)
            return
        # A porta HTTPS do Word: fora o que é do Word, só as fontes do painel.
        if metodo == "GET" and (caminho == "/fontes.css" or caminho.startswith("/fontes/")):
            await app(scope, receive, send)
            return
        PESSOA_DA_VEZ.set(None)
        await recusar(scope, send, 404, "esta porta é só do suplemento do Word")

    async def _arquivo(self, scope, send, nome: str) -> None:
        from acesso.porteiro import recusar, responder

        if scope.get("method") not in ("GET", "HEAD"):
            await recusar(scope, send, 405)
            return
        if nome in ARQUIVOS:
            arquivo, tipo = PASTA_PAINEL / nome, ARQUIVOS[nome]
        elif nome.startswith("icones/") and "/" not in nome[len("icones/"):] and Path(nome).suffix in TIPOS_ICONE:
            arquivo, tipo = PASTA_PAINEL / "icones" / Path(nome).name, TIPOS_ICONE[Path(nome).suffix]
        else:
            await recusar(scope, send, 404, "não encontrado")
            return
        try:
            corpo = arquivo.read_bytes()
        except OSError:
            await recusar(scope, send, 404, "não encontrado")
            return
        extra = [(b"x-content-type-options", b"nosniff"), (b"referrer-policy", b"no-referrer")]
        if nome == "painel.html":
            extra.append((b"content-security-policy", politica_do_painel().encode("latin-1")))
        if nome.startswith("icones/"):
            # O Office guarda os ícones da faixa no disco: com "no-store" (o
            # padrão das respostas daqui) ele não os mostra. Ícone não tem dado.
            await send({"type": "http.response.start", "status": 200,
                        "headers": [(b"content-type", tipo.encode()), (b"cache-control", b"public, max-age=86400"),
                                    (b"content-length", str(len(corpo)).encode())] + extra})
            await send({"type": "http.response.body", "body": corpo})
            return
        await responder(send, 200, corpo, tipo, extra)

    async def _suplemento(self, app, scope, receive, send, cab, tunel: bool) -> None:
        from acesso import politicas
        from acesso.porteiro import PESSOA_DA_VEZ, recusar

        metodo = scope.get("method", "GET")
        ip = cab.get("cf-connecting-ip") or (scope.get("client") or ("", 0))[0]
        autorizacao = cab.get("authorization", "")
        conexao = self.conexoes.do_token(autorizacao[7:].strip() if autorizacao.lower().startswith("bearer ") else "")
        if conexao is None:
            await recusar(scope, send, 401, "conecte este Word ao PAULUS de novo")
            return
        # Token do Word deste computador não vale pelo túnel: se vazar, não
        # abre o escritório de fora.
        if tunel and conexao.get("origem") != "fora":
            await recusar(scope, send, 401, "esta conexão do Word vale só neste computador")
            return
        pessoa = None
        if conexao.get("origem") == "fora":
            conta = self.contas.obter(int(conexao.get("conta_id") or 0)) if self.contas else None
            if not conta:
                await recusar(scope, send, 401, "a conta desta conexão não existe mais")
                return
            from acesso import permissoes

            pessoa = {"conta_id": conta["id"], "nome": conta.get("nome", ""), "email": conta.get("email", ""),
                      "papel": conta.get("papel", ""), "csrf": "", "hash": "", "totp_em": 0, "criada": 0,
                      "permissoes": permissoes.efetivas(conta.get("papel", ""), conta.get("permissoes"))}
        rota = politicas.rota_de(self.rotas or app, scope)
        passa, motivo = permitido(conexao, pessoa, metodo, getattr(rota, "path", None))
        documento = unquote(cab.get("x-paulus-documento", ""))[:200]
        quem = (pessoa or {}).get("nome") or conexao.get("pessoa") or ""
        email = (pessoa or {}).get("email") or conexao.get("email") or ""
        if not passa:
            self._anotar(acao="word_recusado", alvo=f"{metodo} {scope.get('path', '')}" + (f" · {documento}" if documento else ""),
                         pessoa=quem, email=email, ip=ip)
            await recusar(scope, send, 403, motivo)
            return

        estado = scope.setdefault("state", {})
        estado["paulus_local"] = conexao.get("origem") != "fora"
        estado["paulus_pessoa"] = pessoa
        estado["paulus_word"] = conexao
        PESSOA_DA_VEZ.set(pessoa)

        lidos = 0
        grande = False

        async def receber():
            nonlocal lidos, grande
            m = await receive()
            corpo = m.get("body", b"") or b""
            lidos += len(corpo.decode("utf-8", "replace")) if corpo else 0
            if lidos > LIMITE_DO_PEDIDO:
                grande = True
            return m

        status = {"codigo": 0}

        async def enviar(m):
            if m.get("type") == "http.response.start":
                status["codigo"] = m.get("status", 0)
            await send(m)

        try:
            await app(scope, receber, enviar)
        finally:
            self.conexoes.anotar_uso(conexao["id"])
            alvo = f"{metodo} {getattr(rota, 'path', scope.get('path', ''))}"
            if documento:
                alvo += f" · {documento}"
            alvo += f" · {lidos} caracteres"
            if grande:
                alvo += " (acima do limite)"
            self._anotar(acao="word", alvo=alvo, pessoa=quem, email=email, ip=ip)


# ------------------------------------------------------------ rotas

from fastapi import HTTPException, Request  # noqa: E402
from pydantic import BaseModel  # noqa: E402


# Os corpos das rotas: no nível do módulo, porque com as anotações adiadas o
# FastAPI não acha classe definida dentro de montar() e a trata como
# parâmetro de consulta.
class Parear(BaseModel):
    word: str = ""


class Trocar(BaseModel):
    pedido: str
    segredo: str


class Carregou(BaseModel):
    word: str = ""
    plataforma: str = ""
    conjuntos: dict = {}
    montagem: str = ""
    violacoes: list = []


class PermitirDeFora(BaseModel):
    codigo: str
    codigo_autenticador: str = ""


class Preferencias(BaseModel):
    controlada: bool | None = None


class Ligar(BaseModel):
    ligado: bool


class Externo(BaseModel):
    acao: str
    caminho: str = ""


class Atalhos(BaseModel):
    area_de_trabalho: bool = False
    menu_iniciar: bool = False
    botao_direito: bool = False


def montar(estado, app, pasta_dados: Path) -> None:
    """As rotas do Word. As de /api/word/s/* só chegam com token (PortaDoWord)."""
    from acesso.rotas import e_local, so_local

    import word_instalar

    estado.word_conexoes = Conexoes(pasta_dados)
    estado.word_pedidos = Pedidos()
    estado.word_carregamentos = []
    instalacao = word_instalar.Instalacao(estado, pasta_dados)
    estado.word_instalacao = instalacao

    def _anotar(**evento) -> None:
        try:
            estado.acesso_de_fora.auditoria.registrar(**evento)
        except Exception:  # noqa: BLE001
            pass

    def _nome_local() -> str:
        nome = str((estado.prefs.dados.get("pessoa") or {}).get("nome") or "").strip()
        return nome or "Janela do escritório"

    def _ligado() -> bool:
        import recursos_do_plano

        # Ligado e do plano (src/recursos_do_plano.py): sem ele, o painel do Word fica fechado.
        return bool((estado.prefs.dados.get("word") or {}).get("ligado")) and recursos_do_plano.pode(estado, "word")

    # --- o painel, sem token

    @app.post("/api/word/parear")
    def word_parear(payload: Parear, request: Request) -> dict:
        st = request.scope.get("state", {})
        origem = st.get("paulus_word_origem")
        if not origem:
            # Só pela PortaDoWord, que marca de onde veio.
            raise HTTPException(status_code=403, detail="pareamento só pelo painel do Word")
        try:
            p = estado.word_pedidos.abrir(origem=origem, endereco=str(st.get("paulus_word_endereco") or ""), word=payload.word)
        except PermissionError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        return {"pedido": p["id"], "codigo": p["codigo"], "segredo": p["segredo"], "origem": origem,
                "vale_s": PEDIDO_VALE_S}

    @app.post("/api/word/parear/trocar")
    def word_trocar(payload: Trocar) -> dict:
        r = estado.word_pedidos.trocar(payload.pedido, payload.segredo)
        if r["estado"] == "permitido":
            c = r["conexao"]
            return {"estado": "permitido", "token": r["token"], "pessoa": c["pessoa"], "papel": c["papel"]}
        return {"estado": r["estado"]}

    @app.post("/api/word/carregou")
    def word_carregou(payload: Carregou, request: Request) -> dict:
        """O painel abriu num Word: é o que a tela usa para dizer "instalado" (W1)."""
        st = request.scope.get("state", {})
        registro = {"quando": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "word": payload.word[:60],
                    "plataforma": payload.plataforma[:20], "origem": st.get("paulus_word_origem") or "",
                    "montagem": payload.montagem[:4],
                    "conjuntos": {k: bool(v) for k, v in list(payload.conjuntos.items())[:40]},
                    "violacoes": [str(v)[:200] for v in payload.violacoes[:10]]}
        estado.word_carregamentos = (estado.word_carregamentos + [registro])[-20:]
        instalacao.anotar_carregamento(registro)
        return {"ok": True}

    # --- o painel, com token (PortaDoWord conferiu o token e a ROTAS)

    @app.get("/api/word/s/eu")
    def word_eu(request: Request) -> dict:
        c = request.scope["state"]["paulus_word"]
        pessoa = request.scope["state"].get("paulus_pessoa")
        return {"pessoa": (pessoa or {}).get("nome") or c["pessoa"], "papel": (pessoa or {}).get("papel") or c["papel"],
                "origem": c["origem"], "preferencias": c.get("preferencias") or {"controlada": True},
                "documento": None}

    @app.put("/api/word/s/preferencias")
    def word_preferir(payload: Preferencias, request: Request) -> dict:
        c = request.scope["state"]["paulus_word"]
        mudancas = {k: v for k, v in payload.model_dump().items() if v is not None}
        return {"preferencias": estado.word_conexoes.preferir(c["id"], mudancas)}

    @app.delete("/api/word/s/eu")
    def word_desconectar(request: Request) -> dict:
        c = request.scope["state"]["paulus_word"]
        estado.word_conexoes.revogar(c["id"])
        _anotar(acao="word_revogado", alvo=f"desconectado no próprio Word: {c['word'] or c['id']}",
                pessoa=c["pessoa"], email=c.get("email", ""))
        return {"ok": True}

    # --- de fora (montagem C): a pessoa permite com a sessão e o autenticador

    @app.post("/api/word/permitir-de-fora")
    def word_permitir_de_fora(payload: PermitirDeFora, request: Request) -> dict:
        from acesso import rotas as rotas_do_acesso

        sessao = rotas_do_acesso.pessoa(request)
        if not sessao:
            raise HTTPException(status_code=403, detail="entre no PAULUS de fora, com a sua conta, para conectar o Word")
        if not _ligado():
            raise HTTPException(status_code=409, detail="o suplemento do Word está desligado no escritório")
        if not estado.acesso_de_fora.contas.confirmar_de_novo(sessao, payload.codigo_autenticador):
            raise HTTPException(status_code=403, detail="código do autenticador errado")
        p = estado.word_pedidos.do_codigo(payload.codigo, "fora")
        if not p:
            raise HTTPException(status_code=404, detail="não achei esse código; confira no painel do Word (ele vale 10 minutos)")
        conexao, token = estado.word_conexoes.criar(pessoa=sessao["nome"], email=sessao["email"], papel=sessao["papel"],
                                                    conta_id=int(sessao["conta_id"]), origem="fora", word=p["word"])
        estado.word_pedidos.decidir(p["id"], conexao=conexao, token=token)
        _anotar(acao="word_pareado", alvo=f"Word de fora: {p['word'] or 'sem versão'}", pessoa=sessao["nome"],
                email=sessao["email"], ip=(getattr(request, "client", None) or ("", 0))[0])
        return {"ok": True}

    # --- a janela do escritório

    def _situacao() -> dict:
        import os

        sit = instalacao.situacao()
        # A novidade do Editor (js/76-word.js): com Word aqui e o PAVLVS ainda
        # não instalado. PAULUS_SEM_AVISOS (servidor de teste) não a mostra,
        # como não mostra os outros avisos (src/avisos.py).
        # Instalado mas sem nunca ter aberto no Word (a 0.9.23 só registrava, e
        # no Word 2021 isso não mostra a aba): a novidade volta, para abrir.
        novidade = (sit["word_no_computador"] and not sit["carregado"]
                    and not os.environ.get("PAULUS_SEM_AVISOS"))
        tipo = "abrir" if (_ligado() and sit["instalado"]) else "ativar"
        return {"ligado": _ligado(), "instalacao": sit, "novidade": bool(novidade), "novidade_tipo": tipo,
                "conexoes": estado.word_conexoes.listar(),
                "pedidos": estado.word_pedidos.abertos("local"),
                "carregamentos": list(reversed(estado.word_carregamentos[-5:]))}

    @app.get("/api/word")
    def word_situacao(request: Request) -> dict:
        so_local(request)
        return _situacao()

    @app.get("/api/word/pedidos")
    def word_pedidos(request: Request) -> dict:
        """Só os pedidos deste computador: a casca pergunta a cada poucos segundos."""
        if not e_local(request) or not _ligado():
            return {"pedidos": []}
        return {"pedidos": estado.word_pedidos.abertos("local")}

    @app.post("/api/word/ligar")
    def word_ligar(payload: Ligar, request: Request) -> dict:
        so_local(request)
        if payload.ligado:
            import recursos_do_plano

            recursos_do_plano.exigir(estado, "word")
        estado.prefs.atualizar({"word": {"ligado": bool(payload.ligado)}})
        instalacao.aplicar()
        return _situacao()

    @app.post("/api/word/instalar")
    def word_instalar_rota(request: Request) -> dict:
        so_local(request)
        if not _ligado():
            raise HTTPException(status_code=409, detail="ligue o suplemento do Word primeiro")
        try:
            passos = instalacao.instalar()
        except word_instalar.FalhaNaInstalacao as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        _anotar(acao="word_instalado", alvo="; ".join(f"{p['passo']}: {p['resultado']}" for p in passos),
                pessoa=_nome_local())
        return {**_situacao(), "passos": passos}

    @app.post("/api/word/desinstalar")
    def word_desinstalar(request: Request) -> dict:
        so_local(request)
        instalacao.desinstalar()
        _anotar(acao="word_instalado", alvo="tirado do Word deste computador", pessoa=_nome_local())
        return _situacao()

    @app.get("/api/word/manifesto")
    def word_manifesto(request: Request, montagem: str = "local"):
        from fastapi.responses import Response

        so_local(request)
        try:
            xml = instalacao.manifesto(montagem)
        except word_instalar.FalhaNaInstalacao as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        nome = "PAVLVS-word" + ("-de-fora" if montagem == "fora" else "") + ".xml"
        return Response(xml, media_type="application/xml",
                        headers={"Content-Disposition": f'attachment; filename="{nome}"'})

    def _abrir_no_windows(caminho: Path) -> None:
        import os

        os.startfile(str(caminho))  # noqa: S606 - abre no Word do próprio Windows

    estado.word_abrir_no_windows = _abrir_no_windows

    @app.get("/api/word/word-aberto")
    def word_aberto(request: Request) -> dict:
        """O Word está aberto desde antes da instalação? (aí ele não conhece o PAVLVS)."""
        so_local(request)
        return {"precisa_fechar": instalacao.precisa_fechar_o_word()}

    @app.post("/api/word/abrir")
    def word_abrir(request: Request) -> dict:
        """Abre o Word com o PAVLVS: o documento "comece aqui", com a aba e o painel."""
        so_local(request)
        if not instalacao.instalado():
            raise HTTPException(status_code=409, detail="ative o PAVLVS no Word primeiro")
        if instalacao.precisa_fechar_o_word():
            return {"aberto": False, "precisa_fechar": True}
        try:
            estado.word_abrir_no_windows(instalacao.comece_aqui())
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"não consegui abrir o Word: {exc}") from exc
        return {"aberto": True, "precisa_fechar": False}

    def _avisar_no_windows(titulo: str, texto: str) -> None:
        import os

        if os.environ.get("PAULUS_SEM_AVISOS"):
            return
        try:
            import avisos

            avisos.notificar(titulo, texto)
        except Exception:  # noqa: BLE001 - sem o aviso, o Word abre do mesmo jeito quando fechar
            pass

    esperando = {"fio": None}

    def _quando_o_word_fechar(abrir) -> None:
        """Um Word aberto antes da instalação: espera ele fechar (até 15 min) e abre."""
        if esperando["fio"] is not None and esperando["fio"].is_alive():
            return

        def esperar() -> None:
            fim = time.time() + 15 * 60
            while time.time() < fim:
                if not instalacao.precisa_fechar_o_word():
                    try:
                        abrir()
                    except OSError:
                        pass
                    return
                time.sleep(2)

        esperando["fio"] = threading.Thread(target=esperar, name="word-esperando-fechar", daemon=True)
        esperando["fio"].start()

    def word_externo(acao: str, caminho: str = "") -> dict:
        """
        O atalho "Word com PAVLVS" (`novo`) e o botão direito dos .docx
        (`abrir`): o PAULUS.exe chama aqui (src/desktop.py).
        """
        if not instalacao.instalado():
            _avisar_no_windows("PAVLVS no Word", "Ative o PAVLVS no PAULUS, em Configurações › Word, para abrir o Word com ele.")
            return {"aberto": False, "motivo": "não instalado"}
        if acao == "abrir":
            arquivo = Path(caminho)
            try:
                resultado = instalacao.por_no_arquivo(arquivo)
            except (word_instalar.FalhaNaInstalacao, OSError) as exc:
                return {"aberto": False, "motivo": str(exc)}

            def abrir() -> None:
                estado.word_abrir_no_windows(arquivo)
        else:
            resultado = "novo"

            def abrir() -> None:
                estado.word_abrir_no_windows(instalacao.modelo_novo())
        if instalacao.precisa_fechar_o_word():
            _avisar_no_windows("Feche o Word para usar o PAVLVS",
                               "O Word está aberto desde antes de o PAVLVS ser instalado. Salve e feche o Word: "
                               "assim que ele fechar, o PAULUS abre de novo com o PAVLVS.")
            _quando_o_word_fechar(abrir)
            return {"aberto": False, "esperando": True, "resultado": resultado}
        abrir()
        return {"aberto": True, "resultado": resultado}

    estado.word_externo = word_externo

    @app.post("/api/word/externo")
    def word_externo_rota(payload: Externo, request: Request) -> dict:
        so_local(request)
        if payload.acao not in ("novo", "abrir"):
            raise HTTPException(status_code=400, detail="ação desconhecida")
        return word_externo(payload.acao, payload.caminho)

    @app.post("/api/word/atalhos")
    def word_atalhos(payload: Atalhos, request: Request) -> dict:
        so_local(request)
        if not instalacao.instalado():
            raise HTTPException(status_code=409, detail="ative o PAVLVS no Word primeiro")
        try:
            feitos = instalacao.criar_atalhos(area_de_trabalho=payload.area_de_trabalho, menu_iniciar=payload.menu_iniciar,
                                              botao_direito=payload.botao_direito)
        except OSError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {**_situacao(), "feitos": feitos}

    @app.post("/api/word/abrir-pasta")
    def word_abrir_pasta(request: Request) -> dict:
        """
        Grava os manifestos (o deste computador e, com o acesso de fora, o de
        fora) na pasta do Word e a abre no Explorer: na janela do programa o
        download do navegador não funciona (js/02-casca.js).
        """
        import os

        so_local(request)
        gravados = []
        for montagem, nome in (("local", "PAVLVS-word.xml"), ("fora", "PAVLVS-word-de-fora.xml")):
            try:
                xml = instalacao.manifesto(montagem)
            except word_instalar.FalhaNaInstalacao:
                continue
            instalacao.pasta.mkdir(parents=True, exist_ok=True)
            (instalacao.pasta / nome).write_text(xml, encoding="utf-8")
            gravados.append(nome)
        if not gravados:
            raise HTTPException(status_code=409, detail="instale no Word deste computador primeiro")
        try:
            os.startfile(str(instalacao.pasta))  # noqa: S606 - abre o gerenciador do próprio Windows
        except OSError:
            pass
        return {"pasta": str(instalacao.pasta), "arquivos": gravados}

    @app.post("/api/word/pedidos/{id_}/permitir")
    def word_permitir(id_: str, request: Request) -> dict:
        so_local(request)
        p = estado.word_pedidos.obter(id_)
        if not p or p["estado"] != "esperando":
            raise HTTPException(status_code=404, detail="esse pedido não existe mais (vale 10 minutos)")
        if p["origem"] != "local":
            raise HTTPException(status_code=403, detail="pedido de outro computador: quem conecta é a pessoa, no PAULUS de fora, com o autenticador")
        conexao, token = estado.word_conexoes.criar(pessoa=_nome_local(), email="", papel="titular", conta_id=0,
                                                    origem="local", word=p["word"])
        estado.word_pedidos.decidir(id_, conexao=conexao, token=token)
        _anotar(acao="word_pareado", alvo=f"Word deste computador: {p['word'] or 'sem versão'}", pessoa=_nome_local())
        return _situacao()

    @app.post("/api/word/pedidos/{id_}/recusar")
    def word_recusar(id_: str, request: Request) -> dict:
        so_local(request)
        estado.word_pedidos.decidir(id_, conexao=None, token=None)
        return _situacao()

    @app.delete("/api/word/conexoes/{id_}")
    def word_revogar(id_: str, request: Request) -> dict:
        so_local(request)
        fora = estado.word_conexoes.revogar(id_)
        if not fora:
            raise HTTPException(status_code=404, detail="essa conexão não existe mais")
        _anotar(acao="word_revogado", alvo=f"revogado na janela: {fora['pessoa']} · {fora['word'] or fora['id']}",
                pessoa=_nome_local())
        return _situacao()

    porta = PortaDoWord(conexoes=estado.word_conexoes, pedidos=estado.word_pedidos, ligado=_ligado,
                        porta_https=instalacao.porta_aberta, contas=estado.acesso_de_fora.contas,
                        acesso_ligado=lambda: estado.acesso_de_fora.ligado(), registrar=_anotar)
    porta.rotas = app.router
    estado.word = porta
