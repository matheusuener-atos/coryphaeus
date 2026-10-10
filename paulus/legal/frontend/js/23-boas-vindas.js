/* ---------------------------------------------------------- boas-vindas */
/*
   O assistente de configuracao, na primeira abertura: tela cheia, um caminho
   so (09/10/2026) - Boas-vindas, Sua conta (obrigatoria: Google ou conta PAVLVS
   de e-mail e senha), Assinatura (so sem plano ativo), Seus dados (so para quem
   entrou ja com assinatura), Conexoes, Acesso a distancia (ligado de fabrica;
   ou desliga, ou conecta ate o fim) e Atualizacoes. Abre por #boasvindas para
   quem quiser rever. Tudo pode ser mudado depois em Configuracoes.

   O desenho e o das secoes: o rotulo fora, acima do cartao; no cartao os
   campos, o botao e a nota; fora, os links de ir e voltar (css/08-boas-vindas.css).
   O caminho de entrar num escritorio por codigo, o modelo de IA e os modulos
   sairam do assistente: a equipe entra pelo convite do servidor, o modelo e
   escolhido em Configuracoes › Modelos e os modulos em Configuracoes › Modulos.
*/

/* O vinculo por codigo saiu (E4): um pedido que tenha ficado guardado neste
   navegador nao prende mais a casca em modo limitado. */
try { localStorage.removeItem("paulus.vinculo"); } catch (err) { /* sem memoria */ }

const bv = {
  passo: 0, status: null, prefs: null, pessoa: {},
  modulos: {}, google: null,
  escritorio: "", acesso: false,
  // A assinatura do e-mail que entrou (GET /api/assinatura): { ativa, situacao: "ativa"|"vencida"|"nenhuma", pessoa, escritorio, plano, renova_em }.
  // Sem assinatura ativa, o passo "assinatura" entra na ordem e segura o resto; o site faz o cadastro e o pagamento.
  assinatura: null, assinaturaEsperando: false, relogioAssinatura: null,
  // Depois de "edite no site": o formulario da lugar a uma linha de espera; ao voltar com dados novos, redesenha.
  dadosEsperando: false, relogioDados: null,
  // Conexoes: o que foi marcado (servicos), o que o Google ja autorizou (autorizados) e a espera pelo consentimento.
  servicos: {}, autorizados: {}, consentEsperando: false, relogioConsent: null,
};
// "modulos" saiu do assistente: o plano libera, e esconder/mostrar fica em Configuracoes › Modulos.
// O passo Assinatura so entra sem plano ativo (ordemBv): na pratica, quem entrou com o Google sem nunca ter
// assinado. Quem cria a conta no site (09/10/2026) ja sai com o plano e passa direto.
const ORDEM_CRIAR = ["boasvindas", "google", "assinatura", "dados", "conexoes", "acesso", "atualizacoes"];
const NOMES_BV = {
  boasvindas: "Boas-vindas", google: "Sua conta", assinatura: "Assinatura", dados: "Seus dados",
  conexoes: "Conexões", acesso: "Acesso à distância", atualizacoes: "Atualizações",
};

/* Os modulos do menu que podem ser desligados (preferencia `modulos`), com o
   destino de cada um na casca. O Assistente e Configuracoes ficam
   sempre. */
const MODULOS_BV = [
  // [id, icone, nome, descricao, destinos no trilho, grupo] - a mesma ordem e os mesmos grupos do trilho (Aplicacao / index.html).
  ["servicos", "work", "Serviços", "Processos, prazos e a trilha de cada caso", ["servicos"], "Dia a dia"],
  ["gravacoes", "mic", "Gravações", "Audiências e reuniões com transcrição", ["gravacoes"], "Dia a dia"],
  ["agenda", "calendar_month", "Agenda", "Compromissos, prazos e lembretes", ["calendario"], "Dia a dia"],
  ["foco", "self_improvement", "Foco e bem-estar", "Pausas e blocos de concentração", ["foco"], "Dia a dia"],
  ["acervo", "inventory_2", "Acervo", "Os arquivos do escritório, lidos pelo assistente", ["biblioteca"], "Documentos"],
  ["biblioteca", "menu_book", "Biblioteca", "Leis, súmulas e modelos de referência", ["contexto"], "Documentos"],
  ["documentos", "description", "Editor de documentos", "Peças, contratos e modelos no editor", ["editor"], "Documentos"],
  ["assinatura", "draw", "Assinatura", "Assinatura digital com certificado ICP-Brasil", ["assinar"], "Documentos"],
  ["email", "mail", "E-mail", "A caixa de entrada ligada aos serviços", ["caixa"], "Escritório"],
  ["financeiro", "payments", "Financeiro", "Honorários, custas e recebimentos", ["financeiro"], "Escritório"],
  ["cadastros", "contacts", "Cadastros", "Clientes, partes e contatos", ["cadastros"], "Escritório"],
  ["aprovacoes", "verified", "Aprovações", "O que sai do escritório passa aqui antes", ["aprovacoes"], "Escritório"],
  ["agentes", "school", "Agentes", "Rotinas que o assistente executa sozinho", ["agentes"], "Escritório"],
  ["notas", "receipt_long", "Notas fiscais", "Emissão de NFS-e dos honorários", ["notas"], "Escritório"],
];

function ordemBv() {
  const ordem = ORDEM_CRIAR;
  // O login do Google e so identidade; o Gmail, a Agenda e o Drive sao autorizados em Conexoes.
  let o = ordem;
  // Assinatura ativa: o passo nao aparece. Sem ela (ou vencida), ele segura os seguintes.
  if (bv.assinatura && bv.assinatura.ativa) o = o.filter((p) => p !== "assinatura");
  // "Seus dados" so para quem entrou ja com assinatura ativa (09/10/2026): quem criou a conta agora ou
  // assinou no site durante o assistente acabou de preencher tudo la. Os dados sao gravados sem a tela.
  if (bv.semConferirDados) o = o.filter((p) => p !== "dados");
  return o;
}

async function lerAssinatura(soLer) {
  let a;
  try {
    const r = await fetch("/api/assinatura");
    a = r.ok ? await r.json() : { ativa: false, situacao: "nenhuma" };
  } catch (err) { a = { ativa: false, situacao: "nenhuma" }; }
  if (soLer) return a;
  bv.assinatura = a;
  if (a && a.ativa) {
    if (a.pessoa) for (const k of Object.keys(a.pessoa)) if (!bv.pessoa[k]) bv.pessoa[k] = a.pessoa[k];
    if (a.escritorio && !bv.escritorio) bv.escritorio = a.escritorio;
    if (bv.assinaturaEsperando) {
      bv.assinaturaEsperando = false; pararEsperaAssinatura(); avisoCert("assinatura confirmada");
      if (bv.semConferirDados) gravarDadosDaAssinaturaBv();
    }
  }
  return a;
}

/* Depois de abrir a Minha conta ("edite no site", "Fazer upgrade"): o "pulso" de volta. A tela confere a
   assinatura a cada 5 s e logo que a janela do Paulus volta ao primeiro plano; quando o cadastro ou o
   plano mudar no site, redesenha com os dados novos. Compara com o que o site tinha quando a pessoa
   saiu (a ultima resposta de GET /api/assinatura), e nao com os dados daqui. */
