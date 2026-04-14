# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, timedelta
from supabase import create_client, Client
from PIL import Image, ImageDraw, ImageFont
import io

# --- CONFIGURAÇÕES ---
URL = "https://qfvahrtockqxlvrhknkn.supabase.co"
KEY = "sb_publishable_NYv_kYobauOtW0lT3fWp6A_irgKBVGN"
supabase: Client = create_client(URL, KEY)

# Cores vibrantes para os cards (estilo escolinha)
CORES_CARDS = [
    {"bg": "#E8F5E9", "border": "#2E7D32", "text": "#1B5E20"}, # Verde
    {"bg": "#E3F2FD", "border": "#1565C0", "text": "#0D47A1"}, # Azul
    {"bg": "#F3E5F5", "border": "#7B1FA2", "text": "#4A148C"}, # Roxo
    {"bg": "#FFF3E0", "border": "#EF6C00", "text": "#E65100"}, # Laranja
]

def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

# --- NOVA GERAÇÃO: UM CARD POR DIA (TAMANHO WHATSAPP) ---
def gerar_card_dia(row, area_nome):
    # Formato quadrado (1080x1080) - Perfeito para celular
    larg, alt = 1000, 1000
    img = Image.new('RGB', (larg, alt), color="#FFFFFF")
    draw = ImageDraw.Draw(img)
    
    try:
        f_header = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 50)
        f_data = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 70)
        f_cargo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        f_nome = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 55)
    except:
        f_header = f_data = f_cargo = f_nome = ImageFont.load_default()

    # Faixa do Topo (Data)
    draw.rectangle([0, 0, larg, 200], fill="#333333")
    txt_data = f"{row['Data']} - {row['Dia']}"
    w_d = draw.textlength(txt_data, font=f_data)
    draw.text(((larg-w_d)/2, 60), txt_data, fill="white", font=f_data)
    
    # Rodapé com nome da escala
    draw.text((40, 930), area_nome.upper(), fill="#999999", font=f_cargo)

    # Conteúdo (Cargos e Nomes)
    cargos = [c for c in row.index if c not in ['_mes', 'Data', 'Dia']]
    y = 240
    espaco = 160 # Espaço vertical para cada bloco
    
    for idx, cg in enumerate(cargos):
        cor = CORES_CARDS[idx % len(CORES_CARDS)]
        
        # Desenha o Container do Cargo (Estilo a primeira imagem)
        draw.rectangle([40, y, larg-40, y+130], fill=cor["bg"], outline=cor["border"], width=5)
        draw.rectangle([40, y, 250, y+130], fill=cor["border"]) # Tarja lateral
        
        # Texto do Cargo (Dentro da tarja)
        draw.text((60, y+45), cg.upper()[:10], fill="white", font=f_cargo)
        
        # Nome da Pessoa (Destaque máximo)
        nome = str(row[cg])
        draw.text((280, y+35), nome, fill="black", font=f_nome)
        
        y += espaco

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def main():
    st.set_page_config(page_title="Rodízio CCB", layout="wide")
    
    if 'logged_in' not in st.session_state:
        st.title("⛪ Acesso")
        u = st.text_input("Usuário"); p = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            res = supabase.table("usuarios").select("*").eq("login", u).eq("senha", hash_senha(p)).execute()
            if res.data: st.session_state.update({'logged_in': True, 'user_id': res.data[0]['id']}); st.rerun()
    else:
        res_areas = supabase.table("areas").select("*").eq("id_usuario", st.session_state['user_id']).execute().data
        area_n = st.sidebar.selectbox("🎯 Escala", [a['nome_area'] for a in res_areas]) if res_areas else None
        area = next((a for a in res_areas if a['nome_area'] == area_n), None) if area_n else None

        if st.sidebar.button("Sair"): st.session_state.clear(); st.rerun()

        if area:
            st.title(f"📍 {area['nome_area']}")
            
            # Se já houver dados no editor
            if 'df_edit' in st.session_state:
                st.subheader("1. Confira os nomes")
                df_final = st.data_editor(st.session_state['df_edit'], use_container_width=True)
                
                st.divider()
                st.subheader("2. Gerar Cards para WhatsApp")
                st.info("Clique no botão abaixo para gerar uma imagem legível para cada dia.")
                
                if st.button("📸 GERAR CARDS INDIVIDUAIS"):
                    for i, (_, row) in enumerate(df_final.iterrows()):
                        card = gerar_card_dia(row, area['nome_area'])
                        
                        col_img, col_btn = st.columns([2,1])
                        with col_img:
                            st.image(card, width=400)
                        with col_btn:
                            st.write(f"Data: {row['Data']}")
                            st.download_button(f"Baixar Card {row['Data']}", card, f"escala_{row['Data'].replace('/','_')}.png", "image/png")
                        st.divider()
            
            # Painel de geração (escondido após gerar para focar na imagem)
            with st.sidebar.expander("⚙️ Gerar Nova Escala"):
                d_i = st.date_input("Data Inicial")
                dias = st.multiselect("Dias da Semana", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
                if st.button("Criar Tabela Base"):
                    # Lógica simplificada de geração para exemplo
                    cargos = area['posicoes'].split(",")
                    base = [{"Data": (d_i + timedelta(days=x)).strftime("%d/%m"), "Dia": (d_i + timedelta(days=x)).strftime("%a")} for x in range(30) if (d_i + timedelta(days=x)).strftime("%A") in dias]
                    for b in base: 
                        for c in cargos: b[c.strip()] = ""
                    st.session_state['df_edit'] = pd.DataFrame(base)
                    st.rerun()

if __name__ == "__main__":
    main()
