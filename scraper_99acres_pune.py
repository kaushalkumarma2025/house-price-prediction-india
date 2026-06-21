"""
99acres.com Selenium Scraper — Pune (All Three Property Types)
==============================================================
Produces three CSVs with EXACT columns matching professor's dataset:

  pune_apartments.csv  →  7 cols  (new project listings, npxid URLs)
  pune_flats.csv       →  20 cols (resale flat listings, spid URLs)
  pune_houses.csv      →  21 cols (resale house listings, spid URLs)

Strategy:
  - 99acres is a Next.js app. ALL data lives in __NEXT_DATA__ JSON.
  - No CSS selectors. We parse JSON only.
  - For apartments: scrape new-project search pages → detail pages
  - For flats/houses: scrape resale search pages → detail pages

Install:
    pip install selenium webdriver-manager pandas

Run:
    python scraper_99acres_pune.py
"""

import re
import json
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager


# ══════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════

# New-project listing pages (npxid) → apartments CSV
APARTMENT_SEARCH_URLS = [
    "https://www.99acres.com/new-projects-apartments-in-pune-ffid",
]

# Resale listing pages (spid) → flats CSV
FLAT_SEARCH_URLS = [
    "https://www.99acres.com/flats-for-sale-in-pune-ffid",
]

# Resale listing pages (spid) → houses CSV
HOUSE_SEARCH_URLS = [
    "https://www.99acres.com/house-villa-for-sale-in-pune-ffid",
]

MAX_PAGES      = 5    # listing pages per category (each page ~30 properties)
PAGE_LOAD_WAIT = 8    # seconds after page load before extracting
DETAIL_WAIT    = 5    # seconds after opening a detail page
SCROLL_PAUSE   = 1.5  # seconds between scroll steps


# ══════════════════════════════════════════════════════════════════
#  DRIVER SETUP
# ══════════════════════════════════════════════════════════════════

def get_driver(headless=False):
    opts = Options()
    if headless:
        # Use old headless flag — more stable on Windows than --headless=new
        opts.add_argument("--headless")
        opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--dns-prefetch-disable")
    opts.add_argument("--remote-debugging-port=0")  # avoids port conflicts on Windows
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    opts.page_load_strategy = "eager"   # don't wait for all images/fonts to load
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=opts
    )
    driver.set_page_load_timeout(60)    # crash fast instead of hanging 120s
    driver.set_script_timeout(30)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver


# ══════════════════════════════════════════════════════════════════
#  CORE HELPERS
# ══════════════════════════════════════════════════════════════════

def scroll_page(driver, pause=SCROLL_PAUSE):
    last = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause)
        now = driver.execute_script("return document.body.scrollHeight")
        if now == last:
            break
        last = now


def get_next_data(driver):
    """Extract __NEXT_DATA__ JSON embedded by Next.js on every page."""
    try:
        tag = driver.find_element(By.ID, "__NEXT_DATA__")
        return json.loads(tag.get_attribute("innerHTML"))
    except Exception:
        return {}


def deep_search(obj, key):
    """Recursively find ALL values for a given key in nested JSON."""
    results = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                results.append(v)
            results.extend(deep_search(v, key))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(deep_search(item, key))
    return results


def first_str(obj, *keys, default=""):
    """Return the first non-empty string found among given keys in a dict."""
    for k in keys:
        v = obj.get(k, "")
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, (int, float)) and v:
            return str(v)
    return default


def get_page_source_links(driver, pattern):
    """Regex-search page source for URLs matching pattern."""
    return set(re.findall(pattern, driver.page_source))


# ══════════════════════════════════════════════════════════════════
#  LINK COLLECTION  (works for both npxid and spid pages)
# ══════════════════════════════════════════════════════════════════

