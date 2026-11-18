import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import os
import sys
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

# Variável global para manter a chave lida do XML e permitir validação em tempo real
chave_xml_atual = ""

def remove_namespace(doc, namespace):
    """Remove o namespace do XML para facilitar a busca pelas tags."""
    ns = u'{%s}' % namespace
    nsl = len(ns)
    for elem in doc.iter():
        if elem.tag.startswith(ns):
            elem.tag = elem.tag[nsl:]

def extrair_dados_xml(caminho_arquivo, aliq_interna_informada=0.0, aliq_inter_informada=0.0, aliq_icms_informada=0.0, aliq_cbs_padrao=0.9, aliq_ibs_padrao=0.1):
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
                if icms is not None:
                    for child in icms: 
                        cst = child.find('CST') if child.find('CST') is not None else child.find('CSOSN')
                        orig = child.find('orig')
                        
                        cst_txt = cst.text if cst is not None else 'N/A'
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
                        else:
                            try:
                                base_calc = float(vProd) if vProd else 0.0
                                if aliq_icms_informada > 0:
                                    valor_icms_calc = base_calc * (aliq_icms_informada / 100)
                                    linhas.append(f"       ICMS Normal -> [CÁLC. PRESUMIDO] BC: {base_calc:.2f} | Alíq (Tela): {aliq_icms_informada:.2f}% | Valor: {valor_icms_calc:.2f}")
                                else:
                                    linhas.append(f"       ICMS Normal -> Não destacado no XML (Preenchimento Manual)")
                            except Exception:
                                linhas.append(f"       ICMS Normal -> Não destacado no XML (Preenchimento Manual)")
                        
                        # FCP Normal
                        vBCFCP = child.find('vBCFCP')
                        pFCP = child.find('pFCP')
                        vFCP = child.find('vFCP')
                        
                        if vFCP is not None or vBCFCP is not None:
                            bc_fcp = vBCFCP.text if vBCFCP is not None else (vBC.text if vBC is not None else '0.00')
                            aliq_fcp = pFCP.text if pFCP is not None else '0.00'
                            val_fcp = vFCP.text if vFCP is not None else '0.00'
                            linhas.append(f"       FCP Normal  -> BC FCP: {bc_fcp} | Alíq FCP: {aliq_fcp}% | Valor FCP: {val_fcp}")

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
                        
                        # FCP ST
                        vBCFCPST = child.find('vBCFCPST')
                        pFCPST = child.find('pFCPST')
                        vFCPST = child.find('vFCPST')
                        
                        if vFCPST is not None:
                            bc_fcpst = vBCFCPST.text if vBCFCPST is not None else '0'
                            aliq_fcpst = pFCPST.text if pFCPST is not None else '0'
                            val_fcpst = vFCPST.text if vFCPST is not None else '0'
                            linhas.append(f"       FCP ST      -> BC FCP ST: {bc_fcpst} | Alíq FCP ST: {aliq_fcpst}% | Valor FCP ST: {val_fcpst}")

                # 2. Extração de DIFAL (ICMSUFDest) ou Cálculo Presumido
                icms_uf_dest = imposto.find('ICMSUFDest')
                if icms_uf_dest is not None:
                    vbc_uf_dest = icms_uf_dest.find('vBCUFDest').text if icms_uf_dest.find('vBCUFDest') is not None else '0.00'
                    p_icms_uf_dest = icms_uf_dest.find('pICMSUFDest').text if icms_uf_dest.find('pICMSUFDest') is not None else '0.00'
                    p_icms_inter = icms_uf_dest.find('pICMSInter').text if icms_uf_dest.find('pICMSInter') is not None else '0.00'
                    v_icms_uf_dest = icms_uf_dest.find('vICMSUFDest').text if icms_uf_dest.find('vICMSUFDest') is not None else '0.00'
                    
                    linhas.append(f"       DIFAL       -> BC: {vbc_uf_dest} | Alíq Inter: {p_icms_inter}% | Alíq Dest ({dest_uf}): {p_icms_uf_dest}%")
                    linhas.append(f"       (Lançar no Datasul -> Base ICMS Compl.: {vbc_uf_dest} | Valor ICMS Compl.: {v_icms_uf_dest})")
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
                            else:
                                linhas.append(f"       DIFAL       -> ATENÇÃO: Alíquota interestadual ({aliq_inter}%) é maior ou igual à interna informada ({aliq_interna_informada}%).")
                        else:
                            linhas.append(f"       DIFAL       -> ATENÇÃO: Operação Interestadual sem alíquota ICMS. Informe na tela principal.")
                    except Exception:
                        linhas.append(f"       DIFAL       -> ATENÇÃO: Operação Interestadual (CFOP {cfop}). Cálculo manual necessário.")

                # 3. Extração de IPI (Imposto sobre Produtos Industrializados)
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
                    else:
                        ipi_nt = ipi.find('IPINT')
                        if ipi_nt is not None:
                            cst_ipi = ipi_nt.find('CST').text if ipi_nt.find('CST') is not None else 'N/A'
                            linhas.append(f"[IPI] Não tributado (CST: {cst_ipi} | cEnq: {cEnq})")

                # 4. Extração de PIS e COFINS
                pis = imposto.find('PIS')
                cofins = imposto.find('COFINS')
                pis_part = ""
                cofins_part = ""
                if pis is not None:
                    for p_child in pis:
                        cst_p = p_child.find('CST').text if p_child.find('CST') is not None else 'N/A'
                        vbc_p = p_child.find('vBC').text if p_child.find('vBC') is not None else '0.00'
                        aliq_p = p_child.find('pPIS').text if p_child.find('pPIS') is not None else '0.00'
                        val_p = p_child.find('vPIS').text if p_child.find('vPIS') is not None else '0.00'
                        if to_decimal(val_p) > 0 or to_decimal(vbc_p) > 0:
                            pis_part = f"PIS (CST {cst_p}) -> BC: R$ {vbc_p} | Alíq: {aliq_p}% | Valor: R$ {val_p}"
                        else:
                            pis_part = f"PIS (CST {cst_p}) -> Sem destaque"
                        break
                if cofins is not None:
                    for c_child in cofins:
                        cst_c = c_child.find('CST').text if c_child.find('CST') is not None else 'N/A'
                        vbc_c = c_child.find('vBC').text if c_child.find('vBC') is not None else '0.00'
                        aliq_c = c_child.find('pCOFINS').text if c_child.find('pCOFINS') is not None else '0.00'
                        val_c = c_child.find('vCOFINS').text if c_child.find('vCOFINS') is not None else '0.00'
                        if to_decimal(val_c) > 0 or to_decimal(vbc_c) > 0:
                            cofins_part = f"COFINS (CST {cst_c}) -> BC: R$ {vbc_c} | Alíq: {aliq_c}% | Valor: R$ {val_c}"
                        else:
                            cofins_part = f"COFINS (CST {cst_c}) -> Sem destaque"
                        break
                if pis_part or cofins_part:
                    linhas.append(f"[PIS/COFINS] {pis_part} | {cofins_part}")

                # 5. Extração e Auditoria Oficial de Imposto Seletivo (IS)
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
                    if vBC_is_val > 0 and pIS_val > 0:
                        v_is_oficial = (vBC_is_val * (pIS_val / Decimal('100'))).quantize(PRECISAO_MOEDA, rounding=ROUND_HALF_EVEN)
                        if abs(vIS_val - v_is_oficial) <= Decimal('0.01'):
                            status_is = " [Auditoria RFB: ✔️ Conforme]"
                        else:
                            status_is = f" [Auditoria RFB: ⚠️ Divergência! XML: R$ {format_moeda_raw(vIS_val)} vs Oficial: R$ {format_moeda_raw(v_is_oficial)}]"
                    elif cst_is in ('100', '200', '400', '500', '600') and vIS_val == 0:
                        status_is = " [Auditoria RFB: ✔️ Conforme (Sem incidência/Zero)]"

                    linhas.append(f"[IMPOSTO SELETIVO] CST: {cst_is} ({cst_is_desc}) | cClassTrib: {cClassTrib_is} | BC: R$ {vBC_is} | Alíq: {pIS}% | Valor: R$ {vIS}{status_is}")

                # 6. Extração e Auditoria Oficial da Reforma Tributária (IBS e CBS - LC 214/2025)
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
                                return ""
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
                            else:
                                status = f"[Auditoria RFB: ⚠️ Divergência! XML: R$ {format_moeda_raw(v_xml)} vs Oficial: R$ {format_moeda_raw(v_oficial)}]"
                                
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
                            return f"          [{nome_tributo}] Alíq: {p_nom}%{det_str} | Valor: R$ {format_moeda_raw(v_xml)} {status}"

                        gIBSUF = gIBSCBS.find('gIBSUF')
                        if gIBSUF is not None:
                            linhas.append(auditar_tributo(gIBSUF, 'pIBSUF', 'vIBSUF', 'IBS UF'))
                            
                        gIBSMun = gIBSCBS.find('gIBSMun')
                        if gIBSMun is not None:
                            linhas.append(auditar_tributo(gIBSMun, 'pIBSMun', 'vIBSMun', 'IBS MUN'))
                            
                        gCBS = gIBSCBS.find('gCBS')
                        if gCBS is not None:
                            linhas.append(auditar_tributo(gCBS, 'pCBS', 'vCBS', 'CBS'))

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
                        
                        st_ibs = "✔️ Conforme" if abs(v_ibs_mono - v_ibs_oficial) <= Decimal('0.01') else f"⚠️ Divergência! (Oficial: R$ {format_moeda_raw(v_ibs_oficial)})"
                        st_cbs = "✔️ Conforme" if abs(v_cbs_mono - v_cbs_oficial) <= Decimal('0.01') else f"⚠️ Divergência! (Oficial: R$ {format_moeda_raw(v_cbs_oficial)})"
                        
                        linhas.append(f"          [MONOFASIA] Qtd BC: {qBCMono_str} | adRem IBS: R$ {adRemIBS_str} | vIBS: R$ {vIBSMono_str} [Auditoria RFB: {st_ibs}]")
                        linhas.append(f"          [MONOFASIA] adRem CBS: R$ {adRemCBS_str} | vCBS: R$ {vCBSMono_str} [Auditoria RFB: {st_cbs}]")
                    elif gIBSCBS is None:
                        if cst_ibscbs in ('400', '410', '550', '800', '810', '820', '830'):
                            linhas.append(f"          [Auditoria RFB: ✔️ Desonerado / Sem débito de tributo conforme CST {cst_ibscbs}]")
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

            linhas.append("\n")
        
        # --- TOTAIS GERAIS DA NOTA FISCAL (BATIMENTO E CONFERÊNCIA DATASUL) ---
        total = infNFe.find('total')
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

                linhas.append(f"VALOR DOS PRODUTOS: R$ {vProd_tot} | VALOR TOTAL DA NOTA (vNF): R$ {vNF_tot}")
                linhas.append(f"FRETE: R$ {vFrete_tot} | SEGURO: R$ {vSeg_tot} | OUTRAS: R$ {vOutro_tot} | DESCONTO: R$ {vDesc_tot}")
                linhas.append(f"ICMS NORMAL -> Base Total: R$ {vBC_tot} | Valor Total: R$ {vICMS_tot}")
                linhas.append(f"ICMS ST     -> Base Total ST: R$ {vBCST_tot} | Valor Total ST: R$ {vST_tot}")
                linhas.append(f"FCP TOTAL   -> FCP Normal: R$ {vFCP_tot} | FCP ST: R$ {vFCPST_tot}")
                linhas.append(f"IPI TOTAL   -> Valor IPI: R$ {vIPI_tot}")
                linhas.append(f"PIS/COFINS  -> Total PIS: R$ {vPIS_tot} | Total COFINS: R$ {vCOFINS_tot}")
            
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
                
                linhas.append(f"REFORMA TRIBUTÁRIA -> Base RTC: R$ {vBC_rtc} | Total CBS: R$ {vCBS_tot} | Total IBS: R$ {vIBS_tot}")
                
            isTot = total.find('ISTot')
            if isTot is not None:
                vIS_tot = isTot.find('vIS').text if isTot.find('vIS') is not None else '0.00'
                linhas.append(f"IMPOSTO SELETIVO   -> Total IS: R$ {vIS_tot}")
                
            linhas.append("="*80 + "\n")

        return "\n".join(linhas), chave_xml
    except Exception as e:
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

