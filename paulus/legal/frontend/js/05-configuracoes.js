/* ------------------------------------------------------ configuracoes */
/*
   Configuracoes (docs/ui/03-telas-desktop.md, A13): menu interno a esquerda
   e nove secoes. Meus dados, o modelo, os limites da IA, o ritmo, o tema e
   os codigos de lei sao de verdade e gravam em data/preferencias.json; o
   que ainda nao tem motor - foto, senha por pessoa, vinculo por codigo,
   aprendizado por arquivos, feedback enviado, apoio pago, atualizacao
   automatica - diz isso na tela. Habilidades, Conexoes e Desempenho, que
   eram telas proprias, viraram secoes daqui.
*/

const cfg = {
  secao: "perfil", prefs: null, status: null, rascunho: null, sujo: false,
  recursos: null, historico: [], relogio: null, medida: "cpu",
  cx: null, contas: null, cert: null, acoes: [], hab: null, grupoHab: "",
  tema: "claro", apoio: { valor: 40, recorrencia: "mensal", forma: "pix" },
  feedback: { tipo: "bug", onde: "", titulo: "", texto: "", tecnico: true, contato: true },
};

const CFG_JSON = { "Content-Type": "application/json" };

const CFG_SECOES = [
  ["perfil", "person", "Meus dados", "Meus dados · escritório · entrar"],
  ["assistente", "memory", "Assistente e modelo", "Modelo local, limites da IA, cache e índice"],
  ["desempenho", "speed", "Desempenho", "Medido na sua máquina · últimos 60 segundos"],
  ["conexoes", "hub", "Conexões", "Serviços conectados e o que sai desta máquina"],
  ["vinculos", "lan", "Escritório e vínculos", "Quem faz parte do escritório, pedidos de vinculação e moderação · rede local"],
  ["aprendizado", "school", "Aprendizado", "Ensinar o PAULUS com PDFs, modelos e regras escritas à mão"],
  ["aparencia", "palette", "Aparência e atalhos", "Tema, fontes, densidade e atalhos"],
  ["feedback", "rate_review", "Feedback", "Elogios, sugestões, correções e bugs · com anexos"],
  ["plano", "favorite", "Plano e apoio", "Software livre · apoio, doação e atualizações"],
  ["lixeira", "delete", "Lixeira", "O que foi apagado nos últimos 30 dias · restaurar ou apagar de vez"],
];

const CFG_ICONE_HAB = {
  perguntar: "forum", buscar: "search", abrir: "folder_open", classificar: "format_list_bulleted",
  organizar: "drive_file_move", vencimentos: "event_upcoming", ocr: "visibility", redigir: "edit_note", assinar: "draw",
};

/* Os destinos antigos continuam existindo; cada um abre a secao que o
   substituiu. */
function mostrarHabilidades() { return mostrarConfig("aprendizado"); }
function mostrarMaquina() { return mostrarConfig("desempenho"); }
function mostrarConexoes() { return mostrarConfig("conexoes"); }

async function mostrarConfig(secao) {
  const externo = Boolean(secao);
  if (secao) cfg.secao = secao;
  pararMedicao();
  abrirTela("Configurações", { cheia: true });
  marcarDestino("config");
  // Com as preferencias ja lidas, a tela pinta na hora e o que faltar chega
  // em seguida: ler o status do Ollama pode levar segundos quando ele esta
  // desligado, e a troca de secao nao pode esperar por isso.
  if (cfg.prefs) {
    desenharConfig();
  } else {
    $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">lendo…</p></div></div>';
    atualizarPostura();
  }
  const versao = (cfg.versao || 0) + 1;
  cfg.versao = versao;
  try {
    if (!cfg.prefs || externo || cfg.recarregar) {
      const [p, s] = await Promise.all([
        fetch("/api/preferencias").then((r) => r.json()),
        fetch("/api/status").then((r) => r.json()).catch(() => null),
      ]);
      if (versao !== cfg.versao) return;
      cfg.prefs = p;
      cfg.status = s;
      cfg.recarregar = false;
      if (!cfg.sujo) cfg.rascunho = rascunhoDe(p.preferencias, p.modelo_atual);
    }
    await carregarSecao();
    if (versao !== cfg.versao) return;
  } catch (err) {
    if (!cfg.prefs) {
      $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">não consegui ler: ' +
        esc(String(err)) + "</p></div></div>";
    }
    return;
  }
  // A pessoa pode ter ido para outra tela enquanto o status chegava.
  if ($("conversa-titulo").textContent === "Configurações") desenharConfig();
}

function rascunhoDe(pr, modelo) {
  const e = pr.escritorio || {};
  return {
    pessoa: Object.assign({}, pr.pessoa || {}),
    autonomia: Object.assign({}, pr.autonomia || {}),
    escritorio: { nome: e.nome || "", cnpj: e.cnpj || "", oab: e.oab || "", rodape: e.rodape || "" },
    modelo: modelo || pr.modelo || "",
    timbre_no_pdf: Boolean(pr.timbre_no_pdf),
    devagar: Boolean(pr.devagar),
    animacoes_reduzidas: Boolean(pr.animacoes_reduzidas),
  };
}

/* Cada secao busca so o que ela mostra; as outras nao pagam por isso. */
async function carregarSecao() {
  const pega = (url) => fetch(url).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  if (cfg.secao === "conexoes") {
    const [cx, contas, cert, acoes] = await Promise.all([
      pega("/api/conexoes"), pega("/api/email/contas"), pega("/api/certificado"), pega("/api/relatorios/acoes?limite=60"),
    ]);
    cfg.cx = cx; cfg.contas = contas; cfg.cert = cert; cfg.acoes = (acoes && acoes.acoes) || [];
  } else if (cfg.secao === "aprendizado") {
    const [hab, ctx] = await Promise.all([pega("/api/habilidades"), pega("/api/contextos")]);
    cfg.hab = hab;
    cfg.ctx = ctx;
  } else if (cfg.secao === "plano") {
    const acoes = await pega("/api/relatorios/acoes?limite=60");
    cfg.acoes = (acoes && acoes.acoes) || [];
  } else if (cfg.secao === "desempenho") {
    cfg.recursos = await pega("/api/recursos");
  } else if (cfg.secao === "assistente") {
    cfg.voz = await pega("/api/voz");
  } else if (cfg.secao === "lixeira") {
    cfg.lixo = await pega("/api/lixeira");
  }
}

function desenharConfig() {
  cabecalhoConfig();
  const menu = CFG_SECOES.map(([id, icone, rotulo]) => {
    const classe = "cfg-item" + (id === cfg.secao ? " ativa" : "");
    return '<button class="' + classe + '" data-cfg-secao="' + id + '">' + ic(icone, 18) + "<span>" + rotulo + "</span></button>";
  }).join("");
  const nome = ((cfg.rascunho || {}).pessoa || {}).nome || "";
  let secao;
  if (cfg.secao === "assistente") secao = secaoAssistente();
  else if (cfg.secao === "desempenho") secao = secaoDesempenho();
  else if (cfg.secao === "conexoes") secao = secaoConexoes();
  else if (cfg.secao === "vinculos") secao = secaoVinculos();
  else if (cfg.secao === "aprendizado") secao = secaoAprendizado();
  else if (cfg.secao === "aparencia") secao = secaoAparencia();
  else if (cfg.secao === "feedback") secao = secaoFeedback();
  else if (cfg.secao === "plano") secao = secaoPlano();
  else if (cfg.secao === "lixeira") secao = secaoLixeira();
  else secao = secaoPerfil();

  $("centro").innerHTML = '<div class="acervo sem-painel cfg-tela" id="cfg-tela"><div class="cfg-corpo">' +
    '<nav class="cfg-menu">' + menu + '<span class="cfg-risco"></span>' +
    '<button class="cfg-item" data-cfg-manual="1">' + ic("description", 18) + "<span>Manual do sistema</span></button>" +
    '<button class="cfg-item" data-cfg-sair="1">' + ic("logout", 18) + "<span>Sair" + (nome ? " · " + esc(nome.split(" ")[0]) : "") + "</span></button></nav>" +
    '<div class="cfg-secao">' + secao + "</div></div></div>";
  ligarConfig();
  atualizarPostura();
  if (cfg.secao === "desempenho") comecarMedicao();
  if (cfg.secao === "assistente") blocoLeis();
}

function cabecalhoConfig() {
  const achada = CFG_SECOES.find((s) => s[0] === cfg.secao) || CFG_SECOES[0];
  $("conversa-titulo").textContent = "Configurações";
  $("conversa-meta").textContent = achada[3];
  $("acoes-tela").innerHTML = '<button data-cfg-descartar="1"' + (cfg.sujo ? "" : " disabled") + ">Descartar</button>" +
    '<button class="primario com-icone" data-cfg-salvar="1"' + (cfg.sujo ? "" : " disabled") + ">" + ic("check", 16) + "Salvar alterações</button>";
  $("nav-tela").innerHTML = "";
}

function marcarConfigSuja() {
  cfg.sujo = true;
  document.querySelectorAll("[data-cfg-salvar], [data-cfg-descartar]").forEach((b) => { b.disabled = false; });
}

/* --------------------------------------------------------- pecas */

function cartaoCfg(titulo, meta, corpo, extra) {
  const classe = "cfg-cartao" + (extra ? " " + extra : "");
  return '<div class="' + classe + '"><div class="cfg-cartao-cabeca"><span>' + titulo + "</span>" + (meta || "") + "</div>" +
    '<div class="cfg-cartao-corpo">' + corpo + "</div></div>";
}

function metaCfg(texto) { return "<small>" + esc(texto) + "</small>"; }

function pontoCfg(texto, tom) {
  const classe = "fin-meta-ponto" + (tom ? " " + tom : "");
  return '<small><span class="' + classe + '"><i></i>' + esc(texto) + "</span></small>";
}

function campoCfg(chave, rotulo, valor, dica, extra) {
  return '<div class="ag-campo"><label>' + esc(rotulo) + '</label><input type="text" data-cfg-campo="' + chave + '" value="' + esc(valor || "") + '"' +
    (dica ? ' placeholder="' + esc(dica) + '"' : "") + (extra || "") + "></div>";
}

function ligaCfg(chave, titulo, sub, ligada, presa) {
  const classe = "cfg-liga" + (ligada ? " on" : "") + (presa ? " presa" : "");
  return '<div class="' + classe + '"' + (chave ? ' data-cfg-liga="' + chave + '"' : "") + '><span class="duas-linhas"><b>' + esc(titulo) + "</b>" +
    (sub ? "<small>" + esc(sub) + "</small>" : "") + "</span><i></i></div>";
}

function chaveCfg(rotulo, valor, tom) {
  const classe = tom || "";
  return '<div class="chave-valor"><span>' + esc(rotulo) + '</span><b class="' + classe + '">' + esc(valor) + "</b></div>";
}

