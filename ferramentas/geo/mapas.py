"""Gera os mapas temáticos do documento (PNG) com leiaute cartográfico padrão.

Uso:
    python -m ferramentas.geo.mapas candoi [--so solos,uso_solo] [--dpi 200]

Requer: iniciar_projeto (unidades) + fontes.oficiais (bases). Grava em projetos/<chave>/dados/mapas_conferencia/
(SÓ PARA CONFERÊNCIA/rascunho: os mapas do documento são os do Felipe, em mapas/ – ver geo.mapas_felipe):
    localizacao_unidades, localizacao_regional, solos, uso_solo, geomorfologia, altimetria, declividade,
    bacia, geologia, hidrogeologia, fitogeografia, app_rl  (.png) + MAPAS.md (fontes de cada mapa)

Leiaute: mapa com grade UTM, norte, escala gráfica; painel lateral com título, legenda, localização
no estado, sistema de referência e fontes. No PC com QGIS, ver ferramentas/geo/qgis_projeto.py.
"""
import argparse
import datetime as dt
import math
import textwrap
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import BoundaryNorm, ListedColormap, LightSource
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from matplotlib.ticker import FuncFormatter
from shapely.geometry import box

from ferramentas.util import console_utf8, projeto
from ferramentas.geo import raster
from ferramentas.geo.legendas import DECLIVIDADE, MAPBIOMAS
from ferramentas.geo.tematico import faixas_app, hidrografia, unidades

warnings.filterwarnings("ignore", category=UserWarning)
ANO = dt.date.today().year
CM = 1 / 2.54
COR_UNIDADE = ["#e31a1c", "#ff7f00", "#6a3d9a", "#1f78b4", "#b15928", "#33a02c", "#fb9a99", "#cab2d6", "#000000"]
CORES_SOLO = {"L": "#c2523c", "LB": "#a0522d", "LV": "#b22222", "C": "#e5c07b", "R": "#f2e6c9", "N": "#7f2704",
              "P": "#f28e2b", "G": "#8fa8c8", "O": "#3b3b3b", "M": "#6b8e23", "E": "#fff5cc", "F": "#d95f02",
              "S": "#bcbddc", "T": "#984ea3", "V": "#66a61e"}
def _calibri_ok():
    """Calibri regular E negrito com todos os caracteres usados. Num PC o Calibri resolveu para um arquivo sem os
    glifos e os mapas saíram sem legenda/coordenadas (só o título em negrito aparecia) – então testa os glifos."""
    try:
        from matplotlib import font_manager
        from matplotlib.ft2font import FT2Font
        for peso in ("normal", "bold"):
            arq = font_manager.findfont(font_manager.FontProperties(family="Calibri", weight=peso),
                                        fallback_to_default=False)
            f = FT2Font(arq)
            if any(f.get_char_index(ord(c)) == 0 for c in "abcxyzABCÁÇÃõé0123456789.,–"):
                return False
        return True
    except Exception:
        return False


plt.rcParams.update({"font.family": "Calibri" if _calibri_ok() else "DejaVu Sans", "font.size": 7})


