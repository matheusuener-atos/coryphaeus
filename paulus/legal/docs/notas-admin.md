# Notas Admin (a NFS-e dos assinantes)

A NFS-e que o PAVLVS emite para quem assina o PAULUS sai do **PAULUS da casa**:
o PAULUS do servidor do escritório do dono, numa tela à parte ("Notas do
PAVLVS", ícone de nota no trilho). Pelo túnel (`<nome>.paulus.ia.br`), só o
titular entra. Os PAULUS dos clientes não têm essa tela.

Ela usa o mesmo emissor dos escritórios (`src/nfse/`), numa instância
separada: banco `dados/pavlvs/pavlvs.sqlite3`, certificado e configuração
próprios. O emissor do escritório continua como está.

## Como a tela aparece

Sozinha, sem chave nem configuração: o PAULUS ligado à nuvem com uma conta
Google que está na equipe do painel admin como **dono** ou **financeiro**
(Equipe, em paulus.ia.br/admin) mostra a tela. A nuvem confere a cada 30 min.
Nos PAULUS dos clientes a nuvem responde que não, e a tela não existe. A
ponte com o painel usa o mesmo segredo da instalação que o PAULUS já usa com
a nuvem.

## Começar

1. Na tela: certificado A1 do CNPJ do PAVLVS e a senha (uma linha);
   **Parâmetros**: inscrição municipal, endereço, regime, código do serviço,
   NBS e IBS/CBS (o contador diz; os da advocacia não servem).
2. **Testar comunicação**: certificado, servidor da Sefin (com o certificado
   na conexão), cidade conveniada e a ponte com o painel.
3. Emita uma nota no ambiente de testes; depois, Parâmetros › Produção ›
   **Mudar para produção**.

## No dia a dia

- **Emitir NFS-e**: escolha o cliente (vem do cadastro da assinatura) e, se
  quiser, o pagamento sem nota (preenche valor, descrição e competência).
  O clique em Emitir é a aprovação.
- **Clientes**: os dados fiscais de cada assinante (endereço, e-mail, CPF ou
  CNPJ). O que se edita aqui fica no Worker para as notas; o cadastro original
  da conta não muda.
- **Lista**: PDF, imprimir, XML e **Enviar ao cliente**: no PAULUS dele aparece
  "Sua NFS-e de setembro/2026 chegou", com Download e XML.
- **Painel (paulus.ia.br/admin › Notas fiscais)**: "Emitir ao confirmar o
  pagamento" faz a casa emitir sozinha, a cada 5 min, os pagamentos pendentes
  de clientes com dados fiscais completos (o que falta fica anotado e é
  tentado de novo em 6 h). "Enviar PDF e XML ao cliente" manda a nota ao app
  dele logo depois de emitir. Os dois só valem com o PAULUS da casa ligado.

- **Cancelar**: motivo da tabela oficial e a descrição (15 a 255 caracteres),
  dentro do prazo do município. O app do cliente é avisado.
- **Substituir**: uma nota nova no lugar da antiga, com o que estava errado
  corrigido (tomador, valor, descrição, competência); a Sefin cancela a antiga
  sozinha. No Simples, tomador, valor e competência não mudam (E0061). A
  substituta vai ao app do cliente, ligada ao mesmo pagamento.
- **E-mail**: "Mandar também por e-mail" (nos Parâmetros ou no painel) manda
  o PDF e o XML anexos ao e-mail fiscal do cliente, pelo Resend do Worker.

## O que não faz

- emitir com o servidor desligado: o pagamento espera na lista do painel e
  sai na primeira rodada depois que ele ligar (até 5 min).
