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

# Cores fortes para separação visual
ESTILO_CARDS = [
    {"bg": "#2E7D32", "text_bg": "#E8F5E9"}, # Verde
    {"bg": "#1565C0", "text_bg": "#E3F2FD"}, # Azul
    {"bg": "#6A1B9A", "text_bg": "#F3E5F5"}, # Roxo
    {"bg": "#E65100", "text_bg": "#FFF3E0"}, # Laranja
]

MESES_PT = {'January': 'Janeiro', 'February': 'Fevereiro', 'March': 'Março', 'April': 'Abril', 'May': 'Maio', 'June': 'Junho',
            'July': 'Julho', 'August': 'Agosto', 'September': 'Setembro', 'October': 'Outubro', 'November': 'Novembro', 'December': 'Dezembro'}
DIAS_PT = {'Monday': 'Segunda', 'Tuesday': 'Terça', 'Wednesday': 'Quarta', 'Thursday': 'Quinta', 'Friday': 'Sexta', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}

def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

# --- GERAÇÃO DE CARD (FOCO EM FONTE GRANDE) ---
def gerar_card_dia_grande(row, area_nome):
    # Formato Retrato (800 de largura por 1200 de altura) para caber nomes grandes
    larg, alt = 850, 1250 
    img = Image.new('RGB', (larg, alt), color="#FFFFFF")
    draw = ImageDraw.Draw(img)
    
    try:
        # Fontes escaladas para leitura sem óculos
        f_data = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 75)
        f_cargo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 50)
        f_nome = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 85)
        f_footer = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 35)
    except:
        f_data = f_cargo = f_nome = f_footer = ImageFont.load_default()

    # Cabeçalho Data
    draw.rectangle([0, 0, larg, 220], fill="#212121")
    txt_data = f"{row['Data']}"
    txt_dia = f"{row['Dia']}".upper()
    
    w_d = draw.textlength(txt_data, font=f_data)
    draw.text(((larg-w_d)/2, 40), txt_data, fill="white", font=f_data)
    
    w_dia = draw.textlength(txt_dia, font=f_cargo)
    draw.text(((larg-w_dia)/2, 135), txt_dia, fill="#FFD600", font=f_cargo)

    # Conteúdo
    cargos = [c for c in row.index if c not in ['_mes', 'Data', 'Dia']]
    y = 260
    
    for idx, cg in enumerate(cargos):
        estilo = ESTILO_CARDS[idx % len(ESTILO_CARDS)]
        
        # Faixa do Cargo
        draw.rectangle([30, y, larg-30, y+70], fill=estilo["bg"])
        draw.text((50, y+10), cg.upper(), fill="white", font=f_cargo)
        
        # Área do Nome (Fundo levemente colorido para separar)
        y += 70
        draw.rectangle([30, y, larg-30, y+140], fill="#FBFBFB", outline="#CCCCCC", width=2)
        
        nome = str(row[cg])
        # Centralizar Nome
        w_n = draw.textlength(nome, font=f_nome)
        draw.text(((larg-w_n)/2, y+20), nome, fill="black", font=f_nome)
        
        y += 180 # Espaçamento para o próximo bloco

    # Rodapé
    draw.text((30, alt-60), f"RODÍZIO: {area_nome}", fill="#999999", font=f_footer)
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- LÓGICA ---
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