# ------------------------------------------------------------------ leiaute
class Mapa:
    def __init__(self, ctx, titulo, paisagem=False):
        self.ctx = ctx
        w, h = (25.0, 15.0) if paisagem else (16.5, 13.0)
        self.fig = plt.figure(figsize=(w * CM, h * CM), dpi=ctx["dpi"])
        lado = 5.2 / w
        self.ax = self.fig.add_axes([0.06, 0.07, 1 - lado - 0.08, 0.90])
        self.painel = self.fig.add_axes([1 - lado - 0.005, 0.02, lado, 0.96])
        self.painel.set_xticks([]); self.painel.set_yticks([])
        for s in self.painel.spines.values():
            s.set_linewidth(0.8)
        self.titulo = titulo
        self.handles = []
        self.fontes = []
        self._enquadrar()

    def _enquadrar(self):
        x0, y0, x1, y1 = self.ctx["extent"]
        bw = self.ax.get_position().width * self.fig.get_figwidth()
        bh = self.ax.get_position().height * self.fig.get_figheight()
        cx, cy, dx, dy = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0
        if dx / dy > bw / bh:
            dy = dx * bh / bw
        else:
            dx = dy * bw / bh
        self.ax.set_xlim(cx - dx / 2, cx + dx / 2)
        self.ax.set_ylim(cy - dy / 2, cy + dy / 2)
        self.ax.set_aspect("equal")
        fmt = FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", "."))
        self.ax.xaxis.set_major_formatter(fmt)
        self.ax.yaxis.set_major_formatter(fmt)
        self.ax.tick_params(labelsize=5.5, length=2)
        plt.setp(self.ax.get_yticklabels(), rotation=90, va="center")
        self.ax.grid(color="#999", lw=0.25, ls="--", alpha=0.6)
        self.ax.set_axisbelow(False)
        self.ax.set_xlabel("")
        self.ax.set_ylabel("")

    def janela(self):
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        return box(x0, y0, x1, y1)

    # --- camadas
    def satelite(self):
        import contextily as cx
        try:
            cx.add_basemap(self.ax, crs=self.ctx["epsg"], source=cx.providers.Esri.WorldImagery, attribution=False)
            self.fontes.append("Imagem: Esri World Imagery")
        except Exception as e:
            print(f"    (sem imagem de satélite: {e.__class__.__name__})")
        self._enquadrar()

    def unidades(self, rotulos=True, contorno="white"):
        u = self.ctx["unidades"]
        for i, (_, row) in enumerate(u.iterrows()):
            cor = COR_UNIDADE[i % len(COR_UNIDADE)]
            g = gpd.GeoSeries([row.geometry], crs=u.crs)
            if row.geometry.geom_type.endswith("LineString"):
                g.plot(ax=self.ax, color=contorno, lw=2.6, zorder=8)
                g.plot(ax=self.ax, color=cor, lw=1.6, zorder=9)
                self.handles.append(Line2D([], [], color=cor, lw=1.8, label=row["nome"]))
            else:
                g.plot(ax=self.ax, facecolor=cor, edgecolor=contorno, lw=0.8, zorder=9)
                if row.geometry.area < 5e4:  # unidade pequena: marcador para ficar visível
                    c = row.geometry.centroid
                    self.ax.plot(c.x, c.y, marker="s", ms=5, mfc=cor, mec=contorno, mew=0.8, zorder=10)
                self.handles.append(Line2D([], [], marker="s", ls="", mfc=cor, mec="k", mew=0.4, ms=6, label=row["nome"]))

    def vetor_categorico(self, gdf, campo, cores=None, alpha=0.85, max_classes=18):
        g = gdf.copy()
        g[campo] = g[campo].fillna("Sem informação").astype(str).str.strip()
        janela = self.janela()
        g = g[g.intersects(janela)]
        g["_area"] = g.geometry.intersection(janela).area
        ordem = g.groupby(campo)["_area"].sum().sort_values(ascending=False).index.tolist()
        paleta = plt.get_cmap("tab20").colors + plt.get_cmap("Set3").colors
        cmap, usadas = {}, []
        for i, cl in enumerate(ordem):
            cor = matplotlib.colors.to_rgb((cores(cl) if callable(cores) else None) or paleta[i % len(paleta)])
            k = 0
            while cor in usadas:  # mesma cor sugerida para classes diferentes: alterna claro/escuro
                k += 1
                f = 0.25 * ((k + 1) // 2)
                cor = tuple(min(1, c + (1 - c) * f) if k % 2 else c * (1 - f) for c in cor)
            usadas.append(cor)
            cmap[cl] = cor
        for cl in ordem:
            g[g[campo] == cl].plot(ax=self.ax, color=cmap[cl], edgecolor="#555", lw=0.2, alpha=alpha, zorder=2)
        for cl in ordem[:max_classes]:
            self.handles.append(Patch(facecolor=cmap[cl], edgecolor="#555", lw=0.3, label=cl))
        if len(ordem) > max_classes:
            self.handles.append(Patch(facecolor="white", edgecolor="white", label=f"(+{len(ordem) - max_classes} classes)"))
        self._enquadrar()

    def hidro(self, rotulo=True):
        rios, nasc = self.ctx["rios"], self.ctx["nascentes"]
        if len(rios):
            rios.plot(ax=self.ax, color="#1f78b4", lw=0.5, zorder=5)
            if rotulo:
                self.handles.append(Line2D([], [], color="#1f78b4", lw=0.8, label="Curso d'água"))
        if len(nasc):
            nasc.plot(ax=self.ax, color="#00bfff", markersize=2, zorder=6)
            if rotulo:
                self.handles.append(Line2D([], [], marker="o", ls="", color="#00bfff", ms=3, label="Nascente"))

    def limite_municipal(self):
        m = self.ctx.get("municipio")
        if m is not None:
            m.boundary.plot(ax=self.ax, color="black", lw=0.8, ls="-.", zorder=7)
            self.handles.append(Line2D([], [], color="black", lw=0.8, ls="-.", label="Limite municipal"))
            self._enquadrar()

    # --- acabamento
    def _norte(self):
        ax = self.ax
        x = ax.get_xlim()[1] - (ax.get_xlim()[1] - ax.get_xlim()[0]) * 0.06
        y0, y1 = ax.get_ylim()
        y = y1 - (y1 - y0) * 0.14
        alt = (y1 - y0) * 0.07
        ax.annotate("", xy=(x, y + alt), xytext=(x, y), arrowprops=dict(facecolor="black", edgecolor="white",
                    width=3, headwidth=9, headlength=8, lw=0.5), zorder=20)
        ax.text(x, y + alt * 1.15, "N", ha="center", va="bottom", fontsize=9, fontweight="bold", zorder=20,
                color="black", bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.7))

    def _escala(self):
        ax = self.ax
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        alvo = (x1 - x0) / 4
        p = 10 ** math.floor(math.log10(alvo))
        comp = max(v * p for v in (1, 2, 2.5, 5) if v * p <= alvo)
        seg = comp / 4
        bx, by = x0 + (x1 - x0) * 0.04, y0 + (y1 - y0) * 0.04
        hh = (y1 - y0) * 0.012
        ax.add_patch(Rectangle((bx - seg * 0.2, by - hh * 1.6), comp + seg * 0.4, hh * 5.2, fc="white", ec="none",
                               alpha=0.8, zorder=19))
        for i in range(4):
            ax.add_patch(Rectangle((bx + i * seg, by), seg, hh, fc="black" if i % 2 == 0 else "white", ec="black",
                                   lw=0.5, zorder=20))
        un, f = ("km", 1000) if comp >= 1000 else ("m", 1)
        for i in (0, 2, 4):
            v = i * seg / f
            ax.text(bx + i * seg, by + hh * 1.4, f"{v:g}".replace(".", ","), ha="center", va="bottom", fontsize=5.5,
                    zorder=20)
        ax.text(bx + comp + seg * 0.15, by, un, ha="left", va="bottom", fontsize=5.5, zorder=20)

    def _painel(self):
        p = self.painel
        p.set_xlim(0, 1); p.set_ylim(0, 1)
        p.text(0.5, 0.985, "\n".join(textwrap.wrap(self.titulo.upper(), 26)), ha="center", va="top",
               fontsize=8, fontweight="bold")
        p.axhline(0.915, color="black", lw=0.6)
        p.text(0.05, 0.9, "LEGENDA", fontsize=6.5, fontweight="bold", va="top")
        hs = []
        for h in self.handles:
            h.set_label("\n".join(textwrap.wrap(h.get_label(), 34)))
            hs.append(h)
        if hs:
            p.legend(handles=hs, loc="upper left", bbox_to_anchor=(0.0, 0.88), frameon=False, fontsize=5.3,
                     handlelength=1.6, handleheight=1.0, labelspacing=0.45, borderaxespad=0.3)
        # localização no estado
        ins = self.fig.add_axes(self._ret_inset())
        uf = self.ctx["uf"]
        uf.plot(ax=ins, color="#f0f0f0", edgecolor="#bbb", lw=0.1)
        uf.dissolve().boundary.plot(ax=ins, color="#555", lw=0.4)
        if self.ctx.get("municipio") is not None:
            self.ctx["municipio"].plot(ax=ins, color="#fdae61", edgecolor="#d7191c", lw=0.4)
        x0, x1 = self.ax.get_xlim(); y0, y1 = self.ax.get_ylim()
        gpd.GeoSeries([box(x0, y0, x1, y1)], crs=self.ctx["epsg"]).boundary.plot(ax=ins, color="red", lw=0.7)
        ins.set_xticks([]); ins.set_yticks([]); ins.set_aspect("equal")
        ins.set_xlabel(""); ins.set_ylabel("")
        for s in ins.spines.values():
            s.set_linewidth(0.4)
        ins.set_title("Localização no Estado do Paraná", fontsize=5.5, pad=2)
        # rodapé
        zona = self.ctx["epsg"].split(":")[1]
        fuso = f"{int(zona) - 31960}S" if int(zona) > 31960 else ""
        fontes = "; ".join(dict.fromkeys(self.fontes))
        texto = (f"Projeção Universal Transversa de Mercator\nDatum SIRGAS 2000 – Fuso {fuso}\n\n"
                 + "\n".join(textwrap.wrap("Fontes: " + fontes, 40))
                 + f"\n\nElaboração: Biocerne Ambiental, {ANO}")
        p.text(0.05, 0.02, texto, fontsize=5, va="bottom", ha="left", linespacing=1.25)

    def _ret_inset(self):
        pos = self.painel.get_position()
        return [pos.x0 + pos.width * 0.1, pos.y0 + pos.height * 0.21, pos.width * 0.8, pos.height * 0.2]

    def salvar(self, nome):
        self.ax.set_xlabel("")  # o geopandas recoloca "Easting/Northing" a cada plot
        self.ax.set_ylabel("")
        self._norte()
        self._escala()
        self._painel()
        destino = self.ctx["dir_mapas"] / f"{nome}.png"
        self.fig.savefig(destino, dpi=self.ctx["dpi"], facecolor="white")
        plt.close(self.fig)
        self.ctx["gerados"][nome] = "; ".join(dict.fromkeys(self.fontes))
        print(f"  ok   {destino.name}")


