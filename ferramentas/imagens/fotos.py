"""Organiza as fotos de campo de um projeto.

Uso:
    python -m ferramentas.imagens.fotos candoi [--origem PASTA] [--largura 1600] [--sem-mapa]

Lê as fotos de projetos/<chave>/fotos/brutas/ (ou --origem), e para cada uma:
  - corrige a rotação (EXIF), reduz para --largura px e salva como fotos/foto_NNN.jpg
  - lê data e GPS do EXIF; associa à unidade do empreendimento mais próxima
Gera:
  fotos/FOTOS.md        tabela (arquivo, data, coordenadas, unidade mais próxima) + diretivas de figura prontas
  fotos/fotos.gpkg      pontos das fotos com GPS
  fotos/contato_NN.png  folhas de contato numeradas (a IA lê para descrever cada foto)
  mapas/pontos_fotograficos.png  mapa dos pontos fotográficos (se houver GPS)
"""
import argparse
import datetime as dt
from pathlib import Path

import geopandas as gpd
from PIL import Image, ImageDraw, ImageOps
from PIL.ExifTags import GPSTAGS, TAGS
from shapely.geometry import Point

from ferramentas.util import console_utf8, projeto

EXTENSOES = {".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff", ".webp"}


def _exif(im):
    try:
        raw = im._getexif() or {}
    except Exception:
        return {}
    return {TAGS.get(k, k): v for k, v in raw.items()}


def _gps(exif):
    info = exif.get("GPSInfo")
    if not info:
        return None
    g = {GPSTAGS.get(k, k): v for k, v in info.items()}
    try:
        def dec(vals, ref):
            d, m, s = (float(x) for x in vals)
            v = d + m / 60 + s / 3600
            return -v if ref in ("S", "W") else v
        return dec(g["GPSLatitude"], g["GPSLatitudeRef"]), dec(g["GPSLongitude"], g["GPSLongitudeRef"])
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None


def _data(exif):
    for chave in ("DateTimeOriginal", "DateTime"):
        if exif.get(chave):
            try:
                return dt.datetime.strptime(str(exif[chave]), "%Y:%m:%d %H:%M:%S")
            except ValueError:
                pass
    return None


def processar(cfg, origem: Path, largura=1600):
    destino = cfg["dir"] / "fotos"
    destino.mkdir(parents=True, exist_ok=True)
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
    except ImportError:
        pass
    arquivos = sorted(p for p in origem.rglob("*") if p.suffix.lower() in EXTENSOES and p.parent != destino)
    registros = []
    for i, arq in enumerate(arquivos, start=1):
        try:
            with Image.open(arq) as im:
                exif = _exif(im)
                im = ImageOps.exif_transpose(im).convert("RGB")
                im.thumbnail((largura, largura))
                nome = f"foto_{i:03d}.jpg"
                im.save(destino / nome, "JPEG", quality=85, optimize=True)
        except Exception as e:
            print(f"  ERRO {arq.name}: {e}")
            continue
        gps = _gps(exif)
        data = _data(exif)
        registros.append({"arquivo": nome, "original": str(arq.relative_to(origem)), "data": data,
                          "lat": round(gps[0], 6) if gps else None, "lon": round(gps[1], 6) if gps else None})
    return registros


def associar_unidades(cfg, registros):
    arq = cfg["dir"] / "dados" / "unidades.gpkg"
    com_gps = [r for r in registros if r["lat"] is not None]
    if not arq.exists() or not com_gps:
        return None
    from ferramentas.geo.coordenadas import fuso_utm
    u = gpd.read_file(arq)
    c = u.to_crs("EPSG:4674").geometry.union_all().centroid
    epsg = fuso_utm(c.x, c.y)
    u = u.to_crs(epsg)
    pts = gpd.GeoDataFrame(com_gps, geometry=[Point(r["lon"], r["lat"]) for r in com_gps], crs="EPSG:4674").to_crs(epsg)
    for idx, p in pts.iterrows():
        dist = u.distance(p.geometry)
        j = dist.idxmin()
        com_gps[idx]["unidade"] = u.loc[j, "nome"]
        com_gps[idx]["dist_m"] = round(float(dist.min()))
    pts["unidade"] = [r["unidade"] for r in com_gps]
    pts["dist_m"] = [r["dist_m"] for r in com_gps]
    pts["data"] = pts["data"].astype(str)
    pts.to_file(cfg["dir"] / "fotos" / "fotos.gpkg", driver="GPKG")
    return pts


