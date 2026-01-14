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

# Palette de couleurs "RTE Style"
RTE_COLORS = {
    'Nucléaire': '#FFD700',      # Or/Jaune
    'Hydraulique': '#1E90FF',    # Bleu
    'Eolien': '#32CD32',         # Vert lime
    'Solaire': '#FF8C00',        # Orange foncé
    'Gaz': '#FF6347',            # Rouge tomate
    'Bioénergies': '#8B4513',    # Marron
    'Charbon': '#2F4F4F',        # Gris ardoise foncé
    'Fioul': '#8B0000',          # Rouge foncé
    'Pompage': '#4169E1',        # Bleu royal
    'Consommation': '#000000'    # Noir
}

# Coordonnées pour la carte des échanges
COUNTRY_COORDS = {
    'France': [46.603354, 1.888334],
    'Angleterre': [51.5074, -0.1278],
    'Espagne': [40.4168, -3.7038],
    'Italie': [41.9028, 12.4964],
    'Suisse': [46.8182, 8.2275],
    'Allemagne-Belgique': [50.8503, 4.3517]
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
    st.title("⚡ Mix Électrique France")

    if st.sidebar.button("🔄 Forcer Mise à jour (RTE)"):
        status_text = st.sidebar.empty()
        status_text.info("⏳ Téléchargement RTE en cours...")
        
        # 1. Récupération des données (RAM) via module local
        df_new, msg = rte_layer.get_latest_data()
        
        if df_new.empty:
            status_text.error(f"❌ Erreur DL : {msg}")
        else:
            # --- CORRECTION ICI ---
            # On met à jour le cache de l'app pour que le graphique change TOUT DE SUITE
            st.session_state['rte_data'] = df_new
            
            status_text.info(f"💾 Sauvegarde HDFS ({len(df_new)} lignes)...")
            try:
                # 2. Écriture HDFS via Spark
                spark = get_spark_session()
                
                # On prépare une copie pour Spark (qui n'aime pas les index Datetime)
                # On ne touche pas à df_new qui sert à l'affichage
                df_spark_ready = df_new.copy()
                if isinstance(df_spark_ready.index, pd.DatetimeIndex):
                    df_spark_ready = df_spark_ready.reset_index()
                    
                spark_df = spark.createDataFrame(df_spark_ready)
                
                hdfs_rte_path = "/user/mathis/datalake/raw/rte/rte_datalake.parquet"
                spark_df.write.mode("overwrite").parquet(hdfs_rte_path)
                
                status_text.success("✅ Succès ! Données à jour.")
                time.sleep(1)
                st.rerun()
                
            except Exception as e:
                status_text.error(f"❌ Erreur Écriture HDFS : {e}")

    # CHARGEMENT LECTURE
    if 'rte_data' not in st.session_state:
        # On peut aussi lire HDFS ici si souhaité, 
        # mais on garde votre logique 'rte_layer.get_data()' si elle lit en local ou HDFS.
        # Pour être cohérent Big Data, on pourrait lire HDFS ici aussi :
        try:
            spark = get_spark_session()
            path = "/user/mathis/datalake/raw/rte/rte_datalake.parquet"
            # Lecture Lazy Spark -> Pandas
            df_rte_spark = spark.read.parquet(path).toPandas()
            if 'Datetime' in df_rte_spark.columns:
                df_rte_spark['Datetime'] = pd.to_datetime(df_rte_spark['Datetime'])
                df_rte_spark = df_rte_spark.set_index('Datetime').sort_index()
            st.session_state['rte_data'] = df_rte_spark
        except:
            # Fallback si HDFS vide
            st.session_state['rte_data'] = pd.DataFrame()

    data = st.session_state.get('rte_data', pd.DataFrame())

    if not data.empty:
        # Auto-Truncate
        if 'Consommation' in data.columns:
            valid_idx = data[data['Consommation'] > 1].index
            if not valid_idx.empty:
                data = data.loc[:valid_idx.max()]

        st.sidebar.markdown("---")
        st.sidebar.header("📅 Filtrage Temporel")
        
        min_ts, max_ts = data.index.min(), data.index.max()
        default_start = max_ts.date() - pd.Timedelta(days=7)
        if default_start < min_ts.date(): default_start = min_ts.date()

        date_range = st.sidebar.date_input("Période", value=(default_start, max_ts.date()), min_value=min_ts.date(), max_value=max_ts.date())
        
        data_filtered = data.copy()
        if len(date_range) == 2:
            start_d, end_d = date_range
            mask = (data_filtered.index.date >= start_d) & (data_filtered.index.date <= end_d)
            data_filtered = data_filtered[mask]
        
        if data_filtered.empty:
            st.warning("Aucune donnée sur la période.")
        else:
            last_row = data_filtered.iloc[-1]
            prod_cols = [c for c in data.columns if c in RTE_COLORS and c != 'Consommation']
            total_prod = last_row[prod_cols].sum()
            
            st.markdown(f"### Situation au {last_row.name.strftime('%d/%m/%Y %H:%M')}")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Production", f"{total_prod:,.0f} MW")
            c2.metric("Consommation", f"{last_row.get('Consommation',0):,.0f} MW")
            c3.metric("Solde", f"{(total_prod - last_row.get('Consommation',0)):+,.0f} MW")
            c4.metric("Nucléaire", f"{last_row.get('Nucléaire',0):,.0f} MW")

            st.subheader("Évolution Mix")
            fig = px.area(data_filtered, x=data_filtered.index, y=prod_cols, color_discrete_map=RTE_COLORS)
            if 'Consommation' in data_filtered.columns:
                fig.add_trace(go.Scatter(x=data_filtered.index, y=data_filtered['Consommation'], mode='lines', name='Consommation', line=dict(color='black')))
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            col_pie, col_table = st.columns([1, 2])
            
            with col_pie:
                pie_data = last_row[prod_cols]
                pie_data = pie_data[pie_data > 0]
                fig_pie = go.Figure(go.Pie(labels=pie_data.index, values=pie_data.values, hole=.4, marker=dict(colors=[RTE_COLORS.get(x) for x in pie_data.index])))
                fig_pie.update_layout(height=300, margin=dict(t=0,b=0,l=0,r=0))
                st.plotly_chart(fig_pie, use_container_width=True)

            with col_table:
                st.dataframe(data_filtered.tail(24).sort_index(ascending=False), use_container_width=True, height=300)

            # CARTE ECHANGES
            st.markdown("---")
            st.subheader("🌍 Carte des Échanges")
            exch_cols = [c for c in last_row.index if "Ech." in c and ("comm." in c or "Pays" in c or len(c) > 5) and "physique" not in c.lower()]
            
            if exch_cols:
                m_exch = folium.Map(location=[46.6, 2.2], zoom_start=5, tiles="CartoDB positron")
                folium.Marker(COUNTRY_COORDS['France'], icon=folium.Icon(color='blue', icon='home')).add_to(m_exch)
                
                found_any = False
                for c in exch_cols:
                    val = last_row[c]
                    country_key = c.replace("Ech. comm. ", "").replace("Ech. comm.", "").strip()
                    if country_key in COUNTRY_COORDS:
                        found_any = True
                        coord_n = COUNTRY_COORDS[country_key]
                        coord_f = COUNTRY_COORDS['France']
                        
                        if val > 0: # Import
                            folium.PolyLine([coord_n, coord_f], color='green', weight=3).add_to(m_exch)
                            folium.Marker(coord_n, icon=folium.Icon(color='green', icon='arrow-down'), tooltip=f"Import: {val:,.0f} MW").add_to(m_exch)
                        elif val < 0: # Export
                            folium.PolyLine([coord_f, coord_n], color='red', weight=3).add_to(m_exch)
                            folium.Marker(coord_n, icon=folium.Icon(color='red', icon='arrow-up'), tooltip=f"Export: {abs(val):,.0f} MW").add_to(m_exch)
                
                if found_any:
                    st_folium(m_exch, width=None, height=500)
    else:
        st.warning("Données indisponibles. Lancez la mise à jour.")