function esperarVoltaDoSite() {
  const marca = (a) => JSON.stringify([(a && a.pessoa) || {}, (a && a.escritorio) || "", (a && a.plano) || "", (a && a.renova_em) || "", (a && a.situacao) || ""]);
  const antes = marca(bv.assinatura || {});
  pararEsperaDados();
  bv.dadosEsperando = true;
  let conferindo = false;
  const conferir = async () => {
    if (conferindo || !bv.dadosEsperando) return;
    conferindo = true;
    try {
      const r = await lerAssinatura(true);
      if (r && r.ativa && marca(r) !== antes) {
        bv.assinatura = r;
        if (r.pessoa) Object.assign(bv.pessoa, r.pessoa);
        if (r.escritorio) bv.escritorio = r.escritorio;
        pararEsperaDados(); desenharBoasVindas(); avisoCert("dados atualizados pelo site");
      }
    } finally { conferindo = false; }
  };
  bv.relogioDados = setInterval(conferir, 5000);
  bv.aoFocar = conferir;
  window.addEventListener("focus", conferir);
  desenharBoasVindas();
}

function pararEsperaDados() {
  bv.dadosEsperando = false;
  if (bv.relogioDados) { clearInterval(bv.relogioDados); bv.relogioDados = null; }
  if (bv.aoFocar) { window.removeEventListener("focus", bv.aoFocar); bv.aoFocar = null; }
}

function pararEsperaAssinatura() {
  if (bv.relogioAssinatura) { clearInterval(bv.relogioAssinatura); bv.relogioAssinatura = null; }
}

function passoBv() {
  return ordemBv()[bv.passo] || "boasvindas";
}

function primeiraAberturaPendente() {
  try { if (localStorage.getItem("paulus.boasvindas") === "1") return false; } catch (err) { /* sem memoria */ }
  return true;
}

/* O fundo que cobre a janela desde a primeira pintura (index.html) sai quando o assistente decide. */
function tirarCapaBv() {
  document.documentElement.classList.remove("bv-cedo");
}

async function verificarPrimeiraAbertura() {
  const forcar = location.hash === "#boasvindas";
  if (!forcar && !primeiraAberturaPendente()) { tirarCapaBv(); return; }
  try {
    const d = await (await fetch("/api/preferencias")).json();
    const nome = (((d.preferencias || {}).pessoa) || {}).nome || "";
    // Quem ja tem nome cadastrado nao precisa do passeio: marca como visto.
    if (!forcar && nome) { concluirBoasVindas(false); tirarCapaBv(); return; }
    bv.prefs = d;
  } catch (err) {
    if (!forcar) { tirarCapaBv(); return; }
  }
  try {
    await mostrarBoasVindas();
  } finally {
    tirarCapaBv();
  }
}

async function mostrarBoasVindas() {
  if (!bv.prefs) {
    try { bv.prefs = await (await fetch("/api/preferencias")).json(); } catch (err) { bv.prefs = { preferencias: {}, modelos: [] }; }
  }
  try { bv.status = await (await fetch("/api/status")).json(); } catch (err) { bv.status = null; }
  const prefs = bv.prefs.preferencias || {};
  const p = prefs.pessoa || {};
  bv.pessoa = { nome: p.nome || "", cpf: p.cpf || "", oab: p.oab || "", telefone: p.telefone || "", email: p.email || "",
    email_secundario: p.email_secundario || "", endereco: p.endereco || "" };
  bv.modulos = Object.assign({}, prefs.modulos || {});
  bv.escritorio = (prefs.escritorio || {}).nome || "";
  // A assinatura preenche o que as preferencias ainda nao tem (nome, OAB, CPF, endereco, escritorio).
  await lerAssinatura();
  // Vem ligado: o acesso externo e o caminho normal (celular, casa, forum, equipe). Quem nao quer diz na propria tela.
  bv.acesso = (prefs.acesso_remoto || {}).recusado ? false : true;
  const a = prefs.atualizacoes || {};
  bv.atualizacoes = { verificar: a.verificar !== false, avisar_antes: a.avisar_antes !== false };
  MODULOS_BV.forEach(([id]) => { if (bv.modulos[id] === undefined) bv.modulos[id] = true; });
  bv.passo = 0;
  bv.passoDesenhado = undefined;
  $("boas-vindas").hidden = false;
  desenharBoasVindas();
  (typeof lerVinculoGoogle === "function" ? lerVinculoGoogle() : Promise.resolve()).then(conferirContasBv);
}

function iniciaisDe(nome) {
  const n = (nome || "").trim();
  return n ? n.split(/\s+/).map((x) => x[0] || "").filter(Boolean).slice(0, 2).join("").toUpperCase() : "?";
}

function desenharBoasVindas() {
  const caixa = $("boas-vindas");
  const ordem = ordemBv();
  const passo = passoBv();
  // As etapas sao a .nav do site: nomes em texto, a atual acesa, as feitas em meio-tom.
  const etapas = ordem.map((p, i) => {
    const classe = "bv-etapa" + (i < bv.passo ? " feita" : "") + (i === bv.passo ? " atual" : "");
    return '<span class="' + classe + '"' + (i === bv.passo ? ' aria-current="step"' : "") + ">" + NOMES_BV[p] + "</span>";
  }).join("");
  const cabeca = '<div class="bv-cabeca pywebview-drag-region"><span class="bv-marca">PAVLVS</span><div class="bv-etapas">' + etapas + "</div>" +
    // O tema fica no canto de cima, so o icone.
    '<button class="bv-tema" id="bv-tema" title="Alternar tema" aria-label="Alternar tema">' +
    ic(document.documentElement.dataset.tema === "escuro" ? "light_mode" : "dark_mode", 18) + "</button></div>";

  const telas = {
    boasvindas: passoBoasVindas, google: passoGoogle, assinatura: passoAssinatura, dados: passoDados,
    conexoes: passoConexoes, acesso: passoAcesso, atualizacoes: passoAtualizacoes,
  };
  const [texto, lado] = telas[passo]();
  const rotulo = bv.passo === 0 ? "BEM-VINDO" : "PASSO " + bv.passo + " — " + NOMES_BV[passo].toUpperCase();
  // A transicao so quando o passo muda (redesenhar o mesmo passo, ao digitar ou trocar o tema, fica parado):
  // para a frente entra da direita; ao voltar, da esquerda.
  const anterior = bv.passoDesenhado;
  const entra = anterior === undefined ? " bv-entra" : anterior < bv.passo ? " bv-entra" : anterior > bv.passo ? " bv-entra bv-volta" : "";
  bv.passoDesenhado = bv.passo;
  const corpo = '<div class="bv-corpo' + entra + '"><div class="bv-texto"><span class="bv-rotulo">' + rotulo + "</span>" + texto + "</div>" +
    '<div class="bv-lado">' + lado + "</div></div>";

  const ultimo = bv.passo === ordem.length - 1;
  let botao;
  if (bv.passo === 0) botao = "Começar";
  else if (ultimo) botao = "Abrir o Paulus";
  else if (passo === "assinatura") botao = "Continuar sem assinatura";
  else if (passo === "conexoes" && SERVICOS_BV.some((sv) => !sv.com && bv.servicos[sv.id] && !bv.autorizados[sv.id])) botao = "Autorizar no Google";
  else botao = "Continuar";
  const esperando = (passo === "assinatura" && !(bv.assinatura && (bv.assinatura.ativa || bv.assinatura.situacao === "vencida"))) || (passo === "dados" && bv.dadosEsperando) || (passo === "conexoes" && bv.consentEsperando)
    // Entrar e obrigatorio: o Continuar do passo Sua conta so aparece com a conta vinculada.
    || (passo === "google" && !(typeof vinc !== "undefined" && vinc.estado && vinc.estado.vinculado))
    // Acesso a distancia: ou "Nao quero acessar a distancia", ou conectado ate o fim (os tres passos feitos).
    || (passo === "acesso" && !acessoResolvidoBv());
  const nota = passo === "acesso" && esperando
    ? '<span class="bv-rodape-nota">Conclua os três passos ou desligue o acesso à distância para continuar</span>' : "";
  const rodape = '<div class="bv-rodape">' +
    (bv.passo === 0 ? "" : '<button class="bv-ligacao" data-bv="voltar">' + ic("arrow_back", 16) + "Voltar</button>") +
    '<span class="cresce"></span>' +
    nota + (["modulos", "conexoes"].includes(passo) ? '<button class="bv-ligacao apagada" data-bv="pular">Pular por agora</button>' : "") +
    (esperando ? "" : '<button class="bv-continuar" data-bv="continuar"><span>' + botao + "</span></button>") + "</div>";

  caixa.innerHTML = '<div class="bv-tela">' + cabeca + corpo + rodape + "</div>";
  caixa.scrollTop = 0;
  ligarBoasVindas();
}

