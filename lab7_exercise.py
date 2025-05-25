import redis
import json
from datetime import datetime  # Import datetime module to format time
 

def earn(player_id, amount):
    # Get current time and format it as day/month/year - hour:minute:second
    timestamp = datetime.now().strftime("%d/%m/%Y - %H:%M:%S")
    # Complete the code
    transaction_string = json.dumps({'timestamp': timestamp, 'transaction_amount': amount})
    r.lpush(f'player:{player_id}:transactions', transaction_string)
 

def spend(player_id, amount):
    # Get current time and format it as day/month/year - hour:minute:second
    timestamp = datetime.now().strftime("%d/%m/%Y - %H:%M:%S")
    # complete the code
    transaction_string = json.dumps({'timestamp': timestamp, 'transaction_amount': -amount})
    r.lpush(f'player:{player_id}:transactions', transaction_string)
 

 # Complete the code
def history(player_id):
    # return the transaction history
    transactions_history = r.lrange(f'player:{player_id}:transactions', 0, -1)
    transactions = []
    for i in transactions_history:
        transactions.append(json.loads(i))
    return transactions
 

def get_balance(player_id):
    transactions = r.lrange(f'player:{player_id}:transactions', 0, -1)
    deltas = []
    for i in transactions:
        deltas.append(json.loads(i)['transaction_amount'])
    return sum(deltas)
    

def main():
    # Test the functions
    earn('1001', 100)
    earn('1001', 200)
    spend('1001', 50)
    print(get_balance('1001'))
    print(history('1001'))
 

if __name__ == '__main__':
    r = redis.Redis(
    host='localhost',
    port=6379,
    password='',
    decode_responses=True)
    r.flushall()
    main()

'''
Explanation of Changes and Problem Solutions:

Consistent Key Name: The most critical problem was the inconsistency in the key names used to store and retrieve data.

earn and spend functions were using f'player:{player_id}:transactions'
history and get_balance functions were using f'player_transactions:{player_id}'
I've standardized all key names to use f'player:{player_id}:transactions' to ensure data is stored and retrieved from the same location.
transaction_amount Key: The get_balance function was looking for a key named 'transaction_amount' within the JSON data. I've ensured that both earn and spend functions now use this key when creating the JSON string.

Decoding in history(): The history() function was unnecessarily decoding the JSON string twice. I've simplified it to decode once and directly append the resulting dictionary to the transactions list.

Efficiency: The history() function is made more efficient by directly appending the parsed JSON data to the transactions list, removing redundant steps.

With these corrections, the code should now function as intended, correctly storing, retrieving, and calculating player balances.


Sources and related content

'''