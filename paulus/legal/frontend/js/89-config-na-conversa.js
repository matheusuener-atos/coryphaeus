/* ------------------------------------- Configuracoes pela conversa (T5) */
/*
   O pacote de telas de 01/10/2026, T5 (`Conversa - Meus dados`, `- Aparencia`,
   `- Modulos`, `- Assistente e modelo`, `- Modelos`, `- Desempenho`,
   `- Teste`, `- Conexoes`, `- Word`, `- Acesso de fora`, `- Escritorio`,
   `- Backup`, `- Biblioteca`, `- Versao`, `- Lixeira`).

   "troquei de numero, agora e (94) 99123-4567" vira, por regra
   (src/config_pela_conversa.py), a secao de Configuracoes aberta na coluna
   de 460 px com as mudancas marcadas "novo", e na conversa o que muda, de
   quanto para quanto. A coluna e a MESMA secao da tela de Configuracoes
   (js/05-configuracoes.js), com os mesmos dados e as mesmas rotas: aqui so
   muda onde ela e desenhada (`cfg.host = "lado"`). Nada e gravado sem o
   "Salvar alteracoes" do rodape - e assinar sem revisar, enviar sem
   confirmar e a nuvem sem pedir a conversa nem marca.

   Como a secao usa as funcoes de sempre, os redesenhos dela (um toggle, a
   lixeira restaurada, o backup andando) caem aqui: desenharConfig e
   mostrarConfig olham se a coluna esta aberta e se o ultimo toque foi nela.
*/

const cfn = {
  d: null, caixa: null, secao: "", novos: new Set(), atencao: [], destacar: [], extra: {},
  tema: null, tarefas: {}, lembrete: null, busca: "", toqueNoLado: false, teste: null,
};

const CFN_ICONE = { conexoes: "link", acesso: "link", word: "description", aprendizado: "description", backup: "history", lixeira: "history" };

/* O que cada secao diz no rodape quando nada mudou: [texto, rotulo, icone, seletor do botao da secao]. */
const CFN_PE = {
  plano: ["nenhuma mudança", "Verificar agora", "refresh", '[data-cfg-atu="verificar"]'],
  desempenho: ["sem documentos, nomes de clientes nem conversas", "Gerar diagnóstico", "", "[data-cfg-diagnostico]"],
  lixeira: ["", "Esvaziar a lixeira", "close", "[data-cfg-lixo-esvaziar]"],
  vinculos: ["o convite sai depois do vínculo com o Google", "Convidar pela internet", "mail", ""],
  acesso: ["nada é criado antes de você confirmar", "Criar a conta", "check", "[data-cx-criar-conta], [data-acesso-nova]"],
  conexoes: ["esperando o QR · a mensagem fica pronta no chat", "Abrir WhatsApp Web", "", ""],
  word: ["depois, o Word abre sozinho com o PAVLVS", "Instalar no Word", "download", '[data-word-acao="instalar"]'],
};

/* Os nomes curtos do rodape ("2 mudanças · tema e bem-estar"). */
const CFN_CURTO = {
  "pessoa.telefone": "telefone", "pessoa.email": "e-mail", "pessoa.oab": "OAB", "pessoa.cpf": "CPF", "pessoa.endereco": "endereço",
  "pessoa.nome": "nome", "escritorio.nome": "nome do escritório", "escritorio.cnpj": "CNPJ", "escritorio.oab": "OAB da sociedade",
  "timbre_no_pdf": "papel timbrado", tema: "tema", animacoes_reduzidas: "animações", avisos_windows: "avisos do Windows",
  "avisos_tipos.bem_estar": "bem-estar", "avisos_tipos.resposta": "resposta pronta", "avisos_tipos.aprovacao": "aprovação",
  "avisos_tipos.gravacao": "transcrição", "avisos_tipos.agenda": "compromisso", "avisos_tipos.acesso": "acesso de fora",
  "autonomia.organizar_mover": "mover arquivos", "autonomia.ler_pastas": "ler as pastas", "autonomia.agentes_sozinhos": "agentes",
  "autonomia.assinar": "assinar", "autonomia.enviar_mensagem": "enviar", "autonomia.modelo_nuvem": "nuvem",
  devagar: "ir devagar", modelo: "modelo", inteligencia: "o que já foi lido",
  "atualizacoes.verificar": "verificar atualizações", "atualizacoes.avisar_antes": "avisar antes de instalar",
  "tarefas_modelo.conversa": "perguntas", "tarefas_modelo.juiz": "julgamentos rápidos", "tarefas_modelo.email": "e-mail",
  "tarefas_modelo.redacao": "redação", "tarefas_modelo.resumos": "resumos", "tarefas_modelo.leitura": "leitura",
};

function cfgNoLado() {
  return cfg.host === "lado" && papelDoLado() === "configuracao" && Boolean(document.querySelector("#lado-ferramenta [data-fl-tipo='config']"));
}

/* O ultimo toque foi na coluna? Os dialogos que ela abre (confirmar,
   escolher a pasta) nao contam: sao dela. */
(function () {
  const anotar = (e) => {
    const t = e.target;
    if (!t || !t.closest) return;
    if (t.closest("#lado-ferramenta")) cfn.toqueNoLado = true;
    else if (!t.closest("#veu-dialogo, .veu, .dialogo, .menu-na-linha, .escolha-lista, .flutuante")) cfn.toqueNoLado = false;
  };
  document.addEventListener("pointerdown", anotar, true);
  document.addEventListener("keydown", anotar, true);
})();

/* ------------------------------------- as funcoes de Configuracoes, na coluna */

const _mostrarConfigNaTela = mostrarConfig;
mostrarConfig = function (secao) {
  // A secao pediu para se redesenhar (restaurou, mediu, ligou): fica na coluna.
  if (cfgNoLado() && cfn.toqueNoLado) return recarregarConfigNoLado(secao);
  return _mostrarConfigNaTela(secao);
};

const _desenharConfigNaTela = desenharConfig;
desenharConfig = function () {
  if (cfgNoLado()) return desenharConfigNoLado(false);
  if (cfg.host === "lado") return undefined;
  return _desenharConfigNaTela();
};

const _marcarConfigSuja = marcarConfigSuja;
marcarConfigSuja = function () {
  _marcarConfigSuja();
  if (cfgNoLado()) atualizarPeDaConfig();
};

const _salvarConfig = salvarConfig;
salvarConfig = function () {
  if (cfgNoLado()) return salvarConfigDoLado();
  return _salvarConfig();
};

/* O tema na coluna espera o Salvar, como o resto (na tela de Configuracoes
   ele vale na hora). */
const _escolherTema = escolherTema;
escolherTema = function (escolha) {
  if (cfgNoLado() && !cfn.aplicando) {
    cfn.tema = escolha === _temaEscolhido() ? null : escolha;
    if (cfn.tema) cfn.novos.add("tema");
    cfg.sujo = pendentesDaConfig().length > 0;
    return;
  }
  return _escolherTema(escolha);
};

/* O tema da coluna: o que a conversa propos, ate salvar. */
const _temaEscolhido = temaEscolhido;
temaEscolhido = function () {
  if (cfg.host === "lado" && cfn.tema) return cfn.tema;
  return _temaEscolhido();
};

/* ------------------------------------------------------------- o cartao */

