#!/bin/bash
cd "$(dirname "$0")"
echo "=================================="
echo "   ANTIMO - App de gestión"
echo "=================================="
if ! command -v python3 >/dev/null 2>&1; then
  echo "Falta Python. Se abre la instalación de macOS."; xcode-select --install
  read -p "Instalalo y volvé a hacer doble clic. Enter para cerrar..."; exit 1
fi
python3 -m pip install --user --quiet openpyxl requests pdfplumber 2>/dev/null
echo "Iniciando… (el navegador se abre solo en unos segundos)."
echo "IMPORTANTE: dejá esta ventana abierta mientras usás ANTIMO. Para cerrar la app, cerrá esta ventana."
python3 app_antimo.py