# ------------------------------------------------------------------ mapas
def _ler(ctx, nome):
    arq = ctx["of"] / f"{nome}.gpkg"
    return gpd.read_file(arq).to_crs(ctx["epsg"]) if arq.exists() else None


def m_localizacao_unidades(ctx):
    m = Mapa(ctx, "Localização das unidades do empreendimento", paisagem=True)
    m.satelite()
    m.unidades()
    m.fontes.append(f"{ctx['cfg']['empresa'].get('sigla', 'Empreendedor')} ({ANO})")
    m.salvar("localizacao_unidades")


def m_localizacao_regional(ctx):
    ctx2 = dict(ctx)
    mun = ctx["municipio"]
    ctx2["extent"] = tuple(mun.total_bounds + np.array([-8000, -8000, 8000, 8000]))
    m = Mapa(ctx2, f"Localização regional – {ctx['cfg']['municipio']}/{ctx['cfg']['uf']}")
    uf = ctx["uf"]
    uf.plot(ax=m.ax, color="#f7f7f7", edgecolor="#999", lw=0.4, zorder=1)
    for _, r in uf[uf.intersects(m.janela())].iterrows():
        c = r.geometry.representative_point()
        if r["cod_ibge"] != ctx["cfg"]["cod_ibge"]:
            m.ax.text(c.x, c.y, r["nome"], fontsize=5, ha="center", color="#555", zorder=3, clip_on=True)
    mun.plot(ax=m.ax, color="#fee8c8", edgecolor="#d7191c", lw=1.0, zorder=2)
    m.handles.append(Patch(facecolor="#fee8c8", edgecolor="#d7191c", label=f"Município de {ctx['cfg']['municipio']}"))
    m.handles.append(Patch(facecolor="#f7f7f7", edgecolor="#999", label="Municípios limítrofes"))
    m.unidades(contorno="black")
    m._enquadrar()
    m.fontes += ["IBGE (2022) – Malha Municipal", f"{ctx['cfg']['empresa'].get('sigla', 'Empreendedor')} ({ANO})"]
    m.salvar("localizacao_regional")


