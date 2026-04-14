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

# --- NOVA FUNÇÃO DE FONTE ADAPTÁVEL ---
def ajustar_fonte(draw, texto, largura_max, tamanho_base=85):
    """Reduz o tamanho da fonte dinamicamente se o texto for muito largo"""
    tamanho = tamanho_base
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    try:
        font = ImageFont.truetype(font_path, tamanho)
    except:
        return ImageFont.load_default()
    
    # Reduz a fonte de 2 em 2 pixels até caber na coluna (com margem de segurança)
    while draw.textlength(texto, font=font) > (largura_max - 30) and tamanho > 20:
        tamanho -= 2
        font = ImageFont.truetype(font_path, tamanho)
    return font

# --- GERAÇÃO DE IMAGEM COM REDIMENSIONAMENTO AUTOMÁTICO ---
def gerar_imagem_escala(df):
    if df.empty: return None
    
    # Seleciona colunas úteis para a imagem
    colunas_foto = [c for c in df.columns if c not in ['_mes']]
    
    LARG_COL = 400  
    ALT_LINHA = 130 
    MARGEM_TOPO = 130
    
    larg_total = len(colunas_foto) * LARG_COL
    alt_total = (len(df) * ALT_LINHA) + MARGEM_TOPO + 50
    
    img = Image.new('RGB', (larg_total, alt_total), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font_path_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    # Título do Mês (Faixa Superior)
    draw.rectangle([0, 0, larg_total, MARGEM_TOPO], fill=(27, 94, 32))
    txt_mes = f"RODÍZIO: {str(df['_mes'].iloc[0]).upper()}"
    try:
        f_titulo = ImageFont.truetype(font_path_bold, 75)
    except:
        f_titulo = ImageFont.load_default()
    
    w_t = draw.textlength(txt_mes, font=f_titulo)
    draw.text(((larg_total - w_t)/2, 25), txt_mes, fill="white", font=f_titulo)

    # Cabeçalho das Colunas
    y = MARGEM_TOPO
    for i, col in enumerate(colunas_foto):
        x = i * LARG_COL
        draw.rectangle([x, y, x + LARG_COL, y + 80], fill=(56, 142, 60), outline="white", width=2)
        txt_col = col.upper()
        f_col = ajustar_fonte(draw, txt_col, LARG_COL, 50)
        w_c = draw.textlength(txt_col, font=f_col)
        draw.text((x + (LARG_COL - w_c)/2, y + 15), txt_col, fill="white", font=f_col)

    # Linhas de Dados (Ajuste por Célula)
    y += 80
    for idx, row in df.iterrows():
        # Efeito zebrado leve
        cor_fundo = (245, 245, 245) if idx % 2 == 0 else (255, 255, 255)
        draw.rectangle([0, y, larg_total, y + ALT_LINHA], fill=cor_fundo)
        
        for i, col in enumerate(colunas_foto):
            x = i * LARG_COL
            draw.rectangle([x, y, x + LARG_COL, y + ALT_LINHA], outline=(200, 200, 200), width=1)
            
            conteudo = str(row[col]).upper()
            if col == "Data": conteudo = conteudo.split('/')[0] # Apenas o dia numérico
            
            # Fonte calculada para este nome específico nesta célula
            f_dinamica = ajustar_fonte(draw, conteudo, LARG_COL, 80)
            
            w_n = draw.textlength(conteudo, font=f_dinamica)
            # Centralização vertical e horizontal
            draw.text((x + (LARG_COL - w_n)/2, y + 25), conteudo, fill="black", font=f_dinamica)
        y += ALT_LINHA

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- LÓGICA DE ESCALA E LOGIN (MANTIDA) ---
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
                    if m['id'] not in ids_hoje and membro_disponivel(m['id'], data_atual):
                        linha[p_nome] = m['nome']; ids_hoje.append(m['id'])
                        fila_membros.append(fila_membros.pop(idx)); break
            escala_data.append(linha)
        data_atual += timedelta(days=1)
    return pd.DataFrame(escala_data)

def main():
    st.set_page_config(page_title="CCB Rodízio", layout="wide")
    
    if 'logged_in' not in st.session_state:
        st.title("⛪ Acesso ao Sistema")
        u = st.text_input("Login"); p = st.text_input("Senha", type="password")
        if st.button("Entrar", use_container_width=True):
            res = supabase.table("usuarios").select("*").eq("login", u).eq("senha", hash_senha(p)).execute()
            if res.data: 
                st.session_state.update({'logged_in': True, 'user_id': res.data[0]['id']})
                st.rerun()
    else:
        # Carregamento de dados
        res_areas = supabase.table("areas").select("*").eq("id_usuario", st.session_state['user_id']).execute()
        area = None
        if res_areas.data:
            sel = st.sidebar.selectbox("Escolha a Área", [a['nome_area'] for a in res_areas.data])
            area = next(a for a in res_areas.data if a['nome_area'] == sel)
        
        aba = st.sidebar.radio("Navegação", ["📅 Gerar Escala", "📂 Histórico", "👥 Membros"])
        
        if aba == "📅 Gerar Escala" and area:
            st.header(f"Organizando: {area['nome_area']}")
            with st.expander("Parâmetros do Rodízio"):
                c1, c2, c3 = st.columns(3)
                m = c1.selectbox("Duração (Meses)", [1, 2, 3])
                d_i = c2.date_input("Data de Início")
                d_c = c3.multiselect("Dias de Culto", DIAS_ORDEM, default=["Sunday"], format_func=lambda x: DIAS_TRADUCAO[x])
                if st.button("Criar Rascunho"):
                    st.session_state['df_edit'] = gerar_escala_logica(area, d_i, m, d_c)

            if 'df_edit' in st.session_state:
                st.info("Você pode clicar nos nomes abaixo para ajustar manualmente antes de salvar.")
                df_final = st.data_editor(st.session_state['df_edit'], use_container_width=True)
                
                if st.button("✅ FINALIZAR E GERAR IMAGEM PARA WHATSAPP", type="primary", use_container_width=True):
                    # Salva no banco
                    supabase.table("escalas").insert({
                        "id_area": area['id'], 
                        "nome_area": area['nome_area'], 
                        "dados_escala": df_final.to_json(orient='records')
                    }).execute()
                    
                    # Gera e exibe a imagem redimensionável
                    img_bytes = gerar_imagem_escala(df_final)
                    st.image(img_bytes, caption="Visualização da Imagem Final")
                    st.download_button("📥 Baixar Imagem para Enviar", img_bytes, "escala_ccb.png", "image/png")

if __name__ == "__main__":
    main()
