# IMMUNED - Sistema de Análise de Prontuários Médicos

<div align="center">

![IMMUNE Logo](LOGO.jpeg)

**Promovendo a saúde com tratamentos inteligentes**

*Tecnologia em saúde combinando cada paciente com a terapia mais eficaz*

*Precisão em doenças complexas*

---

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-Proprietário-green.svg)]()
[![Version](https://img.shields.io/badge/Version-3.5-brightgreen.svg)]()

</div>

---

## 🌟 Sobre a IMMUNE

A **IMMUNE** é uma empresa de tecnologia em saúde focada em:

- 🎯 **Precisão Terapêutica**: Combinamos cada paciente com a terapia mais eficaz
- 🔬 **Análise Avançada**: Processamento inteligente de dados clínicos complexos
- 💡 **Tratamentos Inteligentes**: Decisões baseadas em evidências e dados reais
- 🏥 **Doenças Complexas**: Especialização em condições que requerem análise detalhada

---

## 🆕 Novidades da Versão 3.5

Versão focada em **correção de extração** (revisão) e **limpeza de coorte**.
Detalhes em [`CHANGELOG_v35.md`](CHANGELOG_v35.md).

- 🔴 **Negação tratada:** *"não faz uso"*, *"nega uso"*, *"sem uso"*, *"não está
  em uso"* passam a ser classificados como **não-ativo**. Antes contavam como uso
  atual (`SIM`) e inflavam sistematicamente as taxas. *(Reprocessar a base muda
  os números para menos — isso é a correção funcionando.)*
- 🟠 **Deduplicação por paciente:** a chave passou a ser
  `paciente + tipo + data_hora + descricao`, evitando apagar registros reais de
  pacientes diferentes que compartilham frases padronizadas.
- 🟠 **Múltiplos biológicos:** 2+ biológicos ativos no mesmo registro são
  marcados como `MÚLTIPLO` (com a lista completa preservada) em vez de fixar
  silenciosamente o primeiro da configuração.
- ✨ **Exclusão de AIJ:** pacientes com Artrite Idiopática Juvenil (por texto ou
  CID-10 **M08**) são removidos inteiros da coorte (checkbox *Filtros de coorte*,
  ligado por padrão).

Herança das versões anteriores: categoria `INDETERMINADO`, base longitudinal com
status em dois momentos (`_t0`/`_t1`), aliases com fronteira de palavra e status
por proximidade (v3.4); Análise de Trocas de Medicamentos (v3.2, abaixo).

---

## 🆕 Novidades da Versão 3.2 (histórico)

### 🔄 **Nova Funcionalidade: Análise de Trocas de Medicamentos**

A versão 3.2 adiciona uma poderosa análise de padrões de troca entre medicamentos biológicos e DMARDs, permitindo:

#### **6 Tipos de Análise Avançada:**

1. **📊 Visão Geral das Trocas**
   - Taxa de troca entre pacientes
   - Distribuição: primeiro biológico vs pacientes que trocaram
   - Número médio de trocas por paciente
   - Distribuição do número de trocas

2. **🔀 Matriz de Transição**
   - Heatmap interativo mostrando padrões DE → PARA
   - Identificação automática da transição mais comum
   - Tabela detalhada de todas as transições

3. **📉 Taxa de Abandono por Medicamento**
   - Ranking de medicamentos por taxa de suspensão
   - Gráfico comparativo colorido
   - Destaque para medicamentos com maior taxa de abandono

4. **📋 Motivos de Suspensão**
   - Gráfico sunburst hierárquico (Medicamento → Motivo)
   - Top 5 motivos mais frequentes
   - Tabela cruzada: Medicamento × Motivo
   - Motivos capturados: falha terapêutica, hepatotoxicidade, intolerância, alopécia, infecção, etc.

5. **🔗 Sequências de Tratamento Comuns**
   - Top 10 linhas terapêuticas mais seguidas
   - Formato: Med1 → Med2 → Med3
   - Identificação de protocolos de sucesso

6. **🎯 Eficácia Pós-Troca**
   - Comparação: Primeiro biológico vs Após troca(s)
   - Métricas de resposta por grupo
   - Interpretação automática dos resultados

#### **Insights Clínicos Possíveis:**

- ✅ *"45% dos pacientes trocaram de biológico pelo menos uma vez"*
- ✅ *"Adalimumabe → Tofacitinibe é a troca mais comum (23 pacientes)"*
- ✅ *"Hepatotoxicidade causa 30% das suspensões de MTX"*
- ✅ *"Taxa de resposta: 50% (1º biológico) vs 42% (pós-troca)"*

---

## 📊 Sobre o Sistema

Esta aplicação é um **Pipeline ETL (Extract, Transform, Load)** especializado para análise de prontuários médicos, permitindo:

### ✨ Funcionalidades Principais

#### 1. **Extração Inteligente de Dados**
   - **Marcadores clínicos**: VHS, PCR, DAS28, HAQ, CDAI, SDAI, BASDAI, ASDAS
   - **Comorbidades**: HAS, DM, DLP, FM, OP, obesidade, DPOC, IRC, hepatopatia, depressão
   - **Medicamentos com Status Avançado**:
     - Status: SIM (em uso) / PRÉVIO (suspenso) / NÃO (nunca usou)
     - JAK inibidores: Tofacitinibe, Upadacitinibe, Baricitinibe
     - Anti-TNF: Adalimumabe, Etanercepte, Golimumabe, Infliximabe, Certolizumabe
     - Outros biológicos: Tocilizumabe, Rituximabe, Abatacepte, Secuquinumabe, Ixequizumabe
     - DMARDs: Metotrexato (com dose, via e motivo), Leflunomida, Sulfassalazina, Hidroxicloroquina
   - **Fator Reumatoide (FR)**: Resultado (POSITIVO/NEGATIVO/NÃO INFORMADO), valor numérico, origem (LAB/TEXTO/CID-10)

#### 2. **Análise Longitudinal**
   - Comparação baseline vs follow-up
   - Evolução individual de marcadores
   - Cálculo automático de tempo de tratamento

#### 3. **Avaliação de Eficácia**
   - Critérios personalizáveis de melhora
   - Taxa de resposta global e estratificada
   - Análise por subgrupos (idade, sexo, FR, comorbidades, medicamentos)
   - **NOVO:** Análise de padrões de troca entre medicamentos

#### 4. **Visualizações Interativas**
   - 20+ tipos de gráficos com Plotly
   - Dashboards interativos
   - Análise exploratória completa
   - **NOVO:** Heatmap de transições, sunburst de motivos, sequências terapêuticas

#### 5. **Exportação de Dados**
   - Excel e CSV
   - Dados processados e longitudinais
   - Preservação de configurações

---

## 🚀 Instalação Rápida

### Pré-requisitos
- Python 3.9 ou superior (necessário para pandas ≥ 2.2)
- pip (gerenciador de pacotes Python)

### Instalação

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# Ou instalar manualmente:
pip install "pandas>=2.2.0,<3.0.0" streamlit plotly openpyxl

# 2. Garantir que LOGO.jpeg está no mesmo diretório (opcional; há fallback)

# 3. Executar aplicação
streamlit run app_immuned_v35.py
```

> **pandas:** o `requirements.txt` fixa `pandas>=2.2.0,<3.0.0`. O teto evita o
> pandas 3.x (strings via PyArrow por padrão quebram reduções numéricas no
> Streamlit Cloud); o piso garante compatibilidade com numpy 2.x.

### Testes

```bash
python3 teste_v35.py    # deve terminar em "TODOS OS TESTES PASSARAM"
```

### Estrutura de Arquivos

```
📁 repositório/
├── 📄 app_immuned_v35.py        # Aplicação principal (v3.5) — usar este
├── 📄 app_immuned_v34.py        # Versão anterior
├── 📄 app_immuned_v33.py
├── 📄 app_immuned_v32.py
├── 📄 patch_v34_to_v35.py       # Gera a v3.5 a partir da v3.4 (reexecutável)
├── 📄 teste_v35.py              # Suíte de testes (45 asserções)
├── 📄 teste_v34.py
├── 📄 extraction_module.py
├── 📄 requirements.txt          # Dependências (pandas pinado)
├── 🖼️ LOGO.jpeg                 # Logo da IMMUNE
├── 📄 README.md                 # Este arquivo
├── 📄 INDEX.md                  # Índice da documentação
├── 📄 CHANGELOG_v35.md          # Mudanças da v3.5
├── 📄 CHANGELOG_v32.md
└── 📄 GUIA_RAPIDO_v32.md
```

---

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

---

## 🎯 Casos de Uso

### 1. Artrite Reumatoide (AR)

**Configuração Típica:**
- **Marcadores**: VHS, PCR, DAS28, HAQ, CDAI
- **Comorbidades**: HAS, DLP, FM, OP
- **Medicamentos**: JAK inibidores, Anti-TNF, Metotrexato
- **Critério de Melhora**: DAS28 < 50% ou HAQ redução > 0.35

**Análise Disponível:**
- Taxa de resposta por medicamento
- Impacto de comorbidades na eficácia
- Evolução de marcadores inflamatórios
- Tempo médio para resposta
- **NOVO:** Padrões de troca entre biológicos, motivos de suspensão

### 2. Espondilite Anquilosante (EA)

**Configuração Típica:**
- **Marcadores**: BASDAI, ASDAS, PCR, VHS
- **Medicamentos**: Anti-TNF, Anti-IL17, JAK inibidores
- **Critério de Melhora**: BASDAI redução > 50%

**Análise Disponível:**
- Resposta por classe de medicamento
- **NOVO:** Sequências de tratamento mais eficazes

### 3. Outras Doenças Reumatológicas

O sistema é totalmente configurável para:
- Lúpus Eritematoso Sistêmico (LES)
- Psoríase / Artrite Psoriásica
- Doença Inflamatória Intestinal (DII)
- E qualquer condição com dados longitudinais

---

## 🔬 Metodologia

### Pipeline ETL

```
┌─────────────────────────────────────────────────────────────┐
│  1. EXTRACT (Extração)                                      │
│     • Carregamento de dados                                 │
│     • Identificação de padrões em texto livre              │
│     • Extração de valores numéricos e flags                │
│     • Extração de status de medicamentos (SIM/PRÉVIO/NÃO)  │
│     • Identificação de motivos de suspensão                │
│     • Inferência de FR por CID-10                          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  2. TRANSFORM (Transformação)                               │
│     • Limpeza de dados numéricos                           │
│     • Agrupamento por paciente (evita duplicatas)          │
│     • Criação de base longitudinal (t0 → t1)               │
│     • Cálculo de tempo de tratamento                       │
│     • Construção de histórico de medicamentos              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  3. LOAD (Análise)                                          │
│     • Cálculo de eficácia (critérios clínicos)            │
│     • Análise estatística descritiva                       │
│     • Estratificação por subgrupos                         │
│     • Análise de padrões de troca (NOVO v3.2)             │
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

---

## 📊 Visualizações Disponíveis

### Demografia
- ✅ Distribuição de idades (histograma)
- ✅ Proporção por sexo (gráfico pizza)
- ✅ Idade estratificada por sexo

### Fator Reumatoide (NOVO v3.1)
- ✅ Distribuição FR (POSITIVO/NEGATIVO/NÃO INFORMADO)
- ✅ Origem da informação (LAB/TEXTO/CID)
- ✅ Valores laboratoriais (histograma e boxplot)

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
- ✅ Status detalhado (SIM/PRÉVIO/NÃO)
- ✅ Distribuição por grupo terapêutico

### Eficácia Terapêutica
- ✅ Taxa de resposta global
- ✅ Evolução t0 → t1 (box plots)
- ✅ Mudança individual (scatter plots)
- ✅ Análise estratificada (sexo, idade, FR, comorbidades, medicamentos)

### Análise de Trocas (NOVO v3.2)
- ✅ Taxa de troca geral
- ✅ Matriz de transição DE → PARA (heatmap)
- ✅ Taxa de abandono por medicamento
- ✅ Motivos de suspensão (sunburst)
- ✅ Sequências de tratamento comuns
- ✅ Eficácia comparativa (primeiro bio vs pós-troca)

---

## 🎨 Interface do Usuário

### Design IMMUNE

A interface utiliza as cores da marca IMMUNE:
- **Gradiente principal**: Azul (#3b82f6) → Ciano (#06b6d4)
- **Tema minimalista branco**
- **Navegação intuitiva por tabs**
- **Feedback visual em tempo real**

### Tabs do Sistema

1. **📊 Visão Geral**: Estatísticas gerais e preview dos dados
2. **🔧 Configurar ETL**: Interface para configuração do pipeline
3. **📈 Análise Exploratória**: Visualizações e estatísticas descritivas
   - 👥 Demografia
   - 🧬 Fator Reumatoide
   - 📊 Marcadores
   - 🏥 Comorbidades
   - 💊 Medicamentos
4. **🎯 Análise de Eficácia**: Avaliação de resposta terapêutica
   - Por Sexo
   - Por Idade
   - Por FR
   - Por Comorbidades
   - Por Medicamentos
   - **🔄 Análise de Trocas (NOVO v3.2)**
5. **💾 Exportar Dados**: Download de resultados processados

---

## ⚙️ Configuração Avançada

### Marcadores Personalizados

```python
# Configure diretamente na interface web:
# Tab 2 → Seção "Marcadores Clínicos" → Marque os checkboxes desejados

# Marcadores disponíveis:
# VHS, Leucócitos, PCR, HAQ, DAS28, CDAI, SDAI, BASDAI, ASDAS
```

### Medicamentos Personalizados

```python
# Configure na interface web:
# Tab 2 → Seção "Medicamentos"

# JAK Inibidores:
# - Tofacitinibe, Upadacitinibe, Baricitinibe

# Anti-TNF:
# - Adalimumabe, Etanercepte, Golimumabe, Infliximabe, Certolizumabe

# Outros Biológicos:
# - Tocilizumabe, Rituximabe, Abatacepte, Secuquinumabe, Ixequizumabe

# DMARDs:
# - Metotrexato, Leflunomida, Sulfassalazina, Hidroxicloroquina
```

### Critérios Customizados

```python
# Configure na interface web:
# Tab 2 → Seção "Critérios de Melhora"

# Exemplos:
# HAQ: Redução mínima de 0.35 pontos
# DAS28: Redução de 50%
# CDAI: Redução de 10 pontos
```

---

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

---

## 📈 Performance

### Capacidade

- ✅ Até 5.000 pacientes: Performance excelente (<2s)
- ⚠️ 5.000-10.000 pacientes: Aceitável (2-5s)
- 🔄 Acima de 10.000: Recomenda-se filtros por período ou amostragem

### Otimizações

- Uso de `.groupby()` para agregações eficientes
- Cálculos vetorizados com pandas e numpy
- Gráficos renderizados sob demanda (lazy loading)
- Cache de resultados intermediários em session_state

---

## 🤝 Suporte

### Para Problemas Técnicos

1. Consulte o **GUIA_RAPIDO_v32.md** na seção "Solução de Problemas"
2. Verifique se todas as dependências estão instaladas: `pip list`
3. Confirme que `LOGO.jpeg` está no diretório correto
4. Valide a estrutura do arquivo de entrada
5. Consulte **CHANGELOG_v32.md** para troubleshooting detalhado

### Documentação Adicional

- 📖 **GUIA_RAPIDO_v32.md** - Início rápido em 5 minutos
- 📋 **CHANGELOG_v32.md** - Detalhes técnicos da v3.2
- 🗺️ **INDEX.md** - Índice completo da documentação

### Contato IMMUNE

Para questões sobre a plataforma IMMUNE ou parcerias:

- 🌐 Website: [LinkedIn - IMMUNED](https://www.linkedin.com/company/immuned/)
- 📧 Email: heloisaleao1183@gmail.com
- 💼 LinkedIn: [Perfil IMMUNE](https://www.linkedin.com/company/immuned/)

---

## 🔄 Atualizações

### Versão 3.5 - Atual (Agosto 2026)

**Correções (revisão):**
- ✅ Negação tratada ("não/nega/sem uso" → não-ativo)
- ✅ Deduplicação por paciente (não apaga registros reais)
- ✅ Múltiplos biológicos no mesmo registro → `MÚLTIPLO`

**Novidade:**
- ✅ Exclusão de coorte AIJ (texto + CID-10 M08)

Ver [`CHANGELOG_v35.md`](CHANGELOG_v35.md).

### Versão 3.4 (2026)

- ✅ Aliases com fronteira de palavra (fim de falsos positivos como `ada` em "indicada")
- ✅ Status por proximidade + categoria `INDETERMINADO`
- ✅ Base longitudinal com status em dois momentos (`_t0`/`_t1`)
- ✅ Ordenação cronológica antes das agregações

### Versão 3.3

- ✅ Ajustes de extração e interface (base para a v3.4)

### Versão 3.2 (Novembro 2025)

- ✅ **Análise de Trocas de Medicamentos** (6 tipos de análise)
- ✅ Matriz de transição DE → PARA, taxa de abandono, motivos de suspensão
- ✅ Sequências de tratamento e eficácia pós-troca

### Versão 3.1 (Outubro 2025)

**Principais Funcionalidades:**
- ✅ Interface IMMUNE com identidade visual
- ✅ Extração de Fator Reumatoide (FR) com inferência por CID-10
- ✅ Status de medicamentos: SIM/PRÉVIO/NÃO
- ✅ MTX detalhado (dose, via, motivo suspensão)
- ✅ Biológicos expandidos (+4 medicamentos)
- ✅ Análise expandida com 15+ visualizações
- ✅ Configuração 100% personalizável
- ✅ Exportação multi-formato

### Versão 2.0 (Setembro 2025)

- ✅ Correção de bug de percentuais
- ✅ Análise por subgrupos
- ✅ Interface completa Streamlit

### Roadmap Futuro (v3.3+)

- 🔮 **Análise Temporal**: Tempo médio até troca, curvas de sobrevivência (Kaplan-Meier)
- 🔮 **Filtros Interativos**: Por período, grupo terapêutico, número de trocas
- 🔮 **Machine Learning**: Predição de resposta terapêutica, fatores de risco para suspensão
- 🔮 **API REST**: Integração com sistemas hospitalares
- 🔮 **Relatórios Automatizados**: PDF com análises completas
- 🔮 **Dashboard em Tempo Real**: Monitoramento contínuo
- 🔮 **Análise de Custo-Efetividade**: Comparação econômica entre opções

---

## 📚 Exemplos de Uso

### Exemplo 1: Análise Básica de Eficácia

```python
# 1. Upload dos dados na Tab 1
# 2. Configurar ETL na Tab 2:
#    - Marcar: VHS, PCR, DAS28, HAQ
#    - Marcar: HAS, DM, DLP
#    - Marcar: Tofacitinibe, Adalimumabe
#    - Critério: DAS28 < 50%
# 3. Processar dados
# 4. Ver resultados na Tab 4

# Resultado esperado:
# - Taxa de resposta: 45%
# - Resposta por sexo, idade, comorbidades
# - Evolução de marcadores
```

### Exemplo 2: Análise de Trocas (NOVO v3.2)

```python
# 1. Processar dados com biológicos selecionados
# 2. Ir para Tab 4 → Subtab "🔄 Análise de Trocas"
# 3. Explorar as 6 seções:

# Insights possíveis:
# - "40% dos pacientes trocaram de biológico"
# - "Adalimumabe → Tofacitinibe: 23 pacientes"
# - "Infliximabe tem 38% de taxa de abandono"
# - "Hepatotoxicidade: 30% das suspensões de MTX"
# - "Sequência comum: Ada → Tofa → Eta"
# - "Eficácia: 50% (1º bio) vs 42% (pós-troca)"
```

### Exemplo 3: Identificar Medicamento Problemático

```python
# Objetivo: Descobrir qual biológico tem mais suspensões

# Passos:
# 1. Tab 4 → Análise de Trocas
# 2. Seção "Taxa de Abandono"
# 3. Ver ranking

# Resultado:
# 1. Infliximabe: 38.5%
# 2. Adalimumabe: 35.2%
# 3. Etanercepte: 28.1%

# Ação: Investigar causas específicas na seção "Motivos"
```

---

## 🎓 Tutoriais e Documentação

### Documentação Completa

Todos os arquivos estão na **raiz do repositório**:

1. **[CHANGELOG_v35.md](CHANGELOG_v35.md)**
   - Correções da v3.5 (negação, dedup, MÚLTIPLO, AIJ)
   - Mudanças técnicas e checklist de validação

2. **[INDEX.md](INDEX.md)**
   - Índice da documentação e histórico de versões

3. **[GUIA_RAPIDO_v32.md](GUIA_RAPIDO_v32.md)**
   - Início rápido e casos de uso (base da v3.2, ainda útil)

4. **[CHANGELOG_v32.md](CHANGELOG_v32.md)**
   - Histórico: Análise de Trocas de Medicamentos (v3.2)

### Vídeos Tutoriais (Em Breve)

- 🎥 Instalação e Configuração (5 min)
- 🎥 Análise Básica de Eficácia (10 min)
- 🎥 Análise Avançada de Trocas (15 min)
- 🎥 Casos Práticos: AR e EA (20 min)

---

## ❓ FAQ - Perguntas Frequentes

### Instalação e Configuração

**P: Quais são os requisitos mínimos?**
R: Python 3.9+ (para pandas ≥ 2.2), 4GB RAM, 100MB espaço em disco

**P: Funciona no Windows/Mac/Linux?**
R: Sim, é multiplataforma (testado em Windows 10/11, macOS 12+, Ubuntu 20.04+)

**P: Preciso instalar banco de dados?**
R: Não, o sistema usa apenas arquivos Excel/CSV

### Uso da Aplicação

**P: Meus dados estão seguros?**
R: Sim, tudo é processado localmente. Nenhum dado é enviado para nuvem.

**P: Posso usar com outras doenças além de AR/EA?**
R: Sim, o sistema é totalmente configurável para qualquer doença com dados longitudinais.

**P: Como exporto os resultados?**
R: Tab 5 (Exportar Dados) → Download Excel ou CSV

### Análise de Trocas (v3.2)

**P: Preciso reprocessar dados da v3.1?**
R: Não se já usou v3.1, os dados já têm as colunas necessárias. Só precisa atualizar o código.

**P: Quantos medicamentos preciso selecionar?**
R: Pelo menos 1 biológico para análise de trocas funcionar.

**P: E se não há trocas nos meus dados?**
R: A análise mostrará "Nenhuma transição identificada" e outras seções continuam funcionando.

---

## 📄 Licença

© 2025 IMMUNE. Todos os direitos reservados.

Este software é proprietário e de uso restrito. Entre em contato com IMMUNE para informações sobre licenciamento.

---

## 🙏 Agradecimentos

- Equipe de desenvolvimento IMMUNE
- Colaboradores médicos e pesquisadores
- Comunidades Python, Streamlit e Plotly
- Pacientes que contribuem com dados anônimos

---

## 📞 Contato e Suporte

### Suporte Técnico
- 📧 Email: heloisaleao1183@gmail.com
- 📖 Documentação: Consulte `docs/`
- 🐛 Problemas: Veja `GUIA_RAPIDO_v32.md` seção "Solução de Problemas"

### Parcerias e Licenciamento
- 🌐 LinkedIn: https://www.linkedin.com/company/immuned/
- 📧 Email: heloisaleao1183@gmail.com

---

<div align="center">

**IMMUNE**

*Promovendo a saúde com tratamentos inteligentes*

**Tecnologia em saúde** • **Precisão em doenças complexas** • **Terapia personalizada**

---

Sistema de Análise de Prontuários **v3.5**

Desenvolvido com ❤️ pela equipe IMMUNE

---

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io/)
[![Version](https://img.shields.io/badge/Version-3.5-brightgreen.svg)]()
[![Docs](https://img.shields.io/badge/Docs-Complete-blue.svg)]()

**[Índice](INDEX.md)** | **[Changelog v3.5](CHANGELOG_v35.md)** | **[Guia Rápido](GUIA_RAPIDO_v32.md)**

</div>
