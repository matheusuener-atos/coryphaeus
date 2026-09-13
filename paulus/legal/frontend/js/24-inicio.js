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
