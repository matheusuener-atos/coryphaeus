/* ------------------------------------------- certificado digital (A7) */
/*
   O certificado e a chave privada de alguem. Duas regras aparecem em tudo
   que segue: a senha nunca volta do servidor para a tela, e a tela nunca
   chama de "assinatura com validade juridica" o que saiu de um certificado
   fora da ICP-Brasil.
*/

const cert = { dados: null, aba: "escrever", tracos: [], desenhando: false, visao: "assinar", largo: false, guardar: false };

/* A tela de Assinatura do desenho (docs/ui/03-telas-desktop.md, A8): duas
   visoes, Assinar documento e Certificado digital, no mesmo cabecalho, com
   o painel de 400 px. O que era a tela do certificado virou a segunda visao. */
async function mostrarCertificado() {
  abrirTela("Assinatura", { cheia: true });
  marcarDestino("assinar");
  cert.visao = "certificado";
  const centro = $("centro");
  centro.innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">abrindo o certificado…</p></div></div>';
  try {
    cert.dados = await (await fetch("/api/certificado")).json();
  } catch (err) {
    centro.innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">não consegui abrir: ' + esc(String(err)) + "</p></div></div>";
    return;
  }
  cert.guardar = Boolean(cert.dados.guardar_senha);
  desenharAssinatura();
  atualizarPostura();
}

function desenharCertificado() { desenharAssinatura(); }

function desenharAssinatura() {
  cabecalhoAssinatura();
  let principal, painel;
  if (cert.visao === "certificado") { principal = cartaoDoCertificado(); painel = painelDoSelo(); }
  else if (assina.doc) { principal = visorParaAssinar(); painel = painelAntesDeAssinar(); }
  else { principal = listaDePdfs(); painel = painelSemDocumento(); }
  const classe = "acervo as-corpo" + (cert.largo ? " painel-largo" : "");
  $("centro").innerHTML = '<div class="' + classe + '" id="assinatura"><div class="acervo-principal as-principal">' + principal + "</div>" + painel + "</div>";
  ligarAssinatura();
}

function situacaoDoCertificado() {
  const d = cert.dados || {};
  const c = d.certificado;
  if (!d.instalado || !c) return { texto: "sem certificado", classe: "atencao" };
  if (c.erro) return { texto: "bloqueado · digite a senha", classe: "atencao" };
  if (c.vencido) return { texto: "vencido", classe: "atencao" };
  if (c.dias_restantes !== null && c.dias_restantes !== undefined && c.dias_restantes <= 30) return { texto: "vence em " + c.dias_restantes + " dias", classe: "atencao" };
  return { texto: c.icp_brasil ? "válido" : "válido · fora da ICP-Brasil", classe: "" };
}

function seloDeSituacao() {
  const s = situacaoDoCertificado();
  const classe = "docs-sinc" + (s.classe ? " " + s.classe : "");
  return '<span class="' + classe + '"><i></i>' + esc(s.texto) + "</span>";
}

function cabecalhoAssinatura() {
  const titulo = $("conversa-titulo");
  const meta = $("conversa-meta");
  if (cert.visao === "certificado") {
    titulo.textContent = "Certificado digital";
    meta.textContent = "O arquivo e a senha ficam nesta máquina · nunca são enviados";
  } else if (assina.doc) {
    const doc = assina.doc;
    const lote = assina.lote;
    titulo.textContent = doc.nome;
    meta.innerHTML = (lote ? "Documento " + (lote.atual + 1) + " de " + lote.itens.length + " do lote · " : "") + plural(doc.paginas, "página") + " · " + String(doc.mb).replace(".", ",") + " MB · " +
      (doc.ja_assinado ? plural(doc.assinaturas, "assinatura") + " já no arquivo" : "ainda sem assinatura") +
      ' · <button class="em-ligacao forte" data-as-acervo="1">do Acervo</button>';
  } else {
    titulo.textContent = "Assinar documento";
    meta.textContent = "escolha um PDF do Acervo ou do computador — ou vários, para assinar em lote";
  }
  const botao = (v, r) => {
    const classe = v === cert.visao ? "ativa" : "";
    return '<button class="' + classe + '" data-as-visao="' + v + '">' + r + "</button>";
  };
  let acoes;
  if (cert.visao === "certificado") {
    acoes = '<button class="primario com-icone" data-as-visao="assinar">' + ic("draw", 16) + "Assinar documento</button>";
  } else if (assina.doc && assina.lote) {
    const t = topoDoLote();
    acoes = '<button class="com-icone" id="assina-trocar">' + ic("close", 16) + "Sair do lote</button>" +
      '<button class="primario com-icone" id="assina-lote-topo"' + (t.desligado ? " disabled" : "") + ">" + ic("draw", 16) + esc(t.texto) + "</button>";
  } else if (assina.doc) {
    acoes = '<button class="com-icone" id="assina-trocar">' + ic("swap_horiz", 16) + "Trocar documento</button>" +
      '<button class="primario com-icone" id="assina-agora-topo">' + ic("draw", 16) + "Assinar agora</button>";
  } else {
    acoes = '<button class="primario com-icone" id="assina-escolher-topo">' + ic("folder_open", 16) + "Escolher PDFs</button>";
  }
  $("acoes-tela").innerHTML = '<div class="visoes">' + botao("assinar", "Assinar documento") + botao("certificado", "Certificado digital") + "</div>" + acoes;
  $("nav-tela").innerHTML = "";
}

