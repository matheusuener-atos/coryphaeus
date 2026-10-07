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

**Além das leis (L7, docs/PLANO-PILOTO.md), conexão por conexão:**

- as súmulas e os temas repetitivos do STJ (públicos, como a lei);
- **o que é do escritório** - a lista de documentos, a busca nos trechos, o
  cartão do documento (os fatos conferidos) e a posição da casa - só com um
  **escopo** escolhido na janela do escritório (o Acervo inteiro, algumas
  pastas ou alguns Serviços) e com o "entendi que sai" marcado: o trecho vai
  para o assistente conectado e dali para a empresa dele. Sempre **só
  leitura**: nenhuma ferramenta muda nada no PAULUS. Caso marcado "só no
  escritório" (src/aparelho.py) nunca sai, nem com o Acervo inteiro liberado.
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
        "description": "Lista os códigos de lei guardados neste Paulus (texto compilado do Planalto), com a data de "
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


# As que não são públicas: só com escopo e o "entendi que sai" (L7).
FERRAMENTAS_DO_ESCRITORIO = {
    "sumulas_stj": {
        "publica": True,
        "description": "Procura nas súmulas do STJ guardadas neste Paulus (texto oficial) por palavras ou pelo número.",
        "inputSchema": {"type": "object", "properties": {
            "termo": {"type": "string", "description": "palavras que o enunciado tem"},
            "numero": {"type": "string", "description": "opcional: o número da súmula"}}, "additionalProperties": False},
    },
    "temas_stj": {
        "publica": True,
        "description": "Procura nos temas repetitivos e IAC do STJ (Portal de Dados Abertos do STJ): a questão, a tese firmada "
                       "e a situação. Por palavras ou pelo número do tema.",
        "inputSchema": {"type": "object", "properties": {
            "termo": {"type": "string"}, "numero": {"type": "string"}}, "additionalProperties": False},
    },
    # N8: as súmulas do STF e as vinculantes, e as teses de repercussão geral, no instalador.
    "sumulas_stf": {
        "publica": True,
        "description": "Procura nas súmulas do STF e nas súmulas vinculantes guardadas neste Paulus (texto oficial, do "
                       "portal do STF, na data do instalador) por palavras ou pelo número.",
        "inputSchema": {"type": "object", "properties": {
            "termo": {"type": "string", "description": "palavras que o enunciado tem"},
            "numero": {"type": "string", "description": "opcional: o número da súmula"},
            "vinculante": {"type": "boolean", "description": "só as vinculantes"}}, "additionalProperties": False},
    },
    "temas_repercussao_geral": {
        "publica": True,
        "description": "Procura nas teses de repercussão geral do STF (banco de teses do portal do STF, na data do "
                       "instalador): a tese, o paradigma e se houve repercussão geral. Por palavras ou pelo número do tema.",
        "inputSchema": {"type": "object", "properties": {
            "termo": {"type": "string"}, "numero": {"type": "string"}}, "additionalProperties": False},
    },
    # N13: os acórdãos do STJ baixados neste Paulus (dados abertos, CC-BY).
    "jurisprudencia_stj": {
        "publica": True,
        "description": "Procura nos acórdãos do STJ baixados neste Paulus (espelhos de acórdãos do Portal de Dados Abertos do "
                       "STJ): a ementa oficial e a citação, por palavras, ou os que citam um artigo (codigo + artigo).",
        "inputSchema": {"type": "object", "properties": {
            "termo": {"type": "string"}, "codigo": {"type": "string", "description": "cc, cpc, cdc, cf..."},
            "artigo": {"type": "string"}}, "additionalProperties": False},
    },
    "vigencia_do_artigo": {
        "publica": True,
        "description": "Como estava um artigo de lei numa data: cada dispositivo (caput, parágrafos, incisos) vigente, "
                       "revogado, ainda não incluído ou com redação anterior, e o histórico das mudanças, pelas notas do "
                       "compilado do Planalto. Não traz o texto da redação anterior.",
        "inputSchema": {"type": "object", "properties": {
            "codigo": {"type": "string"}, "numero": {"type": "string"},
            "data": {"type": "string", "description": "AAAA-MM-DD; sem ela, hoje"}},
            "required": ["codigo", "numero"], "additionalProperties": False},
    },
    # N9: as que escrevem. Nunca apagam nem mudam o que existe: o rascunho é
    # documento novo no editor, a anotação entra na trilha do Serviço marcada
    # com a conexão, e tarefa e compromisso param em Aprovações até o sim.
    "criar_rascunho": {
        "publica": False, "escreve": True,
        "description": "Cria um rascunho novo no editor do Paulus (título e texto). Não mexe em nenhum documento que existe; "
                       "a pessoa do escritório revisa lá.",
        "inputSchema": {"type": "object", "properties": {
            "titulo": {"type": "string"}, "texto": {"type": "string", "description": "o texto do rascunho; parágrafos separados por linha em branco"}},
            "required": ["titulo", "texto"], "additionalProperties": False},
    },
    "anotar_no_servico": {
        "publica": False, "escreve": True,
        "description": "Acrescenta uma anotação na trilha de um Serviço liberado para esta conexão, marcada como vinda do "
                       "assistente conectado. Não apaga nem muda o que já está lá.",
        "inputSchema": {"type": "object", "properties": {
            "servico": {"type": "string", "description": "o nome do Serviço ou o número dele"},
            "texto": {"type": "string"}}, "required": ["servico", "texto"], "additionalProperties": False},
    },
    "propor_tarefa": {
        "publica": False, "escreve": True,
        "description": "Pede uma tarefa (título e, se tiver, o prazo AAAA-MM-DD). O pedido espera em Aprovações: a tarefa só "
                       "existe depois do sim de alguém do escritório.",
        "inputSchema": {"type": "object", "properties": {
            "titulo": {"type": "string"}, "prazo": {"type": "string"}, "anotacao": {"type": "string"}},
            "required": ["titulo"], "additionalProperties": False},
    },
    "propor_compromisso": {
        "publica": False, "escreve": True,
        "description": "Pede um compromisso na agenda (título, data AAAA-MM-DD, hora HH:MM). O pedido espera em Aprovações: "
                       "nada entra na agenda sem o sim de alguém do escritório.",
        "inputSchema": {"type": "object", "properties": {
            "titulo": {"type": "string"}, "data": {"type": "string"}, "hora": {"type": "string"},
            "duracao": {"type": "integer", "description": "minutos"}},
            "required": ["titulo", "data"], "additionalProperties": False},
    },
    "acervo_documentos": {
        "publica": False,
        "description": "Lista os documentos do escritório que esta conexão pode ler (só os do escopo liberado).",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "acervo_procurar": {
        "publica": False,
        "description": "Procura nos documentos do escritório liberados para esta conexão e devolve até 6 trechos, com o "
                       "documento e a página. Só leitura.",
        "inputSchema": {"type": "object", "properties": {"termo": {"type": "string"}}, "required": ["termo"],
                        "additionalProperties": False},
    },
    "acervo_cartao": {
        "publica": False,
        "description": "Os fatos conferidos de um documento liberado (tipo, número do processo, partes, valores, datas), "
                       "cada um com a página e o trecho de onde saiu.",
        "inputSchema": {"type": "object", "properties": {"documento": {"type": "string", "description": "o nome do arquivo"}},
                        "required": ["documento"], "additionalProperties": False},
    },
    "posicao_da_casa": {
        "publica": False,
        "description": "O que o escritório entende de um artigo de lei (a posição da casa), quando escrita.",
        "inputSchema": {"type": "object", "properties": {"codigo": {"type": "string"}, "numero": {"type": "string"}},
                        "required": ["codigo", "numero"], "additionalProperties": False},
    },
}
TODAS = {**FERRAMENTAS, **FERRAMENTAS_DO_ESCRITORIO}


def publica(nome: str) -> bool:
    return nome in FERRAMENTAS or bool(FERRAMENTAS_DO_ESCRITORIO.get(nome, {}).get("publica"))


def escreve(nome: str) -> bool:
    return bool(FERRAMENTAS_DO_ESCRITORIO.get(nome, {}).get("escreve"))


# As que escrevem e não leem o Acervo: não pedem escopo (o rascunho é novo, e o
# pedido espera em Aprovações). A anotação no Serviço pede: só nos liberados.
SEM_ESCOPO = {"criar_rascunho", "propor_tarefa", "propor_compromisso"}


def limpar_escopo(bruto) -> dict:
    b = bruto if isinstance(bruto, dict) else {}
    return {"tudo": bool(b.get("tudo")),
            "pastas": [str(p).strip().strip("\\/") for p in (b.get("pastas") or []) if str(p).strip()][:30],
            "servicos": [int(s) for s in (b.get("servicos") or []) if str(s).isdigit()][:30],
            # N9: os clientes - os Serviços de cada um e os documentos ligados à ficha.
            "clientes": [int(c) for c in (b.get("clientes") or []) if str(c).isdigit()][:30]}


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

    def criar(self, nome: str, ferramentas: list[str], escopo=None, entendi: bool = False,
              entendi_escrever: bool = False) -> tuple[dict, str]:
        """(a conexão, o token) - o token só existe nesta volta."""
        pedidas = [f for f in ferramentas or [] if f in TODAS]
        if not pedidas:
            raise ValueError("escolha pelo menos uma ferramenta")
        escopo = limpar_escopo(escopo)
        privadas = [f for f in pedidas if not publica(f)]
        com_escopo = [f for f in privadas if f not in SEM_ESCOPO]
        if com_escopo and not (escopo["tudo"] or escopo["pastas"] or escopo["servicos"] or escopo["clientes"]):
            raise ValueError("as ferramentas do escritório precisam de um escopo: o Acervo inteiro, pastas, Serviços ou clientes")
        if privadas and not entendi:
            raise ValueError("marque que entendeu: os trechos vão para o assistente conectado e para a empresa dele")
        if any(escreve(f) for f in pedidas) and not entendi_escrever:
            raise ValueError("marque que entendeu que esta conexão vai criar coisas no Paulus: rascunhos, anotações e pedidos em Aprovações")
        nome = " ".join(str(nome or "").split())[:60] or "Assistente"
        token = "paulus_mcp_" + secrets.token_urlsafe(32)
        conexao = {"id": uuid.uuid4().hex[:10], "nome": nome, "ferramentas": pedidas, "resumo": _resumo(token),
                   "escopo": escopo if privadas else {"tudo": False, "pastas": [], "servicos": [], "clientes": []},
                   "escreve": [f for f in pedidas if escreve(f)],
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
    linhas.append(f"Fonte: texto compilado do Planalto, guardado no Paulus do escritório em {importado_em or '?'}.")
    return "\n".join(linhas)


def chamar(leis, nome: str, argumentos: dict) -> tuple[str, bool]:
    """(texto, é erro) de uma ferramenta."""
    import leis as leis_mod

    instalados = {l["codigo"]: l for l in leis.instalados() if l["instalado"]}
    if nome == "leis_instaladas":
        if not instalados:
            return "Nenhum código de lei guardado neste Paulus ainda.", False
        return "\n".join(f"{c} — {l['nome']} ({l['lei']}), {l['artigos']} artigos, importado em {l['importado_em']}"
                         for c, l in instalados.items()), False
    if nome == "citar_artigo":
        codigo = str(argumentos.get("codigo", "")).strip().lower()
        numero = str(argumentos.get("numero", "")).strip()
        if codigo not in leis_mod.CODIGOS:
            return f"Não conheço o código '{codigo}'. Os que existem: {', '.join(leis_mod.CODIGOS)}.", True
        if codigo not in instalados:
            return f"O {leis_mod.CODIGOS[codigo]['nome']} não está guardado neste Paulus: não dá para conferir.", True
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


# ------------------------------------------------------------ o que é do escritório (L7)

def _pastas_do_escopo(estado, escopo: dict) -> list[Path] | None:
    """None = o Acervo inteiro; senão, as pastas liberadas (as do Acervo e as dos Serviços)."""
    if escopo.get("tudo"):
        return None
    saida = []
    for p in escopo.get("pastas") or []:
        c = Path(p)
        saida.append((c if c.is_absolute() else Path(estado.pasta) / c).resolve())
    for s in servicos_do_escopo(estado, escopo):
        pasta = estado.servicos.pasta_de(int(s), criar=False)
        if pasta:
            saida.append(Path(pasta).resolve())
    return saida


def servicos_do_escopo(estado, escopo: dict) -> list[int]:
    """Os Serviços liberados: os escolhidos e os dos clientes escolhidos (N9)."""
    ids = [int(s) for s in escopo.get("servicos") or []]
    for c in escopo.get("clientes") or []:
        ids += [int(l["id"]) for l in estado.base.buscar("SELECT id FROM servicos WHERE cadastro_id = ?", (int(c),))]
    return list(dict.fromkeys(ids))


def _sha1_dos_clientes(estado, escopo: dict) -> set[str]:
    """Os documentos ligados à ficha dos clientes escolhidos (N9)."""
    saida: set[str] = set()
    for c in escopo.get("clientes") or []:
        saida |= {l["sha1"] for l in estado.base.buscar("SELECT sha1 FROM vinculos WHERE tipo = 'cadastro' AND alvo_id = ?", (int(c),))}
    return saida


def liberado(estado, conexao: dict, caminho: str, sha1: str = "") -> bool:
    """Este arquivo está no escopo da conexão, e fora dos casos só no escritório?"""
    import aparelho

    try:
        alvo = Path(caminho).resolve()
    except OSError:
        return False
    if aparelho.so_no_escritorio().toca(estado, [str(alvo)]):
        return False
    escopo = conexao.get("escopo") or {}
    pastas = _pastas_do_escopo(estado, escopo)
    if pastas is None:
        return True
    if sha1 and sha1 in _sha1_dos_clientes(estado, escopo):
        return True
    return any(alvo == p or alvo.is_relative_to(p) for p in pastas)


def chamar_escritorio(estado, conexao: dict, nome: str, argumentos: dict) -> tuple[str, bool]:
    if nome == "sumulas_stj":
        from biblioteca.rotas import procurar_sumulas

        achadas = [x for x in procurar_sumulas(estado.material, termo=str(argumentos.get("termo") or ""),
                                               numero=str(argumentos.get("numero") or ""), limite=40)
                   if "do STJ" in x["titulo"]][:8]
        if not achadas:
            return "Nenhuma súmula do STJ com isso nas guardadas neste Paulus.", False
        return "\n\n".join(f"{s['titulo']}\n{s['texto']}" for s in achadas), False
    if nome == "sumulas_stf":
        from biblioteca.rotas import procurar_sumulas

        so_vinculantes = bool(argumentos.get("vinculante"))
        achadas = [x for x in procurar_sumulas(estado.material, termo=str(argumentos.get("termo") or ""),
                                               numero=str(argumentos.get("numero") or ""), limite=40)
                   if "do STF" in x["titulo"] and (not so_vinculantes or "Vinculante" in x["titulo"])][:8]
        if not achadas:
            return "Nenhuma súmula do STF com isso nas guardadas neste Paulus.", False
        return "\n\n".join(f"{s['titulo']}\n{s['texto']}" for s in achadas), False
    if nome == "temas_repercussao_geral":
        achados = [t for t in estado.temas.procurar(str(argumentos.get("termo") or ""), str(argumentos.get("numero") or ""), limite=30)
                   if t.get("tribunal") == "STF"][:6]
        if not achados:
            return "Nenhuma tese de repercussão geral com isso nas guardadas neste Paulus.", False
        return "\n\n".join(f"{t['rotulo']} — {t['situacao']}" + (f" · {t['assuntos']}" if t.get("assuntos") else "")
                            + f"\nTese: {t['tese']}" for t in achados), False
    if nome == "jurisprudencia_stj":
        jur = getattr(estado, "jurisprudencia", None)
        if jur is None or not jur.instalado():
            return "A jurisprudência do STJ não foi baixada neste Paulus (Biblioteca › Jurisprudência).", False
        if argumentos.get("codigo") and argumentos.get("artigo"):
            achados = jur.do_artigo(str(argumentos["codigo"]).lower(), str(argumentos["artigo"]), limite=6)
        else:
            achados = jur.procurar(str(argumentos.get("termo") or ""), limite=6)
        if not achados:
            return "Nenhum acórdão com isso nos baixados neste Paulus.", False
        return "\n\n".join(f"{a['citacao']}\nEmenta: {a['ementa'][:1200]}" for a in achados), False
    if nome == "temas_stj":
        achados = [t for t in estado.temas.procurar(str(argumentos.get("termo") or ""), str(argumentos.get("numero") or ""), limite=30)
                   if t.get("tribunal") != "STF"][:6]
        if not achados:
            return "Nenhum tema do STJ com isso (Portal de Dados Abertos do STJ).", False
        return "\n\n".join(f"{t['rotulo']} — {t['situacao']} ({t['orgao']})\nQuestão: {t['questao']}"
                            + (f"\nTese firmada: {t['tese']}" if t['tese'] else "\nAinda sem tese firmada.") for t in achados), False
    if nome == "vigencia_do_artigo":
        import vigencia
        from datetime import date as _date

        a = estado.leis.artigo(str(argumentos.get("codigo", "")).lower(), str(argumentos.get("numero", "")))
        if not a:
            return "Artigo não encontrado nos códigos guardados neste Paulus.", True
        quando = str(argumentos.get("data") or _date.today().isoformat())[:10]
        try:
            _date.fromisoformat(quando)
        except ValueError:
            return "A data vai como AAAA-MM-DD.", True
        r = vigencia.do_artigo(a, quando)
        linhas = [f"{r['citacao']} em {quando}: {r['resumo']}"]
        linhas += [f"- {d['rotulo']}: {d['na_data']['frase']}" for d in r["dispositivos"] if d["notas"] or d["diferente"]]
        linhas.append(r["limites"])
        return "\n".join(linhas), False
    if nome == "posicao_da_casa":
        p = estado.posicoes.obter(str(argumentos.get("codigo", "")).lower(), str(argumentos.get("numero", "")))
        return (p["texto"] if p else "O escritório não escreveu a posição dele sobre esse artigo."), False
    if escreve(nome):
        return _escrever(estado, conexao, nome, argumentos)
    docs = [d for d in estado.searcher.documents if liberado(estado, conexao, d.path, getattr(d, "sha1", ""))]
    if nome == "acervo_documentos":
        if not docs:
            return "Nenhum documento liberado para esta conexão.", False
        return "\n".join(f"{d.name} ({d.pages} p.)" if d.pages else d.name for d in docs[:300]), False
    if nome == "acervo_procurar":
        termo = str(argumentos.get("termo") or "").strip()
        if not termo:
            return "Diga o que procurar.", True
        caminhos = {d.path for d in docs}
        achados = [h for h in estado.searcher.search(termo, top_k=40) if getattr(h.chunk, "doc_path", "") in caminhos][:6]
        if not achados:
            return "Nada achado com esse termo nos documentos liberados.", False
        saida = []
        for h in achados:
            pagina = getattr(h.chunk, "pagina", None) or (getattr(h.chunk, "paginas", None) or [None])[0]
            saida.append(f"{h.chunk.doc_name}" + (f", p. {pagina}" if pagina else "") + ":\n" + " ".join(h.chunk.text.split())[:700])
        return "\n\n".join(saida), False
    if nome == "acervo_cartao":
        import ajuda

        doc = next((d for d in docs if d.name == str(argumentos.get("documento") or "")), None)
        if doc is None:
            return "Esse documento não está entre os liberados para esta conexão.", True
        metas, _ = estado.saber.metadados_de([doc])
        if not metas:
            return "Esse documento ainda não foi lido pelo Paulus: não há fatos conferidos.", False
        cartao = ajuda.cartao(metas[0], doc.name) or {}
        itens = cartao.get("itens") or []
        if not itens:
            return f"{doc.name}: nenhum fato conferido ainda.", False
        linhas = [f"{doc.name} — os fatos conferidos na leitura, com a página e o trecho:"]
        for i in itens[:60]:
            linhas.append(f"- {i.get('rotulo', '')}: {i.get('valor', '')}" + (f" (p. {i['pagina']})" if i.get("pagina") else "")
                          + (f" — “{i['quote'][:160]}”" if i.get("quote") else ""))
        return "\n".join(linhas), False
    return f"Ferramenta desconhecida: {nome}", True


def _escrever(estado, conexao: dict, nome: str, argumentos: dict) -> tuple[str, bool]:
    """As quatro que escrevem (N9). Cada uma diz o que fez e onde a pessoa confere."""
    import html as _html
    import re as _re
    from datetime import date as _date

    quem = f"Assistente conectado “{conexao['nome']}” (MCP)"
    if nome == "criar_rascunho":
        titulo = " ".join(str(argumentos.get("titulo") or "").split())[:120]
        texto = str(argumentos.get("texto") or "").strip()[:60000]
        if not titulo or not texto:
            return "O rascunho precisa de título e texto.", True
        corpo = "".join(f"<p>{_html.escape(' '.join(p.split()))}</p>" for p in _re.split(r"\n\s*\n", texto) if p.strip())
        corpo = f"<p><em>Rascunho criado pelo {_html.escape(quem)} — revise antes de usar.</em></p>" + corpo
        id_ = estado.documentos.criar(f"{titulo} (rascunho do assistente)", "texto", corpo)
        return f"Rascunho criado no editor do Paulus: “{titulo} (rascunho do assistente)” (número {id_}). Quem revisa é o escritório.", False
    if nome == "anotar_no_servico":
        alvo = str(argumentos.get("servico") or "").strip()
        texto = " ".join(str(argumentos.get("texto") or "").split())[:2000]
        if not alvo or not texto:
            return "Diga o Serviço e o texto da anotação.", True
        liberados = servicos_do_escopo(estado, conexao.get("escopo") or {})
        todos = conexao.get("escopo", {}).get("tudo")
        candidatos = estado.base.buscar("SELECT id, nome FROM servicos")
        achado = next((c for c in candidatos if str(c["id"]) == alvo or c["nome"].strip().lower() == alvo.lower()), None)
        if not achado or not (todos or int(achado["id"]) in liberados):
            return "Esse Serviço não está entre os liberados para esta conexão.", True
        estado.servicos.trilha(int(achado["id"]), f"Anotação do {quem}: {texto}", quem=conexao["nome"])
        return f"Anotado na trilha do Serviço “{achado['nome']}”, marcado como vindo do assistente conectado.", False
    if nome == "propor_tarefa":
        titulo = " ".join(str(argumentos.get("titulo") or "").split())[:200]
        prazo = str(argumentos.get("prazo") or "").strip()[:10]
        if not titulo:
            return "A tarefa precisa de um título.", True
        if prazo:
            try:
                _date.fromisoformat(prazo)
            except ValueError:
                return "O prazo vai como AAAA-MM-DD.", True
        pedido = estado.fila.pedir(f"{conexao['nome']}: tarefa “{titulo}”", "conversa", acao="mcp.tarefa", pedido_por=quem,
                                   resumo=(f"Prazo {prazo[8:10]}/{prazo[5:7]}/{prazo[:4]}. " if prazo else "") +
                                          (str(argumentos.get("anotacao") or "")[:600]),
                                   etiquetas=["MCP"], prazo=prazo,
                                   dados={"titulo": titulo, "prazo": prazo, "anotacao": str(argumentos.get("anotacao") or "")[:2000],
                                          "conexao": conexao["nome"]})
        return f"Pedido em Aprovações ({pedido.id}): a tarefa “{titulo}” só existe depois do sim de alguém do escritório.", False
    if nome == "propor_compromisso":
        titulo = " ".join(str(argumentos.get("titulo") or "").split())[:200]
        data = str(argumentos.get("data") or "").strip()[:10]
        hora = str(argumentos.get("hora") or "09:00").strip()[:5]
        try:
            _date.fromisoformat(data)
        except ValueError:
            return "A data vai como AAAA-MM-DD.", True
        if not _re.fullmatch(r"\d{2}:\d{2}", hora):
            return "A hora vai como HH:MM.", True
        try:
            duracao = max(5, min(int(argumentos.get("duracao") or 60), 720))
        except (TypeError, ValueError):
            duracao = 60
        pedido = estado.fila.pedir(f"{conexao['nome']}: compromisso “{titulo}”", "agenda", acao="mcp.compromisso", pedido_por=quem,
                                   resumo=f"{data[8:10]}/{data[5:7]}/{data[:4]} às {hora}, {duracao} min.", etiquetas=["MCP"], prazo=data,
                                   dados={"titulo": titulo or "Compromisso", "data": data, "hora": hora, "duracao": duracao,
                                          "conexao": conexao["nome"]})
        return f"Pedido em Aprovações ({pedido.id}): o compromisso só entra na agenda depois do sim de alguém do escritório.", False
    return f"Ferramenta desconhecida: {nome}", True


def executar_tarefa(estado, pedido) -> str:
    """O sim em Aprovações para a tarefa pedida pelo MCP."""
    d = pedido.dados
    tid = estado.tarefas.salvar({"titulo": d["titulo"], "prazo": d.get("prazo") or "",
                                 "anotacao": ((d.get("anotacao") or "") + f"\n\nPedida pelo assistente conectado “{d.get('conexao', '')}” (MCP).").strip()})
    return f"tarefa criada (número {tid})"


def executar_compromisso(estado, pedido) -> str:
    """O sim em Aprovações para o compromisso pedido pelo MCP."""
    d = pedido.dados
    cid = estado.agenda.salvar({"titulo": d["titulo"], "data": d["data"], "hora": d.get("hora") or "09:00",
                                "duracao": int(d.get("duracao") or 60), "tipo": "compromisso",
                                "anotacao": f"Pedido pelo assistente conectado “{d.get('conexao', '')}” (MCP)."})
    return f"compromisso anotado em {d['data'][8:10]}/{d['data'][5:7]} às {d.get('hora')} (número {cid})"


class NovaConexao(BaseModel):
    nome: str = ""
    ferramentas: list[str] = []
    escopo: dict = {}
    entendi: bool = False
    # N9: as ferramentas que escrevem pedem o segundo "entendi".
    entendi_escrever: bool = False


def montar(estado, app) -> None:
    """As conexões, pela janela do escritório (de fora, bloqueadas em src/acesso/politicas.py)."""
    from fastapi import HTTPException

    def _ligado() -> bool:
        return bool((estado.prefs.dados.get("umbrel") or {}).get("mcp"))

    @app.get("/api/mcp")
    def mcp_estado() -> dict:
        return {"ligado": _ligado(), "endereco": f"http://127.0.0.1:{getattr(estado, 'porta', 8000)}/mcp",
                "ferramentas": [{"id": n, "descricao": f["description"], "publica": publica(n), "escreve": escreve(n)} for n, f in TODAS.items()],
                "conexoes": estado.mcp.conexoes.listar()}

    @app.post("/api/mcp/conexoes")
    def mcp_criar(payload: NovaConexao) -> dict:
        """Uma conexão nova: o token volta só agora."""
        if not _ligado():
            raise HTTPException(status_code=409, detail="o servidor MCP está desligado em Configurações")
        try:
            conexao, token = estado.mcp.conexoes.criar(payload.nome, payload.ferramentas, payload.escopo, payload.entendi,
                                                       payload.entendi_escrever)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        privadas = [f for f in conexao["ferramentas"] if not publica(f)]
        estado.mcp._anotar(acao="mcp-conexao", alvo=f"criada: {conexao['nome']}" +
                           (f" · do escritório: {', '.join(privadas)} · escopo {json.dumps(conexao['escopo'], ensure_ascii=False)}" if privadas else "") +
                           (f" · escreve: {', '.join(conexao['escreve'])}" if conexao.get("escreve") else ""),
                           pessoa="janela do escritório")
        return {"conexao": conexao, "token": token, **mcp_estado()}

    @app.delete("/api/mcp/conexoes/{id_}")
    def mcp_revogar(id_: str) -> dict:
        if not estado.mcp.conexoes.revogar(id_):
            raise HTTPException(status_code=404, detail="essa conexão não existe mais")
        estado.mcp._anotar(acao="mcp-conexao", alvo=f"revogada: {id_}", pessoa="janela do escritório")
        return mcp_estado()


class ServidorMCP:
    """O /mcp: JSON-RPC 2.0 por HTTP (o transporte "streamable HTTP", só com respostas JSON)."""

    def __init__(self, *, leis, conexoes: Conexoes, ligado, registrar=None, versao: str = "", estado=None) -> None:
        self.leis = leis
        # L7: o que é do escritório (o Acervo, a posição da casa) - só com escopo.
        self.estado = estado
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
                       "serverInfo": {"name": "paulus", "version": self.versao or "0"},
                       "instructions": "O Paulus do escritório: leis do texto compilado do Planalto (o revogado vem "
                                       "marcado), súmulas e temas do STJ e do STF e, se liberado para esta conexão, documentos "
                                       "do escritório. As ferramentas que escrevem só criam (rascunho, anotação) ou pedem em "
                                       "Aprovações (tarefa, compromisso) - nada apaga nem muda o que existe. Cite pelo texto "
                                       "devolvido; não invente o que não veio."})
        if metodo == "ping":
            return ok({})
        if metodo == "tools/list":
            return ok({"tools": [{"name": n, **{k: v for k, v in TODAS[n].items() if k != "publica"}}
                                 for n in conexao["ferramentas"] if n in TODAS]})
        if metodo == "tools/call":
            params = msg.get("params") or {}
            nome = params.get("name", "")
            if nome not in conexao["ferramentas"]:
                self._anotar(acao="mcp-negado", alvo=nome, pessoa=conexao["nome"], ip="127.0.0.1")
                return erro(-32602, f"a ferramenta '{nome}' não está liberada para esta conexão")
            if nome in FERRAMENTAS:
                texto, falhou = chamar(self.leis, nome, params.get("arguments") or {})
            elif self.estado is None:
                texto, falhou = "Esta ferramenta não está disponível aqui.", True
            else:
                try:
                    texto, falhou = chamar_escritorio(self.estado, conexao, nome, params.get("arguments") or {})
                except Exception as exc:  # noqa: BLE001 - a falha vira resposta, e o servidor segue
                    texto, falhou = f"Não consegui: {exc}", True
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
            await recusar(scope, send, 403, "o MCP do Paulus só atende este computador")
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
