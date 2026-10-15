"""Redator automático: transforma os dados do projeto em parágrafos técnicos com citação.

Uso:
    python -m ferramentas.redacao.redator candoi

Lê dados/resumo_tematico.yaml, dados/dossie.yaml, dados/especies_*.xlsx e gera:
    dados/redacao.yaml   textos {{auto.<bloco>}} usados pelos textos-base (texto/*.md)
    dados/REDACAO.md     os mesmos textos para leitura/revisão
Blocos: pedologia, uso_solo, geomorfologia, geologia, hidrogeologia, hidrologia, fitogeografia, app, erosao,
alagadicos, supressao, entorno, territorios, ucs, impactos_especificos.
Tudo que é estimativa sai identificado como tal; o que depende de campo/cliente continua [A VERIFICAR].
"""
import argparse
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml

from ferramentas.util import console_utf8, projeto
from ferramentas.garimpo import biblio

CIT = {"ibge": "IBGE, 2023", "sgb": "SGB, [20--]", "mapbiomas": "PROJETO MAPBIOMAS, 2024", "dem": "ESA, 2021",
       "ana": "ANA, [20--]", "lei12651": "BRASIL, 2012", "embrapa79": "EMBRAPA, 1979", "conama357": "BRASIL, 2005"}
NATURAL = {"Formação Florestal", "Formação Savânica", "Floresta Alagável", "Restinga Arbórea", "Campo Alagado e Área Pantanosa",
           "Formação Campestre", "Outras Formações não Florestais", "Mangue", "Restinga Herbácea"}
FAIXA_M = 15


def br(v, c=1):
    return f"{v:,.{c}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def lista(itens):
    itens = [str(i) for i in itens if i]
    return "" if not itens else itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1]


def _ler(p):
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}


