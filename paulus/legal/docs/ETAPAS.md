# Etapas — do que existe hoje às 20 telas do manual

Cinco destinos têm motor. Quinze não. Este documento separa esses quinze em
etapas pela **dependência real**, não pela ordem do menu: cada etapa entrega
telas que funcionam e destrava as seguintes.

Sem estimativa em semanas — depende do ritmo de quem constrói. O que está
declarado é o **tamanho relativo** e o **que cada etapa desbloqueia**, que é a
informação que muda a ordem.

---

## Onde estamos

As vinte telas do manual têm motor por trás. A tabela diz o que sustenta cada
uma — porque "pronta" sem isso é só um botão que abre uma tela.

| Tela | Motor por trás |
|---|---|
| Conversa | extração, busca BM25, assistente local, conversas persistidas |
| Calendário | grade que junta compromisso, prazo e data de documento |
| Agendamento | horários livres pela disponibilidade da pessoa |
| Tarefas | base local, com prazo, etapas e vínculo a cliente |
| Foco e bem-estar | tempo ocioso do sistema, sem ler tecla; totais por dia |
| Biblioteca | índice de documentos + cache de classificação |
| Organizar pastas | varredura, classificação híbrida, plano, diário, desfazer |
| Editor de texto | HTML → blocos → PDF e DOCX pelo mesmo caminho; versões |
| Planilha | analisador de fórmula escrito à mão, em português brasileiro |
| Assinar documento | PAdES com certificado A1, via pyHanko |
| Financeiro | lançamentos em centavos inteiros, extrato com saldo correndo |
| Cadastros | base local, com sugestões vindas dos documentos lidos |
| Caixa de entrada | IMAP e SMTP, cabeçalho primeiro, prazo por regra |
| Aprovações | fila persistida, com execução após o sim |
| Relatórios | soma do que as outras telas gravaram; parecer só depois |
| Aprendizado | registro de habilidades carregado da pasta |
| Certificado digital | leitura do .pfx, DPAPI para a senha, aviso de ICP-Brasil |
| Conexões | janela presa a um endereço, sessão só desta máquina |
| Desempenho | leitura real de processador, memória e vídeo |
| Configurações | preferências, autonomia e dados profissionais |

O que continua não existindo, e por quê, está escrito nas etapas: citação de
código de lei (não carrego o texto das leis), assinatura por token A3 (driver
PKCS#11 por fabricante), OAuth de e-mail (semanas de revisão antes da primeira
linha funcionar), automação do WhatsApp Web (dirigir a tela de um site de
terceiro) e permissão por pessoa no financeiro (pertence a um PAULUS de equipe).

---

## Etapa 1 — A moldura que falta ✓ FEITA

**Telas:** Aprovações · Configurações
**Tamanho:** pequeno — quase tudo já existia por baixo
**Destrava:** todas as etapas seguintes

Entregue. A fila existe em `src/aprovacoes.py`, sobrevive ao fechamento do
programa e já recebe o primeiro cliente de verdade: mover arquivos em lote
deixou de acontecer direto e passa por ela. As preferências em `src/config.py`
guardam o que o assistente pode fazer sozinho — tudo desligado por padrão.

O manual tem uma regra central: *nada com efeito externo acontece sem
aprovação*. Hoje isso existe só dentro do organizador, como um cartão. Enviar
e-mail, assinar, pagar e conceder acesso — tudo o que vem nas próximas etapas —
precisa de uma fila para cair.

Configurações consolida o que hoje está espalhado por linha de comando e
variável de ambiente: pastas do acervo, modelo em uso, e o que o assistente
pode fazer sozinho.

Construir isso antes evita ter que voltar em cada tela depois.

---

## Etapa 2 — Memória do escritório ✓ FEITA

**Telas:** Cadastros · Tarefas
**Tamanho:** médio — o trabalho foi a camada de dados, não as telas
**Destrava:** Calendário, Agendamento, Financeiro, Relatórios

