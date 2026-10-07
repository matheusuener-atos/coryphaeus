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
from acesso.auditoria import Auditoria
from acesso.contas import Contas
from acesso.energia import Acordado
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
        # Os convites (E4): o link que o titular manda, e a conta nasce no
        # celular de quem foi convidado.
        from acesso.convites import Convites

        self.convites = Convites(self.pasta / "contas.db", self.contas)
        # Entrar com o Google (E3a): o Google prova o e-mail; o codigo do
        # celular continua pedido depois.
        from acesso.google_login import LoginGoogle

        self.google = LoginGoogle(self)
        # A conversa com o Worker de paulus.ia.br (conexao.py); o api.py cria.
        # E por ela que o Turnstile de cada login e conferido.
        self.conexao = None
        # Os ultimos eventos, em memoria; o registro que vale e o da
        # auditoria (R8): so cresce, com hash encadeado, guardado um ano.
        self.eventos: list[dict] = []
        self.auditoria = Auditoria(self.pasta / "acessos.jsonl")
        # caminho da API -> nome legivel (o api.py entrega; sem ele, fica o caminho).
        self.descrever = None
        self.ao_mudar_contas = []
        self.portao = PortaoRemoto(self.contas, self.ligado, registrar=self.anotar)
        self.portao.propor = self.propor
        # O tunel (R6): os segredos protegidos, o processo do cloudflared e
        # o ouvinte da porta fixa, so do tunel.
        self.cofre = Cofre(self.pasta / "tunel.json")
        self.tunel = Tunel(self._comando_cloudflared, self.cofre.token, self.dados_dir / "logs" / "tunel.log")
        self.porta_ocupada = False
        self._servidor = None
        self._cloudflared: tuple[str, str] | None = None
        # O pedido ao Windows para nao suspender, enquanto o acesso esta ligado.
        self.acordado = Acordado()

    # ------------------------------------------------------------ tunel


    def so_google(self) -> bool:
        """
        De fora, TODA entrada e pelo Google (+ codigo do celular) - decisao do
        dono, 28/09/2026. Sem o login do Google configurado, ninguem entra de
        fora: a tela diz o que falta, e nao volta a pedir senha. A chave
        `acesso_remoto.so_google` existe para os testes do caminho por senha.
        """
        return bool(self.preferencias().get("so_google", True))

    def conferir_turnstile(self, token: str, ip: str = "") -> str:
        """
        O anti-robo de um login de fora, conferido no Worker (o segredo do
        Turnstile nunca vem para ca). "ok", "recusado" ou "indisponivel" -
        e indisponivel NUNCA libera: sem o Worker, ninguem entra.
        """
        from acesso.provisao import ErroProvisao, ErroRemovido

        segredo = self.cofre.segredo() if self.cofre.tem() else ""
        if not segredo or self.conexao is None or not str(token or "").strip():
            return "indisponivel" if not segredo or self.conexao is None else "recusado"
        try:
            ok = self.conexao.provisao.turnstile(segredo, str(token), ip)
        except ErroRemovido as exc:
            self.endereco_liberado(exc.motivo)
            return "indisponivel"
        except ErroProvisao:
            return "indisponivel"
        return "ok" if ok else "recusado"

    def email_do_cliente(self, dados: dict) -> str:
        """
        Manda um e-mail da Area do cliente pelo Worker. Devolve "" quando foi,
        ou a frase do que impediu - sem o acesso de fora conectado, nao ha
        endereco para o link nem segredo para pedir.
        """
        from acesso.provisao import ErroProvisao, ErroRemovido

        if not self.cofre.tem() or self.conexao is None:
            return "o acesso externo não está conectado"
        try:
            self.conexao.provisao.email_do_cliente(self.cofre.segredo(), dados)
        except ErroRemovido as exc:
            self.endereco_liberado(exc.motivo)
            return "o endereço do escritório não existe mais em paulus.ia.br"
        except ErroProvisao as exc:
            return str(exc)
        return ""

    def endereco_liberado(self, motivo: str = "") -> None:
        """
        O Worker diz que o endereco deste PAULUS nao existe mais: desliga o
        tunel, apaga o que foi guardado e deixa o aviso na janela local.
        """
        hostname = self.preferencias().get("hostname", "")
        self.parar()
        self.cofre.apagar()
        if "dias" in (motivo or ""):
            texto = "o endereço foi liberado por falta de uso; conecte de novo"
        else:
            texto = "o endereço não existe mais em paulus.ia.br; conecte de novo"
        self.prefs.atualizar({"acesso_remoto": {"ligado": False, "hostname": "", "turnstile_sitekey": "",
                                                "porta": 0, "liberado": texto}})
        self.contas.encerrar_sessoes()
        self.anotar(acao="liberado", alvo=hostname + (f" ({motivo})" if motivo else ""), pessoa="paulus.ia.br")
        try:
            import avisos

            avisos.avisar("acesso", "Acesso externo desligado", texto[:1].upper() + texto[1:] + ".")
        except Exception:  # noqa: BLE001 - sem aviso do Windows, a tela mostra
            pass

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
        try:
            self.auditoria.podar()
        except OSError:
            pass
        # O endereco ainda existe em paulus.ia.br? Liberado por falta de uso,
        # desliga e avisa em vez de ficar tentando.
        if self.cofre.tem() and self.conexao is not None:
            self.conexao.verificar_endereco()
        if self.ligado() and self.cofre.tem() and self.abrir_porta_de_fora():
            self.tunel.ligar()
            # Com gente podendo entrar de fora, o computador nao dorme sozinho (R9).
            self.segurar_acordado(True)

    def parar(self) -> None:
        """Ao fechar: o processo do tunel nunca sobrevive ao PAULUS."""
        self.tunel.desligar()
        self.fechar_porta_de_fora()
        self.segurar_acordado(False)

    # ------------------------------------------------------------ energia

    def segurar_acordado(self, ligar: bool) -> None:
        if ligar:
            self.acordado.ligar()
        else:
            self.acordado.desligar()

    def energia(self) -> dict:
        """
        O que a tela diz sobre a maquina ficar de pe: se o PAULUS esta
        segurando o Windows acordado, o que o plano de energia faria sem isso,
        e o "abrir com o Windows".
        """
        from acesso import energia as e

        suspende = e.minutos_ate_suspender()
        tomada, bateria = suspende.get("tomada_min", 0), suspende.get("bateria_min", 0)
        if self.acordado.ligado:
            situacao, tom = "o Windows não suspende por inatividade enquanto o acesso externo estiver ligado", "ok"
        elif tomada:
            situacao, tom = f"sem o acesso ligado, o Windows suspende depois de {tomada} min parado", "acc"
        else:
            situacao, tom = "o plano de energia não suspende o computador na tomada", ""
        return {"acordado": self.acordado.ligado, "situacao": situacao, "tom": tom,
                "suspende_tomada_min": tomada, "suspende_bateria_min": bateria,
                "abrir_com_windows": e.abre_com_windows(), "pode_abrir_com_windows": e.exe_do_programa() is not None}

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
        if not self.cofre.tem() and p.get("liberado"):
            estado = "liberado"
        return {"estado": estado, "ligado": self.ligado(), "hostname": p.get("hostname", ""),
                "liberado": p.get("liberado", ""),
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
            resumo=f"Pedido feito pelo acesso externo ({sessao['email']}). Nada foi gravado: "
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

    # ------------------------------------------------------------ eventos

    def anotar(self, **evento) -> None:
        evento.setdefault("quando", time.strftime("%Y-%m-%dT%H:%M:%S"))
        # O endereco da API vira o nome do que foi aberto ou baixado: quem le
        # "quem acessou" quer saber o documento, nao a rota.
        alvo = str(evento.get("alvo") or "")
        if self.descrever and alvo.startswith("/api/"):
            try:
                evento["alvo"] = self.descrever(alvo)
            except Exception:  # noqa: BLE001
                pass
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
        if email:
            texto = f"Alguém errou a senha de {quem} 5 vezes. A conta ficou bloqueada por {minutos} min."
        else:
            texto = f"Muitas tentativas erradas vindas de {quem}: a entrada por ele ficou fechada por {minutos} min."
        try:
            import avisos

            avisos.avisar("acesso", "Acesso externo bloqueado", texto)
        except Exception:  # noqa: BLE001 - sem aviso do Windows, o evento fica na tela
            pass

    def contas_mudaram(self) -> None:
        """Criou, mudou ou tirou conta: quem depende da lista fica sabendo."""
        for f in list(self.ao_mudar_contas):
            try:
                f()
            except Exception:  # noqa: BLE001
                pass
