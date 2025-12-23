import requests
import signal
import time
from time import sleep

Port = 65535

class ApiException(Exception):
    pass

# Signal handler for graceful shutdown
def signal_handler(signum, frame):
    global shutdown
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    shutdown = True

# Set API key
API_KEY = {'X-API-Key': 'L365SOJK'}
shutdown = False

# Trading parameters
ORDER_LIMIT = 10  # orders per second
MAX_ORDER_SIZE = 5000  # max shares per order
POSITION_LIMIT = 25000  # position limit (gross and net)
MAX_ORDERS = 5  # 25000 / 5000 = 5 orders to reach position limit
SPREAD = 0.02  # minimum spread per side before we submit orders

# Speed bump tracking
number_of_orders = 0
total_speedbumps = 0

# Statistics tracking
pairs_submitted = 0
spreads_captured = 0
single_side_filled = False
single_side_transaction_time = 0

def get_tick(session):
    """Get current tick and case status"""
    resp = session.get(f'http://localhost:{Port}/v1/case')
    if resp.status_code == 401:
        raise ApiException('API key mismatch')
    case = resp.json()
    return case['tick'], case['status'], case['period']

def get_security_info(session, ticker='ALGO'):
    """Get security info including position, prices, and P&L"""
    resp = session.get(f'http://localhost:{Port}/v1/securities', params={'ticker': ticker})
    if resp.status_code == 401:
        raise ApiException('API key mismatch')
    
    securities = resp.json()
    for security in securities:
        if security['ticker'] == ticker:
            return {
                'position': security['position'],
                'last': security['last'],
                'bid': security['bid'],
                'bid_size': security['bid_size'],
                'ask': security['ask'],
                'ask_size': security['ask_size'],
                'realized': security['realized'],
                'unrealized': security['unrealized']
            }
    
    return None

def get_book(session, ticker='ALGO'):
    """Get order book - returns best bid and ask prices"""
    resp = session.get(f'http://localhost:{Port}/v1/securities/book', params={'ticker': ticker, 'limit': 1})
    if resp.status_code == 401:
        raise ApiException('API key mismatch')
    
    if resp.ok:
        book = resp.json()
        bid_price = book['bids'][0]['price'] if book['bids'] else 0
        ask_price = book['asks'][0]['price'] if book['asks'] else 0
        return bid_price, ask_price
    return 0, 0

def get_open_orders(session, ticker='ALGO'):
    """Get all open orders and separate them into buys and sells"""
    resp = session.get(f'http://localhost:{Port}/v1/orders?status=OPEN')
    if resp.status_code == 401:
        raise ApiException('API key mismatch')
    
    open_buys_volume = 0
    open_sells_volume = 0
    buy_ids = []
    buy_prices = []
    buy_volumes = []
    buy_filled = []
    sell_ids = []
    sell_prices = []
    sell_volumes = []
    sell_filled = []
    
    if resp.ok:
        orders = resp.json()
        for order in orders:
            if order['ticker'] == ticker:
                remaining = order['quantity'] - order['quantity_filled']
                if order['action'] == 'BUY':
                    open_buys_volume += remaining
                    buy_ids.append(order['order_id'])
                    buy_prices.append(order['price'])
                    buy_volumes.append(order['quantity'])
                    buy_filled.append(order['quantity_filled'])
                elif order['action'] == 'SELL':
                    open_sells_volume += remaining
                    sell_ids.append(order['order_id'])
                    sell_prices.append(order['price'])
                    sell_volumes.append(order['quantity'])
                    sell_filled.append(order['quantity_filled'])
    
    return {
        'buys': {
            'volume': open_buys_volume,
            'ids': buy_ids,
            'prices': buy_prices,
            'order_volumes': buy_volumes,
            'filled': buy_filled
        },
        'sells': {
            'volume': open_sells_volume,
            'ids': sell_ids,
            'prices': sell_prices,
            'order_volumes': sell_volumes,
            'filled': sell_filled
        }
    }

def submit_limit_order(session, ticker, action, quantity, price):
    """Submit a limit order"""
    params = {
        'ticker': ticker,
        'type': 'LIMIT',
        'quantity': quantity,
        'action': action,
        'price': price
    }
    
    resp = session.post(f'http://localhost:{Port}/v1/orders', params=params)
    
    if resp.status_code == 429:
        wait_time = resp.json().get('wait', 1)
        print(f"⚠️ Rate limited! Waiting {wait_time:.2f} seconds...")
        sleep(wait_time)
        return None
    
    if resp.status_code != 200:
        error_msg = resp.json() if resp.content else "Unknown error"
        print(f"⚠️ Order failed: {error_msg}")
        return None
    
    return resp.json()