/* ------------------------------------- os certificados que estao no Windows */
/* Um pop-up nosso, como o de anexar: os certificados instalados nesta conta
   do Windows, os de pessoa (ICP-Brasil) em cima e os tecnicos do sistema
   embaixo. Escolher um so PRE-SELECIONA: nada e exportado, a chave continua
   no Windows (mesmo a marcada como nao exportavel). A senha criada ali e do
   PAULUS, pedida na hora de assinar; o Windows ainda pede a dele se o
   certificado tiver protecao forte. No canto, a janela do proprio Windows. */
const cw = { lista: null, escolhido: "" };

async function abrirCertificadosDoWindows() {
  cw.lista = null;
  cw.escolhido = "";
  const escolha = dialogo({
    titulo: "Certificados instalados no Windows", contexto: "Assinatura › Certificado", classe: "dialogo-anexar", confirmar: "Usar este certificado",
    html: '<div class="anx cw">' +
      '<div class="anx-lista" id="cw-lista"><p class="anx-vazio">lendo os certificados do Windows…</p></div>' +
      '<div class="cw-senha" id="cw-senha" hidden><label for="cw-senha-campo">Crie uma senha do PAULUS para usar este certificado</label>' +
      '<input type="password" id="cw-senha-campo" autocomplete="new-password" placeholder="pelo menos 4 caracteres">' +
      "<small>Nada é copiado: a chave continua no Windows. Peço esta senha na hora de assinar — e, se o certificado foi instalado com proteção forte, o Windows pede também a senha dele.</small></div>" +
      '<p class="cw-erro" id="cw-erro" hidden></p>' +
      '<div class="anx-rodape"><span id="cw-conta"></span>' +
      '<button type="button" class="anx-windows" id="cw-windows">' + ic("open_in_new", 14) + "Abrir a janela do Windows</button></div></div>",
    aoConfirmar: usarCertificadoDoWindows,
  });
  $("cw-windows").onclick = async () => {
    const r = await fetch("/api/certificado/windows/abrir", { method: "POST" });
    if (!r.ok) avisoCert(await erroDe(r));
  };
  $("cw-senha-campo").oninput = conferirCertificadoDoWindows;
  conferirCertificadoDoWindows();
  try {
    cw.lista = (await (await fetch("/api/certificado/windows")).json()).certificados || [];
  } catch (err) {
    const lista = $("cw-lista");
    if (lista) lista.innerHTML = '<p class="anx-vazio">não consegui ler os certificados: ' + esc(String(err)) + "</p>";
    return;
  }
  desenharCertificadosDoWindows();
  const r = await escolha;
  if (r && r.ok && r.dados) {
    cert.dados = r.dados;
    desenharAssinatura();
    avisoCert(r.dados.aviso || "certificado pronto para assinar", { tom: "ok" });
  }
}

