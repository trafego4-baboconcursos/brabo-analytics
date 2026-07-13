import sys
sys.path.insert(0, r'c:\Users\trafe\OneDrive\Desktop\workspace-mmm')
try:
    from frontend.app import get_launches, resolve_launch, _meta
    
    launches = get_launches()
    launch = resolve_launch("PBB-JUN-26", launches)
    print("Resolved Launch:", launch.code if launch else None)
    
    if launch:
        print("has_meta:", launch.has_meta)
        if launch.has_meta:
            meta = _meta(launch)
            print("Meta Object:", meta is not None)
            if meta:
                print("Por Temperatura:", meta.por_temperatura.keys() if meta.por_temperatura else None)
                print("Por Bucket:", meta.por_bucket.keys() if meta.por_bucket else None)
        else:
            print("No Meta detected for this launch.")
except Exception as e:
    import traceback
    traceback.print_exc()