function infosBv(itens, icone, tom) {
  return '<div class="bv-infos">' + itens.map((t) => '<div class="' + (tom || "") + '">' + ic(icone || "info", 16) + "<span>" + t + "</span></div>").join("") + "</div>";
}

/* ------------------------------------------------------------ os passos */

function passoBoasVindas() {
  const s = bv.status || {};
  // O cartao do desenho de 09/10/2026: a linha da instalacao no padrao da linha-botao, a lista em linhas de 40 px
  // (o que ja esta pronto e o que e opcional) e a nota no rodape.
  const pasta = s.programa || s.pasta || "";
  const linha = (ok, titulo, detalhe) => '<li class="bv-item' + (ok ? " ok" : "") + '">' + ic(ok ? "check_circle" : "radio_button_unchecked", 20) +
    "<b>" + titulo + "</b><span>" + detalhe + "</span></li>";
  const texto = "<h1>Olá. Vamos deixar o Paulus do seu jeito.</h1>" +
    "<p>Poucos passos: a sua conta, os seus dados, o que conectar e o acesso à distância. Tudo pode ser mudado depois em Configurações.</p>";
  const lado = '<div class="bv-entrada"><div class="bv-secao"><span class="bv-rotulo">INSTALAÇÃO CONCLUÍDA</span>' +
    linhaBotao({ tag: "div", classe: "duas", icones: [{ html: '<img src="/img/paulus-icone.svg" alt="PAVLVS" width="32" height="32">', classe: "lb-marca-pavlvs" }],
      titulo: "Instalação concluída", sub: "Paulus" + (s.versao ? " " + esc(s.versao) : "") + ' · <span class="mono" title="' + esc(pasta) + '">' + esc(pasta) + "</span>",
      fim: { tipo: "status", texto: "pronto" } }) + "</div>" +
    '<div class="bv-bloco"><ul class="bv-itens">' +
    linha(Boolean(s.contratos), "Pasta de documentos", s.contratos ? plural(s.contratos, "documento") + " no Acervo" : "ainda não apontada") +
    linha(false, "Certificado digital", "opcional, para assinar") + "</ul>" +
    // Nada de "sem conta obrigatoria": desde 09/10/2026 o Paulus pede a conta para abrir.
    '<p class="bv-ajuda bv-bloco-nota com-fio">Os seus documentos e o que você preencher ficam nesta máquina. A conta serve para entrar e conferir a assinatura.</p>' +
    "</div></div>";
  return [texto, lado];
}

/* ------------------------------------------------------- sua conta */

/* O Paulus do servidor vinculado a conta de quem o administra (src/vinculo.py,
   E5): a Conta Google ou, desde 09/10/2026, a Conta Atos (atos.dev.br), que
   entra do mesmo jeito, pelo navegador (js/45-vinculo.js). Da para pular e vincular depois, em
   Configuracoes; vinculado, ele abre travado e pede a conta a cada abertura -
   salvo "manter aberto neste computador". */
function passoGoogle() {
  const e = (typeof vinc !== "undefined" && vinc.estado) || null;
  if (!e && typeof lerVinculoGoogle === "function") lerVinculoGoogle().then(() => { if (passoBv() === "google") desenharBoasVindas(); });
  const texto = "<h1>Entre com a sua conta.</h1>" +
    "<p>Este computador passa a ser o servidor do escritório, e a sua Conta Atos é a chave de acesso: ela se cria com o Google ou com e-mail e senha de qualquer provedor, inclusive do seu domínio ou da Microsoft. A equipe entra do mesmo jeito, cada um com a própria Conta Atos.</p>" +
    infosBv([
      "A Atos só confirma quem é você. Nenhum documento vai junto.",
      "É com ela que o Paulus confere a assinatura e, depois, convida a equipe.",
      "O Gmail, a Agenda e o Drive são opcionais e se conectam depois, em Conexões, com uma conta Google.",
    ]);
  const esperando = e && ["aguardando", "trocando", "testando"].includes(e.fase);
  let lado;
  if (e && e.vinculado) {
    // A mesma coluna do passo anterior: a conta vinculada no lugar do botao, e o interruptor como linha.
    // A conta com o icone da Conta Atos, js/45-vinculo.js iconesDaConta.
    lado = '<div class="bv-entrada"><span class="bv-rotulo">SUA CONTA</span>' +
      linhaBotao({ tag: "div", classe: "duas bv-conta-vinculada", icones: iconesDaConta(e.por, true), titulo: nomeDaConta(e.por, true), sub: esc(e.email),
        // Trocar de conta (09/10/2026): desvincula e o passo volta a pedir a conta (o mesmo do passo Assinatura).
        fim: { tipo: "acao", texto: '<button type="button" class="bv-ligacao" data-bv="outra-conta">Trocar de conta</button>' } }) +
      '<div class="bv-modulo bv-linha" data-bv-manter="1" role="switch" tabindex="0" aria-checked="' + Boolean(e.manter_aberto) + '">' +
      '<span class="duas-linhas"><b>Manter aberto neste computador</b></span>' +
      '<span class="interruptor-min' + (e.manter_aberto ? " on" : "") + '"></span></div>' +
      '<p class="bv-ajuda">' + (e.manter_aberto ? "O Paulus abre direto neste computador, sem pedir a conta de novo." : "O Paulus abre travado e pede a conta a cada abertura.") + "</p></div>";
  } else {
    // So a Conta Atos (09/10/2026): o Google, se a pessoa quiser, e escolhido la, em atos.dev.br.
    lado = '<div class="bv-entrada bv-secoes-conta">' +
      '<div class="bv-secao"><span class="bv-rotulo">SUA CONTA</span><div class="bv-bloco">' +
        (typeof botaoAtos === "function" ? botaoAtos(' data-bv-atos="1"', esperando) : "") + "</div></div>" +
      (e && e.fase === "erro" ? '<p class="acesso-erro">' + esc(e.mensagem) + "</p>" : "") +
      '<p class="bv-ajuda bv-nota-fora">É com a Conta Atos que você entra no programa depois. Sem Conta Atos? Ela se cria na página que abre, com o Google ou com e-mail e senha.</p></div>';
  }
  return [texto, lado];
}

