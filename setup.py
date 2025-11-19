"""
Setup Script for Knowledge Graph Builder
Run this to quickly set up your environment
"""
import os
import shutil
import sys


def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def check_directory_structure():
    """Check and create necessary directories"""
    print_header("Checking Directory Structure")
    
    directories = ["Input", "Output"]
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"✓ Created directory: {directory}/")
        else:
            print(f"✓ Directory exists: {directory}/")


def setup_input_files():
    """Setup input files from examples"""
    print_header("Setting Up Input Files")
    
    # Setup api.txt
    api_example = "Input/api.txt.example"
    api_file = "Input/api.txt"
    
    if not os.path.exists(api_file):
        if os.path.exists(api_example):
            shutil.copy(api_example, api_file)
            print(f"✓ Created {api_file} from example")
            print(f"  ⚠️  IMPORTANT: Edit {api_file} and add your Google API keys!")
        else:
            print(f"✗ Warning: {api_example} not found")
    else:
        print(f"✓ {api_file} already exists")
    
    # Setup input.json
    input_example = "Input/input.json.example"
    input_file = "Input/input.json"
    
    if not os.path.exists(input_file):
        if os.path.exists(input_example):
            shutil.copy(input_example, input_file)
            print(f"✓ Created {input_file} from example")
            print(f"  ⚠️  IMPORTANT: Edit {input_file} and add your actual data!")
        else:
            print(f"✗ Warning: {input_example} not found")
    else:
        print(f"✓ {input_file} already exists")


def check_dependencies():
    """Check if required packages are installed"""
    print_header("Checking Dependencies")
    
    required_packages = [
        "langchain",
        "langchain_google_genai",
        "google.generativeai"
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace("-", "_").replace(".", "_"))
            print(f"✓ {package} is installed")
        except ImportError:
            print(f"✗ {package} is NOT installed")
            missing_packages.append(package)
    
    if missing_packages:
        print("\n⚠️  Missing packages detected!")
        print("Run this command to install:")
        print("    pip install -r requirements.txt")
        return False
    
    return True


def print_next_steps():
    """Print next steps for user"""
    print_header("Setup Complete! Next Steps")
    
    print("""
1. Edit Input/api.txt:
   - Add your Google API keys (one per line)
   - Get keys from: https://makersuite.google.com/app/apikey

2. Edit Input/input.json:
   - Add your mental health data
   - Format: [{"id": 1, "answer": "..."}]

3. Run the application:
   - python build_graph.py

4. Check Output directory:
   - Output/nodes.csv - Extracted nodes
   - Output/edges.csv - Extracted relationships

For detailed instructions, see:
- QUICKSTART.md - Quick start guide
- README.md - Full documentation
- PROJECT_STRUCTURE.md - Directory structure
    """)


def main():
    """Main setup function"""
    print_header("Knowledge Graph Builder - Setup")
    print("This script will help you set up your environment")
    
    try:
        # Check directory structure
        check_directory_structure()
        
        # Setup input files
        setup_input_files()
        
        # Check dependencies
        deps_ok = check_dependencies()
        
        # Print next steps
        print_next_steps()
        
        if not deps_ok:
            print("⚠️  Please install dependencies before running the application.")
            sys.exit(1)
        else:
            print("✅ Setup successful! You're ready to go!")
            
    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

