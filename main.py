import tkinter as tk
from tkinter import filedialog, messagebox, ttk;
from tkcalendar import Calendar
import threading
import gpxpy
import gpxpy.gpx
import overpy
import folium
from geopy.distance import geodesic
import webbrowser
import os
from datetime import datetime
from opening_hours import OpeningHours
from geopy.geocoders import Nominatim
import holidays

# === Detect the German state from coordinates using reverse geocoding ===
def get_state_from_coords(lat, lon):
    try:
        geolocator = Nominatim(user_agent="gpx-poi-analyzer")
        location = geolocator.reverse((lat, lon), language="de")
        if location and 'state' in location.raw['address']:
            return location.raw['address']['state']
        elif location and 'city' in location.raw['address']:
            return location.raw['address']['city'] # city-state
    except Exception as e:
        print("[DEBUG] Reverse geocoding error:", e)
    return None

# === Map German state name to ISO province code ===
def map_state_to_prov_code(state_name):
    state_to_iso = {
        "Baden-Württemberg": "BW",
        "Bayern": "BY",
        "Berlin": "BE",
        "Brandenburg": "BB",
        "Bremen": "HB",
        "Hamburg": "HH",
        "Hessen": "HE",
        "Mecklenburg-Vorpommern": "MV",
        "Niedersachsen": "NI",
        "Nordrhein-Westfalen": "NW",
        "Rheinland-Pfalz": "RP",
        "Saarland": "SL",
        "Sachsen": "SN",
        "Sachsen-Anhalt": "ST",
        "Schleswig-Holstein": "SH",
        "Thüringen": "TH"
    }
    return state_to_iso.get(state_name)

# === Load GPX file ===
def load_gpx_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        gpx = gpxpy.parse(f)
    coords = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                coords.append((point.latitude, point.longitude))
    return coords

# === Cumulative distances along route ===
def cumulative_distances(coords):
    distances = [0.0]
    total = 0.0
    for i in range(1, len(coords)):
        d = geodesic(coords[i - 1], coords[i]).km
        total += d
        distances.append(total)
    return distances

# === Interpolate every step_km ===
def interpolate_every_km(coords, step_km=4):
    sampled = [coords[0]]
    distances = [0.0]
    dist_accum = 0.0
    total_distance = 0.0
    last = coords[0]
    for pt in coords[1:]:
        dist = geodesic(last, pt).km
        dist_accum += dist
        total_distance += dist
        if dist_accum >= step_km:
            sampled.append(pt)
            distances.append(round(total_distance, 2))
            dist_accum = 0.0
            last = pt
    return sampled, distances

# === Overpass API setup ===
api = overpy.Overpass()

def query_pois(lat, lon, radius):
    query = f"""
    (
      node["shop"~"supermarket|convenience|kiosk|beverages"](around:{radius},{lat},{lon});
      node["amenity"="fuel"](around:{radius},{lat},{lon});
    );
    out center;
    """
    return api.query(query)

# === Generate map ===
def generate_map(route_coords, pois, output_path):
    start_lat, start_lon = route_coords[0]
    m = folium.Map(location=[start_lat, start_lon], zoom_start=10)
    folium.PolyLine(route_coords, color="blue", weight=3).add_to(m)
    for poi in pois.values():
        address = f"{poi.get('street', '')} {poi.get('housenumber', '')}, {poi.get('postcode', '')} {poi.get('city', '')}".strip(', ')
        popup_text = f"""<b>{poi['name']}</b><br>
        Type: {poi['type']}<br>
        Distance: {poi['distance_km']} km<br>
        Address: {address}<br>
        Opening hours: {poi['opening_hours']}<br>
        Website: <a href='{poi['website']}' target='_blank'>{poi['website']}</a>""" if poi['website'] else f"""<b>{poi['name']}</b><br>
        Type: {poi['type']}<br>
        Distance: {poi['distance_km']} km<br>
        Address: {address}<br>
        Opening hours: {poi['opening_hours']}"""
        
        if poi['opening_hours'] == "n/a":
            col = "lightgray"
        else:
            col = "blue"

        folium.Marker(
            location=[poi["lat"], poi["lon"]],
            popup=folium.Popup(popup_text, max_width=300),
            icon=folium.Icon(color=col)
        ).add_to(m)
    m.save(output_path)
    webbrowser.open(f'file://{os.path.realpath(output_path)}')

# === Save GPX with POIs ===
def save_gpx(route_coords, pois, filename):
    gpx = gpxpy.gpx.GPX()
    gpx_track = gpxpy.gpx.GPXTrack()
    gpx.tracks.append(gpx_track)
    gpx_segment = gpxpy.gpx.GPXTrackSegment()
    gpx_track.segments.append(gpx_segment)
    for lat, lon in route_coords:
        gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(lat, lon))
    for poi in pois.values():
        address = f"{poi.get('street', '')} {poi.get('housenumber', '')}, {poi.get('postcode', '')} {poi.get('city', '')}".strip(', ')
        description = f"{poi['type']} • {poi['opening_hours']} • {poi['distance_km']} km from start"
        if address:
            description += f" • {address}"
        if poi['website']:
            description += f" • {poi['website']}"

        wpt = gpxpy.gpx.GPXWaypoint(
            latitude=poi["lat"],
            longitude=poi["lon"],
            name=poi["name"],
            description=description
        )
        gpx.waypoints.append(wpt)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(gpx.to_xml())

