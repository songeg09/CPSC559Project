import json
import sqlite3
import threading
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime
import requests
from threading import Thread, Timer
import time
from flask_apscheduler import APScheduler

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///votes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

REPLICA_ID = "24.64.172.31:5001"

# Example list of all replicas, including this one
REPLICAS = ["137.186.166.119:5001", "174.0.252.58:5001"]

ELECTION_TIMEOUT = 7  # seconds, adjust based on network conditions

# Variable to keep track of the current leader
current_leader = None
election_timer = None

# Define the Vote model
class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vote = db.Column(db.String(64), nullable=False)

# Define the User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)  # In a real app, ensure you hash passwords
    email = db.Column(db.String(120), unique=True, nullable=False)

class Ballot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(250), nullable=True)
    start_date = db.Column(db.Date, nullable=False, default=date.today)
    end_date = db.Column(db.Date, nullable=False, default=date.today)

class BallotOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ballot_id = db.Column(db.Integer, db.ForeignKey('ballot.id'), nullable=False)
    option_text = db.Column(db.String(250), nullable=False)
    ballot = db.relationship('Ballot', backref=db.backref('options', lazy=True))
    votes = db.Column(db.Integer, default=0)

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

@scheduler.task('interval', id='request_snapshots', seconds=60, misfire_grace_time=900)
def request_snapshots():
    if REPLICA_ID == current_leader:
        print("requesting snapshot")
        for replica in REPLICAS:
            if replica != REPLICA_ID:
                url = f"http://{replica}/request_snapshot"
                try:
                    response = requests.get(url)
                    # Assume the response contains the snapshot
                    snapshot_data = response.json()
                    compare_and_sync_snapshot(snapshot_data, replica)
                except requests.exceptions.RequestException as e:
                    print(f"Failed to request snapshot from {replica}: {str(e)}")

@app.route('/request_snapshot', methods=['GET'])
def handle_snapshot_request():
    snapshot = create_snapshot()  # Function to create the snapshot
    return jsonify(snapshot)

def compare_and_sync_snapshot(received_snapshot, replica_id):
    # Compare with the leader's snapshot
    leader_snapshot = create_snapshot()
    
    # If they match, send an acknowledgment; if not, send the correct snapshot
    if received_snapshot == leader_snapshot:
        send_ack(replica_id)
    else:
        send_correct_snapshot(replica_id, leader_snapshot)

def send_ack(replica_id):
    url = f"http://{replica_id}/ack_snapshot"
    try:
        requests.post(url)
    except requests.exceptions.RequestException as e:
        print(f"Failed to send ACK to {replica_id}: {str(e)}")

def send_correct_snapshot(replica_id, correct_snapshot):
    url = f"http://{replica_id}/update_snapshot"
    try:
        requests.post(url, json=correct_snapshot)
    except requests.exceptions.RequestException as e:
        print(f"Failed to send correct snapshot to {replica_id}: {str(e)}")

@app.route('/ack_snapshot', methods=['POST'])
def handle_ack():
    # Logic to handle acknowledgment
    print(f"Snapshot ACKed by the leader.")
    return jsonify({"status": "ACK received"}), 200

@app.route('/update_snapshot', methods=['POST'])
def update_snapshot():
    new_snapshot = request.json
    # Logic to update the local state to match the new snapshot
    apply_snapshot(new_snapshot)
    return jsonify({"status": "Snapshot updated"}), 200

def create_snapshot():
    # Connect to your SQLite database
    conn = sqlite3.connect('votes.db')
    cursor = conn.cursor()

    # Fetch the entire state of your database
    cursor.execute("SELECT * FROM vote")
    votes = cursor.fetchall()
    cursor.execute("SELECT * FROM user")
    users = cursor.fetchall()
    cursor.execute("SELECT * FROM ballot")
    ballots = cursor.fetchall()
    cursor.execute("SELECT * FROM ballot_option")
    options = cursor.fetchall()

    # Serialize the state into a dictionary
    snapshot = {
        "votes": votes,
        "users": users,
        "ballots": ballots,
        "options": options
    }

    # Convert the dictionary to a JSON string
    snapshot_json = json.dumps(snapshot)

    # Save the snapshot to a file
    with open("snapshot.json", "w") as file:
        file.write(snapshot_json)

    # Close the database connection
    conn.close()

