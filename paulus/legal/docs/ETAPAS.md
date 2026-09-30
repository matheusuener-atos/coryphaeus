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
| Editor de texto | HTML → blocos → PDF e DOCX pelo mesmo caminho; página medida no próprio PDF |
| Planilha | analisador de fórmula escrito à mão, em português brasileiro; ordenar move a fórmula com a linha |
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

---

# Segunda parte — fechar a distância para o wireframe

As sete primeiras etapas puseram motor nas vinte telas. Esta segunda parte
fecha o que a [comparação com os wireframes](COMPARACAO.md) apontou, e faz o
que antes tinha sido decidido não fazer.

**A mudança de posição está registrada de propósito.** Seis itens foram
declinados nas etapas 1 a 7, cada um com um motivo escrito. Nenhum daqueles
motivos era "é impossível" — eram "custa mais do que vale agora" ou "erraria
de um jeito perigoso". A decisão passou a ser fazer, e o que muda é que agora
cada um vem com o caminho que resolve o motivo original, não passando por
cima dele:

| Declinado antes | O motivo era | O caminho agora |
|---|---|---|
| ~~Citar CC, CPC, CP, CLT~~ ✓ | O modelo inventaria o número do artigo | Feito na Etapa 11: 4.530 artigos no disco. Citar virou consulta, não palpite |
| Token A3 | Driver PKCS#11 por fabricante | A pessoa aponta a DLL do próprio token, uma vez |
| OAuth de e-mail | Semanas de revisão da Google | A credencial é do escritório, não nossa: cada um cria a sua |
| Enviar no WhatsApp | Dirigir a tela de um site quebra e derruba a conta | Caminho oficial pela Cloud API; o assistido fica como segunda opção, com aviso |
| Equipe e permissões | Não havia mais de uma pessoa | Perfis nesta máquina, com papéis e regras de aprovação |
| Plano e cobrança | Não havia o que cobrar | Licença assinada, conferida sem servidor |

A ordem abaixo é por quanto muda o dia de quem usa, não por tamanho.

---

## Etapa 8 — A forma das telas ✓ FEITA

**Telas:** Tarefas · Calendário · Agendamento
**Tamanho:** médio
**Depende de:** nada

As três diferenças estruturais que a comparação achou. Não é acabamento: numa
tela de 900 px, o painel do dia do Calendário fica abaixo da dobra, e o detalhe
da tarefa empurra a lista para fora da vista. A forma é o que faz a tela
servir para trabalhar.

- Tarefas em três colunas: filtros e listas · lista · detalhe
- Calendário com o mês à esquerda e o dia à direita
- Agendamento com a semana em grade, dias em colunas
- Fim de semana esmaecido, e o contador do cabeçalho em cada uma

Sai daqui um componente de três colunas reaproveitável — as três telas pedem a
mesma forma, e três implementações da mesma coisa divergem em uma semana.

Entregue. Tarefas ganhou a coluna de listas com contagem, "Lembrar-me",
"Repetir" — que é comportamento, não rótulo: concluir uma tarefa que repete já
deixa a próxima com o prazo andado — e "Ligado a", pelo SHA-1 do documento.
Calendário e Agendamento ganharam Mês/Semana/Agenda e Semana/Dia/Lista, com a
semana em grade de hora, fim de semana esmaecido, e clicar numa hora vazia já
abre o formulário naquele horário. O painel do dia recebeu as tarefas com caixa
de marcar e o convite de reunião, que sai pela conta de e-mail da Etapa 5.

**Achado:** `.hoje { margin-top: 22px }`, escrita para o bloco "Decidido hoje"
das Aprovações, vazava para qualquer elemento marcado como "hoje". A célula de
hoje do calendário andava 22 px para baixo desde a Etapa 3, e o cabeçalho da
semana quebrava em duas linhas. Classe genérica com layout dentro é a forma
mais silenciosa de uma tela estragar outra.

---

## Etapa 9 — Encontrar e agir em lote ✓ FEITA

**Telas:** Biblioteca · Cadastros
**Tamanho:** médio
**Depende de:** Etapa 8

Com 128 documentos a lista basta; com 1.200 ela é um problema. Falta a camada
de achar e de agir em muitos de uma vez.

- Busca por nome, pasta ou trecho, com atalho de teclado
- Filtros de fixados e sem análise, e ordenação
- Seleção múltipla com barra de ações: assinar, mover, fixar, exportar, apagar
- Ações por documento: tomar vista de novo, perguntar sobre este, apagar
- Nos Cadastros: busca, ordenação, e quanto cada cliente tem em aberto

Mover em lote e apagar em lote passam pela fila, como todo efeito externo.

### O que entrou

`src/acervo.py` e uma tabela no lugar da lista: **nome e pasta · modificado ·
análise**. A busca vai ao servidor porque procura no **texto dos documentos**,
e o texto não está no navegador — quem lembra "aquele contrato que falava em
cessão de direitos hereditários" não lembra o nome do arquivo. Quando o achado
vem do conteúdo, o trecho aparece embaixo da linha: sem isso o documento surge
na lista e quem procurou não sabe por quê. `Ctrl K` cai no campo.

A análise tem três estados, e a diferença entre dois deles é o ponto:
**sem análise** é trabalho que não foi feito; **mudou desde então** é trabalho
que foi feito e não vale mais. Confundir os dois faz citar o documento pela
versão velha. O "quando" só aparece quando está medido — documento analisado
antes de existir esse registro mostra "analisado" e mais nada.

Fixado fica guardado por SHA-1, para mover ou renomear não apagar a marca, e
sobe sempre na ordenação.

Em lote: tomar vista de novo, mover, fixar, exportar, apagar. **Mover, apagar
e exportar viram pedido na fila**, com o plano inteiro à vista antes do sim —
um erro em lote é um erro multiplicado. O plano de mover nunca escolhe um nome
que já existe no destino, e o que não dá para mover sai contado com o motivo.
Apagar só age dentro da pasta do programa, e confere de novo na hora.

Nos Cadastros: os tipos viraram fichas com a contagem, ordenação por A–Z, em
aberto ou atraso, e a coluna **em aberto** com o atraso ao lado — o número que
decide quem ligar primeiro. Sai de uma consulta só para a lista inteira. Quem
não deve nada ganha um travessão, não um "R$ 0,00".

### Dois bugs que a verificação achou

**A biblioteca escondia documento.** O cache de extração é por SHA-1 e
devolvia o *mesmo objeto* para arquivos iguais byte a byte; o laço trocava o
caminho e o nome dele e o guardava duas vezes. Resultado: `contrato (1).pdf`
aparecia duplicado e `contrato.pdf` sumia da lista. Num escritório, dois
arquivos com o mesmo conteúdo são o caso comum.

**E o lote agia sobre o que não foi marcado.** Pela mesma razão: a seleção era
por SHA-1. Pedir para apagar 2 documentos montou um pedido com 4. A linha
passou a ser identificada pelo caminho; fixar continua indo por SHA-1, que é
onde a identidade é mesmo o conteúdo.

---

## Etapa 10 — O escritório por dentro ✓ FEITA

**Tela:** Financeiro
**Tamanho:** grande
**Depende de:** Etapa 2

Quatro blocos inteiros do wireframe, e é a tela com mais coisa pendente.

- Folha de pagamento: pessoas, salários, encargos, estagiários, recibos
- Documentos e comprovantes do mês, com arrastar-e-soltar
- Notas fiscais — registro do que foi emitido, não emissão
- Boletos — acompanhamento de vencimento, não geração
- Contratos concluídos do mês
- Seletor de mês, exportar, e o fechamento em N dias

A distinção que o próprio wireframe faz continua valendo: a emissão da nota é
da prefeitura e o boleto sai do banco. Aqui se controla e se guarda.

### O que entrou

`src/escritorio.py`, seis blocos novos na tela e um seletor de mês com o
"fechamento em N dias" — que é o último dia do mês menos hoje, não um prazo
inventado.

**A folha é cópia, não cálculo.** Quem entra é quem tem vínculo definido no
cadastro — sem vínculo a pessoa não entra, porque não foi dito como ela é paga,
e uma folha por um valor que ninguém digitou sai errada com cara de certa. O
valor de cada pessoa fica gravado no mês: aumentar o salário hoje não reescreve
agosto. Estagiário conta separado de salários, porque bolsa não é salário.
"Gerar recibos" sai um PDF por pessoa, com a natureza certa do pagamento —
"bolsa de estágio", "pró-labore", "salário" — e avisando que sai sem
assinatura, que é da tela de assinar.

**Comprovantes** com arrastar-e-soltar, guardados por mês na pasta do programa
e ligados ao lançamento. O que falta sai contado: despesa paga sem comprovante.

**Nota fiscal e boleto são registro.** A emissão continua na prefeitura e o
boleto continua saindo do banco. O que dá para fazer com verdade aqui é guardar
número, valor e data — e mostrar o que foi recebido e ainda não tem nota
anotada, que é a diferença entre duas listas, não uma pendência inventada.

**Contrato concluído não é um campo.** Sai dos lançamentos: cliente que recebeu
neste mês e não tem mais nada em aberto. Abrir uma cobrança nova tira o cliente
da lista sozinho — um campo "encerrado" seria uma segunda verdade, e a errada é
sempre a que ninguém lembrou de atualizar.

**Exportar** o mês numa planilha com três abas, para quem faz a contabilidade.
Valores vão como número: planilha que chega com "R$ 1.200,00" em célula de
texto não soma do outro lado, e o contador soma.

### Um bug que a verificação achou, e dois acertos de UI

**Duas funções com o mesmo nome.** `blocoComprovantes` já existia dentro da
ficha de lançamento quando nasceu outra com o mesmo nome no bloco novo. O
JavaScript fica com a última, calado: o bloco simplesmente não aparecia, sem
erro no console. Num arquivo de oito mil linhas isso vai acontecer de novo —
agora há um teste que compara os nomes das 248 funções da página.

**`.cresce` não crescia.** A classe é usada em dezenas de linhas esperando
`flex: 1`, e só tinha regra dentro de `.acervo-cortes`. Nas outras telas o texto
encolhia até virar reticências com espaço vazio sobrando na linha —
"Impostos · DAS" aparecia como "Im…".

**"6 pessoa(s)" ninguém escreve.** Um ajudante de plural nos dois lados, usado
em toda a tela do Financeiro. O resto da aplicação ainda tem 57 ocorrências de
"(s)" — é uma varredura mecânica, separada desta etapa.

---

## Etapa 11 — A lei em casa ✓ FEITA

**Telas:** Editor de texto · Configurações
**Tamanho:** grande
**Depende de:** Etapa 6

A que desfaz a primeira decisão. Citar artigo de lei era perigoso porque o
número sairia de um modelo de 3 bilhões de parâmetros — plausível e errado
dentro de um contrato.

O caminho não é confiar mais no modelo: é **tirar o modelo do caminho**. Texto
de lei é público e não tem direito autoral (Lei 9.610, art. 8º, IV). Um
importador busca o texto oficial no Planalto uma vez, guarda em base local, e a
partir daí citar é consulta a um índice — com o texto do artigo do lado, para
conferir.

- Importador de CC, CPC, CP e CLT, com data da captura registrada
- Busca por número de artigo e por palavra
- Inserir citação no editor, com o texto do artigo à vista
- Conferir prazos do documento contra os prazos da lei

Enquanto o texto não estiver no disco, a tela diz isso — nunca chuta o artigo.
Jurisprudência e súmulas ficam para depois: não têm fonte oficial em formato
aberto do mesmo jeito, e inventar acórdão é pior que inventar artigo.

### O que entrou

`src/leis.py` lê o HTML compilado do Planalto e guarda artigo por artigo.
**4.530 artigos** nesta máquina: CC 2.082 (1º–2.046), CPC 1.074 (1º–1.072),
CLT 984 (1º–922), CP 390 (1º–361). Sem repetição e sem buraco de numeração nos
quatro.

Ler a lei é quase todo o trabalho, porque quase tudo no arquivo parece artigo e
não é. O que o leitor precisou aprender, cada item com teste:

- os artigos antes do primeiro título são do **decreto que aprova** o código, e
  não do código. A CLT começa em "Art. 1º Fica aprovada a Consolidação"
- as disposições finais **citam artigos de outras leis**. O CPC escreve
  "Art. 48. Caberão embargos..." dentro do seu art. 1.064, e isso é da Lei dos
  Juizados. O CPC tem art. 48 próprio, do foro do inventário — o citado não
  pode tomar o lugar dele
- **"Art. 58 - A duração normal"** é o artigo 58. A CLT e o Código Penal, dos
  anos 40, separam número e texto com " - ", e o hífen do sufixo tem que estar
  colado para "58-A" continuar sendo outro artigo
- o sufixo vale **inteiro**: 359-M-A fica entre o 359-M e o 359-N, não depois
- **revogado é o artigo, não o inciso**. O art. 3º do Código Civil teve só os
  incisos revogados; dizer que ele não existe seria pior que não ter a busca
- **frase não é cabeçalho**. "Livro II da Parte Especial deste Código." começa
  com a palavra mas é texto — lida como cabeçalho, mandava quem conferisse a
  citação para um trecho que não tem nada a ver
- o **rótulo de alteração vem do caput**. O art. 121 do Código Penal é de 1940;
  foi o § 2º-A que a Lei 13.104/2015 incluiu

Na tela: botão "Citar a lei" na barra do editor e no painel de cláusulas, busca
por número ou palavra, filtro por código, e o texto do artigo à vista antes de
inserir. Artigo revogado só entra com confirmação explícita. Em Configurações,
importar de uma pasta de uma vez, com o relatório do que ficou de fora e por
quê.

Conferir prazos do documento contra os prazos da lei estava marcado para a
Etapa 12 e **não entrou**: o programa não carrega o texto das leis, e um prazo
conferido contra artigo lembrado de cor pelo modelo é pior que prazo nenhum —
a pessoa confia e não confere. Volta quando houver fonte de lei de verdade
nesta máquina, que é o assunto desta etapa aqui.

---

## O documento aberto dentro da conversa ✓ FEITA

**Telas:** Conversa · Editor de texto
**Tamanho:** grande
**Fora da numeração:** veio de dois wireframes que faltavam — "Chat com
editor" e a citação aberta na conversa

Duas coisas que o programa dizia e não mostrava.

### Abrir um documento abre ele ao lado

Pedir *"abra a procuração Matheus"* devolvia o texto transcrito dentro da
resposta — não dá para editar, ocupa a conversa inteira, e no fim o modelo
ainda ensinava a clicar em botões que não existem.

