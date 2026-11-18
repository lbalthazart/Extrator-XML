import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import os
import sys
import re
from decimal import Decimal, ROUND_HALF_EVEN

# ==============================================================================
# MOTOR DE ARREDONDAMENTO E CÁLCULO OFICIAL DA RECEITA FEDERAL (LC 214/2025)
# Baseado na classe ArredondamentoUtils e regras da Calculadora RTC
# ==============================================================================

# Precisão intermediária oficial da Receita Federal: 8 casas decimais
PRECISAO_INTERNA = Decimal('0.00000001')
PRECISAO_MOEDA = Decimal('0.01')
PRECISAO_ALIQUOTA = Decimal('0.0001')

CST_IBS_CBS_DESCRICAO = {
    "000": "Tributação integral",
    "010": "Tributação com alíquotas uniformes (FGTS / Setor financeiro)",
    "011": "Tributação com alíquotas uniformes reduzidas",
    "200": "Tributação com redução de alíquota / Alíquota zero",
    "220": "Alíquota fixa",
    "221": "Alíquota fixa proporcional",
    "222": "Redução de Base de Cálculo",
    "400": "Isenção",
    "410": "Imunidade e não incidência",
    "510": "Diferimento",
    "550": "Suspensão",
    "620": "Tributação monofásica",
    "800": "Transferência de crédito",
    "810": "Ajustes",
    "820": "Tributação em declaração de regime específico",
    "830": "Exclusão de base de cálculo"
}

CST_IS_DESCRICAO = {
    "000": "Tributado com Imposto Seletivo",
    "100": "Imunidade",
    "200": "Não ocorrência do Fato Gerador",
    "300": "Devolução",
    "400": "Suspensão",
    "500": "Alíquota Zero",
    "600": "Isenção"
}

def to_decimal(val, default='0.00'):
    """Converte valores com segurança para Decimal com vírgula ou ponto."""
    if val is None:
        return Decimal(default)
    if isinstance(val, (int, float, Decimal)):
        return Decimal(str(val))
    val_str = str(val).strip().replace(',', '.')
    if not val_str:
        return Decimal(default)
    try:
        return Decimal(val_str)
    except Exception:
        return Decimal(default)

def format_moeda(dec_val):
    """Formata Decimal em moeda no padrão brasileiro (ex: 1.250,50)."""
    try:
        d = dec_val.quantize(PRECISAO_MOEDA, rounding=ROUND_HALF_EVEN)
        return f"{d:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except Exception:
        return "0,00"

def format_moeda_raw(dec_val):
    """Formata Decimal com ponto para leitura direta técnica (ex: 1250.50)."""
    try:
        d = dec_val.quantize(PRECISAO_MOEDA, rounding=ROUND_HALF_EVEN)
        return f"{d:.2f}"
    except Exception:
        return "0.00"

def format_datasul(val):
    """
    Formata valor para digitação no TOTVS Datasul:
    - Com vírgula para decimais (ex: 1250,50 ou 18,00)
    - Sem ponto de milhar para evitar conflitos com a máscara de campo do Progress/Datasul
    """
    if val is None or val == '' or val == '-':
        return "-"
    try:
        d = to_decimal(val).quantize(PRECISAO_MOEDA, rounding=ROUND_HALF_EVEN)
        return f"{d:.2f}".replace('.', ',')
    except Exception:
        return str(val).replace('.', ',')

def format_datasul_aliq(val):
    """Formata alíquota com vírgula para o Datasul (ex: 18,00 ou 0,90)."""
    if val is None or val == '' or val == '-':
        return "-"
    try:
        d = to_decimal(val)
        return f"{d}".replace('.', ',')
    except Exception:
        return str(val).replace('.', ',')

def format_datasul_qtd(val):
    """Formata quantidade sem ponto de milhar e com vírgula."""
    if val is None or val == '' or val == '-':
        return "-"
    try:
        d = to_decimal(val)
        s = f"{d:.4f}".rstrip('0').rstrip('.')
        return s.replace('.', ',') if s else "0"
    except Exception:
        return str(val).replace('.', ',')

def calcular_base_unificada_rtc_oficial(vProd, vFrete, vSeg, vOutro, vII, vIS, vDesc, vICMS, vPIS, vCOFINS, vFCP, vISS, ano=2026):
    """
    Calcula a Base de Cálculo Unificada do IBS/CBS segundo a Lei Complementar 214/2025 (Art. 349)
    e a especificação oficial da Receita Federal (BaseCalculoUnificadaService / ElementoBaseCalculo):
    
    INTEGRAM (Somam):
      - vProd (Valor dos produtos)
      - vFrete (Frete)
      - vSeg (Seguro)
      - vOutro (Outras despesas acessórias)
      - vII (Imposto de Importação)
      - vIS (Imposto Seletivo - a partir de 2027 ou se destacado)
      
    NÃO INTEGRAM (Subtraem na transição 2026-2032):
      - vDesc (Desconto incondicional)
      - vPIS e vCOFINS (no ano de transição 2026)
      - vICMS, vFCP, vISS (durante toda a transição 2026 a 2032)
    """
    integra = to_decimal(vProd) + to_decimal(vFrete) + to_decimal(vSeg) + to_decimal(vOutro) + to_decimal(vII)
    if ano >= 2027 or to_decimal(vIS) > 0:
        integra += to_decimal(vIS)

    nao_integra = to_decimal(vDesc)
    if ano == 2026:
        nao_integra += to_decimal(vPIS) + to_decimal(vCOFINS)
    if ano <= 2032:
        nao_integra += to_decimal(vICMS) + to_decimal(vFCP) + to_decimal(vISS)

    base = max(Decimal('0'), integra - nao_integra)
    return base.quantize(PRECISAO_MOEDA, rounding=ROUND_HALF_EVEN)

def calcular_tributo_rtc_oficial(base_calc, aliq_nominal, red_aliq=Decimal('0'), aliq_efet_xml=None, v_dif=None, p_dif=None):
    """
    Executa o cálculo oficial de IBS ou CBS segundo a LC 214/2025 e o motor oficial RTC (Receita Federal):
    1. Se pAliqEfet já estiver explicitada no XML, ela é utilizada;
       caso contrário: Alíquota Efetiva = Alíquota Nominal * (1 - pRedAliq / 100) (8 casas decimais, ROUND_HALF_EVEN)
    2. Tributo Calculado = Base * (Alíquota Efetiva / 100) (2 casas decimais, ROUND_HALF_EVEN)
    3. Diferimento (gDif): Se houver vDif ou pDif, subtrai o diferimento para obter o Tributo Devido.
    """
    base = to_decimal(base_calc)
    aliq_nom = to_decimal(aliq_nominal)
    red = to_decimal(red_aliq)

    if aliq_efet_xml is not None and to_decimal(aliq_efet_xml) > 0:
        aliq_efetiva = to_decimal(aliq_efet_xml)
    else:
        fator_red = Decimal('1') - (red / Decimal('100'))
        aliq_efetiva = (aliq_nom * fator_red).quantize(PRECISAO_INTERNA, rounding=ROUND_HALF_EVEN)

    tributo_calculado = (base * (aliq_efetiva / Decimal('100'))).quantize(PRECISAO_MOEDA, rounding=ROUND_HALF_EVEN)

    if v_dif is not None and to_decimal(v_dif) > 0:
        tributo_devido = max(Decimal('0'), tributo_calculado - to_decimal(v_dif))
    elif p_dif is not None and to_decimal(p_dif) > 0:
        v_dif_calc = (tributo_calculado * (to_decimal(p_dif) / Decimal('100'))).quantize(PRECISAO_MOEDA, rounding=ROUND_HALF_EVEN)
        tributo_devido = max(Decimal('0'), tributo_calculado - v_dif_calc)
    else:
        tributo_devido = tributo_calculado

    aliq_efetiva_apres = aliq_efetiva.quantize(PRECISAO_ALIQUOTA, rounding=ROUND_HALF_EVEN)
    return aliq_efetiva_apres, tributo_devido

# Variáveis globais de controle
chave_xml_atual = ""
dados_nfe_atual = {}

def remove_namespace(doc, namespace):
    """Remove o namespace do XML para facilitar a busca pelas tags."""
    ns = u'{%s}' % namespace
    nsl = len(ns)
    for elem in doc.iter():
        if elem.tag.startswith(ns):
            elem.tag = elem.tag[nsl:]

