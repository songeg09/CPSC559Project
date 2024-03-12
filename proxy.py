from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# List of replicas
REPLICA_ADDRESSES = [
    'http://localhost:5001/',
    'http://localhost:5002/',
    # Add other replicas as needed
]

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
    app.run(port=5000)