def folhas_contato(destino: Path, registros, por_folha=12, colunas=4, lado=420):
    for f in destino.glob("contato_*.png"):
        f.unlink()
    saidas = []
    for k in range(0, len(registros), por_folha):
        grupo = registros[k:k + por_folha]
        linhas = (len(grupo) + colunas - 1) // colunas
        folha = Image.new("RGB", (colunas * (lado + 10) + 10, linhas * (lado + 40) + 10), "white")
        d = ImageDraw.Draw(folha)
        for j, r in enumerate(grupo):
            with Image.open(destino / r["arquivo"]) as im:
                im.thumbnail((lado, lado))
                x = 10 + (j % colunas) * (lado + 10)
                y = 10 + (j // colunas) * (lado + 40)
                folha.paste(im, (x, y + 28))
                rot = r["arquivo"] + (f" – {r['unidade']}" if r.get("unidade") else "")
                d.text((x, y + 6), rot[:60], fill="black")
        out = destino / f"contato_{k // por_folha + 1:02d}.png"
        folha.save(out)
        saidas.append(out)
    return saidas


def mapa_pontos(cfg, pts):
    from ferramentas.geo import mapas
    ctx = mapas.contexto(cfg)
    m = mapas.Mapa(ctx, "Pontos de registro fotográfico", paisagem=True)
    m.satelite()
    m.unidades()
    pts.plot(ax=m.ax, color="yellow", edgecolor="black", markersize=18, zorder=12)
    for _, p in pts.iterrows():
        m.ax.annotate(p["arquivo"][5:8], (p.geometry.x, p.geometry.y), xytext=(3, 3), textcoords="offset points",
                      fontsize=5, color="white", zorder=13, fontweight="bold")
    from matplotlib.lines import Line2D
    m.handles.insert(0, Line2D([], [], marker="o", ls="", mfc="yellow", mec="black", label="Ponto fotográfico (nº da foto)"))
    m.fontes.append("Levantamento de campo")
    m.salvar("pontos_fotograficos")


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chave")
    ap.add_argument("--origem", help="pasta com as fotos originais (padrão: fotos/brutas)")
    ap.add_argument("--largura", type=int, default=1600)
    ap.add_argument("--sem-mapa", action="store_true")
    a = ap.parse_args()
    cfg = projeto(a.chave)
    origem = Path(a.origem) if a.origem else cfg["dir"] / "fotos" / "brutas"
    if not origem.exists():
        raise SystemExit(f"Coloque as fotos em {origem} (ou use --origem)")
    regs = processar(cfg, origem, a.largura)
    pts = associar_unidades(cfg, regs)
    destino = cfg["dir"] / "fotos"
    contatos = folhas_contato(destino, regs)

    ano = dt.date.today().year
    md = [f"# Fotos de campo – {cfg['municipio']}\n", f"{len(regs)} fotos; {sum(r['lat'] is not None for r in regs)} com GPS.\n",
          "| Foto | Original | Data | Lat | Lon | Unidade mais próxima | Dist. (m) |", "|---|---|---|---|---|---|---|"]
    for r in regs:
        md.append(f"| {r['arquivo']} | {r['original']} | {r['data'] or ''} | {r['lat'] or ''} | {r['lon'] or ''} | "
                  f"{r.get('unidade', '')} | {r.get('dist_m', '')} |")
    md.append("\n## Diretivas prontas (descrever cada foto após ver as folhas de contato)\n")
    for r in sorted(regs, key=lambda r: (r.get("unidade") or "~", r["arquivo"])):
        md.append(f"![[A VERIFICAR: descrever foto – {r.get('unidade', 'sem GPS')}]](fotos/{r['arquivo']})"
                  f"{{fonte=\"Autor, {ano}.\"}}")
    (destino / "FOTOS.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"{len(regs)} fotos processadas em {destino}")
    print("Folhas de contato:", ", ".join(c.name for c in contatos))
    if pts is not None and len(pts) and not a.sem_mapa:
        mapa_pontos(cfg, pts)


if __name__ == "__main__":
    main()
