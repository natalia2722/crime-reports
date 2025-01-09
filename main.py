import streamlit as st
import pandas as pd
from datetime import datetime
import folium
import numpy as np
from sklearn.cluster import DBSCAN
from streamlit_folium import folium_static, st_folium
from folium.plugins import HeatMap, MarkerCluster
import sqlite3
import os
from PIL import Image
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta

UPLOAD_FOLDER = "uploaded_files"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def init_db():
    conn = sqlite3.connect('crime_reports.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS reports
        (id_laporan INTEGER PRIMARY KEY AUTOINCREMENT,
         tanggal DATETIME,
         jenis_kejahatan TEXT,
         deskripsi TEXT,
         lokasi TEXT,
         wilayah TEXT,
         latitude REAL,
         longitude REAL,
         jam TIME, -- Menggunakan tipe TIME
         hari TEXT,
         bulan INTEGER,
         file_bukti TEXT,
         kategori_risiko TEXT,
         timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
    ''')
    conn.commit()
    conn.close()

def calculate_risk_category(count):
    if count < 5:
        return "Rendah"
    elif count < 10:
        return "Sedang"
    else:
        return "Tinggi"

def get_crime_statistics():
    conn = sqlite3.connect('crime_reports.db')
    
    # Get crime counts by area
    area_stats = pd.read_sql_query("""
        SELECT wilayah, COUNT(*) as jumlah_kasus,
        strftime('%m', tanggal) as bulan
        FROM reports
        GROUP BY wilayah, bulan
    """, conn)
    
    # Calculate risk categories
    area_stats['kategori_risiko'] = area_stats['jumlah_kasus'].apply(calculate_risk_category)
    
    conn.close()
    return area_stats

def create_time_analysis_charts():
    conn = sqlite3.connect('crime_reports.db')
    
    # Get hourly data
    hourly_data = pd.read_sql_query("""
        SELECT jam, COUNT(*) as count
        FROM reports
        GROUP BY jam
        ORDER BY jam
    """, conn)
    
    # Convert time strings to datetime
    hourly_data['jam_datetime'] = pd.to_datetime(hourly_data['jam'])
    
    # Custom rounding function
    def round_hour(dt):
        # Get minutes for rounding decision
        minutes = dt.minute
        hour = dt.hour
        
        # If minutes >= 30, round up to next hour
        if minutes >= 30:
            if hour == 23:
                return '00:00'
            return f'{(hour + 1):02d}:00'
        return f'{hour:02d}:00'
    
    # Apply custom rounding
    hourly_data['jam_rounded'] = hourly_data['jam_datetime'].apply(round_hour)
    
    # Group by rounded hour and sum the counts
    hourly_grouped = hourly_data.groupby('jam_rounded')['count'].sum().reset_index()
    
    # Sort by hour for proper display
    hourly_grouped['hour_for_sort'] = pd.to_datetime(hourly_grouped['jam_rounded'], format='%H:%M').dt.hour
    hourly_grouped = hourly_grouped.sort_values('hour_for_sort')
    
    # Create hourly distribution chart
    hourly_fig = px.bar(hourly_grouped, 
                       x='jam_rounded', 
                       y='count',
                       title='Distribusi Kejahatan per Jam (Dibulatkan)',
                       labels={'jam_rounded': 'Jam', 'count': 'Jumlah Kejadian'})
    
    # Improve x-axis appearance
    hourly_fig.update_xaxes(tickangle=45)
    
    # Monthly distribution
    monthly_data = pd.read_sql_query("""
        SELECT bulan, COUNT(*) as count
        FROM reports
        GROUP BY bulan
        ORDER BY bulan
    """, conn)
    
    monthly_fig = px.line(monthly_data, 
                         x='bulan', 
                         y='count',
                         title='Tren Kejahatan per Bulan',
                         labels={'bulan': 'Bulan', 'count': 'Jumlah Kejadian'})
    
    conn.close()
    return hourly_fig, monthly_fig

def main():
    st.set_page_config(page_title="Sistem Pelaporan Kejahatan", layout="wide")
    init_db()

    menu = st.sidebar.selectbox(
        "Menu",
        ["Beranda","Tentang Kami","Tips Keamanan","Kontak Darurat", "Form Laporan", "Analisis Kejahatan", "Peta Kejahatan", "Pencarian Laporan"]
    )

    if menu == "Beranda":
        st.title("Dashboard Sistem Pelaporan Kejahatan")
        
        # Summary statistics
        col1, col2, col3 = st.columns(3)
        
        conn = sqlite3.connect('crime_reports.db')
        total_reports = pd.read_sql_query("SELECT COUNT(*) as count FROM reports", conn).iloc[0]['count']
        high_risk_areas = pd.read_sql_query(
            "SELECT COUNT(DISTINCT wilayah) as count FROM reports GROUP BY wilayah HAVING COUNT(*) >= 10", 
            conn
        ).shape[0]
        recent_reports = pd.read_sql_query(
            "SELECT COUNT(*) as count FROM reports WHERE date(tanggal) >= date('now', '-7 days')",
            conn
        ).iloc[0]['count']
        
        col1.metric("Total Laporan", total_reports)
        col2.metric("Wilayah Risiko Tinggi", high_risk_areas)
        col3.metric("Laporan 7 Hari Terakhir", recent_reports)
        
        # Time analysis charts
        hourly_fig, monthly_fig = create_time_analysis_charts()
        st.plotly_chart(hourly_fig)
        st.plotly_chart(monthly_fig)
        
    elif menu == "Tentang Kami":
        st.title("Tentang Kami")
        st.write("""
        Sistem Pelaporan Kejahatan adalah platform yang dikembangkan untuk memudahkan masyarakat 
        dalam melaporkan tindak kejahatan. Kami berkomitmen untuk menciptakan lingkungan yang 
        lebih aman dengan memfasilitasi pelaporan yang cepat dan efektif.
        """)

    elif menu == "Tips Keamanan":
        st.title("Tips Keamanan")
        st.subheader("Panduan Keamanan Pribadi")
        st.write("""
        1. Selalu waspada dengan lingkungan sekitar
        2. Hindari berjalan sendirian di tempat sepi
        3. Simpan nomor darurat di ponsel Anda
        4. Pastikan rumah selalu terkunci
        5. Gunakan pencahayaan yang cukup di sekitar rumah
        """)

    elif menu == "Kontak Darurat":
        st.title("Kontak Darurat")
        st.write("""
        - Polisi: 110
        - Ambulans: 118
        - Pemadam Kebakaran: 113
        - Call Center: 112
        """)

    elif menu == "Form Laporan":
        st.title("Form Laporan Kejahatan")
        
        # Initialize session state for location tracking
        if 'selected_location' not in st.session_state:
            st.session_state.selected_location = None
        
        col1, col2 = st.columns(2)
        
        with col1:
            tanggal = st.date_input("Tanggal Kejadian")
            jam = st.time_input("Jam Kejadian")  # Menggunakan st.time_input
            jenis_kejahatan = st.selectbox(
                "Jenis Kejahatan",
                ["Pencurian", "Perampokan", "Penipuan", "Kekerasan", "Lainnya"]
            )
            wilayah = st.selectbox(
                "Wilayah",
                ["Makassar Utara", "Makassar Selatan", "Makassar Timur", "Makassar Barat", "Makassar Pusat"]
            )
        
        with col2:
            st.write("Pilih Lokasi Kejadian pada Peta (klik pada lokasi)")
            m = folium.Map(location=[-5.1477, 119.4328], zoom_start=12)
            map_data = st_folium(m, height=300)
            
            # Update and display location immediately when map is clicked
            if map_data['last_clicked']:
                st.session_state.selected_location = map_data['last_clicked']
                st.success(
                    f"Lokasi dipilih: Latitude {st.session_state.selected_location['lat']:.6f}, "
                    f"Longitude {st.session_state.selected_location['lng']:.6f}"
                )
            
            deskripsi = st.text_area("Deskripsi Kejadian")
            bukti = st.file_uploader("Unggah Bukti (Foto/Video)", type=["jpg", "jpeg", "png", "mp4"])
        
        with st.form("submit_form"):
            submit_button = st.form_submit_button("Kirim Laporan")
            if submit_button:
                if tanggal and st.session_state.selected_location and deskripsi:
                    conn = sqlite3.connect('crime_reports.db')
                    c = conn.cursor()
                    
                    bukti_path = None
                    if bukti:
                        bukti_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{bukti.name}"
                        bukti_path = os.path.join(UPLOAD_FOLDER, bukti_filename)
                        with open(bukti_path, "wb") as f:
                            f.write(bukti.getbuffer())
                    
                    latitude = st.session_state.selected_location['lat']
                    longitude = st.session_state.selected_location['lng']
                    hari = tanggal.strftime("%A")
                    bulan = tanggal.month
                    
                    # Simpan waktu dalam format HH:MM:SS
                    c.execute("""
                        INSERT INTO reports (tanggal, jenis_kejahatan, deskripsi, lokasi, wilayah,
                        latitude, longitude, jam, hari, bulan, file_bukti)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (tanggal.strftime("%Y-%m-%d"), jenis_kejahatan, deskripsi,
                          f"Lat: {latitude}, Lng: {longitude}", wilayah,
                          latitude, longitude, jam.strftime("%H:%M:%S"), hari, bulan, bukti_path))
                    
                    conn.commit()
                    conn.close()
                    st.success("Laporan berhasil dikirim!")
                else:
                    st.error("Mohon lengkapi semua field yang wajib diisi")

    elif menu == "Analisis Kejahatan":
        st.title("Analisis Data Kejahatan")
        
        # Crime statistics by area
        stats = get_crime_statistics()
        
        st.subheader("Statistik per Wilayah")
        st.dataframe(stats)
        
        # Create visualization
        fig = px.bar(stats, x='wilayah', y='jumlah_kasus',
                    color='kategori_risiko',
                    title='Jumlah Kejahatan per Wilayah')
        st.plotly_chart(fig)
        
        # Time-based analysis
        hourly_fig, monthly_fig = create_time_analysis_charts()
        st.plotly_chart(hourly_fig)
        st.plotly_chart(monthly_fig)

    elif menu == "Peta Kejahatan":
        st.title("Peta Distribusi Kejahatan")
        
        # Create base map
        m = folium.Map(location=[-5.1477, 119.4328], zoom_start=12)
        
        # Add crime data
        conn = sqlite3.connect('crime_reports.db')
        crime_data = pd.read_sql_query(
            "SELECT latitude, longitude, jenis_kejahatan, kategori_risiko FROM reports",
            conn
        )
        
        # Create marker cluster
        marker_cluster = MarkerCluster().add_to(m)
        
        # Add markers and heatmap
        heat_data = []
        for _, row in crime_data.iterrows():
            folium.CircleMarker(
                location=[row['latitude'], row['longitude']],
                radius=8,
                popup=f"Jenis Kejahatan: {row['jenis_kejahatan']}",
                color='red',
                fill=True
            ).add_to(marker_cluster)
            
            heat_data.append([row['latitude'], row['longitude'], 1])
        
        # Add heatmap layer
        HeatMap(heat_data).add_to(m)
        
        # Display map
        folium_static(m)

    elif menu == "Pencarian Laporan":
        st.title("Pencarian Laporan")
        
        # Search filters
        col1, col2, col3 = st.columns(3)
        
        with col1:
            wilayah_filter = st.selectbox(
                "Filter Wilayah",
                ["Semua"] + ["Makassar Utara", "Makassar Selatan", "Makassar Timur", "Makassar Barat", "Makassar Pusat"]
            )
        
        with col2:
            jenis_filter = st.selectbox(
                "Filter Jenis Kejahatan",
                ["Semua"] + ["Pencurian", "Perampokan", "Penipuan", "Kekerasan", "Lainnya"]
            )
        
        with col3:
            date_filter = st.date_input("Filter Tanggal")
        
        # Build query
        query = """
            SELECT id_laporan, tanggal, jenis_kejahatan, deskripsi, 
                wilayah, lokasi, file_bukti, timestamp 
            FROM reports WHERE 1=1
        """
        params = []
        
        if wilayah_filter != "Semua":
            query += " AND wilayah = ?"
            params.append(wilayah_filter)
        
        if jenis_filter != "Semua":
            query += " AND jenis_kejahatan = ?"
            params.append(jenis_filter)
        
        if date_filter:
            query += " AND date(tanggal) = ?"
            params.append(date_filter.strftime("%Y-%m-%d"))
        
        # Execute search
        conn = sqlite3.connect('crime_reports.db')
        reports = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if not reports.empty:
            # Display each report with its image in a card-like format
            for _, report in reports.iterrows():
                with st.expander(f"Laporan {report['id_laporan']} - {report['tanggal']} - {report['jenis_kejahatan']}"):
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        if report['file_bukti'] and os.path.exists(report['file_bukti']):
                            file_extension = os.path.splitext(report['file_bukti'])[1].lower()
                            if file_extension in ['.jpg', '.jpeg', '.png']:
                                try:
                                    image = Image.open(report['file_bukti'])
                                    st.image(image, caption="Bukti Kejadian", use_container_width=True)
                                except Exception as e:
                                    st.error(f"Gagal memuat gambar: {str(e)}")
                            else:
                                st.info("File bukti bukan berupa gambar")
                        else:
                            st.info("Tidak ada bukti gambar")
                    
                    with col2:
                        st.write(f"**Wilayah:** {report['wilayah']}")
                        st.write(f"**Lokasi:** {report['lokasi']}")
                        st.write(f"**Deskripsi:**")
                        st.write(report['deskripsi'])
                        st.write(f"**Waktu Laporan:** {report['timestamp']}")
        else:
            st.write("Tidak ada laporan yang sesuai dengan kriteria pencarian.")

if __name__ == "__main__":
    main()