function desenharCertificadosDoWindows() {
  const lista = $("cw-lista");
  if (!lista) return;
  const linha = (w) => {
    const bloqueio = w.vencido ? "vencido" : (!w.tem_chave ? "sem chave para assinar" : "");
    const marcado = cw.escolhido === w.impressao;
    const classe = "anx-linha cw-linha" + (marcado ? " escolhida" : "") + (bloqueio ? " cw-off" : "") + (w.icp_brasil ? "" : " cw-sistema");
    return '<div class="' + classe + '" data-cw="' + esc(w.impressao) + '"' + (bloqueio ? ' title="Não dá para assinar: ' + bloqueio + '"' : "") + ">" +
      '<span class="cw-radio' + (marcado ? " on" : "") + '"></span>' + ic("workspace_premium", 18) +
      '<span class="duas-linhas"><b class="corta">' + esc(w.titular || "sem nome") + '</b><small class="corta">' + esc(w.emissor || "") +
      (w.valido_ate ? " · válido até " + esc(dataBR(w.valido_ate)) : "") + "</small></span>" +
      (bloqueio ? '<span class="em-pilula">' + bloqueio + "</span>" : (w.icp_brasil ? '<span class="em-pilula ok">ICP-Brasil</span>' : "")) + "</div>";
  };
  const pessoais = cw.lista.filter((w) => w.icp_brasil);
  const sistema = cw.lista.filter((w) => !w.icp_brasil);
  lista.innerHTML = (cw.lista.length
    ? (pessoais.length ? '<div class="nav-grupo">Seus certificados · ICP-Brasil</div>' + pessoais.map(linha).join("")
        : '<p class="anx-vazio">Nenhum certificado ICP-Brasil (e-CPF ou e-CNPJ) instalado nesta conta do Windows.</p>') +
      (sistema.length ? '<div class="nav-grupo">Outros certificados do Windows</div>' + sistema.map(linha).join("") : "")
    : '<p class="anx-vazio">Nenhum certificado instalado nesta conta do Windows.</p>');
  lista.querySelectorAll("[data-cw]").forEach((el) => {
    el.onclick = () => {
      if (el.classList.contains("cw-off")) return;
      cw.escolhido = el.dataset.cw;
      $("cw-erro").hidden = true;
      desenharCertificadosDoWindows();
      const senha = $("cw-senha-campo");
      if (senha) senha.focus();
    };
  });
  conferirCertificadoDoWindows();
}

function conferirCertificadoDoWindows() {
  const senha = $("cw-senha-campo");
  const botao = document.querySelector('#veu-dialogo [data-dialogo="confirmar"]');
  const escolhido = (cw.lista || []).find((w) => w.impressao === cw.escolhido);
  if ($("cw-senha")) $("cw-senha").hidden = !escolhido;
  if (botao) botao.disabled = !escolhido || !senha || senha.value.length < 4;
  const conta = $("cw-conta");
  if (conta) conta.textContent = escolhido ? "escolhido: " + escolhido.titular : "";
}

async function usarCertificadoDoWindows() {
  const senha = $("cw-senha-campo");
  if (!cw.escolhido || !senha || senha.value.length < 4) { if (senha) senha.focus(); return; }
  const botao = document.querySelector('#veu-dialogo [data-dialogo="confirmar"]');
  const erro = $("cw-erro");
  botao.disabled = true;
  botao.textContent = "Preparando…";
  const r = await fetch("/api/certificado/windows/usar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ impressao: cw.escolhido, senha: senha.value }),
  });
  botao.textContent = "Usar este certificado";
  if (!r.ok) {
    // O pop-up fica aberto, com o motivo (certificado sem chave, vencido,
    // que saiu do Windows), sem perder a escolha nem a senha digitada.
    erro.textContent = await erroDe(r);
    erro.hidden = false;
    conferirCertificadoDoWindows();
    return;
  }
  const d = await r.json();
  if (dialogoAberto) dialogoAberto.fechar({ ok: true, dados: d });
}

/* ----------------------------------------------- o certificado, o cartao */

