"""
As notas do PAVLVS: a NFS-e que o PAVLVS emite para quem assina o PAULUS.

Roda no PAULUS "da casa" (o do servidor do escritório do dono), numa tela à
parte ("Notas do PAVLVS"), e nunca nos PAULUS dos clientes: só aparece com
PAULUS_CASA_PAVLVS=1 no ambiente ou "casa_pavlvs": true no preferencias.json da
pasta de dados.

É o mesmo emissor dos escritórios (src/nfse/), numa instância SEPARADA:
banco próprio (dados/pavlvs/pavlvs.sqlite3), certificado, configuração e notas
próprios — o emissor do escritório do dono continua intacto. O que é do
PAVLVS e não do escritório:

- os clientes e os pagamentos vêm do Worker (paulus.ia.br), pela ponte
  /api/nfse-casa/* com a chave NFSE_CASA_TOKEN (worker/admin-api.md); editar
  um cliente aqui grava os dados fiscais dele no Worker;
- a nota emitida vai para o app do cliente ("Sua NFS-e de … chegou", com
  Download e XML) pelo botão "Enviar ao cliente" ou, ligado nos parâmetros,
  sozinha logo depois de emitir;
- quem emite é o titular, na tela: o clique em "Emitir" é a aprovação (não
  há fila de Aprovações aqui).
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path

log = logging.getLogger("paulus.casa_nfse")

ORIGEM = "pavlvs"
PASTA = "pavlvs"


def ligada(prefs_dados: dict | None = None) -> bool:
    if os.environ.get("PAULUS_CASA_PAVLVS") == "1":
        return True
    return bool((prefs_dados or {}).get("casa_pavlvs"))


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


class _Prefs:
    """As preferências do emissor do PAVLVS, num JSON só dele."""

    def __init__(self, caminho: Path) -> None:
        self.caminho = Path(caminho)
        self._trava = threading.Lock()
        self.dados: dict = {"nfse": {"ligado": True}, "backup": {}, "ponte": {}, "enviar_sozinho": False,
                            "vinculos": {}, "enviadas": {}}
        try:
            bruto = json.loads(self.caminho.read_text(encoding="utf-8"))
            if isinstance(bruto, dict):
                self.dados.update(bruto)
        except (OSError, ValueError):
            pass

    def atualizar(self, novo: dict) -> None:
        with self._trava:
            for k, v in (novo or {}).items():
                if isinstance(v, dict) and isinstance(self.dados.get(k), dict):
                    self.dados[k].update(v)
                else:
                    self.dados[k] = v
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.caminho.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.dados, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.caminho)


class ErroPonte(Exception):
    """O Worker não respondeu ou recusou (a frase vai para a tela)."""


class Casa:
    def __init__(self, dados_dir: Path | str) -> None:
        from base import Base
        from nfse import tabelas
        from nfse.servico import Emissor

        raiz = Path(dados_dir)
        self.pasta = raiz / PASTA
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.base = Base(self.pasta / "pavlvs.sqlite3")
        self.prefs = _Prefs(self.pasta / "preferencias.json")
        self.emissor = Emissor(self.base, self.prefs, self.pasta)
        # O Emissor aponta as tabelas oficiais para a pasta dele; elas são as
        # mesmas para os dois emissores, então voltam para a do escritório.
        tabelas.usar_pasta_de_dados(raiz / "nfse" / "tabelas")
        self.site = os.environ.get("PAULUS_SITE", "https://paulus.ia.br").rstrip("/")
        # O teste troca a ponte HTTP por uma função (metodo, caminho, corpo) -> (status, dados).
        self.ponte_local = None
        self._ultima_resposta: dict = {}

    # ------------------------------------------------------------- a ponte

    def _token(self) -> str:
        import segredos

        guardado = (self.prefs.dados.get("ponte") or {}).get("token") or ""
        if not guardado:
            return ""
        try:
            return segredos.revelar(guardado) or ""
        except Exception:  # noqa: BLE001
            return ""

    def guardar_token(self, token: str) -> None:
        import segredos

        token = str(token or "").strip()
        if not token:
            return
        guardado = segredos.proteger(token) if segredos.disponivel() else ""
        if not guardado:
            raise ValueError("não consegui guardar a chave da ponte cifrada neste computador")
        self.prefs.atualizar({"ponte": {"token": guardado, "gravado_em": _agora()}})

    def ponte(self, metodo: str, caminho: str, corpo: dict | None = None) -> dict:
        if self.ponte_local is not None:
            status, dados = self.ponte_local(metodo, caminho, corpo)
        else:
            token = self._token()
            if not token:
                raise ErroPonte("falta a chave da ponte com paulus.ia.br (Parâmetros › Ponte com o painel)")
            import requests

            try:
                r = requests.request(metodo, self.site + caminho, json=corpo, timeout=40,
                                     headers={"Authorization": f"Bearer {token}"})
            except Exception as exc:  # noqa: BLE001
                raise ErroPonte("não consegui falar com paulus.ia.br agora (sem internet?)") from exc
            status = r.status_code
            try:
                dados = r.json()
            except ValueError:
                dados = {}
        if status >= 400:
            raise ErroPonte(str((dados or {}).get("erro") or f"paulus.ia.br respondeu com erro ({status})"))
        self._ultima_resposta = dados or {}
        return dados or {}

    # ------------------------------------------------------------ clientes

    def clientes(self) -> list[dict]:
        return self.ponte("GET", "/api/nfse-casa/clientes").get("clientes") or []

    def editar_cliente(self, conta: str, tomador: dict) -> dict:
        campos = ("nome", "documento", "email", "telefone", "logradouro", "numero", "complemento", "bairro",
                  "cep", "cmun", "uf", "inscricao_municipal")
        limpo = {k: " ".join(str((tomador or {}).get(k) or "").split()) for k in campos if k in (tomador or {})}
        return self.ponte("POST", f"/api/nfse-casa/clientes/{conta}", {"tomador": limpo}).get("cliente") or {}

    def pagamentos(self) -> list[dict]:
        d = self.ponte("GET", "/api/nfse-casa/pagamentos")
        # Os dois interruptores do painel (Notas fiscais): emitir sozinho ao
        # confirmar o pagamento e mandar a nota ao app do cliente.
        if isinstance(d.get("config"), dict):
            self.prefs.atualizar({"painel": {"auto": bool(d["config"].get("auto")), "email": bool(d["config"].get("email")),
                                             "mail": bool(d["config"].get("mail"))}})
        return d.get("pagamentos") or []

    def _enviar_depois(self) -> bool:
        return bool(self.prefs.dados.get("enviar_sozinho") or (self.prefs.dados.get("painel") or {}).get("email"))

    # ------------------------------------------------- emitir sozinho (painel)

    def rodada_automatica(self, agora: float | None = None) -> list[dict]:
        """
        "Emitir ao confirmar o pagamento", ligado no painel: cada pagamento
        pendente cujo cliente tem os dados fiscais completos vira nota. O que
        falha fica anotado e só é tentado de novo 6 h depois; o pagamento que
        já tem nota aqui nunca é emitido de novo.
        """
        agora = agora or time.time()
        try:
            pags = self.pagamentos()
        except ErroPonte:
            return []
        if not (self.prefs.dados.get("painel") or {}).get("auto"):
            return []
        if not self.emissor.pode_emitir()[0]:
            return []
        ja = {v.get("pagamento") for v in (self.prefs.dados.get("vinculos") or {}).values() if v.get("pagamento")}
        tentativas = dict(self.prefs.dados.get("automaticas") or {})
        pendentes = [p for p in pags if p.get("nota") == "pendente" and str(p.get("id")) not in ja
                     and agora - float((tentativas.get(str(p.get("id"))) or {}).get("t") or 0) > 6 * 3600]
        if not pendentes:
            return []
        try:
            clientes = {c["id"]: c for c in self.clientes()}
        except ErroPonte:
            return []
        feitos = []
        for p in pendentes[:20]:
            pid = str(p["id"])
            c = clientes.get(p.get("conta"))
            tom = (c or {}).get("tomador") or {}
            falta = [k for k in ("nome", "documento", "logradouro", "bairro", "cep", "cmun") if not tom.get(k)]
            if not c or falta:
                tentativas[pid] = {"t": agora, "erro": "faltam dados fiscais do cliente: " + ", ".join(falta or ["conta"])}
                continue
            mensal = p.get("tipo") == "mensalidade"
            try:
                n = self.emitir({"conta": p["conta"], "pagamento": pid, "tomador": tom,
                                 "valor": f"{float(p.get('valor') or 0):.2f}".replace(".", ","),
                                 "descricao": "Assinatura do PAULUS — plano mensal" if mensal else "Recarga de uso do PAULUS (nuvem)",
                                 "competencia": str(p.get("quando") or "")[:7] + "-01" if p.get("quando") else ""}, quem="PAULUS (automático)")
                tentativas[pid] = {"t": agora, "nota": n["id"], "estado": n["estado"]}
                feitos.append(n)
            except ValueError as exc:
                tentativas[pid] = {"t": agora, "erro": str(exc)[:300]}
        self.prefs.atualizar({"automaticas": tentativas})
        return feitos

    def ligar_rotina(self, intervalo: int = 300) -> None:
        def laco():
            time.sleep(30)
            while True:
                try:
                    self.rodada_automatica()
                except Exception:  # noqa: BLE001 - a rotina nunca derruba o PAULUS
                    log.exception("casa_nfse: rodada automática")
                time.sleep(intervalo)

        threading.Thread(target=laco, daemon=True, name="casa-nfse-rotina").start()

    # ----------------------------------------------------------- parâmetros

    def gravar_parametros(self, dados: dict, quem: str) -> None:
        dados = dict(dados or {})
        token = dados.pop("token_ponte", "")
        if "enviar_sozinho" in dados:
            self.prefs.atualizar({"enviar_sozinho": bool(dados.pop("enviar_sozinho"))})
        if "mandar_email" in dados:
            self.prefs.atualizar({"mandar_email": bool(dados.pop("mandar_email"))})
        if token:
            self.guardar_token(token)
        prest = dados.get("prestador")
        if prest:
            self.emissor.prestador.gravar(prest, quem=quem)

    # -------------------------------------------------------------- testar

    def testar(self) -> dict:
        """A comunicação: o certificado, a Sefin (com o certificado na conexão) e a ponte com o painel."""
        from nfse.cliente import CertificadoInvalido, NaoChegou, ProducaoBloqueada, SemResposta

        e = self.emissor
        etapas = []

        def etapa(titulo, ok, detalhe=""):
            etapas.append({"titulo": titulo, "ok": bool(ok), "detalhe": detalhe})

        cert = (e.certificado_para_tela() or {})
        c = cert.get("certificado") or {}
        cert_ok = cert.get("instalado") and not c.get("erro") and not c.get("vencido")
        etapa("Certificado instalado e válido", cert_ok,
              f"{c.get('titular', '')} · até {c.get('valido_ate', '')}" if cert_ok else (c.get("erro") or cert.get("frase") or "instale o certificado"))
        cmun = e.prestador.atual()["dados"].get("municipio") or ""
        if cert_ok and not cmun:
            etapa("Servidor da Sefin (Sistema Nacional)", False, "falta a cidade do PAVLVS nos parâmetros")
        elif cert_ok:
            inicio = time.monotonic()
            try:
                r = e.cliente().parametros_convenio(cmun)
                ms = int((time.monotonic() - inicio) * 1000)
                etapa("Servidor da Sefin (Sistema Nacional)", r.status < 500,
                      f"respondeu em {ms} ms (HTTP {r.status}) · " + ("produção" if e.ambiente == "producao" else "produção restrita"))
                sit = e.consultar_municipio()
                etapa("Cidade emite pelo Sistema Nacional", sit.get("situacao") == "conveniado", sit.get("frase") or sit.get("situacao", ""))
            except (CertificadoInvalido, ProducaoBloqueada) as exc:
                etapa("Servidor da Sefin (Sistema Nacional)", False, str(exc))
            except (SemResposta, NaoChegou) as exc:
                etapa("Servidor da Sefin (Sistema Nacional)", False, f"não respondeu: {exc}")
        try:
            d = self.ponte("GET", "/api/nfse-casa/ping")
            etapa("Ponte com o painel (paulus.ia.br)", True, f"{d.get('contas', 0)} conta(s) de assinantes")
        except ErroPonte as exc:
            etapa("Ponte com o painel (paulus.ia.br)", False, str(exc))
        r = {"ok": all(x["ok"] for x in etapas), "etapas": etapas, "em": _agora()}
        self.prefs.atualizar({"ultimo_teste": r})
        return r

    # --------------------------------------------------------------- emitir

    def emitir(self, dados: dict, quem: str) -> dict:
        """A emissão manual do pop-up: cria, confere, assina e envia. Erro de conferência volta como ValueError."""
        from nfse.cliente import CertificadoInvalido, ProducaoBloqueada
        from nfse.notas import APROVADA, EMITIDA

        e = self.emissor
        pode, motivos = e.pode_emitir()
        if not pode:
            raise ValueError("ainda não dá para emitir: " + "; ".join(motivos[:4]))
        if e.ambiente == "producao" and not e.producao_liberada():
            raise ValueError("a produção não está liberada")
        tomador = dict(dados.get("tomador") or {})
        rasc = {"tomador": tomador, "valor": str(dados.get("valor") or ""), "descricao": str(dados.get("descricao") or "")}
        if dados.get("competencia"):
            rasc["competencia"] = str(dados["competencia"])[:10]
        nota = e.notas.criar(rasc, origem=ORIGEM, quem=quem)
        nota = e.notas.conferir(nota["id"])
        if nota["erros"]:
            e.notas.descartar(nota["id"], quem=quem)
            raise ValueError("a nota não passou na conferência: " + "; ".join(nota["erros"][:4]))
        conta = str(dados.get("conta") or "")
        pagamento = str(dados.get("pagamento") or "")
        vinc = dict(self.prefs.dados.get("vinculos") or {})
        vinc[str(nota["id"])] = {"conta": conta, "pagamento": pagamento}
        self.prefs.atualizar({"vinculos": vinc})
        e.notas.mudar_estado(nota["id"], APROVADA, quem, "Notas do PAVLVS: emitida pelo titular na tela",
                             aprovado_por=quem, aprovado_em=_agora())
        try:
            nota = e.envio.emitir(nota["id"], quem)
        except (CertificadoInvalido, ProducaoBloqueada) as exc:
            raise ValueError(str(exc)) from exc
        if nota["estado"] == EMITIDA and conta and self._enviar_depois():
            try:
                self.enviar(nota["id"])
            except (ErroPonte, ValueError) as exc:
                log.warning("casa_nfse: envio automático ao cliente falhou: %s", exc)
        return self.nota_para_tela(e.notas.obter(nota["id"]))

    # ------------------------------------------------------- arquivos e envio

    def pdf(self, nota: dict) -> bytes | None:
        return self.emissor.danfse_para(nota)

    def xml(self, nota: dict) -> bytes | None:
        caminho = nota.get("xml_nfse")
        if not caminho or not Path(caminho).exists():
            return None
        return Path(caminho).read_bytes()

    def enviar(self, nota_id: int) -> dict:
        """A nota ao app do cliente, pelo Worker ("Sua NFS-e de … chegou")."""
        from nfse.notas import EMITIDA

        nota = self.emissor.notas.obter(nota_id)
        if not nota or nota["estado"] != EMITIDA:
            raise ValueError("só se envia nota emitida")
        v = (self.prefs.dados.get("vinculos") or {}).get(str(nota_id)) or {}
        if not v.get("conta"):
            raise ValueError("esta nota não está ligada a uma conta de assinante: emita escolhendo o cliente da lista")
        pdf, xml = self.pdf(nota), self.xml(nota)
        if not pdf or not xml:
            raise ValueError("não achei o PDF ou o XML da nota")
        r = nota["rascunho"]
        self.ponte("POST", "/api/nfse-casa/notas", {
            "id": str(nota["id"]), "conta": v["conta"], "pagamento": v.get("pagamento") or "",
            "numero": nota.get("numero_nfse") or "", "chave": nota.get("chave") or "",
            "competencia": (r.get("competencia") or "")[:7], "valor": int(nota.get("centavos") or 0) / 100,
            "descricao": r.get("descricao") or "", "ambiente": nota["ambiente"],
            "emitida_em": nota.get("dh_proc") or nota.get("atualizado_em") or _agora(),
            "pdf_b64": base64.b64encode(pdf).decode("ascii"), "xml_b64": base64.b64encode(xml).decode("ascii"),
            "email": self._mandar_email()})
        env = dict(self.prefs.dados.get("enviadas") or {})
        env[str(nota_id)] = _agora()
        resp = self._ultima_resposta or {}
        emails = dict(self.prefs.dados.get("emails") or {})
        if resp.get("email"):
            emails[str(nota_id)] = resp["email"]
        self.prefs.atualizar({"enviadas": env, "emails": emails})
        return self.nota_para_tela(nota)

    def _mandar_email(self) -> bool:
        return bool(self.prefs.dados.get("mandar_email") or (self.prefs.dados.get("painel") or {}).get("mail"))

    # ------------------------------------------------- cancelar e substituir

    def motivos(self) -> dict:
        from nfse import tabelas

        return {"cancelamento": tabelas.dominio("motivo_cancelamento"), "substituicao": tabelas.dominio("motivo_substituicao")}

    def _avisar_cancelada(self, nota: dict, substituta: dict | None = None) -> str:
        """Diz ao Worker que a nota não vale mais (o app do cliente deixa de oferecê-la). Falha não desfaz o cancelamento."""
        v = (self.prefs.dados.get("vinculos") or {}).get(str(nota["id"])) or {}
        if not v.get("conta") or str(nota["id"]) not in (self.prefs.dados.get("enviadas") or {}):
            return ""
        corpo = {"conta": v["conta"], "email": self._mandar_email()}
        if substituta:
            corpo["substituta"] = {"numero": substituta.get("numero_nfse") or ""}
        try:
            self.ponte("POST", f"/api/nfse-casa/notas/{nota['id']}/cancelada", corpo)
            return "o app do cliente foi avisado"
        except ErroPonte as exc:
            return f"não consegui avisar o app do cliente: {exc}"

    def cancelar(self, nota_id: int, motivo: str, texto: str, quem: str) -> dict:
        from nfse.cliente import CertificadoInvalido, NaoChegou, ProducaoBloqueada, SemResposta
        from nfse.notas import CANCELADA

        e = self.emissor
        ev = e.eventos.criar_cancelamento_pavlvs(nota_id, str(motivo or ""), texto, quem)
        try:
            ev = e.eventos.enviar(ev["id"], quem)
        except (CertificadoInvalido, ProducaoBloqueada, SemResposta, NaoChegou, RuntimeError) as exc:
            raise ValueError(f"o cancelamento não saiu: {exc}") from exc
        nota = e.notas.obter(nota_id)
        if nota["estado"] != CANCELADA:
            frases = "; ".join(x.get("frase", "") for x in (ev.get("rejeicao") or []))
            raise ValueError("a Sefin não confirmou o cancelamento: " + (frases or ev.get("ultimo_erro") or "sem resposta ainda"))
        r = self.nota_para_tela(nota)
        r["aviso"] = self._avisar_cancelada(nota)
        return r

    def substituir(self, nota_id: int, motivo: str, texto: str, ajustes: dict, quem: str) -> dict:
        """A nota substituta: os dados da original com os ajustes do pop-up; a Sefin cancela a original sozinha."""
        from nfse.cliente import CertificadoInvalido, ProducaoBloqueada
        from nfse.notas import APROVADA, EMITIDA

        e = self.emissor
        original = e.notas.obter(nota_id)
        if not original or original.get("origem") != ORIGEM:
            raise ValueError("só a nota do PAVLVS se substitui por aqui")
        nova = e.eventos.criar_substituta(nota_id, str(motivo or ""), texto, quem)
        e.base.escrever("UPDATE nfse_notas SET origem = ? WHERE id = ?", (ORIGEM, nova["id"]))
        mudar = {}
        a = dict(ajustes or {})
        if a.get("tomador"):
            mudar["tomador"] = a["tomador"]
        for k in ("valor", "descricao", "competencia"):
            if a.get(k):
                mudar[k] = str(a[k])
        if mudar:
            e.notas.atualizar(nova["id"], mudar, quem=quem, gravar_no_cadastro=False)
        nova = e.notas.conferir(nova["id"])
        if nova["erros"]:
            e.notas.descartar(nova["id"], quem=quem)
            raise ValueError("a nota substituta não passou na conferência: " + "; ".join(nova["erros"][:4]))
        vinc = dict(self.prefs.dados.get("vinculos") or {})
        vinc[str(nova["id"])] = dict(vinc.get(str(nota_id)) or {})
        self.prefs.atualizar({"vinculos": vinc})
        e.notas.mudar_estado(nova["id"], APROVADA, quem, "Notas do PAVLVS: substituta emitida pelo titular na tela",
                             aprovado_por=quem, aprovado_em=_agora())
        try:
            nova = e.envio.emitir(nova["id"], quem)
        except (CertificadoInvalido, ProducaoBloqueada) as exc:
            raise ValueError(str(exc)) from exc
        if nova["estado"] != EMITIDA:
            frases = "; ".join(x.get("frase", "") for x in (nova.get("rejeicao") or []))
            raise ValueError("a Sefin não aceitou a substituta: " + (frases or nova.get("ultimo_erro") or nova["estado_rotulo"]))
        r = self.nota_para_tela(nova)
        avisos = [self._avisar_cancelada(e.notas.obter(nota_id), nova)]
        foi = str(nota_id) in (self.prefs.dados.get("enviadas") or {})
        if (vinc.get(str(nova["id"])) or {}).get("conta") and (self._enviar_depois() or foi):
            try:
                self.enviar(nova["id"])
                avisos.append("a substituta foi ao app do cliente")
            except (ErroPonte, ValueError) as exc:
                avisos.append(f"a substituta não foi ao app do cliente: {exc}")
        r["aviso"] = "; ".join(x for x in avisos if x)
        return r

    # ------------------------------------------------------------- produção

    def liberar_producao(self, quem: str) -> None:
        e = self.emissor
        pode, motivos = e.pode_emitir()
        if not pode:
            raise ValueError("ainda falta: " + "; ".join(motivos[:4]))
        testes = e.base.contar("nfse_notas", "ambiente = 'producao_restrita' AND estado IN ('emitida','cancelada')")
        if not testes:
            raise ValueError("emita antes ao menos uma nota no ambiente de testes (produção restrita)")
        if e.producao_liberada():
            return
        e.base.escrever("INSERT INTO nfse_liberacao (liberado_em, liberado_por, checklist) VALUES (?,?,?)",
                        (_agora(), quem, json.dumps([{"id": "testes", "ok": True, "detalhe": f"{testes} nota(s) de teste"}])))
        e.prestador.mudar_ambiente("producao", quem, "Notas do PAVLVS: produção liberada pelo titular")

    def voltar_para_testes(self, quem: str) -> None:
        self.emissor.producao.voltar(quem)

    # ----------------------------------------------------------------- tela

    def nota_para_tela(self, n: dict) -> dict:
        v = (self.prefs.dados.get("vinculos") or {}).get(str(n["id"])) or {}
        t = (n.get("rascunho") or {}).get("tomador") or {}
        return {"id": n["id"], "estado": n["estado"], "estado_rotulo": n["estado_rotulo"], "numero": n.get("numero_nfse") or "",
                "chave": n.get("chave") or "", "cliente": t.get("nome") or n.get("tomador_nome") or "",
                "documento": t.get("documento") or "", "valor": n["valor"], "tomador": t,
                "competencia": ((n.get("rascunho") or {}).get("competencia") or "")[:7],
                "descricao": (n.get("rascunho") or {}).get("descricao") or "", "ambiente": n["ambiente"],
                "quando": n.get("dh_proc") or n.get("atualizado_em") or "", "erro": n.get("ultimo_erro") or "",
                "conta": v.get("conta") or "", "enviada_em": (self.prefs.dados.get("enviadas") or {}).get(str(n["id"])) or "",
                "email": (self.prefs.dados.get("emails") or {}).get(str(n["id"])) or "",
                "substitui_id": n.get("substitui_id"), "substituida_por_id": n.get("substituida_por_id")}

    def para_tela(self) -> dict:
        e = self.emissor
        tela = e.para_tela()
        notas = [self.nota_para_tela(n) for n in e.notas.listar(limite=300)
                 if n["estado"] not in ("rascunho", "descartada")]
        ponte = self.prefs.dados.get("ponte") or {}
        return {**tela, "notas": notas, "ponte": {"configurada": bool(ponte.get("token")), "gravado_em": ponte.get("gravado_em", ""),
                                                  "site": self.site},
                "enviar_sozinho": bool(self.prefs.dados.get("enviar_sozinho")),
                "mandar_email": bool(self.prefs.dados.get("mandar_email")), "motivos": self.motivos(),
                "painel": self.prefs.dados.get("painel") or {},
                "automaticas": self.prefs.dados.get("automaticas") or {},
                "producao_liberada": e.producao_liberada(), "ultimo_teste": self.prefs.dados.get("ultimo_teste") or {}}

