# Extração de dados técnicos – MCE SAA General Carneiro

Gerado por `ferramentas.ingestao.memorial`. Os memoriais não têm padrão: os valores são achados pela unidade (L/s, hab, DN...) e classificados pelo contexto. Conferir no documento de origem antes de usar.


## Sugestões para a ficha (projeto.yaml)

| Campo | 1º candidato | Pontos | Origem | Outros candidatos |
|---|---|---|---|---|
| eta.capacidade_nominal_ls | **1.94 L/s (de 7 m³/h) – _vazão de operação normal (convertida de m³/h)_** | 10 | 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.9 | 2.78 (3) |
| eta.capacidade_maxima_ls | **2.78 L/s (de 10 m³/h) – _vazão de projeto do tratamento = capacidade testada do poço (convertida de m³/h)_** | 10 | 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.9 | 2.78 (3) |
| manancial.vazao_outorgada_ls | **2.78 L/s (de 10,0 m³/h)** | 2 | 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.8 |  |
| populacao.demanda_m3_dia | **52.8 m³/dia – _demanda média de água_** | 10 | 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.7 | 52.8 (5); 240.2 (3); 167.6 (3) |
| populacao.final_plano_hab | **294 – _população ao fim do plano_** | 10 | 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.7 |  |
| horizonte_projeto_anos | **20 anos** | 10 | 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.7 |  |
| manancial.nome | **Poço CSB-01 – _identificação da captação_** | 10 | 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.7 |  |
| coordenadas.lat_lon_referencia | **25°49'49.4"S 52°44'00.7"W – _SIRGAS 2000_ [só informativo]** | 10 | 001-saa-0674-0000-lega-de-0000csb01jangada-r0.md p.1 |  |
| imoveis_terceiros_decreto | **Decreto de Utilidade Pública nº 20.671 de 24/06/1970 – _citado na planta de legalização_ [só informativo]** | 10 | 001-saa-0674-0000-lega-de-0000csb01jangada-r0.md p.1 |  |
| acessos_rodovia | **BR-153 – _rodovia desenhada na planta_ [só informativo]** | 10 | 001-saa-0674-0000-lega-de-0000csb01jangada-r0.md p.1 |  |
| autoria_projeto.gerente_sanepar | **Joel Pires (CREA 100.276 - D/PR) – _gerente Sanepar no carimbo_ [só informativo]** | 10 | 001-saa-0674-0000-lega-de-0000csb01jangada-r0.md p.1 |  |
| coordenadas.utm_vertice_A1 | **E=474.334,955 N=7.083.057,963 – _SIRGAS 2000 / UTM 22S (MC 51°W); comparar com o KMZ_ [só informativo]** | 10 | 001-saa-0674-0000-lega-md-0000csb01jangada-r0.md p.1 |  |
| manancial.sia | **5079 – _código SIA da captação_ [só informativo]** | 10 | 001-saa-0674-9142-pben-md-0000ger00invflorestal-r0.md p.4 |  |
| manancial.bacia | **Bacia do Rio Iguaçu – _bacia hidrográfica_** | 10 | 001-saa-0674-9142-pben-md-0000ger00invflorestal-r0.md p.46 |  |
| autoria_projeto.projetista | **Song Jon Scremin (CREA 166.833 - D/PR) – S.J.M.H. Engenharia e Construções Ltda. – _responsável técnico do PROJETO de engenharia (não é o RT do MCE)_ [só informativo]** | 10 | 001-saa-0674-9142-pbhi-de-0000ger000patioamardre-r0.md p.1 |  |
| populacao.inicio_plano_ano | **2026 – _início do horizonte de projeto_** | 10 | 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.7 |  |
| populacao.final_plano_ano | **2045 – _fim do horizonte de projeto_** | 10 | 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.7 |  |
| manancial.tipo | **subterrânea (poço profundo, 120 m de profundidade) – _tipo de captação_** | 10 | 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.7 |  |
| eta.regime_operacao_h_dia | **8 h/dia – _operação prevista da elevatória (o poço foi testado em 20 h/dia)_** | 10 | 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.8 |  |
| manancial.profundidade_m | **120 m – _profundidade do poço_ [só informativo]** | 10 | 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.8 |  |
| eta.processo | **hipoclorito de sódio (cloração/desinfecção) e ácido fluossilícico (fluoração) – _produtos e etapas do tratamento_** | 10 | 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.9 |  |
| area.casa_quimica_m2 | **31.7 m² – _parcial: só a casa de química (área construída total depende das demais edificações)_ [só informativo]** | 10 | 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.9 |  |
| imoveis_terceiros | **[{'matricula': '5.744', 'cartorio': 'CRI DE UNIÃO DA VITÓRIA', 'intervencoes': [{'descricao': 'LEGALIZAÇÃO DA FAIXA DE SERVIDÃO DE ACESSO À ÁREA DO POÇO CSB01', 'area_atingida_m2': 212.13, 'art_levantamento': '1720231599408', 'responsavel_levantamento': 'Paulo Cezar Tosin (CREA PR-11.534/D)'}, {'descricao': 'LEGALIZAÇÃO DA ÁREA DO POÇO CSB01', 'area_atingida_m2': 494.0, 'art_levantamento': '1720231599408', 'responsavel_levantamento': 'Paulo Cezar Tosin (CREA PR-11.534/D)'}], 'area_m2': 440550.0, 'incra': '724.041.003.778-1', 'comarca': 'JANGADA DO SUL', 'proprietario': 'FELIPE CHABATURA E OUTROS OU A QUEM DE DIREITO PERTENCER'}] – _imóvel afetado, dos memoriais de legalização_** | 10 | 001-saa-0674-0000-lega-md-0000csb01jangada-r0.md p.1 |  |

