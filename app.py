# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, timedelta
from supabase import create_client, Client
 illusion from PIL import Image, ImageDraw, ImageFont
import io
import json

# --- CONFIGURAÇÕES ---
MESES_TRADUCAO = {
    'January': 'Janeiro', 'February': 'Fevereiro', 'March': 'Março',
    'April': 'Abril', 'May': 'Maio', 'June': 'Junho',
    'July': 'Julho', 'August': 'Agosto', 'September': 'Setembro',
    'October': 'Outubro', 'November': 'Novembro', 'December': 'Dezembro'
}
DIAS_TRADUCAO = {'Monday': 'Seg', 'Tuesday': 'Ter', 'Wednesday': 'Qua', 'Thursday': 'Qui', 'Friday': 'Sex', 'Saturday': 'Sáb', 'Sunday': 'Dom'}
DIAS_ORDEM = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DATA_RESET_INTERNA = "2000-01-01"

URL = "https://qfvahrtockqxlvrhknkn.supabase.co"
KEY = "sb_publishable_NYv_kYobauOtW0lT3fWp6A_irgKBVGN"
supabase: Client = create_client(URL, KEY)

def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

def gerar_imagem_escala(df):
    if df.empty: return None
    df = df.astype(str)
    meses_ref = df['_mes'].values
    df_v = df.drop(columns=['_mes'], errors='ignore')
    colunas = df_v.columns.tolist()
    larg_col = 280 
    larg_total = 60 + (len(colunas) * larg_col)
    alt_total = (len(df) * 60) + 500 
    img = Image.new('RGB', (larg_total, alt_total), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        f_h = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        f_t = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        f_m = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
    except:
        f_h = f_t = f_m = ImageFont.load_default()
    y, mes_at = 40, ""
    for i, row in df_v.iterrows():
        if meses_ref[i] != mes_at:
            mes_at = meses_ref[i]; y += 30
            draw.rectangle([0, y, larg_total, y+60], fill=(230, 230, 230))
            txt = f"MÊS DE {mes_at.upper()}"; w = draw.textlength(txt, font=f_m)
            draw.text(((larg_total-w)/2, y+10), txt, fill="black", font=f_m)
            y += 80; draw.rectangle([0, y, larg_total, y+50], fill=(50, 50, 50))
            for idx, col in enumerate(colunas):
                txt_c = col.upper(); w_c = draw.textlength(txt_c, font=f_h)
                draw.text(((idx*larg_col)+(larg_col-w_c)/2, y+8), txt_c, fill="white", font=f_h)
            y += 60
        if i % 2 == 0: draw.rectangle([0, y-5, larg_total, y+45], fill=(245, 245, 245))
        for idx, col in enumerate(colunas):
            txt_v = row[col]; w_v = draw.textlength(txt_v, font=f_t)
            draw.text(((idx*larg_col)+(larg_col-w_v)/2, y), txt_v, fill="black", font=f_t)
        y += 55 
    buf = io.BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()

def membro_disponivel(id_membro, data_alvo, posicao_alvo=None):
    res = supabase.table("restricoes").select("*").eq("id_membro", id_membro).execute()
    for r in res.data:
        if r['tipo'] == 'dia' and data_alvo.strftime('%A') == r['valor']: return False
        if r['tipo'] == 'regra' and r['valor'] == '3_sabado' and (15 <= data_alvo.day <= 21 and data_alvo.strftime('%A') == 'Saturday'): return False
        if r['tipo'] == 'data_especifica' and data_alvo.strftime('%Y-%m-%d') == r['valor']: return False
        if r['tipo'] == 'posicao' and posicao_alvo == r['valor']: return False
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
            m_en = MESES_TRADUCAO.get(data_atual.strftime('%B'), data_atual.strftime('%B'))
            linha = {"Data": data_atual.strftime('%d/%m/%Y'), "Dia": DIAS_TRADUCAO[dia_s], "_mes": f"{m_en} / {data_atual.year}"}
            preenchidos = 0; ids_hoy = []
            for i in range(vagas):
                p_nome = pos_list[i] if i < len(pos_list) else f"Vaga {i+1}"
                for idx, m in enumerate(fila_membros):
                    if m['id'] not in ids_hoy and membro_disponivel(m['id'], data_atual, p_nome):
                        linha[p_nome] = m['nome']; ids_hoy.append(m['id'])
                        m['total_servicos'] = (m.get('total_servicos') or 0) + 1
                        m['ultimo_servico'] = data_atual.strftime('%Y-%m-%d')
                        supabase.table("membros").update({"total_servicos": m['total_servicos'], "ultimo_servico": m['ultimo_servico']}).eq("id", m['id']).execute()
                        fila_membros.append(fila_membros.pop(idx)); preenchidos += 1; break
            if preenchidos > 0: escala_data.append(linha)
        data_atual += timedelta(days=1)
    return pd.DataFrame(escala_data)

def main():
    st.set_page_config(page_title="CCB Escala", layout="wide")
    if 'logged_in' not in st.session_state:
        st.title("⛪ Sistema de Escala")
        u = st.text_input("Usuário"); p = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            res = supabase.table("usuarios").select("*").eq("login", u).eq("senha", hash_senha(p)).execute()
            if res.data: st.session_state.update({'logged_in': True, 'user_id': res.data[0]['id'], 'user_name': u}); st.rerun()
            else: st.error("Acesso Negado.")
    else:
        st.sidebar.title(f"👤 {st.session_state['user_name']}")
        areas_res = supabase.table("areas").select("*").eq("id_usuario", st.session_state['user_id']).execute()
        if areas_res.data:
            sel = st.sidebar.selectbox("Área", [a['nome_area'] for a in areas_res.data])
            st.session_state['area_ativa'] = next(a for a in areas_res.data if a['nome_area'] == sel)
        aba = st.sidebar.radio("Navegação", ["Gerar Rodízio", "Histórico", "Membros", "Cargos/Horários"])
        if st.sidebar.button("Sair"): st.session_state.clear(); st.rerun()

        if aba == "Gerar Rodízio" and st.session_state.get('area_ativa'):
            area = st.session_state['area_ativa']; st.header(f"📅 Escala: {area['nome_area']}")
            
            with st.expander("🛠️ Configurar Nova Geração"):
                c1, c2 = st.columns(2); m = c1.selectbox("Meses", [1,2,3,4,5,6]); d_ini = c2.date_input("Início")
                dias = st.multiselect("Dias de Culto", DIAS_ORDEM, default=["Sunday"], format_func=lambda x: DIAS_TRADUCAO[x])
                if st.button("Simular Escala"):
                    st.session_state['temp_df'] = gerar_escala_logica(area, d_ini, m, dias)

            if 'temp_df' in st.session_state:
                df = st.session_state['temp_df']
                st.subheader("Edição Pré-Salvamento")
                st.info("💡 Remova as linhas dos dias que NÃO haverá culto nesta escala específica.")
                
                # Permite remover datas específicas antes de salvar
                datas_para_remover = st.multiselect("Selecione datas para CANCELAR (Sem Culto):", df['Data'].tolist())
                df_final = df[~df['Data'].isin(datas_para_remover)]
                
                st.dataframe(df_final.drop(columns=['_mes'], errors='ignore'), use_container_width=True)
                
                if st.button("Confirmar e Salvar Escala"):
                    supabase.table("escalas").insert({"id_area": area['id'], "nome_area": area['nome_area'], "dados_escala": df_final.to_json(orient='records')}).execute()
                    st.success("Escala salva com sucesso!"); del st.session_state['temp_df']; st.rerun()

        elif aba == "Histórico" and st.session_state.get('area_ativa'):
            area = st.session_state['area_ativa']; st.header("📜 Histórico")
            h = supabase.table("escalas").select("*").eq("id_area", area['id']).order("data_geracao", desc=True).execute()
            for e in h.data:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3,2,1])
                    c1.write(f"📅 Gerada em: {e['data_geracao'][:16]}")
                    if c2.button("Ver", key=f"v_{e['id']}"): st.session_state['view'] = e['id']
                    if c3.button("🗑️", key=f"d_{e['id']}"): supabase.table("escalas").delete().eq("id", e['id']).execute(); st.rerun()
                    if st.session_state.get('view') == e['id']:
                        df_h = pd.read_json(io.StringIO(e['dados_escala']))
                        st.dataframe(df_h.drop(columns=['_mes'], errors='ignore'), use_container_width=True)
                        img = gerar_imagem_escala(df_h)
                        st.download_button("📸 Baixar Imagem", img, f"Escala_{area['nome_area']}.png", "image/png", key=f"dl_{e['id']}")

        elif aba == "Membros" and st.session_state.get('area_ativa'):
            area = st.session_state['area_ativa']; st.header("👥 Gestão de Membros")
            with st.form("cad"):
                n = st.text_input("Nome"); d = st.multiselect("Indisponível", DIAS_ORDEM, format_func=lambda x: DIAS_TRADUCAO[x])
                if st.form_submit_button("Cadastrar/Vincular"):
                    ex = supabase.table("membros").select("id").eq("nome", n).execute()
                    mid = ex.data[0]['id'] if ex.data else supabase.table("membros").insert({"nome": n, "total_servicos": 0, "ultimo_servico": DATA_RESET_INTERNA}).execute().data[0]['id']
                    supabase.table("vinculos").upsert({"id_membro": mid, "id_area": area['id']}).execute()
                    for dia in d: supabase.table("restricoes").insert({"id_membro": mid, "tipo": "dia", "valor": dia}).execute()
                    st.success("Pronto!"); st.rerun()
            
            v = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute()
            ids = [x['id_membro'] for x in v.data]
            if ids:
                ms = supabase.table("membros").select("*").in_("id", ids).order("nome").execute()
                for m in ms.data:
                    with st.container(border=True):
                        col1, col2 = st.columns([4,1])
                        col1.write(f"👤 {m['nome']} | Serviços: {m.get('total_servicos', 0)}")
                        if col2.button("Remover desta Área", key=f"rm_{m['id']}"):
                            supabase.table("vinculos").delete().eq("id_membro", m['id']).eq("id_area", area['id']).execute(); st.rerun()

        elif aba == "Cargos/Horários":
            st.header("⚙️ Áreas e Horários")
            st.info("Dica: Para horários diferentes no mesmo cargo, crie áreas separadas. Ex: 'Limpeza (Manhã)' e 'Limpeza (Noite)'.")
            with st.form("area"):
                n = st.text_input("Nome da Área/Horário"); v = st.number_input("Vagas", 1, 10, 2); p = st.text_input("Posições (Vírgula)")
                if st.form_submit_button("Criar"):
                    supabase.table("areas").insert({"id_usuario": st.session_state['user_id'], "nome_area": n, "vagas": v, "posicoes": p}).execute(); st.rerun()
            for a in areas_res.data:
                with st.container(border=True):
                    c1, c2 = st.columns([4,1])
                    c1.write(f"📂 **{a['nome_area']}** | {a['vagas']} vagas | Posições: {a['posicoes']}")
                    if c2.button("Excluir Área", key=f"del_{a['id']}"): supabase.table("areas").delete().eq("id", a['id']).execute(); st.rerun()

if __name__ == "__main__":
    main()
