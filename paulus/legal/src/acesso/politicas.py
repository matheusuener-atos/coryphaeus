"""
O que cada rota permite a quem esta de fora (R3).

O registro e central, e nao um decorador espalhado pelas 10 mil linhas do
api.py, por dois motivos: a tabela inteira cabe numa leitura, para revisar; e
`tests/test_r3_permissoes.py` percorre `app.routes` e falha se alguma rota nao
estiver aqui. **Rota sem politica declarada e bloqueada para quem esta de
fora** - rota nova nasce fechada ate alguem abri-la de proposito.

As politicas:

    publico    so passa pelo Cloudflare Access; nao precisa de sessao do
               PAULUS (a tela de login e o que ela carrega)
    permitido  qualquer pessoa com sessao
    titular    so o papel titular
    download   qualquer pessoa com sessao, um arquivo por requisicao, e
               cada um fica registrado em "quem acessou" (R8)
    bloqueado  "disponivel so no computador do escritorio"
"""

from __future__ import annotations

PUBLICO = "publico"
PERMITIDO = "permitido"
TITULAR = "titular"
DOWNLOAD = "download"
BLOQUEADO = "bloqueado"
POLITICAS = (PUBLICO, PERMITIDO, TITULAR, DOWNLOAD, BLOQUEADO)

MENSAGEM_BLOQUEADA = "Disponível só no computador do escritório"

# (metodo, caminho da rota como esta no app) -> politica. Rota que nao esta
# aqui e BLOQUEADO.
REGISTRO: dict[tuple[str, str], str] = {}


def _declarar(politica: str, *rotas: str) -> None:
    for r in rotas:
        metodo, caminho = r.split(" ", 1)
        REGISTRO[(metodo, caminho)] = politica


# --- a tela de login e o que ela carrega (so atras do Access)
_declarar(PUBLICO,
          "GET /", "GET /css/{arquivo}", "GET /js/{arquivo}", "GET /img/{arquivo}", "GET /img/marcas/{arquivo}",
          "GET /fontes.css", "GET /fontes/{arquivo}",
          "GET /api/acesso/eu", "POST /api/acesso/entrar", "POST /api/acesso/entrar/codigo")
_declarar(PERMITIDO, "POST /api/acesso/sair")


def de(metodo: str, caminho_da_rota: str | None) -> str:
    """A politica remota de uma rota; sem declaracao, bloqueada."""
    if not caminho_da_rota:
        return BLOQUEADO
    metodo = "GET" if metodo == "HEAD" else metodo
    return REGISTRO.get((metodo, caminho_da_rota), BLOQUEADO)


def rota_de(app, scope):
    """A rota do app que atende este pedido, pelo mesmo casamento do Starlette."""
    from starlette.routing import Match

    for rota in getattr(app, "routes", []):
        try:
            casou, _ = rota.matches(scope)
        except Exception:  # noqa: BLE001 - rota que nao sabe casar nao atende
            continue
        if casou == Match.FULL:
            return rota
    return None
