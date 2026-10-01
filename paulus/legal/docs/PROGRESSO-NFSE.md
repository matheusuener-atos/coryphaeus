# PROGRESSO — O emissor de NFS-e

Retomada do plano do emissor de NFS-e pelo Padrão Nacional (N0…N9). Uma
conversa nova, com o mesmo prompt, continua da primeira etapa que não estiver
`feita`.

| Etapa | O quê | Estado | Commit | Portão (medido) |
| --- | --- | --- | --- | --- |
| N0 | Levantamento e fonte oficial (⏸ o que o dono precisa ter) | feita; pausa registrada abaixo, sem parar (pedido do dono) | ver git log (n0) | tabela abaixo; XSD oficiais baixados |
| N1 | Prestador, tabelas oficiais, município | pendente | — | — |
| N2 | Montar e conferir a DPS (XSD, tributos em centavos, numeração) | pendente | — | — |
| N3 | Assinar, enviar, não emitir duas vezes (⏸ 3 notas em produção restrita) | pendente | — | — |
| N4 | O fluxo no PAULUS | pendente | — | — |
| N5 | Consultar, cancelar, substituir, DANFSe | pendente | — | — |
| N6 | Contador e conferência fiscal | pendente | — | — |
| N7 | Recorrência e avisos | pendente | — | — |
| N8 | Produção (⏸ teste real) | pendente | — | — |
| N9 | Manual, política, textos | pendente | — | — |

## Como este trabalho está sendo feito (01/10/2026)

- O dono pediu, às 05h20 de 01/10: "eu vou dormir, pode ir implantando até
  concluir… como fizemos com os outros". Como na Biblioteca e na Conversa,
  **as pausas do prompt não param o trabalho**: o que seria mostrado nelas
  fica registrado aqui, para o dono ver quando acordar.
- **Duas pausas não dá para cumprir sem o dono**, e ficam para ele:
  - a da N3 (emitir 3 notas em produção restrita) precisa do certificado A1
    do escritório e da decisão dele de mandar algo ao Sistema Nacional — nada
    foi enviado a servidor nenhum do governo;
  - a da N8 (teste real) é dele por definição.
- **Nada vai à produção** em nenhum momento deste trabalho; o cliente HTTP
  recusa produção até a liberação da N8.
- **Onde:** worktree separada (`C:\coryphaeus-nfse`, branch `nfse`). A `main`
  tinha alterações do Word não commitadas de outra sessão; para não misturar
  nem atropelar, cada etapa vai para a sua branch e o merge é na `nfse`. O
  merge da `nfse` na `main` fica para quando o trabalho do Word for
  commitado (é um `git merge nfse`, sem conflito esperado fora de `api.py` e
  `politicas.py`).
- Não publiquei e não fiz `git push`.

## N0 — Levantamento e fonte oficial

### Fontes lidas (todas baixadas em 01/10/2026)

