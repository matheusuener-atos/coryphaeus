/* ------------------------------------------ modelo por máquina (L6) */
/*
   O cartão "Perfil desta máquina" em Configurações › Modelos: a faixa de
   hardware (placa NVIDIA, AMD, Intel Arc, integrada ou só o processador), o
   modelo que o perfil sugere, por onde o Ollama roda (CUDA, ROCm, Vulkan ou
   o processador) e, quando é o caso, ligar o Vulkan (src/perfis.py). Nada é
   trocado sozinho: o perfil sugere, a pessoa mede e escolhe.
*/

function cartaoPerfilDaMaquina(p) {
  if (!p) return "";
  const placa = p.placa ? p.placa.nome + (p.placa.memoria_gb ? " · " + String(p.placa.memoria_gb).replace(".", ",") + " GB" + (p.placa.exata ? "" : " (pelo Windows)") : "") : "nenhuma com memória própria";
  const o = p.ollama || {};
  const vulkan = o.variavel === "OLLAMA_VULKAN" && acessoDeFora.local
    ? '<div class="ag-toggle' + (p.vulkan_ligado ? " on" : "") + '" data-perfil-vulkan="1"><span class="duas-linhas"><b>Usar esta placa pelo Vulkan</b>' +
      "<small>grava OLLAMA_VULKAN=1 na sua conta do Windows; o Ollama lê ao ser reaberto. Experimental no Ollama: meça antes e depois</small></span><i></i></div>"
    : "";
  return cartaoCfg("Perfil desta máquina", metaCfg(p.rotulo || ""),
    fichaCfg([["Faixa", p.rotulo || "—"], ["Placa", placa], ["Ollama roda por", o.motor || "—"], ["Sugestão", p.modelo || "—"]]) +
    '<div class="prf-explica">' + (p.explica || []).map((x) => "<p>" + esc(x) + "</p>").join("") +
    (o.explica ? "<p>" + esc(o.explica) + "</p>" : "") +
    (p.avisos || []).map((x) => '<p class="prf-aviso">' + esc(x) + "</p>").join("") + "</div>" + vulkan +
    '<p class="cfg-explica">O perfil só sugere. Meça o modelo sugerido em “Nesta máquina” e troque em “Quem faz cada tarefa” se ele for melhor aqui.</p>');
}

function ligarPerfilDaMaquina(raiz) {
  const t = raiz && raiz.querySelector("[data-perfil-vulkan]");
  if (!t) return;
  t.onclick = async () => {
    const ligar = !t.classList.contains("on");
    const r = await fetch("/api/maquina/perfil/vulkan", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ligar: ligar }) });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    const d = await r.json();
    t.classList.toggle("on", d.vulkan_ligado);
    if (mod.perfil) mod.perfil.vulkan_ligado = d.vulkan_ligado;
    avisoCert((d.vulkan_ligado ? "Vulkan ligado. " : "Vulkan desligado. ") + d.proximo, { tom: "ok" });
  };
}
