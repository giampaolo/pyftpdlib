import os, traceback, shutil

#python_vers = ['2.5']
python_vers = ['2.3', '2.4', '2.5']

def getsitepackagedir(ver):
    if os.name == 'nt':
        return r'C:\Python%s\Lib\site-packages\pyftpdlib' %ver.replace('.', '')
    elif os.name == 'posix':
        return '/usr/lib/python%s/site-packages/pyftpdlib' %ver
    else:
        print "unknown system"
        os._exit(0)

def getpythonbin(ver):
    if os.name == 'nt':
        return r'C:\Python%s\python.exe' %ver.replace('.', '')
    elif os.name == 'posix':
        return '/usr/bin/python%s' %ver
    else:
        print "unknown system"
        os._exit(0)

def uninstall():
    for ver in python_vers:
        print "-" * 50
        print "Removing pyftpdlib from Python " + ver
        print "-" * 50
        dir = getsitepackagedir(ver)
        shutil.rmtree(dir, ignore_errors=True)

def remove_build():
    basedir = os.getcwd()
    os.chdir('..')
    try:
        shutil.rmtree('build', ignore_errors=True)
    finally:
        os.chdir(basedir)

def install():
    basedir = os.getcwd()
    os.chdir('..')
    try:
        for ver in python_vers:
            print "-" * 50
            print "Installing on Python " + ver
            print "-" * 50
            py = getpythonbin(ver)
            print py
            os.system('%s setup.py install' %py)
            print "\n\n"
            print "\n\n"
    finally:
        os.chdir(basedir)

def runtest():
    basedir = os.getcwd()
    os.chdir('..')
    os.chdir('test')
    try:
        for ver in python_vers:
            print "-" * 50
            print "Testing on: ",
            py = getpythonbin(ver)
            print os.system(r'%s -c "import sys; print sys.version"' %py)
            print "-" * 50
            test_script = os.path.join(os.getcwd(), "test_ftpd.py")
            os.system('%s "%s"' %(py, test_script))
            print "\n\n"
    finally:
        os.chdir(basedir)


def run():
    uninstall()
    remove_build()
    install()
    runtest()
    remove_build()

if __name__ == '__main__':
    run()