Agora abre a tela dividida: conversa à esquerda, documento à direita,
editável. O cartão oferece as duas leituras de "abrir" — trazer para cá como
rascunho ou abrir no Windows. Abrir aqui cria uma **cópia**: o arquivo de
origem pode já ter sido assinado, enviado ou protocolado.

A alteração pedida na conversa cai **dentro** do documento, marcada, com
"Descartar / Manter" logo abaixo do parágrafo que mudou. Cada turno guarda o
documento inteiro de antes, e é isso que o "Desfazer" devolve.

### O trecho citado, na página onde está

"3 arquivos citados" era um texto que a pessoa lia e acreditava. Conferir
exigia abrir o PDF por fora, achar a página e procurar o parágrafo com o olho.

`src/citacao.py` procura a frase dentro do PDF e devolve em que página está e
onde marcar, em fração da página — assim a marca acompanha o zoom sem
recalcular nada. A página é o PDF rasterizado, não uma aproximação em HTML.

Com um pedaço só de agulha, **12 de 14** trechos eram localizados; as falhas
eram descasamento bobo entre o texto extraído e o texto interno do PDF — um
espaço antes da vírgula, uma linha de assinatura em underscores. Tentando
quatro pontos do trecho em dois tamanhos: **14 de 14, em 0,3 s**.

**"Por que este trecho"** é a única parte que não copia o wireframe, e de
propósito. Lá o painel traz uma explicação escrita, que teria que sair do
modelo e viraria mais uma afirmação para conferir. Aqui mostra **quais
palavras da pergunta aparecem naquele pedaço**, contadas.

Duas honestidades que o wireframe não precisava ter: **DOCX e TXT não têm
página para desenhar**, e a tela diz isso em vez de fingir uma; e quando o
trecho não é localizado, **mostra a página sem marca** e explica — destacar o
parágrafo errado é pior que não destacar, porque a pessoa confere e acredita.

### E o modelo parou de falar da tela

Ele escreveu *"Você pode editar este documento clicando nos botões 'Editar' ou
'Copiar' e 'Colar'"* — botões que não existem em lugar nenhum. A instrução
agora diz: nunca dizer onde clicar, nunca citar botão, menu ou atalho. Quem
explica a tela é o programa, que sabe quais botões existem.

Junto: o modelo devolvia **o documento de volta** em pedido amplo sem trecho
selecionado, e o texto entrava no fim dobrando o documento — 355 palavras
viraram 712, calado. Agora a resposta que é cópia é recusada com uma saída
útil.

---

## A janelinha dos bastidores ✓ FEITA

**Tela:** Conversa
**Tamanho:** pequeno
**Fora da numeração:** veio do uso — *"quero essa parte mais dinâmica, como se
realmente estivesse pensando"*

O cartão de progresso mostrava uma barra em **25/25** durante os oitenta
segundos de espera. Não era progresso: os dois números chegavam juntos, e a
barra nascia cheia. O resto do tempo, nada se mexia.

O que acontece naquele silêncio tem nome — o modelo está **lendo** o prompt
inteiro antes da primeira palavra, e o Ollama não emite nada nessa fase. Então
não há progresso a relatar, mas há o que dizer: o tamanho do que está sendo
lido, e quanto leituras desse tamanho levaram *neste computador*.

A janelinha mostra uma linha por coisa que aconteceu:

```
O QUE ESTOU FAZENDO                                        27 s
  0,0 s  procurei nos 6 documentos abertos · vou usar 25 trechos de 6
  0,1 s  mandei 21.178 caracteres para o llama3.2:3b, janela de 16.384 tokens
  0,1 s  aqui, leituras deste tamanho levaram ~72 s (mediana de 4 leituras)
  agora  lendo… 38 s de ~72 s  ▓▓▓▓▓▓▓░░░░░
  9,1 s  primeira palavra saiu · esperei 9,1 s até aqui
  agora  escrevendo… 52 palavras · 1,8 por segundo
 93,0 s  pronto · o modelo gastou 6,1 s lendo 7.095 tokens e 83,9 s escrevendo 266
```

`src/ritmo.py` guarda as últimas 25 leituras, **por modelo**: a mesma máquina
lê em velocidades diferentes com Q4 e Q8, e uma média dos dois não descreveria
nenhum. Sem histórico, a janelinha diz *"ainda não medi leituras deste modelo
nesta máquina"* e a barra fica indefinida — nada de porcentagem fingida.

Nada é escrito para parecer ocupado. Quando não há o que dizer, a janelinha
fica quieta e só o relógio anda.

### Quatro coisas que a tela dizia errado

| dizia | era |
|---|---|
| "25 / 25" desde o primeiro instante | os dois números chegavam juntos |
| "leu tudo em 0 s" com 7.092 tokens | cache de prompt do Ollama, agora declarado |
| "terminou de ler em menos de 0,1 s" após 9 s parada | o relógio começava depois do `POST`, que só volta quando o Ollama responde |
| duas perguntas seguidas: linhas da segunda no painel da primeira | dois `id` iguais no DOM |

---

## Ele passa a ler todos os arquivos ✓ FEITA

**Telas:** Conversa
**Tamanho:** médio
**Fora da numeração:** veio de uma observação de uso — *"tenho a sensação de
que ele não olha corretamente todos os arquivos"*

A sensação estava certa, e o problema era pior do que parecia. Medido nesta
máquina, mesma pergunta, mesmo modelo:

| contexto lido | tempo | outorgados achados |
|---|---|---|
| 6.000 caracteres (era o padrão) | 56 s | **0 de 4** |
| 21.382 caracteres (o acervo inteiro) | 95 s | **4 de 4** |

Quatro causas, todas medidas antes e depois.

**A janela do modelo era fixa e pequena.** `num_ctx` em 8.192 e orçamento de
leitura de 6.000 caracteres — um quarto do acervo. Agora a janela acompanha o
acervo: 24 mil caracteres pedem 16.384, com teto de 32.768 por causa da
memória. Cabendo tudo, lê tudo.

**O montador do contexto largava documentos de fora, calado.** Enchia com os
primeiros até estourar o limite, e dois dos seis nunca chegavam ao modelo — que
respondia sobre o acervo tendo visto dois terços dele. Agora reparte entre
todos; não cabendo nem assim, **nomeia quem ficou de fora**, porque o modelo
precisa saber que não viu tudo.

**A instrução entregava uma saída de emergência.** Sete regras numeradas, e a
de número 3 dava a frase pronta: *"se a resposta não estiver nos trechos, diga
exatamente: Não encontrei essa informação"*. Um modelo de 3 bilhões de
parâmetros usa isso cedo demais. Mesmos documentos, mesmo modelo, só trocando
a instrução: das seis informações perguntadas, a antiga achou **uma** e a nova
achou as **seis**. Numa delas a antiga desistiu em 8 segundos — a resposta
estava escrita no primeiro documento.

A trava contra invenção não saiu junto: num programa jurídico, inventar
cláusula ou número é o dano que nenhum ganho de leitura paga. Verificada com
quatro perguntas sem resposta óbvia — três recusas corretas, e uma que eu tinha
suposto impossível e estava na cláusula 9ª, achada e citada certo.

**"Abra a procuração Matheus" não é pergunta.** É pedido para abrir um arquivo
que existe, com esse nome, e ia para a busca — que respondia "não encontrei
essa informação" sobre ele. Agora vira proposta, e só quando o arquivo existe e
é um só: com quatro procurações no acervo, *"abra a procuração"* continua sendo
pergunta, porque escolher uma seria sortear.

### Sobre o Ministral 3B

Instalado e verificado a pedido: `alibayram/ministral-3b-instruct`, 3,3 B em
Q8_0. **Não dá para usar.** Nas mesmas três perguntas, llama3.2:3b acertou 3 de
3 em 4,6 s de média; o ministral acertou 0 de 3 em 15,4 s, respondendo em
inglês, vazando `<|im_start|>` e degenerando em repetição. Testados os três
formatos de prompt — ChatML, Mistral `[INST]` e texto puro: todos quebram. Não
é o template; o GGUF desse empacotamento está corrompido.

---

## A conversa passa a entender o pedido ✓ FEITA

**Telas:** Conversa · Aprendizado
**Tamanho:** médio
**Fora da numeração:** apareceu de um uso real, não do wireframe

Pedir *"anote uma reunião no calendário 11/09/2026 às 13:40 com lembrete 10
minutos antes"* fazia o programa procurar a palavra "reunião" dentro dos
contratos e responder *"não encontrei essa informação nos trechos
fornecidos"* — resposta correta para a pergunta errada. A conversa tinha um
caminho só: toda mensagem virava busca nos documentos. O escritório tem
agenda, tarefas, financeiro e códigos de lei, e a conversa não alcançava nada
disso.

`src/intencao.py` lê a frase antes de sair procurando. Por regra, não por
modelo: reconhecer "anote" seguido de uma data é instantâneo e repetível, e
perguntar a um modelo de 3 bilhões de parâmetros o que a pessoa quis dizer
custaria um minuto e erraria de formas imprevisíveis.

**Entender não é fazer.** O que volta é uma proposta com os campos à vista —
título, data, hora, aviso — e quem grava é a pessoa. Nada entra no calendário
de alguém por interpretação de frase.

O erro caro é o contrário, e é ele que os testes perseguem: pergunta virando
compromisso. Duas regras seguram isso — o verbo tem que ser palavra inteira
("tem alguma reunião **marcada**" não é ordem) e tem que estar no começo da
frase ("o contrato **marca** reunião de diretoria?" é pergunta). Sem data, o
compromisso não é marcado para hoje por conta própria: a proposta diz o que
falta.

**E o programa passou a saber se descrever.** *"O que você sabe fazer?"* é
respondido em menos de um segundo, sem modelo, da lista de telas e do registro
de habilidades — que são declarações do próprio código. Um texto escrito à mão
envelheceria na primeira tela nova.

### Três coisas que o programa dizia errado sobre si

**Duas habilidades se declaravam "ainda não existe"** quando as telas
correspondentes foram entregues nas Etapas 4 e 6. Assinar existe, com
certificado A1; redigir com o assistente existe, no editor. O que não existe é
pedir essas duas *pela conversa* — e agora é isso que a declaração diz.

**"Escritorio" sem acento** no nome do grupo do menu, visível na barra
lateral desde sempre.

**Trinta e seis conversas vazias.** Entrar em "Organizar pastas" criava um
trabalho antes de a pessoa escolher qualquer coisa; cada visita deixava uma
"Organizar uma pasta" sem nada na lista. A conversa passou a nascer quando a
varredura começa, que é quando existe trabalho.

### Varredura de plural

As 57 ocorrências de "(s)" da aplicação viraram plural de verdade — "6
pessoas", não "6 pessoa(s)". Um ajudante em cada lado, e os adjetivos que
concordam junto ("3 documentos abertos", "2 despesas pagas").

---

## Etapa 12 — Escrever melhor ✓ FEITA

**Telas:** Editor de texto · Planilha · Pré-visualização
**Tamanho:** grande
**Depende de:** Etapa 11

O critério desta etapa foi o mesmo do resto do projeto: *o editor em si o Word
já faz*. O que entrou é o que o Word **não** faz para quem redige contrato no
Brasil — e o que a tela dizia e não podia provar.

### Numerar cláusulas e qualificar as partes

Renumerar leva as **referências cruzadas** junto. É a metade do trabalho que
costuma ficar para trás, e é ela que gera a cláusula 7 citando a cláusula 4
depois que a 4 virou 5.

"Conforme cláusula 2" no meio da frase não é título de cláusula. Sem essa
distinção o contrato saía numerado 1, 2, 3, 4 e **6** — aconteceu. E ordinal
por extenso com acento ("DÉCIMA SEGUNDA") não casava, porque a expressão tinha
sido montada só com as formas sem acento.

A qualificação sai do cadastro. O que o cadastro não tem vira `[ESTADO CIVIL]`
no texto, nunca invenção, e a tela diz o que falta **antes** de inserir —
completar em Cadastros agora é mais barato que caçar colchete depois.

### A página deixa de ser estimativa

O editor dizia `páginas ~4`: palavras divididas por 450. Erra em todo documento
com título, lista ou parágrafo curto, e erra mais quanto maior o documento —
justamente quando a pessoa precisa saber. O manual deste projeto diz que número
na tela é número medido, e esse não era.

Agora quem conta é o próprio PDF sendo montado, o mesmo arquivo que a
pré-visualização desenha: **10 a 53 ms** nos contratos deste escritório. Barato
o bastante para rodar 700 ms depois da última tecla.

Com medida no lugar de estimativa, dá para fazer o que estimativa não permite:
as quebras de página aparecem **desenhadas na folha**, na linha certa, e a
régua diz em que página o cursor está. Conferido contra o arquivo: a página 2
do PDF começa em "Parágrafo Único: O presente contrato tem como OBJETO", que é
onde a linha está.

O parágrafo que atravessa a quebra continua no mapa. O reportlab parte
parágrafo grande em dois, e os pedaços novos não herdam nada de quem os gerou;
sem repassar a marca na divisão, sumia do mapa justamente o parágrafo sobre o
qual a pergunta é interessante.

A linha de quebra é desenhada **por cima** da folha, nunca dentro: o que está
dentro do `contenteditable` acaba no contrato gravado.

### A folha: fonte, corpo, recuo, entrelinhas

Por documento, e não por escritório — petição e contrato pedem recuos
diferentes, e quem escreve os dois no mesmo dia não pode trocar configuração
entre um e outro. Chega ao PDF **e** ao DOCX.

O que o PDF não sabe produzir volta ao padrão em vez do mais parecido: "quase o
que você pediu" é a resposta que ninguém consegue conferir.

A folha na tela passou a ser desenhada na escala do PDF — margem de 11,9% da
largura, que são os 2,5 cm de verdade, e corpo proporcional. Antes eram 48 px e
15 px fixos: escolher corpo 13 não mudava nada na tela.

De quebra, PDF e DOCX passaram a sair na mesma fonte. Saíam em Times e Georgia
porque eram os padrões de cada biblioteca, e ninguém tinha decidido isso.

### Quadro dentro do documento

Quadro de parcelas, de honorários, de bens. Era o que fazia o contrato sair do
Word: aqui não havia como montar um.

A célula guarda texto puro — negrito dentro de célula de quadro não aparece em
contrato, e o que importa é o texto chegar inteiro aos dois formatos. Linha em
branco no meio do quadro **fica**: a pré-visualização promete ser o arquivo, e
uma linha que aparece no editor e some do PDF quebra a promessa.

### Controlar alterações