Entregue. `src/base.py` é SQLite com migrações numeradas — base de versão
antiga recebe só o que falta, sem perder o que já estava lá. Cadastros e
Tarefas usam essa camada; Calendário, Agendamento e Financeiro usarão a mesma.

Cinco telas precisam da mesma coisa: um lugar para guardar registro. Hoje o
programa só guarda arquivo e conversa. Uma base local (SQLite) resolve as cinco.

Cadastros vem primeiro porque **já temos metade dele pronto sem perceber**: a
classificação extrai as partes, o CPF/CNPJ, a data e o valor de cada contrato.
Cadastro deixa de ser digitação e vira confirmação do que o assistente já leu.

Tarefas entra junto por ser o consumidor mais simples da mesma base — serve para
provar a camada antes de coisas maiores dependerem dela.

---

## Etapa 3 — Tempo ✓ FEITA

**Telas:** Calendário · Agendamento
**Tamanho:** médio
**Depende de:** Etapa 2

Entregue. A grade do mês junta compromisso, prazo de tarefa e data de
documento — os três gêneros com marca própria. O painel do dia traz os
compromissos, o que vence naquele dia e a nota do dia. Agendamento sugere os
horários que cabem, respeitando janela de trabalho, almoço e folga entre
compromissos.

O convite por e-mail que o wireframe prevê depende da Etapa 5: a tela diz
isso, em vez de oferecer um botão que não envia nada.

Aqui a planilha de vencimentos do plano original finalmente encontra o lugar
certo. As datas já saem por regra na classificação; falta ter onde pousar.

Prazo de contrato, compromisso e tarefa com data passam a viver na mesma grade.
Agendamento vem junto porque é a mesma base vista de outro ângulo — e porque
sugerir horário livre exige o calendário existir.

---

## Etapa 4 — Assinar ✓ FEITA

**Telas:** Certificado digital · Assinar documento
**Tamanho:** grande, e o mais delicado de todos
**Depende de:** Etapa 1 (assinar passa por aprovação)

O par de maior valor comercial para um escritório, e o de maior risco: mexe com
certificado ICP-Brasil, chave privada e validade jurídica. Assinatura errada não
é bug de interface.

Entregue. Assinatura PAdES com certificado A1 (.pfx / .p12), feita nesta
máquina — nada de serviço de assinatura no meio. O selo pode repetir em várias
páginas, e o programa diz em português que a assinatura continua sendo uma só,
cobrindo o documento inteiro: carimbar não assina.

**As duas decisões que o plano deixou em aberto, e como ficaram:**

*A1 primeiro, A3 depois.* Token exige driver PKCS#11 de cada fabricante. A tela
lista os certificados já instalados no Windows — inclusive dizendo quais são
ICP-Brasil — mas não oferece assinar por eles: a chave de um e-CPF instalado
quase sempre vem marcada como não exportável. Melhor mostrar o que existe e
explicar do que fingir um botão que não assina.

*Certificado de teste, dizendo o que ele é.* Dá para gerar um autoassinado e
conhecer a tela inteira. Ele assina de verdade do ponto de vista criptográfico
e **não tem validade jurídica** — e isso aparece no cartão do certificado, na
etiqueta do pedido na fila, na tela de confirmação, na tela de resultado e no
registro. Um programa que mostrasse só "assinado" nos dois casos enganaria
quem depende dele.

**O que o programa recusa fazer**, porque recusar é a resposta certa:

- assinar com certificado vencido
- proteger com senha um PDF que já tem assinatura — reescrever o arquivo
  apagaria a assinatura da outra parte
- sobrescrever o documento original: o assinado sai em arquivo novo
- afirmar que uma assinatura vale perante a ICP-Brasil; sem internet não dá
  para checar revogação nem a cadeia até a raiz, então o programa responde o
  que dá para afirmar offline — se o arquivo foi alterado depois de assinado,
  quem assinou e quem emitiu o certificado

