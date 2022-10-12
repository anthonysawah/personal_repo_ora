# Loading a JSON File to a Python Dictionary
import json

with open("test.json") as jsonFile:
        data = json.load(jsonFile)
        jsonData = data["Users"]

for username in data['Users']:
    if str(username['syspriv']) != "":
        print("Grant " + str(username['syspriv']), " to " + (username['username']) + ";")
    if str(username['object']) != "":
        print("Grant " + str(username['object_priv']) + " ON " + str(username['object']) + " to " + (username['username']) + ";")
