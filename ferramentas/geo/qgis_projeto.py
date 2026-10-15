"""Monta um projeto QGIS (.qgz) com as camadas do empreendimento já organizadas e estilizadas.

Rodar com o Python do QGIS (OSGeo4W Shell ou "python-qgis.bat"), a partir da raiz do repositório:
    python-qgis.bat ferramentas\\geo\\qgis_projeto.py projetos\\candoi [--qpt modelos\\layout_mapa.qpt]

Cria projetos/<chave>/mapas/<chave>.qgz com grupos: Empreendimento, Hidrografia/APP, Temas (IBGE/SGB/ANA),
Relevo e uso (DEM, MapBiomas) e Imagem (Esri). Com --qpt, carrega o leiaute e exporta um PNG por tema
para mapas/qgis_<tema>.png (o leiaute deve ter um item de mapa com id "mapa" e uma legenda com id "legenda").

OBS: escrito para QGIS 3.28+; não testado na máquina onde foi criado (sem QGIS).
"""
import sys
from pathlib import Path

from qgis.core import (QgsApplication, QgsCategorizedSymbolRenderer, QgsCoordinateReferenceSystem, QgsFillSymbol,
                       QgsLayoutExporter, QgsLineSymbol, QgsMarkerSymbol, QgsPrintLayout, QgsProject,
                       QgsRasterLayer, QgsReadWriteContext, QgsRendererCategory, QgsVectorLayer)
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtXml import QDomDocument

TEMAS = {  # arquivo em dados/oficiais -> (campo de categoria, nome no projeto)
    "solos": ("legenda", "Pedologia (IBGE)"),
    "geologia": ("nm_unidade", "Geologia (IBGE)"),
    "geomorfologia": ("nm_unidade", "Geomorfologia (IBGE)"),
    "hidrogeologia": ("nome_unida", "Hidrogeologia (SGB)"),
    "vegetacao": ("nm_pretet", "Fitogeografia (IBGE)"),
    "uph": ("UPH_SG", "Unidades de Planejamento Hídrico (ANA)"),
}
PALETA = ["#a6cee3", "#1f78b4", "#b2df8a", "#33a02c", "#fb9a99", "#e31a1c", "#fdbf6f", "#ff7f00", "#cab2d6",
          "#6a3d9a", "#ffff99", "#b15928", "#8dd3c7", "#bebada", "#80b1d3", "#fccde5"]


def categorizar(camada, campo):
    idx = camada.fields().indexOf(campo)
    if idx < 0:
        return
    cats = []
    for i, v in enumerate(sorted(camada.uniqueValues(idx), key=str)):
        s = QgsFillSymbol.createSimple({"color": PALETA[i % len(PALETA)], "outline_color": "#555555",
                                        "outline_width": "0.1"})
        s.setOpacity(0.85)
        cats.append(QgsRendererCategory(v, s, str(v)))
    camada.setRenderer(QgsCategorizedSymbolRenderer(campo, cats))


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__); return
    d = Path(args[0]).resolve()
    qpt = Path(args[args.index("--qpt") + 1]) if "--qpt" in args else None
    QgsApplication.setPrefixPath(QgsApplication.prefixPath(), True)
    app = QgsApplication([], False)
    app.initQgis()
    proj = QgsProject.instance()
    proj.setCrs(QgsCoordinateReferenceSystem("EPSG:31982"))
    raiz = proj.layerTreeRoot()
    of = d / "dados" / "oficiais"

    g_emp = raiz.addGroup("Empreendimento")
    g_hid = raiz.addGroup("Hidrografia e APP")
    g_tem = raiz.addGroup("Temas")
    g_ras = raiz.addGroup("Relevo e uso do solo")
    g_img = raiz.addGroup("Imagem")

    def add(caminho, nome, grupo, visivel=True):
        lyr = QgsVectorLayer(str(caminho), nome, "ogr")
        if not lyr.isValid():
            print(f"  inválida: {caminho}"); return None
        proj.addMapLayer(lyr, False)
        no = grupo.addLayer(lyr)
        no.setItemVisibilityChecked(visivel)
        return lyr

    u = add(d / "dados" / "unidades.gpkg", "Unidades", g_emp)
    if u:
        idx = u.fields().indexOf("nome")
        cats = []
        for i, v in enumerate(sorted(u.uniqueValues(idx), key=str)):
            cats.append(QgsRendererCategory(v, QgsLineSymbol.createSimple({"color": PALETA[(i * 2 + 5) % len(PALETA)],
                                                                          "width": "1.2"}), str(v)))
        u.setRenderer(QgsCategorizedSymbolRenderer("nome", cats))
    app_l = add(d / "dados" / "app.gpkg", "APP (Lei 12.651/2012)", g_hid)
    if app_l:
        app_l.renderer().setSymbol(QgsFillSymbol.createSimple({"color": "65,171,93,110", "outline_color": "#00441b"}))
    for arq in sorted((d / "dados").glob("*.gpkg")):
        n = arq.stem.lower()
        if "nascente" in n:
            l = add(arq, "Nascentes", g_hid)
            if l: l.renderer().setSymbol(QgsMarkerSymbol.createSimple({"color": "#00bfff", "size": "1.2"}))
        elif "rio" in n:
            l = add(arq, "Cursos d'água", g_hid)
            if l: l.renderer().setSymbol(QgsLineSymbol.createSimple({"color": "#1f78b4", "width": "0.3"}))
    for arq in ("drenagem", "massa_dagua", "rios_ana"):
        if (of / f"{arq}.gpkg").exists():
            add(of / f"{arq}.gpkg", f"{arq} (oficial)", g_hid, visivel=False)
    for arq, (campo, nome) in TEMAS.items():
        if (of / f"{arq}.gpkg").exists():
            l = add(of / f"{arq}.gpkg", nome, g_tem, visivel=False)
            if l: categorizar(l, campo)
    for arq, nome in (("dem", "Altimetria (Copernicus DEM)"), ("mapbiomas", "Uso do solo (MapBiomas)")):
        if (of / f"{arq}.tif").exists():
            r = QgsRasterLayer(str(of / f"{arq}.tif"), nome)
            proj.addMapLayer(r, False)
            g_ras.addLayer(r).setItemVisibilityChecked(False)
    esri = QgsRasterLayer("type=xyz&url=https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/"
                          "MapServer/tile/%7Bz%7D/%7By%7D/%7Bx%7D&zmax=19&zmin=0", "Esri World Imagery", "wms")
    proj.addMapLayer(esri, False)
    g_img.addLayer(esri)

    destino = d / "mapas" / f"{d.name}.qgz"
    destino.parent.mkdir(exist_ok=True)
    proj.write(str(destino))
    print(f"Projeto QGIS: {destino}")

    if qpt and qpt.exists():
        doc = QDomDocument()
        doc.setContent(qpt.read_text(encoding="utf-8"))
        for grupo in g_tem.children():
            for outro in g_tem.children():
                outro.setItemVisibilityChecked(outro is grupo)
            layout = QgsPrintLayout(proj)
            layout.initializeDefaults()
            layout.loadFromTemplate(doc, QgsReadWriteContext())
            mapa = layout.itemById("mapa")
            if mapa and u:
                ext = u.extent(); ext.grow(max(ext.width(), ext.height()) * 0.08)
                mapa.zoomToExtent(ext)
            png = d / "mapas" / f"qgis_{grupo.name().split(' (')[0].lower()}.png"
            QgsLayoutExporter(layout).exportToImage(str(png), QgsLayoutExporter.ImageExportSettings())
            print(f"  exportado {png.name}")
    app.exitQgis()


if __name__ == "__main__":
    main()
