from __future__ import annotations
from loguru import logger
class TrayController:
    def __init__(self,on_open,on_exit,on_close_all,on_diagnostics,on_backup=None,on_tasks=None,get_status=None):
        self.on_open=on_open; self.on_exit=on_exit; self.on_close_all=on_close_all; self.on_diagnostics=on_diagnostics
        self.on_backup=on_backup or (lambda:None); self.on_tasks=on_tasks or (lambda:None); self.get_status=get_status or (lambda:"Triada Network")
        self._icon=None; self._thread=None
    def start(self):
        try:
            import threading, pystray
            from PIL import Image, ImageDraw
        except ImportError:
            logger.info("Tray dependencies are not installed; tray is disabled"); return
        image=Image.new("RGB",(64,64),"black"); draw=ImageDraw.Draw(image); draw.rectangle((8,8,56,56),outline="white",width=3); draw.text((20,18),"T",fill="white")
        menu=pystray.Menu(
            pystray.MenuItem(lambda _item:self.get_status(),lambda *_:None,enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open Triada Network",lambda *_:self.on_open()),
            pystray.MenuItem("Task Center",lambda *_:self.on_tasks()),
            pystray.MenuItem("Close all browsers",lambda *_:self.on_close_all()),
            pystray.MenuItem("Create backup",lambda *_:self.on_backup()),
            pystray.MenuItem("Run diagnostics",lambda *_:self.on_diagnostics()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit",lambda *_:self.on_exit()),
        )
        self._icon=pystray.Icon("triada-network",image,"Triada Network",menu)
        self._thread=threading.Thread(target=self._icon.run,name="triada-tray",daemon=True); self._thread.start()
    def stop(self):
        if self._icon: self._icon.stop()
