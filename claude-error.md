PS D:\dev\oryx-forge-projects\user-24d811e2-seniorhousinganalysis> oryxforge admin config mount suggest "D:\\data\\oryx-forge-projects"
Suggested mount point: D:/data/oryx-forge-projects/24d811e2-1801-4208-8030-a86abbda59b8/e5bc2451-d6fc-478f-8bc7-cb4e778aa329/data

Do you want to set this as your mount point? [Y/n]: y
Created directory: D:\data\oryx-forge-projects\24d811e2-1801-4208-8030-a86abbda59b8\e5bc2451-d6fc-478f-8bc7-cb4e778aa329
2025-10-31 12:26:38.232 | DEBUG    | oryxforge.services.config_service:set:82 - Config updated: [mount] mount_point = D:/data/oryx-forge-projects/24d811e2-1801-4208-8030-a86abbda59b8/e5bc2451-d6fc-478f-8bc7-cb4e778aa329/data
2025-10-31 12:26:38.232 | SUCCESS  | oryxforge.services.cli_service:mount_point_set:271 - Mount point set to 'D:/data/oryx-forge-projects/24d811e2-1801-4208-8030-a86abbda59b8/e5bc2451-d6fc-478f-8bc7-cb4e778aa329/data'
✅ Mount point set to: D:/data/oryx-forge-projects/24d811e2-1801-4208-8030-a86abbda59b8/e5bc2451-d6fc-478f-8bc7-cb4e778aa329/data

Do you want to mount the data directory now? [Y/n]: y
2025-10-31 12:26:42.712 | DEBUG    | oryxforge.services.project_service:__init__:66 - Using mount point from config: D:\data\oryx-forge-projects\24d811e2-1801-4208-8030-a86abbda59b8\e5bc2451-d6fc-478f-8bc7-cb4e778aa329\data
2025-10-31 12:26:43.823 | DEBUG    | oryxforge.services.project_service:_validate_project:114 - Validated project: senior housing analysis

❌ Mount check failed: project mount point at 'D:\data\oryx-forge-projects\24d811e2-1801-4208-8030-a86abbda59b8\e5bc2451-d6fc-478f-8bc7-cb4e778aa329\data' is not mounted. Please ensure the mount is set up before starting the CLI.
❌ Unexpected error:
Aborted!