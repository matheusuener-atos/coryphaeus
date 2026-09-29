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
   Configuracoes › Acesso de fora (js/43-acesso-tunel.js): o endereco, a
   conta do titular com o autenticador e a confirmacao no navegador.
   Desligado ou pulado, nada e criado e nada vai ao Worker.

   Entrar por codigo: a pessoa digita o codigo do responsavel e recebe o
   dela. A rede local que valida o vinculo ainda nao existe; o que existe e
   o modo limitado (docs/ui/01-shell.md): o PAULUS abre, o que e desta
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
  // O Whisper das Gravacoes, escolhido no mesmo passo do modelo de IA e
  // baixado quando o assistente termina (/api/voz/baixar).
  voz: null, vozEscolhida: "",
};
const ORDEM_CRIAR = ["boasvindas", "google", "escritorio", "acesso", "dados", "ia", "modulos", "conexoes", "atualizacoes"];
const ORDEM_ENTRAR = ["boasvindas", "escritorio", "dados", "ia", "codigos"];
const NOMES_BV = {
  boasvindas: "Boas-vindas", escritorio: "Escritório", dados: "Seus dados", ia: "Modelo de IA",
  modulos: "Módulos", conexoes: "Conexões", atualizacoes: "Atualizações", codigos: "Códigos",
  acesso: "Acesso à distância", google: "Conta Google",
};
const CARGOS_VINCULO = ["Advogado(a)", "Sócio(a)", "Financeiro", "Secretaria", "Estagiário(a)", "Outro"];
const DESTINOS_PRESOS = new Set(["servicos", "gravacoes", "calendario", "agendamento", "tarefas", "biblioteca", "organizar", "caixa", "financeiro", "relatorios", "cadastros", "aprovacoes"]);

/* Os modulos do menu que podem ser desligados (preferencia `modulos`), com o
   destino de cada um na casca. O Assistente, Apoiar e Configuracoes ficam
   sempre. */
const MODULOS_BV = [
  ["servicos", "work", "Serviços", "Processos, prazos e a trilha de cada caso", ["servicos"]],
  ["gravacoes", "mic", "Gravações", "Audiências e reuniões com transcrição", ["gravacoes"]],
  ["agenda", "calendar_month", "Agenda", "Compromissos, prazos e lembretes", ["calendario"]],
  ["acervo", "inventory_2", "Acervo", "Os arquivos do escritório, lidos pela IA", ["biblioteca"]],
  ["documentos", "description", "Documentos", "Peças, contratos e modelos no editor", ["editor"]],
  ["assinatura", "draw", "Assinatura", "Assinatura digital com certificado ICP-Brasil", ["assinar"]],
  ["email", "mail", "E-mail", "A caixa de entrada ligada aos serviços", ["caixa"]],
  ["financeiro", "payments", "Financeiro", "Honorários, custas e recebimentos", ["financeiro"]],
  ["cadastros", "contacts", "Cadastros", "Clientes, partes e contatos", ["cadastros"]],
  ["aprovacoes", "verified", "Aprovações", "O que sai do escritório passa aqui antes", ["aprovacoes"]],
  ["foco", "self_improvement", "Foco e bem-estar", "Pausas e blocos de concentração", ["foco"]],
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
  return bv.caminho === "entrar" ? ORDEM_ENTRAR : ORDEM_CRIAR;
}

function passoBv() {
  return ordemBv()[bv.passo] || "boasvindas";
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
  const prefs = bv.prefs.preferencias || {};
  const p = prefs.pessoa || {};
  bv.pessoa = { nome: p.nome || "", cpf: p.cpf || "", oab: p.oab || "", telefone: p.telefone || "", email: p.email || "", endereco: p.endereco || "" };
  bv.modulos = Object.assign({}, prefs.modulos || {});
  bv.escritorio = (prefs.escritorio || {}).nome || "";
  bv.acesso = Boolean((prefs.acesso_remoto || {}).hostname);
  const a = prefs.atualizacoes || {};
  bv.atualizacoes = { verificar: a.verificar !== false, avisar_antes: a.avisar_antes !== false };
  MODULOS_BV.forEach(([id]) => { if (bv.modulos[id] === undefined) bv.modulos[id] = true; });
  bv.passo = 0;
  const pendente = lerVinculo();
  bv.caminho = pendente ? "entrar" : "criar";
  bv.vinculo = pendente ? Object.assign({}, pendente) : { apelido: "", cargo: "", codigoResponsavel: "", meuCodigo: "" };
  $("boas-vindas").hidden = false;
  desenharBoasVindas();
  conferirContasBv();
}

