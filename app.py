import streamlit as st

NEW_PORTAL_URL = "https://ibsecbspricetax.streamlit.app"

st.set_page_config(
    page_title="Consulta CNPJ - Adapta (Em construção)",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ---- Estilo (dark + amarelo) ----
st.markdown(
    """
    <style>
        .stApp { background-color: #1A1A1A; color: #EEEEEE; }
        h1, h2, h3, h4, h5, h6 { color: #FFC300; }
        a { color: #FFD700; text-decoration: none; font-weight: 700; }
        a:hover { text-decoration: underline; }
        .card {
            background:#222222;
            border:1px solid #FFC300;
            border-radius:14px;
            padding:18px 18px;
            box-shadow: 0 0 0 0.1rem rgba(255,195,0,.15);
        }
        .muted { color:#BDBDBD; font-size: 0.98rem; }
        .big {
            font-size: 1.15rem;
            line-height: 1.5;
            margin-top: 8px;
        }
        .cta-btn a {
            display:inline-block;
            background:#FFC300;
            color:#111111 !important;
            padding:12px 16px;
            border-radius:12px;
            font-weight:800;
            letter-spacing:0.2px;
            margin-top: 14px;
        }
        .cta-btn a:hover { background:#FFD700; }
        .pill {
            display:inline-block;
            background:#2a2a2a;
            border:1px dashed #6b7280;
            color:#9ca3af;
            padding:6px 10px;
            border-radius:999px;
            font-weight:800;
            font-size:12px;
            margin-bottom: 10px;
        }
        .footer {
            margin-top: 18px;
            padding-top: 12px;
            border-top: 1px solid #333333;
            color:#9ca3af;
            font-size: 12px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---- Conteúdo (bloqueio total) ----
st.markdown("<div class='pill'>🚧 Em construção</div>", unsafe_allow_html=True)

st.markdown(
    """
    <div class="card">
        <h1 style="margin:0;">Estamos em construção</h1>
        <div class="big">
            Gentileza utilizar o novo portal:
        </div>

        <div class="cta-btn">
            <a href="{url}" target="_blank" rel="noopener noreferrer">Acessar o novo portal PriceTax</a>
        </div>

        <div class="big" style="margin-top:14px;">
            Lá você não consulta apenas CNPJ — tem dúvidas sobre <b>IBS</b> e <b>CBS</b>?<br/>
            Entre no site e teste nosso <b>hub de soluções PriceTax</b>.
        </div>

        <div class="footer">
            Se você salvou este link antigo nos favoritos, atualize para o novo portal.
        </div>
    </div>
    """.format(url=NEW_PORTAL_URL),
    unsafe_allow_html=True,
)

# Opcional: remove espaço extra e impede "interações" sem sentido
st.stop()
