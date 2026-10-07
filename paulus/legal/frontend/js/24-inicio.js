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
// Aberto pelo "Perguntar ao Paulus" do Explorer: o arquivo vem no endereco
// (ou ficou guardado enquanto a janela estava travada). Travada, ele espera:
// destravar recarrega a pagina, e ele entra entao.
(function () {
  let caminho = "";
  if (location.hash.startsWith("#perguntar=")) {
    caminho = decodeURIComponent(location.hash.slice("#perguntar=".length));
    history.replaceState(null, "", location.pathname);
  }
  try { caminho = caminho || sessionStorage.getItem("paulus.perguntar") || ""; } catch (err) { /* sem memoria */ }
  if (!caminho) return;
  acessoDeFora.pronto.then(async () => {
    const e = acessoDeFora.local && typeof lerVinculoGoogle === "function" ? await lerVinculoGoogle() : null;
    if (e && e.travado) {
      try { sessionStorage.setItem("paulus.perguntar", caminho); } catch (err) { /* sem memoria */ }
      return;
    }
    try { sessionStorage.removeItem("paulus.perguntar"); } catch (err) { /* sem memoria */ }
    perguntarSobreArquivo(caminho);
  });
})();
