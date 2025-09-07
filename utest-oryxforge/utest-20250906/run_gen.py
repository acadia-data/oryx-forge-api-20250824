from oryxforge.services.task_service import TaskService

# Initialize service
svc = TaskService("test1",'utest-oryxforge/utest-20250906')

# UPSERT tasks for card data processing (create or update)
svc.upsert(
    module="test1",
    task="LoadCardData",
    code="""df = pd.read_csv('data/df_card_m.csv')
self.save(df)""",
    dependencies=[]
)

svc.upsert(
    module="test1",
    task="CleanCardData", 
    code="""df = self.input().load()
df = df.dropna()
df['date_month'] = pd.to_datetime(df['date_month'])
self.save(df)""",
    dependencies=["LoadCardData"]
)

svc.upsert(
    module="test1",
    task="AnalyzeCardData",
    code="""df = self.input().load()
summary = df.groupby('merchant').agg({
    'transaction_count': 'sum',
    'transacted_value': 'sum',
    'avg_value': 'mean'
}).reset_index()
self.save(summary)""",
    dependencies=["CleanCardData"]
)

# List all tasks
print("Tasks created:", svc.list_tasks("test1"))

# Show generated code
print("\n" + "="*50)
print("Generated tasks.py:")
print("="*50)
with open("tasks.py", "r") as f:
    print(f.read())
