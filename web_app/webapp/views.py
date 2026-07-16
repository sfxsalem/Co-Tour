import math
import re
from datetime import datetime
import numpy as np
import folium
import pandas as pd

from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from django.http import Http404
from django.views.generic import TemplateView

from cotour.forecasts import (
    ForecastInputError,
    ForecastQuery,
    ForecastService,
    Hotspot,
)

from cotour.recommendations import (
    RecommendationInputError,
    RecommendationQuery,
    RecommendationService,
)


SEASON_DATA_DIRECTORY = (
    settings.BASE_DIR / "data" / "Tripadvisor_datasets" / "Seasons"
).resolve()
ALLOWED_SEASONS = frozenset(
    {
        "summer_pre_covid",
        "winter_pre_covid",
        "summer_covid",
        "winter_covid",
    }
)
SAFE_PLACE_NAME = re.compile(r"^[\w .'-]+$", re.UNICODE)


def resolve_season_dataset(place, season):
    """Return an approved season dataset without allowing path traversal."""
    if season not in ALLOWED_SEASONS or not SAFE_PLACE_NAME.fullmatch(place):
        raise SuspiciousOperation("Invalid attraction or season")

    dataset = (SEASON_DATA_DIRECTORY / f"{place}_{season}.csv").resolve()
    if dataset.parent != SEASON_DATA_DIRECTORY:
        raise SuspiciousOperation("Dataset path escaped the approved directory")
    if not dataset.is_file():
        raise Http404("Dataset not found")
    return dataset


def load_tripadvisor_geo_coords():
    geo_coords = pd.read_csv('./data/geocoordinates/TripAdvisor_geoattractions.csv', low_memory=False)
    geo_coords = geo_coords.set_index('place')
    return geo_coords


def get_flow_data():
    data = pd.read_csv("./data/K_means_data/clusters.csv")
    data = data.set_index('attraction_name')
    data['Place'] = data.index
    data['Longitude'] = ''
    data['Latitude'] = ''

    return data


class HomeView(TemplateView):
    template_name = 'webapp/home.html'


class TfaView(TemplateView):
    template_name = 'webapp/tourist_flow_analysis.html'

    def get_season(self):
        tfa_season_select = self.request.GET.get('tfa_season_select', 'summer_pre_covid')
        return tfa_season_select

    def get_place(self):
        tfa_place_select = self.request.GET.get('tfa_place_select', 'Olympiapark')
        return tfa_place_select

    def get_map(self, df, **geo):
        lst_elements = sorted(list(df['Cluster'].unique()))
        lst_colors = ['#%06X' % np.random.randint(0, 0xFFFFFF) for i in
                      range(len(lst_elements))]
        df['Color'] = df['Cluster'].apply(lambda x:
                                          lst_colors[lst_elements.index(x)])
        figure = folium.Figure()
        lat = 48.137154
        lon = 11.576124
        m = folium.Map(
            location=[lat, lon],
            tiles='cartodbpositron',
            zoom_start=12,
        )
        df.apply(lambda row: folium.CircleMarker(radius=8, color=row['Color'],
                                                 location=[row['Latitude'], row['Longitude']], fill=True,
                                                 fill_color=row['Color'], tooltip=str(row["Place"])).add_to(m),
                 axis=1)
        m.add_to(figure)
        figure.render()
        return figure

    def get_map2(self, df, **kwargs):
        figure = folium.Figure()
        lat = 48.137154
        lon = 11.576124
        map1 = folium.Map(
            location=[lat, lon],
            tiles='cartodbpositron',
            zoom_start=4,
        )
        # add a marker on each country propotional to the number of visitors to the selected location
        df.apply(lambda row: folium.CircleMarker(radius=2 + math.ceil(row["flux density"]),
                                                 location=[row["latitude"], row["longitude"]], fill=True,
                                                 fill_color='#3186cc', tooltip=str(
                round(row["flux density"], 1)) + '% of visitors originate from ' + str(row["country"])).add_to(map1),
                 axis=1)
        map1.add_to(figure)
        figure.render()
        return figure

    def get_context_data(self, **kwargs):
        context = super(TfaView, self).get_context_data(**kwargs)
        season = self.get_season()
        place = self.get_place()
        season_dataset = resolve_season_dataset(place, season)

        geo_coords = load_tripadvisor_geo_coords()
        geo_flow = get_flow_data()

        for flow_place in geo_flow.index:
            try:
                geo_flow.loc[flow_place, 'Latitude'] = geo_coords.loc[flow_place, 'latitude']
                geo_flow.loc[flow_place, 'Longitude'] = geo_coords.loc[flow_place, 'longitude']
            except:
                geo_flow.loc[flow_place, 'Latitude'] = ''
                geo_flow.loc[flow_place, 'Longitude'] = ''
        PlacesList = geo_coords.index
        SeasonList = {'summer_pre_covid': 'Summer 2019', 'winter_pre_covid': 'Winter 2019',
                      'summer_covid': 'Summer 2020', 'winter_covid': 'Winter 2020'}
        geo_trajectory = pd.read_csv(season_dataset)
        figure = self.get_map(geo_flow)
        figure2 = self.get_map2(geo_trajectory)
        context['map'] = figure
        context['map2'] = figure2
        context['selected_season'] = season
        context['selected_place'] = place
        context['PlacesList'] = PlacesList
        context['SeasonList'] = SeasonList
        return context


