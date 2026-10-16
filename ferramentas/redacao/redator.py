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
import re
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml

from ferramentas.util import console_utf8, projeto
from ferramentas.garimpo import biblio

CIT = {"ibge": "IBGE, 2023", "sgb": "SGB, [20--]", "mapbiomas": "PROJETO MAPBIOMAS, 2024", "dem": "EUROPEAN SPACE AGENCY, 2021",
       "ana": "ANA, [20--]", "lei12651": "BRASIL, 2012", "embrapa79": "EMBRAPA, 1979", "conama357": "BRASIL, 2005"}
NATURAL = {"Formação Florestal", "Formação Savânica", "Floresta Alagável", "Restinga Arbórea", "Campo Alagado e Área Pantanosa",
           "Formação Campestre", "Outras Formações não Florestais", "Mangue", "Restinga Herbácea"}
FAIXA_M = 15
AGUA = {"Rio, Lago e Oceano", "Aquicultura"}
# descrição resumida das classes da legenda do MapBiomas (Coleção 9) – citar (PROJETO MAPBIOMAS, 2024)
USO_DESC = {
    "Formação Florestal": "vegetação com predomínio de espécies arbóreas e formação de dossel contínuo",
    "Formação Campestre": "vegetação com predomínio de estrato herbáceo, com algumas arbustivas",
    "Silvicultura": "espécies arbóreas plantadas para fins comerciais, como pinus e eucalipto",
    "Pastagem": "áreas de pastagem, naturais ou plantadas, vinculadas à atividade agropecuária",
    "Mosaico de Usos": "áreas de uso agropecuário em que não é possível distinguir entre pastagem e agricultura",
    "Área Urbanizada": "áreas com significativa densidade de edificações e vias, incluindo áreas livres de construção e infraestrutura",
    "Rio, Lago e Oceano": "rios, lagos, represas, reservatórios e outros corpos d'água",
    "Soja": "áreas cultivadas com a cultura da soja",
    "Outras Lavouras Temporárias": "áreas ocupadas com cultivos agrícolas de curta ou média duração",
    "Campo Alagado e Área Pantanosa": "vegetação com influência fluvial, sujeita a alagamento periódico",
    "Outras Áreas não Vegetadas": "superfícies não permeáveis não mapeadas nas demais classes, como vias e solo exposto",
}


def br(v, c=1):
    return f"{v:,.{c}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def lista(itens):
    itens = [str(i) for i in itens if i]
    return "" if not itens else itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1]


