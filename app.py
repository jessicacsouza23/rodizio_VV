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

# --- NOVA GERAÇÃO DE IMAGEM (FONTE GIGANTE ESTILO CLÁSSICO) ---
def gerar_imagem_escala(df):
    if df.empty: return None
    
    # Prepara colunas: Data e Dia primeiro, depois os cargos
    cargos = [c for c in df.columns if c not in ['_mes', 'Data', 'Dia']]
    colunas_finais = ["DATA", "DIA"] + cargos
    
    # Configurações de tamanho para leitura fácil no celular
    LARG_CELULA = 380
    ALT_LINHA = 120
    MARGEM = 20
    
    larg_total = (len(colunas_finais) * LARG_CELULA)
    alt_total = (len(df) + 2) * ALT_LINHA + 100
    
    img = Image.new('RGB', (larg_total, alt_total), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    try:
        # Fontes robustas
        f_titulo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 70)
        f_header = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 55)
        f_corpo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 75)
    except:
        f_titulo = f_header = f_corpo = ImageFont.load_default()

    # 1. Faixa do Mês (Verde Escuro)
    draw.rectangle([0, 0, larg_total, ALT_LINHA], fill="#1B5E20")
    txt_mes = str(df['_mes'].iloc[0]).upper() if '_mes' in df.columns else "RODÍZIO"
    draw.text((30, 25), txt_mes, fill="white", font=f_titulo)

    # 2. Cabeçalho das Colunas (Verde Médio)
    y = ALT_LINHA
    for i, col in enumerate(colunas_finais):
        x = i * LARG_CELULA
        draw.rectangle([x, y, x + LARG_CELULA, y + ALT_LINHA], fill="#2E7D32", outline="white", width=3)
        draw.text((x + 20, y + 30), col, fill="white", font=f_header)

    # 3. Linhas das Irmãs (Texto Grande)
    y += ALT_LINHA
    for _, row in df.iterrows():
        for i, col in enumerate(colunas_finais):
            x = i * LARG_CELULA
            # Borda da célula
            draw.rectangle([x, y, x + LARG_CELULA, y + ALT_LINHA], outline="black", width=2)
            
            # Valor (Data pega só o dia, Dia pega só a letra)
            if col == "DATA": val = str(row['Data']).split('/')[0]
            elif col == "DIA": val = str(row['Dia'])[0].upper()
            else: val = str(row[col])
            
            draw.text((x + 25, y + 20), val.upper(), fill="black", font=f_corpo)
        y += ALT_LINHA

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- LÓGICA DE FILTRAGEM (MANTIDA) ---
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
    membros_res = supabase.table("membros").select("*").in_id(ids).order("total_servicos").order("ultimo_servico").execute()
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

# --- APP PRINCIPAL ---
def main():
    st.set_page_config(page_title="CCB Escala", layout="wide")
    
    if 'logged_in' not in st.session_state:
        st.title("⛪ Gestão de Escalas")
        u = st.text_input("Usuário"); p = st.text_input("Senha", type="password")
        if st.button("Entrar", use_container_width=True):
            res = supabase.table("usuarios").select("*").eq("login", u).eq("senha", hash_senha(p)).execute()
            if res.data: 
                st.session_state.update({'logged_in': True, 'user_id': res.data[0]['id']})
                st.rerun()
    else:
        # Sidebar
        areas_res = supabase.table("areas").select("*").eq("id_usuario", st.session_state['user_id']).execute()
        area = None
        if areas_res.data:
            sel = st.sidebar.selectbox("Escala Ativa", [a['nome_area'] for a in areas_res.data])
            area = next(a for a in areas_res.data if a['nome_area'] == sel)
        
        aba = st.sidebar.radio("Navegação", ["Gerar & Editar", "Histórico", "Membros", "Afastamentos", "Configurar Áreas"])
        if st.sidebar.button("Sair"): st.session_state.clear(); st.rerun()

        # ABA: GERAR & EDITAR
        if aba == "Gerar & Editar" and area:
            st.header(f"✍️ Editor: {area['nome_area']}")
            
            with st.expander("1️⃣ Configurar Período"):
                c1, c2, c3 = st.columns(3)
                m = c1.selectbox("Meses", [1,2,3])
                d_ini = c2.date_input("Início")
                dias = c3.multiselect("Dias de Culto", DIAS_ORDEM, default=["Sunday"], format_func=lambda x: DIAS_TRADUCAO[x])
                if st.button("Gerar Nova Sugestão"):
                    st.session_state['df_edit'] = gerar_escala_logica(area, d_ini, m, dias)

            if 'df_edit' in st.session_state:
                st.subheader("2️⃣ Ajuste os nomes e clique em Salvar")
                df_final = st.data_editor(st.session_state['df_edit'], use_container_width=True, num_rows="dynamic")
                
                if st.button("💾 SALVAR E GERAR IMAGEM", type="primary", use_container_width=True):
                    # Salva no banco
                    supabase.table("escalas").insert({"id_area": area['id'], "nome_area": area['nome_area'], "dados_escala": df_final.to_json(orient='records')}).execute()
                    st.success("Salvo!")
                    
                    # Gera a imagem na hora
                    img_bytes = gerar_imagem_escala(df_final)
                    st.image(img_bytes, caption="Prévia da Imagem para o WhatsApp")
                    st.download_button("📥 BAIXAR IMAGEM (FONTE GRANDE)", img_bytes, "rodizio.png", "image/png")

        # ABA: HISTÓRICO
        elif aba == "Histórico" and area:
            st.header("📜 Escalas Salvas")
            h = supabase.table("escalas").select("*").eq("id_area", area['id']).order("data_geracao", desc=True).execute()
            for e in h.data:
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"📅 Criada em: {e['data_geracao'][:16]}")
                    df_h = pd.read_json(io.StringIO(e['dados_escala']))
                    img_h = gerar_imagem_escala(df_h)
                    c2.download_button("📸 Baixar PNG", img_h, f"escala_{e['id']}.png", "image/png", key=f"btn_{e['id']}")

        # Outras abas mantidas conforme seu código original...
        elif aba == "Membros":
            st.subheader("Gerenciar Membros")
            # Seu código de membros aqui...
            
        elif aba == "Configurar Áreas":
            st.subheader("Novas Escalas")
            # Seu código de cargos/áreas aqui...

if __name__ == "__main__":
    main()
