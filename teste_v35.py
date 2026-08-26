# -*- coding: utf-8 -*-
"""Testa o nucleo de extracao da v3.4 sem precisar de streamlit/plotly."""
import sys
import types
import pandas as pd

# --- stubs minimos para importar o app sem streamlit/plotly ------------------
for nome in ('streamlit', 'plotly', 'plotly.graph_objects', 'plotly.express'):
    mod = types.ModuleType(nome)
    mod.__getattr__ = lambda a: (lambda *x, **k: None)
    sys.modules[nome] = mod

ns = {'__name__': 'app_v35'}
exec(compile(open('app_immuned_v35.py', encoding='utf-8').read(),
             'app_immuned_v35.py', 'exec'), ns)

extract_medicamento_status = ns['extract_medicamento_status']
extract_medicamentos_v3 = ns['extract_medicamentos_v3']
extract_biologicos_detalhado = ns['extract_biologicos_detalhado']
extract_comorbidades = ns['extract_comorbidades']
consolidar_historico = ns['consolidar_historico']
create_longitudinal_data = ns['create_longitudinal_data']
construir_matriz_transicao_t0_t1 = ns['construir_matriz_transicao_t0_t1']
registro_menciona_aij = ns['registro_menciona_aij']
EXTRACTION_OPTIONS = ns['EXTRACTION_OPTIONS']
BIO = ns['BIOLOGICOS_CONFIG']
DMARDS = ns['DMARDS_CONFIG']

falhas = []


def checa(rotulo, obtido, esperado):
    ok = obtido == esperado
    print(f"{'  OK  ' if ok else ' FALHA'} | {rotulo}: {obtido!r}"
          + ('' if ok else f'  (esperado {esperado!r})'))
    if not ok:
        falhas.append(rotulo)


print('=' * 78)
print('1. FALSOS POSITIVOS DE ALIAS CURTO')
print('=' * 78)

texto = "Paciente refere melhora. Mantida a conduta indicada na consulta anterior."
checa("'indicada' NAO deve virar adalimumabe",
      extract_medicamento_status(texto, 'adalimumabe', BIO['adalimumabe']['aliases'])['uso'],
      'NÃO')

texto = "Exame fisico: dor abaixo do joelho direito. Orientada dieta hipocalorica."
checa("'abaixo' NAO deve virar abatacepte",
      extract_medicamento_status(texto, 'abatacepte', BIO['abatacepte']['aliases'])['uso'],
      'NÃO')
checa("'dieta' NAO deve virar etanercepte",
      extract_medicamento_status(texto, 'etanercepte', BIO['etanercepte']['aliases'])['uso'],
      'NÃO')

texto = "Historico de cirurgia bariatrica em 2019."
checa("'bariatrica' NAO deve virar baricitinibe",
      extract_medicamento_status(texto, 'baricitinibe', BIO['baricitinibe']['aliases'])['uso'],
      'NÃO')

texto = "Em uso de ADA 40mg SC quinzenal."
checa("'ADA' isolado DEVE virar adalimumabe em uso",
      extract_medicamento_status(texto, 'adalimumabe', BIO['adalimumabe']['aliases'])['uso'],
      'SIM')

print()
print('=' * 78)
print('2. CONTAMINACAO DO "FEZ USO DE" (bug relatado)')
print('=' * 78)

texto = ("Fez uso de metotrexato 20mg/sem, suspenso por hepatotoxicidade. "
         "Atualmente em uso de tocilizumabe EV mensal, com boa resposta.")

checa("MTX = PREVIO",
      extract_medicamento_status(texto, 'metotrexato', DMARDS['metotrexato']['aliases'])['uso'],
      'PRÉVIO')
checa("MTX motivo = hepatotoxicidade",
      extract_medicamento_status(texto, 'metotrexato', DMARDS['metotrexato']['aliases'])['motivo_suspensao'],
      'hepatotoxicidade')
checa("Tocilizumabe = SIM (nao contaminado pelo 'fez uso')",
      extract_medicamento_status(texto, 'tocilizumabe', BIO['tocilizumabe']['aliases'])['uso'],
      'SIM')

