# Import necessary libraries
from flask import Flask, request, jsonify
from cassandra.cluster import Cluster, NoHostAvailable
from cassandra.query import SimpleStatement
import logging

# Configure logging for better visibility
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Cassandra connection details
CASSANDRA_HOSTS = ['localhost'] # Use 'localhost' if running Cassandra directly, or 'cassandra' if using Docker Compose with a service named 'cassandra'
CASSANDRA_PORT = 9042
KEYSPACE = 'player_management'

cluster = None
session = None

def connect_to_cassandra():
    """Establishes connection to Cassandra cluster and session."""
    global cluster, session
    try:
        cluster = Cluster(CASSANDRA_HOSTS, port=CASSANDRA_PORT)
        session = cluster.connect()
        session.set_keyspace(KEYSPACE)
        logger.info(f"Successfully connected to Cassandra at {CASSANDRA_HOSTS}:{CASSANDRA_PORT}, using keyspace {KEYSPACE}")
    except NoHostAvailable as e:
        logger.error(f"Could not connect to Cassandra: {e}")
        raise ConnectionError("Failed to connect to Cassandra. Is Cassandra running and accessible?")
    except Exception as e:
        logger.error(f"An unexpected error occurred during Cassandra connection: {e}")
        raise

# Ensure connection is established when the app starts
with app.app_context():
    try:
        connect_to_cassandra()
    except ConnectionError:
        logger.critical("Application cannot start without Cassandra connection.")
        exit(1) # Exit if Cassandra connection fails at startup

@app.route('/players', methods=['POST'])
def create_player():
    """
    API endpoint to create a new player.
    Expects JSON body with name, username, email, age, and trophies (as an object: {"gold": 0, "silver": 0, "bronze": 0}).
    Uses INSERT IF NOT EXISTS to prevent overwriting existing players on creation.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request must be JSON"}), 400

    required_fields = ['name', 'username', 'email', 'age']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields. Ensure name, username, email, and age are provided."}), 400

    name = data['name']
    username = data['username']
    email = data['email']
    age = data['age']

    trophies_by_type = data.get('trophies', {})
    if not isinstance(trophies_by_type, dict):
        return jsonify({"error": "Trophies must be an object with gold, silver, bronze keys."}), 400

    valid_trophy_types = {'gold', 'silver', 'bronze'}
    cleaned_trophies = {}
    for trophy_type, count in trophies_by_type.items():
        if trophy_type not in valid_trophy_types:
            return jsonify({"error": f"Invalid trophy type: '{trophy_type}'. Only 'gold', 'silver', 'bronze' are allowed."}), 400
        if not isinstance(count, int) or count < 0:
            return jsonify({"error": f"Trophy count for '{trophy_type}' must be a non-negative integer."}), 400
        cleaned_trophies[trophy_type] = count

    # Ensure all valid trophy types are present, defaulting to 0 if not provided
    for trophy_type in valid_trophy_types:
        if trophy_type not in cleaned_trophies:
            cleaned_trophies[trophy_type] = 0

    try:
        # Use INSERT ... IF NOT EXISTS for creating new players
        query = SimpleStatement(
            """
            INSERT INTO players (name, username, email, age, trophies_by_type)
            VALUES (%s, %s, %s, %s, %s)
            IF NOT EXISTS
            """
        )
        result = session.execute(query, (name, username, email, age, cleaned_trophies))

        if not result.was_applied:
            return jsonify({"error": f"Player with username '{username}' already exists."}), 409

        logger.info(f"Player '{username}' created successfully with trophies: {cleaned_trophies}.")
        return jsonify({"message": "Player created successfully", "player": {"username": username, "name": name, "trophies": cleaned_trophies}}), 201
    except Exception as e:
        logger.error(f"Error creating player '{username}': {e}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

@app.route('/players/<string:username>', methods=['GET'])
def get_player(username):
    """
    API endpoint to retrieve player data by username, including trophy types.
    """
    try:
        query = SimpleStatement(
            """
            SELECT name, username, email, age, trophies_by_type FROM players WHERE username = %s
            """
        )
        row = session.execute(query, (username,)).one()

        if row:
            player_data = {
                "name": row.name,
                "username": row.username,
                "email": row.email,
                "age": row.age,
                "trophies": row.trophies_by_type if row.trophies_by_type is not None else {}
            }
            logger.info(f"Retrieved player '{username}'.")
            return jsonify(player_data), 200
        else:
            logger.warning(f"Player '{username}' not found.")
            return jsonify({"error": f"Player with username '{username}' not found."}), 404
    except Exception as e:
        logger.error(f"Error retrieving player '{username}': {e}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

@app.route('/players/<string:username>', methods=['PUT'])
def update_player(username):
    """
    API endpoint to update existing player data by fetching, merging, and re-inserting the full record.
    Expects JSON body with fields to update (e.g., name, email, age).
    For trophies, provide an object like {"trophies": {"gold": 20, "silver": 5}}.
    Only provided fields will be updated. Trophy types not provided will remain unchanged.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request must be JSON"}), 400

    try:
        # 1. Fetch the existing player data
        select_query = SimpleStatement(
            """
            SELECT name, username, email, age, trophies_by_type FROM players WHERE username = %s
            """
        )
        existing_row = session.execute(select_query, (username,)).one()

        if not existing_row:
            logger.warning(f"Attempted to update non-existent player '{username}'.")
            return jsonify({"error": f"Player with username '{username}' not found for update."}), 404

        # Initialize current_player_data with existing values
        current_player_data = {
            "name": existing_row.name,
            "username": existing_row.username,
            "email": existing_row.email,
            "age": existing_row.age,
            "trophies_by_type": existing_row.trophies_by_type if existing_row.trophies_by_type is not None else {}
        }

        # 2. Merge incoming data with existing data
        if 'name' in data:
            current_player_data['name'] = data['name']
        if 'email' in data:
            current_player_data['email'] = data['email']
        if 'age' in data:
            current_player_data['age'] = data['age']

        if 'trophies' in data:
            trophies_update_data = data['trophies']
            if not isinstance(trophies_update_data, dict):
                return jsonify({"error": "Trophies update must be an object with gold, silver, bronze keys."}), 400

            valid_trophy_types = {'gold', 'silver', 'bronze'}
            for trophy_type, count in trophies_update_data.items():
                if trophy_type not in valid_trophy_types:
                    return jsonify({"error": f"Invalid trophy type for update: '{trophy_type}'. Only 'gold', 'silver', 'bronze' are allowed."}), 400
                if not isinstance(count, int) or count < 0:
                    return jsonify({"error": f"Trophy count for '{trophy_type}' must be a non-negative integer."}), 400
                current_player_data['trophies_by_type'][trophy_type] = count

        # 3. Re-insert the complete, merged record (this overwrites the existing one)
        insert_query = SimpleStatement(
            """
            INSERT INTO players (name, username, email, age, trophies_by_type)
            VALUES (%s, %s, %s, %s, %s)
            """
        )
        # No IF EXISTS needed here, as INSERT with an existing primary key overwrites
        session.execute(insert_query, (
            current_player_data['name'],
            current_player_data['username'],
            current_player_data['email'],
            current_player_data['age'],
            current_player_data['trophies_by_type']
        ))

        logger.info(f"Player '{username}' updated successfully by re-insertion.")
        return jsonify({"message": "Player updated successfully", "username": username}), 200
    except Exception as e:
        logger.error(f"Error updating player '{username}': {e}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

