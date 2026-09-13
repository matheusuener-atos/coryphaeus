/* ---------------------------------------------------------- destinos */
/*
   O menu do manual do sistema: 20 destinos em quatro grupos. Cinco tem motor;
   os outros abrem uma tela que diz o que vao resolver e o que falta para
   existirem. Esconder os quinze apagaria o mapa do produto; desenha-los com
   numero inventado seria pior.
*/

/*
   O trilho e o menu sao os do desenho (docs/ui/01-shell.md): onze destinos
   fixos mais Servicos, Gravacoes e Apoiar, que ainda nao tem motor. O
   registro do servidor (/api/destinos) continua sendo quem diz o que esta
   pronto; os destinos antigos que o desenho fundiu em visoes de outros ficam
   alcancaveis por uma lista no fim do menu, ate cada tela ser refeita.
*/

const NOVOS_DESTINOS = {
  servicos: {
    id: "servicos", nome: "Serviços", pronta: true, abre: "servicos",
    resolve: "Pastas de trabalho por cliente, com equipe, prazos, arquivos e a trilha do que aconteceu.",
    precisa: ["o Assistente abrindo um serviço a partir de um pedido (“abra um serviço para…”)"],
  },
  gravacoes: {
    id: "gravacoes", nome: "Gravações", pronta: true, abre: "gravacoes",
    resolve: "Gravar reuniões e atendimentos, transcrever por falante e resumir, tudo nesta máquina.",
    precisa: ["transcrição local de áudio por falante", "resumo e contexto ao vivo a partir dela"],
  },
  apoiar: {
    id: "apoiar", nome: "Apoiar o projeto", pronta: false, abre: "apoiar",
    resolve: "Contribuir com o software livre que faz o PAULUS existir.",
    precisa: ["pagamento por Pix ou cartão", "a lista de apoiadores"],
  },
};

/* Quem, no trilho, acende quando um destino antigo abre. */
const PAI_NO_TRILHO = {
  agendamento: "calendario", tarefas: "calendario", organizar: "biblioteca", planilha: "editor",
  certificado: "assinar", relatorios: "financeiro", habilidades: "config", conexoes: "config",
  desempenho: "config",
};

const ICONE_ANTIGO = {
  agendamento: "schedule", tarefas: "task_alt", organizar: "drive_file_move", planilha: "table",
  certificado: "workspace_premium", relatorios: "bar_chart", habilidades: "auto_awesome",
  conexoes: "hub", desempenho: "speed",
};

/* Destinos antigos que ja viraram visao de uma tela nova. */
const ABSORVIDOS = new Set(["organizar", "agendamento", "tarefas", "planilha", "certificado", "relatorios", "habilidades", "conexoes", "desempenho"]);

let DESTINOS = [];

async function carregarMenu() {
  let d;
  try {
    d = await (await fetch("/api/destinos")).json();
  } catch (err) {
    d = { grupos: [] };
  }
  DESTINOS = d.grupos.flatMap((g) => g.destinos);

  const noTrilho = new Set(Array.from(document.querySelectorAll(".trilho [data-destino]")).map((b) => b.dataset.destino));
  const antigos = DESTINOS.filter((x) => !noTrilho.has(x.id) && !ABSORVIDOS.has(x.id));
  $("menu-antigos").innerHTML = antigos.map((x) =>
    '<button class="menu-item' + (x.pronta ? "" : " adiante") + '" data-destino="' + esc(x.id) +
    '" title="' + esc(x.resolve) + '"><span class="caixa-ic">' + ic(ICONE_ANTIGO[x.id] || "grid_view") + "</span>" +
    '<span class="rotulo-botao">' + esc(x.nome) + "</span></button>").join("");
  $("ver-antigos").hidden = !antigos.length;

  const semMotor = DESTINOS.filter((x) => !x.pronta).map((x) => x.id);
  semMotor.forEach((id) => {
    document.querySelectorAll('[data-destino="' + id + '"]').forEach((b) => b.classList.add("adiante"));
  });

  document.querySelectorAll("[data-destino]").forEach((b) => {
    b.onclick = () => { fecharFlutuante(); abrirDestino(b.dataset.destino); };
  });
  document.querySelectorAll("[data-nova]").forEach((b) => { b.onclick = () => $("nova").click(); });
}

function marcarDestino(id) {
  const acende = PAI_NO_TRILHO[id] || id;
  document.querySelectorAll("[data-destino]").forEach((b) => {
    b.classList.toggle("ativo", b.dataset.destino === acende || b.dataset.destino === id);
  });
}

function abrirDestino(id) {
  const d = DESTINOS.find((x) => x.id === id) || NOVOS_DESTINOS[id];
  if (!d) return;
  if (vinculoPendente() && DESTINOS_PRESOS.has(id)) {
    avisoCert(d.nome + " depende do escritório — fica liberado quando o responsável validar o seu vínculo");
    return;
  }
  marcarDestino(id);

  if (d.abre === "servicos") return mostrarServicos("pastas");
  if (d.abre === "gravacoes") return mostrarGravacoes("lista");
  if (d.abre === "apoiar") return mostrarApoiar("contribuir");
  if (!d.pronta) return telaAdiante(d);
  if (d.abre === "conversa") return $("nova").click();
  if (d.abre === "biblioteca") return mostrarBiblioteca();
  if (d.abre === "habilidades") return mostrarHabilidades();
  if (d.abre === "maquina") return mostrarMaquina();
  if (d.abre === "aprovacoes") return mostrarAprovacoes();
  if (d.abre === "config") return mostrarConfig("perfil");
  if (d.abre === "cadastros") return mostrarCadastros("clientes");
  if (d.abre === "tarefas") return mostrarTarefas();
  if (d.abre === "calendario") return mostrarCalendario();
  if (d.abre === "agendamento") return mostrarAgendamento();
  if (d.abre === "certificado") return mostrarCertificado();
  if (d.abre === "assinar") return mostrarAssinar();
  if (d.abre === "caixa") return mostrarEmail();
  if (d.abre === "editor") return mostrarEditor();
  if (d.abre === "planilha") return mostrarPlanilha();
  if (d.abre === "financeiro") return mostrarFinanceiro("geral");
  if (d.abre === "relatorios") return mostrarRelatorios();
  if (d.abre === "foco") return mostrarFoco();
  if (d.abre === "conexoes") return mostrarConexoes();
  if (d.abre === "organizar") return organizarComecar();
}

/* Vazio nunca e branco: o mesmo cabecalho, uma frase dizendo o que falta e
   uma acao que resolve. Aqui a acao que resolve e voltar ao que funciona. */
function telaAdiante(d) {
  abrirTela(d.nome);
  $("centro").innerHTML =
    '<div class="catalogo"><div class="adiante-tela">' +
    '<span class="rotulo">Ainda não construída</span>' +
    "<h2>" + esc(d.nome) + "</h2>" +
    "<p>" + esc(d.resolve) + "</p>" +
    (d.precisa.length
      ? '<div class="precisa"><span class="rotulo">O que falta para existir</span><ul>' +
        d.precisa.map((x) => "<li>" + esc(x) + "</li>").join("") + "</ul></div>"
      : "") +
    '<div class="linha-form"><button class="primario" data-volta="1">Voltar para a conversa</button></div>' +
    "</div></div>";
  $("centro").querySelector("[data-volta]").onclick = () => { $("nova").click(); marcarDestino("conversa"); };
  atualizarPostura();
}

