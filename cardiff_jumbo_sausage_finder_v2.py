"""
Cardiff Jumbo Sausage Finder — Version 2
========================================
Install:
    pip install streamlit pandas requests beautifulsoup4

Run:
    streamlit run cardiff_jumbo_sausage_finder_v2.py

Optional:
    Google Places API (New) key for Google ratings/review counts and addresses.
    Set GOOGLE_MAPS_API_KEY in the environment or enter it in the sidebar.

This app does not scrape Google Maps. Google business data is fetched through
Places API. Menu URLs are fetched only when the user explicitly asks; check
each website/platform's terms and robots policy before automated collection.
Menu listing != live stock. Verify availability with the venue.
"""
from __future__ import annotations
import os, re, math, json
from datetime import datetime, timezone
from urllib.parse import urlparse, quote_plus

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(page_title="Cardiff Jumbo Sausage Finder v2", page_icon="🌭", layout="wide")

TODAY = datetime.now().strftime("%Y-%m-%d")
FIELDS = [
    "venue", "product", "style", "price_gbp", "weight_g", "length_cm",
    "availability", "google_rating", "google_reviews", "address",
    "menu_url", "evidence_url", "evidence_note", "checked_at", "place_id",
    "maps_url", "latitude", "longitude"
]

# Prices transcribed from publicly indexed Cardiff delivery/menu listings during
# the initial research pass. Treat as indicative menu evidence, not live stock.
# Rating/review data is intentionally left blank until refreshed via Places API.
SEED = [
    dict(venue="Canton Fish Bar", product="Jumbo Sausage", style="plain",
         price_gbp=2.10, weight_g=None, length_cm=None, availability="Menu listed — stock unverified",
         google_rating=None, google_reviews=None, address="Cardiff CF5 1GX",
         menu_url="https://eateasy.co.uk/Glamorgan-takeaways/Cardiff-restaurants/Canton-Fish-Bar-CF5-1GX-menu.php",
         evidence_url="https://eateasy.co.uk/Glamorgan-takeaways/Cardiff-restaurants/Canton-Fish-Bar-CF5-1GX-menu.php",
         evidence_note="Menu listing shows Jumbo Sausage £2.10; batter version £2.20.",
         checked_at="2026-11-03", maps_url="https://www.google.com/maps/search/?api=1&query=Canton+Fish+Bar+Cardiff"),
    dict(venue="Ely Food Junction Fish & Chips", product="Jumbo Sausage", style="plain",
         price_gbp=2.49, weight_g=None, length_cm=None, availability="Menu listed — stock unverified",
         google_rating=None, google_reviews=None, address="Ely, Cardiff CF5",
         menu_url="https://www.just-eat.co.uk/restaurants-ely-food-junction-cardiff-cf5/menu",
         evidence_url="https://www.just-eat.co.uk/restaurants-ely-food-junction-cardiff-cf5/menu",
         evidence_note="Just Eat menu listing shows Jumbo Sausage £2.49.",
         checked_at="2026-11-03", maps_url="https://www.google.com/maps/search/?api=1&query=Ely+Food+Junction+Cardiff"),
    dict(venue="Tony's Fish And Chip Bar", product="Jumbo Sausage", style="plain",
         price_gbp=2.50, weight_g=None, length_cm=None, availability="Menu listed — stock unverified",
         google_rating=None, google_reviews=None, address="Cardiff CF10 1FF",
         menu_url="https://eateasy.co.uk/Glamorgan-takeaways/Cardiff-restaurants/Tonys-Fish-And-Chip-Bar-CF10-1FF-menu.php",
         evidence_url="https://eateasy.co.uk/Glamorgan-takeaways/Cardiff-restaurants/Tonys-Fish-And-Chip-Bar-CF10-1FF-menu.php",
         evidence_note="Menu listing shows Jumbo Sausage £2.50; sausage with batter £3.00.",
         checked_at="2026-11-03", maps_url="https://www.google.com/maps/search/?api=1&query=Tonys+Fish+and+Chip+Bar+Cardiff"),
    dict(venue="Fintans Fish & Chips", product="Jumbo Sausage", style="plain",
         price_gbp=3.00, weight_g=None, length_cm=None, availability="Menu listed — stock unverified",
         google_rating=None, google_reviews=None, address="Cardiff",
         menu_url="https://www.just-eat.co.uk/restaurants-fintans-fish-and-chips-cardiff/menu",
         evidence_url="https://www.just-eat.co.uk/restaurants-fintans-fish-and-chips-cardiff/menu",
         evidence_note="Just Eat listing shows Jumbo Sausage £3.00 and Jumbo Battered Sausage £3.25.",
         checked_at="2026-11-03", maps_url="https://www.google.com/maps/search/?api=1&query=Fintans+Fish+and+Chips+Cardiff"),
    dict(venue="Fairways Fish & Chips", product="Jumbo Sausage", style="plain",
         price_gbp=3.00, weight_g=None, length_cm=None, availability="Menu listed — stock unverified",
         google_rating=None, google_reviews=None, address="Cardiff",
         menu_url="https://www.ubereats.com/gb/store/fairways-fish-%26-chips/wAF_Y2IdQsOOnjuNvD3zyw",
         evidence_url="https://www.ubereats.com/gb/store/fairways-fish-%26-chips/wAF_Y2IdQsOOnjuNvD3zyw",
         evidence_note="Uber Eats listing shows Jumbo Sausage £3.00; battered £3.36.",
         checked_at="2026-11-03", maps_url="https://www.google.com/maps/search/?api=1&query=Fairways+Fish+and+Chips+Cardiff"),
    dict(venue="Albany Fish Bar", product="Jumbo Sausage", style="plain",
         price_gbp=3.25, weight_g=None, length_cm=None, availability="Menu listed — stock unverified",
         google_rating=None, google_reviews=None, address="Cardiff CF10",
         menu_url="https://www.just-eat.co.uk/restaurants-albany-fish-bar-cardiff-cf10",
         evidence_url="https://www.just-eat.co.uk/restaurants-albany-fish-bar-cardiff-cf10",
         evidence_note="Just Eat listing shows Jumbo Sausage £3.25.",
         checked_at="2026-11-03", maps_url="https://www.google.com/maps/search/?api=1&query=Albany+Fish+Bar+Cardiff"),
    dict(venue="The Posh Fish And Chip Company", product="Jumbo Sausage", style="plain",
         price_gbp=3.00, weight_g=None, length_cm=None, availability="Menu listed — stock unverified",
         google_rating=None, google_reviews=None, address="Cardiff CF5 2BF",
         menu_url="https://eateasy.co.uk/Glamorgan-takeaways/Cardiff-restaurants/The-Posh-Fish-And-Chip-Company-CF5-2BF-menu.php",
         evidence_url="https://eateasy.co.uk/Glamorgan-takeaways/Cardiff-restaurants/The-Posh-Fish-And-Chip-Company-CF5-2BF-menu.php",
         evidence_note="Menu listing shows Jumbo Sausage £3.00 and Jumbo Sausage Batter £3.00.",
         checked_at="2026-11-03", maps_url="https://www.google.com/maps/search/?api=1&query=The+Posh+Fish+and+Chip+Company+Cardiff"),
    dict(venue="Tredegar Chippy", product="Large Jumbo Sausage", style="plain",
         price_gbp=1.99, weight_g=None, length_cm=None, availability="Menu listed — stock unverified",
         google_rating=None, google_reviews=None, address="Cardiff (delivery listing)",
         menu_url="https://guava.failover.uber.com/gb/store/tredegar-chippy/9kt0zaQLXBiORyAf13d8-w",
         evidence_url="https://guava.failover.uber.com/gb/store/tredegar-chippy/9kt0zaQLXBiORyAf13d8-w",
         evidence_note="Indexed delivery menu shows Large Jumbo Sausage £1.99; confirm Cardiff delivery area/address.",
         checked_at="2026-11-03", maps_url="https://www.google.com/maps/search/?api=1&query=Tredegar+Chippy+Cardiff"),
]
for r in SEED:
    for f in FIELDS:
        r.setdefault(f, None)

