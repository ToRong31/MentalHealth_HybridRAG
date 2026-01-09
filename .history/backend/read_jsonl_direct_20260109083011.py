"""
Direct retrieval from JSONL file
"""
import json

jsonl_file = "/app/data/raw/mental_health_diagnostic_support.jsonl"

query_text = "There is often a localized uncomfortable sensation (premonitory sensation) prior to a tic, and most individuals report an \"urge\" to tic."

print("="*80)
print("🔍 SEARCHING IN JSONL FILE")
print("="*80)
print(f"File: {jsonl_file}")
print(f"Query: {query_text}")
print()

# Node IDs from Milvus search
node_ids = [1744, 1750, 1751, 1747, 1748]

print(f"Looking for node IDs: {node_ids}\n")
print("="*80)

found_count = 0
with open(jsonl_file, 'r', encoding='utf-8') as f:
    for line_num, line in enumerate(f, 1):
        if line.strip():
            try:
                item = json.loads(line)
                chunk_id = item.get("chunk_id")
                
                # Convert to int for comparison
                if chunk_id and int(chunk_id) in node_ids:
                    found_count += 1
                    print(f"\n✅ FOUND (Line {line_num})")
                    print(f"Chunk ID: {chunk_id}")
                    print(f"Title: {item.get('title', 'N/A')}")
                    print(f"Section: {item.get('section_type', 'N/A')}")
                    print(f"Text: {item.get('text', 'N/A')}")
                    print("-"*80)
                    
            except Exception as e:
                print(f"Error parsing line {line_num}: {e}")

print(f"\n✅ Found {found_count} / {len(node_ids)} nodes")
print("="*80)