def cancel_order(session, order_id):
    """Cancel an order by ID"""
    resp = session.delete(f'http://localhost:{Port}/v1/orders/{order_id}')
    return resp.ok

def cancel_all_orders(session):
    """Cancel all open orders"""
    resp = session.post(f'http://localhost:{Port}/v1/commands/cancel', params={'all': 1})
    return resp.ok

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

def buy_sell(session, sell_price, buy_price, quantity=MAX_ORDER_SIZE):
    """Submit a pair of buy and sell orders"""
    global pairs_submitted
    
    start_time = time.time()
    
    # Submit MAX_ORDERS pairs to maximize position usage
    for i in range(MAX_ORDERS):
        # Submit sell order
        session.post(f'http://localhost:{Port}/v1/orders', params={
            'ticker': 'ALGO',
            'type': 'LIMIT',
            'quantity': quantity,
            'price': sell_price,
            'action': 'SELL'
        })
        
        # Submit buy order
        session.post(f'http://localhost:{Port}/v1/orders', params={
            'ticker': 'ALGO',
            'type': 'LIMIT',
            'quantity': quantity,
            'price': buy_price,
            'action': 'BUY'
        })
    
    transaction_time = time.time() - start_time
    speedbump(transaction_time)
    
    pairs_submitted += MAX_ORDERS
    print(f"   ✅ Submitted {MAX_ORDERS} pairs: BUY @ ${buy_price:.2f} | SELL @ ${sell_price:.2f}")

def re_order(session, order_ids, volumes_filled, volumes, price, action):
    """Cancel and re-submit orders at a new price"""
    for i in range(len(order_ids)):
        order_id = order_ids[i]
        volume = volumes[i]
        volume_filled = volumes_filled[i]
        
        # If order is partially filled, adjust volume
        if volume_filled != 0:
            volume = MAX_ORDER_SIZE - volume_filled
        
        # Delete then re-submit
        deleted = session.delete(f'http://localhost:{Port}/v1/orders/{order_id}')
        if deleted.ok:
            session.post(f'http://localhost:{Port}/v1/orders', params={
                'ticker': 'ALGO',
                'type': 'LIMIT',
                'quantity': volume,
                'price': price,
                'action': action
            })

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

def print_period_stats(realized, period):
    print("\n" + "="*70)
    print(f"   PERIOD {period} COMPLETED - Statistics:")
    print(f"   Pairs submitted: {pairs_submitted}")
    print(f"   Total orders: {number_of_orders}")
    print(f"   Realized P&L: ${realized:.2f}")
    print("="*70 + "\n")

