import requests
import signal
import time
from time import sleep

Port = 10010

class ApiException(Exception):
    pass

# Signal handler for graceful shutdown
def signal_handler(signum, frame):
    global shutdown
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    shutdown = True

# Set API key
API_KEY = {'X-API-Key': 'HCYA2KPW'}
shutdown = False

# Trading parameters
ORDER_LIMIT = 10  # orders per second
MAX_ORDER_SIZE = 10000
POSITION_LIMIT = 25000

# Speed bump tracking
number_of_orders = 0
total_speedbumps = 0

# Statistics tracking
opportunities_found = 0
trades_executed = 0
evaluations = 0
expected_total_profit = 0

def get_tick(session):
    resp = session.get(f'http://localhost:{Port}/v1/case')
    if resp.status_code == 401:
        raise ApiException('API key mismatch')
    case = resp.json()
    return case['tick'], case['status'], case['period']

def get_limits(session):
    resp = session.get(f'http://localhost:{Port}/v1/limits')
    if resp.status_code == 401:
        raise ApiException('API key mismatch')
    
    limits = resp.json()
    for limit in limits:
        if limit['name'] == 'LIMIT-STOCK':
            return limit['gross'], limit['net'], limit['gross_limit'], limit['net_limit']
    
    return 0, 0, POSITION_LIMIT, POSITION_LIMIT

def get_securities(session):
    resp = session.get(f'http://localhost:{Port}/v1/securities')
    if resp.status_code == 401:
        raise ApiException('API key mismatch')
    
    securities = resp.json()
    crzy_m = None
    crzy_a = None
    total_realized = 0
    
    for security in securities:
        if security['ticker'] == 'CRZY_M':
            crzy_m = security
        elif security['ticker'] == 'CRZY_A':
            crzy_a = security
        
        if security['ticker'] in ['CRZY_M', 'CRZY_A']:
            total_realized += security.get('realized', 0)
    
    return crzy_m, crzy_a, total_realized/2

def submit_order(session, ticker, action, quantity):
    """Submit a market order"""
    params = {
        'ticker': ticker,
        'type': 'MARKET',
        'quantity': quantity,
        'action': action
    }
    
    resp = session.post(f'http://localhost:{Port}/v1/orders', params=params)
    
    if resp.status_code == 429:
        wait_time = resp.json().get('wait', 1)
        print(f"⚠️ Rate limited! Waiting {wait_time:.2f} seconds...")
        sleep(wait_time)
        return None
    
    if resp.status_code != 200:
        print(f"⚠️ Order failed: {resp.json()}")
        return None
    
    return resp.json()

def speedbump(transaction_time):
    """Calculate and apply speed bump"""
    global total_speedbumps
    global number_of_orders
    
    # Calculate speed bump for current order
    order_speedbump = -transaction_time + 1/ORDER_LIMIT
    
    # Add to total
    total_speedbumps = total_speedbumps + order_speedbump
    
    # Increment order counter
    number_of_orders = number_of_orders + 1
    
    # Sleep for average speed bump (only if positive)
    avg_speedbump = total_speedbumps / number_of_orders
    if avg_speedbump > 0:
        sleep(avg_speedbump)

def execute_arbitrage(session, buy_ticker, sell_ticker, quantity, buy_price, sell_price):
    """Execute arbitrage: Buy then Sell IMMEDIATELY, then sleep"""
    global expected_total_profit
    
    expected_profit = (sell_price - buy_price) * quantity
    
    print(f"\n{'='*70}")
    print(f"   ARBITRAGE OPPORTUNITY DETECTED!")
    print(f"   Buy  {quantity:,} shares on {buy_ticker} @ ${buy_price:.2f}")
    print(f"   Sell {quantity:,} shares on {sell_ticker} @ ${sell_price:.2f}")
    print(f"   Expected profit: ${expected_profit:.2f}")
    print(f"{'='*70}")
    
    # --- STEP 1: Execute BUY ---
    start_time = time.time()
    buy_order = submit_order(session, buy_ticker, 'BUY', quantity)
    buy_time = time.time() - start_time
    
    if buy_order is None:
        print("❌ BUY order failed!")
        return False
    
    print(f"✅ BUY  executed: {buy_order['quantity_filled']:,} shares @ ${buy_order['vwap']:.2f} on {buy_ticker}")
    
    # --- STEP 2: Execute SELL (IMMEDIATELY - No sleep yet!) ---
    # We do not call speedbump() here intentionally to reduce leg risk
    start_time = time.time()
    sell_order = submit_order(session, sell_ticker, 'SELL', quantity)
    sell_time = time.time() - start_time
    
    if sell_order is None:
        print("❌ SELL order failed! (Partial execution risk)")
        # Even though sell failed, we must speedbump for the buy that succeeded
        # to ensure we don't violate rate limits for future orders.
        speedbump(buy_time)
        return False
    
    print(f"✅ SELL executed: {sell_order['quantity_filled']:,} shares @ ${sell_order['vwap']:.2f} on {sell_ticker}")
    
    # --- STEP 3: Pay the Rate Limit Debt ---
    # Now that both trades are safely sent, we sleep for the accumulated time required.
    speedbump(buy_time)   # Account for the buy order
    speedbump(sell_time)  # Account for the sell order
    
    # Calculate actual profit
    filled_quantity = min(buy_order['quantity_filled'], sell_order['quantity_filled'])
    actual_profit = (sell_order['vwap'] - buy_order['vwap']) * filled_quantity
    
    expected_total_profit += expected_profit
    
    print(f"Actual profit: ${actual_profit:.2f}")
    print(f"{'='*70}\n")
    
    return True

