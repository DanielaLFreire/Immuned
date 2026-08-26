# -*- coding: utf-8 -*-
"""Gera app_immuned_v35.py a partir de app_immuned_v34.py.

Correções (relatadas na revisão):
  1. NEGAÇÃO não era tratada (crítico) -> NEGACAO_PATTERN + USO_NEGADO_PATTERNS
     + fronteira de palavra em 'em uso'.
  2. Dedup só por 'descricao' -> ['paciente','tipo','data_hora','descricao'].
  3. Vários biológicos SIM no mesmo registro -> 'MÚLTIPLO' + lista completa.
  4. Exclusão de coorte AIJ (texto + CID M08), nível paciente.

O script é idempotente-por-verificação: cada substituição confere se o alvo
existe exatamente uma vez e falha ruidosamente se algo não bater.
"""
import io, sys

SRC = 'app_immuned_v34.py'
DST = 'app_immuned_v35.py'

with io.open(SRC, encoding='utf-8') as f:
    s = f.read()

edits = []  # (rotulo, old, new)

# --- 0. cabeçalho / changelog ------------------------------------------------
edits.append((
    'cabecalho versao',
    '"""\nIMMUNED - Sistema de Análise de Prontuários Médicos\nVersão 3.4\n',
    '"""\nIMMUNED - Sistema de Análise de Prontuários Médicos\nVersão 3.5\n\n'
    'Correções e novidades (v3.5):\n'
    '- 🔴 NEGAÇÃO NÃO ERA TRATADA: "não faz uso", "nega uso", "sem uso", "não\n'
    '  está em uso" eram classificados como uso ATIVO (SIM) — o oposto do que o\n'
    '  prontuário diz — inflando sistematicamente as taxas de uso atual. Agora há\n'
    '  NEGACAO_PATTERN + USO_NEGADO_PATTERNS: um marcador precedido de perto por\n'
    '  negação vira \'NÃO\' com prioridade máxima. Também foi posta fronteira de\n'
    '  palavra em \'em uso\' (antes casava dentro de "sem uso").\n'
    '- 🟠 DEDUP SÓ POR TEXTO: drop_duplicates(subset=[\'descricao\']) apagava\n'
    '  registros reais de pacientes diferentes com a mesma frase padronizada\n'
    '  ("Retorno em 3 meses."). Agora usa\n'
    '  [\'paciente\',\'tipo\',\'data_hora\',\'descricao\'].\n'
    '- 🟠 VÁRIOS BIOLÓGICOS \'SIM\' NO MESMO REGISTRO: o código fixava em silêncio\n'
    '  o primeiro da ordem de configuração. Agora marca \'MÚLTIPLO\' e guarda a\n'
    '  lista completa (biologicos_atuais_lista, num_biologicos_atuais).\n'
    '- ✨ EXCLUSÃO DE COORTE AIJ: pacientes com qualquer menção de Artrite\n'
    '  Idiopática Juvenil (texto ou CID-10 M08) são removidos inteiros da coorte\n'
    '  (checkbox "Filtros de coorte", ligado por padrão).\n',
))

# --- 1a. fronteira de palavra em 'em uso' ------------------------------------
edits.append((
    'em uso -> \\bem uso',
    "USO_ATIVO_PATTERNS = [\n    r'em\\s+uso', r'mant[e\u00e9]m',",
    "USO_ATIVO_PATTERNS = [\n    r'\\bem\\s+uso', r'mant[e\u00e9]m',",
))

