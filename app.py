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

# --- FUNÇÕES DE IMAGEM (FONTE SEGURA) ---
def carregar_fonte(tamanho):
    caminhos = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arial.ttf"]
    for p in caminhos:
        try: return ImageFont.truetype(p, tamanho)
        except: continue
    return ImageFont.load_default()

def get_font_adaptavel(draw, texto, larg_max, tamanho_base):
    font = carregar_fonte(tamanho_base)
    if isinstance(font, ImageFont.DefaultFont): return font
    while draw.textlength(texto, font=font) > (larg_max - 40) and tamanho_base > 20:
        tamanho_base -= 2
        font = carregar_fonte(tamanho_base)
    return font

def gerar_imagem_escala(df):
    if df.empty: return None
    cols = [c for c in df.columns if c not in ['_mes']]
    LARG, ALT, TOP = 500, 170, 150
    img = Image.new('RGB', (len(cols)*LARG, (len(df)*ALT)+TOP+50), (255,255,255))
    draw = ImageDraw.Draw(img)
    
    # Cabeçalho Verde
    draw.rectangle([0, 0, img.width, TOP], fill="#1B5E20")
    f_tit = carregar_fonte(80)
    tit = f"RODÍZIO: {str(df['_mes'].iloc[0]).upper()}"
    draw.text(((img.width - draw.textlength(tit, f_tit))/2, 35), tit, fill="white", font=f_tit)

    y = TOP
    for idx, row in df.iterrows():
        for i, col in enumerate(cols):
            x = i * LARG
            draw.rectangle([x, y, x+LARG, y+ALT], outline="#DDD")
            txt = str(row[col]).upper()
            if col == "Data": txt = txt.split('/')[0]
            f = get_font_adaptavel(draw, txt, LARG, 90)
            draw.text((x+(LARG-draw.textlength(txt, f))/2, y+40), txt, fill="black", font=f)
        y += ALT
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- LÓGICA DE ESCALA ---
def membro_disponivel(id_membro, data):
    r = supabase.table("restricoes").select("*").eq("id_membro", id_membro).execute()
    for x in r.data:
        if x['tipo'] == 'dia' and data.strftime('%A') == x['valor']: return False
        if x['tipo'] == 'data_especifica' and data.strftime('%Y-%m-%d') == x['valor']: return False
    return True

def gerar_escala_logica(area, inicio, meses, dias):
    vagas = int(area['vagas']); pos = [p.strip() for p in area['posicoes'].split(",")]
    data_fim = inicio + timedelta(days=30*meses); dados = []; atual = inicio
    m = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute()
    ids = [x['id_membro'] for x in m.data]
    if not ids: return pd.DataFrame()
    fila = supabase.table("membros").select("*").in_("id", ids).order("ultimo_servico").execute().data
    while atual <= data_fim:
        if atual.strftime('%A') in dias:
            m_pt = MESES_TRADUCAO.get(atual.strftime('%B'), atual.strftime('%B'))
            ln = {"Data": atual.strftime('%d/%m/%Y'), "Dia": DIAS_TRADUCAO[atual.strftime('%A')], "_mes": f"{m_pt} / {atual.year}"}
            h_id = []
            for i in range(vagas):
                p_n = pos[i] if i < len(pos) else f"Vaga {i+1}"
                ln[p_n] = ""
                for idx, mb in enumerate(fila):
                    if mb['id'] not in h_id and membro_disponivel(mb['id'], atual):
                        ln[p_n] = mb['nome']; h_id.append(mb['id'])
                        fila.append(fila.pop(idx)); break
            dados.append(ln)
        atual += timedelta(days=1)
    return pd.DataFrame(dados)

# --- APP ---
def main():
    st.set_page_config(page_title="CCB Rodízio", layout="wide")
    if 'logged_in' not in st.session_state:
        st.title("⛪ Login")
        u = st.text_input("Usuário"); p = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            res = supabase.table("usuarios").select("*").eq("login", u).eq("senha", hash_senha(p)).execute()
            if res.data: st.session_state.update({'logged_in':True, 'u_id':res.data[0]['id']}); st.rerun()
    else:
        areas = supabase.table("areas").select("*").eq("id_usuario", st.session_state['u_id']).execute().data
        sel_area = st.sidebar.selectbox("Área", [a['nome_area'] for a in areas]) if areas else None
        area_obj = next((a for a in areas if a['nome_area'] == sel_area), None)
        menu = st.sidebar.radio("Menu", ["📅 Rodízio", "📂 Histórico", "👥 Membros", "🚫 Afastamentos", "⚙️ Configurações"])

        if menu == "📅 Rodízio" and area_obj:
            st.header(f"✍️ Editor: {area_obj['nome_area']}")
            with st.expander("Parâmetros"):
                c1, c2, c3 = st.columns(3)
                m = c1.number_input("Meses", 1, 3, 1); d_i = c2.date_input("Início")
                d_c = c3.multiselect("Dias", DIAS_ORDEM, default=["Sunday"], format_func=lambda x: DIAS_TRADUCAO[x])
                if st.button("Gerar Sugestão"): st.session_state['df'] = gerar_escala_logica(area_obj, d_i, m, d_c)
            if 'df' in st.session_state:
                df_ed = st.data_editor(st.session_state['df'], use_container_width=True)
                if st.button("💾 Salvar e Gerar Imagem"):
                    supabase.table("escalas").insert({"id_area": area_obj['id'], "nome_area": area_obj['nome_area'], "dados_escala": df_ed.to_json(orient='records')}).execute()
                    img = gerar_imagem_escala(df_ed); st.image(img); st.download_button("Baixar", img, "rodizio.png")

        elif menu == "📂 Histórico" and area_obj:
            st.header("Histórico")
            try:
                h = supabase.table("escalas").select("*").eq("id_area", area_obj['id']).execute().data
                for x in h: 
                    with st.expander(f"Salvo em: {x.get('created_at', 'Sem Data')[:10]}"):
                        st.dataframe(pd.read_json(io.StringIO(x['dados_escala'])))
            except: st.error("Erro ao carregar histórico.")

        elif menu == "👥 Membros":
            st.header("Membros")
            mbs = supabase.table("membros").select("*").execute().data
            st.table(pd.DataFrame(mbs))

        elif menu == "🚫 Afastamentos":
            st.header("Afastamentos")
            afs = supabase.table("restricoes").select("*, membros(nome)").execute().data
            st.table(pd.DataFrame(afs))

        elif menu == "⚙️ Configurações":
            st.header("Configurar Áreas e Cargos")
            if areas:
                df_areas = pd.DataFrame(areas)
                st.write("Cargos atuais (separe por vírgula):")
                df_edt_areas = st.data_editor(df_areas, column_order=("nome_area", "vagas", "posicoes"), use_container_width=True)
                if st.button("Atualizar Áreas"):
                    for _, row in df_edt_areas.iterrows():
                        supabase.table("areas").update({"vagas": row['vagas'], "posicoes": row['posicoes']}).eq("id", row['id']).execute()
                    st.success("Configurações salvas!")

if __name__ == "__main__": main()
