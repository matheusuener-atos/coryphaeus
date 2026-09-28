# PAULUS — Instalador e Assistente de configuração

> **Implementado em 27/09/2026** (`tools/instalador/Instalador.cs` e `frontend/js/23-boas-vindas.js`). Os `.dc.html` do pacote ficam fora do git porque trazem telefone, endereço e e-mail de exemplo. Diferenças do mockup, decididas na implementação:
> - "Fixar na barra de tarefas" e "Fixar no menu Iniciar" viraram **Adicionar ao menu Iniciar**, porque o Windows não deixa um instalador fixar. "Fixar o Assistente PAULUS no Windows Explorer" virou **"Perguntar ao PAULUS" no botão direito**.
> - A tela Local ganha **Instalar o motor de IA local** quando o Ollama falta. O instalador dele tem ~1,5 GB e é baixado na hora, então não dá para "não depender de internet".
> - O instalador ganha a tela **"já instalado"** (Atualizar / Desinstalar) e as telas do desinstalador, no mesmo padrão.
> - Módulos: desligar tira do menu **desta máquina**. A rede local entre máquinas ainda não existe. Os ícones são os do menu do app.
> - Conexões: a conta Google conecta o Gmail. A Agenda e o Drive pedem autorização própria em Configurações › Conexões, e o cartão diz isso.
> - Os logos dos modelos vão com o programa (`frontend/img/marcas`, @lobehub/icons-static-svg 1.95.1, MIT). Modelo já baixado ganha o selo "já nesta máquina"; modelo que não cabe na memória fica desabilitado.

Pacote com as duas telas que substituem o instalador atual (Inno Setup) e o assistente pós-instalação (A0a + A0b).
Abra os `.dc.html` no navegador, com `support.js` na mesma pasta.

- `Instalador v2.dc.html` — janela 640 × 480
- `Assistente de configuracao.dc.html` — janela 1264 × 820
- `support.js` — runtime (não editar)

---

## Decisão principal: instalador mínimo, assistente completo

O instalador faz só o que precisa acontecer antes de o app existir no disco: copiar arquivos, instalar o motor de IA (Ollama) e criar atalhos. Tudo que é escolha do usuário foi movido para o assistente, que roda dentro do app na primeira abertura:

| Antes (instalador) | Agora |
|---|---|
| Escolha do modelo de IA | Assistente › Modelo de IA |
| Diagnóstico da máquina | Assistente › Modelo de IA (automático, ~5 s) |
| Módulos | Assistente › Módulos (só no caminho "Criar") |
| Download do modelo | Começa ao abrir o PAULUS, depois do assistente |
| Tarefas adicionais (tela separada) | Juntas na tela Local |
| "Pronto pra instalar" (resumo) | Removida; o botão da tela Local já diz "Instalar" |

Motivos: o instalador fica curto (4 telas), não depende de internet para concluir, e as escolhas acontecem num lugar com espaço para explicar cada uma e que pode ser revisitado em Configurações.

---

## Padrão visual

### Instalador — preto, branco e cinza
Sem cor de destaque. Nenhum verde, âmbar ou azul.

| Token | Escuro | Claro |
|---|---|---|
| fundo | `#141414` | `#ffffff` |
| lateral | `#1c1c1c` | `#f3f3f3` |
| tinta | `#f2f2f2` | `#161616` |
| tinta 2 | `#a3a3a3` | `#5c5c5c` |
| tinta 3 | `#737373` | `#8c8c8c` |
| linha | `rgba(255,255,255,.1)` | `rgba(0,0,0,.1)` |
| botão primário | `#f2f2f2` / texto `#141414` | `#161616` / texto `#fff` |

- Barra de título integrada ao app: sem faixa de título, só minimizar/fechar flutuando no canto.
- Lateral 188 px: nome **PAVLVS** (EB Garamond 26 px, espaçamento .14em) e o índice das etapas (ponto + nome; atual em peso 600).
- Conteúdo: rótulo mono → título Garamond 30 px → texto 13 px → rodapé com linha fina e botões.

### Assistente — padrão do app
Mesmos tokens do A1 (fundo `#faf9f6` / `#131312`, casca `#26251f` / `#34322c`, verde e âmbar só em selos). Layout editorial: texto à esquerda, cartão à direita; stepper no topo mostra o nome só da etapa atual (as outras mostram número ou ✓).

