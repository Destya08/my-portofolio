from datetime import datetime
data_pasien_lama = {}

# Variabel global untuk menyimpan data pasien dan layanan
nomor_antrian = 0
layanan_terpilih = None
dokter_terpilih = None
jam_terpilih = None
nama = None  # Inisialisasi variabel 'nama' sebagai None

def menu():
    global layanan_terpilih, dokter_terpilih, jam_terpilih
    while True:
        print("\nSelamat Datang di Rumah Sakit Media")
        print("1. Status Pasien")
        print("2. Jenis Layanan")
        print("3. Cetak Bukti")
        print("4. Keluar")

        pilihan = input("\nPilih nomor opsi dari menu di atas: ")

        if pilihan == '1':
            status_pasien()
        elif pilihan == '2':
            layanan_terpilih, dokter_terpilih, jam_terpilih = jenis_layanan()
            if layanan_terpilih:
                print(f"\nAnda memilih: {layanan_terpilih} - {dokter_terpilih} pada {jam_terpilih}")
        elif pilihan == '3':
            cetak_bukti()
        elif pilihan == '4':
            print("Terima kasih! Sampai jumpa.")
            exit()
        else:
            print("Pilihan tidak valid, silahkan coba lagi.")

def pasien_terdaftar():
    banyak_pasien = len(data_pasien_lama) + 1
    pasien_id = f"P00{banyak_pasien}"
    return pasien_id

def status_pasien():
    global nama
    print("\nPilih status pasien:")
    print("1. Pasien baru")
    print("2. Pasien lama")

    status = input("Masukkan pilihan : ")

    if status == '1':
        print ("\nSilahkan masukkan data diri untuk melakukan pendaftaran. ")
        pasien_id = pasien_terdaftar()
        nama = input("Nama: ")
        tanggal_lahir = input("Tanggal Lahir (dd-mm-yyyy): ")
        jenis_kelamin = input("Jenis Kelamin (Laki-Laki/Perempuan): ")
        alamat = input("Alamat: ")
        nomor_telepon =input("Nomor Telepon: ")

        data_pasien_lama[pasien_id] = {"Nama" : nama, 
                                     "Tanggal Lahir" : tanggal_lahir, 
                                     "Jenis Kelamin" : jenis_kelamin, 
                                     "Alamat" : alamat, 
                                     "Nomor Telepon" : nomor_telepon
                                     }
        print(f"Pasien berhasil terdaftar dengan id {pasien_id}")

    elif status == '2':
        print ("\nMasukkan data dibawah untuk melanjutkan: ")
        pasien_id = input("ID Pasien: ")
        tanggal_lahir = input("Tanggal Lahir (dd-mm-yyyy): ")

        if pasien_id in data_pasien_lama :
            print(f"Pasien ID {pasien_id}")
            data_pasien = data_pasien_lama[pasien_id]
            print(f"Nama: {data_pasien['Nama']}")
            print(f"Tanggal Lahir: {data_pasien['Tanggal Lahir']}")
            print(f"Jenis Kelamin: {data_pasien['Jenis Kelamin']}")
            print(f"Alamat: {data_pasien['Alamat']}")
            print(f"Nomor Telepon: {data_pasien['Nomor Telepon']}")

        else:
            print(f"Pasien tidak terdaftar karena pasien dengan id {pasien_id}tidak terdaftar")

    else:
        print("Pilihan tidak valid, silahkan coba lagi. ")
    menu()