function cartaoDaConfig(d) {
  return '<div class="cfc" data-cfc="1">' + htmlDoCartaoDaConfig(d) + "</div>";
}

function iconeDaLinha(tom) {
  if (tom === "ok") return '<span class="cfc-ic ok">' + ic("check_circle", 16) + "</span>";
  if (tom === "aviso") return '<span class="cfc-ic aviso">' + ic("error", 16) + "</span>";
  if (tom === "erro") return '<span class="cfc-ic erro">' + ic("error", 16) + "</span>";
  if (tom === "pendente") return '<span class="cfc-ic">' + ic("schedule", 16) + "</span>";
  if (tom === "info") return '<span class="cfc-ic">' + ic("info", 16) + "</span>";
  return "";
}

function linhaDoCartao(l) {
  const mono = l.mono || /^pessoa\.(telefone|cpf)$|^escritorio\.cnpj$/.test(l.chave || "");
  const antes = l.antes ? '<span class="cfc-antes' + (l.riscar ? " riscado" : "") + (mono ? " mono" : "") + '">' + esc(l.antes) + "</span>" + ic("arrow_forward", 14) : "";
  const depois = l.depois ? '<b class="' + (mono ? "mono" : "") + (l.tom === "aviso" || l.tom === "pendente" || l.tom === "erro" ? " cfc-leve" : "") + '">' + esc(l.depois) + "</b>" : "";
  const icone = l.icone === "speed" ? '<span class="cfc-ic ok">' + ic("speed", 16) + "</span>" : iconeDaLinha(l.tom);
  return '<div class="cfc-linha' + (l.tom === "neutro" ? " neutra" : "") + (l.tom === "info" ? " info" : "") + '">' + icone +
    '<span class="cfc-campo">' + esc(l.campo) + '</span><span class="cfc-valor">' + antes + depois + "</span></div>";
}

function htmlDoCartaoDaConfig(d) {
  const x = d.extra || {};
  let corpo = "";
  if (d.secao === "lixeira") {
    corpo = (x.achados || []).slice(0, 1).map((e) => '<div class="cfc-bloco cfc-item"><span class="caixa-tipo">' + ic(CFG_ICONE_LIXO[e.tipo] || "description", 18) + "</span>" +
      '<span class="duas-linhas"><b>' + esc(e.titulo) + "</b><small>" + esc([e.tipo_rotulo, e.detalhe, "apagado " + quandoCurtoSv(e.apagado_em)].filter(Boolean).join(" · ")) + "</small></span>" +
      '<button type="button" class="primario com-icone" data-cfc-restaurar="' + e.id + '">' + ic("undo", 16) + "Restaurar</button></div>").join("");
  } else if (d.secao === "aprendizado") {
    corpo = '<div class="cfc-bloco cfc-lembrete"><span class="emc-kicker">Lembrete · regra da casa</span><p data-cfc-lembrete="1">' + esc(cfn.d === d && cfn.lembrete != null ? cfn.lembrete : x.lembrete || "") + "</p></div>";
  } else if (d.secao === "word") {
    corpo = '<div class="cfc-bloco">' + (x.passos || []).map((p, i) => {
      const atual = !p.feito && (i === 0 || x.passos[i - 1].feito);
      const marca = p.feito ? '<span class="cfc-passo feito">' + ic("check", 14) + "</span>" : '<span class="cfc-passo' + (atual ? " atual" : "") + '">' + (atual ? i + 1 : "") + "</span>";
      return '<div class="cfc-linha cfc-passo-linha' + (!p.feito && !atual ? " depois" : "") + '">' + marca + '<span class="duas-linhas"><b>' + esc(p.titulo) + "</b><small>" + esc(p.sub) + "</small></span></div>";
    }).join("") + "</div>";
  } else if (d.secao === "acesso") {
    corpo = '<div class="cfc-bloco">' + (x.pontos || []).map((p) =>
      '<div class="cfc-linha"><span class="cfc-ic">' + ic(p.icone, 15) + '</span><span class="cfc-campo">' + esc(p.texto) + "</span></div>").join("") + "</div>";
  } else if (d.secao === "conexoes") {
    const c = x.contato || {};
    corpo = '<div class="cfc-bloco cfc-whats"><div class="cfc-whats-topo"><span class="emc-avatar">WA</span><span class="duas-linhas"><b>' + esc(c.nome || "Sem contato em Cadastros") + "</b>" +
      '<small class="mono">' + esc(c.telefone || "o número você põe ao abrir") + '</small></span><small>WhatsApp</small></div><p data-cfc-msg="1">' + esc(x.mensagem || "") + "</p></div>";
  } else if (d.secao === "desempenho" && x.teste) {
    corpo = '<div class="cfc-bloco cfc-teste" data-cfc-teste="1">' + htmlDoTeste(d) + "</div>";
  } else if ((d.linhas || []).length) {
    corpo = '<div class="cfc-bloco">' + d.linhas.map(linhaDoCartao).join("") + "</div>";
  }
  if (d.secao !== "conexoes" && d.secao !== "lixeira" && d.secao !== "word" && d.secao !== "acesso" && d.secao !== "aprendizado" && !(d.secao === "desempenho" && x.teste) && !(d.linhas || []).length) corpo = "";
  if (d.secao === "vinculos" && (d.linhas || []).length) corpo = '<div class="cfc-bloco">' + d.linhas.map(linhaDoCartao).join("") + "</div>";
  const depois = x.depois ? '<p class="cfc-depois">' + esc(x.depois) + "</p>" : "";
  const acoes = acoesDoCartao(d).map((a, i) =>
    '<button type="button" class="' + (a.primario ? "primario " : "") + 'com-icone" data-cfc-acao="' + i + '">' + (a.icone ? ic(a.icone, 15) : "") + esc(a.rotulo) + "</button>").join("");
  const nota = d.nota ? '<p class="cfc-nota">' + esc(d.nota) + "</p>" : "";
  return corpo + depois + (acoes ? '<div class="cfc-acoes">' + acoes + "</div>" : "") + nota;
}

/* Os botoes que nascem do que o cartao mostra (e nao da frase). */
function acoesDaSecao(d) {
  const x = d.extra || {};
  const a = [];
  if (d.secao === "lixeira") (x.vizinhos || []).forEach((v) => a.push({ rotulo: "Restaurar “" + v.titulo + "” também", faz: "restaurar", id: v.id }));
  if (d.secao === "word" && /\bcit[aã]/i.test(d.pergunta || "")) {
    const m = /(?:conferir|confira|checar)\s+(?:as\s+)?cita[çc][õo]es\s+(d[aeo]s?\s+.+?)[.?!]*$/i.exec(d.pergunta || "");
    a.push({ rotulo: "Conferir aqui na conversa", faz: "pedir", pedido: "confira as citações " + (m ? m[1] : "do documento") });
  }
  if (d.secao === "vinculos") a.push({ rotulo: "Ver permissões", faz: "rolar", alvo: "permissoes" });
  return a;
}

