# Notas do PAVLVS (a NFS-e dos assinantes)

A NFS-e que o PAVLVS emite para quem assina o PAULUS sai do **PAULUS da casa**:
o PAULUS do servidor do escritório do dono, numa tela à parte ("Notas do
PAVLVS", ícone de nota no trilho). Pelo túnel (`<nome>.paulus.ia.br`), só o
titular entra. Os PAULUS dos clientes não têm essa tela.

Ela usa o mesmo emissor dos escritórios (`src/nfse/`), numa instância
separada: banco `dados/pavlvs/pavlvs.sqlite3`, certificado e configuração
próprios. O emissor do escritório continua como está.

## Ligar (uma vez)

1. No Worker: `npx wrangler secret put NFSE_CASA_TOKEN` (uma chave longa e
   aleatória). Confira que a aplicação do Cloudflare Access cobre só `/admin*`
   e `/api/admin*`: a ponte `/api/nfse-casa/*` fica fora dela.
2. No servidor: ligue a tela com `PAULUS_CASA_PAVLVS=1` no ambiente de quem
   abre o PAULUS, ou `"casa_pavlvs": true` no `config.json` da pasta de dados.
   Reabra o PAULUS.
3. Na tela: certificado A1 do CNPJ do PAVLVS e a senha (uma linha);
   **Parâmetros**: inscrição municipal, endereço, regime, código do serviço,
   NBS, IBS/CBS (o contador diz; os da advocacia não servem) e a **chave da
   ponte** (a mesma do passo 1, guardada cifrada).
4. **Testar comunicação**: certificado, servidor da Sefin (com o certificado
   na conexão), cidade conveniada e a ponte com o painel.
5. Emita uma nota no ambiente de testes; depois, Parâmetros › Produção ›
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

## O que não faz (ainda)

- cancelar ou substituir nota por esta tela (o emissor sabe; falta o botão);
- mandar a nota por e-mail (vai ao app do cliente);
- emitir com o servidor desligado: o pagamento espera na lista do painel.
