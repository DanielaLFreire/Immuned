# -*- coding: utf-8 -*-
"""
Módulo de Extração Otimizado - IMMUNED
Implementa regras de variáveis conforme documento de especificação
"""

import pandas as pd
import re
from typing import Dict, List, Tuple, Optional

# =============================================================================
# CONSTANTES E CONFIGURAÇÕES
# =============================================================================

# Padrões de Fator Reumatoide
FR_POSITIVO_PATTERNS = [
    r'\bfr\s*\+',
    r'\bfr\s*positivo',
    r'\bfr\s*reagente',
    r'\(fr\s*\+\)',
    r'fator\s+reumat[oó]ide\s*(positivo|reagente|\+)',
    r'soropositiv[ao]',
    r'ar\s*\(?\s*fr\s*\+\s*\)?',
    r'\bfr\s*[:\s]+\d+[\.,]?\d*\s*\(?positivo\)?',
]

FR_NEGATIVO_PATTERNS = [
    r'\bfr\s*-(?!\d)',  # FR - mas não FR -5 (número negativo)
    r'\bfr\s*negativo',
    r'\bfr\s*n[aã]o\s*reagente',
    r'\(fr\s*-\)',
    r'fator\s+reumat[oó]ide\s*(negativo|n[aã]o\s*reagente|-)',
    r'soronegativ[ao]',
    r'\bfr\s*[:\s]+\d+[\.,]?\d*\s*\(?(neg|negativo)\)?',
]

FR_VALOR_PATTERN = r'\bfr\s*[:\s]+(\d+[\.,]?\d*)'

# CID-10 para inferência de FR
CID_FR_MAPPING = {
    'M06.0': 'NEGATIVO',   # AR soronegativa
    'M05.9': 'POSITIVO',   # AR soropositiva
    'M05.0': 'POSITIVO',   # Síndrome de Felty
    'M05.1': 'POSITIVO',   # Doença reumatoide do pulmão
    'M05.2': 'POSITIVO',   # Vasculite reumatoide
    'M05.3': 'POSITIVO',   # AR com comprometimento de outros órgãos
    'M05.8': 'POSITIVO',   # Outras AR soropositivas
    'M06.8': 'NÃO INFORMADO',  # Outras AR especificadas
    'M06.9': 'NÃO INFORMADO',  # AR não especificada
}

CID_PATTERN = r'CID[\s\-]*10?\s*[:\s]*([M]\d{2}\.?\d?)'

# Biológicos e JAK inibidores
BIOLOGICOS = {
    # Anti-TNF
    'adalimumabe': ['adalimumabe', 'humira', 'ada'],
    'infliximabe': ['infliximabe', 'remicade', 'ifx'],
    'etanercepte': ['etanercepte', 'enbrel', 'eta'],
    'golimumabe': ['golimumabe', 'simponi', 'goli'],
    'certolizumabe': ['certolizumabe', 'cimzia', 'czp'],
    # Anti-IL/Outros biológicos
    'tocilizumabe': ['tocilizumabe', 'actemra', 'tcz'],
    'rituximabe': ['rituximabe', 'mabthera', 'rtx'],
    'abatacepte': ['abatacepte', 'orencia', 'aba'],
    # JAK inibidores (contabilizados como biológico)
    'tofacitinibe': ['tofacitinibe', 'xeljanz', 'tofa'],
    'upadacitinibe': ['upadacitinibe', 'rinvoq', 'upada'],
    'baricitinibe': ['baricitinibe', 'olumiant', 'bari'],
}

BIOLOGICOS_GRUPOS = {
    'anti_tnf': ['adalimumabe', 'infliximabe', 'etanercepte', 'golimumabe', 'certolizumabe'],
    'anti_il_outros': ['tocilizumabe', 'rituximabe', 'abatacepte'],
    'jak_inibidores': ['tofacitinibe', 'upadacitinibe', 'baricitinibe'],
}

