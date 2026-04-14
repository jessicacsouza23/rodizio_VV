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

# Cores pastéis e fortes para distinguir bem as salas/cargos
CORES_ESTILO = ["#E8F5E9", "#E3F2FD", "#F3E5F5", "#FFF3E0", "#FFEBEE", "#ECEFF1"]
CORES_BORDAS = ["#2E7D32", "#1565C0", "#6A1B9A", "#EF6C00", "#C62828", "#37474F"]

MESES_PT = {'January': 'Janeiro', 'February': 'Fevereiro', 'March': 'Março', 'April': 'Abril', 'May': 'Maio', 'June': 'Junho',
            'July': 'Julho', 'August': 'Agosto', 'September': 'Setembro', 'October': 'Outubro', 'November': 'Novembro', 'December': 'Dezembro'}
DIAS_PT = {'Monday': 'Seg', 'Tuesday': 'Ter', 'Wednesday': 'Qua', 'Thursday': 'Qui', 'Friday': 'Sex', 'Saturday': 'Sáb', 'Sunday': 'Dom'}

def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

# --- NOVA GERAÇÃO DE IMAGEM (ESTILO GRADE/MURAL) ---
def gerar_imagem_escala_horizontal(df):
    if df.empty: return None
    df = df.astype(str)
    cargos = [c for c in df.columns if c not in ['_mes', 'Data', 'Dia']]
    
    # Configurações de Tamanho
    larg_coluna = 400
    altura_card = 160
    margem = 40
    header_h = 150
    
    num_datas = len(df)
    larg_total = (num_datas * larg_coluna) + (margem * 2)
    alt_total = header_h + (len(cargos) * altura_card) + 200
    
    img = Image.new('RGB', (larg_total, alt_total), color="#FFFFFF")
    draw = ImageDraw.Draw(img)
    
    try:
        f_titulo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
        f_data = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 45)
        f_cargo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 35)
        f_nome = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 45)
    except:
        f_titulo = f_data = f_cargo = f_nome = ImageFont.load_default()

    # Cabeçalho Principal
    draw.rectangle([0, 0, larg_total, 120], fill="#1E1E1E")
    txt_mes = df['_mes'].iloc[0].upper() if '_mes' in df.columns else "RODÍZIO"
    w_m = draw.textlength(txt_mes, font=f_titulo)
    draw.text(((larg_total-w_m)/2, 30), txt_mes, fill="white", font=f_titulo)

    x_offset = margem
    for _, row in df.iterrows():
        # Cabeçalho da Coluna (Data)
        draw.rectangle([x_offset, header_h-20, x_offset+larg_coluna-20, header_h+60], fill="#333333", outline="black", width=2)
        txt_d = f"{row['Data']} ({row['Dia']})"
        w_d = draw.textlength(txt_d, font=f_data)
        draw.text((x_offset + (larg_coluna-w_d)/2 - 10, header_h), txt_d, fill="white", font=f_data)
        
        y_offset = header_h + 100
        for idx, cargo in enumerate(cargos):
            cor_bg = CORES_ESTILO[idx % len(CORES_ESTILO)]
            cor_bd = CORES_BORDAS[idx % len(CORES_BORDAS)]
            
            # Card do Cargo
            box = [x_offset, y_offset, x_offset+larg_coluna-20, y_offset+altura_card-20]
            draw.rectangle(box, fill=cor_bg, outline=cor_bd, width=4)
            
            # Texto Cargo (Pequeno/Bold)
            draw.text((x_offset+15, y_offset+15), cargo.upper(), fill=cor_bd, font=f_cargo)
            # Nome (Grande)
            nome_aluna = str(row[cargo])
            draw.text((x_offset+15, y_offset+65), nome_aluna, fill="black", font=f_nome)
            
            y_offset += altura_card
        
        x_offset += larg_coluna

    buf = io.BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()

# --- LÓGICA DE NEGÓCIO ---
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
            m_en = data_atual.strftime('%B'); m_pt = MESES_PT.get(m_en, m_en)
            linha = {"Data": data_atual.strftime('%d/%m'), "Dia": DIAS_PT[dia_s], "_mes": f"{m_pt} / {data_atual.year}"}
            ids_hoje = []
            for i in range(vagas):
                p_nome = pos_list[i] if i < len(pos_list) else f"Vaga {i+1}"
                linha[p_nome] = ""
                for idx, m in enumerate(membros):
                    if m['id'] not in ids_hoje: # Simplificado para o exemplo
                        linha[p_nome] = m['nome']; ids_hoje.append(m['id'])
                        membros.append(membros.pop(idx)); break
            escala_data.append(linha)
        data_atual += timedelta(days=1)
    return pd.DataFrame(escala_data)

