"""
A pagina que o navegador mostra quando o Google (ou a Microsoft) devolve a
pessoa ao PAULUS depois do login (docs/ui, export "Retorno do login Google"). Quem serve e o
servidor de volta do proprio PAULUS (src/correio_oauth.py, Loopback), em
127.0.0.1:<porta>.

Tres estados:
  - sucesso: o login chegou. As permissoes vem do proprio endereco de volta
    (`scope`, o que o provedor concedeu); o e-mail, a pagina pergunta ao
    PAULUS (/estado) enquanto ele termina a conexao - antes disso nao se sabe;
  - negado: o provedor devolveu `error` (acesso_negado, na maioria);
  - expirado: o endereco ja foi usado, nao e deste login, ou o login ja
    terminou (cancelado, prazo vencido).

A pagina vem de outra porta que a do app, entao nao carrega nada dele: as
fontes (EB Garamond, Manrope, Fira Code) vao embutidas em base64, e os
icones sao SVG escritos aqui. Nada vem da internet.
"""

from __future__ import annotations

import base64
import html
import json
from functools import lru_cache
from pathlib import Path

FONTES = Path(__file__).resolve().parent.parent / "frontend" / "fontes"

# O que cada permissao quer dizer, na lingua de quem usa. So aparecem as que
# o provedor concedeu de fato (o `scope` da volta).
PERMISSOES = [
    ("mail.google.com", "gmail", "Gmail", "ler e enviar, com Aprovações"),
    ("calendar.events", "gagenda", "Agenda", "ler e criar eventos"),
    ("calendar.events", "gmeet", "Meet", "criar reuniões nos eventos"),
    ("drive.file", "gdrive", "Drive", "só os arquivos que o PAVLVS envia"),
    # A leitura do Drive (drive.readonly) le tudo o que a conta ve; o PAULUS
    # so copia as pastas escolhidas no Acervo (src/drive_online.py).
    ("drive.readonly", "gdrive", "Drive", "ler as pastas que você escolher no Acervo"),
    ("IMAP.AccessAsUser.All", "email", "E-mail do Outlook", "ler as mensagens"),
    ("SMTP.Send", "email", "Envio pelo Outlook", "enviar, passando por Aprovações"),
]

MARCAS = {
    "gmail": '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="#4285F4" d="M2 6.5V18a1.5 1.5 0 0 0 1.5 1.5H6.5V11l-4.5-4.5Z"/>'
             '<path fill="#34A853" d="M17.5 19.5h3A1.5 1.5 0 0 0 22 18V6.5L17.5 11Z"/>'
             '<path fill="#FBBC04" d="M17.5 5.5V11L22 6.5V5.3c0-1.3-1.5-2-2.5-1.3Z"/>'
             '<path fill="#EA4335" d="M6.5 11V5.5L12 9.6l5.5-4.1V11L12 15.1Z"/>'
             '<path fill="#C5221F" d="M2 5.3v1.2L6.5 11V5.5L4.5 4C3.5 3.3 2 4 2 5.3Z"/></svg>',
    "gagenda": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2.5" fill="#fff" stroke="#4285F4" stroke-width="2"/>'
               '<path fill="#4285F4" d="M3 5.5A2.5 2.5 0 0 1 5.5 3h13A2.5 2.5 0 0 1 21 5.5V8H3Z"/>'
               '<text x="12" y="18" text-anchor="middle" font-family="Arial,sans-serif" font-size="8.5" font-weight="700" fill="#1967D2">31</text></svg>',
    "gmeet": '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="#00832D" d="M14 12l2.6 2.3 3.4 2.2V7.5l-3.4 2.2Z"/>'
             '<path fill="#0066DA" d="M3 15.5v3A1.5 1.5 0 0 0 4.5 20h3v-4.5Z"/><path fill="#E94235" d="M7.5 4 3 8.5h4.5Z"/>'
             '<path fill="#2684FC" d="M3 8.5h4.5v7H3Z"/><path fill="#00AC47" d="M15.5 16.3 14 12v5.5a1.5 1.5 0 0 1-1.5 1.5H7.5v-4.5h6.5Z"/>'
             '<path fill="#FFBA00" d="M12.5 4h-5v4.5H14V5.5A1.5 1.5 0 0 0 12.5 4Z"/><path fill="#00832D" d="M7.5 8.5H14V12l-6.5 3.5Z"/></svg>',
    "gdrive": '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="#0066DA" d="m3.5 17.3.9 1.6c.2.3.5.6.8.7L8.3 14H2.1c0 .4.1.7.3 1Z"/>'
              '<path fill="#00AC47" d="M12 8.2 8.9 2.8c-.3.2-.6.4-.8.7L2.4 13c-.2.3-.3.7-.3 1h6.2Z"/>'
              '<path fill="#EA4335" d="M18.8 19.6c.3-.2.6-.4.8-.7l.4-.6 1.7-3c.2-.3.3-.7.3-1h-6.2l1.3 2.6Z"/>'
              '<path fill="#00832D" d="M12 8.2 15.1 2.8c-.3-.2-.7-.3-1-.3H9.9c-.4 0-.7.1-1 .3Z"/>'
              '<path fill="#2684FC" d="M15.7 14H8.3l-3.1 5.6c.3.2.7.3 1 .3h11.6c.4 0 .7-.1 1-.3Z"/>'
              '<path fill="#FFBA00" d="m18.8 8.6-2.9-5c-.2-.3-.5-.6-.8-.8L12 8.2l3.7 5.8h6.2c0-.4-.1-.7-.3-1Z"/></svg>',
}

