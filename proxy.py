import os
from flask import Flask, request, jsonify, send_from_directory, session
import requests

app = Flask(__name__, static_folder='static')
app.secret_key = 'your_secret_key'
# List of replicas
REPLICA_ADDRESSES = [
    'http://127.0.0.1:5001/',
    # 'http://localhost:5002/',
    # Add other replicas as needed
]

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/signup')
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


@app.route('/ballot_list', methods=['GET'])
def ballot_list():
    errors = []
    ballot_list_data = request.json

    for replica in REPLICA_ADDRESSES:
        try:
            response = requests.get(replica + "/ballot_list")
            if response.status_code == 200:
                ballot_list_data.extend(response.json())
            else:
                errors.append(f"Error from replica {replica}: {response.text}")
        except requests.exceptions.RequestException as e:
            errors.append(f"Request failed for replica {replica}: {str(e)}")

    if errors:
        return jsonify(errors), 500

    return render_template('ballot_list.html', ballot_data=ballot_list_data)


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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_data = request.form
        for replica in REPLICA_ADDRESSES:
            try:
                # Send the login data to each replica for authentication
                response = requests.post(replica + "authenticate", data=login_data)
                if response.status_code == 200:
                    # Assume the replica returns a JSON with a success field when authentication succeeds
                    data = response.json()
                    if data.get('success'):
                        # Login successful, manage session
                        session['user'] = login_data['username']
                        return jsonify({"success": True, "message": "Login successful"}), 200
            except requests.exceptions.RequestException as e:
                continue  # If a replica fails, try the next one

        return jsonify({"success": False, "message": "Login failed"}), 401  # Authentication failed
    else:
        # Serve the login page for GET requests
        return send_from_directory('static', 'login.html')

if __name__ == '__main__':
    os.makedirs('static', exist_ok=True)
    app.run(port=5000)
