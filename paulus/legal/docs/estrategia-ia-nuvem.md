# IA local e assinatura OpenAI/Anthropic: como conciliar

Estudo de 27/09/2026. É material para decidir, não uma decisão. As fontes estão no fim, e as incertezas aparecem no texto.

## 1. Dá para usar a assinatura de consumidor (ChatGPT Plus/Pro, Claude Pro/Max)? Não, de forma legítima

**Anthropic.** É proibido.
- A página de conformidade do Claude Code diz que a Anthropic não permite que desenvolvedores terceiros ofereçam login do Claude.ai nos próprios apps, nem que usem as credenciais Free, Pro ou Max em nome dos usuários. Também não permite coletar, guardar ou intermediar essas credenciais.
- Os Termos do Consumidor só permitem acesso automatizado por chave de API.
- A exceção é estreita: o usuário pode rodar o **binário oficial do Claude Code** com a própria assinatura. Montar um app jurídico sobre isso é zona cinzenta, e não deve servir de base para o produto.

**OpenAI.** Não existe caminho oficial para apps de terceiros.
- O "Sign in with ChatGPT" gasta o plano só dentro do Codex. Com chave de API, cobra o preço normal da API.
- Os termos proíbem compartilhar credenciais.
- A OpenAI tolera algumas ferramentas de programação de terceiros, mas por declarações públicas, não por contrato.

**O argumento que encerra a questão:** o plano de consumidor é o pior contrato para o sigilo.
- Não tem DPA, o contrato que define como o fornecedor trata os dados.
- No Claude, quem autoriza treino com as conversas tem retenção de 5 anos.
- A API, ao contrário, não treina com os dados por padrão, apaga em cerca de 30 dias e oferece retenção zero mediante aprovação.

**Conclusão:** o caminho legítimo é a **chave de API do próprio escritório**, paga por uso, direto no provedor ou via Azure, Bedrock ou Vertex.

## 2. Opções de arquitetura

| Opção | Prós | Contras e risco |
|---|---|---|
| **Chave de API do escritório** | Legítimo. O escritório paga o provedor direto, e o PAULUS continua sem servidor. | O escritório precisa criar conta no provedor. Há transferência internacional de dados. |
| **Híbrido por tarefa** | Julgamentos, regras, citação conferida e tudo do Gmail continuam locais. A nuvem só entra na resposta longa e na redação. | Mais caminhos para testar. O juiz de uma letra depende das probabilidades por palavra, que nem todo provedor devolve, então ele fica local. |
| **Cada envio passa pela fila de Aprovações** | Mostra o texto exato, o provedor e o custo estimado, e deixa registro. | Atrito. Dá para liberar por caso ou por sessão. |
| **Mascarar dados antes de enviar** (CPF, CNPJ, processo, e-mail, telefone) | Reduz a exposição. | Dado mascarado continua sendo dado pessoal na LGPD. Vender como "reduz", **nunca** como "anonimiza". |
| **Retenção zero ou processamento no Brasil** | O melhor argumento jurídico. | Depende de aprovação do provedor. No Bedrock, o Claude chamado do Brasil roda em inferência global. |
| **Modelo local maior com GPU** | Mantém a promessa intacta e não custa nada ao PAULUS. | Depende do hardware do cliente. |

## 3. Posicionamento

- **Nome sugerido:** "IA local por padrão. Nuvem só com a sua chave e o seu sim." O recurso poderia se chamar "Reforço na nuvem (opcional)".
- **Site e política:** hoje dizem que nada vai a serviço de IA na internet. Só mude o texto quando o código garantir o novo comportamento. A seção nova da política precisa dizer:
  - que o recurso vem desligado;
  - quais provedores podem ser usados;
  - o que pode ir e o que nunca vai;
  - que o contrato é do escritório com o provedor;
  - que há transferência internacional e qual retenção se aplica;
  - que a chave fica guardada cifrada;
  - que cada envio fica registrado.