# --- APP PRINCIPAL ---
def main():
    st.set_page_config(page_title="Gestão de Escalas", layout="wide")
    
    if 'logged_in' not in st.session_state:
        st.title("⛪ Acesso Restrito")
        with st.form("login"):
            u = st.text_input("Usuário"); p = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                res = supabase.table("usuarios").select("*").eq("login", u).eq("senha", hash_senha(p)).execute()
                if res.data: 
                    st.session_state.update({'logged_in': True, 'user_id': res.data[0]['id'], 'user_login': res.data[0]['login']})
                    st.rerun()
    else:
        res_areas = supabase.table("areas").select("*").eq("id_usuario", st.session_state['user_id']).execute().data
        area_n = st.sidebar.selectbox("🎯 Escala Ativa", [a['nome_area'] for a in res_areas]) if res_areas else None
        area = next((a for a in res_areas if a['nome_area'] == area_n), None) if area_n else None

        aba = st.sidebar.radio("Navegação", ["📅 Rodízio", "📂 Histórico", "👥 Membros", "✈️ Afastamentos", "⚙️ Configurações"])
        st.sidebar.divider()
        if st.sidebar.button("Sair"): st.session_state.clear(); st.rerun()

        if aba == "📅 Rodízio" and area:
            st.title(f"✍️ Organizar: {area['nome_area']}")
            with st.expander("🛠️ Parâmetros de Geração"):
                c1, c2, c3 = st.columns(3)
                m = c1.number_input("Meses", 1, 3, 1)
                d_i = c2.date_input("Início")
                d_c = c3.multiselect("Dias", list(DIAS_PT.keys()), default=["Sunday"], format_func=lambda x: DIAS_PT[x])
                if st.button("Gerar Sugestão"):
                    st.session_state['df_edit'] = gerar_escala_logica(area, d_i, m, d_c)

            if 'df_edit' in st.session_state:
                st.subheader("1. Edite se necessário")
                df_final = st.data_editor(st.session_state['df_edit'], use_container_width=True)
                
                if st.button("💾 SALVAR E GERAR IMAGENS GRANDES", type="primary", use_container_width=True):
                    supabase.table("escalas").insert({"id_area": area['id'], "nome_area": area['nome_area'], "dados_escala": df_final.to_json(orient='records')}).execute()
                    st.success("Salvo!")
                    
                    for _, row in df_final.iterrows():
                        card = gerar_card_dia_grande(row, area['nome_area'])
                        col1, col2 = st.columns([1, 1])
                        col1.image(card, width=400)
                        col2.write(f"### Data: {row['Data']}")
                        col2.download_button(f"📥 Baixar para WhatsApp ({row['Data']})", card, f"card_{row['Data'].replace('/','_')}.png", "image/png")
                        st.divider()

        elif aba == "📂 Histórico" and area:
            st.header("📂 Escalas Anteriores")
            h = supabase.table("escalas").select("*").eq("id_area", area['id']).order("data_geracao", desc=True).execute().data
            for e in h:
                with st.container(border=True):
                    st.write(f"📅 Gerada em: {e['data_geracao'][:16]}")
                    if st.button("👁️ Visualizar/Gerar Cards", key=f"v_{e['id']}"):
                        st.session_state['df_edit'] = pd.read_json(io.StringIO(e['dados_escala']))
                        st.rerun()

        elif aba == "👥 Membros" and area:
            st.header("👥 Gestão de Irmãs/Irmãos")
            with st.form("add_m"):
                n = st.text_input("Nome")
                if st.form_submit_button("Cadastrar"):
                    res = supabase.table("membros").insert({"nome": n}).execute()
                    supabase.table("vinculos").insert({"id_membro": res.data[0]['id'], "id_area": area['id']}).execute()
                    st.rerun()
            
            vinc = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute().data
            ids = [v['id_membro'] for v in vinc]
            if ids:
                ms = supabase.table("membros").select("*").in_("id", ids).order("nome").execute().data
                for m in ms:
                    st.write(f"• {m['nome']} (Total de Serviços: {m['total_servicos']})")

        elif aba == "✈️ Afastamentos" and area:
            st.header("✈️ Bloqueios")
            vinc = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute().data
            ids = [v['id_membro'] for v in vinc]
            if ids:
                membros_l = supabase.table("membros").select("id, nome").in_("id", ids).execute().data
                with st.form("bloq"):
                    m_sel = st.selectbox("Irmã", [m['nome'] for m in membros_l])
                    d_b = st.date_input("Bloquear data")
                    if st.form_submit_button("Confirmar"):
                        mid = next(m['id'] for m in membros_l if m['nome'] == m_sel)
                        supabase.table("restricoes").insert({"id_membro": mid, "tipo": "data_especifica", "valor": d_b.strftime('%Y-%m-%d')}).execute()
                        st.success("Bloqueado!")

        elif aba == "⚙️ Configurações":
            t1, t2 = st.tabs(["🏗️ Áreas", "🔐 Usuários"])
            with t1:
                with st.form("n_a"):
                    n = st.text_input("Nome Escala")
                    p = st.text_input("Cargos (Galeria, Porta, Atrio...)")
                    if st.form_submit_button("Criar"):
                        supabase.table("areas").insert({"id_usuario": st.session_state['user_id'], "nome_area": n, "vagas": len(p.split(",")), "posicoes": p}).execute()
                        st.rerun()
            with t2:
                with st.form("n_u"):
                    u = st.text_input("Login"); p = st.text_input("Senha", type="password")
                    if st.form_submit_button("Criar Acesso"):
                        supabase.table("usuarios").insert({"login": u, "senha": hash_senha(p)}).execute()
                        st.success("Criado!")

if __name__ == "__main__":
    main()
