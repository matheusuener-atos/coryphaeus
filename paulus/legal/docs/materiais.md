# Materiais entre advogados — como publicar (para o dono)

A página `paulus.ia.br/materiais/` lê `site/dados/materiais.json`. Não há
servidor novo nem banco: um material entra quando você o põe na lista e
publica o site (vai junto com o próximo `publicar`, que faz o push).

## Quando chega um material

O advogado manda pelo PAULUS (Biblioteca › Da comunidade). O e-mail chega em
contato@paulus.ia.br com o título, o autor, a área, o resumo, a autorização
de publicar sob **CC BY 4.0** e o texto, depois de o PAULUS conferir os
dados pessoais (CPF, CNPJ, número de processo, e-mail, telefone e nomes dos
clientes do escritório dele). Nome de pessoa que não é cliente a regra não
acha: **leia o texto inteiro antes de publicar**.

## Publicar

1. Salve o texto em `site/materiais/<slug>.md` (o slug: minúsculas, números
   e hífen — por exemplo `multa-moratoria-locacao`).
2. Calcule o hash do arquivo:

   ```bash
   python -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" site/materiais/<slug>.md
   ```

3. Acrescente em `site/dados/materiais.json`, na lista `materiais`:

   ```json
   {"slug": "multa-moratoria-locacao", "titulo": "A multa moratória no contrato de locação",
    "autor": "Maria Souza", "oab": "SP 123.456", "areas": ["civil"], "tipo": "artigo",
    "resumo": "Quando a multa de 10% é abusiva.", "publicado_em": "2026-10-01",
    "licenca": "CC BY 4.0 (Creative Commons Atribuição)",
    "arquivo": "/materiais/multa-moratoria-locacao.md", "sha256": "<o hash do passo 2>"}
   ```

   e ponha a data em `atualizado_em`.
4. Publique o site (o próximo `publicar`).

O PAULUS de cada escritório confere o arquivo pelo `sha256` antes de trazer:
se você mudar o texto depois, calcule o hash de novo.

## Tirar

Apague o item da lista e o arquivo, e publique. Quem já trouxe para a
Biblioteca continua com a cópia (a licença permite); se o autor pedir,
diga isso a ele.