# DMARDs convencionais
DMARDS = {
    'metotrexato': ['metotrexato', 'metotrexate', 'mtx'],
    'leflunomida': ['leflunomida', 'arava', 'lef'],
    'sulfassalazina': ['sulfassalazina', 'azulfin', 'ssz'],
    'hidroxicloroquina': ['hidroxicloroquina', 'plaquinol', 'hcq'],
}

# Padrões de status de uso
USO_ATIVO_PATTERNS = [
    r'em\s+uso',
    r'mant[eé]m',
    r'mantenho',
    r'renovo\s+lme',
    r'segue\s+com',
    r'continua\s+com',
    r'uso\s+atual',
    r'medicaç[oõ]es?\s+em\s+uso',
    r'usando',
]

USO_PREVIO_PATTERNS = [
    r'uso\s+pr[eé]vio',
    r'pr[eé]vio[s]?\s*[:\s]',
    r'fez\s+uso',
    r'j[aá]\s+usou',
    r'suspen[sd][oa]',
    r'parou',
    r'interromp',
    r'descontinua',
    r'n[aã]o\s+tolera',
    r'intoler[aâ]ncia',
    r'hepatotoxicidade',
    r'alop[eé]cia',
    r'falha\s+terap[eê]utica',
]

# Padrões de dose
DOSE_PATTERNS = {
    'mtx': r'(?:mtx|metotrexato)\s*[:\s]*(\d+[\.,]?\d*)\s*(?:mg)?(?:\s*/?\s*sem(?:ana)?)?',
    'biologico': r'(\d+[\.,]?\d*)\s*(?:mg|ml)',
}

# Motivos de suspensão comuns
MOTIVOS_SUSPENSAO = [
    'intolerância',
    'hepatotoxicidade', 
    'alopécia',
    'alopecia',
    'falha',
    'infecção',
    'efeito adverso',
    'evento adverso',
    'falta',
    'indisponibilidade',
]


# =============================================================================
# FUNÇÕES DE EXTRAÇÃO
# =============================================================================

def extract_fator_reumatoide(text: str) -> Dict:
    """
    Extrai informações sobre Fator Reumatoide (FR)
    
    Returns:
        Dict com: fr_resultado, fr_valor, fr_origem
    """
    if pd.isna(text):
        return {'fr_resultado': 'NÃO INFORMADO', 'fr_valor': None, 'fr_origem': None}
    
    text_lower = str(text).lower()
    result = {'fr_resultado': 'NÃO INFORMADO', 'fr_valor': None, 'fr_origem': None}
    
    # 1. Buscar padrões positivos
    for pattern in FR_POSITIVO_PATTERNS:
        if re.search(pattern, text_lower):
            result['fr_resultado'] = 'POSITIVO'
            result['fr_origem'] = 'TEXTO'
            break
    
    # 2. Buscar padrões negativos (se não encontrou positivo)
    if result['fr_resultado'] == 'NÃO INFORMADO':
        for pattern in FR_NEGATIVO_PATTERNS:
            if re.search(pattern, text_lower):
                result['fr_resultado'] = 'NEGATIVO'
                result['fr_origem'] = 'TEXTO'
                break
    
    # 3. Extrair valor numérico se disponível
    valor_match = re.search(FR_VALOR_PATTERN, text_lower)
    if valor_match:
        try:
            result['fr_valor'] = float(valor_match.group(1).replace(',', '.'))
            result['fr_origem'] = 'LAB'
        except:
            pass
    
    # 4. Inferir por CID-10 se ainda não informado
    if result['fr_resultado'] == 'NÃO INFORMADO':
        cid_match = re.search(CID_PATTERN, text, re.IGNORECASE)
        if cid_match:
            cid = cid_match.group(1).upper()
            # Normalizar CID (M060 -> M06.0)
            if '.' not in cid and len(cid) >= 4:
                cid = cid[:3] + '.' + cid[3:]
            if cid in CID_FR_MAPPING:
                result['fr_resultado'] = CID_FR_MAPPING[cid]
                result['fr_origem'] = 'CID'
    
    return result


