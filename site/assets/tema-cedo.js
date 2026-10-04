/* O tema (claro ou escuro) antes de a pagina aparecer, sem piscar. E o mesmo
   script de uma linha das outras paginas, em arquivo: as paginas com a CSP
   restrita (cadastro e pagamento, worker/index.js) nao rodam script inline. */
try { document.documentElement.setAttribute("data-theme", localStorage.getItem("pv-tema") === "claro" ? "light" : "dark"); } catch (e) { /* sem localStorage: escuro */ }