def wait_for_case_start(session):
    print("⏳ Waiting for case to start...")
    last_tick = -1
    while not shutdown:
        try:
            tick, status, period = get_tick(session)
            if status == 'ACTIVE':
                if tick > last_tick or tick == 0:
                    print(f"✅ Case is ACTIVE! Period {period}, Tick {tick}")
                    return True
                else:
                    print(f"   Case ACTIVE but ticks not moving... Tick: {tick}")
            else:
                print(f"   Case status: {status}, waiting...")
            last_tick = tick
            sleep(0.5)
        except Exception as e:
            print(f"   Error checking case status: {e}")
            sleep(2)
    return False

def print_period_stats(realized_profit, period):
    print("\n" + "="*70)
    print(f"   PERIOD {period} COMPLETED - Statistics:")
    print(f"   Evaluations: {evaluations}")
    print(f"   Opportunities found: {opportunities_found}")
    print(f"   Trades executed: {trades_executed}")
    print(f"   Total orders submitted: {number_of_orders}")
    print(f"   Expected total profit: ${expected_total_profit:.2f}")
    print(f"   Actual realized profit: ${realized_profit:.2f}")
    print("="*70 + "\n")

def main():
    global shutdown, opportunities_found, trades_executed, evaluations, expected_total_profit
    global number_of_orders, total_speedbumps
    
    with requests.Session() as s:
        s.headers.update(API_KEY)
        gross_position, net_position, gross_limit, net_limit = get_limits(s)
        
        print("\n" + "="*70)
        print(" ALGORITHMIC ARBITRAGE BOT - BURST MODE")
        print("="*70)
        print(f"Position Limit: ±{POSITION_LIMIT:,} shares")
        print(f"Rate Limit: {ORDER_LIMIT} orders/second (Bursting enabled)")
        print("="*70 + "\n")
        
        if not wait_for_case_start(s):
            return
        
        print("Bot started\n")
        
        last_period = 0
        last_status = 'ACTIVE'
        last_realized = 0
        
        while not shutdown:
            try:
                tick, status, period = get_tick(s)
                
                if period != last_period:
                    if last_period > 0:
                        print_period_stats(last_realized, last_period)
                        print(f"Starting new period {period}\n")
                        opportunities_found = 0
                        trades_executed = 0
                        evaluations = 0
                        expected_total_profit = 0
                        number_of_orders = 0
                        total_speedbumps = 0
                    last_period = period
                
                if last_status == 'ACTIVE' and status != 'ACTIVE':
                    print_period_stats(last_realized, period)
                    print(f"Case is {status}. Waiting for next period.\n")
                
                last_status = status
                
                if status != 'ACTIVE':
                    sleep(0.5)
                    continue
                
                crzy_m, crzy_a, last_realized = get_securities(s)
                
                if crzy_m is None or crzy_a is None:
                    sleep(0.1)
                    continue
                
                if crzy_m['bid'] == 0 or crzy_m['ask'] == 0 or crzy_a['bid'] == 0 or crzy_a['ask'] == 0:
                    sleep(0.1)
                    continue
                
                evaluations += 1
                
                # Check Arbitrage M -> A
                if crzy_m['ask'] < crzy_a['bid']:
                    opportunities_found += 1
                    max_quantity = min(crzy_m['ask_size'], crzy_a['bid_size'], MAX_ORDER_SIZE)
                    if max_quantity > 0:
                        if execute_arbitrage(s, 'CRZY_M', 'CRZY_A', max_quantity, crzy_m['ask'], crzy_a['bid']):
                            trades_executed += 1

                # Check Arbitrage A -> M
                elif crzy_a['ask'] < crzy_m['bid']:
                    opportunities_found += 1
                    max_quantity = min(crzy_a['ask_size'], crzy_m['bid_size'], MAX_ORDER_SIZE)
                    if max_quantity > 0:
                        if execute_arbitrage(s, 'CRZY_A', 'CRZY_M', max_quantity, crzy_a['ask'], crzy_m['bid']):
                            trades_executed += 1
                
                elif evaluations % 20 == 0:
                    print(f"[Tick {tick:3d}] Evaluation #{evaluations}: No arbitrage")
                
            except KeyboardInterrupt:
                shutdown = True
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                sleep(0.5)
        
        print("Bot manually stopped.")

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    main()