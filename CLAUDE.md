# ExecutorRelatorio – montagem de MCE/PCA (IN IAT 37/2025)

Ambiente para gerar documentos de licenciamento ambiental (MCE, PCA, RAP) de empreendimentos de
saneamento Sanepar (SAA/SES) em .docx quase prontos, no layout Biocerne Ambiental, a partir de KMZ,
planilhas e PDFs de projeto.

## Fluxo para montar um documento
```
python -m ferramentas.iniciar_projeto <chave>       # 1. ingere fontes + IBGE, cria projetos/<chave>/ e projeto.yaml
#                                                     2. preencher projeto.yaml a partir de extraido/*.md
python -m ferramentas.docx.esqueleto <chave>        # 3. cria texto/*.md a partir de modelos/estruturas/<doc>_<sis>/
#                                                     4. redigir texto/*.md (substituir os [A VERIFICAR] com fonte)
python -m ferramentas.docx.montar <chave>           # 5. gera saida/<DOC>_<SIS>_<mun>_<data>.docx + PENDENCIAS.md
python -m ferramentas.docx.finalizar <chave> --png  # 6. Word atualiza sumário/listas, gera PDF (+ páginas PNG)
python -m ferramentas.docx.painel saida/X.pdf       # 7. painéis de páginas para conferência visual
```
Depois do passo 6, **conferir visualmente** os painéis (Read nos PNG) antes de entregar.

## Estrutura
- `projetos.yaml` – registro dos empreendimentos + `correcoes_nomes` (erros de digitação do KMZ).
- `dados_comuns/` – `sanepar.yaml`, `biocerne.yaml` (viram `{{sanepar.x}}`, `{{biocerne.x}}`), `cache/` (malha IBGE).
- `modelos/template_mce.docx` – template limpo derivado do MODELO Palmeira (logos, estilos, sumário/listas).
  Recriar: `python -m ferramentas.docx.template "<MODELO>.docx"`.
- `modelos/estruturas/mce_saa/` – textos-base do MCE SAA (falta criar mce_ses, pca_ses, pca_saa).
- `referencias/` – IN 37/2025 em Markdown (Anexo VI = MCE SAA, VII = MCE SES, X = PCA SAA, XI = PCA SES,
  XIV = PGRS; buscar `^ANEXO VI`) e `modelo_mce_saa_palmeira.md` (texto do modelo: **imitar o estilo de redação**).
- `projetos/<chave>/` – `projeto.yaml` (ficha: **fonte única de dados**; `null` = falta), `dados/` (unidades.gpkg,
  coordenadas.xlsx, hidrografia), `extraido/` (planilhas/PDFs em .md – ler daqui), `texto/`, `mapas/`, `fotos/`,
  `imagens/`, `anexos/`, `saida/`.

## Outras ferramentas
```
python -m ferramentas.geo.kml ARQ.kmz [--pasta X] [-o saida.gpkg]
python -m ferramentas.ingestao.pdf ARQ.pdf -o DIR [--tabelas] [--imagens]
python -m ferramentas.ingestao.planilhas ARQ.xlsx -o DIR
python -m ferramentas.ingestao.docx_texto ARQ.docx -o saida.md
python -m ferramentas.fontes.ibge "Município"       # código, Censo 2022, regiões, limítrofes
```

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
- [x] Fase 0 – ambiente
- [x] Fase 1 – ingestão: KMZ/KML, coordenadas/áreas/extensões, planilhas, PDFs, docx, ficha
- [~] Fase 4 – bases oficiais: IBGE pronto (`fontes/ibge.py`); faltam ANA, Embrapa, SGB, IAT/ITCG, MapBiomas, CNUC, SICAR
- [x] Fase 6 – template Biocerne, esqueleto MCE SAA, montador, finalização via Word, painéis de conferência
- [ ] Fase 3 – mapas (PyQGIS com layout .qpt no PC com QGIS; fallback matplotlib/contextily) → mapas/*.png
- [ ] Fase 5 – imagens (fotos de campo: padronizar/EXIF GPS; Wikimedia Commons com licença)
- [ ] Fase 6b – estruturas MCE SES, PCA SES/SAA
- [ ] Fase 7 – conferência: preencher Matriz Anexo VI/VII automaticamente
- [ ] Fase 8 – skills `/montar-mce`, `/montar-pca`, `/matriz`
