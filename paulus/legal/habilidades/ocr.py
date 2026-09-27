"""
Habilidade: Ler documento escaneado.

Nao tem botao proprio: acontece sozinha quando um PDF entra (Acervo, anexo de
servico, material de consulta). A pagina que e imagem passa pelo leitor de
imagem do Windows (src/ocr_windows.py) - sem modelo para baixar, sem internet.
"""

from habilidade_base import Habilidade

HABILIDADE = Habilidade(
    id="ocr",
    nome="Ler documento escaneado",
    resumo="Reconhece o texto de PDF que é imagem, pelo leitor de imagem do Windows",
    grupo="Documentos",
    acao="anexar",
    detalhe=(
        "Acontece sozinho quando o PDF entra: a página que é imagem é lida pelo leitor do "
        "próprio Windows, nesta máquina. O texto pode ter erro de leitura, e o Acervo mostra "
        "que ele veio da imagem."
    ),
    demora="menos de um segundo por página",
    ordem=40,
)


def executar(ctx) -> dict:
    """Confere se o leitor de imagem do Windows responde nesta maquina, e em que idioma."""
    import ocr_windows

    situacao = ocr_windows.situacao()
    ctx.registrar("leitor de imagem " + ("pronto, em " + situacao["idioma"] if situacao["ok"] else "indisponível: " + situacao["motivo"]))
    return {k: v for k, v in situacao.items() if k != "idiomas"}