def apply_snapshot():
    # Read the snapshot from the file
    with open("snapshot.json", "r") as file:
        snapshot_json = file.read()
    
    snapshot = json.loads(snapshot_json)

    # Connect to your SQLite database
    conn = sqlite3.connect('votes.db')
    cursor = conn.cursor()

    # Clear existing data
    cursor.execute("DELETE FROM vote")
    cursor.execute("DELETE FROM user")
    cursor.execute("DELETE FROM ballot")
    cursor.execute("DELETE FROM ballot_option")

    # Restore the state from the snapshot
    for vote in snapshot["votes"]:
        cursor.execute("INSERT INTO vote VALUES (?, ?)", vote)
    for user in snapshot["users"]:
        cursor.execute("INSERT INTO user VALUES (?, ?, ?, ?)", user)
    for ballot in snapshot["ballots"]:
        cursor.execute("INSERT INTO ballot VALUES (?, ?, ?, ?, ?)", ballot)
    for option in snapshot["options"]:
        cursor.execute("INSERT INTO ballot_option VALUES (?, ?, ?, ?)", option)

    # Commit changes and close the connection
    conn.commit()
    conn.close()

# Leader ----------------------------------------------------------------------------------
leader_election_event = threading.Event()
leader_election_event.set()
# Election routes and logic
# Function to monitor the leader's health and initiate an election if necessary
def monitor_leader():
    global current_leader
    while True:
        print(f"Current leader is: {current_leader}")
        leader_election_event.wait()  # Wait for the event to be set
        if current_leader != REPLICA_ID:  # Skip health check if self is the leader
            print("checking leader health")
            if not check_leader_health():
                print("Leader is unresponsive, starting an election.")
                start_election()

        time.sleep(5)  # Check every 5 seconds, adjust as necessary    

# Function to send heartbeat requests to the leader
def check_leader_health():
    global current_leader
    if current_leader is None:
        return False  # No leader to check

    try:
        response = requests.get(f'http://{current_leader}/heartbeat', timeout= 5)
        if response.status_code == 200 and response.json().get('status') == 'alive':
            return True  # Leader is healthy
    except requests.exceptions.RequestException:
        return False  # Leader is unresponsive    

@app.route('/election', methods=['POST'])
def handle_election_message():
    global election_timer
    sender_id = request.json.get('sender_id')
    print(f"Election message received from {sender_id}")
    
    if REPLICA_ID > sender_id:
        # Send an OK message back
        send_message(sender_id, 'ok', {'sender_id': REPLICA_ID})
        
        # Start own election if not already in progress
        if election_timer is None:
            start_election()
    
    return jsonify({'message': 'Election message received'}), 200

def start_election():
    global election_timer, leader_election_event, current_leader
    current_leader = None
    leader_election_event.clear()  # At the start of an election
    higher_replicas = [replica for replica in REPLICAS if replica > REPLICA_ID]

    if higher_replicas:
        print(f"{REPLICA_ID} found higher replicas, sending election messages...")
        
        if not election_timer:  # Start the timer only if it's not already running
            print(f"{REPLICA_ID} starting election timer...")
            election_timer = Timer(ELECTION_TIMEOUT, check_election_timeout)
            election_timer.start()
        
        for replica in higher_replicas:
            send_message(replica, 'election', {'sender_id': REPLICA_ID})
           
    else:
        print(f"{REPLICA_ID} found no higher replicas, declaring itself as leader...")
        declare_leader()

@app.route('/ok', methods=['POST'])
def handle_ok_message():
    global election_timer
    # Stop the election timer upon receiving an OK message
    if election_timer:
        print("cancelling election timer")
        election_timer.cancel()
        election_timer = None
    
    return jsonify({'status': 'OK message received'}), 200

def check_election_timeout():
    global election_timer, current_leader, leader_election_event
    if not current_leader:  # If no leader has been elected by the timeout
        print(f"{REPLICA_ID}'s election timer expired, declaring itself as leader...")
        declare_leader()
    # Reset the timer regardless of the outcome to avoid repeated firing
    election_timer.cancel()
    election_timer = None

def declare_leader():
    global REPLICA_ID, REPLICAS, current_leader, leader_election_event
    current_leader = REPLICA_ID  # Update the current leader
    leader_election_event.set()  # Resume the monitoring loop
    print(f"{REPLICA_ID} is declaring itself as the leader and notifying others...")
    for replica in REPLICAS:
        if replica != REPLICA_ID:
            send_message(replica, 'leader', {'leader_id': REPLICA_ID})

# New route for leader declaration
@app.route('/leader', methods=['POST'])
def handle_leader_message():
    global current_leader, leader_election_event
    leader_election_event.set()
    leader_id = request.json.get('leader_id')
    current_leader = leader_id
    print(f"New leader declared: {current_leader}")
    return jsonify({'message': f'Leader {leader_id} acknowledged'}), 200

def send_message(replica_id, endpoint, data):
    url = f"http://{replica_id}/{endpoint}"
    try:
        response = requests.post(url, json=data, timeout=5)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending message to {replica_id}: {e}")
        return None


# Consencus ------------------------------------------------------------------------------

@app.before_request
def create_tables():
    db.create_all()