def selecionar_arquivo():
    global chave_xml_atual
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
        resultado_texto, chave_xml_atual = extrair_dados_xml(
            caminho,
            aliq_interna_informada,
            aliq_inter_informada,
            aliq_icms_informada,
            aliq_cbs_informada,
            aliq_ibs_informada
        )
        
        # Dispara a validação visual
        validar_chave_live()
        
        # Atualiza a área de texto
        area_texto.config(state=tk.NORMAL)
        area_texto.delete(1.0, tk.END)
        area_texto.insert(tk.END, resultado_texto)
        area_texto.config(state=tk.DISABLED)

def copiar_resultado():
    """Copia o conteúdo da área de texto para a área de transferência."""
    texto = area_texto.get(1.0, tk.END).strip()
    if texto:
        janela.clipboard_clear()
        janela.clipboard_append(texto)
        messagebox.showinfo("Copiado", "Resultado copiado para a área de transferência!")

def limpar_tela():
    """Zera todos os campos e a área de texto para uma nova leitura."""
    global chave_xml_atual
    chave_xml_atual = ""
    var_chave_portal.set("")
    lbl_resultado_chave.config(text="")
    
    area_texto.config(state=tk.NORMAL)
    area_texto.delete(1.0, tk.END)
    area_texto.config(state=tk.DISABLED)

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
janela.geometry("1000x850")
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
frame_topo.pack(pady=15, fill="x", padx=25)

