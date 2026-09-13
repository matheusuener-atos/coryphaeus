"""
Quem extrai o que, com qual modelo - e por que isso e configuracao.

Trocar o especialista de uma secao tem de ser uma linha de arquivo, nao uma
mexida em codigo. A razao e pratica: o melhor modelo para achar partes num
processo muda a cada poucos meses, e o programa roda numa maquina onde o
modelo disponivel depende do que coube no disco. Se a escolha estiver no
codigo, cada troca vira um commit e um risco; no arquivo, vira uma linha e um
reprocessamento da secao afetada.

Ha uma assimetria que este arquivo existe para declarar: **ingestao e consulta
sao perfis opostos.** A ingestao roda uma vez por documento, em segundo plano,
e pode demorar - deve usar o melhor modelo que a maquina tem. A consulta e
interativa e precisa responder agora - usa o modelo pequeno e o contexto
minimo. Um modelo so para as duas coisas seria lento demais para uma ou burro
demais para a outra.

O arquivo fica em `config/extratores.yaml`, versionado junto com o codigo: ele
descreve o desenho do sistema, nao a maquina de quem usa. O que e da maquina -
qual modelo esta instalado - continua em `data/preferencias.json`.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path

PADRAO = Path(__file__).resolve().parent.parent.parent / "config" / "extratores.yaml"


@dataclass
class Modelo:
    """Um perfil de modelo. Temperatura zero e semente fixa, sempre."""

    id: str = ""
    runtime: str = "ollama"
    temperature: float = 0.0
    seed: int = 42
    num_ctx: int = 8192

    def to_dict(self) -> dict:
        return {"id": self.id, "runtime": self.runtime, "temperature": self.temperature,
                "seed": self.seed, "num_ctx": self.num_ctx}


@dataclass
class Extrator:
    """Um especialista declarado: o que ele faz, em que nivel, com que modelo."""

    id: str = ""
    secao: str = ""
    nivel: int = 0
    modulo: str = ""
    modelo: str = ""        # a chave em `modelos`; vazio = nao usa modelo
    modo: str = ""          # "residual" = so no que a regra nao resolveu
    prompt_version: str = ""
    papel: str = ""         # "verifier" para o conferidor

    def carregar(self):
        """O modulo do extrator, importado na hora do uso."""
        return importlib.import_module(f"inteligencia.extratores.{self.modulo}")


@dataclass
class Catalogo:
    caminho: Path = PADRAO
    modelos: dict[str, Modelo] = field(default_factory=dict)
    extratores: dict[str, Extrator] = field(default_factory=dict)
    erro: str = ""

    # ------------------------------------------------------------- leitura

    @classmethod
    def carregar(cls, caminho: Path | str = PADRAO) -> "Catalogo":
        import yaml

        caminho = Path(caminho)
        catalogo = cls(caminho=caminho)
        try:
            bruto = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            # Sem catalogo legivel a camada nao roda - e o programa continua
            # funcionando como antes, que e a regra de ouro do retrofit.
            catalogo.erro = f"nao consegui ler {caminho.name}: {exc}"
            return catalogo

        for nome, dados in (bruto.get("modelos") or {}).items():
            catalogo.modelos[nome] = Modelo(
                id=str(dados.get("id", "")), runtime=str(dados.get("runtime", "ollama")),
                temperature=float(dados.get("temperature", 0) or 0),
                seed=int(dados.get("seed", 42) or 42),
                num_ctx=int(dados.get("num_ctx", 8192) or 8192))

        for identificador, dados in (bruto.get("extratores") or {}).items():
            catalogo.extratores[identificador] = Extrator(
                id=identificador, secao=str(dados.get("secao", "")),
                nivel=int(dados.get("nivel", 0) or 0), modulo=str(dados.get("modulo", "")),
                modelo=str(dados.get("modelo", "") or ""), modo=str(dados.get("modo", "") or ""),
                prompt_version=str(dados.get("prompt_version", "") or ""),
                papel=str(dados.get("papel", "") or ""))
        return catalogo

    # -------------------------------------------------------------- buscar

    def para_secao(self, secao: str) -> Extrator | None:
        """
        O extrator principal de uma secao.

        Principal e o de MENOR nivel: regra antes de modelo, sempre. O
        `residual` - o modelo que entra so no que a regra nao resolveu - nunca
        e o principal, porque a secao tem de continuar existindo quando o
        modelo estiver desligado.
        """
        candidatos = [e for e in self.extratores.values()
                      if e.secao == secao and e.modo != "residual" and not e.papel]
        return sorted(candidatos, key=lambda e: e.nivel)[0] if candidatos else None

    def residuais(self, secao: str) -> list[Extrator]:
        return [e for e in self.extratores.values() if e.secao == secao and e.modo == "residual"]

    def do_nivel(self, nivel: int) -> list[Extrator]:
        return [e for e in self.extratores.values() if e.nivel == nivel and not e.papel]

    def verificador(self) -> Extrator | None:
        return next((e for e in self.extratores.values() if e.papel == "verifier"), None)

    def modelo_de(self, extrator: Extrator) -> Modelo | None:
        return self.modelos.get(extrator.modelo) if extrator.modelo else None

    def secoes_declaradas(self) -> list[str]:
        vistas: list[str] = []
        for extrator in sorted(self.extratores.values(), key=lambda e: (e.nivel, e.secao)):
            if extrator.secao and extrator.secao not in vistas and not extrator.papel:
                vistas.append(extrator.secao)
        return vistas

    def problemas(self) -> list[str]:
        """O que impediria este catalogo de rodar - dito antes de tentar."""
        from . import esquema

        achados = []
        if self.erro:
            achados.append(self.erro)
        for extrator in self.extratores.values():
            if extrator.papel:
                continue
            if extrator.secao not in esquema.SECOES:
                achados.append(f"{extrator.id}: secao '{extrator.secao}' nao existe no esquema")
            if not extrator.modulo:
                achados.append(f"{extrator.id}: sem modulo")
            if extrator.modelo and extrator.modelo not in self.modelos:
                achados.append(f"{extrator.id}: modelo '{extrator.modelo}' nao esta declarado")
            if extrator.nivel == 0 and extrator.modelo:
                achados.append(f"{extrator.id}: nivel 0 e regra, nao pode ter modelo")
        return achados
