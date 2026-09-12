# Especificação de interface — PAULUS Legal

Pacote de desenho para implantação na interface que já existe
(`paulus/legal/frontend/`, servida pelo FastAPI de `paulus/legal/src/api.py`
dentro da janela pywebview).

Não é proposta de stack. Não sugere framework, não sugere reescrita de backend.
Descreve **o que desenhar e como**, com medidas, cores, textos e comportamento,
para que a interface atual seja levada ao desenho aprovado sem adivinhação.

## O que está aqui

| Arquivo | Conteúdo |
|---|---|
| `00-fundamentos.md` | Cores (claro e escuro), tipografia, espaçamento, raios, sombras, ícones, movimento |
| `01-shell.md` | Barra de título, trilho, menu, cabeçalho de página, painel direito, rodapé, tema |
| `02-componentes.md` | Inventário de componentes com CSS exato |
| `03-telas-desktop.md` | A0a–A16, tela a tela, visão a visão |
| `04-telas-mobile.md` | M0–M14 e as regras de adaptação para 390×844 |
| `05-interacoes-e-estados.md` | Diálogos, avisos, estados vazios, carregando, erro, teclado, acessibilidade |
| `06-ordem-de-implantacao.md` | Ordem de trabalho, critérios de aceite por tela |

## Como usar

1. Leia `00` e `01` antes de qualquer tela. Quase tudo na interface é repetição
   dos mesmos seis ou sete componentes; acertar o fundamento resolve 80% do resto.
2. Para cada tela, abra o mockup correspondente ao lado do texto. O mockup manda
   no que o texto não cobrir.
3. Os HTML dos mockups são **referência de desenho**, não código para copiar.
   Foram escritos com estilo em linha, para ler rápido. Na implantação, o estilo
   vive no CSS da interface, com as variáveis de `00-fundamentos.md`.

## Os mockups

Arquivos `.dc.html` na raiz do pacote de desenho. Abrem direto no navegador.

| Mockup | Tela | Visões |
|---|---|---|
| `A0a - Boas-vindas` | Primeira execução, quem cria o escritório | boasvindas · escritorio · dados · ia · conexoes · atualizacoes |
| `A0b - Entrar no escritorio` | Primeira execução, quem entra por código | boasvindas · escritorio · dados · codigos |
| `A1 - Assistente` | Assistente | inicio · conversa · editor |
| `A4 - Agenda` | Agenda | mes · semana · tarefas |
| `A5 - Acervo` | Acervo | documentos · organizar · prazos |
| `A6 - Documentos` | Documentos | editor · planilha · previa |
| `A7 - E-mail` | E-mail | caixa · novo · contas |
| `A8 - Assinatura` | Assinatura | assinar · certificado |
| `A9 - Financeiro` | Financeiro | geral · lancamentos · relatorios |
| `A10 - Cadastros` | Cadastros | clientes · equipe · despesas |
| `A11 - Aprovacoes` | Aprovações | fila · historico · regras |
| `A12 - Foco` | Foco e bem-estar | hoje · semana |
| `A13 - Configuracoes` | Configurações | perfil · assistente · desempenho · conexoes · aprendizado · aparencia · feedback · plano · vinculos |
| `A14 - Apoiar` | Apoiar o projeto | contribuir · lista |
| `A15 - Servicos` | Serviços | pastas · trabalho |
| `A16 - Gravacoes` | Gravações | lista · live · gravacao |
| `P - Popups` | Diálogos e avisos do sistema | — |
| `M0`–`M14` | Versão celular de tudo acima | ver `04-telas-mobile.md` |
| `Plataforma` | Página pública de download e apoio | — |

Cada mockup aceita `tema="claro" | "escuro"`. O tema escuro não é um tema à
parte: é a mesma árvore com outro conjunto de variáveis (ver `00`).

## Três regras que valem para o sistema inteiro

1. **Nada com efeito externo sai sem aprovação.** Enviar e-mail, pagar, assinar,
   compartilhar, dar acesso: tudo vira pedido em Aprovações. A interface nunca
   oferece "Enviar"; oferece "Enviar para aprovação".
2. **Toda ação executada é reversível ou registrada.** Toda confirmação gera
   aviso com Desfazer; o que não dá para desfazer diz o que vai acontecer antes.
3. **O modelo roda nesta máquina.** O rodapé do Assistente e das telas que usam
   IA afirma isso. Atualização é a única saída para a internet.

## Quem pode ficar de fora da primeira leva

Quem não estiver implantando tudo de uma vez: `06-ordem-de-implantacao.md` traz
a ordem sugerida e o que cada fase entrega inteiro.
