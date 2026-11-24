#!/usr/bin/env bash
# Descarga (solo lectura, datos públicos) las velas de 4 h y el funding mensual de Binance USDT-M que usa
# backtest_independiente.py. ~2 800 archivos, ~23 MB. Uso: bash descargar_binance.sh <carpeta_destino_vacia>
# La carpeta de destino es para DATOS (no ejecutar nada desde ella). No borra nada.
set -euo pipefail
DEST="${1:?indica una carpeta de destino}"
mkdir -p "$DEST/k" "$DEST/f"
URLS="$DEST/urls.txt"
: > "$URLS"
for s in BTC ETH SOL BNB XRP DOGE ADA AVAX LINK DOT LTC BCH TRX NEAR ATOM UNI AAVE FIL ETC XLM; do
  for y in 2021 2022 2023 2024 2025 2026; do
    for m in 01 02 03 04 05 06 07 08 09 10 11 12; do
      [ "$y$m" -gt 202610 ] && continue
      echo "k https://data.binance.vision/data/futures/um/monthly/klines/${s}USDT/4h/${s}USDT-4h-${y}-${m}.zip" >> "$URLS"
      echo "f https://data.binance.vision/data/futures/um/monthly/fundingRate/${s}USDT/${s}USDT-fundingRate-${y}-${m}.zip" >> "$URLS"
    done
  done
done
cd "$DEST"
xargs -P 12 -n 2 sh -c 'curl -s -f -m 40 -o "$0/$(basename "$1")" "$1" || echo "FALLO $1"' < "$URLS" > fallos.txt
echo "velas: $(ls k | wc -l) · funding: $(ls f | wc -l) · fallos: $(grep -c FALLO fallos.txt || true)"
