"""
Testes do certificado digital e da assinatura.

Esta e a parte do programa em que errar nao produz um bug de interface. Um
documento assinado com certificado vencido, ou um programa que chama de
"assinado com validade juridica" o que saiu de um autoassinado, causa dano
fora do computador.

Por isso os testes daqui cobrem menos "funciona?" e mais "recusa quando tem
que recusar, e conta a verdade sobre o que fez":

  - senha errada nao abre, e diz por que
  - certificado vencido nao assina
  - certificado fora da ICP-Brasil e marcado como tal, em todo lugar
  - arquivo mexido depois de assinado e detectado
  - o original nunca e sobrescrito
  - sem a permissao ligada, nada e assinado - o pedido vai para a fila
  - a senha guardada nao fica em texto no disco

    python tests/test_assinatura.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import assinatura  # noqa: E402
import certificado  # noqa: E402

SENHA = "senha-de-teste-123"

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {detalhe}")
        _falhas.append(descricao)


def _pdf_de_teste(pasta: Path) -> Path:
    """
    Um PDF real para assinar.

    Usa um dos contratos de exemplo do projeto: PDF gerado por editor de texto
    tem particularidades - xref hibrido, entre outras - que um PDF sintetico
    nao teria, e foi exatamente ai que a primeira versao quebrou.
    """
    for origem in sorted((RAIZ / "data" / "test_contracts").glob("*.pdf")):
        if assinatura.ler(origem).assinaturas == 0:
            return Path(shutil.copy(origem, pasta / "documento.pdf"))
    return None


def _pdf_ja_assinado(pasta: Path) -> Path | None:
    """Um PDF que ja vem com assinatura, para testar o que nao pode ser perdido."""
    for origem in sorted((RAIZ / "data" / "test_contracts").glob("*.pdf")):
        if assinatura.ler(origem).assinaturas > 0:
            return Path(shutil.copy(origem, pasta / "ja-assinado.pdf"))
    return None


# ------------------------------------------------------------- certificado


def test_leitura_do_certificado(tmp: Path) -> Path:
    print("\nleitura do certificado")
    pfx = certificado.gerar_de_teste(tmp / "teste.pfx", SENHA, "MARIA DE TESTE")

    c = certificado.ler(pfx, SENHA)
    checar(not c.erro, "abre com a senha certa", c.erro)
    checar(c.titular == "MARIA DE TESTE", f"le o titular (achou {c.titular!r})")
    checar(c.documento == "000.000.000-00", f"le o documento (achou {c.documento!r})")
    checar(c.serie != "", "le o numero de serie")
    checar(len(c.valido_ate) == 10, f"le a validade (achou {c.valido_ate!r})")
    checar(c.pode_assinar, "certificado novo pode assinar")

    errada = certificado.ler(pfx, "outra")
    checar(bool(errada.erro), "senha errada nao abre")
    checar("senha" in errada.erro.lower(), f"e diz que e a senha ({errada.erro!r})")
    checar(not errada.pode_assinar, "certificado que nao abriu nao assina")

    sumido = certificado.ler(tmp / "nao-existe.pfx", SENHA)
    checar(bool(sumido.erro), "arquivo inexistente vira erro, nao exception")

    return pfx


def test_icp_brasil() -> None:
    """
    A deteccao errou com um certificado real desta maquina: a lista de
    fabricantes nao tinha "AC CONSULTI RFB". As ACs da Receita seguem o padrao
    "AC <fabricante> RFB", e e o padrao que vale, nao a lista.
    """
    print("\nquem e da ICP-Brasil")
    sao = ["AC CONSULTI RFB", "AC DIGITALSIGN RFB G3", "AC Certisign RFB G5",
           "AC SOLUTI Multipla RFB", "AC OAB G3", "Autoridade Certificadora Raiz Brasileira v10"]
    nao = ["localhost", "MARIA DE TESTE", "ACME RFBrasil Ltda", "DigiCert Global Root", ""]

    checar(all(certificado.e_icp(e) for e in sao), "reconhece as autoridades da ICP-Brasil",
           str([e for e in sao if not certificado.e_icp(e)]))
    checar(not any(certificado.e_icp(e) for e in nao), "nao confunde emissor comum com ICP-Brasil",
           str([e for e in nao if certificado.e_icp(e)]))

    c = certificado.Certificado(emissor="MARIA DE TESTE", icp_brasil=False)
    checar(c.to_dict()["icp_brasil"] is False, "o dado chega na tela dizendo que nao e ICP")


def test_certificado_vencido(tmp: Path) -> None:
    """Vencido assina do ponto de vista tecnico; o programa tem que recusar."""
    print("\ncertificado vencido")

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "JOAO VENCIDO:11122233344")])
    ontem = datetime.now(timezone.utc) - timedelta(days=1)
    cert = (
        x509.CertificateBuilder()
        .subject_name(nome).issuer_name(nome)
        .public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(ontem - timedelta(days=400))
        .not_valid_after(ontem)
        .sign(chave, hashes.SHA256())
    )
    alvo = tmp / "vencido.pfx"
    alvo.write_bytes(pkcs12.serialize_key_and_certificates(
        name=b"v", key=chave, cert=cert, cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(SENHA.encode()),
    ))

    c = certificado.ler(alvo, SENHA)
    checar(c.vencido, "percebe que venceu")
    checar(c.situacao == "vencido", f"a tela recebe 'vencido' (achou {c.situacao!r})")
    checar(not c.pode_assinar, "certificado vencido nao pode assinar")

    pdf = _pdf_de_teste(tmp)
    if pdf:
        r = assinatura.assinar(pdf, tmp / "saida.pdf", arquivo_pfx=alvo, senha=SENHA,
                               selo=dict(certificado.PADRAO_SELO))
        checar(bool(r.erro), "assinar com vencido devolve erro")
        checar(not (tmp / "saida.pdf").exists(), "e nao deixa arquivo pela metade")


def test_vencimento_e_uma_hora() -> None:
    """
    O vencimento e um instante, nao um dia.

    Este teste existe porque a suite quebrou as 21h de um dia 10: o certificado
    vencia "ontem" em UTC, que ja era o dia 10, e o codigo comparava essa data
    com o dia 10 do relogio local. Vencido virava "vence em breve", e
    pode_assinar vinha True - ou seja, o programa assinaria com um e-CPF fora
    da validade durante as tres horas em que o Brasil esta na vespera de
    Greenwich. Com hora, nao ha janela.
    """
    print("\nvencimento com hora, nao so com data")
    agora = datetime.now(timezone.utc)

    venceu = certificado.Certificado(
        titular="TESTE", valido_ate=(agora - timedelta(hours=3)).strftime("%Y-%m-%d"),
        vence_em=(agora - timedelta(hours=3)).isoformat())
    checar(venceu.vencido, "venceu ha 3 horas: vencido")
    checar(venceu.situacao == "vencido", f"e a tela diz isso (achou {venceu.situacao!r})")
    checar(not venceu.pode_assinar, "e nao assina")

    vence = certificado.Certificado(
        titular="TESTE", valido_ate=(agora + timedelta(hours=3)).strftime("%Y-%m-%d"),
        vence_em=(agora + timedelta(hours=3)).isoformat())
    checar(not vence.vencido, "vence daqui a 3 horas: ainda vale")
    checar(vence.pode_assinar, "e ainda assina")

    sem_data = certificado.Certificado(titular="TESTE")
    checar(not sem_data.vencido, "sem data de vencimento, nao inventa vencimento")
    checar(sem_data.dias_restantes is None, "e nao inventa prazo")


def test_cofre(tmp: Path, pfx: Path) -> None:
    print("\ncofre: arquivo, senha e prazo")
    pasta = tmp / "cofre"
    cofre = certificado.Cofre(pasta / "cofre.json", pasta)

    cofre.guardar_arquivo("meu.pfx", pfx.read_bytes())
    checar(cofre.arquivo.exists(), "guarda uma copia do certificado")
    checar(cofre.arquivo.parent == pasta, "dentro da pasta do programa")

    checar(cofre.senha_agora() == "", "sem senha digitada, nao inventa senha")
    lido = cofre.certificado()
    checar(bool(lido.erro), "sem senha, o cartao diz que precisa da senha")

    cofre.lembrar(SENHA)
    checar(cofre.senha_agora() == SENHA, "lembra a senha durante o prazo")
    checar(cofre.certificado().titular == "MARIA DE TESTE", "e consegue ler o certificado")

    # Prazo vencido: a senha some sozinha.
    cofre._vale_ate = 0
    checar(cofre.senha_agora() == "", "passado o prazo, esquece a senha")

    if certificado.dpapi_disponivel():
        cofre.lembrar(SENHA)
        checar(cofre.proteger(SENHA), "guarda a senha protegida")
        bruto = (pasta / "cofre.json").read_text(encoding="utf-8")
        checar(SENHA not in bruto, "a senha NAO fica em texto no arquivo")
        cofre.esquecer_senha()
        checar(cofre.senha_agora() == SENHA, "e volta a ler a senha guardada")
    else:
        checar(True, "sem DPAPI nesta maquina - guardar senha fica indisponivel")

    cofre.remover()
    checar(not (pasta / "certificado.pfx").exists(), "remover apaga a copia")
    checar(cofre.dados["senha_protegida"] == "", "remover apaga a senha guardada")
    checar(cofre.senha_agora() == "", "e a memoria tambem")


# ----------------------------------------------------------------- paginas


def test_quais_paginas() -> None:
    print("\nem quais paginas o selo entra")
    alvo = assinatura.paginas_alvo

    checar(alvo("todas", 4) == [1, 2, 3, 4], "todas")
    checar(alvo("ultima", 4) == [4], "so a ultima")
    checar(alvo("primeira_ultima", 4) == [1, 4], "primeira e ultima")
    checar(alvo("primeira_ultima", 1) == [1], "documento de uma pagina nao repete o selo")
    checar(alvo("intervalo", 12, "1-3, 7, 12") == [1, 2, 3, 7, 12], "intervalo misto")
    checar(alvo("intervalo", 12, "3-1") == [1, 2, 3], "intervalo invertido e aceito")
    checar(alvo("intervalo", 12, "1-3, 2") == [1, 2, 3], "nao repete pagina pedida duas vezes")
    checar(alvo("intervalo", 4, "99") == [], "pagina que nao existe fica de fora")
    checar(alvo("intervalo", 4, "abacaxi") == [], "texto sem sentido nao derruba")
    checar(alvo("todas", 0) == [], "documento sem pagina devolve vazio")


def test_texto_do_selo() -> None:
    print("\no que aparece no selo")
    c = certificado.Certificado(
        titular="MARIA DE TESTE", documento="123.456.789-00",
        emissor="AC CONSULTI RFB", tipo="e-CPF A1",
    )
    quando = datetime(2026, 9, 10, 14, 30)

    selo = dict(certificado.PADRAO_SELO)
    texto = assinatura.texto_do_selo(selo, c, "ABC123", quando)
    checar("MARIA DE TESTE" in texto, "troca {nome} pelo titular")
    checar("123.456.789-00" in texto, "mostra o documento")
    checar("10/09/2026" in texto, "mostra a data em portugues")
    checar("ABC123" in texto, "mostra o codigo de conferencia")

    escondido = {**selo, "mostrar_cpf": False, "mostrar_codigo": False, "mostrar_data": False}
    texto2 = assinatura.texto_do_selo(escondido, c, "ABC123", quando)
    checar("123.456.789-00" not in texto2, "esconder o CPF esconde mesmo")
    checar("ABC123" not in texto2, "esconder o codigo esconde mesmo")
    checar("10/09/2026" not in texto2, "esconder a data esconde mesmo")

    livre = {**selo, "texto": "Eu, {nome}, CPF {cpf}, assinei em {data} as {hora}."}
    texto3 = assinatura.texto_do_selo(livre, c, "ABC123", quando)
    checar("Eu, MARIA DE TESTE, CPF 123.456.789-00" in texto3, "preenche varios campos na mesma linha")
    checar("14:30" in texto3, "preenche a hora")

    inventado = {**selo, "texto": "vale {inexistente}"}
    texto4 = assinatura.texto_do_selo(inventado, c, "ABC123", quando)
    checar("{inexistente}" in texto4, "campo desconhecido fica como esta, sem quebrar")


def test_onde_o_selo_cai() -> None:
    print("\nonde o selo cai na pagina")
    largura, altura = 595.0, 842.0

    x1, y1, x2, y2 = assinatura.caixa("rodape_direita", largura, altura)
    checar(x2 <= largura and y2 <= altura, "nao passa da borda da pagina")
    checar(y1 < altura / 2, "rodape fica na metade de baixo")

    tx1, ty1, _, _ = assinatura.caixa("topo_direita", largura, altura)
    checar(ty1 > altura / 2, "topo fica na metade de cima")

    cx1, _, cx2, _ = assinatura.caixa("rodape_centro", largura, altura)
    checar(abs((cx1 + cx2) / 2 - largura / 2) < 2, "centralizado fica no centro")

    # Pagina menor que o selo nao pode gerar coordenada negativa.
    px1, py1, _, _ = assinatura.caixa("rodape_direita", 100, 100)
    checar(px1 >= 0 and py1 >= 0, "pagina pequena nao produz posicao negativa")


# ---------------------------------------------------------------- assinar


def test_assinar_de_verdade(tmp: Path, pfx: Path) -> None:
    print("\nassinar e conferir")
    pdf = _pdf_de_teste(tmp)
    if pdf is None:
        checar(False, "havia um PDF de exemplo para assinar")
        return

    antes = pdf.read_bytes()
    doc = assinatura.ler(pdf)
    checar(doc.paginas > 0, f"le quantas paginas tem (achou {doc.paginas})")
    checar(doc.assinaturas == 0, "o documento de partida nao tem assinatura")

    destino = tmp / "assinado.pdf"
    r = assinatura.assinar(pdf, destino, arquivo_pfx=pfx, senha=SENHA,
                           selo=dict(certificado.PADRAO_SELO), escolha_paginas="ultima")
    checar(not r.erro, "assina sem erro", r.erro)
    checar(destino.exists(), "grava o arquivo assinado")
    checar(pdf.read_bytes() == antes, "NAO mexe no arquivo original")
    checar(len(r.codigo) == 6, f"gera codigo de conferencia (achou {r.codigo!r})")
    checar(r.icp_brasil is False, "avisa que o certificado nao e da ICP-Brasil")

    conferido = assinatura.verificar(destino)
    checar(len(conferido) == 1, f"o arquivo assinado tem 1 assinatura (achou {len(conferido)})")
    if conferido:
        a = conferido[-1]
        checar(a["intacta"] is True, "a assinatura confere com o conteudo")
        checar(a["cobre_documento_todo"] is True, "a assinatura cobre o documento inteiro")
        checar(a["titular"] == "MARIA DE TESTE", "diz quem assinou")
        checar(a["icp_brasil"] is False, "e diz que o emissor nao e da ICP-Brasil")

    # Selo em varias paginas: continua sendo UMA assinatura.
    varias = tmp / "varias.pdf"
    r2 = assinatura.assinar(pdf, varias, arquivo_pfx=pfx, senha=SENHA,
                            selo=dict(certificado.PADRAO_SELO), escolha_paginas="todas")
    checar(not r2.erro, "assina com selo em todas as paginas", r2.erro)
    if not r2.erro:
        checar(r2.paginas == list(range(1, doc.paginas + 1)), "carimba todas as paginas")
        checar(len(assinatura.verificar(varias)) == 1,
               "selo em N paginas continua sendo UMA assinatura")


def test_adulteracao_e_detectada(tmp: Path, pfx: Path) -> None:
    """A propriedade que da sentido a tudo: mexeu depois, aparece."""
    print("\ndocumento mexido depois de assinado")
    pdf = _pdf_de_teste(tmp)
    if pdf is None:
        return

    assinado = tmp / "para-adulterar.pdf"
    r = assinatura.assinar(pdf, assinado, arquivo_pfx=pfx, senha=SENHA,
                           selo=dict(certificado.PADRAO_SELO), escolha_paginas="ultima")
    if r.erro:
        checar(False, "assinou o documento para o teste", r.erro)
        return

    dados = bytearray(assinado.read_bytes())
    ponto = dados.find(b"/Type")
    dados[ponto:ponto + 5] = b"/TypX"
    mexido = tmp / "mexido.pdf"
    mexido.write_bytes(bytes(dados))

    conferido = assinatura.verificar(mexido)
    checar(bool(conferido) and conferido[0].get("intacta") is False,
           "arquivo alterado depois da assinatura e detectado",
           str(conferido))


def test_assinatura_alheia_nao_se_perde(tmp: Path, pfx: Path) -> None:
    """
    Assinar um contrato que a outra parte ja assinou nao pode apagar a
    assinatura dela. E o caso real do acervo deste projeto: um dos contratos
    de exemplo ja vem assinado com e-CPF de verdade.
    """
    print("\ndocumento que a outra parte ja assinou")
    pdf = _pdf_ja_assinado(tmp)
    if pdf is None:
        checar(True, "nenhum PDF ja assinado no acervo - teste pulado")
        return

    antes = assinatura.verificar(pdf)
    # Quantas assinaturas o documento de partida tem e circunstancial: depende
    # de qual PDF assinado esta no acervo desta maquina, e o acervo muda. O que
    # este teste promete e outra coisa - que assinar ACRESCENTA, e nao
    # substitui. Entao o numero que importa e a diferenca, nao o total.
    checar(bool(antes), f"o documento de partida ja vem assinado ({len(antes)})")
    checar(all(a["icp_brasil"] for a in antes),
           "e as assinaturas sao de certificado da ICP-Brasil")

    destino = tmp / "mais-uma-assinatura.pdf"
    r = assinatura.assinar(pdf, destino, arquivo_pfx=pfx, senha=SENHA,
                           selo=dict(certificado.PADRAO_SELO), escolha_paginas="ultima")
    checar(not r.erro, "assina por cima sem erro", r.erro)

    depois = assinatura.verificar(destino)
    checar(len(depois) == len(antes) + 1,
           f"a nova entra sem tirar as que havia ({len(antes)} → {len(depois)})")
    if len(depois) == len(antes) + 1:
        checar([a["titular"] for a in depois[:len(antes)]] ==
               [a["titular"] for a in antes],
               "as assinaturas da outra parte continuam la, na ordem")
        checar(all(a["intacta"] for a in depois[:len(antes)]),
               "e continuam conferindo - nenhuma foi invalidada")
        checar(depois[-1]["titular"] == "MARIA DE TESTE", "a nova assinatura foi acrescentada")

    # Proteger com senha reescreveria o arquivo e apagaria a assinatura alheia.
    protegido = tmp / "nao-deve-existir.pdf"
    r2 = assinatura.assinar(pdf, protegido, arquivo_pfx=pfx, senha=SENHA,
                            selo=dict(certificado.PADRAO_SELO), escolha_paginas="ultima",
                            senha_pdf="123456")
    checar(bool(r2.erro), "recusa proteger com senha um PDF que ja tem assinatura")
    checar("apagaria" in r2.erro, f"e explica por que ({r2.erro!r})")
    checar(not protegido.exists(), "e nao grava arquivo nenhum")


def test_senha_no_pdf(tmp: Path, pfx: Path) -> None:
    print("\nPDF protegido por senha")
    pdf = _pdf_de_teste(tmp)
    if pdf is None:
        return

    destino = tmp / "com-senha.pdf"
    r = assinatura.assinar(pdf, destino, arquivo_pfx=pfx, senha=SENHA,
                           selo=dict(certificado.PADRAO_SELO), escolha_paginas="ultima",
                           senha_pdf="abrir-123")
    checar(not r.erro, "assina e protege", r.erro)
    checar(r.protegido, "o resultado diz que o arquivo saiu protegido")

    sem_senha = assinatura.verificar(destino)
    checar(bool(sem_senha) and "erro" in sem_senha[0],
           "sem a senha, a conferencia avisa em vez de fingir que leu")

    com_senha = assinatura.verificar(destino, "abrir-123")
    checar(bool(com_senha) and com_senha[0].get("intacta") is True,
           "com a senha, confere normalmente")


def test_registro(tmp: Path) -> None:
    print("\nregistro das assinaturas")
    reg = assinatura.Registro(tmp / "assinaturas.json")
    r = assinatura.Resultado(
        destino=str(tmp / "x.pdf"), codigo="A1B2C3", paginas=[4],
        titular="MARIA DE TESTE", icp_brasil=False,
        quando=datetime.now().isoformat(timespec="seconds"),
    )
    reg.anotar(r, tmp / "origem.pdf")

    checar(reg.para_tela()["total"] == 1, "anota a assinatura")
    achado = reg.procurar("a1b2c3")
    checar(achado is not None, "acha pelo codigo, sem ligar para maiuscula")
    checar(achado and achado["icp_brasil"] is False, "o registro guarda que nao era ICP-Brasil")
    checar(reg.procurar("ZZZZZZ") is None, "codigo inexistente devolve None")

    de_novo = assinatura.Registro(tmp / "assinaturas.json")
    checar(de_novo.para_tela()["total"] == 1, "o registro sobrevive a fechar o programa")


def test_resumo_em_portugues() -> None:
    print("\na frase antes de assinar")
    c = certificado.Certificado(titular="MARIA DE TESTE", tipo="e-CPF A1")
    doc = assinatura.Documento(paginas=12)

    uma = assinatura.resumo_em_portugues(c, doc, [12], "")
    checar("na página 12" in uma, f"uma pagina: concordancia certa ({uma})")
    checar("internet" in uma, "diz que nada sai para a internet")

    todas = assinatura.resumo_em_portugues(c, doc, list(range(1, 13)), "")
    checar("em todas as 12 páginas" in todas, "todas as paginas")
    checar("assinatura digital é uma só" in todas,
           "explica que varios selos nao sao varias assinaturas")

    protegido = assinatura.resumo_em_portugues(c, doc, [12], "senha")
    checar("protegido por senha" in protegido, "avisa da senha do arquivo")


# ------------------------------------------------------- a fila decide


def test_sem_permissao_nao_assina(tmp: Path, pfx: Path) -> None:
    """
    A regra da casa: assinar tem efeito juridico e por padrao passa pela fila.
    Sem a permissao ligada, chamar a rota nao pode produzir arquivo nenhum.
    """
    print("\nsem permissao, nada e assinado")
    import api

    pdf = _pdf_de_teste(tmp)
    if pdf is None:
        return

    guardados = (api.estado.cofre, api.estado.assinaturas, api.estado.pasta)
    try:
        pasta = tmp / "cofre-api"
        api.estado.cofre = certificado.Cofre(pasta / "cofre.json", pasta)
        api.estado.cofre.guardar_arquivo("c.pfx", pfx.read_bytes())
        api.estado.cofre.lembrar(SENHA)
        api.estado.assinaturas = assinatura.Registro(tmp / "reg-api.json")
        api.estado.pasta = tmp / "acervo"
        api.estado.pasta.mkdir(exist_ok=True)

        checar(not api.estado.prefs.pode("assinar"),
               "a permissao de assinar sozinho vem desligada")

        antes = set(tmp.rglob("*.pdf"))
        d = api.assinar_agora(api.PedidoAssinatura(arquivo=str(pdf), paginas="ultima"))

        checar(d.get("aguardando_aprovacao") is True, "o pedido vai para a fila")
        checar(set(tmp.rglob("*.pdf")) == antes, "NENHUM arquivo foi assinado ainda")

        pedido = d["pedido"]
        checar(pedido["categoria"] == "assinatura", "o pedido entra na categoria certa")
        checar(pedido["reversivel"] is False, "o pedido avisa que nao da para desfazer")
        checar(any("ICP" in e for e in pedido["etiquetas"]),
               f"a etiqueta avisa do certificado fora da ICP ({pedido['etiquetas']})")
        checar("página" in pedido["resumo"], "o resumo explica em portugues o que vai acontecer")

        # Agora o sim: e so agora o arquivo aparece.
        resultado = api.aprovacoes_decidir(api.Decisao(ids=[pedido["id"]], aprovar=True))
        checar(not resultado["falhas"], f"a aprovacao executa sem falha ({resultado['falhas']})")
        checar(len(set(tmp.rglob("*.pdf"))) > len(antes), "depois do sim, o assinado existe")
        feito = resultado["feitos"][0]
        checar("ICP-Brasil" in feito.get("resultado", ""),
               f"o resultado registrado avisa do certificado ({feito.get('resultado')})")

        api.estado.fila.esquecer(pedido["id"])
    finally:
        api.estado.cofre, api.estado.assinaturas, api.estado.pasta = guardados


def main() -> int:
    print("=" * 55)
    print("PAULUS - certificado digital e assinatura")
    print("=" * 55)

    with tempfile.TemporaryDirectory() as bruto:
        tmp = Path(bruto)
        pfx = test_leitura_do_certificado(tmp)
        test_icp_brasil()
        test_certificado_vencido(tmp)
        test_vencimento_e_uma_hora()
        test_cofre(tmp, pfx)
        test_quais_paginas()
        test_texto_do_selo()
        test_onde_o_selo_cai()
        test_assinar_de_verdade(tmp, pfx)
        test_assinatura_alheia_nao_se_perde(tmp, pfx)
        test_adulteracao_e_detectada(tmp, pfx)
        test_senha_no_pdf(tmp, pfx)
        test_registro(tmp)
        test_resumo_em_portugues()
        test_sem_permissao_nao_assina(tmp, pfx)

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
