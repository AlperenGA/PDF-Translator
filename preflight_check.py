import importlib
import os
import subprocess
import sys
import requests

# ==============================
#  SETTINGS
# ==============================
REQUIRED_PYTHON_PACKAGES = [
    "requests",
    "lxml",
    "beautifulsoup4",
    "transformers",
    "torch",
    "reportlab",
    "pdfminer.six",
]

REQUIRED_SYSTEM_BINARIES = [
    "pdflatex",  # LaTeX derleyici
]

DIRECTORIES = [
    "pdfs",
    "output",
    "logs"
]

# Grobid varsayılan
GROBID_URL = "http://localhost:8070/api/isalive"


# ==============================
#  HELPERS
# ==============================
def check_python_packages():
    print("\n🔍 Python paketleri kontrol ediliyor...")
    missing = []
    for pkg in REQUIRED_PYTHON_PACKAGES:
        try:
            importlib.import_module(pkg.replace("-", "_").replace(".", "_"))
            print(f"  ✅ {pkg}")
        except ImportError:
            print(f"  ❌ {pkg} eksik!")
            missing.append(pkg)

    if missing:
        print("\n📦 Eksik paketler:")
        print("   " + " ".join(missing))
        print("👉 Bunları yüklemek için: pip install " + " ".join(missing))
    return len(missing) == 0


def check_system_binaries():
    print("\n🔍 Sistem bağımlılıkları kontrol ediliyor...")
    missing = []
    for binary in REQUIRED_SYSTEM_BINARIES:
        result = subprocess.run(["which", binary], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            print(f"  ✅ {binary} bulundu: {result.stdout.strip()}")
        else:
            print(f"  ❌ {binary} bulunamadı!")
            missing.append(binary)

    if missing:
        print("\n🛠️ Eksik sistem araçları:")
        print("   " + " ".join(missing))
        print("👉 macOS: brew install mactex   |   Linux: sudo apt-get install texlive-full")
    return len(missing) == 0


def check_directories():
    print("\n🔍 Klasörler kontrol ediliyor...")
    all_ok = True
    for d in DIRECTORIES:
        if os.path.exists(d):
            if os.access(d, os.W_OK):
                print(f"  ✅ {d}/ mevcut ve yazılabilir")
            else:
                print(f"  ❌ {d}/ mevcut ama yazılamıyor (izin hatası)!")
                all_ok = False
        else:
            print(f"  ❌ {d}/ klasörü eksik, oluşturuluyor...")
            try:
                os.makedirs(d, exist_ok=True)
                print(f"  ✅ {d}/ oluşturuldu")
            except Exception as e:
                print(f"  ❌ {d}/ oluşturulamadı: {e}")
                all_ok = False
    return all_ok


def check_grobid():
    print("\n🔍 Grobid servisi kontrol ediliyor...")
    try:
        response = requests.get(GROBID_URL, timeout=5)
        if response.status_code == 200:
            print("  ✅ Grobid çalışıyor")
            return True
        else:
            print(f"  ❌ Grobid cevap veriyor ama hata kodu döndü: {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"  ❌ Grobid’e ulaşılamadı: {e}")
        print("👉 Grobid'i başlat: docker-compose up -d")
        return False


# ==============================
#  MAIN
# ==============================
def main():
    print("===================================")
    print("🚀 Academic PDF Translator - Preflight Check")
    print("===================================")

    checks = {
        "Python Paketleri": check_python_packages(),
        "Sistem Araçları": check_system_binaries(),
        "Klasörler": check_directories(),
        "Grobid Servisi": check_grobid(),
    }

    print("\n===================================")
    print("📊 Kontrol Sonuçları")
    print("===================================")

    all_ok = True
    for name, ok in checks.items():
        print(f"{name}: {'✅ OK' if ok else '❌ HATA'}")
        if not ok:
            all_ok = False

    print("===================================")
    if all_ok:
        print("🎉 Her şey hazır! Pipeline güvenle çalıştırılabilir.")
        sys.exit(0)
    else:
        print("⚠️ Bazı sorunlar var. Yukarıdaki hataları düzeltmelisin.")
        sys.exit(1)


if __name__ == "__main__":
    main()
