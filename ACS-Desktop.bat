@echo off
:: ACS Desktop — opens the studio in its own native window (no browser)
cd /d "%~dp0"
start "" /min pythonw "D:\ACS\desktop.py"