def main():
    global shutdown, pairs_submitted, spreads_captured
    global number_of_orders, total_speedbumps
    global single_side_filled, single_side_transaction_time
    
    with requests.Session() as s:
        s.headers.update(API_KEY)
        
        print("\n" + "="*70)
        print("   MARKET MAKING BOT - ALGO2")
        print("="*70)
        print(f"Position Limit: ±{POSITION_LIMIT:,} shares")
        print(f"Max Order Size: {MAX_ORDER_SIZE:,} shares")
        print(f"Max Orders per Side: {MAX_ORDERS}")
        print(f"Spread Target: ${SPREAD:.2f} per side (${SPREAD*2:.2f} total)")
        print(f"Rate Limit: {ORDER_LIMIT} orders/second")
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
                
                # Handle period changes
                if period != last_period:
                    if last_period > 0:
                        print_period_stats(last_realized, last_period)
                        print(f"Starting new period {period}\n")
                        # Reset stats
                        pairs_submitted = 0
                        number_of_orders = 0
                        total_speedbumps = 0
                        single_side_filled = False
                        single_side_transaction_time = 0
                    last_period = period
                
                # Handle status changes
                if last_status == 'ACTIVE' and status != 'ACTIVE':
                    print_period_stats(last_realized, period)
                    print(f"Case is {status}. Waiting for next period.\n")
                
                last_status = status
                
                if status != 'ACTIVE':
                    sleep(0.5)
                    continue
                
                # Skip first 5 and last 5 seconds
                if tick <= 5 or tick >= 295:
                    sleep(0.1)
                    continue
                
                # Get security info
                security = get_security_info(s, 'ALGO')
                if security is None or security['bid'] == 0 or security['ask'] == 0:
                    sleep(0.1)
                    continue
                
                bid_price = security['bid']
                ask_price = security['ask']
                position = security['position']
                last_realized = security['realized']
                
                # Get open orders
                orders = get_open_orders(s, 'ALGO')
                open_buys_volume = orders['buys']['volume']
                open_sells_volume = orders['sells']['volume']
                
                buy_ids = orders['buys']['ids']
                buy_prices = orders['buys']['prices']
                buy_volumes = orders['buys']['order_volumes']
                buy_filled = orders['buys']['filled']
                
                sell_ids = orders['sells']['ids']
                sell_prices = orders['sells']['prices']
                sell_volumes = orders['sells']['order_volumes']
                sell_filled = orders['sells']['filled']
                
                # CASE 1: No open orders - submit new pairs
                if open_sells_volume == 0 and open_buys_volume == 0:
                    # Both sides are filled now
                    single_side_filled = False
                    
                    # Calculate the spread
                    bid_ask_spread = ask_price - bid_price
                    
                    # Set our prices at the top of the book
                    sell_price = ask_price
                    buy_price = bid_price
                    
                    # Check if spread is wide enough to be profitable
                    # We need spread >= SPREAD * 2 to make profit after rebates
                    if bid_ask_spread >= SPREAD * 2:
                        print(f"\n[Tick {tick:3d}] Submitting market-making orders")
                        print(f"   Position: {position:,} | Spread: ${bid_ask_spread:.2f}")
                        
                        buy_sell(s, sell_price, buy_price)
                    else:
                        if tick % 20 == 0:
                            print(f"[Tick {tick:3d}] Spread too tight: ${bid_ask_spread:.2f} < ${SPREAD*2:.2f}")
                
                # CASE 2: There are outstanding open orders
                else:
                    # Check if one side has been completely filled
                    if not single_side_filled and (open_buys_volume == 0 or open_sells_volume == 0):
                        single_side_filled = True
                        single_side_transaction_time = tick
                        print(f"\n[Tick {tick:3d}] One side filled!")
                        print(f"   Buys remaining: {open_buys_volume} | Sells remaining: {open_sells_volume}")
                    
                    # CASE 2a: Ask side completely filled, buy orders remaining
                    if open_sells_volume == 0 and open_buys_volume > 0:
                        # Check if our buy orders are at the top of the book
                        if buy_prices and buy_prices[0] == bid_price:
                            # Already at best price, wait
                            pass
                        # Wait at least 3 seconds before re-ordering
                        elif tick - single_side_transaction_time >= 3:
                            # Calculate potential profit if we improve our bid
                            next_buy_price = bid_price + 0.01
                            potential_profit = ask_price - next_buy_price - 0.01  # subtract 1 cent for slippage
                            
                            # Re-order if profitable OR if it's been more than 6 seconds
                            if potential_profit >= 0.01 or tick - single_side_transaction_time >= 6:
                                print(f"[Tick {tick:3d}] Re-ordering BUY side at ${next_buy_price:.2f}")
                                
                                start_time = time.time()
                                re_order(s, buy_ids, buy_filled, buy_volumes, next_buy_price, 'BUY')
                                transaction_time = time.time() - start_time
                                speedbump(transaction_time)
                    
                    # CASE 2b: Bid side completely filled, sell orders remaining
                    elif open_buys_volume == 0 and open_sells_volume > 0:
                        # Check if our sell orders are at the top of the book
                        if sell_prices and sell_prices[0] == ask_price:
                            # Already at best price, wait
                            pass
                        # Wait at least 3 seconds before re-ordering
                        elif tick - single_side_transaction_time >= 3:
                            # Calculate potential profit if we improve our ask
                            next_sell_price = ask_price - 0.01
                            potential_profit = next_sell_price - bid_price - 0.01  # subtract 1 cent for slippage
                            
                            # Re-order if profitable OR if it's been more than 6 seconds
                            if potential_profit >= 0.01 or tick - single_side_transaction_time >= 6:
                                print(f"[Tick {tick:3d}] Re-ordering SELL side at ${next_sell_price:.2f}")
                                
                                start_time = time.time()
                                re_order(s, sell_ids, sell_filled, sell_volumes, next_sell_price, 'SELL')
                                transaction_time = time.time() - start_time
                                speedbump(transaction_time)
                    
                    # CASE 2c: Both sides have orders - show status periodically
                    else:
                        if tick % 30 == 0:
                            total_pnl = security['realized'] + security['unrealized']
                            print(f"[Tick {tick:3d}] Orders active | Pos: {position:,} | P&L: ${total_pnl:.2f}")
                
            except KeyboardInterrupt:
                shutdown = True
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                sleep(0.5)
        
        # Final stats
        try:
            security = get_security_info(s, 'ALGO')
            if security:
                print(f"\n{'='*70}")
                print(f"   BOT STOPPED")
                print(f"   Final Position: {security['position']:,}")
                print(f"   Realized P&L: ${security['realized']:.2f}")
                print(f"   Unrealized P&L: ${security['unrealized']:.2f}")
                print(f"   Total P&L: ${security['realized'] + security['unrealized']:.2f}")
                print(f"{'='*70}\n")
        except:
            pass
        
        print("Bot manually stopped.")

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    main()