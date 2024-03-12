import os
from flask import Flask, request, jsonify, send_from_directory
import requests

app = Flask(__name__, static_folder='static')

# List of replicas
REPLICA_ADDRESSES = [
    'http://127.0.0.1:5001/',
    # 'http://localhost:5002/',
    # Add other replicas as needed
]

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/signup', methods=['GET'])
def signup():
    return send_from_directory('static', 'signup.html')

@app.route('/submit_registration', methods=['POST'])
def submit_registration():
    user_data = request.form
    errors = []

    for replica in REPLICA_ADDRESSES:
        try:
            response = requests.post(replica + "register", data=user_data)
            if response.status_code != 200:
                errors.append(f"Error from replica {replica}: {response.text}")
        except requests.exceptions.RequestException as e:
            errors.append(f"Request failed for replica {replica}: {str(e)}")

    if errors:
        return jsonify({"success": False, "errors": errors}), 500
    return jsonify({"success": True, "message": "Registration successful"}), 200

@app.route('/vote', methods=['POST'])
def forward_vote():
    vote_data = request.json
    errors = []

    for replica in REPLICA_ADDRESSES:
        try:
            response = requests.post(replica, json=vote_data)
            if response.status_code != 200:
                errors.append(f"Error from replica {replica}: {response.text}")
        except requests.exceptions.RequestException as e:
            errors.append(f"Request failed for replica {replica}: {str(e)}")

    if errors:
        return jsonify({"success": False, "errors": errors}), 500
    return jsonify({"success": True, "message": "Vote sent to all replicas"}), 200

if __name__ == '__main__':
    os.makedirs('static', exist_ok=True)
    app.run(port=5000)
