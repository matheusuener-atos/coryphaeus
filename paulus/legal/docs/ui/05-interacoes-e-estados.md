# 05 — Interações e estados

## Diálogos

Padrão único, já desenhado em `P - Popups`:

- Título em Garamond + contexto em cinza, dizendo **onde estou**
  ("em Acervo › Clientes › Cooperativa").
- Campo com foco preto. Em renomear arquivo, a extensão fica **fora** do campo.
- Ação primária à direita; "Cancelar" como texto, à esquerda dela.
- Destrutiva em vinho, com o efeito escrito, não insinuado:
  "vai para a lixeira por 30 dias" · "3 citações deixam de apontar para este
  arquivo" · "2 serviços perdem o vínculo".
- **Enter** confirma, **Esc** fecha, foco inicial no campo, foco preso dentro
  do diálogo, devolvido ao elemento de origem ao fechar.

Diálogos existentes: renomear arquivo · renomear pasta · renomear escritório ·
renomear conversa · nova pasta · mover · excluir · remover pessoa ·
compartilhar · renomear na lista (**F2**).

## Avisos (toasts)

Toda ação concluída gera aviso. Se é reversível, o aviso traz **Desfazer** — e
desfazer significa desfazer de verdade, não abrir outra tela.

Casos que são aviso e não diálogo:
- conflito de nome: "já existe um arquivo com esse nome — renomeei para (2)";
- envio para aprovação: "pedido enviado · 1 na fila";
- movimentação em lote: "12 arquivos movidos", com Desfazer.

## Estados de tela

Toda lista e todo painel precisam dos quatro. O que não tiver, não está pronto.

**Vazio inicial** (nunca houve dado): título em Garamond 20px, uma linha de
explicação em `--ink2` e **uma** ação primária. Sem ilustração.
Ex.: Acervo sem documentos → "Nenhum documento ainda" · "Aponte uma pasta e eu
leio o que houver lá dentro." · [Escolher pasta].

**Vazio por filtro**: "Nada com esse filtro" + botão fantasma "Limpar filtros".
Nunca reaproveite o vazio inicial aqui.

**Carregando**: esqueleto com a forma do conteúdo (retângulos em `--fill`, sem
animação de brilho), nunca giro centralizado. Para trabalho do assistente, o
ponto pulsante + rótulo em Fira Code, e o anel girando no logo do trilho.

**Erro**: cartão com borda `--accln`, fundo `--accbg2`, título do que falhou em
linguagem comum, a causa provável e a ação de correção. Sem código de erro no
texto principal; ele vai em "Detalhes" recolhido, em Fira Code 11px.

Erros previstos que precisam de texto próprio:
- Ollama não está rodando → "O assistente está desligado" + [Ligar agora].
- Modelo não baixado → tamanho e tempo estimado + [Baixar].
- Máquina do escritório fora do ar (celular) → "Não encontrei a máquina do
  escritório na rede" + o que continua funcionando.
- Senha de e-mail recusada → estado "Reconectar" na conta, não diálogo.
- Certificado vencido → bloqueia assinar, oferece trocar.
- Disco cheio durante indexação → para, guarda o progresso, explica.

## Teclado

| Atalho | Ação |
|---|---|
| `Ctrl+K` | Foco na caixa de pedido, de qualquer tela |
| `Ctrl+N` | Nova conversa |
| `F2` | Renomear o item selecionado na lista |
| `Delete` | Enviar para a lixeira (com aviso e Desfazer) |
| `Esc` | Fecha diálogo, folha, menu sobreposto |
| `Enter` | Confirma o diálogo em foco |
| `Ctrl+S` | Salvar em Documentos e em Configurações |
| `Ctrl+F` | Buscar dentro da lista ou do documento |
| `Tab` | Percorre na ordem visual; nunca pula o painel direito |

Navegação por setas dentro de tabela e de calendário; `Space` marca a seleção.

## Acessibilidade

- Contraste conforme `00-fundamentos.md`. `--ink3` é o piso.
- Todo botão de ícone tem `aria-label` e `title`.
- Estado não é só cor: prazo em vinho também traz a palavra "prazo"; concluído
  em verde também traz "concluído".
- Foco visível em tudo que recebe teclado: `2px solid var(--acc)`, `offset 2px`.
- Alteração no documento (riscado/inserido) é marcada também por `<del>`/`<ins>`.
- `prefers-reduced-motion: reduce` desliga giro e crescimento de barra.
- Área de conversa é `aria-live="polite"`; o plano de execução anuncia mudança
  de etapa, não cada token.

## Regras de comportamento que valem em toda tela

1. **Nada com efeito externo sai sem aprovação.** Os botões dizem isso:
   "Enviar para aprovação", "Pedir aprovação para pagar".
2. **Toda ação executada é reversível ou registrada.** O que não é reversível
   avisa antes.
3. **Citação sempre clicável.** Toda afirmação da IA sobre um documento leva ao
   trecho, com página.
4. **Contexto explícito.** Diálogo e folha sempre dizem sobre o que agem.
5. **Modo limitado degrada, não quebra.** Destino bloqueado fica opaco e
   inerte, com explicação ao passar o mouse; não some do menu.
6. **Modo foco segura interrupção.** E-mail, WhatsApp e Aprovações esperam a
   pausa; o contador mostra quantos estão retidos.
