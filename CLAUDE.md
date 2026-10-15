# ExecutorRelatorio – montagem de MCE/PCA (IN IAT 37/2025)

Ambiente para gerar documentos de licenciamento ambiental (MCE, PCA, RAP) de empreendimentos de
saneamento Sanepar (SAA/SES) em .docx quase prontos, no layout Biocerne Ambiental, a partir de KMZ,
planilhas e PDFs de projeto.

## Fluxo para montar um documento
Skills: `novo-projeto` (cadastrar), `montar-documento` (fluxo completo com redação), `conferir-documento` (revisão).
```
python -m ferramentas.pipeline <chave> --ate esqueleto   # iniciar, oficiais, tematico, mapas, esqueleto
#   -> preencher projeto.yaml (extraido/*.md) e redigir texto/*.md (RESUMO_TEMATICO.md, MAPAS.md, FONTES.yaml)
python -m ferramentas.pipeline <chave> --de montar       # montar, finalizar (Word), matriz
python -m ferramentas.docx.painel saida/X.pdf            # painéis de páginas para conferência visual
```
Etapas individuais: `iniciar_projeto`, `fontes.oficiais`, `geo.tematico`, `geo.mapas`, `docx.esqueleto`,
`docx.montar`, `docx.finalizar`, `conferencia.matriz` (todas `python -m ferramentas.<etapa> <chave>`).
Depois de montar, **conferir visualmente** os painéis (Read nos PNG) antes de entregar.

## Estrutura
- `projetos.yaml` – registro dos empreendimentos + `correcoes_nomes` (erros de digitação do KMZ).
- `dados_comuns/` – `sanepar.yaml`, `biocerne.yaml` (viram `{{sanepar.x}}`, `{{biocerne.x}}`), `cache/` (malha IBGE).
- `modelos/template_mce.docx` – template limpo derivado do MODELO Palmeira (logos, estilos, sumário/listas).
  Recriar: `python -m ferramentas.docx.template "<MODELO>.docx"`.
- `modelos/estruturas/{mce_saa,mce_ses,pca_saa,pca_ses}/` – textos-base de cada documento (Anexos VI, VII, X, XI).
- `modelos/matrizes/*.yaml` – itens de cada Termo de Referência ligados às seções (usado por `conferencia.matriz`).
- `referencias/` – IN 37/2025 em Markdown (Anexo VI = MCE SAA, VII = MCE SES, X = PCA SAA, XI = PCA SES,
  XIV = PGRS; buscar `^ANEXO VI`) e `modelo_mce_saa_palmeira.md` (texto do modelo: **imitar o estilo de redação**).
- `projetos/<chave>/` – `projeto.yaml` (ficha: **fonte única de dados**; `null` = falta), `dados/` (unidades.gpkg,
  coordenadas.xlsx, hidrografia, `oficiais/` + FONTES.yaml, **RESUMO_TEMATICO.md**, app.gpkg, `car/` p/ shapes do CAR),
  `extraido/` (planilhas/PDFs em .md – ler daqui), `texto/`, `mapas/` (+ MAPAS.md com fontes), `fotos/` (`brutas/`
  = originais), `imagens/` (+ CREDITOS.yaml), `anexos/` (PDFs de plantas), `saida/` (docx, pdf, PENDENCIAS.md, Matriz).