def extrair_dados_xml(caminho_arquivo, aliq_interna_informada=0.0, aliq_inter_informada=0.0, aliq_icms_informada=0.0, aliq_cbs_padrao=0.9, aliq_ibs_padrao=0.1, retornar_estruturado=False):
    try:
        # Conversão segura de alíquotas opcionais
        try:
            aliq_interna_informada = float(str(aliq_interna_informada).replace(',', '.')) if aliq_interna_informada else 0.0
        except Exception:
            aliq_interna_informada = 0.0

        try:
            aliq_inter_informada = float(str(aliq_inter_informada).replace(',', '.')) if aliq_inter_informada else 0.0
        except Exception:
            aliq_inter_informada = 0.0

        try:
            aliq_icms_informada = float(str(aliq_icms_informada).replace(',', '.')) if aliq_icms_informada else 0.0
        except Exception:
            aliq_icms_informada = 0.0

        tree = ET.parse(caminho_arquivo)
        root = tree.getroot()
        
        # Identifica e remove o namespace padrão da NF-e
        if '}' in root.tag:
            ns = root.tag.split('}')[0].strip('{')
            remove_namespace(root, ns)
            
        infNFe = root.find('.//infNFe')
        if infNFe is None:
            if retornar_estruturado:
                return "Erro: O arquivo selecionado não parece ser um XML de NF-e válido.", "", {}
            return "Erro: O arquivo selecionado não parece ser um XML de NF-e válido.", ""

        # Extração da Chave de Acesso do XML (Removendo o prefixo 'NFe')
        chave_xml_bruta = infNFe.attrib.get('Id', '').replace('NFe', '')
        if not chave_xml_bruta:
            protNFe = root.find('.//protNFe/infProt/chNFe')
            if protNFe is not None:
                chave_xml_bruta = protNFe.text
        
        chave_xml = ''.join(filter(str.isdigit, chave_xml_bruta)) if chave_xml_bruta else ""

        linhas = []
        
        # --- DADOS GERAIS DA NOTA ---
        ide = infNFe.find('ide')
        nNF = ide.find('nNF').text if ide is not None and ide.find('nNF') is not None else 'N/A'
        
        # Formata a série para ter sempre 3 dígitos (ex: "1" vira "001")
        serie_raw = ide.find('serie').text if ide is not None and ide.find('serie') is not None else 'N/A'
        serie = serie_raw.zfill(3) if serie_raw.isdigit() else serie_raw
        
        dhEmi = ide.find('dhEmi').text if ide is not None and ide.find('dhEmi') is not None else 'N/A'
        
        emit = infNFe.find('emit')
        xNome = emit.find('xNome').text if emit is not None and emit.find('xNome') is not None else 'N/A'
        cnpj = emit.find('CNPJ').text if emit is not None and emit.find('CNPJ') is not None else 'N/A'

        dest = infNFe.find('dest')
        dest_nome = dest.find('xNome').text if dest is not None and dest.find('xNome') is not None else 'N/A'
        dest_doc = dest.find('CNPJ').text if dest is not None and dest.find('CNPJ') is not None else (dest.find('CPF').text if dest is not None and dest.find('CPF') is not None else 'N/A')
        dest_uf = dest.find('.//UF').text if dest is not None and dest.find('.//UF') is not None else 'RJ'
        
        linhas.append("="*80)
        linhas.append(f"DADOS GERAIS DA NOTA FISCAL: {nNF} | SÉRIE: {serie}")
        linhas.append(f"CHAVE DE ACESSO (XML): {chave_xml}")
        linhas.append(f"EMITENTE: {xNome} (CNPJ: {cnpj})")
        linhas.append(f"DESTINATÁRIO: {dest_nome} (Doc: {dest_doc} | UF: {dest_uf})")
        linhas.append(f"DATA DE EMISSÃO: {dhEmi}")
        linhas.append("="*80)

        # Estrutura completa de dados para a interface estilo Datasul
        dados_estruturados = {
            'chave': chave_xml,
            'ide': {'nNF': nNF, 'serie': serie, 'dhEmi': dhEmi},
            'emit': {'xNome': xNome, 'cnpj': cnpj},
            'dest': {'xNome': dest_nome, 'doc': dest_doc, 'uf': dest_uf},
            'parcelas': [],
            'totais': {},
            'itens': []
        }

        # --- DADOS DE COBRANÇA E PARCELAS (CONDIÇÃO DE PAGAMENTO DATASUL) ---
        cobr = infNFe.find('cobr')
        if cobr is not None:
            dups = cobr.findall('dup')
            if dups:
                linhas.append("")
                linhas.append(f"COBRANÇA / PARCELAS -> TOTAL DE PARCELAS: {len(dups)}")
                fat = cobr.find('fat')
                if fat is not None:
                    vLiq = fat.find('vLiq').text if fat.find('vLiq') is not None else ''
                    if vLiq:
                        linhas.append(f"Valor Líquido da Fatura: R$ {vLiq}")
                
                lista_dups = []
                for dup in dups:
                    nDup = dup.find('nDup').text if dup.find('nDup') is not None else 'N/A'
                    vDup = dup.find('vDup').text if dup.find('vDup') is not None else '0.00'
                    lista_dups.append(f"Parc. {nDup}: R$ {vDup}")
                    dados_estruturados['parcelas'].append({'nDup': nDup, 'vDup': vDup})
                
                linhas.append(" | ".join(lista_dups))
                linhas.append("-" * 80)
        
        linhas.append("\n")

        # --- DADOS DOS ITENS ---
        for det in infNFe.findall('.//det'):
            nItem = det.attrib.get('nItem', '')
            prod = det.find('prod')
            
            cProd = prod.find('cProd').text if prod is not None and prod.find('cProd') is not None else ''
            xProd = prod.find('xProd').text if prod is not None and prod.find('xProd') is not None else ''
            ncm = prod.find('NCM').text if prod is not None and prod.find('NCM') is not None else ''
            cfop = prod.find('CFOP').text if prod is not None and prod.find('CFOP') is not None else ''
            uCom = prod.find('uCom').text if prod is not None and prod.find('uCom') is not None else ''
            qCom = prod.find('qCom').text if prod is not None and prod.find('qCom') is not None else ''
            vUnCom = prod.find('vUnCom').text if prod is not None and prod.find('vUnCom') is not None else ''
            vProd = prod.find('vProd').text if prod is not None and prod.find('vProd') is not None else ''
            
            # Componentes adicionais que compõem a base unificada (art. 349 LC 214/2025)
            vFrete = prod.find('vFrete').text if prod is not None and prod.find('vFrete') is not None else '0.00'
            vSeg = prod.find('vSeg').text if prod is not None and prod.find('vSeg') is not None else '0.00'
            vDesc = prod.find('vDesc').text if prod is not None and prod.find('vDesc') is not None else '0.00'
            vOutro = prod.find('vOutro').text if prod is not None and prod.find('vOutro') is not None else '0.00'

            linhas.append(f"--- ITEM {nItem} ---")
            linhas.append(f"Produto: {cProd} - {xProd}")
            linhas.append(f"NCM: {ncm} | CFOP: {cfop} | Unid: {uCom}")
            linhas.append(f"Qtde: {qCom} | Vlr Unit: R$ {vUnCom} | Vlr Total: R$ {vProd}")
            
            item_obj = {
                'num': nItem,
                'cProd': cProd,
                'xProd': xProd,
                'ncm': ncm,
                'cfop': cfop,
                'uCom': uCom,
                'qCom': qCom,
                'vUnCom': vUnCom,
                'vProd': vProd,
                'vFrete': vFrete,
                'vSeg': vSeg,
                'vDesc': vDesc,
                'vOutro': vOutro,
                'impostos': []
            }

            # Exibe componentes se algum estiver presente
            comp_txt = []
            if to_decimal(vFrete) > 0: comp_txt.append(f"Frete: R$ {vFrete}")
            if to_decimal(vSeg) > 0: comp_txt.append(f"Seguro: R$ {vSeg}")
            if to_decimal(vOutro) > 0: comp_txt.append(f"Outras: R$ {vOutro}")
            if to_decimal(vDesc) > 0: comp_txt.append(f"Desconto: R$ {vDesc}")
            if comp_txt:
                linhas.append(f"Componentes -> {' | '.join(comp_txt)}")
            
            # --- IMPOSTOS ---
            imposto = det.find('imposto')
            if imposto is not None:
                # 1. Extração de ICMS (Normal, ST e FCP ST)
                icms = imposto.find('ICMS')
                cst_icms_salvo = 'N/A'
                if icms is not None:
                    for child in icms: 
                        cst = child.find('CST') if child.find('CST') is not None else child.find('CSOSN')
                        orig = child.find('orig')
                        
                        cst_txt = cst.text if cst is not None else 'N/A'
                        cst_icms_salvo = cst_txt
                        orig_txt = orig.text if orig is not None else '0'
                        linhas.append(f"[ICMS] Origem: {orig_txt} | CST/CSOSN: {cst_txt}")
                        
                        # ICMS Normal
                        vBC = child.find('vBC')
                        pICMS = child.find('pICMS')
                        vICMS = child.find('vICMS')
                        
                        if vBC is not None or vICMS is not None:
                            vbc_val = vBC.text if vBC is not None else '0.00'
                            aliq = pICMS.text if pICMS is not None else '0.00'
                            vlr = vICMS.text if vICMS is not None else '0.00'
                            linhas.append(f"       ICMS Normal -> BC: {vbc_val} | Alíq: {aliq}% | Valor: {vlr}")
                            item_obj['impostos'].append({
                                'tributo': 'ICMS',
                                'cst': cst_txt,
                                'base': vbc_val,
                                'aliq': aliq,
                                'valor': vlr,
                                'status': f"Origem: {orig_txt}"
                            })
                        else:
                            try:
                                base_calc = float(vProd) if vProd else 0.0
                                if aliq_icms_informada > 0:
                                    valor_icms_calc = base_calc * (aliq_icms_informada / 100)
                                    linhas.append(f"       ICMS Normal -> [CÁLC. PRESUMIDO] BC: {base_calc:.2f} | Alíq (Tela): {aliq_icms_informada:.2f}% | Valor: {valor_icms_calc:.2f}")
                                    item_obj['impostos'].append({
                                        'tributo': 'ICMS',
                                        'cst': cst_txt,
                                        'base': f"{base_calc:.2f}",
                                        'aliq': f"{aliq_icms_informada:.2f}",
                                        'valor': f"{valor_icms_calc:.2f}",
                                        'status': 'Cálc. Presumido (Tela)'
                                    })
                                else:
                                    linhas.append(f"       ICMS Normal -> Não destacado no XML (Preenchimento Manual)")
                                    item_obj['impostos'].append({
                                        'tributo': 'ICMS',
                                        'cst': cst_txt,
                                        'base': '0.00',
                                        'aliq': '0.00',
                                        'valor': '0.00',
                                        'status': 'Não destacado'
                                    })
                            except Exception:
                                linhas.append(f"       ICMS Normal -> Não destacado no XML (Preenchimento Manual)")
                                item_obj['impostos'].append({
                                    'tributo': 'ICMS',
                                    'cst': cst_txt,
                                    'base': '0.00',
                                    'aliq': '0.00',
                                    'valor': '0.00',
                                    'status': 'Não destacado'
                                })
                        
                        # FCP Normal
                        vBCFCP = child.find('vBCFCP')
                        pFCP = child.find('pFCP')
                        vFCP = child.find('vFCP')
                        
                        if vFCP is not None or vBCFCP is not None:
                            bc_fcp = vBCFCP.text if vBCFCP is not None else (vBC.text if vBC is not None else '0.00')
                            aliq_fcp = pFCP.text if pFCP is not None else '0.00'
                            val_fcp = vFCP.text if vFCP is not None else '0.00'
                            linhas.append(f"       FCP Normal  -> BC FCP: {bc_fcp} | Alíq FCP: {aliq_fcp}% | Valor FCP: {val_fcp}")
                            if to_decimal(val_fcp) > 0 or to_decimal(bc_fcp) > 0:
                                item_obj['impostos'].append({
                                    'tributo': 'FCP Normal',
                                    'cst': cst_txt,
                                    'base': bc_fcp,
                                    'aliq': aliq_fcp,
                                    'valor': val_fcp,
                                    'status': 'Fundo Combate Pobreza'
                                })

                        # Crédito Simples Nacional
                        pCred = child.find('pCredSN')
                        vCred = child.find('vCredICMSSN')
                        if pCred is not None or vCred is not None:
                            p_cred_val = pCred.text if pCred is not None else '0.00'
                            v_cred_val = vCred.text if vCred is not None else '0.00'
                            linhas.append(f"       Crédito SN  -> Alíq: {p_cred_val}% | Valor: {v_cred_val}")

                        # ICMS ST
                        vBCST = child.find('vBCST')
                        pICMSST = child.find('pICMSST')
                        vICMSST = child.find('vICMSST')
                        pMVAST = child.find('pMVAST')
                        
                        if vBCST is not None or vICMSST is not None:
                            bc_st = vBCST.text if vBCST is not None else '0'
                            aliq_st = pICMSST.text if pICMSST is not None else '0'
                            val_st = vICMSST.text if vICMSST is not None else '0'
                            mva_st = pMVAST.text if pMVAST is not None else '0'
                            linhas.append(f"       ICMS ST     -> MVA: {mva_st}% | BC ST: {bc_st} | Alíq ST: {aliq_st}% | Valor ST: {val_st}")
                            if to_decimal(val_st) > 0 or to_decimal(bc_st) > 0:
                                item_obj['impostos'].append({
                                    'tributo': 'ICMS ST',
                                    'cst': cst_txt,
                                    'base': bc_st,
                                    'aliq': aliq_st,
                                    'valor': val_st,
                                    'status': f"MVA: {mva_st}%"
                                })
                        
                        # FCP ST
                        vBCFCPST = child.find('vBCFCPST')
                        pFCPST = child.find('pFCPST')
                        vFCPST = child.find('vFCPST')
                        
                        if vFCPST is not None:
                            bc_fcpst = vBCFCPST.text if vBCFCPST is not None else '0'
                            aliq_fcpst = pFCPST.text if pFCPST is not None else '0'
                            val_fcpst = vFCPST.text if vFCPST is not None else '0'
                            linhas.append(f"       FCP ST      -> BC FCP ST: {bc_fcpst} | Alíq FCP ST: {aliq_fcpst}% | Valor FCP ST: {val_fcpst}")
                            if to_decimal(val_fcpst) > 0:
                                item_obj['impostos'].append({
                                    'tributo': 'FCP ST',
                                    'cst': cst_txt,
                                    'base': bc_fcpst,
                                    'aliq': aliq_fcpst,
                                    'valor': val_fcpst,
                                    'status': 'FCP Subst. Tributária'
                                })
                else:
                    item_obj['impostos'].append({
                        'tributo': 'ICMS',
                        'cst': 'N/A',
                        'base': '0.00',
                        'aliq': '0.00',
                        'valor': '0.00',
                        'status': 'Não destacado'
                    })

                # Extração de DIFAL (ICMSUFDest) ou Cálculo Presumido
                icms_uf_dest = imposto.find('ICMSUFDest')
                if icms_uf_dest is not None:
                    vbc_uf_dest = icms_uf_dest.find('vBCUFDest').text if icms_uf_dest.find('vBCUFDest') is not None else '0.00'
                    p_icms_uf_dest = icms_uf_dest.find('pICMSUFDest').text if icms_uf_dest.find('pICMSUFDest') is not None else '0.00'
                    p_icms_inter = icms_uf_dest.find('pICMSInter').text if icms_uf_dest.find('pICMSInter') is not None else '0.00'
                    v_icms_uf_dest = icms_uf_dest.find('vICMSUFDest').text if icms_uf_dest.find('vICMSUFDest') is not None else '0.00'
                    
                    linhas.append(f"       DIFAL       -> BC: {vbc_uf_dest} | Alíq Inter: {p_icms_inter}% | Alíq Dest ({dest_uf}): {p_icms_uf_dest}%")
                    linhas.append(f"       (Lançar no Datasul -> Base ICMS Compl.: {vbc_uf_dest} | Valor ICMS Compl.: {v_icms_uf_dest})")
                    item_obj['impostos'].append({
                        'tributo': 'DIFAL',
                        'cst': '-',
                        'base': vbc_uf_dest,
                        'aliq': f"{p_icms_uf_dest}-{p_icms_inter}",
                        'valor': v_icms_uf_dest,
                        'status': f"UF Destino: {dest_uf}"
                    })
                elif cfop.startswith('6'):
                    try:
                        base_difal = 0.0
                        aliq_inter = 0.0
                        
                        icms_node = imposto.find('ICMS')
                        if icms_node is not None:
                            for c in icms_node:
                                vBC_node = c.find('vBC')
                                pICMS_node = c.find('pICMS')
                                if vBC_node is not None:
                                    base_difal = float(vBC_node.text)
                                if pICMS_node is not None:
                                    aliq_inter = float(pICMS_node.text)
                                    
                        if base_difal == 0.0 and vProd:
                            base_difal = float(vProd)
                            
                        if aliq_inter == 0.0:
                            aliq_inter = aliq_inter_informada
                            origem_aliq = "Lida da Tela"
                        else:
                            origem_aliq = "Lida do XML"
                            
                        if aliq_inter > 0:
                            if aliq_interna_informada > aliq_inter:
                                valor_difal = base_difal * ((aliq_interna_informada - aliq_inter) / 100)
                                linhas.append(f"       DIFAL       -> [CÁLC. PRESUMIDO] BC: {base_difal:.2f} | Alíq Inter ({origem_aliq}): {aliq_inter:.2f}% | Alíq Int {dest_uf}: {aliq_interna_informada:.2f}%")
                                linhas.append(f"       (Lançar no Datasul -> Base ICMS Compl.: {base_difal:.2f} | Valor ICMS Compl.: {valor_difal:.2f})")
                                item_obj['impostos'].append({
                                    'tributo': 'DIFAL (Presum.)',
                                    'cst': '-',
                                    'base': f"{base_difal:.2f}",
                                    'aliq': f"{aliq_interna_informada:.2f}-{aliq_inter:.2f}",
                                    'valor': f"{valor_difal:.2f}",
                                    'status': f"Presumido Destino {dest_uf}"
                                })
                            else:
                                linhas.append(f"       DIFAL       -> ATENÇÃO: Alíquota interestadual ({aliq_inter}%) é maior ou igual à interna informada ({aliq_interna_informada}%).")
                        else:
                            linhas.append(f"       DIFAL       -> ATENÇÃO: Operação Interestadual sem alíquota ICMS. Informe na tela principal.")
                    except Exception:
                        linhas.append(f"       DIFAL       -> ATENÇÃO: Operação Interestadual (CFOP {cfop}). Cálculo manual necessário.")

                # 2. Extração e Auditoria Oficial da Reforma Tributária (CBS e IBS - LC 214/2025)
                vProd_dec = to_decimal(vProd)
                vFrete_dec = to_decimal(vFrete)
                vSeg_dec = to_decimal(vSeg)
                vOutro_dec = to_decimal(vOutro)
                vDesc_dec = to_decimal(vDesc)
                
                vII_dec = to_decimal(imposto.find('.//II/vII').text if imposto.find('.//II/vII') is not None else '0')
                vIS_dec = to_decimal(imposto.find('.//IS/vIS').text if imposto.find('.//IS/vIS') is not None else '0')
                vICMS_dec = to_decimal(imposto.find('.//ICMS//vICMS').text if imposto.find('.//ICMS//vICMS') is not None else '0')
                vFCP_dec = to_decimal(imposto.find('.//ICMS//vFCP').text if imposto.find('.//ICMS//vFCP') is not None else '0')
                vPIS_dec = to_decimal(imposto.find('.//PIS//vPIS').text if imposto.find('.//PIS//vPIS') is not None else '0')
                vCOFINS_dec = to_decimal(imposto.find('.//COFINS//vCOFINS').text if imposto.find('.//COFINS//vCOFINS') is not None else '0')
                vISS_dec = to_decimal(imposto.find('.//ISSQN//vISS').text if imposto.find('.//ISSQN//vISS') is not None else '0')

                ano_fg = 2026
                if dhEmi and len(dhEmi) >= 4 and dhEmi[:4].isdigit():
                    try:
                        ano_parsed = int(dhEmi[:4])
                        if ano_parsed >= 2026:
                            ano_fg = ano_parsed
                    except Exception:
                        pass

                base_unificada_oficial = calcular_base_unificada_rtc_oficial(
                    vProd_dec, vFrete_dec, vSeg_dec, vOutro_dec, vII_dec, vIS_dec,
                    vDesc_dec, vICMS_dec, vPIS_dec, vCOFINS_dec, vFCP_dec, vISS_dec,
                    ano=ano_fg
                )
                
                ibscbs = imposto.find('IBSCBS')
                if ibscbs is not None:
                    cst_ibscbs = ibscbs.find('CST').text if ibscbs.find('CST') is not None else 'N/A'
                    cClassTrib = ibscbs.find('cClassTrib').text if ibscbs.find('cClassTrib') is not None else 'N/A'
                    cst_desc = CST_IBS_CBS_DESCRICAO.get(cst_ibscbs, "Regime Específico / Outros")
                    
                    linhas.append(f"[IBS/CBS - REFORMA TRIBUTÁRIA] CST: {cst_ibscbs} ({cst_desc}) | cClassTrib: {cClassTrib}")
                    
                    gIBSCBS = ibscbs.find('gIBSCBS')
                    if gIBSCBS is not None:
                        vBC_ibscbs_str = gIBSCBS.find('vBC').text if gIBSCBS.find('vBC') is not None else '0.00'
                        vBC_ibscbs = to_decimal(vBC_ibscbs_str)
                        
                        aviso_base = ""
                        if abs(vBC_ibscbs - base_unificada_oficial) > Decimal('0.05') and base_unificada_oficial > 0:
                            aviso_base = f" (Base unificada oficial apurada conforme Art. 349: R$ {format_moeda_raw(base_unificada_oficial)})"
                        
                        linhas.append(f"          Base de Cálculo Geral (vBC): R$ {format_moeda_raw(vBC_ibscbs)}{aviso_base}")
                        
                        def auditar_tributo(elemento, tag_aliq, tag_valor, nome_tributo):
                            if elemento is None:
                                return "", {}
                            p_nom = elemento.find(tag_aliq).text if elemento.find(tag_aliq) is not None else '0'
                            v_xml_str = elemento.find(tag_valor).text if elemento.find(tag_valor) is not None else '0'
                            v_xml = to_decimal(v_xml_str)
                            
                            p_red = '0.00'
                            p_efet_xml = None
                            gred = elemento.find('gRed')
                            if gred is not None:
                                p_red = gred.find('pRedAliq').text if gred.find('pRedAliq') is not None else '0.00'
                                p_efet_xml = gred.find('pAliqEfet').text if gred.find('pAliqEfet') is not None else None

                            gdif = elemento.find('gDif')
                            p_dif = gdif.find('pDif').text if gdif is not None and gdif.find('pDif') is not None else None
                            v_dif = gdif.find('vDif').text if gdif is not None and gdif.find('vDif') is not None else None

                            gdev = elemento.find('gDevTrib')
                            v_dev_trib = gdev.find('vDevTrib').text if gdev is not None and gdev.find('vDevTrib') is not None else None
                                
                            aliq_efet_oficial, v_oficial = calcular_tributo_rtc_oficial(
                                vBC_ibscbs, p_nom, p_red, aliq_efet_xml=p_efet_xml, v_dif=v_dif, p_dif=p_dif
                            )
                            
                            dif = abs(v_xml - v_oficial)
                            if dif <= Decimal('0.01'):
                                status = "[Auditoria RFB: ✔️ Conforme]"
                                status_curto = "✔️ Conforme"
                            else:
                                status = f"[Auditoria RFB: ⚠️ Divergência! XML: R$ {format_moeda_raw(v_xml)} vs Oficial: R$ {format_moeda_raw(v_oficial)}]"
                                status_curto = f"⚠️ Divergência! (Oficial: R$ {format_moeda_raw(v_oficial)})"
                                
                            detalhes = []
                            if gred is not None:
                                detalhes.append(f"Alíq Red: {p_red}%")
                                if p_efet_xml:
                                    detalhes.append(f"Alíq Efet: {p_efet_xml}%")
                            if gdif is not None:
                                if p_dif:
                                    detalhes.append(f"Diferimento: {p_dif}%")
                                if v_dif:
                                    detalhes.append(f"vDif: R$ {v_dif}")
                            if v_dev_trib and to_decimal(v_dev_trib) > 0:
                                detalhes.append(f"Devolução: R$ {v_dev_trib}")
                            
                            det_str = (" | " + " | ".join(detalhes)) if detalhes else ""
                            linha_texto = f"          [{nome_tributo}] Alíq: {p_nom}%{det_str} | Valor: R$ {format_moeda_raw(v_xml)} {status}"
                            info_dict = {
                                'tributo': nome_tributo,
                                'cst': cst_ibscbs,
                                'base': vBC_ibscbs_str,
                                'aliq': p_nom,
                                'valor': v_xml_str,
                                'status': status_curto
                            }
                            return linha_texto, info_dict

                        # ORDEM SOLICITADA: CBS > IBS UF > IBS MUN
                        gCBS = gIBSCBS.find('gCBS')
                        if gCBS is not None:
                            lt, idict = auditar_tributo(gCBS, 'pCBS', 'vCBS', 'CBS')
                            linhas.append(lt)
                            item_obj['impostos'].append(idict)

                        gIBSUF = gIBSCBS.find('gIBSUF')
                        if gIBSUF is not None:
                            lt, idict = auditar_tributo(gIBSUF, 'pIBSUF', 'vIBSUF', 'IBS UF')
                            linhas.append(lt)
                            item_obj['impostos'].append(idict)
                            
                        gIBSMun = gIBSCBS.find('gIBSMun')
                        if gIBSMun is not None:
                            lt, idict = auditar_tributo(gIBSMun, 'pIBSMun', 'vIBSMun', 'IBS MUN')
                            linhas.append(lt)
                            item_obj['impostos'].append(idict)

                    gIBSCBSMono = ibscbs.find('gIBSCBSMono')
                    if gIBSCBSMono is not None:
                        qBCMono_str = gIBSCBSMono.find('qBCMono').text if gIBSCBSMono.find('qBCMono') is not None else '0'
                        adRemIBS_str = gIBSCBSMono.find('adRemIBS').text if gIBSCBSMono.find('adRemIBS') is not None else '0'
                        adRemCBS_str = gIBSCBSMono.find('adRemCBS').text if gIBSCBSMono.find('adRemCBS') is not None else '0'
                        vIBSMono_str = gIBSCBSMono.find('vIBSMono').text if gIBSCBSMono.find('vIBSMono') is not None else '0'
                        vCBSMono_str = gIBSCBSMono.find('vCBSMono').text if gIBSCBSMono.find('vCBSMono') is not None else '0'
                        
                        q_mono = to_decimal(qBCMono_str)
                        ad_ibs = to_decimal(adRemIBS_str)
                        ad_cbs = to_decimal(adRemCBS_str)
                        v_ibs_mono = to_decimal(vIBSMono_str)
                        v_cbs_mono = to_decimal(vCBSMono_str)
                        
                        v_ibs_oficial = (q_mono * ad_ibs).quantize(PRECISAO_MOEDA, rounding=ROUND_HALF_EVEN)
                        v_cbs_oficial = (q_mono * ad_cbs).quantize(PRECISAO_MOEDA, rounding=ROUND_HALF_EVEN)
                        
                        st_cbs = "✔️ Conforme" if abs(v_cbs_mono - v_cbs_oficial) <= Decimal('0.01') else f"⚠️ Divergência! (Oficial: R$ {format_moeda_raw(v_cbs_oficial)})"
                        st_ibs = "✔️ Conforme" if abs(v_ibs_mono - v_ibs_oficial) <= Decimal('0.01') else f"⚠️ Divergência! (Oficial: R$ {format_moeda_raw(v_ibs_oficial)})"
                        
                        # ORDEM: CBS > IBS
                        linhas.append(f"          [MONOFASIA] adRem CBS: R$ {adRemCBS_str} | vCBS: R$ {vCBSMono_str} [Auditoria RFB: {st_cbs}]")
                        linhas.append(f"          [MONOFASIA] Qtd BC: {qBCMono_str} | adRem IBS: R$ {adRemIBS_str} | vIBS: R$ {vIBSMono_str} [Auditoria RFB: {st_ibs}]")
                        item_obj['impostos'].append({
                            'tributo': 'CBS (Mono)',
                            'cst': cst_ibscbs,
                            'base': qBCMono_str,
                            'aliq': adRemCBS_str,
                            'valor': vCBSMono_str,
                            'status': st_cbs
                        })
                        item_obj['impostos'].append({
                            'tributo': 'IBS (Mono)',
                            'cst': cst_ibscbs,
                            'base': qBCMono_str,
                            'aliq': adRemIBS_str,
                            'valor': vIBSMono_str,
                            'status': st_ibs
                        })
                    elif gIBSCBS is None:
                        if cst_ibscbs in ('400', '410', '550', '800', '810', '820', '830'):
                            linhas.append(f"          [Auditoria RFB: ✔️ Desonerado / Sem débito de tributo conforme CST {cst_ibscbs}]")
                            item_obj['impostos'].append({
                                'tributo': 'CBS',
                                'cst': cst_ibscbs,
                                'base': '0.00',
                                'aliq': '0.00',
                                'valor': '0.00',
                                'status': 'Desonerado / Sem débito'
                            })
                            item_obj['impostos'].append({
                                'tributo': 'IBS UF',
                                'cst': cst_ibscbs,
                                'base': '0.00',
                                'aliq': '0.00',
                                'valor': '0.00',
                                'status': 'Desonerado / Sem débito'
                            })
                            item_obj['impostos'].append({
                                'tributo': 'IBS MUN',
                                'cst': cst_ibscbs,
                                'base': '0.00',
                                'aliq': '0.00',
                                'valor': '0.00',
                                'status': 'Desonerado / Sem débito'
                            })
                else:
                    aliq_cbs_dec = to_decimal(aliq_cbs_padrao)
                    aliq_ibs_dec = to_decimal(aliq_ibs_padrao)
                    aliq_ibs_uf = aliq_ibs_dec / Decimal('2')
                    aliq_ibs_mun = aliq_ibs_dec / Decimal('2')
                    
                    _, v_cbs_simul = calcular_tributo_rtc_oficial(base_unificada_oficial, aliq_cbs_dec)
                    _, v_ibs_uf_simul = calcular_tributo_rtc_oficial(base_unificada_oficial, aliq_ibs_uf)
                    _, v_ibs_mun_simul = calcular_tributo_rtc_oficial(base_unificada_oficial, aliq_ibs_mun)
                    v_ibs_tot_simul = v_ibs_uf_simul + v_ibs_mun_simul
                    
                    linhas.append(f"[IBS/CBS] Não destacado no XML [SIMULAÇÃO RTC TRANSIÇÃO OFICIAL]")
                    linhas.append(f"          Base Unificada: R$ {format_moeda_raw(base_unificada_oficial)} | CBS ({aliq_cbs_padrao:.2f}%): R$ {format_moeda_raw(v_cbs_simul)}")
                    linhas.append(f"          IBS ({aliq_ibs_padrao:.2f}%): R$ {format_moeda_raw(v_ibs_tot_simul)} (UF: R$ {format_moeda_raw(v_ibs_uf_simul)} | Mun: R$ {format_moeda_raw(v_ibs_mun_simul)})")
                    
                    base_simul_str = format_moeda_raw(base_unificada_oficial)
                    item_obj['impostos'].append({
                        'tributo': 'CBS (Simul.)',
                        'cst': 'Simul.',
                        'base': base_simul_str,
                        'aliq': f"{aliq_cbs_padrao:.2f}",
                        'valor': format_moeda_raw(v_cbs_simul),
                        'status': 'Simulação Art. 349 (Transição)'
                    })
                    item_obj['impostos'].append({
                        'tributo': 'IBS UF (Simul.)',
                        'cst': 'Simul.',
                        'base': base_simul_str,
                        'aliq': f"{aliq_ibs_uf:.2f}",
                        'valor': format_moeda_raw(v_ibs_uf_simul),
                        'status': 'Simulação Art. 349'
                    })
                    item_obj['impostos'].append({
                        'tributo': 'IBS MUN (Simul.)',
                        'cst': 'Simul.',
                        'base': base_simul_str,
                        'aliq': f"{aliq_ibs_mun:.2f}",
                        'valor': format_moeda_raw(v_ibs_mun_simul),
                        'status': 'Simulação Art. 349'
                    })

                # 3. Extração e Auditoria Oficial de Imposto Seletivo (IS)
                is_node = imposto.find('IS')
                if is_node is not None:
                    cst_is = is_node.find('CST').text if is_node.find('CST') is not None else 'N/A'
                    cClassTrib_is = is_node.find('cClassTrib').text if is_node.find('cClassTrib') is not None else 'N/A'
                    cst_is_desc = CST_IS_DESCRICAO.get(cst_is, "Outros")
                    vBC_is = is_node.find('vBC').text if is_node.find('vBC') is not None else '0.00'
                    pIS = is_node.find('pIS').text if is_node.find('pIS') is not None else '0.00'
                    vIS = is_node.find('vIS').text if is_node.find('vIS') is not None else '0.00'
                    
                    vIS_val = to_decimal(vIS)
                    vBC_is_val = to_decimal(vBC_is)
                    pIS_val = to_decimal(pIS)
                    status_is = ""
                    status_is_curto = ""
                    if vBC_is_val > 0 and pIS_val > 0:
                        v_is_oficial = (vBC_is_val * (pIS_val / Decimal('100'))).quantize(PRECISAO_MOEDA, rounding=ROUND_HALF_EVEN)
                        if abs(vIS_val - v_is_oficial) <= Decimal('0.01'):
                            status_is = " [Auditoria RFB: ✔️ Conforme]"
                            status_is_curto = "✔️ Conforme"
                        else:
                            status_is = f" [Auditoria RFB: ⚠️ Divergência! XML: R$ {format_moeda_raw(vIS_val)} vs Oficial: R$ {format_moeda_raw(v_is_oficial)}]"
                            status_is_curto = f"⚠️ Divergência! (Oficial: R$ {format_moeda_raw(v_is_oficial)})"
                    elif cst_is in ('100', '200', '400', '500', '600') and vIS_val == 0:
                        status_is = " [Auditoria RFB: ✔️ Conforme (Sem incidência/Zero)]"
                        status_is_curto = "✔️ Sem incidência/Zero"

                    linhas.append(f"[IMPOSTO SELETIVO] CST: {cst_is} ({cst_is_desc}) | cClassTrib: {cClassTrib_is} | BC: R$ {vBC_is} | Alíq: {pIS}% | Valor: R$ {vIS}{status_is}")
                    item_obj['impostos'].append({
                        'tributo': 'IS',
                        'cst': cst_is,
                        'base': vBC_is,
                        'aliq': pIS,
                        'valor': vIS,
                        'status': status_is_curto if status_is_curto else f"cClass: {cClassTrib_is}"
                    })
                else:
                    item_obj['impostos'].append({
                        'tributo': 'IS',
                        'cst': '-',
                        'base': '0.00',
                        'aliq': '0.00',
                        'valor': '0.00',
                        'status': 'Não destacado'
                    })

                # 4. Extração de IPI (Imposto sobre Produtos Industrializados)
                ipi = imposto.find('IPI')
                if ipi is not None:
                    cEnq = ipi.find('cEnq').text if ipi.find('cEnq') is not None else ''
                    ipi_trib = ipi.find('IPITrib')
                    if ipi_trib is not None:
                        cst_ipi = ipi_trib.find('CST').text if ipi_trib.find('CST') is not None else 'N/A'
                        vbc_ipi = ipi_trib.find('vBC').text if ipi_trib.find('vBC') is not None else '0.00'
                        p_ipi = ipi_trib.find('pIPI').text if ipi_trib.find('pIPI') is not None else '0.00'
                        v_ipi = ipi_trib.find('vIPI').text if ipi_trib.find('vIPI') is not None else '0.00'
                        linhas.append(f"[IPI] CST: {cst_ipi} | cEnq: {cEnq} | BC: R$ {vbc_ipi} | Alíq: {p_ipi}% | Valor: R$ {v_ipi}")
                        item_obj['impostos'].append({
                            'tributo': 'IPI',
                            'cst': cst_ipi,
                            'base': vbc_ipi,
                            'aliq': p_ipi,
                            'valor': v_ipi,
                            'status': f"cEnq: {cEnq}" if cEnq else "Tributado"
                        })
                    else:
                        ipi_nt = ipi.find('IPINT')
                        if ipi_nt is not None:
                            cst_ipi = ipi_nt.find('CST').text if ipi_nt.find('CST') is not None else 'N/A'
                            linhas.append(f"[IPI] Não tributado (CST: {cst_ipi} | cEnq: {cEnq})")
                            item_obj['impostos'].append({
                                'tributo': 'IPI',
                                'cst': cst_ipi,
                                'base': '0.00',
                                'aliq': '0.00',
                                'valor': '0.00',
                                'status': f"Não tributado (cEnq {cEnq})"
                            })
                else:
                    item_obj['impostos'].append({
                        'tributo': 'IPI',
                        'cst': '-',
                        'base': '0.00',
                        'aliq': '0.00',
                        'valor': '0.00',
                        'status': 'Não destacado'
                    })

                # 5. Extração de PIS e COFINS
                pis = imposto.find('PIS')
                cofins = imposto.find('COFINS')
                pis_part = ""
                cofins_part = ""
                pis_info = {'tributo': 'PIS', 'cst': '-', 'base': '0.00', 'aliq': '0.00', 'valor': '0.00', 'status': 'Não destacado'}
                cofins_info = {'tributo': 'COFINS', 'cst': '-', 'base': '0.00', 'aliq': '0.00', 'valor': '0.00', 'status': 'Não destacado'}

                if pis is not None:
                    for p_child in pis:
                        cst_p = p_child.find('CST').text if p_child.find('CST') is not None else 'N/A'
                        vbc_p = p_child.find('vBC').text if p_child.find('vBC') is not None else '0.00'
                        aliq_p = p_child.find('pPIS').text if p_child.find('pPIS') is not None else '0.00'
                        val_p = p_child.find('vPIS').text if p_child.find('vPIS') is not None else '0.00'
                        if to_decimal(val_p) > 0 or to_decimal(vbc_p) > 0:
                            pis_part = f"PIS (CST {cst_p}) -> BC: R$ {vbc_p} | Alíq: {aliq_p}% | Valor: R$ {val_p}"
                            pis_info = {'tributo': 'PIS', 'cst': cst_p, 'base': vbc_p, 'aliq': aliq_p, 'valor': val_p, 'status': 'Tributado'}
                        else:
                            pis_part = f"PIS (CST {cst_p}) -> Sem destaque"
                            pis_info = {'tributo': 'PIS', 'cst': cst_p, 'base': '0.00', 'aliq': '0.00', 'valor': '0.00', 'status': 'Sem destaque'}
                        break
                        
                if cofins is not None:
                    for c_child in cofins:
                        cst_c = c_child.find('CST').text if c_child.find('CST') is not None else 'N/A'
                        vbc_c = c_child.find('vBC').text if c_child.find('vBC') is not None else '0.00'
                        aliq_c = c_child.find('pCOFINS').text if c_child.find('pCOFINS') is not None else '0.00'
                        val_c = c_child.find('vCOFINS').text if c_child.find('vCOFINS') is not None else '0.00'
                        if to_decimal(val_c) > 0 or to_decimal(vbc_c) > 0:
                            cofins_part = f"COFINS (CST {cst_c}) -> BC: R$ {vbc_c} | Alíq: {aliq_c}% | Valor: R$ {val_c}"
                            cofins_info = {'tributo': 'COFINS', 'cst': cst_c, 'base': vbc_c, 'aliq': aliq_c, 'valor': val_c, 'status': 'Tributado'}
                        else:
                            cofins_part = f"COFINS (CST {cst_c}) -> Sem destaque"
                            cofins_info = {'tributo': 'COFINS', 'cst': cst_c, 'base': '0.00', 'aliq': '0.00', 'valor': '0.00', 'status': 'Sem destaque'}
                        break

                if pis_part or cofins_part:
                    linhas.append(f"[PIS/COFINS] {pis_part} | {cofins_part}")

                item_obj['impostos'].append(pis_info)
                item_obj['impostos'].append(cofins_info)

            dados_estruturados['itens'].append(item_obj)
            linhas.append("\n")
        
        # --- TOTAIS GERAIS DA NOTA FISCAL (BATIMENTO E CONFERÊNCIA DATASUL) ---
        total = infNFe.find('total')
        totais_dict = {
            'vProd': '0.00', 'vNF': '0.00', 'vFrete': '0.00', 'vSeg': '0.00', 'vDesc': '0.00', 'vOutro': '0.00',
            'vBC': '0.00', 'vICMS': '0.00', 'vBCST': '0.00', 'vST': '0.00', 'vFCP': '0.00', 'vFCPST': '0.00',
            'vBC_rtc': '0.00', 'vCBS': '0.00', 'vIBS': '0.00', 'vIS': '0.00', 'vIPI': '0.00', 'vPIS': '0.00', 'vCOFINS': '0.00'
        }

        if total is not None:
            linhas.append("="*80)
            linhas.append("TOTAIS DA NOTA FISCAL (CONFERÊNCIA PARA DIGITAÇÃO / DATASUL)")
            linhas.append("="*80)
            
            icmsTot = total.find('ICMSTot')
            if icmsTot is not None:
                vProd_tot = icmsTot.find('vProd').text if icmsTot.find('vProd') is not None else '0.00'
                vNF_tot = icmsTot.find('vNF').text if icmsTot.find('vNF') is not None else '0.00'
                vFrete_tot = icmsTot.find('vFrete').text if icmsTot.find('vFrete') is not None else '0.00'
                vSeg_tot = icmsTot.find('vSeg').text if icmsTot.find('vSeg') is not None else '0.00'
                vDesc_tot = icmsTot.find('vDesc').text if icmsTot.find('vDesc') is not None else '0.00'
                vOutro_tot = icmsTot.find('vOutro').text if icmsTot.find('vOutro') is not None else '0.00'
                
                vBC_tot = icmsTot.find('vBC').text if icmsTot.find('vBC') is not None else '0.00'
                vICMS_tot = icmsTot.find('vICMS').text if icmsTot.find('vICMS') is not None else '0.00'
                vBCST_tot = icmsTot.find('vBCST').text if icmsTot.find('vBCST') is not None else '0.00'
                vST_tot = icmsTot.find('vST').text if icmsTot.find('vST') is not None else '0.00'
                vFCP_tot = icmsTot.find('vFCP').text if icmsTot.find('vFCP') is not None else '0.00'
                vFCPST_tot = icmsTot.find('vFCPST').text if icmsTot.find('vFCPST') is not None else '0.00'
                
                vIPI_tot = icmsTot.find('vIPI').text if icmsTot.find('vIPI') is not None else '0.00'
                vPIS_tot = icmsTot.find('vPIS').text if icmsTot.find('vPIS') is not None else '0.00'
                vCOFINS_tot = icmsTot.find('vCOFINS').text if icmsTot.find('vCOFINS') is not None else '0.00'

                totais_dict.update({
                    'vProd': vProd_tot, 'vNF': vNF_tot, 'vFrete': vFrete_tot, 'vSeg': vSeg_tot,
                    'vDesc': vDesc_tot, 'vOutro': vOutro_tot, 'vBC': vBC_tot, 'vICMS': vICMS_tot,
                    'vBCST': vBCST_tot, 'vST': vST_tot, 'vFCP': vFCP_tot, 'vFCPST': vFCPST_tot,
                    'vIPI': vIPI_tot, 'vPIS': vPIS_tot, 'vCOFINS': vCOFINS_tot
                })

                linhas.append(f"VALOR DOS PRODUTOS: R$ {vProd_tot} | VALOR TOTAL DA NOTA (vNF): R$ {vNF_tot}")
                linhas.append(f"FRETE: R$ {vFrete_tot} | SEGURO: R$ {vSeg_tot} | OUTRAS: R$ {vOutro_tot} | DESCONTO: R$ {vDesc_tot}")
                linhas.append(f"ICMS NORMAL -> Base Total: R$ {vBC_tot} | Valor Total: R$ {vICMS_tot}")
                linhas.append(f"ICMS ST     -> Base Total ST: R$ {vBCST_tot} | Valor Total ST: R$ {vST_tot}")
                linhas.append(f"FCP TOTAL   -> FCP Normal: R$ {vFCP_tot} | FCP ST: R$ {vFCPST_tot}")

            # Totais da Reforma Tributária (se presentes no grupo total)
            ibscbsTot = total.find('IBSCBSTot')
            if ibscbsTot is not None:
                vBC_rtc_el = ibscbsTot.find('.//vBCIBSCBS')
                if vBC_rtc_el is None:
                    vBC_rtc_el = ibscbsTot.find('.//vBC')
                vBC_rtc = vBC_rtc_el.text if vBC_rtc_el is not None else '0.00'
                
                vIBS_tot_el = ibscbsTot.find('.//vIBS')
                vIBS_tot = vIBS_tot_el.text if vIBS_tot_el is not None else '0.00'
                
                vCBS_tot_el = ibscbsTot.find('.//vCBS')
                vCBS_tot = vCBS_tot_el.text if vCBS_tot_el is not None else '0.00'
                
                totais_dict.update({'vBC_rtc': vBC_rtc, 'vCBS': vCBS_tot, 'vIBS': vIBS_tot})
                linhas.append(f"REFORMA TRIBUTÁRIA -> Base RTC: R$ {vBC_rtc} | Total CBS: R$ {vCBS_tot} | Total IBS: R$ {vIBS_tot}")
            else:
                # Simula totais de CBS e IBS somando os itens
                soma_cbs = sum(to_decimal(imp['valor']) for itm in dados_estruturados['itens'] for imp in itm['impostos'] if 'CBS' in imp['tributo'])
                soma_ibs = sum(to_decimal(imp['valor']) for itm in dados_estruturados['itens'] for imp in itm['impostos'] if 'IBS' in imp['tributo'])
                totais_dict['vCBS'] = f"{soma_cbs:.2f}"
                totais_dict['vIBS'] = f"{soma_ibs:.2f}"

            isTot = total.find('ISTot')
            if isTot is not None:
                vIS_tot = isTot.find('vIS').text if isTot.find('vIS') is not None else '0.00'
                totais_dict['vIS'] = vIS_tot
                linhas.append(f"IMPOSTO SELETIVO   -> Total IS: R$ {vIS_tot}")
            else:
                soma_is = sum(to_decimal(imp['valor']) for itm in dados_estruturados['itens'] for imp in itm['impostos'] if imp['tributo'] == 'IS')
                totais_dict['vIS'] = f"{soma_is:.2f}"

            if icmsTot is not None:
                linhas.append(f"IPI TOTAL   -> Valor IPI: R$ {vIPI_tot}")
                linhas.append(f"PIS/COFINS  -> Total PIS: R$ {vPIS_tot} | Total COFINS: R$ {vCOFINS_tot}")
                
            linhas.append("="*80 + "\n")

        dados_estruturados['totais'] = totais_dict

        if retornar_estruturado:
            return "\n".join(linhas), chave_xml, dados_estruturados
        return "\n".join(linhas), chave_xml
    except Exception as e:
        if retornar_estruturado:
            return f"Ocorreu um erro ao processar o XML:\n{str(e)}", "", {}
        return f"Ocorreu um erro ao processar o XML:\n{str(e)}", ""

