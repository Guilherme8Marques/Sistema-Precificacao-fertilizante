@echo off
title Central de Precificacao - Fertilizantes
echo ==========================================
echo   Iniciando Central de Precificacao...
echo   Acesse: http://localhost:8000
echo ==========================================
python -m uvicorn backend.server:app --host 0.0.0.0 --port 8000
pause