def _tema(ctx, nome, camada, campo, titulo, fonte, cores=None, paisagem=False):
    g = _ler(ctx, camada)
    if g is None or g.empty or campo not in g:
        print(f"  --   {nome}: camada {camada} indisponível")
        return
    m = Mapa(ctx, titulo, paisagem)
    m.vetor_categorico(g, campo, cores)
    m.unidades()
    m.fontes += [fonte, f"{ctx['cfg']['empresa'].get('sigla', 'Empreendedor')} ({ANO})"]
    m.salvar(nome)


def _cor_solo(legenda):
    if legenda.lower().startswith("área urbana"):
        return "#bdbdbd"
    if "água" in legenda.lower():
        return "#6baed6"
    sigla = legenda.split(" ")[0]
    return CORES_SOLO.get(sigla[:2]) or CORES_SOLO.get(sigla[:1])


def m_solos(ctx):
    _tema(ctx, "solos", "solos", "legenda", "Mapa pedológico", "IBGE (2023) – BDiA Pedologia 1:250.000", _cor_solo)


def m_geologia(ctx):
    g = _ler(ctx, "geologia")
    if g is not None and "nm_unidade" in g:
        g["classe"] = g["nm_unidade"].astype(str) + g["letra_simb"].map(lambda s: f" ({s})" if s else "").fillna("")
        g.to_file(ctx["of"] / "_geologia_mapa.gpkg", driver="GPKG")
        _tema(ctx, "geologia", "_geologia_mapa", "classe", "Mapa geológico", "IBGE (2023) – BDiA Geologia 1:250.000")
        (ctx["of"] / "_geologia_mapa.gpkg").unlink(missing_ok=True)