# --- 1b. constantes de negação + STATUS_SCAN (antes da NOTA) -----------------
neg_block = (
    "# --- NEGA\u00c7\u00c3O (v3.5) ---------------------------------------------------------\n"
    "# Part\u00edcula de nega\u00e7\u00e3o imediatamente antes de um marcador de uso. Janela curta\n"
    "# (checada sobre os ~25 chars anteriores ao marcador), admitindo at\u00e9 2 palavras\n"
    "# entre a nega\u00e7\u00e3o e o marcador (\"n\u00e3o [ainda] faz uso\").\n"
    "NEGACAO_PATTERN = re.compile(\n"
    "    r'(?:\\bn[a\u00e3]o\\b|\\bnunca\\b|\\bjamais\\b|\\bnega(?:m|ndo|\u00e7[a\u00e3]o)?\\b|\\bsem\\b)'\n"
    "    r'\\s+(?:\\w+\\s+){0,2}$'\n"
    ")\n"
    "\n"
    "# Express\u00f5es explicitamente negativas (uso N\u00c3O ativo). Entram na competi\u00e7\u00e3o de\n"
    "# proximidade com prioridade m\u00e1xima (-1), vencendo SIM e PR\u00c9VIO em empate.\n"
    "USO_NEGADO_PATTERNS = [\n"
    "    r'n[a\u00e3]o\\s+faz\\s+uso', r'n[a\u00e3]o\\s+fazia\\s+uso',\n"
    "    r'n[a\u00e3]o\\s+usa\\b', r'n[a\u00e3]o\\s+utiliza',\n"
    "    r'n[a\u00e3]o\\s+est[a\u00e1]\\s+em\\s+uso', r'n[a\u00e3]o\\s+em\\s+uso',\n"
    "    r'nega\\s+uso', r'nega\\s+.{0,12}?\\buso\\b',\n"
    "    r'nunca\\s+(usou|utilizou|fez\\s+uso)',\n"
    "    r'\\bsem\\s+uso\\b',\n"
    "]\n"
    "\n"
    "# Ordem de varredura: N\u00c3O expl\u00edcito (-1) primeiro, depois PR\u00c9VIO (0), SIM (1).\n"
    "STATUS_SCAN = (\n"
    "    ('N\u00c3O', USO_NEGADO_PATTERNS, -1),\n"
    "    ('PR\u00c9VIO', USO_PREVIO_PATTERNS, 0),\n"
    "    ('SIM', USO_ATIVO_PATTERNS, 1),\n"
    ")\n"
    "\n"
)
edits.append((
    'insere constantes de negacao',
    "# NOTA: 'hepatotoxicidade' e 'alop\u00e9cia' sa\u00edram de USO_PREVIO_PATTERNS. Sozinhos",
    neg_block + "# NOTA: 'hepatotoxicidade' e 'alop\u00e9cia' sa\u00edram de USO_PREVIO_PATTERNS. Sozinhos",
))

# --- 1c. comentário do 'melhor' ---------------------------------------------
edits.append((
    'comentario melhor/prioridade',
    "    # melhor = (distancia, prioridade_empate, status, contexto)\n"
    "    # prioridade_empate: 0 = PR\u00c9VIO, 1 = SIM -> PR\u00c9VIO ganha empates\n"
    "    melhor = None",
    "    # melhor = (distancia, prioridade_empate, status, contexto)\n"
    "    # prioridade_empate: -1 = N\u00c3O (negado) < 0 = PR\u00c9VIO < 1 = SIM\n"
    "    # -> em empate de dist\u00e2ncia, N\u00c3O expl\u00edcito vence PR\u00c9VIO, que vence SIM.\n"
    "    melhor = None",
))

# --- 1d. laço de competição com negação -------------------------------------
edits.append((
    'laco de competicao de status',
    "        for status, padroes, prio in (('PR\u00c9VIO', USO_PREVIO_PATTERNS, 0),\n"
    "                                      ('SIM', USO_ATIVO_PATTERNS, 1)):\n"
    "            for padrao in padroes:\n"
    "                for k in re.finditer(padrao, contexto):\n"
    "                    # dist\u00e2ncia do marcador at\u00e9 a men\u00e7\u00e3o do medicamento\n"
    "                    if k.end() <= pos_med:\n"
    "                        dist = pos_med - k.end()\n"
    "                    elif k.start() >= pos_med:\n"
    "                        dist = k.start() - pos_med\n"
    "                    else:\n"
    "                        dist = 0\n"
    "                    candidato = (dist, prio, status, contexto)\n"
    "                    if melhor is None or candidato[:2] < melhor[:2]:\n"
    "                        melhor = candidato",
    "        for status, padroes, prio in STATUS_SCAN:\n"
    "            for padrao in padroes:\n"
    "                for k in re.finditer(padrao, contexto):\n"
    "                    eff_status, eff_prio = status, prio\n"
    "                    # v3.5: NEGA\u00c7\u00c3O. Marcador de uso (SIM/PR\u00c9VIO) precedido de\n"
    "                    # perto por part\u00edcula de nega\u00e7\u00e3o (\"n\u00e3o faz uso\", \"nega uso\",\n"
    "                    # \"sem uso\", \"nunca usou\") N\u00c3O \u00e9 uso: vira 'N\u00c3O' com\n"
    "                    # prioridade m\u00e1xima (vence empates de dist\u00e2ncia).\n"
    "                    if status != 'N\u00c3O':\n"
    "                        antes = contexto[max(0, k.start() - 25):k.start()]\n"
    "                        if NEGACAO_PATTERN.search(antes):\n"
    "                            eff_status, eff_prio = 'N\u00c3O', -1\n"
    "                    # dist\u00e2ncia do marcador at\u00e9 a men\u00e7\u00e3o do medicamento\n"
    "                    if k.end() <= pos_med:\n"
    "                        dist = pos_med - k.end()\n"
    "                    elif k.start() >= pos_med:\n"
    "                        dist = k.start() - pos_med\n"
    "                    else:\n"
    "                        dist = 0\n"
    "                    candidato = (dist, eff_prio, eff_status, contexto)\n"
    "                    if melhor is None or candidato[:2] < melhor[:2]:\n"
    "                        melhor = candidato",
))

