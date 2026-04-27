import json, sys, subprocess, tempfile

CODE = "def divide(a, b):\n    if b == 0:\n        raise ZeroDivisionError()\n    return float(a) / float(b)\n"

with open('/tmp/target.py', 'w') as f:
    f.write(CODE)

DRIVER = (
    "import importlib.util\n"
    "spec = importlib.util.spec_from_file_location('t', '/tmp/target.py')\n"
    "mod = importlib.util.module_from_spec(spec)\n"
    "spec.loader.exec_module(mod)\n"
    "fn = mod.divide\n"
    "try: fn(1, 0)\n"
    "except Exception: pass\n"
    "try: fn(10, 2)\n"
    "except Exception: pass\n"
)

with open('/tmp/driver.py', 'w') as f:
    f.write(DRIVER)

r1 = subprocess.run(
    ['python', '-m', 'coverage', 'run', '--branch', '--source=/tmp/target.py', '/tmp/driver.py'],
    capture_output=True, text=True
)
r2 = subprocess.run(
    ['python', '-m', 'coverage', 'json', '-o', '/tmp/cov.json', '--quiet'],
    capture_output=True, text=True
)
print("run stderr:", r1.stderr[:300] or "(none)")
print("json stderr:", r2.stderr[:300] or "(none)")
try:
    d = json.load(open('/tmp/cov.json'))
    files = d.get('files', {})
    print("files:", list(files.keys()))
    if files:
        summary = list(files.values())[0]['summary']
        print("summary:", summary)
except Exception as e:
    print("parse error:", e)
