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

# Cores vibrantes para os Cards da Interface
CORES_CARDS = ["#2E7D32", "#1565C0", "#6A1B9A", "#EF6C00", "#C62828", "#37474F"]

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

# --- GERAÇÃO DE IMAGEM PARA WHATSAPP (ESTILO MURAL) ---
def gerar_imagem_escala(df):
    if df.empty: return None
    df = df.astype(str)
    colunas_dados = [c for c in df.columns if c not in ['_mes', 'Data', 'Dia']]
    
    larg_total = 1200
    alt_total = (len(df) * (len(colunas_dados) * 110 + 150)) + 200
    img = Image.new('RGB', (larg_total, alt_total), color="#FFFFFF")
    draw = ImageDraw.Draw(img)
    
    try:
        f_titulo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 65)
        f_data = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 55)
        f_cargo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 45)
        f_nome = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 52)
    except:
        f_titulo = f_data = f_cargo = f_nome = ImageFont.load_default()

    draw.rectangle([0, 0, larg_total, 130], fill="#333333")
    txt_header = df['_mes'].iloc[0].upper() if '_mes' in df.columns else "RODÍZIO"
    w_h = draw.textlength(txt_header, font=f_titulo)
    draw.text(((larg_total-w_h)/2, 30), txt_header, fill="white", font=f_titulo)

    y = 180
    for _, row in df.iterrows():
        draw.rectangle([40, y, larg_total-40, y+80], fill="#E0E0E0")
        txt_d = f"{row['Data']} - {row['Dia'].upper()}"
        draw.text((60, y+10), txt_d, fill="black", font=f_data)
        y += 120
        
        for idx, col in enumerate(colunas_dados):
            cor = CORES_CARDS[idx % len(CORES_CARDS)]
            draw.rectangle([60, y, larg_total-60, y+100], outline=cor, width=3)
            draw.rectangle([60, y, 250, y+100], fill=cor)
            draw.text((70, y+25), col.upper()[:10], fill="white", font=f_cargo)
            draw.text((270, y+20), str(row[col]), fill="black", font=f_nome)
            y += 115
        y += 80

    buf = io.BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()

# --- LÓGICA DE MEMBROS ---
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
    membros = supabase.table("membros").select("*").in_("id", ids).order("total_servicos").order("ultimo_servico").execute().data
    
    while data_atual <= data_fim:
        dia_s = data_atual.strftime('%A')
        if dia_s in dias_culto:
            m_en = data_atual.strftime('%B'); m_pt = MESES_TRADUCAO.get(m_en, m_en)
            linha = {"Data": data_atual.strftime('%d/%m/%Y'), "Dia": DIAS_TRADUCAO[dia_s], "_mes": f"{m_pt} / {data_atual.year}"}
            ids_hoje = []
            for i in range(vagas):
                p_nome = pos_list[i] if i < len(pos_list) else f"Vaga {i+1}"
                linha[p_nome] = ""
                for idx, m in enumerate(membros):
                    if m['id'] not in ids_hoje and membro_disponivel(m['id'], data_atual):
                        linha[p_nome] = m['nome']; ids_hoje.append(m['id'])
                        membros.append(membros.pop(idx)); break
            escala_data.append(linha)
        data_atual += timedelta(days=1)
    return pd.DataFrame(escala_data)

# --- INTERFACE ---
def main():
    st.set_page_config(page_title="CCB Escala", layout="wide")
    
    if 'logged_in' not in st.session_state:
        st.title("⛪ Gestão de Escalas")
        u = st.text_input("Usuário"); p = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            res = supabase.table("usuarios").select("*").eq("login", u).eq("senha", hash_senha(p)).execute()
            if res.data: st.session_state.update({'logged_in': True, 'user_id': res.data[0]['id']}); st.rerun()
            else: st.error("Erro.")
    else:
        # Carrega Área Ativa
        areas = supabase.table("areas").select("*").eq("id_usuario", st.session_state['user_id']).execute().data
        area = next(a for a in areas if a['nome_area'] == st.sidebar.selectbox("Escala Ativa", [a['nome_area'] for a in areas])) if areas else None
        aba = st.sidebar.radio("Navegação", ["Gerar & Editar", "Histórico", "Membros", "Afastamentos", "Config"])

        if aba == "Gerar & Editar" and area:
            st.title(f"✍️ Rodízio: {area['nome_area']}")
            
            # Painel de Controle Superior
            c1, c2, c3, c4 = st.columns([1,1,1,1])
            meses = c1.number_input("Meses", 1, 6, 1)
            data_i = c2.date_input("Início")
            dias_c = c3.multiselect("Dias", DIAS_ORDEM, default=["Sunday"], format_func=lambda x: DIAS_TRADUCAO[x])
            if c4.button("⚡ Gerar Nova Sugestão", use_container_width=True):
                st.session_state['df_edit'] = gerar_escala_logica(area, data_i, meses, dias_c)

            if 'df_edit' in st.session_state:
                # Editor Oculto (Expander) para não poluir a tela
                with st.expander("📝 Abrir Planilha para Ajustes Manuais"):
                    df_final = st.data_editor(st.session_state['df_edit'], num_rows="dynamic", use_container_width=True)
                    if st.button("💾 Salvar Esta Escala"):
                        supabase.table("escalas").insert({"id_area": area['id'], "nome_area": area['nome_area'], "dados_escala": df_final.to_json(orient='records')}).execute()
                        st.success("Salvo com sucesso!")
                
                st.divider()
                st.subheader("👀 Visualização do Rodízio")
                
                # GRID DE CARDS (Onde a mágica acontece)
                vagas_cols = [c for c in df_final.columns if c not in ['_mes', 'Data', 'Dia']]
                
                for _, row in df_final.iterrows():
                    # Bloco de Data (Um por linha)
                    st.markdown(f"### 🗓️ {row['Data']} - {row['Dia']}")
                    
                    # Colunas para os Cargos (Lado a Lado)
                    cols = st.columns(len(vagas_cols))
                    for i, cargo in enumerate(vagas_cols):
                        cor = CORES_CARDS[i % len(CORES_CARDS)]
                        with cols[i]:
                            st.markdown(f"""
                            <div style="background-color: {cor}; padding: 20px; border-radius: 10px; color: white; text-align: center; min-height: 120px;">
                                <small style="text-transform: uppercase; opacity: 0.8;">{cargo}</small><br>
                                <strong style="font-size: 26px;">{row[cargo]}</strong>
                            </div>
                            """, unsafe_allow_html=True)
                    st.write("") # Espaço entre datas

        elif aba == "Histórico" and area:
            st.header("📂 Escalas Salvas")
            h = supabase.table("escalas").select("*").eq("id_area", area['id']).order("data_geracao", desc=True).execute().data
            for e in h.data:
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"📅 Criada em: {e['data_geracao'][:16]}")
                    df_h = pd.read_json(io.StringIO(e['dados_escala']))
                    img = gerar_imagem_escala(df_h)
                    c2.download_button("📸 Baixar Imagem", img, f"escala_{e['id']}.png", "image/png", key=f"dl_{e['id']}")
                    if st.button("👁️ Abrir", key=f"op_{e['id']}"): 
                        st.session_state['df_edit'] = df_h
                        st.rerun()

        # [Abas de Membros, Afastamentos e Configurações seguem a lógica dos blocos anteriores]
        # (Código omitido por brevidade, mas você deve manter as funções de insert/update neles)

if __name__ == "__main__":
    main()
