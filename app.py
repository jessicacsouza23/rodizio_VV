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

# Cores vibrantes e legíveis para os cards (Estilo Escolinha)
ESTILO_CARDS = [
    {"bg": "#E8F5E9", "border": "#2E7D32", "text": "#1B5E20"}, # Verde
    {"bg": "#E3F2FD", "border": "#1565C0", "text": "#0D47A1"}, # Azul
    {"bg": "#F3E5F5", "border": "#7B1FA2", "text": "#4A148C"}, # Roxo
    {"bg": "#FFF3E0", "border": "#EF6C00", "text": "#E65100"}, # Laranja
    {"bg": "#FFEBEE", "border": "#C62828", "text": "#B71C1C"}, # Vermelho
    {"bg": "#F1F8E9", "border": "#558B2F", "text": "#33691E"}, # Lima
]

MESES_PT = {'January': 'Janeiro', 'February': 'Fevereiro', 'March': 'Março', 'April': 'Abril', 'May': 'Maio', 'June': 'Junho',
            'July': 'Julho', 'August': 'Agosto', 'September': 'Setembro', 'October': 'Outubro', 'November': 'Novembro', 'December': 'Dezembro'}
DIAS_PT = {'Monday': 'Segunda', 'Tuesday': 'Terça', 'Wednesday': 'Quarta', 'Thursday': 'Quinta', 'Friday': 'Sexta', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}

def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

# --- GERAÇÃO DE CARD INDIVIDUAL (ALTA LEGIBILIDADE) ---
def gerar_card_dia(row, area_nome):
    larg, alt = 1000, 1000 # Formato quadrado para WhatsApp
    img = Image.new('RGB', (larg, alt), color="#FFFFFF")
    draw = ImageDraw.Draw(img)
    
    try:
        f_data = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 65)
        f_cargo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38)
        f_nome = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
        f_footer = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
    except:
        f_data = f_cargo = f_nome = f_footer = ImageFont.load_default()

    # Cabeçalho Escuro
    draw.rectangle([0, 0, larg, 180], fill="#2C3E50")
    txt_data = f"{row['Data']} - {row['Dia']}"
    w_d = draw.textlength(txt_data, font=f_data)
    draw.text(((larg-w_d)/2, 55), txt_data, fill="white", font=f_data)

    # Listagem de Cargos
    cargos = [c for c in row.index if c not in ['_mes', 'Data', 'Dia']]
    y = 220
    for idx, cg in enumerate(cargos):
        estilo = ESTILO_CARDS[idx % len(ESTILO_CARDS)]
        # Card do Item
        draw.rectangle([40, y, larg-40, y+130], fill=estilo["bg"], outline=estilo["border"], width=4)
        draw.rectangle([40, y, 240, y+130], fill=estilo["border"]) # Tarja do Cargo
        
        # Texto do Cargo (Abreviado se necessário)
        draw.text((60, y+45), cg.upper()[:10], fill="white", font=f_cargo)
        # Nome (Grande e Centralizado no espaço branco)
        draw.text((270, y+35), str(row[cg]), fill="black", font=f_nome)
        y += 150

    # Rodapé
    draw.text((40, 940), f"RODÍZIO: {area_nome.upper()}", fill="#BDC3C7", font=f_footer)
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- LÓGICA DE ESCALA ---
def membro_disponivel(id_membro, data_alvo):
    res = supabase.table("restricoes").select("*").eq("id_membro", id_membro).execute()
    for r in res.data:
        if r['tipo'] == 'dia' and data_alvo.strftime('%A') == r['valor']: return False
        if r['tipo'] == 'data_especifica' and data_alvo.strftime('%Y-%m-%d') == r['valor']: return False
    return True

def gerar_escala_logica(area, data_inicio, meses, dias_culto):
    pos_list = [p.strip() for p in area['posicoes'].split(",")]
    vagas = len(pos_list)
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

