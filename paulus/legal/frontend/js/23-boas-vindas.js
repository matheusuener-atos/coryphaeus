/* ---------------------------------------------------------- boas-vindas */
/*
   O assistente de configuracao, na primeira abertura (docs/ui/instalacao,
   substitui A0a e A0b): tela cheia, dois caminhos. Quem cria o escritorio
   passa por oito passos; quem entra em um que ja existe, por cinco. Abre
   sozinho enquanto ninguem preencheu o nome, e por #boasvindas para quem
   quiser rever. Tudo pode ser mudado depois em Configuracoes.

   O modelo de IA e escolhido aqui (o instalador so copia os arquivos e
   instala o Ollama): o teste da maquina recomenda, a pessoa escolhe, e o
   download comeca quando o assistente termina (/api/modelos/usar).

   Acesso a distancia (R7): logo depois do nome do escritorio, um
   interruptor, desligado de fabrica. Ligado, o mesmo bloco de
   Configuracoes › Acesso externo (js/43-acesso-tunel.js): o endereco, a
   conta do titular com o autenticador e a confirmacao no navegador.
   Desligado ou pulado, nada e criado e nada vai ao Worker.

   Entrar por codigo: a pessoa digita o codigo do responsavel e recebe o
   dela. A rede local que valida o vinculo ainda nao existe; o que existe e
   o modo limitado (docs/ui/01-shell.md): o Paulus abre, o que e desta
   maquina funciona, e o que depende do escritorio fica apagado ate o
   responsavel validar - ou ate a pessoa cancelar o pedido e criar o proprio
   escritorio. O pedido fica nesta maquina, em localStorage.
*/

/* O vinculo por codigo saiu (E4): um pedido que tenha ficado guardado neste
   navegador nao prende mais a casca em modo limitado. */
try { localStorage.removeItem("paulus.vinculo"); } catch (err) { /* sem memoria */ }

const bv = {
  passo: 0, caminho: "criar", status: null, prefs: null, pessoa: {}, vinculo: null,
  maquina: null, conferindo: false, diag: 0, relogioDiag: null, catalogo: [],
  modelo: "", escolheuModelo: false, modulos: {}, google: null, oauth: null, imap: false, calib: null,
  escritorio: "", acesso: false,
  // A assinatura do e-mail que entrou (GET /api/assinatura): { ativa, situacao: "ativa"|"vencida"|"nenhuma", pessoa, escritorio, plano, renova_em }.
  // Sem assinatura ativa, o passo "assinatura" entra na ordem e segura o resto; o site faz o cadastro e o pagamento.
  assinatura: null, assinaturaEsperando: false, relogioAssinatura: null,
  // Depois de "edite no site": o formulario da lugar a uma linha de espera; ao voltar com dados novos, redesenha.
  dadosEsperando: false, relogioDados: null,
  // Conexoes: o que foi marcado (servicos), o que o Google ja autorizou (autorizados) e a espera pelo consentimento.
  servicos: {}, autorizados: {}, consentEsperando: false, relogioConsent: null,
  // O Whisper das Gravacoes, escolhido no mesmo passo do modelo de IA e
  // baixado quando o assistente termina (/api/voz/baixar).
  voz: null, vozEscolhida: "",
};
// "modulos" saiu do assistente: o plano libera, e esconder/mostrar fica em Configuracoes › Modulos.
// O passo Assinatura so entra sem plano ativo (ordemBv): na pratica, quem entrou com o Google sem nunca ter
// assinado. Quem cria a conta no site (09/10/2026) ja sai com o plano e passa direto.
const ORDEM_CRIAR = ["boasvindas", "google", "assinatura", "dados", "conexoes", "acesso", "atualizacoes"];
const ORDEM_ENTRAR = ["boasvindas", "escritorio", "dados", "ia", "codigos"];
const NOMES_BV = {
  boasvindas: "Boas-vindas", escritorio: "Escritório", dados: "Seus dados", ia: "Modelo de IA", assinatura: "Assinatura",
  modulos: "Módulos", conexoes: "Conexões", atualizacoes: "Atualizações", codigos: "Códigos",
  acesso: "Acesso à distância", google: "Sua conta",
};
const CARGOS_VINCULO = ["Advogado(a)", "Sócio(a)", "Financeiro", "Secretaria", "Estagiário(a)", "Outro"];
const DESTINOS_PRESOS = new Set(["servicos", "gravacoes", "calendario", "agendamento", "tarefas", "biblioteca", "organizar", "caixa", "financeiro", "relatorios", "cadastros", "aprovacoes"]);

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

/* O fabricante de cada modelo, pelo nome, com o logo que vai no programa
   (frontend/img/marcas, de @lobehub/icons-static-svg 1.95.1, licenca MIT). */
function fabricanteDoModelo(nome) {
  const n = String(nome || "").toLowerCase();
  if (n.startsWith("hf.co/")) return ["Hugging Face", "huggingface-color"];
  if (/(^|\/)(llama|codellama)/.test(n)) return ["Meta", "meta-color"];
  if (/(^|\/)qwen/.test(n)) return ["Alibaba", "qwen-color"];
  if (/(^|\/)gemma/.test(n)) return ["Google", "gemma-color"];
  if (/(^|\/)(mistral|ministral|mixtral)/.test(n)) return ["Mistral", "mistral-color"];
  if (/(^|\/)phi/.test(n)) return ["Microsoft", "microsoft-color"];
  if (/(^|\/)deepseek/.test(n)) return ["DeepSeek", "deepseek-color"];
  return ["", ""];
}

function ordemBv() {
  const ordem = bv.caminho === "entrar" ? ORDEM_ENTRAR : ORDEM_CRIAR;
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
  const pendente = lerVinculo();
  bv.caminho = pendente ? "entrar" : "criar";
  bv.vinculo = pendente ? Object.assign({}, pendente) : { apelido: "", cargo: "", codigoResponsavel: "", meuCodigo: "" };
  $("boas-vindas").hidden = false;
  desenharBoasVindas();
  (typeof lerVinculoGoogle === "function" ? lerVinculoGoogle() : Promise.resolve()).then(conferirContasBv);
}

function iniciaisDe(nome) {
  const n = (nome || "").trim();
  return n ? n.split(/\s+/).map((x) => x[0] || "").filter(Boolean).slice(0, 2).join("").toUpperCase() : "?";
}

/* A logo oficial e sempre escura, nos dois temas (docs/ui/instalacao). */
function iniciaisBv(nome) {
  const partes = String(nome || "").trim().split(/\s+/).filter(Boolean);
  return ((partes[0] || "")[0] || "" ) + ((partes.length > 1 ? partes[partes.length - 1][0] : "") || "");
}

function logoBv() {
  return '<span class="bv-logo" aria-hidden="true">P</span>';
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
    boasvindas: passoBoasVindas, escritorio: passoEscritorio, dados: bv.caminho === "entrar" ? passoDadosVinculo : passoDados, assinatura: passoAssinatura,
    ia: passoIA, modulos: passoModulos, conexoes: passoConexoes, atualizacoes: passoAtualizacoes, codigos: passoCodigos,
    acesso: passoAcesso, google: passoGoogle,
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
  else if (ultimo) botao = bv.caminho === "entrar" ? "Abrir o Paulus e aguardar" : "Abrir o Paulus";
  else if (passo === "ia") botao = bv.modelo && bv.modelo !== "nenhum" ? "Usar " + esc(bv.modelo) : "Continuar sem modelo";
  else if (passo === "assinatura") botao = "Continuar sem assinatura";
  else if (passo === "conexoes" && SERVICOS_BV.some((sv) => !sv.com && bv.servicos[sv.id] && !bv.autorizados[sv.id])) botao = "Autorizar no Google";
  else botao = "Continuar";
  const esperando = (passo === "ia" && !bv.maquina) || (passo === "assinatura" && !(bv.assinatura && (bv.assinatura.ativa || bv.assinatura.situacao === "vencida"))) || (passo === "dados" && bv.dadosEsperando) || (passo === "conexoes" && bv.consentEsperando)
    // Entrar e obrigatorio: o Continuar do passo Sua conta so aparece com a conta vinculada.
    || (passo === "google" && !(typeof vinc !== "undefined" && vinc.estado && vinc.estado.vinculado));
  const rodape = '<div class="bv-rodape">' +
    (bv.passo === 0 ? "" : '<button class="bv-ligacao" data-bv="voltar">' + ic("arrow_back", 16) + "Voltar</button>") +
    '<span class="cresce"></span>' +
    (["modulos", "conexoes", "acesso"].includes(passo) ? '<button class="bv-ligacao apagada" data-bv="pular">Pular por agora</button>' : "") +
    (esperando ? "" : '<button class="bv-continuar" data-bv="continuar"><span>' + botao + "</span></button>") + "</div>";

  caixa.innerHTML = '<div class="bv-tela">' + cabeca + corpo + rodape + "</div>" +
    (bv.entrarAberto ? janelaEntrarBv() : "");
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
  const lado = '<div class="bv-entrada"><div class="bv-cartao-conta bv-cartao-instalacao"><span class="bv-rotulo">INSTALAÇÃO CONCLUÍDA</span>' +
    linhaBotao({ tag: "div", classe: "duas", icones: [{ html: '<img src="/img/paulus-icone.svg" alt="PAVLVS" width="32" height="32">', classe: "lb-marca-pavlvs" }],
      titulo: "Instalação concluída", sub: "Paulus" + (s.versao ? " " + esc(s.versao) : "") + ' · <span class="mono" title="' + esc(pasta) + '">' + esc(pasta) + "</span>",
      fim: { tipo: "status", texto: "pronto" } }) +
    '<ul class="bv-itens">' +
    linha(Boolean(s.contratos), "Pasta de documentos", s.contratos ? plural(s.contratos, "documento") + " no Acervo" : "ainda não apontada") +
    linha(false, "Certificado digital", "opcional, para assinar") + "</ul>" +
    // Nada de "sem conta obrigatoria": desde 09/10/2026 o Paulus pede a conta para abrir.
    '<p class="bv-ajuda bv-cartao-nota">Os seus documentos e o que você preencher ficam nesta máquina. A conta serve para entrar e conferir a assinatura.</p>' +
    "</div></div>";
  return [texto, lado];
}