texto2 = ("Previos: adalimumabe (falha terapeutica), etanercepte (intolerancia). "
          "Mantem tofacitinibe 5mg 12/12h.")
checa("Adalimumabe = PREVIO", extract_medicamento_status(texto2, 'adalimumabe', BIO['adalimumabe']['aliases'])['uso'], 'PRÉVIO')
checa("Etanercepte = PREVIO", extract_medicamento_status(texto2, 'etanercepte', BIO['etanercepte']['aliases'])['uso'], 'PRÉVIO')
checa("Tofacitinibe = SIM", extract_medicamento_status(texto2, 'tofacitinibe', BIO['tofacitinibe']['aliases'])['uso'], 'SIM')

texto3 = "Parou de fumar em 2020. Mantem leflunomida 20mg/dia."
checa("'parou de fumar' NAO torna leflunomida previa",
      extract_medicamento_status(texto3, 'leflunomida', DMARDS['leflunomida']['aliases'])['uso'],
      'SIM')

print()
print('=' * 78)
print('3. INDETERMINADO vs FALLBACK v3.3')
print('=' * 78)

texto4 = "AR soropositiva. Golimumabe. Retorno em 3 meses."
EXTRACTION_OPTIONS['fallback_sim'] = False
checa("mencao sem contexto -> INDETERMINADO (v3.4)",
      extract_medicamento_status(texto4, 'golimumabe', BIO['golimumabe']['aliases'])['uso'],
      'INDETERMINADO')
EXTRACTION_OPTIONS['fallback_sim'] = True
checa("mencao sem contexto -> SIM (compat v3.3)",
      extract_medicamento_status(texto4, 'golimumabe', BIO['golimumabe']['aliases'])['uso'],
      'SIM')
EXTRACTION_OPTIONS['fallback_sim'] = False

print()
print('=' * 78)
print('4. COMORBIDADES COM FRONTEIRA DE PALAVRA')
print('=' * 78)

df_c = pd.DataFrame({'descricao': [
    "Discutida a opcao cirurgica; sem outras comorbidades.",
    "Paciente com osteoporose em tratamento.",
]})
df_c = extract_comorbidades(df_c, ['op'])
checa("'opcao' NAO deve marcar osteoporose (op)", int(df_c.loc[0, 'op']), 0)
checa("'osteoporose' DEVE marcar op", int(df_c.loc[1, 'op']), 1)

print()
print('=' * 78)
print('5. HISTORICO CRONOLOGICO E BASE LONGITUDINAL t0/t1')
print('=' * 78)

df = pd.DataFrame({
    'paciente': ['P1'] * 3 + ['P2'] * 2,
    'tipo': ['ANAMNESE', 'EVOLUCAO', 'EVOLUCAO', 'ANAMNESE', 'EVOLUCAO'],
    'data_hora': pd.to_datetime([
        '2021-01-10', '2022-06-15', '2024-03-20',
        '2022-02-01', '2023-09-05']),
    'idade': [45, 46, 48, 60, 61],
    'sexo': ['F', 'F', 'F', 'M', 'M'],
    'das28': [5.8, 4.1, 2.9, 6.2, 5.9],
    'descricao': [
        # P1 t0: em uso de adalimumabe
        "AR soropositiva. Em uso de adalimumabe 40mg SC quinzenal. DAS28 5.8",
        # P1 meio: adalimumabe suspenso por falha, inicia tocilizumabe
        "Adalimumabe suspenso por falha terapeutica. Iniciado tocilizumabe. DAS28 4.1",
        # P1 t1: tocilizumabe mantido
        "Mantem tocilizumabe EV mensal. Fez uso de adalimumabe previamente. DAS28 2.9",
        # P2 t0: MTX em uso
        "Em uso de metotrexato 15mg/sem VO. DAS28 6.2",
        # P2 t1: MTX segue
        "Mantem metotrexato 15mg/sem. DAS28 5.9",
    ],
})

