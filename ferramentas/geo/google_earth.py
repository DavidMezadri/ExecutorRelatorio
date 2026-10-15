"""Integração com o Google Earth Pro: exportar o projeto para KMZ e importar pontos marcados pela equipe.

Uso:
    python -m ferramentas.geo.google_earth exportar candoi
        -> saida/<chave>_google_earth.kmz com pastas:
           Unidades (balão com área/extensão/UTM), Vistas para figuras (enquadramentos prontos),
           APP, Travessias de cursos d'água, Nascentes até 100 m, Fotos de campo (foto no balão),
           Limite municipal.
        Para criar figuras: duplo clique na vista -> Arquivo > Salvar > Salvar imagem
        -> gravar em projetos/<chave>/imagens/ge_<nome>.jpg (nomes sugeridos em saida/GE_VISTAS.md).

    python -m ferramentas.geo.google_earth importar candoi ARQUIVO.kmz [--pasta "Nome da pasta"]
    python -m ferramentas.geo.google_earth importar candoi --meus-lugares [--pasta "Candói"]
        -> dados/pontos_ge.gpkg + dados/pontos_ge.xlsx (coordenadas geográficas/UTM de cada ponto,
           linha ou polígono marcado no Google Earth). Usar no texto com
           !quadro[...](dados/pontos_ge.xlsx){colunas="unidade:Ponto,utm_e:E (m),utm_n:N (m)"}
        --meus-lugares lê o "Meus lugares" do Google Earth Pro (myplaces.kml do usuário).
"""
import argparse
import html
import os
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd

from ferramentas.util import console_utf8, corrigir_nome, projeto, slug
from ferramentas.geo import coordenadas, kml
from ferramentas.geo.tematico import faixas_app, hidrografia, unidades

MEUS_LUGARES = Path(os.environ.get("USERPROFILE", "~")) / "AppData" / "LocalLow" / "Google" / "GoogleEarth" / "myplaces.kml"
CORES = ["ff1c1ae3", "ff007fff", "ff9a3d6a", "ffb4781f", "ff2859b1", "ff2ca033", "ff999afb", "ffd6b2ca"]  # aabbggrr


def _esc(s):
    return html.escape(str(s), quote=True)


def _coords(geom):
    return " ".join(f"{x:.7f},{y:.7f},0" for x, y in geom.coords)


def _geom_kml(g):
    t = g.geom_type
    if t == "Point":
        return f"<Point><coordinates>{g.x:.7f},{g.y:.7f},0</coordinates></Point>"
    if t == "LineString":
        return f"<LineString><tessellate>1</tessellate><coordinates>{_coords(g)}</coordinates></LineString>"
    if t == "Polygon":
        inn = "".join(f"<innerBoundaryIs><LinearRing><coordinates>{_coords(r)}</coordinates></LinearRing></innerBoundaryIs>"
                      for r in g.interiors)
        return (f"<Polygon><tessellate>1</tessellate><outerBoundaryIs><LinearRing><coordinates>{_coords(g.exterior)}"
                f"</coordinates></LinearRing></outerBoundaryIs>{inn}</Polygon>")
    if t.startswith("Multi") or t == "GeometryCollection":
        return "<MultiGeometry>" + "".join(_geom_kml(p) for p in g.geoms) + "</MultiGeometry>"
    return ""


def _placemark(nome, geom, estilo, descricao="", visivel=True):
    return (f"<Placemark><name>{_esc(nome)}</name><visibility>{int(visivel)}</visibility>"
            f"<styleUrl>#{estilo}</styleUrl>"
            + (f"<description><![CDATA[{descricao}]]></description>" if descricao else "")
            + _geom_kml(geom) + "</Placemark>")


def _lookat(geom_wgs, geom_utm, inclinacao=0):
    """Enquadramento (LookAt) que mostra a geometria inteira com folga."""
    c = geom_wgs.centroid
    x0, y0, x1, y1 = geom_utm.bounds
    lado = max(x1 - x0, y1 - y0, 150)
    alcance = lado * 1.9
    return (f"<LookAt><longitude>{c.x:.7f}</longitude><latitude>{c.y:.7f}</latitude><altitude>0</altitude>"
            f"<heading>0</heading><tilt>{inclinacao}</tilt><range>{alcance:.0f}</range>"
            f"<altitudeMode>relativeToGround</altitudeMode></LookAt>")


def _pasta(nome, conteudo, aberta=False, visivel=True):
    return (f"<Folder><name>{_esc(nome)}</name><open>{int(aberta)}</open><visibility>{int(visivel)}</visibility>"
            + "".join(conteudo) + "</Folder>")


