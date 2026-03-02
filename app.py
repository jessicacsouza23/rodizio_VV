# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, timedelta
from supabase import create_client, Client
from PIL import Image, ImageDraw, ImageFont
import io
import json

MESES_TRADUCAO = {
    'January': 'Janeiro', 'February': 'Fevereiro', 'March': 'Março',
    'April': 'Abril', 'May': 'Maio', 'June': 'Junho',
    'July': 'Julho', 'August': 'Agosto', 'September': 'Setembro',
    'October': 'Outubro', 'November': 'Novembro', 'December': 'Dezembro'
}

# --- CONEXÃO SUPABASE ---
URL = "https://qfvahrtockqxlvrhknkn.supabase.co"
KEY = "sb_publishable_NYv_kYobauOtW0lT3fWp6A_irgKBVGN"
supabase: Client = create_client(URL, KEY)

# --- CONFIGURAÇÕES GLOBAIS ---
DIAS_TRADUCAO = {'Monday': 'Seg', 'Tuesday': 'Ter', 'Wednesday': 'Qua', 'Thursday': 'Qui', 'Friday': 'Sex', 'Saturday': 'Sáb', 'Sunday': 'Dom'}
DIAS_ORDEM = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DATA_RESET_INTERNA = "2000-01-01"

def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

