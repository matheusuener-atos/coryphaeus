"""
A conferência jurídica do documento (docs/PLANO-EDITOR.md, E6), por regra.

  - o extenso lido de volta em número ("oitocentos e cinquenta mil",
    "um milhão e duzentos mil", "cento e oitenta e sete mil e quinhentos reais");
  - os seis documentos do banco de provas, limpos: nenhum aviso (sem alarme
    falso - o [●] da linha de testemunha não conta);
  - cada erro achado no bloco certo: valor e extenso que não batem (reais,
    prazo, percentual), data que não existe, cláusula repetida e pulada,
    referência para cláusula que não existe, referência que mudou de cláusula
    depois de apagar uma, termo de parte sem definição, lacuna, CPF que não
    fecha, conversa de assistente no corpo, artigo de lei que não existe ou
    revogado (base de leis de mentira);
  - `novos`: só o que a rodada criou;
  - o agente diz, na resposta, o problema que a mudança dele criou.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_editor_conferencia.py
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tools" / "bancada_editor"))

import agente_de_edicao as AG  # noqa: E402
import bancada  # noqa: E402
import blocos as B  # noqa: E402
import conferencia_juridica as C  # noqa: E402
import edicao as ED  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def titulos(avisos: list[dict]) -> list[str]:
    return [a["titulo"] for a in avisos]


def teste_extenso() -> None:
    print("o extenso de volta em número")
    casos = {"oitocentos e cinquenta mil": 850000, "um milhão e duzentos mil": 1200000, "vinte e quatro": 24,
             "cento e setenta mil": 170000, "dois mil e seiscentos": 2600, "dez": 10, "cem": 100, "mil": 1000}
    for texto, n in casos.items():
        checar(C.numero_do_extenso(texto) == n, f"“{texto}” = {n}", C.numero_do_extenso(texto))
    checar(C.numero_do_extenso("trinta dias corridos") is None, "texto que não é só número: None")
    checar(C._reais_do_extenso("cento e oitenta e sete mil e quinhentos reais") == 187500.0, "reais por extenso")
    checar(C._reais_do_extenso("dez reais e cinquenta centavos") == 10.5, "com centavos")


def teste_corpus_limpo() -> None:
    print("os documentos limpos não têm aviso")
    for nome in ("compra_venda", "locacao", "procuracao", "peticao", "partilha", "notificacao"):
        av = C.conferir(bancada.documento(nome))
        checar(not av, f"{nome}: nenhum alarme falso", [(a["titulo"], a["detalhe"][:60]) for a in av])


def com(nome: str, ops: list) -> tuple[list, list]:
    antes = bancada.documento(nome)
    r = ED.aplicar(antes, ops, rodada=1)
    return antes, r.blocos


def teste_erros() -> None:
    print("cada erro, no bloco certo")
    antes, depois = com("locacao", [{"op": "substituir", "bloco": "b0b0011", "de": "R$ 2.400,00", "para": "R$ 2.600,00"},
                                    {"op": "substituir", "bloco": "b0b0008", "de": "30 (trinta) meses", "para": "36 (trinta) meses"},
                                    {"op": "substituir", "bloco": "b0b0015", "de": "10% (dez", "para": "12% (dez"},
                                    {"op": "substituir", "bloco": "b0b0008", "de": "30 de abril de 2029", "para": "31 de abril de 2029"}])
    av = C.conferir(depois)
    por = {a["detalhe"][:30]: a for a in av}
    valor = next((a for a in av if a["titulo"] == "Valor e extenso não batem"), None)
    checar(valor and valor["bloco"] == "b0b0011" and valor["rotulo"] == "Cláusula 3ª", "R$ 2.600,00 com “dois mil e quatrocentos”",
           valor)
    numeros = [a for a in av if a["titulo"] == "Número e extenso não batem"]
    checar({a["bloco"] for a in numeros} == {"b0b0008", "b0b0015"}, "prazo e percentual com extenso errado", numeros)
    data = next((a for a in av if a["titulo"] == "Data que não existe"), None)
    checar(data and "31 de abril de 2029" in data["detalhe"], "31 de abril não existe", data)

    antes, depois = com("locacao", [{"op": "apagar", "bloco": "Cláusula 2ª"}])
    ED.renumerar(depois, 1)
    novos = C.novos(C.conferir(antes), C.conferir(depois, antes=antes))
    mudou = next((a for a in novos if a["titulo"] == "Referência que mudou de cláusula"), None)
    checar(mudou and mudou["bloco"] == "b0b0024" and "DO PRAZO" in mudou["detalhe"],
           "apagar a cláusula do prazo: “conforme a cláusula 2ª” passou a apontar para outra", mudou)

    bs = bancada.documento("compra_venda")
    cabeca = B.por_id(bs)["b0a0014"]
    B.reescrever(cabeca, "CLÁUSULA SEGUNDA – DA POSSE", "s1", 1)
    av = C.conferir(bs)
    checar("Cláusula repetida" in titulos(av), "duas cláusulas segundas", titulos(av))
    bs = bancada.documento("compra_venda")
    B.reescrever(B.por_id(bs)["b0a0019"], "O descumprimento autoriza a rescisão, observada a cláusula 9.", "s1", 1)
    av = C.conferir(bs)
    ref = next((a for a in av if a["titulo"] == "Referência para cláusula que não existe"), None)
    checar(ref and ref["bloco"] == "b0a0019", "“cláusula 9” num contrato de seis", ref)

    bs = bancada.documento("locacao")
    B.reescrever(B.por_id(bs)["b0b0021"], "A INQUILINA declara receber o imóvel em perfeito estado.", "s1", 1)
    av = C.conferir(bs)
    termo = next((a for a in av if a["titulo"] == "Termo sem definição"), None)
    checar(termo and "INQUILINA" in termo["detalhe"] and "LOCATÁRIA" in termo["detalhe"], "INQUILINA sem definição", termo)

    bs = bancada.documento("procuracao")
    B.reescrever(B.por_id(bs)["b0c0008"], "VALIDADE: esta procuração é válida até [DATA].", "s1", 1)
    B.reescrever(B.por_id(bs)["b0c0003"], B.por_id(bs)["b0c0003"].texto + " CPF 111.222.333-44.", "s2", 1)
    bs.insert(1, B.bloco_novo("p", "Segue a minuta da procuração, conforme pedido.", {b.id for b in bs}))
    av = C.conferir(bs)
    checar("Falta preencher" in titulos(av) and "CPF não confere" in titulos(av) and "Conversa dentro do documento" in titulos(av),
           "lacuna, CPF que não fecha e conversa no corpo", titulos(av))


class LeisFalsas:
    def instalados(self):
        return [{"codigo": "cc", "instalado": True}, {"codigo": "inquilinato", "instalado": True}]

    def artigo(self, codigo, numero):
        if codigo == "cc" and numero == "389":
            return {"numero": "389", "revogado": False}
        if codigo == "cc" and numero == "1.233":
            return {"numero": "1.233", "revogado": True}
        if codigo == "inquilinato" and numero == "38":
            return {"numero": "38", "revogado": False}
        return None


def teste_leis() -> None:
    print("artigos de lei contra a base instalada")
    bs = bancada.documento("peticao")
    B.reescrever(B.por_id(bs)["b0d0011"], "A prova está nos autos, nos termos do art. 9.999 do Código Civil. Aplica-se também "
                 "o art. 1.233 do Código Civil.", "s1", 1)
    av = C.conferir(bs, leis=LeisFalsas())
    checar(any(a["titulo"] == "Artigo que não existe" and "9.999" in a["detalhe"] for a in av), "art. 9.999 do CC não existe", av)
    checar(any(a["titulo"] == "Artigo revogado" and "1.233" in a["detalhe"] for a in av), "art. 1.233 revogado", av)
    checar(not any("389" in a["detalhe"] for a in av), "o art. 389, que existe, não é apontado")


def teste_no_agente() -> None:
    print("o agente diz o problema que criou")
    resposta = json.dumps({"operacoes": [{"op": "substituir", "bloco": "b0b0011", "de": "R$ 2.400,00", "para": "R$ 2.600,00"}]})

    def chamar(mensagens, *, json_mode=False, max_tokens=4000, on_token=None):
        if on_token:
            on_token(resposta)
        return resposta

    eventos = list(AG.rodar(chamar, bancada.documento("locacao"), "o aluguel é 2.600", rodada=1))
    r = next(d["rodada"] for t, d in eventos if t == "fim")
    texto = AG.resposta(r, "Locação")
    checar("Conferi:" in texto and "dois mil e quatrocentos" in texto, "a resposta avisa do extenso que ficou para trás", texto)
    checar(r.conferencia and r.conferencia[0]["bloco"] == "b0b0011", "o aviso aponta o bloco")


if __name__ == "__main__":
    teste_extenso()
    teste_corpus_limpo()
    teste_erros()
    teste_leis()
    teste_no_agente()
    print()
    if _falhas:
        print(f"{len(_falhas)} falha(s): " + "; ".join(_falhas))
        sys.exit(1)
    print("todos os testes passaram")
