import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import gpxpy
import gpxpy.gpx
import overpy
import folium
from geopy.distance import geodesic
import webbrowser
import os

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

# === Interpolate points every step_km ===
def interpolate_every_km(coords, step_km=4):
    sampled = [coords[0]]
    dist_accum = 0.0
    last = coords[0]
    for pt in coords[1:]:
        dist = geodesic(last, pt).km
        dist_accum += dist
        if dist_accum >= step_km:
            sampled.append(pt)
            dist_accum = 0.0
            last = pt
    return sampled

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
        popup_text = f"""<b>{poi['name']}</b><br>
        Type: {poi['type']}<br>
        Distance: {poi['distance_km']} km<br>
        Opening hours: {poi['opening_hours']}"""
        folium.Marker(
            location=[poi["lat"], poi["lon"]],
            popup=folium.Popup(popup_text, max_width=250),
            icon=folium.Icon(color="red")
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
        wpt = gpxpy.gpx.GPXWaypoint(
            latitude=poi["lat"],
            longitude=poi["lon"],
            name=poi["name"],
            description=f"{poi['type']} • {poi['opening_hours']} • {poi['distance_km']} km from start"
        )
        gpx.waypoints.append(wpt)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(gpx.to_xml())

# === Analysis thread function ===
def analyze_thread(path, step_km, radius):
    try:
        route_coords = load_gpx_file(path)
        sample_points = interpolate_every_km(route_coords, step_km)
        pois = {}
        total_steps = len(sample_points)

        for i, (lat, lon) in enumerate(sample_points):
            try:
                result = query_pois(lat, lon, radius)
                for node in result.nodes:
                    pois[node.id] = {
                        "name": node.tags.get("name", "Unknown"),
                        "type": node.tags.get("shop", node.tags.get("amenity", "POI")),
                        "lat": node.lat,
                        "lon": node.lon,
                        "distance_km": round(geodesic(route_coords[0], (node.lat, node.lon)).km, 2),
                        "opening_hours": node.tags.get("opening_hours", "n/a"),
                    }
            except Exception as e:
                print("Overpass query error:", e)
            progress = int((i + 1) / total_steps * 100)
            progress_var.set(progress)
            progress_bar.update()

        save_gpx(route_coords, pois, "route_with_pois.gpx")
        generate_map(route_coords, pois, "route_with_pois.html")
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
        step_km = int(entry_step.get())
        radius = int(entry_radius.get())
        threading.Thread(target=analyze_thread, args=(path, step_km, radius), daemon=True).start()
    except Exception as e:
        messagebox.showerror("Error", str(e))

# === GUI setup ===
root = tk.Tk()
root.title("POI Finder for GPX Routes")
root.geometry("400x250")

frame = tk.Frame(root)
frame.pack(pady=20)

btn = tk.Button(frame, text="Select GPX file and analyze", command=start_analysis)
btn.grid(row=0, column=0, columnspan=2, pady=10)

tk.Label(frame, text="Step (km):").grid(row=1, column=0)
entry_step = tk.Entry(frame)
entry_step.insert(0, "4")
entry_step.grid(row=1, column=1)

tk.Label(frame, text="Radius (m):").grid(row=2, column=0)
entry_radius = tk.Entry(frame)
entry_radius.insert(0, "600")
entry_radius.grid(row=2, column=1)

# === Progress bar ===
progress_var = tk.IntVar()
progress_bar = ttk.Progressbar(root, variable=progress_var, maximum=100, length=300)
progress_bar.pack(pady=20)

root.mainloop()
