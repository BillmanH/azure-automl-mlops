import argparse
import os

import joblib
import numpy as np
import pandas as pd
import scipy.signal.signaltools
from azureml.core.run import Run, _OfflineRun
from interpret.ext.blackbox import TabularExplainer
from loguru import logger

parser = argparse.ArgumentParser(
    description="getting inputs from the pipeline setup")
parser.add_argument("--data_path", type=str, default=os.path.join(
    'data', 'kaggle_retail_data_analytics', 'processed'))
parser.add_argument("--model_path", type=str, default=os.path.join(
    'models', 'retail_automl_MaxAbsScaler_XGBoostRegressor', 'model.pkl'))
parser.add_argument("--output_path", type=str, default=os.path.join(
    'data', 'kaggle_retail_data_analytics', 'out'))
args, unknown = parser.parse_known_args()

os.makedirs(args.output_path, exist_ok=True)

data_path = args.data_path
model_path = args.model_path
output_path = args.output_path
logger.debug(f'{data_path = }')
logger.debug(f'{model_path = }')
logger.debug(f'{output_path = }')

test_df = pd.read_csv(os.path.join(data_path, 'test_data_sample_100.csv'))
x_test_df = test_df.drop(['Weekly_Sales'], axis=1)
logger.debug(f'{x_test_df.shape = }')
print(test_df.head())


def _centered(arr, newshape):
    # Return the center newshape portion of the array.
    newshape = np.asarray(newshape)
    currshape = np.array(arr.shape)
    startind = (currshape - newshape) // 2
    endind = startind + newshape
    myslice = [slice(startind[k], endind[k]) for k in range(len(endind))]
    return arr[tuple(myslice)]


run = Run.get_context()
if type(run) == _OfflineRun:
    scipy.signal.signaltools._centered = _centered

model = joblib.load(model_path)
logger.debug(f'{type(model) = }')

'''
Docs:
https://github.com/interpretml/interpret-community
https://github.com/interpretml/interpret-community/blob/master/notebooks/explain-regression-local.ipynb
https://docs.microsoft.com/en-us/azure/machine-learning/how-to-machine-learning-interpretability
https://docs.microsoft.com/en-us/azure/machine-learning/how-to-machine-learning-interpretability-aml#generate-feature-importance-values-via-remote-runs
'''

# SHAP
# Note: run SHAP before model.predict()
explainer = TabularExplainer(
    model=model,
    initialization_examples=x_test_df,
    features=x_test_df.columns)
logger.debug(f'SHAP explainer: {explainer.explainer}')

global_explanation = explainer.explain_global(x_test_df)

local_importance_values = global_explanation.local_importance_values
local_importance_valuess_df = pd.DataFrame(
    local_importance_values, columns=x_test_df.columns)
print(local_importance_valuess_df.head())

# Score
y_pred = model.predict(x_test_df)
y_pred_df = pd.DataFrame(y_pred, columns=['Weekly_Sales_Prediction'])
print(y_pred_df)

shap_df = pd.concat([local_importance_valuess_df, y_pred_df], axis=1)
print(shap_df.head())

shap_df_path = os.path.join(output_path, 'shap_values.csv')
shap_df.to_csv(shap_df_path, index=False)
logger.debug(f'SHAP table saved to {shap_df_path}')
