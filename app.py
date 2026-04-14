# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, timedelta
from supabase import create_client, Client
import io

# --- CONFIGURAÇÕES E CONEXÃO ---
URL = "https://qfvahrtockqxlvrhknkn.supabase.co"
KEY = "sb_publishable_NYv_kYobauOtW0lT3fWp6A_irgKBVGN"
supabase: Client = create_client(URL, KEY)

MESES_PT = {'January': 'Janeiro', 'February': 'Fevereiro', 'March': 'Março', 'April': 'Abril', 'May': 'Maio', 'June': 'Junho',
            'July': 'Julho', 'August': 'Agosto', 'September': 'Setembro', 'October': 'Outubro', 'November': 'Novembro', 'December': 'Dezembro'}
DIAS_PT = {'Monday': 'Segunda', 'Tuesday': 'Terça', 'Wednesday': 'Quarta', 'Thursday': 'Quinta', 'Friday': 'Sexta', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}

def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

# --- CSS PARA AUMENTAR FONTE DO APP ---
st.markdown("""
    <style>
    html, body, [class*="css"] {
        font-size: 22px !important;
    }
    .stDataFrame {
        font-size: 18px !important;
    }
    button {
        height: 4em !important;
        font-weight: bold !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- LÓGICA DE ESCALA ---
def membro_disponivel(id_membro, data_alvo):
    res = supabase.table("restricoes").select("*").eq("id_membro", id_membro).execute()
    for r in res.data:
        if r['tipo'] == 'dia' and data_alvo.strftime('%A') == r['valor']: return False
        if r['tipo'] == 'data_especifica' and data_alvo.strftime('%Y-%m-%d') == r['valor']: return False
    return True

def gerar_escala_logica(area, data_inicio, meses, dias_culto):
    pos_list = [p.strip() for p in area['posicoes'].split(",")]
    escala_data = []; data_atual = data_inicio; data_fim = data_inicio + timedelta(days=30 * meses)
    vinc = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute()
    ids = [v['id_membro'] for v in vinc.data]
    if not ids: return pd.DataFrame()
    membros = supabase.table("membros").select("*").in_("id", ids).order("total_servicos").execute().data
    
    while data_atual <= data_fim:
        if data_atual.strftime('%A') in dias_culto:
            m_en = data_atual.strftime('%B'); m_pt = MESES_PT.get(m_en, m_en)
            linha = {"Data": data_atual.strftime('%d/%m/%Y'), "Dia": DIAS_PT[data_atual.strftime('%A')], "_mes": f"{m_pt} / {data_atual.year}"}
            ids_hoje = []
            for p_nome in pos_list:
                linha[p_nome] = ""
                for idx, m in enumerate(membros):
                    if m['id'] not in ids_hoje and membro_disponivel(m['id'], data_atual):
                        linha[p_nome] = m['nome']; ids_hoje.append(m['id'])
                        membros.append(membros.pop(idx)); break
            escala_data.append(linha)
        data_atual += timedelta(days=1)
    return pd.DataFrame(escala_data)

# --- INTERFACE ---
def main():
    if 'logged_in' not in st.session_state:
        st.title("⛪ Acesso ao Sistema")
        u = st.text_input("Usuário"); p = st.text_input("Senha", type="password")
        if st.button("Entrar", use_container_width=True):
            res = supabase.table("usuarios").select("*").eq("login", u).eq("senha", hash_senha(p)).execute()
            if res.data: 
                st.session_state.update({'logged_in': True, 'user_id': res.data[0]['id'], 'user_login': res.data[0]['login']})
                st.rerun()
    else:
        res_areas = supabase.table("areas").select("*").eq("id_usuario", st.session_state['user_id']).execute().data
        area_n = st.sidebar.selectbox("🎯 Selecione a Escala", [a['nome_area'] for a in res_areas]) if res_areas else None
        area = next((a for a in res_areas if a['nome_area'] == area_n), None) if area_n else None

        aba = st.sidebar.radio("Navegação", ["📅 Rodízio", "📂 Histórico", "👥 Membros", "✈️ Afastamentos", "⚙️ Configurações"])
        
        if aba == "📅 Rodízio" and area:
            st.title(f"✍️ {area['nome_area']}")
            
            with st.expander("⚙️ Gerar Nova"):
                c1, c2, c3 = st.columns(3)
                m = c1.number_input("Meses", 1, 3, 1)
                d_i = c2.date_input("Início")
                d_c = c3.multiselect("Dias", list(DIAS_PT.keys()), default=["Sunday"], format_func=lambda x: DIAS_PT[x])
                if st.button("Gerar Tabela"):
                    st.session_state['df_edit'] = gerar_escala_logica(area, d_i, m, d_c)

            if 'df_edit' in st.session_state:
                st.subheader("📝 Edição dos Nomes")
                df_final = st.data_editor(st.session_state['df_edit'], use_container_width=True)
                
                if st.button("💾 SALVAR RODÍZIO", use_container_width=True):
                    supabase.table("escalas").insert({"id_area": area['id'], "nome_area": area['nome_area'], "dados_escala": df_final.to_json(orient='records')}).execute()
                    st.success("Salvo no banco de dados!")

                st.divider()
                st.subheader("📱 Texto para o WhatsApp (Copie abaixo)")
                
                # Gerador de Texto Formatado
                texto_completo = f"*RODÍZIO: {area['nome_area'].upper()}*\n\n"
                cargos = [c for c in df_final.columns if c not in ['_mes', 'Data', 'Dia']]
                
                for _, row in df_final.iterrows():
                    texto_dia = f"🗓 *{row['Data']} ({row['Dia']})*\n"
                    for cg in cargos:
                        texto_dia += f"▫️ *{cg}:* {row[cg]}\n"
                    st.code(texto_dia, language="text") # O st.code facilita o "Clique para copiar"
                    texto_completo += texto_dia + "\n"

        elif aba == "📂 Histórico" and area:
            st.header("📂 Histórico")
            h = supabase.table("escalas").select("*").eq("id_area", area['id']).order("data_geracao", desc=True).execute().data
            for e in h:
                if st.button(f"Escala de {e['data_geracao'][:16]}", key=e['id']):
                    st.session_state['df_edit'] = pd.read_json(io.StringIO(e['dados_escala']))
                    st.rerun()

        elif aba == "👥 Membros" and area:
            st.header("👥 Membros")
            with st.form("add"):
                n = st.text_input("Nome")
                if st.form_submit_button("Adicionar"):
                    res = supabase.table("membros").insert({"nome": n}).execute()
                    supabase.table("vinculos").insert({"id_membro": res.data[0]['id'], "id_area": area['id']}).execute()
                    st.rerun()
            
            vinc = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute().data
            ids = [v['id_membro'] for v in vinc]
            if ids:
                ms = supabase.table("membros").select("*").in_("id", ids).order("nome").execute().data
                for m in ms: st.write(f"• {m['nome']}")

        elif aba == "✈️ Afastamentos" and area:
            st.header("✈️ Bloqueios")
            vinc = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute().data
            ids = [v['id_membro'] for v in vinc]
            if ids:
                membros_l = supabase.table("membros").select("id, nome").in_("id", ids).execute().data
                with st.form("bloq"):
                    m_sel = st.selectbox("Irmã", [m['nome'] for m in membros_l])
                    d_b = st.date_input("Data")
                    if st.form_submit_button("Bloquear"):
                        mid = next(m['id'] for m in membros_l if m['nome'] == m_sel)
                        supabase.table("restricoes").insert({"id_membro": mid, "tipo": "data_especifica", "valor": d_b.strftime('%Y-%m-%d')}).execute()
                        st.success("Bloqueado!")

        elif aba == "⚙️ Configurações":
            st.header("⚙️ Configurações")
            with st.form("n_a"):
                n = st.text_input("Nome da Escala")
                p = st.text_input("Cargos (separados por vírgula)")
                if st.form_submit_button("Criar"):
                    supabase.table("areas").insert({"id_usuario": st.session_state['user_id'], "nome_area": n, "vagas": len(p.split(",")), "posicoes": p}).execute()
                    st.rerun()

if __name__ == "__main__":
    main()
