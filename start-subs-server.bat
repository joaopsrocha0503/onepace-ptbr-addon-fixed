@echo off
REM ============================================================
REM  Servidor estatico das legendas corrigidas (pasta subs/)
REM  Serve os .srt em http://127.0.0.1:8080/<EP>.srt
REM  ARRANCA ESTE PRIMEIRO. Deixa esta janela aberta.
REM ============================================================
cd /d "%~dp0"
echo A iniciar servidor de legendas em http://127.0.0.1:8080 ...
echo (fecha esta janela para parar o servidor)
npx --yes serve subs -l 8080
