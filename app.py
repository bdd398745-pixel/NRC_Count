import streamlit as st
import pandas as pd
import folium
from folium import CircleMarker
from streamlit_folium import st_folium
from geopy.distance import geodesic

# ----------------------------
# PAGE CONFIG
# ----------------------------
st.set_page_config(page_title="Mahindra NRC RO Coverage Visualizer", layout="wide")
st.title("Mahindra Suggested Workshop Planner Based on NRC RO")
st.markdown(
    "This tool visualizes NRC RO projections around existing Mahindra workshops and shows NRC VIN coverage within a chosen radius."
)

# ----------------------------
# DATA LOAD
# ----------------------------
@st.cache_data
def load_data():
    workshops = pd.read_excel("KMA_Mahindra_Workshops_Lat_Long (1).xlsx")
    nrc = pd.read_excel("KMA_NRC_F30_Retail_RO_Projections_PV_Lat_Long_Pincode (1).xlsx")

    workshops.columns = workshops.columns.str.strip().str.lower()
    nrc.columns = nrc.columns.str.strip().str.lower()

    return workshops, nrc


workshops, nrc = load_data()

# Verify expected headers
expected_wk_headers = {"workshop name", "pincode", "lat", "lon"}
expected_nrc_headers = {"pincode", "lat", "lon", "nrc vin count"}

if not expected_wk_headers.issubset(set(workshops.columns)):
    st.error(f"Workshop file missing columns: {expected_wk_headers - set(workshops.columns)}")

if not expected_nrc_headers.issubset(set(nrc.columns)):
    st.error(f"NRC file missing columns: {expected_nrc_headers - set(nrc.columns)}")

# ----------------------------
# USER INPUTS
# ----------------------------
radius_km = st.slider("Select radius (km)", min_value=1, max_value=20, value=5)

# ----------------------------
# CALCULATE NRC COVERAGE
# ----------------------------
results = []

for _, wk in workshops.iterrows():
    wk_lat, wk_lon = wk["lat"], wk["lon"]
    wk_name = wk["workshop name"]
    wk_pin = wk["pincode"]

    # Compute distance to each NRC pincode
    nrc["distance_km"] = nrc.apply(
        lambda r: geodesic((wk_lat, wk_lon), (r["lat"], r["lon"])).km, axis=1
    )

    nearby_nrc = nrc[nrc["distance_km"] <= radius_km]
    total_vins = nearby_nrc["nrc vin count"].sum()

    results.append({
        "workshop_name": wk_name,
        "pincode": wk_pin,
        "lat": wk_lat,
        "lon": wk_lon,
        "radius_km": radius_km,
        "vin_count_within_radius": total_vins
    })

results_df = pd.DataFrame(results)

# ----------------------------
# MAP VISUALIZATION
# ----------------------------
st.subheader("Workshop NRC VIN Coverage Map")

# Center map at mean coordinates
center_lat = workshops["lat"].mean()
center_lon = workshops["lon"].mean()

m = folium.Map(location=[center_lat, center_lon], zoom_start=7)

# Plot NRC pin points (optional background)
for _, r in nrc.iterrows():
    CircleMarker(
        location=[r["lat"], r["lon"]],
        radius=2,
        color="gray",
        fill=True,
        fill_opacity=0.4,
        popup=f"Pincode: {r.get('pincode','')}<br>NRC VINs: {int(r.get('nrc vin count',0))}"
    ).add_to(m)

# Plot workshops with bubble proportional to VIN count
for _, r in results_df.iterrows():
    count = int(r["vin_count_within_radius"])
    size = max(5, min(count / 200, 25))  # bubble scaling
    CircleMarker(
        location=[r["lat"], r["lon"]],
        radius=size,
        color="blue",
        fill=True,
        fill_opacity=0.6,
        popup=f"Workshop: {r['workshop_name']}<br>VINs within {radius_km} km: {count}"
    ).add_to(m)

# Display map
st_folium(m, width=1100, height=650)

# ----------------------------
# DATA TABLE + EXPORT
# ----------------------------
st.subheader("Summary Table")
st.dataframe(results_df)

csv = results_df.to_csv(index=False).encode("utf-8")
st.download_button("Download CSV", csv, "Workshop_NRC_RO_Coverage.csv", "text/csv")
