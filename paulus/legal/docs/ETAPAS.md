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

Fica para a Etapa 12: conferir prazos do documento contra os prazos da lei.

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

## Etapa 12 — Escrever melhor

**Telas:** Editor de texto · Planilha · Pré-visualização
**Tamanho:** grande
**Depende de:** Etapa 11

- Editor: alinhar, recuo, tabela, fonte e corpo, régua e indicador de página
- Numerar cláusulas, referência cruzada, qualificação das partes
- Comentário do assistente ancorado no trecho, dentro do texto
- Controlar alterações
- Planilha: mesclar, bordas, congelar, filtrar, ordenar, gráfico, resumo da seleção
- Pré-visualização: comparar versões lado a lado, duas páginas, tela cheia,
  imprimir, e o timbre do escritório no PDF

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