## Outras ferramentas
```
python -m ferramentas.geo.kml ARQ.kmz [--pasta X] [-o saida.gpkg]
python -m ferramentas.ingestao.pdf ARQ.pdf -o DIR [--tabelas] [--imagens]
python -m ferramentas.ingestao.planilhas ARQ.xlsx -o DIR
python -m ferramentas.ingestao.docx_texto ARQ.docx -o saida.md
python -m ferramentas.fontes.ibge "Município"       # código, Censo 2022, regiões, limítrofes
python -m ferramentas.fontes.oficiais <chave> [--so solos,dem]   # IBGE BDiA/BC250, SGB, ANA, Copernicus, MapBiomas
python -m ferramentas.geo.tematico <chave>          # cruza unidades x bases -> RESUMO_TEMATICO.md, app.gpkg
python -m ferramentas.geo.mapas <chave> [--so solos] # 12 mapas PNG (leiaute com grade UTM, norte, escala, legenda)
python -m ferramentas.imagens.fotos <chave>          # fotos/brutas -> fotos/ (EXIF/GPS, unidade, contato, mapa)
python -m ferramentas.imagens.web "termo" --projeto <chave>   # Wikimedia Commons, só licença livre
python -m ferramentas.conferencia.matriz <chave>    # matriz de atendimento ao TR (xlsx)
python -m ferramentas.geo.google_earth exportar <chave>   # KMZ p/ Google Earth Pro: unidades, vistas p/ figuras, APP, travessias, fotos
python -m ferramentas.geo.google_earth importar <chave> ARQ.kmz [--pasta X]   # pontos marcados no GE -> dados/pontos_ge.xlsx
python -m ferramentas.geo.google_earth importar <chave> --meus-lugares        # lê o "Meus lugares" do GE Pro
python-qgis.bat ferramentas\geo\qgis_projeto.py projetos\<chave>   # projeto .qgz (PC com QGIS; não testado)
```
Serviços sem acesso automático: CAR/SICAR (baixar shapes manualmente → `dados/car/`); UCs vêm da ANA.

## Dados do cliente: memoriais (PDF) e AutoCAD
```
python -m ferramentas.ingestao.memorial <chave> [--aplicar]   # vazões, população, horizonte, per capita, K1/K2, portarias,
                                                              # DN, extensões, volumes, kW, Hm, processo, DBO, matrículas, rios
python -m ferramentas.ingestao.cad <chave>                    # projetos/<chave>/cad/*.dxf|*.dwg -> camadas, extensão por DN,
                                                              # blocos (PV...), textos; se em UTM: cad_*.gpkg + comparação c/ KMZ
```
- Memoriais NÃO têm padrão: o extrator acha valores pela unidade (L/s, hab, DN…) e classifica pelo contexto
  (palavras antes do valor pesam mais), convertendo unidades. `dados/EXTRACAO_MEMORIAL.md` traz: **Sugestões para a
  ficha** (candidatos por campo com pontuação e página), **Mapa de páginas** (onde ler cada assunto) e todos os valores.
  `--aplicar` só preenche campos VAZIOS com 1º candidato forte (pontos >= 5 e vantagem >= 2) -> `EXTRACAO_APLICADA.md`.
  O resto: a IA lê as páginas indicadas no mapa e preenche citando a página.
- PDF escaneado: OCR local em português (RapidOCR) automático nas páginas sem texto (marcadas "conferir números").
  Word (.docx) e .txt da pasta do cliente também vão para `extraido/` no `iniciar_projeto`.
- AutoCAD: DWG precisa do ODA File Converter (gratuito) ou exportar como DXF. Quantitativos em `dados/cad_quantitativos.xlsx`.

## Redação automática e conferências
- `python -m ferramentas.redacao.redator <chave>` (etapa `redacao`): parágrafos com citação a partir dos dados ->
  `dados/redacao.yaml` = `{{auto.pedologia|uso_solo|geomorfologia|geologia|hidrogeologia|hidrologia|fitogeografia|app|`
  `erosao|alagadicos|supressao|entorno|territorios|ucs|impactos_especificos}}`. Revisar/refinar no texto (pode substituir
  a variável pelo texto editado).
- `python -m ferramentas.conferencia.citacoes <chave>` (etapa `citacoes`): citação sem referência, referência não citada,
  não conferidas -> `saida/CITACOES.md`.
