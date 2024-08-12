import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkcalendar import DateEntry
import pandas as pd
from random import shuffle
from datetime import datetime, timedelta
import sqlite3


# Veritabanı bağlantısı ve tablo oluşturma
def veritabani_baglantisi():
    conn = sqlite3.connect('nobet_app.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS personel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isim TEXT NOT NULL,
            grup INTEGER NOT NULL DEFAULT 1,
            haftasonu_nobeti INTEGER NOT NULL DEFAULT 1,
            izin_baslangic TEXT,
            izin_bitis TEXT
        )
    ''')
    conn.commit()
    return conn


# Personel listesini veritabanına kaydetme
def personel_kaydet(conn, personel_listesi):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM personel")
    for personel in personel_listesi:
        cursor.execute(
            "INSERT INTO personel (isim, grup, haftasonu_nobeti, izin_baslangic, izin_bitis) VALUES (?, ?, ?, ?, ?)",
            (personel["isim"], personel["grup"], int(personel["haftasonu_nobeti"]), personel.get("izin_baslangic"),
             personel.get("izin_bitis")))
    conn.commit()


# Personel listesini veritabanından yükleme
def personel_yukle(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT isim, grup, haftasonu_nobeti, izin_baslangic, izin_bitis FROM personel")
    rows = cursor.fetchall()
    personel_listesi = [{"isim": row[0], "grup": row[1], "haftasonu_nobeti": bool(row[2]), "izin_baslangic": row[3],
                         "izin_bitis": row[4]} for row in rows]
    return personel_listesi


# Nöbet Çizelgesi Fonksiyonları
def tarih_araligi_olustur(baslangic_tarihi, personel_sayisi):
    tarih_araligi = []
    baslangic = datetime.strptime(baslangic_tarihi, '%Y-%m-%d')
    bitis = baslangic + timedelta(days=personel_sayisi - 1)
    gün = baslangic

    while gün <= bitis:
        tarih_araligi.append(gün.strftime('%Y-%m-%d'))
        gün += timedelta(days=1)

    return tarih_araligi


def hafta_ici_ve_hafta_sonu_ayir(tarih_araligi):
    hafta_ici_gunleri = []
    hafta_sonu_gunleri = []

    for tarih in tarih_araligi:
        gün = datetime.strptime(tarih, '%Y-%m-%d').weekday()
        if gün < 5:  # Pazartesi=0, Cuma=4, Cumartesi=5, Pazar=6
            hafta_ici_gunleri.append(tarih)
        else:
            hafta_sonu_gunleri.append(tarih)

    return hafta_ici_gunleri, hafta_sonu_gunleri


def nöbet_çizelgesi_oluştur(personel_listesi, izinli_listesi, tarih_araligi, max_nobet_sayisi, min_gun_araligi):
    hafta_ici_gunleri, hafta_sonu_gunleri = hafta_ici_ve_hafta_sonu_ayir(tarih_araligi)

    nöbet_çizelgesi = {}
    nöbet_sayilari = {personel["isim"]: 0 for personel in personel_listesi}
    son_nöbet_günleri = {personel["isim"]: None for personel in personel_listesi}
    hafta_sonu_nobet_sayisi = {personel["isim"]: 0 for personel in personel_listesi}

    def izinli_mi(personel, tarih):
        izin_baslangic = personel.get("izin_baslangic")
        izin_bitis = personel.get("izin_bitis")
        if izin_baslangic and izin_bitis:
            izin_baslangic = datetime.strptime(izin_baslangic, '%Y-%m-%d')
            izin_bitis = datetime.strptime(izin_bitis, '%Y-%m-%d')
            tarih_obj = datetime.strptime(tarih, '%Y-%m-%d')
            if izin_baslangic <= tarih_obj <= izin_bitis:
                return True
        return False

    def nöbet_yaz(günler, hafta_sonu=False):
        nöbet_günlüğü = {}
        for gün in günler:
            gruplar = {grup: [p for p in personel_listesi if p["grup"] == grup] for grup in range(1, 11)}
            grup_sirasi = list(gruplar.keys())
            shuffle(grup_sirasi)

            seçilenler = []
            for grup in grup_sirasi:
                uygun_personeller = [
                    p["isim"] for p in gruplar[grup]
                    if p["isim"] not in izinli_listesi.get(gün, [])
                       and not izinli_mi(p, gün)
                       and nöbet_sayilari[p["isim"]] < max_nobet_sayisi
                       and (son_nöbet_günleri[p["isim"]] is None or
                            (datetime.strptime(gün, '%Y-%m-%d') - datetime.strptime(son_nöbet_günleri[p["isim"]],
                                                                                    '%Y-%m-%d')).days >= min_gun_araligi)
                       and (not hafta_sonu or p["haftasonu_nobeti"])
                       and (not hafta_sonu or hafta_sonu_nobet_sayisi[p["isim"]] < 1)
                ]
                shuffle(uygun_personeller)
                if len(seçilenler) < 2:
                    seçilenler.extend(uygun_personeller[:2 - len(seçilenler)])

            # Eğer yeterli personel seçilemezse farklı gruptan doldur
            if len(seçilenler) < 2:
                for grup in grup_sirasi:
                    if len(seçilenler) >= 2:
                        break
                    for personel in gruplar[grup]:
                        if personel["isim"] not in seçilenler and nöbet_sayilari[personel["isim"]] < max_nobet_sayisi:
                            seçilenler.append(personel["isim"])
                            break

            nöbet_günlüğü[gün] = seçilenler
            for personel in seçilenler:
                if personel:
                    nöbet_sayilari[personel] += 1
                    son_nöbet_günleri[personel] = gün
                    if hafta_sonu:
                        hafta_sonu_nobet_sayisi[personel] += 1
        return nöbet_günlüğü

    # Hafta sonunu öncelikli olarak dolduralım
    nöbet_çizelgesi["Hafta Sonu"] = nöbet_yaz(hafta_sonu_gunleri, hafta_sonu=True)
    # Ardından hafta içini dolduralım
    nöbet_çizelgesi["Hafta İçi"] = nöbet_yaz(hafta_ici_gunleri)

    return nöbet_çizelgesi


def excel_yaz(nöbet_çizelgesi, dosya_adi):
    try:
        with pd.ExcelWriter(dosya_adi, engine='openpyxl') as writer:
            for kategori, nöbetler in nöbet_çizelgesi.items():
                if nöbetler:  # Nöbetler boş değilse
                    df = pd.DataFrame(nöbetler).T
                    df.columns = ["Nöbetçi 1", "Nöbetçi 2"]
                    df.to_excel(writer, sheet_name=kategori)
    except Exception as e:
        messagebox.showerror("Hata", f"Excel dosyası oluşturulurken bir hata oluştu: {str(e)}")


# Arayüz
class NobetApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Nöbet Yönetim Sistemi")
        self.geometry("600x1000")

        self.conn = veritabani_baglantisi()

        # Personel Listesi
        self.personel_listesi = personel_yukle(self.conn)
        self.izinli_listesi = {}

        # Kullanıcı Girişi
        self.setup_widgets()

    def setup_widgets(self):
        # Personel ekleme formu
        self.personel_frame = tk.Frame(self)
        self.personel_frame.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.personel_entry = tk.Entry(self.personel_frame, width=40, )
        self.personel_entry.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.personel_entry.insert(0, "İsim Giriniz")
        self.personel_entry.bind("<FocusIn>", self.on_entry_click)
        self.personel_entry.bind("<FocusOut>", self.on_focusout)

        self.grup_var = tk.IntVar()
        self.grup_label = tk.Label(self.personel_frame, text="Grup:")
        self.grup_label.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        self.grup_spinbox = tk.Spinbox(self.personel_frame, from_=1, to=10, textvariable=self.grup_var, width=3)
        self.grup_spinbox.grid(row=0, column=2, padx=5, pady=5, sticky="w")

        self.ekle_button = tk.Button(self.personel_frame, text="Personel Ekle", command=self.ekle_personel, fg="white",
                                     bg="green")
        self.ekle_button.grid(row=0, column=3, padx=5, pady=5, sticky="w")

        # Personel Listesi Görüntüleme (Tablo olarak Treeview kullanıldı)
        self.personel_tree = ttk.Treeview(self, columns=("isim", "grup", "haftasonu", "izin"), show='headings',
                                          height=28)
        self.personel_tree.grid(row=1, column=0, columnspan=4, padx=10, pady=10, sticky="nsew")

        # Sütun başlıklarını belirleyelim
        self.personel_tree.heading("isim", text="Kişi")
        self.personel_tree.heading("grup", text="Grup")
        self.personel_tree.heading("haftasonu", text="Hafta Sonu Durumu")
        self.personel_tree.heading("izin", text="İzin Durumu")

        # Sütun genişliklerini ayarlayalım
        self.personel_tree.column("isim", width=200)
        self.personel_tree.column("grup", width=30, anchor="center")
        self.personel_tree.column("haftasonu", width=110, anchor="center")
        self.personel_tree.column("izin", width=200, anchor="center")

        self.ayar_frame = tk.Frame(self)
        self.ayar_frame.grid(row=2, column=0, padx=5, pady=5, sticky="w")

        # Hafta Sonu Nöbeti Değiştirme
        self.haftasonu_toggle_button = tk.Button(self.ayar_frame, text="Hafta Sonu Durumunu Değiştir",
                                                 command=self.haftasonu_toggle, fg="white",
                                                 bg="orange")
        self.haftasonu_toggle_button.grid(row=2, column=0, padx=5, pady=5, sticky="w")

        self.isim_duzenle_button = tk.Button(self.ayar_frame, text="İsim Düzenle", command=self.isim_duzenle,
                                             fg="white",
                                             bg="blue")
        self.isim_duzenle_button.grid(row=2, column=1, padx=10, pady=10, sticky="w")

        # Personel Silme
        self.cikar_button = tk.Button(self.ayar_frame, text="Seçili Personeli Çıkar", command=self.cikar_personel,
                                      fg="white",
                                      bg="red")
        self.cikar_button.grid(row=2, column=2, padx=5, pady=5, sticky="w")

        # Personel Listesini Güncelleme
        self.guncelle_button = tk.Button(self.ayar_frame, text="Personel Listesini Güncelle",
                                         command=self.guncelle_personel_listesi, fg="white",
                                         bg="green")
        self.guncelle_button.grid(row=2, column=3, padx=5, pady=5, sticky="w")

        # Grup Değiştirme
        self.grup_degis_label = tk.Label(self.ayar_frame, text="Yeni Grup:")
        self.grup_degis_label.grid(row=4, column=0, padx=5, pady=5, sticky="w")

        self.grup_degis_spinbox = tk.Spinbox(self.ayar_frame, from_=1, to=10, width=3)
        self.grup_degis_spinbox.grid(row=4, column=1, padx=5, pady=5, sticky="w")

        self.grup_degistir_button = tk.Button(self.ayar_frame, text="Grubu Değiştir", command=self.grup_degistir,
                                              fg="white",
                                              bg="blue")
        self.grup_degistir_button.grid(row=4, column=2, padx=5, pady=5, sticky="w")

        # İzin Tarih Aralığı Seçimi
        self.izin_baslangic_label = tk.Label(self.ayar_frame, text="İzin Başlangıç Tarihi:")
        self.izin_baslangic_label.grid(row=5, column=0, padx=5, pady=5, sticky="w")

        self.izin_baslangic_entry = DateEntry(self.ayar_frame, width=12, background='darkblue',
                                              foreground='white', borderwidth=2, year=datetime.now().year)
        self.izin_baslangic_entry.grid(row=5, column=1, padx=5, pady=5, sticky="w")

        self.izin_bitis_label = tk.Label(self.ayar_frame, text="İzin Bitiş Tarihi:")
        self.izin_bitis_label.grid(row=6, column=0, padx=5, pady=5, sticky="w")

        self.izin_bitis_entry = DateEntry(self.ayar_frame, width=12, background='darkblue',
                                          foreground='white', borderwidth=2, year=datetime.now().year)
        self.izin_bitis_entry.grid(row=6, column=1, padx=5, pady=5, sticky="w")

        self.izin_ekle_button = tk.Button(self.ayar_frame, text="İzin Tarihi Ekle", command=self.izin_tarihi_ekle,
                                          fg="white",
                                          bg="orange")
        self.izin_ekle_button.grid(row=5, column=2, padx=5, pady=5, sticky="w")

        self.izin_sil_button = tk.Button(self.ayar_frame, text="İzin Tarihi Sil", command=self.izin_tarihi_sil,
                                         fg="white",
                                         bg="red")
        self.izin_sil_button.grid(row=6, column=2, padx=5, pady=5, sticky="w")

        self.nobet_frame = tk.Frame(self)
        self.nobet_frame.grid(row=9, column=0, padx=5, pady=5, sticky="w")

        # Nöbet Arası Minimum Gün Sayısı
        self.min_gun_araligi_label = tk.Label(self.nobet_frame, text="Nöbetler Arası Minimum Gün Sayısı:")
        self.min_gun_araligi_label.grid(row=9, column=0, padx=5, pady=5, sticky="w")

        self.min_gun_araligi_var = tk.IntVar(value=6)  # Varsayılan değer 6 gün
        self.min_gun_araligi_spinbox = tk.Spinbox(self.nobet_frame, from_=1, to=30,
                                                  textvariable=self.min_gun_araligi_var, width=3)
        self.min_gun_araligi_spinbox.grid(row=9, column=1, padx=5, pady=5, sticky="w")

        # Tarih seçimi
        self.baslangic_tarihi_label = tk.Label(self.nobet_frame, text="Başlangıç Tarihi (YYYY-AA-GG):")
        self.baslangic_tarihi_label.grid(row=10, column=0, padx=5, pady=5, sticky="w")

        # Varsayılan olarak yarının tarihi
        yarin = datetime.now() + timedelta(days=1)
        self.baslangic_tarihi_entry = tk.Entry(self.nobet_frame)
        self.baslangic_tarihi_entry.insert(0, yarin.strftime('%Y-%m-%d'))
        self.baslangic_tarihi_entry.grid(row=10, column=1, padx=5, pady=5, sticky="w")

        # Nöbet sayısı seçimi
        self.nobet_sayisi_label = tk.Label(self.nobet_frame, text="Her Personel için Nöbet Sayısı:")
        self.nobet_sayisi_label.grid(row=11, column=0, padx=5, pady=5, sticky="w")

        # Varsayılan olarak nöbet sayısı
        self.nobet_sayisi_entry = tk.Entry(self.nobet_frame)
        self.nobet_sayisi_entry.insert(0, '2')
        self.nobet_sayisi_entry.grid(row=11, column=1, padx=5, pady=5, sticky="w")

        # Nöbet Çizelgesi Oluştur
        self.olustur_button = tk.Button(self.nobet_frame, text="Nöbet Çizelgesi Oluştur", command=self.olustur_cizelge,
                                        fg="white",
                                        bg="green")
        self.olustur_button.grid(row=12, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")

        # Personel Listesini Arayüze Yükle
        self.personel_listesini_goster()

    # Placeholder işlevselliği için gerekli fonksiyonlar
    def on_entry_click(self, event):
        if self.personel_entry.get() == 'İsim Giriniz':
            self.personel_entry.delete(0, "end")  # Placeholder metnini sil
            self.personel_entry.config(fg='black')

    def on_focusout(self, event):
        if self.personel_entry.get() == '':
            self.personel_entry.insert(0, 'İsim Giriniz')
            self.personel_entry.config(fg='grey')

    def ekle_personel(self):
        personel = self.personel_entry.get()
        grup = self.grup_var.get()
        if personel and 1 <= grup <= 10:
            self.personel_listesi.append({"isim": personel, "grup": grup, "haftasonu_nobeti": True})
            self.personel_listesini_goster()  # Listeyi güncelle
            messagebox.showinfo("Başarılı", f"{personel} eklendi.")
        else:
            messagebox.showerror("Hata", "Lütfen geçerli bir isim ve grup numarası girin.")
        self.personel_entry.delete(0, tk.END)

    def cikar_personel(self):
        selected_item = self.personel_tree.selection()  # Seçili olan Treeview öğesini al
        if selected_item:
            values = self.personel_tree.item(selected_item, "values")  # Seçili öğenin değerlerini al
            personel_adı = values[0]  # İlk sütun (isim sütunu)

            # Personel listesinden ilgili kişiyi bulup silme
            self.personel_listesi = [personel for personel in self.personel_listesi if personel["isim"] != personel_adı]
            res = messagebox.askquestion('Personel Sil', 'Silmek İstediğinizden Emin Misiniz?')
            if res == 'yes':

                self.personel_tree.delete(selected_item)  # Seçili öğeyi Treeview'dan sil
                messagebox.showinfo("Başarılı", f"{personel_adı} çıkarıldı.")

            else:
                messagebox.showinfo("Silinmedi", f"{personel_adı} Silinmedi.")

        else:
            messagebox.showerror("Hata", "Lütfen tablodan bir personel seçin.")

    # Personel İsmini Düzenleme Fonksiyonu
    def isim_duzenle(self):
        selected_item = self.personel_tree.selection()  # Seçili olan Treeview öğesini al
        if selected_item:
            values = self.personel_tree.item(selected_item, "values")  # Seçili öğenin değerlerini al
            eski_isim = values[0]  # İlk sütun (isim sütunu)

            # Yeni isim girişi için bir pencere açalım
            yeni_isim = simpledialog.askstring("İsim Düzenle", f"{eski_isim} için yeni ismi giriniz:")

            if yeni_isim:  # Yeni isim girildiyse
                # Personel listesinden ilgili kişiyi bul ve ismini değiştir
                for personel in self.personel_listesi:
                    if personel["isim"] == eski_isim:
                        personel["isim"] = yeni_isim
                        break

                # Treeview'daki veriyi güncelle
                self.personel_tree.item(selected_item, values=(yeni_isim, personel["grup"], values[2], values[3]))

                messagebox.showinfo("Başarılı", f"{eski_isim} ismi {yeni_isim} olarak değiştirildi.")
        else:
            messagebox.showerror("Hata", "Lütfen tablodan bir personel seçin.")

    def haftasonu_toggle(self):
        selected_item = self.personel_tree.selection()  # Seçili olan Treeview öğesini al
        if selected_item:
            values = self.personel_tree.item(selected_item, "values")  # Seçili öğenin değerlerini al
            personel_adı = values[0]  # İlk sütun (isim sütunu)

            # Personel listesinden ilgili kişiyi bul ve hafta sonu durumunu değiştir
            for personel in self.personel_listesi:
                if personel["isim"] == personel_adı:
                    personel["haftasonu_nobeti"] = not personel["haftasonu_nobeti"]
                    break

            # Treeview'daki veriyi güncelle
            haftasonu_durum = "Var" if personel["haftasonu_nobeti"] else "Yok"
            self.personel_tree.item(selected_item,
                                    values=(personel["isim"], personel["grup"], haftasonu_durum, values[3]))

            messagebox.showinfo("Başarılı", f"{personel_adı} için hafta sonu nöbet durumu değiştirildi.")
        else:
            messagebox.showerror("Hata", "Lütfen tablodan bir personel seçin.")

    def grup_degistir(self):
        selected_item = self.personel_tree.selection()  # Seçili olan Treeview öğesini al
        if selected_item:
            values = self.personel_tree.item(selected_item, "values")  # Seçili öğenin değerlerini al
            personel_adı = values[0]  # İlk sütun (isim sütunu)
            yeni_grup = int(self.grup_degis_spinbox.get())  # Kullanıcının girdiği yeni grup numarasını al

            # Personel listesinden ilgili kişiyi bul ve grubunu değiştir
            for personel in self.personel_listesi:
                if personel["isim"] == personel_adı:
                    personel["grup"] = yeni_grup
                    break

            # Treeview'daki veriyi güncelle
            self.personel_tree.item(selected_item, values=(personel["isim"], personel["grup"], values[2], values[3]))

            messagebox.showinfo("Başarılı", f"{personel_adı} için grup {yeni_grup} olarak değiştirildi.")
        else:
            messagebox.showerror("Hata", "Lütfen tablodan bir personel seçin.")

    def izin_tarihi_ekle(self):
        selected_item = self.personel_tree.selection()  # Seçili olan Treeview öğesini al
        if selected_item:
            values = self.personel_tree.item(selected_item, "values")  # Seçili öğenin değerlerini al
            personel_adı = values[0]  # İlk sütun (isim sütunu)
            izin_baslangic = self.izin_baslangic_entry.get_date().strftime('%Y-%m-%d')
            izin_bitis = self.izin_bitis_entry.get_date().strftime('%Y-%m-%d')

            # Personel listesinden ilgili kişiyi bul ve izin tarihlerini ekle
            for personel in self.personel_listesi:
                if personel["isim"] == personel_adı:
                    personel["izin_baslangic"] = izin_baslangic
                    personel["izin_bitis"] = izin_bitis
                    break

            # Treeview'daki veriyi güncelle
            izin_durum = f"{izin_baslangic} - {izin_bitis}"
            self.personel_tree.item(selected_item, values=(personel["isim"], personel["grup"], values[2], izin_durum))

            messagebox.showinfo("Başarılı", f"{personel_adı} için izin tarihleri eklendi.")
        else:
            messagebox.showerror("Hata", "Lütfen tablodan bir personel seçin.")

    def izin_tarihi_sil(self):
        selected_item = self.personel_tree.selection()  # Seçili olan Treeview öğesini al
        if selected_item:
            values = self.personel_tree.item(selected_item, "values")  # Seçili öğenin değerlerini al
            personel_adı = values[0]  # İlk sütun (isim sütunu)

            # Personel listesinden ilgili kişiyi bul ve izin tarihlerini sil
            for personel in self.personel_listesi:
                if personel["isim"] == personel_adı:
                    personel["izin_baslangic"] = None
                    personel["izin_bitis"] = None
                    break

            # Treeview'daki veriyi güncelle
            izin_durum = "Yok"
            self.personel_tree.item(selected_item, values=(personel["isim"], personel["grup"], values[2], izin_durum))

            messagebox.showinfo("Başarılı", f"{personel_adı} için izin tarihleri silindi.")
        else:
            messagebox.showerror("Hata", "Lütfen tablodan bir personel seçin.")

    def guncelle_personel_listesi(self):
        personel_kaydet(self.conn, self.personel_listesi)
        messagebox.showinfo("Başarılı", "Personel listesi güncellendi ve kaydedildi.")

    # Treeview içine veri eklemek için bir fonksiyon
    def personel_listesini_goster(self):
        # Mevcut verileri temizleyelim
        for row in self.personel_tree.get_children():
            self.personel_tree.delete(row)

        # Verileri Treeview'a ekleyelim
        for personel in self.personel_listesi:
            haftasonu_durum = "Var" if personel["haftasonu_nobeti"] else "Yok"
            izin_durum = f"{personel.get('izin_baslangic', 'Yok')} - {personel.get('izin_bitis', 'Yok')}"
            self.personel_tree.insert("", "end",
                                      values=(personel["isim"], personel["grup"], haftasonu_durum, izin_durum))

    def olustur_cizelge(self):
        baslangic_tarihi = self.baslangic_tarihi_entry.get()
        try:
            datetime.strptime(baslangic_tarihi, '%Y-%m-%d')
        except ValueError:
            messagebox.showerror("Hata", "Geçersiz tarih formatı, lütfen YYYY-AA-GG formatında girin.")
            return

        try:
            max_nobet_sayisi = int(self.nobet_sayisi_entry.get())
        except ValueError:
            messagebox.showerror("Hata", "Nöbet sayısı için geçerli bir sayı girin.")
            return

        min_gun_araligi = self.min_gun_araligi_var.get()

        # Nöbet Çizelgesini Oluştur
        tarih_araligi = tarih_araligi_olustur(baslangic_tarihi, len(self.personel_listesi))
        nobet_cizelgesi = nöbet_çizelgesi_oluştur(self.personel_listesi, self.izinli_listesi, tarih_araligi,
                                                  max_nobet_sayisi, min_gun_araligi)

        # Sonucu Dosyaya Yaz
        excel_yaz(nobet_cizelgesi, 'nobet_cizelgesi.xlsx')
        messagebox.showinfo("Başarılı", "Nöbet çizelgesi oluşturuldu ve 'nobet_cizelgesi.xlsx' dosyasına kaydedildi.")


if __name__ == "__main__":
    app = NobetApp()
    app.mainloop()