def collect_links_from_page(driver, id_type="spid"):
    """
    Collect property detail links from current listing page.
    id_type: 'spid' for resale listings, 'npxid' for new projects
    """
    links = set()

    # 1. Parse __NEXT_DATA__ JSON for URLs / slugs
    data = get_next_data(driver)
    for key in ["pageUrl", "projectUrl", "url", "detailUrl",
                "shareUrl", "propertyUrl", "listingUrl"]:
        for val in deep_search(data, key):
            if isinstance(val, str) and "99acres.com" in val and id_type in val:
                links.add(val.split("?")[0])

    # Slug-based reconstruction
    slug_key = "projectSlug" if id_type == "npxid" else "propertySlug"
    for slug in deep_search(data, slug_key):
        if isinstance(slug, str) and slug:
            links.add(f"https://www.99acres.com/{slug}")

    # 2. Anchor tags
    for a in driver.find_elements(By.CSS_SELECTOR, f"a[href*='{id_type}']"):
        href = a.get_attribute("href")
        if href:
            links.add(href.split("?")[0])

    # 3. Regex on raw page source (catches JS-rendered hrefs)
    if id_type == "npxid":
        pattern = r'https://www\.99acres\.com/[a-z0-9\-]+-npxid-[a-zA-Z0-9]+'
    else:
        pattern = r'https://www\.99acres\.com/[a-z0-9\-]+-spid-[a-zA-Z0-9]+'
    links.update(get_page_source_links(driver, pattern))

    return links


def collect_all_links(driver, search_urls, id_type="spid", max_pages=MAX_PAGES):
    all_links = set()
    for base_url in search_urls:
        for page in range(1, max_pages + 1):
            url = f"{base_url}?page={page}" if page > 1 else base_url
            print(f"    [Page {page}] {url}")
            driver.get(url)
            time.sleep(PAGE_LOAD_WAIT)
            scroll_page(driver)

            before = len(all_links)
            all_links.update(collect_links_from_page(driver, id_type))
            gained = len(all_links) - before
            print(f"           +{gained} links  (total: {len(all_links)})")
            if gained == 0:
                print("           No new links — stopping pagination.")
                break
    return list(all_links)


# ══════════════════════════════════════════════════════════════════
#  APARTMENTS DETAIL PAGE PARSER  (7 columns, npxid URLs)
# ══════════════════════════════════════════════════════════════════