- **Google:** deixe o Gmail **fora** do modo nuvem. Assim a política de dados do Google e a verificação não mudam.
- **Alerta à parte:** a política de dados para desenvolvedores do Workspace, atualizada em 03/09/2026, exige proteção contra injeção de prompt para escopos restritos. Isso vale para o PAULUS mesmo com IA local, porque ele usa `mail.google.com/`. Vale conferir.

## 4. OAB e LGPD

**OAB.** A Recomendação CFOAB nº 001/2024 é orientação, não norma disciplinar. Ela pede:
- cuidado para o cliente não ficar identificável;
- fornecedor que permita não usar os dados para treino;
- formalizar por escrito ao cliente o uso de IA.

Isso vale **também para a IA local**. É uma oportunidade: o PAULUS pode gerar esse termo para o cliente do escritório.

**LGPD.**
- O escritório é o controlador, e o provedor da API é o operador, com contrato de tratamento de dados.
- A transferência internacional, pelo art. 33 e pela Resolução CD/ANPD nº 19/2024, exige as cláusulas-padrão da ANPD desde 23/08/2025. **Não está confirmado** se os contratos de tratamento de dados da OpenAI e da Anthropic já trazem essas cláusulas.

## 5. Recomendação

1. **Não construir agora nada que use login de assinatura.** Levar a pergunta ao cliente do piloto de outubro: ele quer nuvem? Se não quiser, "100% local" vende melhor, e o próximo ganho é um modelo local maior com GPU.
2. **MVP, se for fazer:**
   - chave de API própria, só OpenAI e Anthropic direto, guardada cifrada;
   - só nas perguntas sobre documentos;
   - cada envio pela fila de Aprovações;
   - mascaramento opcional;
   - registro local de cada envio;
   - interruptor desligado de fábrica;
   - política e site atualizados no mesmo dia;
   - modelo do termo de uso de IA para o cliente.
3. **Não fazer:**
   - usar o token do Claude.ai ou o login do ChatGPT/Codex;
   - revender tokens ou intermediar chamadas;
   - mandar dados do Gmail para a nuvem;
   - deixar a nuvem ligada por padrão;
   - chamar de "anonimizado";
   - prometer processamento "no Brasil".

## Fontes

- [Claude Code, Legal and compliance](https://code.claude.com/docs/en/legal-and-compliance)
- [Anthropic Consumer Terms](https://www.anthropic.com/legal/consumer-terms) e [a atualização dos termos de consumidor](https://www.anthropic.com/news/updates-to-our-consumer-terms)
- [Anthropic, retenção de dados na API](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention) e [por quanto tempo a organização tem os dados guardados](https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data)
- [The Register, esclarecimento da Anthropic (fev/2026)](https://www.theregister.com/2026/02/20/anthropic_clarifies_ban_third_party_claude_access/)
- [Codex, autenticação](https://learn.chatgpt.com/docs/auth) e [OpenAI Terms of Use](https://openai.com/policies/row-terms-of-use/)
- [Retenção zero da OpenAI (ago/2026)](https://www.theregister.com/ai-and-ml/2026/08/20/openai-chases-anthropics-biz-customers-with-zero-data-retention-pledge/5290609)
- [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy) e [Workspace API User Data and Developer Policy](https://developers.google.com/workspace/workspace-api-user-data-developer-policy)
- [Bedrock, inferência entre regiões](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles-support.html)
- [Recomendação CFOAB 001/2024](https://s.oab.org.br/arquivos/2024/11/7160d4fe-9449-4aed-80bc-a2d7ac1f5d2f.pdf)
- [Resolução CD/ANPD nº 19/2024](https://www.gov.br/anpd/pt-br/acesso-a-informacao/institucional/atos-normativos/regulamentacoes_anpd/resolucao-cd-anpd-no-19-de-23-de-agosto-de-2024)
