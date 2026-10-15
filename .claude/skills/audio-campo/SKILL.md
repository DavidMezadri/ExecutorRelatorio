---
name: audio-campo
description: Transcreve áudios de vistoria de campo ou reunião (pasta projetos/<chave>/audios/AAAA-MM-DD/) e transforma o conteúdo em notas de campo organizadas e em texto do MCE/PCA, com a data da vistoria como fonte. Usar quando o usuário mencionar áudio, gravação, áudio de WhatsApp, ditado, vistoria gravada ou pedir para transcrever.
---

# Do áudio de campo ao relatório

## 1. Transcrever
```
python -m ferramentas.audio.transcrever <chave>            # transcreve os áudios novos (modelo small, local)
python -m ferramentas.audio.transcrever <chave> --modelo medium   # áudio ruim/barulhento: mais preciso, mais lento
```
Saída: `audios/AAAA-MM-DD/<nome>.md` (com [mm:ss]) e o consolidado `extraido/transcricoes.md`.
O usuário também pode deixar rodando `--observar` e ir soltando áudios na pasta.

## 2. Notas de campo estruturadas
Ler `extraido/transcricoes.md` e escrever/atualizar `projetos/<chave>/dados/NOTAS_CAMPO.md`, agrupando por seção
do documento (use os títulos de `texto/*.md`): unidades/localização, acessos, solo/erosão, recursos hídricos,
vegetação/APP, entorno/residências/equipamentos públicos, intervenções previstas, pendências.
Cada nota em uma linha, com a origem: `- Mata ciliar com araucárias na margem da captação (2026-10-14/vistoria_captacao [00:14])`.
- Não "melhorar" o que foi dito: números, nomes e medidas exatamente como no áudio.
- Trechos duvidosos (nome de rio/rua mal transcrito, número incerto) → `[A VERIFICAR: ...]` e perguntar ao usuário.
- Dados técnicos ditos no áudio (vazão, área, matrícula) vão ao `projeto.yaml` só se forem inequívocos,
  com comentário `# fonte: áudio 2026-10-14 [mm:ss]`.

## 3. Levar para o texto
- Substituir os `[A VERIFICAR]` correspondentes em `texto/*.md`, no estilo do modelo (técnico, impessoal):
  "Durante a vistoria de campo realizada em 14/10/2026, observou-se ..." – a data da pasta é a data da vistoria.
- Se houver fotos da mesma data (`fotos/`, ver `fotos/FOTOS.md`), relacionar a descrição do áudio às fotos e
  usá-la nas legendas.
- Informação de reunião (não de campo): "conforme informado pela equipe da Sanepar em reunião realizada em ...".
- Remontar: `python -m ferramentas.pipeline <chave> --de montar` e informar o que entrou e o que ficou pendente.