# --- 2. AIJ: constantes + função (após CID_PATTERN) --------------------------
aij_block = (
    "\n\n"
    "# --- Exclus\u00e3o de coorte: Artrite Idiop\u00e1tica Juvenil (AIJ) (v3.5) -------------\n"
    "# AIJ (CID-10 M08) N\u00c3O \u00e9 Artrite Reumatoide do adulto. Pacientes com QUALQUER\n"
    "# men\u00e7\u00e3o de AIJ (texto ou CID) s\u00e3o removidos INTEIROS da coorte: um \u00fanico\n"
    "# registro identificando o diagn\u00f3stico basta para reclassificar o paciente.\n"
    "AIJ_CID_PATTERN = r'\\bm08\\.?\\d?\\b'\n"
    "AIJ_TEXTO_PATTERNS = [\n"
    "    r'artrite\\s+idiop[a\u00e1]tica\\s+juvenil',\n"
    "    r'artrite\\s+reumatoide\\s+juvenil',\n"
    "    r'artrite\\s+cr[o\u00f4]nica\\s+juvenil',\n"
    "    r'\\baij\\b', r'\\bacj\\b', r'\\barj\\b',\n"
    "]\n"
    "\n"
    "def registro_menciona_aij(text):\n"
    "    \"\"\"True se o registro menciona AIJ por texto OU CID-10 (M08.x).\"\"\"\n"
    "    if pd.isna(text):\n"
    "        return False\n"
    "    t = str(text).lower()\n"
    "    if re.search(AIJ_CID_PATTERN, t):\n"
    "        return True\n"
    "    return any(re.search(p, t) for p in AIJ_TEXTO_PATTERNS)\n"
)
edits.append((
    'insere deteccao de AIJ',
    "CID_PATTERN = r'CID[\\s\\-]*10?\\s*[:\\s]*([M]\\d{2}\\.?\\d?)'",
    "CID_PATTERN = r'CID[\\s\\-]*10?\\s*[:\\s]*([M]\\d{2}\\.?\\d?)'" + aij_block,
))

# --- 3. biológicos: MÚLTIPLO + colunas novas ---------------------------------
edits.append((
    'colunas novas em extract_biologicos_detalhado',
    "    df['num_biologicos_previos'] = 0\n"
    "    df['num_biologicos_indeterminados'] = 0\n",
    "    df['num_biologicos_previos'] = 0\n"
    "    df['num_biologicos_indeterminados'] = 0\n"
    "    df['num_biologicos_atuais'] = 0\n"
    "    df['biologicos_atuais_lista'] = None\n",
))
edits.append((
    'ramo biologicos_em_uso -> MULTIPLO',
    "        if biologicos_em_uso:\n"
    "            df.loc[idx, 'uso_biologico'] = 'SIM'\n"
    "            df.loc[idx, 'biologico_nome'] = biologicos_em_uso[0]['nome']\n"
    "            df.loc[idx, 'biologico_grupo'] = biologicos_em_uso[0]['grupo']\n"
    "        elif biologicos_previos:",
    "        n_atuais = len(biologicos_em_uso)\n"
    "        df.loc[idx, 'num_biologicos_atuais'] = n_atuais\n"
    "        if biologicos_em_uso:\n"
    "            nomes_atuais = [b['nome'] for b in biologicos_em_uso]\n"
    "            df.loc[idx, 'uso_biologico'] = 'SIM'\n"
    "            df.loc[idx, 'biologicos_atuais_lista'] = ', '.join(nomes_atuais)\n"
    "            if n_atuais == 1:\n"
    "                df.loc[idx, 'biologico_nome'] = biologicos_em_uso[0]['nome']\n"
    "                df.loc[idx, 'biologico_grupo'] = biologicos_em_uso[0]['grupo']\n"
    "            else:\n"
    "                # v3.5: 2+ biol\u00f3gicos com status SIM no MESMO registro. Antes o\n"
    "                # c\u00f3digo fixava em sil\u00eancio o primeiro da ordem de configura\u00e7\u00e3o.\n"
    "                # Agora marca 'M\u00daLTIPLO' para n\u00e3o mascarar o problema na an\u00e1lise\n"
    "                # por biol\u00f3gico espec\u00edfico (a lista completa fica em\n"
    "                # biologicos_atuais_lista).\n"
    "                df.loc[idx, 'biologico_nome'] = 'M\u00daLTIPLO'\n"
    "                df.loc[idx, 'biologico_grupo'] = 'M\u00daLTIPLO'\n"
    "        elif biologicos_previos:",
))

