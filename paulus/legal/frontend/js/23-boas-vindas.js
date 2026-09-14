/* ---------------------------------------------------------- boas-vindas */
/*
   A primeira abertura (docs/ui/03-telas-desktop.md, A0a e A0b): seis passos
   em tela cheia para quem cria um escritorio, quatro para quem entra em um
   que ja existe, todos pulaveis e revisiveis depois em Configuracoes. Abre
   sozinha enquanto ninguem preencheu o nome, e por #boasvindas para quem
   quiser rever.

   Entrar por codigo (A0b): a pessoa digita o codigo do responsavel e recebe
   o dela. A rede local que valida o vinculo ainda nao existe; o que existe e
   o modo limitado (docs/ui/01-shell.md): o PAULUS abre, o que e desta
   maquina funciona, e o que depende do escritorio fica apagado ate o
   responsavel validar - ou ate a pessoa cancelar o pedido e criar o proprio
   escritorio. O pedido fica nesta maquina, em localStorage.
*/

const bv = { passo: 0, status: null, prefs: null, pessoa: {}, modelo: "", escritorio: "novo", vinculo: null };
const PASSOS_BV = ["Boas-vindas", "Escritório", "Seus dados", "Como a IA funciona", "Conexões", "Atualizações"];
const PASSOS_VINCULO = ["Boas-vindas", "Escritório", "Seus dados", "Códigos"];
const CARGOS_VINCULO = ["Advogado(a)", "Sócio(a)", "Financeiro", "Secretaria", "Estagiário(a)", "Outro"];
const DESTINOS_PRESOS = new Set(["servicos", "gravacoes", "calendario", "agendamento", "tarefas", "biblioteca", "organizar", "caixa", "financeiro", "relatorios", "cadastros", "aprovacoes"]);

function passosAtuais() {
  return bv.escritorio === "existente" ? PASSOS_VINCULO : PASSOS_BV;
}

function primeiraAberturaPendente() {
  try { if (localStorage.getItem("paulus.boasvindas") === "1") return false; } catch (err) { /* sem memoria */ }
  return true;
}

async function verificarPrimeiraAbertura() {
  const forcar = location.hash === "#boasvindas";
  if (!forcar && !primeiraAberturaPendente()) return;
  try {
    const d = await (await fetch("/api/preferencias")).json();
    const nome = (((d.preferencias || {}).pessoa) || {}).nome || "";
    // Quem ja tem nome cadastrado nao precisa do passeio: marca como visto.
    if (!forcar && nome) { concluirBoasVindas(false); return; }
    bv.prefs = d;
  } catch (err) {
    if (!forcar) return;
  }
  mostrarBoasVindas();
}

async function mostrarBoasVindas() {
  if (!bv.prefs) {
    try { bv.prefs = await (await fetch("/api/preferencias")).json(); } catch (err) { bv.prefs = { preferencias: {}, modelos: [] }; }
  }
  try { bv.status = await (await fetch("/api/status")).json(); } catch (err) { bv.status = null; }
  const p = ((bv.prefs.preferencias || {}).pessoa) || {};
  bv.pessoa = { nome: p.nome || "", cpf: p.cpf || "", oab: p.oab || "", telefone: p.telefone || "", email: p.email || "", endereco: p.endereco || "" };
  bv.modelo = bv.prefs.modelo_atual || (bv.status && bv.status.modelo) || "";
  bv.passo = 0;
  const pendente = lerVinculo();
  bv.escritorio = pendente ? "existente" : "novo";
  bv.vinculo = pendente ? Object.assign({}, pendente) : { apelido: "", cargo: "", codigoResponsavel: "", meuCodigo: "" };
  $("boas-vindas").hidden = false;
  desenharBoasVindas();
}

function iniciaisDe(nome) {
  const n = (nome || "").trim();
  return n ? n.split(/\s+/).map((x) => x[0] || "").filter(Boolean).slice(0, 2).join("").toUpperCase() : "?";
}

