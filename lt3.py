# V2

import os
import functools
import operator
import itertools
from time import sleep
import signal
import requests
import keyboard

Port = 65535

class ApiException(Exception):
    pass

# this signal handler allows for a graceful shutdown when CTRL+C is pressed
def signal_handler(signum, frame):
    global shutdown
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    shutdown = True

# set your API key to authenticate to the RIT client
API_KEY = {'X-API-Key': 'L365SOJK'}
shutdown = False

# this helper method returns the current 'tick' of the running case
def get_tick(session):
    resp = session.get(f'http://localhost:{Port}/v1/case')
    if resp.status_code == 401:
        raise ApiException('The API key provided in this Python code must match that in the RIT client (please refer to the API hyperlink in the client toolbar and/or the RIT â€“ User Guide â€“ REST API Documentation.pdf)')
    case = resp.json()
    return case['tick']

# this helper method builds the depth view for two tickers
def depth_view(session):
    crzy_resp = session.get(f'http://localhost:{Port}/v1/securities/book?ticker=CRZY')
    tame_resp = session.get(f'http://localhost:{Port}/v1/securities/book?ticker=TAME')
    if crzy_resp.status_code == 401 or tame_resp.status_code == 401:
        raise ApiException('The API key provided in this Python code must match that in the RIT client (please refer to the API hyperlink in the client toolbar and/or the RIT â€“ User Guide â€“ REST API Documentation.pdf)')
    crzy_book = crzy_resp.json()
    tame_book = tame_resp.json()
    calculate_cumulatives(crzy_book['bids'])
    calculate_cumulatives(crzy_book['asks'])
    calculate_cumulatives(tame_book['bids'])
    calculate_cumulatives(tame_book['asks'])
    combined = itertools.zip_longest(crzy_book['bids'], crzy_book['asks'], tame_book['bids'], tame_book['asks'], fillvalue={'cumulative_vwap': 0, 'cumulative_vol': 0, 'price': 0})
    return combined

# this helper method calculates cumulative volumes and VWAPs for each level of an order book
def calculate_cumulatives(book):
    for level in book:
        slice = book[:book.index(level) + 1]
        level['cumulative_vol'] = int(sum(s['quantity'] - s['quantity_filled'] for s in slice))
        level['cumulative_vwap'] = sum(functools.reduce(operator.mul, data) for data in zip((s['quantity'] - s['quantity_filled'] for s in slice), (s['price'] for s in slice))) / level['cumulative_vol']

# this helper method prints two order books to the screen
def print_books(combined):
    os.system('cls')
    print('CRZY                                                           TAME')
    print('BIDVWAP | CUMUVOL |  BID  |  ASK  | CUMUVOL | ASKVWAP          BIDVWAP | CUMUVOL |  BID  |  ASK  | CUMUVOL | ASKVWAP')
    for level in itertools.islice(combined, 20):
        crzy_bid, crzy_ask, tame_bid, tame_ask = level
        print('{:07.4f} | {:07d} | {:05.2f} | {:05.2f} | {:07d} | {:07.4f}          {:07.4f} | {:07d} | {:05.2f} | {:05.2f} | {:07d} | {:07.4f}'.format(crzy_bid.get('cumulative_vwap'), crzy_bid.get('cumulative_vol'), crzy_bid.get('price'), crzy_ask.get('price'), crzy_ask.get('cumulative_vol'), crzy_ask.get('cumulative_vwap'), tame_bid.get('cumulative_vwap'), tame_bid.get('cumulative_vol'), tame_bid.get('price'), tame_ask.get('price'), tame_ask.get('cumulative_vol'), tame_ask.get('cumulative_vwap')))
    sleep(0.5)

def get_tenders(session):
    resp = session.get(f'http://localhost:{Port}/v1/tenders')
    if resp.status_code == 401:
        raise ApiException('The API key provided in this Python code must match that in the RIT client (please refer to the API hyperlink in the client toolbar and/or the RIT â€“ User Guide â€“ REST API Documentation.pdf)')
    tenders = resp.json()
    return tenders

# def place_order(session, tender):


# def evaluate_tender(session, tender):
#     # This function will look at the tender specifics and decide whether to place an order or not
#     # If the tender is a buy offer, we will comsider the buy
#     # If the tender is a sell offer, we will consider the sell
#     # additionally we need to see for which ticker its for, crazy or tame
#     # We also need to look at the current price of the ticker. If it is a good price difference, we will place the order by calling the place order function with the tender id as a parameter
#     # After the order is placed we will call the zero out function to zero out the tender. input the tedner details as the parameter
#     # If the tender is not a good price, we will call the cancel tender function with the tender id as the parameter

