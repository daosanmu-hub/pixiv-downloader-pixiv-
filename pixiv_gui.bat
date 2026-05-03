@echo off
chcp 65001 >nul 2>&1
title Pixiv Downloader

"C:\Python314\python.exe" "%~dp0pixiv_gui.py"
if %errorlevel% neq 0 (
    pause
)
