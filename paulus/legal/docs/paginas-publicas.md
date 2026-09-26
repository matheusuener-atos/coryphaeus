# Páginas públicas do PAULUS (para a verificação do Google)

O app **PAVLVS** no Google Cloud (projeto `pavlvs`, Google Auth Platform › Branding) já aponta para estes endereços, que **ainda não existem**. Enquanto não estiverem no ar, o app fica em modo Teste.

| O quê | Endereço |
| --- | --- |
| Página inicial | https://paulus.ia.br |
| Política de privacidade | https://paulus.ia.br/politica-de-privacidade |
| Termos de uso | https://paulus.ia.br/termos-de-uso |
| Domínio autorizado | `paulus.ia.br` (DNS no Cloudflare) |
| Contato do desenvolvedor | contato@paulus.ia.br |
| Nome na tela de consentimento | PAVLVS — Assistente jurídico de IA local |

As três páginas precisam estar no mesmo domínio, abrir sem login e ser públicas (o robô do Google precisa conseguir ler).

## 1. Página inicial — `paulus.ia.br`

O Google confere se ela descreve o app de verdade e se bate com a tela de consentimento.

- O nome **PAULUS / PAVLVS**, igual ao da tela de consentimento, e o logotipo (`Downloads\PAULUS - identidade visual`).
- O que o programa faz, em linguagem simples: assistente jurídico que roda **no computador do escritório**, com modelo de IA local; acervo de documentos, editor, assinatura digital, agenda e e-mail.
- **Por que ele pede acesso ao Gmail:** ler as mensagens que a pessoa abre na caixa do PAULUS, transformar prazos em sugestão na Agenda, e enviar respostas — sempre passando por Aprovações antes de sair.
- Link visível para a política de privacidade e para os termos de uso.
- Um jeito de falar com vocês (contato@paulus.ia.br).

## 2. Política de privacidade — `/politica-de-privacidade`

A parte mais conferida pelo Google. Precisa dizer, sem rodeio, **como o app acessa, usa, guarda e compartilha os dados do Google**. Conferir cada frase com o código antes de publicar — nada de prometer o que o programa não faz.

- **Quem é o responsável** (LGPD): nome, CNPJ/CPF, endereço e o contato do encarregado de dados.
- **Quais dados do Google** o PAULUS acessa: o endereço de e-mail da conta (para identificar a conta) e as mensagens do Gmail (ler, enviar, arquivar), pelo escopo `https://mail.google.com/`.
- **Para que usa:** só para mostrar a caixa ao próprio usuário, sugerir prazos e rascunhos, e enviar o que ele aprovou. Nada de publicidade, de vender dados ou de treinar modelos.
- **Onde fica:** no computador de quem usa. A autorização do Google (refresh token) fica cifrada pela conta do Windows (DPAPI); o modelo de IA roda na própria máquina. **Conferir antes de publicar** se nenhum recurso manda conteúdo para fora (internet, outro serviço de IA) — se mandar, isso precisa estar escrito aqui.
- **Com quem compartilha:** com ninguém. Dizer exatamente isso só se for verdade no código.
- **Como apagar:** remover a conta no PAULUS e revogar o acesso em https://myaccount.google.com/permissions. Dizer quanto tempo os dados ficam (enquanto a conta estiver ligada; apagados ao remover).
- **Direitos do titular (LGPD)** e como pedir.
- **A declaração de Uso Limitado**, obrigatória para quem usa dados do Google — texto de referência (adaptar o nome):

  > O uso e a transferência, para qualquer outro app, de informações recebidas das APIs do Google pelo PAVLVS obedecem à [Política de Dados do Usuário dos Serviços de API do Google](https://developers.google.com/terms/api-services-user-data-policy), incluindo os requisitos de Uso Limitado.

## 3. Termos de uso — `/termos-de-uso`

- O que é o serviço e quem o oferece.
- Responsabilidade: o assistente sugere; a decisão e a revisão de cada documento, prazo e envio são do profissional (o programa passa por Aprovações antes de enviar, assinar ou apagar).
- Licença de uso, suporte, limites de responsabilidade, foro.
- Link para a política de privacidade.

## 4. Depois de publicar

1. **Verificar o domínio** `paulus.ia.br` no Google Search Console (registro TXT no DNS do Cloudflare), com a mesma conta dona do projeto no Google Cloud.
2. Conferir que os três links abrem sem login e que a página inicial tem o link da política.
3. No Google Cloud, pedir a verificação em **Central de verificação**. Para o escopo restrito do Gmail, o Google também pede:
   - um vídeo (pode ser não listado no YouTube) mostrando a tela de consentimento e o uso de cada permissão dentro do PAULUS;
   - justificativa de cada escopo;
   - a avaliação de segurança anual (CASA), paga, feita por laboratório credenciado.
4. Enquanto a verificação não sai, dá para publicar o app como **Em produção** sem verificação: acaba o vencimento de 7 dias e a lista de testadores, mas fica o aviso de "app não verificado" e o limite de 100 contas.
