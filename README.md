# 💉 IMMUNE - Sistema de Análise de Prontuários Médicos

<div align="center">

![IMMUNE Logo](LOGO.jpeg)

**Promovendo a saúde com tratamentos inteligentes**

*Tecnologia em saúde combinando cada paciente com a terapia mais eficaz*

*Precisão em doenças complexas*

---

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-Proprietário-green.svg)]()

</div>

---

## 🌟 Sobre a IMMUNE

A **IMMUNE** é uma empresa de tecnologia em saúde focada em:

- 🎯 **Precisão Terapêutica**: Combinamos cada paciente com a terapia mais eficaz
- 🔬 **Análise Avançada**: Processamento inteligente de dados clínicos complexos
- 💡 **Tratamentos Inteligentes**: Decisões baseadas em evidências e dados reais
- 🏥 **Doenças Complexas**: Especialização em condições que requerem análise detalhada

## 📊 Sobre o Sistema

Esta aplicação é um **Pipeline ETL (Extract, Transform, Load)** especializado para análise de prontuários médicos, permitindo:

### ✨ Funcionalidades Principais

1. **Extração Inteligente de Dados**
   - Marcadores clínicos (VHS, PCR, DAS28, HAQ, CDAI, BASDAI, ASDAS)
   - Comorbidades (HAS, DM, DLP, FM, OP e personalizadas)
   - Medicamentos (JAK inibidores, Anti-TNF, Biológicos, DMARDs)

2. **Análise Longitudinal**
   - Comparação baseline vs follow-up
   - Evolução individual de marcadores
   - Cálculo automático de tempo de tratamento

3. **Avaliação de Eficácia**
   - Critérios personalizáveis de melhora
   - Taxa de resposta global e estratificada
   - Análise por subgrupos (idade, sexo, comorbidades, medicamentos)

4. **Visualizações Interativas**
   - 15+ tipos de gráficos com Plotly
   - Dashboards interativos
   - Análise exploratória completa

5. **Exportação de Dados**
   - Excel e CSV
   - Dados processados e longitudinais
   - Preservação de configurações

## 🚀 Instalação Rápida

### Pré-requisitos
- Python 3.8 ou superior
- pip (gerenciador de pacotes Python)

### Instalação

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Garantir que LOGO.jpeg está no mesmo diretório

