"""
As ferramentas que a conversa sabe usar — e o contrato com o modelo.

A conversa já fazia coisas: "anote uma reunião dia 11/09" virava uma proposta
com os campos à vista, e só o sim da pessoa gravava. Este módulo junta essas
ações num catálogo só, com os parâmetros declarados, para que três partes
falem a mesma língua: o leitor de intenção (que acha a ação por regra), o
modelo (quando a regra reconhece a ação mas não consegue preencher um campo
obrigatório) e a rota que grava depois do sim.

Três decisões:

**A regra escolhe a ferramenta; o modelo só completa.** Perguntar ao modelo
antes de toda mensagem custaria um minuto por mensagem num computador sem
placa de vídeo. Ele é chamado só quando a frase já é, com certeza, um pedido
de ação e falta um campo obrigatório — e mesmo aí não pode trocar a
ferramenta que a regra escolheu.

**O que o modelo devolve é conferido como entrada de estranho.** Contrato
JSON estrito: tipo, ferramenta, parâmetros. Parâmetro desconhecido cai; CPF e
CNPJ passam pelo dígito verificador; valor vira centavos; data vira ISO. E o
que o modelo escreveu precisa estar na frase: um nome que a pessoa não disse
é invenção, e invenção não entra no cartão.

**Oferecer não é abrir.** Depois de uma resposta tirada de um ou dois
documentos, a conversa oferece mostrá-los ali mesmo (exibir_documento) — e só
mostra com o clique.

**Entender não é fazer.** Toda ferramenta exige confirmação. A emissão de
NFS-e existe no catálogo e na rota, mas ainda não emite: confirmar confere os
dados e diz isso, sem enviar nada a prefeitura nenhuma.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

# ---------------------------------------------------------------- catálogo

CATALOGO_FERRAMENTAS: dict[str, dict] = {
    "cadastrar_cliente": {
        "descricao": "Cadastra um cliente novo em Cadastros.",
        "modulo": "cadastros",
        "proposta": "cadastro",
        "exige_confirmacao": True,
        "disponivel": True,
        "parametros": {
            "nome": {"tipo": "texto", "descricao": "nome completo da pessoa ou razão social da empresa",
                     "obrigatorio": "o cadastro precisa de um nome"},
            "documento": {"tipo": "cpf_cnpj", "descricao": "CPF ou CNPJ"},
            "telefone": {"tipo": "telefone", "descricao": "telefone com DDD"},
            "email": {"tipo": "email", "descricao": "endereço de e-mail"},
            "endereco": {"tipo": "texto", "descricao": "endereço"},
            "observacao": {"tipo": "texto", "descricao": "anotação livre sobre o cliente"},
        },
    },
    "criar_compromisso": {
        "descricao": "Anota um compromisso na agenda: reunião, audiência, consulta, visita.",
        "modulo": "agenda",
        "proposta": "agenda",
        "exige_confirmacao": True,
        "disponivel": True,
        "parametros": {
            "titulo": {"tipo": "texto", "descricao": "do que se trata, curto: Reunião, Audiência",
                       "obrigatorio": "o compromisso precisa de um titulo"},
            "data": {"tipo": "data", "descricao": "dia do compromisso, AAAA-MM-DD",
                     "obrigatorio": "o compromisso precisa de uma data"},
            "hora": {"tipo": "hora", "descricao": "hora de início, HH:MM"},
            "duracao": {"tipo": "minutos", "descricao": "duração em minutos"},
            "avisar_min": {"tipo": "minutos", "descricao": "quantos minutos antes avisar"},
        },
    },
    "exibir_documento": {
        "descricao": "Mostra um documento do Acervo dentro da conversa, só para leitura.",
        "modulo": "acervo",
        "proposta": "exibir",
        "exige_confirmacao": True,
        "disponivel": True,
        "parametros": {
            "nome": {"tipo": "texto", "descricao": "nome do arquivo, como está no Acervo",
                     "obrigatorio": "diga qual documento mostrar"},
        },
    },
    "emitir_nfse": {
        "descricao": "Emite uma nota fiscal de serviço (NFS-e) para um cliente.",
        "modulo": "escritorio",
        "proposta": "nota",
        "exige_confirmacao": True,
        # A rota existe e confere os dados; a emissão de verdade vem depois.
        "disponivel": False,
        "parametros": {
            "cliente": {"tipo": "texto", "descricao": "nome do tomador do serviço",
                        "obrigatorio": "a nota precisa do cliente"},
            "valor": {"tipo": "dinheiro", "descricao": "valor do serviço em reais, como texto: \"1500,00\"",
                      "obrigatorio": "a nota precisa de um valor maior que zero"},
            "descricao": {"tipo": "texto", "descricao": "o serviço prestado"},
            "data": {"tipo": "data", "descricao": "data de emissão, AAAA-MM-DD"},
        },
    },
}

# O tipo de proposta que a tela conhece -> a ferramenta. "agenda" já existia
# antes do catálogo, e o cartão continua o mesmo.
POR_PROPOSTA = {f["proposta"]: nome for nome, f in CATALOGO_FERRAMENTAS.items()}


class ContratoInvalido(ValueError):
    """O que o modelo devolveu não segue o contrato JSON."""


@dataclass
class Chamada:
    """Uma resposta do modelo, já conferida."""

    tipo: str                                   # acao | resposta
    ferramenta: str = ""
    parametros: dict = field(default_factory=dict)
    mensagem: str = ""
    erros: dict = field(default_factory=dict)   # parâmetro -> por que caiu


# ------------------------------------------------------------ normalizar


def _plano(texto: str) -> str:
    normal = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


def _digitos(texto) -> str:
    return re.sub(r"\D", "", str(texto or ""))


def _cpf_confere(d: str) -> bool:
    if len(d) != 11 or d == d[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(d[i]) * (tamanho + 1 - i) for i in range(tamanho))
        if (soma * 10 % 11) % 10 != int(d[tamanho]):
            return False
    return True


def _cnpj_confere(d: str) -> bool:
    if len(d) != 14 or d == d[0] * 14:
        return False
    pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for tamanho in (12, 13):
        soma = sum(int(d[i]) * pesos[i + 13 - tamanho] for i in range(tamanho))
        resto = soma % 11
        if (0 if resto < 2 else 11 - resto) != int(d[tamanho]):
            return False
    return True


def cpf_ou_cnpj(texto) -> str:
    """CPF ou CNPJ formatado. Número que não confere é recusado, não corrigido."""
    d = _digitos(texto)
    if len(d) == 11:
        if not _cpf_confere(d):
            raise ValueError("o CPF não confere — confira os números")
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    if len(d) == 14:
        if not _cnpj_confere(d):
            raise ValueError("o CNPJ não confere — confira os números")
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    raise ValueError("CPF tem 11 números e CNPJ tem 14")


def telefone(texto) -> str:
    d = _digitos(texto)
    if len(d) in (12, 13) and d.startswith("55"):
        d = d[2:]
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    raise ValueError("o telefone precisa do DDD e do número")


RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def email(texto) -> str:
    t = str(texto or "").strip().lower()
    if not RE_EMAIL.fullmatch(t):
        raise ValueError("o e-mail não parece um e-mail")
    return t


def centavos_de(valor) -> int:
    """
    "R$ 1.500,00", "1500", "1.500", "1500.50", "2 mil" -> centavos.

    Número inteiro já é centavos (é como o programa guarda); texto é reais,
    escrito como se escreve no Brasil. Ponto seguido de três dígitos é milhar.
    """
    if isinstance(valor, bool):
        raise ValueError("valor inválido")
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        return round(valor * 100)
    t = _plano(valor).replace("r$", " ").strip()
    mil = re.search(r"\bmil\b", t)
    t = re.sub(r"\b(mil|reais|real)\b", " ", t)
    numero = re.sub(r"[^\d,.]", "", t)
    if not numero:
        raise ValueError("não achei o valor")
    if "," in numero and "." in numero:
        decimal = "," if numero.rfind(",") > numero.rfind(".") else "."
        milhar = "." if decimal == "," else ","
        numero = numero.replace(milhar, "").replace(decimal, ".")
    elif "," in numero:
        numero = numero.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", numero):
        numero = numero.replace(".", "")
    try:
        reais = float(numero)
    except ValueError as exc:
        raise ValueError("não achei o valor") from exc
    if mil:
        reais *= 1000
    return round(reais * 100)


def _positivo(centavos: int) -> int:
    if centavos < 0:
        raise ValueError("o valor não pode ser negativo")
    return centavos


def data_iso(texto, hoje: date | None = None) -> str:
    t = str(texto or "").strip()
    achado = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", t[:10])
    if achado:
        try:
            return date(*map(int, achado.groups())).isoformat()
        except ValueError as exc:
            raise ValueError("essa data não existe") from exc
    import intencao  # aqui dentro: intencao importa este módulo

    iso, _ = intencao.ler_data(t, hoje)
    if not iso:
        raise ValueError("não entendi a data")
    return iso


def hora(texto) -> str:
    achado = re.fullmatch(r"\s*(\d{1,2})\s*(?::|h)?\s*(\d{2})?\s*(?:h|hs|horas?)?\s*", str(texto or ""))
    if not achado:
        raise ValueError("não entendi a hora")
    h, m = int(achado.group(1)), int(achado.group(2) or 0)
    if h > 23 or m > 59:
        raise ValueError("essa hora não existe")
    return f"{h:02d}:{m:02d}"


def minutos(valor) -> int:
    if isinstance(valor, bool):
        raise ValueError("minutos inválidos")
    try:
        n = int(float(str(valor).strip() or 0))
    except ValueError as exc:
        raise ValueError("minutos inválidos") from exc
    if n < 0:
        raise ValueError("minutos não podem ser negativos")
    return n


def texto(valor) -> str:
    return " ".join(str(valor or "").split())[:200]


NORMALIZADORES = {
    "texto": lambda v, hoje: texto(v),
    "cpf_cnpj": lambda v, hoje: cpf_ou_cnpj(v),
    "telefone": lambda v, hoje: telefone(v),
    "email": lambda v, hoje: email(v),
    "dinheiro": lambda v, hoje: _positivo(centavos_de(v)),
    "data": lambda v, hoje: data_iso(v, hoje),
    "hora": lambda v, hoje: hora(v),
    "minutos": lambda v, hoje: minutos(v),
}


def normalizar(ferramenta: str, parametros: dict, hoje: date | None = None) -> tuple[dict, dict]:
    """
    Os parâmetros que a ferramenta declara, no formato que ela grava.

    Devolve (limpos, erros). Parâmetro que a ferramenta não declara cai
    calado; valor vazio fica de fora; valor que não passa vai para `erros`
    com o motivo, em vez de entrar torto.
    """
    if ferramenta not in CATALOGO_FERRAMENTAS:
        raise ContratoInvalido(f"não existe a ferramenta {ferramenta!r}")
    declarados = CATALOGO_FERRAMENTAS[ferramenta]["parametros"]
    limpos: dict = {}
    erros: dict = {}
    for nome, valor in (parametros or {}).items():
        if nome not in declarados or valor is None or (isinstance(valor, str) and not valor.strip()):
            continue
        try:
            limpo = NORMALIZADORES[declarados[nome]["tipo"]](valor, hoje)
        except ValueError as exc:
            erros[nome] = str(exc)
            continue
        if limpo in ("", 0) and declarados[nome]["tipo"] in ("texto", "dinheiro"):
            continue
        limpos[nome] = limpo
    return limpos, erros


def faltando(ferramenta: str, limpos: dict) -> list[str]:
    """Os obrigatórios que não vieram, na ordem do catálogo."""
    declarados = CATALOGO_FERRAMENTAS[ferramenta]["parametros"]
    return [n for n, p in declarados.items() if p.get("obrigatorio") and not limpos.get(n)]


# ---------------------------------------------------------------- contrato


def obter_prompt_ferramentas(hoje: date | None = None) -> str:
    """
    A instrução de sistema que ensina o contrato ao modelo.

    Montada do catálogo, e não escrita à mão: parâmetro novo no catálogo
    aparece aqui sem ninguém lembrar de atualizar um texto.
    """
    hoje = hoje or date.today()
    dias = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
            "sexta-feira", "sábado", "domingo")
    linhas = [
        "Você lê um pedido feito a um programa de escritório de advocacia e devolve JSON.",
        f"Hoje é {dias[hoje.weekday()]}, {hoje.isoformat()}.",
        "",
        "Ferramentas:",
    ]
    for nome, f in CATALOGO_FERRAMENTAS.items():
        linhas.append(f"- {nome}: {f['descricao']}")
        for p, spec in f["parametros"].items():
            marca = " (obrigatório)" if spec.get("obrigatorio") else ""
            linhas.append(f"    {p}{marca}: {spec['descricao']}")
    linhas += [
        "",
        "Responda APENAS com um objeto JSON, sem texto antes ou depois, neste formato:",
        '{"tipo": "acao", "ferramenta": "<nome>", "parametros": {...}, "mensagem": "<frase curta>"}',
        "ou, quando o pedido não for nenhuma dessas ferramentas:",
        '{"tipo": "resposta", "ferramenta": null, "parametros": {}, "mensagem": "<frase curta>"}',
        "",
        "Regras:",
        "- Use só o que está escrito no pedido. Nunca invente nome, número, data ou valor.",
        "- Parâmetro que o pedido não diz fica de fora do objeto.",
        "- Datas em AAAA-MM-DD, contadas a partir de hoje. Horas em HH:MM.",
        "- Valores em reais como texto, do jeito que foram escritos.",
        "",
        'Exemplo: "cadastre a cliente Maria Souza, telefone 11 98888-7777"',
        '{"tipo": "acao", "ferramenta": "cadastrar_cliente", '
        '"parametros": {"nome": "Maria Souza", "telefone": "11 98888-7777"}, '
        '"mensagem": "Cadastrar Maria Souza"}',
    ]
    return "\n".join(linhas)


def _objeto_json(bruto) -> dict:
    if isinstance(bruto, dict):
        return bruto
    if not isinstance(bruto, str) or not bruto.strip():
        raise ContratoInvalido("o modelo não devolveu nada")
    try:
        dados = json.loads(bruto)
    except json.JSONDecodeError:
        inicio, fim = bruto.find("{"), bruto.rfind("}")
        if inicio == -1 or fim <= inicio:
            raise ContratoInvalido("o modelo não devolveu JSON") from None
        try:
            dados = json.loads(bruto[inicio:fim + 1])
        except json.JSONDecodeError:
            raise ContratoInvalido("o modelo não devolveu JSON") from None
    if not isinstance(dados, dict):
        raise ContratoInvalido("o JSON do modelo não é um objeto")
    return dados


def interpretar_resposta(bruto, hoje: date | None = None) -> Chamada:
    """
    O JSON do modelo, conferido contra o contrato.

    Aceita o texto cru ou o objeto já lido. Sai uma `Chamada` com os
    parâmetros normalizados — ou `ContratoInvalido`, quando o formato está
    errado a ponto de não dar para confiar em nada.
    """
    dados = _objeto_json(bruto)
    tipo = str(dados.get("tipo", "")).strip().lower()
    mensagem = texto(dados.get("mensagem", ""))
    if tipo == "resposta":
        return Chamada(tipo="resposta", mensagem=mensagem)
    if tipo != "acao":
        raise ContratoInvalido("tipo precisa ser \"acao\" ou \"resposta\"")

    ferramenta = str(dados.get("ferramenta") or "").strip()
    if ferramenta not in CATALOGO_FERRAMENTAS:
        raise ContratoInvalido(f"não existe a ferramenta {ferramenta!r}")
    parametros = dados.get("parametros") or {}
    if not isinstance(parametros, dict):
        raise ContratoInvalido("parametros precisa ser um objeto")

    # O modelo escreve 1500 querendo dizer reais; número inteiro, no programa,
    # é centavos. O que vem do modelo é sempre lido como texto em reais.
    declarados = CATALOGO_FERRAMENTAS[ferramenta]["parametros"]
    como_texto = {
        n: (str(v) if declarados.get(n, {}).get("tipo") == "dinheiro" and isinstance(v, (int, float))
            and not isinstance(v, bool) else v)
        for n, v in parametros.items()
    }
    limpos, erros = normalizar(ferramenta, como_texto, hoje)
    return Chamada(tipo="acao", ferramenta=ferramenta, parametros=limpos, mensagem=mensagem, erros=erros)


# --------------------------------------------------------- com o modelo

NUMEROS_POR_EXTENSO = ("um", "dois", "tres", "quatro", "cinco", "seis", "sete", "oito", "nove",
                       "dez", "cem", "cento", "duzentos", "trezentos", "quinhentos", "mil")
INDICIOS_DE_DATA = ("hoje", "amanha", "proxim", "semana", "mes que vem", "segunda", "terca",
                    "quarta", "quinta", "sexta", "sabado", "domingo", "janeiro", "fevereiro",
                    "marco", "abril", "maio", "junho", "julho", "agosto", "setembro",
                    "outubro", "novembro", "dezembro", "daqui")


def tem_indicio_de_data(frase: str) -> bool:
    """
    A frase tem alguma coisa de onde tirar uma data?

    Hora e aviso não contam: "marque uma reunião às 14h" tem número e não tem
    dia — e o modelo, perguntado, responderia com um dia inventado.
    """
    plano = _plano(frase)
    plano = re.sub(r"\d{1,3}\s*(?:min|minutos?|h|hs|horas?|dias?)\s*antes", " ", plano)
    plano = re.sub(r"\d{1,2}\s*(?::|h|hs|horas?)\s*\d{0,2}", " ", plano)
    return bool(re.search(r"\d", plano)) or any(
        re.search(r"\b" + i, plano) for i in INDICIOS_DE_DATA)


def ancorado(tipo: str, valor, frase: str) -> bool:
    """
    O valor que o modelo deu está na frase?

    É o que separa completar de inventar. Texto: toda palavra com três letras
    ou mais aparece na frase. Número: os dígitos aparecem. Data e valor, que
    o modelo converte, pedem ao menos um indício na frase.
    """
    plano = _plano(frase)
    if tipo == "texto":
        palavras = [p for p in re.findall(r"[a-z0-9]+", _plano(valor)) if len(p) >= 3]
        frase_palavras = set(re.findall(r"[a-z0-9]+", plano))
        return bool(palavras) and all(p in frase_palavras for p in palavras)
    if tipo in ("cpf_cnpj", "telefone"):
        d = _digitos(valor)
        return bool(d) and (d in _digitos(frase) or d[2:] in _digitos(frase))
    if tipo == "email":
        return str(valor).lower() in str(frase).lower()
    if tipo == "dinheiro":
        return bool(re.search(r"\d", plano)) or any(
            re.search(r"\b" + n + r"\b", plano) for n in NUMEROS_POR_EXTENSO)
    if tipo == "data":
        return tem_indicio_de_data(frase)
    if tipo in ("hora", "minutos"):
        return bool(re.search(r"\d", plano))
    return False


def o_que_falta(ferramenta: str, campos: dict) -> str:
    """A frase que o cartão mostra quando falta obrigatório. Vazia quando nada falta."""
    nomes = {"nome": "o nome", "data": "a data", "titulo": "o título",
             "cliente": "o cliente", "valor": "o valor"}
    faltam = [nomes.get(n, n) for n in faltando(ferramenta, campos)]
    if not faltam:
        return ""
    juntos = faltam[0] if len(faltam) == 1 else ", ".join(faltam[:-1]) + " e " + faltam[-1]
    return f"não achei {juntos} nessa frase"


def completar_com_modelo(lido, pergunta: str, perguntar_json, hoje: date | None = None) -> list[str]:
    """
    Pede ao modelo o que a regra não conseguiu preencher.

    `lido` é a `Intencao` que a regra montou; é alterada no lugar. Só entram
    os campos obrigatórios ou não que ainda estavam vazios, que passaram na
    normalização e que estão ancorados na frase. A ferramenta é a da regra:
    se o modelo achar que é outra, a resposta dele é ignorada inteira.
    Devolve os campos que o modelo preencheu — a tela diz quais foram.

    `perguntar_json(instrucao, sistema)` é quem fala com o modelo; qualquer
    erro dele (Ollama fechado, JSON torto) deixa o cartão como a regra fez.
    """
    ferramenta = POR_PROPOSTA.get(lido.tipo)
    if not ferramenta:
        return []
    try:
        chamada = interpretar_resposta(perguntar_json(pergunta, obter_prompt_ferramentas(hoje)), hoje)
    except Exception:  # noqa: BLE001 - o modelo falhar nunca pode derrubar a proposta
        return []
    if chamada.tipo != "acao" or chamada.ferramenta != ferramenta:
        return []

    declarados = CATALOGO_FERRAMENTAS[ferramenta]["parametros"]
    preenchidos: list[str] = []
    for nome, valor in chamada.parametros.items():
        if lido.campos.get(nome):
            continue
        if not ancorado(declarados[nome]["tipo"], valor, pergunta):
            continue
        lido.campos[nome] = valor
        preenchidos.append(nome)

    if preenchidos:
        lido.falta = o_que_falta(ferramenta, lido.campos)
        principal = lido.campos.get("nome") or lido.campos.get("titulo") or lido.campos.get("cliente")
        if principal and not lido.titulo:
            lido.titulo = principal
    return preenchidos


# ---------------------------------------------------------------- executar


def _br(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if len(iso or "") >= 10 else str(iso or "")


def _reais(centavos: int) -> str:
    inteiro, resto = divmod(abs(int(centavos)), 100)
    return ("-" if centavos < 0 else "") + "R$ " + f"{inteiro:,}".replace(",", ".") + f",{resto:02d}"


def _conferir(ferramenta: str, campos: dict, hoje: date | None = None) -> dict:
    limpos, erros = normalizar(ferramenta, campos, hoje)
    if erros:
        raise ValueError(next(iter(erros.values())))
    falta = faltando(ferramenta, limpos)
    if falta:
        raise ValueError(CATALOGO_FERRAMENTAS[ferramenta]["parametros"][falta[0]]["obrigatorio"])
    return limpos


def _cadastrar_cliente(estado, campos: dict) -> dict:
    limpos = _conferir("cadastrar_cliente", campos)
    ja_havia = any(" ".join(f["nome"].split()).lower() == limpos["nome"].lower()
                   for f in estado.cadastros.listar())
    novo = estado.cadastros.salvar({**limpos, "tipo": "cliente"})
    registro = estado.cadastros.obter(novo)
    resumo = f"Cadastrei “{limpos['nome']}” como cliente"
    if limpos.get("documento"):
        resumo += f", {'CNPJ' if len(_digitos(limpos['documento'])) == 14 else 'CPF'} {limpos['documento']}"
    if ja_havia:
        resumo += " — já havia outra ficha com esse nome em Cadastros"
    return {"id": novo, "registro": registro, "resumo": resumo, "onde": "cadastros"}


def _criar_compromisso(estado, campos: dict) -> dict:
    limpos = _conferir("criar_compromisso", campos)
    # O que o cartão manda além do catálogo (tipo, onde) segue para a agenda,
    # que confere do jeito dela.
    novo = estado.agenda.salvar({**campos, **limpos})
    feito = estado.agenda.obter(novo)
    resumo = f"Anotei “{feito['titulo']}” em {_br(feito['data'])} às {feito['hora']}"
    if feito.get("avisar_min"):
        resumo += f", avisando {feito['avisar_min']} minutos antes"
    return {"id": novo, "registro": feito, "resumo": resumo, "onde": "calendario"}


def _emitir_nfse(estado, campos: dict) -> dict:
    # Só a rota, por enquanto. Os dados são conferidos como seriam na emissão
    # de verdade — e nada é enviado nem gravado.
    limpos = _conferir("emitir_nfse", campos)
    resumo = (f"Conferi a NFS-e para {limpos['cliente']}, de {_reais(limpos['valor'])}. "
              "A emissão ainda não está ligada: nada foi enviado nem gravado")
    return {"id": 0, "registro": limpos, "resumo": resumo, "onde": "", "pendente": True}


# Um livro de 300 páginas não cabe num cartão de conversa. O começo cabe, e o
# cartão diz que cortou.
LIMITE_DE_PARAGRAFOS = 1500


def leitura(doc) -> dict:
    """O que o visor da conversa mostra: páginas desenhadas no PDF, parágrafos no resto."""
    from pathlib import Path

    if Path(doc.path).suffix.lower() == ".pdf":
        return {"nome": doc.name, "tipo": "pdf", "paginas": int(doc.pages or 0) or 1}
    paragrafos = [p.strip() for p in (doc.text or "").splitlines() if p.strip()]
    return {"nome": doc.name, "tipo": "texto", "paginas": int(doc.pages or 0),
            "paragrafos": paragrafos[:LIMITE_DE_PARAGRAFOS],
            "cortado": len(paragrafos) > LIMITE_DE_PARAGRAFOS}


def _exibir_documento(estado, campos: dict) -> dict:
    # Só leitura: nada é gravado, nenhuma cópia nasce. Confirmar é o clique
    # em "Mostrar aqui".
    nome = _conferir("exibir_documento", campos)["nome"]
    doc = next((d for d in estado.searcher.documents if d.name == nome), None)
    if not doc:
        raise ValueError("esse documento não está mais no Acervo")
    return {"id": 0, "registro": leitura(doc), "resumo": f"Mostrei “{nome}” aqui na conversa", "onde": ""}


def oferta_de_exibir(fontes: list[dict], documentos, ja_oferecidos=()) -> dict | None:
    """
    Depois de uma resposta, quais documentos vale oferecer mostrar.

    Por regra, e sem modelo: os documentos de onde saíram os trechos. Um ou
    dois, oferecidos os dois; mais que isso, só o que deu mais da metade dos
    trechos — oferecer seis arquivos é não oferecer nenhum. O que já foi
    oferecido nesta conversa não volta a ser: perguntar três vezes do mesmo
    contrato não pode virar três convites.
    """
    contagem: dict[str, int] = {}
    for f in fontes or []:
        nome = str(f.get("documento") or "")
        if nome:
            contagem[nome] = contagem.get(nome, 0) + 1
    existentes = {d.name for d in documentos or []}
    nomes = [n for n in contagem if n in existentes]
    if len(nomes) > 2:
        mais = max(nomes, key=lambda n: contagem[n])
        nomes = [mais] if contagem[mais] * 2 > sum(contagem.values()) else []
    nomes = [n for n in nomes if n not in set(ja_oferecidos)]
    if not nomes:
        return None
    trechos = {n: [str(f.get("texto") or "")[:400] for f in fontes if f.get("documento") == n] for n in nomes}
    paginas = {n: next((f["pagina"] for f in fontes if f.get("documento") == n and f.get("pagina")), 0)
               for n in nomes}
    return {
        "tipo": "exibir", "ferramenta": "exibir_documento", "titulo": nomes[0],
        "campos": {"nome": nomes[0]}, "nomes": nomes, "trechos": trechos, "paginas": paginas,
        "porque": "a resposta saiu " + ("deste documento" if len(nomes) == 1 else "destes documentos"),
        "falta": "", "disponivel": True, "ajuda_do_modelo": [],
    }


EXECUTORES = {
    "cadastrar_cliente": _cadastrar_cliente,
    "criar_compromisso": _criar_compromisso,
    "exibir_documento": _exibir_documento,
    "emitir_nfse": _emitir_nfse,
}


def executar(ferramenta: str, campos: dict, estado) -> dict:
    """
    Faz o que a pessoa confirmou. Só a rota de confirmar chama isto.

    Devolve {id, registro, resumo, onde} — e `pendente` quando a ferramenta
    ainda não faz de verdade. Dado que não passa vira ValueError com o motivo.
    """
    if ferramenta not in EXECUTORES:
        raise ContratoInvalido(f"não existe a ferramenta {ferramenta!r}")
    return EXECUTORES[ferramenta](estado, dict(campos or {}))