function iniciaisDe(nome) {
  const n = (nome || "").trim();
  return n ? n.split(/\s+/).map((x) => x[0] || "").filter(Boolean).slice(0, 2).join("").toUpperCase() : "?";
}

/* A logo oficial e sempre escura, nos dois temas (docs/ui/instalacao). */
function logoBv() {
  return '<span class="bv-logo" aria-hidden="true">P</span>';
}

function desenharBoasVindas() {
  const caixa = $("boas-vindas");
  const ordem = ordemBv();
  const passo = passoBv();
  const etapas = ordem.map((p, i) => {
    const classe = "bv-etapa" + (i < bv.passo ? " feita" : "") + (i === bv.passo ? " atual" : "");
    const marca = i < bv.passo ? ic("check", 13) : String(i + 1);
    return (i ? '<i class="bv-traco"></i>' : "") + '<span class="' + classe + '" title="' + NOMES_BV[p] + '"><span class="bv-num">' + marca + "</span>" +
      (i === bv.passo ? NOMES_BV[p] : "") + "</span>";
  }).join("");
  const selo = bv.caminho === "entrar" && bv.passo > 1 ? "REDE LOCAL · NADA NA INTERNET" : "NADA SAIU DESTA MÁQUINA";
  const cabeca = '<div class="bv-cabeca"><span class="bv-marca">PAVLVS</span><div class="bv-etapas">' + etapas + "</div>" +
    '<span class="bv-selo"><i class="ponto-verde"></i>' + selo + "</span>" +
    // O tema fica no canto de cima, so o icone.
    '<button class="bv-tema" id="bv-tema" title="Alternar tema" aria-label="Alternar tema">' +
    ic(document.documentElement.dataset.tema === "escuro" ? "light_mode" : "dark_mode", 18) + "</button></div>";

  const telas = {
    boasvindas: passoBoasVindas, escritorio: passoEscritorio, dados: bv.caminho === "entrar" ? passoDadosVinculo : passoDados,
    ia: passoIA, modulos: passoModulos, conexoes: passoConexoes, atualizacoes: passoAtualizacoes, codigos: passoCodigos,
    acesso: passoAcesso, google: passoGoogle,
  };
  const [texto, lado] = telas[passo]();
  const rotulo = bv.passo === 0 ? "BEM-VINDO" : "PASSO " + bv.passo + " — " + NOMES_BV[passo].toUpperCase();
  const corpo = '<div class="bv-corpo"><div class="bv-texto"><span class="bv-rotulo">' + rotulo + "</span>" + texto + "</div>" +
    '<div class="bv-lado">' + lado + "</div></div>";

  const ultimo = bv.passo === ordem.length - 1;
  let botao;
  if (bv.passo === 0) botao = "Começar";
  else if (ultimo) botao = bv.caminho === "entrar" ? "Abrir o PAULUS e aguardar" : "Abrir o PAULUS";
  else if (passo === "ia") botao = bv.modelo && bv.modelo !== "nenhum" ? "Usar " + esc(bv.modelo) : "Continuar sem modelo";
  else botao = "Continuar";
  const esperando = passo === "ia" && !bv.maquina;
  const versao = (bv.status && bv.status.versao) || "";
  const rodape = '<div class="bv-rodape">' +
    (bv.passo === 0
      ? '<span class="bv-versao">PAULUS' + (versao ? " · versão " + esc(versao) : "") + " · Windows</span>"
      : '<button class="bv-ligacao" data-bv="voltar">← Voltar</button>') +
    '<span class="cresce"></span>' +
    (["dados", "modulos", "conexoes", "acesso", "google"].includes(passo) ? '<button class="bv-ligacao apagada" data-bv="pular">Pular por agora</button>' : "") +
    (esperando ? "" : '<button class="bv-continuar" data-bv="continuar">' + botao + "</button>") + "</div>";

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
  const motor = s.motor || {};
  const item = (estado, texto) => {
    const icone = { ok: "check_circle", parcial: "radio_button_partial", falta: "radio_button_unchecked" }[estado];
    return '<div class="bv-check ' + estado + '">' + ic(icone, 18) + "<span>" + texto + "</span></div>";
  };
  let ollama;
  if (motor.rodando) ollama = item("ok", "Ollama instalado e rodando em 127.0.0.1");
  else if (motor.instalado) ollama = item("parcial", "Ollama instalado, desligado · o PAULUS liga quando precisar");
  else ollama = item("falta", "Ollama não encontrado · instale pelo site ollama.com; a tela inicial mostra como");
  let modelo;
  if (bv.modelo && bv.modelo !== "nenhum") {
    modelo = item("parcial", "Modelo de IA: " + esc(bv.modelo) + (modeloJaAqui(bv.modelo) ? " · já nesta máquina" : " · baixa ao abrir"));
  } else {
    modelo = item("parcial", "Modelo de IA: escolhido no passo " + ordemBv().indexOf("ia"));
  }
  const docs = s.contratos
    ? item("ok", "Pasta de documentos: " + plural(s.contratos, "documento") + " no Acervo")
    : item("falta", "Pasta de documentos: ainda não apontada");
  const pasta = s.programa || s.pasta || "";
  const texto = "<h1>Olá. Vamos deixar o PAULUS do seu jeito.</h1>" +
    "<p>Poucos passos: o escritório, o acesso à distância, seus dados, o modelo de IA desta máquina e o que conectar. Tudo pode ser mudado depois em Configurações.</p>" +
    '<div class="doc-etiquetas"><span class="etiqueta ok">Software livre · gratuito</span><span class="etiqueta">IA 100% local</span><span class="etiqueta">Cerca de 3 minutos</span></div>';
  const lado = '<div class="bv-cartao"><div class="bv-instalacao">' + logoBv() +
    '<span class="duas-linhas"><b>Instalação concluída</b><small title="' + esc(pasta) + '">PAULUS' + (s.versao ? " " + esc(s.versao) : "") + " · " + esc(pasta) + "</small></span>" +
    '<span class="etiqueta ok">pronto</span></div>' +
    '<div class="bv-checks">' + ollama + modelo + docs + item("falta", "Certificado digital: opcional, para assinar") + "</div>" +
    '<span class="bv-cartao-pe">Sem cadastro em servidor, sem conta obrigatória. O que você preencher fica nesta máquina.</span></div>';
  return [texto, lado];
}

