import requests

PORT = 10007
s = requests.Session()
s.headers.update({'X-API-Key': 'HCYA2KPW'})

URL_SEC = f'http://localhost:{PORT}/v1/securities'
URL_ORD = f'http://localhost:{PORT}/v1/orders'
URL_CASE = f'http://localhost:{PORT}/v1/case'
URL_LIM = f'http://localhost:{PORT}/v1/limits'

# Wait for start
print("Waiting...")
while s.get(URL_CASE).json()['status'] != 'ACTIVE': pass
print("GO!")

cap = 25000
n = 0

while True:
    try:
        sec = s.get(URL_SEC).json()
        m = a = None
        for x in sec:
            if x['ticker'] == 'CRZY_M': m = x
            elif x['ticker'] == 'CRZY_A': a = x
        
        if not m or not a or m['bid'] == 0 or a['bid'] == 0:
            continue
        
        # Buy M, Sell A
        if m['ask'] < a['bid']:
            q = min(m['ask_size'], a['bid_size'], 10000, cap)
            if q > 0:
                s.post(URL_ORD, params={'ticker':'CRZY_M','type':'MARKET','quantity':q,'action':'BUY'})
                s.post(URL_ORD, params={'ticker':'CRZY_A','type':'MARKET','quantity':q,'action':'SELL'})
                cap -= q*2
                n += 1
        
        # Buy A, Sell M
        elif a['ask'] < m['bid']:
            q = min(a['ask_size'], m['bid_size'], 10000, cap)
            if q > 0:
                s.post(URL_ORD, params={'ticker':'CRZY_A','type':'MARKET','quantity':q,'action':'BUY'})
                s.post(URL_ORD, params={'ticker':'CRZY_M','type':'MARKET','quantity':q,'action':'SELL'})
                cap -= q*2
                n += 1
        
        # Refresh limits occasionally
        if n % 20 == 0 or cap <= 0:
            for l in s.get(URL_LIM).json():
                if l['name'] == 'LIMIT-STOCK':
                    cap = min(l['gross_limit']-l['gross'], l['net_limit']-abs(l['net']))
            if s.get(URL_CASE).json()['status'] != 'ACTIVE':
                print(f"Trades: {n}")
                while s.get(URL_CASE).json()['status'] != 'ACTIVE': pass
                print("GO!")
                n = 0
                cap = 25000
    except KeyboardInterrupt:
        break
    except:
        pass

print(f"Final: {n}")