def parse_apartment(driver, url):
    try:
        driver.get(url)
    except Exception:
        pass  # page load timeout — partial load is fine, __NEXT_DATA__ loads early
    time.sleep(DETAIL_WAIT)
    scroll_page(driver)
    data = get_next_data(driver)

    # PropertyName
    name = ""
    for key in ["projectName", "name", "title", "projectTitle"]:
        for v in deep_search(data, key):
            if isinstance(v, str) and len(v) > 2:
                name = v; break
        if name: break
    if not name:
        try: name = driver.find_element(By.TAG_NAME, "h1").text.strip()
        except: pass

    # PropertySubName
    subname = ""
    for key in ["projectSubTitle", "subTitle", "subName", "subHeading"]:
        for v in deep_search(data, key):
            if isinstance(v, str) and ("BHK" in v or "Pune" in v):
                subname = v; break
        if subname: break
    if not subname:
        bhks = deep_search(data, "bedroomCount") or deep_search(data, "bhkType") or []
        loc  = next(iter(deep_search(data, "localityName") or [""]), "")
        if bhks:
            subname = f"{', '.join(str(b) for b in bhks[:5])} BHK in {loc}, Pune"

    # NearbyLocations (list of names)
    nearby = []
    for key in ["landmarks", "nearbyLandmarks", "nearByLocations",
                "nearbyLocations", "locationAdvantages"]:
        for f in deep_search(data, key):
            if isinstance(f, list):
                for item in f:
                    n = (item.get("name") or item.get("landmarkName") or "") \
                        if isinstance(item, dict) else (item if isinstance(item, str) else "")
                    if n: nearby.append(n)
            elif isinstance(f, dict):
                n = f.get("name") or f.get("landmarkName") or ""
                if n: nearby.append(n)
        if nearby: break
    nearby = list(dict.fromkeys(nearby))

    # LocationAdvantages (dict name→distance)
    locadv = {}
    for key in ["landmarks", "nearbyLandmarks", "nearByLocations",
                "locationAdvantages", "nearbyLocations"]:
        for f in deep_search(data, key):
            if isinstance(f, list):
                for item in f:
                    if isinstance(item, dict):
                        n = item.get("name") or item.get("landmarkName") or ""
                        d = item.get("distance") or item.get("dist") or item.get("value") or ""
                        if n: locadv[n] = str(d)
        if locadv: break

    # PriceDetails (dict BHK→{building_type, area_type, area, price-range})
    price_details = {}
    unit_list = []
    for key in ["unitConfigs", "unitConfig", "configurations",
                "floorPlanDetails", "bhkDetails", "propertyConfigs"]:
        for f in deep_search(data, key):
            if isinstance(f, list) and f:
                unit_list = f; break
        if unit_list: break

    for unit in unit_list:
        if not isinstance(unit, dict): continue
        bhk = first_str(unit, "bedroomCount", "bhkType", "bedroom", "configName")
        if isinstance(bhk, str) and bhk.isdigit():
            bhk = f"{bhk} BHK"
        elif bhk and "BHK" not in bhk.upper():
            bhk = f"{bhk} BHK"
        btype     = first_str(unit, "propertyType", "buildingType", "type", default="Apartment")
        area_type = first_str(unit, "areaType", "builtUpAreaType", default="Super Built-up Area")
        amin = first_str(unit, "minArea", "areaMin", "carpetArea")
        amax = first_str(unit, "maxArea", "areaMax")
        aunit = first_str(unit, "areaUnit", default="sq.ft.")
        area_str = f"{amin} - {amax} {aunit}" if amin and amax and amin != amax \
                   else (f"{amin} {aunit}" if amin else "")
        pmin = first_str(unit, "minPrice", "priceMin")
        pmax = first_str(unit, "maxPrice", "priceMax")
        price_str = f"₹ {pmin} - {pmax}" if pmin and pmax and pmin != pmax \
                    else (f"₹ {pmin}" if pmin else
                          first_str(unit, "price", "priceLabel", default="Price on Request"))
        if bhk:
            price_details[bhk] = {"building_type": btype, "area_type": area_type,
                                   "area": area_str, "price-range": price_str}

    # TopFacilities (list of names)
    facilities = []
    for key in ["amenities", "facilities", "topFacilities",
                "projectAmenities", "keyHighlights"]:
        for f in deep_search(data, key):
            if isinstance(f, list):
                for item in f:
                    n = (item.get("name") or item.get("amenityName") or
                         item.get("facilityName") or item.get("label") or "") \
                        if isinstance(item, dict) else (item if isinstance(item, str) else "")
                    if n: facilities.append(n)
        if facilities: break
    facilities = list(dict.fromkeys(facilities))

    return {
        "PropertyName":       name,
        "PropertySubName":    subname,
        "NearbyLocations":    str(nearby),
        "LocationAdvantages": str(locadv),
        "Link":               url,
        "PriceDetails":       str(price_details),
        "TopFacilities":      str(facilities),
    }


# ══════════════════════════════════════════════════════════════════
#  FLATS / HOUSES DETAIL PAGE PARSER  (spid URLs)
#  Flats  → 20 cols (no 'rate' col, has 'floorNum')
#  Houses → 21 cols (has 'rate' and 'noOfFloor')
# ══════════════════════════════════════════════════════════════════

