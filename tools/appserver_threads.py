import json, os, subprocess, sys, threading, time, queue

EXE = sys.argv[1]; CODEX_HOME = sys.argv[2]; LIMIT = int(sys.argv[3]) if len(sys.argv)>3 else 5
env = dict(os.environ); env["CODEX_HOME"]=CODEX_HOME; env["RUST_LOG"]="error"; env.pop("CODEX_CLI_PATH",None)
p = subprocess.Popen([EXE,"app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                     env=env, text=True, encoding="utf-8", errors="replace")
q=queue.Queue()
def rd(s,t):
    for line in s: q.put((t,line.rstrip("\n")))
threading.Thread(target=rd,args=(p.stdout,"OUT"),daemon=True).start()
threading.Thread(target=rd,args=(p.stderr,"ERR"),daemon=True).start()
def send(o): p.stdin.write(json.dumps(o)+"\n"); p.stdin.flush()
def wait(i,timeout=60):
    end=time.time()+timeout
    while time.time()<end:
        try: t,l=q.get(timeout=0.5)
        except queue.Empty: continue
        if t=="ERR":
            if "error" in l.lower() or "Error" in l: print("STDERR:",l)
            continue
        try: m=json.loads(l)
        except: continue
        if m.get("id")==i: return m
    return None
send({"id":1,"method":"initialize","params":{"clientInfo":{"name":"probe","title":"probe","version":"1.0"},"capabilities":{"experimentalApi":True}}})
print("INIT:", json.dumps(wait(1))[:300])
send({"id":2,"method":"thread/list","params":{"limit":LIMIT}})
r=wait(2)
if not r: print("THREADS: TIMEOUT")
else:
    data=r.get("result",{}); ts=data.get("data") or data.get("threads") or []
    print("THREAD_COUNT_RETURNED:", len(ts))
    for t in ts:
        print(" -", t.get("id"), "|", (t.get("title") or "")[:60], "|", t.get("updatedAt") or t.get("updated_at"))
try: p.terminate()
except: pass
