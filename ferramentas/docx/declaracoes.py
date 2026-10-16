"""Gera as declarações e a certidão dos Anexos II a V da IN IAT 37/2025, pré-preenchidas.

Uso:
    python -m ferramentas.docx.declaracoes candoi [--lac]

Saída em projetos/<chave>/saida/declaracoes/:
    Anexo_II_Certidao_Uso_Solo.docx          para a Prefeitura assinar (dados do empreendimento já preenchidos)
    Anexo_III_Declaracao_Veracidade_RT.docx  declarante: responsável técnico (dados_comuns/equipe.yaml)
    Anexo_III_Declaracao_Veracidade_Sanepar.docx  declarante: representante da Sanepar
    Anexo_IV/V (somente com --lac)           Licença por Adesão e Compromisso: empreendedor e responsável técnico
Campos sem dado saem como "________" para completar à mão.
"""
import argparse
import datetime as dt

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

from ferramentas.util import console_utf8, projeto
from ferramentas.docx.montar import carregar_ficha

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]
LACUNA = "________________"


def v(x, alt=LACUNA):
    return str(x) if x not in (None, "") else alt


def _doc():
    d = docx.Document()
    s = d.sections[0]
    s.page_width, s.page_height = Cm(21), Cm(29.7)
    s.left_margin = s.right_margin = Cm(3)
    s.top_margin = s.bottom_margin = Cm(2.5)
    st = d.styles["Normal"]
    st.font.name, st.font.size = "Arial", Pt(12)
    st.paragraph_format.space_after = Pt(6)
    st.paragraph_format.line_spacing = 1.5
    return d


def _titulo(d, *linhas):
    for t in linhas:
        p = d.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run(t).bold = True
    d.add_paragraph()


def _par(d, texto, alinhar=WD_ALIGN_PARAGRAPH.JUSTIFY):
    p = d.add_paragraph(texto)
    p.alignment = alinhar
    return p


def _assinatura(d, nome, linha2):
    for _ in range(3):
        d.add_paragraph()
    for t in ("_______________________________________", nome, linha2):
        p = d.add_paragraph(t)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def _local_data(f):
    hoje = dt.date.today()
    return f"{f['municipio']} – {f.get('uf', 'PR')}, {hoje.day} de {MESES[hoje.month - 1]} de {hoje.year}."


def _qualificacao(p):
    """Texto de qualificação do declarante (nome em negrito vem separado)."""
    return (f", {v(p.get('nacionalidade'))}, {v(p.get('estado_civil'))}, {v(p.get('profissao') or p.get('cargo'))}, "
            f"portador(a) do CPF nº {v(p.get('cpf'))}, com Documento de Identidade nº {v(p.get('rg'))}, residente e "
            f"domiciliado(a) em {v(p.get('endereco'))}")


def atividade(f):
    return (f"{'Sistema de Abastecimento de Água' if f['sistema'] == 'SAA' else 'Sistema de Esgotamento Sanitário'} "
            f"({f['sistema']}) de {f['municipio']}/{f.get('uf', 'PR')} – CNAE {v(f.get('cnae'))}")


def certidao(f, destino):
    d = _doc()
    _titulo(d, "ANEXO II", "CERTIDÃO DO MUNICÍPIO QUANTO AO USO E OCUPAÇÃO DO SOLO")
    _par(d, f"Declaramos ao {(f.get('orgao') or {}).get('nome', 'órgão ambiental').upper()}, que o empreendimento abaixo descrito está localizado neste Município e "
            "que o Local, o Tipo de Empreendimento e Atividade estão em conformidade com a legislação municipal aplicável "
            "ao uso e ocupação do solo, bem como, atende às demais exigências legais e administrativas relacionadas ao Município.")
    s = f.get("empresa") or {}
    unid = "; ".join(u["nome"] for u in (f.get("unidades") or []))
    linhas = [("EMPREENDEDOR", v(s.get("razao_social"))), ("CNPJ/CPF", v(s.get("cnpj"))), ("ATIVIDADE", atividade(f)),
              ("LOCALIZAÇÃO", f"{v(f.get('endereco_unidade_principal'), '')} – Município de {f['municipio']}/{f.get('uf', 'PR')}. "
                              f"Unidades: {unid}".strip(" –")),
              ("LEGISLAÇÃO Nº", ""), ("ZONA/MACROZONA", ""), ("PERÍMETRO URBANO/ ZONA RURAL", ""),
              ("ENQUADRAMENTO DA ATIVIDADE PERMITIDA/PERMISSÍVEL", "")]
    t = d.add_table(rows=0, cols=2)
    t.style = "Table Grid"
    for a, b in linhas:
        c = t.add_row().cells
        c[0].text, c[1].text = a, b
        c[0].paragraphs[0].runs[0].bold = True
    d.add_paragraph()
    _par(d, f"{f['municipio']} – {f.get('uf', 'PR')}, ____ de ______________ de ______.", WD_ALIGN_PARAGRAPH.RIGHT)
    _assinatura(d, "Nome, assinatura e carimbo do Prefeito Municipal ou do Secretário de área", "")
    d.save(destino)


