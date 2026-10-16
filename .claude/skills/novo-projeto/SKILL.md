---
name: novo-projeto
description: Cadastra um novo empreendimento (município/sistema, qualquer UF, empresa e órgão) em projetos.yaml a partir de uma pasta de arquivos recebidos (KMZ, planilhas, PDFs) e prepara a pasta de trabalho. Usar quando o usuário trouxer arquivos de um novo projeto ou pedir para incluir/cadastrar um empreendimento.
---

# Novo projeto

1. Localizar os arquivos recebidos (pasta indicada pelo usuário). Listar KMZ/KML, planilhas, PDFs, DOCX.
2. Ler o KMZ para descobrir as pastas e as unidades:
   `python -m ferramentas.geo.kml "<arquivo.kmz>"`
3. Definir com o usuário (perguntar só o que não der para deduzir dos nomes das pastas/arquivos):
   - documento: `MCE` ou `PCA` (RAP ainda não tem estrutura)
   - sistema: `SAA` (água) ou `SES` (esgoto)
   - município (grafia oficial), **UF** e localidade, se houver
   - **empreendedor** (empresa de saneamento): se não existir `dados_comuns/empreendedores/<sigla>.yaml`, copiar
     `sanepar.yaml` como modelo e PEDIR ao usuário razão social, CNPJ, endereço, atuação, equipe envolvida e o padrão
     de nome das plantas (ou deixar `plantas` vazio)
   - **órgão licenciador**: se não existir `modelos/orgaos/<sigla>/`, PEDIR ao usuário o termo de referência do
     órgão (PDF/norma) e montar `orgao.yaml`, `estruturas/` e `matrizes/` a partir dele (iat-pr como ponto de partida)
4. Acrescentar o bloco em `projetos.yaml` (caminhos relativos à raiz), chave em minúsculas sem acento com hífens:
   ```yaml
   <chave>:
     documento: MCE
     sistema: SAA
     municipio: <Nome Oficial>
     uf: <UF>                # padrão: pelo código IBGE
     empreendedor: <sigla>   # dados_comuns/empreendedores/<sigla>.yaml (padrão sanepar)
     orgao: <sigla>          # modelos/orgaos/<sigla>/ (padrão iat-pr)
     cod_ibge:               # preenchido automaticamente
     numero_projeto: "<nº>"
     pasta_fontes: "<pasta do projeto>"
     kmz: "<arquivo.kmz>"
     kmz_pasta: "<pasta dentro do KMZ>"
   ```
   Erros de digitação nos nomes do KMZ vão em `correcoes_nomes`.
5. Rodar `python -m ferramentas.iniciar_projeto <chave>` e mostrar o INVENTARIO.md ao usuário
   (o que foi encontrado e o que falta).
6. Se a UF não tiver provedor estadual (`ferramentas/provedores/estadual/`), avisar que o texto do meio físico sai
   só com as fontes nacionais e perguntar se há fontes estaduais (atlas, cartas, órgão de recursos hídricos) a incluir.
7. Oferecer seguir com a skill `montar-documento`.
