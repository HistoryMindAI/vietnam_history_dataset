import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open('faiss_index/meta.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

docs = data['documents']

for i, d in enumerate(docs[:20]):
    story = d.get('story', '')
    print(f"=== [{d['id']}] Y:{d['year']} ===")
    print(f"{story[:500]}")
    print()