def parse_resale(driver, url, prop_type="flat"):
    """
    prop_type: 'flat' or 'house'
    Extracts all fields from __NEXT_DATA__ JSON on a spid detail page.
    """
    driver.get(url)
    time.sleep(DETAIL_WAIT)
    scroll_page(driver)
    data  = get_next_data(driver)
    src   = driver.page_source

    # ── property_name ─────────────────────────────────────────────
    prop_name = ""
    for key in ["propertyName", "listingTitle", "title", "name"]:
        for v in deep_search(data, key):
            if isinstance(v, str) and len(v) > 3:
                prop_name = v; break
        if prop_name: break
    if not prop_name:
        try: prop_name = driver.find_element(By.TAG_NAME, "h1").text.strip()
        except: pass

    # ── link ──────────────────────────────────────────────────────
    link = url

    # ── society ───────────────────────────────────────────────────
    society = ""
    for key in ["societyName", "society", "projectName", "buildingName",
                "localityName"]:
        for v in deep_search(data, key):
            if isinstance(v, str) and len(v) > 1:
                society = v; break
        if society: break

    # ── price ─────────────────────────────────────────────────────
    price = ""
    for key in ["price", "expectedPrice", "totalPrice", "listingPrice"]:
        for v in deep_search(data, key):
            if v and str(v).strip() not in ("0", ""):
                price = str(v); break
        if price: break

    # ── area (price per sq.ft. label) ─────────────────────────────
    # In flats.csv: area = '₹ 5,000/sq.ft.'
    area = ""
    for key in ["pricePerUnitArea", "ratePerSqft", "pricePerSqft"]:
        for v in deep_search(data, key):
            if v:
                area = f"₹ {v}/sq.ft."; break
        if area: break

    # ── rate (houses only) ────────────────────────────────────────
    # In houses.csv: rate = '₹ 20,115/sq.ft.'
    rate = area  # same source, different column name in houses

    # ── areaWithType ──────────────────────────────────────────────
    area_with_type = ""
    for key in ["areaWithType", "carpetAreaWithType", "builtUpAreaWithType",
                "superBuiltUpAreaWithType"]:
        for v in deep_search(data, key):
            if isinstance(v, str) and v:
                area_with_type = v; break
        if area_with_type: break
    if not area_with_type:
        # Build it: "Carpet area: 900 (83.61 sq.m.)"
        carea = ""
        atype = ""
        for key in ["carpetArea", "builtUpArea", "superBuiltUpArea"]:
            for v in deep_search(data, key):
                if v:
                    carea = str(v)
                    atype = key.replace("Area","").replace("carpet","Carpet ").strip()
                    break
            if carea: break
        if carea:
            area_with_type = f"{atype} area: {carea}"

    # ── bedRoom ───────────────────────────────────────────────────
    bedroom = ""
    for key in ["bedroomCount", "bedroom", "bhk", "noOfBedrooms"]:
        for v in deep_search(data, key):
            if v:
                bedroom = f"{v} Bedroom{'s' if int(str(v).split()[0]) > 1 else ''}"; break
        if bedroom: break

    # ── bathroom ──────────────────────────────────────────────────
    bathroom = ""
    for key in ["bathroomCount", "bathroom", "noOfBathrooms"]:
        for v in deep_search(data, key):
            if v:
                bathroom = f"{v} Bathroom{'s' if int(str(v).split()[0]) > 1 else ''}"; break
        if bathroom: break

    # ── balcony ───────────────────────────────────────────────────
    balcony = ""
    for key in ["balconyCount", "balcony", "noOfBalconies"]:
        for v in deep_search(data, key):
            if v:
                b = str(v)
                balcony = f"{b} Balon{'ies' if int(b) > 1 else 'y'}"; break
        if balcony: break

    # ── additionalRoom ────────────────────────────────────────────
    additional_room = ""
    for key in ["additionalRooms", "otherRooms", "additionalRoom",
                "extraRoom", "servantRoom", "studyRoom"]:
        for v in deep_search(data, key):
            if isinstance(v, str) and v:
                additional_room = v; break
            elif isinstance(v, list) and v:
                additional_room = ",".join(str(x) for x in v); break
        if additional_room: break

    # ── address ───────────────────────────────────────────────────
    address = ""
    for key in ["address", "fullAddress", "propertyAddress", "location"]:
        for v in deep_search(data, key):
            if isinstance(v, str) and len(v) > 5:
                address = v; break
        if address: break

    # ── floorNum (flats only: '4th  of 4 Floors') ────────────────
    floor_num = ""
    for key in ["floorNo", "floorNumber", "floorNum", "floor"]:
        for v in deep_search(data, key):
            if v:
                floor_num = str(v); break
        if floor_num: break
    total_floors = ""
    for key in ["totalFloors", "noOfFloors", "totalFloor"]:
        for v in deep_search(data, key):
            if v:
                total_floors = str(v); break
        if total_floors: break
    if floor_num and total_floors:
        suffix = {1:"st",2:"nd",3:"rd"}.get(int(re.sub(r'\D','',floor_num) or 0) % 10, "th")
        floor_num = f"{floor_num}{suffix}  of {total_floors} Floors"
    elif floor_num:
        floor_num = str(floor_num)

    # ── noOfFloor (houses only: '3 Floors') ──────────────────────
    no_of_floor = ""
    for key in ["noOfFloors", "totalFloors", "floors", "noOfFloor"]:
        for v in deep_search(data, key):
            if v:
                no_of_floor = f"{v} Floors"; break
        if no_of_floor: break

    # ── facing ────────────────────────────────────────────────────
    facing = ""
    for key in ["facing", "propertyFacing", "direction"]:
        for v in deep_search(data, key):
            if isinstance(v, str) and v:
                facing = v; break
        if facing: break

    # ── agePossession ─────────────────────────────────────────────
    age_possession = ""
    for key in ["agePossession", "possessionAge", "propertyAge",
                "ageOfConstruction", "possessionStatus"]:
        for v in deep_search(data, key):
            if isinstance(v, str) and v:
                age_possession = v; break
        if age_possession: break

    # ── nearbyLocations (flat list, no distances) ─────────────────
    nearby = []
    for key in ["landmarks", "nearbyLandmarks", "nearByLocations",
                "nearbyLocations"]:
        for f in deep_search(data, key):
            if isinstance(f, list):
                for item in f:
                    n = (item.get("name") or item.get("landmarkName") or "") \
                        if isinstance(item, dict) else (item if isinstance(item, str) else "")
                    if n: nearby.append(n)
            elif isinstance(f, str) and f:
                nearby.append(f)
        if nearby: break
    nearby = list(dict.fromkeys(nearby))

    # ── description ───────────────────────────────────────────────
    description = ""
    for key in ["description", "propertyDescription", "desc", "aboutProperty"]:
        for v in deep_search(data, key):
            if isinstance(v, str) and len(v) > 20:
                description = v; break
        if description: break

    # ── furnishDetails ────────────────────────────────────────────
    furnish = []
    for key in ["furnishDetails", "furnishingDetails", "furnishings",
                "furnitureDetails"]:
        for f in deep_search(data, key):
            if isinstance(f, list):
                for item in f:
                    n = (item.get("name") or item.get("item") or "") \
                        if isinstance(item, dict) else (item if isinstance(item, str) else "")
                    if n: furnish.append(n)
            elif isinstance(f, dict):
                n = f.get("name") or f.get("item") or ""
                if n: furnish.append(n)
        if furnish: break

    # ── features ──────────────────────────────────────────────────
    features = []
    for key in ["features", "amenities", "facilities", "highlights"]:
        for f in deep_search(data, key):
            if isinstance(f, list):
                for item in f:
                    n = (item.get("name") or item.get("feature") or "") \
                        if isinstance(item, dict) else (item if isinstance(item, str) else "")
                    if n: features.append(n)
        if features: break
    features = list(dict.fromkeys(features))

    # ── rating ────────────────────────────────────────────────────
    # Format: ['Environment4 out of 5', 'Safety4 out of 5', ...]
    rating = []
    for key in ["ratings", "rating", "localityRatings", "propertyRatings"]:
        for f in deep_search(data, key):
            if isinstance(f, list):
                for item in f:
                    if isinstance(item, dict):
                        rtype = item.get("type") or item.get("category") or item.get("name") or ""
                        rval  = item.get("value") or item.get("rating") or item.get("score") or ""
                        if rtype and rval:
                            rating.append(f"{rtype}{rval} out of 5")
                    elif isinstance(item, str) and "out of" in item:
                        rating.append(item)
            elif isinstance(f, dict):
                for rtype, rval in f.items():
                    if rval:
                        rating.append(f"{rtype}{rval} out of 5")
        if rating: break

    # ── property_id ───────────────────────────────────────────────
    # Extracted from URL: spid-XXXXXXXX
    pid_match = re.search(r'spid-([A-Za-z0-9]+)', url)
    property_id = pid_match.group(1) if pid_match else ""
    if not property_id:
        for key in ["propertyId", "listingId", "id"]:
            for v in deep_search(data, key):
                if isinstance(v, str) and len(v) > 3:
                    property_id = v; break
            if property_id: break

    if prop_type == "flat":
        return {
            "property_name":    prop_name,
            "link":             link,
            "society":          society,
            "price":            price,
            "area":             area,
            "areaWithType":     area_with_type,
            "bedRoom":          bedroom,
            "bathroom":         bathroom,
            "balcony":          balcony,
            "additionalRoom":   additional_room,
            "address":          address,
            "floorNum":         floor_num,
            "facing":           facing,
            "agePossession":    age_possession,
            "nearbyLocations":  str(nearby),
            "description":      description,
            "furnishDetails":   str(furnish),
            "features":         str(features),
            "rating":           str(rating),
            "property_id":      property_id,
        }
    else:  # house — adds 'rate', replaces 'floorNum' with 'noOfFloor'
        return {
            "property_name":    prop_name,
            "link":             link,
            "society":          society,
            "price":            price,
            "rate":             rate,
            "area":             area,
            "areaWithType":     area_with_type,
            "bedRoom":          bedroom,
            "bathroom":         bathroom,
            "balcony":          balcony,
            "additionalRoom":   additional_room,
            "address":          address,
            "noOfFloor":        no_of_floor,
            "facing":           facing,
            "agePossession":    age_possession,
            "nearbyLocations":  str(nearby),
            "description":      description,
            "furnishDetails":   str(furnish),
            "features":         str(features),
            "rating":           str(rating),
            "property_id":      property_id,
        }


