python3 -c "
import os
from collections import Counter
seen = Counter()
duplicates = {}
for root, _, files in os.walk('../uapv-cours/cours'):
    for f in files:
        if not f.lower().endswith(('.pdf', '.tex')): continue
        rel = os.path.relpath(os.path.join(root, f), '../uapv-cours/cours')
        ue = rel.split('/')[0]
        key = (ue, f)
        seen[key] += 1
        duplicates.setdefault(key, []).append(rel)

for k, n in seen.items():
    if n > 1:
        print(f'{k[0]} -- {k[1]} ({n} occurrences)')
        for p in duplicates[k]:
            print(f'    {p}')
"