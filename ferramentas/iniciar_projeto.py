"""Prepara a pasta de trabalho de um empreendimento a partir das fontes recebidas.

Uso:
    python -m ferramentas.iniciar_projeto candoi [--sem-pdf] [--forcar-ficha]

Gera em projetos/<chave>/:
    dados/unidades.gpkg          unidades do KMZ (WGS84)
    dados/coordenadas.xlsx|.md   quadro de coordenadas geográficas/UTM, áreas e extensões
    dados/<camada>.gpkg          demais KML/KMZ (hidrografia, nascentes...)
    extraido/*.md                texto das planilhas e PDFs (para a IA ler)
    projeto.yaml                 ficha do empreendimento (só cria se não existir)
    INVENTARIO.md                o que foi encontrado e o que falta
"""
import argparse
from pathlib import Path

import pandas as pd
import requests
import yaml

from ferramentas.util import console_utf8, corrigir_nome, projeto, salvar_yaml, slug, RAIZ
from ferramentas.geo import kml, coordenadas
from ferramentas.fontes import ibge
from ferramentas.ingestao import pdf as pdf_ext, planilhas


def _tabela_md(df, colunas) -> str:
    d = df[colunas].fillna("")
    out = ["| " + " | ".join(colunas) + " |", "|" + "---|" * len(colunas)]
    out += ["| " + " | ".join(str(v) for v in r) + " |" for r in d.itertuples(index=False)]
    return "\n".join(out)