lbl_titulo = ttk.Label(frame_topo, text="Extrator de Dados para Implantação Datasul & Auditoria RTC", style="Titulo.TLabel")
lbl_titulo.pack(pady=(0, 5))

lbl_instrucao = ttk.Label(frame_topo, text="Extração automatizada de Produtos, Parcelas, ICMS, IPI, PIS/COFINS, DIFAL, ST e Auditoria de IBS/CBS.")
lbl_instrucao.pack(pady=(0, 10))

# --- GRUPO DE CONFIGURAÇÕES E VALIDAÇÃO (LabelFrame) ---
frame_config = ttk.LabelFrame(frame_topo, text="Parâmetros de Cálculo & Validação", padding=(15, 10))
frame_config.pack(fill="x", pady=(0, 10))

# Configuração do grid para alinhar os elementos
frame_config.columnconfigure(1, weight=1)
frame_config.columnconfigure(3, weight=1)

# Linha 0: DIFAL
lbl_aliq_int = ttk.Label(frame_config, text="DIFAL - Alíq. Interna Padrão (%):")
lbl_aliq_int.grid(row=0, column=0, padx=(0, 5), pady=4, sticky="e")
var_aliquota_int = tk.StringVar(value="22.0")
entry_aliq_int = ttk.Entry(frame_config, textvariable=var_aliquota_int, width=8, justify="center")
entry_aliq_int.grid(row=0, column=1, padx=(0, 15), pady=4, sticky="w")

