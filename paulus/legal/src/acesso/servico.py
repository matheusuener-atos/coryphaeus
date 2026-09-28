"""
O acesso de fora montado: as contas, o portao, o tunel e a auditoria, num
objeto so, que o api.py cria uma vez e o porteiro consulta a cada pedido.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from acesso import politicas
from acesso.contas import Contas
from acesso.jwt_access import ConferidorAccess
from acesso.remoto import PortaoRemoto
from acesso.tunel import VERSAO_MINIMA, Cofre, Tunel, achar_cloudflared, versao_basta, versao_de

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
        # O tunel (R6): os segredos protegidos, o processo do cloudflared e
        # o ouvinte da porta fixa, so do tunel.
        self.cofre = Cofre(self.pasta / "tunel.json")
        self.tunel = Tunel(self._comando_cloudflared, self.cofre.token, self.dados_dir / "logs" / "tunel.log")
        self.porta_ocupada = False
        self._servidor = None
        self._cloudflared: tuple[str, str] | None = None

    # ------------------------------------------------------------ tunel

    def configurar_conferidor(self, buscar=None) -> None:
        """
        O JWT do Access passa a ser conferido aqui com o `aud` e o time que o
        Worker entregou na conexao. Sem os dois (nunca conectado), nenhum
        conferidor - e ninguem de fora passa.
        """
        p = self.preferencias()
        if p.get("aud") and p.get("team_domain"):
            self.verificar_jwt = ConferidorAccess(p["team_domain"], p["aud"], **({"buscar": buscar} if buscar else {}))
        else:
            self.verificar_jwt = None

    def cloudflared(self) -> dict:
        """Onde esta o cloudflared, que versao, e se ela basta."""
        exe = achar_cloudflared()
        if not exe:
            return {"caminho": "", "versao": "", "basta": False}
        if not self._cloudflared or self._cloudflared[0] != str(exe):
            self._cloudflared = (str(exe), versao_de(exe))
        minima = str(self.preferencias().get("cloudflared_minimo") or VERSAO_MINIMA)
        versao = self._cloudflared[1]
        return {"caminho": str(exe), "versao": versao, "minima": minima, "basta": versao_basta(versao, minima)}

    def _comando_cloudflared(self) -> list[str] | None:
        info = self.cloudflared()
        if not info["basta"]:
            return None
        return [info["caminho"], "tunnel", "--no-autoupdate", "run"]

    def abrir_porta_de_fora(self) -> bool:
        """
        O ouvinte do tunel: o mesmo app, na porta fixa, em 127.0.0.1. A janela
        local continua na porta dela - a porta fixa e so o que o tunel da
        Cloudflare procura. Ocupada por outro programa, nao abre: o que viesse
        de fora cairia naquele programa.
        """
        import socket

        porta = int(self.preferencias().get("porta") or 0)
        if not porta or self.app is None:
            return False
        if self._servidor is not None and getattr(self._servidor, "started", False) \
                and self._servidor.config.port == porta:
            return True
        self.fechar_porta_de_fora()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", porta))
            except OSError:
                self.porta_ocupada = True
                return False
        import uvicorn

        # lifespan desligado: o arranque do programa (reler o acervo, a vigia)
        # ja aconteceu no servidor da janela, e nao pode rodar duas vezes.
        servidor = uvicorn.Server(uvicorn.Config(self.app, host="127.0.0.1", port=porta,
                                                 log_level="warning", lifespan="off"))
        self._fio_servidor = threading.Thread(target=servidor.run, name="porta-de-fora", daemon=True)
        self._fio_servidor.start()
        fim = time.time() + 5
        while time.time() < fim and not servidor.started:
            time.sleep(0.05)
        if not servidor.started:
            servidor.should_exit = True
            self.porta_ocupada = True
            return False
        self._servidor = servidor
        self.porta_ocupada = False
        return True

    def fechar_porta_de_fora(self) -> None:
        """Fecha o ouvinte e espera ele soltar a porta: religar logo em seguida
        acharia a porta ainda presa e diria "porta ocupada"."""
        if self._servidor is not None:
            self._servidor.should_exit = True
            fio = getattr(self, "_fio_servidor", None)
            if fio is not None and fio is not threading.current_thread():
                fio.join(timeout=8)
            self._servidor = None

    def iniciar(self) -> None:
        """Ao abrir o programa: com o acesso ligado e conectado, o tunel sobe sozinho."""
        self.configurar_conferidor()
        if self.ligado() and self.cofre.tem() and self.abrir_porta_de_fora():
            self.tunel.ligar()

    def parar(self) -> None:
        """Ao fechar: o processo do tunel nunca sobrevive ao PAULUS."""
        self.tunel.desligar()
        self.fechar_porta_de_fora()

    def situacao(self) -> dict:
        p = self.preferencias()
        if self.porta_ocupada:
            estado = "porta_ocupada"
        elif not self.ligado():
            estado = "desligado"
        elif not self.cofre.tem():
            estado = "nao_conectado"
        else:
            estado = self.tunel.estado
        return {"estado": estado, "ligado": self.ligado(), "hostname": p.get("hostname", ""),
                "porta": int(p.get("porta") or 0), "porta_ocupada": self.porta_ocupada,
                "cloudflared": self.cloudflared(), "conectado_ao_worker": self.cofre.tem(),
                "ultimo_erro": self.tunel.ultimo_erro, "disponivel": self.contas.disponivel()}

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
