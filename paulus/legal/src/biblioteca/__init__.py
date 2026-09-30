"""
A Biblioteca do escritório: o material de consulta (livros, manuais, tabelas),
as leis em casa e os lembretes, organizados como uma biblioteca jurídica com
fonte (docs/PROGRESSO-BIBLIOTECA.md).

O princípio é o de src/material.py e não muda: o PAULUS não "treina" com os
livros. Lê uma vez, organiza e cita - obra, autor e página -, e o que ele diz
pode ser conferido no arquivo do próprio escritório.

Cada peça atrás da sua chave, no bloco `biblioteca` das preferências
(src/config.py):

- `indice.py` (M1, `hibrida`): o material no pipeline híbrido do Acervo -
  trechos pela estrutura (regime C para obras), FTS5 e vetores, em índices
  próprios, separados do Acervo.
"""