A senha do certificado, quando guardada, fica protegida pela DPAPI do Windows —
amarrada à conta, nunca em texto no disco. Sem guardar, ela vive na memória
pelo prazo que a pessoa escolher.

Assinar não sai sozinho: a permissão vem desligada, e o pedido para na fila da
Etapa 1 com etiqueta de irreversível.

---

## Etapa 5 — E-mail ✓ FEITA

**Telas:** Contas de e-mail · Caixa de entrada · Novo e-mail
**Tamanho:** grande
**Depende de:** Etapa 1 (envio passa por aprovação)

A maior das etapas isoladas. O valor está na caixa de entrada que lê o e-mail,
detecta o prazo e sugere a resposta — não em ser mais um cliente de e-mail.

Entregue com IMAP e SMTP, e **sem OAuth**. A decisão é prática, não ideológica:
OAuth para Gmail ou Microsoft exige registrar aplicativo, publicar política de
privacidade, verificar domínio e passar por revisão de segurança — semanas de
espera e custo antes da primeira linha funcionar. IMAP com senha de aplicativo
funciona hoje, de graça, e é o que a hospedagem de um escritório brasileiro
oferece. Tudo isso sai da biblioteca padrão do Python: a etapa não trouxe uma
dependência nova.

O preço dessa escolha aparece na tela em vez de virar surpresa: a Microsoft
desativou entrada por senha no IMAP das contas Outlook e Microsoft 365, e o
programa avisa isso **antes** de a pessoa tentar e falhar. Para o Gmail, explica
onde gerar a Senha de app.

**Duas escolhas de arquitetura que decidem o resto:**

*A listagem lê cabeçalho, não mensagem.* Assunto, remetente, data e — pela
estrutura que o servidor descreve — se tem anexo. O corpo só é baixado quando
alguém abre aquele e-mail. É a promessa do rodapé ("leio só o que você abre") e
também é o que faz uma caixa com milhares de mensagens abrir em segundos.

*Prazo por regra, texto por modelo.* Rodar o modelo em cada mensagem que chega
custaria perto de um minuto por e-mail nesta máquina — a caixa de entrada
demoraria uma hora para abrir. Então o prazo sai por regra, instantâneo, já na
listagem; o rascunho de resposta só é escrito quando alguém pede. É a mesma
divisão que a classificação de documentos já usava.

Prazo detectado vira tarefa com um clique, e o remetente que já tem ficha nos
Cadastros aparece marcado como cliente.

**O que o programa recusa fazer:**

- enviar sem aprovação: a permissão vem desligada no programa *e* na conta, e
  o pedido para na fila da Etapa 1 marcado como irreversível
- guardar senha em texto — vai para a DPAPI, como a do certificado, e nunca
  volta para a tela, nem protegida
- guardar cópia das mensagens: elas ficam no servidor do escritório
- pôr assinatura inventada pelo modelo num e-mail — a assinatura é a da conta

**Achados durante a construção:**

- `getaddresses` devolve lista vazia para `a@b.com; c@d.com`. O ponto e vírgula
  fecha grupo na regra do e-mail, mas é o separador que o Outlook usa e que
  todo escritório cola no campo "Para". Um campo preenchido que não envia para
  ninguém é pior que um erro
- o Outlook manda travessão e aspas curvas em cp1252 declarando iso-8859-1,
  onde esses bytes são caracteres de controle: o assunto chegava com um
  caractere invisível no meio
- sondar oito candidatos de servidor em série levava dezesseis segundos, porque
  o tempo limite do socket não cobre a resolução de nome. Em paralelo: dois

---

## Etapa 6 — Escrita ✓ FEITA

**Telas:** Editor de texto · Pré-visualização · Planilha
**Tamanho:** grande
**Depende de:** nada — podia ser adiada sem travar as outras