ICONES = {
    "email": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="5.5" width="17" height="13" rx="1.5"/><path d="M4 7l8 6 8-6"/></svg>',
    "agenda": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="5" width="17" height="15" rx="1.5"/><path d="M3.5 9.5h17M8 3v4M16 3v4"/></svg>',
    "pasta": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 6.5a1 1 0 011-1h5l2 2h8a1 1 0 011 1v9.5a1 1 0 01-1 1h-15a1 1 0 01-1-1z"/></svg>',
    "sol": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M5.3 18.7l1.6-1.6M17.1 6.9l1.6-1.6"/></svg>',
    "lua": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19.5 14.5A8 8 0 019.5 4.5a8 8 0 1010 10z"/></svg>',
}

GOOGLE = ('<svg viewBox="0 0 48 48" aria-hidden="true">'
          '<path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>'
          '<path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>'
          '<path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>'
          '<path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>')
MICROSOFT = ('<svg viewBox="0 0 21 21" aria-hidden="true"><rect x="1" y="1" width="9" height="9" fill="#F25022"/>'
             '<rect x="11" y="1" width="9" height="9" fill="#7FBA00"/><rect x="1" y="11" width="9" height="9" fill="#00A4EF"/>'
             '<rect x="11" y="11" width="9" height="9" fill="#FFB900"/></svg>')


@lru_cache(maxsize=1)
def _fontes_css() -> str:
    """As fontes do app, embutidas: a pagina nao pode buscar nada fora dela."""
    pecas = [("EB Garamond", "EBGaramond-normal-400-latin.woff2", "400 600", "normal"),
             ("EB Garamond", "EBGaramond-italic-400-latin.woff2", "400", "italic"),
             ("Manrope", "Manrope-normal-400-latin.woff2", "400 700", "normal"),
             ("Fira Code", "FiraCode-normal-400-latin.woff2", "400 600", "normal")]
    css = []
    for familia, arquivo, pesos, estilo in pecas:
        try:
            dados = base64.b64encode((FONTES / arquivo).read_bytes()).decode("ascii")
        except OSError:
            continue                       # sem a fonte, fica a reserva do sistema
        css.append(f"@font-face{{font-family:'{familia}';font-weight:{pesos};font-style:{estilo};font-display:swap;"
                   f"src:url(data:font/woff2;base64,{dados}) format('woff2')}}")
    return "".join(css)


def _permissoes(escopos: str) -> list[tuple[str, str, str]]:
    return [(icone, nome, desc) for chave, icone, nome, desc in PERMISSOES if chave in (escopos or "")]


# rotulo, tom, titulo, texto, nota, dica
TEXTOS = {
    "sucesso": ("CONECTADO", "ok", "Conta %%PROVEDOR%% conectada.", "", "", "Já pode fechar esta aba."),
    # So quem e (o vinculo do PAVLVS, destravar): nenhuma permissao pedida.
    "entrou": ("LOGIN RECEBIDO", "ok", "Login recebido.", "", "", "Já pode fechar esta aba."),
    "negado": ("NÃO CONECTADO", "aviso", "A conexão não foi autorizada.", "", "", "Nada foi alterado."),
    "expirado": ("LINK EXPIRADO", "erro", "Este login expirou.", "", "", "Volte ao PAVLVS e abra outro."),
}


