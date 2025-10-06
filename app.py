
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import math
from io import BytesIO

st.set_page_config(page_title='Mahindra Workshop NRC VIN Belt Analysis', layout='wide')
st.title('Mahindra Workshop NRC VIN Belt Analysis')

st.markdown('''Upload or use packaged data. For each existing workshop, this tool computes the total **NRC VIN Count**
within a radius X km and visualizes it as a bubble centered at the workshop. Use the slider to set X (0–20 km).''')

# --- Load packaged files if present, otherwise allow upload
use_packaged = True
try:
    df_ws = pd.read_excel("KMA_Mahindra_Workshops_Lat_Long.xlsx")
    df_proj = pd.read_excel("KMA_NRC_F30_Retail_RO_Projections_PV_Lat_Long_Pincode.xlsx")
    st.sidebar.success('Loaded packaged data files.')
except Exception:
    use_packaged = False

if not use_packaged:
    st.sidebar.info('Upload Excel files')
    uploaded_ws = st.sidebar.file_uploader('Workshops Excel', type=['xlsx','xls'])
    uploaded_proj = st.sidebar.file_uploader('NRC projections Excel', type=['xlsx','xls'])
    if uploaded_ws and uploaded_proj:
        df_ws = pd.read_excel(uploaded_ws)
        df_proj = pd.read_excel(uploaded_proj)
    else:
        st.info('Please upload both Excel files (or include them in the repo).')
        st.stop()

# Normalize names
df_ws.columns = [c.strip() if isinstance(c, str) else c for c in df_ws.columns]
df_proj.columns = [c.strip() if isinstance(c, str) else c for c in df_proj.columns]

def find_col(df, candidates):
    cols = {col.lower(): col for col in df.columns if isinstance(col, str)}
    for cand in candidates:
        if cand in df.columns:
            return cand
    for cand in candidates:
        if cand.lower() in cols:
            return cols[cand.lower()]
    for col in df.columns:
        for cand in candidates:
            if isinstance(col, str) and cand.lower() in col.lower():
                return col
    return None

ws_name_col = find_col(df_ws, ['Mabindra Workshop Location', 'Mahindra Workshop Location', 'Workshop', 'workshop'])
ws_lat_col = find_col(df_ws, ['Latitude', 'Lat'])
ws_lon_col = find_col(df_ws, ['Longitude', 'Lon', 'Lng'])
ws_pin_col = find_col(df_ws, ['Pincode', 'Pin Code', 'pincode'])

proj_pin_col = find_col(df_proj, ['Customer Pin Code', 'Pincode', 'Pin Code', 'pincode'])
proj_lat_col = find_col(df_proj, ['Latitude', 'Lat'])
proj_lon_col = find_col(df_proj, ['Longitude', 'Lon', 'Lng'])
nrc_vin_col = find_col(df_proj, ['NRC VIN Count', 'NRC_VIN_Count', 'NRC VIN', 'NRC_Vin', 'NRC_Projected_RO_Yearly', 'NRC_Projected_RO', 'NRC VIN'])

missing = []
for label, col in [('workshop name', ws_name_col), ('workshop lat', ws_lat_col), ('workshop lon', ws_lon_col),
                   ('proj lat', proj_lat_col), ('proj lon', proj_lon_col), ('nrc vin count', nrc_vin_col)]:
    if col is None:
        missing.append(label)

if missing:
    st.error('Could not detect required columns: ' + ', '.join(missing))
    st.write('Workshops columns:', list(df_ws.columns))
    st.write('Projections columns:', list(df_proj.columns))
    st.stop()

# rename for internal use
df_ws = df_ws.rename(columns={ws_name_col: 'workshop_name', ws_lat_col: 'lat', ws_lon_col: 'lon', ws_pin_col: 'pincode'})
df_proj = df_proj.rename(columns={proj_pin_col: 'pincode', proj_lat_col: 'lat', proj_lon_col: 'lon', nrc_vin_col: 'nrc_vin_count'})

# ensure numeric
df_ws['lat'] = pd.to_numeric(df_ws['lat'], errors='coerce')
df_ws['lon'] = pd.to_numeric(df_ws['lon'], errors='coerce')
df_proj['lat'] = pd.to_numeric(df_proj['lat'], errors='coerce')
df_proj['lon'] = pd.to_numeric(df_proj['lon'], errors='coerce')
df_proj['nrc_vin_count'] = pd.to_numeric(df_proj['nrc_vin_count'], errors='coerce').fillna(0)

df_ws = df_ws.dropna(subset=['lat','lon']).reset_index(drop=True)
df_proj = df_proj.dropna(subset=['lat','lon']).reset_index(drop=True)

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2.0)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2.0)**2
    c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

st.sidebar.header('Parameters')
radius_km = st.sidebar.slider('Radius around each workshop (km)', 0, 20, 5, 1)

# Compute VINs within radius per workshop
summary = []
for _, ws in df_ws.iterrows():
    ws_lat, ws_lon = ws['lat'], ws['lon']
    df_proj['dist_km_to_ws'] = df_proj.apply(lambda r: haversine_km(ws_lat, ws_lon, r['lat'], r['lon']), axis=1)
    total_vins = int(df_proj.loc[df_proj['dist_km_to_ws'] <= radius_km, 'nrc_vin_count'].sum())
    summary.append({{
        'workshop_name': ws.get('workshop_name', ''),
        'workshop_pincode': ws.get('pincode', ''),
        'workshop_lat': ws_lat,
        'workshop_lon': ws_lon,
        'nrc_vin_count_within_radius': total_vins
    }})

summary_df = pd.DataFrame(summary).sort_values('nrc_vin_count_within_radius', ascending=False).reset_index(drop=True)

st.subheader('🔎 Workshop NRC VIN Summary')
st.write(f'Radius = {{radius_km}} km')
st.dataframe(summary_df)

st.subheader('🗺️ Workshop Belt Map')
map_center = [df_ws['lat'].mean(), df_ws['lon'].mean()]
m = folium.Map(location=map_center, zoom_start=9)

if st.sidebar.checkbox('Show projection points (pincodes)', value=False):
    for _, r in df_proj.iterrows():
        folium.CircleMarker(
    location=[r['lat'], r['lon']],
    radius=3,
    fill=True,
    fill_opacity=0.6,
    popup=f"Pincode: {r.get('pincode','')}<br>NRC VINs: {int(r.get('nrc_vin_count',0))}"
).add_to(m)


max_vins = summary_df['nrc_vin_count_within_radius'].max() if not summary_df.empty else 0
for _, r in summary_df.iterrows():
    count = r['nrc_vin_count_within_radius']
    radius_m = 200 + (0 if max_vins==0 else int(8000 * (count / max_vins)**0.5))
    folium.Circle(location=[r['workshop_lat'], r['workshop_lon']], radius=radius_m,
                  color='crimson', fill=True, fill_opacity=0.4,
                  popup=f\"Workshop: {{r['workshop_name']}}<br>VINs within {{radius_km}} km: {{count}}\").add_to(m)
    folium.Marker(location=[r['workshop_lat'], r['workshop_lon']],
                  popup=f\"Workshop: {{r['workshop_name']}}<br>VINs within {{radius_km}} km: {{count}}\",\n                  icon=folium.Icon(color='red', icon='wrench', prefix='fa')).add_to(m)

st_folium(m, width=1000, height=650)

csv = summary_df.to_csv(index=False).encode('utf-8')
st.download_button('Download workshop_nrc_vin_summary.csv', csv, 'workshop_nrc_vin_summary.csv', 'text/csv')
