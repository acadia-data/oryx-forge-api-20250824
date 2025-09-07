import pandas as pd
import d6tflow

class LoadCardData(d6tflow.tasks.PandasPq):

    def run(self):
        df = pd.read_csv('data/df_card_m.csv')
        self.save(df)

@d6tflow.requires(LoadCardData)
class CleanCardData(d6tflow.tasks.PandasPq):

    def run(self):
        df = self.input().load()
        df = df.dropna()
        df['date_month'] = pd.to_datetime(df['date_month'])
        self.save(df)

@d6tflow.requires(CleanCardData)
class AnalyzeCardData(d6tflow.tasks.PandasPq):

    def run(self):
        df = self.input().load()
        summary = df.groupby('merchant').agg({'transaction_count': 'sum', 'transacted_value': 'sum', 'avg_value': 'mean'}).reset_index()
        self.save(summary)