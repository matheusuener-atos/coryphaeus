"""
PAULUS - Preferencias.

O que hoje esta espalhado por linha de comando e variavel de ambiente passa a
morar num arquivo: pastas do acervo, modelo em uso, seus dados profissionais e
o que o assistente pode fazer sozinho.

A parte que mais importa e a autonomia. Cada chave aqui responde a mesma
pergunta: isto acontece direto, ou vai para a fila de aprovacao? Ligar uma
delas e uma decisao consciente da pessoa, e por isso ela mora num lugar visivel
em vez de num padrao escondido no codigo.
"""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from pathlib import Path

import campos_br

# Os campos de documento e telefone das preferencias, com o tipo de cada um
# (o mesmo data-campo da tela) e o nome que vai no aviso.
_CAMPOS_CONFERIDOS = (
    ("pessoa", "cpf", "cpf"),
    ("pessoa", "telefone", "telefone"),
    ("escritorio", "cnpj", "cnpj"),
)
_NOME_DO_CAMPO = {
    ("pessoa", "cpf"): "seu CPF",
    ("pessoa", "telefone"): "seu telefone",
    ("escritorio", "cnpj"): "CNPJ do escritório",
}

# Cada permissao diz o que passa a acontecer sem parar na fila. O padrao e
# sempre o mais cauteloso: nada com efeito externo sai sozinho.
AUTONOMIA = [
    {
        "chave": "ler_pastas",
        "titulo": "Ler as pastas incluídas",
        "explica": "Abrir e indexar os documentos das pastas que você escolheu. Não altera arquivo.",
        "padrao": True,
        "travada": False,
    },
    {
        "chave": "organizar_mover",
        "titulo": "Mover arquivos sem pedir",
        "explica": "Aplicar o plano de organização direto. Desligado, cada lote espera seu sim na fila.",
        "padrao": False,
        "travada": False,
    },
    {
        "chave": "assinar",
        "titulo": "Assinar documentos sem revisar",
        "explica": "Usar o certificado sem passar pela fila. Assinatura tem valor jurídico: só ligue sabendo disso.",
        "padrao": False,
        "travada": False,
    },
    {
        "chave": "enviar_mensagem",
        "titulo": "Enviar e-mail e mensagem sem confirmar",
        "explica": "Mandar o que foi escrito direto ao destinatário, sem você revisar antes.",
        "padrao": False,
        "travada": False,
    },
    {
        "chave": "modelo_nuvem",
        "titulo": "Usar modelo em nuvem quando faltar memória",
        "explica": (
            "Indisponível de propósito. O programa promete que nenhum documento sai desta "
            "máquina, e mandar o texto para um modelo remoto quebraria exatamente isso."
        ),
        "padrao": False,
        "travada": True,
    },
]

PADRAO: dict = {
    "pastas": [],
    # Pastas lidas pelo Acervo alem da pasta do programa: para onde o
    # Organizar moveu documentos. Sem isso, o que foi organizado sumia da
    # tela Documentos - estava no disco, mas fora do que o indice le.
    "pastas_acervo": [],
    # Documentos tirados do Acervo sem apagar (o arquivo fica no disco, so nao
    # e lido). Tem de estar aqui: _fundir descarta chave que o padrao nao
    # conhece, e o que foi tirado voltaria ao reabrir o programa.
    "acervo_fora": [],
    # A conta Google alem do Gmail (src/google_servicos.py): qual conta, se a
    # Agenda sincroniza e mostra os eventos de la, a pasta PAULUS no Drive, e
    # o resultado da ultima sincronizacao.
    "google": {"conta": "", "agenda_sincronizar": False, "agenda_mostrar": False,
               "drive_pasta": "", "ultimo_sinc": "", "erro": ""},
    # A calibracao compartilhada (src/calibracao_remota.py): desligada de
    # fabrica. Ligada, as medidas desta maquina vao ao site do PAULUS e as de
    # outras maquinas voltam para melhorar a estimativa dos modelos.
    "calibracao": {"participar": False, "ultimo_envio": "", "ultima_leitura": "", "erro": ""},
    # Avisos do Windows (src/avisos.py): a notificacao do canto da tela e o
    # botao piscando na barra de tarefas, para lembretes e ciclo de foco.
    "avisos_windows": True,
    # Quais avisos, um a um (avisos.TIPOS). Cada chave precisa estar aqui:
    # _fundir so grava o que o padrao ja conhece.
    "avisos_tipos": {"bem_estar": True, "resposta": True, "aprovacao": True,
                     "gravacao": True, "agenda": True},
    "modelo": "",
    # A atualizacao (src/atualizacao.py): ver uma vez por dia se ha versao
    # nova em paulus.ia.br/atualizacao.json e, com avisar_antes, perguntar
    # antes de instalar; sem ele, baixa sozinho e instala ao fechar.
    "atualizacoes": {"verificar": True, "avisar_antes": True, "ultima_consulta": "", "erro": ""},
    # Os modulos do menu (assistente de configuracao, passo Modulos, e
    # Configuracoes › Modulos). Desligado some do menu desta maquina; o
    # Assistente, Apoiar e Configuracoes ficam sempre.
    "modulos": {"servicos": True, "gravacoes": True, "agenda": True, "acervo": True, "documentos": True,
                "assinatura": True, "email": True, "financeiro": True, "cadastros": True, "aprovacoes": True,
                "foco": True},
    # Que modelo faz cada tarefa (src/modelos.py). Vazio: o modelo padrao.
    "tarefas_modelo": {"conversa": "", "juiz": "", "email": "", "redacao": "", "resumos": "", "leitura": ""},
    "devagar": False,
    "autonomia": {a["chave"]: a["padrao"] for a in AUTONOMIA},
    "disponibilidade": {
        "dias": [0, 1, 2, 3, 4],
        "inicio": "09:00",
        "fim": "18:00",
        "almoco_inicio": "12:00",
        "almoco_fim": "13:30",
        "intervalo_min": 15,
        "mesmo_dia": True,
    },
    # Timbre no PDF: desligado por padrao. Uma minuta interna com papel
    # timbrado parece peca protocolada, e o dado pode nem estar preenchido.
    "timbre_no_pdf": False,
    # A camada de inteligencia de documentos (legal-document/v0). Ligada, ela
    # responde do metadata o que ja foi lido uma vez; desligada, o programa
    # volta a ser exatamente o de antes. A chave existe para isso: para dar
    # para voltar atras a qualquer momento, e para medir o ganho ligando e
    # desligando na mesma maquina, com as mesmas perguntas.
    "inteligencia": True,
    # Animacoes reduzidas: quem sente enjoo com movimento na tela, ou trabalha
    # num notebook que engasga, desliga aqui. Fica guardado nas preferencias
    # (e nao so no navegador) porque e escolha da pessoa, nao da maquina.
    "animacoes_reduzidas": False,
    "pessoa": {
        "nome": "",
        "cpf": "",
        "oab": "",
        "telefone": "",
        "email": "",
        "endereco": "",
        "usar_na_qualificacao": True,
    },
    # O escritorio, separado da pessoa: o nome entra nos recibos da folha;
    # CNPJ, OAB da sociedade e rodape ficam guardados para o timbre.
    "escritorio": {
        "nome": "",
        "cnpj": "",
        "oab": "",
        "rodape": "",
    },
    # O modelo de voz (Whisper) que transcreve as gravacoes nesta maquina:
    # "turbo" acerta mais, "small" e mais leve. Ver src/transcricao.py.
    "voz": {
        "modelo": "turbo",
    },
    # Os IDs do login de e-mail (Google e Microsoft) nao sao preferencia: sao
    # do aplicativo PAULUS e vem no codigo, em src/oauth_app.py.
}


