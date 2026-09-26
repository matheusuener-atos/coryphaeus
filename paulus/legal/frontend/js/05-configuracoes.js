/* ------------------------------------------------------ configuracoes */
/*
   Configuracoes (docs/ui/03-telas-desktop.md, A13), no molde editorial das
   outras telas: a medida de 1080px (sv-medida), um sumario discreto a
   esquerda e, a direita, a secao aberta numa coluna de leitura - titulo em
   serifa, uma linha curta e os cartoes um embaixo do outro.

   Meus dados, o modelo, os limites da IA, o ritmo, o tema, os avisos e os
   codigos de lei sao de verdade e gravam em data/preferencias.json. O que
   ainda nao existe nao aparece como botao apagado nem como "em breve": ou
   some, ou uma linha curta diz que nao existe. Habilidades, Conexoes e
   Desempenho, que eram telas proprias, viraram secoes daqui.
*/

const cfg = {
  secao: "perfil", prefs: null, status: null, rascunho: null, sujo: false,
  recursos: null, historico: [], relogio: null, medida: "cpu",
  cx: null, contas: null, cert: null, acoes: [], hab: null, grupoHab: "",
  tema: "claro", feedback: feedbackGuardado(),
};

const CFG_JSON = { "Content-Type": "application/json" };

/* [id, rotulo no sumario, linha de abertura da secao] */
const CFG_SECOES = [
  ["perfil", "Meus dados", "Seus dados e os do escritório. Ficam nesta máquina e entram nos documentos que você pedir."],
  ["assistente", "Assistente e modelo", "Tudo roda nesta máquina: o modelo de linguagem pelo Ollama e a transcrição pelo Whisper."],
  ["desempenho", "Desempenho", "Medido nesta máquina a cada dois segundos. O gráfico mostra o último minuto."],
  ["conexoes", "Conexões", "Os serviços que saem desta máquina. Nada sai sem a sua aprovação, a não ser o que você liberar em Limites da IA."],
  ["vinculos", "Escritório e vínculos", "Hoje o PAULUS roda para uma pessoa, nesta máquina. Vincular outras máquinas ao escritório ainda não existe."],
  ["aprendizado", "Aprendizado", "O que o escritório ensinou com as próprias palavras, e o que o PAULUS já sabe fazer."],
  ["aparencia", "Aparência e avisos", "Tema, avisos do Windows e atalhos do teclado."],
  ["feedback", "Feedback", "O PAULUS não envia nada sozinho: Copiar monta a mensagem e você manda por e-mail. Nenhum documento do escritório vai junto."],
  ["plano", "Apoio e versão", "O PAULUS é software livre, com licença MIT, e roda de graça nesta máquina."],
  ["lixeira", "Lixeira", "O que você apaga fica aqui por 30 dias, com tudo que precisa para voltar. Depois some sozinho."],
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
    $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal sv-principal"><div class="sv-medida"><p class="nota">lendo…</p></div></div></div>';
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
      $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal sv-principal"><div class="sv-medida"><p class="nota">não consegui ler: ' +
        esc(String(err)) + "</p></div></div></div>";
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
    inteligencia: pr.inteligencia !== false,
    avisos_windows: pr.avisos_windows !== false,
    avisos_tipos: Object.assign({}, pr.avisos_tipos || {}),
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
  } else if (cfg.secao === "desempenho") {
    cfg.recursos = await pega("/api/recursos");
  } else if (cfg.secao === "assistente") {
    const [voz, saber] = await Promise.all([pega("/api/voz"), pega("/api/inteligencia")]);
    cfg.voz = voz;
    cfg.saber = saber;
  } else if (cfg.secao === "lixeira") {
    cfg.lixo = await pega("/api/lixeira");
  } else if (cfg.secao === "aparencia") {
    cfg.avisos = await pega("/api/avisos");
  }
}

function desenharConfig() {
  cabecalhoConfig();
  const menu = CFG_SECOES.map(([id, rotulo]) => {
    const classe = "cfg-item" + (id === cfg.secao ? " ativa" : "");
    return '<button class="' + classe + '" data-cfg-secao="' + id + '">' + rotulo + "</button>";
  }).join("");
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

  // Redesenhar a mesma secao (um modelo escolhido, um aviso ligado) nao
  // pode jogar a leitura de volta para o alto.
  const antes = document.querySelector("#cfg-tela .sv-principal");
  const topo = antes && antes.dataset.cfgAberta === cfg.secao ? antes.scrollTop : 0;
  $("centro").innerHTML = '<div class="acervo sem-painel cfg-tela" id="cfg-tela">' +
    '<div class="acervo-principal sv-principal" data-cfg-aberta="' + cfg.secao + '"><div class="sv-medida"><div class="cfg-corpo">' +
    '<nav class="cfg-menu">' + menu + '<span class="cfg-risco"></span>' +
    '<button class="cfg-item cfg-item-manual" data-cfg-manual="1">' + ic("description", 16) + "Manual do sistema</button></nav>" +
    '<div class="cfg-secao">' + secao + "</div></div></div></div></div>";
  const rolagem = document.querySelector("#cfg-tela .sv-principal");
  if (rolagem) rolagem.scrollTop = topo;
  ligarConfig();
  atualizarPostura();
  if (cfg.secao === "desempenho") comecarMedicao();
  if (cfg.secao === "assistente") blocoLeis();
}

function cabecalhoConfig() {
  $("conversa-titulo").textContent = "Configurações";
  $("conversa-meta").textContent = "Preferências desta máquina";
  $("acoes-tela").innerHTML = '<button data-cfg-descartar="1"' + (cfg.sujo ? "" : " disabled") + ">Descartar</button>" +
    '<button class="primario com-icone" data-cfg-salvar="1"' + (cfg.sujo ? "" : " disabled") + ">" + ic("check", 16) + "Salvar alterações</button>";
  $("nav-tela").innerHTML = "";
}

function marcarConfigSuja() {
  cfg.sujo = true;
  document.querySelectorAll("[data-cfg-salvar], [data-cfg-descartar]").forEach((b) => { b.disabled = false; });
}

/* --------------------------------------------------------- pecas */

/* A abertura da secao, como o Resumo de Servicos: titulo em serifa e uma
   linha curta. `extra` fica a direita do titulo (uma ligacao). */
function aberturaCfg(extra) {
  const achada = CFG_SECOES.find((s) => s[0] === cfg.secao) || CFG_SECOES[0];
  return '<header class="sv-resumo-topo"><div class="sv-resumo-cabeca"><h2>' + esc(achada[1]) + "</h2>" + (extra || "") + "</div>" +
    '<p class="sv-resumo-corpo">' + esc(achada[2]) + "</p></header>";
}

