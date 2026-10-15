---
name: montar-documento
description: Monta um MCE ou PCA (IN IAT 37/2025) de um empreendimento Sanepar já cadastrado em projetos.yaml, do zero até o .docx revisado, com mapas, textos redigidos e matriz de atendimento. Usar quando o usuário pedir para montar, gerar, redigir ou atualizar o documento/memorial/PCA de um município (ex.: "monte o MCE de Candói").
---

# Montar documento (MCE/PCA)

Argumento: chave do projeto em `projetos.yaml` (ex.: `candoi`). Se o usuário citar o município, descubra a chave.
Se o empreendimento não estiver cadastrado, use a skill `novo-projeto` antes.

## 1. Etapas automáticas
```
python -m ferramentas.pipeline <chave> --ate esqueleto
```
Gera: `dados/` (coordenadas, unidades, bases oficiais, RESUMO_TEMATICO.md, **DOSSIE.md** da localidade), `mapas/*.png` + `MAPAS.md`,
`extraido/*.md` (planilhas e PDFs do cliente) e `texto/*.md` (só cria os que não existem).

## 2. Preencher a ficha `projetos/<chave>/projeto.yaml`
Primeiro: `python -m ferramentas.ingestao.memorial <chave> --aplicar` (candidatos com página em
`dados/EXTRACAO_MEMORIAL.md`) e, se houver `cad/`, `python -m ferramentas.ingestao.cad <chave>` (extensões por DN).
Ler TUDO em `extraido/` (memoriais, planilha "Lista de documentos e informações", matriz) e preencher os campos
`null` com valores que tenham fonte. Nunca inventar: sem fonte, manter `null`. Registrar a origem de cada
valor num comentário YAML (`# fonte: memorial descritivo p. 12`).

## 3. Redigir `texto/*.md`
- Ler `referencias/modelo_mce_saa_palmeira.md` para imitar o estilo (técnico, impessoal, frases completas).
- `dados/DOSSIE.md`: socioeconomia, saneamento do Censo 2022, clima, acessos, entorno por unidade (escolas, igrejas,
  saúde), terras indígenas – usar com a citação indicada em "Citar como"; itens de "Consultas manuais" ficam como
  pendência para o usuário.
- Substituir cada `[A VERIFICAR: ...]` por texto com fonte, usando: `dados/RESUMO_TEMATICO.md` (solos, geologia,
  geomorfologia, vegetação, uso do solo, declividade, altitude, APP, travessias por unidade), `dados/oficiais/FONTES.yaml`
  (citações ABNT → acrescentar em Referências), `extraido/*.md` e o `projeto.yaml`.
- Descrever classes de solo, geologia etc. a partir do resumo + conhecimento técnico consolidado (EMBRAPA/SiBCS,
  MINEROPAR, SGB), sempre citando a fonte. Manter `[A VERIFICAR]` no que depender de dado do cliente/campo.
- Fotos: se houver `fotos/brutas/`, rodar `python -m ferramentas.imagens.fotos <chave>`, ver as folhas
  `fotos/contato_*.png` (Read) e escrever legendas reais nas diretivas de `fotos/FOTOS.md` antes de usá-las.
- Usar as fontes de `mapas/MAPAS.md` no `fonte=` de cada figura de mapa.
- Google Earth: `saida/<chave>_google_earth.kmz` traz vistas prontas; se existirem `imagens/ge_*.jpg`
  (salvas pela equipe, ver `saida/GE_VISTAS.md`), usá-las nas figuras de localização de cada unidade com
  `fonte="Google Earth Pro, adaptado pelo autor, ANO."`. Pontos marcados pela equipe no GE entram com
  `google_earth importar` e viram `dados/pontos_ge.xlsx` (travessias, acessos etc. com UTM).
- Sintaxe dos textos: ver CLAUDE.md.
- Embasamento externo (fauna/flora, leis, estudos de caso, páginas de órgãos): usar a skill `pesquisar-fontes`.
  Rodar ao menos `python -m ferramentas.garimpo.especies entorno <chave>` para o meio biótico. Toda citação
  precisa estar no catálogo do projeto; a seção Referências (`!referencias`) é automática.

## 4. Montar, finalizar e conferir
```
python -m ferramentas.pipeline <chave> --de montar
python -m ferramentas.docx.painel projetos/<chave>/saida/<arquivo>.pdf
```
Abrir TODOS os painéis (`*_painel_NN.png`) com Read e corrigir problemas visuais (figura cortada, tabela quebrada,
legenda errada, página vazia). Repetir montar/finalizar até ficar limpo.

## 5. Entregar
Informar ao usuário: caminho do .docx, nº de páginas/figuras/quadros, resumo da matriz
(`saida/Matriz_*.xlsx`) e as pendências restantes de `saida/PENDENCIAS.md` agrupadas pelo que depende dele
(dados da Sanepar, campo, CAR, ART...).
