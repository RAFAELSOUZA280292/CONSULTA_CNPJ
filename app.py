import streamlit as st
import requests
import pandas as pd
import time
import re
import datetime
import os

# --- Funções de Utilitário ---
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

# --- Lógica de Negócio ---
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
    """
    Extrai e formata os dados da resposta da API para exibição na GUI.
    Esta função DEVE ser a versão COMPLETA que você tinha no seu app PySide6
    para garantir que todos os campos necessários estejam presentes no dicionário 'extracted'.
    """
    if "error" in response:
        return None, response["error"]

    data = response

    # Comece com o dicionário extracted vazio
    extracted = {}

    # --- Dados da Empresa ---
    company = data.get('company', {})
    simples = company.get('simples', {})
    simei = company.get('simei', {})
    nature = company.get('nature', {})
    size = company.get('size', {})
    status_info = data.get('status', {})
    status_special = data.get('specialStatus', {})

    extracted["CNPJ"] = data.get('taxId', 'N/A')
    extracted["Razão Social"] = company.get('name', 'N/A')
    extracted["Nome Fantasia"] = data.get('alias', 'N/A')

    # Data de Abertura
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

    # Data Situação Cadastral
    status_date_str = data.get('statusDate')
    if status_date_str:
        try:
            dt_object = datetime.datetime.strptime(status_date_str, '%Y-%m-%d')
            extracted["Data Situação Cadastral"] = dt_object.strftime("%d/%m/%Y")
        except ValueError:
            extracted["Data Situação Cadastral"] = 'N/A'
    else:
        extracted["Data Situação Cadastral"] = 'N/A'

    extracted["Motivo Situação Cadastral"] = status_info.get('reason', 'N/A')
    extracted["Situação Especial"] = status_special.get('text', 'N/A')
    extracted["Data Situação Especial"] = status_special.get('date', 'N/A') # Data ainda não formatada

    extracted["Natureza Jurídica"] = nature.get('text', 'N/A')
    extracted["Porte da Empresa"] = size.get('text', 'N/A')

    # Capital Social com formatação comercial
    equity_value = company.get('equity')
    if equity_value is not None:
        try:
            equity_str = f"{float(equity_value):.2f}"
            parts = equity_str.split('.')
            integer_part = parts[0]
            decimal_part = parts[1]
            formatted_integer_part = re.sub(r'(\d)(?=(\d{3})+(?!\d))', r'\1.', integer_part)
            extracted["Capital Social"] = f"R$ {formatted_integer_part},{decimal_part}"
        except (ValueError, TypeError):
            extracted["Capital Social"] = 'N/A'
    else:
        extracted["Capital Social"] = 'N/A'

    # Optante Simples Nacional com ✔/X
    simples_optant = simples.get('optant', False)
    extracted["Optante Simples Nacional"] = f"{'✔ Sim' if simples_optant else 'X Não'}"
    extracted["Início Simples Nacional"] = simples.get('since', 'N/A')

    # Optante SIMEI com ✔/X
    simei_optant = simei.get('optant', False)
    extracted["Optante SIMEI"] = f"{'✔ Sim' if simei_optant else 'X Não'}"
    extracted["Início SIMEI"] = simei.get('since', 'N/A')

    # Última Atualização Dados com formatação de data/hora
    updated_str = data.get('updated')
    if updated_str:
        try:
            dt_object = datetime.datetime.fromisoformat(updated_str.replace('Z', '+00:00'))
            extracted["Última Atualização Dados"] = dt_object.strftime("%d/%m/%Y - %H:%M")
        except ValueError:
            extracted["Última Atualização Dados"] = 'N/A'
    else:
        extracted["Última Atualização Dados"] = 'N/A'

    # Endereço
    address_data = data.get('address')
    if address_data and isinstance(address_data, dict):
        extracted["Logradouro"] = address_data.get('street', 'N/A')
        extracted["Número"] = address_data.get('number', 'N/A')
        extracted["Complemento"] = address_data.get('details', 'N/A')
        extracted["Bairro"] = address_data.get('district', 'N/A')
        extracted["Município"] = address_data.get('city', 'N/A')
        extracted["UF"] = address_data.get('state', 'N/A')
        extracted["CEP"] = address_data.get('zip', 'N/A')
        extracted["País"] = address_data.get('country', {}).get('name', 'N/A')
    else:
        extracted["Logradouro"] = 'N/A'
        extracted["Número"] = 'N/A'
        extracted["Complemento"] = 'N/A'
        extracted["Bairro"] = 'N/A'
        extracted["Município"] = 'N/A'
        extracted["UF"] = 'N/A'
        extracted["CEP"] = 'N/A'
        extracted["País"] = 'N/A'

    # Atividades Econômicas
    main_activity = data.get('mainActivity', {})
    extracted["CNAE Principal"] = f"{main_activity.get('id', 'N/A')} - {main_activity.get('text', 'N/A')}"

    side_activities = data.get('sideActivities', [])
    cnaes_secundarios_list = []
    for activity in side_activities:
        cnaes_secundarios_list.append(f"{activity.get('id', 'N/A')} - {activity.get('text', 'N/A')}")
    extracted["CNAEs Secundários"] = "\n".join(cnaes_secundarios_list) if cnaes_secundarios_list else "N/A"

    # Contatos
    phones = data.get('phones', [])
    phone_list = []
    for phone in phones:
        phone_list.append(f"({phone.get('area', 'N/A')}) {phone.get('number', 'N/A')} ({phone.get('type', 'N/A')})")
    extracted["Telefones"] = "\n".join(phone_list) if phone_list else "N/A"

    emails = data.get('emails', [])
    email_list = []
    for email in emails:
        email_list.append(email.get('address', 'N/A'))
    extracted["Emails"] = "\n".join(email_list) if email_list else "N/A"

    # Sócios
    members = company.get('members', [])
    members_info_list = []
    if members:
        for member in members:
            person = member.get('person', {})
            role = member.get('role', {})
            member_details = []
            member_details.append(f"Nome: {person.get('name', 'N/A')}")
            member_details.append(f"CPF: {person.get('taxId', 'N/A')}")
            member_details.append(f"Idade: {person.get('age', 'N/A')}")
            member_details.append(f"Função: {role.get('text', 'N/A')}")
            members_info_list.append("\n".join(member_details))
        extracted["Sócios"] = "\n\n".join(members_info_list)
    else:
        extracted["Sócios"] = "N/A"

    # Inscrições Estaduais (SINTEGRA)
    registrations = data.get('registrations', [])
    formatted_registrations_list = []
    if registrations:
        for reg in registrations:
            ie_number = reg.get('number', 'N/A')
            uf = reg.get('state', 'N/A')
            enabled = "SIM" if reg.get('enabled', False) else "NÃO"
            status_text = reg.get('status', {}).get('text', 'N/A')
            type_text = reg.get('type', {}).get('text', 'N/A')

            reg_info = (
                f"Nº IE: {ie_number}\n"
                f"UF: {uf}\n"
                f"Habilitada: {enabled}\n"
                f"Status: {status_text}\n"
                f"TIPO: {type_text}"
            )
            formatted_registrations_list.append(reg_info)
        extracted["Inscricoes Estaduais"] = "\n\n".join(formatted_registrations_list)
    else:
        extracted["Inscricoes Estaduais"] = "N/A"

    return extracted, None