def _abre(sujeito, texto):
    """Encaixa o texto da Embrapa numa frase sobre a classe: 'Classes dos X...' -> 'Os Y correspondem às classes
    dos X...'; 'Apresentam...' -> 'Os Y apresentam...'; frases que já citam a classe ficam como estão."""
    texto = texto.strip()
    if texto.lower().startswith(("a classe", "os ", "as ", sujeito.lower())):
        return texto.rstrip(".")
    art = "As" if sujeito.split()[0].endswith("as") else "Os"
    if texto.startswith("Classes ") or texto.startswith("Classe "):
        return f"{art} {sujeito} correspondem às {texto[0].lower() + texto[1:]}".rstrip(".")
    return f"{art} {sujeito} {texto[0].lower() + texto[1:]}".rstrip(".")


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

    def felipe(self, tema):
        """Classes confirmadas da legenda do mapa do Felipe (dados/mapas_felipe.yaml) – prevalecem sobre a base pública."""
        if not hasattr(self, "_felipe"):
            arq = self.cfg["dir"] / "dados" / "mapas_felipe.yaml"
            self._felipe = _ler(arq) or {}
        cl = (self._felipe.get(tema) or {}).get("classes")
        return [c for c in cl if c] if cl else None

    def classes(self, campo, minimo=1):
        """Classes presentes (sem percentuais: os números ficam com os mapas do Felipe)."""
        return [k for k, v in self.ponderado(campo).items() if v >= minimo]

    def aguas(self):
        """Bacia, unidade hidrográfica, aquífero e formação de cada unidade + textos oficiais (garimpo.aguas_pr)."""
        if not hasattr(self, "_aguas"):
            from ferramentas.garimpo import aguas_pr
            try:
                self._aguas = aguas_pr.para_projeto(self.cfg["chave"])
            except Exception as e:
                print(f"  (fontes oficiais de águas/geologia do PR indisponíveis: {e.__class__.__name__})")
                self._aguas = {}
        return self._aguas

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
        fel = self.felipe("solos")
        if fel:
            nomes = [c.split(" - ", 1)[-1] for c in fel]
            texto = (f"Conforme o mapa pedológico da área do empreendimento (@fig:solos), ocorrem as seguintes classes de "
                     f"solo: {lista(nomes)}.")
            classes = fel
        else:
            dist = self.classes("solos")
            if not dist:
                return None
            det = self.cam.get("solos", {}).get("classes", {})
            partes = []
            for cl in dist:
                if cl.lower().startswith("área urbana"):
                    partes.append("área urbana sem mapeamento pedológico")
                    continue
                x = det.get(cl, {})
                carac = "; ".join(f"{k} {' '.join(str(v).split())}" for k, v in (("relevo", x.get("relevo")),
                                                                                  ("textura", x.get("textura"))) if v)
                partes.append(f"{cl.split(' - ', 1)[-1]}" + (f" ({carac})" if carac else ""))
            texto = (f"De acordo com o mapeamento pedológico do IBGE, em escala 1:250.000, ocorrem na região do "
                     f"empreendimento as seguintes classes de solo: {lista(partes)} ({self.cita('ibge')}).")
            classes = [c for c in dist if not c.lower().startswith("área urbana")]
        carac = self._solos_embrapa(classes)
        return texto + ("\n\n" + carac if carac else "")

    def _solos_embrapa(self, classes):
        """Características de cada classe nas páginas técnicas da Embrapa (Ageitec/SiBCS) – garimpo.solos."""
        from ferramentas.garimpo import solos
        try:
            self.solos_emb = solos.para_projeto(self.cfg["chave"], classes)
        except Exception as e:
            print(f"  (Embrapa/Ageitec indisponível: {e.__class__.__name__}; características das classes ficam de fora)")
            self.solos_emb = []
            return None
        achadas = [s for s in self.solos_emb if s.get("encontrada")]
        if not achadas:
            return None
        pars = ["As características gerais de cada classe, descritas a seguir, foram obtidas junto ao Sistema Brasileiro "
                "de Classificação de Solos (SiBCS), por meio das páginas técnicas da Agência de Informação Tecnológica "
                "(Ageitec) da Embrapa."]
        vistas = set()
        for s in achadas:
            cit = s["citacao"]
            if s["url"] not in vistas:
                vistas.add(s["url"])
                pars.append(f"{_abre(s['pagina'], ' '.join(s['intro']))} ({cit}).")
            if s.get("grande_grupo"):
                desc = s["grande_grupo_desc"].rstrip(".")
                verbo = "que correspondem a" if desc.lower().startswith("solos") else "que apresentam"
                pars.append(f"No terceiro nível categórico, a classe mapeada pertence ao grande grupo dos {s['pagina']} "
                            f"{s['grande_grupo']}, {verbo} {desc[0].lower() + desc[1:]} ({cit}).")
        return "\n\n".join(pars)

    def pedologia_fotos(self):
        """Fotos de perfil das classes (Acervo da Embrapa Solos), depois do mapa de solos."""
        fotos, vistas = [], set()
        for s in getattr(self, "solos_emb", []) or []:
            if s.get("foto") and s["foto"] not in vistas:
                vistas.add(s["foto"])
                fotos.append(f"![{s['foto_legenda']}]({s['foto']}){{#fig:perfil-{len(fotos) + 1} "
                             f"fonte=\"{s['foto_fonte']}\" largura=7}}")
        return "\n\n".join(fotos) or None

    def uso_solo(self):
        fel = self.felipe("uso_solo")
        if fel:
            classes, origem = fel, "Conforme o mapa de uso e cobertura do solo (@fig:uso-solo), ocorrem na área do empreendimento"
        else:
            classes = self.classes("uso_solo_mapbiomas")
            if not classes:
                return None
            origem = ("Segundo o mapeamento de cobertura e uso da terra do Projeto MapBiomas (Coleção 9), ocorrem na área do "
                      "empreendimento e em seu entorno")
        cit = "" if fel else f" ({self.cita('mapbiomas')})"
        txt = f"{origem} as seguintes classes: {lista([c.lower() for c in classes])}{cit}."
        nat = [c for c in classes if c in NATURAL]
        antr = [c for c in classes if c not in NATURAL and c not in AGUA]
        if nat and antr:
            txt += (" A paisagem combina formações naturais e usos antrópicos, refletindo a ocupação histórica da região.")
        elif antr:
            txt += " A paisagem é dominada por usos antrópicos."
        desc = [f"{c.lower()} – {USO_DESC[c]}" for c in classes if c in USO_DESC]
        if desc:
            txt += (" Segundo a legenda do Projeto MapBiomas, as classes correspondem a: " + "; ".join(desc)
                    + f" ({self.cita('mapbiomas')}).")
        return txt + " O uso do solo deve ser confirmado na vistoria de campo."

    def geomorfologia(self):
        """Atlas Geomorfológico do Paraná (subunidade de cada unidade, texto do planalto e da subunidade) +
        unidade do IBGE + relevo qualitativo. Com o mapa do Felipe confirmado, usa as classes da legenda dele."""
        import re as _re
        from ferramentas.garimpo import geomorfologia_pr as gpr
        pr = None
        try:
            pr = gpr.para_projeto(self.cfg["chave"])
        except Exception as e:
            print(f"  (Atlas Geomorfológico do Paraná indisponível: {e.__class__.__name__})")
        cit = gpr.CIT
        pars = []
        fel = self.felipe("geomorfologia")
        subs = (pr or {}).get("subunidades") or []
        if fel:
            # classes do mapa do Felipe; descrição do atlas quando o nome coincidir
            pars.append(f"Conforme o mapa geomorfológico (@fig:geomorfologia), a área do empreendimento insere-se nas "
                        f"seguintes unidades: {lista(fel)}.")
            subs = [s for s in subs if any(s["nome"] and s["nome"].lower() in c.lower() for c in fel)]
        if subs:
            if not fel:
                s0 = subs[0]
                morfo = {"1": "Cinturão Orogênico do Atlântico", "2": "Bacia Sedimentar do Paraná",
                         "3": "Bacias Sedimentares Cenozóicas e Depressões Tectônicas"}.get(s0["codigo"][0])
                nomes = [f"{s['nome']} ({s['codigo']})" for s in subs]
                pars.append(f"Segundo o Atlas Geomorfológico do Estado do Paraná ({cit}), o empreendimento insere-se na "
                            f"unidade morfoestrutural {morfo}"
                            + (f", unidade morfoescultural {s0['unidade']}" if s0.get("unidade") else "")
                            + f", {'subunidades morfoesculturais' if len(subs) > 1 else 'subunidade morfoescultural'} "
                            + f"{lista(nomes)}.")
            for un, tx in ((pr or {}).get("planaltos") or {}).items():
                if tx:
                    pars.append(f"{tx if tx.endswith('s.n.m.') else tx.rstrip('.')} ({cit}).")
            for s in subs:
                tx = s.get("texto") or ""
                # tira as estatísticas da folha 1:250.000 (área da subunidade na folha) e reescreve o início
                tx = _re.sub(r",? e ocupa uma área de [\d.,]+ km²,? que corresponde a [\d.,]+ ?% desta Folha", "", tx)
                tx = _re.sub(r" (?:em|de) (?:uma área|um total)(?: total)? de [\d.,]+ km ?2?²?", "", tx)
                tx = _re.sub(r"^A sub-unidade morfoescultural número [\d.]+, denominada (.+?), situada no ([^,]+), ",
                             r"A subunidade \1, situada no \2, ", tx)
                tx = tx.replace("altitutudes", "altitudes").replace("m. s. n. m.", "m.").replace("m.. ", "m. ")
                tx = _re.sub(r" \(metros sobre o nível do mar\)", "", tx)
                un_proj = s.get("unidades_projeto") or []
                pars.append(tx.rstrip(".") + f" ({cit}). Nessa subunidade "
                            + ("situam-se as unidades " if len(un_proj) > 1 else "situa-se a unidade ") + f"{lista(un_proj)}.")
        # IBGE (BDiA) como complemento, sem números
        dist = self.classes("geomorfologia")
        if dist and not fel:
            det = self.cam.get("geomorfologia", {}).get("classes", {})
            x = det.get(dist[0], {})
            pars.append(f"No mapeamento geomorfológico do IBGE, em escala 1:250.000, a área corresponde à unidade {dist[0]}"
                        + (f", da região {x.get('nm_regiao')}" if x.get("nm_regiao") else "")
                        + (f", com formas de {x.get('forma')}" if x.get("forma") else "")
                        + f" ({self.cita('ibge')}).")
        relevo = [k.split(" (")[0].lower() for k in self.classes("declividade", minimo=15)]
        if relevo:
            pars.append(f"Localmente, o relevo apresenta-se predominantemente {lista(relevo)}, segundo as classes de relevo da "
                        f"EMBRAPA ({self.cita('embrapa79')}), conforme os mapas de altimetria e declividade.")
        return "\n\n".join(pars) or None

    def geologia(self):
        ag = self.aguas()
        cit = (ag.get("citacoes") or {}).get("carta", "BRASIL, 2015")
        lit = self.ponderado("litoestratigrafia")
        geo = self.ponderado("geologia")
        det = self.cam.get("litoestratigrafia", {}).get("classes", {})
        pars = []
        fel = self.felipe("geologia")
        if fel:
            pars.append(f"Conforme o mapa geológico (@fig:geologia), a área do empreendimento assenta-se sobre: {lista(fel)}.")
        principais = [cl for cl, pct in lit.items() if pct >= 1]
        sgb = ag.get("formacoes_sgb") or {}
        if principais and not fel:
            x = {**det.get(principais[0], {}), **(sgb.get(principais[0]) or {})}
            idade = " ".join(v for v in (x.get("sistema_min"), x.get("epoca_min")) if v)
            era = (x.get("era_min") or "").replace("ó", "o").replace("Mesozoico", "Mesozoica").replace("Paleozoico", "Paleozoica")                 .replace("Cenozoico", "Cenozoica").replace("Neoproterozoico", "Neoproterozoica")
            pais = x.get("nome_pai")
            pars.append(f"Do ponto de vista geológico, as unidades do empreendimento assentam-se sobre o {principais[0]}"
                        + (f", do {idade}" + (f" (Era {era})" if era else "") if idade else "")
                        + (f", integrante do {pais.split(' - ', 1)[-1]}" if pais else "")
                        + (", na Bacia Sedimentar do Paraná" if x.get("era_min") in ("Mesozóico", "Paleozóico") else "")
                        + (f", com litotipos de {x['litotipos'].lower()}" if x.get("litotipos") else "")
                        + f" ({self.cita('sgb')}).")
            if len(principais) > 1:
                pars[-1] += f" Ocorre ainda {lista(principais[1:])} ({self.cita('sgb')})."
        for cl in principais[:2]:
            leg = ((sgb.get(cl) or {}).get("legenda") or (det.get(cl, {}) or {}).get("legenda") or "")
            leg = re.split(r"\s\d{2,3},\d ?± ?|\s{2,}", leg)[0].strip().rstrip(".")  # sem as datações radiométricas
            if leg:
                pars.append(f"Segundo o Serviço Geológico do Brasil, o {cl} corresponde a uma "
                            f"{leg[0].lower() + leg[1:]} ({self.cita('sgb')}).")
        for f, frases in (ag.get("formacoes") or {}).items():
            if frases:
                txt = " ".join(frases[:6]).rstrip(".")
                pars.append(f"No Paraná, {txt[0].lower() + txt[1:]} ({cit}).")
        if geo and not fel:
            pars.append(f"No mapeamento geológico do IBGE, em escala 1:250.000, a área corresponde às unidades "
                        f"{lista([k for k, v in geo.items() if v >= 1])} ({self.cita('ibge')}).")
        return "\n\n".join(pars) or None

    def hidrogeologia(self):
        ag = self.aguas()
        cits = ag.get("citacoes") or {}
        pars = []
        fel = self.felipe("hidrogeologia")
        if fel:
            pars.append(f"Conforme o mapa hidrogeológico (@fig:hidrogeologia), a área do empreendimento insere-se em: {lista(fel)}.")
        dist = self.ponderado("hidrogeologia")
        det = self.cam.get("hidrogeologia", {}).get("classes", {})
        partes = []
        for cl, pct in dist.items():
            if pct < 1:
                continue
            x = det.get(cl, {})
            partes.append(f"unidade {cl}" + (f" (domínio {x.get('dom')}" + (f", subdomínio {x.get('subdom')}" if x.get("subdom") else "") + ")"
                                            if x.get("dom") else ""))
        if partes and not fel:
            pars.append(f"Em termos hidrogeológicos, a área do empreendimento insere-se na {lista(partes)}, segundo o mapa de "
                        f"domínios e subdomínios hidrogeológicos do Brasil ({self.cita('sgb')}).")
        for aq, x in (ag.get("aquiferos") or {}).items():
            iat = ", ".join(x.get("unidade_iat") or [])
            pars.append(f"No mapeamento das unidades aquíferas do Paraná, o empreendimento situa-se na unidade {iat or aq} "
                        f"({cits.get('iat', 'IAT, [2020]')}), correspondente ao Aquífero {aq} descrito na Carta das Águas "
                        f"Subterrâneas do Paraná ({cits.get('carta', 'BRASIL, 2015')}).")
            if x.get("hidrodinamica"):
                pars.append(" ".join(x["hidrodinamica"]).rstrip(".") + f" ({cits.get('carta', 'BRASIL, 2015')}).")
            if x.get("vulnerabilidade"):
                pars.append("Quanto à vulnerabilidade natural à contaminação, " + (lambda s: s[0].lower() + s[1:])(
                    " ".join(x["vulnerabilidade"]).rstrip(".")) + f" ({cits.get('carta', 'BRASIL, 2015')}).")
            if x.get("sanepar"):
                pars.append("No abastecimento público, " + (lambda s: s[0].lower() + s[1:])(x["sanepar"].rstrip("."))
                            + f" ({cits.get('mendes', 'MENDES et al., 2002')}).")
        return "\n\n".join(pars) or None

    def hidrologia(self):
        ag = self.aguas()
        cits = ag.get("citacoes") or {}
        h = (self.dos or {}).get("hidrologia") or {}
        pars = []
        rh = {"Litorânea": ("Atlântico Sul", "2,9%"), "Ribeira": ("Atlântico Sudeste", "4,9%")}
        for bacia, x in (ag.get("bacias") or {}).items():
            uhs = [u.title().replace(" Do ", " do ").replace(" Dos ", " dos ").replace(" Da ", " da ")
                   for u in x.get("unidades_hidrograficas") or []]
            reg, pct = rh.get(bacia, ("Paraná", "92,2%"))
            pars.append(f"O empreendimento situa-se na Bacia Hidrográfica do Rio {bacia}"
                        + (f", que ocupa {x['area_km2_carta']} km² do território paranaense ({cits.get('carta')})"
                           if x.get("area_km2_carta") else "")
                        + (f", na Unidade Hidrográfica {lista(uhs)}, conforme a divisão estabelecida pela Resolução CERH/PR "
                           f"nº 49/2006 ({cits.get('iat')})" if uhs else "")
                        + f". Quanto às regiões hidrográficas nacionais (Resolução CNRH nº 32/2003), a bacia integra a Região "
                        f"Hidrográfica do {reg}, que abrange {pct} do território paranaense ({cits.get('carta')})"
                        + (f", e, na divisão da Agência Nacional de Águas e Saneamento Básico, a Unidade de Planejamento "
                           f"Hídrico {h['uph']} ({self.cita('ana')})" if h.get("uph") else "") + ".")
        trav = sum(i.get("travessias", 0) for i in self.un.values())
        cursos = sorted({c for i in self.un.values() for c in (i.get("cursos_atravessados") or []) if "sem denominação" not in c})
        nasc = sum(i.get("nascentes_ate_100m", 0) for i in self.un.values())
        frases = []
        rios = {}
        for nome, x in (h.get("por_unidade") or {}).items():
            rios.setdefault(x["rio_mais_proximo"], []).append(nome)
        for rio, un in rios.items():
            frases.append(f"o curso d'água nomeado mais próximo {'das unidades' if len(un) > 1 else 'da unidade'} "
                          f"{lista(un)} é o {rio}")
        if trav:
            frases.append("o traçado das unidades lineares intercepta cursos d'água"
                          + (f", entre eles {lista(cursos)}" if cursos else ", em sua maioria sem denominação"))
        if nasc:
            frases.append("há nascentes nas proximidades das unidades")
        if frases:
            txt = "; ".join(frases)
            pars.append("Em escala local, " + txt + f" ({self.cita('ana')}), conforme o mapa de bacia hidrográfica.")
        return "\n\n".join(pars) or None

    def fitogeografia(self):
        orig = self.ponderado("fitogeografia")
        atual = self.ponderado("vegetacao")
        uso = self.ponderado("uso_solo_mapbiomas")
        if not (orig or atual):
            return None
        txt = ""
        fel = self.felipe("fitogeografia")
        if fel:
            txt = (f"Conforme o mapa de enquadramento fitogeográfico (@fig:fitogeografia), a região do empreendimento "
                   f"pertence originalmente ao domínio da {lista(fel)}.")
        elif orig:
            txt = (f"De acordo com o mapeamento de vegetação do IBGE, a região do empreendimento pertence originalmente ao domínio "
                   f"da {lista([k for k, v in orig.items() if v >= 1])} ({self.cita('ibge')}).")
        if atual:
            txt += (f" Atualmente, a cobertura na área de intervenção é classificada como {lista([k.lower() for k, v in atual.items() if v >= 1])}, "
                    f"refletindo a ocupação antrópica da paisagem.")
        if uso.get("Formação Florestal"):
            txt += f" Há remanescentes de formação florestal na área do empreendimento e em seu entorno ({self.cita('mapbiomas')})."
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
        partes = list(lin) + list(pol)
        base = (f"As Áreas de Preservação Permanente foram delimitadas conforme o art. 4º da Lei nº 12.651/2012, considerando "
                f"faixa de 30 m para cursos d'água com até 10 m de largura e raio de 50 m no entorno de nascentes ({self.cita('lei12651')}).")
        if not partes:
            return base + " Não foi identificada sobreposição das unidades com APP."
        return (base + f" Há sobreposição com APP nas unidades {lista(partes)}, conforme a @fig:app. A intervenção em APP por obra de "
                f"saneamento enquadra-se como de utilidade pública (art. 3º, VIII, b, da Lei nº 12.651/2012) e depende de autorização do órgão ambiental.")

    def app_metodo(self):
        """Como a APP/RL foi delimitada – só cita o CAR se os shapes estiverem em dados/car/."""
        from ferramentas.geo.mapas import tem_car
        d = self.cfg["dir"] / "dados"
        cliente = [p for p in d.glob("*.gpkg") if "rio" in p.stem.lower() and "nascente" not in p.stem.lower()]
        hidro = ("na hidrografia fornecida pela Sanepar" if cliente else
                 f"na hidrografia da Base Cartográfica Contínua do Brasil, escala 1:250.000 – BC250 ({self.cita('ibge')})")
        if tem_car(self.cfg):
            return (f"A delimitação das Áreas de Preservação Permanente (APP) e da Reserva Legal foi realizada com base "
                    f"{hidro}, nas informações constantes no Cadastro Ambiental Rural (SICAR) dos imóveis atravessados e "
                    f"nos critérios da Lei nº 12.651/2012 ({self.cita('lei12651')}), sendo apresentada na @fig:app.")
        return (f"A delimitação das Áreas de Preservação Permanente (APP) foi realizada com base {hidro} e nos critérios "
                f"do art. 4º da Lei nº 12.651/2012 ({self.cita('lei12651')}), sendo apresentada na @fig:app. "
                f"[A VERIFICAR: Reserva Legal – baixar no SICAR os shapes do CAR dos imóveis atravessados para dados/car/ "
                f"e regenerar o mapa e o texto.]")

    def app_titulo(self):
        from ferramentas.geo.mapas import tem_car
        return ("Reservas Legais e Áreas de Preservação Permanente do empreendimento" if tem_car(self.cfg)
                else "Áreas de Preservação Permanente no entorno do empreendimento")

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
            relevo = "plano a suave ondulado" if dm < 8 else "ondulado" if dm < 20 else "forte ondulado ou mais declivoso"
            linhas.append(f"{nome}: {classe} ({solo.split(' - ', 1)[-1]}, relevo {relevo})")
        if not linhas:
            return None
        return (f"A suscetibilidade à erosão foi avaliada qualitativamente pelo cruzamento das classes de solo ({self.cita('ibge')}) "
                f"com o relevo de cada unidade, conforme as classes de relevo da EMBRAPA ({self.cita('embrapa79')}): "
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
        por = [nome for nome, info in self.un.items()
               if sum(v for k, v in (info.get("uso_solo_mapbiomas") or {}).items() if k in NATURAL) >= 1]
        if not por:
            return ("Não foi identificada vegetação natural na área de intervenção no mapeamento MapBiomas "
                    f"({self.cita('mapbiomas')}); a necessidade de supressão deve ser confirmada em campo.")
        return (f"O mapeamento MapBiomas indica vegetação natural na área de intervenção de {lista(por)} "
                f"({self.cita('mapbiomas')}). A área de supressão deve ser quantificada pelo levantamento/inventário florestal "
                f"da área efetivamente afetada.")

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
        dist = [f"{n} ({'inserida na área urbana' if i['distancia_area_urbana_m'] < 50 else 'fora da área urbana'})"
                for n, i in self.un.items() if i.get("distancia_area_urbana_m") is not None]
        if not frases and not dist:
            return None
        self.usados.add("osm")
        txt = ""
        if frases:
            txt = "Segundo a base colaborativa OpenStreetMap (OPENSTREETMAP, 2026), " + "; ".join(frases) + "."
        if dist:
            txt += f" Quanto à inserção urbana das unidades pontuais: {lista(dist)} ({self.cita('mapbiomas')})."
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
            itens.append("intervenção em APP pelas unidades lineares")
        if trav:
            itens.append("travessias de cursos d'água")
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

    def acessos(self):
        """Alternativas de acesso por unidade (ferramentas.geo.acessos: OSRM + OpenStreetMap), com figura."""
        arq = self.cfg["dir"] / "dados" / "acessos.yaml"
        if not arq.exists():
            return None
        return (yaml.safe_load(arq.read_text(encoding="utf-8")) or {}).get("texto")

    def socio(self):
        """3.7.1 Residências e entorno no padrão do MCE de Entre Rios (ferramentas.geo.socio)."""
        arq = self.cfg["dir"] / "dados" / "socio.yaml"
        if not arq.exists():
            try:
                from ferramentas.geo import socio
                socio.gerar(self.cfg["chave"])
            except Exception as e:
                print(f"  (socioeconômico não gerado: {e.__class__.__name__})")
                return None
        return (yaml.safe_load(arq.read_text(encoding="utf-8")) or {}).get("texto")

    BLOCOS = ["acessos", "socio", "pedologia", "pedologia_fotos", "uso_solo", "geomorfologia", "geologia", "hidrogeologia", "hidrologia", "fitogeografia", "app_metodo", "app_titulo", "app",
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
