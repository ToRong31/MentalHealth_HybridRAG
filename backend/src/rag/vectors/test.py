"""
Script to inspect Milvus collections and their fields
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from pymilvus import connections, utility, Collection
from src.rag.config import rag_settings
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def connect_to_milvus():
    """Connect to Milvus"""
    connection_params = {
        "alias": "default",
        "uri": rag_settings.MILVUS_URI,
        "db_name": rag_settings.MILVUS_DB,
    }
    
    if rag_settings.MILVUS_TOKEN and rag_settings.MILVUS_TOKEN.strip():
        connection_params["token"] = rag_settings.MILVUS_TOKEN
        connection_params["secure"] = True
    else:
        connection_params["secure"] = False
    
    connections.connect(**connection_params)
    logger.info("✅ Connected to Milvus")


def inspect_collection(collection_name: str):
    """Inspect a single collection"""
    logger.info("\n" + "=" * 80)
    logger.info(f"📊 Collection: {collection_name}")
    logger.info("=" * 80)
    
    try:
        col = Collection(collection_name)
        
        # Get schema
        schema = col.schema
        logger.info(f"\n📝 Description: {schema.description}")
        logger.info(f"📈 Total entities: {col.num_entities}")
        
        # List all fields
        logger.info(f"\n🔍 Fields ({len(schema.fields)}):")
        for field in schema.fields:
            field_info = f"  • {field.name} ({field.dtype.name})"
            
            if field.is_primary:
                field_info += " [PRIMARY KEY]"
            if field.auto_id:
                field_info += " [AUTO_ID]"
            
            # Add dimension for vector fields
            if hasattr(field, 'params') and 'dim' in field.params:
                field_info += f" [dim={field.params['dim']}]"
            
            # Add max_length for varchar fields
            if hasattr(field, 'params') and 'max_length' in field.params:
                field_info += f" [max_length={field.params['max_length']}]"
            
            if field.description:
                field_info += f"\n    Description: {field.description}"
            
            logger.info(field_info)
        
        # Check indexes
        logger.info(f"\n🔧 Indexes:")
        indexes = col.indexes
        if indexes:
            for idx in indexes:
                logger.info(f"  • Field: {idx.field_name}")
                logger.info(f"    Type: {idx.params.get('index_type', 'N/A')}")
                logger.info(f"    Metric: {idx.params.get('metric_type', 'N/A')}")
                logger.info(f"    Params: {idx.params.get('params', {})}")
        else:
            logger.info("  No indexes found")
        
        # Load collection and show sample data
        col.load()
        logger.info(f"\n📄 Sample data (first 3 records):")
        
        # Get field names (exclude vector fields for display)
        field_names = [f.name for f in schema.fields if f.dtype.name != "FLOAT_VECTOR"]
        
        results = col.query(
            expr="node_id >= 0",
            output_fields=field_names,
            limit=3
        )
        
        if results:
            for i, record in enumerate(results, 1):
                logger.info(f"\n  Record {i}:")
                for key, value in record.items():
                    # Truncate long strings
                    if isinstance(value, str) and len(value) > 100:
                        value = value[:100] + "..."
                    logger.info(f"    {key}: {value}")
        else:
            logger.info("  No data found")
        
    except Exception as e:
        logger.error(f"❌ Error inspecting collection {collection_name}: {e}")


def list_all_collections():
    """List all collections in Milvus"""
    logger.info("\n" + "=" * 80)
    logger.info("📚 All Collections in Milvus")
    logger.info("=" * 80)
    
    collections = utility.list_collections()
    if not collections:
        logger.info("No collections found")
        return []
    
    logger.info(f"\nFound {len(collections)} collection(s):")
    for i, name in enumerate(collections, 1):
        logger.info(f"  {i}. {name}")
    
    return collections


def main():
    """Main function"""
    try:
        connect_to_milvus()
        
        # List all collections
        collections = list_all_collections()
        
        # Inspect each collection
        for collection_name in collections:
            inspect_collection(collection_name)
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ Inspection complete!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()