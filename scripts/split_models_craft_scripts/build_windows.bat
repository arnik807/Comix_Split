@echo off
REM Build ComicSplit: Go CLI + optional PyInstaller bundle
cd /d "%~dp0.."

echo Building Go CLI...
go build -o comicsplit.exe ./cmd/comicsplit
if errorlevel 1 exit /b 1

echo.
echo Go binary: comicsplit.exe
echo Run: comicsplit.exe --input comic.cbz --output panels
echo.
echo PyInstaller (optional):
echo   pip install pyinstaller
echo   pyinstaller packaging\comicsplit.spec