lbl_aliq_ext = ttk.Label(frame_config, text="DIFAL - Alíq. Interestadual (se faltar) (%):")
lbl_aliq_ext.grid(row=0, column=2, padx=(0, 5), pady=4, sticky="e")
var_aliquota_ext = tk.StringVar(value="12.0")
entry_aliq_ext = ttk.Entry(frame_config, textvariable=var_aliquota_ext, width=8, justify="center")
entry_aliq_ext.grid(row=0, column=3, pady=4, sticky="w")

# Linha 1: ICMS Normal e CBS de Transição
lbl_aliq_icms = ttk.Label(frame_config, text="ICMS Normal (se faltar no XML) (%):")
lbl_aliq_icms.grid(row=1, column=0, padx=(0, 5), pady=4, sticky="e")
var_aliquota_icms = tk.StringVar(value="20.0")
entry_aliq_icms = ttk.Entry(frame_config, textvariable=var_aliquota_icms, width=8, justify="center")
entry_aliq_icms.grid(row=1, column=1, padx=(0, 15), pady=4, sticky="w")

lbl_aliq_cbs = ttk.Label(frame_config, text="CBS Transição (se faltar no XML) (%):")
lbl_aliq_cbs.grid(row=1, column=2, padx=(0, 5), pady=4, sticky="e")
var_aliquota_cbs = tk.StringVar(value="0.90")
entry_aliq_cbs = ttk.Entry(frame_config, textvariable=var_aliquota_cbs, width=8, justify="center")
entry_aliq_cbs.grid(row=1, column=3, pady=4, sticky="w")

