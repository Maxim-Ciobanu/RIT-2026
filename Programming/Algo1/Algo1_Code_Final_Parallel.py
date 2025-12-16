import requests
import signal
import time
from time import sleep
import concurrent.futures

Port = 10012

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
    """Get current tick of the case"""
    resp = session.get(f'http://localhost:{Port}/v1/case')
    if resp.status_code == 401:
        raise ApiException('API key mismatch')
    case = resp.json()
    return case['tick'], case['status'], case['period']

def get_limits(session):
    """Get current trading limits"""
    resp = session.get(f'http://localhost:{Port}/v1/limits')
    if resp.status_code == 401:
        raise ApiException('API key mismatch')
    
    limits = resp.json()
    for limit in limits:
        if limit['name'] == 'LIMIT-STOCK':
            return limit['gross'], limit['net'], limit['gross_limit'], limit['net_limit']
    
    return 0, 0, POSITION_LIMIT, POSITION_LIMIT

def get_securities(session):
    """Get securities data"""
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
    """Submit a market order - Helper for threads"""
    params = {
        'ticker': ticker,
        'type': 'MARKET',
        'quantity': quantity,
        'action': action
    }
    
    try:
        resp = session.post(f'http://localhost:{Port}/v1/orders', params=params)
        
        if resp.status_code == 429:
            print(f"⚠️ Rate limited on {ticker}!")
            return None
        
        if resp.status_code != 200:
            print(f"⚠️ Order failed on {ticker}: {resp.json()}")
            return None
            
        return resp.json()
    except Exception as e:
        print(f"⚠️ Exception sending order to {ticker}: {e}")
        return None

def speedbump(transaction_time):
    """Calculate and apply speed bump"""
    global total_speedbumps
    global number_of_orders
    
    # Calculate speed bump for current order
    # debt = (1/rate) - (time_spent)
    order_speedbump = -transaction_time + 1/ORDER_LIMIT
    
    # Add to total debt
    total_speedbumps = total_speedbumps + order_speedbump
    
    # Increment order counter
    number_of_orders = number_of_orders + 1
    
    # Sleep if we have positive debt
    avg_speedbump = total_speedbumps / number_of_orders
    if avg_speedbump > 0:
        sleep(avg_speedbump)

def execute_arbitrage(session, buy_ticker, sell_ticker, quantity, buy_price, sell_price):
    """Execute arbitrage using PARALLEL THREADS"""
    global expected_total_profit
    
    expected_profit = (sell_price - buy_price) * quantity
    
    print(f"\n{'='*70}")
    print(f"   ARBITRAGE OPPORTUNITY DETECTED! (THREADED)")
    print(f"   Buy  {quantity:,} shares on {buy_ticker} @ ${buy_price:.2f}")
    print(f"   Sell {quantity:,} shares on {sell_ticker} @ ${sell_price:.2f}")
    print(f"   Expected profit: ${expected_profit:.2f}")
    print(f"{'='*70}")
    
    # --- STEP 1: Execute BOTH orders in PARALLEL ---
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # Submit both tasks simultaneously
        future_buy = executor.submit(submit_order, session, buy_ticker, 'BUY', quantity)
        future_sell = executor.submit(submit_order, session, sell_ticker, 'SELL', quantity)
        
        # Wait for both to complete
        buy_order = future_buy.result()
        sell_order = future_sell.result()
        
    end_time = time.time()
    elapsed = end_time - start_time
    
    # --- STEP 2: Process Results ---
    
    # Check Buy
    if buy_order:
        print(f"✅ BUY  executed: {buy_order['quantity_filled']:,} shares @ ${buy_order['vwap']:.2f} on {buy_ticker}")
    else:
        print("❌ BUY order failed!")

    # Check Sell
    if sell_order:
        print(f"✅ SELL executed: {sell_order['quantity_filled']:,} shares @ ${sell_order['vwap']:.2f} on {sell_ticker}")
    else:
        print("❌ SELL order failed!")

    if not buy_order or not sell_order:
        # Partial fill risk management would go here (e.g., dump the position)
        pass

    # --- STEP 3: Pay the Rate Limit Debt ---
    # We made 2 API calls. We must call speedbump twice.
    # 1. First call: We claim the actual elapsed time.
    speedbump(elapsed)
    
    # 2. Second call: We claim 0 time passed (since they happened simultaneously).
    #    This ensures we pay the "debt" for the second order completely in sleep.
    speedbump(0)
    
    # Calculate stats if both succeeded
    if buy_order and sell_order:
        filled_quantity = min(buy_order['quantity_filled'], sell_order['quantity_filled'])
        actual_profit = (sell_order['vwap'] - buy_order['vwap']) * filled_quantity
        expected_total_profit += expected_profit
        print(f"Actual profit: ${actual_profit:.2f}")
        print(f"{'='*70}\n")
        return True
        
    return False

def wait_for_case_start(session):
    """Wait for the case to start"""
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
        print(" ALGORITHMIC ARBITRAGE BOT - THREADED BURST MODE")
        print("="*70)
        print(f"Position Limit: ±{POSITION_LIMIT:,} shares")
        print(f"Rate Limit: {ORDER_LIMIT} orders/second")
        print("Strategy: Parallel Threading + Burst Rate Management")
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
                
                # Period Change Detection
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
                
                # Status Change Detection
                if last_status == 'ACTIVE' and status != 'ACTIVE':
                    print_period_stats(last_realized, period)
                    print(f"Case is {status}. Waiting for next period.\n")
                
                last_status = status
                
                if status != 'ACTIVE':
                    sleep(0.5)
                    continue
                
                # Get Data
                crzy_m, crzy_a, last_realized = get_securities(s)
                
                if crzy_m is None or crzy_a is None:
                    sleep(0.1)
                    continue
                
                if crzy_m['bid'] == 0 or crzy_m['ask'] == 0 or crzy_a['bid'] == 0 or crzy_a['ask'] == 0:
                    sleep(0.1)
                    continue
                
                evaluations += 1
                
                # --- ARBITRAGE LOGIC ---
                
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