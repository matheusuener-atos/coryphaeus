/* ------------------------------------------------------------- casca */
/*
   O menu abre ao passar o mouse no trilho e fecha ao sair dele - por cima do
   conteudo, sem empurrar nada. Esc fecha. Ctrl+K leva ao campo de pedido de
   qualquer tela; Ctrl+N abre uma conversa nova.
*/

function abrirFlutuante() { $("menu-flutuante").classList.add("aberto"); }
function fecharFlutuante() {
  $("menu-flutuante").classList.remove("aberto");
  fecharGavetas();
  fecharMenu();
}

$("trilho").addEventListener("mouseenter", abrirFlutuante);
/* Fecha quando o ponteiro esta fora do trilho e do menu. Nao e mouseleave
   porque o menu abre DEBAIXO do ponteiro sem receber mouseenter - um
   movimento rapido para o conteudo nunca geraria o mouseleave. */
document.addEventListener("mousemove", (e) => {
  if (!$("menu-flutuante").classList.contains("aberto")) return;
  if (e.target && e.target.closest && e.target.closest("#menu-flutuante, #trilho")) return;
  fecharFlutuante();
});

/* A gaveta ao lado do menu: as telas antigas que ainda nao tem lugar. */
function fecharGavetas() {
  $("gaveta-antigos").hidden = true;
}
function alternarGaveta(id) {
  const alvo = $(id);
  const abrir = alvo.hidden;
  fecharGavetas();
  alvo.hidden = !abrir;
}
$("ver-antigos").onclick = () => alternarGaveta("gaveta-antigos");

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") fecharFlutuante();
  if (!(e.ctrlKey || e.metaKey)) return;
  const tecla = e.key.toLowerCase();
  if (tecla === "k") {
    e.preventDefault();
    const busca = $("bib-termo");
    if (busca) { busca.focus(); busca.select(); return; }
    if ($("compositor").hidden) $("nova").click();
    $("pedido").focus();
  } else if (tecla === "n") {
    e.preventDefault();
    $("nova").click();
  } else if (tecla === "s" && $("cfg-tela")) {
    e.preventDefault();
    if (cfg.sujo) salvarConfig();
  } else if (tecla === "1" || tecla === "2" || tecla === "3") {
    e.preventDefault();
    abrirDestino({ 1: "conversa", 2: "calendario", 3: "biblioteca" }[tecla]);
  }
});

$("voltar").onclick = () => $("nova").click();

/* O painel da direita: guarda-se a escolha, como o desenho pede. */
function lateralPreferida() {
  try { return localStorage.getItem("paulus.lateral") !== "0"; } catch (err) { return true; }
}

function mostrarLateral(aberta) {
  $("lateral").hidden = !aberta;
  $("conversa-corpo").classList.toggle("com-lateral", aberta);
  $("alternar-lateral").hidden = !$("centro").classList.contains("prosa");
}

$("alternar-lateral").onclick = () => {
  const abrir = $("lateral").hidden;
  try { localStorage.setItem("paulus.lateral", abrir ? "1" : "0"); } catch (err) { /* sem memoria */ }
  mostrarLateral(abrir);
};

/* A tela passa da postura de inicio para a de conversa: a coluna do texto
   ganha a medida de prosa e o painel da direita entra. */
function entrarNaConversa() {
  $("centro").classList.add("prosa");
  $("conversa-col").classList.remove("tela-dupla", "tela-cheia");
  $("acoes-tela").innerHTML = "";
  $("nav-tela").innerHTML = "";
  $("exportar-conversa").hidden = false;
  mostrarLateral(lateralPreferida());
}

/* A conversa em texto, para levar para fora. E o que "Exportar" faz enquanto
   nao existe formato melhor. */
function exportarConversa() {
  const t = estado.trabalho;
  if (!t) return;
  const linhas = [t.titulo, ""];
  for (const m of t.mensagens) linhas.push((m.autor === "pessoa" ? "Você: " : "PAULUS: ") + m.texto, "");
  const blob = new Blob([linhas.join("\n")], { type: "text/plain;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = (t.titulo || "conversa").replace(/[\\/:*?"<>|]+/g, "-") + ".txt";
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
$("exportar-conversa").onclick = exportarConversa;

/* Quem usa, no avatar: a foto enviada em Configuracoes ou, sem foto, as
   iniciais do nome cadastrado la. */
async function carregarUsuario() {
  try {
    const d = await (await fetch("/api/preferencias")).json();
    const p = d.preferencias || d;
    const foto = (d.marca || {}).foto || {};
    const nome = String(p.nome || "").trim();
    const partes = nome ? nome.split(/\s+/) : [];
    // Sem nome cadastrado fica a sigla do produto, que e o que o HTML ja traz.
    const iniciais = nome
      ? (partes[0][0] + (partes.length > 1 ? partes[partes.length - 1][0] : "")).toUpperCase()
      : "PL";

    // A versao no endereco: sem ela, trocar a foto nao mudaria a tela, que
    // continuaria mostrando a imagem que ja tem em maos. E tirar a foto tem
    // de desfazer a imagem aqui, senao o circulo fica com um retrato quebrado.
    const desenho = foto.tem ? '<img src="/marca/foto.png?v=' + foto.versao + '" alt="">' : "";
    for (const id of ["avatar", "avatar-menu"]) {
      if (desenho) $(id).innerHTML = desenho;
      else $(id).textContent = iniciais;
    }

    if (!nome) return;
    $("avatar").title = nome;
    $("usuario-nome").textContent = nome;
    if (p.oab) $("usuario-papel").textContent = "OAB " + p.oab;
  } catch (err) { /* sem preferencias, fica a sigla do produto */ }
}

