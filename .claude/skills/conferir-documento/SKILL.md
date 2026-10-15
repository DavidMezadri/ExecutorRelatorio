---
name: conferir-documento
description: Confere um MCE/PCA já montado contra o Termo de Referência da IN 37/2025 (matriz de atendimento), revisa visualmente as páginas e lista o que falta. Usar quando o usuário pedir para revisar, conferir, checar a matriz ou ver pendências de um documento.
---

# Conferir documento

1. `python -m ferramentas.conferencia.matriz <chave>` → `saida/Matriz_<Anexo>_<municipio>.xlsx`.
2. Se o .docx for mais antigo que os textos, remontar: `python -m ferramentas.pipeline <chave> --de montar`.
3. Gerar painéis do PDF (`python -m ferramentas.docx.painel <pdf>`) e ler todos com Read, procurando:
   figuras faltando (texto amarelo "imagem não encontrada"), tabelas quebradas, legendas sem numeração,
   páginas em branco indevidas, títulos órfãos no fim da página.
4. Ler `saida/PENDENCIAS.md`.
5. Responder com: resumo da matriz (atendidos/parciais/não atendidos), itens NÃO ATENDIDOS com a exigência,
   problemas visuais encontrados e pendências agrupadas por responsável (Sanepar, campo, Biocerne).
   Não alterar textos nesta skill, a menos que o usuário peça.
