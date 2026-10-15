"""Operações raster: reprojeção para UTM, declividade, estatísticas por geometria."""
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import Resampling, calculate_default_transform, reproject


def para_utm(caminho, epsg_utm, res=30.0, reamostragem=Resampling.bilinear):
    """Lê raster e reprojeta para UTM. Retorna (array, transform, nodata)."""
    with rasterio.open(caminho) as src:
        transf, w, h = calculate_default_transform(src.crs, epsg_utm, src.width, src.height, *src.bounds, resolution=res)
        nodata = src.nodata if src.nodata is not None else -9999
        dst = np.full((h, w), nodata, dtype=src.dtypes[0])
        reproject(rasterio.band(src, 1), dst, src_transform=src.transform, src_crs=src.crs,
                  dst_transform=transf, dst_crs=epsg_utm, resampling=reamostragem, dst_nodata=nodata)
    return dst, transf, nodata


def declividade_pct(dem, res):
    z = dem.astype("float64")
    dzdy, dzdx = np.gradient(z, res, res)
    return np.hypot(dzdx, dzdy) * 100.0


def valores_na_geometria(arr, transf, geom, nodata=None):
    """Valores do raster dentro da geometria (já no mesmo CRS do raster)."""
    mask = geometry_mask([geom], out_shape=arr.shape, transform=transf, invert=True, all_touched=True)
    v = arr[mask]
    if nodata is not None:
        v = v[v != nodata]
    return v