#     # Get the ticker
#     ticker = tender['ticker']
#     # Get the tender id
#     tender_id = tender['tender_id']
#     # Get the tender type
#     tender_type = tender['action']
#     # Get the tender price
#     tender_price = tender['price']
#     # Get the tender quantity
#     tender_quantity = tender['quantity']
    
#     # Get the current price of the ticker
#     current_price = get_current_price(session, ticker)
#     print("Tender Details: " + str(tender))
#     print("Current Price: " + str(current_price))
#     # If the tender is a buy offer
#     if tender_type == 'BUY':
#         # If the tender price is less than the current price, then place the order
#         if tender_price+0.1 < current_price:
#             accept_tender(session, tender_id, tender_price, tender_quantity, tender_type, ticker)
#             # Wait one second
#             sleep(1)
#             zero_out_tender(session, ticker, tender_type, tender_quantity)
#         else:
#             decline_tender(session, tender_id)
#     # If the tender is a sell offer
#     elif tender_type == 'SELL':
#         # If the tender price is more than the current price, then place the order
#         if tender_price-0.1 > current_price:
#             accept_tender(session, tender_id, tender_price, tender_quantity, tender_type, ticker)
#             # Wait one second
#             sleep(1)
#             zero_out_tender(session, ticker, tender_type, tender_quantity)
#         else:
#             decline_tender(session, tender_id)


def get_order_book(session, ticker):
    resp = session.get(f'http://localhost:{Port}/v1/securities/book?ticker={ticker}')
    if resp.status_code == 401:
        raise ApiException('Invalid API key')
    book = resp.json()
    calculate_cumulatives(book['bids'])
    calculate_cumulatives(book['asks'])
    return book




# def evaluate_tender(session, tender):

#     ticker = tender['ticker']
#     tender_id = tender['tender_id']
#     tender_type = tender['action']  # BUY or SELL
#     tender_price = tender['price']
#     tender_quantity = tender['quantity']
#     # Get the current price of the ticker
#     current_price = get_current_price(session, ticker)
#     print("Tender Details: " + str(tender))
#     print("Current Price: " + str(current_price))
#     # Get the order book for the ticker
#     order_book = get_order_book(session, ticker)
    
#     # Check if there is enough liquidity to unwind the tender at a profit
#     if check_liquidity(order_book, tender_quantity, tender_type, tender_price):
#         # Accept tender if liquidity and price conditions are favorable
#         accept_tender(session, tender_id, tender_price, tender_quantity, tender_type, ticker)
#         sleep(1)
#         # After accepting the tender, attempt to zero out the position
#         zero_out_tender(session, ticker, tender_type, tender_quantity)
#     else:
#         # Decline tender if liquidity is insufficient or the spread is too narrow
#         decline_tender(session, tender_id, tender_price, tender_quantity, tender_type, ticker)


def evaluate_tender(session, tender):
    ticker = tender['ticker']
    tender_id = tender['tender_id']
    tender_type = tender['action']  # BUY or SELL
    tender_price = tender['price']
    tender_quantity = tender['quantity']
    expires = tender['expires']  # This gives us the number of ticks left until the tender expires

    # Loop until the tender expires
    while get_tick(session) < expires:
        # Get the current price and order book of the ticker
        current_price = get_current_price(session, ticker)
        order_book = get_order_book(session, ticker)
        
        # Print tender details and current price for debugging
        print(f"Tender Details: {tender}")
        print(f"Current Price: {current_price}")
        
        # Check if liquidity is favorable to accept the tender
        if check_liquidity(order_book, tender_quantity, tender_type, tender_price):
            # Accept the tender as soon as it's profitable
            accept_tender(session, tender_id, tender_price, tender_quantity, tender_type, ticker)
            sleep(1)
            # Zero out the tender position
            zero_out_tender(session, ticker)
            return  # Exit the function after accepting the tender
        
        # Wait for 1 second before rechecking the market conditions
        # sleep(1)
    
    # If the current tick reaches the tender expiration and the tender hasn't been accepted, decline it
    print("Tender expired")
    # decline_tender(session, tender_id, tender_price, tender_quantity, tender_type, ticker)

