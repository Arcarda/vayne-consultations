@echo off
title Smart Scout // Vayne Consulting
echo.
echo  ██╗   ██╗ █████╗ ██╗   ██╗███╗   ██╗███████╗
echo  ██║   ██║██╔══██╗╚██╗ ██╔╝████╗  ██║██╔════╝
echo  ██║   ██║███████║ ╚████╔╝ ██╔██╗ ██║█████╗
echo  ╚██╗ ██╔╝██╔══██║  ╚██╔╝  ██║╚██╗██║██╔══╝
echo   ╚████╔╝ ██║  ██║   ██║   ██║ ╚████║███████╗
echo    ╚═══╝  ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═══╝╚══════╝
echo.
echo  SMART SCOUT // Web UI
echo  Starting server at http://localhost:5000
echo  Press Ctrl+C to stop.
echo.
py -3.10 webapp\app.py
pause