def m_geomorfologia(ctx):
    _tema(ctx, "geomorfologia", "geomorfologia", "nm_unidade", "Mapa geomorfológico",
          "IBGE (2023) – BDiA Geomorfologia 1:250.000")


def m_hidrogeologia(ctx):
    _tema(ctx, "hidrogeologia", "hidrogeologia", "nome_unida", "Mapa hidrogeológico",
          "SGB/CPRM – Domínios Hidrogeológicos 1:2.500.000")


def m_fitogeografia(ctx):
    _tema(ctx, "fitogeografia", "vegetacao", "nm_pretet", "Enquadramento fitogeográfico",
          "IBGE (2023) – BDiA Vegetação 1:250.000")


def m_bacia(ctx):
    m = Mapa(ctx, "Bacia hidrográfica")
    uph = _ler(ctx, "uph")
    if uph is not None:
        m.vetor_categorico(uph, "UPH_SG", alpha=0.35)
        m.handles = [Patch(facecolor=h.get_facecolor(), edgecolor="#555", label=f"UPH {h.get_label()}") for h in m.handles]
        m.fontes.append("ANA – Unidades de Planejamento Hídrico")
    ma = _ler(ctx, "massa_dagua")
    if ma is not None:
        ma.plot(ax=m.ax, color="#6baed6", zorder=3)
    dren = _ler(ctx, "drenagem")
    if dren is not None:
        dren.plot(ax=m.ax, color="#08519c", lw=0.7, zorder=4)
        m.handles.append(Line2D([], [], color="#08519c", lw=0.9, label="Drenagem principal (BC250)"))
        nomeados = dren[dren["nome"].notna()].dissolve("nome").reset_index()
        for _, r in nomeados.iterrows():
            p = r.geometry.interpolate(0.5, normalized=True)
            m.ax.text(p.x, p.y, r["nome"], fontsize=5, color="#08306b", style="italic", zorder=11, clip_on=True,
                      bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.6))
        m.fontes.append("IBGE (2023) – BC250")
    m.hidro()
    m.unidades(contorno="black")
    m._enquadrar()
    m.fontes.append(f"{ctx['cfg']['empresa'].get('sigla', 'Empreendedor')} ({ANO})")
    m.salvar("bacia")