# --- FUNÇÃO DE GERAÇÃO DE IMAGEM ---
def gerar_imagem_escala(df):
    if df.empty: return None
    df = df.astype(str)
    meses_ref = df['_mes'].values
    df_v = df.drop(columns=['_mes'])
    colunas = df_v.columns.tolist()
    larg_col = 220
    larg_total = 40 + (len(colunas) * larg_col)
    alt_total = (len(df) * 45) + 400
    img = Image.new('RGB', (larg_total, alt_total), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        f_h = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
        f_t = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        f_m = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except:
        f_h = f_t = f_m = ImageFont.load_default()
    y, mes_at = 30, ""
    for i, row in df_v.iterrows():
        partes_mes = meses_ref[i].split(" / ")
        mes_ingles = partes_mes[0].strip().capitalize()
        ano = partes_mes[1].strip() if len(partes_mes) > 1 else ""
        mes_pt = MESES_TRADUCAO.get(mes_ingles, mes_ingles)
        texto_mes_completo = f"{mes_pt} / {ano}"

        if meses_ref[i] != mes_at:
            mes_at = meses_ref[i]
            y += 20
            draw.rectangle([0, y, larg_total, y+45], fill=(230, 230, 230))
            txt = f"MÊS DE {texto_mes_completo.upper()}"
            w = draw.textlength(txt, font=f_m)
            draw.text(((larg_total-w)/2, y+10), txt, fill="black", font=f_m)
            y += 60
            draw.rectangle([0, y, larg_total, y+35], fill=(50, 50, 50))
            for idx, col in enumerate(colunas):
                txt_c = col.upper(); w_c = draw.textlength(txt_c, font=f_h)
                draw.text(((idx*larg_col)+(larg_col-w_c)/2, y+7), txt_c, fill="white", font=f_h)
            y += 45
        if i % 2 == 0: draw.rectangle([0, y-5, larg_total, y+30], fill=(248, 248, 248))
        for idx, col in enumerate(colunas):
            txt_v = row[col]; w_v = draw.textlength(txt_v, font=f_t)
            draw.text(((idx*larg_col)+(larg_col-w_v)/2, y), txt_v, fill="black", font=f_t)
        y += 40
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def membro_disponivel(id_membro, data_alvo, posicao_alvo=None):
    data_str = data_alvo.strftime('%Y-%m-%d')
    res = supabase.table("restricoes").select("*").eq("id_membro", id_membro).execute()
    for r in res.data:
        if r['tipo'] == 'dia' and data_alvo.strftime('%A') == r['valor']: return False
        if r['tipo'] == 'regra' and r['valor'] == '3_sabado' and (15 <= data_alvo.day <= 21 and data_alvo.strftime('%A') == 'Saturday'): return False
        if r['tipo'] == 'data_especifica' and data_str == r['valor']: return False
        if r['tipo'] == 'posicao' and posicao_alvo == r['valor']: return False
    return True

# --- MOTOR DE ESCALA JUSTO ---
def gerar_escala_logica(area, data_inicio, meses, dias_culto):
    vagas = int(area['vagas'])
    pos_list = [p.strip() for p in area['posicoes'].split(",")]
    escala_data = []
    data_atual = data_inicio
    data_fim = data_inicio + timedelta(days=30 * meses)

    # Buscar todos os membros da área
    vinc = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute()
    ids = [v['id_membro'] for v in vinc.data]
    
    if not ids: return pd.DataFrame()
    
    # Buscar dados dos membros
    membros_res = supabase.table("membros").select("*").in_("id", ids).execute()
    membros_base = membros_res.data
    
    # Inicializar contagem de serviços se necessário
    for m in membros_base:
        if 'total_servicos' not in m or m['total_servicos'] is None: 
            m['total_servicos'] = 0
            # Atualiza no banco para evitar erros futuros
            supabase.table("membros").update({"total_servicos": 0}).eq("id", m['id']).execute()

    while data_atual <= data_fim:
        dia_s = data_atual.strftime('%A')
        if dia_s in dias_culto:
            linha = {"Data": data_atual.strftime('%d/%m/%Y'), "Dia": DIAS_TRADUCAO[dia_s], "_mes": data_atual.strftime('%B / %Y')}
            
            # Ordenar membros pelo total de serviços (quem trabalhou menos primeiro)
            membros_base.sort(key=lambda x: x['total_servicos'])
            
            membros_da_rodada = membros_base.copy()
            preenchidos = 0
            
            for i in range(vagas):
                nome_posicao = pos_list[i] if i < len(pos_list) else f"Vaga {i+1}"
                
                # Tenta achar alguém disponível para a posição
                for p in membros_da_rodada:
                    if membro_disponivel(p['id'], data_atual, nome_posicao):
                        linha[nome_posicao] = p['nome']
                        
                        # Atualiza contagem local e banco
                        p['total_servicos'] += 1
                        supabase.table("membros").update({
                            "total_servicos": p['total_servicos'], 
                            "ultimo_servico": data_atual.strftime('%Y-%m-%d')
                        }).eq("id", p['id']).execute()
                        
                        membros_da_rodada.remove(p)
                        preenchidos += 1
                        break
            
            if preenchidos > 0: escala_data.append(linha)
            
        data_atual += timedelta(days=1)
        
    return pd.DataFrame(escala_data)
    
# --- INTERFACE ---
def main():
    st.set_page_config(page_title="CCB Escala", layout="wide")
    
    if 'logged_in' not in st.session_state:
        st.title("⛪ Sistema de Escala CCB")
        t1, t2 = st.tabs(["Login", "Criar Conta"])
        with t1:
            u = st.text_input("Usuário"); p = st.text_input("Senha", type="password")
            if st.button("Entrar"):
                res = supabase.table("usuarios").select("*").eq("login", u).eq("senha", hash_senha(p)).execute()
                if res.data:
                    st.session_state.update({'logged_in': True, 'user_id': res.data[0]['id'], 'user_name': u})
                    st.rerun()
                else: st.error("Acesso Negado.")
        with t2:
            nu = st.text_input("Novo Usuário"); np = st.text_input("Nova Senha", type="password")
            if st.button("Cadastrar Administrador"):
                supabase.table("usuarios").insert({"login": nu, "senha": hash_senha(np)}).execute()
                st.success("Conta criada!")
    else:
        st.sidebar.title(f"👤 {st.session_state['user_name']}")
        areas_res = supabase.table("areas").select("*").eq("id_usuario", st.session_state['user_id']).execute()
        
        if areas_res.data:
            sel_nome = st.sidebar.selectbox("Área Atual", [a['nome_area'] for a in areas_res.data])
            st.session_state['area_ativa'] = next(a for a in areas_res.data if a['nome_area'] == sel_nome)
        else:
            st.session_state['area_ativa'] = None

        aba = st.sidebar.radio("Navegação", ["Dashboard", "Gerar Rodízio", "Histórico", "Cadastrar Pessoas", "Afastamentos", "Cargos"])
        if st.sidebar.button("Sair"): st.session_state.clear(); st.rerun()

        if aba == "Dashboard" and st.session_state['area_ativa']:
            area = st.session_state['area_ativa']
            st.header(f"📊 Dashboard: {area['nome_area']}")
            
            if st.button("🔄 Reiniciar Fila de Prioridade", type="secondary"):
                vinc = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute()
                ids = [v['id_membro'] for v in vinc.data]
                if ids:
                    supabase.table("membros").update({"total_servicos": 0, "ultimo_servico": DATA_RESET_INTERNA}).in_("id", ids).execute()
                    st.success("Prioridades reiniciadas!")
                    st.rerun()

            vinc = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute()
            ids = [v['id_membro'] for v in vinc.data]
            if ids:
                membros = supabase.table("membros").select("*").in_("id", ids).order("nome").execute()
                posicoes_da_area = [p.strip() for p in area['posicoes'].split(",")]
                for m in membros.data:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 1, 1])
                        c1.write(f"👤 **{m['nome']}** (Total: {m.get('total_servicos', 0)})")
                        if c2.button("✏️", key=f"ed_{m['id']}"): st.session_state['edit_id'] = m['id']
                        if c3.button("🗑️", key=f"rm_{m['id']}"):
                            supabase.table("restricoes").delete().eq("id_membro", m['id']).execute()
                            supabase.table("vinculos").delete().eq("id_membro", m['id']).execute()
                            supabase.table("membros").delete().eq("id", m['id']).execute(); st.rerun()

                        if st.session_state.get('edit_id') == m['id']:
                            with st.form(f"form_ed_{m['id']}"):
                                rest_res = supabase.table("restricoes").select("*").eq("id_membro", m['id']).execute()
                                dias_at = [r['valor'] for r in rest_res.data if r['tipo'] == 'dia']
                                pos_at = [r['valor'] for r in rest_res.data if r['tipo'] == 'posicao']
                                sab_at = any(r['valor'] == '3_sabado' for r in rest_res.data)
                                nv_nome = st.text_input("Nome", m['nome'])
                                nv_ind = st.multiselect("Dias Proibidos", DIAS_ORDEM, default=dias_at, format_func=lambda x: DIAS_TRADUCAO[x])
                                nv_pos = st.multiselect("Posições que NÃO pode fazer", posicoes_da_area, default=pos_at)
                                nv_sab = st.checkbox("Restrição 3º Sábado", value=sab_at)
                                if st.form_submit_button("Salvar"):
                                    supabase.table("membros").update({"nome": nv_nome}).eq("id", m['id']).execute()
                                    supabase.table("restricoes").delete().eq("id_membro", m['id']).execute()
                                    for d in nv_ind: supabase.table("restricoes").insert({"id_membro": m['id'], "tipo": "dia", "valor": d}).execute()
                                    for p_rest in nv_pos: supabase.table("restricoes").insert({"id_membro": m['id'], "tipo": "posicao", "valor": p_rest}).execute()
                                    if nv_sab: supabase.table("restricoes").insert({"id_membro": m['id'], "tipo": "regra", "valor": "3_sabado"}).execute()
                                    del st.session_state['edit_id']; st.rerun()
            else: st.info("Nenhum membro.")

        elif aba == "Gerar Rodízio" and st.session_state['area_ativa']:
            area = st.session_state['area_ativa']
            st.header(f"📅 Gerar: {area['nome_area']}")
            c1, c2 = st.columns(2)
            meses = c1.selectbox("Período (Meses)", [1, 2, 3, 4, 5, 6]); inicio = c2.date_input("Data Inicial")
            dias = st.multiselect("Cultos", DIAS_ORDEM, default=["Thursday", "Saturday", "Sunday"], format_func=lambda x: DIAS_TRADUCAO[x])
            
            if st.button("🚀 Gerar e Salvar Escala", type="primary"):
                df = gerar_escala_logica(area, inicio, meses, dias)
                st.session_state['escala_final'] = df
                dados_json = df.to_json(orient='records')
                supabase.table("escalas").insert({
                    "id_area": area['id'],
                    "nome_area": area['nome_area'],
                    "dados_escala": dados_json
                }).execute()
                st.success("Escala gerada e salva!")
            
            if 'escala_final' in st.session_state:
                df = st.session_state['escala_final']
                st.dataframe(df.drop(columns=['_mes']), use_container_width=True)
                img_data = gerar_imagem_escala(df)
                st.download_button(label="📸 Baixar Foto", data=img_data, file_name=f"Escala.png", mime="image/png")

        elif aba == "Histórico":
            # SEGURANÇA REFORÇADA: Verifica se a área ativa existe e tem um ID
            area_ativa = st.session_state.get('area_ativa')
            
            if area_ativa and 'id' in area_ativa:
                area = area_ativa
                st.header(f"📜 Histórico: {area['nome_area']}")
                
                # Busca escalas apenas se a área estiver definida corretamente
                try:
                    escalas_salvas = supabase.table("escalas").select("*").eq("id_area", area['id']).order("data_geracao", descending=True).execute()
                    
                    if escalas_salvas.data:
                        for esc in escalas_salvas.data:
                            with st.container(border=True):
                                c1, c2, c3 = st.columns([3, 2, 1])
                                
                                # Tratamento seguro da data
                                try:
                                    data_geracao = datetime.fromisoformat(esc['data_geracao'])
                                    data_formatada = data_geracao.strftime('%d/%m/%Y %H:%M')
                                except:
                                    data_formatada = "Data inválida"
                                    
                                c1.write(f"📅 Gerado em: **{data_formatada}**")
                                
                                if c2.button("Visualizar", key=f"view_{esc['id']}"):
                                    st.session_state['view_escala'] = esc['id']
                                
                                if c3.button("🗑️", key=f"del_{esc['id']}"):
                                    supabase.table("escalas").delete().eq("id", esc['id']).execute()
                                    st.rerun()

                                # Exibir escala selecionada
                                if st.session_state.get('view_escala') == esc['id']:
                                    try:
                                        df = pd.read_json(esc['dados_escala'])
                                        st.dataframe(df, use_container_width=True)
                                    except:
                                        st.error("Erro ao carregar os dados da escala.")
                                        
                                    if st.button("Fechar", key=f"close_{esc['id']}"):
                                        del st.session_state['view_escala']
                                        st.rerun()
                    else:
                        st.info("Nenhuma escala salva ainda para esta área.")
                except Exception as e:
                    st.error(f"Erro ao buscar histórico: {e}")
            else:
                st.warning("⚠️ Selecione uma área na barra lateral primeiro.")

        elif aba == "Cadastrar Pessoas" and st.session_state['area_ativa']:
            area = st.session_state['area_ativa']
            posicoes_da_area = [p.strip() for p in area['posicoes'].split(",")]
            st.header(f"👥 Cadastro: {area['nome_area']}")
            with st.form("cad_p", clear_on_submit=True):
                nome = st.text_input("Nome")
                indisp = st.multiselect("Dias Proibidos:", DIAS_ORDEM, format_func=lambda x: DIAS_TRADUCAO[x])
                rest_pos = st.multiselect("Posições que NÃO pode fazer:", posicoes_da_area)
                sab = st.checkbox("Restrição: 3º Sábado")
                if st.form_submit_button("Salvar"):
                    if nome.strip():
                        # Cria membro com total_servicos = 0
                        m_r = supabase.table("membros").insert({"nome": nome, "total_servicos": 0, "ultimo_servico": DATA_RESET_INTERNA}).execute()
                        mid = m_r.data[0]['id']
                        supabase.table("vinculos").insert({"id_membro": mid, "id_area": area['id']}).execute()
                        for d in indisp: supabase.table("restricoes").insert({"id_membro": mid, "tipo": "dia", "valor": d}).execute()
                        for p_rest in rest_pos: supabase.table("restricoes").insert({"id_membro": mid, "tipo": "posicao", "valor": p_rest}).execute()
                        if sab: supabase.table("restricoes").insert({"id_membro": mid, "tipo": "regra", "valor": "3_sabado"}).execute()
                        st.success(f"✅ {nome} cadastrado!")
                    else: st.warning("Digite o nome.")

        elif aba == "Afastamentos" and st.session_state['area_ativa']:
            area = st.session_state['area_ativa']
            st.header(f"✈️ Afastamentos: {area['nome_area']}")
            vinc = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute()
            ids = [v['id_membro'] for v in vinc.data]
            if ids:
                m_list = supabase.table("membros").select("id, nome").in_("id", ids).order("nome").execute()
                with st.form("afast"):
                    n_af = st.selectbox("Irmão(ã)", [m['nome'] for m in m_list.data])
                    d_ini = st.date_input("Início"); d_fim = st.date_input("Fim")
                    if st.form_submit_button("Registrar"):
                        mid = next(m['id'] for m in m_list.data if m['nome'] == n_af)
                        curr = d_ini
                        while curr <= d_fim:
                            supabase.table("restricoes").insert({"id_membro": mid, "tipo": "data_especifica", "valor": curr.strftime('%Y-%m-%d')}).execute()
                            curr += timedelta(days=1)
                        st.success("Registrado!")

        elif aba == "Cargos":
            st.header("⚙️ Configurar Área/Cargo")
            with st.form("nova_a"):
                n = st.text_input("Nome da Área"); v = st.number_input("Qtd Posições", 1, 10, 2); c = st.text_input("Nomes das Posições (separados por vírgula)")
                if st.form_submit_button("Criar"):
                    supabase.table("areas").insert({"id_usuario": st.session_state['user_id'], "nome_area": n, "vagas": v, "posicoes": c}).execute()
                    st.rerun()
            if areas_res.data:
                for a in areas_res.data:
                    with st.container(border=True):
                        col1, col2 = st.columns([4, 1])
                        col1.write(f"📂 **{a['nome_area']}** ({a['vagas']} vagas) - {a['posicoes']}")
                        if col2.button("🗑️", key=f"del_area_{a['id']}"):
                            supabase.table("areas").delete().eq("id", a['id']).execute(); st.rerun()

if __name__ == "__main__":
    main()



