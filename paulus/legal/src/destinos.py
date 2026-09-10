"""
PAULUS - Destinos do menu lateral.

O manual do sistema define 26 telas, 20 delas no menu, em quatro grupos. Este
modulo e a ordem oficial desse menu.

As vinte tem motor por tras. Enquanto faltava alguma, ela entrava na lista com
`pronta=False` e dizia o que resolveria e o que faltava para existir - nao uma
tela em branco, nem um botao morto.

O campo `pronta` continua aqui de proposito. Tela nova nasce falsa e so vira
verdadeira quando ha o que abrir; e mais facil declarar o que falta do que
descobrir depois que um botao do menu nao levava a lugar nenhum.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Destino:
    id: str
    nome: str
    grupo: str
    resolve: str                      # o que a tela resolve, em uma frase
    pronta: bool = False
    abre: str = ""                    # o que a interface chama quando pronta
    precisa: list[str] = field(default_factory=list)   # o que falta existir
    icone: str = "quadro"

    def to_dict(self) -> dict:
        return asdict(self)


GRUPOS = ["Dia a dia", "Documentos", "Escritorio", "Sistema"]

DESTINOS: list[Destino] = [
    # ------------------------------------------------------------ dia a dia
    Destino(
        id="conversa", nome="Conversa", grupo="Dia a dia", icone="conversa", pronta=True,
        abre="conversa",
        resolve="Pergunta livre sobre as pastas, com o plano de execução visível e resposta citando os arquivos.",
    ),
    Destino(
        id="calendario", nome="Calendário", grupo="Dia a dia", icone="calendario", pronta=True,
        abre="calendario",
        resolve="Mês com compromissos, prazos e datas dos documentos na mesma grade, e o painel do dia.",
    ),
    Destino(
        id="agendamento", nome="Agendamento", grupo="Dia a dia", icone="relogio", pronta=True,
        abre="agendamento",
        resolve="Marcar reunião sugerindo os horários que cabem na sua disponibilidade.",
    ),
    Destino(
        id="tarefas", nome="Tarefas", grupo="Dia a dia", icone="lista", pronta=True,
        abre="tarefas",
        resolve="Lista do escritório com prazo, etapas e a origem de cada tarefa.",
    ),
    Destino(
        id="foco", nome="Foco e bem-estar", grupo="Dia a dia", icone="coracao", pronta=True,
        abre="foco",
        resolve="Ciclo de foco, lembretes e o ritmo do dia medido sem ler o que você digita."
    ),
    # ----------------------------------------------------------- documentos
    Destino(
        id="biblioteca", nome="Biblioteca", grupo="Documentos", icone="livros", pronta=True,
        abre="biblioteca",
        resolve="Todos os documentos lidos, com o que o assistente já identificou em cada um.",
    ),
    Destino(
        id="organizar", nome="Organizar pastas", grupo="Documentos", icone="pasta", pronta=True,
        abre="organizar",
        resolve="Proposta de arrumação das pastas em fases, com desfazer.",
    ),
    Destino(
        id="editor", nome="Editor de texto", grupo="Documentos", icone="caneta", pronta=True,
        abre="editor",
        resolve="Redação com o assistente dentro do documento, versões e conferência antes de sair.",
    ),
    Destino(
        id="planilha", nome="Planilha", grupo="Documentos", icone="grade", pronta=True,
        abre="planilha",
        resolve="Cálculos e listas, com a fórmula escrita em português pelo assistente.",
    ),
    Destino(
        id="assinar", nome="Assinar documento", grupo="Documentos", icone="selo", pronta=True,
        abre="assinar",
        resolve="Posicionar a assinatura no PDF e assinar com o certificado.",
    ),
    # ----------------------------------------------------------- escritorio
    Destino(
        id="financeiro", nome="Financeiro", grupo="Escritorio", icone="moeda", pronta=True,
        abre="financeiro",
        resolve="Contas a pagar e receber, honorários e o extrato do mês."
    ),
    Destino(
        id="cadastros", nome="Cadastros", grupo="Escritorio", icone="pessoa", pronta=True,
        abre="cadastros",
        resolve="Clientes, partes e fornecedores, com os documentos vinculados a cada um.",
    ),
    Destino(
        id="caixa", nome="Caixa de entrada", grupo="Escritorio", icone="carta", pronta=True,
        abre="caixa",
        resolve="E-mails com prazo detectado, resposta sugerida e as contas do escritório.",
    ),
    Destino(
        id="aprovacoes", nome="Aprovações", grupo="Escritorio", icone="visto", pronta=True,
        abre="aprovacoes",
        resolve="Fila do que espera a sua decisão antes de sair da máquina.",
    ),
    Destino(
        id="relatorios", nome="Relatórios", grupo="Escritorio", icone="grafico", pronta=True,
        abre="relatorios",
        resolve="O que aconteceu no escritório, somado do que as outras telas gravaram."
    ),
    # -------------------------------------------------------------- sistema
    Destino(
        id="habilidades", nome="Aprendizado", grupo="Sistema", icone="estrela", pronta=True,
        abre="habilidades",
        resolve="O que o assistente sabe fazer, e o que ele ainda não sabe.",
    ),
    Destino(
        id="certificado", nome="Certificado digital", grupo="Sistema", icone="cartao", pronta=True,
        abre="certificado",
        resolve="Cadastro do e-CPF ou e-CNPJ em arquivo A1, validade e o selo de assinatura.",
    ),
    Destino(
        id="conexoes", nome="Conexões", grupo="Sistema", icone="elo", pronta=True,
        abre="conexoes",
        resolve="Navegador embutido para o WhatsApp Web, com sessão só desta máquina."
    ),
    Destino(
        id="desempenho", nome="Desempenho", grupo="Sistema", icone="medidor", pronta=True,
        abre="maquina",
        resolve="Memória, disco e modelo em uso nesta máquina.",
    ),
    Destino(
        id="config", nome="Configurações", grupo="Sistema", icone="engrenagem", pronta=True,
        abre="config",
        resolve="Modelo, seus dados e o que o assistente pode fazer sozinho.",
    ),
]


def por_grupo() -> list[dict]:
    """Menu na ordem oficial do manual."""
    saida = []
    for grupo in GRUPOS:
        itens = [d.to_dict() for d in DESTINOS if d.grupo == grupo]
        if itens:
            saida.append({"grupo": grupo, "destinos": itens})
    return saida


def obter(id_: str) -> Destino | None:
    return next((d for d in DESTINOS if d.id == id_), None)


def contagem() -> dict:
    prontas = sum(1 for d in DESTINOS if d.pronta)
    return {"prontas": prontas, "total": len(DESTINOS)}
