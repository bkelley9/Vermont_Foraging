import requests
import time
import pandas as pd
import json
import os

vermont_edibles = pd.read_csv("vermont_edibles.csv")

species = vermont_edibles['scientific_name'].drop_duplicates().to_list()

def get_taxon_ids_for_species(species_name):
    """Get all taxon IDs matching a species name"""
    url = "https://api.inaturalist.org/v1/taxa"
    params = {'q': species_name}
    
    response = requests.get(url, params=params)
    data = response.json()
    results = data.get('results', [])
    
    # Extract IDs
    ids = [taxon['id'] for taxon in results]
    return ids

def get_all_vermont_observations(taxon_id, place_id=47):
    """Get all observations for a taxon in Vermont"""
    base_url = "https://api.inaturalist.org/v1/observations"
    all_observations = []
    page = 1
    
    while True:
        params = {
            'taxon_id': taxon_id,
            'place_id': place_id,
            'per_page': 200,
            'page': page,
            'quality_grade': 'research,needs_id',
            'captive': 'false',
            'geo': 'true'
        }
        
        response = requests.get(base_url, params=params)
        
        if response.status_code != 200:
            print(f"Error: Status code {response.status_code}")
            break
        
        data = response.json()
        results = data.get('results', [])
        
        all_observations.extend(results)
        
        print(f"  Page {page}: Retrieved {len(results)} observations")
        
        if len(results) < 200:
            break
        
        page += 1
        time.sleep(1)
    
    print(f"Total observations retrieved: {len(all_observations)}")
    return all_observations

def save_species_data(species_name, observations_dict, save_dir='species_data'):
    """
    Save raw observations data as JSON
    observations_dict: {taxon_id: [observations]}
    """
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    # Clean species name for filename
    safe_name = species_name.replace(' ', '_').replace('/', '_')
    filepath = os.path.join(save_dir, f'{safe_name}.json')
    
    with open(filepath, 'w') as f:
        json.dump(observations_dict, f)
    
    total_obs = sum(len(obs) for obs in observations_dict.values())
    print(f"✓ Saved {total_obs} observations for {species_name}")

def load_species_data(save_dir='species_data'):
    """Load all previously saved species data"""
    all_data = {}
    
    if not os.path.exists(save_dir):
        return all_data
    
    for filename in os.listdir(save_dir):
        if filename.endswith('.json'):
            species_name = filename.replace('.json', '').replace('_', ' ')
            filepath = os.path.join(save_dir, filename)
            with open(filepath, 'r') as f:
                all_data[species_name] = json.load(f)
    
    return all_data

def download_all_species(species_list, save_dir='species_data'):
    """Download observations for all species, resuming if interrupted"""
    
    # Check what's already downloaded
    existing_files = set()
    if os.path.exists(save_dir):
        existing_files = {f.replace('.json', '').replace('_', ' ') 
                         for f in os.listdir(save_dir) if f.endswith('.json')}
    
    print(f"Already have data for {len(existing_files)} species")
    print(f"Need to download {len(species_list) - len(existing_files)} species")
    
    for i, species in enumerate(species_list, 1):
        # Skip if already downloaded
        if species in existing_files:
            print(f"[{i}/{len(species_list)}] Skipping {species} (already downloaded)")
            continue
        
        print(f"\n{'='*50}")
        print(f"[{i}/{len(species_list)}] Processing species: {species}")
        print(f"{'='*50}")
        
        try:
            # Get all taxon IDs for this species
            print(f"Looking up taxon IDs for '{species}'...")
            taxon_ids = get_taxon_ids_for_species(species)
            print(f"Found {len(taxon_ids)} taxon IDs: {taxon_ids}")
            
            if not taxon_ids:
                print(f"⚠️  No taxon IDs found for {species}, skipping...")
                continue
            
            # Collect observations for all taxon IDs
            all_observations_for_species = {}
            
            for taxon_id in taxon_ids:
                print(f"\nQuerying observations for taxon ID: {taxon_id}")
                observations = get_all_vermont_observations(taxon_id)
                all_observations_for_species[str(taxon_id)] = observations
            
            # Save raw JSON data
            save_species_data(species, all_observations_for_species, save_dir)
            
            total_obs = sum(len(obs) for obs in all_observations_for_species.values())
            print(f"\n✓ Completed {species}: {total_obs} total observations")
            
            # Progress update
            print(f"\nProgress: {i}/{len(species_list)} ({i/len(species_list)*100:.1f}%)")
            remaining_species = len(species_list) - i
            print(f"Estimated species remaining: {remaining_species}")
            
        except Exception as e:
            print(f"❌ Error with species {species}: {e}")
            import traceback
            traceback.print_exc()
            continue
        
download_all_species(species)