"""
Instalar o suplemento no Word deste computador (W1, montagem A).

O que a W0 mediu e decidiu (docs/PROGRESSO-WORD.md):

- o painel vem de https://localhost:<porta fixa>: a porta é escolhida uma vez
  e guardada, porque o manifesto leva o endereço;
- o certificado é de uma autoridade desta instalação **restrita a localhost e
  127.0.0.1** (name constraints), cuja chave é descartada logo depois de
  emitir o do servidor: copiada, a pasta não emite certificado para outro
  nome. Ele entra em CurrentUser\\Root sem administrador; o Windows pergunta,
  e a pessoa clica em Sim;
- confiado ou não, **quem diz é o repositório lido depois**, nunca o retorno
  do comando: na W0 o Import-Certificate respondeu erro com o certificado
  instalado;
- o Word acha o suplemento pelo registro de desenvolvedor do usuário
  (HKCU\\...\\WEF\\Developer), sem administrador; o catálogo em pasta
  compartilhada fica como segunda via, com o passo a passo na tela;
- "instalado" só depois que o painel abriu num Word e avisou (POST
  /api/word/carregou).
"""

from __future__ import annotations

import ipaddress
import json
import socket
import ssl
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from string import Template
from xml.sax.saxutils import escape

MODELO_DO_MANIFESTO = Path(__file__).resolve().parent.parent / "word" / "manifesto.xml"
FAIXA_DE_PORTAS = range(46300, 46400)
DIAS_DO_CERTIFICADO = 825
RENOVAR_COM_DIAS = 30
CHAVE_DO_REGISTRO = r"Software\Microsoft\Office\16.0\WEF\Developer"
ESPACO_DOS_IDS = uuid.UUID("2f0c9e57-1d0b-4c43-9f0e-5e6b1a7f4d21")
NOME_NO_WORD = "PAVLVS"


class FalhaNaInstalacao(Exception):
    pass


# ------------------------------------------------------------ certificado