O Word marca cada tecla enquanto se digita. Aqui a marca vem da comparação com
uma versão gravada, e não de interceptar a digitação: interceptar tecla dentro
de um campo editável é o caminho curto para perder texto de contrato, e texto
de contrato perdido não tem conserto do lado de cá.

O resultado é o que interessa — o que entrou, o que saiu, o que mudou, e o
caminho de volta para cada um, um a um.

A comparação passou a separar duas coisas que o `difflib` junta: apagar uma
cláusula e escrever outra no lugar não é "esta cláusula mudou". A tela dizia
*"a cláusula do foro virou a cláusula da multa"*, e quem lê isso para decidir o
que aceitar é enganado. O corte é por palavra, e o número saiu de medir
parágrafos daqui: edição de verdade entre **0,60 e 0,83**, parágrafo trocado
por outro entre **0,00 e 0,33**. Por letra não daria — "Nome: ______" e
"CPF: ______" dão 0,74, porque o que eles têm em comum é o sublinhado.

### Notas na margem

A conferência já sabia apontar o parágrafo, mas dizia isso numa lista à parte —
quem lia tinha que achar o parágrafo com o olho. Agora a marca fica ao lado da
linha.

Duas origens, e a tela diz qual é qual: **regra** (o que `conferir` acha,
instantâneo e sempre igual) e **assistente** (o que o modelo comentou quando
pediram). O comentário do modelo é observação para conferir, não texto para
entrar no contrato — e o trecho é obrigatório, porque comentário sobre "o
documento" não gruda em lugar nenhum.

A âncora é o **texto** do parágrafo, não o número dele. Número muda toda vez
que alguém insere uma linha acima, e o comentário passaria a apontar para o
parágrafo errado, calado.

### Planilha: responder sobre a tabela

Selecionar uma célula respondia "quanto é esta?". A pergunta que se faz a uma
tabela de parcelas é outra — e para respondê-la entraram seleção em retângulo,
resumo da seleção (com **quantas estão vazias**: uma vazia no meio de uma coluna
muda a média, não muda a soma, e isso não se vê olhando), bordas e formato na
seleção inteira, congelar, ordenar, filtrar, juntar células e gráfico.

Ordenar leva a linha inteira **e a fórmula da linha**: `=B7*0,1` na linha 7 vira
`=B9*0,1` quando a 7 vai para a 9. Ordenar só a coluna escolhida embaralha a
tabela — o valor da linha 7 passa a valer para o cliente da linha 3 — e o
estrago não aparece olhando, cada célula continua plausível.

Filtrar não grava nada: filtro é jeito de olhar. Filtro gravado esconderia
linhas de quem abrisse o arquivo depois sem saber que há filtro. O aviso de
filtro ligado fica na tela o tempo todo.

Juntar células não cobre conteúdo. O Excel junta e joga fora o que estava
debaixo, avisando numa caixa que todo mundo clica em OK sem ler.

### Pré-visualização

Duas páginas lado a lado, tela cheia, imprimir (o PDF de verdade indo para a
impressora, não a tela impressa), comparar versões — a lista do que mudou **e**
as duas folhas desenhadas, porque só a lista não mostra como ficou e só as
folhas não dizem o que procurar — e o timbre do escritório no PDF, desligado
por padrão: minuta interna com timbre parece peça protocolada.

### Três erros que só apareceram com a tela pintada

**O PDFium derrubando o servidor.** É uma biblioteca em C e não é segura para
duas threads ao mesmo tempo; o FastAPI atende rota `def` num pool de threads.
Enquanto a tela pedia uma página de cada vez, ninguém viu nada. A comparação
passou a mostrar duas folhas, dois `<img>` saíram juntos e o processo morreu com
`access violation reading 0x2C` — sem traceback da aplicação, só dois 500 na
tela. Todo acesso passa agora por `src/leitor_pdf.py`, um de cada vez.

**`=SOMASE(B1:B4;">1000")` somava a coluna inteira.** 13.700 onde o certo era
13.200; `"<1000"` devolvia zero. O critério chega sempre como texto, e a
comparação caía no ramo de texto: letra a letra, `"500" > "1000"` é verdadeiro,
porque "5" vem depois de "1". A célula mostrava um número plausível, que é a
pior forma de errar valor — ninguém confere planilha somando de cabeça.

**O modelo assinando arquivo que não existe.** A sugestão do editor vinha com
`Arquivo: contrato.txt` na frente, com o nome inventado. O prompt de sistema
mandava citar a origem de cada informação — regra do acervo — enquanto a
instrução do editor pedia só o texto. Duas ordens opostas, e o modelo obedecia
as duas. O editor passou a ter instrução de sistema própria.

**Fica para depois:** ver o documento e a planilha lado a lado, e o editor
abrindo DOCX de terceiro sem passar pelo Word.

**Não entrou, e não foi esquecimento:** conferir os prazos do documento contra
os prazos da lei, que a Etapa 11 tinha deixado para cá. O programa não carrega
o texto das leis, e um prazo conferido contra artigo que o modelo lembrou de
cor é pior que prazo nenhum — a pessoa confia e não confere. Volta quando
houver fonte de lei de verdade nesta máquina, que é o assunto da Etapa 11.

---

## Etapa 13 — Assinar com token, entrar com a conta

**Telas:** Certificado digital · Contas de e-mail
**Tamanho:** médio
**Depende de:** Etapas 4 e 5

Desfaz duas decisões de uma vez, e as duas pelo mesmo princípio: o que faltava
não era código nosso, era uma credencial que pertence ao escritório.

- **Token A3**: a pessoa aponta a DLL PKCS#11 do fabricante do próprio token,
  uma vez. O programa lista os certificados do token e assina por ele
- **OAuth de e-mail**: cada escritório cria a própria credencial no Google ou
  na Microsoft e cola aqui. Não somos nós pedindo revisão para milhares de
  usuários — é um aplicativo do escritório, para o escritório
- Estado por conta: sincronizado há quanto tempo, senha recusada, reconectar
- Assinatura por conta, e o registro de acessos

---

## Etapa 14 — WhatsApp de verdade

**Tela:** Conexões
**Tamanho:** médio
**Depende de:** Etapa 7

Desfaz a decisão mais delicada. O motivo original continua sendo verdade:
dirigir a tela do WhatsApp Web quebra a cada mudança de layout, e o preço de
errar é a conta do escritório suspensa. O caminho não é fingir que o risco
sumiu — é oferecer o caminho que não tem esse risco primeiro.

- **Cloud API oficial**: número do escritório cadastrado na Meta, envio por
  requisição documentada, sem tela nenhuma para dirigir. É o caminho que a
  própria WhatsApp oferece para isso
- **Envio assistido** na janela embutida, como segunda opção, com o aviso do
  risco escrito na tela e desligado por padrão
- Navegador dentro da tela, com endereço travado
- Encerrar sessão sem apagar os dados

Envio, nos dois caminhos, passa pela fila de aprovação.

---

## Etapa 15 — Escritório com mais de uma pessoa

**Telas:** Configurações · Aprovações · Tarefas
**Tamanho:** grande
**Depende de:** Etapa 8

A terceira decisão desfeita. Ela dependia de existir mais de uma pessoa; passa
a existir.

- Perfis nesta máquina, com nome, OAB e papel — sócio, advogado, estagiário
- Quem vê o financeiro, quem pode assinar, quem pode enviar
- Regras de aprovação: estagiário sempre precisa, pagamento acima de X precisa
  de sócio
- "Atribuídas a mim" nas Tarefas, e "pedido por" nas Aprovações
- Quem pode aprovar no seu lugar

Sem servidor: os perfis moram na mesma base, e o que separa um do outro é a
senha do perfil, não a do Windows. A tela diz exatamente essa diferença.

---

## Etapa 16 — Licença

**Tela:** Configurações
**Tamanho:** médio
**Depende de:** Etapa 15

A última decisão desfeita, e a que existe por causa da venda.

- Chave de licença assinada, conferida nesta máquina com a chave pública —
  sem servidor, sem telefonar para casa
- Plano, número de pessoas, validade e o que acontece quando vence
- Aviso de vencimento próximo, e o modo leitura quando expira

Vencer não pode apagar o trabalho de ninguém: expirada, a licença tranca o que
tem efeito externo e deixa ler, exportar e imprimir. Perder acesso ao próprio
contrato por causa de uma data é o tipo de coisa que faz um escritório nunca
mais confiar num programa.

---

## Etapa 17 — O resto da comparação

**Telas:** Aprendizado · Desempenho · Relatórios · Foco · Organizar · Assinar
**Tamanho:** médio
**Depende de:** as anteriores

O que sobrou da comparação, tela a tela.

- Aprendizado: ensinar com arquivos e ensinar com palavras
- Desempenho: disco, rede, temperatura e o gráfico dos últimos 60 s
- Relatórios: período, abas, enviar por e-mail, agendar o semanal
- Foco: silenciar avisos, tarefa do ciclo, conversar sobre hábitos
- Organizar: salvar como rotina
- Assinar: compartilhar depois de assinar, prévia, repetir o selo
- Certificado: testar assinatura, arrastar o arquivo
- Configurações: foto e documentos do titular

---

# Acesso de fora (`acesso-remoto/v0`)

O computador do escritório continua sendo o PAULUS; o advogado ganha um
caminho seguro até ele, de casa ou do celular, pelo túnel da Cloudflare em
`<escritório>.paulus.ia.br`. Documentos, metadata e modelo nunca saem da
máquina. Tudo atrás da preferência `acesso_remoto`, desligada de fábrica. O
andamento etapa a etapa está em `docs/PROGRESSO-IMPLEMENTACAO.md`.

## R1 — A chave da janela ✓ FEITA

O servidor sempre escutou só em `127.0.0.1`, e isso parecia bastar. Não
basta: **qualquer programa do computador** chamava `127.0.0.1:<porta>` sem
controle nenhum, e o agente do túnel também vai conectar de `127.0.0.1`. O
endereço de origem não separa quem está na frente da máquina de quem chega
pela internet, e cabeçalho (`Cf-Connecting-IP`, `X-Forwarded-For`) qualquer
processo local forja.

Quem separa agora é uma chave, nova a cada início do servidor
(`src/acesso/chave.py`):

- a janela abre `/entrar-local?chave=…` uma vez, e a chave vira um cookie de
  sessão local — `HttpOnly`, `SameSite=Strict`, de valor diferente da chave.
  O endereço não vale uma segunda vez: endereço fica em histórico e em log;
- quem não tem janela — a segunda instância que entrega o "Perguntar ao
  PAULUS" do Explorer, o roteiro da demonstração, os testes — lê a chave do
  `instancia.json` e manda `X-PAULUS-Chave`;
- `python src/api.py` imprime o endereço com a chave, como o Jupyter.

O resto recebe 403: HTML explicando para quem abriu no navegador, JSON para
quem chamou a API. O `#perguntar=…` do Explorer atravessa a entrada porque
quem segue para `/` é o navegador (`location.replace('/' + location.hash)`):
o fragmento nunca chega ao servidor.

O porteiro (`src/acesso/porteiro.py`) é ASGI puro, e não o middleware de alto
nível do Starlette: aquele embrulha o corpo da resposta, e a conversa sai em
streaming por minutos.

O retorno do login do Google e da Microsoft não precisou de exceção: ele cai
no servidor temporário do próprio `correio_oauth.py`, não neste.

**Medido:** o portão percorre `app.routes` — 363 rotas, nenhuma escrita à mão
— e todas respondem 403 sem a chave; rota que nem existe também (403, não
404: nada se descobre de fora). Chave errada, cookie inventado e cabeçalho de
origem forjado continuam de fora.

**O que a verificação achou:** dois testes que abrem o navegador de verdade
(`test_tela`, `test_listas`) e um que sobe o servidor (`test_habilidades`)
falavam com o PAULUS como qualquer programa — exatamente a brecha. Passaram a
entrar pela chave, como a janela.

## R2 — Contas, senha, código do autenticador ✓ FEITA

Quem entra de fora entra com uma conta do escritório: e-mail, senha e o código
do aplicativo autenticador do celular (`src/acesso/contas.py`). Tudo com a
biblioteca padrão — nenhuma dependência nova:

- **senha** em `hashlib.scrypt` (n=2¹⁴, r=8, p=1), sal por conta, mínimo de 10
  caracteres. Lento de propósito: cada tentativa custa memória e tempo para
  quem roubou o arquivo, e é imperceptível para quem digita a própria;
- **TOTP** (RFC 6238) com `hmac`: 30 s, 6 dígitos, uma janela de folga para
  cada lado. O mesmo código não vale duas vezes — quem viu por cima do ombro
  chega tarde. O segredo fica protegido pela DPAPI; fora do Windows o módulo
  diz que está indisponível em vez de guardar mal;
- **QR** desenhado pelo reportlab, que o programa já usa para o PDF;
- **10 códigos de recuperação** de uso único, dos quais só o hash fica.

A sessão remota é um cookie aleatório (`HttpOnly; Secure; SameSite=Strict`)
de que o servidor guarda só o sha256. Morre com 30 min sem uso e com 12 h de
idade, e leva um token anti-CSRF que todo pedido que altera algo apresenta —
posto por `js/00-acesso.js`, que embrulha o `fetch` da página: tela nova já
nasce protegida, sem ninguém lembrar.

Cinco erros bloqueiam por 15 min, e cada bloqueio dobra o seguinte. O erro
conta por e-mail digitado, exista a conta ou não, e o scrypt roda igual sem
conta: nem o bloqueio nem o tempo de resposta dizem se um e-mail tem conta.
Cada bloqueio vira aviso do Windows na máquina do escritório.

Contas se criam, mudam e saem só pela janela local — as rotas conferem isso
por dentro, além do registro de permissões: uma sessão roubada não cria
conta nem troca senha. A primeira conta é sempre do titular, e o último
titular não sai. Trocar a senha derruba as sessões da conta.

O e-mail que passou pelo Cloudflare Access tem de ser o da conta: Access
dizendo uma pessoa e cookie dizendo outra não vale nenhum dos dois.

**Telas:** Configurações › Acesso de fora (contas, cadastro no autenticador
com QR e chave, códigos de recuperação, sessões abertas) e a tela de entrar
de quem está de fora (`frontend/entrar.html`), em duas etapas, no desenho do
A0: coluna de 520 px, título em Garamond, botão da casca. Conferidas num
navegador de verdade, em 1440 e em 390 px.

**Medido:** vetor da RFC 6238 confere; código de 60 s atrás recusado, de 30 s
aceito; 6ª tentativa bloqueada, bloqueio seguinte de 30 min; sessão viva com
uso a cada 29 min e morta com 31 min parada ou 12 h de idade.

