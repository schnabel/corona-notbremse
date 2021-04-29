from datetime import date

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(layout="wide")
st.title("Bundes-Notbremse Ampel")
pd.set_option('precision', 2)

@st.cache
def load_covid_data():
    cols = ["IdLandkreis", "Meldedatum", "AnzahlFall", "NeuerFall"]
    covid = pd.read_csv('https://npgeo-corona-npgeo-de.hub.arcgis.com/datasets/dd4580c810204019a7b8eb3e0b329dd6_0.csv', usecols=cols, parse_dates=['Meldedatum'])
    covid.Meldedatum = pd.DatetimeIndex(covid.Meldedatum.dt.date)
    return covid

def color_notbremse(val):
    background_color = 'green'
    if val >= 165:
        background_color = 'blue'
    elif val >= 150:
        background_color = 'red'
    elif val >= 100:
        background_color = 'yellow'
    return 'background_color: %s' % background_color

def show_traffic_light(color):
    style = """
        <style>
            .css-ampel {
                display: inline-block;
                width: 30px;
                height: 90px;
                border-radius: 6px;
                position: relative;
                background-color: black;
                zoom: 1.7;
            }
            
            .css-ampel span,
            .css-ampel:before,
            .css-ampel:after {
                content: "";
                color: white;
                position: absolute;
                border-radius: 15px;
                width: 22px;
                height: 22px;
                left: 4px;
            }    
            
            .css-ampel:before {
                top: 6px;
                background-color: red;
                background-color: dimgrey;
            }
            
            .css-ampel:after {
                top: 34px;
                background-color: yellow;
                background-color: dimgrey;
            }
            
            .css-ampel span {
                top: 62px;
                background-color: green;
                background-color: dimgrey;
            }    
            
            .ampelrot:before {
                background-color: red;
                box-shadow: 0 0 20px red;
            }
            
            .ampelblau:before {
                background-color: blue;
                box-shadow: 0 0 20px blue;
            }
            
            .ampelgelb:after {
                background-color: yellow;
                box-shadow: 0 0 20px yellow;
            }
            
            .ampelgruen span {
                background-color: limegreen;
                box-shadow: 0 0 20px limegreen;
            }
        </style>
        """
    value = "< 100"
    if color == "gelb":
        value = "> 100"
    elif color == "rot":
        value = "> 150"
    elif color == "blau":
        value = "> 165"

    components.html(
        style + f"""
        <div>
            <span class="css-ampel ampel{color}"><span></span></span>
            Aktuell gelten die Regeln für eine 7 Tage Inzidenz {value}.
        </div>
        """,
        height=150
    )

covid_data = load_covid_data()
if key_data.Meldedatum.max() + pd.Timedelta('1D') < date.today():
    st.caching.clear_cache()
    covid_data = load_covid_data()

einwohner = pd.read_csv('Einwohnerzahlen.csv')


def get_inzidenz_data(landkreise):
    adm_unit_ids = einwohner[einwohner.Region.isin(landkreise)].AdmUnitId
    inzidenz_data = covid_data[(covid_data.NeuerFall != -1) & (covid_data.IdLandkreis.isin(adm_unit_ids))].groupby(['IdLandkreis', 'Meldedatum']).sum()

    idx = pd.DatetimeIndex(pd.date_range(start=covid_data.Meldedatum.min(), end=covid_data.Meldedatum.max(), freq='1D'))
    multi_idx = pd.MultiIndex.from_product([inzidenz_data.index.levels[0], idx], names=["IdLandkreis", "Meldedatum"])
    inzidenz_data = inzidenz_data.reindex(multi_idx, fill_value=0)

    cases_7d = []
    for group, data in inzidenz_data.groupby(level=0):
        cases_7d.extend(data.reset_index().set_index('Meldedatum').rolling(window="7D").sum()['AnzahlFall'].to_list())
    inzidenz_data['AnzahlFall7T'] = cases_7d
    inzidenz_data.reset_index(inplace=True)

    inzidenz_data = inzidenz_data.merge(einwohner, left_on="IdLandkreis", right_on="AdmUnitId")
    inzidenz_data['Inz7T'] = inzidenz_data.AnzahlFall7T * 100000 / inzidenz_data.EWZ
    return inzidenz_data

def get_ampel_color(inz7T):
    ampel = "gruen"
    for i, val in enumerate(inz7T):
        if i > 2:
            w3 = min(inz7T[i-3:i])
            if (w3 >= 100) & (ampel == "gruen"):
                ampel = "gelb"
            if (w3 >= 150) & (ampel == "gelb"):
                ampel = "rot"
            if (w3 >= 165) & (ampel == "rot"):
                ampel = "blau"
        if i > 4:
            w5 = max(inz7T[i-5:i])
            if (w5 < 165) & (ampel == "blau"):
                ampel = "rot"
            if (w5 < 150) & (ampel == "rot"):
                ampel = "gelb"
            if (w5 < 100) & (ampel == "gelb"):
                ampel = "gruen"
    return ampel

selected_landkreise = st.sidebar.multiselect(
    'Landkreis',
    einwohner.Region
)

if selected_landkreise:
    inzidenz_data = get_inzidenz_data(selected_landkreise)

    for landkreis in selected_landkreise:
        st.markdown(f"## {landkreis}:")
        color = get_ampel_color(inzidenz_data[inzidenz_data.Region == landkreis]['Inz7T'])
        show_traffic_light(color)


    period = pd.date_range(end=inzidenz_data.Meldedatum.max(), periods=10, freq="D")
    notbremse_mask = inzidenz_data.Meldedatum.isin(period) & inzidenz_data.Region.isin(selected_landkreise)
    notbremse_data = inzidenz_data[notbremse_mask]
    notbremse_data.Meldedatum = notbremse_data.Meldedatum.dt.strftime('%Y-%m-%d')
    notbremse_data.set_index(['Region', 'Meldedatum'], inplace=True)
    foo = notbremse_data[['Inz7T']].unstack()


    st.write("# Inzidenzverlauf:")
    st.dataframe(foo.style.applymap(color_notbremse))

    inzidenz_plot = alt.Chart(inzidenz_data[inzidenz_data.Region.isin(selected_landkreise)]).mark_line().encode(
        x='Meldedatum',
        y=alt.Y('Inz7T'),
        color="Region",
    ).interactive(True)

    inzidenz_plot += alt.Chart(pd.DataFrame({'y': [165]})).mark_rule(color="blue").encode(y='y').interactive(True)
    inzidenz_plot += alt.Chart(pd.DataFrame({'y': [150]})).mark_rule(color="red").encode(y='y').interactive(True)
    inzidenz_plot += alt.Chart(pd.DataFrame({'y': [100]})).mark_rule(color="yellow").encode(y='y').interactive(True)
    inzidenz_plot.interactive(True).properties(width=800)

    st.altair_chart(inzidenz_plot, use_container_width=True)