function cartaoDoCertificado() {
  const d = cert.dados;
  const c = d.certificado;
  const classeGuardar = "ag-toggle" + (cert.guardar ? " on" : "");
  let html = '<div class="as-cartao"><div class="as-cartao-topo"><span class="cresce">' + (d.instalado ? "Certificado instalado" : "Certificado digital") + "</span>" +
    (d.instalado ? seloDeSituacao() : "") + "</div><div class=\"as-rolagem\">";

  html += '<div class="as-bloco"><b class="as-titulo">Upload do arquivo</b>' +
    '<div class="as-solta" id="cert-solta"><span>Arraste o arquivo do certificado aqui</span><small>.pfx ou .p12 · até 8 MB</small>' +
    '<span class="as-solta-acoes"><button class="primario com-icone" id="cert-escolher">' + ic("folder_open", 16) + "Escolher no computador</button>" +
    '<button class="com-icone" id="cert-ver-windows">' + ic("desktop_windows", 16) + "Usar um já instalado no Windows</button></span>" +
    '<input type="file" id="cert-arquivo" accept=".pfx,.p12" hidden></div>' +
    (d.instalado ? "" :
      '<div class="as-teste"><b>Sem um certificado à mão?</b><p>Posso criar um certificado de teste para você conhecer a tela. Ele assina de verdade do ponto de vista técnico e <b>não tem validade jurídica</b> — serve para experimentar, não para documento que vale.</p>' +
      '<button id="cert-teste">Criar certificado de teste</button></div>') + "</div>";

  if (d.instalado && c) {
    const doWindows = d.origem === "windows";
    html += '<div class="as-bloco"><div class="as-titular"><span class="as-titular-ic">' + ic("workspace_premium", 24) + "</span>" +
      '<span class="duas-linhas"><b class="as-nome">' + esc(c.titular || "Certificado instalado") + "</b><small>" +
      esc(c.tipo || "certificado A1") + (c.documento ? " · " + esc(c.documento) : "") + (doWindows ? " · instalado no Windows" : " · arquivo .pfx") + "</small></span>" +
      '<span class="as-titular-acoes"><button class="com-icone" id="cert-trocar">' + ic("upload", 16) + "Substituir</button>" +
      '<button class="ag-perigo-fino" id="cert-remover">Remover</button></span></div>' +
      (c.erro
        ? '<p class="as-explica">' + esc(String(c.erro).replace(/[.\s]*$/, ".")) + " Digite a senha abaixo para eu conseguir ler o titular, o emissor e a validade.</p>"
        : '<div class="as-grade4">' +
          cartaoDado("Emissor", c.emissor || "—") +
          cartaoDado("Válido até", dataBR(c.valido_ate) + (c.dias_restantes !== null && c.dias_restantes !== undefined && !c.vencido ? " · " + c.dias_restantes + " dias" : "")) +
          cartaoDado("Nº de série", c.serie || "—") +
          cartaoDado("Guardado em", d.guardado_em || "esta máquina") + "</div>") +
      (c.icp_brasil || c.erro ? "" :
        '<div class="cert-aviso"><strong>Este certificado não é da ICP-Brasil</strong><p>Ele assina, e a assinatura é íntegra: dá para provar que o arquivo não foi alterado depois. Mas ela <b>não tem a validade jurídica</b> de uma assinatura feita com e-CPF ou e-CNPJ emitido por autoridade credenciada. Não use em documento que vá para processo, cartório ou órgão público.</p></div>') +
      (c.vencido ? '<div class="cert-aviso"><strong>Certificado vencido</strong><p>Venceu em ' + esc(dataBR(c.valido_ate)) + ". Não dá para assinar com ele. Instale o certificado novo em Substituir.</p></div>" : "") +
      "</div>";

    const memoria = d.senha_na_memoria
      ? "A senha está na memória por mais " + d.minutos_restantes + " min."
      : (d.tem_senha_guardada ? "A senha está guardada nesta máquina." : "Se não guardar, eu pergunto a senha em cada assinatura.");
    html += '<div class="as-bloco"><b class="as-titulo">' + (doWindows ? "Senha do PAULUS para este certificado" : "Senha do certificado") + "</b>" +
      (doWindows ? '<p class="as-explica">A chave fica no Windows. Esta senha libera o uso aqui; se o certificado tiver proteção forte, o Windows pede a dele na hora de assinar.</p>' : "") +
      /* O olho fica dentro do campo, como em todo campo de senha: "mostrar"
         solto ao lado parecia um link de outra coisa. */
      '<div class="cert-senha"><label class="cert-senha-caixa">' + ic("key", 18) +
      '<input type="password" id="cert-senha" placeholder="' + (doWindows ? "senha do PAULUS" : "senha do certificado") + '" autocomplete="off">' +
      '<button type="button" class="cert-olho" id="cert-mostrar" title="Mostrar a senha" aria-label="Mostrar a senha">' + ic("visibility", 18) + "</button></label>" +
      '<button class="primario" id="cert-abrir">Abrir</button></div>' +
      (d.pode_guardar_senha
        ? '<div class="' + classeGuardar + '" id="cert-guardar"><span>Guardar a senha nesta máquina</span><i></i></div>'
        : '<p class="as-explica">Não consigo guardar a senha com segurança neste sistema: vou perguntar a cada assinatura.</p>') +
      '<small class="as-nota">' + esc(memoria) + (d.tem_senha_guardada ? ' <button class="em-ligacao" id="cert-esquecer">esquecer a senha guardada</button>' : "") + "</small></div>";
  }
  html += "</div>";

  if (d.instalado) {
    const toggles = [
      ["pedir_confirmacao", "Pedir confirmação antes de cada assinatura"],
      ["mostrar_documento", "Mostrar o documento inteiro na confirmação"],
      ["lote_sem_confirmar", "Assinar vários de uma vez sem confirmar cada um"],
    ].map(([chave, rotulo]) => {
      const classe = "ag-toggle" + (d[chave] ? " on" : "");
      return '<div class="' + classe + '" data-cofre="' + chave + '"><span>' + rotulo + "</span><i></i></div>";
    }).join("");
    html += '<div class="as-rodape-cartao"><b class="as-titulo">Ao assinar</b><div class="as-duas-colunas">' + toggles +
      '<div class="ag-chave"><span>Depois de digitar a senha, ela vale por</span><select id="cert-minutos">' +
      [0, 5, 15, 30, 60, 120].map((m) => '<option value="' + m + '"' + (d.minutos === m ? " selected" : "") + ">" + (m ? m + " minutos" : "só esta assinatura") + "</option>").join("") +
      "</select></div></div></div>";
  }
  return html + "</div>";
}

