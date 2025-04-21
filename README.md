# POI-Finder 🗺️

A Python desktop application that analyzes a GPX route and finds relevant POIs (e.g., supermarkets, kiosks, fuel stations) along the way using the Overpass API. Includes filtering for POIs open on a specific date, accounting for Sundays and public holidays in Germany. Which unfortunately does not yet work as hoped.

## Features

- 🧭 Load and analyze `.gpx` route files
- 📍 Interpolate points every X km along the route (with skip zones at start and end)
- 🔎 Search nearby POIs (within custom radius)
- ⏰ Optional filtering by opening hours on a specific travel date
- 🏛 Detect German state automatically via reverse geocoding (for holiday checks)
- 📅 Includes public holiday logic per German state
- 🗺 Generates interactive HTML map with POI markers and route
- 💾 Save a new GPX file with POIs as waypoints
- ⚙️ Simple GUI using Tkinter

## Requirements

    - Python 3.9+

    - Required packages:

        - gpxpy

        - geopy

        - folium

        - overpy

        - tkcalendar

        - holidays

        - opening-hours

        - tkinter (built-in on most systems)

## Usage

Run the app:

    python main.py

In the GUI:

        Choose a GPX file.

        Set the step size (distance between sample points, in km).

        Define the search radius (meters).

        Optionally set a travel date to only show POIs open on that day.

        Optionally skip X km at the beginning and/or end of the route.

View results:

        An interactive map (.html) will be opened in your browser.

        Export a new .gpx with POIs as waypoints.

## Notes

Opening hours are parsed via opening-hours and may fail if the format is non-standard or broken.

Public holidays are determined using the holidays package with automatic detection of the German state based on GPS coordinates.

For performance, Overpass queries are run in a background thread.

## Limitations

Reverse geocoding may fail temporarily if the Nominatim API is rate-limited.

Some POIs may have incomplete or malformed tags (e.g., missing name or opening_hours).

Opening hours logic assumes that holidays follow Sunday schedules, which is a general but not universal rule.

## License

MIT License


### Contributions and feedback welcome!