def validar_chave_live(*args):
    """Valida a chave em tempo real enquanto o usuário digita ou cola."""
    global chave_xml_atual
    chave_portal = ''.join(filter(str.isdigit, var_chave_portal.get()))
    
    if not chave_xml_atual:
        lbl_resultado_chave.config(text="")
        return
        
    if not chave_portal:
        lbl_resultado_chave.config(text="⚠️ Aguardando chave...", foreground="#d97706")
    elif chave_portal == chave_xml_atual:
        lbl_resultado_chave.config(text="✔️ CERTO (Chaves iguais)", foreground="#16a34a")
    else:
        lbl_resultado_chave.config(text="❌ ERRADO (Chaves diferentes)", foreground="#dc2626")

def criar_campo_copiavel(parent, valor_str, nome_campo="", width=12, justify="right", font_size=9):
    """
    Cria um campo readonly com visual de célula do Datasul.
    Ao clicar 1 vez:
    - Copia o número para o clipboard com vírgula e sem ponto de milhar
    - Pisca a caixinha em verde suave (#bbf7d0) por 350ms
    - Atualiza a barra de status com mensagem de confirmação
    """
    val_copia = str(valor_str).strip()
    
    e = tk.Entry(
        parent,
        font=("Segoe UI", font_size, "bold"),
        width=width,
        justify=justify,
        relief="solid",
        bd=1,
        cursor="hand2"
    )
    e.insert(0, val_copia)
    e.configure(state='readonly', readonlybackground="#ffffff", fg="#0f172a")
    
    def on_click(event):
        try:
            janela.clipboard_clear()
            janela.clipboard_append(val_copia)
            janela.update()
        except Exception:
            pass
        
        e.configure(readonlybackground="#bbf7d0")
        e.after(350, lambda: e.configure(readonlybackground="#ffffff"))
        e.select_range(0, tk.END)
        
        lbl_status_copia.config(
            text=f"📋 Copiado: {val_copia} ({nome_campo}) — Pronto para colar no Datasul!",
            foreground="#15803d"
        )
    
    def on_enter(event):
        if e.cget('readonlybackground') != "#bbf7d0":
            e.configure(readonlybackground="#f1f5f9")
            
    def on_leave(event):
        if e.cget('readonlybackground') != "#bbf7d0":
            e.configure(readonlybackground="#ffffff")

    e.bind("<Button-1>", on_click)
    e.bind("<Enter>", on_enter)
    e.bind("<Leave>", on_leave)
    return e

