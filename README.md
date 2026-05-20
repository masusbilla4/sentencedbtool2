# 📚 SentenceDB App

A web-based tool for managing sentence databases with real-time multi-user support. Built with Streamlit and Supabase.

## Features

- ☁️ **Cloud Database** — Supabase-backed real-time multi-user access
- 💻 **Local Database** — SQLite for offline use
- 🔐 **User Authentication** — Login system with admin controls
- ➕ **Add Sentences** — Manually add sentences with duplicate detection
- 🛒 **Shop for Data** — Browse, filter, and export sentences
- ✏️ **Edit Sentences** — Search and modify existing entries
- 📥 **Import/Export** — Bulk import from CSV/SQLite, export to CSV
- ⚙️ **Database Management** — Find and delete duplicates, view statistics

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Supabase (optional):**
   Edit `SUPABASE_URL` and `SUPABASE_KEY` in `app.py` with your Supabase credentials.

3. **Run the app:**
   ```bash
   streamlit run app.py
   ```

4. **Login:**
   - Default admin: `admin` / `admin123`
   - ⚠️ Change the admin password in the code for production use!

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `SUPABASE_URL` | Supabase project URL | Required for cloud mode |
| `SUPABASE_KEY` | Supabase anon key | Required for cloud mode |
| `ADMIN_USERNAME` | Default admin username | `admin` |
| `ADMIN_PASSWORD` | Default admin password | `admin123` |

## CSV Import Format

```csv
sentence,category,language
Your sentence here.,Basic,fil
Another sentence.,Daily,en
```

| Column | Required | Description |
|--------|----------|-------------|
| sentence | ✅ | The sentence text |
| category | ✅ | Category name |
| language | Optional | `fil` or `en` (defaults to `fil`) |

## Tech Stack

- **Frontend:** Streamlit
- **Cloud DB:** Supabase (PostgreSQL)
- **Local DB:** SQLite
- **Auth:** Custom (SHA-256 hashed passwords)

## License

MIT
