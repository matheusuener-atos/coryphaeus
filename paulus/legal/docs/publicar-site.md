# Site público do PAULUS — paulus.ia.br

Três páginas estáticas (HTML + CSS, um JS pequeno para o tema claro/escuro e o menu do celular). Não tem build, não tem servidor, não tem banco de dados: o que está nesta pasta é exatamente o que vai para o ar.

| Página | Arquivo | Endereço |
| --- | --- | --- |
| Página inicial | `index.html` | https://paulus.ia.br |
| Política de privacidade | `politica-de-privacidade/index.html` | https://paulus.ia.br/politica-de-privacidade |
| Termos de uso | `termos-de-uso/index.html` | https://paulus.ia.br/termos-de-uso |

Outros arquivos: `assets/site.css` (visual de todas as páginas), `assets/site.js` (tema e menu), `assets/paulus-logo.svg` e os PNGs do ícone, `favicon.ico`.

Esses três endereços são os que estão cadastrados no Google Cloud (projeto `pavlvs` › Google Auth Platform › Branding). Eles precisam abrir sem login, no mesmo domínio, antes de pedir a verificação do app.

---

## Antes de publicar — conferir

1. Abra os três arquivos no navegador (duplo clique no `index.html`) e leia tudo uma vez.
2. Os dados do responsável (nome, endereço, foro) estão na Política de privacidade (seção "Quem é o responsável") e nos Termos de uso (itens 2 e 10). Quando a empresa do PAULUS existir, procure no código o comentário `<!-- CNPJ: acrescentar quando a empresa do PAULUS existir -->` e coloque o CNPJ ali.
3. A caixa de e-mail **contato@paulus.ia.br** precisa existir e receber mensagens — o Google e os usuários vão escrever para ela. (No Cloudflare dá para criar de graça em *Email* › *Email Routing*, encaminhando para o seu Gmail.)

---

## Publicar no Cloudflare Pages (pelo painel — o caminho mais simples)

O domínio `paulus.ia.br` já está no Cloudflare, então o Cloudflare cria o DNS sozinho.

### 1. Criar o projeto e subir os arquivos

1. Entre em https://dash.cloudflare.com com a conta que tem o domínio `paulus.ia.br`.
2. No menu da esquerda, clique em **Workers & Pages** (em algumas contas aparece como **Compute (Workers)** › **Workers & Pages**).
3. Clique em **Create** (Criar).
4. Escolha a aba **Pages** e clique em **Upload assets** (Enviar arquivos). *Não* escolha "Connect to Git" — não precisa.
5. Em **Project name**, escreva `paulus` e clique em **Create project**.
6. Na tela de envio, arraste **a pasta `site` inteira** (esta pasta, `C:\coryphaeus\site`) ou clique em *select from computer* › *Upload folder* e escolha-a.
   - Confira na lista que aparecem `index.html`, `politica-de-privacidade/index.html`, `termos-de-uso/index.html` e a pasta `assets`. O `index.html` tem que estar na raiz, não dentro de outra pasta.
7. Clique em **Deploy site**. Em alguns segundos aparece um endereço do tipo `https://paulus.pages.dev`. Abra e confira as três páginas:
   - `https://paulus.pages.dev/`
   - `https://paulus.pages.dev/politica-de-privacidade`
   - `https://paulus.pages.dev/termos-de-uso`

> O arquivo `README.md` também vai junto e fica acessível em `/README.md`. Não tem nada secreto nele; se preferir, suba uma cópia da pasta sem ele.

### 2. Ligar o domínio paulus.ia.br