function ligarConfigNaProposta(caixa, d) {
  const alvo = caixa.querySelector("[data-cfc]");
  if (!alvo) return;
  if (caixa.dataset.propostaGuardada) {
    alvo.insertAdjacentHTML("beforeend", '<div class="cfc-acoes"><button type="button" class="com-icone" data-cfc-reabrir="1">' + ic("settings", 15) +
      "Abrir " + esc(d.titulo || "Configurações") + " ao lado</button></div>");
    alvo.querySelectorAll("[data-cfc-acao], [data-cfc-restaurar]").forEach((b) => { b.disabled = true; });
    alvo.querySelector("[data-cfc-reabrir]").onclick = () => abrirConfigNoLado(d, alvo);
    return;
  }
  ligarAcoesDoCartao(alvo, d);
  abrirConfigNoLado(d, alvo);
}

/* Os do Escritorio vem antes ("Ver permissões" primeiro, como na tela). */
function acoesDoCartao(d) {
  return d.secao === "vinculos" ? acoesDaSecao(d).concat(d.acoes || []) : (d.acoes || []).concat(acoesDaSecao(d));
}

function ligarAcoesDoCartao(alvo, d) {
  const acoes = acoesDoCartao(d);
  alvo.querySelectorAll("[data-cfc-acao]").forEach((b) => {
    b.onclick = () => fazerAcaoDoCartao(acoes[Number(b.dataset.cfcAcao)], b, d);
  });
  alvo.querySelectorAll("[data-cfc-restaurar]").forEach((b) => {
    b.onclick = () => restaurarPelaConversa(Number(b.dataset.cfcRestaurar), b);
  });
}

async function fazerAcaoDoCartao(a, botao, d) {
  if (!a) return;
  if (!cfgNoLado() && a.faz !== "pedir" && a.faz !== "copiar") await abrirConfigNoLado(d, cfn.caixa);
  const lado = $("lado-ferramenta");
  if (a.faz === "focar") {
    const campo = lado.querySelector('[data-cfg-campo="' + a.chave + '"]');
    if (campo) { campo.scrollIntoView({ block: "center", behavior: animacoesLigadas() ? "smooth" : "auto" }); campo.focus(); }
  } else if (a.faz === "salvar_so") {
    // Desfaz no rascunho o que nao esta na lista e salva o resto.
    const base = rascunhoDe(cfg.prefs.preferencias, cfg.prefs.modelo_atual);
    pendentesDaConfig().forEach((m) => {
      if (!a.chaves.includes(m.chave)) { porNoRascunho(m.chave, valorEm(base, m.chave)); cfn.novos.delete(m.chave); }
    });
    if (cfn.tema && !a.chaves.includes("tema")) cfn.tema = null;
    await salvarConfigDoLado();
  } else if (a.faz === "marcar") {
    porNoRascunho(a.chave, a.valor);
    cfn.novos.add(a.chave);
    cfg.sujo = true;
    botao.disabled = true;
    desenharConfigNoLado(false);
    notaDeFeitoNaConversa("Marquei “" + (CFN_CURTO[a.chave] || a.chave) + "” ao lado — vale quando você salvar.");
  } else if (a.faz === "clicar") {
    const alvo = lado.querySelector(a.seletor);
    if (alvo) alvo.click();
    else if (a.seletor === "[data-cfg-diagnostico]") baixarDiagnostico();
    else if (a.seletor === "[data-cfg-novidades]") mostrarNovidades();
    else if (a.seletor === "[data-cfg-equipe]") mostrarCadastros("equipe");
  } else if (a.faz === "medir") {
    botao.disabled = true;
    botao.textContent = "medindo…";
    await medirModelo(a.nome);
    botao.textContent = "Medido";
  } else if (a.faz === "rolar") {
    const ancoras = { catalogo: '[data-cartao="baixar"]', permissoes: '[data-cartao="a-equipe"]' };
    const alvo = lado.querySelector(ancoras[a.alvo] || "");
    if (alvo) alvo.scrollIntoView({ block: "start", behavior: animacoesLigadas() ? "smooth" : "auto" });
  } else if (a.faz === "copiar") {
    copiarTexto((d.extra || {}).mensagem || "", "mensagem copiada");
  } else if (a.faz === "pedir") {
    $("pedido").value = a.pedido;
    enviar();
  } else if (a.faz === "restaurar") {
    await restaurarPelaConversa(a.id, botao);
  }
}

