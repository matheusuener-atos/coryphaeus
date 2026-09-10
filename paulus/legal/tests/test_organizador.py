"""
Testes do organizador de acervo: varredura, classificacao por regra, plano,
aplicacao e desfazer.

Nao dependem do Ollama - a parte que chama o modelo e testada com o modelo
desligado (usar_modelo=False), que e o caminho por regra.

    python tests/test_organizador.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from classify import (  # noqa: E402
    Classificacao,
    classificar_documento,
    detectar_data,
    detectar_documentos,
    detectar_partes,
    detectar_tipo,
    detectar_valor,
)
from extract import Document  # noqa: E402
from organize import (  # noqa: E402
    SEM_VALOR,
    aplicar_plano,
    caminho_livre,
    desfazer,
    limpar_segmento,
    listar_diarios,
    montar_plano,
    render_padrao,
)
from scan import escanear, raizes_unicas  # noqa: E402

_falhas: list[str] = []


def checar(condicao: bool, descricao: str) -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        _falhas.append(descricao)


CONTRATO = """CONTRATO DE LOCACAO DE IMOVEL NAO RESIDENCIAL

LOCADOR: BELA VISTA EMPREENDIMENTOS LTDA., CNPJ n 11.222.333/0001-44, com sede
na Rua Sete de Setembro, 500.

LOCATARIA: ACME INDUSTRIA E COMERCIO LTDA., CNPJ n 12.345.678/0001-90.

CLAUSULA TERCEIRA - O aluguel mensal e de R$ 28.500,00 (vinte e oito mil e
quinhentos reais), com vencimento todo dia 5.

CLAUSULA QUINTA - A caucao e de R$ 85.500,00.

