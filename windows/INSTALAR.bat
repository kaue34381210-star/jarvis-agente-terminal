@echo off
setlocal
title Instalador do JARVIS
chcp 65001 >nul

echo(
echo   ============================================
echo    Instalando JARVIS - agente de terminal
echo   ============================================
echo(

REM 1) Python instalado?
where python >nul 2>&1
if errorlevel 1 (
  echo [ERRO] Python nao encontrado no PATH.
  echo Instale em https://python.org e marque "Add python.exe to PATH".
  echo(
  pause
  exit /b 1
)

set "SRC=%~dp0"
set "DEST=%LOCALAPPDATA%\jarvis"
set "CFG=%APPDATA%\jarvis"
set "DOCS=%USERPROFILE%\Documents\JARVIS"

echo Instalando em: %DEST%
if not exist "%DEST%" mkdir "%DEST%"
if not exist "%CFG%"  mkdir "%CFG%"
if not exist "%DOCS%" mkdir "%DOCS%"

echo Copiando codigo...
copy /y "%SRC%config.py"      "%DEST%\" >nul
copy /y "%SRC%ferramentas.py" "%DEST%\" >nul
copy /y "%SRC%gemini.py"      "%DEST%\" >nul
copy /y "%SRC%local.py"       "%DEST%\" >nul
copy /y "%SRC%aprovacao.py"   "%DEST%\" >nul
copy /y "%SRC%agente.py"      "%DEST%\" >nul

echo Criando ambiente Python...
python -m venv "%DEST%\.venv"

echo(
echo Instalando dependencias (rich, requests, openpyxl, reportlab)...
echo Pode levar 1-3 minutos - baixa ~6 MB. AGUARDE, nao feche a janela.
echo(
"%DEST%\.venv\Scripts\python.exe" -m pip install --upgrade --disable-pip-version-check pip
"%DEST%\.venv\Scripts\python.exe" -m pip install --disable-pip-version-check rich requests openpyxl reportlab
if errorlevel 1 (
  echo [ERRO] Falha ao instalar as dependencias. Verifique a internet.
  pause
  exit /b 1
)

echo Configurando chaves...
if not exist "%CFG%\chaves.txt" (
  if exist "%SRC%chaves.txt" (
    copy /y "%SRC%chaves.txt" "%CFG%\chaves.txt" >nul
    echo   chaves instaladas em %CFG%\chaves.txt
  ) else (
    copy /y "%SRC%chaves.txt.exemplo" "%CFG%\chaves.txt" >nul
    echo   [ATENCAO] Coloque suas chaves em %CFG%\chaves.txt
  )
) else (
  echo   mantendo chaves ja existentes em %CFG%\chaves.txt
)

echo Criando comando 'jarvis'...
set "SHIM=%DEST%\jarvis.bat"
> "%SHIM%" echo @echo off
>>"%SHIM%" echo chcp 65001 ^>nul
>>"%SHIM%" echo set "PYTHONUTF8=1"
>>"%SHIM%" echo set "AGENTE_BASE=%DEST%"
>>"%SHIM%" echo set "JARVIS_CHAVES=%CFG%\chaves.txt"
>>"%SHIM%" echo set "AGENTE_WORKSPACE=%DOCS%"
>>"%SHIM%" echo "%DEST%\.venv\Scripts\python.exe" "%DEST%\agente.py" %%*

REM adiciona a pasta ao PATH do usuario (sem duplicar)
powershell -NoProfile -Command "$p=[Environment]::GetEnvironmentVariable('Path','User'); if($p -notlike '*%DEST%*'){[Environment]::SetEnvironmentVariable('Path', ($p.TrimEnd(';') + ';%DEST%'),'User')}"

echo(
echo   ============================================
echo    JARVIS instalado com sucesso!
echo(
echo    -^> Abra um NOVO terminal (cmd) e digite:  jarvis
echo    -^> Chaves em:            %CFG%\chaves.txt
echo    -^> Arquivos gerados em:  %DOCS%
echo   ============================================
echo(
pause