/* A faixa de numeros embaixo da abertura: [rotulo, valor, tom]. */
function fichaCfg(itens) {
  return '<div class="sv-ficha cfg-ficha">' + itens.map(([rotulo, valor, tom]) => {
    const classe = tom || "";
    return '<div class="sv-ficha-item"><span class="sv-kicker">' + esc(rotulo) + '</span><b class="' + classe + '">' + esc(valor) + "</b></div>";
  }).join("") + "</div>";
}

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
  const voce = '<div class="cfg-foto">' + avatarDoPerfil(p.nome) + '<div class="cfg-botoes">' +
    '<button data-cfg-marca="foto">' + ic("photo_camera", 16) + (foto.tem ? "Trocar foto" : "Enviar foto") + "</button>" +
    (foto.tem ? '<button data-cfg-marca-tirar="foto">' + ic("close", 16) + "Remover</button>" : "") +
    '<span class="cfg-explica">PNG ou JPG, até 4 MB</span></div></div>' +
    '<div class="cfg-campos">' + campoCfg("pessoa.nome", "Nome completo", p.nome) +
    '<div class="ag-duas">' + campoCfg("pessoa.cpf", "CPF", p.cpf, "000.000.000-00") + campoCfg("pessoa.oab", "OAB", p.oab, "GO 00000") + "</div>" +
    '<div class="ag-duas">' + campoCfg("pessoa.telefone", "Telefone", p.telefone, "(62) 90000-0000") + campoCfg("pessoa.email", "E-mail", p.email) + "</div>" +
    campoCfg("pessoa.endereco", "Endereço profissional", p.endereco) + "</div>";

  const timbre = '<div class="cfg-sub">' + ligaCfg("timbre_no_pdf", "Papel timbrado nos PDFs", "nome, OAB, endereço e contato no alto de cada PDF gerado aqui", r.timbre_no_pdf) +
    '<p class="cfg-explica" id="cfg-timbre-falta">' + esc(avisoDoTimbre()) + "</p></div>";

  const logo = marcaDaTela("logo");
  const escritorio = '<div class="cfg-foto"><span class="cfg-logo' + (logo.tem ? " cfg-logo-propria" : "") + '">' +
    '<img src="' + (logo.tem ? "/marca/logo.png?v=" + logo.versao : "/img/paulus-logo.svg") + '" alt=""></span><div class="cfg-botoes">' +
    '<button data-cfg-marca="logo">' + ic("upload", 16) + (logo.tem ? "Trocar logo" : "Enviar logo") + "</button>" +
    (logo.tem ? '<button data-cfg-marca-tirar="logo">' + ic("close", 16) + "Remover</button>" : "") +
    '<span class="cfg-explica">vai no alto do papel timbrado</span></div></div>' +
    '<div class="cfg-campos">' + campoCfg("escritorio.nome", "Nome do escritório", e.nome, "como aparece nos recibos") +
    '<div class="ag-duas">' + campoCfg("escritorio.cnpj", "CNPJ", e.cnpj, "00.000.000/0001-00") + campoCfg("escritorio.oab", "OAB da sociedade", e.oab, "GO 0000") + "</div>" +
    campoCfg("escritorio.rodape", "Rodapé dos documentos", e.rodape, "OAB/GO 00000 · Goiânia · GO") + "</div>" +
    '<p class="cfg-explica">O nome entra nos recibos da folha. CNPJ, OAB e rodapé ficam guardados; nenhum documento os usa ainda.</p>';

  return aberturaCfg() +
    cartaoCfg("Você", metaCfg("nos documentos e no selo"), voce + timbre) +
    cartaoCfg("Escritório", metaCfg("recibos e timbre"), escritorio);
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
  desenharConfig();
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const d = await r.json();
  avisoCert(d.aviso, { tom: d.pelo_modelo ? "ok" : "erro" });
  formLembrete({ id: null, titulo: d.titulo, texto: d.texto, gaveta: "" });
}

/* Escrever ou alterar um lembrete: no pop-up do sistema. O arquivo lido
   chega aqui ja com a proposta escrita; guardar e sempre um clique. */
function formLembrete(item) {
  const e = item || {};
  const ctx = cfg.ctx || {};
  const gavetas = ctx.gavetas && ctx.gavetas.length ? ctx.gavetas : ["Regras de redação", "Modelos", "Clientes", "Correções"];
  const escolhida = e.gaveta || gavetas[0];
  const campo = (rotulo, controle, id, longo) => '<div class="dialogo-campo"><label for="' + id + '">' + rotulo + "</label>" +
    '<div class="dialogo-caixa' + (longo ? " texto-longo" : "") + '">' + controle + "</div></div>";
  dialogo({
    titulo: e.id ? "Alterar lembrete" : "Novo lembrete", contexto: "Configurações › Aprendizado",
    classe: "dialogo-cadastro", larga: true,
    html: '<div class="dialogo-form">' +
      campo("Título", '<input type="text" id="cfg-ensinar-titulo" maxlength="80" autocomplete="off" value="' + esc(e.titulo || "") + '" placeholder="Prazo padrão de aviso">', "cfg-ensinar-titulo") +
      campo("O que eu devo saber", '<textarea id="cfg-ensinar-texto" maxlength="600" rows="6" placeholder="Nos contratos do escritório o aviso de não renovação é sempre de…">' + esc(e.texto || "") + "</textarea>", "cfg-ensinar-texto", true) +
      campo("Guardar em", '<select id="cfg-ensinar-gaveta">' + gavetas.map((g) => "<option" + (g === escolhida ? " selected" : "") + ">" + esc(g) + "</option>").join("") + "</select>", "cfg-ensinar-gaveta") +
      '<p class="dialogo-dica">Entra em toda pergunta da conversa. As regras de redação também vão junto quando eu escrevo no editor.</p></div>',
    rodape: '<span class="dialogo-aviso" id="cfg-ensinar-aviso"></span>',
    cancelar: "Cancelar", confirmar: e.id ? "Guardar a alteração" : "Guardar",
    aoConfirmar: () => guardarLembreteCfg(e.id || null),
  });
  const alvo = $(e.texto ? "cfg-ensinar-texto" : "cfg-ensinar-titulo");
  if (alvo) { alvo.focus(); alvo.setSelectionRange(alvo.value.length, alvo.value.length); }
}

async function guardarLembreteCfg(id) {
  const aviso = $("cfg-ensinar-aviso");
  const dados = {
    id: id,
    titulo: $("cfg-ensinar-titulo").value,
    texto: $("cfg-ensinar-texto").value,
    gaveta: $("cfg-ensinar-gaveta").value,
  };
  if (!dados.texto.trim()) { if (aviso) aviso.textContent = "escreva o que eu devo saber"; $("cfg-ensinar-texto").focus(); return; }
  const r = await fetch("/api/contextos", { method: "POST", headers: CFG_JSON, body: JSON.stringify(dados) });
  if (!r.ok) { if (aviso) aviso.textContent = await erroDe(r); return; }
  cfg.ctx = await r.json();
  if (dialogoAberto) dialogoAberto.fechar({ ok: true });
  avisoCert(id ? "lembrete alterado" : "guardado — já vale na próxima pergunta", { tom: "ok" });
  if ($("cfg-tela")) desenharConfig();
}

/* O que mudou no programa. Sai de docs/NOVIDADES.md, que vem junto com o
   programa - a lista de novidades de uma versao e da versao, nao de um
   servidor que esta maquina nem consulta. */
