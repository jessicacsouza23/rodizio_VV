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

# --- GERAÇÃO DE TABELA (FONTE GIGANTE E LIMPA) ---
def gerar_tabela_legivel(df, area_nome):
    if df.empty: return None
    
    # Filtra apenas colunas de cargos
    cargos = [c for c in df.columns if c not in ['_mes', 'Data', 'Dia']]
    
    # Configurações de tamanho (Focadas em leitura fácil)
    LARG_COL = 350  # Colunas largas para o nome não cortar
    ALT_LINHA = 100 # Linhas altas para letra grande
    MARGEM = 40
    
    larg_total = (len(cargos) + 2) * LARG_COL + (MARGEM * 2)
    alt_total = (len(df) + 2) * ALT_LINHA + 150
    
    img = Image.new('RGB', (int(larg_total), int(alt_total)), color="#FFFFFF")
    draw = ImageDraw.Draw(img)
    
    try:
        # Fontes pesadas para leitura sem esforço
        f_tit = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 65)
        f_head = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 55)
        f_corpo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
    except:
        f_tit = f_head = f_corpo = ImageFont.load_default()

    # 1. Título do Mês (Verde Escuro)
    draw.rectangle([0, 0, larg_total, 120], fill="#004D40")
    txt_mes = str(df['_mes'].iloc[0]).upper()
    draw.text((MARGEM, 25), txt_mes, fill="white", font=f_tit)

    # 2. Cabeçalho das Colunas (Verde Claro)
    y = 120
    colunas = cargos + ["DATA", "DIA"]
    for i, col in enumerate(colunas):
        x = MARGEM + (i * LARG_COL)
        draw.rectangle([x, y, x + LARG_COL, y + ALT_LINHA], fill="#80CBC4", outline="black", width=3)
        draw.text((x + 15, y + 20), col, fill="black", font=f_head)

    # 3. Dados das Irmãs (Grade limpa)
    y += ALT_LINHA
    for _, row in df.iterrows():
        for i, col in enumerate(colunas):
            x = MARGEM + (i * LARG_COL)
            # Desenha a borda da célula
            draw.rectangle([x, y, x + LARG_COL, y + ALT_LINHA], outline="#000000", width=2)
            
            # Busca o valor
            if col == "DATA": val = row['Data'].split('/')[0]
            elif col == "DIA": val = row['Dia'][0] # Apenas a letra do dia (D, Q, S...)
            else: val = str(row[col])
            
            # Escreve o nome EM NEGRITO E GRANDE
            draw.text((x + 20, y + 15), val.upper(), fill="black", font=f_corpo)
        y += ALT_LINHA

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def main():
    st.set_page_config(page_title="Rodízio", layout="wide")
    
    # CSS para forçar a fonte do site a ficar grande para você
    st.markdown("<style>*{font-size: 24px !important; font-weight: bold;}</style>", unsafe_allow_html=True)

    if 'logged_in' not in st.session_state:
        st.title("⛪ Login")
        u = st.text_input("Usuário"); p = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            res = supabase.table("usuarios").select("*").eq("login", u).eq("senha", hash_senha(p)).execute()
            if res.data: st.session_state.update({'logged_in': True, 'user_id': res.data[0]['id']}); st.rerun()
    else:
        res_areas = supabase.table("areas").select("*").eq("id_usuario", st.session_state['user_id']).execute().data
        area_n = st.sidebar.selectbox("🎯 Escolha a Escala", [a['nome_area'] for a in res_areas]) if res_areas else None
        area = next((a for a in res_areas if a['nome_area'] == area_n), None) if area_n else None

        menu = st.sidebar.radio("Navegação", ["📅 Gerar Escala", "📂 Histórico", "⚙️ Configurações"])

        if menu == "📅 Gerar Escala" and area:
            st.header(f"Organizando: {area['nome_area']}")
            
            col1, col2 = st.columns(2)
            d_i = col1.date_input("Data de Início")
            d_c = col2.multiselect("Dias de Culto", ["Monday", "Wednesday", "Saturday", "Sunday"], default=["Sunday"])

            if st.button("🔄 GERAR NOVA TABELA (LIMPAR ANTERIOR)"):
                # Limpa qualquer rastro de rodízio antigo da tela
                if 'df_edit' in st.session_state: del st.session_state['df_edit']
                
                cargos = [c.strip() for c in area['posicoes'].split(",")]
                datas = [(d_i + timedelta(days=x)) for x in range(35) if (d_i + timedelta(days=x)).strftime('%A') in d_c]
                
                nova_escala = []
                for d in datas:
                    item = {"Data": d.strftime("%d/%m"), "Dia": d.strftime("%A"), "_mes": d.strftime("%B / %Y")}
                    for c in cargos: item[c] = ""
                    nova_escala.append(item)
                
                st.session_state['df_edit'] = pd.DataFrame(nova_escala)
                st.rerun()

            if 'df_edit' in st.session_state:
                st.subheader("✍️ Digite os nomes (Letra Grande no Zap)")
                df_final = st.data_editor(st.session_state['df_edit'], use_container_width=True)
                
                if st.button("✅ FINALIZAR E GERAR IMAGEM"):
                    img_bytes = gerar_tabela_legivel(df_final, area['nome_area'])
                    st.image(img_bytes)
                    st.download_button("📥 BAIXAR PARA ENVIAR NO WHATSAPP", img_bytes, "escala.png", "image/png")
                    # Salva no banco de dados para o histórico
                    supabase.table("escalas").insert({"id_area": area['id'], "nome_area": area['nome_area'], "dados_escala": df_final.to_json(orient='records')}).execute()

        elif menu == "📂 Histórico" and area:
            st.header("Escalas Salvas")
            h = supabase.table("escalas").select("*").eq("id_area", area['id']).order("data_geracao", desc=True).execute().data
            for e in h:
                if st.button(f"📅 Abrir Escala gerada em {e['data_geracao'][:16]}", key=e['id']):
                    st.session_state['df_edit'] = pd.read_json(io.StringIO(e['dados_escala']))
                    st.rerun()

        elif menu == "⚙️ Configurações":
            st.subheader("Cadastrar Novo Grupo de Rodízio")
            with st.form("nova_area"):
                n = st.text_input("Nome (Ex: Organistas de Sábado)")
                p = st.text_input("Cargos (Ex: G1, G2, Sentinela)")
                if st.form_submit_button("Salvar Grupo"):
                    supabase.table("areas").insert({"id_usuario": st.session_state['user_id'], "nome_area": n, "vagas": len(p.split(",")), "posicoes": p}).execute()
                    st.rerun()

if __name__ == "__main__":
    main()
