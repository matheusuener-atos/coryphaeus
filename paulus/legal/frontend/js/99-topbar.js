/* A BARRA DO ALTO (pedido de 11/10/2026): o trilho sai e os destinos viram
   texto numa barra de 56 px, no desenho do Pos-instalador - PAVLVS a
   esquerda, os destinos a direita, os tres botoes da janela no canto, fio fino
   embaixo. Os destinos sao muitos para uma linha so: Assistente fica solto e
   o resto vai em tres grupos que abrem uma lista. Quem navega continua sendo o
   trilho (escondido): cada item da barra so clica o botao dele, e o ativo da
   barra segue o ativo do trilho. */
(function () {
  const GRUPOS = [
    { rotulo: "Assistente", destino: "conversa" },
    { rotulo: "Trabalho", itens: ["servicos", "gravacoes", "calendario", "foco"] },
    { rotulo: "Documentos", itens: ["biblioteca", "contexto", "editor", "assinar"] },
    { rotulo: "Escritório", itens: ["caixa", "financeiro", "cadastros", "aprovacoes", "agentes", "consumo", "notas"] },
    { rotulo: "Configurações", itens: ["config"], conta: true },
  ];
  const trilho = document.getElementById("trilho");
  if (!trilho || document.getElementById("topbar")) return;
  const doTrilho = (d) => trilho.querySelector('.trilho-item[data-destino="' + d + '"]');
  const nome = (d) => { const b = doTrilho(d); return b ? b.getAttribute("aria-label") || b.title || d : d; };
  const icone = (d) => { const b = doTrilho(d); const i = b && b.querySelector(".ic"); return i ? i.textContent : ""; };
  const e = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const barra = document.createElement("header");
  barra.className = "topbar pywebview-drag-region";
  barra.id = "topbar";
  barra.innerHTML =
    '<div class="topbar-marca-grupo"><button type="button" class="topbar-marca" id="topbar-marca" title="Ir para o início" aria-label="PAVLVS · ir para o início">PAVLVS</button>' +
    '<time class="topbar-relogio" id="topbar-relogio"></time></div>' +
    '<button type="button" class="topbar-busca" id="topbar-busca" title="Buscar em tudo (Ctrl+K)"><span class="ic ic-16">search</span><span class="topbar-busca-texto">Buscar em tudo</span><kbd>Ctrl K</kbd></button>' +
    '<nav class="topbar-nav" aria-label="Destinos">' +
    GRUPOS.map((g, i) => g.destino
      ? '<button type="button" class="topbar-item" data-tb-destino="' + g.destino + '">' + e(g.rotulo) + "</button>"
      : '<div class="topbar-grupo" data-tb-grupo="' + i + '">' +
          '<button type="button" class="topbar-item" aria-haspopup="true" aria-expanded="false" data-tb-abre="' + i + '">' + e(g.rotulo) +
          '<span class="ic ic-16">expand_more</span></button></div>').join("") +
    "</nav>";
  /* A SEGUNDA LINHA: no lugar da lista que caia por cima, a barra estica e
     mostra os destinos do grupo lado a lado, numa linha de 44 px embaixo. */
  const sub = document.createElement("div");
  sub.className = "topbar-sub";
  sub.id = "topbar-sub";
  sub.innerHTML = '<div class="topbar-sub-dentro">' + GRUPOS.map((g, i) => g.itens
    ? '<nav class="topbar-sub-linha" data-tb-linha="' + i + '" aria-label="' + e(g.rotulo) + '">' + g.itens.map((d) =>
        '<button type="button" class="topbar-opcao" data-tb-destino="' + d + '"><span class="ic ic-16">' + e(icone(d)) + "</span><span>" + e(nome(d)) + "</span>" +
        (d === "aprovacoes" ? '<span class="conta topbar-conta" hidden></span>' : "") + "</button>").join("") +
      /* Configuracoes leva junto a conta: Minha conta (so pelo tunel, quando
         ha pessoa de fora) e Sair. */
      (g.conta ? '<button type="button" class="topbar-opcao" id="topbar-minha-conta" hidden><span class="cad-avatar topbar-avatar"></span><span>Minha conta</span></button>' +
        '<button type="button" class="topbar-opcao" id="topbar-sair"><span class="ic ic-16">logout</span><span>Sair</span></button>' : "") + "</nav>"
    : "").join("") + "</div>";
  const corpo = document.querySelector(".corpo");
  corpo.parentElement.insertBefore(barra, corpo);
  corpo.parentElement.insertBefore(sub, corpo);
  // A faixa de avisos sai do pe da janela e entra embaixo da barra.
  const faixa = document.getElementById("faixa-janela");
  if (faixa) corpo.parentElement.insertBefore(faixa, corpo);
  document.documentElement.classList.add("com-topbar");

  // Os botoes da janela moram no canto da barra.
  // O tema fica ao lado dos botoes da janela; ele so clica o do trilho.
  const tema = document.createElement("button");
  tema.type = "button"; tema.className = "botao-janela topbar-tema"; tema.id = "topbar-tema";
  tema.innerHTML = '<span class="ic ic-16"></span>';
  barra.appendChild(tema);
  const temaTrilho = document.getElementById("tema");
  const temaIcone = document.getElementById("tema-icone");
  function espelharTema() {
    tema.querySelector(".ic").textContent = temaIcone ? temaIcone.textContent : "dark_mode";
    tema.title = temaTrilho ? temaTrilho.title : "Alternar tema";
    tema.setAttribute("aria-label", "Alternar tema");
  }
  tema.onclick = () => { if (temaTrilho) temaTrilho.click(); espelharTema(); };
  if (temaIcone) new MutationObserver(espelharTema).observe(temaIcone, { childList: true, characterData: true, subtree: true });
  espelharTema();
  const janela = document.getElementById("botoes-janela");
  if (janela) { barra.appendChild(janela); janela.hidden = false; }

  function mostrarLinha(i) {
    barra.querySelectorAll(".topbar-grupo").forEach((g) => {
      const este = g.dataset.tbGrupo === String(i);
      g.classList.toggle("aberto", este);
      g.querySelector("[data-tb-abre]").setAttribute("aria-expanded", String(este));
    });
    sub.querySelectorAll("[data-tb-linha]").forEach((l) => l.classList.toggle("vista", l.dataset.tbLinha === String(i)));
    sub.classList.toggle("aberta", i !== null && i !== undefined);
  }
  const fecharGrupos = () => mostrarLinha(null);

  /* A linha do grupo recolhe sozinha: 4 s depois de abrir, se o ponteiro nao
     estiver nela nem na barra. Passar o mouse segura; sair conta de novo. */
  const SUB_DURA_MS = 4000;
  let relogioSub = 0;
  const pararRelogio = () => { clearTimeout(relogioSub); relogioSub = 0; };
  const contarRelogio = () => {
    pararRelogio();
    if (!sub.classList.contains("aberta")) return;
    relogioSub = setTimeout(() => { if (!sub.matches(":hover") && !barra.matches(":hover")) fecharGrupos(); }, SUB_DURA_MS);
  };
  new MutationObserver(contarRelogio).observe(sub, { attributes: true, attributeFilter: ["class"] });
  [sub, barra].forEach((el) => {
    el.addEventListener("mouseenter", pararRelogio);
    el.addEventListener("mouseleave", contarRelogio);
  });

  /* O AVISO E O MENU NAO DIVIDEM A LINHA: com um grupo aberto, o aviso que
     chega recolhe a linha do grupo, aparece no lugar dela e, quando vai
     embora, devolve o grupo que estava aberto. Se a pessoa abrir outro grupo
     durante o aviso, o aviso some antes - quem manda e o clique. */
  const faixaAviso = document.getElementById("faixa-janela");
  let grupoGuardado = null;
  let avisoAVista = false;
  if (faixaAviso) {
    new MutationObserver(() => {
      const ve = faixaAviso.classList.contains("visivel");
      if (ve === avisoAVista) return;
      avisoAVista = ve;
      if (ve) {
        const aberto = barra.querySelector(".topbar-grupo.aberto");
        grupoGuardado = aberto ? aberto.dataset.tbGrupo : null;
        if (grupoGuardado !== null) mostrarLinha(null);
      } else if (grupoGuardado !== null) {
        const g = grupoGuardado;
        grupoGuardado = null;
        // espera a faixa terminar de fechar (.3 s) para a linha abrir no lugar dela
        setTimeout(() => { if (!faixaAviso.classList.contains("visivel")) mostrarLinha(g); }, 260);
      }
    }).observe(faixaAviso, { attributes: true, attributeFilter: ["class"] });
  }
  barra.addEventListener("click", (ev) => {
    const abre = ev.target.closest("[data-tb-abre]");
    if (abre) {
      const g = abre.parentElement;
      if (avisoAVista && typeof fecharAvisoNaJanela === "function") { grupoGuardado = null; fecharAvisoNaJanela(); }
      mostrarLinha(g.classList.contains("aberto") ? null : abre.dataset.tbAbre);
      return;
    }
    const alvo = ev.target.closest("[data-tb-destino]");
    if (alvo) {
      // Assistente e Configuracoes recolhem a linha; os do grupo deixam ela aberta.
      fecharGrupos();
      const b = doTrilho(alvo.dataset.tbDestino);
      if (b) b.click();
      return;
    }
    if (ev.target.closest("#topbar-busca")) {
      fecharGrupos();
      const b = document.getElementById("buscar-tudo");
      if (b) b.click();
      return;
    }
    if (ev.target.closest("#topbar-marca")) {
      fecharGrupos();
      if (typeof voltarAoAssistente === "function") voltarAoAssistente();
    }
  });
  sub.addEventListener("click", (ev) => {
    if (ev.target.closest("#topbar-minha-conta")) { const c = document.getElementById("trilho-conta"); if (c) c.click(); return; }
    if (ev.target.closest("#topbar-sair")) { if (typeof sairDoServidor === "function") sairDoServidor(); return; }
    const alvo = ev.target.closest("[data-tb-destino]");
    if (!alvo) return;
    const b = doTrilho(alvo.dataset.tbDestino);
    if (b) b.click();
  });
  document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && sub.classList.contains("aberta")) fecharGrupos(); });

  // O ativo e a contagem de Aprovacoes seguem o trilho.
  function sincronizar() {
    const ativo = trilho.querySelector(".trilho-item.ativo[data-destino]");
    const d = ativo ? ativo.dataset.destino : "";
    [barra, sub].forEach((r) => r.querySelectorAll("[data-tb-destino]").forEach((b) => b.classList.toggle("ativo", b.dataset.tbDestino === d)));
    // Entrar num destino de grupo abre a linha dele; sair para um solto recolhe.
    const grupo = GRUPOS.findIndex((g) => g.itens && g.itens.includes(d));
    if (d && d !== ultimoAtivo) { ultimoAtivo = d; mostrarLinha(grupo >= 0 ? String(grupo) : null); }
    barra.querySelectorAll(".topbar-grupo").forEach((g) => g.classList.toggle("ativo", Boolean(g.querySelector('[data-tb-destino="' + d + '"]'))));
    const c = trilho.querySelector('[data-destino="aprovacoes"] .conta');
    // Minha conta aparece quando o acesso de fora poe a pessoa no trilho.
    const conta = document.getElementById("trilho-conta");
    const mc = document.getElementById("topbar-minha-conta");
    if (mc) {
      mc.hidden = !conta;
      if (conta) {
        const av = conta.querySelector(".cad-avatar");
        mc.querySelector(".topbar-avatar").textContent = av ? av.textContent : "";
        mc.querySelector("span:last-child").textContent = (conta.title || "Minha conta").split(" · ")[0];
        mc.title = conta.title || "Minha conta";
      }
    }
    sub.querySelectorAll('[data-tb-destino="aprovacoes"]').forEach((b) => b.classList.toggle("com-pendente", Boolean(c && !c.hidden && c.textContent)));
    sub.querySelectorAll(".topbar-conta").forEach((x) => { x.textContent = c ? c.textContent : ""; x.hidden = !c || c.hidden; });
  }
  /* O relogio, aos pes da marca: a hora da maquina, virando no minuto. */
  const relogio = document.getElementById("topbar-relogio");
  function marcarHora() {
    const d = new Date();
    const hh = String(d.getHours()).padStart(2, "0"), mm = String(d.getMinutes()).padStart(2, "0");
    relogio.textContent = hh + ":" + mm;
    relogio.dateTime = hh + ":" + mm;
    setTimeout(marcarHora, (60 - d.getSeconds()) * 1000 - d.getMilliseconds() + 20);
  }
  marcarHora();
  let ultimoAtivo = "";
  new MutationObserver(sincronizar).observe(trilho, { subtree: true, attributes: true, attributeFilter: ["class", "hidden"], childList: true, characterData: true });
  sincronizar();
})();


