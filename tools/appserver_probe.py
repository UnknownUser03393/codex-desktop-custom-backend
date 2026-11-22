import json, os, subprocess, sys, threading, time, queue

EXE = sys.argv[1]
CODEX_HOME = sys.argv[2]
CMD = json.loads(sys.argv[3])
CWD = sys.argv[4]

env = dict(os.environ)
env["CODEX_HOME"] = CODEX_HOME
env["RUST_LOG"] = "warn"
env.pop("CODEX_CLI_PATH", None)

p = subprocess.Popen([EXE, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE, env=env, text=True, encoding="utf-8", errors="replace")

q = queue.Queue()
def reader(stream, tag):
    for line in stream:
        q.put((tag, line.rstrip("\n")))
threading.Thread(target=reader, args=(p.stdout, "OUT"), daemon=True).start()
threading.Thread(target=reader, args=(p.stderr, "ERR"), daemon=True).start()

def send(obj):
    p.stdin.write(json.dumps(obj) + "\n")
    p.stdin.flush()

def wait_id(target, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        try:
            tag, line = q.get(timeout=0.5)
        except queue.Empty:
            continue
        if tag == "ERR":
            print("STDERR:", line)
            continue
        print("OUT:", line)
        try:
            m = json.loads(line)
        except Exception:
            continue
        if m.get("id") == target:
            return m
    return None

send({"id": 1, "method": "initialize", "params": {
    "clientInfo": {"name": "probe", "title": "probe", "version": "1.0"},
    "capabilities": {"experimentalApi": True}}})
r1 = wait_id(1)
print("INIT_RESULT:", json.dumps(r1)[:500] if r1 else "TIMEOUT")

send({"id": 2, "method": "command/exec", "params": {
    "command": CMD, "cwd": CWD, "disableTimeout": True}})
r2 = wait_id(2, timeout=120)
print("EXEC_RESULT:", json.dumps(r2) if r2 else "TIMEOUT")

try:
    p.terminate()
except Exception:
    pass
