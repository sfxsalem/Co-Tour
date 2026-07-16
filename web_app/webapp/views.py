import math
from datetime import datetime
import folium

from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from django.views.generic import TemplateView

from cotour.flows import FlowInputError, FlowQuery, FlowService
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


class HomeView(TemplateView):
    template_name = 'webapp/home.html'


class TfaView(TemplateView):
    template_name = 'webapp/tourist_flow_analysis.html'
    service = FlowService(settings.BASE_DIR / "data")
    cluster_colors = {
        0: "#3c78ff",
        1: "#36a269",
        2: "#ff9c3b",
        3: "#9b72e8",
    }

    def get_map(self, attractions):
        figure = folium.Figure()
        map_view = folium.Map(
            location=[48.137154, 11.576124],
            tiles='cartodbpositron',
            zoom_start=12,
        )
        for attraction in attractions:
            color = self.cluster_colors[attraction.cluster]
            folium.CircleMarker(
                radius=8,
                color=color,
                location=[attraction.latitude, attraction.longitude],
                fill=True,
                fill_color=color,
                tooltip=f"{attraction.name} · cluster {attraction.cluster}",
            ).add_to(map_view)
        map_view.add_to(figure)
        return figure

    @staticmethod
    def get_map2(origins):
        figure = folium.Figure()
        map_view = folium.Map(
            location=[20, 0],
            tiles='cartodbpositron',
            zoom_start=2,
        )
        for origin in origins:
            folium.CircleMarker(
                radius=4 + min(12, math.sqrt(origin.share_percent) * 2),
                location=[origin.latitude, origin.longitude],
                color="#3c78ff",
                fill=True,
                fill_color="#3c78ff",
                tooltip=f"{origin.country}: {origin.share_percent:.1f}% of visitors",
            ).add_to(map_view)
        map_view.add_to(figure)
        return figure

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            result = self.service.analyze(
                FlowQuery(
                    place=self.request.GET.get("tfa_place_select", "Olympiapark"),
                    season=self.request.GET.get(
                        "tfa_season_select", "summer_pre_covid"
                    ),
                )
            )
        except FlowInputError as error:
            raise SuspiciousOperation(str(error)) from error

        options = self.service.options()
        context.update(
            {
                "map": self.get_map(result.attractions),
                "map2": self.get_map2(result.origins),
                "selected_season": result.season,
                "selected_place": result.place,
                "PlacesList": options.places,
                "SeasonList": {
                    season.code: season.label for season in options.seasons
                },
                "flow_result": result,
            }
        )
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
