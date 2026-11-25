"""Mo phong ti le lot inhibit va thu nguoc phuong an D. Chay tu goc repo: python docs/05-thu-nghiem/du-lieu/mo-phong-inhibit.py
Can Prometheus con du lieu dot1/dot3 va data/events."""
import sys,random,collections; sys.path.insert(0,'tools')
from lib.common import *
random.seed(7)
GE,GS=9.50,13.96
seen=lambda u,ph:u+((ph-u)%15)
R=lambda:random.uniform(0,15)
def run(case,opt,n=100000):
    c=collections.Counter()
    for _ in range(n):
        u=R(); nroot=R(); eps=[R()] if case!='nginx' else [R(),R()]; sd=R()
        ge=GS if opt=='C' else GE
        rt=seen(seen(u,nroot),GS)
        tg=[seen(seen(u,s),ge) for s in eps]            # EndpointDown bắn (bỏ for 30s chung)
        if case=='nginx': tg.append(seen(seen(u,sd),GS)) # ServiceDown cũng là hệ quả
        wait={'now':5,'C':5,'B25':25,'B35':35}.get(opt,5)
        if opt=='A':   # EndpointDown for 60s thay vì 30s (ServiceDown giữ 30s)
            tg=[x+30 for x in tg[:len(eps)]]+tg[len(eps):]
        # gốc tới tay AM trước khi nhóm hệ quả hết group_wait thì bị chặn; gốc keep_firing giữ chặn
        leak=any(rt-x>wait for x in tg)
        c[leak]+=1
    return round(100*c[True]/n,1)
for case in ('nginx','demo-app','postgresql'):
    print(case,{o:run(case,o) for o in ('now','A','B25','B35','C')})
# --- thử ngược phương án D trên dữ liệu đã ghi (bước 1 s = không phụ thuộc pha đánh giá)
D_ep='(probe_success{job=~"blackbox-http|blackbox-tcp"}==0) unless on(host) (nginx_up==0 or pg_up==0) unless on(host,service) (up{job="demo-app"}==0)'
D_sd='(up{job="demo-app"}==0) unless on(host) (nginx_up==0)'
NOW_ep='probe_success{job=~"blackbox-http|blackbox-tcp"}==0'
def longest(expr,t0,t1):
    best=0
    for s in prom_query_range(expr,t0,t1,1):
        ts=sorted({float(v[0]) for v in s['values']}); run_=0; prev=None
        for t in ts:
            run_=run_+1 if prev is not None and t-prev<1.5 else 0
            best=max(best,run_); prev=t
    return best
E=[e for e in load_events() if e.get('suite') in('gd3-dot1','gd3-dot3')]
agg=collections.defaultdict(list)
for e in E:
    t0=e['injected_ts_receiver']-5; t1=e['recovered_ts_receiver']+60
    r=(longest(NOW_ep,t0,t1),longest(D_ep,t0,t1),longest(D_sd,t0,t1))
    agg[e['suite'],e['case']].append(r)
for k in sorted(agg): print(k,'max giây đúng liên tục: EndpointDown hiện tại',max(x[0] for x in agg[k]),'| D',max(x[1] for x in agg[k]),'| ServiceDown D',max(x[2] for x in agg[k]))
