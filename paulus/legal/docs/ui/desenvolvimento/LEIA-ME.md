# PAVLVS — Desenvolvimento aberto, Apoiadores e Apoiar

> **Removido em 07/10/2026** (telas revisadas): a página /desenvolvimento saiu do site, a rota `/api/public/desenvolvimento` do Worker, a tela A20 e a rota `/api/publico/{qual}` do programa, e o `tools/desenvolvimento.py` com o `site/dados/versoes.json`. O texto abaixo fica como registro.
>
> **Implementado em 28/09/2026**, a partir do pacote `export-desenvolvimento-aberto` (o `IMPLEMENTACAO.md` dele está resumido abaixo). Os `.dc.html` e os JSON de exemplo ficam fora do git: a lista de exemplo traz um nome real.

## Onde está cada parte

| Parte | Arquivo |
|---|---|
| Site `/desenvolvimento` | `site/desenvolvimento/index.html`, `site/assets/desenvolvimento.js` |
| Site `/apoiadores` | `site/apoiadores/index.html`, `site/assets/apoiadores.js` |
| Site `/apoiar` | `site/apoiar/index.html`, `site/assets/apoiar.js` |
| Estilo das três | `site/assets/paginas.css` (sobre o `site.css`) |
| API pública | `worker/index.js`: `GET /api/public/desenvolvimento` e `GET /api/public/apoiadores` |
| Cartão avulso (site) | `worker/index.js`: `POST /api/mp/cartao` (Checkout Pro) |
| Versões | `site/dados/versoes.json`, gerado por `tools/desenvolvimento.py` a partir das releases |
| ITCD recolhido | `site/dados/itcd.json` (`{"2026-09": 22.10}`), editado à mão quando houver recolhimento |
| App, tela A20 | `frontend/js/41-desenvolvimento.js`, `frontend/css/29-desenvolvimento.css`, rota `GET /api/publico/{desenvolvimento,apoiadores}` |

## Decisões e diferenças do pacote

- **Público separado do privado.** Cada contribuição confirmada vira uma chave `contrib:AAAA-MM:<id>` no KV com só o valor; cada nome autorizado, `mural:<hash do e-mail>` com só nome e mês. As rotas públicas leem só essas chaves. O teste do Worker confere que nenhum id, e-mail ou hash sai nelas.
- **Sem contagem dupla.** A chave é o id do pagamento: o mesmo aviso do Mercado Pago repetido não soma de novo. Os Pix pagos antes disto entram uma vez (`migracao:contrib-1`); as cobranças antigas do cartão, quando o programa pede o extrato.
- **Mural.** O nome vai com o pedido de pagamento e só entra no mural quando o pagamento confirma. Uma entrada por pessoa (hash do e-mail), com o mês do primeiro apoio. Nome com marcação ou endereço de internet é descartado. Para sair, a pessoa escreve para contato@paulus.ia.br: não há como provar quem é sem conta.
- **No app, "aparecer" virou "publicar" e começa desligado para todos.** O campo antigo vinha ligado de fábrica, e ninguém o ligou sabendo que o nome iria a uma página pública. A cidade saiu: o mural mostra só o nome.
- **Apoiar no site.** Pix aparece na página e ela espera a confirmação. Cartão uma vez vai ao Checkout Pro; mensal, à assinatura. Os links "simular" do protótipo saíram. A assinatura feita no site guarda a chave no navegador, e é assim que a página oferece "Interromper" (o texto diz isso). O "Obrigado" não promete extrato no site: o extrato é do programa.
- **Versões.** As quatro primeiras (0.9.0 a 0.9.3) foram revistas à mão e marcadas `"curado": true`; o gerador nunca sobrescreve uma versão curada. O `publicar.py` roda o gerador a cada versão nova. Miniaturas (`preview`) só de `paulus.ia.br` ou de caminho do próprio site.
- **Cache.** As rotas públicas ficam 15 minutos na borda (o pacote sugeria 1 h): uma versão nova aparece rápido.
- **Plataforma.** A seção Apoiar da página inicial já não tinha meta nem selos; ganhou os dois links, e o mural da ilustração aparece desligado.
- **Cabeçalho.** Nas páginas do site, só o nome PAVLVS, sem logo, e o botão de tema sem moldura; o menu é Plataforma · Desenvolvimento · Apoiadores · Apoiar.

## Pendências do dono

- No painel do Mercado Pago (Webhooks), ligar também os tópicos **Pagamentos** (`payment`, para o cartão avulso do site) e **Planos e assinaturas › pagamentos autorizados** (`subscription_authorized_payment`, para cada cobrança mensal entrar no total do mês).
- Registrar o ITCD em `site/dados/itcd.json` quando houver recolhimento. Sem registro, a página diz "aguardando apuração".