async function mostrarNovidades() {
  let d = null;
  try {
    d = await (await fetch("/api/novidades")).json();
  } catch (err) { d = null; }
  if (!d || !(d.blocos || []).length) {
    avisoCert((d && d.aviso) || "não consegui ler a lista de novidades", { tom: "erro" });
    return;
  }
  const html = (d.intro ? '<p class="cfg-explica">' + esc(d.intro) + "</p>" : "") +
    d.blocos.map((b) => '<div class="cfg-novidade"><b>' + esc(b.titulo) + "</b><ul>" +
      b.itens.map((x) => "<li>" + negrito(x) + "</li>").join("") + "</ul></div>").join("");
  await dialogo({
    titulo: "Novidades da versão",
    contexto: "Configurações › Apoio e versão",
    html: html,
    confirmar: "Fechar",
    larga: true,
  });
}

/* O **negrito** do arquivo vira negrito na tela; o resto continua texto, com
   os sinais escapados - a lista e um arquivo, e arquivo se edita. */
function negrito(texto) {
  return esc(texto).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
}

/* A lista de lembretes de novo do servidor: apagar e restaurar mexem nela. */
async function recarregarLembretes() {
  try {
    cfg.ctx = await (await fetch("/api/contextos")).json();
  } catch (err) { /* sem lista, a secao fica com a que tinha */ }
  if (cfg.secao === "aprendizado" && $("cfg-tela")) desenharConfig();
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
  if (!r.timbre_no_pdf) return "Desligado: minuta interna com timbre parece peça protocolada. Ligue quando os seus dados estiverem completos.";
  const p = r.pessoa;
  if (!String(p.nome || "").trim()) return "Sem o nome completo o timbre não sai.";
  const campos = ["nome", "cpf", "oab", "telefone", "email", "endereco"];
  const cheios = campos.filter((c) => String(p[c] || "").trim()).length;
  return cheios + " de " + campos.length + " campos preenchidos vão no alto de cada PDF. O que estiver em branco fica de fora.";
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
      (m.instalado ? "" : " · não baixado") + "</small></span><small>" + gb + "</small>" +
      (emUso && m.instalado ? '<span class="cfg-pill">em uso</span>' : (emUso ? '<span class="cfg-pill">escolhido · falta baixar</span>' : "")) + acao + "</div>";
  }).join("");
  return '<div class="cfg-voz"><div class="cfg-modelos">' + lista + "</div>" +
    '<p class="cfg-explica">Em CPU, com ' + plural(v.nucleos || 0, "núcleo") + "; o áudio não sai do computador. " +
    (v.erro ? esc(v.erro) + " " : "") + "Os modelos ficam em " + esc(v.pasta || "") + ".</p></div>";
}

function secaoAssistente() {
  const r = cfg.rascunho;
  const s = cfg.status || {};
  const modelos = (cfg.prefs.modelos || []).slice();
  if (r.modelo && modelos.indexOf(r.modelo) < 0) modelos.unshift(r.modelo);
  const ligado = Boolean(s.ollama);
  const lista = modelos.length
    ? '<div class="cfg-modelos">' + modelos.map((m) => {
      const emUso = m === r.modelo;
      const classe = "cfg-modelo" + (emUso ? " on" : "");
      const tamanho = emUso && s.tamanho_gb ? String(s.tamanho_gb).replace(".", ",") + " GB" : "";
      return '<div class="' + classe + '" data-cfg-modelo="' + esc(m) + '"><i></i><span class="duas-linhas"><b>' + esc(m) + "</b></span>" +
        (tamanho ? "<small>" + esc(tamanho) + "</small>" : "") + (emUso ? '<span class="cfg-pill">em uso</span>' : "") + "</div>";
    }).join("") + "</div>"
    : '<p class="cfg-texto">Nenhum modelo encontrado no Ollama. Instale um com <code>ollama pull llama3.2:3b</code> e abra esta tela de novo.</p>';

  const modelo = lista +
    '<p class="cfg-explica">Vale a partir da próxima pergunta. Modelo maior responde melhor e demora mais. Para instalar outro: <code>ollama pull nome</code>, no terminal.</p>' +
    '<div class="cfg-sub">' + ligaCfg("devagar", "Ir devagar quando eu usar o PC", "espera a máquina desafogar antes de cada documento; a leitura demora mais e o computador continua seu", r.devagar) + "</div>";

  const limites = '<div class="cfg-campos">' + (cfg.prefs.autonomia_opcoes || []).map((a) => {
    const ligada = a.travada ? false : Boolean(r.autonomia[a.chave]);
    return ligaCfg(a.travada ? "" : "autonomia." + a.chave, a.titulo, a.explica, ligada, a.travada);
  }).join("") + "</div>" +
    '<p class="cfg-explica">Desligado, a ação espera o seu sim na fila de Aprovações. Ligado, ela acontece direto.</p>';

  const indice = '<div class="cfg-chaves">' +
    chaveCfg("Pasta do acervo", cfg.prefs.pasta_acervo || "—") +
    chaveCfg("Documentos indexados", String(s.contratos || 0)) +
    chaveCfg("Trechos no índice", String(s.trechos || 0)) +
    chaveCfg("Cache de extração", "local · SHA-1") + "</div>" +
    '<div class="cfg-botoes"><button data-cfg-reindexar="1">' + ic("sync", 16) + "Reindexar tudo</button>" +
    '<button data-cfg-cache="1">' + ic("delete", 16) + "Limpar cache</button></div>";

  const voz = ((cfg.voz || {}).modelos || []).find((m) => m.nome === (cfg.voz || {}).modelo);
  const ficha = fichaCfg([
    ["Modelo", r.modelo || "nenhum"],
    ["Ollama", ligado ? "conectado" : "desligado", ligado ? "sv-valor-concluido" : "cfg-mudo"],
    ["Índice", plural(s.contratos || 0, "documento") + " · " + plural(s.trechos || 0, "trecho")],
    ["Voz", voz ? voz.rotulo : "—"],
  ]);

  return aberturaCfg() + ficha +
    cartaoCfg("Modelo de linguagem", pontoCfg(ligado ? "Ollama conectado" : (s.mensagem || "Ollama desligado"), ligado ? "ok" : ""), modelo) +
    cartaoCfg("Limites da IA", metaCfg("o que o assistente faz sem pedir"), limites) +
    cartaoCfg("Modelo de voz", metaCfg("transcreve as gravações"), cartaoDaVozCfg()) +
    cartaoCfg("Acervo e índice", metaCfg("o que a busca enxerga"), indice) +
    cartaoCfg("O que já foi lido", metaCfg("entendido uma vez, consultado sempre"), blocoDoQueJaFoiLido()) +
    cartaoCfg("Códigos de lei", metaCfg("para citar artigo com o texto certo"), '<div id="cfg-leis"><p class="nota">abrindo os códigos…</p></div>');
}