function cartaoDado(rotulo, valor) {
  return '<div class="as-dado"><small>' + esc(rotulo) + "</small><b>" + esc(valor) + "</b></div>";
}

/* O selo, no painel: a previa em tamanho real e o que entra nele. */
function painelDoSelo() {
  const d = cert.dados;
  const s = d.selo || {};
  const reg = (d.registro && d.registro.assinaturas) || [];
  const mes = new Date().toISOString().slice(0, 7);
  const esteMes = reg.filter((a) => String(a.quando || "").startsWith(mes)).length;
  const marca = (ligado, rotulo, chave) => {
    const classe = "as-marca" + (ligado ? " on" : "") + (chave ? " liga" : "");
    return '<div class="' + classe + '"' + (chave ? ' data-selo="' + chave + '"' : "") + '><span class="as-caixinha">' + ic("check", 12) + "</span><span>" + rotulo + "</span></div>";
  };
  return '<aside class="acervo-painel"><div class="rolagem as-painel">' +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>Selo de assinatura</h3><span class="meta">Prévia em tamanho real</span></span></div>' +
    '<div class="as-selo-caixa"><div class="as-selo-escala" id="selo-previa">' + previaSelo(d) + "</div></div>" +
    '<div class="as-painel-miolo"><div class="as-abas-selo" role="tablist">' +
    [["desenhar", "Desenhar", "draw"], ["escrever", "Escrever", "edit_note"], ["imagem", "Imagem", "upload"]].map(([v, r, icone]) => {
      const classe = "as-aba-selo" + (v === cert.aba ? " ativa" : "");
      return '<button class="' + classe + '" data-aba="' + v + '" role="tab">' + ic(icone, 18) + "<span>" + r + "</span></button>";
    }).join("") + '</div><div id="selo-painel"></div></div>' +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>O que entra no selo</span></div><div class="as-duas-colunas">' +
    marca(Boolean(s.desenho || s.imagem), s.desenho ? "Rubrica desenhada" : "Logo do escritório", "") +
    marca(true, "Nome do titular", "") +
    marca(s.mostrar_cpf !== false, "CPF ou CNPJ", "mostrar_cpf") +
    marca(s.mostrar_data !== false, "Data e hora", "mostrar_data") +
    marca(true, "Emissor do certificado", "") +
    marca(s.mostrar_codigo !== false, "Código de verificação", "mostrar_codigo") + "</div>" +
    '<div class="ag-chave"><span>Posição padrão na página</span><select id="selo-posicao">' +
    (d.posicoes || []).map((p) => '<option value="' + esc(p.valor) + '"' + (s.posicao === p.valor ? " selected" : "") + ">" + esc(p.rotulo) + "</option>").join("") +
    "</select></div></div>" +
    '<div class="painel-chaves">' +
    '<div class="chave-valor"><span>Assinaturas este mês</span><b>' + esteMes + "</b></div>" +
    '<div class="chave-valor"><span>Última</span><b>' + (reg[0] ? esc(quandoCurto(reg[0].quando)) + " · " + esc(reg[0].documento) : "nenhuma ainda") + "</b></div>" +
    '<div class="chave-valor"><span>Feitas nesta máquina</span><b>' + ((d.registro && d.registro.total) || reg.length) + "</b></div></div>" +
    '<div class="as-painel-rodape"><button class="docs-ligacao as-restaurar" id="selo-restaurar">' + ic("restart_alt", 16) + "Restaurar padrão</button>" +
    '<span class="cresce"></span><button class="com-icone" id="cert-ir-assinar">' + ic("draw", 16) + "Testar</button>" +
    '<button class="primario com-icone" id="selo-salvar">' + ic("check", 16) + "Salvar selo</button></div>" +
    "</div></aside>";
}

