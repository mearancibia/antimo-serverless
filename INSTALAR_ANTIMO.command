#!/bin/bash
cd "$(dirname "$0")"
clear
echo "================================================"
echo "     ANTIMO - Instalacion (una sola vez)"
echo "================================================"
echo ""
# 1) Python
if ! command -v python3 >/dev/null 2>&1; then
  echo "Falta instalar Python (herramientas de macOS)."
  echo "Se abrira una ventana de Apple: apreta 'Instalar' y espera"
  echo "a que termine (puede tardar varios minutos)."
  echo ""
  echo "Cuando termine, volve a hacer doble clic en INSTALAR_ANTIMO."
  xcode-select --install 2>/dev/null
  echo ""; read -p "Enter para cerrar..."; exit 0
fi
echo "[OK] Python encontrado."
# 2) dependencias
echo "Instalando componentes (una vez, puede tardar)..."
python3 -m pip install --user --quiet --upgrade pip >/dev/null 2>&1
if python3 -m pip install --user --quiet openpyxl requests pdfplumber >/dev/null 2>&1; then
  echo "[OK] Componentes instalados."
else
  echo "[!] No se pudieron instalar los componentes. Revisa tu conexion a internet."
  echo "    Volve a intentar con este INSTALAR_ANTIMO."
  read -p "Enter para cerrar..."; exit 1
fi
# 3) permisos
chmod +x run_ANTIMO_app.command actualizar_ANTIMO.command 2>/dev/null
# 4) credenciales Bistrosoft
CFG="datos/bistro_config.json"; mkdir -p datos
NEED=1
if [ -f "$CFG" ] && ! grep -q "TU_USUARIO" "$CFG" 2>/dev/null; then NEED=0; fi
if [ "$NEED" = "1" ]; then
  echo ""
  echo "Cargá tus datos de Bistrosoft (los que usás para entrar al sistema)."
  echo "La contraseña no se ve mientras la escribís (es normal)."
  read -p "  Usuario (email): " U
  read -s -p "  Contraseña: " P; echo ""
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
  echo "[OK] Credenciales ya configuradas."
fi
echo ""
echo "================================================"
echo "  Listo! Instalacion completa."
echo ""
echo "  Para USAR ANTIMO: doble clic en"
echo "     run_ANTIMO_app.command"
echo "================================================"
read -p "Enter para cerrar..."