/* Os codigos de lei: o que esta no disco e como trazer mais. */
async function blocoLeis() {
  const alvo = $("cfg-leis");
  if (!alvo) return;
  let d;
  try { d = await (await fetch("/api/leis")).json(); } catch (err) { alvo.innerHTML = '<p class="cfg-explica">não consegui abrir os códigos.</p>'; return; }
  if (!$("cfg-leis")) return;
  alvo.innerHTML = '<div class="cfg-leis-corpo"><p class="cfg-explica">' + esc(d.porque) + "</p>" +
    '<div class="cfg-linhas">' + (d.codigos || []).map((c) =>
      '<div class="cfg-lei"><span class="duas-linhas"><b>' + esc(c.nome) + "</b><small>" + esc(c.lei) +
      (c.instalado ? " · " + plural(c.artigos, "artigo") + " · " + esc(quandoCurto(c.importado_em)) : " · não instalado") + "</small></span>" +
      (c.instalado ? '<button data-cfg-tirar-lei="' + esc(c.codigo) + '">Remover</button>' : '<span class="cfg-pill mute">falta</span>') +
      "</div>").join("") + "</div>" +
    '<p class="cfg-explica">' + esc(d.como_baixar) + "</p>" +
    '<div class="cfg-botoes"><button data-cfg-lei-pasta="1">' + ic("folder_open", 16) + "Importar de uma pasta</button>" +
    '<button data-cfg-lei-arquivo="1">' + ic("upload", 16) + 'Escolher um arquivo</button></div><div id="lei-saida"></div></div>';

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
  return aberturaCfg() + cartaoDesempenho();
}

/* O cartao que a medicao troca a cada dois segundos (#cfg-vivo). Disco e
   rede nao tem leitura: nao aparecem. */
function cartaoDesempenho() {
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
  const pct = (v) => String(v).replace(".", ",") + "%";
  const videoTexto = video.percentual === null || video.percentual === undefined ? "medindo…" : pct(video.percentual);
  const gb = (v) => String(v || 0).replace(".", ",");
  const grande = cfg.medida === "mem"
    ? { valor: (mem.percentual !== undefined ? mem.percentual + "%" : "—"), rotulo: "Memória · " + gb(mem.usado_gb) + " de " + gb(mem.total_gb) + " GB", chave: "mem" }
    : cfg.medida === "video" && video.disponivel
      ? { valor: videoTexto, rotulo: "Vídeo", chave: "video" }
      : { valor: (cpu !== null && cpu !== undefined ? Math.round(cpu) + "%" : "—"), rotulo: "Processador · " + (navigator.hardwareConcurrency ? plural(navigator.hardwareConcurrency, "núcleo") : "medido pelo psutil"), chave: "cpu" };
  const pontos = serie(grande.chave);
  const ultimo = pontos.length ? pontos[pontos.length - 1] : null;
  const st = cfg.status || {};
  const legenda = { mem: "Memória em uso", video: "Vídeo em uso", cpu: "PAULUS + Ollama + sistema" }[grande.chave];

  const corpo = '<div class="cfg-desempenho"><div class="cfg-medidas">' +
    medida("cpu", "Processador", cpu !== null && cpu !== undefined ? pct(cpu) : "medindo…", "cpu") +
    medida("mem", "Memória", gb(mem.usado_gb) + " / " + gb(mem.total_gb) + " GB", "mem") +
    (video.disponivel ? medida("video", "Vídeo", videoTexto, "video") : "") + "</div>" +
    '<div class="cfg-grafico"><div class="cfg-grafico-topo"><b>' + esc(grande.valor) + "</b><small>" + esc(grande.rotulo) + "</small></div>" +
    '<div class="cfg-area"><div class="cfg-eixo"><span>100%</span><span>75%</span><span>50%</span><span>25%</span><span>0</span></div>' +
    '<div class="cfg-legenda"><span><i></i>' + legenda + "</span></div>" +
    graficoCfg(pontos) +
    (ultimo !== null ? '<div class="cfg-agora" style="top:' + (100 - Math.min(100, Math.max(0, ultimo))) + '%"><span>' + Math.round(ultimo) + "% · agora</span><i></i></div>" : "") +
    "</div>" +
    '<div class="cfg-tempos"><span>−60 s</span><span>−45 s</span><span>−30 s</span><span>−15 s</span><span>agora</span></div></div></div>';
  const resumo = '<div class="cfg-chaves">' +
    chaveCfg("Modelo em uso", (st.modelo || "—") + (st.tamanho_gb ? " · " + gb(st.tamanho_gb) + " GB" : "")) +
    chaveCfg("Índice do Acervo", plural(st.trechos || 0, "trecho") + " · " + plural(st.contratos || 0, "documento")) +
    chaveCfg("Como está", m.frase || "medindo…") + "</div>";
  return '<div class="cfg-vivo" id="cfg-vivo">' + cartaoCfg("Agora", pontoCfg("ao vivo · últimos 60 s", ""), corpo, "cfg-cartao-desempenho") +
    cartaoCfg("Nesta máquina", "", resumo) + "</div>";
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
    redesenharMedidas();
  };
  ler();
  cfg.relogio = setInterval(ler, 2000);
}

function pararMedicao() {
  if (cfg.relogio) clearInterval(cfg.relogio);
  cfg.relogio = null;
}

function redesenharMedidas() {
  const alvo = $("cfg-vivo");
  if (alvo) alvo.outerHTML = cartaoDesempenho();
  ligarMedidas();
}

function ligarMedidas() {
  document.querySelectorAll("[data-cfg-medida]").forEach((b) => {
    b.onclick = () => { cfg.medida = b.dataset.cfgMedida; redesenharMedidas(); };
  });
}

/* ----------------------------------------------------------- conexoes */

