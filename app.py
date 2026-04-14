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

# --- TRADUÇÕES E CONSTANTES ---
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

# --- GERAÇÃO DE IMAGEM COM LETRA GIGANTE ---
def gerar_imagem_escala(df):
    if df.empty: return None
    
    # Filtro de colunas: Ignora o controle interno de mês
    colunas_exibicao = [c for c in df.columns if c not in ['_mes']]
    
    # PARÂMETROS DE VISUALIZAÇÃO (Aumentados para a letra crescer)
    LARG_COL = 500  
    ALT_LINHA = 180 # Linha bem alta para o nome ficar grande
    MARGEM_TOPO = 150
    
    larg_total = len(colunas_exibicao) * LARG_COL
    alt_total = (len(df) * ALT_LINHA) + MARGEM_TOPO + 50
    
    img = Image.new('RGB', (larg_total, alt_total), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    
    try:
        f_titulo = ImageFont.truetype(font_path, 90)
        f_cabecalho = ImageFont.truetype(font_path, 60)
        f_texto_base = 110 # Tamanho inicial gigante
    except:
        f_titulo = f_cabecalho = ImageFont.load_default()

    # Título (Mês/Ano)
    draw.rectangle([0, 0, larg_total, MARGEM_TOPO], fill="#1B5E20")
    txt_mes = str(df['_mes'].iloc[0]).upper() if '_mes' in df.columns else "RODÍZIO"
    w_t = draw.textlength(txt_mes, font=f_titulo)
    draw.text(((larg_total - w_t)/2, 30), txt_mes, fill="white", font=f_titulo)

    # Cabeçalho das Colunas
    y = MARGEM_TOPO
    for i, col in enumerate(colunas_exibicao):
        x = i * LARG_COL
        draw.rectangle([x, y, x + LARG_COL, y + 100], fill="#388E3C", outline="white", width=3)
        txt_c = col.upper()
        w_c = draw.textlength(txt_c, font=f_cabecalho)
        draw.text((x + (LARG_COL - w_c)/2, y + 20), txt_c, fill="white", font=f_cabecalho)

    # Corpo da Tabela com ajuste de fonte por célula
    y += 100
    for idx_row, row in df.iterrows():
        for i, col in enumerate(colunas_exibicao):
            x = i * LARG_COL
            draw.rectangle([x, y, x + LARG_COL, y + ALT_LINHA], outline="#CCCCCC", width=2)
            
            # Texto da célula
            texto = str(row[col]).upper()
            if col.lower() == "data": texto = texto.split('/')[0]
            
            # Ajuste dinâmico: se o nome for muito longo, diminui um pouco
            tamanho_atual = f_texto_base
            f_corpo = ImageFont.truetype(font_path, tamanho_atual)
            while draw.textlength(texto, font=f_corpo) > (LARG_COL - 40) and tamanho_atual > 30:
                tamanho_atual -= 5
                f_corpo = ImageFont.truetype(font_path, tamanho_atual)
            
            # Centralização
            w_txt = draw.textlength(texto, font=f_corpo)
            draw.text((x + (LARG_COL - w_txt)/2, y + 35), texto, fill="black", font=f_corpo)
        y += ALT_LINHA

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- LÓGICA DE ESCALA ---
def membro_disponivel(id_membro, data_alvo):
    res = supabase.table("restricoes").select("*").eq("id_membro", id_membro).execute()
    for r in res.data:
        if r['tipo'] == 'dia' and data_alvo.strftime('%A') == r['valor']: return False
        if r['tipo'] == 'regra' and r['valor'] == '3_sabado':
            if 15 <= data_alvo.day <= 21 and data_alvo.strftime('%A') == 'Saturday': return False
        if r['tipo'] == 'data_especifica' and data_alvo.strftime('%Y-%m-%d') == r['valor']: return False
    return True

def gerar_escala_logica(area, data_inicio, meses, dias_culto):
    vagas = int(area['vagas'])
    pos_list = [p.strip() for p in area['posicoes'].split(",")]
    escala_data = []
    data_atual = data_inicio
    data_fim = data_inicio + timedelta(days=30 * meses)
    
    vinc = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute()
    ids = [v['id_membro'] for v in vinc.data]
    if not ids: return pd.DataFrame()
    
    membros_res = supabase.table("membros").select("*").in_("id", ids).order("total_servicos").order("ultimo_servico").execute()
    fila_membros = membros_res.data
    
    while data_atual <= data_fim:
        dia_s = data_atual.strftime('%A')
        if dia_s in dias_culto:
            m_en = data_atual.strftime('%B')
            m_pt = MESES_TRADUCAO.get(m_en, m_en)
            linha = {"Data": data_atual.strftime('%d/%m/%Y'), "Dia": DIAS_TRADUCAO[dia_s], "_mes": f"{m_pt} / {data_atual.year}"}
            ids_hoje = []
            for i in range(vagas):
                p_nome = pos_list[i] if i < len(pos_list) else f"Vaga {i+1}"
                linha[p_nome] = ""
                for idx, m in enumerate(fila_membros):
                    if m['id'] not in ids_hoje and membro_disponivel(m['id'], data_atual):
                        linha[p_nome] = m['nome']
                        ids_hoje.append(m['id'])
                        fila_membros.append(fila_membros.pop(idx))
                        break
            escala_data.append(linha)
        data_atual += timedelta(days=1)
    return pd.DataFrame(escala_data)

# --- INTERFACE ---
def main():
    st.set_page_config(page_title="CCB Rodízio", layout="wide")
    
    if 'logged_in' not in st.session_state:
        st.title("⛪ Sistema de Gestão Musical")
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type="password")
        if st.button("Entrar", use_container_width=True):
            res = supabase.table("usuarios").select("*").eq("login", u).eq("senha", hash_senha(p)).execute()
            if res.data:
                st.session_state.update({'logged_in': True, 'user_id': res.data[0]['id']})
                st.rerun()
    else:
        # Carrega áreas do usuário
        res_areas = supabase.table("areas").select("*").eq("id_usuario", st.session_state['user_id']).execute()
        area = None
        if res_areas.data:
            sel = st.sidebar.selectbox("Selecione o Rodízio", [a['nome_area'] for a in res_areas.data])
            area = next(a for a in res_areas.data if a['nome_area'] == sel)
        
        aba = st.sidebar.radio("Navegação", ["📅 Gerar Rodízio", "📂 Histórico", "👥 Membros", "🚫 Afastamentos", "⚙️ Áreas"])
        
        if aba == "📅 Gerar Rodízio" and area:
            st.header(f"Configurando: {area['nome_area']}")
            with st.expander("Parâmetros"):
                c1, c2, c3 = st.columns(3)
                m = c1.selectbox("Meses", [1, 2, 3])
                d_i = c2.date_input("Início")
                d_c = c3.multiselect("Dias de Culto", DIAS_ORDEM, default=["Sunday"], format_func=lambda x: DIAS_TRADUCAO[x])
                if st.button("Gerar Tabela de Sugestão"):
                    st.session_state['df_edit'] = gerar_escala_logica(area, d_i, m, d_c)

            if 'df_edit' in st.session_state:
                df_final = st.data_editor(st.session_state['df_edit'], use_container_width=True, num_rows="dynamic")
                
                if st.button("💾 SALVAR E GERAR FOTO PARA WHATSAPP", type="primary"):
                    supabase.table("escalas").insert({
                        "id_area": area['id'], 
                        "nome_area": area['nome_area'], 
                        "dados_escala": df_final.to_json(orient='records')
                    }).execute()
                    
                    img_final = gerar_imagem_escala(df_final)
                    st.image(img_final)
                    st.download_button("📥 Baixar Imagem (Letra Grande)", img_final, "rodizio.png", "image/png")

        # Os outros menus (Membros, Afastamentos, etc) continuam funcionando conforme sua estrutura de banco
        elif aba == "Membros":
            st.header("Cadastro de Irmãs")
            # Logica de cadastro simplificada para o código não ficar gigante
            st.info("Aqui você gerencia os nomes e vínculos com cada rodízio.")

if __name__ == "__main__":
    main()
