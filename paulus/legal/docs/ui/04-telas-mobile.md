# 04 — Telas do celular

Referência: **390×844** (iPhone 14/15). O celular não abre a janela do
aplicativo: ele fala com a máquina do escritório pela rede local. O rodapé de
cada tela lembra isso.

## Regras de adaptação

1. **Painel direito vira cartão empilhado ou folha.** Quando é informação, vira
   cartão abaixo do conteúdo. Quando é ação, vira folha subindo de baixo.
2. **Seletor de visões continua seletor**, largura cheia, itens com `flex:1` e
   reticências. Três itens no máximo; acima disso, chips roláveis.
3. **Tabela vira lista.** Nenhuma tabela de desktop sobrevive no celular: cada
   linha vira linha de lista com título, subtítulo e valor à direita.
4. **Ação principal fixa**: rodapé grudado acima da barra inferior, ou botão
   flutuante a 96px da base.
5. **Alvo de toque ≥ 44px.** Sem exceção.
6. **Caixa de pedido sempre à mão** no Assistente, com microfone.

## Casca do celular

```
┌──────────────────────────────┐
│ barra de estado · 44px       │  relógio à esquerda; sinal, wifi, bateria
├──────────────────────────────┤
│ cabeçalho · min 56px         │  logo 30px ou voltar · título Garamond 22px
│                              │  subtítulo 12.5px --ink3 · ações à direita
├──────────────────────────────┤
│ conteúdo (rola)              │  grade, respiro 4px 16px 24px, intervalo 16px
├──────────────────────────────┤
│ fixo opcional                │  caixa de pedido, botão principal
├──────────────────────────────┤
│ barra inferior · 5 destinos  │  respiro 6px 6px 22px (área segura)
└──────────────────────────────┘
```

Moldura de 40px de raio só existe no mockup, para mostrar o aparelho. Na
implantação, a tela ocupa a viewport.

Barra inferior: **Assistente · Serviços · Agenda · Acervo · Mais**. Tudo que não
está nos cinco vive em "Mais", com contadores. "Mais" mostra ponto de pendência
em `--acc` quando há aprovação parada.

## Telas

| Tela | Visões | Conteúdo |
|---|---|---|
| **M0 Boas-vindas** | boas-vindas · escritório · seus dados · códigos · conexões | Mesmos cinco passos do A0a/A0b, um por tela, com rodapé Pular / Continuar |
| **M1 Assistente** | início · conversa · editor | Início: saudação, caixa de pedido, "Acontecendo agora" em cartões, recentes. Conversa: plano recolhido, blocos de resultado, citação abre folha com o trecho. Editor: documento em tela cheia com a alteração marcada e Manter / Descartar fixos embaixo |
| **M15 Serviços** | lista · serviço | Lista de cartões; dentro do serviço, resumo da IA, arquivos, equipe e trilha empilhados |
| **M16 Gravações** | lista · ao vivo | Ao vivo: gravador grande, transcrição rolando, "Contexto ao vivo" em folha arrastável |
| **M4 Agenda** | mês · semana · tarefas | Mês: grade de 7 colunas com pontos; tocar no dia abre a folha do dia. Semana: rolagem horizontal por dia. Tarefas: lista com caixa de seleção |
| **M5 Acervo** | lista · documento | Lista com glifo de arquivo e estado da análise; documento abre ficha em tela cheia com prazos extraídos |
| **M6 Documentos** | lista · editor · planilha | Editor em tela cheia, barra jurídica vira rolagem horizontal de ícones; planilha com rolagem nos dois eixos e barra fx fixa |
| **M7 E-mail** | caixa · mensagem · novo | Caixa com chips de filtro; mensagem com o cartão do assistente abaixo do corpo; novo e-mail com "Enviar para aprovação" fixo |
| **M8 Assinatura** | assinar · certificado | Assinar: página com o selo posicionável por toque; opções em folha. Certificado: ficha e prévia do selo |
| **M9 Financeiro** | geral · relatórios | Quatro números em grade 2×2; fluxo em barras; "Precisa de você" em cartões |
| **M10 Cadastros** | clientes · equipe | Listas com avatar e valor em aberto; ficha em tela cheia |
| **M11 Aprovações** | fila · pedido | Fila em cartões com Aprovar / Recusar no pé de cada um; pedido em tela cheia com o que vai sair e o efeito |
| **M12 Foco** | hoje · semana | Anel grande centralizado; lembretes em lista com interruptor |
| **M13 Mais** | mais · configurações · escritório e vínculos | "Mais" é o índice do que não cabe na barra: Documentos, E-mail, Assinatura, Financeiro, Cadastros, Aprovações, Gravações, Foco, Configurações, Apoiar, tema |
| **M14 Apoiar** | apoiar | Recorrência, valores, Pix com QR, lista de apoiadores |

A página pública (`Plataforma`) já é fluida e serve ao celular como está.

## Diferenças de medida contra o desktop

| Elemento | Desktop | Celular |
|---|---|---|
| Botão | 32px, raio 8 | 44px, raio 10 |
| Botão miúdo | 28px | 36px, raio 8 |
| Campo | 40px | 46px, raio 10 |
| Cartão | raio 12 | raio 14 |
| Linha de lista | 40px | 56px |
| Ícone de navegação | 22px | 24px |
| Respiro lateral | 20–24px | 16px |
| Painel | coluna de 320–400px | folha de raio 24px |
