"""
PAULUS - Registro de habilidades.

Cada coisa que o programa sabe fazer e uma entrada aqui. Este arquivo e a
fonte unica: a pagina de habilidades, as portas de entrada da tela inicial e
os tipos de trabalho saem todos daqui. Adicionar uma capacidade e acrescentar
uma entrada, nao espalhar condicional pela interface.

Honestidade e regra: habilidade que ainda nao existe fica marcada como tal.
Listar promessa junto com o que funciona e a forma mais rapida de perder a
confianca de quem usa.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

PRONTA = "pronta"
EM_BREVE = "em_breve"

# O que uma habilidade pode exigir para funcionar agora.
PRECISA_DOCUMENTOS = "documentos"     # ao menos um documento aberto
PRECISA_ASSISTENTE = "assistente"     # o modelo local respondendo

ROTULOS_PRECISA = {
    PRECISA_DOCUMENTOS: "documentos abertos",
    PRECISA_ASSISTENTE: "assistente local ligado",
}


@dataclass
class Habilidade:
    id: str
    nome: str
    resumo: str                                  # uma linha, na lista
    grupo: str
    estado: str = PRONTA
    acao: str = ""                               # o que a interface abre
    precisa: list[str] = field(default_factory=list)
    detalhe: str = ""                            # o que ela faz, por extenso
    demora: str = ""                             # expectativa honesta de tempo

    def to_dict(self) -> dict:
        dados = asdict(self)
        dados["precisa_rotulos"] = [ROTULOS_PRECISA.get(p, p) for p in self.precisa]
        return dados


HABILIDADES: list[Habilidade] = [
    # ------------------------------------------------------------ documentos
    Habilidade(
        id="perguntar",
        nome="Perguntar sobre os documentos",
        resumo="Responde com base no que está escrito, citando o trecho de origem",
        grupo="Documentos",
        acao="conversa",
        precisa=[PRECISA_DOCUMENTOS, PRECISA_ASSISTENTE],
        detalhe=(
            "Procura os trechos que interessam, lê e responde. Toda resposta vem com "
            "os trechos que o assistente leu, e diz quais documentos ficaram de fora."
        ),
        demora="cerca de 20 s por pergunta",
    ),
    Habilidade(
        id="buscar",
        nome="Achar uma palavra",
        resumo="Mostra onde o termo aparece, sem passar pelo assistente",
        grupo="Documentos",
        acao="busca",
        precisa=[PRECISA_DOCUMENTOS],
        detalhe=(
            "Busca direta no texto, com plural e acento tratados. Serve para quando "
            "você só quer achar onde está escrito, sem esperar."
        ),
        demora="instantâneo",
    ),
    Habilidade(
        id="abrir",
        nome="Abrir documentos",
        resumo="Lê PDF, DOCX, TXT e MD e deixa o conteúdo disponível",
        grupo="Documentos",
        acao="anexar",
        detalhe=(
            "Extrai o texto e guarda por conteúdo: renomear ou mover o arquivo não "
            "obriga a ler de novo. PDF escaneado, que é imagem, ainda não dá."
        ),
        demora="alguns segundos por arquivo",
    ),
    # ------------------------------------------------------------- organizar
    Habilidade(
        id="classificar",
        nome="Identificar o que é cada documento",
        resumo="Tipo, partes, data e valor de cada arquivo",
        grupo="Organizar",
        acao="organizacao",
        precisa=[PRECISA_ASSISTENTE],
        detalhe=(
            "Data, valor e CPF/CNPJ saem por regra, na hora. O assistente entra só "
            "quando a regra não decide o tipo ou não acha as partes."
        ),
        demora="8 a 25 s por documento novo",
    ),
    Habilidade(
        id="organizar",
        nome="Organizar uma pasta",
        resumo="Propõe a estrutura de pastas e move, com desfazer",
        grupo="Organizar",
        acao="organizacao",
        precisa=[PRECISA_ASSISTENTE],
        detalhe=(
            "Varre as pastas que você escolher, classifica e monta a árvore no padrão "
            "que você definir. Você confere a tabela antes de qualquer arquivo sair do "
            "lugar, nada é apagado nem sobrescrito, e todo lote pode ser desfeito."
        ),
        demora="depende do tamanho do acervo",
    ),
    # ---------------------------------------------------------- ainda nao ha
    Habilidade(
        id="vencimentos",
        nome="Planilha de prazos e vencimentos",
        resumo="Lista o que vence, com quantos dias faltam, em Excel",
        grupo="Organizar",
        estado=EM_BREVE,
        detalhe=(
            "Extrai as datas de vigência e vencimento de cada contrato e gera uma "
            "planilha ordenada por urgência."
        ),
    ),
    Habilidade(
        id="ocr",
        nome="Ler documento escaneado",
        resumo="Reconhece o texto de PDF que é imagem",
        grupo="Documentos",
        estado=EM_BREVE,
        detalhe=(
            "Hoje um PDF escaneado é ignorado com aviso, porque não tem texto para "
            "extrair. Reconhecimento de caracteres resolveria."
        ),
    ),
    Habilidade(
        id="redigir",
        nome="Redigir a partir de um modelo",
        resumo="Preenche um modelo com os dados dos documentos abertos",
        grupo="Escrita",
        estado=EM_BREVE,
        detalhe="Pega um modelo do escritório e preenche partes, valores e datas.",
    ),
    Habilidade(
        id="assinar",
        nome="Assinar digitalmente",
        resumo="Assinatura com certificado ICP-Brasil",
        grupo="Escrita",
        estado=EM_BREVE,
        detalhe="Assina o documento com o certificado do escritório, sem sair da máquina.",
    ),
]

GRUPOS = ["Documentos", "Organizar", "Escrita"]


def por_grupo(disponibilidade: dict[str, bool] | None = None) -> list[dict]:
    """
    Habilidades agrupadas para a tela, com o que falta para cada uma rodar.

    `disponibilidade` diz o que existe agora (documentos abertos, assistente
    ligado). Sem isso, a lista mostraria como utilizavel algo que nao vai
    funcionar quando a pessoa clicar.
    """
    disponivel = disponibilidade or {}
    saida: list[dict] = []

    for grupo in GRUPOS:
        itens = []
        for habilidade in HABILIDADES:
            if habilidade.grupo != grupo:
                continue
            dados = habilidade.to_dict()
            faltando = [
                ROTULOS_PRECISA.get(p, p)
                for p in habilidade.precisa
                if not disponivel.get(p, False)
            ]
            dados["faltando"] = faltando
            dados["utilizavel"] = habilidade.estado == PRONTA and not faltando
            itens.append(dados)
        if itens:
            saida.append({"grupo": grupo, "habilidades": itens})

    return saida


def obter(id_: str) -> Habilidade | None:
    return next((h for h in HABILIDADES if h.id == id_), None)


def contagem() -> dict:
    prontas = sum(1 for h in HABILIDADES if h.estado == PRONTA)
    return {"prontas": prontas, "total": len(HABILIDADES)}