# --- APP ---
def main():
    st.set_page_config(page_title="CCB Rodízio", layout="wide")
    
    if 'logged_in' not in st.session_state:
        st.title("⛪ Login")
        u = st.text_input("Usuário"); p = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            res = supabase.table("usuarios").select("*").eq("login", u).eq("senha", hash_senha(p)).execute()
            if res.data: st.session_state.update({'logged_in': True, 'user_id': res.data[0]['id'], 'user_login': res.data[0]['login']}); st.rerun()
    else:
        res_areas = supabase.table("areas").select("*").eq("id_usuario", st.session_state['user_id']).execute().data
        area_n = st.sidebar.selectbox("🎯 Escolha a Escala", [a['nome_area'] for a in res_areas], key="main_sel") if res_areas else None
        area = next((a for a in res_areas if a['nome_area'] == area_n), None) if area_n else None
        
        aba = st.sidebar.radio("Menu", ["📅 Rodízio Atual", "📂 Histórico", "⚙️ Configurações"])
        
        if aba == "📅 Rodízio Atual" and area:
            st.title(f"Mural: {area['nome_area']}")
            
            with st.expander("🛠️ Parâmetros de Geração"):
                c1, c2, c3 = st.columns(3)
                m = c1.number_input("Meses", 1, 2, 1)
                d_i = c2.date_input("Início")
                d_c = c3.multiselect("Dias", list(DIAS_PT.keys()), default=["Sunday"], format_func=lambda x: DIAS_PT[x])
                if st.button("Gerar Nova Base"):
                    st.session_state['df_edit'] = gerar_escala_logica(area, d_i, m, d_c)

            if 'df_edit' in st.session_state:
                st.subheader("📝 Edição e Visualização")
                df_final = st.data_editor(st.session_state['df_edit'], use_container_width=True)
                
                # Visualização Estilo Mural (Igual a imagem que você gostou)
                st.markdown("### 🖼️ Prévia do Mural (Lado a Lado)")
                cargos_v = [c for c in df_final.columns if c not in ['_mes', 'Data', 'Dia']]
                
                # Criar colunas dinâmicas na tela
                cols_tela = st.columns(len(df_final))
                for i, (_, row) in enumerate(df_final.iterrows()):
                    with cols_tela[i]:
                        st.markdown(f"""
                        <div style="background-color: #333; color: white; padding: 10px; border-radius: 5px 5px 0 0; text-align: center; font-weight: bold;">
                            {row['Data']} ({row['Dia']})
                        </div>
                        """, unsafe_allow_html=True)
                        for idx, cg in enumerate(cargos_v):
                            cor = CORES_BORDAS[idx % len(CORES_BORDAS)]
                            bg = CORES_ESTILO[idx % len(CORES_ESTILO)]
                            st.markdown(f"""
                            <div style="border-left: 5px solid {cor}; background-color: {bg}; padding: 10px; margin-bottom: 5px; border-right: 1px solid #ddd; border-bottom: 1px solid #ddd;">
                                <small style="color: {cor}; font-weight: bold;">{cg}</small><br>
                                <b style="font-size: 18px;">{row[cg]}</b>
                            </div>
                            """, unsafe_allow_html=True)

                if st.button("💾 SALVAR E GERAR IMAGEM"):
                    img_bytes = gerar_imagem_escala_horizontal(df_final)
                    supabase.table("escalas").insert({"id_area": area['id'], "nome_area": area['nome_area'], "dados_escala": df_final.to_json(orient='records')}).execute()
                    st.image(img_bytes, caption="Imagem para WhatsApp")
                    st.download_button("📥 Baixar Imagem para WhatsApp", img_bytes, "mural_ccb.png", "image/png")

        elif aba == "⚙️ Configurações":
            st.subheader("Cadastro de Áreas/Cargos")
            with st.form("nova_area"):
                n = st.text_input("Nome da Escala (Ex: Escolinha Sábado)")
                v = st.number_input("Número de Salas/Vagas", 1, 10, 2)
                p = st.text_input("Nomes das Salas (ex: Sala 1, Sala 2, Teoria)")
                if st.form_submit_button("Criar Escala"):
                    supabase.table("areas").insert({"id_usuario": st.session_state['user_id'], "nome_area": n, "vagas": v, "posicoes": p}).execute()
                    st.success("Criado!")
                    st.rerun()

if __name__ == "__main__":
    main()
