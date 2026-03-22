import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(
    page_title="Dashboard Mi Negocio",
    page_icon="🍽️",
    layout="wide",
)

st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem; font-weight: 800; color: #1F4E79;
        text-align: center; margin-bottom: 0.1rem;
    }
    .sub-title {
        font-size: 1rem; color: #666; text-align: center; margin-bottom: 1.2rem;
    }
    .kpi-card {
        background: linear-gradient(135deg, #1F4E79, #2E75B6);
        border-radius: 14px; padding: 1.1rem 1.4rem; color: white;
        text-align: center; box-shadow: 0 4px 14px rgba(0,0,0,0.18);
    }
    .kpi-card .label { font-size: 0.82rem; opacity: 0.85; margin: 0; }
    .kpi-card .value { font-size: 1.9rem; font-weight: 800; margin: 0.2rem 0 0; }
    [data-testid="stSidebar"] { background-color: #EFF4FA; }
</style>
""", unsafe_allow_html=True)

# ── CONFIG ─────────────────────────────────────────────────────────────────
SHEET_NAME = "inventario_minegocio"   # ← Cambia esto por el nombre exacto de tu Google Sheet
WORKSHEET_TAB = 0                     # 0 = primera pestaña del Sheet

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🖼️ Logo del Negocio")
    logo_file = st.file_uploader(
        "Sube tu logo (PNG, JPG)",
        type=["png", "jpg", "jpeg"],
        key="logo"
    )
    st.markdown("---")
    st.markdown("## ☁️ Fuente de Datos")
    st.info("📡 Datos cargados desde **Google Sheets** automáticamente.")
    if st.button("🔄 Actualizar datos"):
        st.cache_data.clear()
        st.rerun()
    st.markdown("---")
    st.caption("Dashboard v2.0 · Mi Negocio 🇭🇳")

# ── Logo + Título ──────────────────────────────────────────────────────────
if logo_file is not None:
    from PIL import Image
    logo_img = Image.open(logo_file)
    col_logo, col_titulo = st.columns([1, 4])
    with col_logo:
        st.image(logo_img, use_container_width=True)
    with col_titulo:
        st.markdown('<div class="main-title" style="text-align:left; padding-top:1rem;">Dashboard de Inventario y Ventas</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-title" style="text-align:left;">Datos en tiempo real desde Google Sheets</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="main-title">🍽️ Dashboard de Inventario y Ventas</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Datos en tiempo real desde Google Sheets</div>', unsafe_allow_html=True)

st.divider()

# ── Cargar datos desde Google Sheets ──────────────────────────────────────
@st.cache_data(ttl=300)  # Refresca cada 5 minutos automáticamente
def load_from_sheets():
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=SCOPES
        )
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).get_worksheet(WORKSHEET_TAB)
        data = sheet.get_all_values()
        return data
    except Exception as e:
        return str(e)

with st.spinner("📡 Conectando con Google Sheets..."):
    raw = load_from_sheets()

if isinstance(raw, str):
    st.error(f"❌ Error al conectar con Google Sheets: {raw}")
    st.info("💡 Verifica que el Secret `gcp_service_account` esté configurado correctamente en Streamlit Cloud.")
    st.stop()

# ── DEBUG TEMPORAL ─────────────────────────────────────────────────────────
with st.expander("🔍 DEBUG - Ver datos crudos del Sheet (borrar después)"):
    st.write(f"Total filas leídas: {len(raw)}")
    st.write("Primeras 6 filas:")
    for i, row in enumerate(raw[:6]):
        st.write(f"Fila {i}: {row}")

# ── Procesar datos ─────────────────────────────────────────────────────────
# Buscar fila de encabezados (la que contiene "Producto")
header_row_idx = None
for i, row in enumerate(raw):
    if any("Producto" in str(cell) for cell in row):
        header_row_idx = i
        break

if header_row_idx is None:
    st.error("❌ No se encontró la fila de encabezados con 'Producto'. Verifica el formato del Sheet.")
    st.stop()

headers = raw[header_row_idx]
data_rows = raw[header_row_idx + 1:]
df_raw = pd.DataFrame(data_rows, columns=headers)
df_raw.columns = df_raw.columns.str.strip()

# Normalizar nombres de columnas (quitar tildes y espacios extra)
import unicodedata
def norm(s):
    s = str(s).strip()
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()

col_map_norm = {
    norm("Producto"):               "Producto",
    norm("Tipo de Producto"):       "Tipo",
    norm("Unidades Vendidas"):      "Unidades_Vendidas",
    norm("Precio por Unidad (L.)"): "Precio_Unidad",
    norm("Stock que Entro"):        "Stock_Entro",
    norm("Stock que Entró"):        "Stock_Entro",
    norm("Mes"):                    "Mes",
    norm("Semana"):                 "Semana",
}

df_raw.columns = [norm(c) for c in df_raw.columns]
rename_map = {c: col_map_norm[c] for c in df_raw.columns if c in col_map_norm}
df_raw.rename(columns=rename_map, inplace=True)

required = ["Producto", "Tipo", "Unidades_Vendidas", "Precio_Unidad", "Stock_Entro", "Mes", "Semana"]
missing = [c for c in required if c not in df_raw.columns]
if missing:
    st.error(f"❌ Columnas faltantes en el Sheet: {missing}")
    with st.expander("Ver columnas detectadas"):
        st.write(list(df_raw.columns))
    st.stop()

df = df_raw[required].copy()
df = df[df["Producto"].notna()]
df = df[df["Producto"].astype(str).str.strip() != ""]
df = df[df["Producto"].astype(str).str.strip().str.upper() != "TOTALES"]

for col in ["Unidades_Vendidas", "Precio_Unidad", "Stock_Entro"]:
    df[col] = pd.to_numeric(
        df[col].astype(str).str.replace(",", "").str.replace("L", "", regex=False).str.replace("l", "", regex=False).str.strip(),
        errors="coerce"
    ).fillna(0)

df["Ingresos"]         = df["Unidades_Vendidas"] * df["Precio_Unidad"]
df["Stock_Disponible"] = df["Stock_Entro"] - df["Unidades_Vendidas"]
df = df[df["Precio_Unidad"] > 0]

# Limpiar columnas de texto
df["Mes"]    = df["Mes"].astype(str).str.strip()
df["Semana"] = df["Semana"].astype(str).str.strip()
df["Mes"]    = df["Mes"].replace({"nan": "", "None": "", "": "Sin mes"})
df["Semana"] = df["Semana"].replace({"nan": "", "None": "", "": "Sin semana"})

if df.empty:
    st.warning("⚠️ No se encontraron datos válidos en el Sheet.")
    st.stop()

# ── Filtros en Sidebar ─────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔍 Filtros")

    # Filtro por Mes
    meses_disp = sorted(df["Mes"].dropna().unique().tolist())
    mes_sel = st.selectbox("📅 Mes", ["Todos"] + meses_disp)

    # Filtro por Semana (tipo slicer)
    semanas_disp = sorted(df["Semana"].dropna().unique().tolist())
    st.markdown("**📆 Semana**")
    semana_sel = st.multiselect(
        "Selecciona semana(s)",
        options=semanas_disp,
        default=semanas_disp,
        key="semana_slicer"
    )

    # Filtro por Categoría
    tipos = ["Todos"] + sorted(df["Tipo"].dropna().unique().tolist())
    tipo_sel = st.selectbox("🏷️ Categoría", tipos)

    top_n = st.slider("Top productos", 5, 20, 10)

# ── Aplicar filtros ────────────────────────────────────────────────────────
df_f = df.copy()
if mes_sel != "Todos":
    df_f = df_f[df_f["Mes"] == mes_sel]
if semana_sel:
    df_f = df_f[df_f["Semana"].isin(semana_sel)]
if tipo_sel != "Todos":
    df_f = df_f[df_f["Tipo"] == tipo_sel]

if df_f.empty:
    st.warning("⚠️ No hay datos para los filtros seleccionados.")
    st.stop()

# ── Indicador de filtros activos ───────────────────────────────────────────
filtros_activos = []
if mes_sel != "Todos":
    filtros_activos.append(f"📅 Mes: **{mes_sel}**")
if semana_sel and len(semana_sel) < len(semanas_disp):
    filtros_activos.append(f"📆 Semanas: **{', '.join(semana_sel)}**")
if tipo_sel != "Todos":
    filtros_activos.append(f"🏷️ Categoría: **{tipo_sel}**")

if filtros_activos:
    st.info("Filtros activos: " + " · ".join(filtros_activos))

# ── KPIs ───────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
kpis = [
    ("📦 Unidades Vendidas",  f"{int(df_f['Unidades_Vendidas'].sum()):,}"),
    ("💰 Ingresos Totales",   f"L. {df_f['Ingresos'].sum():,.2f}"),
    ("🏪 Productos",          f"{df_f['Producto'].nunique():,}"),
    ("📥 Stock Disponible",   f"{int(df_f['Stock_Disponible'].sum()):,}"),
]
for col, (label, value) in zip([k1, k2, k3, k4], kpis):
    with col:
        st.markdown(f"""
        <div class="kpi-card">
            <p class="label">{label}</p>
            <p class="value">{value}</p>
        </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Gráfica de Semanas (si hay varias) ────────────────────────────────────
if df_f["Semana"].nunique() > 1:
    st.subheader("📆 Ingresos por Semana")
    sem_data = df_f.groupby("Semana")["Ingresos"].sum().reset_index().sort_values("Ingresos", ascending=False)
    fig_sem = px.bar(sem_data, x="Semana", y="Ingresos",
                     color="Ingresos", color_continuous_scale="Blues",
                     labels={"Ingresos": "Ingresos (L.)", "Semana": "Semana"})
    fig_sem.update_layout(showlegend=False, coloraxis_showscale=False,
                          plot_bgcolor="white", height=320,
                          margin=dict(l=10, r=10, t=10, b=80),
                          xaxis_tickangle=-30)
    st.plotly_chart(fig_sem, use_container_width=True)
    st.markdown("<br>", unsafe_allow_html=True)

# ── Gráficas fila 1 ────────────────────────────────────────────────────────
c1, c2 = st.columns(2)

with c1:
    st.subheader("🏆 Top Productos más Vendidos")
    top_v = df_f.groupby("Producto")["Unidades_Vendidas"].sum().reset_index().nlargest(top_n, "Unidades_Vendidas")
    fig1 = px.bar(top_v, x="Unidades_Vendidas", y="Producto", orientation="h",
                  color="Unidades_Vendidas", color_continuous_scale="Blues",
                  labels={"Unidades_Vendidas": "Unidades", "Producto": ""})
    fig1.update_layout(showlegend=False, coloraxis_showscale=False,
                       plot_bgcolor="white", height=430,
                       yaxis=dict(autorange="reversed"),
                       margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig1, use_container_width=True)

with c2:
    st.subheader("💵 Top Ingresos por Producto")
    top_i = df_f.groupby("Producto")["Ingresos"].sum().reset_index().nlargest(top_n, "Ingresos")
    fig2 = px.bar(top_i, x="Ingresos", y="Producto", orientation="h",
                  color="Ingresos", color_continuous_scale="Greens",
                  labels={"Ingresos": "Ingresos (L.)", "Producto": ""})
    fig2.update_layout(showlegend=False, coloraxis_showscale=False,
                       plot_bgcolor="white", height=430,
                       yaxis=dict(autorange="reversed"),
                       margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig2, use_container_width=True)

# ── Gráficas fila 2 ────────────────────────────────────────────────────────
c3, c4 = st.columns(2)

with c3:
    st.subheader("📦 Stock Disponible vs Vendido")
    top_s = df_f.groupby("Producto").agg(
        Unidades_Vendidas=("Unidades_Vendidas", "sum"),
        Stock_Disponible=("Stock_Disponible", "sum"),
        Stock_Entro=("Stock_Entro", "sum")
    ).reset_index().nlargest(top_n, "Stock_Entro")
    fig3 = go.Figure()
    fig3.add_trace(go.Bar(name="Vendidas",         x=top_s["Producto"],
                          y=top_s["Unidades_Vendidas"], marker_color="#2E75B6"))
    fig3.add_trace(go.Bar(name="Stock Disponible", x=top_s["Producto"],
                          y=top_s["Stock_Disponible"],  marker_color="#70AD47"))
    fig3.update_layout(barmode="group", plot_bgcolor="white", height=420,
                       xaxis_tickangle=-38,
                       legend=dict(orientation="h", y=1.08),
                       margin=dict(l=10, r=10, t=10, b=80))
    st.plotly_chart(fig3, use_container_width=True)

with c4:
    st.subheader("🍽️ Ingresos por Categoría")
    cat = df_f.groupby("Tipo")["Ingresos"].sum().reset_index().sort_values("Ingresos", ascending=False)
    fig4 = px.pie(cat, values="Ingresos", names="Tipo", hole=0.42,
                  color_discrete_sequence=px.colors.qualitative.Set2)
    fig4.update_traces(textposition="inside", textinfo="percent+label")
    fig4.update_layout(height=420, showlegend=True,
                       margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig4, use_container_width=True)

# ── Tabla detallada ────────────────────────────────────────────────────────
st.divider()
st.subheader("📋 Tabla Detallada")

tabla = df_f[["Producto", "Tipo", "Mes", "Semana", "Unidades_Vendidas",
              "Precio_Unidad", "Stock_Entro", "Stock_Disponible", "Ingresos"]].copy()
tabla.columns = ["Producto", "Categoría", "Mes", "Semana", "Unid. Vendidas",
                 "Precio (L.)", "Stock Entró", "Stock Disponible", "Ingresos (L.)"]
tabla = tabla.sort_values("Ingresos (L.)", ascending=False).reset_index(drop=True)

st.dataframe(
    tabla.style
    .format({"Precio (L.)": "L. {:,.2f}", "Ingresos (L.)": "L. {:,.2f}"})
    .background_gradient(subset=["Ingresos (L.)"], cmap="Blues")
    .background_gradient(subset=["Unid. Vendidas"], cmap="Greens"),
    use_container_width=True,
    height=500,
)

csv = tabla.to_csv(index=False).encode("utf-8")
st.download_button(
    label="⬇️ Descargar tabla en CSV",
    data=csv,
    file_name="resumen_ventas.csv",
    mime="text/csv",
)

st.markdown("---")
st.caption(f"📡 Datos cargados desde Google Sheets · Sheet: `{SHEET_NAME}` · Dashboard v2.0 🇭🇳")
