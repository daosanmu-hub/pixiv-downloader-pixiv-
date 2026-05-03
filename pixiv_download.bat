@echo off
chcp 936 >nul 2>&1
title Pixiv图片下载器 v3

echo.
echo  ==============================================
echo         Pixiv 图片下载器 v3
echo  ==============================================
echo.
echo  1) 下载作品页
echo  2) 下载画师主页所有作品
echo  3) 更新 Cookie（Cookie 过期后在此更换）
echo  0) 退出
echo.

"C:\Python314\python.exe" "%~dp0pixiv_download.py"

echo.
pause
