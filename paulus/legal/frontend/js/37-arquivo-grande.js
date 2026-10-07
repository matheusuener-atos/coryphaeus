/* ------------------------------------------------------ arquivo grande */
/*
   Acima de 50 MB o arquivo não é recusado: pede confirmação (src/entrada.py).
   A pergunta diz nome e tamanho, e o botão só libera com "Conheço este
   arquivo e quero incluí-lo" marcado. Confirmado, o pedido vai de novo com o
   arquivo em `autorizados` - vale para aquele arquivo, naquela vez.

   A tela não promete o que não faz: o Paulus confere que o conteúdo é mesmo
   do tipo do nome (PDF é PDF, DOCX é do Word), e não procura vírus.
*/

const LIMITE_SEM_PERGUNTAR_MB = 50;

function mbBR(mb) {
  return String(mb).replace(".", ",") + " MB";
}

/* A pergunta. `lista` = [{ nome, mb }]. Devolve true só com a caixa marcada e o sim. */
async function confirmarArquivosGrandes(lista) {
  if (!lista.length) return true;
  const um = lista.length === 1;
  const titulo = um ? "“" + lista[0].nome + "” tem " + mbBR(lista[0].mb) : plural(lista.length, "arquivo") + " acima de " + LIMITE_SEM_PERGUNTAR_MB + " MB";
  const itens = um ? "" : '<ul class="grande-lista">' + lista.map((x) => "<li><span class=\"corta\">" + esc(x.nome) + "</span><small>" + mbBR(x.mb) + "</small></li>").join("") + "</ul>";
  const pedido = dialogo({
    titulo: titulo, contexto: "Arquivo grande",
    texto: "Até " + LIMITE_SEM_PERGUNTAR_MB + " MB o arquivo entra direto; acima disso, só com o seu sim. " +
      "Arquivo grande demora mais para ler, e um PDF escaneado de muitas páginas mais ainda.\n" +
      "O Paulus confere se o conteúdo é mesmo do tipo do nome (um PDF é PDF, um DOCX é do Word) — mas não procura vírus. Inclua só o que você sabe de onde veio.",
    html: itens,
    marcar: { rotulo: um ? "Conheço este arquivo e quero incluí-lo" : "Conheço estes arquivos e quero incluí-los", marcada: false },
    confirmar: "Incluir mesmo assim",
  });
  const caixa = document.getElementById("dialogo-marcar");
  const botao = document.querySelector('[data-dialogo="confirmar"]');
  if (caixa && botao) {
    botao.disabled = true;
    caixa.onchange = () => { botao.disabled = !caixa.checked; };
  }
  const r = await pedido;
  return Boolean(r && r.ok && r.marcada);
}

/*
   Para as rotas que recebem o CAMINHO do arquivo: manda, e se voltar algo em
   `pedem_confirmacao`, pergunta e manda de novo só esses, autorizados.
   `enviar(caminhos, autorizados)` devolve a resposta já em JSON; `lista` é
   o campo dos que entraram ("salvos" ou "ligados").
*/
async function enviarComConfirmacao(caminhos, enviar, lista) {
  const primeira = await enviar(caminhos, []);
  const pedem = primeira.pedem_confirmacao || [];
  if (!pedem.length) return primeira;
  if (!(await confirmarArquivosGrandes(pedem))) {
    primeira.recusados = (primeira.recusados || []).concat(pedem.map((x) => ({ nome: x.nome, motivo: x.motivo + " — não confirmado" })));
    return primeira;
  }
  const liberados = pedem.map((x) => x.caminho);
  const segunda = await enviar(liberados, liberados);
  return Object.assign({}, segunda, {
    [lista]: (primeira[lista] || []).concat(segunda[lista] || []),
    recusados: (primeira.recusados || []).concat(segunda.recusados || []),
  });
}

/*
   Para o que sobe pelo navegador (/api/upload): o tamanho já é conhecido
   antes de enviar, então a pergunta vem ANTES - 300 MB não atravessam duas
   vezes. Devolve { lista, autorizados, fora } para montar o envio.
*/
async function prepararEnvio(arquivos) {
  const limite = LIMITE_SEM_PERGUNTAR_MB * 1024 * 1024;
  const grandes = arquivos.filter((a) => a.size > limite);
  if (!grandes.length) return { lista: arquivos, autorizados: [], fora: [] };
  const sim = await confirmarArquivosGrandes(grandes.map((a) => ({ nome: a.name, mb: Math.round(a.size / 104857.6) / 10 })));
  if (sim) return { lista: arquivos, autorizados: grandes.map((a) => a.name), fora: [] };
  return {
    lista: arquivos.filter((a) => a.size <= limite), autorizados: [],
    fora: grandes.map((a) => ({ nome: a.name, motivo: "acima de " + LIMITE_SEM_PERGUNTAR_MB + " MB — não confirmado" })),
  };
}
