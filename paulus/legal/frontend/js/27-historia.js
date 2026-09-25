/* ------------------------------------------------ o caminho de volta */
/*
   A seta do titulo voltava sempre ao inicio: quem foi do Editor para Assinar
   e queria so retornar ao documento perdia o lugar. Agora cada tela aberta
   entra numa pilha, e a seta volta um passo - como o voltar de um navegador.

   Nao ha uma lista de telas mantida a mao: as funcoes que abrem tela sao
   embrulhadas aqui, depois de todos os arquivos carregados. Chamar a mesma
   tela de novo (trocar de aba, redesenhar) atualiza o topo em vez de empilhar,
   e uma tela que abre outra por dentro (mostrarEditor chama
   mostrarDocumentos) conta uma vez so.
*/

const historia = { pilha: [], dentro: false, voltando: false, limite: 40 };

/* Telas que sao a mesma: abrir por qualquer uma dessas portas e estar no
   mesmo lugar. */
const MESMA_TELA = {
  mostrarEditor: "documentos", mostrarPlanilha: "documentos", mostrarDocumentos: "documentos",
  abrirDocumento: "documentos", abrirPlanilha: "documentos", mostrarPrevia: "documentos", listaDocumentos: "documentos",
  mostrarAprovacoes: "aprovacoes", mostrarHistoricoDeAprovacoes: "aprovacoes", mostrarRegrasDeAlcada: "aprovacoes",
  mostrarBiblioteca: "acervo", mostrarPrazos: "prazos",
};

/* Conversa e lugar por si: duas conversas diferentes sao dois passos. */
const TELA_POR_ARGUMENTO = new Set(["abrirTrabalho", "mostrarDupla"]);

function chaveDaTela(nome, args) {
  if (TELA_POR_ARGUMENTO.has(nome)) return nome + ":" + String(args[0]);
  if (nome === "telaAdiante") return "adiante:" + (args[0] && args[0].id);
  return MESMA_TELA[nome] || nome;
}

function registrarNaHistoria(chave, abrir) {
  if (historia.voltando) return;
  const topo = historia.pilha[historia.pilha.length - 1];
  if (topo && topo.chave === chave) { topo.abrir = abrir; return; }
  historia.pilha.push({ chave: chave, abrir: abrir });
  if (historia.pilha.length > historia.limite) historia.pilha.shift();
}

async function voltarNaHistoria() {
  historia.pilha.pop();
  const anterior = historia.pilha[historia.pilha.length - 1];
  historia.voltando = true;
  try {
    if (anterior) await anterior.abrir();
    else { $("nova").click(); historia.pilha.push({ chave: "inicio", abrir: () => $("nova").click() }); }
  } catch (err) {
    $("nova").click();
  } finally {
    historia.voltando = false;
  }
}

function embrulharTela(nome) {
  const original = window[nome];
  if (typeof original !== "function" || original.embrulhada) return;
  const embrulhada = function (...args) {
    if (historia.dentro || historia.voltando) return original.apply(this, args);
    historia.dentro = true;
    try {
      registrarNaHistoria(chaveDaTela(nome, args), () => original.apply(this, args));
      return original.apply(this, args);
    } finally {
      historia.dentro = false;
    }
  };
  embrulhada.embrulhada = true;
  window[nome] = embrulhada;
}

(function ligarHistoria() {
  [
    /* abrirDestino fica de fora: ele so escolhe a tela, e quem entra na
       pilha e a tela que ele abre, com os argumentos dela. */
    "abrirTrabalho", "voltarAoAssistente", "telaAdiante",
    "mostrarAprovacoes", "mostrarHistoricoDeAprovacoes", "mostrarRegrasDeAlcada",
    "mostrarConfig", "mostrarCadastros", "mostrarAgenda", "mostrarApoiar", "mostrarServicos",
    "mostrarGravacoes", "mostrarBiblioteca", "mostrarPrazos", "mostrarDupla", "organizarComecar",
    "mostrarCertificado", "mostrarAssinar", "mostrarEmail", "mostrarDocumentos", "mostrarEditor",
    "mostrarPlanilha", "abrirDocumento", "abrirPlanilha", "mostrarPrevia", "listaDocumentos",
    "mostrarFinanceiro", "mostrarFoco", "mostrarHabilidades", "mostrarMaquina", "mostrarTarefas",
    "mostrarCalendario", "mostrarAgendamento", "mostrarRelatorios", "mostrarConexoes",
  ].forEach(embrulharTela);

  const nova = $("nova");
  const inicio = nova.onclick;
  nova.onclick = function (e) {
    registrarNaHistoria("inicio", () => inicio.call(nova, e));
    return inicio.call(this, e);
  };
  registrarNaHistoria("inicio", () => inicio.call(nova));

  $("voltar").onclick = voltarNaHistoria;
  $("voltar").title = "Voltar";
  /* O botao de voltar do mouse e Alt+seta, como em qualquer navegador. */
  window.addEventListener("mouseup", (e) => { if (e.button === 3) { e.preventDefault(); voltarNaHistoria(); } });
  window.addEventListener("keydown", (e) => {
    if (e.altKey && e.key === "ArrowLeft" && !e.ctrlKey && !e.shiftKey) { e.preventDefault(); voltarNaHistoria(); }
  });
})();