/* Depois de vincular (pelo Google ou pela senha): o e-mail entra em Seus
   dados, Conexoes sabe se o Gmail ja esta autorizado aqui e a assinatura e a
   desta conta (GET /api/assinatura, com o login recente). */
/* O site da assinatura, ja conectado com a conta deste Paulus (o token vai no #t=, que nao sai do navegador),
   e a espera: o assistente confere a assinatura desta conta a cada 5 s e segue quando o pagamento confirmar. */
async function abrirSiteParaAssinar() {
  const e = (typeof vinc !== "undefined" && vinc.estado) || null;
  const email = (e && e.email) || bv.google || "";
  const pagina = bv.assinatura && bv.assinatura.situacao === "vencida" ? "/assinatura" : "/cadastro";
  let token = "";
  try { token = ((await (await fetch("/api/vinculo/token-do-site")).json()) || {}).token || ""; } catch (err) { /* sem token, o site pede a entrada */ }
  window.open("https://paulus.ia.br" + pagina + "/" + (email ? "?email=" + encodeURIComponent(email) : "") + (token ? "#t=" + encodeURIComponent(token) : ""), "_blank", "noopener");
  bv.assinaturaEsperando = true;
  pararEsperaAssinatura();
  bv.relogioAssinatura = setInterval(async () => { await lerAssinatura(); if (bv.assinatura && bv.assinatura.ativa) desenharBoasVindas(); }, 5000);
  desenharBoasVindas();
}

/* Os dados que vieram da assinatura vao para Meus dados e o escritorio. O documento do cadastro do site pode
   ser o CNPJ do escritorio: ele vai para o escritorio, e o CPF de Meus dados fica como estava. */
async function gravarDadosDaAssinaturaBv() {
  const pessoa = Object.assign({}, bv.pessoa);
  const escritorio = {};
  if (String(bv.escritorio || "").trim()) escritorio.nome = String(bv.escritorio).trim();
  if (pessoa.cpf && (String(pessoa.cpf).replace(/\D/g, "").length > 11 || /[A-Za-z]/.test(pessoa.cpf))) { escritorio.cnpj = pessoa.cpf; delete pessoa.cpf; }
  await gravarBoasVindas(Object.keys(escritorio).length ? { pessoa, escritorio } : { pessoa });
}

async function aoVincularBv() {
  const e = vinc.estado || {};
  if (e.vinculado) {
    bv.pessoa.email = e.email;
    if (!bv.pessoa.nome && e.nome) bv.pessoa.nome = e.nome;
    await conferirContasBv();
    if (bv.google) bv.autorizados.gmail = true;
    await lerAssinatura();
    if (!(bv.assinatura && bv.assinatura.ativa)) bv.semConferirDados = true;
  }
  if (passoBv() === "google") desenharBoasVindas();
}

/* ------------------------------------------------- acesso a distancia */

function acessoResolvidoBv() {
  if (!bv.acesso) return true;
  const d = tunelCfg.dados || {};
  const pedido = (d.conexao || {}).pedido;
  return Boolean((d.situacao || {}).conectado_ao_worker || (pedido && pedido.estado === "concluido"));
}

function passoAcesso() {
  const texto = "<h1>O Paulus vai com você: de casa, do celular, do fórum.</h1>" +
    "<p>Este computador atende pelo endereço ao lado. É por ele também que a equipe entra, cada um com a própria conta.</p>" +
    infosBv([
      "O endereço é só seu. Nada seu vai para a internet: é você que acessa o seu computador, diretamente, por ele.",
      "O serviço é o Zero Trust, protegido pela Cloudflare, e fica disponível enquanto o seu computador estiver ligado.",
      "Havendo equipe, cada pessoa acessa com a própria conta — Google ou e-mail e senha —, depois da verificação de segurança.",
    ]);
  // Desenho de 09/10/2026: "ACESSAR À DISTÂNCIA" fora e, no primeiro cartao, o interruptor - ligado por padrao.
  // Desligado, os passos somem; ligado, cada passo e um cartao e, conectado, o endereco fecha a lista.
  const interruptor = '<div class="bv-linha bv-modulo bv-acesso-chave' + (bv.acesso ? " on" : "") + '" data-bv-acesso="1" role="switch" tabindex="0" aria-checked="' + bv.acesso + '">' +
    '<span class="bv-modulo-ic">' + ic(bv.acesso ? "wifi" : "wifi_off", 19) + "</span>" +
    '<span class="duas-linhas"><b>' + (bv.acesso ? "Ligado" : "Desligado") + "</b><small>" + (bv.acesso ? "de casa, do celular, do fórum, pelo seu endereço"
      : "o Paulus abre só neste computador; dá para ligar depois em Configurações › Acesso externo") + "</small></span>" +
    '<span class="interruptor-min' + (bv.acesso ? " on" : "") + '"></span></div>';
  const secao = (miolo) => '<div class="bv-entrada bv-acesso"><span class="bv-rotulo">ACESSAR À DISTÂNCIA</span>' + interruptor + miolo + "</div>";
  if (!bv.acesso) return [texto, secao("")];
  if (!tunelCfg.dados) {
    carregarTunel().then(() => { if (passoBv() === "acesso") desenharBoasVindas(); });
    return [texto, secao('<p class="bv-ajuda bv-nota-fora esquerda">Conferindo este computador…</p>')];
  }
  const s = tunelCfg.dados.situacao || {};
  const pedido = (tunelCfg.dados.conexao || {}).pedido;
  if (s.conectado_ao_worker && !(pedido && pedido.estado === "concluido")) {
    // Ja conectado (o passeio revisto por #boasvindas): so o endereco.
    return [texto, secao(cartaoDoEnderecoBv(s.hostname))];
  }
  conexaoUI.onde = "bv";
  conexaoUI.redesenhar = desenharBoasVindas;
  const v = conexaoUI.conta;
  // A conta de titular sai de Seus dados: nome, e-mail (o da conta vinculada)
  // e o secundario - o bloco so mostra, nao pede de novo.
  conexaoUI.daPessoa = { nome: bv.pessoa.nome || "", email: bv.pessoa.email || "", secundario: bv.pessoa.email_secundario || "" };
  if (!v.nome && bv.pessoa.nome) v.nome = bv.pessoa.nome;
  if (!v.email && bv.pessoa.email) v.email = bv.pessoa.email;
  if (!v.secundario && bv.pessoa.email_secundario) v.secundario = bv.pessoa.email_secundario;
  return [texto, secao(blocoConexao() + (pedido && pedido.estado === "concluido" ? cartaoDoEnderecoBv(s.hostname || pedido.endereco) : ""))];
}

/* O endereco que atende este Paulus, no fim da lista dos passos. */
function cartaoDoEnderecoBv(hostname) {
  return linhaBotao({ tag: "div", classe: "duas", icones: [marca("cloudflare", 22)], titulo: '<span class="mono">' + esc(hostname || "") + "</span>",
    sub: "atende este Paulus", fim: { tipo: "status", texto: "conectado" } });
}

/* ----------------------------------------------------------- assinatura */

/* O portao: a assinatura e feita na Atos (atos.dev.br, que cobra o PAVLVS: os dados da nota e o pagamento),
   com a Conta Atos que entrou. Aqui so se le o estado e se espera - a janela fica
   aberta; quando o site confirmar, o passo some e o assistente segue. */
