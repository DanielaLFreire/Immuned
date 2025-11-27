# 🚀 Guia Rápido: Análise de Trocas - IMMUNED v3.2

## ⚡ Início Rápido (5 minutos)

### 1️⃣ **Instalar Dependências**
```bash
pip install streamlit pandas plotly numpy openpyxl pillow
```

### 2️⃣ **Executar Aplicação**
```bash
streamlit run app_immuned_v32_com_analise_trocas.py
```

### 3️⃣ **Processar Dados**

**Na Tab 2 (Configurar ETL):**

1. Fazer upload do arquivo de dados
2. **IMPORTANTE:** Selecionar pelo menos 1 medicamento biológico:
   - ✅ Tofacitinibe
   - ✅ Adalimumabe
   - ✅ Etanercepte
   - ✅ (ou qualquer outro biológico)

3. Configurar marcadores e comorbidades (opcional)
4. Clicar em "🚀 Processar Dados (ETL)"

### 4️⃣ **Acessar Análise de Trocas**

**Na Tab 4 (Análise de Eficácia):**

1. Clicar na subtab: **"🔄 Análise de Trocas"**
2. Explorar as 6 seções de análise
3. Visualizar gráficos e insights

---

## 📊 O Que Você Verá

### Seção 1: Visão Geral
```
┌─────────────────────────────────────────┐
│  📊 Visão Geral das Trocas              │
├─────────────────────────────────────────┤
│  Total: 323 pacientes                   │
│  Primeiro Biológico: 195 (60.4%)        │
│  Trocaram: 128 (39.6%)                  │
│  Taxa de Troca: 39.6%                   │
└─────────────────────────────────────────┘
```

### Seção 2: Matriz de Transição
```
              ➡️ PARA
         Tofa  Ada  Eta  Inflix
    ┌────┬────┬────┬────┬──────┐
 DE │Ada │ 0  │ 15 │  8 │  12  │
    │Eta │ 5  │  3 │  0 │   7  │
    │Tofa│ 2  │  1 │  4 │   0  │
    └────┴────┴────┴────┴──────┘
```
*Exemplo: 15 pacientes retornaram para Adalimumabe*

### Seção 3: Taxa de Abandono
```
Ranking:
1. Infliximabe    38.5%  ████████
2. Adalimumabe    35.2%  ███████
3. Etanercepte    28.1%  ██████
4. Tofacitinibe   22.3%  ████
```

### Seção 4: Motivos
```
Top Motivos:
• Falha terapêutica: 45 pacientes
• Hepatotoxicidade:  28 pacientes
• Intolerância:      18 pacientes
• Infecção:          12 pacientes
• Alopécia:           8 pacientes
```

### Seção 5: Sequências
```
Top 3 Sequências:
1. Ada → Tofa → Eta       (23 pacientes)
2. Inflix → Ada           (18 pacientes)
3. Eta → Tofa             (15 pacientes)
```

### Seção 6: Eficácia
```
Comparativo:
┌──────────────────┬───────┬──────┐
│ Grupo            │ Taxa  │  N   │
├──────────────────┼───────┼──────┤
│ Primeiro Bio     │ 50.0% │ 195  │
│ Após Troca(s)    │ 42.0% │ 128  │
└──────────────────┴───────┴──────┘

⚠️ Primeiro biológico tem melhor resposta
```

---

## 💡 Casos de Uso Práticos

### Caso 1: Identificar Medicamento Problemático
**Pergunta:** "Qual biológico tem mais suspensões?"

**Como fazer:**
1. Ir para Seção 3 (Taxa de Abandono)
2. Ver ranking
3. Olhar medicamento no topo

**Resultado:**
- "Infliximabe: 38.5% de abandono"
- **Ação:** Investigar causas, considerar protocolo diferente

---

### Caso 2: Planejar Protocolo de Segunda Linha
**Pergunta:** "Para onde os pacientes vão quando falham com Adalimumabe?"

**Como fazer:**
1. Ir para Seção 2 (Matriz de Transição)
2. Olhar linha "Adalimumabe"
3. Ver valores nas colunas

**Resultado:**
- "15 → Adalimumabe (retorno)"
- "12 → Infliximabe"
- "8 → Etanercepte"
- **Ação:** Protocolo: tentar Infliximabe como 2ª linha

---

### Caso 3: Justificar Troca de Medicamento
**Pergunta:** "Por que tantos pacientes param MTX?"

**Como fazer:**
1. Ir para Seção 4 (Motivos)
2. Filtrar por MTX (se disponível)
3. Ver distribuição de motivos

**Resultado:**
- "60% hepatotoxicidade"
- "25% intolerância GI"
- **Ação:** Monitorar função hepática, considerar via SC

---

### Caso 4: Avaliar Eficácia de Linha Tardia
**Pergunta:** "Pacientes respondem melhor no 1º ou 2º biológico?"