# --- Interface Streamlit ---
st.set_page_config(page_title="Consulta CNPJ", layout="centered")

st.title("🔎 Consulta de Dados Cadastrais CNPJ")
st.markdown("Desenvolvido por Zen.Ai TAX (adaptado para Streamlit)")

cnpj_input = st.text_input("Digite o CNPJ para consultar:", max_chars=18, help="Apenas números, ou no formato XX.XXX.XXX/XXXX-XX", key="cnpj_input_field")

# Formatação automática do CNPJ (visual, não altera o valor do input em si)
display_cnpj = format_cnpj(cnpj_input)
if cnpj_input and clean_cnpj(cnpj_input) != clean_cnpj(display_cnpj):
    st.info(f"CNPJ formatado: **{display_cnpj}**")

if st.button("Consultar CNPJ", key="consult_button"):
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
        
        # --- CAMPOS ADICIONADOS / CORRIGIDOS NA EXIBIÇÃO ---
        st.write(f"**Data da Situação Cadastral:** {st.session_state.last_consulted_data.get('Data Situação Cadastral', 'N/A')}")
        st.write(f"**Motivo Situação Cadastral:** {st.session_state.last_consulted_data.get('Motivo Situação Cadastral', 'N/A')}")
        st.write(f"**Situação Especial:** {st.session_state.last_consulted_data.get('Situação Especial', 'N/A')}")
        # A data da Situação Especial não está formatada na extração, vamos formatar aqui se existir e for uma string
        data_especial_str = st.session_state.last_consulted_data.get('Data Situação Especial', 'N/A')
        if data_especial_str != 'N/A':
            try:
                dt_object_esp = datetime.datetime.strptime(data_especial_str, '%Y-%m-%d')
                data_especial_str = dt_object_esp.strftime("%d/%m/%Y")
            except ValueError:
                pass # Mantém como está se não for uma data válida
        st.write(f"**Data Situação Especial:** {data_especial_str}")
        
        st.write(f"**Natureza Jurídica:** {st.session_state.last_consulted_data.get('Natureza Jurídica', 'N/A')}")
        st.write(f"**Porte da Empresa:** {st.session_state.last_consulted_data.get('Porte da Empresa', 'N/A')}")
        st.write(f"**Capital Social:** {st.session_state.last_consulted_data.get('Capital Social', 'N/A')}")
        st.write(f"**Optante Simples Nacional:** {st.session_state.last_consulted_data.get('Optante Simples Nacional', 'N/A')}")
        st.write(f"**Optante SIMEI:** {st.session_state.last_consulted_data.get('Optante SIMEI', 'N/A')}")
        st.write(f"**Início Simples Nacional:** {st.session_state.last_consulted_data.get('Início Simples Nacional', 'N/A')}")
        st.write(f"**Início SIMEI:** {st.session_state.last_consulted_data.get('Início SIMEI', 'N/A')}")
        st.write(f"**Última Atualização Dados:** {st.session_state.last_consulted_data.get('Última Atualização Dados', 'N/A')}")

    with tab_address:
        st.write(f"**Logradouro:** {st.session_state.last_consulted_data.get('Logradouro', 'N/A')}")
        st.write(f"**Número:** {st.session_state.last_consulted_data.get('Número', 'N/A')}")
        st.write(f"**Complemento:** {st.session_state.last_consulted_data.get('Complemento', 'N/A')}")
        st.write(f"**Bairro:** {st.session_state.last_consulted_data.get('Bairro', 'N/A')}")
        st.write(f"**Município:** {st.session_state.last_consulted_data.get('Município', 'N/A')}")
        st.write(f"**UF:** {st.session_state.last_consulted_data.get('UF', 'N/A')}")
        st.write(f"**CEP:** {st.session_state.last_consulted_data.get('CEP', 'N/A')}")
        st.write(f"**País:** {st.session_state.last_consulted_data.get('País', 'N/A')}")

    with tab_activities:
        st.write(f"**CNAE Principal:** {st.session_state.last_consulted_data.get('CNAE Principal', 'N/A')}")
        st.write(f"**CNAEs Secundários:**")
        st.markdown(st.session_state.last_consulted_data.get("CNAEs Secundários", "N/A"))
        st.write(f"**Telefones:**")
        st.markdown(st.session_state.last_consulted_data.get("Telefones", "N/A"))
        st.write(f"**Emails:**")
        st.markdown(st.session_state.last_consulted_data.get("Emails", "N/A"))


    with tab_partners:
        st.write(f"**Sócios:**")
        st.markdown(st.session_state.last_consulted_data.get('Sócios', 'N/A'))

    with tab_registrations:
        st.write(f"**Inscrições Estaduais:**")
        st.markdown(st.session_state.last_consulted_data.get("Inscricoes Estaduais", "N/A"))

    st.markdown("---")
    st.subheader("Opções de Exportação")
    
    # Botão Salvar em Excel
    if st.button("💾 Salvar em Excel", key="save_excel_button"):
        if st.session_state.last_consulted_data:
            # Para exportar todos os campos, incluindo aqueles com múltiplas linhas (CNAEs Sec., Sócios, IEs),
            # você precisará tratá-los para que apareçam em uma única célula do Excel.
            # Uma forma é joinar com "\n" ou ", "
            
            # Cria uma cópia para modificação antes de criar o DataFrame
            data_for_excel = st.session_state.last_consulted_data.copy()

            # Trata campos que podem ter múltiplas linhas no display para uma única linha no Excel
            for key_multi_line in ["CNAEs Secundários", "Telefones", "Emails", "Sócios", "Inscricoes Estaduais"]:
                if key_multi_line in data_for_excel and isinstance(data_for_excel[key_multi_line], str):
                    data_for_excel[key_multi_line] = data_for_excel[key_multi_line].replace("\n", " | ") # Substitui quebras de linha por |

            df_to_export = pd.DataFrame([data_for_excel])
            
            # Reorganiza as colunas na ordem desejada
            # As chaves em data_for_excel serão as mesmas do COLUMN_ORDER que você já tinha no PySide6
            column_order = [
                # Dados Gerais
                "CNPJ", "Razão Social", "Nome Fantasia", "Data de Abertura",
                "Situação Cadastral", "Data Situação Cadastral", "Motivo Situação Cadastral",
                "Situação Especial", "Data Situação Especial",
                "Natureza Jurídica", "Porte da Empresa", "Capital Social", "Optante Simples Nacional",
                "Início Simples Nacional", "Optante SIMEI", "Início SIMEI",
                "Última Atualização Dados",
                # Endereço
                "Logradouro", "Número", "Complemento", "Bairro", "Município",
                "UF", "CEP", "País",
                # Atividades e Contatos
                "CNAE Principal", "CNAEs Secundários", "Telefones", "Emails", "Sócios",
                # SINTEGRA
                "Inscricoes Estaduais"
            ]
            # Filtra apenas as colunas que realmente existem no DataFrame
            existing_columns = [col for col in column_order if col in df_to_export.columns]
            df_to_export = df_to_export[existing_columns]


            # Cria o arquivo Excel em memória
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_to_export.to_excel(writer, index=False, sheet_name='Dados CNPJ')
            processed_data = output.getvalue()


            st.download_button(
                label="Clique para Baixar Excel",
                data=processed_data,
                file_name=f"CNPJ_{clean_cnpj(st.session_state.last_consulted_data['CNPJ'])}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_excel"
            )
        else:
            st.warning("Nenhum dado para salvar em Excel.")

    # Botão Gerar TXT CNPJ
    if st.button("📄 Gerar Cartão CNPJ TXT", key="generate_txt_button"):
        if st.session_state.api_raw_response:
            # Aqui você chamará a sua função `generate_cnpj_text_report`
            # adaptada para retornar a string TXT em vez de salvar no disco.
            # Mova a lógica de `generate_cnpj_text_report` para uma nova função
            # que retorna o conteúdo do TXT como uma string.
            
            # Reutilizando a lógica do PySide6 para gerar o conteúdo TXT
            # Você precisaria mover a função generate_cnpj_text_report_content para fora da classe CnpjApp
            # ou criar uma função helper aqui que replique a lógica.
            
            txt_content = generate_cnpj_text_report_content(st.session_state.api_raw_response)

            st.download_button(
                label="Clique para Baixar Cartão CNPJ TXT",
                data=txt_content.encode('utf-8'),
                file_name=f"Cartao_CNPJ_{clean_cnpj(st.session_state.last_consulted_data['CNPJ'])}.txt",
                mime="text/plain",
                key="download_txt"
            )
        else:
            st.warning("Nenhum dado para gerar Cartão CNPJ TXT.")