def check_liquidity(order_book, tender_quantity, tender_type, tender_price):
    """
   Checks if there is enough liquidity to unwind the tender at a profit.
   """
   # Determine if we are buying or selling
    book_side = 'asks' if tender_type == 'BUY' else 'bids'  # Buy checks sell (ask) side, Sell checks buy (bid) side
    price_threshold = tender_price + 0.20 if tender_type == 'BUY' else tender_price - 0.20

    cumulative_vol = 0
    total_vwap = 0

    for level in order_book[book_side]:         
        price = level['price']
        if (tender_type == 'BUY' and price >= price_threshold) or (tender_type == 'SELL' and price <= price_threshold):
             # Add available volume at this price level
            cumulative_vol += level['cumulative_vol']
            total_vwap += level['cumulative_vwap'] * level['cumulative_vol']
            
             # If cumulative volume is enough to cover tender size
            if cumulative_vol >= tender_quantity:   
                 # Calculate the average VWAP and check profitability
                avg_vwap = total_vwap / cumulative_vol
                if tender_type == 'BUY':
                     return tender_price < avg_vwap  # Ensure we can sell at a higher price
                else:
                     return tender_price > avg_vwap  # Ensure we can buy at a lower price
        else:
            break  # Stop if no better price levels available

    return False  # Not enough liquidity to unwind the tender profitably


# def check_liquidity(order_book, tender_quantity, tender_type, tender_price):
    """
    Checks if the total dollar value of the market options exceeds the total dollar value of the tender.
    Returns True if favorable, False otherwise.
    """
    # Determine if we are buying or selling
    # book_side = 'asks' if tender_type == 'BUY' else 'bids'  # Buy checks sell (ask) side, Sell checks buy (bid) side
    book_side = order_book['bids'] if tender_type == "SELL" else order_book['asks']
    market_total_value = 0  # Total dollar value from the market
    cumulative_vol = 0  # Total quantity accumulated from the market
    
    # Iterate over the book side to accumulate orders that match up to the tender quantity
    for level in book_side:
        price = level['price']
        available_volume = level['cumulative_vol']
        
        # Accumulate volumes up to the tender quantity
        fulfill_quantity = min(available_volume, tender_quantity - cumulative_vol)
        market_total_value += fulfill_quantity * price  # Sum the dollar value (quantity * price)
        cumulative_vol += fulfill_quantity

        # Stop when we have accumulated enough quantity to match the tender
        if cumulative_vol >= tender_quantity:
            break

    # If we don't have enough volume to fulfill the tender, return False
    if cumulative_vol < tender_quantity:
        return False

    # Calculate the tender's total value
    tender_total_value = tender_quantity * tender_price

    # Compare the market total value to the tender total value
    if tender_type == 'BUY':
        # For a buy tender, we want the market total to be higher (so we can sell at a higher price)
        return market_total_value > tender_total_value+(tender_quantity*0.02)
    else:
        # For a sell tender, we want the market total to be lower (so we can buy at a lower price)
        return market_total_value < tender_total_value-(tender_quantity*0.02)










def get_current_price(session, ticker):
    resp = session.get(f'http://localhost:{Port}/v1/securities/book?ticker=' + ticker)
    if resp.status_code == 401:
        raise ApiException('The API key provided in this Python code must match that in the RIT client (please refer to the API hyperlink in the client toolbar and/or the RIT â€“ User Guide â€“ REST API Documentation.pdf)')
    book = resp.json()
    calculate_cumulatives(book['bids'])
    calculate_cumulatives(book['asks'])
    # the current price is the last successful price either bid or ask
    current_price = book['bids'][0]['price'] if book['bids'] else book['asks'][0]['price']
    return current_price

def accept_tender(session, tender_id, tender_price, tender_quantity, tender_type, ticker):
    response = session.post(f"http://localhost:{Port}/v1/tenders/{tender_id}?price={tender_price}")
    if response.status_code == 200:
        if tender_type == 'BUY':
            print(f'BOUGHT {tender_quantity} shares of {ticker} at {tender_price}')
        else:
            print(f'SOLD {tender_quantity} shares of {ticker} at {tender_price}')
    else:
        print(f"Failed to accept tender offer. Status code: {response.status_code}")