## Divergências entre fontes

- Extensão da adutora: memorial 393 m (004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.7) × KMZ 594.2 m ('Jangada do Sul - General Carneiro Adutora') – diferença de 51%. Conferir qual traçado vale (o KMZ pode incluir trecho a mais ou ser anterior ao projeto).
- 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md: descreve captação subterrânea (poço CSB-01), mas também cita 'pátio da captação superficial' – provável erro de redação do projeto; usar 'subterrânea'.

## Mapa de páginas (onde ler cada assunto)

- **População e demanda:** 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.7 (10); 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.8 (6)
- **Vazões de projeto:** 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.8 (18); 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.7 (6); 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.9 (6); 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.12 (4)
- **Captação / manancial:** 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.8 (14); 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.12 (10); 001-saa-0674-9142-sond-de-0000plansondagem-r0.md p.94 (6); 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.7 (6); 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.9 (4); 001-saa-0674-0000-lega-de-0000csb01jangada-r0.md p.1 (3)
- **Tratamento (ETA/ETE):** 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.9 (7); 001-saa-0674-9142-sond-de-0000plansondagem-r0.md p.94 (6); 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.7 (6); 001-saa-0674-9142-pbhi-de-0000ger000patioamardre-r0.md p.1 (4)
- **Outorgas e licenças:** 001-saa-0674-9142-pben-md-0000ger00invflorestal-r0.md p.16 (4); 001-saa-0674-9142-pben-md-0000ger00invflorestal-r0.md p.62 (4); 001-saa-0674-9142-pben-md-0000ger00invflorestal-r0.md p.21 (3)
- **Unidades e tubulações:** 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.8 (20); 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.7 (16); 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.12 (15); 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.13 (12); 004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md p.9 (6); 004-saa-0674-9142-pbhi-de-0000eet01detalhamento-r0.md p.1 (4)
- **Desapropriação e imóveis:** 001-saa-0674-0000-lega-de-0000csb01jangada-r0.md p.1 (16); 002-saa-0674-0000-lega-de-0000csb01jangada-r0.md p.1 (13); 002-saa-0674-0000-lega-md-0000csb01jangada-r0.md p.1 (6); 001-saa-0674-0000-lega-md-0000csb01jangada-r0.md p.1 (5); averbacao-de-decreto.md p.1 (4); averbacao-de-decreto.md p.2 (3)
- **Obras, cronograma e mão de obra:** 001-saa-0674-9142-pben-md-0000ger00invflorestal-r0.md p.45 (5); 001-saa-0674-9142-pben-md-0000ger00invflorestal-r0.md p.46 (4)
- **Produtos químicos:** 001-saa-0674-9142-pbhi-de-0000rda01detalhamento-r0.md p.1 (23); 002-saa-0674-9142-pbhi-de-0000rda01detalhamento-r0.md p.1 (23); 003-saa-0674-9142-pbhi-de-0000rda01detalhamento-r0.md p.1 (22); 001-saa-0674-9142-sond-de-0000plansondagem-r0.md p.94 (18); 002-saa-0674-9142-pbhi-de-0000ger000patiointerli-r0.md p.1 (18); 003-saa-0674-9142-pbhi-de-0000csb01detalhamento-r0.md p.1 (18)

