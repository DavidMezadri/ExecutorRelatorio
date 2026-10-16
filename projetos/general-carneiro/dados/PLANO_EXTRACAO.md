# Plano de extração – MCE SAA General Carneiro (Jangada do Sul)

Legenda: ✅ o extrator atual já acerta · ⚠️ acha, mas errado/incompleto · ❌ não acha · 🔲 tarefa para o script

## 1. O que o cliente entregou (e o que cada arquivo contém)

| Arquivo(s) | Tipo | Conteúdo útil para o MCE |
|---|---|---|
| 004 …PBHI-MD…PLANOPERACAO (14 p.) | Memorial, texto | **Principal.** Horizonte 2026–2045, 294 hab, 52,8 m³/dia, CSB-01 (120 m, 10 m³/h, 20 h/dia), EEB-01/EET-01 (7 m³/h; 63/55 mca), RAP-02 30 m³, AAT-01 PEAD DE90 ~393 m, SCF-01 (hipoclorito + ácido fluossilícico), casa de química 31,70 m² |
| 001/002 …LEGA-DE e LEGA-MD (CSB01 Jangada) | Planta/memorial de legalização, vetorial | Matrícula 5744 (1º CRI União da Vitória), área do imóvel 440.550 m², área de atingimento 212,13 m², perímetro 71,32 m, proprietário, INCRA, lat/long (25°49'49.4"S 52°44'00.7"W), UTM 474.300 / 7.083.000, BR-153, decreto de utilidade pública 20.671/1970, ART 1720231599408, faixa de servidão |
| Averbação de decreto | PDF escaneado | Matrícula 5744 (OCR; números a conferir) |
| 001 …PBEN…INVFLORESTAL (78 p.) | Inventário florestal | Bacia do Rio Iguaçu, Rio Jangada, fragmento, volume 4,0820 m³, estágio da vegetação, Portaria 300/2022, espécies |
| 002 …PBEN…PLANRESGERMO (30 p.) | Plano de resgate | Área inventariada 756 m², Mata Atlântica, Floresta Ombrófila Mista Montana |
| 001 …SOND…PLANSONDAGEM (94 p.) | Sondagem | Perfis geotécnicos, nível d'água ausente, cota 850,50 m (**sem coordenadas**) |
| Unid. Localizadas 001–009 | Plantas de detalhe | Legenda de cada unidade (pátio, CSB-01, EET-01/RAP-02, SCF-01, AAT-01, VRP DN50, fluxograma); carimbo com **resp. técnico (Song Jon Scremin, CREA 166.833-D/PR, SJMH Engenharia)**, fiscais Sanepar |
| Unid. Lineares 001–003 | Plantas de rede | Detalhamento de redes/DN |
| 2 ZIPs | Duplicam as subpastas | Nada novo; ignorar |
| Lista de documentos (.xlsx) | Planilha | Só cabeçalho da Matriz Anexo VI. Nenhuma informação preenchida foi lida |
| KMZ (pasta "Jangada do sul SAA") | Geo | 2 unidades: polígono 1.555,73 m² e adutora 594,2 m |

## 2. Campos da ficha (projeto.yaml) × situação

| Campo | Está no material? | Onde | Extrator | Tarefa |
|---|---|---|---|---|
| populacao.final_plano_hab (294), final_plano_ano (2045), inicio_plano_ano (2026) | Sim | PLANOPERACAO p.7 | ⚠️ acha hab e horizonte, mas não os anos | 🔲 regra "de AAAA até AAAA" |
| populacao.inicio_plano_hab | Não | – | ❌ | Pedir ao cliente |
| populacao.demanda_m3_dia (52,8) | Sim | p.7 | ⚠️ 3 candidatos conflitantes (52,8; 240,2; 167,6) | 🔲 priorizar "demanda média … será" e ignorar valores de outras tabelas |
| horizonte_projeto_anos (20) | Sim | p.7 | ✅ | – |
| eta.capacidade_nominal_ls | Sim (10 m³/h = 2,78 L/s; opera 7 m³/h = 1,94 L/s) | p.8–9 | ⚠️ pegou limite do poço | 🔲 distinguir "capacidade testada" × "vazão de operação" |
| eta.regime_operacao_h_dia (20) | Sim | p.8 | ❌ | 🔲 padrão "regime de N horas diárias" |
| eta.processo | Sim (cloração + fluoração, SCF-01) | p.9 | ⚠️ saiu cortado | 🔲 capturar frase completa até o ponto |
| manancial.tipo (subterrâneo, poço CSB-01, 120 m) | Sim | p.7–8 | ❌ | 🔲 padrão "captação subterrânea … profundidade" |
| manancial.nome / classe / bacia | Bacia: Rio Iguaçu (inventário p.46). Nome: aquífero? Classe: não | – | ⚠️ confundiu cursos d'água | 🔲 bacia por "bacia hidrográfica do …"; **aquífero e classe: consultar SGB/SUDERHSA** |
| manancial.outorga_captacao | Não achado (só portarias de supressão) | – | ⚠️ portarias de ASV vieram como "outorga" | 🔲 separar portaria de outorga (IAT/AAS) de portaria florestal; pedir ao cliente |
| outorga_lancamento | Não se aplica (SAA) | – | – | Marcar "não se aplica" |
| endereco_unidade_principal | Parcial: BR-153, matrícula 5744, lat/long | LEGA | ❌ | 🔲 ler carimbo da planta |
| area.total_m2 (440.550 = imóvel; 1.555,73 = unidade KMZ) | Sim | LEGA + KMZ | ⚠️ não extrai | 🔲 definir qual área vale (imóvel × área de intervenção) |
| area.construida_m2 (casa de química 31,70 m² + RAP/EET) | Parcial | p.9 | ❌ | 🔲 somar edificações; confirmar com projeto |
| imoveis_terceiros (Felipe Chabatura e outros; mat. 5744) | Sim | LEGA | ⚠️ só matrícula | 🔲 extrair proprietário, INCRA, comarca, área |
| responsavel_tecnico (projeto) | Sim, mas é do projetista, não do ambiental | carimbos | ❌ | 🔲 extrair do carimbo (nome, CREA); **RT do MCE (Biocerne) vem de equipe.yaml** |
| art | ART do projeto 1720231599408 | LEGA | ❌ | 🔲 padrão "ART" + número |
| empreendedor.responsavel/telefone/email | Gerente Sanepar: Joel Pires (CREA 100.276-D/PR) | carimbo | ❌ | 🔲 carimbo + completar em dados_comuns/sanepar.yaml |
| cnae | Já preenchido | – | ✅ | – |
| acessos, area_influencia, bairros_atendidos | Parcial (BR-153) | – | ❌ | IA redige a partir de OSM/dossiê e do memorial |
| unidades[].descricao | Sim (cada planta) | Unid. Localizadas | ❌ | 🔲 ligar nome da unidade (CSB-01, EET-01, RAP-02, SCF-01, AAT-01, VRP) às plantas e ao KMZ |
| Extensão e DN da adutora | 393 m (memorial) × 594,2 m (KMZ) | p.7 + KMZ | ✅ extrai; **diverge do KMZ** | 🔲 gerar alerta de divergência |
| Coordenadas das unidades | UTM nas plantas; sondagem sem coordenadas | LEGA, AAT | ❌ | 🔲 extrair UTM/lat-long e comparar com KMZ |
| Supressão de vegetação (m², volume, espécies) | Sim | inventário p.59 e resgate | ⚠️ só volumes | 🔲 bloco "supressão" → redacao.supressao |

## 3. Falhas gerais do extrator (corrigir no script)

- [ ] 🔲 Falsos positivos: "DE 18" (data), "Rio de Janeiro", "Rio Grande (do Sul)". Exigir DN/DE com número plausível e excluir cidades/estados.
- [ ] 🔲 Portaria de **outorga** × portaria **florestal/ambiental**: classificar pelo contexto (ASV, supressão, Lei Florestal).
- [ ] 🔲 Conversão m³/h → L/s: manter os dois e mostrar qual é "testada" e qual é "operação".
- [ ] 🔲 Dedução por seção: ler o memorial por seções (Objetivo / Captação / Tratamento / Reservação) em vez de por janela de contexto.
- [ ] 🔲 Carimbo (selo) das plantas: parser próprio para pares rótulo → valor (RESP. TÉCNICO, CREA, ART, COMARCA, MAT., ÁREA).
- [ ] 🔲 Planilha de lista do cliente: ler todas as abas e células mescladas (hoje só vêm 2 linhas).
- [ ] 🔲 Ignorar ZIPs cujo conteúdo já está extraído.
- [ ] 🔲 Aviso de divergência entre fontes (memorial × KMZ × planta).
- [ ] 🔲 OCR: marcar números do escaneado como "conferir" e validar formato de matrícula.

## 4. O que só o cliente / a equipe pode fornecer

- [ ] Outorga ou portaria de captação do poço CSB-01 (nº, vazão, validade)
- [ ] População no início do plano (2026)
- [ ] Nome do aquífero, classe e dados de qualidade da água
- [ ] Contatos do empreendedor (telefone, e-mail, responsável)
- [ ] Responsável técnico e ART do MCE (preencher `dados_comuns/equipe.yaml`)
- [ ] Shapes do CAR/SICAR (Reserva Legal) em `dados/car/`
- [ ] Confirmar a localidade: o plano de resgate cita "Laranjeiras do Sul" (provável erro do cliente)
- [ ] Confirmar a divergência da adutora (393 m × 594,2 m)

## 5. Ordem sugerida para o script

1. Parser do carimbo → resp. técnico, CREA, ART, matrícula, comarca, área, coordenadas
2. Regras de seção do memorial → população/anos, demanda, regime, processo, manancial
3. Classificador de portarias e filtro de falsos positivos
4. Alerta de divergência (memorial × KMZ × planta)
5. Gerar `EXTRACAO_MEMORIAL.md` com "Sugestões para a ficha" já completo e rodar `--aplicar`

---
## 6. Status da implementação (15/10/2026)

Novo módulo `ferramentas/ingestao/memorial_diretos.py`, chamado por `ingestao.memorial` (regras por frase e por rótulo, pontuação 10, página de origem).

- [x] Anos do plano (2026–2045), população final (294), demanda (52,8 m³/dia), horizonte (20 anos)
- [x] Capacidade nominal = vazão de operação (7 m³/h = 1,94 L/s) e máxima = capacidade testada (10 m³/h = 2,78 L/s)
- [x] Regime de operação = 8 h/dia (a frase de 20 h/dia é do teste do poço, não da operação)
- [x] Tipo de captação (subterrânea, 120 m), nome (Poço CSB-01), código SIA 5079, bacia (Rio Iguaçu)
- [x] Processo de tratamento completo
- [x] Imóvel afetado: matrícula 5.744, CRI União da Vitória, INCRA, proprietário, comarca, 2 intervenções (servidão 212,13 m²; área do poço 494,00 m²), ART e levantamento
- [x] Carimbo: projetista (Song Jon Scremin, CREA 166.833-D/PR, SJMH), gerente Sanepar, lat/long, UTM, decreto, BR-153 (só informativo)
- [x] Tabelas duplicadas do PDF ignoradas; "DE 18 DE ABRIL", "Rio de Janeiro" e "Rio Grande do Sul" não entram mais
- [x] Portarias florestais separadas das de outorga
- [x] Divergências: adutora 393 m (memorial) × 594,2 m (KMZ); "captação superficial" no texto de um poço
- [ ] Planilha do cliente com todas as abas / células mescladas
- [ ] Ignorar ZIPs duplicados
- [ ] Área total e construída (decisão humana: imóvel × intervenção)
- [ ] Coordenadas dos furos de sondagem (o cliente não enviou)
- [ ] Testar o parser em memoriais de SES (outros projetos)