def decline_tender(session, tender_id, tender_price, tender_quantity, tender_type, ticker):
    response = session.delete(f"http://localhost:{Port}/v1/tenders/{tender_id}")

    if response.status_code == 200:
        if tender_type == 'BUY':
            print(f'CANCELED BUY {tender_quantity} shares of {ticker} at {tender_price}')
        else:
            print(f'CANCELED SELL {tender_quantity} shares of {ticker} at {tender_price}')
    else:
        print(f"Failed to decline tender offer. Status code: {response.status_code}")

# def zero_out_tender(session, ticker, tender_type, tender_quantity):
#     # Determine the opposite action
#     opposite_action = "SELL" if tender_type == "BUY" else "BUY"
    
#     # Determine the increment based on the ticker type
#     increment = 25000 if ticker == "CRZY" else 10000
    
#     # Loop to place orders in increments
#     while tender_quantity > 0:
#         current_quantity = min(increment, tender_quantity)
        
#         # Construct the URL
#         response = session.post(f"http://localhost:9999/v1/orders?ticker={ticker}&type=MARKET&quantity={current_quantity}&action={opposite_action}")
        
#         # Handle the response
#         if response.status_code == 200:
#             print(f"Action: {opposite_action}, Quantity: {current_quantity}")
#         else:
#             print(f"Failed to zero out tender. Status code: {response.status_code}")
#             break
        
#         # Decrease the tender quantity
#         tender_quantity -= current_quantity
#         sleep(0.1)

# def zero_out_tender(session, ticker, tender_type, tender_quantity):
    # Determine the opposite action (buy if tender was a sell, and vice versa)
    opposite_action = "SELL" if tender_type == "BUY" else "BUY"

    # Fetch the order book to determine available orders to fulfill
    order_book = get_order_book(session, ticker)
    
    # Depending on whether you're buying or selling, check the opposite side of the book
    book_side = order_book['bids'] if opposite_action == "SELL" else order_book['asks']

    # Loop through the opposite side of the book and fulfill available orders
    remaining_quantity = tender_quantity
    for level in book_side:
        price = level['price']
        available_volume = level['cumulative_vol']
        
        # Determine how much to fulfill from the available volume at this price level
        fulfill_quantity = min(remaining_quantity, available_volume)
        
        # Execute a marketable limit order to accept the order at the current price level
        response = session.post(f"http://localhost:9999/v1/orders?ticker={ticker}&type=MARKET&quantity={fulfill_quantity}&price={price}&action={opposite_action}")
        
        # Handle the response
        if response.status_code == 200:
            print(f"Fulfilled {opposite_action} order for {fulfill_quantity} shares of {ticker} at price {price}")
        else:
            print(f"Failed to fulfill {opposite_action} order. Status code: {response.status_code}")
            break
        
        # Decrease the remaining quantity to zero out
        remaining_quantity -= fulfill_quantity
        if remaining_quantity <= 0:
            break  # Stop if zeroed out
        
        # sleep(0.1)  # Sleep to avoid overwhelming the server with requests too quickly

    # Check if there is any remaining quantity after attempting to zero out
    if remaining_quantity > 0:
        print(f"Warning: Unable to fully zero out, {remaining_quantity} shares remain.")

# def get_position(session, ticker):
#     """Helper function to get the current position for the given ticker."""
#     response = session.get(f"http://localhost:9999/v1/securities?ticker={ticker}")
#     if response.status_code == 200:
#         security_info = response.json()
#         return security_info['position']  # Return the current position (positive or negative)
#     else:
#         raise ApiException(f"Failed to get position for {ticker}. Status code: {response.status_code}")

def get_position(session, ticker):
    """Helper function to get the current position for the given ticker."""
    response = session.get(f"http://localhost:{Port}/v1/securities?ticker={ticker}")
    if response.status_code == 200:
        security_info = response.json()
        if isinstance(security_info, list) and len(security_info) > 0:
            return security_info[0]['position']  # Access the first item in the list and return its position
        else:
            raise ApiException(f"No position data found for ticker {ticker}.")
    else:
        raise ApiException(f"Failed to get position for {ticker}. Status code: {response.status_code}")



