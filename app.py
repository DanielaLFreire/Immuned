# -*- coding: utf-8 -*-
"""
Aplicação Streamlit - Análise de Prontuários Médicos
Sistema ETL Generalizado para Análise de Eficácia Terapêutica
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import re
import io
from PIL import Image

# =============================================================================
# CONFIGURAÇÕES DA PÁGINA
# =============================================================================

# Carregar logo
logo = Image.open('LOGO.jpeg')

st.set_page_config(
    page_title="Immuned - Análise de Prontuários",
    page_icon=logo,  # ← Passar objeto Image
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': """
        ### Immuned
        **Promovendo a saúde com tratamentos inteligentes.**
        
        Tecnologia em saúde combinando cada paciente com a terapia mais eficaz.
        Precisão em doenças complexas.
        """
    }
)

# CSS customizado para tema Immuned - Minimalista
st.markdown("""
    <style>
    /* Importar fonte Poppins */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');
    
    /* Mudar linha vermelha do Streamlit para azul */
    .main .block-container {
        padding-top: 2rem;
    }
    
    /* Linha de progresso azul */
    .stProgress > div > div > div {
        background-color: #3b82f6 !important;
    }
    
    /* Spinner azul */
    .stSpinner > div {
        border-top-color: #3b82f6 !important;
    }
    
    /* Links azuis */
    a {
        color: #3b82f6 !important;
    }
    
    /* Tema totalmente branco */
    .main {
        background-color: #ffffff;
    }
    
    /* Header minimalista - SEM bordas */
    .immune-header {
        background-color: #ffffff;
        padding: 2rem;
        margin-bottom: 2rem;
    }
    
    .immune-title {
        background: linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-family: 'Poppins', sans-serif;
        font-size: 3rem;
        font-weight: 700;
        margin: 0;
        text-align: center;
        letter-spacing: -0.5px;
    }
    
    .immune-subtitle {
        color: #6b7280;
        font-family: 'Poppins', sans-serif;
        font-size: 1rem;
        text-align: center;
        margin-top: 0.5rem;
        font-weight: 400;
    }
    
    /* Estilo dos cards - sem bordas */
    .stMetric {
        background-color: #ffffff;
        padding: 1rem;
        border-radius: 8px;
    }
    
    /* Botões - cores da marca (azul) */
    .stButton>button {
        background: linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 2rem;
        font-family: 'Poppins', sans-serif;
        font-weight: 600;
        transition: all 0.3s ease;
        letter-spacing: 0.3px;
    }
    
    .stButton>button:hover {
        background: linear-gradient(135deg, #2563eb 0%, #0891b2 100%);
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
    }
    
    /* Tabs - minimalista azul */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 2px solid #f3f4f6;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        border-radius: 8px 8px 0 0;
        padding: 12px 24px;
        font-family: 'Poppins', sans-serif;
        font-weight: 500;
        color: #9ca3af;
        border: none;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: transparent;
        color: #3b82f6;
        border-bottom: 3px solid #3b82f6;
        font-weight: 600;
    }
    
    /* Sidebar - totalmente branco SEM bordas */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
    }
    
    [data-testid="stSidebar"] .stMarkdown {
        color: #374151;
    }
    
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #3b82f6 !important;
        font-family: 'Poppins', sans-serif !important;
    }
    
    /* Headers com cor da marca (azul) */
    h1, h2, h3 {
        font-family: 'Poppins', sans-serif !important;
        color: #3b82f6 !important;
    }
    
    /* Footer minimalista */
    .immune-footer {
        text-align: center;
        padding: 2rem;
        margin-top: 3rem;
        color: #9ca3af;
        font-family: 'Poppins', sans-serif;
        font-size: 0.9rem;
        background-color: #ffffff;
    }
    
    /* Texto da sidebar */
    [data-testid="stSidebar"] label {
        color: #374151 !important;
        font-family: 'Poppins', sans-serif !important;
    }
    
    /* Ajuste do expander */
    .streamlit-expanderHeader {
        font-family: 'Poppins', sans-serif !important;
        color: #3b82f6 !important;
    }
    
    /* Remover barra de separação da sidebar */
    [data-testid="stSidebar"] > div:first-child {
        border-right: none;
    }
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def is_number(s):
    """Verifica se uma string contém números"""
    return bool(re.search(r'\d', str(s)))


def extract_generic(df, keywords_dict, column_name='descricao'):
    """
    Função genérica de extração de dados dos prontuários
    
    Args:
        df: DataFrame com os dados
        keywords_dict: Dicionário com palavras-chave a buscar
        column_name: Nome da coluna com o texto a processar
    
    Returns:
        DataFrame com novas colunas extraídas
    """
    # Inicializar colunas
    for key in keywords_dict.keys():
        df[key] = None
    
    # Processar cada linha
    for idx, text in enumerate(df[column_name]):
        if pd.isna(text):
            continue
            
        text_lower = str(text).lower()
        words = text_lower.split()
        
        for i, word in enumerate(words):
            # Limpar pontuação
            word_clean = re.sub(r'[:\\<>;/\']', '', word)
            
            # Verificar se é palavra-chave
            if word_clean in keywords_dict.keys():
                # Procurar valor numérico nas próximas palavras
                for j in range(i+1, min(i+5, len(words))):
                    next_word = words[j]
                    
                    # Verificar operadores
                    operator = ''
                    if next_word in ['<', '>', '=', '<=', '>=']:
                        operator = next_word
                        continue
                    
                    # Extrair número
                    if is_number(next_word):
                        number_match = re.search(r'(\d+[.,]?\d*)', next_word)
                        if number_match and pd.isna(df.loc[idx, word_clean]):
                            df.loc[idx, word_clean] = operator + number_match.group(1)
                            break
    
    return df


def extract_binary_flags(df, keywords_dict, column_name='descricao'):
    """
    Extrai flags binárias (presença/ausência) de condições
    
    Args:
        df: DataFrame com os dados
        keywords_dict: Dicionário com palavras-chave
        column_name: Nome da coluna com o texto
    
    Returns:
        DataFrame com colunas binárias (0/1)
    """
    for key in keywords_dict.keys():
        df[key] = 0
    
    for idx, text in enumerate(df[column_name]):
        if pd.isna(text):
            continue
            
        text_lower = str(text).lower()
        
        for key, aliases in keywords_dict.items():
            # Verificar se algum termo está presente
            for term in aliases:
                if term in text_lower:
                    df.loc[idx, key] = 1
                    break
    
    return df


