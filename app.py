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

# --- FUNÇÃO DE FONTE DINÂMICA ---
def get_font_para_texto(draw, texto, largura_max, altura_max):
    """Calcula o maior tamanho de fonte possível para caber no espaço"""
    tamanho = 80  # Tamanho máximo desejado
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    try:
        font = ImageFont.truetype(font_path, tamanho)
    except:
        return ImageFont.load_default()
        
    # Reduz a fonte até o texto caber na largura da célula (com margem de 20px)
    while draw.textlength(texto, font=font) > (largura_max - 20) and tamanho > 25:
        tamanho -= 2
        font = ImageFont.truetype(font_path, tamanho)
    return font

# --- GERAÇÃO DE IMAGEM COM REDIMENSIONAMENTO ---
def gerar_imagem_escala(df):
    if df.empty: return None
    
    colunas_foto = [c for c in df.columns if c not in ['_mes']]
    
    LARG_COL = 400  
    ALT_LINHA = 130 
    MARGEM_MES = 120
    
    larg_total = len(colunas_foto) * LARG_COL
    alt_total = (len(df) * ALT_LINHA) + MARGEM_MES + 100
    
    img = Image.new('RGB', (larg_total, alt_total), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font_path_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    # 1. Título do Mês
    draw.rectangle([0, 0, larg_total, MARGEM_MES], fill=(30, 30, 30))
    txt_mes = f"MÊS DE {str(df['_mes'].iloc[0]).upper()}"
    f_mes = ImageFont.truetype(font_path_bold, 85)
    w_m = draw.textlength(txt_mes, font=f_mes)
    draw.text(((larg_total - w_m)/2, 20), txt_mes, fill="white", font=f_mes)

    # 2. Cabeçalho
    y = MARGEM_MES
    for i, col in enumerate(colunas_foto):
        x = i * LARG_COL
        draw.rectangle([x, y, x + LARG_COL, y + 80], fill=(60, 60, 60), outline="white", width=2)
        txt_c = col.upper()
        # Fonte dinâmica para o cabeçalho
        f_c = get_font_para_texto(draw, txt_c, LARG_COL, 80)
        w_c = draw.textlength(txt_c, font=f_c)
        draw.text((x + (LARG_COL - w_c)/2, y + 15), txt_c, fill="white", font=f_c)

    # 3. Corpo da Tabela (Nomes das Irmãs)
    y += 80
    for idx_row, row in df.iterrows():
        cor_fundo = (245, 245, 245) if idx_row % 2 == 0 else (255, 255, 255)
        draw.rectangle([0, y, larg_total, y + ALT_LINHA], fill=cor_fundo)
        
        for i, col in enumerate(colunas_foto):
            x = i * LARG_COL
            draw.rectangle([x, y, x + LARG_COL, y + ALT_LINHA], outline=(150, 150, 150), width=1)
            
            texto = str(row[col]).upper()
            # Ajuste de exibição para colunas de data/dia
            if col.lower() == "data": texto = texto.split('/')[0]
            
            # A MAGIA ACONTECE AQUI: A fonte se ajusta ao tamanho do nome
            f_n = get_font_para_texto(draw, texto, LARG_COL, ALT_LINHA)
            
            w_t = draw.textlength(texto, font=f_n)
            # Centraliza o texto na célula
            draw.text((x + (LARG_COL - w_t)/2, y + 25), texto, fill="black", font=f_n)
        y += ALT_LINHA

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- LÓGICA DE FILTRAGEM (ORIGINAL) ---
def membro_disponivel(id_membro, data_alvo, posicao_alvo=None):
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
    membros_res = supabase.table("membros").select("*").in_("id", ids).order("total_servicos").order("ultimo_servico").execute()
    fila_membros = membros_res.data
    while data_atual <= data_fim:
        dia_s = data_atual.strftime('%A')
        if dia_s in dias_culto:
            m_en = data_atual.strftime('%B'); m_pt = MESES_TRADUCAO.get(m_en, m_en)
            linha = {"Data": data_atual.strftime('%d/%m/%Y'), "Dia": DIAS_TRADUCAO[dia_s], "_mes": f"{m_pt} / {data_atual.year}"}
            ids_hoje = []
            for i in range(vagas):
                p_nome = pos_list[i] if i < len(pos_list) else f"Vaga {i+1}"
                linha[p_nome] = ""
                for idx, m in enumerate(fila_membros):
                    if m['id'] not in ids_hoje and membro_disponivel(m['id'], data_atual, p_nome):
                        linha[p_nome] = m['nome']; ids_hoje.append(m['id'])
                        fila_membros.append(fila_membros.pop(idx)); break
            escala_data.append(linha)
        data_atual += timedelta(days=1)
    return pd.DataFrame(escala_data)

def main():
    st.set_page_config(page_title="CCB Escala", layout="wide")
    if 'logged_in' not in st.session_state:
        st.title("⛪ Login")
        u = st.text_input("Usuário"); p = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            res = supabase.table("usuarios").select("*").eq("login", u).eq("senha", hash_senha(p)).execute()
            if res.data: st.session_state.update({'logged_in': True, 'user_id': res.data[0]['id']}); st.rerun()
    else:
        areas_res = supabase.table("areas").select("*").eq("id_usuario", st.session_state['user_id']).execute()
        area = next(a for a in areas_res.data if a['nome_area'] == st.sidebar.selectbox("Escala", [a['nome_area'] for a in areas_res.data])) if areas_res.data else None
        aba = st.sidebar.radio("Menu", ["Gerar & Editar", "Histórico", "Membros", "Afastamentos", "Cargos"])

        if aba == "Gerar & Editar" and area:
            st.header(f"✍️ Editor: {area['nome_area']}")
            with st.expander("Configurar"):
                c1, c2, c3 = st.columns(3)
                m = c1.selectbox("Meses", [1,2,3])
                d_i = c2.date_input("Início")
                dias = c3.multiselect("Dias", DIAS_ORDEM, default=["Sunday"], format_func=lambda x: DIAS_TRADUCAO[x])
                if st.button("Gerar Sugestão"):
                    st.session_state['df_edit'] = gerar_escala_logica(area, d_i, m, dias)

            if 'df_edit' in st.session_state:
                df_final = st.data_editor(st.session_state['df_edit'], use_container_width=True, num_rows="dynamic")
                if st.button("💾 SALVAR E GERAR IMAGEM"):
                    supabase.table("escalas").insert({"id_area": area['id'], "nome_area": area['nome_area'], "dados_escala": df_final.to_json(orient='records')}).execute()
                    img = gerar_imagem_escala(df_final)
                    st.image(img)
                    st.download_button("📥 Baixar Imagem", img, "escala.png", "image/png")

if __name__ == "__main__":
    main()