## Todos os valores encontrados


### Vazões (5 valores distintos)

- **52,8 m³/dia** — _004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md, p. 7_ — …abastecida estimada para este distrito será de aproximadamente 294 habitantes e a demanda média de água será 52,8 m³/dia. Para o atendimento a estas demandas, foram projetados, para o sistema:  Nova captação subterrânea, CSB-01…
- **7,0 m³/h** — _004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md, p. 7_ — … Nova captação subterrânea, CSB-01 (Poço 01), contando com uma nova elevatória de água bruta, a EEB-01 (Q: 7,0 m³/h Hm: 63 mca);  Novo pátio de tratamento para a água bruta do CSB-01, com casa de química para simples clor…
- **10,0 m³/h** — _004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md, p. 8_ — …. Trata-se de uma captação subterrânea com 120 metros de profundidade e capacidade de exploração testada de 10,0 m³/h em regime de 20 horas diárias. A nova elevatória de água bruta, EEB-01, contará com tubo edutor em Aço Carbo…
- **10 m³/h** — _004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md, p. 8_ — …na parte superior do reservatório RAP-02. A EEB-01, recalcará apenas 7,0 m³/h (vazão testada do poço foi de 10 m³/h) para o reservatório apoiado, RAP-02, uma vez que, o estudo de demandas mostrou uma vazão demandada para o…
- **7 m³/h** — _004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md, p. 9_ — …ojetado para a vazão de produção do poço CSB-01 de até 10 m³/h, embora o mesmo deverá operar normalmente com 7 m³/h. A casa de química projetada é uma edificação de pavimento térreo com 31,70 m² de área total. Esta edificaç…

### População (1 valores distintos)

- **294 habitantes** — _004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md, p. 7_ — …eendido de 2026 até 2045, quando a população abastecida estimada para este distrito será de aproximadamente 294 habitantes e a demanda média de água será 52,8 m³/dia. Para o atendimento a estas demandas, foram projetados, para o si…

### Horizonte de projeto (1 valores distintos)

- **horizonte de projeto de 20 anos** — _004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md, p. 7_ — …Para o projeto de ampliação e melhorias no SAA General Carneiro – Distrito de Jangada do Sul, foi adotado o horizonte de projeto de 20 anos, compreendido de 2026 até 2045, quando a população abastecida estimada para este distrito será de aproximad…

### Portarias (outorga) (2 valores distintos)

