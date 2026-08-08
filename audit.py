import os
import re
import ast

FRONTEND_DIR = 'frontend'
SRC_DIR = 'src'

out = open('audit_results_2.txt', 'w', encoding='utf-8')

def scan_frontend_backend():
    out.write("=== 2. FRONTEND-BACKEND BAĞLANTI KOPUKLUĞU ===\n")
    
    # 1. API routes from backend
    backend_routes = set()
    for root, _, files in os.walk(SRC_DIR):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # matches @router.get("/path") or @app.post("/path")
                matches = re.findall(r'@(?:router|app)\.(?:get|post|put|delete|patch)\([\'"]([^\'"]+)[\'"]', content)
                for match in matches:
                    backend_routes.add(match)

    # 2. Fetch calls from frontend
    frontend_fetches = set()
    for root, _, files in os.walk(FRONTEND_DIR):
        for file in files:
            if file.endswith(('.js', '.html')):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # matches fetch('/api/...') or fetch(API + '/api/...')
                matches = re.findall(r'fetch\([\'"`]([^\'"`]+)[\'"`]', content)
                for match in matches:
                    if match.startswith('/api/'):
                        frontend_fetches.add((path, match))
                
                # Also look for (API || '') + '/api/path'
                matches2 = re.findall(r'\+\s*[\'"`](/api/[^\'"`]+)[\'"`]', content)
                for match in matches2:
                    frontend_fetches.add((path, match))

    # Compare
    for path, fetch_url in frontend_fetches:
        # handle path parameters like /api/lab-history/{record_id}
        fetch_base = fetch_url.split('?')[0]
        # simplified check: is there any backend route that starts with fetch_base (or vice versa if fetch has IDs)
        found = False
        for route in backend_routes:
            # Replace {param} with regex
            route_regex = re.sub(r'\{[^\}]+\}', r'[^/]+', route)
            if re.match(f"^{route_regex}$", fetch_base) or fetch_base in route:
                found = True
                break
        
        if not found:
            out.write(f"POTENTIAL BROKEN FETCH: {path} calls {fetch_url} but no matching backend route found.\n")

def scan_onclick():
    out.write("\n=== ONCLICK FUNCTIONS DEFINED CHECK ===\n")
    
    # Extract all JS function names defined in the frontend
    defined_funcs = set()
    for root, _, files in os.walk(FRONTEND_DIR):
        for file in files:
            if file.endswith('.js'):
                with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                    content = f.read()
                # function foo()
                funcs = re.findall(r'function\s+([a-zA-Z0-9_]+)\s*\(', content)
                defined_funcs.update(funcs)
                # window.foo = 
                window_funcs = re.findall(r'window\.([a-zA-Z0-9_]+)\s*=', content)
                defined_funcs.update(window_funcs)
                # window.Module = { func: ... }
                # this is harder, just look for any identifier
                identifiers = re.findall(r'([a-zA-Z0-9_]+)', content)
                defined_funcs.update(identifiers)

    # Check onclick
    for root, _, files in os.walk(FRONTEND_DIR):
        for file in files:
            if file.endswith('.html'):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                onclicks = re.findall(r'onclick=[\'"]([^\'"]+)[\'"]', content)
                for onclick in onclicks:
                    # extract function name, e.g. window.Module.func() -> func
                    match = re.search(r'([a-zA-Z0-9_]+)\(', onclick)
                    if match:
                        func_name = match.group(1)
                        if func_name not in defined_funcs:
                            out.write(f"POTENTIAL UNDEFINED ONCLICK: {path} calls '{onclick}' (Function '{func_name}' not found in JS)\n")

scan_frontend_backend()
scan_onclick()
out.close()
