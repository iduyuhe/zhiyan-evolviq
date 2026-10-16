import subprocess, sys, os

def find_pptx(args):
    for a in args:
        if a.endswith('.pptx') and not a.startswith('-'):
            return a
    return None

def run(args):
    pptx = find_pptx(args)
    cwd = os.path.dirname(os.path.abspath(pptx)) if pptx else os.getcwd()
    cmd = [r"C:\Users\Administrator\.workbuddy\binaries\node\versions\22.22.2-3\slidep.cmd"] + args
    print("CWD:", cwd)
    print("CMD:", " ".join(f'"{a}"' if ' ' in a else a for a in cmd))
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd)
    print("---STDOUT---")
    print(p.stdout)
    if p.stderr.strip():
        print("---STDERR---")
        print(p.stderr)
    print("---RC---", p.returncode)
    return p.returncode

if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