- `python -m ferramentas.docx.declaracoes <chave> [--lac]`: Anexos II–V da IN 37 pré-preenchidos em `saida/declaracoes/`.
- `dados_comuns/equipe.yaml`: responsável técnico e representante da Sanepar – preencher uma vez (vale p/ todos os projetos).

## Dossiê padrão da localidade (igual para todo município)
`python -m ferramentas.dossie.gerar <chave> [--so bloco]` (também é etapa `dossie` do pipeline). Blocos fixos:
socioeconomia (IBGE: população, área, regiões, limítrofes, PIB), saneamento (Censo 2022 tabelas 6803/6805/6892: água,
esgoto, lixo), clima (NASA POWER + Köppen calculado), acesso (OSRM até Curitiba + rodovias OSM), entorno (OSM por
unidade: escolas, igrejas, saúde, comércio, edificações + CNES), territórios (FUNAI terras indígenas, UCs) e
consultas manuais (IPHAN, INCRA/Palmares, Plano Diretor, PMSB, CAR → viram pendências com link).
-> `dados/DOSSIE.md` (com "Citar como") e `dados/dossie.yaml` = variáveis `{{dossie.saneamento.esgoto_rede_pct|num:1}}`,
`{{dossie.acesso.distancia_capital_km}}`, `{{dossie.clima.koppen}}`... Referências entram sozinhas no catálogo do projeto.
Para incluir um novo dado padrão em todo município: novo coletor em `ferramentas/dossie/coletores.py` + `COLETORES`.

## Áudios de campo (transcrição local, Whisper)
Áudios em `projetos/<chave>/audios/AAAA-MM-DD/` (m4a, mp3, ogg/opus do WhatsApp, wav...). Skill `audio-campo`.
```
python -m ferramentas.audio.transcrever <chave> [--modelo small|medium|large-v3] [--observar]
python -m ferramentas.audio.transcrever --arquivo gravacao.m4a
```
-> `audios/AAAA-MM-DD/<nome>.md` (com [mm:ss]) + `extraido/transcricoes.md`; notas organizadas em `dados/NOTAS_CAMPO.md`.
No texto: "Durante a vistoria de campo realizada em DD/MM/AAAA, observou-se..." (data = nome da pasta).
Arquivos de áudio não vão para o git; as transcrições (.md) vão.

## Garimpo de fontes oficiais (sempre com referência ABNT precisa)
Toda informação externa entra no texto **com citação (AUTOR, ano) e referência no catálogo** – nunca escrever
referência "de memória". Catálogo: `referencias/bibliografia.yaml`; por projeto: `projetos/<chave>/referencias.yaml`;
a seção Referências usa `!referencias` (lista ABNT automática, ordenada; não conferidas saem marcadas).
```
python -m ferramentas.garimpo.especies entorno <chave> [--raio-km 10]      # fauna/flora GBIF + ameaça MMA 148/2022 + IUCN + Flora do Brasil
python -m ferramentas.garimpo.especies lista "Sp1" "Sp2" --projeto <chave>  # enriquece lista (ex.: inventário florestal)
python -m ferramentas.garimpo.especies especie "Nome científico"
python -m ferramentas.garimpo.legislacao catalogo | buscar <norma> | artigo <norma> 4 --inciso I | procurar <norma> "termo"
python -m ferramentas.garimpo.legislacao adicionar <chave> <url> --jurisdicao PARANÁ --orgao "..."   # nova norma
python -m ferramentas.garimpo.literatura buscar "tema" --brasil --desde 2010 [--aberto]   # estudos de caso (OpenAlex)
python -m ferramentas.garimpo.literatura doi <doi> --projeto <chave> [--baixar]          # ABNT via Crossref + PDF aberto
python -m ferramentas.garimpo.pagina <url> --projeto <chave>                            # página/PDF oficial -> texto + ABNT
python -m ferramentas.garimpo.biblio abnt --projeto <chave> | usar <chave> CHAVE | listar
```
- Leis: o texto vem do Planalto **sem a redação revogada** (riscada); citar artigo com `legislacao artigo`.
- Espécies do GBIF são registros secundários (ocorrência potencial) – dizer isso no texto; não substituem campo.
- Referência marcada [CONFERIR]/`verificado: false`: conferir na fonte antes de protocolar.
- Textos garimpados para leitura: `referencias/legislacao/`, `referencias/web/`, `referencias/literatura/` (PDFs fora do git).
- Sem acesso automático: LexML e SciELO (bloqueio antirrobô – usar OpenAlex), speciesLink (exige chave), SALVE/ICMBio.