function passoAssinatura() {
  const a = bv.assinatura || { situacao: "nenhuma" };
  const e = (typeof vinc !== "undefined" && vinc.estado) || null;
  const email = (e && e.email) || bv.google || (a.email || "");
  const nome = (e && e.nome) || bv.pessoa.nome || email.split("@")[0];
  const vencida = a.situacao === "vencida";
  const esperando = bv.assinaturaEsperando;
  const texto = (vencida
    ? "<h1>A assinatura desta conta venceu.</h1><p>Regularize no site para voltar a usar tudo. Enquanto isso, você pode continuar com os seus arquivos.</p>"
    : "<h1>Ainda não há assinatura para esta conta.</h1><p>A assinatura é feita na Atos, que cobra o PAVLVS, com os dados da nota e o pagamento. Quando o pagamento for aprovado, esta janela segue sozinha.</p>") +
    infosBv(vencida
      ? ["Os dados e os documentos continuam seus, no seu computador, com ou sem assinatura.", "Ao regularizar, tudo volta na hora, sem reinstalar."]
      : ["A Atos pede o nome ou a razão social, o CPF ou CNPJ e o endereço da nota; o pagamento é no cartão ou no Pix.", "Se fechar esta janela, na próxima abertura o Paulus volta para este passo."]);
  const lado = '<div class="bv-entrada"><div class="bv-secao"><span class="bv-rotulo">ASSINATURA</span>' +
    // A conta com que se assina ("Continuar como…"): o monograma, o nome e o e-mail; o clique troca de conta (desvincula e volta a Sua conta).
    linhaBotao({ classe: "duas", attrs: ' data-bv="outra-conta" title="Trocar de conta"', icones: iconesDaConta(e && e.por, true),
      titulo: "Continuar como " + esc(nome), sub: esc(email), fim: { tipo: "acao", texto: "Trocar" } }) +
    (esperando ? "" : '<div class="bv-bloco">') + (esperando
      ? '<div class="bv-linha bv-espera"><span class="bv-giro"></span><span class="duas-linhas"><b>Esperando a confirmação do site…</b><small>a janela segue sozinha quando o pagamento confirmar</small></span></div>' +
        '<button type="button" class="bv-g-trilho" data-bv="assinatura-conferir"><span class="bv-g-pastilha">Já assinei, conferir agora</span></button>'
      : '<button type="button" class="bv-continuar bv-largo" data-bv="assinar"><span>' + ic("open_in_new", 16) + (vencida ? "Regularizar no site" : "Assinar no site") + "</span></button>") +
    '<p class="bv-ajuda ' + (esperando ? "bv-nota-fora" : "bv-bloco-nota") + '">' + (vencida
      ? "Sem assinatura válida, o Paulus abre só com os seus arquivos: documentos, pastas e anotações seguem acessíveis. Ficam suspensos as respostas de IA, a emissão de NFS-e e os demais serviços. Ao regularizar no site, tudo volta na hora."
      : "A Atos abre no seu navegador; entre com a mesma Conta Atos. O pagamento é feito lá; nada de cartão passa por aqui.") + "</p>" + (esperando ? "" : "</div>") + "</div></div>";
  return [texto, lado];
}

function passoDados() {
  const p = bv.pessoa;
  const a = bv.assinatura || {};
  const g = (typeof vinc !== "undefined" && vinc.estado && vinc.estado.vinculado) ? vinc.estado : null;
  if (g) { p.email = g.email; if (!p.nome && g.nome) p.nome = g.nome; }
  const texto = "<h1>Confira os seus dados.</h1>" +
    "<p>Vieram da assinatura. Nome, OAB e endereço entram na qualificação das partes, no papel timbrado e no selo de assinatura. Nada disso é enviado para fora.</p>" +
    infosBv(["O que mudar no site, em Minha assinatura, muda aqui também."]);
  // Com cara de formulario, mas so leitura: rotulo em cima, valor na caixa; dois por linha quando couber.
  // tam: "" = um terco, "meio" = metade, "largo" = linha inteira.
  const campo = (rotulo, valor, mono, tam) => '<div class="bv-campo-ro' + (tam ? " " + tam : "") + '"><span>' + rotulo + "</span><b" + (mono ? ' class="mono"' : "") + ">" + (valor ? esc(valor) : "<i>não informado</i>") + "</b></div>";
  if (bv.dadosEsperando) {
    // A espera no mesmo cartao da espera do login: o giro, o que acontece, e a acao de conferir.
    // A espera sem cartao em volta (09/10/2026): a linha, o botao e, embaixo, o Cancelar.
    const lado = '<div class="bv-entrada"><div class="bv-secao"><span class="bv-rotulo">DADOS DA ASSINATURA</span>' +
      '<div class="bv-linha bv-espera"><span class="bv-giro"></span><span class="duas-linhas"><b>Aguardando o site…</b><small>quando salvar na Minha conta, os dados e o plano aparecem aqui</small></span></div>' +
      '<button type="button" class="bv-g-trilho" data-bv="dados-conferir"><span class="bv-g-pastilha">Já editei, conferir agora</span></button>' +
      '<div class="cs-links bv-fora"><button type="button" class="bv-ligacao" data-bv="dados-cancelar">Cancelar</button></div></div></div>';
    return [texto, lado];
  }
  // O desenho de 09/10/2026 (o segundo): "DADOS DA ASSINATURA" fora, o cartao com os dados em grade de quatro
  // colunas (fio entre as linhas, o endereco na linha inteira) e, fora, a nota com "edite no site". Depois,
  // "PLANO" com a linha do plano e, embaixo, como a cota funciona.
  const dado = (rotulo, valor, largo) => '<div class="bv-dado' + (largo ? " largo" : "") + '"><span>' + rotulo + "</span>" +
    (valor ? "<b>" + esc(valor) + "</b>" : "<i>não informado</i>") + "</div>";
  const dataCurta = (iso) => { const [y, m, d] = String(iso || "").split("-"); return d ? d + "/" + m + "/" + y : ""; };
  const reais = (n) => "R$ " + Number(n).toLocaleString("pt-BR", { maximumFractionDigits: 2 });
  const anual = a.periodo === "anual";
  const sub = a.cortesia ? "plano de cortesia, sem cobrança"
    : a.valor ? reais(a.valor) + (anual ? " por ano" + (a.pago_ate ? ", pago até " + dataCurta(a.pago_ate) : "") : " por mês, no Pix ou no cartão")
    : "";
  const plano = a.plano
    ? linhaBotao({ tag: "div", classe: sub ? "duas" : "", titulo: esc(a.plano) + (a.periodo && !a.cortesia ? " · " + (anual ? "anual" : "mensal") : "") +
        ' <span class="lb-status bv-plano-ativa">ativa</span>', sub,
        fim: { tipo: "acao", texto: '<button type="button" class="bv-ligacao" data-bv="upgrade">Fazer upgrade ↗</button>' } })
    // Sem plano ativo (a assinatura venceu ou foi cancelada): o Paulus abre com o basico; o link leva a assinar no site.
    : linhaBotao({ tag: "div", classe: "duas", titulo: "Sem plano ativo",
        sub: (a.situacao === "vencida" ? "a assinatura venceu" : "esta conta ainda não tem assinatura") + " — sem IA, NFS-e e os demais serviços até assinar",
        fim: { tipo: "acao", texto: '<button type="button" class="bv-ligacao" data-bv="assinar">Assinar no site ↗</button>' } });
  const lado = '<div class="bv-entrada">' +
    '<div class="bv-secao"><span class="bv-rotulo">DADOS DA ASSINATURA</span>' +
    '<div class="bv-bloco bv-cartao-dados"><div class="bv-dados-grade">' +
    dado("Nome", p.nome) + dado("Escritório", bv.escritorio || a.escritorio) + dado("OAB", p.oab) + dado("CPF ou CNPJ", p.cpf) +
    dado("Telefone", p.telefone) + dado("E-mail", p.email) +
    dado("Endereço", p.endereco, true) + "</div></div>" +
    '<p class="bv-ajuda bv-nota-fora">Estas são as informações do seu cadastro. Se algo estiver errado ou precisar mudar, ' +
    '<button type="button" class="bv-ligacao bv-ligacao-forte" data-bv="editar-site">edite no site ↗</button></p></div>' +
    '<div class="bv-secao bv-secao-plano"><span class="bv-rotulo">PLANO</span>' + plano +
    (a.plano && !a.cortesia ? '<p class="bv-ajuda bv-nota-fora esquerda">A cota é do mês, liberada por semana; uma vez por mês dá para adiantar a semana seguinte. ' +
      "Se acabar, a recarga é no Pix, no preço do plano, e não vence na renovação.</p>" : "") + "</div>" +
    "</div>";
  return [texto, lado];
}