def m_altimetria(ctx):
    if not (ctx["of"] / "dem.tif").exists():
        print("  --   altimetria: dem.tif indisponível"); return
    dem, tr, nd = raster.para_utm(ctx["of"] / "dem.tif", ctx["epsg"])
    z = np.where(dem == nd, np.nan, dem).astype(float)
    ext = (tr.c, tr.c + tr.a * z.shape[1], tr.f + tr.e * z.shape[0], tr.f)
    m = Mapa(ctx, "Mapa hipsométrico")
    ls = LightSource(azdeg=315, altdeg=45)
    vmin, vmax = np.nanpercentile(z, 1), np.nanpercentile(z, 99)
    cmap = plt.get_cmap("terrain")
    rgb = ls.shade(np.nan_to_num(z, nan=vmin), cmap=cmap, vmin=vmin, vmax=vmax, vert_exag=2, blend_mode="soft")
    m.ax.imshow(rgb, extent=ext, zorder=1)
    passos = np.linspace(vmin, vmax, 6)
    for i in range(5):
        cor = cmap(((passos[i] + passos[i + 1]) / 2 - vmin) / (vmax - vmin))
        m.handles.append(Patch(facecolor=cor, edgecolor="#555", lw=0.3, label=f"{passos[i]:.0f} – {passos[i + 1]:.0f} m"))
    m.hidro()
    m.unidades(contorno="black")
    m._enquadrar()
    m.fontes += ["Copernicus DEM GLO-30 (ESA)", f"{ctx['cfg']['empresa'].get('sigla', 'Empreendedor')} ({ANO})"]
    m.salvar("altimetria")


def m_declividade(ctx):
    if not (ctx["of"] / "dem.tif").exists():
        print("  --   declividade: dem.tif indisponível"); return
    dem, tr, nd = raster.para_utm(ctx["of"] / "dem.tif", ctx["epsg"])
    s = raster.declividade_pct(np.where(dem == nd, np.nan, dem), 30.0)
    ext = (tr.c, tr.c + tr.a * s.shape[1], tr.f + tr.e * s.shape[0], tr.f)
    limites = [0] + [l if l < 1e8 else 1000 for l, _, _ in DECLIVIDADE]
    cmap = ListedColormap([c for _, _, c in DECLIVIDADE])
    m = Mapa(ctx, "Mapa de declividade")
    m.ax.imshow(s, extent=ext, cmap=cmap, norm=BoundaryNorm(limites, cmap.N), zorder=1, interpolation="nearest")
    for _, nome, cor in DECLIVIDADE:
        m.handles.append(Patch(facecolor=cor, edgecolor="#555", lw=0.3, label=nome))
    m.unidades(contorno="black")
    m._enquadrar()
    m.fontes += ["Copernicus DEM GLO-30 (ESA)", "classes EMBRAPA (1979)", f"{ctx['cfg']['empresa'].get('sigla', 'Empreendedor')} ({ANO})"]
    m.salvar("declividade")