function passoEscritorio() {
  // O PAULUS de equipe (docs/PLANO-EQUIPE.md, E4): este computador e o
  // servidor do escritorio, e a equipe entra pela internet, por convite. O
  // "entrar num escritorio existente" (o vinculo por codigo, que nunca teve
  // servidor) saiu.
  bv.caminho = "criar";
  const texto = "<h1>Qual é o nome do escritório?</h1>" +
    "<p>Este computador passa a ser o PAULUS do escritório: os documentos, o modelo de IA e as contas ficam aqui. Você é o responsável.</p>" +
    infosBv([
      "A equipe não instala nada: cada pessoa entra pela internet, com a própria conta.",
      "Você convida pelo link — pelo WhatsApp, por exemplo — em Configurações › Acesso de fora.",
      "Para isso, ligue o acesso à distância no próximo passo (dá para ligar depois também).",
    ]);
  const lado = '<div class="bv-cartao">' + campoBv("escritorio", "Nome do escritório", bv.escritorio, "data-bv-escritorio", "", "Moura & Associados Advocacia") +
    '<span class="bv-cartao-pe">Aparece nos recibos, no convite da equipe e sugere o endereço do acesso à distância. Dá para mudar em Configurações › Escritório.</span></div>';
  return [texto, lado];
}

/* ----------------------------------------------------- conta Google */

/* O PAULUS do servidor vinculado a conta Google de quem o administra
   (src/vinculo.py, E5). Da para pular e vincular depois, em Configuracoes;
   vinculado, ele abre travado e pede o Google a cada abertura - salvo
   "manter aberto neste computador". */
