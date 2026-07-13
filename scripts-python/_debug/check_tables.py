import sys
sys.path.insert(0, r'c:\Users\trafe\OneDrive\Desktop\workspace-mmm')
from frontend.database_reader import _get_engine
from sqlalchemy import text

try:
    engine = _get_engine()
    with engine.connect() as conn:
        res = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")).fetchall()
        print("Tables in DB:", [r[0] for r in res])
except Exception as e:
    import traceback
    traceback.print_exc()