# --- HELPERS PARA O DOWNLOAD TXT E EXCEL ---
import io # Adicionar no início do arquivo junto com os outros imports

def generate_cnpj_text_report_content(api_raw_response):
    """
    Gera o conteúdo de texto para o relatório do CNPJ,
    usando a estrutura da sua função `generate_cnpj_text_report` do PySide6.
    Retorna uma string.
    """
    data = api_raw_response
    company = data.get('company', {})
    address = data.get('address', {})
    main_activity = data.get('mainActivity', {})
    side_activities = data.get('sideActivities', [])
    phones = data.get('phones', [])
    emails = data.get('emails', [])
    members = company.get('members', [])
    registrations = data.get('registrations', [])
    simples = company.get('simples', {})
    simei = company.get('simei', {})
    status_info = data.get('status', {})
    status_special = data.get('specialStatus', {})

    # Formatação de campos para TXT (reutilizando sua lógica)
    cnpj_formatted = format_cnpj(data.get('taxId', 'N/A'))
    razao_social = company.get('name', 'N/A')
    nome_fantasia = data.get('alias', 'N/A')
    data_abertura = datetime.datetime.strptime(data.get('founded', '1900-01-01'), '%Y-%m-%d').strftime('%d/%m/%Y') if data.get('founded') else 'N/A'
    situacao_cadastral = status_info.get('text', 'N/A')
    data_situacao_cadastral = datetime.datetime.strptime(data.get('statusDate', '1900-01-01'), '%Y-%m-%d').strftime('%d/%m/%Y') if data.get('statusDate') else 'N/A'
    motivo_situacao_cadastral = status_info.get('reason', 'N/A')
    situacao_especial = status_special.get('text', 'N/A')
    data_situacao_especial = datetime.datetime.strptime(status_special.get('date', '1900-01-01'), '%Y-%m-%d').strftime('%d/%m/%Y') if status_special.get('date') else 'N/A'
    natureza_juridica = company.get('nature', {}).get('text', 'N/A')
    porte_empresa = company.get('size', {}).get('text', 'N/A')

    equity_value = company.get('equity')
    if equity_value is not None:
        try:
            equity_str = f"{float(equity_value):.2f}"
            parts = equity_str.split('.')
            integer_part = parts[0]
            decimal_part = parts[1]
            formatted_capital_social = f"R$ {re.sub(r'(\d)(?=(\d{3})+(?!\d))', r'\1.', integer_part)},{decimal_part}"
        except (ValueError, TypeError):
            formatted_capital_social = 'N/A'
    else:
        formatted_capital_social = 'N/A'

    optante_simples = "SIM" if simples.get('optant', False) else "NÃO"
    data_opcao_simples = simples.get('since', 'N/A')
    optante_simei = "SIM" if simei.get('optant', False) else "NÃO"
    data_opcao_simei = simei.get('since', 'N/A')

    # Endereço
    logradouro = address.get('street', 'N/A')
    numero = address.get('number', 'N/A')
    complemento = address.get('details', 'N/A')
    bairro = address.get('district', 'N/A')
    cep = address.get('zip', 'N/A')
    municipio = address.get('city', 'N/A')
    uf_endereco = address.get('state', 'N/A')
    pais_endereco = address.get('country', {}).get('name', 'N/A')

    # CNAE Principal
    cnae_principal_id = main_activity.get('id', 'N/A')
    cnae_principal_text = main_activity.get('text', 'N/A')
    cnae_principal_formatted = f"{cnae_principal_id} - {cnae_principal_text}"

    # CNAEs Secundários
    cnaes_secundarios_txt = []
    if side_activities:
        for activity in side_activities:
            cnaes_secundarios_txt.append(f"{activity.get('id', 'N/A')} - {activity.get('text', 'N/A')}")
    else:
        cnaes_secundarios_txt.append("N/A")

    # Telefones
    phones_txt = []
    if phones:
        for phone in phones:
            phones_txt.append(f"({phone.get('area', 'N/A')}) {phone.get('number', 'N/A')} ({phone.get('type', 'N/A')})")
    else:
        phones_txt.append("N/A")

    # Emails
    emails_txt = []
    if emails:
        for email in emails:
            emails_txt.append(email.get('address', 'N/A'))
    else:
        emails_txt.append("N/A")

    # Quadro de Sócios e Administradores (QSA)
    qsa_txt = []
    if members:
        for member in members:
            person = member.get('person', {})
            role = member.get('role', {})
            qsa_txt.append(
                f"Nome: {person.get('name', 'N/A')}\n"
                f"CPF/CNPJ: {person.get('taxId', 'N/A')}\n"
                f"Função: {role.get('text', 'N/A')}\n"
                f"Desde: {member.get('since', 'N/A')}"
            )
    else:
        qsa_txt.append("N/A")

    # Inscrições Estaduais
    registrations_txt = []
    if registrations:
        for reg in registrations:
            ie_number = reg.get('number', 'N/A')
            uf_ie = reg.get('state', 'N/A')
            enabled_ie = "SIM" if reg.get('enabled', False) else "NÃO"
            status_ie = reg.get('status', {}).get('text', 'N/A')
            type_ie = reg.get('type', {}).get('text', 'N/A')
            registrations_txt.append(
                f"Nº IE: {ie_number} (UF: {uf_ie})\n"
                f"Habilitada: {enabled_ie}\n"
                f"Status: {status_ie}\n"
                f"Tipo: {type_ie}"
            )
    else:
        registrations_txt.append("N/A")

    # --- Montando o conteúdo TXT ---
    separator_line = "-" * 80 + "\n"
    text_content = separator_line
    text_content += f"|{' ' * 26}CARTÃO CNPJ - LAVORATAX{' ' * 27}|\n"
    text_content += separator_line
    text_content += f"| EMITIDO EM: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
    text_content += separator_line + "\n"

    # DADOS CADASTRAIS
    text_content += separator_line
    text_content += f"| DADOS CADASTRAIS\n"
    text_content += separator_line
    text_content += f"| NÚMERO DE INSCRIÇÃO: {cnpj_formatted}\n"
    text_content += f"| DATA DE ABERTURA: {data_abertura}\n"
    text_content += f"| NOME EMPRESARIAL: {razao_social}\n"
    text_content += f"| NOME FANTASIA: {nome_fantasia}\n"
    text_content += f"| CÓDIGO E DESCRIÇÃO DA ATIVIDADE ECONÔMICA PRINCIPAL: {cnae_principal_formatted}\n"

    text_content += f"| CÓDIGO(S) E DESCRIÇÃO(ÕES) DAS ATIVIDADES ECONÔMICAS SECUNDÁRIAS:\n"
    for cnae in cnaes_secundarios_txt:
        text_content += f"|   - {cnae}\n"
    text_content += f"| CÓDIGO E DESCRIÇÃO DA NATUREZA JURÍDICA: {natureza_juridica}\n"
    text_content += f"| PORTE DA EMPRESA: {porte_empresa}\n"
    text_content += f"| CAPITAL SOCIAL: {formatted_capital_social}\n"
    text_content += separator_line + "\n"

    # ENDEREÇO
    text_content += separator_line
    text_content += f"| ENDEREÇO\n"
    text_content += separator_line
    text_content += f"| LOGRADOURO: {logradouro}\n"
    text_content += f"| NÚMERO: {numero}\n"
    text_content += f"| COMPLEMENTO: {complemento}\n"
    text_content += f"| CEP: {cep}\n"
    text_content += f"| BAIRRO/DISTRITO: {bairro}\n"
    text_content += f"| MUNICÍPIO: {municipio}\n"
    text_content += f"| UF: {uf_endereco}\n"
    text_content += f"| PAÍS: {pais_endereco}\n"
    text_content += separator_line + "\n"

    # SITUAÇÃO CADASTRAL
    text_content += separator_line
    text_content += f"| SITUAÇÃO CADASTRAL\n"
    text_content += separator_line
    text_content += f"| SITUAÇÃO CADASTRAL: {situacao_cadastral}\n"
    text_content += f"| DATA DA SITUAÇÃO CADASTRAL: {data_situacao_cadastral}\n"
    text_content += f"| MOTIVO DE SITUAÇÃO CADASTRAL: {motivo_situacao_cadastral}\n"
    text_content += f"| SITUAÇÃO ESPECIAL: {situacao_especial}\n"
    text_content += f"| DATA DA SITUAÇÃO ESPECIAL: {data_situacao_especial}\n"
    text_content += separator_line + "\n"

    # REGIMES TRIBUTÁRIOS
    text_content += separator_line
    text_content += f"| REGIMES TRIBUTÁRIOS\n"
    text_content += separator_line
    text_content += f"| OPÇÃO PELO SIMPLES NACIONAL: {optante_simples}\n"
    text_content += f"| DATA DE OPÇÃO PELO SIMPLES: {data_opcao_simples}\n"
    text_content += f"| OPÇÃO PELO SIMEI: {optante_simei}\n"
    text_content += f"| DATA DE OPÇÃO PELO SIMEI: {data_opcao_simei}\n"
    text_content += separator_line + "\n"

    # CONTATOS
    text_content += separator_line
    text_content += f"| CONTATOS\n"
    text_content += separator_line
    text_content += f"| TELEFONES:\n"
    for phone in phones_txt:
        text_content += f"|   - {phone}\n"
    text_content += f"| EMAILS:\n"
    for email in emails_txt:
        text_content += f"|   - {email}\n"
    text_content += separator_line + "\n"

    # INSCRIÇÕES ESTADUAIS
    text_content += separator_line
    text_content += f"| INSCRIÇÕES ESTADUAIS\n"
    text_content += separator_line
    if registrations_txt[0] == "N/A":
        text_content += f"|   N/A\n"
    else:
        for i, reg_block in enumerate(registrations_txt):
            for line in reg_block.split('\n'):
                text_content += f"| {line}\n"
            if i < len(registrations_txt) - 1:
                text_content += f"|\n"
    text_content += separator_line + "\n"

    # QUADRO DE SÓCIOS E ADMINISTRADORES (QSA)
    text_content += separator_line
    text_content += f"| QUADRO DE SÓCIOS E ADMINISTRADORES (QSA)\n"
    text_content += separator_line
    if qsa_txt[0] == "N/A":
        text_content += f"|   N/A\n"
    else:
        for i, member_block in enumerate(qsa_txt):
            for line in member_block.split('\n'):
                text_content += f"| {line}\n"
            if i < len(qsa_txt) - 1:
                text_content += f"|\n"
    text_content += separator_line + "\n"

    # FOOTER
    text_content += separator_line
    text_content += f"| A validade e autenticidade deste documento podem ser comprovadas no site da Receita Federal do Brasil.\n"
    text_content += f"| Este é um documento gerado automaticamente pela ferramenta Zen.Ai TAX.\n"
    text_content += separator_line
    return text_content
