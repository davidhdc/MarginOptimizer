"""
Configuration module for Margin Optimizer
Loads environment variables and defines business constants
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Quickbase Configuration
QUICKBASE_REALM = os.getenv('QUICKBASE_REALM', 'ignetworks.quickbase.com')
QUICKBASE_TOKEN = os.getenv('QUICKBASE_TOKEN', 'b9kfn9_w4i_0_da9fbrhdqjiq9qe2pgcfkxcwpu')
QUICKBASE_TABLE_ID = os.getenv('QUICKBASE_TABLE_ID', 'bqrc5mm8e')
QUICKBASE_BASE_URL = f'https://{QUICKBASE_REALM}'

# API VPLs Configuration
VPL_API_BASE_URL = os.getenv('VPL_API_BASE_URL', 'https://igiq-api.ignetworks.com')
VPL_API_TOKEN = os.getenv('VPL_API_TOKEN', '809d6821ee9e60fcaa78347e71b61c59e6c94197')

# Neo4j Configuration (from DH - Quotes Identifier)
NEO4J_URI = os.getenv('NEO4J_URI', 'neo4j+s://00d3ff26.databases.neo4j.io')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'bR3rStkBnA9vSZxCPnrnaKvPbwLvLsJFc67N')
NEO4J_DATABASE = os.getenv('NEO4J_DATABASE', 'neo4j')

# Business Constants
TARGET_GM = float(os.getenv('TARGET_GM', '0.55'))  # 55%
MIN_ACCEPTABLE_GM = float(os.getenv('MIN_ACCEPTABLE_GM', '0.50'))  # 50%

# Quickbase Field IDs (to be determined from API exploration)
QUICKBASE_FIELDS = {
    'associated_id': 3,  # Service ID
    'currency': 6,
    'initial_mrc_usd': 7,
    'initial_mrc_local': 8,
    'final_discount': 9,
    'vendor_name': 10,
    'date_created': 11
}

# API Endpoints
VPL_LIST_ENDPOINT = '/api/procurement/vendorpricelist/list/'

# Analysis Parameters
DEFAULT_LOOKBACK_MONTHS = 12
DEFAULT_BANDWIDTH_TOLERANCE = 0.20  # ±20%
VQ_LOOKBACK_MONTHS = 6
