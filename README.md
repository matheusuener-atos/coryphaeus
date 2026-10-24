# Coryphaeus · PAVLVS

Repositório da Atos que reúne o **PAVLVS**, assistente e ferramentas para
escritórios jurídicos, sua tecnologia de execução e os serviços do produto.
No código e nos caminhos, o nome também aparece como PAULUS/`paulus`.

O produto já inclui aplicativo Windows, acervo e busca de documentos,
conversa, editor, serviços por cliente, tarefas, agenda, financeiro e
integrações. A descrição antiga de “MVP — semana 1” não representa o estado
atual. Código implementado ainda precisa de validação no ambiente de uso.

## Como se encaixa na Atos

| Parte | Responsabilidade |
| --- | --- |
| Atos | Empresa e plataforma compartilhada de identidade e cobrança |
| Coryphaeus | Nome da base tecnológica e deste repositório |
| [PAVLVS](paulus/README.md) | Produto jurídico e aplicação de escritório |
| `paulus/legal/` | Aplicativo Python, interface, dados de exemplo e testes |
| `site/` e `worker/` | Site do produto, acesso, medição de uso e serviços em nuvem |

A base tecnológica e o produto estão no mesmo repositório. Essa organização
não comprova um motor genérico reutilizado por outras verticais.

## Começar

- [Instalação e execução pelo código-fonte](paulus/legal/docs/QUICKSTART.md).
- [Recursos e uso do aplicativo](paulus/legal/README.md).
- [Estado atual, limites e próxima entrega](paulus/legal/docs/ESTADO-ATUAL.md).
- [Contribuição e verificações essenciais](paulus/legal/CONTRIBUTING.md).

A versão distribuída está no [site do produto](https://paulus.ia.br/) e os
instaladores publicados ficam nas
[releases](https://github.com/matheusuener-atos/coryphaeus/releases).
A `main` pode conter mudanças posteriores ao último instalador.

## Processamento e dados

O aplicativo e seu acervo funcionam na máquina do escritório, com caminhos
de inferência local e em nuvem. **“Nenhum dado sai” não descreve todas as
configurações do produto.**

Com a nuvem do plano ativada e o consentimento registrado, ela tem
preferência nas funcionalidades habilitadas; o modelo local serve de
reserva quando aplicável. Existem também provedores com chave de API do
escritório. O código registra inclusive o consentimento pela assinatura do
plano e permite retirá-lo.

E-mail, Drive, acesso remoto, atualizações e consultas externas têm seus
próprios fluxos de dados. Veja as exclusões e os limites no
[estado atual](paulus/legal/docs/ESTADO-ATUAL.md#dados-e-nuvem).

As respostas oferecem fontes e mecanismos de conferência; isso não garante
correção de toda afirmação. O texto gerado precisa ser revisado no contexto
do documento e do trabalho do escritório.
