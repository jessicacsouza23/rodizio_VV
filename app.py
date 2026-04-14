# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, timedelta
from supabase import create_client, Client
from PIL import Image, ImageDraw, ImageFont
import io

# --- CONEXÃO E TRADUÇÕES ---
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

# --- GERAÇÃO DE IMAGEM COM FONTE EXTRA GRANDE (PARA LER NO ZAP) ---
def gerar_imagem_escala(df):
    if df.empty: return None
    
    # Filtra colunas: Data e Dia primeiro, depois o resto
    cargos = [c for c in df.columns if c not in ['_mes', 'Data', 'Dia']]
    colunas_finais = ["DATA", "DIA"] + cargos
    
    # Aumentei muito a largura e altura para a fonte poder crescer
    LARG_COL = 450  
    ALT_LINHA = 140 
    MARGEM_TOP = 150
    
    larg_total = len(colunas_finais) * LARG_COL
    alt_total = (len(df) * ALT_LINHA) + MARGEM_TOP + 50
    
    img = Image.new('RGB', (larg_total, alt_total), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    try:
        # Usando tamanhos de fonte muito maiores (80px a 90px)
        f_titulo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 90)
        f_header = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 65)
        f_corpo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 85)
    except:
        f_titulo = f_header = f_corpo = ImageFont.load_default()

    # Cabeçalho Principal (Mês)
    draw.rectangle([0, 0, larg_total, MARGEM_TOP], fill="#1B5E20")
    txt_mes = str(df['_mes'].iloc[0]).upper() if '_mes' in df.columns else "RODÍZIO"
    draw.text((40, 30), txt_mes, fill="white", font=f_titulo)

    # Nomes das Colunas
    y = MARGEM_TOP
    for i, col in enumerate(colunas_finais):
        x = i * LARG_COL
        # Borda grossa (width=5) para separação clara
        draw.rectangle([x, y, x + LARG_COL, y + ALT_LINHA], fill="#2E7D32", outline="white", width=5)
        draw.text((x + 20, y + 35), col.upper(), fill="white", font=f_header)

    # Linhas dos Dados (Nomes das Irmãs)
    y += ALT_LINHA
    for _, row in df.iterrows():
        for i, col in enumerate(colunas_finais):
            x = i * LARG_COL
            draw.rectangle([x, y, x + LARG_COL, y + ALT_LINHA], outline="black", width=3)
            
            # Formatação curta para caber
            if col == "DATA": val = str(row['Data']).split('/')[0]
            elif col == "DIA": val = str(row['Dia'])[0].upper()
            else: val = str(row[col])
            
            # Texto centralizado na célula
            draw.text((x + 25, y + 25), val.upper(), fill="black", font=f_corpo)
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

# --- INTERFACE ---
def main():
    st.set_page_config(page_title="CCB Escala", layout="wide")
    
    if 'logged_in' not in st.session_state:
        st.title("⛪ Sistema de Rodízio")
        u = st.text_input("Usuário"); p = st.text_input("Senha", type="password")
        if st.button("Entrar", use_container_width=True):
            res = supabase.table("usuarios").select("*").eq("login", u).eq("senha", hash_senha(p)).execute()
            if res.data: 
                st.session_state.update({'logged_in': True, 'user_id': res.data[0]['id']})
                st.rerun()
    else:
        # Sidebar e Menus
        res_areas = supabase.table("areas").select("*").eq("id_usuario", st.session_state['user_id']).execute()
        area = None
        if res_areas.data:
            sel = st.sidebar.selectbox("Selecione o Grupo", [a['nome_area'] for a in res_areas.data])
            area = next(a for a in res_areas.data if a['nome_area'] == sel)
        
        aba = st.sidebar.radio("Navegação", ["📅 Gerar Rodízio", "📂 Histórico", "👥 Membros", "⚙️ Áreas"])
        
        if aba == "📅 Gerar Rodízio" and area:
            st.header(f"Rodízio: {area['nome_area']}")
            
            with st.expander("Configurar Novo Período"):
                c1, c2, c3 = st.columns(3)
                m = c1.selectbox("Meses", [1, 2, 3])
                d_i = c2.date_input("Data Inicial")
                d_c = c3.multiselect("Dias de Culto", DIAS_ORDEM, default=["Sunday"], format_func=lambda x: DIAS_TRADUCAO[x])
                if st.button("Gerar Tabela"):
                    st.session_state['df_edit'] = gerar_escala_logica(area, d_i, m, d_c)

            if 'df_edit' in st.session_state:
                st.subheader("Edite os nomes se necessário:")
                df_final = st.data_editor(st.session_state['df_edit'], use_container_width=True, num_rows="dynamic")
                
                if st.button("💾 SALVAR E GERAR IMAGEM GIGANTE", type="primary", use_container_width=True):
                    supabase.table("escalas").insert({"id_area": area['id'], "nome_area": area['nome_area'], "dados_escala": df_final.to_json(orient='records')}).execute()
                    
                    # Gera imagem com a nova função de fonte grande
                    img_ready = gerar_imagem_escala(df_final)
                    st.image(img_ready, caption="Agora com letra grande para WhatsApp")
                    st.download_button("📥 Baixar Imagem Legível", img_ready, "rodizio_ok.png", "image/png")

        elif aba == "📂 Histórico" and area:
            st.header("Escalas Antigas")
            h = supabase.table("escalas").select("*").eq("id_area", area['id']).order("data_geracao", desc=True).execute()
            for e in h.data:
                with st.container(border=True):
                    st.write(f"📅 Criada em: {e['data_geracao'][:16]}")
                    df_h = pd.read_json(io.StringIO(e['dados_escala']))
                    img_h = gerar_imagem_escala(df_h)
                    st.download_button("📸 Baixar Imagem Grande", img_h, f"escala_{e['id']}.png", "image/png", key=f"h_{e['id']}")

if __name__ == "__main__":
    main()
