import unittest
import xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_HALF_EVEN
import tempfile
import os
from extrator_nfe import (
    extrair_dados_xml,
    calcular_tributo_rtc_oficial,
    to_decimal,
    format_moeda_raw,
    CST_IBS_CBS_DESCRICAO,
    CST_IS_DESCRICAO
)

class TestExtratorNFe(unittest.TestCase):

    def test_01_calculo_rtc_oficial_exemplo_receita(self):
        """Testa o cálculo com o exemplo oficial do repositório da Receita Federal."""
        aliq_efet, valor = calcular_tributo_rtc_oficial(1200.00, 8.8, 60.0)
        self.assertEqual(str(aliq_efet), '3.5200')
        self.assertEqual(str(valor), '42.24')

        aliq_efet_uf, valor_uf = calcular_tributo_rtc_oficial(1200.00, 0.05, 60.0)
        self.assertEqual(str(aliq_efet_uf), '0.0200')
        self.assertEqual(str(valor_uf), '0.24')

    def test_02_arredondamento_bancario_half_even(self):
        """Verifica se o arredondamento segue HALF_EVEN (bancário) da Receita Federal."""
        val1 = Decimal('0.025').quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
        val2 = Decimal('0.035').quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
        self.assertEqual(str(val1), '0.02')
        self.assertEqual(str(val2), '0.04')

    def test_03_xml_com_ibscbs_completo(self):
        """Testa o processamento de um XML com dados da Reforma Tributária."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
            <NFe>
                <infNFe Id="NFe35261100000000000191550010000001231000001234">
                    <ide>
                        <nNF>123</nNF>
                        <serie>1</serie>
                        <dhEmi>2026-11-17T10:00:00-03:00</dhEmi>
                    </ide>
                    <emit>
                        <CNPJ>12345678000195</CNPJ>
                        <xNome>EMPRESA FORNECEDORA LTDA</xNome>
                    </emit>
                    <dest>
                        <CNPJ>98765432000188</CNPJ>
                        <xNome>MINHA EMPRESA CLIENTE</xNome>
                        <enderDest>
                            <UF>RJ</UF>
                        </enderDest>
                    </dest>
                    <cobr>
                        <fat>
                            <vLiq>1040.00</vLiq>
                        </fat>
                        <dup>
                            <nDup>001</nDup>
                            <dVenc>2026-12-17</dVenc>
                            <vDup>520.00</vDup>
                        </dup>
                        <dup>
                            <nDup>002</nDup>
                            <dVenc>2027-01-17</dVenc>
                            <vDup>520.00</vDup>
                        </dup>
                    </cobr>
                    <det nItem="1">
                        <prod>
                            <cProd>PROD001</cProd>
                            <xProd>PARAFUSO SEXTAVADO</xProd>
                            <NCM>73181500</NCM>
                            <CFOP>6102</CFOP>
                            <uCom>UN</uCom>
                            <qCom>100.0000</qCom>
                            <vUnCom>10.0000</vUnCom>
                            <vProd>1000.00</vProd>
                            <vFrete>50.00</vFrete>
                            <vDesc>10.00</vDesc>
                        </prod>
                        <imposto>
                            <ICMS>
                                <ICMS00>
                                    <orig>0</orig>
                                    <CST>00</CST>
                                    <vBC>1040.00</vBC>
                                    <pICMS>12.00</pICMS>
                                    <vICMS>124.80</vICMS>
                                </ICMS00>
                            </ICMS>
                            <IPI>
                                <cEnq>999</cEnq>
                                <IPITrib>
                                    <CST>50</CST>
                                    <vBC>1000.00</vBC>
                                    <pIPI>5.00</pIPI>
                                    <vIPI>50.00</vIPI>
                                </IPITrib>
                            </IPI>
                            <PIS>
                                <PISAliq>
                                    <CST>01</CST>
                                    <vBC>1040.00</vBC>
                                    <pPIS>1.65</pPIS>
                                    <vPIS>17.16</vPIS>
                                </PISAliq>
                            </PIS>
                            <COFINS>
                                <COFINSAliq>
                                    <CST>01</CST>
                                    <vBC>1040.00</vBC>
                                    <pCOFINS>7.60</pCOFINS>
                                    <vCOFINS>79.04</vCOFINS>
                                </COFINSAliq>
                            </COFINS>
                            <IBSCBS>
                                <CST>200</CST>
                                <cClassTrib>200028</cClassTrib>
                                <gIBSCBS>
                                    <vBC>1040.00</vBC>
                                    <gIBSUF>
                                        <pIBSUF>0.05</pIBSUF>
                                        <gRed>
                                            <pRedAliq>60.00</pRedAliq>
                                            <pAliqEfet>0.02</pAliqEfet>
                                        </gRed>
                                        <vIBSUF>0.21</vIBSUF>
                                    </gIBSUF>
                                    <gIBSMun>
                                        <pIBSMun>0.05</pIBSMun>
                                        <gRed>
                                            <pRedAliq>60.00</pRedAliq>
                                            <pAliqEfet>0.02</pAliqEfet>
                                        </gRed>
                                        <vIBSMun>0.21</vIBSMun>
                                    </gIBSMun>
                                    <gCBS>
                                        <pCBS>8.80</pCBS>
                                        <gRed>
                                            <pRedAliq>60.00</pRedAliq>
                                            <pAliqEfet>3.52</pAliqEfet>
                                        </gRed>
                                        <vCBS>36.61</vCBS>
                                    </gCBS>
                                </gIBSCBS>
                            </IBSCBS>
                        </imposto>
                    </det>
                    <total>
                        <ICMSTot>
                            <vProd>1000.00</vProd>
                            <vFrete>50.00</vFrete>
                            <vSeg>0.00</vSeg>
                            <vDesc>10.00</vDesc>
                            <vOutro>0.00</vOutro>
                            <vBC>1040.00</vBC>
                            <vICMS>124.80</vICMS>
                            <vBCST>0.00</vBCST>
                            <vST>0.00</vST>
                            <vFCP>0.00</vFCP>
                            <vFCPST>0.00</vFCPST>
                            <vIPI>50.00</vIPI>
                            <vPIS>17.16</vPIS>
                            <vCOFINS>79.04</vCOFINS>
                            <vNF>1090.00</vNF>
                        </ICMSTot>
                    </total>
                </infNFe>
            </NFe>
        </nfeProc>
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write(xml_content)
            temp_path = f.name
        
        try:
            texto, chave = extrair_dados_xml(temp_path, 22.0, 12.0, 20.0, 0.90, 0.10)
            self.assertEqual(chave, "35261100000000000191550010000001231000001234")
            self.assertIn("DADOS GERAIS DA NOTA FISCAL: 123 | SÉRIE: 001", texto)
            self.assertIn("EMITENTE: EMPRESA FORNECEDORA LTDA", texto)
            
            # Verificação de Cobrança / Parcelas
            self.assertIn("COBRANÇA / PARCELAS -> TOTAL DE PARCELAS: 2", texto)
            self.assertIn("Parc. 001: R$ 520.00 | Parc. 002: R$ 520.00", texto)
            
            # Verificação de IPI e PIS/COFINS nos itens
            self.assertIn("[IPI] CST: 50 | cEnq: 999 | BC: R$ 1000.00 | Alíq: 5.00% | Valor: R$ 50.00", texto)
            self.assertIn("[PIS/COFINS] PIS (CST 01) -> BC: R$ 1040.00 | Alíq: 1.65% | Valor: R$ 17.16 | COFINS (CST 01) -> BC: R$ 1040.00 | Alíq: 7.60% | Valor: R$ 79.04", texto)
            
            # Verificação de Totais
            self.assertIn("IPI TOTAL   -> Valor IPI: R$ 50.00", texto)
            self.assertIn("PIS/COFINS  -> Total PIS: R$ 17.16 | Total COFINS: R$ 79.04", texto)
            
            # Verificação de Reforma Tributária
            self.assertIn("[IBS/CBS - REFORMA TRIBUTÁRIA] CST: 200", texto)
            self.assertIn("[Auditoria RFB: ✔️ Conforme]", texto)
        finally:
            os.remove(temp_path)

    def test_04_xml_sem_ibscbs_simulacao_automatica(self):
        """Testa o comportamento com um XML tradicional de NF-e antiga (sem IBSCBS)."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <NFe xmlns="http://www.portalfiscal.inf.br/nfe">
            <infNFe Id="NFe33261100000000000191550010000009991000009999">
                <ide>
                    <nNF>999</nNF>
                    <serie>2</serie>
                    <dhEmi>2026-10-01T08:00:00-03:00</dhEmi>
                </ide>
                <emit>
                    <CNPJ>99999999000199</CNPJ>
                    <xNome>DISTRIBUIDORA TRADICIONAL</xNome>
                </emit>
                <det nItem="1">
                    <prod>
                        <cProd>ITEM10</cProd>
                        <xProd>CABO DE COBRE</xProd>
                        <NCM>85444900</NCM>
                        <CFOP>5102</CFOP>
                        <uCom>MT</uCom>
                        <qCom>50.0000</qCom>
                        <vUnCom>10.0000</vUnCom>
                        <vProd>500.00</vProd>
                    </prod>
                    <imposto>
                        <ICMS>
                            <ICMS00>
                                <orig>0</orig>
                                <CST>00</CST>
                                <vBC>500.00</vBC>
                                <pICMS>20.00</pICMS>
                                <vICMS>100.00</vICMS>
                            </ICMS00>
                        </ICMS>
                    </imposto>
                </det>
            </infNFe>
        </NFe>
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write(xml_content)
            temp_path = f.name
        
        try:
            texto, chave = extrair_dados_xml(temp_path, 22.0, 12.0, 20.0, 0.90, 0.10)
            self.assertEqual(chave, "33261100000000000191550010000009991000009999")
            self.assertIn("DADOS GERAIS DA NOTA FISCAL: 999 | SÉRIE: 002", texto)
            self.assertIn("DISTRIBUIDORA TRADICIONAL", texto)
            self.assertIn("[SIMULAÇÃO RTC TRANSIÇÃO OFICIAL]", texto)
            self.assertIn("Base Unificada: R$ 400.00 | CBS (0.90%): R$ 3.60", texto)
            self.assertIn("IBS (0.10%): R$ 0.40 (UF: R$ 0.20 | Mun: R$ 0.20)", texto)
        finally:
            os.remove(temp_path)

    def test_05_auditoria_detecta_divergencia_calculo(self):
        """Testa se o auditor detecta quando o fornecedor errou o cálculo de CBS no XML."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <NFe xmlns="http://www.portalfiscal.inf.br/nfe">
            <infNFe Id="NFe35261100000000000191550010000001231000001234">
                <ide><nNF>1</nNF><serie>1</serie></ide>
                <emit><xNome>TESTE</xNome></emit>
                <det nItem="1">
                    <prod><vProd>1000.00</vProd></prod>
                    <imposto>
                        <IBSCBS>
                            <CST>000</CST>
                            <cClassTrib>000001</cClassTrib>
                            <gIBSCBS>
                                <vBC>1000.00</vBC>
                                <gCBS>
                                    <pCBS>10.00</pCBS>
                                    <vCBS>50.00</vCBS>
                                </gCBS>
                            </gIBSCBS>
                        </IBSCBS>
                    </imposto>
                </det>
            </infNFe>
        </NFe>
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write(xml_content)
            temp_path = f.name
        
        try:
            texto, _ = extrair_dados_xml(temp_path, 22.0, 12.0, 20.0, 0.90, 0.10)
            self.assertIn("Divergência! XML: R$ 50.00 vs Oficial: R$ 100.00", texto)
        finally:
            os.remove(temp_path)

    def test_06_imposto_seletivo(self):
        """Testa extração e auditoria de Imposto Seletivo."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <NFe xmlns="http://www.portalfiscal.inf.br/nfe">
            <infNFe Id="NFe35261100000000000191550010000001231000001234">
                <ide><nNF>1</nNF><serie>1</serie></ide>
                <emit><xNome>TESTE BEBIDAS</xNome></emit>
                <det nItem="1">
                    <prod><vProd>150.00</vProd></prod>
                    <imposto>
                        <IS>
                            <CST>000</CST>
                            <cClassTrib>000001</cClassTrib>
                            <vBC>150.00</vBC>
                            <pIS>10.00</pIS>
                            <vIS>15.00</vIS>
                        </IS>
                    </imposto>
                </det>
            </infNFe>
        </NFe>
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write(xml_content)
            temp_path = f.name
        
        try:
            texto, _ = extrair_dados_xml(temp_path, 22.0, 12.0, 20.0, 0.90, 0.10)
            self.assertIn("[IMPOSTO SELETIVO] CST: 000 (Tributado com Imposto Seletivo)", texto)
            self.assertIn("BC: R$ 150.00 | Alíq: 10.00% | Valor: R$ 15.00 [Auditoria RFB: ✔️ Conforme]", texto)
        finally:
            os.remove(temp_path)

    def test_07_arquivo_invalido(self):
        """Testa comportamento com arquivo não XML ou XML inválido."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write("<nao_e_nfe></nao_e_nfe>")
            temp_path = f.name
        
        try:
            texto, chave = extrair_dados_xml(temp_path, 22.0, 12.0, 20.0, 0.90, 0.10)
            self.assertIn("não parece ser um XML de NF-e válido", texto)
            self.assertEqual(chave, "")
        finally:
            os.remove(temp_path)

    def test_08_tabelas_cst_oficiais(self):
        """Testa se todas as 16 tabelas CST de IBS/CBS e 7 de IS da RFB estão presentes."""
        csts_ibscbs_esperadas = ["000", "010", "011", "200", "220", "221", "222", "400", "410", "510", "550", "620", "800", "810", "820", "830"]
        for cst in csts_ibscbs_esperadas:
            self.assertIn(cst, CST_IBS_CBS_DESCRICAO)

        csts_is_esperadas = ["000", "100", "200", "300", "400", "500", "600"]
        for cst in csts_is_esperadas:
            self.assertIn(cst, CST_IS_DESCRICAO)

    def test_09_arquivos_oficiais_receita_federal(self):
        """Valida que os XMLs de homologação oficial da RFB auditem perfeitamente."""
        if os.path.exists("exemplos_xml/nfe_oficial_receita_federal.xml"):
            res, chave = extrair_dados_xml("exemplos_xml/nfe_oficial_receita_federal.xml")
            self.assertIn("[Auditoria RFB: ✔️ Conforme]", res)
            self.assertNotIn("Divergência!", res)
            
        if os.path.exists("exemplos_xml/nfe_valido_receita_federal.xml"):
            res2, chave2 = extrair_dados_xml("exemplos_xml/nfe_valido_receita_federal.xml")
            self.assertIn("[Auditoria RFB: ✔️ Conforme]", res2)
            self.assertNotIn("Divergência!", res2)

    def test_10_monofasia_ibs_cbs(self):
        """Testa tributação monofásica (CST 620) com adRem."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <NFe xmlns="http://www.portalfiscal.inf.br/nfe">
            <infNFe Id="NFe35261100000000000191550010000001231000001234">
                <ide><nNF>1</nNF><serie>1</serie></ide>
                <emit><xNome>TESTE COMBUSTIVEL</xNome></emit>
                <det nItem="1">
                    <prod><vProd>5000.00</vProd></prod>
                    <imposto>
                        <IBSCBS>
                            <CST>620</CST>
                            <cClassTrib>620001</cClassTrib>
                            <gIBSCBSMono>
                                <qBCMono>1000.00</qBCMono>
                                <adRemIBS>0.50</adRemIBS>
                                <adRemCBS>0.25</adRemCBS>
                                <vIBSMono>500.00</vIBSMono>
                                <vCBSMono>250.00</vCBSMono>
                            </gIBSCBSMono>
                        </IBSCBS>
                    </imposto>
                </det>
            </infNFe>
        </NFe>
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write(xml_content)
            temp_path = f.name
        
        try:
            texto, _ = extrair_dados_xml(temp_path)
            self.assertIn("[MONOFASIA] Qtd BC: 1000.00 | adRem IBS: R$ 0.50 | vIBS: R$ 500.00 [Auditoria RFB: ✔️ Conforme]", texto)
            self.assertIn("[MONOFASIA] adRem CBS: R$ 0.25 | vCBS: R$ 250.00 [Auditoria RFB: ✔️ Conforme]", texto)
        finally:
            os.remove(temp_path)

    def test_11_ordem_exibicao_impostos(self):
        """Valida que a ordem de exibição seja estritamente: ICMS > CBS > IBS UF > IBS MUN > IS > IPI > PIS/COFINS."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <NFe xmlns="http://www.portalfiscal.inf.br/nfe">
            <infNFe Id="NFe35261100000000000191550010000001231000001234">
                <ide><nNF>1</nNF><serie>1</serie></ide>
                <emit><xNome>TESTE ORDEM</xNome></emit>
                <det nItem="1">
                    <prod><vProd>1000.00</vProd></prod>
                    <imposto>
                        <ICMS>
                            <ICMS00>
                                <orig>0</orig>
                                <CST>00</CST>
                                <vBC>1000.00</vBC>
                                <pICMS>18.00</pICMS>
                                <vICMS>180.00</vICMS>
                            </ICMS00>
                        </ICMS>
                        <IPI>
                            <cEnq>999</cEnq>
                            <IPITrib><CST>50</CST><vBC>1000.00</vBC><pIPI>5.00</pIPI><vIPI>50.00</vIPI></IPITrib>
                        </IPI>
                        <PIS>
                            <PISAliq><CST>01</CST><vBC>1000.00</vBC><pPIS>1.65</pPIS><vPIS>16.50</vPIS></PISAliq>
                        </PIS>
                        <COFINS>
                            <COFINSAliq><CST>01</CST><vBC>1000.00</vBC><pCOFINS>7.60</pCOFINS><vCOFINS>76.00</vCOFINS></COFINSAliq>
                        </COFINS>
                        <IS>
                            <CST>000</CST><cClassTrib>000001</cClassTrib><vBC>1000.00</vBC><pIS>2.00</pIS><vIS>20.00</vIS>
                        </IS>
                        <IBSCBS>
                            <CST>000</CST><cClassTrib>000001</cClassTrib>
                            <gIBSCBS>
                                <vBC>1000.00</vBC>
                                <gIBSUF><pIBSUF>0.05</pIBSUF><vIBSUF>0.50</vIBSUF></gIBSUF>
                                <gIBSMun><pIBSMun>0.05</pIBSMun><vIBSMun>0.50</vIBSMun></gIBSMun>
                                <gCBS><pCBS>0.90</pCBS><vCBS>9.00</vCBS></gCBS>
                            </gIBSCBS>
                        </IBSCBS>
                    </imposto>
                </det>
            </infNFe>
        </NFe>
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write(xml_content)
            temp_path = f.name
        
        try:
            texto, _ = extrair_dados_xml(temp_path)
            pos_icms = texto.find("[ICMS]")
            pos_cbs = texto.find("[CBS]")
            pos_ibs_uf = texto.find("[IBS UF]")
            pos_ibs_mun = texto.find("[IBS MUN]")
            pos_is = texto.find("[IMPOSTO SELETIVO]")
            pos_ipi = texto.find("[IPI]")
            pos_pis_cofins = texto.find("[PIS/COFINS]")
            
            # Todos os blocos devem existir
            self.assertTrue(all(p > -1 for p in [pos_icms, pos_cbs, pos_ibs_uf, pos_ibs_mun, pos_is, pos_ipi, pos_pis_cofins]))
            
            # Ordem solicitada: ICMS > CBS > IBS UF > IBS MUN > IS > IPI > PIS/COFINS
            self.assertTrue(pos_icms < pos_cbs, f"ICMS ({pos_icms}) deve vir antes de CBS ({pos_cbs})")
            self.assertTrue(pos_cbs < pos_ibs_uf, f"CBS ({pos_cbs}) deve vir antes de IBS UF ({pos_ibs_uf})")
            self.assertTrue(pos_ibs_uf < pos_ibs_mun, f"IBS UF ({pos_ibs_uf}) deve vir antes de IBS MUN ({pos_ibs_mun})")
            self.assertTrue(pos_ibs_mun < pos_is, f"IBS MUN ({pos_ibs_mun}) deve vir antes de IS ({pos_is})")
            self.assertTrue(pos_is < pos_ipi, f"IS ({pos_is}) deve vir antes de IPI ({pos_ipi})")
            self.assertTrue(pos_ipi < pos_pis_cofins, f"IPI ({pos_ipi}) deve vir antes de PIS/COFINS ({pos_pis_cofins})")
        finally:
            os.remove(temp_path)

if __name__ == '__main__':
    unittest.main()
