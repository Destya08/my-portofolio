from tkinter import Tk, Canvas, Entry, Button, PhotoImage, Frame, Label, messagebox, OptionMenu, StringVar, Text
from pathlib import Path
import json
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import folium
from shapely.geometry import shape
import webbrowser
import os
import threading
import time

# Fungsi untuk menggabungkan path relatif
def relative_to_assets(base_path, path: str) -> Path:
    return Path(base_path) / Path(path)

# --- FUNGSI-FUNGSI DARI SKRIP ANALISIS GRAFIK ---
def load_data_from_json(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if 'data_internet' in data and isinstance(data['data_internet'], list):
            return data['data_internet']
        else:
            messagebox.showerror("Format Data Salah", "Key 'data_internet' tidak ditemukan atau bukan list dalam file JSON.")
            return []
    except FileNotFoundError:
        messagebox.showerror("File Tidak Ditemukan", f"File database tidak ditemukan di: {file_path}")
        return []
    except json.JSONDecodeError:
        messagebox.showerror("Error JSON", f"Gagal memparsing file JSON: {file_path}")
        return []
    except Exception as e:
        messagebox.showerror("Error Tak Terduga", f"Terjadi kesalahan saat memuat data: {e}")
        return []

def preprocess_data_for_graph(data):
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    if 'waktu_input' not in df.columns:
        messagebox.showerror("Data Error", "Kolom 'waktu_input' tidak ada dalam data.")
        return pd.DataFrame()
    df['waktu_input'] = pd.to_datetime(df['waktu_input'], errors='coerce')
    df.dropna(subset=['waktu_input'], inplace=True)
    if df.empty: return df
    df['tahun'] = df['waktu_input'].dt.year
    if 'kecepatan' not in df.columns:
        messagebox.showerror("Data Error", "Kolom 'kecepatan' tidak ada dalam data.")
        df['kecepatan1'] = None
    else:
        df['kecepatan1'] = df['kecepatan'].apply(
            lambda x: x[0] if isinstance(x, list) and len(x) > 0 and isinstance(x[0], (int, float)) else None
        )
    df.dropna(subset=['kecepatan1'], inplace=True)
    return df

def plot_grafik_rata_rata_kecepatan(ax, fig, df, tahun_awal, tahun_akhir):
    ax.clear()
    df_filtered = df[(df['tahun'] >= tahun_awal) & (df['tahun'] <= tahun_akhir)].copy()
    if df_filtered.empty:
        ax.text(0.5, 0.5, f"Tidak ada data untuk rentang tahun {tahun_awal}-{tahun_akhir}",
                         horizontalalignment='center', verticalalignment='center', transform=ax.transAxes)
        return False
    if 'daerah' not in df_filtered.columns or df_filtered['daerah'].isnull().all():
        ax.text(0.5, 0.5, "Kolom 'daerah' tidak valid atau kosong.", ha='center', va='center', transform=ax.transAxes)
        return False
    if 'kecepatan1' not in df_filtered.columns or df_filtered['kecepatan1'].isnull().all():
        ax.text(0.5, 0.5, "Kolom 'kecepatan1' tidak valid atau kosong.", ha='center', va='center', transform=ax.transAxes)
        return False
    df_filtered.loc[:, 'daerah'] = df_filtered['daerah'].astype(str)
    try:
        grouped = pd.pivot_table(df_filtered, values='kecepatan1', index='tahun', columns='daerah', aggfunc='mean')
        if grouped.empty:
            ax.text(0.5, 0.5, f"Tidak ada data yang bisa digrupkan untuk {tahun_awal}-{tahun_akhir}", ha='center', va='center', transform=ax.transAxes)
            return False
        grouped.plot(marker='o', ax=ax)
        ax.set_title(f'Rata-rata Kecepatan Internet ({tahun_awal}-{tahun_akhir})')
        unique_years_in_grouped = sorted(grouped.index.unique())
        if unique_years_in_grouped:
            ax.set_xticks(unique_years_in_grouped)
            ax.set_xticklabels([str(int(t)) for t in unique_years_in_grouped])
        ax.set_xlabel('Tahun')
        ax.set_ylabel('Rata-rata Kecepatan (Mbps)')
        ax.grid(True)
        if len(grouped.columns) > 5:
            ax.legend(title='Kabupaten/Kota', bbox_to_anchor=(1.02, 1), loc='upper left', borderaxespad=0.)
            fig.tight_layout(rect=[0, 0, 0.78, 1])
        else:
            ax.legend(title='Kabupaten/Kota')
            fig.tight_layout()
        return True
    except Exception as e:
        messagebox.showerror("Error Plotting", f"Gagal membuat grafik: {e}")
        ax.text(0.5, 0.5, f"Error saat membuat grafik:\n{e}", ha='center', va='center', transform=ax.transAxes, color='red')
        return False

# --- FUNGSI-FUNGSI DARI SKRIP PETA ANDA ---
DATABASE_PATH_FOR_MAP = r"D:\SEM 2\PPBO\pertemuan 13\proyek\database.json"
GEOJSON_PATH_FOR_MAP = r"D:\SEM 2\PPBO\pertemuan 13\proyek\id-yo.geojson"
HTML_MAP_OUTPUT_PATH = os.path.abspath("peta_kecepatan_internet_jogja.html")

def load_data_for_map_script(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if 'data_internet' in data and isinstance(data['data_internet'], list):
            if not data['data_internet']:
                messagebox.showinfo("Info Data Peta", "Tidak ada entri 'data_internet' dalam file JSON untuk peta.")
                return None
            return data['data_internet']
        else:
            messagebox.showerror("Format Data Peta Salah", "Key 'data_internet' tidak ditemukan atau bukan list dalam file JSON.")
            return None
    except FileNotFoundError:
        messagebox.showerror("File Peta Tidak Ditemukan", f"File database untuk peta tidak ditemukan di: {file_path}")
        return None
    except json.JSONDecodeError:
        messagebox.showerror("Error JSON Peta", f"Gagal memparsing file JSON untuk peta: {file_path}")
        return None
    except Exception as e:
        messagebox.showerror("Error Peta Tak Terduga", f"Terjadi kesalahan saat memuat data peta: {e}")
        return None

def preprocess_for_map_script(internet_data):
    if not internet_data:
        return pd.DataFrame()
    df = pd.DataFrame(internet_data)
    required_cols = ['kecepatan', 'daerah', 'waktu_input']
    for col in required_cols:
        if col not in df.columns:
            messagebox.showerror("Data Error Peta", f"Kolom '{col}' tidak ditemukan dalam data untuk peta.")
            return pd.DataFrame()
    return df

def calculate_all_data_speed_for_map(df):
    if df.empty or 'kecepatan' not in df.columns or 'daerah' not in df.columns:
        return pd.DataFrame(columns=['daerah', 'kecepatan_download'])
    df_copy = df.copy()
    df_copy["kecepatan_download"] = df_copy["kecepatan"].apply(
        lambda x: x[0] if isinstance(x, list) and len(x) > 0 and isinstance(x[0], (int, float)) else None
    )
    df_copy.dropna(subset=["kecepatan_download"], inplace=True)
    if df_copy.empty:
        return pd.DataFrame(columns=['daerah', 'kecepatan_download'])
    avg_speed = df_copy.groupby("daerah")["kecepatan_download"].mean().reset_index()
    return avg_speed

def calculate_specific_year_speed_for_map(df, tahun_dipilih):
    if df.empty or 'waktu_input' not in df.columns or 'kecepatan' not in df.columns or 'daerah' not in df.columns:
        return pd.DataFrame(columns=['daerah', 'kecepatan_download'])

    df_copy = df.copy()
    df_copy["waktu_input_dt"] = pd.to_datetime(df_copy["waktu_input"], errors='coerce')
    df_copy.dropna(subset=["waktu_input_dt"], inplace=True)
    if df_copy.empty:
        return pd.DataFrame(columns=['daerah', 'kecepatan_download'])

    df_filtered = df_copy[df_copy["waktu_input_dt"].dt.year == tahun_dipilih].copy()
    if df_filtered.empty:
        return pd.DataFrame(columns=['daerah', 'kecepatan_download'])

    df_filtered["kecepatan_download"] = df_filtered["kecepatan"].apply(
           lambda x: x[0] if isinstance(x, list) and len(x) > 0 and isinstance(x[0], (int, float)) else None
    )
    df_filtered.dropna(subset=["kecepatan_download"], inplace=True)
    if df_filtered.empty:
        return pd.DataFrame(columns=['daerah', 'kecepatan_download'])

    avg_speed = df_filtered.groupby("daerah")["kecepatan_download"].mean().reset_index()
    return avg_speed

def get_color_for_map_script(speed):
    if speed is None: return "#BEBEBE"
    if speed < 5: return "#d73027"
    elif speed < 10: return "#fee08b"
    else: return "#66bd63"

def generate_folium_map_from_script(opsi_tahun=None):
    internet_data = load_data_for_map_script(DATABASE_PATH_FOR_MAP)
    if not internet_data: return False

    df_original = preprocess_for_map_script(internet_data)
    if df_original.empty: return False

    map_title_suffix = "Semua Data"
    avg_speed_df = pd.DataFrame()

    if opsi_tahun is None or str(opsi_tahun).lower() == "semua data":
        avg_speed_df = calculate_all_data_speed_for_map(df_original)
    else:
        try:
            tahun = int(opsi_tahun)
            avg_speed_df = calculate_specific_year_speed_for_map(df_original, tahun)
            map_title_suffix = f"Tahun {tahun}"
        except ValueError:
            messagebox.showerror("Error Peta", "Tahun tidak valid untuk peta.")
            return False

    if avg_speed_df.empty:
        messagebox.showinfo("Info Peta", f"Tidak ada data kecepatan rata-rata untuk ditampilkan pada peta ({map_title_suffix}).")
        return False

    try:
        with open(GEOJSON_PATH_FOR_MAP, 'r', encoding='utf-8') as f:
            geo_data = json.load(f)
    except FileNotFoundError:
        messagebox.showerror("File Tidak Ditemukan", f"File GeoJSON tidak ditemukan di: {GEOJSON_PATH_FOR_MAP}")
        return False
    except json.JSONDecodeError as e:
        messagebox.showerror("Error GeoJSON", f"Gagal membaca file GeoJSON: {GEOJSON_PATH_FOR_MAP}. Detail: {e}")
        return False
    except Exception as e:
        messagebox.showerror("Error GeoJSON Umum", f"Terjadi kesalahan saat memuat GeoJSON: {e}")
        return False

    map_center = [-7.7956, 110.3695]
    m = folium.Map(location=map_center, zoom_start=10, tiles="CartoDB positron")

    for feature in geo_data['features']:
        daerah_name = feature['properties'].get('name', 'N/A')
        speed_row = avg_speed_df[avg_speed_df['daerah'].str.lower() == daerah_name.lower()]
        current_speed = None
        if not speed_row.empty:
            current_speed = speed_row.iloc[0]['kecepatan_download']
        color = get_color_for_map_script(current_speed)
        tooltip_text = f"<b>{daerah_name}</b><br>"
        if current_speed is not None:
            tooltip_text += f"Kecepatan: {current_speed:.2f} Mbps"
        else:
            tooltip_text += "Data kecepatan tidak tersedia"

        folium.GeoJson(
            feature,
            style_function=lambda x, col=color: {
                'fillColor': col, 'color': 'black', 'weight': 1, 'fillOpacity': 0.7,
            },
            tooltip=folium.Tooltip(tooltip_text),
            highlight_function=lambda x: {'weight': 2, 'color': 'yellow', 'fillOpacity': 0.5}
        ).add_to(m)
        try:
            geom = shape(feature['geometry'])
            centroid = geom.centroid
            folium.map.Marker(
                [centroid.y, centroid.x],
                icon=folium.DivIcon(
                    html=f'<div style="font-size:9px; font-weight:bold; color:black; white-space: nowrap; text-shadow: 0 0 2px white, 0 0 2px white, 0 0 2px white;">{daerah_name}</div>'
                )
            ).add_to(m)
        except Exception as e:
            print(f"Error membuat marker teks untuk {daerah_name}: {e}")

    legend_html = """
      <div style="position: fixed; 
          bottom: 20px; left: 20px; width: auto; max-width: 220px; height: auto; 
          border:1px solid grey; z-index:1000; font-size:12px;
          background-color:rgba(255,255,255,0.85); padding: 8px; border-radius:5px;">
        <b>Kategori Kecepatan Unduh (Mbps)</b><br>
        <i style="background:#66bd63;border-radius:50%;margin-right:5px;padding:0px 5px;">&nbsp;</i> &gt; 10 (Cepat)<br>
        <i style="background:#fee08b;border-radius:50%;margin-right:5px;padding:0px 5px;">&nbsp;</i> 5 – 10 (Sedang)<br>
        <i style="background:#d73027;border-radius:50%;margin-right:5px;padding:0px 5px;">&nbsp;</i> &lt; 5 (Lambat)<br>
        <i style="background:#BEBEBE;border-radius:50%;margin-right:5px;padding:0px 5px;">&nbsp;</i> Data Tidak Ada
      </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
    try:
        m.save(HTML_MAP_OUTPUT_PATH)
        webbrowser.open(f"file://{HTML_MAP_OUTPUT_PATH}")
        return True
    except Exception as e:
        messagebox.showerror("Error Menyimpan/Membuka Peta", f"Gagal menyimpan atau membuka peta HTML: {e}")
        return False
# --- AKHIR FUNGSI-FUNGSI PETA ---


# Kelas utama aplikasi
class App(Tk):
    def __init__(self):
        super().__init__()
        self.geometry("700x840")
        self.configure(bg="#FFFFFF")
        self.title("Internet Jogja App")
        self.resizable(False, False)
        self.frames = {}
        self.current_user_type = None
        self.previous_page_for_profile = "Page4"
        # Adjusted default previous page for create account to Page7 as per logic that Admin creates accounts
        self.previous_page_for_create_account = "Page7" 
        self.previous_page_for_graph = "Page4"
        self.previous_page_for_map = "Page4"
        self.previous_page_for_speedtest_loading = "Page5"
        self.form_data_page5 = {}
        self.speed_test_results = {}
        self.client_accounts_created = {} # Dictionary to store created client accounts (username: password)

        for F in (Page1, Page2, Page3, Page4, Page5, Page6, Page7, Page8, Page9, PageGraph, PageMap, Page10):
            frame = F(parent=self, controller=self)
            self.frames[F.__name__] = frame
            frame.place(x=0, y=0, width=700, height=840)

        self.show_frame("Page1")

    def show_frame(self, page_name, user_type=None, previous_page=None, 
                   previous_page_create_account=None, previous_page_graph=None, 
                   previous_page_map=None, previous_page_speedtest_loading=None):
        if user_type is not None:
            self.current_user_type = user_type
        if previous_page:
            self.previous_page_for_profile = previous_page
        if previous_page_create_account:
            self.previous_page_for_create_account = previous_page_create_account
        if previous_page_graph:
            self.previous_page_for_graph = previous_page_graph
        if previous_page_map:
            self.previous_page_for_map = previous_page_map
        if previous_page_speedtest_loading:
            self.previous_page_for_speedtest_loading = previous_page_speedtest_loading


        if page_name not in self.frames:
            print(f"ERROR: Frame '{page_name}' tidak ditemukan dalam self.frames.")
            print(f"Frame yang tersedia: {list(self.frames.keys())}")
            return

        frame = self.frames[page_name]
        self.configure(bg=frame.cget('bg'))
        print(f"Debug App (show_frame): Menampilkan frame: {page_name}")
        frame.tkraise()

        if page_name == "PageGraph" and hasattr(frame, 'load_and_preprocess_data'):
            if frame.df_processed is None:
                print(f"Debug App (show_frame): Memanggil load_and_preprocess_data untuk PageGraph.")
                frame.load_and_preprocess_data()
        elif page_name == "PageMap" and hasattr(frame, 'populate_year_options'):
            print(f"Debug App (show_frame): Memanggil populate_year_options untuk PageMap.")
            frame.populate_year_options()
        elif page_name == "Page10" and hasattr(frame, 'run_speed_test_sequence'):
            print(f"Debug App (show_frame): Memanggil run_speed_test_sequence untuk Page10.")
            frame.run_speed_test_sequence()


# === Page 1 ===
class Page1(Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#FFFFFF")
        self.controller = controller
        ASSETS_PATH = r"D:\SEM 2\PPBO\pertemuan 13\Tkinter-Designer-master\hasil1\build\assets\frame0"
        canvas = Canvas(self, bg="#FFFFFF", height=840, width=700, bd=0, highlightthickness=0, relief="ridge")
        canvas.place(x=0, y=0)
        self.image_1_bg = PhotoImage(file=relative_to_assets(ASSETS_PATH, "image_1.png"))
        canvas.create_image(350.0, 196.0, image=self.image_1_bg)
        canvas.create_text(111.0, 453.0, anchor="nw", text="Informasi Internet Jogja",
                                 fill="#000000", font=("Coiny Regular", 37 * -1))
        self.image_2_bg = PhotoImage(file=relative_to_assets(ASSETS_PATH, "image_2.png"))
        canvas.create_image(348.0, 598.0, image=self.image_2_bg)
        self.button_1_img = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_1.png"))
        button_1 = Button(self, image=self.button_1_img, borderwidth=0, highlightthickness=0,
                                  command=lambda: controller.show_frame("Page2"), relief="flat")
        button_1.place(x=144.0, y=696.0, width=429.0, height=49.0)

# === Page 2 ===
class Page2(Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#FFFFFF")
        self.controller = controller
        ASSETS_PATH = r"D:\SEM 2\PPBO\pertemuan 13\Tkinter-Designer-master\Hasil2\build\assets\frame0"
        canvas = Canvas(self, bg="#FFFFFF", height=840, width=700, bd=0, highlightthickness=0, relief="ridge")
        canvas.place(x=0, y=0)
        self.image_1_bg = PhotoImage(file=relative_to_assets(ASSETS_PATH, "image_1.png"))
        canvas.create_image(350.0, 197.0, image=self.image_1_bg)
        canvas.create_text(120.0, 456.0, anchor="nw", text="Yang Akurat dan Praktis",
                                 fill="#000000", font=("Coiny Regular", 37 * -1))
        self.image_2_bg = PhotoImage(file=relative_to_assets(ASSETS_PATH, "image_2.png"))
        canvas.create_image(348.0, 598.0, image=self.image_2_bg)
        self.button_1_img = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_1.png"))
        button = Button(self, image=self.button_1_img, borderwidth=0, highlightthickness=0,
                                 command=lambda: controller.show_frame("Page3"), relief="flat")
        button.place(x=144.0, y=696.0, width=429.0, height=49.0)

# === Page 3 ===
class Page3(Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#FFFFFF")
        self.controller = controller
        ASSETS_PATH = r"D:\SEM 2\PPBO\pertemuan 13\Tkinter-Designer-master\hasil3\build\assets\frame0"
        canvas = Canvas(self, bg="#FFFFFF", height=840, width=700, bd=0, highlightthickness=0, relief="ridge")
        canvas.place(x=0, y=0)
        self.image_1_bg = PhotoImage(file=relative_to_assets(ASSETS_PATH, "image_1.png"))
        canvas.create_image(539.0, 210.0, image=self.image_1_bg)
        canvas.create_text(172.0, 460.0, anchor="nw", text="Dengan Aplikasi ini",
                                 fill="#000000", font=("Coiny Regular", 37 * -1))
        self.image_2_bg = PhotoImage(file=relative_to_assets(ASSETS_PATH, "image_2.png"))
        canvas.create_image(348.0, 598.0, image=self.image_2_bg)
        self.button_1_img = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_1.png"))
        button = Button(self, image=self.button_1_img, borderwidth=0, highlightthickness=0,
                                 command=lambda: controller.show_frame("Page4"), relief="flat")
        button.place(x=144.0, y=696.0, width=429.0, height=49.0)

# === Page 4 (Login Page) ===
class Page4(Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#FFFFFF")
        self.controller = controller
        ASSETS_PATH = r"D:\SEM 2\PPBO\pertemuan 13\Tkinter-Designer-master\hasil4\build\assets\frame0"
        canvas = Canvas(self, bg="#FFFFFF", height=840, width=700, bd=0, highlightthickness=0, relief="ridge")
        canvas.place(x=0, y=0)
        self.image_1_bg = PhotoImage(file=relative_to_assets(ASSETS_PATH, "image_1.png"))
        canvas.create_image(350.0, 420.0, image=self.image_1_bg)
        canvas.create_text(285.0, 209.0, anchor="nw", text="Sign In",
                                 fill="#000000", font=("Coiny Regular", 37 * -1))
        self.entry_1_img_bg = PhotoImage(file=relative_to_assets(ASSETS_PATH, "entry_1.png"))
        canvas.create_image(339.5, 332.0, image=self.entry_1_img_bg)
        self.entry_1 = Entry(self, bd=0, bg="#FFFFFF", fg="#000716", highlightthickness=0)
        self.entry_1.place(x=99.0, y=302.0, width=481.0, height=58.0)
        self.entry_2_img_bg = PhotoImage(file=relative_to_assets(ASSETS_PATH, "entry_2.png"))
        canvas.create_image(339.5, 427.0, image=self.entry_2_img_bg)
        self.entry_2 = Entry(self, bd=0, bg="#FFFFFF", fg="#000716", highlightthickness=0, show="*")
        self.entry_2.place(x=99.0, y=397.0, width=481.0, height=58.0)
        canvas.create_text(95.0, 271.0, anchor="nw", text="Masukkan Username atau Email",
                                 fill="#000000", font=("Lexend Light", 18 * -1))
        canvas.create_text(95.0, 368.0, anchor="nw", text="Password",
                                 fill="#000000", font=("Lexend Light", 18 * -1))
        
        # --- MODIFIKASI Page4 DIMULAI DI SINI ---
        # "Ingin memasukkan Data Internet Jogja?" dan tombolnya (DIPERTAHANKAN)
        canvas.create_text(89.0, 682.0, anchor="nw", text="Ingin memasukkan Data Internet Jogja?",
                                 fill="#000000", font=("Lexend Bold", 18 * -1))
        self.button_input_data_img = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_1.png"))
        button_input_data = Button(self, image=self.button_input_data_img, borderwidth=0, highlightthickness=0,
                                   command=lambda: controller.show_frame("Page5"), # Link to Page5 for input data
                                   relief="flat")
        button_input_data.place(x=436, y=680, width=154, height=26.3) # Reposition if needed

        # Menghapus bagian "Belum memiliki akun?" dan tombolnya (DIHAPUS)
        # canvas.create_text(89.0, 713.0, anchor="nw", text="Belum memiliki akun?",
        #                          fill="#000000", font=("Lexend Light", 18 * -1))
        # self.button_create_account_img_p4 = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_1.png"))
        # button_create_account = Button(self, image=self.button_create_account_img_p4, borderwidth=0, highlightthickness=0,
        #                                command=lambda: controller.show_frame("Page9", previous_page_create_account="Page4"),
        #                                relief="flat")
        # button_create_account.place(x=350.0, y=711.0, width=154.0, height=26.3)
        # canvas.create_text(510.0, 713.0, anchor="nw", text="Klik Disini",
        #                          fill="#000000", font=("Lexend Light", 18 * -1))
        # --- MODIFIKASI Page4 BERAKHIR DI SINI ---

        self.button_2_img = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_2.png"))
        button_2 = Button(self, image=self.button_2_img, borderwidth=0, highlightthickness=0,
                                  command=self.authenticate_user, relief="flat")
        button_2.place(x=89, y=601, width=501, height=60)

    def authenticate_user(self):
        username = self.entry_1.get()
        password = self.entry_2.get()
        print(f"Mencoba login dengan Username: '{username}', Password: '{password}'")

        self.entry_1.delete(0, 'end')
        self.entry_2.delete(0, 'end')

        if username.lower() == "arsaganteng123" and password == "12345":
            print("Login sebagai Admin (arsaganteng123) berhasil.")
            self.controller.show_frame("Page7", user_type="admin", previous_page="Page4")
        elif username.lower() == "client" and password == "client123":
            print("Login sebagai Client berhasil.")
            self.controller.show_frame("Page6", user_type="client", previous_page="Page4")
        elif hasattr(self.controller, 'client_accounts_created') and \
             username.lower() in self.controller.client_accounts_created and \
             self.controller.client_accounts_created[username.lower()] == password:
            print(f"Login sebagai Client '{username}' (dari Page9) berhasil.")
            self.controller.show_frame("Page6", user_type="client", previous_page="Page4")
        else:
            print("Login gagal: Username atau Password salah.")
            self.controller.current_user_type = None
            messagebox.showerror("Login Gagal", "Username atau Password salah!")


# === Page 5 (Input Data Internet) ===
class Page5(Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#FFD79A")
        self.controller = controller
        ASSETS_PATH = r"D:\SEM 2\PPBO\pertemuan 13\Tkinter-Designer-master\Hasil5\build\assets\frame0"
        canvas = Canvas(self, bg="#FFD79A", height=840, width=700, bd=0, highlightthickness=0, relief="ridge")
        canvas.place(x=0, y=0)
        canvas.create_text(121.0, 54.0, anchor="nw", text="Input Data Internet",
                                 fill="#000000", font=("Coiny Regular", 37 * -1))
        self.entry_1_img_bg = PhotoImage(file=relative_to_assets(ASSETS_PATH, "entry_1.png"))
        canvas.create_image(349.0, 179.0, image=self.entry_1_img_bg)
        self.entry_1 = Entry(self, bd=0, bg="#FFFFFF", fg="#000716", highlightthickness=0)
        self.entry_1.place(x=86.0, y=149.0, width=526.0, height=58.0)
        self.entry_2_img_bg = PhotoImage(file=relative_to_assets(ASSETS_PATH, "entry_2.png"))
        canvas.create_image(350.0, 308.0, image=self.entry_2_img_bg)
        self.entry_2 = Entry(self, bd=0, bg="#FFFFFF", fg="#000716", highlightthickness=0)
        self.entry_2.place(x=87.0, y=278.0, width=526.0, height=58.0)
        self.entry_3_img_bg = PhotoImage(file=relative_to_assets(ASSETS_PATH, "entry_3.png"))
        canvas.create_image(350.0, 540.0, image=self.entry_3_img_bg)
        self.entry_3 = Entry(self, bd=0, bg="#FFFFFF", fg="#000716", highlightthickness=0)
        self.entry_3.place(x=87.0, y=510.0, width=526.0, height=58.0)
        self.entry_4_img_bg = PhotoImage(file=relative_to_assets(ASSETS_PATH, "entry_4.png"))
        canvas.create_image(349.0, 427.0, image=self.entry_4_img_bg)
        self.entry_4 = Entry(self, bd=0, bg="#FFFFFF", fg="#000716", highlightthickness=0)
        self.entry_4.place(x=86.0, y=397.0, width=526.0, height=58.0)
        canvas.create_text(72.0, 111.0, anchor="nw", text="NIK",
                                 fill="#000000", font=("Lexend Light", 30 * -1))
        canvas.create_text(71.0, 225.0, anchor="nw", text="Wilayah",
                                 fill="#000000", font=("Lexend Light", 30 * -1))
        canvas.create_text(71.0, 358.0, anchor="nw", text="Operator Sinyal",
                                 fill="#000000", font=("Lexend Light", 30 * -1))
        canvas.create_text(71.0, 465.0, anchor="nw", text="Generasi Jaringan",
                                 fill="#000000", font=("Lexend Light", 30 * -1))

        self.button_submit_img = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_1.png"))
        button_submit = Button(self, image=self.button_submit_img, borderwidth=0, highlightthickness=0,
                                 command=self.proceed_to_data_collection_page, relief="flat")
        button_submit.place(x=71.0, y=704.0, width=557.0, height=82.0)

        self.button_back_img = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_2.png"))
        button_back = Button(self, image=self.button_back_img, borderwidth=0, highlightthickness=0,
                                 command=lambda: controller.show_frame(controller.previous_page_for_profile if controller.current_user_type else "Page4"),
                                 relief="flat")
        button_back.place(x=22.0, y=45.0, width=50.0, height=50.0)

    def proceed_to_data_collection_page(self):
        nik = self.entry_1.get()
        wilayah = self.entry_2.get()
        operator_sinyal = self.entry_4.get()
        generasi_jaringan = self.entry_3.get()

        if not nik or not wilayah or not operator_sinyal or not generasi_jaringan:
            messagebox.showwarning("Data Tidak Lengkap", "Harap isi semua field sebelum melanjutkan.")
            return

        self.controller.form_data_page5 = {
            "nik": nik,
            "wilayah": wilayah,
            "operator_sinyal": operator_sinyal,
            "generasi_jaringan": generasi_jaringan,
            "waktu_input": pd.Timestamp.now().isoformat(),
            "kecepatan": []
        }
        print(f"Data dari Page5 disimpan sementara: {self.controller.form_data_page5}")
        
        self.controller.show_frame("Page10", previous_page_speedtest_loading="Page5")


# === Page 6 (Client Welcome Page) ===
class Page6(Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#FEF3E2")
        self.controller = controller
        ASSETS_PATH = r"D:\SEM 2\PPBO\pertemuan 13\Tkinter-Designer-master\Hasil6\build\assets\frame0"
        canvas = Canvas(self, bg="#FEF3E2", height=840, width=700, bd=0, highlightthickness=0, relief="ridge")
        canvas.place(x=0, y=0)
        self.image_image_1 = PhotoImage(file=relative_to_assets(ASSETS_PATH, "image_1.png"))
        canvas.create_image(349.0, 737.0, image=self.image_image_1)
        self.button_image_1_profil = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_1.png"))
        button_profil = Button(self, image=self.button_image_1_profil, borderwidth=0, highlightthickness=0,
                                 command=lambda: controller.show_frame("Page8", previous_page="Page6"),
                                 relief="flat")
        button_profil.place(x=590.0, y=741.0, width=78.70870971679688, height=78.70870971679688)
        self.button_image_2_home = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_2.png"))
        button_home = Button(self, image=self.button_image_2_home, borderwidth=0, highlightthickness=0,
                                 command=lambda: controller.show_frame("Page6"), relief="flat")
        button_home.place(x=70.0, y=751.0, width=78.70870971679688, height=68.8701171875)
        canvas.create_text(16.0, 51.0, anchor="nw", text="Selamat Datang Client",
                                 fill="#000000", font=("Lexend Bold", 22 * -1))
        self.image_image_2_main = PhotoImage(file=relative_to_assets(ASSETS_PATH, "image_2.png"))
        canvas.create_image(349.0, 277.0, image=self.image_image_2_main)

        self.button_image_3_graph_client = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_3.png"))
        button_graph_client = Button(self, image=self.button_image_3_graph_client, borderwidth=0, highlightthickness=0,
                                         command=lambda: controller.show_frame("PageGraph", previous_page_graph="Page6"),
                                         relief="flat")
        button_graph_client.place(x=159.0, y=470.0, width=373.0, height=51.0)

        self.button_image_4_map_client = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_4.png"))
        button_map_client = Button(self, image=self.button_image_4_map_client, borderwidth=0, highlightthickness=0,
                                 command=lambda: controller.show_frame("PageMap", previous_page_map="Page6"),
                                 relief="flat")
        button_map_client.place(x=163.0, y=560.0, width=373.0, height=51.0)


# === Page 7 (Admin Welcome Page) ===
class Page7(Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#FEF3E2")
        self.controller = controller
        ASSETS_PATH = r"D:\SEM 2\PPBO\pertemuan 13\Tkinter-Designer-master\Hasil7\build\assets\frame0"
        canvas = Canvas(self, bg="#FEF3E2", height=840, width=700, bd=0, highlightthickness=0, relief="ridge")
        canvas.place(x=0, y=0)

        self.image_image_1_navbar = PhotoImage(file=relative_to_assets(ASSETS_PATH, "image_1.png"))
        canvas.create_image(349.0, 737.0, image=self.image_image_1_navbar)

        self.button_image_1_profil_nav = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_1.png"))
        button_profil_nav = Button(self, image=self.button_image_1_profil_nav, borderwidth=0, highlightthickness=0,
                                         command=lambda: controller.show_frame("Page8", previous_page="Page7"),
                                         relief="flat")
        button_profil_nav.place(x=590.0, y=741.0, width=78.70870971679688, height=78.70870971679688)

        self.button_image_2_home_nav = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_2.png"))
        button_home_nav = Button(self, image=self.button_image_2_home_nav, borderwidth=0, highlightthickness=0,
                                 command=lambda: controller.show_frame("Page7"),
                                 relief="flat")
        button_home_nav.place(x=70.0, y=751.0, width=78.70870971679688, height=68.8701171875)

        canvas.create_text(12.0, 51.0, anchor="nw", text="Selamat Datang Admin",
                                 fill="#000000", font=("Lexend Bold", 22 * -1))
        
        self.image_image_2_main_content = PhotoImage(file=relative_to_assets(ASSETS_PATH, "image_2.png"))
        canvas.create_image(349.0, 277.0, image=self.image_image_2_main_content)

        # Tombol 1 (atas): Lihat Grafik (menggunakan button_3.png dari Hasil7, y=440.0)
        self.admin_button_lihat_grafik_img = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_3.png"))
        admin_button_lihat_grafik = Button(self, image=self.admin_button_lihat_grafik_img, borderwidth=0, highlightthickness=0,
                                         command=lambda: (
                                             print("Debug Page7: Tombol Lihat Grafik (button_3.png) diklik!"),
                                             controller.show_frame("PageGraph", previous_page_graph="Page7")
                                         ),
                                         relief="flat")
        admin_button_lihat_grafik.place(x=163.0, y=440.0, width=373.0, height=51.0)

        # Tombol 2 (tengah): Lihat Peta (menggunakan button_5.png dari Hasil7, y=523.0)
        self.admin_button_lihat_peta_img = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_5.png"))
        admin_button_lihat_peta = Button(self, image=self.admin_button_lihat_peta_img, borderwidth=0, highlightthickness=0,
                                     command=lambda: (
                                         print("Debug Page7: Tombol Lihat Peta (button_5.png) diklik!"),
                                         controller.show_frame("PageMap", previous_page_map="Page7")
                                     ),
                                     relief="flat")
        admin_button_lihat_peta.place(x=163.0, y=523.0, width=373.0, height=51.0)
        
        # Tombol 3 (bawah): Buat Akun Client Baru (menggunakan button_4.png dari Hasil7, y=606.0)
        self.admin_button_create_client_img = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_4.png"))
        admin_button_create_client = Button(self, image=self.admin_button_create_client_img, borderwidth=0, highlightthickness=0,
                                         command=lambda: (
                                             print("Debug Page7: Tombol Buat Akun Client Baru (button_4.png) diklik!"),
                                             controller.show_frame("Page9", previous_page_create_account="Page7") # Set previous page to Page7
                                         ),
                                         relief="flat")
        admin_button_create_client.place(x=163.0, y=606.0, width=373.0, height=51.0)


# === Page 8 (Profile Page) ===
class Page8(Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#FEF3E2")
        self.controller = controller
        ASSETS_PATH = r"D:\SEM 2\PPBO\pertemuan 13\Tkinter-Designer-master\hasil8\build\assets\frame0"
        self.canvas = Canvas(self, bg="#FEF3E2", height=840, width=700, bd=0, highlightthickness=0, relief="ridge")
        self.canvas.place(x=0, y=0)
        self.button_back_img = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_1.png"))
        button_back = Button(self, image=self.button_back_img, borderwidth=0, highlightthickness=0,
                                 command=lambda: controller.show_frame(controller.previous_page_for_profile),
                                 relief="flat")
        button_back.place(x=23.0, y=54.0, width=50.0, height=50.0)
        self.canvas.create_text(117.0, 56.0, anchor="nw", text="Profile",
                                 fill="#000000", font=("Coiny Regular", 43 * -1))
        self.profile_image_bg = PhotoImage(file=relative_to_assets(ASSETS_PATH, "image_1.png"))
        self.canvas.create_image(349.0, 218.0, image=self.profile_image_bg)
        self.nama_pengguna_text_id = self.canvas.create_text(174.0, 334.0, anchor="nw", text="Nama Pengguna",
                                 fill="#000000", font=("Coiny Regular", 43 * -1))
        self.email_text_id = self.canvas.create_text(166.0, 420.0, anchor="nw", text="User@gmail.com",
                                 fill="#000000", font=("Coiny Regular", 43 * -1))
        self.button_edit_img = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_2.png"))
        button_edit = Button(self, image=self.button_edit_img, borderwidth=0, highlightthickness=0,
                                 command=lambda: print("Tombol Edit Profil diklik"), relief="flat")
        button_edit.place(x=23.0, y=577.0, width=243.0, height=49.0)
        self.button_logout_img = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_3.png"))
        button_logout = Button(self, image=self.button_logout_img, borderwidth=0, highlightthickness=0,
                                 command=lambda: controller.show_frame("Page4", user_type=None),
                                 relief="flat")
        button_logout.place(x=387.0, y=581.0, width=243.0, height=49.0)

    def update_profile_info(self, username="Nama Pengguna", email="User@gmail.com"):
        self.canvas.itemconfig(self.nama_pengguna_text_id, text=username)
        self.canvas.itemconfig(self.email_text_id, text=email)


# === Page 9 (Buat Akun Client Baru) ===
class Page9(Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#FFDAA0")
        self.controller = controller
        ASSETS_PATH = r"D:\SEM 2\PPBO\pertemuan 13\Tkinter-Designer-master\Hasil9\build\assets\frame0"
        canvas = Canvas(self, bg="#FFDAA0", height=840, width=700, bd=0, highlightthickness=0, relief="ridge")
        canvas.place(x=0, y=0)
        self.img_navbar_bg_create = PhotoImage(file=relative_to_assets(ASSETS_PATH, "image_1.png"))
        canvas.create_image(349.0, 737.0, image=self.img_navbar_bg_create)
        self.btn_nav1_create_img = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_1.png"))
        btn_nav1_create = Button(self, image=self.btn_nav1_create_img, borderwidth=0, highlightthickness=0,
                                 command=lambda: controller.show_frame(controller.previous_page_for_create_account),
                                 relief="flat")
        btn_nav1_create.place(x=590.0, y=741.0, width=78.70870971679688, height=78.70870971679688)
        self.btn_nav2_create_img = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_2.png"))
        btn_nav2_create = Button(self, image=self.btn_nav2_create_img, borderwidth=0, highlightthickness=0,
                                 command=lambda: controller.show_frame(controller.previous_page_for_create_account),
                                 relief="flat")
        btn_nav2_create.place(x=70.0, y=751.0, width=78.70870971679688, height=68.8701171875)
        canvas.create_text(89.0, 62.0, anchor="nw", text="Buat Akun Client Baru",
                                 fill="#000000", font=("Lexend Bold", 22 * -1))
        self.btn_back_create_img = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_3.png"))
        btn_back_create = Button(self, image=self.btn_back_create_img, borderwidth=0, highlightthickness=0,
                                 command=lambda: controller.show_frame(controller.previous_page_for_create_account),
                                 relief="flat")
        btn_back_create.place(x=20.0, y=51.0, width=50.0, height=50.0)
        self.entry_1_img_create_bg = PhotoImage(file=relative_to_assets(ASSETS_PATH, "entry_1.png"))
        canvas.create_image(333.5, 199.0, image=self.entry_1_img_create_bg)
        self.entry_username_client = Entry(self, bd=0, bg="#FFFFFF", fg="#000716", highlightthickness=0)
        self.entry_username_client.place(x=104.0, y=176.0, width=459.0, height=44.0)
        self.entry_2_img_create_bg = PhotoImage(file=relative_to_assets(ASSETS_PATH, "entry_2.png"))
        canvas.create_image(333.5, 306.0, image=self.entry_2_img_create_bg)
        self.entry_password_client = Entry(self, bd=0, bg="#FFFFFF", fg="#000716", highlightthickness=0, show="*")
        self.entry_password_client.place(x=104.0, y=283.0, width=459.0, height=44.0)
        canvas.create_text(89.0, 137.0, anchor="nw", text="Username Client",
                                 fill="#000000", font=("Lexend Bold", 22 * -1))
        canvas.create_text(92.0, 244.0, anchor="nw", text="Password Client",
                                 fill="#000000", font=("Lexend Bold", 22 * -1))
        self.btn_create_account_final_img = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_4.png"))
        btn_create_account_final = Button(self, image=self.btn_create_account_final_img, borderwidth=0, highlightthickness=0,
                                         command=self.create_client_account,
                                         relief="flat")
        btn_create_account_final.place(x=56.0, y=408.0, width=557.0, height=82.0)

    def create_client_account(self):
        new_username = self.entry_username_client.get()
        new_password = self.entry_password_client.get()
        if new_username and new_password:
            print(f"Membuat akun client baru: Username='{new_username}', Password='{new_password}'")
            if not hasattr(self.controller, 'client_accounts_created'):
                self.controller.client_accounts_created = {}
            self.controller.client_accounts_created[new_username.lower()] = new_password
            print(f"Akun baru (simulasi) tersimpan: {self.controller.client_accounts_created}")
            messagebox.showinfo("Sukses", f"Akun untuk '{new_username}' berhasil dibuat (simulasi).\nSekarang Anda dapat login dengan akun ini.")
            self.entry_username_client.delete(0, 'end')
            self.entry_password_client.delete(0, 'end')
            self.controller.show_frame(self.controller.previous_page_for_create_account)
        else:
            messagebox.showwarning("Input Kosong", "Username dan Password tidak boleh kosong.")


# === PageGraph (Halaman untuk Menampilkan Grafik) ===
class PageGraph(Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#E0E0E0")
        self.controller = controller
        self.df_processed = None

        label_title = Label(self, text="Analisis Kecepatan Internet", font=("Lexend Bold", 20), bg="#E0E0E0")
        label_title.place(x=50, y=20)

        label_tahun_awal = Label(self, text="Tahun Awal:", font=("Lexend", 12), bg="#E0E0E0")
        label_tahun_awal.place(x=50, y=70)
        self.entry_tahun_awal = Entry(self, font=("Lexend", 12), width=8)
        self.entry_tahun_awal.place(x=170, y=70)

        label_tahun_akhir = Label(self, text="Tahun Akhir:", font=("Lexend", 12), bg="#E0E0E0")
        label_tahun_akhir.place(x=280, y=70)
        self.entry_tahun_akhir = Entry(self, font=("Lexend", 12), width=8)
        self.entry_tahun_akhir.place(x=400, y=70)

        button_show_graph = Button(self, text="Tampilkan", font=("Lexend", 12),
                                         command=self.display_graph)
        button_show_graph.place(x=500, y=68, width=100, height=30)

        button_back = Button(self, text="Kembali", font=("Lexend", 12),
                                 command=self.go_back)
        button_back.place(x=50, y=780, width=100, height=30)

        self.graph_frame = Frame(self, bg="white")
        self.graph_frame.place(x=50, y=120, width=600, height=650)

        self.fig, self.ax = plt.subplots(figsize=(7, 6))
        self.canvas_widget = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.plot_widget = self.canvas_widget.get_tk_widget()
        self.plot_widget.pack(side="top", fill="both", expand=True)

    def go_back(self):
        self.ax.clear()
        self.canvas_widget.draw()
        print(f"Debug PageGraph (go_back): Kembali ke -> {self.controller.previous_page_for_graph}")
        self.controller.show_frame(self.controller.previous_page_for_graph)

    def load_and_preprocess_data(self):
        file_path = r"D:\SEM 2\PPBO\pertemuan 13\proyek\database.json"
        print(f"Debug PageGraph (load_data): Mencoba memuat dari -> {file_path}")
        raw_data = load_data_from_json(file_path) # Menggunakan fungsi global dari analisis grafik
        if raw_data:
            self.df_processed = preprocess_data_for_graph(raw_data) # Menggunakan fungsi global dari analisis grafik
            if self.df_processed.empty:
                print("Debug PageGraph (load_data): DataFrame kosong setelah preprocessing.")
            else:
                print(f"Debug PageGraph (load_data): Data berhasil diproses, jumlah baris: {len(self.df_processed)}")
        else:
            self.df_processed = pd.DataFrame()
            print("Debug PageGraph (load_data): Tidak ada raw data atau error saat load_data_from_json.")


    def display_graph(self):
        if self.df_processed is None :
            print("Debug PageGraph (display_graph): df_processed adalah None, memanggil load_and_preprocess_data...")
            self.load_and_preprocess_data()

        if self.df_processed is None or self.df_processed.empty:
                messagebox.showerror("Error", "Data tidak tersedia atau kosong. Tidak bisa menampilkan grafik.")
                self.ax.clear()
                self.canvas_widget.draw()
                return

        try:
            tahun_awal_str = self.entry_tahun_awal.get()
            tahun_akhir_str = self.entry_tahun_akhir.get()

            if not tahun_awal_str or not tahun_akhir_str:
                messagebox.showwarning("Input Kosong", "Tahun awal dan tahun akhir harus diisi.")
                return
            tahun_awal = int(tahun_awal_str)
            tahun_akhir = int(tahun_akhir_str)
            if tahun_awal > tahun_akhir:
                messagebox.showwarning("Input Tidak Valid", "Tahun awal tidak boleh lebih besar dari tahun akhir.")
                return
        except ValueError:
            messagebox.showerror("Input Tidak Valid", "Tahun harus berupa angka.")
            return
        except Exception as e:
            messagebox.showerror("Error Input", f"Terjadi kesalahan input: {e}")
            return

        print(f"Debug PageGraph (display_graph): Menampilkan grafik untuk tahun {tahun_awal}-{tahun_akhir}")
        # Memanggil fungsi plot global yang sudah dimodifikasi
        plot_successful = plot_grafik_rata_rata_kecepatan(self.ax, self.fig, self.df_processed, tahun_awal, tahun_akhir)

        if plot_successful:
            if self.ax.get_legend() and self.ax.get_legend().get_bbox_to_anchor():
                self.fig.tight_layout(rect=[0, 0, 0.80, 1])
            else:
                self.fig.tight_layout()
        self.canvas_widget.draw()


# === PageMap (Halaman untuk Menampilkan Peta Folium) ===
class PageMap(Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#F0F8FF")
        self.controller = controller
        self.df_map_data_raw = None

        label_title = Label(self, text="Peta Sebaran Kecepatan Internet", font=("Lexend Bold", 20), bg="#F0F8FF")
        label_title.place(x=50, y=20)

        label_opsi = Label(self, text="Pilih Tahun:", font=("Lexend", 12), bg="#F0F8FF")
        label_opsi.place(x=50, y=70)

        self.selected_year = StringVar(self)
        self.year_options = ["Semua Data"]
        self.option_menu_year = OptionMenu(self, self.selected_year, *self.year_options)
        self.option_menu_year.config(font=("Lexend", 12), width=15)
        self.option_menu_year.place(x=160, y=68)

        button_show_map = Button(self, text="Tampilkan Peta", font=("Lexend", 12),
                                         command=self.show_map_action)
        button_show_map.place(x=350, y=68, width=150, height=30)

        button_back = Button(self, text="Kembali", font=("Lexend", 12),
                                 command=self.go_back_map)
        button_back.place(x=50, y=780, width=100, height=30)

        self.status_label = Label(self, text="Pilih tahun dan klik 'Tampilkan Peta'.\nPeta akan terbuka di browser.", font=("Lexend", 10), bg="#F0F8FF", justify="left")
        self.status_label.place(x=50, y=120, width=600)

    def populate_year_options(self):
        print("Debug PageMap: populate_year_options dipanggil")
        self.df_map_data_raw = load_data_for_map_script(DATABASE_PATH_FOR_MAP)
        current_selection = self.selected_year.get()

        if self.df_map_data_raw:
            df_temp = pd.DataFrame(self.df_map_data_raw)
            if 'waktu_input' in df_temp.columns:
                df_temp['waktu_input_dt'] = pd.to_datetime(df_temp['waktu_input'], errors='coerce')
                df_temp.dropna(subset=['waktu_input_dt'], inplace=True)
                if not df_temp.empty:
                    unique_years = sorted(df_temp['waktu_input_dt'].dt.year.unique(), reverse=True)
                    self.year_options = ["Semua Data"] + [str(year) for year in unique_years]
                else: self.year_options = ["Semua Data"]
            else: self.year_options = ["Semua Data"]
        else: self.year_options = ["Semua Data"]

        menu = self.option_menu_year["menu"]
        menu.delete(0, "end")
        for year_str in self.year_options:
            menu.add_command(label=year_str, command=lambda value=year_str: self.selected_year.set(value))
        
        if current_selection in self.year_options: self.selected_year.set(current_selection)
        elif self.year_options: self.selected_year.set(self.year_options[0])
        else: self.selected_year.set("Tidak ada data")
        print(f"Debug PageMap: Opsi tahun diperbarui: {self.year_options}, terpilih: {self.selected_year.get()}")


    def show_map_action(self):
        selected_option = self.selected_year.get()
        print(f"Debug PageMap: Tombol Tampilkan Peta diklik dengan opsi: {selected_option}")
        if self.df_map_data_raw is None:
            messagebox.showerror("Error Data Peta", "Gagal memuat data untuk peta. Tidak dapat menampilkan peta.")
            return
        tahun_untuk_map = None
        if selected_option.lower() != "semua data":
            try: tahun_untuk_map = int(selected_option)
            except ValueError:
                messagebox.showerror("Error Peta", "Pilihan tahun tidak valid.")
                return
        self.status_label.config(text="Sedang membuat peta, mohon tunggu...")
        self.update_idletasks()
        map_generated = generate_folium_map_from_script(tahun_untuk_map)
        if map_generated:
            self.status_label.config(text=f"Peta untuk '{selected_option}' telah dibuat dan dibuka di browser.\nFile: {HTML_MAP_OUTPUT_PATH}")
        else:
            self.status_label.config(text="Gagal membuat peta. Periksa konsol atau pesan error sebelumnya untuk detail.")

    def go_back_map(self):
        self.controller.show_frame(self.controller.previous_page_for_map)

# === Page10 (Sedang Mengambil Data / Speedtest Loading) ===
class Page10(Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#FFDAA0")
        self.controller = controller
        ASSETS_PATH = r"D:\SEM 2\PPBO\pertemuan 13\Tkinter-Designer-master\hasil10\build\assets\frame0"
        self.canvas = Canvas(self, bg="#FFDAA0", height=840, width=700, bd=0, highlightthickness=0, relief="ridge")
        self.canvas.place(x=0, y=0)
        self.canvas.create_text(110.0, 50.0, anchor="nw", text="Sedang Mengambil Data",
                                 fill="#000000", font=("Coiny Regular", 37 * -1))

        self.loading_label = Label(self, text="Memulai proses...", font=("Lexend", 16), bg="#FFDAA0")
        self.loading_label.place(relx=0.5, rely=0.3, anchor="center")

        self.status_log_text = Text(self, bd=0, bg="#FFFFFF", fg="#000716", highlightthickness=0, font=("Arial", 10), wrap="word", height=10, width=40)
        self.status_log_text.place(relx=0.5, rely=0.5, anchor="center", width=500, height=200)
        self.status_log_text.insert("1.0", "Status Log Proses:\n")
        self.status_log_text.config(state="disabled")

        # Tombol Kembali (button_2.png dari Hasil10)
        # Tombol ini bisa digunakan jika pengguna ingin membatalkan proses input data dan speedtest
        self.button_image_2_kembali = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_2.png"))
        button_kembali = Button(self, image=self.button_image_2_kembali, borderwidth=0, highlightthickness=0,
                                 command=lambda: controller.show_frame(controller.previous_page_for_speedtest_loading or "Page5"),
                                 relief="flat")
        button_kembali.place(x=22.0, y=45.0, width=50.0, height=50.0)

        # Tombol Lanjutkan (button_1.png dari Hasil10) dihilangkan, karena navigasi otomatis
        # self.button_image_1_lanjutkan = PhotoImage(file=relative_to_assets(ASSETS_PATH, "button_1.png"))
        # self.button_lanjutkan = Button(self, image=self.button_image_1_lanjutkan, ... )
        # self.button_lanjutkan.place(...)


    def add_status_log(self, message):
        if hasattr(self, 'status_log_text') and self.status_log_text.winfo_exists():
            self.status_log_text.config(state="normal")
            self.status_log_text.insert("end", message + "\n")
            self.status_log_text.see("end")
            self.status_log_text.config(state="disabled")
            self.update_idletasks()

    def run_speed_test_sequence(self):
        self.loading_label.config(text="Mengukur Ping...")
        self.add_status_log("Tes dimulai: Mengukur Ping...")
        threading.Thread(target=self._simulated_speed_test_task, daemon=True).start()

    def _simulated_speed_test_task(self):
        # Di sini Anda akan menjalankan speedtest yang sebenarnya
        # Untuk sekarang, kita gunakan simulasi
        print("Simulasi: Mengukur Ping...")
        time.sleep(1) # Simulasi delay
        ping_result_val = "25" # Hasil dummy

        print("Simulasi: Mengukur Kecepatan Unduh...")
        self.after(0, lambda: self.loading_label.config(text="Mengukur Kecepatan Unduh..."))
        self.after(0, lambda: self.add_status_log("Ping selesai. Mengukur Kecepatan Unduh..."))
        time.sleep(2) # Simulasi delay
        download_result_val = "75.5" # Hasil dummy

        print("Simulasi: Mengukur Kecepatan Unggah...")
        self.after(0, lambda: self.loading_label.config(text="Mengukur Kecepatan Unggah..."))
        self.after(0, lambda: self.add_status_log("Tes Unduh selesai. Mengukur Kecepatan Unggah..."))
        time.sleep(2) # Simulasi delay
        upload_result_val = "30.2" # Hasil dummy
        
        self.after(0, lambda: self.finish_speed_test(ping_result_val, download_result_val, upload_result_val))


    def finish_speed_test(self, ping, download, upload):
        self.loading_label.config(text="Tes Kecepatan Selesai!")
        self.add_status_log("Tes Unggah selesai. Semua tes komplet.")
        
        self.controller.speed_test_results = {
            "ping": f"{ping} ms",
            "download": f"{download} Mbps",
            "upload": f"{upload} Mbps"
        }
        
        if hasattr(self.controller, 'form_data_page5') and self.controller.form_data_page5:
            try:
                # Menggabungkan hasil speedtest ke form_data_page5
                # Format kecepatan: [download, upload, ping]
                self.controller.form_data_page5["kecepatan"] = [
                    float(download),
                    float(upload),
                    int(ping)
                ]
                print(f"Data Page5 diperbarui dengan hasil speedtest: {self.controller.form_data_page5}")
                
                # Panggil fungsi untuk menyimpan ke database.json
                self.save_to_database(self.controller.form_data_page5)

            except ValueError as e:
                messagebox.showerror("Error Hasil Tes", f"Format hasil speedtest tidak valid: {e}")
                self.controller.show_frame("Page4", user_type=None)
                return
            except Exception as e:
                messagebox.showerror("Error Pemrosesan", f"Gagal memproses hasil tes: {e}")
                self.controller.show_frame("Page4", user_type=None)
                return

        messagebox.showinfo("Speedtest Selesai", f"Hasil:\nPing: {self.controller.speed_test_results['ping']}\nDownload: {self.controller.speed_test_results['download']}\nUpload: {self.controller.speed_test_results['upload']}\n\nData telah disimpan (simulasi).")
        
        # Navigasi kembali ke halaman login setelah selesai
        self.controller.show_frame("Page4", user_type=None)


    def save_to_database(self, new_data_entry):
        file_path = DATABASE_PATH_FOR_MAP # Asumsi path database sama untuk grafik dan peta
        all_data = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                database = json.load(f)
                if 'data_internet' in database and isinstance(database['data_internet'], list):
                    all_data = database['data_internet']
                else: # Jika key 'data_internet' tidak ada atau bukan list, buat struktur baru
                    database = {"data_internet": []}
                    all_data = database['data_internet']

        except FileNotFoundError:
            print(f"File database {file_path} tidak ditemukan, akan membuat baru.")
            database = {"data_internet": []}
            all_data = database['data_internet']
        except json.JSONDecodeError:
            messagebox.showwarning("Peringatan Database", f"Format database.json tidak valid atau file kosong. Data akan ditambahkan ke struktur baru.")
            database = {"data_internet": []}
            all_data = database['data_internet']
        except Exception as e:
            messagebox.showerror("Error Database", f"Kesalahan saat membaca database: {e}")
            return # Jangan lanjutkan jika tidak bisa baca

        all_data.append(new_data_entry)
        database_to_save = {"data_internet": all_data}

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(database_to_save, f, indent=4)
            print(f"Data baru berhasil disimpan ke {file_path}")
        except Exception as e:
            messagebox.showerror("Error Penyimpanan", f"Gagal menyimpan data ke database: {e}")


# === Jalankan Aplikasi ===
if __name__ == "__main__":
    app = App()
    app.mainloop()