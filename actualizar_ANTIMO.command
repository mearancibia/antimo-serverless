#!/bin/bash
# Doble clic para actualizar el tablero ANTIMO con datos de Bistrosoft
cd "$(dirname "$0")"
echo "======================================"
echo "   ANTIMO - Actualizando tablero"
echo "======================================"
if ! command -v python3 >/dev/null 2>&1; then
  echo ""
  echo "Falta instalar Python. Se va a abrir la instalacion de macOS."
  echo "Instalalo (boton 'Instalar'), esperá a que termine y volvé a hacer doble clic aca."
  xcode-select --install
  echo ""; read -p "Enter para cerrar..."; exit 1
fi
echo "Preparando (primera vez puede tardar)..."
python3 -m pip install --user --quiet openpyxl requests pdfplumber 2>/dev/null
echo "1/2 Trayendo ventas de Bistrosoft..."
python3 conector_bistrosoft.py
if [ $? -ne 0 ]; then echo ""; echo "ERROR al traer datos. Revisá tu internet y las credenciales en datos/bistro_config.json"; read -p "Enter para cerrar..."; exit 1; fi
echo "2/2 Calculando y generando el tablero..."
python3 actualizar_antimo.py
if [ $? -ne 0 ]; then echo ""; echo "ERROR al generar el tablero."; read -p "Enter para cerrar..."; exit 1; fi
echo ""
echo "Listo! Datos actualizados."
echo "Para VER el tablero, usa run_ANTIMO_app.command (el tablero ya no es un archivo"
echo "suelto: pide los datos al servidor local, igual que en la nube)."
read -p "Todo OK. Enter para cerrar esta ventana..."
