"""
O acesso de fora montado: as contas, o portao, o tunel e a auditoria, num
objeto so, que o api.py cria uma vez e o porteiro consulta a cada pedido.
"""

from __future__ import annotations

import time
from pathlib import Path

from acesso.contas import Contas
from acesso.remoto import PortaoRemoto

import json

from acesso import politicas

# O que a proposta vira no titulo do pedido, pela rota. O resto sai como
# "uma alteracao em <rota>" - sem inventar descricao para o que nao se sabe.
ROTULOS_DA_PROPOSTA = {
    ("POST", "/api/agenda"): "compromisso na agenda",
    ("DELETE", "/api/agenda/{id_}"): "tirar um compromisso da agenda",
    ("POST", "/api/agenda/nota"): "nota na agenda",
    ("POST", "/api/agenda/{id_}/meet"): "sala do Google Meet para um compromisso",
    ("POST", "/api/tarefas"): "tarefa",
    ("DELETE", "/api/tarefas/{id_}"): "apagar uma tarefa",
    ("POST", "/api/tarefas/{id_}/concluir"): "concluir uma tarefa",
    ("POST", "/api/cadastros"): "ficha de cadastro",
    ("DELETE", "/api/cadastros/{id_}"): "apagar uma ficha de cadastro",
    ("POST", "/api/trabalhos/{id_}/fazer"): "o que a conversa entendeu",
}


def _titulo_no_corpo(corpo: str) -> str:
    """O nome da coisa proposta, quando o formulario traz um."""
    try:
        dados = json.loads(corpo or "{}")
    except ValueError:
        return ""
    if not isinstance(dados, dict):
        return ""
    for fonte in (dados, dados.get("dados") or {}, dados.get("campos") or {}):
        if isinstance(fonte, dict):
            for chave in ("titulo", "nome", "texto"):
                if str(fonte.get(chave) or "").strip():
                    return str(fonte[chave]).strip()[:80]
    return ""


