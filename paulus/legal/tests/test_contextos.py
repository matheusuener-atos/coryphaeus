"""
O que o escritorio ensinou ao assistente com as proprias palavras.

Sao poucas linhas que entram em TODA pergunta - por isso o que se testa aqui
e o caminho inteiro: o lembrete e guardado, aparece na instrucao que vai ao
modelo, respeita o limite de tamanho (a janela do modelo desta maquina ja e
disputada pelos trechos dos documentos) e, ao ser apagado, passa pela lixeira
como todo o resto.

Rodar: venv\\Scripts\\python.exe tests\\test_contextos.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import base as base_mod  # noqa: E402
import contextos as contextos_mod  # noqa: E402
import lixeira as lixeira_mod  # noqa: E402

_falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {str(detalhe)[:300]}")
        _falhas.append(descricao)


def test_guardar_e_ensinar() -> None:
    print("\nguardar o que o escritorio ensina")
    with tempfile.TemporaryDirectory() as tmp:
        bd = base_mod.Base(Path(tmp) / "teste.db")
        bd.migrar()
        c = contextos_mod.Contextos(bd)

        checar(c.bloco() == "", "sem lembrete nenhum, nada entra na pergunta")

        id_ = c.salvar({"titulo": "Prazo de aviso", "gaveta": "Regras de redação",
                        "texto": "Nos contratos deste escritório o aviso de não renovação é de 90 dias."})
        item = c.obter(id_)
        checar(item and item["titulo"] == "Prazo de aviso" and item["gaveta"] == "Regras de redação",
               "o lembrete fica guardado com a gaveta", item)

        bloco = c.bloco()
        checar("90 dias" in bloco and "Prazo de aviso" in bloco, "e entra na instrucao do assistente", bloco)
        checar(bloco.startswith("O escritório me ensinou"), "com uma linha dizendo o que aquilo e", bloco[:40])

        c.salvar({"titulo": "Como chamar a cliente", "gaveta": "Clientes",
                  "texto": "Escreva Cooperativa Brasileira por extenso, nunca COOBRAMEX."})
        so_redacao = c.bloco(["Regras de redação"])
        checar("90 dias" in so_redacao and "COOBRAMEX" not in so_redacao,
               "no editor entram so as regras de redacao", so_redacao)

        # O mais novo primeiro: quem acabou de ensinar espera que ja valha.
        checar(c.listar()[0]["titulo"] == "Como chamar a cliente", "o mais novo aparece em cima")

        c.salvar({"titulo": "Prazo de aviso", "gaveta": "Regras de redação",
                  "texto": "São 120 dias, mudou na revisão de 2026."}, id_)
        checar("120 dias" in c.bloco() and "90 dias" not in c.bloco(), "alterar troca o que o assistente sabe")

        for dados, pedaco in (({"titulo": "  ", "texto": "algo"}, "título"),
                              ({"titulo": "Algo", "texto": "   "}, "eu devo saber")):
            try:
                c.salvar(dados)
                checar(False, f"recusa o lembrete pela metade ({pedaco})")
            except ValueError as exc:
                checar(pedaco in str(exc), f"recusa dizendo o que falta: {exc}")

        longo = c.salvar({"titulo": "T" * 200, "texto": "x" * 900})
        guardado = c.obter(longo)
        checar(len(guardado["titulo"]) == contextos_mod.MAX_TITULO and len(guardado["texto"]) == contextos_mod.MAX_TEXTO,
               "titulo e texto sao cortados no limite de cada um",
               (len(guardado["titulo"]), len(guardado["texto"])))
        checar(c.obter(longo)["gaveta"] == contextos_mod.GAVETA_PADRAO,
               "gaveta que nao existe vira a padrao, nao um erro")
        bd.fechar()


def test_limite_da_janela() -> None:
    """O que nao cabe fica de fora, e a tela sabe dizer quais."""
    print("\no limite por pergunta")
    with tempfile.TemporaryDirectory() as tmp:
        bd = base_mod.Base(Path(tmp) / "teste.db")
        bd.migrar()
        c = contextos_mod.Contextos(bd)

        for i in range(12):
            c.salvar({"titulo": f"Regra {i}", "texto": "x" * contextos_mod.MAX_TEXTO})

        bloco = c.bloco()
        checar(len(bloco) <= contextos_mod.LIMITE_BLOCO + 80,
               f"o bloco inteiro respeita o limite ({len(bloco)} de {contextos_mod.LIMITE_BLOCO})")
        tela = c.para_tela()
        checar(tela["de_fora"] > 0 and tela["de_fora"] == len([x for x in tela["contextos"] if not x["entra"]]),
               "a tela diz quantos ficaram de fora", tela["de_fora"])
        checar(tela["contextos"][0]["entra"], "e os mais novos sao os que entram")
        bd.fechar()


def test_chega_no_modelo() -> None:
    """A instrucao que sai daqui e a que o modelo recebe, e no lugar certo."""
    print("\na instrucao que vai ao modelo")
    import llama_client

    cliente = llama_client.LlamaClient(model="teste")
    capturado: dict = {}

    def falso_chat(messages, **kwargs):
        capturado["messages"] = messages
        return "resposta"

    cliente._chat = falso_chat
    cliente.ask("Qual o prazo?", "Trecho do contrato", ensinado="O escritório me ensinou:\n- Prazo: 90 dias.")
    sistema = capturado["messages"][0]
    usuario = capturado["messages"][1]
    checar(sistema["role"] == "system" and "90 dias" in sistema["content"],
           "o que o escritorio ensinou entra na instrucao de sistema")
    checar(llama_client.SYSTEM_PROMPT.split("\n")[0] in sistema["content"],
           "sem apagar a instrucao que ja existia")
    checar("90 dias" not in usuario["content"],
           "e nao na pergunta: e regra da casa, nao parte do que foi perguntado agora")

    capturado.clear()
    cliente.ask("Qual o prazo?", "Trecho")
    checar("me ensinou" not in capturado["messages"][0]["content"],
           "sem lembrete nenhum, a instrucao fica como era")


def test_lixeira() -> None:
    """Apagar um lembrete guarda por 30 dias, como todo o resto."""
    print("\napagar passa pela lixeira")
    with tempfile.TemporaryDirectory() as tmp:
        bd = base_mod.Base(Path(tmp) / "teste.db")
        bd.migrar()
        c = contextos_mod.Contextos(bd)
        lixo = lixeira_mod.Lixeira(bd, Path(tmp) / "lixeira")

        id_ = c.salvar({"titulo": "Modelo de notificação", "gaveta": "Modelos",
                        "texto": "Começa com a qualificação e termina com o prazo de resposta."})
        entrada = lixo.apagar_linha("contexto", id_, "Modelo de notificação", "Modelos")
        checar(entrada and c.obter(id_) is None, "sai da lista na hora", entrada)
        checar(entrada["tipo_rotulo"] == "Lembrete do assistente", "e o aviso diz o que era", entrada.get("tipo_rotulo"))
        checar(c.bloco() == "", "e para de entrar nas perguntas")

        lixo.restaurar(entrada["id"])
        voltou = c.obter(id_)
        checar(voltou and voltou["titulo"] == "Modelo de notificação", "Desfazer devolve o lembrete inteiro", voltou)
        checar("prazo de resposta" in c.bloco(), "e ele volta a valer na proxima pergunta")
        bd.fechar()


def main() -> int:
    print("=" * 55)
    print("  PAULUS - o que o escritorio ensina ao assistente")
    print("=" * 55)
    test_guardar_e_ensinar()
    test_limite_da_janela()
    test_chega_no_modelo()
    test_lixeira()

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
