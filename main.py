from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from pydantic import BaseModel
import bcrypt

# Create an instance of FastAPI
app = FastAPI()

# Connect to the MongoDB database
client = MongoClient("mongodb://localhost:27017/")
db = client['user_database']
users_collection = db.users
additional_info= db.additional_data

# Data models using Pydantic to validate data types and constraints
class UserRegistration(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class LinkID(BaseModel):
    username: str
    new_id: str

@app.route('/docs')

@app.post("/register/")
async def register_user(user: UserRegistration):
    # Hash the user's password before storing it in the database
    hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())
    # Check if the username is already taken
    if users_collection.find_one({"username": user.username}):
        raise HTTPException(status_code=400, detail="Username already registered")
    #Check if the email is already taken
    if users_collection.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    # Insert the new user into the database
    users_collection.insert_one({
        "username": user.username,
        "email": user.email,
        "password": hashed_password,
        "linked_ids": []
    })
    return {"message": "User registered successfully"}

@app.post("/login/")
async def login_user(user: UserLogin):
    # Retrieve the user record by username
    user_record = users_collection.find_one({"username": user.username})
    # Validate the password
    if user_record and bcrypt.checkpw(user.password.encode('utf-8'), user_record['password']):
        return {"message": "Login successful"}
    else:
        raise HTTPException(status_code=401, detail="Invalid username or password")

@app.post("/link-id/")
async def link_id(data: LinkID):
    user_record = users_collection.find_one({"username": data.username})
    user2_record = users_collection.find_one({"username": data.new_id})
    # Add a new ID to the user's list of linked IDs
    result = users_collection.update_one(
        {"username": data.username},
        {"$push": {"linked_ids": data.new_id}}
    )

    if result.modified_count and user_record and user2_record:
        return {"message": "ID linked successfully"}
    
    else:
        raise HTTPException(status_code=404, detail="One or More Users not found")

@app.get("/get-linked-users/{username}")
async def get_linked_users(username: str):
    # Fetch the user and retrieve the list of linked usernames (linked_ids)

    user = users_collection.find_one({"username": username})
    if user:
        return user["linked_ids"]
    else:
        raise HTTPException(status_code=404, detail="User not found") 



@app.delete("/delete-user/{username}")
async def delete_user(username: str):
    users_result1= users_collection.find_one({"username": username})
    # Delete the user and any associated data in 'additional_data' collection
    linked_usernames = users_result1["linked_ids"]
    users_result = users_collection.delete_one({"username": username})
    if users_result:
        print(linked_usernames)
        # Delete the user and their linked users
        delete_result = users_collection.delete_many({"username": {"$in": [username] + linked_usernames}})
        
        # Optionally, you might want to clean up references in other users' linked_ids
        if linked_usernames:
            users_collection.update_many({}, {"$pull": {"linked_ids": {"$in": [username] + linked_usernames}}})
    additional_data_collection = db.additional_data
    additional_data_result = additional_data_collection.delete_many({"user_id": username})
    if users_result.deleted_count:
        return {"message": f"User and all associated data deleted: {delete_result.deleted_count} and {additional_data_result.deleted_count} items from additional data deleted."}
    else:
        raise HTTPException(status_code=404, detail="User not found")