def exportar(cfg) -> Path:
    d = cfg["dir"]
    u_utm, epsg = unidades(cfg)
    u = u_utm.to_crs("EPSG:4326")
    quadro = pd.read_excel(d / "dados" / "coordenadas.xlsx") if (d / "dados" / "coordenadas.xlsx").exists() else None

    estilos = []
    for i, cor in enumerate(CORES):
        estilos.append(f'<Style id="u{i}"><LineStyle><color>{cor}</color><width>4</width></LineStyle>'
                       f'<PolyStyle><color>99{cor[2:]}</color></PolyStyle>'
                       f'<IconStyle><color>{cor}</color><Icon><href>http://maps.google.com/mapfiles/kml/shapes/placemark_square.png</href></Icon></IconStyle></Style>')
    estilos += [
        '<Style id="app"><LineStyle><color>ff1b4400</color><width>1</width></LineStyle><PolyStyle><color>6641ab5d</color></PolyStyle></Style>',
        '<Style id="travessia"><IconStyle><color>ffff7f00</color><scale>1.0</scale><Icon><href>http://maps.google.com/mapfiles/kml/shapes/water.png</href></Icon></IconStyle></Style>',
        '<Style id="nascente"><IconStyle><color>ffffbf00</color><scale>0.6</scale><Icon><href>http://maps.google.com/mapfiles/kml/shapes/shaded_dot.png</href></Icon></IconStyle><LabelStyle><scale>0</scale></LabelStyle></Style>',
        '<Style id="foto"><IconStyle><scale>0.9</scale><Icon><href>http://maps.google.com/mapfiles/kml/shapes/camera.png</href></Icon></IconStyle></Style>',
        '<Style id="vista"><IconStyle><scale>0.8</scale><Icon><href>http://maps.google.com/mapfiles/kml/shapes/eye.png</href></Icon></IconStyle></Style>',
        '<Style id="limite"><LineStyle><color>ff000000</color><width>2</width></LineStyle><PolyStyle><fill>0</fill></PolyStyle></Style>',
    ]

    # Unidades
    pm_unid, pm_vistas, vistas_md = [], [], []
    for i, ((_, ru), (_, rw)) in enumerate(zip(u_utm.iterrows(), u.iterrows())):
        linhas = quadro[quadro["unidade"] == ru["nome"]] if quadro is not None else pd.DataFrame()
        info = [f"<b>{_esc(ru['nome'])}</b>"]
        if len(linhas):
            r0 = linhas.iloc[0]
            if pd.notna(r0.get("area_m2")):
                info.append(f"Área: {r0['area_m2']:,.0f} m² ({r0['area_ha']:.4f} ha)".replace(",", "."))
            if pd.notna(r0.get("extensao_m")):
                info.append(f"Extensão: {r0['extensao_m']:,.0f} m".replace(",", "."))
            for _, r in linhas.iterrows():
                info.append(f"{r['referencia'] or 'ponto'}: E {r['utm_e']:.0f} / N {r['utm_n']:.0f} ({r['fuso']}) – "
                            f"{r['latitude_gms']}, {r['longitude_gms']}")
        pm_unid.append(_placemark(ru["nome"], rw.geometry, f"u{i % len(CORES)}", "<br>".join(info)))
        arq = f"ge_{slug(ru['nome'].split(' - ', 1)[-1]).replace('-', '_')}.jpg"
        vistas_md.append(f"| {ru['nome']} | imagens/{arq} |")
        pm_vistas.append(f"<Placemark><name>Vista – {_esc(ru['nome'])}</name><styleUrl>#vista</styleUrl>"
                         f"<description><![CDATA[Duplo clique para enquadrar. Salvar imagem como <b>{arq}</b> em "
                         f"projetos/{cfg['chave']}/imagens/]]></description>{_lookat(rw.geometry, ru.geometry)}"
                         f"<Point><coordinates>{rw.geometry.centroid.x:.7f},{rw.geometry.centroid.y:.7f},0</coordinates></Point></Placemark>")
    todas_w = u.geometry.union_all()
    todas_u = u_utm.geometry.union_all()
    pm_vistas.insert(0, f"<Placemark><name>Vista – sistema completo</name><styleUrl>#vista</styleUrl>"
                        f"{_lookat(todas_w, todas_u)}<Point><coordinates>{todas_w.centroid.x:.7f},"
                        f"{todas_w.centroid.y:.7f},0</coordinates></Point></Placemark>")
    vistas_md.insert(0, "| Sistema completo | imagens/ge_sistema.jpg |")

    pastas = [_pasta("Unidades do empreendimento", pm_unid, aberta=True),
              _pasta("Vistas para figuras (duplo clique)", pm_vistas, aberta=True)]

    # APP, travessias, nascentes
    rios, nasc, _ = hidrografia(cfg, epsg)
    entorno = u_utm.geometry.buffer(1000).union_all()
    rios_e = rios[rios.intersects(entorno)]
    nasc_e = nasc[nasc.intersects(entorno)] if len(nasc) else nasc
    app = faixas_app(rios_e, nasc_e)
    if len(app):
        app_w = gpd.GeoSeries([app.geometry.union_all().intersection(entorno)], crs=epsg).to_crs("EPSG:4326").iloc[0]
        pastas.append(_pasta("APP (Lei 12.651/2012) – entorno de 1 km", [_placemark("APP", app_w, "app")], visivel=True))
    if len(rios_e):
        cruz = []
        uni_rios = rios_e.geometry.union_all()
        for _, ru in u_utm.iterrows():
            if not ru.geometry.geom_type.endswith("LineString"):
                continue
            inter = ru.geometry.intersection(uni_rios)
            pts = [] if inter.is_empty else (list(inter.geoms) if hasattr(inter, "geoms") else [inter])
            for k, p in enumerate(pts, start=1):
                c = p.centroid
                pw = gpd.GeoSeries([c], crs=epsg).to_crs("EPSG:4326").iloc[0]
                cruz.append(_placemark(f"Travessia {k} – {ru['nome']}", pw, "travessia",
                                       f"E {c.x:.0f} / N {c.y:.0f}"))
        if cruz:
            pastas.append(_pasta("Travessias de cursos d'água", cruz))
    if len(nasc_e):
        perto = nasc_e[nasc_e.distance(todas_u) <= 100].to_crs("EPSG:4326")
        pastas.append(_pasta("Nascentes até 100 m das unidades",
                             [_placemark(f"Nascente {k}", g, "nascente") for k, g in enumerate(perto.geometry, 1)]))

    # Fotos (com a imagem embutida no KMZ)
    arquivos_kmz = {}
    fotos_gpkg = d / "fotos" / "fotos.gpkg"
    if fotos_gpkg.exists():
        f = gpd.read_file(fotos_gpkg).to_crs("EPSG:4326")
        pm = []
        for _, r in f.iterrows():
            arquivos_kmz[f"files/{r['arquivo']}"] = d / "fotos" / r["arquivo"]
            desc = f'<img src="files/{r["arquivo"]}" width="480"/><br>{_esc(r.get("data", ""))} – {_esc(r.get("unidade", ""))}'
            pm.append(_placemark(r["arquivo"], r.geometry, "foto", desc))
        pastas.append(_pasta("Fotos de campo", pm))

    mun = d / "dados" / "oficiais" / "municipio.gpkg"
    if mun.exists():
        g = gpd.read_file(mun).to_crs("EPSG:4326").geometry.iloc[0]
        pastas.append(_pasta("Limite municipal (IBGE)", [_placemark(cfg["municipio"], g, "limite")], visivel=False))

    doc = ('<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
           f"<name>{_esc(cfg['documento'])} {_esc(cfg['sistema'])} – {_esc(cfg['municipio'])}</name><open>1</open>"
           + "".join(estilos) + "".join(pastas) + "</Document></kml>")
    saida = d / "saida" / f"{cfg['chave']}_google_earth.kmz"
    saida.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", doc)
        for nome, caminho in arquivos_kmz.items():
            z.write(caminho, nome)
    (d / "saida" / "GE_VISTAS.md").write_text(
        "# Vistas do Google Earth para figuras\n\nNo Google Earth Pro: duplo clique na vista → Arquivo > Salvar > "
        "Salvar imagem (resolução máxima) → gravar com o nome abaixo. Usar no texto com\n"
        "`![Legenda](imagens/ge_x.jpg){fonte=\"Google Earth Pro, adaptado pelo autor, ANO.\"}`\n\n"
        "| Vista | Arquivo |\n|---|---|\n" + "\n".join(vistas_md) + "\n", encoding="utf-8")
    return saida


