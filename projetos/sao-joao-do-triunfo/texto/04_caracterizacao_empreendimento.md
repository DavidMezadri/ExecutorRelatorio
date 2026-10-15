# Caracterização do Empreendimento

## Tipo de Atividade do Empreendimento

O empreendimento consiste na [A VERIFICAR: implantação/ampliação] do sistema de esgotamento sanitário do município de {{municipio}}. A Sanepar é a empresa responsável pela captação, tratamento e distribuição de água potável, além da coleta e do tratamento de esgoto sanitário. CNAE {{cnae}}.

- Esgotamento sanitário: coleta o esgoto gerado e realiza o tratamento adequado antes de devolvê-lo ao meio ambiente;
- Abastecimento de água: capta água de rios, lagos ou poços, trata em estações especializadas e distribui para residências e empresas;
- Atuação geográfica: presta serviços em centenas de municípios no estado do Paraná e em Porto União, em Santa Catarina.

## Descritivo da Obra a ser Implantada e Descrição das Intervenções Necessárias

<!-- Contexto: índice de atendimento atual, problema, concepção do sistema. Intervenções: supressão de
     vegetação (ha, APP?), desapropriações/servidões (matrículas), escavações de valas, travessias,
     acessos à ETE. Usar dados/RESUMO_TEMATICO.md para extensão em APP e travessias. -->
Segundo o Censo Demográfico 2022, {{dossie.saneamento.esgoto_rede_pct|num:1}}% dos domicílios particulares permanentes de {{municipio}} estão ligados à rede geral ou pluvial de esgoto, enquanto {{dossie.saneamento.esgoto_fossa_rudimentar_pct|num:1}}% utilizam fossa rudimentar ou buraco (IBGE, 2023), o que evidencia a demanda pelo sistema de esgotamento sanitário. [A VERIFICAR: índice de atendimento atual da Sanepar e concepção do sistema projetado.]

A implantação do empreendimento demandará as seguintes intervenções:

- Supressão de vegetação: {{auto.supressao}};
- Desapropriação/servidão: {{imoveis_terceiros}};
- [A VERIFICAR: escavações de valas, travessias de cursos d'água, acessos e interligações].

## Descrição do Empreendimento e Apresentação de suas Características Técnicas

### População de Alcance do Plano e Alcance de Plano

O sistema atenderá, em início de plano ({{populacao.inicio_plano_ano}}), cerca de {{populacao.inicio_plano_hab|num:0}} habitantes e, em final de plano ({{populacao.final_plano_ano}}), cerca de {{populacao.final_plano_hab|num:0}} habitantes, com horizonte de projeto de {{horizonte_projeto_anos}} anos. [A VERIFICAR: taxa de crescimento, per capita, coeficiente de retorno, taxa de infiltração e coeficientes K1/K2.]

A vazão média de projeto da ETE é de {{ete.vazao_media_ls|num:2}} L/s e a vazão máxima é de {{ete.vazao_maxima_ls|num:2}} L/s.

### Corpo Receptor

O efluente tratado será lançado no {{corpo_receptor.nome}}, pertencente à {{corpo_receptor.bacia}} e enquadrado na {{corpo_receptor.classe}}. O ponto de lançamento localiza-se nas coordenadas UTM {{corpo_receptor.ponto_lancamento_utm_e}} E e {{corpo_receptor.ponto_lancamento_utm_n}} N (SIRGAS 2000).

### Portaria de Outorga para Lançamento de Efluentes

O lançamento do efluente tratado é objeto da Portaria de Outorga {{corpo_receptor.outorga_lancamento}}, para a vazão de {{corpo_receptor.vazao_outorgada_ls|num:2}} L/s.

### Descrição das Unidades que Compõem o Sistema

<!-- IN 37 Anexo VII: rede coletora, interceptores, linhas de recalque, EEE, ETE e emissário. -->

::: quadro {#qua:unidades fonte="Sanepar, {{ano}}."} Descrição das unidades que compõem o sistema
| Unidade | Características principais |
|---|---|
| São João do Triunfo - ETE | Área aproximada de 6.376 m²; [A VERIFICAR: características – vazão, Hm, potência, volume, material, diâmetro] |
| Rede coletora | [A VERIFICAR: extensão, diâmetros e material] |
| Interceptores / coletores-tronco | [A VERIFICAR: extensão, diâmetros e material] |
| Estações Elevatórias de Esgoto (EEE) | [A VERIFICAR: quantidade, vazão, Hm e potência] |
| Linhas de recalque | [A VERIFICAR: extensão, diâmetro e material] |
| Emissário | [A VERIFICAR: extensão, diâmetro e material] |
:::

### Descrição do Sistema de Tratamento Adotado

<!-- Na sequência do processo: tratamento preliminar (gradeamento, desarenador, medição de vazão),
     tratamento biológico (RALF/UASB, filtro, lagoas...), pós-tratamento, desinfecção,
     gerenciamento do lodo e do biogás. Eficiência esperada de remoção de DBO. -->
O tratamento adotado é do tipo {{ete.processo}}, com eficiência esperada de remoção de DBO de {{ete.eficiencia_dbo_pct}}%. [A VERIFICAR: descrição do processo de tratamento, etapa por etapa, e do gerenciamento do lodo.]

### Projetos das Unidades que Compõem o Sistema

A localização e a disposição das unidades que integram o empreendimento são apresentadas nas plantas constantes dos Anexos, conforme relação apresentada no @qua:anexos.

::: quadro {#qua:anexos fonte="Sanepar, {{ano}}."} Relação das unidades que compõem o empreendimento e respectivos anexos
| Unidade/ponto | Projeto |
|---|---|
| São João do Triunfo - ETE | Anexo I |
:::