meds = ['adalimumabe', 'tocilizumabe', 'metotrexato']
df = extract_medicamentos_v3(df, meds)
df = extract_biologicos_detalhado(df, ['adalimumabe', 'tocilizumabe'])
df = df.sort_values(['paciente', 'data_hora']).reset_index(drop=True)

print('\n-- status por registro --')
print(df[['paciente', 'data_hora', 'tipo', 'adalimumabe_status',
          'tocilizumabe_status', 'metotrexato_status', 'uso_biologico']].to_string(index=False))

hist = consolidar_historico(df, meds)
print('\n-- historico consolidado --')
for _, r in hist.iterrows():
    print(f"  {r['paciente']}: {r['historico_medicamentoso']}")

p1 = hist[hist['paciente'] == 'P1'].iloc[0]
checa("P1 em uso de tocilizumabe", 'Tocilizumabe' in (p1['em_uso_de'] or ''), True)
checa("P1 fez uso de adalimumabe", 'Adalimumabe' in (p1['fez_uso_de'] or ''), True)
checa("P1 n_previos = 1", int(p1['n_previos']), 1)

long_df = create_longitudinal_data(df, 'ANAMNESE', 'EVOLUCAO', ['das28'])
print('\n-- base longitudinal (colunas de status) --')
cols = ['paciente', 'das28_t0', 'das28_t1',
        'adalimumabe_status_t0', 'adalimumabe_status_t1',
        'tocilizumabe_status_t0', 'tocilizumabe_status_t1',
        'uso_biologico', 'uso_biologico_t0', 'uso_biologico_t1']
cols = [c for c in cols if c in long_df.columns]
print(long_df[cols].to_string(index=False))

r1 = long_df[long_df['paciente'] == 'P1'].iloc[0]
checa("adalimumabe_status_t0 = SIM", r1['adalimumabe_status_t0'], 'SIM')
checa("adalimumabe_status_t1 = PREVIO", r1['adalimumabe_status_t1'], 'PRÉVIO')
checa("tocilizumabe_status_t1 = SIM", r1['tocilizumabe_status_t1'], 'SIM')
checa("coluna sem sufixo == t0 (compat v3.3)",
      r1['uso_biologico'], r1['uso_biologico_t0'])

matriz = construir_matriz_transicao_t0_t1(long_df, ['adalimumabe', 'tocilizumabe'])
checa("matriz t0->t1 detecta Adalimumabe -> Tocilizumabe",
      int(matriz.loc['Adalimumabe', 'Tocilizumabe']), 1)

print()
print('=' * 78)
print('6. NEGACAO (v3.5) - o bug critico')
print('=' * 78)

EXTRACTION_OPTIONS['fallback_sim'] = False

casos_neg = [
    ("Nao faz uso de adalimumabe por contraindicacao.",
     'adalimumabe', BIO, 'NÃO'),
    ("Nao esta em uso de tocilizumabe no momento.",
     'tocilizumabe', BIO, 'NÃO'),
    ("Sem uso de metotrexato ate o momento.",
     'metotrexato', DMARDS, 'NÃO'),
    ("Nega uso de adalimumabe. Em uso de tocilizumabe EV mensal.",
     'adalimumabe', BIO, 'NÃO'),
    # o mesmo texto: tocilizumabe segue SIM (negacao e local)
    ("Nega uso de adalimumabe. Em uso de tocilizumabe EV mensal.",
     'tocilizumabe', BIO, 'SIM'),
    # o mais traicoeiro: PREVIO de um, negado no outro
    ("Fez uso de MTX. Nao esta em uso de tocilizumabe.",
     'tocilizumabe', BIO, 'NÃO'),
    ("Nunca usou biologicos; nunca usou tofacitinibe.",
     'tofacitinibe', BIO, 'NÃO'),
]
for texto, med, cfg, esperado in casos_neg:
    checa(f"neg: {texto[:38]!r} -> {med}",
          extract_medicamento_status(texto, med, cfg[med]['aliases'])['uso'],
          esperado)

