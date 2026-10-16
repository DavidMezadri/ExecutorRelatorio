"""Dados nacionais fixos: UFs (código IBGE, nome, capital e coordenadas da capital)."""

# sigla: (código IBGE, nome, capital, (lon, lat) da sede da capital)
UFS = {
    "RO": (11, "Rondônia", "Porto Velho", (-63.9004, -8.7608)),
    "AC": (12, "Acre", "Rio Branco", (-67.8076, -9.9747)),
    "AM": (13, "Amazonas", "Manaus", (-60.0217, -3.1190)),
    "RR": (14, "Roraima", "Boa Vista", (-60.6714, 2.8235)),
    "PA": (15, "Pará", "Belém", (-48.4902, -1.4558)),
    "AP": (16, "Amapá", "Macapá", (-51.0694, 0.0349)),
    "TO": (17, "Tocantins", "Palmas", (-48.3336, -10.1844)),
    "MA": (21, "Maranhão", "São Luís", (-44.3028, -2.5297)),
    "PI": (22, "Piauí", "Teresina", (-42.8019, -5.0920)),
    "CE": (23, "Ceará", "Fortaleza", (-38.5267, -3.7319)),
    "RN": (24, "Rio Grande do Norte", "Natal", (-35.2094, -5.7945)),
    "PB": (25, "Paraíba", "João Pessoa", (-34.8631, -7.1195)),
    "PE": (26, "Pernambuco", "Recife", (-34.8770, -8.0476)),
    "AL": (27, "Alagoas", "Maceió", (-35.7350, -9.6658)),
    "SE": (28, "Sergipe", "Aracaju", (-37.0731, -10.9472)),
    "BA": (29, "Bahia", "Salvador", (-38.5014, -12.9714)),
    "MG": (31, "Minas Gerais", "Belo Horizonte", (-43.9378, -19.9208)),
    "ES": (32, "Espírito Santo", "Vitória", (-40.3128, -20.3155)),
    "RJ": (33, "Rio de Janeiro", "Rio de Janeiro", (-43.1729, -22.9068)),
    "SP": (35, "São Paulo", "São Paulo", (-46.6333, -23.5505)),
    "PR": (41, "Paraná", "Curitiba", (-49.2733, -25.4284)),
    "SC": (42, "Santa Catarina", "Florianópolis", (-48.5482, -27.5949)),
    "RS": (43, "Rio Grande do Sul", "Porto Alegre", (-51.2177, -30.0346)),
    "MS": (50, "Mato Grosso do Sul", "Campo Grande", (-54.6201, -20.4697)),
    "MT": (51, "Mato Grosso", "Cuiabá", (-56.0979, -15.6014)),
    "GO": (52, "Goiás", "Goiânia", (-49.2532, -16.6869)),
    "DF": (53, "Distrito Federal", "Brasília", (-47.8825, -15.7942)),
}
UF_COD = {uf: v[0] for uf, v in UFS.items()}
COD_UF = {v[0]: uf for uf, v in UFS.items()}


def nome_uf(uf):
    return UFS[uf][1]


def capital(uf):
    """(nome da capital, (lon, lat))."""
    return UFS[uf][2], UFS[uf][3]


def uf_do_codigo(cod_ibge):
    """UF a partir do código IBGE do município (2 primeiros dígitos)."""
    return COD_UF.get(int(str(cod_ibge)[:2])) if cod_ibge else None


_DA = {"BA", "PB"}
_DE = {"SP", "SC", "MG", "GO", "AL", "PE", "SE", "RO", "RR"}


def uf_de(uf):
    """'do Paraná', 'de Santa Catarina', 'da Bahia'."""
    art = "da" if uf in _DA else "de" if uf in _DE else "do"
    return f"{art} {UFS[uf][1]}"
