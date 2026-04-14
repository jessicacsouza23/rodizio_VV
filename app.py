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
DATA_RESET_INTERNA = "2000-01-01"

def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

# --- GERAÇÃO DE IMAGEM PARA WHATSAPP ---
def gerar_imagem_escala(df):
    if df.empty: return None
    df = df.astype(str)
    colunas_foto = [c for c in df.columns if c not in ['_mes']]
    larg_col = 350 
    larg_total = 80 + (len(colunas_foto) * larg_col)
    alt_total = (len(df) * 95) + 750 
    img = Image.new('RGB', (larg_total, alt_total), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        f_h = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 75)
        f_t = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 70)
        f_m = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 90)
    except:
        f_h = f_t = f_m = ImageFont.load_default()
    y, mes_at = 50, ""
    for i, row in df.iterrows():
        mes_atual = row.get('_mes', 'Escala')
        if mes_atual != mes_at:
            mes_at = mes_atual; y += 50
            draw.rectangle([0, y, larg_total, y+100], fill=(230, 230, 230))
            txt = f"MÊS DE {str(mes_at).upper()}"; w = draw.textlength(txt, font=f_m)
            draw.text(((larg_total-w)/2, y+15), txt, fill="black", font=f_m)
            y += 120; draw.rectangle([0, y, larg_total, y+80], fill=(40, 40, 40))
            for idx, col in enumerate(colunas_foto):
                txt_c = col.upper(); w_c = draw.textlength(txt_c, font=f_h)
                draw.text(((idx*larg_col)+(larg_col-w_c)/2, y+15), txt_c, fill="white", font=f_h)
            y += 100
        if i % 2 == 0: draw.rectangle([0, y-5, larg_total, y+75], fill=(240, 240, 240))
        for idx, col in enumerate(colunas_foto):
            txt_v = str(row[col]); w_v = draw.textlength(txt_v, font=f_t)
            draw.text(((idx*larg_col)+(larg_col-w_v)/2, y), txt_v, fill="black", font=f_t)
        y += 95 
    buf = io.BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()

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
    st.set_page_config(page_title="CCB Escala", layout="wide")
    
    if 'logged_in' not in st.session_state:
        st.title("⛪ Gestão de Escalas")
        u = st.text_input("Usuário"); p = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            res = supabase.table("usuarios").select("*").eq("login", u).eq("senha", hash_senha(p)).execute()
            if res.data: st.session_state.update({'logged_in': True, 'user_id': res.data[0]['id']}); st.rerun()
            else: st.error("Erro de login.")
    else:
        # Sidebar de Navegação
        areas_res = supabase.table("areas").select("*").eq("id_usuario", st.session_state['user_id']).execute()
        area = None
        if areas_res.data:
            sel = st.sidebar.selectbox("Escala Ativa", [a['nome_area'] for a in areas_res.data])
            area = next(a for a in areas_res.data if a['nome_area'] == sel)
        
        aba = st.sidebar.radio("Navegação", ["Gerar & Editar", "Histórico", "Gerenciar Membros", "Afastamentos", "Cargos"])
        if st.sidebar.button("Sair"): st.session_state.clear(); st.rerun()

        # --- ABA: GERAR & EDITAR ---
        if aba == "Gerar & Editar" and area:
            st.header(f"✍️ Gerador e Editor: {area['nome_area']}")
            with st.expander("1️⃣ Configurar Período"):
                c1, c2, c3 = st.columns(3)
                m = c1.selectbox("Meses", [1,2,3,4,6])
                d_ini = c2.date_input("Início")
                dias = c3.multiselect("Dias de Culto", DIAS_ORDEM, default=["Sunday"], format_func=lambda x: DIAS_TRADUCAO[x])
                if st.button("Gerar Sugestão de Rodízio"):
                    st.session_state['df_edit'] = gerar_escala_logica(area, d_ini, m, dias)

            if 'df_edit' in st.session_state:
                st.divider()
                st.subheader("2️⃣ Ajuste a Tabela (Clique para editar ou excluir linhas)")
                df_final = st.data_editor(st.session_state['df_edit'], num_rows="dynamic", use_container_width=True)
                
                if st.button("💾 Confirmar e Salvar Escala"):
                    supabase.table("escalas").insert({"id_area": area['id'], "nome_area": area['nome_area'], "dados_escala": df_final.to_json(orient='records')}).execute()
                    st.success("Escala salva no banco de dados!")
                    st.session_state['df_edit'] = df_final

        # --- ABA: HISTÓRICO ---
        elif aba == "Histórico" and area:
            st.header("📜 Escalas Salvas")
            h = supabase.table("escalas").select("*").eq("id_area", area['id']).order("data_geracao", desc=True).execute()
            for e in h.data:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 1])
                    c1.write(f"📅 Criada em: {e['data_geracao'][:16]}")
                    if c2.button("👁️ Abrir no Editor", key=f"h_v_{e['id']}"):
                        st.session_state['df_edit'] = pd.read_json(io.StringIO(e['dados_escala']))
                        st.info("Carregado na aba 'Gerar & Editar'!")
                    if c3.button("🗑️ Deletar", key=f"h_d_{e['id']}"):
                        supabase.table("escalas").delete().eq("id", e['id']).execute(); st.rerun()
                    
                    df_h = pd.read_json(io.StringIO(e['dados_escala']))
                    img_data = gerar_imagem_escala(df_h)
                    st.download_button("📸 Baixar Imagem (WhatsApp)", img_data, "escala.png", "image/png", key=f"h_i_{e['id']}")

        # --- ABA: GERENCIAR MEMBROS ---
        elif aba == "Gerenciar Membros" and area:
            st.header("👥 Configurações de Membros")
            with st.expander("➕ Adicionar Novo"):
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
                        if c3.button("⚙️ Regras", key=f"btn_{m['id']}"):
                            st.session_state[f"edit_{m['id']}"] = not st.session_state.get(f"edit_{m['id']}", False)
                        
                        if st.session_state.get(f"edit_{m['id']}"):
                            with st.form(f"f_{m['id']}"):
                                n_n = st.text_input("Nome", m['nome'])
                                n_s = st.number_input("Serviços", value=m['total_servicos'])
                                # Restrições
                                r_res = supabase.table("restricoes").select("*").eq("id_membro", m['id']).execute()
                                d_atuais = [r['valor'] for r in r_res.data if r['tipo'] == 'dia']
                                reg_atuais = [r['valor'] for r in r_res.data if r['tipo'] == 'regra']
                                d_fixos = st.multiselect("Não pode tocar nestes dias:", DIAS_ORDEM, default=d_atuais, format_func=lambda x: DIAS_TRADUCAO[x])
                                sab3 = st.checkbox("Bloquear 3º Sábado?", value=('3_sabado' in reg_atuais))
                                
                                if st.form_submit_button("Atualizar"):
                                    supabase.table("membros").update({"nome": n_n, "total_servicos": n_s}).eq("id", m['id']).execute()
                                    supabase.table("restricoes").delete().eq("id_membro", m['id']).in_("tipo", ["dia", "regra"]).execute()
                                    for d in d_fixos: supabase.table("restricoes").insert({"id_membro": m['id'], "tipo": "dia", "valor": d}).execute()
                                    if sab3: supabase.table("restricoes").insert({"id_membro": m['id'], "tipo": "regra", "valor": "3_sabado"}).execute()
                                    st.rerun()

        # --- ABA: AFASTAMENTOS ---
        elif aba == "Afastamentos" and area:
            st.header("✈️ Afastamentos Temporários")
            vinc = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute()
            ids = [v['id_membro'] for v in vinc.data]
            if ids:
                membros_lista = supabase.table("membros").select("id, nome").in_("id", ids).execute()
                with st.form("afast"):
                    m_sel = st.selectbox("Irmão/Irmã", [m['nome'] for m in membros_lista.data])
                    d1 = st.date_input("Início"); d2 = st.date_input("Fim")
                    if st.form_submit_button("Gravar Bloqueio"):
                        mid = next(m['id'] for m in membros_lista.data if m['nome'] == m_sel)
                        curr = d1
                        while curr <= d2:
                            supabase.table("restricoes").insert({"id_membro": mid, "tipo": "data_especifica", "valor": curr.strftime('%Y-%m-%d')}).execute()
                            curr += timedelta(days=1)
                        st.success("Datas bloqueadas!"); st.rerun()

        # --- ABA: CARGOS ---
        elif aba == "Cargos":
            st.header("⚙️ Configurar Novas Escalas")
            with st.form("nova_area"):
                n = st.text_input("Nome (Ex: Organistas Manhã)")
                v = st.number_input("Nº de Vagas", 1, 5, 2)
                p = st.text_input("Posições (Separadas por vírgula. Ex: Meia-Hora, Culto)")
                if st.form_submit_button("Criar Área de Escala"):
                    supabase.table("areas").insert({"id_usuario": st.session_state['user_id'], "nome_area": n, "vagas": v, "posicoes": p}).execute()
                    st.rerun()

if __name__ == "__main__":
    main()