function passoGoogle() {
  const e = (typeof vinc !== "undefined" && vinc.estado) || null;
  if (!e && typeof lerVinculoGoogle === "function") lerVinculoGoogle().then(() => { if (passoBv() === "google") desenharBoasVindas(); });
  const texto = "<h1>Vincule este PAULUS à sua conta Google.</h1>" +
    "<p>Este computador passa a ser o PAULUS do escritório, e a conta Google é a sua chave: ele abre travado e pede o Google a cada abertura. A equipe entra do mesmo jeito, cada um com a própria conta.</p>" +
    infosBv([
      "O Google só confirma quem é você: nenhum documento vai para ele.",
      "Dá para manter aberto neste computador — e travar de novo quando quiser, em Configurações.",
      "O vínculo é exigido para ligar o acesso de fora e convidar a equipe. Dá para pular e vincular depois.",
    ]);
  const esperando = e && ["aguardando", "trocando", "testando"].includes(e.fase);
  let lado;
  if (e && e.vinculado) {
    lado = '<div class="bv-cartao"><div class="bv-instalacao">' + logoBv() + '<span class="duas-linhas"><b>Vinculado</b><small>' + esc(e.email) +
      '</small></span><span class="etiqueta ok">pronto</span></div>' +
      '<div class="bv-modulo" data-bv-manter="1" role="switch" tabindex="0" aria-checked="' + Boolean(e.manter_aberto) + '">' +
      '<span class="duas-linhas"><b>Manter aberto neste computador</b><small>' +
      (e.manter_aberto ? "abre sem pedir o Google neste computador" : "abre travado e pede o Google a cada abertura") + "</small></span>" +
      '<span class="interruptor-min' + (e.manter_aberto ? " on" : "") + '"></span></div></div>';
  } else {
    lado = '<div class="bv-cartao"><span class="bv-rotulo">CONTA GOOGLE</span>' +
      '<button type="button" class="trava-google" data-bv-google="1"' + (esperando || (e && !e.google) ? " disabled" : "") + ">" +
      (typeof G_DO_GOOGLE !== "undefined" ? G_DO_GOOGLE : "") + (esperando ? "Esperando o Google no navegador…" : "Entrar com Google") + "</button>" +
      (e && e.fase === "erro" ? '<p class="acesso-erro">' + esc(e.mensagem) + "</p>" : "") +
      (e && !e.google ? '<p class="cfg-explica">Esta versão do PAULUS não traz o login do Google.</p>' : "") +
      '<span class="bv-cartao-pe">O navegador abre na página do Google. Depois de entrar, volte para cá.</span></div>';
  }
  return [texto, lado];
}

/* ------------------------------------------------- acesso a distancia */

