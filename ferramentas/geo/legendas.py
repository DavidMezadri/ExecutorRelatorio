"""Legendas e regras oficiais usadas em mapas e resumos."""
import re

# MapBiomas Coleção 9 – código: (nome, cor oficial)
MAPBIOMAS = {
    3: ("Formação Florestal", "#1f8d49"), 4: ("Formação Savânica", "#7dc975"), 5: ("Mangue", "#04381d"),
    6: ("Floresta Alagável", "#026975"), 49: ("Restinga Arbórea", "#02d659"), 11: ("Campo Alagado e Área Pantanosa", "#519799"),
    12: ("Formação Campestre", "#d6bc74"), 32: ("Apicum", "#fc8114"), 29: ("Afloramento Rochoso", "#ffaa5f"),
    50: ("Restinga Herbácea", "#ad5100"), 13: ("Outras Formações não Florestais", "#d89f5c"), 15: ("Pastagem", "#edde8e"),
    39: ("Soja", "#f5b3c8"), 20: ("Cana", "#db7093"), 40: ("Arroz", "#c71585"), 62: ("Algodão", "#ff69b4"),
    41: ("Outras Lavouras Temporárias", "#f54ca9"), 46: ("Café", "#d68fe2"), 47: ("Citrus", "#9932cc"),
    35: ("Dendê", "#9065d0"), 48: ("Outras Lavouras Perenes", "#e6ccff"), 9: ("Silvicultura", "#7a5900"),
    21: ("Mosaico de Usos", "#ffefc3"), 23: ("Praia, Duna e Areal", "#ffa07a"), 24: ("Área Urbanizada", "#d4271e"),
    30: ("Mineração", "#9c0027"), 75: ("Usina Fotovoltaica", "#c12100"), 25: ("Outras Áreas não Vegetadas", "#db4d4f"),
    33: ("Rio, Lago e Oceano", "#2532e4"), 31: ("Aquicultura", "#091077"),
}

# Classes de relevo por declividade (EMBRAPA, 1979) – limite superior em %
DECLIVIDADE = [
    (3, "Plano (0–3%)", "#1a9641"), (8, "Suave ondulado (3–8%)", "#a6d96a"), (20, "Ondulado (8–20%)", "#ffffbf"),
    (45, "Forte ondulado (20–45%)", "#fdae61"), (75, "Montanhoso (45–75%)", "#d7191c"), (1e9, "Escarpado (>75%)", "#7b0d0f"),
]

# Lei 12.651/2012, art. 4º, I – largura do curso d'água (m) -> faixa de APP (m)
APP_CURSO = [(10, 30), (50, 50), (200, 100), (600, 200), (1e9, 500)]
APP_NASCENTE_M = 50


def app_por_largura(texto_largura) -> int:
    """'curso d'água (0 - 10m)' / '10 - 50m' / número -> faixa de APP em metros (padrão 30)."""
    if texto_largura is None:
        return 30
    nums = [float(n) for n in re.findall(r"\d+(?:[.,]\d+)?", str(texto_largura).replace(",", "."))]
    largura = max(nums) if nums else 0
    for limite, faixa in APP_CURSO:
        if largura <= limite:
            return faixa
    return 30
