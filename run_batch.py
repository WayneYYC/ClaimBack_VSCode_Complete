"""Drive real HTTP app runs for PRISM validation. No synthetic PRISM records are fabricated."""
import argparse
import json
import time
import urllib.error
import urllib.request

p=argparse.ArgumentParser(description='Trigger genuine ClaimBack agent runs')
p.add_argument('--mode',choices=['demo','live'],default='live')
p.add_argument('--version',choices=['v1','v2'],default='v1')
p.add_argument('--cases',default='CB-0005,CB-0010,CB-0015')
p.add_argument('--repeat',type=int,default=1)
p.add_argument('--url',default='http://localhost:8000')
args=p.parse_args()
ids=[x.strip() for x in args.cases.split(',') if x.strip()]
if not ids or args.repeat<1 or args.repeat>100:
    p.error('Provide 1+ case IDs and repeat between 1 and 100')
if args.mode=='demo':print('DEMO MODE: these runs are local and DO NOT generate PRISM proof or use Nicrron.')
for i in range(args.repeat):
    for case in ids:
        url=f'{args.url}/api/investigate/{case}?mode={args.mode}&version={args.version}'
        req=urllib.request.Request(url,method='POST')
        try:
            with urllib.request.urlopen(req,timeout=90) as resp:
                data=json.loads(resp.read().decode());print(f'{case} {args.version}: SUCCESS run={data["run_id"]} recommendation={data["recommendation"]}')
        except urllib.error.HTTPError as exc:
            raw=exc.read().decode();
            try:body=json.loads(raw).get('detail',raw)
            except ValueError:body=raw
            print(f'{case} {args.version}: ERROR {exc.code}: {str(body)[:220]}')
        except Exception as exc:
            print(f'{case} {args.version}: {exc}')
