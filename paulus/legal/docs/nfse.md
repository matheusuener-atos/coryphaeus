# Nota fiscal de serviço (NFS-e) no PAULUS

O PAULUS emite a NFS-e pelo **Padrão Nacional**: monta a DPS, confere,
assina com o certificado A1 do escritório e envia ao Sistema Nacional da
NFS-e. Começa em **produção restrita** (testes, sem valor fiscal) e só passa
para a produção quando o titular libera.

O PAULUS **não faz planejamento tributário**. Ele aplica a configuração
fiscal que o escritório (ou o contador) definiu, mostra a conta e avisa
quando algo não bate. Na dúvida tributária, a resposta é do contador.

## 1. Configurar (uma vez): o passo a passo

Configurações › **Nota fiscal**. Só na janela do computador do escritório.
A tela é um passo a passo, com o caminho no alto (✓ no que está feito):

1. **Certificado:** o A1 do escritório (.pfx ou .p12), com a senha — o mesmo
   que ele usa na prefeitura. Separado do certificado de assinar PDF. Do
   certificado o PAULUS já tira o CNPJ (ou CPF) e o nome. "Guardar a senha
   neste computador" vem marcado, para a fila poder enviar sem você; sem
   isso, a senha vale 15 minutos. O A3 (token) não serve, nem o certificado
   instalado no Windows sem exportar.
2. **Escritório:** CNPJ, inscrição municipal, cidade (digite o nome e
   escolha), endereço, telefone e e-mail. Ao gravar, o PAULUS pergunta
   sozinho ao Sistema Nacional se a cidade emite por ele. Sem convênio, a
   tela diz, e a nota continua sendo emitida no sistema da prefeitura e
   **registrada** no Financeiro, como antes.
3. **Impostos:** como o escritório paga impostos (lucro presumido ou real,
   Simples, MEI), se o ISS é fixo por profissional (sociedade de advogados ou
   autônomo), a área de atuação (vira a NBS), a alíquota do ISS da cidade e o
   texto padrão da nota. Em **Mais opções**, para conferir com o contador:
   retenções ("Não sei — perguntar ao contador" deixa a retenção desligada),
   IBS/CBS (já vem com a sugestão da tabela oficial para a advocacia, cClassTrib
   200052 e cIndOp 100301 — confirme), total aproximado de tributos, códigos e
   o contato do contador. Cada gravação é uma versão: a nota emitida guarda a
   versão com que foi feita.
4. **Teste:** escolha um cliente do Cadastro (com endereço completo) e clique
   em **Fazer o teste**. O PAULUS emite uma nota de R$ 1,00 no ambiente de
   testes do governo (produção restrita, sem valor fiscal) e a cancela em
   seguida, mostrando cada etapa. Nada vai ao cliente: nem e-mail, nem
   registro no Financeiro; o XML fica em Notas fiscais/Testes. Se falhar, a
   tela diz o motivo (a frase da Sefin); corrija e teste de novo. Mudou a
   configuração depois, o teste vale para a de antes e a tela pede outro.
5. **Produção:** com o teste passando, a tela diz **"Tudo certo!"** e
   mostra **Mudar para produção** (seção 11).

## 2. Emitir

Quatro portas levam ao **mesmo cartão**:

- **Financeiro:** no recebimento sem nota, **Emitir nota**.
- **Serviço:** em Horas, **Emitir nota dos honorários**.
- **Conversa:** "emita a NFS-e da ACME de R$ 5.000,00 referente a setembro"
  → **Preparar a nota**. A conversa só cria o rascunho.
- **Todo mês** (seção 9).

### O cartão

- **Tomador:** vem dos Cadastros. O que faltar (endereço com o município do
  IBGE, por exemplo) é pedido; completar no cartão grava também na ficha,
  onde estava vazio.
- **Serviço:** valor, competência (o início da prestação), descrição,
  município da prestação, desconto e informações complementares.
- **A conta**, linha a linha, com a regra de cada uma: base e ISS (previsão),
  retenções, valor líquido e, em 2026, a previsão de CBS 0,9% e IBS 0,1% (LC
  214/2025; em 2026 não há recolhimento para quem cumpre as obrigações
  acessórias). O ISS próprio, o IBS e a CBS são calculados pela Sefin: a
  nota emitida mostra os valores dela, e o PAULUS avisa se diferirem.
- **Erros** (bloqueiam) e **avisos** (não bloqueiam): tomador sem endereço,
  valor diferente do recebimento, competência de mês anterior, certificado
  vencendo, município do tomador diferente…