def extract_medicamento_status(text: str, medicamento: str, aliases: List[str]) -> Dict:
    """
    Extrai status de uso de medicamento (SIM/PRÉVIO/NÃO)
    
    Returns:
        Dict com: uso, nome, dose, motivo_suspensao
    """
    if pd.isna(text):
        return {'uso': 'NÃO', 'nome': None, 'dose': None, 'motivo_suspensao': None}
    
    text_lower = str(text).lower()
    result = {'uso': 'NÃO', 'nome': None, 'dose': None, 'motivo_suspensao': None}
    
    # Verificar se o medicamento é mencionado
    med_found = False
    for alias in aliases:
        if alias.lower() in text_lower:
            med_found = True
            result['nome'] = medicamento
            break
    
    if not med_found:
        return result
    
    # Criar padrão para buscar contexto do medicamento
    alias_pattern = '|'.join([re.escape(a) for a in aliases])
    
    # Buscar contexto próximo ao medicamento (300 chars antes e depois)
    for alias in aliases:
        for match in re.finditer(re.escape(alias.lower()), text_lower):
            start = max(0, match.start() - 300)
            end = min(len(text_lower), match.end() + 300)
            context = text_lower[start:end]
            
            # Verificar uso prévio (tem prioridade se encontrar padrões de suspensão)
            for pattern in USO_PREVIO_PATTERNS:
                if re.search(pattern, context):
                    result['uso'] = 'PRÉVIO'
                    # Buscar motivo de suspensão
                    for motivo in MOTIVOS_SUSPENSAO:
                        if motivo in context:
                            result['motivo_suspensao'] = motivo
                            break
                    break
            
            # Verificar uso ativo (só se não encontrou prévio ou se encontrar padrão mais próximo)
            if result['uso'] != 'PRÉVIO':
                for pattern in USO_ATIVO_PATTERNS:
                    if re.search(pattern, context):
                        result['uso'] = 'SIM'
                        break
    
    # Se mencionou mas não identificou status, assumir que está em uso (menção atual)
    if result['uso'] == 'NÃO' and med_found:
        # Verificar se está em seção de "medicações em uso"
        if re.search(r'medica[çc][oõ]es?\s+em\s+uso.*?' + alias_pattern, text_lower, re.DOTALL):
            result['uso'] = 'SIM'
        else:
            result['uso'] = 'SIM'  # Default: se menciona, assume uso
    
    return result


def extract_mtx(text: str) -> Dict:
    """
    Extrai informações sobre Metotrexato
    
    Returns:
        Dict com: uso_mtx, mtx_dose_mg_semana, mtx_via, motivo_suspensao_mtx
    """
    base = extract_medicamento_status(text, 'metotrexato', DMARDS['metotrexato'])
    
    result = {
        'uso_mtx': base['uso'],
        'mtx_dose_mg_semana': None,
        'mtx_via': None,
        'motivo_suspensao_mtx': base['motivo_suspensao']
    }
    
    if pd.isna(text):
        return result
    
    text_lower = str(text).lower()
    
    # Extrair dose
    dose_match = re.search(DOSE_PATTERNS['mtx'], text_lower)
    if dose_match:
        try:
            result['mtx_dose_mg_semana'] = float(dose_match.group(1).replace(',', '.'))
        except:
            pass
    
    # Extrair via
    if re.search(r'mtx\s*(sc|subcutan[eê])', text_lower):
        result['mtx_via'] = 'SC'
    elif re.search(r'mtx\s*(vo|oral|comprimido)', text_lower):
        result['mtx_via'] = 'VO'
    elif re.search(r'mtx\s*(im|intramuscular)', text_lower):
        result['mtx_via'] = 'IM'
    
    return result


