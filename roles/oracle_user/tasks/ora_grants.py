# Loading a JSON File to a Python Dictionary
import json

# Read from ora_user.json
with open("test.json") as jsonFile:
        data = json.load(jsonFile)
        jsonData = data["Users"]

# Generate SQL statement from ora_user.json

#Main for Loop to extract Json Data
for GrantScriptLoop in jsonData:
    objpriv = GrantScriptLoop['object_priv']
    user = GrantScriptLoop['username']
                
                
                #For loop to get Sytem Privilege Values
                
    for syspriv in GrantScriptLoop['syspriv']:
        for sysprivVals in syspriv['syspriv_vals'].splitlines():
            
            #For loop to get Sytem Privilege Values
            
            if not 'sysprivVals' in GrantScriptLoop['syspriv'] or len(GrantScriptLoop['syspriv']) == 0:
                sql = ("Grant " + (sysprivVals) + " to " + user + ";")
                sql += '\n'

                
                 #For loop to get Object Privilege Values
            
    for object in GrantScriptLoop['object']:
       for objects in object['objects'].splitlines():
           if not 'objects' in GrantScriptLoop['object'] or len(GrantScriptLoop['object']) == 0:
                sql+= ("Grant " + (objpriv) + " ON " + str(objects) + " to " + (user) + ";")
                sql+= '\n'

print(sql)