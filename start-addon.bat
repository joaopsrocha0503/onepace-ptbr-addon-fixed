@echo off
REM ============================================================
REM  Addon Stremio One Pace PT-BR
REM  Aponta as legendas para o servidor local (porta 8080)
REM  em vez do GitHub raw, e serve o manifest na porta 7000.
REM  ARRANCA ESTE A SEGUIR ao start-subs-server.bat.
REM  Deixa esta janela aberta.
REM ============================================================
cd /d "%~dp0"
set "SUBS_BASE_URL=http://127.0.0.1:8080"
echo SUBS_BASE_URL = %SUBS_BASE_URL%
echo A iniciar addon ... Manifest: http://127.0.0.1:7000/manifest.json
echo (fecha esta janela para parar o addon)
npm start
