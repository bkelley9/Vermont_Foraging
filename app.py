import streamlit as st
import pandas as pd
import os
import pickle
import plotly.express as px
from datetime import datetime
import base64
from io import BytesIO

# Load tabulated information from Sayer
vermont_edibles = pd.read_csv("vermont_edibles.csv")
# Populate conservation scores (non-native plants) so numeric filtering can apply
vermont_edibles['conservation'] = vermont_edibles['conservation'].fillna(value = 0)
# Populate edible scores (seasoning/steeped_beverages) so numeric filtering can apply
vermont_edibles['sayer_rating'] = vermont_edibles['sayer_rating'].fillna(value = 0)

vermont_edibles_filt = vermont_edibles.copy()

# Load saved locations
saved_coords = pd.read_csv('saved_coords.csv')

# Load iNaturalist data
with open('master_data.pkl', 'rb') as f:
    master = pickle.load(f)

# Convert data to queryable dataframe
all_edibles = pd.concat(
	[df.assign(species=species) for species, df in master.items()],
    ignore_index=True
)

# Drop duplicates (usually from overlap from querying both a genus and a constituent species)
all_edibles.drop_duplicates(subset = 'uuid', keep='first', inplace=True)

# Add Julian day calculation if not already present
if 'time_observed_at' in all_edibles.columns:
    all_edibles['time_observed_at'] = pd.to_datetime(all_edibles['time_observed_at'], errors = 'coerce', utc = True)

# Convert lat/long to numeric
all_edibles['lat'] = pd.to_numeric(all_edibles['lat'], errors='coerce')
all_edibles['long'] = pd.to_numeric(all_edibles['long'], errors='coerce')

# Remove rows with missing coordinates
df_filtered = all_edibles.dropna(subset=['lat', 'long']).copy()

# Define default current season on page load
def get_current_season():
    """
    Calculate the current season based on Julian day.
    Returns one of: early_spring, mid_spring, late_spring,
                   early_summer, mid_summer, late_summer,
                   early_fall, mid_fall, late_fall,
                   early_winter, mid_winter, late_winter
    """
    julian_day = datetime.now().timetuple().tm_yday
    
    # Season boundaries (approximate for Vermont/Northern climate)
    # Spring: March 1 - May 31 (days 60-151)
    # Summer: June 1 - August 31 (days 152-243)
    # Fall: September 1 - November 30 (days 244-334)
    # Winter: December 1 - February 28/29 (days 335-365, 1-59)
    
    if 60 <= julian_day <= 89:  # March 1-30
        return 'early_spring'
    elif 90 <= julian_day <= 120:  # April 1-30
        return 'mid_spring'
    elif 121 <= julian_day <= 151:  # May 1-31
        return 'late_spring'
    
    elif 152 <= julian_day <= 182:  # June 1-30
        return 'early_summer'
    elif 183 <= julian_day <= 213:  # July 1-31
        return 'mid_summer'
    elif 214 <= julian_day <= 243:  # August 1-31
        return 'late_summer'
    
    elif 244 <= julian_day <= 289:  # September 1 - Oct 15
        return 'early_fall'
    elif 290 <= julian_day <= 334:  # Oct 15 - Nov 30
        return 'late_fall'
    
    elif 335 <= julian_day <= 365:  # December 1-31
        return 'early_winter'
    elif 1 <= julian_day <= 31:  # January 1-31
        return 'mid_winter'
    elif 32 <= julian_day <= 59:  # February 1-28/29
        return 'late_winter'
    
    return 'unknown'  # Should never reach here

current_season = get_current_season()

# ====== PERSONAL FORAGING LOG FUNCTIONS ======
FINDS_FILE = 'my_personal_finds.csv'

def load_personal_finds():
    """Load personal foraging finds from CSV file"""
    if os.path.exists(FINDS_FILE):
        try:
            df = pd.read_csv(FINDS_FILE)
            return df.to_dict('records')
        except Exception as e:
            st.error(f"Error loading finds: {e}")
            return []
    return []

