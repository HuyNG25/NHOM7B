import os
files_to_modify = [
    'tests/test_analytics_export.py', 'tests/run_all_tests.py', 
    'tests/environment_local.json', 'src/main.py', 
    'RUN_LOCAL.md', 'README.md', 'openapi.yaml', 
    'docs/integration_notes.md', 'docs/changelog.md', 
    'Dockerfile', 'docker-compose.yml', '.env', '.env.example'
]
for f in files_to_modify:
    if os.path.exists(f):
        with open(f, 'r', encoding='utf-8') as file:
            content = file.read()
        if '8085' in content:
            with open(f, 'w', encoding='utf-8') as file:
                file.write(content.replace('8085', '8000'))
            print(f'Replaced in {f}')