/* A ROLAGEM NA BORDA (pedido de 11/10/2026): nas telas cheias o conteudo tem
   margens, mas a barra de rolagem fica na borda da janela. O rolador
   principal da tela (o maior que rola na vertical dentro da coluna) ganha
   data-rola-borda; o CSS (57-topbar.css) estica ele ate a borda e devolve a
   margem por dentro. */
(function () {
  const marcar = () => {
    const corpo = document.getElementById("conversa-corpo");
    const col = document.getElementById("conversa-col");
    document.querySelectorAll("[data-rola-borda]").forEach((e) => { if (!corpo || !corpo.contains(e) || !col.classList.contains("tela-cheia")) e.removeAttribute("data-rola-borda"); });
    if (!corpo || !col || !col.classList.contains("tela-cheia")) return;
    /* Quem rola dentro de um cartao (moldura dos dois lados, como o historico
       da Trilha) rola no cartao: esticado ate a borda da janela, ele perdia o
       recuo de dentro e passava da borda do cartao (13/10/2026). */
    const dentroDeCartao = (e) => {
      for (let p = e; p && p !== corpo; p = p.parentElement) {
        const cs = getComputedStyle(p);
        if (parseFloat(cs.borderLeftWidth) > 0 && parseFloat(cs.borderRightWidth) > 0) return true;
      }
      return false;
    };
    let melhor = null, area = 0;
    corpo.querySelectorAll("*").forEach((e) => {
      if (e.clientHeight < 200) return;
      const oy = getComputedStyle(e).overflowY;
      if (oy !== "auto" && oy !== "scroll") return;
      if (dentroDeCartao(e)) return;
      // Quem de fato rola vale mais que quem so poderia rolar.
      const a = e.clientWidth * e.clientHeight * (e.scrollHeight > e.clientHeight + 10 ? 10 : 1);
      if (a > area) { area = a; melhor = e; }
    });
    corpo.querySelectorAll("[data-rola-borda]").forEach((e) => { if (e !== melhor) e.removeAttribute("data-rola-borda"); });
    if (!melhor) return;
    /* A distancia ate cada borda da janela, medida sem o ajuste: vira a
       margem negativa (por fora) e o recuo (por dentro). */
    if (!melhor.hasAttribute("data-rola-borda")) {
      const r = melhor.getBoundingClientRect();
      const esq = Math.max(0, Math.round(r.left)), dir = Math.max(0, Math.round(window.innerWidth - r.right));
      melhor.style.setProperty("--rb-esq", esq + "px");
      melhor.style.setProperty("--rb-dir", dir + "px");
      melhor.setAttribute("data-rola-borda", "");
      // Conferir depois de aplicar: o que passou da borda volta.
      const r2 = melhor.getBoundingClientRect();
      const sobra = Math.round(r2.right - document.documentElement.clientWidth);
      if (sobra) melhor.style.setProperty("--rb-dir", Math.max(0, dir - sobra) + "px");
      const sobraE = Math.round(r2.left);
      if (sobraE) melhor.style.setProperty("--rb-esq", Math.max(0, esq + sobraE) + "px");
    }
  };
  let pedido = 0;
  const agendar = () => { if (pedido) return; pedido = setTimeout(() => { pedido = 0; marcar(); }, 16); };
  new MutationObserver(agendar).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });
  window.addEventListener("resize", () => { document.querySelectorAll("[data-rola-borda]").forEach((e) => e.removeAttribute("data-rola-borda")); agendar(); });
  agendar();
})();
