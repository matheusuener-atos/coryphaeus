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
        # N14: o agente do escritório faz, sem o cartão de confirmar, o que o
        # AGENTE.md dele lista em `autonomia:` (o titular escreve).
        "chave": "agentes_sozinhos",
        "titulo": "Agentes fazem sozinhos o que o AGENTE.md permite",
        "explica": ("Cada agente faz sem perguntar só as ferramentas listadas em “autonomia:” no AGENTE.md dele (até 20 por "
                    "dia). Fica tudo no Histórico, com desfazer. Nunca e-mail, assinatura nem pagamento: não são ferramentas de agente."),
        "padrao": False,
        "travada": False,
    },
    {
        # N15: a nuvem com a chave do escritório (src/nuvem.py). Ligar a nuvem é
        # em Configurações › Modelos; esta chave só tira o "pedir a cada vez".
        "chave": "modelo_nuvem",
        "titulo": "Mandar à nuvem sem pedir a cada pergunta",
        "explica": (
            "Com a nuvem ligada em Configurações › Modelos (a chave do escritório, desligada de fábrica), cada pergunta "
            "marcada “Nuvem” espera o seu sim, com o texto que vai sair. Ligada esta, vai direto - e fica tudo no "
            "registro de envios. O que veio do e-mail, a cópia do Drive e o caso só no escritório nunca vão."
        ),
        "padrao": False,
        "travada": False,
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
    # As pastas do Google Drive copiadas para o Acervo (src/drive_online.py).
    "drive_online": {"pastas": []},
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
                     "gravacao": True, "agenda": True, "acesso": True},
    # O acesso de fora (src/acesso/, acesso-remoto/v0): desligado de fabrica.
    # Ligado, o PAULUS atende pelo tunel da Cloudflare quem passar pela
    # verificacao anti-robo (Turnstile) e entrar com conta, senha e codigo do
    # autenticador - sem Cloudflare Access. O endereco e a porta fixa ficam
    # aqui; o token do tunel e o segredo da instalacao, nao - esses sao
    # segredos e moram protegidos pela DPAPI (src/acesso/tunel.py).
    # `instalacao_id` e aleatorio, criado na primeira conexao: e o que o Worker
    # usa para nao deixar a mesma instalacao conectar duas vezes.
    # `cloudflared_minimo`: versao abaixo desta nao roda (a que le o token do
    # ambiente com seguranca).
    # `turnstile_sitekey`: a chave publica do anti-robo da tela de entrar, que
    # o Worker entrega na conexao. `liberado`: a frase de quando o endereco
    # foi liberado em paulus.ia.br (falta de uso) - a tela mostra ate conectar
    # de novo.
    # Prazos e publicacoes (src/prazos.py, src/publicacoes.py): os feriados e
    # suspensoes que o escritorio cadastrou, as OABs acompanhadas no DJEN
    # (alem da de Meus dados) e a consulta diaria.
    "prazos": {"feriados": []},
    "publicacoes": {"ligado": False, "oabs": [], "ultima": "", "ultimo_erro": ""},
    # Backup (src/backup.py): a pasta, o automatico diario, quantos manter, e
    # a senha - guardada pela protecao de dados do Windows, nunca em texto.
    "backup": {"pasta": "", "automatico": True, "manter": 10, "senha": "", "ultimo": "", "ultimo_arquivo": "",
               "ultimo_erro": ""},
    "acesso_remoto": {"seguranca_padrao": "padrao", "ligado": False, "porta": 0, "hostname": "", "turnstile_sitekey": "", "liberado": "",
                      "abrir_com_windows": False, "instalacao_id": "", "cloudflared_minimo": "2025.4.0",
                      # De fora, toda entrada e pelo Google (+ o codigo do celular) - decisao do
                      # dono, 28/09/2026. Sem o Google configurado, ninguem entra de fora (a tela
                      # diz o que falta). Desligar existe so para os testes do caminho por senha.
                      "so_google": True},
    "modelo": "",
    # O que chega ao modelo (src/inferencia.py), uma chave por etapa do plano
    # de melhoria da IA - para dar para voltar atras sem mexer em codigo.
    # `opcoes_fixas` (I1): temperatura 0, semente 42, keep_alive e teto de
    # resposta vindos do catalogo; desligada, volta a temperatura 0,1 de antes.
    # `janela_por_modelo`: {"modelo": num_ctx}; vazio, a do catalogo (16384).
    # `medir` (I1): uma linha por pergunta em data/medicao/perguntas.jsonl,
    # so numeros, nunca o texto - e o arquivo nao sai da maquina.
    # `molde` (I3): pergunta de um dado so (processo, valor, tribunal, partes,
    # assinatura, leis) respondida pelos fatos conferidos, sem modelo e sem
    # fila; onde o modelo continua, numero que nao esta nos fatos derruba a
    # resposta.
    # `memoria` (I4): os 2 ultimos pares da conversa vao junto (~600 tokens),
    # e "e a multa?" herda o sujeito da pergunta anterior, por regra.
    # `trechos_estruturais` (I5): o Acervo e fatiado por clausula, secao e
    # artigo (src/trechos.py), e nao em blocos de 1.200 caracteres.
    # `lexico_fts` (I6): a busca lexica em SQLite FTS5, em disco e
    # incremental, com a normalizacao juridica (src/lexico.py).
    # `denso` (I7): com o modelo de vetores (bge-m3) baixado, o Acervo ganha
    # vetores em segundo plano e a busca vira hibrida (lexica + sentido, RRF).
    # `leitura` (I7): "tudo" le o acervo inteiro quando ele cabe na janela;
    # "trechos" le so os 6 melhores trechos (ate 3000 tokens), salvo escopo
    # pequeno ou pedido de ler inteiro. De fabrica "tudo": a virada so vale
    # depois de medida no conjunto real (docs/PROGRESSO-IMPLEMENTACAO.md).
    # `citacao` (I8): trechos numerados [T1], [T2]..., cada frase marcada com
    # o trecho que a sustenta, e tres conferencias em codigo antes de a
    # resposta ficar (src/citacoes.py).
    # `ajuda` (I9): o cartao do documento com os fatos conferidos, as
    # perguntas que respondem na hora e os prazos propostos em Aprovacoes.
    "ia": {"opcoes_fixas": True, "janela_por_modelo": {}, "medir": True, "molde": True, "memoria": True,
           "trechos_estruturais": True, "lexico_fts": True, "denso": True, "leitura": "tudo",
           "citacao": False, "ajuda": True},
    # A Biblioteca do escritorio (src/biblioteca, docs/PROGRESSO-BIBLIOTECA.md).
    # Cada etapa nasce desligada e so liga de fabrica depois do portao dela;
    # a chave continua existindo para voltar atras.
    # `hibrida` (M1): o material de consulta na busca hibrida do Acervo
    # (trechos pela estrutura, FTS5 e vetores), em indices proprios.
    # `triagem` (M2): o que entra como material passa pela triagem - lei
    # conhecida vai para as leis em casa; o resto ganha a ficha (tipo,
    # autor, obra, edicao, ano, areas) para conferir.
    # Ligadas de fabrica depois do portao (M1: Recall@6 0,84 contra 0,58, sem
    # ruido a mais; M2: a triagem e a ficha, 0 campo errado).
    # `anotacoes` (M3): cada artigo que uma obra cita, com o instrumento, vira
    # anotacao do artigo - na tela da lei e na pergunta que cita o artigo.
    # `camadas` (M4): a resposta em blocos rotulados (LEI, SUMULAS, DOUTRINA,
    # COMUNIDADE, REGRA DA CASA, DOCUMENTOS), marca [Tn] com a origem, e a
    # frase de doutrina dita como lei atribuida ao autor.
    # `defasagem` (M6): obra anterior a redacao atual do artigo que comenta
    # ganha o aviso, na resposta e na tela da lei (so avisa, nao esconde).
    # `mapa` (M7): a tela "O que o PAULUS sabe" por area, e a linha "Nao tenho
    # material de <area> na biblioteca" quando a pergunta e de area sem nada.
    # `pacote`: exportar e importar um material como .paulus-material, so
    # local (o compartilhamento entre escritorios e frente futura).
    # `leitura` (M5): o modelo da tarefa `leitura` le cada obra em segundo
    # plano e guarda conceitos e posicoes - so o que a frase do livro confirma.
    # De fabrica (30/09/2026): ligadas as que passaram no portao; `leitura`
    # desligada - com o llama3.2:3b, 62% dos conceitos e teses certos (teses
    # 93%, conceitos 44%), abaixo dos 80% do portao. Liga quem tiver modelo
    # maior para a tarefa de leitura.
    "biblioteca": {"hibrida": True, "triagem": True, "anotacoes": True, "camadas": True, "defasagem": True,
                   "mapa": True, "leitura": False, "pacote": True},
    # As ideias do umbrelOS (docs/DECISAO-UMBREL.md). `captura` (E): fotografar
    # um documento pelo celular; de fora, a foto vai para Aprovacoes antes do
    # Acervo. `mcp` (A): o servidor MCP das leis, so em 127.0.0.1, com token
    # por conexao - desligado de fabrica: o que ele devolve vai para o modelo
    # de outra empresa (so texto de lei, que e publico).
    "umbrel": {"captura": False, "mcp": False},
    # A conversa e os agentes (docs/PROGRESSO-CONVERSA.md). `execucao` (C1): a
    # resposta roda numa thread de trabalho, com registro de eventos em disco,
    # e a janela so se inscreve - fechar ou recarregar nao perde a resposta.
    # `pensando` (C2): uma linha de estado no lugar da resposta, o "ver
    # detalhes" guardado com ela, vermelho so para erro e a lista de
    # documentos sem trecho resumida numa contagem.
    # `painel` (C3): o painel descreve UMA resposta (a ultima ou a clicada), a
    # barra acima do campo diz onde a proxima pergunta procura, e rascunho,
    # escopo, anexos e rolagem ficam por conversa. `diagnostico`: motor,
    # trechos indexados e pasta no painel (desligado: e dado tecnico).
    # `saudacao` (T1): a frase da tela inicial sai do banco config/saudacoes.json
    # (momento, dia, calendario, chegada e situacao), sem modelo e sem repetir.
    "conversa": {"execucao": True, "pensando": True, "painel": True, "diagnostico": False, "saudacao": True,
                 # `agentes` (A1): o AGENTE.md de cada especialista do escritorio,
                 # validado e versionado (src/agentes.py). Escrever e do titular.
                 "agentes": True,
                 # `avisos` (T2): o carrossel dos avisos do dia na tela inicial, a
                 # Central de avisos e o historico do visto (src/central_avisos.py).
                 "avisos": True,
                 # `superficies` (C5): o parecer, o resumo da gravacao e o
                 # reescrever do e-mail rodam como execucao, na fila do modelo.
                 "superficies": True,
                 # `roteamento` (C4): perguntas sobre o programa (Publicacoes, DJE,
                 # busca, Leis, Acesso de fora...) pela tela certa, e CPF, CNPJ,
                 # telefone, e-mail, endereco e OAB de alguem por molde, sem ler o
                 # acervo (src/consulta_cadastro.py).
                 "roteamento": True,
                 # `cerca` (C6): trechos de documento, material e biblioteca vao ao
                 # modelo cercados, como o e-mail (src/blindagem.py).
                 "cerca": False,
                 # `relacionados` (N7): embaixo da resposta, os temas e sumulas
                 # ligados aos artigos citados e a posicao da casa - por regra.
                 "relacionados": True},
    # Pensar no aparelho (docs/PROGRESSO-APARELHO.md). `fila` (F1): toda
    # chamada ao modelo entra na fila unica, com a origem; a pergunta mandada
    # com outra andando fica na conversa e vai sozinha; Ctrl+Enter pede
    # prioridade. `prioridade_por_hora`: quantas vezes por hora quem tem o
    # nivel do titular passa na frente de outras pessoas.
    # `ligado` (D1): a resposta pode ser escrita no aparelho de quem pergunta
    # de fora, com o nivel "aparelho" da conta (src/aparelho.py).
    # `modelo` (D2): o modelo que o aparelho baixa do Ollama deste escritorio.
    # "modelo": o preferido para o aparelho; sem ele aqui (ou grande demais para
    # o navegador), o do escritório ou o maior que cabe (src/aparelho_motor.py).
    "aparelho": {"fila": False, "prioridade_por_hora": 3, "ligado": False, "modelo": "llama3.2:3b"},
    # N15 (src/nuvem.py): a nuvem com a chave do escritorio - desligada de
    # fabrica. A chave nao mora aqui: fica cifrada pela DPAPI em <dados>/nuvem/.
    # A IA faz parte da assinatura (src/plano.py): o ultimo plano conhecido,
    # para valer sem internet ate o fim do ciclo pago.
    "plano": {"ativo": False, "ate": "", "conferido_em": ""},
    # V5 (docs/PLANO-NUVEM.md): o PAULUS (nuvem) vem primeiro; sem o sim do
    # titular (consentimento, com a versao do termo) nada liga.
    "nuvem": {"ligado": False, "provedor": "paulus", "modelo": "", "mascarar": True, "consentimento": {},
              "pedir_cada_envio": False, "tarefas": {"conversa": True, "resumos": True, "redacao": True}},
    # W1 (src/word_suplemento.py, src/word_instalar.py): o PAVLVS dentro do
    # Word - desligado de fabrica. `porta` e a HTTPS do painel (fixa: o
    # manifesto leva o endereco); `id` gera o Id do manifesto desta instalacao.
    "word": {"ligado": False, "porta": 0, "id": "", "instalado_em": ""},
    # N13 (src/jurisprudencia.py): os orgaos julgadores do STJ que o escritorio
    # escolheu baixar. Vazio de fabrica: nada e baixado sem a pessoa pedir.
    "jurisprudencia": {"orgaos": []},
    # L1 (src/aprendizado.py): 👍/👎 em cada resposta e o caderno de falhas.
    # Ligado de fabrica: o piloto mede desde o primeiro dia, e nada sai daqui.
    "aprendizado": {"avaliar": True},
    # L2 (src/processos.py): acompanhar os processos pelo DataJud, uma vez
    # por dia. So o numero do processo sai daqui. Desligado de fabrica.
    "processos": {"acompanhar": False},
    # A atualizacao (src/atualizacao.py): ver uma vez por dia se ha versao
    # nova em paulus.ia.br/atualizacao.json e, com avisar_antes, perguntar
    # antes de instalar; sem ele, baixa sozinho e instala ao fechar.
    "atualizacoes": {"verificar": True, "avisar_antes": True, "ultima_consulta": "", "erro": ""},
    # Os modulos do menu (assistente de configuracao, passo Modulos, e
    # Configuracoes › Modulos). Desligado some do menu desta maquina; o
    # Assistente e Configuracoes ficam sempre.
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
    # O PAULUS do servidor vinculado a conta Google de quem o administra
    # (src/vinculo.py, E5). Vinculado, abre travado - salvo manter_aberto.
    "vinculo": {"email": "", "nome": "", "em": "", "manter_aberto": False, "saiu": False,
                # entrar sem internet com o codigo proprio do servidor (src/vinculo.py)
                "offline": {"segredo": "", "ultimo_passo": 0, "recuperacao": []}},
    "pessoa": {
        "nome": "",
        "cpf": "",
        "oab": "",
        "telefone": "",
        "email": "",
        # Com o PAULUS vinculado a conta Google (E5), `email` e o do Google; o
        # de contato, se outro, fica aqui.
        "email_secundario": "",
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
        # A data de fundacao (AAAA-MM-DD): no aniversario, a saudacao lembra (T1).
        "fundacao": "",
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
                if not base[chave]:
                    # Dicionario vazio no padrao e mapa de nomes livres (a
                    # janela por modelo, por exemplo): as chaves sao dados.
                    base[chave] = dict(valor)
                    continue
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
