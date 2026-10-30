#!/bin/bash

declare -A arus_info=(
    ["Arus_Lintas_Indonesia_Arlindo"]="Arus yang mengalir dari Samudra Pasifik ke Samudra Hindia melalui laut-laut di Indonesia."
    ["Arus_Laut_Flores"]="Arus laut yang melewati Laut Flores, membawa air dari arah timur ke barat."
    ["Arus_Musiman_Laut_Natuna"]="Arus yang dipengaruhi oleh angin musiman di sekitar Laut Natuna, penting untuk perikanan lokal."
    ["Arus_Khatulistiwa"]="Arus utama yang bergerak ke barat di sepanjang garis khatulistiwa."
    ["Arus_Laut_Banda"]="Arus yang berputar di sekitar Laut Banda."
    ["Arus_Laut_Halmahera"]="Arus yang mengalir dari Laut Pasifik menuju Laut Halmahera."
    ["Arus_Laut_Arafura"]="Arus yang mengalir di Laut Arafura, sering membawa massa air dingin dari selatan."
    ["Arus_Timor"]="Arus hangat yang bergerak dari timur Indonesia ke arah selatan menuju Australia."
    ["Arus_Pecah"]="⚠️ Arus laut berbahaya, terbentuk akibat pertemuan ombak sejajar pantai, menciptakan aliran balik cepat."
)

declare -A provinsi_currents=(
    ["Jawa_Barat"]="Arus_Lintas_Indonesia_Arlindo"
    ["Jawa_Timur"]="Arus_Lintas_Indonesia_Arlindo,Arus_Laut_Flores"
    ["Jawa_Tengah"]="Arus_Pecah"
    ["Sumatera_Barat"]="Arus_Khatulistiwa"
    ["Sumatera_Selatan"]="Arus_Musiman_Laut_Natuna"
    ["Kalimantan_Timur"]="Arus_Lintas_Indonesia_Arlindo"
    ["Kalimantan_Barat"]="Arus_Khatulistiwa"
    ["Sulawesi_Utara"]="Arus_Lintas_Indonesia_Arlindo"
    ["Sulawesi_Selatan"]="Arus_Laut_Banda,Arus_Lintas_Indonesia_Arlindo"
    ["Maluku_Utara"]="Arus_Laut_Halmahera,Arus_Laut_Banda"
    ["Papua_Barat"]="Arus_Laut_Arafura,Arus_Lintas_Indonesia_Arlindo"
    ["Papua_Selatan"]="Arus_Laut_Arafura"
    ["Papua_Tengah"]="Arus_Lintas_Indonesia_Arlindo"
    ["Nusa_Tenggara_Barat"]="Arus_Lintas_Indonesia_Arlindo,Arus_Timor"
    ["Nusa_Tenggara_Timur"]="Arus_Timor,Arus_Laut_Flores"
)

declare -A wilayah_provinsi=(
    ["Jawa"]="Jawa_Barat Jawa_Timur Jawa_Tengah"
    ["Kalimantan"]="Kalimantan_Barat Kalimantan_Tengah Kalimantan_Timur Kalimantan_Utara Kalimantan_Selatan"
    ["Sumatera"]="Sumatera_Barat Sumatera_Selatan Sumatera_Utara"
    ["Sulawesi"]="Sulawesi_Barat Sulawesi_Tengah Sulawesi_Utara Sulawesi_Selatan Sulawesi_Tenggara"
    ["Maluku"]="Maluku_Utara"
    ["Papua"]="Papua_Barat Papua_Barat_Daya Papua_Tengah Papua_Selatan"
    ["Nusa_Tenggara"]="Nusa_Tenggara_Barat Nusa_Tenggara_Timur"
)

echo "Pilih wilayah:"
wilayah_list=()
index=1
for wilayah in "${!wilayah_provinsi[@]}"; do
    echo "$index. $wilayah"
    wilayah_list[$index]=$wilayah
    ((index++))
done

read -p "Masukkan nomor wilayah: " wilayah_choice
selected_wilayah=${wilayah_list[$wilayah_choice]}
if [[ -z "$selected_wilayah" ]]; then
    echo "Wilayah tidak valid."
    exit 1
fi

echo ""
echo "Wilayah: $selected_wilayah"
IFS=' ' read -r -a provinsi_array <<< "${wilayah_provinsi[$selected_wilayah]}"
for i in "${!provinsi_array[@]}"; do
    echo "$((i + 1)). ${provinsi_array[$i]}"
done

read -p "Masukkan nomor provinsi: " prov_choice
selected_provinsi=${provinsi_array[$((prov_choice - 1))]}

if [[ -z "$selected_provinsi" ]]; then
    echo "Provinsi tidak valid."
    exit 1
fi

echo ""
echo "Provinsi yang dipilih: $selected_provinsi"
currents_csv=${provinsi_currents[$selected_provinsi]}

if [[ -z "$currents_csv" ]]; then
    echo "⚠️  Data arus laut tidak tersedia untuk provinsi ini."
else
    IFS=',' read -r -a current_list <<< "$currents_csv"
    echo "Arus laut di sekitar provinsi Anda:"
    for arus in "${current_list[@]}"; do
        echo "- $arus"
        echo "  Penjelasan: ${arus_info[$arus]}"
    done
fi

echo ""
read -p "Masukkan jam saat ini [1-24]: " waktu
if [[ ! "$waktu" =~ ^[0-9]+$ ]] || (( waktu < 1 || waktu > 24 )); then
    echo "Jam tidak valid. Harus antara 1 dan 24."
    exit 1
fi

echo ""
if (( waktu >= 18 && waktu <= 24 )); then
    echo "⚠️  PERINGATAN: Saat ini adalah waktu PASANG (air laut naik)."
    echo "Hati-hati bagi warga pesisir!"
elif (( waktu >= 1 && waktu <= 6 )); then
    echo "⚠️  PERINGATAN: Saat ini adalah waktu SURUT (air laut turun)."
    echo "Waspadai air dangkal jika menggunakan kapal kecil."
else
    echo "🌊 Saat ini kondisi air laut dalam keadaan transisi. Aman dengan kewaspadaan normal."
fi

echo ""
echo "⏱ Jadwal Pasang Surut Umum:"
echo " - Pasang: sekitar pukul 18.00 - 24.00"
echo " - Surut: sekitar pukul 00.00 - 06.00"
echo " - Siklus dapat berbeda tergantung lokasi & fase bulan."
