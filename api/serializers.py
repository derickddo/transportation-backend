from rest_framework import serializers
from .models import Location, Trip, LogEntry, RouteInstruction


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = '__all__'


class CreateTripSerializer(serializers.ModelSerializer):
    pickup_location_name = serializers.CharField()
    current_location_name = serializers.CharField()
    dropoff_location_name = serializers.CharField()
    class Meta:
        model = Trip
        fields = ['pickup_location_name', 'current_location_name', 'dropoff_location_name']
        

# Serializer for the RouteInstruction model
class RouteInstructionSerializer(serializers.ModelSerializer):
    current_location = serializers.CharField(allow_null=True)  # Allow null values for current_location
    
    def get_current_location(self, obj):
        return obj.current_location.name if obj.current_location else None
    class Meta:
        model = RouteInstruction
        fields = ['halt_type', 'duration', 'description', 'day', 'current_location']
        
        
# Serializer for the Trip model
class TripSerializer(serializers.ModelSerializer):
    pickup_location = LocationSerializer()  # Nested serializer for pickup_location
    dropoff_location = LocationSerializer()  # Nested serializer for dropoff_location
    current_location = LocationSerializer(allow_null=True)  # Nested serializer for current_location (can be null)
    route_instructions = RouteInstructionSerializer(many=True, read_only=True)  # Nested serializer for route_instructions

    class Meta:
        model = Trip
        fields = [
            'id',  # Include the ID field for completeness
            'pickup_location',
            'dropoff_location',
            'current_location',
            'cycle_used',
            'distance',
            'number_of_days',
            'route_instructions'
        ]




class LogEntrySerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(allow_blank=True)
    load_number = serializers.CharField(allow_blank=True)
    carrier_name = serializers.CharField(allow_blank=True)
    truck_number = serializers.CharField(allow_blank=True)
    trailer_number = serializers.CharField(allow_blank=True)
    
    
    class Meta:
        model = LogEntry
        fields = ['trip', 'driver_name', 'load_number', 'carrier_name', 'truck_number', 'trailer_number']
        
        
class RouteInstructionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RouteInstruction
        fields = '__all__'