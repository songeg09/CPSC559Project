import os
import threading
from threading import Lock
import time
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

active_replicas = REPLICA_ADDRESSES.copy()  # Start with all replicas considered active
replica_lock = Lock()  # Lock for thread-safe operations on the active_replicas list
inactive_replicas = []  # List to keep track of downed replicas

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/signup')
def signup():
    return render_template('signup.html')

@app.route('/submit_registration', methods=['POST'])
def submit_registration():
    global active_replicas
    user_data = request.form
    errors = []

    with replica_lock:
        for replica in active_replicas:
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
    global active_replicas
    ballots = []
    errors = []

    with replica_lock:
        for replica in active_replicas:
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


@app.route('/ballot_detail/<int:ballot_id>', methods=['GET'])
def ballot_detail(ballot_id):
    global active_replicas


@app.route('/vote_list', methods=['GET'])
def vote_list():
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
    # Assuming you have a 'voting_list.html' template to render ballots
    return render_template('vote_list.html', ballots=ballots)


@app.route('/vote_detail/<int:ballot_id>', methods=['GET'])
def vote_detail(ballot_id):

    ballot_data = []
    errors = []

    with replica_lock:
        for replica in active_replicas:
            try:
                response = requests.get(f"{replica}/ballot_detail/{ballot_id}")
                if response.status_code == 200:
                    ballot_data.append(response.json())  # Assuming each replica returns a list of ballots
                else:
                    errors.append(f"Error from replica {replica}: {response.text}")
            except requests.exceptions.RequestException as e:
                errors.append(f"Request failed for replica {replica}: {str(e)}")

    if errors:
        return jsonify({"success": False, "errors": errors}), 500

    ballot_title = ballot_data[0]["title"]
    ballot_options = [option for data in ballot_data for option in data['options']]

    return render_template('vote_detail.html', title=ballot_title, options=ballot_options)

@app.route('/vote_submit', methods=['POST'])
def vote_submit():
    return

@app.route('/ballot_edit/<int:ballot_id>', methods=['GET'])
def ballot_edit(ballot_id):
    global active_replicas
    ballot_data = []
    errors = []

    with replica_lock:
        for replica in active_replicas:
            try:
                response = requests.get(f"{replica}/ballot_edit/{ballot_id}")
                if response.status_code == 200:
                    ballot_data.append(response.json())  # Assuming each replica returns a list of ballots
                else:
                    errors.append(f"Error from replica {replica}: {response.text}")
            except requests.exceptions.RequestException as e:
                errors.append(f"Request failed for replica {replica}: {str(e)}")

    if errors:
        return jsonify({"success": False, "errors": errors}), 500

    ballot_title = ballot_data[0]["title"]
    ballot_options = [option for data in ballot_data for option in data['options']]

    return render_template('ballot_edit.html', title=ballot_title, options=ballot_options)


@app.route('/votingpage')
def votingpage():
    return send_from_directory('static', 'votingpage.html')

@app.route('/vote', methods=['POST'])
def forward_vote():
    global active_replicas
    vote_data = request.json
    errors = []

    with replica_lock:
        for replica in active_replicas:
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
    global active_replicas
    if request.method == 'POST':
        login_data = request.form
        with replica_lock:
            for replica in active_replicas:
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
    global active_replicas
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
        with replica_lock:
            for replica in active_replicas:
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

def check_replica_health():
    global active_replicas, inactive_replicas
    while True:
        with replica_lock:
            current_active = active_replicas.copy()
            current_inactive = inactive_replicas.copy()

        # Check active replicas and move unresponsive ones to inactive list
        for replica in current_active:
            try:
                response = requests.get(replica + "heartbeat")
                if not (response.status_code == 200 and response.json().get('status') == 'alive'):
                    with replica_lock:
                        if replica in active_replicas:  # Double-check with the lock held
                            active_replicas.remove(replica)
                            inactive_replicas.append(replica)
                            print(f"Replica {replica} is down and moved to inactive list.")
            except requests.exceptions.RequestException:
                with replica_lock:
                    if replica in active_replicas:  # Double-check with the lock held
                        active_replicas.remove(replica)
                        inactive_replicas.append(replica)
                        print(f"Replica {replica} is down and moved to inactive list.")

        # Attempt to re-add inactive replicas if they're back online
        for replica in current_inactive:
            try:
                response = requests.get(replica + "heartbeat")
                if response.status_code == 200 and response.json().get('status') == 'alive':
                    with replica_lock:
                        if replica in inactive_replicas:  # Double-check with the lock held
                            inactive_replicas.remove(replica)
                            active_replicas.append(replica)
                            print(f"Replica {replica} has recovered and moved back to active list.")
            except requests.exceptions.RequestException:
                pass  # If the replica is still down, leave it in the inactive list

        time.sleep(60)  # Check every 60 seconds

if __name__ == '__main__':
    threading.Thread(target=check_replica_health, daemon=True).start()
    app.run(port=5000)
    