# 3. Executar aplicação
streamlit run app_prontuarios_IMMUNE.py
```

### Estrutura de Arquivos

```
📁 seu_projeto/
├── 📄 app_prontuarios_IMMUNE.py    # Aplicação principal
├── 📄 requirements.txt              # Dependências
├── 🖼️ LOGO.jpeg                    # Logo da IMMUNE
└── 📄 README_IMMUNE.md             # Este arquivo
```

## 📋 Estrutura de Dados Esperada

O sistema aceita arquivos Excel (.xlsx) ou CSV com as seguintes colunas:

### Colunas Obrigatórias

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `paciente` | int | ID único do paciente |
| `tipo` | string | Tipo de registro (ANAMNESE, EVOLUCAO) |
| `data_hora` | datetime | Data e hora da consulta |
| `descricao` | string | Texto do prontuário médico |

### Colunas Opcionais (Recomendadas)

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `idade` | int | Idade do paciente |
| `sexo` | string | Sexo (M/F) |
| `especialidade` | string | Especialidade médica |

## 🎯 Casos de Uso

### 1. Artrite Reumatoide (AR)

**Configuração Típica:**
- **Marcadores**: VHS, PCR, DAS28, HAQ, CDAI
- **Comorbidades**: HAS, DLP, FM, OP
- **Medicamentos**: JAK inibidores, Anti-TNF
- **Critério de Melhora**: DAS28 < 50% ou HAQ redução > 0.35

**Análise Disponível:**
- Taxa de resposta por medicamento
- Impacto de comorbidades na eficácia
- Evolução de marcadores inflamatórios
- Tempo médio para resposta

### 2. Espondilite Anquilosante (EA)

**Configuração Típica:**
- **Marcadores**: BASDAI, ASDAS, PCR, VHS
- **Medicamentos**: Anti-TNF, Anti-IL17
- **Critério de Melhora**: BASDAI redução > 50%

### 3. Outras Doenças Reumatológicas

O sistema é totalmente configurável para:
- Lúpus Eritematoso Sistêmico (LES)
- Psoríase / Artrite Psoriásica
- Doença Inflamatória Intestinal (DII)
- E qualquer condição com dados longitudinais

## 🔬 Metodologia

### Pipeline ETL

```
┌─────────────────────────────────────────────────────────────┐
│  1. EXTRACT (Extração)                                      │
│     • Carregamento de dados                                 │
│     • Identificação de padrões em texto livre              │
│     • Extração de valores numéricos e flags                │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  2. TRANSFORM (Transformação)                               │
│     • Limpeza de dados numéricos                           │
│     • Agrupamento por paciente (evita duplicatas)          │
│     • Criação de base longitudinal (t0 → t1)               │
│     • Cálculo de tempo de tratamento                       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  3. LOAD (Análise)                                          │
│     • Cálculo de eficácia (critérios clínicos)            │
│     • Análise estatística descritiva                       │
│     • Estratificação por subgrupos                         │
│     • Geração de visualizações                             │
└─────────────────────────────────────────────────────────────┘
```

### Análise de Eficácia

**Critérios Baseados em Literatura:**

| Marcador | Critério de Melhora | Referência |
|----------|---------------------|------------|
| HAQ | Redução ≥ 0.35 | Clinicamente significativa |
| DAS28 | Redução ≥ 50% | Boa resposta EULAR |
| CDAI | Redução ≥ 10 | Melhora moderada |
| BASDAI | Redução ≥ 50% | Resposta ASAS |

## 📊 Visualizações Disponíveis

### Demografia
- ✅ Distribuição de idades (histograma)
- ✅ Proporção por sexo (gráfico pizza)
- ✅ Idade estratificada por sexo

### Marcadores Clínicos
- ✅ Distribuição de valores (histogramas)
- ✅ Box plots comparativos
- ✅ Matriz de correlação
- ✅ Estatísticas descritivas

### Comorbidades
- ✅ Frequência absoluta e relativa
- ✅ Análise de comorbidades múltiplas
- ✅ Distribuição de número de comorbidades

### Medicamentos
- ✅ Frequência de uso
- ✅ Análise de politerapia
- ✅ Taxa de resposta por medicamento

### Eficácia Terapêutica
- ✅ Taxa de resposta global
- ✅ Evolução t0 → t1 (box plots)
- ✅ Mudança individual (scatter plots)
- ✅ Análise estratificada (sexo, idade, comorbidades)

## 🎨 Interface do Usuário

### Design IMMUNE

A interface utiliza as cores da marca IMMUNE:
- **Gradiente principal**: Azul (#667eea) → Roxo (#764ba2)
- **Tema limpo e profissional**
- **Navegação intuitiva por tabs**
- **Feedback visual em tempo real**

### Tabs do Sistema

1. **📊 Visão Geral**: Estatísticas gerais e preview dos dados
2. **🔧 Configurar ETL**: Interface para configuração do pipeline
3. **📈 Análise Exploratória**: Visualizações e estatísticas descritivas
4. **🎯 Análise de Eficácia**: Avaliação de resposta terapêutica
5. **💾 Exportar Dados**: Download de resultados processados

## ⚙️ Configuração Avançada

### Marcadores Personalizados

```python
# Adicione na interface ou diretamente no código:
custom_markers = {
    'glicose': [],
    'hba1c': [],
    'colesterol': []
}
```

### Critérios Customizados

```python
# Defina sua própria lógica de melhora:
improvement_criteria = {
    'hba1c': lambda v0, v1: v1 < 7.0,  # Alvo terapêutico
    'glicose': lambda v0, v1: v1 <= v0 * 0.8  # Redução de 20%
}
```

## 🔒 Segurança e Privacidade

### Boas Práticas Implementadas

- ✅ Dados processados localmente (não enviados para nuvem)
- ✅ IDs anônimos (apenas números de paciente)
- ✅ Sem armazenamento permanente de dados sensíveis
- ✅ Exportação controlada pelo usuário

### Recomendações

- 🔐 Use IDs pseudonimizados nos dados de entrada
- 🔐 Mantenha exports em local seguro
- 🔐 Siga regulamentações locais (LGPD, HIPAA, etc)

## 📈 Performance

### Capacidade

- ✅ Até 100.000 registros: Performance excelente
- ⚠️ 100k - 500k registros: Considere filtros por período
- 🔄 Acima de 500k: Recomenda-se processamento em lote

### Otimizações

- Uso de `.groupby()` para agregações eficientes
- Cálculos vetorizados com pandas
- Gráficos renderizados sob demanda

## 🤝 Suporte

### Para Problemas Técnicos

1. Verifique se todas as dependências estão instaladas
2. Confirme que `LOGO.jpeg` está no diretório correto
3. Valide a estrutura do arquivo de entrada
4. Consulte os arquivos de documentação

### Contato IMMUNE

Para questões sobre a plataforma IMMUNE ou parcerias:

- 🌐 Website: [https://www.linkedin.com/company/immuned/]
- 📧 Email: [[Contato comercial]("heloisaleao1183@gmail.com" <heloisaleao1183@gmail.com>)]
- 💼 LinkedIn: [[Perfil IMMUNE](https://www.linkedin.com/company/immuned/)]

## 🔄 Atualizações

### Versão 2.0 - Atual

- ✅ Interface IMMUNE com identidade visual
- ✅ Correção de bug de percentuais
- ✅ Análise expandida com 15+ visualizações
- ✅ Configuração 100% personalizável
- ✅ Exportação multi-formato

### Roadmap Futuro

- 🔮 Machine Learning para predição de resposta
- 🔮 API REST para integração com sistemas hospitalares
- 🔮 Relatórios automatizados em PDF
- 🔮 Dashboard em tempo real
- 🔮 Análise de custo-efetividade

## 📄 Licença

© 2025 IMMUNE. Todos os direitos reservados.

Este software é proprietário e de uso restrito. Entre em contato com IMMUNE para informações sobre licenciamento.

---

<div align="center">

**IMMUNE**

*Promovendo a saúde com tratamentos inteligentes*

**Tecnologia em saúde** • **Precisão em doenças complexas** • **Terapia personalizada**

---

Sistema de Análise de Prontuários v2.0

Desenvolvido com ❤️ pela equipe IMMUNE

</div>