function valorDoRascunho(chave) {
  const partes = chave.split(".");
  let v = cfg.rascunho;
  for (const p of partes) v = v == null ? undefined : v[p];
  return v;
}

function porNoRascunho(chave, valor) {
  const partes = chave.split(".");
  let alvo = cfg.rascunho;
  for (const p of partes.slice(0, -1)) { if (!alvo[p]) alvo[p] = {}; alvo = alvo[p]; }
  alvo[partes[partes.length - 1]] = valor;
}

/* ------------------------------------------------------ meus dados */

function secaoPerfil() {
  const r = cfg.rascunho;
  const p = r.pessoa;
  const e = r.escritorio;
  const foto = marcaDaTela("foto");
  const meus = '<div class="cfg-foto">' + avatarDoPerfil(p.nome) + "<div>" +
    '<div class="cfg-botoes"><button data-cfg-marca="foto">' + ic("photo_camera", 16) + (foto.tem ? "Trocar foto" : "Enviar foto") + "</button>" +
    (foto.tem ? '<button data-cfg-marca-tirar="foto">' + ic("close", 16) + "Remover</button>" : "") + "</div>" +
    '<span class="cfg-explica">PNG ou JPG · até 4 MB · fica nesta máquina e aparece no seu avatar</span></div></div>' +
    '<div class="cfg-campos">' + campoCfg("pessoa.nome", "Nome completo", p.nome) +
    '<div class="ag-duas">' + campoCfg("pessoa.cpf", "CPF", p.cpf, "000.000.000-00") + campoCfg("pessoa.oab", "OAB", p.oab, "GO 00000") + "</div>" +
    '<div class="ag-duas">' + campoCfg("pessoa.telefone", "Telefone", p.telefone, "(62) 90000-0000") + campoCfg("pessoa.email", "E-mail", p.email) + "</div>" +
    campoCfg("pessoa.endereco", "Endereço profissional", p.endereco) + "</div>" +
    '<div class="cfg-sub"><b>Documentos e anexos</b>' +
    '<p class="cfg-explica">Carteira da OAB e comprovantes anexados à sua ficha ficam para a versão com equipe. Por enquanto, os seus documentos moram no Acervo.</p>' +
    '<div class="cfg-botoes"><button class="adiante" data-cfg-adiante="Anexar documento ao perfil ainda não existe — guarde no Acervo">' + ic("attach_file", 16) + "Anexar documento</button></div></div>" +
    '<div class="cfg-sub"><b>Nos PDFs</b>' +
    ligaCfg("timbre_no_pdf", "Papel timbrado nos PDFs", "nome, OAB, endereço e contato no alto de todo PDF gerado aqui", r.timbre_no_pdf) +
    '<p class="cfg-explica" id="cfg-timbre-falta">' + esc(avisoDoTimbre()) + "</p></div>";

  const logo = marcaDaTela("logo");
  const escritorio = '<div class="cfg-foto"><span class="cfg-logo' + (logo.tem ? " cfg-logo-propria" : "") + '">' +
    '<img src="' + (logo.tem ? "/marca/logo.png?v=" + logo.versao : "/img/paulus-logo.svg") + '" alt=""></span><div>' +
    '<div class="cfg-botoes"><button data-cfg-marca="logo">' + ic("upload", 16) + (logo.tem ? "Trocar logo" : "Enviar logo") + "</button>" +
    (logo.tem ? '<button data-cfg-marca-tirar="logo">' + ic("close", 16) + "Remover</button>" : "") + "</div>" +
    '<span class="cfg-explica">' + (logo.tem ? "no alto do papel timbrado · PNG com fundo transparente fica melhor" :
      "entra no alto do papel timbrado; o selo de assinatura usa o desenho feito em Assinatura") + "</span></div></div>" +
    '<div class="cfg-campos">' + campoCfg("escritorio.nome", "Nome do escritório", e.nome, "como aparece nos recibos") +
    '<div class="ag-duas">' + campoCfg("escritorio.cnpj", "CNPJ", e.cnpj, "00.000.000/0001-00") + campoCfg("escritorio.oab", "OAB da sociedade", e.oab, "GO 0000") + "</div>" +
    campoCfg("escritorio.rodape", "Rodapé dos documentos", e.rodape, "OAB/GO 00000 · Goiânia · GO") + "</div>" +
    '<p class="cfg-explica">O nome do escritório entra nos recibos da folha; o resto fica guardado para o timbre.</p>' +
    '<div class="cfg-sub"><b>Entrar</b>' +
    ligaCfg("", "Digital do notebook", "em breve · hoje o PAULUS abre com a sua conta do Windows", false, true) +
    ligaCfg("", "Pedir senha ao voltar da pausa", "em breve", false, true) +
    '<div class="cfg-botoes"><button class="adiante" data-cfg-adiante="Senha própria fica para a versão com equipe — hoje o PAULUS abre com a sua conta do Windows">' + ic("key", 16) + "Redefinir senha</button>" +
    '<button class="adiante" data-cfg-adiante="Perfis por pessoa nesta máquina ficam para a versão com equipe">' + ic("group", 16) + "Perfis desta máquina</button></div></div>";

  return '<div class="cfg-grade">' + cartaoCfg("Meus dados", metaCfg("usados nos documentos e no selo"), meus) +
    cartaoCfg("Escritório", metaCfg("timbre, selo e documentos"), escritorio) + "</div>";
}

/* Ensinar por arquivo: o programa le, escreve a proposta e enche o formulario.
   Guardar continua sendo um clique da pessoa - o que entra na cabeca do
   assistente ela leu antes. */
function escolherArquivoParaEnsinar() {
  const campo = document.createElement("input");
  campo.type = "file";
  campo.accept = ".pdf,.docx,.txt,.md";
  campo.onchange = () => {
    const arquivo = campo.files && campo.files[0];
    if (arquivo) lerArquivoParaEnsinar(arquivo);
  };
  campo.click();
}

