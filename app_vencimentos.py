import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import io
import re
import zipfile
from pathlib import Path

from historico_db import init_db, save_run, list_runs, get_run, excluir_run
from vencimentos_utils import (
    carregar_dados_vencimentos,
    comparar_bases,
    extrair_ano_vencimento,
    formatar_cpf_cnpj_brasileiro,
    gerar_excel_vencimentos_formatado,
    remover_duplicados_manter_mais_antiga,
)

# Configuração básica da página.
st.set_page_config(
    page_title="Acompanhamento: Comparação de Bases por Ano de Vencimento",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo visual do app.
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f4e79;
        text-align: center;
        padding: 1rem 0;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f4e79;
    }
    .stButton>button {
        width: 100%;
        background-color: #1f4e79;
        color: white;
        font-weight: bold;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
    }
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Cabeçalho principal.
st.markdown('<div class="main-header">📅 Acompanhamento: Comparação de Bases por Ano de Vencimento</div>', unsafe_allow_html=True)
st.markdown('<p style="text-align: center; color: #666; font-size: 1.1rem;">Compare duas bases e veja quantos autos saíram ou entraram por ano de vencimento</p>', unsafe_allow_html=True)

# Barra lateral com uploads e nomes de colunas.
with st.sidebar:
    st.image("https://via.placeholder.com/200x80/1f4e79/ffffff?text=ANTT", use_container_width=True)
    st.markdown("### 📁 Upload das Bases")
    
    st.markdown("#### Base antiga (período anterior)")
    arquivo_antiga = st.file_uploader(
        "Planilha base antiga",
        type=['xlsx', 'xls', 'csv'],
        key='arquivo_base_antiga'
    )
    
    st.markdown("#### Base nova (período atual)")
    arquivo_nova = st.file_uploader(
        "Planilha base nova",
        type=['xlsx', 'xls', 'csv'],
        key='arquivo_base_nova'
    )
    
    st.markdown("---")
    st.markdown("### ⚙️ Configurações")
    
    st.markdown("#### 🔑 Colunas Obrigatórias")
    # Esse campo precisa bater com o nome real da coluna nas duas bases.
    coluna_auto = st.text_input(
        "Nome da coluna Auto de Infração",
        value="Identificador do Débito",
        help="⚠️ OBRIGATÓRIO: Digite o nome exato da coluna que contém os Autos de Infração"
    )
    
    # A comparação depende da coluna de vencimento estar correta.
    coluna_vencimento = st.text_input(
        "Nome da coluna Vencimento",
        value="Data do Vencimento",
        help="⚠️ OBRIGATÓRIO: Digite o nome exato da coluna que contém as datas de vencimento"
    )
    
    st.markdown("---")
    st.markdown("#### 📋 Colunas Opcionais")
    # Protocolo é opcional, mas ajuda nas exportações.
    coluna_protocolo = st.text_input(
        "Nome da coluna Nº do Processo (Opcional)",
        value="Nº do Processo",
        help="Digite o nome exato da coluna que contém os números de protocolos (opcional)"
    )
    
    # Modal entra como informação complementar.
    coluna_modal = st.text_input(
        "Nome da coluna Subtipo de Débito (Opcional)",
        value="Subtipo de Débito",
        help="Digite o nome exato da coluna que contém os modais (opcional)"
    )
    
    # CPF/CNPJ é opcional e aparece quando a base trouxer esse dado.
    coluna_cpf_cnpj = st.text_input(
        "Nome da coluna CPF/CNPJ (Opcional)",
        value="CPF/CNPJ",
        help="Digite o nome exato da coluna que contém CPF/CNPJ (opcional)"
    )

# A parte de leitura, comparação e exportação ficou em `vencimentos_utils.py`.

# Carrega as duas bases antes de liberar a comparação.
df_antiga = None
df_nova = None
if arquivo_antiga:
    with st.spinner("Carregando base antiga..."):
        df_antiga = carregar_dados_vencimentos(arquivo_antiga)
if arquivo_nova:
    with st.spinner("Carregando base nova..."):
        df_nova = carregar_dados_vencimentos(arquivo_nova)