# ══════════════════════════════════════════════════════════════════
#  PIPELINE
# ══════════════════════════════════════════════════════════════════

def run_category(label, search_urls, parser_fn, id_type, columns, output_file):
    print(f"\n{'='*60}")
    print(f"  {label.upper()}")
    print(f"{'='*60}")

    driver = get_driver(headless=False)
    records = []

    try:
        print("\n[Step 1] Collecting links...")
        links = collect_all_links(driver, search_urls, id_type=id_type)
        print(f"  → {len(links)} unique links found")

        if not links:
            print("  ⚠ Zero links found.")
            print("  Try: set headless=False in get_driver() to see what Chrome loads.")
            print("  OR:  99acres may be showing a CAPTCHA — solve it once, then re-run.")
            return pd.DataFrame(columns=columns)

        print(f"\n[Step 2] Scraping {len(links)} detail pages...")
        for i, link in enumerate(links, 1):
            print(f"  [{i:3d}/{len(links)}] {link}")
            try:
                record = parser_fn(link)
                records.append(record)
                name = record.get("PropertyName") or record.get("property_name") or ""
                print(f"         → {name or '(no name)'}")
            except Exception as e:
                print(f"         ERROR: {e}")
            time.sleep(1.5)

    finally:
        driver.quit()

    df = pd.DataFrame(records, columns=columns)
    df.to_csv(output_file, index=False)
    print(f"\n  ✓ Saved {len(df)} rows → {output_file}")
    return df


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    driver_ref = {"obj": None}

    # ── APARTMENTS ────────────────────────────────────────────────
    drv = get_driver(headless=False)
    try:
        links_apt = collect_all_links(drv, APARTMENT_SEARCH_URLS,
                                      id_type="npxid", max_pages=MAX_PAGES)
    finally:
        drv.quit()

    drv2 = get_driver(headless=False)
    apt_records = []
    try:
        for i, link in enumerate(links_apt, 1):
            print(f"  APT [{i}/{len(links_apt)}] {link}")
            try:
                apt_records.append(parse_apartment(drv2, link))
            except Exception as e:
                print(f"    ERROR: {e}")
            time.sleep(1.5)
    finally:
        drv2.quit()

    apt_cols = ["PropertyName","PropertySubName","NearbyLocations",
                "LocationAdvantages","Link","PriceDetails","TopFacilities"]
    df_apt = pd.DataFrame(apt_records, columns=apt_cols)
    df_apt.to_csv("pune_apartments.csv", index=False)
    print(f"\n✓ pune_apartments.csv  — {len(df_apt)} rows, {len(df_apt.columns)} cols")

    # ── FLATS ─────────────────────────────────────────────────────
    drv3 = get_driver(headless=False)
    try:
        links_flat = collect_all_links(drv3, FLAT_SEARCH_URLS,
                                       id_type="spid", max_pages=MAX_PAGES)
    finally:
        drv3.quit()

    drv4 = get_driver(headless=False)
    flat_records = []
    try:
        for i, link in enumerate(links_flat, 1):
            print(f"  FLAT [{i}/{len(links_flat)}] {link}")
            try:
                flat_records.append(parse_resale(drv4, link, prop_type="flat"))
            except Exception as e:
                print(f"    ERROR: {e}")
            time.sleep(1.5)
    finally:
        drv4.quit()

    flat_cols = ["property_name","link","society","price","area","areaWithType",
                 "bedRoom","bathroom","balcony","additionalRoom","address","floorNum",
                 "facing","agePossession","nearbyLocations","description",
                 "furnishDetails","features","rating","property_id"]
    df_flat = pd.DataFrame(flat_records, columns=flat_cols)
    df_flat.to_csv("pune_flats.csv", index=False)
    print(f"✓ pune_flats.csv       — {len(df_flat)} rows, {len(df_flat.columns)} cols")

    # ── HOUSES ────────────────────────────────────────────────────
    drv5 = get_driver(headless=False)
    try:
        links_house = collect_all_links(drv5, HOUSE_SEARCH_URLS,
                                        id_type="spid", max_pages=MAX_PAGES)
    finally:
        drv5.quit()

    drv6 = get_driver(headless=False)
    house_records = []
    try:
        for i, link in enumerate(links_house, 1):
            print(f"  HOUSE [{i}/{len(links_house)}] {link}")
            try:
                house_records.append(parse_resale(drv6, link, prop_type="house"))
            except Exception as e:
                print(f"    ERROR: {e}")
            time.sleep(1.5)
    finally:
        drv6.quit()

    house_cols = ["property_name","link","society","price","rate","area","areaWithType",
                  "bedRoom","bathroom","balcony","additionalRoom","address","noOfFloor",
                  "facing","agePossession","nearbyLocations","description",
                  "furnishDetails","features","rating","property_id"]
    df_house = pd.DataFrame(house_records, columns=house_cols)
    df_house.to_csv("pune_houses.csv", index=False)
    print(f"✓ pune_houses.csv      — {len(df_house)} rows, {len(df_house.columns)} cols")

    # ── SUMMARY ───────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  SCRAPING COMPLETE")
    print(f"{'='*60}")
    print(f"  pune_apartments.csv  :  {len(df_apt):4d} rows,  7 cols")
    print(f"  pune_flats.csv       :  {len(df_flat):4d} rows, 20 cols")
    print(f"  pune_houses.csv      :  {len(df_house):4d} rows, 21 cols")


if __name__ == "__main__":
    main()