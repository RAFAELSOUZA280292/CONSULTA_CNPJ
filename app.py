import streamlit as st
import requests
import pandas as pd
import time
import re
import datetime
import os
import io

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
            enabled_text = "SIM" if reg.get('enabled', False) else "NÃO"
            status_text = reg.get('status', {}).get('text', 'N/A')
            type_text = reg.get('type', {}).get('text', 'N/A')

            # Emojis para Habilitada
            enabled_emoji = "🟢" if enabled_text == "SIM" else "🔴"

            # Emojis para Status (generalizando para incluir 'Bloqueado', 'Cancelado', 'Suspenso' como negativos)
            status_emoji = ""
            if "Sem restrição" in status_text or "ATIVA" in status_text.upper():
                status_emoji = "🟢"
            elif "Bloqueado" in status_text or "Cancelado" in status_text or "Suspenso" in status_text or "Baixada" in status_text or "Inapta" in status_text:
                status_emoji = "🔴"
            
            # Construindo a string formatada para a IE
            reg_info = (
                f"UF: {uf} | IE: {ie_number} | Habilitada: {enabled_text} {enabled_emoji}\n"
                f"Status: {status_text} {status_emoji}\n"
                f"TIPO: {type_text}"
            )
            formatted_registrations_list.append(reg_info)
        extracted["Inscricoes Estaduais"] = "\n\n".join(formatted_registrations_list)
    else:
        extracted["Inscricoes Estaduais"] = "N/A"

    return extracted, None

# --- Função auxiliar para linhas alternadas ---
def styled_row(label, value, row_index, is_multiline_content=False):
    # Cores para o tema claro
    color1 = "#F0F2F6"  # Cinza muito claro para linhas pares
    color2 = "#E8ECF2"  # Cinza ligeiramente mais escuro para linhas ímpares
    bg_color = color1 if row_index % 2 == 0 else color2
    
    # Cores do texto
    label_text_color = "#00ACC1" # Azul Ciano para o rótulo em negrito
    value_text_color = "#333333" # Cinza escuro para o valor

    min_height_style = "min-height: 25px;" if not is_multiline_content else ""

    html_content = f"""
    <div style="background-color: {bg_color}; padding: 8px 12px; margin-bottom: 2px; border-radius: 5px; {min_height_style}">
        <span style="font-weight: bold; color: {label_text_color};">{label}:</span> <span style="color: {value_text_color};">{value}</span>
    </div>
    """
    return html_content

# --- HELPERS PARA O DOWNLOAD TXT E EXCEL ---

# Constantes para a formatação do TXT
REPORT_WIDTH = 74 # Largura total do relatório em caracteres
HEADER_LINE = "=" * REPORT_WIDTH
SECTION_LINE = "-" * REPORT_WIDTH
SUB_SECTION_LINE = "-" * (REPORT_WIDTH - 4) # Linha mais curta para dentro das seções

