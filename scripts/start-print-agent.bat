@echo off
rem SYNORA print agent for a USB receipt printer on THIS Windows PC.
rem 1) In SYNORA: Settings -> Printers -> add the printer in "Print agent" mode (leave IP empty),
rem    then press "Create token" and paste it below.
rem 2) Set the three values, save, and double-click this file. Keep the window open while you work.
rem    To start it automatically when Windows starts, put a shortcut to this file in
rem    shell:startup (Win+R, type shell:startup).

set SYNORA_SERVER=http://localhost:3000
set SYNORA_AGENT_TOKEN=PASTE_TOKEN_HERE
set SYNORA_WINDOWS_PRINTER=XP-80C

cd /d "%~dp0"
python print_agent.py --interval 1
pause
