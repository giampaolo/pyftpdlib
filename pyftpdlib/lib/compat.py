import sys

PY3 = sys.version_info[0] == 3

if PY3:
    def u(s):
        return s
else:
    def u(s):
        return unicode(s, "unicode_escape")