def generate_cnpj_text_report_content(api_raw_response):
    """
    Gera o conteúdo de texto para o relatório do CNPJ com um novo layout "dahora".
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

    # Formatação de campos
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
            formatted_integer_part = re.sub(r'(\d)(?=(\d{3})+(?!\d))', r'\1.', integer_part)
            formatted_capital_social = f"R$ {formatted_integer_part},{decimal_part}"
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

    cnae_principal_id = main_activity.get('id', 'N/A')
    cnae_principal_text = main_activity.get('text', 'N/A')
    cnae_principal_formatted = f"{cnae_principal_id} - {cnae_principal_text}"

    # --- Start building text content ---
    text_lines = []

    # Header
    text_lines.append(HEADER_LINE)
    text_lines.append(f"{'CONSULTA CNPJ - Zen.Ai TAX'.center(REPORT_WIDTH)}")
    text_lines.append(HEADER_LINE)
    text_lines.append(f"EMITIDO EM: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")

    # DADOS CADASTRAIS
    text_lines.append(SECTION_LINE)
    text_lines.append("DADOS CADASTRAIS".center(REPORT_WIDTH))
    text_lines.append(SECTION_LINE)
    text_lines.append(f"CNPJ:           {cnpj_formatted}")
    text_lines.append(f"Razão Social:   {razao_social}")
    text_lines.append(f"Nome Fantasia:  {nome_fantasia}")
    text_lines.append(f"Data Abertura:  {data_abertura}")
    text_lines.append(f"CNAE Principal: {cnae_principal_formatted}\n")

    text_lines.append("CNAES SECUNDÁRIOS:")
    if side_activities:
        for activity in side_activities:
            text_lines.append(f"  - {activity.get('id', 'N/A')} - {activity.get('text', 'N/A')}")
    else:
        text_lines.append("  N/A")
    text_lines.append(f"\nNatureza Jurídica: {natureza_juridica}") # Adicionado newline antes
    text_lines.append(f"Porte da Empresa:  {porte_empresa}")
    text_lines.append(f"Capital Social:    {formatted_capital_social}\n")

    # ENDEREÇO
    text_lines.append(SECTION_LINE)
    text_lines.append("ENDEREÇO".center(REPORT_WIDTH))
    text_lines.append(SECTION_LINE)
    text_lines.append(f"Logradouro:     {logradouro}")
    text_lines.append(f"Número:         {numero}")
    text_lines.append(f"Complemento:    {complemento}")
    text_lines.append(f"Bairro:         {bairro}")
    text_lines.append(f"CEP:            {cep}")
    text_lines.append(f"Município:      {municipio}")
    text_lines.append(f"UF:             {uf_endereco}")
    text_lines.append(f"País:           {pais_endereco}\n")

    # SITUAÇÃO CADASTRAL
    text_lines.append(SECTION_LINE)
    text_lines.append("SITUAÇÃO CADASTRAL".center(REPORT_WIDTH))
    text_lines.append(SECTION_LINE)
    text_lines.append(f"Situação:              {situacao_cadastral}")
    text_lines.append(f"Data Situação:         {data_situacao_cadastral}")
    text_lines.append(f"Motivo Situação:       {motivo_situacao_cadastral}")
    text_lines.append(f"Situação Especial:     {situacao_especial}")
    text_lines.append(f"Data Situação Especial:{data_situacao_especial}\n")

    # REGIMES TRIBUTÁRIOS
    text_lines.append(SECTION_LINE)
    text_lines.append("REGIMES TRIBUTÁRIOS".center(REPORT_WIDTH))
    text_lines.append(SECTION_LINE)
    text_lines.append(f"Simples Nacional:  {optante_simples} (Desde {data_opcao_simples})")
    text_lines.append(f"SIMEI:             {optante_simei} (Desde {data_opcao_simei})\n")

    # CONTATOS
    text_lines.append(SECTION_LINE)
    text_lines.append("CONTATOS".center(REPORT_WIDTH))
    text_lines.append(SECTION_LINE)
    text_lines.append("Telefones:")
    if phones:
        for phone in phones:
            text_lines.append(f"  - ({phone.get('area', 'N/A')}) {phone.get('number', 'N/A')} ({phone.get('type', 'N/A')})")
    else:
        text_lines.append("  N/A")
    text_lines.append("Emails:")
    if emails:
        for email in emails:
            text_lines.append(f"  - {email.get('address', 'N/A')}")
    else:
        text_lines.append("  N/A")
    text_lines.append("\n") # Extra newline for spacing

    # INSCRIÇÕES ESTADUAIS
    text_lines.append(SECTION_LINE)
    text_lines.append("INSCRIÇÕES ESTADUAIS".center(REPORT_WIDTH))
    text_lines.append(SECTION_LINE)
    if registrations:
        for i, reg in enumerate(registrations):
            ie_number = reg.get('number', 'N/A')
            uf_ie = reg.get('state', 'N/A')
            enabled_ie = "SIM" if reg.get('enabled', False) else "NÃO"
            status_ie = reg.get('status', {}).get('text', 'N/A')
            type_ie = reg.get('type', {}).get('text', 'N/A')
            
            if i > 0:
                text_lines.append(SUB_SECTION_LINE) # Small separator between IEs
            
            text_lines.append(f"UF: {uf_ie}")
            text_lines.append(f"  IE: {ie_number}")
            text_lines.append(f"  Habilitada: {enabled_ie}")
            text_lines.append(f"  Status: {status_ie}")
            text_lines.append(f"  Tipo: {type_ie}")
        text_lines.append("\n") # Extra newline after last IE
    else:
        text_lines.append("N/A\n")

    # QUADRO DE SÓCIOS E ADMINISTRADORES (QSA)
    text_lines.append(SECTION_LINE)
    text_lines.append("QUADRO DE SÓCIOS E ADMINISTRADORES (QSA)".center(REPORT_WIDTH))
    text_lines.append(SECTION_LINE)
    if members:
        for i, member in enumerate(members):
            person = member.get('person', {})
            role = member.get('role', {})
            
            if i > 0:
                text_lines.append(SUB_SECTION_LINE) # Small separator between members
            
            text_lines.append(f"Sócio {i+1}:")
            text_lines.append(f"  Nome: {person.get('name', 'N/A')}")
            text_lines.append(f"  CPF/CNPJ: {person.get('taxId', 'N/A')}")
            text_lines.append(f"  Função: {role.get('text', 'N/A')}")
            text_lines.append(f"  Desde: {member.get('since', 'N/A')}")
        text_lines.append("\n") # Extra newline after last member
    else:
        text_lines.append("N/A\n")

    # Footer
    text_lines.append(HEADER_LINE)
    text_lines.append(f"Validade e Autenticidade: Consulte o site da Receita Federal do Brasil.".center(REPORT_WIDTH))
    text_lines.append(f"Gerado por Zen.Ai TAX.".center(REPORT_WIDTH))
    text_lines.append(HEADER_LINE)

    return "\n".join(text_lines)


# --- Interface Streamlit ---
st.set_page_config(page_title="Consulta CNPJ", layout="centered")

# Custom CSS for light theme and cyan accents
st.markdown("""
<style>
/* Overall app background and default text color for light theme */
.stApp {
    background-color: #F8F9FA; /* A very light grey, almost white */
    color: #333333; /* Dark grey for default text */
}