def jenis_layanan():
    print("\nPilih Jenis Layanan:")
    print("1. Periksa Dokter Umum")
    print("2. Periksa Dokter Spesialis")

    jenis_layanan = input("Masukkan pilihan: ")

    if jenis_layanan == '1':
        print("\nJadwal Pemeriksaan Dokter Umum:")
        print("1. Dr. Ahmad - Senin, Rabu, Jumat: 09:00 - 12:00")
        print("2. Dr. Siti - Selasa, Kamis: 10:00 - 13:00")
        dokter_umum = input("Pilih dokter (1 atau 2): ")
        if dokter_umum == '1':
            return "Periksa Dokter Umum", "Dr. Ahmad", "09:00 - 12:00"
        elif dokter_umum == '2':
            return "Periksa Dokter Umum", "Dr. Siti", "10:00 - 13:00"
        else:
            print("Pilihan tidak valid")
    elif jenis_layanan == '2':
        print("\nPilih Spesialisasi Dokter:")
        print("1. Dokter Spesialis Anak")
        print("2. Dokter Spesialis Jantung")
        print("3. Dokter Spesialis Kulit")
        print("4. Dokter Spesialis THT")

        spesialis = input("\nMasukkan pilihan: ")
        if spesialis == '1':
            print("\n1. Dokter Spesialis Anak : Dr. Budi pukul 08:00 - 11:00")
            print("2. Dokter Spesialis Anak : Dr. Rena pukul 13:00 - 16:00")
            print("3. Dokter Spesialis Anak : Dr. Ana pukul 17:00 - 20:00")
            dokter_spesialis = input ("Pilih dokter (1,2, atau 3) : " )
            if dokter_spesialis == '1':
                return "Dokter Spesialis Anak", "Dr. Budi", "08:00 - 11:00"
            elif dokter_spesialis == '2':
                return "Dokter Spesialis Anak", "Dr. Rena", "13:00 - 16:00"
            elif dokter_spesialis == '3':
                return "Dokter Spesialis Anak", "Dr. Ana", "17:00 - 20:00"
            else :
                print("Pilihan tidak valid")
        elif spesialis == '2':
            print("\n1. Dokter Spesialis Jantung : Dr. Rina pukul 09:00 - 12:00")
            print("2. Dokter Spesialis Jantung : Dr. Cris pukul 17:00 - 20:00")
            dokter_spesialis = input ("Pilih dokter (1 atau 2) : " )
            if dokter_spesialis == '1':
                return "Dokter Spesialis Jantung", "Dr. Rina", "09:00 - 12:00"
            elif dokter_spesialis == '2':
                return "Dokter Spesialis Jantung", "Dr. Cris", "17:00 - 20:00"
            else :
                print("Pilihan tidak valid")
        elif spesialis == '3':
            return "Dokter Spesialis Kulit", "Dr. Lila", "10:00 - 14:00"
        elif spesialis == '4':
            print("\n1. Dokter Spesialis THT : Dr. Devin pukul 08:00 - 11:00")
            print("2. Dokter Spesialis THT : Dr. Fandi pukul 13:00 - 16:00")
            print("3. Dokter Spesialis THT : Dr. Sinta pukul 17:00 - 20:00")
            dokter_spesialis = input ("Pilih dokter (1,2, atau 3) : " )
            if dokter_spesialis == '1':
                return "Dokter Spesialis THT", "Dr. Devin", "08:00 - 11:00"
            elif dokter_spesialis == '2':
                return "Dokter Spesialis THT", "Dr. Fandi", "13:00 - 16:00"
            elif dokter_spesialis == '3':
                return "Dokter Spesialis THT", "Dr. Sinta", "17:00 - 20:00"
            else :
                print("Pilihan tidak valid")
        else:
            print("Pilihan tidak valid")
    else:
        print("Pilihan tidak valid")
        return None, None, None
    menu ()

def cetak_bukti():
    global nomor_antrian, layanan_terpilih, dokter_terpilih, jam_terpilih, nama
    print("\n--- Cetak Bukti Pendaftaran ---")
    
    # Validasi jika data pasien belum diisi
    if not nama:
        print("Data pasien belum diisi! Silahkan isi data pasien terlebih dahulu di menu Status Pasien.")
        return
    
    # Validasi jika layanan belum dipilih
    if not layanan_terpilih:
        print("Silahkan pilih jenis layanan terlebih dahulu!")
        return

    # Increment nomor antrian setiap kali cetak bukti
    nomor_antrian += 1

    # Mendapatkan waktu pemeriksaan sesuai jadwal dokter
    waktu_pemeriksaan = datetime.now().strftime("%d-%m-%Y")
    
    # Mencetak bukti pendaftaran
    print("\nBukti Pendaftaran")
    print(f"Nama Pasien          : {nama}")
    print(f"Layanan              : {layanan_terpilih}")
    print(f"Dokter               : {dokter_terpilih}")
    print(f"Nomor Antrian        : {nomor_antrian}")
    print(f"Jadwal Pemeriksaan   : {jam_terpilih}")
    print(f"Tanggal Pemeriksaan  : {waktu_pemeriksaan}")
    print("Terima kasih telah berkunjung ke Rumah Sakit Media.\n")

# Memanggil fungsi menu untuk memulai program
menu()