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
    "sucesso": ("CONECTADO", "ok", "Conta %%PROVEDOR%% conectada.",
                "Em alguns segundos, e-mails, agenda e arquivos autorizados começam a aparecer no escritório.",
                "Nada dos seus documentos sai deste computador.", "ou feche esta aba"),
    # So quem e (o vinculo do PAVLVS, destravar): nenhuma permissao pedida.
    "entrou": ("LOGIN RECEBIDO", "ok", "Login recebido.",
               "O PAVLVS confere a sua conta em alguns segundos e segue de onde você estava.",
               "Já pode fechar esta aba.", "ou feche esta aba"),
    "negado": ("NÃO CONECTADO", "aviso", "A conexão não foi autorizada.",
               "As permissões não foram aceitas no %%PROVEDOR%%. Volte ao PAVLVS para tentar de novo.",
               "Nada foi alterado.", ""),
    "expirado": ("LINK EXPIRADO", "erro", "Este login expirou.",
                 "O link vale uma única vez, só para o login que o PAVLVS abriu, e por poucos minutos. Volte ao PAVLVS para abrir outro.",
                 "Nada foi alterado.", ""),
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
    painel = ""
    if estado == "sucesso":
        painel = ('<div class="bloco conta-bloco"><span class="etiqueta">CONTA</span>'
                  f'<div class="conta"><span class="marca">{marca}</span><span class="email" id="email">conferindo a conta…</span>'
                  '<span class="selo" id="selo"><i></i><span id="selo-texto">recebido</span></span></div>'
                  '<p class="falha" id="falha" hidden></p></div>')
        if perms:
            painel += ('<div class="linhas"><span class="etiqueta">O QUE VOCÊ AUTORIZOU</span>' + "".join(
                f'<div class="linha"><span class="servico">{MARCAS.get(icone, "")}{esc(nome)}</span><span class="d">{esc(desc)}</span></div>'
                for icone, nome, desc in perms) + "</div>")
    elif detalhe:
        painel = f'<div class="bloco"><span class="etiqueta">DETALHE</span><span class="detalhe">{esc(detalhe)}</span></div>'
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
            .replace("%%PE%%", '<p class="forte">O andamento fica em Configurações › Conexões.</p>' if perms else "")
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
[data-tema="claro"]{--bg:#fff;--ink:#171716;--ink2:#5c5c59;--ink3:#8a8a86;--line:rgba(23,23,22,.1);--line2:rgba(23,23,22,.22);--fill:#f1f1ee;
--btn:#171716;--btnt:#f6f6f4;--ok:#2f6b42;--aviso:#8a5a12;--erro:#a3322b;color-scheme:light}
[data-tema="escuro"]{--bg:#111110;--ink:#f6f6f4;--ink2:#b5b5b0;--ink3:#8a8a86;--line:rgba(255,255,255,.12);--line2:rgba(255,255,255,.26);--fill:#242422;
--btn:#f6f6f4;--btnt:#171716;--ok:#8fd0a3;--aviso:#e8c283;--erro:#f0a19c;color-scheme:dark}
*{box-sizing:border-box}html,body{margin:0;min-height:100%}
body{min-height:100vh;display:flex;flex-direction:column;background:var(--bg);color:var(--ink);font:15px/1.6 'Manrope',system-ui,sans-serif;
-webkit-font-smoothing:antialiased}
.mono{font-family:'Fira Code',ui-monospace,monospace}
header{padding:10px clamp(20px,5vw,88px);min-height:64px;display:flex;align-items:center;justify-content:space-between;gap:12px 24px;border-bottom:1px solid var(--line)}
.pavlvs{font:500 24px/1 'EB Garamond',Georgia,serif;letter-spacing:.14em}
.topo{display:flex;align-items:center;gap:18px}.porta{font:12px 'Fira Code',ui-monospace,monospace;color:var(--ink3)}
.tema{width:36px;height:36px;padding:0;border:0;background:none;color:var(--ink2);cursor:pointer;display:flex;align-items:center;justify-content:center}
.tema:hover{color:var(--ink)}.tema:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.tema svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:1.5;stroke-linecap:round}
[data-tema="escuro"] .tema .lua,[data-tema="claro"] .tema .sol{display:none}
main{flex:1;width:100%;max-width:1280px;margin:0 auto;padding:clamp(56px,9vw,120px) clamp(20px,5vw,48px);display:flex;flex-wrap:wrap;
gap:48px clamp(48px,8vw,112px);align-items:start}
.texto{flex:1 1 380px;min-width:0;display:grid;gap:20px}
.estado{display:flex;align-items:center;gap:8px;font:400 11px 'Fira Code',ui-monospace,monospace;letter-spacing:.16em;color:var(--%%TOM%%)}
.estado i{display:block;width:6px;height:6px;border-radius:50%;background:currentColor}
h1{margin:0;font:400 clamp(44px,6vw,68px)/1 'EB Garamond',Georgia,serif;letter-spacing:-.02em;text-wrap:balance}
.texto p{margin:0;font-size:clamp(17px,1.8vw,19px);line-height:1.6;color:var(--ink2);text-wrap:pretty;max-width:460px}
.nota{font:italic 400 19px 'EB Garamond',Georgia,serif;color:var(--ink3)}
.painel{flex:1 1 360px;min-width:0;max-width:520px;border-left:1px solid var(--line);padding-left:clamp(24px,3vw,40px);display:grid;gap:48px}
.bloco{display:grid;gap:8px}
.etiqueta{font:400 11px 'Fira Code',ui-monospace,monospace;letter-spacing:.14em;color:var(--ink3)}
.conta-bloco{padding-bottom:20px;border-bottom:1px solid var(--line)}
.conta{display:flex;align-items:center;gap:12px}
.marca{display:flex;flex:none}.marca svg{width:18px;height:18px}
.email{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:16px}
.selo{display:flex;align-items:center;gap:6px;flex:none;font-size:12.5px;color:var(--ink3);white-space:nowrap}
.selo i{display:block;width:6px;height:6px;border-radius:50%;background:currentColor}
.selo.ok{color:var(--ok)}.selo.erro{color:var(--erro)}
.falha{margin:0;font-size:13.5px;color:var(--erro)}
.linhas{display:grid;gap:2px}.linhas .etiqueta{padding-bottom:10px}
.linha{display:grid;grid-template-columns:160px minmax(0,1fr);gap:12px;padding:16px 0;border-bottom:1px solid var(--line);font-size:14px}
.servico{display:inline-flex;align-items:center;gap:8px}.servico svg{width:16px;height:16px;flex:none}
.linha .d{color:var(--ink2)}
.detalhe{font:13.5px 'Fira Code',ui-monospace,monospace;color:var(--ink2);word-break:break-all;padding-bottom:14px;border-bottom:1px solid var(--line)}
.acoes{display:flex;align-items:center;gap:20px;flex-wrap:wrap}
.voltar{height:36px;padding:0 16px;border-radius:999px;border:0;background:var(--btn);color:var(--btnt);font:600 13.5px 'Manrope',system-ui,sans-serif;
cursor:pointer;display:inline-flex;align-items:center;gap:6px}
.voltar:hover{opacity:.88}.voltar:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.voltar svg{width:16px;height:16px;fill:currentColor}
.dica{font-size:12.5px;color:var(--ink3)}
footer{border-top:1px solid var(--line);padding:24px clamp(20px,5vw,88px);display:flex;flex-wrap:wrap;justify-content:space-between;gap:12px 48px}
footer p{margin:0;max-width:520px;font-size:13px;line-height:1.65;color:var(--ink3);text-wrap:pretty}
footer p.forte{color:var(--ink2)}
@media (max-width:760px){.painel{border-left:0;padding-left:0;max-width:none}main{padding-top:40px}}
</style>
</head>
<body>
<header><span class="pavlvs">PAVLVS</span><div class="topo"><span class="porta">127.0.0.1:%%PORTA%%</span>
<button type="button" class="tema" id="tema" aria-label="Alternar tema" title="Alternar claro/escuro"><span class="sol">%%SOL%%</span><span class="lua">%%LUA%%</span></button></div></header>
<main>
<section class="texto">
<span class="estado"><i></i><span id="rotulo">%%ROTULO%%</span></span>
<h1>%%TITULO%%</h1>
<p id="texto">%%TEXTO%%</p>
<span class="nota">%%NOTA%%</span>
</section>
<section class="painel">
%%PAINEL%%
<div class="acoes"><button type="button" class="voltar" id="voltar">Voltar ao PAVLVS</button><span class="dica">%%DICA%%</span></div>
</section>
</main>
<footer>%%PE%%<p>Esta página é servida pelo próprio PAVLVS, neste computador.</p></footer>
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
      var selo = document.getElementById("selo"), texto = document.getElementById("selo-texto"), email = document.getElementById("email");
      if (d.email) email.textContent = d.email;
      if (d.fase === "pronto") { texto.textContent = "conectado"; selo.className = "selo ok"; return; }
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
