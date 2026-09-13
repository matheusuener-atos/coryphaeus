"""
Servicos, Gravacoes e a transcricao local, pela API que a tela usa.

Sobe o servidor numa porta livre e conversa com ele como a pagina conversa.
O que e testado e o que a tela promete:
  - um servico e uma pasta com etapas, equipe, anotacoes, arquivos do Acervo,
    prazos do cliente e trilha - e o progresso e a conta das etapas
  - uma gravacao importada fica no disco, volta inteira pelo /audio, aceita
    marcadores e notas, e a busca acha pelo que foi dito
  - com o modelo de voz baixado, a transcricao entra na fila sozinha, termina
    em portugues, sem trecho depois do fim do audio
  - a sessao ao vivo devolve o texto aos poucos enquanto o audio entra, e a
    gravacao arquivada com a sessao ja nasce transcrita

O audio de teste e falado pelas vozes em portugues do Windows (Maria e
Daniel), gerado na hora; sem elas, ou sem o modelo de voz, as partes que
dependem disso dizem que pularam em vez de falhar. Tudo que o teste cria e
apagado no fim.

    python tests/test_gravacoes.py
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
import wave
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []
_pulos: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        if detalhe:
            print(f"         {str(detalhe)[:400]}")
        _falhas.append(descricao)


def pular(descricao: str, motivo: str) -> None:
    print(f"  pulou {descricao} ({motivo})")
    _pulos.append(descricao)


# ------------------------------------------------------------ o servidor


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _subir_servidor(porta: int):
    import uvicorn

    import api

    api.estado.porta = porta
    servidor = uvicorn.Server(uvicorn.Config(api.app, host="127.0.0.1", port=porta, log_level="error"))
    threading.Thread(target=servidor.run, daemon=True).start()
    limite = time.time() + 40
    while time.time() < limite:
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", porta)) == 0:
                return servidor
        time.sleep(0.3)
    raise RuntimeError("o servidor nao subiu")


class Cliente:
    def __init__(self, porta: int) -> None:
        self.base = f"http://127.0.0.1:{porta}"

    def pedir(self, metodo: str, caminho: str, dados=None, bruto: bytes | None = None, tempo: int = 600):
        corpo = bruto if bruto is not None else (json.dumps(dados).encode() if dados is not None else None)
        tipo = "application/octet-stream" if bruto is not None else "application/json"
        req = urllib.request.Request(self.base + caminho, data=corpo, method=metodo, headers={"Content-Type": tipo})
        try:
            with urllib.request.urlopen(req, timeout=tempo) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def enviar_audio(self, campos: dict, nome: str, conteudo: bytes):
        limite = "----paulus" + uuid.uuid4().hex
        corpo = b""
        for k, v in campos.items():
            corpo += f"--{limite}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
        corpo += (f"--{limite}\r\nContent-Disposition: form-data; name=\"arquivo\"; filename=\"{nome}\"\r\n"
                  f"Content-Type: audio/wav\r\n\r\n").encode() + conteudo + f"\r\n--{limite}--\r\n".encode()
        req = urllib.request.Request(self.base + "/api/gravacoes", data=corpo, method="POST",
                                     headers={"Content-Type": f"multipart/form-data; boundary={limite}"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def baixar(self, caminho: str) -> tuple[int, str, bytes]:
        with urllib.request.urlopen(self.base + caminho, timeout=60) as r:
            return r.status, r.headers.get("content-type", ""), r.read()


# --------------------------------------------------------- o audio de teste

FALAS = [
    ("Microsoft Maria Desktop", "Bom dia, Priscila, bom dia, João. Obrigado por aceitarem a reunião. A ideia é fechar hoje o que fazemos com o contrato de logística, que renova sozinho em outubro."),
    ("Microsoft Daniel", "Bom dia. Da nossa parte a intenção é renovar, mas com condições diferentes. Mandamos ontem por e-mail a proposta: renovação com oito por cento de desconto no valor mensal."),
    ("Microsoft Maria Desktop", "Entendi. E o que acontece com o valor em atraso de agosto? São oito mil e quinhentos reais vencidos, com multa de dez por cento na cláusula quatro."),
    ("Microsoft Daniel", "Podemos compensar no aditivo, parcelado em duas vezes, se vocês abrirem mão da multa."),
    ("Microsoft Maria Desktop", "Combinado. Eu volto até sexta com o aditivo para revisão. Vou conferir se a procuração permite renunciar à multa."),
]


def gerar_audio_falado(destino: Path) -> bool:
    """Um WAV de 16 kHz falado pelas vozes do Windows. Devolve False se nao houver voz em portugues."""
    # Virgula entre os pares: com ponto e virgula o PowerShell achata tudo
    # numa lista de textos e $f[1] vira uma letra.
    falas = ", ".join("@('%s', '%s')" % (voz, texto.replace("'", "''")) for voz, texto in FALAS)
    script = f"""
