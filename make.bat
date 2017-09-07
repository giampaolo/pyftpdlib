@echo off

rem ==========================================================================
rem Shortcuts for various tasks, emulating UNIX "make" on Windows.
rem It is primarly intended as a shortcut for installing pyftpdlib and running
rem tests (just run "make.bat test").
rem By default C:\Python27\python.exe is used.
rem To use another Python version run:
rem     set PYTHON=C:\Python24\python.exe & make.bat test
rem ==========================================================================


if "%PYTHON%" == "" (
    set PYTHON=C:\Python27\python.exe
)
if "%TSCRIPT%" == "" (
    set TSCRIPT=pyftpdlib\test\runner.py
)


if "%1" == "help" (
    :help
    echo Run `make ^<target^>` where ^<target^> is one of:
    echo   clean         clean build files
    echo   install       compile and install
    echo   uninstall     uninstall
    echo   test          run tests
    echo   setup-dev-env install all deps
    goto :eof
)

if "%1" == "clean" (
    :clean
    for /r %%R in (__pycache__) do if exist %%R (rmdir /S /Q %%R)
    for /r %%R in (*.pyc) do if exist %%R (del /s %%R)
    for /r %%R in (*.pyd) do if exist %%R (del /s %%R)
    for /r %%R in (*.orig) do if exist %%R (del /s %%R)
    for /r %%R in (*.bak) do if exist %%R (del /s %%R)
    for /r %%R in (*.rej) do if exist %%R (del /s %%R)
    if exist pyftpdlib.egg-info (rmdir /S /Q pyftpdlib.egg-info)
    if exist build (rmdir /S /Q build)
    if exist dist (rmdir /S /Q dist)
    goto :eof
)

if "%1" == "install" (
    :install
    if %PYTHON%==C:\Python24\python.exe (
        %PYTHON% setup.py build -c mingw32 install
    ) else if %PYTHON%==C:\Python25\python.exe (
        %PYTHON% setup.py build -c mingw32 install
    ) else (
        %PYTHON% setup.py build install
    )
    goto :eof
)

if "%1" == "uninstall" (
    :uninstall
    rmdir /S /Q %PYTHON%\Lib\site-packages\pyftpdlib*
    goto :eof
)

if "%1" == "test" (
    :test
    call :install
    %PYTHON% %TSCRIPT%
    goto :eof
)

if "%1" == "setup-dev-env" (
    :setup-env
    if not exist get-pip.py (
        @echo ------------------------------------------------
        @echo downloading pip installer
        @echo ------------------------------------------------
        C:\python27\python.exe -c "import urllib2; r = urllib2.urlopen('https://bootstrap.pypa.io/get-pip.py'); open('get-pip.py', 'wb').write(r.read())"
    )
    @echo ------------------------------------------------
    @echo installing pip for %PYTHON%
    @echo ------------------------------------------------
    %PYTHON% get-pip.py
    @echo ------------------------------------------------
    @echo upgrade pip for %PYTHON%
    @echo ------------------------------------------------
    %PYTHON% -m pip install pip --upgrade
    @echo ------------------------------------------------
    @echo installing deps
    @echo ------------------------------------------------
    rem mandatory / for unittests
    %PYTHON% -m pip install unittest2 ipaddress mock wmi pypiwin32 pyopenssl --upgrade
    goto :eof
)


goto :help

:error
    echo last command returned an error; exiting
    exit /b %errorlevel%
