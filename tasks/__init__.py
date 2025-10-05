import d6tflow
import pandas as pd
pd.set_option('display.max_columns', None)

class TestUnicode(d6tflow.tasks.TaskPqPandas):

    def run(self):
        data = self.inputLoad()
        df_out = None
        self.save(df_out)

    def eda(self):
        data = self.inputLoad()
        print('✓ Unicode works\\!')