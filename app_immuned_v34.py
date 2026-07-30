# -*- coding: utf-8 -*-
"""
IMMUNED - Sistema de Análise de Prontuários Médicos
Versão 3.4

Funcionalidades:
- ✅ Configuração interativa via checkboxes
- ✅ Análise Exploratória completa (5 subtabs)
- ✅ Análise por subgrupos na eficácia
- ✅ Variáveis clínicas (FR, status SIM/PRÉVIO/NÃO, dose MTX, etc.)
- ✅ Histórico medicamentoso legível ("em uso de" / "fez uso de")

Correções (v3.2.1):
- 🐛 TypeError "Cannot perform reduction 'mean' with string dtype": a coluna
  'idade' não passava por conversão numérica no pipeline ETL e quebrava as
  métricas da subtab Demografia sob pandas 3.x (string dtype por padrão).
  Agora é limpa na ETAPA 4.1 e convertida defensivamente na exibição.

Correções e novidades (v3.4):
- 🐛 ALIASES CURTOS SEM FRONTEIRA DE PALAVRA: a busca era substring pura
  (`alias in texto`), então 'ada' (adalimumabe) casava com "indicada"/"usada",
  'aba' (abatacepte) com "abaixo", 'eta' (etanercepte) com "dieta" e 'bari'
  (baricitinibe) com "bariátrica". Agora todo alias é buscado com fronteira de
  palabra (ver `alias_pattern`). Vale também para as comorbidades ('op', 'fm',
  'dm'). Esta é a correção de maior impacto nos números.
- 🐛 FALLBACK SILENCIOSO PARA 'SIM': menção sem nenhum padrão de status era
  classificada como uso atual. Agora gera a categoria explícita
  'INDETERMINADO'. O comportamento antigo segue disponível via checkbox
  (EXTRACTION_OPTIONS['fallback_sim']) para reproduzir os números da v3.3.
- 🐛 PRIORIDADE ABSOLUTA DO 'PRÉVIO': em "fez uso de MTX, atualmente em uso de
  tocilizumabe", o "fez uso" contaminava o tocilizumabe (janela de ±300 chars).
  A decisão passa a ser por PROXIMIDADE: vence o marcador de status mais
  próximo da menção, com janela menor (±120, configurável).
- 🐛 MOMENTO DE REFERÊNCIA INDEFINIDO: a Análise Exploratória usava
  `groupby('paciente').first()` sobre um DataFrame nunca ordenado por data, ou
  seja, o status vinha de um registro escolhido pela ordem do arquivo. Agora
  `df_processed` é ordenado por (paciente, data_hora) e a interface deixa o
  usuário escolher entre a primeira e a última consulta.
- ✨ STATUS NOS DOIS MOMENTOS: a base longitudinal passa a trazer
  `{med}_status_t0` (anamnese) e `{med}_status_t1` (última evolução), além de
  `uso_biologico_t0/_t1`. As colunas sem sufixo continuam iguais à v3.3
  (= t0), para não alterar resultados já publicados sem aviso.
- ✨ HISTÓRICO MEDICAMENTOSO: `consolidar_historico()` percorre todas as
  consultas do mais antigo ao mais recente e gera, por paciente, as colunas
  `em_uso_de`, `fez_uso_de`, `n_previos` e a frase `historico_medicamentoso`
  ("Em uso de Tocilizumabe (03/2023–11/2024); fez uso de Adalimumabe
  (01/2021–02/2023), suspenso por falha.").
- ✨ Padrões de uso prévio ampliados ("fazia uso", "já utilizou", "histórico de
  uso", "trocado por", "substituído por"); 'parou' virou 'parou de usar/o uso/
  com' (antes casava com "parou de fumar"); 'hepatotoxicidade' e 'alopécia'
  saíram dos padrões de STATUS e ficaram apenas como MOTIVOS_SUSPENSAO.
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

def calcular_taxa_troca_geral(df, sufixo=''):
    """Calcula taxa geral de troca de medicamentos.

    `sufixo` escolhe o momento de referência: '' (compatibilidade v3.3, igual a
    t0), '_t0' (anamnese) ou '_t1' (última evolução).
    """
    stats = {
        'total_pacientes': len(df),
        'pacientes_sem_biologico': 0,
        'pacientes_primeiro_biologico': 0,
        'pacientes_que_trocaram': 0,
        'taxa_troca_pct': 0.0,
        'num_trocas_media': 0.0,
    }

    col_previos = f'num_biologicos_previos{sufixo}'
    col_uso = f'uso_biologico{sufixo}'

    if col_previos in df.columns:
        previos = pd.to_numeric(df[col_previos], errors='coerce').fillna(0)
        stats['pacientes_que_trocaram'] = int((previos > 0).sum())
        stats['pacientes_primeiro_biologico'] = int((previos == 0).sum())

        if col_uso in df.columns:
            pacientes_com_bio = int(df[col_uso].isin(['SIM', 'PRÉVIO']).sum())
            if pacientes_com_bio > 0:
                stats['taxa_troca_pct'] = (stats['pacientes_que_trocaram'] / pacientes_com_bio) * 100

        com_troca = previos[previos > 0]
        stats['num_trocas_media'] = float(com_troca.mean()) if len(com_troca) else 0.0

    return stats

def construir_matriz_transicao(df, medicamentos, sufixo=''):
    """Constrói matriz de transição entre medicamentos (DE prévio -> PARA atual).

    ATENÇÃO (limitação conhecida): com sufixo '' ou '_t0' a matriz só captura
    trocas que já estavam DESCRITAS dentro do mesmo registro ("fez uso de X,
    hoje em uso de Y"). Para trocas ocorridas ENTRE a anamnese e a última
    evolução, use `construir_matriz_transicao_t0_t1`.
    """
    matriz = pd.DataFrame(0,
                         index=[m.title() for m in medicamentos],
                         columns=[m.title() for m in medicamentos])

    for idx, row in df.iterrows():
        previos = [m for m in medicamentos
                   if f'{m}_status{sufixo}' in df.columns
                   and row.get(f'{m}_status{sufixo}') == 'PRÉVIO']

        atual = None
        for m in medicamentos:
            if f'{m}_status{sufixo}' in df.columns and row.get(f'{m}_status{sufixo}') == 'SIM':
                atual = m
                break

        if atual:
            for previo in previos:
                matriz.loc[previo.title(), atual.title()] += 1

    return matriz


def construir_matriz_transicao_t0_t1(df, medicamentos):
    """Matriz de transição observada ENTRE os dois momentos (t0 -> t1).

    Novidade da v3.4: conta o paciente que estava em uso de X na anamnese e
    aparece em uso de Y (≠ X) na última evolução. É a troca de fato observada
    no seguimento, e não apenas a troca relatada no texto.
    """
    matriz = pd.DataFrame(0,
                         index=[m.title() for m in medicamentos],
                         columns=[m.title() for m in medicamentos])

    for _, row in df.iterrows():
        de = next((m for m in medicamentos
                   if row.get(f'{m}_status_t0') == 'SIM'), None)
        para = next((m for m in medicamentos
                     if row.get(f'{m}_status_t1') == 'SIM'), None)
        if de and para and de != para:
            matriz.loc[de.title(), para.title()] += 1

    return matriz

def analisar_motivos_suspensao(df, medicamentos, sufixo=''):
    """Analisa motivos de suspensão de medicamentos"""
    motivos_data = []

    for med in medicamentos:
        col_status = f'{med}_status{sufixo}'
        col_motivo = f'{med}_motivo{sufixo}'

        if col_status in df.columns and col_motivo in df.columns:
            suspenderam = df[df[col_status] == 'PRÉVIO']
            motivos = suspenderam[col_motivo].dropna().value_counts()

            for motivo, count in motivos.items():
                motivos_data.append({
                    'Medicamento': med.title(),
                    'Motivo': str(motivo).title(),
                    'Pacientes': int(count)
                })

    if motivos_data:
        return pd.DataFrame(motivos_data)
    else:
        return pd.DataFrame(columns=['Medicamento', 'Motivo', 'Pacientes'])

def calcular_taxa_abandono_por_medicamento(df, medicamentos, sufixo=''):
    """Calcula taxa de abandono para cada medicamento.

    v3.4: 'INDETERMINADO' é reportado em coluna própria e NÃO entra no
    denominador, para não inflar nem deflacionar a taxa de abandono.
    """
    taxas = []

    for med in medicamentos:
        col_status = f'{med}_status{sufixo}'

        if col_status in df.columns:
            serie = df[col_status]
            total_usaram = int(serie.isin(['SIM', 'PRÉVIO']).sum())
            suspenderam = int((serie == 'PRÉVIO').sum())
            indef = int((serie == 'INDETERMINADO').sum())

            if total_usaram > 0:
                taxa_pct = (suspenderam / total_usaram) * 100
                taxas.append({
                    'Medicamento': med.title(),
                    'Total Usaram': total_usaram,
                    'Suspenderam': suspenderam,
                    'Indeterminados': indef,
                    'Taxa Abandono (%)': round(taxa_pct, 2)
                })

    df_taxas = pd.DataFrame(taxas)
    if not df_taxas.empty:
        df_taxas = df_taxas.sort_values('Taxa Abandono (%)', ascending=False)

    return df_taxas

def identificar_sequencias_comuns(df, medicamentos, top_n=10, sufixo=''):
    """Identifica as sequências de tratamento mais comuns"""
    sequencias = []

    for idx, row in df.iterrows():
        previos = [m.title() for m in medicamentos
                   if f'{m}_status{sufixo}' in df.columns
                   and row.get(f'{m}_status{sufixo}') == 'PRÉVIO']

        atual = None
        for m in medicamentos:
            if f'{m}_status{sufixo}' in df.columns and row.get(f'{m}_status{sufixo}') == 'SIM':
                atual = m.title()
                break

        if previos and atual:
            seq = ' → '.join(previos[:3]) + f' → {atual}'
            sequencias.append(seq)

    if not sequencias:
        return pd.DataFrame(columns=['Sequência', 'Pacientes'])

    seq_counts = pd.Series(sequencias).value_counts().head(top_n)

    return pd.DataFrame({
        'Sequência': seq_counts.index,
        'Pacientes': seq_counts.values
    })

def analisar_eficacia_pos_troca(df, sufixo=''):
    """Analisa eficácia em pacientes que trocaram vs não trocaram"""
    stats = {
        'com_troca': {'total': 0, 'melhoraram': 0, 'taxa_pct': 0.0},
        'sem_troca': {'total': 0, 'melhoraram': 0, 'taxa_pct': 0.0},
    }

    col_previos = f'num_biologicos_previos{sufixo}'
    col_uso = f'uso_biologico{sufixo}'

    if 'improvement' not in df.columns or col_previos not in df.columns:
        return stats

    previos = pd.to_numeric(df[col_previos], errors='coerce').fillna(0)

    com_troca = df[previos > 0]
    stats['com_troca']['total'] = len(com_troca)
    stats['com_troca']['melhoraram'] = int(pd.to_numeric(com_troca['improvement'], errors='coerce').fillna(0).sum())
    if len(com_troca) > 0:
        stats['com_troca']['taxa_pct'] = (stats['com_troca']['melhoraram'] / len(com_troca)) * 100

    if col_uso in df.columns:
        sem_troca = df[(previos == 0) & (df[col_uso] == 'SIM')]
    else:
        sem_troca = df[previos == 0]
    stats['sem_troca']['total'] = len(sem_troca)
    stats['sem_troca']['melhoraram'] = int(pd.to_numeric(sem_troca['improvement'], errors='coerce').fillna(0).sum())
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
    r'em\s+uso', r'mant[eé]m', r'mantenho', r'mantid[oa]', r'renovo\s+lme',
    r'renova[çc][aã]o\s+d[eo]\s+lme', r'segue\s+(com|em\s+uso)',
    r'continua\s+(com|em\s+uso)', r'uso\s+atual', r'atualmente\s+em\s+uso',
    r'medica[çc][oõ]es?\s+em\s+uso', r'usando', r'faz\s+uso(?!\s+pr[eé]vio)',
    r'inici(ou|ad[oa]|ando)', r'prescrit[oa]', r'aplica[çc][aã]o\s+quinzenal',
]

USO_PREVIO_PATTERNS = [
    r'fez\s+uso(\s+pr[eé]vio)?(\s+d[eoa]s?)?',
    r'j[aá]\s+(fez\s+uso|usou|utilizou|fazia\s+uso)',
    r'fazia\s+uso', r'uso\s+pr[eé]vio', r'em\s+uso\s+pr[eé]vio',
    r'previamente\s+em\s+uso', r'hist[oó]rico\s+de\s+uso',
    r'usou\s+(no\s+passado|anteriormente|at[eé])',
    r'pr[eé]vio[s]?\s*[:\s]',
    r'suspen[sdçc][oaã]', r'suspendeu', r'interromp', r'descontinu',
    r'parou\s+(de\s+usar|o\s+uso|com)',
    r'trocad[oa]\s+por', r'substitu[ií]d[oa]\s+por', r'troca\s+por',
    r'n[aã]o\s+tolera', r'intoler[aâ]ncia',
    r'falha\s+terap[eê]utica', r'sem\s+resposta\s+a',
]

# NOTA: 'hepatotoxicidade' e 'alopécia' saíram de USO_PREVIO_PATTERNS. Sozinhos
# eles não provam suspensão (podem estar num alerta de monitorização); seguem
# valendo como MOTIVOS_SUSPENSAO quando o status já foi definido como PRÉVIO.
MOTIVOS_SUSPENSAO = [
    'intolerância', 'hepatotoxicidade', 'alopécia', 'alopecia',
    'falha', 'infecção', 'efeito adverso', 'evento adverso',
    'falta', 'indisponibilidade', 'gestação', 'gravidez',
]

# Categorias de status possíveis (a ordem define a ordem nos gráficos)
STATUS_ORDEM = ['SIM', 'PRÉVIO', 'INDETERMINADO', 'NÃO']
STATUS_CORES = {
    'SIM': '#22c55e',
    'PRÉVIO': '#f59e0b',
    'INDETERMINADO': '#94a3b8',
    'NÃO': '#ef4444',
}

# Opções de extração ajustáveis pela interface (aba "Configurar ETL").
# Ficam em nível de módulo porque são lidas pelas funções de extração, que são
# chamadas de vários pontos do pipeline.
EXTRACTION_OPTIONS = {
    # True reproduz a v3.3: menção sem contexto de status vira 'SIM'.
    'fallback_sim': False,
    # True (recomendado) exige fronteira de palavra nos aliases.
    'aliases_estritos': True,
    # Meia-janela, em caracteres, para procurar marcadores de status.
    'janela_contexto': 120,
}


def alias_pattern(alias):
    r"""Monta o regex de um alias com fronteira de palavra.

    Necessário porque aliases curtos ('ada', 'aba', 'eta', 'bari', 'tofa')
    casavam dentro de palavras comuns do português ('indicada', 'abaixo',
    'dieta', 'bariátrica'), gerando falsos positivos de medicamento.
    \b não serve aqui: acentos não são \w em todas as configurações, então
    usamos lookarounds explícitos incluindo o intervalo acentuado.
    """
    nucleo = re.escape(alias.lower())
    if not EXTRACTION_OPTIONS.get('aliases_estritos', True):
        return nucleo
    return r'(?<![0-9a-zà-ÿ])' + nucleo + r'(?![0-9a-zà-ÿ])'


def encontrar_mencoes(text_lower, aliases):
    """Devolve a lista de (inicio, fim) de todas as menções dos aliases."""
    mencoes = []
    for alias in aliases:
        for m in re.finditer(alias_pattern(alias), text_lower):
            mencoes.append((m.start(), m.end()))
    return sorted(set(mencoes))


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
    """Extrai status de uso de medicamento (SIM / PRÉVIO / INDETERMINADO / NÃO).

    Regra de decisão (v3.4): para cada menção do medicamento, procura
    marcadores de uso ativo e de uso prévio dentro de uma janela de
    ±EXTRACTION_OPTIONS['janela_contexto'] caracteres e vence o marcador MAIS
    PRÓXIMO da menção. Em caso de empate de distância, o uso prévio vence
    (conservador: evita contar como tratamento atual algo que foi suspenso).

    Isso substitui a regra da v3.3, em que qualquer padrão de uso prévio na
    janela de ±300 caracteres tornava o medicamento PRÉVIO de forma
    irreversível — o que classificava errado o medicamento atual em textos do
    tipo "fez uso de MTX, atualmente em uso de tocilizumabe".
    """
    if pd.isna(text):
        return {'uso': 'NÃO', 'nome': None, 'motivo_suspensao': None}

    text_lower = str(text).lower()
    result = {'uso': 'NÃO', 'nome': None, 'motivo_suspensao': None}

    mencoes = encontrar_mencoes(text_lower, aliases)
    if not mencoes:
        return result

    result['nome'] = medicamento
    meia_janela = int(EXTRACTION_OPTIONS.get('janela_contexto', 120))

    # melhor = (distancia, prioridade_empate, status, contexto)
    # prioridade_empate: 0 = PRÉVIO, 1 = SIM -> PRÉVIO ganha empates
    melhor = None

    for ini_m, fim_m in mencoes:
        ini = max(0, ini_m - meia_janela)
        fim = min(len(text_lower), fim_m + meia_janela)
        contexto = text_lower[ini:fim]
        pos_med = ini_m - ini

        for status, padroes, prio in (('PRÉVIO', USO_PREVIO_PATTERNS, 0),
                                      ('SIM', USO_ATIVO_PATTERNS, 1)):
            for padrao in padroes:
                for k in re.finditer(padrao, contexto):
                    # distância do marcador até a menção do medicamento
                    if k.end() <= pos_med:
                        dist = pos_med - k.end()
                    elif k.start() >= pos_med:
                        dist = k.start() - pos_med
                    else:
                        dist = 0
                    candidato = (dist, prio, status, contexto)
                    if melhor is None or candidato[:2] < melhor[:2]:
                        melhor = candidato

    if melhor is not None:
        result['uso'] = melhor[2]
        if result['uso'] == 'PRÉVIO':
            contexto = melhor[3]
            for motivo in MOTIVOS_SUSPENSAO:
                if motivo in contexto:
                    result['motivo_suspensao'] = motivo
                    break
    else:
        # Medicamento citado, nenhum marcador de status por perto.
        # v3.3 assumia 'SIM'; v3.4 explicita a ambiguidade.
        result['uso'] = 'SIM' if EXTRACTION_OPTIONS.get('fallback_sim') else 'INDETERMINADO'

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
                    # v3.4: fronteira de palavra. Antes, 'op' (osteoporose)
                    # casava com "opção"/"operação", 'fm' com "fmais",
                    # 'dm' com "dmard" e 'irc' com "circulação".
                    if re.search(alias_pattern(alias), text_lower):
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
                
                # Flag binária = "medicamento citado no registro".
                # INDETERMINADO entra aqui para preservar a contagem binária da
                # v3.3, em que a menção sem contexto era classificada como SIM.
                if status['uso'] in ['SIM', 'PRÉVIO', 'INDETERMINADO']:
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
    """Extrai detalhes de biológicos com grupo terapêutico.

    v3.4: a categoria INDETERMINADO passa a existir e é reportada, em vez de
    ser somada silenciosamente ao uso atual.
    """
    df['uso_biologico'] = 'NÃO'
    df['biologico_nome'] = None
    df['biologico_grupo'] = None
    df['num_biologicos_previos'] = 0
    df['num_biologicos_indeterminados'] = 0

    for idx, text in enumerate(df[column_name]):
        if pd.isna(text):
            continue

        biologicos_em_uso = []
        biologicos_previos = []
        biologicos_indef = []

        for med in selected_biologicos:
            if med in BIOLOGICOS_CONFIG:
                config = BIOLOGICOS_CONFIG[med]
                status = extract_medicamento_status(text, med, config['aliases'])

                if status['uso'] == 'SIM':
                    biologicos_em_uso.append({'nome': med, 'grupo': config['grupo']})
                elif status['uso'] == 'PRÉVIO':
                    biologicos_previos.append({'nome': med, 'grupo': config['grupo']})
                elif status['uso'] == 'INDETERMINADO':
                    biologicos_indef.append({'nome': med, 'grupo': config['grupo']})

        if biologicos_em_uso:
            df.loc[idx, 'uso_biologico'] = 'SIM'
            df.loc[idx, 'biologico_nome'] = biologicos_em_uso[0]['nome']
            df.loc[idx, 'biologico_grupo'] = biologicos_em_uso[0]['grupo']
        elif biologicos_previos:
            df.loc[idx, 'uso_biologico'] = 'PRÉVIO'
            df.loc[idx, 'biologico_nome'] = biologicos_previos[0]['nome']
            df.loc[idx, 'biologico_grupo'] = biologicos_previos[0]['grupo']
        elif biologicos_indef:
            df.loc[idx, 'uso_biologico'] = 'INDETERMINADO'
            df.loc[idx, 'biologico_nome'] = biologicos_indef[0]['nome']
            df.loc[idx, 'biologico_grupo'] = biologicos_indef[0]['grupo']

        df.loc[idx, 'num_biologicos_previos'] = len(biologicos_previos)
        df.loc[idx, 'num_biologicos_indeterminados'] = len(biologicos_indef)

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


# Colunas de medicamento/status que existem por registro e que passam a ser
# duplicadas para os dois momentos (_t0 = anamnese, _t1 = última evolução).
COLS_STATUS_EXTRA = [
    'uso_mtx', 'motivo_suspensao_mtx', 'mtx_dose_mg_semana', 'mtx_via',
    'uso_biologico', 'biologico_nome', 'biologico_grupo',
    'num_biologicos_previos', 'num_biologicos_indeterminados',
    'fr_resultado', 'fr_valor', 'fr_origem',
]


def colunas_de_status(frame):
    """Colunas de status/medicamento de um DataFrame de registros."""
    return [c for c in frame.columns
            if c.endswith('_status') or c.endswith('_motivo')
            or c in COLS_STATUS_EXTRA]


def create_longitudinal_data(df, baseline_type, followup_type, marker_cols,
                            date_col='data_hora', patient_col='paciente'):
    """Cria base longitudinal com medidas t0 e t1.

    Eixo temporal (inalterado desde a v3.2): t0 = registro de ANAMNESE mais
    ANTIGO, t1 = registro de EVOLUÇÃO mais RECENTE.

    v3.4: além dos marcadores, as colunas de medicamento passam a existir nos
    dois momentos (`{med}_status_t0` / `{med}_status_t1`, `uso_biologico_t0` /
    `uso_biologico_t1`, etc.). As colunas SEM sufixo continuam vindo do
    baseline, exatamente como na v3.3, para não alterar em silêncio números já
    calculados; a escolha do momento é feita explicitamente na interface.
    """
    baseline = df[df['tipo'] == baseline_type].copy()
    followup = df[df['tipo'] == followup_type].copy()

    baseline = baseline.sort_values(by=date_col, ascending=True)
    baseline = baseline.drop_duplicates(subset=[patient_col], keep="first")

    followup = followup.sort_values(by=date_col, ascending=False)
    followup = followup.drop_duplicates(subset=[patient_col], keep="first")

    # v3.4: duplicar (não renomear) as colunas de status para os dois momentos.
    # Feito ANTES da renomeação dos marcadores para não capturar vhs_t0 & cia.
    for c in colunas_de_status(baseline):
        baseline[f'{c}_t0'] = baseline[c]
    for c in colunas_de_status(followup):
        followup[f'{c}_t1'] = followup[c]

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
                  'uso_biologico', 'biologico_nome', 'biologico_grupo',
                  'num_biologicos_previos', 'num_biologicos_indeterminados',
                  'comorbidade_qualquer']

    # Adicionar colunas de comorbidades individuais
    comorb_cols = [c for c in baseline.columns if c in COMORBIDADES_CONFIG.keys()]
    extra_cols.extend(comorb_cols)

    # Adicionar colunas de medicamentos individuais (status e binário)
    med_cols = [c for c in baseline.columns
                if (c.endswith('_status') or c.endswith('_motivo'))
                and not c.endswith('_t0') and not c.endswith('_t1')]
    extra_cols.extend(med_cols)

    # Colunas para manter do baseline (inclui automaticamente tudo com _t0)
    keep_cols = [patient_col]
    keep_cols += [c for c in extra_cols if c in baseline.columns]
    keep_cols += [col for col in baseline.columns if col.endswith('_t0')]

    # Remover duplicatas na lista
    keep_cols = list(dict.fromkeys(keep_cols))

    # Selecionar colunas do followup (marcadores _t1 e status _t1 + paciente)
    followup_keep = [patient_col] + [col for col in followup.columns
                                     if col.endswith('_t1')]
    followup_keep = list(dict.fromkeys(followup_keep))

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


def consolidar_historico(df, medicamentos, biologicos=None,
                         patient_col='paciente', date_col='data_hora'):
    """Reconstrói o histórico medicamentoso do registro mais ANTIGO ao mais
    RECENTE e devolve UMA linha por paciente.

    Diferente da base longitudinal (que olha só a anamnese e a última
    evolução), aqui todas as consultas são percorridas. O status considerado
    "atual" é o da consulta mais recente em que o medicamento aparece.

    Colunas devolvidas:
      - em_uso_de:   medicamentos cuja última menção é uso ativo
      - fez_uso_de:  medicamentos cuja última menção é uso prévio (+ motivo)
      - indeterminados: citados sem contexto de status
      - n_atuais / n_previos / n_indeterminados
      - n_biologicos_atuais: quantos BIOLÓGICOS aparecem como uso ativo ao mesmo
        tempo. Valor ≥ 2 é clinicamente improvável (biológicos não se combinam)
        e sinaliza registro a revisar: normalmente o prontuário cita o
        biológico antigo sem marcar a suspensão. Passe `biologicos=` para que
        esta coluna seja calculada.
    """
    if date_col in df.columns:
        df = df.sort_values([patient_col, date_col])
    else:
        df = df.sort_values([patient_col])

    registros = []

    for pid, g in df.groupby(patient_col, sort=False):
        em_uso, fez_uso, indef = [], [], []

        for med in medicamentos:
            col = f'{med}_status'
            if col not in g.columns:
                continue

            hist = g[[c for c in (date_col, col) if c in g.columns]].dropna(subset=[col])
            hist = hist[hist[col].isin(['SIM', 'PRÉVIO', 'INDETERMINADO'])]
            if hist.empty:
                continue

            # Período em que apareceu como uso ativo
            periodo = ''
            if date_col in hist.columns:
                datas_sim = hist.loc[hist[col] == 'SIM', date_col].dropna()
                if not datas_sim.empty:
                    ini, fim = datas_sim.iloc[0], datas_sim.iloc[-1]
                    if ini == fim:
                        periodo = f" ({ini:%m/%Y})"
                    else:
                        periodo = f" ({ini:%m/%Y}–{fim:%m/%Y})"

            rotulo = f"{med.title()}{periodo}"
            status_final = hist[col].iloc[-1]

            if status_final == 'SIM':
                em_uso.append(rotulo)
            elif status_final == 'PRÉVIO':
                col_motivo = f'{med}_motivo'
                if col_motivo in g.columns:
                    motivos = g[col_motivo].dropna()
                    if not motivos.empty:
                        rotulo += f", suspenso por {motivos.iloc[-1]}"
                fez_uso.append(rotulo)
            else:
                indef.append(med.title())

        # Biológicos simultâneos: sinalizador de registro a revisar
        bios_atuais = []
        if biologicos:
            titulos_bio = {b.title() for b in biologicos}
            bios_atuais = [rot for rot in em_uso
                           if rot.split(' (')[0] in titulos_bio]

        registros.append({
            patient_col: pid,
            'em_uso_de': '; '.join(em_uso) or None,
            'fez_uso_de': '; '.join(fez_uso) or None,
            'indeterminados': '; '.join(indef) or None,
            'n_atuais': len(em_uso),
            'n_previos': len(fez_uso),
            'n_indeterminados': len(indef),
            'n_biologicos_atuais': len(bios_atuais),
        })

    df_hist = pd.DataFrame(registros)
    if not df_hist.empty:
        df_hist['historico_medicamentoso'] = df_hist.apply(frase_historico, axis=1)
    return df_hist


def _preenchido(valor):
    """True se o campo tem conteúdo útil.

    Necessário porque `None` numa coluna object do pandas volta como NaN, e
    `bool(float('nan'))` é True — um `if r.get('fez_uso_de'):` ingênuo produzia
    frases do tipo "fez uso de nan".
    """
    if valor is None or pd.isna(valor):
        return False
    return str(valor).strip() not in ('', 'nan', 'None')


def frase_historico(r):
    """Monta a frase legível do histórico de um paciente."""
    partes = []
    if _preenchido(r.get('em_uso_de')):
        partes.append(f"Em uso de {r['em_uso_de']}")
    if _preenchido(r.get('fez_uso_de')):
        partes.append(f"fez uso de {r['fez_uso_de']}")
    if _preenchido(r.get('indeterminados')):
        partes.append(f"citados sem contexto: {r['indeterminados']}")
    if not partes:
        return 'Sem registro de DMARD/biológico.'
    return '; '.join(partes) + '.'

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
# v3.4: tolerante a falha. Antes, um LOGO.jpeg ausente (clone parcial do repo,
# execução a partir de outro diretório) derrubava o app no import, antes mesmo
# de qualquer mensagem de erro chegar à tela.
try:
    logo = Image.open('LOGO.jpeg')
except Exception:
    logo = "🧬"

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
        st.markdown("#### 🧬 0. Fator Reumatoide (FR)")
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
        
        # --- OPÇÕES DE EXTRAÇÃO (v3.4) ---
        st.markdown("#### 🔍 3.1 Opções de Extração de Texto")

        with st.expander("Ajustar regras de reconhecimento (recomendado manter o padrão)"):
            st.markdown(
                "Estas opções controlam **como** o regex interpreta o prontuário. "
                "O padrão corresponde à v3.4; marque as caixas de compatibilidade "
                "para reproduzir os números da v3.3 e comparar."
            )

            opt_aliases = st.checkbox(
                "Exigir fronteira de palavra nos aliases (recomendado)",
                value=True, key='opt_aliases_estritos',
                help="Sem esta opção, 'ada' (adalimumabe) casa com 'indicada', "
                     "'aba' (abatacepte) com 'abaixo' e 'eta' (etanercepte) com "
                     "'dieta'. Desmarque apenas para reproduzir a v3.3."
            )

            opt_fallback = st.checkbox(
                "Compatibilidade v3.3: menção sem contexto conta como uso atual",
                value=False, key='opt_fallback_sim',
                help="Na v3.3, um medicamento citado sem nenhuma expressão de "
                     "status era classificado como 'SIM'. Na v3.4 ele recebe a "
                     "categoria 'INDETERMINADO'."
            )

            opt_janela = st.slider(
                "Janela de contexto (caracteres antes/depois da menção):",
                min_value=60, max_value=300, value=120, step=20,
                key='opt_janela_contexto',
                help="Janelas grandes misturam medicamentos de uma mesma lista. "
                     "A v3.3 usava 300."
            )

            if not opt_aliases or opt_fallback:
                st.warning(
                    "⚠️ Você ativou opções de compatibilidade com a v3.3. "
                    "Os resultados tendem a **superestimar** o uso atual de "
                    "medicamentos. Use apenas para comparação."
                )

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
                    # v3.4: aplicar as opções de extração escolhidas na interface
                    EXTRACTION_OPTIONS['aliases_estritos'] = opt_aliases
                    EXTRACTION_OPTIONS['fallback_sim'] = opt_fallback
                    EXTRACTION_OPTIONS['janela_contexto'] = opt_janela

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

                    # ETAPA 4.1: Garantir tipo numérico das colunas demográficas
                    # ATENÇÃO: nunca incluir colunas categóricas (ex.: 'sexo') aqui,
                    # pois a limpeza numérica as destruiria silenciosamente.
                    df_processed = clean_numeric_columns(df_processed, ['idade'])
                    
                    # ETAPA 5: Filtrar pacientes válidos
                    st.info("🔍 Filtrando pacientes válidos...")
                    tipo_counts = df_processed.groupby('paciente')['tipo'].nunique()
                    valid_patients = tipo_counts[tipo_counts >= 2].index
                    df_processed = df_processed[df_processed['paciente'].isin(valid_patients)].reset_index(drop=True)
                    st.success(f"✅ {len(valid_patients)} pacientes válidos")

                    # ETAPA 5.1 (v3.4): ORDENAÇÃO CRONOLÓGICA.
                    # Sem isso, os `groupby('paciente').first()` da Análise
                    # Exploratória devolviam o registro que estava primeiro no
                    # arquivo — nem o mais antigo, nem o mais recente.
                    # A ordenação vem DEPOIS da extração porque as funções de
                    # extração usam `df.loc[idx, ...]` com índice posicional.
                    if 'data_hora' in df_processed.columns:
                        df_processed = df_processed.sort_values(
                            ['paciente', 'data_hora']
                        ).reset_index(drop=True)
                    
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
                    
                    # ETAPA 9 (v3.4): HISTÓRICO MEDICAMENTOSO
                    # Percorre TODAS as consultas (do mais antigo ao mais
                    # recente) e monta "em uso de" / "fez uso de" por paciente.
                    df_historico = pd.DataFrame()
                    if selected_medications:
                        st.info("📜 Consolidando histórico medicamentoso...")
                        df_historico = consolidar_historico(
                            df_processed, selected_medications,
                            biologicos=selected_biologicos
                        )

                        if not df_historico.empty:
                            cols_hist = ['paciente', 'em_uso_de', 'fez_uso_de',
                                         'indeterminados', 'n_atuais', 'n_previos',
                                         'n_indeterminados', 'n_biologicos_atuais',
                                         'historico_medicamentoso']
                            cols_hist = [c for c in cols_hist if c in df_historico.columns]
                            df_longitudinal = df_longitudinal.merge(
                                df_historico[cols_hist], on='paciente', how='left'
                            )

                    # Salvar no session_state
                    st.session_state['df_historico'] = df_historico
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

        # v3.4: MOMENTO DE REFERÊNCIA EXPLÍCITO.
        # `df_processed` já vem ordenado por (paciente, data_hora), então
        # 'first' = primeira consulta e 'last' = consulta mais recente.
        momento_ref = st.radio(
            "🕐 Momento de referência para status de medicamentos:",
            ["Última consulta (situação mais atual)", "Primeira consulta (anamnese)"],
            horizontal=True, key='momento_exploratoria',
            help="Cada consulta gera sua própria classificação SIM/PRÉVIO. "
                 "Esta opção define qual delas representa o paciente."
        )
        agg_momento = 'last' if momento_ref.startswith('Última') else 'first'

        if 'data_hora' in df_analysis.columns:
            _dt = pd.to_datetime(df_analysis['data_hora'], errors='coerce')
            _ref = _dt.groupby(df_analysis['paciente']).max() if agg_momento == 'last' \
                else _dt.groupby(df_analysis['paciente']).min()
            _ref = _ref.dropna()
            if not _ref.empty:
                st.caption(
                    f"Status referente à **{momento_ref.lower()}** de cada paciente "
                    f"(mediana das datas de referência: {_ref.median():%m/%Y})."
                )

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
            
            # Conversão defensiva: garante idade numérica mesmo se o arquivo de
            # entrada trouxer texto ("45 anos", "N/I", vazio) na coluna.
            idade_num = None
            if 'idade' in df_analysis.columns:
                idade_num = pd.to_numeric(df_analysis['idade'], errors='coerce')

            with col1:
                if idade_num is not None:
                    if idade_num.notna().sum() == 0:
                        st.warning(
                            "⚠️ A coluna 'idade' não contém valores numéricos válidos. "
                            "Verifique o arquivo de origem."
                        )
                    else:
                        st.markdown("**Distribuição de Idades**")
                        fig = px.histogram(x=idade_num.dropna(), nbins=30,
                                           color_discrete_sequence=['#3b82f6'])
                        fig.update_layout(xaxis_title='Idade', yaxis_title='Frequência', height=400)
                        st.plotly_chart(fig, use_container_width=True)

                        col_a, col_b, col_c = st.columns(3)
                        col_a.metric("Média", f"{idade_num.mean():.1f}")
                        col_b.metric("Mediana", f"{idade_num.median():.0f}")
                        col_c.metric("Desvio Padrão", f"{idade_num.std():.1f}")
            
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
            
            if idade_num is not None and 'sexo' in df_analysis.columns and idade_num.notna().any():
                st.markdown("**Distribuição de Idade por Sexo**")
                df_idade_sexo = pd.DataFrame({
                    'idade': idade_num,
                    'sexo': df_analysis['sexo']
                }).dropna(subset=['idade'])
                fig = px.histogram(df_idade_sexo, x='idade', color='sexo', nbins=25,
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
                med_tabs = st.tabs(["📦 MTX", "🧬 Biológicos", "📊 Todos",
                                    "📜 Histórico por Paciente"])
                
                # MTX
                with med_tabs[0]:
                    if 'uso_mtx' in df_analysis.columns:
                        mtx_by_patient = df_analysis.groupby('paciente')['uso_mtx'].agg(agg_momento)
                        mtx_counts = mtx_by_patient.value_counts()
                        mtx_counts = mtx_counts.reindex(
                            [s for s in STATUS_ORDEM if s in mtx_counts.index]
                        )
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("**Status de Uso do MTX**")
                            fig = go.Figure(data=[go.Pie(
                                labels=mtx_counts.index,
                                values=mtx_counts.values,
                                marker=dict(colors=[STATUS_CORES.get(s, '#64748b')
                                                    for s in mtx_counts.index]),
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
                            if mtx_counts.get('INDETERMINADO', 0) > 0:
                                st.metric(
                                    "Indeterminado",
                                    f"{mtx_counts.get('INDETERMINADO', 0)} "
                                    f"({mtx_counts.get('INDETERMINADO', 0)/total*100:.1f}%)",
                                    help="Citado no prontuário sem expressão de status "
                                         "por perto. Requer revisão manual."
                                )
                        
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
                            'uso_biologico': agg_momento,
                            'biologico_nome': agg_momento,
                            'biologico_grupo': agg_momento
                        }).reset_index()
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("**Status de Uso de Biológicos**")
                            bio_counts = bio_by_patient['uso_biologico'].value_counts()
                            bio_counts = bio_counts.reindex(
                                [s for s in STATUS_ORDEM if s in bio_counts.index]
                            )
                            fig = go.Figure(data=[go.Pie(
                                labels=bio_counts.index,
                                values=bio_counts.values,
                                marker=dict(colors=[STATUS_CORES.get(s, '#64748b')
                                                    for s in bio_counts.index]),
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
    
                # v3.4: HISTÓRICO POR PACIENTE ("em uso de" / "fez uso de")
                with med_tabs[3]:
                    st.markdown("##### 📜 Histórico medicamentoso por paciente")
                    st.markdown(
                        "Reconstruído percorrendo **todas** as consultas, do registro "
                        "mais antigo ao mais recente. O status considerado atual é o "
                        "da última consulta em que o medicamento aparece."
                    )

                    df_hist = st.session_state.get('df_historico')

                    if df_hist is None or df_hist.empty:
                        st.info(
                            "Histórico não disponível. Reprocesse o ETL na aba "
                            "'Configurar ETL' para gerá-lo."
                        )
                    else:
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Pacientes com biológico/DMARD atual",
                                    int((df_hist['n_atuais'] > 0).sum()))
                        col2.metric("Pacientes com uso prévio",
                                    int((df_hist['n_previos'] > 0).sum()))
                        col3.metric("Com menção indeterminada",
                                    int((df_hist['n_indeterminados'] > 0).sum()),
                                    help="Medicamento citado sem expressão de status "
                                         "por perto — candidatos a revisão manual.")

                        if 'n_biologicos_atuais' in df_hist.columns:
                            n_simult = int((df_hist['n_biologicos_atuais'] > 1).sum())
                            if n_simult > 0:
                                st.warning(
                                    f"⚠️ {n_simult} paciente(s) aparecem com **2 ou mais "
                                    "biológicos em uso simultâneo**, o que é clinicamente "
                                    "improvável. Em geral o prontuário cita o biológico "
                                    "antigo sem registrar a suspensão. Filtre por eles "
                                    "abaixo e revise antes de usar os números."
                                )
                                if st.checkbox("Mostrar apenas esses pacientes",
                                               key='filtro_bio_simultaneo'):
                                    df_hist = df_hist[df_hist['n_biologicos_atuais'] > 1]

                        busca = st.text_input(
                            "🔎 Filtrar por paciente ou medicamento:",
                            key='busca_historico',
                            placeholder="ex.: tocilizumabe, suspenso por falha, 12345"
                        )

                        tabela = df_hist.copy()
                        if busca:
                            mask = tabela.astype(str).apply(
                                lambda c: c.str.contains(busca, case=False, na=False)
                            ).any(axis=1)
                            tabela = tabela[mask]
                            st.caption(f"{len(tabela)} paciente(s) encontrado(s).")

                        cols_show = ['paciente', 'em_uso_de', 'fez_uso_de',
                                     'indeterminados', 'n_previos']
                        cols_show = [c for c in cols_show if c in tabela.columns]

                        st.dataframe(
                            tabela[cols_show].rename(columns={
                                'paciente': 'Paciente',
                                'em_uso_de': 'Em uso de',
                                'fez_uso_de': 'Fez uso de',
                                'indeterminados': 'Citados sem contexto',
                                'n_previos': 'Nº prévios',
                            }),
                            use_container_width=True, hide_index=True, height=420
                        )

                        with st.expander("📄 Ver frases completas (uma por paciente)"):
                            for _, r in tabela.head(50).iterrows():
                                st.markdown(
                                    f"**{r['paciente']}** — {r['historico_medicamentoso']}"
                                )
                            if len(tabela) > 50:
                                st.caption(
                                    f"Mostrando 50 de {len(tabela)}. Use o filtro acima "
                                    "ou exporte na aba 'Exportar Dados'."
                                )

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
            idade_long = None
            if 'idade' in df_long.columns:
                idade_long = pd.to_numeric(df_long['idade'], errors='coerce')

            if idade_long is not None and idade_long.notna().any():
                df_long['faixa_etaria'] = pd.cut(idade_long,
                                                  bins=[0, 30, 40, 50, 60, 70, 120],
                                                  labels=['<30', '30-40', '40-50', '50-60', '60-70', '>70'])

                response_by_age = df_long.groupby('faixa_etaria', observed=True)['improvement'].agg(['sum', 'count'])
                response_by_age['taxa'] = (response_by_age['sum'] / response_by_age['count'] * 100)
                
                fig = px.bar(x=response_by_age.index.astype(str), y=response_by_age['taxa'],
                             color=response_by_age['taxa'], color_continuous_scale='Greens',
                             text=response_by_age['taxa'].round(1))
                fig.update_traces(texttemplate='%{text}%', textposition='outside')
                fig.update_layout(title="Taxa de Resposta por Faixa Etária",
                                  xaxis_title='Faixa Etária', yaxis_title='Taxa (%)', showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Dados de idade não disponíveis ou não numéricos")
        
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

                # v3.4: momento de referência explícito para as trocas relatadas
                tem_t1 = any(f'{m}_status_t1' in df_long.columns for m in biologicos)

                if tem_t1:
                    momento_troca = st.radio(
                        "🕐 Momento de referência:",
                        ["Anamnese (t0)", "Última evolução (t1)"],
                        horizontal=True, key='momento_trocas',
                        help="Até a v3.3 a análise de trocas usava sempre a anamnese, "
                             "sem dizer isso na tela."
                    )
                    sufixo_troca = '_t0' if momento_troca.startswith('Anamnese') else '_t1'
                else:
                    sufixo_troca = ''
                    st.caption("Momento de referência: anamnese (t0).")

                # --- SEÇÃO 1: VISÃO GERAL ---
                st.markdown("##### 📊 Visão Geral das Trocas")
                
                stats_troca = calcular_taxa_troca_geral(df_long, sufixo=sufixo_troca)
                
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
                        col_prev_troca = f'num_biologicos_previos{sufixo_troca}'
                        if col_prev_troca in df_long.columns:
                            _prev = pd.to_numeric(df_long[col_prev_troca], errors='coerce').fillna(0)
                            dist_trocas = _prev[_prev > 0].value_counts().sort_index()
                            
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
                
                matriz = construir_matriz_transicao(df_long, biologicos, sufixo=sufixo_troca)
                
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

                # --- SEÇÃO 2B (v3.4): TROCA OBSERVADA ENTRE t0 E t1 ---
                if tem_t1:
                    st.markdown("##### 🔁 Troca Observada no Seguimento (t0 → t1)")
                    st.markdown(
                        "*Aqui a troca é medida comparando o biológico em uso na "
                        "anamnese com o em uso na última evolução. A matriz acima "
                        "depende da troca ter sido **escrita** no mesmo registro; "
                        "esta não.*"
                    )

                    matriz_obs = construir_matriz_transicao_t0_t1(df_long, biologicos)

                    if matriz_obs.sum().sum() > 0:
                        fig = go.Figure(data=go.Heatmap(
                            z=matriz_obs.values,
                            x=matriz_obs.columns,
                            y=matriz_obs.index,
                            colorscale='Purples',
                            text=matriz_obs.values,
                            texttemplate='%{text}',
                            textfont={"size": 10},
                            hoverongaps=False
                        ))
                        fig.update_layout(
                            title="Troca observada entre anamnese e última evolução",
                            xaxis_title='Para (em uso em t1)',
                            yaxis_title='De (em uso em t0)',
                            height=500,
                        )
                        st.plotly_chart(fig, use_container_width=True)

                        total_obs = int(matriz_obs.values.sum())
                        st.info(
                            f"• {total_obs} paciente(s) com troca de biológico "
                            "observada entre os dois momentos."
                        )
                    else:
                        st.info(
                            "Nenhuma troca observada entre t0 e t1. Isso pode ser real "
                            "ou indicar que a evolução não registra o biológico em uso."
                        )

                    st.markdown("---")
                
                # --- SEÇÃO 3: TAXA DE ABANDONO ---
                st.markdown("##### 📉 Taxa de Abandono por Medicamento")
                
                df_taxas = calcular_taxa_abandono_por_medicamento(df_long, biologicos, sufixo=sufixo_troca)
                
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
                
                df_motivos = analisar_motivos_suspensao(df_long, biologicos, sufixo=sufixo_troca)
                
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
                
                df_seq = identificar_sequencias_comuns(df_long, biologicos, top_n=10, sufixo=sufixo_troca)
                
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
                
                stats_eficacia = analisar_eficacia_pos_troca(df_long, sufixo=sufixo_troca)
                
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
        
        # v3.4: histórico medicamentoso legível
        df_hist_exp = st.session_state.get('df_historico')
        if df_hist_exp is not None and not df_hist_exp.empty:
            st.markdown("---")
            st.markdown("#### 📜 Histórico Medicamentoso")
            st.info(f"Total de pacientes: {len(df_hist_exp)} "
                    "(colunas: em_uso_de, fez_uso_de, historico_medicamentoso)")

            col1, col2 = st.columns(2)

            with col1:
                output_hist = io.BytesIO()
                with pd.ExcelWriter(output_hist, engine='openpyxl') as writer:
                    df_hist_exp.to_excel(writer, index=False, sheet_name='Historico')

                st.download_button(
                    label="📥 Download Excel - Histórico Medicamentoso",
                    data=output_hist.getvalue(),
                    file_name=f"immuned_historico_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="btn_excel_hist"
                )

            with col2:
                st.download_button(
                    label="📥 Download CSV - Histórico Medicamentoso",
                    data=df_hist_exp.to_csv(index=False),
                    file_name=f"immuned_historico_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="btn_csv_hist"
                )

        st.markdown("---")
        st.markdown("#### 📋 Preview dos Dados")
        
        opcoes_preview = ["Dados Processados", "Dados Longitudinais"]
        if df_hist_exp is not None and not df_hist_exp.empty:
            opcoes_preview.append("Histórico Medicamentoso")

        preview_option = st.radio("Dataset:", opcoes_preview, horizontal=True)
        
        if preview_option == "Dados Processados":
            st.dataframe(st.session_state['df_processed'], use_container_width=True)
        elif preview_option == "Dados Longitudinais":
            if 'df_longitudinal' in st.session_state:
                st.dataframe(st.session_state['df_longitudinal'], use_container_width=True)
        else:
            st.dataframe(df_hist_exp, use_container_width=True)
        
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
            <p><strong>Immuned</strong> v3.4 | Sistema de Análise de Prontuários</p>
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