/* A previa monta as mesmas linhas que o servidor vai gravar no PDF. */
function previaSelo(d) {
  const s = d.selo || {};
  const c = d.certificado || {};
  const nome = c.titular || "SEU NOME";
  const doc = c.documento || "";
  const agora = new Date();
  const data = agora.toLocaleDateString("pt-BR");
  const hora = agora.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });

  let corpo = String(s.texto || "")
    .replace(/\{nome\}/g, nome)
    .replace(/\{cpf\}/g, s.mostrar_cpf === false ? "" : doc)
    .replace(/\{cnpj\}/g, s.mostrar_cpf === false ? "" : doc)
    .replace(/\{data\}/g, data)
    .replace(/\{hora\}/g, hora);

  const linhas = corpo.split("\n").filter((l) => l.trim());
  if (s.mostrar_cpf !== false && doc && corpo.indexOf(doc) < 0) linhas.push(doc);
  if (s.mostrar_data !== false) linhas.push(data + " " + hora + (c.emissor ? " · " + c.emissor : ""));
  if (s.mostrar_codigo !== false) linhas.push("confira no PAULUS · código 4A91C7");

  const img = s.desenho || s.imagem;
  return '<div class="selo-previa">' +
    (img ? '<img src="/api/certificado/selo/' + (s.desenho ? "desenho" : "imagem") + ".png?t=" + Date.now() + '" alt="">' : "") +
    '<div class="linhas">' + linhas.map((l) => "<div>" + esc(l) + "</div>").join("") + "</div></div>";
}

function painelSelo() {
  const s = (cert.dados.selo) || {};
  const alvo = $("selo-painel");
  if (!alvo) return;

  if (cert.aba === "escrever") {
    alvo.innerHTML =
      '<div class="ag-campo"><label>O que aparece no selo</label><textarea id="selo-texto">' + esc(s.texto || "") + "</textarea></div>" +
      '<p class="as-explica">Use <b>{nome}</b>, <b>{cpf}</b>, <b>{data}</b> e <b>{hora}</b> para eu preencher sozinho. O nome sai do certificado.</p>';
  } else if (cert.aba === "desenhar") {
    alvo.innerHTML =
      '<p class="as-explica">Desenhe a rubrica com o mouse ou o dedo, sobre a linha.</p>' +
      '<div class="selo-tela-caixa"><canvas class="selo-tela" id="selo-canvas" width="640" height="200"></canvas><span class="selo-linha-base" aria-hidden="true"></span></div>' +
      '<div class="as-linha-botoes"><button class="com-icone" id="selo-desfazer">' + ic("undo", 16) + "Desfazer</button>" +
      '<button class="com-icone" id="selo-limpar">' + ic("delete", 16) + "Limpar</button>" +
      '<span class="cresce"></span><button class="primario com-icone" id="selo-usar">' + ic("check", 16) + "Usar no selo</button></div>";
    ligarCanvas();
  } else {
    /* Uma area de soltar que tambem abre o seletor do Windows ao clicar. O
       clique e ligado AQUI, a cada vez que a aba e desenhada: ligado so na
       abertura da tela, a aba que nascia depois ficava sem clique. */
    alvo.innerHTML =
      (s.imagem
        ? '<div class="selo-img-atual"><img src="/api/certificado/selo/imagem.png?t=' + Date.now() + '" alt="Imagem do selo">' +
          '<div class="as-linha-botoes"><button class="com-icone" id="selo-trocar-img">' + ic("upload", 16) + "Trocar</button>" +
          '<button class="com-icone" id="selo-tirar-img">' + ic("delete", 16) + "Tirar a imagem</button></div></div>"
        : '<button type="button" class="selo-solta" id="selo-solta">' + ic("upload", 22) + "<b>Escolher uma imagem PNG</b>" +
          "<small>ou arraste o arquivo para cá · fundo transparente fica melhor · até 4 MB</small></button>") +
      '<input type="file" id="selo-img-arquivo" accept="image/png" hidden>';
    const arq = $("selo-img-arquivo");
    const abrir = () => arq.click();
    arq.onchange = () => arq.files[0] && enviarImagemSelo(arq.files[0], "imagem");
    const solta = $("selo-solta");
    if (solta) {
      solta.onclick = abrir;
      solta.ondragover = (e) => { e.preventDefault(); solta.classList.add("sobre"); };
      solta.ondragleave = () => solta.classList.remove("sobre");
      solta.ondrop = (e) => {
        e.preventDefault();
        solta.classList.remove("sobre");
        const f = e.dataTransfer.files[0];
        if (!f) return;
        if (!/\.png$/i.test(f.name) && f.type !== "image/png") { avisoCert("o selo aceita só imagem PNG"); return; }
        enviarImagemSelo(f, "imagem");
      };
    }
    const trocar = $("selo-trocar-img");
    if (trocar) trocar.onclick = abrir;
    const tirar = $("selo-tirar-img");
    if (tirar) tirar.onclick = async () => {
      const r = await (await fetch("/api/certificado/selo/imagem", { method: "DELETE" })).json();
      cert.dados.selo = r.selo;
      desenharAssinatura();
    };
  }
  document.querySelectorAll("[data-aba]").forEach((b) => { b.classList.toggle("ativa", b.dataset.aba === cert.aba); });
}