def save_personal_find(species, common_name, date, lat, lon, notes, quantity, rating):
    """Save a new personal find to CSV file"""
    find = {
        'species': species,
        'common_name': common_name,
        'date': date.strftime('%Y-%m-%d'),
        'lat': lat,
        'lon': lon,
        'notes': notes,
        'quantity': quantity,
        'rating': rating,
        'added_on': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Load existing finds and append new one
    if os.path.exists(FINDS_FILE):
        df = pd.read_csv(FINDS_FILE)
        df = pd.concat([df, pd.DataFrame([find])], ignore_index=True)
    else:
        df = pd.DataFrame([find])
    
    df.to_csv(FINDS_FILE, index=False)
    return True

def delete_personal_find(find_index):
    """Delete a personal find by index"""
    if os.path.exists(FINDS_FILE):
        df = pd.read_csv(FINDS_FILE)
        df = df.drop(index=find_index).reset_index(drop=True)
        df.to_csv(FINDS_FILE, index=False)
        return True
    return False

def export_personal_finds():
    """Export personal finds to CSV"""
    if os.path.exists(FINDS_FILE):
        df = pd.read_csv(FINDS_FILE)
        return df.to_csv(index=False)
    return None

def import_personal_finds(csv_file):
    """Import personal finds from CSV"""
    try:
        new_df = pd.read_csv(csv_file)
        
        # Load existing finds and append
        if os.path.exists(FINDS_FILE):
            existing_df = pd.read_csv(FINDS_FILE)
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            combined_df = new_df
        
        combined_df.to_csv(FINDS_FILE, index=False)
        return True
    except Exception as e:
        st.error(f"Error importing: {e}")
        return False

# ====== END PERSONAL FORAGING LOG FUNCTIONS ======
# ====== BEGIN PAGE UI ARCHITECTURE ======
# Page config
st.set_page_config(page_title="Vermont Foraging App", layout="wide")
# Adjust tab styling, default is too small
st.markdown("""
    <style>
    /* Make tab headers larger */
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 20px;
    }
    
    /* Add more spacing between tabs */
    .stTabs [data-baseweb="tab-list"] button {
        padding: 10px 20px;
    }
    
    /* Make the active tab more prominent */
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# Define tabs to split main page UI components
tab1, tab2 = st.tabs(['🏞️ Explore!', '📓 Forage Recordings'])

tab1.title("🌿 Vermont Edible Species Observations")

# Define nested sidebar structure, where two different expanders hold filters/tools for each tab
with st.sidebar:
    # Explore tab
    with st.expander("🗺️ Explore Filters", expanded=True):
        # Genus filter (multiselect)
        genus_options = sorted(vermont_edibles['genus'].dropna().unique())
        selected_genus = st.multiselect(
            "Select Genus",
            options=genus_options
        )

        st.subheader("🧭 Coordinate Filter")

        use_coord_filter = st.checkbox("Enable Coordinate Filter", value=False)

        if use_coord_filter:
            use_save_coords = st.checkbox('👣 Use Saved Coordinates', value=False)
            
            if use_save_coords:
                # Default 'location' is all of Vermont (i.e. same as page base state)
                select_saved_locations = st.selectbox(
                    'Saved Locations',
                    options=saved_coords['name'].drop_duplicates()
                )
                
                location_coordinates = saved_coords[saved_coords['name'] == select_saved_locations]
                default_min_lat = float(location_coordinates['min_lat'].iloc[0])
                default_max_lat = float(location_coordinates['max_lat'].iloc[0])
                default_min_long = float(location_coordinates['min_long'].iloc[0])
                default_max_long = float(location_coordinates['max_long'].iloc[0])
            else:
                default_min_lat = float(df_filtered['lat'].min())
                default_max_lat = float(df_filtered['lat'].max())
                default_min_long = float(df_filtered['long'].min())
                default_max_long = float(df_filtered['long'].max())
            
            # Show inputs in a little 4x4 box.
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Latitude**")
                min_lat = st.number_input(
                    "Min", 
                    value=default_min_lat, 
                    format="%.4f",
                    key="min_lat"
                )
                max_lat = st.number_input(
                    "Max", 
                    value=default_max_lat, 
                    format="%.4f",
                    key="max_lat"
                )
            
            with col2:
                st.write("**Longitude**")
                min_long = st.number_input(
                    "Min", 
                    value=default_min_long, 
                    format="%.4f",
                    key="min_long"
                )
                max_long = st.number_input(
                    "Max", 
                    value=default_max_long, 
                    format="%.4f",
                    key="max_long"
                )
            # Save coordinates section
            st.subheader("💾 Save Current Coordinates")
            with st.form("save_location_form", clear_on_submit=True):
                location_name = st.text_input('Location Name')
                
                col1, col2 = st.columns(2)
                with col1:
                    cancel = st.form_submit_button('Cancel')
                with col2:
                    save = st.form_submit_button('Save', type='primary')
                
                if save and location_name:
                    # Re-read the CSV to get latest data
                    try:
                        saved_coords_current = pd.read_csv('saved_coords.csv')
                    except FileNotFoundError:
                        saved_coords_current = pd.DataFrame(columns=['name', 'min_lat', 'max_lat', 'min_long', 'max_long'])
                    
                    if location_name not in saved_coords_current['name'].values:
                        new_location = pd.DataFrame([{
                            'name': location_name,
                            'min_lat': min_lat,
                            'max_lat': max_lat,
                            'min_long': min_long,
                            'max_long': max_long
                        }])
                        saved_coords_current = pd.concat([saved_coords_current, new_location], ignore_index=True)
                        saved_coords_current.to_csv("saved_coords.csv", index=False)
                        st.success(f"Location '{location_name}' saved!")
                        st.rerun()
                    else:
                        st.error("Location name already exists")
                
                if cancel:
                    st.rerun()

        st.subheader("🍂 Season Filter")

        unique_seasons = vermont_edibles['season'].drop_duplicates()

        # Add 'current_season' as default
        selected_season = st.multiselect(
            'Select Season',
            options = ['year', 'growing', 'dormant',
                    'spring', 'summer', 'fall', 'winter', 
                    'early_spring', 'mid_spring', 'late_spring',
                    'early_summer', 'mid_summer', 'late_summer',
                    'early_fall', 'late_fall',
                    'early_winter', 'mid_winter', 'late_winter'],
            default=current_season
        )

        st.subheader('🔍 ID Difficulty')
        selected_difficulty = st.slider('Set ID Difficulty', min_value = 1, max_value = 3, value = 2, step = 1)

        st.subheader('🎗️ Conservation Status')
        selected_conservation = st.slider('Set Conservation Status', min_value = 0, max_value = 3, value = 2, step = 1)

        st.subheader("🍴 Edibility")

        selected_edible_rating = st.slider(label = "Select Minimum Edibility Score",
                                                min_value=0,
                                                max_value=3,
                                                value = 0,
                                                step = 1)

        unique_edible_parts = vermont_edibles['plant_part'].drop_duplicates()

        selected_edible_parts = st.multiselect(
            'Select Edible Part(s)',
            options = unique_edible_parts.sort_values(),
            default=None
        )

        st.header('📊 Report Generation')

        # File uploader for map image
        uploaded_map = st.file_uploader(
            "Upload Map Image (optional)", 
            type=['png', 'jpg', 'jpeg'],
            help="Upload the map screenshot you saved using the camera button above"
        )

        report_button = st.button("📊 Generate Forage Report", type="primary")
        
    with st.expander("📝 Personal Log", expanded=False):
        st.text('This is Ben\'s app')

# ====== BEGIN TAB1 MAIN PAGE CODE ======
# Apply filters to vermont_edibles_filt
if selected_genus:
    vermont_edibles_filt = vermont_edibles_filt[vermont_edibles_filt['genus'].isin(selected_genus)]

vermont_edibles_filt = vermont_edibles_filt[vermont_edibles_filt['sayer_rating'] >= selected_edible_rating]

if selected_edible_parts:
    vermont_edibles_filt = vermont_edibles_filt[vermont_edibles_filt['plant_part'].isin(selected_edible_parts)]

# Add associated season(s) based on UI input (i.e. add 'fall' if 'late_fall' selected)
if selected_season:
    # Create expanded season list without modifying the original
    expanded_seasons = []
    for season in selected_season:
        if season == 'year':
            expanded_seasons.extend(unique_seasons.tolist())
        elif season == 'growing':
            expanded_seasons.extend(['early_spring', 'mid_spring', 'late_spring', 
                                    'early_summer', 'mid_summer', 'late_summer', 'early_fall'])
        elif season == 'dormant':
            expanded_seasons.extend(['mid_fall', 'late_fall', 'early_winter', 
                                    'mid_winter', 'late_winter'])
        elif season in ['spring', 'summer', 'fall', 'winter']:
            intra_seasons = [sub_season for sub_season in unique_seasons if season in sub_season]
            expanded_seasons.extend(intra_seasons)
        elif "_" in season:
            base_season = season.split("_")[1]
            expanded_seasons.extend([season, base_season])
        else:
            # Keep the individual season selections too
            expanded_seasons.append(season)
            expanded_seasons.append('year')
    
    # Remove duplicates
    expanded_seasons = list(set(expanded_seasons))

    # Find all entries in vermont edivles with rows EQUAL TO (not contains) values in expanded_seasons
    mask = vermont_edibles_filt['season'].apply(lambda x: any(x == s for s in expanded_seasons))
    vermont_edibles_filt = vermont_edibles_filt[mask]

# Filter by ID difficulty value
vermont_edibles_filt = vermont_edibles_filt[vermont_edibles_filt['id_difficulty'] <= selected_difficulty]

# Filter by conservation value
vermont_edibles_filt = vermont_edibles_filt[vermont_edibles_filt['conservation'] <= selected_conservation]

# If using coordinate filter, remove observations from iNat data
if use_coord_filter:
        # Apply filter
    df_filtered = df_filtered[
        (df_filtered['lat'] >= min_lat) &
        (df_filtered['lat'] <= max_lat) &
        (df_filtered['long'] >= min_long) &
        (df_filtered['long'] <= max_long)
    ]

# Merge observations with the FILTERED list
# Merge by species
vermont_edibles_for_species = vermont_edibles_filt.drop(columns=['genus'])
df_filtered_species = df_filtered.merge(vermont_edibles_for_species, on="scientific_name", how="inner")
# Merge by genus, since not all rows in iNat data have a 'scientific_name'
df_filtered_genus = df_filtered.merge(vermont_edibles_filt, on="genus", how="inner")

# Combine and deduplicate, drop overlap between species/genus merge
presented_df = pd.concat([df_filtered_species, df_filtered_genus]).drop_duplicates(subset="uuid", keep="first")
# Create hover_label for map popups, defaulting to scientific name and then genus
presented_df['hover_label'] = presented_df['scientific_name'].fillna(presented_df['genus'])

# Display stats
col1, col2, col3 = tab1.columns(3)
with col1:
    st.metric("Total Observations", len(presented_df))
with col2:
    st.metric("Unique Species", presented_df['species'].nunique() if 'species' in presented_df.columns else 0)
with col3:
    st.metric("Unique Genera", presented_df['genus'].nunique())

# Create map
if len(presented_df) > 0:
    # Calculate center and zoom based on coordinate filter
    if use_coord_filter:
        # Calculate center point
        center_lat = (min_lat + max_lat) / 2
        center_lon = (min_long + max_long) / 2
        
        # Calculate zoom level based on lat/long range
        lat_range = max_lat - min_lat
        lon_range = max_long - min_long
        max_range = max(lat_range, lon_range)
        
        # Empirical zoom calculation (adjust as needed)
        if max_range > 3:
            zoom_level = 7
        elif max_range > 1:
            zoom_level = 8
        elif max_range > 0.5:
            zoom_level = 10
        elif max_range > 0.2:
            zoom_level = 11
        elif max_range > 0.1:
            zoom_level = 12
        else:
            zoom_level = 13
    else:
        # Default Vermont center
        center_lat = 44.0
        center_lon = -72.7
        zoom_level = 7

    # Create map
    fig = px.scatter_mapbox(
        presented_df,
        lat='lat',
        lon='long',
        color='genus',
        hover_name='hover_label',
        hover_data={
            'common_name': True,
            'genus': True,
            'lat': ':.4f',
            'long': ':.4f'
        },
        zoom=zoom_level,
        height=600,
        title="Species Observations in Vermont"
    )
    
    # Update map center and zoom
    fig.update_layout(
        mapbox_style="open-street-map",
        mapbox=dict(
            center=dict(lat=center_lat, lon=center_lon),
            zoom=zoom_level
        ),
        margin={"r": 0, "t": 40, "l": 0, "b": 0}
    )
    
    tab1.plotly_chart(fig, use_container_width=True)
    
    # Show data table
    tab1.subheader("Filtered Data")
    
    # Select columns to display
    display_cols = ['scientific_name', 'common_name', 'genus', 'season', 'lat', 'long']
    if 'quality_grade' in presented_df.columns:
        display_cols.append('quality_grade')
    
    # Filter to only existing columns
    display_cols = [col for col in display_cols if col in presented_df.columns]
    
    tab1.dataframe(
        presented_df[display_cols].reset_index(drop=True),
        use_container_width=True,
        height=400
    )
    
    # Download button
    csv = presented_df.to_csv(index=False)
    tab1.download_button(
        label="Download Filtered Data as CSV",
        data=csv,
        file_name="filtered_species_data.csv",
        mime="text/csv"
    )

    # Add this function before the report generation button
    def generate_html_report(presented_df, expanded_seasons, species_counts, genus_counts, species_table, uploaded_map=None):
        """Generate HTML report with embedded images"""
        
        # Convert charts to HTML
        spec_plot = px.bar(
            species_counts,
            y='Species',
            x='Count',
            orientation='h',
            title='Species Observations'
        )
        spec_plot.update_layout(
            height=max(400, len(species_counts) * 20),
            yaxis={'categoryorder': 'total ascending'}
        )
        
        genus_plot = px.bar(
            genus_counts,
            y='Genus',
            x='Count',
            orientation='h',
            title='Genus Observations'
        )
        genus_plot.update_layout(
            height=max(400, len(genus_counts) * 20),
            yaxis={'categoryorder': 'total ascending'}
        )
        
        # Build HTML
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Vermont Forage Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                h1 {{ color: #2e7d32; }}
                h2 {{ color: #4caf50; margin-top: 30px; }}
                .metric {{ display: inline-block; margin: 20px; padding: 15px; background: #f5f5f5; border-radius: 5px; }}
                .metric-value {{ font-size: 24px; font-weight: bold; }}
                .metric-label {{ font-size: 14px; color: #666; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #4caf50; color: white; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
                img {{ max-width: 100%; height: auto; }}
            </style>
        </head>
        <body>
            <h1>🌿 Vermont Forage Report</h1>
            <p><strong>Generated:</strong> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
            <p><strong>Season:</strong> {', '.join(expanded_seasons)}</p>
            
            <h2>Summary Statistics</h2>
            <div class="metric">
                <div class="metric-value">{len(presented_df)}</div>
                <div class="metric-label">Total Observations</div>
            </div>
            <div class="metric">
                <div class="metric-value">{presented_df['scientific_name'].nunique()}</div>
                <div class="metric-label">Unique Species</div>
            </div>
            <div class="metric">
                <div class="metric-value">{presented_df['genus'].nunique()}</div>
                <div class="metric-label">Unique Genera</div>
            </div>
        """
        
        # Add map if provided
        if uploaded_map:
            uploaded_map.seek(0)
            img_base64 = base64.b64encode(uploaded_map.read()).decode()
            html += f"""
            <h2>Map of Observations</h2>
            <img src="data:image/png;base64,{img_base64}" alt="Observation Map">
            """
        
        # Add charts
        html += f"""
            <h2>Species Counts</h2>
            {spec_plot.to_html(include_plotlyjs='cdn', full_html=False)}
            
            <h2>Genus Counts</h2>
            {genus_plot.to_html(include_plotlyjs='cdn', full_html=False)}
            
            <h2>Detailed Species List</h2>
            {species_table.to_html(index=False)}
            
        </body>
        </html>
        """
        
        return html

    # Replace the report generation button section with this:
    if report_button:
        with st.spinner("Generating report..."):
            
            st.markdown("---")
            st.title("🌿 Forage Report")
            
            # Header info
            st.write(f"**Generated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
            st.write(f"**Season:** {expanded_seasons}")
            st.write(f'**Max ID Difficulty:** {selected_difficulty}')
            
            # Summary stats
            st.header("Summary Statistics")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Observations", len(presented_df))
            with col2:
                st.metric("Unique Species", presented_df['scientific_name'].nunique())
            with col3:
                st.metric("Unique Genera", presented_df['genus'].nunique())
            
            # Map if uploaded
            if uploaded_map:
                st.header("Map of Observations")
                uploaded_map.seek(0)
                st.image(uploaded_map, use_container_width=True)
            
            # Species chart
            st.header("Species Counts")
            species_counts = presented_df['scientific_name'].value_counts().reset_index()
            species_counts.columns = ['Species', 'Count']
            
            spec_plot = px.bar(
                species_counts,
                y='Species',
                x='Count',
                orientation='h',
                title='Species Observations'
            )
            spec_plot.update_layout(
                height=max(400, len(species_counts) * 20),
                yaxis={'categoryorder': 'total ascending'}
            )
            st.plotly_chart(spec_plot, use_container_width=True)
            
            # Genus chart
            st.header("Genus Counts")
            genus_counts = presented_df['genus'].value_counts().reset_index()
            genus_counts.columns = ['Genus', 'Count']
            
            genus_plot = px.bar(
                genus_counts,
                y='Genus',
                x='Count',
                orientation='h',
                title='Genus Observations'
            )
            genus_plot.update_layout(
                height=max(400, len(genus_counts) * 20),
                yaxis={'categoryorder': 'total ascending'}
            )
            st.plotly_chart(genus_plot, use_container_width=True)
            
            # Species table
            st.header("Detailed Species List")
            counts = presented_df['scientific_name'].value_counts().reset_index()
            counts.columns = ['Scientific Name', 'Count']
            all_edible_parts = presented_df.groupby(['scientific_name', 'season', 'sayer_rating'])['plant_part'].apply(
                lambda x: ', '.join(sorted(x.unique()))
            ).reset_index()
            all_edible_parts.columns = ['Scientific Name', 'Season',"Sayer Rating", 'Edible Parts']
            species_table = counts.merge(
                presented_df[['scientific_name', 'common_name', 'genus', 'page_number']].drop_duplicates(),
                left_on='Scientific Name',
                right_on='scientific_name',
                how='left'
            )[['Scientific Name', 'common_name', 'genus', 'page_number', 'Count']]
            species_table = species_table.merge(all_edible_parts, on = 'Scientific Name', how = 'left')
            species_table.columns = ['Scientific Name', 'Common Name', 'Genus', 'Page Number', 'Count', 'Season', 'Sayer Rating', 'Edible Parts']
            st.dataframe(species_table, use_container_width=True)
            
            st.success("✅ Report generated!")
            
            # Generate and offer download
            html_report = generate_html_report(
                presented_df, 
                expanded_seasons, 
                species_counts, 
                genus_counts, 
                species_table, 
                uploaded_map
            )
            
            st.download_button(
                label="📥 Download Report as HTML",
                data=html_report,
                file_name=f"forage_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                mime="text/html",
                type="primary"
            )
else:
    tab1.warning("No observations match the selected filters. Please adjust your selections.")

# ====== END EXPLORE TAB MAIN PAGE CODE ======

# ====== BEING FORAGE JOURNAL MAIN PAGE CODE ======
with tab2:
    st.header("📝 My Personal Foraging Log")
    
    personal_finds = load_personal_finds()
    
    if personal_finds:
        # Summary stats
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Finds", len(personal_finds))
        with col2:
            unique_species = len(set(f['species'] for f in personal_finds))
            st.metric("Unique Species", unique_species)
        with col3:
            avg_rating = sum(f['rating'] for f in personal_finds) / len(personal_finds)
            st.metric("Avg Rating", f"{avg_rating:.1f}/5")
        with col4:
            current_year_finds = len([f for f in personal_finds if f['date'].startswith(str(datetime.now().year))])
            st.metric("Finds This Year", current_year_finds)
        
        # Map of personal finds
        st.subheader("Map of My Finds")
        personal_df = pd.DataFrame(personal_finds)
        personal_df['lat'] = pd.to_numeric(personal_df['lat'], errors='coerce')
        personal_df['lon'] = pd.to_numeric(personal_df['lon'], errors='coerce')
        personal_df = personal_df.dropna(subset=['lat', 'lon'])
        
        if len(personal_df) > 0:
            fig = px.scatter_mapbox(
                personal_df,
                lat='lat',
                lon='lon',
                hover_name='species',
                hover_data={'common_name': True, 'date': True, 'rating': True, 'quantity': True},
                color='rating',
                color_continuous_scale='Viridis',
                zoom=7,
                height=500
            )
            fig.update_layout(
                mapbox_style="open-street-map",
                mapbox=dict(center=dict(lat=44.0, lon=-72.7)),
                margin={"r": 0, "t": 0, "l": 0, "b": 0}
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Add new find form
        st.subheader("➕ Add New Find")
        with st.form("add_personal_find_tab2", clear_on_submit=True):
            # Create species to common name lookup
            species_to_common = dict(zip(vermont_edibles['scientific_name'].dropna(), 
                                        vermont_edibles['sayer_name'].fillna('')))
            
            col1, col2 = st.columns(2)
            with col1:
                species_list = sorted(vermont_edibles['scientific_name'].dropna().unique())
                selected_species = st.selectbox("Species", options=species_list, key="tab2_species")
                find_common_name = species_to_common.get(selected_species, "")
                find_date = st.date_input("Date Found", value=datetime.now(), key="tab2_date")
            with col2:
                find_lat = st.number_input("Latitude", format="%.6f", value=44.0, key="tab2_lat")
                find_lon = st.number_input("Longitude", format="%.6f", value=-72.7, key="tab2_lon")
                find_rating = st.slider("Quality Rating", 0, 5, 3, key="tab2_rating")
            
            find_quantity = st.text_input("Quantity", placeholder="e.g., 2 lbs, 50+ individuals", key="tab2_qty")
            find_notes = st.text_area("Notes", placeholder="Dense patch near oak trees, south-facing slope...", key="tab2_notes")
            
            if st.form_submit_button("💾 Save Find", type="primary"):
                save_personal_find(
                    selected_species, find_common_name, find_date, 
                    find_lat, find_lon, find_notes, find_quantity, find_rating
                )
                st.success("Find saved!")
                st.rerun()
        
        # List of all finds
        st.subheader("📋 All My Finds")
        
        # Sort options
        sort_by = st.selectbox("Sort by", ["Date (Newest First)", "Date (Oldest First)", "Species", "Rating"])
        
        if sort_by == "Date (Newest First)":
            personal_finds_sorted = sorted(personal_finds, key=lambda x: x['date'], reverse=True)
        elif sort_by == "Date (Oldest First)":
            personal_finds_sorted = sorted(personal_finds, key=lambda x: x['date'])
        elif sort_by == "Species":
            personal_finds_sorted = sorted(personal_finds, key=lambda x: x['species'])
        else:  # Rating
            personal_finds_sorted = sorted(personal_finds, key=lambda x: x['rating'], reverse=True)
        
        for idx, find in enumerate(personal_finds_sorted):
            # Find original index for deletion
            original_idx = personal_finds.index(find)
            
            with st.expander(f"⭐ {find['species']} - {find['date']}", expanded=False):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**Common Name:** {find['common_name']}")
                    st.markdown(f"**Date:** {find['date']}")
                    st.markdown(f"**Location:** {find['lat']:.4f}, {find['lon']:.4f}")
                    st.markdown(f"**Rating:** {'⭐' * find['rating']} ({find['rating']}/5)")
                    if find['quantity']:
                        st.markdown(f"**Quantity:** {find['quantity']}")
                    if find['notes']:
                        st.markdown(f"**Notes:** {find['notes']}")
                    st.caption(f"*Added: {find['added_on']}*")
                
                with col2:
                    if st.button(f"🗑️ Delete", key=f"del_tab2_{original_idx}"):
                        delete_personal_find(original_idx)
                        st.rerun()
        
        # Export/Import
        st.subheader("💾 Export/Import")
        col1, col2 = st.columns(2)
        
        with col1:
            csv_data = export_personal_finds()
            if csv_data:
                st.download_button(
                    "📥 Export My Finds to CSV",
                    data=csv_data,
                    file_name=f"my_foraging_log_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        
        with col2:
            uploaded_finds = st.file_uploader("📤 Import Finds from CSV", type=['csv'], key="tab2_import")
            if uploaded_finds and st.button("Import", use_container_width=True, key="tab2_import_btn"):
                if import_personal_finds(uploaded_finds):
                    st.success("Finds imported!")
                    st.rerun()
    
    else:
        st.info("🌱 No personal finds yet! Soon the wilds will know my presence.")
        
        # Show add find form even when empty
        st.subheader("➕ Add Your First Find")
        with st.form("add_first_find", clear_on_submit=True):
            species_to_common = dict(zip(vermont_edibles['scientific_name'].dropna(), 
                                        vermont_edibles['sayer_name'].fillna('')))
            
            col1, col2 = st.columns(2)
            with col1:
                species_list = sorted(vermont_edibles['scientific_name'].dropna().unique())
                selected_species = st.selectbox("Species", options=species_list, key="first_species")
                find_common_name = species_to_common.get(selected_species, "")
                find_date = st.date_input("Date Found", value=datetime.now(), key="first_date")
            
            with col2:
                find_lat = st.number_input("Latitude", format="%.6f", value=44.0, key="first_lat")
                find_lon = st.number_input("Longitude", format="%.6f", value=-72.7, key="first_lon")
                find_rating = st.slider("Quality Rating", 1, 5, 3, key="first_rating")
            
            find_quantity = st.text_input("Quantity", placeholder="e.g., 2 lbs, 50+ individuals", key="first_qty")
            find_notes = st.text_area("Notes", placeholder="Dense patch near oak trees, south-facing slope...", key="first_notes")
            
            if st.form_submit_button("💾 Save Find", type="primary"):
                save_personal_find(
                    selected_species, find_common_name, find_date, 
                    find_lat, find_lon, find_notes, find_quantity, find_rating
                )
                st.success("Find saved!")
                st.rerun()

# ====== END FORAGE JOURNAL MAIN PAGE CODE ======