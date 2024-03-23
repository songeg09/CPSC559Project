import threading
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime
import requests
from threading import Thread
import time

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///votes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

REPLICA_ID = "24.64.172.31:5001"

# Example list of all replicas, including this one
REPLICAS = ["137.186.166.119:5001", "174.0.252.58:5001"]

# Variable to keep track of the current leader
current_leader = None

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


# Election routes and logic
# Function to monitor the leader's health and initiate an election if necessary
def monitor_leader():
    global current_leader
    while True:
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
        response = requests.get(f'http://{current_leader}/heartbeat')
        if response.status_code == 200 and response.json().get('status') == 'alive':
            return True  # Leader is healthy
    except requests.exceptions.RequestException:
        return False  # Leader is unresponsive    

@app.route('/election', methods=['POST'])
def handle_election_message():
    sender_id = request.json.get('sender_id')
    print(f"Election message received from {sender_id}")
    if REPLICA_ID > sender_id:
        # Send an OK message back to the sender to acknowledge the election message
        send_message(sender_id, 'ok', {'sender_id': REPLICA_ID})
        # Start the election process
        start_election()
    return jsonify({'message': 'Election message received'}), 200

def start_election():
    global REPLICA_ID, REPLICAS
    higher_replicas = [replica for replica in REPLICAS if replica > REPLICA_ID]
    for replica in higher_replicas:
        send_message(replica, 'election', {'sender_id': REPLICA_ID})
    if not higher_replicas:
        declare_leader()

def declare_leader():
    global REPLICA_ID, REPLICAS, current_leader
    print(f"{REPLICA_ID} is declaring itself as the leader.")
    current_leader = REPLICA_ID
    for replica in REPLICAS:
        if replica != REPLICA_ID:
            send_message(replica, 'leader', {'leader_id': REPLICA_ID})

# New route for leader declaration
@app.route('/leader', methods=['POST'])
def handle_leader_message():
    global current_leader
    leader_id = request.json.get('leader_id')
    current_leader = leader_id
    print(f"New leader declared: {current_leader}")
    return jsonify({'message': f'Leader {leader_id} acknowledged'}), 200

def send_message(replica_id, endpoint, data):
    replica_ip, replica_port = replica_id.split(':')
    url = f"http://{replica_ip}:{replica_port}/{endpoint}"
    try:
        response = requests.post(url, json=data)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending message to {replica_id}: {e}")
        return None


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
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)).start()
    threading.Thread(target=monitor_leader, daemon=True).start()
