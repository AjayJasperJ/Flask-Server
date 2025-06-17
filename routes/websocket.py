from flask import Blueprint, request
from flask_socketio import SocketIO, emit
from db import get_db_connection
import redis
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
ONLINE_USERS_KEY = "online_users"
connected_users = {}
socket_io = SocketIO()  # Do NOT pass app here; do it in app.py
ws_chat_bp = Blueprint('ws_chat', __name__)

@socket_io.on('connect')
def on_connect():
    print(f"Client connected: {request.sid}")

@socket_io.on('disconnect')
def on_disconnect():
    sid = request.sid
    userid = None
    for uid, user_sid in list(connected_users.items()):
        if user_sid == sid:
            userid = uid
            del connected_users[uid]
            break
    if userid:
        try:
            redis_client.srem(ONLINE_USERS_KEY, userid)
            # Broadcast updated online users list
            online_users = list(redis_client.smembers(ONLINE_USERS_KEY))
            emit('online_users', online_users, broadcast=True)
        except redis.RedisError as re:
            print(f"Redis error on disconnect: {re}")
    print(f"User disconnected: {userid if userid else sid}")
@socket_io.on('register')
def handle_register(data):
    userid = data.get('userid') or data.get('id')
    if not userid:
        emit('register_response', {
            "success": "false",
            "message": "Missing userid"
        })
        return
    connected_users[userid] = request.sid
    # Add user to Redis set with error handling
    try:
        redis_client.sadd(ONLINE_USERS_KEY, userid)
    except redis.RedisError as re:
        emit('register_response', {
            "success": "false",
            "message": f"Redis error: {str(re)}"
        })
        return
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = "UPDATE users SET ws_id = %s WHERE id = %s"
            cursor.execute(query, (request.sid, userid))
            conn.commit()
            updated = cursor.rowcount
        conn.close()

        if updated:
            emit('register_response', {
                "success": "true",
                "message": "WebSocket ID registered successfully!",
                "content": {
                    "userid": userid,
                    "ws_id": request.sid
                }
            })
            # Broadcast updated online users list with error handling
            try:
                online_users = list(redis_client.smembers(ONLINE_USERS_KEY))
                emit('online_users', online_users, broadcast=True)
            except redis.RedisError as re:
                print(f"Redis error during broadcast: {re}")
        else:
            emit('register_response', {
                "success": "false",
                "message": "Invalid userid!"
            })
    except Exception as e:
        emit('register_response', {
            "success": "false",
            "message": str(e)
        })
@socket_io.on('chat')
def handle_chat(data):
    try:
        sender = data.get('from')
        receiver = data.get('to')
        message = data.get('msg')

        if not sender or not receiver or not message:
            emit('error', "❌ Invalid payload. Required: from, to, msg", to=request.sid)
            return

        payload = {'from': sender, 'to': receiver, 'msg': message}

        if receiver == 'all':
            emit('chat', payload, broadcast=True)
            save_message_to_db(int(sender), 1, message)  # Store in admin chat
        else:
            # Always store the message in the DB
            save_message_to_db(int(sender), int(receiver), message)
            # If recipient is online, emit the message
            if str(receiver) in connected_users:
                receiver_sid = connected_users[str(receiver)]
                emit('chat', payload, to=receiver_sid)
                emit('chat', payload, to=request.sid)
            else:
                emit('status', f"⚠️ {receiver} is not online, message stored in DB", to=request.sid)

    except Exception as e:
        print(f"❌ Chat error: {e}")
        emit('error', 'Something went wrong', to=request.sid)
def save_message_to_db(sender_id, receiver_id, message):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            room_id = get_or_create_private_room(sender_id, receiver_id, cursor)
            cursor.execute("""
                INSERT INTO messages (room_id, sender_id, message)
                VALUES (%s, %s, %s)
            """, (room_id, sender_id, message))
            # Update last_message_at in chat_rooms
            cursor.execute("""
                UPDATE chat_rooms SET last_message_at = NOW(6) WHERE id = %s
            """, (room_id,))
            conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Failed to save message to DB: {e}")
def get_or_create_private_room(sender_id, receiver_id, cursor):
    # Always order IDs to ensure unique room for a pair
    user1, user2 = sorted([int(sender_id), int(receiver_id)])
    cursor.execute("""
        SELECT rp1.room_id FROM room_participants rp1
        JOIN room_participants rp2 ON rp1.room_id = rp2.room_id
        WHERE rp1.user_id = %s AND rp2.user_id = %s AND rp1.room_id != 0
        LIMIT 1
    """, (user1, user2))
    result = cursor.fetchone()
    if result:
        return result['room_id']
    # Create room
    cursor.execute("INSERT INTO chat_rooms (created_by) VALUES (%s);", (user1,))
    new_room_id = cursor.lastrowid
    cursor.execute("""
        INSERT IGNORE INTO room_participants (room_id, user_id) VALUES
        (%s, %s), (%s, %s)
    """, (new_room_id, user1, new_room_id, user2))
    return new_room_id


