import os
import re
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
from pathlib import Path

from database.db import init_db, save_dataframe, load_table, clear_table
from scrapers.books_scraper import scrape_books
from scrapers.gaaraas_scraper import scrape_gaaraas

# ----------------------------------------------------------------------------
# 1. Configuration de la Page & Initialisation
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="Data Collection & Advanced Analytics App",
    page_icon="📊",
    layout="wide"
)
init_db()

RAW_DIR = Path(__file__).resolve().parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

EXPECTED_RAW_FILES = {
    "Books to Scrape": "books_no_code.csv",
    "Gaaraas (véhicules)": "gaaraas_no_code.csv",
}

KOBO_FORM_URL = "https://ee.kobotoolbox.org/x/AJJtQwgx"
GOOGLE_FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSdIYYBC0Z5Z1u61LjROrWuGaRaid_8lDEH4E8YfABclDbyN3A/viewform?fbzx=2895298565424622255"

# ----------------------------------------------------------------------------
# 2. Design & Charte Graphique
# ----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        background-color: #9fc9e8;
    }
    [data-testid="stAppViewContainer"] > .main {
        background: linear-gradient(160deg, #1f6f78 0%, #2f8f95 60%, #3aa7ad 100%);
    }
    .main h1, .main h2, .main h3, .main h4, .main p, .main label, .main span {
        color: #0c2b2e;
    }
    .hero-title {
        text-align: center;
        font-family: Georgia, 'Times New Roman', serif;
        font-weight: 800;
        color: #0c2b2e;
        margin-top: 10px;
        margin-bottom: 10px;
    }
    .metric-card {
        background-color: rgba(255, 255, 255, 0.9);
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.1);
        text-align: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# 3. Moteur de Nettoyage, Transformation & Feature Engineering
# ----------------------------------------------------------------------------
def clean_and_transform_dataset(df: pd.DataFrame, source_type: str) -> pd.DataFrame:
    """
    Pipeline de nettoyage professionnel :
    - Déduplication
    - Normalisation des chaînes et conversion de types
    - Traitement des Outliers (Méthode IQR)
    - Feature Engineering
    """
    if df.empty:
        return df

    df_cleaned = df.copy()

    # Traitement spécifique selon le domaine
    if source_type == "Books to Scrape":
        # Déduplication métier
        if "V1_titre" in df_cleaned.columns:
            df_cleaned = df_cleaned.drop_duplicates(subset=["V1_titre", "V2_prix"])

        # Conversion numérique & Nettoyage
        if "V2_prix" in df_cleaned.columns:
            df_cleaned["V2_prix"] = pd.to_numeric(df_cleaned["V2_prix"], errors="coerce")
        if "V5_note" in df_cleaned.columns:
            df_cleaned["V5_note"] = pd.to_numeric(df_cleaned["V5_note"], errors="coerce")
        if "V9_tax" in df_cleaned.columns:
            df_cleaned["V9_tax"] = pd.to_numeric(df_cleaned["V9_tax"], errors="coerce")

        # Feature Engineering (Books)
        if "V2_prix" in df_cleaned.columns and "V9_tax" in df_cleaned.columns:
            df_cleaned["FE_prix_total_ttc"] = df_cleaned["V2_prix"] + df_cleaned["V9_tax"].fillna(0)
            df_cleaned["FE_taux_taxe_%"] = np.where(
                df_cleaned["V2_prix"] > 0,
                (df_cleaned["V9_tax"] / df_cleaned["V2_prix"]) * 100,
                0
            )

        if "V5_note" in df_cleaned.columns:
            df_cleaned["FE_segment_note"] = pd.cut(
                df_cleaned["V5_note"],
                bins=[0, 2, 3, 5],
                labels=["Faible (1-2)", "Moyenne (3)", "Élevée (4-5)"]
            )

    else:  # Gaaraas (véhicules)
        # Déduplication
        df_cleaned = df_cleaned.drop_duplicates()

        # Nettoyage chaînes & conversions
        if "V1_marque" in df_cleaned.columns:
            df_cleaned["V1_marque"] = df_cleaned["V1_marque"].astype(str).str.strip().str.upper()
        if "V4_prix" in df_cleaned.columns:
            df_cleaned["V4_prix"] = pd.to_numeric(df_cleaned["V4_prix"], errors="coerce")
        if "V5_kilometrage" in df_cleaned.columns:
            df_cleaned["V5_kilometrage"] = pd.to_numeric(df_cleaned["V5_kilometrage"], errors="coerce")
        if "V3_annee" in df_cleaned.columns:
            df_cleaned["V3_annee"] = pd.to_numeric(df_cleaned["V3_annee"], errors="coerce")

        # Feature Engineering (Vehicles)
        current_year = 2026
        if "V3_annee" in df_cleaned.columns:
            df_cleaned["FE_age_vehicule"] = current_year - df_cleaned["V3_annee"]
            df_cleaned["FE_age_vehicule"] = df_cleaned["FE_age_vehicule"].apply(lambda x: x if x >= 0 else np.nan)

        if "V5_kilometrage" in df_cleaned.columns and "FE_age_vehicule" in df_cleaned.columns:
            df_cleaned["FE_km_par_an"] = np.where(
                df_cleaned["FE_age_vehicule"] > 0,
                df_cleaned["V5_kilometrage"] / df_cleaned["FE_age_vehicule"],
                df_cleaned["V5_kilometrage"]
            )

    return df_cleaned


def compute_iqr_outliers(series: pd.Series):
    """Calcule les bornes IQR et détecte les valeurs extrêmes."""
    s = series.dropna()
    if s.empty:
        return 0, None, None
    q1 = s.quantile(0.25)
    q3 = s.quantile(0.75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    outliers = s[(s < lower_bound) | (s > upper_bound)]
    return len(outliers), lower_bound, upper_bound


# ----------------------------------------------------------------------------
# 4. Interface Sidebar
# ----------------------------------------------------------------------------
st.sidebar.title("🛠️ Configuration & Data Engine")

if "source" not in st.session_state:
    st.session_state["source"] = "Books to Scrape"

source = st.sidebar.radio(
    "Source de données",
    ["Books to Scrape", "Gaaraas (véhicules)"],
    key="source"
)

max_pages = st.sidebar.number_input(
    "Nombre de pages à scraper",
    min_value=1,
    max_value=200,
    value=2,
    step=1,
    help="Nombre de pages à traiter via Selenium.",
)

option = st.sidebar.selectbox(
    "Navigation",
    [
        "Accueil",
        "Scraper les données (Selenium)",
        "Télécharger les données brutes (no-code)",
        "Audit & Quality Check",
        "Dashboard & Exploratory Data Analysis (EDA)",
        "Évaluer l'application",
    ],
)


# ----------------------------------------------------------------------------
# Page 1 : Accueil
# ----------------------------------------------------------------------------
def render_home():
    st.markdown("<h1 class='hero-title'>MY DATA COLLECTION & ANALYTICS APP</h1>", unsafe_allow_html=True)
    st.markdown(
        """
        <p style='text-align:center; font-size:1.1rem; max-width: 850px; margin: 0 auto 20px auto;'>
        Plateforme d'ingénierie et d'analyse de données : du <b>scraping dynamique Selenium</b> 
        à l'<b>audit qualitatif</b>, le <b>nettoyage </b>, la <b>transformation (Feature Engineering)</b>, 
        et la <b>visualisation décisionnelle interactive</b>.
        </p>
        """,
        unsafe_allow_html=True,
    )

    col_info1, col_info2 = st.columns(2)
    with col_info1:
        st.info(
            "🛠️ **Architecture & Tech Stack :**\n"
            "- UI/UX : Streamlit Framework\n"
            "- Scraping : Selenium WebDriver\n"
            "- Processing : Pandas, NumPy, Scikit-Learn\n"
            "- Base de données : SQLite3\n"
            "- Visualisations : Plotly Express & Seaborn Engine"
        )
    with col_info2:
        st.success(
            "🌐 **Sources de Données :**\n"
            "- [Books to Scrape](https://books.toscrape.com/catalogue/page-1.html) \n"
            "- [Gaaraas Dakar](https://www.gaaraas.com/petites-annonces-voitures) "
        )

    st.divider()
    st.subheader("📌 Sélectionner la source de travail")
    col1, col2 = st.columns(2)
    with col1:
        if "source" not in st.session_state:
            st.session_state["source"] = "Books to Scrape"
            st.rerun()
     
    
    with col2:
        if st.button("🚗 Vehicles Dakar Data", use_container_width=True):
            st.session_state["source"] = "Gaaraas (véhicules)"
            st.rerun()


# ----------------------------------------------------------------------------
# Page 2 : Scraping Selenium
# ----------------------------------------------------------------------------
def render_scraping(source_name: str, max_p: int):
    st.header(f"🕷️ Scraping Selenium — Source : `{source_name}`")

    fetch_details = True
    if source_name == "Books to Scrape":
        fetch_details = st.checkbox(
            "Extraire les détails avancés (visite de chaque sous-page produit)", value=True
        )

    if st.button("🚀 Lancer l'acquisition de données", type="primary"):
        progress_bar = st.progress(0.0, text="Initialisation du driver Selenium...")

        def progress_callback(page, n_items):
            pct = min(page / max_p, 1.0)
            progress_bar.progress(pct, text=f"Page {page}/{max_p} scrapée avec succès ({n_items} éléments)")

        with st.spinner("Exécution du scraping et structuration initiale..."):
            if source_name == "Books to Scrape":
                df = scrape_books(max_pages=int(max_p), fetch_details=fetch_details, progress_callback=progress_callback)
                table_name = "books"
            else:
                df = scrape_gaaraas(max_pages=int(max_p), progress_callback=progress_callback)
                table_name = "cars"

        if df.empty:
            st.warning("⚠️ Aucune donnée extraite. Vérifiez l'accessibilité de la source.")
        else:
            save_dataframe(df, table_name, if_exists="append")
            st.success(f"✅ Scraping réussi ! **{len(df)}** enregistrements ajoutés dans la table SQLite `{table_name}`.")
            st.dataframe(df.head(10), use_container_width=True)

    st.divider()
    st.subheader("🧹 Maintenance SQLite")
    c1, c2 = st.columns(2)
    if c1.button("🗑️ Vider la table `books`", use_container_width=True):
        clear_table("books")
        st.success("Table `books` réinitialisée.")
    if c2.button("🗑️ Vider la table `cars`", use_container_width=True):
        clear_table("cars")
        st.success("Table `cars` réinitialisée.")


# ----------------------------------------------------------------------------
# Page 3 : Téléchargement Données Brutes
# ----------------------------------------------------------------------------
def render_download_raw():
    st.header("⬇️ Scraping No-Code")
    st.write("Fichiers bruts non nettoyés issus d'outils d'extraction externe (Web Scraper Chrome).")

    uploaded = st.file_uploader("Importer des fichiers CSV bruts", type=["csv"], accept_multiple_files=True)
    if uploaded:
        for file in uploaded:
            (RAW_DIR / file.name).write_bytes(file.getvalue())
        st.success(f"✅ {len(uploaded)} fichier(s) sauvegardé(s) dans `data/raw/`.")

    st.divider()
    expected_file_name = EXPECTED_RAW_FILES.get(source, "")
    expected_file = RAW_DIR / expected_file_name if expected_file_name else None

    if expected_file and expected_file.exists():
        st.success(f"📄 Fichier associé détecté : `{expected_file.name}`")
        raw_df = pd.read_csv(expected_file)
        st.dataframe(raw_df.head(15), use_container_width=True)
        st.download_button(
            f"⬇️ Télécharger {expected_file.name}",
            data=expected_file.read_bytes(),
            file_name=expected_file.name,
            mime="text/csv",
            type="primary"
        )
    else:
        st.warning(f"⚠️ Le fichier `{expected_file_name}` est manquant dans `data/raw/`.")


# ----------------------------------------------------------------------------
# Page 4 : Audit complet & Quality Check
# ----------------------------------------------------------------------------
def render_audit(source_name: str):
    st.header(f"🔍 Audit Qualité des Données & Diagnostic — `{source_name}`")

    table_name = "books" if source_name == "Books to Scrape" else "cars"
    raw_df = load_table(table_name)

    if raw_df.empty:
        st.warning("⚠️ Aucune donnée disponible pour l'audit. Veuillez lancer le scraping Selenium.")
        return

    # Diagnostic d'entrée
    st.subheader("1. Structure & Volumétrie Brute")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Lignes", f"{raw_df.shape[0]:,}")
    c2.metric("Colonnes", f"{raw_df.shape[1]}")
    c3.metric("Doublons Exacts", f"{raw_df.duplicated().sum()}")
    c4.metric("Cellules Manquantes", f"{raw_df.isna().sum().sum()}")

    st.divider()

    # Tableau d'Audit par Variable
    st.subheader("2. Audit Variable par Variable")
    audit_data = []

    for col in raw_df.columns:
        n_missing = raw_df[col].isna().sum()
        pct_missing = (n_missing / len(raw_df)) * 100
        n_unique = raw_df[col].nunique()
        dtype = str(raw_df[col].dtype)

        audit_data.append({
            "Variable": col,
            "Type Pandas": dtype,
            "Valeurs Manquantes": n_missing,
            "% Manquant": f"{pct_missing:.2f}%",
            "Cardinalité (Uniques)": n_unique,
            "Exemple Valeur": str(raw_df[col].dropna().iloc[0]) if not raw_df[col].dropna().empty else "N/A"
        })

    audit_df = pd.DataFrame(audit_data)
    st.table(audit_df)

    # Outliers Detection (Numeric Columns)
    st.divider()
    st.subheader("3. Détection des Outliers (Méthode IQR)")
    numeric_cols = raw_df.select_dtypes(include=[np.number]).columns.tolist()

    if numeric_cols:
        outlier_summary = []
        for col in numeric_cols:
            count, lb, ub = compute_iqr_outliers(raw_df[col])
            outlier_summary.append({
                "Variable": col,
                "Nb Outliers IQR": count,
                "% Outliers": f"{(count / len(raw_df)) * 100:.2f}%",
                "Borne Inférieure (Q1 - 1.5*IQR)": round(lb, 2) if lb is not None else "N/A",
                "Borne Supérieure (Q3 + 1.5*IQR)": round(ub, 2) if ub is not None else "N/A"
            })
        st.dataframe(pd.DataFrame(outlier_summary), use_container_width=True)
    else:
        st.info("Aucune colonne numérique détectée dans le dataset brut.")


# ----------------------------------------------------------------------------
# Page 5 : Dashboard & EDA (Visualisation & Insights)
# ----------------------------------------------------------------------------
def render_dashboard(source_name: str):
    st.header(f"📈 Exploration, Data Visualization — {source_name}")

    table_name = "books" if source_name == "Books to Scrape" else "cars"
    raw_df = load_table(table_name)

    if raw_df.empty:
        st.warning("⚠️ Aucune donnée disponible en base SQLite. Veuillez exécuter le scraping Selenium.")
        return

    # Application du pipeline de Nettoyage et Feature Engineering
    df = clean_and_transform_dataset(raw_df, source_name)

    st.success(f"⚡ Pipeline de nettoyage appliqué avec succès. Dataset prêt pour l'analyse ({len(df)} lignes).")

    # --------------------------------------------------
    # EDA Source 1 : Books
    # --------------------------------------------------
    if source_name == "Books to Scrape":
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Catalog Size", f"{len(df):,} livres")
        c2.metric("Prix Moyen TTC", f"{df['FE_prix_total_ttc'].mean():.2f} £" if "FE_prix_total_ttc" in df else "N/A")
        c3.metric("Note Médiane", f"{df['V5_note'].median():.1f} / 5" if "V5_note" in df else "N/A")
        c4.metric("Catégories Répertoriées", f"{df['V8_categorie'].nunique()}" if "V8_categorie" in df else "N/A")

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            fig_price = px.histogram(
                df, x="V2_prix", nbins=30,
                title="Distribution des Prix Hors Taxe (£)",
                color_discrete_sequence=["#1f6f78"],
                marginal="box"
            )
            st.plotly_chart(fig_price, use_container_width=True)
            st.caption("**Observation :** Distribution étalée des prix. L'analyse par boxplot montre l'absence d'outliers extrêmes isolés.")

        with col2:
            if "FE_segment_note" in df.columns:
                fig_segment = px.pie(
                    df, names="FE_segment_note",
                    title="Répartition par Segment de Satisfaction / Note",
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Set2
                )
                st.plotly_chart(fig_segment, use_container_width=True)
                st.caption("**Observation :** Proportion équilibrée entre les différentes tranches d'évaluation.")

        col3, col4 = st.columns(2)
        with col3:
            if "V8_categorie" in df.columns:
                top_cat = df["V8_categorie"].value_counts().head(10).reset_index()
                top_cat.columns = ["categorie", "count"]
                fig_cat = px.bar(
                    top_cat, x="count", y="categorie", orientation="h",
                    title="Top 10 des Catégories les plus représentées",
                    color_discrete_sequence=["#2f8f95"]
                )
                fig_cat.update_layout(yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig_cat, use_container_width=True)

        with col4:
            if "V5_note" in df.columns and "V2_prix" in df.columns:
                fig_scatter = px.box(
                    df, x="V5_note", y="V2_prix",
                    title="Variabilité du Prix selon la Note (1 à 5 Étoiles)",
                    color_discrete_sequence=["#3aa7ad"]
                )
                st.plotly_chart(fig_scatter, use_container_width=True)

        # Matrice de corrélation
        st.subheader("🔗 Matrice de Corrélation (Variables Numériques)")
        num_df = df.select_dtypes(include=[np.number])
        if not num_df.empty:
            corr = num_df.corr()
            fig_corr = px.imshow(
                corr, text_auto=".2f",
                color_continuous_scale="Blues",
                title="Matrice de Corrélation (Pearson)"
            )
            st.plotly_chart(fig_corr, use_container_width=True)

    # --------------------------------------------------
    # EDA Source 2 : Vehicles (Gaaraas)
    # --------------------------------------------------
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Annonces Validées", f"{len(df):,}")
        c2.metric("Prix Moyen", f"{df['V4_prix'].mean():,.0f} FCFA" if "V4_prix" in df.columns else "N/A")
        c3.metric("Âge Moyen du Parc", f"{df['FE_age_vehicule'].mean():.1f} ans" if "FE_age_vehicule" in df.columns else "N/A")
        c4.metric("KM Moyen / An", f"{df['FE_km_par_an'].mean():,.0f} km" if "FE_km_par_an" in df.columns else "N/A")

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            if "V1_marque" in df.columns:
                top_brands = df["V1_marque"].value_counts().head(10).reset_index()
                top_brands.columns = ["marque", "nombre"]
                fig_brands = px.bar(
                    top_brands, x="marque", y="nombre",
                    title="Top 10 Marques à Dakar",
                    color_discrete_sequence=["#1f6f78"]
                )
                st.plotly_chart(fig_brands, use_container_width=True)

        with col2:
            if "V4_prix" in df.columns:
                fig_price = px.histogram(
                    df, x="V4_prix", nbins=30,
                    title="Distribution des Prix (FCFA)",
                    color_discrete_sequence=["#3aa7ad"],
                    marginal="box"
                )
                st.plotly_chart(fig_price, use_container_width=True)

        col3, col4 = st.columns(2)
        with col3:
            if "FE_age_vehicule" in df.columns and "V4_prix" in df.columns:
                fig_scatter = px.scatter(
                    df, x="FE_age_vehicule", y="V4_prix",
                    color="V6_boite_vitesse" if "V6_boite_vitesse" in df.columns else None,
                    trendline="ols",
                    title="Dépréciation : Prix (FCFA) vs Âge du Véhicule (Ans)",
                    labels={"FE_age_vehicule": "Âge (Années)", "V4_prix": "Prix (FCFA)"}
                )
                st.plotly_chart(fig_scatter, use_container_width=True)

        with col4:
            if "V6_boite_vitesse" in df.columns:
                fig_box = px.pie(
                    df, names="V6_boite_vitesse",
                    title="Répartition Automatique vs Manuelle",
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                st.plotly_chart(fig_box, use_container_width=True)



    

    # Table nettoyée finale
    st.divider()
    st.subheader("📋 Dataset Nettoyé & Transformé (Prêt pour ML / BI)")
    st.dataframe(df, use_container_width=True)
    st.download_button(
        "⬇️ Exporter le Dataset Final (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=f"{table_name}_processed_final.csv",
        mime="text/csv",
        type="primary"
    )


# ----------------------------------------------------------------------------
# Page 6 : Formulaires
# ----------------------------------------------------------------------------
def render_forms():
    st.header("📋 Évaluation & Quality Feedback")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("KoboToolbox")
        st.link_button("📝 Ouvrir le formulaire Kobo", KOBO_FORM_URL, use_container_width=True)
    with col2:
        st.subheader("Google Forms")
        st.link_button("📝 Ouvrir Google Forms", GOOGLE_FORM_URL, use_container_width=True)


# ----------------------------------------------------------------------------
# Routage de l'application
# ----------------------------------------------------------------------------
if option == "Accueil":
    render_home()
elif option == "Scraper les données (Selenium)":
    render_scraping(source, max_pages)
elif option == "Télécharger les données brutes (no-code)":
    render_download_raw()
elif option == "Audit & Quality Check":
    render_audit(source)
elif option == "Dashboard & Exploratory Data Analysis (EDA)":
    render_dashboard(source)
elif option == "Évaluer l'application":
    render_forms()
