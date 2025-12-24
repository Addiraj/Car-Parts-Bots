from curl_cffi import requests
from fuzzywuzzy import process
import json
 
class BMWPartsFinder:
    def __init__(self):
        self.headers = {
            'authority': 'bmw.7zap.com',
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36',
            'referer': 'https://bmw.7zap.com/',
            'x-requested-with': 'XMLHttpRequest',
            'origin': 'https://bmw.7zap.com'
        }
        self.tree_cache = {}
 
    def _fetch_json(self, url):
        """Helper to safely fetch JSON from the API"""
        try:
            response = requests.get(url, headers=self.headers, impersonate="chrome110", timeout=15)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"[BMW API Error] Status Code: {response.status_code}")
        except Exception as e:
            print(f"[BMW API Exception] {e}")
        return None
 
    def get_catalog_tree(self, vin):
        """Fetches the vehicle categories (Engine, Brakes, etc.) for a VIN"""
        if vin in self.tree_cache:
            return self.tree_cache[vin]
 
        url = f"https://bmw.7zap.com/api/catalog/vin_tree?language=en&vin={vin}&modification_number=0"
        data = self._fetch_json(url)
       
        if data:
            self.tree_cache[vin] = data
        return data
 
    def find_node_id_by_name(self, tree_data, search_query):
        """Finds the Diagram ID using Fuzzy Matching (e.g. 'Oil Filter' -> 'Oil filter element')"""
        all_nodes = {}
       
        # Flatten the complex JSON tree into a simple dictionary { "Part Name": "Node ID" }
        def traverse(data):
            if isinstance(data, dict):
                if 'id' in data and 'name' in data:
                    all_nodes[data['name']] = data['id']
                for key in ['tree', 'children', 'nodes']:
                    if key in data:
                        traverse(data[key])
            elif isinstance(data, list):
                for item in data:
                    traverse(item)
 
        traverse(tree_data)
 
        if not all_nodes:
            return None, None
 
        # Fuzzy match to handle typos or slight name variations
        best_match = process.extractOne(search_query, all_nodes.keys())
       
        # We require a 60% match confidence
        if best_match and best_match[1] > 60:
            found_name = best_match[0]
            found_id = all_nodes[found_name]
            return found_id, found_name
       
        return None, None
 
    def get_parts(self, vin, node_id):
        """Fetches the specific part numbers for a single diagram"""
        url = f"https://bmw.7zap.com/api/catalog/vin_parts_by_id?language=en&vin={vin}&node_id={node_id}&modification_number=0"
        return self._fetch_json(url)
 
    def search_part(self, vin, part_query):
        """
        MASTER FUNCTION
        Returns: { "diagram": "Name", "oem_numbers": ['1112...', '1134...'] }
        """
        # 1. Get Tree
        tree = self.get_catalog_tree(vin)
        if not tree or 'tree' not in tree:
            print("[BMWPartsFinder] Could not retrieve catalog tree.")
            return {"error": "Could not identify vehicle. Please check the VIN."}
 
        # 2. Find Diagram
        node_id, node_name = self.find_node_id_by_name(tree, part_query)
        if not node_id:
            print(f"[BMWPartsFinder] No matching category for '{part_query}'")
            return {"error": f"I couldn't find a category matching '{part_query}' for this vehicle."}
 
        # 3. Get Parts
        parts_data = self.get_parts(vin, node_id)
        found_oem_numbers = []
       
        if parts_data and 'parts' in parts_data:
            for p in parts_data['parts']:
                # Extract the part code
                if p.get('type') == 'part' and p.get('part_code'):
                    found_oem_numbers.append(p.get('part_code'))
       
        return {
            "diagram": node_name,
            "oem_numbers": list(set(found_oem_numbers)) # Remove duplicates using set()
        }
 