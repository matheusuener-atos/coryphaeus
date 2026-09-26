/* ------------------------------------------ e-mail: entrar com o provedor */
/*
   Os botoes "Entrar com Google" e "Entrar com Microsoft" (src/correio_oauth.py).
   O login acontece no navegador padrao, na pagina do proprio provedor; o
   PAULUS so recebe a autorizacao de volta, num endereco 127.0.0.1 desta
   maquina. Os IDs do aplicativo vem no codigo (src/oauth_app.py), iguais em
   toda instalacao: provedor sem ID simplesmente nao aparece - quem usa o
   programa nao tem nada para configurar.

   Tres entradas para quem desenha a tela de contas:
     botoesDeLoginOAuth()            o HTML dos botoes
     ligarLoginOAuth(raiz, aoLigar)  liga os cliques; aoLigar(conta) no fim
     entrarDeNovoOAuth(conta, aoLigar)  refaz o login de uma conta vencida

   A espera e discreta: o botao vira "aguardando o navegador" com um giro e
   um "cancelar". So se passar de EO_ESPERA_LONGA sem voltar (ou se o
   navegador nem abriu) aparece a linha com "reabrir o navegador" e "copiar
   o endereco". Leitura e envio funcionando, vai direto para a caixa; se uma
   das pontas falhar, diz qual numa linha, com a acao que resolve.
*/

const eo = { relogio: null, versao: 0, inicio: 0, url: "", botoes: "", desenho: "" };
const EO_ROTULO = { google: "Google", microsoft: "Microsoft" };
const EO_ESPERA_LONGA = 45000;

function eoInfo() {
  return (typeof mail !== "undefined" && mail.contas && mail.contas.oauth) || null;
}

