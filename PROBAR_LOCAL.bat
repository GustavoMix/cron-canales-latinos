@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title ChannelWatch - Prueba local

 echo.
 echo ============================================================
 echo   CHANNELWATCH V3 RAPIDO - PROBAR CRON LOCALMENTE
 echo ============================================================
 echo.

set "PY_LAUNCHER="
where py >nul 2>&1
if not errorlevel 1 (
    py -3.12 --version >nul 2>&1
    if not errorlevel 1 set "PY_LAUNCHER=py -3.12"
    if not defined PY_LAUNCHER (
        py -3.11 --version >nul 2>&1
        if not errorlevel 1 set "PY_LAUNCHER=py -3.11"
    )
    if not defined PY_LAUNCHER set "PY_LAUNCHER=py"
)

if not defined PY_LAUNCHER (
    where python >nul 2>&1
    if not errorlevel 1 set "PY_LAUNCHER=python"
)

if not defined PY_LAUNCHER (
    echo [ERROR] No se encontro Python.
    echo Instala Python 3.11 o 3.12 y marca "Add Python to PATH".
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/5] Python detectado...
%PY_LAUNCHER% --version
if errorlevel 1 goto :error

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [2/5] Creando entorno virtual .venv...
    %PY_LAUNCHER% -m venv .venv
    if errorlevel 1 goto :error
) else (
    echo [2/5] Entorno virtual existente.
)

set "PYTHON=.venv\Scripts\python.exe"

echo.
echo [3/5] Comprobando ChannelWatch y dependencias...
"%PYTHON%" -c "import channelwatch, httpx" >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias por primera vez...
    "%PYTHON%" -m pip install -e "."
    if errorlevel 1 goto :error
) else (
    echo Dependencias listas.
)

echo.
echo [4/5] Validando configuracion...
"%PYTHON%" -m channelwatch validate-config
if errorlevel 1 goto :error

echo.
echo PAISES DISPONIBLES:
"%PYTHON%" -m channelwatch list-countries
if errorlevel 1 goto :error

echo.
echo Escribe el codigo ISO del pais. Ejemplos: BO, AR, BR, PE
echo Escribe ALL para revisar todos los paises.
set "COUNTRY="
set /p COUNTRY=Pais [BO]: 
if not defined COUNTRY set "COUNTRY=BO"

set "WEB_ORIGIN="
echo.
echo Opcional: si quieres medir CORS para la web local escribe:
echo http://localhost:3000
echo Si solo quieres revisar canales, presiona ENTER.
set /p WEB_ORIGIN=Origen web: 
if defined WEB_ORIGIN set "CHANNELWATCH_WEB_ORIGIN=%WEB_ORIGIN%"

echo.
echo [5/5] Ejecutando verificacion...
echo Modo rapido: fuentes en paralelo, sondeo HLS y confirmacion solo de candidatos buenos.
echo Veras porcentaje de avance y cada canal tendra un timeout total limitado.
echo.

if /i "%COUNTRY%"=="ALL" (
    "%PYTHON%" -m channelwatch run
) else (
    "%PYTHON%" -m channelwatch run --country %COUNTRY%
)
if errorlevel 1 goto :error

echo.
echo ============================================================
echo   TERMINADO
 echo ============================================================
echo JSON generados en: %CD%\public\data
if exist "public\data\countries.json" (
    echo Abriendo carpeta de resultados...
    explorer "public\data"
)
echo.
pause
exit /b 0

:error
echo.
echo ============================================================
echo   ERROR - ChannelWatch no pudo terminar
 echo ============================================================
echo Revisa el mensaje que aparece arriba.
echo.
pause
exit /b 1