def extract_biologicos(text: str) -> Dict:
    """
    Extrai informações sobre uso de biológicos
    
    Returns:
        Dict com: uso_biologico, biologico_nome, biologico_grupo, 
                  biologico_plano, motivo_suspensao, lista_biologicos_previos
    """
    result = {
        'uso_biologico': 'NÃO',
        'biologico_nome': None,
        'biologico_grupo': None,
        'biologico_plano': 'NENHUM',
        'motivo_suspensao': None,
        'biologicos_previos': [],
        'biologicos_atuais': [],
    }
    
    if pd.isna(text):
        return result
    
    text_lower = str(text).lower()
    
    biologicos_em_uso = []
    biologicos_previos = []
    
    for med, aliases in BIOLOGICOS.items():
        status = extract_medicamento_status(text, med, aliases)
        
        if status['uso'] == 'SIM':
            biologicos_em_uso.append(med)
        elif status['uso'] == 'PRÉVIO':
            biologicos_previos.append({
                'nome': med, 
                'motivo': status['motivo_suspensao']
            })
    
    # Definir resultado final
    if biologicos_em_uso:
        result['uso_biologico'] = 'SIM'
        result['biologico_nome'] = biologicos_em_uso[0]  # Principal
        result['biologicos_atuais'] = biologicos_em_uso
        
        # Identificar grupo
        for grupo, meds in BIOLOGICOS_GRUPOS.items():
            if result['biologico_nome'] in meds:
                result['biologico_grupo'] = grupo
                break
    
    elif biologicos_previos:
        result['uso_biologico'] = 'PRÉVIO'
        result['biologico_nome'] = biologicos_previos[0]['nome']
        result['motivo_suspensao'] = biologicos_previos[0]['motivo']
    
    result['biologicos_previos'] = biologicos_previos
    
    # Verificar plano de troca
    if re.search(r'troc[oa]r?\s+\w+\s+por', text_lower):
        result['biologico_plano'] = 'TROCA'
    elif re.search(r'iniciar\s+(?:' + '|'.join(BIOLOGICOS.keys()) + ')', text_lower):
        result['biologico_plano'] = 'INICIAR'
    
    return result


def extract_comorbidades_avancado(text: str) -> Dict:
    """
    Extrai comorbidades com mais detalhes
    """
    comorbidades = {
        'has': {'aliases': ['has', 'hipertensão', 'hipertensao', 'hipertenso'], 'flag': 0},
        'dm': {'aliases': ['dm', 'dm2', 'diabetes', 'diabético', 'diabetico'], 'flag': 0},
        'pre_dm': {'aliases': ['pré-dm', 'pre-dm', 'pré-diabetes', 'pre-diabetes'], 'flag': 0},
        'dlp': {'aliases': ['dlp', 'dislipidemia', 'dislipidêmico'], 'flag': 0},
        'fm': {'aliases': ['fm', 'fibromialgia'], 'flag': 0},
        'op': {'aliases': ['op', 'osteoporose', 'osteoporótico'], 'flag': 0},
        'hipotireoidismo': {'aliases': ['hipotireoidismo', 'tireoidite', 'hipotireoideo'], 'flag': 0},
        'obesidade': {'aliases': ['obesidade', 'obeso', 'imc >'], 'flag': 0},
        'dpoc': {'aliases': ['dpoc', 'enfisema', 'bronquite crônica'], 'flag': 0},
        'irc': {'aliases': ['irc', 'doença renal', 'insuficiência renal'], 'flag': 0},
    }
    
    if pd.isna(text):
        return {k: 0 for k in comorbidades.keys()}
    
    text_lower = str(text).lower()
    result = {}
    
    for comorb, info in comorbidades.items():
        for alias in info['aliases']:
            if alias in text_lower:
                result[comorb] = 1
                break
        if comorb not in result:
            result[comorb] = 0
    
    # Flag geral
    result['tem_comorbidade'] = 1 if any(result.values()) else 0
    result['num_comorbidades'] = sum(v for k, v in result.items() if k not in ['tem_comorbidade', 'num_comorbidades'])
    
    return result


