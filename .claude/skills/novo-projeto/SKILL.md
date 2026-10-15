---
name: novo-projeto
description: Cadastra um novo empreendimento (município/sistema) em projetos.yaml a partir de uma pasta de arquivos recebidos (KMZ, planilhas, PDFs) e prepara a pasta de trabalho. Usar quando o usuário trouxer arquivos de um novo projeto ou pedir para incluir/cadastrar um empreendimento.
---

# Novo projeto

1. Localizar os arquivos recebidos (pasta indicada pelo usuário). Listar KMZ/KML, planilhas, PDFs, DOCX.
2. Ler o KMZ para descobrir as pastas e as unidades:
   `python -m ferramentas.geo.kml "<arquivo.kmz>"`
3. Definir com o usuário (perguntar só o que não der para deduzir dos nomes das pastas/arquivos):
   - documento: `MCE` ou `PCA` (RAP ainda não tem estrutura)
   - sistema: `SAA` (água) ou `SES` (esgoto)
   - município (grafia oficial) e localidade, se houver
4. Acrescentar o bloco em `projetos.yaml` (caminhos relativos à raiz), chave em minúsculas sem acento com hífens:
   ```yaml
   <chave>:
     documento: MCE
     sistema: SAA
     municipio: <Nome Oficial>
     cod_ibge:            # preenchido automaticamente
     projeto_sanepar: "<nº>"
     pasta_fontes: "<pasta do projeto>"
     kmz: "<arquivo.kmz>"
     kmz_pasta: "<pasta dentro do KMZ>"
   ```
   Erros de digitação nos nomes do KMZ vão em `correcoes_nomes`.
5. Rodar `python -m ferramentas.iniciar_projeto <chave>` e mostrar o INVENTARIO.md ao usuário
   (o que foi encontrado e o que falta).
6. Oferecer seguir com a skill `montar-documento`.