Rio de Janeiro, 15 de janeiro de 2024.
"""


def _doc(texto: str = CONTRATO, nome: str = "contrato.txt") -> Document:
    return Document(name=nome, path=f"/x/{nome}", text=texto, sha1="abc123")


# ------------------------------------------------------------------ varredura


def test_varredura() -> None:
    print("\nvarredura de pastas")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "clientes" / "acme").mkdir(parents=True)
        (base / "node_modules" / "lixo").mkdir(parents=True)
        (base / "clientes" / "acme" / "contrato.txt").write_text("x", encoding="utf-8")
        (base / "clientes" / "outro.pdf").write_bytes(b"%PDF-1.4 fake")
        (base / "clientes" / "planilha.xlsx").write_text("nao suportado", encoding="utf-8")
        (base / "node_modules" / "lixo" / "readme.txt").write_text("x", encoding="utf-8")

        v = escanear([base])
        nomes = {a.nome for a in v.arquivos}

        checar("contrato.txt" in nomes, "encontra arquivo em subpasta")
        checar("outro.pdf" in nomes, "encontra PDF")
        checar("planilha.xlsx" not in nomes, "ignora extensao nao suportada")
        checar("readme.txt" not in nomes, "pula pasta de sistema (node_modules)")
        checar(all(Path(a.path).exists() for a in v.arquivos), "caminhos apontam para arquivos reais")

        checar(len(escanear([base], limite=1).arquivos) == 1, "limite interrompe a varredura")
        checar(escanear([base / "nao-existe"]).total == 0, "raiz inexistente nao quebra")

        raso = escanear([base], profundidade=1)
        checar(
            all("acme" not in Path(a.path).parts for a in raso.arquivos),
            "profundidade 1 nao desce dois niveis",
        )

        excluida = escanear([base], excluir=["clientes"])
        checar(excluida.total == 0, "pasta excluida pelo usuario e pulada")


# --------------------------------------------------------------- classificacao


def test_raizes_aninhadas() -> None:
    """
    Regressao: escolher uma pasta e uma subpasta dela fazia a varredura visitar
    os mesmos arquivos duas vezes, e o plano proporia mover o mesmo documento
    duas vezes.
    """
    print("\nraizes repetidas e aninhadas")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        dentro = base / "clientes" / "acme"
        dentro.mkdir(parents=True)
        (dentro / "contrato.txt").write_text("x", encoding="utf-8")

        checar(len(raizes_unicas([base, dentro])) == 1, "subpasta e absorvida pela pasta mae")
        checar(len(raizes_unicas([base, base])) == 1, "mesma pasta duas vezes vira uma")
        checar(len(raizes_unicas([base / "nao-existe"])) == 0, "pasta inexistente e descartada")

        irma = base / "outra"
        irma.mkdir()
        checar(len(raizes_unicas([dentro, irma])) == 2, "pastas irmas continuam separadas")

        varredura = escanear([base, dentro])
        checar(varredura.total == 1, "arquivo em pasta aninhada e contado uma vez so")


def test_heuristicas() -> None:
    print("\nclassificacao por regra")
    checar(detectar_tipo(CONTRATO) == "locacao", "tipo pelo vocabulario do documento")
    checar(detectar_tipo("Excelentissimo Senhor Doutor Juiz de Direito") == "peticao", "peticao")
    checar(detectar_tipo("bilhete de padaria") == "outro", "documento fora do vocabulario e 'outro'")

    checar(detectar_data(CONTRATO) == "2024-01-15", "data por extenso vira ISO")
    checar(detectar_data("Assinado em 05/03/2026.") == "2026-03-05", "data numerica")
    checar(detectar_data("Sao Paulo, 1o de marco de 2025.") == "2025-03-01", "data com 1o")
    checar(detectar_data("sem data aqui") == "", "sem data devolve vazio")
    checar(detectar_data("Data invalida 45/45/2020") == "", "data impossivel e recusada")

    checar(detectar_valor(CONTRATO) == "R$ 85.500,00", "pega o maior valor do documento")
    checar(detectar_valor("sem valor") == "", "sem valor devolve vazio")

    docs = detectar_documentos(CONTRATO)
    checar(len(docs) == 2 and "12.345.678/0001-90" in docs, "extrai os CNPJs")

    partes = detectar_partes(CONTRATO)
    checar(any("BELA VISTA" in p for p in partes), "acha a parte apos LOCADOR:")
    checar(any("ACME" in p for p in partes), "acha a parte apos LOCATARIA:")
    checar(all("CNPJ" not in p for p in partes), "nome nao arrasta o CNPJ junto")


def test_classificacao_documento() -> None:
    print("\nclassificacao de um documento (sem modelo)")
    r = classificar_documento(_doc(), client=None, usar_modelo=False)

    checar(r.tipo == "locacao", "tipo detectado")
    checar(r.data == "2024-01-15" and r.ano == "2024", "data e ano")
    checar(r.mes_nome == "Janeiro", "mes por extenso")
    checar(bool(r.cliente), "cliente definido a partir das partes")
    checar(r.origem_tipo == "regra", "resolvido por regra, sem chamar o modelo")
    checar(r.confianca == "alta", "confianca alta quando regra resolve tudo")

    vazio = classificar_documento(_doc("papel qualquer sem nada"), client=None, usar_modelo=False)
    checar(vazio.tipo == "outro" and vazio.confianca == "baixa", "documento indecifravel: confianca baixa")

    pelo_nome = classificar_documento(
        _doc("texto irrelevante", "Procuracao Ad Judicia.pdf"), client=None, usar_modelo=False
    )
    checar(pelo_nome.tipo == "procuracao", "cai para o nome do arquivo quando o texto nao decide")


# ---------------------------------------------------------------- nomes/padrao


def test_nomes_de_pasta() -> None:
    print("\nnomes de pasta seguros no Windows")
    checar(limpar_segmento('ACME: Ind/Com <LTDA>') == "ACME Ind Com LTDA", "remove caracteres proibidos")
    checar(
        limpar_segmento("ACME INDUSTRIA E COMERCIO LTDA") == "Acme Industria e Comercio Ltda",
        "nome todo em caixa alta vira capitalizado",
    )
    checar(
        limpar_segmento("Bela Vista Empreendimentos") == "Bela Vista Empreendimentos",
        "caixa mista e preservada como o usuario escreveu",
    )
    checar(limpar_segmento("") == SEM_VALOR, "vazio vira pasta de revisao")
    checar(limpar_segmento("   ") == SEM_VALOR, "so espacos vira pasta de revisao")
    checar(limpar_segmento("CON") == "Con_", "nome reservado do Windows ganha sufixo")
    checar(len(limpar_segmento("A" * 200)) <= 60, "nome gigante e truncado")
    checar(not limpar_segmento("pasta.").endswith("."), "nao termina em ponto")


def test_padrao() -> None:
    print("\npadrao de pastas")
    r = classificar_documento(_doc(), client=None, usar_modelo=False)

    caminho, motivo = render_padrao("{cliente}/{tipo_rotulo}", r)
    checar(caminho.count("/") == 1 and "Locacao" in caminho, "dois niveis: cliente e tipo")
    checar(motivo == "", "sem campo faltando, sem motivo")

    por_data, _ = render_padrao("{ano}/{mes_nome}/{tipo_rotulo}", r)
    checar(por_data.startswith("2024/Janeiro/"), "padrao por ano e mes")

    sem_data = classificar_documento(_doc("Contrato de locacao sem data."), client=None, usar_modelo=False)
    caminho2, motivo2 = render_padrao("{ano}/{tipo_rotulo}", sem_data)
    checar(caminho2.startswith(SEM_VALOR), "campo vazio cai em pasta de revisao")
    checar("ano" in motivo2, "motivo explica qual campo faltou")

    fixo, _ = render_padrao("Contratos/{tipo_rotulo}", r)
    checar(fixo.startswith("Contratos/"), "texto fixo no padrao e preservado")


def test_colisao() -> None:
    print("\ncolisao de nomes")
    with tempfile.TemporaryDirectory() as tmp:
        alvo = Path(tmp) / "contrato.pdf"
        alvo.write_text("ja existe", encoding="utf-8")

        novo = caminho_livre(alvo)
        checar(novo != alvo and novo.name == "contrato (2).pdf", "arquivo existente ganha sufixo")
        checar(alvo.read_text(encoding="utf-8") == "ja existe", "arquivo original intacto")

        reservados = {str(novo).lower()}
        terceiro = caminho_livre(alvo, reservados)
        checar(terceiro.name == "contrato (3).pdf", "colisao dentro do proprio plano tambem conta")


# ----------------------------------------------------------- plano e aplicacao


def _acervo(base: Path) -> list[Classificacao]:
    """Tres arquivos reais em disco, ja classificados."""
    origem = base / "bagunca"
    origem.mkdir(parents=True)
    resultados = []
    for i, (nome, cliente, tipo) in enumerate(
        [
            ("contrato_a.txt", "ACME LTDA", "locacao"),
            ("contrato_b.txt", "ACME LTDA", "compra_e_venda"),
            ("contrato_c.txt", "NORTE SOLUCOES", "locacao"),
        ]
    ):
        arquivo = origem / nome
        arquivo.write_text(f"conteudo {i}", encoding="utf-8")
        resultados.append(
            Classificacao(
                arquivo=str(arquivo),
                nome=nome,
                sha1=f"sha{i}",
                tipo=tipo,
                partes=[cliente],
                cliente=cliente,
                data="2025-06-10",
            )
        )
    return resultados


def test_plano_nao_toca_disco() -> None:
    print("\nplano (nao pode tocar em disco)")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        acervo = _acervo(base)
        destino = base / "organizado"

        plano = montar_plano(acervo, destino, "{cliente}/{tipo_rotulo}")

        checar(plano.total == 3, "um movimento por documento")
        checar(not destino.exists(), "montar o plano NAO cria a pasta de destino")
        checar(all(Path(c.arquivo).exists() for c in acervo), "nenhum arquivo foi movido")

        pastas = {m.pasta_destino for m in plano.movimentos}
        checar(len(pastas) == 3, "clientes e tipos geram pastas distintas")
        checar(len(plano.resumo_por_pasta()) == 3, "resumo por pasta confere")

        com_erro = [Classificacao(arquivo="x", nome="x.pdf", sha1="", erro="PDF escaneado")]
        checar(montar_plano(com_erro, destino, "{cliente}").ignorados, "documento com erro fica de fora")

        so_confiavel = montar_plano(
            [Classificacao(arquivo="y", nome="y.pdf", sha1="s")],
            destino,
            "{cliente}",
            incluir_baixa_confianca=False,
        )
        checar(so_confiavel.total == 0, "filtro de confianca baixa funciona")


def test_aplicar_e_desfazer() -> None:
    print("\naplicar e desfazer")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        acervo = _acervo(base)
        destino = base / "organizado"
        diarios = base / "diarios"
        origens = [c.arquivo for c in acervo]
        conteudos = {Path(o).name: Path(o).read_text(encoding="utf-8") for o in origens}

        plano = montar_plano(acervo, destino, "{cliente}/{tipo_rotulo}")
        resultado = aplicar_plano(plano, diarios)

        checar(resultado.movidos == 3 and resultado.ok, "tres arquivos movidos sem falha")
        checar(all(not Path(o).exists() for o in origens), "arquivos sairam da origem")
        checar(all(Path(m.destino).exists() for m in plano.movimentos), "arquivos chegaram ao destino")
        checar(
            all(
                Path(m.destino).read_text(encoding="utf-8") == conteudos[Path(m.destino).name]
                for m in plano.movimentos
            ),
            "conteudo preservado no movimento",
        )
        checar(Path(resultado.diario).exists(), "diario gravado")

        lotes = listar_diarios(diarios)
        checar(len(lotes) == 1 and lotes[0]["pendentes"] == 3, "lote aparece na listagem")

        volta = desfazer(resultado.diario)
        checar(volta.movidos == 3 and volta.ok, "desfazer reverteu os tres")
        checar(all(Path(o).exists() for o in origens), "arquivos de volta ao lugar original")
        checar(
            all(Path(o).read_text(encoding="utf-8") == conteudos[Path(o).name] for o in origens),
            "conteudo preservado na volta",
        )
        checar(not any(destino.rglob("*.txt")), "nada ficou no destino")
        checar(listar_diarios(diarios)[0]["pendentes"] == 0, "diario marcado como desfeito")


def test_aplicar_nao_sobrescreve() -> None:
    print("\naplicar nunca sobrescreve")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        origem = base / "bagunca"
        origem.mkdir()
        arquivo = origem / "contrato.txt"
        arquivo.write_text("novo", encoding="utf-8")

        destino = base / "organizado"
        (destino / "Acme Ltda" / "Locacao").mkdir(parents=True)
        ja_existe = destino / "Acme Ltda" / "Locacao" / "contrato.txt"
        ja_existe.write_text("ANTIGO - NAO PODE SUMIR", encoding="utf-8")

        acervo = [
            Classificacao(
                arquivo=str(arquivo), nome="contrato.txt", sha1="s",
                tipo="locacao", partes=["ACME LTDA"], cliente="ACME LTDA", data="2025-01-01",
            )
        ]
        plano = montar_plano(acervo, destino, "{cliente}/{tipo_rotulo}")
        aplicar_plano(plano, base / "diarios")

        checar(ja_existe.read_text(encoding="utf-8") == "ANTIGO - NAO PODE SUMIR", "arquivo pre-existente intacto")
        checar((destino / "Acme Ltda" / "Locacao" / "contrato (2).txt").exists(), "novo arquivo entrou com sufixo")


def test_aplicar_com_arquivo_sumido() -> None:
    print("\narquivo que sumiu entre o plano e a aplicacao")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        acervo = _acervo(base)
        destino = base / "organizado"

        plano = montar_plano(acervo, destino, "{tipo_rotulo}")
        Path(acervo[0].arquivo).unlink()  # usuario apagou o arquivo nesse meio tempo

        resultado = aplicar_plano(plano, base / "diarios")
        checar(resultado.movidos == 2, "move os que sobraram")
        checar(len(resultado.falhas) == 1, "reporta o que sumiu, sem quebrar o lote")

        volta = desfazer(resultado.diario)
        checar(volta.movidos == 2, "desfazer reverte so o que foi movido de fato")


def main() -> int:
    print("=" * 55)
    print("  PAULUS Legal - testes do organizador")
    print("=" * 55)

    test_varredura()
    test_raizes_aninhadas()
    test_heuristicas()
    test_classificacao_documento()
    test_nomes_de_pasta()
    test_padrao()
    test_colisao()
    test_plano_nao_toca_disco()
    test_aplicar_e_desfazer()
    test_aplicar_nao_sobrescreve()
    test_aplicar_com_arquivo_sumido()

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