def clean_df(df):
    for f in FIELDS:
        if f not in df.columns:
            df[f] = None
    return df[FIELDS].copy()

def places_search(api_key, query):
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": ",".join([
            "places.id", "places.displayName", "places.formattedAddress",
            "places.rating", "places.userRatingCount", "places.googleMapsUri",
            "places.location.latitude", "places.location.longitude"
        ])
    }
    resp = requests.post(url, headers=headers,
                         json={"textQuery": query, "pageSize": 20}, timeout=25)
    resp.raise_for_status()
    results = []
    for p in resp.json().get("places", []):
        loc = p.get("location", {})
        results.append({
            "venue": p.get("displayName", {}).get("text", ""),
            "address": p.get("formattedAddress", ""),
            "google_rating": p.get("rating"),
            "google_reviews": p.get("userRatingCount"),
            "place_id": p.get("id"),
            "maps_url": p.get("googleMapsUri", ""),
            "latitude": loc.get("latitude"),
            "longitude": loc.get("longitude")
        })
    return pd.DataFrame(results)

def fetch_menu_text(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Enter a complete http(s) URL.")
    resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (compatible; MenuPriceResearch/1.0)"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    return " ".join(soup.get_text(" ", strip=True).split())

def extract_sausage_items(text):
    # Match product phrases near a GBP price. User must review before import.
    pattern = re.compile(
        r"(?P<name>(?:large\s+)?(?:jumbo\s+)?(?:battered\s+)?(?:jumbo\s+)?"
        r"(?:plain\s+)?(?:sausage(?:\s+in\s+batter)?|saveloy))"
        r".{0,90}?(?P<price>£\s?\d+(?:\.\d{1,2})?)",
        re.IGNORECASE
    )
    found, seen = [], set()
    for m in pattern.finditer(text):
        name = re.sub(r"\s+", " ", m.group("name")).strip()
        price = float(m.group("price").replace("£", "").replace(" ", ""))
        key = (name.lower(), price)
        if key in seen:
            continue
        seen.add(key)
        low = name.lower()
        if "saveloy" in low:
            style = "saveloy"
        elif "batter" in low:
            style = "battered"
        else:
            style = "plain"
        found.append({"product": name.title(), "style": style, "price_gbp": price})
    return found

def bayes_review_score(rating, count):
    if pd.isna(rating):
        return None
    count = 0 if pd.isna(count) else max(0, float(count))
    return (float(rating) * count + 4.0 * 25) / (count + 25)

def rank_data(df, weights, chosen_style):
    d = df.copy()
    d = d[d["style"].fillna("plain").str.lower().isin(chosen_style)]
    for col in ["price_gbp", "weight_g", "length_cm", "google_rating", "google_reviews"]:
        d[col] = pd.to_numeric(d[col], errors="coerce")
    d["price_per_100g"] = d.apply(
        lambda x: x.price_gbp / x.weight_g * 100
        if pd.notna(x.price_gbp) and pd.notna(x.weight_g) and x.weight_g > 0 else None, axis=1
    )
    d["price_score"] = None
    d["size_score"] = None
    d["review_score"] = d.apply(
        lambda x: bayes_review_score(x.google_rating, x.google_reviews), axis=1
    )
    d["availability_score"] = d["availability"].map({
        "Confirmed in stock": 100, "Menu listed — stock unverified": 55,
        "Call to confirm": 40, "Unknown": 25, "Out of stock": 0
    })
    # Cheapest price score if actual weights are absent; use price/100g where available.
    price_metric = d["price_per_100g"].where(d["price_per_100g"].notna(), d["price_gbp"])
    if price_metric.notna().any():
        lo, hi = price_metric.min(), price_metric.max()
        d["price_score"] = 100.0 if hi == lo else (100 * (hi - price_metric) / (hi - lo))
    size_metric = d["weight_g"].where(d["weight_g"].notna(), d["length_cm"])
    if size_metric.notna().any():
        lo, hi = size_metric.min(), size_metric.max()
        d["size_score"] = 100.0 if hi == lo else (100 * (size_metric - lo) / (hi - lo))
    # Weighted mean across available dimensions; no fabricated zero for missing data.
    cols = {"price_score": weights["price"], "size_score": weights["size"],
            "review_score": weights["reviews"], "availability_score": weights["availability"]}
    scores, coverage = [], []
    for _, row in d.iterrows():
        numerator = denominator = 0.0
        for col, weight in cols.items():
            val = row[col]
            if pd.notna(val) and weight > 0:
                numerator += float(val) * weight
                denominator += weight
        scores.append(round(numerator / denominator, 1) if denominator else None)
        coverage.append(round(100 * denominator / sum(cols.values()), 0) if sum(cols.values()) else 0)
    d["overall_score"] = scores
    d["data_coverage_pct"] = coverage
    return d.sort_values(["overall_score", "data_coverage_pct"], ascending=False, na_position="last")

st.title("🌭 Cardiff Jumbo Sausage Finder")
st.caption("Version 2 · menu evidence, Google business ratings, price/size comparison and weighted rankings")

with st.sidebar:
    st.header("Search settings")
    search_term = st.text_input("Google Places search", "fish and chip shops Cardiff")
    api_key = st.text_input("Google Places API key", value=os.getenv("GOOGLE_MAPS_API_KEY", ""), type="password")
    if st.button("Refresh Google business data", use_container_width=True):
        if not api_key:
            st.error("Add a Google Places API key first.")
        else:
            try:
                st.session_state["places"] = places_search(api_key, search_term)
                st.success(f"Retrieved {len(st.session_state['places'])} places.")
            except Exception as e:
                st.error(f"Places API error: {e}")
    st.divider()
    st.header("Ranking weights")
    wp = st.slider("Price / value", 0, 100, 35)
    ws = st.slider("Size", 0, 100, 25)
    wr = st.slider("Google reviews", 0, 100, 20)
    wa = st.slider("Availability", 0, 100, 20)
    st.caption("Weights are normalised across the available data for each product. Coverage shows how much evidence supports each score.")

if "data_v2" not in st.session_state:
    st.session_state["data_v2"] = clean_df(pd.DataFrame(SEED))

tabs = st.tabs(["Rankings", "Venue & menu data", "Find menu prices", "Google Places", "Method"])

with tabs[0]:
    st.subheader("The leaderboard")
    styles = st.multiselect("Compare product types", ["plain", "battered", "saveloy"], default=["plain"])
    data = st.session_state["data_v2"]
    ranked = rank_data(data, {"price": wp, "size": ws, "reviews": wr, "availability": wa}, styles)
    if ranked.empty:
        st.warning("No products match those filters. Add data in Venue & menu data.")
    else:
        valid = ranked[ranked["overall_score"].notna()]
        if not valid.empty:
            winner = valid.iloc[0]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Current leader", winner["venue"])
            c2.metric("Score", f'{winner["overall_score"]}/100')
            c3.metric("Menu price", f'£{winner["price_gbp"]:.2f}' if pd.notna(winner["price_gbp"]) else "Unknown")
            c4.metric("Evidence coverage", f'{int(winner["data_coverage_pct"])}%')
        st.dataframe(
            ranked[["venue", "product", "style", "price_gbp", "weight_g", "length_cm",
                    "price_per_100g", "availability", "google_rating", "google_reviews",
                    "overall_score", "data_coverage_pct", "evidence_url"]],
            use_container_width=True, hide_index=True,
            column_config={
                "price_gbp": st.column_config.NumberColumn("Price", format="£%.2f"),
                "price_per_100g": st.column_config.NumberColumn("£ / 100g", format="£%.2f"),
                "overall_score": st.column_config.NumberColumn("Score", format="%.1f"),
                "evidence_url": st.column_config.LinkColumn("Menu evidence")
            }
        )
        st.caption("A low evidence-coverage score means the result is provisional. Weight data is currently missing for most listings, so the price score falls back to menu price rather than value per 100g.")
    st.download_button("Download ranked results CSV", ranked.to_csv(index=False), "cardiff_jumbo_sausage_rankings.csv", "text/csv")

with tabs[1]:
    st.subheader("Edit, verify and expand the database")
    st.write("Correct prices, add actual weights/lengths, confirm stock and attach source links. One row represents one product variant.")
    edited = st.data_editor(
        st.session_state["data_v2"], num_rows="dynamic", use_container_width=True,
        column_config={
            "style": st.column_config.SelectboxColumn(options=["plain", "battered", "saveloy"]),
            "availability": st.column_config.SelectboxColumn(options=[
                "Confirmed in stock", "Menu listed — stock unverified", "Call to confirm", "Unknown", "Out of stock"
            ]),
            "price_gbp": st.column_config.NumberColumn(format="£%.2f", min_value=0.0),
            "weight_g": st.column_config.NumberColumn("Weight (g)", min_value=0.0),
            "length_cm": st.column_config.NumberColumn("Length (cm)", min_value=0.0),
            "google_rating": st.column_config.NumberColumn(min_value=0.0, max_value=5.0, step=0.1),
            "google_reviews": st.column_config.NumberColumn(min_value=0, step=1),
            "evidence_url": st.column_config.LinkColumn(),
            "menu_url": st.column_config.LinkColumn(),
            "maps_url": st.column_config.LinkColumn(),
        }
    )
    st.session_state["data_v2"] = clean_df(edited)
    up = st.file_uploader("Import additional venues/products (CSV)", type=["csv"], key="v2csv")
    if up:
        imported = clean_df(pd.read_csv(up))
        st.session_state["data_v2"] = clean_df(pd.concat([st.session_state["data_v2"], imported], ignore_index=True))
        st.success(f"Imported {len(imported)} rows. Review duplicates before saving.")
    st.download_button("Download full database CSV", st.session_state["data_v2"].to_csv(index=False),
                       "cardiff_jumbo_sausage_database.csv", "text/csv")

with tabs[2]:
    st.subheader("Extract sausage prices from a menu page")
    st.warning("Only fetch pages you are permitted to access. Delivery platforms may block automated requests or prohibit scraping. Extraction is a draft: verify every result before adding it.")
    menu_url = st.text_input("Menu URL", placeholder="https://example.co.uk/menu")
    if st.button("Fetch menu and detect sausage items"):
        try:
            page_text = fetch_menu_text(menu_url)
            found = extract_sausage_items(page_text)
            st.session_state["menu_found"] = found
            st.session_state["menu_url_current"] = menu_url
            if not found:
                st.info("No sausage/price pairs were detected. The page may be dynamically rendered or use a different layout; add the product manually.")
        except Exception as e:
            st.error(f"Could not read this menu: {e}")
    if "menu_found" in st.session_state:
        st.write("Detected menu entries — check names and prices:")
        found_df = pd.DataFrame(st.session_state["menu_found"])
        st.dataframe(found_df, use_container_width=True, hide_index=True)
        venue_name = st.text_input("Venue name for these products", key="detected_venue")
        if st.button("Add detected items to database"):
            if not venue_name.strip():
                st.error("Enter the venue name.")
            else:
                new = []
                for item in st.session_state["menu_found"]:
                    row = {f: None for f in FIELDS}
                    row.update({
                        "venue": venue_name.strip(), "product": item["product"],
                        "style": item["style"], "price_gbp": item["price_gbp"],
                        "availability": "Menu listed — stock unverified",
                        "menu_url": st.session_state["menu_url_current"],
                        "evidence_url": st.session_state["menu_url_current"],
                        "evidence_note": "Auto-detected from menu page; verify manually.",
                        "checked_at": TODAY,
                        "maps_url": "https://www.google.com/maps/search/?api=1&query=" + quote_plus(venue_name + " Cardiff")
                    })
                    new.append(row)
                st.session_state["data_v2"] = clean_df(pd.concat(
                    [st.session_state["data_v2"], pd.DataFrame(new)], ignore_index=True))
                st.success(f"Added {len(new)} draft product rows.")

with tabs[3]:
    st.subheader("Google Places results")
    st.write("Use Places API (New) to look up ratings, review counts, addresses, map links and coordinates. It does not provide product-level sausage prices, size or live stock.")
    if "places" in st.session_state:
        places = st.session_state["places"]
        st.dataframe(places, use_container_width=True, hide_index=True)
        if st.button("Merge Google data into matching venue rows"):
            current = st.session_state["data_v2"].copy()
            for idx, row in current.iterrows():
                matches = places[places["venue"].str.casefold() == str(row["venue"]).casefold()]
                if not matches.empty:
                    m = matches.iloc[0]
                    for col in ["google_rating", "google_reviews", "address", "place_id", "maps_url", "latitude", "longitude"]:
                        if pd.notna(m.get(col)):
                            current.at[idx, col] = m[col]
            st.session_state["data_v2"] = clean_df(current)
            st.success("Matching venue rows updated.")
    else:
        st.info("No Google Places search has been run yet.")

with tabs[4]:
    st.subheader("Scoring and data quality")
    st.markdown("""
    - **Price:** compares price per 100g when weight exists; otherwise uses the listed item price. This fallback is explicitly less reliable.
    - **Size:** uses weight first, then length. Missing size does not receive a fabricated score.
    - **Google reviews:** Bayesian-adjusted rating, using a 4.0-star prior over 25 reviews, so a tiny sample is not treated like a large one.
    - **Availability:** confirmed in-stock beats menu-listed; a menu listing is not proof that the item is in stock now.
    - **Evidence coverage:** percentage of the chosen scoring weight backed by available data.
    - **Product variants:** plain sausage, battered sausage and saveloy remain separate categories.

    **Important:** A public menu can be stale, prices may vary between collection and delivery, and Google ratings apply to the venue rather than the sausage. Always confirm the product, price and stock with the shop.
    """)
    st.code("pip install streamlit pandas requests beautifulsoup4\nstreamlit run cardiff_jumbo_sausage_finder_v2.py", language="bash")

st.divider()
st.caption(f"Local database session · generated {TODAY}. This app stores edits in the current Streamlit session; download the CSV to keep a durable copy.")