class Redator:
    def __init__(self, cfg):
        self.cfg = cfg
        d = cfg["dir"] / "dados"
        self.res = _ler(d / "resumo_tematico.yaml")
        self.dos = _ler(d / "dossie.yaml")
        self.un = self.res.get("unidades", {})
        self.cam = self.res.get("camadas", {})
        u = gpd.read_file(d / "unidades.gpkg").to_crs(self.res.get("crs_utm", "EPSG:31982"))
        self.area = {r["nome"]: (r.geometry.buffer(FAIXA_M).area if r.geometry.geom_type.endswith("LineString")
                                 else r.geometry.area) for _, r in u.iterrows()}
        self.tipo = {r["nome"]: ("linear" if r.geometry.geom_type.endswith("LineString") else "pontual") for _, r in u.iterrows()}
        self.esp = {k: pd.read_excel(d / f"especies_{k}.xlsx") for k in ("plantas", "animais") if (d / f"especies_{k}.xlsx").exists()}
        self.usados = set()

    def cita(self, k):
        self.usados.add(k)
        return CIT[k]

    def ponderado(self, campo):
        """Distribuição de classes no conjunto das unidades, ponderada pela área (faixa de obra nas lineares)."""
        tot = defaultdict(float)
        for nome, info in self.un.items():
            for cl, pct in (info.get(campo) or {}).items():
                tot[cl] += pct / 100 * self.area.get(nome, 0)
        soma = sum(tot.values()) or 1
        return {k: v / soma * 100 for k, v in sorted(tot.items(), key=lambda x: -x[1])}

    def dominante(self, nome, campo):
        d = self.un.get(nome, {}).get(campo) or {}
        return max(d, key=d.get) if d else None

    # ---------------------------------------------------------------- meio físico
    def pedologia(self):
        dist = self.ponderado("solos")
        if not dist:
            return None
        det = self.cam.get("solos", {}).get("classes", {})
        partes = []
        for cl, pct in dist.items():
            if pct < 1:
                continue
            x = det.get(cl, {})
            carac = "; ".join(f"{k} {' '.join(str(v).split())}" for k, v in (("relevo", x.get("relevo")), ("textura", x.get("textura"))) if v)
            if cl.lower().startswith("área urbana"):
                partes.append(f"área urbana sem mapeamento pedológico ({br(pct)}%)")
                continue
            partes.append(f"{cl.split(' - ', 1)[-1]} ({br(pct)}% da área de intervenção{'; ' + carac if carac else ''})")
        por = defaultdict(list)
        for nome in self.un:
            dom = self.dominante(nome, "solos")
            if dom:
                por[dom.split(" - ", 1)[-1]].append(nome)
        frases = [(f"{lista(n)} {'situam-se' if len(n) > 1 else 'situa-se'} em área urbana" if cl.lower().startswith("área urbana") else
                   f"{lista(n)} {'assentam-se' if len(n) > 1 else 'assenta-se'} predominantemente sobre {cl}") for cl, n in por.items()]
        return (f"De acordo com o mapeamento pedológico do IBGE, em escala 1:250.000, a área de intervenção do empreendimento "
                f"abrange as seguintes classes de solo: {lista(partes)} ({self.cita('ibge')}). "
                f"Por unidade, {'; '.join(frases)}.")

    def uso_solo(self):
        dist = self.ponderado("uso_solo_mapbiomas")
        if not dist:
            return None
        top = [f"{k.lower()} ({br(v)}%)" for k, v in dist.items() if v >= 1]
        nat = sum(v for k, v in dist.items() if k in NATURAL)
        return (f"Segundo o mapeamento de cobertura e uso da terra do Projeto MapBiomas (Coleção 9, ano-base 2023), a área "
                f"de intervenção do empreendimento é ocupada por {lista(top)} ({self.cita('mapbiomas')}). As formações naturais "
                f"somam cerca de {br(nat)}% da área, o restante correspondendo a usos antrópicos. O mapeamento, de resolução "
                f"espacial de 30 m, caracteriza o contexto regional e deve ser confirmado em campo.")

    def geomorfologia(self):
        dist = self.ponderado("geomorfologia")
        if not dist:
            return None
        det = self.cam.get("geomorfologia", {}).get("classes", {})
        principal = next(iter(dist))
        x = det.get(principal, {})
        alts = [i["altitude_m"] for i in self.un.values() if i.get("altitude_m")]
        decl = self.ponderado("declividade")
        dom = [f"{k.split(' (')[0].lower()} ({br(v)}%)" for k, v in decl.items() if v >= 5]
        txt = (f"No contexto geomorfológico, o empreendimento insere-se predominantemente na unidade {principal}"
               + (f", pertencente à região {x.get('nm_regiao')}" if x.get("nm_regiao") else "")
               + (f" e ao domínio das {x.get('nm_dominio')}" if x.get("nm_dominio") else "")
               + (f", com formas de {x.get('forma')}" if x.get("forma") else "")
               + f" ({self.cita('ibge')}).")
        outras = [k for k in dist if k != principal and dist[k] >= 1]
        if outras:
            txt += f" Ocorre ainda a unidade {lista(outras)}."
        if alts:
            txt += (f" As altitudes ao longo das unidades variam de {min(a['min'] for a in alts)} m a "
                    f"{max(a['max'] for a in alts)} m ({self.cita('dem')}).")
        if dom:
            txt += (f" Quanto à declividade, predominam os relevos {lista(dom)}, segundo as classes de relevo da "
                    f"EMBRAPA ({self.cita('embrapa79')}).")
        return txt

    def geologia(self):
        lit = self.ponderado("litoestratigrafia")
        geo = self.ponderado("geologia")
        if not (lit or geo):
            return None
        det = self.cam.get("litoestratigrafia", {}).get("classes", {})
        partes = []
        for cl, pct in lit.items():
            if pct < 1:
                continue
            x = det.get(cl, {})
            idade = " ".join(v for v in (x.get("sistema_min"), x.get("era_min")) if v)
            hier = (x.get("hierarquia") or "unidade").lower()
            partes.append(f"{cl}" + (f" ({hier} do {idade})" if idade else "")
                          + (f", com litotipos de {x.get('litotipos').lower()}" if x.get("litotipos") else ""))
        txt = ""
        if partes:
            txt = f"Do ponto de vista geológico, as unidades do empreendimento assentam-se sobre {'; '.join(partes)} ({self.cita('sgb')})."
        if geo:
            txt += (f" No mapeamento geológico do IBGE (escala 1:250.000), a área corresponde às unidades "
                    f"{lista([k for k, v in geo.items() if v >= 1])} ({self.cita('ibge')}).")
        return txt.strip()

    def hidrogeologia(self):
        dist = self.ponderado("hidrogeologia")
        if not dist:
            return None
        det = self.cam.get("hidrogeologia", {}).get("classes", {})
        partes = []
        for cl, pct in dist.items():
            if pct < 1:
                continue
            x = det.get(cl, {})
            partes.append(f"unidade {cl}" + (f" (domínio {x.get('dom')}" + (f", subdomínio {x.get('subdom')}" if x.get("subdom") else "") + ")"
                                            if x.get("dom") else ""))
        return (f"Em termos hidrogeológicos, a área do empreendimento insere-se na {lista(partes)}, segundo o mapa de domínios "
                f"e subdomínios hidrogeológicos do Brasil ({self.cita('sgb')}).")

    def hidrologia(self):
        h = (self.dos or {}).get("hidrologia") or {}
        trav = sum(i.get("travessias", 0) for i in self.un.values())
        cursos = sorted({c for i in self.un.values() for c in (i.get("cursos_atravessados") or []) if "sem denominação" not in c})
        nasc = sum(i.get("nascentes_ate_100m", 0) for i in self.un.values())
        frases = []
        if h.get("uph"):
            frases.append(f"O empreendimento situa-se na Unidade de Planejamento Hídrico {h['uph']} ({self.cita('ana')})")
        for nome, x in (h.get("por_unidade") or {}).items():
            frases.append(f"o curso d'água nomeado mais próximo da unidade {nome} é o {x['rio_mais_proximo']}, a "
                          f"aproximadamente {br(x['distancia_m'], 0)} m")
        if trav:
            frases.append(f"o traçado das unidades lineares intercepta cursos d'água em {trav} pontos"
                          + (f", entre eles {lista(cursos)}" if cursos else ", em sua maioria cursos d'água sem denominação"))
        if nasc:
            frases.append(f"foram identificadas {nasc} nascentes a menos de 100 m das unidades")
        if not frases:
            return None
        txt = "; ".join(frases)
        return txt[0].upper() + txt[1:] + "."

    # ---------------------------------------------------------------- meio biótico
    def fitogeografia(self):
        orig = self.ponderado("fitogeografia")
        atual = self.ponderado("vegetacao")
        uso = self.ponderado("uso_solo_mapbiomas")
        if not (orig or atual):
            return None
        txt = ""
        if orig:
            txt = (f"De acordo com o mapeamento de vegetação do IBGE, a região do empreendimento pertence originalmente ao domínio "
                   f"da {lista([k for k, v in orig.items() if v >= 1])} ({self.cita('ibge')}).")
        if atual:
            txt += (f" Atualmente, a cobertura na área de intervenção é classificada como {lista([k.lower() for k, v in atual.items() if v >= 1])}, "
                    f"refletindo a ocupação antrópica da paisagem.")
        flo = uso.get("Formação Florestal")
        if flo:
            txt += f" Remanescentes de formação florestal ocupam cerca de {br(flo)}% da área de intervenção ({self.cita('mapbiomas')})."
        ame = []
        for reino, df in self.esp.items():
            if "ameaca_mma_148" in df:
                for r in df[df["ameaca_mma_148"].notna()].itertuples():
                    ame.append(f"{r.especie} ({r.ameaca_mma_148})")
        if ame:
            self.usados |= {"gbif", "mma148"}
            txt += (f" Entre os registros de ocorrência disponíveis no GBIF para o entorno, constam espécies da Lista Nacional de "
                    f"Espécies Ameaçadas (Portaria MMA nº 148/2022), como {lista(ame[:8])} (GBIF.ORG, 2026; BRASIL, 2022). "
                    f"Trata-se de registros secundários, que indicam ocorrência potencial e não substituem o levantamento de campo.")
        return txt.strip()

    def app(self):
        lin = {n: i["extensao_em_app_m"] for n, i in self.un.items() if i.get("extensao_em_app_m")}
        pol = {n: i["area_em_app_m2"] for n, i in self.un.items() if i.get("area_em_app_m2")}
        if "app" not in self.res:
            return None
        partes = [f"{n} ({br(v, 0)} m)" for n, v in lin.items()] + [f"{n} ({br(v, 0)} m²)" for n, v in pol.items()]
        base = (f"As Áreas de Preservação Permanente foram delimitadas conforme o art. 4º da Lei nº 12.651/2012, considerando "
                f"faixa de 30 m para cursos d'água com até 10 m de largura e raio de 50 m no entorno de nascentes ({self.cita('lei12651')}).")
        if not partes:
            return base + " Não foi identificada sobreposição das unidades com APP."
        return (base + f" Há sobreposição das unidades com APP em: {lista(partes)}, totalizando {br(sum(lin.values()), 0)} m de "
                f"unidades lineares e {br(sum(pol.values()), 0)} m² de unidades pontuais. A intervenção em APP por obra de "
                f"saneamento enquadra-se como de utilidade pública (art. 3º, VIII, b, da Lei nº 12.651/2012) e depende de autorização do órgão ambiental.")

    def erosao(self):
        nota_solo = {"R": 3, "C": 2.5, "P": 2.5, "N": 2, "L": 1, "G": 1, "O": 1}
        linhas = []
        for nome, info in self.un.items():
            solo = self.dominante(nome, "solos") or ""
            sig = solo.split(" ")[0]
            s = next((v for k, v in nota_solo.items() if sig.startswith(k)), None)
            dm = info.get("declividade_media_pct")
            if s is None or dm is None:
                continue
            d = 1 if dm < 8 else 2 if dm < 20 else 3
            n = (s + d) / 2
            classe = "alta" if n >= 2.5 or (s >= 2.5 and d >= 2) else "moderada" if n >= 1.5 else "baixa"
            linhas.append(f"{nome}: {classe} ({solo.split(' - ', 1)[-1]}, declividade média de {br(dm)}%)")
        if not linhas:
            return None
        return (f"A suscetibilidade à erosão foi avaliada qualitativamente pelo cruzamento das classes de solo ({self.cita('ibge')}) "
                f"com a declividade média de cada unidade, conforme as classes de relevo da EMBRAPA ({self.cita('embrapa79')}): "
                f"{'; '.join(linhas)}. Nas unidades de suscetibilidade moderada a alta, recomenda-se atenção especial a drenagem "
                f"provisória, proteção de taludes e recomposição imediata das áreas escavadas.")

    def alagadicos(self):
        un = [n for n, i in self.un.items() if (i.get("uso_solo_mapbiomas") or {}).get("Campo Alagado e Área Pantanosa")]
        if not un:
            return (f"No mapeamento de cobertura da terra não foram identificados campos alagados ou áreas pantanosas na área de "
                    f"intervenção ({self.cita('mapbiomas')}); a ocorrência de várzeas e a cota de inundação devem ser confirmadas em campo.")
        return (f"Foram identificadas manchas de campo alagado/área pantanosa na área de intervenção de {lista(un)} "
                f"({self.cita('mapbiomas')}), exigindo atenção quanto à cota de inundação e ao nível do lençol freático.")

    def supressao(self):
        tot, por = 0.0, []
        for nome, info in self.un.items():
            uso = info.get("uso_solo_mapbiomas") or {}
            nat = sum(v for k, v in uso.items() if k in NATURAL)
            ha = nat / 100 * self.area.get(nome, 0) / 1e4
            if ha >= 0.005:
                tot += ha
                por.append(f"{nome} ({br(ha, 2)} ha)")
        if not por:
            return ("Estimativa preliminar: não foi identificada vegetação natural na área de intervenção no mapeamento "
                    f"MapBiomas ({self.cita('mapbiomas')}); a necessidade de supressão deve ser confirmada em campo.")
        return (f"Estimativa preliminar de vegetação natural na área de intervenção (faixa de {2 * FAIXA_M} m nas unidades "
                f"lineares e área total nas pontuais), obtida do mapeamento MapBiomas ({self.cita('mapbiomas')}): "
                f"{lista(por)}, totalizando cerca de {br(tot, 2)} ha. O valor é indicativo e deve ser substituído pelo "
                f"levantamento/inventário florestal da área efetivamente suprimida.")

    # ---------------------------------------------------------------- socioeconômico / territórios
    def entorno(self):
        ent = (self.dos or {}).get("entorno") or {}
        rot = {"escola": ("escola", "escolas"), "saude": ("estabelecimento de saúde", "estabelecimentos de saúde"),
               "igreja": ("templo religioso", "templos religiosos"), "comercio": ("estabelecimento comercial", "estabelecimentos comerciais"),
               "cemiterio": ("cemitério", "cemitérios"), "edificacao": ("edificação", "edificações")}
        frases = []
        for nome, c in ent.items():
            if nome.startswith("_") or not isinstance(c, dict):
                continue
            itens = [f"{v['quantidade']} {rot[k][v['quantidade'] > 1]}"
                     + (f" ({lista(v['nomes'][:3])})" if v.get("nomes") else "") for k, v in c.items() if v.get("quantidade")]
            if itens:
                frases.append(f"no entorno de 500 m da unidade {nome}, constam {lista(itens)}")
        dist = [f"{n} ({'inserida na área urbana' if i['distancia_area_urbana_m'] < 50 else br(i['distancia_area_urbana_m'], 0) + ' m'})"
                for n, i in self.un.items() if i.get("distancia_area_urbana_m") is not None]
        if not frases and not dist:
            return None
        self.usados.add("osm")
        txt = ""
        if frases:
            txt = "Segundo a base colaborativa OpenStreetMap (OPENSTREETMAP, 2026), " + "; ".join(frases) + "."
        if dist:
            txt += f" A distância das unidades pontuais à área urbanizada mais próxima é de: {lista(dist)} ({self.cita('mapbiomas')})."
        return txt.strip() + " As informações devem ser confirmadas e complementadas com o registro fotográfico da vistoria de campo."

    def territorios(self):
        t = (self.dos or {}).get("territorios") or {}
        if not t:
            return None
        self.usados.add("funai")
        txt = ""
        if t.get("terras_indigenas"):
            p = t.get("ti_mais_proxima") or {}
            txt = (f"Foi identificada a Terra Indígena {lista(t['terras_indigenas'])} num raio de 10 km das unidades"
                   + (f", distante cerca de {br(p['distancia_km'])} km" if p.get("distancia_km") is not None else "")
                   + (f" (etnias {p.get('etnia_nome')}; situação: {str(p.get('fase_ti', '')).lower()})" if p.get("etnia_nome") else "")
                   + " (FUNAI, 2026). [A VERIFICAR: avaliar com o IAT a necessidade de manifestação da FUNAI.]")
        elif t.get("ti_mais_proxima"):
            p = t["ti_mais_proxima"]
            txt = (f"Não há terras indígenas num raio de 10 km das unidades; a mais próxima é a TI {p['nome']}, a cerca de "
                   f"{br(p['distancia_km'])} km (FUNAI, 2026).")
        else:
            txt = "Não foram identificadas terras indígenas num raio de 50 km das unidades (FUNAI, 2026)."
        return txt + " [A VERIFICAR: consulta ao INCRA/Fundação Cultural Palmares (quilombolas) e ao IPHAN (bens tombados).]"

    def ucs(self):
        t = (self.dos or {}).get("territorios") or {}
        u = t.get("unidades_conservacao")
        if u is None:
            return None
        if u:
            return (f"Foram identificadas as seguintes Unidades de Conservação na área de estudo: {lista(u)} ({self.cita('ana')}). "
                    f"[A VERIFICAR: zona de amortecimento e necessidade de autorização do órgão gestor.]")
        return (f"Não foram identificadas Unidades de Conservação federais, estaduais ou municipais na área do empreendimento e "
                f"em seu entorno imediato, segundo a base de Unidades de Conservação disponibilizada pela ANA ({self.cita('ana')}).")

    def impactos_especificos(self):
        itens = []
        ext = sum(i.get("extensao_em_app_m", 0) for i in self.un.values())
        trav = sum(i.get("travessias", 0) for i in self.un.values())
        if ext:
            itens.append(f"intervenção em APP em cerca de {br(ext, 0)} m de unidades lineares")
        if trav:
            itens.append(f"{trav} travessias de cursos d'água")
        t = (self.dos or {}).get("territorios") or {}
        if t.get("terras_indigenas"):
            itens.append(f"proximidade da Terra Indígena {lista(t['terras_indigenas'])}")
        ero = self.erosao() or ""
        if "alta" in ero:
            itens.append("trechos com suscetibilidade alta à erosão")
        sup = self.supressao() or ""
        if "totalizando" in sup:
            itens.append("possível supressão de vegetação nativa")
        if not itens:
            return None
        return (f"Considerando as características do empreendimento levantadas neste estudo, destacam-se como aspectos de maior "
                f"relevância ambiental: {lista(itens)}. Esses aspectos orientam as medidas de controle e mitigação apresentadas a seguir.")

    BLOCOS = ["pedologia", "uso_solo", "geomorfologia", "geologia", "hidrogeologia", "hidrologia", "fitogeografia", "app",
              "erosao", "alagadicos", "supressao", "entorno", "territorios", "ucs", "impactos_especificos"]

    def redigir(self):
        return {b: getattr(self, b)() for b in self.BLOCOS}


