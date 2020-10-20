from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np
from pandas import DataFrame

from powertrain.core.core_utils import test_train_split
from powertrain.estimators.base import LinearRegression
from powertrain.estimators.estimator_interface import EstimatorInterface
from powertrain.estimators.explicit_bin import ExplicitBin
from powertrain.estimators.random_forest import RandomForest
from powertrain.utils.fs import get_version
from powertrain.validation import errors

_registered_estimators = {
    'LinearRegression': LinearRegression,
    'ExplicitBin': ExplicitBin,
    'RandomForest': RandomForest,
}


def _load_estimator(name: str, json: dict) -> EstimatorInterface:
    if name not in _registered_estimators:
        raise TypeError(f"{name} estimator not registered with routee-powertrain")

    e = _registered_estimators[name]

    return e.from_json(json)


class Model:
    """This is the core model for interaction with the routee engine.

    Args:
        veh_desc (str):
            Unique description of the vehicle to be modeled.
        estimator (routee.estimator.base.BaseEstimator):
            Estimator to use for predicting route energy usage.
            
    """

    def __init__(self, estimator: EstimatorInterface, veh_desc: Optional[str] = None):
        self.metadata = {
            'veh_desc': veh_desc,
            'estimator': estimator.__class__.__name__,
        }

        self._estimator = estimator

    def train(
            self,
            data: DataFrame,
    ):
        """
        Train a model

        Args:
            data:

        Returns:

        """
        print(f"training estimator {self._estimator} with option {self._estimator.predict_type}.")

        self.metadata['routee_version'] = get_version()

        pass_data = data.copy(deep=True)
        pass_data = pass_data[~pass_data.isin([np.nan, np.inf, -np.inf]).any(1)]

        # splitting test data between train and validate --> 20% here
        train, test = test_train_split(pass_data.dropna(), 0.2)

        self._estimator.train(pass_data)

        self.validate(test)

    def validate(self, test):
        """Validate the accuracy of the estimator.

        Args:
            test (pandas.DataFrame):
                Holdout test dataframe for validating performance.
                
        """

        _target_pred = self.predict(test)
        test['target_pred'] = _target_pred
        self.metadata['errors'] = errors.all_error(
            test[self._estimator.feature_pack.energy.name],
            _target_pred,
            test[self._estimator.feature_pack.distance.name],
        )

    def predict(self, links_df):
        """Apply the trained energy model to to predict consumption.

        Args:
            links_df (pandas.DataFrame):
                Columns that match self.features and self.distance that describe
                vehicle passes over links in the road network.

        Returns:
            energy_pred (pandas.Series):
                Predicted energy consumption for every row in links_df.
                
        """
        return self._estimator.predict(links_df)

    def to_json(self, outfile: Path):
        """Dumps a routee.Model to a json file for persistance and sharing.

        Args:
            outfile (str):
                Filepath for location of dumped model.

        """
        out_dict = {
            'metadata': self.metadata,
            '_estimator_json': self._estimator.to_json(),
        }
        with open(outfile, 'w', encoding='utf-8') as f:
            json.dump(out_dict, f, ensure_ascii=False, indent=4)

    @classmethod
    def from_json(cls, infile: Path) -> Model:
        with infile.open('r', encoding='utf-8') as f:
            in_json = json.load(f)
            metadata = in_json['metadata']
            estimator = _load_estimator(metadata['estimator'], json=in_json['_estimator_json'])

            m = Model(estimator=estimator)
            m.metadata = metadata

            return m
