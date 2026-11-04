@echo off
setlocal
rem Instalador do CryptoVault Desktop para maquinas em que o Smart App Control
rem bloqueia instaladores nao assinados. Nao pede privilegios de administrador.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
if errorlevel 1 pause
