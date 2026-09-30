"""
O servidor MCP das leis (ideia A do umbrelOS, docs/DECISAO-UMBREL.md).

O advogado já usa outros assistentes (Claude, ChatGPT...). Eles não
enxergavam o que o PAULUS tem, e inventavam artigo de lei que o PAULUS sabe
citar certo. Pelo MCP (Model Context Protocol, JSON-RPC 2.0), o assistente de
fora pede ao PAULUS o texto do artigo - e recebe o texto compilado do
Planalto, com o revogado marcado e o ano da última alteração.

**Só as leis, e por quê.** O que o PAULUS devolve aqui vai para o modelo de
outra empresa. Texto de lei é público (Lei 9.610, art. 8º, IV); o resto -
biblioteca do escritório, documentos de cliente, cartão, prazos - não sai por
aqui. Estender a outras ferramentas é decisão do dono, conexão por conexão
(docs/DECISAO-UMBREL.md).

As travas:

- **desligado de fábrica** (`umbrel.mcp`);
- **só deste computador:** o pedido tem de vir do 127.0.0.1 e sem os
  cabeçalhos da Cloudflare - o túnel do acesso de fora também chega pelo
  127.0.0.1, e por ele nunca;
- **um token por conexão**, criado e revogado só na janela do escritório; o
  token aparece uma vez, na hora de criar, e o que fica guardado é só o
  resumo SHA-256 (como senha: quem abrir o arquivo não tem o token);
- **cada conexão tem a sua lista de ferramentas**; fora dela, negado;
- **toda chamada vai para a auditoria** (a mesma de "quem acessou").
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
import uuid
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

PROTOCOLO = "2025-06-18"
LIMITE_DO_PEDIDO = 64 * 1024

FERRAMENTAS = {
    "leis_instaladas": {
        "description": "Lista os códigos de lei guardados neste PAULUS (texto compilado do Planalto), com a data de "
                       "importação. Use antes de citar, para saber o que dá para conferir.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "citar_artigo": {
        "description": "Devolve o texto oficial de um artigo (Planalto), com a citação, se está revogado e o ano da "
                       "última alteração. Códigos: cc, cpc, cp, clt, cdc, cf, ctn, eca, inquilinato. Para o ADCT da "
                       "Constituição, numero = 'ADCT 2'.",
        "inputSchema": {"type": "object", "properties": {
            "codigo": {"type": "string", "description": "cc, cpc, cp, clt, cdc, cf, ctn, eca ou inquilinato"},
            "numero": {"type": "string", "description": "o número do artigo: '421', '1.228', '54-A', 'ADCT 2'"}},
            "required": ["codigo", "numero"], "additionalProperties": False},
    },
    "procurar_na_lei": {
        "description": "Procura por palavra no texto dos códigos guardados e devolve até 8 artigos com a citação e "
                       "um resumo. Não é interpretação: é onde a palavra aparece.",
        "inputSchema": {"type": "object", "properties": {
            "termo": {"type": "string", "description": "a palavra ou expressão, ou o número do artigo"},
            "codigo": {"type": "string", "description": "opcional: restringe a um código"}},
            "required": ["termo"], "additionalProperties": False},
    },
}


def _resumo(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Conexoes:
    """As conexões MCP: nome, ferramentas, e o resumo do token (nunca o token)."""

    def __init__(self, pasta: Path) -> None:
        self.caminho = Path(pasta) / "mcp" / "conexoes.json"
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

    def criar(self, nome: str, ferramentas: list[str]) -> tuple[dict, str]:
        """(a conexão, o token) - o token só existe nesta volta."""
        pedidas = [f for f in ferramentas or [] if f in FERRAMENTAS]
        if not pedidas:
            raise ValueError("escolha pelo menos uma ferramenta")
        nome = " ".join(str(nome or "").split())[:60] or "Assistente"
        token = "paulus_mcp_" + secrets.token_urlsafe(32)
        conexao = {"id": uuid.uuid4().hex[:10], "nome": nome, "ferramentas": pedidas, "resumo": _resumo(token),
                   "criada_em": datetime.now().strftime("%Y-%m-%d %H:%M"), "ultimo_uso": "", "chamadas": 0}
        with self._trava:
            itens = self._ler()
            itens.append(conexao)
            self._gravar(itens)
        return {k: v for k, v in conexao.items() if k != "resumo"}, token

    def revogar(self, id_: str) -> bool:
        with self._trava:
            itens = self._ler()
            restantes = [c for c in itens if c["id"] != id_]
            self._gravar(restantes)
        return len(restantes) != len(itens)

    def do_token(self, token: str | None) -> dict | None:
        if not token:
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


def _texto_do_artigo(a: dict, importado_em: str) -> str:
    linhas = [a["citacao"] + (" — REVOGADO: não está em vigor" if a["revogado"] else "")]
    if a.get("contexto"):
        linhas.append(a["contexto"])
    linhas.append(a["texto"])
    if a.get("alterado_em"):
        linhas.append(f"Última alteração da redação (pelas notas do Planalto): {a['alterado_em']}.")
    linhas.append(f"Fonte: texto compilado do Planalto, guardado no PAULUS do escritório em {importado_em or '?'}.")
    return "\n".join(linhas)


def chamar(leis, nome: str, argumentos: dict) -> tuple[str, bool]:
    """(texto, é erro) de uma ferramenta."""
    import leis as leis_mod

    instalados = {l["codigo"]: l for l in leis.instalados() if l["instalado"]}
    if nome == "leis_instaladas":
        if not instalados:
            return "Nenhum código de lei guardado neste PAULUS ainda.", False
        return "\n".join(f"{c} — {l['nome']} ({l['lei']}), {l['artigos']} artigos, importado em {l['importado_em']}"
                         for c, l in instalados.items()), False
    if nome == "citar_artigo":
        codigo = str(argumentos.get("codigo", "")).strip().lower()
        numero = str(argumentos.get("numero", "")).strip()
        if codigo not in leis_mod.CODIGOS:
            return f"Não conheço o código '{codigo}'. Os que existem: {', '.join(leis_mod.CODIGOS)}.", True
        if codigo not in instalados:
            return f"O {leis_mod.CODIGOS[codigo]['nome']} não está guardado neste PAULUS: não dá para conferir.", True
        a = leis.artigo(codigo, numero)
        if not a:
            return f"Não achei o art. {numero} no {leis_mod.CODIGOS[codigo]['nome']}.", True
        return _texto_do_artigo(a, instalados[codigo]["importado_em"]), False
    if nome == "procurar_na_lei":
        termo = str(argumentos.get("termo", "")).strip()
        codigo = str(argumentos.get("codigo", "") or "").strip().lower()
        if not termo:
            return "Diga o que procurar.", True
        achados = leis.procurar(termo, codigo if codigo in instalados else "", limite=8)
        if not achados:
            return "Nada achado com esse termo nos códigos guardados (não achei - não quer dizer que não exista).", False
        return "\n\n".join(a["citacao"] + (" — REVOGADO" if a["revogado"] else "") + "\n" + a["resumo"] for a in achados), False
    return f"Ferramenta desconhecida: {nome}", True


class NovaConexao(BaseModel):
    nome: str = ""
    ferramentas: list[str] = []


def montar(estado, app) -> None:
    """As conexões, pela janela do escritório (de fora, bloqueadas em src/acesso/politicas.py)."""
    from fastapi import HTTPException

    def _ligado() -> bool:
        return bool((estado.prefs.dados.get("umbrel") or {}).get("mcp"))

    @app.get("/api/mcp")
    def mcp_estado() -> dict:
        return {"ligado": _ligado(), "endereco": f"http://127.0.0.1:{getattr(estado, 'porta', 8000)}/mcp",
                "ferramentas": [{"id": n, "descricao": f["description"]} for n, f in FERRAMENTAS.items()],
                "conexoes": estado.mcp.conexoes.listar()}

    @app.post("/api/mcp/conexoes")
    def mcp_criar(payload: NovaConexao) -> dict:
        """Uma conexão nova: o token volta só agora."""
        if not _ligado():
            raise HTTPException(status_code=409, detail="o servidor MCP está desligado em Configurações")
        try:
            conexao, token = estado.mcp.conexoes.criar(payload.nome, payload.ferramentas)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        estado.mcp._anotar(acao="mcp-conexao", alvo=f"criada: {conexao['nome']}", pessoa="janela do escritório")
        return {"conexao": conexao, "token": token, **mcp_estado()}

    @app.delete("/api/mcp/conexoes/{id_}")
    def mcp_revogar(id_: str) -> dict:
        if not estado.mcp.conexoes.revogar(id_):
            raise HTTPException(status_code=404, detail="essa conexão não existe mais")
        estado.mcp._anotar(acao="mcp-conexao", alvo=f"revogada: {id_}", pessoa="janela do escritório")
        return mcp_estado()


class ServidorMCP:
    """O /mcp: JSON-RPC 2.0 por HTTP (o transporte "streamable HTTP", só com respostas JSON)."""

    def __init__(self, *, leis, conexoes: Conexoes, ligado, registrar=None, versao: str = "") -> None:
        self.leis = leis
        self.conexoes = conexoes
        self.ligado = ligado
        self.registrar = registrar
        self.versao = versao

    def _anotar(self, **evento) -> None:
        if self.registrar:
            try:
                self.registrar(**evento)
            except Exception:  # noqa: BLE001 - a auditoria não derruba o pedido
                pass

    def responder(self, msg: dict, conexao: dict) -> dict | None:
        """A resposta JSON-RPC de uma mensagem; None para notificação."""
        metodo = msg.get("method")
        id_ = msg.get("id")
        if id_ is None:
            return None  # notificação (notifications/initialized etc.): nada a responder

        def ok(resultado):
            return {"jsonrpc": "2.0", "id": id_, "result": resultado}

        def erro(codigo, mensagem):
            return {"jsonrpc": "2.0", "id": id_, "error": {"code": codigo, "message": mensagem}}

        if metodo == "initialize":
            return ok({"protocolVersion": PROTOCOLO, "capabilities": {"tools": {"listChanged": False}},
                       "serverInfo": {"name": "paulus-leis", "version": self.versao or "0"},
                       "instructions": "Leis brasileiras guardadas no PAULUS do escritório, do texto compilado do "
                                       "Planalto. Cite o artigo pelo texto devolvido; o revogado vem marcado."})
        if metodo == "ping":
            return ok({})
        if metodo == "tools/list":
            return ok({"tools": [{"name": n, **FERRAMENTAS[n]} for n in conexao["ferramentas"] if n in FERRAMENTAS]})
        if metodo == "tools/call":
            params = msg.get("params") or {}
            nome = params.get("name", "")
            if nome not in conexao["ferramentas"]:
                self._anotar(acao="mcp-negado", alvo=nome, pessoa=conexao["nome"], ip="127.0.0.1")
                return erro(-32602, f"a ferramenta '{nome}' não está liberada para esta conexão")
            texto, falhou = chamar(self.leis, nome, params.get("arguments") or {})
            self._anotar(acao="mcp", alvo=f"{nome} {json.dumps(params.get('arguments') or {}, ensure_ascii=False)[:120]}",
                         pessoa=conexao["nome"], ip="127.0.0.1")
            self.conexoes.anotar_uso(conexao["id"])
            return ok({"content": [{"type": "text", "text": texto}], "isError": falhou})
        return erro(-32601, f"método desconhecido: {metodo}")

    async def __call__(self, scope, receive, send, cab: dict) -> None:
        from acesso.porteiro import recusar, responder

        if not self.ligado():
            await recusar(scope, send, 404, "o servidor MCP está desligado")
            return
        # Só deste computador, e nunca pelo túnel (que também chega pelo 127.0.0.1).
        cliente = (scope.get("client") or ("", 0))[0]
        if cliente not in ("127.0.0.1", "::1") or any(k.startswith("cf-") for k in cab) or "x-forwarded-for" in cab:
            await recusar(scope, send, 403, "o MCP do PAULUS só atende este computador")
            return
        if scope.get("method") != "POST":
            await recusar(scope, send, 405, "use POST com JSON-RPC")
            return
        autorizacao = cab.get("authorization", "")
        conexao = self.conexoes.do_token(autorizacao[7:].strip() if autorizacao.lower().startswith("bearer ") else "")
        if conexao is None:
            self._anotar(acao="mcp-recusado", alvo="token inválido", ip=cliente)
            await recusar(scope, send, 401, "token do MCP inválido ou revogado")
            return
        corpo = b""
        while True:
            m = await receive()
            corpo += m.get("body", b"")
            if len(corpo) > LIMITE_DO_PEDIDO:
                await recusar(scope, send, 413, "pedido grande demais")
                return
            if not m.get("more_body"):
                break
        try:
            mensagem = json.loads(corpo.decode("utf-8") or "null")
        except (ValueError, UnicodeDecodeError):
            await responder(send, 400, json.dumps({"jsonrpc": "2.0", "id": None,
                                                   "error": {"code": -32700, "message": "JSON inválido"}}).encode(),
                            "application/json")
            return
        lote = mensagem if isinstance(mensagem, list) else [mensagem]
        respostas = [r for r in (self.responder(m, conexao) for m in lote if isinstance(m, dict)) if r is not None]
        if not respostas:
            await responder(send, 202, b"", "application/json")
            return
        saida = respostas if isinstance(mensagem, list) else respostas[0]
        await responder(send, 200, json.dumps(saida, ensure_ascii=False).encode("utf-8"),
                        "application/json; charset=utf-8")
