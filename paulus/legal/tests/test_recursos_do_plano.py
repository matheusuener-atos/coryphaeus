"""
Os recursos de cada plano (src/recursos_do_plano.py, 03/10/2026).

  - sem a cobrança (terminal, testes), tudo liberado;
  - no Advogado: profundidade até Advogado, 1 pessoa, 3 agentes, 1 conta de
    e-mail, e sem NFS-e, DataJud, gravação, horas, muralha, agente sozinho,
    jurisprudência em massa, Word e MCP - cada recusa diz o plano que tem;
  - no Escritório: até Juiz, 5 pessoas, NFS-e até 20 por mês (só a de
    produção conta), sem as sugestões ao vivo, o Word e o MCP;
  - no Plus, tudo;
  - sem internet, vale o plano guardado;
  - a pergunta à nuvem leva o nível, e o modelo que respondeu volta do Worker.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_recursos_do_plano.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-recursos-plano-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
os.environ["PAULUS_NFSE_SEM_FILA"] = "1"
os.environ.pop("PAULUS_COBRANCA", None)
os.environ.pop("PAULUS_INSTALADO", None)
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


# Os recursos de fábrica do Worker (worker/ia.js, PLANOS_DE_FABRICA).
ESCRITORIO = {"profundidade": "juiz", "agentes": None, "equipe": True, "emails": None, "consumo_por_pessoa": True,
              "nfse_mes": 20, "nfse_recorrente": False, "datajud": True, "gravacao": True, "ao_vivo": False, "horas": True,
              "muralha": True, "autonomia": True, "jurisprudencia_stj": True, "word": False, "mcp": False, "pagina_cliente": False}
ADVOGADO = {**ESCRITORIO, "profundidade": "advogado", "agentes": 3, "equipe": False, "emails": 1, "consumo_por_pessoa": False,
            "nfse_mes": 0, "datajud": False, "gravacao": False, "horas": False, "muralha": False, "autonomia": False,
            "jurisprudencia_stj": False}
PLUS = {**ESCRITORIO, "profundidade": "ministro", "nfse_mes": None, "nfse_recorrente": True, "ao_vivo": True, "word": True,
        "mcp": True, "pagina_cliente": True}
PLANOS = [{"id": "advogado", "nome": "Advogado", "pessoas": 1, "recursos": ADVOGADO},
          {"id": "escritorio", "nome": "Escritório", "pessoas": 5, "recursos": ESCRITORIO},
          {"id": "plus", "nome": "Escritório Plus", "pessoas": 15, "recursos": PLUS}]


def conta_no(plano_id: str) -> dict:
    p = next(x for x in PLANOS if x["id"] == plano_id)
    fim = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()
    return {"plano_vigente": True, "ciclo": {"fim": fim}, "plano": p, "planos": PLANOS}


def test_tudo() -> None:
    import api
    import nuvem
    import plano
    import recursos_do_plano as rp
    from fastapi.testclient import TestClient

    e = api.estado
    c = TestClient(api.app, headers=api.cabecalho_local())

    print("\nsem a cobrança")
    plano.esquecer()
    checar(rp.do_plano(e) is None and rp.pode(e, "word") and rp.nivel_max(e) == "ministro", "fora do instalado: tudo liberado")

    os.environ["PAULUS_COBRANCA"] = "1"
    original = nuvem.conta_paulus
    try:
        # ------------------------------------------------ Advogado
        print("\nno Advogado")
        nuvem.conta_paulus = lambda estado, forcar=False: conta_no("advogado")
        plano.esquecer()
        checar(plano.liberada(e) and e.prefs.dados["plano"]["id"] == "advogado" and e.prefs.dados["plano"]["recursos"]["agentes"] == 3,
               "o plano e os recursos ficam guardados", e.prefs.dados["plano"])
        niveis = {n["id"]: n for n in c.get("/api/nuvem/situacao").json()["profundidade"]["niveis"]}
        checar(not niveis["advogado"].get("bloqueado") and niveis["juiz"]["bloqueado"] and "Escritório" in niveis["juiz"]["no_plano"]
               and niveis["ministro"]["no_plano"].endswith("do plano Escritório Plus."),
               "a profundidade acima de Advogado vem travada, com o plano que a tem", niveis["ministro"])
        import profundidade

        checar(profundidade.limitar(profundidade.NIVEIS["ministro"], rp.nivel_max(e)).id == "advogado", "o nível pedido acima do plano desce ao máximo")

        r = c.post("/api/word/ligar", json={"ligado": True})
        checar(r.status_code == 403 and r.json()["motivo"] == "plano" and "Escritório Plus" in r.json()["detail"],
               "o Word não liga: 403 com o plano que tem", r.json())
        r = c.post("/api/chaves", json={"bloco": "processos", "chave": "acompanhar", "ligada": True})
        checar(r.status_code == 403 and "DataJud" in r.json()["detail"] and "Escritório e Escritório Plus" in r.json()["detail"],
               "o DataJud não liga", r.json())
        checar(c.post("/api/chaves", json={"bloco": "processos", "chave": "acompanhar", "ligada": False}).status_code == 200,
               "desligar nunca é barrado")
        e.prefs.atualizar({"processos": {"acompanhar": True}})
        import processos

        checar(not processos.ligado(e), "ligado antes, num plano sem DataJud: não consulta")
        e.prefs.atualizar({"processos": {"acompanhar": False}})
        checar(c.post("/api/chaves", json={"bloco": "umbrel", "chave": "mcp", "ligada": True}).status_code == 403, "o MCP não liga")
        checar(c.post("/api/gravacoes/1/transcrever").status_code == 403, "gravação: 403 antes de procurar a gravação")
        checar(c.post("/api/gravacoes/sugerir", json={"texto": "a multa"}).status_code == 403, "sugestões ao vivo: 403")
        checar(c.post("/api/servicos/1/horas", json={"duracao": "1h"}).status_code == 403, "horas: 403")
        r = c.get("/api/conflitos")
        checar(r.status_code == 200 and r.json()["conflitos"] == [] and "muralha" in r.json()["no_plano"], "a lista da muralha vem vazia, com a frase", r.json())
        checar(c.post("/api/jurisprudencia/baixar", json={"orgaos": ["corte-especial"]}).status_code == 403, "a jurisprudência em massa: 403")
        checar(c.post("/api/nfse/ligar", json={"ligado": True}).status_code == 403, "a NFS-e não liga no Advogado")
        checar(c.post("/api/passos", json={"tipo": "x", "params": {}}).status_code == 403, "tarefas de vários passos: 403")
        import agente_na_conversa

        class Ag:
            slug = "a"
            autonomia = ["criar_tarefa"]
            precisa_aprovar = False

        e.prefs.dados.setdefault("autonomia", {})["agentes_sozinhos"] = True
        checar(agente_na_conversa.pode_sozinho(e, Ag(), "criar_tarefa") == (False, ""), "o agente não faz sozinho: vira o cartão de sempre")

        # Agentes: 3 do escritório (os de exemplo do produto não contam).
        class A:
            def __init__(self, origem):
                self.origem = origem

        listar = e.agentes.listar
        e.prefs.atualizar({"conversa": {"agentes": True}})
        try:
            e.agentes.listar = lambda: [A("escritorio"), A("importado"), A("produto"), A("escritorio")]
            r = c.post("/api/agentes", json={"markdown": "---\nnome: x\n---\n"})
            checar(r.status_code == 403 and "até 3 agentes" in r.json()["detail"] and "Escritório" in r.json()["detail"],
                   "o quarto agente do escritório não entra", r.json())
            e.agentes.listar = lambda: [A("escritorio"), A("produto"), A("produto")]
            checar(c.post("/api/agentes", json={"markdown": "---\nnome: x\n---\n"}).status_code != 403, "com 1 do escritório (e 2 de exemplo), cabe")
        finally:
            e.agentes.listar = listar

        # Pessoas e e-mails.
        try:
            e.acesso_de_fora.contas.vaga(1)
            checar(False, "o Advogado não tem equipe")
        except rp.SemRecurso as exc:
            checar("equipe" in str(exc), "o Advogado não tem equipe: a segunda conta não nasce", str(exc))
        checar("equipe" in rp.colaborador_barrado(e), "e o colaborador que já existia não entra de fora")
        e.contas.vaga(0)
        try:
            e.contas.vaga(1)
            checar(False, "a segunda conta de e-mail")
        except rp.SemRecurso as exc:
            checar("até 1 conta de e-mail" in str(exc), "a segunda conta de e-mail não entra", str(exc))
        r = c.post("/api/consumo/limites", json={"diario": 0, "mensal": 0, "pessoas": {"2": {"diario": "1.000", "mensal": ""}}})
        checar(r.status_code == 403, "o limite por pessoa é do plano com equipe")
        checar(c.post("/api/consumo/limites", json={"diario": 1000, "mensal": 0, "pessoas": {}}).status_code == 200, "o do escritório é de todos")

        # ------------------------------------------------ Escritório
        print("\nno Escritório")
        nuvem.conta_paulus = lambda estado, forcar=False: conta_no("escritorio")
        plano.esquecer()
        niveis = {n["id"]: n for n in c.get("/api/nuvem/situacao").json()["profundidade"]["niveis"]}
        checar(not niveis["juiz"].get("bloqueado") and niveis["ministro"]["bloqueado"], "até Juiz; o Ministro travado")
        e.acesso_de_fora.contas.vaga(4)
        try:
            e.acesso_de_fora.contas.vaga(5)
            checar(False, "a sexta pessoa")
        except rp.SemRecurso as exc:
            checar("até 5 pessoas" in str(exc) and "Escritório Plus" in str(exc), "a sexta pessoa não entra; o Plus tem mais", str(exc))
        checar(rp.colaborador_barrado(e) == "", "o colaborador entra de fora")
        e.contas.vaga(7)
        checar(c.post("/api/word/ligar", json={"ligado": True}).status_code == 403, "o Word é do Plus")
        checar(c.post("/api/gravacoes/sugerir", json={"texto": "a multa"}).status_code == 403, "as sugestões ao vivo são do Plus")
        checar(c.post("/api/gravacoes/1/transcrever").status_code == 404, "a gravação é do Escritório (a gravação 1 não existe: 404)")

        # A NFS-e do mês: 20 em produção; a da produção restrita não conta.
        import rotas_nfse

        mes = date.today().isoformat()[:7]
        listar_notas = e.nfse.notas.listar
        try:
            e.nfse.notas.listar = lambda estados=None, mes_="", limite=300, **k: (
                [{"ambiente": "producao", "dh_proc": mes + "-02T10:00:00"}] * 19 + [{"ambiente": "producao_restrita", "dh_proc": mes + "-02"}] * 5)
            rotas_nfse._cota_do_mes(e, {"ambiente": "producao"})
            checar(True, "19 emitidas em produção (e 5 de teste): a 20ª sai")
            e.nfse.notas.listar = lambda estados=None, mes_="", limite=300, **k: [{"ambiente": "producao", "dh_proc": mes + "-02"}] * 20
            try:
                rotas_nfse._cota_do_mes(e, {"ambiente": "producao"})
                checar(False, "a 21ª nota")
            except rp.SemRecurso as exc:
                checar("até 20 NFS-e por mês" in str(exc), "a 21ª do mês não sai", str(exc))
            rotas_nfse._cota_do_mes(e, {"ambiente": "producao_restrita"})
            checar(True, "a de teste (produção restrita) sai sempre")
        finally:
            e.nfse.notas.listar = listar_notas
        checar(c.post("/api/nfse/recorrencias", json={}).status_code == 403, "a NFS-e recorrente é do Plus")

        # ------------------------------------------------ Plus
        print("\nno Plus")
        nuvem.conta_paulus = lambda estado, forcar=False: conta_no("plus")
        plano.esquecer()
        checar(rp.nivel_max(e) == "ministro" and rp.pode(e, "word") and rp.limite(e, "nfse_mes") is None, "tudo, e NFS-e sem limite")
        e.acesso_de_fora.contas.vaga(14)
        rotas_nfse._cota_do_mes(e, {"ambiente": "producao"})
        checar(True, "15 pessoas e NFS-e sem teto")

        # ------------------------------------------------ sem internet
        print("\nsem internet")

        def caiu(estado, forcar=False):
            raise RuntimeError("sem internet")

        nuvem.conta_paulus = caiu
        plano.esquecer()
        checar(rp.pode(e, "word") and rp.nivel_max(e) == "ministro", "vale o plano guardado (o Plus)")

        # ------------------------------------------------ o nível vai à nuvem
        print("\na pergunta leva o nível")
        pedidos = []

        class Resposta:
            status_code = 200
            headers = {"x-paulus-modelo": "claude-opus-5-5"}

            def iter_lines(self, decode_unicode=True):
                yield 'data: {"choices":[{"delta":{"content":"ok"}}]}'
                yield 'data: {"choices":[],"usage":{"prompt_tokens":10,"completion_tokens":2}}'
                yield "data: [DONE]"

            def close(self):
                pass

        nuvem.PEDIR["fn"] = lambda m, url, cab, corpo, stream: (pedidos.append(corpo), Resposta())[1]
        try:
            uso = nuvem.chamar("paulus", "meta-llama/Llama-3.3-70B-Instruct", "pia_x", [{"role": "user", "content": "oi"}],
                               lambda t: None, nivel="ministro")
        finally:
            nuvem.PEDIR["fn"] = None
        checar(pedidos[0]["paulus_nivel"] == "ministro" and uso["modelo"] == "claude-opus-5-5",
               "o nível vai no pedido; o modelo que respondeu volta do Worker", (pedidos[0], uso))
    finally:
        nuvem.conta_paulus = original
        os.environ.pop("PAULUS_COBRANCA", None)
        plano.esquecer()


def main() -> int:
    print("=" * 55)
    print("  Os recursos de cada plano")
    print("=" * 55)
    try:
        test_tudo()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
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