class Preferencias:
    def __init__(self, caminho: Path) -> None:
        self.caminho = Path(caminho)
        self._trava = threading.Lock()
        self.dados = deepcopy(PADRAO)
        self._carregar()

    def _carregar(self) -> None:
        if not self.caminho.exists():
            return
        try:
            bruto = json.loads(self.caminho.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if isinstance(bruto, dict):
            self._fundir(self.dados, bruto)
        self._formatar_gravados()
        # Permissao travada nunca vem do arquivo: alguem editando o JSON na mao
        # nao deve conseguir ligar o que o produto nao oferece.
        for a in AUTONOMIA:
            if a["travada"]:
                self.dados["autonomia"][a["chave"]] = a["padrao"]

    @staticmethod
    def _fundir(base: dict, novo: dict) -> None:
        """Mescla sem perder chave que o arquivo antigo nao conhecia."""
        for chave, valor in novo.items():
            if chave not in base:
                continue
            if isinstance(base[chave], dict) and isinstance(valor, dict):
                Preferencias._fundir(base[chave], valor)
            else:
                base[chave] = valor

    def salvar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.write_text(
            json.dumps(self.dados, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    # ----------------------------------------------------------------- uso

    def pode(self, chave: str) -> bool:
        """Se isto acontece direto ou vai para a fila."""
        return bool(self.dados["autonomia"].get(chave, False))

    def _conferir_campos(self, novo: dict) -> dict:
        """
        CPF, telefone e CNPJ entram com a mascara, pela regra da tela
        (src/campos_br.py). O que nao fecha e recusado com o aviso do campo -
        a nao ser que seja o mesmo valor que ja estava gravado: um dado antigo
        torto nao pode travar quem so quis ligar uma chave.
        """
        novo = dict(novo)
        for secao, chave, tipo in _CAMPOS_CONFERIDOS:
            parte = novo.get(secao)
            if not isinstance(parte, dict) or chave not in parte:
                continue
            valor = str(parte.get(chave) or "")
            antes = str((self.dados.get(secao) or {}).get(chave) or "")
            try:
                formatado = campos_br.formatar(tipo, valor)
            except ValueError as exc:
                if campos_br.normalizado(valor) != campos_br.normalizado(antes):
                    raise ValueError(f"{exc} ({_NOME_DO_CAMPO[(secao, chave)]})") from exc
                formatado = antes
            novo[secao] = {**parte, chave: formatado}
        return novo

    def _formatar_gravados(self) -> None:
        """O que foi gravado sem mascara passa a te-la, se fecha."""
        for secao, chave, tipo in _CAMPOS_CONFERIDOS:
            parte = self.dados.get(secao)
            if isinstance(parte, dict):
                parte[chave] = campos_br.exibir(tipo, parte.get(chave))

    def atualizar(self, novo: dict) -> dict:
        novo = self._conferir_campos(novo or {})
        with self._trava:
            self._fundir(self.dados, novo)
            for a in AUTONOMIA:
                if a["travada"]:
                    self.dados["autonomia"][a["chave"]] = a["padrao"]
        self.salvar()
        return self.dados

    def para_tela(self) -> dict:
        return {
            "preferencias": self.dados,
            "autonomia_opcoes": AUTONOMIA,
        }
