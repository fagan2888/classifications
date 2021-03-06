import pandas as pd
from pandas.io.json import json_normalize
import requests
import json

from classification import (
    Hierarchy,
    parent_code_table_to_parent_id_table,
    Classification,
)


def get_wdi_data():
    r = requests.get("http://api.worldbank.org/v2/countries/?format=json&per_page=400")

    # Metadata in 0, data in 1
    wdi_locations = json_normalize(json.loads(r.text)[1])
    wdi_locations = wdi_locations[["id", "iso2Code"]].rename(
        columns={"id": "iso3", "iso2Code": "iso2"}
    )
    return wdi_locations


if __name__ == "__main__":

    df = pd.read_csv(
        "./in/International Atlas Location Codes - Clean Countries.csv",
        encoding="utf-8",
        dtype={"parent_code": str},
    ).drop("comtrade_name", axis=1)
    df["level"] = "country"

    regions = pd.read_csv(
        "./in/International Atlas Location Codes - Continents and Regions.csv",
        encoding="utf-8",
    )
    regions["name_short_en"] = regions["name_en"]
    regions["name_short_es"] = regions["name_es"]
    regions["level"] = "region"
    regions["code"] = regions["code"].astype(str)

    df = pd.concat([df, regions]).reset_index(drop=True)

    # Merge in data from WDI API
    wdi_locations = get_wdi_data()
    df = df.merge(wdi_locations, left_on="code", right_on="iso3", how="left").drop(
        columns=["iso3"]
    )

    h = Hierarchy(["region", "country"])
    parent_id_table = parent_code_table_to_parent_id_table(df, h)
    parent_id_table["name"] = parent_id_table["name_en"]

    # Add a "gap" between countries and regions in case we need to add stuff in
    # the future
    parent_id_table["new_index"] = parent_id_table.index
    parent_id_table.loc[parent_id_table.level == "region", "new_index"] += 100
    parent_id_table.loc[parent_id_table.level == "country", "parent_id"] += 100
    parent_id_table = parent_id_table.reset_index(drop=True).set_index("new_index")
    parent_id_table.index.name = None

    # Add in other properties, like in_rankings and trusted
    trusted = pd.read_csv("./in/trusted_countries.csv", index_col="iso")
    parent_id_table = parent_id_table.merge(
        trusted, left_on="code", right_index=True, how="left"
    )
    in_rankings = pd.read_table("./in/in_rankings.csv", index_col="iso", sep=";")
    parent_id_table = parent_id_table.merge(
        in_rankings, left_on="code", right_index=True, how="left"
    )
    services = pd.read_csv("./in/services_flags.csv", index_col="code")
    services = services.astype(float)
    parent_id_table = parent_id_table.merge(
        services, left_on="code", right_index=True, how="left"
    )

    former = pd.read_csv("./in/former_countries.csv", index_col="code")
    former = former.astype(float)
    parent_id_table = parent_id_table.merge(
        former, left_on="code", right_index=True, how="left"
    )

    # Services flags should be False in case of regions, per Huy's request
    parent_id_table.loc[parent_id_table.level == "region", "reported_serv"] = 0
    parent_id_table.loc[parent_id_table.level == "region", "reported_serv_recent"] = 0

    # Remove World as a country since it doesn't have data
    parent_id_table = parent_id_table[parent_id_table.code != "WLD"]

    c = Classification(parent_id_table, h)
    c.to_csv("out/locations_international_atlas.csv")