A etapa que eu adiaria mais. Word e Excel já existem e o escritório já os usa; o
ganho aqui é o assistente escrevendo dentro do documento, não o editor em si.

Esse aviso continua valendo depois de pronta, e ele guiou onde o esforço foi:
**o editor é o suficiente para escrever; o valor está no que só existe aqui** —
o assistente escrevendo dentro do documento, os cadastros e a biblioteca do
lado, a conferência antes de o arquivo sair, e o caminho direto para assinar e
enviar, que as etapas 4 e 5 já construíram.

**Uma leitura, dois formatos.** O editor escreve HTML, porque é o que um campo
editável do navegador produz sem biblioteca nenhuma. Mas HTML não é o
documento: é a forma de digitar. O servidor lê isso uma vez e produz blocos, e é
dos blocos que saem tanto o PDF quanto o DOCX. Caminhos separados produziriam
dois documentos diferentes com o mesmo nome, e num contrato "a versão em Word
está diferente da versão em PDF" não é detalhe de formatação.

O PDF é o formato canônico: é o que a pré-visualização mostra — o arquivo de
verdade rasterizado, não uma aproximação em CSS — e é o que vai para a
assinatura. O DOCX existe para continuar no Word, e a tela diz isso.

**Conferir antes de sair** é tudo regra, nada de modelo: lacuna de modelo que
ficou (`_____`, `[  ]`), CPF e CNPJ com dígito verificador que não fecha, valor
com cifrão e sem número, e nome que aparece no texto sem bater com a ficha do
cadastro. Roda em milissegundos e a resposta é sempre a mesma — um aviso que
muda de opinião a cada leitura não serve para conferir contrato.

**A planilha fala português brasileiro de verdade**: ponto e vírgula separa
argumento, vírgula é decimal, funções com nome em português.
`=SE(C4="pago";0;B4*0,1)` é o que a pessoa já escreve no Excel dela. O
analisador é escrito à mão, não `eval`: fórmula chega de planilha que veio de
fora, e o pior que uma fórmula estranha pode fazer aqui é devolver `#NOME?` numa
célula. Referência circular vira `#CIRCULAR`, não travamento.

**O que ficou de fora, e por quê:**

*Citação de código de lei (CC, CPC, CP, CLT).* O programa não carrega o texto
das leis, e pedir o artigo a um modelo de 3 bilhões de parâmetros produziria
número de artigo plausível e errado dentro de um contrato. A tela diz isso e
oferece o que não tem esse risco: as cláusulas que o próprio escritório guarda.

*Controlar alterações no estilo do Word.* O que existe é o fluxo que o wireframe
destaca: a sugestão do assistente aparece, e você aceita ou descarta. Versões e
comparação entre elas cobrem o resto.

**Achados durante a construção:**

- quebra de linha entre tags do HTML é formatação, não conteúdo: tratá-la como
  texto criava um parágrafo vazio por linha do fonte, e o PDF saía com o dobro
  de espaço entre as cláusulas
- `R\$\s*(?![\d_])` aponta "R$ 12.000,00" como valor sem número: o `\s*` fora do
  lookahead volta atrás e casa com zero espaço. O espaço tem que estar dentro
- cabeçalho HTTP é latin-1, e título de documento brasileiro tem acento e
  travessão — baixar o PDF derrubava a rota com UnicodeEncodeError
- o FastAPI casa rota na ordem de declaração: `/api/documentos/{id}` engolia
  `/api/documentos/modelos` e devolvia 422

---

## Etapa 7 — O que precisa de história ✓ FEITA

**Telas:** Financeiro · Conexões · Relatórios · Foco e bem-estar
**Tamanho:** médio cada
**Depende de:** Etapas 2 e 3

Relatórios e Foco só existem depois que houver histórico acumulado — antes
disso, mostram gráfico vazio ou, pior, número inventado.

