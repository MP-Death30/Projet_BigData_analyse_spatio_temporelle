import findspark
findspark.init()

import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import os
import signal
import time

# Module local pour la couche Speed (RTE)
import rte_layer
from pyspark.sql import SparkSession

# ==========================================
# CONFIGURATION & STYLES
# ==========================================
st.set_page_config(layout="wide", page_title="Big Data Dashboard")

# --- CORRECTION : SESSION SPARK DÉFINIE GLOBALEMENT ---
# Indispensable pour être accessible par NYC (Batch) ET RTE (Speed/Ingestion)
@st.cache_resource
def get_spark_session():
    return SparkSession.builder \
        .appName("Dashboard_App") \
        .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:9000") \
        .getOrCreate()
# ------------------------------------------------------

# --- PALETTE OFFICIELLE RTE (Approximative) ---
# Couleurs extraites du site éCO2mix pour un rendu fidèle
RTE_COLORS = {
    'Nucléaire': '#F5D300',      # Jaune RTE
    'Hydraulique': '#2774B8',    # Bleu RTE
    'Eolien': '#84C66B',         # Vert clair
    'Solaire': '#F29400',        # Orange
    'Gaz': '#F05A28',            # Rouge orangé
    'Bioénergies': '#166A57',    # Vert foncé
    'Charbon': '#A0A0A0',        # Gris
    'Fioul': '#805B50',          # Marron
    'Pompage': '#113366',        # Bleu nuit
    'Consommation': '#333333'    # Noir
}

# Ordre d'empilement logique (Base -> Pointe)
STACK_ORDER = [
    'Nucléaire', 'Hydraulique', 'Bioénergies',  # Base & Pilotable vert
    'Eolien', 'Solaire',                        # Intermittent
    'Gaz', 'Charbon', 'Fioul',                  # Thermique fossile (Pointe)
    'Pompage'
]

# Coordonnées pour la carte des échanges
COUNTRY_COORDS = {
    'France': [46.603354, 1.888334],
    'Angleterre': [51.0, 0.5],          # Décalé vers la manche pour visibilité
    'Espagne': [42.0, -1.0],            # Proche frontière Pyrénées
    'Italie': [44.5, 6.5],              # Proche frontière Alpes
    'Suisse': [46.5, 6.0],              # Proche Genève
    'Allemagne-Belgique': [50.0, 5.0]   # Frontière Nord-Est
}

# ==============================================================================
# NAVIGATION (SIDEBAR)
# ==============================================================================
st.sidebar.title("Navigation")
app_mode = st.sidebar.radio("Choisir l'application", ["NYC Air Quality", "RTE Production"])

