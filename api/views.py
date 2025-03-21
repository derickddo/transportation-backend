from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework import permissions
from .models import Location, Trip, LogEntry, RouteInstruction
from .serializers import LocationSerializer, TripSerializer, LogEntrySerializer, RouteInstructionSerializer
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .services import TripService
# import generic views
from rest_framework import generics



class TripCreateAndGetAllView(APIView):
    """
    API to create a new trip, ensuring locations exist in the database.
    """

    def get_or_create_location(self, location_data):
        """Retrieve an existing location or create a new one if not found."""
        location, created = Location.objects.get_or_create(
            name=location_data["name"],
            defaults={
                "latitude": location_data["latitude"],
                "longitude": location_data["longitude"],
                "address": location_data["name"],  # Use name as address if missing
            },
        )
        return location
    
   
        
        

    def post(self, request):
        """Handles trip creation with location lookup and route instructions."""
        try:
            pickup_location_data = request.data.get("pickup_location")
            dropoff_location_data = request.data.get("dropoff_location")
            cycle_used = request.data.get("cycle_used")

            if not pickup_location_data or not dropoff_location_data or not cycle_used:
                return Response({"error": "All fields are required"}, status=status.HTTP_400_BAD_REQUEST)

            # Ensure locations exist in the database
            pickup_location = self.get_or_create_location(pickup_location_data)
            dropoff_location = self.get_or_create_location(dropoff_location_data)

            # Create the trip
            trip = Trip.objects.create(
                pickup_location=pickup_location,
                dropoff_location=dropoff_location,
                cycle_used=int(cycle_used),
            )

            # Generate route instructions based on assumptions
            TripService.generate_route_instructions(trip)
            route_instructions = trip.route_instructions.values_list("halt_type", "duration","description",)
            serializer = TripSerializer(trip)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get(self, request):
        """
        API to list all trips.
        """
        trips = Trip.objects.all()
        serializer = TripSerializer(trips, many=True)
        return Response(serializer.data)
        


class TripRetrieveUpdateDeleteView(APIView):
    """
    API to retrieve, update, or delete a trip instance.
    """

    def get(self, request, trip_id):
        """Retrieve a trip instance."""
        trip = get_object_or_404(Trip, id=trip_id)
        serializer = TripSerializer(trip)
        return Response(serializer.data)

    def put(self, request, trip_id):
        """Update a trip instance."""
        trip = get_object_or_404(Trip, id=trip_id)
        serializer = TripSerializer(trip, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, trip_id):
        """Delete a trip instance."""
        trip = get_object_or_404(Trip, id=trip_id)
        trip.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)     
        
    
            
            
           
    
    

class LocationCreateListView(generics.ListCreateAPIView):
    """
    API to create a new location or list all locations.
    """
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    
    def create(self, request, *args, **kwargs):
        # If request data is a list, handle bulk creation
        if isinstance(request.data, list):
            serializer = self.get_serializer(data=request.data, many=True)
        else:
            serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
   


class LogEntryCreateView(generics.CreateAPIView):
    """
    API view to create a new log entry associated with a trip.
    """
    queryset = LogEntry.objects.all()
    serializer_class = LogEntrySerializer
    

class LogEntryListView(generics.ListAPIView):
    serializer_class = LogEntrySerializer
    def get_queryset(self):
        trip_id = self.kwargs['trip_id']
        return LogEntry.objects.filter(trip_id=trip_id)