def extract_marcadores_clinicos(text: str) -> Dict:
    """
    Extrai marcadores clínicos com valores numéricos
    """
    marcadores = {
        'vhs': r'v[hs]s\s*[:\s=]*(\d+[\.,]?\d*)',
        'pcr': r'pcr\s*[:\s=]*(\d+[\.,]?\d*)',
        'haq': r'haq\s*[:\s=]*(\d+[\.,]?\d*)',
        'das28': r'das\s*-?\s*28\s*[:\s=]*(\d+[\.,]?\d*)',
        'cdai': r'cdai\s*[:\s=]*(\d+[\.,]?\d*)',
        'sdai': r'sdai\s*[:\s=]*(\d+[\.,]?\d*)',
        'basdai': r'basdai\s*[:\s=]*(\d+[\.,]?\d*)',
        'asdas': r'asdas\s*[:\s=]*(\d+[\.,]?\d*)',
        'eva_dor': r'eva\s*(?:dor)?\s*[:\s=]*(\d+[\.,]?\d*)',
        'nav': r'nav\s*[:\s=]*(\d+[\.,]?\d*)',
        'nad': r'nad\s*[:\s=]*(\d+[\.,]?\d*)',
    }
    
    result = {k: None for k in marcadores.keys()}
    
    if pd.isna(text):
        return result
    
    text_lower = str(text).lower()
    
    for marker, pattern in marcadores.items():
        match = re.search(pattern, text_lower)
        if match:
            try:
                result[marker] = float(match.group(1).replace(',', '.'))
            except:
                pass
    
    return result


# =============================================================================
# FUNÇÃO PRINCIPAL DE PROCESSAMENTO
# =============================================================================

def process_prontuario(row: pd.Series) -> Dict:
    """
    Processa uma linha do DataFrame extraindo todas as variáveis
    """
    text = row.get('descricao', '')
    
    # Extrair todas as informações
    fr_info = extract_fator_reumatoide(text)
    mtx_info = extract_mtx(text)
    bio_info = extract_biologicos(text)
    comorb_info = extract_comorbidades_avancado(text)
    marcadores = extract_marcadores_clinicos(text)
    
    # Combinar resultados
    result = {}
    result.update(fr_info)
    result.update(mtx_info)
    result.update(bio_info)
    result.update(comorb_info)
    result.update(marcadores)
    
    return result


def process_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Processa todo o DataFrame aplicando as extrações
    """
    # Aplicar processamento a cada linha
    extracted = df.apply(process_prontuario, axis=1)
    
    # Converter para DataFrame
    extracted_df = pd.DataFrame(extracted.tolist())
    
    # Concatenar com dados originais
    result = pd.concat([df.reset_index(drop=True), extracted_df], axis=1)
    
    return result


# =============================================================================
# TESTE DO MÓDULO
# =============================================================================

if __name__ == "__main__":
    # Teste com texto de exemplo
    texto_teste = """
    # AMBULATÓRIO DE REUMATOLOGIA - ARTRITE REUMATOIDE #
    CID10: M05.9
    
    FR: 120 (positivo)
    
    MEDICAÇÕES EM USO:
    Tofacitinibe 5mg 12/12h
    MTX 15mg/sem VO
    
    USO PRÉVIO: 
    Adalimumabe (suspenso por falha terapêutica)
    Infliximabe (hepatotoxicidade)
    
    COMORBIDADES:
    HAS
    DM2
    """
    
    # Criar DataFrame de teste
    test_df = pd.DataFrame({'descricao': [texto_teste]})
    
    # Processar
    result = process_dataframe(test_df)
    
    print("=== RESULTADO DO TESTE ===")
    for col in result.columns:
        if col != 'descricao':
            print(f"{col}: {result[col].iloc[0]}")