def clean_numeric_columns(df, columns):
    """Limpa e converte colunas numéricas"""
    for col in columns:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.extract(r'(\d+[.,]?\d*)', expand=False)
                .str.replace(',', '.', regex=False)
            )
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def create_longitudinal_data(df, baseline_type, followup_type, marker_cols, 
                            date_col='data_hora', patient_col='paciente'):
    """
    Cria base longitudinal com medidas t0 e t1
    
    Args:
        df: DataFrame processado
        baseline_type: Valor que identifica baseline (ex: 'ANAMNESE')
        followup_type: Valor que identifica follow-up (ex: 'EVOLUCAO')
        marker_cols: Lista de colunas de marcadores a comparar
        date_col: Nome da coluna de data
        patient_col: Nome da coluna de identificação do paciente
    
    Returns:
        DataFrame longitudinal mesclado
    """
    # Separar baseline e follow-up
    baseline = df[df['tipo'] == baseline_type].copy()
    followup = df[df['tipo'] == followup_type].copy()
    
    # Ordenar por data e pegar registros apropriados
    baseline = baseline.sort_values(by=date_col, ascending=True)
    baseline = baseline.drop_duplicates(subset=[patient_col], keep="first")
    
    followup = followup.sort_values(by=date_col, ascending=False)
    followup = followup.drop_duplicates(subset=[patient_col], keep="first")
    
    # Renomear colunas
    baseline_marker_cols = marker_cols + [date_col]
    baseline.columns = [
        col + '_t0' if col in baseline_marker_cols else col 
        for col in baseline.columns
    ]
    
    followup.columns = [
        col + '_t1' if col in baseline_marker_cols else col 
        for col in followup.columns
    ]
    
    # Identificar colunas para merge
    keep_cols_baseline = [patient_col, 'idade', 'sexo'] + [
        col for col in baseline.columns if '_t0' in col
    ]
    
    # Merge
    merged = baseline[keep_cols_baseline].merge(
        followup,
        on=patient_col,
        how='inner'
    )
    
    # Remover duplicatas de idade/sexo se existirem
    if 'idade_y' in merged.columns:
        merged = merged.drop(columns=['idade_y', 'sexo_y'])
        merged = merged.rename(columns={'idade_x': 'idade', 'sexo_x': 'sexo'})
    
    # Calcular tempo de tratamento
    if f'{date_col}_t0' in merged.columns and f'{date_col}_t1' in merged.columns:
        merged['tempo_tratamento_dias'] = (
            merged[f'{date_col}_t1'] - merged[f'{date_col}_t0']
        ).dt.days
    
    return merged


def calculate_improvement(merged_df, criteria_dict):
    """
    Calcula melhora baseada em critérios personalizados
    
    Args:
        merged_df: DataFrame longitudinal
        criteria_dict: Dicionário com critérios {marcador: função_lambda}
    
    Returns:
        DataFrame com coluna 'improvement'
    """
    merged_df['improvement'] = None
    
    for marker, criteria_func in criteria_dict.items():
        col_t0 = f'{marker}_t0'
        col_t1 = f'{marker}_t1'
        
        if col_t0 in merged_df.columns and col_t1 in merged_df.columns:
            for idx in merged_df.index:
                v0 = merged_df.loc[idx, col_t0]
                v1 = merged_df.loc[idx, col_t1]
                
                if merged_df.loc[idx, 'improvement'] is None:
                    if not pd.isna(v0) and not pd.isna(v1):
                        merged_df.loc[idx, 'improvement'] = int(criteria_func(v0, v1))
    
    merged_df['improvement'] = merged_df['improvement'].fillna(0).astype(int)
    
    return merged_df


# =============================================================================
# INTERFACE STREAMLIT
# =============================================================================

