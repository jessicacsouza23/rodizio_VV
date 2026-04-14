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

# Cores inspiradas no seu exemplo (Tons Pastel Profissionais)
CORES_POSICOES = {
    0: {"bg": "#E8F5E9", "border": "#4CAF50"},  # Verde (Sala 2/6)
    1: {"bg": "#FFFDE7", "border": "#FBC02D"},  # Amarelo (Sala 3)
    2: {"bg": "#FFEBEE", "border": "#EF5350"},  # Vermelho/Rosa (Sala 4)
    3: {"bg": "#F3E5F5", "border": "#AB47BC"},  # Roxo (Sala 5)
    4: {"bg": "#E3F2FD", "border": "#42A5F5"},  # Azul (Sala 7)
    5: {"bg": "#FFF3E0", "border": "#FB8C00"},  # Laranja (Teoria)
}

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

# --- NOVA GERAÇÃO DE IMAGEM (ESTILO CARDS) ---
def gerar_imagem_escala(df):
    if df.empty: return None
    df = df.astype(str)
    colunas_dados = [c for c in df.columns if c not in ['_mes', 'Data', 'Dia']]
    
    # Configurações de Tamanho
    largura_card = 500
    espacamento = 30
    margem_top = 180
    larg_total = (len(colunas_dados) * (largura_card + espacamento)) + 100
    alt_total = (len(df) * 160) + margem_top + 100
    
    img = Image.new('RGB', (larg_total, alt_total), color="#F8F9FA")
    draw = ImageDraw.Draw(img)
    
    try:
        f_titulo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 50)
        f_card_h = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        f_card_n = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 38)
        f_data = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 35)
    except:
        f_titulo = f_card_h = f_card_n = f_data = ImageFont.load_default()

    # Cabeçalho Principal
    mes_nome = df['_mes'].iloc[0].upper() if '_mes' in df.columns else "ESCALA"
    draw.rectangle([0, 0, larg_total, 130], fill="#2C3E50")
    w_t = draw.textlength(mes_nome, font=f_titulo)
    draw.text(((larg_total - w_t)/2, 35), mes_nome, fill="white", font=f_titulo)

    y_offset = margem_top
    for i, row in df.iterrows():
        # Linha da Data
        txt_data = f"📅 {row['Data']} ({row['Dia']})"
        draw.text((50, y_offset - 45), txt_data, fill="#2C3E50", font=f_data)
        
        x_offset = 50
        for idx, col in enumerate(colunas_dados):
            cor = CORES_POSICOES.get(idx, {"bg": "#FFFFFF", "border": "#CCCCCC"})
            
            # Desenha Card
            x1, y1, x2, y2 = x_offset, y_offset, x_offset + largura_card, y_offset + 110
            # Sombra/Borda
            draw.rounded_rectangle([x1, y1, x2, y2], radius=15, fill=cor['bg'], outline=cor['border'], width=3)
            # Barra Lateral Colorida
            draw.rounded_rectangle([x1, y1, x1+15, y2], radius=15, fill=cor['border'])
            
            # Texto do Card
            draw.text((x1 + 35, y1 + 15), col.upper(), fill="#555555", font=f_card_h)
            draw.text((x1 + 35, y1 + 55), str(row[col]), fill="#000000", font=f_card_n)
            
            x_offset += largura_card + espacamento
            
        y_offset += 180

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- LÓGICA DE FILTRAGEM ---
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

