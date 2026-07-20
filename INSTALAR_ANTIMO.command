#!/bin/bash
cd "$(dirname "$0")"
clear
echo "================================================"
echo "     ANTIMO - Instalacion (una sola vez)"
echo "================================================"
echo ""

# 0) Auto-reparacion: si la carpeta vino por ZIP, pendrive o AirDrop, los .command
#    pueden llegar sin permiso de ejecucion y/o marcados en cuarentena por macOS.
#    Se arregla aca para que a partir de ahora el doble clic funcione siempre.
chmod +x *.command 2>/dev/null
xattr -dr com.apple.quarantine . 2>/dev/null
echo "[OK] Carpeta desbloqueada."

# 1) Python
if ! command -v python3 >/dev/null 2>&1; then
  echo ""
  echo "Falta instalar Python (herramientas de macOS)."
  echo "Se abrira una ventana de Apple: apreta 'Instalar' y espera"
  echo "a que termine (puede tardar varios minutos)."
  echo ""
  echo "Cuando termine, volve a hacer doble clic en INSTALAR_ANTIMO."
  xcode-select --install 2>/dev/null
  echo ""; read -p "Enter para cerrar..."; exit 0
fi
echo "[OK] Python encontrado ($(python3 -V 2>&1))."

# 2) Dependencias.
#    Se intenta primero --user. Los Python nuevos (3.11+ de Homebrew o python.org) rechazan
#    instalar ahi y piden --break-system-packages: sin ese reintento, el error se confundia
#    con un problema de internet y mandaba a buscar donde no era.
echo "Instalando componentes (una vez, puede tardar)..."
LOG=$(mktemp)
python3 -m pip install --user --quiet --upgrade pip >/dev/null 2>&1
if python3 -m pip install --user --quiet openpyxl requests pdfplumber >"$LOG" 2>&1; then
  echo "[OK] Componentes instalados."
elif python3 -m pip install --user --break-system-packages --quiet openpyxl requests pdfplumber >>"$LOG" 2>&1; then
  echo "[OK] Componentes instalados."
else
  echo "[!] No se pudieron instalar los componentes."
  echo "    Detalle:"
  tail -6 "$LOG" | sed 's/^/      /'
  echo ""
  echo "    Suele ser falta de internet. Revisa la conexion y volve a abrir INSTALAR_ANTIMO."
  read -p "Enter para cerrar..."; exit 1
fi

# 3) Verificacion real: que los tres modulos IMPORTEN, no solo que pip diga que los bajo.
if ! python3 -c "import openpyxl, requests, pdfplumber" 2>>"$LOG"; then
  echo "[!] Los componentes se bajaron pero no cargan. Detalle:"
  tail -4 "$LOG" | sed 's/^/      /'
  read -p "Enter para cerrar..."; exit 1
fi
echo "[OK] Componentes verificados."

# 4) Credenciales Bistrosoft (si ya vienen configuradas, no se pregunta nada)
CFG="datos/bistro_config.json"; mkdir -p datos entrada
NEED=1
if [ -f "$CFG" ] && ! grep -q "TU_USUARIO" "$CFG" 2>/dev/null; then NEED=0; fi
if [ "$NEED" = "1" ]; then
  echo ""
  echo "Carga tus datos de Bistrosoft (los que usas para entrar al sistema)."
  echo "La contrasena no se ve mientras la escribis (es normal)."
  read -p "  Usuario (email): " U
  read -s -p "  Contrasena: " P; echo ""
  read -p "  Codigo de tienda (shopCode): " S
  cat > "$CFG" <<JSON
{
  "base": "https://ar-api.bistrosoft.com",
  "username": "$U",
  "password": "$P",
  "shopCode": "$S"
}
JSON
  echo "[OK] Credenciales guardadas."
else
  echo "[OK] Cuenta de Bistrosoft ya configurada."
fi

# 5) Prueba de que el sistema realmente arranca en esta Mac
echo ""
echo "Probando que todo funcione..."
if python3 actualizar_antimo.py >"$LOG" 2>&1; then
  echo "[OK] $(tail -1 "$LOG")"
else
  if grep -q "no hay ventas" "$LOG"; then
    echo "[OK] Instalacion lista. Todavia no hay ventas cargadas:"
    echo "     al abrir ANTIMO vas a poder traerlas con un boton."
  else
    echo "[!] Algo fallo al calcular. Detalle:"
    tail -6 "$LOG" | sed 's/^/      /'
    echo ""
    echo "    Sacale una foto a esta ventana y mandasela a quien te paso ANTIMO."
    read -p "Enter para cerrar..."; exit 1
  fi
fi
rm -f "$LOG"

echo ""
echo "================================================"
echo "  Listo! Instalacion completa."
echo ""
echo "  Para USAR ANTIMO: doble clic en"
echo "     run_ANTIMO_app.command"
echo "================================================"
read -p "Enter para cerrar..."
