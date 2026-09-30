"""
Modelo de voz pesado demais para a memória livre: o PAULUS sugere o mais leve.

  - sem memória para o Whisper turbo, carregar dá o erro de sempre (em vez de
    derrubar o programa) e ele diz qual modelo é mais leve;
  - o erro que o CTranslate2 dá no meio (MemoryError, "failed to allocate")
    vira o mesmo erro, com a mesma sugestão;
  - com o modelo mais leve já em uso, não há o que sugerir;
  - a gravação que falhou por memória diz isso à tela, e a situação da voz diz
    qual é o mais leve e se ele já está baixado;
  - a troca pela tela é a de sempre (/api/voz/modelo), e a próxima
    transcrição usa o modelo novo.

Não carrega modelo de voz de verdade: a memória e o faster-whisper são
simulados.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_voz_mais_leve.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import types
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import transcricao  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def _com_modelos(pasta: Path, *nomes: str) -> None:
    for n in nomes:
        (pasta / n).mkdir(parents=True, exist_ok=True)
        for a in transcricao.ARQUIVOS_DO_MODELO:
            (pasta / n / a).write_text("x", encoding="utf-8")


class _Memoria:
    """psutil.virtual_memory() com a memória livre que o teste quiser."""

    def __init__(self, livre_mb: float) -> None:
        self.livre_mb = livre_mb

    def __call__(self):
        return types.SimpleNamespace(available=self.livre_mb * 1024 * 1024)


def _whisper_falso(erro: BaseException | None = None, erro_ao_transcrever: BaseException | None = None):
    class Modelo:
        def __init__(self, *a, **k) -> None:
            if erro is not None:
                raise erro

        def transcribe(self, *a, **k):
            if erro_ao_transcrever is not None:
                raise erro_ao_transcrever
            return iter([]), types.SimpleNamespace(duration=1.0, language="pt")

    return types.SimpleNamespace(WhisperModel=Modelo)


def test_carregar(pasta: Path) -> None:
    print("\nsem memória para o modelo escolhido")
    import psutil

    _com_modelos(pasta, "turbo", "small")
    antes = psutil.virtual_memory
    try:
        psutil.virtual_memory = _Memoria(1000)
        t = transcricao.Transcritor(pasta, "turbo")
        try:
            t.carregar()
            checar(False, "turbo com 1 GB livre não carrega")
        except transcricao.SemMemoria as exc:
            checar(exc.mais_leve == "small", "o erro diz qual é o mais leve", exc.mais_leve)
            checar("Whisper small" in str(exc) and "1,0 GB livres" in str(exc),
                   "a frase diz a memória livre e o nome do mais leve", str(exc))
            checar(transcricao.falta_de_memoria(str(exc)), "a frase guardada ainda se reconhece como falta de memória")
        t.escolher("small")
        psutil.virtual_memory = _Memoria(300)
        try:
            t.carregar()
            checar(False, "small com 0,3 GB livre não carrega")
        except transcricao.SemMemoria as exc:
            checar(exc.mais_leve == "", "com o mais leve em uso, não há o que sugerir", exc.mais_leve)
            checar("Whisper small" not in str(exc).split("GB).")[-1], "e a frase não sugere trocar por ele mesmo", str(exc))
        checar(not transcricao.falta_de_memoria("o áudio não está mais no disco"), "outro erro não vira falta de memória")
    finally:
        psutil.virtual_memory = antes


def test_no_meio(pasta: Path) -> None:
    print("\no erro de memória que vem de dentro do modelo")
    import psutil

    _com_modelos(pasta, "turbo")
    antes_mem, antes_fw = psutil.virtual_memory, sys.modules.get("faster_whisper")
    try:
        psutil.virtual_memory = _Memoria(8000)
        for erro, nome in ((MemoryError(), "MemoryError ao carregar"),
                           (RuntimeError("mkl_malloc: failed to allocate memory"), "“failed to allocate” ao carregar")):
            sys.modules["faster_whisper"] = _whisper_falso(erro=erro)
            t = transcricao.Transcritor(pasta, "turbo")
            try:
                t.carregar()
                checar(False, nome + " vira falta de memória")
            except transcricao.SemMemoria as exc:
                checar(exc.mais_leve == "small", nome + " vira falta de memória, com a sugestão", str(exc))
        sys.modules["faster_whisper"] = _whisper_falso(
            erro_ao_transcrever=RuntimeError("CUDA failed... no: std::bad_alloc"))
        t = transcricao.Transcritor(pasta, "turbo")
        audio = pasta / "a.wav"
        audio.write_bytes(b"RIFF")
        try:
            t.transcrever(audio)
            checar(False, "bad_alloc ao transcrever vira falta de memória")
        except transcricao.SemMemoria as exc:
            checar(exc.mais_leve == "small", "bad_alloc ao transcrever vira falta de memória, com a sugestão")
        sys.modules["faster_whisper"] = _whisper_falso(erro_ao_transcrever=ValueError("áudio corrompido"))
        t = transcricao.Transcritor(pasta, "turbo")
        try:
            t.transcrever(audio)
        except transcricao.SemMemoria:
            checar(False, "outro erro ao transcrever continua sendo o erro dele")
        except ValueError:
            checar(True, "outro erro ao transcrever continua sendo o erro dele")
    finally:
        psutil.virtual_memory = antes_mem
        if antes_fw is not None:
            sys.modules["faster_whisper"] = antes_fw
        else:
            sys.modules.pop("faster_whisper", None)


def test_situacao(pasta: Path) -> None:
    print("\no que a tela recebe")
    _com_modelos(pasta, "turbo")
    t = transcricao.Transcritor(pasta, "turbo")
    s = t.situacao()
    checar(s["mais_leve"] == {"nome": "small", "rotulo": "Whisper small", "instalado": False, "mb": 480},
           "a situação diz qual é o mais leve e que ele ainda não está baixado", s.get("mais_leve"))
    _com_modelos(pasta, "small")
    checar(t.situacao()["mais_leve"]["instalado"], "e quando ele já está baixado")
    t.escolher("small")
    checar(t.situacao()["mais_leve"] is None, "com o mais leve em uso, nada a sugerir")


def test_gravacao() -> None:
    print("\na gravação que falhou por falta de memória")
    from fastapi.testclient import TestClient

    import api

    c = TestClient(api.app, headers=api.cabecalho_local())
    gid = int(api.estado.gravacoes.guardar({"titulo": "Teste — voz pesada", "tipo": "nota"}, b"RIFF0000WAVE", "t.wav"))
    try:
        erro = transcricao.SemMemoria("turbo", 900, 1920, "small")
        api.estado.gravacoes.marcar_transcricao(gid, "erro", erro=str(erro))
        r = c.get(f"/api/gravacoes/{gid}").json()
        checar(r.get("transcricao_sem_memoria") is True, "a gravação diz que faltou memória", r.get("transcricao_erro"))
        api.estado.gravacoes.marcar_transcricao(gid, "erro", erro="o áudio não está mais no disco")
        r = c.get(f"/api/gravacoes/{gid}").json()
        checar(r.get("transcricao_sem_memoria") is False, "outro erro, não")
        v = c.get("/api/voz").json()
        checar("mais_leve" in v, "a situação da voz leva o mais leve para a tela")
        # Ao vivo: a frase chega inteira, para a tela reconhecê-la e oferecer a troca.
        t = api.estado.transcritor
        antes = (t.instalado, t.ao_vivo_receber)

        def sem_memoria(*a, **k):
            raise transcricao.SemMemoria("turbo", 900, 1920, "small")

        t.instalado, t.ao_vivo_receber = (lambda nome=None: True), sem_memoria
        try:
            sid = c.post("/api/voz/ao-vivo", json={}).json()["sessao"]
            r = c.post(f"/api/voz/ao-vivo/{sid}/audio", content=b"\x00\x01" * 800,
                       headers={"Content-Type": "application/octet-stream"})
            checar(r.status_code == 503 and transcricao.falta_de_memoria(r.json()["detail"]),
                   "ao vivo, a falta de memória chega com a frase que a tela reconhece", (r.status_code, r.text[:120]))
            c.delete(f"/api/voz/ao-vivo/{sid}")
        finally:
            t.instalado, t.ao_vivo_receber = antes
    finally:
        r = c.delete(f"/api/gravacoes/{gid}")
        lixo = (r.json() or {}).get("lixeira") if r.status_code == 200 else None
        if lixo:
            c.delete(f"/api/lixeira/{lixo}")


def main() -> int:
    print("=" * 55)
    print("  Modelo de voz pesado: sugerir o mais leve")
    print("=" * 55)
    pastas = [Path(tempfile.mkdtemp(prefix=f"paulus-voz-{i}-")) for i in range(3)]
    try:
        test_carregar(pastas[0])
        test_no_meio(pastas[1])
        test_situacao(pastas[2])
        test_gravacao()
    finally:
        for p in pastas:
            shutil.rmtree(p, ignore_errors=True)
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
