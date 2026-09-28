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
// Aberto pelo "Perguntar ao PAULUS" do Explorer: o arquivo vem no endereco.
if (location.hash.startsWith("#perguntar=")) {
  const caminho = decodeURIComponent(location.hash.slice("#perguntar=".length));
  history.replaceState(null, "", location.pathname);
  perguntarSobreArquivo(caminho);
}
