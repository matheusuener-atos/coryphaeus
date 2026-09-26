/* ------------------------------------------ e-mail: entrar com o provedor */
/*
   Os botoes "Entrar com Google" e "Entrar com Microsoft" (src/correio_oauth.py).
   O login acontece no navegador padrao, na pagina do proprio provedor; o
   PAULUS so recebe a autorizacao de volta, num endereco 127.0.0.1 desta
   maquina. Os IDs do aplicativo vem no codigo (src/oauth_app.py), iguais em
   toda instalacao: provedor sem ID simplesmente nao aparece - quem usa o
   programa nao tem nada para configurar.

   Tres entradas para quem desenha a tela de contas:
     botoesDeLoginOAuth()            o HTML dos botoes (com a explicacao)
     ligarLoginOAuth(raiz, aoLigar)  liga os cliques; aoLigar(conta) no fim
     entrarDeNovoOAuth(conta, aoLigar)  refaz o login de uma conta vencida
*/

const eo = { relogio: null, versao: 0 };
const EO_ROTULO = { google: "Google", microsoft: "Microsoft" };

function eoInfo() {
  return (typeof mail !== "undefined" && mail.contas && mail.contas.oauth) || null;
}

/* O simbolo de cada provedor, como as diretrizes de "Entrar com" deles pedem:
   o G de quatro cores do Google e os quatro quadrados da Microsoft. Desenhados
   aqui em SVG - nada e baixado da internet. As cores sao as da marca, e nao
   do tema, de proposito: o simbolo nao muda com o claro/escuro. */
const EO_SIMBOLO = {
  google: '<svg class="eo-simbolo" viewBox="0 0 48 48" aria-hidden="true">' +
    '<path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>' +
    '<path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>' +
    '<path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>' +
    '<path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>',
  microsoft: '<svg class="eo-simbolo" viewBox="0 0 21 21" aria-hidden="true">' +
    '<rect x="1" y="1" width="9" height="9" fill="#F25022"/><rect x="11" y="1" width="9" height="9" fill="#7FBA00"/>' +
    '<rect x="1" y="11" width="9" height="9" fill="#00A4EF"/><rect x="11" y="11" width="9" height="9" fill="#FFB900"/></svg>',
};

function eoMarca(p) {
  return EO_SIMBOLO[p] || "";
}

function botoesDeLoginOAuth(info) {
  const o = info || eoInfo();
  if (!o) return "";
  const prontos = ["google", "microsoft"].filter((p) => Boolean(o[p] && o[p].configurado));
  if (!prontos.length) return "";
  return '<div class="eo-login"><div class="eo-botoes">' + prontos.map((p) => '<button class="eo-botao" data-eo-entrar="' + p + '">' +
    eoMarca(p) + "<span>Entrar com " + EO_ROTULO[p] + "</span></button>").join("") + "</div></div>";
}

function ligarLoginOAuth(raiz, aoLigar) {
  if (!raiz) return;
  raiz.querySelectorAll("[data-eo-entrar]").forEach((b) => {
    b.onclick = () => {
      const campo = raiz.querySelector('input[type="email"], #mail-endereco');
      const dica = campo && campo.value.includes("@") ? campo.value.trim() : "";
      eoComecar(b.dataset.eoEntrar, raiz, aoLigar, dica);
    };
  });
}

/* Refaz o login de uma conta que venceu: o mesmo provedor, o mesmo endereco. */
function entrarDeNovoOAuth(conta, aoLigar) {
  const raiz = document.querySelector(".ec-cartao") || $("email");
  if (!raiz || !conta) return;
  const p = conta.autenticacao;
  const o = eoInfo() || {};
  const pronto = Boolean(o[p] && o[p].configurado);
  const motivo = conta.precisa_entrar
    ? "A autorização do " + EO_ROTULO[p] + " para esta conta venceu ou foi revogada. Entre de novo na página do " + EO_ROTULO[p] + "."
    : "Entre de novo na página do " + EO_ROTULO[p] + " para renovar a autorização desta conta.";
  const marca = raiz.querySelector(".ec-marca");
  raiz.innerHTML = (marca ? marca.outerHTML : "") + '<div class="eo-denovo"><h2>Entrar de novo</h2><p class="eo-sub">' + esc(conta.email) + " · login " + EO_ROTULO[p] + "</p>" +
    '<p class="eo-texto">' + esc(motivo) + "</p>" +
    '<div class="eo-login"><div class="eo-botoes">' +
    '<button class="eo-botao" data-eo-entrar="' + p + '"' + (pronto ? "" : " disabled") + ">" + eoMarca(p) + "<span>Entrar com " + EO_ROTULO[p] + "</span></button></div>" +
    (pronto ? "" : '<p class="eo-explica">' + ic("info", 15) + "<span>Esta versão do PAULUS não traz o login do " + EO_ROTULO[p] + ".</span></p>") +
    '</div><div class="eo-rodape"><button data-eo-voltar="1">Voltar</button></div></div>';
  raiz.querySelector("[data-eo-voltar]").onclick = () => {
    eoParar();
    fetch("/api/email/oauth/cancelar", { method: "POST" }).catch(() => {});
    desenharEmail();
  };
  raiz.querySelector("[data-eo-entrar]").onclick = () => eoComecar(p, raiz, aoLigar, conta.email);
  if (pronto) eoComecar(p, raiz, aoLigar, conta.email);
}

function eoParar() {
  eo.versao += 1;
  if (eo.relogio) { clearTimeout(eo.relogio); eo.relogio = null; }
}

/* O lugar onde o andamento aparece: no lugar dos botoes. */
function eoCaixa(raiz) {
  return raiz.querySelector(".eo-login");
}

function eoMostrar(raiz, html) {
  const caixa = eoCaixa(raiz);
  if (caixa) caixa.innerHTML = html;
}