- **Portaria 300/200** — _002-saa-0674-9142-pben-md-0000ger00planresgermo-r0.md, p. 9_ — …. ................ 14 Quadro 3:Número de indivíduos nativos e quantidade mínima a ser resgatada, conforme a Portaria 300/200 IAT. ........................................................................................................…
- **Portaria 300/2022** — _002-saa-0674-9142-pben-md-0000ger00planresgermo-r0.md, p. 25_ — …reprodutiva dessas espécies, a quantidade do material resgatado deve considerar o estabelecido no Art. 15 da Portaria 300/2022 IAT, ou seja, 80 % (das espécies raras, ameaçadas de extinção e endêmicas) e 20 % das demais espécies (Qua…

### Diâmetros (2 valores distintos)

- **DN150** — _004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md, p. 12_ — …o falso, com bomba submersa dotada de camisa de sucção. Este poço falso será alimentado por uma tubulação de DN150 mm advinda do RAP-02. O barrilete de recalque será em Aço Carbono Galvanizado Classe Pressão Média BSP Ø 2”…
- **DN50** — _008-saa-0674-9142-pbhi-de-0000vrp01detalhamento-r0.md, p. 1_ — …JANGADA DO SUL PROJETO/UNIDADE CONSTRUTIVA: ESCALA: INDICADA DATA: AGOSTO/2023 VÁLVULA REDUTORA DE PRESSÃO - DN50 (2") SISTEMA DE ABASTECIMENTO DE ÁGUA PROJETO BÁSICO HIDRÁULICO PLANTA, CORTE E DETALHE ARQUIVO ELETRÔNICO: 0…

### Extensões (1 valores distintos)

- **393 m** — _004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md, p. 7_ — …da rede de distribuição;  Nova adutora de água tratada, AAT-01, em PEAD DE90, com aproximadamente 393 m de extensão, para abastecimento da rede de distribuição com a água tratada proveniente do CSB-01;  Readequ…

### Volumes (8 valores distintos)

- **4,0820 m³** — _001-saa-0674-9142-pben-md-0000ger00invflorestal-r0.md, p. 59_ — …e indivíduos. Estimativas volumétrica das espécies nativa no local do empreendimento: Volume total geral: 4,0820 m³; Volume comercial (madeira) geral: 2,1291 m³; Volume residual (lenha) geral: 1,9529 m³. 3.1.6. Resumo…
- **2,1291 m³** — _001-saa-0674-9142-pben-md-0000ger00invflorestal-r0.md, p. 59_ — …pécies nativa no local do empreendimento: Volume total geral: 4,0820 m³; Volume comercial (madeira) geral: 2,1291 m³; Volume residual (lenha) geral: 1,9529 m³. 3.1.6. Resumo dos Resultados O quadro 9 apresenta os result…
- **1,9529 m³** — _001-saa-0674-9142-pben-md-0000ger00invflorestal-r0.md, p. 59_ — …olume total geral: 4,0820 m³; Volume comercial (madeira) geral: 2,1291 m³; Volume residual (lenha) geral: 1,9529 m³. 3.1.6. Resumo dos Resultados O quadro 9 apresenta os resultados considerando espécies nativas e exótica…
- **30,0 m³** — _001-saa-0674-9142-pbhi-de-0000ger000patioamardre-r0.md, p. 1_ — …## Página 1 N NE NW W SW S SE E N NE NW W SW S SE E N NE NW W SW S SE E EET-01 EET-01 CASA DE QUÍMICA RAP-02 30,0 m³ RAP-02 30,0 m³ CSB-01 CSB-01 N NE NO O SO S SE E NOVO PÁTIO DE RESERVAÇÃO E TRATAMENTO NOVO PÁTIO DE RESERVA…
- **30m³** — _004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md, p. 7_ — …o CSB-01, com casa de química para simples cloração e fluoração (SCF-01);  Novo Reservatório, o RAP-02, de 30m³ em PRFV apoiado sobre base de concreto;  Nova elevatória de água tratada, a EET-01 (Q: 7,0 m³/h Hm: 55 mca…
- **30 m³** — _004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md, p. 9_ — …co. O contato destes produtos químicos será realizado no reservatório projetado RAP-02, que possui volume de 30 m³ de reserva. Este sistema de tratamento foi projetado para a vazão de produção do poço CSB-01 de até 10 m³/h,…
- **53 m³** — _004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md, p. 12_ — …tos seja alcançado. O volume total demandado para o sistema, em final de plano, deve ser de aproximadamente 53 m³. A vazão de adução do poço CSB-01 é de 7 m³/h, portanto o volume de contato mínimo para este tratamento, ser…
- **3,5 m³** — _004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md, p. 12_ — …zão de adução do poço CSB-01 é de 7 m³/h, portanto o volume de contato mínimo para este tratamento, seria de 3,5 m³ para atender ao tempo de contato. Como o reservatório tem 30 m³ nominais, o volume será suficiente para aten…

### Processo de tratamento (1 valores distintos)

- **desinfecção) e ácido fluossilícico (fluor** — _004-saa-0674-9142-pbhi-md-0000ger00planoperacao-r0.md, p. 9_ — …2 TRATAMENTO – SCF-02 Ficou definido para o presente projeto a utilização de hipoclorito de sódio (cloração/desinfecção) e ácido fluossilícico (fluoração). Ambos os produtos serão fornecidos em bombonas de 25 kg. O tratamento da água do CSB-01 será realizad…

### Matrículas de imóveis (1 valores distintos)

- **MATRÍCULA N.°5744** — _averbacao-de-decreto.md, p. 1_ — …da Vitória - Paraná 5744 Praçs Alvir Riesomborg, 65- Pono: 22-3246 RUBRICA TITULAR: IBELMAR SELEME CP056900 9 MATRÍCULA N.°5744 LIVRO N.° 2 MATRfCULA (5744) - 23 de agosto de 1983.-IMÓVEL:Uma área de terras ry rais, medindo 440.550m2(QUA…

### Cursos d'água citados (5 valores distintos)

- **Rio Jangada** — _001-saa-0674-9142-pben-md-0000ger00invflorestal-r0.md, p. 12_ — …............................................................................ 18 Figura 2: Fragmento nativo e Rio Jangada junto a área do empreendimento. .................. 19 Figura 3: Disposição do Fragmento. ...................…
- **Rio das Jangada** — _001-saa-0674-9142-pben-md-0000ger00invflorestal-r0.md, p. 27_ — …florestal cercado por propriedades agrícolas, áreas de pastagem/campo e plantios florestais as margens do Rio das Jangada o qual forma um corredor ecológico na região. Figura 3: Disposição do Fragmento. Fonte: Autor, 2023. #…
- **Rio Iguaçu** — _001-saa-0674-9142-pben-md-0000ger00invflorestal-r0.md, p. 46_ — …ípio de General Carneiro e o empreendimento estão totalmente inseridos na bacia hidrográfica do Rio Iguaçu (Figura 27), que possui 1.320 km de extensão e 72.637 km² de área, sendo uma das principais bacias hi…
- **Rio Grande** — _001-saa-0674-9142-pben-md-0000ger00invflorestal-r0.md, p. 62_ — …lógico. 2002. 1ed. Clube da Árvore. BACKES, A.; NARDINO, M. Árvores, arbustos e algumas lianas nativas no Rio Grande do Sul. São Leopoldo: Ed. da UNISINOS, 1998. 202 p. BRASIL. LEI N° 11.428, de 22 de dezembro de 2006. Dis…
- **Rio Iguaçu Bioma** — _002-saa-0674-9142-pben-md-0000ger00planresgermo-r0.md, p. 11_ — …F: General Carneiro – PR. Área total inventariada: 756 m² (0,0756 hectares). Bacia Hidrográfica: Bacia do Rio Iguaçu Bioma: Mata Atlântica. Tipologia Florestal: Floresta Ombrófila Mista (Montana). ## Página 12 Plano de Resgate de…

### Portarias florestais/ambientais (NÃO são outorga) (5 valores distintos)

- **Portaria n°300/2022.** — _001-saa-0674-9142-pben-md-0000ger00invflorestal-r0.md, p. 15_ — …etação está prevista na Lei Federal n°12.651/2012, Resolução SEMA‐PR n°21/2009, Lei Federal n° 11.428/2006 e Portaria n°300/2022. 1.2. Justificativa A intervenção em vegetação em estágio inicial, médio e avançado de regeneração de fl…
- **Portaria IAP n° 233** — _001-saa-0674-9142-pben-md-0000ger00invflorestal-r0.md, p. 16_ — …ei da Mata Atlântica, a resolução SEMA‐PR nº21 de 22 de abril de 2009, Decreto nº387 de 3 de março do 1999, Portaria IAP n° 233 de 30 de novembro de 2004 que revoga a Portaria Estadual IAP nº 207 de 2002, a resolução SEMA nº 0…
- **portaria nº 300/2022** — _001-saa-0674-9142-pben-md-0000ger00invflorestal-r0.md, p. 20_ — …sitos, critérios e procedimentos administrativos referente a licenciamento ambiental no Estado do Paraná. A portaria nº 300/2022 que estabelece a documentação necessária para análise do pedido de ASV e resgate da flora. A lei florestal d…
- **Portaria IAP n° 096** — _001-saa-0674-9142-pben-md-0000ger00invflorestal-r0.md, p. 21_ — …de 22 de dezembro de 2004 ‐ Altera o art. 7º da Lei nº 11.054, de 11 de janeiro de 1995. (Lei Florestal); ‐ Portaria IAP n° 096, de 22 de maio de 2007 ‐ Isenta a matéria prima florestal exótica da obrigatoriedade de reposição florestal,…
- **Portaria IAT n° 300/2022** — _002-saa-0674-9142-pben-md-0000ger00planresgermo-r0.md, p. 10_ — …o poço do distrito de Laranjeiras do Sul, do município de General Carneiro‐PR. De acordo com o previsto na Portaria IAT n° 300/2022 que estabelece os critérios e procedimentos para o requerimento de Autorização de Supressão de Vegetação – A…
