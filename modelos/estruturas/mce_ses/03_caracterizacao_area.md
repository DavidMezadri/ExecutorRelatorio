# Caracterização da Área

O empreendimento é composto pelas unidades delimitadas no arquivo georreferenciado do projeto ({{unidades_nomes|lista}}), que abrangem, conforme os projetos do sistema, as seguintes unidades: {{unidades_sistema|lista}}. As características de cada unidade são detalhadas no item 4. A seguir são apresentadas a área de influência, as áreas ocupadas e as coordenadas das unidades.

## Delimitação e Caracterização da Área de Influência

Área Diretamente Afetada – ADA: corresponde às áreas diretamente destinadas à implantação das estruturas e infraestruturas que compõem o empreendimento, incluindo as unidades pontuais e as faixas necessárias à implantação das adutoras, abrangendo os locais sujeitos às intervenções físicas decorrentes das obras.

## Área Onde será Implantada a Atividade

<!-- IN 37: área total, área construída e área livre. Áreas e extensões abaixo foram calculadas do KMZ.
     Completar área construída/livre com o projeto da Sanepar. -->
O @qua:areas apresenta a área ocupada por cada unidade do sistema, obtida a partir da delimitação georreferenciada das unidades projetadas. A área total do empreendimento, correspondente à soma das áreas das unidades delimitadas, é de {{area.total_m2|num:2}} m² ({{area.total_ha|num:2}} ha). As áreas construída e livre correspondem, respectivamente, a {{area.construida_m2|num:2}} m² e {{area.livre_m2|num:2}} m².

