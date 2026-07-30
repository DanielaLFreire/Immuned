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

ns = {'__name__': 'app_v34'}
exec(compile(open('app_immuned_v34.py', encoding='utf-8').read(),
             'app_immuned_v34.py', 'exec'), ns)

extract_medicamento_status = ns['extract_medicamento_status']
extract_medicamentos_v3 = ns['extract_medicamentos_v3']
extract_biologicos_detalhado = ns['extract_biologicos_detalhado']
extract_comorbidades = ns['extract_comorbidades']
consolidar_historico = ns['consolidar_historico']
create_longitudinal_data = ns['create_longitudinal_data']
construir_matriz_transicao_t0_t1 = ns['construir_matriz_transicao_t0_t1']
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
if falhas:
    print(f'{len(falhas)} FALHA(S): ' + '; '.join(falhas))
    sys.exit(1)
print('TODOS OS TESTES PASSARAM')