@app.route('/', methods=['POST'])
def receive_vote():
    vote_data = request.json
    vote = vote_data.get('vote')
    new_vote = Vote(vote=vote_data['vote'])
    db.session.add(new_vote)
    db.session.commit()
    
    # Process the vote here. For example, save it to a database.
    print(f"Replica received vote: {vote}")

    return jsonify({"success": True, "message": "Vote received"}), 200

@app.route('/register', methods=['POST'])
def register():
    data = request.form
    username = data.get('username')
    password = data.get('password')  # Remember, in real applications, always hash passwords!
    email = data.get('email')

    if not username or not password or not email:
        return jsonify({"error": "Missing data"}), 400

    # Check if the user already exists
    if User.query.filter_by(username=username).first() is not None:
        return jsonify({"error": "Username already exists"}), 400

    if User.query.filter_by(email=email).first() is not None:
        return jsonify({"error": "Email already exists"}), 400

    # Create a new user instance
    new_user = User(username=username, password=password, email=email)
    
    # Add the new user to the database
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User registered successfully"}), 200

@app.route('/ballot_list', methods=['GET'])
def ballot_list():
    ballots = Ballot.query.all()  # Fetch all ballot records from the database
    ballot_list = [{"id": ballot.id, "title": ballot.title, "description": ballot.description} for ballot in ballots]

    return jsonify(ballot_list), 200
    
@app.route('/ballot_detail/<int:ballot_id>', methods=['GET'])
def ballot_detail(ballot_id):
    ballot = Ballot.query.get(ballot_id)
    options = BallotOption.query.filter_by(ballot_id=ballot_id).all()

    ballot_data = {
        "title": ballot.title,
        "options": [{"id": option.id, "option_text": option.option_text} for option in options]
    }

    return jsonify(ballot_data)

@app.route('/ballot_edit/<int:ballot_id>', methods=['GET'])
def ballot_edit(ballot_id):
    ballot = Ballot.query.get(ballot_id)
    options = BallotOption.query.filter_by(ballot_id=ballot_id).all()


    print(ballot.title)


    ballot_data = {
        "title": ballot.title,
        "options": [{"id": option.id, "option_text": option.option_text} for option in options]
    }


    return jsonify(ballot_data)

@app.route('/submit_ballot_edit/<int:ballot_id>', methods=['POST'])
def submit_ballot_edit(ballot_id):
    # Assuming updated_options is a list of dicts with 'id' and 'option_text'
    updated_options = request.json.get("options", [])

    try:
        # Iterate through the updated options
        for option_update in updated_options:
            option_id = option_update.get("id")
            new_text = option_update.get("option_text")

            # Fetch the existing option from the database
            option = BallotOption.query.filter_by(id=option_id, ballot_id=ballot_id).first()
            if option:
                # Update the option text
                option.option_text = new_text
            else:
                return jsonify({"success": False, "message": f"Option with ID {option_id} not found"}), 404
        
        # Commit the changes to the database
        db.session.commit()

        return jsonify({"success": True, "message": "Ballot options updated successfully"}), 200
    except Exception as e:
        db.session.rollback()  # Rollback in case of error
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/vote_submit', methods=['POST'])
def vote_submit():
    option_id = request.form.get('option_id')
    option = BallotOption.query.get(option_id)
    ballot = Ballot.query.filter_by(id=option.ballot_id).first()
    options = BallotOption.query.filter_by(ballot_id=ballot.id).all()

    option.votes += 1
    db.session.commit()
    
    ballot_data = {
        "title": ballot.title,
        "ballot_id":ballot.id,
        "options": [{"id": option.id, "option_text": option.option_text, "votes":option.votes} for option in options]
    }

    return jsonify(ballot_data)

@app.route('/authenticate', methods=['POST'])
def authenticate():
    username = request.form['username']
    password = request.form['password']  # Remember, you should hash passwords in real applications

    # Query the database for the user
    user = User.query.filter_by(username=username).first()
    if user and user.password == password:  # Simple check; in real apps, use password hashing
        return jsonify({"success": True}), 200
    else:
        return jsonify({"success": False}), 401

@app.route('/create_ballot', methods=['POST'])
def create_ballot():
    data = request.json
    title = data['title']
    description = data.get('description', '')  # Optional
    start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
    end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
    options = data['options']

    new_ballot = Ballot(title=title, description=description, start_date=start_date, end_date=end_date)
    db.session.add(new_ballot)
    db.session.flush()  # Flush to assign an ID to new_ballot

    for option_text in options:
        new_option = BallotOption(ballot_id=new_ballot.id, option_text=option_text)
        db.session.add(new_option)

    db.session.commit()
    return jsonify({"success": True, "message": "Ballot and options created successfully"}), 200

@app.route('/heartbeat', methods=['GET'])
def heartbeat():
    return jsonify({"status": "alive"}), 200

if __name__ == '__main__':
    # threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)).start()
    threading.Thread(target=monitor_leader, daemon=True).start()
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)