def pagina(estado: str, *, provedor: str = "Google", escopos: str = "", detalhe: str = "", tema: str = "escuro",
           porta: int = 0, state: str = "") -> str:
    """O HTML completo de um dos tres estados."""
    esc = html.escape
    perms = _permissoes(escopos) if estado == "sucesso" else []
    chave = "entrou" if estado == "sucesso" and not perms else estado
    rotulo, tom, titulo, texto, nota, dica = TEXTOS.get(chave, TEXTOS["expirado"])
    titulo, texto = titulo.replace("%%PROVEDOR%%", provedor), texto.replace("%%PROVEDOR%%", provedor)
    marca = MICROSOFT if provedor.lower().startswith("micro") else GOOGLE
    # O desenho "Google - Conectado" (02/10/2026): a coluna de 360 px, a conta
    # com o selo, o que foi autorizado numa caixa so, com a marca de cada
    # servico, e o "Voltar ao PAVLVS" no trilho.
    painel = ""
    if estado == "sucesso":
        painel = ('<div class="grupo"><span class="etiqueta">CONTA</span>'
                  f'<div class="caixa"><span class="marca">{marca}</span><span class="email" id="email">conferindo a conta…</span>'
                  '<span class="selo" id="selo"><i></i><span id="selo-texto">recebido</span></span></div>'
                  '<p class="falha" id="falha" hidden></p></div>')
        if perms:
            painel += ('<div class="grupo"><span class="etiqueta">O QUE VOCÊ AUTORIZOU</span><div class="lista">' + "".join(
                f'<div class="linha"><span class="servico">{MARCAS.get(icone, "")}</span><span class="nome">{esc(nome)}</span>'
                f'<span class="d">{esc(desc)}</span></div>'
                for icone, nome, desc in perms) + "</div></div>")
    elif detalhe:
        painel = f'<div class="grupo"><span class="etiqueta">DETALHE</span><div class="caixa detalhe">{esc(detalhe)}</div></div>'
    tema = "claro" if tema == "claro" else "escuro"
    dados = json.dumps({"state": state if estado == "sucesso" else "", "tema": tema})
    return (PAGINA.replace("%%FONTES%%", _fontes_css())
            .replace("%%TEMA%%", tema)
            .replace("%%TOM%%", tom)
            .replace("%%ROTULO%%", esc(rotulo))
            .replace("%%TITULO%%", esc(titulo))
            .replace("%%TEXTO%%", esc(texto))
            .replace("%%NOTA%%", esc(nota))
            .replace("%%PAINEL%%", painel)
            .replace("%%DICA%%", esc(dica))
            .replace("%%PORTA%%", str(porta) if porta else "")
            .replace("%%PROVEDOR%%", esc(provedor))
            .replace("%%SOL%%", ICONES["sol"]).replace("%%LUA%%", ICONES["lua"])
            .replace("%%DADOS%%", dados))


