from supabase import create_client, Client

import adtiam
adtiam.load_creds('adt-db')

cnxn_supabase = create_client(adtiam.creds['db']['supabase']['url'], adtiam.creds['db']['supabase']['key-public'])
cnxn_supabase = create_client(adtiam.creds['db']['supabase']['url'], adtiam.creds['db']['supabase']['key-admin'])

user_response = cnxn_supabase.auth.sign_in_with_password({
    "email":"public@oryxintel.com","password":"Iqu5YuHI1ArKsgZ"})
user_owner = user_response.user.id


r = (
    cnxn_supabase.table("projects")
    .insert({"name": 'unemployment analysis 2025-08', "user_owner": user_owner})
    .execute()
)

r2 = (
    cnxn_supabase.table("projects")
    .select("*")
    .eq("name", 'unemployment analysis 2025-08')
    .eq("user_owner", user_owner)
    .execute()
)

r = (
    cnxn_supabase.table("datasets")
    .insert({"name": 'unemployment rate', "user_owner": user_owner, "project_id": r2.data[0]['id']})
    .execute()
)

r2 = (
    cnxn_supabase.table("datasheets")
    .select("*")
    .eq("name", 'data')
    .eq("user_owner", user_owner)
    .execute()
)
assert len(r2.data)==1

import pandas as pd

df_adp = pd.read_excel('data/ADPWNUSNERSA.xlsx',sheet_name='Weekly')
df_adp = pd.read_csv('data/ADPWNUSNERSA.csv')
df_adp.iloc[0,0]

df_adp.head().to_json()

df_adp.head().to_json()


def dataframe_to_spreadsheet_format(df):
    # Handle NaN values
    df_clean = df.fillna('')  # or df.fillna(None) for null values

    return {
        "headers": df_clean.columns.tolist(),
        "data": df_clean.values.tolist()
    }

r = (
    cnxn_supabase.table("datasheets_output")
    .insert({"data": dataframe_to_spreadsheet_format(df_adp), "user_owner": user_owner, "datasheet_id": r2.data[0]['id']})
    .execute()
)

r = (
    cnxn_supabase.table("datasheets_output")
    .upsert({"data": dataframe_to_spreadsheet_format(df_adp.head()), "user_owner": user_owner, "datasheet_id": r2.data[0]['id']})
    .execute()
)

fileid='cbc46cd4-1b5e-4168-a7f9-13529c5a10a1'
r = (
    cnxn_supabase.table("data_sources")
    .select("*")
    .eq("id", fileid)
    .execute()
)
print(len(r.data))
