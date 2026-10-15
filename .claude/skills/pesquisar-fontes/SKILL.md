---
name: pesquisar-fontes
description: Pesquisa em fontes oficiais (fauna, flora, espécies ameaçadas, legislação, artigos/estudos de caso, páginas de órgãos públicos) para fundamentar um trecho de MCE/PCA, registrando a referência ABNT precisa no catálogo do projeto. Usar quando for preciso embasar, citar, referenciar ou levantar informação externa para os relatórios.
---

# Pesquisar fontes oficiais

Regra: **nenhuma informação externa sem fonte registrada**. Toda referência vem das ferramentas
(`ferramentas/garimpo/`), que a montam a partir da própria fonte. Não digitar referência de memória.

## Escolher a ferramenta
| Necessidade | Comando |
|---|---|
| Fauna/flora da região, espécies ameaçadas | `python -m ferramentas.garimpo.especies entorno <chave> --raio-km 10` → `dados/ESPECIES_*.md` |
| Lista de espécies do inventário/campo | `python -m ferramentas.garimpo.especies lista --arquivo lista.txt --projeto <chave>` |
| Status de uma espécie | `python -m ferramentas.garimpo.especies especie "Nome"` |
| Lei/decreto federal | `python -m ferramentas.garimpo.legislacao buscar <norma> --projeto <chave>` (ver `catalogo`) |
| Texto literal de artigo | `python -m ferramentas.garimpo.legislacao artigo <norma> <n> [--inciso X] --projeto <chave>` |
| Norma estadual / CONAMA / portaria | `python -m ferramentas.garimpo.legislacao adicionar <chave> <url oficial> --jurisdicao ... --orgao ...` |
| Estudos de caso, artigos, teses | `python -m ferramentas.garimpo.literatura buscar "tema" --brasil --desde 2010`, depois `literatura doi <doi> --projeto <chave> --baixar` |
| Página/PDF de órgão oficial (Embrapa, IAT, IBGE, ANA, ICMBio...) | `python -m ferramentas.garimpo.pagina <url> --projeto <chave>` |

## Como usar no texto
1. Ler o conteúdo obtido (`referencias/legislacao|web|literatura/*.md`, `dados/ESPECIES_*.md`).
2. Redigir com citação no formato impresso pela ferramenta: "(BRASIL, 2012)", "(SANTOS; ZARONI, 2021)".
3. Citação literal de lei: copiar o texto de `legislacao artigo` entre aspas, com o artigo e a fonte.
4. Espécies do GBIF: tratar como **ocorrência potencial/registros secundários**; destacar as ameaçadas
   (Portaria MMA nº 148/2022 e IUCN) num quadro (`!quadro[...](dados/especies_plantas.xlsx){colunas=...}`).
5. Conferir: `python -m ferramentas.garimpo.biblio listar --projeto <chave>`; itens [CONFERIR] precisam de
   verificação manual na fonte (ou completar autor/ano com `pagina --autor --ano`).
6. A seção Referências (`!referencias`) é gerada sozinha no `montar`.
