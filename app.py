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

# --- LÓGICA DE FILTRAGEM ---
def membro_disponivel(id_membro, data_alvo, posicao_alvo=None):
    res = supabase.table("restricoes").select("*").eq("id_membro", id_membro).execute()
    for r in res.data:
        if r['tipo'] == 'dia' and data_alvo.strftime('%A') == r['valor']: return False
        if r['tipo'] == 'regra' and r['valor'] == '3_sabado':
            # Lógica do 3º sábado: entre os dias 15 e 21 e sendo Sábado
            if 15 <= data_alvo.day <= 21 and data_alvo.strftime('%A') == 'Saturday': return False
        if r['tipo'] == 'data_especifica' and data_alvo.strftime('%Y-%m-%d') == r['valor']: return False
    return True

# --- INTERFACE ---
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
        # Sidebar
        areas_res = supabase.table("areas").select("*").eq("id_usuario", st.session_state['user_id']).execute()
        if areas_res.data:
            sel = st.sidebar.selectbox("Escala Ativa", [a['nome_area'] for a in areas_res.data])
            area = next(a for a in areas_res.data if a['nome_area'] == sel)
        
        aba = st.sidebar.radio("Navegação", ["Gerar & Editar", "Histórico", "Gerenciar Membros", "Afastamentos", "Cargos"])
        if st.sidebar.button("Sair"): st.session_state.clear(); st.rerun()

        # --- ABA: GERENCIAR MEMBROS (DASHBOARD COMPLETO) ---
        if aba == "Gerenciar Membros" and area:
            st.header(f"👥 Dashboard de Membros - {area['nome_area']}")
            
            with st.expander("➕ Cadastrar Novo Irmão/Irmã"):
                with st.form("novo_membro"):
                    nome = st.text_input("Nome Completo")
                    servicos = st.number_input("Serviços Iniciais", 0)
                    if st.form_submit_button("Salvar"):
                        m = supabase.table("membros").insert({"nome": nome, "total_servicos": servicos}).execute()
                        supabase.table("vinculos").insert({"id_membro": m.data[0]['id'], "id_area": area['id']}).execute()
                        st.success("Cadastrado!"); st.rerun()

            st.divider()
            vinc = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute()
            ids = [x['id_membro'] for x in vinc.data]
            
            if ids:
                membros = supabase.table("membros").select("*").in_("id", ids).order("nome").execute()
                for m in membros.data:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 2, 1])
                        c1.subheader(m['nome'])
                        c2.write(f"Serviços: {m['total_servicos']}")
                        
                        if c3.button("⚙️ Editar / Regras", key=f"edit_{m['id']}"):
                            st.session_state[f"show_edit_{m['id']}"] = not st.session_state.get(f"show_edit_{m['id']}", False)
                        
                        if st.session_state.get(f"show_edit_{m['id']}"):
                            with st.form(key=f"form_m_{m['id']}"):
                                new_name = st.text_input("Editar Nome", value=m['nome'])
                                new_serv = st.number_input("Ajustar Serviços", value=m['total_servicos'])
                                
                                # Buscar restrições atuais
                                rest = supabase.table("restricoes").select("*").eq("id_membro", m['id']).execute()
                                d_atuais = [r['valor'] for r in rest.data if r['tipo'] == 'dia']
                                r_atuais = [r['valor'] for r in rest.data if r['tipo'] == 'regra']
                                
                                st.write("**Restrições Fixas:**")
                                d_fixos = st.multiselect("Dias que NÃO pode trabalhar:", DIAS_ORDEM, default=d_atuais, format_func=lambda x: DIAS_TRADUCAO[x], key=f"dias_{m['id']}")
                                
                                sabado_3 = st.checkbox("Restrito no 3º Sábado?", value=('3_sabado' in r_atuais), key=f"sab_{m['id']}")
                                
                                col_b1, col_b2 = st.columns(2)
                                if col_b1.form_submit_button("✅ Atualizar Tudo"):
                                    # Atualiza Nome/Serviços
                                    supabase.table("membros").update({"nome": new_name, "total_servicos": new_serv}).eq("id", m['id']).execute()
                                    # Limpa e reinsere restrições
                                    supabase.table("restricoes").delete().eq("id_membro", m['id']).in_("tipo", ["dia", "regra"]).execute()
                                    for d in d_fixos:
                                        supabase.table("restricoes").insert({"id_membro": m['id'], "tipo": "dia", "valor": d}).execute()
                                    if sabado_3:
                                        supabase.table("restricoes").insert({"id_membro": m['id'], "tipo": "regra", "valor": "3_sabado"}).execute()
                                    st.success("Atualizado!"); st.rerun()
                                    
                                if col_b2.form_submit_button("🗑️ Remover da Escala"):
                                    supabase.table("vinculos").delete().eq("id_membro", m['id']).eq("id_area", area['id']).execute()
                                    st.warning("Membro removido desta escala."); st.rerun()

        # --- ABA: AFASTAMENTOS (FÉRIAS / DATAS ESPECÍFICAS) ---
        elif aba == "Afastamentos" and area:
            st.header("✈️ Afastamentos Temporários")
            st.info("Use esta parte para quando alguém vai viajar ou ficar doente em datas específicas.")
            vinc = supabase.table("vinculos").select("id_membro").eq("id_area", area['id']).execute()
            ids = [v['id_membro'] for v in vinc.data]
            if ids:
                membros_lista = supabase.table("membros").select("id, nome").in_("id", ids).execute()
                with st.form("afast_form"):
                    m_sel = st.selectbox("Selecione o Irmão/Irmã", [m['nome'] for m in membros_lista.data])
                    d1 = st.date_input("Início do Afastamento")
                    d2 = st.date_input("Fim do Afastamento")
                    if st.form_submit_button("Gravar Período"):
                        mid = next(m['id'] for m in membros_lista.data if m['nome'] == m_sel)
                        curr = d1
                        while curr <= d2:
                            supabase.table("restricoes").insert({"id_membro": mid, "tipo": "data_especifica", "valor": curr.strftime('%Y-%m-%d')}).execute()
                            curr += timedelta(days=1)
                        st.success("Afastamento registrado com sucesso!")

        # --- OUTRAS ABAS (Mantidas conforme código anterior) ---
        elif aba == "Gerar & Editar":
            # [Lógica do data_editor e geração de base mantida aqui...]
            st.header(f"✍️ Editor de Escala: {area['nome_area']}")
            # ... (Código de geração anterior) ...
            pass # Para encurtar a resposta, mas no seu arquivo você mantém as abas anteriores.

if __name__ == "__main__":
    main()