function ligarAssinatura() {
  const raiz = $("assinatura");
  document.querySelectorAll("[data-as-visao]").forEach((b) => {
    b.onclick = () => (b.dataset.asVisao === "certificado" ? mostrarCertificado() : mostrarAssinar(assina.doc ? assina.doc.caminho : ""));
  });
  if (cert.visao === "certificado") return ligarCertificado();
  if (assina.doc) return ligarAssinar();
  ligarListaDePdfs();
}

function ligarCertificado() {
  const d = cert.dados;

  const irAssinar = $("cert-ir-assinar");
  if (irAssinar) irAssinar.onclick = () => mostrarAssinar();

  const campo = $("cert-arquivo");
  $("cert-escolher").onclick = () => campo.click();
  campo.onchange = () => campo.files[0] && enviarCertificado(campo.files[0]);
  const solta = $("cert-solta");
  solta.ondragover = (e) => { e.preventDefault(); solta.classList.add("sobre"); };
  solta.ondragleave = () => solta.classList.remove("sobre");
  solta.ondrop = (e) => {
    e.preventDefault();
    solta.classList.remove("sobre");
    if (e.dataTransfer.files[0]) enviarCertificado(e.dataTransfer.files[0]);
  };

  const teste = $("cert-teste");
  if (teste) teste.onclick = async () => {
    teste.disabled = true;
    const r = await fetch("/api/certificado/teste", { method: "POST" });
    if (!r.ok) { avisoCert(await erroDe(r)); teste.disabled = false; return; }
    const d2 = await r.json();
    cert.dados = d2;
    desenharAssinatura();
    avisoCert("certificado de teste criado — a senha dele é “" + d2.senha_do_teste + "”");
  };

  $("cert-ver-windows").onclick = () => abrirCertificadosDoWindows();

  const trocar = $("cert-trocar");
  if (trocar) trocar.onclick = () => campo.click();
  const remover = $("cert-remover");
  if (remover) remover.onclick = async () => {
    if (!(await confirmar({ titulo: "Remover o certificado?", contexto: "Assinatura › Certificado", texto: "A cópia guardada aqui e a senha são apagadas. O arquivo original que você enviou continua onde estava.", confirmar: "Remover", perigo: true }))) return;
    cert.dados = await (await fetch("/api/certificado", { method: "DELETE" })).json();
    desenharAssinatura();
  };

  const senha = $("cert-senha");
  if (senha) {
    $("cert-mostrar").onclick = () => {
      const ver = senha.type === "password";
      senha.type = ver ? "text" : "password";
      const olho = $("cert-mostrar");
      olho.innerHTML = ic(ver ? "visibility_off" : "visibility", 18);
      olho.title = ver ? "Esconder a senha" : "Mostrar a senha";
      olho.setAttribute("aria-label", olho.title);
      olho.classList.toggle("on", ver);
      senha.focus();
    };
    const guardar = $("cert-guardar");
    if (guardar) guardar.onclick = () => { cert.guardar = !cert.guardar; guardar.classList.toggle("on", cert.guardar); };
    const abrir = async () => {
      if (!senha.value) { senha.focus(); return; }
      const botao = $("cert-abrir");
      botao.disabled = true;
      const r = await fetch("/api/certificado/senha", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ senha: senha.value, guardar: cert.guardar }),
      });
      botao.disabled = false;
      if (!r.ok) { avisoCert(await erroDe(r)); return; }
      cert.dados = await r.json();
      desenharAssinatura();
      avisoCert(cert.dados.aviso || "certificado aberto");
    };
    $("cert-abrir").onclick = abrir;
    senha.onkeydown = (e) => { if (e.key === "Enter") abrir(); };
    const esquecer = $("cert-esquecer");
    if (esquecer) esquecer.onclick = async () => {
      cert.dados = await (await fetch("/api/certificado/esquecer", { method: "POST" })).json();
      desenharAssinatura();
    };
  }

  const minutos = $("cert-minutos");
  if (minutos) minutos.onchange = () => gravarCofre({ minutos: Number(minutos.value) });
  document.querySelectorAll("[data-cofre]").forEach((t) => {
    t.onclick = async () => {
      const chave = t.dataset.cofre;
      await gravarCofre({ [chave]: !cert.dados[chave] });
      t.classList.toggle("on", Boolean(cert.dados[chave]));
    };
  });

  document.querySelectorAll("[data-aba]").forEach((b) => { b.onclick = () => { cert.aba = b.dataset.aba; painelSelo(); }; });
  painelSelo();
  document.querySelectorAll("[data-selo]").forEach((m) => { m.onclick = () => m.classList.toggle("on"); });

  $("selo-salvar").onclick = async () => {
    const texto = $("selo-texto");
    const novo = { posicao: $("selo-posicao").value };
    if (texto) novo.texto = texto.value;
    document.querySelectorAll("[data-selo]").forEach((m) => { novo[m.dataset.selo] = m.classList.contains("on"); });
    const r = await (await fetch("/api/certificado/selo", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(novo),
    })).json();
    cert.dados.selo = r.selo;
    $("selo-previa").innerHTML = previaSelo(cert.dados);
    avisoCert("selo salvo");
  };

  $("selo-restaurar").onclick = async () => {
    const ok = await confirmar({
      titulo: "Restaurar o selo padrão?", contexto: "Assinatura › Selo",
      texto: "O texto, as marcas e a posição voltam ao padrão, e a rubrica desenhada e a imagem enviada são apagadas. O certificado e as assinaturas já feitas não mudam.",
      confirmar: "Restaurar",
    });
    if (!ok) return;
    const r = await fetch("/api/certificado/selo/restaurar", { method: "POST" });
    if (!r.ok) { avisoCert(await erroDe(r)); return; }
    cert.dados.selo = (await r.json()).selo;
    cert.tracos = [];
    desenharAssinatura();
    avisoCert("selo de volta ao padrão");
  };
}

