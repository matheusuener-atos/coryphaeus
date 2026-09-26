/* ------------------------------------------------ e-mail: configuracoes */
/*
   A visao "ajustes" do E-mail: como a mensagem aberta aparece e a
   assinatura de cada conta. Comeca simples, de proposito:

     cor         acompanhar o PAULUS, sempre claro ou sempre escuro - os
                 mesmos cartoes do Tema em Configuracoes › Aparencia
     imagens     mostrar as imagens de fora sem pedir, ou bloquear ate o
                 "mostrar" de cada mensagem (o padrao)
     so texto    abrir as mensagens no texto puro
     assinatura  o rodape da conta, com formatacao e imagem pequena, na
                 mesma faixa de edicao do Escrever (js/33-email-editor.js)

   As tres primeiras ficam nesta maquina (localStorage, como o tema). A
   assinatura vai para a conta, pela rota de sempre (/api/email/contas), e
   o servidor a poe no fim de cada envio, depois do "--".
   js/29-email-caixa.js le emailPrefs() ao abrir cada mensagem.
*/

const EMAIL_PREFS_PADRAO = { tema: "auto", imagens: false, soTexto: false };

function emailPrefs() {
  try {
    const salvo = JSON.parse(localStorage.getItem("paulus.email.prefs") || "{}");
    const p = Object.assign({}, EMAIL_PREFS_PADRAO, salvo);
    if (!["auto", "claro", "escuro"].includes(p.tema)) p.tema = "auto";
    p.imagens = !!p.imagens;
    p.soTexto = !!p.soTexto;
    return p;
  } catch (err) {
    return Object.assign({}, EMAIL_PREFS_PADRAO);
  }
}

function guardarEmailPrefs(mudanca) {
  const p = Object.assign(emailPrefs(), mudanca);
  try { localStorage.setItem("paulus.email.prefs", JSON.stringify(p)); } catch (err) { /* sem memoria: vale ate fechar */ }
  return p;
}

// `assinatura` e o HTML que esta no campo; `base`, o de quando abriu.
const ej = { contaId: "", assinatura: null, base: null, mudou: false, salvando: false };

function ejConta() {
  const contas = mail.contas.contas;
  return contas.find((c) => c.id === ej.contaId) || mail.conta || contas[0] || null;
}

function ejCartaoCor(p) {
  const tema = (id, rotulo) => {
    const classe = "cfg-tema " + id + (id === p.tema ? " on" : "");
    return '<button class="' + classe + '" data-ej-tema="' + id + '"><span><img src="/img/paulus-logo.svg" alt=""></span><span>' + rotulo + "</span></button>";
  };
  const explica = {
    auto: "Ao alternar o PAULUS entre claro e escuro, o e-mail aberto troca junto. Se o remetente fez uma versão escura, ela é usada; se não fez, o PAULUS escurece as cores do texto e do fundo e deixa as imagens como vieram.",
    claro: "O e-mail abre sempre claro, como o remetente desenhou, mesmo com o PAULUS no escuro.",
    escuro: "O e-mail abre sempre escuro, mesmo com o PAULUS no claro. Se o remetente fez uma versão escura, ela é usada; se não fez, o PAULUS escurece as cores e deixa as imagens como vieram.",
  };
  const corpo = '<div class="ag-campo"><label>Cor das mensagens</label><div class="cfg-temas">' +
    tema("auto", "Acompanhar o PAULUS") + tema("claro", "Sempre claro") + tema("escuro", "Sempre escuro") + "</div>" +
    '<span class="cfg-explica">' + explica[p.tema] + "</span></div>" +
    '<div class="cfg-sub">' +
    ligaCfg("soTexto", "Abrir só o texto", "sem a formatação do remetente; dá para ver formatado em cada mensagem", p.soTexto) + "</div>";
  return cartaoCfg("Ao abrir uma mensagem", metaCfg("fica nesta máquina"), corpo);
}

function ejCartaoImagens(p) {
  const corpo = '<div class="cfg-sub ej-primeiro">' +
    ligaCfg("imagens", "Mostrar imagens automaticamente", "sem clicar em “mostrar” em cada mensagem", p.imagens) + "</div>" +
    '<p class="cfg-explica">' + (p.imagens
      ? "Ligado: as imagens de fora carregam ao abrir. Quem enviou pode saber que você abriu, quando e de qual endereço de internet."
      : "Desligado: as imagens de fora ficam bloqueadas até você clicar em “mostrar”, e o remetente não fica sabendo que você abriu. As imagens que vêm dentro da mensagem aparecem sempre.") + "</p>";
  return cartaoCfg("Imagens", metaCfg(p.imagens ? "carregam sozinhas" : "bloqueadas até pedir"), corpo);
}

/* A assinatura como estava gravada, em HTML: a formatada, ou a de texto
   puro das contas antigas. */
function ejInicial(c) {
  return c.assinatura_html || (c.assinatura ? erTextoParaHtml(c.assinatura) : "");
}