def veracidade(f, p, destino, quem):
    d = _doc()
    _titulo(d, "ANEXO III", "DECLARAÇÃO DA VERACIDADE DAS INFORMAÇÕES PRESTADAS")
    par = d.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    par.add_run(v(p.get("nome"))).bold = True
    doc_nome = {"MCE": "Memorial de Caracterização do Empreendimento (MCE)", "PCA": "Plano de Controle Ambiental (PCA)"}.get(
        f["documento"], f["documento"])
    par.add_run(_qualificacao(p) + ", DECLARO, para os devidos fins de direito, sob as penas da lei, que as informações "
                f"prestadas e documentos que apresento para o licenciamento ambiental junto ao {(f.get('orgao') or {}).get('nome', 'órgão ambiental')} do "
                f"{atividade(f)}, relacionados abaixo, são verdadeiros e autênticos (fiéis à verdade e condizentes com a "
                f"realidade dos fatos à época).")
    _par(d, "FATOS DECLARADOS:")
    _par(d, f"Informações técnicas e ambientais constantes do {doc_nome} do {atividade(f)}"
            + (", elaborado sob minha responsabilidade técnica." if quem == "rt" else f", apresentado pela {(f.get('empresa') or {}).get('razao_social', 'empreendedor')}."))
    _par(d, "DOCUMENTOS APRESENTADOS:")
    _par(d, f"{doc_nome} e respectivos anexos" + (f"; ART nº {v(f.get('responsavel_tecnico', {}).get('art'))}." if quem == "rt" else "."))
    _par(d, "Fico ciente através desse documento que a falsidade dessa declaração configura crime previsto no Código Penal "
            "Brasileiro, passível de apuração na forma da Lei bem como pode ser enquadrada como litigância de má-fé.")
    _par(d, "Nada mais a declarar, e ciente das responsabilidades das declarações prestadas, firmo a presente.")
    _par(d, _local_data(f), WD_ALIGN_PARAGRAPH.RIGHT)
    _assinatura(d, v(p.get("nome")), f"DECLARANTE – CPF: {v(p.get('cpf'))}")
    d.save(destino)


def lac(f, p, destino, quem):
    d = _doc()
    if quem == "empreendedor":
        _titulo(d, "ANEXO IV", "DECLARAÇÃO DO EMPREENDEDOR PELO LICENCIAMENTO POR ADESÃO E COMPROMISSO")
        corpo = ("Pelo presente instrumento, formalizo adesão e compromisso aos parâmetros técnicos estabelecidos pelo órgão "
                 "ambiental competente, assumindo responsabilidade pelo cumprimento de todas as normas legais vigentes e "
                 f"condicionantes estabelecidas na licença, com o intuito de licenciamento ambiental da atividade {atividade(f)} "
                 "através da Licença por Adesão e Compromisso (LAC), sob pena de sofrer as sanções legais cabíveis.")
        rodape = f"DECLARANTE – CPF ou CNPJ: {v(p.get('cpf'))}"
    else:
        _titulo(d, "ANEXO V", "DECLARAÇÃO DO RESPONSÁVEL TÉCNICO PELO LICENCIAMENTO POR ADESÃO E COMPROMISSO")
        corpo = ("Pelo presente instrumento, declaro ser responsável pelas informações prestadas sobre o empreendimento em "
                 "questão, assumindo a responsabilidade técnica pelas informações prestadas e pelo cumprimento de todas as "
                 f"normas legais vigentes, com o intuito de licenciamento ambiental da atividade de {atividade(f)} através da "
                 "Licença por Adesão e Compromisso (LAC), sob pena de sofrer as sanções legais cabíveis.")
        rodape = f"DECLARANTE – Nº DO REGISTRO NO CONSELHO DE CLASSE: {v(p.get('registro'))}"
    par = d.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    par.add_run(v(p.get("nome"))).bold = True
    par.add_run(_qualificacao(p) + ",")
    _par(d, corpo)
    _par(d, _local_data(f), WD_ALIGN_PARAGRAPH.RIGHT)
    _assinatura(d, v(p.get("nome")), rodape)
    d.save(destino)


def gerar(cfg, com_lac=False):
    f = carregar_ficha(cfg["dir"])
    f.setdefault("municipio", cfg["municipio"])
    f.setdefault("sistema", cfg["sistema"])
    f.setdefault("documento", cfg["documento"])
    equipe = f.get("equipe") or {}
    rt = {**(equipe.get("responsavel_tecnico") or {}), **{k: x for k, x in (f.get("responsavel_tecnico") or {}).items() if x}}
    rep = (f.get("empresa") or {}).get("representante") or equipe.get("representante_sanepar") or {}
    out = cfg["dir"] / "saida" / "declaracoes"
    out.mkdir(parents=True, exist_ok=True)
    arqs = [out / "Anexo_II_Certidao_Uso_Solo.docx", out / "Anexo_III_Declaracao_Veracidade_RT.docx",
            out / f"Anexo_III_Declaracao_Veracidade_{(f.get('empresa') or {}).get('sigla', 'Empreendedor')}.docx"]
    certidao(f, arqs[0])
    veracidade(f, rt, arqs[1], "rt")
    veracidade(f, rep, arqs[2], "empreendedor")
    if com_lac:
        arqs += [out / "Anexo_IV_Declaracao_LAC_Empreendedor.docx", out / "Anexo_V_Declaracao_LAC_RT.docx"]
        lac(f, rep, arqs[3], "empreendedor")
        lac(f, rt, arqs[4], "rt")
    faltam = [k for k in ("nome", "cpf", "rg", "registro") if not rt.get(k)]
    return arqs, faltam


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chave")
    ap.add_argument("--lac", action="store_true", help="gera também os Anexos IV e V (Licença por Adesão e Compromisso)")
    a = ap.parse_args()
    cfg = projeto(a.chave)
    if not cfg["orgao_info"].get("declaracoes"):
        raise SystemExit(f"O órgão {cfg['orgao']} não tem modelos de declaração cadastrados (orgao.yaml: declaracoes).")
    arqs, faltam = gerar(cfg, a.lac)
    for x in arqs:
        print(x)
    if faltam:
        print(f"Atenção: preencha em dados_comuns/equipe.yaml (responsavel_tecnico): {', '.join(faltam)}")


if __name__ == "__main__":
    main()