### Logo
A logo oficial é **sempre escura**: quadrado `#1c1c1a` com "P" em EB Garamond `#f2f1ec`, nos dois temas. No escuro, ganha um contorno de 1 px `rgba(255,255,255,.14)`.
Uso atual: só no cartão "Instalação concluída" do assistente. Cabeçalhos e lateral usam só o nome PAVLVS.

### Nome
Nos textos, usar **PAULUS** (sem "Legal"). Na marca, **PAVLVS**.

### Tipografia
EB Garamond (títulos e marca) · Manrope (interface) · IBM Plex Mono (rótulos, caminhos, tamanhos) · Material Symbols Outlined peso 300.

---

## Instalador v2 — 4 telas

1. **Boas-vindas** — "Instalar o PAULUS neste computador." Versão 0.9.0 · Windows 64 bits · 393,4 MB.
2. **Local** — pasta `C:\Users\…\AppData\Local\Programs\PAULUS` + Procurar. Opções:
   - Criar um atalho na área de trabalho ✓
   - Fixar atalho na barra de tarefas ✓
   - Fixar atalho no menu Iniciar ✓
   - Fixar o Assistente PAULUS no Windows Explorer ☐
   - Botão **Instalar**. Se a pasta já existe, abre o diálogo "A pasta já existe" (Sim / Não).
3. **Instalação** — barra fina + ação atual (Extraindo arquivos → Instalando o motor de IA local → Criando atalhos → Finalizando). Só "Cancelar".
4. **Concluído** — "O PAULUS está instalado." Opção "Abrir o PAULUS agora" ✓ → abre o assistente.

---

## Assistente de configuração — dois caminhos

**Criar escritório** (7): Boas-vindas → Escritório → Seus dados → Modelo de IA → Módulos → Conexões → Atualizações
**Entrar em escritório** (5): Boas-vindas → Escritório → Seus dados → Modelo de IA → Códigos

Cada máquina escolhe o seu modelo, por isso "Modelo de IA" está nos dois caminhos.

1. **Boas-vindas** — cartão "Instalação concluída": Ollama rodando em 127.0.0.1 · modelo (escolhido no passo 3) · pasta de documentos · certificado digital.
2. **Escritório** — Criar um escritório novo (você será o responsável) / Entrar em um existente (precisa de código). A escolha define o caminho.
3. **Seus dados**
   - Criar: Nome, OAB, CPF, Telefone, E-mail, Endereço.
   - Entrar: Nome, Como quer ser chamado(a), OAB, Cargo sugerido, E-mail, Escritório (bloqueado, vem do vínculo).
4. **Modelo de IA** — diagnóstico automático (processador, memória, placa de vídeo) e depois a lista no estilo Ollama, com logo do fabricante, nota no teste, tempo da 1ª pergunta e tamanho:
   - **Recomendado:** llama3.2:3b (Meta) · 2,0 GB · 41/41 · ~74 s
   - Participar da calibração (switch) — logo abaixo do recomendado
   - Outras opções: llama3.2:1b 1,3 GB · qwen2.5:3b 1,9 GB · gemma2:2b 1,6 GB · qwen2.5:7b 4,7 GB (mais lento aqui) · llama3.1:8b 4,9 GB (mais lento aqui) · Não baixar agora
5. **Módulos** (criar) — Assistente fixo; Serviços, Gravações, Agenda, Acervo, Documentos, Assinatura, E-mail, Financeiro, Cadastros, Aprovações, Foco e bem-estar com switch.
6. **Conexões** (criar) — só **Conta Google** com switch. Ligar abre a janela "Entrar" (Entrar com Google / Outro provedor IMAP e SMTP).
7. **Atualizações** (criar) — opções "em breve" + apoiar o projeto. Botão "Abrir o PAULUS".
8. **Códigos** (entrar) — código do responsável (6 caixas) + seu código gerado (5WUY3S) com Copiar / WhatsApp. Botão "Abrir o PAULUS e aguardar".

---

## Observações
- Logos dos modelos e do Google vêm de `unpkg.com/@lobehub/icons-static-svg` (exigem internet no protótipo; no app, empacotar localmente).
- Dados de máquina, notas e tempos são os do seu diagnóstico atual (i7-1360P, 16,9 GB, sem NVIDIA).
- Props para revisão: Instalador `passo`, `tema`; Assistente `caminho`, `passo`, `tema`.
- Versões anteriores (`Instalador.dc.html`, A0a, A0b) continuam no projeto e não entram neste pacote.