function desenharBoasVindas() {
  const caixa = $("boas-vindas");
  const lista = passosAtuais();
  const passos = lista.map((t, i) => {
    const feito = i < bv.passo;
    const classe = "bv-passo" + (feito ? " feito" : "") + (i === bv.passo ? " atual" : "");
    return (i ? '<i class="bv-traco"></i>' : "") +
      '<span class="' + classe + '"><span class="bv-num">' + (feito ? ic("check", 12) : String(i + 1)) + "</span>" + t + "</span>";
  }).join("");
  const selo = bv.escritorio === "existente" && bv.passo >= 2 ? "REDE LOCAL · NADA NA INTERNET" : "NADA SAIU DESTA MÁQUINA";
  const cabeca = '<div class="bv-cabeca"><span class="bv-marca"><img src="/img/paulus-logo.svg" alt=""><span>PAVLVS</span></span>' +
    '<div class="bv-passos">' + passos + '</div><span class="bv-selo"><i class="ponto-verde pulsa"></i>' + selo + "</span></div>";

  const telas = bv.escritorio === "existente"
    ? [passoBoasVindas, passoEscritorio, passoDadosVinculo, passoCodigos]
    : [passoBoasVindas, passoEscritorio, passoDados, passoIA, passoConexoes, passoAtualizacoes];
  const corpo = telas[bv.passo]();
  const ultimo = bv.passo === lista.length - 1;
  let botaoFinal;
  if (bv.passo === 0) botaoFinal = "Começar";
  else if (!ultimo) botaoFinal = "Continuar";
  else if (bv.escritorio === "existente") botaoFinal = ic("arrow_forward", 18) + "Abrir o PAULUS e aguardar";
  else botaoFinal = ic("arrow_forward", 18) + "Abrir o PAULUS";
  const rodape = '<div class="bv-rodape">' +
    (bv.passo === 0
      ? '<span class="nota-barra">PAULUS Legal · versão em desenvolvimento · Windows</span>'
      : '<button class="bv-ligacao" data-bv="voltar">← Voltar</button>') +
    '<span class="cresce"></span>' +
    (bv.passo >= 2 && !ultimo ? '<button class="bv-ligacao apagada" data-bv="pular">Pular por agora</button>' : "") +
    '<button class="primario bv-continuar" data-bv="continuar">' + botaoFinal + "</button></div>";

  caixa.innerHTML = '<div class="bv-tela">' + cabeca + corpo + rodape + "</div>" +
    '<button class="bv-tema" id="bv-tema" title="Alternar tema" aria-label="Alternar tema">' +
    ic(document.documentElement.dataset.tema === "escuro" ? "light_mode" : "dark_mode", 18) + "</button>";
  caixa.scrollTop = 0;
  ligarBoasVindas();
}

function passoBoasVindas() {
  const s = bv.status || {};
  const item = (ok, texto, parcial) => {
    const classe = "bv-check" + (ok ? " ok" : "");
    return '<div class="' + classe + '">' + ic(ok ? "check_circle" : (parcial ? "radio_button_partial" : "radio_button_unchecked"), 18) +
      "<span>" + texto + "</span></div>";
  };
  const modeloTxt = s.modelo
    ? "Modelo " + esc(s.modelo) + (s.tamanho_gb ? " · " + String(s.tamanho_gb).replace(".", ",") + " GB" : " · ainda não baixado")
    : "Modelo: nenhum encontrado no Ollama";
  return '<div class="bv-corpo"><div class="bv-texto"><span class="bv-rotulo">BEM-VINDO</span>' +
    "<h1>Olá. Vamos deixar o PAULUS do seu jeito.</h1>" +
    "<p>Seis passos rápidos: o escritório, seus dados, como a IA funciona, o que conectar e como atualizar. Tudo pode ser mudado depois em Configurações.</p>" +
    '<div class="doc-etiquetas"><span class="etiqueta ok">Software livre · gratuito</span><span class="etiqueta">IA 100% local</span><span class="etiqueta">Cerca de 3 minutos</span></div></div>' +
    '<div class="bv-cartao"><div class="bv-instalacao"><img src="/img/paulus-logo.svg" alt=""><span class="duas-linhas"><b>' +
    (s.ollama ? "Instalação concluída" : "Quase lá") + "</b><small>PAULUS Legal · " + esc(s.pasta || "") + "</small></span>" +
    '<span class="etiqueta ' + (s.ollama ? "ok" : "prazo") + '">' + (s.ollama ? "pronto" : "falta o Ollama") + "</span></div>" +
    '<div class="bv-checks">' +
    item(Boolean(s.ollama), s.ollama ? "Ollama instalado e rodando em 127.0.0.1" : "Ollama não respondeu — abra o Ollama e clique em Começar de novo") +
    item(Boolean(s.modelo && s.tamanho_gb), modeloTxt, Boolean(s.modelo)) +
    item(Boolean(s.contratos), s.contratos ? "Pasta de documentos: " + plural(s.contratos, "documento") + " abertos" : "Pasta de documentos: ainda não apontada", true) +
    item(false, "Certificado digital: opcional, para assinar") + "</div>" +
    '<span class="nota-barra">Sem cadastro em servidor, sem conta obrigatória. O que você preencher fica nesta máquina.</span></div></div>';
}

