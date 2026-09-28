# PAULUS — Retorno do login Google

> **Implementado em 27/09/2026** em `src/pagina_retorno.py`, servido por `src/correio_oauth.py` (`Loopback`). O `.dc.html` do pacote fica fora do git, porque traz um e-mail de exemplo. Diferenças do mockup:
> - **E-mail:** a página abre antes de o PAULUS trocar o código pela autorização, então ainda não sabe o e-mail. Ela pergunta ao PAULUS (`/estado`, só com o `state` deste login) e troca "conferindo a conta…" pelo e-mail, e "login recebido" por "conectado" ou pelo erro.
> - **Permissões:** vêm do `scope` que o Google devolve no endereço. Só aparece o que foi concedido, na descrição de verdade: Drive é "só os arquivos que o PAULUS envia" (`drive.file`), e Agenda é "criar e mudar os compromissos que o PAULUS marca".
> - **Voltar ao PAULUS:** não há `paulus://`. O botão pede ao PAULUS (`/voltar`) que traga a janela para frente, pelo mesmo caminho do "Perguntar ao PAULUS", e tenta fechar a aba.
> - **Expirado:** o login vale 5 minutos (`PRAZO_LOGIN`), não 10. Depois de terminar ou ser cancelado, a porta fica aberta mais 2 minutos respondendo "Este login expirou", em vez de "conexão recusada".
> - **Tema:** o app manda o tema atual ao abrir o login. O botão de tema não tem círculo.
> - **Fontes e ícones:** vão embutidos (woff2 em base64, SVG). A página vem de outra porta e não carrega nada do app nem da internet.

Página que o PAULUS serve em `127.0.0.1:<porta>` quando o Google devolve o usuário após o login (OAuth). Abra `Retorno do login Google.dc.html` no navegador, com `support.js` na mesma pasta.

## Padrão
- Tema escuro por padrão; botão no canto superior direito alterna claro/escuro (salvo em `pv-tema`, o mesmo do app).
- Marca PAVLVS no topo à esquerda; bloco central com no máximo 520 px; rodapé explicando que a página é local.
- Tipografia: EB Garamond (título/marca), Manrope (texto), IBM Plex Mono (rótulos).

## Estados (prop `estado`)
1. **sucesso** — "Pode fechar esta aba e voltar ao PAULUS." Cartão com a conta Google e o que foi autorizado (Gmail, Agenda e Meet, Drive). Botão "Voltar ao PAULUS".
2. **negado** — `error=access_denied`: "A conexão não foi autorizada." Nada foi conectado.
3. **expirado** — `state` inválido ou já usado: "Este login expirou." Link vale 10 min, uso único.

## Implementação
- "Voltar ao PAULUS" deve abrir o app por deep link (ex.: `paulus://conexoes`) ou focar a janela; navegadores só permitem `window.close()` em abas abertas por script.
- Na versão servida pelo app, empacotar fontes e o ícone do Google localmente (o protótipo usa Google Fonts e unpkg).
- E-mail exibido e permissões devem vir da resposta real do token.
