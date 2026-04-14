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

# --- GERAÇÃO DE TABELA ESTILO ANTIGO (COMPACTA) ---
def gerar_tabela_estilo_antigo(df):
    if df.empty: return None
    
    # Configurações de tamanho para garantir que caiba no celular
    larg_celula = 250
    alt_linha = 80
    margem = 20
    colunas_dados = [c for c in df.columns if c not in ['_mes', 'Data', 'Dia']]
    num_cols = len(colunas_dados) + 2 # + Data e Dia
    
    larg_total = (num_cols * larg_celula) + (margem * 2)
    alt_total = (len(df) + 2) * alt_linha + 100
    
    img = Image.new('RGB', (larg_total, alt_total), color="#FFFFFF")
    draw = ImageDraw.Draw(img)
    
    try:
        f_header = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 45)
        f_texto = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
    except:
        f_header = f_texto = ImageFont.load_default()

    # Cabeçalho Principal (Verde Escuro)
    draw.rectangle([0, 0, larg_total, alt_linha], fill="#1B5E20")
    txt_mes = df['_mes'].iloc[0] if '_mes' in df.columns else "RODÍZIO"
    draw.text((larg_total/2 - 100, 15), txt_mes.upper(), fill="white", font=f_header)

    # Cabeçalho das Colunas (Verde Médio)
    y = alt_linha
    draw.rectangle([0, y, larg_total, y + alt_linha], fill="#2E7D32", outline="white", width=2)
    
    titulos = colunas_dados + ["DIA", "DATA"]
    for i, tit in enumerate(titulos):
        x = i * larg_celula
        draw.rectangle([x, y, x + larg_celula, y + alt_linha], outline="white", width=2)
        draw.text((x + 20, y + 15), tit.upper(), fill="white", font=f_header)

    # Linhas de Dados (Branco com bordas pretas)
    y += alt_linha
    for _, row in df.iterrows():
        for i, tit in enumerate(titulos):
            x = i * larg_celula
            # Desenha a grade
            draw.rectangle([x, y, x + larg_celula, y + alt_linha], outline="#333333", width=2)
            
            # Pega o valor da coluna correspondente
            if tit == "DIA": valor = row['Dia']
            elif tit == "DATA": valor = row['Data'].split('/')[0] # Só o número do dia
            else: valor = str(row[tit])
            
            # Escreve o nome com letra forte
            draw.text((x + 15, y + 15), valor.upper(), fill="black", font=f_texto)
        y += alt_linha

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- APP ---
def main():
    st.set_page_config(page_title="Rodízio CCB", layout="wide")
    
    if 'logged_in' not in st.session_state:
        st.title("⛪ Sistema de Rodízio")
        u = st.text_input("Usuário"); p = st.text_input("Senha", type="password")
        if st.button("Entrar", use_container_width=True):
            res = supabase.table("usuarios").select("*").eq("login", u).eq("senha", hash_senha(p)).execute()
            if res.data: 
                st.session_state.update({'logged_in': True, 'user_id': res.data[0]['id']})
                st.rerun()
    else:
        res_areas = supabase.table("areas").select("*").eq("id_usuario", st.session_state['user_id']).execute().data
        area_n = st.sidebar.selectbox("🎯 Escala", [a['nome_area'] for a in res_areas]) if res_areas else None
        area = next((a for a in res_areas if a['nome_area'] == area_n), None) if area_n else None

        aba = st.sidebar.radio("Menu", ["📅 Gerar Tabela", "📂 Histórico", "👥 Membros", "⚙️ Configurações"])

        if aba == "📅 Gerar Tabela" and area:
            st.title(f"Tabela: {area['nome_area']}")
            
            with st.sidebar.expander("Configurar Geração"):
                d_i = st.date_input("Início")
                d_c = st.multiselect("Dias", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], default=["Sunday"])
                if st.button("Gerar Base"):
                    # Lógica de escala simples para preencher a tabela
                    cargos = [c.strip() for c in area['posicoes'].split(",")]
                    datas = [(d_i + timedelta(days=x)) for x in range(35) if (d_i + timedelta(days=x)).strftime('%A') in d_c]
                    data_final = []
                    for d in datas:
                        item = {"Data": d.strftime("%d/%m"), "Dia": d.strftime("%a").upper(), "_mes": d.strftime("%B/%Y")}
                        for c in cargos: item[c] = ""
                        data_final.append(item)
                    st.session_state['df_edit'] = pd.DataFrame(data_final)

            if 'df_edit' in st.session_state:
                # Editor de tabela para você preencher os nomes
                st.subheader("✍️ Preencha os nomes das irmãs:")
                df_final = st.data_editor(st.session_state['df_edit'], use_container_width=True)
                
                if st.button("💾 GERAR TABELA PARA WHATSAPP", type="primary", use_container_width=True):
                    img_tabela = gerar_tabela_estilo_antigo(df_final)
                    st.image(img_tabela, caption="Esta é a imagem estilo antigo para o grupo")
                    st.download_button("📥 Baixar Tabela", img_tabela, "tabela_rodizio.png", "image/png")
                    
                    # Salva no banco
                    supabase.table("escalas").insert({"id_area": area['id'], "nome_area": area['nome_area'], "dados_escala": df_final.to_json(orient='records')}).execute()

        elif aba == "📂 Histórico" and area:
            st.header("Histórico")
            h = supabase.table("escalas").select("*").eq("id_area", area['id']).order("data_geracao", desc=True).execute().data
            for e in h:
                if st.button(f"Ver escala de {e['data_geracao'][:16]}", key=e['id']):
                    st.session_state['df_edit'] = pd.read_json(io.StringIO(e['dados_escala']))
                    st.rerun()

        elif aba == "👥 Membros":
            st.header("Gestão de Irmãs")
            # Código de gestão de membros aqui (mesmo das versões anteriores)
            st.info("Use esta aba para manter a lista de nomes atualizada.")

        elif aba == "⚙️ Configurações":
            st.header("Configurações")
            # Cadastro de novas escalas (áreas)
            with st.form("nova"):
                n = st.text_input("Nome (Ex: Organistas)"); p = st.text_input("Cargos (Ex: G1, G2, Sentinela)")
                if st.form_submit_button("Salvar"):
                    supabase.table("areas").insert({"id_usuario": st.session_state['user_id'], "nome_area": n, "vagas": len(p.split(",")), "posicoes": p}).execute()
                    st.rerun()

if __name__ == "__main__":
    main()