function baixarDiagnostico() {
  const a = document.createElement("a");
  a.href = "/api/saude/diagnostico";
  a.download = "";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

/* ------------------------------------------------------------- a coluna */

async function abrirConfigNoLado(d, caixa) {
  cfn.d = d;
  cfn.caixa = caixa || cfn.caixa;
  cfn.secao = d.secao;
  cfn.novos = new Set();
  cfn.extra = d.extra || {};
  cfn.atencao = (d.extra || {}).atencao || [];
  cfn.destacar = (d.extra || {}).destacar || [];
  cfn.tema = null;
  cfn.tarefas = {};
  cfn.lembrete = d.secao === "aprendizado" ? ((d.extra || {}).lembrete || "") : null;
  cfn.busca = d.secao === "lixeira" ? ((d.extra || {}).busca || "") : "";
  cfn.backupPasta = d.secao === "backup" ? ((d.extra || {}).pasta_sugerida || "") : "";
  cfn.convite = d.secao === "vinculos" ? ((d.extra || {}).convite || null) : null;
  cfg.host = "lado";
  cfg.secao = d.secao;
  pararMedicao();
  try {
    const [p, s] = await Promise.all([
      fetch("/api/preferencias").then((r) => r.json()),
      fetch("/api/status").then((r) => r.json()).catch(() => null),
    ]);
    cfg.prefs = p;
    cfg.status = s;
    cfg.rascunho = rascunhoDe(p.preferencias, p.modelo_atual);
    cfg.sujo = false;
    await carregarSecao();
  } catch (err) {
    avisoCert("não consegui ler as Configurações: " + err, { tom: "erro" });
    return;
  }
  if (d.secao === "lixeira") cfn.busca = (d.extra || {}).busca || "";
  (d.mudancas || []).forEach((m) => {
    if (m.chave === "tema") cfn.tema = m.valor;
    else if (m.chave.startsWith("tarefas_modelo.")) cfn.tarefas[m.chave.split(".")[1]] = m.valor;
    else porNoRascunho(m.chave, m.chave === "pessoa.telefone" ? formatarTelefone(m.valor) : m.valor);
    cfn.novos.add(m.chave);
  });
  if (cfn.backupPasta) cfn.novos.add("backup.pasta");
  if (cfn.lembrete) cfn.novos.add("lembrete");
  if (cfn.convite) cfn.novos.add("convite");
  cfg.sujo = pendentesDaConfig().length > 0;
  desenharConfigNoLado(true);
  if (d.secao === "desempenho" && cfn.extra.teste && cfn.caixa && !cfn.caixa.closest("[data-proposta-guardada]")) rodarTesteDosModelos();
}

async function recarregarConfigNoLado(secao) {
  if (secao && secao !== cfg.secao) cfg.secao = secao;
  try {
    if (cfg.recarregar) {
      cfg.prefs = await fetch("/api/preferencias").then((r) => r.json());
      cfg.recarregar = false;
      if (!pendentesDaConfig().length) cfg.rascunho = rascunhoDe(cfg.prefs.preferencias, cfg.prefs.modelo_atual);
    }
    await carregarSecao();
  } catch (err) { /* fica o que estava */ }
  desenharConfigNoLado(false);
}

function tituloDaColuna() {
  const achada = CFG_SECOES.find((s) => s[0] === cfg.secao) || ["", "Configurações"];
  if (cfg.secao === "desempenho" && cfn.teste && !cfn.teste.fim) return "Desempenho · teste em andamento";
  return achada[1];
}

function subDaColuna() {
  if (cfg.secao === "desempenho" && cfn.teste && !cfn.teste.fim) return "o processador sobe enquanto mede";
  return (cfn.d && cfn.d.secao === cfg.secao && cfn.d.sub) || "";
}

function htmlDaConfigNoLado() {
  let secao;
  try {
    if (cfg.secao === "assistente") secao = secaoAssistente();
    else if (cfg.secao === "modelos") secao = secaoModelos();
    else if (cfg.secao === "desempenho") secao = secaoDesempenho();
    else if (cfg.secao === "conexoes") secao = secaoConexoes();
    else if (cfg.secao === "vinculos") secao = secaoVinculos();
    else if (cfg.secao === "aprendizado") secao = secaoAprendizado();
    else if (cfg.secao === "aparencia") secao = secaoAparencia();
    else if (cfg.secao === "backup") secao = secaoBackup();
    else if (cfg.secao === "menu") secao = secaoModulos();
    else if (cfg.secao === "plano") secao = secaoPlano();
    else if (cfg.secao === "lixeira") secao = secaoLixeira();
    else if (cfg.secao === "acesso") secao = secaoAcesso();
    else if (cfg.secao === "word") secao = secaoWord();
    else secao = secaoPerfil();
  } catch (err) {
    secao = '<p class="nota">não consegui desenhar esta seção: ' + esc(String(err)) + "</p>";
  }
  return '<div class="cfn" data-fl-tipo="config" data-cfn-secao="' + esc(cfg.secao) + '">' +
    '<div class="cfn-topo"><span class="cfn-ic">' + ic(CFN_ICONE[cfg.secao] || "settings", 18) + "</span>" +
    '<span class="cfn-titulo"><b>' + esc(tituloDaColuna()) + "</b><small>Configurações" + (subDaColuna() ? " · " + esc(subDaColuna()) : "") + "</small></span>" +
    '<button type="button" class="em-ligacao cfn-abrir" data-cfn-abrir="1">Abrir em Configurações' + ic("open_in_new", 14) + "</button>" +
    '<button type="button" class="icone cfn-fechar" data-cfn-fechar="1" title="Fechar" aria-label="Fechar">' + ic("close", 18) + "</button></div>" +
    '<div class="cfn-corpo cfg-tela" id="cfg-tela"><div class="cfg-secao">' + secao + "</div></div>" +
    '<div class="cfn-pe" data-cfn-pe="1"></div></div>';
}

function desenharConfigNoLado(abrir) {
  const html = htmlDaConfigNoLado();
  if (abrir || !cfgNoLado()) {
    abrirNoLado("configuracao", { chave: "config", html: html, aoFechar: fecharConfigDoLado });
  } else {
    const lado = $("lado-ferramenta");
    const corpo = lado.querySelector(".cfn-corpo");
    const topo = corpo ? corpo.scrollTop : 0;
    lado.innerHTML = html;
    const novo = lado.querySelector(".cfn-corpo");
    if (novo) novo.scrollTop = topo;
  }
  depoisDeDesenharNoLado();
}

function depoisDeDesenharNoLado() {
  const lado = $("lado-ferramenta");
  ligarConfig();
  if (cfg.secao === "desempenho") comecarMedicao();
  if (cfg.secao === "plano" && typeof ligarAtualizacao === "function") ligarAtualizacao(lado);
  if (cfg.secao === "assistente") blocoLeis();
  if (cfg.secao === "modelos") ligarTarefasNoLado(lado);
  if (cfg.secao === "lixeira") ligarBuscaDaLixeira(lado);
  if (cfg.secao === "aprendizado") ligarLembreteNoLado(lado);
  if (cfg.secao === "backup") ligarBackupNoLado(lado);
  marcarNovosNoLado(lado);
  lado.querySelector("[data-cfn-fechar]").onclick = () => fecharColunaDaConfig();
  lado.querySelector("[data-cfn-abrir]").onclick = () => abrirNaTelaDeConfiguracoes();
  if (typeof melhorarCampos === "function") melhorarCampos(lado);
  atualizarPeDaConfig();
}

/* O selo "novo" no que a conversa mudou, e o aviso no que pede atencao. */
function marcarNovosNoLado(lado) {
  const selo = '<span class="cfn-novo">novo</span>';
  cfn.novos.forEach((k) => {
    const campo = lado.querySelector('[data-cfg-campo="' + k + '"]');
    if (campo) {
      const caixa = campo.closest(".ag-campo");
      if (caixa) { caixa.classList.add("cfn-com-selo"); campo.insertAdjacentHTML("afterend", selo); }
      return;
    }
    const liga = lado.querySelector('[data-cfg-liga="' + k + '"]');
    if (liga) { const b = liga.querySelector("b"); if (b) b.insertAdjacentHTML("beforeend", selo); return; }
    if (k === "tema" && cfn.tema) {
      const t = lado.querySelector('[data-cfg-tema="' + cfn.tema + '"]');
      // Antes do rotulo: o rotulo do cartao e o ultimo span (17-configuracoes.css).
      if (t && t.lastElementChild) t.lastElementChild.insertAdjacentHTML("beforebegin", selo);
      return;
    }
    if (k === "modelo") {
      const m = lado.querySelector('[data-cfg-modelo="' + cfg.rascunho.modelo + '"] b');
      if (m) m.insertAdjacentHTML("beforeend", selo);
      return;
    }
    if (k.startsWith("tarefas_modelo.")) {
      const s = lado.querySelector('[data-mod-tarefa="' + k.split(".")[1] + '"]');
      const alvo = s && (s.nextElementSibling && s.nextElementSibling.classList.contains("escolha-botao") ? s.nextElementSibling : s);
      if (alvo) { alvo.classList.add("cfn-com-selo-escolha"); alvo.insertAdjacentHTML("beforeend", selo); }
    }
  });
  cfn.atencao.forEach((k) => {
    const campo = lado.querySelector('[data-cfg-campo="' + k + '"]');
    if (!campo) return;
    const caixa = campo.closest(".ag-campo");
    if (caixa && !caixa.classList.contains("cfn-atencao")) {
      caixa.classList.add("cfn-atencao");
      campo.insertAdjacentHTML("afterend", '<span class="cfn-atencao-ic" title="falta preencher para o timbre">' + ic("error", 16) + "</span>");
    }
  });
  cfn.destacar.forEach((k) => {
    const liga = lado.querySelector('[data-cfg-liga="' + k + '"]');
    if (liga) liga.classList.add("cfn-destaque");
  });
}

/* --------------------------------------------- o que esta por salvar */

function valorEm(obj, chave) {
  let v = obj;
  for (const p of chave.split(".")) v = v == null ? undefined : v[p];
  return v;
}

/* O rascunho contra o que esta gravado, folha por folha. */
function pendentesDaConfig() {
  if (!cfg.prefs || !cfg.rascunho) return [];
  const base = rascunhoDe(cfg.prefs.preferencias, cfg.prefs.modelo_atual);
  const saida = [];
  const andar = (a, b, prefixo) => {
    Object.keys(Object.assign({}, a || {}, b || {})).forEach((k) => {
      const chave = prefixo ? prefixo + "." + k : k;
      const va = (a || {})[k];
      const vb = (b || {})[k];
      if (va && typeof va === "object" && !Array.isArray(va)) andar(va, vb, chave);
      else if (vb && typeof vb === "object" && !Array.isArray(vb)) andar(va, vb, chave);
      else if (JSON.stringify(va === undefined ? null : va) !== JSON.stringify(vb === undefined ? null : vb)) {
        // Vazio e ausente sao a mesma coisa; o avisos_tipos/modulos ausente vale "ligado".
        const vazio = (x) => x === undefined || x === null || x === "";
        if (vazio(va) && vazio(vb)) return;
        if (/^(avisos_tipos|modulos)\./.test(chave) && (va === true || va === undefined) && (vb === true || vb === undefined)) return;
        if (/^pessoa\.(telefone|cpf)$|^escritorio\.cnpj$/.test(chave) && String(va || "").replace(/\D/g, "") === String(vb || "").replace(/\D/g, "")) return;
        saida.push({ chave: chave, valor: va });
      }
    });
  };
  andar(cfg.rascunho, base, "");
  if (cfn.tema && cfn.tema !== _temaEscolhido()) saida.unshift({ chave: "tema", valor: cfn.tema });
  Object.keys(cfn.tarefas).forEach((t) => {
    const atual = ((((mod.dados || {}).tarefas) || []).find((x) => x.id === t) || {}).modelo || "";
    if (cfn.tarefas[t] !== atual) saida.push({ chave: "tarefas_modelo." + t, valor: cfn.tarefas[t] });
  });
  return saida;
}

function juntarComE(xs) {
  return xs.length > 1 ? xs.slice(0, -1).join(", ") + " e " + xs[xs.length - 1] : (xs[0] || "");
}

function atualizarPeDaConfig() {
  const pe = document.querySelector("#lado-ferramenta [data-cfn-pe]");
  if (!pe) return;
  const pend = pendentesDaConfig();
  const n = pend.length;
  let html;
  if (cfg.secao === "aprendizado" && cfn.lembrete != null) {
    html = '<small class="cfn-resumo">1 lembrete por guardar</small><button type="button" class="fantasma" data-cfn-descartar="1">Descartar</button>' +
      '<button type="button" class="primario com-icone" data-cfn-lembrete="1">' + ic("check", 16) + "Guardar lembrete</button>";
  } else if (cfg.secao === "backup" && cfn.d && cfn.d.secao === "backup" && !((cfg.backup || {}).ultimo)) {
    const b = cfg.backup || {};
    html = '<small class="cfn-resumo">' + (b.tem_senha ? "a senha está guardada" : "defina a senha para fazer o primeiro") + "</small>" +
      '<button type="button" class="primario com-icone" data-cfn-backup="1">' + ic("check", 16) + "Salvar e fazer backup agora</button>";
  } else if (cfg.secao === "desempenho" && cfn.teste && !cfn.teste.fim) {
    html = '<small class="cfn-resumo">o resultado corrige a estimativa de todos</small><button type="button" class="com-icone" data-cfn-parar="1">' +
      ic("stop_circle", 16) + "Parar teste</button>";
  } else if (n) {
    const nomes = pend.map((m) => CFN_CURTO[m.chave] || (m.chave.startsWith("modulos.") ? nomeDoModulo(m.chave.split(".")[1]) : m.chave.split(".").pop()));
    const atencao = cfn.atencao.filter((k) => !valorDoRascunho(k) || /^0+$/.test(String(valorDoRascunho(k)).replace(/\D/g, ""))).length;
    html = '<small class="cfn-resumo">' + plural(n, "mudança") + " · " + esc(atencao ? plural(atencao, "campo") + " pede atenção" : juntarComE(nomes)) + "</small>" +
      '<button type="button" class="fantasma" data-cfn-descartar="1">Descartar</button>' +
      '<button type="button" class="primario com-icone" data-cfn-salvar="1">' + ic("check", 16) + "Salvar alterações</button>";
  } else {
    const p = CFN_PE[cfg.secao];
    let texto = p ? p[0] : "nenhuma mudança";
    if (cfg.secao === "lixeira") texto = plural(((cfg.lixo || {}).itens || []).length, "item", "itens") + " na lixeira";
    let botao = "";
    if (p) {
      let rotulo = p[1];
      let icone = p[2];
      if (cfg.secao === "word") {
        const w = cfg.word || {};
        rotulo = !w.ligado ? "Ligar o PAVLVS" : ((w.instalacao || {}).instalado ? "Abrir o Word com o PAVLVS" : "Instalar no Word");
        icone = !w.ligado ? "check" : ((w.instalacao || {}).instalado ? "description" : "download");
      }
      const desligado = (cfg.secao === "vinculos" && !vinculadoAoGoogle()) || (cfg.secao === "acesso" && !document.querySelector("#lado-ferramenta " + (p[3] || "x")));
      if (cfg.secao === "vinculos" && vinculadoAoGoogle()) texto = "nada é enviado antes do seu clique";
      if (cfg.secao === "conexoes" && ((cfg.cx || {}).sessao || {}).existe) texto = "a mensagem vai escrita; enviar é com você";
      if (!(cfg.secao === "acesso" && desligado)) {
        botao = '<button type="button" class="' + (cfg.secao === "lixeira" ? "fantasma " : "") + 'com-icone" data-cfn-pe-acao="1"' + (desligado ? " disabled" : "") + ">" +
          (icone ? ic(icone, 16) : "") + esc(rotulo) + "</button>";
      }
    }
    html = '<small class="cfn-resumo">' + esc(texto) + "</small>" + botao;
  }
  pe.innerHTML = html;
  const ligar = (sel, fn) => { const b = pe.querySelector(sel); if (b) b.onclick = (e) => { e.stopPropagation(); fn(b); }; };
  ligar("[data-cfn-salvar]", () => salvarConfigDoLado());
  ligar("[data-cfn-descartar]", () => descartarNoLado());
  ligar("[data-cfn-lembrete]", (b) => guardarLembreteDoLado(b));
  ligar("[data-cfn-backup]", (b) => salvarBackupDoLado(b));
  ligar("[data-cfn-parar]", () => { if (cfn.teste) cfn.teste.parar = true; avisoCert("o teste para depois do modelo que está medindo"); });
  ligar("[data-cfn-pe-acao]", (b) => acaoDoPe(b));
  atualizarMetaDaConversa();
}

function nomeDoModulo(id) {
  const m = (typeof MODULOS_BV !== "undefined" ? MODULOS_BV : []).find((x) => x[0] === id);
  return m ? m[2] : id;
}

function vinculadoAoGoogle() {
  return typeof vinc !== "undefined" && vinc && vinc.estado ? Boolean(vinc.estado.vinculado) : Boolean(cfn.extra && cfn.extra.vinculado);
}

function acaoDoPe(botao) {
  const lado = $("lado-ferramenta");
  if (cfg.secao === "vinculos") {
    const c = cfn.convite || {};
    convidarPessoa(null, async () => { await carregarAcessoDaEquipe(); desenharConfigNoLado(false); }, { nome: c.nome || "", email: c.email || "" });
    return;
  }
  if (cfg.secao === "conexoes") { abrirWhatsappDaConversa(botao); return; }
  if (cfg.secao === "desempenho") { baixarDiagnostico(); return; }
  if (cfg.secao === "word") {
    const w = cfg.word || {};
    const alvo = lado.querySelector(!w.ligado ? '[data-word-acao="ligar"]' : (w.instalacao || {}).instalado ? '[data-word-acao="abrir"]' : '[data-word-acao="instalar"]');
    if (alvo) alvo.click();
    return;
  }
  const p = CFN_PE[cfg.secao];
  const alvo = p && p[3] ? lado.querySelector(p[3]) : null;
  if (alvo) alvo.click();
}

function atualizarMetaDaConversa() {
  if (!cfgNoLado()) return;
  const n = pendentesDaConfig().length;
  const achada = CFG_SECOES.find((s) => s[0] === cfg.secao) || ["", "Configurações"];
  let fim = n ? plural(n, "mudança") + " por salvar" : "";
  if (!fim && cfg.secao === "lixeira") fim = plural(((cfg.lixo || {}).itens || []).length, "item", "itens");
  if (!fim && cfg.secao === "plano") fim = ((typeof atu !== "undefined" && atu.dados && atu.dados.anuncio && atu.dados.anuncio.nova) ? "versão nova disponível" : "na versão mais nova");
  if (!fim && cfg.secao === "desempenho") fim = cfn.teste && !cfn.teste.fim ? "testando " + (cfn.teste.i + 1) + " de " + cfn.teste.total : "medido a cada 2 segundos";
  if (!fim && cfg.secao === "backup") fim = (cfg.backup || {}).ultimo ? "ligado" : "desligado";
  if (!fim && cfg.secao === "aprendizado" && cfn.lembrete != null) fim = "1 lembrete novo";
  if (!fim && cfg.secao === "vinculos" && cfn.convite) fim = "1 convite pronto";
  if (!fim && cfg.secao === "conexoes") fim = ((cfg.cx || {}).sessao || {}).existe ? "WhatsApp Web conectado" : "WhatsApp Web não conectado";
  if (!fim && (cfg.secao === "word" || cfg.secao === "acesso") && cfn.d && cfn.d.extra && cfn.d.extra.passo) fim = "passo " + Math.min(3, cfn.d.extra.passo) + " de 3";
  $("conversa-meta").textContent = "Configurações › " + (cfg.secao === "desempenho" && cfn.teste ? "Modelos" : achada[1]) + (fim ? " · " + fim : "");
}

/* ---------------------------------------------------- salvar e descartar */

async function salvarConfigDoLado() {
  const pend = pendentesDaConfig();
  if (!pend.length) return;
  const lado = $("lado-ferramenta");
  const errado = camposInvalidos(lado);
  if (errado) { errado.focus(); avisoCert("confira o campo marcado antes de salvar"); return; }
  const botao = lado.querySelector("[data-cfn-salvar]");
  if (botao) botao.disabled = true;
  // O que nao e preferencia: o tema (desta maquina) e quem faz cada tarefa (rota propria).
  for (const m of pend) {
    if (!m.chave.startsWith("tarefas_modelo.")) continue;
    const t = m.chave.split(".")[1];
    const r = await fetch("/api/modelos/tarefa", { method: "POST", headers: CFG_JSON, body: JSON.stringify({ tarefa: t, modelo: m.valor }) });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); if (botao) botao.disabled = false; return; }
  }
  const temPrefs = pend.some((m) => m.chave !== "tema" && !m.chave.startsWith("tarefas_modelo."));
  if (temPrefs) {
    cfg.sujo = true;
    await _salvarConfig();
    if (cfg.sujo) { if (botao) botao.disabled = false; return; }
  }
  if (cfn.tema) { _escolherTema(cfn.tema); cfn.tema = null; }
  cfn.tarefas = {};
  cfn.novos = new Set();
  cfn.atencao = [];
  if (cfg.secao === "modelos") await carregarModelos();
  cfg.sujo = false;
  desenharConfigNoLado(false);
  await registrarNaConversa({ secao: cfg.secao, acao: "salvar", chaves: pend.map((m) => m.chave) });
}

