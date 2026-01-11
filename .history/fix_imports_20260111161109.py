import os
import re

directory = r'd:\MINHTRIET\Y3\KiThuatLapTrinhAI\MentalHealth\Code\MentalHealth_HybridRAG\frontend\src\components'

pattern = re.compile(r'from\s+["\']([^"\']+)@\d+\.\d+\.\d+["\']')

for root, dirs, files in os.walk(directory):
    for file in files:
        if file.endswith('.tsx') or file.endswith('.ts'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            new_content = pattern.sub(r'from "\1"', content)
            
            if content != new_content:
                print(f"Fixing imports in {filepath}")
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