# --- APP PRINCIPAL ---
def main():
    st.set_page_config(page_title="CCB Escala Pro", layout="wide")
    
    if 'logged_in' not in st.session_state:
        st.title("⛪ Gestão de Escalas")
        c1, c2 = st.columns(2)
        u = c1.text_input("Usuário")
        p = c2.text_input("Senha", type="password")
        if st.button("Entrar", use_container_width=True):
            res = supabase.table("usuarios").select("*").eq("login", u).eq("senha", hash_senha(p)).execute()
            if res.data: st.session_state.update({'logged_in': True, 'user_id': res.data[0]['id']}); st.rerun()
            else: st.error("Erro de login.")
    else:
        # Sidebar Estilizada
        st.sidebar.title("Menu de Controle")
        areas_res = supabase.table("areas").select("*").eq("id_usuario", st.session_state['user_id']).execute()
        area = None
        if areas_res.data:
            sel = st.sidebar.selectbox("🎯 Selecione a Escala", [a['nome_area'] for a in areas_res.data])
            area = next(a for a in areas_res.data if a['nome_area'] == sel)
        
        aba = st.sidebar.radio("Navegação", ["📝 Gerar & Editar", "📂 Histórico", "👥 Membros", "✈️ Afastamentos", "⚙️ Configs"])
        if st.sidebar.button("🚪 Sair"): st.session_state.clear(); st.rerun()

        if aba == "📝 Gerar & Editar" and area:
            st.header(f"✍️ Editor de Rodízio: {area['nome_area']}")
            with st.expander("⚙️ Configurar Novo Período"):
                c1, c2, c3 = st.columns(3)
                m = c1.selectbox("Quantos meses?", [1,2,3,4,6])
                d_ini = c2.date_input("Data de Início")
                dias = c3.multiselect("Dias de Culto", DIAS_ORDEM, default=["Sunday"], format_func=lambda x: DIAS_TRADUCAO[x])
                if st.button("🔄 Gerar Sugestão Inteligente", use_container_width=True):
                    st.session_state['df_edit'] = gerar_escala_logica(area, d_ini, m, dias)

            if 'df_edit' in st.session_state:
                st.info("💡 Você pode editar qualquer nome ou data diretamente na tabela abaixo.")
                df_final = st.data_editor(st.session_state['df_edit'], num_rows="dynamic", use_container_width=True)
                
                if st.button("💾 SALVAR E FINALIZAR", use_container_width=True, type="primary"):
                    supabase.table("escalas").insert({
                        "id_area": area['id'], 
                        "nome_area": area['nome_area'], 
                        "dados_escala": df_final.to_json(orient='records')
                    }).execute()
                    st.success("Escala salva com sucesso no histórico!")
                    st.session_state['df_edit'] = df_final

        elif aba == "📂 Histórico" and area:
            st.header("📜 Escalas Concluídas")
            h = supabase.table("escalas").select("*").eq("id_area", area['id']).order("data_geracao", desc=True).execute()
            for e in h.data:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 1])
                    c1.markdown(f"**Escala de {e['data_geracao'][:16]}**")
                    if c2.button("👁️ Abrir no Editor", key=f"h_v_{e['id']}"):
                        st.session_state['df_edit'] = pd.read_json(io.StringIO(e['dados_escala']))
                        st.info("Carregado!")
                    if c3.button("🗑️", key=f"h_d_{e['id']}"):
                        supabase.table("escalas").delete().eq("id", e['id']).execute(); st.rerun()
                    
                    df_h = pd.read_json(io.StringIO(e['dados_escala']))
                    img_data = gerar_imagem_escala(df_h)
                    st.download_button("📥 Baixar Imagem para WhatsApp", img_data, f"escala_{area['nome_area']}.png", "image/png", key=f"h_i_{e['id']}")

        elif aba == "👥 Membros" and area:
            st.header("👥 Gerenciar Irmandade")
            # [Aba de Membros com regras de 3º sábado conforme solicitado antes]
            with st.expander("➕ Adicionar Novo Membro"):
                with st.form("add_m"):
                    n = st.text_input("Nome"); s = st.number_input("Serviços", 0)
                    if st.form_submit_button("Salvar"):
                        res = supabase.table("membros").insert({"nome": n, "total_servicos": s}).execute()
                        supabase.table("vinculos").insert({"id_membro": res.data[0]['id'], "id_area": area['id']}).execute(); st.rerun()

            vinc = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute()
            ids = [x['id_membro'] for x in vinc.data]
            if ids:
                ms = supabase.table("membros").select("*").in_("id", ids).order("nome").execute()
                for m in ms.data:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 2, 1])
                        c1.subheader(m['nome'])
                        if c3.button("⚙️ Configurar", key=f"btn_{m['id']}"):
                            st.session_state[f"edit_{m['id']}"] = not st.session_state.get(f"edit_{m['id']}", False)
                        if st.session_state.get(f"edit_{m['id']}"):
                            with st.form(f"f_{m['id']}"):
                                n_n = st.text_input("Nome", m['nome'])
                                n_s = st.number_input("Serviços Realizados", value=m['total_servicos'])
                                r_res = supabase.table("restricoes").select("*").eq("id_membro", m['id']).execute()
                                d_atuais = [r['valor'] for r in r_res.data if r['tipo'] == 'dia']
                                reg_atuais = [r['valor'] for r in r_res.data if r['tipo'] == 'regra']
                                d_fixos = st.multiselect("Não pode tocar nestes dias:", DIAS_ORDEM, default=d_atuais, format_func=lambda x: DIAS_TRADUCAO[x])
                                sab3 = st.checkbox("Restrito no 3º Sábado?", value=('3_sabado' in reg_atuais))
                                if st.form_submit_button("Atualizar Cadastro"):
                                    supabase.table("membros").update({"nome": n_n, "total_servicos": n_s}).eq("id", m['id']).execute()
                                    supabase.table("restricoes").delete().eq("id_membro", m['id']).in_("tipo", ["dia", "regra"]).execute()
                                    for d in d_fixos: supabase.table("restricoes").insert({"id_membro": m['id'], "tipo": "dia", "valor": d}).execute()
                                    if sab3: supabase.table("restricoes").insert({"id_membro": m['id'], "tipo": "regra", "valor": "3_sabado"}).execute()
                                    st.rerun()

        elif aba == "✈️ Afastamentos" and area:
            st.header("✈️ Bloqueio de Datas")
            vinc = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute()
            ids = [v['id_membro'] for v in vinc.data]
            if ids:
                membros_lista = supabase.table("membros").select("id, nome").in_("id", ids).execute()
                with st.form("afast"):
                    m_sel = st.selectbox("Quem ficará ausente?", [m['nome'] for m in membros_lista.data])
                    d1 = st.date_input("De:"); d2 = st.date_input("Até:")
                    if st.form_submit_button("Confirmar Afastamento"):
                        mid = next(m['id'] for m in membros_lista.data if m['nome'] == m_sel)
                        curr = d1
                        while curr <= d2:
                            supabase.table("restricoes").insert({"id_membro": mid, "tipo": "data_especifica", "valor": curr.strftime('%Y-%m-%d')}).execute()
                            curr += timedelta(days=1)
                        st.success("Período bloqueado!"); st.rerun()

        elif aba == "⚙️ Configs":
            st.header("⚙️ Configurar Áreas")
            with st.form("nova_area"):
                n = st.text_input("Nome da Escala (Ex: Rodízio Organistas)")
                v = st.number_input("Número de Vagas por dia", 1, 5, 2)
                p = st.text_input("Nomes das Vagas (Ex: Meia-Hora, Culto)")
                if st.form_submit_button("Criar"):
                    supabase.table("areas").insert({"id_usuario": st.session_state['user_id'], "nome_area": n, "vagas": v, "posicoes": p}).execute()
                    st.rerun()

if __name__ == "__main__":
    main()
