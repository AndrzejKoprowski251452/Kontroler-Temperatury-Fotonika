#!/bin/bash

# Skrypt instalacyjny dla Kontrolera Temperatury na Linux

echo "=== Instalator Kontrolera Temperatury dla Linux ==="
echo

# Sprawdź system
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "❌ Ten skrypt jest przeznaczony dla systemu Linux"
    exit 1
fi

echo "🔍 Sprawdzanie systemu..."
echo "System: $(uname -s)"
echo "Dystrybucja: $(lsb_release -d 2>/dev/null | cut -f2 || echo 'Nieznana')"

# Sprawdź Python
echo
echo "🐍 Sprawdzanie Pythona..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 nie jest zainstalowany"
    echo "Zainstaluj używając: sudo apt-get install python3"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo "✅ $PYTHON_VERSION"

# Sprawdź pip
echo
echo "📦 Sprawdzanie pip..."
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 nie jest zainstalowany"
    echo "Zainstaluj używając: sudo apt-get install python3-pip"
    exit 1
fi

echo "✅ pip3 dostępny"

# Sprawdź zależności systemowe
echo
echo "🔧 Sprawdzanie zależności systemowych..."

# Tkinter (część standardowej biblioteki na większości dystrybucji)
if ! python3 -c "import tkinter" 2>/dev/null; then
    echo "⚠️  Tkinter nie jest dostępny"
    echo "Instalowanie tkinter..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y python3-tk
    elif command -v yum &> /dev/null; then
        sudo yum install -y tkinter
    elif command -v pacman &> /dev/null; then
        sudo pacman -S tk
    else
        echo "❌ Nie udało się automatycznie zainstalować tkinter"
        echo "Zainstaluj ręcznie dla swojej dystrybucji"
        exit 1
    fi
else
    echo "✅ tkinter dostępny"
fi

# Instaluj zależności Python
echo
echo "📚 Instalowanie bibliotek Python..."

LIBRARIES=("matplotlib" "pyserial" "numpy")

for lib in "${LIBRARIES[@]}"; do
    echo "Instalowanie $lib..."
    if ! python3 -c "import ${lib/pyserial/serial}" 2>/dev/null; then
        pip3 install --user "$lib"
    else
        echo "✅ $lib już zainstalowany"
    fi
done

# Sprawdź uprawnienia do portów szeregowych
echo
echo "🔌 Sprawdzanie uprawnień do portów szeregowych..."

if groups $USER | grep -q "\bdialout\b"; then
    echo "✅ Użytkownik jest w grupie dialout"
else
    echo "⚠️  Użytkownik nie jest w grupie dialout"
    echo "Dodawanie do grupy dialout..."
    sudo usermod -a -G dialout $USER
    echo "✅ Dodano użytkownika do grupy dialout"
    echo "⚠️  UWAGA: Aby zmiany weszły w życie, wyloguj się i zaloguj ponownie!"
fi

# Sprawdź dostępne porty szeregowe
echo
echo "🔍 Sprawdzanie dostępnych portów szeregowych..."
if ls /dev/tty{USB,ACM}* 2>/dev/null; then
    echo "✅ Znaleziono porty szeregowe USB:"
    ls /dev/tty{USB,ACM}* 2>/dev/null
else
    echo "⚠️  Nie znaleziono portów USB"
    echo "Sprawdź czy urządzenie jest podłączone"
fi

# Test aplikacji
echo
echo "🧪 Testowanie aplikacji..."
if python3 -c "
from Kontroler import get_available_serial_ports, get_default_serial_port
import platform
print('✅ Import modułów OK')
print(f'System: {platform.system()}')
print(f'Dostępne porty: {get_available_serial_ports()}')
print(f'Domyślny port: {get_default_serial_port()}')
" 2>/dev/null; then
    echo "✅ Aplikacja działa poprawnie"
else
    echo "❌ Błąd testowania aplikacji"
    echo "Sprawdź czy wszystkie zależności są zainstalowane"
    exit 1
fi

echo
echo "🎉 Instalacja zakończona pomyślnie!"
echo
echo "📋 Instrukcje uruchomienia:"
echo "1. Podłącz urządzenie USB"
echo "2. Uruchom: python3 Kontroler.py"
echo "3. Jeśli są problemy z uprawnieniami, wyloguj się i zaloguj ponownie"
echo
echo "🔧 Rozwiązywanie problemów:"
echo "- Brak uprawnień do portu: sudo chmod 666 /dev/ttyUSB0"
echo "- Sprawdź porty: ls -la /dev/tty{USB,ACM}*"
echo "- Sprawdź logi: dmesg | grep tty"