- **Ver a DPS (XML)**: a prévia; o número definitivo é reservado ao assinar.

**Conferir** refaz a conta e confere a DPS no XSD oficial.

## 3. Aprovar

**Pedir aprovação** põe a nota em Aprovações ("Emitir NFS-e — ACME — R$
5.000,00"), com a conta e a DPS resumida. Aprovam o titular e quem ele
liberar (Escritório e equipe › nível "Emitir nota fiscal"). De fora, o
PAULUS pede o código do autenticador de novo. Agente nenhum aprova nem
emite. Esperando aprovação, a nota não se edita.

## 4. A nota vai ao Sistema Nacional

Depois do sim: o número da DPS é reservado, a DPS é montada, validada no XSD
oficial, assinada e enviada. O cartão mostra o estado:

| Estado | O que quer dizer |
| --- | --- |
| Emitida | A Sefin gerou a NFS-e. O XML e o DANFSe vão para o Acervo (pasta do Serviço, ou Notas fiscais/<cliente>), a nota entra no registro do Financeiro e o recebimento sai da lista "sem nota". Um e-mail ao cliente, com o PDF e o XML, fica proposto em Aprovações. |
| Rejeitada | A Sefin recusou: o cartão mostra o código oficial, a frase e o campo. Corrija e peça a aprovação de novo — a nota volta com a **mesma** identidade de DPS. |
| Aguardando confirmação | O pedido pode ter chegado e a resposta não voltou. **O PAULUS não reenvia às cegas:** consulta a DPS no Sistema Nacional; se a nota existe, fica emitida; se não existe, manda a mesma DPS de novo. |
| Na fila | Não deu para falar com o Sistema Nacional. A fila tenta de novo com espera crescente (1, 2, 5, 10, 20, 40, 60 minutos) e avisa se parar. A nota nunca some. |

**Se a nota ficar aguardando confirmação:** não emita outra igual por fora.
Abra o cartão e clique em **Consultar e mandar** (ou espere a fila). Se o
programa fechar no meio do envio, ao abrir ele consulta antes de qualquer
reenvio.

## 5. Cancelar

No cartão da nota emitida: **Cancelar a nota**, com o motivo da tabela oficial
(1 – Erro na emissão, 2 – Serviço não prestado, 9 – Outros) e a descrição (15
a 255 caracteres). O pedido vai para Aprovações. O prazo é do município: fora
dele, o PAULUS recusa e explica; sem o prazo nos parâmetros, quem decide é a
Sefin (rejeição E0822). Cancelada, a nota fica marcada no registro e o
recebimento volta para "sem nota".

## 6. Substituir

**Substituir** cria uma nota nova (rascunho) que substitui a emitida, com o
motivo da tabela oficial (01 a 05, ou 99 – Outros). Emitida a nova, a Sefin
cancela a antiga sozinha, e as duas ficam ligadas no PAULUS. No Simples
Nacional, tomador, competência e valor não mudam (regra E0061).

**Atualizar situação** consulta os eventos da nota: um cancelamento feito
pelo município (por ofício) aparece aqui.

## 7. DANFSe

O documento auxiliar é gerado pelo PAULUS a partir do XML, no leiaute da NT
008 (a API do DANFSe do Ambiente Nacional foi suspensa em 03/08/2026), com o
QR Code da consulta pública. Em produção restrita traz "NFS-e SEM VALIDADE
JURÍDICA". **Abrir o DANFSe** no cartão. Diferenças conhecidas: a fonte é a
Helvetica do PDF (de métrica igual à Arial pedida) e a logomarca oficial não
vem embutida.

## 8. Para o contador

Configurações › Nota fiscal › **Abrir o relatório do mês** (ou Financeiro ›
Notas fiscais): o mês da **competência**, com as notas emitidas, canceladas e
substituídas, os totais (somados dos XMLs) e a diferença recebido × faturado.
A **conferência** acha recebimento sem nota, nota sem recebimento, valor
divergente, retenção configurada e não aplicada, competência de outro mês e
certificado vencendo.

- **Exportar para o contador:** um .zip no Acervo (Notas fiscais/Contador)
  com todos os XMLs do mês (DPS, NFS-e, pedidos e eventos), uma planilha e um
  leia-me.
- **Mandar ao contador:** o mesmo .zip, por e-mail, depois do sim em
  Aprovações.

**Guarda:** os XMLs ficam na pasta de dados do PAULUS (que vai no backup
cifrado) e uma cópia no Acervo. Nota emitida não se apaga: cancela-se. O
mínimo legal é o do CTN (art. 195, parágrafo único: até a prescrição dos
créditos); a lei do município pode pedir mais — pergunte ao contador.

## 9. Todo mês

No Serviço, Horas › **Nota todo mês**: o dia e o valor. No dia, o PAULUS cria
o rascunho da nota do mês e o põe em Aprovações. **Nunca emite sozinho.** Se
faltar algo (o endereço do cliente, por exemplo), o rascunho espera por você,
com aviso. As recorrências ficam listadas em Configurações › Nota fiscal,
com "Desligar".

## 10. Avisos

No carrossel, uma vez cada: nota emitida hoje, recusada, aguardando
confirmação, fila parada, rascunho do mês, certificado a 30, 7 e 1 dia de
vencer, parâmetros do município que mudaram (a consulta é refeita todo mês) e
esquema novo publicado no portal da NFS-e (o PAULUS confere a página oficial
uma vez por mês).

## 11. Produção

Configurações › Nota fiscal › passo 5, só o titular. Libera quando:

1. a configuração está completa;
2. o certificado está válido;
3. o município tem convênio confirmado;
4. o teste do passo 4 passou com a configuração de agora.

Recomendados, sem travar: a configuração conferida pelo contador
("Registrar que o contador conferiu") e o backup configurado.

**Mudar para produção** grava quem e quando. A primeira nota de produção
pergunta: "Esta nota vale de verdade. Conferiu os dados?". **Voltar para o
ambiente de testes** tranca de novo.

## 12. Rejeições comuns

| Código | O que é | O que fazer |
| --- | --- | --- |
| E0014 | A DPS já gerou nota | Nada: o PAULUS consulta e fica com a nota que existe. |
| E0010 | Série fora da faixa | Não deveria acontecer: o PAULUS usa a série 1, na faixa de aplicativo próprio (1 a 49999). |
| E0015 | Competência depois da emissão | Corrija a competência. |
| E0037 | Município sem convênio | O município não emite pelo nacional: emita na prefeitura e registre. |
| E0121 | Nome do prestador na DPS | Não deveria acontecer (o PAULUS não manda): avise o suporte. |
| E0160 | Situação no Simples diferente do cadastro | Confira o regime com o contador. |
| E0237 | Tomador sem endereço com ISS retido | Complete o endereço do tomador. |
| E0310 / E0316 | Código de serviço ou NBS fora da lista | Escolha da tabela oficial (importe a planilha nova, se o portal publicou). |
| E0322 | IBS/CBS sem NBS | Escolha a NBS em Configurações. |
| E0588 / E0604 | Regime especial com ISS retido ou alíquota | Com regime especial, sem ISS retido e sem alíquota. |
| E0595 | Alíquota acima de 5% | Corrija a alíquota. |
| E0617 / E0619 | Alíquota que não devia (ou devia) ir | O PAULUS decide pela regra; se aparecer, confira o regime e o convênio do município. |
| E0822 | Cancelamento fora do prazo | Use a substituição, ou peça análise fiscal ao município. |
| E0850 | IBS/CBS antes de 2026 | Competência anterior a 2026 não leva o grupo. |
| E1200–E1209 | Certificado de transmissão | Certificado ICP-Brasil, válido, com CNPJ/CPF e LCR acessível. |
| E1235 | XML fora do esquema | Não deveria acontecer (o PAULUS confere no XSD): avise o suporte. |

## 13. Quando procurar o contador

- regime, regime especial de ISS e anexo do Simples;
- quando reter IRRF, PIS, COFINS, CSLL, CP e ISS, e de quais tomadores;
- o CST do PIS/COFINS, o CST e o cClassTrib do IBS/CBS, a NBS de cada área;
- o total aproximado de tributos;
- se o Simples deve mandar o grupo IBS/CBS ainda em 2026;
- o prazo de guarda pela lei do município;
- antes de mudar para produção (recomendado; a conferência aparece no passo 5).

## 14. O que o PAULUS não faz

- integração com o sistema próprio de prefeitura (ABRASF e outros): no
  município sem convênio, a nota é emitida lá e registrada aqui;
- certificado A3 (token);
- emissão sem aprovação humana — por agente, recorrência ou automação;
- reenvio sem consulta;
- decidir regra tributária que a documentação não resolve;
- boleto ou cobrança.

Os nomes dos campos JSON da API não estão em documento público (o Swagger só
abre com certificado). O PAULUS confere esses nomes no Swagger oficial na
primeira conexão com o certificado do escritório; se algum faltar, o envio
fica travado até alguém conferir.