@socket_io.on('create_group')
def handle_create_group(data):
    name = data.get('name')
    created_by = data.get('created_by')
    user_ids = data.get('user_ids')  # List of user IDs
    if not name or not created_by or not user_ids or not isinstance(user_ids, list):
        emit('create_group_response', {"success": False, "message": "Missing or invalid data"}, to=request.sid)
        return
    room_id = create_group_chat_room(name, created_by, user_ids)
    emit('create_group_response', {"success": True, "room_id": room_id}, to=request.sid)
def create_group_chat_room(name, created_by, user_ids):
    """
    name: Group name
    created_by: User ID of creator
    user_ids: List of user IDs to add (including creator)
    """
    conn = get_db_connection()
    with conn.cursor() as cursor:
        # Create the group chat room
        cursor.execute("""
            INSERT INTO chat_rooms (name, created_by, is_group)
            VALUES (%s, %s, TRUE)
        """, (name, created_by))
        room_id = cursor.lastrowid

        # Add all users to room_participants
        values = ','.join(['(%s, %s)'] * len(user_ids))
        params = []
        for uid in user_ids:
            params.extend([room_id, uid])
        cursor.execute(f"""
            INSERT IGNORE INTO room_participants (room_id, user_id)
            VALUES {values}
        """, params)
        conn.commit()
    conn.close()
    return room_id

def add_user_to_group(room_id, user_id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT IGNORE INTO room_participants (room_id, user_id)
            VALUES (%s, %s)
        """, (room_id, user_id))
        conn.commit()
    conn.close()

def handle_group_message(sender_id, room_id, message):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        # Store message
        cursor.execute("""
            INSERT INTO messages (room_id, sender_id, message)
            VALUES (%s, %s, %s)
        """, (room_id, sender_id, message))
        # Update last_message_at
        cursor.execute("""
            UPDATE chat_rooms SET last_message_at = NOW(6) WHERE id = %s
        """, (room_id,))
        # Get all participants
        cursor.execute("""
            SELECT user_id FROM room_participants WHERE room_id = %s
        """, (room_id,))
        participants = [str(row['user_id']) for row in cursor.fetchall()]
    conn.close()
    # Emit to all connected users in the group
    payload = {'from': sender_id, 'room_id': room_id, 'msg': message}
    for uid in participants:
        if uid in connected_users:
            emit('chat', payload, to=connected_users[uid])



@socket_io.on('mark_delivered')
def handle_mark_delivered(data):
    message_id = data.get('message_id')
    user_id = data.get('user_id')
    if message_id and user_id:
        mark_message_delivered(message_id, user_id)

@socket_io.on('mark_read')
def handle_mark_read(data):
    message_id = data.get('message_id')
    user_id = data.get('user_id')
    if message_id and user_id:
        mark_message_read(message_id, user_id)

def mark_message_delivered(message_id, user_id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            UPDATE message_status SET status='delivered'
            WHERE message_id=%s AND user_id=%s
        """, (message_id, user_id))
        conn.commit()
    conn.close()

def mark_message_read(message_id, user_id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            UPDATE message_status SET status='read'
            WHERE message_id=%s AND user_id=%s
        """, (message_id, user_id))
        conn.commit()
    conn.close()
@socket_io.on('fetch_unread')
def handle_fetch_unread(data):
    user_id = data.get('user_id')
    if not user_id:
        emit('fetch_unread_response', {
            "success": False,
            "message": "Missing user_id"
        }, to=request.sid)
        return
    try:
        messages = fetch_unread_messages(user_id)
        emit('fetch_unread_response', {
            "success": True,
            "messages": messages
        }, to=request.sid)
    except Exception as e:
        emit('fetch_unread_response', {
            "success": False,
            "message": str(e)
        }, to=request.sid)
def fetch_unread_messages(user_id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT m.* FROM messages m
            JOIN message_status ms ON m.id = ms.message_id
            WHERE ms.user_id=%s AND ms.status != 'read'
            ORDER BY m.created_at ASC
        """, (user_id,))
        messages = cursor.fetchall()
    conn.close()
    return messages
