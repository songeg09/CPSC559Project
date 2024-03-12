from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///votes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Define the Vote model
class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vote = db.Column(db.String(64), nullable=False)

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

if __name__ == '__main__':
    app.run(port=5001)  # Run different instances on different ports.