def ficha_inicial(cfg: dict, quadro, info_mun: dict) -> dict:
    unidades = []
    if not quadro.empty:
        for nome, g in quadro.groupby("unidade", sort=False):
            r = g.iloc[0]
            u = {"nome": nome, "descricao": None, "geometria": r["geometria"]}
            if pd.notna(r["area_m2"]):
                u["area_m2"] = float(r["area_m2"])
            if pd.notna(r["extensao_m"]):
                u["extensao_m"] = float(r["extensao_m"])
            unidades.append(u)

    ficha = {
        "documento": cfg["documento"],
        "sistema": cfg["sistema"],
        "projeto_sanepar": cfg.get("projeto_sanepar"),
        "municipio": cfg["municipio"],
        "localidade": cfg.get("localidade"),
        "uf": "PR",
        "cod_ibge": cfg.get("cod_ibge"),
        "municipio_info": info_mun or None,
        # dados institucionais da Sanepar e da Biocerne vêm de dados_comuns/*.yaml ({{sanepar.cnpj}}, {{biocerne.cnpj}})
        "empreendedor": {"responsavel": None, "telefone": None, "email": None},
        "cnae": "3600-6/01 (Captação, tratamento e distribuição de água)" if cfg["sistema"] == "SAA"
                else "3701-1/00 (Gestão de redes de esgoto)",
        "area_influencia": None,
        "acessos": None,
        "endereco_unidade_principal": None,
        "area": {"total_m2": None, "construida_m2": None, "livre_m2": None},
        "unidades": unidades,
        "imoveis_terceiros": None,
        "populacao": {"inicio_plano_ano": None, "inicio_plano_hab": None,
                      "final_plano_ano": None, "final_plano_hab": None, "demanda_m3_dia": None},
    }
    if cfg["sistema"] == "SAA":
        ficha["manancial"] = {"nome": None, "tipo": None, "bacia": None, "classe": None,
                              "outorga_captacao": None}
        ficha["eta"] = {"capacidade_nominal_ls": None, "capacidade_maxima_ls": None,
                        "regime_operacao_h_dia": None, "processo": None}
        ficha["outorga_lancamento"] = None
    else:
        ficha["ete"] = {"vazao_media_ls": None, "vazao_maxima_ls": None, "processo": None,
                        "eficiencia_dbo_pct": None}
        ficha["corpo_receptor"] = {"nome": None, "bacia": None, "classe": None,
                                   "outorga_lancamento": None}
    ficha["responsavel_tecnico"] = {"empresa": None, "nome": None, "registro": None, "art": None}
    return ficha


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chave")
    ap.add_argument("--sem-pdf", action="store_true", help="pula extração de PDFs")
    ap.add_argument("--forcar-ficha", action="store_true", help="recria projeto.yaml (sobrescreve!)")
    a = ap.parse_args()

    cfg = projeto(a.chave)
    d = cfg["dir"]
    for sub in ("dados", "extraido", "mapas", "fotos", "imagens", "saida"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    inv = [f"# Inventário – {cfg['documento']} {cfg['sistema']} {cfg['municipio']}\n"]

    try:
        info_mun = ibge.info(cfg["municipio"])
    except requests.RequestException as e:
        info_mun = {}
        inv.append(f"- IBGE indisponível ({e.__class__.__name__}); rode de novo com internet")
    cfg["cod_ibge"] = cfg.get("cod_ibge") or info_mun.get("cod_ibge")
    inv.append(f"- Código IBGE: {cfg['cod_ibge'] or 'NÃO ENCONTRADO'}")
    if info_mun.get("populacao_2022"):
        inv.append(f"- IBGE: {info_mun['populacao_2022']} hab. (2022), {info_mun.get('area_km2')} km², "
                   f"limítrofes: {', '.join(info_mun.get('limitrofes', []))}")

    # 1. Unidades do KMZ
    gdf = kml.ler(cfg["kmz"], cfg["kmz_pasta"]) if cfg.get("kmz") else None
    if gdf is not None and not gdf.empty:
        gdf["nome"] = gdf["nome"].map(corrigir_nome)
        gdf.to_file(d / "dados" / "unidades.gpkg", driver="GPKG")
        quadro = coordenadas.quadro(gdf)
        quadro.to_excel(d / "dados" / "coordenadas.xlsx", index=False)
        cols = ["unidade", "referencia", "latitude_gms", "longitude_gms", "utm_e", "utm_n",
                "fuso", "area_m2", "extensao_m"]
        (d / "dados" / "coordenadas.md").write_text(
            f"# Coordenadas – SIRGAS 2000 / UTM {quadro.attrs['epsg_utm']}\n\n" + _tabela_md(quadro, cols) + "\n",
            encoding="utf-8")
        inv.append(f"- KMZ: {len(gdf)} unidades em '{cfg['kmz_pasta']}' -> dados/unidades.gpkg, dados/coordenadas.xlsx")
        # camadas auxiliares do mesmo KMZ ligadas ao município (ex.: pr_4104428_nascentes)
        if cfg["cod_ibge"]:
            tudo = kml.ler(cfg["kmz"])
            for pasta, g in tudo[tudo["pasta"].str.contains(str(cfg["cod_ibge"]))].groupby("pasta"):
                g.to_file(d / "dados" / f"{slug(pasta)}.gpkg", driver="GPKG")
                inv.append(f"- KMZ camada auxiliar '{pasta}': {len(g)} feições")
    else:
        quadro = pd.DataFrame()
        inv.append("- KMZ: NENHUMA unidade encontrada (verificar kmz/kmz_pasta em projetos.yaml)")

    fontes = cfg["pasta_fontes"]
    # 2. KML/KMZ da pasta do projeto
    for k in sorted(list(fontes.rglob("*.kml")) + list(fontes.rglob("*.kmz"))):
        g = kml.ler(k)
        g.to_file(d / "dados" / f"{slug(k.stem)}.gpkg", driver="GPKG")
        inv.append(f"- {k.name}: {len(g)} feições {g.geometry.geom_type.value_counts().to_dict()}")

    # 3. Planilhas
    for x in sorted(fontes.rglob("*.xlsx")):
        if x.name.startswith("~$"):
            continue
        md = planilhas.extrair(x, d / "extraido")
        inv.append(f"- Planilha {x.name} -> extraido/{md.name}")

    # 4. PDFs
    pdfs = sorted(fontes.rglob("*.pdf"))
    if not pdfs:
        inv.append("- PDFs de projeto: NENHUM na pasta de fontes")
    for p in pdfs if not a.sem_pdf else []:
        r = pdf_ext.extrair(p, d / "extraido", tabelas=True)
        aviso = f" (sem texto nas págs {r['escaneadas']} – OCR)" if r["escaneadas"] else ""
        inv.append(f"- PDF {p.name}: {r['paginas']} págs -> extraido/{Path(r['md']).name}{aviso}")

    # 5. Outros arquivos não tratados
    tratados = {".kml", ".kmz", ".xlsx", ".pdf"}
    outros = [f for f in fontes.rglob("*") if f.is_file() and f.suffix.lower() not in tratados]
    for f in outros:
        inv.append(f"- NÃO TRATADO: {f.relative_to(fontes)}")

    # 6. Ficha
    ficha_path = d / "projeto.yaml"
    if a.forcar_ficha or not ficha_path.exists():
        salvar_yaml(ficha_inicial(cfg, quadro, info_mun), ficha_path)
        inv.append("- projeto.yaml criado (campos nulos = a preencher)")
    else:
        inv.append("- projeto.yaml já existia (mantido)")

    (d / "INVENTARIO.md").write_text("\n".join(inv) + "\n", encoding="utf-8")
    print("\n".join(inv))
    print(f"\nPasta: {d}")


if __name__ == "__main__":
    main()