# Linha 2: IBS de Transição
lbl_aliq_ibs = ttk.Label(frame_config, text="IBS Transição (se faltar no XML) (%):")
lbl_aliq_ibs.grid(row=2, column=0, padx=(0, 5), pady=4, sticky="e")
var_aliquota_ibs = tk.StringVar(value="0.10")
entry_aliq_ibs = ttk.Entry(frame_config, textvariable=var_aliquota_ibs, width=8, justify="center")
entry_aliq_ibs.grid(row=2, column=1, padx=(0, 15), pady=4, sticky="w")

# Linha 3: Verificação de Chave de Acesso
lbl_chave = ttk.Label(frame_config, text="Chave de Acesso do Portal:")
lbl_chave.grid(row=3, column=0, padx=(0, 5), pady=(10, 4), sticky="e")
var_chave_portal = tk.StringVar(value="")
var_chave_portal.trace_add("write", validar_chave_live)

entry_chave = ttk.Entry(frame_config, textvariable=var_chave_portal, width=48, justify="center")
entry_chave.grid(row=3, column=1, columnspan=2, padx=(0, 10), pady=(10, 4), sticky="we")

lbl_resultado_chave = ttk.Label(frame_config, text="", font=("Segoe UI", 10, "bold"))
lbl_resultado_chave.grid(row=3, column=3, padx=(0, 5), pady=(10, 4), sticky="w")
# --------------------------------------------------------

# Container para os botões
frame_botoes = ttk.Frame(frame_topo)
frame_botoes.pack(pady=8)

btn_abrir = ttk.Button(frame_botoes, text="📁 Selecionar Arquivo XML", command=selecionar_arquivo, style="Principal.TButton", cursor="hand2")
btn_abrir.grid(row=0, column=0, padx=6)

btn_copiar = ttk.Button(frame_botoes, text="📋 Copiar Resultado", command=copiar_resultado, style="Acao.TButton", cursor="hand2")
btn_copiar.grid(row=0, column=1, padx=6)

btn_limpar = ttk.Button(frame_botoes, text="🗑️ Limpar Tudo", command=limpar_tela, style="Limpar.TButton", cursor="hand2")
btn_limpar.grid(row=0, column=2, padx=6)

# Container para o campo de texto
frame_texto = ttk.Frame(janela)
frame_texto.pack(expand=True, fill='both', padx=25, pady=(0, 15))

# Campo de texto (ScrolledText) configurado como bloqueado inicialmente
area_texto = scrolledtext.ScrolledText(frame_texto, wrap=tk.WORD, font=("Consolas", 10), bg="#ffffff", fg="#2d3748", relief="flat", padx=10, pady=10)
area_texto.pack(expand=True, fill='both')
area_texto.config(state=tk.DISABLED)

if __name__ == '__main__':
    janela.mainloop()
