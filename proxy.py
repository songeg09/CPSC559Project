import os
import threading
from threading import Lock
import time
from flask import Flask, render_template, request, jsonify, send_from_directory, session
import requests
from flask import Flask, request, redirect, url_for
from concurrent.futures import ThreadPoolExecutor, as_completed, FIRST_COMPLETED, wait
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__, static_folder='static')
app.secret_key = 'your_secret_key'
# List of replicas
REPLICA_ADDRESSES = [
    'http://127.0.0.1:5001/',
    #'http://24.64.172.31:5001/',
    #'http://174.0.252.58:5001/',
    #'http://137.186.166.119:5001/',
    # 'http://localhost:5002/',
    # Add other replicas as needed
]

active_replicas = REPLICA_ADDRESSES.copy()  # Start with all replicas considered active
replica_lock = Lock()  # Lock for thread-safe operations on the active_replicas list
inactive_replicas = []  # List to keep track of downed replicas

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup')
def signup():
    return render_template('signup.html')

def submit_registration_to_replica(replica, user_data):
    try:
        response = requests.post(replica + "register", data=user_data)
        if response.status_code != 200:
            return f"Error from replica {replica}: {response.text}"
    except requests.exceptions.RequestException as e:
        return f"Request failed for replica {replica}: {str(e)}"
    return None  # Return None if there was no error

@app.route('/submit_registration', methods=['POST'])
def submit_registration():
    user_data = request.form
    errors = []

    with ThreadPoolExecutor(max_workers=len(active_replicas)) as executor:
        # Initiate all the POST requests concurrently
        future_to_replica = {executor.submit(submit_registration_to_replica, replica, user_data): replica for replica in active_replicas}

        # As each future completes, check if there was an error
        for future in as_completed(future_to_replica):
            error = future.result()
            if error:
                errors.append(error)

    if errors:
        flash({"Signup failed": errors})
        return redirect(url_for('signup')) 
        # return jsonify({"success": False, "errors": errors}), 500
    return redirect(url_for('login'))