def main():
    # Header IMMUNE com logo
    col_logo, col_title = st.columns([1, 4])
    
    with col_logo:
        try:
            # Tentar carregar logo do mesmo diretório
            import os
            logo_path = os.path.join(os.path.dirname(__file__), 'LOGO.jpeg')
            if os.path.exists(logo_path):
                st.image(logo_path, width=120)
            else:
                # Fallback: emoji
                st.markdown("# 💉")
        except:
            st.markdown("# 💉")
    
    with col_title:
        st.markdown("""
            <div class="immune-header">
                <h1 class="immune-title">Immuned</h1>
                <p class="immune-subtitle">Sistema de Análise de Prontuários Médicos</p>
                <p class="immune-subtitle" style="font-size: 0.95rem;">
                    Promovendo a saúde com tratamentos inteligentes • Precisão em doenças complexas
                </p>
            </div>
        """, unsafe_allow_html=True)
    
    st.header(" Pipeline ETL para Análise de Eficácia Terapêutica")
    st.markdown("---")
    
    # Sidebar - Upload e Configurações
    with st.sidebar:
        st.markdown("⚙️ Configurações")
    
    # Upload de arquivo
    uploaded_file = st.sidebar.file_uploader(
        "📁 Upload do arquivo de dados",
        type=['xlsx', 'xls', 'csv'],
        help="Faça upload da planilha com os prontuários médicos"
    )
    
    if uploaded_file is None:
        st.info("👈 Por favor, faça upload de um arquivo na barra lateral para começar.")
        
        # Mostrar exemplo de estrutura esperada
        with st.expander("📋 Estrutura de dados esperada"):
            st.markdown("""
            O arquivo deve conter as seguintes colunas:
            - **paciente**: ID único do paciente
            - **tipo**: Tipo de registro (ex: ANAMNESE, EVOLUCAO)
            - **data_hora**: Data e hora do registro
            - **descricao**: Texto do prontuário
            - **idade**: Idade do paciente
            - **sexo**: Sexo do paciente (M/F)
            
            Outras colunas são opcionais.
            """)
        return
    
    # Carregar dados
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        # Converter coluna de data se existir
        if 'data_hora' in df.columns:
            df['data_hora'] = pd.to_datetime(df['data_hora'], errors='coerce')
        
        st.sidebar.success(f"✅ Arquivo carregado: {len(df)} registros")
        
    except Exception as e:
        st.sidebar.error(f"❌ Erro ao carregar arquivo: {str(e)}")
        return
    
    # =============================================================================
    # TABS PRINCIPAIS
    # =============================================================================
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Visão Geral",
        "🔧 Configurar ETL",
        "📈 Análise Exploratória",
        "🎯 Análise de Eficácia",
        "💾 Exportar Dados"
    ])
    
    # =============================================================================
    # TAB 1: VISÃO GERAL
    # =============================================================================
    
    with tab1:
        st.subheader("📊 Visão Geral dos Dados")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total de Registros", len(df))
        
        with col2:
            if 'paciente' in df.columns:
                st.metric("Pacientes Únicos", df['paciente'].nunique())
            else:
                st.metric("Pacientes Únicos", "N/A")
        
        with col3:
            if 'tipo' in df.columns:
                st.metric("Tipos de Registro", df['tipo'].nunique())
            else:
                st.metric("Tipos de Registro", "N/A")
        
        with col4:
            if 'data_hora' in df.columns:
                date_range = (df['data_hora'].max() - df['data_hora'].min()).days
                st.metric("Período (dias)", date_range)
            else:
                st.metric("Período (dias)", "N/A")
        
        # Mostrar preview dos dados
        st.markdown("📋 Preview dos Dados")
        st.dataframe(df.head(20), use_container_width=True)
        
        # Informações sobre colunas
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("📐 Informações das Colunas")
            info_df = pd.DataFrame({
                'Coluna': df.columns,
                'Tipo': df.dtypes.values,
                'Não-Nulos': df.count().values,
                '% Completo': (df.count().values / len(df) * 100).round(2)
            })
            st.dataframe(info_df, use_container_width=True)
        
        with col2:
            if 'tipo' in df.columns:
                st.markdown("📊 Distribuição por Tipo")
                tipo_counts = df['tipo'].value_counts()
                fig = px.bar(
                    x=tipo_counts.index,
                    y=tipo_counts.values,
                    labels={'x': 'Tipo', 'y': 'Quantidade'},
                    color=tipo_counts.values,
                    color_continuous_scale='Blues'
                )
                fig.update_layout(showlegend=False, height=300)
                st.plotly_chart(fig, use_container_width=True)
    
    # =============================================================================
    # TAB 2: CONFIGURAR ETL
    # =============================================================================
    
    with tab2:
        st.subheader("🔧 Configuração do Pipeline ETL")
        
        # Verificar requisitos mínimos
        required_cols = ['paciente', 'tipo', 'descricao', 'data_hora']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            st.error(f"❌ Colunas obrigatórias ausentes: {', '.join(missing_cols)}")
            st.info("As seguintes colunas são necessárias: paciente, tipo, descricao, data_hora")
            return
        
        st.success("✅ Todas as colunas obrigatórias presentes!")
        
        # Configuração de Marcadores Clínicos
        st.markdown("📊 1. Marcadores Clínicos")
        
        default_markers = {
            'vhs': 'VHS - Velocidade de Hemossedimentação',
            'leucocitos': 'Leucócitos',
            'pcr': 'PCR - Proteína C-Reativa',
            'haq': 'HAQ - Health Assessment Questionnaire',
            'das28': 'DAS28 - Disease Activity Score',
            'cdai': 'CDAI - Clinical Disease Activity Index',
            'basdai': 'BASDAI - Bath Ankylosing Spondylitis Disease Activity Index',
            'asdas': 'ASDAS - Ankylosing Spondylitis Disease Activity Score'
        }
        
        st.markdown("Selecione os marcadores clínicos a extrair:")
        selected_markers = {}
        
        col1, col2 = st.columns(2)
        
        with col1:
            for key, label in list(default_markers.items())[:4]:
                if st.checkbox(label, value=(key in ['vhs', 'pcr', 'haq', 'das28']), key=f'marker_{key}'):
                    selected_markers[key] = []
        
        with col2:
            for key, label in list(default_markers.items())[4:]:
                if st.checkbox(label, value=(key == 'cdai'), key=f'marker_{key}'):
                    selected_markers[key] = []
        
        # Marcadores personalizados
        with st.expander("➕ Adicionar marcadores personalizados"):
            custom_markers = st.text_area(
                "Digite marcadores personalizados (um por linha):",
                help="Exemplo: glicose, triglicerideos, colesterol"
            )
            if custom_markers:
                for marker in custom_markers.strip().split('\n'):
                    marker = marker.strip().lower()
                    if marker:
                        selected_markers[marker] = []
        
        # Configuração de Comorbidades
        st.markdown("🏥 2. Comorbidades")
        
        default_comorbidities = {
            'has': ['has', 'hipertensão', 'hipertensao'],
            'dlp': ['dlp', 'dislipidemia'],
            'dm': ['dm', 'diabetes', 'diabetes mellitus'],
            'fm': ['fm', 'fibromialgia'],
            'op': ['op', 'osteoporose'],
            'hipotireoidismo': ['hipotireoidismo', 'tireoidite'],
            'doenca_renal': ['doença renal', 'insuficiência renal', 'nefropatia'],
            'doenca_hepatica': ['hepatopatia', 'doença hepática', 'cirrose']
        }
        
        st.markdown("Selecione as comorbidades a identificar:")
        selected_comorbidities = {}
        
        col1, col2 = st.columns(2)
        
        with col1:
            for key, aliases in list(default_comorbidities.items())[:4]:
                label = f"{key.upper()} - {', '.join(aliases[:2])}"
                if st.checkbox(label, value=(key in ['has', 'dlp', 'dm']), key=f'comorb_{key}'):
                    selected_comorbidities[key] = aliases
        
        with col2:
            for key, aliases in list(default_comorbidities.items())[4:]:
                label = f"{key.upper()} - {', '.join(aliases[:2])}"
                if st.checkbox(label, value=(key == 'fm'), key=f'comorb_{key}'):
                    selected_comorbidities[key] = aliases
        
        # Comorbidades personalizadas
        with st.expander("➕ Adicionar comorbidades personalizadas"):
            custom_comorb_name = st.text_input("Nome da comorbidade:", key='custom_comorb_name')
            custom_comorb_terms = st.text_input(
                "Termos de busca (separados por vírgula):",
                help="Exemplo: asma, bronquite",
                key='custom_comorb_terms'
            )
            if custom_comorb_name and custom_comorb_terms:
                terms_list = [t.strip().lower() for t in custom_comorb_terms.split(',')]
                selected_comorbidities[custom_comorb_name.lower().replace(' ', '_')] = terms_list
                st.success(f"✅ Adicionado: {custom_comorb_name}")
        
        # Configuração de Medicamentos
        st.markdown("💊 3. Medicamentos")
        
        default_medications = {
            # JAK Inibidores
            'tofacitinibe': ['tofacitinibe', 'xeljanz'],
            'upadacitinibe': ['upadacitinibe', 'rinvoq'],
            'baricitinibe': ['baricitinibe', 'olumiant'],
            # Anti-TNF
            'adalimumabe': ['adalimumabe', 'humira'],
            'etanercepte': ['etanercepte', 'enbrel'],
            'golimumabe': ['golimumabe', 'simponi'],
            'infliximabe': ['infliximabe', 'remicade'],
            'certolizumabe': ['certolizumabe', 'cimzia'],
            # Outros biológicos
            'tocilizumabe': ['tocilizumabe', 'actemra'],
            'rituximabe': ['rituximabe', 'mabthera'],
            'abatacepte': ['abatacepte', 'orencia'],
            # DMARDs convencionais
            'metotrexato': ['metotrexato', 'mtx'],
            'leflunomida': ['leflunomida'],
            'sulfassalazina': ['sulfassalazina']
        }
        
        st.markdown("Selecione os medicamentos a identificar:")
        
        # Organizar por categoria
        col1, col2, col3 = st.columns(3)
        
        selected_medications = {}
        
        with col1:
            st.markdown("**JAK Inibidores**")
            for key in ['tofacitinibe', 'upadacitinibe', 'baricitinibe']:
                aliases = default_medications[key]
                if st.checkbox(
                    f"{key.title()}", 
                    value=(key in ['tofacitinibe', 'upadacitinibe']),
                    key=f'med_{key}'
                ):
                    selected_medications[key] = aliases
        
        with col2:
            st.markdown("**Anti-TNF**")
            for key in ['adalimumabe', 'etanercepte', 'golimumabe', 'infliximabe', 'certolizumabe']:
                aliases = default_medications[key]
                if st.checkbox(
                    f"{key.title()}", 
                    value=(key in ['adalimumabe', 'etanercepte']),
                    key=f'med_{key}'
                ):
                    selected_medications[key] = aliases
        
        with col3:
            st.markdown("**Outros**")
            for key in ['tocilizumabe', 'rituximabe', 'abatacepte', 'metotrexato']:
                aliases = default_medications[key]
                if st.checkbox(f"{key.title()}", value=False, key=f'med_{key}'):
                    selected_medications[key] = aliases
        
        # Medicamentos personalizados
        with st.expander("➕ Adicionar medicamentos personalizados"):
            custom_med_name = st.text_input("Nome do medicamento:", key='custom_med_name')
            custom_med_terms = st.text_input(
                "Termos de busca (separados por vírgula):",
                help="Exemplo: azatioprina, imuran",
                key='custom_med_terms'
            )
            if custom_med_name and custom_med_terms:
                terms_list = [t.strip().lower() for t in custom_med_terms.split(',')]
                selected_medications[custom_med_name.lower().replace(' ', '_')] = terms_list
                st.success(f"✅ Adicionado: {custom_med_name}")
        
        # Configuração de Critérios de Melhora
        st.markdown("🎯 4. Critérios de Melhora")
        
        st.markdown("Configure os critérios para definir melhora clínica:")
        
        improvement_criteria = {}
        
        if 'haq' in selected_markers:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown("**HAQ** - Redução mínima para considerar melhora:")
            with col2:
                haq_threshold = st.number_input(
                    "Redução", 
                    min_value=0.0, 
                    max_value=3.0, 
                    value=0.35, 
                    step=0.05,
                    key='haq_threshold',
                    label_visibility='collapsed'
                )
            improvement_criteria['haq'] = lambda v0, v1: v1 <= v0 - haq_threshold
        
        if 'das28' in selected_markers:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown("**DAS28** - Percentual mínimo de redução:")
            with col2:
                das28_pct = st.number_input(
                    "% Redução", 
                    min_value=0, 
                    max_value=100, 
                    value=50,
                    step=5,
                    key='das28_pct',
                    label_visibility='collapsed'
                )
            improvement_criteria['das28'] = lambda v0, v1: v1 <= v0 * (1 - das28_pct/100)
        
        if 'cdai' in selected_markers:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown("**CDAI** - Redução mínima para considerar melhora:")
            with col2:
                cdai_threshold = st.number_input(
                    "Redução", 
                    min_value=0.0, 
                    max_value=50.0, 
                    value=10.0,
                    step=1.0,
                    key='cdai_threshold',
                    label_visibility='collapsed'
                )
            improvement_criteria['cdai'] = lambda v0, v1: v1 <= v0 - cdai_threshold
        
        # Tempo mínimo de tratamento
        st.markdown("⏱️ 5. Tempo Mínimo de Tratamento")
        min_treatment_days = st.slider(
            "Dias mínimos entre baseline e follow-up:",
            min_value=0,
            max_value=365,
            value=60,
            step=10,
            help="Pacientes com menos dias de tratamento serão excluídos da análise de eficácia"
        )
        
        # Botão de processamento
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            process_button = st.button(
                "🚀 Processar Dados (ETL)",
                type="primary",
                use_container_width=True
            )
        
        # =============================================================================
        # PROCESSAMENTO ETL
        # =============================================================================
        
        if process_button:
            with st.spinner("⚙️ Processando dados..."):
                
                try:
                    # Criar cópia para processamento
                    df_processed = df.copy()
                    
                    # Remover duplicatas
                    initial_len = len(df_processed)
                    df_processed = df_processed.drop_duplicates(
                        subset=['descricao']
                    ).reset_index(drop=True)
                    st.info(f"🗑️ Removidas {initial_len - len(df_processed)} duplicatas")
                    
                    # ETAPA 1: Extrair marcadores clínicos
                    if selected_markers:
                        st.info("📊 Extraindo marcadores clínicos...")
                        df_processed = extract_generic(
                            df_processed, 
                            selected_markers,
                            'descricao'
                        )
                    
                    # ETAPA 2: Extrair comorbidades
                    if selected_comorbidities:
                        st.info("🏥 Identificando comorbidades...")
                        df_processed = extract_binary_flags(
                            df_processed,
                            selected_comorbidities,
                            'descricao'
                        )
                        # Criar flag geral de comorbidade
                        comorbidity_cols = list(selected_comorbidities.keys())
                        df_processed['comorbidade_qualquer'] = (
                            df_processed[comorbidity_cols].sum(axis=1) > 0
                        ).astype(int)
                    
                    # ETAPA 3: Extrair medicamentos
                    if selected_medications:
                        st.info("💊 Identificando medicamentos...")
                        df_processed = extract_binary_flags(
                            df_processed,
                            selected_medications,
                            'descricao'
                        )
                    
                    # ETAPA 4: Limpeza de dados numéricos
                    st.info("🧹 Limpando dados numéricos...")
                    numeric_cols = list(selected_markers.keys())
                    df_processed = clean_numeric_columns(df_processed, numeric_cols)
                    
                    # ETAPA 5: Filtrar pacientes válidos
                    st.info("🔍 Filtrando pacientes válidos...")
                    tipo_counts = df_processed.groupby('paciente')['tipo'].nunique()
                    valid_patients = tipo_counts[tipo_counts >= 2].index
                    df_processed = df_processed[
                        df_processed['paciente'].isin(valid_patients)
                    ].reset_index(drop=True)
                    
                    st.success(f"✅ {len(valid_patients)} pacientes válidos (com múltiplas consultas)")
                    
                    # ETAPA 6: Criar base longitudinal
                    st.info("📈 Criando base longitudinal...")
                    
                    # Identificar tipos de baseline e follow-up
                    tipos_disponiveis = df_processed['tipo'].unique()
                    
                    if len(tipos_disponiveis) < 2:
                        st.error("❌ É necessário pelo menos 2 tipos de registro diferentes")
                        return
                    
                    # Usar ANAMNESE como baseline e EVOLUCAO como follow-up
                    baseline_type = 'ANAMNESE' if 'ANAMNESE' in tipos_disponiveis else tipos_disponiveis[0]
                    followup_type = 'EVOLUCAO' if 'EVOLUCAO' in tipos_disponiveis else tipos_disponiveis[1]
                    
                    st.info(f"📌 Baseline: {baseline_type} | Follow-up: {followup_type}")
                    
                    df_longitudinal = create_longitudinal_data(
                        df_processed,
                        baseline_type,
                        followup_type,
                        list(selected_markers.keys())
                    )
                    
                    # ETAPA 7: Calcular melhora
                    if improvement_criteria:
                        st.info("🎯 Calculando melhora clínica...")
                        df_longitudinal = calculate_improvement(
                            df_longitudinal,
                            improvement_criteria
                        )
                    
                    # ETAPA 8: Filtrar por tempo mínimo
                    if min_treatment_days > 0:
                        st.info(f"⏱️ Filtrando tratamentos com mínimo de {min_treatment_days} dias...")
                        before_filter = len(df_longitudinal)
                        df_longitudinal = df_longitudinal[
                            df_longitudinal['tempo_tratamento_dias'] >= min_treatment_days
                        ].reset_index(drop=True)
                        st.info(f"📊 Removidos {before_filter - len(df_longitudinal)} pacientes")
                    
                    # Salvar no session_state
                    st.session_state['df_processed'] = df_processed
                    st.session_state['df_longitudinal'] = df_longitudinal
                    st.session_state['selected_markers'] = selected_markers
                    st.session_state['selected_comorbidities'] = selected_comorbidities
                    st.session_state['selected_medications'] = selected_medications
                    
                    st.success("✅ Processamento concluído com sucesso!")
                    
                    # Resumo
                    st.markdown("### 📋 Resumo do Processamento")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Pacientes Finais", len(df_longitudinal))
                    
                    with col2:
                        if 'improvement' in df_longitudinal.columns:
                            improved = df_longitudinal['improvement'].sum()
                            st.metric("Pacientes que Melhoraram", improved)
                    
                    with col3:
                        if 'improvement' in df_longitudinal.columns:
                            pct = (improved / len(df_longitudinal) * 100) if len(df_longitudinal) > 0 else 0
                            st.metric("% de Melhora", f"{pct:.1f}%")
                
                except Exception as e:
                    st.error(f"❌ Erro durante o processamento: {str(e)}")
                    st.exception(e)
    
    # =============================================================================
    # TAB 3: ANÁLISE EXPLORATÓRIA
    # =============================================================================
    
    with tab3:
        st.subheader("📈 Análise Exploratória dos Dados")
        
        if 'df_processed' not in st.session_state:
            st.warning("⚠️ Execute o processamento ETL primeiro (Tab: Configurar ETL)")
            return
        
        df_analysis = st.session_state['df_processed']
        
        # Subtabs para diferentes análises
        subtab1, subtab2, subtab3, subtab4 = st.tabs([
            "👥 Demografia",
            "📊 Marcadores",
            "🏥 Comorbidades",
            "💊 Medicamentos"
        ])
        
        # --- SUBTAB 1: Demografia ---
        with subtab1:
            st.markdown("👥 Análise Demográfica")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Distribuição de idades
                if 'idade' in df_analysis.columns:
                    st.markdown("**Distribuição de Idades**")
                    
                    fig = px.histogram(
                        df_analysis,
                        x='idade',
                        nbins=30,
                        title="Frequência por Idade",
                        labels={'idade': 'Idade', 'count': 'Frequência'},
                        color_discrete_sequence=['#1f77b4']
                    )
                    fig.update_layout(showlegend=False, height=400)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Estatísticas
                    st.markdown("**Estatísticas de Idade:**")
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Média", f"{df_analysis['idade'].mean():.1f}")
                    col_b.metric("Mediana", f"{df_analysis['idade'].median():.0f}")
                    col_c.metric("Desvio Padrão", f"{df_analysis['idade'].std():.1f}")
            
            with col2:
                # Distribuição por sexo
                if 'sexo' in df_analysis.columns:
                    st.markdown("**Distribuição por Sexo**")
                    
                    sexo_counts = df_analysis['sexo'].value_counts()
                    
                    fig = go.Figure(data=[
                        go.Pie(
                            labels=sexo_counts.index,
                            values=sexo_counts.values,
                            marker=dict(colors=['#ff9999', '#66b3ff']),
                            textinfo='label+percent+value'
                        )
                    ])
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Estatísticas
                    st.markdown("**Proporção:**")
                    if 'F' in sexo_counts and 'M' in sexo_counts:
                        ratio = sexo_counts['F'] / sexo_counts['M']
                        st.info(f"Proporção F:M = {ratio:.2f}:1")
            
            # Distribuição por idade e sexo
            if 'idade' in df_analysis.columns and 'sexo' in df_analysis.columns:
                st.markdown("**Distribuição de Idade por Sexo**")
                
                fig = px.histogram(
                    df_analysis,
                    x='idade',
                    color='sexo',
                    nbins=25,
                    title="Frequência de Idades por Sexo",
                    labels={'idade': 'Idade', 'count': 'Frequência'},
                    barmode='stack',
                    color_discrete_map={'F': '#ff9999', 'M': '#66b3ff'}
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
        
        # --- SUBTAB 2: Marcadores ---
        with subtab2:
            st.markdown("📊 Análise de Marcadores Clínicos")
            
            if 'selected_markers' not in st.session_state:
                st.info("Nenhum marcador configurado")
                return
            
            markers = list(st.session_state['selected_markers'].keys())
            available_markers = [m for m in markers if m in df_analysis.columns]
            
            if not available_markers:
                st.warning("Nenhum marcador foi extraído dos dados")
                return
            
            # Seletor de marcador
            selected_marker = st.selectbox(
                "Selecione o marcador para análise:",
                available_markers,
                format_func=lambda x: x.upper()
            )
            
            marker_data = df_analysis[selected_marker].dropna()
            
            if len(marker_data) == 0:
                st.warning(f"Nenhum dado disponível para {selected_marker.upper()}")
                return
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Histograma
                fig = px.histogram(
                    marker_data,
                    nbins=30,
                    title=f"Distribuição de {selected_marker.upper()}",
                    labels={'value': selected_marker.upper(), 'count': 'Frequência'},
                    color_discrete_sequence=['#2ca02c']
                )
                fig.update_layout(showlegend=False, height=350)
                st.plotly_chart(fig, use_container_width=True)
                
                # Estatísticas descritivas
                st.markdown("**Estatísticas Descritivas:**")
                stats_df = pd.DataFrame({
                    'Métrica': ['Média', 'Mediana', 'Desvio Padrão', 'Mínimo', 'Máximo', 'Q25', 'Q75'],
                    'Valor': [
                        f"{marker_data.mean():.2f}",
                        f"{marker_data.median():.2f}",
                        f"{marker_data.std():.2f}",
                        f"{marker_data.min():.2f}",
                        f"{marker_data.max():.2f}",
                        f"{marker_data.quantile(0.25):.2f}",
                        f"{marker_data.quantile(0.75):.2f}"
                    ]
                })
                st.dataframe(stats_df, use_container_width=True, hide_index=True)
            
            with col2:
                # Box plot
                fig = px.box(
                    marker_data,
                    y=marker_data.values,
                    title=f"Box Plot - {selected_marker.upper()}",
                    labels={'y': selected_marker.upper()},
                    color_discrete_sequence=['#2ca02c']
                )
                fig.update_layout(showlegend=False, height=350)
                st.plotly_chart(fig, use_container_width=True)
                
                # Valores ausentes
                total_records = len(df_analysis)
                available = len(marker_data)
                missing = total_records - available
                missing_pct = (missing / total_records * 100)
                
                st.markdown("**Completude dos Dados:**")
                st.metric("Registros Disponíveis", f"{available} / {total_records}")
                st.metric("% Ausente", f"{missing_pct:.1f}%")
            
            # Comparação com outros marcadores
            if len(available_markers) > 1:
                st.markdown("---")
                st.markdown("**Matriz de Correlação dos Marcadores**")
                
                # Criar dataframe apenas com marcadores
                markers_df = df_analysis[available_markers].apply(pd.to_numeric, errors='coerce')
                
                # Calcular correlação
                corr_matrix = markers_df.corr()
                
                # Heatmap
                fig = px.imshow(
                    corr_matrix,
                    labels=dict(color="Correlação"),
                    x=[m.upper() for m in corr_matrix.columns],
                    y=[m.upper() for m in corr_matrix.index],
                    color_continuous_scale='RdBu_r',
                    aspect='auto',
                    zmin=-1,
                    zmax=1
                )
                fig.update_layout(height=500)
                st.plotly_chart(fig, use_container_width=True)
        
        # --- SUBTAB 3: Comorbidades ---
        with subtab3:
            st.markdown("🏥 Análise de Comorbidades")
            
            if 'selected_comorbidities' not in st.session_state:
                st.info("Nenhuma comorbidade configurada")
                return
            
            comorb_cols = list(st.session_state['selected_comorbidities'].keys())
            available_comorb = [c for c in comorb_cols if c in df_analysis.columns]
            
            if not available_comorb:
                st.warning("Nenhuma comorbidade foi identificada nos dados")
                return
            
            # Calcular frequências por paciente único
            comorb_by_patient = df_analysis.groupby('paciente')[available_comorb].max()
            comorb_counts_unique = {}
            for comorb in available_comorb:
                comorb_counts_unique[comorb.upper()] = int(comorb_by_patient[comorb].sum())
            
            # Gráfico de barras
            fig = px.bar(
                x=list(comorb_counts_unique.keys()),
                y=list(comorb_counts_unique.values()),
                title="Frequência de Comorbidades",
                labels={'x': 'Comorbidade', 'y': 'Número de Pacientes'},
                color=list(comorb_counts_unique.values()),
                color_continuous_scale='Reds'
            )
            fig.update_layout(showlegend=False, height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            # Tabela de frequências
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Frequência Absoluta:**")
                freq_df = pd.DataFrame({
                    'Comorbidade': list(comorb_counts_unique.keys()),
                    'Pacientes': list(comorb_counts_unique.values())
                }).sort_values('Pacientes', ascending=False)
                st.dataframe(freq_df, use_container_width=True, hide_index=True)
            
            with col2:
                st.markdown("**Frequência Relativa:**")
                total_patients_unique = df_analysis['paciente'].nunique()
                freq_df['%'] = (freq_df['Pacientes'] / total_patients_unique * 100).round(2)
                st.dataframe(
                    freq_df[['Comorbidade', '%']],
                    use_container_width=True,
                    hide_index=True
                )
            
            # Comorbidades múltiplas
            if 'comorbidade_qualquer' in df_analysis.columns:
                st.markdown("---")
                st.markdown("**Análise de Comorbidades Múltiplas**")
                
                # CORREÇÃO: Agrupar por paciente primeiro
                comorb_by_patient = df_analysis.groupby('paciente')[available_comorb].max()
                comorb_by_patient['num_comorbidades'] = comorb_by_patient.sum(axis=1)
                
                comorb_dist = comorb_by_patient['num_comorbidades'].value_counts().sort_index()
                
                fig = px.bar(
                    x=comorb_dist.index,
                    y=comorb_dist.values,
                    title="Distribuição de Número de Comorbidades por Paciente",
                    labels={'x': 'Número de Comorbidades', 'y': 'Número de Pacientes'},
                    color=comorb_dist.values,
                    color_continuous_scale='Oranges'
                )
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
        
        # --- SUBTAB 4: Medicamentos ---
        with subtab4:
            st.markdown("💊 Análise de Medicamentos")
            
            if 'selected_medications' not in st.session_state:
                st.info("Nenhum medicamento configurado")
                return
            
            med_cols = list(st.session_state['selected_medications'].keys())
            available_meds = [m for m in med_cols if m in df_analysis.columns]
            
            if not available_meds:
                st.warning("Nenhum medicamento foi identificado nos dados")
                return
            
            # Calcular frequências
            med_counts = {}
            for med in available_meds:
                med_counts[med.title()] = df_analysis[med].sum()
            
            # Ordenar por frequência
            med_counts_sorted = dict(sorted(
                med_counts.items(),
                key=lambda x: x[1],
                reverse=True
            ))
            
            # Gráfico de barras horizontal
            fig = px.bar(
                x=list(med_counts_sorted.values()),
                y=list(med_counts_sorted.keys()),
                orientation='h',
                title="Frequência de Uso de Medicamentos",
                labels={'x': 'Número de Pacientes', 'y': 'Medicamento'},
                color=list(med_counts_sorted.values()),
                color_continuous_scale='Greens'
            )
            fig.update_layout(showlegend=False, height=max(400, len(med_counts_sorted) * 30))
            st.plotly_chart(fig, use_container_width=True)
            
            # Estatísticas
            col1, col2, col3 = st.columns(3)
            
            with col1:
                total_prescriptions = sum(med_counts.values())
                st.metric("Total de Prescrições", total_prescriptions)
            
            with col2:
                # CORREÇÃO: Usar base correta para contagem
                total_patients_unique = df_analysis['paciente'].nunique()
                patients_with_meds = (df_analysis.groupby('paciente')[available_meds].max().sum(axis=1) > 0).sum()
                st.metric("Pacientes com Medicação", patients_with_meds)
            
            with col3:
                pct_with_meds = (patients_with_meds / total_patients_unique * 100)
                st.metric("% com Medicação", f"{pct_with_meds:.1f}%")
            
            # Tabela detalhada
            st.markdown("---")
            st.markdown("**Detalhamento por Medicamento:**")
            
            # CORREÇÃO: Calcular corretamente por paciente único
            med_by_patient = df_analysis.groupby('paciente')[available_meds].max()
            med_counts_unique = med_by_patient.sum().to_dict()
            med_counts_unique_sorted = {
                med.title(): int(med_counts_unique[med]) 
                for med in available_meds
            }
            med_counts_unique_sorted = dict(sorted(
                med_counts_unique_sorted.items(),
                key=lambda x: x[1],
                reverse=True
            ))
            
            med_detail_df = pd.DataFrame({
                'Medicamento': list(med_counts_unique_sorted.keys()),
                'Pacientes': list(med_counts_unique_sorted.values()),
                '% do Total': [
                    f"{(v / total_patients_unique * 100):.2f}%"
                    for v in med_counts_unique_sorted.values()
                ]
            })
            st.dataframe(med_detail_df, use_container_width=True, hide_index=True)
            
            # Combinações de medicamentos
            st.markdown("---")
            st.markdown("**Análise de Politerapia**")
            
            # CORREÇÃO: Agrupar por paciente primeiro
            politerapia_by_patient = df_analysis.groupby('paciente')[available_meds].max()
            politerapia_by_patient['num_medicamentos'] = politerapia_by_patient.sum(axis=1)
            
            politerapia_counts = politerapia_by_patient['num_medicamentos'].value_counts().sort_index()
            
            fig = px.bar(
                x=politerapia_counts.index,
                y=politerapia_counts.values,
                title="Distribuição de Número de Medicamentos por Paciente",
                labels={'x': 'Número de Medicamentos', 'y': 'Número de Pacientes'},
                color=politerapia_counts.values,
                color_continuous_scale='Purples'
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
            # Estatísticas de politerapia
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Média de Medicamentos", f"{politerapia_by_patient['num_medicamentos'].mean():.2f}")
            
            with col2:
                st.metric("Mediana", f"{politerapia_by_patient['num_medicamentos'].median():.0f}")
            
            with col3:
                monoterapia = (politerapia_by_patient['num_medicamentos'] == 1).sum()
                st.metric("Pacientes em Monoterapia", monoterapia)
    
    # =============================================================================
    # TAB 4: ANÁLISE DE EFICÁCIA
    # =============================================================================
    
    with tab4:
        st.subheader("🎯 Análise de Eficácia Terapêutica")
        
        if 'df_longitudinal' not in st.session_state:
            st.warning("⚠️ Execute o processamento ETL primeiro (Tab: Configurar ETL)")
            return
        
        df_long = st.session_state['df_longitudinal']
        
        if 'improvement' not in df_long.columns:
            st.warning("⚠️ Nenhum critério de melhora foi configurado")
            return
        
        # Métricas gerais
        st.markdown("📊 Visão Geral da Eficácia")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total de Pacientes", len(df_long))
        
        with col2:
            improved = df_long['improvement'].sum()
            st.metric("Melhoraram", improved)
        
        with col3:
            not_improved = len(df_long) - improved
            st.metric("Não Melhoraram", not_improved)
        
        with col4:
            pct_improved = (improved / len(df_long) * 100) if len(df_long) > 0 else 0
            st.metric("Taxa de Resposta", f"{pct_improved:.1f}%")
        
        # Gráfico pizza - Distribuição de melhora
        col1, col2 = st.columns(2)
        
        with col1:
            fig = go.Figure(data=[
                go.Pie(
                    labels=['Com Melhora', 'Sem Melhora'],
                    values=[improved, not_improved],
                    marker=dict(colors=['#66b3ff', '#ff9999']),
                    textinfo='label+percent+value',
                    hole=0.3
                )
            ])
            fig.update_layout(
                title="Distribuição de Resposta ao Tratamento",
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Tempo de tratamento
            if 'tempo_tratamento_dias' in df_long.columns:
                fig = px.histogram(
                    df_long,
                    x='tempo_tratamento_dias',
                    color='improvement',
                    nbins=30,
                    title="Distribuição do Tempo de Tratamento",
                    labels={
                        'tempo_tratamento_dias': 'Dias de Tratamento',
                        'improvement': 'Melhorou'
                    },
                    color_discrete_map={0: '#ff9999', 1: '#66b3ff'},
                    barmode='overlay'
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
        
        # Análise por marcadores
        st.markdown("---")
        st.markdown("📈 Evolução dos Marcadores Clínicos")
        
        if 'selected_markers' in st.session_state:
            markers = list(st.session_state['selected_markers'].keys())
            
            # Identificar marcadores com dados t0 e t1
            available_markers_t0t1 = []
            for marker in markers:
                if f'{marker}_t0' in df_long.columns and f'{marker}_t1' in df_long.columns:
                    if df_long[f'{marker}_t0'].notna().any() and df_long[f'{marker}_t1'].notna().any():
                        available_markers_t0t1.append(marker)
            
            if available_markers_t0t1:
                selected_marker_evo = st.selectbox(
                    "Selecione o marcador para análise de evolução:",
                    available_markers_t0t1,
                    format_func=lambda x: x.upper()
                )
                
                col_t0 = f'{selected_marker_evo}_t0'
                col_t1 = f'{selected_marker_evo}_t1'
                
                # Filtrar dados válidos
                df_marker = df_long[[col_t0, col_t1, 'improvement']].dropna()
                
                if len(df_marker) > 0:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Box plot comparando t0 e t1
                        df_marker_melt = pd.melt(
                            df_marker,
                            id_vars=['improvement'],
                            value_vars=[col_t0, col_t1],
                            var_name='Tempo',
                            value_name='Valor'
                        )
                        df_marker_melt['Tempo'] = df_marker_melt['Tempo'].map({
                            col_t0: 'Baseline (t0)',
                            col_t1: 'Follow-up (t1)'
                        })
                        
                        fig = px.box(
                            df_marker_melt,
                            x='Tempo',
                            y='Valor',
                            color='improvement',
                            title=f"Comparação {selected_marker_evo.upper()} - t0 vs t1",
                            labels={'Valor': selected_marker_evo.upper(), 'improvement': 'Melhorou'},
                            color_discrete_map={0: '#ff9999', 1: '#66b3ff'}
                        )
                        fig.update_layout(height=400)
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        # Scatter plot - mudança individual
                        df_marker['mudanca'] = df_marker[col_t1] - df_marker[col_t0]
                        
                        fig = px.scatter(
                            df_marker,
                            x=col_t0,
                            y=col_t1,
                            color='improvement',
                            title=f"Evolução Individual - {selected_marker_evo.upper()}",
                            labels={
                                col_t0: f'{selected_marker_evo.upper()} Baseline',
                                col_t1: f'{selected_marker_evo.upper()} Follow-up',
                                'improvement': 'Melhorou'
                            },
                            color_discrete_map={0: '#ff9999', 1: '#66b3ff'},
                            hover_data=['mudanca']
                        )
                        
                        # Adicionar linha de referência (sem mudança)
                        max_val = max(df_marker[col_t0].max(), df_marker[col_t1].max())
                        min_val = min(df_marker[col_t0].min(), df_marker[col_t1].min())
                        fig.add_shape(
                            type='line',
                            x0=min_val, y0=min_val,
                            x1=max_val, y1=max_val,
                            line=dict(color='gray', dash='dash')
                        )
                        
                        fig.update_layout(height=400)
                        st.plotly_chart(fig, use_container_width=True)
                    
                    # Estatísticas de mudança
                    st.markdown("**Estatísticas de Mudança:**")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    improved_data = df_marker[df_marker['improvement'] == 1]
                    not_improved_data = df_marker[df_marker['improvement'] == 0]
                    
                    with col1:
                        st.markdown("**Todos os Pacientes**")
                        st.metric("Mudança Média", f"{df_marker['mudanca'].mean():.2f}")
                        st.metric("Mudança Mediana", f"{df_marker['mudanca'].median():.2f}")
                    
                    with col2:
                        st.markdown("**Pacientes que Melhoraram**")
                        if len(improved_data) > 0:
                            st.metric("Mudança Média", f"{improved_data['mudanca'].mean():.2f}")
                            st.metric("Mudança Mediana", f"{improved_data['mudanca'].median():.2f}")
                        else:
                            st.info("Sem dados")
                    
                    with col3:
                        st.markdown("**Pacientes que NÃO Melhoraram**")
                        if len(not_improved_data) > 0:
                            st.metric("Mudança Média", f"{not_improved_data['mudanca'].mean():.2f}")
                            st.metric("Mudança Mediana", f"{not_improved_data['mudanca'].median():.2f}")
                        else:
                            st.info("Sem dados")
            else:
                st.info("Nenhum marcador com dados longitudinais disponível")
        
        # Análise por subgrupos
        st.markdown("---")
        st.markdown("👥 Análise por Subgrupos")
        
        tab_sex, tab_age, tab_comorb, tab_meds = st.tabs([
            "Por Sexo",
            "Por Faixa Etária",
            "Por Comorbidades",
            "Por Medicamentos"
        ])
        
        with tab_sex:
            if 'sexo' in df_long.columns:
                # Taxa de resposta por sexo
                response_by_sex = df_long.groupby('sexo')['improvement'].agg(['sum', 'count'])
                response_by_sex['taxa'] = (response_by_sex['sum'] / response_by_sex['count'] * 100)
                
                fig = px.bar(
                    x=response_by_sex.index,
                    y=response_by_sex['taxa'],
                    title="Taxa de Resposta por Sexo",
                    labels={'x': 'Sexo', 'y': 'Taxa de Resposta (%)'},
                    color=response_by_sex['taxa'],
                    color_continuous_scale='Blues',
                    text=response_by_sex['taxa'].round(1)
                )
                fig.update_traces(texttemplate='%{text}%', textposition='outside')
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
                
                # Tabela detalhada
                st.dataframe(
                    response_by_sex.rename(columns={
                        'sum': 'Melhoraram',
                        'count': 'Total',
                        'taxa': 'Taxa (%)'
                    }).round(2),
                    use_container_width=True
                )
            else:
                st.info("Dados de sexo não disponíveis")
        
        with tab_age:
            if 'idade' in df_long.columns:
                # Criar faixas etárias
                df_long['faixa_etaria'] = pd.cut(
                    df_long['idade'],
                    bins=[0, 30, 40, 50, 60, 70, 120],
                    labels=['<30', '30-40', '40-50', '50-60', '60-70', '>70']
                )
                
                response_by_age = df_long.groupby('faixa_etaria')['improvement'].agg(['sum', 'count'])
                response_by_age['taxa'] = (response_by_age['sum'] / response_by_age['count'] * 100)
                
                fig = px.bar(
                    x=response_by_age.index.astype(str),
                    y=response_by_age['taxa'],
                    title="Taxa de Resposta por Faixa Etária",
                    labels={'x': 'Faixa Etária', 'y': 'Taxa de Resposta (%)'},
                    color=response_by_age['taxa'],
                    color_continuous_scale='Greens',
                    text=response_by_age['taxa'].round(1)
                )
                fig.update_traces(texttemplate='%{text}%', textposition='outside')
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
                
                # Tabela detalhada
                st.dataframe(
                    response_by_age.rename(columns={
                        'sum': 'Melhoraram',
                        'count': 'Total',
                        'taxa': 'Taxa (%)'
                    }).round(2),
                    use_container_width=True
                )
            else:
                st.info("Dados de idade não disponíveis")
        
        with tab_comorb:
            if 'comorbidade_qualquer' in df_long.columns:
                df_long['tem_comorbidade'] = df_long['comorbidade_qualquer'].map({
                    0: 'Sem Comorbidades',
                    1: 'Com Comorbidades'
                })
                
                response_by_comorb = df_long.groupby('tem_comorbidade')['improvement'].agg(['sum', 'count'])
                response_by_comorb['taxa'] = (response_by_comorb['sum'] / response_by_comorb['count'] * 100)
                
                fig = px.bar(
                    x=response_by_comorb.index,
                    y=response_by_comorb['taxa'],
                    title="Taxa de Resposta - Presença de Comorbidades",
                    labels={'x': 'Grupo', 'y': 'Taxa de Resposta (%)'},
                    color=response_by_comorb['taxa'],
                    color_continuous_scale='Reds',
                    text=response_by_comorb['taxa'].round(1)
                )
                fig.update_traces(texttemplate='%{text}%', textposition='outside')
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
                
                # Tabela detalhada
                st.dataframe(
                    response_by_comorb.rename(columns={
                        'sum': 'Melhoraram',
                        'count': 'Total',
                        'taxa': 'Taxa (%)'
                    }).round(2),
                    use_container_width=True
                )
                
                # Análise por comorbidade específica
                if 'selected_comorbidities' in st.session_state:
                    st.markdown("---")
                    st.markdown("**Taxa de Resposta por Comorbidade Específica:**")
                    
                    comorb_cols = list(st.session_state['selected_comorbidities'].keys())
                    available_comorb = [c for c in comorb_cols if c in df_long.columns]
                    
                    if available_comorb:
                        comorb_response = {}
                        
                        for comorb in available_comorb:
                            df_with_comorb = df_long[df_long[comorb] == 1]
                            if len(df_with_comorb) > 0:
                                response_rate = (df_with_comorb['improvement'].sum() / len(df_with_comorb) * 100)
                                comorb_response[comorb.upper()] = {
                                    'Total': len(df_with_comorb),
                                    'Melhoraram': df_with_comorb['improvement'].sum(),
                                    'Taxa (%)': round(response_rate, 2)
                                }
                        
                        if comorb_response:
                            comorb_df = pd.DataFrame(comorb_response).T
                            st.dataframe(comorb_df, use_container_width=True)
            else:
                st.info("Dados de comorbidades não disponíveis")
        
        with tab_meds:
            if 'selected_medications' in st.session_state:
                med_cols = list(st.session_state['selected_medications'].keys())
                available_meds = [m for m in med_cols if m in df_long.columns]
                
                if available_meds:
                    st.markdown("**Taxa de Resposta por Medicamento:**")
                    
                    med_response = {}
                    
                    for med in available_meds:
                        df_with_med = df_long[df_long[med] == 1]
                        if len(df_with_med) > 5:  # Mínimo de pacientes para análise
                            response_rate = (df_with_med['improvement'].sum() / len(df_with_med) * 100)
                            med_response[med.title()] = {
                                'Total': len(df_with_med),
                                'Melhoraram': df_with_med['improvement'].sum(),
                                'Taxa (%)': round(response_rate, 2)
                            }
                    
                    if med_response:
                        med_df = pd.DataFrame(med_response).T.sort_values('Taxa (%)', ascending=False)
                        
                        # Gráfico
                        fig = px.bar(
                            x=med_df.index,
                            y=med_df['Taxa (%)'],
                            title="Taxa de Resposta por Medicamento",
                            labels={'x': 'Medicamento', 'y': 'Taxa de Resposta (%)'},
                            color=med_df['Taxa (%)'],
                            color_continuous_scale='Purples',
                            text=med_df['Taxa (%)'].round(1)
                        )
                        fig.update_traces(texttemplate='%{text}%', textposition='outside')
                        fig.update_layout(showlegend=False, height=400)
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Tabela
                        st.dataframe(med_df, use_container_width=True)
                    else:
                        st.info("Número insuficiente de pacientes por medicamento para análise")
                else:
                    st.info("Nenhum medicamento foi identificado nos dados")
            else:
                st.info("Nenhum medicamento configurado")
    
    # =============================================================================
    # TAB 5: EXPORTAR DADOS
    # =============================================================================
    
    with tab5:
        st.subheader("💾 Exportar Dados Processados")
        
        if 'df_processed' not in st.session_state or 'df_longitudinal' not in st.session_state:
            st.warning("⚠️ Execute o processamento ETL primeiro (Tab: Configurar ETL)")
            return
        
        st.markdown("### Escolha o dataset para exportar:")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("📊 Dados Processados (Todos os Registros)")
            st.info(f"Total de registros: {len(st.session_state['df_processed'])}")
            
            # Criar Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                st.session_state['df_processed'].to_excel(writer, index=False, sheet_name='Dados')
            
            st.download_button(
                label="📥 Download Excel - Dados Processados",
                data=output.getvalue(),
                file_name=f"prontuarios_processados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            
            # CSV
            csv = st.session_state['df_processed'].to_csv(index=False)
            st.download_button(
                label="📥 Download CSV - Dados Processados",
                data=csv,
                file_name=f"prontuarios_processados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col2:
            st.markdown("📈 Dados Longitudinais (t0 e t1)")
            st.info(f"Total de pacientes: {len(st.session_state['df_longitudinal'])}")
            
            # Criar Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                st.session_state['df_longitudinal'].to_excel(writer, index=False, sheet_name='Longitudinal')
            
            st.download_button(
                label="📥 Download Excel - Dados Longitudinais",
                data=output.getvalue(),
                file_name=f"prontuarios_longitudinal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            
            # CSV
            csv = st.session_state['df_longitudinal'].to_csv(index=False)
            st.download_button(
                label="📥 Download CSV - Dados Longitudinais",
                data=csv,
                file_name=f"prontuarios_longitudinal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        # Preview dos dados
        st.markdown("---")
        st.markdown("Preview dos Dados")
        
        preview_option = st.radio(
            "Selecione o dataset para visualizar:",
            ["Dados Processados", "Dados Longitudinais"],
            horizontal=True
        )
        
        if preview_option == "Dados Processados":
            st.dataframe(st.session_state['df_processed'], use_container_width=True)
        else:
            st.dataframe(st.session_state['df_longitudinal'], use_container_width=True)
        
        # Resumo da configuração usada
        st.markdown("---")
        st.markdown("⚙️ Configuração Utilizada")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if 'selected_markers' in st.session_state:
                st.markdown("**Marcadores:**")
                for marker in st.session_state['selected_markers'].keys():
                    st.text(f"• {marker.upper()}")
        
        with col2:
            if 'selected_comorbidities' in st.session_state:
                st.markdown("**Comorbidades:**")
                for comorb in st.session_state['selected_comorbidities'].keys():
                    st.text(f"• {comorb.upper()}")
        
        with col3:
            if 'selected_medications' in st.session_state:
                st.markdown("**Medicamentos:**")
                for med in list(st.session_state['selected_medications'].keys())[:10]:
                    st.text(f"• {med.title()}")
                if len(st.session_state['selected_medications']) > 10:
                    st.text(f"• ... e mais {len(st.session_state['selected_medications'])-10}")




# =============================================================================

    # Footer IMMUNE
    st.markdown("---")
    st.markdown("""
        <div class="immune-footer">
            <p><strong>Immuned</strong> | Promovendo a saúde com tratamentos inteligentes</p>
            <p style="font-size: 0.85rem; margin-top: 0.5rem;">
                Tecnologia em saúde • Precisão em doenças complexas • Terapia personalizada
            </p>
            <p style="font-size: 0.8rem; color: #d1d5db; margin-top: 1rem;">
                Sistema de Análise de Prontuários v2.0 | © 2025 Immuned
            </p>
        </div>
    """, unsafe_allow_html=True)


# EXECUÇÃO
# =============================================================================

if __name__ == "__main__":
    main()
