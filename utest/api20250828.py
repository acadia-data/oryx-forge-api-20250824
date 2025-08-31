fileid = 'de73a2b6-3c0e-4c8d-b579-7d42715e9da6'
url = 'https://oryx-forge-dev-20250823-846392806260.us-central1.run.app/files/preview'
url = "http://localhost:8000/files/preview"

def utest_service():
    from supabase import create_client, Client

    import adtiam
    adtiam.load_creds('adt-db')

    cnxn_supabase = create_client(adtiam.creds['db']['supabase']['url'], adtiam.creds['db']['supabase']['key-admin'])
    # fileid='cbc46cd4-1b5e-4168-a7f9-13529c5a10a1'

    from api.services.file_service import FileService
    file_service = FileService(cnxn_supabase)
    preview_data = file_service.preview_file(fileid)
    print(preview_data)


def utest_api():
    import httpx
    import json

    # Simple httpx call to /files/preview endpoint
    settings = {}

    payload = {
        "fileid": fileid,
        # "settings": settings
    }

    response = httpx.post(
        url,
        json=payload,
        timeout=30.0
    )
    if not response.is_success:
        print(response.text)
    else:
        print(response.json())

# utest_service()
utest_api()
