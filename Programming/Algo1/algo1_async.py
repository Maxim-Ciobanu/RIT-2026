import asyncio
import aiohttp

PORT = 10001
API_KEY = 'HCYA2KPW'
URL_SEC = f'http://localhost:{PORT}/v1/securities'
URL_ORD = f'http://localhost:{PORT}/v1/orders'
URL_CASE = f'http://localhost:{PORT}/v1/case'
URL_LIM = f'http://localhost:{PORT}/v1/limits'

async def post_order(session, ticker, action, qty):
    """Fire and forget order submission"""
    async with session.post(URL_ORD, params={
        'ticker': ticker, 'type': 'MARKET', 'quantity': qty, 'action': action
    }) as r:
        return r.status

async def main():
    headers = {'X-API-Key': API_KEY}
    connector = aiohttp.TCPConnector(limit=100, limit_per_host=100, force_close=False)
    
    async with aiohttp.ClientSession(headers=headers, connector=connector) as s:
        
        print("Waiting...")
        while True:
            async with s.get(URL_CASE) as r:
                if (await r.json())['status'] == 'ACTIVE':
                    print("GO!")
                    break
            await asyncio.sleep(0.1)
        
        cap = 25000
        n = 0
        check = 0
        
        while True:
            try:
                # Get securities
                async with s.get(URL_SEC) as r:
                    sec = await r.json()
                
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
                        # TRUE PARALLEL - both orders fire simultaneously!
                        await asyncio.gather(
                            post_order(s, 'CRZY_M', 'BUY', q),
                            post_order(s, 'CRZY_A', 'SELL', q)
                        )
                        cap -= q * 2
                        n += 1
                
                # Buy A, Sell M
                elif a['ask'] < m['bid']:
                    q = min(a['ask_size'], m['bid_size'], 10000, cap)
                    if q > 0:
                        # TRUE PARALLEL - both orders fire simultaneously!
                        await asyncio.gather(
                            post_order(s, 'CRZY_A', 'BUY', q),
                            post_order(s, 'CRZY_M', 'SELL', q)
                        )
                        cap -= q * 2
                        n += 1
                
                # Periodic checks
                check += 1
                if check >= 50 or cap <= 0:
                    check = 0
                    async with s.get(URL_LIM) as r:
                        for l in await r.json():
                            if l['name'] == 'LIMIT-STOCK':
                                cap = min(l['gross_limit']-l['gross'], l['net_limit']-abs(l['net']))
                                break
                    
                    async with s.get(URL_CASE) as r:
                        if (await r.json())['status'] != 'ACTIVE':
                            print(f"Period ended. Trades: {n}")
                            while True:
                                async with s.get(URL_CASE) as r2:
                                    if (await r2.json())['status'] == 'ACTIVE':
                                        print("GO!")
                                        n = 0
                                        cap = 25000
                                        break
                                await asyncio.sleep(0.1)
            
            except KeyboardInterrupt:
                break
            except:
                pass
        
        print(f"Final: {n}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped")
