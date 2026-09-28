/* ------------------------------------------------------------- inicio */

atualizarSelo(false);
atualizarSaudacao();
carregarMenu().then(contarPendencias);
carregarTrabalhos();
carregarStatus().then(atualizarPostura);
carregarAbertos();
carregarModelo();
carregarUsuario();
verificarPrimeiraAbertura();
aplicarModoLimitado();
$("nova").click();
// A versao nova: o anuncio ja guardado aparece logo; o da verificacao do dia
// (que o servidor faz 30 s depois de abrir) aparece em seguida.
setTimeout(() => avisarAtualizacao(), 4000);
setTimeout(() => avisarAtualizacao(), 50000);
// Aberto pelo "Perguntar ao PAULUS" do Explorer: o arquivo vem no endereco.
if (location.hash.startsWith("#perguntar=")) {
  const caminho = decodeURIComponent(location.hash.slice("#perguntar=".length));
  history.replaceState(null, "", location.pathname);
  perguntarSobreArquivo(caminho);
}