function ejCartaoAssinatura() {
  const contas = mail.contas.contas;
  const c = ejConta();
  if (!c) {
    return cartaoCfg("Assinatura", "", '<p class="cfg-explica">Conecte uma conta em Contas para escrever a assinatura dela.</p>');
  }
  if (ej.assinatura === null || ej.assinaturaDe !== c.id) { ej.assinatura = ejInicial(c); ej.assinaturaDe = c.id; ej.base = null; ej.mudou = false; }
  const escolha = contas.length > 1
    ? '<div class="ag-campo"><label>Conta</label><select id="ej-conta">' + contas.map((x) =>
      '<option value="' + esc(x.id) + '"' + (x.id === c.id ? " selected" : "") + ">" + esc(x.email) + "</option>").join("") + "</select></div>"
    : "";
  // O HTML da assinatura ja vem limpo do servidor (correio.limpar_assinatura).
  const corpo = escolha +
    '<div class="ag-campo"><label>Assinatura' + (contas.length > 1 ? "" : " · " + esc(c.email)) + "</label>" +
    editorRico({ id: "ej-assinatura", html: ej.assinatura, placeholder: "Nome · OAB/UF 00000", imagem: true, classe: "ej-er" }) + "</div>" +
    '<p class="cfg-explica">Vai no fim de cada e-mail enviado por esta conta, com a formatação e a imagem. A imagem é reduzida nesta máquina (até 150 KB) e vai dentro do e-mail. Em branco, o e-mail sai sem assinatura.</p>' +
    '<div class="cfg-botoes"><button class="primario com-icone" id="ej-salvar"' + (ej.mudou && !ej.salvando ? "" : " disabled") + ">" +
    ic("check", 16) + (ej.salvando ? "Salvando…" : "Salvar assinatura") + "</button>" +
    (ej.mudou ? '<button id="ej-desfazer">Desfazer</button>' : "") + "</div>";
  return cartaoCfg("Assinatura", metaCfg(c.assinatura || c.assinatura_html ? "em uso" : "sem assinatura"), corpo);
}

function desenharAjustesDoEmail() {
  cabecalhoEmail();
  const p = emailPrefs();
  $("centro").innerHTML = '<div class="acervo sem-painel ej-tela" id="email"><div class="acervo-principal sv-principal"><div class="ej-palco">' +
    // Um cartao embaixo do outro, na ordem de uso: como abre, imagens, assinatura.
    '<div class="cfg-grade larga">' + ejCartaoCor(p) + ejCartaoImagens(p) + ejCartaoAssinatura() + "</div>" +
    "</div></div></div>";
  ligarEmail();
}

/* Redesenha sem perder o lugar da rolagem nem o texto que esta sendo
   digitado na assinatura. */
function redesenharAjustes() {
  const rolagem = document.querySelector("#email .sv-principal");
  const topo = rolagem ? rolagem.scrollTop : 0;
  desenharAjustesDoEmail();
  const nova = document.querySelector("#email .sv-principal");
  if (nova) nova.scrollTop = topo;
}

function ligarAjustesDoEmail() {
  const raiz = $("email");
  if (!raiz) return;
  raiz.querySelectorAll("[data-ej-tema]").forEach((b) => {
    b.onclick = () => { guardarEmailPrefs({ tema: b.dataset.ejTema }); redesenharAjustes(); };
  });
  raiz.querySelectorAll("[data-cfg-liga]").forEach((b) => {
    b.onclick = () => {
      const chave = b.dataset.cfgLiga;
      guardarEmailPrefs({ [chave]: !emailPrefs()[chave] });
      if (chave === "soTexto") cx.soTexto = undefined;
      redesenharAjustes();
    };
  });
  const conta = $("ej-conta");
  if (conta) {
    if (typeof melhorarSelect === "function") melhorarSelect(conta);
    conta.onchange = () => { ej.contaId = conta.value; ej.assinatura = null; redesenharAjustes(); };
  }
  // A mesma faixa de edicao do Escrever, com o botao de imagem.
  const texto = ligarEditorRico("ej-assinatura", () => {
    ej.assinatura = texto.html;
    const mudou = texto.html !== ej.base;
    if (mudou === ej.mudou) return;
    ej.mudou = mudou;
    const salvar = $("ej-salvar");
    if (salvar) salvar.disabled = !mudou || ej.salvando;
    const desfazer = $("ej-desfazer");
    if (mudou && !desfazer && salvar) {
      salvar.insertAdjacentHTML("afterend", '<button id="ej-desfazer">Desfazer</button>');
      $("ej-desfazer").onclick = desfazerAssinatura;
    } else if (!mudou && desfazer) desfazer.remove();
  });
  // A base e o HTML como o navegador o escreve, para comparar igual com igual.
  if (texto && ej.base === null) ej.base = texto.html;
  const desfazer = $("ej-desfazer");
  if (desfazer) desfazer.onclick = desfazerAssinatura;
  const salvar = $("ej-salvar");
  if (salvar) salvar.onclick = salvarAssinaturaDoEmail;
}

function desfazerAssinatura() {
  ej.assinatura = null;
  redesenharAjustes();
}

async function salvarAssinaturaDoEmail() {
  const c = ejConta();
  if (!c || ej.salvando) return;
  const vazia = !ej.assinatura;
  ej.salvando = true;
  redesenharAjustes();
  let r;
  try {
    r = await fetch("/api/email/contas", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dados: { id: c.id, email: c.email, assinatura_html: ej.assinatura } }),
    });
  } catch (err) { r = null; }
  ej.salvando = false;
  if (!r || !r.ok) {
    avisoCert(r ? await erroDe(r) : "não consegui salvar a assinatura", { tom: "erro" });
    redesenharAjustes();
    return;
  }
  mail.contas = await r.json();
  const nova = mail.contas.contas.find((x) => x.id === c.id);
  if (mail.conta && nova && mail.conta.id === nova.id) mail.conta = nova;
  ej.assinatura = null;
  avisoCert(vazia ? "assinatura removida" : "assinatura salva", { tom: "ok" });
  redesenharAjustes();
}

(function () {
  const desenharAntes = desenharEmail;
  window.desenharEmail = function () {
    if (mail.visao !== "ajustes") return desenharAntes();
    desenharAjustesDoEmail();
  };
})();
