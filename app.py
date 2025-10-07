import streamlit as st
import pandas as pd
import folium
from folium import CircleMarker
from streamlit_folium import st_folium
from geopy.distance import geodesic

# -----------------------------------------
# PAGE CONFIGURATION
# -----------------------------------------
st.set_page_config(page_title="Mahindra NRC RO Coverage Visualizer", layout="wide")
st.title("Mahindra Suggested Workshop Planner Based on NRC RO")
st.markdown("""
This interactive tool shows how many **NRC VINs** fall within a selected distance (in km) 
from each Mahindra workshop location.  
Use this to identify **coverage zones** and **potential workshop expansion areas**.
""")

# -----------------------------------------
# LOAD DATA
# -----------------------------------------
@st.cache_data
def load_data():
    workshops = pd.read_excel("KMA_Mahindra_Workshops_Lat_Long (1).xlsx")
    nrc = pd.read_excel("KMA_NRC_F30_Retail_RO_Projections_PV_Lat_Long_Pincode (1).xlsx")

    # Standardize column names
    workshops.columns = workshops.columns.str.strip().str.lower()
    nrc.columns = nrc.columns.str.strip().str.lower()

    return workshops, nrc


workshops, nrc = load_data()

# -----------------------------------------
# VERIFY COLUMNS
# -----------------------------------------
expected_wk_headers = {"workshop name", "pincode", "lat", "lon"}
expected_nrc_headers = {"customer pin code", "latitude", "longitude", "nrc vin count", "nrc_projected_ro_yearly"}

if not expected_wk_headers.issubset(set(workshops.columns)):
    st.error(f"⚠ Workshop file missing columns: {expected_wk_headers - set(workshops.columns)}")

if not expected_nrc_headers.issubset(set(nrc.columns)):
    st.error(f"⚠ NRC file missing columns: {expected_nrc_headers - set(nrc.columns)}")

# -----------------------------------------
# USER INPUT
# -----------------------------------------
radius_km = st.slider("Select radius (km)", min_value=1, max_value=20, value=5)

# -----------------------------------------
# CALCULATE NRC COVERAGE
# -----------------------------------------
results = []

for _, wk in workshops.iterrows():
    wk_lat, wk_lon = wk["lat"], wk["lon"]
    wk_name = wk["workshop name"]
    wk_pin = wk["pincode"]

    # Compute distance for each NRC point
    nrc["distance_km"] = nrc.apply(
        lambda r: geodesic((wk_lat, wk_lon), (r["latitude"], r["longitude"])).km, axis=1
    )

    # Filter NRCs within radius
    nearby_nrc = nrc[nrc["distance_km"] <= radius_km]
    total_vins = nearby_nrc["nrc vin count"].sum()

    results.append({
        "Workshop Name": wk_name,
        "Workshop Pincode": wk_pin,
        "Latitude": wk_lat,
        "Longitude": wk_lon,
        "Radius (km)": radius_km,
        "NRC VINs within Radius": total_vins
    })

results_df = pd.DataFrame(results)

# -----------------------------------------
# MAP VISUALIZATION
# -----------------------------------------
st.subheader("🗺️ Workshop NRC VIN Coverage Map")

center_lat = workshops["lat"].mean()
center_lon = workshops["lon"].mean()

m = folium.Map(location=[center_lat, center_lon], zoom_start=7)

# Add NRC points (gray)
for _, r in nrc.iterrows():
    CircleMarker(
        location=[r["latitude"], r["longitude"]],
        radius=2,
        color="gray",
        fill=True,
        fill_opacity=0.3,
        popup=f"Pincode: {r.get('customer pin code', '')}<br>NRC VINs: {int(r.get('nrc vin count', 0))}"
    ).add_to(m)

# Add workshops (blue bubbles proportional to VINs)
for _, r in results_df.iterrows():
    count = int(r["NRC VINs within Radius"])
    size = max(5, min(count / 200, 25))  # Bubble scaling logic
    CircleMarker(
        location=[r["Latitude"], r["Longitude"]],
        radius=size,
        color="blue",
        fill=True,
        fill_opacity=0.6,
        popup=f"<b>{r['Workshop Name']}</b><br>"
              f"Pincode: {r['Workshop Pincode']}<br>"
              f"VINs within {radius_km} km: {count}"
    ).add_to(m)

st_folium(m, width=1100, height=650)

# -----------------------------------------
# SUMMARY TABLE
# -----------------------------------------
st.subheader("📊 Workshop-wise NRC VIN Coverage Summary")
st.dataframe(results_df, use_container_width=True)

# Download option
csv = results_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "Download Coverage Report (CSV)",
    csv,
    "Workshop_NRC_Coverage.csv",
    "text/csv",
    key="download-csv"
)
