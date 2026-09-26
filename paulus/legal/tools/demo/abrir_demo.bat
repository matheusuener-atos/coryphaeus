@echo off
rem Abre o PAULUS na base de demonstracao (data\demo), sem tocar nos dados de verdade.
rem Para criar ou refazer a base: venv\Scripts\python.exe tools\demo\criar_demo.py --refazer
cd /d "%~dp0..\.."
if not exist "data\demo\paulus.db" venv\Scripts\python.exe tools\demo\criar_demo.py
set PAULUS_DADOS=%CD%\data\demo
venv\Scripts\python.exe src\desktop.py
