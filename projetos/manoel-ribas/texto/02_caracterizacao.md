# Caracterização do Empreendimento

## Descrição Resumida do Empreendimento

<!-- IN 37 Anexo XI, 2.1 a) a l). Detalhes técnicos ficam no item 4 (Projeto Básico). -->

**a) Nome do SES:** Sistema de Esgotamento Sanitário de {{municipio}}/PR [A VERIFICAR: nome oficial do sistema].

**b) Características técnicas das unidades em licenciamento:** as unidades que compõem o sistema são apresentadas no @qua:unidades-resumo. A ETE adota tratamento do tipo {{ete.processo}}; o lodo gerado será {{ete.lodo}}.

::: quadro {#qua:unidades-resumo fonte="Sanepar, {{ano}}."} Unidades do sistema em licenciamento
| Unidade | Características técnicas |
|---|---|
| Manoel Ribas - ETE | Área aproximada de 15.960 m²; [A VERIFICAR: características – vazão, Hm, potência, volume, material, diâmetro] |
:::

**c) Bairros a serem atendidos:** {{bairros_atendidos}}.

**d) Horizonte de alcance do projeto:** {{horizonte_projeto_anos}} anos.

**e) Vazão de alcance de plano da ETE:** {{ete.vazao_fim_plano_ls|num:2}} L/s.

**f) Vazão outorgada de lançamento:** {{corpo_receptor.vazao_outorgada_ls|num:2}} L/s (Portaria {{corpo_receptor.outorga_lancamento}}).

**g) Distância da ETE a núcleos populacionais:** {{ete.distancia_nucleo_populacional_m|num:0}} m, medidos a partir do perímetro da ETE até a área urbanizada mais próxima. <!-- valor calculado em dados/RESUMO_TEMATICO.md (distancia_area_urbana_m, MapBiomas) – conferir em imagem recente -->

**h) População de alcance de projeto (início de plano):** {{populacao.inicio_plano_hab|num:0}} habitantes ({{populacao.inicio_plano_ano}}).

**i) População de fim de plano:** {{populacao.final_plano_hab|num:0}} habitantes ({{populacao.final_plano_ano}}).

**j) Forma de disposição final do efluente:** lançamento do efluente tratado no {{corpo_receptor.nome}}.

**k) Coordenadas do ponto de lançamento (UTM SIRGAS 2000):** {{corpo_receptor.ponto_lancamento_utm_e}} E; {{corpo_receptor.ponto_lancamento_utm_n}} N.

**l) Localização das EEE e da ETE:** as coordenadas das unidades são apresentadas no @qua:coordenadas. [A VERIFICAR: rua de cada unidade e se a área é pública, da Sanepar ou objeto de desapropriação.]

!quadro[Coordenadas das unidades do sistema (SIRGAS 2000)](dados/coordenadas.xlsx){#qua:coordenadas colunas="unidade:Unidade,referencia:Ponto,latitude_gms:Latitude,longitude_gms:Longitude,utm_e:E (m),utm_n:N (m),fuso:Fuso" tamanho=9 fonte="Elaborado pelo autor, {{ano}}."}

## Plantas do Sistema

<!-- IN 37 Anexo XI 2.2 a) a f): área planejada com recursos hídricos e APP; bacias de esgotamento;
     faixa de domínio e interferências; posição da ETE/EEE/interceptores/emissário; acessos à ETE;
     ponto de lançamento. Mapas automáticos abaixo + plantas da Sanepar nos Anexos. -->

::: paisagem
![Delimitação da área do sistema, recursos hídricos e Áreas de Preservação Permanente](mapas/app_rl.png){#fig:app}
:::

![Localização das unidades do sistema](mapas/localizacao_unidades.png){#fig:loc-unidades}

[A VERIFICAR: bacias de esgotamento (planta Sanepar), faixa de domínio e interferências (viário, cursos d'água, adutoras, gasodutos, patrimônio), acessos provisórios e definitivos à ETE e ponto de lançamento – plantas nos Anexos.]

## Estimativa de População e Vazões

<!-- IN 37 2.3: populações residente e flutuante, início e alcance de plano, vazões ano a ano até a saturação.
     Copiar a tabela do estudo de concepção da Sanepar. -->

::: quadro {#qua:populacao fonte="Sanepar, {{ano}}."} Estimativa de população atendida e vazões de projeto
| Ano | População residente (hab) | População flutuante (hab) | Vazão média (L/s) | Vazão máxima (L/s) |
|---|---|---|---|---|
| {{populacao.inicio_plano_ano}} | {{populacao.inicio_plano_hab|num:0}} | [A VERIFICAR] | [A VERIFICAR] | [A VERIFICAR] |
| {{populacao.final_plano_ano}} | {{populacao.final_plano_hab|num:0}} | [A VERIFICAR] | [A VERIFICAR] | [A VERIFICAR] |
:::

## Caracterização da Água de Fornecimento ao Sistema

**a) Manancial de abastecimento:** {{manancial.nome}}.

**b) Coordenadas do ponto de captação (UTM SIRGAS 2000):** [A VERIFICAR: coordenadas da captação que abastece a área atendida].

**c) Vazão outorgável de adução:** {{manancial.vazao_outorgada_ls|num:2}} L/s (Portaria {{manancial.outorga_captacao}}).

**d) Concentrações dos principais parâmetros na entrada da ETA:** [A VERIFICAR: turbidez, cor, pH, ferro, manganês, coliformes – dados da Sanepar].