def fetch_ballot_list(replica):
    try:
        response = requests.get(replica + "ballot_list")
        if response.status_code == 200:
            return response.json()  # Assuming each replica returns a list of ballots
        else:
            return {"error": f"Error from replica {replica}: {response.text}"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed for replica {replica}: {str(e)}"}

@app.route('/ballot_list', methods=['GET'])
def ballot_list():
    global active_replicas
    ballots = []
    errors = []

    with ThreadPoolExecutor(max_workers=len(active_replicas)) as executor:
        future_to_replica = {executor.submit(fetch_ballot_list, replica): replica for replica in active_replicas}
        done, _ = wait(future_to_replica.keys(), return_when=FIRST_COMPLETED)
        for future in done:
            data = future.result()
            if "error" in data:
                errors.append(data["error"])
            else:
                ballots.extend(data)
        # for future in as_completed(future_to_replica):
        #     replica = future_to_replica[future]
        #     try:
        #         data = future.result()
        #         if "error" in data:
        #             errors.append(data["error"])
        #         else:
        #             ballots.extend(data)
        #     except Exception as exc:
        #         errors.append(f"Replica {replica} generated an exception: {str(exc)}")

    if errors:
        return jsonify({"success": False, "errors": errors}), 500
    # Assuming you have a 'ballot_list.html' template to render ballots
    return render_template('ballot_list.html', ballots=ballots)

def fetch_vote_list_from_replica(replica):
    try:
        response = requests.get(replica + "ballot_list")
        if response.status_code == 200:
            return response.json()  # Assuming each replica returns a list of ballots
        else:
            return {"error": f"Error from replica {replica}: {response.text}"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed for replica {replica}: {str(e)}"}

@app.route('/vote_list', methods=['GET'])
def vote_list():
    ballots = []
    errors = []

    # Use ThreadPoolExecutor to fetch ballot lists concurrently from all active replicas
    with ThreadPoolExecutor(max_workers=len(active_replicas)) as executor:
        future_to_replica = {executor.submit(fetch_vote_list_from_replica, replica): replica for replica in active_replicas}
         # Use wait with FIRST_COMPLETED to return as soon as the first successful response is received
        done, _ = wait(future_to_replica.keys(), return_when=FIRST_COMPLETED)
        for future in done:
            data = future.result()
            if "error" in data:
                errors.append(data["error"])
            else:
                ballots.extend(data)
        # for future in as_completed(future_to_replica):
        #     data = future.result()
        #     if "error" in data:
        #         errors.append(data["error"])
        #     else:
        #         ballots.extend(data)

    if errors:
        return jsonify({"success": False, "errors": errors}), 500
    return render_template('vote_list.html', ballots=ballots)

def fetch_ballot_detail(replica, ballot_id):
    try:
        response = requests.get(f"{replica}/ballot_detail/{ballot_id}")
        if response.status_code == 200:
            return response.json()  # Return the JSON response from the replica
        else:
            return {"error": f"Error from replica {replica}: {response.text}"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed for replica {replica}: {str(e)}"}

@app.route('/vote_detail/<int:ballot_id>', methods=['GET'])
def vote_detail(ballot_id):
    global active_replicas
    # ballot_data = []
    # errors = []

    with ThreadPoolExecutor(max_workers=len(active_replicas)) as executor:
        # Create a future for each replica
        future_to_replica = {executor.submit(fetch_ballot_detail, replica, ballot_id): replica for replica in active_replicas}
        
        # Use wait with FIRST_COMPLETED to return as soon as the first successful response is received
        done, _ = wait(future_to_replica.keys(), return_when=FIRST_COMPLETED)

        # Check the completed futures for a successful response
        for future in done:
            data = future.result()
            if "error" not in data:
                # Found successful data response, return this to the frontend
                return render_template('vote_detail.html', title=data.get("title", ""), options=data.get('options', []))
            else:
                # Log the error, you can also accumulate errors if needed
                print(data["error"])
                # Handle case where no valid ballot data is received
                return jsonify({"success": False, "message": "No valid ballot data received from any replica"}), 500

        # # As each future completes, process its result
        # for future in as_completed(future_to_replica):
        #     data = future.result()
        #     if "error" in data:
        #         errors.append(data["error"])
        #     else:
        #         ballot_data.append(data)

    # if errors:
    #     return jsonify({"success": False, "errors": errors}), 500

    # # Assume the first successful response has the needed data structure
    # if ballot_data:
    #     ballot_title = ballot_data[0].get("title", "")
    #     ballot_options = ballot_data[0].get('options', [])
    #     # ballot_options = [option for data in ballot_data[0] for option in data.get('options', [])]

    #     return render_template('vote_detail.html', title=ballot_title, options=ballot_options)
    # else:
    #     # Handle case where no valid ballot data is received
    #     return jsonify({"success": False, "message": "No valid ballot data received from any replica"}), 500
    
@app.route('/ballot_detail/<int:ballot_id>', methods=['GET'])
def ballot_detail(ballot_id):
    global active_replicas
    ballot_data = []
    errors = []

    with ThreadPoolExecutor(max_workers=len(active_replicas)) as executor:
        # Create a future for each replica
        future_to_replica = {executor.submit(fetch_ballot_detail, replica, ballot_id): replica for replica in active_replicas}
        done, _ = wait(future_to_replica.keys(), return_when=FIRST_COMPLETED)
        # As each future completes, process its result
        for future in done:
            data = future.result()
            if "error" in data:
                errors.append(data["error"])
            else:
                ballot_data.append(data)

    if errors:
        return jsonify({"success": False, "errors": errors}), 500

    # Assume the first successful response has the needed data structure
    if ballot_data:
        ballot_title = ballot_data[0].get("title", "")
        ballot_options = [option for data in ballot_data for option in data.get('options', [])]

        return render_template('ballot_detail.html', title=ballot_title, options=ballot_options)
    else:
        # Handle case where no valid ballot data is received
        return jsonify({"success": False, "message": "No valid ballot data received from any replica"}), 500

def fetch_vote_submit(replica, option_id):
    try:
        response = requests.post(replica + "/vote_submit", data={'option_id': option_id})
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Error from replica {replica}: {response.text}"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed for replica {replica}: {str(e)}"}

@app.route('/vote_submit', methods=['POST'])
def vote_submit():
    option_id = request.form.get('option')
    errors = []
    ballot_data = []

    with ThreadPoolExecutor(max_workers=len(active_replicas)) as executor:
        # Create a future for each replica
        future_to_replica = {executor.submit(fetch_vote_submit, replica, option_id): replica for replica in active_replicas}
    
        # As each future completes, process its result
        for future in as_completed(future_to_replica):
            data = future.result()
            if "error" in data:
                errors.append(data["error"])
            else:
                ballot_data.append(data)
    
    if errors:
        return jsonify({"success": False, "errors": errors}), 500

    # Assume the first successful response has the needed data structure
    if ballot_data:
        ballot_title = ballot_data[0].get("title", "")
        ballot_id = ballot_data[0].get("ballot_id", "")
        ballot_options = [option for data in ballot_data for option in data.get('options', [])]

        return render_template('vote_result.html',ballot_id = ballot_id, title=ballot_title, options=ballot_options)
    else:
        # Handle case where no valid ballot data is received
        return jsonify({"success": False, "message": "No valid ballot data received from any replica"}), 500


def fetch_ballot_from_replica(replica, ballot_id):
    try:
        response = requests.get(f"{replica}ballot_edit/{ballot_id}")
        if response.status_code == 200:
            return {'data': response.json()}
        else:
            return {'error': f"Error from replica {replica}: {response.status_code}"}
    except requests.exceptions.RequestException as e:
        return {'error': f"Request failed for replica {replica}: {str(e)}"}

@app.route('/ballot_edit/<int:ballot_id>', methods=['GET'])
def ballot_edit(ballot_id):
    with ThreadPoolExecutor(max_workers=len(REPLICA_ADDRESSES)) as executor:
        futures = [executor.submit(fetch_ballot_from_replica, replica, ballot_id) for replica in REPLICA_ADDRESSES]

        for future in as_completed(futures):
            result = future.result()
            if 'data' in result:
                ballot_data = result['data']
                return render_template('ballot_edit.html', ballot_id=ballot_id, title=ballot_data["title"], options=ballot_data["options"])
            else:
                continue  # Try the next future if the current one resulted in an error

    # If all futures result in an error, return an error message
    return "Error fetching ballot data", 500

def update_ballot_at_replica(replica, ballot_id, updated_options):
    try:
        response = requests.post(f"{replica}submit_ballot_edit/{ballot_id}", json={"options": updated_options})
        if response.status_code != 200:
            return f"Error from replica {replica}: {response.text}"
    except requests.exceptions.RequestException as e:
        return f"Request failed for replica {replica}: {str(e)}"
    return None  # Return None if there was no error



@app.route('/submit_ballot_edit/<int:ballot_id>', methods=['POST'])
def submit_ballot_edit(ballot_id):
    updated_options = [{
        "id": int(key.split('_')[1]),
        "option_text": value
    } for key, value in request.form.items() if key.startswith('option_')]

    errors = []

    with ThreadPoolExecutor(max_workers=len(active_replicas)) as executor:
        future_to_replica = {
            executor.submit(update_ballot_at_replica, replica, ballot_id, updated_options): replica
            for replica in active_replicas
        }

        for future in as_completed(future_to_replica):
            error = future.result()
            if error:
                errors.append(error)

    if errors:
        # Handle errors, e.g., by displaying them to the user
        return "Error updating ballot: " + "; ".join(errors), 500

    return redirect(url_for('ballot_edit', ballot_id=ballot_id))

@app.route('/votingpage')
def votingpage():
    return send_from_directory('static', 'votingpage.html')

def forward_vote_to_replica(replica, vote_data):
    try:
        response = requests.post(replica, json=vote_data)
        if response.status_code != 200:
            return f"Error from replica {replica}: {response.text}"
    except requests.exceptions.RequestException as e:
        return f"Request failed for replica {replica}: {str(e)}"
    return None  # Return None if there was no error


@app.route('/vote', methods=['POST'])
def forward_vote():
    vote_data = request.json
    errors = []

    # No need for replica_lock here as we are only reading from active_replicas
    with ThreadPoolExecutor(max_workers=len(active_replicas)) as executor:
        # Launch a thread for each replica
        future_to_replica = {executor.submit(forward_vote_to_replica, replica, vote_data): replica for replica in active_replicas}

        # Process the results as they become available
        for future in as_completed(future_to_replica):
            error = future.result()
            if error:
                errors.append(error)

    if errors:
        return jsonify({"success": False, "errors": errors}), 500
    return jsonify({"success": True, "message": "Vote sent to all replicas"}), 200

def authenticate_with_replica(replica, login_data):
    try:
        response = requests.post(replica + "authenticate", data=login_data)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return {'success': True, 'user': login_data['username']}
        return {'success': False}
    except requests.exceptions.RequestException:
        return {'success': False}


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_data = request.form
        authentication_results = []

        with ThreadPoolExecutor(max_workers=len(active_replicas)) as executor:
            # Launch an authentication task for each replica
            future_to_replica = {executor.submit(authenticate_with_replica, replica, login_data): replica for replica in active_replicas}

            # Process the results as they become available
            for future in as_completed(future_to_replica):
                result = future.result()
                authentication_results.append(result)
                if result['success']:
                    # If any replica successfully authenticates the user, manage session and redirect
                    session['user'] = result['user']
                    return redirect(url_for('index'))

        # If no replicas authenticate the user, return a login failed message
        # return jsonify({"success": False, "message": "Login failed"}), 401
        flash('Login failed. Please try again.')
        return redirect(url_for('login'))        
    else:
        # Serve the login page for GET requests
        return render_template('login.html')

@app.route('/logout')
def logout():
    # Clear the user session
    session.pop('user', None)
    # Redirect the user to the home page
    return redirect(url_for('index'))

def create_ballot_at_replica(replica, ballot_data):
    try:
        response = requests.post(replica + "create_ballot", json=ballot_data)
        if response.status_code == 200:
            return None  # No error
        else:
            return f"Error from replica {replica}: {response.text}"
    except requests.exceptions.RequestException as e:
        return f"Request failed for replica {replica}: {str(e)}"


@app.route('/ballot_create', methods=['GET', 'POST'])
def ballot_create():
    if request.method == 'POST':
        ballot_data = {
            'title': request.form['title'],
            'start_date': request.form['start_date'],
            'end_date': request.form['end_date'],
            'options': request.form.getlist('options[]')
        }

        errors = []

        with ThreadPoolExecutor(max_workers=len(active_replicas)) as executor:
            future_to_replica = {
                executor.submit(create_ballot_at_replica, replica, ballot_data): replica
                for replica in active_replicas
            }

            for future in as_completed(future_to_replica):
                error = future.result()
                if error:
                    errors.append(error)

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

@app.route('/heartbeat')
def heartbeat():
    return jsonify({"status": "alive"}), 200

if __name__ == '__main__':
    threading.Thread(target=check_replica_health, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
    
