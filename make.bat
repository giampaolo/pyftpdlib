@echo off

rem ==========================================================================
rem Shortcuts for various tasks, emulating UNIX "make" on Windows.
rem To use a specific Python version run:
rem     set PYTHON=C:\Python34\python.exe & make.bat test
rem ==========================================================================

if "%PYTHON%" == "" (
    set PYTHON=python
)

"%PYTHON%" scripts\internal\winmake.py %1 %2 %3 %4 %5 %6