def gerar_certificado(pasta: Path, dias: int = DIAS_DO_CERTIFICADO) -> dict:
    """A autoridade só-localhost, o certificado do servidor e a chave dele."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    pasta.mkdir(parents=True, exist_ok=True)
    agora = datetime.now(timezone.utc)
    fim = agora + timedelta(days=dias)
    dns, ips = ["localhost"], [ipaddress.ip_address("127.0.0.1")]

    chave_ac = ec.generate_private_key(ec.SECP256R1())
    nome_ac = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "PAULUS - Word nesta instalacao (so localhost)"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PAULUS"),
    ])
    ac = (x509.CertificateBuilder()
          .subject_name(nome_ac).issuer_name(nome_ac).public_key(chave_ac.public_key())
          .serial_number(x509.random_serial_number())
          .not_valid_before(agora - timedelta(minutes=5)).not_valid_after(fim)
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .add_extension(x509.NameConstraints(
              permitted_subtrees=[x509.DNSName(n) for n in dns]
              + [x509.IPAddress(ipaddress.ip_network(f"{ip}/32")) for ip in ips],
              excluded_subtrees=None), critical=True)
          .add_extension(x509.KeyUsage(digital_signature=False, content_commitment=False, key_encipherment=False,
                                       data_encipherment=False, key_agreement=False, key_cert_sign=True,
                                       crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
          .add_extension(x509.SubjectKeyIdentifier.from_public_key(chave_ac.public_key()), critical=False)
          .sign(chave_ac, hashes.SHA256()))
    chave_srv = ec.generate_private_key(ec.SECP256R1())
    srv = (x509.CertificateBuilder()
           .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
           .issuer_name(nome_ac).public_key(chave_srv.public_key())
           .serial_number(x509.random_serial_number())
           .not_valid_before(agora - timedelta(minutes=5)).not_valid_after(fim)
           .add_extension(x509.SubjectAlternativeName([x509.DNSName(n) for n in dns] + [x509.IPAddress(ip) for ip in ips]),
                          critical=False)
           .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
           .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
           .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(chave_ac.public_key()), critical=False)
           .sign(chave_ac, hashes.SHA256()))
    del chave_ac  # nunca gravada

    der = ac.public_bytes(serialization.Encoding.DER)
    (pasta / "autoridade.cer").write_bytes(der)
    (pasta / "servidor.pem").write_bytes(srv.public_bytes(serialization.Encoding.PEM)
                                         + ac.public_bytes(serialization.Encoding.PEM))
    (pasta / "servidor.key").write_bytes(chave_srv.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    info = {"impressao": ac.fingerprint(hashes.SHA1()).hex().upper(), "vence": fim.isoformat(timespec="seconds")}
    (pasta / "certificado.json").write_text(json.dumps(info), encoding="utf-8")
    return info


def confiado(der: bytes) -> bool:
    """O certificado está entre as raízes confiáveis deste usuário? Lido do repositório."""
    if sys.platform != "win32":
        return False
    try:
        return any(cert == der for cert, _cod, _uso in ssl.enum_certificates("ROOT"))
    except OSError:
        return False


def pedir_confianca(arquivo: Path) -> int:
    """certutil com a janela do Windows ("Aviso de Segurança"); devolve o código de saída."""
    r = subprocess.run(["certutil", "-user", "-addstore", "Root", str(arquivo)], capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=600)
    return r.returncode


# ------------------------------------------------------------ registro do Word

def registrar_no_word(manifesto: Path) -> None:
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CHAVE_DO_REGISTRO) as k:
        winreg.SetValueEx(k, str(manifesto), 0, winreg.REG_SZ, str(manifesto))


def tirar_do_word(manifesto: Path) -> None:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHAVE_DO_REGISTRO, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, str(manifesto))
    except OSError:
        pass


def registrado_no_word(manifesto: Path) -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHAVE_DO_REGISTRO) as k:
            valor, _ = winreg.QueryValueEx(k, str(manifesto))
            return Path(valor) == manifesto
    except OSError:
        return False


def word_no_computador() -> bool:
    """Há Word instalado? Pelo registro do Windows (App Paths), sem abrir o Word."""
    if sys.platform != "win32":
        return False
    import winreg

    caminho = r"Software\Microsoft\Windows\CurrentVersion\App Paths\Winword.exe"
    for raiz in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for vista in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(raiz, caminho, 0, winreg.KEY_READ | vista):
                    return True
            except OSError:
                continue
    return False


# ------------------------------------------------------------ manifesto

def versao_do_manifesto(versao: str) -> str:
    partes = [p for p in str(versao).split(".") if p.isdigit()][:4]
    return ".".join((partes + ["0", "0", "0", "0"])[:4])


def montar_manifesto(*, id_: str, base: str, versao: str) -> str:
    modelo = Template(MODELO_DO_MANIFESTO.read_text(encoding="utf-8"))
    return modelo.substitute(ID=id_, BASE=escape(base.rstrip("/")), VERSAO=versao_do_manifesto(versao),
                             NOME=NOME_NO_WORD)


# ------------------------------------------------------------ a instalação

class Instalacao:
    def __init__(self, estado, pasta_dados: Path) -> None:
        self.estado = estado
        self.pasta = Path(pasta_dados) / "word"
        self.pasta_cert = self.pasta / "certificado"
        self._servidor = None
        self._fio = None
        self._trava = threading.Lock()

    # --- o que está guardado

    def _prefs(self) -> dict:
        return dict(self.estado.prefs.dados.get("word") or {})

    def _id(self, montagem: str) -> str:
        base = self._prefs().get("id") or ""
        if not base:
            base = uuid.uuid4().hex
            self.estado.prefs.atualizar({"word": {"id": base}})
        return str(uuid.uuid5(ESPACO_DOS_IDS, f"{base}:{montagem}"))

    def porta(self) -> int:
        return int(self._prefs().get("porta") or 0)

    def porta_aberta(self) -> int:
        """A porta do servidor HTTPS no ar, ou 0. O porteiro pergunta a cada
        pedido: sem servidor não há pedido nessa porta, e não se lê nada."""
        servidor = self._servidor
        return servidor.config.port if servidor is not None and getattr(servidor, "started", False) else 0

    def manifesto_local(self) -> Path:
        return self.pasta / "manifesto-local.xml"

    def certificado(self) -> dict:
        try:
            info = json.loads((self.pasta_cert / "certificado.json").read_text(encoding="utf-8"))
            der = (self.pasta_cert / "autoridade.cer").read_bytes()
        except (OSError, ValueError):
            return {"existe": False, "confiado": False}
        vence = info.get("vence", "")
        try:
            dias = (datetime.fromisoformat(vence) - datetime.now(timezone.utc)).days
        except ValueError:
            dias = 0
        return {"existe": True, "confiado": confiado(der), "impressao": info.get("impressao", ""),
                "vence": vence[:10], "dias": dias}

    def anotar_carregamento(self, registro: dict) -> None:
        if registro.get("origem") != "local":
            return
        self.pasta.mkdir(parents=True, exist_ok=True)
        (self.pasta / "carregou.json").write_text(json.dumps(registro, ensure_ascii=False), encoding="utf-8")

    def ultimo_carregamento(self) -> dict | None:
        try:
            return json.loads((self.pasta / "carregou.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def endereco_de_fora(self) -> str:
        try:
            situacao = self.estado.acesso_de_fora.situacao()
        except Exception:  # noqa: BLE001
            return ""
        nome = str(situacao.get("hostname") or "")
        return f"https://{nome}" if nome and situacao.get("ligado") else ""

    def situacao(self) -> dict:
        porta = self.porta()
        cert = self.certificado()
        manifesto = self.manifesto_local()
        registrado = manifesto.exists() and registrado_no_word(manifesto)
        instalado_em = self._prefs().get("instalado_em") or ""
        carregou = self.ultimo_carregamento()
        # "Carregado" vale só se o painel abriu depois da última instalação.
        carregado = bool(carregou and instalado_em and carregou.get("quando", "") >= instalado_em)
        return {"porta": porta, "endereco": f"https://localhost:{porta}/word/painel.html" if porta else "",
                "servidor": self._servidor is not None and getattr(self._servidor, "started", False),
                "certificado": cert, "registrado": registrado, "instalado_em": instalado_em,
                "carregado": carregado, "carregou": carregou, "endereco_de_fora": self.endereco_de_fora(),
                "word_no_computador": word_no_computador()}

    # --- instalar

    def _escolher_porta(self) -> int:
        atual = self.porta()
        if atual:
            return atual
        for p in FAIXA_DE_PORTAS:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("127.0.0.1", p))
                except OSError:
                    continue
            self.estado.prefs.atualizar({"word": {"porta": p}})
            return p
        raise FalhaNaInstalacao("nenhuma porta livre entre 46300 e 46399")

    def manifesto(self, montagem: str) -> str:
        from versao import VERSAO

        if montagem == "fora":
            base = self.endereco_de_fora()
            if not base:
                raise FalhaNaInstalacao("o acesso de fora não está ligado e conectado: sem ele não há endereço para o Word de outro computador")
        else:
            porta = self.porta()
            if not porta:
                raise FalhaNaInstalacao("instale no Word deste computador primeiro: a porta ainda não foi escolhida")
            base = f"https://localhost:{porta}"
        return montar_manifesto(id_=self._id(montagem), base=base, versao=VERSAO)

    def instalar(self, *, pedir=pedir_confianca, registrar=registrar_no_word) -> list[dict]:
        passos: list[dict] = []
        with self._trava:
            cert = self.certificado()
            if not cert["existe"] or cert.get("dias", 0) < RENOVAR_COM_DIAS:
                info = gerar_certificado(self.pasta_cert)
                passos.append({"passo": "certificado", "resultado": f"gerado, vale até {info['vence'][:10]}"})
                cert = self.certificado()
            else:
                passos.append({"passo": "certificado", "resultado": f"o mesmo, vale até {cert['vence']}"})
            if not cert["confiado"]:
                codigo = pedir(self.pasta_cert / "autoridade.cer")
                cert = self.certificado()
                if not cert["confiado"]:
                    raise FalhaNaInstalacao("o Windows não confiou no certificado (a janela de aviso foi recusada ou fechada"
                                            f"; código {codigo}). Sem ele o Word não abre o painel.")
                passos.append({"passo": "confiança", "resultado": "o Windows confiou (conferido no repositório)"})
            else:
                passos.append({"passo": "confiança", "resultado": "já confiado"})
            porta = self._escolher_porta()
            passos.append({"passo": "porta", "resultado": f"https://localhost:{porta}"})
            self.pasta.mkdir(parents=True, exist_ok=True)
            self.manifesto_local().write_text(self.manifesto("local"), encoding="utf-8")
            passos.append({"passo": "manifesto", "resultado": str(self.manifesto_local())})
            registrar(self.manifesto_local())
            passos.append({"passo": "registro", "resultado": "o Word deste usuário acha o PAVLVS ao abrir"})
            self.estado.prefs.atualizar({"word": {"instalado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}})
        aberto = self.aplicar()
        passos.append({"passo": "servidor", "resultado": "no ar" if aberto else "não abriu: a porta está ocupada"})
        return passos

    def desinstalar(self, *, tirar=tirar_do_word) -> None:
        tirar(self.manifesto_local())
        self.estado.prefs.atualizar({"word": {"instalado_em": ""}})

    # --- o servidor HTTPS

    def aplicar(self) -> bool:
        """Liga o servidor HTTPS se o Word está ligado e instalado; senão, fecha."""
        prefs = self._prefs()
        cert_ok = (self.pasta_cert / "servidor.pem").exists() and (self.pasta_cert / "servidor.key").exists()
        if prefs.get("ligado") and self.porta() and cert_ok:
            return self.abrir()
        self.fechar()
        return False

    def abrir(self) -> bool:
        app = getattr(self.estado, "app_para_word", None)
        porta = self.porta()
        if app is None or not porta:
            return False
        servidor = self._servidor
        if servidor is not None and getattr(servidor, "started", False) and servidor.config.port == porta:
            return True
        self.fechar()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", porta))
            except OSError:
                return False
        import uvicorn

        # lifespan desligado, como a porta do túnel: o arranque já aconteceu.
        servidor = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=porta, log_level="warning",
                                                 lifespan="off", ssl_certfile=str(self.pasta_cert / "servidor.pem"),
                                                 ssl_keyfile=str(self.pasta_cert / "servidor.key")))
        self._fio = threading.Thread(target=servidor.run, name="porta-do-word", daemon=True)
        self._fio.start()
        fim = time.time() + 5
        while time.time() < fim and not servidor.started:
            time.sleep(0.05)
        if not servidor.started:
            servidor.should_exit = True
            return False
        self._servidor = servidor
        return True

    def fechar(self) -> None:
        if self._servidor is not None:
            self._servidor.should_exit = True
            fio = self._fio
            if fio is not None and fio is not threading.current_thread():
                fio.join(timeout=8)
        self._servidor = None
        self._fio = None