# --- INTERFACE COMPLETA ---
def main():
    st.set_page_config(page_title="Gestão de Rodízio", layout="wide")
    
    if 'logged_in' not in st.session_state:
        st.title("⛪ Login do Sistema")
        u = st.text_input("Usuário"); p = st.text_input("Senha", type="password")
        if st.button("Entrar", use_container_width=True):
            res = supabase.table("usuarios").select("*").eq("login", u).eq("senha", hash_senha(p)).execute()
            if res.data: 
                st.session_state.update({'logged_in': True, 'user_id': res.data[0]['id'], 'user_login': res.data[0]['login']})
                st.rerun()
    else:
        # Busca áreas do usuário
        res_areas = supabase.table("areas").select("*").eq("id_usuario", st.session_state['user_id']).execute().data
        area_n = st.sidebar.selectbox("🎯 Selecione a Escala", [a['nome_area'] for a in res_areas]) if res_areas else None
        area = next((a for a in res_areas if a['nome_area'] == area_n), None) if area_n else None

        aba = st.sidebar.radio("Navegação", ["📅 Gerar Rodízio", "📂 Histórico", "👥 Membros", "✈️ Afastamentos", "⚙️ Configurações"])
        st.sidebar.divider()
        if st.sidebar.button("Sair"): st.session_state.clear(); st.rerun()

        if aba == "📅 Gerar Rodízio" and area:
            st.title(f"✍️ Organizar: {area['nome_area']}")
            with st.expander("⚙️ Parâmetros de Geração"):
                c1, c2, c3 = st.columns(3)
                m = c1.number_input("Meses", 1, 3, 1)
                d_i = c2.date_input("Data de Início")
                d_c = c3.multiselect("Dias de Culto", list(DIAS_PT.keys()), default=["Sunday"], format_func=lambda x: DIAS_PT[x])
                if st.button("Gerar Nova Sugestão"):
                    st.session_state['df_edit'] = gerar_escala_logica(area, d_i, m, d_c)

            if 'df_edit' in st.session_state:
                st.subheader("1. Ajuste os nomes se necessário")
                df_final = st.data_editor(st.session_state['df_edit'], use_container_width=True)
                
                if st.button("💾 SALVAR E GERAR CARDS PARA WHATSAPP", type="primary", use_container_width=True):
                    supabase.table("escalas").insert({"id_area": area['id'], "nome_area": area['nome_area'], "dados_escala": df_final.to_json(orient='records')}).execute()
                    st.success("Rodízio salvo! Veja os cards abaixo:")
                    
                    for _, row in df_final.iterrows():
                        card = gerar_card_dia(row, area['nome_area'])
                        col1, col2 = st.columns([1, 2])
                        col1.image(card, width=350)
                        col2.write(f"### Card do dia {row['Data']}")
                        col2.download_button(f"📥 Baixar Imagem {row['Data']}", card, f"card_{row['Data'].replace('/','_')}.png", "image/png")
                        st.divider()

        elif aba == "📂 Histórico" and area:
            st.header("📂 Histórico de Escalas")
            hist = supabase.table("escalas").select("*").eq("id_area", area['id']).order("data_geracao", desc=True).execute().data
            for e in hist:
                with st.container(border=True):
                    st.write(f"📅 Gerada em: {e['data_geracao'][:16]}")
                    if st.button("👁️ Visualizar esta escala", key=f"v_{e['id']}"):
                        st.session_state['df_edit'] = pd.read_json(io.StringIO(e['dados_escala']))
                        st.rerun()

        elif aba == "👥 Membros" and area:
            st.header("👥 Gestão de Membros")
            with st.form("novo_m"):
                n = st.text_input("Nome do Irmão/Irmã")
                if st.form_submit_button("Cadastrar"):
                    res = supabase.table("membros").insert({"nome": n}).execute()
                    supabase.table("vinculos").insert({"id_membro": res.data[0]['id'], "id_area": area['id']}).execute()
                    st.rerun()
            
            # Lista membros vinculados
            vinc = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute().data
            ids = [v['id_membro'] for v in vinc]
            if ids:
                ms = supabase.table("membros").select("*").in_("id", ids).order("nome").execute().data
                for m in ms:
                    st.text(f"• {m['nome']} (Serviços: {m['total_servicos']})")

        elif aba == "✈️ Afastamentos" and area:
            st.header("✈️ Bloqueios e Férias")
            # Lista membros para o selectbox
            vinc = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute().data
            ids = [v['id_membro'] for v in vinc]
            if ids:
                membros_lista = supabase.table("membros").select("id, nome").in_("id", ids).execute().data
                with st.form("afast"):
                    m_sel = st.selectbox("Membro", [m['nome'] for m in membros_lista])
                    d_bloq = st.date_input("Data para bloquear")
                    if st.form_submit_button("Confirmar Bloqueio"):
                        mid = next(m['id'] for m in membros_lista if m['nome'] == m_sel)
                        supabase.table("restricoes").insert({"id_membro": mid, "tipo": "data_especifica", "valor": d_bloq.strftime('%Y-%m-%d')}).execute()
                        st.success("Bloqueado!")

        elif aba == "⚙️ Configurações":
            tab1, tab2 = st.tabs(["🏗️ Configurar Áreas", "🔐 Usuários"])
            with tab1:
                with st.form("nova_a"):
                    n = st.text_input("Nome (Ex: Organistas Sábado)")
                    p = st.text_input("Cargos/Salas (Ex: Galeria, Porta, Atrio)")
                    if st.form_submit_button("Criar Área"):
                        supabase.table("areas").insert({"id_usuario": st.session_state['user_id'], "nome_area": n, "vagas": len(p.split(",")), "posicoes": p}).execute()
                        st.rerun()
            with tab2:
                with st.form("novo_u"):
                    u = st.text_input("Login")
                    p = st.text_input("Senha", type="password")
                    if st.form_submit_button("Criar Acesso"):
                        supabase.table("usuarios").insert({"login": u, "senha": hash_senha(p)}).execute()
                        st.success("Usuário criado!")

if __name__ == "__main__":
    main()