def importar(cfg, arquivo: Path, pasta=None) -> Path:
    g = kml.ler(arquivo, pasta)
    if g.empty:
        raise SystemExit(f"Nenhuma feição em {arquivo}" + (f" (pasta '{pasta}')" if pasta else ""))
    g["nome"] = g["nome"].fillna("(sem nome)").map(corrigir_nome)
    d = cfg["dir"] / "dados"
    d.mkdir(exist_ok=True)
    g.to_file(d / "pontos_ge.gpkg", driver="GPKG")
    q = coordenadas.quadro(g)
    q.insert(1, "pasta", [g.loc[g["nome"] == n, "pasta"].iloc[0] for n in q["unidade"]])
    q.to_excel(d / "pontos_ge.xlsx", index=False)
    print(f"{len(g)} feições importadas -> {d / 'pontos_ge.gpkg'}, {d / 'pontos_ge.xlsx'}")
    print(q[["unidade", "pasta", "referencia", "utm_e", "utm_n", "fuso"]].to_string(index=False))
    return d / "pontos_ge.xlsx"


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="acao", required=True)
    e = sub.add_parser("exportar")
    e.add_argument("chave")
    i = sub.add_parser("importar")
    i.add_argument("chave")
    i.add_argument("arquivo", nargs="?")
    i.add_argument("--meus-lugares", action="store_true")
    i.add_argument("--pasta")
    a = ap.parse_args()
    cfg = projeto(a.chave)
    if a.acao == "exportar":
        s = exportar(cfg)
        print(f"KMZ: {s}\nVistas: {s.parent / 'GE_VISTAS.md'}")
    else:
        arq = MEUS_LUGARES if a.meus_lugares else Path(a.arquivo or "")
        if not arq.is_file():
            raise SystemExit(f"Arquivo não encontrado: {arq}")
        importar(cfg, arq, a.pasta)


if __name__ == "__main__":
    main()