function passoAcesso() {
  const texto = "<h1>Quer acessar o PAULUS à distância — de casa, do celular, do fórum?</h1>" +
    "<p>Desligado, o PAULUS só abre neste computador. Dá para ligar depois em Configurações › Acesso de fora.</p>" +
    (bv.acesso
      ? infosBv([
        "Este computador precisa ficar ligado, com o PAULUS aberto: é ele que atende.",
        "Documentos e modelo de IA não saem daqui. Só a tela trafega, pela Cloudflare, que a vê descriptografada no caminho.",
        "A conta da Cloudflare é do Atos, que não inspeciona nem registra esse conteúdo.",
        "Cada pessoa entra com a própria conta Google e o código do celular, depois da verificação contra robôs.",
      ])
      : "");
  const chave = '<div class="bv-modulo" data-bv-acesso="1" role="switch" tabindex="0" aria-checked="' + bv.acesso + '">' +
    '<span class="bv-modulo-ic">' + ic("lan", 19) + "</span>" +
    '<span class="duas-linhas"><b>Acesso à distância</b><small>' +
    (bv.acesso ? "ligado · o endereço abaixo leva a este computador" : "desligado · só neste computador") + "</small></span>" +
    '<span class="interruptor-min' + (bv.acesso ? " on" : "") + '"></span></div>';
  if (!bv.acesso) return [texto, '<div class="bv-cartao">' + chave + "</div>"];
  if (!tunelCfg.dados) {
    carregarTunel().then(() => { if (passoBv() === "acesso") desenharBoasVindas(); });
    return [texto, '<div class="bv-cartao">' + chave + '<p class="cfg-explica">Conferindo este computador…</p></div>'];
  }
  const s = tunelCfg.dados.situacao || {};
  const pedido = (tunelCfg.dados.conexao || {}).pedido;
  if (s.conectado_ao_worker && !(pedido && pedido.estado === "concluido")) {
    // Ja conectado (o passeio revisto por #boasvindas): so o endereco.
    const e = "https://" + (s.hostname || "");
    return [texto, '<div class="bv-acesso"><div class="bv-cartao">' + chave + "</div>" +
      '<div class="bv-cartao"><div class="acesso-endereco"><code>' + esc(e) + "</code>" +
      '<button class="com-icone" data-tunel-copiar="' + esc(e) + '">' + ic("content_copy", 16) + "Copiar</button></div>" +
      '<span class="bv-cartao-pe">Desligar, remover e as contas da equipe ficam em Configurações › Acesso de fora.</span></div></div>'];
  }
  conexaoUI.onde = "bv";
  conexaoUI.redesenhar = desenharBoasVindas;
  const v = conexaoUI.conta;
  if (!v.nome && bv.pessoa.nome) v.nome = bv.pessoa.nome;
  if (!v.email && bv.pessoa.email) v.email = bv.pessoa.email;
  return [texto, '<div class="bv-acesso"><div class="bv-cartao">' + chave + "</div>" + '<div class="bv-cartao">' + blocoConexao() + "</div></div>"];
}

/* `modo` e o teclado (inputmode) ou, para CPF e telefone, o tipo do campo
   formatado (js/39-campos.js), que ja traz o teclado certo. */
function campoBv(chave, rotulo, valor, atributo, modo, dica) {
  const formatado = modo === "cpf" || modo === "telefone";
  return '<div class="campo-painel"><label for="bv-' + chave + '">' + rotulo + '</label><input type="text" id="bv-' + chave +
    '" ' + atributo + '="' + chave + '" value="' + esc(formatado ? formatarCampo(modo, valor || "") : (valor || "")) + '"' +
    (formatado ? atributosDoCampo(modo) : (modo ? ' inputmode="' + modo + '"' : "")) +
    (dica ? ' placeholder="' + esc(dica) + '"' : "") + "></div>";
}

function fotoBv(titulo) {
  return '<div class="bv-foto"><span class="bv-iniciais" id="bv-iniciais">' + esc(iniciaisDe(bv.pessoa.nome)) + "</span>" +
    '<span class="duas-linhas"><b>' + titulo + "</b><small>saem do nome; a foto fica para Configurações › Meus dados</small></span></div>";
}

