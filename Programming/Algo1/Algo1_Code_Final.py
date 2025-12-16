import requests
import signal
import time
from time import sleep

Port = 10011

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
ORDER_LIMIT = 10  # orders per second (adjust based on actual rate limit)
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
    """
    Get securities data - ONE API call for both tickers!
    Returns bid, ask, bid_size, ask_size for both CRZY_M and CRZY_A
    Also returns realized profit
    """
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
        
        # Sum up realized profits while we're at it
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
        # Rate limited
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
    """Execute arbitrage by buying on one exchange and selling on the other"""
    global expected_total_profit
    
    expected_profit = (sell_price - buy_price) * quantity
    
    print(f"\n{'='*70}")
    print(f"   ARBITRAGE OPPORTUNITY DETECTED!")
    print(f"   Buy  {quantity:,} shares on {buy_ticker} @ ${buy_price:.2f}")
    print(f"   Sell {quantity:,} shares on {sell_ticker} @ ${sell_price:.2f}")
    print(f"   Expected profit: ${expected_profit:.2f}")
    print(f"{'='*70}")
    
    # Execute buy order
    start_time = time.time()
    buy_order = submit_order(session, buy_ticker, 'BUY', quantity)
    buy_time = time.time() - start_time
    
    if buy_order is None:
        print("❌ BUY order failed!")
        return False
    
    print(f"✅ BUY  executed: {buy_order['quantity_filled']:,} shares @ ${buy_order['vwap']:.2f} on {buy_ticker}")
    speedbump(buy_time)
    
    # Execute sell order
    start_time = time.time()
    sell_order = submit_order(session, sell_ticker, 'SELL', quantity)
    sell_time = time.time() - start_time
    
    if sell_order is None:
        print("❌ SELL order failed!")
        return False
    
    print(f"✅ SELL executed: {sell_order['quantity_filled']:,} shares @ ${sell_order['vwap']:.2f} on {sell_ticker}")
    speedbump(sell_time)
    
    # Calculate actual profit
    filled_quantity = min(buy_order['quantity_filled'], sell_order['quantity_filled'])
    actual_profit = (sell_order['vwap'] - buy_order['vwap']) * filled_quantity
    
    # Add to expected total profit
    expected_total_profit += expected_profit
    
    print(f"Actual profit: ${actual_profit:.2f}")
    print(f"{'='*70}\n")
    
    return True

