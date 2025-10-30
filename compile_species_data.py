import requests
import time
import pandas as pd
import json
import os
import pickle

species_dirs = os.listdir("species_data")

def load_single_species(species = "Acorus.json"):
    species_data = []

    path = os.path.join("species_data", species)

    if not os.path.exists(path):
        return species_data
    
    if species.endswith('.json'):
        with open(path, 'r') as f:
            species_data = json.load(f)
    
    return species_data

master = {}

for species in species_dirs:
    print(f'Loading {species} from json files...\n')
    species_data = load_single_species(species)
    
    all_dfs = []

    for id in species_data:
        df = pd.DataFrame(species_data[id])
        
        # Check if empty
        if df.empty:
            print(f"No observations for taxon {id}")
            continue
        
        print(f"Processing taxon {id}: {len(df)} observations")
        
        # Add derived columns
        df['scientific_name'] = df['taxon'].apply(lambda x: x.get('name') if x else None)
        df['genus'] = df['scientific_name'].str.split(" ", expand=True)[0]

        df['common_name'] = df['taxon'].apply(lambda x: x.get('preferred_common_name') if x else None)
        
        # Add taxon_id BEFORE selecting columns
        df['taxon_id'] = id  # Use 'taxon_id' instead of 'id' to avoid confusion
        
        # Split location
        if 'location' in df.columns:
            df[['lat', 'long']] = df['location'].str.split(',', expand=True)
        
        # NOW select columns (including the ones you just added)
        cols = ['uuid', 'scientific_name', 'genus' ,'common_name', 'quality_grade', 
                'time_observed_at', 'location', 'description', 'taxon_id', 'lat', 'long']
        
        # Only keep columns that exist
        existing_cols = [col for col in cols if col in df.columns]
        df = df[existing_cols]
        
        all_dfs.append(df)

    # Combine all
    if all_dfs:
        all_df = pd.concat(all_dfs, ignore_index=True)

    # Define filtering rules for each genus
    genus_filters = {
        # Genera that filter by genus name only
        'genus_only': ['Acorus', 'Amaranthus', 'Amelanchier', 'Atriplex', 'Claytonia', 
                    'Crataegus', 'Erythronium', 'Fragaria', 'Galinsoga', 'Impatiens', 
                    'Lilium', 'Mentha', 'Nuphar', 'Persicaria', 'Picea', 'Pinus', 
                    'Rosa', 'Rubus', 'Sanicula', 'Tradescantia', 'Tragopogon', 
                    'Trillium', 'Typha', 'Vitis', 'Yucca'],
        
        # Genera that filter by common name keywords
        'common_name': {
            'Chenopodium': 'lamb|goose|spinach|pig',
            'Fallopia': 'bindweed|buckwheat',
            'Lycopus': 'bugleweed',
            'Malus': 'crab|wild',
            'Muscari': 'hyacinth',
            'Physalis': 'cherry',
            'Pycnanthemum': 'hoary|whorled|narrow|clustered',
            'Ribes': 'goose',
            'Rubus': 'blackberry|dewberry|dewberries',
            'Smilax': 'green|carrion',
            'Vaccinium': 'cranberry|cranberries'
        }
    }

    # Apply the appropriate filter
    if species in genus_filters['genus_only']:
        all_df = all_df[all_df['genus'].str.contains(species, na=False)]
    elif species in genus_filters['common_name']:
        keywords = genus_filters['common_name'][species]
        all_df = all_df[all_df['common_name'].str.contains(keywords, case=False, na=False)]


        all_df = all_df.drop_duplicates(subset='uuid', keep='first')

        all_df = all_df.dropna(subset = "time_observed_at")

        master[species.removesuffix('.json')] = all_df

        print(f"\nTotal observations: {len(all_df)}")
    else:
        all_df = all_df.drop_duplicates(subset='uuid', keep='first')

        all_df = all_df.dropna(subset = "time_observed_at")

        master[species.removesuffix('.json')] = all_df

        print(f"\nTotal observations: {len(all_df)}")
        continue

with open('master_data.pkl', 'wb') as f:
    pickle.dump(master, f)
