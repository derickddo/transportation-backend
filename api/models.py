from django.db import models
from django.utils.timezone import now


class Location(models.Model):
    """
    Represents a geographical location, including stops and break locations.
    """
    name = models.CharField(max_length=255)  # City or stop name
    address = models.CharField(max_length=500)  # Full address
    latitude = models.FloatField()  # For mapping
    longitude = models.FloatField()  # For mapping

    def __str__(self):
        return f"{self.name} ({self.latitude}, {self.longitude})"


class Trip(models.Model):
    """
    Represents a trip with stops and breaks.
    """
    pickup_location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name='pickup_trips'
    )
    dropoff_location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name='dropoff_trips',
        
    )
    current_location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name='current_trips',
        null=True, blank=True
    )
    cycle_used = models.IntegerField()  # Current cycle used in hours
    distance = models.FloatField(default=0, null=True, blank=True)  # Total distance in miles
    number_of_days = models.IntegerField(default=1)  # Number of days for the trip
    route_instructions = models.ManyToManyField('RouteInstruction', related_name='trips', blank=True) # Stops and breaks in the trip; many-to-many relationship because a trip can have multiple stops and breaks

    def __str__(self):
        return f"Trip from {self.pickup_location.name} to {self.dropoff_location.name}"
    
    # delete route instructions when trip is deleted
    def delete(self, *args, **kwargs):
        self.route_instructions.all().delete()
        super().delete(*args, **kwargs)
    
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(cycle_used__gte=0),
                name='cycle_used_gte_0',
            ),
            models.CheckConstraint(
                check=models.Q(distance__gte=0),
                name='distance_gte_0',
            ),
        ]
        
        db_table = 'trip'


class LogEntry(models.Model):
    """
    Represents a log entry associated with a trip.
    """
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='log_entries')
    driver_name = models.CharField(max_length=255)
    load_number = models.CharField(max_length=255, blank=True, null=True)
    carrier_name = models.CharField(max_length=255, blank=True, null=True)
    truck_number = models.CharField(max_length=255, blank=True, null=True)
    trailer_number = models.CharField(max_length=255, blank=True, null=True)
    co_driver_name = models.CharField(max_length=255, blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Log entry for trip {self.trip.id} by {self.driver_name}"

class RouteInstruction(models.Model):
    """
    Represents stops, breaks, and their durations during the trip.
    """
    HALT_TYPE_CHOICES = [ # Type of stop/break
        ('STOP', 'Stop'),
        ('BREAK', 'Break'),
    ]
    
    halt_type = models.CharField(max_length=10, choices=HALT_TYPE_CHOICES)
    duration = models.IntegerField()  # Duration in minutes
    description = models.CharField(max_length=255) # Description of the stop/break
    day = models.IntegerField(default=1)  # Day of the trip when the stop/break occurs
    current_location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name='current_route_instructions',
        null=True, blank=True
    )
    
    def __str__(self):
        return f"{self.halt_type} for {self.duration} minutes"
    
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(duration__gte=0),
                name='duration_gte_0',
            ),
        ]
        
        db_table = 'route_instruction'
        
    
