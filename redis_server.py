from flask import Flask, request, jsonify
import redis
import json
from datetime import datetime

# Initialize the Flask application
app = Flask(__name__)

# Initialize the Redis client
# Redis is running on localhost:6379
try:
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    # Ping Redis to check connection
    r.ping()
    print("Successfully connected to Redis!")
except redis.exceptions.ConnectionError as e:
    print(f"Could not connect to Redis: {e}")
    r = None # Set r to None if connection fails, so we can handle it later

# --- GET Request ---
@app.route('/', methods=['GET'])
def get_best_scores_for_each_player(): 
    """
    Retrieves the best historical 'coins' score for each player from Redis.
    It iterates through all "PlayerData:<player_id>" keys, where each key
    points to a Redis List of JSON string snapshots.
    Returns a JSON object with player IDs and their historically best 'coins' scores.
    """
    if not r:
        return jsonify({
            "status": "error",
            "message": "Redis connection not established."
        }), 500

    best_scores_by_player = {}
    try:
        
        player_data_keys_iterator = r.keys("PlayerData:*")
        found_any_keys = False
        print(f"Found {player_data_keys_iterator} player data keys in Redis.")
        for key_bytes in player_data_keys_iterator:
            found_any_keys = True
            player_key_str = key_bytes.decode('utf-8') # Decode key from bytes to string
            # Extract player_id from the key (e.g., "PlayerData:1001" -> "1001")
            try:
                player_id = player_key_str.split(':')[-1]
                if not player_id: # Handle cases like "PlayerData:" with no ID
                    print(f"Warning: Skipping malformed key: {player_key_str}")
                    continue
            except IndexError:
                print(f"Warning: Skipping malformed key (no ':' found): {player_key_str}")
                continue

            #print(f"Processing data for player ID: {player_id} from key {player_key_str}")

            # Get all elements from the player's data list
            # Using (0, -1) to get ALL elements. Your original had (0, -5) which skips last 4.
            player_snapshot_list_bytes = r.lrange(player_key_str, 0, -1)
            #print(f"Data entries for player {player_id}: {len(player_snapshot_list_bytes)} snapshots")

            if not player_snapshot_list_bytes:
                print(f"No data snapshots found for player {player_id} in list {player_key_str}")
                continue

            max_coins_for_player = -1 # Initialize for finding the maximum

            for snapshot_bytes in player_snapshot_list_bytes:
                #print(f"Processing snapshot for player {player_id}: {snapshot_bytes[:100]}...") # Print first 100 bytes for debugging
                try:
                    snapshot_str = snapshot_bytes.decode('utf-8')
                    player_snapshot_data = json.loads(snapshot_str)
                    #print(f"Decoded snapshot for player {player_id}: {player_snapshot_data}") # For debugging
                    # Assuming 'coins' is the field to track. Adjust if different.
                    current_coins = player_snapshot_data.get('coins')
                    print(f"Current coins for player {player_id}: {current_coins}") # For debugging
                    if current_coins is not None and isinstance(current_coins, (int, float)):
                        if current_coins > max_coins_for_player:
                            max_coins_for_player = current_coins
                    # else:
                        # print(f"Player {player_id}: Snapshot missing 'coins' or invalid type: {player_snapshot_data}")

                except json.JSONDecodeError:
                    print(f"Warning: JSONDecodeError for player {player_id} in key {player_key_str}. Snapshot: {snapshot_bytes[:100]}...")
                except Exception as e:
                    print(f"Error processing a snapshot for player {player_id}: {e}. Snapshot: {snapshot_bytes[:100]}...")
            
            if max_coins_for_player > -1: # Check if any valid score was found
                best_scores_by_player[player_id] = max_coins_for_player
            # else:
                # print(f"No valid 'coins' scores found for player {player_id} after processing snapshots.")

        if not found_any_keys:
            return jsonify({
                "status": "info",
                "message": "No player data keys (PlayerData:*) found in Redis.",
                "best_scores": {}
            }), 200
            
        return jsonify(best_scores_by_player), 200

    except redis.exceptions.RedisError as e:
        print(f"RedisError: {e}")
        return jsonify({
            "status": "error",
            "message": f"Redis error occurred: {e}"
        }), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({
            "status": "error",
            "message": f"An unexpected error occurred: {e}"
        }), 500



# --- POST Request Example ---
# This route handles POST requests to /api/data
@app.route('/', methods=['POST'])
def receive_data():
    """
    Handles POST requests to receive data.
    It expects JSON data in the request body and stores it in Redis.
    """
    if not r:
        response = {
            "status": "error",
            "message": "Redis connection not established. Cannot store data."
        }
        return jsonify(response), 500 # Internal Server Error

    # Check if the request has JSON content type
    if request.is_json:
        # Get the JSON data from the request body
        data = request.get_json()

        # Ensure 'player_id' is present in the received data
        player_id = data.get('player_id')
        if not player_id:
            response = {
                "status": "error",
                "message": "Missing 'player_id' in JSON data. Cannot store player data."
            }
            return jsonify(response), 400 # Bad Request

        print(f"Received JSON data for player {player_id}: {data}") # For debugging on the server console

        # Add a timestamp to the data
        data['timestamp'] = datetime.now().isoformat()

        # Convert the dictionary to a JSON string
        json_data_string = json.dumps(data)

        # Define the Redis key for the player's data list
        # Example: PlayerData:1001, PlayerData:1002
        redis_key = f"PlayerData:{player_id}"

        try:
            # Store the JSON string in the Redis list using RPUSH (append to the right/end)
            r.rpush(redis_key, json_data_string)
            print(f"Data for {player_id} stored in Redis key '{redis_key}'.")

            response = {
                "status": "success",
                "message": f"Data for player {player_id} received and stored in Redis successfully!",
                "received_data": data,
                "redis_key": redis_key
            }
            # Return a JSON response
            return jsonify(response), 200 # 200 OK status code

        except redis.exceptions.RedisError as e:
            print(f"Error storing data in Redis: {e}")
            response = {
                "status": "error",
                "message": f"Failed to store data in Redis: {e}"
            }
            return jsonify(response), 500 # Internal Server Error

    else:
        # If not JSON, try to get form data or other data (existing logic)
        if request.form:
            data = request.form.to_dict()
            print(f"Received form data: {data}")
            response = {
                "status": "success",
                "message": "Form data received successfully!",
                "received_data": data
            }
            return jsonify(response), 200
        elif request.data:
            data = request.data.decode('utf-8') # Decode raw data
            print(f"Received raw data: {data}")
            response = {
                "status": "success",
                "message": "Raw data received successfully!",
                "received_data": data
            }
            return jsonify(response), 200
        else:
            # If no data is found or content type is not supported
            response = {
                "status": "error",
                "message": "Request must be JSON, form-encoded, or contain raw data."
            }
            return jsonify(response), 400 # 400 Bad Request status code

# This block ensures the Flask development server runs only when the script is executed directly.
if __name__ == '__main__':
    # Run the Flask app in debug mode.
    # debug=True allows for automatic reloading on code changes and provides more detailed error messages.
    app.run(debug=True)