/* Headings (h1, h2, h3, h5) */
h1, h2, h3, h5 {
    color: #00ACC1; /* Cyan blue for all relevant headings */
}

/* Text input fields background */
/* These class names are heuristic and might change with Streamlit updates.
   It's better to inspect elements in browser dev tools for exact classes. */
.st-emotion-cache-z5fcl4, /* Primary input container */
.st-emotion-cache-1oe5f0g, /* Text input actual box */
.st-emotion-cache-13vmq3j, /* Another common input class */
.st-emotion-cache-1g0b27k, /* Yet another common input class */
.st-emotion-cache-f0f7f3 /* Textarea class, if applicable */
{
    background-color: white; /* White background for input fields */
    color: #333333; /* Dark text color in inputs */
    border-radius: 5px;
    border: 1px solid #ced4da; /* Light grey border */
}

/* Info box (for "CNPJ formatado") */
div[data-testid="stAlert"] {
    background-color: #e0f7fa; /* Light cyan background */
    color: #004d40; /* Dark green-blue text for good contrast */
    border-left: 5px solid #00ACC1; /* Cyan border for accent */
    border-radius: 5px;
}

/* Button styling */
.stButton>button {
    background-color: #00ACC1; /* Cyan background */
    color: white; /* White text for contrast */
    border-radius: 5px;
    border: none;
    padding: 10px 20px;
    font-size: 16px;
    cursor: pointer;
    box-shadow: 0 2px 5px rgba(0,0,0,0.2); /* Subtle shadow for depth */
    transition: background-color 0.3s ease; /* Smooth transition on hover */
}
.stButton>button:hover {
    background-color: #008C9E; /* Slightly darker cyan on hover */
}

/* Tabs styling */
div[data-testid="stTabs"] { /* Container for all tabs */
    background-color: #F0F2F6; /* Light grey background for the tab bar */
    border-radius: 5px;
    border-bottom: 1px solid #ced4da; /* Light border below tabs */
}

button[data-testid^="stTab"] { /* Individual tab buttons */
    color: #555555; /* Darker grey for inactive tab text */
    background-color: #F0F2F6; /* Match tab background to light grey */
    font-weight: bold;
    padding: 10px 15px;
    border-radius: 5px 5px 0 0; /* Rounded top corners */
    margin-right: 2px; /* Small space between tabs */
    transition: background-color 0.3s ease, color 0.3s ease, border-bottom 0.3s ease;
}

