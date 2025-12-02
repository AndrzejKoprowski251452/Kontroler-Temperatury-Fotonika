# Kontroler Temperatury - Instrukcje Linux

## 🐧 Uruchomienie na systemie Linux

### Automatyczna instalacja (zalecana)

```bash
chmod +x install_linux.sh
./install_linux.sh
```

### Instalacja ręczna

#### 1. Zainstaluj zależności systemowe

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install python3 python3-pip python3-tk
```

**CentOS/RHEL/Fedora:**
```bash
sudo yum install python3 python3-pip tkinter
# lub na nowszych wersjach:
sudo dnf install python3 python3-pip python3-tkinter
```

**Arch Linux:**
```bash
sudo pacman -S python python-pip tk
```

#### 2. Zainstaluj biblioteki Python

```bash
pip3 install --user matplotlib pyserial numpy
```

#### 3. Skonfiguruj uprawnienia do portów szeregowych

```bash
sudo usermod -a -G dialout $USER
```

**⚠️ WAŻNE:** Po dodaniu do grupy dialout, wyloguj się i zaloguj ponownie!

#### 4. Uruchom aplikację

```bash
python3 Kontroler.py
```

## 🔧 Rozwiązywanie problemów

### Nie ma uprawnień do portu szeregowego

```bash
# Tymczasowo:
sudo chmod 666 /dev/ttyUSB0

# Lub dodaj użytkownika do grupy dialout (trwale):
sudo usermod -a -G dialout $USER
# Następnie wyloguj się i zaloguj ponownie
```

### Sprawdzenie dostępnych portów

```bash
# Lista portów USB
ls -la /dev/tty{USB,ACM}*

# Sprawdź logi urządzeń
dmesg | grep tty

# Sprawdź czy urządzenie jest wykrywane
lsusb
```

### Biblioteki nie są zainstalowane

```bash
# Sprawdź czy biblioteka jest zainstalowana
python3 -c "import matplotlib, serial, numpy, tkinter"

# Reinstalacja jeśli potrzebna
pip3 install --user --force-reinstall matplotlib pyserial numpy
```

### Aplikacja nie wykrywa portów

1. Sprawdź czy urządzenie jest podłączone: `lsusb`
2. Sprawdź uprawnienia: `ls -la /dev/ttyUSB*`
3. Sprawdź grupy użytkownika: `groups $USER`
4. Sprawdź czy port istnieje: `ls /dev/tty{USB,ACM}*`

### Problemy z GUI (tkinter)

```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# Sprawdź zmienne środowiskowe
echo $DISPLAY

# Jeśli używasz SSH, włącz X11 forwarding
ssh -X username@hostname
```

## 📋 Różnice między systemami

### Porty szeregowe

| System | Typowe porty |
|--------|-------------|
| Windows | COM1, COM2, COM3, COM4 |
| Linux | /dev/ttyUSB0, /dev/ttyACM0, /dev/ttyS0 |
| macOS | /dev/cu.usbserial, /dev/tty.usbmodem |

### Konfiguracja portów

Aplikacja automatycznie wykrywa system i proponuje odpowiednie porty:

- **Windows**: Standardowe porty COM1-COM5
- **Linux**: Skanuje `/dev/tty{USB,ACM,S}*`
- **macOS**: Sprawdza porty `/dev/{cu,tty}.usb*`

### Uprawnienia

- **Windows**: Nie wymagane specjalne uprawnienia
- **Linux**: Użytkownik musi być w grupie `dialout`
- **macOS**: Zazwyczaj nie wymagane specjalne uprawnienia

## 🎯 Testowanie

```bash
# Test podstawowych funkcji
python3 -c "
from Kontroler import get_available_serial_ports, get_default_serial_port
print('Dostępne porty:', get_available_serial_ports())
print('Domyślny port:', get_default_serial_port())
"

# Test GUI
python3 -c "import tkinter; tkinter.Tk().withdraw(); print('tkinter OK')"

# Test matplotlib
python3 -c "import matplotlib.pyplot as plt; print('matplotlib OK')"

# Test serial
python3 -c "import serial; print('pyserial OK')"
```

## 💡 Wskazówki

1. **Sprawdź logi**: `dmesg | tail` po podłączeniu urządzenia
2. **Uprawnienia**: Dodaj się do grupy dialout przed pierwszym użyciem
3. **Porty**: Aplikacja automatycznie wykrywa dostępne porty
4. **GUI**: Sprawdź czy masz aktywne środowisko graficzne (X11/Wayland)
5. **Zależności**: Używaj pip3 z flagą `--user` dla instalacji lokalnej

## 🆘 Dalsze wsparcie

Jeśli nadal masz problemy:

1. Sprawdź czy wszystkie zależności są zainstalowane
2. Uruchom skrypt `install_linux.sh` ponownie
3. Sprawdź logi systemowe: `journalctl -f`
4. Sprawdź czy port jest dostępny: `sudo minicom -D /dev/ttyUSB0`