1. Ainda no projeto `paulus`, abra a aba **Custom domains** (Domínios personalizados).
2. Clique em **Set up a custom domain**, escreva `paulus.ia.br` e clique em **Continue**.
3. Como o DNS já está no Cloudflare, ele mostra o registro que vai criar (um CNAME de `paulus.ia.br` para `paulus.pages.dev`). Clique em **Activate domain**.
4. Espere o status ficar **Active** (normalmente poucos minutos; o certificado HTTPS é emitido sozinho).
5. Opcional, mas recomendado: repita os passos 2 a 4 com `www.paulus.ia.br`, para quem digitar com "www" também chegar.
6. Teste no navegador, de preferência numa janela anônima:
   - https://paulus.ia.br
   - https://paulus.ia.br/politica-de-privacidade
   - https://paulus.ia.br/termos-de-uso

   O Cloudflare pode acrescentar uma barra no fim do endereço (`/politica-de-privacidade/`) — é normal, e o Google aceita.

> Se aparecer erro de DNS: em **DNS** › **Records** do domínio, veja se já existe um registro antigo para `paulus.ia.br` (A, AAAA ou CNAME) apontando para outro lugar. Apague esse registro antigo e repita o passo 2.

### 3. Atualizar o site depois

Mudou algum texto? Abra o projeto `paulus` em **Workers & Pages**, clique em **Create deployment** (Criar implantação) e arraste a pasta `site` de novo. A versão nova substitui a anterior no mesmo endereço.

---

## Opção B — publicar pela linha de comando (wrangler)

Para quem prefere o terminal. Precisa do Node.js instalado.

```powershell
# 1. Entrar na conta do Cloudflare (abre o navegador; tem que ser o dono da conta)
npx wrangler login

# 2. Publicar a pasta (rodar a partir de C:\coryphaeus)
npx wrangler pages deploy site --project-name paulus
```

Na primeira vez o wrangler pergunta se quer criar o projeto `paulus` e qual é a branch de produção (responda `main`). Depois disso, o domínio `paulus.ia.br` é ligado pelo painel, como no passo 2 da opção A — só uma vez.

---

## Verificar o domínio no Google Search Console

O Google só aprova o app se o domínio `paulus.ia.br` estiver verificado **pela mesma conta Google que é dona (ou editora) do projeto `pavlvs` no Google Cloud**. Use essa conta em todos os passos abaixo.

1. Abra https://search.google.com/search-console **logado com a conta dona do projeto do Google Cloud**. (Confira o e-mail no canto de cima à direita.)
2. Clique em **Adicionar propriedade** (no seletor de propriedades, no alto à esquerda; na primeira vez a tela já abre nele).
3. Escolha o tipo **Domínio** (o quadro da esquerda) — não "Prefixo do URL".
4. Escreva só `paulus.ia.br` (sem `https://`, sem `www`) e clique em **Continuar**.
5. O Google mostra um registro **TXT** parecido com `google-site-verification=AbC123...`. Clique em **Copiar**. Deixe essa janela aberta.
6. Em outra aba, no Cloudflare: abra o domínio **paulus.ia.br** › **DNS** › **Records** › **Add record**:
   - **Type:** `TXT`
   - **Name:** `@` (quer dizer o próprio `paulus.ia.br`)
   - **Content:** cole o texto copiado, inteiro (`google-site-verification=...`)
   - **TTL:** Auto
   - Clique em **Save**.
7. Volte ao Search Console e clique em **Verificar**. Se disser que não encontrou, espere alguns minutos e clique de novo (às vezes leva até uma hora).
8. **Não apague esse registro TXT depois** — o Google confere de tempos em tempos; se sumir, o domínio deixa de estar verificado.

Pronto: no Google Cloud (Google Auth Platform › **Branding**), o domínio `paulus.ia.br` em *Authorized domains* passa a aparecer como verificado.

---

## Depois de tudo no ar — pedir a verificação do app

1. Google Cloud › projeto `pavlvs` › **Google Auth Platform** › **Branding**: confira que
   - Página inicial: `https://paulus.ia.br`
   - Política de privacidade: `https://paulus.ia.br/politica-de-privacidade`
   - Termos de serviço: `https://paulus.ia.br/termos-de-uso`
   - Domínio autorizado: `paulus.ia.br`
2. Abra cada um desses endereços numa janela anônima e veja se carrega (é isso que o robô do Google faz).
3. Em **Verification Center** (Central de verificação), envie de novo o pedido de verificação.
