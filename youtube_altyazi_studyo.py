import re
import time
from tkinter import filedialog, messagebox
import customtkinter as ctk
from deep_translator import GoogleTranslator
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import SRTFormatter, TextFormatter

# Görünüm Ayarları
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class AltyaziSarmalayici:
    """Sözlük verisini Formatter'ların hem eski hem yeni sürümüyle uyumlu hale getirir."""

    def __init__(self, satirlar):
        self.satirlar = satirlar

    def __iter__(self):
        for s in self.satirlar:
            yield s

    def to_raw_data(self):
        return self.satirlar


class AltyaziUygulamasi(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("YouTube Altyazı Stüdyosu")
        self.geometry("750x600")
        self.minsize(650, 500)

        # Önbellek (Aynı videoyu tekrar tekrar indirmemek ve çevirmemek için)
        self.video_id = None
        self.orijinal_satirlar = None
        self.orijinal_dil_kodu = None
        self.guncel_satirlar = None
        self.ceviri_onbellek = {}  # Çevrilen dilleri hafızada tutar

        self.arayuzu_olustur()

    def arayuzu_olustur(self):
        # 1. Başlık
        self.baslik = ctk.CTkLabel(
            self,
            text="🎬 YouTube Altyazı İndirici & Çevirici",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        self.baslik.pack(pady=(20, 10))

        # 2. Üst Panel (URL Girişi)
        self.ust_cerceve = ctk.CTkFrame(self)
        self.ust_cerceve.pack(pady=10, padx=20, fill="x")

        self.url_giris = ctk.CTkEntry(
            self.ust_cerceve,
            placeholder_text="YouTube video linkini buraya yapıştırın...",
            height=40,
        )
        self.url_giris.pack(side="left", padx=(10, 10), pady=10, fill="x", expand=True)

        self.getir_buton = ctk.CTkButton(
            self.ust_cerceve,
            text="Altyazıyı Getir",
            height=40,
            font=ctk.CTkFont(weight="bold"),
            command=self.altyazi_getir,
        )
        self.getir_buton.pack(side="right", padx=(0, 10), pady=10)

        # 3. Orta Panel (Dil ve Format Seçenekleri)
        self.ayar_cerceve = ctk.CTkFrame(self)
        self.ayar_cerceve.pack(pady=5, padx=20, fill="x")

        self.dil_etiket = ctk.CTkLabel(self.ayar_cerceve, text="Hedef Dil / Çeviri:")
        self.dil_etiket.pack(side="left", padx=(15, 5), pady=10)

        self.dil_secim = ctk.CTkOptionMenu(
            self.ayar_cerceve,
            values=[
                "Türkçe (tr)",
                "İngilizce (en)",
                "Almanca (de)",
                "Fransızca (fr)",
                "İspanyolca (es)",
                "Orijinal Dil",
            ],
            command=self.dil_degisti,
        )
        self.dil_secim.set("Türkçe (tr)")
        self.dil_secim.pack(side="left", padx=5, pady=10)

        self.format_etiket = ctk.CTkLabel(self.ayar_cerceve, text="Önizleme Formatı:")
        self.format_etiket.pack(side="left", padx=(25, 5), pady=10)

        self.format_secim = ctk.CTkSegmentedButton(
            self.ayar_cerceve,
            values=["Düz Metin (.txt)", "Zaman Damgalı (.srt)"],
            command=self.onizleme_guncelle,
        )
        self.format_secim.set("Düz Metin (.txt)")
        self.format_secim.pack(side="left", padx=5, pady=10)

        # 4. Metin Önizleme Alanı
        self.metin_kutusu = ctk.CTkTextbox(self, font=ctk.CTkFont(size=13), wrap="word")
        self.metin_kutusu.pack(pady=10, padx=20, fill="both", expand=True)
        self.metin_kutusu.insert(
            "0.0",
            "Altyazı önizlemesi burada görünecek...\n\n1. Yukarıya bir YouTube linki yapıştırın.\n2. İstediğiniz dili seçin.\n3. 'Altyazıyı Getir' butonuna tıklayın.",
        )

        # 5. Alt Panel (Kaydetme ve Durum)
        self.alt_cerceve = ctk.CTkFrame(self, fg_color="transparent")
        self.alt_cerceve.pack(pady=(5, 15), padx=20, fill="x")

        self.durum_etiket = ctk.CTkLabel(
            self.alt_cerceve, text="Hazır.", text_color="gray"
        )
        self.durum_etiket.pack(side="left")

        self.kaydet_buton = ctk.CTkButton(
            self.alt_cerceve,
            text="💾 Dosya Olarak Kaydet",
            fg_color="#28a745",
            hover_color="#218838",
            state="disabled",
            command=self.dosya_kaydet,
        )
        self.kaydet_buton.pack(side="right")

    def video_id_ayikla(self, url):
        """Hem normal linkleri hem de yarım/kısaltılmış linkleri çözer."""
        url = url.strip()
        pattern = r"(?:v=|\/|^)([0-9A-Za-z_-]{11})(?:[&?\/]|$)"
        eslesme = re.search(pattern, url)
        return eslesme.group(1) if eslesme else url[:11]

    def dil_kodunu_al(self):
        secim = self.dil_secim.get()
        harita = {
            "Türkçe (tr)": "tr",
            "İngilizce (en)": "en",
            "Almanca (de)": "de",
            "Fransızca (fr)": "fr",
            "İspanyolca (es)": "es",
            "Orijinal Dil": "orijinal",
        }
        return harita.get(secim, "tr")

    def ham_listeye_cevir(self, fetched_obj):
        if hasattr(fetched_obj, "to_raw_data"):
            return fetched_obj.to_raw_data()
        satirlar = []
        for item in fetched_obj:
            if isinstance(item, dict):
                satirlar.append(item.copy())
            else:
                satirlar.append(
                    {
                        "text": getattr(item, "text", ""),
                        "start": getattr(item, "start", 0.0),
                        "duration": getattr(item, "duration", 0.0),
                    }
                )
        return satirlar

    def google_api_ile_cevir(self, metin, hedef_dil):
        """1. Aşama: Doğrudan resmi Google Mobil API üzerinden engelsiz çeviri yapar."""
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "auto",
            "tl": hedef_dil,
            "dt": "t",
            "q": metin,
        }
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        yanit = requests.get(url, params=params, headers=headers, timeout=15)
        yanit.raise_for_status()
        veri = yanit.json()
        return "".join([parca[0] for parca in veri[0] if parca[0]])

    def paketi_guvenli_cevir(self, birlesik_metin, hedef_dil):
        """Önce doğrudan API'yi dener, hata olursa bekleyip yedek motoru çalıştırır."""
        try:
            return self.google_api_ile_cevir(birlesik_metin, hedef_dil)
        except Exception:
            time.sleep(1.0)
            return GoogleTranslator(source="auto", target=hedef_dil).translate(
                birlesik_metin
            )

    def metinleri_cevir(self, satirlar, hedef_dil):
        """Altyazı satırlarını hız sınırına takılmadan paketler halinde çevirir."""
        yeni_satirlar = [s.copy() for s in satirlar]

        grup = []
        grup_indeksleri = []
        mevcut_uzunluk = 0

        for idx, s in enumerate(yeni_satirlar):
            temiz_metin = s["text"].replace("\n", " ").strip()
            if not temiz_metin:
                continue

            # 2500 karakterlik güvenli paket boyutu
            if mevcut_uzunluk + len(temiz_metin) > 2500 and grup:
                birlesik = "\n".join(grup)
                cevrilmis_metin = self.paketi_guvenli_cevir(birlesik, hedef_dil)
                cevrilmis_liste = cevrilmis_metin.split("\n")

                for i, c_metin in zip(grup_indeksleri, cevrilmis_liste):
                    yeni_satirlar[i]["text"] = c_metin.strip()

                grup = []
                grup_indeksleri = []
                mevcut_uzunluk = 0
                time.sleep(0.4)  # Rate-limit (hız sınırı) koruması

            grup.append(temiz_metin)
            grup_indeksleri.append(idx)
            mevcut_uzunluk += len(temiz_metin) + 1

        if grup:
            birlesik = "\n".join(grup)
            cevrilmis_metin = self.paketi_guvenli_cevir(birlesik, hedef_dil)
            cevrilmis_liste = cevrilmis_metin.split("\n")
            for i, c_metin in zip(grup_indeksleri, cevrilmis_liste):
                yeni_satirlar[i]["text"] = c_metin.strip()

        return yeni_satirlar

    def dil_degisti(self, *args):
        if self.orijinal_satirlar:
            self.hedef_dili_uygula()

    def altyazi_getir(self):
        url = self.url_giris.get().strip()
        if not url:
            messagebox.showwarning("Uyarı", "Lütfen bir YouTube linki girin!")
            return

        yeni_id = self.video_id_ayikla(url)

        # Yeni bir video girildiyse YouTube'dan 1 kere çek ve önbelleği sıfırla
        if yeni_id != self.video_id or not self.orijinal_satirlar:
            self.video_id = yeni_id
            self.ceviri_onbellek = {}
            self.durum_etiket.configure(
                text="YouTube'dan orijinal altyazı alınıyor...",
                text_color="#ffc107",
            )
            self.update()

            try:
                ytt_api = YouTubeTranscriptApi()
                if hasattr(ytt_api, "list"):
                    transcript_list = ytt_api.list(self.video_id)
                else:
                    transcript_list = YouTubeTranscriptApi.list_transcripts(
                        self.video_id
                    )

                first_transcript = next(iter(transcript_list))
                fetched = first_transcript.fetch()

                self.orijinal_satirlar = self.ham_listeye_cevir(fetched)
                self.orijinal_dil_kodu = first_transcript.language_code.split("-")[
                    0
                ].lower()

            except Exception as e:
                self.orijinal_satirlar = None
                self.kaydet_buton.configure(state="disabled")
                self.durum_etiket.configure(
                    text="Hata: Altyazı alınamadı.", text_color="#dc3545"
                )
                messagebox.showerror(
                    "Hata", f"Altyazı çekilemedi.\n\nTeknik Detay: {str(e)}"
                )
                return

        self.hedef_dili_uygula()

    def hedef_dili_uygula(self):
        hedef_dil = self.dil_kodunu_al()

        try:
            if hedef_dil == "orijinal" or hedef_dil == self.orijinal_dil_kodu:
                self.guncel_satirlar = [s.copy() for s in self.orijinal_satirlar]
                bilgi_notu = (
                    f"Orijinal altyazı gösteriliyor ({self.orijinal_dil_kodu})."
                )
            elif hedef_dil in self.ceviri_onbellek:
                # Daha önce bu dile çevrildiyse hiç bekletmeden hafızadan getir
                self.guncel_satirlar = [
                    s.copy() for s in self.ceviri_onbellek[hedef_dil]
                ]
                bilgi_notu = f"'{hedef_dil}' çevirisi önbellekten yüklendi."
            else:
                self.durum_etiket.configure(
                    text=f"'{hedef_dil}' diline çevriliyor, lütfen bekleyin...",
                    text_color="#ffc107",
                )
                self.update()
                cevrilen = self.metinleri_cevir(self.orijinal_satirlar, hedef_dil)
                self.ceviri_onbellek[hedef_dil] = cevrilen
                self.guncel_satirlar = [s.copy() for s in cevrilen]
                bilgi_notu = f"'{self.orijinal_dil_kodu}' dilinden '{hedef_dil}' diline başarıyla çevrildi."

            self.onizleme_guncelle()
            self.kaydet_buton.configure(state="normal")
            self.durum_etiket.configure(
                text=f"Başarılı! {bilgi_notu}", text_color="#28a745"
            )

        except Exception as e:
            self.durum_etiket.configure(
                text="Çeviri sırasında hata oluştu.", text_color="#dc3545"
            )
            messagebox.showerror("Çeviri Hatası", f"Çeviri yapılamadı:\n{str(e)}")

    def formatli_metin_uret(self):
        if not self.guncel_satirlar:
            return ""

        secili_format = self.format_secim.get()
        sarmalanmis_veri = AltyaziSarmalayici(self.guncel_satirlar)

        if secili_format == "Düz Metin (.txt)":
            try:
                return TextFormatter().format_transcript(sarmalanmis_veri)
            except Exception:
                return "\n".join(s["text"] for s in self.guncel_satirlar)
        else:
            try:
                return SRTFormatter().format_transcript(sarmalanmis_veri)
            except Exception:
                srt_cikti = []
                for idx, s in enumerate(self.guncel_satirlar, 1):
                    basla = self.saniyeyi_srt_yap(s["start"])
                    bitis = self.saniyeyi_srt_yap(s["start"] + s.get("duration", 2.0))
                    srt_cikti.append(f"{idx}\n{basla} --> {bitis}\n{s['text']}\n")
                return "\n".join(srt_cikti)

    def saniyeyi_srt_yap(self, saniye):
        saat = int(saniye // 3600)
        dakika = int((saniye % 3600) // 60)
        sn = int(saniye % 60)
        ms = int((saniye - int(saniye)) * 1000)
        return f"{saat:02d}:{dakika:02d}:{sn:02d},{ms:03d}"

    def onizleme_guncelle(self, *args):
        if not self.guncel_satirlar:
            return

        metin = self.formatli_metin_uret()
        self.metin_kutusu.delete("0.0", "end")
        self.metin_kutusu.insert("0.0", metin)

    def dosya_kaydet(self):
        if not self.guncel_satirlar:
            return

        secili_format = self.format_secim.get()
        uzanti = ".txt" if secili_format == "Düz Metin (.txt)" else ".srt"
        dosya_tipi = (
            [("Metin Dosyası", "*.txt")]
            if uzanti == ".txt"
            else [("SRT Altyazı Dosyası", "*.srt")]
        )

        dosya_yolu = filedialog.asksaveasfilename(
            defaultextension=uzanti,
            initialfile=f"{self.video_id}_{self.dil_kodunu_al()}{uzanti}",
            filetypes=dosya_tipi,
            title="Altyazıyı Kaydet",
        )

        if dosya_yolu:
            metin = self.formatli_metin_uret()
            with open(dosya_yolu, "w", encoding="utf-8") as f:
                f.write(metin)
            messagebox.showinfo(
                "Başarılı", f"Dosya başarıyla kaydedildi:\n{dosya_yolu}"
            )


if __name__ == "__main__":
    app = AltyaziUygulamasi()
    app.mainloop()