function descartarNoLado() {
  cfg.rascunho = rascunhoDe(cfg.prefs.preferencias, cfg.prefs.modelo_atual);
  cfg.sujo = false;
  cfn.tema = null;
  cfn.tarefas = {};
  cfn.novos = new Set();
  cfn.atencao = [];
  if (cfg.secao === "aprendizado") cfn.lembrete = null;
  desenharConfigNoLado(false);
  notaDeFeitoNaConversa("Descartei as mudanças: " + (CFG_SECOES.find((s) => s[0] === cfg.secao) || ["", "a seção"])[1] + " ficou como estava.");
}

async function registrarNaConversa(campos) {
  if (!estado.trabalhoId) return;
  const r = await fetch("/api/trabalhos/" + estado.trabalhoId + "/fazer", {
    method: "POST", headers: CFG_JSON, body: JSON.stringify({ tipo: "config", campos: campos }),
  }).catch(() => null);
  const feito = r && r.ok ? await r.json() : null;
  notaDeFeitoNaConversa(feito && feito.resumo ? feito.resumo + "." : "Salvei.");
}

/* Fechar a coluna (x): com mudanca por salvar, pergunta antes. */
async function fecharColunaDaConfig() {
  const pend = pendentesDaConfig().length + (cfn.lembrete ? 1 : 0);
  if (pend && !(await confirmar({ titulo: "Fechar sem salvar?", contexto: "Configurações", texto: "As mudanças marcadas ao lado ficam de fora. Nada foi gravado.", confirmar: "Fechar sem salvar" }))) return;
  voltarAoContexto();
}