# ==============================================================================
# APPLICATION 1 : NYC AIR QUALITY (BATCH)
# ==============================================================================
if app_mode == "NYC Air Quality":
    
    # Initialisation des états
    if 'selected_geocode' not in st.session_state:
        st.session_state.selected_geocode = None
    if 'dropdown_selector' not in st.session_state:
        st.session_state.dropdown_selector = "Tous quartiers"

    # 1. FONCTIONS CHARGEMENT & CALCULS
    @st.cache_data
    def load_data():
        spark = get_spark_session()
        hdfs_base = "/user/mathis/datalake/processed/dashboard"
        
        # Lecture HDFS via Spark
        # Note : On lit et on convertit en Pandas pour l'affichage
        try:
            air = spark.read.parquet(f"{hdfs_base}/air_quality.parquet").toPandas()
            weather = spark.read.parquet(f"{hdfs_base}/weather.parquet").toPandas()
        except Exception as e:
            st.error(f"Impossible de lire les fichiers HDFS : {e}")
            st.stop()
            
        # Lecture GeoJSON local (fichier statique)
        geo = gpd.read_file("dashboard_map.geojson")
        
        # Nettoyage & Typage
        geo['GEOCODE'] = geo['GEOCODE'].astype(str)
        
        if 'LATITUDE_ZONE' not in geo.columns:
            try:
                geo_temp = geo.to_crs(epsg=2263)
                centroids = geo_temp.geometry.centroid.to_crs(epsg=4326)
            except:
                centroids = geo.geometry.centroid
            geo['LATITUDE_ZONE'] = centroids.y
            geo['LONGITUDE_ZONE'] = centroids.x
        
        if 'DATE_OBSERVATION' in air.columns:
            air['DATE_OBSERVATION'] = pd.to_datetime(air['DATE_OBSERVATION'])
            
        if 'DATE' in weather.columns:
            weather['DATE'] = pd.to_datetime(weather['DATE'])
        
        # Conversions Météo
        if 'TEMP' in weather.columns:
            weather['TEMP'] = (weather['TEMP'] - 32) * 5.0/9.0
        if 'DEWP' in weather.columns:
            weather['DEWP'] = (weather['DEWP'] - 32) * 5.0/9.0
        if 'WDSP' in weather.columns:
            weather['WDSP'] = weather['WDSP'] * 1.852
    
        # Filtres valeurs aberrantes
        if 'WDSP' in weather.columns:
            weather = weather[weather['WDSP'] <= 150]
        if 'DEWP' in weather.columns:
            weather = weather[weather['DEWP'] <= 40]
        
        stations = pd.DataFrame()
        if not weather.empty:
            stations = weather[['ID_STATION', 'NAME', 'LATITUDE', 'LONGITUDE']].drop_duplicates()
        
        return geo, air, weather, stations

    def haversine_vectorized(lon1, lat1, lon2, lat2):
        lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2
        c = 2 * np.arcsin(np.sqrt(a))
        return 6371 * c 

    def calculate_global_metrics(geo_df, weather_df, stations_df, radius_km):
        results = []
        weather_agg = weather_df.groupby('ID_STATION')[['TEMP', 'WDSP', 'DEWP']].mean().reset_index()
        stations_w_weather = stations_df.merge(weather_agg, on='ID_STATION')
        
        if stations_w_weather.empty:
            return pd.DataFrame()

        for _, row in geo_df.iterrows():
            lat_q, lon_q = row['LATITUDE_ZONE'], row['LONGITUDE_ZONE']
            dists = haversine_vectorized(
                lon_q, lat_q, 
                stations_w_weather['LONGITUDE'].values, 
                stations_w_weather['LATITUDE'].values
            )
            
            mask = dists <= radius_km
            nearby_stations = stations_w_weather[mask].copy()
            nearby_dists = dists[mask]
            
            if not nearby_stations.empty:
                weights = 1 / (nearby_dists + 0.1)
                w_temp = np.average(nearby_stations['TEMP'], weights=weights)
                w_wind = np.average(nearby_stations['WDSP'], weights=weights)
                w_dewp = np.average(nearby_stations['DEWP'], weights=weights)
                
                results.append({
                    'GEOCODE': str(row['GEOCODE']),
                    'W_TEMP': round(w_temp, 1),
                    'W_WIND': round(w_wind, 1),
                    'W_DEWP': round(w_dewp, 1),
                    'NB_STATIONS': len(nearby_stations)
                })
            else:
                results.append({
                    'GEOCODE': str(row['GEOCODE']),
                    'W_TEMP': None, 'W_WIND': None, 'W_DEWP': None, 'NB_STATIONS': 0
                })
        return pd.DataFrame(results)

    # 2. CHARGEMENT DONNÉES
    geo, df_air, df_weather, df_stations = load_data()

    if geo is not None:
        # --- BOUTON D'ARRÊT ---
        st.sidebar.header("⚙️ Contrôle")
        if st.sidebar.button("🛑 Arrêter le Dashboard"):
            st.sidebar.warning("Arrêt du serveur en cours...")
            time.sleep(1)
            os.kill(os.getpid(), signal.SIGTERM)

        st.sidebar.markdown("---")
        st.sidebar.header("🎛️ Filtres & Paramètres")

        # Filtres
        min_date, max_date = df_air['DATE_OBSERVATION'].min(), df_air['DATE_OBSERVATION'].max()
        start_date, end_date = st.sidebar.date_input(
            "Période d'analyse", [min_date, max_date], min_value=min_date, max_value=max_date
        )

        mask_air_date = (df_air['DATE_OBSERVATION'].dt.date >= start_date) & (df_air['DATE_OBSERVATION'].dt.date <= end_date)
        df_air_filtered = df_air[mask_air_date]

        valid_pollutants = sorted(df_air_filtered[df_air_filtered['VALEUR'].notna()]['NOM_POLLUANT'].unique())

        if len(valid_pollutants) > 0:
            selected_polluant = st.sidebar.selectbox("Polluant", valid_pollutants)
        else:
            st.sidebar.error("⚠️ Aucune donnée de pollution.")
            selected_polluant = None

        radius = st.sidebar.slider("Rayon stations météo (km)", 1, 100, 15)
        meteo_vars = ['Température', 'Vitesse Vent', 'Point de Rosée']
        selected_meteo_vars = st.sidebar.multiselect("Graphiques Météo", meteo_vars, default=['Température'])

        if selected_polluant is None:
            st.stop()

        mask_weather_date = (df_weather['DATE'].dt.date >= start_date) & (df_weather['DATE'].dt.date <= end_date)
        df_weather_filtered = df_weather[mask_weather_date]

        # Indicateurs Sidebar
        with st.sidebar:
            st.markdown("---")
            st.markdown("### ℹ️ Info Stations")
            active_stations = df_weather_filtered[['ID_STATION']].drop_duplicates()
            active_stations_coords = active_stations.merge(df_stations, on='ID_STATION')

            if st.session_state.selected_geocode is None:
                lat_center = geo['LATITUDE_ZONE'].mean()
                lon_center = geo['LONGITUDE_ZONE'].mean()
                if not active_stations_coords.empty:
                    dists_s = haversine_vectorized(lon_center, lat_center, active_stations_coords['LONGITUDE'].values, active_stations_coords['LATITUDE'].values)
                    nb_visible = np.sum(dists_s <= radius)
                    st.metric(f"Stations (Global, {radius} km)", nb_visible)
            else:
                sel_geo = geo[geo['GEOCODE'] == st.session_state.selected_geocode]
                if not sel_geo.empty:
                    lat_s = sel_geo.iloc[0]['LATITUDE_ZONE']
                    lon_s = sel_geo.iloc[0]['LONGITUDE_ZONE']
                    if not active_stations_coords.empty:
                        dists_s = haversine_vectorized(lon_s, lat_s, active_stations_coords['LONGITUDE'].values, active_stations_coords['LATITUDE'].values)
                        nb_visible = np.sum(dists_s <= radius)
                        st.metric(f"Stations (Local, {radius} km)", nb_visible)

        # Préparation Données Carte
        df_air_map = df_air_filtered[df_air_filtered['NOM_POLLUANT'] == selected_polluant]
        if not df_air_map.empty:
            air_agg = df_air_map.groupby('GEOJOIN_ID')['VALEUR'].mean().reset_index()
            air_agg.columns = ['GEOCODE', 'MEAN_POLLUANT']
            air_agg['GEOCODE'] = air_agg['GEOCODE'].astype(str)
        else:
            air_agg = pd.DataFrame(columns=['GEOCODE', 'MEAN_POLLUANT'])

        weather_metrics_df = calculate_global_metrics(geo, df_weather_filtered, df_stations, radius)

        gdf_display = geo.merge(air_agg, on='GEOCODE', how='left')
        if not weather_metrics_df.empty:
            gdf_display = gdf_display.merge(weather_metrics_df, on='GEOCODE', how='left')

        gdf_display['MEAN_POLLUANT'] = gdf_display['MEAN_POLLUANT'].fillna(0).round(2)
        gdf_display['W_TEMP'] = gdf_display['W_TEMP'].fillna(0)
        gdf_display['NB_STATIONS'] = gdf_display['NB_STATIONS'].fillna(0).astype(int)

        # Préparation Données Graphiques
        chart_air_src = pd.DataFrame()
        chart_weather_src = pd.DataFrame()
        
        current_title, current_caption = "", ""
        avg_polluant, avg_temp, avg_wind = 0, 0, 0

        if st.session_state.selected_geocode is None:
            current_title = "New York City (Global)"
            current_caption = "Moyenne de tous les quartiers"
            valid_data = gdf_display[gdf_display['MEAN_POLLUANT'] > 0]
            if not valid_data.empty:
                avg_polluant = valid_data['MEAN_POLLUANT'].mean()
                avg_temp = valid_data['W_TEMP'].replace(0, np.nan).mean()
                avg_wind = valid_data['W_WIND'].replace(0, np.nan).mean()
            chart_air_src = df_air_filtered[df_air_filtered['NOM_POLLUANT'] == selected_polluant].copy()
            chart_weather_src = df_weather_filtered.copy()
        else:
            current_geo_data = gdf_display[gdf_display['GEOCODE'] == st.session_state.selected_geocode].iloc[0]
            current_title = current_geo_data['GEONAME']
            current_caption = f"Borough: {current_geo_data['BOROUGH']}"
            avg_polluant = current_geo_data['MEAN_POLLUANT']
            avg_temp = current_geo_data['W_TEMP']
            avg_wind = current_geo_data['W_WIND']
            
            chart_air_src = df_air_filtered[
                (df_air_filtered['GEOJOIN_ID'] == st.session_state.selected_geocode) & 
                (df_air_filtered['NOM_POLLUANT'] == selected_polluant)
            ].copy()
            
            lat_q, lon_q = current_geo_data['LATITUDE_ZONE'], current_geo_data['LONGITUDE_ZONE']
            dists = haversine_vectorized(lon_q, lat_q, df_stations['LONGITUDE'].values, df_stations['LATITUDE'].values)
            nearby_ids = df_stations[dists <= radius]['ID_STATION'].unique()
            chart_weather_src = df_weather_filtered[df_weather_filtered['ID_STATION'].isin(nearby_ids)].copy()

        # Resampling
        delta_days = (end_date - start_date).days
        resample_rule = 'D'
        if delta_days > 730: resample_rule = 'Q'
        elif delta_days > 180: resample_rule = 'M'
        elif delta_days > 60: resample_rule = 'W'

        if not chart_air_src.empty:
            chart_air_final = chart_air_src.set_index('DATE_OBSERVATION').resample(resample_rule)['VALEUR'].mean().reset_index()
        else:
            chart_air_final = pd.DataFrame()

        if not chart_weather_src.empty:
            chart_weather_final = chart_weather_src.set_index('DATE').resample(resample_rule)[['TEMP', 'WDSP', 'DEWP']].mean().reset_index()
        else:
            chart_weather_final = pd.DataFrame()

        # UI Principale
        col_map, col_details = st.columns([3, 2])

        with col_map:
            st.subheader(f"Carte : {selected_polluant}")
            m = folium.Map(location=[40.7128, -74.0060], zoom_start=10, tiles="CartoDB positron")

            choropleth = folium.Choropleth(
                geo_data=gdf_display,
                data=gdf_display,
                columns=['GEOCODE', 'MEAN_POLLUANT'],
                key_on='feature.properties.GEOCODE',
                fill_color='YlOrRd',
                fill_opacity=0.7,
                line_opacity=0.2,
                legend_name=f"Concentration {selected_polluant}",
                highlight=True
            )
            choropleth.add_to(m)

            folium.GeoJson(
                gdf_display,
                style_function=lambda x: {'fillColor': '#ffffff', 'color':'#000000', 'fillOpacity': 0.0, 'weight': 0.1},
                tooltip=folium.GeoJsonTooltip(
                    fields=['GEONAME', 'BOROUGH', 'MEAN_POLLUANT', 'W_TEMP'],
                    aliases=['Quartier:', 'Borough:', f'{selected_polluant}:', 'Temp (°C):'],
                    localize=True
                )
            ).add_to(m)

            st_map = st_folium(m, width=None, height=650)
            
            if st_map and st_map.get('last_object_clicked'):
                last_clicked = st_map['last_object_clicked']
                if isinstance(last_clicked, dict) and 'properties' in last_clicked:
                    props = last_clicked['properties']
                    if 'GEOCODE' in props:
                        clicked_code = str(props['GEOCODE'])
                        name_match = geo[['GEOCODE', 'GEONAME']].drop_duplicates()
                        name_match = name_match[name_match['GEOCODE'] == clicked_code]
                        if not name_match.empty:
                            clicked_name = name_match.iloc[0]['GEONAME']
                            if st.session_state.dropdown_selector != clicked_name:
                                st.session_state.dropdown_selector = clicked_name
                                st.session_state.selected_geocode = clicked_code
                                st.rerun()

        with col_details:
            st.markdown("### 📍 Détails")
            all_options = ["Tous quartiers"] + sorted(geo['GEONAME'].unique().tolist())
            selected_option = st.selectbox("Sélectionner une zone", options=all_options, key="dropdown_selector")
            
            if selected_option == "Tous quartiers":
                st.session_state.selected_geocode = None
            else:
                code_match = geo[geo['GEONAME'] == selected_option]['GEOCODE']
                if not code_match.empty:
                    st.session_state.selected_geocode = str(code_match.values[0])

            st.title(current_title)
            st.caption(current_caption)

            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric(f"Moy. {selected_polluant}", f"{avg_polluant:.2f}" if pd.notnull(avg_polluant) else "N/A")
            kpi2.metric("Temp. Moy", f"{avg_temp:.1f} °C" if pd.notnull(avg_temp) else "N/A")
            kpi3.metric("Vent Moy", f"{avg_wind:.1f} km/h" if pd.notnull(avg_wind) else "N/A")

            st.markdown("---")
            st.subheader("📈 Tendance")
            
            fig_main = go.Figure()
            if not chart_air_final.empty:
                fig_main.add_trace(go.Scatter(
                    x=chart_air_final['DATE_OBSERVATION'], 
                    y=chart_air_final['VALEUR'], 
                    name=selected_polluant, 
                    mode='lines+markers',
                    line=dict(color='red', width=3)
                ))
                fig_main.update_layout(xaxis_title="Date", yaxis_title="Concentration", height=300, margin=dict(t=10,b=0,l=0,r=0))
                st.plotly_chart(fig_main, use_container_width=True)

        st.markdown("---")
        st.subheader("☁️ Analyse Croisée Météo")
        col_graphs, col_box = st.columns([2, 1])

        meteo_config = {
            'Température': {'col': 'TEMP', 'color': 'orange', 'label': 'Temp (°C)'},
            'Vitesse Vent': {'col': 'WDSP', 'color': 'blue', 'label': 'Vent (km/h)'},
            'Point de Rosée': {'col': 'DEWP', 'color': 'green', 'label': 'Rosée (°C)'}
        }

        with col_graphs:
            for var_name in selected_meteo_vars:
                fig = go.Figure()
                if not chart_air_final.empty:
                    fig.add_trace(go.Scatter(
                        x=chart_air_final['DATE_OBSERVATION'], 
                        y=chart_air_final['VALEUR'], 
                        name=selected_polluant, 
                        line=dict(color='red', width=1)
                    ))
                if not chart_weather_final.empty and var_name in meteo_config:
                    conf = meteo_config[var_name]
                    fig.add_trace(go.Scatter(
                        x=chart_weather_final['DATE'], 
                        y=chart_weather_final[conf['col']], 
                        name=conf['label'], 
                        line=dict(color=conf['color'], width=2), 
                        yaxis='y2'
                    ))
                fig.update_layout(
                    title=f"{selected_polluant} vs {var_name}",
                    yaxis=dict(title=selected_polluant),
                    yaxis2=dict(title=var_name, overlaying='y', side='right'),
                    height=300, margin=dict(t=30,b=0,l=0,r=0)
                )
                st.plotly_chart(fig, use_container_width=True)

        with col_box:
            if selected_meteo_vars and not chart_weather_src.empty:
                for var_name in selected_meteo_vars:
                    conf = meteo_config[var_name]
                    fig_box = go.Figure(go.Box(y=chart_weather_src[conf['col']], name=conf['label'], marker_color=conf['color']))
                    fig_box.update_layout(title=f"Dist. {var_name}", height=300, margin=dict(t=30,b=20,l=0,r=0))
                    st.plotly_chart(fig_box, use_container_width=True)

