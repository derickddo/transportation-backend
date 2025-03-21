import requests
from datetime import timedelta
from django.utils.timezone import now
from django.db.models import Sum
from .models import RouteInstruction, Trip, LogEntry, Location
import random

class TripService:
    """
    Handles trip calculations, including generating route instructions.
    """

    AVG_SPEED_MPH = 55  # Align with front-end assumption
    FUEL_STOP_INTERVAL = 1000  # Fuel every 1,000 miles
    FUEL_STOP_DURATION = 30  # Align with front-end (30 minutes)
    PICKUP_DROPOFF_DURATION = 60  # 1 hour for pickup & dropoff
    MAX_DRIVE_HOURS_PER_DAY = 11  # FMCSA rule: 11-hour driving limit
    MAX_ON_DUTY_HOURS_PER_DAY = 14  # FMCSA rule: 14-hour on-duty window
    MANDATORY_BREAK_DURATION = 30  # 30-minute break after 8 hours of driving
    MANDATORY_BREAK_THRESHOLD = 8  # Break required after 8 hours of driving
    SLEEPER_BERTH_DURATION = 7  # 7 hours sleeper berth
    OFF_DUTY_DURATION = 3  # 3 hours off duty (total 10-hour rest)
    MAX_HOURS_PER_WEEK = 70  # 70-hour/8-day limit
    MAX_HOURS_PER_CYCLE = 60  # 60-hour/7-day limit
    DRIVER_WAKE_UP_TIME = 4  # Driver wakes up at 4:00 AM (in hours)
    DRIVER_START_TIME = 6  # Driver starts at pickup location at 6:00 AM (in hours)

    @staticmethod
    def get_number_of_days(trip):
        """
        Calculates the number of days required for the trip based on driving hours,
        including pickup/drop-off, rest breaks, and fuel stops.
        """
        if trip.distance == 0:
            distance, _ = TripService.get_distance_and_duration(
                trip.pickup_location.latitude, trip.pickup_location.longitude,
                trip.dropoff_location.latitude, trip.dropoff_location.longitude
            )
            if distance is None:
                raise ValueError("Unable to calculate distance for the trip.")
            trip.distance = distance
            trip.save()

        driving_hours = trip.distance / TripService.AVG_SPEED_MPH
        total_fuel_stops = max(0, (trip.distance // TripService.FUEL_STOP_INTERVAL))
        fuel_stop_hours = total_fuel_stops * (TripService.FUEL_STOP_DURATION / 60)

        # Calculate mandatory breaks (one 30-minute break per 14-hour on-duty window)
        total_on_duty_windows = driving_hours / TripService.MAX_ON_DUTY_HOURS_PER_DAY
        total_breaks = max(0, int(total_on_duty_windows))  # One break per 14-hour window
        break_hours = total_breaks * (TripService.MANDATORY_BREAK_DURATION / 60)

        # Add pickup, drop-off, and pre-trip on-duty time
        total_non_driving_hours = (TripService.PICKUP_DROPOFF_DURATION * 2 / 60) + fuel_stop_hours + break_hours
        total_non_driving_hours += (TripService.DRIVER_START_TIME - TripService.DRIVER_WAKE_UP_TIME)  # 2 hours pre-trip

        # Total time including driving and non-driving
        total_hours = driving_hours + total_non_driving_hours

        # Calculate days, accounting for 11-hour driving limit and 14-hour on-duty window
        current_time = TripService.DRIVER_WAKE_UP_TIME  # Start at 4:00 AM
        remaining_driving_hours = driving_hours
        total_driving_time_today = 0
        on_duty_window = 0
        num_days = 1

        # Add pre-trip on-duty time
        current_time += (TripService.DRIVER_START_TIME - TripService.DRIVER_WAKE_UP_TIME)
        on_duty_window += (TripService.DRIVER_START_TIME - TripService.DRIVER_WAKE_UP_TIME)

        while remaining_driving_hours > 0:
            # Calculate driving time for the current on-duty window
            driving_hours_before_break = min(
                TripService.MANDATORY_BREAK_THRESHOLD,
                TripService.MAX_DRIVE_HOURS_PER_DAY - total_driving_time_today,
                TripService.MAX_ON_DUTY_HOURS_PER_DAY - on_duty_window,
                remaining_driving_hours
            )

            if driving_hours_before_break > 0:
                current_time += driving_hours_before_break
                on_duty_window += driving_hours_before_break
                total_driving_time_today += driving_hours_before_break
                remaining_driving_hours -= driving_hours_before_break

            # Add mandatory break if 8 hours of driving have been reached
            if total_driving_time_today >= TripService.MANDATORY_BREAK_THRESHOLD and on_duty_window < TripService.MAX_ON_DUTY_HOURS_PER_DAY:
                current_time += TripService.MANDATORY_BREAK_DURATION / 60
                on_duty_window += TripService.MANDATORY_BREAK_DURATION / 60

            # Check if the day or on-duty window is over
            if (total_driving_time_today >= TripService.MAX_DRIVE_HOURS_PER_DAY or
                on_duty_window >= TripService.MAX_ON_DUTY_HOURS_PER_DAY) and remaining_driving_hours > 0:
                # Add 10-hour rest
                current_time += (TripService.SLEEPER_BERTH_DURATION + TripService.OFF_DUTY_DURATION)

                # Reset for the next on-duty window
                total_driving_time_today = 0
                on_duty_window = 0

                # Check if we've crossed into a new 24-hour period
                if current_time >= 24:
                    num_days += 1
                    current_time -= 24

        # Add pickup and drop-off time to the final day
        current_time += (TripService.PICKUP_DROPOFF_DURATION * 2 / 60)

        # If the final time exceeds 24 hours, increment the day
        if current_time >= 24:
            num_days += 1

        return max(1, num_days)

    @staticmethod
    def generate_random_current_location(pickup_location, dropoff_location, halt_type):
        """
        Generate a random current location along the route between pickup and dropoff locations.
        The location is selected based on the halt_type (FUEL, BREAK, or STOP).
        Uses reverse geocoding to get a meaningful name.
        """
        API_KEY = "5b3ce3597851110001cf62487069056f2c3940edbd6052342210264d"
        url = f"https://api.openrouteservice.org/v2/directions/driving-car?api_key={API_KEY}&start={pickup_location.longitude},{pickup_location.latitude}&end={dropoff_location.longitude},{dropoff_location.latitude}"

        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an exception for bad status codes
            data = response.json()

            # Check if the response contains features
            if not data.get("features"):
                raise ValueError("No route features found in OpenRouteService response")

            feature = data["features"][0]
            if "geometry" not in feature or "coordinates" not in feature["geometry"]:
                raise ValueError("No geometry coordinates found in OpenRouteService response")

            # Extract the route coordinates (list of [longitude, latitude])
            coordinates = feature["geometry"]["coordinates"]
            if len(coordinates) < 2:
                raise ValueError("Insufficient coordinates to select a random location")

            # Select a random point along the route (excluding start and end to avoid overlap)
            random_index = random.randint(1, len(coordinates) - 2)
            random_coord = coordinates[random_index]

            # Try to extract a name from the route data
            name = "Unknown Location"
            address = "Unknown"
            if "properties" in feature and "segments" in feature["properties"]:
                segments = feature["properties"]["segments"]
                for segment in segments:
                    if "steps" in segment:
                        for step in segment["steps"]:
                            if "name" in step and step["name"]:
                                name = step["name"]
                                if "," in name:
                                    parts = name.split(",")
                                    name = parts[0].strip()  # Take the first part (e.g., "Cleveland HSt")
                                    address = ", ".join(parts[1:]).strip() or name
                                break
                        if name != "Unknown Location":
                            break

            # Use reverse geocoding to get a more meaningful name
            geocode_url = f"https://api.openrouteservice.org/geocode/reverse?api_key={API_KEY}&point.lat={random_coord[1]}&point.lon={random_coord[0]}"
            try:
                geocode_response = requests.get(geocode_url)
                geocode_response.raise_for_status()
                geocode_data = geocode_response.json()
                if geocode_data.get("features"):
                    geocode_feature = geocode_data["features"][0]
                    name = geocode_feature["properties"].get("name", name)
                    address = geocode_feature["properties"].get("label", address) or name
                    # If the name is still not meaningful, try to extract a street or city
                    if "street" in geocode_feature["properties"]:
                        name = geocode_feature["properties"]["street"]
                    elif "locality" in geocode_feature["properties"]:
                        name = geocode_feature["properties"]["locality"]
            except Exception as e:
                print(f"Error reverse geocoding: {e}")

            # Customize the location name based on halt_type (remove "Drive Stop" prefix)
            if halt_type == "DRIVE":
                location_name = name  # Just the street or city name (e.g., "Cleveland HSt")
            else:
                location_name = f"{halt_type.capitalize()} Stop: {name}" if halt_type != "STOP" else name

            current_location = Location.objects.create(
                name=location_name,
                address=address,
                latitude=random_coord[1],  # Latitude
                longitude=random_coord[0],  # Longitude
            )
            return current_location

        except requests.RequestException as e:
            print(f"Error fetching route from OpenRouteService: {e}")
            # Fallback: Create a dummy location
            return Location.objects.create(
                name=f"{halt_type.capitalize()} Stop: Fallback Location" if halt_type != "STOP" else "Fallback Location",
                address="Unknown",
                latitude=(pickup_location.latitude + dropoff_location.latitude) / 2,
                longitude=(pickup_location.longitude + dropoff_location.longitude) / 2,
            )
        except Exception as e:
            print(f"Error generating random location: {e}")
            # Fallback: Create a dummy location
            return Location.objects.create(
                name=f"{halt_type.capitalize()} Stop: Fallback Location" if halt_type != "STOP" else "Fallback Location",
                address="Unknown",
                latitude=(pickup_location.latitude + dropoff_location.latitude) / 2,
                longitude=(pickup_location.longitude + dropoff_location.longitude) / 2,
            )

    @staticmethod
    def get_distance_and_duration(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng):
        """
        Calls OpenRouteService API to get the distance (in miles) and duration (in hours and minutes).
        """
        API_KEY = "5b3ce3597851110001cf62487069056f2c3940edbd6052342210264d"
        url = f"https://api.openrouteservice.org/v2/directions/driving-car?api_key={API_KEY}&start={pickup_lng},{pickup_lat}&end={dropoff_lng},{dropoff_lat}"

        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an exception for bad status codes
            data = response.json()

            

            # Check if the response contains features
            if not data.get("features") or len(data["features"]) == 0:
                print("Error: No features found in OpenRouteService response")
                return None, None

            feature = data["features"][0]

            # Extract distance and duration from the feature properties
            if "properties" not in feature or "summary" not in feature["properties"]:
                print("Error: No summary found in OpenRouteService response")
                return None, None

            summary = feature["properties"]["summary"]

            # Extract distance and duration
            distance_meters = summary["distance"]  # Distance in meters
            duration_seconds = summary["duration"]  # Duration in seconds

            # Convert distance to miles
            distance_km = distance_meters / 1000
            distance_miles = distance_km * 0.621371  # Convert kilometers to miles

            # Convert duration to hours and minutes
            duration_hours = duration_seconds // 3600
            duration_minutes = (duration_seconds % 3600) // 60

            return round(distance_miles, 2), f"{int(duration_hours)}h {int(duration_minutes)}m"
        except requests.RequestException as e:
            print(f"Error fetching distance from OpenRouteService: {e}")
            return None, None
        except Exception as e:
            print(f"Error processing OpenRouteService response: {e}")
            return None, None

    @staticmethod
    def generate_route_instructions(trip):
        """
        Generates route instructions based on distance, stops, and FMCSA rules.
        Aligns with front-end assumptions (e.g., no fuel stops for < 1,000 miles).
        Starts the timeline at 4:00 AM with "On Duty (not driving)" until 6:00 AM.
        """
        if trip.distance == 0:
            distance, _ = TripService.get_distance_and_duration(
                trip.pickup_location.latitude, trip.pickup_location.longitude,
                trip.dropoff_location.latitude, trip.dropoff_location.longitude
            )
            if distance is None:
                raise ValueError("Unable to calculate distance for the trip.")
            trip.distance = distance
            trip.save()

        distance = trip.distance
        total_driving_hours = distance / TripService.AVG_SPEED_MPH
        total_fuel_stops = max(0, (distance // TripService.FUEL_STOP_INTERVAL))

        # Clear existing route instructions
        trip.route_instructions.clear()

        # Initialize variables for timeline calculation
        current_time = TripService.DRIVER_WAKE_UP_TIME  # Start at 4:00 AM (in hours)
        current_day = 1
        remaining_distance = distance
        total_driving_time_today = 0
        on_duty_window = 0
        distance_covered = 0
        route_instructions = []
        has_taken_break = False  # Track if a break has been taken in the current on-duty window

        # Add Pre-Trip On Duty (not driving) Instruction (4:00 AM to 6:00 AM)
        pre_trip_duration = (TripService.DRIVER_START_TIME - TripService.DRIVER_WAKE_UP_TIME) * 60  # 2 hours in minutes
        pre_trip_instruction = RouteInstruction.objects.create(
            halt_type="ON_DUTY_NOT_DRIVING",
            duration=pre_trip_duration,
            description="Pre-trip preparation and travel to pickup location",
            day=current_day,
            current_location=trip.pickup_location,  # Assume preparation happens at or near the pickup location
        )
        route_instructions.append(pre_trip_instruction)
        current_time += (TripService.DRIVER_START_TIME - TripService.DRIVER_WAKE_UP_TIME)  # Move to 6:00 AM
        on_duty_window += (TripService.DRIVER_START_TIME - TripService.DRIVER_WAKE_UP_TIME)

        # Add Pickup Instruction (at 6:00 AM)
        pickup_instruction = RouteInstruction.objects.create(
            halt_type="STOP",
            duration=TripService.PICKUP_DROPOFF_DURATION,
            description="Pickup at location",
            day=current_day,
            current_location=trip.pickup_location,
        )
        route_instructions.append(pickup_instruction)
        current_time += TripService.PICKUP_DROPOFF_DURATION / 60  # 1 hour
        on_duty_window += TripService.PICKUP_DROPOFF_DURATION / 60

        # Main loop to calculate driving, breaks, fuel stops, and rest periods
        while remaining_distance > 0.01:  # Small threshold to handle floating-point errors
            # Calculate driving time before a mandatory break or end of day
            driving_hours_before_break = min(
                TripService.MANDATORY_BREAK_THRESHOLD if not has_taken_break else TripService.MAX_DRIVE_HOURS_PER_DAY,
                TripService.MAX_DRIVE_HOURS_PER_DAY - total_driving_time_today,
                TripService.MAX_ON_DUTY_HOURS_PER_DAY - on_duty_window,
                remaining_distance / TripService.AVG_SPEED_MPH
            )

            if driving_hours_before_break > 0:
                distance_covered += driving_hours_before_break * TripService.AVG_SPEED_MPH
                remaining_distance -= driving_hours_before_break * TripService.AVG_SPEED_MPH

                # Add driving instruction
                current_location = TripService.generate_random_current_location(
                    pickup_location=trip.pickup_location,
                    dropoff_location=trip.dropoff_location,
                    halt_type="DRIVE"
                )
                driving_instruction = RouteInstruction.objects.create(
                    halt_type="DRIVE",
                    duration=int(driving_hours_before_break * 60),  # Convert to minutes
                    description="Driving",
                    day=current_day,
                    current_location=current_location,
                )
                route_instructions.append(driving_instruction)

                current_time += driving_hours_before_break
                on_duty_window += driving_hours_before_break
                total_driving_time_today += driving_hours_before_break

            # Check for fuel stop (every 1,000 miles)
            if distance >= TripService.FUEL_STOP_INTERVAL and distance_covered >= TripService.FUEL_STOP_INTERVAL:
                fuel_instruction = RouteInstruction.objects.create(
                    halt_type="FUEL",
                    duration=TripService.FUEL_STOP_DURATION,
                    description="Fuel stop",
                    day=current_day,
                    current_location=TripService.generate_random_current_location(
                        pickup_location=trip.pickup_location,
                        dropoff_location=trip.dropoff_location,
                        halt_type="FUEL"
                    ),
                )
                route_instructions.append(fuel_instruction)
                current_time += TripService.FUEL_STOP_DURATION / 60
                on_duty_window += TripService.FUEL_STOP_DURATION / 60
                distance_covered -= TripService.FUEL_STOP_INTERVAL  # Reset for next fuel stop

            # Check for mandatory 30-minute break after 8 hours of driving (only once per 14-hour window)
            if not has_taken_break and total_driving_time_today >= TripService.MANDATORY_BREAK_THRESHOLD:
                break_instruction = RouteInstruction.objects.create(
                    halt_type="BREAK",
                    duration=TripService.MANDATORY_BREAK_DURATION,
                    description="Mandatory 30-minute rest break",
                    day=current_day,
                    current_location=TripService.generate_random_current_location(
                        pickup_location=trip.pickup_location,
                        dropoff_location=trip.dropoff_location,
                        halt_type="BREAK"
                    ),
                )
                route_instructions.append(break_instruction)
                current_time += TripService.MANDATORY_BREAK_DURATION / 60
                on_duty_window += TripService.MANDATORY_BREAK_DURATION / 60
                has_taken_break = True

            # Check if the day or on-duty window is over
            if (total_driving_time_today >= TripService.MAX_DRIVE_HOURS_PER_DAY or
                on_duty_window >= TripService.MAX_ON_DUTY_HOURS_PER_DAY) and remaining_distance > 0.01:
                # Add sleeper berth and off-duty periods (10-hour rest)
                sleeper_instruction = RouteInstruction.objects.create(
                    halt_type="SLEEPER",
                    duration=TripService.SLEEPER_BERTH_DURATION * 60,
                    description="Sleeper Berth Rest",
                    day=current_day,
                    current_location=TripService.generate_random_current_location(
                        pickup_location=trip.pickup_location,
                        dropoff_location=trip.dropoff_location,
                        halt_type="SLEEPER"
                    ),
                )
                route_instructions.append(sleeper_instruction)
                current_time += TripService.SLEEPER_BERTH_DURATION

                off_duty_instruction = RouteInstruction.objects.create(
                    halt_type="OFF_DUTY",
                    duration=TripService.OFF_DUTY_DURATION * 60,
                    description="Off Duty Rest",
                    day=current_day,
                    current_location=sleeper_instruction.current_location,
                )
                route_instructions.append(off_duty_instruction)
                current_time += TripService.OFF_DUTY_DURATION

                # Reset for the next on-duty window
                total_driving_time_today = 0
                on_duty_window = 0
                has_taken_break = False

                # Check if we've crossed into a new 24-hour period
                if current_time >= 24:
                    current_day += 1
                    current_time -= 24

        # Add Drop-off Instruction
        dropoff_instruction = RouteInstruction.objects.create(
            halt_type="STOP",
            duration=TripService.PICKUP_DROPOFF_DURATION,
            description="Dropoff at location",
            day=current_day,
            current_location=trip.dropoff_location,
        )
        route_instructions.append(dropoff_instruction)
        current_time += TripService.PICKUP_DROPOFF_DURATION / 60

        # Add all route instructions to the trip
        for instruction in route_instructions:
            trip.route_instructions.add(instruction)

        # Update the number of days
        trip.number_of_days = current_day if current_time < 24 else current_day + 1
        trip.save()