function fecharConfigDoLado() {
  pararMedicao();
  if (cfn.teste && !cfn.teste.fim) cfn.teste.parar = true;
  cfg.host = "tela";
  cfg.sujo = false;
  cfg.rascunho = cfg.prefs ? rascunhoDe(cfg.prefs.preferencias, cfg.prefs.modelo_atual) : cfg.rascunho;
  cfn.tema = null;
  cfn.tarefas = {};
  cfn.lembrete = null;
  if (typeof bkp !== "undefined") clearInterval(bkp.relogio);
  if (typeof carregarStatus === "function") carregarStatus();
}

/* "Abrir em Configuracoes": a tela inteira, com o que estava marcado. */
function abrirNaTelaDeConfiguracoes() {
  const rascunho = cfg.rascunho;
  const sujo = pendentesDaConfig().length > 0;
  const tema = cfn.tema;
  const secao = cfg.secao;
  largarFerramentaDoLado();
  cfg.host = "tela";
  if (tema) _escolherTema(tema);
  cfg.rascunho = rascunho;
  cfg.sujo = sujo;
  marcarDestino("config");
  _mostrarConfigNaTela(secao);
}

/* --------------------------------------------------- cada secao, na coluna */

/* Quem faz cada tarefa: na coluna, escolher marca e espera o Salvar. */
function ligarTarefasNoLado(lado) {
  lado.querySelectorAll("[data-mod-tarefa]").forEach((s) => {
    const t = s.dataset.modTarefa;
    if (cfn.tarefas[t] !== undefined) {
      s.value = cfn.tarefas[t];
      const botao = s.nextElementSibling;
      const rotulo = botao && botao.querySelector(".escolha-rotulo");
      const opcao = s.options[s.selectedIndex];
      if (rotulo && opcao) rotulo.textContent = opcao.text;
    }
    s.onchange = () => {
      cfn.tarefas[t] = s.value;
      cfn.novos.add("tarefas_modelo." + t);
      cfg.sujo = true;
      desenharConfigNoLado(false);
    };
  });
}