# === Analysis thread function ===
def analyze_thread(path, step_km, radius, travel_date):
    try:
        path_name = os.path.splitext(os.path.basename(path))[0] # fileName without ext
        path_dir = os.path.dirname(path)
        route_coords = load_gpx_file(path)
        cum_distances = cumulative_distances(route_coords)
        sample_points, _ = interpolate_every_km(route_coords, step_km)
        pois = {}
        total_steps = len(sample_points)

        # Detect travel date and convert to datetime object
        if travel_date == "":
            only_open = False
        else:
            only_open = True
            dt = datetime.strptime(travel_date, "%d.%m.%Y")

        for i, (lat, lon) in enumerate(sample_points):
            try:
                result = query_pois(lat, lon, radius)
                if only_open:
                    # Determine federal state from gpx of route
                    state_name = get_state_from_coords(lat, lon)
                    prov_code = map_state_to_prov_code(state_name)

                    print(f"[DEBUG] Detected state: {state_name} → {prov_code}")

                    # Setup holiday lookup
                    de_holidays = holidays.Germany(prov=prov_code)
                    is_holiday = dt.date() in de_holidays

                for node in result.nodes:
                    oh_raw = node.tags.get("opening_hours", "")
                    is_open = True
                    if only_open and oh_raw:
                        try:
                            dt = datetime.strptime(travel_date, "%d.%m.%Y")
                            weekday_osm = dt.strftime('%a')[:2]  # Get weekday as 'Mo', 'Tu', etc.
                            match oh_raw:
                                case "24/7":
                                    is_open = True
                                case _:
                                    oh = OpeningHours(oh_raw)
                                    is_open = oh.is_open_at(dt)
                                    test_date = dt

                                    # If it's a holiday, treat as Sunday ("Su")
                                    weekday = "Su" if is_holiday else dt.strftime("%a")[:2]
                                    is_open = oh.is_open_at(test_date, day=weekday)

                        except Exception as e:
                            # Fallback: check if weekday is mentioned in the raw string
                            is_open = weekday_osm in oh_raw
                            print(f"[DEBUG] Could not parse opening_hours for node [{node.id}] '{node.tags.get('name', 'Unknown')}': {oh_raw}")
                            print(f"[DEBUG] Fallback check - is_open={is_open} based on weekday '{weekday_osm}'")
                            
                            #is_open = True # Treat as open if not parsable || ToDo: add option and parser
                    if not is_open:
                        continue  # POI will be skipped if not opened.
                    
                    if node.tags.get('name', 'Unknown') == 'Unknown':
                        continue # POI will be skipped if unkown

                    #Cumulative distances along route
                    min_dist = float('inf')
                    closest_idx = 0
                    for idx, coord in enumerate(route_coords):
                        d = geodesic((node.lat, node.lon), coord).km
                        if d < min_dist:
                            min_dist = d
                            closest_idx = idx
                    distance_to_start = round(cum_distances[closest_idx], 2)

                    pois[node.id] = {
                        "name": node.tags.get("name", "Unknown"),
                        "type": node.tags.get("shop", node.tags.get("amenity", "POI")),
                        "lat": node.lat,
                        "lon": node.lon,
                        "distance_km": distance_to_start,
                        "opening_hours": oh_raw or "n/a",
                        "street": node.tags.get("addr:street", ""),
                        "housenumber": node.tags.get("addr:housenumber", ""),
                        "postcode": node.tags.get("addr:postcode", ""),
                        "city": node.tags.get("addr:city", ""),
                        "website": node.tags.get("website", "")
                    }
            except Exception as e:
                print("Overpass query error:", e)

            progress = int((i + 1) / total_steps * 100)
            progress_var.set(progress)
            progress_bar.update()

        #save_gpx(route_coords, pois, os.sep.join([path_dir, path_name + "_with_pois.gpx"]))
        generate_map(route_coords, pois, os.sep.join([path_dir, path_name + "_with_pois.html"]))
        messagebox.showinfo("Done", f"Done! Found {len(pois)} POIs. Files saved.")
        progress_var.set(0)
        progress_bar.update()

    except Exception as e:
        messagebox.showerror("Error", str(e))
        progress_var.set(0)
        progress_bar.update()

# === Start analysis from GUI ===
def start_analysis():
    path = filedialog.askopenfilename(filetypes=[("GPX files", "*.gpx")])
    if not path:
        return
    try:
        travel_date = entry_date.get().strip()
        step_km = int(entry_step.get())
        radius = int(entry_radius.get())
        threading.Thread(
            target=analyze_thread,
            args=(path, step_km, radius, travel_date),
            daemon=True
        ).start()
    except Exception as e:
        messagebox.showerror("Error", str(e))

# === GUI setup ===
root = tk.Tk()
root.title("POI Finder for GPX Routes")
root.geometry("400x250")

frame = tk.Frame(root)
frame.pack(pady=20)

tk.Label(frame, text="Step size (km):").grid(row=0, column=0, sticky="W")
entry_step = tk.Entry(frame)
entry_step.insert(0, "4")
entry_step.grid(row=0, column=1, sticky="W")

tk.Label(frame, text="Search Radius (m):").grid(row=1, column=0, sticky="W")
entry_radius = tk.Entry(frame)
entry_radius.insert(0, "1000")
entry_radius.grid(row=1, column=1, sticky="W")

tk.Label(frame, text="Travel date (DD.MM.YYYY):").grid(row=2, column=0, sticky="W")
entry_date = tk.Entry(frame)
entry_date.insert(0, "")
entry_date.grid(row=2, column=1, sticky="W")

btn = tk.Button(frame, text="Select GPX file and analyze", command=start_analysis)
btn.grid(row=4, column=0, columnspan=2, pady=10)


# === Progress bar ===
progress_var = tk.IntVar()
progress_bar = ttk.Progressbar(root, variable=progress_var, maximum=100, length=300)
progress_bar.pack(pady=10)

root.mainloop()
