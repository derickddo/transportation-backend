from django.urls import path
from .views import TripCreateAndGetAllView, LocationCreateListView, TripRetrieveUpdateDeleteView, LogEntryCreateView, LogEntryListView


urlpatterns = [
    path('trips', TripCreateAndGetAllView.as_view(), name='create-trip'),
    path('locations', LocationCreateListView.as_view(), name='create-list-location'),
    path('trips/<int:trip_id>', TripRetrieveUpdateDeleteView.as_view(), name='retrieve-update-delete-trip'),
    path('log-entries', LogEntryCreateView.as_view(), name='log-entry-create'),
    path('trips/<int:trip_id>/log-entries/', LogEntryListView.as_view(), name='log-entry-list')

]