def renderizar_totais_card(parent_frame, totais_data):
    """Renderiza os Totais da Nota Fiscal ao final da lista de itens, rolando naturalmente junto com a tela."""
    card = tk.LabelFrame(
        parent_frame,
        text="  TOTAIS DA NOTA FISCAL (CONFERÊNCIA & DIGITAÇÃO NO DATASUL)  ",
        font=("Segoe UI", 10, "bold"),
        fg="#1e3a8a",
        bg="#ffffff",
        padx=12,
        pady=10,
        relief="solid",
        bd=1
    )
    card.pack(fill="x", padx=10, pady=(10, 20))
    
    # Linha 1: Valores Comerciais
    f1 = tk.Frame(card, bg="#ffffff")
    f1.pack(fill="x", pady=2)
    
    col1 = 0
    def add_tot_field(label_txt, val_txt, desc_campo, width=12):
        nonlocal col1
        l = tk.Label(f1, text=label_txt, font=("Segoe UI", 9), bg="#ffffff", fg="#475569")
        l.grid(row=0, column=col1, padx=(8 if col1 > 0 else 0, 2), sticky="w")
        col1 += 1
        c = criar_campo_copiavel(f1, format_datasul(val_txt), desc_campo, width=width)
        c.grid(row=0, column=col1, padx=(0, 8), sticky="w")
        col1 += 1

    add_tot_field("Vlr Produtos:", totais_data.get('vProd', '0.00'), "Total Produtos", width=12)
    add_tot_field("Total da NF (vNF):", totais_data.get('vNF', '0.00'), "Valor Total da Nota", width=12)
    add_tot_field("Frete:", totais_data.get('vFrete', '0.00'), "Total Frete", width=10)
    add_tot_field("Seguro:", totais_data.get('vSeg', '0.00'), "Total Seguro", width=10)
    add_tot_field("Desconto:", totais_data.get('vDesc', '0.00'), "Total Desconto", width=10)
    add_tot_field("Outras:", totais_data.get('vOutro', '0.00'), "Total Outras Despesas", width=10)

    # Linha 2: Tributos na ordem estrita: ICMS > CBS > IBS > IS > IPI > PIS/COFINS
    f2 = tk.Frame(card, bg="#ffffff")
    f2.pack(fill="x", pady=(6, 2))
    
    col2 = 0
    def add_trib_tot_field(label_txt, val_txt, desc_campo, width=11):
        nonlocal col2
        l = tk.Label(f2, text=label_txt, font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#1e293b")
        l.grid(row=0, column=col2, padx=(8 if col2 > 0 else 0, 2), sticky="w")
        col2 += 1
        c = criar_campo_copiavel(f2, format_datasul(val_txt), desc_campo, width=width)
        c.grid(row=0, column=col2, padx=(0, 8), sticky="w")
        col2 += 1

    add_trib_tot_field("ICMS:", totais_data.get('vICMS', '0.00'), "ICMS Total")
    add_trib_tot_field("CBS:", totais_data.get('vCBS', '0.00'), "CBS Total")
    add_trib_tot_field("IBS:", totais_data.get('vIBS', '0.00'), "IBS Total")
    add_trib_tot_field("IS:", totais_data.get('vIS', '0.00'), "IS Total")
    add_trib_tot_field("IPI:", totais_data.get('vIPI', '0.00'), "IPI Total")
    add_trib_tot_field("PIS:", totais_data.get('vPIS', '0.00'), "PIS Total")
    add_trib_tot_field("COFINS:", totais_data.get('vCOFINS', '0.00'), "COFINS Total")

def renderizar_item_card(parent_frame, item_data):
    """Renderiza um card visual completo para um item da NF-e no estilo da tela do Datasul."""
    card = tk.Frame(parent_frame, bg="#ffffff", relief="solid", bd=1)
    card.pack(fill="x", padx=10, pady=(0, 15))
    
    # 1. Header do Item (Barra Azul de Destaque)
    header = tk.Frame(card, bg="#1e3a8a", padx=10, pady=6)
    header.pack(fill="x")
    
    lbl_item_titulo = tk.Label(
        header,
        text=f"ITEM {str(item_data['num']).zfill(2)}: {item_data['cProd']} - {item_data['xProd']}",
        font=("Segoe UI", 10, "bold"),
        bg="#1e3a8a",
        fg="#ffffff"
    )
    lbl_item_titulo.pack(side="left")
    
    def copiar_item_resumo():
        resumo = f"Item {item_data['num']} | NCM: {item_data['ncm']} | CFOP: {item_data['cfop']} | Qtd: {format_datasul_qtd(item_data['qCom'])} | Vl Unit: {format_datasul(item_data['vUnCom'])} | Total: {format_datasul(item_data['vProd'])}"
        janela.clipboard_clear()
        janela.clipboard_append(resumo)
        lbl_status_copia.config(text=f"📋 Copiado resumo do Item {item_data['num']}!", foreground="#15803d")
        
    btn_copiar_item = tk.Button(
        header,
        text="📋 Copiar Linha do Item",
        font=("Segoe UI", 8, "bold"),
        bg="#3b82f6",
        fg="white",
        activebackground="#2563eb",
        relief="flat",
        cursor="hand2",
        command=copiar_item_resumo,
        padx=6,
        pady=1
    )
    btn_copiar_item.pack(side="right")
    
    # 2. Barra de Dados Cadastrais (Cinza Claro)
    dados_cad = tk.Frame(card, bg="#f8fafc", padx=10, pady=8)
    dados_cad.pack(fill="x")
    
    col_idx = 0
    def add_cad_field(label_txt, val_txt, campo_nome, width=10):
        nonlocal col_idx
        lbl = tk.Label(dados_cad, text=label_txt, font=("Segoe UI", 9), bg="#f8fafc", fg="#475569")
        lbl.grid(row=0, column=col_idx, padx=(6 if col_idx > 0 else 0, 2), sticky="w")
        col_idx += 1
        campo = criar_campo_copiavel(dados_cad, val_txt, f"{campo_nome} - Item {item_data['num']}", width=width)
        campo.grid(row=0, column=col_idx, padx=(0, 6), sticky="w")
        col_idx += 1

    add_cad_field("Cód:", item_data['cProd'], "Código", width=10)
    add_cad_field("NCM:", item_data['ncm'], "NCM", width=10)
    add_cad_field("CFOP:", item_data['cfop'], "CFOP", width=6)
    add_cad_field("Qtd:", f"{format_datasul_qtd(item_data['qCom'])} {item_data['uCom']}", "Quantidade", width=10)
    add_cad_field("Vl Unit:", format_datasul(item_data['vUnCom']), "Valor Unitário", width=10)
    add_cad_field("Vl Total:", format_datasul(item_data['vProd']), "Valor Total", width=11)
    if to_decimal(item_data.get('vFrete', 0)) > 0:
        add_cad_field("Frete:", format_datasul(item_data['vFrete']), "Frete", width=9)
    if to_decimal(item_data.get('vDesc', 0)) > 0:
        add_cad_field("Desc:", format_datasul(item_data['vDesc']), "Desconto", width=9)

    # 3. Tabela de Impostos (Estilo Tela do Datasul)
    frame_tabela = tk.Frame(card, bg="#ffffff", padx=10, pady=8)
    frame_tabela.pack(fill="x")
    
    headers = [
        ("Tributo", 14, "w"),
        ("CST", 7, "center"),
        ("Base de Cálculo", 16, "e"),
        ("Alíquota (%)", 14, "e"),
        ("Valor do Imposto", 16, "e"),
        ("Auditoria / Detalhes do Cálculo", 38, "w")
    ]
    
    hdr_frame = tk.Frame(frame_tabela, bg="#e2e8f0")
    hdr_frame.pack(fill="x", pady=(0, 4))
    
    for h_title, h_width, h_anchor in headers:
        lbl_h = tk.Label(
            hdr_frame,
            text=h_title,
            font=("Segoe UI", 9, "bold"),
            bg="#e2e8f0",
            fg="#334155",
            width=h_width,
            anchor=h_anchor,
            padx=4,
            pady=3
        )
        lbl_h.pack(side="left", padx=2)
        
    for imp in item_data['impostos']:
        row_frame = tk.Frame(frame_tabela, bg="#ffffff", pady=2)
        row_frame.pack(fill="x")
        
        # Tributo (escrito chapado, em negrito)
        lbl_trib = tk.Label(
            row_frame,
            text=imp['tributo'],
            font=("Segoe UI", 9, "bold"),
            bg="#ffffff",
            fg="#1e293b",
            width=14,
            anchor="w",
            padx=4
        )
        lbl_trib.pack(side="left", padx=2)
        
        # CST (caixinha clicável)
        cst_box = criar_campo_copiavel(
            row_frame,
            imp['cst'],
            f"CST {imp['tributo']} - Item {item_data['num']}",
            width=7,
            justify="center"
        )
        cst_box.pack(side="left", padx=2)
        
        # Base de Cálculo (caixinha clicável com vírgula)
        base_val = format_datasul(imp['base']) if imp['base'] != '-' else '-'
        base_box = criar_campo_copiavel(
            row_frame,
            base_val,
            f"Base {imp['tributo']} - Item {item_data['num']}",
            width=16,
            justify="right"
        )
        base_box.pack(side="left", padx=2)
        
        # Alíquota (%) (caixinha clicável com vírgula)
        aliq_val = format_datasul_aliq(imp['aliq']) if imp['aliq'] != '-' else '-'
        aliq_box = criar_campo_copiavel(
            row_frame,
            aliq_val,
            f"Alíquota {imp['tributo']} - Item {item_data['num']}",
            width=14,
            justify="right"
        )
        aliq_box.pack(side="left", padx=2)
        
        # Valor do Imposto (caixinha clicável com vírgula)
        vlr_val = format_datasul(imp['valor']) if imp['valor'] != '-' else '-'
        vlr_box = criar_campo_copiavel(
            row_frame,
            vlr_val,
            f"Valor {imp['tributo']} - Item {item_data['num']}",
            width=16,
            justify="right"
        )
        vlr_box.pack(side="left", padx=2)
        
        # Auditoria / Detalhes
        status_txt = imp.get('status', '')
        fg_status = "#475569"
        if "✔️" in status_txt or "Conforme" in status_txt:
            fg_status = "#16a34a"
        elif "⚠️" in status_txt or "Divergência" in status_txt:
            fg_status = "#dc2626"
            
        lbl_stat = tk.Label(
            row_frame,
            text=status_txt,
            font=("Segoe UI", 9, "bold" if ("✔️" in status_txt or "⚠️" in status_txt) else "normal"),
            bg="#ffffff",
            fg=fg_status,
            anchor="w",
            padx=6
        )
        lbl_stat.pack(side="left", padx=2, fill="x", expand=True)

def renderizar_visao_datasul(dados):
    """Renderiza a Visão Datasul completa (Cards de Itens + Totais ao final, rolando naturalmente)."""
    for w in frame_itens_scroll.winfo_children():
        w.destroy()
        
    if not dados or not dados.get('itens'):
        lbl_aviso = tk.Label(
            frame_itens_scroll,
            text="Nenhum item encontrado no arquivo selecionado.",
            font=("Segoe UI", 11),
            fg="#64748b",
            bg="#f4f6f9",
            pady=40
        )
        lbl_aviso.pack()
        return
        
    # Título da seção de itens
    lbl_sec = tk.Label(
        frame_itens_scroll,
        text="ITENS DA NOTA FISCAL (DIGITAÇÃO NO DATASUL — CLIQUE NO NÚMERO PARA COPIAR COM VÍRGULA)",
        font=("Segoe UI", 10, "bold"),
        fg="#1e3a8a",
        bg="#f4f6f9",
        pady=4
    )
    lbl_sec.pack(anchor="w", padx=10, pady=(6, 6))
    
    # 1. Renderiza cada item
    for item in dados.get('itens', []):
        renderizar_item_card(frame_itens_scroll, item)
        
    # 2. Renderiza Totais da Nota Fiscal AO FINAL, rolando junto com os itens (não fixo!)
    renderizar_totais_card(frame_itens_scroll, dados.get('totais', {}))
        
    # Rola para o topo e seleciona a aba Datasul
    canvas_itens.yview_moveto(0)
    notebook.select(0)

def inserir_texto_com_destaques(widget, texto_completo):
    """
    Insere o relatório em modo texto corrido aplicando negrito em todos os valores
    fiscais, monetários, percentuais e códigos (conforme solicitado pelo usuário).
    """
    widget.config(state=tk.NORMAL)
    widget.delete(1.0, tk.END)
    
    widget.tag_config("normal", font=("Consolas", 10), foreground="#2d3748")
    widget.tag_config("negrito", font=("Consolas", 10, "bold"), foreground="#0f172a")
    widget.tag_config("titulo", font=("Consolas", 10, "bold"), foreground="#1e3a8a")
    widget.tag_config("separador", font=("Consolas", 10), foreground="#94a3b8")
    widget.tag_config("conforme", font=("Consolas", 10, "bold"), foreground="#15803d")
    widget.tag_config("divergencia", font=("Consolas", 10, "bold"), foreground="#dc2626")
    
    # Regex para capturar valores fiscais, monetários (R$), alíquotas (%) e códigos numéricos
    padrao_valor = re.compile(r'(R\$\s*[\d\.,]+|\b\d+[\.,]\d+%?|\b(?:\d{4,8})\b)')
    
    for linha in texto_completo.split('\n'):
        linha_strip = linha.strip()
        if not linha_strip:
            widget.insert(tk.END, "\n")
            continue
            
        # Linhas de divisores e títulos
        if linha_strip.startswith('===') or linha_strip.startswith('---'):
            if 'ITEM' in linha:
                widget.insert(tk.END, linha + "\n", ("titulo",))
            else:
                widget.insert(tk.END, linha + "\n", ("separador",))
            continue
            
        if (linha_strip.startswith('DADOS GERAIS') or 
            linha_strip.startswith('TOTAIS DA NOTA FISCAL') or 
            linha_strip.startswith('COBRANÇA')):
            widget.insert(tk.END, linha + "\n", ("titulo",))
            continue
            
        # Linha comum: destaca valores numéricos em negrito
        pos = 0
        matches = list(padrao_valor.finditer(linha))
        for m in matches:
            start, end = m.start(), m.end()
            if start > pos:
                widget.insert(tk.END, linha[pos:start], ("normal",))
            widget.insert(tk.END, linha[start:end], ("negrito",))
            pos = end
        if pos < len(linha):
            widget.insert(tk.END, linha[pos:] + "\n", ("normal",))
        else:
            widget.insert(tk.END, "\n")
            
    widget.config(state=tk.DISABLED)

def copiar_valor_do_texto(event):
    """Permite dar clique duplo em qualquer valor no modo texto corrido para copiar com vírgula."""
    try:
        idx = area_texto.index(f"@{event.x},{event.y}")
        start = area_texto.index(f"{idx} wordstart")
        end = area_texto.index(f"{idx} wordend")
        palavra = area_texto.get(start, end).strip()
        
        # Se selecionou o 'R$', avança para o número seguinte
        if palavra == "R$":
            palavra = area_texto.get(end, f"{end} wordend + 1 word").strip()
            
        num_limpo = re.sub(r'[^\d\.,]', '', palavra)
        if num_limpo:
            val_fmt = format_datasul(num_limpo)
            janela.clipboard_clear()
            janela.clipboard_append(val_fmt)
            lbl_status_copia.config(
                text=f"📋 Copiado do texto: {val_fmt} — Pronto para colar no Datasul!",
                foreground="#15803d"
            )
    except Exception:
        pass

def selecionar_arquivo():
    global chave_xml_atual, dados_nfe_atual
    try:
        aliq_interna_informada = float(var_aliquota_int.get().replace(',', '.'))
        aliq_inter_informada = float(var_aliquota_ext.get().replace(',', '.'))
        aliq_icms_informada = float(var_aliquota_icms.get().replace(',', '.'))
        aliq_cbs_informada = float(var_aliquota_cbs.get().replace(',', '.'))
        aliq_ibs_informada = float(var_aliquota_ibs.get().replace(',', '.'))
    except ValueError:
        messagebox.showerror("Erro", "Por favor, insira valores numéricos válidos para as alíquotas (ex: 22.0 ou 0.90).")
        return
        
    caminho = filedialog.askopenfilename(
        title="Selecione o arquivo XML da NF-e",
        filetypes=(("Arquivos XML", "*.xml"), ("Todos os arquivos", "*.*"))
    )
    if caminho:
        resultado_texto, chave_xml_atual, dados_estruturados = extrair_dados_xml(
            caminho,
            aliq_interna_informada,
            aliq_inter_informada,
            aliq_icms_informada,
            aliq_cbs_padrao=aliq_cbs_informada,
            aliq_ibs_padrao=aliq_ibs_informada,
            retornar_estruturado=True
        )
        dados_nfe_atual = dados_estruturados
        
        # Dispara a validação visual da chave
        validar_chave_live()
        
        # Atualiza o espelho em texto (Aba 2) com formatação em negrito nos valores
        inserir_texto_com_destaques(area_texto, resultado_texto)
        
        # Renderiza a Visão Datasul (Aba 1) com Totais ao final rolando naturalmente
        renderizar_visao_datasul(dados_estruturados)
        
        lbl_status_copia.config(
            text=f"✔️ XML Carregado: NF {dados_estruturados.get('ide', {}).get('nNF', '')} ({len(dados_estruturados.get('itens', []))} itens). Clique em qualquer valor para copiar!",
            foreground="#15803d"
        )

def copiar_resultado():
    """Copia o conteúdo do espelho de texto para a área de transferência."""
    texto = area_texto.get(1.0, tk.END).strip()
    if texto:
        janela.clipboard_clear()
        janela.clipboard_append(texto)
        messagebox.showinfo("Copiado", "Espelho completo da nota copiado para a área de transferência!")

def limpar_tela():
    """Zera todos os campos, abas e área de texto para uma nova leitura."""
    global chave_xml_atual, dados_nfe_atual
    chave_xml_atual = ""
    dados_nfe_atual = {}
    var_chave_portal.set("")
    lbl_resultado_chave.config(text="")
    
    area_texto.config(state=tk.NORMAL)
    area_texto.delete(1.0, tk.END)
    area_texto.config(state=tk.DISABLED)
    
    for w in frame_itens_scroll.winfo_children():
        w.destroy()
        
    lbl_placeholder = tk.Label(
        frame_itens_scroll,
        text="📁 Clique em 'Selecionar Arquivo XML' acima para carregar e auditar a NF-e.",
        font=("Segoe UI", 11),
        fg="#64748b",
        bg="#f4f6f9",
        pady=80
    )
    lbl_placeholder.pack()
    
    lbl_status_copia.config(
        text="💡 Dica: Dê 1 clique em qualquer número para copiar para o Datasul (com vírgula).",
        foreground="#475569"
    )

def resource_path(relative_path):
    """Retorna o caminho absoluto do recurso, compatível com PyInstaller e execução direta."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# Identificador explícito do app no Windows
try:
    import ctypes
    myappid = 'balthazar.ia.extratornfe.datasul'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

# --- Configuração da Interface Gráfica Moderna ---
janela = tk.Tk()
janela.title("Leitor de XML NF-e & Auditor Oficial RTC - Balthazar IA")
janela.geometry("1100x880")
janela.configure(bg="#f4f6f9")

# Ícone nativo da janela e barra de tarefas (.ico ajustado)
icon_ico = resource_path("app_icon.ico")
if os.path.exists(icon_ico):
    try:
        janela.iconbitmap(icon_ico)
    except Exception:
        pass

# Imagem PNG ajustada para o ícone
for img_name in ["app_icon.png", "logo_original.png"]:
    img_path = resource_path(img_name)
    if os.path.exists(img_path):
        try:
            janela._icon_img = tk.PhotoImage(file=img_path)
            janela.iconphoto(True, janela._icon_img)
            break
        except Exception:
            pass

# Define um tema mais limpo para o aplicativo
estilo = ttk.Style()
estilo.theme_use("clam")

# Customizando cores e fontes
estilo.configure("TFrame", background="#f4f6f9")
estilo.configure("TLabelframe", background="#f4f6f9", borderwidth=2)
estilo.configure("TLabelframe.Label", background="#f4f6f9", font=("Segoe UI", 11, "bold"), foreground="#1e3a8a")
estilo.configure("TLabel", background="#f4f6f9", foreground="#333333", font=("Segoe UI", 10))
estilo.configure("Titulo.TLabel", font=("Segoe UI", 16, "bold"), foreground="#1e3a8a")

# Botões Padrões e Secundários
estilo.configure("Principal.TButton", font=("Segoe UI", 11, "bold"), padding=8, background="#2563eb", foreground="white")
estilo.map("Principal.TButton", background=[("active", "#1d4ed8")])
estilo.configure("Acao.TButton", font=("Segoe UI", 10, "bold"), padding=6, background="#475569", foreground="white")
estilo.map("Acao.TButton", background=[("active", "#334155")])
estilo.configure("Limpar.TButton", font=("Segoe UI", 10, "bold"), padding=6, background="#ef4444", foreground="white")
estilo.map("Limpar.TButton", background=[("active", "#b91c1c")])

# Container superior
frame_topo = ttk.Frame(janela)
frame_topo.pack(pady=10, fill="x", padx=20)

lbl_titulo = ttk.Label(frame_topo, text="Extrator de Dados para Implantação Datasul & Auditoria RTC", style="Titulo.TLabel")
lbl_titulo.pack(pady=(0, 3))

lbl_instrucao = ttk.Label(frame_topo, text="Padrão Datasul: Impostos em ordem estrita (ICMS > CBS > IBS UF > IBS MUN > IS > IPI > PIS/COFINS) com 1 clique para copiar.")
lbl_instrucao.pack(pady=(0, 8))

# --- GRUPO DE CONFIGURAÇÕES E VALIDAÇÃO (LabelFrame) ---
frame_config = ttk.LabelFrame(frame_topo, text="Parâmetros de Cálculo & Validação", padding=(12, 8))
frame_config.pack(fill="x", pady=(0, 8))

frame_config.columnconfigure(1, weight=1)
frame_config.columnconfigure(3, weight=1)

# Linha 0: DIFAL
lbl_aliq_int = ttk.Label(frame_config, text="DIFAL - Alíq. Interna Padrão (%):")
lbl_aliq_int.grid(row=0, column=0, padx=(0, 5), pady=3, sticky="e")
var_aliquota_int = tk.StringVar(value="22.0")
entry_aliq_int = ttk.Entry(frame_config, textvariable=var_aliquota_int, width=8, justify="center")
entry_aliq_int.grid(row=0, column=1, padx=(0, 15), pady=3, sticky="w")

lbl_aliq_ext = ttk.Label(frame_config, text="DIFAL - Alíq. Interestadual (se faltar) (%):")
lbl_aliq_ext.grid(row=0, column=2, padx=(0, 5), pady=3, sticky="e")
var_aliquota_ext = tk.StringVar(value="12.0")
entry_aliq_ext = ttk.Entry(frame_config, textvariable=var_aliquota_ext, width=8, justify="center")
entry_aliq_ext.grid(row=0, column=3, pady=3, sticky="w")

# Linha 1: ICMS Normal e CBS de Transição
lbl_aliq_icms = ttk.Label(frame_config, text="ICMS Normal (se faltar no XML) (%):")
lbl_aliq_icms.grid(row=1, column=0, padx=(0, 5), pady=3, sticky="e")
var_aliquota_icms = tk.StringVar(value="20.0")
entry_aliq_icms = ttk.Entry(frame_config, textvariable=var_aliquota_icms, width=8, justify="center")
entry_aliq_icms.grid(row=1, column=1, padx=(0, 15), pady=3, sticky="w")

lbl_aliq_cbs = ttk.Label(frame_config, text="CBS Transição (se faltar no XML) (%):")
lbl_aliq_cbs.grid(row=1, column=2, padx=(0, 5), pady=3, sticky="e")
var_aliquota_cbs = tk.StringVar(value="0.90")
entry_aliq_cbs = ttk.Entry(frame_config, textvariable=var_aliquota_cbs, width=8, justify="center")
entry_aliq_cbs.grid(row=1, column=3, pady=3, sticky="w")

# Linha 2: IBS de Transição
lbl_aliq_ibs = ttk.Label(frame_config, text="IBS Transição (se faltar no XML) (%):")
lbl_aliq_ibs.grid(row=2, column=0, padx=(0, 5), pady=3, sticky="e")
var_aliquota_ibs = tk.StringVar(value="0.10")
entry_aliq_ibs = ttk.Entry(frame_config, textvariable=var_aliquota_ibs, width=8, justify="center")
entry_aliq_ibs.grid(row=2, column=1, padx=(0, 15), pady=3, sticky="w")

# Linha 3: Verificação de Chave de Acesso
lbl_chave = ttk.Label(frame_config, text="Chave de Acesso do Portal:")
lbl_chave.grid(row=3, column=0, padx=(0, 5), pady=(8, 3), sticky="e")
var_chave_portal = tk.StringVar(value="")
var_chave_portal.trace_add("write", validar_chave_live)

entry_chave = ttk.Entry(frame_config, textvariable=var_chave_portal, width=48, justify="center")
entry_chave.grid(row=3, column=1, columnspan=2, padx=(0, 10), pady=(8, 3), sticky="we")

lbl_resultado_chave = ttk.Label(frame_config, text="", font=("Segoe UI", 10, "bold"))
lbl_resultado_chave.grid(row=3, column=3, padx=(0, 5), pady=(8, 3), sticky="w")

# Container para os botões de ação
frame_botoes = ttk.Frame(frame_topo)
frame_botoes.pack(pady=6)

btn_abrir = ttk.Button(frame_botoes, text="📁 Selecionar Arquivo XML", command=selecionar_arquivo, style="Principal.TButton", cursor="hand2")
btn_abrir.grid(row=0, column=0, padx=6)

btn_copiar = ttk.Button(frame_botoes, text="📋 Copiar Espelho Completo (Texto)", command=copiar_resultado, style="Acao.TButton", cursor="hand2")
btn_copiar.grid(row=0, column=1, padx=6)

btn_limpar = ttk.Button(frame_botoes, text="🗑️ Limpar Tudo", command=limpar_tela, style="Limpar.TButton", cursor="hand2")
btn_limpar.grid(row=0, column=2, padx=6)

# --- NOTEBOOK COM ABAS (VISÃO DATASUL & ESPELHO EM TEXTO) ---
frame_conteudo = ttk.Frame(janela)
frame_conteudo.pack(expand=True, fill='both', padx=20, pady=(0, 8))

notebook = ttk.Notebook(frame_conteudo)
notebook.pack(expand=True, fill='both')

tab_datasul = ttk.Frame(notebook)
tab_texto = ttk.Frame(notebook)

notebook.add(tab_datasul, text="  🖥️ Tela Datasul (Clique para Copiar)  ")
notebook.add(tab_texto, text="  📄 Espelho em Texto (Relatório Completo)  ")

# --- CONTEÚDO DA ABA 1: VISÃO DATASUL (TOTAIS AO FINAL ROLANDO NATURALMENTE) ---
canvas_itens = tk.Canvas(tab_datasul, bg="#f4f6f9", highlightthickness=0)
vbar_itens = ttk.Scrollbar(tab_datasul, orient="vertical", command=canvas_itens.yview)
canvas_itens.configure(yscrollcommand=vbar_itens.set)

vbar_itens.pack(side="right", fill="y")
canvas_itens.pack(side="left", fill="both", expand=True)

frame_itens_scroll = tk.Frame(canvas_itens, bg="#f4f6f9")
canvas_itens_window = canvas_itens.create_window((0, 0), window=frame_itens_scroll, anchor="nw")

def _on_frame_configure(event):
    canvas_itens.configure(scrollregion=canvas_itens.bbox("all"))

def _on_canvas_configure(event):
    canvas_itens.itemconfig(canvas_itens_window, width=event.width)

frame_itens_scroll.bind("<Configure>", _on_frame_configure)
canvas_itens.bind("<Configure>", _on_canvas_configure)

def _on_mousewheel(event):
    if notebook.index(notebook.select()) == 0:
        canvas_itens.yview_scroll(int(-1 * (event.delta / 120)), "units")

canvas_itens.bind_all("<MouseWheel>", _on_mousewheel)

# Placeholder inicial na aba Datasul
lbl_placeholder_init = tk.Label(
    frame_itens_scroll,
    text="📁 Clique em 'Selecionar Arquivo XML' acima para carregar e auditar a NF-e.",
    font=("Segoe UI", 11),
    fg="#64748b",
    bg="#f4f6f9",
    pady=80
)
lbl_placeholder_init.pack()

# --- CONTEÚDO DA ABA 2: ESPELHO EM TEXTO (COM VALORES EM NEGRITO) ---
area_texto = scrolledtext.ScrolledText(
    tab_texto,
    wrap=tk.WORD,
    font=("Consolas", 10),
    bg="#ffffff",
    fg="#2d3748",
    relief="flat",
    padx=10,
    pady=10
)
area_texto.pack(expand=True, fill='both')
area_texto.config(state=tk.DISABLED)
area_texto.bind("<Double-Button-1>", copiar_valor_do_texto)

# --- BARRA DE STATUS INFERIOR ---
frame_status = tk.Frame(janela, bg="#e2e8f0", padx=15, pady=6)
frame_status.pack(side="bottom", fill="x")

lbl_status_copia = tk.Label(
    frame_status,
    text="💡 Dica: Dê 1 clique em qualquer número para copiar para o Datasul (com vírgula).",
    font=("Segoe UI", 9, "bold"),
    bg="#e2e8f0",
    fg="#475569"
)
lbl_status_copia.pack(side="left")

if __name__ == '__main__':
    janela.mainloop()