/* ------------------------------------------------------------ conexoes */

/* A conta Google comeca pelo e-mail (o login do Gmail, src/correio_oauth.py);
   a Agenda, o Meet e o Drive pedem a propria autorizacao depois, em
   Configuracoes › Conexoes. */
async function conferirContasBv() {
  try {
    const d = await (await fetch("/api/email/contas")).json();
    const g = (d.contas || []).find((c) => c.autenticacao === "google");
    bv.google = g ? g.email : null;
  } catch (err) { /* sem contas, fica como estava */ }
}

/* Um servico por linha, cada um com o proprio interruptor: o Google pede a
   permissao de cada um separadamente (src/correio_oauth.py, agenda, drive). */
const SERVICOS_BV = [
  { id: "gmail", nome: "Gmail", desc: "ler e enviar, com Aprovações" },
  { id: "agenda", nome: "Agenda", desc: "ler e criar eventos" },
  { id: "meet", nome: "Meet", desc: "criar reuniões nos eventos", com: "agenda" },
  { id: "drive", nome: "Drive", desc: "só os arquivos que o Paulus envia" },
  // A leitura do Drive (drive.readonly): a mesma de Configurações › Conexões e do Acervo (conectarGoogle("drive_leitura")).
  { id: "drive_leitura", marca: "drive", nome: "Drive", desc: "ler as pastas que você escolher no Acervo" },
]

function passoConexoes() {
  const e = (typeof vinc !== "undefined" && vinc.estado) || null;
  // Com a Conta Atos, o e-mail pode nem ser do Google: a conta e a que a pessoa escolher no consentimento.
  const porSenha = Boolean(e && e.vinculado && (e.por === "atos" || e.por === "senha"));
  const conta = bv.google || (e && e.vinculado && !porSenha ? e.email : "");
  const texto = "<h1>Conectar o Gmail, a Agenda e o Drive?</h1>" +
    (porSenha && !bv.google
      ? "<p>São serviços do Google: use uma conta Google, que pode ser outra, diferente do e-mail com que você entrou. Cada serviço pede a própria permissão ao Google, uma vez. Tudo opcional.</p>"
      : "<p>É a mesma conta Google de agora. Cada serviço pede a própria permissão ao Google, uma vez. Tudo opcional.</p>") +
    infosBv([
      "Dá para conectar ou desconectar depois em Configurações › Conexões.",
      "A autorização fica nesta máquina, cifrada pela sua conta do Windows.",
    ]);
  if (bv.google) bv.autorizados.gmail = true;
  const pedidos = SERVICOS_BV.filter((sv) => !sv.com && bv.servicos[sv.id] && !bv.autorizados[sv.id]);
  if (bv.consentEsperando) {
    const lado = '<div class="bv-entrada"><div class="bv-secao"><span class="bv-rotulo">CONEXÕES</span>' +
      '<div class="bv-linha bv-espera"><span class="bv-giro"></span><span class="duas-linhas"><b>Aguardando o consentimento no Google…</b><small>' + esc(pedidos.map((p) => p.nome).join(", ")) + " · quando autorizar, a janela segue sozinha</small></span></div>" +
      '<button type="button" class="bv-g-trilho" data-bv="consent-conferir"><span class="bv-g-pastilha">Já autorizei, conferir agora</span></button>' +
      '<p class="bv-ajuda bv-nota-fora">' + (conta ? "O Google abriu no seu navegador com esta conta." : "O Google abriu no seu navegador: escolha a conta Google que vai usar.") +
      " Se a aba não apareceu, confira as janelas abertas.</p>" +
      '<div class="cs-links bv-fora"><button type="button" class="bv-ligacao" data-bv="consent-cancelar">Cancelar</button></div></div></div>';
    return [texto, lado];
  }
  // O Meet vem com a Agenda (mesma permissao, calendar.events): a linha mostra o estado, sem interruptor proprio.
  const linhas = SERVICOS_BV.map((sv) => {
    const on = Boolean(bv.autorizados[sv.com || sv.id] || bv.servicos[sv.com || sv.id]);
    const junto = Boolean(sv.com);
    return '<button type="button" class="lb-escopo' + (junto ? " junto" : "") + '" data-bv-servico="' + (sv.com || sv.id) + '" role="switch" aria-checked="' + on + '"' + (junto ? ' title="Vem com a Agenda: a mesma permissão"' : "") + ">" +
      '<span class="lb-ic">' + eoMarca(sv.marca || sv.id) + "</span>" +
      '<span class="lb-escopo-nome">' + sv.nome + "</span>" +
      '<span class="lb-escopo-d">' + (bv.autorizados[sv.com || sv.id] ? "autorizado" : sv.desc) + "</span>" +
      '<span class="lb-toggle" aria-hidden="true"></span></button>';
  }).join("");
  // O cartao de conta + permissoes (css/57-linha-botao.css): a conta no topo, "conectado" quando o Gmail ja esta autorizado nela.
  // Entrou com a Conta Atos e ainda sem conta Google: o topo diz, sem rodeio, que esses
  // servicos so funcionam com uma conta Google, escolhida no consentimento (src/rotas_boas_vindas.py, autorizar).
  const semGoogle = linhaBotao({ tag: "div", classe: "duas lb-sem-google", icones: [eoMarca("google")],
    titulo: "Precisa de uma conta Google",
    sub: "você entrou com a Conta Atos " + esc((e && e.email) || "") }) +
    '<p class="bv-ajuda bv-nota-fora esquerda">Gmail, Agenda, Meet e Drive são serviços do Google e só funcionam com uma conta Google. Ao autorizar, o Google pede para escolher a conta, que pode ser diferente do e-mail com que você entrou.</p>';
  // Desenho de 09/10/2026: "SUA CONTA GOOGLE" com a linha da conta e "O QUE AUTORIZAR" com os servicos num cartao.
  const topo = conta ? linhaBotao({ tag: "div", icones: [eoMarca("google")], titulo: esc(conta),
      fim: bv.autorizados.gmail ? { tipo: "status", texto: "conectado" } : null }) : (porSenha ? semGoogle : "");
  const lado = '<div class="bv-entrada">' +
    (topo ? '<div class="bv-secao"><span class="bv-rotulo">SUA CONTA GOOGLE</span>' + topo + "</div>" : "") +
    '<div class="bv-secao"><span class="bv-rotulo">O QUE AUTORIZAR</span><div class="cartao-permissoes"><div class="lb-escopos">' + linhas + "</div></div></div></div>";
  return [texto, lado];
}