!quadro[Áreas ocupadas pelas unidades do sistema projetado](dados/coordenadas.xlsx){#qua:areas filtro="area_m2 == area_m2" colunas="unidade:Unidade,area_m2:Área (m²),area_ha:Área (ha)" fonte="Sanepar, {{ano}}; adaptado pelo autor, {{ano}}."}

Complementarmente às áreas pontuais de cada unidade, o @qua:adutoras apresenta a extensão das unidades lineares do sistema.

!quadro[Extensão das unidades lineares do sistema projetado](dados/coordenadas.xlsx){#qua:adutoras filtro="extensao_m == extensao_m and referencia == 'início'" colunas="unidade:Unidade,extensao_m:Extensão (m)" casas=0 fonte="Sanepar, {{ano}}; adaptado pelo autor, {{ano}}."}

<!-- Material e diâmetro das tubulações: acrescentar a partir do memorial descritivo da Sanepar. -->

## Coordenadas Geográficas e UTM

As coordenadas das unidades do empreendimento são apresentadas no @qua:coordenadas, no Sistema de Referência SIRGAS 2000, em coordenadas geográficas e na projeção UTM. Para as unidades lineares (adutoras), são indicados os pontos inicial e final do traçado.

!quadro[Coordenadas geográficas e UTM das unidades do empreendimento (SIRGAS 2000)](dados/coordenadas.xlsx){#qua:coordenadas colunas="unidade:Unidade,referencia:Ponto,latitude_gms:Latitude,longitude_gms:Longitude,utm_e:E (m),utm_n:N (m),fuso:Fuso" tamanho=9 fonte="Elaborado pelo autor, {{ano}}."}

A seguir são apresentados os mapas de localização das unidades que compõem o empreendimento.

::: paisagem
![Localização das unidades projetadas](mapas/localizacao_unidades.png){#fig:loc-unidades}
:::

![Mapa de localização regional](mapas/localizacao_regional.png){#fig:loc-regional}

<!-- Para cada unidade (captação, ETA, reservação...): imagem de localização + foto de campo, como no modelo.
     Ex.: ![Vista da área destinada à captação](fotos/captacao_01.jpg){fonte="Autor, {{ano}}."} -->

## Alternativa de Acessos ao Empreendimento

<!-- IN 37: acessos (alternativas, condições de tráfego). -->
O Paraná está inserido na Região Sul do território brasileiro, fazendo divisa, ao norte, com o estado de São Paulo, a leste, com o oceano Atlântico, ao sul, com Santa Catarina, a sudoeste e oeste, respectivamente, com a Argentina e o Paraguai, e, a noroeste, com o estado de Mato Grosso do Sul. O estado ocupa uma extensão territorial de aproximadamente 199.575 km².

O município de {{municipio}} está localizado na mesorregião {{municipio_info.mesorregiao}}, na Região Geográfica Imediata de {{municipio_info.regiao_imediata}}. Possui área territorial de aproximadamente {{municipio_info.area_km2|num:0}} km² e população de {{municipio_info.populacao_2022|num:0}} habitantes (IBGE, 2022). Faz divisa com os municípios de {{municipio_info.limitrofes|lista}}.

O município dista aproximadamente {{dossie.acesso.distancia_capital_km|num:0}} km de Curitiba por via rodoviária (OSRM, 2026), sendo servido, na região do empreendimento, pelas rodovias {{dossie.acesso.rodovias_15km|lista}} (OPENSTREETMAP, 2026).

<!-- Gerado por ferramentas.geo.acessos (rotas OSRM + vias/revestimento do OpenStreetMap + mapa). -->
{{auto.acessos}}

## Caracterização Meio Físico

### Pedologia

<!-- Mapa de solos (fase 3: Embrapa/IAT). Descrever as classes que ocorrem na área (SiBCS/Embrapa),
     seguindo o padrão do modelo: características, limitações, suscetibilidade à erosão. -->
{{auto.pedologia}}

![Mapa de solos da área do empreendimento](mapas/solos.png){#fig:solos}

{{auto.pedologia_fotos}}

#### Uso do Solo

{{auto.uso_solo}} O uso do solo na área do empreendimento é apresentado na @fig:uso-solo.

![Uso do solo na área do empreendimento](mapas/uso_solo.png){#fig:uso-solo}

### Geomorfologia

O território paranaense é constituído por três grandes unidades morfoestruturais: o Cinturão Orogênico do Atlântico, a Bacia Sedimentar do Paraná, que se estende pela porção central e ocidental do Estado, e as Bacias Sedimentares Cenozóicas e Depressões Tectônicas. Na sua configuração, predomina o relevo de planalto, sendo reconhecidos cinco compartimentos geomorfológicos (grandes unidades morfoesculturais): Litoral, Serra do Mar, Primeiro Planalto, Segundo Planalto e Terceiro Planalto Paranaense (MAACK, 1968).

{{auto.geomorfologia}}

![Geomorfologia da área do empreendimento](mapas/geomorfologia.png){#fig:geomorfologia}

![Altimetria da área do empreendimento](mapas/altimetria.png){#fig:altimetria}

![Declividades existentes na área do empreendimento](mapas/declividade.png){#fig:declividade}

### Hidrologia

<!-- IN 37: recursos hídricos (nascentes, olhos d'água, cursos d'água). Há camadas de nascentes e rios
     do município em dados/ – usar no mapa de bacia/APP e citar quantos cursos d'água são interceptados. -->
O Paraná possui 16 bacias hidrográficas: Bacia do Rio das Cinzas, Bacia do Rio Iguaçu, Bacia do Rio Itararé, Bacia do Rio Ivaí, Bacia Litorânea, Bacia do Paraná 1, Bacia do Paraná 2, Bacia do Paraná 3, Bacia do Paranapanema 1, Bacia do Paranapanema 2, Bacia do Paranapanema 3, Bacia do Paranapanema 4, Bacia do Rio Piquiri, Bacia do Rio Pirapó, Bacia do Rio Ribeira e Bacia do Rio Tibagi (BRASIL, 2015).

A Resolução CERH/PR nº 49/2006 agrupa essas bacias em 12 unidades hidrográficas: Unidade Hidrográfica Litorânea; Unidade Hidrográfica do Alto Iguaçu, Afluentes do Rio Negro e Afluentes do Rio Ribeira; Unidade Hidrográfica do Itararé, do Cinzas, do Paranapanema 1 e do Paranapanema 2; Unidade Hidrográfica do Baixo Tibagi; Unidade Hidrográfica do Alto Tibagi; Unidade Hidrográfica do Pirapó, do Paranapanema 3 e do Paranapanema 4; Unidade Hidrográfica do Alto Ivaí; Unidade Hidrográfica do Baixo Ivaí e do Paraná 1; Unidade Hidrográfica da Bacia do Piquiri e do Paraná 2; Unidade Hidrográfica do Paraná 3; Unidade Hidrográfica dos Afluentes do Médio Iguaçu e Unidade Hidrográfica dos Afluentes do Baixo Iguaçu.

No âmbito local, o corpo receptor do efluente tratado é o {{corpo_receptor.nome}}, enquadrado na {{corpo_receptor.classe}}. [A VERIFICAR: vazão de referência do corpo receptor e cursos d'água interceptados pelas unidades lineares.]

{{auto.hidrologia}}

![Bacia hidrográfica do empreendimento](mapas/bacia.png){#fig:bacia}

### Geologia

{{auto.geologia}}

![Geologia das áreas do empreendimento](mapas/geologia.png){#fig:geologia}

### Hidrogeologia

{{auto.hidrogeologia}}

![Hidrogeologia das áreas do empreendimento](mapas/hidrogeologia.png){#fig:hidrogeologia}

## Caracterização Meio Biótico (Cobertura Vegetal)

<!-- IN 37: cobertura vegetal. Enquadramento fitogeográfico (IBGE, 2012; IAT, 2023), aspectos de campo,
     espécies registradas (do Inventário Florestal, se houver), fotos. -->
{{auto.fitogeografia}}

![Enquadramento fitogeográfico da área do empreendimento](mapas/fitogeografia.png){#fig:fitogeografia}

### Áreas de Preservação Permanente e Reserva Legal

As áreas com vegetação nativa existentes no entorno do empreendimento desempenham importante função ecológica, atuando como corredores ecológicos que favorecem o deslocamento da fauna, promovem o fluxo gênico entre populações, contribuem para a conservação da biodiversidade, a proteção dos recursos hídricos, a estabilidade geológica, a conservação do solo e a manutenção da paisagem.

{{auto.app_metodo}}

{{auto.app}}

::: paisagem
![{{auto.app_titulo}}](mapas/app_rl.png){#fig:app}
:::

## Caracterização Meio Socioeconômico

### Residências, condições do entorno

<!-- IN 37: características do entorno (uso do solo, residências, áreas de interesse ambiental).
     Padrão do modelo: percorrer o traçado do início ao fim descrevendo propriedades, estradas,
     residências, escolas, igrejas, com fotos de campo. -->
{{auto.socio}}
