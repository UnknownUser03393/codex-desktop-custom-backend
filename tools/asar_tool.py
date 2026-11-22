import json, struct, sys, os, re

def load_header(asar):
    with open(asar,'rb') as f:
        pre = f.read(16)
        json_size = struct.unpack('<I', pre[12:16])[0]
        raw = f.read(json_size)
        base = 16 + json_size
    return json.loads(raw.decode('utf-8')), base

def walk(node, path=''):
    for name, val in node.get('files', {}).items():
        p = f"{path}/{name}" if path else name
        if 'files' in val:
            yield from walk(val, p)
        else:
            yield p, val

def read_entry(asar, base, ent):
    with open(asar,'rb') as f:
        f.seek(base + int(ent['offset']))
        return f.read(int(ent['size']))

def main():
    asar = sys.argv[1]
    mode = sys.argv[2]
    hdr, base = load_header(asar)
    entries = dict(walk(hdr))
    if mode == 'list':
        for p,v in entries.items():
            print(f"{v.get('size',0)}\t{p}")
    elif mode == 'grep':
        pat = re.compile(sys.argv[3].encode())
        for p,v in entries.items():
            if v.get('unpacked'): continue
            data = read_entry(asar, base, v)
            if pat.search(data): print(p)
    elif mode == 'ctx':
        target = sys.argv[3]; pat = re.compile(sys.argv[4].encode()); radius=int(sys.argv[5]) if len(sys.argv)>5 else 600
        data = read_entry(asar, base, entries[target])
        for m in pat.finditer(data):
            s=max(0,m.start()-radius); e=min(len(data),m.end()+radius)
            print(f"--- offset {m.start()} ---")
            print(data[s:e].decode('utf-8','replace'))
    elif mode == 'extract':
        target = sys.argv[3]; dest = sys.argv[4]
        data = read_entry(asar, base, entries[target])
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest,'wb').write(data)
        print(f"wrote {dest} ({len(data)} bytes)")

if __name__=='__main__':
    main()
