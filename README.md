# Extrator de XML NF-e & Auditor Oficial RTC (Reforma Tributária)

[![Python Version](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/GUI-Tkinter%20%2F%20TTK-brightgreen.svg)]()
[![Compliance](https://img.shields.io/badge/Compliance-LC%20214%2F2025%20(RTC)-orange.svg)]()
[![Engine](https://img.shields.io/badge/Engine-Receita%20Federal%20%2F%20SERPRO-darkblue.svg)]()
[![Signed](https://img.shields.io/badge/Authenticode-Balthazar%20IA-purple.svg)]()

> Solução desktop autônoma desenvolvida por **Balthazar IA** para automação fiscal, agilização do processo de implantação e conferência de notas fiscais no ERP **TOTVS Datasul**, e auditoria em tempo real da **Reforma Tributária do Consumo (IBS, CBS e Imposto Seletivo)** segundo os motores de cálculo da Receita Federal e a Lei Complementar nº 214/2025.

---

## 🎯 Objetivo e Visão Geral

Na rotina fiscal e de suprimentos de empresas que utilizam o **TOTVS Datasul**, a conferência manual de arquivos XML de NF-e (modelo 55) é um processo moroso e suscetível a erros de digitação de alíquotas, bases de cálculo e vencimentos de duplicatas.

Este aplicativo resolve esse gargalo através de:
1. **Extração Estruturada:** Leitura instantânea e organizada dos blocos essenciais da NF-e no padrão mental e operacional dos analistas fiscais do Datasul.
2. **Conferência em Tempo Real:** Validação dinâmica de chaves de acesso (para bipagem de código de barras ou cópia do portal da SEFAZ).
3. **Auditoria da Reforma Tributária (RTC):** Validação matemática profunda de IBS, CBS e Imposto Seletivo (IS), comparando os valores declarados no XML contra as regras oficiais do motor do SERPRO/Receita Federal.

---

## ✨ Principais Funcionalidades

### 1. Visão Datasul Otimizada (Clique para Copiar com Vírgula)
* **Padrão Visual do ERP:** Interface desenhada no modelo operacional do TOTVS Datasul, com títulos de tributos estáticos ("escritos chapados") e valores em **negrito**.
* **1 Clique para Copiar:** Dê 1 clique sobre qualquer número (Base de Cálculo, Alíquota, Valor, NCM, CFOP ou Totais) para copiá-lo instantaneamente para a área de transferência.
* **Formatação Compatível com Datasul:** Todos os números são copiados **com vírgula** decimal e **sem ponto de milhar** (ex: `1250,50` e `180,00`), evitando conflitos com as máscaras nativas de campos numéricos do Progress 4GL.
* **Feedback Visual Instantâneo:** Ao clicar em um valor, o campo pisca em verde suave (`#bbf7d0`) e a barra de status inferior confirma o dado copiado.
* **Cards Destacados por Item:** Divisão clara entre itens com barra de identificação azul, linha de dados cadastrais (Cód, NCM, CFOP, Qtd, Vl Unit, Total) e grade de tributos.
* **Totais da Nota em Destaque:** Painel superior com conciliação imediata de valores comerciais e fiscais antes de auditar os itens.
* **Espelho em Texto (Aba 2):** Aba dedicada que preserva o relatório textual corrido completo com o botão **📋 Copiar Espelho Completo (Texto)**.
* **Ordem Padronizada dos Tributos:** `ICMS` (com DIFAL/ST/FCP) $\rightarrow$ `CBS` $\rightarrow$ `IBS UF` $\rightarrow$ `IBS MUN` $\rightarrow$ `IS (Imposto Seletivo)` $\rightarrow$ `IPI` $\rightarrow$ `PIS / COFINS`.

### 2. Motor Oficial de Auditoria RTC (Reforma Tributária)
* **Base de Cálculo Unificada (Art. 349 da LC 214/2025):**
  - **Integram (+):** `vProd` + `vFrete` + `vSeg` + `vOutro` + `vII` + (`vIS` a partir de 2027 ou se destacado).
  - **Deduções do Período de Transição (-):** `vDesc` + (`vPIS` e `vCOFINS` em 2026) + (`vICMS`, `vFCP` e `vISS` de 2026 a 2032).
  - **Progressão Temporal Automática:** O motor identifica o ano de emissão (`dhEmi`) e adapta a fórmula da base de cálculo conforme a etapa constitucional vigente (2026, 2027–2032 ou 2033+).
* **Tabelas Completas de CST Oficiais da Receita Federal:**
  - **16 CSTs de IBS e CBS:** `000`, `010`, `011`, `200`, `220`, `221`, `222`, `400`, `410`, `510`, `550`, `620`, `800`, `810`, `820` e `830`.
  - **7 CSTs de Imposto Seletivo (IS):** `000`, `100`, `200`, `300`, `400`, `500` e `600`.
* **Alíquota Efetiva e Redução (`gRed`):**
  - Cálculo oficial: $\text{Alíq. Efetiva} = \text{Alíq. Nominal} \times (1 - \text{pRedAliq} / 100)$, mantendo 8 casas decimais intermediárias e arredondamento `ROUND_HALF_EVEN`.
* **Diferimento (`gDif`):**
  - Subtração do valor diferido (`vDif`) ou dedução por percentual (`pDif`) para apuração do tributo efetivamente devido.
* **Devolução de Tributos (`gDevTrib`):**
  - Extração do montante de `vDevTrib` em fornecimento de utilidades públicas (energia, água, saneamento, gás).
* **Tributação Monofásica (`gIBSCBSMono`):**
  - Conferência de alíquotas *ad rem* e quantidade base (`qBCMono`) para produtos do regime monofásico (CST 620).
* **Imposto Seletivo (`IS`):**
  - Auditoria matemática de incidência do imposto sobre bens e serviços específicos.

### 3. Validador Live de Chave de Acesso
* Campo interativo que analisa a digitação ou bipagem em tempo real, indicando visualmente:
  - `✔️ CERTO (Chaves iguais)`
  - `❌ ERRADO (Chaves diferentes)`
  - `⚠️ Aguardando chave...`

---

## 🛠️ Tecnologias Utilizadas

* **Linguagem:** Python 3.12+
* **Interface Gráfica:** `tkinter` e `ttk` com tema customizado e paleta corporativa.
* **Motor Numérico:** Módulo nativo `decimal` com constantes de alta precisão (`ROUND_HALF_EVEN` - padrão bancário/fiscal).
* **Processamento de XML:** `xml.etree.ElementTree` com rotina inteligente de expurgo de namespaces.
* **Empacotamento Standalone:** PyInstaller 6.x (arquivo único `.exe`, sem dependência de terminal ou runtime Python pré-instalado).
* **Assinatura Digital:** Microsoft Authenticode SHA-256 (`CN=Balthazar IA`).

---

## 📁 Estrutura do Repositório

```text
├── extrator_nfe.py           # Código-fonte principal com GUI e motor fiscal RTC
├── test_extrator.py          # Bateria completa de 12 testes unitários automatizados
├── Extrator_NFe_Datasul.spec # Especificação técnica do PyInstaller para build
├── file_version_info.txt     # Metadados de versão do Windows PE (Balthazar IA v1.2)
├── app_icon.ico              # Ícone desktop em alta resolução (.ico com múltiplos canais)
├── app_icon.png              # Asset gráfico do ícone da aplicação
├── header_icon.png           # Asset gráfico do cabeçalho
├── logo_original.png         # Logotipo original da solução
├── .gitignore                # Regras de exclusão de temporários e builds locais
└── README.md                 # Documentação completa do projeto
```

---

## 🚀 Como Utilizar

### Opção 1: Executável Pré-Compilado (Sem Instalar Nada)
1. Baixe o executável `Extrator NFe.exe` disponível na raiz do repositório ou na aba de Releases.
2. Dê dois cliques para abrir diretamente no Windows 10 ou Windows 11.
3. Clique em **📁 Selecionar Arquivo XML**, escolha a NF-e desejada e visualize todos os dados extraídos.
4. Para copiar o relatório formatado, clique em **📋 Copiar Resultado**.

### Opção 2: Executando a Partir do Código-Fonte Python
1. Clone o repositório:
   ```bash
   git clone https://github.com/lbalthazart/Extrator-XML.git
   cd Extrator-XML
   ```
2. Certifique-se de possuir o **Python 3.10+** instalado (o projeto utiliza bibliotecas padrão da linguagem, dispensando `pip install` para execução básica).
3. Execute o programa:
   ```bash
   python extrator_nfe.py
   ```

---

## 🧪 Testes Automatizados

O repositório inclui uma suíte completa de testes unitários que valida desde o motor de arredondamento bancário até notas fiscais complexas da Reforma Tributária:

Para executar os testes:
```bash
python -m unittest test_extrator.py -v
```

Cobertura dos testes:
* `test_01`: Validação com cálculo oficial da Receita Federal / SERPRO.
* `test_02`: Verificação do arredondamento bancário `ROUND_HALF_EVEN`.
* `test_03`: Processamento de XML com todos os grupos da Reforma Tributária (`gIBSUF`, `gIBSMun`, `gCBS`).
* `test_04`: Simulação automática para notas tradicionais sem destaque de IBS/CBS.
* `test_05`: Detecção e alerta de divergências em cálculos incorretos de fornecedores.
* `test_06`: Extração e auditoria matemática de Imposto Seletivo (`IS`).
* `test_07`: Resiliência contra arquivos inválidos ou corrompidos.
* `test_08`: Integridade de todas as tabelas de CST (16 de IBS/CBS e 7 de IS).
* `test_09`: Conformidade com arquivos de homologação oficial da Receita Federal.
* `test_10`: Tributação monofásica com alíquotas *ad rem* e base quantitativa.
* `test_11`: Validação rigorosa da ordem sequencial dos tributos (ICMS > CBS > IBS UF > IBS MUN > IS > IPI > PIS/COFINS).
* `test_12`: Validação da formatação padrão Datasul (vírgula decimal sem ponto de milhar) e estrutura de dados da Visão Datasul.

---

## 🔨 Como Compilar o Executável

Caso deseje recompilar o `.exe` a partir do código-fonte:

1. Instale o PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. Execute o build utilizando o arquivo de especificação já configurado:
   ```bash
   pyinstaller Extrator_NFe_Datasul.spec
   ```
3. O executável standalone será gerado na pasta `dist/`.

---

## 🔒 Segurança e Privacidade

* **Processamento 100% Local:** O processamento do XML ocorre exclusivamente na memória do computador do usuário (ambiente *air-gapped*).
* **Sem Telemetria ou Envio de Dados:** Nenhuma informação fiscal, cadastral ou financeira é enviada para servidores externos ou serviços de terceiros.
* **Sem Informações Sensíveis:** O código e os testes utilizam apenas dados hipotéticos ou de domínio público fornecidos em ambientes de homologação da Receita Federal.

---

## 📜 Licença e Direitos

Copyright © 2026 **Balthazar IA**. Todos os direitos reservados.
Projeto distribuído para uso corporativo interno e automação fiscal.