button[data-testid^="stTab"][aria-selected="true"] {
    color: #00ACC1; /* Cyan for selected tab text */
    background-color: white; /* White background for selected tab */
    border-bottom: 3px solid #00ACC1; /* Cyan underline for selected tab */
}
</style>
""", unsafe_allow_html=True)


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
        fields = [
            ("CNPJ", "CNPJ"),
            ("Razão Social", "Razão Social"),
            ("Nome Fantasia", "Nome Fantasia"),
            ("Data de Abertura", "Data de Abertura"),
            ("Situação Cadastral", "Situação Cadastral"),
            ("Data da Situação Cadastral", "Data Situação Cadastral"),
            ("Motivo Situação Cadastral", "Motivo Situação Cadastral"),
            ("Situação Especial", "Situação Especial"),
            ("Data Situação Especial", "Data Situação Especial"),
            ("Natureza Jurídica", "Natureza Jurídica"),
            ("Porte da Empresa", "Porte da Empresa"),
            ("Capital Social", "Capital Social"),
            ("Optante Simples Nacional", "Optante Simples Nacional"),
            ("Início Simples Nacional", "Início Simples Nacional"),
            ("Optante SIMEI", "Optante SIMEI"),
            ("Início SIMEI", "Início SIMEI"),
            ("Última Atualização Dados", "Última Atualização Dados"),
        ]
        
        row_idx = 0
        for label, key in fields:
            value = st.session_state.last_consulted_data.get(key, 'N/A')
            
            # Special handling for "Data Situação Especial"
            if key == "Data Situação Especial" and value != 'N/A' and isinstance(value, str) and len(value) >= 10:
                try:
                    dt_object_esp = datetime.datetime.strptime(value[:10], '%Y-%m-%d')
                    value = dt_object_esp.strftime("%d/%m/%Y")
                except ValueError:
                    pass
            
            # --- Lógica de Emojis Aprimorada ---
            if key == "Situação Cadastral":
                if value.strip().upper() == "ATIVA": # Normaliza para comparação
                    value = "🟢 Ativa"
            elif key == "Optante Simples Nacional":
                if "Sim" in value: # Verifica se "Sim" está na string
                    value = "🟢 Sim"
                elif "Não" in value: # Verifica se "Não" está na string
                    value = "🔴 Não"
            elif key == "Optante SIMEI":
                if "Sim" in value:
                    value = "🟢 Sim"
                elif "Não" in value:
                    value = "🔴 Não"
            # --- FIM DA LÓGICA DE EMOJIS APRIMORADA ---
            
            st.markdown(styled_row(label, value, row_idx), unsafe_allow_html=True)
            row_idx += 1

    with tab_address:
        row_idx = 0 
        fields = [
            ("Logradouro", "Logradouro"),
            ("Número", "Número"),
            ("Complemento", "Complemento"),
            ("Bairro", "Bairro"),
            ("Município", "Município"),
            ("UF", "UF"),
            ("CEP", "CEP"),
            ("País", "País"),
        ]
        for label, key in fields:
            value = st.session_state.last_consulted_data.get(key, 'N/A')
            st.markdown(styled_row(label, value, row_idx), unsafe_allow_html=True)
            row_idx += 1

    with tab_activities:
        row_idx = 0 # Inicia o contador de linhas para esta aba

        # CNAE Principal (linha única)
        label, key = "CNAE Principal", "CNAE Principal"
        value = st.session_state.last_consulted_data.get(key, 'N/A')
        st.markdown(styled_row(label, value, row_idx), unsafe_allow_html=True)
        row_idx += 1

        # CNAEs Secundários (lista de itens com zebra striping e separador)
        st.markdown("<h5 style='margin-bottom: 0;'>CNAEs Secundários:</h5>", unsafe_allow_html=True) # Título da seção
        cnaes_sec = st.session_state.last_consulted_data.get("CNAEs Secundários", "N/A")
        if cnaes_sec != "N/A":
            cnae_items = cnaes_sec.split('\n')
            for i, item in enumerate(cnae_items):
                st.markdown(styled_row("Item", item, row_idx), unsafe_allow_html=True) # "Item" como label genérico
                row_idx += 1
                if i < len(cnae_items) - 1: # Adiciona separador entre itens, mas não após o último
                    st.markdown("<div style='height: 5px;'></div>", unsafe_allow_html=True) # Separador visual leve
        else:
            st.markdown(styled_row("Item", "N/A", row_idx), unsafe_allow_html=True)
            row_idx += 1

        # Telefones (lista de itens com zebra striping e separador)
        st.markdown("<h5 style='margin-top: 15px; margin-bottom: 0;'>Telefones:</h5>", unsafe_allow_html=True) # Título da seção
        phones = st.session_state.last_consulted_data.get("Telefones", "N/A")
        if phones != "N/A":
            phone_items = phones.split('\n')
            for i, item in enumerate(phone_items):
                st.markdown(styled_row("Contato", item, row_idx), unsafe_allow_html=True) # "Contato" como label genérico
                row_idx += 1
                if i < len(phone_items) - 1:
                    st.markdown("<div style='height: 5px;'></div>", unsafe_allow_html=True)
        else:
            st.markdown(styled_row("Contato", "N/A", row_idx), unsafe_allow_html=True)
            row_idx += 1

        # Emails (lista de itens com zebra striping e separador)
        st.markdown("<h5 style='margin-top: 15px; margin-bottom: 0;'>Emails:</h5>", unsafe_allow_html=True) # Título da seção
        emails = st.session_state.last_consulted_data.get("Emails", "N/A")
        if emails != "N/A":
            email_items = emails.split('\n')
            for i, item in enumerate(email_items):
                st.markdown(styled_row("Email", item, row_idx), unsafe_allow_html=True) # "Email" como label genérico
                row_idx += 1
                if i < len(email_items) - 1:
                    st.markdown("<div style='height: 5px;'></div>", unsafe_allow_html=True)
        else:
            st.markdown(styled_row("Email", "N/A", row_idx), unsafe_allow_html=True)
            row_idx += 1


    with tab_partners:
        row_idx = 0 # Inicia o contador de linhas para esta aba
        st.markdown("<h5 style='margin-bottom: 0;'>Sócios:</h5>", unsafe_allow_html=True) # Título da seção
        socios = st.session_state.last_consulted_data.get('Sócios', 'N/A')
        if socios != "N/A":
            socio_blocks = socios.split('\n\n') # Divide em blocos de sócios
            for i, block in enumerate(socio_blocks):
                st.markdown(styled_row(f"Sócio {i+1}", block, row_idx, is_multiline_content=True), unsafe_allow_html=True) # Passa como multi-line content
                row_idx += 1
                if i < len(socio_blocks) - 1:
                    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True) # Separador maior entre sócios
        else:
            st.markdown(styled_row("Sócio", "N/A", row_idx), unsafe_allow_html=True)
            row_idx += 1

    with tab_registrations:
        row_idx = 0 # Inicia o contador de linhas para esta aba
        st.markdown("<h5 style='margin-bottom: 0;'>Inscrições Estaduais:</h5>", unsafe_allow_html=True) # Título da seção
        inscricoes_estaduais = st.session_state.last_consulted_data.get("Inscricoes Estaduais", "N/A")
        if inscricoes_estaduais != "N/A":
            ie_blocks = inscricoes_estaduais.split('\n\n') # Divide em blocos de IEs
            for i, block in enumerate(ie_blocks):
                st.markdown(styled_row(f"IE {i+1}", block, row_idx, is_multiline_content=True), unsafe_allow_html=True) # Passa como multi-line content
                row_idx += 1
                if i < len(ie_blocks) - 1:
                    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True) # Separador maior entre IEs
        else:
            st.markdown(styled_row("Inscrição Estadual", "N/A", row_idx), unsafe_allow_html=True)
            row_idx += 1


    st.markdown("---")
    st.subheader("Opções de Exportação")
    
    # Botão Salvar em Excel
    if st.button("💾 Salvar em Excel", key="save_excel_button"):
        if st.session_state.last_consulted_data:
            # Cria uma cópia para modificação antes de criar o DataFrame
            data_for_excel = st.session_state.last_consulted_data.copy()

            # Trata campos que podem ter múltiplas linhas no display para uma única linha no Excel
            for key_multi_line in ["CNAEs Secundários", "Telefones", "Emails", "Sócios", "Inscricoes Estaduais"]:
                if key_multi_line in data_for_excel and isinstance(data_for_excel[key_multi_line], str):
                    # Troca "\n\n" por um separador duplo para blocos (Sócios, IEs) e "\n" por um separador simples
                    data_for_excel[key_multi_line] = data_for_excel[key_multi_line].replace("\n\n", " || ").replace("\n", " | ") 

            # Reformatar Data Situação Especial para o Excel, se necessário
            if "Data Situação Especial" in data_for_excel and data_for_excel["Data Situação Especial"] != 'N/A':
                try:
                    dt_obj_esp = datetime.datetime.strptime(data_for_excel["Data Situação Especial"], '%Y-%m-%d')
                    data_for_excel["Data Situação Especial"] = dt_obj_esp.strftime("%d/%m/%Y")
                except ValueError:
                    pass

            df_to_export = pd.DataFrame([data_for_excel])
            
            # Reorganiza as colunas na ordem desejada (sua COLUMN_ORDER do PySide6)
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