function passoEscritorio() {
  const opcao = (id, icone, titulo, pill, texto) => {
    const classe = "bv-opcao" + (bv.escritorio === id ? " escolhida" : "");
    return '<div class="' + classe + '" data-escritorio="' + id + '"><span class="bv-radio"></span>' +
      '<span class="duas-linhas"><span class="bv-opcao-titulo">' + ic(icone, 18) + titulo +
      '<span class="etiqueta ok">' + pill + "</span></span><small>" + texto + "</small></span></div>";
  };
  return '<div class="bv-corpo"><div class="bv-texto"><span class="bv-rotulo">PASSO 1 — ESCRITÓRIO</span>' +
    "<h1>Este computador começa um escritório novo ou entra em um que já existe?</h1>" +
    "<p>O escritório é o grupo de máquinas que compartilham cadastros, agenda, serviços e aprovações pela rede local. Quem cria o escritório vira o responsável e define as alçadas; os demais entram com um código de vínculo.</p>" +
    '<div class="bv-infos">' + [
      "As máquinas se encontram pela rede local (mesmo Wi-Fi ou cabo). Nada passa por servidor na internet.",
      "Cada máquina mantém sua própria IA local; o que se compartilha são os dados do escritório.",
      "Sozinho? Crie o escritório mesmo assim — dá para convidar gente depois em Configurações › Escritório e vínculos.",
    ].map((t) => "<div>" + ic("info", 16) + "<span>" + t + "</span></div>").join("") + "</div></div>" +
    '<div class="bv-opcoes">' +
    opcao("novo", "add_business", "Criar um escritório novo", "você será o responsável",
      "Você passa a ser o responsável: aprova o que sai e define quem faz o quê. Quando a rede local chegar, é você quem gera os códigos de vínculo para as outras máquinas.") +
    opcao("existente", "group_add", "Entrar em um escritório existente", "precisa de código",
      "Peça ao responsável o código de vínculo. Ele aparece no PAULUS dele em Configurações › Escritório e vínculos. A validação pela rede local ainda não existe: até lá, o PAULUS abre em modo limitado, com o que é só desta máquina.") +
    "</div></div>";
}

function passoDados() {
  const campo = (chave, rotulo, modo) =>
    '<div class="campo-painel"><label for="bv-' + chave + '">' + rotulo + '</label><input type="text" id="bv-' + chave +
    '" data-bv-pessoa="' + chave + '" value="' + esc(bv.pessoa[chave] || "") + '"' + (modo ? ' inputmode="' + modo + '"' : "") + "></div>";
  return '<div class="bv-corpo"><div class="bv-texto"><span class="bv-rotulo">PASSO 2 — SEUS DADOS</span>' +
    "<h1>Quem vai usar o PAULUS?</h1>" +
    "<p>Nome, OAB e endereço entram na qualificação das partes, no papel timbrado e no selo de assinatura. Nada disso é enviado para fora.</p></div>" +
    '<div class="bv-cartao"><div class="bv-foto"><span class="bv-iniciais" id="bv-iniciais">' + esc(iniciaisDe(bv.pessoa.nome)) + "</span>" +
    '<span class="duas-linhas"><b>Iniciais</b><small>saem do nome; a foto fica para Configurações › Meus dados</small></span></div>' +
    '<div class="bv-grade">' + campo("nome", "Nome completo") + campo("oab", "OAB") + campo("cpf", "CPF", "numeric") +
    campo("telefone", "Telefone", "tel") + campo("email", "E-mail", "email") + campo("endereco", "Endereço") + "</div></div></div>";
}

