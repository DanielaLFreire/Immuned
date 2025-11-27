# -*- coding: utf-8 -*-
"""
IMMUNED - Sistema de Análise de Prontuários Médicos
Versão 3.1 - Completa (v2.0 + novas variáveis v3.0)

Funcionalidades:
- ✅ Configuração interativa via checkboxes
- ✅ Análise Exploratória completa (4 subtabs)
- ✅ Análise por subgrupos na eficácia
- ✅ Novas variáveis (FR, status SIM/PRÉVIO/NÃO, dose MTX, etc.)
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import re
import io
from PIL import Image
import numpy as np

# =============================================================================
# FUNÇÕES DE ANÁLISE DE TROCAS DE MEDICAMENTOS
# =============================================================================

def calcular_taxa_troca_geral(df):
    """Calcula taxa geral de troca de medicamentos"""
    stats = {
        'total_pacientes': len(df),
        'pacientes_sem_biologico': 0,
        'pacientes_primeiro_biologico': 0,
        'pacientes_que_trocaram': 0,
        'taxa_troca_pct': 0.0,
        'num_trocas_media': 0.0,
    }
    
    if 'num_biologicos_previos' in df.columns:
        stats['pacientes_que_trocaram'] = (df['num_biologicos_previos'] > 0).sum()
        stats['pacientes_primeiro_biologico'] = (df['num_biologicos_previos'] == 0).sum()
        
        pacientes_com_bio = (df['uso_biologico'].isin(['SIM', 'PRÉVIO'])).sum()
        if pacientes_com_bio > 0:
            stats['taxa_troca_pct'] = (stats['pacientes_que_trocaram'] / pacientes_com_bio) * 100
        
        stats['num_trocas_media'] = df['num_biologicos_previos'].mean()
    
    return stats


def construir_matriz_transicao(df, medicamentos):
    """Constrói matriz de transição entre medicamentos"""
    matriz = pd.DataFrame(0, 
                         index=[m.title() for m in medicamentos],
                         columns=[m.title() for m in medicamentos])
    
    for idx, row in df.iterrows():
        previos = [m for m in medicamentos 
                   if f'{m}_status' in df.columns 
                   and row.get(f'{m}_status') == 'PRÉVIO']
        
        atual = None
        for m in medicamentos:
            if f'{m}_status' in df.columns and row.get(f'{m}_status') == 'SIM':
                atual = m
                break
        
        if atual:
            for previo in previos:
                matriz.loc[previo.title(), atual.title()] += 1
    
    return matriz


def analisar_motivos_suspensao(df, medicamentos):
    """Analisa motivos de suspensão de medicamentos"""
    motivos_data = []
    
    for med in medicamentos:
        col_status = f'{med}_status'
        col_motivo = f'{med}_motivo'
        
        if col_status in df.columns and col_motivo in df.columns:
            suspenderam = df[df[col_status] == 'PRÉVIO']
            motivos = suspenderam[col_motivo].dropna().value_counts()
            
            for motivo, count in motivos.items():
                motivos_data.append({
                    'Medicamento': med.title(),
                    'Motivo': motivo.title(),
                    'Pacientes': count
                })
    
    if motivos_data:
        return pd.DataFrame(motivos_data)
    else:
        return pd.DataFrame(columns=['Medicamento', 'Motivo', 'Pacientes'])


def calcular_taxa_abandono_por_medicamento(df, medicamentos):
    """Calcula taxa de abandono para cada medicamento"""
    taxas = []
    
    for med in medicamentos:
        col_status = f'{med}_status'
        
        if col_status in df.columns:
            total_usaram = (df[col_status].isin(['SIM', 'PRÉVIO'])).sum()
            suspenderam = (df[col_status] == 'PRÉVIO').sum()
            
            if total_usaram > 0:
                taxa_pct = (suspenderam / total_usaram) * 100
                taxas.append({
                    'Medicamento': med.title(),
                    'Total Usaram': total_usaram,
                    'Suspenderam': suspenderam,
                    'Taxa Abandono (%)': round(taxa_pct, 2)
                })
    
    df_taxas = pd.DataFrame(taxas)
    if not df_taxas.empty:
        df_taxas = df_taxas.sort_values('Taxa Abandono (%)', ascending=False)
    
    return df_taxas


def identificar_sequencias_comuns(df, medicamentos, top_n=10):
    """Identifica as sequências de tratamento mais comuns"""
    sequencias = []
    
    for idx, row in df.iterrows():
        previos = [m.title() for m in medicamentos 
                   if f'{m}_status' in df.columns 
                   and row.get(f'{m}_status') == 'PRÉVIO']
        
        atual = None
        for m in medicamentos:
            if f'{m}_status' in df.columns and row.get(f'{m}_status') == 'SIM':
                atual = m.title()
                break
        
        if previos and atual:
            seq = ' → '.join(previos[:3]) + f' → {atual}'
            sequencias.append(seq)
    
    seq_counts = pd.Series(sequencias).value_counts().head(top_n)
    
    return pd.DataFrame({
        'Sequência': seq_counts.index,
        'Pacientes': seq_counts.values
    })


def analisar_eficacia_pos_troca(df):
    """Analisa eficácia em pacientes que trocaram vs não trocaram"""
    stats = {
        'com_troca': {'total': 0, 'melhoraram': 0, 'taxa_pct': 0.0},
        'sem_troca': {'total': 0, 'melhoraram': 0, 'taxa_pct': 0.0},
    }
    
    if 'improvement' not in df.columns or 'num_biologicos_previos' not in df.columns:
        return stats
    
    com_troca = df[df['num_biologicos_previos'] > 0]
    stats['com_troca']['total'] = len(com_troca)
    stats['com_troca']['melhoraram'] = com_troca['improvement'].sum()
    if len(com_troca) > 0:
        stats['com_troca']['taxa_pct'] = (stats['com_troca']['melhoraram'] / len(com_troca)) * 100
    
    sem_troca = df[(df['num_biologicos_previos'] == 0) & (df['uso_biologico'] == 'SIM')]
    stats['sem_troca']['total'] = len(sem_troca)
    stats['sem_troca']['melhoraram'] = sem_troca['improvement'].sum()
    if len(sem_troca) > 0:
        stats['sem_troca']['taxa_pct'] = (stats['sem_troca']['melhoraram'] / len(sem_troca)) * 100
    
    return stats


# =============================================================================
# CONFIGURAÇÕES E CONSTANTES
# =============================================================================

# Padrões de Fator Reumatoide
FR_POSITIVO_PATTERNS = [
    r'\bfr\s*\+', r'\bfr\s*positivo', r'\bfr\s*reagente', r'\(fr\s*\+\)',
    r'fator\s+reumat[oó]ide\s*(positivo|reagente|\+)', r'soropositiv[ao]',
    r'ar\s*\(?\s*fr\s*\+\s*\)?', r'\bfr\s*[:\s]+\d+[\.,]?\d*\s*\(?positivo\)?',
]

FR_NEGATIVO_PATTERNS = [
    r'\bfr\s*-(?!\d)', r'\bfr\s*negativo', r'\bfr\s*n[aã]o\s*reagente',
    r'\(fr\s*-\)', r'fator\s+reumat[oó]ide\s*(negativo|n[aã]o\s*reagente|-)',
    r'soronegativ[ao]', r'\bfr\s*[:\s]+\d+[\.,]?\d*\s*\(?(neg|negativo)\)?',
]

FR_VALOR_PATTERN = r'\bfr\s*[:\s]+(\d+[\.,]?\d*)'

CID_FR_MAPPING = {
    'M06.0': 'NEGATIVO', 'M05.9': 'POSITIVO', 'M05.0': 'POSITIVO',
    'M05.1': 'POSITIVO', 'M05.2': 'POSITIVO', 'M05.3': 'POSITIVO',
    'M05.8': 'POSITIVO', 'M06.8': 'NÃO INFORMADO', 'M06.9': 'NÃO INFORMADO',
}

CID_PATTERN = r'CID[\s\-]*10?\s*[:\s]*([M]\d{2}\.?\d?)'

# Medicamentos biológicos e JAK
BIOLOGICOS_CONFIG = {
    # JAK Inibidores
    'tofacitinibe': {'aliases': ['tofacitinibe', 'xeljanz', 'tofa'], 'grupo': 'JAK Inibidores'},
    'upadacitinibe': {'aliases': ['upadacitinibe', 'rinvoq', 'upada'], 'grupo': 'JAK Inibidores'},
    'baricitinibe': {'aliases': ['baricitinibe', 'olumiant', 'bari'], 'grupo': 'JAK Inibidores'},
    # Anti-TNF
    'adalimumabe': {'aliases': ['adalimumabe', 'humira', 'ada'], 'grupo': 'Anti-TNF'},
    'etanercepte': {'aliases': ['etanercepte', 'enbrel', 'eta'], 'grupo': 'Anti-TNF'},
    'golimumabe': {'aliases': ['golimumabe', 'simponi', 'goli'], 'grupo': 'Anti-TNF'},
    'infliximabe': {'aliases': ['infliximabe', 'remicade', 'ifx'], 'grupo': 'Anti-TNF'},
    'certolizumabe': {'aliases': ['certolizumabe', 'cimzia', 'czp'], 'grupo': 'Anti-TNF'},
    # Outros biológicos
    'tocilizumabe': {'aliases': ['tocilizumabe', 'actemra', 'tcz'], 'grupo': 'Anti-IL/Outros'},
    'rituximabe': {'aliases': ['rituximabe', 'mabthera', 'rtx'], 'grupo': 'Anti-IL/Outros'},
    'abatacepte': {'aliases': ['abatacepte', 'orencia', 'aba'], 'grupo': 'Anti-IL/Outros'},
    'secuquinumabe': {'aliases': ['secuquinumabe', 'cosentyx'], 'grupo': 'Anti-IL17'},
    'ixequizumabe': {'aliases': ['ixequizumabe', 'taltz'], 'grupo': 'Anti-IL17'},
}

# DMARDs convencionais
DMARDS_CONFIG = {
    'metotrexato': {'aliases': ['metotrexato', 'metotrexate', 'mtx'], 'grupo': 'csDMARD'},
    'leflunomida': {'aliases': ['leflunomida', 'arava', 'lef'], 'grupo': 'csDMARD'},
    'sulfassalazina': {'aliases': ['sulfassalazina', 'azulfin', 'ssz'], 'grupo': 'csDMARD'},
    'hidroxicloroquina': {'aliases': ['hidroxicloroquina', 'plaquinol', 'hcq'], 'grupo': 'csDMARD'},
}

# Comorbidades
COMORBIDADES_CONFIG = {
    'has': ['has', 'hipertensão', 'hipertensao', 'hipertenso'],
    'dm': ['dm', 'dm2', 'diabetes', 'diabético', 'diabetico'],
    'pre_dm': ['pré-dm', 'pre-dm', 'pré-diabetes', 'pre-diabetes', 'pre-dm2'],
    'dlp': ['dlp', 'dislipidemia', 'dislipidêmico'],
    'fm': ['fm', 'fibromialgia'],
    'op': ['op', 'osteoporose', 'osteoporótico'],
    'hipotireoidismo': ['hipotireoidismo', 'tireoidite', 'hipotireoideo'],
    'obesidade': ['obesidade', 'obeso', 'imc >30'],
    'dpoc': ['dpoc', 'enfisema', 'bronquite crônica'],
    'irc': ['irc', 'doença renal', 'insuficiência renal', 'nefropatia'],
    'hepatopatia': ['hepatopatia', 'doença hepática', 'cirrose', 'esteatose'],
    'depressao': ['depressão', 'depressao', 'transtorno depressivo'],
}

# Marcadores clínicos
MARCADORES_CONFIG = {
    'vhs': {'pattern': r'v[hs]s\s*[:\s=]*(\d+[\.,]?\d*)', 'label': 'VHS - Velocidade de Hemossedimentação'},
    'leucocitos': {'pattern': r'leuc[oó]?c?i?t?o?s?\s*[:\s=]*(\d+[\.,]?\d*)', 'label': 'Leucócitos'},
    'pcr': {'pattern': r'pcr\s*[:\s=]*(\d+[\.,]?\d*)', 'label': 'PCR - Proteína C-Reativa'},
    'haq': {'pattern': r'haq\s*[:\s=]*(\d+[\.,]?\d*)', 'label': 'HAQ - Health Assessment Questionnaire'},
    'das28': {'pattern': r'das\s*-?\s*28\s*[:\s=]*(\d+[\.,]?\d*)', 'label': 'DAS28 - Disease Activity Score'},
    'cdai': {'pattern': r'cdai\s*[:\s=]*(\d+[\.,]?\d*)', 'label': 'CDAI - Clinical Disease Activity Index'},
    'sdai': {'pattern': r'sdai\s*[:\s=]*(\d+[\.,]?\d*)', 'label': 'SDAI - Simplified Disease Activity Index'},
    'basdai': {'pattern': r'basdai\s*[:\s=]*(\d+[\.,]?\d*)', 'label': 'BASDAI - Bath Ankylosing Spondylitis DAI'},
    'asdas': {'pattern': r'asdas\s*[:\s=]*(\d+[\.,]?\d*)', 'label': 'ASDAS - Ankylosing Spondylitis DAS'},
}

# Padrões de status de uso
USO_ATIVO_PATTERNS = [
    r'em\s+uso', r'mant[eé]m', r'mantenho', r'renovo\s+lme',
    r'segue\s+com', r'continua\s+com', r'uso\s+atual',
    r'medicaç[oõ]es?\s+em\s+uso', r'usando',
]

USO_PREVIO_PATTERNS = [
    r'uso\s+pr[eé]vio', r'pr[eé]vio[s]?\s*[:\s]', r'fez\s+uso',
    r'j[aá]\s+usou', r'suspen[sd][oa]', r'parou', r'interromp',
    r'descontinua', r'n[aã]o\s+tolera', r'intoler[aâ]ncia',
    r'hepatotoxicidade', r'alop[eé]cia', r'falha\s+terap[eê]utica',
]

MOTIVOS_SUSPENSAO = [
    'intolerância', 'hepatotoxicidade', 'alopécia', 'alopecia',
    'falha', 'infecção', 'efeito adverso', 'evento adverso',
    'falta', 'indisponibilidade', 'gestação', 'gravidez',
]


# =============================================================================
# FUNÇÕES DE EXTRAÇÃO
# =============================================================================

def is_number(s):
    """Verifica se uma string contém números"""
    return bool(re.search(r'\d', str(s)))


def extract_fator_reumatoide(text):
    """Extrai informações sobre Fator Reumatoide"""
    if pd.isna(text):
        return {'fr_resultado': 'NÃO INFORMADO', 'fr_valor': None, 'fr_origem': None}
    
    text_lower = str(text).lower()
    result = {'fr_resultado': 'NÃO INFORMADO', 'fr_valor': None, 'fr_origem': None}
    
    # Buscar padrões positivos
    for pattern in FR_POSITIVO_PATTERNS:
        if re.search(pattern, text_lower):
            result['fr_resultado'] = 'POSITIVO'
            result['fr_origem'] = 'TEXTO'
            break
    
    # Buscar padrões negativos
    if result['fr_resultado'] == 'NÃO INFORMADO':
        for pattern in FR_NEGATIVO_PATTERNS:
            if re.search(pattern, text_lower):
                result['fr_resultado'] = 'NEGATIVO'
                result['fr_origem'] = 'TEXTO'
                break
    
    # Extrair valor numérico
    valor_match = re.search(FR_VALOR_PATTERN, text_lower)
    if valor_match:
        try:
            result['fr_valor'] = float(valor_match.group(1).replace(',', '.'))
            result['fr_origem'] = 'LAB'
        except:
            pass
    
    # Inferir por CID-10
    if result['fr_resultado'] == 'NÃO INFORMADO':
        cid_match = re.search(CID_PATTERN, text, re.IGNORECASE)
        if cid_match:
            cid = cid_match.group(1).upper()
            if '.' not in cid and len(cid) >= 4:
                cid = cid[:3] + '.' + cid[3:]
            if cid in CID_FR_MAPPING:
                result['fr_resultado'] = CID_FR_MAPPING[cid]
                result['fr_origem'] = 'CID'
    
    return result


def extract_medicamento_status(text, medicamento, aliases):
    """Extrai status de uso de medicamento (SIM/PRÉVIO/NÃO)"""
    if pd.isna(text):
        return {'uso': 'NÃO', 'nome': None, 'motivo_suspensao': None}
    
    text_lower = str(text).lower()
    result = {'uso': 'NÃO', 'nome': None, 'motivo_suspensao': None}
    
    # Verificar se o medicamento é mencionado
    med_found = False
    for alias in aliases:
        if alias.lower() in text_lower:
            med_found = True
            result['nome'] = medicamento
            break
    
    if not med_found:
        return result
    
    # Buscar contexto próximo ao medicamento
    for alias in aliases:
        for match in re.finditer(re.escape(alias.lower()), text_lower):
            start = max(0, match.start() - 300)
            end = min(len(text_lower), match.end() + 300)
            context = text_lower[start:end]
            
            # Verificar uso prévio
            for pattern in USO_PREVIO_PATTERNS:
                if re.search(pattern, context):
                    result['uso'] = 'PRÉVIO'
                    for motivo in MOTIVOS_SUSPENSAO:
                        if motivo in context:
                            result['motivo_suspensao'] = motivo
                            break
                    break
            
            # Verificar uso ativo
            if result['uso'] != 'PRÉVIO':
                for pattern in USO_ATIVO_PATTERNS:
                    if re.search(pattern, context):
                        result['uso'] = 'SIM'
                        break
    
    # Default: se menciona, assume uso
    if result['uso'] == 'NÃO' and med_found:
        result['uso'] = 'SIM'
    
    return result


def extract_marcadores(df, selected_markers, column_name='descricao'):
    """Extrai marcadores clínicos selecionados"""
    for marker in selected_markers:
        df[marker] = None
    
    for idx, text in enumerate(df[column_name]):
        if pd.isna(text):
            continue
        text_lower = str(text).lower()
        
        for marker in selected_markers:
            if marker in MARCADORES_CONFIG:
                pattern = MARCADORES_CONFIG[marker]['pattern']
                match = re.search(pattern, text_lower)
                if match and pd.isna(df.loc[idx, marker]):
                    try:
                        df.loc[idx, marker] = float(match.group(1).replace(',', '.'))
                    except:
                        pass
    
    return df


def extract_comorbidades(df, selected_comorbidities, column_name='descricao'):
    """Extrai comorbidades selecionadas como flags binárias"""
    for comorb in selected_comorbidities:
        df[comorb] = 0
    
    for idx, text in enumerate(df[column_name]):
        if pd.isna(text):
            continue
        text_lower = str(text).lower()
        
        for comorb in selected_comorbidities:
            if comorb in COMORBIDADES_CONFIG:
                for alias in COMORBIDADES_CONFIG[comorb]:
                    if alias in text_lower:
                        df.loc[idx, comorb] = 1
                        break
    
    # Flag geral
    if selected_comorbidities:
        df['comorbidade_qualquer'] = (df[list(selected_comorbidities)].sum(axis=1) > 0).astype(int)
    
    return df


def extract_medicamentos_v3(df, selected_medications, column_name='descricao'):
    """Extrai medicamentos com status SIM/PRÉVIO/NÃO"""
    # Colunas de status (novo)
    for med in selected_medications:
        df[f'{med}_status'] = 'NÃO'
        df[f'{med}_motivo'] = None
        df[med] = 0  # Manter compatibilidade binária
    
    for idx, text in enumerate(df[column_name]):
        if pd.isna(text):
            continue
        
        for med in selected_medications:
            # Buscar config em biológicos ou DMARDs
            config = BIOLOGICOS_CONFIG.get(med) or DMARDS_CONFIG.get(med)
            if config:
                aliases = config['aliases']
                status = extract_medicamento_status(text, med, aliases)
                
                df.loc[idx, f'{med}_status'] = status['uso']
                df.loc[idx, f'{med}_motivo'] = status['motivo_suspensao']
                
                # Flag binária para compatibilidade
                if status['uso'] in ['SIM', 'PRÉVIO']:
                    df.loc[idx, med] = 1
    
    return df


def extract_mtx_detalhado(df, column_name='descricao'):
    """Extrai detalhes específicos do Metotrexato"""
    df['uso_mtx'] = 'NÃO'
    df['mtx_dose_mg_semana'] = None
    df['mtx_via'] = None
    df['motivo_suspensao_mtx'] = None
    
    for idx, text in enumerate(df[column_name]):
        if pd.isna(text):
            continue
        
        text_lower = str(text).lower()
        
        # Status
        status = extract_medicamento_status(text, 'metotrexato', DMARDS_CONFIG['metotrexato']['aliases'])
        df.loc[idx, 'uso_mtx'] = status['uso']
        df.loc[idx, 'motivo_suspensao_mtx'] = status['motivo_suspensao']
        
        # Dose
        dose_match = re.search(r'(?:mtx|metotrexato)\s*[:\s]*(\d+[\.,]?\d*)\s*(?:mg)?', text_lower)
        if dose_match:
            try:
                df.loc[idx, 'mtx_dose_mg_semana'] = float(dose_match.group(1).replace(',', '.'))
            except:
                pass
        
        # Via
        if re.search(r'(?:mtx|metotrexato)\s*\S*\s*(sc|subcutan[eê])', text_lower):
            df.loc[idx, 'mtx_via'] = 'SC'
        elif re.search(r'(?:mtx|metotrexato)\s*\S*\s*(vo|oral|comprimido)', text_lower):
            df.loc[idx, 'mtx_via'] = 'VO'
        elif re.search(r'(?:mtx|metotrexato)\s*\S*\s*(im|intramuscular)', text_lower):
            df.loc[idx, 'mtx_via'] = 'IM'
    
    return df


def extract_biologicos_detalhado(df, selected_biologicos, column_name='descricao'):
    """Extrai detalhes de biológicos com grupo terapêutico"""
    df['uso_biologico'] = 'NÃO'
    df['biologico_nome'] = None
    df['biologico_grupo'] = None
    df['num_biologicos_previos'] = 0
    
    for idx, text in enumerate(df[column_name]):
        if pd.isna(text):
            continue
        
        biologicos_em_uso = []
        biologicos_previos = []
        
        for med in selected_biologicos:
            if med in BIOLOGICOS_CONFIG:
                config = BIOLOGICOS_CONFIG[med]
                status = extract_medicamento_status(text, med, config['aliases'])
                
                if status['uso'] == 'SIM':
                    biologicos_em_uso.append({'nome': med, 'grupo': config['grupo']})
                elif status['uso'] == 'PRÉVIO':
                    biologicos_previos.append({'nome': med, 'grupo': config['grupo']})
        
        if biologicos_em_uso:
            df.loc[idx, 'uso_biologico'] = 'SIM'
            df.loc[idx, 'biologico_nome'] = biologicos_em_uso[0]['nome']
            df.loc[idx, 'biologico_grupo'] = biologicos_em_uso[0]['grupo']
        elif biologicos_previos:
            df.loc[idx, 'uso_biologico'] = 'PRÉVIO'
            df.loc[idx, 'biologico_nome'] = biologicos_previos[0]['nome']
            df.loc[idx, 'biologico_grupo'] = biologicos_previos[0]['grupo']
        
        df.loc[idx, 'num_biologicos_previos'] = len(biologicos_previos)
    
    return df


def extract_fator_reumatoide_df(df, column_name='descricao'):
    """Aplica extração de FR ao DataFrame"""
    df['fr_resultado'] = 'NÃO INFORMADO'
    df['fr_valor'] = None
    df['fr_origem'] = None
    
    for idx, text in enumerate(df[column_name]):
        fr_info = extract_fator_reumatoide(text)
        df.loc[idx, 'fr_resultado'] = fr_info['fr_resultado']
        df.loc[idx, 'fr_valor'] = fr_info['fr_valor']
        df.loc[idx, 'fr_origem'] = fr_info['fr_origem']
    
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
    """Cria base longitudinal com medidas t0 e t1"""
    baseline = df[df['tipo'] == baseline_type].copy()
    followup = df[df['tipo'] == followup_type].copy()
    
    baseline = baseline.sort_values(by=date_col, ascending=True)
    baseline = baseline.drop_duplicates(subset=[patient_col], keep="first")
    
    followup = followup.sort_values(by=date_col, ascending=False)
    followup = followup.drop_duplicates(subset=[patient_col], keep="first")
    
    baseline_marker_cols = marker_cols + [date_col]
    baseline.columns = [
        col + '_t0' if col in baseline_marker_cols else col
        for col in baseline.columns
    ]
    
    followup.columns = [
        col + '_t1' if col in baseline_marker_cols else col
        for col in followup.columns
    ]
    
    # Colunas extras para manter do baseline (não são marcadores, não ganham _t0)
    extra_cols = ['idade', 'sexo', 'fr_resultado', 'fr_valor', 'fr_origem',
                  'uso_mtx', 'mtx_dose_mg_semana', 'mtx_via', 'motivo_suspensao_mtx',
                  'uso_biologico', 'biologico_nome', 'biologico_grupo', 'num_biologicos_previos',
                  'comorbidade_qualquer']
    
    # Adicionar colunas de comorbidades individuais
    comorb_cols = [c for c in baseline.columns if c in COMORBIDADES_CONFIG.keys()]
    extra_cols.extend(comorb_cols)
    
    # Adicionar colunas de medicamentos individuais (status e binário)
    med_cols = [c for c in baseline.columns if c.endswith('_status') or c.endswith('_motivo')]
    extra_cols.extend(med_cols)
    
    # Colunas para manter do baseline
    keep_cols = [patient_col]
    keep_cols += [c for c in extra_cols if c in baseline.columns]
    keep_cols += [col for col in baseline.columns if '_t0' in col]
    
    # Remover duplicatas na lista
    keep_cols = list(dict.fromkeys(keep_cols))
    
    # Selecionar colunas do followup (apenas marcadores _t1 e paciente)
    followup_keep = [patient_col] + [col for col in followup.columns if '_t1' in col]
    
    merged = baseline[keep_cols].merge(followup[followup_keep], on=patient_col, how='inner')
    
    # Tratar possíveis duplicatas restantes
    for col in extra_cols:
        if f'{col}_y' in merged.columns:
            merged = merged.drop(columns=[f'{col}_y'], errors='ignore')
        if f'{col}_x' in merged.columns:
            merged = merged.rename(columns={f'{col}_x': col})
    
    # Calcular tempo de tratamento
    if f'{date_col}_t0' in merged.columns and f'{date_col}_t1' in merged.columns:
        merged['tempo_tratamento_dias'] = (
            merged[f'{date_col}_t1'] - merged[f'{date_col}_t0']
        ).dt.days
    
    return merged


def calculate_improvement(merged_df, criteria_dict):
    """Calcula melhora baseada em critérios personalizados"""
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
# INTERFACE PRINCIPAL
# =============================================================================

def main():
    # Header
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

    st.header("Pipeline ETL para Análise de Eficácia Terapêutica")
    st.markdown("---")

    # Sidebar
    with st.sidebar:
        st.markdown("### ⚙️ Configurações")
        st.markdown("---")
    
    uploaded_file = st.sidebar.file_uploader(
        "📁 Upload do arquivo de dados",
        type=['xlsx', 'xls', 'csv'],
        help="Faça upload da planilha com os prontuários médicos"
    )
    
    if uploaded_file is None:
        st.info("👈 Por favor, faça upload de um arquivo na barra lateral para começar.")
        
        with st.expander("📋 Estrutura de dados esperada"):
            st.markdown("""
            **Colunas obrigatórias:**
            - `paciente`: ID único do paciente
            - `tipo`: Tipo de registro (ANAMNESE, EVOLUCAO)
            - `data_hora`: Data e hora do registro
            - `descricao`: Texto do prontuário
            
            **Colunas opcionais (recomendadas):**
            - `idade`: Idade do paciente
            - `sexo`: Sexo (M/F)
            - `especialidade`: Especialidade médica
            """)
        
        with st.expander("🆕 Novidades da versão 3.1"):
            st.markdown("""
            **Novas variáveis:**
            - ✅ **Fator Reumatoide (FR)**: resultado, valor numérico, origem (LAB/TEXTO/CID)
            - ✅ **Status de medicamentos**: SIM / PRÉVIO / NÃO
            - ✅ **MTX detalhado**: dose, via (VO/SC/IM), motivo suspensão
            - ✅ **Biológicos expandidos**: +4 medicamentos, grupo terapêutico
            - ✅ **Inferência por CID-10** para FR
            
            **Funcionalidades completas:**
            - ✅ Configuração interativa via checkboxes
            - ✅ Análise Exploratória (4 subtabs)
            - ✅ Análise de Eficácia por subgrupos
            - ✅ Critérios de melhora configuráveis
            """)
        return
    
    # Carregar dados
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        if 'data_hora' in df.columns:
            df['data_hora'] = pd.to_datetime(df['data_hora'], errors='coerce')
        
        st.sidebar.success(f"✅ {len(df)} registros carregados")
        
    except Exception as e:
        st.sidebar.error(f"❌ Erro: {str(e)}")
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
            st.metric("Pacientes Únicos", df['paciente'].nunique() if 'paciente' in df.columns else "N/A")
        with col3:
            st.metric("Tipos de Registro", df['tipo'].nunique() if 'tipo' in df.columns else "N/A")
        with col4:
            if 'data_hora' in df.columns:
                date_range = (df['data_hora'].max() - df['data_hora'].min()).days
                st.metric("Período (dias)", date_range)
            else:
                st.metric("Período", "N/A")
        
        st.markdown("#### 📋 Preview dos Dados")
        st.dataframe(df.head(20), use_container_width=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📐 Informações das Colunas")
            info_df = pd.DataFrame({
                'Coluna': df.columns,
                'Tipo': df.dtypes.values,
                'Não-Nulos': df.count().values,
                '% Completo': (df.count().values / len(df) * 100).round(2)
            })
            st.dataframe(info_df, use_container_width=True)
        
        with col2:
            if 'tipo' in df.columns:
                st.markdown("#### 📊 Distribuição por Tipo")
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
        
        # Verificar requisitos
        required_cols = ['paciente', 'tipo', 'descricao', 'data_hora']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            st.error(f"❌ Colunas obrigatórias ausentes: {', '.join(missing_cols)}")
            return
        
        st.success("✅ Todas as colunas obrigatórias presentes!")
        
        # --- FATOR REUMATOIDE (NOVO) ---
        st.markdown("#### 🧬 0. Fator Reumatoide (FR) - NOVO v3.1")
        extract_fr = st.checkbox("Extrair Fator Reumatoide", value=True, 
                                  help="Extrai FR resultado, valor e origem (LAB/TEXTO/CID)")
        
        st.markdown("---")
        
        # --- MARCADORES CLÍNICOS ---
        st.markdown("#### 📊 1. Marcadores Clínicos")
        st.markdown("Selecione os marcadores clínicos a extrair:")
        
        selected_markers = {}
        col1, col2 = st.columns(2)
        
        with col1:
            for key in ['vhs', 'leucocitos', 'pcr', 'haq']:
                label = MARCADORES_CONFIG[key]['label']
                if st.checkbox(label, value=(key in ['vhs', 'pcr', 'haq', 'das28']), key=f'marker_{key}'):
                    selected_markers[key] = MARCADORES_CONFIG[key]
        
        with col2:
            for key in ['das28', 'cdai', 'sdai', 'basdai', 'asdas']:
                label = MARCADORES_CONFIG[key]['label']
                if st.checkbox(label, value=(key in ['das28', 'cdai']), key=f'marker_{key}'):
                    selected_markers[key] = MARCADORES_CONFIG[key]
        
        st.markdown("---")
        
        # --- COMORBIDADES ---
        st.markdown("#### 🏥 2. Comorbidades")
        st.markdown("Selecione as comorbidades a identificar:")
        
        selected_comorbidities = {}
        col1, col2 = st.columns(2)
        
        comorb_keys = list(COMORBIDADES_CONFIG.keys())
        
        with col1:
            for key in comorb_keys[:len(comorb_keys)//2]:
                if st.checkbox(key.upper(), value=(key in ['has', 'dm', 'dlp', 'fm']), key=f'comorb_{key}'):
                    selected_comorbidities[key] = COMORBIDADES_CONFIG[key]
        
        with col2:
            for key in comorb_keys[len(comorb_keys)//2:]:
                if st.checkbox(key.upper(), value=(key in ['op']), key=f'comorb_{key}'):
                    selected_comorbidities[key] = COMORBIDADES_CONFIG[key]
        
        st.markdown("---")
        
        # --- MEDICAMENTOS ---
        st.markdown("#### 💊 3. Medicamentos")
        
        col1, col2, col3 = st.columns(3)
        
        selected_medications = []
        selected_biologicos = []
        
        with col1:
            st.markdown("**JAK Inibidores**")
            for key in ['tofacitinibe', 'upadacitinibe', 'baricitinibe']:
                if st.checkbox(key.title(), value=(key in ['tofacitinibe', 'upadacitinibe']), key=f'med_{key}'):
                    selected_medications.append(key)
                    selected_biologicos.append(key)
        
        with col2:
            st.markdown("**Anti-TNF**")
            for key in ['adalimumabe', 'etanercepte', 'golimumabe', 'infliximabe', 'certolizumabe']:
                if st.checkbox(key.title(), value=(key in ['adalimumabe', 'etanercepte']), key=f'med_{key}'):
                    selected_medications.append(key)
                    selected_biologicos.append(key)
        
        with col3:
            st.markdown("**Outros Biológicos**")
            for key in ['tocilizumabe', 'rituximabe', 'abatacepte', 'secuquinumabe']:
                if st.checkbox(key.title(), value=False, key=f'med_{key}'):
                    selected_medications.append(key)
                    selected_biologicos.append(key)
        
        st.markdown("**DMARDs Convencionais**")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.checkbox("Metotrexato (MTX)", value=True, key='med_metotrexato'):
                selected_medications.append('metotrexato')
        with col2:
            if st.checkbox("Leflunomida", value=False, key='med_leflunomida'):
                selected_medications.append('leflunomida')
        with col3:
            if st.checkbox("Sulfassalazina", value=False, key='med_sulfassalazina'):
                selected_medications.append('sulfassalazina')
        with col4:
            if st.checkbox("Hidroxicloroquina", value=False, key='med_hidroxicloroquina'):
                selected_medications.append('hidroxicloroquina')
        
        st.markdown("---")
        
        # --- CRITÉRIOS DE MELHORA ---
        st.markdown("#### 🎯 4. Critérios de Melhora")
        
        improvement_criteria = {}
        
        if 'haq' in selected_markers:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown("**HAQ** - Redução mínima para considerar melhora:")
            with col2:
                haq_threshold = st.number_input("Redução HAQ", min_value=0.0, max_value=3.0, 
                                                 value=0.35, step=0.05, key='haq_threshold',
                                                 label_visibility='collapsed')
            improvement_criteria['haq'] = lambda v0, v1, t=haq_threshold: v1 <= v0 - t
        
        if 'das28' in selected_markers:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown("**DAS28** - Percentual mínimo de redução:")
            with col2:
                das28_pct = st.number_input("% Redução DAS28", min_value=0, max_value=100,
                                            value=50, step=5, key='das28_pct',
                                            label_visibility='collapsed')
            improvement_criteria['das28'] = lambda v0, v1, p=das28_pct: v1 <= v0 * (1 - p/100)
        
        if 'cdai' in selected_markers:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown("**CDAI** - Redução mínima para considerar melhora:")
            with col2:
                cdai_threshold = st.number_input("Redução CDAI", min_value=0.0, max_value=50.0,
                                                  value=10.0, step=1.0, key='cdai_threshold',
                                                  label_visibility='collapsed')
            improvement_criteria['cdai'] = lambda v0, v1, t=cdai_threshold: v1 <= v0 - t
        
        st.markdown("---")
        
        # --- TEMPO MÍNIMO ---
        st.markdown("#### ⏱️ 5. Tempo Mínimo de Tratamento")
        min_treatment_days = st.slider(
            "Dias mínimos entre baseline e follow-up:",
            min_value=0, max_value=365, value=60, step=10,
            help="Pacientes com menos dias de tratamento serão excluídos da análise de eficácia"
        )
        
        st.markdown("---")
        
        # BOTÃO DE PROCESSAMENTO
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            process_button = st.button("🚀 Processar Dados (ETL)", type="primary", use_container_width=True)
        
        # =============================================================================
        # PROCESSAMENTO ETL
        # =============================================================================
        
        if process_button:
            with st.spinner("⚙️ Processando dados..."):
                try:
                    df_processed = df.copy()
                    
                    # Remover duplicatas
                    initial_len = len(df_processed)
                    df_processed = df_processed.drop_duplicates(subset=['descricao']).reset_index(drop=True)
                    st.info(f"🗑️ Removidas {initial_len - len(df_processed)} duplicatas")
                    
                    # ETAPA 0: Fator Reumatoide (NOVO)
                    if extract_fr:
                        st.info("🧬 Extraindo Fator Reumatoide...")
                        df_processed = extract_fator_reumatoide_df(df_processed)
                    
                    # ETAPA 1: Marcadores clínicos
                    if selected_markers:
                        st.info("📊 Extraindo marcadores clínicos...")
                        df_processed = extract_marcadores(df_processed, list(selected_markers.keys()))
                    
                    # ETAPA 2: Comorbidades
                    if selected_comorbidities:
                        st.info("🏥 Identificando comorbidades...")
                        df_processed = extract_comorbidades(df_processed, list(selected_comorbidities.keys()))
                    
                    # ETAPA 3: Medicamentos com status (NOVO v3.1)
                    if selected_medications:
                        st.info("💊 Identificando medicamentos (com status SIM/PRÉVIO/NÃO)...")
                        df_processed = extract_medicamentos_v3(df_processed, selected_medications)
                    
                    # ETAPA 3.1: MTX detalhado
                    if 'metotrexato' in selected_medications:
                        st.info("💊 Extraindo detalhes do Metotrexato...")
                        df_processed = extract_mtx_detalhado(df_processed)
                    
                    # ETAPA 3.2: Biológicos detalhado
                    if selected_biologicos:
                        st.info("🧬 Extraindo detalhes de Biológicos...")
                        df_processed = extract_biologicos_detalhado(df_processed, selected_biologicos)
                    
                    # ETAPA 4: Limpeza numérica
                    st.info("🧹 Limpando dados numéricos...")
                    df_processed = clean_numeric_columns(df_processed, list(selected_markers.keys()))
                    
                    # ETAPA 5: Filtrar pacientes válidos
                    st.info("🔍 Filtrando pacientes válidos...")
                    tipo_counts = df_processed.groupby('paciente')['tipo'].nunique()
                    valid_patients = tipo_counts[tipo_counts >= 2].index
                    df_processed = df_processed[df_processed['paciente'].isin(valid_patients)].reset_index(drop=True)
                    st.success(f"✅ {len(valid_patients)} pacientes válidos")
                    
                    # ETAPA 6: Base longitudinal
                    st.info("📈 Criando base longitudinal...")
                    
                    tipos_disponiveis = df_processed['tipo'].unique()
                    baseline_type = 'ANAMNESE' if 'ANAMNESE' in tipos_disponiveis else tipos_disponiveis[0]
                    followup_type = 'EVOLUCAO' if 'EVOLUCAO' in tipos_disponiveis else tipos_disponiveis[1]
                    
                    st.info(f"📌 Baseline: {baseline_type} | Follow-up: {followup_type}")
                    
                    df_longitudinal = create_longitudinal_data(
                        df_processed, baseline_type, followup_type,
                        list(selected_markers.keys())
                    )
                    
                    # ETAPA 7: Calcular melhora
                    if improvement_criteria:
                        st.info("🎯 Calculando melhora clínica...")
                        df_longitudinal = calculate_improvement(df_longitudinal, improvement_criteria)
                    
                    # ETAPA 8: Filtrar tempo mínimo
                    if min_treatment_days > 0 and 'tempo_tratamento_dias' in df_longitudinal.columns:
                        before_filter = len(df_longitudinal)
                        df_longitudinal = df_longitudinal[
                            df_longitudinal['tempo_tratamento_dias'] >= min_treatment_days
                        ].reset_index(drop=True)
                        st.info(f"⏱️ Removidos {before_filter - len(df_longitudinal)} pacientes com <{min_treatment_days} dias")
                    
                    # Salvar no session_state
                    st.session_state['df_processed'] = df_processed
                    st.session_state['df_longitudinal'] = df_longitudinal
                    st.session_state['selected_markers'] = selected_markers
                    st.session_state['selected_comorbidities'] = selected_comorbidities
                    st.session_state['selected_medications'] = selected_medications
                    st.session_state['selected_biologicos'] = selected_biologicos
                    
                    st.success("✅ Processamento concluído!")
                    
                    # Resumo
                    st.markdown("### 📋 Resumo do Processamento")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Pacientes Finais", len(df_longitudinal))
                    
                    if 'improvement' in df_longitudinal.columns:
                        improved = df_longitudinal['improvement'].sum()
                        col2.metric("Melhoraram", improved)
                        pct = (improved / len(df_longitudinal) * 100) if len(df_longitudinal) > 0 else 0
                        col3.metric("% Melhora", f"{pct:.1f}%")
                    
                    if 'tempo_tratamento_dias' in df_longitudinal.columns:
                        col4.metric("Tempo Médio", f"{df_longitudinal['tempo_tratamento_dias'].mean():.0f} dias")
                    
                    # Resumo FR (novo)
                    if extract_fr and 'fr_resultado' in df_processed.columns:
                        st.markdown("#### 🧬 Fator Reumatoide")
                        fr_by_patient = df_processed.groupby('paciente')['fr_resultado'].first()
                        col1, col2, col3 = st.columns(3)
                        col1.metric("FR Positivo", (fr_by_patient == 'POSITIVO').sum())
                        col2.metric("FR Negativo", (fr_by_patient == 'NEGATIVO').sum())
                        col3.metric("Não Informado", (fr_by_patient == 'NÃO INFORMADO').sum())
                    
                except Exception as e:
                    st.error(f"❌ Erro: {str(e)}")
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
        subtab1, subtab2, subtab3, subtab4, subtab5 = st.tabs([
            "👥 Demografia",
            "🧬 Fator Reumatoide",
            "📊 Marcadores",
            "🏥 Comorbidades",
            "💊 Medicamentos"
        ])
        
        # --- SUBTAB 1: DEMOGRAFIA ---
        with subtab1:
            st.markdown("#### 👥 Análise Demográfica")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if 'idade' in df_analysis.columns:
                    st.markdown("**Distribuição de Idades**")
                    fig = px.histogram(df_analysis, x='idade', nbins=30,
                                       color_discrete_sequence=['#3b82f6'])
                    fig.update_layout(xaxis_title='Idade', yaxis_title='Frequência', height=400)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Média", f"{df_analysis['idade'].mean():.1f}")
                    col_b.metric("Mediana", f"{df_analysis['idade'].median():.0f}")
                    col_c.metric("Desvio Padrão", f"{df_analysis['idade'].std():.1f}")
            
            with col2:
                if 'sexo' in df_analysis.columns:
                    st.markdown("**Distribuição por Sexo**")
                    sexo_counts = df_analysis['sexo'].value_counts()
                    fig = go.Figure(data=[go.Pie(
                        labels=sexo_counts.index,
                        values=sexo_counts.values,
                        marker=dict(colors=['#ff9999', '#66b3ff']),
                        textinfo='label+percent+value'
                    )])
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
            
            if 'idade' in df_analysis.columns and 'sexo' in df_analysis.columns:
                st.markdown("**Distribuição de Idade por Sexo**")
                fig = px.histogram(df_analysis, x='idade', color='sexo', nbins=25,
                                   barmode='stack',
                                   color_discrete_map={'F': '#ff9999', 'M': '#66b3ff'})
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
        
        # --- SUBTAB 2: FATOR REUMATOIDE (NOVO) ---
        with subtab2:
            st.markdown("#### 🧬 Análise do Fator Reumatoide")
            
            if 'fr_resultado' not in df_analysis.columns:
                st.info("Fator Reumatoide não foi extraído. Ative a opção na configuração do ETL.")
            else:
                # Por paciente único
                fr_by_patient = df_analysis.groupby('paciente').agg({
                    'fr_resultado': 'first',
                    'fr_valor': 'first',
                    'fr_origem': 'first'
                }).reset_index()
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Distribuição do FR**")
                    fr_counts = fr_by_patient['fr_resultado'].value_counts()
                    fig = go.Figure(data=[go.Pie(
                        labels=fr_counts.index,
                        values=fr_counts.values,
                        marker=dict(colors=['#ef4444', '#22c55e', '#9ca3af']),
                        textinfo='label+percent+value',
                        hole=0.4
                    )])
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    st.markdown("**Origem da Informação**")
                    origem_counts = fr_by_patient['fr_origem'].dropna().value_counts()
                    fig = px.bar(x=origem_counts.index, y=origem_counts.values,
                                 color=origem_counts.index,
                                 color_discrete_map={'LAB': '#3b82f6', 'TEXTO': '#06b6d4', 'CID': '#8b5cf6'})
                    fig.update_layout(height=400, showlegend=False,
                                      xaxis_title='Origem', yaxis_title='Pacientes')
                    st.plotly_chart(fig, use_container_width=True)
                
                # Valores numéricos
                fr_valores = fr_by_patient[fr_by_patient['fr_valor'].notna()]
                if len(fr_valores) > 0:
                    st.markdown("**Valores Laboratoriais de FR**")
                    col1, col2 = st.columns(2)
                    with col1:
                        fig = px.histogram(fr_valores, x='fr_valor', nbins=20,
                                           color_discrete_sequence=['#3b82f6'])
                        fig.update_layout(xaxis_title='Valor FR (UI/mL)', yaxis_title='Frequência')
                        st.plotly_chart(fig, use_container_width=True)
                    with col2:
                        fig = px.box(fr_valores, y='fr_valor', color_discrete_sequence=['#3b82f6'])
                        fig.update_layout(yaxis_title='Valor FR (UI/mL)')
                        st.plotly_chart(fig, use_container_width=True)
        
        # --- SUBTAB 3: MARCADORES ---
        with subtab3:
            st.markdown("#### 📊 Análise de Marcadores Clínicos")
            
            if 'selected_markers' not in st.session_state:
                st.info("Nenhum marcador configurado")
            else:
                markers = list(st.session_state['selected_markers'].keys())
                available_markers = [m for m in markers if m in df_analysis.columns]
                
                if not available_markers:
                    st.warning("Nenhum marcador foi extraído dos dados")
                else:
                    selected_marker = st.selectbox("Selecione o marcador:", available_markers,
                                                    format_func=lambda x: x.upper())
                    
                    marker_data = df_analysis[selected_marker].dropna()
                    
                    if len(marker_data) == 0:
                        st.warning(f"Nenhum dado disponível para {selected_marker.upper()}")
                    else:
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            fig = px.histogram(marker_data, nbins=30,
                                               color_discrete_sequence=['#22c55e'])
                            fig.update_layout(title=f"Distribuição de {selected_marker.upper()}",
                                              xaxis_title=selected_marker.upper(),
                                              yaxis_title='Frequência', height=350)
                            st.plotly_chart(fig, use_container_width=True)
                            
                            stats_df = pd.DataFrame({
                                'Métrica': ['Média', 'Mediana', 'Desvio Padrão', 'Mínimo', 'Máximo'],
                                'Valor': [f"{marker_data.mean():.2f}", f"{marker_data.median():.2f}",
                                          f"{marker_data.std():.2f}", f"{marker_data.min():.2f}",
                                          f"{marker_data.max():.2f}"]
                            })
                            st.dataframe(stats_df, use_container_width=True, hide_index=True)
                        
                        with col2:
                            fig = px.box(marker_data, y=marker_data.values,
                                         color_discrete_sequence=['#22c55e'])
                            fig.update_layout(title=f"Box Plot - {selected_marker.upper()}",
                                              yaxis_title=selected_marker.upper(), height=350)
                            st.plotly_chart(fig, use_container_width=True)
                            
                            total_records = len(df_analysis)
                            available = len(marker_data)
                            st.metric("Registros Disponíveis", f"{available} / {total_records}")
                            st.metric("% Completo", f"{(available/total_records*100):.1f}%")
                    
                    # Matriz de correlação
                    if len(available_markers) > 1:
                        st.markdown("---")
                        st.markdown("**Matriz de Correlação dos Marcadores**")
                        markers_df = df_analysis[available_markers].apply(pd.to_numeric, errors='coerce')
                        corr_matrix = markers_df.corr()
                        
                        fig = px.imshow(corr_matrix,
                                        labels=dict(color="Correlação"),
                                        x=[m.upper() for m in corr_matrix.columns],
                                        y=[m.upper() for m in corr_matrix.index],
                                        color_continuous_scale='RdBu_r',
                                        zmin=-1, zmax=1)
                        fig.update_layout(height=500)
                        st.plotly_chart(fig, use_container_width=True)
        
        # --- SUBTAB 4: COMORBIDADES ---
        with subtab4:
            st.markdown("#### 🏥 Análise de Comorbidades")
            
            if 'selected_comorbidities' not in st.session_state:
                st.info("Nenhuma comorbidade configurada")
            else:
                comorb_cols = list(st.session_state['selected_comorbidities'].keys())
                available_comorb = [c for c in comorb_cols if c in df_analysis.columns]
                
                if not available_comorb:
                    st.warning("Nenhuma comorbidade foi identificada")
                else:
                    # Por paciente único
                    comorb_by_patient = df_analysis.groupby('paciente')[available_comorb].max()
                    comorb_counts = {c.upper(): int(comorb_by_patient[c].sum()) for c in available_comorb}
                    
                    fig = px.bar(x=list(comorb_counts.keys()), y=list(comorb_counts.values()),
                                 color=list(comorb_counts.values()),
                                 color_continuous_scale='Reds')
                    fig.update_layout(title="Frequência de Comorbidades",
                                      xaxis_title='Comorbidade', yaxis_title='Pacientes',
                                      showlegend=False, height=400)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**Frequência Absoluta:**")
                        freq_df = pd.DataFrame({
                            'Comorbidade': list(comorb_counts.keys()),
                            'Pacientes': list(comorb_counts.values())
                        }).sort_values('Pacientes', ascending=False)
                        st.dataframe(freq_df, use_container_width=True, hide_index=True)
                    
                    with col2:
                        st.markdown("**Frequência Relativa:**")
                        total_patients = df_analysis['paciente'].nunique()
                        freq_df['%'] = (freq_df['Pacientes'] / total_patients * 100).round(2)
                        st.dataframe(freq_df[['Comorbidade', '%']], use_container_width=True, hide_index=True)
                    
                    # Comorbidades múltiplas
                    st.markdown("---")
                    st.markdown("**Análise de Comorbidades Múltiplas**")
                    comorb_by_patient['num_comorbidades'] = comorb_by_patient.sum(axis=1)
                    comorb_dist = comorb_by_patient['num_comorbidades'].value_counts().sort_index()
                    
                    fig = px.bar(x=comorb_dist.index, y=comorb_dist.values,
                                 color=comorb_dist.values, color_continuous_scale='Oranges')
                    fig.update_layout(title="Número de Comorbidades por Paciente",
                                      xaxis_title='Número de Comorbidades',
                                      yaxis_title='Pacientes', showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
        
        # --- SUBTAB 5: MEDICAMENTOS ---
        with subtab5:
            st.markdown("#### 💊 Análise de Medicamentos")
            
            if 'selected_medications' not in st.session_state:
                st.info("Nenhum medicamento configurado")
            else:
                med_tabs = st.tabs(["📦 MTX", "🧬 Biológicos", "📊 Todos"])
                
                # MTX
                with med_tabs[0]:
                    if 'uso_mtx' in df_analysis.columns:
                        mtx_by_patient = df_analysis.groupby('paciente')['uso_mtx'].first()
                        mtx_counts = mtx_by_patient.value_counts()
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("**Status de Uso do MTX**")
                            fig = go.Figure(data=[go.Pie(
                                labels=mtx_counts.index,
                                values=mtx_counts.values,
                                marker=dict(colors=['#22c55e', '#f59e0b', '#ef4444']),
                                textinfo='label+percent+value',
                                hole=0.4
                            )])
                            fig.update_layout(height=350)
                            st.plotly_chart(fig, use_container_width=True)
                        
                        with col2:
                            st.markdown("**Estatísticas MTX**")
                            total = len(mtx_by_patient)
                            st.metric("Uso Atual (SIM)", f"{mtx_counts.get('SIM', 0)} ({mtx_counts.get('SIM', 0)/total*100:.1f}%)")
                            st.metric("Uso Prévio", f"{mtx_counts.get('PRÉVIO', 0)} ({mtx_counts.get('PRÉVIO', 0)/total*100:.1f}%)")
                            st.metric("Nunca Usou", f"{mtx_counts.get('NÃO', 0)} ({mtx_counts.get('NÃO', 0)/total*100:.1f}%)")
                        
                        # Dose e via
                        if 'mtx_dose_mg_semana' in df_analysis.columns:
                            doses = df_analysis['mtx_dose_mg_semana'].dropna()
                            if len(doses) > 0:
                                st.markdown("**Distribuição de Doses de MTX**")
                                fig = px.histogram(doses, nbins=15, color_discrete_sequence=['#3b82f6'])
                                fig.update_layout(xaxis_title='Dose (mg/semana)', yaxis_title='Frequência')
                                st.plotly_chart(fig, use_container_width=True)
                        
                        if 'mtx_via' in df_analysis.columns:
                            via_counts = df_analysis['mtx_via'].dropna().value_counts()
                            if len(via_counts) > 0:
                                st.markdown("**Via de Administração**")
                                fig = px.pie(values=via_counts.values, names=via_counts.index)
                                st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("MTX não foi configurado para extração")
                
                # Biológicos
                with med_tabs[1]:
                    if 'uso_biologico' in df_analysis.columns:
                        bio_by_patient = df_analysis.groupby('paciente').agg({
                            'uso_biologico': 'first',
                            'biologico_nome': 'first',
                            'biologico_grupo': 'first'
                        }).reset_index()
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("**Status de Uso de Biológicos**")
                            bio_counts = bio_by_patient['uso_biologico'].value_counts()
                            fig = go.Figure(data=[go.Pie(
                                labels=bio_counts.index,
                                values=bio_counts.values,
                                marker=dict(colors=['#22c55e', '#f59e0b', '#ef4444']),
                                textinfo='label+percent+value',
                                hole=0.4
                            )])
                            fig.update_layout(height=350)
                            st.plotly_chart(fig, use_container_width=True)
                        
                        with col2:
                            st.markdown("**Biológicos Mais Utilizados**")
                            nome_counts = bio_by_patient['biologico_nome'].dropna().value_counts().head(10)
                            fig = px.bar(x=nome_counts.values, y=nome_counts.index,
                                         orientation='h', color=nome_counts.values,
                                         color_continuous_scale='Blues')
                            fig.update_layout(height=350, showlegend=False,
                                              xaxis_title='Pacientes', yaxis_title='')
                            st.plotly_chart(fig, use_container_width=True)
                        
                        st.markdown("**Distribuição por Grupo Terapêutico**")
                        grupo_counts = bio_by_patient['biologico_grupo'].dropna().value_counts()
                        fig = px.bar(x=grupo_counts.index, y=grupo_counts.values,
                                     color=grupo_counts.index,
                                     color_discrete_map={
                                         'Anti-TNF': '#3b82f6',
                                         'Anti-IL/Outros': '#06b6d4',
                                         'JAK Inibidores': '#8b5cf6',
                                         'Anti-IL17': '#f59e0b'
                                     })
                        fig.update_layout(xaxis_title='', yaxis_title='Pacientes', showlegend=False)
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("Biológicos não foram configurados para extração")
                
                # Todos
                with med_tabs[2]:
                    selected_meds = st.session_state.get('selected_medications', [])
                    available_meds = [m for m in selected_meds if m in df_analysis.columns]
                    
                    if available_meds:
                        med_by_patient = df_analysis.groupby('paciente')[available_meds].max()
                        med_counts = {m.title(): int(med_by_patient[m].sum()) for m in available_meds}
                        med_counts_sorted = dict(sorted(med_counts.items(), key=lambda x: x[1], reverse=True))
                        
                        fig = px.bar(x=list(med_counts_sorted.values()),
                                     y=list(med_counts_sorted.keys()),
                                     orientation='h',
                                     color=list(med_counts_sorted.values()),
                                     color_continuous_scale='Greens')
                        fig.update_layout(title="Frequência de Uso de Medicamentos",
                                          xaxis_title='Pacientes', yaxis_title='',
                                          showlegend=False, height=max(400, len(med_counts)*30))
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Politerapia
                        st.markdown("---")
                        st.markdown("**Análise de Politerapia**")
                        med_by_patient['num_medicamentos'] = med_by_patient.sum(axis=1)
                        politerapia_counts = med_by_patient['num_medicamentos'].value_counts().sort_index()
                        
                        fig = px.bar(x=politerapia_counts.index, y=politerapia_counts.values,
                                     color=politerapia_counts.values, color_continuous_scale='Purples')
                        fig.update_layout(xaxis_title='Número de Medicamentos',
                                          yaxis_title='Pacientes', showlegend=False)
                        st.plotly_chart(fig, use_container_width=True)
    
    # =============================================================================
    # TAB 4: ANÁLISE DE EFICÁCIA
    # =============================================================================
    
    with tab4:
        st.subheader("🎯 Análise de Eficácia Terapêutica")
        
        if 'df_longitudinal' not in st.session_state:
            st.warning("⚠️ Execute o processamento ETL primeiro")
            return
        
        df_long = st.session_state['df_longitudinal']
        
        if 'improvement' not in df_long.columns:
            st.warning("⚠️ Nenhum critério de melhora foi configurado")
            return
        
        # Métricas gerais
        st.markdown("#### 📊 Visão Geral da Eficácia")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total de Pacientes", len(df_long))
        improved = df_long['improvement'].sum()
        col2.metric("Melhoraram", improved)
        col3.metric("Não Melhoraram", len(df_long) - improved)
        pct_improved = (improved / len(df_long) * 100) if len(df_long) > 0 else 0
        col4.metric("Taxa de Resposta", f"{pct_improved:.1f}%")
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = go.Figure(data=[go.Pie(
                labels=['Com Melhora', 'Sem Melhora'],
                values=[improved, len(df_long) - improved],
                marker=dict(colors=['#22c55e', '#ef4444']),
                textinfo='label+percent+value',
                hole=0.3
            )])
            fig.update_layout(title="Distribuição de Resposta", height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            if 'tempo_tratamento_dias' in df_long.columns:
                fig = px.histogram(df_long, x='tempo_tratamento_dias',
                                   color='improvement', nbins=30, barmode='overlay',
                                   color_discrete_map={0: '#ef4444', 1: '#22c55e'},
                                   labels={'tempo_tratamento_dias': 'Dias', 'improvement': 'Melhorou'})
                fig.update_layout(title="Tempo de Tratamento por Resposta", height=400)
                st.plotly_chart(fig, use_container_width=True)
        
        # Evolução dos marcadores
        if 'selected_markers' in st.session_state:
            st.markdown("---")
            st.markdown("#### 📈 Evolução dos Marcadores Clínicos")
            
            markers = list(st.session_state['selected_markers'].keys())
            available_t0t1 = [m for m in markers 
                             if f'{m}_t0' in df_long.columns and f'{m}_t1' in df_long.columns]
            
            if available_t0t1:
                selected_marker_evo = st.selectbox("Marcador para análise:",
                                                    available_t0t1, format_func=lambda x: x.upper())
                
                col_t0 = f'{selected_marker_evo}_t0'
                col_t1 = f'{selected_marker_evo}_t1'
                
                df_marker = df_long[[col_t0, col_t1, 'improvement']].dropna()
                
                if len(df_marker) > 0:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        df_melt = pd.melt(df_marker, id_vars=['improvement'],
                                          value_vars=[col_t0, col_t1],
                                          var_name='Tempo', value_name='Valor')
                        df_melt['Tempo'] = df_melt['Tempo'].map({col_t0: 'Baseline', col_t1: 'Follow-up'})
                        
                        fig = px.box(df_melt, x='Tempo', y='Valor', color='improvement',
                                     color_discrete_map={0: '#ef4444', 1: '#22c55e'},
                                     labels={'improvement': 'Melhorou'})
                        fig.update_layout(title=f"Comparação {selected_marker_evo.upper()}", height=400)
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        df_marker['mudanca'] = df_marker[col_t1] - df_marker[col_t0]
                        
                        fig = px.scatter(df_marker, x=col_t0, y=col_t1, color='improvement',
                                         color_discrete_map={0: '#ef4444', 1: '#22c55e'},
                                         hover_data=['mudanca'],
                                         labels={'improvement': 'Melhorou'})
                        
                        max_val = max(df_marker[col_t0].max(), df_marker[col_t1].max())
                        min_val = min(df_marker[col_t0].min(), df_marker[col_t1].min())
                        fig.add_shape(type='line', x0=min_val, y0=min_val, x1=max_val, y1=max_val,
                                      line=dict(color='gray', dash='dash'))
                        fig.update_layout(title=f"Evolução Individual", height=400)
                        st.plotly_chart(fig, use_container_width=True)
        
        # Análise por subgrupos
        st.markdown("---")
        st.markdown("#### 👥 Análise por Subgrupos")
        
        subtab_sex, subtab_age, subtab_fr, subtab_comorb, subtab_meds, subtab_trocas = st.tabs([
            "Por Sexo", "Por Idade", "Por FR", "Por Comorbidades", "Por Medicamentos", "🔄 Análise de Trocas"
        ])
        
        with subtab_sex:
            if 'sexo' in df_long.columns:
                response_by_sex = df_long.groupby('sexo')['improvement'].agg(['sum', 'count'])
                response_by_sex['taxa'] = (response_by_sex['sum'] / response_by_sex['count'] * 100)
                
                fig = px.bar(x=response_by_sex.index, y=response_by_sex['taxa'],
                             color=response_by_sex['taxa'], color_continuous_scale='Blues',
                             text=response_by_sex['taxa'].round(1))
                fig.update_traces(texttemplate='%{text}%', textposition='outside')
                fig.update_layout(title="Taxa de Resposta por Sexo",
                                  xaxis_title='Sexo', yaxis_title='Taxa (%)', showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
                
                st.dataframe(response_by_sex.rename(columns={
                    'sum': 'Melhoraram', 'count': 'Total', 'taxa': 'Taxa (%)'
                }).round(2), use_container_width=True)
            else:
                st.info("Dados de sexo não disponíveis")
        
        with subtab_age:
            if 'idade' in df_long.columns:
                df_long['faixa_etaria'] = pd.cut(df_long['idade'],
                                                  bins=[0, 30, 40, 50, 60, 70, 120],
                                                  labels=['<30', '30-40', '40-50', '50-60', '60-70', '>70'])
                
                response_by_age = df_long.groupby('faixa_etaria')['improvement'].agg(['sum', 'count'])
                response_by_age['taxa'] = (response_by_age['sum'] / response_by_age['count'] * 100)
                
                fig = px.bar(x=response_by_age.index.astype(str), y=response_by_age['taxa'],
                             color=response_by_age['taxa'], color_continuous_scale='Greens',
                             text=response_by_age['taxa'].round(1))
                fig.update_traces(texttemplate='%{text}%', textposition='outside')
                fig.update_layout(title="Taxa de Resposta por Faixa Etária",
                                  xaxis_title='Faixa Etária', yaxis_title='Taxa (%)', showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Dados de idade não disponíveis")
        
        with subtab_fr:
            if 'fr_resultado' in df_long.columns:
                response_by_fr = df_long.groupby('fr_resultado')['improvement'].agg(['sum', 'count'])
                response_by_fr['taxa'] = (response_by_fr['sum'] / response_by_fr['count'] * 100)
                
                fig = px.bar(x=response_by_fr.index, y=response_by_fr['taxa'],
                             color=response_by_fr.index,
                             color_discrete_map={'POSITIVO': '#ef4444', 'NEGATIVO': '#22c55e', 'NÃO INFORMADO': '#9ca3af'},
                             text=response_by_fr['taxa'].round(1))
                fig.update_traces(texttemplate='%{text}%', textposition='outside')
                fig.update_layout(title="Taxa de Resposta por Fator Reumatoide",
                                  xaxis_title='FR', yaxis_title='Taxa (%)', showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
                
                st.dataframe(response_by_fr.rename(columns={
                    'sum': 'Melhoraram', 'count': 'Total', 'taxa': 'Taxa (%)'
                }).round(2), use_container_width=True)
            else:
                st.info("FR não foi extraído")
        
        with subtab_comorb:
            if 'comorbidade_qualquer' in df_long.columns:
                df_long['tem_comorbidade'] = df_long['comorbidade_qualquer'].map({
                    0: 'Sem Comorbidades', 1: 'Com Comorbidades'
                })
                
                response_by_comorb = df_long.groupby('tem_comorbidade')['improvement'].agg(['sum', 'count'])
                response_by_comorb['taxa'] = (response_by_comorb['sum'] / response_by_comorb['count'] * 100)
                
                fig = px.bar(x=response_by_comorb.index, y=response_by_comorb['taxa'],
                             color=response_by_comorb['taxa'], color_continuous_scale='Reds',
                             text=response_by_comorb['taxa'].round(1))
                fig.update_traces(texttemplate='%{text}%', textposition='outside')
                fig.update_layout(title="Taxa de Resposta por Comorbidades",
                                  xaxis_title='', yaxis_title='Taxa (%)', showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Comorbidades não foram configuradas")
        
        with subtab_meds:
            if 'uso_biologico' in df_long.columns:
                st.markdown("**Por Status de Biológico:**")
                response_by_bio = df_long.groupby('uso_biologico')['improvement'].agg(['sum', 'count'])
                response_by_bio['taxa'] = (response_by_bio['sum'] / response_by_bio['count'] * 100)
                
                fig = px.bar(x=response_by_bio.index, y=response_by_bio['taxa'],
                             color=response_by_bio.index,
                             color_discrete_map={'SIM': '#22c55e', 'PRÉVIO': '#f59e0b', 'NÃO': '#ef4444'},
                             text=response_by_bio['taxa'].round(1))
                fig.update_traces(texttemplate='%{text}%', textposition='outside')
                fig.update_layout(title="Taxa de Resposta por Uso de Biológico",
                                  xaxis_title='', yaxis_title='Taxa (%)', showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
                
                # Por biológico específico
                if 'biologico_nome' in df_long.columns:
                    st.markdown("**Por Biológico Específico:**")
                    bio_response = {}
                    for bio in df_long['biologico_nome'].dropna().unique():
                        df_bio = df_long[df_long['biologico_nome'] == bio]
                        if len(df_bio) >= 5:
                            bio_response[bio.title()] = {
                                'Total': len(df_bio),
                                'Melhoraram': df_bio['improvement'].sum(),
                                'Taxa (%)': round(df_bio['improvement'].mean() * 100, 2)
                            }
                    
                    if bio_response:
                        bio_df = pd.DataFrame(bio_response).T.sort_values('Taxa (%)', ascending=False)
                        
                        fig = px.bar(x=bio_df.index, y=bio_df['Taxa (%)'],
                                     color=bio_df['Taxa (%)'], color_continuous_scale='Purples',
                                     text=bio_df['Taxa (%)'].round(1))
                        fig.update_traces(texttemplate='%{text}%', textposition='outside')
                        fig.update_layout(xaxis_title='', yaxis_title='Taxa (%)', showlegend=False)
                        st.plotly_chart(fig, use_container_width=True)
                        
                        st.dataframe(bio_df, use_container_width=True)
            else:
                st.info("Medicamentos não foram configurados")
        
        # =============================================================================
        # SUBTAB: ANÁLISE DE TROCAS DE MEDICAMENTOS
        # =============================================================================
        
        with subtab_trocas:
            st.markdown("#### 🔄 Análise de Trocas de Medicamentos")
            
            if 'selected_biologicos' not in st.session_state or not st.session_state['selected_biologicos']:
                st.info("💡 Configure medicamentos biológicos no ETL para ver análise de trocas")
            else:
                biologicos = st.session_state['selected_biologicos']
                
                # --- SEÇÃO 1: VISÃO GERAL ---
                st.markdown("##### 📊 Visão Geral das Trocas")
                
                stats_troca = calcular_taxa_troca_geral(df_long)
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total de Pacientes", stats_troca['total_pacientes'])
                col2.metric("Primeiro Biológico", stats_troca['pacientes_primeiro_biologico'])
                col3.metric("Trocaram Biológico", stats_troca['pacientes_que_trocaram'])
                col4.metric("Taxa de Troca", f"{stats_troca['taxa_troca_pct']:.1f}%")
                
                if stats_troca['pacientes_que_trocaram'] > 0:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Gráfico pizza: trocaram vs não trocaram
                        fig = go.Figure(data=[go.Pie(
                            labels=['Primeiro Biológico', 'Trocaram'],
                            values=[stats_troca['pacientes_primeiro_biologico'], 
                                    stats_troca['pacientes_que_trocaram']],
                            marker=dict(colors=['#22c55e', '#f59e0b']),
                            textinfo='label+percent+value',
                            hole=0.4
                        )])
                        fig.update_layout(title="Distribuição de Pacientes", height=350)
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        st.metric("Número Médio de Trocas", 
                                 f"{stats_troca['num_trocas_media']:.2f}",
                                 help="Entre pacientes que trocaram pelo menos uma vez")
                        
                        # Distribuição do número de trocas
                        if 'num_biologicos_previos' in df_long.columns:
                            dist_trocas = df_long[df_long['num_biologicos_previos'] > 0]['num_biologicos_previos'].value_counts().sort_index()
                            
                            if len(dist_trocas) > 0:
                                fig = px.bar(x=dist_trocas.index, y=dist_trocas.values,
                                             labels={'x': 'Número de Trocas', 'y': 'Pacientes'},
                                             color=dist_trocas.values,
                                             color_continuous_scale='Oranges')
                                fig.update_layout(title="Distribuição do Número de Trocas", 
                                                  showlegend=False, height=300)
                                st.plotly_chart(fig, use_container_width=True)
                
                st.markdown("---")
                
                # --- SEÇÃO 2: MATRIZ DE TRANSIÇÃO ---
                st.markdown("##### 🔀 Matriz de Transição de Medicamentos")
                st.markdown("*Mostra quantos pacientes trocaram de um medicamento (linhas) para outro (colunas)*")
                
                matriz = construir_matriz_transicao(df_long, biologicos)
                
                if matriz.sum().sum() > 0:  # Se há pelo menos uma transição
                    # Heatmap da matriz
                    fig = go.Figure(data=go.Heatmap(
                        z=matriz.values,
                        x=matriz.columns,
                        y=matriz.index,
                        colorscale='Blues',
                        text=matriz.values,
                        texttemplate='%{text}',
                        textfont={"size": 10},
                        hoverongaps=False
                    ))
                    
                    fig.update_layout(
                        title="Matriz de Transição de Medicamentos",
                        xaxis_title='Para (Medicamento Atual)',
                        yaxis_title='De (Medicamento Prévio)',
                        height=500,
                        xaxis={'side': 'bottom'},
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Mostrar tabela
                    with st.expander("📋 Ver tabela de transições"):
                        st.dataframe(matriz, use_container_width=True)
                    
                    # Insights automáticos
                    st.markdown("**💡 Insights:**")
                    max_val = matriz.max().max()
                    if max_val > 0:
                        max_pos = [(i, j) for i in matriz.index for j in matriz.columns 
                                  if matriz.loc[i, j] == max_val][0]
                        st.info(f"• Transição mais comum: **{max_pos[0]} → {max_pos[1]}** ({int(max_val)} pacientes)")
                else:
                    st.info("Nenhuma transição de medicamento identificada nos dados")
                
                st.markdown("---")
                
                # --- SEÇÃO 3: TAXA DE ABANDONO ---
                st.markdown("##### 📉 Taxa de Abandono por Medicamento")
                
                df_taxas = calcular_taxa_abandono_por_medicamento(df_long, biologicos)
                
                if not df_taxas.empty:
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        fig = px.bar(
                            df_taxas,
                            x='Medicamento',
                            y='Taxa Abandono (%)',
                            color='Taxa Abandono (%)',
                            color_continuous_scale='Reds',
                            text='Taxa Abandono (%)',
                            hover_data=['Total Usaram', 'Suspenderam']
                        )
                        
                        fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                        fig.update_layout(
                            title='Taxa de Abandono por Medicamento',
                            xaxis_title='',
                            yaxis_title='Taxa de Abandono (%)',
                            showlegend=False,
                            height=400
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        st.markdown("**Ranking de Abandono:**")
                        st.dataframe(df_taxas[['Medicamento', 'Taxa Abandono (%)']].head(10),
                                    use_container_width=True, hide_index=True)
                        
                        # Destaque
                        if len(df_taxas) > 0:
                            mais_abandonado = df_taxas.iloc[0]
                            st.warning(f"⚠️ Maior taxa de abandono: **{mais_abandonado['Medicamento']}** ({mais_abandonado['Taxa Abandono (%)']:.1f}%)")
                else:
                    st.info("Sem dados de suspensão de medicamentos")
                
                st.markdown("---")
                
                # --- SEÇÃO 4: MOTIVOS DE SUSPENSÃO ---
                st.markdown("##### 📋 Motivos de Suspensão")
                
                df_motivos = analisar_motivos_suspensao(df_long, biologicos)
                
                if not df_motivos.empty:
                    col1, col2 = st.columns([3, 2])
                    
                    with col1:
                        # Gráfico sunburst
                        fig = px.sunburst(
                            df_motivos,
                            path=['Medicamento', 'Motivo'],
                            values='Pacientes',
                            color='Pacientes',
                            color_continuous_scale='Oranges'
                        )
                        
                        fig.update_layout(
                            title='Motivos de Suspensão por Medicamento',
                            height=500
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        st.markdown("**Motivos Mais Frequentes:**")
                        top_motivos = df_motivos.groupby('Motivo')['Pacientes'].sum().sort_values(ascending=False).head(5)
                        for motivo, count in top_motivos.items():
                            st.text(f"• {motivo}: {int(count)} pacientes")
                    
                    # Tabela detalhada
                    with st.expander("📊 Ver detalhes por medicamento"):
                        pivot = df_motivos.pivot_table(
                            index='Medicamento', 
                            columns='Motivo', 
                            values='Pacientes', 
                            fill_value=0
                        )
                        st.dataframe(pivot, use_container_width=True)
                else:
                    st.info("Motivos de suspensão não foram identificados")
                
                st.markdown("---")
                
                # --- SEÇÃO 5: SEQUÊNCIAS COMUNS ---
                st.markdown("##### 🔗 Sequências de Tratamento Mais Comuns")
                
                df_seq = identificar_sequencias_comuns(df_long, biologicos, top_n=10)
                
                if not df_seq.empty:
                    fig = px.bar(
                        df_seq,
                        x='Pacientes',
                        y='Sequência',
                        orientation='h',
                        color='Pacientes',
                        color_continuous_scale='Purples',
                        text='Pacientes'
                    )
                    
                    fig.update_traces(textposition='outside')
                    fig.update_layout(
                        title='Sequências de Tratamento Mais Comuns',
                        xaxis_title='Número de Pacientes',
                        yaxis_title='',
                        showlegend=False,
                        height=max(400, len(df_seq) * 40)
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.markdown("**💡 Interpretação:**")
                    st.markdown("As sequências mostram a ordem de uso de medicamentos. O símbolo → indica a progressão temporal do tratamento.")
                else:
                    st.info("Nenhuma sequência de tratamento identificada")
                
                st.markdown("---")
                
                # --- SEÇÃO 6: EFICÁCIA PÓS-TROCA ---
                st.markdown("##### 🎯 Eficácia: Primeiro Biológico vs Após Troca")
                
                stats_eficacia = analisar_eficacia_pos_troca(df_long)
                
                if stats_eficacia['com_troca']['total'] > 0 and stats_eficacia['sem_troca']['total'] > 0:
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        # Gráfico comparativo
                        data = {
                            'Grupo': ['Primeiro Biológico', 'Após Troca(s)'],
                            'Taxa de Resposta (%)': [
                                stats_eficacia['sem_troca']['taxa_pct'],
                                stats_eficacia['com_troca']['taxa_pct']
                            ],
                            'N': [
                                stats_eficacia['sem_troca']['total'],
                                stats_eficacia['com_troca']['total']
                            ]
                        }
                        
                        df_comp = pd.DataFrame(data)
                        
                        fig = px.bar(
                            df_comp,
                            x='Grupo',
                            y='Taxa de Resposta (%)',
                            color='Grupo',
                            color_discrete_map={
                                'Primeiro Biológico': '#22c55e',
                                'Após Troca(s)': '#f59e0b'
                            },
                            text='Taxa de Resposta (%)',
                            hover_data=['N']
                        )
                        
                        fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                        fig.update_layout(
                            title='Taxa de Resposta: Primeiro Biológico vs Após Troca',
                            xaxis_title='',
                            yaxis_title='Taxa de Resposta (%)',
                            showlegend=False,
                            height=400
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        st.markdown("**Comparativo:**")
                        
                        st.metric("Primeiro Biológico",
                                 f"{stats_eficacia['sem_troca']['taxa_pct']:.1f}%",
                                 delta=None,
                                 help=f"N = {stats_eficacia['sem_troca']['total']}")
                        
                        st.metric("Após Troca(s)",
                                 f"{stats_eficacia['com_troca']['taxa_pct']:.1f}%",
                                 delta=f"{stats_eficacia['com_troca']['taxa_pct'] - stats_eficacia['sem_troca']['taxa_pct']:.1f}%",
                                 help=f"N = {stats_eficacia['com_troca']['total']}")
                        
                        # Interpretação
                        diff = stats_eficacia['com_troca']['taxa_pct'] - stats_eficacia['sem_troca']['taxa_pct']
                        if diff > 5:
                            st.success("✅ Pacientes que trocaram têm melhor resposta")
                        elif diff < -5:
                            st.warning("⚠️ Primeiro biológico tem melhor resposta")
                        else:
                            st.info("ℹ️ Resposta similar entre grupos")
                else:
                    st.info("Dados insuficientes para comparação de eficácia")
    
    # =============================================================================
    # TAB 5: EXPORTAR DADOS
    # =============================================================================
    
    with tab5:
        st.subheader("💾 Exportar Dados Processados")
        
        if 'df_processed' not in st.session_state:
            st.warning("⚠️ Execute o processamento ETL primeiro")
            return
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📊 Dados Processados")
            df_proc = st.session_state['df_processed']
            st.info(f"Total de registros: {len(df_proc)}")
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_proc.to_excel(writer, index=False, sheet_name='Dados')
            
            st.download_button(
                label="📥 Download Excel - Dados Processados",
                data=output.getvalue(),
                file_name=f"immuned_processados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="btn_excel_proc"
            )
            
            csv = df_proc.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV - Dados Processados",
                data=csv,
                file_name=f"immuned_processados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
                key="btn_csv_proc"
            )
        
        with col2:
            if 'df_longitudinal' in st.session_state:
                st.markdown("#### 📈 Dados Longitudinais")
                df_long = st.session_state['df_longitudinal']
                st.info(f"Total de pacientes: {len(df_long)}")
                
                output_long = io.BytesIO()
                with pd.ExcelWriter(output_long, engine='openpyxl') as writer:
                    df_long.to_excel(writer, index=False, sheet_name='Longitudinal')
                
                st.download_button(
                    label="📥 Download Excel - Dados Longitudinais",
                    data=output_long.getvalue(),
                    file_name=f"immuned_longitudinal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="btn_excel_long"
                )
                
                csv_long = df_long.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV - Dados Longitudinais",
                    data=csv_long,
                    file_name=f"immuned_longitudinal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="btn_csv_long"
                )
        
        st.markdown("---")
        st.markdown("#### 📋 Preview dos Dados")
        
        preview_option = st.radio("Dataset:", ["Dados Processados", "Dados Longitudinais"], horizontal=True)
        
        if preview_option == "Dados Processados":
            st.dataframe(st.session_state['df_processed'], use_container_width=True)
        else:
            if 'df_longitudinal' in st.session_state:
                st.dataframe(st.session_state['df_longitudinal'], use_container_width=True)
        
        # Resumo da configuração
        st.markdown("---")
        st.markdown("#### ⚙️ Configuração Utilizada")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**Marcadores:**")
            if 'selected_markers' in st.session_state:
                for m in st.session_state['selected_markers'].keys():
                    st.text(f"• {m.upper()}")
        
        with col2:
            st.markdown("**Comorbidades:**")
            if 'selected_comorbidities' in st.session_state:
                for c in st.session_state['selected_comorbidities'].keys():
                    st.text(f"• {c.upper()}")
        
        with col3:
            st.markdown("**Medicamentos:**")
            if 'selected_medications' in st.session_state:
                for m in st.session_state['selected_medications'][:10]:
                    st.text(f"• {m.title()}")
                if len(st.session_state['selected_medications']) > 10:
                    st.text(f"• ... e mais {len(st.session_state['selected_medications'])-10}")
    
    # Footer
    st.markdown("---")
    st.markdown("""
        <div class="immune-footer">
            <p><strong>Immuned</strong> v3.1 | Sistema de Análise de Prontuários</p>
            <p style="font-size: 0.85rem; margin-top: 0.5rem;">
                Promovendo a saúde com tratamentos inteligentes • Precisão em doenças complexas
            </p>
            <p style="font-size: 0.8rem; color: #d1d5db; margin-top: 1rem;">
                © 2025 Immuned - Todos os direitos reservados
            </p>
        </div>
    """, unsafe_allow_html=True)


# =============================================================================
# EXECUÇÃO
# =============================================================================

if __name__ == "__main__":
    main()