class ThfView(TemplateView):
    template_name = 'webapp/tourist_hotspot_forecast.html'
    service = ForecastService(settings.BASE_DIR / "data")

    @staticmethod
    def get_map(hotspots: tuple[Hotspot, ...]):
        figure = folium.Figure()
        map_view = folium.Map(
            location=[48.137154, 11.576124],
            tiles='cartodbpositron',
            zoom_start=12,
        )
        for hotspot in hotspots:
            folium.Marker(
                icon=folium.Icon(color=hotspot.color),
                location=[hotspot.latitude, hotspot.longitude],
                tooltip=f"{hotspot.name}: {hotspot.weight:.1%}",
            ).add_to(map_view)
        map_view.add_to(figure)
        return figure

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            query = ForecastQuery(
                predicted_month=datetime.strptime(
                    self.request.GET.get("tfh_month_select", "Jul 2020"), "%b %Y"
                ).date(),
                historical_month=datetime.strptime(
                    self.request.GET.get("month_picker", "Apr 2020"), "%b %Y"
                ).date(),
            )
            result = self.service.forecast(query)
        except (ForecastInputError, ValueError) as error:
            raise SuspiciousOperation(str(error)) from error

        options = self.service.options()
        context.update(
            {
                "map": self.get_map(result.predicted),
                "map2": self.get_map(result.historical),
                "PredDateList": tuple(
                    month.strftime("%b %Y") for month in options.predicted_months
                ),
                "HistDateList": tuple(
                    month.strftime("%b %Y") for month in options.historical_months
                ),
                "selected_pred_date": result.predicted_month.strftime("%b %Y"),
                "selected_hist_date": result.historical_month.strftime("%b %Y"),
                "top_10": result.top_attractions,
            }
        )
        return context


class TrsView(TemplateView):
    template_name = 'webapp/tourism_recommendation_system.html'
    service = RecommendationService(settings.BASE_DIR / "data")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            query = RecommendationQuery(
                country=self.request.GET.get("trs_country_select", "Tunisia"),
                german_city=self.request.GET.get("trs_city_select", "Munich"),
                visit_type=self.request.GET.get("trs_visit_select", "solo"),
                accommodation=self.request.GET.get(
                    "trs_accommodation_select", "Maxvorstadt"
                ),
                visit_date=datetime.strptime(
                    self.request.GET.get("date_picker", "2020-08-10"), "%Y-%m-%d"
                ).date(),
                preference=self.request.GET.get(
                    "trs_preferences_select", "outdoors"
                ),
            )
            recommendations = self.service.recommend(query)
        except (RecommendationInputError, ValueError) as error:
            raise SuspiciousOperation(str(error)) from error

        options = self.service.options()
        context.update(
            {
                "selected_country": query.country,
                "selected_city": query.german_city,
                "selected_visit": f"visit_Traveled {query.visit_type}",
                "selected_accommodation": query.accommodation,
                "selected_preference": query.preference,
                "date_picker": query.visit_date.isoformat(),
                "RecommendationResults": {
                    result.name: result.address for result in recommendations
                },
                "CountriesList": options.countries,
                "GermanCitiesList": options.german_cities,
                "DistrictList": options.districts,
            }
        )
        return context


class ContactView(TemplateView):
    template_name = 'webapp/contact.html'
