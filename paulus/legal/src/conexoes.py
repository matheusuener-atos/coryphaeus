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

A sessao fica na pasta do programa. Apagar e apagar de verdade: os dados do
site somem e o WhatsApp pede o codigo de novo.

Onde ela fica: o navegador embutido (WebView2) guarda tudo num perfil so, em
sessoes/EBWebView - a janela do programa e a do WhatsApp dividem esse perfil.
O que e do WhatsApp e o banco do site (IndexedDB, por origem); ele nasce
quando a pagina abre, mesmo antes de ler o codigo. Por isso a tela diz
"sessao guardada", e nao "conectado": daqui nao da para saber se o celular
ainda reconhece este computador.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import campos_br

# O unico endereco que a janela embutida abre.
WHATSAPP = "https://web.whatsapp.com"
WHATSAPP_ENVIO = "https://web.whatsapp.com/send"

# O banco do site dentro do perfil do WebView2 (ver o cabecalho).
PERFIL = Path("EBWebView") / "Default"
BANCO_DO_SITE = ("IndexedDB/https_web.whatsapp.com_0.indexeddb.leveldb",
                 "IndexedDB/https_web.whatsapp.com_0.indexeddb.blob")

# A janela ao lado: larga o bastante para a lista e a conversa do WhatsApp
# aparecerem juntas; abaixo das minimas, os dois lado a lado nao servem.
LARGURA_AO_LADO = 820
LARGURA_MINIMA_DO_PROGRAMA = 760
LARGURA_MINIMA_DO_WHATSAPP = 560

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

    Numero que nao da conversa volta vazio, em vez de um endereco que abre
    em branco: o brasileiro tem de fechar pela regra da tela
    (src/campos_br.py) - DDD e numero, e 0800 nao tem WhatsApp -; o de fora
    (com + ou 00 na frente) tem de 8 a 15 digitos, o tamanho do padrao E.164.
    """
    texto = str(bruto or "").strip()
    digitos = RE_SO_DIGITOS.sub("", texto)
    if not digitos:
        return ""
    de_fora = texto.startswith("+")
    if digitos.startswith("00"):
        digitos, de_fora = digitos[2:], True
    # O de fora primeiro: "+1 919 555 1234" tambem teria cara de celular daqui.
    if de_fora and not digitos.startswith("55"):
        return digitos if 8 <= len(digitos) <= 15 else ""
    nacional = digitos[2:] if len(digitos) > 11 and digitos.startswith("55") else digitos
    if (len(nacional) in (10, 11) and not nacional.startswith(("0800", "0300"))
            and campos_br.telefone_valido(nacional)):
        return ddi + nacional
    return ""


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


def lugar_ao_lado(x: int, y: int, largura: int, altura: int) -> dict:
    """
    Divide o espaco da janela do programa em dois: o programa a esquerda, o
    WhatsApp a direita, na mesma altura - como o Windows faz ao encaixar duas
    janelas. Com a tela estreita demais para os dois, o WhatsApp vem por cima,
    no lado direito, e o programa fica como estava (`programa` vazio).
    """
    # O notebook de 1366 de largura e o caso comum: o programa fica com o que
    # precisa e o WhatsApp com o resto, ainda com lista e conversa juntas.
    lado = min(LARGURA_AO_LADO, largura - LARGURA_MINIMA_DO_PROGRAMA)
    if lado < LARGURA_MINIMA_DO_WHATSAPP:
        lado = min(LARGURA_AO_LADO, largura)
        return {"programa": None, "whatsapp": (x + largura - lado, y, lado, altura)}
    return {"programa": (x, y, largura - lado, altura), "whatsapp": (x + largura - lado, y, lado, altura)}


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

    def pastas_da_sessao(self) -> list[Path]:
        """O banco do site no perfil do WebView2 e a pasta antiga sessoes/whatsapp."""
        perfil = self.pasta_sessoes / PERFIL
        return [perfil / p for p in BANCO_DO_SITE] + [self.pasta_sessoes / "whatsapp"]

    def sessao(self, servico: str = "whatsapp") -> Sessao:
        pastas = [p for p in self.pastas_da_sessao() if p.exists()]
        if not pastas:
            return Sessao(servico=servico, pasta=str(self.pasta_sessoes))

        total = 0
        recente = 0.0
        for pasta in pastas:
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
            pasta=str(self.pasta_sessoes),
            existe=True,
            tamanho_kb=round(total / 1024),
            ultimo_acesso=datetime.fromtimestamp(recente).isoformat(timespec="seconds") if recente else "",
        )

    def apagar_sessao(self, servico: str = "whatsapp") -> bool:
        """
        Apaga de verdade: os dados do site somem e o serviço pede o código de novo.

        Com o programa aberto, os arquivos estao presos pelo navegador
        embutido: quem apaga ali e o proprio navegador (api.py pede antes de
        chamar isto). Aqui sai o que sobrou, e a resposta e o que ficou no
        disco, nao o que se tentou.
        """
        achadas = [p for p in self.pastas_da_sessao() if p.exists()]
        if not achadas:
            return False
        for pasta in achadas:
            shutil.rmtree(pasta, ignore_errors=True)
        return not any(p.exists() for p in achadas)

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
                {"faz": True, "texto": "Abrir uma janela só, presa a este endereço, ao lado do Paulus, com sessão própria nesta máquina."},
                {"faz": True, "texto": "Preparar a mensagem com o número e o texto já preenchidos."},
                {"faz": True, "texto": "Anexar um arquivo do Acervo — eu mostro o arquivo na pasta, você arrasta para a conversa."},
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
                "Esta é a única tela do Paulus que vai para a internet. O site carrega o que "
                "o site carrega; eu não copio nada dele para cá."
            ),
        }