function passoEscritorio() {
  // O Paulus de equipe (docs/PLANO-EQUIPE.md, E4): este computador e o
  // servidor do escritorio, e a equipe entra pela internet, por convite. O
  // "entrar num escritorio existente" (o vinculo por codigo, que nunca teve
  // servidor) saiu.
  bv.caminho = "criar";
  const texto = "<h1>Qual é o nome do escritório?</h1>" +
    "<p>Este computador passa a ser o servidor do escritório: os documentos e as contas ficam aqui. Você é o responsável.</p>" +
    infosBv([
      "A equipe não instala nada: cada pessoa entra pela internet, com a própria conta.",
      "Você convida pelo link — pelo WhatsApp, por exemplo — em Configurações › Acesso externo.",
      "Para isso, ligue o acesso à distância no próximo passo (dá para ligar depois também).",
    ]);
  const lado = '<div class="bv-cartao">' + campoBv("escritorio", "Nome do escritório", bv.escritorio, "data-bv-escritorio", "", "Moura & Associados Advocacia") +
    '<span class="bv-cartao-pe">Aparece nos recibos, no convite da equipe e sugere o endereço do acesso à distância. Dá para mudar em Configurações › Escritório.</span></div>';
  return [texto, lado];
}

/* ------------------------------------------------------- sua conta */

/* O Paulus do servidor vinculado a conta de quem o administra (src/vinculo.py,
   E5): a conta Google ou, desde 07/10/2026, a conta PAVLVS por e-mail e senha
   (o formulario de js/45-vinculo.js). Da para pular e vincular depois, em
   Configuracoes; vinculado, ele abre travado e pede a conta a cada abertura -
   salvo "manter aberto neste computador". */
function passoGoogle() {
  const e = (typeof vinc !== "undefined" && vinc.estado) || null;
  if (!e && typeof lerVinculoGoogle === "function") lerVinculoGoogle().then(() => { if (passoBv() === "google") desenharBoasVindas(); });
  const texto = "<h1>Entre com a sua conta.</h1>" +
    "<p>Este computador passa a ser o servidor do escritório, e a sua conta é a chave de acesso: a do Google ou uma conta PAVLVS com e-mail e senha — serve e-mail de qualquer provedor, inclusive do seu domínio ou da Microsoft. A equipe entra do mesmo jeito, cada um com a própria conta.</p>" +
    infosBv([
      "O Google, ou paulus.ia.br no caso da senha, só confirma quem é você. Nenhum documento vai junto.",
      "É com ela que o Paulus confere a assinatura e, depois, convida a equipe.",
      "O Gmail, a Agenda e o Drive são opcionais e se conectam depois, em Conexões, com uma conta Google.",
    ]);
  const esperando = e && ["aguardando", "trocando", "testando"].includes(e.fase);
  let lado;
  if (e && e.vinculado) {
    // A mesma coluna do passo anterior: a conta vinculada no lugar do botao, e o interruptor como linha.
    // O G do Google ao lado da logo so na conta Google; a conta PAVLVS e so a logo.
    const marcaDaConta = e.por === "senha" ? "" : (typeof G_DO_GOOGLE !== "undefined" ? G_DO_GOOGLE : "");
    lado = '<div class="bv-entrada"><span class="bv-rotulo">' + (e.por === "senha" ? "CONTA PAVLVS" : "CONTA GOOGLE") + "</span>" +
      linhaBotao({ tag: "div", classe: "duas bv-conta-vinculada", icones: [{ html: '<img src="/img/paulus-icone.svg" alt="PAVLVS" width="32" height="32">', classe: "lb-marca-pavlvs" }, marcaDaConta], titulo: "Vinculado", sub: esc(e.email) }) +
      '<div class="bv-modulo bv-linha" data-bv-manter="1" role="switch" tabindex="0" aria-checked="' + Boolean(e.manter_aberto) + '">' +
      '<span class="duas-linhas"><b>Manter aberto neste computador</b></span>' +
      '<span class="interruptor-min' + (e.manter_aberto ? " on" : "") + '"></span></div>' +
      '<p class="bv-ajuda">' + (e.manter_aberto ? "O Paulus abre direto neste computador, sem pedir a conta de novo." : "O Paulus abre travado e pede a conta a cada abertura.") + "</p></div>";
  } else {
    // A coluna de /entrar (entrar.html): sem cartao, rotulo mono, o trilho com a pastilha do Google e,
    // embaixo, a conta PAVLVS por e-mail e senha. Criar conta e Esqueci a senha escondem o Google ate voltar.
    const noComeco = typeof contaSenha === "undefined" || (contaSenha.modo === "entrar" && !contaSenha.etapa);
    // O e-mail de Seus dados (se ja houver) vem no campo; a pessoa troca se quiser.
    if (typeof contaSenha !== "undefined" && !contaSenha.email && bv.pessoa.email) contaSenha.email = bv.pessoa.email;
    // Uma linha so no topo do cartao: onde o primeiro campo e o e-mail, o rotulo do cartao ja diz o que digitar.
    const soEmail = !noComeco && !contaSenha.etapa && (contaSenha.modo === "criar" || contaSenha.modo === "esqueci");
    const rotulo = noComeco ? "SUA CONTA" : soEmail ? (contaSenha.modo === "criar" ? "DIGITE UM E-MAIL PARA CRIAR SUA CONTA" : "DIGITE O E-MAIL PARA TROCAR A SENHA")
      : contaSenha.etapa === "codigo" ? "DIGITE O CÓDIGO QUE ENVIAMOS"
      : contaSenha.modo === "criar" ? "CRIAR CONTA PAVLVS" : "TROCAR A SENHA";
    const comGoogle = noComeco && !(e && !e.google);
    // Um cartao so (desenho de 08/10/2026): o rotulo, o Google, "OU COM E-MAIL", o formulario e, depois de um fio, a nota.
    const nota = comGoogle ? "Com o Google, o seu navegador abre a página de login; quando o Google confirmar, volte para esta janela: o Paulus reconhece sozinho. Com e-mail e senha, tudo acontece aqui."
      : noComeco && e && !e.google ? "Esta versão do Paulus não traz o login do Google: entre com e-mail e senha." : "";
    lado = '<div class="bv-entrada"><div class="bv-cartao-conta"><span class="bv-rotulo">' + rotulo + "</span>" +
      (comGoogle ? linhaBotao({ classe: "centro", attrs: ' data-bv-google="1"' + (esperando ? " disabled" : ""),
        icones: [typeof G_DO_GOOGLE !== "undefined" ? G_DO_GOOGLE : ""], titulo: esperando ? "Esperando o Google no navegador…" : "Entrar com Google" }) +
        (e && e.fase === "erro" ? '<p class="acesso-erro">' + esc(e.mensagem) + "</p>" : "") +
        '<div class="cs-ou">OU COM E-MAIL</div>' : "") +
      (typeof formContaSenha === "function" ? formContaSenha({ v: VISUAL_BV, cartao: true }) : "") +
      (nota ? '<p class="bv-ajuda bv-cartao-nota">' + nota + "</p>" : "") + "</div></div>";
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
  if (bv.caminho === "criar" && String(bv.escritorio || "").trim()) escritorio.nome = String(bv.escritorio).trim();
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
    if ((typeof contaSenha !== "undefined" && contaSenha.criouAgora) || !(bv.assinatura && bv.assinatura.ativa)) bv.semConferirDados = true;
    // Conta criada agora, aqui no assistente: sem plano, vai direto ao passo Assinatura e abre o site para assinar.
    if (typeof contaSenha !== "undefined" && contaSenha.criouAgora) {
      contaSenha.criouAgora = false;
      if (!(bv.assinatura && bv.assinatura.ativa) && ordemBv().includes("assinatura")) {
        bv.passo = ordemBv().indexOf("assinatura");
        await abrirSiteParaAssinar();
        return;
      }
    }
  }
  if (passoBv() === "google") desenharBoasVindas();
}

