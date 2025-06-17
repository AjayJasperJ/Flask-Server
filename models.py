from db import get_db_connection

def create_users_table():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255) NOT NULL UNIQUE,
                    password VARCHAR(255) NOT NULL,
                    ws_id VARCHAR(255) DEFAULT NULL,
                    email VARCHAR(50) NOT NULL UNIQUE,
                    gender ENUM('male', 'female', 'other') NOT NULL,
                    dob DATE NOT NULL,
                    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6)
                );
            """)
            # Ensure admin user exists
            cursor.execute("""
                INSERT IGNORE INTO users (id, username, password, email, gender, dob)
                VALUES (1, 'admin', 'admin', 'admin@example.com', 'other', '2000-01-01')
            """)
            conn.commit()
        conn.close()
        print("✅ Users table and admin ensured.")
    except Exception as e:
        print(f"❌ Error creating users table: {e}")

def create_chat_rooms_table():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_rooms (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255),
                    created_by INT NOT NULL,
                    is_group BOOLEAN DEFAULT FALSE,
                    last_message_at DATETIME(6),
                    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
                    FOREIGN KEY (created_by) REFERENCES users(id)
                );
            """)
            # Ensure room_id 0 exists for broadcast
            cursor.execute("INSERT IGNORE INTO chat_rooms (id, name, created_by, is_group) VALUES (0, 'Broadcast', 1, TRUE);")
            conn.commit()
        conn.close()
        print("✅ Chat rooms table ensured.")
    except Exception as e:
        print(f"❌ Error creating chat_rooms table: {e}")


def create_room_participants_table():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS room_participants (
                    room_id INT NOT NULL,
                    user_id INT NOT NULL,
                    joined_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
                    PRIMARY KEY (room_id, user_id),
                    FOREIGN KEY (room_id) REFERENCES chat_rooms(id),
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    INDEX idx_room_user (room_id, user_id)
                );
            """)
            conn.commit()
        conn.close()
        print("✅ Room participants table ensured.")
    except Exception as e:
        print(f"❌ Error creating room_participants table: {e}")


def create_messages_table():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    room_id INT NOT NULL,
                    sender_id INT NOT NULL,
                    message TEXT,
                    type ENUM('text', 'image', 'video', 'audio', 'file') DEFAULT 'text',
                    is_deleted BOOLEAN DEFAULT FALSE,
                    is_edited BOOLEAN DEFAULT FALSE,
                    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
                    FOREIGN KEY (room_id) REFERENCES chat_rooms(id),
                    FOREIGN KEY (sender_id) REFERENCES users(id),
                    INDEX idx_room (room_id),
                    INDEX idx_created_at (created_at),
                    INDEX idx_sender (sender_id)
                );
            """)
            conn.commit()
        conn.close()
        print("✅ Messages table ensured.")
    except Exception as e:
        print(f"❌ Error creating messages table: {e}")


def create_attachments_table():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS attachments (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    message_id BIGINT NOT NULL,
                    file_url VARCHAR(512) NOT NULL,
                    mime_type VARCHAR(50),
                    file_size INT,
                    uploaded_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
                    FOREIGN KEY (message_id) REFERENCES messages(id),
                    INDEX idx_message_id (message_id)
                );
            """)
            conn.commit()
        conn.close()
        print("✅ Attachments table ensured.")
    except Exception as e:
        print(f"❌ Error creating attachments table: {e}")


def create_message_status_table():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS message_status (
                    message_id BIGINT NOT NULL,
                    user_id INT NOT NULL,
                    status ENUM('sent', 'delivered', 'read') DEFAULT 'sent',
                    updated_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
                    PRIMARY KEY (message_id, user_id),
                    FOREIGN KEY (message_id) REFERENCES messages(id),
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    INDEX idx_msg_user (message_id, user_id)
                );
            """)
            conn.commit()
        conn.close()
        print("✅ Message status table ensured.")
    except Exception as e:
        print(f"❌ Error creating message_status table: {e}")


def create_all_tables():
    create_users_table()
    create_chat_rooms_table()
    create_room_participants_table()
    create_messages_table()
    create_attachments_table()
    create_message_status_table()