def zero_out_tender(session, ticker):
    """
    Continuously check the current position and zero it out by fulfilling available orders
    until the position reaches zero.
    """
    # Loop until the position is fully zeroed out
    while True:
        # Check the current position for the ticker
        current_position = get_position(session, ticker)

        # If the current position is zero, we're done
        if current_position == 0:
            print(f"Position for {ticker} is fully zeroed out.")
            break

        # Determine whether we need to buy or sell to zero out
        action = "SELL" if current_position > 0 else "BUY"  # Sell if long (positive), Buy if short (negative)
        remaining_quantity = abs(current_position)  # We only care about the absolute value of the position

        # Fetch the order book to fulfill available orders
        order_book = get_order_book(session, ticker)
        
        # Depending on the action, check the opposite side of the book
        book_side = order_book['bids'] if action == "SELL" else order_book['asks']

        # Loop through the book to fulfill available orders
        for level in book_side:
            price = level['price']
            available_volume = level['cumulative_vol']
            
            # Determine how much to fulfill from the available volume at this price level
            fulfill_quantity = min(remaining_quantity, available_volume)
            
            # Execute a marketable limit order to fulfill the order at the current price level
            response = session.post(f"http://localhost:{Port}/v1/orders?ticker={ticker}&type=MARKET&quantity={fulfill_quantity}&price={price}&action={action}")
            
            # Handle the response
            if response.status_code == 200:
                print(f"Fulfilled {action} order for {fulfill_quantity} shares of {ticker} at price {price}")
            else:
                print(f"Failed to fulfill {action} order. Status code: {response.status_code}")
                break
            
            # Decrease the remaining quantity
            remaining_quantity -= fulfill_quantity
            if remaining_quantity <= 0:
                break  # Stop if we've zeroed out the current iteration
            
            sleep(0.1)  # Sleep to avoid overwhelming the server with requests too quickly

        # If we can't zero out more at the moment, wait a bit and retry
        sleep(1)

    print(f"Finished zeroing out the position for {ticker}.")



def zero_out_all_on_keypress(session, tickers):
    """Listens for 'z' key press and triggers zero_out_tender for all tickers when pressed."""
    print("Press 'z' to zero out positions for all tickers.")
    while True:
        if keyboard.is_pressed('z'):  # If the 'z' key is pressed
            print("Key 'z' pressed! Zeroing out positions for all tickers...")
            for ticker in tickers:
                zero_out_tender(session, ticker)  # Call zero out function for each ticker
            sleep(1)  # Add a delay to avoid multiple triggers from one keypress

def call_position_on_keypress(session, tickers):
    """Listens for 'p' key press and triggers get_position for all tickers when pressed."""
    print("Press 'p' to get positions for all tickers.")
    if keyboard.is_pressed('p'):  # If the 'p' key is pressed
        print("Key 'p' pressed! Getting positions for all tickers...")
        for ticker in tickers:
            position = get_position(session, ticker)  # Call get position function for each ticker
            print(f"Position for {ticker}: {position}")
        sleep(1)  # Add a delay to avoid multiple triggers from one keypress

# this is the main method containing the actual order routing logic
def main():
    seen_tenders = []
    # creates a session to manage connections and requests to the RIT Client
    with requests.Session() as s:
        # add the API key to the session to authenticate during requests
        s.headers.update(API_KEY)
        # get the current time of the case
        tick = get_tick(s)

        # while the time is <= 300
        while tick <= 300:
            tickers = ['CRZY', 'TAME']
            if keyboard.is_pressed('p'):  # If the 'p' key is pressed
                print("Key 'p' pressed! Getting positions for all tickers...")
                for ticker in tickers:
                    position = get_position(s, ticker)  # Call get position function for each ticker
                    print(f"Position for {ticker}: {position}")
            if keyboard.is_pressed('z'):  # If the 'z' key is pressed
                print("Key 'z' pressed! Zeroing out positions for all tickers...")
                for ticker in tickers:
                    zero_out_tender(s, ticker)  # Call zero out function for each ticker
            # tickers = ['CRZY', 'TAME']  # List of tickers to zero out
            # zero_out_all_on_keypress(s, tickers)  # Wait for the 'z' keypress to zero out positions for all tickers
            # array to store already seen tender id's
            # print(get_current_price(s, 'CRZY'))

            # get and print the two books to the prompt
            # books = depth_view(s)
            # print_books(books)
            tenders = get_tenders(s)
            # If the tenders array is not empty, then call the evaluation on it
            for tender in tenders:
                if tender['tender_id'] not in seen_tenders:
                    seen_tenders.append(tender['tender_id'])
                    evaluate_tender(s, tender)
            

            # refresh the case time. THIS IS IMPORTANT FOR THE WHILE LOOP
            tick = get_tick(s)

# this calls the main() method when you type 'python lt3.py' into the command prompt
if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    main()
