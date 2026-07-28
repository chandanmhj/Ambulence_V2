"""
Classifies raw Overpass hospital data into:
  - type: primary / secondary / tertiary  (same as before)
  - specialties: list of specialty categories this hospital can be routed to
                 for (cardiology, orthopedic, ophthalmology, ent, neurology,
                 maternity, pediatric, psychiatric, oncology, nephrology_urology,
                 pulmonology, gastroenterology, general)

A hospital can have multiple specialties. Every hospital gets "general" added
if it's a large/multispecialty facility (or if nothing more specific matched),
so severity-only routing (no specialty text entered) keeps working exactly as
before.
"""

import json
import re

# ---------- Existing type classification (unchanged from before) ----------

EXCLUDE_KEYWORDS = [
    "dental", "optical", "opticals", "eye care centre", "homeopath", "homoeopath",
    "veterinary", "vet clinic", "physiotherapy", "ayurved", "arya vaidya",
    "skin clinic", "dermat", "ivf", "fertility", "diagnostic lab",
    "diagnostics", "pathology", "pharmacy", "chemist"
]
# Note: "eye care" alone is NOT excluded anymore since we now want to route to
# eye hospitals for ophthalmology emergencies - only excludes generic optical/
# spectacles shops misclassified as hospitals by OSM.

TERTIARY_KEYWORDS = [
    "medical college", "institute", "multispeciality", "multispecialty",
    "super speciality", "superspeciality", "teaching hospital", "nimhans",
    "victoria", "bowring", "manipal", "narayana", "fortis", "apollo",
    "aster", "sparsh", "columbia asia", "vikram", "mazumdar", "st john",
    "st. john", "bgs gleneagles", "sagar", "hosmat", "jayadeva",
    "kidwai", "vani vilas", "trauma center", "trauma centre", "research institute"
]

PRIMARY_KEYWORDS = [
    "primary health centre", "phc", "dispensary", "clinic",
    "health centre", "health center", "nursing home"
]

# ---------- New: specialty classification ----------

SPECIALTY_KEYWORDS = {
    "cardiology": [
        "cardiology", "cardiac", "heart institute", "heart hospital", "cardio",
        "chest pain",
    ],
    "orthopedic": [
        "ortho", "orthopedic", "orthopaedic", "bone and joint", "fracture",
        "sports injury", "hosmat",
    ],
    "ophthalmology": [
        "eye hospital", "eye care", "eye institute", "ophthalmic", "ophthalmology",
        "vision care", "netra", "eye clinic",
    ],
    "ent": [
        "ent hospital", "ent clinic", "ear nose throat", "ent centre", "ent center",
        "otolaryngology",
    ],
    "neurology": [
        "neuro", "neurology", "neurosurgery", "stroke centre", "stroke center",
        "brain and spine", "nimhans",
    ],
    "maternity": [
        "maternity", "obstetric", "gynec", "gynaec", "women and children",
        "mother and child", "cloud nine", "fertility",
    ],
    "pediatric": [
        "pediatric", "paediatric", "children hospital", "child care", "kids",
    ],
    "psychiatric": [
        "psychiatr", "mental health", "de-addiction", "nimhans",
    ],
    "oncology": [
        "cancer", "oncology", "kidwai",
    ],
    "nephrology_urology": [
        "nephrology", "urology", "kidney", "dialysis", "stone clinic",
    ],
    "pulmonology": [
        "pulmonology", "chest hospital", "respiratory", "tb hospital", "lung",
    ],
    "gastroenterology": [
        "gastro", "liver", "digestive",
    ],
}


def is_excluded(name):
    name_lower = name.lower()
    return any(kw in name_lower for kw in EXCLUDE_KEYWORDS)


def classify_type(tags):
    name = tags.get("name", "").lower()
    amenity = tags.get("amenity", "")
    emergency = tags.get("emergency", "").lower()
    healthcare = tags.get("healthcare", "").lower()

    if any(kw in name for kw in TERTIARY_KEYWORDS):
        return "tertiary"

    if amenity == "clinic" or healthcare == "clinic" or any(kw in name for kw in PRIMARY_KEYWORDS):
        return "primary"

    if amenity == "hospital":
        if emergency == "yes":
            return "secondary"
        return "primary"

    return "primary"


def classify_specialties(name, hospital_type):
    name_lower = name.lower()
    specialties = []

    for category, keywords in SPECIALTY_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            specialties.append(category)

    is_multispecialty = any(kw in name_lower for kw in TERTIARY_KEYWORDS)

    # Large/multispecialty facilities (and tertiary hospitals in general) can
    # reasonably handle anything, so tag them "general" too - this keeps
    # severity-only routing (no specialty text) working exactly as before,
    # and lets them still be selected for a specific specialty search if no
    # dedicated specialty hospital is nearby.
    if is_multispecialty or hospital_type == "tertiary" or not specialties:
        specialties.append("general")

    return sorted(set(specialties))


def process(input_path="raw_hospitals.json", output_path="hospitals.json"):
    with open(input_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    elements = raw.get("elements", [])
    cleaned = []
    seen_names_coords = set()

    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name", "").strip()

        if not name:
            continue
        if is_excluded(name):
            continue

        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if lat is None or lon is None:
            continue

        key = (name.lower(), round(lat, 4), round(lon, 4))
        if key in seen_names_coords:
            continue
        seen_names_coords.add(key)

        hospital_type = classify_type(tags)
        specialties = classify_specialties(name, hospital_type)

        cleaned.append({
            "name": name,
            "lat": lat,
            "lon": lon,
            "type": hospital_type,
            "specialties": specialties,
            "emergency": tags.get("emergency", "unknown"),
            "operator_type": tags.get("operator:type", "unknown"),
            "phone": tags.get("phone", ""),
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)

    type_counts = {}
    specialty_counts = {}
    for h in cleaned:
        type_counts[h["type"]] = type_counts.get(h["type"], 0) + 1
        for s in h["specialties"]:
            specialty_counts[s] = specialty_counts.get(s, 0) + 1

    print(f"Processed {len(elements)} raw elements -> {len(cleaned)} clean hospitals")
    print(f"Type breakdown: {type_counts}")
    print(f"Specialty breakdown: {specialty_counts}")
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    process()