Entregue. Com ela o menu fecha: **20 telas de 20, todas com motor**.

Esta é a etapa em que inventar número era mais fácil e mais tentador — as
quatro telas mostram totais, médias e gráficos. A regra do manual ("número na
tela é número medido, sem placeholder, sem estimativa") virou o critério de
cada decisão, e os testes cobrem justamente isso: sem lançamento o painel dá
zero e diz que está vazio; média de dois recebimentos não vira "prazo médio";
sem medição ligada o relatório omite o tempo em vez de estimar.

**Financeiro.** Dinheiro em centavos inteiros, nunca em ponto flutuante: somar
0,1 + 0,2 em float dá 0,30000000000000004, e num extrato de honorários o erro
aparece depois de algumas dezenas de lançamentos. Saldo em caixa é o que
entrou menos o que saiu — dinheiro liquidado, não previsto; chamar de "saldo"
uma soma que inclui o que ainda não foi pago seria mostrar um caixa que não
existe. Cobrança atrasada vira rascunho de e-mail, que segue o caminho da fila.

Sobre a "permissão separada" que o plano previa: ela pertence a um PAULUS de
equipe, que não existe. Em vez de inventar uma senha local que qualquer um
contorna lendo o arquivo, a tela diz onde os números moram e que quem abre o
Windows com a sua conta vê o financeiro.

**Bem-estar.** O ponto delicado era o que medir. Para dizer "você está há duas
horas sem levantar" há dois caminhos: ler o teclado — que é um registrador de
teclas com outro nome — ou perguntar ao Windows quanto tempo faz desde o
último toque, sem saber qual foi. O módulo usa `GetLastInputInfo`, e há teste
verificando que ele não usa `GetAsyncKeyState` nem `SetWindowsHookEx`. O que
fica gravado é menos ainda: uma linha por dia com os totais. Não há linha do
tempo, e o teste confere as colunas da tabela.

**Conexões.** A única tela do programa que vai para a internet, e ela diz isso.
Abre uma janela presa a um endereço só, com sessão própria nesta máquina, e
prepara a conversa com número e texto pelo endereço que o próprio WhatsApp
publica. Não aperta enviar, não lê conversas: automatizar o WhatsApp Web
significa dirigir a tela de um site de terceiro — quebra a cada mudança de
layout, e o preço de errar é a conta do escritório ser derrubada. O wireframe
promete "eu digito e mostro; o envio só sai depois do seu sim"; é exatamente
isso, e nada além.

**Relatórios.** Não gera dado: lê o que as outras etapas produziram — tarefas
concluídas, lançamentos liquidados, documentos assinados, e-mails enviados,
versões gravadas, e a fila de aprovações. É a fila que torna "aprovei alguma
coisa ontem" conferível depois. O parecer em texto é a única parte que passa
pelo modelo, e sempre depois: ele recebe os números já apurados e escreve sobre
eles. Nunca calcula — erro de aritmética de um modelo de 3B viraria número
errado num parecer financeiro.

**Achado:** o teste de destinos afirmava que sempre existiria tela por
construir. Era verdade durante todo o caminho e deixou de ser aqui. O que tem
que valer sempre é a regra, não o estado: ou a tela abre algo, ou diz o que
falta — nunca as duas, nunca nenhuma.

---

## O que não muda em nenhuma etapa

As regras do manual valem para toda tela nova:

- **Vazio nunca é branco.** Mesmo cabeçalho, mesma grade; muda o conteúdo do
  cartão — uma frase dizendo o que falta e uma única ação que resolve.
- **Erro é faixa no topo**, em português, com saída. Nunca modal, nunca some
  sozinho.
- **Efeito externo passa por aprovação.** Sem exceção.
- **Número na tela é número medido.** Sem placeholder, sem estimativa
  disfarçada de fato.
- **Toda ação é reversível ou registrada**, e o rodapé diz onde o dado está.
