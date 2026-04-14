# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, timedelta
from supabase import create_client, Client
from PIL import Image, ImageDraw, ImageFont
import io

# --- CONFIGURAÇÕES E CONEXÃO ---
URL = "https://qfvahrtockqxlvrhknkn.supabase.co"
KEY = "sb_publishable_NYv_kYobauOtW0lT3fWp6A_irgKBVGN"
supabase: Client = create_client(URL, KEY)

CORES_CARDS = ["#2E7D32", "#1565C0", "#6A1B9A", "#EF6C00", "#C62828", "#37474F"]

MESES_TRADUCAO = {
    'January': 'Janeiro', 'February': 'Fevereiro', 'March': 'Março',
    'April': 'Abril', 'May': 'Maio', 'June': 'Junho',
    'July': 'Julho', 'August': 'Agosto', 'September': 'Setembro',
    'October': 'Outubro', 'November': 'Novembro', 'December': 'Dezembro'
}
DIAS_TRADUCAO = {'Monday': 'Seg', 'Tuesday': 'Ter', 'Wednesday': 'Qua', 'Thursday': 'Qui', 'Friday': 'Sex', 'Saturday': 'Sáb', 'Sunday': 'Dom'}
DIAS_ORDEM = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

# --- IMAGEM WHATSAPP (FONTE GIGANTE) ---
def gerar_imagem_escala(df):
    if df.empty: return None
    df = df.astype(str)
    colunas_dados = [c for c in df.columns if c not in ['_mes', 'Data', 'Dia']]
    larg_total = 1200
    alt_total = (len(df) * (len(colunas_dados) * 120 + 150)) + 250
    img = Image.new('RGB', (larg_total, alt_total), color="#FFFFFF")
    draw = ImageDraw.Draw(img)
    try:
        f_titulo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 65)
        f_data = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 55)
        f_cargo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 45)
        f_nome = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 52)
    except:
        f_titulo = f_data = f_cargo = f_nome = ImageFont.load_default()

    draw.rectangle([0, 0, larg_total, 140], fill="#333333")
    txt_header = df['_mes'].iloc[0].upper() if '_mes' in df.columns else "RODÍZIO"
    w_h = draw.textlength(txt_header, font=f_titulo)
    draw.text(((larg_total-w_h)/2, 35), txt_header, fill="white", font=f_titulo)

    y = 190
    for _, row in df.iterrows():
        draw.rectangle([40, y, larg_total-40, y+85], fill="#E0E0E0")
        txt_d = f"{row['Data']} - {row['Dia'].upper()}"
        draw.text((60, y+12), txt_d, fill="black", font=f_data)
        y += 120
        for idx, col in enumerate(colunas_dados):
            cor = CORES_CARDS[idx % len(CORES_CARDS)]
            draw.rectangle([60, y, larg_total-60, y+110], outline=cor, width=4)
            draw.rectangle([60, y, 280, y+110], fill=cor)
            draw.text((75, y+30), col.upper()[:12], fill="white", font=f_cargo)
            draw.text((310, y+25), str(row[col]), fill="black", font=f_nome)
            y += 125
        y += 80
    buf = io.BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()

def membro_disponivel(id_membro, data_alvo):
    res = supabase.table("restricoes").select("*").eq("id_membro", id_membro).execute()
    for r in res.data:
        if r['tipo'] == 'dia' and data_alvo.strftime('%A') == r['valor']: return False
        if r['tipo'] == 'regra' and r['valor'] == '3_sabado':
            if 15 <= data_alvo.day <= 21 and data_alvo.strftime('%A') == 'Saturday': return False
        if r['tipo'] == 'data_especifica' and data_alvo.strftime('%Y-%m-%d') == r['valor']: return False
    return True

