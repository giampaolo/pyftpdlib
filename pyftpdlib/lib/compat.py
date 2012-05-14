import sys

PY3 = sys.version_info[0] == 3

if PY3:
    import builtins

    def u(s):
        return s

    print_ = getattr(builtins, "print")
else:
    def u(s):
        return unicode(s, "unicode_escape")

    def print_(s):
        sys.stdout.write(s + '\n')
        sys.stdout.flush()