if df_antiga is not None and df_nova is not None:
    st.markdown("---")
    st.markdown("### 📋 Preview das bases")
    col_prev1, col_prev2 = st.columns(2)
    with col_prev1:
        st.markdown("**Base antiga**")
        st.dataframe(df_antiga.head(), use_container_width=True)
        st.caption(f"Total: {len(df_antiga):,} registros")
    with col_prev2:
        st.markdown("**Base nova**")
        st.dataframe(df_nova.head(), use_container_width=True)
        st.caption(f"Total: {len(df_nova):,} registros")
    st.markdown("---")

    # Se a coluna obrigatória não existir, o app para por aqui.
    ok_antiga = coluna_auto in df_antiga.columns and coluna_vencimento in df_antiga.columns
    ok_nova = coluna_auto in df_nova.columns and coluna_vencimento in df_nova.columns
    if not ok_antiga:
        st.error(f"⚠️ Na base antiga: verifique as colunas '{coluna_auto}' e '{coluna_vencimento}'.")
    if not ok_nova:
        st.error(f"⚠️ Na base nova: verifique as colunas '{coluna_auto}' e '{coluna_vencimento}'.")
    if ok_antiga and ok_nova:
        if st.button("🚀 Comparar bases (antiga x nova)", type="primary", use_container_width=True):
            with st.spinner("Comparando bases por ano de vencimento..."):
                try:
                    resultado = comparar_bases(df_antiga, df_nova, coluna_auto, coluna_vencimento)
                    st.session_state['comparacao_resultado'] = resultado
                    st.session_state['coluna_auto'] = coluna_auto
                    st.session_state['coluna_vencimento'] = coluna_vencimento
                    st.session_state['coluna_cpf_cnpj'] = coluna_cpf_cnpj
                    st.session_state['coluna_modal'] = coluna_modal
                    st.session_state['coluna_protocolo'] = coluna_protocolo
                    st.session_state['nome_base_antiga'] = arquivo_antiga.name
                    st.session_state['nome_base_nova'] = arquivo_nova.name
                    st.session_state['historico_run_id'] = None  # será preenchido ao exibir resultados
                    st.success("✅ Comparação concluída!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao comparar: {str(e)}")

