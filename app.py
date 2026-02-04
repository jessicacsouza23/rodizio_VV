import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, timedelta
from supabase import create_client, Client
from PIL import Image, ImageDraw, ImageFont
import io

# --- CONEXÃO SUPABASE (Utilizando suas chaves) ---
URL = "https://vjqkmomxlqwhthxkkfmp.supabase.co"
KEY = "sb_publishable_3LhpzB7wNPY7WpgKWP_BqA_5eJ5Xik-"
supabase: Client = create_client(URL, KEY)

# --- CONFIGURAÇÕES GLOBAIS ---
DIAS_TRADUCAO = {'Monday': 'Seg', 'Tuesday': 'Ter', 'Wednesday': 'Qua', 'Thursday': 'Qui', 'Friday': 'Sex', 'Saturday': 'Sáb', 'Sunday': 'Dom'}
DIAS_ORDEM = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

# --- FUNÇÃO DE GERAÇÃO DE IMAGEM ---
def gerar_imagem_escala(df):
    if df.empty: return None
    meses_ref = df['_mes'].values
    df_v = df.drop(columns=['_mes'])
    colunas = df_v.columns.tolist()
    
    larg_col = 220
    larg_total = 40 + (len(colunas) * larg_col)
    alt_total = (len(df) * 45) + 300
    
    img = Image.new('RGB', (larg_total, alt_total), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        f_h = ImageFont.truetype("arial.ttf", 18)
        f_t = ImageFont.truetype("arial.ttf", 16)
        f_m = ImageFont.truetype("arial.ttf", 20)
    except:
        f_h = f_t = f_m = ImageFont.load_default()
        
    y, mes_at = 30, ""
    for i, row in df_v.iterrows():
        if meses_ref[i] != mes_at:
            mes_at = meses_ref[i]
            y += 20
            draw.rectangle([0, y, larg_total, y+40], fill=(230, 230, 230))
            txt = f"MÊS DE {mes_at.upper()}"; w = draw.textlength(txt, font=f_m)
            draw.text(((larg_total-w)/2, y+8), txt, fill="black", font=f_m)
            y += 50
            draw.rectangle([0, y, larg_total, y+35], fill=(50, 50, 50))
            for idx, col in enumerate(colunas):
                txt_c = col.upper(); w_c = draw.textlength(txt_c, font=f_h)
                draw.text(((idx*larg_col)+(larg_col-w_c)/2, y+7), txt_c, fill="white", font=f_h)
            y += 45
        if i % 2 == 0: draw.rectangle([0, y-5, larg_total, y+30], fill=(248, 248, 248))
        for idx, col in enumerate(colunas):
            txt_v = str(row[col]); w_v = draw.textlength(txt_v, font=f_t)
            draw.text(((idx*larg_col)+(larg_col-w_v)/2, y), txt_v, fill="black", font=f_t)
        y += 40
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- LÓGICA DE DISPONIBILIDADE ---
def membro_disponivel(id_membro, nome_membro, data_alvo):
    data_str = data_alvo.strftime('%Y-%m-%d')
    # Verifica se já trabalhou no dia
    ja = supabase.table("membros").select("id").eq("nome", nome_membro).eq("ultimo_servico", data_str).execute()
    if ja.data: return False
    
    res = supabase.table("restricoes").select("*").eq("id_membro", id_membro).execute()
    for r in res.data:
        if r['tipo'] == 'dia' and data_alvo.strftime('%A') == r['valor']: return False
        if r['tipo'] == 'regra' and r['valor'] == '3_sabado' and (15 <= data_alvo.day <= 21 and data_alvo.strftime('%A') == 'Saturday'): return False
        if r['tipo'] == 'data_especifica' and data_str == r['valor']: return False
    return True

# --- MOTOR DE ESCALA ---
def gerar_escala_logica(area, data_inicio, meses, dias_culto):
    vagas = int(area['vagas'])
    pos_list = [p.strip() for p in area['posicoes'].split(",")]
    escala_data = []
    data_atual = data_inicio
    data_fim = data_inicio + timedelta(days=30 * meses)

    while data_atual <= data_fim:
        dia_s = data_atual.strftime('%A')
        if dia_s in dias_culto:
            vinc = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute()
            ids = [v['id_membro'] for v in vinc.data]
            membros = supabase.table("membros").select("*").in_("id", ids).order("ultimo_servico").order("id").execute()
            
            linha = {"Data": data_atual.strftime('%d/%m/%Y'), "Dia": DIAS_TRADUCAO[dia_s], "_mes": data_atual.strftime('%B / %Y')}
            v_p = 0
            for p in membros.data:
                if v_p == vagas: break
                if membro_disponivel(p['id'], p['nome'], data_atual):
                    pos = pos_list[v_p] if v_p < len(pos_list) else f"Vaga {v_p+1}"
                    linha[pos] = p['nome']
                    supabase.table("membros").update({"ultimo_servico": data_atual.strftime('%Y-%m-%d')}).eq("id", p['id']).execute()
                    v_p += 1
            escala_data.append(linha)
        data_atual += timedelta(days=1)
    return pd.DataFrame(escala_data)

# --- INTERFACE PRINCIPAL ---
def main():
    st.set_page_config(page_title="CCB Escala Nuvem", layout="wide")
    
    if 'logged_in' not in st.session_state:
        st.title("⛪ Sistema de Escala CCB")
        t1, t2 = st.tabs(["Login", "Criar Conta"])
        with t1:
            u = st.text_input("Usuário")
            p = st.text_input("Senha", type="password")
            if st.button("Entrar"):
                res = supabase.table("usuarios").select("*").eq("login", u).eq("senha", hash_senha(p)).execute()
                if res.data:
                    st.session_state.update({'logged_in': True, 'user_id': res.data[0]['id'], 'user_name': u})
                    st.rerun()
                else: st.error("Acesso Negado.")
        with t2:
            nu = st.text_input("Novo Usuário"); np = st.text_input("Nova Senha", type="password")
            if st.button("Cadastrar Administrador"):
                supabase.table("usuarios").insert({"login": nu, "senha": hash_senha(np)}).execute()
                st.success("Conta criada!")
    else:
        st.sidebar.title(f"👤 {st.session_state['user_name']}")
        areas_res = supabase.table("areas").select("*").eq("id_usuario", st.session_state['user_id']).execute()
        
        if areas_res.data:
            sel_nome = st.sidebar.selectbox("Área Atual", [a['nome_area'] for a in areas_res.data])
            st.session_state['area_ativa'] = next(a for a in areas_res.data if a['nome_area'] == sel_nome)
        else:
            st.session_state['area_ativa'] = None

        aba = st.sidebar.radio("Navegação", ["Dashboard", "Gerar Rodízio", "Cadastrar Pessoas", "Afastamentos", "Configurações"])
        if st.sidebar.button("Sair"): st.session_state.clear(); st.rerun()

        if aba == "Configurações":
            st.header("⚙️ Configurar Áreas")
            with st.form("nova_a"):
                n = st.text_input("Nome da Área"); v = st.number_input("Vagas", 1, 10, 2); c = st.text_input("Cargos")
                if st.form_submit_button("Criar Área"):
                    supabase.table("areas").insert({"id_usuario": st.session_state['user_id'], "nome_area": n, "vagas": v, "posicoes": c}).execute()
                    st.rerun()
            if areas_res.data:
                for a in areas_res.data:
                    col1, col2 = st.columns([4, 1])
                    col1.write(f"📂 {a['nome_area']}")
                    if col2.button("🗑️", key=f"del_area_{a['id']}"):
                        supabase.table("areas").delete().eq("id", a['id']).execute(); st.rerun()

        elif st.session_state['area_ativa']:
            area = st.session_state['area_ativa']

            if aba == "Dashboard":
                st.header(f"📊 Dashboard: {area['nome_area']}")
                vinc = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute()
                ids = [v['id_membro'] for v in vinc.data]
                membros = supabase.table("membros").select("*").in_("id", ids).order("nome").execute()
                
                for m in membros.data:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 1, 1])
                        c1.write(f"👤 **{m['nome']}**")
                        if c2.button("✏️ Editar", key=f"btn_ed_{m['id']}"): st.session_state['edit_id'] = m['id']
                        if c3.button("🗑️ Excluir", key=f"btn_rm_{m['id']}"):
                            supabase.table("restricoes").delete().eq("id_membro", m['id']).execute()
                            supabase.table("vinculos").delete().eq("id_membro", m['id']).execute()
                            supabase.table("membros").delete().eq("id", m['id']).execute(); st.rerun()

                        if st.session_state.get('edit_id') == m['id']:
                            with st.form(f"form_ed_{m['id']}"):
                                rest_res = supabase.table("restricoes").select("*").eq("id_membro", m['id']).execute()
                                dias_at = [r['valor'] for r in rest_res.data if r['tipo'] == 'dia']
                                sab_at = any(r['valor'] == '3_sabado' for r in rest_res.data)
                                nv_nome = st.text_input("Nome", m['nome'])
                                nv_ind = st.multiselect("Dias Proibidos", DIAS_ORDEM, default=dias_at, format_func=lambda x: DIAS_TRADUCAO[x])
                                nv_sab = st.checkbox("Restrição 3º Sábado", value=sab_at)
                                if st.form_submit_button("Salvar Alterações"):
                                    supabase.table("membros").update({"nome": nv_nome}).eq("id", m['id']).execute()
                                    supabase.table("restricoes").delete().eq("id_membro", m['id']).execute()
                                    for d in nv_ind: supabase.table("restricoes").insert({"id_membro": m['id'], "tipo": "dia", "valor": d}).execute()
                                    if nv_sab: supabase.table("restricoes").insert({"id_membro": m['id'], "tipo": "regra", "valor": "3_sabado"}).execute()
                                    del st.session_state['edit_id']; st.rerun()

            elif aba == "Cadastrar Pessoas":
                st.header(f"👥 Cadastro: {area['nome_area']}")
                with st.form("cad_p", clear_on_submit=True):
                    nome = st.text_input("Nome")
                    indisp = st.multiselect("Dias Proibidos:", DIAS_ORDEM, format_func=lambda x: DIAS_TRADUCAO[x])
                    sab = st.checkbox("Restrição: 3º Sábado")
                    if st.form_submit_button("Salvar"):
                        m_r = supabase.table("membros").insert({"nome": nome}).execute()
                        mid = m_r.data[0]['id']
                        supabase.table("vinculos").insert({"id_membro": mid, "id_area": area['id']}).execute()
                        for d in indisp: supabase.table("restricoes").insert({"id_membro": mid, "tipo": "dia", "valor": d}).execute()
                        if sab: supabase.table("restricoes").insert({"id_membro": mid, "tipo": "regra", "valor": "3_sabado"}).execute()
                        st.success("Membro Cadastrado!")

            elif aba == "Gerar Rodízio":
                st.header(f"📅 Gerar: {area['nome_area']}")
                c1, c2 = st.columns(2)
                meses = c1.selectbox("Período (Meses)", [1, 3, 6]); inicio = c2.date_input("Data Inicial")
                dias = st.multiselect("Cultos", DIAS_ORDEM, default=["Thursday", "Saturday", "Sunday"], format_func=lambda x: DIAS_TRADUCAO[x])
                if st.button("🚀 Gerar Escala", type="primary"):
                    st.session_state['escala_final'] = gerar_escala_logica(area, inicio, meses, dias)
                if 'escala_final' in st.session_state:
                    df = st.session_state['escala_final']
                    st.dataframe(df.drop(columns=['_mes']), use_container_width=True)
                    img_data = gerar_imagem_escala(df)
                    st.download_button(label="📸 Baixar Foto da Escala", data=img_data, file_name=f"Escala_{area['nome_area']}.png", mime="image/png")

            elif aba == "Afastamentos":
                st.header(f"✈️ Afastamentos: {area['nome_area']}")
                vinc = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute()
                ids = [v['id_membro'] for v in vinc.data]
                m_list = supabase.table("membros").select("id, nome").in_("id", ids).execute()
                with st.form("afast"):
                    n_af = st.selectbox("Irmão(ã)", [m['nome'] for m in m_list.data])
                    d_ini = st.date_input("Início"); d_fim = st.date_input("Fim")
                    if st.form_submit_button("Registrar"):
                        mid = next(m['id'] for m in m_list.data if m['nome'] == n_af)
                        curr = d_ini
                        while curr <= d_fim:
                            supabase.table("restricoes").insert({"id_membro": mid, "tipo": "data_especifica", "valor": curr.strftime('%Y-%m-%d')}).execute()
                            curr += timedelta(days=1)
                        st.success("Registrado!")

if __name__ == "__main__":
    main()
