import os
from flask import Flask, render_template, request, jsonify, send_from_directory, session
import requests
from flask import Flask, request, redirect, url_for

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
    return render_template('signup.html')

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
    return redirect(url_for('index'))
    return jsonify({"success": True, "message": "Registration successful"}), 200



@app.route('/ballot_list', methods=['GET'])
def ballot_list():
    ballots = []
    errors = []

    for replica in REPLICA_ADDRESSES:
        try:
            response = requests.get(replica + "ballot_list")
            if response.status_code == 200:
                ballots.extend(response.json())  # Assuming each replica returns a list of ballots
            else:
                errors.append(f"Error from replica {replica}: {response.text}")
        except requests.exceptions.RequestException as e:
            errors.append(f"Request failed for replica {replica}: {str(e)}")

    if errors:
        return jsonify({"success": False, "errors": errors}), 500
    # Assuming you have a 'ballot_list.html' template to render ballots
    return render_template('ballot_list.html', ballots=ballots)


@app.route('/votingpage')
def votingpage():
    return send_from_directory('static', 'votingpage.html')

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
                        return redirect(url_for('index'))
                        return jsonify({"success": True, "message": "Login successful"}), 200
            except requests.exceptions.RequestException as e:
                continue  # If a replica fails, try the next one

        return jsonify({"success": False, "message": "Login failed"}), 401  # Authentication failed
    else:
        # Serve the login page for GET requests
        return render_template('login.html')

@app.route('/logout')
def logout():
    # Clear the user session
    session.pop('user', None)
    # Redirect the user to the home page
    return redirect(url_for('index'))

@app.route('/ballot_create', methods=['GET', 'POST'])
def ballot_create():
    if request.method == 'POST':
        title = request.form['title']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        options = request.form.getlist('options[]')  # Extracts all input fields named 'options[]'
        
        ballot_data = {
            'title': title,
            'start_date': start_date,
            'end_date': end_date,
            'options': options
        }
        
        errors = []

        for replica in REPLICA_ADDRESSES:
            try:
                response = requests.post(replica + "create_ballot", json=ballot_data)  # Notice the use of json=ballot_data here
                if response.status_code != 200:
                    errors.append(f"Error from replica {replica}: {response.text}")
            except requests.exceptions.RequestException as e:
                errors.append(f"Request failed for replica {replica}: {str(e)}")

        if errors:
            return render_template('ballot_create.html', errors=errors)
        
        return redirect(url_for('ballot_list'))

    return render_template('ballot_create.html')



if __name__ == '__main__':
    app.run(port=5000)