function secaoConexoes() {
  const cx = cfg.cx || {};
  const s = cx.sessao || {};
  const contas = ((cfg.contas || {}).contas) || [];
  const atencao = contas.filter((c) => c.ultimo_erro || !c.tem_senha).length;
  const cert = cfg.cert || {};
  const ponto = (texto, tom) => { const classe = "fin-meta-ponto" + (tom ? " " + tom : ""); return '<span class="' + classe + '"><i></i>' + esc(texto) + "</span>"; };
  const servico = (icone, nome, sub, estado, acao) =>
    '<div class="cfg-servico"><span class="cfg-servico-ic">' + ic(icone, 18) + '</span><span class="duas-linhas"><b>' + nome + "</b><small>" + esc(sub) + "</small></span>" +
    estado + '<span class="cfg-botoes">' + acao + "</span></div>";

  const lista =
    servico("chat", "WhatsApp Web", "a sessão fica nesta máquina; enviar é com você",
      ponto(s.existe ? "conectado" : "não conectado", s.existe ? "ok" : ""),
      '<button data-cfg-cx-preparar="1">Preparar mensagem</button><button data-cfg-cx-abrir="1">Abrir</button>') +
    servico("mail", "E-mail", contas.length ? plural(contas.length, "conta") + (atencao ? " · " + atencao + " precisa de atenção" : " · em dia") : "nenhuma conta ainda",
      contas.length ? (atencao ? ponto("atenção", "acc") : ponto("conectado", "ok")) : ponto("sem conta", ""),
      '<button data-cfg-cx-contas="1">Contas</button>') +
    servico("draw", "Certificado digital", cert.instalado ? "usado para assinar PDFs nesta máquina" : "nenhum certificado instalado",
      cert.instalado ? ponto("instalado", "ok") : ponto("sem certificado", ""), '<button data-cfg-cx-cert="1">Ver</button>') +
    (s.existe
      ? '<p class="cfg-explica">Sessão do WhatsApp em ' + esc(s.pasta || "") + (s.tamanho_kb ? " · " + s.tamanho_kb + " KB" : "") +
        ' · <button class="em-ligacao" data-cfg-cx-apagar="1">apagar sessão</button></p>'
      : "");

  const saidas = saidasDaMaquina();
  const registro = saidas.length
    ? '<div class="cfg-linhas">' + saidas.map((x) => '<div class="cfg-saida"><span class="fin-data">' + esc(x.quando) + '</span><span class="duas-linhas"><b>' + esc(x.titulo) + "</b><small>" + esc(x.sub) + "</small></span></div>").join("") + "</div>"
    : '<p class="cfg-texto">Nada saiu desta máquina nas últimas 24 horas.</p>';

  return aberturaCfg() +
    cartaoCfg("Serviços", "", lista) +
    cartaoCfg("O que saiu desta máquina", metaCfg("últimas 24 horas"), registro);
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

function ligarConexoesCfg() {
  const abrir = document.querySelector("[data-cfg-cx-abrir]");
  if (abrir) abrir.onclick = async () => {
    const r = await (await fetch("/api/conexoes/abrir", { method: "POST", headers: CFG_JSON, body: "{}" })).json();
    if (r.abriu) { avisoCert("janela do WhatsApp Web aberta"); return; }
    avisoCert(r.motivo);
    window.open(r.endereco, "_blank");
  };
  const preparar = document.querySelector("[data-cfg-cx-preparar]");
  if (preparar) preparar.onclick = () => formMensagemWhatsapp();
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
}

/* Preparar uma mensagem no WhatsApp Web, no pop-up: eu escrevo e abro a
   conversa; apertar enviar e com a pessoa. */
async function formMensagemWhatsapp() {
  let anexo = "";
  const campo = (rotulo, controle, id, longo) => '<div class="dialogo-campo"><label for="' + id + '">' + rotulo + "</label>" +
    '<div class="dialogo-caixa' + (longo ? " texto-longo" : "") + '">' + controle + "</div></div>";
  dialogo({
    titulo: "Preparar uma mensagem", contexto: "Configurações › Conexões › WhatsApp Web",
    classe: "dialogo-cadastro", larga: true,
    html: '<div class="dialogo-form"><div class="dialogo-duas">' +
      campo("Contato", '<select id="cx-contato"><option value="">escolher do cadastro…</option></select>', "cx-contato") +
      campo("Telefone", '<input type="text" id="cx-telefone" autocomplete="off" placeholder="(62) 99999-8888">', "cx-telefone") + "</div>" +
      campo("Mensagem", '<textarea id="cx-texto" rows="5" placeholder="escreva a mensagem…"></textarea>', "cx-texto", true) +
      '<div class="cfg-botoes"><button type="button" id="cx-anexar">' + ic("attach_file", 16) + "Anexar da biblioteca</button></div>" +
      '<div id="cx-anexo"></div>' +
      '<p class="dialogo-dica">Eu abro a conversa com o texto já escrito; apertar enviar é com você.</p></div>',
    rodape: '<span class="dialogo-aviso" id="cx-aviso"></span>',
    cancelar: "Cancelar", confirmar: "Preparar no WhatsApp",
    aoConfirmar: async () => {
      const r = await fetch("/api/conexoes/mensagem", {
        method: "POST", headers: CFG_JSON,
        body: JSON.stringify({ telefone: $("cx-telefone").value, nome: ($("cx-contato").selectedOptions[0] || {}).textContent || "", texto: $("cx-texto").value, anexo: anexo }),
      });
      if (!r.ok) { $("cx-aviso").textContent = await erroDe(r); return; }
      const d = await r.json();
      if (dialogoAberto) dialogoAberto.fechar({ ok: true });
      conversaPronta(d);
    },
  });
  $("cx-anexar").onclick = async () => {
    const d = await (await fetch("/api/email/anexaveis")).json();
    const lugar = $("cx-anexo");
    if (!lugar) return;
    lugar.innerHTML = '<div class="cfg-linhas">' +
      (d.arquivos.length
        ? d.arquivos.slice(0, 20).map((a) => '<div class="cfg-lei"><span class="duas-linhas"><b>' + esc(a.nome) + '</b></span><button type="button" data-cx-anexo="' + esc(a.path) + '">Escolher</button></div>').join("")
        : '<p class="cfg-explica">A biblioteca está vazia.</p>') + "</div>";
    lugar.querySelectorAll("[data-cx-anexo]").forEach((b) => {
      b.onclick = () => { anexo = b.dataset.cxAnexo; lugar.innerHTML = '<p class="cfg-explica">anexo: ' + esc(anexo.split(/[\\/]/).pop()) + "</p>"; };
    });
  };
  const contato = $("cx-contato");
  try {
    const c = await (await fetch("/api/conexoes/contatos")).json();
    if (!document.contains(contato)) return;
    c.contatos.forEach((x) => {
      const op = document.createElement("option");
      op.value = x.telefone;
      op.textContent = x.nome + " · " + x.telefone;
      contato.appendChild(op);
    });
    contato.onchange = () => { $("cx-telefone").value = contato.value; };
  } catch (err) { /* sem cadastro com telefone, o campo fica manual */ }
}

/* A conversa preparada: o endereco, onde esta o anexo (ele vai a mao) e o
   botao que abre. */
function conversaPronta(d) {
  dialogo({
    titulo: "Conversa pronta", contexto: "Configurações › Conexões › WhatsApp Web",
    larga: true,
    html: '<p class="cfg-texto">' + esc(d.aviso) + "</p>" + '<div class="cfg-endereco">' + esc(d.endereco) + "</div>" +
      (d.anexo ? '<p class="cfg-explica">Anexo: ' + esc(d.anexo) + " — em " + esc(d.pasta_do_anexo) + "</p>" : ""),
    cancelar: "Fechar", confirmar: "Abrir a conversa",
    aoConfirmar: async () => {
      if (dialogoAberto) dialogoAberto.fechar({ ok: true });
      const a = await (await fetch("/api/conexoes/abrir", { method: "POST", headers: CFG_JSON, body: JSON.stringify({ endereco: d.endereco }) })).json();
      if (!a.abriu) window.open(d.endereco, "_blank");
    },
  });
}

/* ------------------------------------------------ escritorio e vinculos */

function secaoVinculos() {
  const p = (cfg.rascunho || {}).pessoa || {};
  const e = (cfg.rascunho || {}).escritorio || {};
  const maquina = '<div class="cfg-maquina">' + ic("desktop_windows", 18) + '<span class="duas-linhas"><b>' + esc(p.nome || "Você") + "</b>" +
    "<small>responsável · esta máquina" + (e.nome ? " · " + esc(e.nome) : "") + "</small></span></div>" +
    '<p class="cfg-explica">As pessoas do escritório já podem ser cadastradas em Cadastros › Equipe, para a folha e para os serviços.</p>' +
    '<div class="cfg-botoes"><button data-cfg-equipe="1">' + ic("groups", 16) + "Abrir Cadastros › Equipe</button></div>";
  return aberturaCfg() + cartaoDoPedidoDestaMaquina() + cartaoCfg("Nesta máquina", metaCfg("1 máquina"), maquina);
}

/* O que a camada de inteligencia ja entendeu do acervo, e quanto isso esta
   economizando. E aqui que se ve se ela esta valendo a pena: sem numero
   medido, ligar ou desligar vira gosto. */
function blocoDoQueJaFoiLido() {
  const d = cfg.saber || {};
  if (d.erro || !d.no_acervo) {
    return '<p class="cfg-explica">Ainda não há documentos no acervo para ler.</p>';
  }
  const m = d.medicao || {};
  const secoes = d.secoes || {};
  const ROTULO = {
    case: "Número do processo", dates: "Datas", amounts: "Valores",
    legal_references: "Leis citadas", jurisdiction: "Vara e comarca",
    classification: "Tipo do documento", parties: "Partes", summary: "Resumo",
    people: "Pessoas (CPF)", organizations: "Empresas (CNPJ)",
    requests: "Pedidos", decisions: "Decisões", events: "Linha do tempo",
    evidence: "Provas e anexos", claims: "Alegações", relationships: "Ligações",
  };
  const linhas = Object.keys(ROTULO).filter((k) => secoes[k]).map((k) => {
    const prontas = (secoes[k] || {}).ok || 0;
    return chaveCfg(ROTULO[k], prontas + " de " + d.no_acervo, prontas ? "" : "mute");
  }).join("");

  return ligaCfg("inteligencia", "Responder pelo que já foi lido",
      "consulta o que foi entendido antes de ler o documento de novo; desligado, tudo é lido a cada pergunta",
      Boolean((cfg.rascunho || {}).inteligencia)) +
    '<div class="cfg-chaves">' +
    chaveCfg("Documentos entendidos", d.documentos + " de " + d.no_acervo, d.documentos ? "" : "mute") +
    (m.perguntas ? chaveCfg("Perguntas sem abrir documento", m.no_metadata + " de " + m.perguntas + " · " + m.porcento + "%") : "") + "</div>" +
    (linhas ? '<div class="cfg-chaves cfg-chaves-duas">' + linhas + "</div>" : "") +
    '<p class="cfg-explica">O que é regra roda sozinho na indexação. Partes e resumo precisam do assistente e são lidos uma vez por documento, pelo terminal: ' +
    "<code>python -m inteligencia.retomar --assistente</code>. Fica tudo em " + esc(d.pasta || "data/conhecimento") + ", nesta máquina.</p>";
}

/* ---------------------------------------------------------- aprendizado */

function secaoAprendizado() {
  const ctx = cfg.ctx || { contextos: [], gavetas: [], caracteres: 0, limite: 2400, de_fora: 0 };
  const itens = ctx.contextos || [];
  const lendo = cfg.lendoArquivo || "";

  const guardados = itens.map((x) =>
    '<div class="cfg-lembrete' + (x.entra ? "" : " de-fora") + '"><span class="duas-linhas"><b>' + esc(x.titulo || "Sem título") + "</b><small>" + esc(x.texto) + "</small></span>" +
    '<small class="cfg-lixo-quando">' + esc(x.gaveta) + (x.entra ? "" : " · fora do limite") + "</small>" +
    '<button data-cfg-ensinar-editar="' + x.id + '">Alterar</button>' +
    '<button class="mais-linha" data-cfg-ensinar-tirar="' + x.id + '" title="Apagar">' + ic("delete", 16) + "</button></div>").join("");

  const lembretes = (guardados ? '<div class="cfg-linhas">' + guardados + "</div>" : '<p class="cfg-texto">Nenhum lembrete ainda.</p>') +
    '<div class="cfg-solta" id="cfg-solta-ensinar"><span class="duas-linhas"><b>' + (lendo ? "lendo “" + esc(lendo) + "”…" : "Arraste um PDF, DOCX, TXT ou MD para cá") + "</b>" +
    "<small>eu leio e proponho o lembrete; o arquivo não fica guardado</small></span>" +
    '<span class="cfg-botoes"><button data-cfg-ensinar-arquivo="1"' + (lendo ? " disabled" : "") + ">" + ic("folder_open", 16) + "Escolher arquivo</button>" +
    '<button class="primario com-icone" data-cfg-ensinar-novo="1">' + ic("add", 16) + "Escrever lembrete</button></span></div>" +
    '<p class="cfg-explica">Entram em toda pergunta da conversa, junto com os trechos dos documentos' +
    (ctx.de_fora ? "; " + plural(ctx.de_fora, "lembrete") + " não cabe no limite de " + ctx.limite + " caracteres e fica de fora" : "") + ".</p>";

  const d = cfg.hab || { grupos: [], contagem: {} };
  // So o que existe: o que ainda nao foi feito nao entra na lista.
  const grupos = (d.grupos || []).map((g) => ({ grupo: g.grupo, habilidades: g.habilidades.filter((h) => h.estado !== "em_breve") }))
    .filter((g) => g.habilidades.length);
  const total = grupos.reduce((n, g) => n + g.habilidades.length, 0);
  const grupo = (v, r) => { const classe = v === cfg.grupoHab ? "ativa" : ""; return '<button class="' + classe + '" data-cfg-grupo="' + esc(v) + '">' + esc(r) + "</button>"; };
  const mostrar = grupos.filter((g) => !cfg.grupoHab || g.grupo === cfg.grupoHab);
  const habs = mostrar.map((g) => g.habilidades.map((h) => {
    const classe = "cfg-hab" + (h.utilizavel ? " pronta" : "");
    let linha = "";
    if ((h.faltando || []).length) linha = "precisa de: " + h.faltando.join(", ");
    else if (h.demora) linha = h.demora;
    return '<div class="' + classe + '">' + ic(CFG_ICONE_HAB[h.id] || "auto_awesome", 18) + '<span class="duas-linhas"><b>' + esc(h.nome) + "</b><small>" + esc(h.resumo) + "</small>" +
      (linha ? "<small>" + esc(linha) + "</small>" : "") + "</span>" +
      (h.utilizavel ? '<button data-cfg-usar="' + esc(h.acao) + '">Usar</button>' : "") + "</div>";
  }).join("")).join("");
  const sei = grupos.length
    ? '<div class="visoes cfg-grupos">' + grupo("", "Todas · " + total) + grupos.map((g) => grupo(g.grupo, g.grupo + " · " + g.habilidades.length)).join("") + "</div>" +
      '<div class="cfg-habs">' + habs + "</div>"
    : '<p class="cfg-texto">Não consegui ler o catálogo de habilidades.</p>';

  const ficha = fichaCfg([
    ["Lembretes", String(itens.length)],
    ["Em uso", ctx.caracteres + " de " + ctx.limite + " caracteres"],
    ["Habilidades", String(total)],
  ]);

  return aberturaCfg() + ficha +
    cartaoCfg("Lembretes", metaCfg("o que eu devo saber do escritório"), lembretes) +
    cartaoCfg("O que eu sei fazer", metaCfg(plural(total, "habilidade")), sei);
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
  const aparencia = '<div class="cfg-temas">' + tema("claro", "Claro") + tema("escuro", "Escuro") + tema("auto", "Seguir o Windows") + "</div>" +
    '<p class="cfg-explica">Vale na hora e fica nesta máquina.</p>' +
    '<div class="cfg-sub">' + ligaCfg("animacoes_reduzidas", "Animações reduzidas", "sem deslizes nem pulsos; a tela troca direto", Boolean((cfg.rascunho || {}).animacoes_reduzidas)) + "</div>";

  const atalho = (rotulo, teclas) => '<div class="cfg-atalho"><span>' + esc(rotulo) + '</span><span class="cfg-teclas">' +
    teclas.map((t) => "<span>" + esc(t) + "</span>").join("") + "</span></div>";
  const atalhos = '<div class="cfg-linhas">' +
    atalho("Nova conversa", ["Ctrl", "N"]) + atalho("Buscar em tudo", ["Ctrl", "K"]) + atalho("Salvar (Documentos e Configurações)", ["Ctrl", "S"]) +
    atalho("Ir para Assistente", ["Ctrl", "1"]) + atalho("Ir para Agenda", ["Ctrl", "2"]) + atalho("Ir para Acervo", ["Ctrl", "3"]) +
    atalho("Fechar menus e painéis soltos", ["Esc"]) +
    atalho("Aprovar marcados, em Aprovações", ["Ctrl", "Enter"]) +
    atalho("Começar o ciclo de foco ou ir para a pausa", ["Ctrl", "Shift", "F"]) +
    atalho("Assinar o documento aberto", ["Ctrl", "Shift", "S"]) + "</div>" +
    '<p class="cfg-explica">Valem em qualquer tela, menos enquanto você escreve num campo.</p>';

  // Os avisos do Windows (src/avisos.py). A mesma chave que o interruptor da
  // tela de Foco muda; aqui ela segue o rascunho, como o resto da tela.
  const av = cfg.avisos || {};
  const r = cfg.rascunho || {};
  const avisos = av.disponivel
    ? ligaCfg("avisos_windows", "Avisar no Windows", "a notificação no canto da tela e o PAULUS piscando na barra de tarefas", Boolean(r.avisos_windows)) +
      /* Um interruptor por tipo, recuado sob o geral: desligar o geral cala todos. */
      (r.avisos_windows
        ? '<div class="cfg-avisos-tipos">' + (av.tipos || []).map((t) =>
            ligaCfg("avisos_tipos." + t.chave, t.rotulo, t.explica, ((r.avisos_tipos || {})[t.chave]) !== false)).join("") + "</div>"
        : "") +
      '<p class="cfg-explica">Resposta, aprovação e transcrição só avisam quando o PAULUS não está na frente. ' +
      "Lembretes e o alerta de pausa, só no horário de trabalho" + (av.horario ? " (" + esc(av.horario) + ")" : "") + ".</p>" +
      '<div class="cfg-botoes"><button data-cfg-aviso-teste="1">' + ic("notifications", 16) + "Mandar um aviso de teste</button></div>"
    : '<p class="cfg-texto">Os avisos só existem no Windows.</p>';

  return aberturaCfg() +
    cartaoCfg("Tema", "", aparencia) +
    cartaoCfg("Avisos", metaCfg("notificações do Windows"), avisos) +
    cartaoCfg("Atalhos", metaCfg("teclado"), atalhos);
}

/* ------------------------------------------------------------- feedback */

const CFG_TIPOS_FEEDBACK = [["bug", "bug_report", "Bug"], ["sugestao", "lightbulb", "Sugestão"], ["correcao", "edit_note", "Correção"], ["elogio", "favorite", "Elogio"], ["duvida", "help", "Dúvida"]];

/* O rascunho guardado nesta maquina volta quando a tela abre. */
function feedbackGuardado() {
  const padrao = { tipo: "bug", onde: "", titulo: "", texto: "", tecnico: true, contato: true };
  try {
    return Object.assign(padrao, JSON.parse(localStorage.getItem("paulus.feedback") || "{}"));
  } catch (err) { return padrao; }
}

function secaoFeedback() {
  const f = cfg.feedback;
  const s = cfg.status || {};
  const p = (cfg.rascunho || {}).pessoa || {};
  const tipos = CFG_TIPOS_FEEDBACK.map(([id, icone, rotulo]) => {
    const classe = "cfg-tipo" + (id === f.tipo ? " on" : "");
    return '<button class="' + classe + '" data-cfg-tipo="' + id + '">' + ic(icone, 18) + "<span>" + rotulo + "</span></button>";
  }).join("");
  const telas = ["Assistente", "Agenda", "Acervo", "Editor de documentos", "E-mail", "Assinatura", "Financeiro", "Cadastros", "Aprovações", "Configurações", "Outra"];
  const tecnico = "Windows · " + (s.modelo || "modelo local") + " · documentos no índice";
  const escrever = '<div class="cfg-campos"><div class="ag-campo"><label>Sobre o que é</label><div class="cfg-tipos">' + tipos + "</div></div>" +
    '<div class="ag-campo"><label>Onde aconteceu</label><select data-cfg-fb="onde"><option value="">escolha a tela…</option>' +
    telas.map((t) => '<option value="' + t + '"' + (t === f.onde ? " selected" : "") + ">" + t + "</option>").join("") + "</select></div>" +
    '<div class="ag-campo"><label>Título</label><input type="text" data-cfg-fb="titulo" value="' + esc(f.titulo) + '" placeholder="em uma linha"></div>' +
    '<div class="ag-campo"><label>Descreva</label><textarea data-cfg-fb="texto" placeholder="o que você fez, o que esperava e o que aconteceu; num bug, a tela e a hora ajudam">' + esc(f.texto) + "</textarea></div></div>" +
    '<div class="cfg-sub">' + ligaCfg("feedback.tecnico", "Incluir informações técnicas", tecnico, f.tecnico) +
    ligaCfg("feedback.contato", "Posso ser contatado sobre este feedback", p.email || "sem e-mail em Meus dados", f.contato) + "</div>" +
    '<div class="cfg-botoes cfg-botoes-fim"><button data-cfg-fb-guardar="1">' + ic("save", 16) + "Guardar rascunho</button>" +
    '<button class="primario com-icone" data-cfg-fb-copiar="1">' + ic("content_copy", 16) + "Copiar para enviar</button></div>";
  return aberturaCfg() + cartaoCfg("Escrever", metaCfg("o rascunho fica nesta máquina"), escrever);
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

/* --------------------------------------------------------- apoio e versao */

function secaoPlano() {
  const apoiar = '<p class="cfg-texto">Sem assinatura nem cobrança por uso. Quem usa e pode contribuir paga o desenvolvimento, por Pix ou cartão.</p>' +
    '<div class="cfg-botoes"><button class="primario com-icone" data-cfg-apoiar="contribuir">' + ic("favorite", 16) + "Apoiar o projeto</button>" +
    '<button data-cfg-apoiar="lista">Quem já apoia</button></div>';
  const versao = '<div class="cfg-chaves">' +
    chaveCfg("Versão", "em desenvolvimento · sem número ainda", "mute") +
    chaveCfg("Licença", "MIT · código aberto") +
    chaveCfg("Atualização", "manual · o programa não se atualiza sozinho") + "</div>" +
    '<div class="cfg-botoes"><button data-cfg-novidades="1">' + ic("article", 16) + "Novidades da versão</button></div>";
  return aberturaCfg() +
    cartaoCfg("Apoiar o projeto", "", apoiar) +
    cartaoCfg("Versão", "", versao);
}

/* ------------------------------------------------------------- lixeira */
/* O que foi apagado nos ultimos 30 dias, com Restaurar e Apagar de vez.
   O que passou do prazo ja sumiu antes de a lista ser lida. */

const CFG_ICONE_LIXO = {
  conversa: "forum", tarefa: "task_alt", compromisso: "event", servico: "work", gravacao: "graphic_eq",
  documento: "description", lancamento: "payments", cadastro: "person",
};

function secaoLixeira() {
  const l = cfg.lixo;
  if (!l) return aberturaCfg() + cartaoCfg("Itens apagados", "", '<p class="cfg-texto">não consegui ler a lixeira.</p>');
  const itens = l.itens || [];
  if (!itens.length) {
    return aberturaCfg() + cartaoCfg("Itens apagados", metaCfg("vazia"),
      '<p class="cfg-texto">Nada na lixeira. Conversa, tarefa, compromisso, serviço, gravação, documento, lançamento ou ficha que você apagar aparece aqui.</p>');
  }
  const linhas = itens.map((e) => '<div class="cfg-servico cfg-lixo-linha"><span class="cfg-servico-ic">' + ic(CFG_ICONE_LIXO[e.tipo] || "delete", 18) + "</span>" +
    '<div class="duas-linhas"><b>' + esc(e.titulo) + "</b><small>" + esc(e.tipo_rotulo + (e.detalhe ? " · " + e.detalhe : "")) + "</small></div>" +
    '<small class="cfg-lixo-quando">apagado ' + esc(quandoCurtoSv(e.apagado_em)) + " · some em " + plural(e.dias_restantes, "dia") + "</small>" +
    '<button data-cfg-lixo-restaurar="' + e.id + '">' + ic("undo", 16) + "Restaurar</button>" +
    '<button class="mais-linha" data-cfg-lixo-tirar="' + e.id + '" title="Apagar de vez">' + ic("close", 16) + "</button></div>").join("");
  const esvaziar = '<button class="sv-ligacao" data-cfg-lixo-esvaziar="1">' + ic("delete", 16) + "Esvaziar a lixeira</button>";
  return aberturaCfg(esvaziar) + cartaoCfg("Itens apagados", metaCfg(plural(itens.length, "item", "itens")),
    '<div class="cfg-linhas">' + linhas + "</div>" +
    '<p class="cfg-explica cfg-lixo-pe">Restaurar devolve a linha, as ligações e os arquivos ao lugar de onde saíram.</p>');
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
  clique("[data-cfg-salvar]", salvarConfig);
  clique("[data-cfg-descartar]", () => { cfg.rascunho = rascunhoDe(cfg.prefs.preferencias, cfg.prefs.modelo_atual); cfg.sujo = false; desenharConfig(); });
  clique("[data-cfg-ensinar-arquivo]", () => escolherArquivoParaEnsinar());
  clique("[data-cfg-ensinar-novo]", () => formLembrete(null));
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
  clique("[data-cfg-ensinar-editar]", (b) => {
    const item = ((cfg.ctx || {}).contextos || []).find((x) => x.id === Number(b.dataset.cfgEnsinarEditar));
    if (item) formLembrete(item);
  });
  clique("[data-cfg-ensinar-tirar]", async (b) => {
    const id = Number(b.dataset.cfgEnsinarTirar);
    const r = await fetch("/api/contextos/" + id, { method: "DELETE" });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    // O aviso le a resposta (e dela que sai o Desfazer); a lista vem depois.
    await avisarLixeira(r, recarregarLembretes);
    await recarregarLembretes();
  });
  clique("[data-cfg-cache]", async (b) => {
    const resposta = await dialogo({
      titulo: "Limpar o cache?",
      contexto: "Configurações › Acervo e índice",
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
  clique("[data-cfg-novidades]", mostrarNovidades);
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
  clique("[data-cfg-apoiar]", (b) => { marcarDestino("apoiar"); mostrarApoiar(b.dataset.cfgApoiar); });
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
  clique("[data-cfg-aviso-teste]", async (b) => {
    b.disabled = true;
    const t = await fetch("/api/avisos/teste", { method: "POST" }).then((x) => x.json()).catch(() => ({ ok: false }));
    b.disabled = false;
    avisoCert(t.ok ? "mandei um aviso de teste para o canto da tela" : "o Windows não mostrou o aviso de teste");
  });
  clique("[data-cfg-modelo]", (b) => { cfg.rascunho.modelo = b.dataset.cfgModelo; marcarConfigSuja(); desenharConfig(); });
  clique("[data-cfg-liga]", (b) => {
    const chave = b.dataset.cfgLiga;
    const ligada = !b.classList.contains("on");
    b.classList.toggle("on", ligada);
    if (chave.startsWith("feedback.")) { cfg.feedback[chave.split(".")[1]] = ligada; return; }
    porNoRascunho(chave, ligada);
    marcarConfigSuja();
    if (chave === "avisos_windows") { desenharConfig(); return; }
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
}

async function salvarConfig() {
  const r = cfg.rascunho;
  if (!r) return;
  const resposta = await fetch("/api/preferencias", {
    method: "POST", headers: CFG_JSON,
    body: JSON.stringify({
      pessoa: r.pessoa, autonomia: r.autonomia, escritorio: r.escritorio,
      modelo: r.modelo, timbre_no_pdf: r.timbre_no_pdf, devagar: r.devagar,
      animacoes_reduzidas: r.animacoes_reduzidas, inteligencia: r.inteligencia,
      avisos_windows: r.avisos_windows, avisos_tipos: r.avisos_tipos,
    }),
  });
  if (!resposta.ok) { avisoCert("não consegui salvar: " + (await erroDe(resposta))); return; }
  cfg.prefs = await resposta.json();
  cfg.rascunho = rascunhoDe(cfg.prefs.preferencias, cfg.prefs.modelo_atual);
  cfg.sujo = false;
  aplicarAnimacoes(cfg.prefs.preferencias.animacoes_reduzidas);
  avisoCert("salvo em data/preferencias.json, nesta máquina", { tom: "ok" });
  carregarStatus();
  if ($("cfg-tela")) desenharConfig();
}