class AcessoDeFora:
    def __init__(self, dados_dir: Path, prefs, chave, fila=None) -> None:
        self.dados_dir = Path(dados_dir)
        self.pasta = self.dados_dir / "acesso"
        self.prefs = prefs
        self.chave = chave
        # A fila de Aprovacoes: e para onde vai o que se propoe de fora.
        self.fila = fila
        # O app, para executar a proposta aprovada (o api.py entrega).
        self.app = None
        self.contas = Contas(self.pasta / "contas.db", ao_bloquear=self._bloqueou)
        # O conferidor do JWT do Cloudflare Access (jwt_access.py). Sem ele -
        # tunel nunca conectado -, ninguem de fora passa.
        self.verificar_jwt = None
        # Os ultimos eventos, para a tela; o registro que vale e o da
        # auditoria (R8), quando existir.
        self.eventos: list[dict] = []
        self.auditoria = None
        self.ao_mudar_contas = []
        self.portao = PortaoRemoto(self.contas, self.ligado, self._conferir_jwt, registrar=self.anotar)
        self.portao.propor = self.propor

    # ----------------------------------------------------------- propor

    def propor(self, sessao: dict, metodo: str, caminho: str, corpo: str, tipo: str) -> dict:
        """O pedido de fora vira item na fila, com tudo para ser refeito depois do sim."""
        if self.fila is None:
            raise RuntimeError("sem fila de aprovações")
        rota = self._rota(metodo, caminho)
        rotulo = ROTULOS_DA_PROPOSTA.get((metodo, rota), "uma alteração em " + rota)
        nome = _titulo_no_corpo(corpo)
        # Pedir a sala do Meet cria evento no Google: sai do escritorio, e
        # aprovar de fora vai pedir o codigo do autenticador.
        try:
            formulario = json.loads(corpo or "{}")
        except ValueError:
            formulario = {}
        sai = rota.endswith("/meet") or (rota == "/api/agenda" and isinstance(formulario, dict)
                                         and bool(formulario.get("meet")))
        pedido = self.fila.pedir(
            f"{sessao['nome']} propôs de fora: {rotulo}" + (f" — {nome}" if nome else ""),
            "permissao",
            resumo=f"Pedido feito pelo acesso de fora ({sessao['email']}). Nada foi gravado: "
                   "aprovar faz exatamente o que foi pedido.",
            etiquetas=["de fora"] + (["sai desta máquina"] if sai else []),
            pedido_por=f"{sessao['nome']} (de fora)",
            acao="acesso.proposta",
            dados={"metodo": metodo, "caminho": caminho, "rota": rota, "corpo": corpo, "tipo": tipo,
                   "conta_id": sessao["conta_id"], "sai_daqui": sai},
        )
        return pedido.to_dict()

    def _rota(self, metodo: str, caminho: str) -> str:
        """O desenho da rota (/api/tarefas/{id_}) de um caminho de verdade."""
        if self.app is None:
            return caminho.split("?", 1)[0]
        escopo = {"type": "http", "method": metodo, "path": caminho.split("?", 1)[0], "root_path": "",
                  "headers": [], "query_string": b""}
        rota = politicas.rota_de(self.app.router, escopo)
        return getattr(rota, "path", "") or caminho.split("?", 1)[0]

    def executar_proposta(self, pedido) -> str:
        """
        O sim: refaz o pedido guardado, pela janela local, e devolve o que
        aconteceu. Confere de novo que a rota e das que se propoem - o arquivo
        da fila e local, mas proposta e proposta: nada alem do que a tabela
        deixa propor passa por aqui.
        """
        from starlette.testclient import TestClient

        d = pedido.dados or {}
        metodo, caminho = str(d.get("metodo", "")), str(d.get("caminho", ""))
        if politicas.de(metodo, self._rota(metodo, caminho)) != politicas.PROPOR:
            raise RuntimeError("esta rota não se propõe de fora")
        cliente = TestClient(self.app, headers=self.chave.cabecalho())
        r = cliente.request(metodo, caminho, content=str(d.get("corpo", "")).encode("utf-8"),
                            headers={"content-type": str(d.get("tipo") or "application/json")})
        if r.status_code >= 400:
            try:
                detalhe = r.json().get("detail", "")
            except ValueError:
                detalhe = r.text[:200]
            raise RuntimeError(detalhe or f"a rota respondeu {r.status_code}")
        return "feito como foi proposto de fora"

    # ------------------------------------------------------------- estado

    def preferencias(self) -> dict:
        return dict(self.prefs.dados.get("acesso_remoto") or {})

    def ligado(self) -> bool:
        return bool(self.preferencias().get("ligado"))

    def _conferir_jwt(self, token: str):
        return self.verificar_jwt(token) if self.verificar_jwt else None

    # ------------------------------------------------------------ eventos

    def anotar(self, **evento) -> None:
        evento.setdefault("quando", time.strftime("%Y-%m-%dT%H:%M:%S"))
        self.eventos = (self.eventos + [evento])[-200:]
        if self.auditoria is not None:
            try:
                self.auditoria.registrar(**evento)
            except Exception:  # noqa: BLE001 - a auditoria nao derruba o pedido
                pass

    def _bloqueou(self, email: str, nome: str, ate: float) -> None:
        minutos = max(1, round((ate - time.time()) / 60))
        quem = nome or email
        self.anotar(acao="bloqueio", alvo=f"{minutos} min", pessoa=quem, email=email)
        try:
            import avisos

            avisos.avisar("acesso", "Acesso de fora bloqueado",
                          f"Alguém errou a senha de {quem} 5 vezes. A conta ficou bloqueada por {minutos} min.")
        except Exception:  # noqa: BLE001 - sem aviso do Windows, o evento fica na tela
            pass

    def contas_mudaram(self) -> None:
        """Criou, mudou ou tirou conta: quem depende da lista (o Access, na R7) fica sabendo."""
        for f in list(self.ao_mudar_contas):
            try:
                f()
            except Exception:  # noqa: BLE001
                pass