# Exibe o resultado salvo em sessão.
if 'comparacao_resultado' in st.session_state:
    res = st.session_state['comparacao_resultado']
    comparacao_df = res['comparacao_df']
    autos_sairam_por_ano = res['autos_sairam_por_ano']
    autos_entraram_por_ano = res['autos_entraram_por_ano']
    df_antiga_com_ano = res['df_antiga_com_ano']
    df_nova_com_ano = res['df_nova_com_ano']
    stats_antiga_por_ano = res['stats_antiga_por_ano']
    stats_nova_por_ano = res['stats_nova_por_ano']
    anos_todos = res['anos_todos']
    coluna_auto = st.session_state['coluna_auto']
    coluna_vencimento = st.session_state['coluna_vencimento']
    coluna_cpf_cnpj = st.session_state.get('coluna_cpf_cnpj', '')
    coluna_modal = st.session_state.get('coluna_modal', '')
    coluna_protocolo = st.session_state.get('coluna_protocolo', '')

    st.markdown("---")
    st.markdown("## 📊 Acompanhamento: Comparação Base Antiga x Base Nova")

    if res.get('duplicados_antiga', 0) > 0 or res.get('duplicados_nova', 0) > 0:
        st.info(
            f"ℹ️ Base antiga: {res.get('duplicados_antiga', 0):,} duplicados removidos. "
            f"Base nova: {res.get('duplicados_nova', 0):,} duplicados removidos (mantida a data de vencimento mais antiga por auto)."
        )

    # Resumo rápido para o usuário bater o olho.
    total_sairam = comparacao_df['Sairam'].sum()
    total_entraram = comparacao_df['Entraram'].sum()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Anos comparados", len(anos_todos), "")
    with col2:
        st.metric("Total base antiga", f"{len(df_antiga_com_ano):,}", "")
    with col3:
        st.metric("Total base nova", f"{len(df_nova_com_ano):,}", "")
    with col4:
        st.metric("Sairam (total)", f"{total_sairam:,}", f"Entraram: {total_entraram:,}")

    # Tabela base da comparação.
    st.markdown("### 📋 Comparação por ano de vencimento")
    st.dataframe(comparacao_df, use_container_width=True, hide_index=True)

    # Os dois gráficos principais da tela.
    st.markdown("### 📈 Gráficos")
    col_a, col_b = st.columns(2)
    with col_a:
        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(name='Base antiga', x=comparacao_df['Ano'], y=comparacao_df['Qtd base antiga'], marker_color='#1f4e79'))
        fig_comp.add_trace(go.Bar(name='Base nova', x=comparacao_df['Ano'], y=comparacao_df['Qtd base nova'], marker_color='#2e7d32'))
        fig_comp.update_layout(barmode='group', title='Quantidade: Base antiga x Base nova por ano', height=400)
        st.plotly_chart(fig_comp, use_container_width=True)
    with col_b:
        fig_mov = go.Figure()
        fig_mov.add_trace(go.Bar(name='Sairam', x=comparacao_df['Ano'], y=comparacao_df['Sairam'], marker_color='#c62828'))
        fig_mov.add_trace(go.Bar(name='Entraram', x=comparacao_df['Ano'], y=comparacao_df['Entraram'], marker_color='#1565c0'))
        fig_mov.update_layout(barmode='group', title='Sairam x Entraram por ano', height=400)
        st.plotly_chart(fig_mov, use_container_width=True)

    # Prepara o material que vai para download e para o histórico.
    st.markdown("---")
    st.markdown("### 📥 Exportar")
    data_arquivo = datetime.now().strftime('%d %m %Y %H%M')

    # A tabela principal vai em um arquivo próprio.
    buf_comp = io.BytesIO()
    comparacao_df.to_excel(buf_comp, index=False, sheet_name='Comparacao')
    buf_comp.seek(0)
    excel_comparacao_bytes = buf_comp.getvalue()

    # Também separa os arquivos por ano porque essa costuma ser a consulta mais comum.
    excel_por_ano_dict = {}
    for ano in sorted(anos_todos, reverse=False):
        df_ano = stats_nova_por_ano[ano]['dataframe'].copy()
        colunas_export = {}
        colunas_export['IDENTIFICADOR DE DÉBITO'] = df_ano[coluna_auto].fillna('').astype(str).str.strip()
        if coluna_protocolo and coluna_protocolo in df_ano.columns:
            colunas_export['Nº DE PROCESSO'] = df_ano[coluna_protocolo].fillna('').astype(str).str.strip()
        if coluna_modal and coluna_modal in df_ano.columns:
            colunas_export['MODAL'] = df_ano[coluna_modal].fillna('').astype(str).str.strip()
        if coluna_cpf_cnpj and coluna_cpf_cnpj in df_ano.columns:
            colunas_export['CNPJ'] = df_ano[coluna_cpf_cnpj].fillna('').astype(str).str.strip().apply(formatar_cpf_cnpj_brasileiro)
        try:
            vencimento_dt = pd.to_datetime(df_ano[coluna_vencimento], errors='coerce', dayfirst=True)
            colunas_export['DATA DE VENCIMENTO'] = vencimento_dt.dt.strftime('%d/%m/%Y').fillna('')
        except Exception:
            colunas_export['DATA DE VENCIMENTO'] = df_ano[coluna_vencimento].fillna('').astype(str).str.strip()
        ordem_colunas = ['IDENTIFICADOR DE DÉBITO']
        if 'Nº DE PROCESSO' in colunas_export:
            ordem_colunas.append('Nº DE PROCESSO')
        if 'MODAL' in colunas_export:
            ordem_colunas.append('MODAL')
        if 'CNPJ' in colunas_export:
            ordem_colunas.append('CNPJ')
        ordem_colunas.append('DATA DE VENCIMENTO')
        dados_exportacao = pd.DataFrame({col: colunas_export[col] for col in ordem_colunas}, index=df_ano.index)
        dados_exportacao = dados_exportacao.dropna(how='all')
        if not dados_exportacao.empty:
            try:
                excel_por_ano_dict[ano] = gerar_excel_vencimentos_formatado(
                    dados_exportacao,
                    f'Autos_{ano}',
                    f'Autos Vencimento {ano}.xlsx'
                )
            except Exception:
                pass

    # A primeira vez que a comparação aparece na tela, ela já vai para o histórico.
    if st.session_state.get('historico_run_id') is None:
        try:
            config = {
                'coluna_auto': coluna_auto,
                'coluna_vencimento': coluna_vencimento,
                'coluna_protocolo': coluna_protocolo,
                'coluna_modal': coluna_modal,
                'coluna_cpf_cnpj': coluna_cpf_cnpj,
            }
            nome_antiga = st.session_state.get('nome_base_antiga') or 'base_antiga'
            nome_nova = st.session_state.get('nome_base_nova') or 'base_nova'
            run_id = save_run(
                res,
                nome_antiga,
                nome_nova,
                config,
                excel_comparacao_bytes,
                excel_por_ano_dict,
            )
            st.session_state['historico_run_id'] = run_id
            st.success("✅ Comparação salva no histórico. Você pode acessá-la na seção **Histórico de comparações** abaixo.")
        except Exception as e:
            st.warning(f"Não foi possível salvar no histórico: {e}")

    # Download da tabela principal.
    st.download_button(
        label="📥 Download tabela de comparação (Excel)",
        data=excel_comparacao_bytes,
        file_name=f"Comparacao_bases_{data_arquivo}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key="download_comparacao"
    )

    # Download separado por ano usando a base nova.
    st.markdown("#### 📥 Exportar por ano de vencimento (base nova)")
    st.info("💡 Baixe planilhas separadas por ano de vencimento. Cada arquivo contém todos os autos da base nova com vencimento naquele ano (do ano mais antigo ao mais novo).")
    num_colunas_export = min(3, len(anos_todos))
    cols_export = st.columns(num_colunas_export)
    for idx, ano in enumerate(sorted(anos_todos, reverse=False)):
        col_idx = idx % num_colunas_export
        with cols_export[col_idx]:
            st.markdown(f"##### 📅 Ano {ano}")
            qtd_autos = stats_nova_por_ano[ano]['quantidade']
            if ano in excel_por_ano_dict:
                st.download_button(
                    label=f"📥 Download Autos {ano}",
                    data=excel_por_ano_dict[ano],
                    file_name=f"Autos Vencimento {ano} {data_arquivo}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key=f"download_ano_{ano}",
                    help=f"Arquivo Excel com todos os autos de vencimento {ano} (base nova)"
                )
                st.caption(f"✅ {qtd_autos:,} autos")
            else:
                st.caption(f"📊 Ano {ano}: 0 autos")

    st.markdown("---")
    st.caption(f"📅 Data da comparação: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    st.caption(f"📊 Anos: {', '.join([str(a) for a in sorted(anos_todos)])}")

else:
    st.info("👆 Faça o upload da **base antiga** e da **base nova** na barra lateral e clique em **Comparar bases**.")
    
    with st.expander("ℹ️ Como usar o sistema"):
        st.markdown("""
        ### Instruções de Uso:
        
        1. **Upload das bases**: Na barra lateral, envie duas planilhas:
           - **Base antiga** (período anterior)
           - **Base nova** (período atual)
        2. **Configuração de colunas**: Informe os nomes exatos das colunas (valem para as duas bases):
           - ⚠️ **Coluna Auto de Infração** (OBRIGATÓRIA)
           - ⚠️ **Coluna Vencimento** (OBRIGATÓRIA)
           - Coluna Nº do Processo, Modal, CPF/CNPJ (Opcionais)
        3. **Comparar**: Clique em **Comparar bases (antiga x nova)**.
        4. **Resultados**: Veja por ano de vencimento:
           - **Qtd base antiga** e **Qtd base nova**
           - **Sairam**: autos que estavam na base antiga naquele ano e não estão na base nova
           - **Entraram**: autos que estão na base nova naquele ano e não estavam na base antiga
        5. **Exportar**: Baixe a tabela de comparação e, por ano de vencimento, um Excel com todos os autos da base nova (do ano mais antigo ao mais novo).
        
        ### Funcionalidades:
        - ✅ Comparação de duas bases por ano de vencimento
        - ✅ Tabela e gráficos: antiga x nova e saíram x entraram
        - ✅ Exportação por ano de vencimento (um arquivo por ano, base nova)
        - ✅ Formatação profissional das planilhas Excel
        - ✅ Histórico de comparações salvo em SQLite + pasta (veja abaixo)
        """)

# Histórico sempre visível no fim da página.
st.markdown("---")
st.markdown("## 📚 Histórico de comparações")
init_db()
runs = list_runs()
if not runs:
    st.info("Nenhuma comparação salva ainda. Após comparar duas bases, o resultado será salvo aqui automaticamente.")
else:
    for r in runs:
        with st.expander(
            f"🕐 {r['data_hora']} — **{r['nome_base_antiga']}** × **{r['nome_base_nova']}** "
            f"(antiga: {r['total_antiga']:,} | nova: {r['total_nova']:,} | saíram: {r['total_sairam']:,} | entraram: {r['total_entraram']:,})"
        ):
            run_full = get_run(r["id"])
            if not run_full:
                st.caption("Registro não encontrado.")
                continue
            st.markdown(f"**Base antiga:** {run_full['nome_base_antiga']} | **Base nova:** {run_full['nome_base_nova']}")
            st.dataframe(run_full["comparacao_df"], use_container_width=True, hide_index=True)
            col_a, col_b = st.columns(2)
            with col_a:
                # Junta tudo da execução em um único ZIP.
                if run_full.get("arquivos"):
                    buf_zip = io.BytesIO()
                    with zipfile.ZipFile(buf_zip, "w", zipfile.ZIP_DEFLATED) as zf:
                        for f in run_full["arquivos"]:
                            if f.is_file():
                                zf.write(str(f), f.name)
                    buf_zip.seek(0)
                    # O nome do ZIP usa o nome das bases, mas já limpo para Windows.
                    def nome_seguro(s):
                        if not s:
                            return "base"
                        n = Path(s).stem
                        n = re.sub(r'[<>:"/\\|?*]', "_", n).strip() or "base"
                        return n[:80]
                    nome_zip = f"{nome_seguro(run_full['nome_base_antiga'])} x {nome_seguro(run_full['nome_base_nova'])}.zip"
                    st.download_button(
                        label="📥 Baixar todos os arquivos (ZIP)",
                        data=buf_zip,
                        file_name=nome_zip,
                        mime="application/zip",
                        key=f"zip_{r['id']}",
                    )
            with col_b:
                if st.button("🗑️ Excluir deste histórico", key=f"del_{r['id']}"):
                    excluir_run(r["id"])
                    st.rerun()

