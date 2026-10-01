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
        from .notas import Notas

        self.notas = Notas(self)

    # ---------------------------------------------------------------- chaves

    @property
    def ligado(self) -> bool:
        return bool((self.prefs.dados.get("nfse") or {}).get("ligado"))

    def ligar(self, ligado: bool) -> None:
        self.prefs.atualizar({"nfse": {"ligado": bool(ligado)}})

    @property
    def ambiente(self) -> str:
        return self.prestador.atual()["dados"].get("ambiente") or "producao_restrita"

    def producao_liberada(self) -> bool:
        """A liberação da N8: o ambiente da configuração em vigor é produção."""
        return self.ambiente == "producao"

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
        if guardar and not self.cofre.proteger(senha):
            raise ValueError("certificado instalado, mas não consegui guardar a senha nesta conta do Windows")
        if not guardar:
            self.cofre.dados["senha_protegida"] = ""
            self.cofre.dados["guardar_senha"] = False
            self.cofre.salvar()
        return self.certificado_para_tela()

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

    # -------------------------------------------------------------- município

    def consultar_municipio(self) -> dict:
        cmun = self.prestador.atual()["dados"].get("municipio") or ""
        if not cmun:
            raise ValueError("escolha primeiro o município do prestador")
        return self.municipios.consultar(self.cliente(), cmun, self.ambiente)

    def situacao_municipio(self) -> dict:
        cmun = self.prestador.atual()["dados"].get("municipio") or ""
        return self.municipios.situacao(cmun, self.ambiente)

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