**O que a verificação achou:** o FastAPI desta versão guarda o roteador
incluído (`include_router`) embrulhado, e as rotas dele somem de
`app.routes` — o porteiro não achava a rota de entrar e respondia 401. As
rotas do acesso passaram a ser registradas direto no app, como as outras.
Quatro ícones da seção não existiam no recorte da fonte e apareciam como
letras; trocados.

## R3 — O que se faz de fora, rota por rota ✓ FEITA

Ler, perguntar e redigir: sim. O que é irreversível, ou mexe na própria
segurança: só no computador do escritório. A tabela é **código**
(`src/acesso/politicas.py`): um registro central com as 376 rotas, cada uma
com a sua política, e **rota sem política é bloqueada** — rota nova nasce
fechada, e o portão falha até alguém decidir o que ela é.

Registro central, e não decorador espalhado: a tabela inteira cabe numa
leitura, e é o tipo de coisa que se revisa inteira.

- **permitido** — conversar, perguntar, buscar, ver documento e trecho
  citado, o editor e a planilha, usar o e-mail e o Google já configurados;
- **propor** — agenda, tarefas e cadastros: ver é livre, e o que grava vira
  pedido na fila de Aprovações com o pedido inteiro guardado. O sim de quem
  pode (a janela local, ou o titular de fora) refaz exatamente aquilo. A tela
  de fora recebe 202 e diz "Foi para Aprovações";
- **titular** — aprovar. E a rota confere item por item: o que é só do
  escritório (mover, apagar, exportar em lote, assinar) não se aprova de fora
  nem pelo titular — aprovar ali seria fazer por tabela o que a tabela proíbe;
  o que sai desta máquina (e-mail, Drive, sala do Meet) pede o código do
  autenticador de novo;
- **download** — um documento por pedido, e cada um registrado;
- **bloqueado** — o resto, incluindo a documentação automática do FastAPI
  (`/openapi.json` é o mapa inteiro da API).

E-mail de fora vai **sempre** para a fila, mesmo com "enviar sem confirmar"
ligado, e senha de e-mail não se entrega de fora.

Na tela, os destinos que só existem no escritório (Configurações, Assinatura,
Financeiro, Relatórios, Foco, Conexões, Organizar, Apoiar) ficam apagados no
menu e abrem uma tela que diz "Disponível só no computador do escritório". O
403 de qualquer outra tela traz a mesma frase, que aparece na barra de avisos
sem cada tela precisar saber disso.

**Não se encaixou com clareza** numa linha da tabela, e ficou bloqueado para
revisão: Financeiro, Relatórios, Foco e bem-estar, gravar em Serviços e
Gravações, enviar arquivo, trazer arquivo para o editor, guardar anexo de
e-mail no Acervo, Apoiar. A lista está em `docs/PROGRESSO-IMPLEMENTACAO.md`.

**Medido:** as 376 rotas com política (114 permitidas, 19 de propor, 9 de download, 1 de titular, 10 públicas, 223 bloqueadas); cada linha da tabela testada de fora
com colaborador e com titular.

**O que a verificação achou:** o 401 de "sessão acabou" e o 401 de "preciso
da senha do e-mail" eram iguais para a tela, que mandaria para o login quem só
esqueceu a senha do e-mail. O do porteiro passou a vir com
`X-PAULUS-Sessao: acabou`. E a opacidade dos itens bloqueados não pegava no
trilho: a animação de entrada vence a declaração; vai no ícone e no rótulo.

## R4 — A fila do modelo ✓ FEITA

O modelo desta máquina responde uma pergunta por vez. Com uma pessoa só,
ninguém percebia. Com o escritório perguntando daqui e o advogado do celular,
as duas respostas disputariam o mesmo processador — as duas mais lentas, e
sem ninguém saber por quê.

`src/fila_modelo.py`: uma fila única, na ordem de chegada, com no máximo
**duas perguntas por pessoa** (a que está sendo respondida conta). Quem
espera vê a posição e a previsão — "na fila do modelo: você é o 2º, ~40 s" —,
e a previsão sai da mediana do que esta máquina já levou para responder
(`ritmo.segundos_por_resposta`). Sem medida, só a posição. Com uma pessoa
só, a fila é invisível: ninguém espera, nada aparece.

Parar tira da fila, ou interrompe só a própria resposta. O trabalho de
segundo plano chama `ceder()` entre um item e outro e espera enquanto houver
pergunta. A conversa sobre um Serviço entra na mesma fila: é o mesmo modelo.

A vez é pega **dentro** da resposta em andamento, e não na rota: se a
página fechar antes de a resposta começar, nenhum lugar fica preso na fila.
A terceira pergunta é recusada antes de entrar no histórico da conversa.

**Medido** com um modelo de mentira que escreve a própria pergunta em cada
palavra e dorme entre elas: duas pessoas ao mesmo tempo, nunca mais de uma
resposta andando, nenhuma palavra trocada, ordem de chegada respeitada, e
quem esperou viu "1º na fila"; a terceira da mesma pessoa, 429 com a frase;
parar A no meio e B termina inteira.

**O que a verificação achou:** o servidor relê a pasta ao subir e troca o
índice — o documento posto direto no índice sumia antes da primeira
pergunta. O teste passou a pôr o arquivo na pasta do Acervo.

## R5 — O Worker cria o caminho de cada escritório ⏸ ESPERA O PAINEL

O advogado não pode precisar de conta Cloudflare. O Worker de
`paulus.ia.br` (`worker/tunel.js`) cria tudo na conta do Atos, sob demanda,
com o fluxo de autorização de dispositivo: o PAULUS pede, recebe um código
curto (`XXXX-XXXX`), o titular abre `paulus.ia.br/conectar`, confirma o
e-mail pelo Cloudflare Access e aperta Confirmar. O Worker então cria o
túnel gerenciado remotamente, o ingress para `127.0.0.1:<porta>` (o resto
404), o CNAME com proxy, a política e a aplicação do Access (sessão de 12 h,
só o e-mail do titular), e entrega o token do túnel ao PAULUS **uma vez**.

Falha em qualquer passo desfaz os anteriores: escritório pela metade na
conta do Atos é lixo que ninguém vê. O KV guarda só o hash do segredo de
cada instalação. O Worker confere o JWT do Access com a chave pelo `kid`,
`aud` e `iss`, e nunca atende `<escritório>.paulus.ia.br` — esse tráfego vai
direto ao túnel; se uma rota curinga apontar para ele por engano, 404.

Tudo atrás de `TUNEL_ATIVO` e do KV `ESCRITORIOS`: sem os dois, as rotas não
existem, e o código pode ir ao ar no deploy de cada push sem ligar nada.

**Medido** (`worker/teste-tunel.mjs`, API da Cloudflare e Access de mentira,
JWT assinado de verdade com chave gerada no teste): fluxo completo; entrega
uma vez só; JWT de outro e-mail, de outra chave, de outra aplicação e
vencido, recusados; falha na criação da aplicação desfaz túnel, DNS e
política; segredo errado 401; limite de escritórios; `TUNEL_ATIVO` ausente,
404.

**Falta** o que só o dono da conta faz no painel: token de API, KV, a
aplicação do Access de `/conectar`, os segredos e ligar `TUNEL_ATIVO`. A
lista passo a passo está em `docs/PROGRESSO-IMPLEMENTACAO.md`.

## R6 — O túnel dentro do PAULUS ✓ FEITA

O `cloudflared` roda como processo filho (`src/acesso/tunel.py`): acha o
executável (a pasta do instalador, o PATH, Program Files), confere a versão
mínima, e sobe `cloudflared tunnel --no-autoupdate run` com o token **no
ambiente** — linha de comando de processo qualquer programa da máquina lê.
O log (`data/logs/tunel.log`) passa por um filtro que tira o token de toda
linha. Caiu, levanta de novo com espera crescente (2 s, 4 s… até 1 min).
Fechar o PAULUS ou desligar o módulo encerra o processo — com `atexit` de
garantia: túnel órfão seria a porta de fora aberta sem o PAULUS saber.

**A porta fixa virou um segundo ouvinte**, e não a porta da janela: o mesmo
app, em `127.0.0.1:<porta fixa>`, só para o túnel. A janela continua abrindo
como sempre, a conexão vale na hora (sem reiniciar o programa), e a porta
fixa ocupada por outro programa só deixa o acesso de fora "porta ocupada" —
e o túnel **não liga**: o que viesse de fora cairia naquele programa.

**O JWT do Access é conferido aqui de novo** (`src/acesso/jwt_access.py`),
defesa em profundidade: RS256 com a chave do time escolhida pelo `kid`
(`cryptography`, que já era dependência), `aud` do escritório, `iss` do
time, validade. As chaves ficam guardadas por uma hora; sem chave
alcançável, nega. Token e segredo da instalação ficam protegidos pela DPAPI;
fora do Windows o módulo é indisponível.

**Medido:** com um `cloudflared` de mentira que registra argumentos e
ambiente, escreve o token no próprio log e cai na primeira vez: o token não
aparece nos argumentos nem no log, aparece no ambiente, e o processo levanta
de novo. JWT válido passa; vencido, de outra aplicação, de outro time,
assinado com outra chave e sem chaves alcançáveis, não. A versão foi lida do
`cloudflared` 2026.9.3 de verdade, assinado pela Cloudflare.

## R7 — O instalador traz o cloudflared, e o assistente conecta ✓ FEITA

**No instalador**, uma caixa nova: "Acesso de fora pelo celular (baixa
52,8 MB de github.com)", marcada em instalação nova quando a máquina não tem
`cloudflared`; numa atualização, só quando ele falta e o acesso de fora está
em uso. O download é de **versão fixa** (2026.9.3, constante no código) e o
arquivo só é usado depois de duas conferências: a assinatura Authenticode
válida para o Windows (`WinVerifyTrust`) **e** o assinante "Cloudflare,
Inc.". Uma sem a outra não serve — a primeira sozinha aceitaria qualquer
programa assinado por qualquer empresa. Falhou: o arquivo é apagado, a
instalação segue sem o túnel e a tela final diz por quê. Vai para
`%LOCALAPPDATA%\Programs\PAULUS-cloudflared`, sem administrador; desinstalar
encerra o processo e apaga a pasta. A tela final oferece "Configurar o
acesso de fora agora", que abre o PAULUS com `--configurar-acesso`.

**No app**, Configurações › Acesso de fora ganhou o assistente
(`src/acesso/conexao.py`, `js/43-acesso-tunel.js`), em três estados:
conectar (nome do escritório e e-mail do titular, que tem de ser uma conta
de titular com o autenticador confirmado); esperando (o código `XXXX-XXXX`
grande enquanto o titular confirma no navegador, a tela conferindo a cada
3 s); e conectado (o endereço copiável, o estado do túnel, quem pode passar
pela Cloudflare, Desligar e Remover). A lista do Access acompanha as contas:
criar conta acrescenta o e-mail, remover tira. Desligar para o túnel e
guarda o endereço; Remover apaga lá e aqui.

**Medido:** o fluxo inteiro contra um Worker de mentira (pendente, pendente,
pronto) até o túnel de mentira conectado; token e segredo fora do arquivo em
texto puro; lista de e-mails em cada mudança de conta; desligar, religar,
remover. O instalador compila com o `csc.exe` do .NET Framework 4 e a
conferência de assinatura aceita o `cloudflared` real e recusa o Python
(assinado, mas pela Python Software Foundation), o Edge (Microsoft) e um
arquivo qualquer. A tela nova do instalador foi fotografada numa montagem de
teste (o programa novo com o pacote da 0.9.3), sem instalar.

**O que a verificação achou:** desligar e religar em seguida achava a porta
fixa "ocupada" — pelo próprio ouvinte, ainda fechando. Fechar passou a
esperar o ouvinte soltar a porta. E os botões com ícone empilhavam ícone e
texto sem a classe `com-icone` do resto do app.

## R8 — Quem acessou ✓ FEITA

