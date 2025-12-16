import requests
import signal
import time

# CONFIGURATION
PORT = 10007
API_KEY = {'X-API-Key': 'HCYA2KPW'}
MAX_ORDER_SIZE = 10000
POSITION_LIMIT = 25000

# Pre-computed URLs (string formatting is slow)
URL_CASE = f'http://localhost:{PORT}/v1/case'
URL_SECURITIES = f'http://localhost:{PORT}/v1/securities'
URL_LIMITS = f'http://localhost:{PORT}/v1/limits'
URL_ORDERS = f'http://localhost:{PORT}/v1/orders'

# Global state
shutdown = False
trades = 0

def signal_handler(signum, frame):
    global shutdown
    shutdown = True

def main():
    global trades
    
    # Create session with optimized settings
    s = requests.Session()
    s.headers.update(API_KEY)
    
    # Pre-bind methods (avoid attribute lookup in hot loop)
    s_get = s.get
    s_post = s.post
    
    print("RACE MODE - Waiting for case...")
    
    # Wait for case to be active
    while not shutdown:
        try:
            r = s_get(URL_CASE)
            c = r.json()
            if c['status'] == 'ACTIVE':
                print(f"GO! Period {c['period']}")
                break
        except:
            pass
    
    # Cache for limits - don't check every iteration
    remaining_capacity = POSITION_LIMIT
    limit_check_counter = 0
    
    # Main racing loop
    while not shutdown:
        try:
            # Get securities - ONE call for everything
            r = s_get(URL_SECURITIES)
            securities = r.json()
            
            # Fast extraction - direct loop, no dict building
            m_bid = m_ask = m_bid_sz = m_ask_sz = 0
            a_bid = a_ask = a_bid_sz = a_ask_sz = 0
            
            for sec in securities:
                t = sec['ticker']
                if t == 'CRZY_M':
                    m_bid = sec['bid']
                    m_ask = sec['ask']
                    m_bid_sz = sec['bid_size']
                    m_ask_sz = sec['ask_size']
                elif t == 'CRZY_A':
                    a_bid = sec['bid']
                    a_ask = sec['ask']
                    a_bid_sz = sec['bid_size']
                    a_ask_sz = sec['ask_size']
            
            # Skip if no valid quotes
            if m_bid == 0 or a_bid == 0:
                continue
            
            # CHECK ARBITRAGE AND EXECUTE IMMEDIATELY
            
            # Opportunity 1: Buy Main, Sell Alternate
            if m_ask < a_bid:
                qty = min(m_ask_sz, a_bid_sz, MAX_ORDER_SIZE, remaining_capacity)
                if qty > 0:
                    # BUY IMMEDIATELY
                    r1 = s_post(URL_ORDERS, params={
                        'ticker': 'CRZY_M',
                        'type': 'MARKET',
                        'quantity': qty,
                        'action': 'BUY'
                    })
                    # SELL IMMEDIATELY
                    r2 = s_post(URL_ORDERS, params={
                        'ticker': 'CRZY_A',
                        'type': 'MARKET',
                        'quantity': qty,
                        'action': 'SELL'
                    })
                    
                    # Handle rate limit only if it happens
                    if r1.status_code == 429:
                        time.sleep(r1.json().get('wait', 0.1))
                    if r2.status_code == 429:
                        time.sleep(r2.json().get('wait', 0.1))
                    
                    trades += 1
                    remaining_capacity -= qty * 2
            
            # Opportunity 2: Buy Alternate, Sell Main
            elif a_ask < m_bid:
                qty = min(a_ask_sz, m_bid_sz, MAX_ORDER_SIZE, remaining_capacity)
                if qty > 0:
                    # BUY IMMEDIATELY
                    r1 = s_post(URL_ORDERS, params={
                        'ticker': 'CRZY_A',
                        'type': 'MARKET',
                        'quantity': qty,
                        'action': 'BUY'
                    })
                    # SELL IMMEDIATELY
                    r2 = s_post(URL_ORDERS, params={
                        'ticker': 'CRZY_M',
                        'type': 'MARKET',
                        'quantity': qty,
                        'action': 'SELL'
                    })
                    
                    # Handle rate limit only if it happens
                    if r1.status_code == 429:
                        time.sleep(r1.json().get('wait', 0.1))
                    if r2.status_code == 429:
                        time.sleep(r2.json().get('wait', 0.1))
                    
                    trades += 1
                    remaining_capacity -= qty * 2
            
            # Only check limits occasionally (every 50 iterations)
            limit_check_counter += 1
            if limit_check_counter >= 50 or remaining_capacity <= 0:
                limit_check_counter = 0
                try:
                    r = s_get(URL_LIMITS)
                    for lim in r.json():
                        if lim['name'] == 'LIMIT-STOCK':
                            remaining_capacity = min(
                                lim['gross_limit'] - lim['gross'],
                                lim['net_limit'] - abs(lim['net'])
                            )
                            break
                except:
                    pass
                
                # Also check if case ended
                try:
                    r = s_get(URL_CASE)
                    c = r.json()
                    if c['status'] != 'ACTIVE':
                        print(f"Case ended. Trades: {trades}")
                        # Wait for next period
                        while not shutdown:
                            r = s_get(URL_CASE)
                            c = r.json()
                            if c['status'] == 'ACTIVE':
                                print(f"New period {c['period']}! GO!")
                                trades = 0
                                remaining_capacity = POSITION_LIMIT
                                break
                            time.sleep(0.5)
                except:
                    pass
        
        except KeyboardInterrupt:
            break
        except:
            pass  # Never stop for errors
    
    print(f"Stopped. Total trades: {trades}")
    s.close()

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    main()
