from flask import Flask, request, jsonify
import redis
import json
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)
# Configure Redis connection
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

@app.route('/data', methods=['GET', 'POST'])
def manage_data():
    if request.method == 'POST':
        # Get data from the request
        data = request.get_json()
        key = data.get('key')
        value = data.get('value')
        if key and value:
            redis_client.set(key, value)  # Store data in Redis
            return jsonify({'message': 'Data stored successfully'}), 201
        else:
            return jsonify({'message': 'Key and value are required'}), 400
    elif request.method == 'GET':
        # Get data from Redis
        key = request.args.get('key')
        if key:
            value = redis_client.get(key)
            if value:
                return jsonify({'key': key, 'value': value.decode('utf-8')}) # Decode bytes to string
            else:
                return jsonify({'message': 'Data not found'}), 404
        else:
            # Get all keys and their values
            all_data = {}
            for key in redis_client.scan_iter():
                all_data[key.decode('utf-8')] = redis_client.get(key).decode('utf-8')
            return jsonify(all_data), 200 
    

@app.route('/data/<key>', methods=['DELETE'])
def delete_data(key):
    # Delete data from Redis
    if redis_client.delete(key):
        return jsonify({'message': 'Data deleted successfully'}), 200
    else:
        return jsonify({'message': 'Data not found'}), 404

@app.route('/data/<key>', methods=['PUT']) 
def update_data(key):
    # Update data in Redis
    data = request.get_json()
    value = data.get('value')
    if value:
        redis_client.set(key, value)
        return jsonify({'message': 'Data updated successfully'}), 200
    else:
        return jsonify({'message': 'Value is required'}), 400

@app.route('/')
def index():
    return ""

if __name__ == '__main__':
    app.run(debug=True)