PAGINA = """<!doctype html>
<html lang="pt-BR" data-tema="%%TEMA%%">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PAULUS</title>
<style>
%%FONTES%%
[data-tema="escuro"]{--bg:#131312;--surf:#1a1a18;--fill2:#2a2a27;--ink:#f2f1ec;--ink3:#95938a;--apagado:#6f6e68;--marca-dagua:#8a8982;--marca-sub:#6f6e68;
--fio:rgba(242,241,236,.12);--fio2:rgba(242,241,236,.1);--fio3:rgba(242,241,236,.08);--ok:#7fbf8e;--erro:#f0a19c;--sobre:#303030;--ativa:#333330;color-scheme:dark}
[data-tema="claro"]{--bg:#faf9f6;--surf:#fff;--fill2:#e9e8e3;--ink:#1c1c1a;--ink3:#6b6b65;--apagado:#9a9a93;--marca-dagua:#8a8a86;--marca-sub:#a8a69e;
--fio:rgba(28,28,26,.12);--fio2:rgba(28,28,26,.1);--fio3:rgba(28,28,26,.08);--ok:#2f6b42;--erro:#a3322b;--sobre:#e2e1db;--ativa:#dcdbd5;color-scheme:light}
*{box-sizing:border-box}html,body{margin:0}
body{min-height:100vh;min-height:100dvh;display:flex;flex-direction:column;align-items:center;justify-content:flex-start;padding:22vh 24px 48px;padding-top:22dvh;
background:var(--bg);color:var(--ink);font:400 14px/1.5 'Manrope',system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.coluna{width:100%;max-width:360px;display:grid;gap:40px}
.topo{display:grid;gap:14px;text-align:center}
.topo b{font:400 56px/1 'EB Garamond',Georgia,serif;letter-spacing:.08em;text-transform:uppercase;color:var(--marca-dagua)}
.topo p{margin:0;font:400 14px/1.55 'Manrope',sans-serif;color:var(--marca-sub);text-wrap:pretty}
.form{display:grid;gap:14px}.grupo{display:grid;gap:6px}
.etiqueta{font:400 11px 'Fira Code',ui-monospace,monospace;letter-spacing:.18em;color:var(--apagado)}
.caixa{display:flex;align-items:center;gap:10px;height:40px;padding:0 12px;border-radius:10px;background:var(--surf);border:1px solid var(--fio)}
.marca{display:flex;flex:none}.marca svg{width:16px;height:16px}
.email{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font:400 13.5px 'Manrope',sans-serif;color:var(--ink)}
.selo{flex:none;display:flex;align-items:center;gap:6px;font:400 11px 'Fira Code',ui-monospace,monospace;color:var(--apagado);white-space:nowrap}
.selo i{display:block;width:6px;height:6px;border-radius:50%;background:currentColor}
.selo.ok{color:var(--ok)}.selo.erro{color:var(--erro)}
.falha{margin:0;font-size:12.5px;line-height:1.5;color:var(--erro)}
.lista{display:grid;border-radius:10px;background:var(--surf);border:1px solid var(--fio2);overflow:hidden}
.linha{display:flex;align-items:center;gap:10px;height:44px;padding:0 12px;border-bottom:1px solid var(--fio3)}
.linha:last-child{border-bottom:0}
.servico{display:flex;flex:none}.servico svg{width:16px;height:16px}
.nome{width:56px;flex:none;font:500 13.5px 'Manrope',sans-serif;color:var(--ink)}
.linha .d{flex:1;min-width:0;font:400 12.5px 'Manrope',sans-serif;color:var(--ink3);text-align:right}
.detalhe{height:auto;min-height:40px;padding:10px 12px;font:400 12.5px 'Fira Code',ui-monospace,monospace;color:var(--ink3);word-break:break-all}
.trilho{display:flex;width:100%;padding:3px;border-radius:10px;background:var(--surf);border:1px solid var(--fio2);cursor:pointer}
.pastilha{flex:1;height:34px;display:flex;align-items:center;justify-content:center;border-radius:8px;background:var(--fill2);color:var(--ink);
font:500 13.5px 'Manrope',sans-serif;letter-spacing:.01em}
.trilho:hover .pastilha{background:var(--sobre)}.trilho:active .pastilha{background:var(--ativa)}
.trilho:focus-visible{outline:2px solid var(--ink3);outline-offset:2px}
.dica{justify-self:center;font:400 12px/1.5 'Manrope',sans-serif;color:var(--apagado);text-align:center;text-wrap:pretty}
</style>
</head>
<body>
<div class="coluna">
<div class="topo"><b>PAVLVS</b><p id="titulo">%%TITULO%%</p></div>
<div class="form">
%%PAINEL%%
<button type="button" class="trilho" id="voltar"><span class="pastilha">Voltar ao PAVLVS</span></button>
<span class="dica">%%DICA%%</span>
</div>
</div>
<script>
(function () {
  var dados = %%DADOS%%;
  var raiz = document.documentElement;
  try { var t = localStorage.getItem("pv-tema"); if (t === "claro" || t === "escuro") raiz.dataset.tema = t; } catch (e) {}
  // Voltar: o PAULUS traz a janela dele para frente; a aba fecha se o
  // navegador deixar (so abas abertas por script podem se fechar).
  // paulus:// (02/10): o navegador pergunta "Abrir PAULUS?" e o PAULUS
  // aberto vem para a frente (src/desktop.py). Sem o registro, nada acontece
  // aqui - e o aviso ao servidor, de sempre, traz a janela do mesmo jeito.
  var abriu = false;
  function abrirApp() {
    if (abriu) return;
    abriu = true;
    try { window.location.href = "paulus://voltar"; } catch (e) {}
  }
  document.getElementById("voltar").onclick = function () {
    abriu = false;
    abrirApp();
    fetch("/voltar?state=" + encodeURIComponent(dados.state)).catch(function () {});
    setTimeout(function () { try { window.close(); } catch (e) {} }, 300);
  };
  if (!dados.state) return;
  // O e-mail e o fim da conexao: o PAULUS sabe depois de trocar o codigo.
  var tentativas = 0;
  function perguntar() {
    tentativas += 1;
    fetch("/estado?state=" + encodeURIComponent(dados.state)).then(function (r) { return r.json(); }).then(function (d) {
      var selo = document.getElementById("selo"), texto = document.getElementById("selo-texto"), email = document.getElementById("email");
      if (d.email) email.textContent = d.email;
      if (d.fase === "pronto") { texto.textContent = "conectado"; selo.className = "selo ok"; abrirApp(); return; }
      if (d.fase === "erro" || d.fase === "cancelado") {
        texto.textContent = "não conectado"; selo.className = "selo erro";
        var f = document.getElementById("falha"); f.hidden = false;
        f.textContent = "O PAULUS não terminou: " + (d.mensagem || "o login não foi concluído") + ". Volte ao PAULUS e tente de novo.";
        if (!d.email) email.textContent = "conta não confirmada";
        return;
      }
      if (tentativas < 90) setTimeout(perguntar, 1000);
    }).catch(function () { if (tentativas < 90) setTimeout(perguntar, 1500); });
  }
  perguntar();
})();
</script>
</body>
</html>
"""
