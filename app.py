# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, timedelta
from supabase import create_client, Client
from PIL import Image, ImageDraw, ImageFont
import io

# --- CONEXÃO ---
URL = "https://qfvahrtockqxlvrhknkn.supabase.co"
KEY = "sb_publishable_NYv_kYobauOtW0lT3fWp6A_irgKBVGN"
supabase: Client = create_client(URL, KEY)

def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

# --- GERAÇÃO DE IMAGEM (ESTILO TABELA VERDE COM FONTE GIGANTE) ---
def gerar_tabela_final(df):
    if df.empty: return None
    
    # Pega apenas as colunas que pertencem a ESTA escala específica
    colunas_cargos = [c for c in df.columns if c not in ['_mes', 'Data', 'Dia']]
    titulos = ["DATA", "DIA"] + colunas_cargos
    
    # Dimensões para garantir que a letra fique enorme
    LARG_CELULA = 400
    ALT_LINHA = 120 # Linha bem alta
    larg_total = len(titulos) * LARG_CELULA
    alt_total = (len(df) + 2) * ALT_LINHA
    
    img = Image.new('RGB', (larg_total, alt_total), color="#FFFFFF")
    draw = ImageDraw.Draw(img)
    
    try:
        # Fonte tamanho 75 - equivalente a um título grande
        f_header = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
        f_corpo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 75)
    except:
        f_header = f_corpo = ImageFont.load_default()

    # Cabeçalho (Verde)
    draw.rectangle([0, 0, larg_total, ALT_LINHA], fill="#1B5E20")
    for i, tit in enumerate(titulos):
        x = i * LARG_CELULA
        draw.rectangle([x, 0, x + LARG_CELULA, ALT_LINHA], outline="white", width=3)
        draw.text((x + 20, 30), tit.upper(), fill="white", font=f_header)

    # Linhas com Nomes
    y = ALT_LINHA
    for _, row in df.iterrows():
        for i, tit in enumerate(titulos):
            x = i * LARG_CELULA
            draw.rectangle([x, y, x + LARG_CELULA, y + ALT_LINHA], outline="black", width=2)
            
            # Valor da célula
            if tit == "DATA": val = row['Data'].split('/')[0]
            elif tit == "DIA": val = row['Dia'][0].upper() # S, D, Q...
            else: val = str(row[tit])
            
            # Escreve o nome centralizado na célula
            draw.text((x + 25, y + 15), val.upper(), fill="black", font=f_corpo)
        y += ALT_LINHA

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def main():
    st.set_page_config(page_title="Rodízio CCB", layout="wide")

    if 'logged_in' not in st.session_state:
        st.title("⛪ Login")
        u = st.text_input("Usuário"); p = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            res = supabase.table("usuarios").select("*").eq("login", u).eq("senha", hash_senha(p)).execute()
            if res.data: st.session_state.update({'logged_in': True, 'user_id': res.data[0]['id']}); st.rerun()
    else:
        # Busca áreas e garante que ao trocar de área, os dados antigos sumam
        res_areas = supabase.table("areas").select("*").eq("id_usuario", st.session_state['user_id']).execute().data
        area_n = st.sidebar.selectbox("🎯 Selecione o Grupo", [a['nome_area'] for a in res_areas])
        
        # Lógica para limpar escala ao trocar de grupo
        if 'area_atual' not in st.session_state or st.session_state['area_atual'] != area_n:
            st.session_state['area_atual'] = area_n
            if 'df_edit' in st.session_state: del st.session_state['df_edit']

        area = next((a for a in res_areas if a['nome_area'] == area_n), None)
        menu = st.sidebar.radio("Menu", ["📅 Rodízio", "📂 Histórico", "⚙️ Configurações"])

        if menu == "📅 Rodízio" and area:
            st.title(f"Grupo: {area['nome_area']}")
            
            with st.expander("Configurar Nova Escala"):
                c1, c2 = st.columns(2)
                d_i = c1.date_input("Data de Início")
                d_c = c2.multiselect("Dias", ["Monday", "Wednesday", "Saturday", "Sunday"], default=["Sunday"])
                
                if st.button("GERAR TABELA VAZIA"):
                    cargos = [c.strip() for c in area['posicoes'].split(",")]
                    datas = [(d_i + timedelta(days=x)) for x in range(35) if (d_i + timedelta(days=x)).strftime('%A') in d_c]
                    
                    dados = []
                    for d in datas:
                        linha = {"Data": d.strftime("%d/%m"), "Dia": d.strftime("%A"), "_mes": d.strftime("%B/%Y")}
                        for c in cargos: linha[c] = ""
                        dados.append(linha)
                    st.session_state['df_edit'] = pd.DataFrame(dados)

            if 'df_edit' in st.session_state:
                st.subheader("Preencha os Nomes:")
                # Exibe apenas as colunas DESTA área no editor
                df_final = st.data_editor(st.session_state['df_edit'], use_container_width=True)
                
                if st.button("📸 GERAR IMAGEM PARA WHATSAPP", type="primary"):
                    img = gerar_tabela_final(df_final)
                    st.image(img)
                    st.download_button("📥 Baixar Imagem com Letra Grande", img, "rodizio.png", "image/png")
                    # Salva no histórico
                    supabase.table("escalas").insert({"id_area": area['id'], "nome_area": area['nome_area'], "dados_escala": df_final.to_json(orient='records')}).execute()

        elif menu == "📂 Histórico" and area:
            st.header("Histórico deste Grupo")
            h = supabase.table("escalas").select("*").eq("id_area", area['id']).order("data_geracao", desc=True).execute().data
            for e in h:
                if st.button(f"Abrir {e['data_geracao'][:16]}", key=e['id']):
                    st.session_state['df_edit'] = pd.read_json(io.StringIO(e['dados_escala']))
                    st.rerun()

        elif menu == "⚙️ Configurações":
            st.subheader("Novo Grupo de Rodízio")
            with st.form("new_group"):
                n = st.text_input("Nome (Ex: Organistas Culto)")
                p = st.text_input("Cargos (Ex: G1, G2, Sentinela)")
                if st.form_submit_button("Criar Grupo"):
                    supabase.table("areas").insert({"id_usuario": st.session_state['user_id'], "nome_area": n, "vagas": len(p.split(",")), "posicoes": p}).execute()
                    st.rerun()

if __name__ == "__main__":
    main()
