import requests
import signal
import time
from time import sleep

Port = 10005

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
ORDER_LIMIT = 5  # orders per second (adjust based on actual rate limit)
MAX_ORDER_SIZE = 10000
POSITION_LIMIT = 25000

# Speed bump tracking
number_of_orders = 0
total_speedbumps = 0

def get_tick(session):
    """Get current tick of the case"""
    resp = session.get(f'http://localhost:{Port}/v1/case')
    if resp.status_code == 401:
        raise ApiException('API key mismatch')
    case = resp.json()
    return case['tick'], case['status']

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

def get_order_books(session):
    """Get order books for both exchanges"""
    crzy_m_resp = session.get(f'http://localhost:{Port}/v1/securities/book?ticker=CRZY_M&limit=1')
    crzy_a_resp = session.get(f'http://localhost:{Port}/v1/securities/book?ticker=CRZY_A&limit=1')
    
    if crzy_m_resp.status_code == 401 or crzy_a_resp.status_code == 401:
        raise ApiException('API key mismatch')
    
    crzy_m_book = crzy_m_resp.json()
    crzy_a_book = crzy_a_resp.json()
    
    return crzy_m_book, crzy_a_book

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
        print(f"⚠ Rate limited! Waiting {wait_time:.2f} seconds...")
        sleep(wait_time)
        return None
    
    if resp.status_code != 200:
        print(f"⚠ Order failed: {resp.json()}")
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
    
    # Sleep for average speed bump
    avg_speedbump = total_speedbumps / number_of_orders
    if avg_speedbump > 0:
        sleep(avg_speedbump)

def execute_arbitrage(session, buy_ticker, sell_ticker, quantity, buy_price, sell_price):
    """Execute arbitrage by buying on one exchange and selling on the other"""
    
    print(f"\n{'='*70}")
    print(f"🎯 ARBITRAGE OPPORTUNITY DETECTED!")
    print(f"   Buy  {quantity:,} shares on {buy_ticker} @ ~${buy_price:.2f}")
    print(f"   Sell {quantity:,} shares on {sell_ticker} @ ~${sell_price:.2f}")
    print(f"   Expected profit: ${(sell_price - buy_price) * quantity:.2f}")
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
    print(f"💰 Actual profit: ${actual_profit:.2f}")
    print(f"{'='*70}\n")
    
    return True

def main():
    global shutdown
    
    with requests.Session() as s:
        s.headers.update(API_KEY)
        
        print("\n" + "="*70)
        print(" ALGORITHMIC ARBITRAGE BOT - ALGO1 Case")
        print("="*70)
        print(f"Position Limit: ±{POSITION_LIMIT:,} shares (gross/net)")
        print(f"Max Order Size: {MAX_ORDER_SIZE:,} shares")
        print(f"Rate Limit: {ORDER_LIMIT} orders/second")
        print(f"Strategy: Market orders for immediate execution")
        print("="*70 + "\n")
        
        tick, status = get_tick(s)
        opportunities_found = 0
        trades_executed = 0
        
        print("🤖 Bot started. Monitoring markets for arbitrage opportunities...\n")
        
        while tick <= 300 and status == 'ACTIVE' and not shutdown:
            try:
                # Get current limits
                gross_position, net_position, gross_limit, net_limit = get_limits(s)
                
                # Calculate remaining capacity
                remaining_capacity = min(
                    gross_limit - gross_position,
                    net_limit - abs(net_position)
                )
                
                if remaining_capacity <= 0:
                    print("⚠ Position limit reached. Waiting...")
                    sleep(1)
                    tick, status = get_tick(s)
                    continue
                
                # Get order books
                crzy_m_book, crzy_a_book = get_order_books(s)
                
                # Check if books have valid data
                if not crzy_m_book.get('bids') or not crzy_m_book.get('asks'):
                    tick, status = get_tick(s)
                    sleep(0.1)
                    continue
                    
                if not crzy_a_book.get('bids') or not crzy_a_book.get('asks'):
                    tick, status = get_tick(s)
                    sleep(0.1)
                    continue
                
                # Extract best bid/ask for both exchanges
                crzy_m_bid = crzy_m_book['bids'][0]['price']
                crzy_m_ask = crzy_m_book['asks'][0]['price']
                crzy_m_bid_size = crzy_m_book['bids'][0]['quantity'] - crzy_m_book['bids'][0]['quantity_filled']
                crzy_m_ask_size = crzy_m_book['asks'][0]['quantity'] - crzy_m_book['asks'][0]['quantity_filled']
                
                crzy_a_bid = crzy_a_book['bids'][0]['price']
                crzy_a_ask = crzy_a_book['asks'][0]['price']
                crzy_a_bid_size = crzy_a_book['bids'][0]['quantity'] - crzy_a_book['bids'][0]['quantity_filled']
                crzy_a_ask_size = crzy_a_book['asks'][0]['quantity'] - crzy_a_book['asks'][0]['quantity_filled']
                
                # Check for arbitrage opportunities
                
                # Opportunity 1: Buy on Main, Sell on Alternate (M ask < A bid)
                if crzy_m_ask < crzy_a_bid:
                    opportunities_found += 1
                    
                    # Calculate maximum quantity we can trade
                    max_quantity = min(
                        crzy_m_ask_size,      # Liquidity on Main ask
                        crzy_a_bid_size,      # Liquidity on Alternate bid
                        MAX_ORDER_SIZE,       # Per-order limit
                        remaining_capacity    # Position limit
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
                        remaining_capacity    # Position limit
                    )
                    
                    if max_quantity > 0:
                        if execute_arbitrage(s, 'CRZY_A', 'CRZY_M', max_quantity, crzy_a_ask, crzy_m_bid):
                            trades_executed += 1
                
                # Update tick
                tick, status = get_tick(s)
                
                # Small delay to avoid hammering the API unnecessarily
                # sleep(0.05)
                
            except KeyboardInterrupt:
                shutdown = True
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                sleep(0.5)
        
        print("\n" + "="*70)
        print("🛑 Bot stopped.")
        print(f"📊 Statistics:")
        print(f"   Opportunities found: {opportunities_found}")
        print(f"   Trades executed: {trades_executed}")
        print(f"   Total orders: {number_of_orders}")
        print("="*70 + "\n")

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    main()
