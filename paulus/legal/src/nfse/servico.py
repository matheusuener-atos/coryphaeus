"""
O emissor de NFS-e montado sobre o estado do PAULUS.

Junta o que cada parte faz sozinha: a configuração fiscal (prestador.py), o
município (municipio.py), o certificado da nota e o cliente HTTP
(cliente.py). As rotas (src/rotas_nfse.py) só falam com isto.

O certificado da nota é um cofre próprio, separado do de assinar PDF: quem
assina petição costuma ser o e-CPF do advogado, e quem emite nota é o
e-CNPJ da sociedade. Só A1 em arquivo serve — o TLS do Python precisa da
chave, e o certificado "do Windows, não exportável" não a entrega.
"""

from __future__ import annotations

from pathlib import Path

import certificado

from . import cliente as cliente_mod
from . import tabelas
from .municipio import Municipios
from .prestador import AMBIENTES, Prestador

AVISAR_CERTIFICADO_DIAS = 30


class Emissor:
    def __init__(self, base, prefs, dados_dir: Path | str) -> None:
        self.base = base
        self.prefs = prefs
        self.pasta = Path(dados_dir) / "nfse"
        self.prestador = Prestador(base)
        self.municipios = Municipios(base)
        self.cofre = certificado.Cofre(self.pasta / "certificado" / "cofre.json", self.pasta / "certificado")
        # O teste troca a rede pelo servidor simulado (N3) por aqui.
        self.transporte = None
        tabelas.usar_pasta_de_dados(self.pasta / "tabelas")
        from .emissao import Envio
        from .eventos import Eventos
        from .notas import Notas

        self.notas = Notas(self)
        self.envio = Envio(self)
        self.eventos = Eventos(self)
        from .contador import Contador
        from .recorrencia import Recorrencias

        self.contador = Contador(self)
        self.recorrencias = Recorrencias(self)
        from .producao import Producao

        self.producao = Producao(self)
        from .teste import Teste

        self.teste = Teste(self)
        # O estado do programa (para Aprovações), posto pelas rotas; e o dia em
        # que a rotina diária já rodou.
        self.estado_app = None
        self._rotina_em = ""
        # A substituta emitida marca a original antes do resto (Acervo, e-mail…).
        self.envio.ao_emitir.append(self.eventos.depois_de_emitir)

    # ---------------------------------------------------------------- chaves

    @property
    def ligado(self) -> bool:
        return bool((self.prefs.dados.get("nfse") or {}).get("ligado"))

    def ligar(self, ligado: bool) -> None:
        self.prefs.atualizar({"nfse": {"ligado": bool(ligado)}})

    @property
    def ambiente(self) -> str:
        return self.prestador.atual()["dados"].get("ambiente") or "producao_restrita"

    def liberacao(self) -> dict | None:
        """A liberação da produção em vigor (N8), ou None."""
        return self.base.um("SELECT * FROM nfse_liberacao WHERE revogado_em = '' ORDER BY id DESC LIMIT 1")

    def producao_liberada(self) -> bool:
        """Só com a liberação do titular registrada (N8). Sem ela, o cliente recusa produção."""
        return self.liberacao() is not None

    # ----------------------------------------------------------- certificado

    def instalar_certificado(self, nome: str, conteudo: bytes, senha: str, guardar: bool) -> dict:
        if Path(nome).suffix.lower() not in (".pfx", ".p12"):
            raise ValueError("a nota fiscal usa o certificado A1 em arquivo (.pfx ou .p12)")
        anterior = self.cofre.arquivo.read_bytes() if self.cofre.arquivo and self.cofre.arquivo.exists() else None
        self.cofre.guardar_arquivo(nome, conteudo)
        lido = self.cofre.abrir(senha)
        if lido.erro:
            # Não deixa um .pfx que não abre no lugar do que funcionava.
            if anterior is not None:
                self.cofre.guardar_arquivo(nome, anterior)
            else:
                self.cofre.remover()
            raise ValueError(lido.erro)
        self.cofre.lembrar(senha)
        self._preencher_do_certificado()
        if guardar and not self.cofre.proteger(senha):
            raise ValueError("certificado instalado, mas não consegui guardar a senha nesta conta do Windows")
        if not guardar:
            self.cofre.dados["senha_protegida"] = ""
            self.cofre.dados["guardar_senha"] = False
            self.cofre.salvar()
        return self.certificado_para_tela()

    def _preencher_do_certificado(self) -> None:
        """O CNPJ (ou CPF) e o nome do certificado preenchem a configuração, se ainda estão vazios."""
        cert = self.cofre.certificado()
        if not cert or cert.erro:
            return
        d = cert.to_dict()
        doc = "".join(ch for ch in (d.get("documento") or "") if ch.isalnum())
        nome = str(d.get("titular") or "").split(":")[0].strip()
        atual = self.prestador.atual()["dados"]
        novo = {}
        if doc and not atual.get("documento"):
            novo["documento"] = doc
        if nome and not atual.get("razao_social"):
            novo["razao_social"] = nome
        if novo:
            try:
                self.prestador.gravar(novo, quem="titular", motivo="dados do certificado")
            except ValueError:
                pass

    def desbloquear(self, senha: str, guardar: bool = False) -> dict:
        lido = self.cofre.abrir(senha)
        if lido.erro:
            raise ValueError(lido.erro)
        self.cofre.lembrar(senha)
        if guardar:
            self.cofre.proteger(senha)
        return self.certificado_para_tela()

    def remover_certificado(self) -> None:
        self.cofre.remover()

    def certificado_para_tela(self) -> dict:
        if not self.cofre.instalado:
            return {"instalado": False, "frase": "Nenhum certificado A1 para a nota fiscal."}
        cert = self.cofre.certificado()
        dados = cert.to_dict() if cert else {}
        doc_cert = "".join(ch for ch in (dados.get("documento") or "") if ch.isalnum())
        doc_prest = self.prestador.atual()["dados"].get("documento") or ""
        avisos = []
        if cert and not cert.erro:
            dias = cert.dias_restantes
            if cert.vencido:
                avisos.append("O certificado venceu: a Sefin recusa a nota (regra E1203).")
            elif dias is not None and dias <= AVISAR_CERTIFICADO_DIAS:
                avisos.append(f"O certificado vence em {dias} dia(s). Renove antes para não parar a emissão.")
            if not cert.icp_brasil:
                avisos.append("O certificado não parece ser ICP-Brasil: a Sefin só aceita ICP-Brasil (E1208).")
            if doc_prest and doc_cert and doc_cert != doc_prest:
                avisos.append("O certificado é de outro CNPJ/CPF que não o do prestador configurado: "
                              "a Sefin exige o certificado do emitente (E0718).")
        return {
            "instalado": True,
            "certificado": dados,
            "precisa_senha": bool(cert and cert.erro and "senha" in cert.erro),
            "senha_guardada": bool(self.cofre.dados.get("senha_protegida")),
            "minutos_restantes": self.cofre.minutos_restantes,
            "avisos": avisos,
            "frase": (f"{dados.get('titular', '')} · válido até {dados.get('valido_ate', '')}"
                      if dados and not dados.get("erro") else (dados.get("erro") or "")),
        }

    def _pfx_e_senha(self) -> tuple[bytes, str]:
        alvo = self.cofre.arquivo
        if not alvo or not alvo.exists():
            raise cliente_mod.CertificadoInvalido("instale o certificado A1 da nota em Configurações › Nota fiscal")
        senha = self.cofre.senha_agora()
        if not senha:
            raise cliente_mod.CertificadoInvalido("preciso da senha do certificado da nota")
        return alvo.read_bytes(), senha

    def cliente(self, ambiente: str | None = None) -> cliente_mod.Cliente:
        ambiente = ambiente or self.ambiente
        liberada = self.producao_liberada()
        if self.transporte is not None:
            return cliente_mod.Cliente(ambiente, producao_liberada=liberada, transporte=self.transporte)
        pfx, senha = self._pfx_e_senha()
        return cliente_mod.Cliente(ambiente, pfx, senha, producao_liberada=liberada)

    def avisos_extras(self, hoje) -> list[dict]:
        """
        O que mais a nota fiscal põe no carrossel, cada um com id estável (o
        mesmo fato é sempre o mesmo aviso, e o "visto" vale para ele):
        conferência do mês (N6), recorrência do mês, certificado a 30, 7 e 1
        dia de vencer, fila de envio parada, parâmetros do município que
        mudaram e esquema novo publicado no portal.
        """
        if not self.ligado:
            return []
        saida: list[dict] = []
        try:
            saida += [{"id": a["id"], "titulo": a["titulo"], "detalhe": a.get("detalhe", ""), "nota_id": a.get("nota_id")}
                      for a in self.contador.conferir(hoje.isoformat()[:7], hoje)
                      if a["tipo"] not in ("recebimento_sem_nota", "certificado")]
        except Exception:  # noqa: BLE001 - conferência que falha não derruba o carrossel
            pass
        saida += self.recorrencias.avisos(hoje)
        cert = (self.certificado_para_tela() or {}).get("certificado") or {}
        dias = cert.get("dias_restantes")
        if dias is not None and dias <= 30:
            faixa = 1 if dias <= 1 else (7 if dias <= 7 else 30)
            quando = "vencido" if dias < 0 else ("vence amanhã" if dias <= 1 else f"vence em {dias} dias")
            saida.append({"id": f"nfse:certificado:{faixa}:{cert.get('valido_ate', '')}",
                          "titulo": "Certificado da nota fiscal " + quando,
                          "detalhe": f"válido até {cert.get('valido_ate', '')}: renove para não parar a emissão"})
        from .notas import AGUARDANDO_CONFIRMACAO, NA_FILA

        for n in self.notas.listar((NA_FILA, AGUARDANDO_CONFIRMACAO), limite=50):
            if int(n.get("esperas") or 0) >= 3:
                saida.append({"id": f"nfse:fila_parada:{n['id']}",
                              "titulo": f"A fila de envio está parada — nota de {n.get('tomador_nome') or 'tomador'}",
                              "detalhe": f"{n['esperas']} tentativas sem resposta; " + (n.get("ultimo_erro") or "")[:100],
                              "nota_id": n["id"]})
        cmun = self.prestador.atual()["dados"].get("municipio") or ""
        u = self.municipios.ultima(cmun, self.ambiente) if cmun else None
        if u and u.get("mudou_em"):
            saida.append({"id": f"nfse:municipio:{cmun}:{u['mudou_em'][:10]}",
                          "titulo": "Os parâmetros do município mudaram no Sistema Nacional",
                          "detalhe": (u.get("anterior") or "")[:160]})
        for nome in self.documentacao().get("novos") or []:
            saida.append({"id": f"nfse:layout:{nome}", "titulo": "O portal da NFS-e publicou esquema novo",
                          "detalhe": f"{nome}: o PAULUS precisa ser atualizado para ele"})
        return saida

    # --------------------------------------------------------- rotina diária

    def documentacao(self) -> dict:
        import json

        try:
            return json.loads((self.pasta / "documentacao.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def rotina_diaria(self, hoje=None, baixar=None) -> dict:
        """Uma vez por dia: recorrências, reconsulta mensal do município e a documentação."""
        import json
        from datetime import date, datetime, timedelta

        hoje = hoje or date.today()
        if self._rotina_em == hoje.isoformat() or not self.ligado:
            return {}
        self._rotina_em = hoje.isoformat()
        feito: dict = {}
        if self.estado_app is not None:
            feito["recorrencias"] = self.recorrencias.rodar(self.estado_app, hoje)
        sit = self.situacao_municipio()
        if sit.get("reconsultar") and sit.get("situacao") != "nao_consultado":
            try:
                feito["municipio"] = self.consultar_municipio()
            except Exception as exc:  # noqa: BLE001 - sem certificado ou sem rede: tenta amanhã
                feito["municipio"] = {"erro": str(exc)[:200]}
        doc = self.documentacao()
        velha = (not doc.get("conferido_em")
                 or (datetime.now() - datetime.fromisoformat(doc["conferido_em"])) > timedelta(days=30))
        if velha:
            from .recorrencia import conferir_documentacao

            r = conferir_documentacao(baixar)
            if r.get("ok"):
                self.pasta.mkdir(parents=True, exist_ok=True)
                (self.pasta / "documentacao.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
            feito["documentacao"] = r
        return feito

    def papeis_a_emitir(self, mes: str) -> list[dict]:
        """Os recebimentos do mês sem nota (a mesma lista do Financeiro)."""
        import escritorio

        return escritorio.PapeisFiscais(self.base).a_emitir(mes)

    # ------------------------------------------------------------ DANFSe

    def danfse_para(self, nota: dict) -> bytes | None:
        """O PDF do DANFSe da nota emitida, gerado do XML (NT 008)."""
        from . import danfse

        caminho = nota.get("xml_nfse") or ""
        if not caminho or not Path(caminho).exists():
            return None
        return danfse.gerar(Path(caminho).read_bytes())

    # ------------------------------------------------- o contrato da API

    @property
    def _arquivo_contrato(self) -> Path:
        return self.pasta / "contrato.json"

    def contrato(self) -> dict:
        import json

        try:
            return json.loads(self._arquivo_contrato.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def conferir_contrato(self, cliente=None) -> dict:
        """
        Os nomes dos campos JSON (cliente.CAMPOS) conferidos no Swagger
        oficial, que só abre com o certificado (docs/PROGRESSO-NFSE.md, N0).
        """
        import json
        from datetime import datetime

        cliente = cliente or self.cliente()
        r = cliente.conferir_contrato()
        r["conferido_em"] = datetime.now().isoformat(timespec="seconds")
        r["ambiente"] = cliente.ambiente
        self.pasta.mkdir(parents=True, exist_ok=True)
        self._arquivo_contrato.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        return r

    def contrato_trava(self) -> str:
        """Por que o envio real está travado pelo contrato (vazio = não está)."""
        c = self.contrato()
        if c.get("fonte") and c.get("faltam"):
            return ("o Swagger oficial não tem os campos " + ", ".join(c["faltam"]) +
                    ": o envio fica travado até alguém conferir (docs/PROGRESSO-NFSE.md, N3)")
        return ""

    # -------------------------------------------------------------- município

    def consultar_municipio(self) -> dict:
        cmun = self.prestador.atual()["dados"].get("municipio") or ""
        if not cmun:
            raise ValueError("escolha primeiro o município do prestador")
        return self.municipios.consultar(self.cliente(), cmun, self.ambiente)

    def situacao_municipio(self) -> dict:
        cmun = self.prestador.atual()["dados"].get("municipio") or ""
        sit = self.municipios.situacao(cmun, self.ambiente)
        if sit.get("situacao") == "conveniado" and not self.ligado:
            # O município emite pelo nacional, mas a emissão daqui está
            # desligada: a frase não pode dizer que "dá para emitir" já.
            m = tabelas.municipio(cmun) or {}
            sit = dict(sit, frase=f"{m.get('nome', cmun)}/{m.get('uf', '')} tem convênio ativo com o Sistema Nacional "
                                  "da NFS-e: ligando a emissão aqui em cima, as notas passam a sair pelo PAULUS.")
        return sit

    # ------------------------------------------------------------------- tela

    def pode_emitir(self) -> tuple[bool, list[str]]:
        """Se dá para emitir agora, e por que não."""
        motivos: list[str] = []
        if not self.ligado:
            motivos.append("a emissão de nota fiscal está desligada em Configurações › Nota fiscal")
        tela = self.prestador.para_tela()
        motivos += [f"falta {f}" for f in tela["faltas"]]
        if not self.cofre.instalado:
            motivos.append("falta o certificado A1 da nota")
        mun = self.situacao_municipio()
        if not mun["pode_emitir"]:
            motivos.append(mun["frase"])
        return (not motivos), motivos

    def para_tela(self) -> dict:
        pode, motivos = self.pode_emitir()
        return {
            "ligado": self.ligado,
            "ambiente": self.ambiente,
            "ambiente_rotulo": AMBIENTES.get(self.ambiente, ""),
            "prestador": self.prestador.para_tela(),
            "certificado": self.certificado_para_tela(),
            "municipio": self.situacao_municipio(),
            "pode_emitir": pode,
            "motivos": motivos,
        }