/* Um unico consentimento: o Google pede de uma vez as permissoes dos servicos
   marcados (POST /api/conexoes/autorizar {servicos}); a volta e a pagina de
   retorno (src/pagina_retorno.py), e aqui so se espera e se confere. */
async function pedirConsentimentoBv(servicos) {
  try {
    const resp = await fetch("/api/conexoes/autorizar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ servicos }) });
    const r = await resp.json().catch(() => ({}));
    // Recusado (o Gmail que falta, o serviço desligado na Minha conta): diz por quê, sem ficar esperando o Google.
    if (!resp.ok || !r.url) { avisoCert(maiuscula(r.detail || "não deu para abrir a autorização do Google"), { tom: "erro", dura: 8000 }); return; }
    window.open(r.url, "_blank", "noopener");
    bv.consentEsperando = true; pararEsperaConsent(); bv.consentEsperando = true;
    bv.relogioConsent = setInterval(conferirConsentBv, 4000);
    setTimeout(pararEsperaConsent, 5 * 60 * 1000);
    desenharBoasVindas();
  } catch (err) { avisoCert("não deu para abrir a autorização do Google"); }
}

async function conferirConsentBv() {
  let st = null;
  try { st = await (await fetch("/api/conexoes")).json(); } catch (err) { return false; }
  const antes = JSON.stringify(bv.autorizados);
  for (const sv of SERVICOS_BV) if (st && st[sv.id]) bv.autorizados[sv.id] = true;
  const faltam = SERVICOS_BV.some((sv) => !sv.com && bv.servicos[sv.id] && !bv.autorizados[sv.id]);
  // Autorizado: a conta Google escolhida no consentimento passa a ser a do topo do cartao.
  if (!faltam) { pararEsperaConsent(); await conferirContasBv(); desenharBoasVindas(); return true; }
  // O retorno do Google deu errado (permissao nao marcada, conta recusada, limite do plano): a espera para e a
  // tela diz por que - antes ela seguia "aguardando" para sempre. Terminou sem os servicos: tambem para.
  const c = (st && st.consentimento) || {};
  if (bv.consentEsperando && ["erro", "cancelado", "pronto"].includes(c.fase)) {
    pararEsperaConsent();
    if (c.fase === "pronto") await conferirContasBv();
    const motivo = c.fase === "pronto"
      ? "o Google voltou sem algumas permissões: na tela do Google, marque as caixas dos serviços e autorize de novo"
      : (c.mensagem || "a autorização do Google não terminou");
    if (c.fase !== "cancelado") avisoCert(maiuscula(motivo), { tom: "erro", dura: 12000 });
    desenharBoasVindas();
    return true;
  }
  if (JSON.stringify(bv.autorizados) !== antes) desenharBoasVindas();
  return false;
}

function pararEsperaConsent() {
  bv.consentEsperando = false;
  if (bv.relogioConsent) { clearInterval(bv.relogioConsent); bv.relogioConsent = null; }
}

function passoAtualizacoes() {
  const a = bv.atualizacoes || { verificar: true, avisar_antes: true };
  const texto = "<h1>Como o Paulus deve se atualizar?</h1>" +
    "<p>Uma vez por dia, o Paulus lê em paulus.ia.br se há versão nova — só essa leitura; nada seu vai junto. A versão nova vem do instalador oficial, conferido antes de abrir, e os dados do escritório ficam como estão.</p>";
  const linha = (id, titulo, desc, ligado, bloqueado) =>
    '<div class="bv-modulo' + (bloqueado ? " fixo" : "") + '"' + (bloqueado ? "" : ' data-bv-atu="' + id + '" role="switch" tabindex="0" aria-checked="' + Boolean(ligado) + '"') + ">" +
    '<span class="duas-linhas"><b>' + titulo + "</b><small>" + desc + "</small></span>" +
    '<span class="interruptor-min' + (ligado ? " on" : "") + '"></span></div>';
  // Desenho de 09/10/2026: o rotulo fora e cada opcao no seu cartao.
  const lado = '<div class="bv-entrada bv-secao bv-secao-atu"><span class="bv-rotulo">ATUALIZAÇÕES</span>' +
    linha("verificar", "Verificar atualizações uma vez por dia", a.verificar
      ? "o Paulus procura versão nova todo dia"
      : "desligado, o Paulus não procura versão nova; dá para verificar em Configurações › Versão", a.verificar) +
    linha("avisar_antes", "Avisar antes de instalar", a.avisar_antes
      ? "a faixa do topo avisa; você instala quando quiser"
      : "a versão nova baixa sozinha e se instala quando você fechar o Paulus", a.avisar_antes, !a.verificar) + "</div>";
  return [texto, lado];
}

/* ----------------------------------------------------------- os cliques */

function ligarBoasVindas() {
  const caixa = $("boas-vindas");
  caixa.querySelectorAll("[data-bv]").forEach((b) => {
    b.onclick = () => acaoBoasVindas(b.dataset.bv);
  });
  const teclaAtiva = (el, fazer) => {
    el.onclick = fazer;
    el.onkeydown = (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); fazer(); } };
  };
  caixa.querySelectorAll("[data-bv-atu]").forEach((m) => {
    teclaAtiva(m, () => { const id = m.dataset.bvAtu; bv.atualizacoes[id] = !bv.atualizacoes[id]; desenharBoasVindas(); });
  });
  // A Conta Atos (js/45-vinculo.js): o navegador abre atos.dev.br e a volta segue como a do Google.
  caixa.querySelectorAll("[data-bv-atos]").forEach((b) => {
    b.onclick = async () => {
      try {
        await entrarNoGoogleDoVinculo("vincular", aoVincularBv, false, "atos");
      } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    };
  });
  caixa.querySelectorAll("[data-bv-servico]").forEach((m) => {
    teclaAtiva(m, () => {
      const id = m.getAttribute("data-bv-servico");
      if (bv.autorizados[id]) { avisoCert("para desconectar, use Configurações › Conexões depois de abrir o Paulus"); return; }
      bv.servicos[id] = !bv.servicos[id];
      // A Agenda, o Meet e o Drive usam a autorizacao do Gmail (src/rotas_boas_vindas.py, autorizar): enquanto
      // o Gmail nao esta autorizado, ligar um deles liga o Gmail junto, e desligar o Gmail desliga os outros.
      if (!bv.autorizados.gmail) {
        const dependentes = SERVICOS_BV.filter((sv) => !sv.com && sv.id !== "gmail" && !bv.autorizados[sv.id]).map((sv) => sv.id);
        if (id !== "gmail" && bv.servicos[id] && !bv.servicos.gmail) {
          bv.servicos.gmail = true;
          avisoCert("o Gmail foi marcado junto: a Agenda e o Drive usam a mesma autorização dele");
        } else if (id === "gmail" && !bv.servicos.gmail && dependentes.some((d) => bv.servicos[d])) {
          dependentes.forEach((d) => { bv.servicos[d] = false; });
          avisoCert("a Agenda e o Drive foram desmarcados: eles usam a autorização do Gmail");
        }
      }
      desenharBoasVindas();
    });
  });
  caixa.querySelectorAll("[data-bv-manter]").forEach((m) => {
    teclaAtiva(m, async () => {
      try { await postVinculo("/api/vinculo/manter-aberto", { ligado: !(vinc.estado || {}).manter_aberto }); }
      catch (err) { avisoCert(err.message, { tom: "erro" }); }
      desenharBoasVindas();
    });
  });
  caixa.querySelectorAll("[data-bv-acesso]").forEach((m) => {
    teclaAtiva(m, async () => {
      if (bv.acesso && tunelCfg.dados && (tunelCfg.dados.situacao || {}).conectado_ao_worker) {
        avisoCert("já conectado: para desligar ou remover, use Configurações › Acesso externo");
        return;
      }
      bv.acesso = !bv.acesso;
      gravarBoasVindas({ acesso_remoto: { recusado: !bv.acesso } }).catch(() => {});
      if (!bv.acesso) {
        const pedido = ((tunelCfg.dados || {}).conexao || {}).pedido;
        if (pedido && pedido.estado === "esperando") await acessoPost("/api/acesso/tunel/cancelar").catch(() => {});
        clearTimeout(conexaoUI.relogioDisp);
      }
      desenharBoasVindas();
    });
  });
  if (passoBv() === "acesso" && bv.acesso && tunelCfg.dados) {
    ligarBlocoConexao(caixa);
    const pedido = ((tunelCfg.dados || {}).conexao || {}).pedido;
    if (pedido && pedido.estado === "esperando") acompanharTunel();
  }
  $("bv-tema").onclick = () => { alternarTema(); desenharBoasVindas(); };
}