| Fonte | Versão / data | Link |
| --- | --- | --- |
| Documentação atual (produção) | página atualizada em 15/08/2026 | https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual |
| Documentação de homologação (produção restrita) | página atualizada em 28/07/2026 | https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/producao-restrita |
| RTC (notas técnicas da reforma) | página atualizada em 15/07/2026 | https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/rtc |
| Atualizações e implantações | página atualizada em 11/08/2026 | https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/atualizacoes-e-implantacoes |
| Endereços das APIs | página atualizada em 20/08/2026 | https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/apis-prod-restrita-e-producao |
| Manual dos Contribuintes — APIs do Emissor Público | v1.0 de 17/03/2025 (arquivo "v1-2-out2025") | `.../documentacao-atual/manual-contribuintes-emissor-publico-api-sistema-nacional-nfs-e-v1-2-out2025.pdf` |
| Manual dos Contribuintes — APIs do ADN | v1.0 de 12/02/2026 | `.../documentacao-atual/manual-contribuintes-apis-adn-sistema-nacional-nfse.pdf` |
| Esquemas XSD (produção) | NFSe-ESQUEMAS_XSD-v1.01-20260209 | `.../documentacao-atual/nfse-esquemas_xsd-v1-01-20260209.zip` |
| Esquemas XSD (produção restrita) | NFSe-ESQUEMAS_XSD-PRODREST-v1.01-20260727 | `.../producao-restrita/esquemas-nfse-rtc-v1-01-20260727.zip` |
| Anexo I — leiaute e regras da DPS/NFS-e | v1.01-20260209 (produção e produção restrita) | `.../anexo_i-sefin_adn-dps_nfse-snnfse-v1-01-20260209.xlsx` |
| Anexo II — eventos | v1.01-20260122 | `.../anexo_ii-sefin_adn-pedregevt_evt-snnfse-v1-01-20260122.xlsx` |
| Anexo A — municípios IBGE e países | v1.00-20251210 | `.../anexo_a-municipio_ibge-paises_iso2-v1-00-snnfse-20251210.xlsx` |
| Anexo B — lista de serviços nacional e NBS | v1.01-20260122 | `.../anexo_b-nbs2-lista_servico_nacional-snnfse-v1-01-20260122.xlsx` |
| Anexo C — código indicador da operação (cIndOp) | v1.01 | `.../anexo-c-indop-ibscbs-snnfse-v1-01.xlsx` |
| Anexo V — parametrização municipal | v1.00-20251216 | `.../anexo_v-painel_adm_municipal-snnfse-v1-00-20251216.xlsx` |
| Anexo VIII — correlação item × NBS × cIndOp × cClassTrib | v1.01.00 ("trabalho inicial, sem regra de negócio") | `.../rtc/anexoviii-correlacaoitemnbsindopcclasstrib_ibscbs_v1-01-00.xlsx` |
| NT 004 v2.0 (grupos IBS/CBS) | 10/12/2025 | `.../producao-restrita/nt-004-se-cgnfse-novo-layout-rtc-v2-00-20251210.pdf` |
| NT 007 v1.0 (PIS/COFINS/CSLL retidos, numeração) | 07/02/2026 | `.../rtc/nt-007-se-cgnfse-v1-0.pdf` |
| NT 008 v1.02 (DANFSe) | 14/07/2026 | `.../rtc/nt-008-se-cgnfse-danfse-20260714-v1-02.pdf` |
| NT 009 v1.0.1 | (não implantada em agosto/2026) | `.../rtc/nt-009-se-cgnfse-v1-0-1.pdf` |
| Resolução CGSN nº 191, de 04/08/2026 (Simples Nacional) | notícias de 11 e 14/08/2026 | [Portal NFS-e](https://www.gov.br/nfse/pt-br/noticias/comite-gestor-do-simples-nacional-prorroga-a-obrigatoriedade-de-emissao-de-notas-fiscais-de-servico-pelo-emissor-nacional-da-nfs-e), [Receita Federal](https://www.gov.br/receitafederal/pt-br/assuntos/noticias/2026/agosto/simples-nacional-nfs-e-nacional-sera-obrigatoria-para-me-e-epp-a-partir-de-1o-de-novembro-de-2026) |
| LC 214/2025, arts. 343, 346 e 348 (alíquotas de teste de 2026) | publicação original | https://www2.camara.leg.br/legin/fed/leicom/2025/leicomplementar-214-16-janeiro-2025-796905-publicacaooriginal-174141-pl.html (o Planalto não respondeu) |
| CTN, arts. 173, 174 e 195 (guarda) | compilado já no acervo do PAULUS | `data/leis/l5172compilado.htm` |

Os prefixos `.../` são `https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica`.

**O que NÃO é público:** o Swagger das APIs (Sefin, ADN, parâmetros
municipais) só abre com certificado digital no TLS — sem certificado, a Sefin
responde 403 e o ADN derruba a conexão. Por isso os **nomes dos campos JSON**
do envio e das respostas não estão em documento público (ver a linha
"Formato do envio" na tabela). O PAULUS confere esses nomes sozinho, no Swagger
oficial, na primeira conexão com o certificado do escritório (N3).

### Endereços

| Serviço | Produção restrita | Produção |
| --- | --- | --- |
| Sefin Nacional (emitir, consultar NFS-e, DPS, eventos) | `https://sefin.producaorestrita.nfse.gov.br/API/SefinNacional` | `https://sefin.nfse.gov.br/SefinNacional` |
| Parâmetros municipais | `https://adn.producaorestrita.nfse.gov.br/parametrizacao` | `https://adn.nfse.gov.br/parametrizacao` |
| ADN — contribuintes (DF-e por NSU, eventos) | `https://adn.producaorestrita.nfse.gov.br/contribuintes` | `https://adn.nfse.gov.br/contribuintes` |
| DANFSe (API) | suspensa desde 03/08/2026 (NT 008) | suspensa desde 03/08/2026 (NT 008) |

Os caminhos vêm da página "APIs - Prod. Restrita e Produção" (links `.../docs/index`
de cada serviço, sem o `/docs/index`). Métodos (Manual dos Contribuintes):

- `POST /nfse` — recebe a DPS e devolve a NFS-e (síncrono) ou a rejeição;
- `GET /nfse/{chaveAcesso}` — a NFS-e pela chave;
- `GET /dps/{id}` — a chave da NFS-e gerada pela DPS (só para prestador, tomador ou intermediário);
- `HEAD /dps/{id}` — só diz se a DPS gerou NFS-e (qualquer certificado válido);
- `POST /nfse/{chaveAcesso}/eventos` e `GET /nfse/{chaveAcesso}/eventos[/{tipo}[/{nSeq}]]`;
- `GET /parametros_municipais/{codigoMunicipio}/convenio`, `/{codigoMunicipio}/{codigoServico}` e `/{codigoMunicipio}/{CPF/CNPJ}`.

### Tabela: o que o prompt supõe × o que a documentação diz

Onde divergem, vale a documentação.

| # | O prompt supõe | A documentação diz | Fonte | Efeito no trabalho |
| --- | --- | --- | --- | --- |
| 1 | Os campos de IBS/CBS passam a ser exigidos para a maioria dos serviços a partir de 1º/10/2026 | **A partir de 03/08/2026** há "previsão de obrigatoriedade" dos grupos IBS/CBS; o leiaute exigido é o da **NT 004 + `tpRetPisCofins` da NT 007** (o que está hoje nas APIs) | página RTC, observação 3 | A DPS sai sempre com o grupo `IBSCBS` (competência a partir de 01/01/2026, regra E0850) |
| 2 | O Simples Nacional migra para o Emissor Nacional "nos meses seguintes" | **ME/EPP do Simples: obrigatório a partir de 01/11/2026** (Resolução CGSN 191/2026, que revogou a 189 e o 01/09). **IBS/CBS para o Simples: só a partir de 01/01/2027.** O MEI já emite pelo nacional | notícias do Portal NFS-e (11/08) e da Receita (14/08) | Escritório no Simples: o grupo IBS/CBS fica **opcional até 31/12/2026**; o PAULUS pergunta ao contador se manda (pergunta 6) |
| 3 | O emissor calcula IBS, CBS e a conta dos tributos | **A DPS só declara** (`finNFSe`, `cIndOp`, `indDest`, `CST`, `cClassTrib`); **quem calcula** IBS/CBS, a base do ISS, a alíquota aplicada e o ISS é a **Sefin**, com a "Calculadora RTC", e devolve na NFS-e | NT 004 §1 ("Sefin Nacional, responsável pela validação, cálculo dos tributos e autorização"); RN E1530, E1539… | O cartão mostra uma **previsão** por regra; depois de emitida, mostra o que a Sefin calculou e **avisa se diferir** da previsão |
| 4 | Alíquota de ISS do município entra na DPS | `pAliq` é **proibido** para não optante com convênio ativo (E0617) e para quem tem regime especial (E0604); é **obrigatório** em casos do Simples com retenção (E0621/E0628) e quando o convênio não está ativo (E0619/E0640). Máximo 5% (E0595) | Anexo I, RN DPS, linhas 501–513 | A regra de "pôr ou não pôr `pAliq`" é aplicada por código, com teste por caso |
| 5 | Sociedade de advogados com ISS fixo usa "regime especial" pela tabela oficial | `regEspTrib` = **6 – Sociedade de Profissionais** (também 5 – Profissional Autônomo). Com regime especial **não pode haver retenção de ISS** (E0588) nem `pAliq` (E0604); o valor fixo não vai na DPS | XSD `TCRegTrib`; RN 492 e 504 | Com regime 5/6, o ISS da nota fica fora da conta da nota; o cartão diz "ISS pago por valor fixo, fora da nota" |
| 6 | Código de tributação nacional e NBS da advocacia vêm das tabelas oficiais | **`cTribNac` = 171401** ("Advocacia", item 17.14 da LC 116). NBS: **1.1301.10.00** (criminal), **1.1301.20.00** (outras áreas, exceto consultoria tributária), **1.1301.90.00** (não classificados) e **1.1303.10.00** (consultoria tributária para PJ). No XML a NBS vai sem pontos (`TSCodNBS` = 9 dígitos) | Anexo B v1.01; XSD | Tabelas carregadas da planilha oficial; o escritório escolhe a NBS (depende da área) |
| 7 | IBS/CBS: "alíquotas de teste de 2026" | **CBS 0,9% e IBS estadual 0,1%** em 2026 (LC 214, arts. 343 e 346), com **dispensa de recolhimento** para quem cumpre as obrigações acessórias (art. 348, §1º). Em 2026, a base do IBS/CBS = vServ − desc. incond. − reembolsos − vISSQN − vPIS − vCOFINS; `vTotNF = vLiq` | LC 214; RN E1530, E1555 | Previsão no cartão com essas alíquotas e a frase "em 2026 não há recolhimento, para quem emite certo" |
| 8 | `cClassTrib` e `cIndOp` vêm da documentação | A **correlação** (Anexo VIII) sugere para 17.14: `cIndOp` **100301** e `cClassTrib` **200052** ("profissões intelectuais", com redução), mas o anexo é "trabalho inicial, sem regra de negócio". `cClassTrib` é decisão tributária | Anexo VIII v1.01.00; página RTC | O PAULUS **mostra a sugestão** e **pergunta ao contador**; sem resposta, não emite com IBS/CBS (pergunta 5) |
| 9 | Retenções federais: "como informar PIS/COFINS/CSLL retidos" | **PIS + COFINS + CSLL retidos vão SOMADOS em `vRetCSLL`**, com `tpRetPisCofins` (0, 3 a 9). `vPis`/`vCofins` são **débito de apuração própria, não retenção**. IRRF em `vRetIRRF`; CP em `vRetCP`. Arredondamento **bancário (half-even)**, tolerância R$ 0,01 | NT 007 §2.c | A conta junta as três em `vRetCSLL`, guarda cada uma separada para o cartão e o contador, e arredonda half-even |
| 10 | Restrições para prestador pessoa física | A regra que proibia tributos federais para emitente CPF (**E0675**) foi **desligada em 13/03/2026**; continua proibido para **MEI** (E0676) | página Atualizações; Anexo I linha 515 | Advogado autônomo (CPF) pode informar retenções federais |
| 11 | O que garante que a mesma DPS não gera duas notas | A **identidade da DPS** é `"DPS" + cMun(7) + tipo de inscrição(1) + CNPJ/CPF(14) + série(5) + número(15)`; repetir série+número+município+CNPJ é **rejeitado (E0014)**. A **série 00001–49999** é de "aplicativo próprio" (E0010) | XSD `TSIdDPS`; RN 139, 144, 145 | Série própria do PAULUS na faixa 1–49999; numeração local atômica; **consulta antes de reenviar** (`GET`/`HEAD /dps/{id}`) |
| 12 | Numeração "sem buraco" | O número **da DPS** é do emitente (sem buraco, controlado aqui). O número **da NFS-e** é da Sefin e **pode ter pulos** que não são irregularidade | NT 007 §3.b | O teste de "sem buraco" vale para a DPS; os pulos da NFS-e são explicados na tela e no relatório |
| 13 | Assinatura XMLDSig com "os algoritmos que a documentação define" | XSD 1.00 fixava **C14N 1.0 (20010315)**, transformações **enveloped + C14N**, **RSA-SHA1** e digest **SHA-1**. O XSD 1.01 (vigente) aceita qualquer algoritmo. **Prefixo de namespace é proibido** (E1228); UTF-8 obrigatório (E1229) | xmldsig-core-schema.xsd (1.00 e 1.01); RN de recepção | Perfil padrão = o fixado no 1.00 (o único escrito); SHA-256 fica como opção. Assinatura sem prefixo `ds:` |
| 14 | Formato do envio: "DPS em XML assinado, compactação e codificação no JSON" | XML **compactado em GZip e codificado em Base64** dentro de JSON (erro E1225 "Falha ao descompactar XML Zip B64"). **Os nomes dos campos JSON só estão no Swagger, que exige certificado** | página Atualizações (24/04/2026); RN de recepção | Campos usados (`dpsXmlGZipB64`, `nfseXmlGZipB64`, `chaveAcesso`, `pedidoRegistroEventoXmlGZipB64`, `eventoXmlGZipB64`, `erros`) ficam numa tabela única no código e são **conferidos no Swagger oficial na primeira conexão** (N3); divergência trava o envio |
| 15 | Autenticação | Certificado ICP-Brasil **no TLS** (mTLS): v3, não pode ser de AC, uso "Autenticação Cliente", com CNPJ/CPF no OID 2.16.76.1.3.3, cadeia ICP-Brasil e LCR acessível (E1200–E1209) | Anexo I, RN_RECEPCAO_DPS | Só o A1 em arquivo (.pfx/.p12); o do Windows não exportável não serve para o TLS do Python, e a tela diz isso |
| 16 | Cancelamento "dentro do prazo do município" | Evento **e101101**, motivos **1 – Erro na emissão, 2 – Serviço não prestado, 9 – Outros**, `xMotivo` 15–255 caracteres. Prazo e valor máximo **são parametrização do município** (E0822, E0823). Fora do prazo: "Solicitação de Análise Fiscal" (e101103) | Anexo II; XSD `TSCodJustCanc` | Prazo vem dos parâmetros consultados (N1); fora dele, a tela explica e oferece substituição |
| 17 | Substituição | É uma **DPS nova** com o grupo `subst` (chave da substituída + motivo **01–05 ou 99**); a Sefin gera a nova e **cancela a antiga por substituição** (e105102) sozinha. Simples Nacional: tomador, competência e valor **não podem mudar** (E0061) | Manual dos Contribuintes 1.3.2; XSD `TCSubstituicao`; RN 174 | Substituir = emitir de novo com `subst`; o PAULUS liga as duas |
| 18 | DANFSe: "baixar o oficial; senão, gerar do XML marcado como representação" | A **API do DANFSe foi suspensa em 03/08/2026**; o DANFSe **deve ser gerado pelo próprio software** no leiaute da NT 008, com QR Code, e com "NFS-e SEM VALIDADE JURÍDICA" em produção restrita | NT 008 v1.02 §1 e §2 | O PAULUS gera o DANFSe pela NT 008 (é o caminho oficial agora) |
| 19 | Município sem convênio | Para emitir pelo nacional, o município emissor tem de ser **conveniado, ativo e permitir os emissores públicos** (doc. de `cLocEmi`; E0037). O MEI é exceção | XSD `cLocEmi`; RN 160 | A verificação do município consulta `/parametros_municipais/{cMun}/convenio` |
| 20 | Guarda legal | CTN, art. 195, parágrafo único: conservar até a **prescrição** dos créditos (arts. 173 e 174: 5 anos para constituir + 5 para cobrar). Legislação municipal pode pedir mais | CTN | O PAULUS **nunca apaga** nota emitida nem XML; o prazo exato é pergunta ao contador |
| 21 | Tomador: endereço | Com `cIndOp` 100301 (o sugerido para advocacia) **o endereço do tomador é obrigatório** (RN 255); com ISS retido pelo tomador também (E0237) | Anexo I | Cartão bloqueia sem endereço do tomador nesses casos |
| 22 | Prestador na DPS | Quando o emitente é o prestador, **não se informa o nome** (E0121) nem o endereço; a **inscrição municipal é obrigatória** se ele estiver no CNC do município (RN 198) | Anexo I | A DPS leva só CNPJ/CPF, IM e regime |
| 23 | Total aproximado de tributos (Lei 12.741) | Não optante: `vTotTrib` ou `pTotTrib` (nunca `indTotTrib`/`pTotTribSN`, E0713); ME/EPP: `pTotTribSN` ou valores (nunca `indTotTrib`, E0712); MEI: nunca `pTotTribSN` | Anexo I, RN 538–541 | O percentual vem da configuração (o contador informa) |
| 24 | CNPJ | CNPJ **alfanumérico** já aceito (produção desde 10/08/2026; XSD de produção restrita de 27/07/2026) | página Atualizações; XSD | Validação aceita os dois formatos |

### Datas que afetam o escritório

- **03/08/2026** — grupos IBS/CBS com previsão de obrigatoriedade (empresas fora do Simples).
- **03/08/2026** — API do DANFSe suspensa; DANFSe passa a ser gerado pelo software.
- **10/08/2026** — CNPJ alfanumérico em produção.
- **01/11/2026** — ME/EPP do Simples Nacional passam a emitir obrigatoriamente pelo Emissor Nacional (web ou API).
- **01/01/2027** — IBS/CBS passam a valer para o Simples; o IBS municipal começa (0,05% + 0,05% em 2027–2028, LC 214 art. 344).
- **Ano de 2026** — CBS 0,9% e IBS 0,1% com dispensa de recolhimento para quem cumpre as obrigações acessórias.

### O que o dono precisa ter em mãos para a produção restrita

1. **Certificado A1 em arquivo (.pfx ou .p12)** do prestador: e-CNPJ da sociedade (ou e-CPF, se for advogado autônomo), ICP-Brasil, válido, com a senha. O A3 (token) não serve; o certificado "do Windows, não exportável" também não serve para a API.
2. **CNPJ (ou CPF)**, **inscrição municipal** e **município** (código IBGE sai da tabela oficial pelo nome).
3. **Regime tributário**: não optante (presumido/real), Simples ME/EPP (com o regime de apuração) ou MEI; e se há **regime especial de ISS** (sociedade de profissionais / profissional autônomo).
4. **Se o município tem convênio** com o Sistema Nacional e permite os emissores públicos — o PAULUS consulta isso sozinho com o certificado (N1), mas vale o dono saber antes.
5. **Credenciamento prévio:** a documentação pública não exige cadastro prévio para usar a API além do convênio do município e, se houver, do registro no Cadastro Nacional de Contribuintes (CNC) do município — o "primeiro acesso" do portal é para usuário e senha do Emissor Web. A produção restrita aceita "todas as empresas que desejam testá-lo" (NT 004 §1.2). Confirmar no primeiro envio (N3).
6. Um ou dois **tomadores de teste** com CPF/CNPJ e endereço completo (CEP do município certo: a Sefin confere, E0240).

### Perguntas que só o contador responde

1. Qual o **regime** do escritório na competência (não optante, Simples ME/EPP e qual regime de apuração `regApTribSN`, MEI) e se há **regime especial de ISS** (sociedade de profissionais com ISS fixo)?
2. **Retenções**: quando reter **IRRF** (alíquota e de quais tomadores), **PIS/COFINS/CSLL** (alíquotas, de quais tomadores, valor mínimo) e **ISS retido** (quais tomadores, quais municípios)? O PAULUS aplica a regra que ele escrever; sem resposta, a retenção fica desligada.
3. **NBS** de cada tipo de serviço do escritório (criminal, outras áreas, consultoria tributária).
4. **Total aproximado de tributos** (Lei 12.741): percentual ou valores a informar.
5. **`cClassTrib`** do IBS/CBS (a correlação oficial sugere 200052, "profissões intelectuais", com redução de alíquota — é enquadramento tributário) e o **`CST`** correspondente; e o `cIndOp` (sugestão 100301).
6. Escritório no Simples: **mandar o grupo IBS/CBS já em 2026** ou só a partir de 2027?
7. **Prazo de guarda** dos XMLs pela lei do município, se maior que o do CTN.
8. Município do tomador diferente: alguma **regra de incidência** especial para os clientes do escritório?

### O que existe no código (confirmado)

- `src/ferramentas.py:105` — `emitir_nfse` no catálogo (cliente, valor, descrição, data), exige confirmação, `disponivel: False`; `src/ferramentas.py:577` `_emitir_nfse` só confere e devolve `pendente`.
- `src/intencao.py` — reconhece "emita uma NFS-e para … de R$ …" e vira a proposta "nota".
- `src/certificado.py` — lê A1 (.pfx/.p12) e o instalado no Windows (`Cofre`, senha em memória com prazo e protegida por `segredos.py`); A3 não.
- `src/base.py` (migração 011) — `papeis_fiscais` (tipo, número, cadastro, lançamento, centavos, data, situação); `src/escritorio.py:187` `PapeisFiscais` ("nota fiscal e boleto são registro, não emissão") e `a_emitir()` (recebimentos sem nota).
- `src/aprovacoes.py` — `Fila.pedir(titulo, categoria, acao=, dados=)`; quem executa é quem sabe a ação.
- `src/segredos.py` — DPAPI do Windows (`proteger`/`revelar`).
- Dependências: `lxml` 6.1.3 e `cryptography` 50 **já estão no venv** (o `lxml` veio como dependência de outro pacote; passa a ser declarado no `requirements.txt` na N2).

## Fora do foco

- (nada ainda)
