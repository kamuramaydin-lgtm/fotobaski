from tkinter import *
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageEnhance
import platform, sys, os, subprocess

# Platform modülleri
HAS_WIN32 = False
if platform.system() == "Windows":
    try:
        import win32print, win32ui, win32con
        from PIL import ImageWin
        HAS_WIN32 = True
    except Exception:
        HAS_WIN32 = False
elif platform.system() == "Linux":
    try:
        import cups
    except Exception:
        cups = None

def get_default_printer():
    sysname = platform.system()
    if sysname == "Windows" and HAS_WIN32:
        try: return win32print.GetDefaultPrinter()
        except Exception: return None
    if sysname == "Darwin":
        try:
            out = subprocess.check_output(["lpstat","-d"]).decode("utf-8")
            return (out.split(":")[-1].strip()) or None
        except Exception:
            return None
    if sysname == "Linux" and cups:
        try: return cups.Connection().getDefault()
        except Exception: return None
    return None


class VskBiometrikYuklePenceresi:
    def __init__(self, root, ebat="10x15", yazici=None, mod="normal"):
        self.pencere = Toplevel(root if root else Tk())
        self.pencere.attributes('-topmost', True)
        self.pencere.title("VSK / Biometrik Fotoğraf Düzenleme")
        self.pencere.geometry("1200x760")
        self.pencere.configure(bg="#333333")
        self.pencere.resizable(False, False)

        self.ebat = ebat
        self.yazici = yazici or get_default_printer()
        self.mod = mod
        self.canvas_boyut = (390, 250)

        self.sayfa = 0
        self.gorseller = []
        self.degerler = []           # [sarı, kırmızı, cyan, parlaklık, adet]
        self.canvaslar = []
        self.fotograf_imgler = []

        Label(self.pencere, text="VSK / BİOMETRİK YAZDIR - GÖNDER",
              font=("Segoe UI", 24, "bold"), bg="#333333", fg="white").pack(pady=10)

        Button(self.pencere, text="Fotoğraf Seç", command=self.foto_yukle,
               font=("Segoe UI", 12), bg="#4CAF50", fg="white",
               relief=FLAT, padx=20, pady=10).pack(pady=10)

        self.gorsel_cerceve = Frame(self.pencere, bg="#333333"); self.gorsel_cerceve.pack(pady=10)
        self.alt_butonlar = Frame(self.pencere, bg="#333333"); self.alt_butonlar.pack(pady=10)

        Button(self.alt_butonlar, text="⬅ Geri", command=self.geri,
               font=("Segoe UI", 11), width=10, bg="#555", fg="white", relief=FLAT).pack(side=LEFT, padx=15)
        Button(self.alt_butonlar, text="İleri ➡", command=self.ileri,
               font=("Segoe UI", 11), width=10, bg="#555", fg="white", relief=FLAT).pack(side=LEFT, padx=15)

        send = Frame(self.alt_butonlar, bg="#555", padx=10, pady=10); send.pack(side=LEFT, padx=15, pady=10)
        Button(send, text="Gönder", command=self.gonder,
               font=("Segoe UI", 12), bg="#4CAF50", fg="white",
               relief=FLAT, padx=10, pady=5).pack(side=LEFT)
        Label(send, text="🖨", font=("Segoe UI", 16), bg="#555", fg="white").pack(side=LEFT, padx=5)

        if len(sys.argv) > 1:
            self._load_images(sys.argv[1:])
        else:
            self.foto_yukle()

    def _load_images(self, files):
        self.gorseller=[]
        for d in files:
            if os.path.isfile(d) and d.lower().endswith(('.jpg','.jpeg','.png')):
                try: self.gorseller.append(Image.open(d).convert("RGB"))
                except Exception as e: messagebox.showerror("Hata", f"{d} yüklenemedi: {e}")
        if not self.gorseller: return
        self.degerler = [[0,0,0,1.0,1] for _ in self.gorseller]
        self.fotograf_imgler = [None]*len(self.gorseller)
        self.sayfa=0
        self.gorsel_goster()

    def foto_yukle(self):
        files = filedialog.askopenfilenames(parent=self.pencere, title="Fotoğraf Seçiniz",
                                            filetypes=[("Resim Dosyaları","*.jpg *.jpeg *.png")])
        if not files: return
        self._load_images(files)

    def get_islenmis_gorsel(self, ix):
        img = self.gorseller[ix].copy()
        sari,kirmizi,cyan,parlak,_ = self.degerler[ix]
        r,g,b = img.split()
        r = r.point(lambda i: min(255,max(0,i+(sari+kirmizi)*3)))
        g = g.point(lambda i: min(255,max(0,i+(sari-kirmizi)*3)))
        b = b.point(lambda i: min(255,max(0,i+(cyan-sari)*3)))
        img = Image.merge("RGB",(r,g,b))
        img = ImageEnhance.Brightness(img).enhance(parlak)
        if img.height>img.width:
            img = img.rotate(90, expand=True)
        return img

    def hazirla_tuval(self, img):
        # 13x18 örnek şablon: 2x2 yerleşim
        tuval = Image.new("RGB", (1772,1181), "white")
        w,h = img.size
        mx = (tuval.width - 2*w)//3
        my = (tuval.height - 2*h)//3
        for dx in [0,1]:
            for dy in [0,1]:
                x = mx*(1+dx) + w*dx
                y = my*(1+dy) + h*dy
                bordered = Image.new("RGB",(w+4,h+4), "black")
                bordered.paste(img,(2,2))
                tuval.paste(bordered,(x-2,y-2))
        return tuval

    # ---- Yazdırma ----
    def yazdir(self, img):
        if not img: return
        if not self.yazici:
            messagebox.showwarning("Uyarı","Yazıcı bulunamadı!"); return
        try:
            sysname=platform.system()
            if sysname=="Windows" and HAS_WIN32: self._print_windows(img)
            elif sysname=="Darwin": self._print_mac(img)
            elif sysname=="Linux" and cups: self._print_linux(img)
            else: messagebox.showwarning("Uyarı","Bu platformda yazdırma yapılandırılmadı.")
        except Exception as e:
            messagebox.showerror("Yazdırma Hatası", f"Hata: {e}")

    def _get_media_mac(self):
        return {"10x15":"10x15cm","13x18":"13x18cm","15x21":"15x21cm","A4":"iso-a4"}.get(self.ebat,"iso-a4")

    def _print_mac(self, image_to_print):
        temp="/tmp/print_temp.jpg"
        image_to_print.save(temp,"JPEG",quality=95)
        cmd=["lp","-o","fit-to-page","-o",f"media={self._get_media_mac()}"]
        if self.yazici: cmd+=["-d", self.yazici]
        cmd.append(temp)
        subprocess.run(cmd, check=True)
        try: os.unlink(temp)
        except Exception: pass

    def _print_windows(self, image_to_print):
        printer = self.yazici
        h = win32print.OpenPrinter(printer)
        dc = win32ui.CreateDC(); dc.CreatePrinterDC(printer)
        dc.StartDoc("VSK BASKI"); dc.StartPage()
        dpi_x = dc.GetDeviceCaps(win32con.LOGPIXELSX)
        dpi_y = dc.GetDeviceCaps(win32con.LOGPIXELSY)
        # A4 varsayımı; istersen ebatla eşleştir
        tw,th = (21/2.54, 29.7/2.54)
        pw,ph = int(tw*dpi_x), int(th*dpi_y)

        img=image_to_print; iw,ih=img.size
        scale=min(pw/iw, ph/ih)
        fw,fh=int(iw*scale), int(ih*scale)
        img=img.resize((fw,fh), Image.LANCZOS)
        page_w = dc.GetDeviceCaps(win32con.HORZRES)
        page_h = dc.GetDeviceCaps(win32con.VERTRES)
        x=(page_w-fw)//2; y=(page_h-fh)//2
        ImageWin.Dib(img).draw(dc.GetHandleOutput(), (x,y,x+fw,y+fh))
        dc.EndPage(); dc.EndDoc(); dc.DeleteDC(); win32print.ClosePrinter(h)

    def _print_linux(self, image_to_print):
        temp="/tmp/print_temp.jpg"
        image_to_print.save(temp,"JPEG",quality=95)
        conn=cups.Connection()
        printer=self.yazici or conn.getDefault()
        options={"fit-to-page":"True","media":"A4","scaling":"100"}
        conn.printFile(printer, temp, "VSK BASKI", options)
        try: os.unlink(temp)
        except Exception: pass

    # ---- Arayüz ----
    def gorsel_goster(self):
        for w in self.gorsel_cerceve.winfo_children(): w.destroy()
        self.canvaslar=[]
        bas=self.sayfa*6
        for i in range(6):
            ix=bas+i
            if ix>=len(self.gorseller): continue
            f=Frame(self.gorsel_cerceve, bg="#222", highlightbackground="#666", highlightthickness=1)
            f.grid(row=i//3, column=i%3, padx=8, pady=8)
            c=Canvas(f, width=self.canvas_boyut[0], height=self.canvas_boyut[1],
                     bg="black", highlightthickness=0); c.pack()
            self.canvaslar.append(c)
            self.render(ix)

    def render(self, ix):
        loc = ix - self.sayfa*6
        if loc>=len(self.canvaslar): return
        c=self.canvaslar[loc]; c.delete("all")
        img=self.get_islenmis_gorsel(ix)
        iw,ih=img.size
        cw,ch=self.canvas_boyut
        scale=min(cw/iw, ch/ih)
        img=img.resize((int(iw*scale), int(ih*scale)), Image.LANCZOS)
        self.fotograf_imgler[ix]=ImageTk.PhotoImage(img)
        c.image=self.fotograf_imgler[ix]
        c.create_image(cw//2, ch//2, image=self.fotograf_imgler[ix], anchor=CENTER)

    def ileri(self):
        if (self.sayfa+1)*6 < len(self.gorseller):
            self.sayfa+=1; self.gorsel_goster()

    def geri(self):
        if self.sayfa>0:
            self.sayfa-=1; self.gorsel_goster()

    def gonder(self):
        bas=self.sayfa*6
        for ix in range(bas, min(bas+6, len(self.gorseller))):
            if self.degerler[ix][4] <= 0: continue
            img=self.get_islenmis_gorsel(ix)
            tuval=self.hazirla_tuval(img)
            self.yazdir(tuval)
        messagebox.showinfo("Tamam","Sayfa yazdırma gönderildi.")


if __name__ == "__main__":
    root = Tk(); root.withdraw()
    VskBiometrikYuklePenceresi(root, ebat="10x15", yazici=get_default_printer())
    root.mainloop()
