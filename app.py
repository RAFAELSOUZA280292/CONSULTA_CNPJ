# cnpj_app_streamlit/app.py

import streamlit as st
import requests
import pandas as pd
import time
import re
import datetime
import os

# --- Funções de Utilitário (Podem ser mantidas como estão) ---

def format_cnpj(cnpj_text):
    """Formata o CNPJ para o padrão XX.XXX.XXX/XXXX-XX."""
    clean_cnpj = re.sub(r'\D', '', cnpj_text)
    if len(clean_cnpj) > 14:
        clean_cnpj = clean_cnpj[:14]

    formatted_cnpj = ""
    if len(clean_cnpj) > 0:
        formatted_cnpj += clean_cnpj[0:2]
    if len(clean_cnpj) > 2:
        formatted_cnpj += "." + clean_cnpj[2:5]
    if len(clean_cnpj) > 5:
        formatted_cnpj += "." + clean_cnpj[5:8]
    if len(clean_cnpj) > 8:
        formatted_cnpj += "/" + clean_cnpj[8:12]
    if len(clean_cnpj) > 12:
        formatted_cnpj += "-" + clean_cnpj[12:14]
    return formatted_cnpj

def clean_cnpj(formatted_cnpj):
    """Remove a formatação do CNPJ, deixando apenas dígitos."""
    return re.sub(r'\D', '', formatted_cnpj)

# --- Lógica de Negócio (Adaptada para Streamlit, sem prints de debug) ---

