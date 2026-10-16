# Caracterização do Empreendimento

## Descrição Resumida do Empreendimento

<!-- IN 37 Anexo X, 2.1 a) a h). Detalhes técnicos ficam no item 4 (Projeto Básico da ETA). -->

**a) Nome do SAA:** Sistema de Abastecimento de Água de {{municipio}}/{{uf}} [A VERIFICAR: nome oficial do sistema].

**b) Características técnicas das unidades em licenciamento:** apresentadas no @qua:unidades-resumo.

::: quadro {#qua:unidades-resumo fonte="{{empresa.sigla}}, {{ano}}."} Unidades do sistema em licenciamento
| Unidade | Características técnicas |
|---|---|
<<UNIDADES_LINHAS>>
:::

**c) Bairros a serem atendidos:** {{bairros_atendidos}}.

**d) Horizonte de alcance do projeto:** {{horizonte_projeto_anos}} anos.

**e) Vazão de fim de plano da ETA:** {{eta.capacidade_maxima_ls|num:2}} L/s. <!-- confirmar se a vazão de fim de plano coincide com a capacidade máxima -->

**f) Vazão outorgada de captação:** [A VERIFICAR: vazão em L/s] (Portaria {{manancial.outorga_captacao}}).

**g) População de fim de plano:** {{populacao.final_plano_hab|num:0}} habitantes ({{populacao.final_plano_ano}}).

**h) Coordenadas do ponto de captação (UTM SIRGAS 2000):** ver @qua:coordenadas.

!quadro[Coordenadas das unidades do sistema (SIRGAS 2000)](dados/coordenadas.xlsx){#qua:coordenadas colunas="unidade:Unidade,referencia:Ponto,latitude_gms:Latitude,longitude_gms:Longitude,utm_e:E (m),utm_n:N (m),fuso:Fuso" tamanho=9 fonte="Elaborado pelo autor, {{ano}}."}

::: paisagem
![Localização das unidades do sistema](mapas/localizacao_unidades.png){#fig:loc-unidades}
:::

## Estimativa de População e Vazões

<!-- IN 37 2.2: populações residente e flutuante, início e alcance de plano, vazões ano a ano. -->

::: quadro {#qua:populacao fonte="{{empresa.sigla}}, {{ano}}."} Estimativa de população atendida e vazões de projeto
| Ano | População residente (hab) | População flutuante (hab) | Demanda média (L/s) | Demanda máxima diária (L/s) |
|---|---|---|---|---|
| {{populacao.inicio_plano_ano}} | {{populacao.inicio_plano_hab|num:0}} | [A VERIFICAR] | [A VERIFICAR] | [A VERIFICAR] |
| {{populacao.final_plano_ano}} | {{populacao.final_plano_hab|num:0}} | [A VERIFICAR] | [A VERIFICAR] | [A VERIFICAR] |
:::

## Caracterização da Água de Fornecimento ao Sistema

**a) Manancial de abastecimento:** {{manancial.nome}} ({{manancial.tipo}}), {{manancial.bacia}}, {{manancial.classe}}.

**b) Coordenadas do ponto de captação (UTM SIRGAS 2000):** ver @qua:coordenadas.

**c) Vazão outorgável de adução:** [A VERIFICAR: L/s] (Portaria {{manancial.outorga_captacao}}).

**d) Concentrações dos principais parâmetros na entrada da ETA:** [A VERIFICAR: turbidez, cor aparente, pH, alcalinidade, ferro, manganês, coliformes – séries de monitoramento da Sanepar].