async function lerArquivoParaEnsinar(arquivo) {
  cfg.lendoArquivo = arquivo.name;
  desenharConfig();
  const corpo = new FormData();
  corpo.append("arquivo", arquivo, arquivo.name);
  let r;
  try {
    r = await fetch("/api/contextos/ler", { method: "POST", body: corpo });
  } catch (err) {
    cfg.lendoArquivo = "";
    desenharConfig();
    avisoCert("não consegui ler o arquivo", { tom: "erro" });
    return;
  }
  cfg.lendoArquivo = "";
  if (!r.ok) { desenharConfig(); avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const d = await r.json();
  cfg.ensinando = { id: null, titulo: d.titulo, texto: d.texto, gaveta: (cfg.ensinando || {}).gaveta || "" };
  desenharConfig();
  avisoCert(d.aviso, { tom: d.pelo_modelo ? "ok" : "erro" });
  const campo = $("cfg-ensinar-texto");
  if (campo) { campo.focus(); campo.setSelectionRange(campo.value.length, campo.value.length); }
}

/* A lista de lembretes de novo do servidor: apagar e restaurar mexem nela. */
async function recarregarLembretes() {
  try {
    cfg.ctx = await (await fetch("/api/contextos")).json();
  } catch (err) { /* sem lista, a secao fica com a que tinha */ }
  if (cfg.secao === "aprendizado") desenharConfig();
}

/* A foto e a logo desta maquina, do jeito que /api/preferencias devolve. */
function marcaDaTela(tipo) {
  return ((cfg.prefs && cfg.prefs.marca) || {})[tipo] || { tem: false, versao: 0 };
}

/* O avatar do perfil: a foto, quando existe; as iniciais, quando nao. */
function avatarDoPerfil(nome) {
  const foto = marcaDaTela("foto");
  return '<span class="cad-avatar">' + (foto.tem
    ? '<img src="/marca/foto.png?v=' + foto.versao + '" alt="">'
    : esc(iniciaisDoRemetente(nome || "?"))) + "</span>";
}

/* Escolher o arquivo no computador. O campo nasce e morre aqui: um input
   escondido no HTML guardaria o arquivo escolhido entre uma vez e outra. */
function escolherMarca(tipo) {
  const campo = document.createElement("input");
  campo.type = "file";
  campo.accept = "image/png,image/jpeg,image/webp";
  campo.onchange = () => {
    const arquivo = campo.files && campo.files[0];
    if (arquivo) enviarMarca(tipo, arquivo);
  };
  campo.click();
}

async function enviarMarca(tipo, arquivo) {
  const corpo = new FormData();
  corpo.append("arquivo", arquivo, arquivo.name || (tipo + ".png"));
  const r = await fetch("/api/marca/" + tipo, { method: "POST", body: corpo });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const d = await r.json();
  if (cfg.prefs) cfg.prefs.marca = d.marca;
  desenharConfig();
  carregarUsuario();
  avisoCert(tipo === "foto" ? "foto guardada" : "logo guardada", { tom: "ok" });
}

/* Ligar o timbre com "Meus dados" em branco nao poe nada no papel: o nome e
   o que abre o timbre. A tela diz isso na hora de decidir. */
function avisoDoTimbre() {
  const r = cfg.rascunho;
  if (!r.timbre_no_pdf) return "Desligado: minuta interna com timbre parece peça protocolada. Ligue quando os dados acima estiverem completos.";
  const p = r.pessoa;
  if (!String(p.nome || "").trim()) return "Sem o nome completo, o timbre não sai: OAB e endereço sozinhos no alto da folha não são um timbre.";
  const campos = ["nome", "cpf", "oab", "telefone", "email", "endereco"];
  const cheios = campos.filter((c) => String(p[c] || "").trim()).length;
  return cheios + " de " + campos.length + " campos preenchidos entram no alto de cada PDF. O que estiver em branco é omitido — não sai rótulo vazio.";
}

/* ------------------------------------------------ assistente e modelo */

/* O modelo de voz que transcreve as gravacoes: qual esta em uso, qual esta
   baixado, e o botao de baixar o outro. */
function cartaoDaVozCfg() {
  const v = cfg.voz;
  if (!v) return '<p class="cfg-texto">não consegui ler o estado do modelo de voz.</p>';
  const lista = (v.modelos || []).map((m) => {
    const emUso = m.nome === v.modelo;
    const classe = "cfg-modelo" + (emUso ? " on" : "");
    const gb = String(Math.round(m.mb / 100) / 10).replace(".", ",") + " GB";
    let acao = "";
    if (v.baixando === m.nome) acao = '<span class="cfg-pill">baixando · ' + (v.baixado_mb || 0) + " MB</span>";
    else if (!m.instalado) acao = '<button data-cfg-voz-baixar="' + m.nome + '">' + ic("download", 16) + "Baixar</button>";
    else if (!emUso) acao = '<button data-cfg-voz-usar="' + m.nome + '">Usar este</button>';
    return '<div class="' + classe + '"><i></i><span class="duas-linhas"><b>' + esc(m.rotulo) + '</b><small class="cfg-voz-nota">' + esc(m.nota) +
      (m.instalado ? " · baixado" : " · não baixado") + "</small></span><small>" + gb + "</small>" +
      (emUso && m.instalado ? '<span class="cfg-pill ok">em uso</span>' : (emUso ? '<span class="cfg-pill acc">escolhido · falta baixar</span>' : "")) + acao + "</div>";
  }).join("");
  return '<div class="cfg-voz"><div class="cfg-modelos">' + lista + "</div>" +
    '<p class="cfg-explica">Transcreve as gravações nesta máquina, em CPU, com ' + (v.nucleos || 0) + " núcleos — o áudio não sai do computador. " +
    (v.erro ? esc(v.erro) + " " : "") + "Os modelos ficam em " + esc(v.pasta || "") + ".</p></div>";
}

function secaoAssistente() {
  const r = cfg.rascunho;
  const s = cfg.status || {};
  const modelos = (cfg.prefs.modelos || []).slice();
  if (r.modelo && modelos.indexOf(r.modelo) < 0) modelos.unshift(r.modelo);
  const ligado = Boolean(s.ollama);
  const lista = modelos.length
    ? modelos.map((m) => {
      const emUso = m === r.modelo;
      const classe = "cfg-modelo" + (emUso ? " on" : "");
      const tamanho = emUso && s.tamanho_gb ? String(s.tamanho_gb).replace(".", ",") + " GB" : "";
      return '<div class="' + classe + '" data-cfg-modelo="' + esc(m) + '"><i></i><span class="duas-linhas"><b>' + esc(m) + "</b><small>" +
        (emUso ? "responde as perguntas · instalado no Ollama" : "instalado no Ollama") + "</small></span>" +
        (tamanho ? "<small>" + esc(tamanho) + "</small>" : "") + (emUso ? '<span class="cfg-pill ok">em uso</span>' : "") + "</div>";
    }).join("")
    : '<p class="cfg-texto">Nenhum modelo encontrado no Ollama. Instale um com <code>ollama pull llama3.2:3b</code> e abra esta tela de novo.</p>';

  const assistente = '<div class="cfg-campos"><div class="ag-campo"><label>Modelo em uso</label><select data-cfg-select="modelo">' +
    (modelos.length ? modelos.map((m) => '<option value="' + esc(m) + '"' + (m === r.modelo ? " selected" : "") + ">" + esc(m) + "</option>").join("")
      : '<option value="">nenhum modelo encontrado</option>') + "</select></div></div>" +
    '<div class="cfg-modelos">' + lista + "</div>" +
    '<p class="cfg-explica">Trocar o modelo vale para a próxima pergunta. Modelo maior responde melhor e demora mais. Baixar outro por aqui fica para depois: por enquanto é <code>ollama pull nome</code> no terminal.</p>' +
    '<div class="cfg-sub"><b>Modelo de voz</b>' + cartaoDaVozCfg() + "</div>" +
    '<div class="cfg-sub"><b>Ritmo</b>' +
    ligaCfg("devagar", "Ir devagar quando eu usar o PC", "espera a máquina desafogar antes de começar cada documento; a leitura demora mais e o computador continua seu", r.devagar) + "</div>" +
    '<div class="cfg-sub"><b>Onde ficam os documentos</b><div class="cfg-campos"><div class="ag-campo"><label>Pasta do acervo</label><input type="text" readonly value="' + esc(cfg.prefs.pasta_acervo || "") + '"></div></div>' +
    '<p class="cfg-explica">Trechos por pergunta, temperatura e idioma seguem o padrão do programa; ajustar por aqui fica para depois.</p></div>';

  const limites = '<div class="cfg-campos">' + (cfg.prefs.autonomia_opcoes || []).map((a) => {
    const ligada = a.travada ? false : Boolean(r.autonomia[a.chave]);
    return ligaCfg(a.travada ? "" : "autonomia." + a.chave, a.titulo, a.explica, ligada, a.travada);
  }).join("") + "</div>" +
    '<p class="cfg-explica">Desligado significa que a ação para na fila de Aprovações e espera o seu sim. Ligado significa que ela acontece direto.</p>' +
    '<div class="cfg-sub"><b>Cache e índice</b><div class="cfg-chaves">' +
    chaveCfg("Documentos indexados", String(s.contratos || 0)) +
    chaveCfg("Trechos no índice", String(s.trechos || 0)) +
    chaveCfg("Cache de extração", "local · SHA-1") +
    chaveCfg("Assistente", ligado ? "Ollama conectado" : (s.mensagem || "Ollama desligado"), ligado ? "" : "acc") + "</div>" +
    '<div class="cfg-botoes"><button data-cfg-reindexar="1">' + ic("sync", 16) + "Reindexar tudo</button>" +
    '<button data-cfg-cache="1">' + ic("delete", 16) + "Limpar cache</button></div></div>" +
    '<div class="cfg-sub"><b>Códigos de lei</b><div id="cfg-leis"><p class="nota">abrindo os códigos…</p></div></div>';

  return '<div class="cfg-grade">' +
    cartaoCfg("Assistente e modelo", pontoCfg(ligado ? "Ollama conectado · 127.0.0.1:11434" : "Ollama desligado", ligado ? "ok" : "acc"), assistente) +
    cartaoCfg("Limites da IA", metaCfg("o que o assistente pode fazer sozinho"), limites) + "</div>";
}

/* Os codigos de lei: o que esta no disco e como trazer mais. */
async function blocoLeis() {
  const alvo = $("cfg-leis");
  if (!alvo) return;
  let d;
  try { d = await (await fetch("/api/leis")).json(); } catch (err) { alvo.innerHTML = '<p class="cfg-explica">não consegui abrir os códigos.</p>'; return; }
  alvo.innerHTML = '<p class="cfg-explica">' + esc(d.porque) + "</p>" +
    '<div class="cfg-linhas">' + (d.codigos || []).map((c) =>
      '<div class="cfg-lei"><span class="duas-linhas"><b>' + esc(c.nome) + "</b><small>" + esc(c.lei) +
      (c.instalado ? " · " + plural(c.artigos, "artigo") + " · " + esc(quandoCurto(c.importado_em)) : " · não instalado") + "</small></span>" +
      (c.instalado ? '<span class="cfg-pill ok">instalado</span><button data-cfg-tirar-lei="' + esc(c.codigo) + '">Remover</button>' : '<span class="cfg-pill mute">falta</span>') +
      "</div>").join("") + "</div>" +
    '<p class="cfg-explica">' + esc(d.como_baixar) + "</p>" +
    '<div class="cfg-botoes"><button data-cfg-lei-pasta="1">' + ic("folder_open", 16) + "Importar de uma pasta</button>" +
    '<button data-cfg-lei-arquivo="1">' + ic("upload", 16) + 'Escolher um arquivo</button></div><div id="lei-saida"></div>';

  alvo.querySelectorAll("[data-cfg-tirar-lei]").forEach((b) => {
    b.onclick = async () => {
      if (!(await confirmar({ titulo: "Remover este código?", contexto: "Configurações › Códigos de lei", texto: "A citação volta a ficar indisponível até você importar de novo.", confirmar: "Remover", perigo: true }))) return;
      await fetch("/api/leis/" + b.dataset.cfgTirarLei, { method: "DELETE" });
      blocoLeis();
    };
  });
  alvo.querySelector("[data-cfg-lei-pasta]").onclick = async () => {
    const pasta = await escolherPastaDoSistema("Pasta com os códigos salvos do Planalto");
    if (!pasta) return;
    const saida = $("lei-saida");
    saida.innerHTML = '<p class="nota">lendo os arquivos… isso leva alguns segundos</p>';
    const r = await fetch("/api/leis/importar-pasta", { method: "POST", headers: CFG_JSON, body: JSON.stringify({ pasta: pasta }) });
    if (!r.ok) { saida.innerHTML = '<p class="cfg-explica">' + esc(await erroDe(r)) + "</p>"; return; }
    mostrarResultadoDaImportacao(await r.json());
  };
  alvo.querySelector("[data-cfg-lei-arquivo]").onclick = async () => {
    const caminho = await perguntar({ titulo: "Importar um código do Planalto", contexto: "Configurações › Códigos de lei", campo: { rotulo: "Caminho do arquivo HTML salvo", placeholder: "C:\\Users\\você\\Downloads\\L10406compilada.htm", icone: "description" }, confirmar: "Importar" });
    if (!caminho) return;
    const saida = $("lei-saida");
    saida.innerHTML = '<p class="nota">lendo…</p>';
    const r = await fetch("/api/leis/importar", { method: "POST", headers: CFG_JSON, body: JSON.stringify({ caminho: caminho }) });
    if (!r.ok) { saida.innerHTML = '<p class="cfg-explica">' + esc(await erroDe(r)) + "</p>"; return; }
    mostrarResultadoDaImportacao({ importados: [await r.json()], ignorados: [] });
  };
}

function mostrarResultadoDaImportacao(d) {
  const saida = $("lei-saida");
  if (!saida) return;
  saida.innerHTML = '<div class="cfg-pronto"><b>O que entrou</b>' +
    (d.importados || []).map((x) =>
      '<p class="cfg-texto">' + esc(x.nome) + ": <b>" + x.artigos + "</b> artigos, do " + esc(x.primeiro) + " ao " + esc(x.ultimo) +
      (x.revogados ? " · " + esc(plural(x.revogados, "revogado")) : "") + "</p>").join("") +
    ((d.ignorados || []).length ? '<p class="cfg-explica">Não usei: ' + d.ignorados.map((x) => esc(x.arquivo) + " (" + esc(x.motivo) + ")").join("; ") + "</p>" : "") +
    "</div>";
  avisoCert(plural((d.importados || []).length, "código importado", "códigos importados"));
  blocoLeis();
}

/* --------------------------------------------------------- desempenho */

function secaoDesempenho() {
  const m = cfg.recursos || {};
  const cpu = m.processador ? m.processador.percentual : null;
  const mem = m.memoria || {};
  const video = m.video || {};
  const serie = (chave) => cfg.historico.map((h) => h[chave]).filter((v) => v !== null && v !== undefined);
  const medida = (id, rotulo, valor, chave, presa) => {
    const classe = "cfg-medida" + (id === cfg.medida ? " ativa" : "") + (presa ? " presa" : "");
    return '<button class="' + classe + '" data-cfg-medida="' + id + '"' + (presa ? " disabled" : "") + ">" + faiscaCfg(chave ? serie(chave) : []) +
      '<span class="duas-linhas"><b>' + esc(rotulo) + "</b><small>" + esc(valor) + "</small></span></button>";
  };
  const videoTexto = video.disponivel
    ? (video.percentual === null || video.percentual === undefined ? "medindo…" : video.percentual + "%")
    : "sem leitura nesta máquina";
  const grande = cfg.medida === "mem"
    ? { valor: (mem.percentual !== undefined ? mem.percentual + "%" : "—"), rotulo: "Memória · " + String(mem.usado_gb || 0).replace(".", ",") + " de " + String(mem.total_gb || 0).replace(".", ",") + " GB", chave: "mem" }
    : { valor: (cpu !== null && cpu !== undefined ? Math.round(cpu) + "%" : "—"), rotulo: "Processador · " + (navigator.hardwareConcurrency ? plural(navigator.hardwareConcurrency, "núcleo") : "medido pelo psutil"), chave: "cpu" };
  const pontos = serie(grande.chave);
  const ultimo = pontos.length ? pontos[pontos.length - 1] : null;

  const corpo = '<div class="cfg-desempenho"><div class="cfg-medidas">' +
    medida("cpu", "Processador", cpu !== null && cpu !== undefined ? cpu + "%" : "medindo…", "cpu") +
    medida("mem", "Memória", String(mem.usado_gb || 0).replace(".", ",") + " / " + String(mem.total_gb || 0).replace(".", ",") + " GB", "mem") +
    medida("video", "Vídeo", videoTexto, video.disponivel ? "video" : "", !video.disponivel) +
    medida("disco", "Disco", "sem leitura ainda", "", true) +
    medida("rede", "Rede", "sem saída · leitura em breve", "", true) + "</div>" +
    '<div class="cfg-grafico"><div class="cfg-grafico-topo"><b>' + esc(grande.valor) + "</b><small>" + esc(grande.rotulo) + "</small></div>" +
    '<div class="cfg-area"><div class="cfg-eixo"><span>100%</span><span>75%</span><span>50%</span><span>25%</span><span>0</span></div>' +
    '<div class="cfg-legenda"><span><i></i>' + (grande.chave === "mem" ? "Memória em uso" : "PAULUS + Ollama + sistema") + "</span></div>" +
    graficoCfg(pontos) +
    (ultimo !== null ? '<div class="cfg-agora" style="top:' + (100 - Math.min(100, Math.max(0, ultimo))) + '%"><span>' + Math.round(ultimo) + "% · agora</span><i></i></div>" : "") +
    "</div>" +
    '<div class="cfg-tempos"><span>−60 s</span><span>−45 s</span><span>−30 s</span><span>−15 s</span><span>agora</span></div>' +
    '<div class="cfg-resumo"><div><small>Modelo em uso</small><b>' + esc((cfg.status || {}).modelo || "—") + ((cfg.status || {}).tamanho_gb ? " · " + String(cfg.status.tamanho_gb).replace(".", ",") + " GB" : "") + "</b></div>" +
    "<div><small>Índice do Acervo</small><b>" + esc(plural((cfg.status || {}).trechos || 0, "trecho")) + " · " + esc(plural((cfg.status || {}).contratos || 0, "documento")) + "</b></div>" +
    "<div><small>Como está</small><b>" + esc(m.frase || "medindo…") + "</b></div></div></div></div>";
  return '<div class="cfg-grade larga">' + cartaoCfg("Desempenho", pontoCfg("ao vivo · últimos 60 s", "ok"), corpo, "cfg-cartao-desempenho") + "</div>";
}

function faiscaCfg(pontos) {
  if (pontos.length < 2) return '<svg viewBox="0 0 64 34" preserveAspectRatio="none"></svg>';
  const passo = 64 / (pontos.length - 1);
  const pts = pontos.map((v, i) => (i * passo).toFixed(1) + "," + (32 - Math.min(100, Math.max(0, v)) * 0.28 + 1).toFixed(1)).join(" ");
  return '<svg viewBox="0 0 64 34" preserveAspectRatio="none"><polyline points="' + pts + '" fill="none" stroke="var(--ink)" stroke-width="1.5"></polyline></svg>';
}

function graficoCfg(pontos) {
  if (pontos.length < 2) return '<svg viewBox="0 0 300 100" preserveAspectRatio="none"></svg>';
  const passo = 300 / 29;
  const inicio = 29 - (pontos.length - 1);
  const pts = pontos.map((v, i) => ((inicio + i) * passo).toFixed(1) + "," + (100 - Math.min(100, Math.max(0, v))).toFixed(1)).join(" ");
  return '<svg viewBox="0 0 300 100" preserveAspectRatio="none"><polyline points="' + pts + '" fill="none" stroke="var(--ink)" stroke-width="1.5" vector-effect="non-scaling-stroke"></polyline></svg>';
}

function comecarMedicao() {
  pararMedicao();
  const ler = async () => {
    if (!$("cfg-tela") || cfg.secao !== "desempenho") { pararMedicao(); return; }
    try {
      const m = await (await fetch("/api/recursos")).json();
      cfg.recursos = m;
      cfg.historico.push({ cpu: m.processador.percentual, mem: m.memoria.percentual, video: m.video.percentual });
      if (cfg.historico.length > 30) cfg.historico.shift();
    } catch (err) { return; }
    if (!$("cfg-tela") || cfg.secao !== "desempenho") { pararMedicao(); return; }
    const alvo = document.querySelector(".cfg-grade.larga");
    if (alvo) alvo.outerHTML = secaoDesempenho();
    ligarMedidas();
  };
  ler();
  cfg.relogio = setInterval(ler, 2000);
}

function pararMedicao() {
  if (cfg.relogio) clearInterval(cfg.relogio);
  cfg.relogio = null;
}

function ligarMedidas() {
  document.querySelectorAll("[data-cfg-medida]").forEach((b) => {
    b.onclick = () => { cfg.medida = b.dataset.cfgMedida; const alvo = document.querySelector(".cfg-grade.larga"); if (alvo) alvo.outerHTML = secaoDesempenho(); ligarMedidas(); };
  });
}

/* ----------------------------------------------------------- conexoes */

function secaoConexoes() {
  const cx = cfg.cx || {};
  const s = cx.sessao || {};
  const contas = ((cfg.contas || {}).contas) || [];
  const atencao = contas.filter((c) => c.ultimo_erro || !c.tem_senha).length;
  const cert = cfg.cert || {};
  const servico = (icone, nome, sub, estado, acao) =>
    '<div class="cfg-servico"><span class="cfg-servico-ic">' + ic(icone, 20) + '</span><span class="duas-linhas"><b>' + nome + "</b><small>" + esc(sub) + "</small></span>" + estado + acao + "</div>";
  const ponto = (texto, tom) => { const classe = "fin-meta-ponto" + (tom ? " " + tom : ""); return '<span class="' + classe + '"><i></i>' + esc(texto) + "</span>"; };

  const nomeEscritorio = ((cfg.rascunho || {}).escritorio || {}).nome || "";
  const rede = '<p class="cfg-texto">Vincular outras máquinas por código, com papéis e alçadas, é a próxima etapa. Hoje o PAULUS roda para uma pessoa, nesta máquina.</p>' +
    '<div class="cfg-maquina">' + ic("desktop_windows", 18) + '<span class="duas-linhas"><b>Esta máquina</b><small>' +
    esc((((cfg.rascunho || {}).pessoa || {}).nome || "você") + " · responsável") + '</small></span><span class="cfg-pill">esta máquina</span></div>' +
    '<div class="cfg-botoes"><button class="adiante" data-cfg-adiante="Vínculo por código ainda não existe — quando existir, quem instala digita o código na primeira abertura">' + ic("key", 16) + "Gerar código de vínculo</button>" +
    '<button data-cfg-vinculos="1">' + ic("lan", 16) + "Escritório e vínculos</button></div>";

  const preparar = '<p class="cfg-explica">' + esc(cx.aviso_internet || "Esta é a única tela do PAULUS que vai para a internet.") + "</p>" +
    '<div class="cfg-campos"><div class="ag-duas"><div class="ag-campo"><label>Contato</label><select id="cx-contato"><option value="">escolher do cadastro…</option></select></div>' +
    '<div class="ag-campo"><label>Telefone</label><input type="text" id="cx-telefone" placeholder="(62) 99999-8888"></div></div>' +
    '<div class="ag-campo"><label>Mensagem</label><textarea id="cx-texto" placeholder="escreva a mensagem…"></textarea></div></div>' +
    '<div class="cfg-botoes"><button id="cx-anexar">' + ic("attach_file", 16) + "Anexar da biblioteca</button>" +
    '<button class="primario" id="cx-preparar">' + ic("chat", 16) + "Preparar no WhatsApp</button></div>" +
    '<div id="cx-anexo"></div><div id="cx-saida"></div>' +
    '<p class="cfg-explica">Eu abro a conversa com o texto já escrito. Apertar enviar é com você — ' + esc(cx.porque_nao || "") + "</p>";

  const lista =
    servico("chat", "WhatsApp Web", "navegador embutido · sessão salva nesta máquina · envio só com aprovação",
      ponto(s.existe ? "conectado" : "não conectado", s.existe ? "ok" : ""), '<button data-cfg-cx-abrir="1">Abrir</button>') +
    servico("mail", "E-mail", contas.length ? plural(contas.length, "conta") + (atencao ? " · " + atencao + " precisa de atenção" : " · em dia") : "nenhuma conta entrou ainda",
      contas.length ? (atencao ? '<span class="cfg-pill acc">atenção</span>' : ponto("conectado", "ok")) : '<span class="cfg-pill mute">desligado</span>',
      '<button data-cfg-cx-contas="1">Contas</button>') +
    servico("videocam", "Google Meet", "criar salas a partir da Agenda · em breve", '<span class="cfg-pill mute">em breve</span>', '<button class="adiante" disabled>Conectar</button>') +
    servico("groups", "Microsoft Teams", "não conectado · em breve", '<span class="cfg-pill mute">em breve</span>', '<button class="adiante" disabled>Conectar</button>') +
    servico("video_call", "Zoom", "não conectado · em breve", '<span class="cfg-pill mute">em breve</span>', '<button class="adiante" disabled>Conectar</button>') +
    servico("gavel", "PJe e tribunais", cert.instalado ? "peticionamento em breve · o certificado já está aqui" : "peticionamento em breve · sem certificado instalado",
      cert.instalado ? ponto("certificado instalado", "ok") : '<span class="cfg-pill mute">sem certificado</span>', '<button data-cfg-cx-cert="1">Ver</button>') +
    (s.existe
      ? '<p class="cfg-explica">Sessão do WhatsApp: ' + esc(s.pasta || "") + (s.tamanho_kb ? " · " + s.tamanho_kb + " KB" : "") +
        ' · <button class="em-ligacao acc" data-cfg-cx-apagar="1">apagar sessão</button></p>'
      : "");

  const saidas = saidasDaMaquina();
  const registro = (saidas.length
    ? '<div class="cfg-linhas">' + saidas.map((x) => '<div class="cfg-saida"><span class="fin-data">' + esc(x.quando) + '</span><span class="duas-linhas"><b>' + esc(x.titulo) + "</b><small>" + esc(x.sub) + "</small></span></div>").join("") + "</div>"
    : '<p class="cfg-texto">Nada saiu desta máquina nas últimas 24 h. Só sai o que você aprovar na fila — e o registro aparece aqui.</p>') +
    '<div class="cfg-sub">' +
    ligaCfg("", "Bloquear qualquer saída sem aprovação", "regra do sistema · desligar é ligar uma permissão em Limites da IA", true, true) +
    ligaCfg("", "Avisar quando um serviço pedir nova sessão", "em breve", false, true) + "</div>";

  return '<div class="cfg-grade"><div class="cfg-secao">' +
    cartaoCfg("Escritório na rede local", pontoCfg((nomeEscritorio ? nomeEscritorio + " · " : "") + "1 máquina · em breve", "") , rede) +
    cartaoCfg("Preparar uma mensagem", metaCfg("WhatsApp Web · eu escrevo, você aperta enviar"), preparar) + "</div>" +
    '<div class="cfg-secao">' + cartaoCfg("Conexões", metaCfg("serviços do escritório · sessão fica nesta máquina"), lista) +
    cartaoCfg("O que sai desta máquina", metaCfg("registro das últimas 24 h"), registro) + "</div></div>";
}

/* O registro sai da fila de Aprovacoes e das conversas preparadas no
   WhatsApp: cada linha e uma coisa que existiu. */
function saidasDaMaquina() {
  const limite = Date.now() - 24 * 3600 * 1000;
  const saida = [];
  (cfg.acoes || []).forEach((a) => {
    const t = new Date(String(a.quando || "").replace(" ", "T"));
    if (isNaN(t) || t.getTime() < limite || a.estado !== "aprovado") return;
    saida.push({ t: t, quando: quandoCurtoCfg(t), titulo: a.categoria_rotulo + " · " + a.titulo, sub: "aprovado por você" + (a.resultado ? " · " + a.resultado : "") });
  });
  (((cfg.cx || {}).envios) || []).forEach((e) => {
    const t = new Date(String(e.quando || "").replace(" ", "T"));
    if (isNaN(t) || t.getTime() < limite) return;
    saida.push({ t: t, quando: quandoCurtoCfg(t), titulo: "WhatsApp · " + (e.nome || e.para || "conversa"), sub: "preparado aqui · enviar foi com você" });
  });
  return saida.sort((a, b) => b.t - a.t).slice(0, 12);
}

function quandoCurtoCfg(t) {
  const hoje = new Date();
  const hora = t.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  return t.toDateString() === hoje.toDateString() ? hora : "ontem " + hora;
}

async function ligarConexoesCfg() {
  let anexo = "";
  const abrir = document.querySelector("[data-cfg-cx-abrir]");
  if (abrir) abrir.onclick = async () => {
    const r = await (await fetch("/api/conexoes/abrir", { method: "POST", headers: CFG_JSON, body: "{}" })).json();
    if (r.abriu) { avisoCert("janela do WhatsApp Web aberta"); return; }
    avisoCert(r.motivo);
    window.open(r.endereco, "_blank");
  };
  const apagar = document.querySelector("[data-cfg-cx-apagar]");
  if (apagar) apagar.onclick = async () => {
    if (!(await confirmar({ titulo: "Apagar a sessão do WhatsApp?", contexto: "Configurações › Conexões", texto: "A sessão sai desta máquina. Você vai precisar ler o código de novo para conectar.", confirmar: "Apagar", perigo: true }))) return;
    const r = await (await fetch("/api/conexoes/sessao/apagar", { method: "POST" })).json();
    avisoCert(r.aviso);
    mostrarConfig("conexoes");
  };
  const contas = document.querySelector("[data-cfg-cx-contas]");
  if (contas) contas.onclick = () => { marcarDestino("caixa"); mostrarEmail("contas"); };
  const cert = document.querySelector("[data-cfg-cx-cert]");
  if (cert) cert.onclick = () => { marcarDestino("assinar"); mostrarCertificado(); };

  const contato = $("cx-contato");
  if (!contato) return;
  try {
    const c = await (await fetch("/api/conexoes/contatos")).json();
    c.contatos.forEach((x) => {
      const op = document.createElement("option");
      op.value = x.telefone;
      op.textContent = x.nome + " · " + x.telefone;
      contato.appendChild(op);
    });
    contato.onchange = () => { $("cx-telefone").value = contato.value; };
  } catch (err) { /* sem cadastro com telefone, o campo fica manual */ }

  $("cx-anexar").onclick = async () => {
    const d = await (await fetch("/api/email/anexaveis")).json();
    $("cx-anexo").innerHTML = '<div class="cfg-linhas">' +
      (d.arquivos.length
        ? d.arquivos.slice(0, 20).map((a) => '<div class="cfg-lei"><span class="duas-linhas"><b>' + esc(a.nome) + '</b></span><button data-cx-anexo="' + esc(a.path) + '">Escolher</button></div>').join("")
        : '<p class="cfg-explica">A biblioteca está vazia.</p>') + "</div>";
    document.querySelectorAll("[data-cx-anexo]").forEach((b) => {
      b.onclick = () => { anexo = b.dataset.cxAnexo; $("cx-anexo").innerHTML = '<p class="cfg-explica">anexo: ' + esc(anexo.split(/[\\/]/).pop()) + "</p>"; };
    });
  };
  $("cx-preparar").onclick = async () => {
    const r = await fetch("/api/conexoes/mensagem", {
      method: "POST", headers: CFG_JSON,
      body: JSON.stringify({ telefone: $("cx-telefone").value, nome: ($("cx-contato").selectedOptions[0] || {}).textContent || "", texto: $("cx-texto").value, anexo: anexo }),
    });
    if (!r.ok) { avisoCert(await erroDe(r)); return; }
    const d = await r.json();
    $("cx-saida").innerHTML = '<div class="cfg-pronto"><b>Conversa pronta</b><p class="cfg-explica">' + esc(d.aviso) + "</p>" +
      '<div class="cfg-endereco">' + esc(d.endereco) + "</div>" +
      (d.anexo ? '<p class="cfg-explica">anexo: ' + esc(d.anexo) + " — em " + esc(d.pasta_do_anexo) + "</p>" : "") +
      '<div class="cfg-botoes"><button class="primario" id="cx-ir">' + ic("chat", 16) + "Abrir a conversa</button></div></div>";
    $("cx-ir").onclick = async () => {
      const a = await (await fetch("/api/conexoes/abrir", { method: "POST", headers: CFG_JSON, body: JSON.stringify({ endereco: d.endereco }) })).json();
      if (!a.abriu) window.open(d.endereco, "_blank");
    };
  };
}

/* ------------------------------------------------ escritorio e vinculos */

function secaoVinculos() {
  const p = (cfg.rascunho || {}).pessoa || {};
  const e = (cfg.rascunho || {}).escritorio || {};
  const pedidos = '<p class="cfg-texto">Quando outra máquina instalar o PAULUS e pedir para entrar no escritório, o pedido aparece aqui com o código que a pessoa vê na tela dela. Você confere o código, define cargo e alçada e adiciona — ou recusa.</p>' +
    '<div class="cfg-codigo"><span class="duas-linhas"><b>Nenhum pedido aguardando</b><small>vínculo por código ainda não existe · primeira abertura em outra máquina vai pedir este passo</small></span>' +
    '<span class="cfg-casas"><span>·</span><span>·</span><span>·</span><span>·</span><span>·</span><span>·</span></span></div>' +
    '<div class="cfg-lista-ok">' +
    "<div>" + ic("check_circle", 18) + "<span>Cargo e alçada de aprovação por pessoa</span></div>" +
    "<div>" + ic("check_circle", 18) + "<span>O que cada uma vê: serviços, pastas do Acervo, Financeiro, Cadastros</span></div>" +
    "<div>" + ic("check_circle", 18) + "<span>Revisão das permissões em 30 ou 90 dias, com lembrete em Aprovações</span></div></div>" +
    '<p class="cfg-explica">Tudo isso está desenhado e ainda não construído. As pessoas do escritório já podem ser cadastradas em Cadastros › Equipe.</p>';
  const vinculados = '<div class="cfg-maquina">' + ic("desktop_windows", 18) + '<span class="duas-linhas"><b>' + esc(p.nome || "Você") + ' <small>· responsável</small></b><small>esta máquina · online agora</small></span><span class="cfg-pill ok">online</span></div>' +
    '<div class="cfg-codigo"><span class="duas-linhas"><b>Código de vínculo</b><small>quem instala digita este código na primeira abertura · em breve</small></span>' +
    '<span class="cfg-casas"><span>·</span><span>·</span><span>·</span><span>·</span><span>·</span><span>·</span></span></div>' +
    '<div class="cfg-botoes"><button class="adiante" data-cfg-adiante="Gerar código de vínculo ainda não existe">' + ic("key", 16) + "Gerar código de vínculo</button>" +
    '<button data-cfg-equipe="1">' + ic("groups", 16) + "Cadastros › Equipe</button></div>";
  return cartaoDoPedidoDestaMaquina() + '<div class="cfg-grade">' + cartaoCfg("Pedidos de vinculação", metaCfg("0 aguardando · em breve"), pedidos) +
    cartaoCfg("Máquinas e pessoas vinculadas", metaCfg((e.nome ? e.nome + " · " : "") + "1 máquina"), vinculados) + "</div>";
}

/* ---------------------------------------------------------- aprendizado */

function secaoAprendizado() {
  const ctx = cfg.ctx || { contextos: [], gavetas: [], caracteres: 0, limite: 2400, de_fora: 0 };
  const gavetas = ctx.gavetas && ctx.gavetas.length ? ctx.gavetas : ["Regras de redação", "Modelos", "Clientes", "Correções"];
  const emEdicao = cfg.ensinando || {};
  const opcoes = gavetas.map((g) => '<option' + (g === (emEdicao.gaveta || gavetas[0]) ? " selected" : "") + ">" + esc(g) + "</option>").join("");

  const guardados = (ctx.contextos || []).map((x) =>
    '<div class="cfg-servico cfg-lembrete' + (x.entra ? "" : " de-fora") + '"><span class="cfg-servico-ic">' + ic("lightbulb", 18) + "</span>" +
    '<div class="duas-linhas"><b>' + esc(x.titulo) + "</b><small>" + esc(x.texto) + "</small></div>" +
    '<small class="cfg-lixo-quando">' + esc(x.gaveta) + (x.entra ? "" : " · fora do limite") + "</small>" +
    '<button data-cfg-ensinar-editar="' + x.id + '">' + ic("edit", 16) + "Alterar</button>" +
    '<button data-cfg-ensinar-tirar="' + x.id + '">' + ic("delete", 16) + "Apagar</button></div>").join("");

  const lendo = cfg.lendoArquivo || "";
  const ensinar = '<div class="cfg-solta" id="cfg-solta-ensinar"><span>' +
    (lendo ? "lendo “" + esc(lendo) + "”…" : "Arraste um PDF, DOCX, TXT ou MD aqui") + "</span>" +
    '<small>eu leio, escrevo o lembrete em poucas linhas e mostro antes de guardar · o arquivo não fica guardado</small>' +
    '<div class="cfg-botoes"><button class="primario" data-cfg-ensinar-arquivo="1"' + (lendo ? " disabled" : "") + ">" +
    ic("folder_open", 16) + "Escolher no computador</button></div></div>" +
    '<div class="cfg-sub"><b>Ensinar com suas palavras</b><div class="cfg-campos">' +
    '<div class="ag-campo"><label>Título</label><input type="text" id="cfg-ensinar-titulo" data-cfg-ensinar="titulo" maxlength="80" value="' + esc(emEdicao.titulo || "") + '" placeholder="Prazo padrão de aviso"></div>' +
    '<div class="ag-campo"><label>O que eu devo saber</label><textarea id="cfg-ensinar-texto" data-cfg-ensinar="texto" maxlength="600" placeholder="Nos contratos do escritório o aviso de não renovação é sempre de…">' + esc(emEdicao.texto || "") + "</textarea></div>" +
    '<div class="ag-duas"><div class="ag-campo"><label>Guardar em</label><select id="cfg-ensinar-gaveta" data-cfg-ensinar="gaveta">' + opcoes + "</select></div>" +
    '<div class="ag-campo"><label>&nbsp;</label><div class="cfg-botoes"><button class="primario" data-cfg-ensinar-guardar="1">' + ic("check", 16) + (emEdicao.id ? "Guardar a alteração" : "Guardar") + "</button>" +
    (emEdicao.id ? '<button data-cfg-ensinar-cancelar="1">Cancelar</button>' : "") + "</div></div></div></div>" +
    (guardados ? '<div class="cfg-linhas">' + guardados + "</div>" : "") +
    '<p class="cfg-explica">' + (ctx.contextos || []).length +
    (((ctx.contextos || []).length === 1) ? " lembrete entra" : " lembretes entram") + " em toda pergunta da conversa, junto com os trechos dos documentos · " +
    ctx.caracteres + " de " + ctx.limite + " caracteres em uso" +
    (ctx.de_fora ? " · " + plural(ctx.de_fora, "lembrete") + " não cabe no limite e fica de fora" : "") +
    ". As regras de redação vão junto quando eu escrevo no editor.</p></div>";

  const d = cfg.hab || { grupos: [], contagem: {} };
  const grupos = d.grupos || [];
  const grupo = (v, r) => { const classe = v === cfg.grupoHab ? "ativa" : ""; return '<button class="' + classe + '" data-cfg-grupo="' + esc(v) + '">' + esc(r) + "</button>"; };
  const mostrar = grupos.filter((g) => !cfg.grupoHab || g.grupo === cfg.grupoHab);
  const habs = mostrar.map((g) => g.habilidades.map((h) => {
    const futura = h.estado === "em_breve";
    const classe = "cfg-hab" + (futura ? " futura" : (h.utilizavel ? " pronta" : ""));
    let linha = "";
    if (futura) linha = "ainda não existe";
    else if ((h.faltando || []).length) linha = "precisa de: " + h.faltando.join(", ");
    else if (h.demora) linha = h.demora;
    const classeLinha = (h.faltando || []).length && !futura ? "acc" : "";
    return '<div class="' + classe + '">' + ic(CFG_ICONE_HAB[h.id] || "auto_awesome", 18) + '<span class="duas-linhas"><b>' + esc(h.nome) + "</b><small>" + esc(h.resumo) + "</small>" +
      (linha ? '<small class="' + classeLinha + '">' + esc(linha) + "</small>" : "") + "</span>" +
      (futura ? '<span class="cfg-pill mute">em breve</span>' : (h.utilizavel ? '<button data-cfg-usar="' + esc(h.acao) + '">Usar</button>' : "<button disabled>Usar</button>")) + "</div>";
  }).join("")).join("");
  const c = d.contagem || {};
  const sei = (grupos.length
    ? '<div class="cfg-grupos">' + grupo("", "Todas · " + (c.total || 0)) + grupos.map((g) => grupo(g.grupo, g.grupo + " · " + g.habilidades.length)).join("") + "</div>" +
      '<div class="cfg-habs">' + habs + "</div>"
    : '<p class="cfg-texto">Não consegui ler o catálogo de habilidades.</p>') +
    '<p class="cfg-explica">Cada habilidade é uma coisa que o programa faz por inteiro. As que ainda não existem estão marcadas — prefiro dizer do que prometer.</p>';

  const quantos = (ctx.contextos || []).length;
  return '<div class="cfg-grade">' + cartaoCfg("Aprendizado",
    metaCfg(quantos ? plural(quantos, "lembrete") + " · arquivos em breve" : "ensinar com suas palavras · arquivos em breve"), ensinar) +
    cartaoCfg("O que eu sei fazer", metaCfg((c.prontas || 0) + " prontas · " + (c.em_breve || 0) + " em breve"), sei) + "</div>";
}

/* ------------------------------------------------ aparencia e atalhos */

function temaEscolhido() {
  try {
    const t = localStorage.getItem("paulus.tema");
    if (t === "claro" || t === "escuro" || t === "auto") return t;
  } catch (err) { /* sem memoria */ }
  return document.documentElement.dataset.tema || "claro";
}

function escolherTema(escolha) {
  const efetivo = escolha === "auto"
    ? (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "escuro" : "claro")
    : escolha;
  aplicarTema(efetivo);
  try { localStorage.setItem("paulus.tema", escolha); } catch (err) { /* sem memoria */ }
  cfg.tema = escolha;
}

function secaoAparencia() {
  const atual = temaEscolhido();
  const tema = (id, rotulo) => {
    const classe = "cfg-tema " + id + (id === atual ? " on" : "");
    return '<button class="' + classe + '" data-cfg-tema="' + id + '"><span><img src="/img/paulus-logo.svg" alt=""></span><span>' + rotulo + "</span></button>";
  };
  const aparencia = '<div class="ag-campo"><label>Tema</label><div class="cfg-temas">' + tema("claro", "Claro") + tema("escuro", "Escuro") + tema("auto", "Seguir o Windows") + "</div>" +
    '<span class="cfg-explica">No tema escuro a logo é invertida. A escolha fica nesta máquina.</span></div>' +
    '<div class="cfg-campos"><div class="ag-duas"><div class="ag-campo"><label>Fonte da interface</label><select disabled><option>Manrope · padrão</option></select></div>' +
    '<div class="ag-campo"><label>Fonte dos documentos</label><select disabled><option>EB Garamond</option></select></div></div>' +
    '<div class="ag-campo"><label>Densidade</label><div class="cfg-segmento"><button class="ativa" disabled>Confortável</button><button disabled>Compacta</button></div></div></div>' +
    '<p class="cfg-explica">Fontes e densidade seguem o desenho; trocar por aqui fica para depois.</p>' +
    '<div class="cfg-sub">' + ligaCfg("", "Menu lateral abre ao passar o mouse", "sempre ligado por enquanto", true, true) +
    ligaCfg("animacoes_reduzidas", "Animações reduzidas", "sem deslizes nem pulsos — a tela troca direto", Boolean((cfg.rascunho || {}).animacoes_reduzidas)) + "</div>";

  const atalho = (rotulo, teclas, futura) => {
    const classe = "cfg-atalho" + (futura ? " futura" : "");
    return '<div class="' + classe + '"><span>' + esc(rotulo) + '</span><span class="cfg-teclas">' + teclas.map((t) => "<span>" + esc(t) + "</span>").join("") + "</span>" +
      (futura ? '<span class="cfg-pill mute">em breve</span>' : "") + "</div>";
  };
  const atalhos = '<div class="cfg-linhas">' +
    atalho("Nova conversa", ["Ctrl", "N"]) + atalho("Buscar em tudo", ["Ctrl", "K"]) + atalho("Salvar em Documentos e em Configurações", ["Ctrl", "S"]) +
    atalho("Ir para Assistente", ["Ctrl", "1"]) + atalho("Ir para Agenda", ["Ctrl", "2"]) + atalho("Ir para Acervo", ["Ctrl", "3"]) +
    atalho("Fechar menus e painéis soltos", ["Esc"]) +
    atalho("Aprovar selecionados", ["Ctrl", "Enter"], true) + atalho("Iniciar / pausar foco", ["Ctrl", "Shift", "F"], true) + atalho("Assinar documento aberto", ["Ctrl", "Shift", "S"], true) + "</div>" +
    '<div class="cfg-botoes"><button class="em-ligacao" data-cfg-adiante="Personalizar atalhos fica para depois">Personalizar atalhos →</button></div>';
  return '<div class="cfg-grade">' + cartaoCfg("Aparência", metaCfg("tema, fonte e densidade"), aparencia) + cartaoCfg("Atalhos", metaCfg("teclado"), atalhos) + "</div>";
}

/* ------------------------------------------------------------- feedback */

const CFG_TIPOS_FEEDBACK = [["bug", "bug_report", "Bug"], ["sugestao", "lightbulb", "Sugestão"], ["correcao", "edit_note", "Correção"], ["elogio", "favorite", "Elogio"], ["duvida", "help", "Dúvida"]];

function secaoFeedback() {
  const f = cfg.feedback;
  const s = cfg.status || {};
  const p = (cfg.rascunho || {}).pessoa || {};
  const tipos = CFG_TIPOS_FEEDBACK.map(([id, icone, rotulo]) => {
    const classe = "cfg-tipo" + (id === f.tipo ? " on" : "");
    return '<button class="' + classe + '" data-cfg-tipo="' + id + '">' + ic(icone, 18) + "<span>" + rotulo + "</span></button>";
  }).join("");
  const telas = ["Assistente", "Agenda", "Acervo", "Documentos", "E-mail", "Assinatura", "Financeiro", "Cadastros", "Aprovações", "Configurações", "Outra"];
  const tecnico = "Windows · " + (s.modelo || "modelo local") + (s.tamanho_gb ? " · " + String(s.tamanho_gb).replace(".", ",") + " GB" : "") + " · nenhum documento do escritório vai junto";
  const enviar = '<div class="cfg-campos"><div class="ag-campo"><label>Sobre o que é</label><div class="cfg-tipos">' + tipos + "</div></div>" +
    '<div class="ag-campo"><label>Onde aconteceu</label><select data-cfg-fb="onde"><option value="">escolha a tela…</option>' +
    telas.map((t) => '<option value="' + t + '"' + (t === f.onde ? " selected" : "") + ">" + t + "</option>").join("") + "</select></div>" +
    '<div class="ag-campo"><label>Título</label><input type="text" data-cfg-fb="titulo" value="' + esc(f.titulo) + '" placeholder="em uma linha"></div>' +
    '<div class="ag-campo"><label>Descreva com detalhes</label><textarea data-cfg-fb="texto" placeholder="o que você fez, o que esperava e o que aconteceu">' + esc(f.texto) + "</textarea></div></div>" +
    '<div class="cfg-sub"><b>Anexos</b><div class="cfg-solta"><span>Arraste capturas, áudio, PDF ou .log aqui</span><small>até 50 MB · em breve</small></div></div>' +
    '<div class="cfg-sub">' + ligaCfg("feedback.tecnico", "Incluir informações técnicas", tecnico, f.tecnico) +
    ligaCfg("feedback.contato", "Posso ser contatado sobre este feedback", p.email || "sem e-mail em Meus dados", f.contato) + "</div>" +
    '<p class="cfg-explica">O envio ainda não existe: o texto fica guardado nesta máquina, e Copiar monta a mensagem para você mandar por e-mail. Quando existir, sai só ao clicar em Enviar e passa por Aprovações como qualquer saída.</p>' +
    '<div class="cfg-botoes"><button data-cfg-fb-guardar="1">' + ic("save", 16) + "Salvar rascunho</button>" +
    '<button class="primario" data-cfg-fb-copiar="1">' + ic("content_copy", 16) + "Copiar para enviar</button></div>";

  const envios = '<p class="cfg-texto">Nenhum envio ainda. Quando o envio existir, cada feedback aparece aqui com o número e a resposta.</p>' +
    '<div class="cfg-sub"><b>Antes de relatar um bug</b><div class="cfg-lista-ok">' +
    "<div>" + ic("check_circle", 18) + "<span>Diga a tela e a hora: o registro do programa ajuda a achar o que aconteceu</span></div>" +
    "<div>" + ic("check_circle", 18) + "<span>Anexe uma captura quando existir anexo — ajuda muito</span></div>" +
    "<div>" + ic("check_circle", 18) + "<span>Nenhum documento do escritório vai junto; só o que você escrever</span></div></div></div>" +
    '<div class="cfg-botoes"><button class="adiante" data-cfg-adiante="Novidades da versão ficam para quando a atualização existir">' + ic("article", 16) + "Novidades da versão</button></div>";
  return '<div class="cfg-grade feedback">' + cartaoCfg("Enviar feedback", metaCfg("elogios, sugestões, correções e bugs"), enviar) +
    cartaoCfg("Seus envios", metaCfg("nenhum ainda"), envios) + "</div>";
}

function textoDoFeedback() {
  const f = cfg.feedback;
  const s = cfg.status || {};
  const tipo = (CFG_TIPOS_FEEDBACK.find((t) => t[0] === f.tipo) || [])[2] || "";
  return "[PAULUS · " + tipo + "] " + (f.titulo || "(sem título)") + "\n\n" + (f.texto || "") +
    (f.onde ? "\n\nOnde: " + f.onde : "") +
    (f.tecnico ? "\n\nTécnico: Windows · " + (s.modelo || "modelo local") + " · " + (s.contratos || 0) + " documentos no índice" : "") +
    (f.contato ? "\nContato: " + (((cfg.rascunho || {}).pessoa || {}).email || "") : "");
}

/* --------------------------------------------------------- plano e apoio */

function secaoPlano() {
  const d = NOVOS_DESTINOS.apoiar || { resolve: "", precisa: [] };
  const a = cfg.apoio;
  const valor = (v, rotulo) => {
    const classe = "cfg-valor" + (a.valor === v ? " on" : "");
    return '<button class="' + classe + '" data-cfg-apoio-valor="' + v + '"><b>' + (v ? "R$ " + v : "Outro") + "</b><small>" + rotulo + "</small></button>";
  };
  const seg = (chave, opcoes) => '<div class="cfg-segmento">' + opcoes.map(([v, r]) => {
    const classe = a[chave] === v ? "ativa" : "";
    return '<button class="' + classe + '" data-cfg-apoio="' + chave + ":" + v + '">' + r + "</button>";
  }).join("") + "</div>";
  const chamada = '<div class="cfg-chamada"><h3>Ajude o PAULUS a continuar gratuito.</h3>' +
    "<p>O PAULUS é software livre: roda na sua máquina, sem assinatura nem cobrança por uso. O que mantém o projeto vivo é a contribuição de quem usa — ela paga o desenvolvimento, os modelos locais e o suporte. Qualquer valor ajuda; a recorrência ajuda mais.</p>" +
    '<p class="cfg-explica">Meta do mês e apoiadores aparecem aqui quando o pagamento existir. ' + esc(d.resolve || "") + "</p></div>";
  const contribuicao = '<div class="ag-campo"><label>Valor</label><div class="cfg-valores">' + valor(20, "um café por semana") + valor(40, "mais escolhido") + valor(100, "escritório pequeno") + valor(0, "você define") + "</div></div>" +
    '<div class="ag-duas"><div class="ag-campo"><label>Recorrência</label>' + seg("recorrencia", [["mensal", "Mensal"], ["anual", "Anual"], ["unica", "Única"]]) + "</div>" +
    '<div class="ag-campo"><label>Forma de pagamento</label>' + seg("forma", [["pix", "Pix"], ["cartao", "Cartão"]]) + "</div></div>" +
    '<div class="cfg-botoes"><button class="primario" data-cfg-apoiar="1">' + ic("favorite", 16) + "Apoiar o projeto</button>" +
    '<span class="cfg-explica">falta: ' + esc((d.precisa || []).join(", ") || "o pagamento") + "</span></div>";
  const ultima = saidasDaMaquina()[0];
  const atualizacoes = '<div class="cfg-chaves">' +
    chaveCfg("Versão", "em desenvolvimento · sem número ainda", "mute") +
    chaveCfg("Atualização automática", "em breve", "mute") +
    chaveCfg("Única saída para a internet", "atualizações, quando existirem, e o WhatsApp Web que você abre") +
    chaveCfg("Última saída registrada", ultima ? ultima.quando + " · " + ultima.titulo : "nenhuma nas últimas 24 h") + "</div>" +
    '<p class="cfg-texto">Software livre: o código é seu para ler, mudar e distribuir. Nenhum documento do escritório sai desta máquina — nem para atualizar.</p>' +
    '<div class="cfg-botoes"><button class="adiante" data-cfg-adiante="A licença e o código abertos ficam publicados junto com a primeira versão">' + ic("description", 16) + "Licença</button></div>";
  return '<div class="cfg-secao">' + chamada + '<div class="cfg-grade apoio">' +
    cartaoCfg("Sua contribuição", metaCfg("escolha o valor e a forma · em breve"), contribuicao) +
    cartaoCfg("Atualizações e saída para a internet", metaCfg("o que sai desta máquina"), atualizacoes) + "</div></div>";
}

/* ------------------------------------------------------------ as acoes */

/* ------------------------------------------------------------- lixeira */
/* O que foi apagado nos ultimos 30 dias, com Restaurar e Apagar de vez.
   O que passou do prazo ja sumiu antes de a lista ser lida. */

const CFG_ICONE_LIXO = {
  conversa: "forum", tarefa: "task_alt", compromisso: "event", servico: "work", gravacao: "graphic_eq",
  documento: "description", lancamento: "payments", cadastro: "person",
};

function secaoLixeira() {
  const l = cfg.lixo;
  if (!l) return cartaoCfg("Lixeira", "", '<p class="cfg-texto">não consegui ler a lixeira.</p>');
  const itens = l.itens || [];
  if (!itens.length) {
    return cartaoCfg("Lixeira", metaCfg("vazia"), '<div class="cfg-lixo-vazia"><h3>Nada na lixeira</h3>' +
      "<p>O que você apagar — conversa, tarefa, compromisso, serviço, gravação, documento, lançamento ou ficha — fica aqui por " + (l.dias || 30) +
      " dias, com tudo que precisa para voltar. Depois disso some sozinho.</p></div>");
  }
  const linhas = itens.map((e) => '<div class="cfg-servico cfg-lixo-linha"><span class="cfg-servico-ic">' + ic(CFG_ICONE_LIXO[e.tipo] || "delete", 18) + "</span>" +
    '<div class="duas-linhas"><b>' + esc(e.titulo) + "</b><small>" + esc(e.tipo_rotulo + (e.detalhe ? " · " + e.detalhe : "")) + "</small></div>" +
    '<small class="cfg-lixo-quando">apagado ' + esc(quandoCurtoSv(e.apagado_em)) + " · some em " + plural(e.dias_restantes, "dia") + "</small>" +
    '<button data-cfg-lixo-restaurar="' + e.id + '">' + ic("undo", 16) + "Restaurar</button>" +
    '<button class="mais-linha" data-cfg-lixo-tirar="' + e.id + '" title="Apagar de vez">' + ic("close", 16) + "</button></div>").join("");
  return cartaoCfg("Lixeira", metaCfg(plural(itens.length, "item", "itens") + " · cada um fica " + (l.dias || 30) + " dias"),
    '<div class="cfg-linhas">' + linhas + "</div>" +
    '<div class="cfg-botoes cfg-lixo-pe"><button data-cfg-lixo-esvaziar="1">' + ic("delete", 16) + "Esvaziar a lixeira</button>" +
    '<span class="cfg-explica">Restaurar devolve a linha, as ligações e os arquivos ao lugar de onde saíram.</span></div>');
}

function ligarConfig() {
  const cada = (seletor, fn) => document.querySelectorAll(seletor).forEach(fn);
  const clique = (seletor, fn) => cada(seletor, (b) => { b.onclick = (e) => { e.stopPropagation(); fn(b, e); }; });

  clique("[data-cfg-secao]", (b) => { cfg.secao = b.dataset.cfgSecao; mostrarConfig(); });
  clique("[data-cfg-manual]", () => { location.hash = "#boasvindas"; verificarPrimeiraAbertura(); });
  clique("[data-cfg-lixo-restaurar]", async (b) => {
    b.disabled = true;
    await restaurarDaLixeira(Number(b.dataset.cfgLixoRestaurar), null);
    cfg.recarregar = true;
    mostrarConfig("lixeira");
  });
  clique("[data-cfg-lixo-tirar]", async (b) => {
    const e = (cfg.lixo.itens || []).find((x) => x.id === Number(b.dataset.cfgLixoTirar));
    if (!e) return;
    if (!(await confirmar({ titulo: "Apagar de vez?", contexto: "Lixeira › " + e.titulo, texto: "Sai da lixeira agora, sem esperar os 30 dias. Não dá para desfazer.", confirmar: "Apagar de vez", perigo: true }))) return;
    const r = await fetch("/api/lixeira/" + e.id, { method: "DELETE" });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    cfg.recarregar = true;
    mostrarConfig("lixeira");
  });
  clique("[data-cfg-lixo-esvaziar]", async () => {
    const quantos = (cfg.lixo.itens || []).length;
    if (!(await confirmar({ titulo: "Esvaziar a lixeira?", contexto: "Configurações › Lixeira", texto: plural(quantos, "item", "itens") + " somem agora, sem esperar os 30 dias. Não dá para desfazer.", confirmar: "Esvaziar", perigo: true }))) return;
    const r = await fetch("/api/lixeira/esvaziar", { method: "POST" });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    avisoCert("lixeira esvaziada", { tom: "ok" });
    cfg.recarregar = true;
    mostrarConfig("lixeira");
  });
  clique("[data-cfg-sair]", () => avisoCert("sair não existe ainda — hoje o PAULUS abre com a sua conta do Windows, e fechar a janela basta"));
  clique("[data-cfg-salvar]", salvarConfig);
  clique("[data-cfg-descartar]", () => { cfg.rascunho = rascunhoDe(cfg.prefs.preferencias, cfg.prefs.modelo_atual); cfg.sujo = false; desenharConfig(); });
  clique("[data-cfg-adiante]", (b) => avisoCert(b.dataset.cfgAdiante));
  clique("[data-cfg-ensinar-arquivo]", () => escolherArquivoParaEnsinar());
  const solta = $("cfg-solta-ensinar");
  if (solta) {
    solta.ondragover = (e) => { e.preventDefault(); solta.classList.add("sobre"); };
    solta.ondragleave = () => solta.classList.remove("sobre");
    solta.ondrop = (e) => {
      e.preventDefault();
      solta.classList.remove("sobre");
      const arquivo = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (arquivo) lerArquivoParaEnsinar(arquivo);
    };
  }
  clique("[data-cfg-ensinar-guardar]", async (b) => {
    const dados = {
      id: (cfg.ensinando || {}).id || null,
      titulo: $("cfg-ensinar-titulo").value,
      texto: $("cfg-ensinar-texto").value,
      gaveta: $("cfg-ensinar-gaveta").value,
    };
    b.disabled = true;
    const r = await fetch("/api/contextos", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(dados),
    });
    b.disabled = false;
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    cfg.ctx = await r.json();
    cfg.ensinando = null;
    avisoCert(dados.id ? "lembrete alterado" : "guardado — já vale na próxima pergunta", { tom: "ok" });
    desenharConfig();
  });
  clique("[data-cfg-ensinar-editar]", (b) => {
    const item = ((cfg.ctx || {}).contextos || []).find((x) => x.id === Number(b.dataset.cfgEnsinarEditar));
    if (!item) return;
    cfg.ensinando = { id: item.id, titulo: item.titulo, texto: item.texto, gaveta: item.gaveta };
    desenharConfig();
    const campo = $("cfg-ensinar-titulo");
    if (campo) campo.focus();
  });
  clique("[data-cfg-ensinar-cancelar]", () => { cfg.ensinando = null; desenharConfig(); });
  clique("[data-cfg-ensinar-tirar]", async (b) => {
    const id = Number(b.dataset.cfgEnsinarTirar);
    const r = await fetch("/api/contextos/" + id, { method: "DELETE" });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    if ((cfg.ensinando || {}).id === id) cfg.ensinando = null;
    // O aviso le a resposta (e dela que sai o Desfazer); a lista vem depois.
    await avisarLixeira(r, recarregarLembretes);
    await recarregarLembretes();
  });
  clique("[data-cfg-cache]", async (b) => {
    const resposta = await dialogo({
      titulo: "Limpar o cache?",
      contexto: "Configurações › Limites da IA",
      texto: "O cache guarda o texto já extraído de cada arquivo, por SHA-1. Apagar não " +
        "tira documento nenhum do Acervo: eles são lidos de novo no próximo Reindexar, " +
        "o que demora mais nessa primeira vez.",
      marcar: { rotulo: "Apagar também o que o assistente já classificou (refazer isso roda o modelo em todo o acervo)", marcada: false },
      confirmar: "Limpar cache",
      perigo: true,
    });
    if (!resposta || !resposta.ok) return;
    b.disabled = true;
    const r = await fetch("/api/cache/limpar", {
      method: "POST", headers: CFG_JSON, body: JSON.stringify({ classificacao: Boolean(resposta.marcada) }),
    });
    b.disabled = false;
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    const d = await r.json();
    avisoCert(d.aviso, { tom: "ok" });
    cfg.recarregar = true;
    mostrarConfig("assistente");
  });
  clique("[data-cfg-marca]", (b) => escolherMarca(b.dataset.cfgMarca));
  clique("[data-cfg-marca-tirar]", async (b) => {
    const tipo = b.dataset.cfgMarcaTirar;
    const eFoto = tipo === "foto";
    if (!(await confirmar({
      titulo: eFoto ? "Remover a foto?" : "Remover a logo?",
      contexto: "Configurações › Meus dados",
      texto: eFoto ? "O avatar volta a mostrar as suas iniciais." : "O papel timbrado volta a sair só com o texto.",
      confirmar: "Remover", perigo: true,
    }))) return;
    const r = await fetch("/api/marca/" + tipo, { method: "DELETE" });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    const d = await r.json();
    if (cfg.prefs) cfg.prefs.marca = d.marca;
    desenharConfig();
    carregarUsuario();
  });
  clique("[data-cfg-vinculos]", () => { cfg.secao = "vinculos"; mostrarConfig(); });
  clique("[data-cfg-apoiar]", () => { marcarDestino("apoiar"); mostrarApoiar("contribuir"); });
  clique("[data-cfg-vinculo-copiar]", () => copiarTexto((lerVinculo() || {}).meuCodigo || "", "código copiado"));
  clique("[data-cfg-vinculo-cancelar]", () => cancelarVinculo());
  clique("[data-cfg-equipe]", () => mostrarCadastros("equipe"));
  clique("[data-cfg-voz-usar]", async (b) => {
    const r = await fetch("/api/voz/modelo", { method: "POST", headers: CFG_JSON, body: JSON.stringify({ modelo: b.dataset.cfgVozUsar }) });
    if (!r.ok) { avisoCert(await erroDe(r)); return; }
    cfg.voz = await r.json();
    cfg.recarregar = true;
    mostrarConfig("assistente");
  });
  clique("[data-cfg-voz-baixar]", async (b) => {
    let r = await fetch("/api/voz/modelo", { method: "POST", headers: CFG_JSON, body: JSON.stringify({ modelo: b.dataset.cfgVozBaixar }) });
    if (!r.ok) { avisoCert(await erroDe(r)); return; }
    r = await fetch("/api/voz/baixar", { method: "POST", headers: CFG_JSON, body: JSON.stringify({ modelo: b.dataset.cfgVozBaixar }) });
    if (!r.ok) { avisoCert(await erroDe(r)); return; }
    cfg.voz = await r.json();
    avisoCert("baixando o modelo de voz em segundo plano — abra esta seção de novo para ver o andamento");
    cfg.recarregar = true;
    mostrarConfig("assistente");
  });
  clique("[data-cfg-reindexar]", async (b) => {
    b.disabled = true;
    avisoCert("reindexando o acervo…");
    const r = await fetch("/api/reindex", { method: "POST" });
    b.disabled = false;
    if (!r.ok) { avisoCert(await erroDe(r)); return; }
    const d = await r.json();
    avisoCert(plural(d.contratos || 0, "documento") + " no índice");
    carregarStatus();
    cfg.recarregar = true;
    mostrarConfig();
  });

  cada("[data-cfg-campo]", (el) => {
    el.oninput = () => {
      porNoRascunho(el.dataset.cfgCampo, el.value);
      marcarConfigSuja();
      const aviso = $("cfg-timbre-falta");
      if (aviso) aviso.textContent = avisoDoTimbre();
    };
  });
  cada("[data-cfg-select]", (el) => { el.onchange = () => { porNoRascunho(el.dataset.cfgSelect, el.value); marcarConfigSuja(); desenharConfig(); }; });
  clique("[data-cfg-modelo]", (b) => { cfg.rascunho.modelo = b.dataset.cfgModelo; marcarConfigSuja(); desenharConfig(); });
  clique("[data-cfg-liga]", (b) => {
    const chave = b.dataset.cfgLiga;
    const ligada = !b.classList.contains("on");
    b.classList.toggle("on", ligada);
    if (chave.startsWith("feedback.")) { cfg.feedback[chave.split(".")[1]] = ligada; return; }
    porNoRascunho(chave, ligada);
    marcarConfigSuja();
    const aviso = $("cfg-timbre-falta");
    if (aviso) aviso.textContent = avisoDoTimbre();
  });

  ligarMedidas();
  if (cfg.secao === "conexoes") ligarConexoesCfg();
  clique("[data-cfg-grupo]", (b) => { cfg.grupoHab = b.dataset.cfgGrupo; desenharConfig(); });
  clique("[data-cfg-usar]", (b) => usarHabilidade(b.dataset.cfgUsar));
  clique("[data-cfg-tema]", (b) => { escolherTema(b.dataset.cfgTema); desenharConfig(); });

  clique("[data-cfg-tipo]", (b) => { cfg.feedback.tipo = b.dataset.cfgTipo; desenharConfig(); });
  cada("[data-cfg-fb]", (el) => { el.oninput = () => { cfg.feedback[el.dataset.cfgFb] = el.value; }; el.onchange = el.oninput; });
  clique("[data-cfg-fb-guardar]", () => {
    try { localStorage.setItem("paulus.feedback", JSON.stringify(cfg.feedback)); } catch (err) { /* sem memoria */ }
    avisoCert("rascunho guardado nesta máquina");
  });
  clique("[data-cfg-fb-copiar]", () => copiarTexto(textoDoFeedback(), "feedback copiado — cole num e-mail para quem cuida do PAULUS"));

  clique("[data-cfg-apoio-valor]", (b) => { cfg.apoio.valor = Number(b.dataset.cfgApoioValor); desenharConfig(); });
  clique("[data-cfg-apoio]", (b) => { const [chave, v] = b.dataset.cfgApoio.split(":"); cfg.apoio[chave] = v; desenharConfig(); });
}

async function salvarConfig() {
  const r = cfg.rascunho;
  if (!r) return;
  const resposta = await fetch("/api/preferencias", {
    method: "POST", headers: CFG_JSON,
    body: JSON.stringify({
      pessoa: r.pessoa, autonomia: r.autonomia, escritorio: r.escritorio,
      modelo: r.modelo, timbre_no_pdf: r.timbre_no_pdf, devagar: r.devagar,
      animacoes_reduzidas: r.animacoes_reduzidas,
    }),
  });
  if (!resposta.ok) { avisoCert("não consegui salvar: " + (await erroDe(resposta))); return; }
  cfg.prefs = await resposta.json();
  cfg.rascunho = rascunhoDe(cfg.prefs.preferencias, cfg.prefs.modelo_atual);
  cfg.sujo = false;
  aplicarAnimacoes(cfg.prefs.preferencias.animacoes_reduzidas);
  avisoCert("salvo em data/preferencias.json, nesta máquina");
  carregarStatus();
  if ($("cfg-tela")) desenharConfig();
}

