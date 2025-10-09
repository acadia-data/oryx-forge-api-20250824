ImportService
init(file_id)
init ProjectService
utils.init_supabase_client
file = get file data from supabase data_sources using file_id
raise Error if no such fileid
import() => returns message
set data_sources status = 
  "flag": "processing",
  "msg": "Import queued"
sets dataset = “Sources”, sheet name = file name
construct file_path from file.uri
if local: in uri, then construct from “local://{filePath}”
if supabase: in uri, then construct from “data/.import”
render the prompt
use oryxforge/prompts/templates.cfg as the basis and adjust to take inputs file_path, dataset and sheet to be rendered in the prompt
call ClaudeAgent query_run with the rendered prompt
projectservice.sheet_create 
use projectservice.ds_get(name=”Sources”) to get the id
set data_sources status = 
 "flag": "ready",
  "msg": "File imported successfully"
filepath(): Pathlib.path
construct file_path from file.uri
if local: in uri, then construct from “local://{filePath}”
if supabase: in uri, then construct from “data/.import”
download() 
download only if “supabase:” in uri
download from supabase
       fpath = self.filepath()
        fpath.parent.mkdir(parents=True, exist_ok=True)
        # Download the file content
        file_response = self.supabase_client.storage.from_(self.bucket_name).download(source_record['uri'])
        # Write the file to disk
        with open(fpath, "wb") as f:
            f.write(file_response)
exists_local(): bool
check if self.filepath().exists()


CLIService
add method import_file(path)
utils.init_supabase_client
create supabase data_sources entry with uri “local://{filePath}”, keep the file_id
user owner and project id you can get from oryxforge.iam.CredentialsManager().get_profile()
name is the actual file name extracted from the path using Pathlib
ImportService(file_id).import()