def m_uso_solo(ctx):
    if not (ctx["of"] / "mapbiomas.tif").exists():
        print("  --   uso_solo: mapbiomas.tif indisponível"); return
    from rasterio.enums import Resampling
    mb, tr, nd = raster.para_utm(ctx["of"] / "mapbiomas.tif", ctx["epsg"], reamostragem=Resampling.nearest)
    ext = (tr.c, tr.c + tr.a * mb.shape[1], tr.f + tr.e * mb.shape[0], tr.f)
    rgba = np.zeros(mb.shape + (4,))
    presentes = []
    for cod in np.unique(mb):
        if cod in MAPBIOMAS:
            nome, cor = MAPBIOMAS[cod]
            rgba[mb == cod] = matplotlib.colors.to_rgba(cor)
            presentes.append((int((mb == cod).sum()), nome, cor))
    m = Mapa(ctx, "Uso e cobertura do solo")
    m.ax.imshow(rgba, extent=ext, zorder=1, interpolation="nearest")
    for _, nome, cor in sorted(presentes, reverse=True):
        m.handles.append(Patch(facecolor=cor, edgecolor="#555", lw=0.3, label=nome))
    m.unidades(contorno="black")
    m._enquadrar()
    m.fontes += ["MapBiomas Coleção 9 (2023)", f"{ctx['cfg']['empresa'].get('sigla', 'Empreendedor')} ({ANO})"]
    m.salvar("uso_solo")


def tem_car(cfg):
    car_dir = cfg["dir"] / "dados" / "car"
    return car_dir.exists() and any(list(car_dir.glob("*.shp")) + list(car_dir.glob("*.gpkg")))


def m_app_rl(ctx):
    # sem shapes do CAR não há Reserva Legal no mapa: o título não pode prometer o que o mapa não mostra
    titulo = "Áreas de Preservação Permanente e Reserva Legal" if tem_car(ctx["cfg"]) else "Áreas de Preservação Permanente"
    m = Mapa(ctx, titulo, paisagem=True)
    m.satelite()
    # só o entorno das unidades (1 km): na escala do sistema a hidrografia inteira polui o mapa
    entorno = ctx["unidades"].geometry.buffer(1000).union_all()
    rios = ctx["rios"][ctx["rios"].intersects(entorno)]
    nasc = ctx["nascentes"][ctx["nascentes"].intersects(entorno)] if len(ctx["nascentes"]) else ctx["nascentes"]
    app = faixas_app(rios, nasc)
    app = app[app.intersects(entorno)]
    ctx = dict(ctx, rios=rios.clip(entorno), nascentes=nasc)
    m.ctx = ctx
    gpd.GeoSeries([entorno], crs=ctx["epsg"]).boundary.plot(ax=m.ax, color="white", lw=0.5, ls=":", zorder=2)
    m.handles.append(Line2D([], [], color="#777", lw=0.6, ls=":", label="Entorno de 1 km das unidades"))
    if len(app):
        gpd.GeoSeries([app.geometry.union_all()], crs=ctx["epsg"]).plot(ax=m.ax, facecolor="#41ab5d", alpha=0.45,
                                                                        edgecolor="#00441b", lw=0.3, zorder=3)
        m.handles.append(Patch(facecolor="#41ab5d", alpha=0.6, edgecolor="#00441b", label="APP (Lei 12.651/2012)"))
    # CAR (Reserva Legal etc.) se o usuário colocar os shapefiles em dados/car/
    car_dir = ctx["cfg"]["dir"] / "dados" / "car"
    estilos = [("#ffd92f", "Reserva Legal"), ("#e78ac3", "Imóvel rural (CAR)"), ("#a6d854", "Vegetação nativa (CAR)")]
    for i, arq in enumerate(sorted(list(car_dir.glob("*.shp")) + list(car_dir.glob("*.gpkg"))) if car_dir.exists() else []):
        g = gpd.read_file(arq).to_crs(ctx["epsg"])
        cor, rot = next(((c, r) for c, r in estilos if r.split()[0].lower() in arq.stem.lower()), (estilos[i % 3][0], arq.stem))
        g.plot(ax=m.ax, facecolor="none", edgecolor=cor, lw=0.9, hatch="///" if "reserva" in arq.stem.lower() else None, zorder=4)
        m.handles.append(Patch(facecolor="none", edgecolor=cor, hatch="///", label=rot))
        m.fontes.append("SICAR")
    m.hidro()
    m.unidades()
    m._enquadrar()
    if ctx.get("fonte_hidro"):
        m.fontes.append(f"Hidrografia: {ctx['fonte_hidro']}")
    m.fontes.append(f"{ctx['cfg']['empresa'].get('sigla', 'Empreendedor')} ({ANO})")
    m.salvar("app_rl")


