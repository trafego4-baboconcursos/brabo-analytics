import sys
import os

sys.path.insert(0, r'c:\Users\trafe\OneDrive\Desktop\workspace-mmm')
try:
    from frontend.app import get_launches, resolve_launch, _google, _meta
    
    launches = get_launches()
    print("Launches found:", [l.code for l in launches])
    launch = resolve_launch("PBB-JUN-26", launches)
    print("Resolved Launch:", launch.code if launch else None)
    
    if launch:
        print("has_google:", launch.has_google)
        print("has_meta:", launch.has_meta)
        if launch.has_google:
            google = _google(launch)
            print("Google Object:", google)
            print("Campanhas in Google Object:", len(getattr(google, "campanhas", [])))
            print("Públicos in Google Object:", len(getattr(google, "publicos", [])))
            print("Ads in Google Object:", len(getattr(google, "anuncios_por_ad", [])))
        else:
            print("No Google CSV detected for this launch.")
except Exception as e:
    import traceback
    traceback.print_exc()
