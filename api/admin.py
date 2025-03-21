from django.contrib import admin
from api.models import Location, Trip, LogEntry, RouteInstruction

admin.site.register(Location)
admin.site.register(Trip)
admin.site.register(LogEntry)
admin.site.register(RouteInstruction)
