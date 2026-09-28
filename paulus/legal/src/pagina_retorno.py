"""
A pagina que o navegador mostra quando o Google (ou a Microsoft) devolve a
pessoa ao PAULUS depois do login (docs/ui/login-google). Quem serve e o
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
fontes (EB Garamond, Manrope, IBM Plex Mono) vao embutidas em base64, e os
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
    ("mail.google.com", "email", "Gmail", "ler e enviar, com o envio passando por Aprovações"),
    ("calendar.events", "agenda", "Agenda e Meet", "criar e mudar os compromissos que o PAULUS marca"),
    ("drive.file", "pasta", "Drive", "só os arquivos que o PAULUS envia"),
    ("IMAP.AccessAsUser.All", "email", "E-mail do Outlook", "ler as mensagens"),
    ("SMTP.Send", "email", "Envio pelo Outlook", "enviar, passando por Aprovações"),
]

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
    pecas = [("EB Garamond", "EBGaramond-normal-400-latin.woff2", "400 600"),
             ("Manrope", "Manrope-normal-400-latin.woff2", "400 700"),
             ("IBM Plex Mono", "IBMPlexMono-normal-400-latin.woff2", "400")]
    css = []
    for familia, arquivo, pesos in pecas:
        try:
            dados = base64.b64encode((FONTES / arquivo).read_bytes()).decode("ascii")
        except OSError:
            continue                       # sem a fonte, fica a reserva do sistema
        css.append(f"@font-face{{font-family:'{familia}';font-weight:{pesos};font-display:swap;"
                   f"src:url(data:font/woff2;base64,{dados}) format('woff2')}}")
    return "".join(css)


def _permissoes(escopos: str) -> list[tuple[str, str, str]]:
    return [(icone, nome, desc) for chave, icone, nome, desc in PERMISSOES if chave in (escopos or "")]


TEXTOS = {
    "sucesso": ("CONECTADO", "ok", "Pode fechar esta aba e voltar ao PAULUS.",
                "O login foi recebido. O PAULUS termina a conexão com a sua conta em alguns segundos; o andamento aparece aqui e no próprio PAULUS.",
                "ou feche esta aba"),
    "negado": ("NÃO CONECTADO", "aviso", "A conexão não foi autorizada.",
               "O login foi cancelado ou as permissões não foram marcadas. Nada foi conectado. Para tentar de novo, volte ao PAULUS e peça para entrar outra vez.",
               "nada foi alterado"),
    "expirado": ("LINK EXPIRADO", "erro", "Este login expirou.",
                 "Este endereço de volta já foi usado, não é do login que o PAULUS abriu, ou o login já terminou (cancelado, ou passaram 5 minutos). Volte ao PAULUS e peça para entrar de novo.",
                 "nada foi alterado"),
}


def pagina(estado: str, *, provedor: str = "Google", escopos: str = "", detalhe: str = "", tema: str = "escuro",
           porta: int = 0, state: str = "") -> str:
    """O HTML completo de um dos tres estados."""
    rotulo, tom, titulo, texto, dica = TEXTOS.get(estado, TEXTOS["expirado"])
    esc = html.escape
    marca = MICROSOFT if provedor.lower().startswith("micro") else GOOGLE
    cartao = ""
    if estado == "sucesso":
        linhas = "".join(
            f'<div class="perm"><span class="ic">{ICONES[icone]}</span><span class="nome">{esc(nome)}</span>'
            f'<span class="desc">{esc(desc)}</span></div>' for icone, nome, desc in _permissoes(escopos))
        cartao = (f'<div class="cartao"><div class="conta"><span class="marca">{marca}</span>'
                  f'<span class="quem"><b>Conta {esc(provedor)}</b><small id="email">conferindo a conta…</small></span>'
                  f'<span class="selo" id="selo">login recebido</span></div>'
                  + (f'<div class="perms"><span class="rotulo">O QUE VOCÊ AUTORIZOU</span>{linhas}</div>' if linhas else "")
                  + '<p class="falha" id="falha" hidden></p></div>')
    elif detalhe:
        cartao = f'<div class="cartao"><span class="rotulo">DETALHE</span><code>{esc(detalhe)}</code></div>'
    tema = "claro" if tema == "claro" else "escuro"
    dados = json.dumps({"state": state if estado == "sucesso" else "", "tema": tema})
    return (PAGINA.replace("%%FONTES%%", _fontes_css())
            .replace("%%TEMA%%", tema)
            .replace("%%TOM%%", tom)
            .replace("%%ROTULO%%", esc(rotulo))
            .replace("%%TITULO%%", esc(titulo))
            .replace("%%TEXTO%%", esc(texto))
            .replace("%%CARTAO%%", cartao)
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
:root{--bg:#faf9f6;--surf:#fff;--ink:#1c1c1a;--ink2:#6b6b65;--ink3:#8a8a84;--fill:#f3f2ee;--hair:rgba(28,28,26,.1);
--ok:#2f6b42;--okbg:#edf5ee;--aviso:#8a5a12;--avisobg:#fbf1de;--erro:#a3322b;--errobg:#fbeceb;--casca:#26251f;--casca2:#3a382f;color-scheme:light}
[data-tema="escuro"]{--bg:#131312;--surf:#1a1a18;--ink:#f2f1ec;--ink2:#a8a69e;--ink3:#95938a;--fill:#222220;--hair:rgba(242,241,236,.1);
--ok:#8fd0a3;--okbg:#16281c;--aviso:#e8c283;--avisobg:#3a2c12;--erro:#f0a19c;--errobg:#3a1716;--casca:#34322c;--casca2:#413e35;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;flex-direction:column;background:var(--bg);color:var(--ink);font:15px/1.55 'Manrope',system-ui,sans-serif;
-webkit-font-smoothing:antialiased;padding:36px clamp(24px,5vw,64px)}
.topo{display:flex;align-items:center;justify-content:space-between;gap:16px}
.pavlvs{font:500 22px/1 'EB Garamond',Georgia,serif;letter-spacing:.12em}
.tema{width:32px;height:32px;padding:0;border:0;background:none;color:var(--ink2);cursor:pointer;display:flex;align-items:center;justify-content:center;border-radius:6px}
.tema:hover{color:var(--ink)}.tema:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.tema svg{width:19px;height:19px;fill:none;stroke:currentColor;stroke-width:1.5;stroke-linecap:round}
[data-tema="escuro"] .tema .lua,[data-tema="claro"] .tema .sol{display:none}
main{flex:1;display:flex;align-items:center;justify-content:center;padding:48px 0}
.bloco{width:100%;max-width:520px;display:grid;gap:20px}
.estado{display:flex;align-items:center;gap:8px;font:400 11px 'IBM Plex Mono',ui-monospace,monospace;letter-spacing:.16em;color:var(--%%TOM%%)}
.estado i{display:block;width:6px;height:6px;border-radius:50%;background:currentColor}
h1{margin:0;font:400 clamp(34px,4.4vw,48px)/1.06 'EB Garamond',Georgia,serif;letter-spacing:-.015em;text-wrap:balance}
p{margin:0;font-size:16px;line-height:1.65;color:var(--ink2);text-wrap:pretty}
.cartao{border:1px solid var(--hair);border-radius:14px;background:var(--surf);padding:18px 20px;display:grid;gap:14px}
.conta{display:flex;align-items:center;gap:12px}
.marca{width:36px;height:36px;border-radius:9px;background:var(--bg);border:1px solid var(--hair);display:flex;align-items:center;justify-content:center;flex:none}
.marca svg{width:18px;height:18px}
.quem{display:grid;flex:1;min-width:0}.quem b{font-weight:600}
.quem small{font-size:13px;color:var(--ink2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.selo{padding:2px 8px;border-radius:5px;font-weight:600;font-size:11.5px;white-space:nowrap;background:var(--fill);color:var(--ink2)}
.selo.ok{background:var(--okbg);color:var(--ok)}.selo.erro{background:var(--errobg);color:var(--erro)}
.perms{display:grid;gap:8px;border-top:1px solid var(--hair);padding-top:12px}
.rotulo{font:400 11px 'IBM Plex Mono',ui-monospace,monospace;letter-spacing:.16em;color:var(--ink3)}
.perm{display:flex;align-items:flex-start;gap:10px;font-size:13.5px}
.perm .ic svg{width:17px;height:17px;fill:none;stroke:var(--ink2);stroke-width:1.4;stroke-linejoin:round;margin-top:2px}
.perm .nome{flex:none;min-width:110px}.perm .desc{color:var(--ink2);flex:1;text-align:right}
.falha{font-size:13.5px;color:var(--erro)}
code{font:13px 'IBM Plex Mono',ui-monospace,monospace;color:var(--ink2);word-break:break-all}
.acoes{display:flex;align-items:center;gap:16px;flex-wrap:wrap;padding-top:4px}
.voltar{display:inline-flex;align-items:center;gap:8px;padding:10px 18px;border-radius:8px;border:0;font:600 14px 'Manrope',system-ui,sans-serif;
cursor:pointer;background:var(--casca);color:#f2f1ec}
.voltar:hover{background:var(--casca2)}.voltar:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.dica{font-size:13px;color:var(--ink3)}
footer{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;border-top:1px solid var(--hair);padding-top:16px;font-size:12.5px;color:var(--ink3)}
footer .porta{font-family:'IBM Plex Mono',ui-monospace,monospace}
@media (max-width:560px){.perm{flex-wrap:wrap}.perm .desc{text-align:left;flex-basis:100%;padding-left:27px}}
</style>
</head>
<body>
<header class="topo"><span class="pavlvs">PAVLVS</span>
<button type="button" class="tema" id="tema" aria-label="Alternar claro/escuro" title="Alternar claro/escuro"><span class="sol">%%SOL%%</span><span class="lua">%%LUA%%</span></button></header>
<main><div class="bloco">
<span class="estado"><i></i><span id="rotulo">%%ROTULO%%</span></span>
<h1>%%TITULO%%</h1>
<p id="texto">%%TEXTO%%</p>
%%CARTAO%%
<div class="acoes"><button type="button" class="voltar" id="voltar">Voltar ao PAULUS</button><span class="dica">%%DICA%%</span></div>
</div></main>
<footer><span>Esta página é servida pelo próprio PAULUS, neste computador (127.0.0.1). O %%PROVEDOR%% não recebe nada dos seus documentos.</span>
<span class="porta">127.0.0.1:%%PORTA%%</span></footer>
<script>
(function () {
  var dados = %%DADOS%%;
  var raiz = document.documentElement;
  try { var t = localStorage.getItem("pv-tema"); if (t === "claro" || t === "escuro") raiz.dataset.tema = t; } catch (e) {}
  document.getElementById("tema").onclick = function () {
    var t = raiz.dataset.tema === "escuro" ? "claro" : "escuro";
    raiz.dataset.tema = t;
    try { localStorage.setItem("pv-tema", t); } catch (e) {}
  };
  // Voltar: o PAULUS traz a janela dele para frente; a aba fecha se o
  // navegador deixar (so abas abertas por script podem se fechar).
  document.getElementById("voltar").onclick = function () {
    fetch("/voltar?state=" + encodeURIComponent(dados.state)).catch(function () {});
    setTimeout(function () { try { window.close(); } catch (e) {} }, 300);
  };
  if (!dados.state) return;
  // O e-mail e o fim da conexao: o PAULUS sabe depois de trocar o codigo.
  var tentativas = 0;
  function perguntar() {
    tentativas += 1;
    fetch("/estado?state=" + encodeURIComponent(dados.state)).then(function (r) { return r.json(); }).then(function (d) {
      var selo = document.getElementById("selo"), email = document.getElementById("email");
      if (d.email) email.textContent = d.email;
      if (d.fase === "pronto") { selo.textContent = "conectado"; selo.className = "selo ok"; return; }
      if (d.fase === "erro" || d.fase === "cancelado") {
        selo.textContent = "não conectado"; selo.className = "selo erro";
        var f = document.getElementById("falha"); f.hidden = false;
        f.textContent = "O PAULUS não terminou a conexão: " + (d.mensagem || "o login não foi concluído") + ". Volte ao PAULUS e tente de novo.";
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
