import glob
import os
import sqlite3
from multiprocessing import Pool
from pathlib import Path

import pandas as pd

from powertrain.core.features import Feature, FeaturePack
from powertrain.core.model import Model
from powertrain.trainers.explicit_bin import ExplicitBin
from powertrain.trainers.linear_regression import LinearRegression
from powertrain.trainers.random_forest_old import RandomForest

RAW_DATA_PATH = (
    "/projects/mbap/data/fastsim_results/2020_11_9/FASTSim_py_veh_db_w_phevs/*.db"
)

outpath = Path("/projects/mbap/data/routee_results/2020_11_9")
outpath.mkdir(exist_ok=True)


def train_model(file):
    vehicle_name = os.path.splitext(os.path.basename(file))[0]

    print(f"Working on vehicle: {vehicle_name}")

    features = (
        Feature("gpsspeed", units="mph"),
        Feature("grade", units="percent_0_100"),
    )
    distance = Feature("miles", units="mi")

    sql_con = sqlite3.connect(file)

    df = pd.read_sql_query("SELECT * FROM links", sql_con)
    df["grade"] = df.grade.apply(lambda x: x * 100)

    if df.gge.sum() > 0:
        energy = Feature("gge", units="gallons")
    elif df.esskwhoutach.sum() > 0:
        energy = Feature("esskwhoutach", units="kwh")
    else:
        raise RuntimeError("There is no energy in this data file..")

    train_df = df[["miles", "gpsspeed", "grade", energy.name]].dropna()
    feature_pack = FeaturePack(features, distance, energy)

    ln_e = LinearRegression(feature_pack=feature_pack)
    rf_e = RandomForest(feature_pack=feature_pack)
    eb_e = ExplicitBin(feature_pack=feature_pack)

    for e in (ln_e, rf_e, eb_e):
        m = Model(e, description=vehicle_name)
        m.train(train_df)
        m.to_json(outpath / f"{vehicle_name}_{e.__class__.__name__}.json")
        m.to_pickle(outpath / f"{vehicle_name}_{e.__class__.__name__}.pickle")


if __name__ == "__main__":
    num_cores = 6

    raw_files = glob.glob(RAW_DATA_PATH)
    print(f"Total of {len(raw_files)}")

    with Pool(num_cores) as p:
        p.map(train_model, raw_files)