/* Os provedores com login neste PAULUS, na ordem em que aparecem. */
function provedoresOAuth(info) {
  const o = info || eoInfo();
  if (!o) return [];
  return ["google", "microsoft"].filter((p) => Boolean(o[p] && o[p].configurado));
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

/* Os botoes de entrar sao todos contornados; `principal` ficou de antes. */
function eoBotao(p, desligado, principal) {
  return '<button class="eo-botao" data-eo-entrar="' + p + '"' + (desligado ? " disabled" : "") + ">" + eoMarca(p) + "<span>Entrar com " + EO_ROTULO[p] + "</span></button>";
}

function botoesDeLoginOAuth(info) {
  const prontos = provedoresOAuth(info);
  if (!prontos.length) return "";
  return '<div class="eo-login"><div class="eo-botoes">' + prontos.map((p, i) => eoBotao(p, false, i === 0)).join("") + "</div></div>";
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

/* Refaz o login de uma conta que venceu: o mesmo provedor, o mesmo endereco.
   Comeca sozinho - quem clicou na conta ja disse que quer entrar. */
function entrarDeNovoOAuth(conta, aoLigar) {
  const raiz = document.querySelector(".ec-cartao") || $("email");
  if (!raiz || !conta) return;
  const p = conta.autenticacao;
  const pronto = provedoresOAuth().includes(p);
  raiz.innerHTML = '<div class="eo-denovo">' +
    '<button class="ec-quem" data-eo-voltar="1" title="Voltar">' + ic("arrow_back", 16) + avatarDaConta({ email: conta.email }) + "<span>" + esc(conta.email) + "</span></button>" +
    "<h2>Entrar de novo</h2>" +
    (conta.precisa_entrar ? '<p class="eo-texto">A autorização do ' + EO_ROTULO[p] + " venceu.</p>" : "") +
    '<div class="eo-login"><div class="eo-botoes">' + eoBotao(p, !pronto, true) + "</div>" +
    (pronto ? "" : '<p class="eo-explica">' + ic("info", 15) + "<span>Esta versão do PAULUS não traz o login do " + EO_ROTULO[p] + ".</span></p>") +
    "</div></div>";
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

/* Os botoes voltam como estavam antes do clique, com o motivo em cima. */
function eoRestaurar(raiz, aoLigar, mensagem) {
  const caixa = eoCaixa(raiz);
  if (!caixa) return;
  caixa.innerHTML = (mensagem ? '<p class="eo-erro">' + ic("error", 16) + "<span>" + esc(mensagem) + "</span></p>" : "") + eo.botoes;
  ligarLoginOAuth(raiz, aoLigar);
  const denovo = raiz.querySelector(".eo-denovo [data-eo-entrar]");
  if (denovo) {
    const conta = raiz.querySelector(".ec-quem span:last-child");
    denovo.onclick = () => eoComecar(denovo.dataset.eoEntrar, raiz, aoLigar, conta ? conta.textContent : "");
  }
}

async function eoComecar(p, raiz, aoLigar, dica) {
  eoParar();
  const versao = eo.versao;
  const caixa = eoCaixa(raiz);
  if (caixa && !caixa.querySelector(".eo-espera")) eo.botoes = caixa.innerHTML.replace(/<p class="eo-erro">[\s\S]*?<\/p>/, "");
  Object.assign(eo, { inicio: Date.now(), url: "", desenho: "" });
  eoDesenharEspera(raiz, aoLigar, { fase: "aguardando", abriu_navegador: true });
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

/* A espera: so o giro e o cancelar. A linha de socorro so aparece quando o
   navegador nao abriu ou a volta demora. Redesenha so quando muda algo, para
   o giro nao recomecar a cada consulta. */
function eoDesenharEspera(raiz, aoLigar, d) {
  if (d.url) eo.url = d.url;
  const conferindo = d.fase === "trocando" || d.fase === "testando";
  const travou = !conferindo && Boolean(eo.url) && (d.abriu_navegador === false || Date.now() - eo.inicio > EO_ESPERA_LONGA);
  const desenho = (conferindo ? "c" : "a") + (travou ? "t" : "");
  if (desenho === eo.desenho && eoCaixa(raiz) && eoCaixa(raiz).querySelector(".eo-espera")) return;
  eo.desenho = desenho;
  eoMostrar(raiz, '<div class="eo-espera" aria-live="polite"><div class="eo-aguardo"><span class="eo-giro" aria-hidden="true"></span><span>' +
    (conferindo ? "conferindo a conexão…" : "aguardando o navegador…") + "</span>" +
    '<button class="eo-ligacao" data-eo-cancelar="1">cancelar</button></div>' +
    (travou ? '<p class="eo-travou">' + (d.abriu_navegador === false ? "O navegador não abriu." : "Não voltou?") +
      ' <button class="eo-ligacao" data-eo-reabrir="1">reabrir o navegador</button> · <button class="eo-ligacao" data-eo-copiar="1">copiar o endereço</button></p>' : "") +
    "</div>");
  const cancelar = raiz.querySelector("[data-eo-cancelar]");
  if (cancelar) cancelar.onclick = async () => {
    eoParar();
    try { await fetch("/api/email/oauth/cancelar", { method: "POST" }); } catch (err) { /* o prazo encerra do outro lado */ }
    eoRestaurar(raiz, aoLigar, "");
  };
  const copiar = raiz.querySelector("[data-eo-copiar]");
  if (copiar) copiar.onclick = async () => {
    try { await navigator.clipboard.writeText(eo.url); avisoCert("endereço copiado · cole no navegador"); } catch (err) { avisoCert("não consegui copiar"); }
  };
  const reabrir = raiz.querySelector("[data-eo-reabrir]");
  if (reabrir) reabrir.onclick = async () => {
    let r = null;
    try { r = await (await fetch("/api/email/oauth/reabrir", { method: "POST" })).json(); } catch (err) { /* abaixo */ }
    if (!r || !r.abriu_navegador) avisoCert("não consegui abrir o navegador · copie o endereço");
  };
}

function eoAcompanhar(raiz, aoLigar, versao) {
  eo.relogio = setTimeout(async () => {
    if (versao !== eo.versao) return;
    /* A pessoa saiu da tela no meio: o login que ficou esperando e cancelado. */
    if (!document.body.contains(raiz)) {
      eoParar();
      fetch("/api/email/oauth/cancelar", { method: "POST" }).catch(() => {});
      return;
    }
    let d;
    try {
      d = await (await fetch("/api/email/oauth/andamento")).json();
    } catch (err) {
      d = null;
    }
    if (versao !== eo.versao) return;
    if (!d || d.fase === "aguardando" || d.fase === "trocando" || d.fase === "testando" || d.fase === "preparando") {
      eoDesenharEspera(raiz, aoLigar, d || { fase: "aguardando" });
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
  /* Sem leitura nao ha caixa: o botao volta, que e o "tentar de novo". */
  if (!prova.entrada) return eoRestaurar(raiz, aoLigar, "Entrou, mas não consegui ler as mensagens: " + (prova.erro_entrada || "o servidor recusou"));
  /* Le mas nao envia: diz isso e deixa seguir. */
  eoMostrar(raiz, '<p class="eo-erro">' + ic("error", 16) + "<span>Lê, mas não envia: " + esc(prova.erro_saida || "o servidor recusou") +
    '. <button class="eo-ligacao" data-eo-seguir="1">abrir a caixa assim mesmo</button></span></p>');
  raiz.querySelector("[data-eo-seguir]").onclick = () => aoLigar && aoLigar(conta);
}
