import os

# Create the required directories
dirs = [
    r'c:\zz_projects\dp_ai_devs_centrala\lesson_05\services',
    r'c:\zz_projects\dp_ai_devs_centrala\lesson_05\views',
    r'c:\zz_projects\dp_ai_devs_centrala\lesson_05\templates\lesson_05\partials'
]

for dir_path in dirs:
    os.makedirs(dir_path, exist_ok=True)
    print(f"Created: {dir_path}")

print("All directories created successfully!")