/* Os dados de quem entra por codigo: vao para o responsavel junto com o
   pedido. O escritorio vem do vinculo e nao se digita aqui. */
function passoDadosVinculo() {
  const v = bv.vinculo;
  const campo = (chave, rotulo, valor, atributo, modo) =>
    '<div class="campo-painel"><label for="bv-' + chave + '">' + rotulo + '</label><input type="text" id="bv-' + chave +
    '" ' + atributo + '="' + chave + '" value="' + esc(valor || "") + '"' + (modo ? ' inputmode="' + modo + '"' : "") + "></div>";
  return '<div class="bv-corpo"><div class="bv-texto"><span class="bv-rotulo">PASSO 2 — SEUS DADOS</span>' +
    "<h1>Quem é você no escritório?</h1>" +
    "<p>Esses dados vão para o responsável junto com o seu pedido de acesso. Ele confirma o cargo e define o que você pode aprovar sozinho.</p></div>" +
    '<div class="bv-cartao"><div class="bv-foto"><span class="bv-iniciais" id="bv-iniciais">' + esc(iniciaisDe(bv.pessoa.nome)) + "</span>" +
    '<span class="duas-linhas"><b>Foto ou iniciais</b><small>as iniciais saem do nome; a foto fica para Configurações › Meus dados</small></span></div>' +
    '<div class="bv-grade">' + campo("nome", "Nome completo", bv.pessoa.nome, "data-bv-pessoa") +
    campo("apelido", "Como quer ser chamado(a)", v.apelido, "data-bv-vinculo") +
    campo("oab", "OAB", bv.pessoa.oab, "data-bv-pessoa") +
    '<div class="campo-painel"><label for="bv-cargo">Cargo sugerido</label><select id="bv-cargo" data-bv-vinculo="cargo"><option value="">escolha…</option>' +
    CARGOS_VINCULO.map((c) => '<option value="' + c + '"' + (c === v.cargo ? " selected" : "") + ">" + c + "</option>").join("") + "</select></div>" +
    campo("email", "E-mail", bv.pessoa.email, "data-bv-pessoa", "email") +
    '<div class="campo-painel"><label>Escritório</label><span class="bv-campo-fixo">' + ic("lan", 16) + "vem do vínculo · aparece quando o responsável validar</span></div></div>" +
    '<span class="nota-barra">“Escritório” vem do vínculo e não pode ser alterado aqui.</span></div></div>';
}