# --- 3b. propagar num_biologicos_atuais para t0/t1 ---------------------------
edits.append((
    'COLS_STATUS_EXTRA += num_biologicos_atuais',
    "    'num_biologicos_previos', 'num_biologicos_indeterminados',\n"
    "    'fr_resultado', 'fr_valor', 'fr_origem',",
    "    'num_biologicos_previos', 'num_biologicos_indeterminados',\n"
    "    'num_biologicos_atuais',\n"
    "    'fr_resultado', 'fr_valor', 'fr_origem',",
))

# --- 4a. dedup correto -------------------------------------------------------
edits.append((
    'dedup por paciente/tipo/data/descricao',
    "df_processed = df_processed.drop_duplicates(subset=['descricao']).reset_index(drop=True)",
    "df_processed = df_processed.drop_duplicates(\n"
    "                        subset=['paciente', 'tipo', 'data_hora', 'descricao']\n"
    "                    ).reset_index(drop=True)",
))

# --- 4b. checkbox de filtro de coorte ---------------------------------------
edits.append((
    'checkbox filtros de coorte',
    "        st.success(\"\u2705 Todas as colunas obrigat\u00f3rias presentes!\")\n"
    "        \n"
    "        # --- FATOR REUMATOIDE (NOVO) ---",
    "        st.success(\"\u2705 Todas as colunas obrigat\u00f3rias presentes!\")\n"
    "        \n"
    "        # --- FILTROS DE COORTE (v3.5) ---\n"
    "        st.markdown(\"#### \U0001f3af Filtros de coorte\")\n"
    "        excluir_aij = st.checkbox(\n"
    "            \"Excluir pacientes com AIJ (Artrite Idiop\u00e1tica Juvenil)\",\n"
    "            value=True,\n"
    "            help=\"AIJ (CID-10 M08) n\u00e3o \u00e9 Artrite Reumatoide do adulto. Se \"\n"
    "                 \"QUALQUER registro do paciente mencionar AIJ (texto ou CID), \"\n"
    "                 \"o paciente inteiro \u00e9 removido da coorte antes das an\u00e1lises.\"\n"
    "        )\n"
    "        \n"
    "        st.markdown(\"---\")\n"
    "        \n"
    "        # --- FATOR REUMATOIDE (NOVO) ---",
))

# --- 4c. etapa de exclusão no pipeline --------------------------------------
edits.append((
    'etapa exclusao AIJ no pipeline',
    "                    st.info(f\"\U0001f5d1\ufe0f Removidas {initial_len - len(df_processed)} duplicatas\")\n"
    "                    \n"
    "                    # ETAPA 0: Fator Reumatoide (NOVO)",
    "                    st.info(f\"\U0001f5d1\ufe0f Removidas {initial_len - len(df_processed)} duplicatas\")\n"
    "                    \n"
    "                    # ETAPA 0.5 (v3.5): EXCLUS\u00c3O DE AIJ (n\u00edvel PACIENTE).\n"
    "                    if excluir_aij:\n"
    "                        mask_aij = df_processed['descricao'].apply(registro_menciona_aij)\n"
    "                        pacientes_aij = sorted(df_processed.loc[mask_aij, 'paciente'].unique())\n"
    "                        if pacientes_aij:\n"
    "                            n_antes = df_processed['paciente'].nunique()\n"
    "                            df_processed = df_processed[\n"
    "                                ~df_processed['paciente'].isin(pacientes_aij)\n"
    "                            ].reset_index(drop=True)\n"
    "                            st.warning(\n"
    "                                f\"\U0001f6ab Exclu\u00eddos {len(pacientes_aij)} paciente(s) com \"\n"
    "                                f\"men\u00e7\u00e3o de AIJ (de {n_antes} pacientes).\"\n"
    "                            )\n"
    "                            with st.expander(\"Ver pacientes exclu\u00eddos por AIJ\"):\n"
    "                                st.write(pacientes_aij)\n"
    "                        else:\n"
    "                            st.info(\"\U0001f6ab Nenhum paciente com men\u00e7\u00e3o de AIJ encontrado.\")\n"
    "                    \n"
    "                    # ETAPA 0: Fator Reumatoide (NOVO)",
))

# aplica -----------------------------------------------------------------------
for rotulo, old, new in edits:
    n = s.count(old)
    if n != 1:
        print(f"ERRO em '{rotulo}': encontrei {n} ocorrencia(s) do alvo (esperava 1).")
        sys.exit(1)
    s = s.replace(old, new)
    print(f"  ok  | {rotulo}")

with io.open(DST, 'w', encoding='utf-8') as f:
    f.write(s)

print(f"\nGerado {DST} ({len(s)} chars).")
