#!/usr/bin/env python3
"""
Script para forzar la actualización del diseño (sin caché)
"""
import webbrowser
import time

def force_refresh():
    """Fuerza la actualización del navegador sin caché"""
    
    timestamp = str(int(time.time()))
    urls = [
        f"http://localhost:5000/?v={timestamp}&no-cache=1",
        f"http://localhost:5000/auth?state=demo&v={timestamp}&no-cache=1"
    ]
    
    print("🎨 Forzando actualización del diseño...")
    print("=" * 45)
    print(f"⏰ Timestamp: {timestamp}")
    print("🧹 Forzando limpieza de caché del navegador")
    
    for url in urls:
        print(f"🌐 Abriendo: {url}")
        webbrowser.open(url)
        time.sleep(1)
    
    print("\n✅ Páginas abiertas con caché limpio")
    print("\n🎨 Deberías ver ahora:")
    print("=" * 25)
    print("🌈 Gradiente: Amarillo → Rojo")
    print("🖼️ Logo: Tu logo.png (100px)")
    print("🔴 Elementos rojos: botones, bordes, badges")
    print("💫 Animaciones suaves")
    
    print("\n💡 Si el gradiente aún no se ve:")
    print("=" * 35)
    print("1. Presiona Ctrl+F5 en el navegador")
    print("2. O Ctrl+Shift+R para refrescar completamente")
    print("3. O ve a Dev Tools (F12) → Application → Storage → Clear Storage")

if __name__ == "__main__":
    force_refresh()