function eoRestaurar(raiz, aoLigar, mensagem) {
  const caixa = eoCaixa(raiz);
  if (!caixa) return;
  const tmp = document.createElement("div");
  tmp.innerHTML = botoesDeLoginOAuth();
  const novo = tmp.querySelector(".eo-login");
  caixa.innerHTML = (mensagem ? '<p class="eo-erro">' + ic("error", 16) + "<span>" + esc(mensagem) + "</span></p>" : "") +
    (novo ? novo.innerHTML : "");
  ligarLoginOAuth(raiz, aoLigar);
}

async function eoComecar(p, raiz, aoLigar, dica) {
  eoParar();
  const versao = eo.versao;
  eoMostrar(raiz, '<div class="eo-espera"><p class="eo-titulo">' + ic("open_in_new", 18) + "<span>Abrindo o navegador…</span></p></div>");
  let r;
  try {
    r = await fetch("/api/email/oauth/entrar", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ provedor: p, email: dica || "" }),
    });
  } catch (err) {
    return eoRestaurar(raiz, aoLigar, String(err));
  }
  if (versao !== eo.versao) return;
  if (!r.ok) return eoRestaurar(raiz, aoLigar, maiuscula(await erroDe(r)));
  const d = await r.json();
  eoDesenharEspera(raiz, aoLigar, d);
  eoAcompanhar(raiz, aoLigar, versao);
}

function eoDesenharEspera(raiz, aoLigar, d) {
  const rotulo = d.rotulo || EO_ROTULO[d.provedor] || "";
  const minutos = Math.max(1, Math.round((d.prazo_s || 300) / 60));
  let titulo = "Abrimos o navegador — entre na sua conta " + rotulo + " lá e volte aqui.";
  let sub = "O login acontece na página do próprio " + rotulo + ". Espero até " + minutos + " min.";
  if (d.fase === "trocando" || d.fase === "testando") {
    titulo = "Recebi o login. Conferindo a conexão com o servidor de e-mail…";
    sub = "Leva alguns segundos.";
  }
  const semNavegador = d.fase === "aguardando" && d.url && !d.abriu_navegador;
  eoMostrar(raiz, '<div class="eo-espera" aria-live="polite"><p class="eo-titulo">' + ic("open_in_new", 18) + "<span>" + esc(titulo) + "</span></p>" +
    '<p class="eo-sub">' + esc(sub) + "</p>" +
    (semNavegador ? '<p class="eo-sub">Não consegui abrir o navegador. Copie o endereço e abra nele: <button class="eo-ligacao" data-eo-copiar="1">copiar endereço</button></p>' : "") +
    '<div class="eo-rodape"><button data-eo-cancelar="1">Cancelar</button></div></div>');
  const copiar = raiz.querySelector("[data-eo-copiar]");
  if (copiar) copiar.onclick = async () => {
    try { await navigator.clipboard.writeText(d.url); avisoCert("endereço copiado"); } catch (err) { avisoCert("não consegui copiar"); }
  };
  raiz.querySelector("[data-eo-cancelar]").onclick = async () => {
    eoParar();
    try { await fetch("/api/email/oauth/cancelar", { method: "POST" }); } catch (err) { /* o prazo encerra do outro lado */ }
    eoRestaurar(raiz, aoLigar, "");
  };
}

function eoAcompanhar(raiz, aoLigar, versao) {
  eo.relogio = setTimeout(async () => {
    if (versao !== eo.versao) return;
    if (!document.body.contains(raiz)) { eoParar(); return; }
    let d;
    try {
      d = await (await fetch("/api/email/oauth/andamento")).json();
    } catch (err) {
      d = null;
    }
    if (versao !== eo.versao) return;
    if (!d || d.fase === "aguardando" || d.fase === "trocando" || d.fase === "testando" || d.fase === "preparando") {
      if (d && d.fase !== "aguardando") eoDesenharEspera(raiz, aoLigar, d);
      return eoAcompanhar(raiz, aoLigar, versao);
    }
    eo.relogio = null;
    if (d.fase === "pronto") return eoPronto(raiz, aoLigar, d);
    if (d.fase === "cancelado") return eoRestaurar(raiz, aoLigar, "");
    eoRestaurar(raiz, aoLigar, maiuscula(d.mensagem || "o login não terminou"));
  }, 1200);
}

function eoPronto(raiz, aoLigar, d) {
  if (d.contas && typeof mail !== "undefined") mail.contas = Object.assign({}, mail.contas || {}, d.contas);
  const res = d.resultado || {};
  const conta = res.conta || null;
  const prova = res.prova || {};
  if (prova.entrada && prova.saida) return aoLigar && aoLigar(conta);
  /* Entrou, mas uma das pontas nao funcionou: diz qual, antes de seguir. */
  const linha = (ok, texto, erro) => '<div class="em-conferencia ' + (ok ? "ok" : "aviso") + '">' + ic(ok ? "check_circle" : "error", 18) +
    "<span>" + texto + (ok ? " funciona" : ": " + esc(erro || "não")) + "</span></div>";
  eoMostrar(raiz, '<div class="eo-espera"><p class="eo-titulo">' + ic("check_circle", 18) + "<span>Login feito" + (conta ? " · " + esc(conta.email) : "") + "</span></p>" +
    '<div class="em-conferencias">' + linha(prova.entrada, "Ler as mensagens (IMAP)", prova.erro_entrada) + linha(prova.saida, "Enviar (SMTP)", prova.erro_saida) + "</div>" +
    '<div class="eo-rodape"><button class="primario" data-eo-seguir="1">Continuar</button></div></div>');
  raiz.querySelector("[data-eo-seguir]").onclick = () => aoLigar && aoLigar(conta);
}