function passoCodigos() {
  const v = bv.vinculo;
  if (!v.meuCodigo) v.meuCodigo = gerarCodigoDeVinculo();
  const casas = (codigo, digitando) => {
    const texto = String(codigo || "").toUpperCase();
    const classe = "bv-casas" + (digitando ? "" : " pronto");
    return '<div class="' + classe + '"' + (digitando ? ' data-bv-focar="1"' : "") + ">" + [0, 1, 2, 3, 4, 5].map((i) => {
      const c = texto[i] || "";
      const classeCasa = c ? "" : (digitando && i === texto.length ? "vazia cursor" : "vazia");
      return '<span class="' + classeCasa + '">' + esc(c || "·") + "</span>";
    }).join("") + "</div>";
  };
  const nome = bv.pessoa.nome || "você";
  return '<div class="bv-corpo"><div class="bv-texto"><span class="bv-rotulo">PASSO 3 — CÓDIGOS</span>' +
    "<h1>Dois códigos: um que você recebe, um que você passa.</h1>" +
    "<p>O primeiro é o código do responsável: ele gera no PAULUS dele e vincula esta máquina ao escritório. O segundo é gerado aqui e identifica você: o responsável digita em Configurações › Escritório e vínculos para adicionar você ao escritório, com cargo e alçada.</p>" +
    '<div class="bv-infos">' + [
      "O responsável encontra o código dele em Configurações › Escritório e vínculos. Vale por 15 minutos.",
      "Enquanto ele não adiciona você, o PAULUS abre normalmente e funciona com o que é só desta máquina; o que depende do escritório fica bloqueado.",
      "A conferência pela rede local ainda não existe nesta versão: o código fica guardado nesta máquina até ela chegar. Você pode cancelar o pedido e criar o seu escritório a qualquer momento.",
    ].map((t) => "<div>" + ic("info", 16) + "<span>" + t + "</span></div>").join("") + "</div></div>" +
    '<div class="bv-opcoes">' +
    '<div class="bv-cartao bv-codigo-cartao"><div class="bv-codigo-cabeca"><span class="bv-num-passo">1</span><span>Código do responsável</span><small>' +
    (v.codigoResponsavel && v.codigoResponsavel.length === 6 ? "6 de 6" : "6 caracteres") + "</small></div>" +
    casas(v.codigoResponsavel, true) +
    '<input type="text" id="bv-codigo" class="bv-oculto" maxlength="6" autocomplete="off" spellcheck="false" value="' + esc(v.codigoResponsavel || "") + '">' +
    '<span class="bv-codigo-nota">Digite os 6 caracteres que o responsável gerou para esta máquina. Letras e números, sem diferença entre maiúsculas e minúsculas.</span></div>' +
    '<div class="bv-cartao bv-codigo-cartao"><div class="bv-codigo-cabeca"><span class="bv-num-passo">2</span><span>Seu código, para o responsável</span><span class="etiqueta prazo">aguardando</span></div>' +
    casas(v.meuCodigo, false) +
    '<span class="bv-codigo-nota">Gerado para ' + esc(nome) + " · esta máquina · válido até o responsável validar</span>" +
    '<div class="bv-codigo-acoes"><button class="com-icone" data-bv="copiar">' + ic("content_copy", 16) + "Copiar</button>" +
    '<button class="com-icone" data-bv="whatsapp">' + ic("chat", 16) + "WhatsApp</button></div></div>" +
    "</div></div>";
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

function passoIA() {
  const modelos = (bv.prefs && bv.prefs.modelos) || [];
  const s = bv.status || {};
  const linhas = [
    ["Modelo de IA", "nesta máquina · Ollama", true],
    ["Seus documentos e índice", "nesta máquina", true],
    ["Senhas e certificado", "cofre desta máquina", true],
    ["E-mail", "seu servidor (IMAP/SMTP) · opcional", false],
    ["Atualizações", "pelo instalador · nada sai sozinho", false],
  ];
  return '<div class="bv-corpo"><div class="bv-texto"><span class="bv-rotulo">PASSO 3 — COMO A IA FUNCIONA</span>' +
    "<h1>A inteligência artificial roda aqui, nesta máquina. Ponto.</h1>" +
    "<p>O modelo, o índice dos seus documentos e as senhas ficam no seu computador. Não existe chamada a nenhum serviço de IA na internet. Você pode desligar o Wi-Fi e tudo continua funcionando.</p>" +
    '<div class="bv-checks">' + [
      "Os seus documentos nunca são enviados para treinar ou consultar modelo algum.",
      "Serviços online são opcionais e só para o que é online por natureza: e-mail e arquivos na nuvem.",
      "Tudo que sai da máquina — um e-mail, um pagamento — passa por Aprovações antes.",
    ].map((t) => '<div class="bv-check ok">' + ic("check_circle", 18) + "<span>" + t + "</span></div>").join("") + "</div></div>" +
    '<div class="bv-cartao"><b class="bv-cartao-titulo">Onde cada coisa fica</b><div class="bv-tabela">' +
    linhas.map(([k, v, local]) => "<div><span>" + k + '</span><span class="bv-onde' + (local ? " ok" : "") + '">' + v + "</span></div>").join("") + "</div>" +
    '<div class="campo-painel"><label for="bv-modelo">Modelo escolhido</label><select id="bv-modelo">' +
    (modelos.length
      ? modelos.map((m) => '<option value="' + esc(m) + '"' + (m === bv.modelo ? " selected" : "") + ">" + esc(m) + "</option>").join("")
      : '<option value="">' + esc(bv.modelo || "nenhum modelo no Ollama") + "</option>") + "</select></div>" +
    '<span class="nota-barra">' + (s.tamanho_gb ? "Este pesa " + String(s.tamanho_gb).replace(".", ",") + " GB. " : "") +
    "Com placa de vídeo, você pode trocar por um modelo maior em Configurações › Assistente e modelo.</span></div></div>";
}

function passoConexoes() {
  const conta = (letra, titulo, sub, acao) =>
    '<div class="bv-conta"><span class="bv-conta-letra">' + letra + '</span><span class="duas-linhas"><b>' + titulo + "</b><small>" + sub + "</small></span>" + acao + "</div>";
  return '<div class="bv-corpo"><div class="bv-texto"><span class="bv-rotulo">PASSO 4 — CONEXÕES</span>' +
    "<h1>O que você quer conectar? Tudo opcional.</h1>" +
    "<p>O e-mail do escritório pode ser lido e respondido daqui, com envio passando por Aprovações. A IA continua local: o PAULUS lê aqui e não devolve nada sem o seu sim.</p>" +
    '<div class="bv-infos">' + [
      "A senha do e-mail fica nesta máquina, no cofre do programa.",
      "Leio só o que você abre; nada é apagado no servidor.",
      "Dá para desconectar a qualquer hora em E-mail › Contas.",
    ].map((t) => "<div>" + ic("info", 16) + "<span>" + t + "</span></div>").join("") + "</div></div>" +
    '<div class="bv-contas">' +
    conta("@", "E-mail do escritório", "IMAP / SMTP · detecto o servidor pelo domínio", '<button class="com-icone" data-bv="email">Configurar ao abrir</button>') +
    conta("G", "Conta Google", "Gmail · Google Drive", '<span class="etiqueta">em breve</span>') +
    conta("M", "Conta Microsoft", "Outlook · OneDrive", '<span class="etiqueta">em breve</span>') +
    '<span class="nota-barra">WhatsApp Web e certificado digital ficam para depois, quando você precisar — em Conexões e em Assinatura.</span></div></div>';
}

function passoAtualizacoes() {
  return '<div class="bv-corpo"><div class="bv-texto"><span class="bv-rotulo">PASSO 5 — ATUALIZAÇÕES</span>' +
    "<h1>Como o PAULUS deve se atualizar?</h1>" +
    "<p>Nesta versão, atualizar é rodar o instalador novo: o programa não verifica nada na internet sozinho. Quando a verificação automática chegar, ela vai baixar só o instalador — nenhum dado seu vai junto — e você poderá desligá-la.</p></div>" +
    '<div class="bv-cartao"><div class="bv-checks">' +
    '<div class="bv-check">' + ic("radio_button_unchecked", 18) + "<span>Verificar atualizações uma vez por dia — em breve</span></div>" +
    '<div class="bv-check">' + ic("radio_button_unchecked", 18) + "<span>Avisar antes de instalar — em breve</span></div></div>" +
    '<div class="bv-apoio"><b>Você também pode apoiar o projeto</b><p>O PAULUS é gratuito e mantido por quem usa. Sem pressa: dá para fazer isso depois, em Apoiar, no menu.</p></div></div></div>';
}

function ligarBoasVindas() {
  const caixa = $("boas-vindas");
  caixa.querySelectorAll("[data-bv]").forEach((b) => { b.onclick = () => acaoBoasVindas(b.dataset.bv); });
  caixa.querySelectorAll("[data-escritorio]").forEach((o) => {
    o.onclick = () => {
      bv.escritorio = o.dataset.escritorio;
      if (!bv.vinculo) bv.vinculo = { apelido: "", cargo: "", codigoResponsavel: "", meuCodigo: "" };
      desenharBoasVindas();
    };
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
  caixa.querySelectorAll("[data-bv-vinculo]").forEach((i) => {
    i.oninput = (e) => { bv.vinculo[i.dataset.bvVinculo] = e.target.value; };
    i.onchange = i.oninput;
  });
  const modelo = $("bv-modelo");
  if (modelo) modelo.onchange = (e) => { bv.modelo = e.target.value; };
  const codigo = $("bv-codigo");
  if (codigo) {
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
  if (qual === "pular") { bv.passo += 1; desenharBoasVindas(); return; }
  if (qual === "email") {
    await concluirBoasVindas(true);
    marcarDestino("caixa");
    mostrarEmail();
    return;
  }
  if (qual === "copiar") { copiarTexto(bv.vinculo.meuCodigo, "código copiado — passe ao responsável"); return; }
  if (qual === "whatsapp") {
    copiarTexto("Meu código para entrar no PAULUS do escritório: " + bv.vinculo.meuCodigo + " (" + (bv.pessoa.nome || "") + ")",
      "mensagem copiada — cole na conversa com o responsável no WhatsApp");
    return;
  }
  const ultimo = bv.passo === passosAtuais().length - 1;
  // Continuar grava o que o passo tem, e so o que tem.
  if (bv.passo === 2) await gravarBoasVindas({ pessoa: bv.pessoa });
  if (bv.escritorio !== "existente" && bv.passo === 3 && bv.modelo) await gravarBoasVindas({ modelo: bv.modelo });
  if (ultimo) {
    if (bv.escritorio === "existente") {
      if ((bv.vinculo.codigoResponsavel || "").length !== 6) { avisoCert("digite os 6 caracteres do código do responsável"); $("bv-codigo").focus(); return; }
      guardarVinculo({
        meuCodigo: bv.vinculo.meuCodigo, codigoResponsavel: bv.vinculo.codigoResponsavel, apelido: bv.vinculo.apelido || "",
        cargo: bv.vinculo.cargo || "", nome: bv.pessoa.nome || "", pedido_em: new Date().toISOString(), estado: "aguardando",
      });
      aplicarModoLimitado();
    }
    await concluirBoasVindas(true);
    if (bv.escritorio === "existente") avisoCert("pedido guardado nesta máquina — o PAULUS abre em modo limitado até o responsável validar");
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
    '<div class="corpo">Enquanto isso, o que é só desta máquina funciona: Assistente, Documentos, Assinatura, Foco, Configurações e Apoiar. Serviços, Agenda, Acervo, E-mail, Financeiro, Cadastros e Aprovações esperam o escritório.</div>' +
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
    (v.cargo ? " · " + esc(v.cargo) : "") + ". O responsável digita o seu código no PAULUS dele; até ele validar, o que depende do escritório fica apagado no menu.</p>" +
    '<div class="cfg-codigo"><span class="duas-linhas"><b>Seu código, para o responsável</b><small>pedido em ' + esc(dataBR(v.pedido_em)) + " · válido até ele validar</small></span>" +
    '<span class="cfg-casas">' + String(v.meuCodigo || "").split("").map((c) => "<span>" + esc(c) + "</span>").join("") + "</span></div>" +
    '<div class="cfg-codigo"><span class="duas-linhas"><b>Código do responsável que você digitou</b><small>a conferência pela rede local ainda não existe</small></span>' +
    '<span class="cfg-casas">' + String(v.codigoResponsavel || "").split("").map((c) => "<span>" + esc(c) + "</span>").join("") + "</span></div>" +
    '<div class="cfg-botoes"><button data-cfg-vinculo-copiar="1">' + ic("content_copy", 16) + "Copiar meu código</button>" +
    '<button class="em-ligacao acc" data-cfg-vinculo-cancelar="1">Cancelar o pedido e criar meu escritório</button></div>';
  return cartaoCfg("Pedido desta máquina", pontoCfg("aguardando o responsável", "acc"), corpo);
}

