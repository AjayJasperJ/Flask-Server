from flask import Blueprint, request, jsonify
from db import get_db_connection
import pymysql
import jwt
import datetime

SECRET_KEY = "your-very-secret-key"
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register_credential():
    data = request.get_json()
    key = request.headers.get('x-api-key')

    if key != "regkey-12345":
        return jsonify({"success": "false", "message": "Unauthorized: Invalid API Key"}), 401
    if not data or not all(k in data for k in ('username', 'email', 'dob', 'gender', 'password')):
        return jsonify({"success": "false", "message": "Missing data"}), 400

    username = data['username']
    password = data['password']
    email = data['email']
    gender = data['gender']
    dob = data['dob']

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = """
                INSERT INTO users (username, password, email, gender, dob)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(query, (username, password, email, gender, dob))
            user_id = cursor.lastrowid
            conn.commit()
        conn.close()

        return jsonify({
            "success": "true",
            "message": "Register successful",
            "content": {
                "userid": user_id,
                "username": username
            }
        }), 201

    except pymysql.err.IntegrityError:
        return jsonify({"success": "false", "message": "User already exists or invalid data"}), 409
    except Exception as e:
        return jsonify({"success": "false", "message": f"Server error: {str(e)}"}), 500

@auth_bp.route('/check_exist', methods=['POST'])
def verify_email_usage():
    data = request.get_json()
    key = request.headers.get('x-api-key')
    if key != "verify_key-12345":
        return jsonify({"success": "false", "message": "Unauthorized: Invalid API Key"}), 401

    if not data or 'username' not in data:
        return jsonify({"success": "false", "message": "Missing data"}), 400
    username = data['username']
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = "SELECT id FROM users WHERE username=%s or email=%s"
            cursor.execute(query, (username, username))
            result = cursor.fetchone()
            conn.close()

            if result:
                return jsonify({
                    "success": "false",
                    "message": "User already Exist",
                }), 401
            else:
                return jsonify({"success": "true", "message": "New User Found!"}), 401

    except Exception as e:
        return jsonify({"success": "false", "message": str(e)}), 500


@auth_bp.route('/auth', methods=['POST'])
def login_credential():
    data = request.get_json()
    key = request.headers.get('x-api-key')

    if key != "authkey-12345":
        return jsonify({"success": "false", "message": "Unauthorized: Invalid API Key"}), 401

    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"success": "false", "message": "Missing data"}), 400

    username = data['username']
    password = data['password']

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = "SELECT id, username FROM users WHERE username=%s AND password=%s"
            cursor.execute(query, (username, password))
            result = cursor.fetchone()
            conn.close()

            if result:
                # Generate JWT token
                payload = {
                    'user_id': result['id'],
                    'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)
                }
                token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
                return jsonify({
                    "success": "true",
                    "message": "Login successful",
                    "content": {
                        "userid": result['id'],
                        "username": result['username'],
                        "token": token
                    }
                }), 200
            else:
                return jsonify({"success": "false", "message": "Invalid credentials"}), 401

    except Exception as e:
        return jsonify({"success": "false", "message": str(e)}), 500