function ligarBuscaDaLixeira(lado) {
  const campo = lado.querySelector("[data-cfn-busca]");
  if (!campo) return;
  campo.oninput = () => {
    cfn.busca = campo.value;
    const pos = campo.selectionStart;
    desenharConfigNoLado(false);
    const novo = $("lado-ferramenta").querySelector("[data-cfn-busca]");
    if (novo) { novo.focus(); novo.setSelectionRange(pos, pos); }
  };
}

/* A lixeira filtrada pelo que a frase procurou: "4 de 640". */
function filtrarLixeiraNoLado(itens) {
  const termos = String(cfn.busca || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").split(/\s+/).filter((p) => p.length > 1);
  if (!termos.length) return itens;
  return itens.filter((e) => {
    const alvo = (e.titulo + " " + (e.tipo_rotulo || "") + " " + (e.detalhe || "")).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
    return termos.every((t) => alvo.includes(t));
  });
}

function campoDeBuscaDaLixeira(mostrados, total) {
  return '<label class="cfn-busca">' + ic("search", 16) + '<input type="search" data-cfn-busca="1" value="' + esc(cfn.busca || "") + '" placeholder="Procurar na lixeira" aria-label="Procurar na lixeira">' +
    "<small>" + mostrados + " de " + total + "</small></label>";
}

async function restaurarPelaConversa(id, botao) {
  if (botao) botao.disabled = true;
  const d = await restaurarDaLixeira(id, null);
  if (!d) { if (botao) botao.disabled = false; return; }
  if (botao) botao.innerHTML = ic("check", 16) + "Restaurado";
  cfg.lixo = await fetch("/api/lixeira").then((r) => r.json()).catch(() => cfg.lixo);
  if (cfgNoLado() && cfg.secao === "lixeira") desenharConfigNoLado(false);
  await registrarNaConversa({ secao: "lixeira", acao: "restaurar", titulos: [d.titulo] });
}

/* O lembrete novo, no alto do cartao Lembretes, com o texto da conversa. */
function blocoDoLembreteNovo() {
  if (cfg.host !== "lado" || cfn.lembrete == null) return "";
  const n = cfn.lembrete.length;
  return '<div class="cfn-lembrete"><label for="cfn-lembrete">Novo lembrete</label><textarea id="cfn-lembrete" rows="4" maxlength="600">' + esc(cfn.lembrete) + "</textarea>" +
    '<span class="cfn-lembrete-pe"><small data-cfn-conta="1">' + n + " caracteres · entra em toda pergunta da conversa</small>" +
    (cfn.novos.has("lembrete") ? '<span class="cfn-novo">novo</span>' : "") + "</span></div>";
}

function ligarLembreteNoLado(lado) {
  const t = lado.querySelector("#cfn-lembrete");
  if (!t) return;
  t.oninput = () => {
    cfn.lembrete = t.value;
    const conta = lado.querySelector("[data-cfn-conta]");
    if (conta) conta.textContent = t.value.length + " caracteres · entra em toda pergunta da conversa";
    const p = cfn.caixa && cfn.caixa.querySelector("[data-cfc-lembrete]");
    if (p) p.textContent = t.value;
  };
}

async function guardarLembreteDoLado(botao) {
  const texto = (cfn.lembrete || "").trim();
  if (!texto) { avisoCert("escreva o lembrete antes de guardar"); return; }
  botao.disabled = true;
  const ctx = cfg.ctx || {};
  const gavetas = ctx.gavetas && ctx.gavetas.length ? ctx.gavetas : ["Regras de redação", "Modelos", "Clientes", "Correções"];
  const gaveta = /\bclientes?\b/i.test(texto) && gavetas.includes("Clientes") ? "Clientes" : gavetas[0];
  const titulo = (texto.split(", ").pop() || texto).replace(/\.$/, "");
  const r = await fetch("/api/contextos", { method: "POST", headers: CFG_JSON, body: JSON.stringify({ id: null, titulo: (titulo[0] || "").toUpperCase() + titulo.slice(1, 80), texto: texto, gaveta: gaveta }) });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); botao.disabled = false; return; }
  cfg.ctx = await r.json();
  cfn.lembrete = null;
  cfn.novos.delete("lembrete");
  desenharConfigNoLado(false);
  await registrarNaConversa({ secao: "aprendizado", acao: "lembrete" });
}

/* Backup: a pasta sugerida (o Drive para computador) e a senha, aqui mesmo. */
function blocoDoBackupNoLado() {
  if (cfg.host !== "lado" || !cfn.d || cfn.d.secao !== "backup" || (cfg.backup || {}).ultimo) return "";
  const b = cfg.backup || {};
  const pasta = b.pasta || cfn.backupPasta || "";
  return '<div class="cfn-backup"><div class="ag-campo' + (cfn.novos.has("backup.pasta") && !b.pasta ? " cfn-com-selo" : "") + '"><label>Pasta</label>' +
    '<input type="text" data-cfn-bkp="pasta" value="' + esc(pasta) + '" placeholder="escolha uma pasta deste computador">' +
    (cfn.novos.has("backup.pasta") && !b.pasta ? '<span class="cfn-novo">novo</span>' : "") + "</div>" +
    (b.tem_senha ? "" : '<div class="ag-duas"><div class="ag-campo"><label>Senha</label><input type="password" data-cfn-bkp="senha" placeholder="mínimo ' + (b.senha_minima || 12) + ' caracteres" autocomplete="new-password"></div>' +
      '<div class="ag-campo"><label>Repita a senha</label><input type="password" data-cfn-bkp="repetir" autocomplete="new-password"></div></div>') + "</div>";
}

function ligarBackupNoLado(lado) {
  const pasta = lado.querySelector('[data-cfn-bkp="pasta"]');
  if (pasta) pasta.oninput = () => { cfn.backupPasta = pasta.value; };
}