Tudo o que acontece pelo acesso de fora vira uma linha em
`data/acesso/acessos.jsonl` (`src/acesso/auditoria.py`): entrada e saída,
login que falhou, bloqueio, documento aberto, download, proposta, aprovação,
pedido recusado por ser só do escritório, e as mudanças do próprio módulo
(conectar, ligar, desligar, remover). Cada linha tem pessoa, e-mail que
passou pela Cloudflare, data e hora, o IP que a Cloudflare informou (só
para referência), o que aconteceu e sobre o quê — pelo **nome** ("“Minuta”
(DOCX)"), e não pelo endereço da API, que ninguém que lê um registro de
controle entenderia.

O arquivo só cresce, e cada linha guarda o sha256 da anterior somado ao
próprio conteúdo: editar uma linha antiga quebra a corrente dali em diante,
e a tela diz em qual linha. Não impede ninguém de apagar o arquivo — quem
tem a máquina tem o arquivo —, mas torna visível a edição escondida, que é o
que um registro de controle precisa mostrar. Guardado por um ano; o que sai
pela idade deixa o hash da última linha numa âncora, e a conferência começa
dela.

Folhear as páginas do mesmo documento vira uma linha a cada 10 minutos, e
não uma por página.

**Tela:** Configurações › Acesso de fora › Quem acessou, só na janela local
— com filtro por pessoa, tipo e período, o estado da corrente ("registro
íntegro · N linhas" ou "alterado à mão na linha N") e a exportação em PDF,
pelo reportlab que o programa já usa, com o estado da corrente impresso.

**Medido:** as nove ações da tabela feitas de fora, cada uma com a sua
linha; a terceira linha editada à mão acusada na linha 3; a poda de um ano
com a corrente conferível pela âncora; o PDF sai; de fora, a tela não abre.

## R9 — Celular, energia e abrir com o Windows ✓ FEITA

**No celular** (`css/22-responsivo.css`, abaixo de 600 px — a janela do
programa nunca chega lá): o trilho vira a barra de destinos embaixo, rolável,
com 44 px de toque; o cabeçalho da tela quebra linha; tabela vira lista (sem
cabeçalho de coluna, o que eram colunas corre na linha) — as regras de
`docs/ui/04-telas-mobile.md`. A tela de entrar, a conversa, o documento com o
trecho citado e Aprovações conferidos num Edge de 390 px pelo caminho de
fora de verdade (`test_tela.py`): nada passa da largura, Aprovar e Recusar
inteiros e tocáveis. "Abrir fora" (abre o arquivo num programa do Windows)
some de fora.

O aviso "Disponível só no computador do escritório" passou a aparecer só
para o que a pessoa pediu (gravar, mandar, apagar). Antes, a leitura que a
tela faz sozinha ao abrir, e que é do escritório, disparava o aviso sem
ninguém ter apertado nada.

**Streaming:** as nove respostas em streaming do `api.py` já saíam com
`text/event-stream`, `Cache-Control: no-cache` e `X-Accel-Buffering: no` —
conferido agora por leitura do código (toda chamada de `StreamingResponse`)
e na resposta de verdade da conversa. É o que faz a resposta chegar ao
celular palavra a palavra pelo túnel, e não de uma vez no fim.

**Energia** (`src/acesso/energia.py`): com o acesso de fora ligado, o
PAULUS pede ao Windows para não suspender por inatividade
(`SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)`), de uma
thread própria que fica viva enquanto segura — o pedido vale só enquanto a
thread que o fez existe. A tela diz o que o plano de energia faria sem isso
(`powercfg`, na língua do Windows) e avisa que tampa fechada ou "suspender"
continuam suspendendo.

**Abrir o PAULUS com o Windows**, minimizado: uma linha na chave `Run` do
usuário, sem administrador, desligada de fábrica, só no programa instalado
(no código-fonte não há `PAULUS.exe`). `--minimizado` abre a janela na barra
de tarefas.

**O que a verificação achou:** o celular não quebrava a largura — o que
quebrava era o espaço: com o trilho de 64 px ao lado, Aprovações ficava com
o texto do pedido sobreposto e o Aprovar cortado.

## R10 — Política, manual e o roteiro do teste real ⏸ ESPERA O TESTE NO 4G

**Política e termos** (`site/politica-de-privacidade/`, seção "Acesso de
fora", e `site/termos-de-uso/`, cláusula 6, com a numeração das seguintes
refeita): desligado de fábrica; documentos e modelo continuam no computador;
o tráfego passa pela Cloudflare, descriptografado no caminho, num subdomínio
da conta do Atos; o Atos não roteia, não inspeciona e não registra esse
conteúdo; todo acesso fica registrado no computador do escritório; só o
escritório liga e desliga. O `cloudflared` entrou na lista do que o programa
baixa. **Não publicado:** as duas páginas ficam na branch
`r10-politica-site`, fora do `main` — um push no `main` publicaria o site
antes de existir a versão que faz o que o texto diz.

**Manual** (`docs/acesso-de-fora.md`): como funciona, como conectar, como
desligar e remover, e o que fazer com porta ocupada, túnel caído e e-mail
não autorizado — cada problema com a frase que a tela mostra e onde olhar
(`logs/tunel.log`).

**Falta:** o teste real, do celular em 4G, em dez passos
(`PROGRESSO-IMPLEMENTACAO.md`). Depende do painel da Cloudflare (R5).

## Ajuste R — sem Cloudflare Access ✓ FEITO

O contrato revisado tirou o Cloudflare Access de todas as contas (decisão de
produto). O Access guardava a porta antes do PAULUS; agora quem guarda é o
próprio PAULUS, e cada escritório não gasta mais vaga do Zero Trust da conta
do Atos.

**Entrar de fora** é igual para titular e colaborador: a verificação contra
robôs (Turnstile), e-mail e senha, e o código do autenticador. O Turnstile é
conferido antes da senha, pelo Worker de paulus.ia.br, com o segredo da
instalação; se o Worker não responde, ninguém entra. Vinte erros do mesmo
endereço de internet em 10 minutos fecham o endereço por uma hora. Conta que
não existe e senha errada dão a mesma frase, no mesmo tempo. Sem sessão, de
fora só se vê a tela de entrar; toda resposta leva os cabeçalhos de
segurança (CSP com os hashes dos scripts, sem moldura, sem referer). De
fora, o titular troca a própria senha e encerra as sessões com o código de
novo.

**Ligar** virou o passo "Acesso à distância" do assistente de configuração,
logo depois do nome do escritório, e o mesmo bloco em Configurações ›
Acesso de fora: o endereço sugerido do nome (`Moura & Associados Advocacia`
→ `moura-associados`), conferido enquanto se digita; a conta do titular com
o autenticador; a confirmação no navegador com o código. O Worker reserva o
nome por 15 minutos, cria túnel e DNS (o token de API só tem Tunnel e DNS) e
limpa por dia o que nunca conectou em 7 dias ou parou há mais de 180 — o
PAULUS percebe e diz "o endereço foi liberado por falta de uso; conecte de
novo". O instalador traz o `cloudflared` sempre que falta, sem perguntar.

**Portões:** `test_r2` (Turnstile, IP, mesma resposta, 401 sem sessão,
cabeçalhos, ações sensíveis), `test_r6` (Turnstile pelo Worker, endereço
liberado), `test_r7_assistente` (sugestão, indisponível, fluxo inteiro,
expirado, interruptor desligado sem Worker, remover), `test_tela` (o passo
novo depois do nome), `worker/teste-tunel.mjs`.

# Melhoria da IA

O plano 2 do contrato: a conversa sobre documentos mais rápida, mais estável
e medida em documentos reais. Cada etapa atrás de uma chave no bloco `ia` das
preferências, e cada uma roda o banco de provas (`tools/demo/roteiro.py
--tudo`) com o Ollama antes de entrar: o resultado não pode cair.

## I1 — O que chega ao modelo ✓ FEITA

Os parâmetros não chegavam ao modelo. `config/extratores.yaml` dizia
temperatura 0 e semente 42, e a conversa mandava 0,1 e semente nenhuma: a
mesma pergunta, duas vezes, podia dar duas respostas — e não havia como saber
se uma troca de prompt melhorou ou só sorteou outra resposta. A janela
(`num_ctx`) crescia com o acervo, e cada mudança dela faz o Ollama recarregar
o modelo: um documento novo custava uma recarga na pergunta seguinte.

**Agora** (`src/inferencia.py`): as opções vêm do perfil `conversa` do
catálogo — temperatura 0, semente 42, `keep_alive` de 30 minutos (o padrão do
Ollama são 5, e a pergunta seguinte de quem lê um contrato quase sempre vem
depois disso) e teto de resposta por tarefa: conversa 700 tokens, JSON 800,
juiz 1. O editor e os resumos não têm teto. O **nome** do modelo continua na
delegação por tarefa; trocar de modelo segue sendo configuração. A janela é
fixa por modelo — 16384 de fábrica, `ia.janela_por_modelo` para outra — e o
juiz usa a mesma da conversa (janela diferente recarregava o modelo entre o
juiz e a resposta). `think: false` só vai para modelo que declara a
capacidade `thinking` no `/api/show`.

**Guarda de truncamento:** o Ollama corta calado quando o prompt passa da
janela. Chegando a 64 tokens do fim, o cliente registra e emite o evento
`truncou`; a tela põe na resposta "o texto não coube inteiro nesta leitura: o
começo ficou de fora", e o aviso fica guardado com a conversa.

**Medição** (`src/medicao.py`): uma linha por pergunta em
`data/medicao/perguntas.jsonl` — modelo, digest, janela, tokens lidos e
escritos, tempos, caminho (`tudo`, `busca`, `foco`, `nivel0`, `programa`,
`regra`), nível, trechos, caracteres, `truncou` e `fallback`. Só números,
nunca o texto da pergunta; o arquivo não sai da máquina.

**Medido** (demonstração, llama3.2:3b): roteiro `--tudo` 40/41 antes e 40/41
depois — a mesma pergunta de ausência falha nos dois ("qual a multa por
atraso no aluguel da Clínica?": o modelo responde com a multa de rescisão de
3 aluguéis). Tempo mediano das perguntas sobre documentos 8,5 s antes, 8,9 s
depois (dentro da variação; a demonstração cabe inteira nas duas janelas).
Entrada mediana de 2.366 tokens, nenhum corte. A mesma pergunta duas vezes
deu a mesma resposta, palavra por palavra.

## I2 — Medição com documentos reais ⏸ ESPERA O CONJUNTO REAL

O 41/41 do banco de provas é medido nos documentos fictícios da
demonstração, os mesmos usados para ajustar o prompt: é teto, não medida.
`tools/medir.py` roda um conjunto de perguntas com resposta conhecida e
imprime acerto, latência p50/p95, tokens de entrada e, para a busca,
Recall@20, Recall@6 e MRR@6 — mais "no contexto": das frases esperadas,
quantas estavam no que foi de fato mandado ao modelo.

O formato é o do `P(...)` do roteiro, mais `trechos_esperados` (frases
literais curtas que têm de estar no contexto — frase, e não id de trecho,
porque os ids mudam até a I5), `documentos` e `continua` (a pergunta vai na
mesma conversa da anterior). O conjunto real mora em
`data/medicao/conjunto-real.jsonl`, fora do git; `docs/medicao.md` explica
como anotar. O exemplo, sobre a demonstração, está em
`tools/demo/conjunto-demo.jsonl`: 27 perguntas dos seis tipos, 9 de
continuação ("e a multa por atraso no pagamento?", "e o foro?").

**Linha de base na demonstração** (llama3.2:3b, depois da I1): 25/27 · p50
6,6 s · p95 39,3 s · entrada p50 2.362 tokens · Recall@20 0,96 · Recall@6 0,96
· MRR@6 0,86 · 0,90 das frases no contexto. Continuação 8/9 — alto porque a
demonstração cabe inteira na leitura e o modelo acha o assunto sozinho; a
busca, sozinha, não acha "e qual índice reajusta ele?" (Recall 0). Erros: a
ausência da multa do aluguel (a mesma do roteiro) e "e a garantia?" (o
modelo disse "3 aluguéis" sem a palavra caução).

**Falta:** o conjunto real, de 30 a 50 perguntas sobre 10 a 20 documentos do
escritório. Até ele chegar, as etapas seguintes medem na demonstração — o que
é limitação, e está anotado no PROGRESSO.

## I3 — Nível 0 por molde, sem modelo ✓ FEITA

O nível 0 era texto livre do modelo sobre fatos já conferidos. Os fatos
estavam certos; a frase, não necessariamente: um modelo de 3 bilhões de
parâmetros copia um CNJ trocando um dígito com a mesma cara de certeza com
que copia certo. Para as perguntas de um dado só a resposta **é** o fato, e
agora sai montada por molde (`src/inteligencia/molde.py`), com a página —
"O valor da causa é R$ 15.000,00 (p. 2)." —, sem chamar o modelo e sem
entrar na fila (R4): número do processo, valor, tribunal, partes, data de
assinatura e leis citadas. Documento sem página (DOCX, TXT) cita o nome do
arquivo no lugar da página.

As travas do molde: dois valores num documento para "qual o valor?" não
viram um escolhido (escolher seria sortear); "qual o valor da multa?" num
documento em que a regra só achou o aluguel não responde com o aluguel;
"qual a vara?" e "qual o foro?" não recebem o tribunal; "quem é o réu?"
lista só o réu.

Onde o modelo continua no nível 0 (prazos, vários valores, listas, o
resumo), a **conferência mecânica**: todo número, data, CNJ, CPF, CNPJ e
valor em R$ da resposta tem de estar nos fatos (ou na pergunta). 18.500 e
18.500,00 são o mesmo número; 10/03/2024 e "10 de março de 2024" a mesma
data. Um dígito trocado descarta a resposta: a lista pronta a substitui
quando a pergunta era de lista, e senão a pergunta escala para a leitura.

**Medido:** portão com 5 perguntas factuais sobre uma petição, zero
chamadas ao modelo, mediana de 5 ms, com a fila ocupada por outra pessoa
(nenhuma esperou). Roteiro `--tudo` 40/41 (igual); mediana das perguntas
sobre documentos 8,9 → 7,2 s. Medição da demo: 25/27, p50 6,6 → 6,2 s, p95
39,3 → 17,2 s.

**O que a verificação achou:** o CNJ do teste tinha dígito verificador
inválido — a regra de extração recusou (com razão), a pergunta caiu na
fila ocupada e o teste travou em vez de falhar. O teste agora pergunta
antes se a resposta sai sem o modelo.

## I4 — Memória da conversa ✓ FEITA

Cada pergunta ia ao modelo sozinha. "E a multa?", depois de "qual o prazo do
contrato ACME?", chegava como "e a multa?": a busca procurava "multa" no
acervo inteiro e o modelo escolhia um contrato qualquer.

Agora (`src/memoria.py`), por regra e antes da busca: a pergunta que começa
com "e o", "e a", "e no", "e quanto"…, ou que diz "ele", "dela", "nesse" sem
nome próprio, **herda o sujeito da anterior** — "e a multa?" vira "qual a
multa do contrato ACME?"; "e qual índice reajusta ele?" vira "qual índice
reajusta o aluguel da Clínica Bem Viver?". Numa sequência de continuações o
assunto herdado passa adiante como estava, sem ser tirado de novo da
pergunta já reescrita (o que dava "o locador da locação do aluguel…"). A
continuação herda também os documentos a que a resposta anterior se
restringiu. A conversa guarda o que a pessoa escreveu; a busca e o modelo
leem a pergunta inteira, e o registro da conversa diz como ela foi entendida.

Os **dois últimos pares** pergunta/resposta vão como mensagens anteriores,
até ~600 tokens: as perguntas inteiras, as respostas cortadas em fim de
frase, sem resumo por modelo. Resposta parada no meio não entra. Chave
`ia.memoria`.

**Medido:** as 9 continuações do conjunto herdam o sujeito, e as 18 que não
são continuação não mudam. Demonstração: 26/27 (era 25/27) — **continuação
9/9** (era 8/9: "e a garantia?" agora responde com a caução). Roteiro
`--tudo` 40/41 (igual). O tempo dessa rodada (p50 16,8 s) não vale: ela
rodou junto com a medição do reranker da I7, que ocupou a CPU por minutos.

## I5 — Trechos pela estrutura do documento ✓ FEITA

A busca quebrava o texto em blocos de 1.200 caracteres, cortando onde o
tamanho mandava: a cláusula começava num trecho e terminava no outro, com a
multa num pedaço e a condição dela no outro. Agora (`src/trechos.py`) a
unidade é a do autor do documento:

- **regime B — peças e contratos:** quebra no cabeçalho (CLÁUSULA, DOS
  FATOS, DO DIREITO, DOS PEDIDOS, DISPOSITIVO, VOTO, EMENTA, numeração romana
  e decimal). Seção acima de ~1000 tokens vira janelas de ~700 com 96 de
  sobreposição, sem sair dela; seção abaixo de 80 tokens se junta à vizinha
  — o grupo para de crescer quando passa do mínimo (crescer até o teto
  juntava seis cláusulas curtas num trecho só);
- **regime A — leis:** um artigo por trecho, com os parágrafos e incisos
  dele. Artigos não se juntam.

Cada trecho tem `chunk_id` (versão + posição; a versão combina o sha1 do
arquivo com o nome, porque "contrato.pdf" e "contrato (1).pdf" iguais são
dois documentos), `char_start`/`char_end`, páginas pelo mapa de layout,
regime e `text_embed` com o caminho na frente ("Contrato ACME > CLÁUSULA
9ª"), que é o que a busca indexa. A API do buscador (`search`, `tudo`,
`dos_documentos`, `format_context`) não mudou; a remontagem de trechos
vizinhos usa a posição, sem adivinhar a sobreposição pelo texto. Chave
`ia.trechos_estruturais`.

**Medido:** mesmo documento e reindexação do zero em outra ordem dão os
mesmos ids; todo trecho de documento paginado tem página; nenhum trecho
corta seção; o texto de cada trecho é a faixa exata do extraído. Roteiro
`--tudo` 40/41 (igual), mediana 8,8 s. Demonstração 26/27, p50 9,2 s,
Recall@6 0,95, MRR@6 0,87 (15 trechos, eram 9). Suíte: 71 passam.

**Depois:** a verificação da I8 achou contrato com "CLÁUSULA 3ª - DO ATRASO.
A multa é…" na mesma linha — o cabeçalho só era reconhecido em linha curta.
Agora a linha que começa por CLÁUSULA abre seção, qualquer que seja o
tamanho dela.

## I6 — Índice léxico em FTS5, com uma normalização jurídica só ✓ FEITA

O BM25 de antes (rank_bm25) morava na memória e era refeito do zero a cada
abertura, com o acervo inteiro tokenizado de novo. Agora (`src/lexico.py`)
o índice fica em disco, em SQLite FTS5 (`data/indice/lexico.db`,
`unicode61 remove_diacritics 2` sobre o `text_embed`), incremental por
versão: arquivo que não mudou não é reindexado, e o que saiu do Acervo sai do
índice.

**Uma única normalização para indexar e para consultar** — se o texto vira
"art 300" e a pergunta "art. 300", nada casa e ninguém vê o erro. Ela
reaproveita `normalize` e `radical` de `search.py` e acrescenta o que é da
escrita jurídica: `art. 300 → art 300`, `§1º → par 1`, `13.105/2015 → 13105
2015`, `S. 331 TST → sumula 331 tst` (e "Súmula 331 do TST", "parágrafo
único", "2ª"). Números de um dígito ficam — o "5" de "art. 5" é o que se
procura. O filtro por documento vale antes de ordenar; empate desempata pelo
id (mesma consulta, mesma ordem); o complemento por presença de termos
continua quando falta resultado. Substitui o rank_bm25 atrás de
`ia.lexico_fts` (o material de consulta segue no BM25 de antes).

**Medido:** os quatro exemplos normalizam igual dos dois lados; "S. 331
TST", "súmula 331 do TST" e "parágrafo 1 do artigo 300" acham o trecho certo;
abrir de novo não reindexa nada. **Linha de base só-léxico** na
demonstração: Recall@20 0,96, Recall@6 0,95, MRR@6 0,87. Roteiro `--tudo`
40/41 (igual), mediana 7,6 s; demo 26/27, p50 7,9 s. Suíte: 71 passam; o
test_tela caiu uma vez com o segfault intermitente de antes (código 139).

## I7 — Busca híbrida, e a virada do "ler tudo" pronta atrás de chave ✓ FEITA (virada desligada)

**Busca por sentido** (`src/denso.py`): vetores do `bge-m3` pelo próprio
Ollama (`/api/embed`), normalizados L2, com o espaço gravado em cada vetor
(`bge-m3|1024|l2|v1`); a consulta nunca compara espaços diferentes, e trocar
o modelo de vetores pede vetorizar de novo. Os vetores ficam em SQLite como
BLOB, com o cosseno em numpy: a extensão `sqlite-vec` não está no ambiente
do programa, e numpy já vem. Os vetores são feitos em segundo plano,
cedendo a vez à fila do modelo (R4) antes de cada lote de 16. O modelo só
chega pelo botão novo em Configurações › Modelos ("Busca por sentido", com
o tamanho — 1,2 GB — antes de baixar).

**Fusão** (`src/recuperacao.py`): RRF k=60 sobre as duas listas (léxico 50 +
denso 50 → 20), trecho que não ficou entre os 20 primeiros de nenhuma delas
não entra para "completar", e o orçamento: 6 trechos, 3000 tokens, 3 por
documento, sem quase-duplicado (cosseno ≥ 0,92).

**Reranker:** `bge-reranker-v2-m3` int8 em CPU, com onnxruntime (já no
ambiente, pelo faster-whisper), medido por `tools/medir_reranker.py`:
**34 s para 20 pares** (10.240 tokens). A régua era 3 s — **não entrou**;
fica só a RRF.

**A virada** (`ia.leitura = "trechos"`): lê os trechos da busca híbrida em
vez do escopo inteiro, salvo escopo que cabe em ~4000 tokens ou pergunta
que pede ("leia o contrato inteiro"); a janela cai para 8192. Está pronta e
testada, e **desligada de fábrica** (ver PROGRESSO): a demonstração cabe
inteira em 4000 tokens, então nenhuma pergunta do banco de provas passa pela
virada, e ligar a leitura por trechos com base só nela seria ligar sem
medir.

**Medido na demonstração** (15 trechos, 15 vetores): só léxico R@20 1,00 ·
só denso 1,00 · híbrido 1,00 (satura — a régua "híbrido > o melhor dos
dois" não discrimina aqui); Recall@6 0,99; MRR@6 0,93; contexto p50 **718
tokens** no que a busca híbrida mandaria ao modelo, contra ~2.368 da leitura
inteira. Roteiro `--tudo` 40/41 (igual), mediana 7,2 s; demo 26/27, p50
7,8 s. Suíte: 73 passam.

**O que a verificação achou:** o teste do orçamento passava com um trecho só
— os vetores de mentira deixavam todos os trechos quase iguais, e a
deduplicação tirava o resto. Com vetores de palavras (hash), o orçamento é
exercitado de verdade: 6 trechos, 2.128 tokens, no máximo 3 por documento.

## I8 — Contrato de resposta `[Tn]` ✓ FEITA (chave desligada)

Cada frase da resposta aponta para o trecho que a sustenta, e três
conferências em código rodam antes de a resposta ficar na conversa
(`src/citacoes.py`):

1. frase que afirma e não tem marca ganha o rótulo **"sem fonte"**;
2. marca de trecho que não existe (`[T9]` com seis trechos) refaz a resposta
   uma vez, com metade dos trechos;
3. lei, artigo, súmula ou número de processo citado que não está em nenhum
   trecho **sai da resposta** e fica registrado — os achadores são os da
   camada de inteligência (`regras_leis`, `regras_processo`), e a marca que
   estava colada à citação fica.

Na tela, `[Tn]` vira um botão com o número do trecho que abre o trecho na
página do documento (o "ver no documento" de sempre); "sem fonte" vira
rótulo. Sem nenhuma frase sustentada, a resposta vem com o cartão "sem
fundamento nos trechos": **Ler o documento inteiro** ou **Procurar em todo o
Acervo**. `papel_sem_prova` e `trecho_decisivo` continuam: o primeiro
responde por regra antes do modelo, o segundo acrescenta a frase literal do
documento depois da conferência.

**Três tentativas, medidas.** Pedir as marcas ao modelo derrubou o banco de
provas nas duas primeiras — trechos numerados soltos (38/41) e agrupados por
documento (38/41): a instrução a mais deixou o llama3.2:3b seco ("Não
achou.") e fez ele misturar documentos (a multa de 2% do transporte virou a
multa do aluguel). A terceira, a que ficou: **o modelo lê o contexto e a
instrução de sempre, e as marcas são postas em código** — cada frase ganha o
trecho que tem todos os números dela e mais palavras em comum
(`ia.citacao = "codigo"`; `"modelo"` continua existindo para um modelo maior).

**Medido com `"codigo"`, sozinho na máquina:** roteiro `--tudo` 40/41
(igual à I7); demonstração 26/27; **0 "não encontrei" indevido** (igual à
I7); **0 citação inventada**; 5 frases marcadas "sem fonte" em 27 respostas.
O roteiro passou a conferir o texto conferido (evento `revisao`), que é o
que fica na conversa.

**Por que desligada de fábrica:** o portão passa, mas o rótulo "sem fonte" e
o cartão de sem fundamento mudam o que a pessoa vê em toda resposta — é
decisão de produto, e está no PROGRESSO para o dono.

**O que a verificação achou:** a divisão em frases quebrava em "art. 412"
(o ponto da abreviatura); o conectivo da citação removida ficava pendurado
("nos termos do."); e rodar dois roteiros ao mesmo tempo no Ollama muda as
respostas — os números acima são de rodadas sozinhas.

## I9 — A IA ajuda sem ser perguntada ✓ FEITA

Tudo a partir do metadata que já existe, sem modelo (`src/ajuda.py`):

1. **O cartão do documento**, na ficha do Acervo: tipo, partes, valores,
   número do processo, datas e pedidos — **só fatos conferidos** —, cada um
   com a página. O lápis corrige: a correção fica gravada como `manual` no
   metadata e vira uma pergunta nova em `data/medicao/conjunto-real.jsonl`.
   Data se corrige como dd/mm/aaaa.
2. **Perguntas que respondem na hora**, pelo tipo do documento — só as que o
   molde responde (a lista de pedidos passou a sair por molde também).
   Clicar pergunta.
3. **Prazos e vencimentos** conferidos viram pedido em Aprovações ao fim da
   análise do documento ("Vencimento de … em 10/12/2099 — anotar?"), uma vez
   por prazo. O sim anota uma tarefa com o prazo na Agenda; nada é gravado
   sozinho.
4. **A resposta diz como foi feita**: "respondi pelos fatos já conferidos,
   sem o modelo, em menos de 0,1 s", "li 2 documentos por inteiro, em 8 s",
   "li 6 trechos de 2 documentos, em 34 s".

**Medido:** o cartão não mostra um valor não conferido posto no metadata; a
correção grava `manual` e a linha no conjunto; as 4 perguntas sugeridas da
petição de teste responderam sem nenhuma chamada ao modelo; o prazo virou
pedido em Aprovações, sem tarefa gravada, e não duplica. Roteiro `--tudo`
40/41, demo 26/27. Suíte: 75 passam.

**O que a verificação achou:** o campo de correção não tinha teto de largura
(`test_frontend`); e a ficha que aparece no Acervo é a da linha
(`25-acervo-editorial.js`), não o painel lateral antigo — o cartão foi para
ela, no estilo dela.

## Plano 2 — antes e depois

Medido na demonstração (8 documentos, llama3.2:3b, CPU), cada rodada sozinha
na máquina. **O conjunto real ainda não existe** (⏸ I2): estes números são
teto, não medida.

| | Antes (I1/I2) | Depois (I9) |
| --- | --- | --- |
| Roteiro `--tudo` | 40/41 | 40/41 |
| Conjunto da demonstração | 25/27 | 26/27 |
| Continuação ("e a multa?") | 8/9 | 9/9 |
| Pergunta de um dado só (nível 0) | modelo, segundos | molde, ~5 ms, sem fila |
| "Não encontrei" indevido | 0 | 0 |
| Citação inventada | não medido | 0 (e tirada se houver) |
| Entrada p50 / p95 (tokens) | 2.362 / 2.371 | 2.368 / 2.522 (o histórico da I4) |
| Latência p50 / p95 | 6,6 s / 39,3 s | 9,1 s / 51,5 s |
| Contexto com a leitura por trechos | — | 718 tokens (virada desligada) |

A latência da demonstração varia de 6,2 a 9,2 s de p50 entre rodadas do
mesmo código (I3 a I7) — a diferença acima está dentro dessa variação, e a
demonstração cabe inteira na leitura, então a busca e a virada quase não
entram. O ganho de tempo que o plano mira (ler 700 tokens em vez de 32 mil
num acervo grande) só aparece com documentos reais e a virada ligada.


---

# A Biblioteca do escritório (M0–M7)

O plano está em `docs/PROGRESSO-BIBLIOTECA.md`: o material de consulta, as
leis em casa e os lembretes viram uma biblioteca jurídica com fonte. O
PAULUS não "treina" com os livros: lê uma vez, organiza e cita obra, autor e
página.

## M0 — Levantamento e o conjunto da Biblioteca ✓ FEITA

**Levantamento** do que o plano supunha contra o código de 30/09/2026 (tabela
no PROGRESSO). Duas adaptações: `jobs.py` são os trabalhos da conversa, não
uma fila de fundo (a leitura da M5 vira um fio como o `Backfill`); e não há
"tela da lei" própria (a seção da M3 entra no painel "Citar a lei" e na tela
Biblioteca).

**Conjunto:** `tools/demo/biblioteca_demo.py` monta `data/demo-biblioteca` (o
escritório fictício, o manual, o CDC do Planalto em PDF e **duas obras de
doutrina fictícias**, marcadas como fictícias) e escreve 44 perguntas em
`data/medicao/conjunto-biblioteca.jsonl`, de sete tipos: sinônimo,
dispositivo, lei pura, manual, sem material, fora da cobertura e temporal.
`tools/medir.py --conjunto biblioteca` mede Recall@6, MRR@6, ruído, acerto por
tipo e os avisos. O dono pediu para seguir com a demonstração: é a limitação
desta medição.

**Linha de base** (BM25 + cobertura, o material de antes): Recall@6 0,58, MRR@6
0,54, ruído 0,375, sinônimo 1/7, acerto 32/44, 6 "não encontrei" indevidos, 0
citação inventada, p50 15,6 s. Roteiro `--tudo` 41/41.

## M1 — O material no pipeline híbrido ✓ FEITA

- `src/biblioteca/indice.py`: o material usa `IndiceLexico` e `IndiceDenso`
  em `<material>/indice/`, separados do Acervo; vetores pelo `Backfill`,
  cedendo a vez; sem o bge-m3, só o léxico, sem erro.
- **Regime C** em `src/trechos.py` (`fatiar_obra`): Parte, Título, Capítulo,
  seção decimal e título em caixa alta; sumário, folha de rosto, cabeçalho e
  rodapé repetidos não viram trecho (trocados por espaços, as posições ficam);
  nenhum trecho atravessa capítulo; a janela prefere terminar na virada de
  página. Manual e tabela: regime B dentro de cada página. Lei: regime A.
- A entrada do trecho: top-20 da RRF + (cobertura de palavras **ou** cosseno ≥
  τ) + 0,35 do melhor + a regra dos nomes. **τ = 0,625**, escolhido pela regra
  escrita antes de medir (maior Recall@6 − ruído, ruído ≤ o da base).
- Chave `biblioteca.hibrida`, ligada de fábrica depois do portão.

**Medido:** Recall@6 **0,839** (base 0,581), ruído 0,375 (igual à base),
sinônimo 4/7 (base 1/7), MRR@6 0,707. Roteiro `--tudo` 40/41 — a que falha
("qual a multa por atraso no aluguel da Clínica?") falha igual, com a mesma
resposta, na árvore principal sem nenhuma mudança da Biblioteca e com o
bge-m3 fora da memória: o 3B mudou a resposta dela entre a madrugada e a
manhã.

**O que a verificação achou:** a regra dos nomes tratava "Código Civil" e
"CDC" como nome de parte, e a pergunta por dispositivo não achava a obra
(corrigido: `NAO_SAO_NOMES`); o título do capítulo que quebra em duas linhas
virava capítulo novo; a folha de rosto em caixa alta virava trecho; o trecho
que termina na virada de página dizia "páginas 5–6" sem texto na 6.

## M2 — Triagem, ficha e as leis que faltam ✓ FEITA

- **Cinco códigos novos** em `leis.CODIGOS`: CDC, Constituição (com o ADCT à
  parte: "CF, ADCT, art. 2º"), CTN, ECA e Lei do Inquilinato, com os endereços
  do Planalto conferidos em 30/09. "Baixar do Planalto" em Configurações ›
  Códigos de lei (só um GET no endereço oficial).
- **O leitor de leis perdia artigos**: a quebra de linha do código-fonte do
  Planalto partia "Art." e "10." em linhas diferentes, e o artigo ia parar
  dentro do anterior. Medido: o Código Penal ganhou 44 artigos (o 147-A,
  perseguição, inclusive), a CLT 28, o CC 1 (853-A), a Lei do Inquilinato 2.
  O nome do Título, na linha de baixo, também saiu do fim do artigo anterior.
- **Triagem por regra** (`src/biblioteca/triagem.py`): lei conhecida vai para
  as leis em casa, artigo por artigo (e não é guardada de novo se já está);
  lei não catalogada fica como material de lei, com aviso; súmulas, um trecho
  por enunciado; doutrina, manual, tabela, modelo de peça.
- **Ficha** (`src/biblioteca/ficha.py`): tipo, título, autor, edição, ano,
  editora, ISBN (com dígito conferido), áreas (das leis mais citadas),
  `origem` e `licenca`. Pela ficha catalográfica; campo não achado fica vazio;
  o que a pessoa edita vale sobre a regra.
- Chave `biblioteca.triagem`, ligada de fábrica depois do portão.

**Medido:** 5 fichas realistas com armadilhas (histórico de edições,
reimpressão, ISBN com dígito trocado, edição sem número): 30 campos, 0
errados. O CDC em PDF dá os mesmos 130 artigos do HTML do Planalto, com o
mesmo texto. 10 artigos sorteados de cada código novo conferem com o
Planalto. Na busca: **ruído 0,0** (base 0,375), fora da cobertura 0/5 com
material; o Recall@6 da lei pura cai para 0,17 até a M4 pôr o texto do
artigo na camada LEI.

**O que a verificação achou:** a rota nova `GET /api/biblioteca` tomava o
lugar da lista do Acervo (que já usa esse nome) — virou
`/api/biblioteca-juridica`; toda rota nova precisa de política de acesso de
fora (`src/acesso/politicas.py`); "ficha catalográfica" no meio de uma frase
era lida como o começo da ficha; o registro da bibliotecária ("CRB-9/1234")
tinha barra antes da barra do autor.

## M3 — A ponte doutrina ↔ lei: o Código anotado ✓ FEITA

- `src/biblioteca/anotacoes.py`: na indexação, cada citação com instrumento
  ("art. 18 do CDC") achada num trecho do material vira anotação do artigo,
  em `<material>/biblioteca.db` — com a página e a frase, conferida por
  `alinhar.py` no pedaço do arquivo de onde o trecho saiu. Sem instrumento
  não liga ("como visto no art. 18"). Tirar o material tira as anotações.
- Na tela da lei (painel "Citar a lei"), cada artigo mostra **"Na biblioteca
  do escritório"**: obra, autor, edição, ano, página, um trecho de até 300
  caracteres e "abrir na página" (o PDF do escritório no visor, na página).
  Artigo sem obra: "nenhuma obra da biblioteca cita este artigo".
- Na pergunta que cita o artigo com o instrumento, os trechos anotados são a
  terceira lista da RRF.
- Chave `biblioteca.anotacoes`, ligada de fábrica depois do portão.

**Medido:** as 26 anotações das duas obras da demonstração, conferidas à mão
contra o PDF: página certa em 26, **zero** ligação a código errado. Perguntas
por dispositivo: **Recall@6 1,0** (antes 0,83). Ruído 0,0. Roteiro 40/41 (=
controle).

**O que a verificação achou:** a frase do título "4.1 O art. 18 do CDC" casava
primeiro no sumário, e a página saía a 3 (agora confere dentro do trecho); no
PDF a citação quebra de linha ("art. 421 do Código⏎Civil") e perdia o
instrumento — a quebra simples vira espaço, do mesmo tamanho.

## M4 — A resposta em camadas ✓ FEITA

- `src/biblioteca/camadas.py`: o que a busca trouxe da biblioteca vai ao
  modelo em blocos com rótulo e teto próprio, nesta ordem: LEI (texto do
  Planalto, até 2 artigos, o caput sempre inteiro e só os incisos citados),
  SÚMULA, DOUTRINA ("o que autores sustentam; não é texto de lei"),
  COMUNIDADE (cercada como dado, pela blindagem), MODELOS DA CASA e MATERIAL.
  Orçamento total da biblioteca: o de hoje, 2400 caracteres.
- Depois da resposta, por regra (`conferir_doutrina`): frase que atribui a
  doutrina à lei ("o CDC diz que…" com texto de obra) é reescrita para
  "Segundo <autor>," ou marcada "(posição doutrinária)"; a marca [Tn] só
  fica na frase que o trecho sustenta (`citacoes.revisar`).
- As fontes da resposta mostram a camada ("Lei", "Doutrina", "Modelo da
  casa").
- **A ordem do contexto importa para a velocidade:** com a biblioteca antes
  dos documentos, o Ollama perde o prefixo guardado e a pergunta do manual
  foi de 10 s para 55 s. Os documentos vão primeiro e a biblioteca depois.
- Chave `biblioteca.camadas`, ligada de fábrica depois do portão.

**Medido (44 perguntas):** Recall@6 0,903 (lei pura 1,0; antes 0,17 com o
CDC só como material), ruído 0,0, acerto 36/44, 2 "não encontrei"
indevidos, **0 citação inventada, 0 doutrina apresentada como lei** (6
atribuídas ao autor). Roteiro 40/41 (= controle) depois de uma correção
achada na medição final: o material sem ficha tem de ir ao modelo com o
rótulo de antes, letra por letra. Com um rótulo mais curto, o 3B deixou de
achar os 20% do contrato ao lado da tabela do manual (3 vezes em 3).

## M5 — Leitura da obra em segundo plano ✓ FEITA (chave desligada de fábrica)

- `src/biblioteca/leitura.py`: um fio em segundo plano, no molde do
  `Backfill`, cedendo a vez à fila do modelo, trecho por trecho (o trecho do
  regime C nunca atravessa capítulo) e retomável; o modelo da tarefa
  `leitura` devolve conceitos e posições por JSON Schema (`format` do
  Ollama). Toda `quote` passa pelo `alinhar.py`; a que não casa some. Os
  artigos da tese saem da frase conferida, por regra. Guardado com extrator,
  modelo, digest e versão do prompt; trocar o modelo marca `stale`.
- Na tela: glossário e teses no menu de cada obra; na tela da lei, a tese do
  autor sobre o artigo em destaque; na busca, o termo definido aponta para o
  trecho que o define.
- Adaptação: `jobs.py` são os trabalhos da conversa, não uma fila de fundo.

**Medido com o llama3.2:3b** (os 20 trechos das duas obras, 519 s, 0 frase
fora do livro): teses 28/30 certas (93%), conceitos 23/52 (44% — item de
lista tomado por conceito, um termo inventado), **62% no total**, abaixo dos
80% do portão: a chave `biblioteca.leitura` fica desligada de fábrica. Com
ela ligada, os sinônimos ficam em 4/7 (não cai nem sobe) e a lei pura cai de
1,0 para 0,83 de Recall@6.

## M6 — Aviso de obra anterior à redação atual ✓ FEITA

- `leis.ano_da_alteracao`: o ano mais recente das notas "(Redação dada
  pela…)", "(Incluído pela…)", "(Revogado pela…)" do artigo inteiro (caput,
  parágrafos, incisos). Calculado do texto guardado: vale também para o
  código importado antes, sem reimportar. "(Vide…)" não conta.
- `src/biblioteca/defasagem.py`: obra com ano menor que a alteração do
  artigo que ela comenta → "Obra de 2015; este artigo teve a redação alterada
  em 2021. Confira se o comentário ainda vale." Sem ano na ficha: "Ano da
  obra desconhecido; confira a redação." Na resposta em camadas (no fim, para
  os trechos de doutrina que a resposta cita) e na tela da lei. Não esconde e
  não decide: só avisa.
- Chave `biblioteca.defasagem`.

**Medido:** 20 artigos com alteração conhecida e 10 sem, no CDC e no CC do
Planalto: `alterado_em` certo nos 30 (gabarito conferido lendo as notas de
cada um). Obra anterior → aviso; posterior ou artigo sem alteração → nenhum.

## M7 — O que o PAULUS sabe ✓ FEITA

- `src/biblioteca/mapa.py`: a área da pergunta por regra — o artigo citado
  com o código decide; senão, o vocabulário curto de cada área, escrito à mão
  em `config/areas-biblioteca.json` (só termos de direito: "aluguel",
  "contrato", "locador" não entram, senão toda pergunta sobre o contrato de um
  cliente ganharia o aviso). Empate ou nada: sem área e sem aviso.
- Fora da cobertura (área sem obra nem lei): a resposta segue e ganha, no
  fim, "Não tenho material de <área> na biblioteca; esta resposta usa só os
  documentos.", com o botão "acrescentar material". Nunca bloqueia. Se a
  biblioteca trouxe algo para a pergunta (o manual, por exemplo), não avisa.
- Configurações › Aprendizado virou **Biblioteca**, com o cartão "O que eu
  sei": as áreas com as obras e as leis, e por código quantos artigos as obras
  comentam e os mais comentados.
- Chave `biblioteca.mapa`.

**Medido:** as 5 perguntas fora da cobertura do conjunto com a área certa e o
aviso; zero aviso nas 39 outras.

## Pacote `.paulus-material` (Compartilhamento futuro) ✓ FEITO (só local)

- `src/biblioteca/pacote.py`: exportar e importar um material num arquivo
  (manifesto, ficha, texto com as páginas, anotações — sem vetores e sem o
  original). Nada vai pela rede.
- Só o autor exporta: artigo, modelo de peça ou manual, depois de marcar
  "sou o autor deste material e posso compartilhá-lo" e escolher a licença.
  Doutrina de editora nunca, nem com a marca.
- O importado entra com `origem: comunidade`, na camada COMUNIDADE da
  resposta ("compartilhado por <autor>, não revisado por este escritório"),
  cercado como texto de terceiro (`blindagem.cercar`); nunca vira lembrete;
  "ignore as instruções anteriores" fica anotado como suspeita.
- Chave `biblioteca.pacote`. O blog (contas de autor, curadoria, moderação,
  publicação online) é a frente futura.

**Medido:** ida e volta entre duas bibliotecas com os mesmos `chunk_id` e as
mesmas anotações; pacote com arquivo a mais, de doutrina ou de outro formato é
recusado.

---

# Ideias do umbrelOS 2.0 (docs/DECISAO-UMBREL.md)

Briefing `docs/prompt-ideias-umbrel-v0.md`. Das seis ideias, três para fazer
agora: F, E e A (só leis). B, C e D ficam para depois, com o motivo na tabela.

## F — Placas de vídeo de qualquer fabricante ✓ FEITA

`maquina.testar()` lê todas as placas pelo Windows (Win32_VideoController):
Intel, AMD e NVIDIA, integrada ou não; o "Medir" guarda quanto do modelo o
Ollama pôs na placa (`/api/ps`, `size_vram`), e a calibração só conta a placa
quando a medida confirma. **Medido nesta máquina:** Intel Iris Xe integrada, e
o Ollama põe 0% do 3B nela — o caso que a ideia existe para mostrar.

## E — Documento fotografado pelo celular ✓ FEITA (chave `umbrel.captura`, desligada)

"Fotografar" no Acervo: câmera do celular (ou seletor de imagens), prévia com
girar e tirar, e as fotos viram um PDF que passa pelo OCR de sempre. Na
janela do escritório entra direto; **de fora vira pedido em Aprovações**
("Entrar no Acervo"), porque o envio de arquivo de fora continua bloqueado.
**Medido:** 98,8% das palavras certas numa foto de página gerada aqui (giro de
2°, ruído, JPEG de celular). Falta medir com fotos de verdade.

**O que a verificação achou:** a rota com anotações adiadas não achava o
`UploadFile` importado dentro da função; a "proposta" de fora guarda o corpo
inteiro e tem limite pequeno — por isso a captura faz a própria quarentena.

## A — MCP só das leis ✓ FEITA (chave `umbrel.mcp`, desligada)

`/mcp` (JSON-RPC 2.0, sem dependência nova) com `leis_instaladas`,
`citar_artigo` e `procurar_na_lei`: só texto de lei, que é público. Só deste
computador e nunca pelo túnel (o túnel também chega pelo 127.0.0.1: os
cabeçalhos da Cloudflare decidem); token por conexão, criado e revogado na
janela, guardado só o resumo SHA-256; cada chamada na auditoria. As chaves da
Biblioteca e do umbrelOS ligam e desligam em Configurações.

**Medido:** sem token, token errado e revogado → 401; outro endereço e túnel →
403; ferramenta fora da lista → negada; o catálogo não tem nada do Acervo, da
biblioteca ou de cadastro; as rotas de conexão bloqueadas de fora.

## Modelo de voz pesado: a tela sugere o mais leve ✓ FEITA (30/09/2026)

Pedido do dono: quando o modelo de transcrição for pesado demais e der erro
por isso, sugerir a troca por um mais leve, "clicando aqui".

- `src/transcricao.py`: a falta de memória virou `SemMemoria`, com o modelo
  mais leve que dá para sugerir (`mais_leve_que`). Vale para a conferência de
  antes de carregar e para o erro que o CTranslate2 dá no meio
  (`MemoryError`, "failed to allocate", `bad_alloc`), que antes chegava como
  erro qualquer. `situacao()` diz qual é o mais leve e se já está baixado.
- A gravação que falhou por memória leva `transcricao_sem_memoria`; o ao vivo
  devolve a frase inteira (503), para a tela reconhecê-la.
- Na tela (Gravações › Transcrição e no ao vivo): o motivo e "troque para o
  Whisper small, mais leve (0,5 GB; erra um pouco mais em nomes e números),
  clicando aqui". Baixado: troca e transcreve de novo. Não baixado: baixa uma
  vez e recomeça sozinha. Ao vivo: troca e volta a ouvir.
- Portão: `tests/test_voz_mais_leve.py` (memória e faster-whisper simulados)
  e um caso novo em `tests/test_tela.py`.

## C0 — Levantamento da Conversa e dos Agentes ✓ FEITA

Prompt `docs/prompt-conversa-agentes-v0.md` (30/09/2026). A tabela "o prompt
supõe × o código tem hoje" está em `docs/PROGRESSO-CONVERSA.md`: tudo do §1
confere, com ressalvas (o rascunho não se perde, vaza para a outra conversa;
o vermelho da cobertura é só no bastidor; de fora, as ferramentas do chat já
passam pela fila; a cerca já existe na COMUNIDADE da Biblioteca; não há data
de aniversário do escritório nem coluna de OAB nos cadastros). Achado a mais:
fechar a janela deixava a thread do Ollama órfã com a vez na fila já
liberada. Ordem: a do prompt. A pausa da C0 não parou o trabalho (pedido do
dono: seguir direto e publicar).

## C1 — A resposta roda sem depender da janela ✓ FEITA

- `src/execucoes.py` + `src/rotas_execucoes.py`: a resposta da conversa roda
  numa thread de trabalho e cada evento vai, na hora, para um registro só
  acrescentado (`data/execucoes/<id>.jsonl`). A rota da pergunta vira uma
  inscrição nesse registro; `GET /api/execucoes/{id}/eventos?desde=n`
  reinscreve. Fechar ou recarregar a janela não para nada.
- Ao abrir o programa, a resposta que ficou pela metade entra na conversa como
  texto parcial, marcado como interrompido.
- Na tela, a leitura saiu de `enviar()` para `lerResposta()`, e todo efeito
  fora da resposta só vale com a conversa dela aberta: acabou o vazamento de
  título, foco e painel. Voltar para a conversa (ou recarregar) se reinscreve
  e redesenha o que já saiu.
- Chave `conversa.execucao`, ligada de fábrica.

**Medido:** `tests/test_c1_execucao.py` (modelo simulado que escreve devagar,
e o Edge pelo Playwright) passa inteiro; roteiro `--tudo` 41/41.

## C2 — A tela enquanto pensa ✓ FEITA

- Uma linha de estado no lugar da resposta ("Procurando em 29 documentos…",
  "Lendo 1 documento · ~42 s…", "Escrevendo…"); o "o que estou fazendo" vira
  "ver detalhes", recolhido, e fica guardado com a resposta (`src/detalhes.py`
  lê o registro da execução).
- Documento sem trecho vira contagem ("12 documentos sem nada sobre isso ·
  ver lista"); a resposta guardada só tem a contagem.
- As etapas vêm do servidor desde o primeiro evento; cartão e painel com a
  mesma conta. Vermelho só para erro. "Tentar de novo" funciona.
- Chave `conversa.pensando`, ligada de fábrica.

**Medido:** `tests/test_c2_pensando.py` passa inteiro (modelo simulado e o
Edge).

## C3 — Sobre esta resposta, a barra do escopo e o que é de cada conversa ✓ FEITA

- O painel descreve uma resposta — a última, ou a clicada em "ver fontes":
  fontes citadas (as marcas [Tn]), também lidas (recolhidas), como respondi e
  onde procurei, tirados do que a resposta guardou. O Progresso sai do
  painel; motor e índice só no modo de diagnóstico, com o motor de verdade.
- A barra acima do campo diz onde a próxima pergunta procura; com resposta
  andando, o que ela faz e o Parar. Uma linha de registro não sobe mais a
  conversa na lista.
- Rascunho, anexos, rolagem e modo de escopo ficam com cada conversa; a
  segunda pergunta com outra respondendo diz por quê e oferece esperar a vez.
- Celular: o painel começa fechado e abre como folha de baixo. A busca de
  conversas acha pelo texto das mensagens.
- Chave `conversa.painel`, ligada de fábrica; `conversa.diagnostico`,
  desligada.

**Medido:** `tests/test_c3_painel.py` passa inteiro (modelo simulado e o
Edge, 1440 e 390 px).

## T1 — A saudação que não se repete ✓ FEITA

- `config/saudacoes.json`: 130 títulos e 82 subtítulos, com as frases de
  antes, cada uma com as condições em que vale (momento, dia, calendário,
  chegada, situação). `src/saudacao.py` escolhe por regra, sem modelo: a
  situação forte fica sozinha, as outras camadas cedem a vez quando as frases
  delas estão entre as 20 últimas mostradas; sorteio entre as que sobram.
- Feriados nacionais e recesso pela tabela de `src/prazos.py`; nome de quem
  entrou (a conta de fora ou o titular); "de volta" cita a última conversa,
  com o atalho para abri-la; `escritorio.fundacao` para o aniversário.
- Chave `conversa.saudacao`, ligada de fábrica.

**Medido:** `tests/test_t1_saudacao.py` passa inteiro (relógio simulado e o
Edge); dez exemplos no PROGRESSO-CONVERSA.

## A1 — Formato de agente: carregar, validar e versionar ✓ FEITA

- `src/agentes.py`: lê `data/agentes/<slug>/AGENTE.md` (cabeçalho YAML +
  instruções), valida contra as capacidades carregadas, o
  `CATALOGO_FERRAMENTAS`, os perfis de modelo, as áreas da Biblioteca e as
  leis. Nome desconhecido (e campo com erro de digitação) é erro claro com o
  que existe; `modelo: llama3.2:3b` é recusado (é perfil de tarefa). Um agente
  com problema aparece com o motivo e não derruba os outros.
- Estado (ligado, origem escritorio|importado|produto, aprovação) em
  `estado.json` ao lado do arquivo; a versão fica no cabeçalho, e cada edição
  guarda a anterior em `versoes/<n>.md`, mudando só a linha `versao:`.
- Importar SKILL.md/AGENTE.md: `name`/`description` → `nome`/`descricao`,
  campos de outro programa listados na ficha, original guardado, suspeitas da
  blindagem anotadas; entra desligado e só liga com `vi_o_conteudo: true`.
- `src/rotas_agentes.py`: listar, ler, versão, criar, salvar, ativar,
  desativar, importar, testar. Escrever é TITULAR (janela local ou titular);
  ler e testar, PERMITIDO. Nenhuma ferramenta é executada no teste.
- Chave `conversa.agentes`, ligada de fábrica. `pyyaml` declarado no
  requirements.

**Medido:** `tests/test_a1_agentes.py` 67/67; `tests/test_r3_permissoes.py`
58/58, 477 pares com política.

## A2 — O agente do escritório na conversa ✓ FEITA

- Escolha por regra (`src/agente_na_conversa.py`): barra ou "@Nome" → exemplos
  e palavras → juiz só entre candidatos → sem candidato, como antes. A
  sugestão aparece na barra antes de enviar (`GET /api/agentes/sugerir`), com
  um seletor para trocar ou não usar.
- As instruções do agente entram no fim da instrução de sistema, abaixo das
  regras do produto, cercadas e rotuladas; `fontes` só restringe o que a busca
  lê; o perfil de modelo é o do agente.
- Ferramenta não declarada: recusada e registrada. Declarada: o cartão da
  conversa e o pedido na fila de Aprovações são o mesmo — confirmar num fecha
  o outro.
- A resposta guarda agente, versão e como foi escolhido (assinatura e painel).

**Medido:** `tests/test_a2_agente_na_conversa.py` passa inteiro.

## T2 — Carrossel de avisos, Central de avisos e histórico ✓ FEITA

- `src/central_avisos.py` junta os avisos do dia (prazo, compromisso, data de
  documento, a pagar e a receber, publicação do DJEN, tarefa, aprovação,
  conversa pela metade, lembrete do Vigia) sem mudar a regra de nenhuma fonte,
  com id estável pela origem e pela data, sem duplicado, na ordem atrasado →
  hoje → amanhã → esta semana.
- Tabela `avisos_vistos` (migração 026): visto por pessoa, com hora, de onde e
  a cópia do que o aviso dizia. Visto não conclui nada; prazo visto volta no
  dia do vencimento.
- Carrossel na tela inicial (arrasto, setas, teclado, o círculo das tarefas;
  lista no celular) e a Central de avisos com Hoje, Todos e Histórico. O Vigia
  usa os mesmos ids.
- Chave `conversa.avisos`, ligada de fábrica.

**Medido:** `tests/test_t2_avisos.py` 83 ok.

## C5 — As outras superfícies de IA ✓ FEITA EM PARTE

- O bug do documento errado: a sugestão do painel de Documentos (e a folha
  timbrada e a fórmula da planilha) só entra no documento que a pediu; com
  outro aberto, espera o de origem e aparece nele quando ele abre.
- Um leitor de SSE só (`eventosSSE`), usado pela conversa, pelo organizador e
  pelo `lerEventos`.
- `src/ia_em_fundo.py`: o parecer do Financeiro, o resumo da gravação e o
  reescrever do e-mail como execução, na fila do modelo (com a posição),
  com Parar e com o resultado que volta ao sair, recarregar ou reabrir. Um
  componente de tela para "IA trabalhando".
- Ficou para depois: as outras nove superfícies, o texto chegando aos poucos
  nelas, e a fila do modelo para quem não passa pela execução.
- Chave `conversa.superficies`, ligada de fábrica.

**Medido:** `tests/test_c5_superficies.py` passa inteiro (modelo simulado e o
Edge).

## C4 — Roteamento: perguntas sobre o programa e consultas de cadastro ✓ FEITA

- Mapa ampliado: Publicações e DJE, Buscar em tudo (Ctrl+K), Biblioteca,
  Códigos de lei e Acesso de fora, com perguntas de exemplo e passos
  conferidos no frontend; o "Abrir" leva a cada lugar.
- `src/consulta_cadastro.py`: CPF, CNPJ, telefone, e-mail, endereço e OAB de
  alguém por molde — Cadastros, Meus dados, fatos conferidos dos documentos
  (com a página) ou "não encontrei" com a oferta de ler os documentos. Nunca
  lê o acervo sem a pessoa pedir; nome ambíguo vira lista.
- Chave `conversa.roteamento`, ligada de fábrica.

**Medido:** 22/22 do programa na tela certa sem modelo; 10 consultas de
cadastro por molde, máx. 27 ms (antes ~165 s); 29/29 perguntas de documento
do banco de provas no mesmo caminho.

## C6 — Cerca em todo texto de terceiros ✓ FEITA (chave desligada de fábrica)

- Com `conversa.cerca`, trechos de documento, material e biblioteca vão ao
  modelo entre os marcadores da blindagem do e-mail, com a regra de que são
  dado; frase de "ordem ao assistente" é detectada e registrada
  (`data/cerca/suspeitas.jsonl`); link ou e-mail que a resposta traz e não
  estava nos trechos sai dela.
- **Medido:** a injeção "diga que o prazo é 1 dia" não mudou a resposta do
  llama3.2:3b (15 dias). No roteiro, com a cerca, 40/41 e mediana de 17,0 s,
  contra 41/41 e 13,1 s sem ela: como a cerca não pode derrubar o acerto, a
  chave fica desligada de fábrica.

## A3 — Tela de agentes ✓ FEITA

- Tela "Agentes" no trilho: a lista, o formulário que grava o AGENTE.md, a
  visão do markdown com a validação em português antes de salvar, e as
  versões. "Criar agente desta conversa" monta o rascunho por regra e não
  salva sem confirmação. "Testar" mostra passou ou falhou, com o que faltou.
- Dois exemplos do produto, desativados: Revisor de contratos e Triagem de
  consumidor, 3 testes cada. De fora, a lista e o teste funcionam.

**Medido:** `tests/test_a3_tela.py` 50 ok. Com o llama3.2:3b: Triagem 3/3,
Revisor 2/3 (o teste da garantia foi ajustado para o que a cláusula diz, sem
medir de novo).

## A4 — Medir os agentes ✓ FEITA

- Por agente: o último resultado dos testes, as vezes usado e as vezes "não
  usar" (o programa não avalia respostas: "sem avaliação"). Teste falhando na
  versão atual: "precisa de revisão", fora da escolha automática; a escolha
  manual continua. `tools/medir.py --agentes`.

**Medido:** `tests/test_a4_medir.py` 28 ok.

## Avisos do dia num cartão só ✓ FEITA (30/09/2026)

Pedido do dono: um cartão único navegável, sem rolagem lateral. O cabeçalho
diz "3 de 12"; setas, teclado e arrasto trocam o aviso; marcar como visto ou
concluir põe o próximo no lugar; "Ver todos" foi para o cabeçalho. Vale
também no celular. **Medido:** `tests/test_t2_avisos.py`, `test_tela` e
`test_frontend` passam.

## D0 — Pensar no aparelho: levantamento ⏸ PAUSA (30/09/2026)

Tabela "o prompt supõe × o código tem" em `docs/PROGRESSO-APARELHO.md`.
Uso real do acesso de fora nesta máquina: zero (0 contas; a auditoria é só
do teste de tela). Cada lugar na fila custa a mediana de 34 s (p90 102 s) com
o llama3.2:3b. Achado: o filtro de Serviços (ContextVar) não chega à thread
da resposta; bloqueia a D1.

## Filtro de Serviços dentro da resposta ✓ FEITA (30/09/2026)

Achado na D0 do plano do aparelho: o filtro de Serviços por equipe (ContextVar)
não chegava à thread da resposta, e um colaborador de fora recebia trecho de
Serviço que não é dele. A execução e o fluxo das habilidades agora levam o
contexto de quem pediu. **Medido:** `tests/test_seg_filtro_na_thread.py` 5 ok
(antes: 2 falhas, o parecer do B no contexto e nas fontes da Sara).
