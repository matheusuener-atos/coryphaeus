"""
As tabelas oficiais da NFS-e que vão no PAULUS (docs/PROGRESSO-NFSE.md, N1).

Lê as planilhas e os XSD publicados no Portal da NFS-e e grava, em
src/nfse/tabelas/, um JSON por tabela, cada um com a versão, a data e o link
de onde veio:

  - municipios.json: código IBGE, nome e UF (Anexo A, TAB.MUN_IBGE);
  - servicos.json: código de tributação nacional (cTribNac, 6 dígitos) e a
    descrição (Anexo B, LISTA.SERV.NAC.);
  - nbs.json: NBS com e sem pontos (Anexo B, LISTA.NBS_v2.0);
  - indop.json: código indicador da operação do IBS/CBS (Anexo C);
  - correlacao.json: a sugestão item × NBS × cIndOp × cClassTrib (Anexo VIII,
    que o próprio portal chama de "trabalho inicial, sem regra de negócio":
    o PAULUS mostra como sugestão, nunca decide por ela);
  - dominios.json: os domínios que moram no XSD (motivos de cancelamento e de
    substituição, regimes especiais, opção pelo Simples, regime de apuração,
    tipo de retenção, CST do PIS/COFINS).

Nada disso é editado à mão no código: tabela nova = planilha nova = rodar
este script de novo (ou importar a planilha em Configurações › Nota fiscal,
que usa as mesmas funções).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/nfse_tabelas.py <pasta com os .xlsx>

A pasta precisa ter os arquivos com os nomes do portal (anexo_a-..., anexo_b-...,
anexo-c-..., anexoviii-...). Os XSD saem de src/nfse/xsd/.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from nfse import tabelas  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    pasta = Path(argv[1])
    gravadas = tabelas.gerar_de_pasta(pasta, tabelas.PASTA_EMBUTIDA)
    for nome, info in gravadas.items():
        print(f"{nome}: {info['itens']} itens, versão {info['versao']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
