"""Executa todas as etapas automáticas de um projeto, em ordem.

Uso:
    python -m ferramentas.pipeline candoi [--de mapas] [--ate montar] [--sem-word] [--refazer-ficha]

Etapas: iniciar -> oficiais -> tematico -> dossie -> mapas -> kmz -> esqueleto -> montar -> finalizar -> matriz
(dossie = informações padrão da localidade: IBGE, saneamento do Censo, clima, acessos, entorno, territórios)
(kmz = saida/<chave>_google_earth.kmz para conferir no Google Earth Pro e salvar as vistas como figuras)
- iniciar não sobrescreve projeto.yaml (use --refazer-ficha para recriar)
- esqueleto não sobrescreve textos já existentes
- finalizar precisa do Word (Windows); --sem-word pula
A redação dos textos (texto/*.md) e o preenchimento do projeto.yaml são feitos entre esqueleto e montar.
"""
import argparse
import subprocess
import sys
import time

from ferramentas.util import console_utf8, projeto

ETAPAS = {
    "iniciar": ["ferramentas.iniciar_projeto"],
    "oficiais": ["ferramentas.fontes.oficiais"],
    "tematico": ["ferramentas.geo.tematico"],
    "dossie": ["ferramentas.dossie.gerar"],
    "mapas": ["ferramentas.geo.mapas"],
    "kmz": ["ferramentas.geo.google_earth", "exportar"],
    "esqueleto": ["ferramentas.docx.esqueleto"],
    "montar": ["ferramentas.docx.montar"],
    "finalizar": ["ferramentas.docx.finalizar"],
    "matriz": ["ferramentas.conferencia.matriz"],
}


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chave")
    ap.add_argument("--de", choices=list(ETAPAS), default="iniciar")
    ap.add_argument("--ate", choices=list(ETAPAS), default="matriz")
    ap.add_argument("--sem-word", action="store_true")
    ap.add_argument("--refazer-ficha", action="store_true")
    a = ap.parse_args()
    projeto(a.chave)  # valida a chave
    nomes = list(ETAPAS)
    selecionadas = nomes[nomes.index(a.de):nomes.index(a.ate) + 1]
    if a.sem_word and "finalizar" in selecionadas:
        selecionadas.remove("finalizar")
    falhas = []
    for etapa in selecionadas:
        cmd = [sys.executable, "-m", *ETAPAS[etapa], a.chave]
        if etapa == "iniciar" and a.refazer_ficha:
            cmd.append("--forcar-ficha")
        if etapa == "finalizar":
            cmd.append("--png")
        print(f"\n=== {etapa} ===", flush=True)
        t0 = time.time()
        r = subprocess.run(cmd)
        print(f"--- {etapa}: {'ok' if r.returncode == 0 else 'FALHOU'} ({time.time() - t0:.0f}s)", flush=True)
        if r.returncode != 0:
            falhas.append(etapa)
            if etapa in ("iniciar", "montar"):
                break  # etapas seguintes dependem destas
    print("\nResumo:", "tudo ok" if not falhas else f"falhas em {', '.join(falhas)}")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