MAPAS = {
    "localizacao_unidades": m_localizacao_unidades, "localizacao_regional": m_localizacao_regional,
    "solos": m_solos, "uso_solo": m_uso_solo, "geomorfologia": m_geomorfologia, "altimetria": m_altimetria,
    "declividade": m_declividade, "bacia": m_bacia, "geologia": m_geologia, "hidrogeologia": m_hidrogeologia,
    "fitogeografia": m_fitogeografia, "app_rl": m_app_rl,
}


def contexto(cfg, dpi=200):
    u, epsg = unidades(cfg)
    rios, nasc, fonte_r = hidrografia(cfg, epsg)
    of = cfg["dir"] / "dados" / "oficiais"
    x0, y0, x1, y1 = u.total_bounds
    # extensão mínima de 4 km: projetos de uma só unidade pequena (ex.: ETE) precisam mostrar o entorno
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    x0, x1 = min(x0, cx - 2000), max(x1, cx + 2000)
    y0, y1 = min(y0, cy - 2000), max(y1, cy + 2000)
    pad = min(max(0.08 * max(x1 - x0, y1 - y0), 500), 2500)
    janela = box(x0 - pad * 3, y0 - pad * 3, x1 + pad * 3, y1 + pad * 3)
    uf = gpd.read_file(of / "municipios_uf.gpkg").to_crs(epsg)
    mun = gpd.read_file(of / "municipio.gpkg").to_crs(epsg) if (of / "municipio.gpkg").exists() else None
    ctx = {"cfg": cfg, "epsg": epsg, "unidades": u, "of": of, "dpi": dpi, "uf": uf, "municipio": mun,
           "rios": rios[rios.intersects(janela)], "nascentes": nasc[nasc.intersects(janela)] if len(nasc) else nasc,
           "fonte_hidro": fonte_r, "extent": (x0 - pad, y0 - pad, x1 + pad, y1 + pad),
           "dir_mapas": cfg["dir"] / "dados" / "mapas_conferencia", "gerados": {}}
    ctx["dir_mapas"].mkdir(parents=True, exist_ok=True)
    return ctx


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chave")
    ap.add_argument("--so", help="lista separada por vírgula")
    ap.add_argument("--dpi", type=int, default=200)
    a = ap.parse_args()
    cfg = projeto(a.chave)
    ctx = contexto(cfg, a.dpi)
    alvo = a.so.split(",") if a.so else list(MAPAS)
    for nome in alvo:
        try:
            MAPAS[nome](ctx)
        except Exception as e:
            print(f"  ERRO {nome}: {e.__class__.__name__}: {e}")
            plt.close("all")
    indice = ctx["dir_mapas"] / "MAPAS.md"
    anteriores = {}
    if indice.exists():  # mantém mapas gerados em execuções anteriores (--so)
        for ln in indice.read_text(encoding="utf-8").splitlines():
            if ln.startswith("| mapas/"):
                partes = [p.strip() for p in ln.strip("|").split("|")]
                anteriores[partes[0][6:-4]] = partes[1]
    anteriores.update({n: f"{f}; elaborado pelo autor, {ANO}." for n, f in ctx["gerados"].items()})
    linhas = [f"# Mapas – {cfg['municipio']}\n", "| Mapa | Fontes (usar no campo fonte= da figura) |", "|---|---|"]
    linhas += [f"| mapas/{n}.png | {f} |" for n, f in anteriores.items()]
    indice.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"Mapas em {ctx['dir_mapas']}")


if __name__ == "__main__":
    main()