# regressao 1: negacao de OUTRA coisa nao pode negar um marcador distante
checa("'Nega tabagismo. Em uso de adalimumabe.' -> adalimumabe SIM",
      extract_medicamento_status("Nega tabagismo. Em uso de adalimumabe 40mg.",
                                 'adalimumabe', BIO['adalimumabe']['aliases'])['uso'],
      'SIM')
# regressao 2: uso ativo simples continua SIM
checa("'Em uso de tocilizumabe' -> SIM",
      extract_medicamento_status("Em uso de tocilizumabe EV mensal.",
                                 'tocilizumabe', BIO['tocilizumabe']['aliases'])['uso'],
      'SIM')

print()
print('=' * 78)
print('7. VARIOS BIOLOGICOS "SIM" NO MESMO REGISTRO -> MULTIPLO (v3.5)')
print('=' * 78)

df_m = pd.DataFrame({'descricao': [
    "Em uso de adalimumabe 40mg SC quinzenal e em uso de tocilizumabe EV mensal.",
    "Em uso de etanercepte 50mg SC semanal.",
]})
df_m = extract_biologicos_detalhado(df_m, ['adalimumabe', 'tocilizumabe', 'etanercepte'])

checa("2 biologicos SIM -> biologico_nome = MULTIPLO",
      df_m.loc[0, 'biologico_nome'], 'MÚLTIPLO')
checa("2 biologicos SIM -> num_biologicos_atuais = 2",
      int(df_m.loc[0, 'num_biologicos_atuais']), 2)
checa("lista guarda os dois nomes",
      ('adalimumabe' in (df_m.loc[0, 'biologicos_atuais_lista'] or '')
       and 'tocilizumabe' in (df_m.loc[0, 'biologicos_atuais_lista'] or '')), True)
checa("1 biologico SIM -> nome do proprio biologico",
      df_m.loc[1, 'biologico_nome'], 'etanercepte')
checa("1 biologico SIM -> num_biologicos_atuais = 1",
      int(df_m.loc[1, 'num_biologicos_atuais']), 1)

print()
print('=' * 78)
print('8. DETECCAO DE AIJ (texto + CID M08) (v3.5)')
print('=' * 78)

checa("texto 'artrite idiopatica juvenil' -> True",
      registro_menciona_aij("Diagnostico: artrite idiopatica juvenil, forma poliarticular."),
      True)
checa("CID 'M08.0' -> True",
      registro_menciona_aij("Retorno. CID M08.0. Mantida conduta."), True)
checa("sigla 'AIJ' isolada -> True",
      registro_menciona_aij("Paciente com AIJ desde a infancia."), True)
checa("AR do adulto (M06.0) -> False",
      registro_menciona_aij("Artrite reumatoide soronegativa. CID M06.0."), False)
checa("frase sem AIJ -> False",
      registro_menciona_aij("Em uso de metotrexato. Retorno em 3 meses."), False)

print()
print('=' * 78)
print('9. DEDUP POR PACIENTE (nao so por descricao) (v3.5)')
print('=' * 78)

df_d = pd.DataFrame({
    'paciente': ['P1', 'P2', 'P1'],
    'tipo': ['EVOLUCAO', 'EVOLUCAO', 'ANAMNESE'],
    'data_hora': pd.to_datetime(['2022-01-01', '2022-01-01', '2021-01-01']),
    'descricao': ['Retorno em 3 meses.', 'Retorno em 3 meses.', 'Anamnese inicial.'],
})
antes = len(df_d)
df_dd = df_d.drop_duplicates(
    subset=['paciente', 'tipo', 'data_hora', 'descricao']).reset_index(drop=True)
checa("frase identica de 2 pacientes NAO e apagada", len(df_dd), antes)
# e o comportamento antigo (so descricao) apagaria uma:
so_desc = df_d.drop_duplicates(subset=['descricao'])
checa("(controle) dedup so por descricao apagaria 1 registro real",
      len(so_desc), antes - 1)

print()
print('=' * 78)
if falhas:
    print(f'{len(falhas)} FALHA(S): ' + '; '.join(falhas))
    sys.exit(1)
print('TODOS OS TESTES PASSARAM')