## Sintaxe dos textos (texto/*.md)
- `# Título` … `####` – numerados automaticamente (3.1, 3.5.2…); `{-}` no fim = sem número. Nível 1 vira MAIÚSCULAS.
- `**negrito**`, `*itálico*`, `- item`, `a) item`, `\newpage`, `<!-- comentário/instrução (ignorado) -->`.
- `[A VERIFICAR: o que falta]` – destacado em amarelo e listado em `saida/PENDENCIAS.md`.
- `{{campo.sub}}` – variável do projeto.yaml/dados_comuns; filtros `|num:2` (pt-BR), `|lista` ("A, B e C"),
  `|upper`. Valor nulo vira `[A VERIFICAR: campo]` automaticamente.
- Figura: `![Legenda](mapas/x.png){#fig:id fonte="Autor, 2026." largura=15}` (imagem → legenda → Fonte).
- Quadro de arquivo: `!quadro[Legenda](dados/coordenadas.xlsx){#qua:id colunas="col:Título,..." filtro="..." casas=0 tamanho=9 larguras="3,1,1"}`.
- Quadro inline: `::: quadro {#qua:id fonte="..."} Legenda` + tabela Markdown + `:::`.
- PDF como imagem (anexos/plantas): `!pdf[Legenda opcional](anexos/x.pdf){paginas=1-3}`.
- Página paisagem: `::: paisagem` … `:::` (mapas grandes).
- Referência cruzada: `@fig:id` / `@qua:id` → "Figura 3" / "Quadro 2".

## Regras para redigir documentos
- **Nunca inventar dados técnicos** (vazões, população, outorgas, matrículas, áreas). Sem fonte → manter
  `[A VERIFICAR: ...]` e `null` no projeto.yaml.
- Áreas, extensões e coordenadas vêm de `dados/coordenadas.xlsx` (KMZ, SIRGAS 2000 / UTM).
- Seguir a ordem do Termo de Referência e do MODELO Palmeira; tom técnico e impessoal como no modelo.
- Todo dado público citado precisa de fonte no texto (AUTOR, ano) e entrada em Referências (ABNT).
- A "Lista de documentos e informações" de cada projeto (extraido/) diz o que a equipe tem e o que falta.
- Após montar, revisar PENDENCIAS.md e informar ao usuário o que ainda depende dele.

## Roteiro (status)
- [x] Ingestão: KMZ/KML, coordenadas/áreas/extensões, planilhas, PDFs, docx, ficha
- [x] Bases oficiais: IBGE (malha, Censo, BDiA, BC250), SGB, ANA, Copernicus DEM, MapBiomas; resumo temático e APP
- [x] Mapas automáticos (matplotlib) + projeto QGIS (não testado – máquina sem QGIS)
- [x] Imagens: fotos de campo (EXIF/GPS) e Wikimedia Commons
- [x] Documento: template Biocerne, estruturas MCE SAA/SES e PCA SAA/SES, montador, finalização via Word
- [x] Conferência: matriz de atendimento (Anexos VI, VII, X, XI), pendências, painéis
- [x] Pipeline e skills (`novo-projeto`, `montar-documento`, `conferir-documento`)
- [ ] Próximos: RAP (Anexos VIII/IX) e PGRS (Anexo XIV); leiaute .qpt próprio no QGIS; OCR para PDFs escaneados
