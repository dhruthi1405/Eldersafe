import pandas as pd
import os

datasets = [
    ('Fall Detection', 'datasets/processed/fall_binary_train.csv'),
    ('Activity Recognition', 'datasets/processed/activity_train.csv')
]

for name, path in datasets:
    if os.path.exists(path):
        df = pd.read_csv(path)
        print(f'\n=== {name.upper()} ===')
        print(f'Shape: {df.shape}')
        print(f'Memory: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB')
        print(f'Columns: {list(df.columns[-5:])}')
        if 'label' in df.columns:
            print(f'Labels: {dict(df["label"].value_counts())}')
        print(f'Missing values: {df.isnull().sum().sum()}')
    else:
        print(f'\n{name}: FILE NOT FOUND')
