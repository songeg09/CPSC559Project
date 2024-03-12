document.getElementById('vote-form').onsubmit = function(event) {
    event.preventDefault();

    // Get the selected vote value
    const vote = document.querySelector('input[name="vote"]:checked').value;

    // Send the vote to the proxy server
    fetch('http://127.0.0.1:5000/vote', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ vote: vote })
    })
    .then(response => response.json())
    .then(data => alert(data.status))
    .catch(error => alert('Error sending vote: ' + error));
};