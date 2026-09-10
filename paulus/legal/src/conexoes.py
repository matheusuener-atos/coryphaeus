"""
PAULUS - Conexoes.

O navegador embutido para os servicos que o escritorio ja usa - hoje, o
WhatsApp Web.

Esta e a unica tela do programa que vai para a internet, e por isso ela diz
isso em letras grandes. O resto do PAULUS roda desligado; aqui voce entra na
sua conta, como faria no navegador, e o site carrega o que o site carrega.

O que o programa faz e o que ele NAO faz, e a distincao importa:

FAZ - abre uma janela separada, presa a um endereco so, com sessao propria
guardada nesta maquina. Prepara a mensagem com o texto e o numero ja
preenchidos, pelo endereco de conversa que o proprio WhatsApp publica, e deixa
voce apertar enviar.

NAO FAZ - nao clica em enviar por voce, nao le suas conversas, nao mexe na
pagina. Automatizar o WhatsApp Web significa dirigir a tela de um site de
terceiro: quebra a cada mudanca de layout, e conta pesada demais quando o preco
de errar e a conta de WhatsApp do escritorio ser derrubada. O wireframe promete
"eu digito e mostro; o envio so sai depois do seu sim" - o que esta aqui e
exatamente isso, e nada alem.

A sessao fica na pasta do programa. Apagar e apagar de verdade: a pasta some e
o WhatsApp pede o codigo de novo.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

# O unico endereco que a janela embutida abre.
WHATSAPP = "https://web.whatsapp.com"
WHATSAPP_ENVIO = "https://web.whatsapp.com/send"

SERVICOS = [
    {
        "id": "whatsapp",
        "nome": "WhatsApp Web",
        "endereco": WHATSAPP,
        "explica": "Você entra com a sua conta, lendo o código com o celular, como faria no navegador.",
        "pronto": True,
    },
]

RE_SO_DIGITOS = re.compile(r"\D")


def numero_whatsapp(bruto: str, ddi: str = "55") -> str:
    """
    Normaliza o telefone para o formato que o WhatsApp espera.

    "(62) 99999-8888" vira "5562999998888". Sem isso o endereco de conversa
    abre em branco e a pessoa conclui que o programa esta quebrado, quando o
    problema era um parenteses.
    """
    digitos = RE_SO_DIGITOS.sub("", bruto or "")
    if not digitos:
        return ""
    if digitos.startswith("00"):
        digitos = digitos[2:]
    # Numero brasileiro sem DDI: 10 digitos (fixo) ou 11 (celular).
    if len(digitos) in (10, 11):
        digitos = ddi + digitos
    return digitos


def link_de_conversa(telefone: str, texto: str = "") -> str:
    """
    O endereco de conversa que o proprio WhatsApp publica.

    E o caminho estavel: nao depende do layout da pagina, nao quebra quando o
    site muda. Abre a conversa com o texto ja escrito; apertar enviar continua
    sendo com a pessoa.
    """
    numero = numero_whatsapp(telefone)
    if not numero:
        return ""
    endereco = f"{WHATSAPP_ENVIO}?phone={numero}"
    if texto:
        endereco += "&text=" + quote(texto)
    return endereco


@dataclass
class Sessao:
    servico: str = "whatsapp"
    pasta: str = ""
    existe: bool = False
    tamanho_kb: int = 0
    ultimo_acesso: str = ""

    def to_dict(self) -> dict:
        return {
            "servico": self.servico,
            "pasta": self.pasta,
            "existe": self.existe,
            "tamanho_kb": self.tamanho_kb,
            "ultimo_acesso": self.ultimo_acesso,
        }


class Conexoes:
    """
    A sessao do navegador embutido e o registro do que foi preparado aqui.

    O registro guarda para quem e quando - nunca o texto da mensagem. O texto
    ja esta na conversa do WhatsApp; repetir aqui seria uma segunda copia da
    conversa do escritorio, guardada sem ninguem ter pedido.
    """

    def __init__(self, caminho: Path, pasta_sessoes: Path) -> None:
        self.caminho = Path(caminho)
        self.pasta_sessoes = Path(pasta_sessoes)
        self.itens: list[dict] = []
        if self.caminho.exists():
            try:
                bruto = json.loads(self.caminho.read_text(encoding="utf-8"))
                self.itens = bruto.get("envios", []) if isinstance(bruto, dict) else []
            except (json.JSONDecodeError, OSError):
                self.itens = []

    # ------------------------------------------------------------ sessao

    def sessao(self, servico: str = "whatsapp") -> Sessao:
        pasta = self.pasta_sessoes / servico
        if not pasta.exists():
            return Sessao(servico=servico, pasta=str(pasta))

        total = 0
        recente = 0.0
        for arquivo in pasta.rglob("*"):
            if arquivo.is_file():
                try:
                    info = arquivo.stat()
                except OSError:
                    continue
                total += info.st_size
                recente = max(recente, info.st_mtime)

        return Sessao(
            servico=servico,
            pasta=str(pasta),
            existe=True,
            tamanho_kb=round(total / 1024),
            ultimo_acesso=datetime.fromtimestamp(recente).isoformat(timespec="seconds") if recente else "",
        )

    def apagar_sessao(self, servico: str = "whatsapp") -> bool:
        """Apaga de verdade: a pasta some e o serviço pede o código de novo."""
        pasta = self.pasta_sessoes / servico
        if not pasta.exists():
            return False
        shutil.rmtree(pasta, ignore_errors=True)
        return not pasta.exists()

    # ----------------------------------------------------------- registro

    def anotar(self, para: str, nome: str = "", anexo: str = "") -> dict:
        item = {
            "quando": datetime.now().isoformat(timespec="seconds"),
            "para": numero_whatsapp(para),
            "nome": nome,
            "anexo": Path(anexo).name if anexo else "",
        }
        self.itens.insert(0, item)
        self.salvar()
        return item

    def salvar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.write_text(
            json.dumps({"versao": 1, "envios": self.itens[:300]}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    def para_tela(self) -> dict:
        return {
            "servicos": SERVICOS,
            "sessao": self.sessao().to_dict(),
            "envios": self.itens[:20],
            "o_que_faco": [
                {"faz": True, "texto": "Abrir uma janela presa só a este endereço, com sessão própria nesta máquina."},
                {"faz": True, "texto": "Preparar a mensagem com o número e o texto já preenchidos."},
                {"faz": True, "texto": "Anexar um arquivo da biblioteca — eu abro a pasta, você arrasta na conversa."},
                {"faz": False, "texto": "Apertar enviar por você."},
                {"faz": False, "texto": "Ler as suas conversas."},
            ],
            "porque_nao": (
                "Automatizar o WhatsApp Web significa dirigir a tela de um site de terceiro. "
                "Quebra a cada mudança de layout, e o preço de errar é a conta de WhatsApp do "
                "escritório ser derrubada. Uso o endereço de conversa que o próprio WhatsApp "
                "publica: ele não quebra, e apertar enviar continua sendo seu."
            ),
            "aviso_internet": (
                "Esta é a única tela do PAULUS que vai para a internet. O site carrega o que "
                "o site carrega; eu não copio nada dele para cá."
            ),
        }