def gerar_escala_logica(area, data_inicio, meses, dias_culto):
    vagas = int(area['vagas']); pos_list = [p.strip() for p in area['posicoes'].split(",")]
    escala_data = []; data_atual = data_inicio; data_fim = data_inicio + timedelta(days=30 * meses)
    vinc = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute()
    ids = [v['id_membro'] for v in vinc.data]
    if not ids: return pd.DataFrame()
    membros = supabase.table("membros").select("*").in_("id", ids).order("total_servicos").order("ultimo_servico").execute().data
    
    while data_atual <= data_fim:
        dia_s = data_atual.strftime('%A')
        if dia_s in dias_culto:
            m_en = data_atual.strftime('%B'); m_pt = MESES_TRADUCAO.get(m_en, m_en)
            linha = {"Data": data_atual.strftime('%d/%m/%Y'), "Dia": DIAS_TRADUCAO[dia_s], "_mes": f"{m_pt} / {data_atual.year}"}
            ids_hoje = []
            for i in range(vagas):
                p_nome = pos_list[i] if i < len(pos_list) else f"Vaga {i+1}"
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
    st.set_page_config(page_title="CCB Escala", layout="wide")
    
    if 'logged_in' not in st.session_state:
        st.title("⛪ Acesso ao Sistema")
        u = st.text_input("Usuário"); p = st.text_input("Senha", type="password")
        if st.button("Entrar", use_container_width=True):
            res = supabase.table("usuarios").select("*").eq("login", u).eq("senha", hash_senha(p)).execute()
            if res.data: 
                st.session_state['logged_in'] = True
                st.session_state['user_id'] = res.data[0]['id']
                st.session_state['user_login'] = res.data[0]['login']
                st.rerun()
            else: st.error("Login ou senha incorretos.")
    else:
        # Sidebar e Busca de Áreas
        res_areas = supabase.table("areas").select("*").eq("id_usuario", st.session_state['user_id']).execute().data
        area_nome = st.sidebar.selectbox("🎯 Escala Ativa", [a['nome_area'] for a in res_areas], key="sel_area_sidebar") if res_areas else None
        area = next((a for a in res_areas if a['nome_area'] == area_nome), None) if area_nome else None

        aba = st.sidebar.radio("Navegação", ["📅 Gerar & Editar", "📂 Histórico", "👥 Membros", "✈️ Afastamentos", "⚙️ Configurações"])
        st.sidebar.divider()
        
        # Correção do KeyError aqui:
        login_display = st.session_state.get('user_login', 'Usuário')
        st.sidebar.write(f"Logado como: **{login_display}**")
        
        if st.sidebar.button("Sair"): st.session_state.clear(); st.rerun()

        if aba == "📅 Gerar & Editar":
            if not area: st.warning("Crie uma escala na aba 'Configurações' primeiro."); return
            
            st.title(f"✍️ Rodízio: {area['nome_area']}")
            c1, c2, c3, c4 = st.columns([1,1,1,1])
            m = c1.number_input("Meses", 1, 6, 1)
            d_i = c2.date_input("Início")
            d_c = c3.multiselect("Dias", DIAS_ORDEM, default=["Sunday"], format_func=lambda x: DIAS_TRADUCAO[x])
            if c4.button("⚡ Gerar Novo", use_container_width=True):
                st.session_state['df_edit'] = gerar_escala_logica(area, d_i, m, d_c)

            if 'df_edit' in st.session_state:
                with st.expander("📝 Editar Tabela Manualmente"):
                    df_final = st.data_editor(st.session_state['df_edit'], num_rows="dynamic", use_container_width=True)
                    if st.button("💾 Salvar Rodízio"):
                        supabase.table("escalas").insert({"id_area": area['id'], "nome_area": area['nome_area'], "dados_escala": df_final.to_json(orient='records')}).execute()
                        st.success("Rodízio salvo!")

                st.subheader("👀 Visualização do Mural")
                v_cols = [c for c in df_final.columns if c not in ['_mes', 'Data', 'Dia']]
                for _, row in df_final.iterrows():
                    st.markdown(f"### 🗓️ {row['Data']} - {row['Dia']}")
                    cols = st.columns(len(v_cols))
                    for i, cargo in enumerate(v_cols):
                        cor = CORES_CARDS[i % len(CORES_CARDS)]
                        with cols[i]:
                            st.markdown(f"""<div style="background-color: {cor}; padding: 25px; border-radius: 12px; color: white; text-align: center;">
                                <small style="text-transform: uppercase; font-weight: bold; opacity: 0.9;">{cargo}</small><br>
                                <strong style="font-size: 28px;">{row[cargo]}</strong></div>""", unsafe_allow_html=True)
                    st.write("")

        elif aba == "📂 Histórico" and area:
            st.header("📂 Escalas Salvas")
            h = supabase.table("escalas").select("*").eq("id_area", area['id']).order("data_geracao", desc=True).execute().data
            for e in h:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2,1,1])
                    c1.write(f"📅 **{e['data_geracao'][:16]}**")
                    df_h = pd.read_json(io.StringIO(e['dados_escala']))
                    if c2.button("👁️ Abrir", key=f"op_{e['id']}"): st.session_state['df_edit'] = df_h; st.rerun()
                    img = gerar_imagem_escala(df_h)
                    c3.download_button("📸 Baixar", img, f"escala_{e['id']}.png", "image/png", key=f"dl_{e['id']}")

        elif aba == "👥 Membros" and area:
            st.header("👥 Gestão de Membros")
            with st.expander("➕ Novo Membro"):
                with st.form("add"):
                    n = st.text_input("Nome"); s = st.number_input("Serviços", 0)
                    if st.form_submit_button("Cadastrar"):
                        res = supabase.table("membros").insert({"nome": n, "total_servicos": s}).execute()
                        if res.data:
                            supabase.table("vinculos").insert({"id_membro": res.data[0]['id'], "id_area": area['id']}).execute()
                            st.rerun()

            vinc = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute().data
            ids = [x['id_membro'] for x in vinc]
            if ids:
                ms = supabase.table("membros").select("*").in_("id", ids).order("nome").execute().data
                for m in ms:
                    with st.container(border=True):
                        c1, c2 = st.columns([4, 1])
                        c1.subheader(m['nome'])
                        if c2.button("⚙️ Config", key=f"ed_{m['id']}"): st.session_state[f"f_{m['id']}"] = not st.session_state.get(f"f_{m['id']}", False)
                        if st.session_state.get(f"f_{m['id']}"):
                            with st.form(f"frm_{m['id']}"):
                                n_n = st.text_input("Nome", m['nome'])
                                n_s = st.number_input("Serviços", value=m['total_servicos'])
                                if st.form_submit_button("Salvar"):
                                    supabase.table("membros").update({"nome": n_n, "total_servicos": n_s}).eq("id", m['id']).execute(); st.rerun()

        elif aba == "✈️ Afastamentos" and area:
            st.header("✈️ Bloqueio de Datas")
            vinc = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute().data
            ids = [v['id_membro'] for v in vinc]
            if ids:
                membros_lista = supabase.table("membros").select("id, nome").in_("id", ids).execute().data
                with st.form("afast"):
                    m_sel = st.selectbox("Irmão/Irmã", [m['nome'] for m in membros_lista])
                    d1 = st.date_input("Início"); d2 = st.date_input("Fim")
                    if st.form_submit_button("Bloquear"):
                        mid = next(m['id'] for m in membros_lista if m['nome'] == m_sel)
                        curr = d1
                        while curr <= d2:
                            supabase.table("restricoes").insert({"id_membro": mid, "tipo": "data_especifica", "valor": curr.strftime('%Y-%m-%d')}).execute()
                            curr += timedelta(days=1)
                        st.success("Bloqueado!"); st.rerun()

        elif aba == "⚙️ Configurações":
            tab1, tab2 = st.tabs(["🏗️ Áreas/Cargos", "🔐 Usuários"])
            with tab1:
                st.subheader("Configurar Novo Rodízio")
                with st.form("area_f"):
                    n = st.text_input("Nome (Ex: Organistas Manhã)")
                    v = st.number_input("Vagas", 1, 10, 2)
                    p = st.text_input("Posições (Separadas por vírgula)")
                    if st.form_submit_button("Criar"):
                        supabase.table("areas").insert({"id_usuario": st.session_state['user_id'], "nome_area": n, "vagas": v, "posicoes": p}).execute()
                        st.rerun()
            with tab2:
                st.subheader("Criar Acesso")
                with st.form("user_f"):
                    new_u = st.text_input("Login")
                    new_p = st.text_input("Senha", type="password")
                    if st.form_submit_button("Cadastrar"):
                        supabase.table("usuarios").insert({"login": new_u, "senha": hash_senha(new_p)}).execute()
                        st.success("Usuário criado!")

if __name__ == "__main__":
    main()