async function gravarCofre(mudanca) {
  cert.dados = await (await fetch("/api/certificado/opcoes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(mudanca),
  })).json();
}

async function enviarCertificado(arquivo) {
  const forma = new FormData();
  forma.append("arquivo", arquivo);
  const r = await fetch("/api/certificado/arquivo", { method: "POST", body: forma });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  cert.dados = await r.json();
  desenharAssinatura();
  avisoCert("certificado guardado — digite a senha para eu conseguir lê-lo");
}

async function enviarImagemSelo(arquivo, campo) {
  const leitor = new FileReader();
  leitor.onload = async () => {
    const r = await fetch("/api/certificado/selo/imagem", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ campo: campo, dados: leitor.result }),
    });
    if (!r.ok) { avisoCert(await erroDe(r)); return; }
    cert.dados.selo = (await r.json()).selo;
    desenharAssinatura();
  };
  leitor.readAsDataURL(arquivo);
}

/* O desenho da rubrica: tracos guardados em pontos, para o Desfazer voltar
   um traco inteiro em vez de um pixel. */
function ligarCanvas() {
  const tela = $("selo-canvas");
  if (!tela) return;
  const pincel = tela.getContext("2d");
  cert.tracos = [];

  const redesenhar = () => {
    pincel.clearRect(0, 0, tela.width, tela.height);
    pincel.strokeStyle = "#14120f";
    pincel.lineWidth = 3;
    pincel.lineCap = "round";
    pincel.lineJoin = "round";
    cert.tracos.forEach((traco) => {
      pincel.beginPath();
      traco.forEach((p, i) => (i ? pincel.lineTo(p.x, p.y) : pincel.moveTo(p.x, p.y)));
      pincel.stroke();
    });
  };

  const ponto = (e) => {
    const caixa = tela.getBoundingClientRect();
    return {
      x: (e.clientX - caixa.left) * (tela.width / caixa.width),
      y: (e.clientY - caixa.top) * (tela.height / caixa.height),
    };
  };

  tela.onpointerdown = (e) => {
    tela.setPointerCapture(e.pointerId);
    cert.desenhando = true;
    cert.tracos.push([ponto(e)]);
  };
  tela.onpointermove = (e) => {
    if (!cert.desenhando) return;
    cert.tracos[cert.tracos.length - 1].push(ponto(e));
    redesenhar();
  };
  tela.onpointerup = () => { cert.desenhando = false; };

  $("selo-desfazer").onclick = () => { cert.tracos.pop(); redesenhar(); };
  $("selo-limpar").onclick = () => { cert.tracos = []; redesenhar(); };
  $("selo-usar").onclick = async () => {
    if (!cert.tracos.length) { avisoCert("desenhe a assinatura antes"); return; }
    const r = await fetch("/api/certificado/selo/imagem", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ campo: "desenho", dados: tela.toDataURL("image/png") }),
    });
    if (!r.ok) { avisoCert(await erroDe(r)); return; }
    cert.dados.selo = (await r.json()).selo;
    desenharAssinatura();
    avisoCert("rubrica gravada no selo");
  };
}

/* O aviso curto que qualquer tela usa: uma faixa embaixo, que some sozinha.
   Antes ele so aparecia dentro de .tela-topo, que as telas do desenho nao
   tem - e os avisos sumiam. */
