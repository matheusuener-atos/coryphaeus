# PAVLVS — Extrato de contribuições

> **Implementado em 28/09/2026** em `src/extrato_apoio.py` (reportlab), pela rota `POST /api/apoio/extrato` e pelo botão **Baixar extrato de contribuições** em Apoiar o projeto. O `.dc.html` do pacote fica fora do git, porque traz nome e e-mail reais. Diferenças do mockup:
> - **Fontes:** o PDF não carrega Google Fonts. `tools/fontes_pdf.py` converte as fontes do app (`frontend/fontes`) em TrueType estático, com o recorte latino e o estendido juntos, para `src/fontes_pdf`. O IBM Plex Mono vira "PAULUS Mono", porque "Plex" é nome reservado na licença (OFL em `src/fontes_pdf`). Se as fontes faltarem, o extrato sai com Helvetica, Times e Courier em vez de falhar.
> - **Tipo:** Pix é **Avulsa**; cada cobrança do apoio mensal no cartão é **Recorrente**. O programa não tem Pix recorrente nem cartão avulso.
> - **Situação:** "Confirmada" leva o selo verde do desenho. As outras (Pendente, Em análise, Agendada, Nova tentativa, Recusada, Cancelada, Devolvida, Estornada) aparecem com selo cinza e ficam fora do total, do período e da contagem.
> - **Emitido em**, no quadro, traz também a hora; o rótulo do topo e o rodapé trazem só a data.
> - **Referência:** os 10 últimos caracteres do identificador do Mercado Pago.
> - **Quebra de página:** o cabeçalho da tabela se repete; linha, quadro, "Tratamento fiscal / Sobre este documento" e o agradecimento não se partem. Se as duas colunas não cabem no fim da página, vão inteiras para a próxima.

Abra `Extrato de apoio.dc.html` no navegador (com `support.js` e `doc-page.js` na mesma pasta). Para PDF: Ctrl+P → Salvar como PDF (A4, margens padrão; o documento já controla as margens).

## Formato
- Documento corrido em A4, modo claro. Quebra em quantas páginas forem necessárias.
- Margem 16 mm. Rodapé repetido em todas as páginas: "PAVLVS — Extrato de contribuições · emitido em DD/MM/AAAA" e "paulus.ia.br".
- O cabeçalho da tabela se repete em cada página; linhas e blocos não se partem no meio.

## Estrutura
1. Topo: marca **PAVLVS** (EB Garamond) + "PAVLVS · PAULUS LEGAL · SOFTWARE LIVRE".
2. Rótulo "EMITIDO EM", título **Extrato de contribuições** e parágrafo de abertura.
3. Quadro de dados (3 × 2): Apoiador · E-mail do recibo · Emitido em / Total contribuído · Período · Contribuições.
4. Tabela **Contribuições**: Data · Tipo · Forma · Referência · Situação · Valor; rodapé "Total contribuído".
   - **Tipo** = Avulsa ou Recorrente, por linha. Não existe campo "apoio recorrente sim/não" no resumo, porque a recorrência pode ter começado e parado.
   - Nota abaixo da tabela explica os dois tipos.
5. **Sobre estas contribuições**, com **Tratamento fiscal** e **Sobre este documento** lado a lado.
6. Agradecimento em itálico + links (termos, privacidade, contato).

## Dados para preencher (gerados pelo app)
- Nome, e-mail do recibo, data/hora de emissão.
- Total, período (primeira e última contribuição), quantidade confirmada.
- Uma linha por contribuição: data, tipo, forma (Pix / Cartão de crédito), referência do Mercado Pago, situação, valor.

## Padrão visual
- Fontes: EB Garamond (marca, títulos), Manrope (texto), IBM Plex Mono (rótulos e referências).
- Cores: tinta `#1c1c1a`, texto secundário `#6b6b65`, rótulos `#8a8a83`, linhas `rgba(0,0,0,.08–.14)`, quadro `#fff`.
- Situação "Confirmada": selo `#edf5ee` / `#2f6b42`.
