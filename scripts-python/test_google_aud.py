import sys
sys.path.insert(0, r'c:\Users\trafe\OneDrive\Desktop\workspace-mmm')
try:
    from frontend.app import get_launches, resolve_launch
    from frontend.database_reader import read_google, _get_engine
    import pandas as pd
    from sqlalchemy import text
    
    code = "PBB-JUN-26"
    engine = _get_engine()
    
    print(f"Buscando com code: '{code}'")
    
    df_aud = pd.read_sql(
        text("SELECT * FROM google_ads_audiences_daily WHERE lancamento_codigo = :code LIMIT 5"),
        engine,
        params={"code": code}
    )
    print("Direct Query length:", len(df_aud))
    if not df_aud.empty:
        print(df_aud.head())
        
    google = read_google(code)
    if google:
        print("Read_google publicos len:", len(google.publicos))
    else:
        print("GoogleSummary is None")
        
except Exception as e:
    import traceback
    traceback.print_exc()
