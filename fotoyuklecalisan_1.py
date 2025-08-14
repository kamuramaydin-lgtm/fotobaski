import platform, os, sys, subprocess, struct, socket, time
from tkinter import *
from tkinter import filedialog, ttk, messagebox
from PIL import Image, ImageTk, ImageEnhance, ImageOps, ImageFilter

# ---- Platform opsiyonel modüller ----
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
        cups = None  # cups yoksa None

def get_default_printer():
    sysname = platform.system()
    if sysname == "Windows" and HAS_WIN32:
        try: return win32print.GetDefaultPrinter()
        except Exception: return None
    if sysname == "Darwin":
        try:
            out = subprocess.check_output(["lpstat", "-d"]).decode("utf-8")
            return (out.split(":")[-1].strip()) or None
        except Exception:
            return None
    if sysname == "Linux" and cups:
        try: return cups.Connection().getDefault()
        except Exception: return None
    return None


class FotoYuklemePenceresi:
    def __init__(self, root, ebat="10x15", yazici=None, mod="normal"):
        self.pencere = Toplevel(root if root else Tk())
        self.pencere.attributes('-topmost', True)
        self.pencere.title("Fotoğraf Düzenleme ve Gönderme")
        self.pencere.configure(bg="#333333")
        self.pencere.resizable(False, False)

        # Ekran & tuval ölçeği
        ekw, ekh = self.pencere.winfo_screenwidth(), self.pencere.winfo_screenheight()
        scale = min(0.8, ekh / 900)

        # Tuval boyutu
        if ebat == "10x15":
            cw, ch = int(450*scale), int(300*scale)
        elif ebat == "13x18":
            cw, ch = int(415*scale), int(300*scale)
        elif ebat == "15x21":
            cw, ch = int(420*scale), int(300*scale)
        elif ebat == "A4":
            cw, ch = int(424*scale), int(300*scale)
        else:
            cw, ch = int(300*scale), int(300*scale)
        self.canvas_boyut = (cw, ch)

        pw = min(ekw, int((cw*3 + 16*2) * 1.08))
        ph = int(ekh*0.85)
        self.pencere.geometry(f"{pw}x{ph}")

        # Durum
        self.ebat = ebat
        self.yazici = yazici or get_default_printer()
        self.mod = mod
        self.zoom_hassasiyet = 0.02

        # Çalışma dizileri
        self.sayfa = 0
        self.gorseller = []
        self.rotated_images = []
        self.degerler = []            # [sarı, kırmızı, cyan, parlaklık, adet, netlik]
        self.zoom_oranlari = []
        self.pan_koordinatlari = []
        self.min_zoom_oranlari = []
        self.pan_sinirlari = []
        self.pan_baslangic = []
        self.fotograf_imgler = []
        self.renk_kutulari = []
        self.adet_etiketleri = []
        self.canvaslar = []

        # Üst başlık
        Label(self.pencere, text="FOTOĞRAF DÜZENLEME ve GÖNDERME",
              font=("Segoe UI", int(24*scale), "bold"), bg="#333333", fg="white").pack(pady=10)

        Button(self.pencere, text="📂 Fotoğraf Seç", command=self.foto_yukle,
               font=("Segoe UI", int(14*scale), "bold"), bg="#4CAF50", fg="white",
               relief=FLAT, padx=int(20*scale), pady=int(10*scale)).pack(pady=10)

        self.gorsel_cerceve = Frame(self.pencere, bg="#333333"); self.gorsel_cerceve.pack(pady=10)
        self.alt_butonlar = Frame(self.pencere, bg="#333333"); self.alt_butonlar.pack(pady=10, expand=True)

        self.geri_btn = Button(self.alt_butonlar, text="⬅ Geri", command=self.geri,
                               font=("Segoe UI", int(13*scale), "bold"),
                               width=14, bg="#555", fg="white", relief=FLAT)
        self.ileri_btn = Button(self.alt_butonlar, text="İleri ➡", command=self.ileri,
                                font=("Segoe UI", int(13*scale), "bold"),
                                width=14, bg="#555", fg="white", relief=FLAT)

        self.gonder_cerceve = Frame(self.alt_butonlar, bg="#555", padx=int(10*scale), pady=int(10*scale))
        self.gonder_cerceve.pack(side=LEFT, padx=15, pady=5)
        Button(self.gonder_cerceve, text="Sayfayı Yazdır", command=self.gonder,
               font=("Segoe UI", int(14*scale), "bold"),
               bg="#4CAF50", fg="white", relief=FLAT,
               padx=int(10*scale), pady=int(5*scale)).pack(side=LEFT)
        Label(self.gonder_cerceve, text="🖨", font=("Segoe UI", int(16*scale)),
              bg="#555", fg="white").pack(side=LEFT, padx=5)

        self.geri_btn.pack(side=LEFT, padx=15)
        Button(self.alt_butonlar, text="Hepsine Uygula", command=self.hepsine_uygula,
               font=("Segoe UI", int(13*scale), "bold"), width=18,
               bg="#888", fg="white", relief=FLAT).pack(side=LEFT, padx=15)
        self.ileri_btn.pack(side=LEFT, padx=15)

        # Argümanla foto gelmişse
        if len(sys.argv) > 1:
            self._load_images(sys.argv[1:])
        else:
            self.foto_yukle()

    # ----------------- Yardımcılar -----------------
    def _load_images(self, paths):
        self.gorseller, self.rotated_images = [], []
        for p in paths:
            if os.path.isfile(p) and p.lower().endswith(('.jpg','.jpeg','.png')):
                try:
                    img = Image.open(p).convert("RGB")
                    self.gorseller.append(img)
                    self.rotated_images.append(img.rotate(90, expand=True) if img.height>img.width else img.copy())
                except Exception as e:
                    messagebox.showerror("Hata", f"{p} yüklenemedi: {e}")

        if self.gorseller:
            n = len(self.gorseller)
            self.degerler = [[0,0,0,1.0,1,0] for _ in range(n)]
            self.zoom_oranlari = [1.0]*n
            self.pan_koordinatlari = [(0,0)]*n
            self.min_zoom_oranlari = [1.0]*n
            self.pan_sinirlari = [(0,0,0,0)]*n
            self.pan_baslangic = [(0,0)]*n
            self.fotograf_imgler = [None]*n
            self.sayfa = 0
            self.gorsel_goster()
        else:
            self.foto_yukle()

    def foto_yukle(self):
        files = filedialog.askopenfilenames(parent=self.pencere, title="Fotoğraf Seçiniz",
                                            filetypes=[("Resim Dosyaları","*.jpg *.jpeg *.png")])
        if not files: return
        if len(files)>50:
            messagebox.showwarning("Uyarı","En fazla 50 dosya seçebilirsiniz."); return
        self._load_images(files)

    # ----------------- Çizim -----------------
    def gorsel_goster(self):
        for w in self.gorsel_cerceve.winfo_children():
            w.destroy()
        self.renk_kutulari, self.adet_etiketleri, self.canvaslar = [], [], []
        bas = self.sayfa*6
        cw, ch = self.canvas_boyut

        for i in range(6):
            ix = bas+i
            if ix >= len(self.gorseller): continue
            frame = Frame(self.gorsel_cerceve, bg="#222", highlightbackground="#666", highlightthickness=1)
            frame.grid(row=i//3, column=i%3, padx=8, pady=8)

            canvas = Canvas(frame, width=cw, height=ch, bg="black", highlightthickness=0)
            canvas.pack()
            self.canvaslar.append(canvas)
            canvas.bind("<MouseWheel>", lambda e, k=ix: self.zoom_yap(e,k))
            canvas.bind("<ButtonPress-1>", lambda e, k=ix: self.basla_pan(e,k))
            canvas.bind("<B1-Motion>", lambda e, k=ix: self.pan_yap(e,k))
            canvas.config(cursor="fleur")

            panel = Frame(frame, bg="#444"); panel.pack(pady=4)
            renkler = ["yellow","red","cyan","gray","white"]
            kutular = []
            for j, renk in enumerate(renkler):
                holder = Frame(panel, bg="#555", padx=5, pady=5); holder.pack(side=LEFT, padx=2)
                lbl = Label(holder, bg=renk, fg="black", width=5, height=2, font=("Segoe UI",10,"bold")); lbl.pack()
                if j==4:
                    lbl.config(text=f"{self.degerler[ix][5]:+d}")
                    lbl.bind("<Button-1>", lambda e,k=ix: self.netlik_ayar(k,1))
                    lbl.bind("<Button-3>", lambda e,k=ix: self.netlik_ayar(k,-1))
                    s_holder = Frame(panel, bg="#555", padx=5, pady=5); s_holder.pack(side=LEFT, padx=2)
                    sifirla = Label(s_holder, text="Sıfırla", bg="#222", fg="white",
                                    width=6, height=2, font=("Segoe UI",10,"bold"), cursor="hand2")
                    sifirla.pack(); sifirla.bind("<Button-1>", lambda e,k=ix: self.zoom_pan_sifirla(k))
                else:
                    val = self.degerler[ix][j]
                    lbl.config(text=f"{val:+.0f}" if j!=3 else f"{val:.1f}")
                    lbl.bind("<Button-1>", lambda e,k=ix,p=j: self.renk_ayar(k,p,1))
                    lbl.bind("<Button-3>", lambda e,k=ix,p=j: self.renk_ayar(k,p,-1))
                kutular.append(lbl)
            self.renk_kutulari.append(kutular)

            adet_holder = Frame(panel, bg="#555", padx=5, pady=5); adet_holder.pack(side=LEFT, padx=2)
            adet_lbl = Label(adet_holder, text=str(self.degerler[ix][4]), bg="#444",
                             fg="white", width=5, height=2, font=("Segoe UI",10,"bold"))
            adet_lbl.pack()
            adet_lbl.bind("<Button-1>", lambda e,k=ix: self.adet_degistir(k,1))
            adet_lbl.bind("<Button-3>", lambda e,k=ix: self.adet_degistir(k,-1))
            self.adet_etiketleri.append(adet_lbl)

            self.render_gorsel(ix)

    def render_gorsel(self, ix):
        bas = self.sayfa*6
        loc = ix - bas
        if loc >= len(self.canvaslar): return
        canvas = self.canvaslar[loc]; canvas.delete("all")

        img = self.rotated_images[ix].copy()
        sari,kirmizi,cyan,ton,adet,netlik = self.degerler[ix]

        r,g,b = img.split()
        r = r.point(lambda i: min(255,max(0,i+(sari+kirmizi)*3)))
        g = g.point(lambda i: min(255,max(0,i+(sari-kirmizi)*3)))
        b = b.point(lambda i: min(255,max(0,i+(cyan-sari)*3)))
        img = Image.merge("RGB",(r,g,b))
        img = ImageEnhance.Brightness(img).enhance(ton)

        if netlik:
            factor = max(0.5,min(2.0,1.0+netlik/10.0))
            img = ImageEnhance.Sharpness(img).enhance(factor)

        cw,ch = self.canvas_boyut
        iw,ih = img.size
        min_zoom = max(cw/iw, ch/ih)
        if self.zoom_oranlari[ix]==1.0:
            self.zoom_oranlari[ix]=min_zoom
        else:
            self.zoom_oranlari[ix]=max(min_zoom, min(3.0,self.zoom_oranlari[ix]))

        zoom = self.zoom_oranlari[ix]
        img = img.resize((int(iw*zoom), int(ih*zoom)), Image.LANCZOS)
        iw,ih = img.size

        x_min,x_max = min(0,cw-iw), 0
        y_min,y_max = min(0,ch-ih), 0
        self.pan_sinirlari[ix]=(x_min,x_max,y_min,y_max)

        px,py = self.pan_koordinatlari[ix]
        px = max(x_min, min(x_max, px))
        py = max(y_min, min(y_max, py))
        if px==0 and py==0 and zoom==min_zoom:
            px = (cw-iw)//2; py=(ch-ih)//2
        self.pan_koordinatlari[ix]=(px,py)

        self.fotograf_imgler[ix]=ImageTk.PhotoImage(img)
        canvas.image=self.fotograf_imgler[ix]
        canvas.create_image(px,py,anchor=NW,image=self.fotograf_imgler[ix])

        if self.degerler[ix][4]==0:
            canvas.create_text(cw/2,ch/2,text="PASS",fill="red",font=("Segoe UI",32,"bold"))

        for j,lbl in enumerate(self.renk_kutulari[loc]):
            if j==4: lbl.config(text=f"{self.degerler[ix][5]:+d}")
            else:
                v=self.degerler[ix][j]; lbl.config(text=f"{v:+.0f}" if j!=3 else f"{v:.1f}")
        self.adet_etiketleri[loc].config(text=str(self.degerler[ix][4]))

    # ----------------- Etkileşim -----------------
    def basla_pan(self,e,ix):
        if len(self.pan_baslangic)<=ix:
            self.pan_baslangic += [(0,0)]*(ix-len(self.pan_baslangic)+1)
        self.pan_baslangic[ix]=(e.x,e.y)

    def pan_yap(self,e,ix):
        x0,y0=self.pan_baslangic[ix]
        dx,dy=e.x-x0, e.y-y0
        px,py=self.pan_koordinatlari[ix]
        x_min,x_max,y_min,y_max=self.pan_sinirlari[ix]
        self.pan_koordinatlari[ix]=(max(x_min,min(x_max,px+dx)),
                                    max(y_min,min(y_max,py+dy)))
        self.pan_baslangic[ix]=(e.x,e.y)
        self.render_gorsel(ix)

    def zoom_yap(self,e,ix):
        delta = self.zoom_hassasiyet if e.delta>0 else -self.zoom_hassasiyet
        cw,ch=self.canvas_boyut
        img=self.rotated_images[ix]
        iw,ih=img.size
        min_zoom=max(cw/iw, ch/ih)
        new_zoom=max(min_zoom, min(3.0, self.zoom_oranlari[ix]+delta))
        if abs(new_zoom-self.zoom_oranlari[ix])<0.01: return
        old_zoom=self.zoom_oranlari[ix]
        self.zoom_oranlari[ix]=new_zoom

        mx,my=e.x,e.y
        old_px,old_py=self.pan_koordinatlari[ix]
        old_w,old_h=iw*old_zoom, ih*old_zoom
        new_w,new_h=iw*new_zoom, ih*new_zoom
        rel_x=0.5 if old_w==0 else (mx-old_px)/old_w
        rel_y=0.5 if old_h==0 else (my-old_py)/old_h
        new_px = mx - (rel_x*new_w)
        new_py = my - (rel_y*new_h)
        self.pan_koordinatlari[ix]=(new_px,new_py)
        self.render_gorsel(ix)

    def renk_ayar(self,ix,param,delta):
        if param==3:
            self.degerler[ix][param]=round(max(0.3,min(1.5,self.degerler[ix][param]+delta*0.02)),2)
        else:
            self.degerler[ix][param]+=delta
        self.render_gorsel(ix)

    def netlik_ayar(self,ix,delta):
        self.degerler[ix][5]=max(-50,min(50,self.degerler[ix][5]+delta))
        self.render_gorsel(ix)

    def adet_degistir(self,ix,delta):
        self.degerler[ix][4]=max(0,self.degerler[ix][4]+delta)
        self.render_gorsel(ix)

    def ileri(self):
        if (self.sayfa+1)*6 < len(self.gorseller):
            self.sayfa += 1
            self.gorsel_goster()

    def geri(self):
        if self.sayfa>0:
            self.sayfa -= 1
            self.gorsel_goster()

    # ----------------- Yazdırma -----------------
    def yazdir(self, image_to_print):
        if not image_to_print:
            return
        if not self.yazici:
            messagebox.showwarning("Uyarı", "Yazıcı bulunamadı!")
            return
        try:
            sysname=platform.system()
            if sysname=="Windows" and HAS_WIN32:
                self._print_windows(image_to_print)
            elif sysname=="Darwin":
                self._print_mac(image_to_print)
            elif sysname=="Linux" and cups:
                self._print_linux(image_to_print)
            else:
                messagebox.showwarning("Uyarı","Bu platformda yazdırma yapılandırılmadı.")
        except Exception as e:
            messagebox.showerror("Yazdırma Hatası", f"Yazdırma sırasında hata: {e}")

    def _get_paper_size_inches(self):
        if self.ebat=="10x15": return (10/2.54, 15/2.54)
        if self.ebat=="13x18": return (13/2.54, 18/2.54)
        if self.ebat=="15x21": return (15/2.54, 21/2.54)
        if self.ebat=="A4":    return (21/2.54, 29.7/2.54)
        return (21/2.54, 29.7/2.54)

    def _print_windows(self, image_to_print):
        printer = self.yazici
        hprinter = win32print.OpenPrinter(printer)
        pdc = win32ui.CreateDC(); pdc.CreatePrinterDC(printer)
        pdc.StartDoc("FOTOĞRAF BASKI"); pdc.StartPage()
        dpi_x = pdc.GetDeviceCaps(win32con.LOGPIXELSX)
        dpi_y = pdc.GetDeviceCaps(win32con.LOGPIXELSY)

        tw,th = self._get_paper_size_inches()
        pw,ph = int(tw*dpi_x), int(th*dpi_y)

        img=image_to_print; iw,ih=img.size
        if (tw<th and iw>ih) or (tw>th and iw<ih):
            img=img.rotate(90, expand=True); iw,ih=img.size
        scale=min(pw/iw, ph/ih)
        fw,fh=int(iw*scale), int(ih*scale)
        img=img.resize((fw,fh), Image.LANCZOS)

        page_w=pdc.GetDeviceCaps(win32con.HORZRES)
        page_h=pdc.GetDeviceCaps(win32con.VERTRES)
        x=(page_w-fw)//2; y=(page_h-fh)//2
        ImageWin.Dib(img).draw(pdc.GetHandleOutput(), (x,y,x+fw,y+fh))
        pdc.EndPage(); pdc.EndDoc(); pdc.DeleteDC(); win32print.ClosePrinter(hprinter)

    def _get_mac_media(self):
        if self.ebat=="10x15": return "10x15cm"
        if self.ebat=="13x18": return "13x18cm"
        if self.ebat=="15x21": return "15x21cm"
        if self.ebat=="A4":    return "iso-a4"
        return "iso-a4"

    def _print_mac(self, image_to_print):
        temp="/tmp/print_temp.jpg"
        image_to_print.save(temp,"JPEG",quality=95)
        cmd=["lp","-o","fit-to-page","-o",f"media={self._get_mac_media()}"]
        if self.yazici: cmd+=["-d",self.yazici]
        cmd.append(temp)
        subprocess.run(cmd, check=True)
        try: os.unlink(temp)
        except Exception: pass

    def _get_cups_media(self):
        if self.ebat=="10x15": return "10x15cm"
        if self.ebat=="13x18": return "13x18cm"
        if self.ebat=="15x21": return "15x21cm"
        if self.ebat=="A4":    return "A4"
        return "A4"

    def _print_linux(self, image_to_print):
        temp="/tmp/print_temp.jpg"
        image_to_print.save(temp,"JPEG",quality=95)
        conn=cups.Connection()
        printer=self.yazici or conn.getDefault()
        options={"fit-to-page":"True","media":self._get_cups_media(),"scaling":"100"}
        conn.printFile(printer, temp, "Fotoğraf Baskı", options)
        try: os.unlink(temp)
        except Exception: pass

    # ----------------- Yardımcı işlemler -----------------
    def zoom_pan_sifirla(self, ix):
        img=self.rotated_images[ix]; iw,ih=img.size
        cw,ch=self.canvas_boyut
        zoom=max(cw/iw, ch/ih)
        self.zoom_oranlari[ix]=zoom
        self.pan_koordinatlari[ix]=((cw-iw*zoom)//2, (ch-ih*zoom)//2)
        self.render_gorsel(ix)

    def hepsine_uygula(self):
        if not self.gorseller: return
        bas=self.sayfa*6
        ref=self.degerler[bas][:]
        for i in range(bas, min(bas+6, len(self.gorseller))):
            self.degerler[i]=[ref[0],ref[1],ref[2],ref[3],self.degerler[i][4],ref[5]]
            self.zoom_oranlari[i]=1.0; self.pan_koordinatlari[i]=(0,0)
            self.render_gorsel(i)
        self.gorsel_goster()


if __name__ == "__main__":
    root = Tk(); root.withdraw()
    FotoYuklemePenceresi(root, ebat="10x15", yazici=get_default_printer())
    root.mainloop()