# ==============================================================================
# APP 2 : RTE (DATALAKE INCREMENTAL)
# ==============================================================================
elif app_mode == "RTE Production":
    st.title("⚡ Météo de l'Électricité (Style éCO2mix)")

    # --- CONTROLES SIDEBAR ---
    st.sidebar.markdown("---")
    st.sidebar.header("Mise à jour des données")
    if st.sidebar.button("🔄 Actualiser depuis RTE"):
        status = st.sidebar.empty()
        status.info("⏳ Connexion API RTE...")
        
        # 1. Pipeline Pandas (ETL Local)
        df_new, msg = rte_layer.get_latest_data()
        
        if df_new.empty:
            status.error(f"❌ Erreur : {msg}")
        else:
            # Mise à jour immédiate du cache session
            st.session_state['rte_data'] = df_new
            status.info(f"💾 Sauvegarde HDFS ({len(df_new)} lignes)...")
            
            try:
                # 2. Pipeline Spark (Ingestion HDFS)
                spark = get_spark_session()
                # Nettoyage index pour Spark
                df_spark_ready = df_new.copy()
                if isinstance(df_spark_ready.index, pd.DatetimeIndex):
                    df_spark_ready = df_spark_ready.reset_index()
                
                # Écriture
                spark_df = spark.createDataFrame(df_spark_ready)
                hdfs_path = "/user/mathis/datalake/raw/rte/rte_datalake.parquet"
                spark_df.write.mode("overwrite").parquet(hdfs_path)
                
                status.success("✅ Données synchronisées !")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                status.error(f"⚠️ Erreur HDFS (mais affichage OK) : {e}")

    # --- CHARGEMENT DES DONNEES ---
    if 'rte_data' not in st.session_state:
        # Essai de lecture HDFS au démarrage, sinon vide
        try:
            spark = get_spark_session()
            path = "/user/mathis/datalake/raw/rte/rte_datalake.parquet"
            df_spark = spark.read.parquet(path).toPandas()
            if not df_spark.empty and 'Datetime' in df_spark.columns:
                df_spark['Datetime'] = pd.to_datetime(df_spark['Datetime'])
                df_spark = df_spark.set_index('Datetime').sort_index()
            st.session_state['rte_data'] = df_spark
        except:
            st.session_state['rte_data'] = pd.DataFrame()

    data = st.session_state['rte_data']

    # --- AFFICHAGE PRINCIPAL ---
    if not data.empty:
        # Nettoyage des futurs (Consommation = 0 ou ND)
        if 'Consommation' in data.columns:
            valid_idx = data[data['Consommation'] > 1].index
            if not valid_idx.empty:
                data = data.loc[:valid_idx.max()]
        
        # Sélecteur de date intelligent
        min_ts, max_ts = data.index.min(), data.index.max()
        col_date, col_kpi = st.columns([1, 3])
        
        with col_date:
            date_selected = st.date_input("Date", value=max_ts.date(), min_value=min_ts.date(), max_value=max_ts.date())
            
        # Filtrage sur la journée sélectionnée
        mask = (data.index.date == date_selected)
        df_day = data[mask]
        
        if df_day.empty:
            st.warning("Pas de données pour cette date.")
        else:
            last_row = df_day.iloc[-1]
            last_time = last_row.name.strftime('%H:%M')
            
            # --- BLOC KPI (EN HAUT) ---
            prod_cols = [c for c in STACK_ORDER if c in data.columns]
            current_prod = last_row[prod_cols].sum()
            current_conso = last_row.get('Consommation', 0)
            
            # Calcul du Solde Exportateur (Prod - Conso - Pompage)
            # Note: RTE calcule Solde = Exports - Imports. Ici on l'estime par Prod - Conso.
            # Pour être précis, utilisons les colonnes "Ech. comm." si dispo
            exch_cols = [c for c in last_row.index if "Ech." in c and ("comm." in c or "Pays" in c) and "physique" not in c.lower()]
            current_balance = last_row[exch_cols].sum() if exch_cols else (current_prod - current_conso)
            
            # Couleur dynamique du solde
            balance_color = "normal" 
            label_balance = "Solde (Neutre)"
            if current_balance > 0: 
                balance_color = "inverse" # Vert (souvent import positif dans les raw data, à vérifier selon convention)
                # Convention RTE Raw : Positif = Import, Négatif = Export
                # Mais pour l'affichage "Exportateur", on préfère souvent dire :
                # Si (Prod > Conso) => Exportateur.
            
            with col_kpi:
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Production", f"{current_prod/1000:.1f} GW")
                k2.metric("Consommation", f"{current_conso/1000:.1f} GW")
                k3.metric("Nucléaire", f"{last_row.get('Nucléaire', 0)/1000:.1f} GW", 
                          f"{last_row.get('Nucléaire', 0)/current_prod*100:.0f}% du mix")
                
                # --- REMPLACEMENT ICI : CO2 -> MIX ÉNERGÉTIQUE ---
                with k4:
                    # Titre style "Metric"
                    st.markdown("<p style='font-size: 14px; margin-bottom: 5px;'>Mix Énergétique</p>", unsafe_allow_html=True)
                    
                    # Création du Donut (Version Compacte)
                    pie_data = last_row[prod_cols]
                    pie_data = pie_data[pie_data > 0] # On garde que ce qui produit
                    
                    fig_kpi_pie = go.Figure(go.Pie(
                        labels=pie_data.index, 
                        values=pie_data.values, 
                        hole=.6, # Trou plus grand pour aspect "anneau fin"
                        marker=dict(colors=[RTE_COLORS.get(x, '#333') for x in pie_data.index]),
                        textinfo='none', # Pas de texte pour rester propre en petit
                        hoverinfo='label+percent+value'
                    ))
                    
                    fig_kpi_pie.update_layout(
                        height=80, # Très petite hauteur pour s'aligner avec les chiffres
                        margin=dict(t=0, b=0, l=0, r=0),
                        showlegend=False,
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig_kpi_pie, use_container_width=True)

            # --- GRAPHIQUE 1 : PRODUCTION PAR FILIERE (AIRE) ---
            st.subheader(f"Production d'électricité par filière ({date_selected.strftime('%d/%m/%Y')})")
            
            # Préparation des données pour Plotly (Stack Order respecté)
            cols_to_plot = [c for c in STACK_ORDER if c in df_day.columns and df_day[c].sum() > 0]
            
            fig = go.Figure()
            
            # Ajout des aires empilées
            for col in cols_to_plot:
                fig.add_trace(go.Scatter(
                    x=df_day.index, y=df_day[col],
                    mode='lines',
                    name=col,
                    stackgroup='one', # Ceci active l'empilement
                    line=dict(width=0.5, color=RTE_COLORS.get(col, '#333')),
                    fillcolor=RTE_COLORS.get(col, '#333')
                ))
                
            # Ajout de la courbe de consommation par dessus
            if 'Consommation' in df_day.columns:
                fig.add_trace(go.Scatter(
                    x=df_day.index, y=df_day['Consommation'],
                    mode='lines',
                    name='Consommation',
                    line=dict(color='black', width=2)
                ))

            fig.update_layout(
                height=400,
                margin=dict(l=0, r=0, t=10, b=0),
                legend=dict(orientation="h", y=1.1, x=0.5, xanchor='center'),
                yaxis=dict(title="Puissance (MW)"),
                hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True)

            # --- SECTION 2 : CARTE ET JAUGE (COTE A COTE) ---
            st.markdown("---")
            c_map, c_gauge = st.columns([2, 1])

            # --- SECTION 2 : CARTE ET JAUGE (COTE A COTE) ---
            st.markdown("---")
            
            # MODIFICATION ICI : Ratio [1, 1] pour donner plus de place aux jauges
            c_map, c_gauge = st.columns([1, 1])

            with c_map:
                st.subheader("🌍 Échanges aux frontières")
                
                # Carte focalisée "Carré France"
                # Zoom 6 + Centrage ajusté pour voir les voisins (UK, ES, IT, DE, CH)
                m = folium.Map(location=[46.5, 2.5], zoom_start=5.25, tiles="CartoDB positron")
                
                # Marqueur France
                folium.Marker(COUNTRY_COORDS['France'], popup="France", 
                             icon=folium.Icon(color='blue', icon='home', prefix='fa')).add_to(m)

                found_exchange = False
                if exch_cols:
                    for c in exch_cols:
                        val = last_row[c]
                        country = c.replace("Ech. comm. ", "").replace("Ech. comm.", "").strip()
                        
                        if country in COUNTRY_COORDS:
                            found_exchange = True
                            coord = COUNTRY_COORDS[country]
                            coord_fr = COUNTRY_COORDS['France']
                            
                            # Logique Visuelle (Rouge=Export, Vert=Import)
                            if val > 0: # IMPORT (Vers la France)
                                color = 'green'
                                icon_name = 'arrow-down'
                                tooltip = f"IMPORT depuis {country}: {val:,.0f} MW"
                                folium.PolyLine([coord, coord_fr], color=color, weight=4, opacity=0.8, dash_array='10').add_to(m)
                            else: # EXPORT (Depuis la France)
                                color = 'red'
                                icon_name = 'arrow-up'
                                tooltip = f"EXPORT vers {country}: {abs(val):,.0f} MW"
                                folium.PolyLine([coord_fr, coord], color=color, weight=4, opacity=0.8).add_to(m)
                            
                            # Marqueur Voisin
                            folium.Marker(
                                location=coord,
                                icon=folium.Icon(color=color, icon=icon_name, prefix='fa'),
                                tooltip=tooltip
                            ).add_to(m)
                
                # Hauteur ajustée pour un rendu "Carré" (approx 500px sur écran standard)
                st_folium(m, width=None, height=500)
                
                if not found_exchange:
                    st.info("⚠️ Pas de données d'échanges frontaliers disponibles.")

            with c_gauge:
                st.subheader("⚖️ Solde Import/Export")
                
                # =========================================================
                # 1. JAUGE PRINCIPALE (GLOBALE) - INCHANGÉE
                # =========================================================
                
                net_balance = last_row[exch_cols].sum() if exch_cols else 0
                limit = 15000
                
                # Couleurs
                color_export = "#D32F2F" # Rouge
                color_import = "#388E3C" # Vert
                
                # Logique Remplissage (Step)
                if net_balance < 0:
                    title_gauge = "Exportateur Net"
                    active_step = {'range': [net_balance, 0], 'color': color_export}
                else:
                    title_gauge = "Importateur Net"
                    active_step = {'range': [0, net_balance], 'color': color_import}
                
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number+delta",
                    value = net_balance,
                    domain = {'x': [0, 1], 'y': [0, 1]},
                    title = {'text': f"{title_gauge}<br><span style='font-size:0.8em;color:gray'>Flux (MW)</span>"},
                    delta = {'reference': 0, 'increasing': {'color': color_import}, 'decreasing': {'color': color_export}},
                    gauge = {
                        'axis': {'range': [-limit, limit], 'tickwidth': 1, 'tickcolor': "darkblue"},
                        'bar': {'color': "rgba(0,0,0,0)"}, # Invisible
                        'bgcolor': "white",
                        'borderwidth': 2,
                        'bordercolor': "gray",
                        'steps': [
                            {'range': [-limit, 0], 'color': "rgba(211, 47, 47, 0.15)"},
                            {'range': [0, limit], 'color': "rgba(56, 142, 60, 0.15)"},
                            active_step # La zone colorée
                        ],
                        'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': 0}
                    }
                ))
                fig_gauge.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=0))
                st.plotly_chart(fig_gauge, use_container_width=True)
                
                # =========================================================
                # 2. LES 5 PETITS DEMI-CERCLES (FRONTIÈRES)
                # =========================================================
                st.markdown("---")
                
                # Définition des 5 pays avec leurs limites de capacité (pour que la jauge soit jolie)
                neighbors = [
                    {'code': 'UK', 'col': 'Ech. comm. Angleterre', 'lim': 3000},
                    {'code': 'ES', 'col': 'Ech. comm. Espagne', 'lim': 4000},
                    {'code': 'IT', 'col': 'Ech. comm. Italie', 'lim': 4000},
                    {'code': 'CH', 'col': 'Ech. comm. Suisse', 'lim': 4000},
                    {'code': 'DE/BE', 'col': 'Ech. comm. Allemagne-Belgique', 'lim': 8000}
                ]
                
                # Création des 5 colonnes alignées
                cols_mini = st.columns(5)
                
                for i, n in enumerate(neighbors):
                    with cols_mini[i]:
                        # Récupération valeur
                        val = last_row.get(n['col'], 0)
                        lim = n['lim']
                        
                        # Définition de la "marche" colorée (Step) qui part de 0
                        if val < 0:
                            # Export (Gauche / Rouge)
                            mini_step = {'range': [val, 0], 'color': color_export}
                        else:
                            # Import (Droite / Vert)
                            mini_step = {'range': [0, val], 'color': color_import}
                            
                        # Création de la Jauge minimaliste
                        fig_mini = go.Figure(go.Indicator(
                            mode = "gauge", # Pas de chiffre, pas de delta
                            value = val,
                            domain = {'x': [0, 1], 'y': [0, 1]},
                            title = {'text': n['code'], 'font': {'size': 14, 'weight': 'bold', 'color': '#555'}},
                            gauge = {
                                # On cache l'axe (chiffres) mais on garde la forme
                                'axis': {'range': [-lim, lim], 'visible': False}, 
                                'bar': {'color': "rgba(0,0,0,0)"}, # Barre invisible
                                'bgcolor': "white",
                                'borderwidth': 0,
                                'steps': [
                                    # Fonds pâles pour dessiner le demi-cercle vide
                                    {'range': [-lim, 0], 'color': "rgba(211, 47, 47, 0.1)"},
                                    {'range': [0, lim], 'color': "rgba(56, 142, 60, 0.1)"},
                                    # La couleur active
                                    mini_step
                                ],
                                # Petit trait noir au milieu (0)
                                'threshold': {'line': {'color': "black", 'width': 2}, 'thickness': 1, 'value': 0}
                            }
                        ))
                        
                        fig_mini.update_layout(
                            height=80, # Très compact
                            margin=dict(l=2, r=2, t=30, b=0), # Marges minimales
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)'
                        )
                        st.plotly_chart(fig_mini, use_container_width=True)

    else:
        st.info("👋 Bienvenue ! Cliquez sur le bouton 'Actualiser depuis RTE' dans la barre latérale pour charger les données.")