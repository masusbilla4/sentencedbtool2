"""
SentenceDB App - Streamlit Web App with Supabase
A web-based tool for managing sentence databases with real-time multi-user support.
With user authentication system.
"""

import streamlit as st
import pandas as pd
import csv
import os
import random
import json
import hashlib
from io import StringIO, BytesIO
import sqlite3
from datetime import datetime

# Supabase imports
try:
    from supabase import create_client, Client
    import httpx
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# ========== SECRETS (from st.secrets or env) ==========
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")
ADMIN_USERNAME = st.secrets.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "")

# ========== USER DATABASE FILE ==========
USERS_DB_FILE = "users.json"

# Page config
st.set_page_config(
    page_title="SentenceDB App",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    div[data-testid="stMetric"] {
        background-color: #f1f5f9;
        border-radius: 10px;
        padding: 15px;
        border: 1px solid #cbd5e1;
    }
    div[data-testid="stMetric"] > label {
        color: #1e293b !important;
        font-weight: 600;
    }
    div[data-testid="stMetric"] > div {
        color: #0f172a !important;
        font-size: 1.8rem;
        font-weight: bold;
    }
    @media (prefers-color-scheme: dark) {
        div[data-testid="stMetric"] {
            background-color: #1e293b;
            border: 1px solid #334155;
        }
        div[data-testid="stMetric"] > label {
            color: #e2e8f0 !important;
        }
        div[data-testid="stMetric"] > div {
            color: #f8fafc !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# Single table for all languages
TABLE_NAME = "sentences"

# ========== USER AUTHENTICATION FUNCTIONS ==========

def get_users_db():
    if os.path.exists(USERS_DB_FILE):
        try:
            with open(USERS_DB_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_users_db(users):
    with open(USERS_DB_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password, email=""):
    users = get_users_db()
    if username in users:
        return False, "Username already exists"
    if username.lower() == ADMIN_USERNAME.lower():
        return False, "Cannot register with admin username"
    users[username] = {
        "password": hash_password(password),
        "email": email,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "is_admin": False
    }
    save_users_db(users)
    return True, "Registration successful"

def is_admin(username):
    if username.lower() == ADMIN_USERNAME.lower():
        return True
    users = get_users_db()
    return users.get(username, {}).get("is_admin", False)

def get_admin_users():
    admins = [ADMIN_USERNAME]
    users = get_users_db()
    for username, data in users.items():
        if data.get("is_admin", False):
            admins.append(username)
    return admins

def delete_user(username):
    if username.lower() == ADMIN_USERNAME.lower():
        return False, "Cannot delete main admin account"
    users = get_users_db()
    if username in users:
        del users[username]
        save_users_db(users)
        return True, f"User '{username}' deleted"
    return False, "User not found"

def reset_user_password(username, new_password):
    if username.lower() == ADMIN_USERNAME.lower():
        return False, "Cannot reset admin password"
    users = get_users_db()
    if username in users:
        users[username]["password"] = hash_password(new_password)
        users[username]["password_reset_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_users_db(users)
        return True, f"Password reset for '{username}'"
    return False, "User not found"

def get_all_users():
    users = get_users_db()
    user_list = []
    for username, data in users.items():
        user_list.append({
            "username": username,
            "email": data.get("email", ""),
            "created_at": data.get("created_at", ""),
            "is_admin": data.get("is_admin", False),
            "password_reset_at": data.get("password_reset_at", "")
        })
    return user_list

def add_user(username, password, email="", is_admin=False):
    users = get_users_db()
    if username in users:
        return False, "Username already exists"
    if username.lower() == ADMIN_USERNAME.lower():
        return False, "Cannot use admin username"
    users[username] = {
        "password": hash_password(password),
        "email": email,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "is_admin": is_admin
    }
    save_users_db(users)
    return True, f"User '{username}' added"

def login_user(username, password):
    if username.lower() == ADMIN_USERNAME.lower():
        if password == ADMIN_PASSWORD:
            return True, "Login successful"
        return False, "Invalid username or password"
    users = get_users_db()
    if username not in users:
        return False, "Invalid username or password"
    if users[username]["password"] == hash_password(password):
        return True, "Login successful"
    return False, "Invalid username or password"

def get_current_user():
    return st.session_state.get('current_user', None)

def is_authenticated():
    return st.session_state.get('authenticated', False)

def logout_user():
    st.session_state.authenticated = False
    st.session_state.current_user = None
    st.session_state.is_admin = False
    if 'supabase_client' in st.session_state:
        del st.session_state.supabase_client
    if 'db_mode' in st.session_state:
        st.session_state.db_mode = None

# ========== INITIALIZE SESSION STATE ==========

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False
if 'cart' not in st.session_state:
    st.session_state.cart = []
if 'db_mode' not in st.session_state:
    st.session_state.db_mode = None
if 'supabase_client' not in st.session_state:
    st.session_state.supabase_client = None
if 'sqlite_path' not in st.session_state:
    st.session_state.sqlite_path = None

# ---------- SUPABASE FUNCTIONS ----------

def init_supabase(url: str = None, key: str = None) -> bool:
    if not SUPABASE_AVAILABLE:
        st.error("❌ Supabase package not installed. Run: `pip install supabase`")
        return False
    try:
        supa_url = url if url else SUPABASE_URL
        supa_key = key if key else SUPABASE_KEY
        
        if not supa_url or not supa_key or "your-" in supa_url or "your-" in supa_key:
            st.warning("⚠️ Supabase credentials not configured.")
            return False
        
        import ssl
        ssl._create_default_https_context = ssl._create_unverified_context
        
        client = create_client(supa_url, supa_key)
        
        try:
            client.table(TABLE_NAME).select("sen_id").limit(1).execute()
        except Exception as table_err:
            st.warning(f"⚠️ Connected to Supabase but table '{TABLE_NAME}' not found. Create it in the SQL Editor first.")
            return False
        
        st.session_state.supabase_client = client
        st.session_state.db_mode = 'supabase'
        return True
    except Exception as e:
        st.error(f"Failed to connect to Supabase: {str(e)}")
        return False

def get_supabase_client():
    return st.session_state.supabase_client

# ---------- SQLITE FUNCTIONS ----------

def connect_sqlite():
    if st.session_state.sqlite_path is None:
        return None
    return sqlite3.connect(st.session_state.sqlite_path, timeout=10)

def init_sqlite(db_path: str):
    st.session_state.sqlite_path = db_path
    conn = connect_sqlite()
    if conn is None:
        return False
    cursor = conn.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            sen_id TEXT PRIMARY KEY,
            sentence TEXT,
            category TEXT,
            language TEXT,
            used INTEGER DEFAULT 0,
            char_count INTEGER,
            word_count INTEGER,
            sentence_count INTEGER
        )
    """)
    conn.commit()
    conn.close()
    st.session_state.db_mode = 'sqlite'
    return True

# ---------- UNIVERSAL DATABASE FUNCTIONS ----------

def generate_sen_id(language):
    prefix = "eng" if language == "en" else "fil"
    
    if st.session_state.db_mode == 'supabase':
        client = get_supabase_client()
        result = client.table(TABLE_NAME).select("sen_id").eq("language", language).order("sen_id", desc=True).limit(1).execute()
        
        if result.data:
            last_num = int(result.data[0]['sen_id'].split('_')[-1])
            next_num = last_num + 1
        else:
            next_num = 1
        
        return f"{prefix}_{next_num:06d}"
    
    else:  # SQLite
        conn = connect_sqlite()
        cursor = conn.cursor()
        cursor.execute(f"SELECT sen_id FROM {TABLE_NAME} WHERE language=? ORDER BY sen_id DESC LIMIT 1", (language,))
        result = cursor.fetchone()
        
        if result:
            last_num = int(result[0].split('_')[-1])
            next_num = last_num + 1
        else:
            next_num = 1
        
        conn.close()
        return f"{prefix}_{next_num:06d}"

def _clear_cache():
    """Clear cached data when database changes."""
    for key in ['_cached_all_data', '_cached_stats', '_cached_remaining', '_cached_categories', '_cached_category_stats']:
        if key in st.session_state:
            del st.session_state[key]

def _get_all_data():
    """Fetch all data from Supabase and cache it."""
    if st.session_state.db_mode != 'supabase':
        return None
    if '_cached_all_data' in st.session_state:
        return st.session_state._cached_all_data
    client = get_supabase_client()
    result = client.table(TABLE_NAME).select("*").execute()
    st.session_state._cached_all_data = result.data
    return result.data

def get_stats():
    if st.session_state.db_mode == 'supabase':
        data = _get_all_data()
        fil = len([r for r in data if r.get('language') == 'fil'])
        eng = len([r for r in data if r.get('language') == 'en'])
        return fil + eng, eng, fil
    
    else:  # SQLite
        conn = connect_sqlite()
        if conn is None:
            return 0, 0, 0
        cursor = conn.cursor()
        
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE language='fil'")
        fil = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE language='en'")
        eng = cursor.fetchone()[0]
        
        conn.close()
        return fil + eng, eng, fil

def get_remaining_stats():
    if st.session_state.db_mode == 'supabase':
        data = _get_all_data()
        fil = len([r for r in data if r.get('language') == 'fil' and r.get('used', 0) == 0])
        eng = len([r for r in data if r.get('language') == 'en' and r.get('used', 0) == 0])
        return fil, eng
    
    else:  # SQLite
        conn = connect_sqlite()
        if conn is None:
            return 0, 0
        cursor = conn.cursor()
        
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE language='fil' AND (used=0 OR used IS NULL)")
        fil = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE language='en' AND (used=0 OR used IS NULL)")
        eng = cursor.fetchone()[0]
        
        conn.close()
        return fil, eng

def get_categories():
    if st.session_state.db_mode == 'supabase':
        data = _get_all_data()
        categories = set()
        for row in data:
            if row.get('category'):
                categories.add(row['category'])
        return sorted(list(categories))
    
    else:  # SQLite
        conn = connect_sqlite()
        if conn is None:
            return []
        cursor = conn.cursor()
        
        cursor.execute(f"SELECT DISTINCT category FROM {TABLE_NAME} WHERE category IS NOT NULL")
        categories = set()
        for row in cursor.fetchall():
            if row[0]:
                categories.add(row[0])
        
        conn.close()
        return sorted(list(categories))

def get_category_stats():
    if st.session_state.db_mode == 'supabase':
        data = _get_all_data()
        
        categories = set()
        for row in data:
            if row.get('category'):
                categories.add(row['category'])
        
        stats = []
        for cat in sorted(categories):
            entry = {"category": cat}
            
            fil_data = [r for r in data if r.get('category') == cat and r.get('language') == 'fil']
            eng_data = [r for r in data if r.get('category') == cat and r.get('language') == 'en']
            
            entry["fil_total"] = len(fil_data)
            entry["fil_used"] = len([r for r in fil_data if r.get('used') == 1])
            entry["fil_remaining"] = entry["fil_total"] - entry["fil_used"]
            
            entry["eng_total"] = len(eng_data)
            entry["eng_used"] = len([r for r in eng_data if r.get('used') == 1])
            entry["eng_remaining"] = entry["eng_total"] - entry["eng_used"]
            
            stats.append(entry)
        
        return stats
    
    else:  # SQLite
        conn = connect_sqlite()
        if conn is None:
            return []
        cursor = conn.cursor()
        
        cursor.execute(f"SELECT DISTINCT category FROM {TABLE_NAME} WHERE category IS NOT NULL")
        categories = set()
        for row in cursor.fetchall():
            categories.add(row[0])
        
        stats = []
        for cat in sorted(categories):
            entry = {"category": cat}
            
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE category=? AND language='fil'", (cat,))
            entry["fil_total"] = cursor.fetchone()[0]
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE category=? AND language='fil' AND used=1", (cat,))
            entry["fil_used"] = cursor.fetchone()[0]
            entry["fil_remaining"] = entry["fil_total"] - entry["fil_used"]
            
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE category=? AND language='en'", (cat,))
            entry["eng_total"] = cursor.fetchone()[0]
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE category=? AND language='en' AND used=1", (cat,))
            entry["eng_used"] = cursor.fetchone()[0]
            entry["eng_remaining"] = entry["eng_total"] - entry["eng_used"]
            
            stats.append(entry)
        
        conn.close()
        return stats

def check_sentence_exists(sentence, language=None):
    if st.session_state.db_mode == 'supabase':
        client = get_supabase_client()
        
        query = client.table(TABLE_NAME).select("sen_id,category,language").eq("sentence", sentence)
        if language:
            query = query.eq("language", language)
        result = query.execute()
        
        if result.data:
            row = result.data[0]
            return True, row['sen_id'], row['category'], row['language']
        
        return False, None, None, None
    
    else:  # SQLite
        conn = connect_sqlite()
        if conn is None:
            return False, None, None, None
        cursor = conn.cursor()
        
        if language:
            cursor.execute(f"SELECT sen_id, category, language FROM {TABLE_NAME} WHERE sentence=? AND language=?", (sentence, language))
        else:
            cursor.execute(f"SELECT sen_id, category, language FROM {TABLE_NAME} WHERE sentence=?", (sentence,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return True, result[0], result[1], result[2]
        return False, None, None, None

def insert_sentence(sentence, category, language):
    char_count = len(sentence)
    word_count = len(sentence.split())
    sentence_count = max(1, sentence.count('.') + sentence.count('?'))
    
    sen_id = generate_sen_id(language)
    
    data = {
        "sen_id": sen_id,
        "sentence": sentence,
        "category": category,
        "language": language,
        "used": 0,
        "char_count": char_count,
        "word_count": word_count,
        "sentence_count": sentence_count
    }
    
    if st.session_state.db_mode == 'supabase':
        client = get_supabase_client()
        try:
            result = client.table(TABLE_NAME).insert(data).execute()
            _clear_cache()
            return True, f"Added as {sen_id}"
        except Exception as e:
            return False, f"Insert failed: {str(e)}"
    
    else:  # SQLite
        try:
            conn = connect_sqlite()
            cursor = conn.cursor()
            cursor.execute(f"""
                INSERT INTO {TABLE_NAME}
                (sen_id, sentence, category, language, used, char_count, word_count, sentence_count)
                VALUES (?, ?, ?, ?, 0, ?, ?, ?)
            """, (sen_id, sentence, category, language, char_count, word_count, sentence_count))
            conn.commit()
            conn.close()
            return True, f"Added as {sen_id}"
        except Exception as e:
            return False, f"Insert failed: {str(e)}"

def get_all_sentences(language=None):
    if st.session_state.db_mode == 'supabase':
        client = get_supabase_client()
        
        query = client.table(TABLE_NAME).select("sen_id,sentence,category").eq("used", 0)
        if language:
            query = query.eq("language", language)
        result = query.execute()
        
        sentences = []
        for row in result.data:
            sentences.append((row['sen_id'], row['sentence'], row['category']))
        return sentences
    
    else:  # SQLite
        conn = connect_sqlite()
        if conn is None:
            return []
        cursor = conn.cursor()
        
        if language:
            cursor.execute(f"SELECT sen_id, sentence, category FROM {TABLE_NAME} WHERE language=? AND (used=0 OR used IS NULL)", (language,))
        else:
            cursor.execute(f"SELECT sen_id, sentence, category FROM {TABLE_NAME} WHERE (used=0 OR used IS NULL)")
        
        rows = cursor.fetchall()
        conn.close()
        return rows

def search_sentences(keyword, language=None):
    if st.session_state.db_mode == 'supabase':
        client = get_supabase_client()
        search_pattern = f"%{keyword}%"
        
        query = client.table(TABLE_NAME).select("sen_id,sentence,category").ilike("sentence", search_pattern).eq("used", 0)
        if language:
            query = query.eq("language", language)
        result = query.execute()
        
        sentences = []
        for row in result.data:
            sentences.append((row['sen_id'], row['sentence'], row['category']))
        return sentences
    
    else:  # SQLite
        conn = connect_sqlite()
        if conn is None:
            return []
        cursor = conn.cursor()
        
        if language:
            cursor.execute(f"""
                SELECT sen_id, sentence, category FROM {TABLE_NAME}
                WHERE sentence LIKE ? AND language=? AND (used=0 OR used IS NULL)
            """, (f"%{keyword}%", language))
        else:
            cursor.execute(f"""
                SELECT sen_id, sentence, category FROM {TABLE_NAME}
                WHERE sentence LIKE ? AND (used=0 OR used IS NULL)
            """, (f"%{keyword}%",))
        
        rows = cursor.fetchall()
        conn.close()
        return rows

def get_filtered_sentences(category, language, word_count):
    if st.session_state.db_mode == 'supabase':
        client = get_supabase_client()
        
        query = client.table(TABLE_NAME).select("sentence,category,language,word_count").eq("used", 0).eq("language", language)
        if category:
            query = query.eq("category", category)
        result = query.execute()
        
        sentences = []
        for row in result.data:
            if word_count is None or row.get('word_count') == word_count:
                sentences.append((row['sentence'], row['category'], row['language'], row.get('word_count', 0)))
        return sentences
    
    else:  # SQLite
        conn = connect_sqlite()
        if conn is None:
            return []
        cursor = conn.cursor()
        
        query = f"SELECT sentence, category, language, word_count FROM {TABLE_NAME} WHERE language=? AND (used=0 OR used IS NULL)"
        params = [language]
        
        if category:
            query += " AND category=?"
            params.append(category)
        if word_count:
            query += " AND word_count=?"
            params.append(word_count)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return rows

def update_sentence(sen_id, text, language):
    if st.session_state.db_mode == 'supabase':
        client = get_supabase_client()
        client.table(TABLE_NAME).update({"sentence": text}).eq("sen_id", sen_id).execute()
    else:  # SQLite
        conn = connect_sqlite()
        cursor = conn.cursor()
        cursor.execute(f"UPDATE {TABLE_NAME} SET sentence=? WHERE sen_id=?", (text, sen_id))
        conn.commit()
        conn.close()

def mark_sentences_as_used(sentences):
    if st.session_state.db_mode == 'supabase':
        client = get_supabase_client()
        marked_count = 0
        for sentence in sentences:
            client.table(TABLE_NAME).update({"used": 1}).eq("sentence", sentence[0]).eq("category", sentence[1]).eq("language", sentence[2]).execute()
            marked_count += 1
        return marked_count
    else:  # SQLite
        conn = connect_sqlite()
        cursor = conn.cursor()
        marked_count = 0
        for sentence in sentences:
            cursor.execute(f"""
                UPDATE {TABLE_NAME} SET used=1
                WHERE sentence=? AND category=? AND language=?
            """, (sentence[0], sentence[1], sentence[2]))
            marked_count += 1
        conn.commit()
        conn.close()
        return marked_count

def find_duplicate_sentences():
    if st.session_state.db_mode == 'supabase':
        data = _get_all_data()
        
        sentence_groups = {}
        for row in data:
            sent = row['sentence']
            if sent not in sentence_groups:
                sentence_groups[sent] = []
            sentence_groups[sent].append(row)
        
        duplicates = []
        for sentence, rows in sentence_groups.items():
            if len(rows) > 1:
                duplicates.append({
                    'sentence': sentence,
                    'count': len(rows),
                    'ids': [r['sen_id'] for r in rows],
                    'language': rows[0]['language'],
                    'categories': [r['category'] for r in rows]
                })
        return duplicates
    
    else:  # SQLite
        conn = connect_sqlite()
        if conn is None:
            return []
        cursor = conn.cursor()
        duplicates = []
        
        cursor.execute(f"""
            SELECT sentence, COUNT(*) as count, GROUP_CONCAT(sen_id) as ids, GROUP_CONCAT(category) as categories
            FROM {TABLE_NAME}
            GROUP BY sentence
            HAVING COUNT(*) > 1
        """)
        
        for row in cursor.fetchall():
            sentence, count, ids, categories = row
            cursor2 = conn.cursor()
            cursor2.execute(f"SELECT language FROM {TABLE_NAME} WHERE sentence=? LIMIT 1", (sentence,))
            lang_result = cursor2.fetchone()
            language = lang_result[0] if lang_result else 'fil'
            
            duplicates.append({
                'sentence': sentence,
                'count': count,
                'ids': ids.split(','),
                'language': language,
                'categories': categories.split(',')
            })
        
        conn.close()
        return duplicates

def delete_duplicate_sentences(duplicate_ids, language):
    if st.session_state.db_mode == 'supabase':
        client = get_supabase_client()
        deleted_count = 0
        for sen_id in duplicate_ids:
            client.table(TABLE_NAME).delete().eq("sen_id", sen_id).execute()
            deleted_count += 1
        return deleted_count
    else:  # SQLite
        conn = connect_sqlite()
        cursor = conn.cursor()
        deleted_count = 0
        for sen_id in duplicate_ids:
            cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE sen_id=?", (sen_id,))
            deleted_count += 1
        conn.commit()
        conn.close()
        return deleted_count

def get_database_info():
    total, eng, fil = get_stats()
    fil_remaining, eng_remaining = get_remaining_stats()
    categories = get_categories()
    
    if st.session_state.db_mode == 'supabase':
        data = _get_all_data()
        sentences = [r['sentence'] for r in data]
        dup_counts = {}
        duplicates = 0
        for s in sentences:
            dup_counts[s] = dup_counts.get(s, 0) + 1
        for s, c in dup_counts.items():
            if c > 1:
                duplicates += c - 1
    else:  # SQLite
        conn = connect_sqlite()
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT SUM(cnt) FROM (
                SELECT COUNT(*) - 1 as cnt FROM {TABLE_NAME} GROUP BY sentence HAVING COUNT(*) > 1
            )
        """)
        result = cursor.fetchone()[0]
        duplicates = result if result else 0
        conn.close()
    
    return {
        'fil_total': fil,
        'fil_used': fil - fil_remaining,
        'fil_available': fil_remaining,
        'eng_total': eng,
        'eng_used': eng - eng_remaining,
        'eng_available': eng_remaining,
        'categories': len(categories),
        'duplicates': duplicates
    }

# ---------- IMPORT/EXPORT FUNCTIONS ----------

def import_from_csv_to_db(csv_content, skip_duplicates=True):
    try:
        lines = csv_content.strip().split('\n')
        reader = csv.reader(lines)
        header = next(reader, None)
        
        if not header:
            return 0, 0, "Empty CSV file"
        
        imported = 0
        skipped = 0
        
        for row in reader:
            if not row or not row[0].strip():
                continue
            
            sentence = row[0].strip() if len(row) > 0 else ""
            category = row[1].strip() if len(row) > 1 else "imported"
            language = row[2].strip().lower() if len(row) > 2 else "fil"
            
            if language in ["en", "eng", "english"]:
                language = "en"
            elif language in ["fil", "filipino", "tagalog"]:
                language = "fil"
            else:
                language = "fil"
            
            if not sentence:
                continue
            
            if skip_duplicates:
                exists, _, _, _ = check_sentence_exists(sentence, language)
                if exists:
                    skipped += 1
                    continue
            
            insert_sentence(sentence, category, language)
            imported += 1
        
        return imported, skipped, None
    except Exception as e:
        return 0, 0, str(e)

def export_to_csv_string():
    csv_buffer = StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(["sentence", "category", "language", "word_count", "used"])
    
    if st.session_state.db_mode == 'supabase':
        client = get_supabase_client()
        result = client.table(TABLE_NAME).select("*").execute()
        for row in result.data:
            writer.writerow([
                row['sentence'],
                row['category'],
                row['language'],
                row.get('word_count', 0),
                row.get('used', 0)
            ])
    else:
        conn = connect_sqlite()
        cursor = conn.cursor()
        cursor.execute(f"SELECT sentence, category, language, word_count, used FROM {TABLE_NAME}")
        for row in cursor.fetchall():
            writer.writerow(row)
        conn.close()
    
    return csv_buffer.getvalue()

def import_from_sqlite_file(uploaded_file):
    try:
        temp_path = f"temp_import_{datetime.now().strftime('%Y%m%d%H%M%S')}.db"
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        conn = sqlite3.connect(temp_path)
        cursor = conn.cursor()
        
        imported = 0
        skipped = 0
        
        # Try importing from both old-style separate tables and new single table
        tables_to_try = [TABLE_NAME, "fil_sentences", "eng_sentences"]
        for table in tables_to_try:
            try:
                cursor.execute(f"SELECT sentence, category, language FROM {table}")
                for row in cursor.fetchall():
                    sentence, category, language = row
                    
                    exists, _, _, _ = check_sentence_exists(sentence, language)
                    if exists:
                        skipped += 1
                        continue
                    
                    insert_sentence(sentence, category or "imported", language or "fil")
                    imported += 1
            except:
                pass
        
        conn.close()
        os.remove(temp_path)
        
        return imported, skipped, None
    except Exception as e:
        return 0, 0, str(e)

# ---------- AUTHENTICATION UI ----------

def show_login_page():
    _left, login_col, _right = st.columns([2, 1.2, 2])
    with login_col:
        st.markdown("<h2 style='text-align: center;'>🔐 SentenceDB</h2>", unsafe_allow_html=True)
        
        if ADMIN_PASSWORD == "admin123":
            st.warning("⚠️ **Default admin password is active!** Please change ADMIN_PASSWORD in the code for security.")
        
        login_username = st.text_input("Username", key="login_username")
        login_password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("🔓 Login", type="primary", use_container_width=True, key="btn_login"):
            if login_username and login_password:
                success, message = login_user(login_username, login_password)
                if success:
                    st.session_state.authenticated = True
                    st.session_state.current_user = login_username
                    st.session_state.is_admin = is_admin(login_username)
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.error("Please enter both username and password")
        
        st.markdown("---")
        st.markdown("<p style='text-align: center; color: #64748b; font-size: 0.85rem;'>New user accounts can only be created by an admin.</p>", unsafe_allow_html=True)

def show_database_selector():
    st.markdown("<h3 style='text-align: center;'>📚 Get Started</h3>", unsafe_allow_html=True)
    
    db_choice = st.radio("Choose database type", ["☁️ Cloud (Supabase)", "💻 Local (SQLite)"], horizontal=True, label_visibility="collapsed")
    
    if "Cloud" in db_choice:
        if st.button("🚀 Connect", type="primary", use_container_width=True, key="btn_cloud"):
            if init_supabase():
                st.session_state.db_mode = 'supabase'
                st.rerun()
    else:
        new_db_name = st.text_input("Database name", value="sentences.db", label_visibility="collapsed")
        if st.button("📂 Open", type="primary", use_container_width=True, key="btn_local"):
            init_sqlite(os.path.join(os.getcwd(), new_db_name))
            st.rerun()
    
    with st.expander("📥 Import data"):
        import_tab1, import_tab2 = st.tabs(["SQLite (.db)", "CSV (.csv)"])
        
        with import_tab1:
            uploaded_db = st.file_uploader("Upload .db file", type=["db"], key="combine_uploader", label_visibility="collapsed")
            if uploaded_db is not None:
                if st.button("Import & Merge", type="primary", key="btn_combine"):
                    if init_supabase():
                        with st.spinner("Importing..."):
                            imported, skipped, error = import_from_sqlite_file(uploaded_db)
                        if error:
                            st.error(f"Error: {error}")
                        else:
                            st.success(f"✅ Imported: {imported} | Skipped: {skipped}")
                            st.session_state.db_mode = 'supabase'
                            st.rerun()
        
        with import_tab2:
            uploaded_csv = st.file_uploader("Upload .csv file", type=["csv"], key="csv_uploader", label_visibility="collapsed")
            if uploaded_csv is not None:
                if st.button("Import CSV", type="primary", key="btn_csv"):
                    if init_supabase():
                        with st.spinner("Importing..."):
                            csv_content = uploaded_csv.read().decode('utf-8')
                            imported, skipped, error = import_from_csv_to_db(csv_content, skip_duplicates=True)
                        if error:
                            st.error(f"Error: {error}")
                        else:
                            st.success(f"✅ Imported: {imported} | Skipped: {skipped}")
                            st.session_state.db_mode = 'supabase'
                            st.rerun()
            
            with st.expander("📋 CSV Format"):
                st.code("sentence,category,language\nYour sentence here.,Basic,fil", language="csv")

def show_home():
    st.markdown("<h3 style='text-align: center; margin-bottom: 5px;'>📚 Sentence Database</h3>", unsafe_allow_html=True)
    
    total, eng, fil = get_stats()
    fil_remaining, eng_remaining = get_remaining_stats()
    available = fil_remaining + eng_remaining
    
    if total > 0:
        st.markdown(f"<p style='text-align: center; color: #64748b;'>{total} sentences · {available} available</p>", unsafe_allow_html=True)
    
    # Square menu buttons with big icons
    st.markdown("""
    <style>
    .square-menu-btn > div.stButton > button {
        width: 120px !important;
        height: 120px !important;
        font-size: 1.1rem;
        border-radius: 16px;
        border: 2px solid #cbd5e1;
        white-space: pre-line;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        margin: 0 auto;
    }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown('<div class="square-menu-btn">', unsafe_allow_html=True)
        if st.button("➕\nAdd", key="btn_add"):
            st.session_state.page = "add"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="square-menu-btn">', unsafe_allow_html=True)
        if st.button("🛒\nShop", key="btn_shop"):
            st.session_state.page = "shop"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="square-menu-btn">', unsafe_allow_html=True)
        if st.button("✏️\nEdit", key="btn_edit"):
            st.session_state.page = "edit"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with col4:
        st.markdown('<div class="square-menu-btn">', unsafe_allow_html=True)
        if st.button("📥\nImport", key="btn_import"):
            st.session_state.page = "import"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    if total > 0:
        with st.expander("📊 Statistics"):
            st.markdown(f"🇵🇭 **{fil}** Filipino ({fil_remaining} available) · 🇬🇧 **{eng}** English ({eng_remaining} available)")
            stats = get_category_stats()
            if stats:
                used_fil = sum(e["fil_used"] for e in stats)
                used_eng = sum(e["eng_used"] for e in stats)
                st.markdown(f"Used: 🇵🇭 {used_fil} · 🇬🇧 {used_eng} · 📁 {len(stats)} categories")
                df_data = []
                for entry in stats:
                    total_cat = entry["fil_total"] + entry["eng_total"]
                    used_cat = entry["fil_used"] + entry["eng_used"]
                    pct = (used_cat * 100 // total_cat) if total_cat > 0 else 0
                    df_data.append({
                        "Category": entry["category"],
                        "FIL": f"{entry['fil_used']}/{entry['fil_total']}",
                        "ENG": f"{entry['eng_used']}/{entry['eng_total']}",
                        "Progress": f"{pct}%"
                    })
                df = pd.DataFrame(df_data)
                st.dataframe(df, use_container_width=True, hide_index=True)

def show_add():
    st.title("➕ Add New Sentence")
    
    if st.button("← Back to Home"):
        st.session_state.page = "home"
        st.rerun()
    
    st.markdown("Enter a new sentence to the database")
    
    sentence = st.text_area("Sentence *", height=100, placeholder="Enter your sentence here...", key="add_sentence_text")
    
    try:
        categories = get_categories()
    except Exception:
        categories = []
    
    if not categories:
        categories = ["General"]
    
    category = st.selectbox("Category", options=categories + ["Add New..."])
    
    new_category = ""
    if category == "Add New...":
        new_category = st.text_input("Enter New Category")
    
    language = st.radio("Language", options=["fil", "en"], format_func=lambda x: "Filipino" if x == "fil" else "English", horizontal=True)
    
    if st.button("Add Sentence", type="primary"):
        final_category = new_category if category == "Add New..." and new_category else category
        if not sentence.strip():
            st.error("Sentence cannot be empty!")
        elif category == "Add New..." and not new_category.strip():
            st.error("Please enter a new category name!")
        else:
            try:
                exists, existing_id, existing_cat, existing_lang = check_sentence_exists(sentence.strip())
                if exists:
                    st.error(f"❌ Cannot add: This sentence already exists! (ID: {existing_id})")
                else:
                    success, message = insert_sentence(sentence.strip(), final_category, language)
                    if success:
                        st.success(f"✅ {message}")
                        st.session_state.add_sentence_text = ""
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

def show_edit():
    st.title("✏️ Edit Sentences")
    
    if st.button("← Back to Home"):
        st.session_state.page = "home"
        st.rerun()
    
    search_keyword = st.text_input("🔍 Search", placeholder="Enter keyword to search...")
    
    if search_keyword:
        sentences = search_sentences(search_keyword)
    else:
        sentences = get_all_sentences()
    
    st.markdown(f"**Found: {len(sentences)} sentences**")
    
    if sentences:
        df = pd.DataFrame(sentences, columns=["ID", "Sentence", "Category"])
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        st.markdown("### Edit Selected Sentence")
        selected_id = st.selectbox("Select Sentence ID to Edit", options=[s[0] for s in sentences])
        
        if selected_id:
            selected_sentence = None
            selected_language = None
            
            for s in sentences:
                if s[0] == selected_id:
                    selected_sentence = s[1]
                    break
            
            if st.session_state.db_mode == 'supabase':
                client = get_supabase_client()
                result = client.table(TABLE_NAME).select("language").eq("sen_id", selected_id).execute()
                if result.data:
                    selected_language = result.data[0]['language']
            else:  # SQLite
                conn = connect_sqlite()
                cursor = conn.cursor()
                cursor.execute(f"SELECT language FROM {TABLE_NAME} WHERE sen_id=?", (selected_id,))
                result = cursor.fetchone()
                if result:
                    selected_language = result[0]
                conn.close()
            
            edited_sentence = st.text_area("Edit Sentence", value=selected_sentence, height=100)
            
            if st.button("Save Changes", type="primary"):
                update_sentence(selected_id, edited_sentence.strip(), selected_language)
                st.success("Sentence updated successfully!")
                st.rerun()
    else:
        st.info("No sentences found.")

def show_shop():
    st.title("🛒 Shop for Data")
    
    if st.button("← Back to Home"):
        st.session_state.page = "home"
        st.rerun()
    
    fil_remaining, eng_remaining = get_remaining_stats()
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("📚 Remaining Filipino", fil_remaining)
    with col2:
        st.metric("📚 Remaining English", eng_remaining)
    
    st.divider()
    st.markdown("### Filter Options")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        categories = get_categories()
        category = st.selectbox("Category", options=["All"] + categories)
        category_filter = None if category == "All" else category
    with col2:
        language = st.radio("Language", options=["fil", "en"], format_func=lambda x: "Filipino" if x == "fil" else "English", horizontal=True)
    with col3:
        quantity = st.number_input("Quantity", min_value=1, max_value=1000, value=10)
    
    if st.button("🛒 Add to Cart", type="primary"):
        sentences = get_filtered_sentences(category_filter, language, None)
        cart_sentences = set((item[0], item[1], item[2]) for item in st.session_state.cart)
        available = [s for s in sentences if (s[0], s[1], s[2]) not in cart_sentences]
        if available:
            selected = random.sample(available, min(quantity, len(available)))
            st.session_state.cart.extend(selected)
            st.success(f"Added {len(selected)} sentences to cart!")
        else:
            st.warning("No new sentences available")
    
    st.divider()
    st.markdown(f"### 🛒 Cart ({len(st.session_state.cart)} items)")
    
    if st.session_state.cart:
        # Select/deselect all
        col_sel1, col_sel2 = st.columns([1, 5])
        with col_sel1:
            select_all = st.checkbox("Select All", key="cart_select_all")
        
        # Show cart items with checkboxes
        selected_indices = []
        for i, item in enumerate(st.session_state.cart):
            checked = select_all or st.checkbox(
                f"**{item[0][:60]}{'...' if len(item[0]) > 60 else ''}** — {item[1]} ({item[2]})",
                key=f"cart_item_{i}",
                value=select_all
            )
            if checked:
                selected_indices.append(i)
        
        st.markdown(f"**{len(selected_indices)} selected** out of {len(st.session_state.cart)} items")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🗑️ Remove Selected", disabled=len(selected_indices) == 0):
                st.session_state.cart = [item for i, item in enumerate(st.session_state.cart) if i not in selected_indices]
                st.rerun()
        with col2:
            if st.button("🗑️ Clear All"):
                st.session_state.cart = []
                st.rerun()
        with col3:
            if st.button("✅ Checkout & Export", type="primary"):
                csv_buffer = StringIO()
                writer = csv.writer(csv_buffer)
                writer.writerow(["sentence", "category", "language", "word_count"])
                writer.writerows(st.session_state.cart)
                marked = mark_sentences_as_used(st.session_state.cart)
                st.session_state.cart = []
                st.download_button(label="📥 Download CSV", data=csv_buffer.getvalue(), file_name="exported_sentences.csv", mime="text/csv")
                st.success(f"Checkout complete! {marked} sentences marked as used.")
    else:
        st.info("Your cart is empty.")

def show_import():
    st.title("📥 Import Data")
    
    if st.button("← Back to Home"):
        st.session_state.page = "home"
        st.rerun()
    
    total, eng, fil = get_stats()
    st.markdown(f"**Current Database:** Total: {total} | English: {eng} | Filipino: {fil}")
    
    st.divider()
    st.markdown("### 📂 Import from SQLite")
    uploaded_db = st.file_uploader("Upload .db file", type=["db"], key="import_db")
    if uploaded_db is not None:
        if st.button("📥 Import SQLite", type="primary"):
            with st.spinner("Importing..."):
                imported, skipped, error = import_from_sqlite_file(uploaded_db)
            if error:
                st.error(f"Error: {error}")
            else:
                st.success(f"✅ Imported: {imported} | Skipped: {skipped}")
                st.rerun()
    
    st.divider()
    st.markdown("### 📄 Import from CSV")
    uploaded_csv = st.file_uploader("Upload .csv file", type=["csv"], key="import_csv")
    if uploaded_csv is not None:
        if st.button("📥 Import CSV", type="primary"):
            csv_content = uploaded_csv.read().decode('utf-8')
            imported, skipped, error = import_from_csv_to_db(csv_content, skip_duplicates=True)
            if error:
                st.error(f"Error: {error}")
            else:
                st.success(f"✅ Imported: {imported} | Skipped: {skipped}")
                st.rerun()
    
    st.divider()
    st.markdown("### 📤 Export Database")
    if st.button("📥 Export to CSV"):
        csv_data = export_to_csv_string()
        st.download_button(label="📥 Download CSV", data=csv_data, file_name="database_export.csv", mime="text/csv")

def show_manage():
    st.title("⚙️ Database Management")
    
    if st.button("← Back to Home"):
        st.session_state.page = "home"
        st.rerun()
    
    st.markdown("### 📊 Database Information")
    info = get_database_info()
    if info:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🟣 Filipino Total", info['fil_total'])
        with col2:
            st.metric("🟣 Filipino Available", info['fil_available'])
        with col3:
            st.metric("🟢 English Total", info['eng_total'])
        with col4:
            st.metric("🟢 English Available", info['eng_available'])
        col1, col2 = st.columns(2)
        with col1:
            st.metric("📁 Categories", info['categories'])
        with col2:
            st.metric("⚠️ Duplicates", info['duplicates'])
    
    st.divider()
    st.markdown("### 🔍 Find & Delete Duplicates")
    
    if st.button("🔍 Scan for Duplicates", type="primary"):
        st.session_state.duplicates_found = find_duplicate_sentences()
    
    if 'duplicates_found' in st.session_state:
        duplicates = st.session_state.duplicates_found
        if duplicates:
            st.warning(f"⚠️ Found **{len(duplicates)}** sentences with duplicates!")
            for i, dup in enumerate(duplicates):
                with st.expander(f"📝 {dup['sentence'][:50]}...", expanded=False):
                    st.markdown(f"**Sentence:** {dup['sentence']}")
                    st.markdown(f"**Language:** {'Filipino' if dup['language'] == 'fil' else 'English'}")
                    st.markdown(f"**Occurrences:** {dup['count']}")
                    ids_to_delete = dup['ids'][1:]
                    if st.button(f"🗑️ Delete {len(ids_to_delete)} Duplicates", key=f"del_{i}"):
                        deleted = delete_duplicate_sentences(ids_to_delete, dup['language'])
                        st.success(f"✅ Deleted {deleted} duplicate(s)!")
                        if 'duplicates_found' in st.session_state:
                            del st.session_state.duplicates_found
                        st.rerun()
            if st.button("🗑️ Delete ALL Duplicates", type="primary"):
                total_deleted = 0
                for dup in duplicates:
                    ids_to_delete = dup['ids'][1:]
                    deleted = delete_duplicate_sentences(ids_to_delete, dup['language'])
                    total_deleted += deleted
                st.success(f"✅ Deleted **{total_deleted}** duplicate sentences!")
                if 'duplicates_found' in st.session_state:
                    del st.session_state.duplicates_found
                st.rerun()
        else:
            st.success("✅ No duplicates found!")

# ---------- MAIN APP ----------

def main():
    if 'page' not in st.session_state:
        st.session_state.page = 'home'
    
    if not is_authenticated():
        show_login_page()
        return
    
    with st.sidebar:
        user = get_current_user()
        admin_badge = " 👑" if st.session_state.is_admin else ""
        st.markdown(f"👤 **{user}**{admin_badge}")
        
        if st.session_state.db_mode is not None:
            # Show connection status
            if st.session_state.db_mode == 'supabase':
                st.markdown("🟢 **Connected to Cloud DB**", help="Real-time sync with Supabase")
            else:
                st.markdown("💻 **Connected to Local DB**", help="SQLite local database")
            
            nav_options = ["🏠 Home", "➕ Add", "✏️ Edit", "🛒 Shop", "📥 Import", "⚙️ Manage DB"]
            nav_map = {"🏠 Home": "home", "➕ Add": "add", "✏️ Edit": "edit", "🛒 Shop": "shop", "📥 Import": "import", "⚙️ Manage DB": "manage"}
            page_to_nav = {v: k for k, v in nav_map.items()}
            current_nav = page_to_nav.get(st.session_state.page, "🏠 Home")
            default_index = nav_options.index(current_nav) if current_nav in nav_options else 0
            
            def on_nav_change():
                nav = st.session_state.nav_select
                if nav and nav_map.get(nav):
                    st.session_state.page = nav_map[nav]
            
            st.selectbox("Navigate", nav_options, index=default_index, key="nav_select", on_change=on_nav_change, label_visibility="collapsed")
            if st.session_state.is_admin:
                if st.button("👥 Manage Users", use_container_width=True):
                    st.session_state.page = "admin_users"
                    st.rerun()
            st.divider()
            if st.button("🔄 Switch Database", use_container_width=True):
                st.session_state.db_mode = None
                st.session_state.cart = []
                st.session_state.page = "home"
                st.rerun()
            if st.button("🚪 Logout", use_container_width=True):
                logout_user()
                st.rerun()
        else:
            st.info("Select a database to start.")
            if st.session_state.is_admin:
                if st.button("👥 Manage Users", use_container_width=True):
                    st.session_state.page = "admin_users"
                    st.rerun()
            st.divider()
            if st.button("🚪 Logout", use_container_width=True):
                logout_user()
                st.rerun()
    
    if st.session_state.page == "admin_users":
        show_admin_users()
    elif st.session_state.db_mode is None:
        show_database_selector()
    else:
        if st.session_state.page == "home":
            show_home()
        elif st.session_state.page == "add":
            show_add()
        elif st.session_state.page == "edit":
            show_edit()
        elif st.session_state.page == "shop":
            show_shop()
        elif st.session_state.page == "import":
            show_import()
        elif st.session_state.page == "manage":
            show_manage()

def show_admin_users():
    st.title("🔐 User Management")
    
    if st.button("← Back to Home"):
        st.session_state.page = "home"
        st.rerun()
    
    if not st.session_state.is_admin:
        st.error("🚫 Access denied. Admin privileges required.")
        return
    
    st.markdown("Manage registered users and accounts")
    st.divider()
    st.markdown("### 📋 Registered Users")
    
    users = get_all_users()
    if users:
        df = pd.DataFrame(users)
        df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d")
        df = df[["username", "email", "created_at"]]
        df.columns = ["Username", "Email", "Registered"]
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Delete User")
            delete_username = st.selectbox("Select user to delete", options=[u["username"] for u in users], key="delete_user")
            if st.button("🗑️ Delete User", type="primary", key="btn_delete_user"):
                if delete_username.lower() == ADMIN_USERNAME.lower():
                    st.error("Cannot delete the main admin account!")
                else:
                    success, message = delete_user(delete_username)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
        with col2:
            st.markdown("### Reset Password")
            reset_username = st.selectbox("Select user", options=[u["username"] for u in users], key="reset_pwd")
            new_password = st.text_input("New password", type="password", key="new_pwd")
            if st.button("🔄 Reset Password", type="primary", key="btn_reset_pwd"):
                if reset_username.lower() == ADMIN_USERNAME.lower():
                    st.error("Cannot reset admin password!")
                elif not new_password or len(new_password) < 4:
                    st.error("Password must be at least 4 characters")
                else:
                    success, message = reset_user_password(reset_username, new_password)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
    else:
        st.info("No registered users yet.")
    
    st.divider()
    st.markdown("### ➕ Add New User")
    with st.form("add_user_form"):
        new_username = st.text_input("Username")
        new_email = st.text_input("Email (optional)")
        new_pwd = st.text_input("Password", type="password")
        new_pwd_confirm = st.text_input("Confirm Password", type="password")
        new_is_admin = st.checkbox("Make admin")
        submitted = st.form_submit_button("Add User")
        if submitted:
            if not new_username or not new_pwd:
                st.error("Username and password are required")
            elif new_pwd != new_pwd_confirm:
                st.error("Passwords do not match")
            elif len(new_pwd) < 4:
                st.error("Password must be at least 4 characters")
            else:
                success, message = add_user(new_username, new_pwd, new_email, new_is_admin)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
    
    st.divider()
    st.warning("⚠️ **Security Notice:** The hardcoded admin password should be changed in the source code for production use.")

if __name__ == "__main__":
    main()
