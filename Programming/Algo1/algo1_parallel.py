import requests
import signal
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# CONFIGURATION
PORT = 10007
API_KEY = {'X-API-Key': 'HCYA2KPW'}
MAX_ORDER_SIZE = 10000
POSITION_LIMIT = 25000

# Pre-computed URLs
URL_CASE = f'http://localhost:{PORT}/v1/case'
URL_SECURITIES = f'http://localhost:{PORT}/v1/securities'
URL_LIMITS = f'http://localhost:{PORT}/v1/limits'
URL_ORDERS = f'http://localhost:{PORT}/v1/orders'

shutdown = False
trades = 0

def signal_handler(signum, frame):
    global shutdown
    shutdown = True

def submit_order(session, ticker, action, quantity):
    """Submit order - used by thread pool"""
    try:
        r = session.post(URL_ORDERS, params={
            'ticker': ticker,
            'type': 'MARKET',
            'quantity': quantity,
            'action': action
        })
        if r.status_code == 429:
            time.sleep(r.json().get('wait', 0.1))
            # Retry once
            r = session.post(URL_ORDERS, params={
                'ticker': ticker,
                'type': 'MARKET',
                'quantity': quantity,
                'action': action
            })
        return r.status_code == 200
    except:
        return False

def main():
    global trades
    
    # Create session
    s = requests.Session()
    s.headers.update(API_KEY)
    
    # Thread pool for parallel order submission
    executor = ThreadPoolExecutor(max_workers=2)
    
    # Pre-bind for speed
    s_get = s.get
    
    print("PARALLEL RACE MODE - Waiting...")
    
    # Wait for active
    while not shutdown:
        try:
            if s_get(URL_CASE).json()['status'] == 'ACTIVE':
                print("GO!")
                break
        except:
            pass
    
    remaining = POSITION_LIMIT
    check_ctr = 0
    
    while not shutdown:
        try:
            # Get quotes
            securities = s_get(URL_SECURITIES).json()
            
            m_bid = m_ask = m_bid_sz = m_ask_sz = 0
            a_bid = a_ask = a_bid_sz = a_ask_sz = 0
            
            for sec in securities:
                t = sec['ticker']
                if t == 'CRZY_M':
                    m_bid, m_ask = sec['bid'], sec['ask']
                    m_bid_sz, m_ask_sz = sec['bid_size'], sec['ask_size']
                elif t == 'CRZY_A':
                    a_bid, a_ask = sec['bid'], sec['ask']
                    a_bid_sz, a_ask_sz = sec['bid_size'], sec['ask_size']
            
            if m_bid == 0 or a_bid == 0:
                continue
            
            # ARBITRAGE CHECK AND PARALLEL EXECUTION
            
            if m_ask < a_bid:
                qty = min(m_ask_sz, a_bid_sz, MAX_ORDER_SIZE, remaining)
                if qty > 0:
                    # Submit BOTH orders in parallel!
                    f1 = executor.submit(submit_order, s, 'CRZY_M', 'BUY', qty)
                    f2 = executor.submit(submit_order, s, 'CRZY_A', 'SELL', qty)
                    # Wait for both to complete
                    f1.result()
                    f2.result()
                    trades += 1
                    remaining -= qty * 2
            
            elif a_ask < m_bid:
                qty = min(a_ask_sz, m_bid_sz, MAX_ORDER_SIZE, remaining)
                if qty > 0:
                    # Submit BOTH orders in parallel!
                    f1 = executor.submit(submit_order, s, 'CRZY_A', 'BUY', qty)
                    f2 = executor.submit(submit_order, s, 'CRZY_M', 'SELL', qty)
                    f1.result()
                    f2.result()
                    trades += 1
                    remaining -= qty * 2
            
            # Periodic checks
            check_ctr += 1
            if check_ctr >= 50 or remaining <= 0:
                check_ctr = 0
                try:
                    for lim in s_get(URL_LIMITS).json():
                        if lim['name'] == 'LIMIT-STOCK':
                            remaining = min(
                                lim['gross_limit'] - lim['gross'],
                                lim['net_limit'] - abs(lim['net'])
                            )
                            break
                    
                    c = s_get(URL_CASE).json()
                    if c['status'] != 'ACTIVE':
                        print(f"Period ended. Trades: {trades}")
                        while not shutdown:
                            if s_get(URL_CASE).json()['status'] == 'ACTIVE':
                                print("New period! GO!")
                                trades = 0
                                remaining = POSITION_LIMIT
                                break
                            time.sleep(0.5)
                except:
                    pass
        
        except KeyboardInterrupt:
            break
        except:
            pass
    
    executor.shutdown(wait=False)
    print(f"Done. Trades: {trades}")
    s.close()

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    main()