CHAVES_BIBLIO = {"lei12651": "norma-lei-12651-2012", "embrapa79": "embrapa-1979-sumula", "conama357": "conama-357-2005",
                 "osm": "openstreetmap", "funai": "funai-tis", "mma148": "brasil-portaria-mma-148-2022"}


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chave")
    a = ap.parse_args()
    cfg = projeto(a.chave)
    r = Redator(cfg)
    textos = r.redigir()
    d = cfg["dir"] / "dados"
    (d / "redacao.yaml").write_text(yaml.safe_dump({k: v for k, v in textos.items() if v}, allow_unicode=True,
                                                   sort_keys=False, width=10000), encoding="utf-8")
    md = [f"# Redação automática – {cfg['municipio']}\n", "Gerado por `ferramentas.redacao.redator` a partir dos dados do "
          "projeto. Revisar antes de protocolar; no texto entram como `{{auto.<bloco>}}`.\n"]
    md += [f"\n## {k}\n\n{v or '(sem dados para este bloco)'}" for k, v in textos.items()]
    (d / "REDACAO.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    # referências citadas pelo redator entram no projeto
    if "embrapa79" in r.usados and "embrapa-1979-sumula" not in biblio.catalogo():
        biblio.registrar("embrapa-1979-sumula", "EMBRAPA. Serviço Nacional de Levantamento e Conservação de Solos. Súmula da "
                         "10ª Reunião Técnica de Levantamento de Solos. Rio de Janeiro: EMBRAPA-SNLCS, 1979. 83 p.", "base",
                         None, "EMBRAPA, 1979", verificado=False)
    biblio.usar(cfg["chave"], [CHAVES_BIBLIO[k] for k in r.usados if k in CHAVES_BIBLIO and CHAVES_BIBLIO[k] in biblio.catalogo()])
    print("\n".join(md))


if __name__ == "__main__":
    main()