**Como fazer:**
1. Ir para Seção 6 (Eficácia Pós-Troca)
2. Comparar taxas

**Resultado:**
- "1º bio: 50% | 2ª linha: 42%"
- **Ação:** Iniciar biológico mais cedo, evitar atraso

---

## 🎨 Customizações Rápidas

### Aumentar Número de Sequências
No código, linha ~1930:
```python
# ANTES:
df_seq = identificar_sequencias_comuns(df_long, biologicos, top_n=10)

# DEPOIS (para ver top 20):
df_seq = identificar_sequencias_comuns(df_long, biologicos, top_n=20)
```

### Alterar Cores dos Gráficos
Exemplo - mudar cores da matriz de transição (linha ~1895):
```python
# ANTES:
colorscale='Blues',

# DEPOIS:
colorscale='Viridis',  # ou 'Reds', 'Greens', 'Purples'
```

### Adicionar Filtro por Período
No início da subtab_trocas (após linha ~1850):
```python
# Adicionar filtro de data
col1, col2 = st.columns(2)
with col1:
    data_inicio = st.date_input("Data Início")
with col2:
    data_fim = st.date_input("Data Fim")

# Filtrar dados
if 'data_hora_t0' in df_long.columns:
    df_long = df_long[
        (df_long['data_hora_t0'] >= pd.to_datetime(data_inicio)) &
        (df_long['data_hora_t0'] <= pd.to_datetime(data_fim))
    ]
```

---

## 🐛 Solução de Problemas Comuns

### ❌ "Configure medicamentos biológicos no ETL"
**Causa:** Nenhum biológico foi selecionado na configuração

**Solução:**
1. Voltar para Tab 2
2. Na seção "3. Medicamentos"
3. Marcar pelo menos 1 checkbox em "JAK Inibidores" ou "Anti-TNF"
4. Reprocessar dados

---

### ❌ "Nenhuma transição identificada"
**Causa:** Não há pacientes com status "PRÉVIO"

**Solução:**
1. Verificar se os dados têm informação de suspensão
2. Checar se o padrão de extração está capturando "uso prévio"
3. Validar texto nos prontuários (deve mencionar suspensão/troca)

**Exemplo de texto esperado:**
```
USO PRÉVIO:
- Adalimumabe (suspenso por falha terapêutica)

EM USO:
- Tofacitinibe 5mg
```

---

### ❌ Gráficos aparecem vazios
**Causa:** Dados insuficientes ou colunas ausentes

**Solução:**
1. Verificar se processamento ETL foi concluído
2. Confirmar que `df_longitudinal` existe em session_state
3. Validar que há pelo menos 5 pacientes com dados completos

**Debug:**
```python
# Adicionar no início da subtab_trocas:
st.write("Debug - Colunas disponíveis:", df_long.columns.tolist())
st.write("Debug - Shape:", df_long.shape)
st.write("Debug - Sample:", df_long.head())
```

---

### ❌ Erro: "module 'numpy' has no attribute..."
**Causa:** Numpy não instalado ou versão antiga

**Solução:**
```bash
pip install --upgrade numpy
```

---

## 📚 Recursos Adicionais

### Arquivos de Referência:
1. `CHANGELOG_v32.md` - Mudanças detalhadas
2. `ANALISE_TROCAS_README.md` - Documentação completa das análises
3. `app_immuned_v32_com_analise_trocas.py` - Código fonte

### Exemplos de Dados:
O sistema espera prontuários com texto como:

```
MEDICAÇÕES EM USO:
Tofacitinibe 5mg 12/12h
Metotrexato 15mg/semana VO

USO PRÉVIO:
Adalimumabe 40mg SC 14/14d (suspenso em 2024 por falha terapêutica)
Infliximabe (hepatotoxicidade - 2023)
```

### Padrões Reconhecidos:
- ✅ "em uso", "mantém", "usando"
- ✅ "uso prévio", "suspenso", "descontinuado"
- ✅ "falha", "intolerância", "hepatotoxicidade"

---

## 🎯 Checklist Rápido

Antes de usar:
- [ ] Arquivo v3.2 executando sem erros
- [ ] Dados carregados com sucesso
- [ ] Pelo menos 1 biológico selecionado
- [ ] ETL processado completamente
- [ ] Nova subtab "🔄 Análise de Trocas" visível

Durante o uso:
- [ ] Métricas fazem sentido (% não ultrapassam 100%)
- [ ] Gráficos renderizando corretamente
- [ ] Insights alinhados com expectativa clínica
- [ ] Números batem com contagem manual de amostra

---

## 💬 Feedback

Encontrou um bug ou tem sugestão?
1. Anotar o erro específico
2. Capturar screenshot se possível
3. Verificar versão do Streamlit: `streamlit --version`

---

**Tudo pronto! Boa análise! 📊🎯**

*Guia Rápido v3.2 - IMMUNED*