Add-Type -AssemblyName System.Speech
$vozes = (New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices() | ForEach-Object {{ $_.VoiceInfo.Name }}
if (-not ($vozes -contains 'Microsoft Maria Desktop')) {{ Write-Output 'SEM-VOZ'; exit 0 }}
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SetOutputToWaveFile('{str(destino).replace("'", "''")}', $fmt)
foreach ($f in @({falas})) {{ try {{ $s.SelectVoice([string]$f[0]) }} catch {{ }}; $s.Speak([string]$f[1]) }}
$s.SetOutputToNull(); $s.Dispose(); Write-Output 'OK'
"""
    try:
        saida = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "OK" in saida.stdout and destino.exists() and destino.stat().st_size > 20000


def wav_sintetico(destino: Path, segundos: int = 3) -> None:
    """Um tom de 440 Hz: serve para testar disco, tocador e marcadores quando nao ha voz."""
    import math
    import struct

    taxa = 16000
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taxa)
        w.writeframes(b"".join(struct.pack("<h", int(9000 * math.sin(2 * math.pi * 440 * i / taxa))) for i in range(taxa * segundos)))


# ------------------------------------------------------------- os testes


def test_servicos(c: Cliente, criados: dict) -> None:
    print("\nservicos: a pasta de trabalho")
    st, cli = c.pedir("POST", "/api/cadastros", {"id": None, "dados": {"tipo": "cliente", "nome": "Teste Servicos Cliente Ltda", "documento": "12.345.678/0001-90"}})
    checar(st == 200, "cliente de teste criado", (st, cli))
    criados["cadastros"].append(cli["id"])
    st, pes = c.pedir("POST", "/api/cadastros", {"id": None, "dados": {"tipo": "colaborador", "nome": "Teste Advogada", "observacao": "contratos"}})
    criados["cadastros"].append(pes["id"])

    st, s = c.pedir("POST", "/api/servicos", {"id": None, "dados": {"nome": "Teste — Renovação", "cadastro_id": cli["id"], "descricao": "Aviso e aditivo.", "equipe": [pes["id"]]}})
    checar(st == 200 and s["cliente_nome"].startswith("Teste Servicos"), "servico aberto com cliente", (st, s))
    sid = s["id"]
    criados["servicos"].append(sid)
    checar(s["equipe"] and s["equipe"][0]["nome"] == "Teste Advogada", "a equipe vem de Cadastros")
    checar(s["trilha"] and s["trilha"][0]["texto"] == "Serviço aberto", "a trilha comeca com a abertura")
    st, _ = c.pedir("POST", "/api/servicos", {"id": None, "dados": {"nome": "   "}})
    checar(st == 400, "servico sem nome e recusado")

    c.pedir("POST", f"/api/servicos/{sid}/etapas", {"titulo": "Ler o contrato", "quando": "2026-09-20"})
    c.pedir("POST", f"/api/servicos/{sid}/etapas", {"titulo": "Rascunhar a notificação"})
    st, e = c.pedir("POST", f"/api/servicos/{sid}/etapas/0")
    checar(st == 200 and e["etapas"][0]["feita"] and e["etapas"][0]["feita_em"], "etapa concluida com data e quem")
    st, s = c.pedir("GET", f"/api/servicos/{sid}")
    checar(s["progresso"] == 50 and s["etapas_feitas"] == 1, "o progresso e a conta das etapas", s["progresso"])
    st, a = c.pedir("POST", f"/api/servicos/{sid}/anotacoes", {"texto": "Cliente prefere 6 meses."})
    checar(st == 200 and a["anotacoes"][0]["texto"] == "Cliente prefere 6 meses.", "anotacao guardada")

    st, t = c.pedir("POST", "/api/tarefas", {"id": None, "dados": {"titulo": "Teste Servicos prazo", "prazo": "2026-09-30", "cadastro_id": cli["id"], "anotacao": ""}})
    if t.get("id"):
        criados["tarefas"].append(t["id"])
    st, s = c.pedir("GET", f"/api/servicos/{sid}")
    checar(any(p["titulo"] == "Teste Servicos prazo" for p in s["prazos"]), "o prazo do cliente aparece na pasta", s["prazos"])

    st, lista = c.pedir("GET", "/api/servicos?filtro=andamento")
    checar(any(x["id"] == sid and x["prazos_quantos"] >= 1 for x in lista["servicos"]) and lista["contagem"]["andamento"] >= 1, "a lista traz a pasta e a contagem")

    st, b = c.pedir("GET", "/api/biblioteca")
    docs = b.get("documentos") or []
    if docs:
        st, v = c.pedir("POST", f"/api/servicos/{sid}/vincular", {"sha1": docs[0]["sha1"], "nome": docs[0]["nome"]})
        checar(st == 200 and len(v["arquivos"]) == 1, "documento do Acervo ligado")
        st, v = c.pedir("DELETE", f"/api/servicos/{sid}/vinculos/{docs[0]['sha1']}")
        checar(st == 200 and len(v["arquivos"]) == 0, "documento desligado")
    else:
        pular("ligar documento do Acervo", "sem documentos no Acervo")

    st, s = c.pedir("POST", f"/api/servicos/{sid}/status", {"status": "concluido"})
    checar(st == 200 and s["status"] == "concluido" and s["concluido_em"], "concluir marca a data")
    st, lista = c.pedir("GET", "/api/servicos?filtro=concluidos")
    checar(any(x["id"] == sid for x in lista["servicos"]), "concluido aparece no filtro certo")


def test_gravacoes(c: Cliente, criados: dict, audio: bytes, falado: bool) -> int:
    print("\ngravacoes: importar, ouvir, marcar, anotar")
    st, s = c.pedir("POST", "/api/servicos", {"id": None, "dados": {"nome": "Teste Gravacoes Serviço"}})
    criados["servicos"].append(s["id"])
    st, g = c.enviar_audio({"titulo": "Teste — reunião", "tipo": "reuniao", "servico_id": str(s["id"]), "participantes": "Ana Lima, Bruno Souza",
                            "duracao_s": "3", "origem": "importada", "marcadores": "[]", "transcrever": "0"}, "teste.wav", audio)
    checar(st == 200 and g["existe"], "audio importado e guardado no disco", (st, g))
    gid = g["id"]
    criados["gravacoes"].append(gid)
    checar(g["servico_nome"] == "Teste Gravacoes Serviço" and g["participantes_lista"] == ["Ana Lima", "Bruno Souza"], "servico e participantes lidos")
    st, sv = c.pedir("GET", f"/api/servicos/{s['id']}")
    checar(any("Gravação arquivada" in e["texto"] for e in sv["trilha"]) and len(sv.get("gravacoes", [])) == 1, "a trilha do servico registra e a pasta lista a gravacao")

    st, x = c.enviar_audio({"titulo": "vazia"}, "teste.wav", b"")
    checar(st == 400, "audio vazio e recusado")
    st, x = c.enviar_audio({"titulo": "errada"}, "teste.txt", b"abc")
    checar(st == 400, "formato estranho e recusado")

    st, tipo, corpo = c.baixar(f"/api/gravacoes/{gid}/audio")
    checar(st == 200 and tipo.startswith("audio/wav") and len(corpo) == len(audio), "o audio volta inteiro com o tipo certo")

    st, m = c.pedir("POST", f"/api/gravacoes/{gid}/marcadores", {"t": 2, "texto": "proposta"})
    st, m = c.pedir("POST", f"/api/gravacoes/{gid}/marcadores", {"t": 1, "texto": "abertura"})
    checar(m["marcadores"][0]["t"] == 1 and len(m["marcadores"]) == 2, "marcadores em ordem de tempo")
    st, m = c.pedir("DELETE", f"/api/gravacoes/{gid}/marcadores/0")
    checar(st == 200 and len(m["marcadores"]) == 1, "marcador tirado")
    st, g2 = c.pedir("POST", f"/api/gravacoes/{gid}", {"notas": "Combinado 6 meses.", "tipo": "atendimento"})
    checar(st == 200 and g2["notas"] == "Combinado 6 meses." and g2["tipo"] == "atendimento", "notas e tipo atualizados")
    st, lista = c.pedir("GET", "/api/gravacoes?tipo=atendimento")
    checar(any(x["id"] == gid for x in lista["gravacoes"]) and lista["total_segundos"] >= 3, "a lista filtra por tipo e soma o tempo")
    st, lista = c.pedir("GET", "/api/gravacoes?termo=Combinado")
    checar(any(x["id"] == gid for x in lista["gravacoes"]), "a busca acha pelas notas")
    linha = next(x for x in lista["gravacoes"] if x["id"] == gid)
    checar("trechos" not in linha, "a lista nao carrega a transcricao inteira")
    return gid


def esperar_transcricao(c: Cliente, gid: int, limite: int = 300) -> dict:
    comeco = time.time()
    while time.time() - comeco < limite:
        st, g = c.pedir("GET", f"/api/gravacoes/{gid}")
        if g.get("transcricao_estado") in ("pronta", "erro"):
            return g
        time.sleep(2)
    return c.pedir("GET", f"/api/gravacoes/{gid}")[1]


def test_transcricao(c: Cliente, criados: dict, audio: bytes, segundos: int) -> None:
    print("\ntranscricao nesta maquina (fila de fundo)")
    st, voz = c.pedir("GET", "/api/voz")
    checar(st == 200 and "modelos" in voz, "/api/voz diz o que ha")
    if not voz.get("disponivel"):
        pular("transcrever pela fila", "modelo de voz nao baixado")
        return
    st, g = c.enviar_audio({"titulo": "Teste — transcrição", "tipo": "reuniao", "duracao_s": str(segundos), "origem": "importada", "marcadores": "[]", "transcrever": "1"}, "fala.wav", audio)
    criados["gravacoes"].append(g["id"])
    checar(g["transcricao_estado"] in ("fila", "transcrevendo"), "importar com o modelo baixado entra na fila sozinho", g["transcricao_estado"])
    comeco = time.time()
    g = esperar_transcricao(c, g["id"])
    checar(g["transcricao_estado"] == "pronta", f"transcricao pronta em {round(time.time() - comeco)} s", g.get("transcricao_erro"))
    texto = " ".join(t["texto"] for t in g.get("trechos", [])).lower()
    checar(len(g.get("trechos", [])) >= 5 and "aditivo" in texto and "renova" in texto, f"texto em portugues com {len(g.get('trechos', []))} trechos", texto[:200])
    checar(all(t["inicio"] < segundos for t in g["trechos"]), "nenhum trecho alem do fim do audio")
    checar(g["transcricao_modelo"] and g["transcricao_tempo"] > 0 and g["palavras"] > 40, "modelo, tempo e palavras registrados")
    st, lista = c.pedir("GET", "/api/gravacoes?termo=aditivo")
    checar(any(x["id"] == g["id"] for x in lista["gravacoes"]), "a busca acha pelo que foi dito")

    # Corrigir um nome vale para a transcricao inteira; o .docx sai com titulo, resumo e minutos.
    st, r = c.pedir("POST", f"/api/gravacoes/{g['id']}/corrigir", {"de": "aditivo", "para": "TERMO-X"})
    checar(st == 200 and r["trocados"] >= 1 and any("TERMO-X" in t["texto"] for t in r["trechos"]), "corrigir troca a palavra em todos os trechos")
    st, r = c.pedir("POST", f"/api/gravacoes/{g['id']}/corrigir", {"de": "TERMO-X", "para": "aditivo"})
    checar(st == 200 and not any("TERMO-X" in t["texto"] for t in r["trechos"]), "corrigir de volta")
    st, tipo, corpo = c.baixar(f"/api/gravacoes/{g['id']}/transcricao.docx")
    checar(st == 200 and "wordprocessingml" in tipo and corpo[:2] == b"PK", "a transcricao sai em .docx")
    st, ex = c.pedir("POST", f"/api/gravacoes/{g['id']}/exportar")
    checar(st == 200 and Path(ex["path"]).exists(), "exportar guarda o .docx para anexar")
    Path(ex["path"]).unlink(missing_ok=True)
    st, r = c.pedir("POST", f"/api/gravacoes/{g['id']}/resumo")
    checar(st in (200, 503), "pedir resumo responde (200 com o Ollama, 503 sem)", (st, r))


def test_ao_vivo(c: Cliente, criados: dict, pcm: bytes, audio: bytes, segundos: int) -> None:
    print("\ntranscricao ao vivo (audio em pedacos)")
    st, voz = c.pedir("GET", "/api/voz")
    if not voz.get("disponivel"):
        pular("sessao ao vivo", "modelo de voz nao baixado")
        return
    st, s = c.pedir("POST", "/api/voz/ao-vivo", {})
    checar(st == 200 and s.get("sessao"), "sessao aberta", (st, s))
    sid = s["sessao"]
    st, x = c.pedir("POST", "/api/voz/ao-vivo/nao-existe/audio", bruto=b"\x00\x00" * 100)
    checar(st == 404, "sessao desconhecida da 404")
    pedaco = 2 * 16000 * 2
    chegados = 0
    for i in range(0, len(pcm), pedaco):
        st, r = c.pedir("POST", f"/api/voz/ao-vivo/{sid}/audio", bruto=pcm[i:i + pedaco])
        if st != 200:
            checar(False, "pedaco aceito", (st, r))
            break
        chegados += len(r["trechos"])
    checar(chegados >= 2, f"o texto foi chegando enquanto o audio entrava ({chegados} trechos antes do fim)")
    st, fim = c.pedir("POST", f"/api/voz/ao-vivo/{sid}/fim")
    todos = fim.get("trechos", [])
    texto = " ".join(t["texto"] for t in todos).lower()
    checar(st == 200 and len(todos) >= chegados and "aditivo" in texto, f"ao fechar, {len(todos)} trechos em portugues", texto[:200])
    checar(all(todos[i]["inicio"] <= todos[i + 1]["inicio"] for i in range(len(todos) - 1)), "minutos em ordem")
    st, g = c.enviar_audio({"titulo": "Teste — ao vivo", "tipo": "reuniao", "duracao_s": str(segundos), "origem": "gravada", "marcadores": "[]", "transcrever": "1", "sessao": sid}, "gravacao.wav", audio)
    criados["gravacoes"].append(g["id"])
    checar(g["transcricao_estado"] == "pronta" and g["trechos_quantos"] == len(todos) and "ao vivo" in g["transcricao_modelo"], "arquivar com a sessao deixa a gravacao transcrita, sem passar pela fila", g)
    st, x = c.pedir("POST", f"/api/voz/ao-vivo/{sid}/fim")
    checar(st == 404, "a sessao some depois de arquivada")
    st, s2 = c.pedir("POST", "/api/voz/ao-vivo", {})
    st, x = c.pedir("DELETE", f"/api/voz/ao-vivo/{s2['sessao']}")
    checar(st == 200, "descartar uma sessao")


def test_lixeira(c: Cliente, criados: dict) -> None:
    print("\nlixeira: apagar guarda 30 dias, restaurar devolve tudo")
    st, cli = c.pedir("POST", "/api/cadastros", {"id": None, "dados": {"tipo": "cliente", "nome": "Teste Lixeira Cliente"}})
    criados["cadastros"].append(cli["id"])
    st, s = c.pedir("POST", "/api/servicos", {"id": None, "dados": {"nome": "Teste Lixeira Serviço", "cadastro_id": cli["id"]}})
    c.pedir("POST", f"/api/servicos/{s['id']}/etapas", {"titulo": "Etapa que volta"})
    st, b = c.pedir("GET", "/api/biblioteca")
    docs = b.get("documentos") or []
    if docs:
        c.pedir("POST", f"/api/servicos/{s['id']}/vincular", {"sha1": docs[0]["sha1"], "nome": docs[0]["nome"]})
    st, r = c.pedir("DELETE", f"/api/servicos/{s['id']}")
    checar(st == 200 and r.get("lixeira") and "lixeira" in r.get("aviso", ""), "apagar devolve o numero na lixeira e a frase do aviso", r)
    st, x = c.pedir("GET", f"/api/servicos/{s['id']}")
    checar(st == 404, "o servico sumiu da tela")
    st, l = c.pedir("GET", "/api/lixeira")
    entrada = next((e for e in l["itens"] if e["id"] == r["lixeira"]), None)
    checar(entrada is not None and entrada["tipo"] == "servico" and entrada["dias_restantes"] >= 29, "a lixeira lista a entrada com os dias restantes", entrada)
    st, v = c.pedir("POST", f"/api/lixeira/{r['lixeira']}/restaurar")
    checar(st == 200 and v["restaurado"] == str(s["id"]), "restaurar responde", (st, v))
    st, s2 = c.pedir("GET", f"/api/servicos/{s['id']}")
    checar(st == 200 and s2["nome"] == "Teste Lixeira Serviço" and s2["cliente_nome"] == "Teste Lixeira Cliente", "o servico voltou com o mesmo numero e o cliente")
    checar(len(s2["etapas"]) == 1 and s2["etapas"][0]["titulo"] == "Etapa que volta", "as etapas voltaram")
    if docs:
        checar(len(s2["arquivos"]) == 1, "o arquivo ligado voltou")
    criados["servicos"].append(s["id"])
    st, x = c.pedir("POST", f"/api/lixeira/{r['lixeira']}/restaurar")
    checar(st == 409, "restaurar duas vezes nao duplica")

    # A ficha do cliente: as ligacoes por cadastro_id voltam junto.
    st, r2 = c.pedir("DELETE", f"/api/cadastros/{cli['id']}")
    st, s3 = c.pedir("GET", f"/api/servicos/{s['id']}")
    checar(s3["cadastro_id"] is None, "apagar a ficha desliga o servico")
    st, v2 = c.pedir("POST", f"/api/lixeira/{r2['lixeira']}/restaurar")
    st, s4 = c.pedir("GET", f"/api/servicos/{s['id']}")
    checar(st == 200 and s4["cadastro_id"] == cli["id"], "restaurar a ficha religa o servico")

    # Uma gravacao leva o audio junto e traz de volta.
    st, g = c.enviar_audio({"titulo": "Teste Lixeira gravação", "tipo": "nota", "duracao_s": "1", "origem": "importada", "marcadores": "[]", "transcrever": "0"}, "lixo.wav", criados["audio"])
    st, r3 = c.pedir("DELETE", f"/api/gravacoes/{g['id']}")
    pasta = Path(RAIZ / "data" / "gravacoes" / g["arquivo"])
    checar(not pasta.exists(), "o audio saiu de data/gravacoes")
    st, v3 = c.pedir("POST", f"/api/lixeira/{r3['lixeira']}/restaurar")
    st, g2 = c.pedir("GET", f"/api/gravacoes/{g['id']}")
    checar(st == 200 and g2["existe"] and pasta.exists(), "restaurar traz o audio de volta")
    criados["gravacoes"].append(g["id"])
    st, r4 = c.pedir("DELETE", f"/api/gravacoes/{g['id']}")
    st, x = c.pedir("DELETE", f"/api/lixeira/{r4['lixeira']}")
    checar(st == 200 and not pasta.exists(), "apagar de vez tira a entrada e o arquivo")
    criados["gravacoes"].remove(g["id"])


def main() -> int:
    print("=" * 55)
    print("  PAULUS - servicos, gravacoes e transcricao")
    print("=" * 55)
    porta = _porta_livre()
    servidor = _subir_servidor(porta)
    c = Cliente(porta)
    criados: dict = {"gravacoes": [], "servicos": [], "cadastros": [], "tarefas": [], "audio": b""}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "fala.wav"
            falado = gerar_audio_falado(caminho)
            if not falado:
                wav_sintetico(caminho)
                pular("audio falado pelas vozes do Windows", "sem a voz Microsoft Maria; usando um tom")
            audio = caminho.read_bytes()
            criados["audio"] = audio
            with wave.open(str(caminho), "rb") as w:
                pcm = w.readframes(w.getnframes())
                segundos = max(1, round(w.getnframes() / w.getframerate()))

            test_servicos(c, criados)
            test_gravacoes(c, criados, audio, falado)
            if falado:
                test_transcricao(c, criados, audio, segundos)
                test_ao_vivo(c, criados, pcm, audio, segundos)
            else:
                pular("transcricao e ao vivo", "sem audio falado")
            test_lixeira(c, criados)
    finally:
        # Apagar manda para a lixeira; o teste tira de la tambem, para nao
        # deixar entrada de teste no meio das de verdade.
        def apagar_de_vez(caminho: str) -> None:
            st, r = c.pedir("DELETE", caminho)
            if isinstance(r, dict) and r.get("lixeira"):
                c.pedir("DELETE", f"/api/lixeira/{r['lixeira']}")

        for gid in criados["gravacoes"]:
            apagar_de_vez(f"/api/gravacoes/{gid}")
        for sid in criados["servicos"]:
            apagar_de_vez(f"/api/servicos/{sid}")
        for tid in criados["tarefas"]:
            apagar_de_vez(f"/api/tarefas/{tid}")
        for cid in criados["cadastros"]:
            apagar_de_vez(f"/api/cadastros/{cid}")
        st, sobra = c.pedir("GET", "/api/gravacoes?termo=Teste%20%E2%80%94")
        sobrou = [x["titulo"] for x in sobra.get("gravacoes", [])]
        checar(not sobrou, "nada de teste sobrou no disco", sobrou)
        servidor.should_exit = True

    print("\n" + "=" * 55)
    if _pulos:
        print(f"  {len(_pulos)} pulou: " + "; ".join(_pulos))
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
