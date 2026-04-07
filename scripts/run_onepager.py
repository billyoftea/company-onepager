import json
import subprocess
import sys

from common import resolve_company

query = ' '.join(sys.argv[1:]).strip()
if not query:
    raise SystemExit('Usage: run_onepager.py <company-name-or-ticker>')

base = '/home/lenovo/.openclaw/workspace/skills/company-onepager/scripts'
python = '/home/lenovo/.openclaw/workspace/.venv-akshare/bin/python'

resolved = resolve_company(query)
market = resolved['marketType']
identifier = resolved.get('code') or resolved.get('ticker') or resolved.get('query')

if market == 'CN':
    raw = subprocess.check_output([python, f'{base}/cn_onepager.py', identifier, json.dumps(resolved, ensure_ascii=False)], text=True)
elif market == 'HK':
    raw = subprocess.check_output([python, f'{base}/hk_onepager.py', identifier, json.dumps(resolved, ensure_ascii=False)], text=True)
else:
    raw = subprocess.check_output([python, f'{base}/us_onepager.py', identifier, json.dumps(resolved, ensure_ascii=False)], text=True)

data = json.loads(raw)
data['marketType'] = market
data['resolved'] = resolved
out = subprocess.check_output([python, f'{base}/render_onepager.py'], input=json.dumps(data, ensure_ascii=False), text=True)
print(out)
