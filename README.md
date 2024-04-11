In order to run each file
1. Go into terminal
2. In replica.py, change REPLICA_ID to current IP address and desired port, and change REPLICAS to list of extra replicas, on the last line change port to desired port.
3. In proxy.py, change REPLICA_ADDRESSES to list of extra replicas, same with standby_proxy.py, on the last line change port to desired port.
4. Change directories to the root folder (CPSC559Project)
5. type: python *Filename* (proxy.py, standby_proxy.py, replica.py)