def wait_for_case_start(session):
    """Wait for the case to start (status = ACTIVE and ticks moving)"""
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
    """Print statistics for the completed period"""
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
        # Get current limits
        gross_position, net_position, gross_limit, net_limit = get_limits(s)
        
        print("\n" + "="*70)
        print(" ALGORITHMIC ARBITRAGE BOT - ALGO1 Case")
        print("="*70)
        print(f"Position Limit: ±{POSITION_LIMIT:,} shares (gross/net)")
        print(f"Max Order Size: {MAX_ORDER_SIZE:,} shares")
        print(f"Rate Limit: {ORDER_LIMIT} orders/second")
        print(f"Strategy: /securities endpoint - SINGLE API call for quotes!")
        print("="*70 + "\n")
        
        # Wait for case to start
        if not wait_for_case_start(s):
            print("Shutdown before case started")
            return
        
        print("Bot started\n")
        
        last_period = 0
        last_status = 'ACTIVE'
        last_realized = 0
        
        while not shutdown:
            try:
                tick, status, period = get_tick(s)
                
                # Check if we've moved to a new period (case restarted)
                if period != last_period:
                    if last_period > 0:
                        # Case restarted - print stats for previous period
                        print_period_stats(last_realized, last_period)
                        print(f"Starting new period {period}\n")
                        
                        # Reset counters for new period
                        opportunities_found = 0
                        trades_executed = 0
                        evaluations = 0
                        expected_total_profit = 0
                        number_of_orders = 0
                        total_speedbumps = 0
                    
                    last_period = period
                
                # Check if case just stopped (was ACTIVE, now is not)
                if last_status == 'ACTIVE' and status != 'ACTIVE':
                    # Case just stopped - print stats
                    print_period_stats(last_realized, period)
                    print(f"Case is {status}. Waiting for next period.\n")
                
                last_status = status
                
                # Check if case is not active
                if status != 'ACTIVE':
                    sleep(0.5)
                    continue
                
                # # Calculate remaining capacity
                # remaining_capacity = min(
                #     gross_limit - gross_position,
                #     net_limit - abs(net_position)
                # )
                
                # if remaining_capacity <= 0:
                #     print(f"⚠ Position limit reached (Tick {tick}). Waiting...")
                #     sleep(1)
                #     continue
                
                # Get securities data - ONE CALL for both tickers!
                crzy_m, crzy_a, last_realized = get_securities(s)
                
                # Check if we got valid data
                if crzy_m is None or crzy_a is None:
                    sleep(0.1)
                    continue
                
                # Check if we have valid bid/ask (non-zero)
                if crzy_m['bid'] == 0 or crzy_m['ask'] == 0:
                    sleep(0.1)
                    continue
                    
                if crzy_a['bid'] == 0 or crzy_a['ask'] == 0:
                    sleep(0.1)
                    continue
                
                # Increment evaluation counter
                evaluations += 1
                
                # Extract bid/ask from securities response
                crzy_m_bid = crzy_m['bid']
                crzy_m_ask = crzy_m['ask']
                crzy_m_bid_size = crzy_m['bid_size']
                crzy_m_ask_size = crzy_m['ask_size']
                
                crzy_a_bid = crzy_a['bid']
                crzy_a_ask = crzy_a['ask']
                crzy_a_bid_size = crzy_a['bid_size']
                crzy_a_ask_size = crzy_a['ask_size']
                
                # Check for arbitrage opportunities
                
                # Opportunity 1: Buy on Main, Sell on Alternate (M ask < A bid)
                if crzy_m_ask < crzy_a_bid:
                    opportunities_found += 1
                    
                    # Calculate maximum quantity we can trade
                    max_quantity = min(
                        crzy_m_ask_size,      # Liquidity on Main ask
                        crzy_a_bid_size,      # Liquidity on Alternate bid
                        MAX_ORDER_SIZE,       # Per-order limit
                        # remaining_capacity    # Position limit
                    )
                    
                    if max_quantity > 0:
                        if execute_arbitrage(s, 'CRZY_M', 'CRZY_A', max_quantity, crzy_m_ask, crzy_a_bid):
                            trades_executed += 1
                
                # Opportunity 2: Buy on Alternate, Sell on Main (A ask < M bid)
                elif crzy_a_ask < crzy_m_bid:
                    opportunities_found += 1
                    
                    # Calculate maximum quantity we can trade
                    max_quantity = min(
                        crzy_a_ask_size,      # Liquidity on Alternate ask
                        crzy_m_bid_size,      # Liquidity on Main bid
                        MAX_ORDER_SIZE,       # Per-order limit
                        # remaining_capacity    # Position limit
                    )
                    
                    if max_quantity > 0:
                        if execute_arbitrage(s, 'CRZY_A', 'CRZY_M', max_quantity, crzy_a_ask, crzy_m_bid):
                            trades_executed += 1
                
                # Print status every 20 evaluations to show we're alive
                elif evaluations % 20 == 0:
                    print(f"[Tick {tick:3d}] Evaluation #{evaluations}: No arbitrage (M: {crzy_m_bid:.2f}/{crzy_m_ask:.2f}, A: {crzy_a_bid:.2f}/{crzy_a_ask:.2f})")
                
            except KeyboardInterrupt:
                shutdown = True
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                sleep(0.5)
        
        # Final stats when manually stopped
        print("\n" + "="*70)
        print("Bot manually stopped.")
        print(f"   Final Statistics:")
        print(f"   Evaluations: {evaluations}")
        print(f"   Opportunities found: {opportunities_found}")
        print(f"   Trades executed: {trades_executed}")
        print(f"   Total orders submitted: {number_of_orders}")
        print(f"   Expected total profit: ${expected_total_profit:.2f}")
        print(f"   Actual realized profit: ${last_realized/2:.2f}")
        print("="*70 + "\n")

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    main()