function passoDados() {
  const p = bv.pessoa;
  const texto = "<h1>Quem vai usar o PAULUS?</h1>" +
    "<p>Nome, OAB e endereço entram na qualificação das partes, no papel timbrado e no selo de assinatura. Nada disso é enviado para fora.</p>";
  const lado = '<div class="bv-cartao">' + fotoBv("Iniciais") +
    '<div class="bv-grade">' + campoBv("nome", "Nome completo", p.nome, "data-bv-pessoa") + campoBv("oab", "OAB", p.oab, "data-bv-pessoa", "", "GO 00000") +
    campoBv("cpf", "CPF", p.cpf, "data-bv-pessoa", "cpf", "000.000.000-00") + campoBv("telefone", "Telefone", p.telefone, "data-bv-pessoa", "telefone", "(62) 99999-8888") +
    campoBv("email", "E-mail", p.email, "data-bv-pessoa", "email") + campoBv("endereco", "Endereço", p.endereco, "data-bv-pessoa") + "</div></div>";
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
  if (pronto && m.na_bateria) linhas.push(["Energia", "na bateria: na tomada o PAULUS responde mais rápido"]);
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
    "<small>mede o modelo desta máquina uma vez (cerca de um minuto), manda as medidas ao site do PAULUS e recebe as de outras; nada do escritório · " +
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
  const ligados = 1 + MODULOS_BV.filter(([id]) => bv.modulos[id]).length;
  const texto = "<h1>O que o escritório vai usar?</h1>" +
    "<p>O Assistente é fixo. Os demais módulos podem ser ligados ou desligados depois em Configurações › Módulos, sem reinstalar. O que você desligar some do menu desta máquina.</p>" +
    '<div class="bv-contagem"><span>Módulos ligados</span><span>' + ligados + " de " + (MODULOS_BV.length + 1) + "</span></div>";
  const linha = (id, icone, nome, desc, fixo) => {
    const ligado = fixo || bv.modulos[id];
    return '<div class="bv-modulo' + (fixo ? " fixo" : "") + '"' + (fixo ? "" : ' data-bv-modulo="' + id + '" role="switch" tabindex="0" aria-checked="' + Boolean(ligado) + '"') + ">" +
      '<span class="bv-modulo-ic">' + ic(icone, 19) + "</span>" +
      '<span class="duas-linhas"><b>' + nome + "</b><small>" + desc + "</small></span>" +
      (fixo ? '<span class="bv-fixo">fixo</span>' : '<span class="interruptor-min' + (ligado ? " on" : "") + '"></span>') + "</div>";
  };
  const lado = '<div class="bv-grupos"><span class="bv-rotulo bv-lista-titulo">NÚCLEO</span>' +
    linha("assistente", "forum", "Assistente", "Conversa, pesquisa no acervo e rascunhos", true) +
    '<span class="bv-rotulo bv-lista-titulo">ESCRITÓRIO</span>' +
    MODULOS_BV.map(([id, icone, nome, desc]) => linha(id, icone, nome, desc, false)).join("") + "</div>";
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

function passoConexoes() {
  const texto = "<h1>O que você quer conectar? Tudo opcional.</h1>" +
    "<p>O e-mail do escritório pode ser lido e respondido daqui, com envio passando por Aprovações. A IA continua local: o PAULUS lê aqui e não devolve nada sem o seu sim.</p>" +
    infosBv([
      "A autorização do e-mail fica nesta máquina, cifrada pela sua conta do Windows.",
      "Dá para desconectar a qualquer hora em E-mail › Contas.",
    ]);
  const ligado = Boolean(bv.google);
  const desc = ligado
    ? "Conectada · " + esc(bv.google) + " · a Agenda e o Drive se conectam em Configurações › Conexões"
    : (bv.imap ? "Outro provedor: o PAULUS abre em E-mail › Contas ao terminar" : "Gmail · Agenda e Meet · Drive");
  const lado = '<div class="bv-conta' + (ligado ? " on" : "") + '" data-bv="google" role="switch" tabindex="0" aria-checked="' + ligado + '">' +
    '<span class="bv-fabricante">' + eoMarca("google") + "</span>" +
    '<span class="duas-linhas"><b>Conta Google</b><small>' + desc + "</small></span>" +
    '<span class="interruptor-min' + (ligado ? " on" : "") + '"></span></div>';
  return [texto, lado];
}

function janelaEntrarBv() {
  const botoes = botoesDeLoginOAuth(bv.oauth);
  return '<div class="bv-veu" data-bv="fechar-entrar"><div class="bv-entrar-coluna" data-bv-parar="1">' +
    '<div class="bv-entrar" id="bv-entrar"><h2>Entrar</h2>' +
    (botoes || '<p class="bv-cartao-pe">Esta versão do PAULUS não traz o login do Google. Use outro provedor.</p>') +
    '<button type="button" class="bv-ligacao" data-bv="imap">Outro provedor (IMAP e SMTP)</button></div>' +
    '<div class="bv-entrar-notas"><span>Leio só o que você abre</span><span>Prazos viram sugestão na Agenda</span></div>' +
    '<span class="bv-entrar-notas">Nada sai sem passar por Aprovações</span></div></div>';
}

function passoAtualizacoes() {
  const a = bv.atualizacoes || { verificar: true, avisar_antes: true };
  const texto = "<h1>Como o PAULUS deve se atualizar?</h1>" +
    "<p>Uma vez por dia, o PAULUS lê em paulus.ia.br se há versão nova — só essa leitura; nada seu vai junto. A versão nova vem do instalador oficial, conferido antes de abrir, e os dados do escritório ficam como estão.</p>";
  const linha = (id, titulo, desc, ligado, bloqueado) =>
    '<div class="bv-modulo' + (bloqueado ? " fixo" : "") + '"' + (bloqueado ? "" : ' data-bv-atu="' + id + '" role="switch" tabindex="0" aria-checked="' + Boolean(ligado) + '"') + ">" +
    '<span class="duas-linhas"><b>' + titulo + "</b><small>" + desc + "</small></span>" +
    '<span class="interruptor-min' + (ligado ? " on" : "") + '"></span></div>';
  const lado = '<div class="bv-cartao"><div class="bv-grupos">' +
    linha("verificar", "Verificar atualizações uma vez por dia", "desligado, o PAULUS não procura versão nova; dá para verificar em Configurações › Apoio e versão", a.verificar) +
    linha("avisar_antes", "Avisar antes de instalar", a.avisar_antes
      ? "a faixa do topo avisa; você instala quando quiser"
      : "a versão nova baixa sozinha e se instala quando você fechar o PAULUS", a.avisar_antes, !a.verificar) + "</div>" +
    '<div class="bv-apoio"><b>Você também pode apoiar o projeto</b><p>O PAULUS é gratuito e mantido por quem usa. Sem pressa: dá para fazer isso depois, em Apoiar, no menu.</p></div></div>';
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
    "<p>O primeiro é o código do responsável: ele gera no PAULUS dele e vincula esta máquina ao escritório. O segundo é gerado aqui e identifica você; o responsável digita em Configurações › Escritório e vínculos.</p>" +
    infosBv([
      "O código do responsável vale por 15 minutos.",
      "Enquanto ele não adiciona você, o PAULUS abre com o que é só desta máquina; o que depende do escritório fica bloqueado.",
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
        await entrarNoGoogleDoVinculo("vincular", () => { if (passoBv() === "google") desenharBoasVindas(); });
      } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    };
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
        avisoCert("já conectado: para desligar ou remover, use Configurações › Acesso de fora");
        return;
      }
      bv.acesso = !bv.acesso;
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
  if (qual === "google") {
    if (bv.google) { avisoCert("para desconectar, use E-mail › Contas depois de abrir o PAULUS"); return; }
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
    copiarTexto("Meu código para entrar no PAULUS do escritório: " + bv.vinculo.meuCodigo + " (" + (bv.pessoa.nome || "") + ")",
      "mensagem copiada — cole na conversa com o responsável no WhatsApp");
    return;
  }
  const passo = passoBv();
  const ultimo = bv.passo === ordemBv().length - 1;
  // Continuar grava o que o passo tem, e so o que tem. CPF ou telefone que
  // nao fecha para aqui, com o aviso no campo (Pular por agora segue).
  if (passo === "dados") {
    const errado = camposInvalidos($("boas-vindas"));
    if (errado) { errado.focus(); avisoCert("confira o campo marcado — ou deixe em branco e preencha depois"); return; }
    $("boas-vindas").querySelectorAll("[data-bv-pessoa]").forEach((i) => { bv.pessoa[i.dataset.bvPessoa] = i.value; });
    await gravarBoasVindas({ pessoa: bv.pessoa });
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
  if (passo === "acesso" && bv.acesso) {
    const d = tunelCfg.dados || {};
    const pedido = (d.conexao || {}).pedido;
    if (pedido && pedido.estado === "esperando") avisoCert("a confirmação continua no navegador; o endereço aparece em Configurações › Acesso de fora quando terminar", { dura: 7000 });
    else if (!(d.situacao || {}).conectado_ao_worker) avisoCert("o acesso à distância ficou desligado; dá para ligar em Configurações › Acesso de fora");
  }
  if (ultimo) {
    if (bv.caminho === "entrar") {
      if ((bv.vinculo.codigoResponsavel || "").length !== 6) { avisoCert("digite os 6 caracteres do código do responsável"); $("bv-codigo").focus(); return; }
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
    if (bv.caminho === "entrar") avisoCert("pedido guardado nesta máquina — o PAULUS abre em modo limitado até o responsável validar");
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