async function salvarBackupDoLado(botao) {
  const lado = $("lado-ferramenta");
  const b = cfg.backup || {};
  const pasta = ((lado.querySelector('[data-cfn-bkp="pasta"]') || {}).value || b.pasta || "").trim();
  const senha = (lado.querySelector('[data-cfn-bkp="senha"]') || {}).value || "";
  const repetir = (lado.querySelector('[data-cfn-bkp="repetir"]') || {}).value || "";
  if (!pasta) { avisoCert("escolha a pasta do backup", { tom: "erro" }); return; }
  if (!b.tem_senha) {
    if (senha.length < (b.senha_minima || 12)) { avisoCert("a senha precisa de pelo menos " + (b.senha_minima || 12) + " caracteres", { tom: "erro" }); return; }
    if (senha !== repetir) { avisoCert("as duas senhas não são iguais", { tom: "erro" }); return; }
  }
  botao.disabled = true;
  const post = async (url, corpo) => {
    const r = await fetch(url, { method: "POST", headers: CFG_JSON, body: JSON.stringify(corpo || {}) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || "não deu certo");
    return d;
  };
  try {
    if (pasta !== b.pasta) cfg.backup = await post("/api/backup/configurar", { pasta: pasta });
    if (!b.tem_senha) cfg.backup = await post("/api/backup/configurar", { senha: senha });
    cfg.backup = await post("/api/backup/agora");
  } catch (err) {
    avisoCert(err.message, { tom: "erro" });
    botao.disabled = false;
    return;
  }
  cfn.backupPasta = "";
  cfn.novos.delete("backup.pasta");
  desenharConfigNoLado(false);
  if (typeof ligarBackupCfg === "function") ligarBackupCfg();
  await registrarNaConversa({ secao: "backup", acao: "backup" });
}

/* Escritorio: a pessoa do convite na lista da equipe, marcada "novo". */
function linhaDoConviteNoLado() {
  if (cfg.host !== "lado" || !cfn.convite || !cfn.convite.nome) return "";
  const c = cfn.convite;
  const ja = typeof eqp !== "undefined" && (eqp.equipe || []).some((f) => (f.email || "").toLowerCase() === (c.email || "").toLowerCase() && c.email);
  if (ja) return "";
  return '<div class="cfg-servico cfn-convite"><span class="cad-avatar">' + esc(iniciaisDoRemetente(c.nome)) + "</span>" +
    '<span class="duas-linhas"><b>' + esc(c.nome) + "</b><small>" + esc([c.email || "falta o e-mail Google", "colaborador"].join(" · ")) + "</small></span>" +
    '<span class="cfn-novo">novo</span></div>';
}

/* Conexoes: a conversa do WhatsApp com o texto pronto. Enviar e com voce. */
async function abrirWhatsappDaConversa(botao) {
  const x = (cfn.d && cfn.d.extra) || {};
  const c = x.contato || {};
  botao.disabled = true;
  try {
    let endereco = "";
    if (c.telefone) {
      const r = await fetch("/api/conexoes/mensagem", { method: "POST", headers: CFG_JSON, body: JSON.stringify({ telefone: c.telefone, texto: x.mensagem || "", nome: c.nome || "" }) });
      if (!r.ok) throw new Error(await erroDe(r));
      endereco = (await r.json()).endereco || "";
    }
    const a = await fetch("/api/conexoes/abrir", { method: "POST", headers: CFG_JSON, body: JSON.stringify(endereco ? { endereco: endereco } : {}) }).then((r) => r.json());
    avisoCert(a.abriu ? "abri o WhatsApp Web com a mensagem escrita — confira e aperte enviar" : (a.motivo || "não consegui abrir a janela do WhatsApp"), { tom: a.abriu ? "ok" : "" });
  } catch (err) {
    avisoCert(err.message, { tom: "erro" });
  }
  botao.disabled = false;
}

/* ------------------------------------------------- o teste dos modelos */

function htmlDoTeste(d) {
  const lista = ((d && d.extra) || cfn.extra || {}).teste || [];
  const t = cfn.teste || { feitos: {}, i: 0, total: lista.length };
  const num = (x) => (x === undefined || x === null ? "–" : String(x).replace(".", ","));
  const linhas = lista.map((m, i) => {
    const f = t.feitos[m.nome];
    const atual = !f && t.atual === m.nome;
    const q = m.qualidade;
    const icone = f && !f.erro ? '<span class="cfc-ic ok">' + ic("check_circle", 16) + "</span>" : '<span class="cfc-ic' + (atual ? "" : " apagado") + '">' + ic("schedule", 16) + "</span>";
    return '<div class="cfc-teste-linha' + (!f && !atual ? " depois" : "") + '">' + icone + "<b>" + esc(m.nome) + "</b>" +
      '<span class="mono">' + (f && !f.erro ? num(f.tokens_por_segundo) : "–") + '</span><span class="mono">' + (f && !f.erro ? Math.round(f.total_s) + " s" : "–") + "</span>" +
      '<span class="mono">' + (q ? q.certas + "/" + q.total : "–") + "</span></div>";
  }).join("");
  const feitos = Object.keys(t.feitos).length;
  const pct = lista.length ? Math.round((feitos / lista.length) * 100) : 0;
  let faltam = "";
  if (t.inicio && feitos && feitos < lista.length) {
    const porModelo = (Date.now() - t.inicio) / feitos;
    faltam = "faltam ~" + Math.max(1, Math.round((porModelo * (lista.length - feitos)) / 60000)) + " min";
  }
  const pe = t.fim ? (t.parar ? "parado em " + feitos + " de " + lista.length : "medido " + feitos + " de " + lista.length)
    : (t.atual ? (feitos + 1) + " de " + lista.length + " · medindo " + t.atual + (estado.ocupado ? " · pausado enquanto a conversa responde" : "") : "começando…");
  return '<div class="cfc-teste-linha cabeca"><span></span><span>Modelo</span><span>Palavras/s</span><span>1ª resp.</span><span>Acertos</span></div>' + linhas +
    '<div class="cfc-teste-pe"><small>' + esc(pe) + '</small><small class="mono">' + esc(faltam) + "</small></div>" +
    '<div class="progresso cfc-teste-barra"><i style="width:' + pct + '%"></i></div>';
}

function redesenharTeste() {
  const alvo = cfn.caixa && cfn.caixa.querySelector("[data-cfc-teste]");
  if (alvo) alvo.innerHTML = htmlDoTeste(cfn.d);
  if (cfgNoLado() && cfg.secao === "desempenho") {
    const lado = $("lado-ferramenta");
    const titulo = lado.querySelector(".cfn-titulo");
    if (titulo) titulo.innerHTML = "<b>" + esc(tituloDaColuna()) + "</b><small>Configurações" + (subDaColuna() ? " · " + esc(subDaColuna()) : "") + "</small>";
    atualizarPeDaConfig();
  }
}

async function rodarTesteDosModelos() {
  const lista = (cfn.extra || {}).teste || [];
  if (!lista.length || (cfn.teste && !cfn.teste.fim)) return;
  cfn.teste = { feitos: {}, i: 0, total: lista.length, inicio: Date.now(), parar: false, fim: false, atual: "" };
  redesenharTeste();
  const medidos = [];
  for (let i = 0; i < lista.length; i++) {
    if (cfn.teste.parar) break;
    // A conversa respondendo tem a vez: o teste espera.
    while (estado.ocupado && !cfn.teste.parar) { redesenharTeste(); await new Promise((ok) => setTimeout(ok, 1000)); }
    if (cfn.teste.parar) break;
    cfn.teste.i = i;
    cfn.teste.atual = lista[i].nome;
    redesenharTeste();
    const r = await fetch("/api/modelos/medir", { method: "POST", headers: CFG_JSON, body: JSON.stringify({ nome: lista[i].nome }) }).catch(() => null);
    const d = r && r.ok ? await r.json() : null;
    cfn.teste.feitos[lista[i].nome] = d ? d.medida : { erro: true };
    if (d) medidos.push(lista[i].nome);
    redesenharTeste();
  }
  cfn.teste.fim = true;
  cfn.teste.atual = "";
  redesenharTeste();
  if (typeof carregarModelos === "function") await carregarModelos();
  await registrarNaConversa({ secao: "desempenho", acao: "teste", titulos: medidos });
}