async function acaoBoasVindas(qual) {
  if (qual === "voltar") { bv.passo = Math.max(0, bv.passo - 1); desenharBoasVindas(); return; }
  if (qual === "dados-cancelar") { pararEsperaDados(); desenharBoasVindas(); return; }
  if (qual === "consent-cancelar") { pararEsperaConsent(); fetch("/api/conexoes/cancelar", { method: "POST" }).catch(() => {}); desenharBoasVindas(); return; }
  if (qual === "consent-conferir") {
    const ok = await conferirConsentBv();
    if (!ok) avisoCert("o Google ainda não confirmou — se já autorizou, aguarde um instante");
    return;
  }
  if (qual === "dados-conferir") {
    // Voltou do site: se nada mudou (dados e plano), um ok e o assistente segue; se mudou, os dados novos
    // aparecem para conferir antes de continuar.
    const marca = () => JSON.stringify([bv.pessoa, bv.escritorio, (bv.assinatura || {}).plano || ""]);
    const antes = marca();
    const r = await lerAssinatura(true);
    if (r && r.ativa) { bv.assinatura = r; if (r.pessoa) Object.assign(bv.pessoa, r.pessoa); if (r.escritorio) bv.escritorio = r.escritorio; }
    pararEsperaDados();
    if (marca() === antes) {
      avisoCert("tudo certo: os dados continuam os mesmos");
      await gravarDadosDaAssinaturaBv();
      bv.passo += 1;
    } else avisoCert("dados atualizados pelo site: confira e continue");
    desenharBoasVindas(); return;
  }
  if (qual === "upgrade" || qual === "editar-site") {
    // A Minha conta do site ja com a sessao (um link de uso unico que a nuvem da), na aba certa:
    // Cadastro para editar os dados, Plano para o upgrade. Sem a nuvem, o endereco comum.
    const aba = qual === "upgrade" ? "plano" : "cadastro";
    let url = "https://paulus.ia.br/minha-conta/#" + aba;
    try {
      const r = await fetch("/api/assinatura/link", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ aba }) });
      if (r.ok) url = (await r.json()).url || url;
    } catch (err) { /* fica o endereco comum */ }
    window.open(url, "_blank", "noopener");
    esperarVoltaDoSite();
    return;
  }
  if (qual === "assinar") {
    await abrirSiteParaAssinar();
    return;
  }
  if (qual === "assinatura-conferir") {
    await lerAssinatura();
    if (!(bv.assinatura && bv.assinatura.ativa)) avisoCert("o site ainda não confirmou — se já pagou, aguarde um instante");
    desenharBoasVindas();
    return;
  }
  if (qual === "outra-conta") {
    pararEsperaAssinatura(); bv.assinaturaEsperando = false;
    // Trocar de conta e desvincular (src/vinculo.py): o passo Sua conta volta a pedir a conta,
    // e a assinatura e conferida de novo para a conta que entrar.
    try { await postVinculo("/api/vinculo/desvincular", {}); } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    bv.assinatura = null; bv.semConferirDados = false;
    bv.passo = Math.max(0, ordemBv().indexOf("google")); desenharBoasVindas(); return;
  }
  if (qual === "pular") { bv.passo += 1; desenharBoasVindas(); return; }
  const passo = passoBv();
  const ultimo = bv.passo === ordemBv().length - 1;
  // Continuar grava o que o passo tem, e so o que tem. CPF ou telefone que
  // nao fecha para aqui, com o aviso no campo (Pular por agora segue).
  if (passo === "google" && !(typeof vinc !== "undefined" && vinc.estado && vinc.estado.vinculado)) return;
  // Seus dados so mostra: Continuar grava o que veio da assinatura.
  if (passo === "dados") await gravarDadosDaAssinaturaBv();
  if (passo === "conexoes") {
    const pedidos = SERVICOS_BV.filter((sv) => !sv.com && bv.servicos[sv.id] && !bv.autorizados[sv.id]).map((sv) => sv.id);
    if (pedidos.length) { await pedirConsentimentoBv(pedidos); return; }
  }
  if (ultimo) {
    await gravarBoasVindas({ modulos: bv.modulos, atualizacoes: bv.atualizacoes });
    aplicarModulos(bv.modulos);
    await concluirBoasVindas(true);
    return;
  }
  bv.passo += 1;
  desenharBoasVindas();
}

async function gravarBoasVindas(dados) {
  try {
    const r = await fetch("/api/preferencias", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dados),
    });
    if (!r.ok) throw new Error(await erroDe(r));
  } catch (err) {
    avisoCert("não consegui gravar: " + err);
  }
}

async function concluirBoasVindas(fechar) {
  try { localStorage.setItem("paulus.boasvindas", "1"); } catch (err) { /* sem memoria */ }
  if (location.hash === "#boasvindas") history.replaceState(null, "", location.pathname);
  if (!fechar) return;
  $("boas-vindas").hidden = true;
  carregarUsuario();
  carregarStatus();
  $("nova").click();
}

/* --------------------------------------------------- os modulos no menu */

/* Desligado some do menu (os dois: o trilho e o seletor). Chamado ao abrir,
   ao terminar o assistente e ao salvar Configuracoes. */
function aplicarModulos(modulos) {
  const m = modulos || {};
  MODULOS_BV.forEach(([id, , , , destinos]) => {
    const desligado = m[id] === false;
    destinos.forEach((d) => document.querySelectorAll('[data-destino="' + d + '"]').forEach((b) => { b.hidden = desligado; }));
  });
}