def consultar_cnpj_api(cnpj):
    """
    Realiza a consulta de um CNPJ na API open.cnpja.com.
    Implementa um retry básico para status 429.
    """
    clean_cnpj_num = clean_cnpj(cnpj)
    if not clean_cnpj_num.isdigit() or len(clean_cnpj_num) != 14:
        return {"error": "CNPJ inválido. Digite 14 dígitos numéricos."}

    url = f"https://open.cnpja.com/office/{clean_cnpj_num}"
    try:
        response = requests.get(url)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            st.warning("Muitas requisições (429). Tentando novamente em 60 segundos...")
            time.sleep(60) # Espera antes de tentar novamente
            return consultar_cnpj_api(cnpj) # Tenta novamente
        elif response.status_code == 404:
            return {"error": f"CNPJ {clean_cnpj_num} não encontrado ou inválido na base da API."}
        else:
            return {"error": f"Erro ao consultar {clean_cnpj_num}: Status {response.status_code}"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Erro de conexão: {e}"}

def extract_data_for_display(response):
    """Extrai e formatar os dados da resposta da API para exibição."""
    if "error" in response:
        return None, response["error"]

    data = response
    extracted = {}

    # Adaptação para extrair e formatar apenas alguns campos para este exemplo
    # Você expandiria isso para todos os campos que deseja exibir
    company = data.get('company', {})
    address_data = data.get('address', {})
    status_info = data.get('status', {})
    main_activity = data.get('mainActivity', {})

    extracted["CNPJ"] = format_cnpj(data.get('taxId', 'N/A'))
    extracted["Razão Social"] = company.get('name', 'N/A')
    extracted["Nome Fantasia"] = data.get('alias', 'N/A')
    
    founded_str = data.get('founded')
    if founded_str:
        try:
            dt_object = datetime.datetime.strptime(founded_str, '%Y-%m-%d')
            extracted["Data de Abertura"] = dt_object.strftime("%d/%m/%Y")
        except ValueError:
            extracted["Data de Abertura"] = 'N/A'
    else:
        extracted["Data de Abertura"] = 'N/A'

    extracted["Situação Cadastral"] = status_info.get('text', 'N/A')
    extracted["Logradouro"] = address_data.get('street', 'N/A')
    extracted["Número"] = address_data.get('number', 'N/A')
    extracted["CNAE Principal"] = f"{main_activity.get('id', 'N/A')} - {main_activity.get('text', 'N/A')}"
    
    # Exemplo de extração de sócios (apenas nomes para simplicidade)
    members = company.get('members', [])
    members_info_list = []
    if members:
        for member in members:
            person = member.get('person', {})
            members_info_list.append(person.get('name', 'N/A'))
        extracted["Sócios"] = ", ".join(members_info_list)
    else:
        extracted["Sócios"] = "N/A"

    return extracted, None

# --- Interface Streamlit ---
st.set_page_config(page_title="Consulta CNPJ", layout="centered")

st.title("🔎 Consulta de Dados Cadastrais CNPJ")
st.markdown("Desenvolvido por Zen.Ai TAX (adaptado para Streamlit)")

cnpj_input = st.text_input("Digite o CNPJ para consultar:", max_chars=18, help="Apenas números, ou no formato XX.XXX.XXX/XXXX-XX")

# Formatação automática do CNPJ (visual, não altera o valor do input em si)
display_cnpj = format_cnpj(cnpj_input)
if cnpj_input and clean_cnpj(cnpj_input) != clean_cnpj(display_cnpj):
    st.info(f"CNPJ formatado: **{display_cnpj}**")

if st.button("Consultar CNPJ"):
    if not cnpj_input:
        st.warning("Por favor, digite um CNPJ para consultar.")
    else:
        cleaned_cnpj = clean_cnpj(cnpj_input)
        if len(cleaned_cnpj) != 14 or not cleaned_cnpj.isdigit():
            st.error("CNPJ inválido. Digite 14 dígitos numéricos.")
        else:
            with st.spinner("Consultando CNPJ..."):
                api_response = consultar_cnpj_api(cleaned_cnpj)
            
            if "error" in api_response:
                st.error(f"Erro na consulta: {api_response['error']}")
                st.session_state.last_consulted_data = {} # Limpa dados anteriores
                st.session_state.api_raw_response = {}
            else:
                extracted_data, error_msg = extract_data_for_display(api_response)
                if error_msg:
                    st.error(f"Erro ao processar dados: {error_msg}")
                    st.session_state.last_consulted_data = {}
                    st.session_state.api_raw_response = {}
                else:
                    st.success("Consulta concluída com sucesso!")
                    # Armazena os dados no session_state
                    st.session_state.last_consulted_data = extracted_data
                    st.session_state.api_raw_response = api_response # Guarda a resposta bruta para TXT/Excel

# Exibe os resultados se houver dados consultados
if "last_consulted_data" in st.session_state and st.session_state.last_consulted_data:
    st.subheader("Dados do CNPJ")

    # Usando st.tabs para organizar os dados, simulando as abas PySide6
    tab_general, tab_address, tab_activities, tab_partners, tab_registrations = st.tabs([
        "Geral", "Endereço", "Atividades", "Sócios", "IEs"
    ])

    with tab_general:
        st.write(f"**CNPJ:** {st.session_state.last_consulted_data.get('CNPJ', 'N/A')}")
        st.write(f"**Razão Social:** {st.session_state.last_consulted_data.get('Razão Social', 'N/A')}")
        st.write(f"**Nome Fantasia:** {st.session_state.last_consulted_data.get('Nome Fantasia', 'N/A')}")
        st.write(f"**Data de Abertura:** {st.session_state.last_consulted_data.get('Data de Abertura', 'N/A')}")
        st.write(f"**Situação Cadastral:** {st.session_state.last_consulted_data.get('Situação Cadastral', 'N/A')}")
        # ... Adicione mais campos gerais aqui, usando dados de `st.session_state.last_consulted_data`

    with tab_address:
        st.write(f"**Logradouro:** {st.session_state.last_consulted_data.get('Logradouro', 'N/A')}")
        st.write(f"**Número:** {st.session_state.last_consulted_data.get('Número', 'N/A')}")
        # ... Adicione mais campos de endereço

    with tab_activities:
        st.write(f"**CNAE Principal:** {st.session_state.last_consulted_data.get('CNAE Principal', 'N/A')}")
        # Para CNAEs Secundários e outros campos longos, você precisaria de uma lógica de extração mais robusta
        # ou passá-los como texto formatado do `extract_data_for_display`
        # Ex: st.text_area("CNAEs Secundários", value=extracted_data.get("CNAEs Secundários", "N/A"), height=200)

    with tab_partners:
        st.write(f"**Sócios:** {st.session_state.last_consulted_data.get('Sócios', 'N/A')}")
        # ... Adicione mais campos de sócios

    with tab_registrations:
        st.write("Inscrições Estaduais (IEs) viriam aqui.")
        # Similarmente, para IEs, você precisaria de uma lógica de extração/formatação no `extract_data_for_display`
        # que retorne as IEs como uma string ou lista para exibição.

    st.markdown("---")
    st.subheader("Opções de Exportação")
    
    # Botão Salvar em Excel
    if st.button("💾 Salvar em Excel"):
        if st.session_state.last_consulted_data:
            # Cria um DataFrame a partir dos dados extraídos para exibição
            df_to_export = pd.DataFrame([st.session_state.last_consulted_data])
            # Se você quiser mais colunas, precisaria re-extrair da api_raw_response
            # ou expandir `last_consulted_data` para ter todos os campos desejados no Excel.

            # Para um Excel completo, você precisaria de uma função similar a `extract_data_for_display`
            # que extraia *todos* os campos em um formato flat adequado para Excel, talvez usando `pd.json_normalize`.
            
            st.download_button(
                label="Clique para Baixar Excel",
                data=df_to_export.to_excel(index=False).encode('utf-8'), # Apenas um exemplo simples
                file_name=f"CNPJ_{clean_cnpj(st.session_state.last_consulted_data['CNPJ'])}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_excel"
            )
        else:
            st.warning("Nenhum dado para salvar em Excel.")

    # Botão Gerar TXT CNPJ
    if st.button("📄 Gerar Cartão CNPJ TXT"):
        if st.session_state.api_raw_response:
            # Aqui você chamaria a sua função `generate_cnpj_text_report`
            # adaptada para retornar a string TXT em vez de salvar no disco.
            # Ex:
            # txt_content = generate_cnpj_text_report_for_streamlit(st.session_state.api_raw_response)
            
            # POR EXEMPLO: Apenas para ilustração
            mock_txt_content = f"""
            --------------------------------------------------------------------------------
            |                            CARTÃO CNPJ - LAVORATAX                           |
            --------------------------------------------------------------------------------
            | EMITIDO EM: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
            --------------------------------------------------------------------------------

            --------------------------------------------------------------------------------
            | DADOS CADASTRAIS
            --------------------------------------------------------------------------------
            | NÚMERO DE INSCRIÇÃO: {st.session_state.last_consulted_data.get('CNPJ', 'N/A')}
            | RAZÃO SOCIAL: {st.session_state.last_consulted_data.get('Razão Social', 'N/A')}
            | ... (todos os dados formatados aqui)
            --------------------------------------------------------------------------------
            """

            st.download_button(
                label="Clique para Baixar Cartão CNPJ TXT",
                data=mock_txt_content.encode('utf-8'),
                file_name=f"Cartao_CNPJ_{clean_cnpj(st.session_state.last_consulted_data['CNPJ'])}.txt",
                mime="text/plain",
                key="download_txt"
            )
        else:
            st.warning("Nenhum dado para gerar Cartão CNPJ TXT.")