/* ------------------------------------------------- acesso a distancia */

function passoAcesso() {
  const texto = "<h1>O Paulus vai com você: de casa, do celular, do fórum.</h1>" +
    "<p>Este computador atende pelo endereço ao lado. É por ele também que a equipe entra, cada um com a própria conta.</p>" +
    infosBv([
      "O endereço é só seu. Nada seu vai para a internet: é você que acessa o seu computador, diretamente, por ele.",
      "O serviço é o Zero Trust, protegido pela Cloudflare, e fica disponível enquanto o seu computador estiver ligado.",
      "Havendo equipe, cada pessoa acessa com a própria conta — Google ou e-mail e senha —, depois da verificação de segurança.",
    ]);
  // A tela afirma; quem nao quer, liga o interruptor do cartao de baixo - e o cartao das etapas some.
  const chave = "";
  const recusa = '<div class="bv-linha bv-modulo bv-recusa' + (bv.acesso ? "" : " on") + '" data-bv-acesso="1" role="switch" tabindex="0" aria-checked="' + !bv.acesso + '">' +
    '<span class="bv-modulo-ic">' + ic("wifi_off", 19) + "</span>" +
    '<span class="duas-linhas"><b>Não quero acessar à distância</b><small>' + (bv.acesso ? "o Paulus abre só neste computador" : "só neste computador · dá para ligar depois em Configurações › Acesso externo") + "</small></span>" +
    '<span class="interruptor-min' + (bv.acesso ? "" : " on") + '"></span></div>';
  if (!bv.acesso) return [texto, '<div class="bv-acesso">' + recusa + "</div>"];
  if (!tunelCfg.dados) {
    carregarTunel().then(() => { if (passoBv() === "acesso") desenharBoasVindas(); });
    return [texto, '<div class="bv-cartao"><p class="cfg-explica">Conferindo este computador…</p></div>'];
  }
  const s = tunelCfg.dados.situacao || {};
  const pedido = (tunelCfg.dados.conexao || {}).pedido;
  if (s.conectado_ao_worker && !(pedido && pedido.estado === "concluido")) {
    // Ja conectado (o passeio revisto por #boasvindas): so o endereco.
    const e = "https://" + (s.hostname || "");
    return [texto, '<div class="bv-acesso">' +
      '<div class="bv-cartao"><div class="acesso-endereco"><code>' + esc(e) + "</code>" +
      '<button class="com-icone" data-tunel-copiar="' + esc(e) + '">' + ic("content_copy", 16) + "Copiar</button></div>" +
      '<span class="bv-cartao-pe">Desligar, remover e as contas da equipe ficam em Configurações › Acesso externo.</span></div></div>'];
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
  return [texto, '<div class="bv-acesso">' + blocoConexao() + recusa + "</div>"];
}

/* `modo` e o teclado (inputmode) ou, para CPF e telefone, o tipo do campo
   formatado (js/39-campos.js), que ja traz o teclado certo. */
function campoBv(chave, rotulo, valor, atributo, modo, dica) {
  const formatado = modo === "cpf" || modo === "telefone" || modo === "email";
  return '<div class="campo-painel"><label for="bv-' + chave + '">' + rotulo + '</label><input type="text" id="bv-' + chave +
    '" ' + atributo + '="' + chave + '" value="' + esc(formatado ? formatarCampo(modo, valor || "") : (valor || "")) + '"' +
    (formatado ? atributosDoCampo(modo) : (modo ? ' inputmode="' + modo + '"' : "")) +
    (dica ? ' placeholder="' + esc(dica) + '"' : "") + "></div>";
}

function fotoBv(titulo) {
  return '<div class="bv-foto"><span class="bv-iniciais" id="bv-iniciais">' + esc(iniciaisDe(bv.pessoa.nome)) + "</span>" +
    '<span class="duas-linhas"><b>' + titulo + "</b><small>saem do nome; a foto fica para Configurações › Meus dados</small></span></div>";
}

/* ----------------------------------------------------------- assinatura */

/* O portao: a assinatura e feita no site (cadastro + pagamento no Mercado Pago),
   com o e-mail que entrou. Aqui so se le o estado e se espera - a janela fica
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
    : "<h1>Ainda não há assinatura para esta conta.</h1><p>A assinatura é feita no site, com os dados do escritório e o pagamento. Quando o site confirmar, esta janela segue sozinha.</p>") +
    infosBv(vencida
      ? ["Os dados e os documentos continuam seus, no seu computador, com ou sem assinatura.", "Ao regularizar, tudo volta na hora, sem reinstalar."]
      : ["O cadastro no site já pede nome, OAB, CPF ou CNPJ e endereço: aqui você só confere.", "Se fechar esta janela, na próxima abertura o Paulus volta para este passo."]);
  const lado = '<div class="bv-entrada"><span class="bv-rotulo">ASSINATURA</span>' +
    // A conta com que se assina ("Continuar como…"): o monograma, o nome e o e-mail; o clique troca de conta (desvincula e volta a Sua conta).
    linhaBotao({ classe: "duas", attrs: ' data-bv="outra-conta" title="Trocar de conta"', icones: [monogramaLb(iniciaisBv(nome))],
      titulo: "Continuar como " + esc(nome), sub: esc(email), fim: { tipo: "acao", texto: "Trocar" } }) +
    (esperando
      ? '<div class="bv-linha bv-espera"><span class="bv-giro"></span><span class="duas-linhas"><b>Esperando a confirmação do site…</b><small>a janela segue sozinha quando o pagamento confirmar</small></span></div>' +
        '<button type="button" class="bv-continuar bv-largo" data-bv="assinatura-conferir"><span>Já assinei, conferir agora</span></button>'
      : '<button type="button" class="bv-continuar bv-largo" data-bv="assinar"><span>' + ic("open_in_new", 16) + (vencida ? "Regularizar no site" : "Assinar no site") + "</span></button>") +
    '<p class="bv-ajuda">' + (vencida
      ? "Sem assinatura válida, o Paulus abre só com os seus arquivos: documentos, pastas e anotações seguem acessíveis. Ficam suspensos as respostas de IA, a emissão de NFS-e e os demais serviços. Ao regularizar no site, tudo volta na hora."
      : "O site abre no seu navegador com esta conta já preenchida. O pagamento é feito lá, com o Mercado Pago; nada de cartão passa por aqui.") + "</p></div>";
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
    const lado = '<div class="bv-entrada"><div class="bv-cartao-conta"><span class="bv-rotulo">DADOS DA ASSINATURA</span>' +
      '<div class="bv-linha bv-espera"><span class="bv-giro"></span><span class="duas-linhas"><b>Aguardando o site…</b><small>quando salvar na Minha conta, os dados e o plano aparecem aqui</small></span></div>' +
      '<button type="button" class="bv-g-trilho" data-bv="dados-conferir"><span class="bv-g-pastilha">Já editei, conferir agora</span></button>' +
      '<div class="cs-links"><button type="button" class="bv-ligacao" data-bv="dados-cancelar">Cancelar</button></div></div></div>';
    return [texto, lado];
  }
  // O desenho de 09/10/2026: um cartao com os dados em grade de tres colunas (rotulo em cima, valor embaixo,
  // fio entre as linhas; o endereco na linha inteira) e a nota com "edite no site"; outro cartao com o plano.
  const dado = (rotulo, valor, largo) => '<div class="bv-dado' + (largo ? " largo" : "") + '"><span>' + rotulo + "</span>" +
    (valor ? "<b>" + esc(valor) + "</b>" : "<i>não informado</i>") + "</div>";
  const plano = a.plano
    ? linhaBotao({ tag: "div", titulo: esc(a.plano) + ' <span class="lb-status bv-plano-ativa">ativa</span>',
        fim: { tipo: "acao", texto: '<button type="button" class="bv-ligacao" data-bv="upgrade">Fazer upgrade ↗</button>' } })
    // Sem plano ativo (a assinatura venceu ou foi cancelada): o Paulus abre com o basico; o link leva a assinar no site.
    : linhaBotao({ tag: "div", classe: "duas", titulo: "Sem plano ativo",
        sub: (a.situacao === "vencida" ? "a assinatura venceu" : "esta conta ainda não tem assinatura") + " — sem IA, NFS-e e os demais serviços até assinar",
        fim: { tipo: "acao", texto: '<button type="button" class="bv-ligacao" data-bv="assinar">Assinar no site ↗</button>' } });
  const lado = '<div class="bv-entrada">' +
    '<div class="bv-cartao-conta bv-cartao-dados"><span class="bv-rotulo">DADOS DA ASSINATURA</span>' +
    '<div class="bv-dados-grade">' +
    dado("Nome", p.nome) + dado("Escritório", bv.escritorio || a.escritorio) + dado("OAB", p.oab) +
    dado("CPF ou CNPJ", p.cpf) + dado("Telefone", p.telefone) + dado("E-mail", p.email) +
    dado("Endereço", p.endereco, true) + "</div>" +
    '<p class="bv-ajuda bv-dados-nota">Estas são as informações do seu cadastro. Se algo estiver errado ou precisar mudar, ' +
    '<button type="button" class="bv-ligacao bv-ligacao-forte" data-bv="editar-site">edite no site ↗</button></p></div>' +
    '<div class="bv-cartao-conta bv-cartao-plano"><span class="bv-rotulo">PLANO</span>' + plano + "</div>" +
    "</div>";
  return [texto, lado];
}

/* Os dados de quem entra por codigo: vao para o responsavel junto com o
   pedido. O escritorio vem do vinculo e nao se digita aqui. */
function passoDadosVinculo() {
  const v = bv.vinculo;
  const texto = "<h1>Quem é você no escritório?</h1>" +
    "<p>Esses dados vão para o responsável junto com o seu pedido de acesso. Ele confirma o cargo e define o que você pode aprovar sozinho.</p>";
  const lado = '<div class="bv-cartao">' + fotoBv("Iniciais") +
    '<div class="bv-grade">' + campoBv("nome", "Nome completo", bv.pessoa.nome, "data-bv-pessoa") +
    campoBv("apelido", "Como quer ser chamado(a)", v.apelido, "data-bv-vinculo") +
    campoBv("oab", "OAB", bv.pessoa.oab, "data-bv-pessoa", "", "GO 00000") +
    '<div class="campo-painel"><label for="bv-cargo">Cargo sugerido</label><select id="bv-cargo" data-bv-vinculo="cargo"><option value="">escolha…</option>' +
    CARGOS_VINCULO.map((c) => '<option value="' + c + '"' + (c === v.cargo ? " selected" : "") + ">" + c + "</option>").join("") + "</select></div>" +
    campoBv("email", "E-mail", bv.pessoa.email, "data-bv-pessoa", "email") +
    '<div class="campo-painel"><label>Escritório</label><span class="bv-campo-fixo">' + ic("lan", 16) + "vem do vínculo · aparece quando o responsável validar</span></div></div>" +
    '<span class="bv-cartao-pe">“Escritório” vem do vínculo e não pode ser alterado aqui.</span></div>';
  return [texto, lado];
}

/* ------------------------------------------------------- o modelo de IA */

/* O teste desta maquina (src/maquina.py): sem IA, uns cinco segundos, na
   primeira vez que o passo abre. A barra anda enquanto ele roda; dele sai o
   recomendado, com a nota no nosso banco de provas e o tempo ESTIMADO aqui. */
async function conferirMaquinaBv() {
  if (bv.maquina || bv.conferindo) return;
  bv.conferindo = true;
  bv.diag = 4;
  bv.relogioDiag = setInterval(() => {
    bv.diag = Math.min(92, bv.diag + 3);
    const barra = document.querySelector("#bv-diag i");
    if (barra) barra.style.width = bv.diag + "%";
  }, 150);
  let d = null;
  try {
    const r = await fetch("/api/maquina");
    d = r.ok ? await r.json() : null;
  } catch (err) { d = null; }
  if (!d || !d.modelos) {
    try {
      const m = await (await fetch("/api/modelos")).json();
      bv.catalogo = (m.catalogo || []).map((c) => ({ nome: c.nome, gb: c.gb || c.gb_aprox, instalado: c.instalado, estimativa: null, qualidade: null }));
    } catch (err) { bv.catalogo = []; }
  }
  try {
    const c = await fetch("/api/calibracao");
    if (c.ok) bv.calib = await c.json();
  } catch (err) { /* sem a chave da calibracao, a linha fica como estava */ }
  clearInterval(bv.relogioDiag);
  bv.conferindo = false;
  bv.diag = 100;
  bv.maquina = d || { erro: true };
  // Sem escolha de quem usa, o recomendado vira o escolhido.
  if (!bv.escolheuModelo) bv.modelo = (d && d.recomendado) || "";
  if (!$("boas-vindas").hidden && passoBv() === "ia") desenharBoasVindas();
}

function modeloJaAqui(nome) {
  const lista = (bv.maquina && bv.maquina.modelos) || bv.catalogo || [];
  const achado = lista.find((m) => m.nome === nome);
  return Boolean(achado && achado.instalado);
}

function gbBv(x) {
  return x === null || x === undefined ? "" : Number(x).toFixed(1).replace(".", ",") + " GB";
}

function linhaModeloBv(m, limite) {
  const [autor, logo] = fabricanteDoModelo(m.nome);
  const e = m.estimativa || null;
  const q = m.qualidade || null;
  const naoCabe = Boolean(e && e.cabe === false);
  const lento = Boolean(e && e.cabe && e.primeira_s && limite && e.primeira_s > limite);
  const selos = [];
  if (m.recomendado) selos.push('<span class="etiqueta ok">recomendado</span>');
  if (lento) selos.push('<span class="etiqueta atencao">mais lento aqui</span>');
  if (naoCabe) selos.push('<span class="etiqueta atencao">não cabe na memória</span>');
  if (m.instalado) selos.push('<span class="etiqueta">já nesta máquina</span>');
  const nota = q ? "acertou " + q.certas + " de " + q.total + " no nosso teste" : "ainda sem nota no nosso teste";
  const desc = (autor ? autor + " · " : "") + nota;
  const tempo = naoCabe ? "" : (e && e.primeira_s ? "1ª pergunta ~" + e.primeira_s + " s" : "");
  const classe = "bv-modelo" + (bv.modelo === m.nome ? " escolhido" : "") + (naoCabe ? " bloqueado" : "");
  return '<button type="button" class="' + classe + '" data-bv-modelo="' + esc(m.nome) + '"' + (naoCabe ? " disabled" : "") + ">" +
    '<span class="bv-radio"></span>' +
    '<span class="bv-fabricante"' + (autor ? ' title="' + esc(autor) + '"' : "") + ">" +
    (logo ? '<img src="/img/marcas/' + logo + '.svg" alt="">' : ic("memory", 19)) + "</span>" +
    '<span class="duas-linhas"><span class="bv-modelo-nome"><span>' + esc(m.nome) + "</span>" + selos.join("") + "</span><small>" + esc(desc) + "</small></span>" +
    '<span class="bv-modelo-medida"><span class="bv-tamanho">' + gbBv(m.gb) + "</span>" + (tempo ? "<small>" + tempo + "</small>" : "") + "</span></button>";
}

function passoIA() {
  const texto = "<h1>A inteligência artificial roda aqui, nesta máquina. Ponto.</h1>" +
    "<p>Conferimos o processador, a memória e a placa de vídeo para recomendar o modelo que responde bem aqui. O modelo, o índice dos seus documentos e as senhas ficam no seu computador.</p>" +
    infosBv([
      "Os seus documentos nunca são enviados para treinar ou consultar modelo algum.",
      "Você pode desligar o Wi-Fi e tudo continua funcionando.",
      "Os tempos são estimativas; depois de baixar, “Medir” em Configurações › Modelos dá o número de verdade.",
    ], "check_circle", "ok");
  const d = bv.maquina;
  if (!d) conferirMaquinaBv();
  const m = (d && d.maquina) || {};
  const pronto = Boolean(d && !d.erro);
  const gb = (x) => String(x).replace(".", ",") + " GB";
  const placas = (m.placas_nvidia || []).map((p) => p.nome + " · " + gb(p.memoria_gb)).join("; ");
  const linhas = [
    ["Processador", pronto ? m.processador || "—" : "…"],
    ["Memória", pronto ? gb(m.ram_total_gb) + " · " + gb(m.ram_livre_gb) + " livres agora" : "…"],
    ["Placa de vídeo", pronto ? placas || "sem placa NVIDIA: o modelo roda no processador" : "…"],
  ];
  if (pronto && m.na_bateria) linhas.push(["Energia", "na bateria: na tomada o Paulus responde mais rápido"]);
  let maquina = '<div class="bv-cartao bv-maquina"><span class="bv-rotulo">ESTA MÁQUINA</span><div class="bv-tabela">' +
    linhas.map(([k, v]) => "<div><span>" + k + "</span><span>" + esc(v) + "</span></div>").join("") + "</div>";
  if (!d) {
    maquina += '<div class="bv-diag"><span><i class="pulso"></i>Conferindo esta máquina para recomendar o modelo… (uns 5 segundos, sem IA)</span>' +
      '<div class="barra-fina" id="bv-diag"><i style="width:' + bv.diag + '%"></i></div></div>';
  } else if (d.erro) {
    maquina += '<p class="bv-cartao-pe">Não consegui conferir esta máquina agora. Escolha abaixo, ou deixe para Configurações › Modelos.</p>';
  }
  maquina += "</div>";
  if (!d) return [texto, maquina];

  const todos = (d.modelos || bv.catalogo || []).slice();
  const rec = todos.filter((x) => x.recomendado);
  const outros = todos.filter((x) => !x.recomendado);
  const limite = d.limite_s || 0;
  const nenhum = '<button type="button" class="bv-modelo' + (bv.modelo === "nenhum" || !bv.modelo ? " escolhido" : "") + '" data-bv-modelo="nenhum">' +
    '<span class="bv-radio"></span><span class="bv-fabricante">' + ic("schedule", 19) + "</span>" +
    '<span class="duas-linhas"><span class="bv-modelo-nome"><span>Não baixar agora</span></span><small>escolho depois, em Configurações › Modelos</small></span></button>';
  const cal = bv.calib || {};
  const calibracao = '<div class="bv-calibracao"><span class="duas-linhas"><b>Participar da calibração</b>' +
    "<small>mede o modelo desta máquina uma vez (cerca de um minuto), manda as medidas ao site do Paulus e recebe as de outras; nada do escritório · " +
    '<button type="button" class="em-ligacao" data-cal-ver="1">ver o que é enviado</button></small></span>' +
    '<span class="interruptor-min' + (cal.participar ? " on" : "") + '" data-cal-participar="1" role="switch" tabindex="0" aria-checked="' + Boolean(cal.participar) + '" aria-label="Participar da calibração"></span></div>';
  const lista = (rec.length ? '<span class="bv-rotulo bv-lista-titulo">RECOMENDADO PARA ESTA MÁQUINA</span>' + rec.map((x) => linhaModeloBv(x, limite)).join("") : "") +
    calibracao +
    '<span class="bv-rotulo bv-lista-titulo">' + (rec.length ? "OUTRAS OPÇÕES" : "MODELOS") + "</span>" +
    outros.map((x) => linhaModeloBv(x, limite)).join("") + nenhum;
  return [texto, maquina + '<div class="bv-modelos">' + lista + blocoVozBv(m) + "</div>"];
}

/* A transcricao das Gravacoes (faster-whisper, src/transcricao.py): o
   turbo acerta mais em portugues e pede ~2 GB de memoria; o small e leve.
   Recomendado pela memoria desta maquina; tudo local, depois de baixado. */
function vozRecomendadaBv(maquina) {
  const ram = Number((maquina || {}).ram_total_gb || 0);
  return ram && ram < 12 ? "small" : "turbo";
}

function blocoVozBv(maquina) {
  if (bv.voz === null) {
    bv.voz = { carregando: true };
    fetch("/api/voz").then((r) => r.json()).then((d) => { bv.voz = d; if (passoBv() === "ia") desenharBoasVindas(); })
      .catch(() => { bv.voz = { modelos: [] }; });
    return "";
  }
  const modelos = bv.voz.modelos || [];
  if (!modelos.length) return "";
  const rec = vozRecomendadaBv(maquina);
  if (!bv.vozEscolhida) bv.vozEscolhida = (modelos.find((x) => x.instalado) || {}).nome || rec;
  const linha = (m) => {
    const escolhido = bv.vozEscolhida === m.nome;
    const selos = (m.nome === rec ? '<span class="etiqueta ok">recomendado</span>' : "") + (m.instalado ? '<span class="etiqueta">já nesta máquina</span>' : "");
    return '<button type="button" class="bv-modelo' + (escolhido ? " escolhido" : "") + '" data-bv-voz="' + esc(m.nome) + '">' +
      '<span class="bv-radio"></span><span class="bv-fabricante">' + ic("mic", 19) + "</span>" +
      '<span class="duas-linhas"><span class="bv-modelo-nome"><span>' + esc(m.rotulo) + "</span>" + selos + "</span><small>" + esc(m.nota) + "</small></span>" +
      '<span class="bv-modelo-medida"><span class="bv-tamanho">' + gbBv(m.mb / 1024) + "</span></span></button>";
  };
  const nenhum = '<button type="button" class="bv-modelo' + (bv.vozEscolhida === "nenhum" ? " escolhido" : "") + '" data-bv-voz="nenhum">' +
    '<span class="bv-radio"></span><span class="bv-fabricante">' + ic("schedule", 19) + "</span>" +
    '<span class="duas-linhas"><span class="bv-modelo-nome"><span>Não baixar agora</span></span><small>baixa na primeira gravação, em Gravações</small></span></button>';
  return '<span class="bv-rotulo bv-lista-titulo">TRANSCRIÇÃO DAS GRAVAÇÕES (WHISPER)</span>' + modelos.map(linha).join("") + nenhum;
}

/* O Whisper escolhido vira o das Gravacoes; se ainda nao esta aqui, o
   download comeca agora, junto com o do modelo de IA. */
async function usarVozEscolhida() {
  const nome = bv.vozEscolhida;
  if (!nome || nome === "nenhum") return;
  const post = (url, corpo) => fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
  try {
    let r = await post("/api/voz/modelo", { modelo: nome });
    if (!r.ok) throw new Error(await erroDe(r));
    const ja = ((bv.voz && bv.voz.modelos) || []).find((x) => x.nome === nome && x.instalado);
    if (ja) return;
    r = await post("/api/voz/baixar", { modelo: nome });
    if (!r.ok) throw new Error(await erroDe(r));
    avisoCert("baixando o Whisper para as Gravações — o andamento aparece em Gravações", { dura: 7000 });
  } catch (err) {
    avisoCert("não consegui começar o download do Whisper: " + err.message + " · dá para baixar em Gravações");
  }
}

/* ------------------------------------------------------------ modulos */

function passoModulos() {
  const ligados = 3 + MODULOS_BV.filter(([id]) => bv.modulos[id] && (!(bv.assinatura || {}).recursos || bv.assinatura.recursos.includes(id))).length;
  const a = bv.assinatura || {};
  const liberado = (id) => !a.recursos || a.recursos.includes(id);
  const texto = "<h1>O que aparece no seu menu?</h1>" +
    "<p>Só personalização: o que você desligar some do menu desta máquina, e volta quando quiser, em Configurações › Módulos. O que cada módulo pode fazer vem do plano" + (a.plano ? " <b>" + esc(a.plano) + "</b>" : "") + ".</p>" +
    '<div class="bv-contagem"><span>No menu</span><span>' + ligados + " de " + (MODULOS_BV.length + 3) + "</span></div>";
  // Fora do plano: a linha fica apagada, com o selo do plano que libera, e o interruptor nao mexe.
  const linha = (id, icone, nome, desc, fixo) => {
    const fora = !fixo && !liberado(id);
    const ligado = fixo || (!fora && bv.modulos[id]);
    const precisa = fora && a.libera_em && a.libera_em[id] ? a.libera_em[id] : "";
    return '<div class="bv-modulo' + (fixo ? " fixo" : "") + (fora ? " fora" : "") + '"' + (fixo || fora ? "" : ' data-bv-modulo="' + id + '" role="switch" tabindex="0" aria-checked="' + Boolean(ligado) + '"') + (fora ? ' title="Não está no plano atual"' : "") + ">" +
      '<span class="bv-modulo-ic">' + ic(icone, 19) + "</span>" +
      '<span class="duas-linhas"><b>' + nome + (precisa ? ' <span class="etiqueta">' + esc(precisa) + "</span>" : "") + "</b><small>" + desc + "</small></span>" +
      (fixo ? '<span class="bv-fixo">fixo</span>' : '<span class="interruptor-min' + (ligado ? " on" : "") + '"></span>') + "</div>";
  };
  // Um cartao largo, em duas colunas; os grupos do trilho, com o nucleo (Assistente, Plano e consumo, Configuracoes) fixo.
  const grupos = ["Dia a dia", "Documentos", "Escritório"];
  const colunas = grupos.map((g) => '<div class="bv-mod-grupo"><span class="bv-rotulo bv-lista-titulo">' + g.toUpperCase() + "</span>" +
    MODULOS_BV.filter((m) => m[5] === g).map(([id, icone, nome, desc]) => linha(id, icone, nome, desc, false)).join("") + "</div>").join("");
  const lado = '<div class="bv-cartao bv-modulos"><div class="bv-mod-grupo"><span class="bv-rotulo bv-lista-titulo">SEMPRE</span>' +
    linha("assistente", "forum", "Assistente", "Conversa, pesquisa no acervo e rascunhos", true) +
    linha("consumo", "speed", "Plano e consumo", "A cota do mês e o que foi usado", true) +
    linha("config", "settings", "Configurações", "Dados, módulos e conexões", true) + "</div>" + colunas + "</div>";
  return [texto, lado];
}

/* ------------------------------------------------------------ conexoes */

/* A conta Google comeca pelo e-mail (o login do Gmail, src/correio_oauth.py);
   a Agenda, o Meet e o Drive pedem a propria autorizacao depois, em
   Configuracoes › Conexoes. */
async function conferirContasBv() {
  try {
    bv.oauth = await (await fetch("/api/email/oauth")).json();
  } catch (err) { bv.oauth = null; }
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
  // Com a conta PAVLVS de e-mail e senha, o e-mail pode nem ser do Google: a conta e a que a pessoa escolher no consentimento.
  const porSenha = Boolean(e && e.vinculado && e.por === "senha");
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
    const lado = '<div class="bv-entrada"><span class="bv-rotulo">CONEXÕES</span>' +
      '<div class="bv-linha bv-espera"><span class="bv-giro"></span><span class="duas-linhas"><b>Aguardando o consentimento no Google…</b><small>' + esc(pedidos.map((p) => p.nome).join(", ")) + " · quando autorizar, a janela segue sozinha</small></span>" +
      '<button type="button" class="bv-ligacao apagada" data-bv="consent-cancelar">Cancelar</button></div>' +
      '<button type="button" class="bv-continuar bv-largo" data-bv="consent-conferir"><span>Já autorizei, conferir agora</span></button>' +
      '<p class="bv-ajuda">O Google abriu no seu navegador com esta conta. Se a aba não apareceu, confira as janelas abertas.</p></div>';
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
  const lado = '<div class="bv-entrada"><div class="cartao-permissoes">' +
    (conta ? linhaBotao({ tag: "div", icones: [eoMarca("google")], titulo: esc(conta),
      fim: bv.autorizados.gmail ? { tipo: "status", texto: "conectado" } : null }) : "") +
    '<span class="lb-rotulo">O que autorizar</span><div class="lb-escopos">' + linhas + "</div></div></div>";
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
  if (!faltam) { pararEsperaConsent(); desenharBoasVindas(); return true; }
  if (JSON.stringify(bv.autorizados) !== antes) desenharBoasVindas();
  return false;
}

function pararEsperaConsent() {
  bv.consentEsperando = false;
  if (bv.relogioConsent) { clearInterval(bv.relogioConsent); bv.relogioConsent = null; }
}

function janelaEntrarBv() {
  // So o Google: a conta do Paulus e a conta Google (nada de Microsoft nem IMAP aqui).
  const botoes = botoesDeLoginOAuth(bv.oauth && { google: bv.oauth.google });
  return '<div class="bv-veu" data-bv="fechar-entrar"><div class="bv-entrar-coluna" data-bv-parar="1">' +
    '<div class="bv-entrar" id="bv-entrar"><h2>Autorizar o Gmail</h2>' +
    (botoes || '<p class="bv-cartao-pe">Esta versão do Paulus não traz o login do Google.</p>') + "</div>" +
    '<div class="bv-entrar-notas"><span>Leio só o que você abre</span><span>Prazos viram sugestão na Agenda</span></div>' +
    '<span class="bv-entrar-notas">Nada sai sem passar por Aprovações</span></div></div>';
}

function passoAtualizacoes() {
  const a = bv.atualizacoes || { verificar: true, avisar_antes: true };
  const texto = "<h1>Como o Paulus deve se atualizar?</h1>" +
    "<p>Uma vez por dia, o Paulus lê em paulus.ia.br se há versão nova — só essa leitura; nada seu vai junto. A versão nova vem do instalador oficial, conferido antes de abrir, e os dados do escritório ficam como estão.</p>";
  const linha = (id, titulo, desc, ligado, bloqueado) =>
    '<div class="bv-modulo' + (bloqueado ? " fixo" : "") + '"' + (bloqueado ? "" : ' data-bv-atu="' + id + '" role="switch" tabindex="0" aria-checked="' + Boolean(ligado) + '"') + ">" +
    '<span class="duas-linhas"><b>' + titulo + "</b><small>" + desc + "</small></span>" +
    '<span class="interruptor-min' + (ligado ? " on" : "") + '"></span></div>';
  const lado = '<div class="bv-cartao"><div class="bv-grupos">' +
    linha("verificar", "Verificar atualizações uma vez por dia", "desligado, o Paulus não procura versão nova; dá para verificar em Configurações › Versão", a.verificar) +
    linha("avisar_antes", "Avisar antes de instalar", a.avisar_antes
      ? "a faixa do topo avisa; você instala quando quiser"
      : "a versão nova baixa sozinha e se instala quando você fechar o Paulus", a.avisar_antes, !a.verificar) + "</div></div>";
  return [texto, lado];
}

function passoCodigos() {
  const v = bv.vinculo;
  if (!v.meuCodigo) v.meuCodigo = gerarCodigoDeVinculo();
  const casas = (codigo, digitando) => {
    const t = String(codigo || "").toUpperCase();
    const classe = "bv-casas" + (digitando ? "" : " pronto");
    return '<div class="' + classe + '"' + (digitando ? ' data-bv-focar="1"' : "") + ">" + [0, 1, 2, 3, 4, 5].map((i) => {
      const c = t[i] || "";
      const classeCasa = c ? "" : (digitando && i === t.length ? "vazia cursor" : "vazia");
      return '<span class="' + classeCasa + '">' + esc(c || "·") + "</span>";
    }).join("") + "</div>";
  };
  const nome = bv.pessoa.nome || "você";
  const texto = "<h1>Dois códigos: um que você recebe, um que você passa.</h1>" +
    "<p>O primeiro é o código do responsável: ele gera no Paulus dele e vincula esta máquina ao escritório. O segundo é gerado aqui e identifica você; o responsável digita em Configurações › Escritório e vínculos.</p>" +
    infosBv([
      "O código do responsável vale por 15 minutos.",
      "Enquanto ele não adiciona você, o Paulus abre com o que é só desta máquina; o que depende do escritório fica bloqueado.",
      "A conferência pela rede local ainda não existe nesta versão: o pedido fica guardado nesta máquina até ela chegar. Dá para cancelar e criar o seu escritório a qualquer momento.",
    ]);
  const lado = '<div class="bv-cartao bv-codigo-cartao"><div class="bv-codigo-cabeca"><span class="bv-num-passo">1</span><span>Código do responsável</span><small>' +
    (v.codigoResponsavel && v.codigoResponsavel.length === 6 ? "6 de 6" : "6 caracteres") + "</small></div>" +
    casas(v.codigoResponsavel, true) +
    '<input type="text" id="bv-codigo" class="bv-oculto" maxlength="6" autocomplete="off" spellcheck="false" value="' + esc(v.codigoResponsavel || "") + '">' +
    '<span class="bv-codigo-nota">Digite os 6 caracteres que o responsável gerou para esta máquina. Letras e números, sem diferença entre maiúsculas e minúsculas.</span></div>' +
    '<div class="bv-cartao bv-codigo-cartao"><div class="bv-codigo-cabeca"><span class="bv-num-passo">2</span><span>Seu código, para o responsável</span><span class="etiqueta prazo">aguardando</span></div>' +
    casas(v.meuCodigo, false) +
    '<span class="bv-codigo-nota">Gerado para ' + esc(nome) + " · esta máquina · válido até o responsável validar</span>" +
    '<div class="bv-codigo-acoes"><button class="com-icone" data-bv="copiar">' + ic("content_copy", 16) + "Copiar</button>" +
    '<button class="com-icone" data-bv="whatsapp">' + ic("chat", 16) + "WhatsApp</button></div></div>";
  return [texto, lado];
}

/* Sem O, 0, I e 1: um codigo ditado por telefone nao pode depender de
   distinguir letra de numero. */
function gerarCodigoDeVinculo() {
  const alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const sorteio = new Uint8Array(6);
  if (window.crypto && window.crypto.getRandomValues) window.crypto.getRandomValues(sorteio);
  else for (let i = 0; i < 6; i += 1) sorteio[i] = Math.floor(Math.random() * 256);
  return Array.from(sorteio).map((n) => alfabeto[n % alfabeto.length]).join("");
}

/* ----------------------------------------------------------- os cliques */

function ligarBoasVindas() {
  const caixa = $("boas-vindas");
  caixa.querySelectorAll("[data-bv]").forEach((b) => {
    /* O fundo da janela Entrar so fecha com clique NELE. Perguntar se o alvo
       esta dentro da janela nao serve: o botao do Google se troca pelo
       "aguardando o navegador" no proprio clique, e o alvo, ja fora da
       pagina, parecia um clique fora - fechava a janela e cancelava o login
       (a volta do Google caia numa porta fechada). */
    b.onclick = (e) => { if (b.dataset.bv === "fechar-entrar" && e.target !== b) return; acaoBoasVindas(b.dataset.bv); };
  });
  const teclaAtiva = (el, fazer) => {
    el.onclick = fazer;
    el.onkeydown = (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); fazer(); } };
  };
  caixa.querySelectorAll("[data-caminho]").forEach((o) => {
    teclaAtiva(o, () => {
      bv.caminho = o.dataset.caminho;
      if (!bv.vinculo) bv.vinculo = { apelido: "", cargo: "", codigoResponsavel: "", meuCodigo: "" };
      desenharBoasVindas();
    });
  });
  caixa.querySelectorAll("[data-bv-voz]").forEach((b) => {
    b.onclick = () => { bv.vozEscolhida = b.dataset.bvVoz; desenharBoasVindas(); };
  });
  caixa.querySelectorAll("[data-bv-modelo]").forEach((b) => {
    b.onclick = () => { bv.modelo = b.dataset.bvModelo; bv.escolheuModelo = true; desenharBoasVindas(); };
  });
  caixa.querySelectorAll("[data-bv-atu]").forEach((m) => {
    teclaAtiva(m, () => { const id = m.dataset.bvAtu; bv.atualizacoes[id] = !bv.atualizacoes[id]; desenharBoasVindas(); });
  });
  caixa.querySelectorAll("[data-bv-modulo]").forEach((m) => {
    teclaAtiva(m, () => { const id = m.dataset.bvModulo; bv.modulos[id] = !bv.modulos[id]; desenharBoasVindas(); });
  });
  caixa.querySelectorAll("[data-bv-pessoa]").forEach((i) => {
    i.oninput = (e) => {
      bv.pessoa[i.dataset.bvPessoa] = e.target.value;
      if (i.dataset.bvPessoa === "nome") {
        const el = $("bv-iniciais");
        if (el) el.textContent = iniciaisDe(e.target.value);
      }
    };
  });
  caixa.querySelectorAll("[data-bv-google]").forEach((b) => {
    b.onclick = async () => {
      try {
        await entrarNoGoogleDoVinculo("vincular", aoVincularBv, false);
      } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    };
  });
  // A conta PAVLVS por e-mail e senha (js/45-vinculo.js): entrou, segue como a volta do Google.
  if (passoBv() === "google" && typeof ligarContaSenha === "function") {
    ligarContaSenha(caixa, { finalidade: "vincular", redesenhar: desenharBoasVindas, aoEntrar: aoVincularBv });
  }
  caixa.querySelectorAll("[data-bv-servico]").forEach((m) => {
    teclaAtiva(m, () => {
      const id = m.getAttribute("data-bv-servico");
      if (bv.autorizados[id]) { avisoCert("para desconectar, use Configurações › Conexões depois de abrir o Paulus"); return; }
      bv.servicos[id] = !bv.servicos[id];
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
  caixa.querySelectorAll("[data-bv-escritorio]").forEach((i) => {
    i.oninput = () => { bv.escritorio = i.value; };
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
  caixa.querySelectorAll("[data-bv-vinculo]").forEach((i) => {
    i.oninput = (e) => { bv.vinculo[i.dataset.bvVinculo] = e.target.value; };
    i.onchange = i.oninput;
  });
  ligarCalibracao(caixa, async () => {
    try { bv.calib = await (await fetch("/api/calibracao")).json(); } catch (err) { /* fica o que havia */ }
  });
  const entrar = $("bv-entrar");
  if (entrar) {
    ligarLoginOAuth(entrar, (conta) => {
      bv.google = (conta && conta.email) || "conta Google";
      bv.imap = false;
      bv.entrarAberto = false;
      avisoCert("conta Google conectada ao e-mail", { tom: "ok" });
      desenharBoasVindas();
    });
  }
  const codigo = $("bv-codigo");
  if (codigo) {
    // As seis casas sao a borda do campo (js/00-base.js): vermelhas quando nao fecha, verdes quando fecha.
    vigiarCampo(codigo, (x) => (/^[A-Z0-9]{6}$/i.test(x) ? "" : "digite os 6 caracteres do código do responsável"),
      { vazio: "digite os 6 caracteres do código do responsável", caixa: caixa.querySelector("[data-bv-focar]") || undefined });
    codigo.oninput = () => {
      codigo.value = codigo.value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 6);
      bv.vinculo.codigoResponsavel = codigo.value;
      const casas = caixa.querySelector("[data-bv-focar]");
      if (casas) {
        casas.querySelectorAll("span").forEach((s, i) => {
          const c = codigo.value[i] || "";
          s.textContent = c || "·";
          s.className = c ? "" : (i === codigo.value.length ? "vazia cursor" : "vazia");
        });
      }
      const contagem = caixa.querySelector(".bv-codigo-cabeca small");
      if (contagem) contagem.textContent = codigo.value.length === 6 ? "6 de 6" : "6 caracteres";
    };
    const focar = caixa.querySelector("[data-bv-focar]");
    if (focar) focar.onclick = () => codigo.focus();
    codigo.focus();
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
    bv.assinatura = null;
    bv.passo = Math.max(0, ordemBv().indexOf("google")); desenharBoasVindas(); return;
  }
  if (qual === "pular") { bv.passo += 1; desenharBoasVindas(); return; }
  if (qual === "google") {
    if (bv.google) { avisoCert("para desconectar, use E-mail › Contas depois de abrir o Paulus"); return; }
    bv.entrarAberto = true;
    desenharBoasVindas();
    return;
  }
  if (qual === "fechar-entrar") {
    eoParar();
    fetch("/api/email/oauth/cancelar", { method: "POST" }).catch(() => {});
    bv.entrarAberto = false;
    desenharBoasVindas();
    return;
  }
  if (qual === "imap") {
    eoParar();
    fetch("/api/email/oauth/cancelar", { method: "POST" }).catch(() => {});
    bv.entrarAberto = false;
    bv.imap = true;
    desenharBoasVindas();
    return;
  }
  if (qual === "copiar") { copiarTexto(bv.vinculo.meuCodigo, "código copiado — passe ao responsável"); return; }
  if (qual === "whatsapp") {
    copiarTexto("Meu código para entrar no Paulus do escritório: " + bv.vinculo.meuCodigo + " (" + (bv.pessoa.nome || "") + ")",
      "mensagem copiada — cole na conversa com o responsável no WhatsApp");
    return;
  }
  const passo = passoBv();
  const ultimo = bv.passo === ordemBv().length - 1;
  // Continuar grava o que o passo tem, e so o que tem. CPF ou telefone que
  // nao fecha para aqui, com o aviso no campo (Pular por agora segue).
  if (passo === "google" && !(typeof vinc !== "undefined" && vinc.estado && vinc.estado.vinculado)) return;
  if (passo === "dados") {
    const errado = camposInvalidos($("boas-vindas"));
    // O campo que nao fecha ja esta vermelho (js/39-campos.js): so o foco nele.
    if (errado) { errado.focus(); return; }
    $("boas-vindas").querySelectorAll("[data-bv-pessoa]").forEach((i) => { bv.pessoa[i.dataset.bvPessoa] = i.value; });
    await gravarDadosDaAssinaturaBv();
  }
  if (passo === "escritorio" && bv.caminho === "criar") {
    const campo = $("boas-vindas").querySelector("[data-bv-escritorio]");
    if (campo) bv.escritorio = campo.value;
    if (bv.escritorio.trim()) {
      await gravarBoasVindas({ escritorio: { nome: bv.escritorio.trim() } });
      // O endereco sugerido acompanha o nome, enquanto ninguem mexeu nele.
      await carregarTunel();
    }
  }
  if (passo === "conexoes") {
    const pedidos = SERVICOS_BV.filter((sv) => !sv.com && bv.servicos[sv.id] && !bv.autorizados[sv.id]).map((sv) => sv.id);
    if (pedidos.length) { await pedirConsentimentoBv(pedidos); return; }
  }
  if (passo === "acesso" && bv.acesso) {
    const d = tunelCfg.dados || {};
    const pedido = (d.conexao || {}).pedido;
    if (pedido && pedido.estado === "esperando") avisoCert("a confirmação continua no navegador; o endereço aparece em Configurações › Acesso externo quando terminar", { dura: 7000 });
    else if (!(d.situacao || {}).conectado_ao_worker) avisoCert("o acesso à distância ficou desligado; dá para ligar em Configurações › Acesso externo");
  }
  if (ultimo) {
    if (bv.caminho === "entrar") {
      if ($("bv-codigo") ? !conferirCampos([$("bv-codigo")]) : (bv.vinculo.codigoResponsavel || "").length !== 6) return;
      guardarVinculo({
        meuCodigo: bv.vinculo.meuCodigo, codigoResponsavel: bv.vinculo.codigoResponsavel, apelido: bv.vinculo.apelido || "",
        cargo: bv.vinculo.cargo || "", nome: bv.pessoa.nome || "", pedido_em: new Date().toISOString(), estado: "aguardando",
      });
      aplicarModoLimitado();
    } else {
      await gravarBoasVindas({ modulos: bv.modulos, atualizacoes: bv.atualizacoes });
      aplicarModulos(bv.modulos);
    }
    await usarModeloEscolhido();
    await usarVozEscolhida();
    await concluirBoasVindas(true);
    if (bv.caminho === "entrar") avisoCert("pedido guardado nesta máquina — o Paulus abre em modo limitado até o responsável validar");
    if (bv.imap && bv.caminho === "criar") { marcarDestino("caixa"); mostrarEmail(); }
    return;
  }
  bv.passo += 1;
  desenharBoasVindas();
}

/* O modelo escolhido no passo 3 vira o padrao; se ainda nao esta aqui, o
   download comeca agora, com a barra no cartao do inicio. */
async function usarModeloEscolhido() {
  if (!bv.modelo || bv.modelo === "nenhum") return;
  try {
    const r = await fetch("/api/modelos/usar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome: bv.modelo, baixar: true }),
    });
    if (!r.ok) throw new Error(await erroDe(r));
    if (!modeloJaAqui(bv.modelo)) avisoCert("baixando o " + bv.modelo + " — o andamento aparece no início", { dura: 7000 });
  } catch (err) {
    avisoCert("não consegui começar o download do modelo: " + err + " · dá para baixar em Configurações › Modelos");
  }
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

/* ------------------------------------------------- o vinculo pendente */

function lerVinculo() {
  try {
    const v = JSON.parse(localStorage.getItem("paulus.vinculo") || "null");
    return v && v.estado === "aguardando" ? v : null;
  } catch (err) { return null; }
}

function guardarVinculo(v) {
  try { localStorage.setItem("paulus.vinculo", JSON.stringify(v)); } catch (err) { /* sem memoria */ }
}

function vinculoPendente() { return Boolean(lerVinculo()); }

/* A casca inteira continua; o que depende da rede fica apagado
   (docs/ui/01-shell.md, modo limitado). */
function aplicarModoLimitado() {
  const pendente = vinculoPendente();
  document.body.classList.toggle("vinculo-pendente", pendente);
  document.querySelectorAll("[data-destino]").forEach((b) => {
    b.classList.toggle("presa", pendente && DESTINOS_PRESOS.has(b.dataset.destino));
  });
  /* O estado fica dito na barra de titulo enquanto durar - e nao so no cartao
     do inicio, que some assim que a pessoa abre outra tela. */
  avisoFixoNaJanela(pendente
    ? "Aguardando o responsável adicionar você ao escritório · só o que é desta máquina funciona por enquanto."
    : null, { icone: "schedule", acao: { rotulo: "Mostrar meu código", fazer: mostrarMeuCodigo } });
}

async function mostrarMeuCodigo() {
  const v = lerVinculo();
  if (!v) return;
  const r = await dialogo({
    titulo: "Seu código", contexto: "Escritório e vínculos",
    texto: "O responsável digita este código em Configurações › Escritório e vínculos para adicionar você ao escritório.",
    html: casasDoCodigo(v.meuCodigo),
    confirmar: "Copiar código", cancelar: "Fechar",
  });
  if (r && r.ok) copiarTexto(v.meuCodigo || "", "código copiado");
}

async function cancelarVinculo() {
  if (!(await confirmar({ titulo: "Cancelar o pedido de entrar no escritório?", contexto: "Escritório e vínculos", texto: "Este computador passa a ser um escritório novo, e você o responsável. Dá para pedir de novo depois.", confirmar: "Cancelar o pedido", cancelar: "Manter o pedido" }))) return;
  try { localStorage.removeItem("paulus.vinculo"); } catch (err) { /* sem memoria */ }
  aplicarModoLimitado();
  avisoCert("pedido cancelado — tudo liberado; este computador é o seu escritório");
  if ($("cfg-tela")) desenharConfig();
  else carregarAgora();
}

function casasDoCodigo(codigo) {
  return '<span class="agora-codigo">' + String(codigo || "").split("").map((c) => "<span>" + esc(c) + "</span>").join("") + "</span>";
}

/* No Assistente, no lugar de "Acontecendo agora": o cartao de espera com o
   codigo da pessoa e o que ela ja pode fazer. */
function cartaoDeEsperaDoVinculo() {
  const v = lerVinculo();
  if (!v) return "";
  return '<div class="cartao-agora espera"><div class="cabeca"><i class="ponto-acc"></i><span class="nome">Aguardando o responsável validar o seu vínculo</span></div>' +
    '<div class="corpo">Seu código, para ele digitar em Configurações › Escritório e vínculos:</div>' + casasDoCodigo(v.meuCodigo) +
    '<div class="corpo">Enquanto isso, o que é só desta máquina funciona: Assistente, Documentos, Assinatura, Foco e Configurações. Serviços, Agenda, Acervo, E-mail, Financeiro, Cadastros e Aprovações esperam o escritório.</div>' +
    '<div class="rodape">A conferência pela rede local ainda não existe nesta versão; o pedido fica guardado nesta máquina.</div>' +
    '<div class="acoes"><button class="fantasma" data-vinculo-copiar="1">' + ic("content_copy", 16) + "Copiar código</button>" +
    '<button class="fantasma" data-vinculo-cancelar="1">Cancelar e criar meu escritório</button></div></div>';
}

function ligarEsperaDoVinculo() {
  const copiar = document.querySelector("[data-vinculo-copiar]");
  if (copiar) copiar.onclick = (e) => { e.stopPropagation(); copiarTexto((lerVinculo() || {}).meuCodigo || "", "código copiado"); };
  const cancelar = document.querySelector("[data-vinculo-cancelar]");
  if (cancelar) cancelar.onclick = (e) => { e.stopPropagation(); cancelarVinculo(); };
}

/* Em Configuracoes > Escritorio e vinculos: o pedido desta maquina. */
function cartaoDoPedidoDestaMaquina() {
  const v = lerVinculo();
  if (!v) return "";
  const corpo = '<p class="cfg-texto">Este computador pediu para entrar em um escritório existente' + (v.nome ? " como " + esc(v.nome) : "") +
    (v.cargo ? " · " + esc(v.cargo) : "") + ". O responsável digita o seu código no Paulus dele; até ele validar, o que depende do escritório fica apagado no menu.</p>" +
    '<div class="cfg-codigo"><span class="duas-linhas"><b>Seu código, para o responsável</b><small>pedido em ' + esc(dataBR(v.pedido_em)) + " · válido até ele validar</small></span>" +
    '<span class="cfg-casas">' + String(v.meuCodigo || "").split("").map((c) => "<span>" + esc(c) + "</span>").join("") + "</span></div>" +
    '<div class="cfg-codigo"><span class="duas-linhas"><b>Código do responsável que você digitou</b><small>a conferência pela rede local ainda não existe</small></span>' +
    '<span class="cfg-casas">' + String(v.codigoResponsavel || "").split("").map((c) => "<span>" + esc(c) + "</span>").join("") + "</span></div>" +
    '<div class="cfg-botoes"><button data-cfg-vinculo-copiar="1">' + ic("content_copy", 16) + "Copiar meu código</button>" +
    '<button class="em-ligacao acc" data-cfg-vinculo-cancelar="1">Cancelar o pedido e criar meu escritório</button></div>';
  return cartaoCfg("Pedido desta máquina", pontoCfg("aguardando o responsável", "acc"), corpo);
}
