"""Check restored index and meta."""
import faiss, json, sys, io
sys.stdout = io.TextIOWrapper(open('index_check.txt','wb'), encoding='utf-8')

idx = faiss.read_index('faiss_index/index.bin')
print(f'Restored index.bin: {idx.ntotal} vectors, dim={idx.d}')

meta = json.load(open('faiss_index/meta.json','r',encoding='utf-8'))
print(f'meta.json keys: {list(meta.keys())}')
docs = meta.get('documents',[])
print(f'meta.json doc count: {len(docs)}')
if docs:
    d0 = docs[0]
    print(f'First doc keys: {list(d0.keys())}')
    print(f'First doc year: {d0.get("year")}')
    evt = str(d0.get("event",""))[:100]
    print(f'First doc event: {evt}')
    # Check a few more
    for i in [10, 30, 60]:
        if i < len(docs):
            di = docs[i]
            print(f'docs[{i}]: year={di.get("year")}, event={str(di.get("event",""))[:80]}')
